import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Tag } from '../api'
import { Dialog } from './Dialog'
import { sourceSelection } from '../annotationSpans'
import './ReviewAnnotationWorkspace.css'

type Status = 'needs_review' | 'reviewed' | 'needs_adjudication'
type Mention = { raw_aspect: string; start_char: number; end_char: number; canonical_id: string | null; sentiment: Tag['sentiment'] }
type WorkItem = { review_id: string; review_text: string; status: Status; model_mentions: number; annotated_mentions: number | null; reviewer: string | null; corrections_changed: boolean }
type Worklist = { snapshot_id: string | null; summary: Record<Status, number> & { total: number }; items: WorkItem[] }
type AnnotationEvent = { id: string; status: Status; reviewer: string; reason: string; created_at: string; mentions: Mention[] }
type ReviewDetail = { review_id: string; review_text: string; snapshot_id: string; latest_id: string | null; correction_revision: string | null; status: Status; reviewer: string; reason: string; confirmed_no_aspects: boolean; mentions: Mention[]; corrections_changed: boolean; original_predictions: Tag[]; history: AnnotationEvent[]; correction_history: { id: string; reviewer: string; reason: string; original: Tag; resolution: { supported: boolean; canonical_id: string | null; sentiment: string | null } | null }[] }
type Options = { aspects: { id: string; label: string }[] }
const names: Record<Status, string> = { needs_review: 'Needs review', reviewed: 'Reviewed', needs_adjudication: 'Needs adjudication' }

