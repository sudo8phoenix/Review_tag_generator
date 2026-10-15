import { useEffect, useRef, useState, type MutableRefObject } from 'react'
import { api, type Analysis, type Tag } from '../api'
import './ReviewAssistant.css'

type AssistStatus = { enabled: boolean; provider: string | null; model: string | null; reason: string }
export type NormalizationResult = {
  id?: string
  canonical_aspect_id: string | null
  canonical_aspect_label: string | null
  proposed_aspect_label: string | null
  explanation: string
  source: { raw_aspect: string; start_char: number; end_char: number }
  applied: false
  provider: string | null
  model: string | null
}
type Citation = { review_id: string; quote: string }
type Claim = { text: string; citations: Citation[] }
type ProductAnswer = {
  claims: Claim[]
  status: 'answered' | 'insufficient_evidence'
  snapshot_id: string | null
  data_revision: number
  pipeline_version: string | null
  stale: boolean
  retrieval_review_count: number
  provider: string | null
  model: string | null
}

function invalidateRequest(request: MutableRefObject<number>) {
  request.current++
}

function useAssistStatus() {
  const [status, setStatus] = useState<AssistStatus | null>(null)
  const [error, setError] = useState('')
  const request = useRef(0)

  useEffect(() => {
    let active = true
    const current = ++request.current
    api<AssistStatus>('/assist/status').then(result => {
      if (active && request.current === current) setStatus(result)
    }).catch(reason => {
      if (active && request.current === current) setError((reason as Error).message || 'Assistant status is unavailable.')
    })
    return () => { active = false; invalidateRequest(request) }
  }, [])

  return { status, statusError: error }
}

function SetupNote({ reason }: { reason: string }) {
  return <div className="review-assistant__setup"><p>{reason}</p><p>Server configuration: <code>LLM_PROVIDER=groq</code>, <code>GROQ_API_KEY</code> (keep the key server-side), and <code>LLM_MODEL=openai/gpt-oss-20b</code>; or <code>LLM_PROVIDER=gemini</code>, <code>GEMINI_API_KEY</code> (keep the key server-side), and <code>LLM_MODEL=gemini-flash-latest</code>; or <code>LLM_PROVIDER=ollama</code> with <code>LLM_MODEL=&lt;installed-model&gt;</code> for a local model.</p></div>
}

function ProviderDisclosure({ provider }: { provider: string | null }) {
  if (provider === 'gemini' || provider === 'groq') return <p className="review-assistant__disclosure">When you submit, this review text is sent to the configured cloud provider to generate a suggestion. The suggestion may be wrong and is not saved automatically.</p>
  if (provider?.toLowerCase() === 'ollama') return <p className="review-assistant__disclosure">When you submit, this review text is processed by the configured local Ollama model. The suggestion may be wrong and is not saved automatically.</p>
  return <p className="review-assistant__disclosure">When you submit, the review text is sent to the configured assistant provider. The suggestion may be wrong and is not saved automatically.</p>
}

export type SavedAspectContext = { productId: string; snapshotId: string }

export function UnknownAspectAssist({ review, tag, savedContext, onSuggestion }: { review: Analysis; tag: Tag; savedContext?: SavedAspectContext; onSuggestion?: (suggestion: NormalizationResult) => void }) {
  const { status, statusError } = useAssistStatus()
  const [result, setResult] = useState<NormalizationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const aspectContext = `${review.review.review_id}:${review.review.review_text}:${tag.raw_aspect}:${tag.start_char ?? ''}:${tag.end_char ?? ''}`
  const [resultContext, setResultContext] = useState('')
  const request = useRef(0)

  useEffect(() => {
    request.current++
    setResult(null)
    setResultContext('')
    setError('')
    setLoading(false)
    return () => { invalidateRequest(request) }
  }, [review.review.review_id, review.review.review_text, tag.raw_aspect, tag.start_char, tag.end_char])

  if (tag.normalized_aspect !== null) return null

  async function suggest() {
    const current = ++request.current
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const response = await api<NormalizationResult>(savedContext ? `/demo/products/${savedContext.productId}/corrections/suggest` : '/assist/normalize', savedContext ? {
        snapshot_id: savedContext.snapshotId, review_id: review.review.review_id,
        start_char: tag.start_char, end_char: tag.end_char,
      } : {
        review_text: review.review.review_text,
        raw_aspect: tag.raw_aspect,
        start_char: tag.start_char,
        end_char: tag.end_char,
      })
      if (request.current === current) {
        setResult(response)
        setResultContext(aspectContext)
        onSuggestion?.(response)
      }
    } catch (reason) {
      if (request.current === current) setError((reason as Error).message || 'Could not get a suggestion. Try again.')
    } finally {
      if (request.current === current) setLoading(false)
    }
  }

  const configured = status?.enabled === true
  return <section className="review-assistant review-assistant--compact" aria-labelledby="unknown-aspect-title">
    <div className="review-assistant__heading">
      <div><h3 id="unknown-aspect-title">Review aspect suggestion</h3><p>Suggest a mapping for “{tag.raw_aspect}”. {savedContext ? 'The suggestion is recorded for review; predictions stay unchanged.' : 'Nothing is saved or changed.'}</p></div>
      <button className="button button-secondary" type="button" onClick={() => void suggest()} disabled={!configured || loading}>
        {loading ? 'Suggesting…' : error ? 'Retry suggestion' : result ? 'Suggest again' : 'Suggest mapping'}
      </button>
    </div>
    {statusError && <p className="review-assistant__message review-assistant__message--error" role="alert">Assistant status unavailable: {statusError}</p>}
    {status && !status.enabled && <SetupNote reason={status.reason} />}
    {configured && status && <ProviderDisclosure provider={status.provider} />}
    {loading && <p className="review-assistant__message" role="status">Checking the review text for a suitable aspect…</p>}
    {error && <p className="review-assistant__message review-assistant__message--error" role="alert">{error}</p>}
    {result && resultContext === aspectContext && <div className="review-assistant__result" aria-live="polite">
      {result.canonical_aspect_id && result.canonical_aspect_label
        ? <p><strong>Suggested mapping:</strong> {result.canonical_aspect_label}</p>
        : result.proposed_aspect_label
          ? <p><strong>Possible new aspect:</strong> {result.proposed_aspect_label}</p>
          : <p><strong>No suitable aspect suggested.</strong></p>}
      <p>{result.explanation}</p>
      <small>Source phrase: “{result.source.raw_aspect}” ({result.source.start_char}–{result.source.end_char}) · suggestion only{result.provider ? ` · ${result.provider}${result.model ? ` / ${result.model}` : ''}` : ''}</small>
    </div>}
  </section>
}

