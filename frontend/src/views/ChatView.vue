<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import ChatContainer from '@/components/chat/ChatContainer.vue'
import Sidebar from '@/components/layout/Sidebar.vue'
import ThemeToggle from '@/components/layout/ThemeToggle.vue'

const chat = useChatStore()
const auth = useAuthStore()
const route = useRoute()
const showDebug = ref(false)
const mobileSidebarOpen = ref(false)
const sidebarCollapsed = ref(false)

const expandedSteps = ref<Set<string>>(new Set())

function toggleStep(msgIdx: number, stepIdx: number) {
  const key = `${msgIdx}-${stepIdx}`
  const next = new Set(expandedSteps.value)
  if (next.has(key)) next.delete(key); else next.add(key)
  expandedSteps.value = next
}

function isExpanded(msgIdx: number, stepIdx: number): boolean {
  return expandedSteps.value.has(`${msgIdx}-${stepIdx}`)
}

onMounted(async () => {
  chat.resetConversations()
  await chat.loadConversations()
})

const showChatProfile = ref(false)
const chatProfileTab = ref<'info' | 'avatar'>('info')
const chatDisplayName = ref('')
const chatPhone = ref('')
const chatNewPassword = ref('')
const chatNewPassword2 = ref('')
const chatAvatarUrl = ref('')
const chatProfileSaving = ref(false)
const chatProfileError = ref('')
const chatProfileSuccess = ref('')
const chatAvatarFileInput = ref<HTMLInputElement | null>(null)
const chatAvatarUploading = ref(false)

function generatePassword() {
  const lower = 'abcdefghijklmnopqrstuvwxyz'
  const upper = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
  const digits = '0123456789'
  const special = '!@#$%^&*()_+-=[]{};:,.<>?'
  const pick = (s: string) => s[Math.floor(Math.random() * s.length)]
  let pw = pick(lower) + pick(upper) + pick(digits) + pick(special)
  const all = lower + upper + digits + special
  for (let i = 0; i < 8; i++) pw += pick(all)
  return pw.split('').sort(() => Math.random() - 0.5).join('')
}

