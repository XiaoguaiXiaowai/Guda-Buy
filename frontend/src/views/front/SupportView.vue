<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import {
  createConversation,
  fetchConversationMessages,
  fetchMyConversations,
  sendConversationMessage,
} from '@/api/support'
import type { SupportConversation, SupportMessage } from '@/types/support'
import { formatDateTime } from '@/utils/format'
import { supportStatusLabel, supportStatusTone } from '@/utils/support'

const POLL_INTERVAL_MS = 5000

const route = useRoute()
const router = useRouter()

const conversations = ref<SupportConversation[]>([])
const activeId = ref('')
const messages = ref<SupportMessage[]>([])
const draft = ref('')
const loading = ref(true)
const loadingMessages = ref(false)
const sending = ref(false)
const creating = ref(false)
const nextAfter = ref('')
const messageBox = ref<HTMLElement | null>(null)
let pollTimer: number | null = null

const activeConversation = computed(
  () => conversations.value.find((item) => item.public_id === activeId.value) ?? null,
)
const isClosed = computed(() => activeConversation.value?.status === 'CLOSED')
const openConversation = computed(
  () => conversations.value.find((item) => item.status !== 'CLOSED') ?? null,
)
const showEmpty = computed(() => !loading.value && conversations.value.length === 0)

function upsertConversation(conversation: SupportConversation): void {
  const index = conversations.value.findIndex((item) => item.public_id === conversation.public_id)
  if (index >= 0) {
    conversations.value.splice(index, 1, conversation)
  } else {
    conversations.value.unshift(conversation)
  }
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  if (messageBox.value) {
    messageBox.value.scrollTop = messageBox.value.scrollHeight
  }
}

async function loadMessages(reset = false): Promise<void> {
  if (!activeId.value) {
    return
  }
  loadingMessages.value = true
  try {
    const anchor = reset ? undefined : nextAfter.value || undefined
    const data = await fetchConversationMessages(activeId.value, anchor)
    if (reset) {
      messages.value = data.messages
      nextAfter.value = data.next_after
      await scrollToBottom()
    } else if (data.messages.length) {
      messages.value = [...messages.value, ...data.messages]
      nextAfter.value = data.next_after
      await scrollToBottom()
    }
  } catch {
    // 轮询失败保持当前会话内容
  } finally {
    loadingMessages.value = false
  }
}

async function selectConversation(publicId: string): Promise<void> {
  if (!publicId) {
    return
  }
  activeId.value = publicId
  messages.value = []
  nextAfter.value = ''
  await router.replace({ name: 'support', query: { conversation: publicId } })
  await loadMessages(true)
  startPolling()
}

async function loadConversations(): Promise<void> {
  const data = await fetchMyConversations({ page_size: 50 })
  conversations.value = data.results
  const preferred =
    typeof route.query.conversation === 'string' ? route.query.conversation : ''
  const target =
    conversations.value.find((item) => item.public_id === preferred) ??
    conversations.value.find((item) => item.public_id === activeId.value) ??
    conversations.value[0] ??
    null
  if (target) {
    await selectConversation(target.public_id)
  } else {
    activeId.value = ''
    messages.value = []
    nextAfter.value = ''
  }
}

async function startConversation(orderNo = ''): Promise<void> {
  creating.value = true
  try {
    const conversation = await createConversation({ order_no: orderNo })
    upsertConversation(conversation)
    await selectConversation(conversation.public_id)
    ElMessage.success(orderNo ? '已关联订单发起咨询' : '咨询已发起，请留言等待客服接入')
  } finally {
    creating.value = false
  }
}

async function send(): Promise<void> {
  const text = draft.value.trim()
  if (!text || !activeId.value || isClosed.value) {
    return
  }
  sending.value = true
  try {
    const message = await sendConversationMessage(activeId.value, text)
    messages.value = [...messages.value, message]
    nextAfter.value = message.public_id
    draft.value = ''
    if (activeConversation.value) {
      activeConversation.value.last_message_at = message.created_at
    }
    await scrollToBottom()
  } finally {
    sending.value = false
  }
}

function handleVisibilityChange(): void {
  if (document.visibilityState === 'visible' && activeId.value) {
    void loadMessages()
  }
}

