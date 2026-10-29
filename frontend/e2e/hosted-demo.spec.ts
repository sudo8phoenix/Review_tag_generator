import { chromium, expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const liveUrl = process.env.LIVE_DEMO_URL

test('hosted extension connects, captures, previews and saves through Vercel', async ({ request }, testInfo) => {
  test.skip(!liveUrl, 'Set LIVE_DEMO_URL to explicitly run against the public demo')
  test.setTimeout(600_000)
  const extensionPath = fileURLToPath(new URL('../dist-extension', import.meta.url))
  const context = await chromium.launchPersistentContext('', {
    channel: 'chromium', headless: true,
    args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
  })
  let productId = ''
  try {
    const response = await request.post(`${liveUrl}/api/demo/products`, { data: { name: `Disposable hosted extension QA ${Date.now()}` } })
    expect(response.ok()).toBeTruthy()
    productId = (await response.json()).id
    const worker = context.serviceWorkers()[0] ?? await context.waitForEvent('serviceworker')
    const panel = await context.newPage()
    const errors: string[] = []
    panel.on('pageerror', error => errors.push(error.message))
    panel.on('console', msg => { if (msg.type() === 'error' && /Content Security Policy|Refused to connect/.test(msg.text())) errors.push(msg.text()) })
    await panel.goto(`chrome-extension://${new URL(worker.url()).host}/sidepanel.html`)
    await expect(panel.getByText('Vercel · trained models', { exact: true })).toBeVisible({ timeout: 90_000 })
    const retailer = await context.newPage()
    await context.route('https://www.amazon.in/hosted-qa', route => route.fulfill({ contentType: 'text/html', body: '<title>Disposable QA laptop</title><div data-hook="review"><span data-hook="review-body">QA test review: The battery life is excellent but the display is dim.</span></div>' }))
    await retailer.goto('https://www.amazon.in/hosted-qa')
    await retailer.bringToFront()
    await panel.getByRole('button', { name: 'Capture from current page' }).evaluate((button: HTMLButtonElement) => button.click())
    await expect(panel.locator('.panel-capture')).toContainText('1 review captured')
    await panel.getByLabel('Product for captured reviews').selectOption(productId)
    await panel.getByRole('button', { name: 'Preview feature feedback' }).evaluate((button: HTMLButtonElement) => button.click())
    await expect(panel.getByRole('heading', { name: 'What stands out' })).toBeVisible({ timeout: 90_000 })
    const before = await (await request.get(`${liveUrl}/api/demo/products/${productId}`)).json()
    expect(before.insights.review_count).toBe(0)
    await panel.getByRole('button', { name: 'Save captured reviews', exact: true }).last().evaluate((button: HTMLButtonElement) => button.click())
    await expect(panel.getByRole('button', { name: 'Reviews saved', exact: true }).last()).toBeVisible({ timeout: 480_000 })
    const after = await (await request.get(`${liveUrl}/api/demo/products/${productId}`)).json()
    expect(after.insights.review_count).toBe(1)
    expect(after.reviews[0].tags.length).toBeGreaterThan(0)
    expect(errors).toEqual([])
    for (const width of [390, 1440]) {
      await panel.setViewportSize({ width, height: 1000 })
      expect(await panel.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(width)
      await panel.screenshot({ path: testInfo.outputPath(`hosted-extension-${width}.png`), fullPage: true })
    }
  } finally {
    await context.close()
    if (productId) {
      const cleanup = await request.delete(`${liveUrl}/api/demo/products/${productId}`)
      if (!cleanup.ok()) console.warn(`QA cleanup deferred for ${productId}: ${cleanup.status()}`)
    }
  }
})


test('hosted website loads saved products, review preview and responsive routes', async ({ page, request }, testInfo) => {
  test.skip(!liveUrl, 'Set LIVE_DEMO_URL to explicitly run against the public demo')
  test.setTimeout(180_000)
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const name = `Disposable hosted website QA ${Date.now()}`
  let id = ''
  try {
    await page.goto(`${liveUrl}/products`)
    await expect(page.getByRole('heading', { level: 1, name: 'Saved products' })).toBeVisible()
    await page.getByLabel('Create a product', { exact: true }).fill(name)
    await page.getByRole('button', { name: 'Create product', exact: true }).click()
    const row = page.locator('.saved-product-row').filter({ has: page.getByRole('heading', { name, exact: true }) })
    await row.getByRole('link', { name: 'Analyze review', exact: true }).click()
    id = new URL(page.url()).pathname.split('/')[2] ?? ''
    await page.getByLabel('Customer review', { exact: true }).fill('QA test review: The battery is excellent and the keyboard feels comfortable.')
    await page.getByRole('button', { name: 'Preview analysis', exact: true }).click()
    await expect(page.getByText(/Preview ready · 1 review/)).toBeVisible({ timeout: 90_000 })
    await expect(page.getByRole('button', { name: 'Save review', exact: true })).toBeEnabled()
    const detail = await (await request.get(`${liveUrl}/api/demo/products/${id}`)).json()
    expect(detail.insights.review_count).toBe(0)
    for (const path of ['/products', '/compare', '/companion', '/models']) {
      await page.goto(`${liveUrl}${path}`)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      if (path === '/products') await expect(page.locator('.saved-product-row').first()).toBeVisible()
      if (path === '/compare') await expect(page.getByLabel('Start with', { exact: true })).toBeVisible()
      if (path === '/models') await expect(page.getByRole('heading', { name: 'Aspect extraction · held-out test' })).toBeVisible()
      await expect(page.getByText('Page not found', { exact: true })).toHaveCount(0)
      for (const width of [390, 1440]) {
        await page.setViewportSize({ width, height: 1000 })
        expect(await page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(width)
        await page.screenshot({ path: testInfo.outputPath(`hosted-${path.slice(1)}-${width}.png`), fullPage: true })
      }
    }
    expect(errors).toEqual([])
  } finally {
    if (id) await request.delete(`${liveUrl}/api/demo/products/${id}`)
  }
})

test('hosted saved laptop comparison has published evidence and handles disabled AI', async ({ page, request }, testInfo) => {
  test.skip(!liveUrl, 'Set LIVE_DEMO_URL to explicitly run against the public demo')
  test.setTimeout(600_000)
  const products = await (await request.get(`${liveUrl}/api/demo/products`)).json() as { id: string; name: string }[]
  const left = products.find(product => product.name === 'MacBook Air M2')
  const right = products.find(product => product.name === 'Lenovo IdeaPad Slim 3 Ryzen 5 5500U')
  expect(left).toBeTruthy()
  expect(right).toBeTruthy()
  await expect.poll(async () => {
    const details = await Promise.all([left!, right!].map(async product => (await request.get(`${liveUrl}/api/demo/products/${product.id}`)).json()))
    return details.every(detail => detail.insights.review_count >= 30 && !detail.stale)
  }, { timeout: 480_000, intervals: [5000] }).toBe(true)
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`${liveUrl}/compare?left=${left!.id}`)
  await page.getByLabel('Compare with', { exact: true }).selectOption(right!.id)
  await page.getByRole('button', { name: 'Compare products', exact: true }).click()
  await expect(page.locator('.comparison-verdict h3')).toBeVisible()
  await expect(page.locator('.comparison-verdict')).toContainText('30 and 30 saved reviews')
  await expect(page.getByRole('table')).not.toBeVisible()
  await page.getByText('Explore the detailed feature evidence', { exact: true }).click()
  await expect(page.getByRole('table')).toBeVisible()
  await page.getByRole('button', { name: 'Explain this comparison with AI', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('disabled')
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(width)
    await page.screenshot({ path: testInfo.outputPath(`hosted-comparison-${width}.png`), fullPage: true })
  }
  expect(errors).toEqual([])
})
