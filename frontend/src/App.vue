<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import { onStaleSession } from '@/api/client'

const theme = useThemeStore()
const auth = useAuthStore()
const router = useRouter()

const showStaleDialog = ref(false)
const staleMessage = ref('')
let unsubStale: (() => void) | null = null

onStaleSession(() => {
  staleMessage.value = '该账户已在别处登录，请重新登录'
  showStaleDialog.value = true
})

function onStaleConfirm() {
  showStaleDialog.value = false
  auth.clearAuth()
  router.push('/login')
}

onMounted(async () => {
  theme.init()
  await auth.init()
})

onUnmounted(() => {
  if (unsubStale) unsubStale()
})
</script>

<template>
  <!-- Stale session dialog -->
  <Transition name="dialog">
    <div v-if="showStaleDialog" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4" @click="onStaleConfirm">
      <div class="bg-card border border-border rounded-xl w-full max-w-sm shadow-2xl dialog-pop overflow-hidden" @click.stop>
        <div class="px-5 py-4 border-b border-border flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg bg-destructive/10 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-destructive"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          </div>
          <div><h2 class="text-sm font-semibold">会话已失效</h2><p class="text-xs text-muted-foreground">{{ staleMessage }}</p></div>
        </div>
        <div class="px-5 py-4 text-xs text-muted-foreground">你的账号已在其他设备登录，当前会话已过期，请重新登录。</div>
        <div class="px-5 py-4 border-t border-border flex justify-end">
          <button @click="onStaleConfirm" class="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-xs font-medium hover:bg-primary/90 transition-colors">重新登录</button>
        </div>
      </div>
    </div>
  </Transition>

  <!-- Logout overlay -->
  <Transition name="dialog">
    <div v-if="auth.showLogoutOverlay" class="fixed inset-0 z-[9999] flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div class="flex flex-col items-center gap-3 dialog-pop">
        <svg class="animate-spin-slow text-muted-foreground" xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>
        <p class="text-sm text-muted-foreground">正在退出...</p>
      </div>
    </div>
  </Transition>

  <!-- Router view with grid-stacked concurrent fade (no overlay, no height collapse) -->
  <div class="min-h-screen bg-background text-foreground route-view">
    <router-view v-slot="{ Component }">
      <transition name="route-fade">
        <component :is="Component" />
      </transition>
    </router-view>
  </div>
</template>
