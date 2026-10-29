import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { ProductDetailPage } from './pages'

afterEach(() => vi.unstubAllGlobals())
it('distinguishes saved reviews from published analysis and starts analysis', async () => {
  const detail = { product: { id: 'p1', name: 'Laptop' }, backend: 'transformer', stale: true, review_counts: { pending: 3 }, reviews: [], insights: { review_count: 0, aspects: [], top_tags: [], sentiment_distribution: {} } }
  const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => detail }).mockResolvedValue({ ok: true, json: async () => ({ id: 'j1', status: 'failed', total_rows: 3, completed_rows: 0, failed_rows: 3 }) })
  vi.stubGlobal('fetch', fetchMock)
  render(<MemoryRouter initialEntries={['/products/p1']}><Routes><Route path="/products/:id" element={<ProductDetailPage />} /></Routes></MemoryRouter>)
  expect(await screen.findByText('3 saved reviews · 0 in published analysis')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Analyze saved reviews' }))
  expect(await screen.findByRole('status')).toHaveTextContent('3 failed')
  expect(fetchMock).toHaveBeenCalledWith('/api/demo/products/p1/regenerate', expect.objectContaining({ method: 'POST' }))
})
