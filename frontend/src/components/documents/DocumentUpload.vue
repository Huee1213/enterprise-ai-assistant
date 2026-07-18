<script setup lang="ts">
import { ref } from 'vue'
import { uploadDocument } from '@/api/documents'

const emit = defineEmits<{
  uploaded: []
}>()

const isDragging = ref(false)
const isUploading = ref(false)
const error = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const ACCEPTED_TYPES = '.txt,.md,.pdf,.docx,.csv'

function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function onDragLeave() {
  isDragging.value = false
}

async function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (files?.length) {
    await handleFile(files[0])
  }
}

async function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) {
    await handleFile(input.files[0])
    input.value = ''
  }
}

async function handleFile(file: File) {
  error.value = ''
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  if (!ACCEPTED_TYPES.includes(ext)) {
    error.value = `不支持的文件类型: ${ext}。支持的类型: ${ACCEPTED_TYPES}`
    return
  }

  isUploading.value = true
  try {
    const result = await uploadDocument(file)
    if (result.status === 'success') {
      emit('uploaded')
    } else {
      error.value = result.message
    }
  } catch (err: any) {
    error.value = err.message || '上传失败'
  } finally {
    isUploading.value = false
  }
}
</script>

<template>
  <div>
    <div
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
      class="border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer"
      :class="isDragging
        ? 'border-primary bg-primary/5'
        : 'border-border hover:border-primary/50 hover:bg-muted/30'"
      @click="fileInput?.click()"
    >
      <input
        ref="fileInput"
        type="file"
        :accept="ACCEPTED_TYPES"
        class="hidden"
        @change="onFileSelect"
      />

      <div v-if="isUploading" class="flex flex-col items-center gap-2">
        <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <p class="text-sm text-muted-foreground">正在上传并处理...</p>
      </div>

      <div v-else class="flex flex-col items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-muted-foreground">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" x2="12" y1="3" y2="15" />
        </svg>
        <p class="text-sm font-medium">拖拽文件到此处，或点击上传</p>
        <p class="text-xs text-muted-foreground">PDF、DOCX、TXT、MD、CSV（最大 10MB）</p>
      </div>
    </div>

    <p v-if="error" class="mt-2 text-sm text-destructive">{{ error }}</p>
  </div>
</template>
