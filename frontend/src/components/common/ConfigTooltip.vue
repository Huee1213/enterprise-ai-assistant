<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{ text: string; label?: string }>(), { label: '' })
const show = ref(false)
const pos = ref({ x: 0, y: 0 })
const triggerEl = ref<HTMLElement | null>(null)
let hideTimer: ReturnType<typeof setTimeout> | null = null

// Anchor the tooltip to the label element (below it) instead of following the
// cursor. Stable positioning removes the jitter/jump users saw when moving
// quickly across several descriptions.
function updatePos() {
  const el = triggerEl.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const vw = window.innerWidth || document.documentElement.clientWidth
  const w = 280
  let left = r.left
  if (left + w > vw - 8) left = vw - w - 8
  if (left < 8) left = 8
  pos.value = { x: left, y: r.bottom + 6 }
}

function onEnter() {
  if (hideTimer) clearTimeout(hideTimer)
  show.value = true
  updatePos()
}

// Hover/click on the label text both reveal the description.
function onClick() {
  if (hideTimer) clearTimeout(hideTimer)
  show.value = true
  updatePos()
}

function onLeave() {
  // A short grace lets the mouse cross tiny gaps between adjacent labels
  // without the tooltip flickering, while staying snappy between rows.
  hideTimer = setTimeout(() => { show.value = false }, 60)
}

onMounted(() => document.addEventListener('click', onGlobalClick))
onUnmounted(() => {
  document.removeEventListener('click', onGlobalClick)
  if (hideTimer) clearTimeout(hideTimer)
})
function onGlobalClick(e: Event) {
  const el = e.target as HTMLElement | null
  if (el && el.closest?.('.cfg-tip-trigger')) return
  show.value = false
}
</script>

<template>
  <span
    ref="triggerEl"
    class="cfg-tip-trigger inline-flex select-none cursor-help text-sm font-medium border-b border-dotted border-transparent hover:border-muted-foreground/25 transition-colors shrink-0"
    @mouseenter="onEnter" @mouseleave="onLeave" @click="onClick"
  >{{ label }}</span>

  <Teleport to="body">
    <Transition name="tip">
      <div
        v-if="show"
        class="fixed z-[10000] w-72 max-w-[86vw] rounded-lg border border-border bg-popover text-popover-foreground px-3 py-2 text-xs leading-relaxed shadow-lg pointer-events-none"
        :style="{ left: pos.x + 'px', top: pos.y + 'px' }"
      >{{ text }}</div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.tip-enter-active {
  transition: opacity 0.14s ease, transform 0.14s ease;
}
.tip-leave-active {
  transition: opacity 0.1s ease, transform 0.1s ease;
}
.tip-enter-from,
.tip-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
