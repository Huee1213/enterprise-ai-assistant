<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import ChatContainer from '@/components/chat/ChatContainer.vue'
import AgentPanel from '@/components/agent/AgentPanel.vue'
import Sidebar from '@/components/layout/Sidebar.vue'
import ThemeToggle from '@/components/layout/ThemeToggle.vue'

const chat = useChatStore()
const auth = useAuthStore()
const route = useRoute()
const showDebug = ref(false)

onMounted(async () => {
  chat.resetConversations()
  await chat.loadConversations()
})
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-background">
    <Sidebar />

    <div class="flex-1 flex flex-col min-w-0">
      <header class="h-11 border-b border-border flex items-center justify-between px-3 bg-card shrink-0">
        <div class="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary shrink-0">
            <path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4Z" />
            <path d="M16 14H8a4 4 0 0 0-4 4v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1a4 4 0 0 0-4-4Z" />
          </svg>
          <span class="font-semibold text-sm truncate max-w-[180px]">{{ chat.activeConversation?.title || '企业 AI 知识助手' }}</span>
        </div>

        <div class="flex items-center gap-1">
          <!-- Debug toggle (admin only) -->
          <button
            v-if="auth.isAdmin"
            @click="showDebug = !showDebug"
            class="rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            :title="showDebug ? '隐藏调试面板' : '显示调试面板'"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10" /><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8" /><path d="M12 18V6" /></svg>
          </button>

          <router-link
            v-if="auth.isAdmin"
            to="/admin"
            class="rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          >后台</router-link>

          <ThemeToggle />
          <button @click="auth.logout()" class="rounded-md p-1.5 text-muted-foreground hover:text-destructive hover:bg-accent transition-colors" title="退出登录">
            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" x2="9" y1="12" y2="12" /></svg>
          </button>
        </div>
      </header>

      <ChatContainer />
    </div>

    <!-- Debug panel (admin only, collapsible) -->
    <div v-if="auth.isAdmin && showDebug" class="w-72 border-l border-border bg-card overflow-y-auto">
      <AgentPanel />
    </div>
  </div>
</template>
