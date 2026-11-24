import { expect, test } from '@playwright/test'
import { PASSWORD, uniqueEmail, uniqueUsername, waitForEmailCode } from './helpers'

test('E2E-01 注册 → 登录 → 刷新页面仍保持登录', async ({ page }) => {
  const email = uniqueEmail('e2e.reg')
  const username = uniqueUsername('e2ereg')

  await page.goto('/register')
  await page.getByPlaceholder('用于接收验证码与找回密码').fill(email)
  await page.getByRole('button', { name: '获取验证码' }).click()

  const code = await waitForEmailCode(email)
  await page.getByPlaceholder('6 位数字').fill(code)
  await page.getByPlaceholder('3–20 位字母、数字或下划线').fill(username)
  await page.getByPlaceholder('8–64 位，需包含字母与数字').fill(PASSWORD)
  await page.getByPlaceholder('请再次输入密码').fill(PASSWORD)
  await page.getByRole('button', { name: '注册并登录' }).click()

  await expect(page).not.toHaveURL(/\/register/, { timeout: 20_000 })

  await page.reload()
  await expect(page).not.toHaveURL(/\/login/)
  await expect(page).not.toHaveURL(/\/register/)
})
