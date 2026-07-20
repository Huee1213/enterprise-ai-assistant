<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { marked, Renderer } from 'marked'
import type { Message } from '@/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const props = defineProps<{
  message: Message
  isStreaming?: boolean
  msgIndex?: number
  isAdmin?: boolean
  selectMode?: boolean
  selected?: boolean
}>()

const emit = defineEmits<{
  edit: [msgId: string, newContent: string]
  retry: [msgId: string]
  deleteMsg: [msgId: string]
  toggleSelect: [msgId: string]
}>()

const expandedSteps = ref<Set<string>>(new Set())
const editing = ref(false)
const editText = ref('')
const copied = ref(false)

// Language name mapping
const LANG_LABELS: Record<string, string> = {
  js: 'JavaScript', javascript: 'JavaScript', ts: 'TypeScript', typescript: 'TypeScript',
  py: 'Python', python: 'Python',
  java: 'Java',
  go: 'Go', golang: 'Go',
  rs: 'Rust', rust: 'Rust',
  cpp: 'C++', c: 'C', cs: 'C#', csharp: 'C#',
  rb: 'Ruby', ruby: 'Ruby',
  php: 'PHP',
  swift: 'Swift', kt: 'Kotlin', kotlin: 'Kotlin',
  sh: 'Shell', bash: 'Bash', zsh: 'Zsh',
  ps1: 'PowerShell', powershell: 'PowerShell', pwsh: 'PowerShell',
  cmd: 'CMD', bat: 'Batch',
  sql: 'SQL',
  html: 'HTML', xml: 'XML', json: 'JSON', yaml: 'YAML', yml: 'YAML',
  md: 'Markdown', markdown: 'Markdown',
  dockerfile: 'Dockerfile', docker: 'Docker',
  nginx: 'Nginx', conf: 'Config',
  diff: 'Diff',
  text: 'Text', plain: 'Plain',
}

function langLabel(lang: string): string {
  return LANG_LABELS[lang.toLowerCase()] || lang
}

