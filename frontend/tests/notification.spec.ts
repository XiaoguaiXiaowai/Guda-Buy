import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useNotificationStore } from '@/stores/notification'
import type { NotificationItem } from '@/types/notification'
import {
  NOTIFICATION_TYPE_TABS,
  notificationTarget,
  notificationTypeLabel,
  notificationTypeTone,
} from '@/utils/notification'

const mocks = vi.hoisted(() => ({
  fetchUnreadCount: vi.fn(),
  getAccessToken: vi.fn(),
}))

vi.mock('@/api/notification', () => ({
  fetchUnreadCount: mocks.fetchUnreadCount,
  fetchNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
}))

vi.mock('@/api/authToken', () => ({
  getAccessToken: mocks.getAccessToken,
}))

function makeItem(overrides: Partial<NotificationItem> = {}): NotificationItem {
  return {
    public_id: 'n-1',
    type: 'ORDER_PAID',
    type_text: '支付成功',
    title: '订单 GUDA202601010001 支付成功',
    content: '你的订单已支付成功',
    biz_type: 'ORDER',
    biz_public_id: 'GUDA202601010001',
    is_read: false,
    read_at: null,
    created_at: '2026-11-23T10:00:00+08:00',
    ...overrides,
  }
}

describe('notificationTypeTone / notificationTypeLabel', () => {
  it('按类型映射标签色', () => {
    expect(notificationTypeTone('ORDER_PAID')).toBe('primary')
    expect(notificationTypeTone('ORDER_SHIPPED')).toBe('success')
    expect(notificationTypeTone('ORDER_CANCELLED')).toBe('danger')
    expect(notificationTypeTone('COUPON_EXPIRING')).toBe('warning')
    expect(notificationTypeTone('SYSTEM')).toBe('info')
  })

  it('优先使用后端文案，缺失时回退本地映射', () => {
    expect(notificationTypeLabel('ORDER_SHIPPED', '订单发货')).toBe('订单发货')
    expect(notificationTypeLabel('ORDER_SHIPPED')).toBe('订单发货')
  })

  it('筛选页签覆盖五种消息类型', () => {
    expect(NOTIFICATION_TYPE_TABS.map((tab) => tab.value)).toEqual([
      '',
      'ORDER_PAID',
      'ORDER_SHIPPED',
      'ORDER_CANCELLED',
      'COUPON_EXPIRING',
      'SYSTEM',
    ])
  })
})

describe('notificationTarget', () => {
  it('订单消息跳订单详情', () => {
    expect(notificationTarget(makeItem())).toEqual({
      name: 'user-order-detail',
      params: { orderNo: 'GUDA202601010001' },
    })
  })

  it('优惠券消息跳我的优惠券', () => {
    const item = makeItem({
      type: 'COUPON_EXPIRING',
      biz_type: 'USER_COUPON',
      biz_public_id: 'uc-1',
    })
    expect(notificationTarget(item)).toEqual({ name: 'user-coupons' })
  })

  it('系统消息不跳转', () => {
    expect(
      notificationTarget(makeItem({ type: 'SYSTEM', biz_type: '', biz_public_id: '' })),
    ).toBeNull()
  })
})

describe('useNotificationStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mocks.getAccessToken.mockReturnValue('token')
  })

  it('未登录时未读数归零且不发请求', async () => {
    mocks.getAccessToken.mockReturnValue(null)
    const store = useNotificationStore()
    store.setUnreadCount(5)

    await store.refreshUnreadCount()

    expect(store.unreadCount).toBe(0)
    expect(mocks.fetchUnreadCount).not.toHaveBeenCalled()
  })

  it('登录后刷新未读数', async () => {
    mocks.fetchUnreadCount.mockResolvedValue({ unread_count: 3 })
    const store = useNotificationStore()

    await store.refreshUnreadCount()

    expect(store.unreadCount).toBe(3)
  })

  it('接口失败时保留上一次未读数', async () => {
    mocks.fetchUnreadCount.mockRejectedValue(new Error('network'))
    const store = useNotificationStore()
    store.setUnreadCount(2)

    await store.refreshUnreadCount()

    expect(store.unreadCount).toBe(2)
  })

  it('未读数不会为负', () => {
    const store = useNotificationStore()

    store.setUnreadCount(-1)

    expect(store.unreadCount).toBe(0)
  })

  it('页面隐藏时轮询跳过请求，回到前台补拉', async () => {
    vi.useFakeTimers()
    mocks.fetchUnreadCount.mockResolvedValue({ unread_count: 1 })
    const store = useNotificationStore()
    const visibility = vi.spyOn(document, 'visibilityState', 'get')

    visibility.mockReturnValue('hidden')
    store.startPolling()
    await vi.advanceTimersByTimeAsync(30_000)
    // 启动时立即拉取一次，隐藏期间的 30 秒心跳不再发请求
    expect(mocks.fetchUnreadCount).toHaveBeenCalledTimes(1)

    visibility.mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)
    expect(mocks.fetchUnreadCount).toHaveBeenCalledTimes(2)
    expect(store.unreadCount).toBe(1)

    store.stopPolling()
    visibility.mockRestore()
    vi.useRealTimers()
  })
})
