<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import apiClient from '@/api/client'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { useAuthStore } from '@/stores/auth'
import { isUploadedAvatar, isExternalImageUrl, avatarUrlInputValue } from '@/utils/avatar'
const auth = useAuthStore()

function groupBy<T>(arr: T[], key: keyof T): Record<string, T[]> {
  return arr.reduce((acc, item) => {
    const k = String(item[key])
    if (!acc[k]) acc[k] = []
    acc[k].push(item)
    return acc
  }, {} as Record<string, T[]>)
}

interface UserInfo {
  id: string; username: string; role: string; display_name: string; created_at: string
  employee_id?: string | null; avatar_url?: string; phone?: string; is_online?: boolean
}

const users = ref<UserInfo[]>([])
const loading = ref(true)
const isFetching = ref(false)
const error = ref('')
const searchQuery = ref('')
const activeRoleTab = ref<'employee' | 'admin'>('employee')
const refreshInterval = ref(30)
const editInterval = ref(false)
const newInterval = ref(30)
const lastRefreshTime = ref('')
let refreshTimer: ReturnType<typeof setTimeout> | null = null
let _fetching = false

// Filters
const filterStatus = ref<'all' | 'online' | 'offline'>('all')

// Pagination
const page = ref(1)
const pageSize = ref(15)
const sortBy = ref<'created_at' | 'username' | 'employee_id'>('created_at')
const sortOrder = ref<'asc' | 'desc'>('desc')

const filteredUsers = computed(() => {
  let list = users.value.filter(u => activeRoleTab.value === 'admin' ? (u.role === 'admin' || u.role === 'super_admin') : u.role === activeRoleTab.value)
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter(u =>
      u.username.toLowerCase().includes(q) ||
      u.display_name.toLowerCase().includes(q) ||
      (u.employee_id || '').toLowerCase().includes(q)
    )
  }
  if (filterStatus.value === 'online') list = list.filter(u => u.is_online)
  else if (filterStatus.value === 'offline') list = list.filter(u => !u.is_online)
  // Sort
  list.sort((a, b) => {
    let va: any = a[sortBy.value] || '', vb: any = b[sortBy.value] || ''
    if (sortBy.value === 'created_at') return sortOrder.value === 'desc' ? (new Date(vb).getTime() - new Date(va).getTime()) : (new Date(va).getTime() - new Date(vb).getTime())
    return sortOrder.value === 'desc' ? String(vb).localeCompare(String(va)) : String(va).localeCompare(String(vb))
  })
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredUsers.value.length / pageSize.value)))
const selectableCount = computed(() => filteredUsers.value.filter(u => u.role !== 'super_admin').length)

const pagedUsers = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredUsers.value.slice(start, start + pageSize.value)
})

function goPage(p: number) { page.value = Math.max(1, Math.min(p, totalPages.value)) }

function changePageSize(e: Event) {
  pageSize.value = parseInt((e.target as HTMLSelectElement).value)
  page.value = 1
}

const jumpPageInput = ref('')

function jumpToPage() {
  const p = parseInt(jumpPageInput.value)
  if (p >= 1 && p <= totalPages.value) { page.value = p; jumpPageInput.value = '' }
}

function onFilterChange() { page.value = 1 }

function closeCreateForm() {
  showCreate.value = false
  newUsername.value = ''; newPassword.value = ''; newDisplayName.value = ''; newEmployeeId.value = ''
  newAdminPerms.value = new Set(); createError.value = ''
}

function toggleCreateForm() {
  if (showCreate.value) { closeCreateForm(); return }
  showCreate.value = true
  if (!newEmployeeId.value) generateEmployeeId()
  if (!newPassword.value) newPassword.value = generatePassword()
  if (activeRoleTab.value === 'admin') loadPermBlocks()
}

function resetFormState() {
  showCreate.value = false; showImport.value = false
  newUsername.value = ''; newPassword.value = ''; newDisplayName.value = ''; newEmployeeId.value = ''; createError.value = ''
  importText.value = ''; importResults.value = null; newAdminPerms.value = new Set()
  selectMode.value = false; selectedIds.value = new Set()
  filterStatus.value = 'all'; searchQuery.value = ''; page.value = 1
}

const showCreate = ref(false)
const newUsername = ref(''), newPassword = ref(''), newDisplayName = ref('')
const newEmployeeId = ref('')
const createError = ref(''), creating = ref(false)

function generateEmployeeId() {
  const prefix = activeRoleTab.value === 'admin' ? 'ADM' : 'EMP'
  let s = ''
  for (let i = 0; i < 6; i++) s += Math.floor(Math.random() * 10).toString()
  newEmployeeId.value = `${prefix}-${s}`
}

function generatePassword() {
  const lower = 'abcdefghijklmnopqrstuvwxyz'
  const upper = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
  const digits = '0123456789'
  const special = '!@#$%^&*()_+-=[]{};:,.<>?'
  const pick = (s: string) => s[Math.floor(Math.random() * s.length)]
  let pw = pick(lower) + pick(upper) + pick(digits) + pick(special)
  const all = lower + upper + digits + special
  for (let i = 0; i < 8; i++) pw += pick(all)
  return pw.split('').sort(() => Math.random() - 0.5).join('')
}

function fillGeneratedPassword(target: 'create' | 'import') {
  const pw = generatePassword()
  if (target === 'create') newPassword.value = pw
  else importPassword.value = pw
}

const usernameError = computed(() => {
  const v = newUsername.value.trim()
  if (!v) return ''
  if (v.length < 3) return '用户名至少 3 个字符'
  if (v.length > 50) return '用户名不超过 50 个字符'
  if (!/^[a-zA-Z0-9_-]+$/.test(v)) return '用户名只能包含字母、数字、下划线和连字符'
  return ''
})
const passwordError = computed(() => {
  const v = newPassword.value
  if (!v) return ''
  if (v.length < 8) return '密码至少 8 个字符'
  if (v.length > 128) return '密码不超过 128 个字符'
  if (!/[a-z]/.test(v)) return '密码必须包含小写字母'
  if (!/[A-Z]/.test(v)) return '密码必须包含大写字母'
  if (!/[0-9]/.test(v)) return '密码必须包含数字'
  if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(v)) return '密码必须包含至少一个特殊字符'
  return ''
})
const displayNameError = computed(() => {
  const v = newDisplayName.value.trim()
  if (!v) return ''
  if (v.length > 100) return '显示名称不超过 100 个字符'
  return ''
})
const employeeIdError = computed(() => {
  const v = newEmployeeId.value.trim()
  if (!v) return '工号不能为空'
  if (!/^[A-Za-z0-9][A-Za-z0-9\-]{2,29}$/.test(v)) return '工号 3-30 位，仅含字母、数字、连字符'
  if (/^[-]|[-]$/.test(v)) return '工号不能以连字符开头或结尾'
  return ''
})
const createFormValid = computed(() => {
  return newUsername.value.trim().length >= 3 && /^[a-zA-Z0-9_-]+$/.test(newUsername.value.trim())
    && newPassword.value.length >= 8 && /[a-z]/.test(newPassword.value) && /[A-Z]/.test(newPassword.value) && /[0-9]/.test(newPassword.value) && /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(newPassword.value)
    && newEmployeeId.value.trim().length >= 3 && /^[A-Za-z0-9][A-Za-z0-9\-]{2,29}$/.test(newEmployeeId.value.trim())
})

const pwHasLower = computed(() => /[a-z]/.test(newPassword.value))
const pwHasUpper = computed(() => /[A-Z]/.test(newPassword.value))
const pwHasDigit = computed(() => /[0-9]/.test(newPassword.value))
const pwHasSpecial = computed(() => /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(newPassword.value))
const pwLongEnough = computed(() => newPassword.value.length >= 8)

const editPwHasLower = computed(() => /[a-z]/.test(editData.value.password))
const editPwHasUpper = computed(() => /[A-Z]/.test(editData.value.password))
const editPwHasDigit = computed(() => /[0-9]/.test(editData.value.password))
const editPwHasSpecial = computed(() => /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(editData.value.password))
const editPwLongEnough = computed(() => editData.value.password.length >= 8)

const editPw2HasLower = computed(() => /[a-z]/.test(editData.value.password2))
const editPw2HasUpper = computed(() => /[A-Z]/.test(editData.value.password2))
const editPw2HasDigit = computed(() => /[0-9]/.test(editData.value.password2))
const editPw2HasSpecial = computed(() => /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(editData.value.password2))
const editPw2LongEnough = computed(() => editData.value.password2.length >= 8)

const confirmDeleteId = ref<string | null>(null)
const confirmDeleteIds = ref<string[] | null>(null)

// Batch import
const showImport = ref(false)
const importText = ref('')
const importPassword = ref(generatePassword())
const importResults = ref<any[] | null>(null)
const importing = ref(false)

// Multi-select
const selectedIds = ref<Set<string>>(new Set())
const selectMode = ref(false)

// Edit dialog
const editUser = ref<UserInfo | null>(null)
const editData = ref({ display_name: '', employee_id: '', avatar_url: '', phone: '', password: '', password2: '' })
const editError = ref(''), showEdit = ref(false)

// Data manager dialog (tabs)
const dmUser = ref<UserInfo | null>(null)
const showDm = ref(false), dmTab = ref<'messages' | 'facts' | 'summaries' | 'stats'>('messages')
const dmSearch = ref(''), dmItems = ref<any[]>([]), dmLoading = ref(false)
const dmTotals = ref({ messages: 0, facts: 0, summaries: 0 })
const dmEditId = ref<number | null>(null), dmEditText = ref('')
const dmSummaries = ref<Record<string, { id: number; summary: string }>>({})
const dmStats = ref<any>(null)
const dmConvId = ref<string | null>(null)
const selectModeMsg = ref(false), selectedMsgIds = ref<Set<number>>(new Set())
const convSelectMode = ref(false), selectedConvIds = ref<Set<string>>(new Set())
const confirmDeleteItem = ref<{ endpoint: string; label: string } | null>(null)
const confirmBulkDeleteMsgs = ref<number[] | null>(null)
const confirmBulkDeleteConvs = ref<string[] | null>(null)
const confirmClearUserData = ref(false)

