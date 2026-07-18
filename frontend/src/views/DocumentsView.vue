<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { marked } from 'marked'
import * as mammoth from 'mammoth'
import axios from 'axios'
import apiClient from '@/api/client'
import DocumentUpload from '@/components/documents/DocumentUpload.vue'
import DocumentList from '@/components/documents/DocumentList.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const documentListRef = ref<InstanceType<typeof DocumentList> | null>(null)
const stats = ref({ total_docs: 0, total_chunks: 0 })
const pdfBlobUrl = ref('')
const loadingPdf = ref(false)
const alertMsg = ref('')
const docxHtml = ref('')
const loadingDocx = ref(false)
const csvRows = ref<string[][]>([])
const csvHeaders = ref<string[]>([])

function onUploaded() { documentListRef.value?.fetchDocuments(); refreshStats() }

const detailDoc = ref<any>(null)
const detailTab = ref<'original' | 'chunks'>('original')
const loadingDetail = ref(false)

const isMarkdown = computed(() => detailDoc.value?.content_type?.toLowerCase() === 'md')
const isPdf = computed(() => detailDoc.value?.content_type?.toLowerCase() === 'pdf')
const isDocx = computed(() => detailDoc.value?.content_type?.toLowerCase() === 'docx')
const isCsv = computed(() => detailDoc.value?.content_type?.toLowerCase() === 'csv')

const renderedMd = computed(() => {
  if (!detailDoc.value?.original_content || !isMarkdown.value) return ''
  return marked.parse(detailDoc.value.original_content, { async: false }) as string
})

function parseCsv(text: string) {
  const lines = text.trim().split('\n').filter(Boolean)
  if (lines.length === 0) return
  csvHeaders.value = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''))
  csvRows.value = lines.slice(1).map(line => line.split(',').map(c => c.trim().replace(/^"|"$/g, '')))
}

