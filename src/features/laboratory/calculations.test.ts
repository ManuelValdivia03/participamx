import { describe, expect, it } from 'vitest'
import { calculateScenario, formatMXN } from './calculations'
import type { ScenarioDraft } from './types'

const draft = (overrides: Partial<ScenarioDraft> = {}): ScenarioDraft => ({ name: 'Referencia', strategyId: 'clear-guide', budget: '10000', unitCost: '200', plannedUnits: '30', operationalCapacity: '', assumptions: '', ...overrides })

describe('calculateScenario', () => {
  it('calcula el escenario de referencia reproducible', () => {
    const result = calculateScenario(draft())
    expect(result.projectedCost).toBe(6000)
    expect(result.budgetPercent).toBe(60)
    expect(result.remainingBudget).toBe(4000)
    expect(result.theoreticalCapacity).toBe(50)
    expect(result.errors).toEqual([])
  })
  it('mantiene visible un déficit presupuestario y de recursos', () => {
    const result = calculateScenario(draft({ budget: '1000', plannedUnits: '30', operationalCapacity: '20' }))
    expect(result.remainingBudget).toBe(-5000)
    expect(result.feasibleCapacity).toBe(5)
    expect(result.resourceDifference).toBe(-10)
  })
  it('no crea Infinity cuando presupuesto o costo son cero', () => {
    expect(calculateScenario(draft({ budget: '0' })).theoreticalCapacity).toBe(0)
    const zeroCost = calculateScenario(draft({ unitCost: '0' }))
    expect(zeroCost.theoreticalCapacity).toBeNull()
    expect(zeroCost.budgetPercent).toBe(0)
  })
  it('rechaza campos vacíos, negativos, texto, infinitos y unidades fraccionarias', () => {
    for (const overrides of [{ budget: '' }, { unitCost: '-1' }, { plannedUnits: 'texto' }, { budget: 'Infinity' }, { plannedUnits: '1.5' }, { operationalCapacity: '2.2' }]) {
      expect(calculateScenario(draft(overrides)).errors.length).toBeGreaterThan(0)
    }
  })
  it('aplica una restricción operativa sólo cuando se cuantifica', () => {
    expect(calculateScenario(draft()).feasibleCapacity).toBeNull()
    const result = calculateScenario(draft({ operationalCapacity: '40' }))
    expect(result.feasibleCapacity).toBe(40)
    expect(result.resourceDifference).toBe(10)
  })
  it('conserva moneda mexicana y precisión decimal', () => {
    expect(formatMXN(1234.5)).toContain('$1,234.50')
    const overflow = calculateScenario(draft({ budget: '1e308', unitCost: '1e308', plannedUnits: '2' }))
    expect(overflow.projectedCost).toBeNull()
    expect(overflow.errors).toContain('El costo previsto excede el límite numérico permitido.')
  })
})
