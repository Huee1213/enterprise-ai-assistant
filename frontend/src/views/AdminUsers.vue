<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import apiClient from '@/api/client'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

function groupBy<T>(arr: T[], key: keyof T): Record<string, T[]> {
  return arr.reduce((acc, item) => {
    const k = String(item[key])
    if (!acc[k]) acc[k] = []
    acc[k].push(item)
    return acc
  }, {} as Record<string, T[]>)
}

interface UserInfo { id: string; username: string; role: string; display_name: string; created_at: string }

const users = ref<UserInfo[]>([])
const loading = ref(true)
const error = ref('')
const searchQuery = ref('')
const roleFilter = ref<'all' | 'admin' | 'employee'>('all')

const filteredUsers = computed(() => {
  let list = users.value
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter(u => u.username.toLowerCase().includes(q) || u.display_name.toLowerCase().includes(q))
  }
  if (roleFilter.value !== 'all') list = list.filter(u => u.role === roleFilter.value)
  return list
})

const showCreate = ref(false)
const newUsername = ref(''), newPassword = ref(''), newDisplayName = ref('')
const createError = ref(''), creating = ref(false)
const confirmDeleteId = ref<string | null>(null)

// Edit dialog (account info only)
const editUser = ref<UserInfo | null>(null)
const editDisplayName = ref(''), editPassword = ref(''), editError = ref(''), showEdit = ref(false)

// Data manager dialog (tabs)
const dmUser = ref<UserInfo | null>(null)
const showDm = ref(false), dmTab = ref<'messages' | 'facts' | 'summaries' | 'stats'>('messages')
const dmSearch = ref(''), dmItems = ref<any[]>([]), dmLoading = ref(false)
const dmTotals = ref({ messages: 0, facts: 0, summaries: 0 })
const dmEditId = ref<number | null>(null), dmEditText = ref('')
const dmSummaries = ref<Record<string, { id: number; summary: string }>>({}) // conv_id → {id, summary}

// Stats in data manager
const dmStats = ref<any>(null)

async function fetchUsers() {
  loading.value = true; error.value = ''
  try { const { data } = await apiClient.get('/auth/users'); users.value = data }
  catch (err: any) { error.value = err.message || '加载失败' }
  finally { loading.value = false }
}

async function handleCreate() {
  createError.value = ''
  if (!newUsername.value.trim() || newPassword.value.length < 4) { createError.value = '用户名不能为空，密码至少4位'; return }
  creating.value = true
  try {
    await apiClient.post('/auth/register', { username: newUsername.value.trim(), password: newPassword.value, display_name: newDisplayName.value.trim() || newUsername.value.trim() })
    showCreate.value = false; newUsername.value = ''; newPassword.value = ''; newDisplayName.value = ''
    await fetchUsers()
  } catch (err: any) { createError.value = err.message || '创建失败' }
  finally { creating.value = false }
}

function confirmDelete(id: string) { confirmDeleteId.value = id }
async function executeDelete() {
  const id = confirmDeleteId.value; confirmDeleteId.value = null
  if (!id) return
  try { await apiClient.delete(`/auth/users/${id}`); await fetchUsers() }
  catch (err: any) { error.value = err.message || '删除失败' }
}
function cancelDelete() { confirmDeleteId.value = null }

// ── Edit dialog ──────────────────────────────────
async function openEdit(user: UserInfo) {
  editUser.value = user; editDisplayName.value = user.display_name; editPassword.value = ''; editError.value = ''; showEdit.value = true
}
function closeEdit() { showEdit.value = false; editUser.value = null }
async function saveEdit() {
  if (!editUser.value) return; editError.value = ''
  try {
    await apiClient.put(`/auth/users/${editUser.value.id}`, { display_name: editDisplayName.value.trim() || editUser.value.username, password: editPassword.value || undefined })
    closeEdit(); await fetchUsers()
  } catch (err: any) { editError.value = err.message || '保存失败' }
}

// ── Data Manager ────────────────────────────────
const dmConvId = ref<string | null>(null) // selected conversation in messages tab

async function openDm(user: UserInfo) {
  dmUser.value = user; showDm.value = true; dmTab.value = 'messages'; dmSearch.value = ''; dmStats.value = null
  dmConvId.value = null; dmItems.value = []; dmSummaries.value = {}
  dmTotals.value = { messages: 0, facts: 0, summaries: 0 }
  await Promise.all([loadDmTab(), loadDmStats(), loadDmCounts()])
}
function closeDm() { showDm.value = false; dmUser.value = null }

