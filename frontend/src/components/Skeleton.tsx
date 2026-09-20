type Props = { lines?: number; label?: string }

export function Skeleton({ lines = 3, label = 'Loading content' }: Props) {
  return (
    <div className="skeleton-group" role="status" aria-label={label}>
      {Array.from({ length: lines }, (_, index) => <span key={index} className="skeleton-line" aria-hidden="true" />)}
      <span className="sr-only">{label}</span>
    </div>
  )
}
