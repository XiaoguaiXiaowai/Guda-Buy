import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT || 8001)
const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT || 5174)
const CONFIG_DIR = fileURLToPath(new URL('.', import.meta.url))
const REPO_ROOT = path.resolve(CONFIG_DIR, '..')

export default defineConfig({
  testDir: './e2e',
  outputDir: 'reports/playwright-artifacts',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ['list'],
    ['junit', { outputFile: 'reports/playwright.xml' }],
    ['html', { outputFolder: 'reports/playwright-html', open: 'never' }],
  ],
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], channel: 'chrome' } },
  ],
  webServer: [
    {
      command: `bash ${path.join(REPO_ROOT, 'scripts/e2e-backend.sh')}`,
      url: `http://127.0.0.1:${BACKEND_PORT}/healthz/`,
      reuseExistingServer: true,
      timeout: 180_000,
      stdout: 'ignore',
      stderr: 'pipe',
    },
    {
      command: `pnpm exec vite --host 127.0.0.1 --port ${FRONTEND_PORT} --strictPort`,
      url: `http://127.0.0.1:${FRONTEND_PORT}`,
      reuseExistingServer: true,
      timeout: 120_000,
      env: { VITE_PROXY_TARGET: `http://127.0.0.1:${BACKEND_PORT}` },
    },
  ],
})
