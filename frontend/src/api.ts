export type Tag = { normalized_aspect: string | null; normalized_aspect_id?: string | null; normalization_method?: string; normalization_similarity?: number | null; raw_aspect: string; start_char?: number; end_char?: number; context_start_char?: number; context_end_char?: number; aspect_confidence?: number; sentiment_confidence?: number; probabilities?: Record<string, number>; tag: string | null; sentiment: 'positive' | 'neutral' | 'negative'; confidence: number }
export type Analysis = { review: { review_id: string; review_text: string }; tags: Tag[]; backend: string; context_policy?: string }
export type Product = { id: string; name: string; review_count: number }
export type Detail = {
  product: Product; reviews: Analysis[]; backend: string; stale?: boolean; pipeline_version?: string; requested_pipeline_version?: string; snapshot_id?: string | null; data_revision?: number
  insights: { review_count: number; sentiment_distribution: Record<string, number>; aspects: { aspect_id: string; aspect: string; review_count: number; classification: string; counts?: Record<string, number>; ratios?: Record<string, number>; average_confidence?: number; aggregate_tag?: string | null }[]; top_tags: { aggregate_tag: string | null; aspect_id: string; aspect: string }[]; representative_reviews?: { aspect?: string; aspect_id?: string; sentiment: string; review_id: string; review_text: string; tag?: string | null; confidence?: number }[] }
}
export type PreviewResult = { analyses: Analysis[]; preview_ids?: string[] }
export type PreviewPoll = { id: string; status: 'queued' | 'running' | 'completed' | 'failed'; analysis?: Analysis; error_summary?: string }
export type Job = { id: string; status: string; stage?: string; total_rows: number; accepted_rows?: number; rejected_rows?: number; completed_rows: number; failed_rows: number; duplicate_rows: number; errors?: { row?: string; error?: string; message?: string; status?: string }[]; error_summary?: string }
export type ImportValidation = { reviews: string[]; errors: { row: number; error: string }[]; total_rows: number }
export type MetricRecord = { task_id?: string; protocol?: string; pipeline_version?: string | null; metrics?: Record<string, number>; [key: string]: unknown }
export type ModelMetrics = { historical?: MetricRecord[]; current?: MetricRecord[]; records?: Record<string, unknown>; human_gate?: string; human_normalization_gate?: string; [key: string]: unknown }
export async function api<T>(path: string, body?: unknown, idempotencyKey?: string): Promise<T> {
  const response = await fetch(`/api${path}`, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}) }, body: JSON.stringify(body),
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    const message = typeof data.detail === 'string' ? data.detail : typeof data.error?.message === 'string' ? data.error.message : `Request failed (${response.status}). Check your input and try again.`
    throw new Error(message)
  }
  return response.json()
}