// Admin permissions management
const adminList = ref<any[]>([])
const permEditingAdmin = ref<any | null>(null)
const permSelected = ref<Set<string>>(new Set())
const permSaving = ref(false)
const permError = ref('')
const permBlocks = ref<{ groups: { group: string; label: string; perms: { key: string; label: string }[] }[] }>({ groups: [] })

const flatPerms = computed(() => permBlocks.value.groups.flatMap(g => g.perms))
const newAdminPerms = ref<Set<string>>(new Set())

const permDeps: Record<string, string[]> = {
  'documents.upload': ['documents.view'],
  'documents.delete': ['documents.view'],
  'documents.download': ['documents.view'],
  'users.create': ['users.view'],
  'users.edit': ['users.view'],
  'users.delete': ['users.view'],
  'users.import': ['users.view'],
  'users.view_data': ['users.view'],
}

const childPerms: Record<string, string[]> = {}
for (const [child, parents] of Object.entries(permDeps)) {
  for (const p of parents) {
    if (!childPerms[p]) childPerms[p] = []
    childPerms[p].push(child)
  }
}

function togglePerm(s: Set<string>, key: string) {
  if (s.has(key)) {
    s.delete(key)
    for (const c of (childPerms[key] || [])) s.delete(c)
  } else {
    s.add(key)
    for (const p of (permDeps[key] || [])) s.add(p)
  }
}

function permBlockToggled(key: string) {
  const s = new Set(newAdminPerms.value)
  togglePerm(s, key)
  newAdminPerms.value = s
}

function permDialogToggled(key: string) {
  const s = new Set(permSelected.value)
  togglePerm(s, key)
  permSelected.value = s
}

async function loadPermBlocks() {
  if (permBlocks.value.groups.length === 0) {
    try { const { data } = await apiClient.get('/auth/permissions'); permBlocks.value = data } catch {}
  }
}

function openPermEditor(admin: any) {
  permEditingAdmin.value = admin
  permSelected.value = new Set(admin.permissions || [])
  permError.value = ''
}

async function openPermEditorForUser(u: any) {
  if (permBlocks.value.groups.length === 0) {
    try { const { data } = await apiClient.get('/auth/permissions'); permBlocks.value = data } catch {}
  }
  openPermEditor(u)
}

async function saveAdminPerms() {
  if (!permEditingAdmin.value) return
  permSaving.value = true
  try {
    await apiClient.put(`/auth/admins/${permEditingAdmin.value.id}/permissions`, { permissions: Array.from(permSelected.value) })
    permEditingAdmin.value.permissions = Array.from(permSelected.value)
    permEditingAdmin.value = null
  } catch (err: any) { permError.value = err.response?.data?.detail || err.message || '保存失败' }
  finally { permSaving.value = false }
}

const importFileInput = ref<HTMLInputElement | null>(null)

async function onFileImport(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files?.length) return
  const file = input.files[0]
  const text = await file.text()
  const lines = text.replace(/\r\n/g, '\n').split('\n').map(l => l.trim()).filter(Boolean)
  // Remove CSV header if present
  const first = lines[0]?.toLowerCase()
  if (first && (first.includes('工号') || first.includes('id') || first.includes('employee'))) lines.shift()
  // Append to existing text
  const existing = importText.value.split('\n').map(l => l.trim()).filter(Boolean)
  const merged = [...new Set([...existing, ...lines])]
  importText.value = merged.join('\n')
  input.value = ''
  checkEmployeeIds(lines)
}

// Employee ID check
const employeeIdChecks = ref<Record<string, { registered: boolean }>>({})

async function fetchUsers() {
  if (_fetching) return
  _fetching = true
  isFetching.value = true
  error.value = ''
  try {
    const { data } = await apiClient.get('/auth/users')
    users.value = data
    lastRefreshTime.value = new Date().toLocaleTimeString()
    loading.value = false
  } catch (err: any) {
    if (loading.value) error.value = err.message || '加载失败'
  }
  finally {
    isFetching.value = false
    _fetching = false
    if (refreshTimer !== null && refreshInterval.value > 0) {
      refreshTimer = setTimeout(fetchUsers, refreshInterval.value * 1000)
    }
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  if (refreshInterval.value > 0) {
    refreshTimer = setTimeout(fetchUsers, 0)
  }
}

function stopAutoRefresh() {
  if (refreshTimer !== null) {
    clearTimeout(refreshTimer)
    refreshTimer = null
  }
}

function onRefreshIntervalChange() {
  startAutoRefresh()
}

function applyInterval() {
  const v = Math.max(5, Math.min(300, Math.floor(newInterval.value)))
  newInterval.value = v
  refreshInterval.value = v
  editInterval.value = false
  startAutoRefresh()
}

onMounted(() => {
  if (auth.hasPermission('users.view') || auth.hasPermission('users.create') || auth.hasPermission('users.edit') || auth.hasPermission('users.delete') || auth.hasPermission('users.import') || auth.hasPermission('users.view_data')) {
    loading.value = true; startAutoRefresh()
  } else {
    loading.value = false
  }
})
onUnmounted(stopAutoRefresh)

async function checkEmployeeIds(ids: string[]) {
  if (!ids.length) return
  try {
    const { data } = await apiClient.post('/auth/check-employee-ids', { employee_ids: ids })
    for (const item of data) { employeeIdChecks.value[item.employee_id] = { registered: item.registered } }
  } catch {}
}

function onImportInput() {
  const lines = importText.value.split('\n').map(l => l.trim()).filter(Boolean)
  if (lines.length > 0) checkEmployeeIds(lines)
}

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selectedIds.value = new Set()
}

function toggleSelectAll() {
  const selectable = filteredUsers.value.filter(u => u.role !== 'super_admin')
  if (selectedIds.value.size === selectable.length) selectedIds.value = new Set()
  else selectedIds.value = new Set(selectable.map(u => u.id))
}

function toggleSelect(id: string) {
  const u = users.value.find(x => x.id === id)
  if (u?.role === 'super_admin') return
  const n = new Set(selectedIds.value)
  if (n.has(id)) n.delete(id); else n.add(id)
  selectedIds.value = n
}

function confirmDelete(id: string) { confirmDeleteId.value = id }
async function executeDelete() {
  const id = confirmDeleteId.value; confirmDeleteId.value = null
  if (!id) return
  try { await apiClient.delete(`/auth/users/${id}`); await fetchUsers() }
  catch (err: any) { error.value = err.message || '删除失败' }
}

function confirmBatchDelete() {
  if (selectedIds.value.size === 0) return
  confirmDeleteIds.value = Array.from(selectedIds.value)
}

async function executeBatchDelete() {
  const ids = confirmDeleteIds.value; confirmDeleteIds.value = null
  if (!ids || !ids.length) return
  try {
    await apiClient.post('/auth/batch-delete', { user_ids: ids })
    selectedIds.value = new Set(); selectMode.value = false; await fetchUsers()
  } catch (err: any) { error.value = err.message || '批量删除失败' }
}

function cancelDelete() { confirmDeleteId.value = null; confirmDeleteIds.value = null }

async function executeImport() {
  const ids = importText.value.split('\n').map(l => l.trim()).filter(Boolean)
  if (!ids.length) return
  importing.value = true; importResults.value = null
  try {
    const { data } = await apiClient.post('/auth/batch-import', { employee_ids: ids, default_password: importPassword.value })
    importResults.value = data.results; await fetchUsers()
  } catch (err: any) { error.value = err.message || '导入失败' }
  importing.value = false
}

async function handleCreate() {
  createError.value = ''
  if (!newEmployeeId.value.trim()) generateEmployeeId()
  if (!newPassword.value) newPassword.value = generatePassword()
  if (!createFormValid.value) { createError.value = usernameError.value || passwordError.value || '请检查输入'; return }
  creating.value = true
  try {
    if (activeRoleTab.value === 'admin' && auth.isSuperAdmin) {
      await apiClient.post('/auth/admins', {
        username: newUsername.value.trim(), password: newPassword.value,
        display_name: newDisplayName.value.trim() || newUsername.value.trim(),
        employee_id: newEmployeeId.value.trim(),
        permissions: Array.from(newAdminPerms.value),
      })
      newAdminPerms.value = new Set()
    } else {
      await apiClient.post('/auth/register', {
        username: newUsername.value.trim(), password: newPassword.value,
        display_name: newDisplayName.value.trim() || newUsername.value.trim(),
        employee_id: newEmployeeId.value.trim(),
      })
    }
    showCreate.value = false; newUsername.value = ''; newPassword.value = ''; newDisplayName.value = ''; newEmployeeId.value = ''; newAdminPerms.value = new Set()
    await fetchUsers()
  } catch (err: any) { createError.value = err.message || '创建失败' }
  finally { creating.value = false }
}

async function openEdit(user: UserInfo) {
  editUser.value = user
  editData.value = { display_name: user.display_name, employee_id: user.employee_id || '', avatar_url: user.avatar_url || '', phone: user.phone || '', password: '', password2: '' }
  editAvatarUrlInput.value = avatarUrlInputValue(user.avatar_url)
  editError.value = ''; showEdit.value = true
}

function closeEdit() { showEdit.value = false; editUser.value = null }

const editAvatarFileInput = ref<HTMLInputElement | null>(null)
const editAvatarUploading = ref(false)
const editAvatarUrlInput = ref('')

async function uploadEditAvatar(file: File) {
  if (!file.type.startsWith('image/')) { editError.value = '请选择图片文件'; return }
  editAvatarUploading.value = true; editError.value = ''
  try {
    const form = new FormData()
    form.append('file', file)
    const { data } = await apiClient.post('/auth/avatar', form)
    editData.value.avatar_url = data.url
    editAvatarUrlInput.value = ''
  } catch (err: any) { editError.value = err.response?.data?.detail || err.message || '上传失败' }
  finally { editAvatarUploading.value = false }
}

