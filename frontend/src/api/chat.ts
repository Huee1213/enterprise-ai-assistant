import apiClient from './client'
import { dispatchStaleSession } from './client'
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
        const detail = errorData.detail || `HTTP ${response.status}`
        if (response.status === 401 && typeof detail === 'string' && detail.includes('已在其他地方登录') && token) {
          dispatchStaleSession()
        }
        throw new Error(detail)
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

export async function fetchConversationMessages(convId: string): Promise<{ id: number; role: string; content: string; metadata?: string; timestamp: string }[]> {
  const { data } = await apiClient.get(`/chat/conversations/${convId}`)
  return data.messages || []
}

export async function deleteConversation(convId: string): Promise<void> {
  await apiClient.delete(`/chat/conversations/${convId}`)
}

export async function saveConversationTitle(convId: string, title: string): Promise<void> {
  await apiClient.put(`/chat/conversations/${convId}/title`, { title })
}

export async function regenerateConversationTitle(convId: string): Promise<string> {
  const { data } = await apiClient.post(`/chat/conversations/${convId}/regenerate-title`)
  return data.title
}

export async function clearConversationMessages(convId: string): Promise<void> {
  await apiClient.delete(`/chat/conversations/${convId}/messages`)
}

export async function deleteMessagesFrom(convId: string, msgDbId: number): Promise<void> {
  await apiClient.delete(`/chat/conversations/${convId}/messages/from/${msgDbId}`)
}

export async function bulkDeleteConversations(convIds: string[]): Promise<void> {
  await apiClient.post('/chat/conversations/bulk-delete', { conversation_ids: convIds })
}

export async function deleteMessage(convId: string, msgDbId: number): Promise<void> {
  await apiClient.delete(`/chat/conversations/${convId}/messages/${msgDbId}`)
}

export async function bulkDeleteMessages(convId: string, msgDbIds: number[]): Promise<void> {
  await apiClient.post(`/chat/conversations/${convId}/messages/bulk-delete`, { message_ids: msgDbIds })
}

export async function searchMessages(convId: string, q: string): Promise<{ id: number; role: string; timestamp: string; snippet: string }[]> {
  const { data } = await apiClient.get(`/chat/conversations/${convId}/search`, { params: { q } })
  return data.matches || []
}

