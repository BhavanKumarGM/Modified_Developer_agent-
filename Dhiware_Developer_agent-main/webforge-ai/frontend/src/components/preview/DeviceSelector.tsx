import { Monitor, Tablet, Smartphone } from 'lucide-react'
import { clsx } from 'clsx'
import { useUIStore } from '@/stores/uiStore'
import type { DeviceMode } from '@/types'

const devices: { mode: DeviceMode; icon: React.ElementType; label: string; width: string }[] = [
  { mode: 'desktop', icon: Monitor, label: 'Desktop', width: '100%' },
  { mode: 'tablet', icon: Tablet, label: 'Tablet', width: '768px' },
  { mode: 'mobile', icon: Smartphone, label: 'Mobile', width: '375px' },
]

interface DeviceSelectorProps {
  onReload?: () => void
}

export function DeviceSelector({ onReload }: DeviceSelectorProps) {
  const { deviceMode, setDeviceMode } = useUIStore()

  return (
    <div className="flex items-center gap-0.5 rounded-lg border border-border-subtle bg-surface-3 p-0.5">
      {devices.map(({ mode, icon: Icon, label }) => (
        <button
          key={mode}
          onClick={() => setDeviceMode(mode)}
          title={label}
          className={clsx(
            'flex items-center justify-center h-6 w-7 rounded transition-colors',
            deviceMode === mode
              ? 'bg-accent/20 text-accent'
              : 'text-text-muted hover:text-text-secondary'
          )}
        >
          <Icon className="h-3.5 w-3.5" />
        </button>
      ))}
    </div>
  )
}

export function getDeviceWidth(mode: DeviceMode): string {
  const map: Record<DeviceMode, string> = {
    desktop: '100%',
    tablet: '768px',
    mobile: '375px',
  }
  return map[mode]
}
