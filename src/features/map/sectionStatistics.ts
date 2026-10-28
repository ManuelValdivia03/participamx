import { ratio, sumCounts, type Counts } from './territorialData'
import type { LayerValue, ThematicTerritory } from './thematicData'

export const sectionTypes = ['U', 'R', 'M'] as const
export type SectionType = typeof sectionTypes[number]
export const sectionLabels: Record<SectionType, string> = { U: 'Urbana', R: 'Rural', M: 'Mixta' }
export const sectionCaution = 'U/R/M clasifica el tipo de sección electoral. No identifica residencia individual, localidad, nivel socioeconómico ni causas de participación.'
export interface SectionCell extends Counts { section_type: SectionType }
export interface SectionProfile { code: string; name: string; complete: true; totals: Counts; sections: SectionCell[] }
export interface SectionIndex { schema_version: 'section-statistics-1'; election_year: number; state_code: null; national: SectionProfile; states: SectionProfile[] }
export interface SectionMunicipalities { schema_version: 'section-statistics-1'; election_year: number; state_code: string; data: SectionProfile[] }
export function sectionSupport(counts: Counts): boolean { return counts.LN >= 100 && counts.SV + counts.NV >= 100 && counts.source_row_count >= 5 }

// El máximo de LN compara las mismas proporciones sin redondear ni ordenar U/R/M.
export function dominantSectionValue(profile: SectionProfile | null, mapped = true): LayerValue {
  const empty = (status: LayerValue['status']): LayerValue => ({ status, value: null, numerator: null, denominator: null, counts: null, highNs: false })
  if (!mapped) return empty('unmapped')
  if (!profile || !profile.complete) return empty('missing')
  if (profile.totals.LN <= 0) return { ...empty('undefined'), counts: profile.totals, denominator: profile.totals.LN }
  const maximum = Math.max(...profile.sections.map(cell => cell.LN))
  const leaders = profile.sections.filter(cell => cell.LN === maximum)
  const dominantTypes = sectionTypes.filter(kind => leaders.some(cell => cell.section_type === kind))
  const sufficient = sectionSupport(profile.totals) && leaders.every(sectionSupport)
  return { value: null, numerator: maximum, denominator: profile.totals.LN, counts: profile.totals, dominantTypes,
    status: sufficient ? 'defined' : 'low_support',
    highNs: [profile.totals, ...leaders].some(counts => (ratio(counts.NS, counts.LN) ?? 0) >= .1) }
}

export function dominantSectionLabel(result: LayerValue): string {
  if (!result.dominantTypes?.length) return 'Sin información'
  return `${result.dominantTypes.length > 1 ? 'Empate · ' : ''}${result.dominantTypes.map(kind => sectionLabels[kind]).join(' / ')}`
}

export function rankSectionTerritories(rows: ThematicTerritory[]): ThematicTerritory[] {
  return [...rows].sort((a, b) => {
    const validA = a.result.status === 'defined', validB = b.result.status === 'defined'
    if (validA !== validB) return validA ? -1 : 1
    if (validA && validB) {
      const delta = BigInt(a.result.numerator!) * BigInt(b.result.denominator!) - BigInt(b.result.numerator!) * BigInt(a.result.denominator!)
      if (delta !== 0n) return delta > 0n ? -1 : 1
    }
    return a.code.localeCompare(b.code)
  })
}

export function sectionValue(profile: SectionProfile | null, kind: SectionType, participation: boolean, mapped = true): LayerValue {
  const empty = (status: LayerValue['status']): LayerValue => ({ status, value: null, numerator: null, denominator: null, counts: null, highNs: false })
  if (!mapped) return empty('unmapped')
  if (!profile) return empty('missing')
  // Sólo una partición completa conciliada permite un cero nominal por tipo no observado.
  const cell = profile.sections.find(row => row.section_type === kind)
  const counts = cell ?? sumCounts([])
  const numerator = participation ? counts.SV : counts.LN
  const denominator = participation ? counts.SV + counts.NV : profile.totals.LN
  const value = ratio(numerator, denominator)
  const sufficient = cell ? sectionSupport(counts) : !participation && sectionSupport(profile.totals)
  return { counts, numerator, denominator, value, status: value === null ? 'undefined' : sufficient ? 'defined' : 'low_support', highNs: (ratio(counts.NS, counts.LN) ?? 0) >= .1 }
}

export function validateSectionProfile(profile: SectionProfile): SectionProfile {
  if (!profile || profile.complete !== true || typeof profile.name !== 'string' || !/^(national|\d{2}|\d{5})$/.test(profile.code) || !Array.isArray(profile.sections) || !profile.sections.length) throw new Error('Desglose por sección inválido')
  const keys = new Set<string>()
  for (const cell of profile.sections) {
    if (!sectionTypes.includes(cell.section_type) || keys.has(cell.section_type)) throw new Error('Tipo de sección desconocido o duplicado')
    keys.add(cell.section_type)
  }
  for (const counts of [profile.totals, ...profile.sections]) {
    for (const field of ['LN', 'SV', 'NV', 'NS', 'source_row_count'] as const) if (!Number.isSafeInteger(counts?.[field]) || counts[field] < 0) throw new Error('Conteo de sección inválido')
    if (counts.LN !== counts.SV + counts.NV + counts.NS) throw new Error('LN de sección no concilia')
  }
  const total = sumCounts(profile.sections)
  for (const field of Object.keys(total) as (keyof Counts)[]) if (total[field] !== profile.totals[field]) throw new Error('Tipos de sección no concilian con el total')
  return profile
}

export function validateSectionPayload(value: unknown, year: number, stateCode: string | null): SectionIndex | SectionMunicipalities {
  const data = value as SectionIndex | SectionMunicipalities
  if (!data || data.schema_version !== 'section-statistics-1' || data.election_year !== year || data.state_code !== stateCode) throw new Error('Elección o ámbito de sección incorrectos')
  const profiles = data.state_code === null ? data.states : data.data
  if (!Array.isArray(profiles) || (!stateCode && profiles.length !== 32)) throw new Error('Cobertura de sección inválida')
  const keys = new Set<string>()
  for (const profile of profiles) {
    validateSectionProfile(profile)
    if (keys.has(profile.code) || (stateCode ? !new RegExp(`^${stateCode}\\d{3}$`).test(profile.code) : !/^(0[1-9]|[12]\d|3[0-2])$/.test(profile.code))) throw new Error('Clave de sección incorrecta')
    keys.add(profile.code)
  }
  if (data.state_code === null) {
    validateSectionProfile(data.national)
    if (data.national.code !== 'national') throw new Error('Clave nacional incorrecta')
    const sums = sumCounts(profiles.map(row => row.totals))
    for (const field of Object.keys(sums) as (keyof Counts)[]) if (sums[field] !== data.national.totals[field]) throw new Error('Total nacional de sección incorrecto')
    for (const kind of sectionTypes) {
      const subtotal = sumCounts(profiles.flatMap(row => row.sections.filter(cell => cell.section_type === kind)))
      const national = data.national.sections.find(cell => cell.section_type === kind)
      for (const field of Object.keys(subtotal) as (keyof Counts)[]) if (subtotal[field] !== (national?.[field] ?? 0)) throw new Error('Marginal nacional de sección incorrecto')
    }
  }
  return data
}
