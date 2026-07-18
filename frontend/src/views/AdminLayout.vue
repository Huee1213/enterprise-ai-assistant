<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useHealthStore } from '@/stores/health'

const auth = useAuthStore()
const theme = useThemeStore()
const health = useHealthStore()

function dotColor(status: string): string {
  if (status.startsWith('connected') || status.startsWith('configured')) return 'bg-green-500'
  return 'bg-red-500'
}

onMounted(() => health.startAutoRefresh())
onUnmounted(() => health.stopAutoRefresh())
</script>

<template>
  <div class="flex h-screen bg-background">
    <aside class="w-56 bg-sidebar border-r border-border flex flex-col shrink-0">
      <div class="p-4 border-b border-border">
        <div class="flex items-center gap-2.5 mb-1">
          <div class="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary">
              <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
            </svg>
          </div>
          <div>
            <span class="font-semibold text-sm">管理后台</span>
            <p class="text-[10px] text-muted-foreground/60 leading-none mt-0.5">{{ auth.user?.display_name }}</p>
          </div>
        </div>
      </div>

      <nav class="flex-1 p-2 space-y-0.5 overflow-y-auto">
        <div class="animate-slide-in" style="animation-delay: 0s">
          <p class="text-[10px] font-medium text-muted-foreground/50 uppercase tracking-wider px-3 pt-3 pb-1">系统管理</p>
          <router-link to="/admin" class="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors hover:bg-sidebar-muted" :class="$route.path === '/admin' ? 'bg-sidebar-muted font-medium text-sidebar-foreground' : 'text-sidebar-foreground/80'">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /></svg>
            总览
          </router-link>
        </div>

        <div class="animate-slide-in" style="animation-delay: 0.05s">
          <p class="text-[10px] font-medium text-muted-foreground/50 uppercase tracking-wider px-3 pt-3 pb-1">知识库</p>
          <router-link to="/admin/documents" class="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors hover:bg-sidebar-muted" :class="$route.path === '/admin/documents' ? 'bg-sidebar-muted font-medium text-sidebar-foreground' : 'text-sidebar-foreground/80'">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
            文档管理
          </router-link>
        </div>

        <div class="animate-slide-in" style="animation-delay: 0.1s">
          <p class="text-[10px] font-medium text-muted-foreground/50 uppercase tracking-wider px-3 pt-3 pb-1">用户</p>
          <router-link to="/admin/users" class="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors hover:bg-sidebar-muted" :class="$route.path === '/admin/users' ? 'bg-sidebar-muted font-medium text-sidebar-foreground' : 'text-sidebar-foreground/80'">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            用户管理
          </router-link>
        </div>

      </nav>

      <!-- Footer: per-service status dots -->
      <div class="border-t border-border shrink-0">
        <div class="px-3 py-2">
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
          <div class="flex items-center justify-between mt-1.5 pt-1.5 border-t border-border/40">
            <router-link to="/" class="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-sidebar-muted transition-colors" title="返回对话">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
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
      </div>
    </aside>

    <main class="flex-1 overflow-hidden">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>
