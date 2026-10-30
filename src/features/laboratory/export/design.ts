import { jsPDF } from 'jspdf'
import { formatMXN, formatNumber } from '../calculations'
import { proposalNotice, type StrategyDetail } from '../strategyDetails'
import type { ComparisonReport, ScenarioReport } from './data'

export type DrawCommand =
  | { kind: 'text'; x: number; y: number; text: string; size: number; bold: boolean; color: string; maxWidth: number }
  | { kind: 'rect'; x: number; y: number; width: number; height: number; color: string }
export type ReportPlan = { width: number; height: number; title: string; pages: DrawCommand[][] }
export const reportColors = { paper: '#fffdf9', ink: '#382742', muted: '#66566f', purple: '#694382', soft: '#f3edf6', line: '#d9cddd', warning: '#a95536' }
const width = 595.28, height = 841.89, margin = 40, bottom = height - 52, contentWidth = width - margin * 2
const plain = (value: string) => value.replace(/[–—−]/g, '-').replace(/[“”]/g, '"').replace(/[‘’]/g, "'").replace(/≥/g, '>=').replace(/≤/g, '<=').replace(/→/g, ' -> ').replace(/×/g, 'x').replace(/Σ/g, 'suma ')

// El mismo plano paginado alimenta PDF con texto nativo y PNG con canvas.
class ReportLayout {
  plan: ReportPlan
  y = 0
  private metrics = new jsPDF({ unit: 'pt', format: 'a4' })
  private get page() { return this.plan.pages[this.plan.pages.length - 1] }
  constructor(title: string) { this.plan = { width, height, title, pages: [] }; this.nextPage() }
  private rect(x: number, y: number, w: number, h: number, color: string) {
    this.page.push({ kind: 'rect', x, y, width: w, height: h, color })
  }
  private lines(value: string, maxWidth: number, size: number, bold = false): string[] {
    this.metrics.setFont('helvetica', bold ? 'bold' : 'normal'); this.metrics.setFontSize(size)
    return this.metrics.splitTextToSize(plain(value), maxWidth) as string[]
  }
  private text(value: string, x: number, y: number, size = 10.5, bold = false, color = reportColors.ink, maxWidth = contentWidth) {
    this.page.push({ kind: 'text', x, y, text: plain(value), size, bold, color, maxWidth })
  }
  private nextPage() {
    this.plan.pages.push([])
    this.rect(0, 0, width, height, reportColors.paper)
    this.rect(0, 0, width, 10, reportColors.purple)
    this.text('ParticipaMX', margin, 45, 24, true, reportColors.purple)
    this.text('Laboratorio de Estrategias Cívicas · Exploración hipotética', margin, 65, 10, false, reportColors.muted)
    this.text(this.plan.title, margin, 84, 10, true, reportColors.muted)
    this.y = 108
  }
  private ensure(space: number) { if (this.y + space > bottom) this.nextPage() }
  heading(value: string) {
    const lines = this.lines(value, contentWidth - 16, 13, true)
    this.ensure(lines.length * 18 + 48)
    this.rect(margin, this.y, 3, lines.length * 18 + 8, reportColors.purple)
    lines.forEach((line, i) => this.text(line, margin + 12, this.y + 17 + i * 18, 13, true, reportColors.purple, contentWidth - 16))
    this.y += lines.length * 18 + 20
  }
  paragraph(value: string, muted = false) {
    for (const line of this.lines(value, contentWidth, 10.5)) {
      this.ensure(15)
      this.text(line, margin, this.y + 10.5, 10.5, false, muted ? reportColors.muted : reportColors.ink)
      this.y += 15
    }
    this.y += 7
  }
  cards(rows: [string, string][]) {
    const gap = 10, cardWidth = (contentWidth - gap) / 2
    for (let i = 0; i < rows.length; i += 2) {
      const group = rows.slice(i, i + 2).map(([label, value]) => ({ label: this.lines(label, cardWidth - 24, 9.5), value: this.lines(value, cardWidth - 24, 13, true) }))
      const cardHeight = Math.max(...group.map(item => item.label.length * 13 + item.value.length * 18 + 24))
      this.ensure(cardHeight + gap)
      group.forEach((item, column) => {
        const x = margin + column * (cardWidth + gap)
        this.rect(x, this.y, cardWidth, cardHeight, reportColors.soft)
        item.label.forEach((line, row) => this.text(line, x + 12, this.y + 17 + row * 13, 9.5, false, reportColors.muted, cardWidth - 24))
        item.value.forEach((line, row) => this.text(line, x + 12, this.y + 19 + item.label.length * 13 + row * 18, 13, true, reportColors.purple, cardWidth - 24))
      })
      this.y += cardHeight + gap
    }
    this.y += 4
  }
  diagnosis(report: ScenarioReport) {
    this.heading('Diagnóstico del escenario')
    report.diagnosis.forEach(value => this.paragraph(value))
  }
  chart(title: string, rows: { label: string; value: number | null; formatted: string }[]) {
    const prepared = rows.map(row => ({ ...row, lines: this.lines(`${row.label}: ${row.formatted}`, contentWidth, 10) }))
    const titleLines = this.lines(title, contentWidth, 11, true)
    this.ensure(titleLines.length * 16 + prepared.reduce((sum, row) => sum + row.lines.length * 14 + 25, 0) + 14)
    titleLines.forEach(line => { this.text(line, margin, this.y + 11, 11, true); this.y += 16 })
    const max = Math.max(...rows.map(row => row.value ?? 0), 1)
    prepared.forEach((row, index) => {
      row.lines.forEach(line => { this.text(line, margin, this.y + 10, 10); this.y += 14 })
      this.rect(margin, this.y + 4, contentWidth, 11, reportColors.line)
      // Una barra cero permanece vacía; los valores comparten escala.
      if (row.value !== null && row.value > 0) this.rect(margin, this.y + 4, contentWidth * (row.value / max), 11, index === 0 ? reportColors.purple : reportColors.warning)
      this.y += 25
    })
    this.y += 14
  }
  finish() {
    const total = this.plan.pages.length
    this.plan.pages.forEach((commands, index) => {
      commands.push({ kind: 'rect', x: margin, y: height - 39, width: contentWidth, height: 0.7, color: reportColors.line })
      commands.push({ kind: 'text', x: margin, y: height - 23, text: 'ParticipaMX · Propuestas y escenarios hipotéticos', size: 8, bold: false, color: reportColors.muted, maxWidth: 380 })
      commands.push({ kind: 'text', x: width - 119, y: height - 23, text: `Página ${index + 1} de ${total}`, size: 8, bold: false, color: reportColors.muted, maxWidth: 79 })
    })
    validateReportPlan(this.plan)
    return this.plan
  }
}

