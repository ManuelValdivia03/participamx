import type { CitizenProfile, ProfileCrossCell, ProfileEnrichment, ProfileValueStatus } from './types'

export const profileIds = ['young_favorable', 'young_unfavorable', 'adult_favorable', 'adult_unfavorable', 'older_favorable', 'older_unfavorable'] as const
export const profileSectionLabels = { U: 'Urbana', R: 'Rural', M: 'Mixta' } as const
export const valueStatusLabels: Record<ProfileValueStatus, string> = {
  defined: 'Dato disponible', missing: 'Sin información', undefined: 'Sin denominador definido',
  low_support: 'Soporte reducido', unavailable_category: 'Categoría no disponible en esta elección',
}
export function percent(value: number | null | undefined) {
  return value == null || !Number.isFinite(value) ? 'Sin información' : `${new Intl.NumberFormat('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value * 100)} %`
}
export function points(value: number | null | undefined) {
  return value == null || !Number.isFinite(value) ? 'Sin información' : `${value > 0 ? '+' : value < 0 ? '−' : ''}${new Intl.NumberFormat('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Math.abs(value))} pp`
}
export function count(value: number | null | undefined) {
  return value == null || !Number.isFinite(value) ? 'Sin información' : new Intl.NumberFormat('es-MX', { maximumFractionDigits: 0 }).format(value)
}
function requireValue(condition: unknown): asserts condition { if (!condition) throw new Error('El enriquecimiento de perfiles no tiene el contrato esperado') }
function object(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value) }
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const integer = (v: unknown): v is number => finite(v) && Number.isSafeInteger(v) && v >= 0
const rate = (v: unknown) => v === null || (finite(v) && v >= 0 && v <= 1)
const close = (a: number, b: number) => Math.abs(a - b) < 1e-9

function validateCell(value: unknown): asserts value is ProfileCrossCell {
  requireValue(object(value) && typeof value.code === 'string' && typeof value.status === 'string' && value.status in valueStatusLabels)
  for (const field of ['LN', 'SV', 'NV', 'NS', 'specifiedCount', 'sourceRows']) requireValue(value[field] === null || integer(value[field]))
  for (const field of ['nominalShare', 'participation', 'reference']) requireValue(rate(value[field]))
  requireValue(value.deltaPp === null || finite(value.deltaPp))
  for (const field of ['availableCells', 'eligibleCells', 'undefinedCells']) requireValue(integer(value[field]))
  requireValue((value.eligibleCells as number) <= (value.availableCells as number))
  if (finite(value.SV) && finite(value.NV) && finite(value.NS) && finite(value.LN) && finite(value.specifiedCount)) {
    requireValue(value.SV + value.NV + value.NS === value.LN && value.SV + value.NV === value.specifiedCount)
    if (value.specifiedCount === 0) requireValue(value.participation === null && value.deltaPp === null)
    else requireValue(finite(value.participation) && close(value.participation, value.SV / value.specifiedCount))
  }
  if (finite(value.participation) && finite(value.reference)) requireValue(finite(value.deltaPp) && close(value.deltaPp, (value.participation - value.reference) * 100))
}

