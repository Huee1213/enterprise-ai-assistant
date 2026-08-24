<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import type { AgentStep, Message } from '@/types'

const FOLLOW_LATEST = '__latest__'
const props = withDefaults(defineProps<{ followMsgId?: string }>(), { followMsgId: FOLLOW_LATEST })
const emit = defineEmits<{ followChange: [msgId: string] }>()

const chat = useChatStore()

type FilterMode = 'all' | 'llm' | 'tool'
interface TimelineItem {
  key: string
  step: AgentStep
  userText: string
  turnStart: boolean
  isLive: boolean
  gapS: string | null
  timeStr: string
}

const filterMode = ref<FilterMode>('all')
const bodyRef = ref<HTMLElement | null>(null)
const detail = ref<TimelineItem | null>(null)
const copied = ref<'input' | 'output' | null>(null)
let copyTimer: ReturnType<typeof setTimeout> | null = null

// Assistant messages that recorded Agent steps (chronological).
const stepMessages = computed<Message[]>(() =>
  chat.messages.filter(m => m.role === 'assistant' && m.steps && m.steps.length > 0)
)

// Message whose steps the panel should display.
const effectiveMsg = computed<Message | null>(() => {
  const pinned = props.followMsgId !== FOLLOW_LATEST
    ? stepMessages.value.find(m => m.id === props.followMsgId)
    : undefined
  return pinned || stepMessages.value[stepMessages.value.length - 1] || null
})
const isFollowingLatest = computed(() => effectiveMsg.value !== null &&
  (props.followMsgId === FOLLOW_LATEST || !stepMessages.value.some(m => m.id === props.followMsgId)))

// Select value: keep the raw pinned id when valid, else the auto-latest marker.
const selectValue = computed(() =>
  stepMessages.value.some(m => m.id === props.followMsgId) ? props.followMsgId : FOLLOW_LATEST
)
const isLiveTurn = computed(() =>
  chat.isStreaming && effectiveMsg.value !== null &&
  effectiveMsg.value.id === (chat.messages[chat.messages.length - 1]?.id)
)

// Selector options (newest first).
const msgOptions = computed(() => {
  const opts: { value: string; label: string }[] = [
    { value: FOLLOW_LATEST, label: '跟随最新（自动）' },
  ]
  const msgs = [...stepMessages.value].reverse()
  msgs.forEach((m, i) => {
    const q = precedingUserText(m)
    const qShort = q.length > 14 ? q.slice(0, 14) + '…' : (q || '(无提问)')
    opts.push({ value: m.id, label: `消息 ${stepMessages.value.length - i} · ${qShort}` })
  })
  return opts
})

function msgIndexLabel(m: Message): string {
  const idx = stepMessages.value.findIndex(x => x.id === m.id)
  return idx >= 0 ? `消息 ${idx + 1}` : ''
}

function precedingUserText(m: Message): string {
  const idx = chat.messages.indexOf(m)
  for (let i = idx - 1; i >= 0; i--) {
    if (chat.messages[i].role === 'user') {
      return (chat.messages[i].content || '').replace(/\s+/g, ' ').trim()
    }
  }
  return ''
}

// Timeline limited to the followed message's steps.
const timeline = computed<TimelineItem[]>(() => {
  const m = effectiveMsg.value
  if (!m || !m.steps) return []
  const userText = precedingUserText(m)
  let lastTs: number | null = null
  return m.steps.map((st, si) => {
    const prevTs = lastTs
    lastTs = typeof st.ts === 'number' ? st.ts : (lastTs ?? null)
    const gapS = prevTs != null && lastTs != null && lastTs > prevTs
      ? `${(lastTs - prevTs).toFixed(1)}s` : null
    return {
      key: `${m.id}-${si}`,
      step: st,
      userText,
      turnStart: si === 0,
      isLive: isLiveTurn.value && si === (m.steps?.length || 0) - 1,
      gapS,
      timeStr: typeof st.ts === 'number'
        ? new Date(st.ts * 1000).toLocaleTimeString('zh-CN', { hour12: false }) : '',
    }
  })
})

const filteredTimeline = computed(() =>
  timeline.value.filter(i => {
    if (filterMode.value === 'llm') return i.step.action === 'llm_call'
    if (filterMode.value === 'tool') return i.step.action === 'tool_execution'
    return true
  })
)
const llmCount = computed(() => timeline.value.filter(i => i.step.action === 'llm_call').length)
const toolCount = computed(() => timeline.value.filter(i => i.step.action === 'tool_execution').length)

function isLlm(item: TimelineItem): boolean { return item.step.action === 'llm_call' }

function pretty(text: string): string {
  const t = (text || '').trim()
  if (!t) return '—'
  try { return JSON.stringify(JSON.parse(t), null, 2) } catch { return t }
}
function oneLine(text: string, n = 90): string {
  return pretty(text).replace(/\s+/g, ' ').trim().slice(0, n) || '—'
}

function setFollow(id: string) { emit('followChange', id) }
function followLatest() { emit('followChange', FOLLOW_LATEST) }

