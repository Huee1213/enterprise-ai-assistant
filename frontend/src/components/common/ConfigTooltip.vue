<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{ text: string; label?: string }>(), { label: '' })
const show = ref(false)
const pos = ref({ x: 0, y: 0 })
let hideTimer: ReturnType<typeof setTimeout> | null = null

function onEnter(e: MouseEvent) {
  if (hideTimer) clearTimeout(hideTimer)
  show.value = true
  pos.value = { x: e.clientX, y: e.clientY }
}
function onLeave() {
  hideTimer = setTimeout(() => { show.value = false }, 150)
}
function onMove(e: MouseEvent) {
  if (show.value && (Math.abs(e.clientX - pos.value.x) > 4 || Math.abs(e.clientY - pos.value.y) > 4)) {
    pos.value = { x: e.clientX, y: e.clientY }
  }
}
function onClick(e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()
  // Clicking the label/icon opens the description (mouse-leave/outside click closes).
  show.value = true
  pos.value = { x: e.clientX, y: e.clientY }
}
onMounted(() => document.addEventListener('click', onGlobalClick))
onUnmounted(() => {
  document.removeEventListener('click', onGlobalClick)
  if (hideTimer) clearTimeout(hideTimer)
})
function onGlobalClick(e: Event) {
  // Ignore clicks that land on this trigger (handled by @click).
  const el = e.target as HTMLElement | null
  if (el && el.closest?.('.cfg-tip-trigger')) return
  show.value = false
}
</script>

<template>
  <span
    class="cfg-tip-trigger inline-flex items-center gap-1 cursor-help select-none shrink-0 text-sm font-medium"
    @mouseenter="onEnter" @mouseleave="onLeave" @mousemove="onMove" @click="onClick"
  >
    <template v-if="label">{{ label }}</template>
    <svg class="text-muted-foreground/60 hover:text-muted-foreground transition-colors" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>
    </svg>
  </span>

  <Teleport to="body">
    <div
      v-if="show"
      class="fixed z-[10000] max-w-[280px] rounded-lg border border-border bg-popover text-popover-foreground px-3 py-2 text-xs leading-relaxed shadow-lg pointer-events-none"
      :style="{ left: pos.x + 8 + 'px', top: pos.y + 8 + 'px' }"
    >{{ text }}</div>
  </Teleport>
</template>