export function validateProfileEnrichment(value: unknown, expectedYear = 2024): ProfileEnrichment {
  requireValue(object(value) && value.schemaVersion === 'profiles-enriched-1' && value.year === expectedYear && [2009,2012,2015,2018,2021,2024].includes(expectedYear) && value.rateUnit === 'proportion' && value.namesStatus === 'agreed')
  requireValue(Array.isArray(value.profiles) && value.profiles.length === 6)
  const ids = new Set<string>()
  for (const p of value.profiles) {
    requireValue(object(p) && typeof p.id === 'string' && profileIds.some(id => id === p.id) && !ids.has(p.id))
    ids.add(p.id)
    for (const field of ['name', 'ageBand', 'subtitle', 'description', 'distinctive', 'sexAnalysis', 'sectionAnalysis', 'territoryAnalysis']) requireValue(typeof p[field] === 'string' && !!p[field])
    requireValue(p.nameStatus === 'agreed' && Array.isArray(p.findings) && p.findings.every(v => typeof v === 'string'))
    requireValue(rate(p.participation) && rate(p.reference) && rate(p.nominalShare) && (p.deltaPp === null || finite(p.deltaPp)))
    requireValue(object(p.counts))
    for (const field of ['LN', 'SV', 'NV', 'NS', 'specified_count', 'source_row_count']) requireValue(integer(p.counts[field]))
    requireValue((p.counts.SV as number) + (p.counts.NV as number) === p.counts.specified_count)
    requireValue((p.counts.specified_count as number) + (p.counts.NS as number) === p.counts.LN)
    if (p.counts.specified_count === 0) requireValue(p.participation === null && p.deltaPp === null)
    else requireValue(finite(p.participation) && close(p.participation, (p.counts.SV as number) / (p.counts.specified_count as number)))
    if (finite(p.participation) && finite(p.reference)) requireValue(finite(p.deltaPp) && close(p.deltaPp, (p.participation - p.reference) * 100))
    requireValue(integer(p.segments) && integer(p.municipalities) && integer(p.states))
    requireValue(object(p.quality))
    for (const field of ['availableCells', 'eligibleCells', 'undefinedCells', 'signReversals', 'reversalLN']) requireValue(integer(p.quality[field]))
    for (const field of ['nearReferenceShare', 'highNsShare', 'reversalShare', 'reversalNominalShare']) requireValue(rate(p.quality[field]))
    requireValue(p.quality.signReversals as number <= (p.quality.eligibleCells as number))
    for (const [name, expected] of [['sexCells', 2], ['sectionCells', 3], ['jointCells', 6]] as const) {
      requireValue(Array.isArray(p[name]) && p[name].length === expected)
      p[name].forEach(validateCell)
      const keys = p[name].map(c => name === 'jointCells' ? `${c.sexCode}|${c.code}` : c.code)
      const expectedKeys = name === 'sexCells' ? ['0', '1'] : name === 'sectionCells' ? ['U', 'R', 'M'] : ['0|U', '0|R', '0|M', '1|U', '1|R', '1|M']
      requireValue(new Set(keys).size === expected && expectedKeys.every(k => keys.includes(k)))
      for (const [field, totalField] of [['LN', 'LN'], ['SV', 'SV'], ['NV', 'NV'], ['NS', 'NS'], ['specifiedCount', 'specified_count']] as const) {
        const measured = p[name].map(c => c[field])
        // Una conciliación parcial no convierte conteos ausentes en cero.
        if (measured.every(v => v !== null)) requireValue(measured.reduce((sum, v) => sum + v, 0) === p.counts[totalField])
      }
    }
    requireValue(object(p.additionalCategory) && p.additionalCategory.code === '2' && p.additionalCategory.value === null && p.additionalCategory.status === (expectedYear === 2024 ? 'low_support' : 'unavailable_category') && typeof p.additionalCategory.explanation === 'string')
  }
  if (expectedYear === 2024) {
    requireValue(object(value.transversalFinding) && value.transversalFinding.id === 'interaction_18-34_R_U' && value.transversalFinding.year === 2024)
    for (const field of ['municipalContrastPp', 'nominalContrastPp']) requireValue(finite(value.transversalFinding[field]))
    for (const field of ['municipalities', 'LN', 'specifiedCount']) requireValue(integer(value.transversalFinding[field]))
    for (const field of ['directionShare', 'annualNominalShare']) requireValue(rate(value.transversalFinding[field]))
    requireValue(typeof value.transversalFinding.title === 'string' && typeof value.transversalFinding.ageBand === 'string')
  } else requireValue(value.transversalFinding === null)
  requireValue(object(value.heterogeneity))
  for (const field of ['eligibleCells', 'signReversals', 'bothBeyond2Pp']) requireValue(integer(value.heterogeneity[field]))
  requireValue(object(value.sources) && Object.values(value.sources).every(s => object(s) && typeof s.path === 'string' && typeof s.sha256 === 'string' && /^[0-9a-f]{64}$/.test(s.sha256)))
  return value as unknown as ProfileEnrichment
}

export function enrichProfiles(profiles: CitizenProfile[], enrichment: ProfileEnrichment, year: number): CitizenProfile[] {
  requireValue(year === enrichment.year && profiles.length === 6 && new Set(profiles.map(p => p.id)).size === 6)
  return profileIds.map(id => {
    const base = profiles.find(p => p.id === id)
    const extra = enrichment.profiles.find(p => p.id === id)
    requireValue(base && extra && base.nominalList === extra.counts.LN && base.segmentCount === extra.segments)
    requireValue(base.participation !== null && extra.participation !== null && close(base.participation, extra.participation * 100))
    requireValue(base.peerReference != null && extra.reference !== null && close(base.peerReference, extra.reference * 100))
    return { ...base, name: extra.name, summary: extra.distinctive, description: extra.description, ageBand: extra.ageBand, enriched: extra,
      characteristics: extra.findings }
  })
}
