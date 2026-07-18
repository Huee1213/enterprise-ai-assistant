<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  send: [message: string]
  stop: []
}>()

const props = defineProps<{
  disabled?: boolean
  isStreaming?: boolean
}>()

const input = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

function adjustHeight() {
  const el = textareaRef.value
  if (el) {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }
}

function handleSubmit() {
  const text = input.value.trim()
  if (!text || props.disabled) return
  emit('send', text)
  input.value = ''
  adjustHeight()
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSubmit()
  }
}
</script>

<template>
  <div class="border-t border-border bg-background p-4">
    <div class="max-w-4xl mx-auto">
      <div class="relative flex items-end gap-2">
        <textarea
          ref="textareaRef"
          v-model="input"
          @keydown="handleKeydown"
          @input="adjustHeight"
          placeholder="输入你的问题..."
          :disabled="disabled || isStreaming"
          rows="1"
          class="flex w-full rounded-xl border border-input bg-background px-4 py-3 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-none min-h-[44px] max-h-[200px]"
        />

        <!-- Stop button (during streaming) -->
        <button
          v-if="isStreaming"
          @click="emit('stop')"
          title="停止响应"
          class="inline-flex items-center justify-center rounded-xl text-sm font-medium transition-colors bg-destructive text-destructive-foreground hover:bg-destructive/90 h-11 w-11 shrink-0 animate-pulse"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        </button>

        <!-- Send button -->
        <button
          v-else
          @click="handleSubmit"
          :disabled="disabled || !input.trim()"
          class="inline-flex items-center justify-center rounded-xl text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-11 w-11 shrink-0"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 2 11 13" />
            <path d="m22 2-7 20-4-9-9-4 20-7z" />
          </svg>
        </button>
      </div>
      <p class="text-[10px] text-muted-foreground/50 text-center mt-2">
        Enter 发送 · Shift+Enter 换行
      </p>
    </div>
  </div>
</template>
