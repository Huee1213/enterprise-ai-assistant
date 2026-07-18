export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  sources?: Source[]
  steps?: AgentStep[]
  reasoning?: string
  backendId?: number
}

export interface Source {
  source: string
  content: string
}

export interface AgentStep {
  step: number
  action: string
  input: string
  output: string
  duration_ms: number
}

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  createdAt: Date
  updatedAt: Date
}

export interface ChatRequest {
  message: string
  conversation_id?: string
  use_agent: boolean
}

export interface ChatResponse {
  conversation_id: string
  answer: string
  sources: Source[]
}

export interface DocumentInfo {
  id: string
  filename: string
  size: number
  content_type: string
  uploaded_at: string
  chunk_count: number
}

export interface UploadResponse {
  id: string
  filename: string
  status: string
  message: string
}

export interface HealthStatus {
  status: string
  version: string
  milvus_connected: boolean
  llm_configured: boolean
}

export type SSEEvent = {
  event: 'token' | 'sources' | 'steps' | 'step' | 'reasoning' | 'done' | 'error'
  data: any
}
