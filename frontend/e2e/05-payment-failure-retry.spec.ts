import { expect, test } from '@playwright/test'
import { BUYER, apiLogin, createOrderViaApi, uiLogin } from './helpers'

test('E2E-05 模拟支付失败 → 重新支付成功', async ({ page, request }) => {
  const token = await apiLogin(request, BUYER)
  const order = await createOrderViaApi(request, token)

  await uiLogin(page)
  await page.goto(`/pay/${order.order_no}`)
  await page.getByRole('button', { name: '模拟支付失败' }).click()
  await expect(page.getByText('支付失败', { exact: true })).toBeVisible({ timeout: 20_000 })

  await page.getByRole('button', { name: '重新支付' }).click()
  await expect(page).toHaveURL(new RegExp(`/pay/${order.order_no}`))
  await page.getByRole('button', { name: '模拟支付成功' }).click()
  await expect(page.getByText('支付成功', { exact: true })).toBeVisible({ timeout: 20_000 })
})
