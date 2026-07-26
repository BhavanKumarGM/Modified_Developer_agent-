const BASE = '/api'

async function request<T>(path: string, init?: RequestInit & { timeout?: number }): Promise<T> {
  const { timeout, ...fetchInit } = init ?? {}
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout ?? 30000)
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...fetchInit?.headers },
    signal: controller.signal,
    ...fetchInit,
  }).finally(() => clearTimeout(timer))
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Request failed')
  }
  return res.json()
}

// ─── Projects ─────────────────────────────────────────────────────────────────

export const api = {
  projects: {
    list: () => request<{ projects: import('@/types').Project[] }>('/projects'),
    get: (id: string) => request<import('@/types').Project>(`/projects/${id}`),
    create: (data: { name: string; description?: string }) =>
      request<import('@/types').Project>('/projects', { method: 'POST', body: JSON.stringify(data) }),
    delete: (id: string) => request<void>(`/projects/${id}`, { method: 'DELETE' }),
    memory: (id: string) => request<{ memory: Record<string, unknown> }>(`/projects/${id}/memory`),
  },

  chat: {
    send: (projectId: string, message: string) =>
      request<{ messageId: string }>('/chat/send', {
        method: 'POST',
        body: JSON.stringify({ projectId, message }),
      }),
    history: (projectId: string) =>
      request<{ messages: import('@/types').Message[] }>(`/chat/history/${projectId}`),
  },

  files: {
    tree: (projectId: string) =>
      request<{ tree: import('@/types').FileNode[] }>(`/files/tree/${projectId}`),
    read: (projectId: string, path: string) =>
      request<{ content: string; language: string }>(`/files/read`, {
        method: 'POST',
        body: JSON.stringify({ projectId, path }),
      }),
    write: (projectId: string, path: string, content: string) =>
      request<void>('/files/write', {
        method: 'POST',
        body: JSON.stringify({ projectId, path, content }),
      }),
    delete: (projectId: string, path: string) =>
      request<void>('/files/delete', {
        method: 'POST',
        body: JSON.stringify({ projectId, path }),
      }),
  },

  upload: {
    zip: async (file: File, onProgress?: (pct: number) => void) => {
      const form = new FormData()
      form.append('file', file)
      const xhr = new XMLHttpRequest()
      return new Promise<import('@/types').Project>((resolve, reject) => {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100))
        }
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(JSON.parse(xhr.responseText))
          } else {
            reject(new Error(xhr.responseText))
          }
        }
        xhr.onerror = () => reject(new Error('Upload failed'))
        xhr.open('POST', `${BASE}/upload/zip`)
        xhr.send(form)
      })
    },
  },

  preview: {
    start: (projectId: string) =>
      request<{
        port: number
        url: string
        backendPort: number | null
        backendUrl: string | null
        backendFramework: string | null
      }>(`/preview/start/${projectId}`, { method: 'POST', timeout: 240000 }),
    stop: (projectId: string) =>
      request<void>(`/preview/stop/${projectId}`, { method: 'POST' }),
  },

  git: {
    history: (projectId: string) =>
      request<{ snapshots: import('@/types').GitSnapshot[] }>(`/git/history/${projectId}`),
    restore: (projectId: string, snapshotId: string) =>
      request<void>('/git/restore', {
        method: 'POST',
        body: JSON.stringify({ projectId, snapshotId }),
      }),
  },

  ollama: {
    status: () => request<{ connected: boolean; models: string[] }>('/ollama/status'),
  },
}
