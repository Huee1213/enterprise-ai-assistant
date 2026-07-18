import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Message, Conversation, SSEEvent, AgentStep } from '@/types'
import { createChatStream, generateTitle, fetchConversations, fetchConversationMessages, deleteConversation as apiDeleteConv, saveConversationTitle, clearConversationMessages } from '@/api/chat'

let msgCounter = 0
function generateId(): string {
  return `msg_${Date.now()}_${++msgCounter}`
}

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<Conversation[]>([])
  const activeConversationId = ref<string | null>(null)
  const isStreaming = ref(false)
  const useAgentMode = ref(true)
  const currentAbortController = ref<AbortController | null>(null)
  const loadingHistory = ref(false)
  let loadingLock = false

  const activeConversation = computed(() => {
    return conversations.value.find((c) => c.id === activeConversationId.value) || null
  })

  const messages = computed(() => {
    return activeConversation.value?.messages || []
  })

  function createConversation(addToSidebar: boolean = true): string {
    const id = `conv_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
    if (addToSidebar) {
      conversations.value.unshift({
        id, title: '新对话', messages: [],
        createdAt: new Date(), updatedAt: new Date(),
      })
    }
    activeConversationId.value = id
    return id
  }

  function _mergeServerConvs(serverConvs: { conversation_id: string; title: string; latest: string }[]) {
    for (const sc of serverConvs) {
      const existing = conversations.value.find(c => c.id === sc.conversation_id)
      if (existing) {
        existing.updatedAt = new Date(sc.latest)
        if (sc.title && sc.title !== '新对话') existing.title = sc.title
      } else {
        conversations.value.push({
          id: sc.conversation_id, title: sc.title || '新对话', messages: [],
          createdAt: new Date(sc.latest), updatedAt: new Date(sc.latest),
        })
      }
    }
  }

  async function loadConversations() {
    if (loadingLock) return
    loadingLock = true
    try {
      const convs = await fetchConversations()
      // Merge server conversations without clearing local state
      _mergeServerConvs(convs)
      conversations.value.sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
    } catch { /* ignore */ }
    loadingLock = false
  }

  function resetConversations() {
    conversations.value.splice(0)
    activeConversationId.value = null
  }

  async function selectConversation(id: string) {
    const conv = conversations.value.find(c => c.id === id)
    if (!conv || conv.messages.length > 0) { activeConversationId.value = id; return }
    loadingHistory.value = true
    try {
      const msgs = await fetchConversationMessages(id)
      if (msgs.length > 0) {
        conv.messages = msgs.map(m => {
          const msg: Message = {
            id: generateId(), role: m.role as 'user' | 'assistant',
            content: m.content, timestamp: new Date(m.timestamp),
          }
          if (m.metadata && m.metadata !== '{}') {
            try {
              const meta = JSON.parse(m.metadata)
              if (meta.steps) msg.steps = meta.steps
              if (meta.reasoning) msg.reasoning = meta.reasoning
            } catch { /* ignore */ }
          }
          return msg
        })
      }
    } catch { /* ignore */ }
    activeConversationId.value = id
    loadingHistory.value = false
  }

  async function deleteConversation(id: string) {
    try { await apiDeleteConv(id) } catch { /* ignore */ }
    const idx = conversations.value.findIndex(c => c.id === id)
    if (idx === -1) return
    conversations.value.splice(idx, 1)
    if (activeConversationId.value !== id) return
    activeConversationId.value = conversations.value[0]?.id || null
    if (activeConversationId.value) {
      await selectConversation(activeConversationId.value)
    }
  }

  function addMessage(msg: Omit<Message, 'id' | 'timestamp'>) {
    const conv = activeConversation.value
    if (!conv) return
    if (!conversations.value.some(c => c.id === conv.id)) {
      conversations.value.unshift(conv)
    }
    conv.messages = [...conv.messages, { ...msg, id: generateId(), timestamp: new Date() }]
    conv.updatedAt = new Date()
  }

  function updateLastAssistantMessage(updates: Partial<Message>) {
    const conv = activeConversation.value
    if (!conv) return
    const msgs = [...conv.messages]
    const lastIdx = msgs.length - 1
    if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
      msgs[lastIdx] = { ...msgs[lastIdx], ...updates }
      conv.messages = msgs
    }
  }

  function toggleAgentMode() { useAgentMode.value = !useAgentMode.value }

  function stopStreaming() {
    if (currentAbortController.value) {
      currentAbortController.value.abort()
      currentAbortController.value = null
    }
    isStreaming.value = false
  }

  async function resendEdit(msgId: string, newContent: string) {
    const conv = activeConversation.value
    if (!conv) return
    const idx = conv.messages.findIndex(m => m.id === msgId)
    if (idx === -1) return
    // Clear backend history for this conversation before resending
    try { await clearConversationMessages(conv.id) } catch { /* ignore */ }
    conv.messages.splice(idx)
    conv.updatedAt = new Date()
    sendMessage(newContent)
  }

  function sendMessage(content: string): Promise<void> {
    return new Promise((resolve) => {
      const conv = activeConversation.value
      if (!conv || isStreaming.value) { resolve(); return }

      const isFirst = conv.messages.length === 0
      addMessage({ role: 'user', content })
      addMessage({ role: 'assistant', content: '' })
      isStreaming.value = true

      let accumulatedContent = ''
      let titled = false
      const doTitle = (full: string) => {
        if (titled) return; titled = true
        generateTitle(full).then(t => {
          conv!.title = t
          saveConversationTitle(conv!.id, t).catch(() => {})
        }).catch(() => {})
      }

      currentAbortController.value = createChatStream(
        { message: content, conversation_id: conv.id, use_agent: useAgentMode.value },
        (ev) => {
          if (ev.event === 'token') {
            accumulatedContent += ev.data
            updateLastAssistantMessage({ content: accumulatedContent })
          } else if (ev.event === 'sources') {
            updateLastAssistantMessage({ sources: ev.data })
          } else if (ev.event === 'reasoning') {
            const prev = conv.messages[conv.messages.length - 1]
            updateLastAssistantMessage({ reasoning: (prev?.reasoning || '') + ev.data })
          } else if (ev.event === 'step' || ev.event === 'steps') {
            const list = Array.isArray(ev.data) ? ev.data : [ev.data]
            const existing = conv.messages[conv.messages.length - 1]?.steps || []
            updateLastAssistantMessage({ steps: [...existing, ...list].map(s => ({ ...s, duration_ms: s.duration_ms || 0 })) })
          } else if (ev.event === 'done') {
            isStreaming.value = false
            currentAbortController.value = null
            if (isFirst) doTitle(`用户说: ${content}\nAI回复: ${accumulatedContent}`)
            resolve()
          }
        },
        (err) => {
          isStreaming.value = false
          currentAbortController.value = null
          updateLastAssistantMessage({ content: `错误：${err.message}` })
          resolve()
        },
        () => {
          isStreaming.value = false
          currentAbortController.value = null
          if (isFirst) doTitle(`用户说: ${content}\nAI回复: ${accumulatedContent}`)
          resolve()
        }
      )
    })
  }

  return {
    conversations, activeConversationId, activeConversation, messages,
    isStreaming, useAgentMode, loadingHistory,
    createConversation, selectConversation, deleteConversation,
    loadConversations, resetConversations, addMessage, sendMessage, stopStreaming, resendEdit, toggleAgentMode,
  }
})
