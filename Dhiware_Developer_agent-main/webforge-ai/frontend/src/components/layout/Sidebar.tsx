import { motion, AnimatePresence } from 'framer-motion'
import {
  FolderKanban, Files, Cpu, GitBranch, Brain, Settings, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useUIStore } from '@/stores/uiStore'
import { Button } from '@/components/ui/Button'
import { Tooltip } from '@/components/ui/Tooltip'
import { ProjectsPanel } from '@/components/sidebar/ProjectsPanel'
import { AgentStatusPanel } from '@/components/sidebar/AgentStatusPanel'
import { GitHistoryPanel } from '@/components/sidebar/GitHistoryPanel'
import { MemoryPanel } from '@/components/sidebar/MemoryPanel'
import { SettingsPanel } from '@/components/sidebar/SettingsPanel'
import { FileTree } from '@/components/files/FileTree'

type Panel = 'projects' | 'files' | 'agents' | 'git' | 'memory' | 'settings'

const navItems: { id: Panel; icon: React.ElementType; label: string }[] = [
  { id: 'projects', icon: FolderKanban, label: 'Projects' },
  { id: 'files', icon: Files, label: 'Files' },
  { id: 'agents', icon: Cpu, label: 'Agents' },
  { id: 'git', icon: GitBranch, label: 'Git History' },
  { id: 'memory', icon: Brain, label: 'Memory' },
  { id: 'settings', icon: Settings, label: 'Settings' },
]

const panelLabels: Record<Panel, string> = {
  projects: 'Projects', files: 'File Explorer', agents: 'Agent Status',
  git: 'Git History', memory: 'Project Memory', settings: 'Settings',
}

export function Sidebar() {
  const { sidebarPanel, setSidebarPanel, isSidebarCollapsed, toggleSidebar } = useUIStore()

  return (
    <div className="flex h-full">
      {/* Icon rail */}
      <nav className="flex flex-col items-center gap-1 w-12 py-3 border-r border-border-subtle bg-surface-1">
        <div className="mb-3 flex flex-col items-center">
          <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center">
            <span className="text-white text-xs font-bold">W</span>
          </div>
        </div>

        {navItems.map(({ id, icon: Icon, label }) => (
          <Tooltip key={id} content={label} side="right">
            <Button
              variant="ghost"
              size="icon"
              className={clsx(
                'h-9 w-9 rounded-lg transition-all',
                sidebarPanel === id && !isSidebarCollapsed
                  ? 'bg-accent/15 text-accent'
                  : 'text-text-muted hover:text-text-primary'
              )}
              onClick={() => {
                if (sidebarPanel === id && !isSidebarCollapsed) {
                  toggleSidebar()
                } else {
                  setSidebarPanel(id as Panel)
                  if (isSidebarCollapsed) toggleSidebar()
                }
              }}
            >
              <Icon className="h-4 w-4" />
            </Button>
          </Tooltip>
        ))}

        <div className="flex-1" />

        <Tooltip content={isSidebarCollapsed ? 'Expand' : 'Collapse'} side="right">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-text-muted hover:text-text-primary"
            onClick={toggleSidebar}
          >
            {isSidebarCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
          </Button>
        </Tooltip>
      </nav>

      {/* Panel */}
      <AnimatePresence initial={false}>
        {!isSidebarCollapsed && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 248, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 400, damping: 40 }}
            className="flex flex-col h-full border-r border-border-subtle bg-surface-1 overflow-hidden"
          >
            <div className="flex-shrink-0 px-3 py-2.5 border-b border-border-subtle">
              <h2 className="text-[11px] font-semibold text-text-muted uppercase tracking-widest">
                {panelLabels[sidebarPanel]}
              </h2>
            </div>
            <div className="flex-1 overflow-y-auto min-h-0">
              {sidebarPanel === 'projects' && <ProjectsPanel />}
              {sidebarPanel === 'files' && <FileTree />}
              {sidebarPanel === 'agents' && <AgentStatusPanel />}
              {sidebarPanel === 'git' && <GitHistoryPanel />}
              {sidebarPanel === 'memory' && <MemoryPanel />}
              {sidebarPanel === 'settings' && <SettingsPanel />}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
