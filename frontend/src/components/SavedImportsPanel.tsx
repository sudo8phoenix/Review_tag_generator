import { useEffect, useRef, useState } from 'react'
import { Button } from './Button'
import { Dialog } from './Dialog'
import './SavedImportsPanel.css'

type SavedImport = {
  id: string
  filename: string | null
  status: string
  total_rows: number
  accepted_rows: number
  completed_rows: number
  created_at: string
}

type Props = { productId: string; onRemoved: () => void }

function messageFrom(value: unknown, fallback: string): string {
  if (value && typeof value === 'object') {
    const detail = (value as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail.trim()) return detail
  }
  return fallback
}

function dateLabel(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function removeMatchingLocalJob(productId: string, importId: string) {
  const ids = new Set([productId])
  if (productId === 'demo-laptop' || productId === '00000000-0000-4000-8000-000000000001') ids.add('demo-laptop')
  try {
    for (const id of ids) {
      for (const prefix of ['review-tag-job', 'review-tag-draft']) {
        const key = `${prefix}:${id}:import`
        const stored = localStorage.getItem(key)
        if (!stored) continue
        let value: unknown
        try { value = JSON.parse(stored) } catch { continue }
        if (!value || typeof value !== 'object') continue
        const record = value as { id?: unknown; job?: { id?: unknown } }
        if (record.job?.id === importId || record.id === importId) localStorage.removeItem(key)
      }
    }
  } catch {
    // Browser storage may be unavailable; saved import removal has still succeeded.
  }
}

export function SavedImportsPanel({ productId, onRemoved }: Props) {
  const [imports, setImports] = useState<SavedImport[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [requestVersion, setRequestVersion] = useState(0)
  const [selected, setSelected] = useState<SavedImport | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [removeError, setRemoveError] = useState('')
  const mounted = useRef(true)
  const busyRef = useRef(false)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setLoadError('')
    fetch(`/api/demo/products/${encodeURIComponent(productId)}/imports`, { signal: controller.signal })
      .then(async response => {
        let body: unknown = null
        try { body = await response.json() } catch { /* Use the fallback error below. */ }
        if (!response.ok) throw new Error(messageFrom(body, `Could not load saved imports (${response.status}).`))
        if (!Array.isArray(body)) throw new Error('The saved imports response was not valid.')
        return body as SavedImport[]
      })
      .then(result => { if (!controller.signal.aborted) setImports(result) })
      .catch(cause => { if (!controller.signal.aborted) setLoadError(cause instanceof Error ? cause.message : 'Could not load saved imports.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [productId, requestVersion])

  const closeDialog = () => {
    if (busyRef.current) return
    setSelected(null)
    setRemoveError('')
  }

  const removeImport = async () => {
    if (!selected || busyRef.current) return
    const current = selected
    busyRef.current = true
    setBusyId(current.id)
    setRemoveError('')
    try {
      const response = await fetch(`/api/demo/products/${encodeURIComponent(productId)}/imports/${encodeURIComponent(current.id)}`, {
        method: 'DELETE',
        headers: { Accept: 'application/json' },
      })
      let body: unknown = null
      try { body = await response.json() } catch { /* Successful DELETE responses may have no body. */ }
      if (!response.ok) throw new Error(messageFrom(body, `Could not remove this import (${response.status}).`))
      removeMatchingLocalJob(productId, current.id)
      if (!mounted.current) return
      setImports(value => value.filter(item => item.id !== current.id))
      setSelected(null)
      onRemoved()
    } catch (cause) {
      if (mounted.current) setRemoveError(cause instanceof Error ? cause.message : 'Could not remove this import. Please try again.')
    } finally {
      busyRef.current = false
      if (mounted.current) setBusyId(null)
    }
  }

  return (
    <section className="saved-imports" aria-labelledby="saved-imports-title">
      <div className="saved-imports__heading">
        <div>
          <h2 id="saved-imports-title">Saved imports</h2>
          <p>Remove an imported batch and its saved reviews and insights.</p>
        </div>
      </div>

      {loading && <p className="saved-imports__state" role="status">Loading saved imports…</p>}
      {!loading && loadError && <div className="saved-imports__error" role="alert"><p>{loadError}</p><Button variant="secondary" onClick={() => setRequestVersion(value => value + 1)}>Try again</Button></div>}
      {!loading && !loadError && imports.length === 0 && <p className="saved-imports__state">No saved import batches for this product.</p>}
      {!loading && !loadError && imports.length > 0 && <ul className="saved-imports__list">
        {imports.map(item => {
          const filename = item.filename || 'Saved batch'
          return <li className="saved-imports__row" key={item.id}>
            <div className="saved-imports__info">
              <strong title={filename}>{filename}</strong>
              <span className="saved-imports__meta">{item.status.replaceAll('_', ' ')} · {item.completed_rows} of {item.accepted_rows} accepted rows completed · {item.total_rows} total rows · {dateLabel(item.created_at)}</span>
            </div>
            <Button variant="quiet" aria-label={`Remove import ${filename}`} onClick={() => { setRemoveError(''); setSelected(item) }}>Remove import</Button>
          </li>
        })}
      </ul>}

      <Dialog open={selected !== null} onClose={closeDialog} title="Remove saved import">
        {selected && <div className="saved-imports__dialog">
          <p>Remove <strong>{selected.filename || 'Saved batch'}</strong> and delete the reviews and insights inserted by this batch? Duplicate reviews saved by other batches will remain.</p>
          {removeError && <p className="saved-imports__error-text" role="alert">{removeError}</p>}
          <div className="saved-imports__actions">
            <Button variant="secondary" onClick={closeDialog} disabled={busyRef.current}>Cancel</Button>
            <Button className="saved-imports__confirm" onClick={removeImport} busy={busyId === selected.id}>Remove saved import</Button>
          </div>
        </div>}
      </Dialog>
    </section>
  )
}
