<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import {
  assignConversation,
  closeConversation,
  fetchAdminConversations,
  fetchConversationMessages,
  sendConversationMessage,
} from '@/api/support'
import { useAuthStore } from '@/stores/auth'
import type { AdminSupportConversation, SupportMessage, SupportStatus } from '@/types/support'
import { formatCurrency, formatDateTime } from '@/utils/format'
import { supportStatusLabel, supportStatusTone } from '@/utils/support'

const REFRESH_INTERVAL_MS = 5000
const QUICK_REPLIES = [
  '你好，请稍等，我帮您查询一下。',
  '已为您登记，请耐心等待处理结果。',
  '这个问题需要核实，稍后回复您。',
  '请问还有什么可以帮您？',
]

type QueueStatus = SupportStatus | 'OPEN' | 'ALL'

const auth = useAuthStore()

const conversations = ref<AdminSupportConversation[]>([])
const total = ref(0)
const loading = ref(false)
const actingId = ref('')

const filters = reactive({
  status: 'OPEN' as QueueStatus,
  keyword: '',
  page: 1,
  pageSize: 10,
})

const drawerOpen = ref(false)
const selected = ref<AdminSupportConversation | null>(null)
const messages = ref<SupportMessage[]>([])
const draft = ref('')
const sending = ref(false)
const loadingMessages = ref(false)
const nextAfter = ref('')
let refreshTimer: number | null = null

const canReply = computed(
  () =>
    selected.value?.status === 'ACTIVE' &&
    Boolean(auth.user?.public_id) &&
    selected.value.agent_public_id === auth.user?.public_id,
)
const isClosed = computed(() => selected.value?.status === 'CLOSED')

function buildQuery() {
  return {
    status: filters.status === 'OPEN' ? undefined : filters.status,
    keyword: filters.keyword.trim() || undefined,
    page: filters.page,
    page_size: filters.pageSize,
  }
}

async function loadQueue(silent = false): Promise<void> {
  if (!silent) {
    loading.value = true
  }
  try {
    const data = await fetchAdminConversations(buildQuery())
    conversations.value = data.results
    total.value = data.count
    if (selected.value) {
      const latest = data.results.find((item) => item.public_id === selected.value?.public_id)
      if (latest) {
        selected.value = latest
      }
    }
  } finally {
    if (!silent) {
      loading.value = false
    }
  }
}

function applyFilters(): void {
  filters.page = 1
  void loadQueue()
}

function changePage(page: number): void {
  filters.page = page
  void loadQueue()
}

async function loadMessages(reset = false): Promise<void> {
  if (!selected.value) {
    return
  }
  loadingMessages.value = true
  try {
    const anchor = reset ? undefined : nextAfter.value || undefined
    const data = await fetchConversationMessages(selected.value.public_id, anchor)
    if (reset) {
      messages.value = data.messages
      nextAfter.value = data.next_after
    } else if (data.messages.length) {
      messages.value = [...messages.value, ...data.messages]
      nextAfter.value = data.next_after
    }
    if ('user' in data.conversation) {
      selected.value = data.conversation as AdminSupportConversation
    }
  } catch {
    // 轮询失败保留当前内容
  } finally {
    loadingMessages.value = false
  }
}

async function openDetail(row: AdminSupportConversation): Promise<void> {
  selected.value = row
  drawerOpen.value = true
  messages.value = []
  nextAfter.value = ''
  draft.value = ''
  await loadMessages(true)
}

function closeDetail(): void {
  drawerOpen.value = false
  selected.value = null
  messages.value = []
  nextAfter.value = ''
  draft.value = ''
}

async function assign(row: AdminSupportConversation): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    `确认接管 ${row.user.nickname || row.user.username} 的会话？接管后由你负责回复。`,
    '接管会话',
    { confirmButtonText: '接管', cancelButtonText: '取消', type: 'info' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  actingId.value = row.public_id
  try {
    const updated = await assignConversation(row.public_id)
    ElMessage.success('已接管会话')
    if (selected.value?.public_id === updated.public_id) {
      selected.value = updated
      await loadMessages(true)
    }
    await loadQueue(true)
  } finally {
    actingId.value = ''
  }
}

async function close(row: AdminSupportConversation): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    '确认关闭该会话？关闭后双方只读，用户可重新发起咨询。',
    '关闭会话',
    { confirmButtonText: '关闭会话', cancelButtonText: '取消', type: 'warning' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  actingId.value = row.public_id
  try {
    const updated = await closeConversation(row.public_id)
    ElMessage.success('会话已关闭')
    if (selected.value?.public_id === updated.public_id) {
      selected.value = updated
      await loadMessages(true)
    }
    await loadQueue(true)
  } finally {
    actingId.value = ''
  }
}

