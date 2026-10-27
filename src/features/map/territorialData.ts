export const ageBands = ['18-34', '35-59', '60-100'] as const
export const sexCodes = ['0', '1'] as const
export const electionYears = [2009, 2012, 2015, 2018, 2021, 2024] as const

export interface Counts {
  LN: number
  SV: number
  NV: number
  NS: number
  source_row_count: number
}

export interface DemographicSegment extends Counts {
  age_band: string
  sex_code: string
  sufficient_support: boolean
  high_ns: boolean
  assignment_status: string
}

export interface MunicipalityDemographics {
  ine_code: string
  municipality_name: string
  totals: Counts
  profile_ids: string[]
  segments: DemographicSegment[]
  complementary: DemographicSegment[]
}

export type DemographicProfile = Pick<MunicipalityDemographics, 'totals' | 'segments' | 'complementary'>
export interface TerritorySummary extends DemographicProfile {
  schema_version: 'territorial-summary-1'
  election_year: number
  level: 'national' | 'state'
  state_code: string | null
  territory_name: string
  profile_ids: string[]
  registered_sexes: string[]
}

export const sexLabels: Record<string, string> = { '0': 'Hombres', '1': 'Mujeres', '2': 'No binario' }

export function aggregateSegments(rows: DemographicSegment[]): DemographicSegment[] {
  const groups = new Map<string, DemographicSegment[]>()
  for (const row of rows) {
    const key = `${row.age_band}:${row.sex_code}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(row)
  }
  return [...groups.values()].map(group => {
    const counts = sumCounts(group)
    return { ...counts, age_band: group[0].age_band, sex_code: group[0].sex_code,
      sufficient_support: counts.LN >= 100 && counts.SV + counts.NV >= 100 && counts.source_row_count >= 5,
      high_ns: (ratio(counts.NS, counts.LN) ?? 0) >= .1, assignment_status: 'aggregated_summary' }
  }).sort((a, b) => a.age_band.localeCompare(b.age_band) || a.sex_code.localeCompare(b.sex_code))
}

export type DemographicAxis = 'crossed' | 'age' | 'sex'
export function demographicBreakdown(data: DemographicProfile, axis: DemographicAxis) {
  const all = [...data.segments, ...data.complementary]
  const sexes = ['0', '1', ...(all.some(row => row.sex_code === '2') ? ['2'] : [])]
  const groups = axis === 'sex' ? sexes.map(sex => ({ key: sex, label: sexLabels[sex], sex_code: sex, age_band: null }))
    : axis === 'age' ? ageBands.map(band => ({ key: band, label: `${band.replace('-', '–')} años`, sex_code: null, age_band: band }))
    : ageBands.flatMap(band => sexes.map(sex => ({ key: `${band}:${sex}`, label: sexLabels[sex], sex_code: sex, age_band: band })))
  const universe = all.filter(row => axis === 'sex' || ageBands.some(band => band === row.age_band))
  const included = sumCounts(universe)
  const rows = groups.map(group => {
    const matching = universe.filter(row => (!group.sex_code || row.sex_code === group.sex_code) && (!group.age_band || row.age_band === group.age_band))
    const counts = matching.length ? sumCounts(matching) : null
    return { ...group, counts, participation: counts ? turnout(counts) : null,
      distribution: counts ? ratio(counts.SV, included.SV) : null,
      sufficient_support: counts ? counts.LN >= 100 && counts.SV + counts.NV >= 100 && counts.source_row_count >= 5 : null,
      high_ns: counts ? (ratio(counts.NS, counts.LN) ?? 0) >= .1 : null }
  })
  return { rows, included, sexes }
}

export function validateTerritorySummary(value: unknown, year: number, state: string | null): TerritorySummary {
  const data = value as TerritorySummary
  if (!data || data.schema_version !== 'territorial-summary-1' || data.election_year !== year ||
    data.state_code !== state || data.level !== (state ? 'state' : 'national') || typeof data.territory_name !== 'string' ||
    !Array.isArray(data.registered_sexes) || data.registered_sexes.some(sex => !sexLabels[sex]) ||
    !Array.isArray(data.profile_ids) || !Array.isArray(data.segments) || !Array.isArray(data.complementary)) throw new Error('Resumen territorial inválido')
  // Reutiliza las mismas invariantes de conteos y soporte; no crea una clave geográfica ficticia.
  validateProfileCounts(data)
  return data
}

export interface TerritorialResponse {
  schema_version: 'territorial-explorer-1'
  election_year: number
  state_code: string
  rate_unit: 'proportion'
  source: string
  warnings: string[]
  data: MunicipalityDemographics[]
}

export function normalizeStateCode(value: string | number): string {
  const raw = String(value)
  if (!/^\d{1,2}$/.test(raw) || Number(raw) < 1 || Number(raw) > 32) {
    throw new Error('Clave estatal INE inválida')
  }
  return raw.padStart(2, '0')
}

export function normalizeMunicipalityCode(value: string | number): string {
  const raw = String(value)
  if (!/^\d{1,3}$/.test(raw) || Number(raw) < 1) throw new Error('Clave municipal INE inválida')
  return raw.padStart(3, '0')
}

export function normalizeIneCode(state: string | number, municipality: string | number): string {
  return normalizeStateCode(state) + normalizeMunicipalityCode(municipality)
}

export function ratio(numerator: number | null, denominator: number | null): number | null {
  return numerator !== null && denominator !== null && Number.isFinite(numerator) &&
    Number.isFinite(denominator) && denominator > 0 ? numerator / denominator : null
}

export function turnout(counts: Pick<Counts, 'SV' | 'NV'>): number | null {
  return ratio(counts.SV, counts.SV + counts.NV)
}

export function differencePoints(local: number | null, national: number | null): number | null {
  return local === null || national === null ? null : (local - national) * 100
}

export function isCoreSegment(segment: Pick<DemographicSegment, 'age_band' | 'sex_code'>): boolean {
  return ageBands.some(band => band === segment.age_band) && sexCodes.some(sex => sex === segment.sex_code)
}

export function sumCounts(rows: Counts[]): Counts {
  return rows.reduce((sum, row) => ({
    LN: sum.LN + row.LN, SV: sum.SV + row.SV, NV: sum.NV + row.NV,
    NS: sum.NS + row.NS, source_row_count: sum.source_row_count + row.source_row_count,
  }), { LN: 0, SV: 0, NV: 0, NS: 0, source_row_count: 0 })
}

// La distribución usa sólo SV de las celdas presentes del núcleo mostrado.
export function demographicCells(municipality: MunicipalityDemographics) {
  const total = sumCounts(municipality.segments)
  return ageBands.flatMap(age_band => sexCodes.map(sex_code => {
    const segment = municipality.segments.find(row => row.age_band === age_band && row.sex_code === sex_code) ?? null
    return {
      age_band, sex_code, segment,
      participation: segment ? turnout(segment) : null,
      distribution: segment ? ratio(segment.SV, total.SV) : null,
    }
  }))
}

function checkCounts(counts: Counts): void {
  for (const field of ['LN', 'SV', 'NV', 'NS', 'source_row_count'] as const) {
    if (!Number.isSafeInteger(counts[field]) || counts[field] < 0) throw new Error(`Conteo inválido: ${field}`)
  }
  if (counts.LN !== counts.SV + counts.NV + counts.NS) throw new Error('LN no concilia con SV+NV+NS')
}

export function validateProfileCounts(data: DemographicProfile): void {
  checkCounts(data.totals)
  const keys = new Set<string>()
  for (const [rows, core] of [[data.segments, true], [data.complementary, false]] as const) for (const row of rows) {
    checkCounts(row)
    const key = `${row.age_band}:${row.sex_code}`
    if (keys.has(key) || isCoreSegment(row) !== core || !sexLabels[row.sex_code] ||
      row.sufficient_support !== (row.LN >= 100 && row.SV + row.NV >= 100 && row.source_row_count >= 5) ||
      row.high_ns !== ((ratio(row.NS, row.LN) ?? 0) >= .1)) throw new Error('Celda o soporte no conciliados')
    keys.add(key)
  }
  const total = sumCounts([...data.segments, ...data.complementary])
  for (const field of ['LN', 'SV', 'NV', 'NS', 'source_row_count'] as const) if (total[field] !== data.totals[field]) throw new Error(`Total no conciliado: ${field}`)
}

export function validateTerritorialResponse(value: unknown, year: number, stateCode: string): TerritorialResponse {
  const result = value as TerritorialResponse
  const state = normalizeStateCode(stateCode)
  if (!result || result.schema_version !== 'territorial-explorer-1' || result.election_year !== year ||
    !electionYears.some(item => item === year) || result.state_code !== state || result.rate_unit !== 'proportion' ||
    typeof result.source !== 'string' || !Array.isArray(result.warnings) ||
    !result.warnings.every(warning => typeof warning === 'string') || !Array.isArray(result.data)) {
    throw new Error('Contrato territorial inválido')
  }
  const seen = new Set<string>()
  for (const municipality of result.data) {
    if (!/^\d{5}$/.test(municipality.ine_code) || !municipality.ine_code.startsWith(state) ||
      normalizeIneCode(state, municipality.ine_code.slice(2)) !== municipality.ine_code ||
      seen.has(municipality.ine_code) || typeof municipality.municipality_name !== 'string' ||
      !Array.isArray(municipality.profile_ids) || !municipality.profile_ids.every(id => typeof id === 'string') ||
      !Array.isArray(municipality.segments) || !Array.isArray(municipality.complementary)) {
      throw new Error('Municipio o clave territorial inválidos')
    }
    seen.add(municipality.ine_code)
    checkCounts(municipality.totals)
    const cells = new Set<string>()
    for (const [rows, core] of [[municipality.segments, true], [municipality.complementary, false]] as const) {
      for (const row of rows) {
        checkCounts(row)
        const key = `${row.age_band}:${row.sex_code}`
        const support = row.LN >= 100 && row.SV + row.NV >= 100 && row.source_row_count >= 5
        if (typeof row.age_band !== 'string' || typeof row.sex_code !== 'string' || cells.has(key) ||
          isCoreSegment(row) !== core || row.sufficient_support !== support ||
          row.high_ns !== ((ratio(row.NS, row.LN) ?? 0) >= .1) || typeof row.assignment_status !== 'string') {
          throw new Error('Celda demográfica o soporte inválidos')
        }
        cells.add(key)
      }
    }
    const total = sumCounts([...municipality.segments, ...municipality.complementary])
    for (const field of ['LN', 'SV', 'NV', 'NS', 'source_row_count'] as const) {
      if (total[field] !== municipality.totals[field]) throw new Error(`Total municipal no conciliado: ${field}`)
    }
  }
  return result
}

export function formatCount(value: number | null): string {
  return value === null ? 'No disponible' : value.toLocaleString('es-MX')
}

export function formatPercent(value: number | null, maximumFractionDigits = 2): string {
  return value === null ? 'No disponible' : `${(value * 100).toLocaleString('es-MX', { minimumFractionDigits: 1, maximumFractionDigits })} %`
}

export function formatPoints(value: number | null): string {
  return value === null ? 'No disponible' : `${value > 0 ? '+' : ''}${value.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} pp`
}