const chatPwHasLower = computed(() => /[a-z]/.test(chatNewPassword.value))
const chatPwHasUpper = computed(() => /[A-Z]/.test(chatNewPassword.value))
const chatPwHasDigit = computed(() => /[0-9]/.test(chatNewPassword.value))
const chatPwHasSpecial = computed(() => /[!@#$%^&*()_+\-=\[\]{};':",.<>\/?\\|]/.test(chatNewPassword.value))
const chatPwLongEnough = computed(() => chatNewPassword.value.length >= 8)

const chatPw2HasLower = computed(() => /[a-z]/.test(chatNewPassword2.value))
const chatPw2HasUpper = computed(() => /[A-Z]/.test(chatNewPassword2.value))
const chatPw2HasDigit = computed(() => /[0-9]/.test(chatNewPassword2.value))
const chatPw2HasSpecial = computed(() => /[!@#$%^&*()_+\-=\[\]{};':",.<>\/?\\|]/.test(chatNewPassword2.value))
const chatPw2LongEnough = computed(() => chatNewPassword2.value.length >= 8)

function openChatProfile() {
  chatDisplayName.value = auth.user?.display_name || ''
  chatPhone.value = auth.user?.phone || ''
  chatAvatarUrl.value = auth.user?.avatar_url || ''
  chatProfileError.value = ''; chatProfileSuccess.value = ''
  chatProfileTab.value = 'info'
  showChatProfile.value = true
}

async function saveChatProfile() {
  chatProfileError.value = ''; chatProfileSuccess.value = ''
  if (chatNewPassword.value && chatNewPassword.value !== chatNewPassword2.value) {
    chatProfileError.value = '两次密码输入不一致'; return
  }
  chatProfileSaving.value = true
  try {
    const updates: any = {}
    if (chatDisplayName.value !== (auth.user?.display_name || '')) updates.display_name = chatDisplayName.value
    if (chatPhone.value !== (auth.user?.phone || '')) updates.phone = chatPhone.value
    if (chatNewPassword.value) updates.password = chatNewPassword.value
    if (Object.keys(updates).length > 0) {
      await auth.updateSelfProfile(updates)
      chatProfileSuccess.value = '资料已更新'
      chatNewPassword.value = ''; chatNewPassword2.value = ''
      setTimeout(() => chatProfileSuccess.value = '', 2000)
    }
  } catch (err: any) { chatProfileError.value = err.response?.data?.detail || err.message || '更新失败' }
  finally { chatProfileSaving.value = false }
}

async function uploadChatAvatar(file: File) {
  if (!file.type.startsWith('image/')) { chatProfileError.value = '请选择图片文件'; return }
  chatAvatarUploading.value = true; chatProfileError.value = ''
  try {
    const data = await auth.uploadAvatar(file)
    chatAvatarUrl.value = data.url
    chatProfileSuccess.value = '头像已更新'
    setTimeout(() => chatProfileSuccess.value = '', 2000)
  } catch (err: any) { chatProfileError.value = err.response?.data?.detail || err.message || '上传失败' }
  finally { chatAvatarUploading.value = false }
}

async function saveChatAvatarUrl() {
  if (!chatAvatarUrl.value.trim()) return
  chatProfileError.value = ''; chatProfileSaving.value = true
  try {
    await auth.updateSelfProfile({ avatar_url: chatAvatarUrl.value.trim() })
    chatProfileSuccess.value = '头像已更新'
    setTimeout(() => chatProfileSuccess.value = '', 2000)
  } catch (err: any) { chatProfileError.value = err.response?.data?.detail || err.message || '更新失败' }
  finally { chatProfileSaving.value = false }
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
            <div @click="!auth.isAdmin ? (openChatProfile(), chatProfileTab='avatar') : null" class="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center text-[10px] font-bold text-primary overflow-hidden shrink-0 cursor-pointer" :class="auth.isAdmin ? 'cursor-default' : 'cursor-pointer hover:ring-2 hover:ring-primary/30 transition-all'" :title="auth.isAdmin ? '请在管理后台修改' : '点击修改头像'">
              <img v-if="auth.user?.avatar_url" :src="auth.user.avatar_url" class="w-full h-full object-cover" @error="$event.target.style.display='none'" />
              <span v-else>{{ (auth.user?.display_name || auth.user?.username || '?')[0] }}</span>
            </div>
            <span @click="!auth.isAdmin ? (openChatProfile(), chatProfileTab='info') : null" class="text-[11px] text-muted-foreground hidden sm:inline truncate max-w-[120px] cursor-pointer hover:text-foreground transition-colors" :class="auth.isAdmin ? 'cursor-default hover:text-muted-foreground pointer-events-none' : ''" :title="auth.isAdmin ? '请在管理后台修改' : '点击编辑资料'">{{ auth.user?.display_name || auth.user?.username }}</span>
          </div>
          <button @click="auth.logout()" class="rounded-md p-1.5 text-muted-foreground hover:text-destructive hover:bg-accent transition-colors" title="退出登录">
            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" x2="9" y1="12" y2="12" /></svg>
          </button>
        </div>
      </header>

      <ChatContainer />
    </div>

    <!-- Agent debug panel -->
    <div v-if="auth.isAdmin">
      <!-- Mobile: slide-out drawer -->
      <template v-if="showDebug">
        <div class="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm md:hidden" @click="showDebug = false" />
        <div class="fixed inset-y-0 right-0 z-40 w-72 bg-card border-l border-border shadow-xl md:hidden flex flex-col">
          <div class="flex items-center justify-between px-4 py-3 bg-card border-b border-border shrink-0">
            <span class="text-xs font-semibold">Agent 调试</span>
            <button @click="showDebug = false" class="rounded-md p-1 text-muted-foreground hover:text-foreground">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
            </button>
          </div>
          <div class="flex-1 overflow-y-auto px-4 py-3 min-h-0">
            <div v-if="chat.messages.length === 0" class="text-center text-muted-foreground text-sm py-8">暂无 Agent 活动</div>
            <div v-for="(msg, msgIdx) in chat.messages" :key="msg.id" class="mb-4">
              <div v-if="msg.role === 'assistant' && msg.steps && msg.steps.length > 0">
                <p class="text-xs font-medium text-muted-foreground/70 mb-2">消息 {{ msgIdx + 1 }} · {{ msg.steps.length }} 步</p>
                <div class="space-y-1.5">
                  <button v-for="(step, stepIdx) in msg.steps" :key="`${msg.id}-${stepIdx}`" @click="toggleStep(msgIdx, stepIdx)"
                    class="w-full text-left rounded-lg p-2.5 text-xs font-mono transition-all"
                    :class="isExpanded(msgIdx, stepIdx) ? 'bg-muted border border-border shadow-sm' : 'bg-muted/40 hover:bg-muted/70 border border-transparent'">
                    <div class="flex items-center gap-2.5">
                      <span v-if="step.action === 'llm_call'" class="shrink-0"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-primary"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></span>
                      <span v-else class="shrink-0"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-accent-foreground"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg></span>
                      <div class="flex-1 min-w-0"><span class="font-medium text-foreground/90">{{ step.action === 'llm_call' ? 'LLM 调用' : '工具执行' }}</span><span class="text-muted-foreground ml-1.5">#{{ step.step }}</span></div>
                      <svg class="shrink-0 text-muted-foreground transition-transform duration-200" :class="isExpanded(msgIdx, stepIdx) ? 'rotate-180' : ''" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                    </div>
                    <div v-if="isExpanded(msgIdx, stepIdx)" class="mt-2.5 space-y-2 border-t border-border/50 pt-2.5">
                      <div><div class="flex items-center gap-1 text-muted-foreground mb-1"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" x2="15" y1="20" y2="20"/><line x1="12" x2="12" y1="4" y2="20"/></svg><span class="text-[10px] font-medium">输入</span></div><div class="p-2 rounded bg-background/60 text-muted-foreground text-[10px] break-words whitespace-pre-wrap max-h-20 overflow-y-auto leading-relaxed">{{ step.input.slice(0, 300) || '—' }}</div></div>
                      <div><div class="flex items-center gap-1 text-muted-foreground mb-1"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg><span class="text-[10px] font-medium">输出</span></div><div class="p-2 rounded bg-background/60 text-muted-foreground text-[10px] break-words whitespace-pre-wrap max-h-20 overflow-y-auto leading-relaxed">{{ step.output.slice(0, 300) || '—' }}</div></div>
                    </div>
                  </button>
                </div>
              </div>
            </div>
          </div>
          <div class="flex items-center justify-between px-4 py-3 border-t border-border bg-card shrink-0">
            <span class="text-muted-foreground text-xs">Agent 模式</span>
            <span class="text-xs font-medium" :class="chat.useAgentMode ? 'text-primary' : 'text-muted-foreground'">{{ chat.useAgentMode ? '开启' : '关闭（纯 RAG）' }}</span>
          </div>
        </div>
      </template>
      <!-- Desktop: side panel -->
      <div v-if="showDebug" class="hidden md:flex flex-col w-72 border-l border-border bg-card shrink-0 h-full relative">
        <div class="p-4 border-b border-border shrink-0">
          <h2 class="text-sm font-semibold flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-primary"><circle cx="12" cy="12" r="10"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 18V6"/></svg>
            Agent 调试
          </h2>
        </div>
        <div class="flex-1 overflow-y-auto p-4">
          <div v-if="chat.messages.length === 0" class="text-center text-muted-foreground text-sm py-8">暂无 Agent 活动</div>
          <div v-for="(msg, msgIdx) in chat.messages" :key="msg.id" class="mb-4">
            <div v-if="msg.role === 'assistant' && msg.steps && msg.steps.length > 0">
              <p class="text-xs font-medium text-muted-foreground/70 mb-2">消息 {{ msgIdx + 1 }} · {{ msg.steps.length }} 步</p>
              <div class="space-y-1.5">
                <button v-for="(step, stepIdx) in msg.steps" :key="`${msg.id}-${stepIdx}`" @click="toggleStep(msgIdx, stepIdx)"
                  class="w-full text-left rounded-lg p-2.5 text-xs font-mono transition-all"
                  :class="isExpanded(msgIdx, stepIdx) ? 'bg-muted border border-border shadow-sm' : 'bg-muted/40 hover:bg-muted/70 border border-transparent'">
                  <div class="flex items-center gap-2.5">
                    <span v-if="step.action === 'llm_call'" class="shrink-0"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-primary"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></span>
                    <span v-else class="shrink-0"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-accent-foreground"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg></span>
                    <div class="flex-1 min-w-0"><span class="font-medium text-foreground/90">{{ step.action === 'llm_call' ? 'LLM 调用' : '工具执行' }}</span><span class="text-muted-foreground ml-1.5">#{{ step.step }}</span></div>
                    <svg class="shrink-0 text-muted-foreground transition-transform duration-200" :class="isExpanded(msgIdx, stepIdx) ? 'rotate-180' : ''" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                  </div>
                  <div v-if="isExpanded(msgIdx, stepIdx)" class="mt-2.5 space-y-2 border-t border-border/50 pt-2.5">
                    <div><div class="flex items-center gap-1 text-muted-foreground mb-1"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" x2="15" y1="20" y2="20"/><line x1="12" x2="12" y1="4" y2="20"/></svg><span class="text-[10px] font-medium">输入</span></div><div class="p-2 rounded bg-background/60 text-muted-foreground text-[10px] break-words whitespace-pre-wrap max-h-20 overflow-y-auto leading-relaxed">{{ step.input.slice(0, 300) || '—' }}</div></div>
                    <div><div class="flex items-center gap-1 text-muted-foreground mb-1"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg><span class="text-[10px] font-medium">输出</span></div><div class="p-2 rounded bg-background/60 text-muted-foreground text-[10px] break-words whitespace-pre-wrap max-h-20 overflow-y-auto leading-relaxed">{{ step.output.slice(0, 300) || '—' }}</div></div>
                  </div>
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="p-3 border-t border-border">
          <div class="flex items-center justify-between text-xs">
            <span class="text-muted-foreground">Agent 模式</span>
            <span class="font-medium" :class="chat.useAgentMode ? 'text-primary' : 'text-muted-foreground'">{{ chat.useAgentMode ? '开启' : '关闭（纯 RAG）' }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Employee profile edit dialog -->
  <Teleport to="body">
    <div v-if="showChatProfile" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-fade-in" @click="showChatProfile = false">
      <div class="bg-card border border-border rounded-xl w-full max-w-sm shadow-2xl animate-scale-in overflow-hidden" @click.stop>
        <div class="px-5 py-4 border-b border-border flex items-center justify-between bg-muted/20">
          <div class="flex items-center gap-2.5">
            <div class="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            </div>
            <div><h2 class="text-sm font-semibold">个人资料</h2><p class="text-[10px] text-muted-foreground">{{ auth.user?.username }}</p></div>
          </div>
          <button @click="showChatProfile = false" class="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>
        </div>
        <div class="p-5 space-y-4 max-h-[70vh] overflow-y-auto">
          <!-- Avatar tab -->
          <div v-if="chatProfileTab === 'avatar'" class="space-y-3">
            <div class="flex flex-col items-center gap-3">
              <div class="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center text-2xl font-bold text-primary overflow-hidden ring-2 ring-border">
                <img v-if="chatAvatarUrl" :src="chatAvatarUrl" class="w-full h-full object-cover" />
                <span v-else>{{ (auth.user?.display_name || auth.user?.username || '?')[0] }}</span>
              </div>
              <div class="border-2 border-dashed rounded-xl p-4 w-full text-center cursor-pointer hover:border-primary/50 hover:bg-muted/30 transition-colors" @click="chatAvatarFileInput?.click()">
                <input ref="chatAvatarFileInput" type="file" accept="image/*" class="hidden" @change="chatAvatarFileInput?.files?.[0] && uploadChatAvatar(chatAvatarFileInput.files[0])" />
                <svg v-if="!chatAvatarUploading" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="mx-auto mb-1 text-muted-foreground"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                <div v-else class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-1" />
                <p class="text-xs text-muted-foreground">{{ chatAvatarUploading ? '上传中...' : '点击上传图片' }}</p>
              </div>
            </div>
            <div class="relative"><div class="absolute inset-0 flex items-center"><div class="w-full border-t border-border" /></div><div class="relative flex justify-center"><span class="bg-card px-2 text-[10px] text-muted-foreground">或使用在线链接</span></div></div>
            <div class="flex gap-2">
              <input v-model="chatAvatarUrl" placeholder="https://example.com/avatar.png" class="flex-1 h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
              <button @click="saveChatAvatarUrl" :disabled="chatProfileSaving || !chatAvatarUrl.trim()" class="rounded-lg bg-primary text-primary-foreground px-3 text-xs font-medium hover:bg-primary/90 disabled:opacity-50 shrink-0">应用</button>
            </div>
            <p v-if="chatProfileError" class="text-xs text-destructive bg-destructive/5 rounded-lg px-3 py-2">{{ chatProfileError }}</p>
            <p v-if="chatProfileSuccess && chatProfileTab === 'avatar'" class="text-xs text-green-600 dark:text-green-400 bg-green-500/5 rounded-lg px-3 py-2">{{ chatProfileSuccess }}</p>
            <button @click="chatProfileTab = 'info'" class="w-full rounded-lg border border-border py-2 text-sm hover:bg-muted transition-colors">返回资料编辑</button>
          </div>

          <!-- Info tab -->
          <div v-else class="space-y-3">
            <div class="space-y-1"><label class="text-xs font-medium text-muted-foreground">用户名</label><input :value="auth.user?.username" disabled class="h-9 w-full rounded-lg border border-input bg-muted/50 px-3 text-sm text-muted-foreground" /></div>
            <div class="space-y-1"><label class="text-xs font-medium text-muted-foreground">显示名称</label><input v-model="chatDisplayName" class="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
            <div class="space-y-1"><label class="text-xs font-medium text-muted-foreground">电话</label><input v-model="chatPhone" class="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
            <div class="space-y-1"><label class="text-xs font-medium text-muted-foreground">新密码（留空不修改）</label><div class="flex gap-1"><input v-model="chatNewPassword" type="text" placeholder="留空则不修改" class="flex-1 h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /><button @click="chatNewPassword = generatePassword(); chatNewPassword2 = ''" class="h-9 rounded-lg border border-input bg-background px-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted shrink-0">生成</button></div></div>
            <div v-if="chatNewPassword" class="flex flex-wrap gap-1.5">
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="chatPwHasLower ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="chatPwHasLower" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>小写</span>
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="chatPwHasUpper ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="chatPwHasUpper" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>大写</span>
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="chatPwHasDigit ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="chatPwHasDigit" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>数字</span>
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="chatPwHasSpecial ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="chatPwHasSpecial" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>特殊字符</span>
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="chatPwLongEnough ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="chatPwLongEnough" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>≥8位</span>
            </div>
            <div class="space-y-1"><label class="text-xs font-medium text-muted-foreground">确认新密码</label><input v-model="chatNewPassword2" type="text" :placeholder="chatNewPassword ? '再次输入新密码' : '留空则不修改'" class="flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            <div v-if="chatNewPassword2" class="flex flex-wrap gap-1.5"><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="chatPw2HasLower ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="chatPw2HasLower" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>小写</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="chatPw2HasUpper ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="chatPw2HasUpper" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>大写</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="chatPw2HasDigit ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="chatPw2HasDigit" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>数字</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="chatPw2HasSpecial ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="chatPw2HasSpecial" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>特殊字符</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="chatPw2LongEnough ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="chatPw2LongEnough" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>≥8位</span></div></div>
            <button @click="chatProfileTab = 'avatar'" class="w-full rounded-lg border border-border py-2 text-sm hover:bg-muted transition-colors">修改头像</button>
            <p v-if="chatProfileError" class="text-xs text-destructive bg-destructive/5 rounded-lg px-3 py-2">{{ chatProfileError }}</p>
            <p v-if="chatProfileSuccess && chatProfileTab === 'info'" class="text-xs text-green-600 dark:text-green-400 bg-green-500/5 rounded-lg px-3 py-2">{{ chatProfileSuccess }}</p>
            <button @click="saveChatProfile" :disabled="chatProfileSaving" class="w-full rounded-lg bg-primary text-primary-foreground py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors">{{ chatProfileSaving ? '保存中...' : '保存资料' }}</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
