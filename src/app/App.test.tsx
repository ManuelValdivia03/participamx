import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import App from './App'

describe('navegación principal', () => {
  beforeEach(() => { window.location.hash = '#dashboard' })

  it('navega entre Dashboard y el Laboratorio', async () => {
    const user = userEvent.setup()
    render(<App />)
    expect(screen.getByRole('heading', { level: 1, name: 'Menú principal' })).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: /Laboratorio de Estrategias/ }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Laboratorio de Estrategias' })).toBeInTheDocument()
    expect(await screen.findByText('Laboratorio de Estrategias Cívicas')).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: /Menú principal/ }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Menú principal' })).toBeInTheDocument()
  })
})