async function loadDmCounts() {
  if (!dmUser.value) return
  const uid = dmUser.value.id
  try {
    const [m, f, s] = await Promise.all([
      apiClient.get(`/auth/users/${uid}/messages?limit=1`),
      apiClient.get(`/auth/users/${uid}/facts?limit=1`),
      apiClient.get(`/auth/users/${uid}/summaries?limit=1`),
    ])
    dmTotals.value.messages = m.data.total || 0
    dmTotals.value.facts = f.data.total || 0
    dmTotals.value.summaries = s.data.total || 0
  } catch {}
}

async function loadDmTab() {
  if (!dmUser.value) return
  dmLoading.value = true; dmConvId.value = null
  try {
    let url = ''
    if (dmTab.value === 'messages') {
      url = `/auth/users/${dmUser.value.id}/messages?search=${encodeURIComponent(dmSearch.value)}&limit=200`
      const { data } = await apiClient.get(url)
      dmItems.value = data.items || []
      // Also load summaries for all conversations
      try {
        const sRes = await apiClient.get(`/auth/users/${dmUser.value.id}/summaries?limit=200`)
        const map: Record<string, { id: number; summary: string }> = {}
        for (const s of (sRes.data.items || [])) {
          if (s.conv_id && s.summary) map[s.conv_id] = { id: s.id, summary: s.summary }
        }
        dmSummaries.value = map
      } catch {}
    } else if (dmTab.value === 'facts') {
      url = `/auth/users/${dmUser.value.id}/facts?search=${encodeURIComponent(dmSearch.value)}&limit=50`
      const { data } = await apiClient.get(url); dmItems.value = data.items || []
    } else if (dmTab.value === 'summaries') {
      url = `/auth/users/${dmUser.value.id}/summaries?search=${encodeURIComponent(dmSearch.value)}&limit=200`
      const { data } = await apiClient.get(url)
      dmItems.value = data.items || []
      // Build dmSummaries from the API response directly
      const map: Record<string, { id: number; summary: string }> = {}
      for (const s of (data.items || [])) {
        if (s.conv_id && s.summary) map[s.conv_id] = { id: s.id, summary: s.summary }
      }
      dmSummaries.value = map
    }
  } catch { dmItems.value = [] }
  dmLoading.value = false; dmEditId.value = null
}

async function loadDmSummaries() {
  if (!dmUser.value) return
  try {
    const { data } = await apiClient.get(`/auth/users/${dmUser.value.id}/summaries?limit=200`)
    const map: Record<string, { id: number; summary: string }> = {}
    for (const s of data.items || []) {
      if (s.conv_id && s.summary) map[s.conv_id] = { id: s.id, summary: s.summary }
    }
    dmSummaries.value = map
  } catch {}
}

async function loadDmStats() {
  if (!dmUser.value) return
  try { const { data } = await apiClient.get(`/auth/users/${dmUser.value.id}/stats`); dmStats.value = data }
  catch {}
}

function switchTab(tab: typeof dmTab.value) {
  dmTab.value = tab; dmSearch.value = ''; dmEditId.value = null; dmConvId.value = null
  loadDmTab()
}

function selectConversation(convId: string) { dmConvId.value = convId }

// Group messages by conversation and sort each group by time ascending
const messageGroups = computed(() => {
  const groups = groupBy(dmItems.value, 'conversation_id')
  const entries = Object.entries(groups).map(([id, msgs]) => ({
    id,
    msgs: msgs.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()),
    count: msgs.length,
    latest: new Date(Math.max(...msgs.map(m => new Date(m.timestamp).getTime()))),
  }))
  entries.sort((a, b) => b.latest.getTime() - a.latest.getTime())
  return entries
})

function startEdit(item: any, field: string) {
  dmEditId.value = item.id
  dmEditText.value = item[field] || item.summary || ''
}
function cancelEdit() { dmEditId.value = null }
async function saveEditItem(item: any, field: string, endpoint: string) {
  try { await apiClient.put(endpoint, { [field === 'summary' ? 'summary' : 'content']: dmEditText.value }); dmEditId.value = null; await loadDmTab() }
  catch {}
}
const confirmDeleteItem = ref<{ endpoint: string; label: string } | null>(null)
const confirmBulkDeleteMsgs = ref<number[] | null>(null)
const confirmBulkDeleteConvs = ref<string[] | null>(null)
const confirmClearUserData = ref(false)
const selectMode = ref(false)
const selectedMsgIds = ref<Set<number>>(new Set())
const convSelectMode = ref(false)
const selectedConvIds = ref<Set<string>>(new Set())

