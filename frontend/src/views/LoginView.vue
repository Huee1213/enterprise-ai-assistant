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
const showPassword = ref(false)

// 409 from login (already logged in elsewhere)
const showReLoginDialog = ref(false)
let pendingLogin = { username: '', password: '' }

async function handleSubmit() {
  error.value = ''
  loading.value = true
  const user = username.value.trim()
  const pass = password.value
  try {
    await auth.login(user, pass)
    showOverlay.value = true
    await new Promise(r => setTimeout(r, 600))
    if (auth.isAdmin) router.push('/admin')
    else router.push('/')
  } catch (err: any) {
    if (err.message?.includes('已在别处登录')) {
      pendingLogin = { username: user, password: pass }
      showReLoginDialog.value = true
    } else {
      error.value = err.message || '登录失败'
    }
    loading.value = false
  }
}

async function confirmReLogin() {
  showReLoginDialog.value = false
  loading.value = true
  try {
    await auth.forceLogin(pendingLogin.username, pendingLogin.password)
    showOverlay.value = true
    await new Promise(r => setTimeout(r, 600))
    if (auth.isAdmin) router.push('/admin')
    else router.push('/')
  } catch (err: any) {
    error.value = err.message || '登录失败'
    loading.value = false
  }
}

function cancelReLogin() {
  showReLoginDialog.value = false
  loading.value = false
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

    <!-- 409: Already logged in elsewhere dialog -->
    <div v-if="showReLoginDialog" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-fade-in" @click="cancelReLogin">
      <div class="bg-card border border-border rounded-xl w-full max-w-sm shadow-2xl animate-scale-in overflow-hidden" @click.stop>
        <div class="px-5 py-4 border-b border-border flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-amber-500"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          </div>
          <div><h2 class="text-sm font-semibold">账号已在别处登录</h2><p class="text-xs text-muted-foreground">该账户当前已在其他设备登录</p></div>
        </div>
        <div class="px-5 py-4 text-xs text-muted-foreground">重新登录将使其他设备下线，是否继续？</div>
        <div class="px-5 py-4 border-t border-border flex justify-end gap-2">
          <button @click="cancelReLogin" class="rounded-lg border border-border px-4 py-2 text-xs font-medium hover:bg-muted transition-colors">取消</button>
          <button @click="confirmReLogin" class="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-xs font-medium hover:bg-primary/90 transition-colors">重新登录</button>
        </div>
      </div>
    </div>

    <!-- Login form -->
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
          <label class="text-sm font-medium">用户名 / 工号</label>
          <input v-model="username" required class="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:-translate-y-0.5" :class="{ 'border-destructive/50': !!error }" placeholder="输入用户名或工号" />
        </div>
        <div class="space-y-2 transition-all duration-200 focus-within:translate-x-1" :class="{ 'animate-shake': !!error }">
          <label class="text-sm font-medium">密码</label>
          <div class="relative">
            <input v-model="password" :type="showPassword ? 'text' : 'password'" required class="flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2 pr-9 text-sm ring-offset-background placeholder:text-muted-foreground transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:-translate-y-0.5" :class="{ 'border-destructive/50': !!error }" placeholder="输入密码" />
            <button type="button" @click="showPassword = !showPassword" class="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground transition-colors" tabindex="-1">
              <svg v-if="showPassword" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
            </button>
          </div>
        </div>

        <p v-if="error" :key="error" class="text-sm text-destructive animate-slide-in-right">{{ error }}</p>

        <button type="submit" :disabled="loading" class="w-full h-10 rounded-lg bg-primary text-primary-foreground font-medium text-sm hover:bg-primary/90 active:scale-[0.98] transition-all duration-150 disabled:opacity-50 disabled:active:scale-100 inline-flex items-center justify-center gap-2">
          <svg v-if="loading" class="animate-spin-slow" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>

      <div class="text-center">
        <p class="text-xs text-muted-foreground">员工使用员工账号登录 · 管理员使用管理员账号登录</p>
      </div>
    </div>
  </div>
</template>
