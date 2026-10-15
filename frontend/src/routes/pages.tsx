import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type Analysis, type Detail, type ImportValidation, type Job, type ModelMetrics, type PreviewPoll, type Product } from '../api'
import { Button } from '../components/Button'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { SentimentBadge } from '../components/SentimentBadge'
import { StatusBadge } from '../components/StatusBadge'
import { Dialog } from '../components/Dialog'
import { SavedDataControls } from '../components/SavedDataControls'
import { SavedImportsPanel } from '../components/SavedImportsPanel'
import { UnknownAspectAssist, ProductReviewAssistant } from '../components/ReviewAssistant'
import { EvidenceRobustnessPanel } from '../components/EvidenceRobustnessPanel'
import { ReviewQualityPanel } from '../components/ReviewQualityPanel'
import { ProductComparisonPanel } from '../components/ProductComparisonPanel'

function ErrorMessage({ error }: { error: string }) {
  return error ? <p className="alert alert-error" role="alert">{error}</p> : null
}

function useDetail(id: string | undefined) {
  const [data, setData] = useState<Detail | null>(null)
  const [error, setError] = useState('')
  const [reloadVersion, setReloadVersion] = useState(0)
  const refresh = useCallback(() => setReloadVersion(value => value + 1), [])
  useEffect(() => {
    let active = true
    setData(null); setError('')
    api<Detail>(`/demo/products/${id}`).then(value => { if (active) setData(value) }).catch(reason => { if (active) setError(String(reason.message)) })
    return () => { active = false }
  }, [id, reloadVersion])
  return { data, error, refresh }
}

function HighlightedReview({ analysis, onEvidence }: { analysis: Analysis; onEvidence?: (tagIndex: number) => void }) {
  const text = analysis.review.review_text
  const chars = Array.from(text)
  const spans = analysis.tags.map((tag, tagIndex) => {
    if (tag.start_char !== undefined && tag.end_char !== undefined) return { start: tag.start_char, end: tag.end_char, tagIndex }
    const index = text.toLowerCase().indexOf(tag.raw_aspect.toLowerCase())
    if (index < 0) return null
    const start = Array.from(text.slice(0, index)).length
    return { start, end: start + Array.from(tag.raw_aspect).length, tagIndex }
  }).filter((span): span is { start: number; end: number; tagIndex: number } => !!span).sort((a, b) => a.start - b.start)
  const parts: React.ReactNode[] = []
  let cursor = 0
  spans.forEach((span, index) => {
    if (span.start < cursor || span.end > chars.length) return
    parts.push(chars.slice(cursor, span.start).join(''))
    const phrase = chars.slice(span.start, span.end).join('')
    parts.push(<button type="button" key={`${span.start}-${index}`} className="aspect-highlight" aria-label={`Show evidence for ${phrase}`} onClick={() => onEvidence?.(span.tagIndex)}>{phrase}</button>)
    cursor = span.end
  })
  parts.push(chars.slice(cursor).join(''))
  return <p className="review-quote">“{parts}”</p>
}

function ReviewResults({ analyses, onEvidence }: { analyses: Analysis[]; onEvidence?: (analysis: Analysis, tagIndex: number) => void }) {
  return <div className="demo-stack">{analyses.map(analysis => <article className="content-section" key={analysis.review.review_id}>
    <HighlightedReview analysis={analysis} onEvidence={index => onEvidence?.(analysis, index)} />
    {analysis.tags.length ? <div className="table-scroll"><table><thead><tr><th>Aspect evidence</th><th>Normalized aspect</th><th>Sentiment</th><th>Generated tag</th><th>Model score</th></tr></thead>
      <tbody>{analysis.tags.map((tag, index) => <tr key={index}><td><button className="evidence-link" onClick={() => onEvidence?.(analysis, index)}>{tag.raw_aspect}</button></td><td>{tag.normalized_aspect ?? 'Unknown'}</td><td><SentimentBadge sentiment={tag.sentiment} /></td><td>{tag.tag ?? 'No canonical tag'}</td><td>{(tag.confidence * 100).toFixed(1)}%</td></tr>)}</tbody></table></div>
      : <p>No aspects detected in this review. Try mentioning a display, battery, keyboard, or another product feature.</p>}
  </article>)}</div>
}

