<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
  destructive?: boolean
}>(), {
  title: '确认',
  message: '确定执行此操作？',
  confirmText: '确定',
  cancelText: '取消',
  destructive: false,
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<template>
  <Teleport to="body">
    <Transition name="dialog">
      <div class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4" @click="emit('cancel')">
        <div class="bg-card border border-border rounded-xl p-5 max-w-sm w-full shadow-xl dialog-pop" @click.stop>
          <h3 class="text-sm font-semibold mb-2" :class="destructive ? 'text-destructive' : ''">{{ title }}</h3>
          <p class="text-sm text-muted-foreground mb-4">{{ message }}</p>
          <div class="flex gap-2 justify-end">
            <button @click="emit('cancel')" class="rounded-lg px-3 py-1.5 text-xs border border-border hover:bg-muted transition-colors">{{ cancelText }}</button>
            <button @click="emit('confirm')" class="rounded-lg px-3 py-1.5 text-xs transition-colors" :class="destructive ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90' : 'bg-primary text-primary-foreground hover:bg-primary/90'">{{ confirmText }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