async function loadDocxHtml(docId: string) {
  loadingDocx.value = true
  try {
    const token = localStorage.getItem('token')
    const resp = await axios.get(`/api/documents/${docId}/file`, {
      responseType: 'arraybuffer', headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    const result = await mammoth.convertToHtml({ arrayBuffer: resp.data })
    docxHtml.value = result.value
  } catch { docxHtml.value = '' }
  loadingDocx.value = false
}

async function viewDetail(docId: string) {
  loadingDetail.value = true
  pdfBlobUrl.value = ''
  docxHtml.value = ''
  csvRows.value = []
  csvHeaders.value = []
  try {
    const { data } = await apiClient.get(`/documents/${docId}`)
    detailDoc.value = data
    detailTab.value = 'original'
    if (data.content_type?.toLowerCase() === 'pdf') loadPdfBlob(docId)
    if (data.content_type?.toLowerCase() === 'docx') loadDocxHtml(docId)
    if (data.content_type?.toLowerCase() === 'csv') parseCsv(data.original_content)
  } catch (err: any) { alertMsg.value = err.message || '加载失败' }
  loadingDetail.value = false
}

async function loadPdfBlob(docId: string) {
  loadingPdf.value = true
  try {
    const token = localStorage.getItem('token')
    const resp = await axios.get(`/api/documents/${docId}/file`, {
      responseType: 'blob', headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    pdfBlobUrl.value = URL.createObjectURL(resp.data)
  } catch { pdfBlobUrl.value = '' }
  loadingPdf.value = false
}

function closeDetail() {
  if (pdfBlobUrl.value) URL.revokeObjectURL(pdfBlobUrl.value)
  pdfBlobUrl.value = ''; docxHtml.value = ''; csvRows.value = []; csvHeaders.value = [];
  detailDoc.value = null
}

async function refreshStats() {
  try {
    const { data } = await apiClient.get('/documents/list')
    stats.value.total_docs = data.length
    stats.value.total_chunks = data.reduce((s: number, d: any) => s + (d.chunk_count || 0), 0)
  } catch {}
}

async function downloadFile() {
  if (!detailDoc.value) return
  try {
    const token = localStorage.getItem('token')
    const resp = await axios.get(`/api/documents/${detailDoc.value.id}/file`, {
      responseType: 'blob', headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    const url = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = url; a.download = detailDoc.value.filename; a.click()
    URL.revokeObjectURL(url)
  } catch {}
}

onMounted(refreshStats)
</script>

<template>
  <div class="h-full overflow-y-auto">
    <div class="max-w-4xl mx-auto p-6 space-y-6">
      <div class="flex items-center justify-between">
        <div><h1 class="text-2xl font-bold">文档管理</h1><p class="text-sm text-muted-foreground mt-0.5">上传企业文档以构建知识库</p></div>
        <div class="flex items-center gap-4 text-xs text-muted-foreground">
          <span>文档: <strong class="text-foreground">{{ stats.total_docs }}</strong></span>
          <span>文本块: <strong class="text-foreground">{{ stats.total_chunks }}</strong></span>
        </div>
      </div>

      <div class="rounded-xl border border-border bg-card p-6">
        <h2 class="text-sm font-semibold mb-4">上传文档</h2>
        <DocumentUpload @uploaded="onUploaded" />
      </div>

      <div class="rounded-xl border border-border bg-card p-6">
        <DocumentList ref="documentListRef" @view-detail="viewDetail" @deleted="refreshStats" />
      </div>

      <Teleport to="body">
        <div v-if="detailDoc" class="fixed inset-0 z-[9999] flex items-start justify-center bg-black/40 backdrop-blur-sm p-4 pt-12 overflow-y-auto" @click="closeDetail">
          <div class="bg-card border border-border rounded-xl w-full max-w-3xl shadow-xl animate-scale-in overflow-hidden" @click.stop>
            <div class="px-5 py-4 border-b border-border flex items-center justify-between">
              <div class="min-w-0">
                <h2 class="text-sm font-semibold truncate">{{ detailDoc.filename }}</h2>
                <p class="text-[11px] text-muted-foreground mt-0.5">
                  {{ (detailDoc.size / 1024).toFixed(1) }} KB · {{ detailDoc.chunk_count }} 个文本块 · {{ detailDoc.content_type?.toUpperCase() }}
                  <button @click="downloadFile" class="ml-2 text-primary hover:underline text-[10px]">[下载原文件]</button>
                </p>
              </div>
              <button @click="closeDetail" class="shrink-0 rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" title="关闭">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
              </button>
            </div>

            <div class="flex border-b border-border px-5">
              <button @click="detailTab = 'original'" class="px-3 py-2 text-xs font-medium border-b-2 transition-colors" :class="detailTab === 'original' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'">原始内容</button>
              <button @click="detailTab = 'chunks'" class="px-3 py-2 text-xs font-medium border-b-2 transition-colors" :class="detailTab === 'chunks' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'">文本块 ({{ detailDoc.chunks?.length || 0 }})</button>
            </div>

            <div class="p-5 max-h-[65vh] overflow-y-auto">
              <div v-if="loadingDetail" class="text-center py-8 text-sm text-muted-foreground">加载中...</div>

              <!-- Original content -->
              <template v-if="detailTab === 'original' && !loadingDetail">
                <!-- Markdown -->
                <div v-if="isMarkdown" class="markdown-content text-sm" v-html="renderedMd" />

                <!-- PDF: iframe inline -->
                <div v-else-if="isPdf" class="flex flex-col items-center">
                  <div v-if="loadingPdf" class="py-12 text-sm text-muted-foreground">加载 PDF 中...</div>
                  <iframe v-else-if="pdfBlobUrl" :src="pdfBlobUrl" class="w-full h-[60vh] rounded-lg border border-border" />
                  <div v-else class="py-12 text-sm text-muted-foreground">PDF 无法预览 · <button @click="downloadFile" class="text-primary hover:underline">下载文件</button></div>
                  <p class="text-xs text-muted-foreground mt-2">PDF 内联预览 · <button @click="downloadFile" class="text-primary hover:underline">下载原文件</button></p>
                </div>

                <!-- CSV: table -->
                <div v-else-if="isCsv" class="overflow-x-auto">
                  <table class="w-full text-xs border-collapse">
                    <thead>
                      <tr class="bg-muted/50">
                        <th v-for="(h, i) in csvHeaders" :key="i" class="border border-border px-3 py-2 text-left font-medium whitespace-nowrap">{{ h }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, ri) in csvRows" :key="ri" class="hover:bg-muted/20">
                        <td v-for="(cell, ci) in row" :key="ci" class="border border-border px-3 py-1.5 whitespace-nowrap">{{ cell }}</td>
                      </tr>
                    </tbody>
                  </table>
                  <p class="text-xs text-muted-foreground mt-2">{{ csvRows.length }} 行数据 · <button @click="downloadFile" class="text-primary hover:underline">下载原文件</button></p>
                </div>

                <!-- DOCX: mammoth HTML preview -->
                <div v-else-if="isDocx" class="space-y-3">
                  <div v-if="loadingDocx" class="py-8 text-sm text-muted-foreground text-center">转换 DOCX 中...</div>
                  <div v-else-if="docxHtml" class="docx-preview text-sm leading-relaxed" v-html="docxHtml" />
                  <div v-else class="rounded-lg bg-muted/20 border border-border p-4 text-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-muted-foreground mx-auto mb-2"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
                    <p class="text-sm font-medium mb-1">DOCX 文件</p>
                    <button @click="downloadFile" class="rounded-lg bg-primary text-primary-foreground px-4 py-1.5 text-xs hover:bg-primary/90 transition-colors">下载原文件</button>
                  </div>
                </div>

                <!-- Plain text -->
                <pre v-else class="text-xs leading-relaxed whitespace-pre-wrap font-sans text-foreground/90">{{ detailDoc.original_content }}</pre>
              </template>

              <!-- Chunks -->
              <template v-if="detailTab === 'chunks' && !loadingDetail">
                <div v-if="!detailDoc.chunks || detailDoc.chunks.length === 0" class="text-center py-8 text-sm text-muted-foreground">暂无文本块数据（重新上传文档后可查看）</div>
                <div v-else class="space-y-3">
                  <div v-for="chunk in detailDoc.chunks" :key="chunk.index" class="rounded-lg border border-border p-3">
                    <div class="flex items-center gap-2 mb-1.5">
                      <span class="text-[10px] font-mono bg-muted px-1.5 py-0.5 rounded text-muted-foreground">#{{ chunk.index }}</span>
                      <span class="text-[10px] text-muted-foreground">{{ chunk.content?.length || 0 }} 字符</span>
                    </div>
                    <p class="text-xs leading-relaxed text-foreground/85 whitespace-pre-wrap">{{ chunk.content || '(空)' }}</p>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </Teleport>

    <ConfirmDialog v-if="alertMsg" title="提示" :message="alertMsg" @confirm="alertMsg = ''" @cancel="alertMsg = ''" />
    </div>
  </div>
</template>
