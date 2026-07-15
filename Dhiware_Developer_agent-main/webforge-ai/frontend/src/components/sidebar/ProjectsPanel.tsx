import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, FolderOpen, Trash2, Upload, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import { useProjectStore } from '@/stores/projectStore'
import { useChatStore } from '@/stores/chatStore'
import { useUIStore } from '@/stores/uiStore'
import { api } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import type { Project, FileNode } from '@/types'

function pickMainFile(nodes: FileNode[]): string | null {
  const flat: FileNode[] = []
  const walk = (ns: FileNode[]) => ns.forEach((n) => { if (n.type === 'file') flat.push(n); if (n.children) walk(n.children) })
  walk(nodes)
  for (const p of ['src/App.tsx', 'src/App.jsx', 'src/app.tsx', 'App.tsx', 'index.tsx']) {
    if (flat.find((f) => f.path === p)) return p
  }
  return flat.find((f) => f.path.endsWith('.tsx') || f.path.endsWith('.jsx') || f.path.endsWith('.ts'))?.path ?? flat[0]?.path ?? null
}

const frameworkIcon: Record<string, string> = {
  react: '⚛️', nextjs: '▲', vue: '💚', angular: '🔴', static: '🌐', unknown: '📦',
}

const statusVariant = {
  idle: 'default', generating: 'warning', running: 'success', error: 'error', ready: 'success',
} as const

interface NewProjectDialogProps {
  onClose: () => void
  onCreate: (name: string, description: string) => void
}

function NewProjectDialog({ onClose, onCreate }: NewProjectDialogProps) {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    if (!name.trim()) return
    setLoading(true)
    onCreate(name.trim(), desc.trim())
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="mx-3 mb-2 rounded-xl border border-border-default bg-surface-3 p-3 space-y-2"
    >
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Project name"
        className="w-full rounded-lg bg-surface-4 border border-border-subtle px-3 py-1.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50"
        onKeyDown={(e) => e.key === 'Enter' && submit()}
      />
      <input
        value={desc}
        onChange={(e) => setDesc(e.target.value)}
        placeholder="Description (optional)"
        className="w-full rounded-lg bg-surface-4 border border-border-subtle px-3 py-1.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50"
        onKeyDown={(e) => e.key === 'Enter' && submit()}
      />
      <div className="flex gap-2">
        <Button variant="primary" size="sm" className="flex-1" loading={loading} onClick={submit}>
          Create
        </Button>
        <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
      </div>
    </motion.div>
  )
}

export function ProjectsPanel() {
  const { projects, activeProject, setProjects, addProject, setActiveProject, removeProject, setFileTree, openFile } =
    useProjectStore()
  const clearMessages = useChatStore((s) => s.clearMessages)
  const { setSidebarPanel, isSidebarCollapsed, toggleSidebar } = useUIStore()
  const [showNew, setShowNew] = useState(false)
  const [loading, setLoading] = useState(true)
  const [uploadRef, setUploadRef] = useState<HTMLInputElement | null>(null)

  useEffect(() => {
    api.projects.list()
      .then((r) => setProjects(r.projects))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [setProjects])

  const handleCreate = async (name: string, description: string) => {
    try {
      const project = await api.projects.create({ name, description })
      addProject(project)
      setActiveProject(project)
      clearMessages()
      setShowNew(false)
    } catch (e) {
      console.error(e)
    }
  }

  const loadProjectFiles = async (project: Project) => {
    if (!project.rootPath) return
    try {
      const { tree } = await api.files.tree(project.id)
      setFileTree(tree)
      setSidebarPanel('files')
      if (isSidebarCollapsed) toggleSidebar()
      const mainPath = pickMainFile(tree)
      if (!mainPath) return
      const already = useProjectStore.getState().openFiles.find((f) => f.path === mainPath)
      if (already) return
      const { content, language } = await api.files.read(project.id, mainPath)
      openFile({ path: mainPath, content, language })
    } catch {
      // non-fatal
    }
  }

  const handleSelect = (project: Project) => {
    if (activeProject?.id === project.id) return
    setActiveProject(project)
    clearMessages()
    loadProjectFiles(project)
  }

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    await api.projects.delete(id).catch(() => {})
    removeProject(id)
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1 px-3 py-2">
        <Button variant="primary" size="sm" className="flex-1 gap-1.5" onClick={() => setShowNew(true)}>
          <Plus className="h-3.5 w-3.5" /> New Project
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => uploadRef?.click()}
          title="Upload ZIP"
        >
          <Upload className="h-3.5 w-3.5" />
        </Button>
        <input
          ref={setUploadRef}
          type="file"
          accept=".zip"
          className="hidden"
          onChange={async (e) => {
            const file = e.target.files?.[0]
            if (!file) return
            try {
              const project = await api.upload.zip(file)
              addProject(project)
              setActiveProject(project)
              clearMessages()
              await loadProjectFiles(project)
            } catch (err) {
              console.error(err)
            }
          }}
        />
      </div>

      <AnimatePresence>
        {showNew && (
          <NewProjectDialog onClose={() => setShowNew(false)} onCreate={handleCreate} />
        )}
      </AnimatePresence>

      {loading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="h-5 w-5 text-text-muted animate-spin" />
        </div>
      ) : projects.length === 0 ? (
        <p className="text-xs text-text-muted text-center py-8 px-4">
          No projects yet. Create one or upload a ZIP.
        </p>
      ) : (
        <div className="space-y-0.5 px-2">
          {projects.map((project) => (
            <motion.button
              key={project.id}
              layout
              onClick={() => handleSelect(project)}
              className={clsx(
                'group w-full flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors',
                activeProject?.id === project.id
                  ? 'bg-accent/10 border border-accent/20'
                  : 'hover:bg-white/4 border border-transparent'
              )}
            >
              <span className="text-base leading-none">{frameworkIcon[project.framework]}</span>
              <div className="flex-1 min-w-0">
                <p className={clsx(
                  'text-sm font-medium truncate',
                  activeProject?.id === project.id ? 'text-accent' : 'text-text-primary'
                )}>
                  {project.name}
                </p>
                {project.description && (
                  <p className="text-[11px] text-text-muted truncate">{project.description}</p>
                )}
              </div>
              <div className="flex items-center gap-1">
                <Badge variant={statusVariant[project.status]} dot>
                  {project.status}
                </Badge>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 opacity-0 group-hover:opacity-100"
                  onClick={(e) => handleDelete(e, project.id)}
                >
                  <Trash2 className="h-3 w-3 text-red-400" />
                </Button>
              </div>
            </motion.button>
          ))}
        </div>
      )}
    </div>
  )
}
