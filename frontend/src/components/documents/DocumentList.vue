<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { listDocuments, deleteDocument } from '@/api/documents'
import type { DocumentInfo } from '@/types'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const emit = defineEmits<{
  viewDetail: [docId: string]
  deleted: []
}>()

const documents = ref<DocumentInfo[]>([])
const isLoading = ref(true)
const error = ref('')
const confirmDeleteId = ref<string | null>(null)
const listRef = ref<HTMLDivElement | null>(null)
let scrollTop = 0

async function fetchDocuments() {
  scrollTop = listRef.value?.scrollTop || 0
  isLoading.value = true
  error.value = ''
  try {
    documents.value = await listDocuments()
  } catch (err: any) {
    error.value = err.message || '加载文档失败'
  } finally {
    isLoading.value = false
    await nextTick()
    if (listRef.value) listRef.value.scrollTop = scrollTop
  }
}

function confirmDelete(id: string) {
  confirmDeleteId.value = id
}

async function executeDelete() {
  const id = confirmDeleteId.value
  confirmDeleteId.value = null
  if (!id) return
  try {
    await deleteDocument(id)
    await fetchDocuments()
    emit('deleted')
  } catch (err: any) {
    error.value = err.message || '删除失败'
  }
}

function cancelDelete() { confirmDeleteId.value = null }

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

defineExpose({ fetchDocuments })

onMounted(fetchDocuments)
</script>

<template>
  <div ref="listRef">
    <h3 class="text-sm font-medium mb-3">已上传文档</h3>

    <div v-if="isLoading" class="flex justify-center py-8">
      <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>

    <div v-else-if="error" class="text-sm text-destructive py-4">{{ error }}</div>

    <div v-else-if="documents.length === 0" class="text-center text-muted-foreground text-sm py-8">暂无上传文档</div>

    <div v-else class="space-y-2">
      <div
        v-for="(doc, idx) in documents"
        :key="doc.id"
        class="flex items-center justify-between rounded-lg border border-border p-3 hover:bg-muted/30 transition-colors animate-fade-in"
        :style="{ animationDelay: `${idx * 0.03}s` }"
      >
        <div class="flex items-center gap-3 min-w-0 flex-1">
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
          <button @click="confirmDelete(doc.id)" class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors" title="删除">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" /></svg>
            删除
          </button>
        </div>
      </div>
    </div>

    <ConfirmDialog v-if="confirmDeleteId" title="删除文档" message="确定删除此文档？删除后文本块将从知识库中移除，不可恢复。" destructive @confirm="executeDelete" @cancel="cancelDelete" />
  </div>
</template>
