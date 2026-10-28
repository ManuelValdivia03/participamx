import type { ScenarioDraft, ScenarioMetrics } from './types'

const numberFrom = (value: string, label: string, optional = false, integer = false): { value: number | null; error?: string } => {
  if (value.trim() === '') return optional ? { value: null } : { value: null, error: `${label} es obligatorio.` }
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed < 0) return { value: null, error: `${label} debe ser un número finito igual o mayor que cero.` }
  if (integer && !Number.isInteger(parsed)) return { value: null, error: `${label} debe ser una cantidad entera.` }
  return { value: parsed }
}

export function calculateScenario(draft: ScenarioDraft): ScenarioMetrics {
  const budget = numberFrom(draft.budget, 'El presupuesto')
  const unitCost = numberFrom(draft.unitCost, 'El costo unitario')
  const plannedUnits = numberFrom(draft.plannedUnits, 'Las unidades planificadas', false, true)
  const operationalCapacity = numberFrom(draft.operationalCapacity, 'La capacidad operativa', true, true)
  const errors = [budget.error, unitCost.error, plannedUnits.error, operationalCapacity.error].filter((item): item is string => Boolean(item))
  const rawProjectedCost = unitCost.value !== null && plannedUnits.value !== null ? unitCost.value * plannedUnits.value : null
  const projectedCost = rawProjectedCost !== null && Number.isFinite(rawProjectedCost) ? rawProjectedCost : null
  if (rawProjectedCost !== null && projectedCost === null) errors.push('El costo previsto excede el límite numérico permitido.')
  const remainingBudget = budget.value !== null && projectedCost !== null ? budget.value - projectedCost : null
  const budgetPercent = budget.value !== null && projectedCost !== null && budget.value > 0 ? (projectedCost / budget.value) * 100 : null
  const rawTheoreticalCapacity = budget.value !== null && unitCost.value !== null && unitCost.value > 0 ? budget.value / unitCost.value : null
  const theoreticalCapacity = rawTheoreticalCapacity !== null && Number.isFinite(rawTheoreticalCapacity) ? rawTheoreticalCapacity : null
  if (rawTheoreticalCapacity !== null && theoreticalCapacity === null) errors.push('La capacidad teórica excede el límite numérico permitido.')
  const feasibleCapacity = theoreticalCapacity !== null && operationalCapacity.value !== null ? Math.min(theoreticalCapacity, operationalCapacity.value) : null
  const resourceDifference = plannedUnits.value !== null ? (operationalCapacity.value ?? theoreticalCapacity ?? plannedUnits.value) - plannedUnits.value : null
  return { budget: budget.value, unitCost: unitCost.value, plannedUnits: plannedUnits.value, operationalCapacity: operationalCapacity.value, projectedCost, budgetPercent, remainingBudget, theoreticalCapacity, feasibleCapacity, resourceDifference, errors }
}

export const formatMXN = (value: number | null) => value === null ? 'Sin información' : new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 }).format(value)
export const formatNumber = (value: number | null, digits = 0) => value === null ? 'Sin información' : new Intl.NumberFormat('es-MX', { maximumFractionDigits: digits }).format(value)
