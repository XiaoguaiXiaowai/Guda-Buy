<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/api/notification'
import { useNotificationStore } from '@/stores/notification'
import type { NotificationItem, NotificationType } from '@/types/notification'
import { formatDateTime } from '@/utils/format'
import {
  NOTIFICATION_TYPE_TABS,
  notificationTarget,
  notificationTypeLabel,
  notificationTypeTone,
} from '@/utils/notification'

const router = useRouter()
const notificationStore = useNotificationStore()

const items = ref<NotificationItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const activeType = ref<NotificationType | ''>('')
const loading = ref(true)
const failed = ref(false)
const markingId = ref('')
const readingAll = ref(false)

const hasUnread = computed(() => items.value.some((item) => !item.is_read))

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    const data = await fetchNotifications({
      type: activeType.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    items.value = data.results
    total.value = data.count
  } catch {
    items.value = []
    total.value = 0
    failed.value = true
  } finally {
    loading.value = false
  }
}

function switchType(type: NotificationType | ''): void {
  if (activeType.value === type) {
    return
  }
  activeType.value = type
  page.value = 1
  void load()
}

function changePage(value: number): void {
  page.value = value
  void load()
}

async function markRead(item: NotificationItem): Promise<void> {
  if (item.is_read || markingId.value) {
    return
  }
  markingId.value = item.public_id
  try {
    const data = await markNotificationRead(item.public_id)
    item.is_read = data.is_read
    item.read_at = data.read_at
    notificationStore.setUnreadCount(data.unread_count)
  } catch {
    ElMessage.error('标记已读失败，请稍后重试')
  } finally {
    markingId.value = ''
  }
}

async function openNotification(item: NotificationItem): Promise<void> {
  await markRead(item)
  const target = notificationTarget(item)
  if (target) {
    await router.push(target)
  }
}

async function readAll(): Promise<void> {
  if (!hasUnread.value && notificationStore.unreadCount === 0) {
    return
  }
  readingAll.value = true
  try {
    const data = await markAllNotificationsRead()
    notificationStore.setUnreadCount(data.unread_count)
    ElMessage.success(`已将 ${data.updated} 条消息标记为已读`)
    await load()
  } catch {
    ElMessage.error('操作失败，请稍后重试')
  } finally {
    readingAll.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="messages">
    <header class="messages__header">
      <div>
        <h1>消息中心</h1>
        <p>订单动态与优惠券提醒都在这里，未读消息自动汇总。</p>
      </div>
      <nav class="user-tabs" aria-label="个人中心导航">
        <RouterLink to="/user/profile">个人资料</RouterLink>
        <RouterLink to="/user/addresses">收货地址</RouterLink>
        <RouterLink to="/user/orders">我的订单</RouterLink>
        <RouterLink to="/user/transactions">交易记录</RouterLink>
        <RouterLink to="/user/notifications">消息中心</RouterLink>
      </nav>
    </header>

    <div class="messages__toolbar">
      <div class="messages__tabs" role="tablist">
        <button
          v-for="tab in NOTIFICATION_TYPE_TABS"
          :key="tab.value || 'all'"
          type="button"
          role="tab"
          class="messages__tab"
          :class="{ 'is-active': activeType === tab.value }"
          :aria-selected="activeType === tab.value"
          @click="switchType(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>
      <el-button :loading="readingAll" :disabled="!hasUnread" @click="readAll">
        全部已读
      </el-button>
    </div>

    <el-skeleton v-if="loading" class="messages__skeleton" :rows="6" animated />

    <el-result
      v-else-if="failed"
      icon="warning"
      title="消息加载失败"
      sub-title="请检查网络后重试。"
    >
      <template #extra>
        <el-button type="primary" @click="load">重新加载</el-button>
      </template>
    </el-result>

    <el-empty v-else-if="!items.length" description="暂无消息" />

    <template v-else>
      <div class="messages__list">
        <article
          v-for="item in items"
          :key="item.public_id"
          class="message-card"
          :class="{ 'is-unread': !item.is_read }"
          @click="openNotification(item)"
        >
          <div class="message-card__head">
            <el-tag :type="notificationTypeTone(item.type)" effect="light" size="small">
              {{ notificationTypeLabel(item.type, item.type_text) }}
            </el-tag>
            <span class="message-card__title">{{ item.title }}</span>
            <span v-if="!item.is_read" class="message-card__dot" aria-label="未读" />
            <time class="message-card__time">{{ formatDateTime(item.created_at) }}</time>
          </div>
          <p class="message-card__content">{{ item.content }}</p>
          <div class="message-card__actions">
            <el-button
              v-if="!item.is_read"
              text
              type="primary"
              size="small"
              :loading="markingId === item.public_id"
              @click.stop="markRead(item)"
            >
              标记已读
            </el-button>
            <span v-if="notificationTarget(item)" class="message-card__link">查看详情</span>
          </div>
        </article>
      </div>

      <el-pagination
        v-if="total > pageSize"
        class="messages__pagination"
        layout="prev, pager, next"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        @current-change="changePage"
      />
    </template>
  </section>
</template>

<style scoped lang="scss">
.messages {
  &__header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 20px;

    h1 {
      font-size: 26px;
      margin-bottom: 6px;
    }

    p {
      color: var(--guda-text-muted);
      font-size: 13px;
    }
  }

  &__toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 18px;
  }

  &__tabs {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  &__tab {
    border: 1px solid var(--guda-border);
    background: var(--guda-surface);
    color: var(--guda-text-muted);
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 13px;
    cursor: pointer;

    &.is-active {
      color: var(--guda-primary);
      border-color: var(--guda-primary);
      background: rgba(64, 128, 255, 0.08);
    }
  }

  &__list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  &__pagination {
    margin-top: 24px;
    justify-content: flex-end;
  }

  &__skeleton {
    padding: 24px;
    background: var(--guda-surface);
    border: 1px solid var(--guda-border);
    border-radius: var(--guda-radius);
  }
}

.message-card {
  background: var(--guda-surface);
  border: 1px solid var(--guda-border);
  border-radius: var(--guda-radius);
  padding: 16px 20px;
  cursor: pointer;
  transition: border-color 0.2s ease;

  &:hover {
    border-color: var(--guda-primary);
  }

  &.is-unread {
    border-left: 3px solid var(--guda-primary);
  }

  &__head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  &__title {
    font-weight: 600;
    font-size: 15px;
  }

  &__dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--guda-primary);
  }

  &__time {
    margin-left: auto;
    font-size: 12px;
    color: var(--guda-text-muted);
  }

  &__content {
    font-size: 13px;
    color: var(--guda-text-muted);
    line-height: 1.6;
    margin: 0 0 6px;
  }

  &__actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
  }

  &__link {
    font-size: 12px;
    color: var(--guda-primary);
  }
}

.user-tabs {
  display: flex;
  gap: 20px;
  font-size: 14px;
  flex-wrap: wrap;

  a {
    color: var(--guda-text-muted);
    text-decoration: none;
    padding-bottom: 4px;
    border-bottom: 2px solid transparent;

    &.router-link-active {
      color: var(--guda-primary);
      border-color: var(--guda-primary);
    }
  }
}
</style>
