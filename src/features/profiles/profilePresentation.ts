import type { ProfileCrossCell, ProfileSectionType, EnrichedProfile } from './types'
import { points, profileSectionLabels } from './profileEnrichment'
import { profileInsights } from './profileInsights'
export { sexLabels } from './profileLanguage'

export const profileNames: Record<string, string> = {
  young_favorable: 'Jóvenes con mayor participación',
  young_unfavorable: 'Jóvenes con menor participación',
  adult_favorable: 'Adultos con mayor participación',
  adult_unfavorable: 'Adultos con menor participación',
  older_favorable: 'Personas mayores con mayor participación',
  older_unfavorable: 'Personas mayores con menor participación',
}
export const profileCatalog = Object.entries(profileNames).map(([id, name], index) => ({
  id, name, number: String(index + 1).padStart(2, '0'),
  ageBand: id.startsWith('young_') ? '18-34' : id.startsWith('adult_') ? '35-59' : '60-100',
  direction: id.endsWith('_unfavorable') ? 'por debajo' : 'por encima',
}))
export const sectionOrder = ['U', 'R', 'M'] as const
export function orderedSections(cells: ProfileCrossCell[]) {
  return sectionOrder.map(code => cells.find(c => c.code === code)).filter((c): c is ProfileCrossCell => !!c)
}
export function orderedSexes(cells: ProfileCrossCell[]) {
  return [...cells].sort((a, b) => ['1', '0', '2'].indexOf(a.code) - ['1', '0', '2'].indexOf(b.code))
}
function comparable(cell: ProfileCrossCell | undefined): cell is ProfileCrossCell & { participation: number } {
  return !!cell && cell.status === 'defined' && cell.participation !== null && Number.isFinite(cell.participation) && cell.specifiedCount !== null && cell.specifiedCount > 0
}
export function sexRateDifference(cells: ProfileCrossCell[]) {
  const women = cells.find(c => c.code === '1'), men = cells.find(c => c.code === '0')
  return comparable(women) && comparable(men) ? (women.participation - men.participation) * 100 : null
}
export function sexDifferenceText(cells: ProfileCrossCell[]) {
  const difference = sexRateDifference(cells)
  if (difference === null) return 'No hay dos tasas con información suficiente para comparar mujeres y hombres.'
  if (Math.abs(difference) < 1e-10) return 'En este perfil, las tasas observadas de mujeres y hombres son iguales.'
  return `En este perfil, la participación observada fue ${points(Math.abs(difference)).replace('+', '').replace(' pp', ' puntos porcentuales')} mayor entre ${difference > 0 ? 'mujeres que entre hombres' : 'hombres que entre mujeres'}.`
}
export function sectionDifferenceText(cells: ProfileCrossCell[]) {
  const valid = cells.filter(comparable)
  if (valid.length < 2) return 'No hay información suficiente para comparar las tasas por tipo de sección electoral.'
  const range=(Math.max(...valid.map(c=>c.participation))-Math.min(...valid.map(c=>c.participation)))*100
  if(valid.length===3&&range<1)return 'Las tres tasas agregadas difieren menos de 1 pp. Es cercanía descriptiva, no una prueba estadística.'
  const urban=valid.find(c=>c.code==='U'),rural=valid.find(c=>c.code==='R')
  if(!urban||!rural)return 'No hay información suficiente para el contraste rural–urbano; se conservan las tasas disponibles.'
  return `Rural menos Urbana: ${points((rural.participation-urban.participation)*100)}. Este contraste fijo no identifica una causa.`
}
export function sectionPlural(code: string) {
  return ({ U: 'urbanas', R: 'rurales', M: 'mixtas' } as Record<string, string>)[code] ?? profileSectionLabels[code as ProfileSectionType] ?? code
}

// Edición de los hallazgos ya validados; no redefine pertenencias ni estima resultados nuevos.
export function getProfileReading(data: EnrichedProfile, year: number) {
  const insights = profileInsights(data, year)
  return {
    intro: `Grupos municipales de ${data.ageBand} años comparados con la referencia nacional de su misma edad y sexo en ${year}.`,
    insights, findings: insights.map(f => `${f.title}: ${f.metric}. ${f.text}`),
    sectionNote: insights.find(f => f.id === 'section')!.context,
  }
}

