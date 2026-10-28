import { prepareComparisonReport, prepareScenarioReport } from './data'
import { downloadPdf, safeFileName } from './download'
import { renderComparisonPdf, renderScenarioPdf } from './design'
import { validatePdf } from './pdfDocument'
import type { SavedScenario, ScenarioDraft } from '../types'

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

export { extractPdfText } from './pdfDocument'
export { safeFileName, safeFileName as safeDownloadFileName } from './download'
