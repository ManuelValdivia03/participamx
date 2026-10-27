import { formatPercent, ratio, sumCounts, validateTerritorySummary, type Counts, type DemographicProfile, type TerritorySummary } from './territorialData'
import { scaleClassIndex, type ThematicScale } from './thematicScale'

export const layerDefinitions = {
  participation: { group: 'participation', label: 'Participación ciudadana', kind: 'rate' },
  nonparticipation: { group: 'participation', label: 'No participación', kind: 'rate' },
  women: { group: 'sex', label: 'Mujeres en lista nominal', kind: 'composition', sex: '1' },
  men: { group: 'sex', label: 'Hombres en lista nominal', kind: 'composition', sex: '0' },
  women_participants: { group: 'sex', label: 'Mujeres entre participantes', kind: 'participant_composition', sex: '1' },
  men_participants: { group: 'sex', label: 'Hombres entre participantes', kind: 'participant_composition', sex: '0' },
  nonbinary: { group: 'sex', label: 'No binario', kind: 'composition', sex: '2' },
  age18_34: { group: 'age', label: '18–34 años', kind: 'composition', band: '18-34' },
  age35_59: { group: 'age', label: '35–59 años', kind: 'composition', band: '35-59' },
  age60_100: { group: 'age', label: '60–100 años', kind: 'composition', band: '60-100' },
} as const
export type LayerId = keyof typeof layerDefinitions
export type LayerGroup = 'participation' | 'sex' | 'age'
export function layerPalette(layer: LayerId): string {
  if (layer === 'women' || layer === 'women_participants') return 'rose'
  if (layer === 'men' || layer === 'men_participants') return 'blue'
  if (layer === 'nonparticipation') return 'warm'
  if (layer === 'age18_34') return 'teal'
  if (layer === 'age60_100') return 'amber'
  return 'purple'
}
export type LayerValue = {
  value: number | null
  numerator: number | null
  denominator: number | null
  counts: Counts | null
  status: 'defined' | 'low_support' | 'undefined' | 'missing' | 'unmapped' | 'unavailable_category'
  highNs: boolean
}
export type ThematicTerritory = { code: string; ineCode: string | null; name: string; result: LayerValue }
export interface TerritorialLayerIndex {
  schema_version: 'territorial-layers-1'
  election_year: number
  registered_sexes: string[]
  states: TerritorySummary[]
}

export function layerUniverse(layer: LayerId): string {
  const definition = layerDefinitions[layer]
  if (definition.kind === 'rate') return 'Participación especificada: participaron + no participaron. No incluye no especificados.'
  if (definition.kind === 'participant_composition') return 'Participaron en la categoría / total de participaciones registradas (SV). Todas las edades y sexos registrados; NS no se cuenta como participación.'
  if (definition.group === 'sex') return 'Lista nominal total: todas las edades, incluidas 101+, y categorías registradas. No es población censal.'
  return 'LN del grupo / lista nominal total de todas las edades y sexos registrados. 101+ sólo en el denominador.'
}

export function layerValue(profile: DemographicProfile | null, layer: LayerId, registeredSexes: readonly string[], mapped = true): LayerValue {
  const empty = (status: LayerValue['status']): LayerValue => ({ value: null, numerator: null, denominator: null, counts: null, status, highNs: false })
  if (!mapped) return empty('unmapped')
  if (!profile) return empty('missing')
  const definition = layerDefinitions[layer]
  if ('sex' in definition && !registeredSexes.includes(definition.sex)) return empty('unavailable_category')
  const cells = [...profile.segments, ...profile.complementary]
  const matches = 'sex' in definition ? cells.filter(cell => cell.sex_code === definition.sex)
    : 'band' in definition ? cells.filter(cell => cell.age_band === definition.band) : null
  if (matches && !matches.length) return empty('missing')
  const counts = matches ? sumCounts(matches) : profile.totals
  const numerator = layer === 'participation' || definition.kind === 'participant_composition' ? counts.SV : layer === 'nonparticipation' ? counts.NV : counts.LN
  const denominator = definition.kind === 'rate' ? counts.SV + counts.NV : definition.kind === 'participant_composition' ? profile.totals.SV : profile.totals.LN
  const value = ratio(numerator, denominator)
  const lowSupport = counts.LN < 100 || counts.SV + counts.NV < 100 || counts.source_row_count < 5
  return { value, numerator, denominator, counts, status: value === null ? 'undefined' : lowSupport ? 'low_support' : 'defined',
    highNs: (ratio(counts.NS, counts.LN) ?? 0) >= .1 }
}

export function layerStatusLabel(status: LayerValue['status']): string {
  return { defined: 'Con soporte exploratorio', low_support: 'Soporte reducido · fuera de la escala comparable',
    undefined: 'Sin información: denominador cero', missing: 'Sin información: combinación no observada',
    unmapped: 'Sin información: correspondencia INE pendiente', unavailable_category: 'Sin información: categoría no registrada en esta elección' }[status]
}

export function formatLayerPercent(value: number | null): string {
  return value === null ? 'Sin información' : formatPercent(value, value > 0 && value < .0001 ? 6 : 2)
}

export function layerExplanation(layer: LayerId): string {
  if (layer === 'participation') return 'Mayor porcentaje indica mayor participación observada, entre los registros con participación especificada.'
  if (layer === 'nonparticipation') return 'Mayor porcentaje indica mayor proporción de no participación especificada; no incluye NS.'
  const definition = layerDefinitions[layer]
  if ('sex' in definition) {
    const category = definition.sex === '1' ? 'mujeres' : definition.sex === '0' ? 'hombres' : 'la categoría No binario'
    return definition.kind === 'participant_composition'
      ? `Mayor porcentaje indica mayor proporción de participaciones registradas de ${category} sobre el total de participantes.`
      : `Mayor porcentaje indica mayor proporción de registros de ${category} en la lista nominal total.`
  }
  return 'band' in definition ? `Mayor porcentaje indica mayor proporción de registros nominales de ${definition.band} años sobre la lista nominal total.` : ''
}

export function thematicFill(result: LayerValue | undefined, scale: ThematicScale): string {
  if (result?.status === 'low_support') return 'var(--atlas-low-support)'
  if (result?.status !== 'defined' || result.value === null) return 'var(--atlas-no-data)'
  const index = scaleClassIndex(result.value, scale)
  return index === null ? 'var(--atlas-no-data)' : `var(--atlas-color-${scale.classes[index].colorLevel})`
}

export function validateLayerIndex(value: unknown, year: number): TerritorialLayerIndex {
  const index = value as TerritorialLayerIndex
  if (!index || index.schema_version !== 'territorial-layers-1' || index.election_year !== year || !Array.isArray(index.states) || index.states.length !== 32 ||
    !Array.isArray(index.registered_sexes) || !index.registered_sexes.length || index.registered_sexes.some(sex => !['0', '1', '2'].includes(sex)) || new Set(index.registered_sexes).size !== index.registered_sexes.length) throw new Error('Índice de capas inválido')
  const codes = new Set<string>()
  for (const state of index.states) {
    if (!state.state_code || !/^(0[1-9]|[12]\d|3[0-2])$/.test(state.state_code) || codes.has(state.state_code)) throw new Error('Entidad de capa duplicada o inválida')
    validateTerritorySummary(state, year, state.state_code)
    if (state.registered_sexes.join() !== index.registered_sexes.join()) throw new Error('Categorías de sexo incoherentes')
    codes.add(state.state_code)
  }
  return index
}
