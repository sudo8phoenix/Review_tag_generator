export type Tag = { normalized_aspect: string | null; raw_aspect: string; tag: string | null; sentiment: 'positive' | 'neutral' | 'negative'; confidence: number }
export type Analysis = { review: { review_id: string; review_text: string }; tags: Tag[]; backend: string }
export type Product = { id: string; name: string; review_count: number }
export type Detail = {
  product: Product; reviews: Analysis[]; backend: string
  insights: { review_count: number; sentiment_distribution: Record<string, number>; aspects: { aspect_id: string; aspect: string; review_count: number; classification: string }[]; top_tags: { aggregate_tag: string | null; aspect_id: string; aspect: string }[] }
}
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status}). Check your input and try again.`)
  }
  return response.json()
}