async function refreshConversations(): Promise<void> {
  if (!activeId.value) {
    return
  }
  try {
    const data = await fetchMyConversations()
    const fresh = data.results.find((item) => item.public_id === activeId.value)
    if (!fresh) {
      return
    }
    const index = conversations.value.findIndex((item) => item.public_id === activeId.value)
    if (index >= 0) {
      conversations.value.splice(index, 1, fresh)
    }
  } catch {
    // 轮询失败保持当前会话内容
  }
}

function startPolling(): void {
  stopPolling()
  if (!activeId.value || isClosed.value) {
    return
  }
  pollTimer = window.setInterval(() => {
    if (document.visibilityState !== 'visible') {
      return
    }
    void (async () => {
      await refreshConversations()
      if (isClosed.value) {
        stopPolling()
        return
      }
      await loadMessages()
    })()
  }, POLL_INTERVAL_MS)
  document.addEventListener('visibilitychange', handleVisibilityChange)
}

function stopPolling(): void {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
  document.removeEventListener('visibilitychange', handleVisibilityChange)
}

onMounted(async () => {
  loading.value = true
  try {
    await loadConversations()
  } finally {
    loading.value = false
  }
  startPolling()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <section class="support">
    <header class="support__header">
      <div>
        <p class="support__eyebrow">在线客服</p>
        <h1>咨询客服</h1>
        <p class="support__hint">客服工作时间内会尽快回复，消息每 5 秒自动刷新。</p>
      </div>
      <el-button
        v-if="!openConversation"
        type="primary"
        :loading="creating"
        @click="startConversation(activeConversation?.order?.order_no ?? '')"
      >
        发起咨询
      </el-button>
    </header>

    <el-skeleton v-if="loading" :rows="8" animated />

    <el-empty v-else-if="showEmpty" description="还没有咨询记录">
      <el-button type="primary" :loading="creating" @click="startConversation()">
        发起第一次咨询
      </el-button>
    </el-empty>

    <div v-else class="support__layout">
      <aside class="support__list">
        <button
          v-for="item in conversations"
          :key="item.public_id"
          type="button"
          class="support__item"
          :class="{ 'support__item--active': item.public_id === activeId }"
          @click="selectConversation(item.public_id)"
        >
          <span class="support__item-top">
            <el-tag size="small" :type="supportStatusTone(item.status)">
              {{ supportStatusLabel(item.status, item.status_text) }}
            </el-tag>
            <span>{{ formatDateTime(item.last_message_at) }}</span>
          </span>
          <strong v-if="item.order">订单 {{ item.order.order_no }}</strong>
          <strong v-else>售前 / 其他咨询</strong>
          <span class="support__item-agent">
            {{ item.agent_name ? `客服 ${item.agent_name}` : '等待客服接入' }}
          </span>
        </button>
      </aside>

      <div v-if="activeConversation" class="support__chat">
        <header class="support__chat-header">
          <div>
            <el-tag :type="supportStatusTone(activeConversation.status)">
              {{ supportStatusLabel(activeConversation.status, activeConversation.status_text) }}
            </el-tag>
            <span v-if="activeConversation.agent_name" class="support__agent">
              客服 {{ activeConversation.agent_name }}
            </span>
          </div>
          <RouterLink
            v-if="activeConversation.order"
            class="support__order"
            :to="`/user/orders/${activeConversation.order.order_no}`"
          >
            订单 {{ activeConversation.order.order_no }}
          </RouterLink>
        </header>

        <el-alert
          v-if="activeConversation.status === 'WAITING'"
          class="support__alert"
          type="warning"
          :closable="false"
          show-icon
          title="已提交咨询，等待客服接入；接入前可以继续留言。"
        />
        <el-alert
          v-else-if="isClosed"
          class="support__alert"
          type="info"
          :closable="false"
          show-icon
          title="会话已关闭，历史消息仅可查看；如需继续咨询请新建会话。"
        />

        <div ref="messageBox" v-loading="loadingMessages" class="support__messages">
          <div
            v-for="message in messages"
            :key="message.public_id"
            class="support__message"
            :class="`support__message--${message.sender_role.toLowerCase()}`"
          >
            <template v-if="message.sender_role === 'SYSTEM'">
              <span class="support__system">{{ message.content }}</span>
            </template>
            <template v-else>
              <span class="support__bubble">{{ message.content }}</span>
              <span class="support__meta">
                {{ message.sender_name }} · {{ formatDateTime(message.created_at) }}
              </span>
            </template>
          </div>
          <p v-if="!messages.length" class="support__empty-chat">暂无消息，先和客服打个招呼吧。</p>
        </div>

        <footer class="support__composer">
          <el-input
            v-model="draft"
            type="textarea"
            :rows="3"
            maxlength="1000"
            show-word-limit
            :disabled="isClosed"
            placeholder="请输入咨询内容，纯文本，最多 1000 字"
            @keydown.enter.exact.prevent="send"
          />
          <div class="support__composer-actions">
            <el-button
              v-if="isClosed"
              type="primary"
              plain
              :loading="creating"
              @click="startConversation(activeConversation.order?.order_no ?? '')"
            >
              再次咨询
            </el-button>
            <el-button
              type="primary"
              :loading="sending"
              :disabled="isClosed || !draft.trim()"
              @click="send"
            >
              发送
            </el-button>
          </div>
        </footer>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
.support {
  &__header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 20px;

    h1 {
      font-size: 26px;
      margin: 6px 0;
    }
  }

  &__eyebrow {
    color: var(--guda-text-muted);
    font-size: 12px;
    letter-spacing: 2px;
  }

  &__hint {
    color: var(--guda-text-muted);
    font-size: 13px;
  }

  &__layout {
    display: grid;
    grid-template-columns: 280px minmax(0, 1fr);
    gap: 16px;
    align-items: start;
  }

  &__list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    background: var(--guda-surface);
    border: 1px solid var(--guda-border);
    border-radius: var(--guda-radius);
    padding: 10px;
  }

  &__item {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 12px;
    border: 1px solid transparent;
    border-radius: 8px;
    background: transparent;
    text-align: left;
    cursor: pointer;
    color: var(--guda-text);

    &:hover {
      background: #faf7f5;
    }

    &--active {
      border-color: var(--guda-primary);
      background: #fff7f2;
    }

    strong {
      font-size: 14px;
    }
  }

  &__item-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    color: var(--guda-text-muted);
    font-size: 12px;
  }

  &__item-agent {
    color: var(--guda-text-muted);
    font-size: 12px;
  }

  &__chat {
    display: flex;
    flex-direction: column;
    min-height: 560px;
    background: var(--guda-surface);
    border: 1px solid var(--guda-border);
    border-radius: var(--guda-radius);
  }

  &__chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 18px;
    border-bottom: 1px solid var(--guda-border);

    > div {
      display: flex;
      align-items: center;
      gap: 10px;
    }
  }

  &__agent {
    color: var(--guda-text-muted);
    font-size: 13px;
  }

  &__order {
    color: var(--guda-primary);
    font-size: 13px;
    text-decoration: none;
  }

  &__alert {
    margin: 12px 18px 0;
  }

  &__messages {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 18px;
    max-height: 460px;
    overflow-y: auto;
  }

  &__message {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-width: 72%;

    &--customer {
      align-self: flex-end;
      align-items: flex-end;
    }

    &--agent {
      align-self: flex-start;
      align-items: flex-start;
    }

    &--system {
      align-self: center;
      max-width: 100%;
    }
  }

  &__bubble {
    padding: 10px 14px;
    border-radius: 12px;
    background: #f5f5f4;
    line-height: 1.6;
    word-break: break-word;

    .support__message--customer & {
      background: var(--guda-primary);
      color: #fff;
    }
  }

  &__meta {
    color: var(--guda-text-muted);
    font-size: 11px;
  }

  &__system {
    color: var(--guda-text-muted);
    font-size: 12px;
    background: #f5f5f4;
    padding: 4px 10px;
    border-radius: 999px;
  }

  &__empty-chat {
    margin: auto;
    color: var(--guda-text-muted);
    font-size: 13px;
  }

  &__composer {
    border-top: 1px solid var(--guda-border);
    padding: 14px 18px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  &__composer-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
}

@media (max-width: 991px) {
  .support__layout {
    grid-template-columns: 1fr;
  }

  .support__messages {
    max-height: none;
  }
}

@media (max-width: 767px) {
  .support__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .support__message {
    max-width: 88%;
  }
}
</style>