function AspectEvidenceDrawer({ evidence, onClose }: { evidence: { review: Analysis; tagIndex: number } | null; onClose: () => void }) {
  const review = evidence?.review
  const tag = evidence ? review?.tags[evidence.tagIndex] : undefined
  if (!review || !tag) return <Dialog open={false} onClose={onClose} title="Aspect evidence" variant="drawer"> </Dialog>
  const chars = Array.from(review.review.review_text)
  const contextStart = tag.context_start_char ?? tag.start_char ?? 0
  const contextEnd = tag.context_end_char ?? tag.end_char ?? chars.length
  const mentionStart = tag.start_char ?? contextStart
  const mentionEnd = tag.end_char ?? mentionStart + Array.from(tag.raw_aspect).length
  const context = chars.slice(contextStart, contextEnd)
  const relativeStart = Math.max(0, mentionStart - contextStart)
  const relativeEnd = Math.min(context.length, mentionEnd - contextStart)
  return <Dialog open={!!evidence} onClose={onClose} title="Aspect evidence" variant="drawer">
    <p className="field-hint">The highlighted phrase was classified using this context window.</p>
    <p className="review-quote evidence-context">“{context.slice(0, relativeStart).join('')}<mark>{context.slice(relativeStart, relativeEnd).join('')}</mark>{context.slice(relativeEnd).join('')}”</p>
    <dl className="evidence-details"><dt>Matched phrase</dt><dd>{tag.raw_aspect}</dd><dt>Normalized aspect</dt><dd>{tag.normalized_aspect ?? 'Unknown'}</dd><dt>Normalization</dt><dd>{tag.normalization_method ?? 'Not reported'}{tag.normalization_similarity != null ? ` · similarity ${(tag.normalization_similarity * 100).toFixed(1)}%` : ''}</dd><dt>Context policy</dt><dd>{review.context_policy ?? 'Not reported'}</dd><dt>Sentiment</dt><dd><SentimentBadge sentiment={tag.sentiment} /></dd><dt>Sentiment confidence</dt><dd>{tag.sentiment_confidence == null ? 'Not reported' : `${(tag.sentiment_confidence * 100).toFixed(1)}%`}</dd><dt>Aspect confidence</dt><dd>{tag.aspect_confidence == null ? 'Not reported' : `${(tag.aspect_confidence * 100).toFixed(1)}%`}</dd><dt>Tag</dt><dd>{tag.tag ?? 'No canonical tag'}</dd><dt>Summary score</dt><dd>{(tag.confidence * 100).toFixed(1)}%</dd>{tag.probabilities && <><dt>Sentiment probabilities</dt><dd>{(['negative', 'neutral', 'positive'] as const).map(label => `${label} ${((tag.probabilities?.[label] ?? 0) * 100).toFixed(1)}%`).join(' · ')}</dd></>}</dl>
    {tag.normalized_aspect === null && <UnknownAspectAssist key={`${review.review.review_id}:${tag.start_char}`} review={review} tag={tag} />}
  </Dialog>
}

function discardRemovedProductDrafts(products: Product[]) {
  const existing = new Set(products.map(product => product.id))
  if (existing.has('00000000-0000-4000-8000-000000000001')) existing.add('demo-laptop')
  try {
    const keys = Array.from({ length: localStorage.length }, (_, index) => localStorage.key(index))
    for (const key of keys) {
      const match = key?.match(/^review-tag-(?:draft|job):([^:]+):(?:review|import)$/)
      const productId = match?.[1]
      if (key && productId && !existing.has(productId)) localStorage.removeItem(key)
    }
  } catch { /* Keep the product list usable when browser storage is unavailable. */ }
}

export function ProductsPage() {
  const [products, setProducts] = useState<Product[] | null>(null)
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { let active = true; api<Product[]>('/demo/products').then(value => { if (active) { discardRemovedProductDrafts(value); setProducts(value) } }).catch(reason => { if (active) setError(reason.message) }); return () => { active = false } }, [])
  async function refreshProducts() {
    try { const value = await api<Product[]>('/demo/products'); discardRemovedProductDrafts(value); setProducts(value); setError('') }
    catch (reason) { setError((reason as Error).message) }
  }
  async function create(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try { await api('/demo/products', { name }); setProducts(await api<Product[]>('/demo/products')); setName('') } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }
  return <>
    <PageHeader eyebrow="Workspace" title="Products" description="Explore customer feedback, analyze a new review, and generate aspect-level tags." />
    <ErrorMessage error={error} />
    <form className="content-section demo-form" onSubmit={create}>
      <label htmlFor="product-name">Create a product</label><div className="demo-actions"><input id="product-name" value={name} onChange={event => setName(event.target.value)} placeholder="e.g. Campus laptop" maxLength={120} required /><Button busy={busy} disabled={!name.trim()}>Create product</Button></div>
    </form>
    <div className="demo-stack">{products === null && !error && <p role="status">Connecting to backend and loading products…</p>}
      {products?.map(product => <section className="content-section" key={product.id}><div className="section-heading"><div><h2>{product.name}</h2><p>{product.review_count} saved reviews</p></div><StatusBadge tone="success">Ready to analyze</StatusBadge></div>
        <div className="demo-actions"><Link className="button button-primary" to={`/products/${product.id}`}>View insights</Link><Link className="button button-secondary" to={`/products/${product.id}/review`}>Analyze review</Link><Link className="text-link" to={`/products/${product.id}/upload`}>Import reviews</Link></div><SavedDataControls productId={product.id} productName={product.name} onCleared={() => void refreshProducts()} onDeleted={() => void refreshProducts()} /></section>)}
      {products?.length === 0 && <EmptyState title="No products yet">Create a product above to start analyzing reviews.</EmptyState>}
    </div>
  </>
}

