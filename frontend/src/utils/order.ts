import type { OrderStatus, OrderStatusOption } from '@/types/order'

type TagTone = 'primary' | 'success' | 'info' | 'warning' | 'danger'

const STATUS_TONE: Record<OrderStatus, TagTone> = {
  PENDING_PAYMENT: 'warning',
  PAID: 'primary',
  SHIPPED: 'success',
  COMPLETED: 'info',
  CANCELLED: 'danger',
  REFUNDING: 'warning',
  REFUNDED: 'info',
}

const STATUS_LABEL: Record<OrderStatus, string> = {
  PENDING_PAYMENT: '待支付',
  PAID: '已支付',
  SHIPPED: '已发货',
  COMPLETED: '已完成',
  CANCELLED: '已取消',
  REFUNDING: '退款中',
  REFUNDED: '已退款',
}

export const ORDER_STATUS_TABS: OrderStatusOption[] = [
  { label: '全部', value: '' },
  { label: '待支付', value: 'PENDING_PAYMENT' },
  { label: '已支付', value: 'PAID' },
  { label: '已发货', value: 'SHIPPED' },
  { label: '已完成', value: 'COMPLETED' },
  { label: '已取消', value: 'CANCELLED' },
]

export function orderStatusTone(status: OrderStatus): TagTone {
  return STATUS_TONE[status] ?? 'info'
}

export function orderStatusLabel(status: OrderStatus, fallback?: string): string {
  return fallback || STATUS_LABEL[status] || status
}
