import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AppRoutes } from './AppRoutes'

describe('AppRoutes', () => {
  it('renders the model-metrics route inside the application shell', () => {
    render(
      <MemoryRouter initialEntries={['/models']}>
        <AppRoutes />
      </MemoryRouter>,
    )

    expect(screen.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible()
    expect(screen.getByRole('heading', { level: 1, name: 'Model metrics' })).toBeVisible()
  })
})
