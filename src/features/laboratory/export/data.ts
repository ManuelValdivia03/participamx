import { calculateScenario, formatMXN, formatNumber } from '../calculations'
import { strategyById } from '../strategies'
import { scenarioDiagnosis } from '../diagnosis'
import { proposalNotice } from '../strategyDetails'
import type { SavedScenario, ScenarioDraft, ScenarioMetrics, Strategy } from '../types'

export type ScenarioReport = {
  draft: ScenarioDraft
  strategy: Strategy
  metrics: ScenarioMetrics
  rows: [string, string][]
  diagnosis: string[]
  indicators: string[]
  limitations: string[]
}

export type ComparisonReport = {
  scenarios: [ScenarioReport, ScenarioReport]
  differentUnits: boolean
  differences: string[]
  limitations: string[]
}

export function prepareScenarioReport(draft: ScenarioDraft): ScenarioReport {
  const strategy = strategyById(draft.strategyId)
  const metrics = calculateScenario(draft)
  if (metrics.errors.length > 0) throw new Error('No se puede exportar un escenario con datos incompletos o inválidos.')
  const diagnosis = scenarioDiagnosis(metrics, strategy.unit)
  const operationKnown = metrics.operationalCapacity !== null
  return {
    draft,
    strategy,
    metrics,
    rows: [
      ['Presupuesto disponible', formatMXN(metrics.budget)],
      ['Costo por actividad', formatMXN(metrics.unitCost)],
      ['Actividades planificadas', `${formatNumber(metrics.plannedUnits)} ${strategy.unit}`],
      ['Capacidad de trabajo indicada', operationKnown ? `${formatNumber(metrics.operationalCapacity)} ${strategy.unit}` : 'No indicada'],
      ['Costo total', formatMXN(metrics.projectedCost)],
      [metrics.remainingBudget !== null && metrics.remainingBudget < 0 ? 'Déficit presupuestario (saldo)' : 'Dinero restante', formatMXN(metrics.remainingBudget)],
      ['Parte del presupuesto utilizada', metrics.budgetPercent === null ? 'No disponible' : `${formatNumber(metrics.budgetPercent, 1)}%`],
      ['Actividades que podrías pagar', formatCapacity(metrics.theoreticalCapacity, strategy.unit)],
      ['Actividades que podrías completar', formatCapacity(metrics.feasibleCapacity, strategy.unit)],
    ],
    diagnosis: [
      diagnosis.title, diagnosis.budget, diagnosis.operation,
    ],
    indicators: strategy.indicators,
    limitations: [...strategy.limitations, 'Fuente: valores hipotéticos escritos por la persona usuaria; no son costos ni capacidades oficiales del INE o de los OPLE.', 'Los costos y recursos son supuestos del escenario.', 'Este reporte no predice votos, abstención ni participación electoral.', proposalNotice],
  }
}

export function prepareComparisonReport(scenarios: SavedScenario[]): ComparisonReport {
  if (scenarios.length !== 2) throw new Error('Selecciona exactamente dos escenarios válidos para exportar la comparación.')
  let reports: [ScenarioReport, ScenarioReport]
  try {
    reports = scenarios.map(prepareScenarioReport) as [ScenarioReport, ScenarioReport]
  } catch {
    throw new Error('Sólo se pueden comparar escenarios válidos.')
  }
  const differentUnits = reports[0].strategy.unit !== reports[1].strategy.unit
  return {
    scenarios: reports,
    differentUnits,
    differences: [
      `Dinero disponible: ${describeDifference(reports[0].metrics.budget, reports[1].metrics.budget)}`,
      `Costo total: ${describeDifference(reports[0].metrics.projectedCost, reports[1].metrics.projectedCost)}`,
      differentUnits ? 'Las capacidades no se comparan como equivalentes porque las unidades son distintas.' :       `Actividades que podrías completar: ${describeCountDifference(reports[0].metrics.feasibleCapacity, reports[1].metrics.feasibleCapacity, reports[0].strategy.unit)}`,
    ],
    limitations: ['La comparación depende de los datos escritos en cada escenario.', 'Los costos y recursos son supuestos, no cifras oficiales.', 'No se elaboran rankings de eficacia electoral ni predicciones de participación.'],
  }
}

function describeDifference(first: number | null, second: number | null) {
  if (first === null || second === null) return 'no permite comparar'
  const delta = second - first
  const percent = first === 0 ? '' : ` (${formatNumber(Math.abs(delta / first * 100), 1)}%)`
  return `${delta === 0 ? 'mantiene la misma cantidad' : delta > 0 ? `aumenta ${formatMXN(delta)}` : `disminuye ${formatMXN(Math.abs(delta))}`}${percent}`
}

function describeCountDifference(first: number | null, second: number | null, unit: string) {
  if (first === null || second === null) return 'no permite comparar'
  const firstWhole = Math.floor(first)
  const secondWhole = Math.floor(second)
  const delta = secondWhole - firstWhole
  return `${delta === 0 ? 'mantiene la misma cantidad' : delta > 0 ? `aumenta ${formatNumber(delta)} ${unit}` : `disminuye ${formatNumber(Math.abs(delta))} ${unit}`}`
}

function formatCapacity(value: number | null, unit: string) {
  return value === null ? 'No disponible' : `${formatNumber(Math.floor(value))} ${unit}`
}
