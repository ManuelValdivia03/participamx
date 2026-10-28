import { differencePoints, formatCount, formatPercent, formatPoints, ratio } from './territorialData'
import { layerDefinitions, type LayerId, type LayerValue } from './thematicData'
import { dominantSectionLabel, sectionLabels, sectionTypes, sectionValue, type SectionProfile } from './sectionStatistics'

type ElectoralCounts = { LN: number; SV: number; NV: number; NS: number }
export type TerritoryHighlight = { id: string; title: string; value: string; text: string; icon: 'ballot' | 'info' | 'coverage'; caution?: boolean }

export function buildTerritoryHighlights(counts: ElectoralCounts, sufficientSupport: boolean, nationalRate: number | null, compareNational: boolean, sections: SectionProfile | null = null): TerritoryHighlight[] {
  const participation = ratio(counts.SV, counts.SV + counts.NV)
  const unspecified = ratio(counts.NS, counts.LN)
  const findings: TerritoryHighlight[] = []
  if (participation !== null && sufficientSupport) {
    const gap = compareNational ? differencePoints(participation, nationalRate) : null
    findings.push(gap !== null
      ? { id: 'reference', title: 'Frente a México', value: formatPoints(gap), text: 'Diferencia descriptiva frente a la tasa nacional de esta elección, sin ajuste demográfico.', icon: 'ballot' }
      : { id: 'participation', title: 'Participación en contexto', value: participation > .005 && participation < .995 ? `≈ ${Math.round(participation * 100)} de 100` : formatPercent(participation, 6), text: describeTurnout(counts, true), icon: 'ballot' })
  } else {
    findings.push({ id: 'availability', title: 'Lectura con cautela', value: participation === null ? 'Sin tasa disponible' : 'Soporte insuficiente', text: describeTurnout(counts, false), icon: 'info', caution: true })
  }
  if (unspecified !== null) findings.push({ id: 'coverage', title: unspecified > 0 ? 'Condición no especificada' : 'Condición especificada', value: unspecified > 0 ? formatPercent(unspecified, unspecified < .0001 ? 6 : 2) : formatPercent(ratio(counts.SV + counts.NV, counts.LN)), text: unspecified > 0 ? 'Parte del nominal sin condición de voto conocida. No equivale a abstención.' : 'Todo el nominal reportado tiene condición de voto conocida; no certifica representatividad.', icon: 'coverage', caution: unspecified >= .1 })
  const sectionRates = sections ? sectionTypes.map(kind => ({ kind, result: sectionValue(sections, kind, true) })).filter(row => row.result.status === 'defined').sort((a, b) => a.result.value! - b.result.value!) : []
  const first = sectionRates[0], last = sectionRates.at(-1)
  if (first && last && first !== last && last.result.value! - first.result.value! >= .0001) findings.push({ id: 'section', title: 'Contraste por tipo de sección electoral', value: `${formatPercent(last.result.value! - first.result.value!).replace(' %', '')} pp`, text: `${sectionLabels[last.kind]} frente a ${sectionLabels[first.kind]}: diferencia observada entre tipos con soporte, sin ajuste demográfico ni interpretación causal.${sectionRates.length < 3 ? ' No incluye los tipos sin tasa comparable.' : ''}`, icon: 'info', caution: sectionRates.some(row => row.result.highNs) })
  else if (counts.SV + counts.NV > 0) findings.push({ id: 'base', title: 'Base de la lectura', value: formatCount(counts.SV + counts.NV), text: 'Registros con condición de voto conocida: son la base de la tasa observada.', icon: 'info' })
  return findings.slice(0, 3)
}

// Lecturas descriptivas de los conteos existentes; no imputan ni estiman conducta.
export function describeTurnout(counts: ElectoralCounts, sufficientSupport = true): string {
  const value = ratio(counts.SV, counts.SV + counts.NV)
  if (value === null) return 'No hay registros con condición de voto especificada para calcular la participación observada.'
  if (!sufficientSupport) return 'La tasa está disponible, pero su soporte es insuficiente para una comparación territorial.'
  if ((value > 0 && value < .005) || (value < 1 && value > .995)) return `${formatPercent(value, 6)} de los registros con condición de voto especificada registraron participación.`
  const voted = Math.round(value * 100)
  return `De cada 100 registros con condición de voto especificada, aproximadamente ${voted} registraron participación y ${100 - voted} no.`
}

export function describeUnspecified(counts: ElectoralCounts): string {
  const value = ratio(counts.NS, counts.LN)
  return value === null ? 'No hay base nominal para calcular la proporción no especificada.'
    : `${formatPercent(value, value > 0 && value < .0001 ? 6 : 2)} de la lista nominal no tiene condición de voto especificada. No debe clasificarse automáticamente como abstención.`
}

export function describeLayerValue(layer: LayerId, result: LayerValue): string {
  if (result.status === 'low_support') return 'Hay una cifra disponible, pero su soporte es insuficiente para compararla mediante colores.'
  if (result.status === 'unavailable_category') return 'Esta categoría no está registrada en la elección consultada; su ausencia no equivale a cero.'
  if (result.status === 'unmapped') return 'La correspondencia territorial está pendiente; no se asignan cifras de otro territorio.'
  if (result.status === 'missing') return 'No hay información de esta combinación en el ámbito consultado; no significa un porcentaje cero.'
  if (layer === 'section_dominant' && result.dominantTypes?.length) return `${dominantSectionLabel(result)}: ${formatPercent(ratio(result.numerator, result.denominator))} del nominal ${result.dominantTypes.length > 1 ? 'en cada tipo empatado' : 'en el tipo de sección electoral predominante'}. Describe composición nominal, no tasa de participación ni residencia individual; predominante no exige más del 50 %.`
  if (result.value === null || result.denominator === null || result.denominator <= 0) return 'El denominador es cero; no se puede interpretar un porcentaje para este indicador.'
  const definition = layerDefinitions[layer]
  if ('section' in definition) return definition.kind === 'rate'
    ? `${formatPercent(result.value)} de los registros especificados del tipo de sección electoral ${sectionLabels[definition.section].toLowerCase()} registraron participación. NS no se considera abstención; la diferencia no demuestra causalidad.`
    : `${formatPercent(result.value)} de los registros nominales pertenece al tipo de sección electoral ${sectionLabels[definition.section].toLowerCase()}. Describe composición, no residencia individual ni participación.`
  if (layer === 'participation' && result.counts) return describeTurnout(result.counts)
  const percent = formatPercent(result.value, result.value > 0 && result.value < .0001 ? 6 : 2)
  if (layer === 'nonparticipation') return `${percent} de los registros con condición de voto especificada no registraron participación. Los no especificados quedan fuera de esta proporción.`
  const category = layer.startsWith('women') ? 'mujeres' : layer.startsWith('men') ? 'hombres' : 'la categoría No binario'
  if (layer.endsWith('_participants')) return `${percent} de las participaciones registradas corresponde a ${category}. No es la tasa de participación dentro de esa categoría.`
  if (layer.startsWith('age')) {
    const band = { age18_34: '18–34', age35_59: '35–59', age60_100: '60–100' }[layer as 'age18_34' | 'age35_59' | 'age60_100']
    return `${percent} de la lista nominal corresponde a ${band} años. Describe composición por edad, no la participación de ese grupo.`
  }
  return `${percent} de los registros nominales corresponde a ${category}. No indica qué proporción de esa categoría participó.`
}
