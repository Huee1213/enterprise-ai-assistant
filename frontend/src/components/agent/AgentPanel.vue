<script setup lang="ts">
import { useChatStore } from '@/stores/chat'
import { ref, computed } from 'vue'

const chat = useChatStore()

type StepKey = string

const expandedSteps = ref<Set<StepKey>>(new Set())

function stepKey(msgIdx: number, stepIdx: number): StepKey {
  return `${msgIdx}-${stepIdx}`
}

function toggleStep(msgIdx: number, stepIdx: number) {
  const key = stepKey(msgIdx, stepIdx)
  const next = new Set(expandedSteps.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  expandedSteps.value = next
}

function isExpanded(msgIdx: number, stepIdx: number): boolean {
  return expandedSteps.value.has(stepKey(msgIdx, stepIdx))
}
</script>

<template>
  <div class="h-full flex flex-col bg-card border-l border-border">
    <div class="p-4 border-b border-border">
      <h2 class="text-sm font-semibold flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary">
          <circle cx="12" cy="12" r="10" />
          <path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8" />
          <path d="M12 18V6" />
        </svg>
        Agent 调试
      </h2>
    </div>

    <div class="flex-1 overflow-y-auto p-4">
      <div v-if="chat.messages.length === 0" class="text-center text-muted-foreground text-sm py-8">
        暂无 Agent 活动
      </div>

      <div v-for="(msg, msgIdx) in chat.messages" :key="msg.id">
        <div v-if="msg.role === 'assistant' && msg.steps && msg.steps.length > 0" class="mb-5">
          <p class="text-xs font-medium text-muted-foreground/70 mb-2 px-1">
            消息 {{ msgIdx + 1 }} · {{ msg.steps.length }} 步
          </p>
          <div class="space-y-1.5">
            <button
              v-for="(step, stepIdx) in msg.steps"
              :key="`${msg.id}-${stepIdx}`"
              @click="toggleStep(msgIdx, stepIdx)"
              class="w-full text-left rounded-lg p-2.5 text-xs font-mono transition-all"
              :class="isExpanded(msgIdx, stepIdx)
                ? 'bg-muted border border-border shadow-sm'
                : 'bg-muted/40 hover:bg-muted/70 border border-transparent'"
            >
              <div class="flex items-center gap-2.5">
                <!-- LLM call icon -->
                <span v-if="step.action === 'llm_call'" class="shrink-0">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-primary">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  </svg>
                </span>
                <!-- Tool execution icon -->
                <span v-else class="shrink-0">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-accent-foreground">
                    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                  </svg>
                </span>

                <div class="flex-1 min-w-0">
                  <span class="font-medium text-foreground/90">{{ step.action === 'llm_call' ? 'LLM 调用' : '工具执行' }}</span>
                  <span class="text-muted-foreground ml-1.5">#{{ step.step }}</span>
                </div>

                <svg
                  class="shrink-0 text-muted-foreground transition-transform duration-200"
                  :class="isExpanded(msgIdx, stepIdx) ? 'rotate-180' : ''"
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </div>

              <div v-if="isExpanded(msgIdx, stepIdx)" class="mt-2.5 space-y-2 border-t border-border/50 pt-2.5">
                <div>
                  <div class="flex items-center gap-1 text-muted-foreground mb-1">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 7 4 4 20 4 20 7" /><line x1="9" x2="15" y1="20" y2="20" /><line x1="12" x2="12" y1="4" y2="20" /></svg>
                    <span class="text-[10px] font-medium">输入</span>
                  </div>
                  <div class="p-2 rounded bg-background/60 text-muted-foreground text-[10px] break-words whitespace-pre-wrap max-h-20 overflow-y-auto leading-relaxed">
                    {{ step.input.slice(0, 300) || '—' }}
                  </div>
                </div>
                <div>
                  <div class="flex items-center gap-1 text-muted-foreground mb-1">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>
                    <span class="text-[10px] font-medium">输出</span>
                  </div>
                  <div class="p-2 rounded bg-background/60 text-muted-foreground text-[10px] break-words whitespace-pre-wrap max-h-20 overflow-y-auto leading-relaxed">
                    {{ step.output.slice(0, 300) || '—' }}
                  </div>
                </div>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="p-3 border-t border-border shrink-0">
      <div class="flex items-center justify-between text-xs">
        <span class="text-muted-foreground">Agent 模式</span>
        <span
          class="font-medium"
          :class="chat.useAgentMode ? 'text-primary' : 'text-muted-foreground'"
        >
          {{ chat.useAgentMode ? '开启' : '关闭（纯 RAG）' }}
        </span>
      </div>
    </div>
  </div>
</template>
