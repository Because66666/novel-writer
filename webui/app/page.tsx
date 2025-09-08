"use client"

import { useState, createContext, useContext } from "react"
import { FileTree } from "@/components/file-tree"
import { FileViewer } from "@/components/file-viewer"
import { AIChat } from "@/components/ai-chat"
import { ThemeProvider } from "@/components/theme-provider"

// API配置上下文
interface ApiContextType {
  baseUrl: string
  setBaseUrl: (url: string) => void
  isConnected: boolean
  setIsConnected: (connected: boolean) => void
  workingDir: string
  setWorkingDir: (dir: string) => void
}

const ApiContext = createContext<ApiContextType | undefined>(undefined)

export const useApiContext = () => {
  const context = useContext(ApiContext)
  if (!context) {
    throw new Error('useApiContext must be used within ApiProvider')
  }
  return context
}

function HomePage() {
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [fileContent, setFileContent] = useState<string>("")

  return (
    <div className="flex h-screen bg-background">
      {/* 左侧文件树 */}
      <div className="w-80 border-r border-sidebar-border bg-sidebar">
        <FileTree
          onFileSelect={(filePath, content) => {
            setSelectedFile(filePath)
            setFileContent(content)
          }}
        />
      </div>

      {/* 中间文件内容查看器 */}
      <div className="flex-1 bg-background">
        <FileViewer selectedFile={selectedFile} content={fileContent} />
      </div>

      {/* 右侧AI聊天界面 */}
      <div className="w-96 border-l border-sidebar-border bg-sidebar">
        <AIChat />
      </div>
    </div>
  )
}

// API配置提供者组件
function ApiProvider({ children }: { children: React.ReactNode }) {
  const [baseUrl, setBaseUrl] = useState("http://localhost:5000/")
  const [isConnected, setIsConnected] = useState(false)
  const [workingDir, setWorkingDir] = useState(process.cwd?.() || "/tmp")

  return (
    <ApiContext.Provider value={{
      baseUrl,
      setBaseUrl,
      isConnected,
      setIsConnected,
      workingDir,
      setWorkingDir
    }}>
      {children}
    </ApiContext.Provider>
  )
}

// 主导出组件
export default function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <ApiProvider>
        <HomePage />
      </ApiProvider>
    </ThemeProvider>
  )
}