function openDetail(item: TimelineItem) { detail.value = item }
function closeDetail() { detail.value = null }

async function copyText(which: 'input' | 'output', text: string) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = which
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => { copied.value = null }, 1600)
  } catch { /* ignore */ }
}

// Auto-scroll while the followed message is streaming.
watch(
  () => [chat.isStreaming, effectiveMsg.value?.id, timeline.value.length],
  () => {
    if (chat.isStreaming && isLiveTurn.value) {
      nextTick(() => {
        const el = bodyRef.value
        if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
      })
    }
  }
)

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && detail.value) detail.value = null
}
onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  if (copyTimer) clearTimeout(copyTimer)
})
</script>

<template>
  <div class="flex flex-col h-full min-h-0">
    <!-- Panel header -->
    <div class="px-3 py-3 border-b border-border shrink-0">
      <div class="flex items-center gap-2">
        <h2 class="text-sm font-semibold flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-primary shrink-0"><circle cx="12" cy="12" r="10"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 18V6"/></svg>
          Agent 调试
        </h2>
        <span v-if="effectiveMsg" class="ml-auto text-[10px] font-normal text-muted-foreground bg-muted px-1.5 py-0.5 rounded-full shrink-0">{{ timeline.length }} 步</span>
      </div>

      <!-- Message selector: follow a specific message or auto latest -->
      <div v-if="stepMessages.length" class="mt-2 flex items-center gap-1.5">
        <div class="relative flex-1 min-w-0">
          <select
            :value="selectValue"
            @change="setFollow(($event.target as HTMLSelectElement).value)"
            class="w-full appearance-none rounded-md border border-border bg-background pl-2 pr-7 py-1.5 text-[11px] text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 truncate"
          >
            <option v-for="o in msgOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
          </select>
          <svg class="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground/50" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
        </div>
        <button
          v-if="!isFollowingLatest"
          @click="followLatest"
          class="shrink-0 inline-flex items-center gap-1 rounded-md border border-border px-2 py-1.5 text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title="回到最新消息"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 14 12 22 20 14"/><polyline points="4 2 12 10 20 2"/></svg>
          跟最新
        </button>
      </div>

      <!-- Filter chips -->
      <div v-if="timeline.length" class="flex items-center gap-1 mt-2">
        <button @click="filterMode = 'all'" class="px-2 py-0.5 rounded-md text-[11px] font-medium transition-colors"
          :class="filterMode === 'all' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground'">全部 {{ timeline.length }}</button>
        <button @click="filterMode = 'llm'" class="px-2 py-0.5 rounded-md text-[11px] font-medium transition-colors"
          :class="filterMode === 'llm' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground'">LLM {{ llmCount }}</button>
        <button @click="filterMode = 'tool'" class="px-2 py-0.5 rounded-md text-[11px] font-medium transition-colors"
          :class="filterMode === 'tool' ? 'bg-accent text-accent-foreground' : 'bg-muted text-muted-foreground hover:text-foreground'">工具 {{ toolCount }}</button>
      </div>
    </div>

    <!-- Panel body -->
    <div ref="bodyRef" class="flex-1 overflow-y-auto p-3 min-h-0">
      <div v-if="stepMessages.length === 0" class="flex flex-col items-center justify-center text-center text-muted-foreground text-sm py-12">
        <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="mb-2 opacity-60"><circle cx="12" cy="12" r="10"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 18V6"/></svg>
        暂无 Agent 活动
        <p class="text-[11px] text-muted-foreground/60 mt-1 px-6">发送问题后，Agent 的每次 LLM 决策与工具执行会实时显示在这里</p>
      </div>

      <div v-else-if="timeline.length === 0" class="flex flex-col items-center justify-center text-center text-muted-foreground text-sm py-12">
        该消息没有 Agent 步骤
        <p class="text-[11px] text-muted-foreground/60 mt-1 px-6">从上方选择其他消息，或点击聊天中的消息状态条进行定位</p>
      </div>

      <div v-else-if="filteredTimeline.length === 0" class="text-center text-muted-foreground text-xs py-10">当前筛选下没有步骤</div>

      <div v-else class="space-y-2">
        <!-- Question context chip -->
        <div class="flex items-start gap-2 rounded-lg bg-primary/10 border border-primary/15 px-2.5 py-1.5">
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-primary shrink-0 mt-0.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <span class="text-[11px] text-muted-foreground flex-1 min-w-0">{{ filteredTimeline[0].userText || (effectiveMsg ? msgIndexLabel(effectiveMsg) + ' · 无提问' : '') }}</span>
          <span v-if="effectiveMsg" class="shrink-0 text-[10px] text-muted-foreground/50">{{ msgIndexLabel(effectiveMsg) }}</span>
        </div>

        <!-- Steps -->
        <template v-for="item in filteredTimeline" :key="item.key">
          <button
            @click="openDetail(item)"
            class="w-full text-left rounded-lg border p-2.5 transition-all font-mono"
            :class="item.isLive
              ? 'border-primary/40 bg-primary/5'
              : 'border-border bg-card hover:border-muted-foreground/40 hover:shadow-sm'"
          >
            <div class="flex items-center gap-2 text-xs">
              <span class="shrink-0 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold"
                :class="isLlm(item) ? 'bg-primary/10 text-primary' : 'bg-accent/30 text-accent-foreground'">
                <svg v-if="isLlm(item)" xmlns="http://www.w3.org/2000/svg" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
                {{ isLlm(item) ? 'LLM' : '工具' }}
              </span>
              <span class="min-w-0 flex-1 truncate text-muted-foreground">
                <span class="text-foreground/90 font-medium">{{ item.step.name || (isLlm(item) ? '模型决策' : '工具执行') }}</span>
                <span class="text-muted-foreground/60 ml-1.5">#{{ item.step.step }}</span>
              </span>
              <span v-if="item.isLive" class="shrink-0 inline-flex items-center gap-1 text-[10px] text-primary">
                <span class="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />处理中
              </span>
              <span v-else class="shrink-0 text-[10px] text-green-500">✓</span>
              <span v-if="item.gapS" class="shrink-0 text-[10px] text-muted-foreground/50">{{ item.gapS }}</span>
              <span v-if="item.timeStr" class="shrink-0 text-[10px] text-muted-foreground/50">{{ item.timeStr }}</span>
            </div>
            <!-- Inline preview -->
            <div class="mt-1.5 flex items-center gap-2 text-[11px] text-muted-foreground/80 truncate">
              <span class="text-muted-foreground/50 shrink-0">{{ isLlm(item) || (item.step.input && item.step.input !== '{}') ? '参数' : '结果' }}</span>
              <span class="truncate">{{ oneLine(item.step.input && item.step.input !== '{}' ? item.step.input : item.step.output) }}</span>
              <svg class="shrink-0 text-muted-foreground/40" xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
            </div>
          </button>
        </template>
      </div>
    </div>

    <!-- Footer: agent mode -->
    <div class="px-4 py-3 border-t border-border shrink-0">
      <div class="flex items-center justify-between text-xs">
        <span class="text-muted-foreground">Agent 模式</span>
        <span class="font-medium" :class="chat.useAgentMode ? 'text-primary' : 'text-muted-foreground'">{{ chat.useAgentMode ? '开启' : '关闭（纯 RAG）' }}</span>
      </div>
    </div>

    <!-- ── Step detail viewer ── -->
    <Teleport to="body">
      <div v-if="detail" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-fade-in" @click="closeDetail">
        <div class="bg-card border border-border rounded-xl w-full max-w-3xl shadow-2xl flex flex-col max-h-[86vh] overflow-hidden animate-scale-in" @click.stop>
          <!-- Header -->
          <div class="px-5 py-3.5 border-b border-border flex items-center gap-3 shrink-0">
            <span class="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-bold"
              :class="isLlm(detail) ? 'bg-primary/10 text-primary' : 'bg-accent/30 text-accent-foreground'">
              <svg v-if="isLlm(detail)" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
              {{ isLlm(detail) ? 'LLM 决策' : '工具执行' }}
            </span>
            <div class="min-w-0 flex-1">
              <p class="text-sm font-semibold truncate">{{ detail.step.name || '步骤' }} <span class="text-muted-foreground/60 font-normal">#{{ detail.step.step }}</span></p>
              <p v-if="detail.userText" class="text-[11px] text-muted-foreground/70 truncate">问：{{ detail.userText }}</p>
            </div>
            <span v-if="detail.timeStr" class="text-[11px] text-muted-foreground/60 shrink-0">{{ detail.timeStr }}</span>
            <button @click="closeDetail" class="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
            </button>
          </div>

          <!-- Body -->
          <div class="p-5 overflow-y-auto min-h-0 space-y-4">
            <div>
              <div class="flex items-center justify-between mb-1.5">
                <span class="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" x2="15" y1="20" y2="20"/><line x1="12" x2="12" y1="4" y2="20"/></svg>
                  {{ isLlm(detail) ? '参数 (输入)' : '调用参数' }}
                </span>
                <button @click="copyText('input', pretty(detail.step.input))" class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
                  <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                  {{ copied === 'input' ? '已复制' : '复制' }}
                </button>
              </div>
              <pre class="rounded-lg bg-muted/40 border border-border/60 p-3 text-xs font-mono leading-relaxed text-foreground/90 whitespace-pre-wrap break-words max-h-56 overflow-y-auto">{{ pretty(detail.step.input) }}</pre>
            </div>

            <div>
              <div class="flex items-center justify-between mb-1.5">
                <span class="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                  {{ isLlm(detail) ? '动作' : '结果 (输出)' }}
                </span>
                <button @click="copyText('output', pretty(detail.step.output))" class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
                  <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                  {{ copied === 'output' ? '已复制' : '复制' }}
                </button>
              </div>
              <pre class="rounded-lg bg-muted/40 border border-border/60 p-3 text-xs font-mono leading-relaxed text-foreground/90 whitespace-pre-wrap break-words max-h-64 overflow-y-auto">{{ pretty(detail.step.output) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
