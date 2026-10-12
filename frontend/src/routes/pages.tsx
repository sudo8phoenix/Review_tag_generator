import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Analysis, type Detail, type Product } from '../api'
import { Button } from '../components/Button'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { SentimentBadge } from '../components/SentimentBadge'
import { StatusBadge } from '../components/StatusBadge'

function ErrorMessage({ error }: { error: string }) {
  return error ? <p className="alert alert-error" role="alert">{error}</p> : null
}

function useDetail(id: string | undefined) {
  const [data, setData] = useState<Detail | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    api<Detail>(`/demo/products/${id}`).then(value => { if (active) setData(value) }).catch(reason => { if (active) setError(String(reason.message)) })
    return () => { active = false }
  }, [id])
  return { data, error }
}

function ReviewResults({ analyses }: { analyses: Analysis[] }) {
  return <div className="demo-stack">{analyses.map(analysis => <article className="content-section" key={analysis.review.review_id}>
    <p className="review-quote">“{analysis.review.review_text}”</p>
    {analysis.tags.length ? <div className="table-scroll"><table><thead><tr><th>Aspect evidence</th><th>Normalized aspect</th><th>Sentiment</th><th>Generated tag</th><th>Model score</th></tr></thead>
      <tbody>{analysis.tags.map((tag, index) => <tr key={index}><td>{tag.raw_aspect}</td><td>{tag.normalized_aspect ?? 'Unknown'}</td><td><SentimentBadge sentiment={tag.sentiment} /></td><td>{tag.tag ?? 'No canonical tag'}</td><td>{(tag.confidence * 100).toFixed(1)}%</td></tr>)}</tbody></table></div>
      : <p>No aspects detected in this review. Try mentioning a display, battery, keyboard, or another product feature.</p>}
  </article>)}</div>
}

export function ProductsPage() {
  const [products, setProducts] = useState<Product[] | null>(null)
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { let active = true; api<Product[]>('/demo/products').then(value => { if (active) setProducts(value) }).catch(reason => { if (active) setError(reason.message) }); return () => { active = false } }, [])
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
        <div className="demo-actions"><Link className="button button-primary" to={`/products/${product.id}`}>View insights</Link><Link className="button button-secondary" to={`/products/${product.id}/review`}>Analyze review</Link><Link className="text-link" to={`/products/${product.id}/upload`}>Import reviews</Link></div></section>)}
      {products?.length === 0 && <EmptyState title="No products yet">Create a product above to start analyzing reviews.</EmptyState>}
    </div>
  </>
}

export function ProductDetailPage() {
  const { id } = useParams(); const { data, error } = useDetail(id)
  return <><PageHeader eyebrow="Product insights" title={data?.product.name ?? 'Product'} description="Saved review evidence, generated tags, and recurring customer opinions." /><ErrorMessage error={error} />
    {!data && !error && <p role="status">Loading insights…</p>}
    {data && <><div className="demo-actions"><Link className="button button-primary" to={`/products/${id}/review`}>Analyze a review</Link><Link className="button button-secondary" to={`/products/${id}/upload`}>Import reviews</Link><StatusBadge>{data.backend === 'transformer' ? 'Trained DistilBERT' : 'Heuristic demo'}</StatusBadge></div>
      <div className="demo-stats"><section><strong>{data.insights.review_count}</strong><span>Saved reviews</span></section>{['positive', 'neutral', 'negative'].map(sentiment => <section key={sentiment}><strong>{data.insights.sentiment_distribution[sentiment] ?? 0}</strong><span>{sentiment} aspect votes</span></section>)}</div>
      <section className="content-section"><h2>Supported product tags</h2><p className="field-hint">Tags require at least three supporting reviews. Add more feedback to establish recurring themes.</p><div className="demo-actions">{data.insights.top_tags.map(tag => <StatusBadge key={tag.aspect_id}>{tag.aggregate_tag ?? tag.aspect}</StatusBadge>)}{!data.insights.top_tags.length && <p>No tags have enough evidence yet.</p>}</div></section>
      {!!data.insights.aspects.length && <section className="content-section demo-spaced"><h2>Aspect summary</h2><div className="table-scroll"><table><thead><tr><th>Aspect</th><th>Review support</th><th>Classification</th></tr></thead><tbody>{data.insights.aspects.map(aspect => <tr key={aspect.aspect_id}><td>{aspect.aspect}</td><td>{aspect.review_count}</td><td>{aspect.classification.replaceAll('_', ' ')}</td></tr>)}</tbody></table></div></section>}
      <h2 className="demo-spaced">Review evidence</h2><ReviewResults analyses={data.reviews} />{!data.reviews.length && <EmptyState title="No reviews yet">Analyze a review to populate this product’s insights.</EmptyState>}
    </>}
  </>
}

