import type { ButtonHTMLAttributes } from 'react'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'quiet'
  busy?: boolean
}

export function Button({ variant = 'primary', busy = false, disabled, children, className = '', ...props }: Props) {
  return (
    <button className={`button button-${variant} ${className}`} disabled={disabled || busy} aria-busy={busy} {...props}>
      {children}
    </button>
  )
}