export function ProductDetailPage() {
  const navigate = useNavigate()
  const { id } = useParams(); const { data, error, refresh } = useDetail(id)
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<'support' | 'name' | 'sentiment'>('support')
  const [evidence, setEvidence] = useState<{ review: Analysis; tagIndex: number } | null>(null)
  const [regeneration, setRegeneration] = useState<Job | null>(null)
  const [regenerationError, setRegenerationError] = useState('')
  const [regenerationBusy, setRegenerationBusy] = useState(false)
  const regenerationId = regeneration?.id
  const regenerationStatus = regeneration?.status
  const regenerationActive = !!regenerationId && !!regenerationStatus && !['completed', 'completed_with_errors', 'failed'].includes(regenerationStatus)
  const aspects = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const rows = (data?.insights.aspects ?? []).map(item => {
      if (item.counts) return item
      const counts: Record<string, number> = { positive: 0, neutral: 0, negative: 0 }
      for (const review of data?.reviews ?? []) {
        const sentiments = new Set(review.tags.filter(tag => tag.normalized_aspect === item.aspect || tag.normalized_aspect === item.aspect_id).map(tag => tag.sentiment))
        for (const sentiment of sentiments) counts[sentiment] = (counts[sentiment] ?? 0) + 1
      }
      return { ...item, counts, ratios: Object.fromEntries(Object.entries(counts).map(([key, value]) => [key, value / Math.max(item.review_count, 1)])) }
    }).filter(item => !needle || item.aspect.toLowerCase().includes(needle) || item.classification.includes(needle))
    return rows.sort((a, b) => sort === 'name' ? a.aspect.localeCompare(b.aspect) : sort === 'sentiment' ? (b.ratios?.positive ?? 0) - (a.ratios?.positive ?? 0) : b.review_count - a.review_count)
  }, [data, query, sort])
  useEffect(() => {
    if (!regenerationId || !regenerationStatus || !regenerationActive) return
    let active = true
    let checking = false
    const poll = async () => {
      if (checking) return
      checking = true
      try { const result = await api<Job>(`/demo/jobs/${regenerationId}`); if (active) { setRegeneration(result); setRegenerationError('') } }
      catch { if (active) setRegenerationError('Connection interrupted while checking refresh progress. Reconnecting automatically…') }
      finally { checking = false }
    }
    void poll()
    const timer = window.setInterval(() => void poll(), 1500)
    return () => { active = false; window.clearInterval(timer) }
  }, [regenerationActive, regenerationId, regenerationStatus])
  useEffect(() => {
    if (regenerationStatus === 'completed' || regenerationStatus === 'completed_with_errors') refresh()
  }, [regenerationStatus, refresh])
  async function regenerate() {
    if (!id) return
    setRegenerationBusy(true); setRegenerationError('')
    try { setRegeneration(await api<Job>(`/demo/products/${id}/regenerate`, {})) }
    catch (reason) { setRegenerationError((reason as Error).message) } finally { setRegenerationBusy(false) }
  }
  return <><PageHeader eyebrow="Product insights" title={data?.product.name ?? 'Product'} description="Saved review evidence, generated tags, and recurring customer opinions." /><ErrorMessage error={error} />
    {!data && !error && <p role="status">Loading insights…</p>}
    {data && <><div className="demo-actions"><Link className="button button-primary" to={`/products/${id}/review`}>Analyze a review</Link><Link className="button button-secondary" to={`/products/${id}/upload`}>Import reviews</Link><StatusBadge>{data.backend === 'transformer' ? 'Trained DistilBERT' : 'Heuristic demo'}</StatusBadge></div>
      {data.stale && <section className="alert alert-warning stale-insights"><div><strong>Showing the last published analysis</strong><p>These insights may use an earlier analysis version or exclude recent reviews. Refresh analyses to include saved feedback.</p></div><Button variant="secondary" onClick={() => void regenerate()} disabled={regenerationBusy || regenerationActive}>{regenerationActive ? 'Refresh in progress…' : 'Refresh analyses'}</Button>{regeneration && <p role="status">Refresh job {regeneration.status.replaceAll('_', ' ')} · {regeneration.completed_rows} of {regeneration.total_rows} reviews analyzed</p>}{regenerationError && <p role="alert">{regenerationError}</p>}</section>}
      <SavedDataControls productId={data.product.id} productName={data.product.name} onCleared={refresh} onDeleted={() => navigate('/products')} />
      <SavedImportsPanel key={`imports:${data.product.id}:${data.snapshot_id}`} productId={data.product.id} onRemoved={refresh} />
      <div className="demo-stats"><section><strong>{data.insights.review_count}</strong><span>Saved reviews</span></section>{['positive', 'neutral', 'negative'].map(sentiment => <section key={sentiment}><strong>{data.insights.sentiment_distribution[sentiment] ?? 0}</strong><span>{sentiment} aspect votes</span></section>)}</div>
      <section className="content-section"><div className="section-heading"><div><h2>Sentiment by aspect</h2><p>Review votes grouped by detected product feature.</p></div></div>
        {data.insights.aspects.length ? <div className="sentiment-chart" role="img" aria-label="Stacked chart showing positive, neutral, and negative votes by aspect"><ResponsiveContainer width="100%" height={Math.max(220, data.insights.aspects.length * 42)}><BarChart data={aspects} layout="vertical" margin={{ left: 20, right: 18, top: 8, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" allowDecimals={false} /><YAxis type="category" dataKey="aspect" width={95} tick={{ fontSize: 11 }} /><Tooltip /><Bar isAnimationActive={false} dataKey="counts.positive" name="Positive" stackId="votes" fill="#177451" /><Bar isAnimationActive={false} dataKey="counts.neutral" name="Neutral" stackId="votes" fill="#a5b0aa" /><Bar isAnimationActive={false} dataKey="counts.negative" name="Negative" stackId="votes" fill="#b54742" /></BarChart></ResponsiveContainer></div> : <p className="field-hint">No aspect votes to chart yet.</p>}
      </section>
      <section className="content-section"><h2>Supported product tags</h2><p className="field-hint">Tags require at least three supporting reviews. Add more feedback to establish recurring themes.</p><div className="demo-actions">{data.insights.top_tags.map(tag => <StatusBadge key={tag.aspect_id}>{tag.aggregate_tag ?? tag.aspect}</StatusBadge>)}{!data.insights.top_tags.length && <p>No tags have enough evidence yet.</p>}</div></section>
      {!!data.insights.aspects.length && <section className="content-section demo-spaced"><div className="section-heading"><div><h2>Aspect summary</h2><p>Search and sort to inspect support and sentiment.</p></div></div><div className="insight-controls"><label>Search aspects<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Display, battery…" /></label><label>Sort by<select value={sort} onChange={event => setSort(event.target.value as typeof sort)}><option value="support">Review support</option><option value="name">Aspect name</option><option value="sentiment">Positive share</option></select></label></div><div className="table-scroll"><table><thead><tr><th>Aspect</th><th>Review support</th><th>Positive</th><th>Neutral</th><th>Negative</th><th>Classification</th></tr></thead><tbody>{aspects.map(aspect => <tr key={aspect.aspect_id}><td>{aspect.aspect}</td><td>{aspect.review_count}</td><td>{aspect.counts?.positive ?? '—'}</td><td>{aspect.counts?.neutral ?? '—'}</td><td>{aspect.counts?.negative ?? '—'}</td><td>{aspect.classification.replaceAll('_', ' ')}</td></tr>)}</tbody></table>{!aspects.length && <p className="field-hint">No aspects match that search.</p>}</div></section>}
      <ProductReviewAssistant key={`ask:${data.product.id}:${data.snapshot_id}`} productId={data.product.id} snapshotId={data.snapshot_id ?? null} />
      <EvidenceRobustnessPanel key={`robustness:${data.product.id}:${data.snapshot_id}`} productId={data.product.id} snapshotId={data.snapshot_id ?? null} />
      <ReviewQualityPanel key={`quality:${data.product.id}:${data.snapshot_id}`} productId={data.product.id} snapshotId={data.snapshot_id ?? null} />
      <ProductComparisonPanel key={`comparison:${data.product.id}:${data.snapshot_id}`} productId={data.product.id} />
      <section className="content-section demo-spaced"><h2>Representative reviews</h2><div className="representative-list">{(data.insights.representative_reviews ?? []).map((item, index) => <article key={`${item.review_id}-${index}`}><div className="section-heading"><strong>{item.aspect ?? data.insights.aspects.find(aspect => aspect.aspect_id === item.aspect_id)?.aspect ?? 'Product aspect'}</strong><SentimentBadge sentiment={item.sentiment as 'positive' | 'neutral' | 'negative'} /></div><p className="review-quote">“{item.review_text}”</p><span className="field-hint">{item.tag ?? `Representative evidence · ${((item.confidence ?? 0) * 100).toFixed(1)}% model score`}</span></article>)}{!data.insights.representative_reviews?.length && <p className="field-hint">Representative reviews will appear as reviews are analyzed.</p>}</div></section>
      <h2 className="demo-spaced">Review evidence</h2><ReviewResults analyses={data.reviews} onEvidence={(review, tagIndex) => setEvidence({ review, tagIndex })} />{!data.reviews.length && <EmptyState title="No reviews yet">Analyze a review to populate this product’s insights.</EmptyState>}
      <AspectEvidenceDrawer evidence={evidence} onClose={() => setEvidence(null)} />
    </>}
  </>
}

function ReviewForm({ importing = false }: { importing?: boolean }) {
  const { id } = useParams()
  const storageKey = `review-tag-draft:${id}:${importing ? 'import' : 'review'}`
  const jobStorageKey = `review-tag-job:${id}:${importing ? 'import' : 'review'}`
  const [text, setText] = useState('')
  const [filename, setFilename] = useState('pasted-reviews.txt')
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [ready, setReady] = useState(false)
  const [restored, setRestored] = useState(false)
  const [previewText, setPreviewText] = useState('')
  const [previewFilename, setPreviewFilename] = useState('')
  const [previewIds, setPreviewIds] = useState<string[]>([])
  const [previewTargetText, setPreviewTargetText] = useState('')
  const [job, setJob] = useState<Job | null>(null)
  const [submitted, setSubmitted] = useState<{ text: string; filename: string; idempotencyKey: string } | null>(null)
  const [saveKey, setSaveKey] = useState<string | null>(null)
  const [importValidation, setImportValidation] = useState<ImportValidation | null>(null)
  const [evidence, setEvidence] = useState<{ review: Analysis; tagIndex: number } | null>(null)
  const activeJob = !!job && !['completed', 'completed_with_errors', 'failed'].includes(job.status)
  const activeJobId = job?.id
  const activeJobStatus = job?.status
  const completedJob = activeJobStatus === 'completed'
  const terminalJob = ['completed', 'completed_with_errors', 'failed'].includes(activeJobStatus ?? '')
  const fieldsLocked = busy || activeJob || (completedJob && !!submitted)
  const previewReviews = importing ? importValidation?.reviews.slice(0, 100) ?? [] : (text.trim() ? [text] : [])
  useEffect(() => {
    try {
      const draftValue = localStorage.getItem(storageKey)
      if (draftValue) {
        try {
          const draft = JSON.parse(draftValue) as { text?: string; filename?: string; idempotencyKey?: string }
          if (typeof draft.text === 'string') { setText(draft.text); setFilename(draft.filename ?? 'pasted-reviews.txt'); setSaveKey(draft.idempotencyKey ?? null) }
          else setText(draftValue)
        } catch { setText(draftValue) }
        setRestored(true)
      }
      const savedJob = localStorage.getItem(jobStorageKey)
      if (savedJob) {
        const value = JSON.parse(savedJob) as { job: Job; submitted: { text: string; filename: string; idempotencyKey: string } }
        if (value.job?.id) { setJob(value.job); setSubmitted(value.submitted); setRestored(true) }
      }
    } catch { /* Storage can be unavailable in private browsing. */ }
    setReady(true)
  }, [jobStorageKey, storageKey])
  useEffect(() => {
    if (!ready || activeJob) return
    try { if (text) localStorage.setItem(storageKey, JSON.stringify({ text, filename, idempotencyKey: saveKey })); else localStorage.removeItem(storageKey) } catch { /* Keep editing if storage is unavailable. */ }
  }, [activeJob, filename, ready, saveKey, storageKey, text])
  useEffect(() => {
    if (!ready || !job || !submitted) return
    try { localStorage.setItem(jobStorageKey, JSON.stringify({ job, submitted })) } catch { /* Job polling still works if storage is unavailable. */ }
  }, [job, jobStorageKey, ready, submitted])
  useEffect(() => {
    if (!activeJobId || !activeJobStatus || ['completed', 'completed_with_errors', 'failed'].includes(activeJobStatus)) return
    let active = true
    let checking = false
    const poll = async () => {
      if (checking) return
      checking = true
      try { const value = await api<Job>(`/demo/jobs/${activeJobId}`); if (active) { setJob(value); setError('') } }
      catch { if (active) setError('Connection interrupted while checking progress. Reconnecting automatically…') }
      finally { checking = false }
    }
    void poll()
    const timer = window.setInterval(() => void poll(), 1500)
    return () => { active = false; window.clearInterval(timer) }
  }, [activeJobId, activeJobStatus])
  useEffect(() => {
    if (!previewIds.length) return
    let active = true
    const poll = async () => {
      try {
        const states = await Promise.all(previewIds.map(previewId => api<PreviewPoll>(`/demo/previews/${previewId}`)))
        if (!active) return
        const failed = states.find(state => state.status === 'failed')
        if (failed) { setError(failed.error_summary ?? 'One or more reviews could not be analyzed.'); setPreviewIds([]); setBusy(false); return }
        if (states.every(state => state.status === 'completed' && state.analysis)) {
          setAnalyses(states.map(state => state.analysis as Analysis)); setPreviewText(previewTargetText); setPreviewFilename(filename); setRestored(false); setPreviewIds([]); setBusy(false)
        }
      } catch (reason) { if (active) { setError((reason as Error).message); setPreviewIds([]); setBusy(false) } }
    }
    void poll()
    const timer = window.setInterval(() => void poll(), 1000)
    return () => { active = false; window.clearInterval(timer) }
  }, [filename, previewIds, previewTargetText])
  useEffect(() => {
    if (!terminalJob) return
    setSaveKey(null)
    if (completedJob) {
      if (submitted && text === submitted.text && filename === submitted.filename) { setText(''); setFilename('pasted-reviews.txt'); setRestored(false) }
      setSubmitted(null)
      try { localStorage.removeItem(jobStorageKey) } catch { /* Ignore unavailable storage. */ }
    } else if (submitted?.idempotencyKey) setSubmitted({ ...submitted, idempotencyKey: '' })
  }, [completedJob, filename, jobStorageKey, submitted, terminalJob, text])
  async function preview() {
    setBusy(true); setError(''); setAnalyses([]); setPreviewIds([]); setJob(null); setSubmitted(null); setImportValidation(null)
    try { localStorage.removeItem(jobStorageKey) } catch { /* Ignore unavailable storage. */ }
    let waiting = false
    try {
      const reviews = importing ? previewReviews : (text.trim() ? [text] : [])
      const validation = importing ? await api<ImportValidation>('/demo/imports/validate', { filename, content: text }) : null
      if (validation) setImportValidation(validation)
      const previewBatch = validation ? validation.reviews.slice(0, 100) : reviews
      if (!previewBatch.length) { setError('No valid reviews were found to preview.'); return }
      const result = await api<{ analyses: Analysis[]; preview_ids?: string[] }>(`/demo/products/${id}/preview`, { reviews: previewBatch })
      if (result.preview_ids?.length) { waiting = true; setPreviewTargetText(text); setPreviewIds(result.preview_ids); return }
      setAnalyses(result.analyses); setPreviewText(text); setPreviewFilename(filename); setRestored(false)
    } catch (reason) { setError((reason as Error).message) } finally { if (!waiting) setBusy(false) }
  }
  async function save() {
    setBusy(true); setError('')
    const idempotencyKey = saveKey ?? crypto.randomUUID()
    setSaveKey(idempotencyKey)
    try { localStorage.setItem(storageKey, JSON.stringify({ text, filename, idempotencyKey })) } catch { /* Saving still proceeds if browser storage is full or unavailable. */ }
    try {
      const result = importing
        ? await api<Job>(`/demo/products/${id}/imports`, { filename, content: text }, idempotencyKey)
        : await api<Job>(`/demo/products/${id}/jobs`, { reviews: [text] }, idempotencyKey)
      setJob(result); setSubmitted({ text, filename, idempotencyKey }); setAnalyses([]); setPreviewText('')
    } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }
  async function retryFailed() {
    if (!job) return
    setBusy(true); setError('')
    try { const result = await api<Job>(`/demo/jobs/${job.id}/retry`, {}); setJob(result) }
    catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }
  function downloadValidationErrors() {
    if (!importValidation?.errors.length) return
    const cell = (value: string | number) => {
      const safe = /^[=+\-@\t\r]/.test(String(value)) ? `'${value}` : value
      return `"${String(safe).replaceAll('"', '""')}"`
    }
    const content = [['row', 'error'], ...importValidation.errors.map(issue => [issue.row, issue.error])].map(row => row.map(cell).join(',')).join('\r\n')
    const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = 'import-validation-errors.csv'; anchor.click()
    URL.revokeObjectURL(url)
  }
  return <><PageHeader eyebrow="Product workspace" title={importing ? 'Import reviews' : 'Review analyzer'} description={importing ? 'Paste one review per line or load a text file. Preview the batch, then save it for analysis.' : 'Preview extracted aspects and sentiment first, then save the review when the evidence looks right.'} />
    <p><Link className="text-link" to={`/products/${id}`}>← Product insights</Link></p><ErrorMessage error={error} />
    {restored && <p className="alert alert-info" role="status">Recovered an unsaved draft from this browser. Review it and preview again before saving.</p>}
    {activeJob && <p className="alert alert-info" role="status">A submitted job is still processing. Progress polling has resumed; editing is paused to protect the draft.</p>}
    <form className="content-section demo-form" onSubmit={event => { event.preventDefault(); void preview() }}>
      {importing && <><label htmlFor="review-file">Load a text file (.txt, .csv, .json, .jsonl)</label><input id="review-file" type="file" accept=".txt,.csv,.json,.jsonl,text/plain,text/csv,application/json" disabled={fieldsLocked} onChange={async event => { const file = event.target.files?.[0]; if (file) { if (file.size > 10485760) { setError('Please use a file smaller than 10 MB.'); return } try { setText(await file.text()); setFilename(file.name); setSaveKey(null); setAnalyses([]); setPreviewText(''); setError('') } catch { setError('Unable to read the file. Please paste the reviews instead.') } } }} /></>}
      <label htmlFor="review-text">{importing ? 'Reviews — one per line' : 'Customer review'}</label>
      <textarea id="review-text" rows={importing ? 8 : 5} value={text} onChange={event => { setText(event.target.value); setSaveKey(null); if (importing) setFilename('pasted-reviews.txt'); setAnalyses([]); setPreviewText(''); setImportValidation(null) }} required disabled={fieldsLocked} maxLength={importing ? 1000000 : 10000} />
      <div className="demo-actions"><Button busy={busy} disabled={!text.trim() || !ready || fieldsLocked}>{busy ? 'Analyzing…' : 'Preview analysis'}</Button><Button type="button" variant="quiet" disabled={!text || fieldsLocked} onClick={() => { setText(''); setFilename('pasted-reviews.txt'); setSaveKey(null); setAnalyses([]); setPreviewText(''); setRestored(false) }}>Clear draft</Button><span className="field-hint">Draft and file name are saved in this browser automatically.</span></div>
      <p className="field-hint">Preview does not save reviews or change product totals. Model scores are uncalibrated confidence estimates.</p>
    </form>
    <div aria-live="polite">{busy && <p role="status">{job ? 'Submitting or retrying reviews…' : 'Running aspect extraction and sentiment classification…'}</p>}{importValidation && <p className="field-hint">Import validation found {importValidation.reviews.length} valid reviews out of {importValidation.total_rows} rows{importValidation.errors.length ? ` and ${importValidation.errors.length} invalid rows` : ''}. Preview is limited to the first 100 valid reviews.</p>}{importValidation?.errors.length ? <div className="alert alert-warning"><strong>Rows skipped during preview validation</strong>{importValidation.errors.slice(0, 5).map(issue => <p key={`${issue.row}-${issue.error}`}>Row {issue.row}: {issue.error}</p>)}<Button type="button" variant="secondary" onClick={downloadValidationErrors}>Download all validation errors</Button></div> : null}{importValidation && importValidation.reviews.length > 100 && <p className="alert alert-warning">Preview shows the first 100 valid reviews. Saving imports the full file.</p>}{analyses.length > 0 && <><p className="alert alert-success">Preview ready · {analyses.length} review{analyses.length === 1 ? '' : 's'} · {analyses[0]?.backend === 'transformer' ? 'Trained DistilBERT' : 'Heuristic demo'} · product totals are unchanged</p><ReviewResults analyses={analyses} onEvidence={(review, tagIndex) => setEvidence({ review, tagIndex })} /><div className="demo-actions"><Button onClick={() => void save()} disabled={busy || activeJob || previewText !== text || (importing && previewFilename !== filename)}>{importing ? 'Save import' : 'Save review'}</Button><span className="field-hint">Saving adds these reviews to product insights.</span></div></>}
      {job && <section className="content-section demo-spaced"><div className="section-heading"><div><h2>{importing ? 'Import progress' : 'Review save progress'}</h2><p>{job.status.replaceAll('_', ' ')} · {job.completed_rows} of {job.total_rows} rows analyzed{job.duplicate_rows ? ` · ${job.duplicate_rows} duplicates skipped` : ''}</p></div><StatusBadge tone={job.status === 'failed' ? 'error' : job.status === 'completed' ? 'success' : 'warning'}>{job.status.replaceAll('_', ' ')}</StatusBadge></div>{job.errors?.length ? <div className="alert alert-error"><strong>{job.errors.length} row{job.errors.length === 1 ? '' : 's'} need attention</strong>{job.errors.map((item, index) => <p key={`${item.row}-${index}`}>Row {item.row ?? index + 1}: {item.error ?? item.message ?? 'Could not process row'}</p>)}</div> : null}{(job.failed_rows > 0 || (job.rejected_rows ?? 0) > 0) && <p><a className="text-link" href={`/api/demo/jobs/${job.id}/errors.csv`}>Download row errors (CSV)</a></p>}{job.failed_rows > 0 && ['failed', 'completed_with_errors'].includes(job.status) && <div className="demo-actions"><Button variant="secondary" onClick={() => void retryFailed()} disabled={busy}>Retry failed reviews</Button></div>}{['completed', 'completed_with_errors'].includes(job.status) && <p><Link className="text-link" to={`/products/${id}`}>View updated product insights →</Link></p>}</section>}
      <AspectEvidenceDrawer evidence={evidence} onClose={() => setEvidence(null)} />
    </div>
  </>
}
export function ReviewPage() { return <ReviewForm /> }
export function UploadPage() { return <ReviewForm importing /> }

function valueAt(value: unknown, path: string[]): unknown {
  return path.reduce<unknown>((current, key) => current && typeof current === 'object' ? (current as Record<string, unknown>)[key] : undefined, value)
}

function metricText(value: unknown): string | null {
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3)
  if (typeof value === 'boolean' || typeof value === 'string') return String(value)
  return null
}

export function ModelsPage() {
  const [health, setHealth] = useState<{ backend: string; storage: string } | null>(null)
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    api<{ backend: string; storage: string }>('/health').then(value => { if (active) setHealth(value) }).catch(reason => { if (active) setError((reason as Error).message) })
    api<ModelMetrics>('/models/metrics').then(value => { if (active) setMetrics(value) }).catch(reason => { if (active) setError((reason as Error).message) })
    return () => { active = false }
  }, [])
  const artifactRecords = metrics?.records
  const cards = [
    { title: 'Aspect extraction · held-out test', source: 'current/test', values: [['Exact-span F1', ['aspect_extraction', 'exact_span', 'f1']], ['Precision', ['aspect_extraction', 'exact_span', 'precision']], ['Recall', ['aspect_extraction', 'exact_span', 'recall']], ['Reviews', ['aspect_extraction', 'review_count']]] },
    { title: 'Sentiment · held-out test', source: 'A3/sentiment_test', values: [['Macro F1', ['macro_f1']], ['Accuracy', ['accuracy']], ['Negative recall', ['per_class_recall', 'negative']], ['Neutral recall', ['per_class_recall', 'neutral']], ['Positive recall', ['per_class_recall', 'positive']]] },
    { title: 'Normalization · synthetic fixtures', source: 'current/normalization-fixture-report', values: [['Held-out accuracy', ['alias_only', 'heldout', 'accuracy_including_unknowns']], ['Examples', ['alias_only', 'heldout', 'examples']], ['False known unknowns', ['alias_only', 'heldout', 'false_known_unknown_count']]] },
  ]
  const policy = valueAt(artifactRecords, ['current/policy']) as Record<string, unknown> | undefined
  const split = valueAt(artifactRecords, ['current/split_hashes']) as Record<string, unknown> | undefined
  const testSplit = split?.splits && typeof split.splits === 'object' ? (split.splits as Record<string, unknown>).test as Record<string, unknown> | undefined : undefined
  return <><PageHeader eyebrow="System" title="Model metrics" description="Evaluation evidence for the extraction, sentiment, and normalization models." /><ErrorMessage error={error} /><section className="content-section"><h2>Inference status</h2>{health ? <><StatusBadge tone="success">{health.backend === 'transformer' ? 'Trained DistilBERT models loaded' : 'Heuristic demo mode'}</StatusBadge><p className="muted-copy">Storage: {health.storage}. Aspect extraction and sentiment classification run on this computer.</p></> : <p>Checking backend…</p>}<h2 className="demo-spaced">Evaluation metrics</h2>{metrics ? <><p className="field-hint">Recorded results are tied to named evaluation runs. Normalization accuracy uses synthetic fixtures; human review gate: {metrics.human_normalization_gate ?? 'pending'}.</p>{cards.map(card => {
    const record = artifactRecords?.[card.source]
    const values = card.values.map(([label, path]) => [label, metricText(valueAt(record, path as string[]))] as const).filter((item): item is readonly [string, string] => item[1] !== null)
    return <section className="metrics-group" key={card.source}><h3>{card.title}</h3>{values.length ? <div className="metric-values">{values.map(([label, value]) => <div key={label}><strong>{value}</strong><span>{label}</span></div>)}</div> : <p className="field-hint">No scores were recorded for this run.</p>}</section>
  })}<details className="metrics-provenance"><summary>Run policy and data provenance</summary><dl className="evidence-details"><dt>Pipeline version</dt><dd className="hash-value">{String(metrics.pipeline_version ?? 'Not reported')}</dd><dt>Context policy</dt><dd>{String(metrics.context_policy ?? 'Not reported')}</dd><dt>Inference backend</dt><dd>{String(metrics.backend ?? health?.backend ?? 'Not reported')}</dd><dt>Selected policy</dt><dd>{String(policy?.selected ?? 'Not reported')}</dd><dt>Policy settings</dt><dd>{policy?.settings ? JSON.stringify(policy.settings) : 'Not reported'}</dd><dt>Test data SHA-256</dt><dd className="hash-value">{String(testSplit?.file_sha256 ?? 'Not reported')}</dd><dt>Aspect split SHA-256</dt><dd className="hash-value">{String(testSplit?.a2_review_list_sha256 ?? 'Not reported')}</dd><dt>Sentiment split SHA-256</dt><dd className="hash-value">{String(testSplit?.a3_deduplicated_pair_list_sha256 ?? 'Not reported')}</dd></dl></details></> : !error && <p role="status">Loading evaluation evidence…</p>}</section></>
}

export function NotFoundPage() {
  return <><PageHeader eyebrow="Page not found" title="That address isn’t available" description="The page may have moved or the link may be incomplete." /><p><Link className="text-link" to="/products">Return to products</Link></p></>
}
