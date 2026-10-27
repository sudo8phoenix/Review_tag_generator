import { expect, test } from '@playwright/test'

test('removes an import, clears saved data and deletes a product with confirmation', async ({ page, request }, testInfo) => {
  const name = `Saved-data test ${Date.now()}`
  const product = await (await request.post('/api/demo/products', { data: { name } })).json()
  const first = await (await request.post(`/api/demo/products/${product.id}/imports`, { data: { filename: 'first.txt', content: 'Great display.\nPoor battery.' } })).json()
  const second = await (await request.post(`/api/demo/products/${product.id}/imports`, { data: { filename: 'second.txt', content: 'Great display.\nExcellent keyboard.' } })).json()
  for (const job of [first, second]) {
    await expect.poll(async () => (await (await request.get(`/api/demo/jobs/${job.id}`)).json()).status).toBe('completed')
  }
  await page.goto(`/products/${product.id}/settings`)
  const imports = page.getByRole('region', { name: 'Saved imports', exact: true })
  await expect(imports.getByText('first.txt', { exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('saved-imports-desktop.png'), fullPage: true })
  await imports.getByRole('button', { name: 'Remove import first.txt' }).click()
  const removal = page.getByRole('dialog', { name: 'Remove saved import', exact: true })
  await removal.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(imports.getByText('first.txt', { exact: true })).toBeVisible()
  await imports.getByRole('button', { name: 'Remove import first.txt' }).click()
  await removal.getByRole('button', { name: 'Remove saved import', exact: true }).click()
  await expect(imports.getByText('first.txt', { exact: true })).toHaveCount(0)
  await expect(imports.getByText('second.txt', { exact: true })).toBeVisible()
  expect((await (await request.get(`/api/demo/products/${product.id}`)).json()).insights.review_count).toBe(1)
  await page.evaluate(id => {
    localStorage.setItem(`review-tag-draft:${id}:import`, 'saved product draft')
    localStorage.setItem('review-tag-draft:unrelated:import', 'keep this draft')
  }, product.id)
  await page.getByRole('button', { name: 'Clear saved reviews', exact: true }).click()
  const clear = page.getByRole('dialog', { name: 'Clear saved reviews?', exact: true })
  await clear.getByRole('button', { name: 'Clear saved data', exact: true }).click()
  await expect(page.getByText('No saved import batches for this product.')).toBeVisible()
  expect(await page.evaluate(id => localStorage.getItem(`review-tag-draft:${id}:import`), product.id)).toBeNull()
  expect(await page.evaluate(() => localStorage.getItem('review-tag-draft:unrelated:import'))).toBe('keep this draft')
  // Refreshing detail can unmount the dialog after its server-side success.
  if (await clear.isVisible()) await clear.getByRole('button', { name: 'Close', exact: true }).click()
  for (const width of [320, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    await expect.poll(() => page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(width)
    await page.screenshot({ path: testInfo.outputPath(`saved-data-${width}.png`), fullPage: true })
  }
  await page.getByRole('button', { name: 'Delete product', exact: true }).click()
  await page.getByRole('dialog', { name: 'Delete product?', exact: true }).getByRole('button', { name: 'Delete product permanently', exact: true }).click()
  await expect(page).toHaveURL(/\/products$/)
  await expect(page.getByRole('heading', { name, exact: true })).toHaveCount(0)
  expect((await request.get(`/api/demo/products/${product.id}`)).status()).toBe(404)
})


test('product list discards drafts for removed products and keeps existing product drafts', async ({ page, request }) => {
  const product = await (await request.post('/api/demo/products', { data: { name: `Keep draft ${Date.now()}` } })).json()
  await page.goto('/products')
  await page.evaluate(id => {
    localStorage.setItem('review-tag-draft:removed-product:import', 'old deleted import')
    localStorage.setItem(`review-tag-draft:${id}:review`, 'keep existing product draft')
  }, product.id)
  await page.reload()
  await expect(page.getByRole('heading', { name: product.name, exact: true })).toBeVisible()
  await expect.poll(() => page.evaluate(() => localStorage.getItem('review-tag-draft:removed-product:import'))).toBeNull()
  expect(await page.evaluate(id => localStorage.getItem(`review-tag-draft:${id}:review`), product.id)).toBe('keep existing product draft')
})
