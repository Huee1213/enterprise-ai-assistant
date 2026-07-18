<script setup lang="ts">
import { ref } from 'vue'
import DocumentUpload from '@/components/documents/DocumentUpload.vue'
import DocumentList from '@/components/documents/DocumentList.vue'

const documentListRef = ref<InstanceType<typeof DocumentList> | null>(null)

function onUploaded() {
  documentListRef.value?.fetchDocuments()
}
</script>

<template>
  <div class="h-full overflow-y-auto">
    <div class="max-w-3xl mx-auto p-6 space-y-8">
      <div>
        <h1 class="text-2xl font-bold">文档管理</h1>
        <p class="text-sm text-muted-foreground mt-1">
          上传企业文档以构建知识库
        </p>
      </div>

      <div class="rounded-xl border border-border bg-card p-6">
        <h2 class="text-sm font-semibold mb-4">上传文档</h2>
        <DocumentUpload @uploaded="onUploaded" />
      </div>

      <div class="rounded-xl border border-border bg-card p-6">
        <DocumentList ref="documentListRef" />
      </div>
    </div>
  </div>
</template>
