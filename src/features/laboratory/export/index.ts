import { prepareComparisonReport, prepareScenarioReport } from './data'
import { downloadPdf, downloadPngs, safeFileName } from './download'
import { buildComparisonPlan, buildScenarioPlan, buildStrategyPlan, renderComparisonPdf, renderScenarioPdf, renderReportPdf, renderReportPng } from './design'
import { getStrategyDetail } from '../strategyDetails'
import { validatePdf } from './pdfDocument'
import type { SavedScenario, ScenarioDraft, Strategy } from '../types'

export function createScenarioPdf(draft: ScenarioDraft) {
  const blob = renderScenarioPdf(prepareScenarioReport(draft))
  if (!validatePdf(blob)) throw new Error('El reporte individual no produjo un PDF válido.')
  return blob
}

export function downloadScenarioPdf(draft: ScenarioDraft) {
  downloadPdf(createScenarioPdf(draft), `ParticipaMX_Escenario_${safeFileName(draft.name)}.pdf`)
}

export function createComparisonPdf(scenarios: SavedScenario[]) {
  const blob = renderComparisonPdf(prepareComparisonReport(scenarios))
  if (!validatePdf(blob)) throw new Error('El reporte comparativo no produjo un PDF válido.')
  return blob
}

export function downloadComparisonPdf(scenarios: SavedScenario[]) {
  downloadPdf(createComparisonPdf(scenarios), 'ParticipaMX_Comparacion.pdf')
}

export const createScenarioPng = (draft: ScenarioDraft) => renderReportPng(buildScenarioPlan(prepareScenarioReport(draft)))
export const createComparisonPng = (scenarios: SavedScenario[]) => renderReportPng(buildComparisonPlan(prepareComparisonReport(scenarios)))
export const createStrategyPdf = (strategy: Strategy) => renderReportPdf(buildStrategyPlan(getStrategyDetail(strategy)))
export const createStrategyPng = (strategy: Strategy) => renderReportPng(buildStrategyPlan(getStrategyDetail(strategy)))
export const downloadScenarioPng = (draft: ScenarioDraft) => downloadPngs(createScenarioPng(draft), `ParticipaMX_Escenario_${safeFileName(draft.name)}`)
export const downloadComparisonPng = (scenarios: SavedScenario[]) => downloadPngs(createComparisonPng(scenarios), 'ParticipaMX_Comparacion')
export const downloadStrategyPdf = (strategy: Strategy) => downloadPdf(createStrategyPdf(strategy), `ParticipaMX_Estrategia_${safeFileName(strategy.name)}.pdf`)
export const downloadStrategyPng = (strategy: Strategy) => downloadPngs(createStrategyPng(strategy), `ParticipaMX_Estrategia_${safeFileName(strategy.name)}`)

export { extractPdfText } from './pdfDocument'
export { safeFileName, safeFileName as safeDownloadFileName } from './download'
