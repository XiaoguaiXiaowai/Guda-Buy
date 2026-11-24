import { expect, test } from '@playwright/test'
import {
  BUYER,
  OPERATOR,
  apiLogin,
  createOrderViaApi,
  getE2eProduct,
  mockPayViaApi,
  shipOrderViaApi,
  uiLogin,
} from './helpers'

const REVIEW_CONTENT = `E2E 自动化评价：版型好看，面料舒适 ${Date.now()}`

test('E2E-07 确认收货 → 提交评价 → 后台审核通过 → 前台展示', async ({ browser, page, request }) => {
  const buyerToken = await apiLogin(request, BUYER)
  const order = await createOrderViaApi(request, buyerToken)
  await mockPayViaApi(request, buyerToken, order.order_no)
  const operatorToken = await apiLogin(request, OPERATOR)
  await shipOrderViaApi(request, operatorToken, order.order_no)

  await uiLogin(page)
  await page.goto('/user/orders')
  const card = page.locator('.order-card', { hasText: order.order_no })
  await card.getByRole('button', { name: '确认收货' }).click()
  const confirmDialog = page.locator('.el-message-box')
  await confirmDialog.getByRole('button', { name: '确认收货' }).click()
  await expect(page.getByText('已确认收货')).toBeVisible()
  await expect(card.getByText('已完成')).toBeVisible()

  await card.getByRole('button', { name: '评价' }).click()
  await expect(page).toHaveURL(new RegExp(`/user/orders/${order.order_no}/review`))
  await page.locator('.el-rate__item').nth(4).click()
  await page
    .getByPlaceholder('说说商品的材质、版型、上身效果等真实体验（5–500 字）')
    .fill(REVIEW_CONTENT)
  await page.getByRole('button', { name: '提交评价' }).click()
  await expect(page.getByText('评价已提交，等待审核')).toBeVisible({ timeout: 20_000 })

  const adminContext = await browser.newContext()
  const adminPage = await adminContext.newPage()
  await uiLogin(adminPage, OPERATOR)
  await adminPage.goto('/admin/reviews')
  const row = adminPage.locator('.el-table__row', { hasText: order.order_no })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: '通过' }).click()
  await adminPage.locator('.el-message-box').getByRole('button', { name: '通过' }).click()
  await expect(adminPage.getByText('评价已通过审核')).toBeVisible()
  await adminContext.close()

  const product = await getE2eProduct(request)
  await page.goto(`/product/${product.public_id}`)
  await expect(page.getByText(REVIEW_CONTENT)).toBeVisible({ timeout: 20_000 })
})
