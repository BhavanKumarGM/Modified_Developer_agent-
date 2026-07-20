import type {
  WSEvent,
  StreamTokenEvent,
  AgentStatusEvent,
  FileEvent,
  PreviewReadyEvent,
} from '@/types'

type Handler<T = unknown> = (payload: T) => void

class WebForgeSocket {
  private ws: WebSocket | null = null
  private projectId: string | null = null
  private handlers = new Map<string, Handler[]>()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectDelay = 1000

  connect(projectId: string) {
    if (this.ws?.readyState === WebSocket.OPEN && this.projectId === projectId) return
    this.disconnect()
    this.projectId = projectId
    this.ws = new WebSocket(`ws://localhost:8000/ws/${projectId}`)

    this.ws.onmessage = (e) => {
      try {
        const event: WSEvent = JSON.parse(e.data)
        this.emit(event.type, event.payload)
      } catch {
        // ignore malformed messages
      }
    }

    this.ws.onclose = () => {
      this.scheduleReconnect()
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.ws?.close()
    this.ws = null
    this.projectId = null
  }

  private scheduleReconnect() {
    if (!this.projectId) return
    this.reconnectTimer = setTimeout(() => {
      if (this.projectId) this.connect(this.projectId)
    }, this.reconnectDelay)
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, 10000)
  }

  send(data: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  /** Ask the backend to cancel the in-flight generation/edit for this
   * project (see app/main.py's websocket_endpoint "stop" handling). */
  stopGeneration() {
    this.send({ type: 'stop' })
  }

  on<T>(event: string, handler: Handler<T>) {
    const arr = this.handlers.get(event) ?? []
    arr.push(handler as Handler)
    this.handlers.set(event, arr)
    return () => this.off(event, handler as Handler)
  }

  off(event: string, handler: Handler) {
    const arr = this.handlers.get(event) ?? []
    this.handlers.set(event, arr.filter((h) => h !== handler))
  }

  private emit(event: string, payload: unknown) {
    const arr = this.handlers.get(event) ?? []
    arr.forEach((h) => h(payload))
  }
}

export const socket = new WebForgeSocket()

export type {
  StreamTokenEvent,
  AgentStatusEvent,
  FileEvent,
  PreviewReadyEvent,
}
