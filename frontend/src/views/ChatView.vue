<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import ChatContainer from '@/components/chat/ChatContainer.vue'
import Sidebar from '@/components/layout/Sidebar.vue'
import ThemeToggle from '@/components/layout/ThemeToggle.vue'
import ProfileEditor from '@/components/common/ProfileEditor.vue'
import AgentDebugPanel from '@/components/agent/AgentDebugPanel.vue'

const chat = useChatStore()
const auth = useAuthStore()
const showDebug = ref(false)
const mobileSidebarOpen = ref(false)
const sidebarCollapsed = ref(false)
const chatContainerRef = ref<InstanceType<typeof ChatContainer> | null>(null)

// Which assistant message the Agent debug panel follows. '__latest__' = auto follow
// the newest streaming/latest assistant message.
const FOLLOW_LATEST = '__latest__'
const followMsgId = ref<string>(FOLLOW_LATEST)

// Resizable debug panel width (desktop)
const debugWidth = ref(440)
let resizing = false
function startResize(e: PointerEvent) {
  if (e.button !== 0) return
  resizing = true
  window.addEventListener('pointermove', onResizeMove)
  window.addEventListener('pointerup', stopResize)
  e.preventDefault()
}
function onResizeMove(e: PointerEvent) {
  if (!resizing) return
  const w = window.innerWidth - e.clientX
  debugWidth.value = Math.max(340, Math.min(820, w))
}
function stopResize() {
  resizing = false
  window.removeEventListener('pointermove', onResizeMove)
  window.removeEventListener('pointerup', stopResize)
}
onUnmounted(stopResize)

onMounted(async () => {
  chat.resetConversations()
  await chat.loadConversations()
})

const profileEditorRef = ref<InstanceType<typeof ProfileEditor> | null>(null)

function openProfileEditor() {
  profileEditorRef.value?.open()
}
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
          <button
            v-if="chat.messages.length > 0"
            @click="chatContainerRef?.toggleSearch()"
            class="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors shrink-0"
            :title="'搜索对话内容 (Ctrl+F)'"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          </button>
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
          <div class="flex items-center gap-1.5 ml-1 pr-1 border-r border-border/50">
            <div @click="openProfileEditor" class="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center text-[10px] font-bold text-primary overflow-hidden shrink-0 cursor-pointer hover:ring-2 hover:ring-primary/30 transition-all" title="编辑个人资料">
              <img v-if="auth.user?.avatar_url" :src="auth.user.avatar_url" class="w-full h-full object-cover" @error="$event.target.style.display='none'" />
              <span v-else>{{ (auth.user?.display_name || auth.user?.username || '?')[0] }}</span>
            </div>
            <span class="text-[11px] text-muted-foreground hidden sm:inline truncate max-w-[120px]" title="个人资料">{{ auth.user?.display_name || auth.user?.username }}</span>
          </div>
          <button @click="auth.logout()" class="rounded-md p-1.5 text-muted-foreground hover:text-destructive hover:bg-accent transition-colors" title="退出登录">
            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" x2="9" y1="12" y2="12" /></svg>
          </button>
        </div>
      </header>

      <ChatContainer ref="chatContainerRef" :follow-msg-id="followMsgId" @view-steps="followMsgId = $event" />
    </div>

    <!-- Agent debug panel -->
    <div v-if="auth.isAdmin">
      <!-- Mobile: slide-out drawer -->
      <template v-if="showDebug">
        <div class="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm md:hidden" @click="showDebug = false" />
        <div class="fixed inset-y-0 right-0 z-40 w-[88vw] max-w-[500px] bg-card border-l border-border shadow-xl md:hidden flex flex-col">
          <div class="flex items-center justify-end px-3 pt-2 shrink-0">
            <button @click="showDebug = false" class="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted" title="关闭调试面板">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
            </button>
          </div>
          <div class="flex-1 flex flex-col min-h-0 overflow-hidden">
            <AgentDebugPanel :follow-msg-id="followMsgId" @follow-change="followMsgId = $event" />
          </div>
        </div>
      </template>
      <!-- Desktop: resizable side panel -->
      <div v-if="showDebug" class="hidden md:flex flex-col border-l border-border bg-card shrink-0 h-full relative overflow-hidden min-h-0" :style="{ width: debugWidth + 'px' }">
        <!-- Drag handle -->
        <div
          @pointerdown="startResize"
          class="absolute left-0 top-0 bottom-0 w-2 z-10 cursor-col-resize select-none group"
          title="拖动调整面板宽度"
        >
          <div class="w-1 h-full mx-auto bg-transparent group-hover:bg-primary/50 group-active:bg-primary transition-colors" />
        </div>
        <AgentDebugPanel :follow-msg-id="followMsgId" @follow-change="followMsgId = $event" />
      </div>
    </div>
  </div>

  <ProfileEditor ref="profileEditorRef" />
</template>
