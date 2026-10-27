export type CapturedReviews = {
  title: string
  url: string
  method: 'selection' | 'amazon-loaded' | 'paste'
  reviews: string[]
  skipped: number
  limited: boolean
}

type Tab = { id?: number; url?: string }
type ChromeApi = {
  storage: { local: { get(keys: string[]): Promise<Record<string, unknown>>; set(values: Record<string, unknown>): Promise<void>; remove(keys: string[]): Promise<void> } }
  tabs: {
    query(query: { active: boolean; currentWindow: boolean }): Promise<Tab[]>
    create(input: { url: string }): Promise<unknown>
    onActivated: { addListener(callback: (info: { tabId: number }) => void): void; removeListener(callback: (info: { tabId: number }) => void): void }
    onUpdated: { addListener(callback: (tabId: number, change: { url?: string; status?: string }) => void): void; removeListener(callback: (tabId: number, change: { url?: string; status?: string }) => void): void }
  }
  scripting: { executeScript<T>(input: { target: { tabId: number }; func: () => T }): Promise<{ result?: T }[]> }
}

export function chromeApi(): ChromeApi | undefined {
  const value = (globalThis as typeof globalThis & { chrome?: ChromeApi }).chrome
  return value?.storage?.local && value?.scripting ? value : undefined
}

// This function is serialized into the tab. Keep it self-contained and read-only.
export function capturePage(): CapturedReviews {
  const selected = window.getSelection()?.toString() ?? ''
  const title = document.querySelector('#productTitle')?.textContent?.trim() || document.title.trim()
  const base = { title: title.slice(0, 120), url: location.href, skipped: 0, limited: false }
  if (selected.trim()) {
    if (Array.from(selected).length > 10000) throw new Error('Select a review of at most 10,000 characters.')
    return { ...base, method: 'selection', reviews: [selected] }
  }
  if (!/(^|\.)amazon\.(com|in)$/i.test(location.hostname)) throw new Error('Select a complete review before capturing, or paste reviews below. Automatic capture is experimental on Amazon.com and Amazon.in only.')
  const reviews: string[] = []
  const seen = new Set<string>()
  let skipped = 0
  const blocks = [...document.querySelectorAll<HTMLElement>('[data-hook="review"]')]
  for (const block of blocks) {
    const body = block.querySelector<HTMLElement>('[data-hook="review-body"]')
    if (!body || !body.getClientRects().length) continue
    // Clipped/expandable bodies cannot establish complete-review coverage.
    const expander = body.closest<HTMLElement>('.a-expander-content')
    const collapsed = expander && expander.classList.contains('a-expander-partial-collapse-content')
    const clipped = body.clientHeight > 0 && body.scrollHeight > body.clientHeight + 2
    const text = body.innerText.trim()
    if (!text || collapsed || clipped || Array.from(text).length > 10000) { skipped++; continue }
    const key = text.replace(/\s+/g, ' ').toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    reviews.push(text)
    if (reviews.length === 20) return { ...base, method: 'amazon-loaded', reviews, skipped, limited: true }
  }
  if (!reviews.length) throw new Error('No complete loaded reviews could be captured. Expand the review text, select a full review, or use paste below.')
  return { ...base, method: 'amazon-loaded', reviews, skipped }
}

export function parsePastedReviews(text: string): string[] {
  const reviews = text.split(/\r?\n\s*\r?\n/).filter(value => value.trim())
  if (!reviews.length || reviews.length > 20) throw new Error('Paste 1–20 reviews, separated by a blank line.')
  if (reviews.some(value => Array.from(value).length > 10000)) throw new Error('Each review must contain at most 10,000 characters.')
  return reviews
}
