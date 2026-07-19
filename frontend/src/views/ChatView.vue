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
const mobileSidebarOpen = ref(false)
const sidebarCollapsed = ref(false)

onMounted(async () => {
  chat.resetConversations()
  await chat.loadConversations()
})
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-background">
    <!-- Mobile sidebar backdrop -->
    <div v-if="mobileSidebarOpen" class="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm md:hidden" @click="mobileSidebarOpen = false" />

    <!-- Sidebar: slide-out on mobile, collapsible on desktop -->
    <div
      class="fixed md:static inset-y-0 left-0 z-40 transition-all duration-250 ease-out md:translate-x-0"
      :class="[
        mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full',
        sidebarCollapsed ? 'w-14 md:w-14' : 'w-64'
      ]"
    >
      <Sidebar :collapsed="sidebarCollapsed" @close="mobileSidebarOpen = false" />
    </div>

    <!-- Desktop sidebar collapse toggle -->
    <button
      @click="sidebarCollapsed = !sidebarCollapsed"
      class="hidden md:flex absolute left-0 top-1/2 -translate-y-1/2 z-20 w-5 h-10 items-center justify-center rounded-r-md bg-card border border-l-0 border-border text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
      :class="sidebarCollapsed ? 'ml-14' : 'ml-64'"
      :title="sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :class="sidebarCollapsed ? 'rotate-180' : ''">
        <polyline points="15 18 9 12 15 6" />
      </svg>
    </button>

    <div class="flex-1 flex flex-col min-w-0">
      <header class="h-11 border-b border-border flex items-center justify-between px-2 md:px-3 bg-card shrink-0">
        <div class="flex items-center gap-2 min-w-0">
          <!-- Mobile hamburger -->
          <button
            @click="mobileSidebarOpen = !mobileSidebarOpen"
            class="md:hidden rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors shrink-0"
            aria-label="切换侧栏"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
          </button>
          <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary shrink-0 hidden md:block">
            <path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4Z" />
            <path d="M16 14H8a4 4 0 0 0-4 4v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1a4 4 0 0 0-4-4Z" />
          </svg>
          <span class="font-semibold text-sm truncate">{{ chat.activeConversation?.title || '企业 AI 知识助手' }}</span>
        </div>

        <div class="flex items-center gap-0.5 md:gap-1">
          <!-- Debug toggle (admin only) -->
          <button
            v-if="auth.isAdmin"
            @click="showDebug = !showDebug"
            class="rounded-md p-1.5 md:px-2 md:py-1 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
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

    <!-- Debug panel: slide-out drawer on mobile, side panel on desktop -->
    <div v-if="auth.isAdmin" class="relative">
      <!-- Mobile backdrop -->
      <div v-if="showDebug" class="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm md:hidden" @click="showDebug = false" />
      <!-- Panel content -->
      <div
        class="fixed md:static inset-y-0 right-0 z-40 w-72 md:w-72 bg-card border-l border-border overflow-y-auto transition-transform duration-250 ease-out md:translate-x-0"
        :class="showDebug ? 'translate-x-0' : 'translate-x-full'"
      >
        <div class="flex items-center justify-between p-3 border-b border-border md:hidden">
          <span class="text-xs font-semibold">Agent 调试</span>
          <button @click="showDebug = false" class="rounded-md p-1 text-muted-foreground hover:text-foreground transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>
        <AgentPanel />
      </div>
    </div>
  </div>
</template>
