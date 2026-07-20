import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

describe('api request wrapper', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('resolves with the parsed JSON body on a successful response', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse({ projects: [] }))

    const result = await api.projects.list()

    expect(result).toEqual({ projects: [] })
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/projects',
      expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) })
    )
  })

  it('throws using the backend-provided detail message on a non-OK response', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      jsonResponse({ detail: 'Project not found' }, { status: 404 })
    )

    await expect(api.projects.get('missing-id')).rejects.toThrow('Project not found')
  })

  it('falls back to the HTTP status text when the error body is not JSON', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(
      new Response('not json', { status: 500, statusText: 'Internal Server Error' })
    )

    await expect(api.projects.get('x')).rejects.toThrow('Internal Server Error')
  })

  it('sends the request body as JSON for POST calls', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(jsonResponse({ messageId: 'm1' }))

    await api.chat.send('proj-1', 'hello')

    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0]
    expect(init?.method).toBe('POST')
    expect(JSON.parse(init?.body as string)).toEqual({ projectId: 'proj-1', message: 'hello' })
  })

  it('aborts the request once the default timeout elapses', async () => {
    vi.useFakeTimers()
    vi.mocked(globalThis.fetch).mockImplementation((_url: RequestInfo | URL, init?: RequestInit) => {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          const err = new Error('The operation was aborted')
          err.name = 'AbortError'
          reject(err)
        })
      })
    })

    const pending = api.projects.list()
    const assertion = expect(pending).rejects.toThrow('The operation was aborted')

    await vi.advanceTimersByTimeAsync(30000)
    await assertion

    vi.useRealTimers()
  })
})
