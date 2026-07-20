<script setup lang="ts">
import { ref, computed } from 'vue'
import { useChatStore } from '@/stores/chat'
import { regenerateConversationTitle } from '@/api/chat'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

defineProps<{ collapsed?: boolean }>()
const emit = defineEmits<{ close: [] }>()

const chat = useChatStore()
const confirmingDelete = ref<string | null>(null)
const regenerating = ref<string | null>(null)
const rotatingTitles = ref<Set<string>>(new Set())
const searchQuery = ref('')
const isSearching = ref(false)

const filteredConversations = computed(() => {
  if (!searchQuery.value.trim()) return chat.conversations
  const q = searchQuery.value.toLowerCase().trim()
  return chat.conversations.filter(c => c.title.toLowerCase().includes(q))
})

function handleNewChat() {
  chat.createConversation(false)
  emit('close')
}

function handleSelect(id: string) {
  chat.selectConversation(id)
  searchQuery.value = ''
}

async function handleRegenerateTitle(id: string, event: MouseEvent) {
  event.stopPropagation()
  regenerating.value = id
  rotatingTitles.value.add(id)
  try {
    const newTitle = await regenerateConversationTitle(id)
    const conv = chat.conversations.find(c => c.id === id)
    if (conv) conv.title = newTitle
  } catch {}
  rotatingTitles.value.delete(id)
  regenerating.value = null
}

function handleDelete(id: string, event: MouseEvent) {
  event.stopPropagation()
  confirmingDelete.value = id
}

function confirmDelete() {
  const id = confirmingDelete.value
  if (!id) return
  chat.deleteConversation(id)
  confirmingDelete.value = null
}

function cancelDelete() {
  confirmingDelete.value = null
}
</script>

<template>
  <aside class="h-full flex flex-col bg-sidebar border-r border-border transition-all duration-250" :class="collapsed ? 'w-14' : 'w-64'">
    <!-- Mobile close button -->
    <button @click="emit('close')" class="md:hidden absolute top-2 right-2 rounded-md p-1 text-muted-foreground hover:text-foreground transition-colors" aria-label="关闭侧栏">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
    </button>

    <div class="p-4 border-b border-border" :class="collapsed ? 'p-2 flex flex-col items-center' : ''">
      <div class="flex items-center justify-between" :class="collapsed ? 'mb-2' : 'mb-3'">
        <div class="flex items-center gap-2" :class="collapsed ? 'justify-center w-full' : ''">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary shrink-0">
            <path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4Z" /><path d="M16 14H8a4 4 0 0 0-4 4v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1a4 4 0 0 0-4-4Z" />
          </svg>
          <span v-show="!collapsed" class="font-semibold text-sm">AI 知识助手</span>
        </div>
      </div>
      <button @click="handleNewChat" class="inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-all duration-150 bg-primary text-primary-foreground hover:bg-primary/90 active:scale-[0.97] h-9 group" :class="collapsed ? 'w-9 px-0' : 'w-full px-4'" :title="collapsed ? '新对话' : ''">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="transition-transform duration-200 group-hover:rotate-90 shrink-0"><path d="M5 12h14" /><path d="M12 5v14" /></svg>
        <span v-show="!collapsed">新对话</span>
      </button>
    </div>

    <!-- Search input (not collapsed) -->
    <div v-show="!collapsed" class="px-3 pt-2">
      <div class="relative">
        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/50 pointer-events-none"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索历史对话..."
          class="w-full h-8 rounded-md bg-sidebar-muted/50 border border-border/50 pl-8 pr-2 text-xs text-sidebar-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/30 transition-all"
        />
        <button
          v-if="searchQuery"
          @click="searchQuery = ''"
          class="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground/40 hover:text-muted-foreground transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
        </button>
      </div>
    </div>

    <nav class="flex-1 overflow-y-auto p-2 relative" :class="collapsed ? 'px-1' : ''">
      <div v-if="chat.conversations.length === 0" class="text-center text-muted-foreground text-xs py-8" :class="collapsed ? 'hidden' : ''">暂无对话</div>
      <div v-else-if="searchQuery && filteredConversations.length === 0" class="text-center text-muted-foreground text-xs py-8">未找到匹配对话</div>
      <div class="space-y-1" :class="collapsed ? 'flex flex-col items-center' : ''">
        <button
          v-for="(conv, idx) in filteredConversations"
          :key="conv.id"
          @click="handleSelect(conv.id)"
          :style="{ animationDelay: `${Math.min(idx * 0.03, 0.3)}s` }"
          class="flex items-center gap-2 rounded-md text-sm transition-colors hover:bg-sidebar-muted group"
          :class="[
            conv.id === chat.activeConversationId ? 'bg-sidebar-muted text-sidebar-foreground' : 'text-sidebar-foreground/80',
            collapsed ? 'w-9 h-9 justify-center px-0' : 'w-full px-3 py-2'
          ]"
          :title="collapsed ? conv.title : ''"
        >
          <svg v-show="collapsed" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="shrink-0"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <span v-show="!collapsed" class="truncate text-left flex-1" :class="{ 'animate-pulse': regenerating === conv.id }">
            <span v-if="searchQuery">
              <span v-for="(part, pi) in conv.title.split(new RegExp(`(${searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'))" :key="pi">
                <mark v-if="part.toLowerCase() === searchQuery.toLowerCase()" class="bg-primary/20 text-sidebar-foreground rounded-sm px-0.5">{{ part }}</mark>
                <template v-else>{{ part }}</template>
              </span>
            </span>
            <template v-else>{{ conv.title }}</template>
          </span>
          <button
            v-show="!collapsed"
            @click="handleRegenerateTitle(conv.id, $event)"
            :disabled="regenerating === conv.id"
            class="opacity-0 group-hover:opacity-100 hover:text-primary transition-opacity shrink-0"
            title="重新生成标题"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :class="{ 'animate-spin-slow': rotatingTitles.has(conv.id) }"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          </button>
          <button
            v-show="!collapsed"
            @click="handleDelete(conv.id, $event)"
            class="opacity-0 group-hover:opacity-100 hover:text-destructive transition-opacity shrink-0"
            title="删除对话"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /></svg>
          </button>
        </button>
      </div>
    </nav>

    <ConfirmDialog
      v-if="confirmingDelete"
      title="删除对话"
      message="确定删除此对话？删除后不可恢复。"
      destructive
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />

    <div class="p-3 border-t border-border" :class="collapsed ? 'p-2 flex flex-col items-center' : ''">
      <div v-show="!collapsed" class="flex items-center justify-between text-xs text-muted-foreground">
        <span>Agent 模式</span>
        <button
          @click="chat.toggleAgentMode()"
          class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors"
          :class="chat.useAgentMode ? 'bg-primary' : 'bg-input'"
          role="switch"
          :aria-checked="chat.useAgentMode"
        >
          <span class="pointer-events-none block h-4 w-4 rounded-full bg-white shadow-lg ring-0 transition-transform" :class="chat.useAgentMode ? 'translate-x-[18px]' : 'translate-x-[2px]'" />
        </button>
      </div>
      <!-- Collapsed: show agent mode indicator dot -->
      <div v-show="collapsed" class="flex flex-col items-center gap-2">
        <div class="w-2 h-2 rounded-full" :class="chat.useAgentMode ? 'bg-primary' : 'bg-muted-foreground/30'" :title="chat.useAgentMode ? 'Agent模式' : '普通模式'" />
      </div>
    </div>
  </aside>
</template>