async function send(): Promise<void> {
  const text = draft.value.trim()
  if (!text || !selected.value || !canReply.value) {
    return
  }
  sending.value = true
  try {
    const message = await sendConversationMessage(selected.value.public_id, text)
    messages.value = [...messages.value, message]
    nextAfter.value = message.public_id
    draft.value = ''
    await loadQueue(true)
  } finally {
    sending.value = false
  }
}

function handleVisibilityChange(): void {
  if (document.visibilityState === 'visible') {
    void refreshSilently()
  }
}

async function refreshSilently(): Promise<void> {
  await loadQueue(true)
  if (drawerOpen.value && selected.value && !isClosed.value) {
    await loadMessages()
  }
}

function startPolling(): void {
  stopPolling()
  refreshTimer = window.setInterval(() => {
    if (document.visibilityState === 'visible') {
      void refreshSilently()
    }
  }, REFRESH_INTERVAL_MS)
  document.addEventListener('visibilitychange', handleVisibilityChange)
}

function stopPolling(): void {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
  document.removeEventListener('visibilitychange', handleVisibilityChange)
}

onMounted(() => {
  void loadQueue()
  startPolling()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <section class="admin-page">
    <header class="admin-page__header">
      <div>
        <p class="admin-page__eyebrow">客服后台</p>
        <h1>客服工作台</h1>
      </div>
      <el-button :loading="loading" @click="loadQueue()">刷新队列</el-button>
    </header>

    <div class="admin-page__filters">
      <el-select v-model="filters.status" @change="applyFilters">
        <el-option label="未关闭" value="OPEN" />
        <el-option label="待接入" value="WAITING" />
        <el-option label="进行中" value="ACTIVE" />
        <el-option label="已关闭" value="CLOSED" />
        <el-option label="全部" value="ALL" />
      </el-select>
      <el-input
        v-model="filters.keyword"
        placeholder="用户昵称 / 用户名 / 订单号"
        clearable
        class="admin-page__search"
        @keyup.enter="applyFilters"
      />
      <el-button type="primary" @click="applyFilters">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="conversations" border stripe>
      <el-table-column label="用户" min-width="180">
        <template #default="{ row }">
          <div class="admin-page__cell">
            <strong>{{ row.user.nickname || row.user.username }}</strong>
            <span>{{ row.user.username }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="supportStatusTone(row.status)">
            {{ supportStatusLabel(row.status, row.status_text) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="关联订单" min-width="180">
        <template #default="{ row }">
          <div v-if="row.order" class="admin-page__cell">
            <strong>{{ row.order.order_no }}</strong>
            <span>{{ row.order.status_text }} · {{ formatCurrency(row.order.payable_amount) }}</span>
          </div>
          <span v-else class="admin-page__muted">无</span>
        </template>
      </el-table-column>
      <el-table-column label="客服" width="120">
        <template #default="{ row }">
          <span v-if="row.agent_name">{{ row.agent_name }}</span>
          <span v-else class="admin-page__muted">待接入</span>
        </template>
      </el-table-column>
      <el-table-column label="最近消息" width="170">
        <template #default="{ row }">{{ formatDateTime(row.last_message_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDetail(row)">进入</el-button>
          <el-button
            v-if="row.status === 'WAITING'"
            size="small"
            type="primary"
            :loading="actingId === row.public_id"
            @click="assign(row)"
          >
            接管
          </el-button>
          <el-button
            v-if="row.status !== 'CLOSED'"
            size="small"
            type="danger"
            :loading="actingId === row.public_id"
            @click="close(row)"
          >
            关闭
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > filters.pageSize"
      class="admin-page__pagination"
      layout="total, prev, pager, next"
      :total="total"
      :page-size="filters.pageSize"
      :current-page="filters.page"
      @current-change="changePage"
    />

    <el-drawer v-model="drawerOpen" size="560px" title="会话详情" @closed="closeDetail">
      <template v-if="selected">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="用户">
            {{ selected.user.nickname || selected.user.username }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="supportStatusTone(selected.status)">
              {{ supportStatusLabel(selected.status, selected.status_text) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="用户名">{{ selected.user.username }}</el-descriptions-item>
          <el-descriptions-item label="注册时间">
            {{ formatDateTime(selected.user.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item v-if="selected.order" label="关联订单">
            {{ selected.order.order_no }} · {{ selected.order.status_text }}
          </el-descriptions-item>
          <el-descriptions-item v-if="selected.order" label="订单金额">
            {{ formatCurrency(selected.order.payable_amount) }}
          </el-descriptions-item>
          <el-descriptions-item label="接管客服">
            {{ selected.agent_name || '未接管' }}
          </el-descriptions-item>
          <el-descriptions-item label="最近消息">
            {{ formatDateTime(selected.last_message_at) }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-loading="loadingMessages" class="support-chat">
          <div
            v-for="message in messages"
            :key="message.public_id"
            class="support-chat__message"
            :class="`support-chat__message--${message.sender_role.toLowerCase()}`"
          >
            <template v-if="message.sender_role === 'SYSTEM'">
              <span class="support-chat__system">{{ message.content }}</span>
            </template>
            <template v-else>
              <span class="support-chat__bubble">{{ message.content }}</span>
              <span class="support-chat__meta">
                {{ message.sender_name }} · {{ formatDateTime(message.created_at) }}
              </span>
            </template>
          </div>
          <p v-if="!messages.length" class="support-chat__empty">暂无消息</p>
        </div>

        <div class="support-quick">
          <el-button
            v-for="reply in QUICK_REPLIES"
            :key="reply"
            size="small"
            plain
            :disabled="!canReply"
            @click="draft = reply"
          >
            {{ reply }}
          </el-button>
        </div>

        <el-alert
          v-if="!canReply"
          class="support-composer__alert"
          type="info"
          :closable="false"
          show-icon
          :title="
            isClosed
              ? '会话已关闭，仅可查看历史消息。'
              : selected.status === 'WAITING'
                ? '请先接管会话再回复。'
                : '会话已由其他客服接管，仅可查看。'
          "
        />
        <el-input
          v-model="draft"
          type="textarea"
          :rows="3"
          maxlength="1000"
          show-word-limit
          :disabled="!canReply"
          placeholder="输入回复内容，纯文本，最多 1000 字"
        />
        <div class="support-composer__actions">
          <el-button
            v-if="selected.status === 'WAITING'"
            type="primary"
            :loading="actingId === selected.public_id"
            @click="assign(selected)"
          >
            接管会话
          </el-button>
          <el-button
            v-if="selected.status !== 'CLOSED'"
            type="danger"
            plain
            :loading="actingId === selected.public_id"
            @click="close(selected)"
          >
            关闭会话
          </el-button>
          <el-button
            type="primary"
            :loading="sending"
            :disabled="!canReply || !draft.trim()"
            @click="send"
          >
            发送回复
          </el-button>
        </div>
      </template>
    </el-drawer>
  </section>
</template>

<style scoped lang="scss">
.admin-page {
  &__header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 20px;
  }

  &__eyebrow {
    color: var(--guda-text-muted);
    font-size: 12px;
    letter-spacing: 2px;
    margin-bottom: 6px;
  }

  h1 {
    font-size: 26px;
  }

  &__filters {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 16px;

    :deep(.el-select) {
      width: 150px;
    }
  }

  &__search {
    width: 260px;
  }

  &__cell {
    display: flex;
    flex-direction: column;
    gap: 2px;

    strong {
      color: var(--guda-primary);
    }

    span {
      color: var(--guda-text-muted);
      font-size: 12px;
    }
  }

  &__muted {
    color: var(--guda-text-muted);
    font-size: 12px;
  }

  &__pagination {
    margin-top: 18px;
    justify-content: flex-end;
  }
}

.support-chat {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 16px 0;
  padding: 12px;
  min-height: 240px;
  max-height: 380px;
  overflow-y: auto;
  background: #fafaf9;
  border: 1px solid var(--guda-border);
  border-radius: 8px;

  &__message {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-width: 82%;

    &--customer {
      align-self: flex-start;
      align-items: flex-start;
    }

    &--agent {
      align-self: flex-end;
      align-items: flex-end;
    }

    &--system {
      align-self: center;
      align-items: center;
      max-width: 100%;
    }
  }

  &__bubble {
    padding: 8px 12px;
    border-radius: 10px;
    background: #fff;
    border: 1px solid var(--guda-border);
    line-height: 1.6;
    word-break: break-word;

    .support-chat__message--agent & {
      background: var(--guda-primary);
      border-color: var(--guda-primary);
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
    background: #f0efee;
    padding: 4px 10px;
    border-radius: 999px;
  }

  &__empty {
    margin: auto;
    color: var(--guda-text-muted);
    font-size: 13px;
  }
}

.support-quick {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;

  :deep(.el-button) {
    margin-left: 0;
  }
}

.support-composer {
  &__alert {
    margin-bottom: 10px;
  }

  &__actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 10px;
  }
}

@media (max-width: 767px) {
  .admin-page__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .admin-page__search {
    width: 100%;
  }
}
</style>
