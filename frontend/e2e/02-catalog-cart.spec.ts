import { expect, test } from '@playwright/test'
import { BUYER, E2E_PRODUCT, E2E_SKU, apiLogin, resetCart, uiLogin } from './helpers'

test('E2E-02 浏览分类商品 → 详情选 SKU → 加入购物车', async ({ page, request }) => {
  const token = await apiLogin(request, BUYER)
  await resetCart(request, token)

  await uiLogin(page)
  await page.goto('/products')
  await page.getByText(E2E_PRODUCT).first().click()

  await expect(page).toHaveURL(/\/product\//)
  await page.getByRole('button', { name: E2E_SKU }).click()
  await page.getByRole('button', { name: '加入购物车' }).click()
  await expect(page.getByText('已加入购物车')).toBeVisible()

  await page.goto('/cart')
  await expect(page.locator('.cart-row__name', { hasText: E2E_PRODUCT })).toBeVisible()
  await expect(page.getByText(E2E_SKU)).toBeVisible()
})
