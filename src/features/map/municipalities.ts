import type { Feature, FeatureCollection, MultiPolygon, Polygon } from 'geojson'
import { normalizeGeometry } from './geography'
import { resolveIneKey, type ElectoralYear, type Crosswalk } from './ineKeys'

export type Municipality = Feature<Polygon | MultiPolygon, {
  code: string | null; ineCode: string | null; ineName: string | null; inegiCode: string;
  stateCode: string; municipalityCode: string; name: string; year: ElectoralYear; correspondence: 'name-match' | 'pending'
}>
const cache = new Map<string, Municipality[]>()

export async function loadMunicipalities(stateCode: string, year: ElectoralYear, signal: AbortSignal): Promise<Municipality[]> {
  const cacheKey = `${stateCode}:${year}`
  const cached = cache.get(cacheKey)
  if (cached) return cached
  const [response, keysResponse] = await Promise.all([
    fetch(`${import.meta.env.BASE_URL}data/municipalities/${stateCode}.json`, { signal }),
    fetch(`${import.meta.env.BASE_URL}data/ine-crosswalk/${stateCode}.json`, { signal }),
  ])
  if (!response.ok || !keysResponse.ok) throw new Error('No se pudo cargar la división municipal o sus claves INE.')
  const data = await response.json() as FeatureCollection<Polygon | MultiPolygon, { code: string; stateCode: string; municipalityCode: string; name: string }>
  const crosswalk = await keysResponse.json() as Crosswalk
  if (crosswalk.stateCode !== stateCode || !crosswalk.years[year]) throw new Error('Catálogo INE no disponible para el año.')
  if (data.type !== 'FeatureCollection' || !Array.isArray(data.features) || !data.features.length) throw new Error('Datos municipales incompletos.')
  const codes = new Set<string>()
  const features = data.features.map(feature => {
    const p = feature.properties
    if (!p || !/^\d{5}$/.test(p.code) || p.stateCode !== stateCode || p.code !== p.stateCode + p.municipalityCode || codes.has(p.code) || !p.name) throw new Error('Claves municipales inválidas.')
    codes.add(p.code)
    return { ...feature, properties: { ...p, ...resolveIneKey(p.code, year, crosswalk) }, geometry: normalizeGeometry(feature.geometry) }
  }).sort((a, b) => a.properties.name.localeCompare(b.properties.name, 'es'))
  const resolved = features.flatMap(item => item.properties.ineCode ? [item.properties.ineCode] : [])
  if (new Set(resolved).size !== resolved.length) throw new Error('Una clave INE corresponde a varias geometrías.')
  cache.set(cacheKey, features)
  return features
}

export function searchKey(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').trim()
}