function ReviewForm({ importing = false }: { importing?: boolean }) {
  const { id } = useParams()
  const [text, setText] = useState(importing ? '' : 'Amazing display but terrible battery.')
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setAnalyses([])
    try { const result = await api<{ analyses: Analysis[] }>(`/demo/products/${id}/reviews`, { reviews: importing ? text.split(/\r?\n/).filter(line => line.trim()) : [text] }); setAnalyses(result.analyses) }
    catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }
  return <><PageHeader eyebrow="Product workspace" title={importing ? 'Import reviews' : 'Review analyzer'} description={importing ? 'Paste one review per line or load a text file. Up to 100 reviews per batch.' : 'Extract product aspects, classify their sentiment, and generate tags using the local model.'} />
    <p><Link className="text-link" to={`/products/${id}`}>← Product insights</Link></p><ErrorMessage error={error} />
    <form className="content-section demo-form" onSubmit={submit}>
      {importing && <><label htmlFor="review-file">Load a text file (.txt)</label><input id="review-file" type="file" accept=".txt,text/plain" disabled={busy} onChange={async event => { const file = event.target.files?.[0]; if (file) { if (file.size > 1048576) { setError('Please use a text file smaller than 1 MB.'); return } try { setText(await file.text()); setError('') } catch { setError('Unable to read the file. Please paste the reviews instead.') } } }} /></>}
      <label htmlFor="review-text">{importing ? 'Reviews — one per line' : 'Customer review'}</label>
      <textarea id="review-text" rows={importing ? 8 : 5} value={text} onChange={event => setText(event.target.value)} required disabled={busy} maxLength={importing ? 1000000 : 10000} />
      <div className="demo-actions"><Button busy={busy} disabled={!text.trim()}>{busy ? 'Analyzing…' : importing ? 'Import and analyze' : 'Analyze and save review'}</Button>{!importing && <Button type="button" variant="secondary" disabled={busy} onClick={() => setText('The keyboard is comfortable and the performance is excellent, but the speakers are poor.')}>Try another example</Button>}</div>
      <p className="field-hint">Reviews are saved locally. Model scores are uncalibrated confidence estimates.</p>
    </form>
    <div aria-live="polite">{busy && <p role="status">Running aspect extraction and sentiment classification…</p>}{analyses.length > 0 && <><p className="alert alert-success">{analyses.length} review{analyses.length === 1 ? '' : 's'} analyzed and saved · {analyses[0]?.backend === 'transformer' ? 'Trained DistilBERT' : 'Heuristic demo'}</p><ReviewResults analyses={analyses} /><p><Link className="text-link" to={`/products/${id}`}>View updated product insights →</Link></p></>}</div>
  </>
}
export function ReviewPage() { return <ReviewForm /> }
export function UploadPage() { return <ReviewForm importing /> }

export function ModelsPage() {
  const [health, setHealth] = useState<{ backend: string; storage: string } | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { let active = true; api<{ backend: string; storage: string }>('/health').then(value => { if (active) setHealth(value) }).catch(reason => { if (active) setError(reason.message) }); return () => { active = false } }, [])
  return <><PageHeader eyebrow="System" title="Model metrics" description="Inference backend and evaluation status." /><ErrorMessage error={error} /><section className="content-section"><h2>Inference status</h2>{health ? <><StatusBadge tone="success">{health.backend === 'transformer' ? 'Trained DistilBERT models loaded' : 'Heuristic demo mode'}</StatusBadge><p className="muted-copy">Storage: {health.storage}. Aspect extraction and sentiment classification run on this computer.</p></> : <p>Checking backend…</p>}<h2>Evaluation status</h2><p>No evaluation scores are displayed until a verified report is connected.</p></section></>
}

export function NotFoundPage() {
  return <><PageHeader eyebrow="Page not found" title="That address isn’t available" description="The page may have moved or the link may be incomplete." /><p><Link className="text-link" to="/products">Return to products</Link></p></>
}