function scenarioContent(layout: ReportLayout, report: ScenarioReport, label = 'Escenario') {
  layout.heading(`${label}: ${report.draft.name}`)
  layout.paragraph(`Estrategia: ${report.strategy.name}`)
  layout.paragraph(report.strategy.description, true)
  layout.cards(report.rows)
  layout.diagnosis(report)
  layout.chart('Presupuesto disponible frente a costo total · MXN', [
    { label: 'Disponible', value: report.metrics.budget, formatted: formatMXN(report.metrics.budget) },
    { label: 'Costo total', value: report.metrics.projectedCost, formatted: formatMXN(report.metrics.projectedCost) },
  ])
  layout.chart(`Actividades · ${report.strategy.unit}`, [
    { label: 'Planificadas', value: report.metrics.plannedUnits, formatted: formatNumber(report.metrics.plannedUnits) },
    { label: 'Financiables', value: report.metrics.theoreticalCapacity, formatted: capacity(report.metrics.theoreticalCapacity) },
    { label: 'Factibles (presupuesto y operación)', value: report.metrics.feasibleCapacity, formatted: capacity(report.metrics.feasibleCapacity) },
  ])
  layout.paragraph('Las barras comparten escala dentro de cada gráfica. Capacidades expresadas en actividades completas (redondeo hacia abajo); los cálculos originales se conservan.', true)
  layout.heading('Supuestos escritos')
  layout.paragraph(report.draft.assumptions || 'No se escribieron supuestos.')
  layout.heading('Indicadores para una evaluación posterior')
  report.indicators.forEach(value => layout.paragraph(value))
  layout.heading('Advertencias y limitaciones')
  report.limitations.forEach(value => layout.paragraph(value, true))
}
function capacity(value: number | null) { return value === null ? 'No disponible' : formatNumber(Math.floor(value)) }

export function buildScenarioPlan(report: ScenarioReport) {
  const layout = new ReportLayout('Reporte de escenario')
  scenarioContent(layout, report)
  return layout.finish()
}

export function buildComparisonPlan(report: ComparisonReport) {
  const layout = new ReportLayout('Reporte de comparación · Escenarios A y B')
  layout.heading('Lectura de la comparación')
  report.scenarios.forEach((item, index) => layout.paragraph(`Escenario ${index === 0 ? 'A' : 'B'}: ${item.draft.name} · ${item.strategy.name}`))
  report.differences.forEach(value => layout.paragraph(value))
  layout.chart('Costo total comparado · MXN', report.scenarios.map((item, index) => ({ label: `Escenario ${index === 0 ? 'A' : 'B'}`, value: item.metrics.projectedCost, formatted: formatMXN(item.metrics.projectedCost) })))
  if (!report.differentUnits) layout.chart(`Capacidad factible comparada · ${report.scenarios[0].strategy.unit}`, report.scenarios.map((item, index) => ({ label: `Escenario ${index === 0 ? 'A' : 'B'}`, value: item.metrics.feasibleCapacity, formatted: capacity(item.metrics.feasibleCapacity) })))
  report.limitations.forEach(value => layout.paragraph(value, true))
  if (report.differentUnits) layout.paragraph('Advertencia: las unidades son distintas. Las actividades y capacidades no son equivalentes y no se comparan directamente.')
  report.scenarios.forEach((item, index) => scenarioContent(layout, item, `Escenario ${index === 0 ? 'A' : 'B'}`))
  return layout.finish()
}

