import { useState, useEffect } from 'react'
import { CheckCircle2, XCircle, Loader2, ExternalLink } from 'lucide-react'
import { api } from '@/services/api'
import { Badge } from '@/components/ui/Badge'

interface OllamaStatus {
  connected: boolean
  models: string[]
  default_model_available: boolean
  embedding_model_available: boolean
}

const DEFAULT_MODEL = 'qwen2.5-coder:7b'
const EMBEDDING_MODEL = 'nomic-embed-text'

export function SettingsPanel() {
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.ollama.status()
      .then(setOllamaStatus)
      .catch(() =>
        setOllamaStatus({
          connected: false,
          models: [],
          default_model_available: false,
          embedding_model_available: false,
        })
      )
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="p-3 space-y-4">
      <div className="rounded-xl border border-border-subtle bg-surface-3 p-3 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-text-secondary">Ollama Connection</span>
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 text-text-muted animate-spin" />
          ) : ollamaStatus?.connected ? (
            <div className="flex items-center gap-1 text-emerald-400 text-xs">
              <CheckCircle2 className="h-3.5 w-3.5" /> Connected
            </div>
          ) : (
            <div className="flex items-center gap-1 text-red-400 text-xs">
              <XCircle className="h-3.5 w-3.5" /> Offline
            </div>
          )}
        </div>
        <div>
          <p className="text-[10px] text-text-muted mb-1">Endpoint</p>
          <code className="text-xs text-accent font-mono">http://localhost:11434</code>
        </div>
        {ollamaStatus?.models && ollamaStatus.models.length > 0 && (
          <div>
            <p className="text-[10px] text-text-muted mb-1.5">Available Models</p>
            <div className="flex flex-wrap gap-1">
              {ollamaStatus.models.map((m) => (
                <Badge key={m} variant={m.startsWith('qwen') ? 'accent' : 'default'}>
                  {m}
                </Badge>
              ))}
            </div>
          </div>
        )}
        {!loading && !ollamaStatus?.connected && (
          <div className="rounded-lg bg-red-500/8 border border-red-500/15 p-2">
            <p className="text-[11px] text-red-400">
              Ollama is not running. Start it with{' '}
              <code className="font-mono bg-red-500/10 px-1 rounded">ollama serve</code>
            </p>
          </div>
        )}
        {!loading && ollamaStatus?.connected && !ollamaStatus.default_model_available && (
          <div className="rounded-lg bg-amber-500/8 border border-amber-500/15 p-2">
            <p className="text-[11px] text-amber-400">
              {DEFAULT_MODEL} isn't pulled — code generation will fail. Run{' '}
              <code className="font-mono bg-amber-500/10 px-1 rounded">ollama pull {DEFAULT_MODEL}</code>
            </p>
          </div>
        )}
        {!loading && ollamaStatus?.connected && !ollamaStatus.embedding_model_available && (
          <div className="rounded-lg bg-amber-500/8 border border-amber-500/15 p-2">
            <p className="text-[11px] text-amber-400">
              {EMBEDDING_MODEL} isn't pulled — semantic search will fall back to keyword-only. Run{' '}
              <code className="font-mono bg-amber-500/10 px-1 rounded">ollama pull {EMBEDDING_MODEL}</code>
            </p>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-border-subtle bg-surface-3 p-3 space-y-2">
        <span className="text-xs font-semibold text-text-secondary">Default Model</span>
        <div className="flex items-center gap-2">
          <Badge variant={ollamaStatus?.default_model_available ? 'accent' : 'default'} dot>
            {DEFAULT_MODEL}
          </Badge>
        </div>
        <p className="text-[11px] text-text-muted">
          All AI capabilities route through Ollama via the LLM abstraction layer.
        </p>
      </div>

      <div className="rounded-xl border border-border-subtle bg-surface-3 p-3">
        <span className="text-xs font-semibold text-text-secondary block mb-2">About</span>
        <p className="text-[11px] text-text-muted leading-relaxed">
          WebForge AI — Local-first AI Website Development Platform.
          100% private. All inference runs on your machine via Ollama.
        </p>
        <p className="text-[11px] text-text-muted mt-2">Version 1.0.0</p>
      </div>
    </div>
  )
}
