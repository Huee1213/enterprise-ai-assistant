<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import ChatContainer from '@/components/chat/ChatContainer.vue'

const chat = useChatStore()

onMounted(() => {
  if (!chat.activeConversation) {
    chat.createConversation()
  }
})
</script>

<template>
  <div class="h-full flex flex-col bg-background">
    <header class="h-10 border-b border-border flex items-center justify-between px-4 bg-card shrink-0">
      <div class="flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <span class="text-sm font-medium">对话测试</span>
      </div>
      <p class="text-[10px] text-muted-foreground">管理员快速测试 AI 问答</p>
    </header>
    <ChatContainer />
  </div>
</template>
