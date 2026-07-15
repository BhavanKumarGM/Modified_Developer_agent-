import { useState, useRef, useCallback, useEffect } from 'react'
import { Send, Paperclip, Square, Loader2 } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { useChatStore } from '@/stores/chatStore'

interface ChatInputProps {
  onSend: (message: string) => void
  onStop?: () => void
  disabled?: boolean
  placeholder?: string
}

export function ChatInput({ onSend, onStop, disabled, placeholder }: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const isStreaming = useChatStore((s) => s.isStreaming)

  const autoResize = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }

  useEffect(autoResize, [value])

  const submit = useCallback(() => {
    if (!value.trim() || disabled || isStreaming) return
    onSend(value.trim())
    setValue('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }, [value, disabled, isStreaming, onSend])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const charCount = value.length
  const isNearLimit = charCount > 3000

  return (
    <div className="px-4 py-3 border-t border-border-subtle bg-surface-1">
      <div className={clsx(
        'flex flex-col gap-2 rounded-2xl border transition-colors bg-surface-3',
        'focus-within:border-accent/40 border-border-default'
      )}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder ?? 'Describe what you want to build or change…'}
          disabled={disabled || isStreaming}
          rows={1}
          className="flex-1 resize-none bg-transparent px-4 pt-3.5 pb-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none min-h-[44px] max-h-[200px] disabled:opacity-60"
          style={{ height: 'auto' }}
        />

        <div className="flex items-center justify-between px-3 pb-2.5">
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="h-7 w-7" title="Attach file">
              <Paperclip className="h-3.5 w-3.5" />
            </Button>
            {isNearLimit && (
              <span className="text-[10px] text-amber-400">{charCount}/4000</span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] text-text-muted hidden sm:block">
              {isStreaming ? 'Generating…' : 'Enter to send · Shift+Enter for new line'}
            </span>
            {isStreaming ? (
              <Button
                variant="danger"
                size="sm"
                onClick={onStop}
                className="h-8 px-3 gap-1.5"
              >
                <Square className="h-3 w-3 fill-current" /> Stop
              </Button>
            ) : (
              <Button
                variant="primary"
                size="sm"
                onClick={submit}
                disabled={!value.trim() || disabled}
                className="h-8 px-3 gap-1.5"
              >
                <Send className="h-3.5 w-3.5" /> Send
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
