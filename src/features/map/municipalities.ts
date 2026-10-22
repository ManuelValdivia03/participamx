import type { Feature, FeatureCollection, MultiPolygon, Polygon } from 'geojson'
import { normalizeGeometry } from './geography'

export type Municipality = Feature<Polygon | MultiPolygon, {
  code: string; stateCode: string; municipalityCode: string; name: string
}>
const cache = new Map<string, Municipality[]>()

export async function loadMunicipalities(stateCode: string, signal: AbortSignal): Promise<Municipality[]> {
  const cached = cache.get(stateCode)
  if (cached) return cached
  const response = await fetch(`${import.meta.env.BASE_URL}data/municipalities/${stateCode}.json`, { signal })
  if (!response.ok) throw new Error('No se pudo cargar la división municipal.')
  const data = await response.json() as FeatureCollection<Polygon | MultiPolygon, Municipality['properties']>
  if (data.type !== 'FeatureCollection' || !Array.isArray(data.features) || !data.features.length) throw new Error('Datos municipales incompletos.')
  const codes = new Set<string>()
  const features = data.features.map(feature => {
    const p = feature.properties
    if (!p || !/^\d{5}$/.test(p.code) || p.stateCode !== stateCode || p.code !== p.stateCode + p.municipalityCode || codes.has(p.code) || !p.name) throw new Error('Claves municipales inválidas.')
    codes.add(p.code)
    return { ...feature, geometry: normalizeGeometry(feature.geometry) }
  }).sort((a, b) => a.properties.name.localeCompare(b.properties.name, 'es'))
  cache.set(stateCode, features)
  return features
}

export function searchKey(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').trim()
}
