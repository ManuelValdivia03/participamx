import { jsPDF } from 'jspdf'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { buildComparisonPlan, buildScenarioPlan, buildStrategyPlan, renderReportPng, reportColors, type ReportPlan } from './export/design'
import { prepareComparisonReport, prepareScenarioReport } from './export/data'
import { getStrategyDetail } from './strategyDetails'
import { strategies } from './strategies'
import type { ScenarioDraft } from './types'
import { createScenarioPdf, extractPdfText } from './export'

const draft: ScenarioDraft = { name: 'Escenario de prueba', strategyId: 'clear-guide', budget: '10000', unitCost: '200', plannedUnits: '30', operationalCapacity: '40', assumptions: 'Supuesto documentado.' }
afterEach(() => vi.restoreAllMocks())

function checkLayout(plan: ReportPlan) {
  const metrics = new jsPDF({ unit: 'pt' })
  for (const page of plan.pages) {
    const texts = page.filter(item => item.kind === 'text')
    expect(texts.some(item => item.y >= 108 && item.y < plan.height - 52)).toBe(true)
    texts.forEach((item, index) => {
      expect(item.y).toBeLessThanOrEqual(plan.height - 18)
      metrics.setFont('helvetica', item.bold ? 'bold' : 'normal'); metrics.setFontSize(item.size)
      const right = item.x + metrics.getTextWidth(item.text)
      for (const other of texts.slice(index + 1)) {
        const overlapY = item.y - item.size < other.y && item.y > other.y - other.size
        if (overlapY) expect(right <= other.x + .5 || other.x + other.maxWidth <= item.x + .5).toBe(true)
      }
    })
  }
}

describe('paginación compartida de PDF y PNG', () => {
  it('acomoda las seis estrategias, escenarios y comparaciones sin recortes ni superposiciones', () => {
    const plans = strategies.map(strategy => buildStrategyPlan(getStrategyDetail(strategy)))
    plans.push(buildScenarioPlan(prepareScenarioReport(draft)))
    plans.push(buildComparisonPlan(prepareComparisonReport([{ ...draft, id: 'a', createdAt: '' }, { ...draft, id: 'b', createdAt: '', strategyId: 'accessible-library' }])))
    plans.forEach(checkLayout)
  })

  it('conserva supuestos y nombres extensos hasta la última palabra', async () => {
    const assumptions = `${'Condición extensa de operación y recursos. '.repeat(600)}MARCADOR_FINAL`
    const report = prepareScenarioReport({ ...draft, name: 'Nombre largo '.repeat(20), assumptions })
    checkLayout(buildScenarioPlan(report))
    expect(await extractPdfText(createScenarioPdf(report.draft))).toContain('MARCADOR_FINAL')
  })

  it('muestra déficit y operación por separado, aun con costo mayor al presupuesto', async () => {
    const report = prepareScenarioReport({ ...draft, budget: '100', unitCost: '200', operationalCapacity: '2' })
    const text = await extractPdfText(createScenarioPdf(report.draft))
    expect(text).toContain('Se necesitarían $5,900.00 adicionales')
    expect(text).toContain('0 guías revisadas completas')
    expect(text).toContain('capacidad operativa es insuficiente')
    checkLayout(buildScenarioPlan(report))
  })

  it('representa el cero con barras vacías y distingue capacidades ausentes', () => {
    const plan = buildScenarioPlan(prepareScenarioReport({ ...draft, budget: '0', unitCost: '0', plannedUnits: '0', operationalCapacity: '' }))
    expect(plan.pages.flat().filter(item => item.kind === 'rect' && item.height === 11 && [reportColors.purple, reportColors.warning].includes(item.color))).toHaveLength(0)
    const text = plan.pages.flat().filter(item => item.kind === 'text').map(item => item.text).join(' ')
    expect(text).toContain('No disponible')
    expect(text).not.toMatch(/NaN|Infinity/)
    checkLayout(plan)
  })

  it('usa la misma escala para presupuesto y costo aun cuando hay déficit', () => {
    const plan = buildScenarioPlan(prepareScenarioReport({ ...draft, budget: '100', unitCost: '200', plannedUnits: '1' }))
    const bars = plan.pages.flat().filter(item => item.kind === 'rect' && item.height === 11 && [reportColors.purple, reportColors.warning].includes(item.color))
    expect(bars[0].kind === 'rect' && bars[1].kind === 'rect' && bars[0].width / bars[1].width).toBeCloseTo(.5)
  })

  it('dibuja en PNG todos los textos y páginas a 1600 px de ancho y divide documentos largos', async () => {
    const texts: string[] = [], sizes: [number, number][] = []
    const ctx = { fillStyle: '', font: '', fillRect: vi.fn(), save: vi.fn(), restore: vi.fn(), scale: vi.fn(), translate: vi.fn(), fillText: (text: string) => texts.push(text) }
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx as unknown as CanvasRenderingContext2D)
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (this: HTMLCanvasElement, callback) { sizes.push([this.width, this.height]); callback(new Blob(['png'], { type: 'image/png' })) })
    const plan = buildScenarioPlan(prepareScenarioReport({ ...draft, assumptions: `${'Condición de operación. '.repeat(2000)}FIN_DEL_DOCUMENTO` }))
    const images = await renderReportPng(plan)
    expect(images.length).toBeGreaterThan(1)
    expect(images.every(blob => blob.type === 'image/png')).toBe(true)
    expect(sizes.every(([w, h]) => w === 1600 && h <= 14000)).toBe(true)
    expect(texts).toEqual(plan.pages.flatMap(page => page.filter(item => item.kind === 'text').map(item => item.text)))
    expect(texts.join(' ')).toContain('FIN_DEL_DOCUMENTO')
  })

  it('comunica errores de canvas en la exportación PNG', async () => {
    const plan = buildScenarioPlan(prepareScenarioReport(draft))
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
    await expect(renderReportPng(plan)).rejects.toThrow('preparar la imagen PNG')
  })
})
