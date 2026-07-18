<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const showOverlay = ref(false)

async function handleSubmit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    showOverlay.value = true
    await new Promise(r => setTimeout(r, 600))
    if (auth.isAdmin) {
      router.push('/admin')
    } else {
      router.push('/')
    }
  } catch (err: any) {
    error.value = err.message || '登录失败'
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-background p-4 relative overflow-hidden">
    <!-- Success overlay -->
    <div v-if="showOverlay" class="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm animate-fade-in">
      <div class="flex flex-col items-center gap-3">
        <svg class="animate-scale-in text-green-500" xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        <p class="text-sm text-foreground animate-fade-in-up">登录成功</p>
      </div>
    </div>

    <div class="w-full max-w-sm space-y-6" :class="showOverlay ? 'animate-fade-out' : 'animate-fade-in-up'">
      <div class="text-center space-y-2">
        <div class="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mx-auto animate-scale-in">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary">
            <path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4Z" />
            <path d="M16 14H8a4 4 0 0 0-4 4v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1a4 4 0 0 0-4-4Z" />
          </svg>
        </div>
        <h1 class="text-xl font-semibold">企业 AI 知识助手</h1>
        <p class="text-sm text-muted-foreground">登录你的账号</p>
      </div>

      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div class="space-y-2 transition-all duration-200 focus-within:translate-x-1" :class="{ 'animate-shake': !!error }">
          <label class="text-sm font-medium">用户名</label>
          <input v-model="username" required class="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:-translate-y-0.5" :class="{ 'border-destructive/50': !!error }" placeholder="输入用户名" />
        </div>
        <div class="space-y-2 transition-all duration-200 focus-within:translate-x-1" :class="{ 'animate-shake': !!error }">
          <label class="text-sm font-medium">密码</label>
          <input v-model="password" type="password" required class="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:-translate-y-0.5" :class="{ 'border-destructive/50': !!error }" placeholder="输入密码" />
        </div>

        <p v-if="error" :key="error" class="text-sm text-destructive animate-slide-in-right">{{ error }}</p>

        <button type="submit" :disabled="loading" class="w-full h-10 rounded-lg bg-primary text-primary-foreground font-medium text-sm hover:bg-primary/90 active:scale-[0.98] transition-all duration-150 disabled:opacity-50 disabled:active:scale-100 inline-flex items-center justify-center gap-2">
          <svg v-if="loading" class="animate-spin-slow" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>

      <div class="text-center space-y-1">
        <p class="text-xs text-muted-foreground">员工用员工账号登录 · 管理员用管理员账号登录</p>
        <p class="text-[10px] text-muted-foreground/50">默认管理员: admin / admin123</p>
      </div>
    </div>
  </div>
</template>
