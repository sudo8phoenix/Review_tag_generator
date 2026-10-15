import { defineConfig, devices } from '@playwright/test'

const browserPort = process.env.PLAYWRIGHT_PORT ?? '5173'
if (!/^\d+$/.test(browserPort)) throw new Error('PLAYWRIGHT_PORT must be a numeric port')
const browserUrl = `http://127.0.0.1:${browserPort}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: browserUrl,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: `npm run dev -- --port ${browserPort} --strictPort`,
    url: browserUrl,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