// Custom marked renderer with enhanced code blocks
const renderer = new Renderer()
renderer.code = function ({ text, lang, escaped }) {
  const label = lang ? langLabel(lang) : 'Code'
  const id = `cb-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
  // Escape HTML in raw code text for safe display
  const code = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return `<div class="code-block group relative my-3 rounded-lg border border-border overflow-hidden bg-card">
    <div class="flex items-center justify-between px-3 py-1.5 bg-muted/60 border-b border-border text-[10px] text-muted-foreground">
      <span class="font-medium">${label}</span>
      <button
        onclick="(function(btn){
          var code = btn.closest('.code-block').querySelector('pre code');
          var text = code.textContent || code.innerText;
          navigator.clipboard.writeText(text).then(function(){
            btn.textContent = '已复制';
            btn.classList.add('text-green-500');
            setTimeout(function(){ btn.textContent = '复制'; btn.classList.remove('text-green-500'); }, 2000);
          });
        })(this)"
        class="code-copy opacity-0 group-hover:opacity-100 transition-opacity px-1.5 py-0.5 rounded hover:bg-muted-foreground/10"
      >复制</button>
    </div>
    <pre class="p-3 overflow-x-auto text-xs leading-relaxed"><code>${code}</code></pre>
  </div>`
}

marked.setOptions({ renderer })

async function copyContent() {
  if (!props.message.content) return
  try {
    await navigator.clipboard.writeText(props.message.content)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch { /* ignore */ }
}

const renderedContent = computed(() => {
  if (!props.message.content) return ''
  return marked.parse(props.message.content, { async: false }) as string
})

function toggleStep(stepIdx: number) {
  const key = `${props.message.id}-${stepIdx}`
  const next = new Set(expandedSteps.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedSteps.value = next
}

function isExpanded(stepIdx: number): boolean {
  return expandedSteps.value.has(`${props.message.id}-${stepIdx}`)
}

function startEdit() {
  editText.value = props.message.content
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  editText.value = ''
}

function handleRetry() {
  emit('retry', props.message.id)
}

function submitEdit() {
  const text = editText.value.trim()
  if (!text || text === props.message.content) {
    cancelEdit()
    return
  }
  editing.value = false
  emit('edit', props.message.id, text)
}

function handleEditKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submitEdit()
  }
  if (e.key === 'Escape') {
    cancelEdit()
  }
}

const isUser = computed(() => props.message.role === 'user')
const isAssistant = computed(() => props.message.role === 'assistant')

const latestStep = computed(() => {
  if (!props.message.steps || props.message.steps.length === 0) return null
  return props.message.steps[props.message.steps.length - 1]
})

const agentStatusText = computed(() => {
  if (!props.isStreaming) return '处理完成'
  const step = latestStep.value
  if (!step) return '思考中...'
  switch (step.action) {
    case 'llm_call':
      return '分析中...'
    case 'tool_execution':
      const out = (step.output || '').toLowerCase()
      if (out.includes('get_current_time') || out.includes('current time')) return '查询时间...'
      if (out.includes('knowledge_search') || out.includes('knowledge')) return '搜索知识库...'
      if (out.includes('web_search') || out.includes('web') || out.includes('search')) return '搜索网络...'
      if (out.includes('summarize') || out.includes('summary')) return '生成摘要...'
      return '处理中...'
    default:
      return '处理中...'
  }
})

</script>

<template>
  <div
    class="flex gap-3 group items-start"
    :class="[isUser ? 'flex-row-reverse' : 'flex-row', isUser ? 'animate-slide-in-right' : 'animate-fade-in-up']"
    :style="msgIndex != null ? { animationDelay: `${Math.min(msgIndex * 0.05, 0.3)}s` } : {}"
    @click="selectMode && emit('toggleSelect', message.id)"
    :role="selectMode ? 'button' : undefined"
  >
    <!-- Select checkbox mode -->
    <div v-if="selectMode" class="shrink-0 mt-2.5">
      <div class="w-4.5 h-4.5 rounded border flex items-center justify-center transition-colors cursor-pointer" :class="selected ? 'bg-primary border-primary' : 'border-border hover:border-muted-foreground'" style="width:18px;height:18px">
        <svg v-if="selected" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" class="text-primary-foreground"><polyline points="20 6 9 17 4 12"/></svg>
      </div>
    </div>
    <div v-else class="shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold mt-1 overflow-hidden"
      :class="isUser ? 'bg-primary/10 text-primary' : 'bg-secondary text-secondary-foreground'"
    >
      <img v-if="isUser && auth.user?.avatar_url" :src="auth.user.avatar_url" class="w-full h-full object-cover" @error="$event.target.style.display='none'" />
      <span v-else>{{ isUser ? (auth.user?.display_name || auth.user?.username || '我')[0] : 'AI' }}</span>
    </div>

    <div class="flex-1 max-w-[80%] flex flex-col gap-0.5" :class="isUser ? 'items-end' : 'items-start'">
      <div
        class="rounded-2xl px-4 py-3 relative w-fit min-w-[60px]"
        :class="isUser
          ? 'bg-primary/10 text-foreground rounded-tr-sm'
          : 'bg-card text-card-foreground border border-border rounded-tl-sm'"
      >
        <!-- Edit button for user messages -->
        <button
          v-if="isUser && !isStreaming && !editing && !selectMode"
          @click="startEdit"
          class="absolute -top-2 -right-2 opacity-0 group-hover:opacity-100 transition-opacity rounded-full bg-background border border-border p-1 shadow-sm hover:bg-muted"
          title="编辑问题"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-muted-foreground">
            <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
          </svg>
        </button>

        <!-- Edit mode for user messages -->
        <div v-if="isUser && editing">
          <textarea
            v-model="editText"
            @keydown="handleEditKeydown"
            class="w-full rounded-lg border border-input bg-background text-foreground p-2 text-sm resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[60px]"
            rows="3"
          />
          <div class="flex gap-2 mt-2 justify-end">
            <button
              @click="cancelEdit"
              class="text-xs px-3 py-1.5 rounded-md border border-border hover:bg-muted transition-colors"
            >
              取消
            </button>
            <button
              @click="submitEdit"
              class="text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
              :disabled="!editText.trim()"
            >
              重新提问
            </button>
          </div>
        </div>

        <!-- Streaming thinking indicator -->
        <div v-else-if="isStreaming && !message.content && !message.steps?.length" class="flex gap-1 py-2">
          <span class="w-2 h-2 rounded-full bg-muted-foreground/40 animate-pulse-dot" />
          <span class="w-2 h-2 rounded-full bg-muted-foreground/40 animate-pulse-dot" style="animation-delay: 0.2s" />
          <span class="w-2 h-2 rounded-full bg-muted-foreground/40 animate-pulse-dot" style="animation-delay: 0.4s" />
        </div>

        <!-- Agent status: simplified for employees, full for admins -->
        <div v-if="!isUser && message.steps && message.steps.length > 0" class="mb-3">
          <!-- Simplified status for employees -->
          <div v-if="!isAdmin" class="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs bg-muted/40">
            <span v-if="isStreaming" class="shrink-0">
              <svg class="animate-spin text-primary" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
            </span>
            <span v-else class="shrink-0 text-green-500">✓</span>
            <span class="text-muted-foreground">{{ agentStatusText }}</span>
          </div>
          <!-- Full steps for admins -->
          <div v-else class="space-y-1">
            <button
              v-for="(step, i) in message.steps"
              :key="i"
              @click="toggleStep(i)"
              class="w-full text-left rounded-lg px-2.5 py-1.5 text-xs font-mono transition-all animate-slide-in"
              :style="{ animationDelay: `${i * 0.05}s` }"
              :class="[
                i === message.steps.length - 1 && isStreaming
                  ? 'bg-primary/5 border border-primary/20 animate-pulse'
                  : isExpanded(i)
                    ? 'bg-muted border border-border'
                    : 'bg-muted/40 hover:bg-muted/70 border border-transparent',
              ]"
            >
              <div class="flex items-center gap-2">
                <span v-if="step.action === 'llm_call'" class="shrink-0">
                  <svg v-if="i === message.steps.length - 1 && isStreaming" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary animate-spin"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </span>
                <span v-else class="shrink-0">
                  <svg v-if="i === message.steps.length - 1 && isStreaming" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-accent-foreground animate-spin"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-accent-foreground"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
                </span>
                <span class="flex-1 text-muted-foreground">
                  {{ step.action === 'llm_call' ? 'LLM 调用' : '工具执行' }}
                  <span class="text-muted-foreground/50">#{{ step.step }}</span>
                </span>
                <svg class="shrink-0 text-muted-foreground/40 transition-transform duration-200" :class="isExpanded(i) ? 'rotate-180' : ''" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
                <span v-if="i === message.steps.length - 1 && isStreaming" class="flex gap-0.5">
                  <span class="w-1 h-1 rounded-full bg-muted-foreground/50 animate-pulse-dot" />
                  <span class="w-1 h-1 rounded-full bg-muted-foreground/50 animate-pulse-dot" style="animation-delay: 0.2s" />
                  <span class="w-1 h-1 rounded-full bg-muted-foreground/50 animate-pulse-dot" style="animation-delay: 0.4s" />
                </span>
              </div>
              <div v-if="isExpanded(i)" class="mt-2 pt-2 border-t border-border/40 space-y-1.5">
                <div>
                  <div class="flex items-center gap-1 text-muted-foreground mb-0.5">
                    <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 7 4 4 20 4 20 7" /><line x1="9" x2="15" y1="20" y2="20" /><line x1="12" x2="12" y1="4" y2="20" /></svg>
                    <span class="text-[10px] font-medium">输入</span>
                  </div>
                  <div class="p-1.5 rounded bg-background/60 text-muted-foreground text-[10px] break-words whitespace-pre-wrap max-h-16 overflow-y-auto leading-relaxed">{{ step.input.slice(0, 300) || '—' }}</div>
                </div>
                <div>
                  <div class="flex items-center gap-1 text-muted-foreground mb-0.5">
                    <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>
                    <span class="text-[10px] font-medium">输出</span>
                  </div>
                  <div class="p-1.5 rounded bg-background/60 text-muted-foreground text-[10px] break-words whitespace-pre-wrap max-h-16 overflow-y-auto leading-relaxed">{{ step.output.slice(0, 300) || '—' }}</div>
                </div>
              </div>
            </button>
          </div>
        </div>

        <!-- Model reasoning / thinking (collapsible) -->
        <div v-if="!isUser && message.reasoning" class="mb-2">
          <details class="bg-muted/40 rounded-lg p-2">
            <summary class="text-[11px] font-mono text-muted-foreground cursor-pointer hover:text-foreground select-none">
              <span class="flex items-center gap-1.5">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
                模型思考过程
              </span>
            </summary>
            <div class="mt-1.5 text-[11px] text-muted-foreground leading-relaxed whitespace-pre-wrap">{{ message.reasoning }}</div>
          </details>
        </div>

        <!-- User message text (markdown) -->
        <div v-if="!editing && isUser" class="markdown-content text-sm leading-relaxed max-w-none w-fit" v-html="renderedContent" />

        <!-- Assistant message text (markdown) -->
        <div v-if="!editing && !isUser" class="markdown-content text-sm leading-relaxed max-w-none w-fit" v-html="renderedContent" />

        <div v-if="message.sources && message.sources.length > 0 && !isStreaming" class="mt-3 pt-3 border-t border-border/50">
          <p class="text-xs font-medium text-muted-foreground mb-2">📎 来源:</p>
          <div class="flex flex-wrap gap-2">
            <span v-for="(source, i) in message.sources" :key="i" class="text-xs bg-muted px-2 py-1 rounded-md text-muted-foreground">{{ source.source }}</span>
          </div>
        </div>

      </div>

      <p class="text-[10px] text-muted-foreground/60 px-1" :class="isUser ? 'text-right' : 'text-left'">
        {{ new Date(message.timestamp).toLocaleTimeString() }}
      </p>

        <!-- Action buttons (below time) -->
      <div v-if="!isStreaming && message.content && !selectMode" class="flex items-center gap-1 px-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button v-if="!isUser" @click="handleRetry" class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors" title="重新生成">
          <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          重新生成
        </button>
        <button @click="copyContent" class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors" title="复制">
          <svg v-if="!copied" xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-green-500"><polyline points="20 6 9 17 4 12"/></svg>
          {{ copied ? '已复制' : '复制' }}
        </button>
        <button @click="emit('deleteMsg', message.id)" class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors" title="删除">
          <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
          删除
        </button>
      </div>
    </div>
  </div>
</template>
