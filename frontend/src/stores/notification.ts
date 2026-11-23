import { ref } from 'vue'
import { defineStore } from 'pinia'

import { getAccessToken } from '@/api/authToken'
import { fetchUnreadCount } from '@/api/notification'

const POLL_INTERVAL_MS = 30_000

export const useNotificationStore = defineStore('notification', () => {
  const unreadCount = ref(0)
  let timer: number | null = null

  function reset(): void {
    unreadCount.value = 0
  }

  function setUnreadCount(value: number): void {
    unreadCount.value = Math.max(value, 0)
  }

  /** 未读数轮询：未登录直接清零；页面隐藏时跳过请求，回到前台立即补拉一次。 */
  async function refreshUnreadCount(): Promise<void> {
    if (!getAccessToken()) {
      reset()
      return
    }
    try {
      const data = await fetchUnreadCount()
      setUnreadCount(data.unread_count)
    } catch {
      // 角标失败不影响页面使用
    }
  }

  function handleVisibilityChange(): void {
    if (document.visibilityState === 'visible') {
      void refreshUnreadCount()
    }
  }

  function startPolling(): void {
    stopPolling()
    void refreshUnreadCount()
    timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void refreshUnreadCount()
      }
    }, POLL_INTERVAL_MS)
    document.addEventListener('visibilitychange', handleVisibilityChange)
  }

  function stopPolling(): void {
    if (timer !== null) {
      window.clearInterval(timer)
      timer = null
    }
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  }

  return {
    unreadCount,
    refreshUnreadCount,
    setUnreadCount,
    reset,
    startPolling,
    stopPolling,
  }
})