function requestDeleteItem(endpoint: string, label: string) { confirmDeleteItem.value = { endpoint, label } }
function cancelDeleteItem() { confirmDeleteItem.value = null }

async function executeDeleteItem() {
  const c = confirmDeleteItem.value; confirmDeleteItem.value = null
  if (!c) return
  try { await apiClient.delete(c.endpoint); await loadDmTab(); await loadDmCounts(); await loadDmStats() }
  catch {}
}

// Conversation-level delete
function toggleConvSelectMode() {
  convSelectMode.value = !convSelectMode.value
  if (!convSelectMode.value) selectedConvIds.value = new Set()
}
function selectAllConvs() {
  selectedConvIds.value = new Set(messageGroups.value.map(g => g.id))
}
function deselectAllConvs() {
  selectedConvIds.value = new Set()
}
function toggleConvSelect(convId: string) {
  const n = new Set(selectedConvIds.value)
  if (n.has(convId)) n.delete(convId); else n.add(convId)
  selectedConvIds.value = n
}
function requestBulkDeleteConvs() {
  if (selectedConvIds.value.size === 0) return
  confirmBulkDeleteConvs.value = Array.from(selectedConvIds.value)
}
function cancelBulkDeleteConvs() { confirmBulkDeleteConvs.value = null }
async function executeBulkDeleteConvs() {
  const ids = confirmBulkDeleteConvs.value; confirmBulkDeleteConvs.value = null
  if (!ids || ids.length === 0) return
  try {
    await apiClient.post(`/auth/users/${dmUser.value!.id}/conversations/bulk-delete`, { conversation_ids: ids })
    selectedConvIds.value = new Set(); convSelectMode.value = false
    await loadDmTab(); await loadDmCounts(); await loadDmStats()
  } catch {}
}

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selectedMsgIds.value = new Set()
}
function selectAllMsgs() {
  const conv = messageGroups.value.find(g => g.id === dmConvId.value)
  if (conv) selectedMsgIds.value = new Set(conv.msgs.map(m => m.id))
}
function deselectAllMsgs() {
  selectedMsgIds.value = new Set()
}
function toggleMsgSelect(id: number) {
  const n = new Set(selectedMsgIds.value)
  if (n.has(id)) n.delete(id); else n.add(id)
  selectedMsgIds.value = n
}
function requestBulkDelete() {
  if (selectedMsgIds.value.size === 0) return
  confirmBulkDeleteMsgs.value = Array.from(selectedMsgIds.value)
}
function cancelBulkDelete() { confirmBulkDeleteMsgs.value = null }
async function executeBulkDelete() {
  const ids = confirmBulkDeleteMsgs.value; confirmBulkDeleteMsgs.value = null
  if (!ids || ids.length === 0) return
  try {
    await apiClient.post(`/auth/users/${dmUser.value!.id}/messages/bulk-delete`, { message_ids: ids })
    selectedMsgIds.value = new Set(); selectMode.value = false
    await loadDmTab(); await loadDmCounts(); await loadDmStats()
  } catch {}
}
function requestClearUserData() { confirmClearUserData.value = true }
async function executeClearUserData() {
  confirmClearUserData.value = false
  try {
    await apiClient.post(`/auth/users/${dmUser.value!.id}/clear-data`)
    await loadDmTab(); await loadDmCounts(); await loadDmStats()
  } catch {}
}

onMounted(fetchUsers)
</script>

