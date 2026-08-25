<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { isUploadedAvatar, isExternalImageUrl, avatarUrlInputValue } from '@/utils/avatar'

const auth = useAuthStore()

const visible = ref(false)
const saving = ref(false)
const uploading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
let successTimer: ReturnType<typeof setTimeout> | null = null

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && visible.value) close()
}
onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))

const displayName = ref('')
const phone = ref('')
const password = ref('')
const password2 = ref('')
const avatarUrl = ref('')
const avatarUrlInput = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const user = computed(() => auth.user)

const roleLabel = computed(() => {
  const u = user.value
  if (!u) return ''
  if (u.is_super_admin || u.role === 'super_admin') return '系统管理员'
  if (u.role === 'admin') return '管理员'
  return '员工'
})

const joinedAt = computed(() => {
  const c = user.value?.created_at
  if (!c) return ''
  const d = new Date(c)
  return isNaN(d.getTime()) ? String(c).slice(0, 10) : d.toLocaleDateString('zh-CN')
})

const pwLower = computed(() => /[a-z]/.test(password.value))
const pwUpper = computed(() => /[A-Z]/.test(password.value))
const pwDigit = computed(() => /[0-9]/.test(password.value))
const pwSpecial = computed(() => /[!@#$%^&*()_+\-=\[\]{};':",.<>\/?\\|]/.test(password.value))
const pwLong = computed(() => password.value.length >= 8)

const pw2Lower = computed(() => /[a-z]/.test(password2.value))
const pw2Upper = computed(() => /[A-Z]/.test(password2.value))
const pw2Digit = computed(() => /[0-9]/.test(password2.value))
const pw2Special = computed(() => /[!@#$%^&*()_+\-=\[\]{};':",.<>\/?\\|]/.test(password2.value))
const pw2Long = computed(() => password2.value.length >= 8)

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

function showSuccess(msg: string) {
  successMsg.value = msg
  if (successTimer) clearTimeout(successTimer)
  successTimer = setTimeout(() => { successMsg.value = '' }, 2000)
}

function fail(err: any) {
  errorMsg.value = err?.response?.data?.detail || err?.message || '操作失败'
}

function open() {
  displayName.value = user.value?.display_name || ''
  phone.value = user.value?.phone || ''
  avatarUrl.value = user.value?.avatar_url || ''
  avatarUrlInput.value = avatarUrlInputValue(user.value?.avatar_url)
  password.value = ''; password2.value = ''
  errorMsg.value = ''; successMsg.value = ''
  visible.value = true
}

function close() {
  visible.value = false
}

async function uploadAvatar(file: File) {
  if (!file.type.startsWith('image/')) { errorMsg.value = '请选择图片文件'; return }
  uploading.value = true; errorMsg.value = ''
  try {
    const data = await auth.uploadAvatar(file)
    avatarUrl.value = data.url
    avatarUrlInput.value = ''
    showSuccess('头像已更新')
  } catch (err: any) { fail(err) }
  finally { uploading.value = false }
}

async function applyExternalUrl() {
  const url = avatarUrlInput.value.trim()
  if (!url) return
  if (!isExternalImageUrl(url)) { errorMsg.value = '请输入以 http(s):// 开头的图片链接'; return }
  errorMsg.value = ''; saving.value = true
  try {
    await auth.updateSelfProfile({ avatar_url: url })
    avatarUrl.value = url
    showSuccess('头像已更新')
  } catch (err: any) { fail(err) }
  finally { saving.value = false }
}

async function removeAvatar() {
  errorMsg.value = ''; saving.value = true
  try {
    await auth.updateSelfProfile({ avatar_url: '' })
    avatarUrl.value = ''; avatarUrlInput.value = ''
    showSuccess('头像已移除')
  } catch (err: any) { fail(err) }
  finally { saving.value = false }
}

async function save() {
  errorMsg.value = ''; successMsg.value = ''
  if (password.value && password.value !== password2.value) {
    errorMsg.value = '两次密码输入不一致'; return
  }
  saving.value = true
  try {
    const updates: any = {}
    if (displayName.value !== (user.value?.display_name || '')) updates.display_name = displayName.value
    if (phone.value !== (user.value?.phone || '')) updates.phone = phone.value
    if (password.value) updates.password = password.value
    if (Object.keys(updates).length > 0) {
      await auth.updateSelfProfile(updates)
      password.value = ''; password2.value = ''
      showSuccess('资料已更新')
    }
  } catch (err: any) { fail(err) }
  finally { saving.value = false }
}

defineExpose({ open })
</script>

<template>
  <Teleport to="body">
    <Transition name="dialog">
    <div
      v-if="visible"
      class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      @click="close"
    >
      <div class="bg-card border border-border rounded-xl w-full max-w-md shadow-2xl dialog-pop overflow-hidden" @click.stop>
        <!-- Header -->
        <div class="px-5 py-4 border-b border-border flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <div class="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            </div>
            <div>
              <h2 class="text-sm font-semibold">个人资料</h2>
              <p class="text-[10px] text-muted-foreground">{{ user?.username }} · {{ roleLabel }}</p>
            </div>
          </div>
          <button @click="close" class="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>

        <div class="p-5 space-y-4 max-h-[75vh] overflow-y-auto">
          <!-- Avatar -->
          <div class="flex flex-col items-center gap-3">
            <div class="relative group" @click="fileInput?.click()">
              <div class="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center text-2xl font-bold text-primary overflow-hidden ring-2 ring-border transition-shadow group-hover:ring-primary/50 cursor-pointer">
                <img v-if="avatarUrl" :src="avatarUrl" class="w-full h-full object-cover" />
                <span v-else>{{ (user?.display_name || user?.username || '?')[0] }}</span>
              </div>
              <div class="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
              </div>
              <div v-if="uploading" class="absolute -bottom-1 -right-1 w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin bg-background" />
            </div>
            <input ref="fileInput" type="file" accept="image/*" class="hidden" @change="fileInput?.files?.[0] && uploadAvatar(fileInput.files[0])" />
            <p class="text-[11px] text-muted-foreground/60 -mt-1">点击头像上传新头像</p>
          </div>

          <!-- Online URL -->
          <div class="relative">
            <div class="absolute inset-0 flex items-center"><div class="w-full border-t border-border" /></div>
            <div class="relative flex justify-center"><span class="bg-card px-2 text-[10px] text-muted-foreground">或使用在线链接</span></div>
          </div>
          <div class="flex gap-2">
            <input v-model="avatarUrlInput" placeholder="https://example.com/avatar.png" class="flex-1 h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            <button @click="applyExternalUrl" :disabled="saving || !avatarUrlInput.trim()" class="rounded-lg bg-primary text-primary-foreground px-3 text-xs font-medium hover:bg-primary/90 disabled:opacity-50 shrink-0">应用</button>
          </div>
          <p v-if="isUploadedAvatar(avatarUrl)" class="text-[10px] text-muted-foreground/70 -mt-1">当前为上传的头像，填写链接可切换为在线头像。</p>
          <button
            v-if="avatarUrl"
            @click="removeAvatar"
            :disabled="saving"
            class="w-full rounded-lg border border-destructive/40 text-destructive py-2 text-sm hover:bg-destructive/5 disabled:opacity-50 transition-colors"
          >{{ saving ? '处理中...' : '移除头像' }}</button>

          <div class="h-px bg-border" />

          <!-- Read-only info -->
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1">
              <label class="text-xs font-medium text-muted-foreground">用户名</label>
              <input :value="user?.username" disabled class="h-9 w-full rounded-lg border border-input bg-muted/50 px-3 text-sm text-muted-foreground" />
            </div>
            <div class="space-y-1">
              <label class="text-xs font-medium text-muted-foreground">角色</label>
              <input :value="roleLabel" disabled class="h-9 w-full rounded-lg border border-input bg-muted/50 px-3 text-sm text-muted-foreground" />
            </div>
            <div v-if="user?.employee_id" class="space-y-1">
              <label class="text-xs font-medium text-muted-foreground">工号</label>
              <input :value="user.employee_id" disabled class="h-9 w-full rounded-lg border border-input bg-muted/50 px-3 text-sm text-muted-foreground" />
            </div>
            <div class="space-y-1">
              <label class="text-xs font-medium text-muted-foreground">注册时间</label>
              <input :value="joinedAt" disabled class="h-9 w-full rounded-lg border border-input bg-muted/50 px-3 text-sm text-muted-foreground" />
            </div>
          </div>

          <!-- Editable -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div class="space-y-1">
              <label class="text-xs font-medium text-muted-foreground">显示名称</label>
              <input v-model="displayName" class="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            </div>
            <div class="space-y-1">
              <label class="text-xs font-medium text-muted-foreground">电话</label>
              <input v-model="phone" placeholder="选填" class="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            </div>
          </div>

          <div class="space-y-1">
            <label class="text-xs font-medium text-muted-foreground">新密码（留空不修改）</label>
            <div class="flex gap-1">
              <input v-model="password" type="text" placeholder="留空则不修改" class="flex-1 h-9 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
              <button @click="password = generatePassword(); password2 = ''" class="h-9 rounded-lg border border-input bg-background px-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted shrink-0">生成</button>
            </div>
            <div v-if="password" class="flex flex-wrap gap-1.5">
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="pwLower ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pwLower" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>小写</span>
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="pwUpper ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pwUpper" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>大写</span>
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="pwDigit ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pwDigit" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>数字</span>
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="pwSpecial ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pwSpecial" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>特殊字符</span>
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="pwLong ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pwLong" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>≥8位</span>
            </div>
          </div>

          <div class="space-y-1">
            <label class="text-xs font-medium text-muted-foreground">确认新密码</label>
            <input v-model="password2" type="text" :placeholder="password ? '再次输入新密码' : '留空则不修改'" class="flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            <div v-if="password2" class="flex flex-wrap gap-1.5">
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="pw2Lower ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pw2Lower" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>小写</span>
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="pw2Upper ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pw2Upper" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>大写</span>
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="pw2Digit ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pw2Digit" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>数字</span>
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="pw2Special ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pw2Special" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>特殊字符</span>
              <span class="inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5" :class="pw2Long ? 'bg-green-500/10 text-green-600 dark:text-green-400' : 'bg-muted text-muted-foreground'"><svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline v-if="pw2Long" points="20 6 9 17 4 12"/><circle v-else cx="12" cy="12" r="10"/></svg>≥8位</span>
            </div>
          </div>

          <p v-if="errorMsg" class="text-xs text-destructive bg-destructive/5 rounded-lg px-3 py-2">{{ errorMsg }}</p>
          <p v-if="successMsg" class="text-xs text-green-600 dark:text-green-400 bg-green-500/5 rounded-lg px-3 py-2">{{ successMsg }}</p>

          <button @click="save" :disabled="saving" class="w-full rounded-lg bg-primary text-primary-foreground py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors">{{ saving ? '保存中...' : '保存资料' }}</button>
        </div>
      </div>
    </div>
    </Transition>
  </Teleport>
</template>
