import { useEffect } from 'react'
import { socket } from '@/services/websocket'
import { useChatStore } from '@/stores/chatStore'
import { useProjectStore } from '@/stores/projectStore'
import { useUIStore } from '@/stores/uiStore'
import { api } from '@/services/api'
import type { AgentStatusEvent, StreamTokenEvent, FileEvent, PreviewReadyEvent, FileNode } from '@/types'

function flattenTree(nodes: FileNode[]): FileNode[] {
  const result: FileNode[] = []
  for (const n of nodes) {
    if (n.type === 'file') result.push(n)
    if (n.children) result.push(...flattenTree(n.children))
  }
  return result
}

function pickMainFile(nodes: FileNode[]): string | null {
  const files = flattenTree(nodes)
  const priority = ['src/App.tsx', 'src/App.jsx', 'src/app.tsx', 'App.tsx', 'index.tsx']
  for (const p of priority) {
    if (files.find((f) => f.path === p)) return p
  }
  const tsx = files.find((f) => f.path.endsWith('.tsx') || f.path.endsWith('.jsx'))
  return tsx?.path ?? files[0]?.path ?? null
}

export function useWebSocket(projectId: string | null) {
  const appendToken = useChatStore((s) => s.appendToken)
  const finalizeStream = useChatStore((s) => s.finalizeStream)
  const setAgentStatus = useChatStore((s) => s.setAgentStatus)
  const { setFileTree, openFile, activeProject } = useProjectStore()
  const { setSidebarPanel, isSidebarCollapsed, toggleSidebar } = useUIStore()

  useEffect(() => {
    if (!projectId) return
    socket.connect(projectId)

    const offs = [
      socket.on<StreamTokenEvent>('stream_token', ({ token, messageId }) => {
        appendToken(token, messageId)
      }),

      socket.on<{ messageId: string }>('stream_done', ({ messageId }) => {
        finalizeStream(messageId)
        if (activeProject?.id !== projectId) return

        api.files.tree(projectId)
          .then(async (r) => {
            setFileTree(r.tree)

            // Switch sidebar to Files so user can see the tree
            setSidebarPanel('files')
            if (isSidebarCollapsed) toggleSidebar()

            // Auto-open the main app file
            const mainPath = pickMainFile(r.tree)
            if (!mainPath) return

            // Don't re-open if already in openFiles
            const alreadyOpen = useProjectStore.getState().openFiles.find((f) => f.path === mainPath)
            if (alreadyOpen) return

            try {
              const { content, language } = await api.files.read(projectId, mainPath)
              openFile({ path: mainPath, content, language })
            } catch {
              openFile({ path: mainPath, content: '', language: 'typescript' })
            }
          })
          .catch(() => {})
      }),

      socket.on<AgentStatusEvent>('agent_status', ({ agent, status, task }) => {
        setAgentStatus(agent, status, task)
      }),

      socket.on<FileEvent>('file_created', () => {
        if (activeProject?.id !== projectId) return
        api.files.tree(projectId)
          .then((r) => setFileTree(r.tree))
          .catch(() => {})
      }),

      socket.on<FileEvent>('file_modified', ({ path }) => {
        if (activeProject?.id !== projectId) return
        api.files.tree(projectId)
          .then((r) => setFileTree(r.tree))
          .catch(() => {})
        // Refresh content of open file if it was modified
        if (!path) return
        const openEntry = useProjectStore.getState().openFiles.find((f) => f.path === path)
        if (openEntry) {
          api.files.read(projectId, path)
            .then(({ content }) => useProjectStore.getState().updateFileContent(path, content))
            .catch(() => {})
        }
      }),

      socket.on<FileEvent>('file_deleted', ({ path }) => {
        if (activeProject?.id !== projectId) return
        api.files.tree(projectId)
          .then((r) => setFileTree(r.tree))
          .catch(() => {})
        if (path) useProjectStore.getState().closeFile(path)
      }),

      socket.on<{ messageId: string }>('stream_cancelled', ({ messageId }) => {
        // Cancellation still ends the stream from the UI's point of view —
        // reuse the same "stop showing a live cursor" transition as a
        // normal completion so the message doesn't look stuck forever.
        finalizeStream(messageId)
      }),

      socket.on<PreviewReadyEvent>('preview_ready', () => {}),
    ]

    return () => offs.forEach((off) => off())
  }, [projectId, appendToken, finalizeStream, setAgentStatus, setFileTree, openFile, activeProject?.id, setSidebarPanel, isSidebarCollapsed, toggleSidebar])
}
