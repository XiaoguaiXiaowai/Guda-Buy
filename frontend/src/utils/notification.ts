import type { RouteLocationRaw } from 'vue-router'

import type {
  NotificationItem,
  NotificationType,
  NotificationTypeOption,
} from '@/types/notification'

type TagTone = 'primary' | 'success' | 'info' | 'warning' | 'danger'

const TYPE_TONE: Record<NotificationType, TagTone> = {
  ORDER_PAID: 'primary',
  ORDER_SHIPPED: 'success',
  ORDER_CANCELLED: 'danger',
  COUPON_EXPIRING: 'warning',
  SYSTEM: 'info',
}

const TYPE_LABEL: Record<NotificationType, string> = {
  ORDER_PAID: '支付成功',
  ORDER_SHIPPED: '订单发货',
  ORDER_CANCELLED: '订单取消',
  COUPON_EXPIRING: '优惠券到期',
  SYSTEM: '系统通知',
}

export const NOTIFICATION_TYPE_TABS: NotificationTypeOption[] = [
  { label: '全部', value: '' },
  { label: '支付成功', value: 'ORDER_PAID' },
  { label: '订单发货', value: 'ORDER_SHIPPED' },
  { label: '订单取消', value: 'ORDER_CANCELLED' },
  { label: '优惠券', value: 'COUPON_EXPIRING' },
  { label: '系统', value: 'SYSTEM' },
]

export function notificationTypeTone(type: NotificationType): TagTone {
  return TYPE_TONE[type] ?? 'info'
}

export function notificationTypeLabel(type: NotificationType, fallback?: string): string {
  return fallback || TYPE_LABEL[type] || type
}

/** 消息点击跳转：订单消息进订单详情，券消息进我的优惠券，其余不跳转。 */
export function notificationTarget(item: NotificationItem): RouteLocationRaw | null {
  if (item.biz_type === 'ORDER' && item.biz_public_id) {
    return { name: 'user-order-detail', params: { orderNo: item.biz_public_id } }
  }
  if (item.type === 'COUPON_EXPIRING') {
    return { name: 'user-coupons' }
  }
  return null
}
