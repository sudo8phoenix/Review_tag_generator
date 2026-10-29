import { expect, test } from '@playwright/test'

test('explores robustness, review priorities and real product comparison', async ({ page, request }, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
  const left = await (await request.post('/api/demo/products', { data: { name: `Evidence lab ${Date.now()}` } })).json()
  const right = await (await request.post('/api/demo/products', { data: { name: `Comparison lab ${Date.now()}` } })).json()
  const leftJob = await (await request.post(`/api/demo/products/${left.id}/jobs`, { data: { reviews: ['Great display.', 'Excellent display.', 'Amazing display.', 'Poor display.', 'Terrible display.', 'Nothing to report.'] } })).json()
  const rightJob = await (await request.post(`/api/demo/products/${right.id}/jobs`, { data: { reviews: ['Poor display.', 'Terrible display.', 'Bad display.'] } })).json()
  for (const job of [leftJob, rightJob]) {
    await expect.poll(async () => (await (await request.get(`/api/demo/jobs/${job.id}`)).json()).status).toBe('completed')
  }
  await page.goto(`/products/${left.id}/advanced`)
  const robustness = page.getByRole('region', { name: 'Evidence robustness', exact: true })
  await expect(robustness.getByText('40%', { exact: true })).toHaveCount(2)
  await robustness.getByLabel('Remove one vote').selectOption('0')
  await expect(robustness.getByText('weak', { exact: true })).toBeVisible()
  const quality = page.getByRole('region', { name: 'Review quality queue' })
  await expect(quality.getByText('Nothing to report.', { exact: true })).toBeVisible()
  const download = page.waitForEvent('download')
  await quality.getByRole('button', { name: 'Export JSON' }).click()
  expect((await download).suggestedFilename()).toContain('review-quality-')
  for (const width of [320, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    await expect(robustness.getByRole('heading', { name: 'Evidence robustness' })).toBeVisible()
    await expect.poll(() => page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(width)
    await page.screenshot({ path: testInfo.outputPath(`evidence-tools-${width}.png`), fullPage: true })
  }
  await page.goto(`/compare?left=${left.id}`)
  const comparison = page.getByRole('region', { name: 'Which laptop fits you better?' })
  await comparison.getByLabel('Compare with').selectOption(right.id)
  await comparison.getByRole('button', { name: 'Compare products' }).click()
  await expect(comparison.locator('.comparison-verdict h3')).toHaveText(`${left.name} looks stronger in these reviews`)
  await expect(comparison.locator('.comparison-verdict')).toContainText('Stronger feedback for display.')
  await expect(comparison.getByRole('table')).not.toBeVisible()
  await comparison.getByText('Explore the detailed feature evidence', { exact: true }).click()
  await expect(comparison.getByRole('table')).toBeVisible()
  expect(errors).toEqual([])
})
