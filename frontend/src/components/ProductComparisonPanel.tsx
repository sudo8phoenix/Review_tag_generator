import { useEffect, useRef, useState } from 'react'
import { api, type Product } from '../api'
import './ProductComparisonPanel.css'

type Side = {
  product: { id: string | null; name: string | null }
  review_count: number
  snapshot_id: string | null
  pipeline_version: string | null
  aggregate_version: string | null
  data_revision: number | null
  stale: boolean
}
type AspectStats = {
  review_count: number
  positive: number
  neutral: number
  negative: number
  positive_share: number
  neutral_share: number
  negative_share: number
  classification: string | null
}
type Comparison = {
  left: Side
  right: Side
  minimum_evidence_reviews: number
  pipeline_version_mismatch: boolean
  interpretation: string
  rows: {
    aspect_id: string
    aspect: string
    left: AspectStats | null
    right: AspectStats | null
    evidence_gap: { left: boolean; right: boolean; pipeline_version_mismatch: boolean }
    favorable_share_difference: number | null
    signal: 'left' | 'right' | 'tie' | 'insufficient_evidence'
  }[]
}

type Props = { productId: string }

function share(value: number | null | undefined) {
  return value == null ? '—' : `${(value * 100).toFixed(0)}%`
}

function sideStats(stats: AspectStats | null) {
  if (!stats) return <span className="comparison-missing">No saved votes</span>
  return <span className="comparison-counts">
    <strong>{stats.review_count} {stats.review_count === 1 ? 'review' : 'reviews'}</strong>
    <span><i className="comparison-dot positive" />{stats.positive} positive · {share(stats.positive_share)}</span>
    <span><i className="comparison-dot neutral" />{stats.neutral} neutral · {share(stats.neutral_share)}</span>
    <span><i className="comparison-dot negative" />{stats.negative} negative · {share(stats.negative_share)}</span>
  </span>
}

type Explanation = { summary: string; trade_off: string; snapshots: (string | null)[]; model: string }

function ComparisonSummary({ comparison }: { comparison: Comparison }) {
  const [explanation, setExplanation] = useState<Explanation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const active = useRef(true)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  const supported = comparison.rows.filter(row => row.signal !== 'insufficient_evidence')
  const leftLeads = supported.filter(row => row.signal === 'left')
  const rightLeads = supported.filter(row => row.signal === 'right')
  const blocked = comparison.left.stale || comparison.right.stale || comparison.pipeline_version_mismatch
  const winner = blocked || leftLeads.length === rightLeads.length ? null : leftLeads.length > rightLeads.length ? comparison.left : comparison.right
  const title = blocked ? 'Refresh the analyses before choosing' : !supported.length ? 'More review evidence is needed' : winner ? `${winner.product.name} looks stronger in these reviews` : 'No clear winner in these reviews'
  async function explain() {
    setBusy(true)
    setError('')
    try {
      const result = await api<Explanation>(`/demo/products/${comparison.left.product.id}/compare/${comparison.right.product.id}/summary`, {})
      if (result.snapshots[0] !== comparison.left.snapshot_id || result.snapshots[1] !== comparison.right.snapshot_id) throw new Error('The reviews changed. Compare the products again for a fresh summary.')
      if (active.current) setExplanation(result)
    } catch (reason) { if (active.current) setError((reason as Error).message) }
    finally { if (active.current) setBusy(false) }
  }
  return <div className="comparison-verdict">
    <span className="section-number">THE REVIEW VERDICT</span>
    <h3>{title}</h3>
    <p>{blocked ? 'One or both analyses are out of date or use different model versions.' : supported.length ? `Based on ${comparison.left.review_count} and ${comparison.right.review_count} saved reviews, with enough shared evidence for ${supported.length} features. Each feature counts equally; your priorities may differ.` : `Each feature needs at least ${comparison.minimum_evidence_reviews} supporting reviews for both products.`}</p>
    {!blocked && supported.length > 0 && <div className="comparison-takeaways">
      {[{ side: comparison.left, leads: leftLeads }, { side: comparison.right, leads: rightLeads }].map(({ side, leads }) => <div key={side.product.id}>
        <h4>{side.product.name}</h4>
        <p>{leads.length ? `Stronger feedback for ${leads.map(row => row.aspect.toLowerCase()).join(', ')}.` : 'No clear feature advantage in the shared evidence.'}</p>
        {leads.slice(0, 3).map(row => <span className="comparison-reason" key={row.aspect_id}>{row.aspect}: {row.left?.positive} of {row.left?.review_count} positive for {comparison.left.product.name}; {row.right?.positive} of {row.right?.review_count} for {comparison.right.product.name}.</span>)}
      </div>)}
    </div>}
    <p className="comparison-note">This reflects sampled review feedback. Price, specifications, and features with limited evidence are not part of the verdict.</p>
    {!blocked && supported.length > 0 && <button className="button button-secondary" disabled={busy} aria-busy={busy} onClick={() => void explain()}>{busy ? 'Writing the AI explanation…' : explanation ? 'Regenerate AI explanation' : 'Explain this comparison with AI'}</button>}
    {busy && <p role="status" className="comparison-note">Reading the shared feature evidence. This may take a minute.</p>}
    {error && <p role="alert" className="alert alert-error">{error} The review verdict above is still available.</p>}
    {explanation && <div className="comparison-ai" aria-live="polite"><span className="section-number">AI EXPLANATION</span><p>{explanation.summary}</p><p>{explanation.trade_off}</p><span className="comparison-note">Generated from the shared feature evidence · {explanation.model}</span></div>}
  </div>
}

