<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useHealthStore } from '@/stores/health'

const auth = useAuthStore()
const theme = useThemeStore()
const health = useHealthStore()
const mobileSidebarOpen = ref(false)
const sidebarCollapsed = ref(false)
const showProfile = ref(false)
const avatarError = ref(false)
const profileTab = ref<'info' | 'avatar'>('info')
const profileUsername = ref(''), profileDisplayName = ref(''), profilePhone = ref('')
const profilePassword = ref(''), profilePassword2 = ref('')
const profileSaving = ref(false), profileError = ref(''), profileSuccess = ref('')
const avatarFileInput = ref<HTMLInputElement | null>(null)
const avatarUploading = ref(false)
const avatarUrl = ref('')

const profilePwHasLower = computed(() => /[a-z]/.test(profilePassword.value))
const profilePwHasUpper = computed(() => /[A-Z]/.test(profilePassword.value))
const profilePwHasDigit = computed(() => /[0-9]/.test(profilePassword.value))
const profilePwHasSpecial = computed(() => /[!@#$%^&*()_+\-=\[\]{};':",.<>\/?\\|]/.test(profilePassword.value))
const profilePwLongEnough = computed(() => profilePassword.value.length >= 8)

const profilePw2HasLower = computed(() => /[a-z]/.test(profilePassword2.value))
const profilePw2HasUpper = computed(() => /[A-Z]/.test(profilePassword2.value))
const profilePw2HasDigit = computed(() => /[0-9]/.test(profilePassword2.value))
const profilePw2HasSpecial = computed(() => /[!@#$%^&*()_+\-=\[\]{};':",.<>\/?\\|]/.test(profilePassword2.value))
const profilePw2LongEnough = computed(() => profilePassword2.value.length >= 8)

function openProfile(tab?: 'info' | 'avatar') {
  profileUsername.value = auth.user?.username || ''
  profileDisplayName.value = auth.user?.display_name || ''
  profilePhone.value = auth.user?.phone || ''
  profilePassword.value = ''; profilePassword2.value = ''
  profileError.value = ''; profileSuccess.value = ''
  avatarUrl.value = auth.user?.avatar_url || ''
  profileTab.value = tab || 'info'
  showProfile.value = true
}

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

async function saveProfile() {
  profileError.value = ''; profileSuccess.value = ''
  if (profilePassword.value && profilePassword.value !== profilePassword2.value) {
    profileError.value = '两次密码输入不一致'; return
  }
  profileSaving.value = true
  try {
    const updates: any = {}
    if (profileDisplayName.value !== auth.user?.display_name) updates.display_name = profileDisplayName.value
    if (profilePhone.value !== (auth.user?.phone || '')) updates.phone = profilePhone.value
    if (profilePassword.value) updates.password = profilePassword.value
    if (Object.keys(updates).length > 0) {
      await auth.updateSelfProfile(updates)
      profileSuccess.value = '资料已更新'
    }
    setTimeout(() => profileSuccess.value = '', 2000)
  } catch (err: any) { profileError.value = err.response?.data?.detail || err.message || '更新失败' }
  finally { profileSaving.value = false }
}

async function uploadAvatarFile(file: File) {
  if (!file.type.startsWith('image/')) { profileError.value = '请选择图片文件'; return }
  avatarUploading.value = true; profileError.value = ''
  try {
    const data = await auth.uploadAvatar(file)
    avatarUrl.value = data.url
    profileSuccess.value = '头像已更新'
    setTimeout(() => profileSuccess.value = '', 2000)
  } catch (err: any) { profileError.value = err.response?.data?.detail || err.message || '上传失败' }
  finally { avatarUploading.value = false }
}

async function saveAvatarUrl() {
  if (!avatarUrl.value.trim()) return
  profileError.value = ''; profileSaving.value = true
  try {
    await auth.updateSelfProfile({ avatar_url: avatarUrl.value.trim() })
    profileSuccess.value = '头像已更新'
    setTimeout(() => profileSuccess.value = '', 2000)
  } catch (err: any) { profileError.value = err.response?.data?.detail || err.message || '更新失败' }
  finally { profileSaving.value = false }
}

function dotColor(status: string): string {
  if (status.startsWith('connected') || status.startsWith('configured')) return 'bg-green-500'
  return 'bg-red-500'
}

onMounted(() => {
  if (auth.isSuperAdmin || auth.hasPermission('dashboard.view') || auth.hasGroupPermission('documents') || auth.hasGroupPermission('users')) {
    health.startAutoRefresh()
  }
})
onUnmounted(() => health.stopAutoRefresh())
</script>

<template>
  <div class="flex h-screen bg-background">
    <!-- Mobile sidebar backdrop -->
    <div v-if="mobileSidebarOpen" class="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm md:hidden" @click="mobileSidebarOpen = false" />

    <!-- Sidebar: fixed on mobile (slide drawer), static/collapsible on desktop -->
    <aside
      class="fixed md:static inset-y-0 left-0 z-40 bg-sidebar border-r border-border flex flex-col shrink-0 transition-all duration-250 ease-out md:translate-x-0"
      :class="[
        mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full',
        sidebarCollapsed ? 'w-14' : 'w-56'
      ]"
    >
      <div class="p-4 border-b border-border" :class="sidebarCollapsed ? 'p-2 flex flex-col items-center' : ''">
          <div class="flex items-center gap-2.5 mb-1" :class="sidebarCollapsed ? 'mb-0 justify-center' : ''">
            <div @click="openProfile('avatar')" class="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 overflow-hidden cursor-pointer hover:ring-2 hover:ring-primary/30 transition-all">
              <img v-if="auth.user?.avatar_url && !avatarError" :src="auth.user.avatar_url" class="w-full h-full object-cover" @error="avatarError = true" />
              <span v-else class="text-xs font-bold text-primary">{{ (auth.user?.display_name || auth.user?.username || '?')[0] }}</span>
            </div>
          <div v-show="!sidebarCollapsed" class="flex-1 min-w-0">
            <span class="font-semibold text-sm">管理后台</span>
            <p @click="openProfile('info')" class="text-xs text-foreground/80 leading-none mt-0.5 truncate hover:text-foreground transition-colors cursor-pointer font-medium">{{ auth.user?.display_name || auth.user?.username }}<span class="text-[9px] text-muted-foreground/50 ml-1.5">{{ auth.isSuperAdmin ? '· 系统管理员' : '· 管理员' }}</span></p>
          </div>
          <button @click="mobileSidebarOpen = false" class="md:hidden rounded-md p-1 text-muted-foreground hover:text-foreground transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>
      </div>

      <nav class="flex-1 p-2 space-y-0.5 overflow-y-auto" :class="sidebarCollapsed ? 'flex flex-col items-center px-1' : ''">
        <div v-if="auth.isSuperAdmin || auth.hasPermission('dashboard.view') || auth.hasGroupPermission('documents') || auth.hasGroupPermission('users')" class="animate-slide-in" style="animation-delay: 0s">
          <p v-show="!sidebarCollapsed" class="text-[10px] font-medium text-muted-foreground/50 uppercase tracking-wider px-3 pt-3 pb-1">系统管理</p>
          <router-link @click="mobileSidebarOpen = false" to="/admin" class="flex items-center gap-2.5 rounded-md text-sm transition-colors hover:bg-sidebar-muted" :class="[
            $route.path === '/admin' ? 'bg-sidebar-muted font-medium text-sidebar-foreground' : 'text-sidebar-foreground/80',
            sidebarCollapsed ? 'w-9 h-9 justify-center px-0' : 'px-3 py-2'
          ]" :title="sidebarCollapsed ? '总览' : ''">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="shrink-0"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /></svg>
            <span v-show="!sidebarCollapsed">总览</span>
          </router-link>
        </div>

        <div v-if="auth.hasGroupPermission('documents')" class="animate-slide-in" style="animation-delay: 0.05s">
          <p v-show="!sidebarCollapsed" class="text-[10px] font-medium text-muted-foreground/50 uppercase tracking-wider px-3 pt-3 pb-1">知识库</p>
          <router-link @click="mobileSidebarOpen = false" to="/admin/documents" class="flex items-center gap-2.5 rounded-md text-sm transition-colors hover:bg-sidebar-muted" :class="[
            $route.path === '/admin/documents' ? 'bg-sidebar-muted font-medium text-sidebar-foreground' : 'text-sidebar-foreground/80',
            sidebarCollapsed ? 'w-9 h-9 justify-center px-0' : 'px-3 py-2'
          ]" :title="sidebarCollapsed ? '文档管理' : ''">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="shrink-0"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
            <span v-show="!sidebarCollapsed">文档管理</span>
          </router-link>
        </div>

        <div v-if="auth.hasGroupPermission('users')" class="animate-slide-in" style="animation-delay: 0.1s">
          <p v-show="!sidebarCollapsed" class="text-[10px] font-medium text-muted-foreground/50 uppercase tracking-wider px-3 pt-3 pb-1">用户</p>
          <router-link @click="mobileSidebarOpen = false" to="/admin/users" class="flex items-center gap-2.5 rounded-md text-sm transition-colors hover:bg-sidebar-muted" :class="[
            $route.path === '/admin/users' ? 'bg-sidebar-muted font-medium text-sidebar-foreground' : 'text-sidebar-foreground/80',
            sidebarCollapsed ? 'w-9 h-9 justify-center px-0' : 'px-3 py-2'
          ]" :title="sidebarCollapsed ? '用户管理' : ''">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="shrink-0"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            <span v-show="!sidebarCollapsed">用户管理</span>
          </router-link>
        </div>
      </nav>

      <!-- Footer: collapse toggle + per-service status dots -->
      <div class="border-t border-border shrink-0">
        <!-- Expanded footer -->
        <div v-show="!sidebarCollapsed" class="px-3 py-2">
          <button
            @click="sidebarCollapsed = !sidebarCollapsed"
            class="hidden md:flex w-full items-center justify-center rounded-md px-2 py-1.5 mb-1 text-xs text-muted-foreground hover:text-foreground hover:bg-sidebar-muted transition-colors"
            title="收起侧栏"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="shrink-0"><polyline points="15 18 9 12 15 6" /></svg>
            <span class="ml-1.5">收起</span>
          </button>
          <div v-if="auth.isSuperAdmin || auth.hasPermission('dashboard.view') || auth.hasGroupPermission('documents') || auth.hasGroupPermission('users')">
            <div v-if="!health.loaded" class="flex items-center gap-2 text-[10px] text-muted-foreground">
              <span class="w-1.5 h-1.5 rounded-full bg-muted-foreground/30 animate-pulse" />
              检测中...
            </div>
            <div v-else class="space-y-1">
              <div v-for="svc in (health.data?.services || [])" :key="svc.name" class="flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full shrink-0" :class="dotColor(svc.status)" />
                <span class="text-[10px] text-muted-foreground flex-1 truncate">{{ svc.name }}</span>
                <span class="text-[9px] text-muted-foreground/50">{{ svc.status.startsWith('connected') || svc.status.startsWith('configured') ? '✓' : '✗' }}</span>
              </div>
            </div>
          </div>
          <div class="flex items-center justify-between mt-1.5 pt-1.5 border-t border-border/40">
            <router-link @click="mobileSidebarOpen = false" to="/" class="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-sidebar-muted transition-colors" title="返回对话">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="shrink-0"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              对话
            </router-link>
            <div class="flex items-center gap-1.5">
              <button @click="theme.toggle()" class="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-sidebar-muted transition-colors" title="切换主题">
                <svg v-if="theme.isDark" xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
              </button>
              <button @click="auth.logout()" class="rounded-md p-1.5 text-muted-foreground hover:text-destructive hover:bg-sidebar-muted transition-colors" title="退出登录">
                <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>
              </button>
            </div>
          </div>
        </div>
        <!-- Collapsed footer -->
        <div v-show="sidebarCollapsed" class="flex flex-col items-center py-1 gap-1">
          <button
            @click="sidebarCollapsed = false"
            class="hidden md:flex items-center justify-center rounded-md w-9 h-9 text-muted-foreground hover:text-foreground hover:bg-sidebar-muted transition-colors"
            title="展开侧栏"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
          </button>
          <div v-if="(auth.isSuperAdmin || auth.hasPermission('dashboard.view') || auth.hasGroupPermission('documents') || auth.hasGroupPermission('users')) && health.loaded" class="flex flex-col items-center gap-1 py-0.5">
            <div v-for="svc in (health.data?.services || [])" :key="svc.name">
              <span class="block w-1.5 h-1.5 rounded-full" :class="dotColor(svc.status)" :title="svc.name" />
            </div>
          </div>
          <router-link @click="mobileSidebarOpen = false" to="/" class="flex items-center justify-center rounded-md w-9 h-9 text-muted-foreground hover:text-foreground hover:bg-sidebar-muted transition-colors" title="对话">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          </router-link>
          <button @click="theme.toggle()" class="flex items-center justify-center rounded-md w-9 h-9 text-muted-foreground hover:text-foreground hover:bg-sidebar-muted transition-colors" title="切换主题">
            <svg v-if="theme.isDark" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
          </button>
          <button @click="auth.logout()" class="flex items-center justify-center rounded-md w-9 h-9 text-muted-foreground hover:text-destructive hover:bg-sidebar-muted transition-colors" title="退出登录">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>
          </button>
        </div>
      </div>
    </aside>

    <main class="flex-1 overflow-hidden">
      <!-- Mobile hamburger button (visible on all admin pages) -->
      <div class="md:hidden fixed top-2 left-2 z-10">
        <button
          @click="mobileSidebarOpen = true"
          class="rounded-md p-2 bg-card border border-border text-muted-foreground hover:text-foreground shadow-sm"
          aria-label="打开菜单"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
        </button>
      </div>

      <!-- No permission warning -->
      <div v-if="!auth.isSuperAdmin && !auth.hasPermission('dashboard.view') && !auth.hasGroupPermission('users') && !auth.hasGroupPermission('documents')" class="flex items-center justify-center h-full p-8">
        <div class="text-center max-w-sm">
          <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="mx-auto mb-4 text-muted-foreground/40"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          <h2 class="text-lg font-semibold mb-2">暂无权限</h2>
          <p class="text-sm text-muted-foreground">你尚未被授予任何管理权限，请联系系统管理员获取相应权限。</p>
        </div>
      </div>
      <router-view v-else v-slot="{ Component }">
        <transition name="page">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>

  <!-- Profile edit dialog -->
  <Teleport to="body">
    <div v-if="showProfile" key="profile" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-fade-in" @click="showProfile = false">
      <div class="bg-card border border-border rounded-xl w-full max-w-md shadow-2xl animate-scale-in overflow-hidden" @click.stop>
        <div class="px-5 py-4 border-b border-border flex items-center justify-between bg-muted/20">
          <div class="flex items-center gap-2.5">
            <div class="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            </div>
            <div><h2 class="text-sm font-semibold">{{ auth.user?.username }}</h2><p class="text-[10px] text-muted-foreground">个人资料</p></div>
          </div>
          <button @click="showProfile = false" class="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>
        </div>
        <div class="p-5 space-y-4 max-h-[70vh] overflow-y-auto">
          <!-- Avatar -->
          <div class="flex flex-col items-center gap-3">
            <div class="relative group">
              <div class="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center text-2xl font-bold text-primary overflow-hidden ring-2 ring-border" @click="profileTab = 'avatar'">
                <img v-if="auth.user?.avatar_url" :src="auth.user.avatar_url" class="w-full h-full object-cover" />
                <span v-else>{{ (auth.user?.display_name || auth.user?.username || '?')[0] }}</span>
              </div>
              <button @click="profileTab = 'avatar'" class="absolute bottom-0 right-0 rounded-full bg-primary text-primary-foreground w-6 h-6 flex items-center justify-center shadow-sm text-xs hover:bg-primary/90 transition-colors">✎</button>
            </div>
          </div>

          <!-- Tab: Info -->
          <div v-if="profileTab === 'info'" class="space-y-3">
            <div class="space-y-1"><label class="text-xs font-medium text-muted-foreground">用户名</label><input :value="profileUsername" disabled class="h-9 w-full rounded-lg border border-input bg-muted/50 px-3 text-sm text-muted-foreground" /></div>
            <div class="space-y-1"><label class="text-xs font-medium text-muted-foreground">工号</label><input :value="auth.user?.employee_id || '—'" disabled class="h-9 w-full rounded-lg border border-input bg-muted/50 px-3 text-sm text-muted-foreground" /></div>
            <div class="space-y-1"><label class="text-xs font-medium text-muted-foreground">显示名称</label><input v-model="profileDisplayName" class="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
            <div class="space-y-1"><label class="text-xs font-medium text-muted-foreground">电话</label><input v-model="profilePhone" class="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
            <div class="space-y-1"><label class="text-xs font-medium text-muted-foreground">新密码（留空不修改）</label><div class="flex gap-1"><input v-model="profilePassword" type="text" placeholder="留空则不修改" class="flex-1 h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /><button @click="profilePassword = generatePassword(); profilePassword2 = ''" class="h-9 rounded-lg border border-input bg-background px-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted shrink-0">生成</button></div></div>
            <div v-if="profilePassword" class="flex flex-wrap gap-1.5"><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="profilePwHasLower ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="profilePwHasLower" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>小写</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="profilePwHasUpper ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="profilePwHasUpper" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>大写</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="profilePwHasDigit ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="profilePwHasDigit" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>数字</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="profilePwHasSpecial ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="profilePwHasSpecial" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>特殊字符</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="profilePwLongEnough ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="profilePwLongEnough" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>≥8位</span></div>
            <div class="space-y-1"><label class="text-xs font-medium text-muted-foreground">确认新密码</label><input v-model="profilePassword2" type="text" :placeholder="profilePassword ? '再次输入新密码' : '留空则不修改'" class="flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            <div v-if="profilePassword2" class="flex flex-wrap gap-1.5"><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="profilePw2HasLower ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="profilePw2HasLower" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>小写</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="profilePw2HasUpper ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="profilePw2HasUpper" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>大写</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="profilePw2HasDigit ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="profilePw2HasDigit" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>数字</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="profilePw2HasSpecial ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="profilePw2HasSpecial" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>特殊字符</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="profilePw2LongEnough ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="profilePw2LongEnough" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>≥8位</span></div></div>
            <p v-if="profileError" class="text-xs text-destructive bg-destructive/5 rounded-lg px-3 py-2">{{ profileError }}</p>
            <p v-if="profileSuccess && profileTab === 'info'" class="text-xs text-green-600 dark:text-green-400 bg-green-500/5 rounded-lg px-3 py-2">{{ profileSuccess }}</p>
            <button @click="saveProfile" :disabled="profileSaving" class="w-full rounded-lg bg-primary text-primary-foreground py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors">{{ profileSaving ? '保存中...' : '保存资料' }}</button>
          </div>

          <!-- Tab: Avatar -->
          <div v-else class="space-y-3">
            <p class="text-xs font-medium text-muted-foreground">上传头像</p>
            <div class="border-2 border-dashed rounded-xl p-6 text-center cursor-pointer hover:border-primary/50 hover:bg-muted/30 transition-colors" @click="avatarFileInput?.click()">
              <input ref="avatarFileInput" type="file" accept="image/*" class="hidden" @change="avatarFileInput?.files?.[0] && uploadAvatarFile(avatarFileInput.files[0])" />
              <svg v-if="!avatarUploading" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="mx-auto mb-1 text-muted-foreground"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
              <div v-else class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-1" />
              <p class="text-xs text-muted-foreground">{{ avatarUploading ? '上传中...' : '点击选择图片文件' }}</p>
            </div>
            <div class="relative"><div class="absolute inset-0 flex items-center"><div class="w-full border-t border-border" /></div><div class="relative flex justify-center"><span class="bg-card px-2 text-[10px] text-muted-foreground">或使用在线链接</span></div></div>
            <div class="flex gap-2">
              <input v-model="avatarUrl" placeholder="https://example.com/avatar.png" class="flex-1 h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
              <button @click="saveAvatarUrl" :disabled="profileSaving || !avatarUrl.trim()" class="rounded-lg bg-primary text-primary-foreground px-3 text-xs font-medium hover:bg-primary/90 disabled:opacity-50 shrink-0">应用</button>
            </div>
            <div v-if="avatarUrl" class="flex items-center gap-2 text-xs text-muted-foreground">
              <span>预览:</span>
              <img :src="avatarUrl" class="w-8 h-8 rounded-full object-cover ring-1 ring-border" @error="$event.target.style.display='none'" />
            </div>
            <p v-if="profileError && profileTab === 'avatar'" class="text-xs text-destructive bg-destructive/5 rounded-lg px-3 py-2">{{ profileError }}</p>
            <p v-if="profileSuccess && profileTab === 'avatar'" class="text-xs text-green-600 dark:text-green-400 bg-green-500/5 rounded-lg px-3 py-2">{{ profileSuccess }}</p>
            <button @click="profileTab = 'info'" class="w-full rounded-lg border border-border py-2 text-sm hover:bg-muted transition-colors">返回资料编辑</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
