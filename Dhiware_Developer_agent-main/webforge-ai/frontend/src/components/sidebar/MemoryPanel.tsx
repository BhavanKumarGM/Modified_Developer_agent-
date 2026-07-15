import { Brain, Tag, Layers, Palette, Code2 } from 'lucide-react'
import { useProjectStore } from '@/stores/projectStore'

export function MemoryPanel() {
  const activeProject = useProjectStore((s) => s.activeProject)
  const meta = activeProject?.metadata

  if (!activeProject) {
    return <p className="text-xs text-text-muted text-center py-8 px-4">Select a project to view memory.</p>
  }

  const entries = [
    { icon: Layers, label: 'Framework', value: activeProject.framework },
    { icon: Palette, label: 'Styling', value: meta?.styling?.join(', ') },
    { icon: Tag, label: 'Architecture', value: meta?.architecture },
    { icon: Code2, label: 'Naming', value: meta?.namingConvention },
    { icon: Brain, label: 'Libraries', value: meta?.preferredLibraries?.join(', ') },
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