function FeatureTakeaways({ comparison }: { comparison: Comparison }) {
  const [result, setResult] = useState<{ features: { aspect_id: string; takeaway: string }[]; snapshots: (string | null)[] } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const active = useRef(true)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  async function generate() {
    setBusy(true)
    setError('')
    try {
      const value = await api<NonNullable<typeof result>>(`/demo/products/${comparison.left.product.id}/compare/${comparison.right.product.id}/takeaways`, {})
      if (value.snapshots[0] !== comparison.left.snapshot_id || value.snapshots[1] !== comparison.right.snapshot_id) throw new Error('Reviews changed. Compare the products again to refresh the evidence.')
      if (active.current) setResult(value)
    } catch (reason) { if (active.current) setError((reason as Error).message) }
    finally { if (active.current) setBusy(false) }
  }
  return <>
    <button className="button button-secondary" disabled={busy || !comparison.rows.length} aria-busy={busy} onClick={() => void generate()}>{busy ? 'Writing AI feature takeaways…' : result ? 'Regenerate AI feature takeaways' : 'Generate AI feature takeaways'}</button>
    {busy && <p role="status" className="comparison-note">The AI is interpreting each feature’s review evidence. This may take a minute.</p>}
    {error && <p className="alert alert-error" role="alert">{error}</p>}
    <div className="table-scroll comparison-table" tabIndex={0} role="region" aria-label="Product comparison rows, scrollable">
      <table><caption>Saved feedback by feature. AI takeaways describe these review samples and may be imperfect.</caption>
        <thead><tr><th scope="col">Feature</th><th scope="col">{comparison.left.product.name}</th><th scope="col">{comparison.right.product.name}</th><th scope="col">AI takeaway</th></tr></thead>
        <tbody>{comparison.rows.map(row => <tr key={row.aspect_id}>
          <th scope="row">{row.aspect}</th><td>{sideStats(row.left)}</td><td>{sideStats(row.right)}</td>
          <td className="comparison-ai-takeaway">{result?.features.find(feature => feature.aspect_id === row.aspect_id)?.takeaway ?? 'Generate AI feature takeaways above to see an interpretation of these reviews.'}</td>
        </tr>)}</tbody>
      </table>
    </div>
  </>
}

export function ProductComparisonPanel({ productId }: Props) {
  const [products, setProducts] = useState<Product[] | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [comparison, setComparison] = useState<Comparison | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    setProducts(null)
    setComparison(null)
    setError('')
    api<Product[]>('/demo/products').then(value => {
      if (active) {
        setProducts(value)
        setSelectedId(current => value.some(item => item.id === current && current !== productId)
          ? current
          : value.find(item => item.id !== productId)?.id ?? '')
      }
    }).catch(reason => { if (active) setError((reason as Error).message) })
    return () => { active = false }
  }, [productId])

  async function compare() {
    if (!selectedId || selectedId === productId) return
    setBusy(true)
    setError('')
    setComparison(null)
    try {
      setComparison(await api<Comparison>(`/demo/products/${encodeURIComponent(productId)}/compare/${encodeURIComponent(selectedId)}`))
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const available = products?.filter(product => product.id !== productId) ?? []
  return <section className="content-section product-comparison" aria-labelledby="comparison-title">
    <div className="section-heading"><div><h2 id="comparison-title">Which laptop fits you better?</h2>
      <p>Get a clear recommendation from the reviews you saved.</p></div></div>
    {products === null && !error && <p role="status">Loading available products…</p>}
    {products && available.length === 0 && <p className="comparison-note">Create another product and add reviews before comparing feedback.</p>}
    {available.length > 0 && <div className="comparison-controls">
      <label htmlFor="comparison-product">Compare with</label>
      <select id="comparison-product" disabled={busy} value={selectedId} onChange={event => { setSelectedId(event.target.value); setComparison(null); setError('') }}>
        {available.map(product => <option value={product.id} key={product.id}>{product.name} · {product.review_count} reviews</option>)}
      </select>
      <button className="button button-secondary" type="button" onClick={() => void compare()} disabled={!selectedId || busy} aria-busy={busy}>
        {busy ? 'Comparing…' : 'Compare products'}
      </button>
    </div>}
    {error && <p className="alert alert-error" role="alert">{error}</p>}
    {comparison && <div className="comparison-result" aria-live="polite">
      <ComparisonSummary comparison={comparison} />
      <div className="comparison-provenance">
        {[comparison.left, comparison.right].map(side => <div key={side.product.id ?? side.product.name}>
          <strong>{side.product.name ?? 'Product'}</strong>
          <span>{side.review_count} saved reviews · revision {side.data_revision ?? 'unknown'}</span>
          <span>{side.stale ? 'Earlier analysis · newer reviews may be missing' : 'Published analysis'}</span>
        </div>)}
      </div>
      <details className="comparison-provenance-details"><summary>Analysis provenance</summary>{[comparison.left, comparison.right].map(side => <p key={side.product.id ?? side.product.name}><strong>{side.product.name}</strong><br />Snapshot {side.snapshot_id ?? 'not published'}<br />Pipeline {side.pipeline_version ?? 'unknown'}</p>)}</details>
      {(comparison.left.stale || comparison.right.stale) && <p className="comparison-note warning">At least one snapshot is stale and may exclude newer reviews.</p>}
      {comparison.pipeline_version_mismatch && <p className="comparison-note warning">Pipeline versions differ, so directional comparisons are withheld.</p>}
      <details className="comparison-evidence"><summary>Explore the detailed feature evidence</summary>
      <FeatureTakeaways comparison={comparison} />
      </details>
      <p className="comparison-note">{comparison.interpretation} Review sampling, timing, and model labeling can change the observed distribution.</p>
    </div>}
  </section>
}
