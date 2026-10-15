import { expect, test, type Page } from '@playwright/test'

const productId = '10000000-0000-4000-8000-000000000001'
const snapshotId = '20000000-0000-4000-8000-000000000001'
const reviewId = '30000000-0000-4000-8000-000000000001'

async function fixture(page: Page, failFirstSave = false) {
  const decisions: Record<string, unknown>[] = []
  const requests: Record<string, unknown>[] = []
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/corrections') && route.request().method() === 'POST') {
      const body = route.request().postDataJSON()
      requests.push(body)
      if (failFirstSave && requests.length === 1) {
        await route.fulfill({ status: 503, json: { detail: 'Temporary connection failure. Try saving again.' } }); return
      }
      const decision = { id: `decision-${requests.length}`, ...body, created_at: '2026-10-15T12:00:00Z',
        resolution: body.decision === 'rejected' ? null : { supported: true,
          canonical_id: body.decision === 'accepted' ? 'performance' : body.canonical_id,
          sentiment: body.decision === 'accepted' ? 'positive' : body.sentiment, proposed_aspect_label: null } }
      decisions.unshift(decision)
      await route.fulfill({ status: 201, json: decision }); return
    }
    const review = { review: { review_id: reviewId, review_text: 'speed is excellent' }, backend: 'transformer', tags: [{ raw_aspect: 'speed', normalized_aspect: null, normalized_aspect_id: null, start_char: 0, end_char: 5, sentiment: 'positive', confidence: .93, tag: null }] }
    const bodies: Record<string, unknown> = {
      '/api/assist/status': { enabled: true, provider: 'groq', model: 'test-provider-response', reason: 'Configured' },
      '/api/corrections/options': { ontology_version: 'test-ontology', aspects: [{ id: 'performance', label: 'Performance' }, { id: 'display', label: 'Display' }] },
      [`/api/demo/products/${productId}`]: { product: { id: productId, name: 'Correction fixture' }, snapshot_id: snapshotId, pipeline_version: 'test-pipeline', backend: 'transformer', reviews: [review], insights: { review_count: 1, sentiment_distribution: {}, aspects: [], top_tags: [] } },
      [`/api/demo/products/${productId}/imports`]: [],
      [`/api/demo/products/${productId}/evidence-audit`]: { snapshot_id: snapshotId, aspects: [] },
      [`/api/demo/products/${productId}/quality-queue`]: { snapshot_id: snapshotId, items: [], summary: { queued_reviews: 0, reason_counts: {} } },
      [`/api/demo/products/${productId}/corrections/history`]: { snapshot_id: snapshotId, items: decisions, latest_id: decisions[0]?.id ?? null },
      [`/api/demo/products/${productId}/corrections/suggest`]: { id: '40000000-0000-4000-8000-000000000001', canonical_aspect_id: 'performance', canonical_aspect_label: 'Performance', proposed_aspect_label: null, explanation: 'Speed describes system performance.', source: { raw_aspect: 'speed', start_char: 0, end_char: 5 }, applied: false, provider: 'groq', model: 'test-provider-response' },
      [`/api/demo/products/${productId}/corrections`]: { items: decisions },
      [`/api/demo/products/${productId}/annotations`]: { snapshot_id: snapshotId, items: [], summary: { total: 0, reviewed: 0, needs_review: 0, needs_adjudication: 0 } },
      '/api/demo/products': [],
    }
    if (!(path in bodies)) throw new Error(`Unexpected correction fixture request: ${path}`)
    await route.fulfill({ json: bodies[path] })
  })
  return { decisions, requests }
}

