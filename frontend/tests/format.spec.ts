import { describe, expect, it } from 'vitest'

import { formatCurrency, formatDateTime } from '@/utils/format'

describe('formatCurrency', () => {
  it('保留两位小数并添加千分位', () => {
    expect(formatCurrency('129.00')).toBe('¥129.00')
    expect(formatCurrency(1234.5)).toBe('¥1,234.50')
  })

  it('非法金额回退为 0.00', () => {
    expect(formatCurrency('abc')).toBe('¥0.00')
  })
})

describe('formatDateTime', () => {
  it('空值展示占位符', () => {
    expect(formatDateTime(null)).toBe('-')
    expect(formatDateTime('')).toBe('-')
  })

  it('有效时间可格式化', () => {
    expect(formatDateTime('2026-11-04T10:30:00+08:00')).toContain('2026')
  })
})
