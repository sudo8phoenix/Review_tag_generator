import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import type { Detail } from '../api'
import { ProductInsights } from './ProductInsights'

it('filters by review vote while retaining contradictory source mentions and Unicode evidence', () => {
  const review = { review: { review_id: 'one', review_text: '😀 battery good, battery bad' }, backend: 'transformer', tags: [
    { normalized_aspect: 'Battery', normalized_aspect_id: 'battery', raw_aspect: 'battery', start_char: 2, end_char: 9, sentiment: 'positive' as const, confidence: .8, tag: 'Great Battery' },
    { normalized_aspect: 'Battery', normalized_aspect_id: 'battery', raw_aspect: 'battery', start_char: 16, end_char: 23, sentiment: 'negative' as const, confidence: .8, tag: 'Poor Battery' },
  ] }
  const data: Detail = { product: { id: 'p', name: 'Laptop', review_count: 1 }, backend: 'transformer', reviews: [review], insights: { review_count: 1, sentiment_distribution: { positive: 0, neutral: 1, negative: 0 }, aspects: [{ aspect_id: 'battery', aspect: 'Battery', review_count: 1, classification: 'insufficient_evidence', counts: { positive: 0, neutral: 1, negative: 0 } }], top_tags: [] } }
  const onEvidence = vi.fn()
  render(<MemoryRouter><ProductInsights data={data} onEvidence={onEvidence} /></MemoryRouter>)
  expect(document.querySelector('mark')?.textContent).toBe('battery')
  fireEvent.click(screen.getByRole('button', { name: 'Positive 0' }))
  expect(screen.getByText('No positive review votes for this feature.')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Neutral 1' }))
  fireEvent.click(screen.getByRole('button', { name: /Inspect prediction/ }))
  expect(onEvidence).toHaveBeenCalledWith(review, 0)
})
