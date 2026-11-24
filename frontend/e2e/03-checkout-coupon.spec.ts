import { expect, test } from '@playwright/test'
import {
  BUYER,
  E2E_COUPON,
  E2E_PRODUCT,
  addCartItem,
  apiLogin,
  claimE2eCoupon,
  ensureAddress,
  findSku,
  getE2eProduct,
  resetCart,
  uiLogin,
} from './helpers'

test('E2E-03 购物车改数量 → 勾选 → 结算 → 用券 → 提交订单', async ({ page, request }) => {
  const token = await apiLogin(request, BUYER)
  await resetCart(request, token)
  await ensureAddress(request, token)
  await claimE2eCoupon(request, token)
  const product = await getE2eProduct(request)
  const sku = findSku(product)
  await addCartItem(request, token, sku.public_id, 1)

  await uiLogin(page)
  await page.goto('/cart')

  const row = page.locator('.cart-row', { hasText: E2E_PRODUCT }).first()
  const quantity = row.locator('.cart-row__quantity input')
  await quantity.fill('2')
  await quantity.press('Enter')
  await expect(page.getByText('共 1 种 / 2 件')).toBeVisible()

  await page.getByRole('button', { name: '去结算' }).click()
  await expect(page).toHaveURL(/\/checkout/)
  await page.locator('.coupon-option', { hasText: E2E_COUPON }).click()
  await page.getByRole('button', { name: '提交订单' }).click()

  await expect(page).toHaveURL(/\/user\/orders\/[A-Za-z0-9]+/, { timeout: 20_000 })
  await expect(page.getByText('待支付').first()).toBeVisible()
})
