import { useCallback, useEffect, useState } from 'react'
import { Link, NavLink, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, type Analysis, type Detail, type ImportValidation, type Job, type ModelMetrics, type PreviewPoll, type Product } from '../api'
import { Button } from '../components/Button'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { SentimentBadge } from '../components/SentimentBadge'
import { StatusBadge } from '../components/StatusBadge'
import { Dialog } from '../components/Dialog'
import { SavedDataControls } from '../components/SavedDataControls'
import { SavedImportsPanel } from '../components/SavedImportsPanel'
import { UnknownAspectAssist, ProductReviewAssistant, type SavedAspectContext } from '../components/ReviewAssistant'
import { AspectCorrectionPanel, CorrectionExport } from '../components/AspectCorrectionPanel'
import { ReviewAnnotationWorkspace } from '../components/ReviewAnnotationWorkspace'
import { EvidenceRobustnessPanel } from '../components/EvidenceRobustnessPanel'
import { ReviewQualityPanel } from '../components/ReviewQualityPanel'
import { ProductInsights } from '../components/ProductInsights'
import { Icon } from '../components/Icon'

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

function AspectEvidenceDrawer({ evidence, onClose, savedContext }: { evidence: { review: Analysis; tagIndex: number } | null; onClose: () => void; savedContext?: SavedAspectContext }) {
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
    {savedContext && tag.start_char !== undefined && tag.end_char !== undefined
      ? <AspectCorrectionPanel key={`${savedContext.snapshotId}:${review.review.review_id}:${tag.start_char}:${tag.end_char}`} review={review} tag={tag} savedContext={savedContext} />
      : tag.normalized_aspect === null && <UnknownAspectAssist key={`${review.review.review_id}:${tag.start_char}`} review={review} tag={tag} />}
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
  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''
  useEffect(() => {
    let active = true
    api<Product[]>('/demo/products').then(value => { if (active) { discardRemovedProductDrafts(value); setProducts(value) } }).catch(reason => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [])
  async function create(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try { await api('/demo/products', { name }); setProducts(await api<Product[]>('/demo/products')); setName('') }
    catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }
  const visible = products?.filter(product => product.name.toLowerCase().includes(query.toLowerCase()))
  return <>
    <PageHeader eyebrow="A more considered purchase" title="Saved products" description="Keep your options together. Let the reviews tell you more." actions={<Link className="button button-secondary" to="/companion"><Icon name="browser" /> Browser companion</Link>} />
    <ErrorMessage error={error} />
    <section className="collection-intro"><div><span className="section-number">01 / YOUR SHORTLIST</span><h2>Good decisions start with a closer look.</h2><p>Collect reviews, uncover recurring feedback, and compare the features that matter to you.</p></div><div className="collection-total"><strong>{products?.length ?? '—'}</strong><span>saved product{products?.length === 1 ? '' : 's'}</span></div></section>
    <form className="create-product-form demo-form" onSubmit={create}>
      <label htmlFor="product-name">Create a product</label><div className="demo-actions"><input id="product-name" value={name} onChange={event => setName(event.target.value)} placeholder="Name a product you’re considering…" maxLength={120} required /><Button busy={busy} disabled={!name.trim()}><Icon name="plus" /> Create product</Button></div>
    </form>
    <div className="collection-toolbar"><h2>Your products <span>{products?.length ?? '—'}</span></h2><label className="collection-search"><Icon name="search" /><span className="sr-only">Search saved products</span><input value={query} placeholder="Search your products…" onChange={event => setParams(event.target.value ? { q: event.target.value } : {}, { replace: true })} /></label></div>
    <div className="product-collection">
      {products === null && !error && <p role="status">Connecting to the local service and loading your products…</p>}
      {visible?.map((product, index) => <section className="content-section saved-product-row" key={product.id}><div className="product-thumbnail" aria-hidden="true"><Icon name="bookmark" /><span>{String(index + 1).padStart(2, '0')}</span></div><div className="saved-product-info"><span className="product-kicker">SAVED PRODUCT</span><h2>{product.name}</h2><p>{product.review_count} saved review{product.review_count === 1 ? '' : 's'} <span aria-hidden="true">·</span> {product.review_count ? 'Ready to explore' : 'Add reviews to see feedback'}</p><div className="product-row-links"><Link to={`/products/${product.id}/review`}>Analyze review</Link><Link to={`/products/${product.id}/upload`}>Import reviews</Link><Link to={`/compare?left=${encodeURIComponent(product.id)}`}>Compare</Link></div></div><Link className="button button-secondary product-open" to={`/products/${product.id}`}>View insights <Icon name="arrow" /></Link></section>)}
      {products?.length === 0 && <EmptyState title="Start your first shortlist">Create a product above, then paste or import reviews. Your saved findings will stay together here.</EmptyState>}
      {!!products?.length && visible?.length === 0 && <EmptyState title="No matching products">Try a different name or clear the search to see your collection.</EmptyState>}
    </div>
    <p className="collection-footnote"><Icon name="quote" /> Every finding starts with a review. Your saved sample may differ from a retailer’s full review history.</p>
  </>
}

type ProductView = 'overview' | 'reviews' | 'advanced' | 'settings'

export function ProductDetailPage({ view = 'overview' }: { view?: ProductView }) {
  const { id } = useParams()
  return <ProductDetail key={`${id}:${view}`} view={view} />
}

function ProductDetail({ view }: { view: ProductView }) {
  const navigate = useNavigate()
  const { id } = useParams()
  const { data, error, refresh } = useDetail(id)
  const [evidence, setEvidence] = useState<{ review: Analysis; tagIndex: number } | null>(null)
  const [regeneration, setRegeneration] = useState<Job | null>(null)
  const [regenerationError, setRegenerationError] = useState('')
  const [regenerationBusy, setRegenerationBusy] = useState(false)
  const regenerationId = regeneration?.id
  const regenerationStatus = regeneration?.status
  const regenerationActive = !!regenerationId && !!regenerationStatus && !['completed', 'completed_with_errors', 'failed'].includes(regenerationStatus)
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
  const savedCount = data?.review_counts ? Object.values(data.review_counts).reduce((sum, count) => sum + count, 0) : data?.insights.review_count ?? 0
  const onEvidence = (review: Analysis, tagIndex: number) => setEvidence({ review, tagIndex })
  return <>
    <Link className="back-link" to="/products">← Saved products</Link>
    <PageHeader eyebrow="A closer look" title={data?.product.name ?? 'Product'} description="The strengths, the tradeoffs, and the reviews behind them." actions={<><Link className="button button-secondary" to={`/products/${id}/review`}><Icon name="plus" /> Analyze a review</Link>{data && savedCount > 0 && <Button onClick={() => void regenerate()} disabled={regenerationBusy || regenerationActive}>{regenerationBusy || regenerationActive ? 'Analyzing saved reviews…' : 'Analyze saved reviews'}</Button>}</>} />
    <ErrorMessage error={error} />
    {!data && !error && <p role="status">Loading saved evidence…</p>}
    {data && <>
      <div className="product-context"><StatusBadge>{data.backend === 'transformer' ? 'Trained DistilBERT' : 'Heuristic demo'}</StatusBadge><span>{savedCount} saved review{savedCount === 1 ? '' : 's'} · {data.insights.review_count} in published analysis</span><Link to={`/products/${id}/upload`}>Import reviews</Link></div>
      <nav className="product-tabs" aria-label="Product views"><NavLink end to={`/products/${id}`}>Overview</NavLink><NavLink to={`/products/${id}/reviews`}>Review evidence</NavLink><Link to={`/compare?left=${encodeURIComponent(data.product.id)}`}>Compare</Link><NavLink to={`/products/${id}/advanced`}>Advanced tools</NavLink><NavLink to={`/products/${id}/settings`}>Data settings</NavLink></nav>
      {data.stale && <section className="alert alert-warning stale-insights"><div><strong>{data.insights.review_count ? 'Showing the last published analysis' : 'Saved reviews are waiting for analysis'}</strong><p>{savedCount} reviews saved. Use Analyze saved reviews to update the findings below.</p></div></section>}
      {regeneration && <p role="status">Analysis {regeneration.status.replaceAll('_', ' ')} · {regeneration.completed_rows} of {regeneration.total_rows} reviews analyzed{regeneration.failed_rows > 0 ? ` · ${regeneration.failed_rows} failed` : ''}</p>}
      <ErrorMessage error={regenerationError} />
      {view === 'overview' && <><ProductInsights data={data} onEvidence={onEvidence} />{data.insights.top_tags.length > 0 && <section className="supported-tags"><h2>Supported product tags</h2><div>{data.insights.top_tags.map(tag => <StatusBadge key={tag.aspect_id}>{tag.aggregate_tag ?? tag.aspect}</StatusBadge>)}</div><p>Recurring feedback in this saved sample, supported by at least three reviews per feature.</p></section>}<details className="optional-assistant"><summary>Ask about these reviews <span>Optional assistance</span></summary><ProductReviewAssistant key={`ask:${data.snapshot_id}`} productId={data.product.id} snapshotId={data.snapshot_id ?? null} /></details></>}
      {view === 'reviews' && <section aria-labelledby="review-evidence-heading"><div className="section-heading evidence-list-heading"><div><h2 id="review-evidence-heading">Review evidence</h2><p>Original reviews and predictions from this published sample. Select a highlighted phrase to inspect it.</p></div><span className="count-label">{data.reviews.length} reviews</span></div><ReviewResults analyses={data.reviews} onEvidence={onEvidence} />{!data.reviews.length && <EmptyState title="No reviews yet">Analyze a review to populate this product’s insights.</EmptyState>}</section>}
      {view === 'advanced' && <div className="advanced-tools"><div className="section-heading"><div><h2>Review and evaluate</h2><p>Inspect prediction stability and record reviewer decisions. Decisions stay separate from model totals.</p></div></div><EvidenceRobustnessPanel key={`robustness:${data.snapshot_id}`} productId={data.product.id} snapshotId={data.snapshot_id ?? null} /><ReviewQualityPanel key={`quality:${data.snapshot_id}`} productId={data.product.id} snapshotId={data.snapshot_id ?? null} onReview={(reviewId, start, end) => { const review = data.reviews.find(item => item.review.review_id === reviewId); const tagIndex = review?.tags.findIndex(tag => tag.start_char === start && tag.end_char === end) ?? -1; if (review && tagIndex >= 0) setEvidence({ review, tagIndex }) }} /><CorrectionExport productId={data.product.id} />{data.snapshot_id && data.pipeline_version && <ReviewAnnotationWorkspace key={`annotations:${data.snapshot_id}`} productId={data.product.id} snapshotId={data.snapshot_id} />}</div>}
      {view === 'settings' && <><section className="data-settings-heading"><h2>Manage this product’s data</h2><p>Review imported batches or remove saved data. Removing reviews also removes their associated reviewer records.</p><SavedDataControls productId={data.product.id} productName={data.product.name} onCleared={refresh} onDeleted={() => navigate('/products')} /></section><SavedImportsPanel key={`imports:${data.snapshot_id}`} productId={data.product.id} onRemoved={refresh} /></>}
      <AspectEvidenceDrawer evidence={evidence && data.reviews.includes(evidence.review) ? evidence : null} onClose={() => setEvidence(null)} savedContext={data.snapshot_id && data.pipeline_version ? { productId: data.product.id, snapshotId: data.snapshot_id } : undefined} />
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
export function ReviewPage() { const { id } = useParams(); return <ReviewForm key={id} /> }
export function UploadPage() { const { id } = useParams(); return <ReviewForm key={id} importing /> }

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
