import { chromium, expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'

test('built Chrome extension previews without saving and recovers a lost save response', async ({ request }, testInfo) => {
  const product = await (await request.post('/api/demo/products', { data: { name: `Extension recovery ${Date.now()}` } })).json()
  const extensionPath = fileURLToPath(new URL('../dist-extension', import.meta.url))
  const context = await chromium.launchPersistentContext('', {
    channel: 'chromium', headless: true,
    args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
  })
  try {
    const worker = context.serviceWorkers()[0] ?? await context.waitForEvent('serviceworker')
    const apiPort = Number(new URL(process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000').port)
    const webPort = Number(new URL(testInfo.project.use.baseURL as string).port)
    await worker.evaluate(async ({ apiPort, webPort }) => {
      // This is the actual extension storage API, in an isolated Chromium profile.
      const chrome = (globalThis as unknown as { chrome: { storage: { local: { set(values: unknown): Promise<void> } } } }).chrome
      await chrome.storage.local.set({ 'review-companion-connection-v1': { apiPort, webPort } })
    }, { apiPort, webPort })
    const page = await context.newPage()
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto(`chrome-extension://${new URL(worker.url()).host}/sidepanel.html`)
    await expect(page.getByText('Heuristic demo · local service', { exact: true })).toBeVisible()
    // Hold only tab discovery to reproduce a switch before capture owns a tab.
    // Service calls, extension storage, and the later analysis/save remain real.
    await page.evaluate(() => {
      const probe = globalThis as typeof globalThis & {
        chrome: { tabs: { query: (...args: unknown[]) => Promise<unknown> }; scripting: { executeScript: (...args: unknown[]) => Promise<unknown> } }
        captureStarted?: boolean; captureReads?: number; releaseCapture?: () => void; restoreCapture?: () => void
      }
      const originalQuery = probe.chrome.tabs.query
      const originalScript = probe.chrome.scripting.executeScript
      probe.captureReads = 0
      probe.chrome.tabs.query = async () => {
        probe.captureStarted = true
        await new Promise<void>(resolve => { probe.releaseCapture = resolve })
        return [{ id: 777, url: 'https://www.amazon.com/dp/B000000001' }]
      }
      probe.chrome.scripting.executeScript = async (...args) => { probe.captureReads = (probe.captureReads ?? 0) + 1; return originalScript(...args) }
      probe.restoreCapture = () => { probe.chrome.tabs.query = originalQuery; probe.chrome.scripting.executeScript = originalScript }
    })
    await page.getByRole('button', { name: 'Capture from current page' }).click()
    await expect.poll(() => page.evaluate(() => (globalThis as typeof globalThis & { captureStarted?: boolean }).captureStarted)).toBe(true)
    const otherTab = await context.newPage()
    await expect(page.getByRole('alert')).toContainText('The browsing page changed')
    await page.evaluate(() => (globalThis as typeof globalThis & { releaseCapture?: () => void }).releaseCapture?.())
    await expect(page.getByRole('button', { name: 'Capture from current page' })).toBeEnabled()
    expect(await page.evaluate(() => (globalThis as typeof globalThis & { captureReads?: number }).captureReads)).toBe(0)
    await page.evaluate(() => (globalThis as typeof globalThis & { restoreCapture?: () => void }).restoreCapture?.())
    await otherTab.close()
    await page.bringToFront()
    await page.getByText('Or paste review text', { exact: true }).click()
    await page.getByLabel('Reviews, separated by a blank line').fill('Great display.\n\nExcellent display.\n\nAmazing display.')
    await page.getByRole('button', { name: 'Use pasted reviews' }).click()
    await page.getByLabel('Product for captured reviews').selectOption(product.id)
    await page.getByRole('button', { name: 'Preview feature feedback' }).click()
    await expect(page.getByRole('heading', { name: 'What stands out' })).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText(/3 unique reviews/)).toBeVisible()
    expect((await (await request.get(`/api/demo/products/${product.id}`)).json()).insights.review_count).toBe(0)
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 1000 })
      expect(await page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(width)
      await page.screenshot({ path: testInfo.outputPath(`actual-extension-${width}.png`), fullPage: true })
    }
    const keys: string[] = []
    let acceptedJobId = ''
    let interrupted = false
    await page.route('**/api/demo/products/*/jobs', async route => {
      keys.push(route.request().headers()['idempotency-key'] ?? '')
      if (!interrupted) {
        interrupted = true
        // Let the real API accept it, then simulate losing only its response.
        acceptedJobId = (await (await route.fetch()).json()).id
        await route.abort('failed')
      } else await route.continue()
    })
    await page.getByRole('button', { name: 'Save captured reviews' }).click()
    await expect(page.getByRole('button', { name: 'Resume save' })).toBeVisible()
    await page.reload()
    await page.getByRole('button', { name: 'Resume save' }).click()
    await expect(page.locator('.panel-job')).toContainText('completed', { timeout: 30_000 })
    expect(keys).toHaveLength(2)
    expect(keys[0]).toMatch(/^[0-9a-f-]{36}$/i)
    expect(keys[1]).toBe(keys[0])
    const detail = await (await request.get(`/api/demo/products/${product.id}`)).json()
    expect(detail.insights.review_count).toBe(3)
    expect(detail.insights.aspects[0].counts.positive).toBe(3)
    // The web app may delete a completed product while the panel is closed.
    expect((await request.delete(`/api/demo/products/${product.id}`)).ok()).toBe(true)
    await worker.evaluate(async recovery => {
      const chrome = (globalThis as unknown as { chrome: { storage: { local: { set(values: unknown): Promise<void> } } } }).chrome
      await chrome.storage.local.set({ 'review-companion-pending-v1': recovery })
    }, { productId: product.id, productName: product.name, reviews: ['Great display.'], key: keys[0], connection: { apiPort, webPort }, jobId: acceptedJobId })
    await page.reload()
    await page.getByRole('button', { name: 'Clear missing job recovery' }).click()
    await expect(page.getByRole('button', { name: 'Capture from current page' })).toBeEnabled()
    await expect(page.getByLabel('Product for captured reviews')).toHaveValue('')
    expect(errors).toEqual([])
  } finally { await context.close() }
})

