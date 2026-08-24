<script setup lang="ts">
import { ref, computed, nextTick, watch as vueWatch, onMounted, onUnmounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { fetchSuggestions, type ChatSuggestion } from '@/api/chat'
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
const scrollContainerRef = ref<HTMLDivElement | null>(null)

// Knowledge-base starter questions (empty state)
const suggestions = ref<ChatSuggestion[]>([])
const suggestionsLoaded = ref(false)
let suggestionsPromise: Promise<void> | null = null

async function loadSuggestions() {
  if (suggestionsLoaded.value) return
  if (suggestionsPromise) return suggestionsPromise
  suggestionsPromise = (async () => {
    try {
      suggestions.value = await fetchSuggestions()
    } catch {
      suggestions.value = []
    } finally {
      suggestionsLoaded.value = true
      suggestionsPromise = null
    }
  })()
  return suggestionsPromise
}

// Message search
const showSearch = ref(false)
const searchQuery = ref('')
const currentMatchIdx = ref(-1)

// Scroll tracking for position indicator
const activeDotIdx = ref(0)
const showTimeline = ref(false)
let timelineTimer: ReturnType<typeof setTimeout> | null = null
let scrollLocked = false

function onTimelineEnter() {
  if (timelineTimer) clearTimeout(timelineTimer)
  showTimeline.value = true
}

function onTimelineLeave() {
  if (timelineTimer) clearTimeout(timelineTimer)
  timelineTimer = setTimeout(() => { showTimeline.value = false }, 300)
}

const filteredMatchIndices = computed(() => {
  if (!searchQuery.value.trim()) return []
  const q = searchQuery.value.toLowerCase().trim()
  return chat.messages
    .map((m, i) => ({ msg: m, idx: i }))
    .filter(({ msg }) => msg.content.toLowerCase().includes(q))
    .map(({ idx }) => idx)
})

// Messages to show as dots: only user messages
const dotMessages = computed(() =>
  chat.messages.filter(m => m.role === 'user')
)

const userMsgItems = computed(() =>
  dotMessages.value.map(m => ({
    id: m.id,
    idx: chat.messages.indexOf(m),
    label: m.content.slice(0, 48) + (m.content.length > 48 ? '...' : ''),
  }))
)

function scrollToMsg(msgId: string) {
  const msgIdx = chat.messages.findIndex(m => m.id === msgId)
  if (msgIdx !== -1) {
    activeDotIdx.value = msgIdx
    scrollLocked = true
    setTimeout(() => { scrollLocked = false }, 400)
  }
  const el = msgRefs.value.get(msgId)
  if (el) {
    el.scrollIntoView({ behavior: 'auto', block: 'center' })
  }
}

function handleDotClick(msgId: string) {
  scrollToMsg(msgId)
}

function onScroll() {
  if (scrollLocked) return
  const el = scrollContainerRef.value
  if (!el || chat.messages.length === 0) return

  const containerRect = el.getBoundingClientRect()
  const midY = containerRect.top + containerRect.height / 2
  let bestIdx = activeDotIdx.value
  let bestDist = Infinity
  let found = false

  for (const [id, msgEl] of msgRefs.value.entries()) {
    const msg = chat.messages.find(m => m.id === id)
    if (!msg || msg.role !== 'user') continue
    found = true
    const rect = msgEl.getBoundingClientRect()
    const dist = Math.abs(rect.top + rect.height / 2 - midY)
    if (dist < bestDist) {
      bestDist = dist
      bestIdx = chat.messages.findIndex(m => m.id === id)
    }
  }
  if (found) activeDotIdx.value = bestIdx
}

function setMsgRef(id: string, el: HTMLElement | null) {
  if (el) msgRefs.value.set(id, el)
  else msgRefs.value.delete(id)
}

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

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  loadSuggestions()
})
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

    <div ref="scrollContainerRef" @scroll="onScroll" class="flex-1 overflow-y-auto px-4 py-6 min-h-0">
      <div class="max-w-4xl mx-auto space-y-6">
        <template v-if="chat.messages.length === 0">
          <div class="flex flex-col items-center justify-center min-h-[300px] py-16 text-center">
            <div class="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-primary"><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4Z" /><path d="M16 14H8a4 4 0 0 0-4 4v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1a4 4 0 0 0-4-4Z" /></svg>
            </div>
            <h2 class="text-xl font-semibold mb-2">企业 AI 知识助手</h2>
            <p class="text-sm text-muted-foreground max-w-md mb-6">{{ auth.isAdmin ? '上传企业文档后即可测试问答。' : '企业文档已就绪，开始提问吧。' }}</p>

            <div v-if="suggestionsLoaded && suggestions.length > 0" class="w-full max-w-xl">
              <p class="text-[11px] font-medium text-muted-foreground/60 mb-2">试试这些基于知识库的问题：</p>
              <div class="flex flex-wrap justify-center gap-2">
                <button
                  v-for="s in suggestions"
                  :key="s.id"
                  @click="handleSend(s.question)"
                  class="group inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3.5 py-1.5 text-xs text-muted-foreground hover:border-primary/40 hover:text-foreground hover:bg-primary/5 transition-colors cursor-pointer"
                >
                  <svg v-if="s.id === '__kb_overview__'" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary shrink-0"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-muted-foreground/50 group-hover:text-primary shrink-0"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>
                  <span>{{ s.title }}</span>
                </button>
              </div>
            </div>
            <p v-else-if="suggestionsLoaded && suggestions.length === 0" class="text-xs text-muted-foreground/50">
              {{ auth.isAdmin ? '知识库暂无文档，请先上传文档后刷新本页。' : '知识库暂无内容，请联系管理员上传文档。' }}
            </p>
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
              :isLastMsg="idx === chat.messages.length - 1"
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

    <!-- Right-side message navigation: small horizontal bars -->
    <div v-if="userMsgItems.length >= 2" class="absolute right-8 inset-y-0 z-10 flex items-center pointer-events-none">
      <div
        class="relative flex items-center pointer-events-auto"
        @mouseenter="onTimelineEnter"
        @mouseleave="onTimelineLeave"
      >
        <!-- Bars column -->
        <div class="h-3/5 flex flex-col items-end justify-center gap-1.5 py-1 -mr-1">
          <div
            v-for="(item, i) in userMsgItems.slice(0, 6)"
            :key="item.id"
            class="h-1 rounded-sm transition-all duration-200 ease-out"
            :class="activeDotIdx === item.idx ? 'w-5 bg-primary' : 'w-2 bg-muted-foreground/30'"
          />
        </div>

        <!-- Hover popup: scrollable message list -->
        <div
          v-show="showTimeline"
          class="flex flex-col pointer-events-auto"
          @mouseenter="onTimelineEnter"
          @mouseleave="onTimelineLeave"
        >
          <div class="bg-popover text-popover-foreground rounded-lg shadow-xl border border-border py-1.5 min-w-[220px] max-w-[360px] max-h-[320px] overflow-y-auto">
            <div class="px-3 py-1.5 text-[10px] font-medium text-muted-foreground/60 border-b border-border/50 flex items-center justify-between sticky top-0 bg-popover">
              <span>消息定位 ({{ userMsgItems.length }})</span>
              <span class="text-[9px]">点击跳转</span>
            </div>
            <div
              v-for="(item, i) in userMsgItems"
              :key="item.id"
              @click="handleDotClick(item.id)"
              class="flex items-start gap-2 px-3 py-2 cursor-pointer transition-colors hover:bg-muted/50 border-b border-border/30 last:border-0"
              :class="activeDotIdx === item.idx ? 'bg-primary/5' : ''"
            >
              <span class="text-[10px] font-mono text-muted-foreground/40 mt-0.5 shrink-0 w-4 text-right">{{ i + 1 }}</span>
              <span class="text-xs leading-relaxed line-clamp-2 break-words flex-1 min-w-0">{{ item.label }}</span>
              <div v-if="activeDotIdx === item.idx" class="w-1.5 h-1.5 rounded-full bg-primary shrink-0 mt-1.5" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <ChatInput :disabled="chat.isStreaming" :isStreaming="chat.isStreaming" @send="handleSend" @stop="chat.stopStreaming" />

    <ConfirmDialog v-if="confirmRetryMsgId" title="重新生成" message="确定重新生成回答？当前 AI 回答将被替换。" @confirm="executeRetry" @cancel="cancelRetry" />
    <ConfirmDialog v-if="confirmDeleteMsgId" title="删除消息" :message="`确定删除这条消息？\n「${confirmDeleteMsgContent}」`" destructive @confirm="executeDeleteMsg" @cancel="cancelDeleteMsg" />
  </div>
</template>
