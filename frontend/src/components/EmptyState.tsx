import type { ReactNode } from 'react'

type Props = { title: string; children: ReactNode; action?: ReactNode }

export function EmptyState({ title, children, action }: Props) {
  return (
    <section className="empty-state" aria-labelledby="empty-state-title">
      <span className="empty-state-mark" aria-hidden="true">—</span>
      <h2 id="empty-state-title">{title}</h2>
      <p>{children}</p>
      {action && <div className="empty-state-action">{action}</div>}
    </section>
  )
}
