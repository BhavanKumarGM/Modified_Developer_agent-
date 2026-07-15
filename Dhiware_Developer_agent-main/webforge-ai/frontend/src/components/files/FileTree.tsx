import { ChevronRight, ChevronDown, File, Folder, FolderOpen, Download } from 'lucide-react'
import { clsx } from 'clsx'
import { useProjectStore } from '@/stores/projectStore'
import { api } from '@/services/api'
import type { FileNode } from '@/types'

const languageColors: Record<string, string> = {
  ts: 'text-blue-400', tsx: 'text-cyan-400', js: 'text-yellow-400', jsx: 'text-yellow-300',
  css: 'text-pink-400', html: 'text-orange-400', json: 'text-amber-400',
  py: 'text-green-400', md: 'text-text-secondary', svg: 'text-purple-400',
}

function getExt(name: string) {
  return name.split('.').pop() ?? ''
}

interface FileNodeProps {
  node: FileNode
  depth: number
}

function FileNodeRow({ node, depth }: FileNodeProps) {
  const { activeProject, activeFilePath, toggleFolder, openFile, setActiveFile } = useProjectStore()

  const handleClick = async () => {
    if (node.type === 'directory') {
      toggleFolder(node.path)
    } else {
      if (!activeProject) return
      setActiveFile(node.path)
      const existing = useProjectStore.getState().openFiles.find((f) => f.path === node.path)
      if (existing) return
      try {
        const { content, language } = await api.files.read(activeProject.id, node.path)
        openFile({ path: node.path, content, language })
      } catch {
        openFile({ path: node.path, content: '', language: 'text' })
      }
    }
  }

  const ext = getExt(node.name)
  const colorClass = languageColors[ext] ?? 'text-text-secondary'
  const isActive = activeFilePath === node.path

  return (
    <>
      <button
        onClick={handleClick}
        style={{ paddingLeft: `${8 + depth * 12}px` }}
        className={clsx(
          'group w-full flex items-center gap-1.5 py-0.5 pr-2 rounded text-xs transition-colors hover:bg-white/4',
          isActive ? 'bg-accent/10 text-accent' : 'text-text-secondary'
        )}
      >
        {node.type === 'directory' ? (
          <>
            {node.isExpanded ? (
              <ChevronDown className="h-3 w-3 flex-shrink-0" />
            ) : (
              <ChevronRight className="h-3 w-3 flex-shrink-0" />
            )}
            {node.isExpanded ? (
              <FolderOpen className="h-3.5 w-3.5 flex-shrink-0 text-amber-400" />
            ) : (
              <Folder className="h-3.5 w-3.5 flex-shrink-0 text-amber-400" />
            )}
          </>
        ) : (
          <>
            <span className="w-3 flex-shrink-0" />
            <File className={clsx('h-3.5 w-3.5 flex-shrink-0', colorClass)} />
          </>
        )}
        <span className="truncate">{node.name}</span>
      </button>
      {node.type === 'directory' && node.isExpanded && node.children?.map((child) => (
        <FileNodeRow key={child.path} node={child} depth={depth + 1} />
      ))}
    </>
  )
}

export function FileTree() {
  const { fileTree, activeProject } = useProjectStore()

  const handleDownload = () => {
    if (!activeProject) return
    const a = document.createElement('a')
    a.href = `/api/files/download/${activeProject.id}`
    a.download = ''
    a.click()
  }

  if (!activeProject) {
    return <p className="text-xs text-text-muted text-center py-8 px-4">No project selected.</p>
  }

  if (fileTree.length === 0) {
    return <p className="text-xs text-text-muted text-center py-8 px-4">No files generated yet.</p>
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-end px-2 py-1 border-b border-border-subtle">
        <button
          onClick={handleDownload}
          title="Download source as ZIP"
          className="flex items-center gap-1 px-2 py-1 rounded text-xs text-text-muted hover:text-text-primary hover:bg-white/5 transition-colors"
        >
          <Download className="h-3.5 w-3.5" />
          Download ZIP
        </button>
      </div>
      <div className="py-1 select-none flex-1 overflow-y-auto">
        {fileTree.map((node) => (
          <FileNodeRow key={node.path} node={node} depth={0} />
        ))}
      </div>
    </div>
  )
}
