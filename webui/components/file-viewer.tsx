"use client"

import { ScrollArea } from "@/components/ui/scroll-area"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Copy, Download, Edit } from "lucide-react"
import { useState } from "react"

interface FileViewerProps {
  selectedFile: string | null
  content: string
}

export function FileViewer({ selectedFile, content }: FileViewerProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!selectedFile) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <div className="text-6xl mb-4">📁</div>
          <h3 className="text-xl font-semibold mb-2">选择一个文件</h3>
          <p>从左侧文件树中选择一个文件来查看其内容</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* 文件头部 */}
      <div className="p-4 border-b border-border bg-card">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-card-foreground">{selectedFile}</h2>
            <p className="text-sm text-muted-foreground">UTF-8 编码</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleCopy} className="gap-2 bg-transparent">
              <Copy className="h-4 w-4" />
              {copied ? "已复制" : "复制"}
            </Button>
            <Button variant="outline" size="sm" className="gap-2 bg-transparent">
              <Edit className="h-4 w-4" />
              编辑
            </Button>
            <Button variant="outline" size="sm" className="gap-2 bg-transparent">
              <Download className="h-4 w-4" />
              下载
            </Button>
          </div>
        </div>
      </div>

      {/* 文件内容 */}
      <ScrollArea className="flex-1">
        <Card className="m-4 p-0 overflow-hidden">
          <pre className="p-4 text-sm font-mono bg-card text-card-foreground overflow-x-auto">
            <code>{content}</code>
          </pre>
        </Card>
      </ScrollArea>
    </div>
  )
}
