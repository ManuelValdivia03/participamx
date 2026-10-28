import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { LaboratoryPage } from './LaboratoryPage'

describe('LaboratoryPage', () => {
  it('muestra las seis estrategias y el estado U/R/M pendiente', () => {
    render(<LaboratoryPage />)
    expect(screen.getAllByRole('article')).toHaveLength(6)
    expect(screen.getByText('Información no disponible.')).toBeInTheDocument()
    expect(screen.getByText('¿Cómo evaluaríamos esta propuesta?')).toBeInTheDocument()
  })
  it('configura, guarda, compara y elimina escenarios', async () => {
    const user = userEvent.setup()
    render(<LaboratoryPage />)
    const fill = async (name: string, value: string) => { const field = screen.getByLabelText(name); await user.clear(field); await user.type(field, value) }
    await fill('Presupuesto hipotético (MXN)', '10000')
    await fill('Costo unitario supuesto (MXN)', '200')
    await fill('Unidades de actividad planificadas', '30')
    expect(screen.getByText('$6,000.00', { exact: false })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Guardar escenario temporalmente' }))
    await user.click(screen.getAllByRole('button', { name: /^Crear escenario$/ })[1])
    await fill('Presupuesto hipotético (MXN)', '5000')
    await fill('Costo unitario supuesto (MXN)', '100')
    await fill('Unidades de actividad planificadas', '20')
    await user.click(screen.getByRole('button', { name: 'Guardar escenario temporalmente' }))
    expect(screen.getByLabelText('Gráfica comparativa de costos previstos')).toBeInTheDocument()
    expect(screen.getByText(/las estrategias usan unidades distintas/i)).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: /Eliminar Escenario:/ })[0])
    expect(screen.queryByLabelText('Gráfica comparativa de costos previstos')).not.toBeInTheDocument()
  })
})
