import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LaboratoryPage } from './LaboratoryPage'
import { strategies } from './strategies'
import * as downloads from './export'

afterEach(() => vi.restoreAllMocks())

describe('detalle accesible de estrategias', () => {
  it('abre los seis detalles sin seleccionar otra estrategia y vuelve al botón con Escape', async () => {
    const user = userEvent.setup()
    render(<LaboratoryPage />)
    for (const strategy of strategies) {
      const trigger = screen.getByRole('button', { name: `Ver detalles: ${strategy.name}` })
      await user.click(trigger)
      const dialog = screen.getByRole('dialog', { name: strategy.name })
      expect(dialog).toHaveFocus()
      expect(within(dialog).getAllByRole('heading', { level: 3 })).toHaveLength(13)
      expect(within(dialog).getByRole('button', { name: 'Descargar PDF' })).toBeEnabled()
      expect(within(dialog).getByRole('button', { name: 'Descargar PNG' })).toBeEnabled()
      await user.keyboard('{Tab}')
      expect(within(dialog).getByRole('button', { name: 'Cerrar detalles de estrategia' })).toHaveFocus()
      await user.keyboard('{Shift>}{Tab}{/Shift}')
      expect(within(dialog).getByRole('button', { name: 'Descargar PNG' })).toHaveFocus()
      await user.keyboard('{Escape}')
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(trigger).toHaveFocus()
    }
    expect(screen.getByRole('button', { name: 'Estrategia elegida' }).closest('article')).toHaveTextContent(strategies[0].name)
  })

  it('navega a las secciones sin alterar la ruta y restaura el desplazamiento al cerrar', async () => {
    const user = userEvent.setup()
    render(<LaboratoryPage />)
    const originalHash = location.hash
    await user.click(screen.getAllByRole('button', { name: /^Ver detalles:/ })[0])
    expect(document.body.style.overflow).toBe('hidden')
    await user.click(screen.getByText('Ir a una sección · 13 apartados'))
    await user.click(screen.getByRole('link', { name: 'Recursos humanos, tecnológicos y operativos' }))
    expect(screen.getByRole('heading', { name: /Recursos humanos, tecnológicos y operativos/ })).toHaveFocus()
    expect(location.hash).toBe(originalHash)
    await user.click(screen.getByRole('button', { name: 'Cerrar detalles de estrategia' }))
    expect(document.body.style.overflow).not.toBe('hidden')
  })

  it('genera PDF y comunica fallos PNG recuperando los botones', async () => {
    const user = userEvent.setup()
    const pdf = vi.spyOn(downloads, 'downloadStrategyPdf').mockImplementation(() => {})
    vi.spyOn(downloads, 'downloadStrategyPng').mockRejectedValue(new Error('No se pudo generar el PNG.'))
    render(<LaboratoryPage />)
    await user.click(screen.getAllByRole('button', { name: /^Ver detalles:/ })[0])
    await user.click(screen.getByRole('button', { name: 'Descargar PDF' }))
    expect(pdf).toHaveBeenCalledWith(strategies[0])
    await user.click(screen.getByRole('button', { name: 'Descargar PNG' }))
    expect(screen.getByRole('alert')).toHaveTextContent('No se pudo generar el PNG.')
    expect(screen.getByRole('button', { name: 'Descargar PNG' })).toBeEnabled()
  })
})
