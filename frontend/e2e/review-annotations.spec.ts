import { expect, test, type APIRequestContext, type Locator } from '@playwright/test'
import { readFile } from 'node:fs/promises'

async function setup(request: APIRequestContext, texts: string[]) {
  const created = await request.post('/api/demo/products', { data: { name: `Annotation flow ${Date.now()}` } })
  expect(created.ok()).toBe(true)
  const product = await created.json()
  const job = await (await request.post(`/api/demo/products/${product.id}/jobs`, { data: { reviews: texts } })).json()
  await expect.poll(async () => (await (await request.get(`/api/demo/jobs/${job.id}`)).json()).status, { timeout: 30_000 }).toBe('completed')
  const before = await (await request.get(`/api/demo/products/${product.id}`)).json()
  return { product, before }
}

async function selectPhrase(textarea: Locator, phrase: string) {
  await textarea.evaluate((element, selected) => {
    const input = element as HTMLTextAreaElement
    input.focus()
    const start = input.value.indexOf(selected)
    if (start < 0) throw new Error('Test phrase is absent')
    input.setSelectionRange(start, start + selected.length)
    document.dispatchEvent(new Event('selectionchange', { bubbles: true }))
  }, phrase)
}

test('adds missed spans, edits boundaries, persists progress and reviews the next item', async ({ page, request }, testInfo) => {
  const text = '😀 Great battery life; wifi is poor.'
  const { product, before } = await setup(request, [text, 'Nothing to report.'])
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  try {
    await page.goto(`/products/${product.id}`)
    const workspace = page.getByRole('region', { name: 'Annotation workspace' })
    await expect(workspace.getByText('0 of 2 reviewed · 2 need review · 0 need adjudication')).toBeVisible()
    await workspace.locator('.annotation-worklist > li').filter({ hasText: text }).getByRole('button', { name: 'Annotate review', exact: true }).click()
    const drawer = page.getByRole('dialog', { name: 'Annotate review' })
    const textarea = drawer.getByLabel('Review text for selection')
    await selectPhrase(textarea, 'wifi')
    await drawer.getByRole('button', { name: 'Add selected phrase' }).click()
    await expect(drawer.getByRole('group', { name: 'Aspect 2: wifi', exact: true })).toBeVisible()
    await drawer.getByLabel('Sentiment for aspect 2').selectOption('negative')
    await drawer.getByLabel('End position for aspect 1').fill('15')
    await expect(drawer.getByRole('group', { name: 'Aspect 1: battery', exact: true })).toBeVisible()
    await drawer.getByLabel('Annotation reviewer').fill('Browser reviewer')
    await drawer.getByLabel('Review notes').fill('Added missing Wi-Fi and tightened the battery span.')
    await drawer.getByRole('button', { name: 'Save draft', exact: true }).click()
    await expect(drawer.getByText('Annotation history (1)')).toBeVisible()
    await page.reload()
    await workspace.locator('.annotation-worklist > li').filter({ hasText: text }).getByRole('button', { name: 'Annotate review', exact: true }).click()
    await expect(drawer.getByLabel('End position for aspect 1')).toHaveValue('15')
    await expect(drawer.getByLabel('Sentiment for aspect 2')).toHaveValue('negative')
    for (const width of [320, 768, 1440]) {
      await page.setViewportSize({ width, height: 1000 })
      await drawer.getByLabel('Annotation reviewer').scrollIntoViewIfNeeded()
      expect(await drawer.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
      expect(await page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(width)
      await expect(drawer.getByRole('button', { name: 'Close dialog' })).toBeVisible()
      await page.screenshot({ path: testInfo.outputPath(`annotation-editor-${width}.png`) })
    }
    await drawer.getByRole('button', { name: 'Mark reviewed & next', exact: true }).click()
    await expect(textarea).toHaveValue('Nothing to report.')
    await expect(drawer.getByRole('button', { name: 'Mark reviewed', exact: true })).toBeDisabled()
    await drawer.getByLabel('Annotation reviewer').fill('Browser reviewer')
    await drawer.getByLabel('Review notes').fill('Need agreement about implicit aspects.')
    await drawer.getByRole('button', { name: 'Needs adjudication', exact: true }).click()
    await expect(drawer.getByText('Annotation history (1)')).toBeVisible()
    await drawer.getByLabel('I checked the full review and found no explicit aspects.').check()
    await drawer.getByLabel('Review notes').fill('Confirmed there are no explicit aspect mentions.')
    await drawer.getByRole('button', { name: 'Mark reviewed & next', exact: true }).click()
    await expect(drawer).not.toBeVisible()
    await expect(workspace.getByText('2 of 2 reviewed · 0 need review · 0 need adjudication')).toBeVisible()
    await workspace.getByRole('combobox', { name: 'Review status', exact: true }).selectOption('reviewed')
    await expect(workspace.getByRole('button', { name: 'Annotate review', exact: true })).toHaveCount(2)
    const downloadPromise = page.waitForEvent('download')
    await workspace.getByRole('button', { name: 'Export annotations' }).click()
    const download = await downloadPromise
    const path = await download.path()
    expect(path).toBeTruthy()
    const exported = JSON.parse(await readFile(path!, 'utf-8'))
    expect(exported.items).toHaveLength(2)
    const labeled = exported.items.find((item: { review_text: string }) => item.review_text === text)
    expect(labeled.mentions[1]).toMatchObject({ raw_aspect: 'wifi', start_char: 22, end_char: 26, sentiment: 'negative', canonical_id: null })
    expect(await (await request.get(`/api/demo/products/${product.id}`)).json()).toEqual(before)
    expect(errors).toEqual([])
  } finally { expect((await request.delete(`/api/demo/products/${product.id}`)).ok()).toBe(true) }
})

test('keeps annotation edits and request identity after a failed save', async ({ page, request }) => {
  const { product, before } = await setup(request, ['😀\r\nwifi is excellent.'])
  const requestIds: string[] = []
  try {
    await page.route(`**/api/demo/products/${product.id}/annotations`, async route => {
      if (route.request().method() !== 'POST') { await route.continue(); return }
      requestIds.push(route.request().postDataJSON().request_id)
      if (requestIds.length === 1) await route.fulfill({ status: 503, json: { detail: 'Temporary annotation save failure.' } })
      else await route.continue()
    })
    await page.goto(`/products/${product.id}`)
    const workspace = page.getByRole('region', { name: 'Annotation workspace' })
    await workspace.getByRole('button', { name: 'Annotate review', exact: true }).click()
    const drawer = page.getByRole('dialog', { name: 'Annotate review' })
    await selectPhrase(drawer.getByLabel('Review text for selection'), 'wifi')
    await drawer.getByRole('button', { name: 'Add selected phrase' }).click()
    await drawer.getByLabel('Sentiment for aspect 1').selectOption('positive')
    await drawer.getByLabel('Annotation reviewer').fill('Reviewer A')
    await drawer.getByLabel('Review notes').fill('Keep this draft through a failed save.')
    await drawer.getByRole('button', { name: 'Save draft', exact: true }).click()
    await expect(drawer.getByText('Temporary annotation save failure.')).toBeVisible()
    await expect(drawer.getByLabel('Review notes')).toHaveValue('Keep this draft through a failed save.')
    await drawer.getByRole('button', { name: 'Save draft', exact: true }).click()
    await expect(drawer.getByText('Annotation history (1)')).toBeVisible()
    expect(requestIds).toHaveLength(2)
    expect(requestIds[1]).toBe(requestIds[0])
    const exported = await (await request.get(`/api/demo/products/${product.id}/annotations/export?snapshot_id=${before.snapshot_id}`)).json()
    expect(exported.items[0].mentions[0]).toMatchObject({ raw_aspect: 'wifi', start_char: 3, end_char: 7 })
  } finally { expect((await request.delete(`/api/demo/products/${product.id}`)).ok()).toBe(true) }
})

test('keeps a conflicting draft until the reviewer explicitly reloads', async ({ page, request }) => {
  const { product, before } = await setup(request, ['Great battery.'])
  try {
    await page.goto(`/products/${product.id}`)
    await page.getByRole('region', { name: 'Annotation workspace' }).getByRole('button', { name: 'Annotate review', exact: true }).click()
    const drawer = page.getByRole('dialog', { name: 'Annotate review' })
    await drawer.getByLabel('Annotation reviewer').fill('Reviewer A')
    await drawer.getByLabel('Review notes').fill('My unsaved annotation.')
    const rid = before.reviews[0].review.review_id
    const draft = await (await request.get(`/api/demo/products/${product.id}/annotations/${rid}?snapshot_id=${before.snapshot_id}`)).json()
    const competing = await request.post(`/api/demo/products/${product.id}/annotations`, { data: {
      snapshot_id: before.snapshot_id, review_id: rid, request_id: crypto.randomUUID(),
      expected_previous_id: draft.latest_id, expected_correction_id: draft.correction_revision,
      status: 'reviewed', reviewer: 'Reviewer B', reason: 'Another reviewer completed this.', mentions: draft.mentions,
    } })
    expect(competing.ok()).toBe(true)
    await drawer.getByRole('button', { name: 'Save draft', exact: true }).click()
    await expect(drawer.getByText('Another annotation was saved. Reload the review before saving your changes.')).toBeVisible()
    await expect(drawer.getByLabel('Review notes')).toHaveValue('My unsaved annotation.')
    await drawer.getByRole('button', { name: 'Reload saved annotation' }).click()
    await expect(drawer.getByLabel('Review notes')).toHaveValue('Another reviewer completed this.')
    await expect(drawer.getByLabel('Annotation reviewer')).toHaveValue('Reviewer B')
  } finally { expect((await request.delete(`/api/demo/products/${product.id}`)).ok()).toBe(true) }
})
