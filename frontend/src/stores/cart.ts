import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { addCartItem as addCartItemApi, fetchCartCount } from '@/api/cart'
import { getAccessToken } from '@/api/authToken'
import type { CartItem } from '@/types/cart'

export const useCartStore = defineStore('cart', () => {
  const count = ref(0)
  const totalQuantity = ref(0)
  const hasItems = computed(() => count.value > 0)

  function reset(): void {
    count.value = 0
    totalQuantity.value = 0
  }

  /** 角标双通道之一：登录态下从 /cart/count/ 拉取；未登录直接清零。 */
  async function refreshCount(): Promise<void> {
    if (!getAccessToken()) {
      reset()
      return
    }
    try {
      const data = await fetchCartCount()
      count.value = data.count
      totalQuantity.value = data.total_quantity
    } catch {
      reset()
    }
  }

  async function addItem(skuPublicId: string, quantity = 1): Promise<CartItem> {
    const item = await addCartItemApi({ sku_public_id: skuPublicId, quantity })
    await refreshCount()
    return item
  }

  return { count, totalQuantity, hasItems, refreshCount, addItem, reset }
})
