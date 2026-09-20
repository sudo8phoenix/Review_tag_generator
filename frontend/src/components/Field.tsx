import type { InputHTMLAttributes } from 'react'

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  id: string
  label: string
  hint?: string
  error?: string
}

export function Field({ id, label, hint, error, className = '', ...props }: Props) {
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [hintId, errorId, props['aria-describedby']].filter(Boolean).join(' ') || undefined
  return (
    <div className={`field ${className}`}>
      <label htmlFor={id}>{label}</label>
      {hint && <p id={hintId} className="field-hint">{hint}</p>}
      <input id={id} aria-invalid={Boolean(error)} aria-describedby={describedBy} {...props} />
      {error && <p id={errorId} className="field-error">{error}</p>}
    </div>
  )
}
