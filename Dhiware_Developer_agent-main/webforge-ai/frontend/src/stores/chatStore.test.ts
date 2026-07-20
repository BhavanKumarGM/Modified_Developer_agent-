import { beforeEach, describe, expect, it } from 'vitest'
import { useChatStore } from './chatStore'
import type { Message } from '@/types'

const initialState = useChatStore.getState()

beforeEach(() => {
  useChatStore.setState(initialState, true)
})

function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: 'm1',
    role: 'assistant',
    content: '',
    timestamp: new Date().toISOString(),
    isStreaming: true,
    ...overrides,
  }
}

describe('chatStore', () => {
  it('addMessage appends the message and tracks streaming state', () => {
    const msg = makeMessage()
    useChatStore.getState().addMessage(msg)

    const state = useChatStore.getState()
    expect(state.messages).toHaveLength(1)
    expect(state.messages[0]).toEqual(msg)
    expect(state.isStreaming).toBe(true)
    expect(state.streamingMessageId).toBe('m1')
  })

  it('appendToken accumulates streamingContent and updates the matching message', () => {
    useChatStore.getState().addMessage(makeMessage({ id: 'm1' }))
    useChatStore.getState().appendToken('Hel', 'm1')
    useChatStore.getState().appendToken('lo', 'm1')

    const state = useChatStore.getState()
    expect(state.streamingContent).toBe('Hello')
    expect(state.messages[0].content).toBe('Hello')
  })

  it('appendToken does not touch messages with a different id', () => {
    useChatStore.getState().addMessage(makeMessage({ id: 'm1', content: 'unchanged' }))
    useChatStore.getState().appendToken('token', 'other-id')

    expect(useChatStore.getState().messages[0].content).toBe('unchanged')
  })

  it('finalizeStream clears streaming state and marks the message not streaming', () => {
    useChatStore.getState().addMessage(makeMessage({ id: 'm1' }))
    useChatStore.getState().appendToken('hi', 'm1')

    useChatStore.getState().finalizeStream('m1')

    const state = useChatStore.getState()
    expect(state.isStreaming).toBe(false)
    expect(state.streamingContent).toBe('')
    expect(state.streamingMessageId).toBeNull()
    expect(state.messages[0].isStreaming).toBe(false)
  })

  it('replaceMessageId updates both the message id and a matching streamingMessageId', () => {
    useChatStore.getState().addMessage(makeMessage({ id: 'temp-id' }))
    useChatStore.getState().replaceMessageId('temp-id', 'real-id')

    const state = useChatStore.getState()
    expect(state.messages[0].id).toBe('real-id')
    expect(state.streamingMessageId).toBe('real-id')
  })

  it('clearMessages resets messages and streaming state', () => {
    useChatStore.getState().addMessage(makeMessage())
    useChatStore.getState().clearMessages()

    const state = useChatStore.getState()
    expect(state.messages).toEqual([])
    expect(state.isStreaming).toBe(false)
    expect(state.streamingMessageId).toBeNull()
  })

  it('setAgentStatus updates only the named agent', () => {
    useChatStore.getState().setAgentStatus('codegen', 'working', 'Generating files')

    const state = useChatStore.getState()
    const codegen = state.agents.find((a) => a.name === 'codegen')
    const planner = state.agents.find((a) => a.name === 'planner')
    expect(codegen?.status).toBe('working')
    expect(codegen?.task).toBe('Generating files')
    expect(planner?.status).toBe('idle')
  })

  it('resetAgents restores every agent to idle', () => {
    useChatStore.getState().setAgentStatus('codegen', 'working')
    useChatStore.getState().resetAgents()

    const codegen = useChatStore.getState().agents.find((a) => a.name === 'codegen')
    expect(codegen?.status).toBe('idle')
  })
})
