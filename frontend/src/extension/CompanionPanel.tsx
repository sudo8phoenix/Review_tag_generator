import { useEffect, useRef, useState } from 'react'
import type { Analysis, Detail, Job, PreviewPoll, Product } from '../api'
import { Icon } from '../components/Icon'
import { chromeApi, capturePage, parsePastedReviews, type CapturedReviews } from './browser'
import {
  defaultConnection,
  defaultVercelUrl,
  getApiBaseUrl,
  getWebUrl,
  isValidUrl,
  localRequest,
  LocalServiceError,
  validConnection,
  type Connection,
} from './api'

type Summary = { saved: false; duplicate_reviews: number; insights: Detail['insights'] }
type Pending = { productId: string; productName: string; reviews: string[]; key: string; connection: Connection; jobId?: string }
type Health = { backend: string; worker_ready: boolean }
const settingsKey = 'review-companion-connection-v1'
const pendingKey = 'review-companion-pending-v1'
const terminal = (job: Job) => ['completed', 'completed_with_errors', 'failed'].includes(job.status)
const message = (error: unknown) => error instanceof Error ? error.message : 'The service could not complete this request.'

function isPending(value: unknown): value is Pending {
  if (!value || typeof value !== 'object') return false
  const record = value as Pending
  return typeof record.productId === 'string' && typeof record.productName === 'string' && typeof record.key === 'string' && validConnection(record.connection) && Array.isArray(record.reviews) && record.reviews.length > 0 && record.reviews.length <= 100 && record.reviews.every(text => typeof text === 'string' && text.trim() && Array.from(text).length <= 10000) && (record.jobId === undefined || typeof record.jobId === 'string')
}

