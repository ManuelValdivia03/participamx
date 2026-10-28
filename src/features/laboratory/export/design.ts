import { createPdfDocument, type PdfPage } from './pdfDocument'
import type { ComparisonReport, ScenarioReport } from './data'

const pageWidth = 595
const pageHeight = 842
const margin = 44
const contentWidth = pageWidth - margin * 2
const colors = {
  background: [255, 255, 255],
  text: [0, 0, 0],
  secondaryText: [0, 0, 0],
  heading: [0, 0, 0],
  accent: [137, 99, 166],
  border: [221, 211, 227],
  card: [245, 240, 248],
  warm: [193, 117, 82],
}

export function renderScenarioPdf(report: ScenarioReport) {
  const page = createPage()
  let y = header(page, 'Reporte de escenario')
  y = sectionTitle(page, 'Escenario', y)
  y = paragraph(page, `Nombre: ${report.draft.name}`, y)
  y = paragraph(page, `Estrategia: ${report.strategy.name}`, y)
  y = paragraph(page, report.strategy.description, y)
  y = paragraph(page, `Fecha de generación: ${new Intl.DateTimeFormat('es-MX', { dateStyle: 'long' }).format(new Date())}`, y)
  y = sectionTitle(page, 'Resultados calculados', y - 8)
  y = table(page, report.rows, y)
  y = sectionTitle(page, 'Diagnóstico', y - 8)
  report.diagnosis.forEach(item => { y = paragraph(page, item, y) })
  y = chart(page, 'Dinero utilizado', report.metrics.budgetPercent ?? 0, `${report.metrics.budgetPercent === null ? 'No disponible' : `${report.metrics.budgetPercent.toFixed(1)}%`}`, y)
  y = chart(page, 'Actividades frente a lo que podrías completar', report.metrics.plannedUnits !== null && report.metrics.feasibleCapacity ? Math.min(report.metrics.plannedUnits / report.metrics.feasibleCapacity * 100, 100) : 0, `${report.metrics.plannedUnits === null ? 'No disponible' : formatCapacity(report.metrics.plannedUnits, report.strategy.unit)} / ${formatCapacity(report.metrics.feasibleCapacity, report.strategy.unit)}`, y)
  const continuationPages = createFlowPages([
    ['Supuestos escritos', [report.draft.assumptions || 'No se escribieron supuestos.']],
    ['Indicadores para una evaluación posterior', report.indicators],
    ['Advertencias y limitaciones', report.limitations],
  ])
  return createPdfDocument([page, ...continuationPages].map((item, index, pages) => withFooter(item, index + 1, pages.length)))
}

export function renderComparisonPdf(report: ComparisonReport) {
  const [first, second] = report.scenarios
  const page = createPage()
  let y = header(page, 'Reporte de comparación')
  y = paragraph(page, `Fecha de generación: ${new Intl.DateTimeFormat('es-MX', { dateStyle: 'long' }).format(new Date())}`, y)
  y = sectionTitle(page, 'Escenarios comparados', y - 8)
  y = table(page, [
    ['Escenario A', `${first.draft.name} · ${first.strategy.name}`],
    ['Escenario B', `${second.draft.name} · ${second.strategy.name}`],
    ['Dinero disponible', `${format(first.metrics.budget)} / ${format(second.metrics.budget)}`],
    ['Costo total', `${format(first.metrics.projectedCost)} / ${format(second.metrics.projectedCost)}`],
    ['Dinero restante', `${format(first.metrics.remainingBudget)} / ${format(second.metrics.remainingBudget)}`],
    ['Actividades planeadas', `${first.metrics.plannedUnits} ${first.strategy.unit} / ${second.metrics.plannedUnits} ${second.strategy.unit}`],
    ['Actividades que podrías completar', `${formatCapacity(first.metrics.feasibleCapacity, first.strategy.unit)} / ${formatCapacity(second.metrics.feasibleCapacity, second.strategy.unit)}`],
  ], y)
  y = sectionTitle(page, 'Gráficas comparativas', y - 8)
  y = comparisonChart(page, 'Costo total', first.metrics.projectedCost, second.metrics.projectedCost, y, format)
  if (!report.differentUnits) y = comparisonChart(page, 'Actividades que podrías completar', first.metrics.feasibleCapacity, second.metrics.feasibleCapacity, y, value => formatCapacity(value, first.strategy.unit))
  y = sectionTitle(page, 'Diferencias', y - 8)
  report.differences.forEach(item => { y = paragraph(page, item, y) })
  const continuationPages = createFlowPages([
    ['Supuestos del escenario A', [first.draft.assumptions || 'No se escribieron supuestos.']],
    ['Supuestos del escenario B', [second.draft.assumptions || 'No se escribieron supuestos.']],
    ['Limitaciones', [...report.limitations, ...(report.differentUnits ? ['Advertencia: las unidades de las estrategias no son compatibles para una comparación directa.'] : [])]],
  ])
  return createPdfDocument([page, ...continuationPages].map((item, index, pages) => withFooter(item, index + 1, pages.length)))
}

