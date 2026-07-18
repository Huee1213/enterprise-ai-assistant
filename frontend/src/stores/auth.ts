import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '@/api/client'
import router from '@/router'

interface User {
  id: string
  username: string
  role: string
  display_name: string
  created_at: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<User | null>(null)
  const showLogoutOverlay = ref(false)

  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  function setAuth(t: string, u: User) {
    token.value = t
    user.value = u
    localStorage.setItem('token', t)
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${t}`
  }

  function clearAuth() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    delete apiClient.defaults.headers.common['Authorization']
  }

  async function login(username: string, password: string) {
    const { data } = await apiClient.post('/auth/login', { username, password })
    setAuth(data.access_token, data.user)
    return data
  }

  async function register(username: string, password: string, display_name?: string) {
    const { data } = await apiClient.post('/auth/register', { username, password, display_name })
    setAuth(data.access_token, data.user)
    return data
  }

  async function fetchMe() {
    if (!token.value) return
    try {
      const { data } = await apiClient.get('/auth/me')
      user.value = data
    } catch {
      clearAuth()
    }
  }

  async function logout() {
    showLogoutOverlay.value = true
    await new Promise(r => setTimeout(r, 400))
    // Clear chat state before switching user
    const { useChatStore } = await import('@/stores/chat')
    useChatStore().resetConversations()
    clearAuth()
    await router.push('/login')
    showLogoutOverlay.value = false
  }

  async function init() {
    if (token.value) {
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
      await fetchMe()
    }
  }

  return {
    token, user, isLoggedIn, isAdmin,
    showLogoutOverlay, login, register, logout, fetchMe, init, clearAuth,
  }
})
