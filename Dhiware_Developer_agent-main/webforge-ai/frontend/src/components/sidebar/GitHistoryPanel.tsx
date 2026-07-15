import { useEffect } from 'react'
import { GitBranch, RotateCcw, Loader2 } from 'lucide-react'
import { useProjectStore } from '@/stores/projectStore'
import { api } from '@/services/api'
import { Button } from '@/components/ui/Button'

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

export function GitHistoryPanel() {
  const { activeProject, gitHistory, setGitHistory } = useProjectStore()

  useEffect(() => {
    if (!activeProject) return
    api.git.history(activeProject.id)
      .then((r) => setGitHistory(r.snapshots))
      .catch(() => {})
  }, [activeProject, setGitHistory])

  if (!activeProject) {
    return <p className="text-xs text-text-muted text-center py-8 px-4">Select a project first.</p>
  }

  if (gitHistory.length === 0) {
    return <p className="text-xs text-text-muted text-center py-8 px-4">No snapshots yet.</p>
  }

  return (
    <div className="space-y-0.5 px-2 py-1">
      {gitHistory.map((snap) => (
        <div
          key={snap.id}
          className="group flex items-start gap-2.5 rounded-lg px-2.5 py-2 hover:bg-white/4 transition-colors"
        >
          <GitBranch className="h-3.5 w-3.5 text-text-muted mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-xs text-text-primary truncate">{snap.message}</p>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-[10px] text-text-muted">{timeAgo(snap.timestamp)}</span>
              <span className="text-[10px] text-emerald-400">+{snap.additions}</span>
              <span className="text-[10px] text-red-400">-{snap.deletions}</span>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 opacity-0 group-hover:opacity-100"
            title="Restore snapshot"
            onClick={() => api.git.restore(activeProject.id, snap.id).catch(() => {})}
          >
            <RotateCcw className="h-3 w-3 text-text-secondary" />
          </Button>
        </div>
      ))}
    </div>
  )
}
