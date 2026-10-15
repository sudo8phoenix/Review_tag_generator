import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Analysis, type Tag } from '../api'
import { UnknownAspectAssist, type NormalizationResult, type SavedAspectContext } from './ReviewAssistant'
import './AspectCorrectionPanel.css'

type Resolution = { supported: boolean; canonical_id: string | null; proposed_aspect_label: string | null; sentiment: string | null }
type Decision = { id: string; decision: 'accepted' | 'edited' | 'rejected'; reviewer: string; reason: string; created_at: string; resolution: Resolution | null }
type History = { items: Decision[]; latest_id: string | null; snapshot_id: string }
type Options = { ontology_version: string; aspects: { id: string; label: string }[] }

export function AspectCorrectionPanel({ review, tag, savedContext }: { review: Analysis; tag: Tag; savedContext: SavedAspectContext }) {
  const client = useQueryClient()
  const [suggestion, setSuggestion] = useState<NormalizationResult | null>(null)
  const [mapping, setMapping] = useState(tag.normalized_aspect_id ?? '')
  const [sentiment, setSentiment] = useState(tag.sentiment)
  const [supported, setSupported] = useState(true)
  const [reviewer, setReviewer] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const retry = useRef<{ body: string; id: string } | null>(null)
  const reference = { snapshot_id: savedContext.snapshotId, review_id: review.review.review_id, start_char: tag.start_char, end_char: tag.end_char }
  const query = new URLSearchParams(Object.entries(reference).map(([key, value]) => [key, String(value)]))
  const historyKey = ['correction-history', savedContext.productId, savedContext.snapshotId, review.review.review_id, tag.start_char, tag.end_char]
  const history = useQuery({ queryKey: historyKey, queryFn: () => api<History>(`/demo/products/${savedContext.productId}/corrections/history?${query}`) })
  const options = useQuery({ queryKey: ['correction-options'], queryFn: () => api<Options>('/corrections/options'), staleTime: 60_000 })
  const mismatch = history.data && history.data.snapshot_id !== savedContext.snapshotId
  const ready = !!history.data && !history.isFetching && !history.error && !!options.data && !mismatch
  const canSave = ready && !busy && !!reviewer.trim() && !!reason.trim()

  function receiveSuggestion(result: NormalizationResult) {
    setSuggestion(result)
    if (result.canonical_aspect_id) setMapping(result.canonical_aspect_id)
    setMessage('')
  }

  async function save(decision: Decision['decision']) {
    if (!canSave) return
    const body = {
      ...reference, decision, reviewer: reviewer.trim(), reason: reason.trim(),
      expected_previous_id: history.data?.latest_id ?? null,
      suggestion_id: suggestion?.id ?? null,
      ...(decision === 'edited' ? { supported, canonical_id: supported ? mapping || null : null, sentiment: supported ? sentiment : null } : {}),
    }
    const serialized = JSON.stringify(body)
    if (retry.current?.body !== serialized) retry.current = { body: serialized, id: crypto.randomUUID() }
    setBusy(true); setError(''); setMessage('')
    try {
      await api(`/demo/products/${savedContext.productId}/corrections`, { ...body, request_id: retry.current.id })
      setMessage(decision === 'rejected' ? 'Rejection recorded. Original predictions remain visible.' : 'Review decision saved. Original predictions and product totals remain unchanged.')
      setReason('')
      retry.current = null
      await client.invalidateQueries({ queryKey: historyKey })
      await client.invalidateQueries({ queryKey: ['annotation-worklist', savedContext.productId] })
      await client.invalidateQueries({ queryKey: ['review-annotation', savedContext.productId] })
    } catch (failure) {
      setError((failure as Error).message || 'Could not save the decision. Your input has been kept.')
    } finally { setBusy(false) }
  }

  return <section className="aspect-correction" aria-labelledby="aspect-correction-title">
    <h3 id="aspect-correction-title">Review this prediction</h3>
    <p className="field-hint">Record a mapping or sentiment correction alongside the original analysis.</p>
    {tag.normalized_aspect === null && <UnknownAspectAssist review={review} tag={tag} savedContext={savedContext} onSuggestion={receiveSuggestion} />}
    {history.isPending && <p role="status">Loading review history…</p>}
    {history.error && <div role="alert"><p>{history.error.message}</p><button type="button" className="button button-secondary" onClick={() => void history.refetch()}>Reload decision history</button></div>}
    {mismatch && <p role="alert">This history belongs to a different snapshot. Reload the product.</p>}
    {options.error && <div role="alert"><p>Could not load aspect choices.</p><button type="button" className="button button-secondary" onClick={() => void options.refetch()}>Retry aspect choices</button></div>}
    <form onSubmit={event => { event.preventDefault(); void save('edited') }}>
      <fieldset disabled={busy || !ready}>
        <legend>Your decision</legend>
        <label>Reviewer name<input value={reviewer} onChange={event => setReviewer(event.target.value)} required maxLength={120} autoComplete="name" /></label>
        <p className="field-hint">Reviewer names are self-reported in this local demo.</p>
        <label className="aspect-correction__check"><input type="checkbox" checked={!supported} onChange={event => setSupported(!event.target.checked)} />This phrase is not a supported aspect</label>
        <label>Correct aspect<select value={mapping} onChange={event => setMapping(event.target.value)} disabled={!supported}>
          <option value="">Unknown / outside the current categories</option>
          {options.data?.aspects.map(aspect => <option key={aspect.id} value={aspect.id}>{aspect.label}</option>)}
        </select></label>
        <label>Correct sentiment<select value={sentiment} onChange={event => setSentiment(event.target.value as Tag['sentiment'])} disabled={!supported}>
          <option value="positive">Positive</option><option value="neutral">Neutral</option><option value="negative">Negative</option>
        </select></label>
        <label>Reason for this decision<textarea value={reason} onChange={event => setReason(event.target.value)} required maxLength={2000} rows={3} /></label>
        <div className="aspect-correction__actions">
          <button className="button button-primary" type="submit" disabled={!canSave}>Save correction</button>
          {suggestion?.id && <>
            <button className="button button-secondary" type="button" disabled={!canSave || (!suggestion.canonical_aspect_id && !suggestion.proposed_aspect_label)} onClick={() => void save('accepted')}>Accept suggestion</button>
            <button className="button button-quiet" type="button" disabled={!canSave} onClick={() => void save('rejected')}>Reject suggestion</button>
          </>}
        </div>
        {suggestion?.id && <p className="field-hint">Accept keeps the original sentiment and the exact suggested mapping. Use Save correction to record your edits.</p>}
      </fieldset>
    </form>
    {busy && <p role="status">Saving review decision…</p>}
    {message && <p className="alert alert-success" role="status">{message}</p>}
    {error && <div role="alert"><p>{error}</p><button className="button button-secondary" type="button" disabled={busy} onClick={() => void history.refetch()}>Reload decision history</button></div>}
    <div className="aspect-correction__history">
      <h4>Decision history</h4>
      {history.data?.items.length === 0 && <p className="field-hint">No decisions recorded for this prediction.</p>}
      <ol>{history.data?.items.map(item => <li key={item.id}>
        <strong>{item.decision === 'edited' ? 'Correction' : item.decision === 'accepted' ? 'Accepted suggestion' : 'Rejected suggestion'}</strong>
        <span>{item.reviewer} · {new Date(item.created_at).toLocaleString()}</span>
        {item.resolution && <p>{!item.resolution.supported ? 'Not a supported aspect' : `${options.data?.aspects.find(aspect => aspect.id === item.resolution?.canonical_id)?.label ?? item.resolution.proposed_aspect_label ?? 'Unknown'} · ${item.resolution.sentiment}${item.resolution.proposed_aspect_label ? ' · proposed category' : ''}`}</p>}
        <p>{item.reason}</p>
      </li>)}</ol>
    </div>
  </section>
}

export function CorrectionExport({ productId }: { productId: string }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function download() {
    setBusy(true); setError('')
    try {
      const data = await api(`/demo/products/${productId}/corrections`)
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
      const link = document.createElement('a'); link.href = url; link.download = `review-decisions-${productId}.json`; link.click(); URL.revokeObjectURL(url)
    } catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }
  return <div><button type="button" className="button button-secondary" disabled={busy} onClick={() => void download()}>{busy ? 'Exporting…' : 'Export review decisions'}</button>{error && <p className="field-error" role="alert">{error}</p>}</div>
}
