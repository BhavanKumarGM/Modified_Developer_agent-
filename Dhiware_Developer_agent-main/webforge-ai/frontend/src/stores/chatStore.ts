import { create } from 'zustand'
import type { Message, AgentState, AgentName, AgentStatus } from '@/types'

interface ChatStore {
  messages: Message[]
  isStreaming: boolean
  streamingContent: string
  streamingMessageId: string | null
  agents: AgentState[]

  addMessage: (msg: Message) => void
  appendToken: (token: string, messageId: string) => void
  finalizeStream: (messageId: string) => void
  replaceMessageId: (oldId: string, newId: string) => void
  clearMessages: () => void
  setAgentStatus: (name: AgentName, status: AgentStatus, task?: string) => void
  resetAgents: () => void
}

const defaultAgents: AgentState[] = [
  { name: 'conversation', label: 'Conversation', status: 'idle' },
  { name: 'planner', label: 'Planner', status: 'idle' },
  { name: 'repository', label: 'Repository', status: 'idle' },
  { name: 'search', label: 'Search', status: 'idle' },
  { name: 'memory', label: 'Memory', status: 'idle' },
  { name: 'design', label: 'Design', status: 'idle' },
  { name: 'codegen', label: 'Code Gen', status: 'idle' },
  { name: 'editing', label: 'Editing', status: 'idle' },
  { name: 'refactoring', label: 'Refactoring', status: 'idle' },
  { name: 'review', label: 'Review', status: 'idle' },
  { name: 'validation', label: 'Validation', status: 'idle' },
  { name: 'debug', label: 'Debug', status: 'idle' },
  { name: 'git', label: 'Git', status: 'idle' },
  { name: 'preview', label: 'Preview', status: 'idle' },
]

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  isStreaming: false,
  streamingContent: '',
  streamingMessageId: null,
  agents: defaultAgents,

  addMessage: (msg) =>
    set((s) => ({
      messages: [...s.messages, msg],
      isStreaming: msg.isStreaming ?? false,
      streamingContent: msg.isStreaming ? '' : s.streamingContent,
      streamingMessageId: msg.isStreaming ? msg.id : s.streamingMessageId,
    })),

  appendToken: (token, messageId) =>
    set((s) => {
      const newContent = s.streamingContent + token
      return {
        streamingContent: newContent,
        messages: s.messages.map((m) =>
          m.id === messageId ? { ...m, content: newContent } : m
        ),
      }
    }),

  finalizeStream: (messageId) =>
    set((s) => ({
      isStreaming: false,
      streamingContent: '',
      streamingMessageId: null,
      messages: s.messages.map((m) =>
        m.id === messageId ? { ...m, isStreaming: false } : m
      ),
    })),

  replaceMessageId: (oldId, newId) =>
    set((s) => ({
      streamingMessageId: s.streamingMessageId === oldId ? newId : s.streamingMessageId,
      messages: s.messages.map((m) => (m.id === oldId ? { ...m, id: newId } : m)),
    })),

  clearMessages: () =>
    set({ messages: [], isStreaming: false, streamingContent: '', streamingMessageId: null }),

  setAgentStatus: (name, status, task) =>
    set((s) => ({
      agents: s.agents.map((a) => (a.name === name ? { ...a, status, task } : a)),
    })),

  resetAgents: () => set({ agents: defaultAgents }),
}))