test('accepts, edits and rejects with persistent history and export', async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const { requests } = await fixture(page)
  await page.goto(`/products/${productId}`)
  await page.getByRole('button', { name: 'Show evidence for speed' }).click()
  const drawer = page.getByRole('dialog', { name: 'Aspect evidence' })
  await drawer.getByRole('button', { name: 'Suggest mapping' }).click()
  await expect(drawer.getByText('Speed describes system performance.')).toBeVisible()
  await drawer.getByLabel('Reviewer name').fill('Reviewer A')
  await drawer.getByLabel('Reason for this decision').fill('Speed means responsiveness here.')
  await drawer.getByRole('button', { name: 'Accept suggestion' }).click()
  await expect(drawer.getByText('Accepted suggestion', { exact: true })).toBeVisible()
  expect(requests[0].decision).toBe('accepted')
  expect(requests[0]).not.toHaveProperty('sentiment')

  await drawer.getByLabel('Correct aspect').selectOption('display')
  await drawer.getByLabel('Correct sentiment').selectOption('negative')
  await drawer.getByLabel('Reason for this decision').fill('Testing an edited decision.')
  await drawer.getByRole('button', { name: 'Save correction', exact: true }).click()
  await expect(drawer.getByText('Testing an edited decision.')).toBeVisible()
  expect(requests[1]).toMatchObject({ decision: 'edited', canonical_id: 'display', sentiment: 'negative', expected_previous_id: 'decision-1' })

  await drawer.getByLabel('Reason for this decision').fill('Rejecting the suggestion after further review.')
  await drawer.getByRole('button', { name: 'Reject suggestion' }).click()
  await expect(drawer.getByText('Rejected suggestion', { exact: true })).toBeVisible()
  for (const width of [320, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await drawer.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    await drawer.getByLabel('Reviewer name').scrollIntoViewIfNeeded()
    await expect(drawer.getByRole('button', { name: 'Close dialog' })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath(`correction-drawer-${width}.png`) })
  }
  await page.keyboard.press('Escape')
  await expect(page.getByText('No canonical tag', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Show evidence for speed' }).click()
  await expect(drawer.getByText('Accepted suggestion', { exact: true })).toBeVisible()
  await expect(drawer.getByText('Rejected suggestion', { exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export review decisions' }).click()
  expect((await download).suggestedFilename()).toContain('review-decisions-')
  expect(errors).toEqual([])
})

test('keeps input and request identity when saving fails', async ({ page }) => {
  const { requests } = await fixture(page, true)
  await page.goto(`/products/${productId}`)
  await page.getByRole('button', { name: 'Show evidence for speed' }).click()
  const drawer = page.getByRole('dialog', { name: 'Aspect evidence' })
  await drawer.getByLabel('Reviewer name').fill('Reviewer A')
  await drawer.getByLabel('Reason for this decision').fill('Keep this reason through retries.')
  await drawer.getByRole('button', { name: 'Save correction', exact: true }).click()
  await expect(drawer.getByText('Temporary connection failure. Try saving again.')).toBeVisible()
  await expect(drawer.getByLabel('Reason for this decision')).toHaveValue('Keep this reason through retries.')
  await drawer.getByRole('button', { name: 'Save correction', exact: true }).click()
  await expect(drawer.getByText('Correction', { exact: true })).toBeVisible()
  expect(requests[1].request_id).toBe(requests[0].request_id)
})

test('saves a real sentiment correction through the API and reloads it', async ({ page, request }) => {
  const created = await request.post('/api/demo/products', { data: { name: `Correction flow ${Date.now()}` } })
  expect(created.ok()).toBe(true)
  const product = await created.json()
  try {
    const saved = await request.post(`/api/demo/products/${product.id}/jobs`, { data: { reviews: ['Great battery.'] } })
    const job = await saved.json()
    await expect.poll(async () => (await (await request.get(`/api/demo/jobs/${job.id}`)).json()).status, { timeout: 30_000 }).toBe('completed')
    const before = await (await request.get(`/api/demo/products/${product.id}`)).json()
    await page.goto(`/products/${product.id}`)
    await page.getByRole('button', { name: 'Show evidence for battery' }).click()
    const drawer = page.getByRole('dialog', { name: 'Aspect evidence' })
    await drawer.getByLabel('Reviewer name').fill('Browser reviewer')
    await drawer.getByLabel('Correct sentiment').selectOption('negative')
    await drawer.getByLabel('Reason for this decision').fill('Synthetic correction persistence check.')
    await drawer.getByRole('button', { name: 'Save correction', exact: true }).click()
    await expect(drawer.getByText('Synthetic correction persistence check.')).toBeVisible()
    await page.reload()
    await page.getByRole('button', { name: 'Show evidence for battery' }).click()
    await expect(drawer.getByText('Synthetic correction persistence check.')).toBeVisible()
    const after = await (await request.get(`/api/demo/products/${product.id}`)).json()
    expect(after).toEqual(before)
    const exported = await (await request.get(`/api/demo/products/${product.id}/corrections`)).json()
    expect(exported.items[0].resolution.sentiment).toBe('negative')
    expect(exported.items[0].original.sentiment).toBe('positive')
  } finally {
    expect((await request.delete(`/api/demo/products/${product.id}`)).ok()).toBe(true)
  }
})
