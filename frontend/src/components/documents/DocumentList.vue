<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listDocuments, deleteDocument } from '@/api/documents'
import type { DocumentInfo } from '@/types'

const documents = ref<DocumentInfo[]>([])
const isLoading = ref(true)
const error = ref('')

async function fetchDocuments() {
  isLoading.value = true
  error.value = ''
  try {
    documents.value = await listDocuments()
  } catch (err: any) {
    error.value = err.message || '加载文档失败'
  } finally {
    isLoading.value = false
  }
}

async function handleDelete(id: string) {
  try {
    await deleteDocument(id)
    await fetchDocuments()
  } catch (err: any) {
    error.value = err.message || '删除失败'
  }
}

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
  <div>
    <h3 class="text-sm font-medium mb-3">已上传文档</h3>

    <div v-if="isLoading" class="flex justify-center py-8">
      <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>

    <div v-else-if="error" class="text-sm text-destructive py-4">{{ error }}</div>

    <div v-else-if="documents.length === 0" class="text-center text-muted-foreground text-sm py-8">
      暂无上传文档
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="(doc, idx) in documents"
        :key="doc.id"
        class="flex items-center justify-between rounded-lg border border-border p-3 hover:bg-muted/30 transition-colors animate-fade-in"
        :style="{ animationDelay: `${idx * 0.05}s` }"
      >
        <div class="flex items-center gap-3 min-w-0">
          <div class="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary">
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          </div>
          <div class="min-w-0">
            <p class="text-sm font-medium truncate">{{ doc.filename }}</p>
            <p class="text-xs text-muted-foreground">
              {{ doc.chunk_count }} 个文本块
              <span v-if="doc.size"> · {{ formatSize(doc.size) }}</span>
            </p>
          </div>
        </div>
        <button
          @click="handleDelete(doc.id)"
          class="shrink-0 inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors hover:bg-destructive/10 hover:text-destructive h-8 w-8"
          title="删除"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 6h18" />
            <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
            <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>
