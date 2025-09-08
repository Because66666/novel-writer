"use client"

import { useState } from "react"
import { ChevronRight, ChevronDown, File, Folder, FolderOpen } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"

interface FileNode {
  name: string
  type: "file" | "folder"
  path: string
  children?: FileNode[]
}

interface FileTreeProps {
  onFileSelect: (filePath: string, content: string) => void
}

// 模拟文件系统数据
const mockFileSystem: FileNode[] = [
  {
    name: "src",
    type: "folder",
    path: "/src",
    children: [
      {
        name: "components",
        type: "folder",
        path: "/src/components",
        children: [
          { name: "Header.tsx", type: "file", path: "/src/components/Header.tsx" },
          { name: "Footer.tsx", type: "file", path: "/src/components/Footer.tsx" },
        ],
      },
      {
        name: "pages",
        type: "folder",
        path: "/src/pages",
        children: [
          { name: "index.tsx", type: "file", path: "/src/pages/index.tsx" },
          { name: "about.tsx", type: "file", path: "/src/pages/about.tsx" },
        ],
      },
      { name: "utils.ts", type: "file", path: "/src/utils.ts" },
    ],
  },
  {
    name: "public",
    type: "folder",
    path: "/public",
    children: [
      { name: "favicon.ico", type: "file", path: "/public/favicon.ico" },
      { name: "logo.png", type: "file", path: "/public/logo.png" },
    ],
  },
  { name: "package.json", type: "file", path: "/package.json" },
  { name: "README.md", type: "file", path: "/README.md" },
]

// 模拟文件内容
const mockFileContents: Record<string, string> = {
  "/src/components/Header.tsx": `import React from 'react'

export const Header: React.FC = () => {
  return (
    <header className="bg-primary text-primary-foreground p-4">
      <h1 className="text-2xl font-bold">My App</h1>
    </header>
  )
}`,
  "/src/components/Footer.tsx": `import React from 'react'

export const Footer: React.FC = () => {
  return (
    <footer className="bg-muted text-muted-foreground p-4 text-center">
      <p>&copy; 2024 My App. All rights reserved.</p>
    </footer>
  )
}`,
  "/src/pages/index.tsx": `import React from 'react'
import { Header } from '../components/Header'
import { Footer } from '../components/Footer'

const HomePage: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 p-8">
        <h2 className="text-3xl font-semibold mb-4">Welcome to My App</h2>
        <p className="text-lg text-muted-foreground">
          This is the home page of our application.
        </p>
      </main>
      <Footer />
    </div>
  )
}

export default HomePage`,
  "/package.json": `{
  "name": "my-app",
  "version": "1.0.0",
  "description": "A sample application",
  "main": "index.js",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "react": "^18.0.0",
    "next": "^14.0.0"
  }
}`,
  "/README.md": `# My App

This is a sample application built with React and Next.js.

## Getting Started

1. Install dependencies: \`npm install\`
2. Run the development server: \`npm run dev\`
3. Open [http://localhost:3000](http://localhost:3000) in your browser

## Features

- Modern React components
- TypeScript support
- Responsive design
- Dark mode support`,
}

export function FileTree({ onFileSelect }: FileTreeProps) {
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(["/src"]))

  const toggleFolder = (path: string) => {
    const newExpanded = new Set(expandedFolders)
    if (newExpanded.has(path)) {
      newExpanded.delete(path)
    } else {
      newExpanded.add(path)
    }
    setExpandedFolders(newExpanded)
  }

  const handleFileClick = (filePath: string) => {
    const content = mockFileContents[filePath] || `// 文件内容: ${filePath}\n// 这是一个示例文件`
    onFileSelect(filePath, content)
  }

  const renderNode = (node: FileNode, depth = 0) => {
    const isExpanded = expandedFolders.has(node.path)
    const paddingLeft = depth * 16 + 8

    return (
      <div key={node.path}>
        <Button
          variant="ghost"
          className="w-full justify-start h-8 px-2 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
          style={{ paddingLeft }}
          onClick={() => {
            if (node.type === "folder") {
              toggleFolder(node.path)
            } else {
              handleFileClick(node.path)
            }
          }}
        >
          <div className="flex items-center gap-2">
            {node.type === "folder" ? (
              <>
                {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                {isExpanded ? <FolderOpen className="h-4 w-4" /> : <Folder className="h-4 w-4" />}
              </>
            ) : (
              <>
                <div className="w-4" />
                <File className="h-4 w-4" />
              </>
            )}
            <span className="text-sm">{node.name}</span>
          </div>
        </Button>

        {node.type === "folder" && isExpanded && node.children && (
          <div>{node.children.map((child) => renderNode(child, depth + 1))}</div>
        )}
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-sidebar-border">
        <h2 className="text-lg font-semibold text-sidebar-foreground">文件浏览器</h2>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2">{mockFileSystem.map((node) => renderNode(node))}</div>
      </ScrollArea>
    </div>
  )
}
