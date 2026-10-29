export type CapturedReviews = {
  title: string
  url: string
  method: 'selection' | 'amazon-loaded' | 'retailer-loaded' | 'paste'
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
  const adapters = [
    { host: /(^|\.)amazon\.(com|in)$/, selectors: ['[data-hook="review"] [data-hook="review-body"]'], amazon: true },
    { host: /(^|\.)flipkart\.com$/, selectors: ['.ZmyHeo', '.t-ZTKy', '[data-testid="review-body"]'] },
    { host: /(^|\.)walmart\.com$/, selectors: ['[data-testid="review-text"]', '[itemprop="reviewBody"]'] },
    { host: /(^|\.)bestbuy\.com$/, selectors: ['.review-body', '[data-testid="review-body"]'] },
    { host: /(^|\.)target\.com$/, selectors: ['[data-test="review-content"]', '[itemprop="reviewBody"]'] },
  ]
  const adapter = adapters.find(candidate => candidate.host.test(location.hostname.toLowerCase()))
  if (!adapter) throw new Error('Select a complete review before capturing, or paste reviews below. Automatic capture is experimental on Amazon.com / .in, Flipkart, Walmart, Best Buy, and Target.')
  const method = adapter.amazon ? 'amazon-loaded' as const : 'retailer-loaded' as const
  // Prefer one known layout to avoid overlapping wrapper/body selectors.
  const selector = [...adapter.selectors, '[itemprop="reviewBody"]'].find(value => document.querySelector(value))
  const bodies = selector ? [...document.querySelectorAll<HTMLElement>(selector)] : []
  const reviews: string[] = []
  const seen = new Set<string>()
  let skipped = 0
  for (const body of bodies) {
    if (!body.getClientRects().length || body.closest('[hidden], [aria-hidden="true"]')) continue
    // Clipped/expandable bodies cannot establish complete-review coverage.
    const expander = body.closest<HTMLElement>('.a-expander-content')
    const collapsed = !!expander?.classList.contains('a-expander-partial-collapse-content') || !!body.querySelector('[aria-expanded="false"]')
    let clipped = false
    // Retailers may clamp a wrapper rather than the text element.
    for (let node: HTMLElement | null = body, depth = 0; node && depth < 3; node = node.parentElement, depth++) {
      const style = getComputedStyle(node)
      if (node.clientHeight > 0 && node.scrollHeight > node.clientHeight + 2 && (node === body || ['hidden', 'clip'].includes(style.overflowY))) clipped = true
    }
    const text = body.innerText.trim()
    if (!text || collapsed || clipped || /(?:read|show)\s+more\s*$/i.test(text) || Array.from(text).length > 10000) { skipped++; continue }
    const key = text.replace(/\s+/g, ' ').toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    reviews.push(text)
    if (reviews.length === 100) return { ...base, method, reviews, skipped, limited: true }
  }
  if (!reviews.length) throw new Error('No complete loaded reviews could be captured. Expand the review text, select a full review, or use paste below.')
  return { ...base, method, reviews, skipped }
}

export function parsePastedReviews(text: string): string[] {
  const reviews = text.split(/\r?\n\s*\r?\n/).filter(value => value.trim())
  if (!reviews.length || reviews.length > 100) throw new Error('Paste 1–100 reviews, separated by a blank line.')
  if (reviews.some(value => Array.from(value).length > 10000)) throw new Error('Each review must contain at most 10,000 characters.')
  return reviews
}
