<script setup lang="ts">
import { onMounted } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'

const theme = useThemeStore()
const auth = useAuthStore()

onMounted(async () => {
  theme.init()
  await auth.init()
})
</script>

<template>
  <!-- Logout overlay -->
  <div v-if="auth.showLogoutOverlay" class="fixed inset-0 z-[9999] flex items-center justify-center bg-background/80 backdrop-blur-sm animate-fade-in">
    <div class="flex flex-col items-center gap-3">
      <svg class="animate-spin-slow text-muted-foreground" xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>
      <p class="text-sm text-muted-foreground animate-fade-in-up">正在退出...</p>
    </div>
  </div>

  <router-view v-slot="{ Component }">
    <transition name="page" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>
