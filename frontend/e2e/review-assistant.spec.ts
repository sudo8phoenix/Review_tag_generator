import { expect, test } from '@playwright/test'

// Provider responses are injected only in this browser test; backend grounding
// and provider transport validation have independent integration/unit coverage.
async function assistantFixture(page: import('@playwright/test').Page, enabled = true) {
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    const review = { review: { review_id: 'review-1', review_text: 'speed is excellent' }, backend: 'transformer', tags: [{ raw_aspect: 'speed', normalized_aspect: null, normalized_aspect_id: null, start_char: 0, end_char: 5, sentiment: 'positive', confidence: .93, tag: null }] }
    const bodies: Record<string, unknown> = {
      '/api/assist/status': { enabled, provider: 'groq', model: 'openai/gpt-oss-20b', reason: enabled ? 'Configured' : 'Set GROQ_API_KEY on the server to enable Groq.' },
      '/api/demo/products/assistant-fixture': { product: { id: 'assistant-fixture', name: 'Assistant test product' }, snapshot_id: 'snapshot-1', backend: 'transformer', reviews: [review], insights: { review_count: 1, sentiment_distribution: { positive: 0, neutral: 0, negative: 0 }, aspects: [], top_tags: [] } },
      '/api/demo/products/assistant-fixture/imports': [],
      '/api/demo/products/assistant-fixture/evidence-audit': { snapshot_id: 'snapshot-1', aspects: [] },
      '/api/demo/products/assistant-fixture/quality-queue': { snapshot_id: 'snapshot-1', items: [], summary: { queued_reviews: 0, reason_counts: {} } },
      '/api/demo/products': [],
      '/api/assist/normalize': { canonical_aspect_id: 'performance', canonical_aspect_label: 'Performance', proposed_aspect_label: null, explanation: 'Speed describes system performance.', source: { raw_aspect: 'speed', start_char: 0, end_char: 5 }, applied: false, provider: 'groq', model: 'openai/gpt-oss-20b' },
      '/api/demo/products/assistant-fixture/ask': { status: 'answered', claims: [{ text: 'One reviewer describes excellent speed.', citations: [{ review_id: 'review-1', quote: 'speed is excellent' }] }], snapshot_id: 'snapshot-1', retrieval_review_count: 1, provider: 'groq', model: 'openai/gpt-oss-20b' },
    }
    if (!(path in bodies)) throw new Error(`Unexpected test request: ${path}`)
    await route.fulfill({ json: bodies[path] })
  })
}

test('renders structured unknown suggestions and cited answers without changing saved tags', async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await assistantFixture(page)
  await page.goto('/products/assistant-fixture')
  await page.locator('.optional-assistant > summary').click()
  const assistant = page.getByRole('region', { name: 'Ask about these reviews' })
  await assistant.getByLabel('Your question').fill('What do reviewers say about speed?')
  await assistant.getByRole('button', { name: 'Ask about reviews' }).click()
  await expect(assistant.getByText('One reviewer describes excellent speed.')).toBeVisible()
  await expect(assistant.getByText('Review review-1')).toBeVisible()
  await page.getByRole('link', { name: 'Review evidence', exact: true }).click()
  await page.getByRole('button', { name: 'Show evidence for speed' }).click()
  const drawer = page.getByRole('dialog', { name: 'Aspect evidence' })
  await drawer.getByRole('button', { name: 'Suggest mapping' }).click()
  await expect(drawer.getByText('Suggested mapping:')).toBeVisible()
  await expect(drawer.getByText('Speed describes system performance.')).toBeVisible()
  await expect(drawer.getByText(/Source phrase: “speed” \(0–5\)/)).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByText('No canonical tag', { exact: true })).toBeVisible()
  for (const width of [320, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    await expect.poll(() => page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(width)
    await page.screenshot({ path: testInfo.outputPath(`assistant-${width}.png`), fullPage: true })
  }
  expect(errors).toEqual([])
})

test('assistant stays disabled until server credentials are configured', async ({ page }) => {
  await assistantFixture(page, false)
  await page.goto('/products/assistant-fixture')
  await page.locator('.optional-assistant > summary').click()
  const assistant = page.getByRole('region', { name: 'Ask about these reviews' })
  await expect(assistant.getByRole('button', { name: 'Ask about reviews' })).toBeDisabled()
  await expect(assistant.getByText('Set GROQ_API_KEY on the server to enable Groq.')).toBeVisible()
})