<template>
  <div class="h-full overflow-y-auto p-6 space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <div><h1 class="text-xl font-bold">用户管理</h1><p class="text-sm text-muted-foreground mt-0.5">共 {{ users.length }} 个账号</p></div>
      <div class="flex items-center gap-2 flex-wrap">
        <div class="relative flex-1 sm:flex-none min-w-0"><svg class="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
          <input v-model="searchQuery" placeholder="搜索用户..." class="h-9 w-full sm:w-44 rounded-lg border border-input bg-background pl-8 pr-3 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
        <select v-model="roleFilter" class="h-9 rounded-lg border border-input bg-background px-3 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <option value="all">全部角色</option><option value="admin">管理员</option><option value="employee">员工</option></select>
        <button @click="showCreate = !showCreate" class="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-2 text-sm font-medium hover:bg-primary/90 transition-colors whitespace-nowrap"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14"/><path d="M12 5v14"/></svg>添加用户</button>
      </div>
    </div>

    <div v-if="showCreate" class="rounded-xl border border-border bg-card p-5">
      <h3 class="text-sm font-semibold mb-4">新建员工账号</h3>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
        <input v-model="newUsername" placeholder="用户名 *" class="h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
        <input v-model="newPassword" type="password" placeholder="密码 *（至少4位）" class="h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
        <input v-model="newDisplayName" placeholder="显示名称" class="h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
      </div>
      <p v-if="createError" class="text-xs text-destructive mb-2">{{ createError }}</p>
      <div class="flex gap-2">
        <button @click="handleCreate" :disabled="creating" class="rounded-lg bg-primary text-primary-foreground px-4 py-1.5 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50">{{ creating ? '创建中...' : '创建' }}</button>
        <button @click="showCreate = false" class="rounded-lg border border-border px-4 py-1.5 text-sm hover:bg-muted transition-colors">取消</button>
      </div>
    </div>

    <p v-if="error" class="text-sm text-destructive">{{ error }}</p>

    <div v-if="!loading" class="rounded-xl border border-border bg-card overflow-hidden">
      <div v-if="filteredUsers.length === 0" class="text-center text-muted-foreground text-sm py-12">无匹配用户</div>
      <!-- Desktop table + Mobile card list -->
      <template v-else>
        <table class="hidden sm:table w-full text-sm">
          <thead class="bg-muted/30"><tr class="border-b border-border">
            <th class="text-left px-4 py-3 font-medium text-muted-foreground text-xs">用户名</th>
            <th class="text-left px-4 py-3 font-medium text-muted-foreground text-xs">显示名称</th>
            <th class="text-left px-4 py-3 font-medium text-muted-foreground text-xs">角色</th>
            <th class="text-left px-4 py-3 font-medium text-muted-foreground text-xs">创建时间</th>
            <th class="text-right px-4 py-3 font-medium text-muted-foreground text-xs">操作</th>
          </tr></thead>
          <tbody>
            <tr v-for="(u, idx) in filteredUsers" :key="u.id" class="border-b border-border last:border-0 hover:bg-muted/20 animate-fade-in" :style="{ animationDelay: `${idx * 0.02}s` }">
              <td class="px-4 py-3 font-medium">{{ u.username }}</td>
              <td class="px-4 py-3 text-muted-foreground">{{ u.display_name }}</td>
              <td class="px-4 py-3"><span class="text-xs px-2 py-0.5 rounded-full font-medium" :class="u.role === 'admin' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'">{{ u.role === 'admin' ? '管理员' : '员工' }}</span></td>
              <td class="px-4 py-3 text-muted-foreground text-xs">{{ new Date(u.created_at).toLocaleString() }}</td>
              <td class="px-4 py-3 text-right space-x-1">
                <button @click="openDm(u)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>数据</button>
                <button v-if="u.role !== 'admin'" @click="openEdit(u)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>编辑</button>
                <button v-if="u.role !== 'admin'" @click="confirmDelete(u.id)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>删除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="sm:hidden divide-y divide-border">
          <div v-for="(u, idx) in filteredUsers" :key="u.id" class="p-4 animate-fade-in space-y-2" :style="{ animationDelay: `${idx * 0.02}s` }">
            <div class="flex items-center justify-between">
              <span class="font-medium text-sm">{{ u.username }}</span>
              <span class="text-xs px-2 py-0.5 rounded-full font-medium" :class="u.role === 'admin' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'">{{ u.role === 'admin' ? '管理员' : '员工' }}</span>
            </div>
            <p class="text-xs text-muted-foreground">{{ u.display_name }}</p>
            <p class="text-[10px] text-muted-foreground/60">{{ new Date(u.created_at).toLocaleString() }}</p>
            <div class="flex items-center gap-1 pt-1">
              <button @click="openDm(u)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>数据</button>
              <button v-if="u.role !== 'admin'" @click="openEdit(u)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>编辑</button>
              <button v-if="u.role !== 'admin'" @click="confirmDelete(u.id)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>删除</button>
            </div>
          </div>
        </div>
      </template>
    </div>
    <div v-else class="text-center text-sm text-muted-foreground py-12">加载中...</div>

    <ConfirmDialog v-if="confirmDeleteId" title="删除用户" message="确定删除此用户？该用户的所有数据将被清空，不可恢复。" destructive @confirm="executeDelete" @cancel="cancelDelete" />
    <ConfirmDialog v-if="confirmDeleteItem" title="确认删除" :message="`确定删除${confirmDeleteItem.label}？删除后不可恢复。`" destructive @confirm="executeDeleteItem" @cancel="cancelDeleteItem" />
    <ConfirmDialog v-if="confirmBulkDeleteMsgs" :title="`删除 ${confirmBulkDeleteMsgs.length} 条消息`" message="确定删除选中的消息？删除后不可恢复。" destructive @confirm="executeBulkDelete" @cancel="cancelBulkDelete" />
    <ConfirmDialog v-if="confirmBulkDeleteConvs" :title="`删除 ${confirmBulkDeleteConvs.length} 个对话`" message="确定删除选中的对话及其所有消息？删除后不可恢复。" destructive @confirm="executeBulkDeleteConvs" @cancel="cancelBulkDeleteConvs" />
    <ConfirmDialog v-if="confirmClearUserData" title="清空数据" message="确定清空该用户的所有对话记录、记忆事实和摘要？不可恢复。" destructive @confirm="executeClearUserData" @cancel="() => confirmClearUserData = false" />

    <!-- ── Edit dialog (account only) ─────────────── -->
    <Teleport to="body">
      <div v-if="showEdit && editUser" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4" @click="closeEdit">
        <div class="bg-card border border-border rounded-xl w-full max-w-md shadow-xl animate-scale-in overflow-hidden" @click.stop>
          <div class="px-5 py-4 border-b border-border flex items-center justify-between">
            <h2 class="text-sm font-semibold">编辑用户 — {{ editUser.username }}</h2>
            <button @click="closeEdit" class="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>
          </div>
          <div class="p-5 space-y-4">
            <div class="space-y-2"><label class="text-xs font-medium text-muted-foreground">显示名称</label><input v-model="editDisplayName" class="flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
            <div class="space-y-2"><label class="text-xs font-medium text-muted-foreground">新密码（留空不修改）</label><input v-model="editPassword" type="password" placeholder="留空则不修改" class="flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
            <p v-if="editError" class="text-xs text-destructive">{{ editError }}</p>
          </div>
          <div class="px-5 py-4 border-t border-border flex justify-end gap-2">
            <button @click="closeEdit" class="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-muted transition-colors">取消</button>
            <button @click="saveEdit" class="rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-xs hover:bg-primary/90 transition-colors">保存</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Data Manager dialog (tabs) ──────────────── -->
    <Teleport to="body">
      <div v-if="showDm && dmUser" class="fixed inset-0 z-[9999] flex items-start justify-center bg-black/40 backdrop-blur-sm p-4 pt-12 overflow-y-auto" @click="closeDm">
        <div class="bg-card border border-border rounded-xl w-full max-w-2xl shadow-xl animate-scale-in overflow-hidden" @click.stop>
          <div class="px-5 py-4 border-b border-border flex items-center justify-between">
            <h2 class="text-sm font-semibold">数据管理 — {{ dmUser.username }}</h2>
            <button @click="closeDm" class="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>
          </div>

          <!-- Tabs -->
          <div class="flex border-b border-border px-5">
            <button @click="switchTab('messages')" class="px-3 py-2 text-xs font-medium border-b-2 transition-colors" :class="dmTab === 'messages' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'">消息 ({{ dmTotals.messages }})</button>
            <button @click="switchTab('facts')" class="px-3 py-2 text-xs font-medium border-b-2 transition-colors" :class="dmTab === 'facts' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'">记忆事实 ({{ dmTotals.facts }})</button>
            <button @click="switchTab('summaries')" class="px-3 py-2 text-xs font-medium border-b-2 transition-colors" :class="dmTab === 'summaries' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'">摘要 ({{ dmTotals.summaries }})</button>
            <button @click="switchTab('stats')" class="px-3 py-2 text-xs font-medium border-b-2 transition-colors" :class="dmTab === 'stats' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'">统计</button>
          </div>

          <!-- Search bar (for messages/facts/summaries) -->
          <div v-if="dmTab !== 'stats'" class="px-5 pt-3">
            <div class="flex gap-2">
              <input v-model="dmSearch" @keydown.enter="loadDmTab" placeholder="搜索内容..." class="flex-1 h-8 rounded-lg border border-input bg-background px-3 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
              <button @click="loadDmTab" class="rounded-lg bg-primary text-primary-foreground px-3 text-xs hover:bg-primary/90 transition-colors">搜索</button>
            </div>
          </div>

          <!-- Content -->
          <div class="p-5 max-h-[55vh] overflow-y-auto">
            <div v-if="dmLoading" class="text-center py-6 text-xs text-muted-foreground">加载中...</div>

            <!-- Messages tab: conversation list → detail -->
            <div v-else-if="dmTab === 'messages'">
              <div v-if="dmItems.length === 0" class="text-center py-6 text-xs text-muted-foreground">暂无消息</div>
              <!-- Conversation list (with delete + multi-select) -->
              <div v-else-if="!dmConvId" class="space-y-1">
                <div v-if="messageGroups.length > 0" class="flex items-center justify-between mb-1 px-0.5">
                  <span class="text-[10px] text-muted-foreground/50">{{ messageGroups.length }} 个对话</span>
                  <div class="flex items-center gap-1">
                    <button v-if="!convSelectMode" @click="toggleConvSelectMode()" class="text-[10px] text-muted-foreground hover:text-foreground px-1">选择</button>
                    <template v-else>
                      <button @click="toggleConvSelectMode()" class="text-[10px] text-muted-foreground hover:text-foreground px-1">取消</button>
                      <span class="text-[10px] text-muted-foreground/50">{{ selectedConvIds.size }}/{{ messageGroups.length }}</span>
                      <button @click="selectedConvIds.size === messageGroups.length ? deselectAllConvs() : selectAllConvs()" class="text-[10px] text-muted-foreground hover:text-foreground px-1">{{ selectedConvIds.size === messageGroups.length ? '取消全选' : '全选' }}</button>
                      <button v-if="selectedConvIds.size > 0" @click="requestBulkDeleteConvs()" class="text-[10px] text-destructive hover:text-destructive/80 px-1">删除选中</button>
                    </template>
                  </div>
                </div>
                <button
                  v-for="g in messageGroups" :key="g.id"
                  @click="convSelectMode ? toggleConvSelect(g.id) : selectConversation(g.id)"
                  class="w-full text-left rounded-lg border border-border p-2.5 transition-colors flex items-center gap-2"
                  :class="convSelectMode ? (selectedConvIds.has(g.id) ? 'bg-primary/5 border-primary/30' : 'hover:bg-muted/30') : 'hover:bg-muted/30 group'"
                >
                  <input v-if="convSelectMode" type="checkbox" :checked="selectedConvIds.has(g.id)" class="shrink-0" />
                  <div class="flex items-center justify-between gap-2 flex-1 min-w-0">
                    <div class="flex items-center gap-2 min-w-0">
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-muted-foreground shrink-0"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                      <div class="min-w-0">
                        <span class="text-xs font-medium truncate block">{{ g.msgs[0]?.title || g.msgs[0]?.content?.slice(0,80) || '对话' }}</span>
                        <span class="text-[9px] text-muted-foreground/70 truncate block mt-0.5">{{ g.msgs[g.msgs.length-1]?.content?.slice(0,80) || '' }}</span>
                        <span v-if="dmSummaries[g.id]" class="text-[9px] text-muted-foreground/50 truncate block mt-0.5">📝 {{ dmSummaries[g.id].summary }}</span>
                      </div>
                    </div>
                    <div class="text-right shrink-0">
                      <span class="text-[10px] text-muted-foreground block">{{ g.count }} 条</span>
                      <span class="text-[9px] text-muted-foreground/60 block mt-0.5">{{ g.latest.toLocaleDateString() }}</span>
                    </div>
                  </div>
                  <button v-if="!convSelectMode" @click.stop="requestDeleteItem(`/auth/users/${dmUser!.id}/conversations/${g.id}`, '此对话')" class="text-[9px] text-destructive/60 hover:text-destructive opacity-0 group-hover:opacity-100 shrink-0">删除</button>
                </button>
              </div>
              <!-- Conversation detail (with multi-select) -->
              <div v-else class="space-y-2">
                <div class="flex items-center justify-between mb-1">
                  <button @click="dmConvId = null; selectMode = false; selectedMsgIds = new Set()" class="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m15 18-6-6 6-6"/></svg>
                    返回对话列表
                  </button>
                  <div class="flex items-center gap-1">
                    <button v-if="!selectMode" @click="selectMode = true" class="text-[10px] text-muted-foreground hover:text-foreground px-1">选择</button>
                    <template v-else>
                      <button @click="toggleSelectMode()" class="text-[10px] text-muted-foreground hover:text-foreground px-1">取消</button>
                      <span class="text-[10px] text-muted-foreground/50">{{ selectedMsgIds.size }}/{{ messageGroups.find(g => g.id === dmConvId)?.msgs.length || 0 }}</span>
                      <button @click="(selectedMsgIds.size === (messageGroups.find(g => g.id === dmConvId)?.msgs.length || 0)) ? deselectAllMsgs() : selectAllMsgs()" class="text-[10px] text-muted-foreground hover:text-foreground px-1">{{ selectedMsgIds.size === (messageGroups.find(g => g.id === dmConvId)?.msgs.length || 0) ? '取消全选' : '全选' }}</button>
                      <button v-if="selectedMsgIds.size > 0" @click="requestBulkDelete()" class="text-[10px] text-destructive hover:text-destructive/80 px-1">删除选中</button>
                    </template>
                  </div>
                </div>
                <div v-for="m in (messageGroups.find(g => g.id === dmConvId)?.msgs || [])" :key="m.id" class="rounded-lg border border-border p-2.5 flex items-start gap-2">
                  <input v-if="selectMode" type="checkbox" :checked="selectedMsgIds.has(m.id)" @change="toggleMsgSelect(m.id)" class="mt-1 shrink-0" />
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-0.5">
                      <span class="text-[10px] font-mono bg-muted px-1 py-0.5 rounded" :class="m.role === 'user' ? 'text-primary' : 'text-green-600'">{{ m.role === 'user' ? '用户' : 'AI' }}</span>
                      <span class="text-[9px] text-muted-foreground">{{ new Date(m.timestamp).toLocaleString() }}</span>
                      <button v-if="!selectMode" @click="requestDeleteItem(`/auth/users/${dmUser!.id}/messages/${m.id}`, '此消息')" class="ml-auto text-[9px] text-destructive/60 hover:text-destructive opacity-0 hover:opacity-100 transition-opacity">删除</button>
                    </div>
                    <p class="text-xs text-foreground/85 leading-relaxed">{{ m.content }}</p>
                  </div>
                </div>
              </div>
            </div>

            <!-- Facts tab -->
            <div v-else-if="dmTab === 'facts'" class="space-y-2">
              <div v-if="dmItems.length === 0" class="text-center py-6 text-xs text-muted-foreground">暂无记忆事实</div>
              <div v-for="f in dmItems" :key="f.id" class="rounded-lg border border-border p-2.5">
                <div v-if="dmEditId === f.id">
                  <textarea v-model="dmEditText" class="w-full rounded border border-input bg-background p-2 text-xs min-h-[60px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
                  <div class="flex gap-1 mt-1.5 justify-end">
                    <button @click="saveEditItem(f, 'content', `/auth/users/${dmUser!.id}/facts/${f.id}`)" class="rounded bg-primary text-primary-foreground px-2 py-0.5 text-xs">保存</button>
                    <button @click="cancelEdit" class="rounded border border-border px-2 py-0.5 text-xs hover:bg-muted">取消</button>
                  </div>
                </div>
                <template v-else>
                  <div class="flex items-center justify-between gap-2">
                    <span class="text-[10px] text-muted-foreground">{{ new Date(f.timestamp).toLocaleString() }}</span>
                    <div class="flex gap-1 shrink-0">
                      <button @click="startEdit(f, 'content')" class="text-[9px] text-muted-foreground hover:text-foreground px-1">编辑</button>
                      <button @click="requestDeleteItem(`/auth/users/${dmUser!.id}/facts/${f.id}`, '此记忆事实')" class="text-[9px] text-destructive hover:text-destructive/80 px-1">删除</button>
                    </div>
                  </div>
                  <p class="text-xs text-foreground/85 mt-1">{{ f.content }}</p>
                </template>
              </div>
            </div>

            <!-- Summaries tab: conversation list → summary detail -->
            <div v-else-if="dmTab === 'summaries'">
              <div v-if="dmItems.length === 0" class="text-center py-6 text-xs text-muted-foreground">暂无摘要</div>
              <!-- Conversation list (only those with summaries) -->
              <div v-else-if="!dmConvId" class="space-y-1">
                <div class="flex items-center justify-between mb-1 px-0.5">
                  <span class="text-[10px] text-muted-foreground/50">{{ dmItems.length }} 个摘要</span>
                </div>
                <button
                  v-for="(item, idx) in dmItems" :key="item.id || idx"
                  @click="dmConvId = item.conv_id"
                  class="w-full text-left rounded-lg border border-border p-2.5 hover:bg-muted/30 transition-colors group"
                >
                  <div class="flex items-center justify-between gap-2">
                    <div class="flex items-center gap-2 min-w-0">
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-muted-foreground shrink-0"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                      <div class="min-w-0">
                        <span class="text-xs font-medium truncate block">{{ item.title || item.summary?.slice(0,80) || '对话摘要' }}</span>
                        <span class="text-[9px] text-muted-foreground/70 truncate block mt-0.5">📝 {{ item.summary }}</span>
                      </div>
                    </div>
                    <div class="text-right shrink-0">
                      <span class="text-[10px] text-muted-foreground block">摘要</span>
                      <span class="text-[9px] text-muted-foreground/60 block mt-0.5">{{ new Date(item.timestamp).toLocaleDateString() }}</span>
                    </div>
                  </div>
                </button>
              </div>
              <!-- Summary detail -->
              <div v-else class="space-y-2">
                <button @click="dmConvId = null" class="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m15 18-6-6 6-6"/></svg>
                  返回摘要列表
                </button>
                <div v-if="dmSummaries[dmConvId]" class="rounded-lg border border-border p-3">
                  <div class="flex items-center justify-between gap-2 mb-2">
                    <span class="text-[10px] text-muted-foreground font-mono">{{ dmConvId.slice(0,12) }}...</span>
                    <div class="flex gap-1">
                      <button @click="startEdit({ id: dmSummaries[dmConvId].id, summary: dmSummaries[dmConvId].summary }, 'summary')" class="text-[9px] text-muted-foreground hover:text-foreground px-1">编辑</button>
                      <button @click="requestDeleteItem(`/auth/users/${dmUser!.id}/summaries/${dmSummaries[dmConvId].id}`, '此摘要')" class="text-[9px] text-destructive hover:text-destructive/80 px-1">删除</button>
                    </div>
                  </div>
                  <div v-if="dmEditId === dmSummaries[dmConvId].id">
                    <textarea v-model="dmEditText" class="w-full rounded border border-input bg-background p-2 text-xs min-h-[60px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
                    <div class="flex gap-1 mt-1.5 justify-end">
                      <button @click="saveEditItem({ id: dmSummaries[dmConvId].id, summary: dmEditText }, 'summary', `/auth/users/${dmUser!.id}/summaries/${dmSummaries[dmConvId].id}`)" class="rounded bg-primary text-primary-foreground px-2 py-0.5 text-xs">保存</button>
                      <button @click="cancelEdit" class="rounded border border-border px-2 py-0.5 text-xs hover:bg-muted">取消</button>
                    </div>
                  </div>
                  <p v-else class="text-sm text-foreground/85 leading-relaxed">{{ dmSummaries[dmConvId].summary }}</p>
                </div>
              </div>
            </div>

            <!-- Stats tab (view only) -->
            <div v-else-if="dmTab === 'stats'">
              <div v-if="!dmStats" class="text-center py-6 text-xs text-muted-foreground">加载中...</div>
              <div v-else class="space-y-4">
                <div class="grid grid-cols-2 gap-3">
                  <div v-for="key in ['conversations','messages','facts','summaries']" :key="key" class="rounded-lg bg-muted/30 p-3 text-center">
                    <p class="text-2xl font-bold text-foreground">{{ dmStats[key] }}</p>
                    <p class="text-[10px] text-muted-foreground mt-0.5">{{ { conversations:'对话', messages:'消息', facts:'记忆事实', summaries:'摘要' }[key] }}</p>
                  </div>
                </div>
                <button @click="requestClearUserData()" class="w-full rounded-lg border border-destructive/30 text-destructive px-3 py-1.5 text-xs font-medium hover:bg-destructive/10 transition-colors">清空数据</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
