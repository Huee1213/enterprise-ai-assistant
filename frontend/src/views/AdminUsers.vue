<script setup lang="ts">
import { ref, onMounted } from 'vue'
import apiClient from '@/api/client'

interface UserInfo {
  id: string
  username: string
  role: string
  display_name: string
  created_at: string
}

const users = ref<UserInfo[]>([])
const loading = ref(true)
const error = ref('')

const showCreate = ref(false)
const newUsername = ref('')
const newPassword = ref('')
const newDisplayName = ref('')
const createError = ref('')
const creating = ref(false)

async function fetchUsers() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await apiClient.get('/auth/users')
    users.value = data
  } catch (err: any) {
    error.value = err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  createError.value = ''
  if (!newUsername.value.trim() || newPassword.value.length < 4) {
    createError.value = '用户名不能为空，密码至少4位'
    return
  }
  creating.value = true
  try {
    await apiClient.post('/auth/register', {
      username: newUsername.value.trim(),
      password: newPassword.value,
      display_name: newDisplayName.value.trim() || newUsername.value.trim(),
    })
    showCreate.value = false
    newUsername.value = ''
    newPassword.value = ''
    newDisplayName.value = ''
    await fetchUsers()
  } catch (err: any) {
    createError.value = err.message || '创建失败'
  } finally {
    creating.value = false
  }
}

async function handleDelete(id: string) {
  if (!confirm('确定删除此用户？')) return
  try {
    await apiClient.delete(`/auth/users/${id}`)
    await fetchUsers()
  } catch (err: any) {
    error.value = err.message || '删除失败'
  }
}

onMounted(fetchUsers)
</script>

<template>
  <div class="h-full overflow-y-auto p-6 space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold">用户管理</h1>
        <p class="text-sm text-muted-foreground mt-0.5">管理系统中的员工账号</p>
      </div>
      <button
        @click="showCreate = !showCreate"
        class="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-2 text-sm font-medium hover:bg-primary/90 transition-colors"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
        添加用户
      </button>
    </div>

    <!-- Create user form -->
    <div v-if="showCreate" class="rounded-xl border border-border bg-card p-5">
      <h3 class="text-sm font-semibold mb-4">新建员工账号</h3>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
        <input v-model="newUsername" placeholder="用户名 *" class="h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
        <input v-model="newPassword" type="password" placeholder="密码 *（至少4位）" class="h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
        <input v-model="newDisplayName" placeholder="显示名称" class="h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
      </div>
      <p v-if="createError" class="text-xs text-destructive mb-2">{{ createError }}</p>
      <div class="flex gap-2">
        <button @click="handleCreate" :disabled="creating" class="rounded-lg bg-primary text-primary-foreground px-4 py-1.5 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50">
          {{ creating ? '创建中...' : '创建' }}
        </button>
        <button @click="showCreate = false" class="rounded-lg border border-border px-4 py-1.5 text-sm hover:bg-muted transition-colors">取消</button>
      </div>
    </div>

    <!-- Error -->
    <p v-if="error" class="text-sm text-destructive">{{ error }}</p>

    <!-- Table -->
    <div v-if="!loading" class="rounded-xl border border-border bg-card overflow-hidden">
      <div v-if="users.length === 0" class="text-center text-muted-foreground text-sm py-12">
        暂无用户，点击上方「添加用户」创建员工账号
      </div>
      <table v-else class="w-full text-sm">
        <thead class="bg-muted/30">
          <tr class="border-b border-border">
            <th class="text-left px-4 py-3 font-medium text-muted-foreground text-xs">用户名</th>
            <th class="text-left px-4 py-3 font-medium text-muted-foreground text-xs">显示名称</th>
            <th class="text-left px-4 py-3 font-medium text-muted-foreground text-xs">角色</th>
            <th class="text-left px-4 py-3 font-medium text-muted-foreground text-xs">创建时间</th>
            <th class="text-right px-4 py-3 font-medium text-muted-foreground text-xs">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(u, idx) in users" :key="u.id" class="border-b border-border last:border-0 hover:bg-muted/20 animate-fade-in" :style="{ animationDelay: `${idx * 0.03}s` }">
            <td class="px-4 py-3">{{ u.username }}</td>
            <td class="px-4 py-3 text-muted-foreground">{{ u.display_name }}</td>
            <td class="px-4 py-3">
              <span class="text-xs px-2 py-0.5 rounded-full font-medium" :class="u.role === 'admin' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'">
                {{ u.role === 'admin' ? '管理员' : '员工' }}
              </span>
            </td>
            <td class="px-4 py-3 text-muted-foreground text-xs">{{ new Date(u.created_at).toLocaleString() }}</td>
            <td class="px-4 py-3 text-right">
              <button v-if="u.role !== 'admin'" @click="handleDelete(u.id)" class="text-xs text-destructive hover:underline">删除</button>
              <span v-else class="text-xs text-muted-foreground/40">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="text-center text-sm text-muted-foreground py-12">加载中...</div>
  </div>
</template>
