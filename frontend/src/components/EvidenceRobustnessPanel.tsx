import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import './EvidenceRobustnessPanel.css'

type RemovalScenario = {
  removed_vote: string
  review_count: number
  classification_after_removal: string
  tag_unchanged: boolean
}
type AuditedAspect = {
  aspect_id: string
  aspect: string
  review_count: number
  classification: string
  supported: boolean
  classification_stability: number
  tag_stability: number
  fragile_tag: boolean
  opposing_review_votes: boolean
  contradictory_review_count: number
  ordinary_neutral_review_count: number
  removal_scenarios: RemovalScenario[]
}
type EvidenceAudit = {
  method: string
  aspects: AuditedAspect[]
  note: string
  snapshot_id: string | null
  pipeline_version?: string | null
  aggregate_version?: string | null
  data_revision?: number
  stale?: boolean
}

function percent(value: number) {
  return `${(value * 100).toFixed(0)}%`
}

export function EvidenceRobustnessPanel({ productId, snapshotId }: { productId: string; snapshotId: string | null }) {
  const [audit, setAudit] = useState<EvidenceAudit | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedAspect, setSelectedAspect] = useState('')
  const [selectedScenario, setSelectedScenario] = useState('')

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError('')
    try {
      const result = await api<EvidenceAudit>(`/demo/products/${encodeURIComponent(productId)}/evidence-audit`)
      if (!signal?.aborted) {
        setAudit(result)
        setSelectedAspect(current => result.aspects.some(item => item.aspect_id === current) ? current : result.aspects[0]?.aspect_id ?? '')
        setSelectedScenario('')
      }
    } catch (reason) {
      if (!signal?.aborted) setError((reason as Error).message || 'Could not load evidence audit.')
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [productId])

  useEffect(() => {
    const controller = new AbortController()
    setAudit(null)
    void load(controller.signal)
    return () => controller.abort()
  }, [load, snapshotId])

  const visibleAudit = !loading && !error ? audit : null
  const mismatch = !!visibleAudit && visibleAudit.snapshot_id !== snapshotId
  const aspect = visibleAudit?.aspects.find(item => item.aspect_id === selectedAspect)
  const scenario = aspect?.removal_scenarios.find((_, index) => String(index) === selectedScenario)

  function downloadJson() {
    if (!audit || mismatch) return
    const blob = new Blob([JSON.stringify(audit, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `evidence-audit-${productId}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  return <section className="content-section evidence-robustness" aria-labelledby="evidence-robustness-title">
    <div className="section-heading">
      <div><h2 id="evidence-robustness-title">Evidence robustness</h2><p>How much do each aspect’s saved prediction and tag change when one review vote is removed?</p></div>
      {visibleAudit && !mismatch && <button type="button" className="button button-secondary" onClick={downloadJson}>Download JSON</button>}
    </div>
    {loading && <p className="evidence-robustness__state" role="status">Loading evidence audit…</p>}
    {!loading && error && <div className="alert alert-error" role="alert"><strong>Evidence audit unavailable</strong><span>{error}</span><button type="button" className="button button-secondary" onClick={() => void load()}>Retry</button></div>}
    {visibleAudit && mismatch && <div className="alert alert-warning" role="alert"><strong>This audit belongs to a different published snapshot.</strong><span>Reload the page to inspect evidence for the current snapshot.</span></div>}
    {visibleAudit && !mismatch && visibleAudit.aspects.length === 0 && <p className="evidence-robustness__state">No aspect evidence is available for this snapshot yet.</p>}
    {visibleAudit && aspect && !mismatch && <>
      <div className="evidence-robustness__controls">
        <label>Aspect<select value={selectedAspect} onChange={event => { setSelectedAspect(event.target.value); setSelectedScenario('') }}>{visibleAudit.aspects.map(item => <option key={item.aspect_id} value={item.aspect_id}>{item.aspect}</option>)}</select></label>
        <label>Remove one vote<select value={selectedScenario} onChange={event => setSelectedScenario(event.target.value)}><option value="">Choose a vote to remove</option>{aspect.removal_scenarios.map((item, index) => <option key={`${item.removed_vote}-${index}`} value={String(index)}>One {item.removed_vote} vote ({item.review_count} available)</option>)}</select></label>
      </div>
      <div className="evidence-robustness__summary">
        <div><span>Current classification</span><strong>{aspect.classification.replaceAll('_', ' ')}</strong></div>
        <div><span>Classification stability</span><strong>{percent(aspect.classification_stability)}</strong></div>
        <div><span>Tag stability</span><strong>{percent(aspect.tag_stability)}</strong></div>
        <div><span>Review support</span><strong>{aspect.review_count}</strong></div>
      </div>
      <p className="evidence-robustness__calibration">Sensitivity only. These uncalibrated leave-one-review-out rates measure stability of saved predictions; they are not accuracy, confidence intervals, or probabilities.</p>
      {scenario && <div className={`evidence-robustness__outcome ${scenario.tag_unchanged ? 'is-stable' : 'is-changed'}`} aria-live="polite"><strong>After removing one {scenario.removed_vote} vote:</strong> classification becomes <b>{scenario.classification_after_removal.replaceAll('_', ' ')}</b>; tag {scenario.tag_unchanged ? 'stays the same' : 'changes'}.</div>}
      <div className="evidence-robustness__signals"><div><strong>Disagreement across reviews</strong><p>{aspect.opposing_review_votes ? 'Positive and negative votes both occur across different reviews.' : 'No opposing positive and negative review votes are recorded.'}</p></div><div><strong>Contradictions within reviews</strong><p>{aspect.contradictory_review_count} review{aspect.contradictory_review_count === 1 ? '' : 's'} contain conflicting aspect evidence; {aspect.ordinary_neutral_review_count} neutral vote{aspect.ordinary_neutral_review_count === 1 ? '' : 's'} are ordinary neutral evidence.</p></div></div>
      <p className="evidence-robustness__method">{visibleAudit.note}{visibleAudit.stale ? ' This published analysis is marked stale.' : ''}</p>
    </>}
  </section>
}
