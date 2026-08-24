<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { listDocuments, deleteDocument, batchDeleteDocuments } from '@/api/documents'
import type { DocumentInfo } from '@/types'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()

const emit = defineEmits<{
  viewDetail: [docId: string]
  deleted: []
  loaded: [docs: DocumentInfo[]]
}>()

const documents = ref<DocumentInfo[]>([])
const isLoading = ref(true)
const error = ref('')
const confirmDeleteIds = ref<string[] | null>(null)
const listRef = ref<HTMLDivElement | null>(null)
const selectedIds = ref<Set<string>>(new Set())
const searchQuery = ref('')
let scrollTop = 0

const filteredDocuments = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return documents.value
  return documents.value.filter(d =>
    d.filename.toLowerCase().includes(q) ||
    (d.content_type || '').toLowerCase().includes(q)
  )
})

const hasQuery = computed(() => searchQuery.value.trim().length > 0)

function toggleSelect(id: string) {
  const s = new Set(selectedIds.value)
  if (s.has(id)) { s.delete(id) } else { s.add(id) }
  selectedIds.value = s
}

function toggleSelectAll() {
  const target = hasQuery.value ? filteredDocuments.value.map(d => d.id) : documents.value.map(d => d.id)
  if (allSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(target)
  }
}

const allSelected = computed(() => {
  const target = hasQuery.value ? filteredDocuments.value : documents.value
  return target.length > 0 && selectedIds.value.size === target.length
})

const indeterminate = computed(() =>
  selectedIds.value.size > 0 && selectedIds.value.size < (hasQuery.value ? filteredDocuments.value : documents.value).length
)

async function fetchDocuments() {
  scrollTop = listRef.value?.scrollTop || 0
  isLoading.value = true
  error.value = ''
  try {
    documents.value = await listDocuments()
    emit('loaded', documents.value)
  } catch (err: any) {
    error.value = err.message || '加载文档失败'
  } finally {
    isLoading.value = false
    await nextTick()
    if (listRef.value) listRef.value.scrollTop = scrollTop
  }
}

function confirmDelete(id: string) {
  confirmDeleteIds.value = [id]
}

function confirmBatchDelete() {
  if (selectedIds.value.size === 0) return
  confirmDeleteIds.value = Array.from(selectedIds.value)
}

async function executeDelete() {
  const ids = confirmDeleteIds.value
  confirmDeleteIds.value = null
  if (!ids || ids.length === 0) return
  try {
    if (ids.length === 1) {
      await deleteDocument(ids[0])
    } else {
      await batchDeleteDocuments(ids)
    }
    selectedIds.value = new Set()
    emit('deleted')
  } catch (err: any) {
    error.value = err.message || '删除失败'
  }
}

function cancelDelete() { confirmDeleteIds.value = null }

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function setDocuments(data: any[]) {
  documents.value = data
  selectedIds.value = new Set()
  isLoading.value = false
}

defineExpose({ fetchDocuments, setDocuments })

onMounted(fetchDocuments)
</script>

<template>
  <div ref="listRef">
    <div class="flex items-center justify-between mb-3 gap-2 flex-wrap">
      <h3 class="text-sm font-medium">已上传文档</h3>
      <div class="flex items-center gap-2">
        <div class="relative">
          <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/50 pointer-events-none"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索文件名..."
            class="h-8 w-40 sm:w-52 rounded-md border border-border/60 bg-background pl-7 pr-7 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/30 transition-all"
          />
          <button
            v-if="hasQuery"
            @click="searchQuery = ''"
            class="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground/40 hover:text-muted-foreground transition-colors"
            title="清除搜索"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>
        <button
          v-if="auth.hasPermission('documents.delete') && selectedIds.size > 0"
          @click="confirmBatchDelete"
          class="inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs bg-destructive/10 text-destructive hover:bg-destructive/20 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
          删除 ({{ selectedIds.size }})
        </button>
      </div>
    </div>

    <div v-if="isLoading" class="flex justify-center py-8">
      <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>

    <div v-else-if="error" class="text-sm text-destructive py-4">{{ error }}</div>

    <div v-else-if="documents.length === 0" class="text-center text-muted-foreground text-sm py-8">暂无上传文档</div>

    <div v-else-if="hasQuery && filteredDocuments.length === 0" class="text-center text-muted-foreground text-sm py-8">未找到匹配的文档</div>

    <div v-else class="space-y-2">
      <div class="flex items-center gap-2 pb-1 text-xs text-muted-foreground border-b border-border">
        <label class="flex items-center gap-1.5 cursor-pointer select-none">
          <input
            type="checkbox"
            :checked="allSelected"
            :indeterminate="indeterminate"
            @change="toggleSelectAll"
            class="accent-primary"
          />
          <span>全选</span>
        </label>
      </div>

      <div
        v-for="(doc, idx) in filteredDocuments"
        :key="doc.id"
        class="flex items-center justify-between rounded-lg border border-border p-3 hover:bg-muted/30 transition-colors animate-fade-in"
        :class="{ 'border-primary/40 bg-primary/5': selectedIds.has(doc.id) }"
        :style="{ animationDelay: `${idx * 0.03}s` }"
      >
        <div class="flex items-center gap-3 min-w-0 flex-1">
          <input
            type="checkbox"
            :checked="selectedIds.has(doc.id)"
            @change="toggleSelect(doc.id)"
            class="shrink-0 accent-primary"
            @click.stop
          />
          <div class="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary">
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" /><polyline points="14 2 14 8 20 8" />
            </svg>
          </div>
          <div class="min-w-0">
            <p class="text-sm font-medium truncate">{{ doc.filename }}</p>
            <p class="text-xs text-muted-foreground">{{ doc.chunk_count }} 个文本块<span v-if="doc.size"> · {{ formatSize(doc.size) }}</span></p>
          </div>
        </div>
        <div class="flex items-center gap-1 shrink-0">
          <button @click="emit('viewDetail', doc.id)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" title="查看详情">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
            查看
          </button>
          <button v-if="auth.hasPermission('documents.delete')" @click="confirmDelete(doc.id)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors" title="删除">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /></svg>
            删除
          </button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      v-if="confirmDeleteIds"
      title="删除文档"
      :message="confirmDeleteIds.length === 1 ? '确定删除此文档？删除后文本块将从知识库中移除，不可恢复。' : `确定删除选中的 ${confirmDeleteIds.length} 个文档？删除后文本块将从知识库中移除，不可恢复。`"
      destructive
      @confirm="executeDelete"
      @cancel="cancelDelete"
    />
  </div>
</template>