function format(value: number | null) { return value === null ? 'No disponible' : new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(value) }
function formatCapacity(value: number | null, unit: string) { return value === null ? 'No disponible' : `${new Intl.NumberFormat('es-MX', { maximumFractionDigits: 0 }).format(Math.floor(value))} ${unit}` }
function createPage(): PdfPage { const page = { commands: [] as string[] }; rect(page, 0, 0, pageWidth, pageHeight, colors.background); return page }
function header(page: PdfPage, title: string) { line(page, margin, pageHeight - 82, pageWidth - margin, pageHeight - 82, colors.border); text(page, 'ParticipaMX', margin, pageHeight - 42, 17, colors.heading, true); text(page, title, margin, pageHeight - 70, 19, colors.text, true); return pageHeight - 105 }
function withFooter(page: PdfPage, number: number, total: number) { line(page, margin, 38, pageWidth - margin, 38, colors.border); text(page, 'ParticipaMX · Exploración hipotética · No predice resultados electorales', margin, 23, 8, colors.secondaryText); text(page, `Página ${number} de ${total}`, pageWidth - 100, 23, 8, colors.secondaryText); return page }
function sectionTitle(page: PdfPage, title: string, y: number) { text(page, title, margin, y, 12, colors.heading, true); return y - 20 }
function paragraph(page: PdfPage, value: string, y: number) { wrap(value, 92).forEach(item => { if (y > 52) text(page, item, margin, y, 9.5, colors.text); y -= 14 }); return y - 3 }
function table(page: PdfPage, rows: [string, string][], y: number) {
  const labelX = margin + 8
  const valueX = margin + 205
  const valueWidth = 48
  rows.forEach(([label, value]) => {
    const labelLines = wrap(label, 30)
    const valueLines = wrap(value, valueWidth)
    const rowHeight = Math.max(labelLines.length, valueLines.length) * 13 + 10
    const top = y + 4
    const bottom = y - rowHeight + 4
    rect(page, margin, bottom, contentWidth, rowHeight, colors.card)
    line(page, margin, top, pageWidth - margin, top, colors.border)
    line(page, margin, bottom, pageWidth - margin, bottom, colors.border)
    line(page, margin + 195, bottom, margin + 195, top, colors.border)
    labelLines.forEach((item, index) => text(page, item, labelX, y - 8 - index * 13, 8.5, colors.heading, true))
    valueLines.forEach((item, index) => text(page, item, valueX, y - 8 - index * 13, 8.5, colors.text))
    y -= rowHeight
  })
  return y - 6
}
function chart(page: PdfPage, title: string, value: number, label: string, y: number) {
  const barY = y - 22
  const barHeight = 14
  const filledWidth = Math.max(0, Math.min(value, 100)) / 100 * contentWidth
  text(page, title, margin, y, 9, colors.heading, true)
  rect(page, margin, barY, contentWidth, barHeight, colors.card)
  rect(page, margin, barY, filledWidth, barHeight, colors.accent)
  strokeRect(page, margin, barY, contentWidth, barHeight, colors.border)
  text(page, label, margin, barY - 16, 8.5, colors.secondaryText)
  return barY - 35
}
function comparisonChart(page: PdfPage, title: string, first: number | null, second: number | null, y: number, formatter: (value: number | null) => string) {
  const max = Math.max(first ?? 0, second ?? 0, 1)
  const barHeight = 14
  const barWidth = 300
  text(page, title, margin, y, 9, colors.heading, true)
  const values: [number | null, number[]][] = [[first, colors.accent], [second, colors.warm]]
  values.forEach(([value, color], index) => {
    const rowY = y - 23 - index * 30
    const filledWidth = Math.max(0, Number(value) / max * barWidth)
    rect(page, margin + 76, rowY - 4, barWidth, barHeight, colors.card)
    rect(page, margin + 76, rowY - 4, Math.max(filledWidth, 2), barHeight, color)
    strokeRect(page, margin + 76, rowY - 4, barWidth, barHeight, colors.border)
    text(page, `Escenario ${index === 0 ? 'A' : 'B'}`, margin, rowY, 8.5, colors.text)
    text(page, formatter(value as number | null), margin + 385, rowY, 8.5, colors.text)
  })
  return y - 88
}
function createFlowPages(blocks: [string, string[]][]) {
  const pages: PdfPage[] = []
  let page = createPage()
  let y = header(page, 'Información complementaria')
  const nextPage = () => { pages.push(page); page = createPage(); y = header(page, 'Información complementaria · continuación') }
  blocks.forEach(([title, values]) => {
    if (y < 110) nextPage()
    y = sectionTitle(page, title, y)
    values.forEach(value => wrap(value, 92).forEach(lineValue => {
      if (y < 65) nextPage()
      text(page, lineValue, margin, y, 9.5, colors.text)
      y -= 14
    }))
    y -= 5
  })
  pages.push(page)
  return pages
}
function wrap(value: string, max: number) { const lines: string[] = []; let lineValue = ''; value.split(/\s+/).forEach(word => { if ((lineValue + ' ' + word).trim().length > max) { lines.push(lineValue); lineValue = word } else lineValue = `${lineValue} ${word}`.trim() }); if (lineValue) lines.push(lineValue); return lines }
function text(page: PdfPage, value: string, x: number, y: number, size: number, _color: number[], bold = false) { page.commands.push(`BT 0 0 0 rg /${bold ? 'F2' : 'F1'} ${size} Tf ${x} ${y} Td <${encodeWinAnsi(value)}> Tj ET`) }
function line(page: PdfPage, x1: number, y1: number, x2: number, y2: number, color: number[]) { page.commands.push(`${color.join(' ')} RG 0.7 w ${x1} ${y1} m ${x2} ${y2} l S`) }
function rect(page: PdfPage, x: number, y: number, width: number, height: number, color: number[]) { page.commands.push(`${color.join(' ')} rg ${x} ${y} ${width} ${height} re f`) }
function strokeRect(page: PdfPage, x: number, y: number, width: number, height: number, color: number[]) {
  line(page, x, y, x + width, y, color)
  line(page, x, y + height, x + width, y + height, color)
  line(page, x, y, x, y + height, color)
  line(page, x + width, y, x + width, y + height, color)
}
function encodeWinAnsi(value: string) { const map: Record<string, number> = { 'á': 0xe1, 'é': 0xe9, 'í': 0xed, 'ó': 0xf3, 'ú': 0xfa, 'Á': 0xc1, 'É': 0xc9, 'Í': 0xcd, 'Ó': 0xd3, 'Ú': 0xda, 'ñ': 0xf1, 'Ñ': 0xd1, 'ü': 0xfc, 'Ü': 0xdc, '¿': 0xbf, '¡': 0xa1, '€': 0x80, '•': 0x95, '·': 0xb7, '–': 0x96, '—': 0x97, '…': 0x85 }; return Array.from(value).map(character => map[character] ?? (character.charCodeAt(0) <= 255 ? character.charCodeAt(0) : 0x3f)).map(code => code.toString(16).padStart(2, '0')).join('') }