async function saveEdit() {
  if (!editUser.value) return; editError.value = ''
  if (editData.value.password && editData.value.password !== editData.value.password2) {
    editError.value = '两次密码输入不一致'; return
  }
  const urlInput = editAvatarUrlInput.value.trim()
  if (urlInput && !isExternalImageUrl(urlInput)) {
    editError.value = '请输入以 http(s):// 开头的图片链接'; return
  }
  const payload: any = { display_name: editData.value.display_name || editUser.value.username }
  if (editData.value.employee_id) payload.employee_id = editData.value.employee_id
  if (urlInput) payload.avatar_url = urlInput
  if (editData.value.phone) payload.phone = editData.value.phone
  if (editData.value.password) payload.password = editData.value.password
  try { await apiClient.put(`/auth/users/${editUser.value.id}`, payload); closeEdit(); await fetchUsers() }
  catch (err: any) { editError.value = err.response?.data?.detail || err.message || '保存失败' }
}

// ── Data Manager ────────────────────────────────
async function openDm(user: UserInfo) {
  dmUser.value = user; showDm.value = true; dmTab.value = 'messages'; dmSearch.value = ''; dmStats.value = null
  dmConvId.value = null; dmItems.value = []; dmSummaries.value = {}
  dmTotals.value = { messages: 0, facts: 0, summaries: 0 }
  await Promise.all([loadDmTab(), loadDmStats(), loadDmCounts()])
}
function closeDm() { showDm.value = false; dmUser.value = null }

async function loadDmCounts() {
  if (!dmUser.value) return
  try {
    const [m, f, s] = await Promise.all([
      apiClient.get(`/auth/users/${dmUser.value.id}/messages?limit=1`),
      apiClient.get(`/auth/users/${dmUser.value.id}/facts?limit=1`),
      apiClient.get(`/auth/users/${dmUser.value.id}/summaries?limit=1`),
    ])
    dmTotals.value = { messages: m.data.total || 0, facts: f.data.total || 0, summaries: s.data.total || 0 }
  } catch {}
}

async function loadDmTab() {
  if (!dmUser.value) return
  dmLoading.value = true; dmConvId.value = null
  try {
    let data: any
    if (dmTab.value === 'messages') {
      const r = await apiClient.get(`/auth/users/${dmUser.value.id}/messages?search=${encodeURIComponent(dmSearch.value)}&limit=200`)
      data = r.data; dmItems.value = data.items || []
      try { const s = await apiClient.get(`/auth/users/${dmUser.value.id}/summaries?limit=200`)
        const map: Record<string, { id: number; summary: string }> = {}
        for (const x of (s.data.items || [])) { if (x.conv_id && x.summary) map[x.conv_id] = { id: x.id, summary: x.summary } }
        dmSummaries.value = map } catch {}
    } else if (dmTab.value === 'facts') {
      const r = await apiClient.get(`/auth/users/${dmUser.value.id}/facts?search=${encodeURIComponent(dmSearch.value)}&limit=50`)
      data = r.data; dmItems.value = data.items || []
    } else {
      const r = await apiClient.get(`/auth/users/${dmUser.value.id}/summaries?search=${encodeURIComponent(dmSearch.value)}&limit=200`)
      data = r.data; dmItems.value = data.items || []
      const map: Record<string, { id: number; summary: string }> = {}
      for (const x of (data.items || [])) { if (x.conv_id && x.summary) map[x.conv_id] = { id: x.id, summary: x.summary } }
      dmSummaries.value = map
    }
  } catch { dmItems.value = [] }
  dmLoading.value = false; dmEditId.value = null
}

async function loadDmStats() {
  if (!dmUser.value) return
  try { const { data } = await apiClient.get(`/auth/users/${dmUser.value.id}/stats`); dmStats.value = data } catch {}
}

function switchTab(tab: typeof dmTab.value) {
  dmTab.value = tab; dmSearch.value = ''; dmEditId.value = null; dmConvId.value = null; selectedMsgIds.value = new Set(); selectModeMsg.value = false; selectedConvIds.value = new Set(); convSelectMode.value = false; loadDmTab()
}

function selectConversation(convId: string) { dmConvId.value = convId }

const messageGroups = computed(() => {
  const groups = groupBy(dmItems.value, 'conversation_id')
  const entries = Object.entries(groups).map(([id, msgs]) => ({
    id, msgs: msgs.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()),
    count: msgs.length, latest: new Date(Math.max(...msgs.map(m => new Date(m.timestamp).getTime()))),
  }))
  entries.sort((a, b) => b.latest.getTime() - a.latest.getTime())
  return entries
})

const summaryGroups = computed(() => {
  const groups = groupBy(dmItems.value, 'conv_id')
  const entries = Object.entries(groups).map(([convId, items]) => ({
    convId, items: items.sort((a, b) => new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime()),
    count: items.length, latest: new Date(Math.max(...items.map(m => new Date(m.created_at || 0).getTime()))),
    title: items[0]?.title || '',
    firstContent: items[0]?.summary || '',
  }))
  entries.sort((a, b) => b.latest.getTime() - a.latest.getTime())
  return entries
})

function startEdit(item: any, field: string) { dmEditId.value = item.id; dmEditText.value = item[field] || item.summary || '' }
function cancelEdit() { dmEditId.value = null }
async function saveEditItem(item: any, field: string, endpoint: string) {
  try { await apiClient.put(endpoint, { [field === 'summary' ? 'summary' : 'content']: dmEditText.value }); dmEditId.value = null; await loadDmTab() } catch {}
}

function requestDeleteItem(endpoint: string, label: string) { confirmDeleteItem.value = { endpoint, label } }
function cancelDeleteItem() { confirmDeleteItem.value = null }
async function executeDeleteItem() {
  const c = confirmDeleteItem.value; confirmDeleteItem.value = null
  if (!c) return
  try {
    if (c.endpoint.includes('bulk-delete')) {
      await apiClient.post(c.endpoint, { ids: [] })
    } else {
      await apiClient.delete(c.endpoint)
    }
    await loadDmTab(); await loadDmCounts(); await loadDmStats()
  } catch {}
}

function toggleConvSelectMode() { convSelectMode.value = !convSelectMode.value; if (!convSelectMode.value) selectedConvIds.value = new Set() }
function toggleConvSelect(convId: string) { const n = new Set(selectedConvIds.value); if (n.has(convId)) n.delete(convId); else n.add(convId); selectedConvIds.value = n }
function requestBulkDeleteConvs() { if (selectedConvIds.value.size > 0) confirmBulkDeleteConvs.value = Array.from(selectedConvIds.value) }
function cancelBulkDeleteConvs() { confirmBulkDeleteConvs.value = null }
async function executeBulkDeleteConvs() {
  const ids = confirmBulkDeleteConvs.value; confirmBulkDeleteConvs.value = null
  if (!ids || !ids.length) return
  try { await apiClient.post(`/auth/users/${dmUser.value!.id}/conversations/bulk-delete`, { conversation_ids: ids }); selectedConvIds.value = new Set(); convSelectMode.value = false; await loadDmTab(); await loadDmCounts(); await loadDmStats() } catch {}
}

function toggleSelectModeMsg() { selectModeMsg.value = !selectModeMsg.value; if (!selectModeMsg.value) selectedMsgIds.value = new Set() }
function toggleMsgSelect(id: number) { const n = new Set(selectedMsgIds.value); if (n.has(id)) n.delete(id); else n.add(id); selectedMsgIds.value = n }
function requestBulkDeleteMsgs() { if (selectedMsgIds.value.size > 0) confirmBulkDeleteMsgs.value = Array.from(selectedMsgIds.value) }
function cancelBulkDeleteMsgs() { confirmBulkDeleteMsgs.value = null }
async function executeBulkDeleteMsgs() {
  const ids = confirmBulkDeleteMsgs.value; confirmBulkDeleteMsgs.value = null
  if (!ids || !ids.length) return
  try { await apiClient.post(`/auth/users/${dmUser.value!.id}/messages/bulk-delete`, { message_ids: ids }); selectedMsgIds.value = new Set(); selectModeMsg.value = false; await loadDmTab(); await loadDmCounts(); await loadDmStats() } catch {}
}

function requestClearUserData() { confirmClearUserData.value = true }
async function executeClearUserData() {
  confirmClearUserData.value = false
  try { await apiClient.post(`/auth/users/${dmUser.value!.id}/clear-data`); await loadDmTab(); await loadDmCounts(); await loadDmStats() } catch {}
}


</script>

