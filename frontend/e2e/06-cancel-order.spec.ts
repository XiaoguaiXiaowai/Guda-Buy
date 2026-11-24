import { expect, test } from '@playwright/test'
import {
  BUYER,
  apiLogin,
  createOrderViaApi,
  findSku,
  getE2eProduct,
  resetCart,
  uiLogin,
} from './helpers'

test('E2E-06 取消未支付订单 → 库存立即释放', async ({ page, request }) => {
  const token = await apiLogin(request, BUYER)
  await resetCart(request, token)
  const beforeSku = findSku(await getE2eProduct(request))
  const before = beforeSku.stock - beforeSku.locked_stock

  const order = await createOrderViaApi(request, token)
  const lockedSku = findSku(await getE2eProduct(request))
  expect(lockedSku.stock - lockedSku.locked_stock).toBe(before - 1)

  await uiLogin(page)
  await page.goto('/user/orders')
  const card = page.locator('.order-card', { hasText: order.order_no })
  await card.getByRole('button', { name: '取消订单' }).click()
  const dialog = page.locator('.el-message-box')
  await expect(dialog.getByText('取消后库存将立即释放')).toBeVisible()
  await dialog.getByRole('button', { name: '取消订单' }).click()
  await expect(page.getByText('订单已取消')).toBeVisible()

  const releasedSku = findSku(await getE2eProduct(request))
  expect(releasedSku.stock - releasedSku.locked_stock).toBe(before)
})
