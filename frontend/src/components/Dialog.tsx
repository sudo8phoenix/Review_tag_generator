import { useEffect, useId, useRef, type ReactNode } from 'react'
import { Button } from './Button'

type Props = {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  variant?: 'dialog' | 'drawer'
}

export function Dialog({ open, onClose, title, children, variant = 'dialog' }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const priorFocus = useRef<HTMLElement | null>(null)
  const titleId = useId()

  useEffect(() => {
    const element = ref.current
    if (!element) return
    if (open && !element.open) {
      priorFocus.current = document.activeElement as HTMLElement | null
      element.showModal()
    } else if (!open && element.open) {
      element.close()
    }
  }, [open])

  return (
    <dialog
      ref={ref}
      className={`app-dialog ${variant === 'drawer' ? 'app-drawer' : ''}`}
      aria-labelledby={titleId}
      onCancel={(event) => { event.preventDefault(); onClose() }}
      onClose={() => { onClose(); priorFocus.current?.focus() }}
    >
      <div className="dialog-heading">
        <h2 id={titleId}>{title}</h2>
        <Button variant="quiet" onClick={onClose} aria-label="Close dialog">Close</Button>
      </div>
      <div className="dialog-content">{children}</div>
    </dialog>
  )
}
