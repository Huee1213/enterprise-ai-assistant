<script setup lang="ts">
import { ref, computed, nextTick, watch as vueWatch, onMounted, onUnmounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import ChatMessage from './ChatMessage.vue'
import ChatInput from './ChatInput.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const chat = useChatStore()
const auth = useAuthStore()
const messagesEndRef = ref<HTMLDivElement | null>(null)
const confirmRetryMsgId = ref<string | null>(null)
const confirmDeleteMsgId = ref<string | null>(null)
const confirmDeleteMsgContent = ref('')
const msgContainerRef = ref<HTMLDivElement | null>(null)
const msgRefs = ref<Map<string, HTMLElement>>(new Map())

// Message search
const showSearch = ref(false)
const searchQuery = ref('')
const searchMatches = ref<number[]>([])
const currentMatchIdx = ref(-1)

function setMsgRef(id: string, el: HTMLElement | null) {
  if (el) msgRefs.value.set(id, el)
  else msgRefs.value.delete(id)
}

const filteredMatchIndices = computed(() => {
  if (!searchQuery.value.trim()) return []
  const q = searchQuery.value.toLowerCase().trim()
  return chat.messages
    .map((m, i) => ({ msg: m, idx: i }))
    .filter(({ msg }) => msg.content.toLowerCase().includes(q))
    .map(({ idx }) => idx)
})

function toggleSearch() {
  showSearch.value = !showSearch.value
  if (showSearch.value) {
    nextTick(() => {
      const input = msgContainerRef.value?.querySelector<HTMLInputElement>('[data-search-input]')
      input?.focus()
    })
  } else {
    searchQuery.value = ''
    currentMatchIdx.value = -1
  }
}

function jumpToMatch(dir: 'prev' | 'next') {
  const matches = filteredMatchIndices.value
  if (matches.length === 0) return
  const cur = currentMatchIdx.value
  if (cur === -1) {
    currentMatchIdx.value = 0
  } else {
    if (dir === 'next') {
      currentMatchIdx.value = (cur + 1) % matches.length
    } else {
      currentMatchIdx.value = (cur - 1 + matches.length) % matches.length
    }
  }
  const targetIdx = matches[currentMatchIdx.value]
  const targetMsg = chat.messages[targetIdx]
  if (targetMsg) {
    const el = msgRefs.value.get(targetMsg.id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }
}

function requestRetry(msgId: string) {
  confirmRetryMsgId.value = msgId
}

function executeRetry() {
  const msgId = confirmRetryMsgId.value
  confirmRetryMsgId.value = null
  if (!msgId) return
  const conv = chat.activeConversation
  if (!conv) return
  const idx = conv.messages.findIndex(m => m.id === msgId)
  if (idx < 1) return
  const prevMsg = conv.messages[idx - 1]
  if (prevMsg.role !== 'user') return
  chat.resendEdit(prevMsg.id, prevMsg.content)
}

function cancelRetry() { confirmRetryMsgId.value = null }

function requestDeleteMsg(msgId: string) {
  const conv = chat.activeConversation
  if (!conv) return
  const msg = conv.messages.find(m => m.id === msgId)
  if (!msg) return
  confirmDeleteMsgId.value = msgId
  confirmDeleteMsgContent.value = msg.content.slice(0, 80) + (msg.content.length > 80 ? '...' : '')
}

function executeDeleteMsg() {
  const msgId = confirmDeleteMsgId.value
  confirmDeleteMsgId.value = null
  if (!msgId) return
  chat.deleteMessages([msgId])
}

function cancelDeleteMsg() { confirmDeleteMsgId.value = null }

async function scrollToBottom(force = false) {
  await nextTick()
  if (force) await new Promise(r => setTimeout(r, 50))
  messagesEndRef.value?.scrollIntoView(force ? { behavior: 'auto' } : { behavior: 'smooth' })
}

vueWatch(() => chat.messages.length, () => scrollToBottom(true))
vueWatch(() => { const msgs = chat.messages; return msgs[msgs.length - 1]?.content }, () => scrollToBottom())

function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
    e.preventDefault()
    if (chat.messages.length > 0) toggleSearch()
  }
  if (e.key === 'Escape' && showSearch.value) {
    toggleSearch()
  }
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))

function handleSend(message: string) {
  if (!chat.activeConversation) chat.createConversation()
  chat.sendMessage(message)
}

function handleEdit(msgId: string, newContent: string) {
  chat.resendEdit(msgId, newContent)
}

defineExpose({ toggleSearch })
</script>

