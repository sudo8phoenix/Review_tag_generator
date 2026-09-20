import { expect, test } from '@playwright/test'

test('redirects home to products and exposes the app landmarks', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/products$/)
  await expect(page.getByRole('banner')).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible()
  await expect(page.getByRole('main')).toBeVisible()
  await expect(page.getByRole('heading', { level: 1, name: 'Products' })).toBeVisible()
})

test('primary navigation reaches metrics and returns to products', async ({ page }) => {
  await page.goto('/products')
  await page.getByRole('link', { name: 'Model metrics' }).click()
  await expect(page).toHaveURL(/\/models$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Model metrics' })).toBeVisible()
  await page.getByRole('link', { name: 'Products' }).click()
  await expect(page).toHaveURL(/\/products$/)
})

test('skip link is keyboard reachable and moves focus to main content', async ({ page }) => {
  await page.goto('/products')
  await page.keyboard.press('Tab')
  const skipLink = page.getByRole('link', { name: 'Skip to main content' })
  await expect(skipLink).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.locator('#main-content')).toBeFocused()
})

test('navigation links follow a predictable keyboard order', async ({ page }) => {
  await page.goto('/products')
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Model metrics' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/models$/)
})

for (const width of [375, 768, 1440]) {
  test(`shell fits viewport at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/products')
    await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible()
    const dimensions = await page.evaluate(() => ({
      body: document.body.scrollWidth,
      viewport: document.documentElement.clientWidth,
    }))
    expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport)
  })
}
