import { afterEach, describe, expect, it, vi } from 'vitest'
import { capturePage, parsePastedReviews } from './browser'
import { validConnection } from './api'

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
    expect(parsePastedReviews('First review.\nSecond sentence.\n\nAnother review.')).toEqual(['First review.\nSecond sentence.', 'Another review.'])
    expect(() => parsePastedReviews(Array(21).fill('Review').join('\n\n'))).toThrow(/1–20/)
    expect(() => parsePastedReviews('x'.repeat(10001))).toThrow(/10,000/)
    expect(() => parsePastedReviews('  ')).toThrow(/1–20/)
    expect(parsePastedReviews('😀'.repeat(10000))).toHaveLength(1)
  })
})

it('restricts connection settings to valid loopback-service ports', () => {
  expect(validConnection({ apiPort: 8000, webPort: 5173 })).toBe(true)
  for (const port of [0, -1, 65536, Infinity, NaN, 80.5, '8000']) expect(validConnection({ apiPort: port, webPort: 5173 })).toBe(false)
})