function AnnotationForm({ data, options, productId, onSaved, onReload }: { data: ReviewDetail; options: Options; productId: string; onSaved: (advance: boolean) => Promise<void>; onReload: () => void }) {
  // Keep the versions the draft started from; background fetches cannot silently
  // acknowledge another reviewer's update on behalf of this draft.
  const [baseline] = useState(data)
  const [mentions, setMentions] = useState(data.mentions)
  const [reviewer, setReviewer] = useState(data.reviewer)
  const [reason, setReason] = useState(data.reason)
  const [confirmedEmpty, setConfirmedEmpty] = useState(data.confirmed_no_aspects)
  const [selection, setSelection] = useState<{ start: number; end: number } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const retry = useRef<{ body: string; id: string } | null>(null)
  const chars = Array.from(data.review_text)
  const ordered = [...mentions].sort((a, b) => a.start_char - b.start_char || a.end_char - b.end_char)
  const invalidSpans = ordered.some((mention, index) => !Number.isInteger(mention.start_char) || !Number.isInteger(mention.end_char) || mention.start_char < 0 || mention.end_char <= mention.start_char || mention.end_char > chars.length || !mention.raw_aspect.trim() || (index > 0 && mention.start_char < (ordered[index - 1]?.end_char ?? 0)))
  const ready = !busy && !!reviewer.trim() && !!reason.trim() && !invalidSpans

  function update(index: number, patch: Partial<Mention>) {
    setMentions(current => current.map((mention, i) => {
      if (i !== index) return mention
      const result = { ...mention, ...patch }
      return { ...result, raw_aspect: chars.slice(result.start_char, result.end_char).join('') }
    }))
    setError('')
  }

  function applySelection(index?: number) {
    if (!selection) return
    if (mentions.some((mention, i) => i !== index && selection.start < mention.end_char && selection.end > mention.start_char)) {
      setError('This selection overlaps an existing aspect. Adjust that aspect’s boundaries instead.'); return
    }
    const span = { start_char: selection.start, end_char: selection.end, raw_aspect: chars.slice(selection.start, selection.end).join('') }
    if (index !== undefined) update(index, span)
    else setMentions(current => [...current, { ...span, canonical_id: null, sentiment: 'neutral' }])
    setConfirmedEmpty(false); setError('')
  }

  async function save(status: Status, advance = false) {
    if (!ready || (status === 'reviewed' && !mentions.length && !confirmedEmpty)) return
    const body = { snapshot_id: baseline.snapshot_id, review_id: baseline.review_id,
      expected_previous_id: baseline.latest_id, expected_correction_id: baseline.correction_revision,
      status, reviewer: reviewer.trim(), reason: reason.trim(), mentions: ordered,
      confirmed_no_aspects: mentions.length === 0 && confirmedEmpty }
    const serialized = JSON.stringify(body)
    if (retry.current?.body !== serialized) retry.current = { body: serialized, id: crypto.randomUUID() }
    setBusy(true); setError('')
    try {
      await api(`/demo/products/${productId}/annotations`, { ...body, request_id: retry.current.id })
      retry.current = null
      await onSaved(advance)
    } catch (failure) { setError((failure as Error).message || 'Could not save. Your edits have been kept.') }
    finally { setBusy(false) }
  }

  return <div className="annotation-editor">
    <p className="field-hint">Select a phrase in the review, then add it as an aspect or use it to replace an existing span. Positions count Unicode characters from zero; the end is excluded.</p>
    {data.corrections_changed && <p className="alert alert-warning" role="status">Aspect decisions changed since this review was last saved. Check those changes before marking it reviewed again.</p>}
    <label className="annotation-field">Review text for selection<textarea readOnly value={data.review_text} rows={6} onSelect={event => {
      const element = event.currentTarget
      setSelection(sourceSelection(data.review_text, element.selectionStart, element.selectionEnd))
    }} /></label>
    <div className="annotation-selection"><span aria-live="polite">{selection ? `Selected “${chars.slice(selection.start, selection.end).join('')}” (${selection.start}–${selection.end})` : 'Select text with your mouse, touch, or Shift + arrow keys.'}</span><button type="button" className="button button-secondary" disabled={!selection || busy || mentions.length >= 200} onClick={() => applySelection()}>Add selected phrase</button></div>
    <form onSubmit={event => { event.preventDefault(); void save('needs_review') }}>
      <fieldset disabled={busy} className="annotation-fields">
        <legend>Review annotations</legend>
        <label className="annotation-field">Annotation reviewer<input required value={reviewer} onChange={event => setReviewer(event.target.value)} maxLength={120} autoComplete="name" /></label>
        <p className="field-hint">Reviewer identity is self-reported. Save a draft to keep unfinished work.</p>
        {mentions.length === 0 && <p className="annotation-empty">No aspect mentions yet. Add a missed phrase above, or confirm there are no explicit aspects.</p>}
        {mentions.map((mention, index) => <fieldset className="annotation-mention" key={index}>
          <legend>Aspect {index + 1}: {mention.raw_aspect || 'Choose a valid span'}</legend>
          <div className="annotation-mention__actions"><button type="button" className="button button-secondary" disabled={!selection} onClick={() => applySelection(index)}>Use selection for aspect {index + 1}</button><button type="button" className="button button-quiet" onClick={() => { setMentions(current => current.filter((_, i) => i !== index)); setError('') }}>Remove aspect {index + 1}</button></div>
          <div className="annotation-span"><label className="annotation-field">Start position for aspect {index + 1}<input type="number" min={0} max={chars.length - 1} step={1} value={mention.start_char} onChange={event => update(index, { start_char: event.target.valueAsNumber || 0 })} /></label><label className="annotation-field">End position for aspect {index + 1}<input type="number" min={1} max={chars.length} step={1} value={mention.end_char} onChange={event => update(index, { end_char: event.target.valueAsNumber || 0 })} /></label></div>
          <label className="annotation-field">Category for aspect {index + 1}<select value={mention.canonical_id ?? ''} onChange={event => update(index, { canonical_id: event.target.value || null })}><option value="">Unknown / outside the current categories</option>{options.aspects.map(aspect => <option key={aspect.id} value={aspect.id}>{aspect.label}</option>)}</select></label>
          <label className="annotation-field">Sentiment for aspect {index + 1}<select value={mention.sentiment} onChange={event => update(index, { sentiment: event.target.value as Tag['sentiment'] })}><option value="positive">Positive</option><option value="neutral">Neutral</option><option value="negative">Negative</option></select></label>
        </fieldset>)}
        {invalidSpans && <p className="field-error" role="alert">Aspect spans must be nonempty, inside the review, and must not overlap.</p>}
        {mentions.length === 0 && <label className="annotation-checkbox"><input type="checkbox" checked={confirmedEmpty} onChange={event => setConfirmedEmpty(event.target.checked)} />I checked the full review and found no explicit aspects.</label>}
        <label className="annotation-field">Review notes<textarea required rows={3} value={reason} onChange={event => setReason(event.target.value)} maxLength={2000} /></label>
        <div className="annotation-actions">
          <button className="button button-secondary" type="submit" disabled={!ready}>Save draft</button>
          <button className="button button-primary" type="button" disabled={!ready || (!mentions.length && !confirmedEmpty)} onClick={() => void save('reviewed')}>Mark reviewed</button>
          <button className="button button-primary" type="button" disabled={!ready || (!mentions.length && !confirmedEmpty)} onClick={() => void save('reviewed', true)}>Mark reviewed &amp; next</button>
          <button className="button button-quiet" type="button" disabled={!ready} onClick={() => void save('needs_adjudication')}>Needs adjudication</button>
        </div>
      </fieldset>
    </form>
    {busy && <p role="status">Saving annotation…</p>}
    {error && <div role="alert"><p>{error}</p><button type="button" className="button button-secondary" disabled={busy} onClick={onReload}>Reload saved annotation</button><p className="field-hint">Reload replaces unsaved edits with the latest saved version.</p></div>}
    <details className="annotation-original"><summary>Original model predictions ({data.original_predictions.length})</summary>{data.original_predictions.length ? <ul>{data.original_predictions.map((tag, index) => <li key={index}>{tag.raw_aspect} ({tag.start_char}–{tag.end_char}) · {tag.normalized_aspect ?? 'Unknown'} · {tag.sentiment}</li>)}</ul> : <p>The model detected no aspects.</p>}</details>
    {data.correction_history.length > 0 && <details className="annotation-original" open={data.corrections_changed}><summary>Saved aspect decisions ({data.correction_history.length})</summary><ul>{data.correction_history.map(item => <li key={item.id}><strong>{item.original.raw_aspect}</strong> · {item.reviewer}{item.resolution ? <p>{item.resolution.supported ? `${options.aspects.find(aspect => aspect.id === item.resolution?.canonical_id)?.label ?? 'Unknown / proposed category'} · ${item.resolution.sentiment}` : 'Not a supported aspect'}</p> : <p>Suggestion rejected; no replacement label.</p>}<p>{item.reason}</p></li>)}</ul></details>}
    <details className="annotation-original"><summary>Annotation history ({data.history.length})</summary><ol>{data.history.map(item => <li key={item.id}><strong>{names[item.status]}</strong> · {item.reviewer} · {new Date(item.created_at).toLocaleString()}<p>{item.reason}</p></li>)}</ol></details>
  </div>
}