test('saved product search, feature filters and comparison retain their context', async ({ page, request }) => {
  const product = await (await request.post('/api/demo/products', { data: { name: `Shopping context ${Date.now()}` } })).json()
  const job = await (await request.post(`/api/demo/products/${product.id}/jobs`, { data: { reviews: ['Great battery.', 'Excellent battery.', 'Poor battery.'] } })).json()
  await expect.poll(async () => (await (await request.get(`/api/demo/jobs/${job.id}`)).json()).status).toBe('completed')
  await page.goto(`/products?q=${encodeURIComponent(product.name)}`)
  const row = page.locator('.saved-product-row').filter({ hasText: product.name })
  await row.getByRole('link', { name: 'View insights' }).click()
  await page.getByRole('button', { name: /Battery good/ }).click()
  await page.getByRole('button', { name: 'Negative 1', exact: true }).click()
  await expect(page).toHaveURL(/aspect=battery&sentiment=negative/)
  await expect(page.locator('.source-review')).toHaveCount(1)
  await expect(page.locator('.source-review')).toContainText('Poor battery.')
  await page.reload()
  await expect(page.getByRole('button', { name: 'Negative 1', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('navigation', { name: 'Product views' }).getByRole('link', { name: 'Compare', exact: true }).click()
  await expect(page.getByLabel('Start with')).toHaveValue(product.id)
})

test('changing product routes never carries a review draft into another product', async ({ page, request }) => {
  const first = await (await request.post('/api/demo/products', { data: { name: `Draft A ${Date.now()}` } })).json()
  const second = await (await request.post('/api/demo/products', { data: { name: `Draft B ${Date.now()}` } })).json()
  await page.goto(`/products/${first.id}/review`)
  await page.getByLabel('Customer review').fill('This draft belongs only to product A.')
  await page.evaluate(id => { history.pushState({}, '', `/products/${id}/review`); window.dispatchEvent(new PopStateEvent('popstate')) }, second.id)
  await expect(page.getByLabel('Customer review')).toHaveValue('')
  await page.getByLabel('Customer review').fill('This draft belongs only to product B.')
  await page.goBack()
  await expect(page.getByLabel('Customer review')).toHaveValue('This draft belongs only to product A.')
})
