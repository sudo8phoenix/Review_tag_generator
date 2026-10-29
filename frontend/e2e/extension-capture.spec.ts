import { chromium, expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { readFile } from 'node:fs/promises'

test('product creation recovers after the panel opens while the API is unavailable', async () => {
  const extensionPath = fileURLToPath(new URL('../dist-extension', import.meta.url))
  const context = await chromium.launchPersistentContext('', {
    channel: 'chromium', headless: true,
    args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
  })
  try {
    const worker = context.serviceWorkers()[0] ?? await context.waitForEvent('serviceworker')
    let available = false
    let created = false
    let reviewsSaved = false
    const job = { id: 'saved-job', status: 'completed', completed_rows: 1, total_rows: 1, failed_rows: 0 }
    const product = { id: 'reconnect-product', name: 'HP Victus', review_count: 0 }
    await context.route('http://127.0.0.1:8000/api/**', async route => {
      const request = route.request()
      if (request.url().endsWith('/jobs')) {
        expect(request.postDataJSON()).toEqual({ reviews: ['Excellent battery.'] })
        reviewsSaved = true
        return route.fulfill({ status: 202, json: job })
      }
      if (request.url().endsWith('/jobs/saved-job')) return route.fulfill({ json: job })
      if (request.url().endsWith('/health')) {
        if (!available) return route.abort('connectionrefused')
        return route.fulfill({ json: { backend: 'transformer', worker_ready: true } })
      }
      if (request.method() === 'POST') {
        expect(request.postDataJSON()).toEqual({ name: product.name })
        created = true
        available = true
        return route.fulfill({ status: 201, json: product })
      }
      return route.fulfill({ json: created ? [product] : [] })
    })
    const panel = await context.newPage()
    await panel.goto(`chrome-extension://${new URL(worker.url()).host}/sidepanel.html`)
    await expect(panel.getByRole('alert')).toContainText('Retrying automatically')
    // Model the service coming back without closing/reopening the panel.
    available = true
    await expect(panel.getByText('Local trained models', { exact: true })).toBeVisible({ timeout: 10_000 })
    available = false
    await panel.reload()
    await expect(panel.getByRole('alert')).toContainText('Retrying automatically')
    await panel.getByText('Or paste review text', { exact: true }).click()
    await panel.getByLabel('Reviews, separated by a blank line').fill('Excellent battery.')
    await panel.getByRole('button', { name: 'Use pasted reviews' }).click()
    await panel.getByText('Create a product', { exact: true }).click()
    await panel.getByLabel('Product name', { exact: true }).fill(product.name)
    // A failed initial health check must not prevent a real create request.
    await panel.getByRole('button', { name: 'Create product', exact: true }).click()
    await expect(panel.getByLabel('Product for captured reviews')).toHaveValue(product.id)
    await expect(panel.locator('.panel-capture')).toContainText('1 review captured')
    await expect(panel.getByRole('button', { name: 'Preview feature feedback' })).toBeEnabled()
    expect(created).toBe(true)
    const downloadPromise = panel.waitForEvent('download')
    await panel.getByRole('button', { name: 'Download captured reviews (.txt)', exact: true }).click()
    const download = await downloadPromise
    expect(await readFile((await download.path())!, 'utf8')).toBe('Excellent battery.')
    await panel.getByRole('button', { name: 'Save captured reviews', exact: true }).click()
    await expect(panel.getByRole('button', { name: 'Reviews saved', exact: true })).toBeVisible()
    expect(reviewsSaved).toBe(true)
  } finally { await context.close() }
})

test('retailers capture up to 100 reviews without a toolbar permission grant', async () => {
  const extensionPath = fileURLToPath(new URL('../dist-extension', import.meta.url))
  const context = await chromium.launchPersistentContext('', {
    channel: 'chromium', headless: true,
    args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
  })
  try {
    const worker = context.serviceWorkers()[0] ?? await context.waitForEvent('serviceworker')
    const panel = await context.newPage()
    await panel.goto(`chrome-extension://${new URL(worker.url()).host}/sidepanel.html`)
    const product = await context.newPage()
    for (const [host, markup] of [
      ['www.amazon.in', '<div data-hook="review"><span data-hook="review-body">TEXT</span></div>'],
      ['www.amazon.com', '<div data-hook="review"><span data-hook="review-body">TEXT</span></div>'],
      ['www.flipkart.com', '<div class="ZmyHeo">TEXT</div>'],
      ['www.walmart.com', '<div data-testid="review-text">TEXT</div>'],
      ['www.bestbuy.com', '<div class="review-body">TEXT</div>'],
      ['www.target.com', '<div data-test="review-content">TEXT</div>'],
    ]) {
      await context.route(`https://${host}/**`, route => route.fulfill({
        contentType: 'text/html',
        body: '<title>Test laptop</title>' + Array.from({ length: 105 }, (_, i) => markup.replace('TEXT', `Review ${i}: The display is bright and clear.`)).join(''),
      }))
      await product.goto(`https://${host}/dp/B000000001`)
      await product.bringToFront()
      // Operate the panel without activating its standalone test tab.
      await panel.getByRole('button', { name: 'Capture from current page' }).evaluate((button: HTMLButtonElement) => button.click())
      await expect(panel.locator('.panel-capture')).toContainText('100 reviews captured')
      await expect(panel.locator('.panel-capture')).toContainText('Test laptop')
      await expect(panel.locator('.panel-captured-text')).toHaveCount(100)
      await expect(panel.locator('.panel-captured-text').first()).toContainText('The display is bright and clear.')
      await expect(panel.locator('.panel-capture')).toContainText('100-review limit')
    }
  } finally { await context.close() }
})
