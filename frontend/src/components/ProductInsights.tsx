import { useSearchParams } from 'react-router-dom'
import type { Analysis, Detail } from '../api'
import { Icon } from './Icon'
import { SentimentBadge } from './SentimentBadge'

type Aspect = Detail['insights']['aspects'][number]
type Sentiment = 'positive' | 'neutral' | 'negative'
type EvidenceHandler = (review: Analysis, tagIndex: number) => void

function matchesAspect(tag: Analysis['tags'][number], aspect: Aspect) {
  return tag.normalized_aspect_id === aspect.aspect_id || tag.normalized_aspect === aspect.aspect_id || tag.normalized_aspect === aspect.aspect
}

function reviewVote(review: Analysis, aspect: Aspect): Sentiment | null {
  const labels = new Set(review.tags.filter(tag => matchesAspect(tag, aspect)).map(tag => tag.sentiment))
  if (!labels.size) return null
  if (labels.has('positive') && labels.has('negative')) return 'neutral'
  return labels.has('positive') ? 'positive' : labels.has('negative') ? 'negative' : 'neutral'
}

function SentimentBar({ aspect }: { aspect: Aspect }) {
  const total = aspect.review_count
  return <span className="feature-bar" aria-hidden="true">{(['positive', 'neutral', 'negative'] as const).map(label => <span key={label} className={`feature-bar-${label}`} style={{ flexGrow: Math.max(0, Math.min(total, aspect.counts?.[label] ?? 0)) }} />)}</span>
}

