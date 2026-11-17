import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useCartStore } from '@/stores/cart'
import type { CartItem } from '@/types/cart'
import { cartStatusLabel, cartStatusTone } from '@/utils/cart'

const mocks = vi.hoisted(() => ({
  fetchCartCount: vi.fn(),
  addCartItem: vi.fn(),
  getAccessToken: vi.fn(),
}))

vi.mock('@/api/cart', () => ({
  fetchCartCount: mocks.fetchCartCount,
  addCartItem: mocks.addCartItem,
}))

vi.mock('@/api/authToken', () => ({
  getAccessToken: mocks.getAccessToken,
}))

describe('cartStatusTone / cartStatusLabel', () => {
  it('按状态映射标签色与文案', () => {
    expect(cartStatusTone('VALID')).toBe('success')
    expect(cartStatusTone('INSUFFICIENT')).toBe('warning')
    expect(cartStatusTone('INVALID')).toBe('danger')
    expect(cartStatusLabel('VALID')).toBe('有效')
    expect(cartStatusLabel('INSUFFICIENT')).toBe('库存不足')
    expect(cartStatusLabel('INVALID')).toBe('已失效')
  })
})

describe('useCartStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mocks.getAccessToken.mockReturnValue('token')
  })

  it('未登录时清零角标', async () => {
    mocks.getAccessToken.mockReturnValue(null)
    const store = useCartStore()
    store.count = 3

    await store.refreshCount()

    expect(store.count).toBe(0)
    expect(store.totalQuantity).toBe(0)
    expect(mocks.fetchCartCount).not.toHaveBeenCalled()
  })

  it('登录后刷新角标并计算 hasItems', async () => {
    mocks.fetchCartCount.mockResolvedValue({ count: 2, total_quantity: 5 })
    const store = useCartStore()

    await store.refreshCount()

    expect(store.count).toBe(2)
    expect(store.totalQuantity).toBe(5)
    expect(store.hasItems).toBe(true)
  })

  it('加购成功后同步刷新角标', async () => {
    const item = { public_id: 'item-1' } as CartItem
    mocks.addCartItem.mockResolvedValue(item)
    mocks.fetchCartCount.mockResolvedValue({ count: 1, total_quantity: 1 })
    const store = useCartStore()

    const result = await store.addItem('sku-1', 2)

    expect(mocks.addCartItem).toHaveBeenCalledWith({ sku_public_id: 'sku-1', quantity: 2 })
    expect(result).toBe(item)
    expect(store.count).toBe(1)
  })

  it('接口失败时清零', async () => {
    mocks.fetchCartCount.mockRejectedValue(new Error('network'))
    const store = useCartStore()
    store.count = 4

    await store.refreshCount()

    expect(store.count).toBe(0)
    expect(store.hasItems).toBe(false)
  })
})
