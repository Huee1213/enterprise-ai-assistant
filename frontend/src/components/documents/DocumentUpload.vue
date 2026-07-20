<script setup lang="ts">
import { ref, computed } from 'vue'
import { uploadDocument, uploadDocumentsBulk } from '@/api/documents'
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()

const emit = defineEmits<{
  uploaded: []
}>()

const isDragging = ref(false)
const isUploading = ref(false)
const error = ref('')
const progress = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const ACCEPTED_TYPES = '.txt,.md,.pdf,.docx,.csv'
const MAX_SIZE = 500 * 1024 * 1024

async function onDragOver(e: DragEvent) { e.preventDefault(); isDragging.value = true }
function onDragLeave() { isDragging.value = false }

async function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (files?.length) await handleFiles(Array.from(files))
}

async function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) {
    await handleFiles(Array.from(input.files))
    input.value = ''
  }
}

function validateFiles(files: File[]): File[] {
  const valid: File[] = []
  for (const f of files) {
    const ext = '.' + f.name.split('.').pop()?.toLowerCase()
    if (!ACCEPTED_TYPES.includes(ext)) {
      error.value = `不支持的类型: ${ext}`
      continue
    }
    if (f.size > MAX_SIZE) {
      error.value = `文件过大: ${f.name} (>500MB)`
      continue
    }
    valid.push(f)
  }
  return valid
}

async function handleFiles(files: File[]) {
  error.value = ''
  const valid = validateFiles(files)
  if (valid.length === 0) return

  isUploading.value = true
  let ok = 0, fail = 0

  if (valid.length === 1) {
    progress.value = '正在上传并处理...'
    try {
      const r = await uploadDocument(valid[0])
        if (r.status === 'success') { ok++ } else { fail++ }
      if (r.status !== 'success') { error.value = r.message }
    } catch (err: any) { error.value = err.message || '上传失败'; fail++ }
  } else {
    progress.value = `正在上传 ${valid.length} 个文件...`
    try {
      const r = await uploadDocumentsBulk(valid)
      ok = r.success; fail = r.failed
      progress.value = `完成: ${ok} 成功, ${fail} 失败`
    } catch (err: any) { error.value = err.message || '批量上传失败'; fail = valid.length }
  }

  isUploading.value = false
  progress.value = ''
  if (ok > 0) emit('uploaded')
}
</script>

<template>
  <div>
    <div v-if="auth.hasPermission('documents.upload')"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
      class="border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer"
      :class="isDragging ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50 hover:bg-muted/30'"
      @click="fileInput?.click()"
    >
      <input ref="fileInput" type="file" :accept="ACCEPTED_TYPES" multiple class="hidden" @change="onFileSelect" />

      <div v-if="isUploading" class="flex flex-col items-center gap-2">
        <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <p class="text-sm text-muted-foreground">{{ progress || '正在上传并处理...' }}</p>
      </div>

      <div v-else class="flex flex-col items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-muted-foreground">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" x2="12" y1="3" y2="15" />
        </svg>
        <p class="text-sm font-medium">拖拽文件到此处，或点击上传</p>
        <p class="text-xs text-muted-foreground">PDF、DOCX、TXT、MD、CSV（支持多文件，单文件最大 500MB）</p>
      </div>
    </div>

    <p v-if="error" class="mt-2 text-sm text-destructive">{{ error }}</p>
    <div v-else-if="!auth.hasPermission('documents.upload')" class="rounded-xl border-2 border-dashed border-border p-8 text-center">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="mx-auto mb-2 text-muted-foreground/40"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      <p class="text-sm text-muted-foreground">没有上传权限</p>
    </div>
  </div>
</template>
