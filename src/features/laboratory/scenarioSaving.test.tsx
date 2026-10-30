import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LaboratoryPage } from './LaboratoryPage'

const duplicateMessage = 'Este escenario ya está guardado. Modifica alguno de sus valores para guardar una nueva alternativa'
const labels = {
  name: 'Nombre del escenario',
  budget: '¿Con cuánto dinero contarías? (MXN)',
  unitCost: '¿Cuánto costaría cada actividad? (MXN)',
  plannedUnits: '¿Cuántas actividades quieres realizar?',
  operationalCapacity: '¿Cuántas actividades podrían realizarse como máximo? (opcional)',
  assumptions: 'Condiciones y notas del escenario',
}
const base = { name: 'Original', budget: '100', unitCost: '100', plannedUnits: '100', operationalCapacity: '100', assumptions: 'Notas originales' }
function setValues(values: Partial<typeof base>) {
  for (const key of Object.keys(values) as (keyof typeof base)[]) fireEvent.change(screen.getByLabelText(labels[key]), { target: { value: values[key] } })
}
function savedCards() {
  const list = screen.queryByLabelText('Tus escenarios')
  return list ? within(list).queryAllByRole('article') : []
}
async function saveOriginal(overrides: Partial<typeof base> = {}) {
  const user = userEvent.setup()
  render(<LaboratoryPage />)
  setValues({ ...base, ...overrides })
  await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
  expect(savedCards()).toHaveLength(1)
  return user
}
afterEach(() => vi.restoreAllMocks())

describe('guardar escenarios sin duplicados', () => {
  it('impide guardar repetidos aunque cambien nombre y notas, conservando el original', async () => {
    const user = await saveOriginal()
    await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
    expect(screen.getByRole('alert')).toHaveTextContent(duplicateMessage)
    setValues({ name: 'Otro nombre', assumptions: 'Notas diferentes' })
    await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
    expect(savedCards()).toHaveLength(1)
    expect(savedCards()[0]).toHaveAccessibleName('Original')
    expect(savedCards()[0]).toHaveTextContent('Notas originales')
    expect(savedCards()[0]).not.toHaveTextContent('Notas diferentes')
    expect(screen.getByRole('alert')).toHaveTextContent(duplicateMessage)
    // Un duplicado no bloquea las exportaciones del borrador ni del original.
    expect(screen.getByRole('button', { name: 'Descargar resultados en PDF' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Descargar resultados en PNG' })).toBeEnabled()
    expect(within(savedCards()[0]).getByRole('button', { name: 'Descargar PDF' })).toBeEnabled()
    expect(within(savedCards()[0]).getByRole('button', { name: 'Descargar PNG' })).toBeEnabled()
  })

  it('considera iguales 100, 100.0 y 100.00 en los cuatro campos numéricos', async () => {
    const user = await saveOriginal()
    for (const suffix of ['.0', '.00']) {
      setValues({ budget: `100${suffix}`, unitCost: `100${suffix}`, plannedUnits: `100${suffix}`, operationalCapacity: `100${suffix}` })
      await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
      expect(savedCards()).toHaveLength(1)
      expect(screen.getByRole('alert')).toHaveTextContent(duplicateMessage)
    }
  })

  it.each(['budget', 'unitCost', 'plannedUnits', 'operationalCapacity'] as const)('permite guardar una alternativa al cambiar sólo %s', async key => {
    const user = await saveOriginal()
    await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
    expect(screen.getByRole('alert')).toHaveTextContent(duplicateMessage)
    setValues({ [key]: '101' })
    expect(screen.queryByText(duplicateMessage)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
    expect(savedCards()).toHaveLength(2)
    expect(screen.queryByText(duplicateMessage)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Descargar comparación en PDF' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Descargar comparación en PNG' })).toBeEnabled()
  })

  it('permite los mismos valores con una estrategia distinta', async () => {
    const user = await saveOriginal()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await user.click(screen.getAllByRole('button', { name: 'Elegir esta estrategia' })[0])
    setValues({ ...base, name: 'Estrategia diferente' })
    await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
    expect(savedCards()).toHaveLength(2)
    expect(savedCards()[0]).toHaveTextContent('Guía de pasos con vocabulario claro')
    expect(savedCards()[1]).toHaveTextContent('Localizador de fuentes y requisitos verificados')
    expect(screen.queryByText(duplicateMessage)).not.toBeInTheDocument()
  })

  it('comprueba todos los escenarios guardados sin alterar la selección de comparación', async () => {
    const user = await saveOriginal()
    setValues({ name: 'Segunda alternativa', budget: '200' })
    await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
    setValues({ name: 'Copia del primero', budget: '100' })
    await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
    expect(savedCards()).toHaveLength(2)
    for (const card of savedCards()) expect(within(card).getByRole('checkbox')).toBeChecked()
    expect(screen.getByRole('alert')).toHaveTextContent(duplicateMessage)
    expect(screen.getByRole('button', { name: 'Descargar comparación en PNG' })).toBeEnabled()
  })

  it('distingue capacidad operativa omitida de cero y detecta repetidos con capacidad omitida', async () => {
    const user = await saveOriginal({ operationalCapacity: '' })
    await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
    expect(savedCards()).toHaveLength(1)
    expect(screen.getByRole('alert')).toHaveTextContent(duplicateMessage)
    setValues({ operationalCapacity: '0' })
    await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
    expect(savedCards()).toHaveLength(2)
    setValues({ operationalCapacity: '' })
    await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
    expect(savedCards()).toHaveLength(2)
    expect(screen.getByRole('alert')).toHaveTextContent(duplicateMessage)
  })

  it('permite volver a guardar los mismos valores después de eliminar el original', async () => {
    const user = await saveOriginal()
    await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
    expect(screen.getByRole('alert')).toHaveTextContent(duplicateMessage)
    await user.click(screen.getByRole('button', { name: 'Eliminar Original' }))
    expect(savedCards()).toHaveLength(0)
    expect(screen.queryByText(duplicateMessage)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Guardar escenario' }))
    expect(savedCards()).toHaveLength(1)
    expect(savedCards()[0]).toHaveAccessibleName('Original')
  })
})
