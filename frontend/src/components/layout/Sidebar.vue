<script setup lang="ts">
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()

function handleNewChat() {
  chat.createConversation(false)
}

function handleSelect(id: string) {
  chat.selectConversation(id)
}

function handleDelete(id: string, event: MouseEvent) {
  event.stopPropagation()
  chat.deleteConversation(id)
}
</script>

<template>
  <aside class="w-64 h-full flex flex-col bg-sidebar border-r border-border">
    <div class="p-4 border-b border-border">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="text-primary"
          >
            <path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4Z" />
            <path d="M16 14H8a4 4 0 0 0-4 4v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1a4 4 0 0 0-4-4Z" />
          </svg>
          <span class="font-semibold text-sm">AI 知识助手</span>
        </div>
      </div>
      <button
        @click="handleNewChat"
        class="w-full inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 active:scale-[0.97] h-9 px-4 group"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="transition-transform duration-200 group-hover:rotate-90"
        >
          <path d="M5 12h14" />
          <path d="M12 5v14" />
        </svg>
        新对话
      </button>
    </div>

      <nav class="flex-1 overflow-y-auto p-2 relative">
      <div v-if="chat.conversations.length === 0" class="text-center text-muted-foreground text-xs py-8">暂无对话</div>
      <TransitionGroup name="conv" tag="div" class="space-y-1 relative">
      <button
        v-for="(conv, idx) in chat.conversations"
        :key="conv.id"
        @click="handleSelect(conv.id)"
        :style="{ animationDelay: `${Math.min(idx * 0.03, 0.3)}s` }"
        class="w-full flex items-center justify-between gap-2 rounded-md px-3 py-2 text-sm transition-colors hover:bg-sidebar-muted group animate-fade-in"
        :class="{
          'bg-sidebar-muted text-sidebar-foreground': conv.id === chat.activeConversationId,
          'text-sidebar-foreground/80': conv.id !== chat.activeConversationId,
        }"
      >
        <span class="truncate text-left flex-1">{{ conv.title }}</span>
        <button
          @click="handleDelete(conv.id, $event)"
          class="opacity-0 group-hover:opacity-100 hover:text-destructive transition-opacity shrink-0"
          title="删除对话"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M3 6h18" />
            <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
            <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
          </svg>
        </button>
      </button>
      </TransitionGroup>
    </nav>

    <div class="p-3 border-t border-border">
      <div class="flex items-center justify-between text-xs text-muted-foreground">
        <span>Agent 模式</span>
        <button
          @click="chat.toggleAgentMode()"
          class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          :class="chat.useAgentMode ? 'bg-primary' : 'bg-input'"
          role="switch"
          :aria-checked="chat.useAgentMode"
        >
          <span
            class="pointer-events-none block h-4 w-4 rounded-full bg-white shadow-lg ring-0 transition-transform"
            :class="chat.useAgentMode ? 'translate-x-[18px]' : 'translate-x-[2px]'"
          />
        </button>
      </div>
    </div>
  </aside>
</template>
