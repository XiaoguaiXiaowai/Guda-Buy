import { describe, expect, it } from 'vitest'

import {
  formatPriceRange,
  productStatusLabel,
  resolveImageUrl,
  stockTone,
  toQueryParams,
} from '@/utils/catalog'

describe('resolveImageUrl', () => {
  it('相对路径补齐 /media 前缀', () => {
    expect(resolveImageUrl('products/abc/cover.png')).toBe('/media/products/abc/cover.png')
    expect(resolveImageUrl('/media/a.png')).toBe('/media/a.png')
  })

  it('绝对地址原样返回', () => {
    expect(resolveImageUrl('https://cdn.example.com/a.png')).toBe('https://cdn.example.com/a.png')
  })

  it('空值返回空字符串', () => {
    expect(resolveImageUrl(null)).toBe('')
    expect(resolveImageUrl('')).toBe('')
  })
})

describe('formatPriceRange', () => {
  it('同价展示单价', () => {
    expect(formatPriceRange('99.00', '99.00')).toBe('¥99.00')
  })

  it('不同价展示起售价', () => {
    expect(formatPriceRange('99.00', '129.00')).toBe('¥99.00 起')
  })

  it('未定价给出占位', () => {
    expect(formatPriceRange('0.00', '0.00')).toBe('待定价')
  })
})

describe('stockTone', () => {
  it('按库存状态映射标签色', () => {
    expect(stockTone('IN_STOCK')).toBe('success')
    expect(stockTone('LOW')).toBe('warning')
    expect(stockTone('OUT_OF_STOCK')).toBe('danger')
  })
})

describe('productStatusLabel', () => {
  it('返回中文状态', () => {
    expect(productStatusLabel('DRAFT')).toBe('草稿')
    expect(productStatusLabel('ON_SALE')).toBe('在售')
    expect(productStatusLabel('OFF_SALE')).toBe('已下架')
  })
})

describe('toQueryParams', () => {
  it('过滤空值与空字符串', () => {
    expect(toQueryParams({ category: 'abc', search: '', page: 2, ordering: undefined })).toEqual({
      category: 'abc',
      page: 2,
    })
  })
})