<template>
  <div class="h-full overflow-y-auto p-4 md:p-6 space-y-4 md:space-y-6">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <div><h1 class="text-xl font-bold">用户管理</h1><p class="text-sm text-muted-foreground mt-0.5">共 {{ users.length }} 个账号</p></div>
        <div class="flex items-center gap-1.5 self-end sm:self-auto">
          <!-- Refresh interval control (matching dashboard style) -->
          <div v-if="editInterval" class="flex items-center gap-1">
            <input v-model.number="newInterval" type="number" min="5" max="300" class="w-14 h-7 rounded border border-input bg-background px-2 text-xs text-center focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" />
            <span class="text-[10px] text-muted-foreground">秒</span>
            <button @click="applyInterval" class="text-[10px] px-1.5 py-0.5 rounded bg-primary text-primary-foreground hover:bg-primary/90">确定</button>
            <button @click="editInterval = false" class="text-[10px] px-1.5 py-0.5 rounded hover:bg-muted">取消</button>
          </div>
          <button v-else @click="editInterval = true; newInterval = refreshInterval" class="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-0.5">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            {{ refreshInterval }}s
          </button>
          <!-- Manual refresh -->
          <button @click="fetchUsers()" title="手动刷新" class="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" :disabled="isFetching">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :class="isFetching ? 'animate-spin' : ''"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          </button>
          <span v-if="lastRefreshTime" class="text-[10px] text-muted-foreground/50 whitespace-nowrap">{{ lastRefreshTime }}</span>
        </div>
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <div class="relative flex-1 sm:flex-none min-w-0">
          <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
          <input v-model="searchQuery" placeholder="搜索姓名/工号..." class="h-9 w-full sm:w-44 rounded-lg border border-input bg-background pl-8 pr-3 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
        </div>
        <button @click="toggleSelectMode"
          class="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-colors whitespace-nowrap"
          :class="selectMode ? 'bg-primary/10 text-primary border-primary/30' : 'border-border hover:bg-muted'">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 12l2 2 4-4"/></svg>
          多选
        </button>
        <button v-if="auth.hasPermission('users.import') && activeRoleTab === 'employee'" @click="showImport = !showImport" class="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium hover:bg-muted transition-colors">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>导入工号
        </button>
        <button v-if="auth.hasPermission('users.create')" @click="toggleCreateForm" class="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-2 text-sm font-medium hover:bg-primary/90 transition-colors whitespace-nowrap">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
          添加{{ activeRoleTab === 'employee' ? '员工' : '管理员' }}
        </button>
      </div>
    </div>

    <!-- Role tabs -->
    <div class="flex gap-0 border-b border-border">
      <button @click="activeRoleTab = 'employee'; resetFormState()" class="px-4 py-2 text-sm font-medium border-b-2 transition-colors" :class="activeRoleTab === 'employee' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'">
        员工管理 <span class="text-xs text-muted-foreground/60 ml-1">({{ users.filter(u => u.role === 'employee').length }})</span>
      </button>
      <button v-if="auth.isSuperAdmin" @click="activeRoleTab = 'admin'; resetFormState()" class="px-4 py-2 text-sm font-medium border-b-2 transition-colors" :class="activeRoleTab === 'admin' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'">
        管理员 <span class="text-xs text-muted-foreground/60 ml-1">({{ users.filter(u => u.role === 'admin' || u.role === 'super_admin').length }})</span>
      </button>
    </div>

    <!-- Filter bar -->
    <div v-if="activeRoleTab === 'employee'" class="flex flex-wrap items-center gap-2 text-xs">
      <select v-model="filterStatus" @change="onFilterChange" class="h-8 rounded-lg border border-input bg-background px-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
        <option value="all">全部状态</option><option value="online">在线</option><option value="offline">离线</option>
      </select>
      <select v-model="sortBy" @change="onFilterChange" class="h-8 rounded-lg border border-input bg-background px-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
        <option value="created_at">创建时间</option><option value="username">用户名</option><option value="employee_id">工号</option>
      </select>
      <button @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'; onFilterChange()" class="h-8 rounded-lg border border-input bg-background px-2 hover:bg-muted transition-colors" :title="sortOrder === 'asc' ? '升序' : '降序'">
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :class="sortOrder === 'asc' ? 'rotate-180' : ''"><line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/></svg>
      </button>
    </div>
    <div v-else-if="activeRoleTab === 'admin'" class="flex flex-wrap items-center gap-2 text-xs">
      <select v-model="filterStatus" @change="onFilterChange" class="h-8 rounded-lg border border-input bg-background px-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
        <option value="all">全部状态</option><option value="online">在线</option><option value="offline">离线</option>
      </select>
      <select v-model="sortBy" @change="onFilterChange" class="h-8 rounded-lg border border-input bg-background px-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
        <option value="created_at">创建时间</option><option value="username">用户名</option><option value="employee_id">工号</option>
      </select>
      <button @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'; onFilterChange()" class="h-8 rounded-lg border border-input bg-background px-2 hover:bg-muted transition-colors" :title="sortOrder === 'asc' ? '升序' : '降序'">
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :class="sortOrder === 'asc' ? 'rotate-180' : ''"><line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/></svg>
      </button>
    </div>

    <!-- Batch import -->
    <div v-if="showImport && activeRoleTab === 'employee'" class="rounded-xl border border-border bg-card p-5">
      <h3 class="text-sm font-semibold mb-3">批量导入工号</h3>
      <p class="text-xs text-muted-foreground mb-3">每行一个工号，或上传 .txt / .csv 文件</p>
      <div class="flex items-center gap-2 mb-3">
        <label class="text-xs text-muted-foreground shrink-0">临时密码:</label>
        <input v-model="importPassword" type="text" maxlength="128" placeholder="设置导入用户的初始密码"
          class="flex-1 h-8 rounded-lg border border-input bg-background px-2.5 text-xs font-mono focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" />
        <button @click="fillGeneratedPassword('import')" type="button" title="生成随机密码"
          class="inline-flex items-center gap-1 h-8 rounded-lg border border-input bg-background px-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0">
          <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg>
          生成
        </button>
      </div>
      <div class="flex gap-2 mb-3">
        <input ref="importFileInput" type="file" accept=".txt,.csv" @change="onFileImport" class="block w-full text-xs text-muted-foreground file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-primary file:text-primary-foreground hover:file:bg-primary/90" />
      </div>
      <textarea v-model="importText" @input="onImportInput" placeholder="EMP001\nEMP002\nEMP003" class="w-full h-24 rounded-lg border border-input bg-background p-3 text-sm font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none" />
      <div v-if="importText.trim()" class="mt-2 flex flex-wrap gap-2 text-xs">
        <span v-for="line in importText.split('\n').map(l=>l.trim()).filter(Boolean)" :key="line" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full"
          :class="employeeIdChecks[line]?.registered ? 'bg-destructive/10 text-destructive' : 'bg-green-500/10 text-green-600 dark:text-green-400'">
          <span class="w-1.5 h-1.5 rounded-full" :class="employeeIdChecks[line]?.registered ? 'bg-destructive' : 'bg-green-500'" /> {{ line }}
          <template v-if="employeeIdChecks[line]?.registered">（已注册）</template>
          <template v-else-if="employeeIdChecks[line] !== undefined">（可导入）</template>
          <template v-else><span class="w-2 h-2 rounded-full bg-muted-foreground/30 animate-pulse" /></template>
        </span>
      </div>
      <div class="flex gap-2 mt-3">
        <button @click="executeImport" :disabled="importing || !importText.trim()" class="rounded-lg bg-primary text-primary-foreground px-4 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50">{{ importing ? '导入中...' : '导入' }}</button>
        <button @click="showImport = false; importResults = null; importText = ''" class="rounded-lg border border-border px-4 py-1.5 text-sm hover:bg-muted">取消</button>
      </div>
      <div v-if="importResults" class="mt-3 space-y-1 max-h-32 overflow-y-auto">
        <div v-for="r in importResults" :key="r.employee_id" class="text-xs flex items-center gap-2" :class="r.status === 'created' ? 'text-green-600 dark:text-green-400' : r.status === 'skipped' ? 'text-muted-foreground' : 'text-destructive'">{{ r.employee_id }} — {{ r.status === 'created' ? '已创建' : r.reason || r.status }}</div>
      </div>
    </div>

    <!-- Create user -->
      <div v-if="showCreate" class="rounded-xl border border-border bg-card p-5">
        <h3 class="text-sm font-semibold mb-4">新建{{ activeRoleTab === 'employee' ? '员工' : '管理员' }}账号</h3>
        <div class="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-1">
          <div class="space-y-1">
            <input v-model="newUsername" @input="createError = ''" placeholder="用户名 *" maxlength="50"
              class="h-9 w-full rounded-lg border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors"
              :class="newUsername && usernameError ? 'border-destructive/60 focus-visible:ring-destructive/30' : newUsername && !usernameError ? 'border-green-500/60 focus-visible:ring-green-500/30' : 'border-input'" />
            <p v-if="newUsername && usernameError" class="text-[10px] text-destructive flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              {{ usernameError }}
            </p>
            <p v-else-if="newUsername && !usernameError" class="text-[10px] text-green-600 dark:text-green-400 flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
              用户名格式正确
            </p>
          </div>
          <div class="space-y-1">
            <div class="flex gap-1">
              <input v-model="newEmployeeId" @input="createError = ''" placeholder="工号 *" maxlength="30"
                class="flex-1 h-9 rounded-lg border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors font-mono"
                :class="newEmployeeId && employeeIdError ? 'border-destructive/60 focus-visible:ring-destructive/30' : newEmployeeId && !employeeIdError ? 'border-green-500/60 focus-visible:ring-green-500/30' : 'border-input'" />
              <button @click="generateEmployeeId" type="button" title="生成工号"
                class="inline-flex items-center gap-1 h-9 rounded-lg border border-input bg-background px-2.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg>
                生成
              </button>
            </div>
            <p v-if="newEmployeeId && employeeIdError" class="text-[10px] text-destructive flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              {{ employeeIdError }}
            </p>
            <p v-else-if="newEmployeeId && !employeeIdError" class="text-[10px] text-green-600 dark:text-green-400 flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
              工号格式正确
            </p>
          </div>
          <div class="space-y-1">
            <div class="flex gap-1">
              <input v-model="newPassword" @input="createError = ''" type="text" placeholder="密码 *" maxlength="128"
                class="flex-1 h-9 rounded-lg border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors"
                :class="newPassword && passwordError ? 'border-destructive/60 focus-visible:ring-destructive/30' : newPassword && !passwordError ? 'border-green-500/60 focus-visible:ring-green-500/30' : 'border-input'" />
              <button @click="fillGeneratedPassword('create')" type="button" title="生成随机密码"
                class="inline-flex items-center gap-1 h-9 rounded-lg border border-input bg-background px-2.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg>
                生成
              </button>
            </div>
            <p v-if="newPassword && passwordError" class="text-[10px] text-destructive flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              {{ passwordError }}
            </p>
            <p v-else-if="newPassword && !passwordError" class="text-[10px] text-green-600 dark:text-green-400 flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
              密码强度达标
            </p>
          </div>
          <div class="space-y-1">
            <input v-model="newDisplayName" placeholder="显示名称（选填）" maxlength="100"
              class="h-9 w-full rounded-lg border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors"
              :class="newDisplayName && displayNameError ? 'border-destructive/60 focus-visible:ring-destructive/30' : 'border-input'" />
            <p v-if="newDisplayName && displayNameError" class="text-[10px] text-destructive flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              {{ displayNameError }}
            </p>
          </div>
        </div>
        <div v-if="newPassword && passwordError" class="flex flex-wrap gap-1.5 mt-2 mb-2">
          <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5"
            :class="pwHasLower ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'">
            <svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pwHasLower" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>
            小写
          </span>
          <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5"
            :class="pwHasUpper ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'">
            <svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pwHasUpper" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>
            大写
          </span>
          <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5"
            :class="pwHasDigit ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'">
            <svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pwHasDigit" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>
            数字
          </span>
          <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5"
            :class="pwHasSpecial ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'">
            <svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pwHasSpecial" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>
            特殊字符
          </span>
          <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5"
            :class="pwLongEnough ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'">
            <svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pwLongEnough" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>
            ≥8位
          </span>
        </div>
        <!-- Admin permission selection -->
        <div v-if="activeRoleTab === 'admin' && auth.isSuperAdmin" class="mt-4 border-t border-border pt-3 mb-4">
          <p class="text-xs font-medium text-muted-foreground mb-3">授予以下权限（可多选）：</p>
          <div v-if="permBlocks.groups.length === 0" class="text-[10px] text-muted-foreground/60">加载中...</div>
          <div v-else v-for="g in permBlocks.groups" :key="g.group" class="mb-3">
            <p class="text-[10px] font-medium text-muted-foreground/60 uppercase tracking-wider mb-1.5">{{ g.label }}</p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              <div v-for="b in g.perms" :key="b.key"
                @click="permBlockToggled(b.key)"
                class="flex items-center gap-2.5 rounded-lg border px-3 py-2 cursor-pointer select-none transition-all"
                :class="newAdminPerms.has(b.key) ? 'border-primary/40 bg-primary/5 shadow-sm' : 'border-border hover:border-muted-foreground/30 hover:bg-muted/20'">
                <div class="w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 transition-colors"
                  :class="newAdminPerms.has(b.key) ? 'bg-primary border-primary' : 'border-muted-foreground/30'">
                  <svg v-if="newAdminPerms.has(b.key)" xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                </div>
                <span class="text-xs font-medium" :class="newAdminPerms.has(b.key) ? 'text-foreground' : 'text-muted-foreground'">{{ b.label }}</span>
              </div>
            </div>
          </div>
        </div>
      <p v-if="createError" class="text-xs text-destructive mb-2">{{ createError }}</p>
      <div class="flex gap-2">
        <button @click="handleCreate" :disabled="creating || !createFormValid" class="rounded-lg bg-primary text-primary-foreground px-4 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50">{{ creating ? '创建中...' : '创建' }}</button>
        <button @click="closeCreateForm" class="rounded-lg border border-border px-4 py-1.5 text-sm hover:bg-muted">取消</button>
      </div>
    </div>

    <p v-if="error" class="text-sm text-destructive">{{ error }}</p>

    <!-- Loading skeleton -->
    <div v-if="loading" class="rounded-xl border border-border bg-card overflow-hidden">
      <div class="p-5 space-y-3 animate-pulse">
        <div class="flex gap-3"><div class="h-9 bg-muted rounded-lg flex-1" /><div class="h-9 bg-muted rounded-lg w-20" /><div class="h-9 bg-muted rounded-lg w-20" /><div class="h-9 bg-muted rounded-lg w-24" /></div>
        <div class="h-10 bg-muted rounded-lg" />
        <div class="space-y-2"><div v-for="i in 5" :key="i" class="h-12 bg-muted/50 rounded-lg" /></div>
      </div>
    </div>

    <!-- User list -->
    <div v-if="!loading" class="rounded-xl border border-border bg-card overflow-hidden animate-fade-in-up">
      <!-- Multi-select action bar -->
      <div v-if="selectMode && filteredUsers.length > 0" class="flex items-center justify-between px-4 py-2.5 bg-primary/5 border-b border-primary/20">
        <div class="flex items-center gap-2">
          <input type="checkbox" :checked="selectedIds.size === selectableCount && selectableCount > 0" :indeterminate="selectedIds.size > 0 && selectedIds.size < selectableCount" @change="toggleSelectAll" class="accent-primary w-4 h-4 rounded" />
          <span class="text-sm font-medium text-foreground">
            {{ selectedIds.size > 0 ? `已选 ${selectedIds.size} 人` : selectableCount > 0 ? `全选 ${selectableCount} 人` : '无可选用户' }}
          </span>
        </div>
        <div class="flex items-center gap-2">
          <button v-if="selectedIds.size > 0" @click="confirmBatchDelete" class="inline-flex items-center gap-1.5 text-xs font-medium text-destructive hover:text-destructive/80 bg-destructive/10 hover:bg-destructive/15 px-3 py-1.5 rounded-lg transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
            删除选中
          </button>
          <button @click="toggleSelectMode" class="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground bg-muted/50 hover:bg-muted px-2.5 py-1.5 rounded-lg transition-colors">
            退出多选
          </button>
        </div>
      </div>
      <div v-if="filteredUsers.length === 0" class="text-center text-muted-foreground text-sm py-12">无匹配用户</div>
      <template v-else>
        <!-- Desktop table -->
        <table class="hidden sm:table w-full text-sm">
          <thead class="bg-muted/30">
            <tr class="border-b border-border">
              <th class="text-left px-3 py-3 font-medium text-muted-foreground text-xs">状态</th>
              <th class="text-left px-3 py-3 font-medium text-muted-foreground text-xs">姓名</th>
              <th class="text-left px-3 py-3 font-medium text-muted-foreground text-xs">工号</th>
              <th class="text-left px-3 py-3 font-medium text-muted-foreground text-xs">角色</th>
              <th class="text-left px-3 py-3 font-medium text-muted-foreground text-xs">创建时间</th>
              <th class="text-right px-3 py-3 font-medium text-muted-foreground text-xs">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(u, idx) in pagedUsers" :key="u.id"
              class="border-b border-border last:border-0 hover:bg-muted/20 animate-fade-in transition-colors duration-150"
              :class="[selectMode ? 'cursor-pointer' : '',
                       selectMode && selectedIds.has(u.id) ? 'bg-primary/5 border-primary/30 hover:bg-primary/10' : '']"
              :style="{ animationDelay: `${idx * 0.02}s` }"
               @click="selectMode && u.role !== 'super_admin' ? toggleSelect(u.id) : null">
              <td class="px-3 py-3">
                <span class="block w-2 h-2 rounded-full" :class="u.is_online ? 'bg-green-500 shadow-sm shadow-green-500/50' : 'bg-muted-foreground/30'" :title="u.is_online ? '在线' : '离线'" />
              </td>
              <td class="px-3 py-3">
                <div class="flex items-center gap-2">
                  <div v-if="u.avatar_url" class="w-7 h-7 rounded-full bg-cover bg-center shrink-0" :style="{ backgroundImage: `url(${u.avatar_url})` }" />
                  <div v-else class="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center text-xs font-bold text-primary shrink-0">{{ (u.display_name || u.username)[0] }}</div>
                  <span class="font-medium truncate">{{ u.display_name }}</span>
                </div>
              </td>
              <td class="px-3 py-3 font-mono text-xs text-muted-foreground">{{ u.employee_id || '—' }}</td>
              <td class="px-3 py-3"><span class="text-xs px-2 py-0.5 rounded-full font-medium" :class="u.role === 'super_admin' ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400' : u.role === 'admin' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'">{{ u.role === 'super_admin' ? '系统管理员' : u.role === 'admin' ? '管理员' : '员工' }}</span></td>
              <td class="px-3 py-3 text-muted-foreground text-xs">{{ new Date(u.created_at).toLocaleString() }}</td>
              <td class="px-3 py-3 text-right space-x-1">
              <button v-if="auth.hasPermission('users.view_data')" @click="openDm(u)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" title="数据管理"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>数据</button>
              <button v-if="auth.isSuperAdmin && (u.role === 'admin' && !u.is_super_admin)" @click="openPermEditorForUser(u)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" title="权限管理"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 12l2 2 4-4"/></svg>权限</button>
              <button v-if="auth.hasPermission('users.edit')" @click="openEdit(u)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" title="编辑"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>编辑</button>
              <button v-if="auth.hasPermission('users.delete') && (u.role === 'employee' || (auth.isSuperAdmin && u.role === 'admin' && !u.is_super_admin))" @click="confirmDelete(u.id)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors" title="删除"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>删除</button>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Mobile card list -->
        <div class="sm:hidden divide-y divide-border">
          <div v-if="selectMode" class="flex items-center justify-between px-4 py-2.5 bg-primary/5 border-b border-primary/20">
            <div class="flex items-center gap-2">
              <input type="checkbox" :checked="selectedIds.size === selectableCount && selectableCount > 0" :indeterminate="selectedIds.size > 0 && selectedIds.size < selectableCount" @change="toggleSelectAll" class="accent-primary w-4 h-4 rounded" />
              <span class="text-sm font-medium">{{ selectedIds.size > 0 ? `已选 ${selectedIds.size} 人` : selectableCount > 0 ? `全选 ${selectableCount} 人` : '无可选用户' }}</span>
            </div>
            <div class="flex items-center gap-2">
              <button v-if="selectedIds.size > 0" @click="confirmBatchDelete" class="inline-flex items-center gap-1.5 text-xs font-medium text-destructive hover:text-destructive/80 bg-destructive/10 hover:bg-destructive/15 px-2.5 py-1.5 rounded-lg transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                删除选中
              </button>
              <span @click="toggleSelectMode" class="text-xs text-muted-foreground hover:text-foreground cursor-pointer select-none">退出</span>
            </div>
          </div>
          <div v-for="(u, idx) in pagedUsers" :key="u.id" class="p-4 animate-fade-in space-y-2" :style="{ animationDelay: `${idx * 0.02}s` }">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <input v-if="selectMode && u.role !== 'super_admin'" type="checkbox" :checked="selectedIds.has(u.id)" @change="toggleSelect(u.id)" class="accent-primary" />
                <div v-if="u.avatar_url" class="w-8 h-8 rounded-full bg-cover bg-center shrink-0" :style="{ backgroundImage: `url(${u.avatar_url})` }" />
                <div v-else class="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-xs font-bold text-primary shrink-0">{{ (u.display_name || u.username)[0] }}</div>
                <div>
                  <span class="font-medium text-sm flex items-center gap-2">{{ u.display_name }} <span class="block w-1.5 h-1.5 rounded-full" :class="u.is_online ? 'bg-green-500' : 'bg-muted-foreground/30'" /></span>
                  <p class="text-xs text-muted-foreground">{{ u.employee_id || u.username }} · <span :class="u.role === 'super_admin' ? 'text-amber-500' : u.role === 'admin' ? 'text-primary' : ''">{{ u.role === 'super_admin' ? '系统管理员' : u.role === 'admin' ? '管理员' : '员工' }}</span></p>
                </div>
              </div>
            </div>
            <p class="text-[10px] text-muted-foreground/60">{{ new Date(u.created_at).toLocaleString() }}</p>
            <div class="flex items-center gap-1 pt-1">
              <button v-if="auth.hasPermission('users.view_data')" @click="openDm(u)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>数据</button>
              <button v-if="auth.isSuperAdmin && (u.role === 'admin' && !u.is_super_admin)" @click="openPermEditorForUser(u)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 12l2 2 4-4"/></svg>权限</button>
              <button v-if="auth.hasPermission('users.edit')" @click="openEdit(u)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>编辑</button>
              <button v-if="auth.hasPermission('users.delete') && (u.role === 'employee' || (auth.isSuperAdmin && u.role === 'admin' && !u.is_super_admin))" @click="confirmDelete(u.id)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>删除</button>
            </div>
          </div>
        </div>

        <!-- Pagination -->
        <div class="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-muted-foreground flex-wrap gap-2">
          <div class="flex items-center gap-3">
            <span>共 {{ filteredUsers.length }} 条</span>
            <span v-if="filteredUsers.length > 0" class="text-muted-foreground/60">{{ (page - 1) * pageSize + 1 }}-{{ Math.min(page * pageSize, filteredUsers.length) }} 条</span>
            <label class="flex items-center gap-1 text-muted-foreground/60">
              每页
              <select @change="changePageSize" :value="pageSize" class="h-7 rounded border border-input bg-background px-1.5 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
                <option value="15">15</option>
                <option value="30">30</option>
                <option value="50">50</option>
                <option value="100">100</option>
              </select>
              条
            </label>
          </div>
          <div class="flex items-center gap-1.5">
            <button @click="goPage(1)" :disabled="page <= 1" class="rounded-md px-1.5 py-1 hover:bg-muted disabled:opacity-30 transition-colors" title="首页">«</button>
            <button @click="goPage(page - 1)" :disabled="page <= 1" class="rounded-md px-2 py-1 hover:bg-muted disabled:opacity-30 transition-colors">‹ 上一页</button>
            <template v-for="p in totalPages" :key="p">
              <button v-if="Math.abs(p - page) <= 2 || p === 1 || p === totalPages" @click="goPage(p)"
                class="rounded-md px-2.5 py-1 font-medium transition-colors"
                :class="p === page ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'">{{ p }}</button>
              <span v-else-if="p === page - 3 || p === page + 3" class="px-1">…</span>
            </template>
            <button @click="goPage(page + 1)" :disabled="page >= totalPages" class="rounded-md px-2 py-1 hover:bg-muted disabled:opacity-30 transition-colors">下一页 ›</button>
            <button @click="goPage(totalPages)" :disabled="page >= totalPages" class="rounded-md px-1.5 py-1 hover:bg-muted disabled:opacity-30 transition-colors" title="末页">»</button>
            <span class="w-px h-4 bg-border mx-1"></span>
            <form @submit.prevent="jumpToPage" class="flex items-center gap-1">
              <input v-model="jumpPageInput" type="number" min="1" :max="totalPages" placeholder="页码" class="w-14 h-7 rounded border border-input bg-background px-1.5 text-xs text-center focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none" />
              <button type="submit" :disabled="!jumpPageInput" class="rounded-md px-2 py-1 bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-30 transition-colors">跳转</button>
            </form>
          </div>
        </div>
      </template>
    </div>
    <div v-else class="text-center text-sm text-muted-foreground py-12">加载中...</div>

    <ConfirmDialog v-if="confirmDeleteId" title="删除用户" message="确定删除此用户？该用户的所有数据将被清空，不可恢复。" destructive @confirm="executeDelete" @cancel="cancelDelete" />
    <ConfirmDialog v-if="confirmDeleteIds" :title="`删除 ${confirmDeleteIds.length} 个用户`" message="确定删除选中的用户？所有相关数据将被清空，不可恢复。" destructive @confirm="executeBatchDelete" @cancel="cancelDelete" />
    <ConfirmDialog v-if="confirmDeleteItem" title="确认删除" :message="`确定删除${confirmDeleteItem.label}？删除后不可恢复。`" destructive @confirm="executeDeleteItem" @cancel="cancelDeleteItem" />
    <ConfirmDialog v-if="confirmBulkDeleteMsgs" :title="`删除 ${confirmBulkDeleteMsgs.length} 条消息`" message="确定删除选中的消息？删除后不可恢复。" destructive @confirm="executeBulkDeleteMsgs" @cancel="cancelBulkDeleteMsgs" />
    <ConfirmDialog v-if="confirmBulkDeleteConvs" :title="`删除 ${confirmBulkDeleteConvs.length} 个对话`" message="确定删除选中的对话及其所有消息？删除后不可恢复。" destructive @confirm="executeBulkDeleteConvs" @cancel="cancelBulkDeleteConvs" />
    <ConfirmDialog v-if="confirmClearUserData" title="清空数据" message="确定清空该用户的所有对话记录、记忆事实和摘要？不可恢复。" destructive @confirm="executeClearUserData" @cancel="() => confirmClearUserData = false" />

    <!-- Edit dialog -->
    <Teleport to="body">
      <div v-if="showEdit && editUser" key="edit" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-fade-in" @click="closeEdit">
        <div class="bg-card border border-border rounded-xl w-full max-w-lg shadow-xl animate-scale-in overflow-hidden" @click.stop>
          <div class="px-5 py-4 border-b border-border flex items-center justify-between">
            <h2 class="text-sm font-semibold">编辑{{ editUser.role === 'admin' || editUser.role === 'super_admin' ? '管理员' : '员工' }} — {{ editUser.username }}</h2>
            <button @click="closeEdit" class="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>
          </div>
          <div class="p-5 space-y-4">
            <div class="flex items-center gap-4 mb-2">
              <div class="relative group shrink-0" @click="editAvatarFileInput?.click()">
                <div class="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-lg font-bold text-primary overflow-hidden cursor-pointer ring-2 ring-border hover:ring-primary/50 transition-all">
                  <img v-if="editData.avatar_url" :src="editData.avatar_url" class="w-full h-full object-cover" />
                  <span v-else>{{ (editData.display_name || editUser.username)[0] }}</span>
                </div>
                <div class="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>
                </div>
                <input ref="editAvatarFileInput" type="file" accept="image/*" class="hidden" @change="editAvatarFileInput?.files?.[0] && uploadEditAvatar(editAvatarFileInput.files[0])" />
                <div v-if="editAvatarUploading" class="absolute -bottom-1 -right-1 w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin bg-background" />
              </div>
              <div><span class="text-sm font-medium block">{{ editData.display_name || editUser.username }}</span><span class="text-xs text-muted-foreground">{{ editUser.role === 'admin' || editUser.role === 'super_admin' ? '管理员' : '员工' }}</span></div>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div class="space-y-1.5"><label class="text-xs font-medium text-muted-foreground">显示名称</label><input v-model="editData.display_name" class="flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
              <div class="space-y-1.5"><label class="text-xs font-medium text-muted-foreground">工号</label><input v-model="editData.employee_id" class="flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
              <div class="sm:col-span-2 space-y-1.5"><label class="text-xs font-medium text-muted-foreground">头像 URL</label><div class="flex gap-1"><input v-model="editAvatarUrlInput" placeholder="https://example.com/avatar.png" class="flex-1 h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /><button @click="editAvatarFileInput?.click()" class="h-9 rounded-lg border border-input bg-background px-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted shrink-0"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg> 上传</button></div><p v-if="isUploadedAvatar(editData.avatar_url)" class="text-[10px] text-muted-foreground/70">当前为上传的头像，填写链接可切换为在线头像。</p></div>
              <div class="space-y-1.5"><label class="text-xs font-medium text-muted-foreground">电话</label><input v-model="editData.phone" class="flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
              <div class="sm:col-span-2 space-y-1.5"><label class="text-xs font-medium text-muted-foreground">新密码（留空不修改）</label><div class="flex gap-1"><input v-model="editData.password" type="text" placeholder="留空则不修改" class="flex-1 h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" /><button @click="editData.password = generatePassword()" class="h-9 rounded-lg border border-input bg-background px-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted shrink-0">生成</button></div>
              <div v-if="editData.password" class="flex flex-wrap gap-1.5"><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="editPwHasLower ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="editPwHasLower" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>小写</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="editPwHasUpper ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="editPwHasUpper" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>大写</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="editPwHasDigit ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="editPwHasDigit" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>数字</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="editPwHasSpecial ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="editPwHasSpecial" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>特殊字符</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="editPwLongEnough ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="editPwLongEnough" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>≥8位</span></div>
              <div class="space-y-1"><label class="text-xs font-medium text-muted-foreground">确认新密码</label><input v-model="editData.password2" type="text" :placeholder="editData.password ? '再次输入新密码' : '留空则不修改'" class="flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
              <div v-if="editData.password2" class="flex flex-wrap gap-1.5"><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="editPw2HasLower ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="editPw2HasLower" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>小写</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="editPw2HasUpper ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="editPw2HasUpper" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>大写</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="editPw2HasDigit ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="editPw2HasDigit" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>数字</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="editPw2HasSpecial ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="editPw2HasSpecial" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>特殊字符</span><span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="editPw2LongEnough ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="editPw2LongEnough" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>≥8位</span></div></div></div>
            </div>
            <p v-if="editError" class="text-xs text-destructive">{{ editError }}</p>
          </div>
          <div class="px-5 py-4 border-t border-border flex justify-end gap-2">
            <button @click="closeEdit" class="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-muted">取消</button>
            <button @click="saveEdit" class="rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-xs hover:bg-primary/90">保存</button>
        </div>
      </div>
    </div>
    </Teleport>

    <!-- Data Manager dialog -->
    <Teleport to="body">
      <div v-if="showDm && dmUser" key="dm" class="fixed inset-0 z-[9999] flex items-start justify-center bg-black/40 backdrop-blur-sm p-4 pt-12 overflow-y-auto animate-fade-in" @click="closeDm">
        <div class="bg-card border border-border rounded-xl w-full max-w-2xl shadow-xl animate-scale-in overflow-hidden" @click.stop>
          <div class="px-5 py-4 border-b border-border flex items-center justify-between">
            <h2 class="text-sm font-semibold">数据管理 — {{ dmUser.display_name || dmUser.username }}</h2>
            <button @click="closeDm" class="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>
          </div>
          <div class="flex border-b border-border px-5">
            <button @click="switchTab('messages')" class="px-3 py-2 text-xs font-medium border-b-2 transition-colors" :class="dmTab === 'messages' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'">消息 ({{ dmTotals.messages }})</button>
            <button @click="switchTab('facts')" class="px-3 py-2 text-xs font-medium border-b-2 transition-colors" :class="dmTab === 'facts' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'">记忆事实 ({{ dmTotals.facts }})</button>
            <button @click="switchTab('summaries')" class="px-3 py-2 text-xs font-medium border-b-2 transition-colors" :class="dmTab === 'summaries' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'">摘要 ({{ dmTotals.summaries }})</button>
            <button @click="switchTab('stats')" class="px-3 py-2 text-xs font-medium border-b-2 transition-colors" :class="dmTab === 'stats' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'">统计</button>
          </div>
          <div v-if="dmTab !== 'stats' && dmItems.length > 0" class="px-5 pt-3">
            <div class="flex gap-2">
              <input v-model="dmSearch" @keydown.enter="loadDmTab" placeholder="搜索内容..." class="flex-1 h-8 rounded-lg border border-input bg-background px-3 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
              <button @click="loadDmTab" class="rounded-lg bg-primary text-primary-foreground px-3 text-xs hover:bg-primary/90">搜索</button>
              <button v-if="dmTab === 'messages'" @click="requestClearUserData" class="rounded-lg border border-destructive/30 text-destructive px-3 text-xs hover:bg-destructive/10">清空消息</button>
              <button v-if="dmTab === 'facts'" @click="requestDeleteItem(`/auth/users/${dmUser!.id}/facts/bulk-delete`, '所有记忆事实')" class="rounded-lg border border-destructive/30 text-destructive px-3 text-xs hover:bg-destructive/10">清空事实</button>
              <button v-if="dmTab === 'summaries'" @click="requestDeleteItem(`/auth/users/${dmUser!.id}/summaries/bulk-delete`, '所有摘要')" class="rounded-lg border border-destructive/30 text-destructive px-3 text-xs hover:bg-destructive/10">清空摘要</button>
            </div>
          </div>
          <div class="p-5 max-h-[55vh] overflow-y-auto">
            <div v-if="dmLoading" class="text-center py-6 text-xs text-muted-foreground">加载中...</div>

            <!-- Messages tab -->
            <div v-else-if="dmTab === 'messages'">
              <div v-if="dmItems.length === 0" class="text-center py-6 text-xs text-muted-foreground">暂无消息</div>
              <div v-else-if="!dmConvId" class="space-y-1">
                <div class="flex items-center justify-between mb-1 px-0.5">
                  <span class="text-[10px] text-muted-foreground/50">{{ messageGroups.length }} 个对话</span>
                  <div class="flex items-center gap-1">
                    <button v-if="!convSelectMode" @click="toggleConvSelectMode()" class="text-[10px] text-muted-foreground hover:text-foreground px-1">选择</button>
                    <template v-else>
                      <button @click="toggleConvSelectMode()" class="text-[10px] text-muted-foreground hover:text-foreground px-1">取消</button>
                      <span class="text-[10px] text-muted-foreground/50">{{ selectedConvIds.size }}/{{ messageGroups.length }}</span>
                      <button @click="selectedConvIds.size === messageGroups.length ? selectedConvIds = new Set() : selectedConvIds = new Set(messageGroups.map(g=>g.id))" class="text-[10px] text-muted-foreground hover:text-foreground px-1">{{ selectedConvIds.size === messageGroups.length ? '取消全选' : '全选' }}</button>
                      <button v-if="selectedConvIds.size > 0" @click="requestBulkDeleteConvs()" class="text-[10px] text-destructive hover:text-destructive/80 px-1">删除选中</button>
                    </template>
                  </div>
                </div>
                <button v-for="g in messageGroups" :key="g.id" @click="convSelectMode ? toggleConvSelect(g.id) : selectConversation(g.id)" class="w-full text-left rounded-lg border border-border p-2.5 transition-colors flex items-center gap-2" :class="convSelectMode ? (selectedConvIds.has(g.id) ? 'bg-primary/5 border-primary/30' : 'hover:bg-muted/30') : 'hover:bg-muted/30'">
                  <input v-if="convSelectMode" type="checkbox" :checked="selectedConvIds.has(g.id)" class="shrink-0" />
                  <div class="flex items-center justify-between gap-2 flex-1 min-w-0">
                    <div class="flex items-center gap-2 min-w-0">
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-muted-foreground shrink-0"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                      <div class="min-w-0">
                        <p class="text-xs font-medium truncate">{{ g.msgs[0]?.title || g.msgs[0]?.content?.slice(0, 60) || '(空对话)' }}{{ !g.msgs[0]?.title && (g.msgs[0]?.content?.length || 0) > 60 ? '...' : '' }}</p>
                        <p class="text-[10px] text-muted-foreground/60">{{ g.count }} 条消息 · {{ g.latest.toLocaleString() }}</p>
                      </div>
                    </div>
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-muted-foreground/40 shrink-0"><polyline points="9 18 15 12 9 6"/></svg>
                  </div>
                </button>
              </div>
              <!-- Message detail -->
              <div v-else class="space-y-2">
                <button @click="dmConvId = null" class="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mb-2"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>返回对话列表</button>
                <div class="flex items-center justify-between mb-1">
                  <span class="text-[10px] text-muted-foreground/50">{{ messageGroups.find(g => g.id === dmConvId)?.count || 0 }} 条消息</span>
                  <div class="flex items-center gap-1">
                    <button v-if="!selectModeMsg" @click="toggleSelectModeMsg()" class="text-[10px] text-muted-foreground hover:text-foreground px-1">选择</button>
                    <template v-else>
                      <button @click="toggleSelectModeMsg()" class="text-[10px] text-muted-foreground hover:text-foreground px-1">取消</button>
                      <span class="text-[10px] text-muted-foreground/50">{{ selectedMsgIds.size }}</span>
                      <button v-if="selectedMsgIds.size > 0" @click="requestBulkDeleteMsgs()" class="text-[10px] text-destructive hover:text-destructive/80 px-1">删除选中</button>
                    </template>
                  </div>
                </div>
                <div v-for="msg in (messageGroups.find(g => g.id === dmConvId)?.msgs || [])" :key="msg.id" class="rounded-lg border border-border p-3">
                  <div class="flex items-center justify-between mb-1">
                    <div class="flex items-center gap-1.5">
                      <input v-if="selectModeMsg" type="checkbox" :checked="selectedMsgIds.has(msg.id)" @change="toggleMsgSelect(msg.id)" class="shrink-0" />
                      <span class="text-[10px] font-mono bg-muted px-1.5 py-0.5 rounded text-muted-foreground">#{{ msg.id }}</span>
                      <span class="text-[10px] text-muted-foreground" :class="msg.role === 'user' ? 'text-primary' : 'text-accent-foreground'">{{ msg.role === 'user' ? '用户' : 'AI' }}</span>
                    </div>
                    <button @click="requestDeleteItem(`/auth/users/${dmUser!.id}/messages/${msg.id}`, '消息')" class="text-[10px] text-muted-foreground hover:text-destructive">删除</button>
                  </div>
                  <p class="text-xs leading-relaxed whitespace-pre-wrap text-foreground/85">{{ (msg.content || '').slice(0, 300) }}{{ (msg.content || '').length > 300 ? '...' : '' }}</p>
                </div>
              </div>
            </div>

            <!-- Facts tab -->
            <div v-else-if="dmTab === 'facts'">
              <div v-if="dmItems.length === 0" class="text-center py-6 text-xs text-muted-foreground">暂无记忆事实</div>
              <div v-else>
                <div class="flex items-center justify-between mb-2 px-0.5">
                  <span class="text-[10px] text-muted-foreground/50">{{ dmItems.length }} 条事实</span>
                </div>
                <div class="space-y-2">
                <div v-for="fact in dmItems" :key="fact.id" class="rounded-lg border border-border p-3">
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-[10px] font-mono bg-muted px-1.5 py-0.5 rounded text-muted-foreground">#{{ fact.id }}</span>
                    <div class="flex items-center gap-1">
                      <button v-if="dmEditId !== fact.id" @click="startEdit(fact, 'content')" class="text-[10px] text-muted-foreground hover:text-foreground px-1">编辑</button>
                      <button @click="requestDeleteItem(`/auth/users/${dmUser!.id}/facts/${fact.id}`, '记忆事实')" class="text-[10px] text-muted-foreground hover:text-destructive px-1">删除</button>
                    </div>
                  </div>
                  <textarea v-if="dmEditId === fact.id" v-model="dmEditText" class="w-full text-xs bg-background border border-input rounded px-2 py-1 resize-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" rows="2" />
                  <p v-else class="text-xs leading-relaxed text-foreground/85">{{ fact.content }}</p>
                  <div v-if="dmEditId === fact.id" class="flex gap-1 mt-1 justify-end">
                    <button @click="cancelEdit()" class="text-[10px] text-muted-foreground hover:text-foreground px-1">取消</button>
                    <button @click="saveEditItem(fact, 'content', `/auth/users/${dmUser!.id}/facts/${fact.id}`)" class="text-[10px] text-primary hover:text-primary/80 px-1">保存</button>
                  </div>
                </div>
              </div>
            </div>
            </div>

            <!-- Summaries tab -->
            <div v-else-if="dmTab === 'summaries'">
              <div v-if="dmItems.length === 0" class="text-center py-6 text-xs text-muted-foreground">暂无摘要</div>
              <div v-else>
                <div class="flex items-center justify-between mb-2 px-0.5">
                  <span class="text-[10px] text-muted-foreground/50">{{ dmConvId ? (summaryGroups.find(g => g.convId === dmConvId)?.count || 0) + ' 条摘要' : summaryGroups.length + ' 个对话' }}</span>
                </div>
                <div v-if="!dmConvId" class="space-y-1">
                  <button v-for="g in summaryGroups" :key="g.convId" @click="dmConvId = g.convId" class="w-full text-left rounded-lg border border-border p-2.5 transition-colors hover:bg-muted/30 flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-muted-foreground shrink-0"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                    <div class="flex-1 min-w-0">
                      <p class="text-xs font-medium truncate">{{ g.title || g.firstContent?.slice(0, 60) || '(空)' }}{{ !g.title && (g.firstContent?.length || 0) > 60 ? '...' : '' }}</p>
                      <p class="text-[10px] text-muted-foreground/60">{{ g.count }} 条摘要 · {{ g.latest.toLocaleString() }}</p>
                    </div>
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-muted-foreground/40 shrink-0"><polyline points="9 18 15 12 9 6"/></svg>
                  </button>
                </div>
                <div v-else class="space-y-2">
                  <button @click="dmConvId = null" class="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mb-2"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>返回对话列表</button>
                  <div v-for="sum in (summaryGroups.find(g => g.convId === dmConvId)?.items || [])" :key="sum.id" class="rounded-lg border border-border p-3">
                    <div class="flex items-center justify-between mb-1">
                      <span class="text-[10px] font-mono bg-muted px-1.5 py-0.5 rounded text-muted-foreground">#{{ sum.id }}</span>
                      <div class="flex items-center gap-1">
                        <button v-if="dmEditId !== sum.id" @click="startEdit(sum, 'summary')" class="text-[10px] text-muted-foreground hover:text-foreground px-1">编辑</button>
                        <button @click="requestDeleteItem(`/auth/users/${dmUser!.id}/summaries/${sum.id}`, '摘要')" class="text-[10px] text-muted-foreground hover:text-destructive px-1">删除</button>
                      </div>
                    </div>
                    <textarea v-if="dmEditId === sum.id" v-model="dmEditText" class="w-full text-xs bg-background border border-input rounded px-2 py-1 resize-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" rows="2" />
                    <p v-else class="text-xs leading-relaxed text-foreground/85 whitespace-pre-wrap">{{ (sum.summary || '').slice(0, 500) }}{{ (sum.summary || '').length > 500 ? '...' : '' }}</p>
                    <div v-if="dmEditId === sum.id" class="flex gap-1 mt-1 justify-end">
                      <button @click="cancelEdit()" class="text-[10px] text-muted-foreground hover:text-foreground px-1">取消</button>
                      <button @click="saveEditItem(sum, 'summary', `/auth/users/${dmUser!.id}/summaries/${sum.id}`)" class="text-[10px] text-primary hover:text-primary/80 px-1">保存</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Stats tab -->
            <div v-else>
              <div v-if="!dmStats" class="text-center py-6 text-xs text-muted-foreground">暂无统计数据</div>
              <div v-else class="space-y-4">
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div class="rounded-lg bg-muted/50 p-3 text-center"><p class="text-2xl font-bold">{{ dmStats.conversations || 0 }}</p><p class="text-[10px] text-muted-foreground mt-1">对话数</p></div>
                  <div class="rounded-lg bg-muted/50 p-3 text-center"><p class="text-2xl font-bold">{{ dmStats.messages || 0 }}</p><p class="text-[10px] text-muted-foreground mt-1">消息数</p></div>
                  <div class="rounded-lg bg-muted/50 p-3 text-center"><p class="text-2xl font-bold">{{ dmStats.facts || 0 }}</p><p class="text-[10px] text-muted-foreground mt-1">记忆事实</p></div>
                  <div class="rounded-lg bg-muted/50 p-3 text-center"><p class="text-2xl font-bold">{{ dmStats.summaries || 0 }}</p><p class="text-[10px] text-muted-foreground mt-1">摘要数</p></div>
                </div>
                <button v-if="(dmStats?.conversations || 0) + (dmStats?.messages || 0) + (dmStats?.facts || 0) + (dmStats?.summaries || 0) > 0" @click="requestClearUserData()" class="w-full rounded-lg border border-destructive/30 text-destructive px-3 py-2 text-xs hover:bg-destructive/10">清空该用户所有数据</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Permission editor dialog -->
    <Teleport to="body">
      <div v-if="permEditingAdmin" key="perm" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-fade-in" @click="permEditingAdmin = null">
        <div class="bg-card border border-border rounded-xl w-full max-w-lg shadow-2xl animate-scale-in overflow-hidden" @click.stop>
          <div class="px-5 py-4 border-b border-border flex items-center justify-between bg-muted/20">
            <div class="flex items-center gap-2.5">
              <div class="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 12l2 2 4-4"/></svg>
              </div>
              <div>
                <h2 class="text-sm font-semibold">编辑权限</h2>
                <p class="text-[10px] text-muted-foreground">{{ permEditingAdmin.display_name }} · @{{ permEditingAdmin.username }}</p>
              </div>
            </div>
            <button @click="permEditingAdmin = null" class="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>
          </div>
          <div class="p-5 space-y-5 max-h-[60vh] overflow-y-auto">
            <p class="text-xs text-muted-foreground bg-muted/50 rounded-lg px-3 py-2">勾选该管理员拥有的权限，未勾选的权限将不可用。</p>
            <div v-for="g in (permEditingAdmin?.is_super_admin ? permBlocks.groups : permBlocks.groups.filter((g: any) => g.group !== 'system.admins'))" :key="g.group" class="space-y-2">
              <div class="flex items-center gap-2">
                <div class="h-px flex-1 bg-border/50"></div>
                <p class="text-[10px] font-semibold text-muted-foreground/50 uppercase tracking-widest shrink-0">{{ g.label }}</p>
                <div class="h-px flex-1 bg-border/50"></div>
              </div>
              <div class="grid grid-cols-1 gap-1.5">
                <div v-for="b in g.perms" :key="b.key"
                  @click="permDialogToggled(b.key)"
                  class="group flex items-center gap-3 rounded-lg border px-3.5 py-2.5 cursor-pointer select-none transition-all"
                  :class="permSelected.has(b.key) ? 'border-primary/30 bg-primary/[0.04] shadow-sm' : 'border-border hover:border-muted-foreground/20 hover:bg-muted/20'">
                  <div class="w-4.5 h-4.5 rounded border-2 flex items-center justify-center shrink-0 transition-all"
                    :class="permSelected.has(b.key) ? 'bg-primary border-primary shadow-sm shadow-primary/20' : 'border-muted-foreground/30 group-hover:border-muted-foreground/50'">
                    <svg v-if="permSelected.has(b.key)" xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                  </div>
                  <span class="text-xs font-medium flex-1" :class="permSelected.has(b.key) ? 'text-foreground' : 'text-muted-foreground'">{{ b.label }}</span>
                  <span class="text-[9px] font-mono text-muted-foreground/30 group-hover:text-muted-foreground/50 transition-colors">{{ b.key.split('.').pop() }}</span>
                </div>
              </div>
            </div>
            <p v-if="permError" class="text-xs text-destructive bg-destructive/5 rounded-lg px-3 py-2">{{ permError }}</p>
            <div v-else class="text-[10px] text-muted-foreground/50 text-center">已选 {{ permSelected.size }} / {{ (permEditingAdmin?.is_super_admin ? permBlocks.groups : permBlocks.groups.filter((g: any) => g.group !== 'system.admins')).reduce((a: number, g: any) => a + g.perms.length, 0) }} 项</div>
          </div>
          <div class="px-5 py-4 border-t border-border bg-muted/10 flex justify-end gap-2">
            <button @click="permEditingAdmin = null" class="rounded-lg border border-border px-4 py-2 text-xs font-medium hover:bg-muted transition-colors">取消</button>
            <button @click="saveAdminPerms" :disabled="permSaving" class="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-xs font-medium hover:bg-primary/90 disabled:opacity-50 shadow-sm transition-colors inline-flex items-center gap-1.5">
              <svg v-if="permSaving" class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              {{ permSaving ? '保存中...' : '保存权限' }}
            </button>
        </div>
      </div>
    </div>
    </Teleport>
  </div>
</template>
