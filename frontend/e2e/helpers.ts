import { expect, type APIRequestContext, type Page } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

export const API_BASE = process.env.E2E_API_BASE || 'http://127.0.0.1:8001/api/v1'
export const PASSWORD = 'Passw0rd123'
export const BUYER = 'e2e_buyer'
export const OPERATOR = 'e2e_operator'
export const SUPPORT = 'e2e_support'
export const E2E_PRODUCT = 'E2E 法式碎花连衣裙'
export const E2E_SKU = '米白 M'
export const E2E_COUPON = 'E2E 满 100 减 10'

export interface ProductSku {
  public_id: string
  spec_text: string
  stock: number
  locked_stock: number
  sale_price: string
}

export interface ProductPayload {
  public_id: string
  name: string
  skus: ProductSku[]
}

export type OrderPayload = { order_no: string; payable_amount: string; status: string }

export function bearer(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` }
}

export function uniqueEmail(prefix: string): string {
  return `${prefix}.${Date.now()}.${Math.floor(Math.random() * 1000)}@guda.test`
}

export function uniqueUsername(prefix: string): string {
  return `${prefix}${Date.now().toString().slice(-10)}`
}

export async function apiLogin(
  ctx: APIRequestContext,
  account: string,
  password = PASSWORD,
): Promise<string> {
  const response = await ctx.post(`${API_BASE}/auth/login/`, {
    data: { account, password },
  })
  expect(response.ok(), `登录失败：${account} / ${response.status()}`).toBeTruthy()
  const body = await response.json()
  return body.access as string
}

export async function uiLogin(page: Page, account: string = BUYER): Promise<void> {
  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名或邮箱').fill(account)
  await page.getByPlaceholder('请输入密码').fill(PASSWORD)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 })
}

export async function getE2eProduct(ctx: APIRequestContext): Promise<ProductPayload> {
  const list = await ctx.get(`${API_BASE}/products/?page_size=100`)
  expect(list.ok()).toBeTruthy()
  const body = await list.json()
  const items: Array<{ public_id: string; name: string }> = body.results ?? body
  const product = items.find((item) => item.name === E2E_PRODUCT)
  expect(product, `未找到 E2E 商品：${E2E_PRODUCT}`).toBeTruthy()
  const detail = await ctx.get(`${API_BASE}/products/${product!.public_id}/`)
  expect(detail.ok()).toBeTruthy()
  return (await detail.json()) as ProductPayload
}

export function findSku(product: ProductPayload, spec: string = E2E_SKU): ProductSku {
  const sku = product.skus.find((item) => item.spec_text === spec)
  expect(sku, `未找到 SKU：${spec}`).toBeTruthy()
  return sku!
}

export async function resetCart(ctx: APIRequestContext, token: string): Promise<void> {
  await ctx.post(`${API_BASE}/cart/clear/`, {
    headers: bearer(token),
    data: { only_selected: false },
  })
}

export async function ensureAddress(ctx: APIRequestContext, token: string): Promise<string> {
  const list = await ctx.get(`${API_BASE}/users/me/addresses/`, { headers: bearer(token) })
  expect(list.ok()).toBeTruthy()
  const body = await list.json()
  const items = Array.isArray(body) ? body : (body.results ?? [])
  if (items.length) {
    return items[0].public_id as string
  }
  const response = await ctx.post(`${API_BASE}/users/me/addresses/`, {
    headers: bearer(token),
    data: {
      receiver_name: '测试收货人',
      phone: '13800138000',
      province: '广东省',
      city: '深圳市',
      district: '南山区',
      detail: 'E2E 测试路 1 号',
      postal_code: '518000',
    },
  })
  expect(response.status(), '创建测试地址失败').toBe(201)
  return (await response.json()).public_id as string
}

export async function addCartItem(
  ctx: APIRequestContext,
  token: string,
  skuPublicId: string,
  quantity = 1,
): Promise<string> {
  const response = await ctx.post(`${API_BASE}/cart/items/`, {
    headers: bearer(token),
    data: { sku_public_id: skuPublicId, quantity },
  })
  expect([200, 201]).toContain(response.status())
  return (await response.json()).public_id as string
}

export async function claimE2eCoupon(
  ctx: APIRequestContext,
  token: string,
): Promise<string | null> {
  const available = await ctx.get(`${API_BASE}/coupons/available/`, { headers: bearer(token) })
  expect(available.ok()).toBeTruthy()
  const body = await available.json()
  const items: Array<{ public_id: string; name: string }> = body.results ?? body
  const coupon = items.find((item) => item.name === E2E_COUPON)
  if (!coupon) {
    return null
  }
  const claim = await ctx.post(`${API_BASE}/coupons/${coupon.public_id}/claim/`, {
    headers: bearer(token),
  })
  expect([201, 422]).toContain(claim.status())
  return coupon.public_id
}

export async function createOrderViaApi(
  ctx: APIRequestContext,
  token: string,
  options: { quantity?: number; useCoupon?: boolean; spec?: string } = {},
): Promise<OrderPayload> {
  const { quantity = 1, useCoupon = false, spec = E2E_SKU } = options
  await resetCart(ctx, token)
  const product = await getE2eProduct(ctx)
  const sku = findSku(product, spec)
  const cartItemId = await addCartItem(ctx, token, sku.public_id, quantity)
  const addressId = await ensureAddress(ctx, token)
  const payload: Record<string, unknown> = {
    cart_item_public_ids: [cartItemId],
    address_public_id: addressId,
  }
  if (useCoupon) {
    const couponId = await claimE2eCoupon(ctx, token)
    if (couponId) {
      payload.user_coupon_public_id = couponId
    }
  }
  const response = await ctx.post(`${API_BASE}/orders/`, {
    headers: {
      ...bearer(token),
      'Idempotency-Key': `e2e-${Date.now()}-${Math.floor(Math.random() * 100000)}`,
    },
    data: payload,
  })
  expect(response.status(), 'API 创建订单失败').toBe(201)
  return (await response.json()) as OrderPayload
}

export async function mockPayViaApi(
  ctx: APIRequestContext,
  token: string,
  orderNo: string,
  status: 'SUCCESS' | 'FAILED' = 'SUCCESS',
): Promise<void> {
  const start = await ctx.post(`${API_BASE}/payments/${orderNo}/mock-pay/`, {
    headers: bearer(token),
    data: { channel: 'ALIPAY_MOCK' },
  })
  expect(start.ok(), `发起模拟支付失败：${start.status()}`).toBeTruthy()
  const cashier = await start.json()
  const callback = await ctx.post(`${API_BASE}/payments/callback/`, {
    headers: bearer(token),
    data: {
      payment_no: cashier.payment_no,
      amount: cashier.amount,
      status,
      signature: cashier.sign,
      transaction_ref: `e2e-${status.toLowerCase()}`,
    },
  })
  expect(callback.status(), '支付回调失败').toBe(200)
}

export async function shipOrderViaApi(
  ctx: APIRequestContext,
  operatorToken: string,
  orderNo: string,
): Promise<void> {
  const response = await ctx.post(`${API_BASE}/admin/orders/${orderNo}/ship/`, {
    headers: bearer(operatorToken),
    data: { tracking_no: `SF${Date.now()}` },
  })
  expect(response.status(), '后台发货失败').toBe(200)
}

export function e2eMailDir(): string {
  return path.resolve(process.cwd(), '../backend/logs/e2e-mail')
}

export async function waitForEmailCode(email: string): Promise<string> {
  const dir = e2eMailDir()
  const deadline = Date.now() + 15_000
  while (Date.now() < deadline) {
    if (fs.existsSync(dir)) {
      const files = fs
        .readdirSync(dir)
        .filter((name) => name.endsWith('.log'))
        .map((name) => path.join(dir, name))
        .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)
      for (const file of files) {
        const content = fs.readFileSync(file, 'utf8')
        if (!content.includes(email)) {
          continue
        }
        const match = content.match(/验证码是\s*(\d{6})/)
        if (match) {
          return match[1]
        }
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 300))
  }
  throw new Error(`未在 15 秒内获取 ${email} 的验证码邮件`)
}
