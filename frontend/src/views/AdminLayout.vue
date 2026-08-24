<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useHealthStore } from '@/stores/health'
import ProfileEditor from '@/components/common/ProfileEditor.vue'

const auth = useAuthStore()
const theme = useThemeStore()
const health = useHealthStore()
const mobileSidebarOpen = ref(false)
const sidebarCollapsed = ref(false)
const profileEditorRef = ref<InstanceType<typeof ProfileEditor> | null>(null)

function openProfileEditor() {
  profileEditorRef.value?.open()
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
            <div @click="openProfileEditor" class="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 overflow-hidden cursor-pointer hover:ring-2 hover:ring-primary/30 transition-all" title="编辑个人资料">
              <img v-if="auth.user?.avatar_url" :src="auth.user.avatar_url" class="w-full h-full object-cover" @error="$event.target.style.display='none'" />
              <span v-else class="text-xs font-bold text-primary">{{ (auth.user?.display_name || auth.user?.username || '?')[0] }}</span>
            </div>
          <div v-show="!sidebarCollapsed" class="flex-1 min-w-0">
            <span class="font-semibold text-sm">管理后台</span>
            <p class="text-xs text-foreground/80 leading-none mt-0.5 truncate cursor-default font-medium" title="个人资料">{{ auth.user?.display_name || auth.user?.username }}<span class="text-[9px] text-muted-foreground/50 ml-1.5">{{ auth.isSuperAdmin ? '· 系统管理员' : '· 管理员' }}</span></p>
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

        <div v-if="auth.hasPermission('agent.config')" class="animate-slide-in" style="animation-delay: 0.15s">
          <p v-show="!sidebarCollapsed" class="text-[10px] font-medium text-muted-foreground/50 uppercase tracking-wider px-3 pt-3 pb-1">系统</p>
          <router-link @click="mobileSidebarOpen = false" to="/admin/agent" class="flex items-center gap-2.5 rounded-md text-sm transition-colors hover:bg-sidebar-muted" :class="[
            $route.path === '/admin/agent' ? 'bg-sidebar-muted font-medium text-sidebar-foreground' : 'text-sidebar-foreground/80',
            sidebarCollapsed ? 'w-9 h-9 justify-center px-0' : 'px-3 py-2'
          ]" :title="sidebarCollapsed ? '智能体配置' : ''">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="shrink-0"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            <span v-show="!sidebarCollapsed">智能体配置</span>
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

    <main class="flex-1 overflow-y-auto">
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
        <div class="relative">
          <transition name="page">
            <component :is="Component" />
          </transition>
        </div>
      </router-view>
    </main>
  </div>

  <ProfileEditor ref="profileEditorRef" />
</template>
