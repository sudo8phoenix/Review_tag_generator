import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, type Product } from '../api'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { ProductComparisonPanel } from '../components/ProductComparisonPanel'

export function ComparePage() {
  const [products, setProducts] = useState<Product[] | null>(null)
  const [error, setError] = useState('')
  const [params, setParams] = useSearchParams()
  useEffect(() => {
    let active = true
    api<Product[]>('/demo/products').then(value => { if (active) setProducts(value) }).catch(reason => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [])
  const left = products?.find(product => product.id === params.get('left')) ?? products?.[0]
  return <>
    <PageHeader eyebrow="Find your fit" title="Compare your options" description="A closer look at the features, with the evidence side by side." />
    {error && <p className="alert alert-error" role="alert">{error}</p>}
    {!products && !error && <p role="status">Loading saved products…</p>}
    {products && products.length < 2 ? <EmptyState title="Give yourself something to compare">Save at least two products and add reviews to each. <Link className="text-link" to="/products">Open saved products →</Link></EmptyState> : left && <>
      <div className="compare-start"><span className="section-number">01 / CHOOSE YOUR OPTIONS</span><label htmlFor="compare-left">Start with</label><select id="compare-left" value={left.id} onChange={event => setParams({ left: event.target.value })}>{products?.map(product => <option key={product.id} value={product.id}>{product.name} · {product.review_count} saved reviews</option>)}</select><Link className="text-link" to={`/products/${left.id}`}>View this product’s evidence →</Link></div>
      <ProductComparisonPanel key={left.id} productId={left.id} />
    </>}
    <p className="comparison-page-note">These comparisons describe predicted feedback in your saved samples. Review coverage, model versions, and timing can affect the result.</p>
  </>
}