export function buildStrategyPlan(detail: StrategyDetail) {
  const layout = new ReportLayout('Detalle de estrategia · Contexto electoral 2024')
  layout.heading(detail.strategy.name)
  layout.paragraph(proposalNotice)
  detail.sections.forEach(section => {
    layout.heading(section.title)
    if (section.id === 'statistics') layout.cards(detail.statistics)
    else section.paragraphs.forEach(value => layout.paragraph(value))
  })
  return layout.finish()
}

export function validateReportPlan(plan: ReportPlan) {
  if (!plan.pages.length) throw new Error('El documento no tiene páginas.')
  const metrics = new jsPDF({ unit: 'pt' })
  for (const page of plan.pages) {
    if (!page.some(command => command.kind === 'text' && command.y >= 108 && command.y < bottom)) throw new Error('El documento contiene una página vacía.')
    for (const command of page) {
      if (command.kind === 'rect') {
        if (![command.x, command.y, command.width, command.height].every(Number.isFinite) || command.x < 0 || command.y < 0 || command.width < 0 || command.height < 0 || command.x + command.width > plan.width + .1 || command.y + command.height > plan.height + .1) throw new Error('Elemento fuera de los márgenes del documento.')
      } else {
        metrics.setFont('helvetica', command.bold ? 'bold' : 'normal'); metrics.setFontSize(command.size)
        if (command.y - command.size < 15 || command.y > plan.height - 18 || command.x < margin || command.x + command.maxWidth > plan.width - margin + .1 || metrics.getTextWidth(command.text) > command.maxWidth + .5) throw new Error('Texto fuera de los márgenes del documento.')
      }
    }
  }
}

export function renderReportPdf(plan: ReportPlan) {
  const pdf = new jsPDF({ unit: 'pt', format: [plan.width, plan.height], compress: false })
  pdf.setProperties({ title: `ParticipaMX · ${plan.title}`, author: 'ParticipaMX', subject: 'Exploración hipotética; sin efectos electorales demostrados' })
  plan.pages.forEach((page, index) => {
    if (index) pdf.addPage()
    page.forEach(command => {
      if (command.kind === 'rect') { pdf.setFillColor(command.color); pdf.rect(command.x, command.y, command.width, command.height, 'F') }
      else { pdf.setFont('helvetica', command.bold ? 'bold' : 'normal'); pdf.setFontSize(command.size); pdf.setTextColor(command.color); pdf.text(command.text, command.x, command.y) }
    })
  })
  return pdf.output('blob')
}

export async function renderReportPng(plan: ReportPlan): Promise<Blob[]> {
  const scale = 1600 / plan.width
  const pagePixels = Math.ceil(plan.height * scale)
  // Limita el alto del canvas para documentos extensos en dispositivos móviles.
  const perImage = Math.max(1, Math.floor(14000 / pagePixels))
  const images: Blob[] = []
  for (let start = 0; start < plan.pages.length; start += perImage) {
    const pages = plan.pages.slice(start, start + perImage)
    const canvas = document.createElement('canvas')
    canvas.width = 1600; canvas.height = pagePixels * pages.length
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('No se pudo preparar la imagen PNG.')
    ctx.fillStyle = reportColors.paper; ctx.fillRect(0, 0, canvas.width, canvas.height)
    pages.forEach((page, index) => {
      ctx.save(); ctx.translate(0, index * pagePixels); ctx.scale(scale, scale)
      page.forEach(command => {
        ctx.fillStyle = command.color
        if (command.kind === 'rect') ctx.fillRect(command.x, command.y, command.width, command.height)
        else { ctx.font = `${command.bold ? 'bold' : 'normal'} ${command.size}px Arial, sans-serif`; ctx.fillText(command.text, command.x, command.y, command.maxWidth) }
      })
      ctx.restore()
    })
    images.push(await new Promise<Blob>((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('No se pudo generar el PNG.')), 'image/png')))
    canvas.width = 0; canvas.height = 0
  }
  return images
}

export const renderScenarioPdf = (report: ScenarioReport) => renderReportPdf(buildScenarioPlan(report))
export const renderComparisonPdf = (report: ComparisonReport) => renderReportPdf(buildComparisonPlan(report))
