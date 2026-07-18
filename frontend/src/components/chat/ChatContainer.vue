<script setup lang="ts">
import { ref, nextTick, watch as vueWatch } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import ChatMessage from './ChatMessage.vue'
import ChatInput from './ChatInput.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'

const chat = useChatStore()
const auth = useAuthStore()
const messagesEndRef = ref<HTMLDivElement | null>(null)
const confirmRetryMsgId = ref<string | null>(null)
const confirmDeleteMsgId = ref<string | null>(null)
const confirmDeleteMsgContent = ref('')

function requestRetry(msgId: string) {
  confirmRetryMsgId.value = msgId
}

function executeRetry() {
  const msgId = confirmRetryMsgId.value
  confirmRetryMsgId.value = null
  if (!msgId) return
  const conv = chat.activeConversation
  if (!conv) return
  const idx = conv.messages.findIndex(m => m.id === msgId)
  if (idx < 1) return
  const prevMsg = conv.messages[idx - 1]
  if (prevMsg.role !== 'user') return
  chat.resendEdit(prevMsg.id, prevMsg.content)
}

function cancelRetry() { confirmRetryMsgId.value = null }

function requestDeleteMsg(msgId: string) {
  const conv = chat.activeConversation
  if (!conv) return
  const msg = conv.messages.find(m => m.id === msgId)
  if (!msg) return
  confirmDeleteMsgId.value = msgId
  confirmDeleteMsgContent.value = msg.content.slice(0, 80) + (msg.content.length > 80 ? '...' : '')
}

function executeDeleteMsg() {
  const msgId = confirmDeleteMsgId.value
  confirmDeleteMsgId.value = null
  if (!msgId) return
  chat.deleteMessages([msgId])
}

function cancelDeleteMsg() { confirmDeleteMsgId.value = null }

async function scrollToBottom(force = false) {
  await nextTick()
  if (force) await new Promise(r => setTimeout(r, 50))
  messagesEndRef.value?.scrollIntoView(force ? { behavior: 'auto' } : { behavior: 'smooth' })
}

vueWatch(() => chat.messages.length, () => scrollToBottom(true))
vueWatch(() => { const msgs = chat.messages; return msgs[msgs.length - 1]?.content }, () => scrollToBottom())

function handleSend(message: string) {
  if (!chat.activeConversation) chat.createConversation()
  chat.sendMessage(message)
}

function handleEdit(msgId: string, newContent: string) {
  chat.resendEdit(msgId, newContent)
}
</script>

<template>
  <div class="flex flex-col min-h-0 flex-1">
    <div class="flex-1 overflow-y-auto px-4 py-6 min-h-0">
      <div class="max-w-4xl mx-auto space-y-6">
        <template v-if="chat.messages.length === 0">
          <div class="flex flex-col items-center justify-center min-h-[300px] py-16 text-center">
            <div class="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-primary"><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4Z" /><path d="M16 14H8a4 4 0 0 0-4 4v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1a4 4 0 0 0-4-4Z" /></svg>
            </div>
            <h2 class="text-xl font-semibold mb-2">企业 AI 知识助手</h2>
            <p class="text-sm text-muted-foreground max-w-md mb-8">{{ auth.isAdmin ? '上传企业文档后即可测试问答。' : '企业文档已就绪，开始提问吧。' }}</p>
          </div>
        </template>
        <template v-else>
          <ChatMessage
            v-for="(msg, idx) in chat.messages"
            :key="msg.id"
            :message="msg"
            :msgIndex="idx"
            :isAdmin="auth.isAdmin"
            :isStreaming="chat.isStreaming && msg === chat.messages[chat.messages.length - 1] && msg.role === 'assistant'"
            @edit="handleEdit"
            @retry="requestRetry"
            @delete-msg="requestDeleteMsg"
          />
        </template>
        <div ref="messagesEndRef" />
      </div>
    </div>

    <ChatInput :disabled="chat.isStreaming" :isStreaming="chat.isStreaming" @send="handleSend" @stop="chat.stopStreaming" />

    <ConfirmDialog v-if="confirmRetryMsgId" title="重新生成" message="确定重新生成回答？当前 AI 回答将被替换。" @confirm="executeRetry" @cancel="cancelRetry" />
    <ConfirmDialog v-if="confirmDeleteMsgId" title="删除消息" :message="`确定删除这条消息？\n「${confirmDeleteMsgContent}」`" destructive @confirm="executeDeleteMsg" @cancel="cancelDeleteMsg" />
  </div>
</template>
