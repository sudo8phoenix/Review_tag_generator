import { useEffect, useState } from 'react'
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
    <strong>{stats.review_count} reviews</strong>
    <span><i className="comparison-dot positive" />{stats.positive} positive · {share(stats.positive_share)}</span>
    <span><i className="comparison-dot neutral" />{stats.neutral} neutral · {share(stats.neutral_share)}</span>
    <span><i className="comparison-dot negative" />{stats.negative} negative · {share(stats.negative_share)}</span>
  </span>
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
    <div className="section-heading"><div><h2 id="comparison-title">Compare observed feedback</h2>
      <p>Compare predicted aspect sentiment in saved reviews. This does not measure objective product quality.</p></div></div>
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
      <div className="comparison-provenance">
        {[comparison.left, comparison.right].map(side => <div key={side.product.id ?? side.product.name}>
          <strong>{side.product.name ?? 'Product'}</strong>
          <span>{side.review_count} saved reviews · revision {side.data_revision ?? 'unknown'}</span>
          <span>Snapshot {side.snapshot_id ?? 'not published'} · {side.stale ? 'stale' : 'current'}</span>
          <span>Pipeline {side.pipeline_version ?? 'unknown'}</span>
        </div>)}
      </div>
      {(comparison.left.stale || comparison.right.stale) && <p className="comparison-note warning">At least one snapshot is stale and may exclude newer reviews.</p>}
      {comparison.pipeline_version_mismatch && <p className="comparison-note warning">Pipeline versions differ, so directional comparisons are withheld.</p>}
      <div className="table-scroll comparison-table" tabIndex={0} role="region" aria-label="Product comparison rows, scrollable">
        <table><caption>Canonical aspect feedback. At least {comparison.minimum_evidence_reviews} supporting reviews per product are required.</caption>
          <thead><tr><th scope="col">Aspect</th><th scope="col">{comparison.left.product.name ?? 'Left product'}</th><th scope="col">{comparison.right.product.name ?? 'Right product'}</th><th scope="col">Observed balance difference</th></tr></thead>
          <tbody>{comparison.rows.length === 0
            ? <tr><td colSpan={4}>No canonical aspects appear in either saved snapshot.</td></tr>
            : comparison.rows.map(row => <tr key={row.aspect_id}>
              <th scope="row">{row.aspect}</th><td>{sideStats(row.left)}</td><td>{sideStats(row.right)}</td>
              <td><strong className={`comparison-signal ${row.signal}`}>
                {row.signal === 'left' ? 'Left higher' : row.signal === 'right' ? 'Right higher' : row.signal === 'tie' ? 'Tie' : 'Insufficient evidence'}
              </strong><span className="comparison-difference">{row.favorable_share_difference == null ? '—' : `${row.favorable_share_difference > 0 ? '+' : ''}${(row.favorable_share_difference * 100).toFixed(0)} percentage points`}</span>
                {(row.evidence_gap.left || row.evidence_gap.right) && <span className="comparison-gap">Below support threshold: {[row.evidence_gap.left ? comparison.left.product.name : null, row.evidence_gap.right ? comparison.right.product.name : null].filter(Boolean).join(', ')}</span>}
              </td>
            </tr>)}</tbody>
        </table>
      </div>
      <p className="comparison-note">{comparison.interpretation} Review sampling, timing, and model labeling can change the observed distribution.</p>
    </div>}
  </section>
}
