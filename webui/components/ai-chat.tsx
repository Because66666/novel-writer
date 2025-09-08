"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Card } from "@/components/ui/card"
import { Send, Bot, User, Square, AlertCircle, CheckCircle, Settings } from "lucide-react"
import { useApiContext } from "@/app/page"

interface Message {
  id: string
  type: "user" | "ai" | "system"
  content: string
  timestamp: Date
  taskId?: string
  messageType?: "start" | "complete" | "error" | "end" | "step"
}

interface TaskStatus {
  taskId: string
  status: "running" | "completed" | "error" | "stopped"
  startTime: number
  duration?: number
}

interface ApiConfig {
  baseUrl: string
  isConnected: boolean
}

export function AIChat(): React.JSX.Element {
  const { baseUrl, isConnected, setIsConnected, workingDir } = useApiContext()
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      type: "ai",
      content: "你好！我是Trae Agent AI助手。我可以帮助你执行代码任务、分析项目或提供编程建议。请输入你的任务描述。",
      timestamp: new Date(),
    },
  ])
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [currentTask, setCurrentTask] = useState<TaskStatus | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  const scrollAreaRef = useRef<HTMLDivElement>(null)

  // 检查API连接状态
  const checkApiHealth = async () => {
    try {
      const response = await fetch(`${baseUrl}/api/health`)
      const data = await response.json()
      setIsConnected(data.status === "healthy")
    } catch (error) {
      setIsConnected(false)
    }
  }

  // 停止当前任务
  const stopCurrentTask = async () => {
    if (!currentTask || currentTask.status !== "running") return

    try {
      await fetch(`${baseUrl}/api/tasks/${currentTask.taskId}/stop`, {
        method: "POST"
      })
      
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      
      setCurrentTask(prev => prev ? { ...prev, status: "stopped" } : null)
      setIsLoading(false)
      
      const systemMessage: Message = {
        id: Date.now().toString(),
        type: "system",
        content: "任务已停止",
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, systemMessage])
    } catch (error) {
      console.error("停止任务失败:", error)
    }
  }

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading || !isConnected) return

    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: inputValue,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    const taskContent = inputValue
    setInputValue("")
    setIsLoading(true)

    try {
      // 执行任务
      const response = await fetch(`${baseUrl}/api/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          task: taskContent,
          working_dir: workingDir,
          provider: "openai",
          model: "glm-4-flash",
          max_steps: 10,
          config_file: "trae_config.yaml"
        }),
      })

      const data = await response.json()
      
      if (response.ok && data.status === "success") {
        const taskId = data.task_id
        setCurrentTask({
          taskId,
          status: "running",
          startTime: Date.now()
        })

        // 建立流式连接
        const eventSource = new EventSource(`${baseUrl}/api/tasks/${taskId}/stream`)
        eventSourceRef.current = eventSource

        eventSource.onmessage = (event) => {
          const messageData = JSON.parse(event.data)
          
          // 构建消息内容
          let content = messageData.message || `[${messageData.type}] 任务状态更新`
          
          // 如果是错误消息，显示更详细的信息
          if (messageData.type === "error") {
            content = messageData.error || messageData.message || "任务执行出错"
            if (messageData.traceback) {
              console.error("Task Error Traceback:", messageData.traceback)
            }
          }
          
          // 如果是完成消息，显示结果信息和步骤详情
          if (messageData.type === "complete" && messageData.result) {
            const result = messageData.result
            
            // 首先添加每个步骤的llm_response作为AI消息
            if (result.steps && Array.isArray(result.steps)) {
              result.steps.forEach((step: any, index: number) => {
                if (step.llm_response && step.llm_response.trim()) {
                  const stepMessage: Message = {
                    id: Date.now().toString() + Math.random() + index,
                    type: "ai",
                    content: step.llm_response.trim(),
                    timestamp: new Date(),
                    taskId: messageData.task_id,
                    messageType: "step"
                  }
                  setMessages(prev => [...prev, stepMessage])
                }
              })
            }
            
            // 然后添加任务完成的摘要信息
            content = `任务完成！\n输出: ${result.output || '无输出'}\n步骤数: ${result.steps_count || 0}\n成本: $${result.total_cost || 0}\n成功: ${result.success ? '是' : '否'}`
          }
          
          const streamMessage: Message = {
            id: Date.now().toString() + Math.random(),
            type: messageData.type === "error" ? "system" : (messageData.type === "complete" ? "system" : "ai"),
            content: content,
            timestamp: new Date(),
            taskId: messageData.task_id,
            messageType: messageData.type
          }
          
          setMessages(prev => [...prev, streamMessage])
          
          if (messageData.type === "complete" || messageData.type === "error" || messageData.type === "end") {
            setCurrentTask(prev => prev ? {
              ...prev,
              status: messageData.type === "error" ? "error" : "completed",
              duration: Date.now() - prev.startTime
            } : null)
            setIsLoading(false)
            eventSource.close()
            eventSourceRef.current = null
          }
        }

        eventSource.onerror = (error) => {
          console.error("流式连接错误:", error)
          const errorMessage: Message = {
            id: Date.now().toString(),
            type: "system",
            content: "连接中断，请检查API服务状态",
            timestamp: new Date(),
          }
          setMessages(prev => [...prev, errorMessage])
          setIsLoading(false)
          setCurrentTask(prev => prev ? { ...prev, status: "error" } : null)
          eventSource.close()
          eventSourceRef.current = null
        }
      } else {
        // 处理400错误和其他API错误
        let errorMessage = "任务启动失败"
        if (data.error) {
          errorMessage = typeof data.error === 'string' ? data.error : JSON.stringify(data.error)
        } else if (data.message) {
          errorMessage = data.message
        }
        
        // 如果有traceback信息，在控制台输出详细错误
        if (data.traceback) {
          console.error("API Error Traceback:", data.traceback)
        }
        
        throw new Error(errorMessage)
      }
    } catch (error) {
      const errorMessage: Message = {
        id: Date.now().toString(),
        type: "system",
        content: `错误: ${error instanceof Error ? error.message : "未知错误"}`,
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, errorMessage])
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // 组件挂载时检查API状态
  useEffect(() => {
    checkApiHealth()
    const interval = setInterval(checkApiHealth, 30000) // 每30秒检查一次
    return () => clearInterval(interval)
  }, [])

  // 组件卸载时清理EventSource
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  // 自动滚动到底部
  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]')
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight
      }
    }
  }, [messages])

  return (
    <div className="h-full flex flex-col">
      {/* AI聊天头部 */}
      <div className="p-4 border-b border-sidebar-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-sidebar-accent" />
            <h2 className="text-lg font-semibold text-sidebar-foreground">Trae Agent</h2>
          </div>
          <div className="flex items-center gap-2">
             <Button
               onClick={() => setShowSettings(!showSettings)}
               size="sm"
               variant="ghost"
               className="h-6 w-6 p-0"
             >
               <Settings className="h-3 w-3" />
             </Button>
             {isConnected ? (
               <CheckCircle className="h-4 w-4 text-green-500" />
             ) : (
               <AlertCircle className="h-4 w-4 text-red-500" />
             )}
             <span className={isConnected ? 'text-xs text-green-600' : 'text-xs text-red-600'}>
               {isConnected ? "已连接" : "未连接"}
             </span>
           </div>
        </div>
        <div className="flex items-center justify-between mt-1">
          <p className="text-sm text-muted-foreground">智能代码任务执行</p>
          {currentTask && currentTask.status === "running" && (
            <Button
              onClick={stopCurrentTask}
              size="sm"
              variant="outline"
              className="h-6 px-2 text-xs"
            >
              <Square className="h-3 w-3 mr-1" />
              停止任务
            </Button>
          )}
        </div>
      </div>

      {/* 消息列表 */}
      <ScrollArea className="flex-1 p-4" ref={scrollAreaRef}>
        <div className="space-y-4">
          {messages.map((message) => (
            <div key={message.id} className={message.type === "user" ? "flex gap-3 justify-end" : "flex gap-3 justify-start"}>
              {(message.type === "ai" || message.type === "system") && (
                <div className="flex-shrink-0">
                  <div className={message.type === "system" ? "w-8 h-8 rounded-full flex items-center justify-center bg-yellow-500" : "w-8 h-8 rounded-full flex items-center justify-center bg-sidebar-accent"}>
                    {message.type === "system" ? (
                      <AlertCircle className="h-4 w-4 text-white" />
                    ) : (
                      <Bot className="h-4 w-4 text-sidebar-accent-foreground" />
                    )}
                  </div>
                </div>
              )}

              <Card
                className={
                  message.type === "user" 
                    ? "max-w-[80%] p-3 bg-blue-500 text-white" 
                    : message.type === "system"
                    ? "max-w-[80%] p-3 bg-yellow-50 border-yellow-200 text-yellow-800"
                    : "max-w-[80%] p-3 bg-card text-card-foreground"
                }
              >
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
                <div className="flex items-center justify-between mt-2">
                  <p
                    className={
                      message.type === "user" 
                        ? "text-xs opacity-70 text-white" 
                        : message.type === "system"
                        ? "text-xs opacity-70 text-yellow-600"
                        : "text-xs opacity-70 text-muted-foreground"
                    }
                  >
                    {message.timestamp.toLocaleTimeString()}
                  </p>
                  {message.taskId && (
                    <span className="text-xs opacity-50 font-mono">
                      {message.taskId.slice(0, 8)}
                    </span>
                  )}
                </div>
              </Card>

              {message.type === "user" && (
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center">
                    <User className="h-4 w-4 text-white" />
                  </div>
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-3 justify-start">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 rounded-full bg-sidebar-accent flex items-center justify-center">
                  <Bot className="h-4 w-4 text-sidebar-accent-foreground" />
                </div>
              </div>
              <Card className="bg-card text-card-foreground p-3">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
                    <div
                      className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce"
                      style={{ animationDelay: "0.1s" }}
                    />
                    <div
                      className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce"
                      style={{ animationDelay: "0.2s" }}
                    />
                  </div>
                  <span className="text-sm text-muted-foreground">AI正在思考...</span>
                </div>
              </Card>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* 输入区域 */}
      <div className="p-4 border-t border-sidebar-border">
        {showSettings && (
          <div className="mb-3 p-3 bg-gray-50 border border-gray-200 rounded text-sm">
            <div className="space-y-2">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">API地址</label>
                <div className="text-xs text-gray-600 font-mono">{baseUrl}</div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">工作目录</label>
                <div className="text-xs text-gray-600 font-mono">{workingDir}</div>
              </div>
            </div>
          </div>
        )}
        {!isConnected && (
          <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
            API服务未连接，请确保Flask服务运行在 {baseUrl}
          </div>
        )}
        {currentTask && (
          <div className="mb-3 p-2 bg-blue-50 border border-blue-200 rounded text-sm">
            <div className="flex items-center justify-between">
              <span className="text-blue-700">
                任务状态: <span className="font-medium">{currentTask.status}</span>
              </span>
              {currentTask.duration && (
                <span className="text-blue-600 text-xs">
                  耗时: {Math.round(currentTask.duration / 1000)}s
                </span>
              )}
            </div>
          </div>
        )}
        <div className="flex gap-2">
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={isConnected ? "输入你的任务描述..." : "等待API连接..."}
            className="flex-1"
            disabled={isLoading || !isConnected}
          />
          <Button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading || !isConnected}
            size="icon"
            className="bg-sidebar-accent hover:bg-sidebar-accent/90 text-sidebar-accent-foreground"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
