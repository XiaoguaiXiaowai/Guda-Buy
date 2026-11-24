import { expect, test } from '@playwright/test'
import { BUYER, SUPPORT, apiLogin, createOrderViaApi, uiLogin } from './helpers'

test('E2E-08 客服会话：发起咨询 → 后台接管 → 双向消息 → 关闭会话', async ({
  browser,
  page,
  request,
}) => {
  const buyerToken = await apiLogin(request, BUYER)
  const order = await createOrderViaApi(request, buyerToken)
  const question = `E2E 咨询：这笔订单什么时候发货？${Date.now()}`

  await uiLogin(page)
  await page.goto(`/user/orders/${order.order_no}`)
  await page.getByRole('button', { name: '联系客服' }).click()
  await expect(page).toHaveURL(/\/support/)
  await page.getByPlaceholder('请输入咨询内容，纯文本，最多 1000 字').fill(question)
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.getByText(question)).toBeVisible()

  const supportContext = await browser.newContext()
  const supportPage = await supportContext.newPage()
  await uiLogin(supportPage, SUPPORT)
  await supportPage.goto('/admin/support')
  const row = supportPage.locator('.el-table__row', { hasText: order.order_no })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: '接管' }).click()
  await supportPage.locator('.el-message-box').getByRole('button', { name: '接管' }).click()
  await expect(supportPage.getByText('已接管会话')).toBeVisible()

  await row.getByRole('button', { name: '进入' }).click()
  const drawer = supportPage.locator('.el-drawer')
  const reply = `E2E 客服回复：今天 18 点前安排发货 ${Date.now()}`
  await drawer.getByPlaceholder('输入回复内容，纯文本，最多 1000 字').fill(reply)
  await drawer.getByRole('button', { name: '发送回复' }).click()
  await expect(drawer.getByText(reply)).toBeVisible()

  await expect(page.getByText(reply)).toBeVisible({ timeout: 20_000 })

  await drawer.getByRole('button', { name: '关闭会话' }).click()
  await supportPage.locator('.el-message-box').getByRole('button', { name: '关闭会话' }).click()
  await expect(supportPage.getByText('会话已关闭').first()).toBeVisible()
  await expect(page.getByText('会话已关闭').first()).toBeVisible({ timeout: 20_000 })
  await supportContext.close()
})