export function ProductReviewAssistant({ productId, snapshotId }: { productId: string; snapshotId: string | null }) {
  const { status, statusError } = useAssistStatus()
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<ProductAnswer | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const request = useRef(0)
  const contextKey = `${productId}:${snapshotId ?? ''}`
  const [answerContext, setAnswerContext] = useState('')
  const context = useRef(contextKey)

  useEffect(() => {
    context.current = contextKey
    request.current++
    setAnswer(null)
    setAnswerContext('')
    setError('')
    setLoading(false)
  }, [contextKey])

  async function ask(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const submittedQuestion = question.trim()
    if (!submittedQuestion || submittedQuestion.length > 500 || !status?.enabled || loading) return
    const current = ++request.current
    const submittedContext = contextKey
    setLoading(true)
    setError('')
    setAnswer(null)
    try {
      const response = await api<ProductAnswer>(`/demo/products/${encodeURIComponent(productId)}/ask`, { question: submittedQuestion })
      if (request.current !== current || context.current !== submittedContext) return
      setAnswer(response)
      setAnswerContext(submittedContext)
    } catch (reason) {
      if (request.current === current && context.current === submittedContext) setError((reason as Error).message || 'Could not answer this question. Try again.')
    } finally {
      if (request.current === current && context.current === submittedContext) setLoading(false)
    }
  }

  const visibleAnswer = answerContext === contextKey ? answer : null
  const snapshotMismatch = !!visibleAnswer && visibleAnswer.snapshot_id !== snapshotId
  const configured = status?.enabled === true
  return <section className="content-section review-assistant" aria-labelledby="product-assistant-title">
    <div className="review-assistant__heading">
      <div><h2 id="product-assistant-title">Ask about these reviews</h2><p>Answers use this product’s published review snapshot and include supporting quotes.</p></div>
    </div>
    {statusError && <p className="review-assistant__message review-assistant__message--error" role="alert">Assistant status unavailable: {statusError}</p>}
    {status && !status.enabled && <SetupNote reason={status.reason} />}
    {configured && status && <p className="review-assistant__disclosure">When you submit, your question and retrieved review text are sent to {status.provider ?? 'the configured assistant provider'}{status.provider?.toLowerCase() === 'gemini' ? ' (Gemini)' : status.provider?.toLowerCase() === 'ollama' ? ' running locally' : ''}. Answers can be wrong. Citations are checked against source quotes, but that does not guarantee the quotes support every claim.</p>}
    <form className="review-assistant__form" onSubmit={event => void ask(event)}>
      <label htmlFor="product-review-question">Your question</label>
      <textarea id="product-review-question" rows={3} maxLength={500} value={question} disabled={loading || !configured} onChange={event => setQuestion(event.target.value)} placeholder="For example, what do reviewers say about battery life?" />
      <div className="review-assistant__form-footer"><span>{question.length}/500</span><button className="button button-primary" type="submit" disabled={!configured || loading || !question.trim()}>{loading ? 'Finding evidence…' : error ? 'Retry answer' : 'Ask about reviews'}</button></div>
    </form>
    {loading && <p className="review-assistant__message" role="status">Searching review evidence and preparing an answer…</p>}
    {error && <p className="review-assistant__message review-assistant__message--error" role="alert">{error}</p>}
    {snapshotMismatch && <div className="alert alert-warning" role="alert"><strong>The answer is for a different review snapshot.</strong><span>Reload this product page before using an answer from the current data.</span></div>}
    {visibleAnswer && !snapshotMismatch && <div className="review-assistant__answer" aria-live="polite">
      {visibleAnswer.status === 'insufficient_evidence' && <p className="review-assistant__insufficient"><strong>Not enough review evidence.</strong> Try a more specific question or reload if the product data has changed.</p>}
      {visibleAnswer.claims.length > 0 ? <ol className="review-assistant__claims">{visibleAnswer.claims.map((claim, index) => <li key={`${index}-${claim.text}`}>
        <p>{claim.text}</p>
        {claim.citations.length > 0 && <ul className="review-assistant__citations">{claim.citations.map((citation, citationIndex) => <li key={`${citation.review_id}-${citationIndex}`}><blockquote>{citation.quote}</blockquote><span>Review {citation.review_id}</span></li>)}</ul>}
      </li>)}</ol> : visibleAnswer.status === 'answered' && <p>No cited claims were returned for this answer.</p>}
      <p className="review-assistant__provenance">Based on {visibleAnswer.retrieval_review_count} retrieved review{visibleAnswer.retrieval_review_count === 1 ? '' : 's'}{visibleAnswer.provider ? ` · ${visibleAnswer.provider}${visibleAnswer.model ? ` / ${visibleAnswer.model}` : ''}` : ''}{visibleAnswer.stale ? ' · published data marked stale' : ''}</p>
    </div>}
  </section>
}
