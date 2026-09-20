import type { ReactNode } from 'react'

type Props = { children: ReactNode; tone?: 'neutral' | 'success' | 'warning' | 'error' }

export function StatusBadge({ children, tone = 'neutral' }: Props) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}