function ReviewEditor({ productId, snapshotId, reviewId, onSaved }: { productId: string; snapshotId: string; reviewId: string; onSaved: (advance: boolean) => Promise<void> }) {
  const [reload, setReload] = useState(0)
  const [notice, setNotice] = useState('')
  const detail = useQuery({ queryKey: ['review-annotation', productId, snapshotId, reviewId, reload], queryFn: () => api<ReviewDetail>(`/demo/products/${productId}/annotations/${reviewId}?snapshot_id=${snapshotId}`) })
  const options = useQuery({ queryKey: ['correction-options'], queryFn: () => api<Options>('/corrections/options'), staleTime: 60_000 })
  if (detail.isPending || options.isPending) return <p role="status">Loading review annotation…</p>
  if (detail.error || options.error) return <div role="alert"><p>{detail.error?.message ?? options.error?.message}</p><button className="button button-secondary" onClick={() => { void detail.refetch(); void options.refetch() }}>Retry annotation</button></div>
  if (detail.data.snapshot_id !== snapshotId) return <p role="alert">The snapshot changed. Reload the product before annotating.</p>
  return <>{notice && <p role="status" className="alert alert-success">{notice}</p>}<AnnotationForm key={`${detail.data.latest_id ?? 'initial'}:${reload}`} data={detail.data} options={options.data} productId={productId} onSaved={async advance => { await onSaved(advance); if (!advance) setNotice('Annotation saved.'); }} onReload={() => { setNotice(''); setReload(value => value + 1) }} /></>
}

