import { useEffect, useState } from 'react'
import { Brain, Tag, Layers, Palette, Code2 } from 'lucide-react'
import { useProjectStore } from '@/stores/projectStore'
import { api } from '@/services/api'
import type { ProjectMetadata } from '@/types'

export function MemoryPanel() {
  const activeProject = useProjectStore((s) => s.activeProject)
  const [memory, setMemory] = useState<ProjectMetadata | undefined>(activeProject?.metadata)

  useEffect(() => {
    if (!activeProject) {
      setMemory(undefined)
      return
    }
    // Seed from whatever the project list/detail call already gave us, then
    // refresh from the dedicated memory endpoint so this panel reflects
    // MemoryAgent's latest update even if the project object in the store
    // is stale.
    setMemory(activeProject.metadata)
    let cancelled = false
    api.projects
      .memory(activeProject.id)
      .then((res) => {
        if (!cancelled) setMemory(res.memory as ProjectMetadata)
      })
      .catch(() => {
        // Keep the seeded value; the panel just won't refresh this turn.
      })
    return () => {
      cancelled = true
    }
  }, [activeProject?.id, activeProject?.metadata])

  if (!activeProject) {
    return <p className="text-xs text-text-muted text-center py-8 px-4">Select a project to view memory.</p>
  }

  const entries = [
    { icon: Layers, label: 'Framework', value: activeProject.framework },
    { icon: Palette, label: 'Styling', value: memory?.styling?.join(', ') },
    { icon: Tag, label: 'Architecture', value: memory?.architecture },
    { icon: Code2, label: 'Naming', value: memory?.naming_convention },
    { icon: Brain, label: 'Libraries', value: memory?.preferred_libraries?.join(', ') },
  ].filter((e) => e.value)

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-8 px-4 text-center">
        <Brain className="h-8 w-8 text-text-muted opacity-40" />
        <p className="text-xs text-text-muted">Project memory will be built as you work.</p>
      </div>
    )
  }

  return (
    <div className="p-3 space-y-2">
      {entries.map(({ icon: Icon, label, value }) => (
        <div key={label} className="rounded-lg bg-white/4 px-3 py-2">
          <div className="flex items-center gap-1.5 mb-0.5">
            <Icon className="h-3 w-3 text-accent" />
            <span className="text-[10px] text-text-muted font-medium uppercase tracking-wide">{label}</span>
          </div>
          <p className="text-xs text-text-primary">{value}</p>
        </div>
      ))}
    </div>
  )
}