export function ProductInsights({ data, onEvidence }: { data: Detail; onEvidence: EvidenceHandler }) {
  const [params, setParams] = useSearchParams()
  const needle = params.get('featureQuery') ?? ''
  const aspects = [...data.insights.aspects].sort((a, b) => b.review_count - a.review_count || a.aspect.localeCompare(b.aspect))
  const visibleAspects = aspects.filter(aspect => aspect.aspect.toLowerCase().includes(needle.toLowerCase()))
  const selected = visibleAspects.find(aspect => aspect.aspect_id === params.get('aspect')) ?? visibleAspects[0]
  const sentiment = params.get('sentiment')
  const activeSentiment = sentiment === 'positive' || sentiment === 'neutral' || sentiment === 'negative' ? sentiment : 'all'
  const reviews = selected ? data.reviews.filter(review => {
    const vote = reviewVote(review, selected)
    return vote && (activeSentiment === 'all' || vote === activeSentiment)
  }) : []
  function update(key: string, value: string) {
    setParams(current => { const next = new URLSearchParams(current); if (value) next.set(key, value); else next.delete(key); if (key === 'aspect' || key === 'featureQuery') next.delete('sentiment'); return next }, { replace: true })
  }
  const supported = aspects.filter(aspect => aspect.review_count >= 3)
  const strengths = supported.filter(aspect => ['good', 'excellent'].includes(aspect.classification))
  const complaints = supported.filter(aspect => ['weak', 'poor'].includes(aspect.classification))

  return <>
    <div className="insight-summary" aria-label="Saved evidence summary">
      <div><span className="summary-label">Reviews analyzed</span><strong>{data.insights.review_count}<span>in published analysis</span></strong></div>
      <div><span className="summary-label">What stands out</span><strong>{strengths.length}<span>supported strengths</span></strong></div>
      <div><span className="summary-label">Worth a closer look</span><strong>{complaints.length}<span>recurring complaints</span></strong></div>
    </div>
    <div className="evidence-workspace">
      <section className="feature-feedback" aria-labelledby="feature-feedback-title">
        <div className="section-heading"><div><p className="eyebrow">The review picture</p><h2 id="feature-feedback-title">Feature by feature</h2><p>Choose a feature. Read what people actually said.</p></div><span className="count-label">{aspects.length} features</span></div>
        <label className="feature-search"><Icon name="search" /><span className="sr-only">Search features</span><input value={needle} onChange={event => update('featureQuery', event.target.value)} placeholder="Find a feature…" /></label>
        <p className="sentiment-legend"><span><i className="sentiment-dot positive" />Positive</span><span><i className="sentiment-dot neutral" />Neutral</span><span><i className="sentiment-dot negative" />Negative</span></p>
        <div className="feature-rows">{visibleAspects.map(aspect => <button type="button" className="feature-row" key={aspect.aspect_id} aria-pressed={selected?.aspect_id === aspect.aspect_id} onClick={() => update('aspect', aspect.aspect_id)}>
          <span className="feature-row-heading"><strong>{aspect.aspect}</strong><span className={`feature-classification ${aspect.classification}`}>{aspect.classification.replaceAll('_', ' ')}</span></span>
          <SentimentBar aspect={aspect} />
          <span className="feature-counts"><span>{aspect.review_count} supporting review{aspect.review_count === 1 ? '' : 's'}</span><span>{aspect.counts?.positive ?? 0}+ <span className="sr-only">positive</span> / {aspect.counts?.neutral ?? 0} neutral / {aspect.counts?.negative ?? 0}− <span className="sr-only">negative</span></span></span>
        </button>)}</div>
        {!aspects.length && <div className="inline-empty"><Icon name="quote" /><h3>No feature feedback yet</h3><p>Analyze or import reviews to start building the picture. Reviews without detected features remain available under Review evidence.</p></div>}
        {!!aspects.length && !visibleAspects.length && <p className="inline-empty">No features match “{needle}”.</p>}
        <p className="feature-policy">One vote per review and feature. Recurring tags require at least three supporting reviews. A review can discuss several features.</p>
      </section>
      <section className="supporting-evidence" aria-labelledby="supporting-evidence-title">
        <div className="evidence-pane-heading"><span className="evidence-icon"><Icon name="quote" /></span><div><p className="eyebrow">Behind the finding</p><h2 id="supporting-evidence-title">{selected ? `${selected.aspect} evidence` : 'Supporting reviews'}</h2></div></div>
        {selected ? <><p className="field-hint">{selected.review_count} supporting reviews in this saved sample.</p><div className="evidence-filters" aria-label="Filter evidence by review vote">{(['all', 'positive', 'neutral', 'negative'] as const).map(label => <button key={label} type="button" aria-pressed={activeSentiment === label} onClick={() => update('sentiment', label === 'all' ? '' : label)}>{label === 'all' ? 'All' : label.charAt(0).toUpperCase() + label.slice(1)} <span>{label === 'all' ? selected.review_count : selected.counts?.[label] ?? 0}</span></button>)}</div>
          <div className="source-reviews">{reviews.slice(0, 5).map((review, index) => {
            const tagIndex = review.tags.findIndex(tag => matchesAspect(tag, selected))
            const tag = review.tags[tagIndex]
            if (!tag) return null
            const chars = Array.from(review.review.review_text)
            const start = tag.start_char
            const end = tag.end_char
            return <article className="source-review" key={review.review.review_id}><div className="source-meta"><span>Saved review {index + 1}</span><SentimentBadge sentiment={reviewVote(review, selected) ?? 'neutral'} /></div><p className="source-quote">“{start !== undefined && end !== undefined && start >= 0 && end <= chars.length && end > start ? <>{chars.slice(0, start).join('')}<mark>{chars.slice(start, end).join('')}</mark>{chars.slice(end).join('')}</> : review.review.review_text}”</p><button className="evidence-link" onClick={() => onEvidence(review, tagIndex)}>Inspect prediction <Icon name="arrow" /></button></article>
          })}{!reviews.length && <p className="inline-empty">No {activeSentiment === 'all' ? '' : activeSentiment} review votes for this feature.</p>}</div>
          {reviews.length > 5 && <p className="field-hint">Showing 5 of {reviews.length} matching reviews. Open Review evidence for the complete saved sample.</p>}
          <p className="evidence-footnote">Predicted feedback from your saved reviews. Sample selection and model errors can affect the picture.</p></> : <p className="inline-empty">Feature evidence will appear here as reviews are analyzed.</p>}
      </section>
    </div>
  </>
}