export function ReviewAnnotationWorkspace({ productId, snapshotId }: { productId: string; snapshotId: string }) {
  const client = useQueryClient()
  const [filter, setFilter] = useState<Status | 'all'>('needs_review')
  const [limit, setLimit] = useState(20)
  const [activeReview, setActiveReview] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [exportError, setExportError] = useState('')
  const [exporting, setExporting] = useState(false)
  const key = ['annotation-worklist', productId, snapshotId, filter]
  const queryPath = `/demo/products/${productId}/annotations?snapshot_id=${snapshotId}&status=${filter}`
  const worklist = useQuery({ queryKey: key, queryFn: () => api<Worklist>(queryPath) })
  const mismatch = worklist.data && worklist.data.snapshot_id !== snapshotId

  async function saved(advance: boolean) {
    await client.invalidateQueries({ queryKey: ['annotation-worklist', productId] })
    await client.invalidateQueries({ queryKey: ['review-annotation', productId, snapshotId, activeReview] })
    setMessage('Annotation saved. Original predictions and product totals are unchanged.')
    if (advance) {
      const updated = await client.fetchQuery({ queryKey: key, queryFn: () => api<Worklist>(queryPath) })
      const next = updated.items.find(item => item.review_id !== activeReview && item.status === 'needs_review')
      setActiveReview(next?.review_id ?? null)
      if (!next) setMessage('Annotation saved. No more reviews needing review in this filter.')
    }
  }

  async function download() {
    setExporting(true); setExportError('')
    try {
      const data = await api(`/demo/products/${productId}/annotations/export?snapshot_id=${snapshotId}`)
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
      const link = document.createElement('a'); link.href = url; link.download = `review-annotations-${productId}.json`; link.click(); URL.revokeObjectURL(url)
    } catch (failure) { setExportError((failure as Error).message) }
    finally { setExporting(false) }
  }

  return <section className="content-section annotation-workspace" aria-labelledby="annotation-workspace-title">
    <div className="annotation-heading"><div><h2 id="annotation-workspace-title">Annotation workspace</h2><p className="field-hint">Review complete texts, add missed aspects, and track unfinished or disputed labels.</p></div><button type="button" className="button button-secondary" disabled={exporting || !!mismatch || !worklist.data} onClick={() => void download()}>{exporting ? 'Exporting…' : 'Export annotations'}</button></div>
    {worklist.isPending && <p role="status">Loading annotation progress…</p>}
    {worklist.error && <div role="alert"><p>{worklist.error.message}</p><button type="button" className="button button-secondary" onClick={() => void worklist.refetch()}>Reload annotation workspace</button></div>}
    {mismatch && <p role="alert">The product snapshot changed. Reload the product before reviewing annotations.</p>}
    {worklist.data && !mismatch && <>
      <div className="annotation-progress"><label>Review completion<progress max={Math.max(1, worklist.data.summary.total)} value={worklist.data.summary.reviewed} /></label><p>{worklist.data.summary.reviewed} of {worklist.data.summary.total} reviewed · {worklist.data.summary.needs_review} need review · {worklist.data.summary.needs_adjudication} need adjudication</p></div>
      <label className="annotation-filter">Review status<select value={filter} onChange={event => { setFilter(event.target.value as typeof filter); setLimit(20) }}><option value="all">All reviews</option>{Object.entries(names).map(([status, name]) => <option key={status} value={status}>{name}</option>)}</select></label>
      {worklist.data.items.length ? <ol className="annotation-worklist">{worklist.data.items.slice(0, limit).map(item => <li key={item.review_id}><div><span className={`annotation-status annotation-status--${item.status}`}>{names[item.status]}</span><p>{item.review_text}</p><small>{item.model_mentions} model aspect{item.model_mentions === 1 ? '' : 's'}{item.annotated_mentions !== null ? ` · ${item.annotated_mentions} saved annotations` : ''}{item.reviewer ? ` · ${item.reviewer}` : ''}{item.corrections_changed ? ' · aspect decisions changed' : ''}</small></div><button type="button" className="button button-secondary" onClick={() => { setActiveReview(item.review_id); setMessage('') }}>Annotate review</button></li>)}</ol> : <p className="annotation-empty">No reviews match this status.</p>}
      {worklist.data.items.length > limit && <button type="button" className="button button-secondary" onClick={() => setLimit(value => value + 20)}>Show more reviews</button>}
    </>}
    {message && <p className="alert alert-success" role="status">{message}</p>}
    {exportError && <p className="field-error" role="alert">{exportError}</p>}
    <Dialog open={activeReview !== null} title="Annotate review" variant="drawer" onClose={() => setActiveReview(null)}>{activeReview && <ReviewEditor key={activeReview} productId={productId} snapshotId={snapshotId} reviewId={activeReview} onSaved={saved} />}</Dialog>
  </section>
}
