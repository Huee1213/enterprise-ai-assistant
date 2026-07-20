import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '@/api/client'
import router from '@/router'

export interface User {
  id: string
  username: string
  role: string
  display_name: string
  created_at: string
  employee_id?: string | null
  avatar_url?: string
  phone?: string
  is_online?: boolean
  is_super_admin?: boolean
  permissions?: string[]
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<User | null>(null)
  const showLogoutOverlay = ref(false)

  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin' || user.value?.role === 'super_admin')
  const isSuperAdmin = computed(() => user.value?.role === 'super_admin')
  const permissions = computed(() => user.value?.permissions ?? [])

  function hasPermission(perm: string) {
    return isSuperAdmin.value || permissions.value.includes(perm)
  }

  function hasAnyPermission(perms: string[]) {
    if (isSuperAdmin.value) return true
    return perms.some(p => permissions.value.includes(p))
  }

  function hasGroupPermission(group: string) {
    // e.g. group="documents" matches any "documents.*" permission
    if (isSuperAdmin.value) return true
    return permissions.value.some(p => p.startsWith(`${group}.`))
  }

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

  async function forceLogin(username: string, password: string) {
    const { data } = await apiClient.post('/auth/force-login', { username, password })
    setAuth(data.access_token, data.user)
    return data
  }

  async function register(username: string, password: string, display_name?: string) {
    const { data } = await apiClient.post('/auth/register', { username, password, display_name })
    setAuth(data.access_token, data.user)
    return data
  }

  let _fetchPromise: Promise<void> | null = null

  async function fetchMe() {
    if (!token.value) return
    if (_fetchPromise) return _fetchPromise
    _fetchPromise = (async () => {
      try {
        const { data } = await apiClient.get('/auth/me')
        user.value = data
      } catch {
        clearAuth()
      }
    })()
    await _fetchPromise
    _fetchPromise = null
  }

  async function updateProfile(updates: Partial<User>) {
    const { data } = await apiClient.put(`/auth/users/${user.value!.id}`, updates)
    if (user.value) Object.assign(user.value, updates)
    return data
  }

  async function updateSelfProfile(updates: { display_name?: string; password?: string; avatar_url?: string; phone?: string }) {
    const { data } = await apiClient.put('/auth/profile', updates)
    user.value = data
    return data
  }

  async function uploadAvatar(file: File) {
    const form = new FormData()
    form.append('file', file)
    const { data } = await apiClient.post('/auth/avatar', form)
    if (data.url && user.value) user.value.avatar_url = data.url
    return data
  }

  async function logout() {
    showLogoutOverlay.value = true
    await new Promise(r => setTimeout(r, 400))
    try { await apiClient.post('/auth/logout') } catch {}
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
    token, user, isLoggedIn, isAdmin, isSuperAdmin, permissions,
    hasPermission, hasAnyPermission, hasGroupPermission,
    showLogoutOverlay, login, forceLogin, register, logout, fetchMe, init, clearAuth, updateProfile,
    updateSelfProfile, uploadAvatar,
  }
})
