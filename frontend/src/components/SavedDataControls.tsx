import { useEffect, useRef, useState } from 'react'
import { Button } from './Button'
import { Dialog } from './Dialog'
import './SavedDataControls.css'

type Props = {
  productId: string
  productName: string
  onCleared?: () => void
  onDeleted?: () => void
}

type Action = 'clear' | 'delete'

function responseMessage(value: unknown, fallback: string): string {
  if (value && typeof value === 'object') {
    const body = value as { detail?: unknown; message?: unknown; error?: unknown }
    for (const candidate of [body.detail, body.message, body.error]) {
      if (typeof candidate === 'string' && candidate.trim()) return candidate
      if (Array.isArray(candidate)) {
        const message = candidate.map((item) => typeof item === 'object' && item && 'msg' in item ? String(item.msg) : String(item)).join(', ')
        if (message) return message
      }
    }
  }
  return fallback
}

function clearLocalReviewState(productId: string) {
  const ids = new Set([productId])
  // Older demo routes used this readable alias before products received UUIDs.
  if (productId === 'demo-laptop' || productId === '00000000-0000-4000-8000-000000000001') ids.add('demo-laptop')
  try {
    for (const id of ids) {
      localStorage.removeItem(`review-tag-draft:${id}:review`)
      localStorage.removeItem(`review-tag-draft:${id}:import`)
      localStorage.removeItem(`review-tag-job:${id}:review`)
      localStorage.removeItem(`review-tag-job:${id}:import`)
    }
  } catch {
    // Storage may be unavailable; server deletion has still succeeded.
  }
}

export function SavedDataControls({ productId, productName, onCleared, onDeleted }: Props) {
  const [action, setAction] = useState<Action | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const mounted = useRef(true)
  const busyRef = useRef(false)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  const closeDialog = () => {
    if (busyRef.current) return
    setAction(null)
    setError('')
    setSuccess('')
  }

  const begin = (nextAction: Action) => {
    setError('')
    setSuccess('')
    setAction(nextAction)
  }

  const confirm = async () => {
    if (!action || busyRef.current) return
    busyRef.current = true
    setBusy(true)
    setError('')
    const path = action === 'clear'
      ? `/api/demo/products/${encodeURIComponent(productId)}/saved-data`
      : `/api/demo/products/${encodeURIComponent(productId)}`
    try {
      const response = await fetch(path, { method: 'DELETE', headers: { Accept: 'application/json' } })
      let body: unknown = null
      try { body = await response.json() } catch { /* Some successful DELETE responses have no body. */ }
      if (!response.ok) throw new Error(responseMessage(body, `Request failed (${response.status}). Please try again.`))
      clearLocalReviewState(productId)
      if (!mounted.current) return
      if (action === 'clear') {
        setSuccess(`Saved data for ${productName} has been cleared.`)
        onCleared?.()
      } else {
        setAction(null)
        onDeleted?.()
      }
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause.message : 'Could not complete this request. Please try again.')
    } finally {
      busyRef.current = false
      if (mounted.current) setBusy(false)
    }
  }

  const clearing = action === 'clear'

  return (
    <section className="saved-data-controls" aria-label="Saved data controls">
      <button type="button" className="saved-data-link" onClick={() => begin('clear')}>Clear saved reviews</button>
      <span className="saved-data-separator" aria-hidden="true">·</span>
      <button type="button" className="saved-data-link saved-data-link--delete" onClick={() => begin('delete')}>Delete product</button>

      <Dialog open={action !== null} onClose={closeDialog} title={clearing ? 'Clear saved reviews?' : 'Delete product?'}>
        <div className="saved-data-dialog">
          <p>
            {clearing
              ? `This removes all saved reviews, imported content, insights, previews, and import job history for ${productName}. The product will remain.`
              : `This cannot be undone. It permanently deletes ${productName} and all of its saved reviews, imported content, insights, previews, and import job history.`}
          </p>
          <p className="saved-data-file-note">Original files you uploaded or downloaded on your device are not deleted.</p>
          {success && <p className="saved-data-message saved-data-message--success" role="status">{success}</p>}
          {error && <p className="saved-data-message saved-data-message--error" role="alert">{error}</p>}
          <div className="saved-data-actions">
            <Button variant="secondary" onClick={closeDialog} disabled={busy}>{success ? 'Close' : 'Cancel'}</Button>
            {!success && <Button className={clearing ? '' : 'saved-data-confirm--delete'} onClick={confirm} busy={busy}>
              {busy ? (clearing ? 'Clearing…' : 'Deleting…') : (clearing ? 'Clear saved data' : 'Delete product permanently')}
            </Button>}
          </div>
        </div>
      </Dialog>
    </section>
  )
}