export function CompanionPanel() {
  const [connection, setConnection] = useState(defaultConnection)
  const [formMode, setFormMode] = useState<'vercel' | 'local'>(defaultConnection.mode === 'local' ? 'local' : 'vercel')
  const [loaded, setLoaded] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [health, setHealth] = useState<Health | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [productId, setProductId] = useState('')
  const [productName, setProductName] = useState('')
  const [capture, setCapture] = useState<CapturedReviews | null>(null)
  const [pasted, setPasted] = useState('')
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [previewIds, setPreviewIds] = useState<string[]>([])
  const [previewCompleted, setPreviewCompleted] = useState(0)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [pending, setPending] = useState<Pending | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [connectionError, setConnectionError] = useState('')
  const [saved, setSaved] = useState(false)
  const [recoveryMissing, setRecoveryMissing] = useState(false)
  const epoch = useRef(0)
  const captureTab = useRef<number | null>(null)
  const operation = useRef(false)
  const locked = !!busy || previewIds.length > 0 || !!pending

  function clearPreview() {
    epoch.current++
    setPreviewIds([]); setPreviewCompleted(0); setAnalyses([]); setSummary(null); setSaved(false)
  }

  useEffect(() => {
    let active = true
    const chrome = chromeApi()
    if (!chrome) { setError('Open this panel through the built Chrome extension. See Browser companion in the web app for setup.'); return }
    chrome.storage.local.get([settingsKey, pendingKey]).then(values => {
      if (!active) return
      const restored = isPending(values[pendingKey]) ? values[pendingKey] : null
      const nextConnection = restored?.connection ?? (validConnection(values[settingsKey]) ? values[settingsKey] : defaultConnection)
      setConnection(nextConnection)
      setFormMode(nextConnection.mode === 'vercel' || (Boolean(nextConnection.baseUrl) && nextConnection.mode !== 'local') ? 'vercel' : 'local')
      if (restored) { setPending(restored); setProductId(restored.productId) }
      setLoaded(true)
    }).catch(() => { if (active) { setError('Browser storage is unavailable. Reopen the extension to recover safely.'); setLoaded(false) } })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!loaded) return
    let active = true
    const controller = new AbortController()
    let timer: number | undefined
    setHealth(null)
    async function connect() {
      try {
        const [status, rows] = await Promise.all([
          localRequest<Health>(connection, '/api/health', undefined, undefined, controller.signal),
          localRequest<Product[]>(connection, '/api/demo/products', undefined, undefined, controller.signal),
        ])
        if (!Array.isArray(rows) || typeof status.worker_ready !== 'boolean') throw new Error('Unexpected API response.')
        if (active) {
          setHealth(status); setProducts(rows); setConnectionError('')
          if (!status.worker_ready) timer = window.setTimeout(() => void connect(), 5000)
        }
      } catch {
        if (active) {
          setHealth(null)
          const isVercel = connection.mode === 'vercel' || (Boolean(connection.baseUrl) && connection.mode !== 'local')
          const target = isVercel ? `Vercel (${getApiBaseUrl(connection)})` : `the local service on port ${connection.apiPort ?? 8000}`
          const hint = isVercel ? 'Free backends on Render may take a minute to wake up. Check Connection settings if using a different URL.' : 'Check Connection settings if your API uses a different port.'
          setConnectionError(`Could not connect to ${target}. Retrying automatically. ${hint}`)
          timer = window.setTimeout(() => void connect(), 5000)
        }
      }
    }
    void connect()
    return () => { active = false; controller.abort(); window.clearTimeout(timer) }
  }, [loaded, connection])

  useEffect(() => {
    const chrome = chromeApi()
    if (!chrome) return
    const invalidate = () => {
      if (captureTab.current === null) return
      epoch.current++; captureTab.current = null; setCapture(null); setProductId(''); setPreviewIds([]); setAnalyses([]); setSummary(null); setSaved(false)
      setError('The browsing page changed. Capture the current product’s reviews again before analyzing.')
    }
    const onUpdated = (tabId: number, change: { url?: string; status?: string }) => { if ((tabId === captureTab.current || captureTab.current === -1) && (change.url || change.status === 'loading')) invalidate() }
    chrome.tabs.onActivated.addListener(invalidate)
    chrome.tabs.onUpdated.addListener(onUpdated)
    return () => { chrome.tabs.onActivated.removeListener(invalidate); chrome.tabs.onUpdated.removeListener(onUpdated) }
  }, [])

  useEffect(() => {
    if (!previewIds.length) return
    const controller = new AbortController()
    let active = true
    let timer: number | undefined
    const started = Date.now()
    async function poll() {
      try {
        const results = await Promise.all(previewIds.map(id => localRequest<PreviewPoll>(connection, `/api/demo/previews/${id}`, undefined, undefined, controller.signal)))
        if (!active) return
        setPreviewCompleted(results.filter(result => result.status === 'completed').length)
        const failed = results.find(result => result.status === 'failed')
        if (failed) throw new Error(failed.error_summary || 'A captured review could not be analyzed.')
        if (results.every(result => result.status === 'completed' && result.analysis)) {
          const result = await localRequest<Summary>(connection, `/api/demo/products/${encodeURIComponent(productId)}/preview-summary`, { preview_ids: previewIds }, undefined, controller.signal)
          if (active) { setSummary(result); setAnalyses(results.map(item => item.analysis!)); setPreviewIds([]) }
          return
        }
        if (Date.now() - started > 30 * 60 * 1000) throw new Error('Preview is taking too long. You can save the captured reviews now and let analysis continue in the background.')
      } catch (cause) {
        if (active) { setError(message(cause)); setPreviewIds([]) }
        return
      }
      if (active) timer = window.setTimeout(() => void poll(), 1000)
    }
    void poll()
    return () => { active = false; controller.abort(); window.clearTimeout(timer) }
  }, [previewIds, productId, connection])

  useEffect(() => {
    if (!pending?.jobId) return
    setRecoveryMissing(false)
    let active = true
    let timer: number | undefined
    const controller = new AbortController()
    async function poll() {
      try {
        const result = await localRequest<Job>(pending!.connection, `/api/demo/jobs/${pending!.jobId}`, undefined, undefined, controller.signal)
        if (!active) return
        setJob(result); setError('')
        if (terminal(result)) {
          if (result.status === 'completed') {
            await chromeApi()!.storage.local.remove([pendingKey])
            if (active) { setPending(null); setSaved(true); setError('') }
          }
          return
        }
      } catch (cause) {
        if (active && cause instanceof LocalServiceError && cause.status === 404) {
          setRecoveryMissing(true)
          setError('The saved job no longer exists. Its product or import may have been removed. Clear this local recovery record to continue.')
          return
        }
        if (active) setError('Connection interrupted while checking the saved job. Your recovery record is retained; reconnecting…')
      }
      if (active) timer = window.setTimeout(() => void poll(), 1500)
    }
    void poll()
    return () => { active = false; controller.abort(); window.clearTimeout(timer) }
  }, [pending])

  async function captureCurrentPage() {
    if (operation.current || locked) return
    operation.current = true; setBusy('Capturing reviews…'); setError(''); clearPreview(); setCapture(null)
    captureTab.current = -1
    const generation = epoch.current
    try {
      const chrome = chromeApi()!
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
      if (generation !== epoch.current) return
      if (!tab?.id) throw new Error('No active browser tab was found. Open a product page in this window and try again.')
      if (!tab.url) throw new Error('Page access is unavailable. In Chrome’s extension settings, allow this extension on this shopping site, then reload the extension. For other sites, click its toolbar icon while that page is active.')
      if (!/^https?:\/\//.test(tab.url)) throw new Error('Capture works on http or https webpages. Open the product page in a browser tab and try again.')
      captureTab.current = tab.id
      const [result] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: capturePage })
      if (generation !== epoch.current) return
      if (!result?.result?.reviews.length) throw new Error('Nothing was captured. Try selecting a complete review or paste the text.')
      if (result.result.url !== tab.url) throw new Error('The page changed during capture. Capture the current product’s reviews again.')
      setCapture(result.result); setJob(null)
    } catch (cause) { if (generation === epoch.current) { captureTab.current = null; setError(message(cause)) } }
    finally { operation.current = false; setBusy('') }
  }

  async function preview() {
    if (!capture || !productId || locked || operation.current) return
    operation.current = true; setBusy('Queueing analysis…'); setError(''); clearPreview()
    const generation = epoch.current
    try {
      const result = await localRequest<{ preview_ids: string[] }>(connection, `/api/demo/products/${encodeURIComponent(productId)}/preview`, { reviews: capture.reviews })
      if (generation === epoch.current) setPreviewIds(result.preview_ids)
    } catch (cause) { if (generation === epoch.current) setError(message(cause)) }
    finally { operation.current = false; setBusy('') }
  }

  async function submit(request: Pending) {
    if (operation.current) return
    operation.current = true; setBusy('Saving reviews…'); setError(''); setRecoveryMissing(false)
    try {
      try { await chromeApi()!.storage.local.set({ [pendingKey]: request }) }
      catch { setError('Recovery storage is unavailable. The save was not sent; reopen the extension and try again.'); return }
      setPending(request)
      const result = await localRequest<Job>(request.connection, `/api/demo/products/${encodeURIComponent(request.productId)}/jobs`, { reviews: request.reviews }, request.key)
      const accepted = { ...request, jobId: result.id }
      await chromeApi()!.storage.local.set({ [pendingKey]: accepted })
      setPending(accepted); setJob(result)
    } catch (cause) {
      if (cause instanceof LocalServiceError && cause.status === 404) setRecoveryMissing(true)
      setError(`${message(cause)} ${cause instanceof LocalServiceError && cause.status === 404 ? 'Clear the missing local recovery record to choose another product.' : 'Resume this save to retry with the same request key.'}`)
    }
    finally { operation.current = false; setBusy('') }
  }

  async function retryJob() {
    if (!pending?.jobId || operation.current) return
    operation.current = true; setBusy('Retrying failed reviews…'); setError('')
    try {
      const result = await localRequest<Job>(pending.connection, `/api/demo/jobs/${pending.jobId}/retry`, {})
      setJob(result); setPending({ ...pending })
    } catch (cause) { setError(message(cause)) }
    finally { operation.current = false; setBusy('') }
  }

  async function createProduct(event: React.FormEvent) {
    event.preventDefault()
    if (locked || operation.current || !productName.trim()) return
    operation.current = true; setBusy('Creating product…'); setError('')
    try {
      const product = await localRequest<Product>(connection, '/api/demo/products', { name: productName })
      setProducts(current => [...current, { ...product, review_count: 0 }]); setProductId(product.id); setProductName(''); clearPreview()
      setConnection(current => ({ ...current }))
    } catch (cause) { setError(message(cause)) }
    finally { operation.current = false; setBusy('') }
  }

  async function saveSettings(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (locked) return
    const fields = new FormData(event.currentTarget)
    const mode = (fields.get('mode') as 'vercel' | 'local') || formMode
    let next: Connection
    if (mode === 'vercel') {
      const baseUrl = String(fields.get('baseUrl') || '').trim()
      if (!isValidUrl(baseUrl)) {
        setError('Use a Vercel or Render HTTPS URL (e.g. https://review-tag-generator.vercel.app).')
        return
      }
      next = {
        mode: 'vercel',
        baseUrl,
        apiPort: connection.apiPort ?? 8000,
        webPort: connection.webPort ?? 5173,
      }
    } else {
      const apiPort = Number(fields.get('apiPort'))
      const webPort = Number(fields.get('webPort'))
      next = {
        mode: 'local',
        apiPort,
        webPort,
        baseUrl: connection.baseUrl ?? defaultVercelUrl,
      }
      if (!validConnection(next)) {
        setError('Use whole-number ports between 1 and 65535.')
        return
      }
    }
    try {
      await chromeApi()!.storage.local.set({ [settingsKey]: next })
      clearPreview(); setCapture(null); captureTab.current = null; setProductId(''); setProducts([]); setConnection(next); setSettingsOpen(false); setError('')
    } catch { setError('Could not save connection settings in browser storage.') }
  }

  const isVercel = connection.mode === 'vercel' || (Boolean(connection.baseUrl) && connection.mode !== 'local')
  const product = products.find(item => item.id === productId)
  const webUrl = getWebUrl(connection)
  const apiBaseUrl = getApiBaseUrl(connection)

  return <div className="companion-panel">
    <header className="panel-brand"><div className="brand"><span className="brand-mark">R</span><span>Review <span className="panel-brand-light">Tag Generator</span></span></div><button type="button" aria-label="Connection settings" className="panel-settings" onClick={() => setSettingsOpen(value => !value)} disabled={locked}><Icon name="sliders" /></button></header>
    <main className="panel-content"><p className="eyebrow">Your shopping companion</p><h1>A closer look,<br />before you choose.</h1><p className="panel-intro">Find feature strengths and recurring complaints in the reviews you capture.</p>
      <div className="panel-connection"><span className={`panel-status-dot ${health ? 'connected' : ''}`} /><span>{health ? health.backend === 'transformer' ? (isVercel ? 'Vercel · trained models' : 'Local trained models') : (isVercel ? 'Vercel · heuristic demo' : 'Heuristic demo · local service') : (isVercel ? 'Vercel service not connected' : 'Local service not connected')}</span></div>
      {settingsOpen && <form className="panel-settings-form" onSubmit={saveSettings}>
        <h2>Connection settings</h2>
        <p>Choose where to send review analysis and workspace requests.</p>
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.75rem' }}>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', fontWeight: 500 }}>
            <input type="radio" name="mode" value="vercel" checked={formMode === 'vercel'} onChange={() => setFormMode('vercel')} />
            <span>Vercel / Cloud</span>
          </label>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', fontWeight: 500 }}>
            <input type="radio" name="mode" value="local" checked={formMode === 'local'} onChange={() => setFormMode('local')} />
            <span>Localhost (127.0.0.1)</span>
          </label>
        </div>
        {formMode === 'vercel' ? (
          <label>Vercel URL
            <input key={`vercel-${connection.baseUrl ?? defaultVercelUrl}`} name="baseUrl" type="url" required defaultValue={connection.baseUrl ?? defaultVercelUrl} placeholder="https://review-tag-generator.vercel.app" />
            <span style={{ display: 'block', fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>Connects to your Vercel deployment which routes /api calls to the backend.</span>
          </label>
        ) : (
          <>
            <label>API port<input key={`api-${connection.apiPort ?? 8000}`} name="apiPort" type="number" min="1" max="65535" required defaultValue={connection.apiPort ?? 8000} /></label>
            <label>Workspace port<input key={`web-${connection.webPort ?? 5173}`} name="webPort" type="number" min="1" max="65535" required defaultValue={connection.webPort ?? 5173} /></label>
          </>
        )}
        <button className="button button-primary">Save connection</button>
      </form>}
      {loaded && !health?.worker_ready && <button className="button button-secondary panel-wide" disabled={locked} onClick={() => setConnection({ ...connection })}>{isVercel ? 'Retry Vercel connection' : 'Retry local connection'}</button>}{summary && <p className="panel-current-product"><Icon name="bookmark" /><span>Reviewing <strong>{product?.name}</strong></span></p>}{connectionError && <p className="alert alert-error" role="alert">{connectionError}</p>}{error && <p className="alert alert-error" role="alert">{error}</p>}
      {loaded && <>
        <details className="panel-step" open={!summary}><summary className="panel-step-label"><span>01</span><h2>Bring in the reviews</h2></summary><button className="button button-primary panel-wide" disabled={locked} onClick={() => void captureCurrentPage()}><Icon name="browser" /> Capture from current page</button><p className="panel-note">Capture up to 100 loaded, complete reviews on Amazon.com / .in, Flipkart, Walmart, Best Buy, and Target. Expand review text and load more reviews first. Site adapters are experimental. You can also select one complete review.</p><details><summary>Or paste review text</summary><label className="panel-paste-label" htmlFor="pasted-reviews">Reviews, separated by a blank line</label><textarea id="pasted-reviews" rows={5} value={pasted} maxLength={2000200} disabled={locked} onChange={event => setPasted(event.target.value)} /><button className="button button-secondary panel-wide" disabled={locked || !pasted.trim()} onClick={() => { try { const reviews = parsePastedReviews(pasted); clearPreview(); captureTab.current = null; setCapture({ title: 'Pasted review sample', url: '', method: 'paste', reviews, skipped: 0, limited: false }); setJob(null); setError('') } catch (cause) { setError(message(cause)) } }}>Use pasted reviews</button></details>
        {capture && <div className="panel-capture"><strong>{capture.reviews.length} review{capture.reviews.length === 1 ? '' : 's'} captured</strong><span>{capture.title}</span><p>{(capture.method === 'amazon-loaded' || capture.method === 'retailer-loaded') ? 'Loaded review text only; other pages were not read.' : capture.method === 'selection' ? 'Selected text only. Check that it contains one complete review.' : 'Pasted sample only.'} {capture.skipped > 0 ? `${capture.skipped} incomplete or oversized reviews skipped.` : ''} {capture.limited ? 'Capture stopped at the 100-review limit.' : ''}</p><details><summary>Inspect captured text</summary>{capture.reviews.map((text, i) => <p className="panel-captured-text" key={i}>“{text}”</p>)}</details></div>}
        </details>
        <details className="panel-step" open={!summary}><summary className="panel-step-label"><span>02</span><h2>Choose a saved product</h2></summary><label className="sr-only" htmlFor="panel-product">Product for captured reviews</label><select id="panel-product" value={productId} disabled={locked} onChange={event => { clearPreview(); setProductId(event.target.value); setJob(null) }}><option value="">Choose a product…</option>{products.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select><details><summary>Create a product</summary><form className="panel-create" onSubmit={createProduct}><label htmlFor="panel-product-name">Product name</label><input id="panel-product-name" value={productName} onChange={event => setProductName(event.target.value)} maxLength={120} required disabled={locked} /><button className="button button-secondary" disabled={!productName.trim() || locked}>Create product</button><p className="panel-note">Creates an empty product. Captured reviews stay unsaved until you explicitly save them.</p></form></details></details>
        <button className="button button-primary panel-wide" onClick={() => void preview()} disabled={!capture || !productId || !health?.worker_ready || locked}>{previewIds.length ? `Analyzing captured reviews… ${previewCompleted}/${previewIds.length}` : 'Preview feature feedback'} <Icon name="arrow" /></button><p className="panel-note">Preview sends captured text to the selected service. It does not add reviews to product totals.</p>
        {(busy || previewIds.length > 0) && <p className="panel-note" role="status">{busy || (isVercel ? 'The models are processing your captured reviews…' : 'The local models are processing your captured reviews…')}</p>}
        {capture && <button className="button button-secondary panel-wide" type="button" onClick={() => {
          const blob = new Blob([capture.reviews.join('\n\n')], { type: 'text/plain;charset=utf-8' })
          const url = URL.createObjectURL(blob)
          const link = document.createElement('a')
          link.href = url; link.download = 'captured-reviews.txt'; link.click()
          window.setTimeout(() => URL.revokeObjectURL(url), 1000)
        }}>Download captured reviews (.txt)</button>}
        {capture && !summary && <><button className="button button-secondary panel-wide" type="button" disabled={!product || !!busy || !!pending || saved} onClick={() => {
          if (product) { clearPreview(); void submit({ productId, productName: product.name, reviews: capture.reviews, key: crypto.randomUUID(), connection }) }
        }}>{saved ? 'Reviews saved' : 'Save captured reviews'}</button><p className="panel-note">Save to the selected product without waiting for preview. Reviews are stored immediately; analysis continues in the background.</p></>}
        {health && !health.worker_ready && <p className="alert alert-warning">The inference worker is not ready. Start the worker and reopen this panel before previewing.</p>}
        {summary && <section className="panel-results" aria-labelledby="panel-results-title"><div className="panel-step-label"><span>03</span><h2 id="panel-results-title">What stands out</h2></div><p className="panel-note">{summary.insights.review_count} unique reviews · {summary.duplicate_reviews} duplicate texts excluded · {saved ? 'save finished' : pending ? 'save in progress' : 'not saved'}</p>{summary.insights.aspects.map(aspect => <details className="panel-feature" key={aspect.aspect_id}><summary><strong>{aspect.aspect}</strong><span className={`panel-feature-status ${aspect.classification}`}>{aspect.classification.replaceAll('_', ' ')}</span></summary><p className="panel-votes">{aspect.counts?.positive ?? 0} positive · {aspect.counts?.neutral ?? 0} neutral · {aspect.counts?.negative ?? 0} negative <span> / {aspect.review_count} reviews</span></p>{analyses.filter(review => review.tags.some(tag => tag.normalized_aspect_id === aspect.aspect_id || tag.normalized_aspect === aspect.aspect)).slice(0, 5).map(review => <blockquote key={review.review.review_id}>“{review.review.review_text}”</blockquote>)}</details>)}{!summary.insights.aspects.length && <p className="panel-note">No canonical features were detected. Your captured text remains available above.</p>}<p className="panel-note">Recurring tags require three supporting reviews. This is preview feedback for the captured sample. Open saved products for the published result after saving.</p><button className="button button-primary panel-wide" disabled={locked || saved} onClick={() => { if (capture && product) void submit({ productId, productName: product.name, reviews: capture.reviews, key: crypto.randomUUID(), connection }) }}>{saved ? 'Reviews saved' : 'Save captured reviews'}</button></section>}
        {pending && !pending.jobId && <div className="panel-recovery"><p>Save interrupted for <strong>{pending.productName}</strong>. Resume with the same request key to avoid duplicate submissions.</p><button className="button button-secondary panel-wide" disabled={!!busy} onClick={() => void submit(pending)}>Resume save</button></div>}
        {job && <section className="panel-job" aria-live="polite"><h2>Save progress</h2><p>{job.status.replaceAll('_', ' ')} · {job.completed_rows} of {job.total_rows} reviews analyzed{job.duplicate_rows ? ` · ${job.duplicate_rows} duplicates skipped` : ''}</p>{job.failed_rows > 0 && <p>Some reviews failed. Inspect the row errors and retry the failed reviews below.</p>}{pending?.jobId && (job.failed_rows > 0 || (job.rejected_rows ?? 0) > 0) && <button className="button button-secondary" onClick={() => void chromeApi()?.tabs.create({ url: `${apiBaseUrl}/api/demo/jobs/${pending.jobId}/errors.csv` })}>Open row errors (CSV)</button>}{pending && job.failed_rows > 0 && terminal(job) && <button className="button button-secondary" disabled={!!busy} onClick={() => void retryJob()}>Retry failed reviews</button>}{pending && terminal(job) && job.status !== 'completed' && <button className="button button-secondary" disabled={!!busy} onClick={async () => { try { await chromeApi()!.storage.local.remove([pendingKey]); setPending(null); setSaved(job.status === 'completed_with_errors') } catch { setError('Could not clear the local recovery record.') } }}>{job.status === 'failed' ? 'Dismiss failed job' : 'Keep partial result and finish'}</button>}</section>}
        {pending && recoveryMissing && <button className="button button-secondary panel-wide" disabled={!!busy} onClick={async () => { try { await chromeApi()!.storage.local.remove([pendingKey]); setPending(null); setJob(null); setProductId(''); setCapture(null); clearPreview(); setRecoveryMissing(false); setError('') } catch { setError('Could not clear the local recovery record. Check browser storage and reopen the panel.') } }}>Clear missing job recovery</button>}
        {pending?.jobId && !job && !recoveryMissing && <p className="panel-note" role="status">Recovering saved job for {pending.productName}…</p>}
      </>}
      <button className="panel-workspace" type="button" onClick={() => { const id = pending?.productId ?? productId; void chromeApi()?.tabs.create({ url: `${webUrl}${id ? `/products/${encodeURIComponent(id)}` : '/products'}` }) }}>Open saved products <Icon name="arrow" /></button>
    </main><footer className="panel-footer">Evidence to help you consider. Predictions can be wrong.</footer>
  </div>
}
