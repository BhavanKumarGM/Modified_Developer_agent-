// ─── Project ──────────────────────────────────────────────────────────────────

export interface Project {
  id: string
  name: string
  description?: string
  framework: Framework
  status: ProjectStatus
  createdAt: string
  updatedAt: string
  rootPath?: string
  previewPort?: number
  metadata?: ProjectMetadata
}

export type Framework = 'react' | 'nextjs' | 'vue' | 'angular' | 'static' | 'unknown'
export type ProjectStatus = 'idle' | 'generating' | 'running' | 'error' | 'ready'

// Field names match the raw JSON produced by MemoryAgent / RepositoryAgent
// on the backend (backend/app/agents/memory_agent.py,
// backend/app/agents/repository_agent.py) — snake_case, unconverted.
export interface ProjectMetadata {
  theme?: string
  primary_color?: string
  styling?: string[]
  architecture?: string
  naming_convention?: string
  folder_structure?: string
  preferred_libraries?: string[]
  component_style?: string
  has_typescript?: boolean
  has_tests?: boolean
}

// ─── Messages ─────────────────────────────────────────────────────────────────

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'agent'
  content: string
  timestamp: string
  agentName?: string
  agentStatus?: AgentStatus
  fileRefs?: FileReference[]
  codeBlocks?: CodeBlock[]
  diff?: FileDiff[]
  isStreaming?: boolean
  error?: string
}

export interface FileReference {
  path: string
  language?: string
  startLine?: number
  endLine?: number
}

export interface CodeBlock {
  language: string
  code: string
  filename?: string
}

export interface FileDiff {
  path: string
  before: string
  after: string
  additions: number
  deletions: number
}

// ─── Agents ───────────────────────────────────────────────────────────────────

export type AgentName =
  | 'conversation'
  | 'planner'
  | 'repository'
  | 'search'
  | 'memory'
  | 'design'
  | 'codegen'
  | 'editing'
  | 'refactoring'
  | 'review'
  | 'validation'
  | 'debug'
  | 'git'
  | 'preview'

export type AgentStatus = 'idle' | 'thinking' | 'working' | 'done' | 'error'

export interface AgentState {
  name: AgentName
  label: string
  status: AgentStatus
  task?: string
  progress?: number
}

// ─── Files ────────────────────────────────────────────────────────────────────

export interface FileNode {
  id: string
  name: string
  path: string
  type: 'file' | 'directory'
  language?: string
  size?: number
  children?: FileNode[]
  isExpanded?: boolean
}

export interface FileContent {
  path: string
  content: string
  language: string
  isDirty?: boolean
}

// ─── Git ──────────────────────────────────────────────────────────────────────

export interface GitSnapshot {
  id: string
  message: string
  timestamp: string
  filesChanged: number
  additions: number
  deletions: number
}

// ─── Preview ──────────────────────────────────────────────────────────────────

export type DeviceMode = 'desktop' | 'tablet' | 'mobile'

export interface PreviewState {
  url?: string
  port?: number
  device: DeviceMode
  isLoading: boolean
  error?: string
}

// ─── WebSocket Events ─────────────────────────────────────────────────────────

export type WSEventType =
  | 'stream_token'
  | 'stream_done'
  | 'stream_cancelled'
  | 'agent_status'
  | 'file_created'
  | 'file_modified'
  | 'file_deleted'
  | 'preview_ready'
  | 'build_log'
  | 'error'

export interface WSEvent {
  type: WSEventType
  payload: unknown
}

export interface StreamTokenEvent {
  token: string
  messageId: string
}

export interface AgentStatusEvent {
  agent: AgentName
  status: AgentStatus
  task?: string
}

export interface FileEvent {
  path: string
  content?: string
}

export interface PreviewReadyEvent {
  port: number
  url: string
}
