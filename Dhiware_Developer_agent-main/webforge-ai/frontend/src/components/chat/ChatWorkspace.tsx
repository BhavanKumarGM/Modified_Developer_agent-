import { useEffect, useRef, useCallback, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'
import { WelcomeScreen } from './WelcomeScreen'
import { useChatStore } from '@/stores/chatStore'
import { useProjectStore } from '@/stores/projectStore'
import { useWebSocket } from '@/hooks/useWebSocket'
import { api } from '@/services/api'
import { socket } from '@/services/websocket'
import type { Message } from '@/types'

function generateId() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

export function ChatWorkspace() {
  const { messages, addMessage, isStreaming } = useChatStore()
  const activeProject = useProjectStore((s) => s.activeProject)
  const scrollRef = useRef<HTMLDivElement>(null)
  const [abortController, setAbortController] = useState<AbortController | null>(null)

  useWebSocket(activeProject?.id ?? null)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [messages])

  useEffect(() => {
    if (!activeProject) return
    api.chat.history(activeProject.id)
      .then((r) => {
        const store = useChatStore.getState()
        store.clearMessages()
        r.messages.forEach((m) => store.addMessage(m))
      })
      .catch(() => {})
  }, [activeProject?.id])

  const handleSend = useCallback(async (text: string) => {
    if (!activeProject) return

    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }
    addMessage(userMsg)

    const assistantId = generateId()
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      isStreaming: true,
    }
    addMessage(assistantMsg)

    socket.connect(activeProject.id)

    try {
      const { messageId } = await api.chat.send(activeProject.id, text)
      useChatStore.getState().replaceMessageId(assistantId, messageId)
    } catch (err) {
      useChatStore.getState().finalizeStream(assistantId)
      const errMsg: Message = {
        id: generateId(),
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
        timestamp: new Date().toISOString(),
        error: String(err),
      }
      addMessage(errMsg)
    }
  }, [activeProject, addMessage])

  const handleStop = useCallback(() => {
    abortController?.abort()
    const { streamingMessageId, finalizeStream } = useChatStore.getState()
    if (streamingMessageId) finalizeStream(streamingMessageId)
  }, [abortController])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-4 py-2.5 border-b border-border-subtle">
        <div className="flex items-center gap-2">
          {activeProject ? (
            <>
              <div className="h-2 w-2 rounded-full bg-emerald-400" />
              <span className="text-sm font-medium text-text-primary">{activeProject.name}</span>
              <span className="text-xs text-text-muted">{activeProject.framework}</span>
            </>
          ) : (
            <span className="text-sm text-text-muted">No project selected</span>
          )}
        </div>
        {isStreaming && (
          <div className="flex items-center gap-1.5 text-xs text-accent">
            <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
            Generating…
          </div>
        )}
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0"
      >
        {messages.length === 0 ? (
          <WelcomeScreen onSuggestion={handleSend} />
        ) : (
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
          </AnimatePresence>
        )}
      </div>

      {/* Input */}
      <ChatInput
        onSend={handleSend}
        onStop={handleStop}
        disabled={!activeProject}
      />
    </div>
  )
}
