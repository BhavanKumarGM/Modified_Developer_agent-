import { useState, useEffect, useRef } from 'react'
import { RefreshCw, ExternalLink, Play, Square, Globe, Loader2, Terminal, AlertCircle } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import { DeviceSelector, getDeviceWidth } from './DeviceSelector'
import { Button } from '@/components/ui/Button'
import { useUIStore } from '@/stores/uiStore'
import { useProjectStore } from '@/stores/projectStore'
import { api } from '@/services/api'

type PreviewStatus = 'idle' | 'installing' | 'starting' | 'running' | 'error'

const STATUS_MESSAGES: Record<PreviewStatus, string> = {
  idle: 'Ready to launch',
  installing: 'Installing dependencies (this may take 1-2 min)…',
  starting: 'Starting Vite dev server…',
  running: 'Running',
  error: 'Failed to start',
}

export function PreviewPanel() {
  const { deviceMode } = useUIStore()
  const activeProject = useProjectStore((s) => s.activeProject)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [status, setStatus] = useState<PreviewStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const timerRef = useRef<ReturnType<typeof setInterval>>()
  const width = getDeviceWidth(deviceMode)

  useEffect(() => {
    setPreviewUrl(null)
    setStatus('idle')
    setError(null)
    clearInterval(timerRef.current)
    setElapsed(0)
  }, [activeProject?.id])

  const startTimer = () => {
    setElapsed(0)
    clearInterval(timerRef.current)
    timerRef.current = setInterval(() => setElapsed((n) => n + 1), 1000)
  }

  const stopTimer = () => clearInterval(timerRef.current)

  const startPreview = async () => {
    if (!activeProject) return
    setError(null)
    setStatus('installing')
    startTimer()

    try {
      const { url } = await api.preview.start(activeProject.id)
      setPreviewUrl(url)
      setStatus('running')
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to start preview'
      setError(msg)
      setStatus('error')
    } finally {
      stopTimer()
    }
  }

  const stopPreview = async () => {
    if (!activeProject) return
    await api.preview.stop(activeProject.id).catch(() => {})
    setPreviewUrl(null)
    setStatus('idle')
    stopTimer()
    setElapsed(0)
  }

  const reload = () => {
    if (iframeRef.current) {
      iframeRef.current.src = iframeRef.current.src
    }
  }

  const isLoading = status === 'installing' || status === 'starting'

  return (
    <div className="flex flex-col h-full border-l border-border-subtle bg-surface-0">
      {/* Toolbar */}
      <div className="flex-shrink-0 flex items-center gap-2 px-3 py-2 border-b border-border-subtle bg-surface-1">
        <Globe className="h-3.5 w-3.5 text-text-muted flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 rounded-lg bg-surface-3 border border-border-subtle px-2.5 py-1">
            <span className={clsx('h-1.5 w-1.5 rounded-full flex-shrink-0', {
              'bg-text-muted': status === 'idle',
              'bg-amber-400 animate-pulse': isLoading,
              'bg-emerald-400': status === 'running',
              'bg-red-400': status === 'error',
            })} />
            <span className="text-xs font-mono truncate text-text-secondary">
              {status === 'running' && previewUrl ? previewUrl : STATUS_MESSAGES[status]}
            </span>
            {isLoading && elapsed > 0 && (
              <span className="text-[10px] text-text-muted flex-shrink-0">{elapsed}s</span>
            )}
          </div>
        </div>

        <DeviceSelector />

        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={reload}
          disabled={status !== 'running'} title="Reload">
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>

        {previewUrl && (
          <Button variant="ghost" size="icon" className="h-7 w-7"
            onClick={() => window.open(previewUrl, '_blank')} title="Open in browser">
            <ExternalLink className="h-3.5 w-3.5" />
          </Button>
        )}

        {status === 'running' ? (
          <Button variant="ghost" size="icon" className="h-7 w-7 text-red-400"
            onClick={stopPreview} title="Stop server">
            <Square className="h-3.5 w-3.5" />
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1.5 text-emerald-400 hover:text-emerald-300"
            onClick={startPreview}
            loading={isLoading}
            disabled={!activeProject || isLoading}
          >
            {!isLoading && <Play className="h-3.5 w-3.5" />}
            Run
          </Button>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 relative overflow-hidden bg-surface-0">
        {!activeProject ? (
          <EmptyState icon={Globe} message="Select or create a project to see a live preview." />
        ) : isLoading ? (
          <LoadingState status={status} elapsed={elapsed} />
        ) : status === 'error' ? (
          <ErrorState error={error!} onRetry={startPreview} />
        ) : status === 'running' && previewUrl ? (
          <div className="flex justify-center h-full bg-neutral-800 transition-all">
            <motion.div
              animate={{ width }}
              transition={{ type: 'spring', stiffness: 300, damping: 35 }}
              className="h-full bg-white shadow-2xl overflow-hidden relative"
              style={{ width }}
            >
              <iframe
                ref={iframeRef}
                src={previewUrl}
                className="h-full w-full border-0"
                title="Live Preview"
                allow="*"
              />
            </motion.div>
          </div>
        ) : (
          <LaunchState onStart={startPreview} disabled={!activeProject} />
        )}
      </div>
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function EmptyState({ icon: Icon, message }: { icon: React.ElementType; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-6">
      <Icon className="h-12 w-12 text-text-muted opacity-20" />
      <p className="text-sm text-text-muted">{message}</p>
    </div>
  )
}

function LoadingState({ status, elapsed }: { status: PreviewStatus; elapsed: number }) {
  const steps = [
    { key: 'installing', label: 'Installing npm dependencies', done: false },
    { key: 'starting', label: 'Starting Vite dev server', done: false },
  ]
  const currentIdx = steps.findIndex((s) => s.key === status)

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 px-6">
      <Loader2 className="h-10 w-10 text-accent animate-spin" />
      <div className="w-full max-w-xs space-y-3">
        {steps.map((step, i) => (
          <div key={step.key} className="flex items-center gap-3">
            <div className={clsx('h-5 w-5 rounded-full flex items-center justify-center text-xs flex-shrink-0', {
              'bg-accent/20 border border-accent text-accent animate-pulse-soft': i === currentIdx,
              'bg-emerald-500/20 border border-emerald-500 text-emerald-400': i < currentIdx,
              'bg-surface-4 border border-border-default text-text-muted': i > currentIdx,
            })}>
              {i < currentIdx ? '✓' : i + 1}
            </div>
            <span className={clsx('text-sm', {
              'text-text-primary': i === currentIdx,
              'text-emerald-400': i < currentIdx,
              'text-text-muted': i > currentIdx,
            })}>
              {step.label}
            </span>
          </div>
        ))}
      </div>
      <p className="text-xs text-text-muted">
        {elapsed > 0 ? `${elapsed}s elapsed` : 'Starting…'}
        {status === 'installing' && elapsed > 30 ? ' — downloading packages…' : ''}
      </p>
    </div>
  )
}

function ErrorState({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 px-6 text-center">
      <AlertCircle className="h-10 w-10 text-red-400 opacity-80" />
      <div className="rounded-xl border border-red-500/20 bg-red-500/8 p-4 max-w-sm w-full text-left">
        <p className="text-sm text-red-400 font-medium mb-2">Preview failed to start</p>
        <pre className="text-[11px] text-red-400/70 whitespace-pre-wrap break-all font-mono max-h-32 overflow-y-auto">
          {error}
        </pre>
      </div>
      <Button variant="outline" size="sm" onClick={onRetry}>Retry</Button>
    </div>
  )
}

function LaunchState({ onStart, disabled }: { onStart: () => void; disabled: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-center px-6">
      <div className="h-16 w-16 rounded-2xl bg-surface-3 border border-border-subtle flex items-center justify-center">
        <Play className="h-7 w-7 text-emerald-400" />
      </div>
      <div>
        <p className="text-sm font-medium text-text-primary mb-1">Launch Preview</p>
        <p className="text-xs text-text-muted max-w-xs leading-relaxed">
          Starts the Vite dev server for your generated project. First run installs npm packages (~1 min).
        </p>
      </div>
      <Button variant="primary" size="md" onClick={onStart} disabled={disabled}>
        <Play className="h-4 w-4" /> Start Dev Server
      </Button>
    </div>
  )
}
