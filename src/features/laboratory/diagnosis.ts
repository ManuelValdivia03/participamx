import { formatMXN, formatNumber } from './calculations'
import type { ScenarioMetrics } from './types'

export function scenarioDiagnosis(metrics: ScenarioMetrics, unit: string) {
  const budgetDeficit = metrics.remainingBudget !== null && metrics.remainingBudget < 0
  const operationDeficit = metrics.operationalCapacity !== null && metrics.plannedUnits !== null && metrics.plannedUnits > metrics.operationalCapacity
  const title = metrics.errors.length ? 'Completa la información para revisar el escenario' : budgetDeficit ? 'El escenario supera el presupuesto disponible' : operationDeficit ? 'El plan supera la capacidad operativa indicada' : metrics.operationalCapacity === null ? 'El presupuesto alcanza; falta indicar la capacidad operativa' : 'El dinero y la capacidad alcanzan con estos datos'
  const budget = budgetDeficit
    ? `Se necesitarían ${formatMXN(Math.abs(metrics.remainingBudget!))} adicionales. Con el presupuesto indicado podrían financiarse ${formatNumber(Math.floor(metrics.theoreticalCapacity ?? 0))} ${unit} completas.`
    : 'El presupuesto disponible cubre el costo del plan según los supuestos escritos.'
  const operation = metrics.operationalCapacity === null ? 'Capacidad operativa no indicada; no se puede confirmar la factibilidad operativa.' : operationDeficit ? `La capacidad operativa es insuficiente: se planificaron ${formatNumber(metrics.plannedUnits)} y se indicó un máximo de ${formatNumber(metrics.operationalCapacity)} ${unit}.` : 'La capacidad operativa indicada es suficiente para el plan.'
  return { title, budget, operation }
}
