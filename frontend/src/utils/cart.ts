import type { CartItemStatus } from '@/types/cart'

export function cartStatusTone(status: CartItemStatus): 'success' | 'warning' | 'danger' {
  if (status === 'VALID') {
    return 'success'
  }
  return status === 'INSUFFICIENT' ? 'warning' : 'danger'
}

export function cartStatusLabel(status: CartItemStatus): string {
  const labels: Record<CartItemStatus, string> = {
    VALID: '有效',
    INVALID: '已失效',
    INSUFFICIENT: '库存不足',
  }
  return labels[status]
}
