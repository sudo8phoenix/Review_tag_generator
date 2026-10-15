import { expect, test } from '@playwright/test'

test('previews a review before saving it and observes job completion', async ({ page }, testInfo) => {
  const productName = `Browser flow ${Date.now()}`
  const browserErrors: string[] = []
  page.on('pageerror', error => browserErrors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') browserErrors.push(message.text()) })
  await page.goto('/products')
  await page.getByLabel('Create a product').fill(productName)
  await page.getByRole('button', { name: 'Create product' }).click()
  const product = page.locator('section.content-section').filter({ has: page.getByRole('heading', { name: productName }) })
  await product.getByRole('link', { name: 'View insights' }).click()
  await page.getByRole('link', { name: 'Analyze a review' }).click()
  for (const width of [320, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await expect(page.getByLabel('Customer review')).toBeVisible()
    expect(await page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(width)
    await page.screenshot({ path: testInfo.outputPath(`review-form-${width}.png`), fullPage: true })
  }
  await page.setViewportSize({ width: 1280, height: 900 })

  await page.getByLabel('Customer review').fill('The battery lasts all day and the display is bright.')
  await page.getByRole('button', { name: 'Preview analysis' }).click()
  await expect(page.getByText(/Preview ready · 1 review/)).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('button', { name: 'Save review' })).toBeEnabled()
  await expect(page.getByText(/product totals are unchanged/)).toBeVisible()

  const saveRequest = page.waitForRequest(request => request.url().endsWith('/jobs') && request.method() === 'POST')
  await page.getByRole('button', { name: 'Save review' }).click()
  const request = await saveRequest
  expect(request.headers()['idempotency-key']).toMatch(/^[0-9a-f-]{36}$/i)
  await expect(page.getByRole('heading', { name: 'Review save progress' })).toBeVisible()
  await expect(page.getByText(/completed · 1 of 1 rows analyzed/)).toBeVisible({ timeout: 30_000 })
  await page.getByRole('link', { name: 'View updated product insights' }).click()
  await expect(page.getByRole('heading', { name: 'Review evidence' })).toBeVisible()
  await expect(page.getByText('The battery lasts all day and the display is bright.').last()).toBeVisible()
  expect(browserErrors).toEqual([])
})

test('restores an unsaved review draft after reload', async ({ page }) => {
  await page.goto('/products/demo-laptop/review')
  const draft = 'The keyboard feels excellent even after a long day.'
  await page.getByLabel('Customer review').fill(draft)
  await page.reload()
  await expect(page.getByRole('status').filter({ hasText: 'Recovered an unsaved draft' })).toBeVisible()
  await expect(page.getByLabel('Customer review')).toHaveValue(draft)
})
