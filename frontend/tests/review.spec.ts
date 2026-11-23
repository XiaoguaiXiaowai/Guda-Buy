import { describe, expect, it } from 'vitest'

import {
  distributionPercent,
  remainingImageSlots,
  reviewStatusLabel,
  reviewStatusTone,
} from '@/utils/review'

describe('评价状态映射', () => {
  it('优先使用后端文案，缺失时回退本地映射', () => {
    expect(reviewStatusLabel('PENDING')).toBe('待审核')
    expect(reviewStatusLabel('APPROVED', '已通过审核')).toBe('已通过审核')
    expect(reviewStatusLabel('REJECTED')).toBe('已驳回')
  })

  it('状态对应不同标签色', () => {
    expect(reviewStatusTone('PENDING')).toBe('warning')
    expect(reviewStatusTone('APPROVED')).toBe('success')
    expect(reviewStatusTone('REJECTED')).toBe('danger')
  })
})

describe('评分分布与图片配额', () => {
  it('按总数计算星级占比并四舍五入', () => {
    expect(distributionPercent(2, 3)).toBe(67)
    expect(distributionPercent(0, 3)).toBe(0)
    expect(distributionPercent(1, 0)).toBe(0)
  })

  it('最多 3 张图片，剩余配额不为负', () => {
    expect(remainingImageSlots(0)).toBe(3)
    expect(remainingImageSlots(2)).toBe(1)
    expect(remainingImageSlots(3)).toBe(0)
    expect(remainingImageSlots(4)).toBe(0)
  })
})