<template>
  <div class="flex flex-col min-h-0 flex-1 relative">
    <!-- Message search bar -->
    <div v-if="showSearch" class="absolute top-0 left-0 right-0 z-10 bg-card border-b border-border px-4 py-2 flex items-center gap-2 shadow-sm">
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-muted-foreground shrink-0"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      <input
        ref="searchInput"
        data-search-input
        v-model="searchQuery"
        type="text"
        placeholder="搜索当前对话内容..."
        class="flex-1 h-8 bg-transparent border-none outline-none text-sm text-foreground placeholder:text-muted-foreground/40"
        @keydown.enter="jumpToMatch('next')"
        @keydown.shift.enter="jumpToMatch('prev')"
      />
      <span class="text-xs text-muted-foreground shrink-0 tabular-nums">
        {{ filteredMatchIndices.length > 0 ? `${currentMatchIdx + 1}/${filteredMatchIndices.length}` : '0/0' }}
      </span>
      <button
        @click="jumpToMatch('prev')"
        class="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        :disabled="filteredMatchIndices.length === 0"
        title="上一个 (Shift+Enter)"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      </button>
      <button
        @click="jumpToMatch('next')"
        class="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        :disabled="filteredMatchIndices.length === 0"
        title="下一个 (Enter)"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
      </button>
      <button
        @click="toggleSearch"
        class="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        title="关闭搜索 (Esc)"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
      </button>
    </div>

    <div ref="msgContainerRef" class="flex-1 overflow-y-auto px-4 py-6 min-h-0">
      <div class="max-w-4xl mx-auto space-y-6">
        <template v-if="chat.messages.length === 0">
          <div class="flex flex-col items-center justify-center min-h-[300px] py-16 text-center">
            <div class="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-primary"><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4Z" /><path d="M16 14H8a4 4 0 0 0-4 4v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1a4 4 0 0 0-4-4Z" /></svg>
            </div>
            <h2 class="text-xl font-semibold mb-2">企业 AI 知识助手</h2>
            <p class="text-sm text-muted-foreground max-w-md mb-8">{{ auth.isAdmin ? '上传企业文档后即可测试问答。' : '企业文档已就绪，开始提问吧。' }}</p>
          </div>
        </template>
        <template v-else>
          <div
            v-for="(msg, idx) in chat.messages"
            :key="msg.id"
            :ref="(el) => setMsgRef(msg.id, el as HTMLElement | null)"
            :class="[
              'rounded-lg transition-all duration-300',
              filteredMatchIndices.includes(idx) && currentMatchIdx !== -1 && filteredMatchIndices[currentMatchIdx] === idx
                ? 'ring-2 ring-primary/40 shadow-lg shadow-primary/5'
                : filteredMatchIndices.includes(idx)
                  ? 'ring-1 ring-primary/20'
                  : ''
            ]"
          >
            <ChatMessage
              :message="msg"
              :msgIndex="idx"
              :isAdmin="auth.isAdmin"
              :isStreaming="chat.isStreaming && msg === chat.messages[chat.messages.length - 1] && msg.role === 'assistant'"
              :searchQuery="searchQuery"
              @edit="handleEdit"
              @retry="requestRetry"
              @delete-msg="requestDeleteMsg"
            />
          </div>
        </template>
        <div ref="messagesEndRef" />
      </div>
    </div>

    <!-- Right-side match position indicator -->
    <div v-if="showSearch && searchQuery.trim()" class="absolute right-2 top-1/2 -translate-y-1/2 z-10 flex flex-col items-center gap-0.5">
      <div class="bg-card border border-border rounded-lg py-2 px-1 shadow-md flex flex-col items-center gap-1 max-h-[300px] overflow-y-auto scrollbar-none">
        <div
          v-for="(matchIdx, mi) in filteredMatchIndices"
          :key="matchIdx"
          @click="currentMatchIdx = mi; jumpToMatch('next')"
          class="w-2 h-2 rounded-full cursor-pointer transition-all shrink-0"
          :class="mi === currentMatchIdx ? 'bg-primary scale-125 shadow-sm shadow-primary/30' : 'bg-muted-foreground/30 hover:bg-muted-foreground/60'"
          :title="`跳转到第 ${matchIdx + 1} 条消息`"
        />
      </div>
      <span class="text-[10px] text-muted-foreground tabular-nums mt-1">{{ filteredMatchIndices.length }}</span>
    </div>

    <ChatInput :disabled="chat.isStreaming" :isStreaming="chat.isStreaming" @send="handleSend" @stop="chat.stopStreaming" />

    <ConfirmDialog v-if="confirmRetryMsgId" title="重新生成" message="确定重新生成回答？当前 AI 回答将被替换。" @confirm="executeRetry" @cancel="cancelRetry" />
    <ConfirmDialog v-if="confirmDeleteMsgId" title="删除消息" :message="`确定删除这条消息？\n「${confirmDeleteMsgContent}」`" destructive @confirm="executeDeleteMsg" @cancel="cancelDeleteMsg" />
  </div>
</template>
