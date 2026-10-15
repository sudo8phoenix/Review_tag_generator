import { useEffect, useState } from 'react'
import './ReviewQualityPanel.css'

type Reason = { code: string; label: string }
type Aspect = {
  raw_aspect?: string
  normalized_aspect?: string | null
  normalized_aspect_id?: string | null
  sentiment?: string
  confidence?: number
  probabilities?: Record<string, number>
  start_char?: number
  end_char?: number
}
type QueueItem = {
  review_id: string
  review_text: string
  backend?: string | null
  context_policy?: string | null
  reasons: Reason[]
  minimum_confidence?: number | null
  confidence_threshold: number
  aspects: Aspect[]
}
type QualityQueueResponse = {
  items: QueueItem[]
  summary: { queued_reviews: number; reason_counts: Record<string, number>; confidence_threshold: number }
  snapshot_id: string | null
  stale: boolean
  disclaimer: string
}

type Props = { productId: string; snapshotId: string | null; onReview?: (reviewId: string, start: number, end: number) => void }

const reasonNames: Record<string, string> = {
  unknown_aspect: 'Unknown aspect',
  low_confidence: 'Low confidence',
  no_aspects: 'No aspects returned',
  contradictory_sentiment: 'Mixed sentiment',
}

export function ReviewQualityPanel({ productId, snapshotId, onReview }: Props) {
  const [data, setData] = useState<QualityQueueResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [requestVersion, setRequestVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    fetch(`/api/demo/products/${encodeURIComponent(productId)}/quality-queue`, { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(`Could not load the review queue (${response.status}).`)
        return response.json() as Promise<QualityQueueResponse>
      })
      .then(result => setData(result))
      .catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Could not load the review queue.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [productId, snapshotId, requestVersion])

  const snapshotMismatch = !!data && data.snapshot_id !== snapshotId

  const exportQueue = () => {
    if (!data || loading || error || snapshotMismatch) return
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `review-quality-${productId}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="review-quality" aria-labelledby="review-quality-title">
      <header className="rq-header">
        <div>
          <p className="rq-eyebrow">Human review assistance</p>
          <h2 id="review-quality-title">Review quality queue</h2>
          <p className="rq-intro">A short list of saved reviews with signals that may benefit from a closer look.</p>
        </div>
        <button className="rq-export" type="button" onClick={exportQueue} disabled={loading || !!error || !data || snapshotMismatch || data.items.length === 0}>
          Export JSON
        </button>
      </header>

      {loading && <p className="rq-state" role="status">Loading review suggestions…</p>}
      {error && <p className="rq-error" role="alert">{error}</p>}
      {!loading && !error && data && <>
        {snapshotMismatch && <div className="rq-stale" role="status"><p>The product snapshot changed while this queue was loading. Reload the product view before using these suggestions.</p><button type="button" onClick={() => window.location.reload()}>Reload product</button></div>}
        {!snapshotMismatch && data.stale && <p className="rq-stale" role="status">Some saved analyses may still be processing. This queue covers the currently available snapshot.</p>}
        {!snapshotMismatch && <>
        <div className="rq-summary" aria-label="Review signal counts">
          <div className="rq-total"><strong>{data.summary.queued_reviews}</strong><span>reviews suggested</span></div>
          {Object.entries(data.summary.reason_counts).filter(([, count]) => count > 0).map(([code, count]) => (
            <div className="rq-count" key={code}><strong>{count}</strong><span>{reasonNames[code] ?? code.replaceAll('_', ' ')}</span></div>
          ))}
        </div>
        {data.items.length === 0 ? <p className="rq-empty">No review signals met the current queue rules for this snapshot.</p> :
          <ol className="rq-list">{data.items.map(item => <li key={item.review_id} className="rq-item">
            <div className="rq-item-heading"><span className="rq-id">{item.review_id}</span><div className="rq-reasons">{item.reasons.map(reason => <span className="rq-reason" key={reason.code}>{reasonNames[reason.code] ?? reason.label}</span>)}</div></div>
            <blockquote>{item.review_text}</blockquote>
            <div className="rq-aspects" aria-label="Saved aspect predictions">
              {item.aspects.map((aspect, index) => <span className="rq-aspect" key={`${aspect.start_char ?? 'x'}-${aspect.end_char ?? 'x'}-${index}`}>
                {onReview && aspect.start_char !== undefined && aspect.end_char !== undefined
                  ? <button type="button" className="evidence-link" aria-label={`Review ${aspect.raw_aspect ?? 'aspect'} prediction`} onClick={() => onReview(item.review_id, aspect.start_char!, aspect.end_char!)}>{aspect.raw_aspect ?? 'Aspect'}</button>
                  : <strong>{aspect.raw_aspect ?? 'Aspect'}</strong>}{' '}{aspect.normalized_aspect ?? 'Unmapped'} · {aspect.sentiment ?? 'sentiment not reported'}{typeof aspect.confidence === 'number' ? ` · ${(aspect.confidence * 100).toFixed(0)}% score` : ''}
              </span>)}
            </div>
            <p className="rq-provenance">{item.backend ?? 'Backend not reported'}{item.context_policy ? ` · ${item.context_policy} context` : ''}{item.minimum_confidence != null ? ` · minimum score ${(item.minimum_confidence * 100).toFixed(1)}%` : ''}</p>
          </li>)}</ol>}
        <p className="rq-disclaimer">{data.disclaimer || 'Suggestions only. This queue does not provide gold corrections, accuracy estimates, or retraining data.'}</p>
        </>}
      </>}
      {error && <button className="rq-retry" type="button" onClick={() => setRequestVersion(value => value + 1)}>Try again</button>}
    </section>
  )
}
