import { describe, expect, it } from 'vitest'
import { createComparisonPdf, createScenarioPdf, extractPdfText, safeDownloadFileName as safeFileName } from './export'
import type { SavedScenario, ScenarioDraft } from './types'

const draft: ScenarioDraft = {
  name: 'Guías para ciudadanía / abril',
  strategyId: 'clear-guide',
  budget: '10000',
  unitCost: '200',
  plannedUnits: '30',
  operationalCapacity: '40',
  assumptions: 'Escenario ficticio para revisar costos, actividades y capacidad.',
}

function saved(id: string, values: Partial<ScenarioDraft> = {}): SavedScenario {
  return { ...draft, ...values, id, createdAt: '2025-01-01T00:00:00.000Z' }
}

describe('exportación PDF del laboratorio', () => {
  it('genera un PDF individual con los datos del escenario', async () => {
    const pdf = createScenarioPdf(draft)
    expect(pdf.type).toBe('application/pdf')
    expect((await pdf.arrayBuffer()).byteLength).toBeGreaterThan(500)
    const text = await extractPdfText(pdf)
    expect(text).toContain('ParticipaMX')
    expect(text).toContain(draft.name)
    expect(text).toContain('Costo total')
    expect(text).toContain('$10,000')
    const source = new TextDecoder('latin1').decode(await pdf.arrayBuffer())
    expect(source).toContain('0 0 0 rg')
    expect(source).toContain('255 255 255 rg')
    expect(source).not.toMatch(/BT\s+(?!0 0 0 rg)/)
  })

  it('rechaza escenarios incompletos', () => {
    expect(() => createScenarioPdf({ ...draft, budget: '' })).toThrow('datos incompletos')
  })

  it('genera una comparación sólo con dos escenarios válidos', async () => {
    const pdf = createComparisonPdf([saved('one'), saved('two', { budget: '12000' })])
    expect((await pdf.arrayBuffer()).byteLength).toBeGreaterThan(500)
    const text = await extractPdfText(pdf)
    expect(text).toContain('Guías para ciudadanía')
    expect(text).toContain('Escenario B')
    const source = new TextDecoder('latin1').decode(await pdf.arrayBuffer())
    expect(source).toContain('0 0 0 rg')
    expect(source).toContain('137 99 166 rg')
    expect(source).toContain('193 117 82 rg')
    expect(() => createComparisonPdf([saved('one')])).toThrow('exactamente dos')
  })

  it('rechaza la comparación si alguno de los escenarios es inválido', () => {
    expect(() => createComparisonPdf([saved('one'), saved('two', { unitCost: '' })])).toThrow('escenarios válidos')
  })

  it('crea nombres de archivo seguros y legibles', () => {
    expect(safeFileName('  Guías / ciudadanía: abril 2025  ')).toBe('Guias_ciudadania_abril_2025')
    expect(safeFileName('???')).toBe('sin_nombre')
  })

  it('no genera texto de resultados no finitos', async () => {
    const pdf = createScenarioPdf({ ...draft, unitCost: '0.0000000000000000001', plannedUnits: '1' })
    const bytes = new Uint8Array(await pdf.arrayBuffer())
    const content = new TextDecoder().decode(bytes)
    expect(content).not.toContain('NaN')
    expect(content).not.toContain('Infinity')
  })

  it('conserva supuestos extensos en páginas adicionales', async () => {
    const assumptions = Array.from({ length: 240 }, () => 'Condición documentada del escenario para revisar recursos y límites.').join(' ')
    const pdf = createScenarioPdf({ ...draft, assumptions })
    const text = await extractPdfText(pdf)
    expect(text).toContain('Condición documentada del escenario')
    expect((await pdf.arrayBuffer()).byteLength).toBeGreaterThan(3000)
  })

  it('presenta capacidades como actividades enteras y no como importes', async () => {
    const pdf = createScenarioPdf({ ...draft, unitCost: '65', plannedUnits: '10' })
    const text = await extractPdfText(pdf)
    expect(text).toContain('153 guías revisadas')
    expect(text).not.toContain('153.84615384615384')
    expect(text).not.toContain('153.85 guías revisadas')
  })

  it('mantiene visibles las barras y la tabla comparativa', async () => {
    const pdf = createComparisonPdf([saved('one'), saved('two', { budget: '12000', plannedUnits: '25' })])
    const source = new TextDecoder('latin1').decode(await pdf.arrayBuffer())
    const text = await extractPdfText(pdf)
    expect(source).toContain('re f')
    expect(text).toContain('Escenario A')
    expect(text).toContain('Escenario B')
    expect(text).not.toContain('guías revisadas / $')
  })
})
