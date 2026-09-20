import { Link, useParams } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { StatusBadge } from '../components/StatusBadge'

export function ProductsPage() {
  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Products"
        description="Choose a product to review customer feedback and its detected themes."
      />
      <EmptyState title="No products yet">
        Import a review file to create your first product workspace. Product data will appear here when the API is connected.
      </EmptyState>
    </>
  )
}

export function ProductDetailPage() {
  const { id } = useParams()
  return (
    <>
      <PageHeader eyebrow="Product" title={`Product ${id}`} description="Review themes and sentiment will appear here." />
      <EmptyState title="No review analysis available">
        Add reviews to this product to see supported themes and sentiment summaries.
      </EmptyState>
    </>
  )
}

export function ReviewPage() {
  const { id } = useParams()
  return (
    <>
      <PageHeader eyebrow={`Product ${id}`} title="Review analyzer" description="Inspect review evidence and model suggestions." />
      <EmptyState title="Select a review session">
        Review sessions will be available here after product data is connected.
      </EmptyState>
    </>
  )
}

export function UploadPage() {
  const { id } = useParams()
  return (
    <>
      <PageHeader eyebrow={`Product ${id}`} title="Import reviews" description="Prepare a review file for analysis." />
      <EmptyState title="No import in progress">
        File validation and import status will appear here when the import service is connected.
      </EmptyState>
    </>
  )
}

export function ModelsPage() {
  return (
    <>
      <PageHeader eyebrow="System" title="Model metrics" description="Current model quality and evaluation status." />
      <section className="content-section" aria-labelledby="metrics-status-title">
        <div className="section-heading">
          <div>
            <h2 id="metrics-status-title">Evaluation status</h2>
            <p>Metrics are not connected to an approved evaluation report yet.</p>
          </div>
          <StatusBadge>Not available</StatusBadge>
        </div>
        <p className="muted-copy">No scores are shown until the application can load verified evaluation evidence.</p>
      </section>
    </>
  )
}

export function NotFoundPage() {
  return (
    <>
      <PageHeader eyebrow="Page not found" title="That address isn’t available" description="The page may have moved or the link may be incomplete." />
      <p><Link className="text-link" to="/products">Return to products</Link></p>
    </>
  )
}
