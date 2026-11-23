import { describe, expect, it } from 'vitest'

import type { CouponBrief } from '@/types/coupon'
import {
  couponConditionLabel,
  couponStatusTone,
  couponValueLabel,
  userCouponStatusTone,
} from '@/utils/coupon'

function coupon(overrides: Partial<CouponBrief>): Pick<CouponBrief, 'coupon_type' | 'value'> {
  return { coupon_type: 'FIXED', value: '20.00', ...overrides }
}

describe('couponValueLabel', () => {
  it('展示满减面额', () => {
    expect(couponValueLabel(coupon({}))).toBe('减 ¥20.00')
  })

  it('把折扣率换算成折', () => {
    expect(couponValueLabel(coupon({ coupon_type: 'DISCOUNT', value: '0.90' }))).toBe('9 折')
    expect(couponValueLabel(coupon({ coupon_type: 'DISCOUNT', value: '0.85' }))).toBe('8.5 折')
  })

  it('免邮券表达为免运费', () => {
    expect(couponValueLabel(coupon({ coupon_type: 'FREE_SHIPPING', value: '0.00' }))).toBe('免运费')
  })
})

describe('couponConditionLabel', () => {
  it('零门槛显示无门槛', () => {
    expect(couponConditionLabel('0.00')).toBe('无门槛')
  })

  it('有门槛显示满额可用', () => {
    expect(couponConditionLabel('100.00')).toBe('满 ¥100.00 可用')
  })
})

describe('status tone', () => {
  it('券模板与用户券状态映射到标签色', () => {
    expect(couponStatusTone('ACTIVE')).toBe('success')
    expect(couponStatusTone('STOPPED')).toBe('warning')
    expect(couponStatusTone('DRAFT')).toBe('info')
    expect(userCouponStatusTone('UNUSED')).toBe('success')
    expect(userCouponStatusTone('EXPIRED')).toBe('danger')
  })
})
