import apiClient from './client'
import type { ChatRequest, ChatResponse, SSEEvent } from '@/types'

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>('/chat/simple', request)
  return data
}

export function createChatStream(
  request: ChatRequest,
  onEvent: (event: SSEEvent) => void,
  onError: (error: Error) => void,
  onComplete: () => void
): AbortController {
  const controller = new AbortController()
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  fetch('/api/chat/stream', {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const parsed = JSON.parse(line.slice(6))
              onEvent({
                event: parsed.event,
                data: parsed.data,
              })
            } catch {
              // skip malformed data
            }
          }
        }
      }

      onComplete()
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError(err)
      }
    })

  return controller
}

export async function generateTitle(message: string): Promise<string> {
  const { data } = await apiClient.post<{ title: string }>('/chat/title', { message })
  return data.title
}

export async function fetchConversations(): Promise<{ conversation_id: string; title: string; latest: string }[]> {
  const { data } = await apiClient.get('/chat/conversations')
  return data.conversations || []
}

export async function fetchConversationMessages(convId: string): Promise<{ role: string; content: string; metadata?: string; timestamp: string }[]> {
  const { data } = await apiClient.get(`/chat/conversations/${convId}`)
  return data.messages || []
}

export async function deleteConversation(convId: string): Promise<void> {
  await apiClient.delete(`/chat/conversations/${convId}`)
}

export async function saveConversationTitle(convId: string, title: string): Promise<void> {
  await apiClient.put(`/chat/conversations/${convId}/title`, { title })
}

export async function clearConversationMessages(convId: string): Promise<void> {
  await apiClient.delete(`/chat/conversations/${convId}/messages`)
}

