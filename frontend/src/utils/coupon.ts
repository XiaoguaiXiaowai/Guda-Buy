import type { CouponBrief, CouponStatus, UserCouponStatus } from '@/types/coupon'
import { formatCurrency } from '@/utils/format'

export function couponValueLabel(coupon: Pick<CouponBrief, 'coupon_type' | 'value'>): string {
  if (coupon.coupon_type === 'FREE_SHIPPING') {
    return '免运费'
  }
  if (coupon.coupon_type === 'DISCOUNT') {
    const rate = Number(coupon.value)
    if (!Number.isFinite(rate)) {
      return '折扣券'
    }
    const discount = Math.round(rate * 1000) / 100
    return `${discount} 折`
  }
  return `减 ${formatCurrency(coupon.value)}`
}

export function couponConditionLabel(minAmount: string): string {
  const amount = Number(minAmount)
  if (!Number.isFinite(amount) || amount <= 0) {
    return '无门槛'
  }
  return `满 ${formatCurrency(minAmount)} 可用`
}

export function couponStatusTone(status: CouponStatus): 'info' | 'success' | 'warning' {
  if (status === 'ACTIVE') {
    return 'success'
  }
  if (status === 'STOPPED') {
    return 'warning'
  }
  return 'info'
}

export function userCouponStatusTone(
  status: UserCouponStatus,
): 'info' | 'success' | 'warning' | 'danger' {
  if (status === 'UNUSED') {
    return 'success'
  }
  if (status === 'LOCKED') {
    return 'warning'
  }
  if (status === 'USED') {
    return 'info'
  }
  return 'danger'
}
