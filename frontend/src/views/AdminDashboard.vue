<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useHealthStore } from '@/stores/health'
import apiClient from '@/api/client'

const auth = useAuthStore()
const health = useHealthStore()

const stats = ref({ total_docs: 0, total_chunks: 0, total_users: 0 })
const loading = ref(true)
const editInterval = ref(false)
const newInterval = ref(health.refreshSeconds)

function fmtUptime(seconds: number): string {
  if (!seconds) return '—'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

function applyInterval() {
  const v = Math.max(5, Math.min(300, Math.floor(newInterval.value)))
  newInterval.value = v
  health.setRefreshSeconds(v)
  editInterval.value = false
}

onMounted(async () => {
  if (!health.loaded) {
    await health.fetch()
  }
  try {
    const [docRes, userRes] = await Promise.allSettled([
      apiClient.get('/documents/list'),
      apiClient.get('/auth/users'),
    ])
    if (docRes.status === 'fulfilled') {
      const docs = docRes.value.data
      stats.value.total_docs = docs.length
      stats.value.total_chunks = docs.reduce((s: number, d: any) => s + (d.chunk_count || 0), 0)
    }
    if (userRes.status === 'fulfilled') {
      stats.value.total_users = userRes.value.data.length
    }
  } catch {}
  loading.value = false
})
</script>

<template>
  <div class="h-full overflow-y-auto p-6 space-y-6">
    <div>
      <h1 class="text-xl font-bold">总览</h1>
      <p class="text-sm text-muted-foreground mt-0.5">系统运行状态与统计数据</p>
    </div>

    <div v-if="loading" class="text-sm text-muted-foreground py-8 text-center">加载中...</div>

    <template v-else>
      <!-- Stats cards -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="rounded-xl border border-border bg-card p-5 animate-scale-in" style="animation-delay: 0s">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
            </div>
            <div>
              <p class="text-xs text-muted-foreground">文档总数</p>
              <p class="text-2xl font-bold">{{ stats.total_docs }}</p>
            </div>
          </div>
          <p class="text-[10px] text-muted-foreground">{{ stats.total_chunks }} 个文本块</p>
        </div>

        <div class="rounded-xl border border-border bg-card p-5 animate-scale-in" style="animation-delay: 0.05s">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-9 h-9 rounded-lg bg-accent flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-accent-foreground"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            </div>
            <div>
              <p class="text-xs text-muted-foreground">用户总数</p>
              <p class="text-2xl font-bold">{{ stats.total_users }}</p>
            </div>
          </div>
          <p class="text-[10px] text-muted-foreground">{{ stats.total_users > 0 ? '管理员 + 员工' : '暂无用户' }}</p>
        </div>

        <div class="rounded-xl border border-border bg-card p-5 animate-scale-in" style="animation-delay: 0.1s">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-9 h-9 rounded-lg bg-muted flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-muted-foreground"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            </div>
            <div>
              <p class="text-xs text-muted-foreground">运行状态</p>
              <p class="text-2xl font-bold" :class="health.data?.status === 'healthy' ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-400'">{{ health.data?.status === 'healthy' ? '正常' : '异常' }}</p>
            </div>
          </div>
          <p class="text-[10px] text-muted-foreground">运行时长 {{ fmtUptime(health.data?.uptime_seconds) }}</p>
        </div>
      </div>

      <!-- System Status Detail -->
      <div class="rounded-xl border border-border bg-card animate-fade-in-up" style="animation-delay: 0.15s">
        <div class="px-5 py-4 border-b border-border flex items-center justify-between">
          <h2 class="text-sm font-semibold flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-muted-foreground"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
            系统状态
          </h2>
          <div class="flex items-center gap-2">
            <!-- Refresh interval control -->
            <div v-if="editInterval" class="flex items-center gap-1">
              <input v-model.number="newInterval" type="number" min="5" max="300" class="w-14 h-7 rounded border border-input bg-background px-2 text-xs text-center focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" />
              <span class="text-[10px] text-muted-foreground">秒</span>
              <button @click="applyInterval" class="text-[10px] px-1.5 py-0.5 rounded bg-primary text-primary-foreground hover:bg-primary/90">确定</button>
              <button @click="editInterval = false" class="text-[10px] px-1.5 py-0.5 rounded hover:bg-muted">取消</button>
            </div>
            <button v-else @click="editInterval = true; newInterval = health.refreshSeconds" class="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-0.5">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
              {{ health.refreshSeconds }}s
            </button>
            <!-- Manual refresh -->
            <button @click="health.fetch()" title="手动刷新" class="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" :disabled="health.isFetching">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :class="health.isFetching ? 'animate-spin' : ''"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
            </button>
          </div>
        </div>

        <div v-if="health.data" class="p-5">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1">
            <div v-for="svc in (health.data.services || [])" :key="svc.name" class="flex items-center justify-between py-2.5 border-b border-border/40">
              <div class="flex items-center gap-2.5">
                <span class="w-2 h-2 rounded-full" :class="svc.status.startsWith('connected') || svc.status.startsWith('configured') ? 'bg-green-500' : 'bg-red-500'" />
                <span class="text-sm font-medium">{{ svc.name }}</span>
              </div>
              <div class="text-right">
                <span class="text-sm" :class="svc.status.startsWith('connected') || svc.status.startsWith('configured') ? 'text-green-600 dark:text-green-400' : 'text-red-500'">{{ svc.status === 'connected' ? '已连接' : svc.status === 'configured' ? '已配置' : '断开' }}</span>
                <p v-if="svc.info" class="text-[10px] text-muted-foreground/60 mt-0.5">{{ svc.info }}</p>
              </div>
            </div>
            <div class="flex items-center justify-between py-2.5 border-b border-border/40">
              <span class="text-sm text-muted-foreground">服务器时间</span>
              <span class="text-sm font-mono text-xs">{{ health.data.server_time?.split(' UTC')[0] || '—' }}</span>
            </div>
            <div class="flex items-center justify-between py-2.5 border-b border-border/40">
              <span class="text-sm text-muted-foreground">运行时长</span>
              <span class="text-sm">{{ fmtUptime(health.data.uptime_seconds) }}</span>
            </div>
            <div class="flex items-center justify-between py-2.5 border-b border-border/40">
              <span class="text-sm text-muted-foreground">系统版本</span>
              <span class="text-sm font-mono">v{{ health.data.version }}</span>
            </div>
            <div class="flex items-center justify-between py-2.5 border-b border-border/40">
              <span class="text-sm text-muted-foreground">管理员</span>
              <span class="text-sm">{{ auth.user?.display_name || auth.user?.username }}</span>
            </div>
          </div>
        </div>
        <div v-else class="p-5 text-sm text-muted-foreground">无法获取系统状态</div>
      </div>
    </template>
  </div>
</template>
