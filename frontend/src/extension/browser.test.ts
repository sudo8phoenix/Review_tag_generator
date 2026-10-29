import { afterEach, describe, expect, it, vi } from 'vitest'
import { capturePage, parsePastedReviews } from './browser'
import { getApiBaseUrl, getWebUrl, localRequest, validConnection } from './api'

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); document.body.innerHTML = '' })

describe('review capture boundaries', () => {
  it('preserves selected Unicode text and never reads unrelated page text', () => {
    const text = '😀 The battery lasts all day.\nA complete review.'
    vi.spyOn(window, 'getSelection').mockReturnValue({ toString: () => text } as Selection)
    document.body.textContent = 'Unrelated page content'
    expect(capturePage()).toMatchObject({ method: 'selection', reviews: [text] })
  })

  it('captures only complete rendered Amazon bodies and deduplicates them', () => {
    vi.stubGlobal('location', new URL('https://www.amazon.in/dp/B000000001'))
    vi.spyOn(window, 'getSelection').mockReturnValue(null)
    vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{}] as unknown as DOMRectList)
    document.body.innerHTML = '<span id="productTitle">Sample laptop</span><div data-hook="review"><span data-hook="review-body" id="first"></span></div><div data-hook="review"><span data-hook="review-body" id="duplicate"></span></div><div data-hook="review"><div class="a-expander-content a-expander-partial-collapse-content"><span data-hook="review-body" id="partial"></span></div></div>'
    for (const id of ['first', 'duplicate', 'partial']) Object.defineProperty(document.getElementById(id), 'innerText', { value: id === 'partial' ? 'Truncated text' : 'Great display.' })
    expect(capturePage()).toMatchObject({ title: 'Sample laptop', method: 'amazon-loaded', reviews: ['Great display.'], skipped: 1 })
  })

  it('does not accept an Amazon-looking unrelated host for automatic capture', () => {
    vi.stubGlobal('location', new URL('https://amazon.com.attacker.example/product'))
    vi.spyOn(window, 'getSelection').mockReturnValue(null)
    expect(() => capturePage()).toThrow(/Select a complete review/)
  })

  it('bounds pasted batches and preserves line breaks inside each review', () => {
    expect(parsePastedReviews(Array(100).fill('Review').join('\n\n'))).toHaveLength(100)
    expect(parsePastedReviews('First review.\nSecond sentence.\n\nAnother review.')).toEqual(['First review.\nSecond sentence.', 'Another review.'])
    expect(() => parsePastedReviews(Array(101).fill('Review').join('\n\n'))).toThrow(/1–100/)
    expect(() => parsePastedReviews('x'.repeat(10001))).toThrow(/10,000/)
    expect(() => parsePastedReviews('  ')).toThrow(/1–100/)
    expect(parsePastedReviews('😀'.repeat(10000))).toHaveLength(1)
  })

  it('skips incomplete and duplicate Flipkart reviews', () => {
    vi.stubGlobal('location', new URL('https://www.flipkart.com/product-reviews/sample'))
    vi.spyOn(window, 'getSelection').mockReturnValue(null)
    vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{}] as unknown as DOMRectList)
    const texts = ['Great display.', ' Great   display. ', 'Truncated read more', 'x'.repeat(10001), 'Hidden review']
    document.body.innerHTML = texts.map((_, i) => `<div class="ZmyHeo" ${i === 4 ? 'hidden' : ''}></div>`).join('')
    document.querySelectorAll('.ZmyHeo').forEach((node, i) => Object.defineProperty(node, 'innerText', { value: texts[i] }))
    expect(capturePage()).toMatchObject({ method: 'retailer-loaded', reviews: ['Great display.'], skipped: 2 })
  })
})

it('restricts connection settings to valid loopback-service ports', () => {
  expect(validConnection({ apiPort: 8000, webPort: 5173 })).toBe(true)
  for (const port of [0, -1, 65536, Infinity, NaN, 80.5, '8000']) expect(validConnection({ apiPort: port, webPort: 5173 })).toBe(false)
})

it('supports Vercel and remote base URL connections', () => {
  expect(validConnection({ mode: 'vercel', baseUrl: 'https://review-tag-generator.vercel.app' })).toBe(true)
  expect(validConnection({ mode: 'vercel', baseUrl: 'not-a-url' })).toBe(false)
  expect(validConnection({ mode: 'vercel', baseUrl: 'ftp://bad' })).toBe(false)
  expect(getApiBaseUrl({ mode: 'vercel', baseUrl: 'https://review-tag-generator.vercel.app/' })).toBe('https://review-tag-generator.vercel.app')
  expect(getWebUrl({ mode: 'vercel', baseUrl: 'https://review-tag-generator.vercel.app' })).toBe('https://review-tag-generator.vercel.app')
  expect(getApiBaseUrl({ mode: 'local', apiPort: 8080 })).toBe('http://127.0.0.1:8080')
  expect(getWebUrl({ mode: 'local', webPort: 3000 })).toBe('http://127.0.0.1:3000')
})


it('rejects hosted addresses outside the extension connection policy', () => {
  for (const baseUrl of [
    'https://example.com', 'http://review-tag-generator.vercel.app',
    'https://user:password@review-tag-generator.vercel.app',
    'https://review-tag-generator.vercel.app/not-an-origin',
    'https://review-tag-generator.vercel.app?redirect=elsewhere',
  ]) expect(validConnection({ mode: 'vercel', baseUrl })).toBe(false)
  expect(validConnection({ mode: 'vercel', baseUrl: 'https://review-tag-generator-api.onrender.com' })).toBe(true)
})


it('reports an HTML wake-up or misrouted API page instead of treating it as product data', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>Starting service</html>', { headers: { 'Content-Type': 'text/html' } })))
  await expect(localRequest({ mode: 'vercel', baseUrl: 'https://review-tag-generator.vercel.app' }, '/api/demo/products')).rejects.toThrow('API is not ready')
})
