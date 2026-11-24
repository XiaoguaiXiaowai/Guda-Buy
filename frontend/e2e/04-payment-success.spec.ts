import { expect, test } from '@playwright/test'
import { BUYER, apiLogin, createOrderViaApi, uiLogin } from './helpers'

test('E2E-04 模拟支付成功 → 订单已支付 → 消息通知', async ({ page, request }) => {
  const token = await apiLogin(request, BUYER)
  const order = await createOrderViaApi(request, token)

  await uiLogin(page)
  await page.goto(`/pay/${order.order_no}`)
  await page.getByRole('button', { name: '模拟支付成功' }).click()
  await expect(page.getByText('支付成功', { exact: true })).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText('待发货', { exact: false })).toBeVisible()

  await page.goto(`/user/orders/${order.order_no}`)
  await expect(page.getByText('已支付').first()).toBeVisible()

  await page.goto('/user/notifications')
  await expect(page.getByText(order.order_no).first()).toBeVisible()
})
