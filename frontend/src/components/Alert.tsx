import type { ReactNode } from 'react'

type Props = { title: string; children: ReactNode; tone?: 'info' | 'success' | 'warning' | 'error' }

export function Alert({ title, children, tone = 'info' }: Props) {
  return (
    <div className={`alert alert-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <strong>{title}</strong>
      <div>{children}</div>
    </div>
  )
}
