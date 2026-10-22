import { geoArea, geoMercator, geoPath } from 'd3-geo'
import type { Feature, FeatureCollection, MultiPolygon, Polygon } from 'geojson'
import raw from './data/mexico-states.json'

const catalog: Record<string, [string, string]> = {
  Aguascalientes: ['01', 'Aguascalientes'], 'Baja California': ['02', 'Baja California'],
  'Baja California Sur': ['03', 'Baja California Sur'], Campeche: ['04', 'Campeche'],
  'Coahuila de Zaragoza': ['05', 'Coahuila'], Colima: ['06', 'Colima'], Chiapas: ['07', 'Chiapas'],
  Chihuahua: ['08', 'Chihuahua'], 'Distrito Federal': ['09', 'Ciudad de México'], Durango: ['10', 'Durango'],
  Guanajuato: ['11', 'Guanajuato'], Guerrero: ['12', 'Guerrero'], Hidalgo: ['13', 'Hidalgo'],
  Jalisco: ['14', 'Jalisco'], Mexico: ['15', 'Estado de México'], 'Michoacan de Ocampo': ['16', 'Michoacán'],
  Morelos: ['17', 'Morelos'], Nayarit: ['18', 'Nayarit'], 'Nuevo Leon': ['19', 'Nuevo León'],
  Oaxaca: ['20', 'Oaxaca'], Puebla: ['21', 'Puebla'], 'Queretaro de Arteaga': ['22', 'Querétaro'],
  'Quintana Roo': ['23', 'Quintana Roo'], 'San Luis Potosi': ['24', 'San Luis Potosí'],
  Sinaloa: ['25', 'Sinaloa'], Sonora: ['26', 'Sonora'], Tabasco: ['27', 'Tabasco'],
  Tamaulipas: ['28', 'Tamaulipas'], Tlaxcala: ['29', 'Tlaxcala'],
  'Veracruz de Ignacio de la Llave': ['30', 'Veracruz'], Yucatan: ['31', 'Yucatán'], Zacatecas: ['32', 'Zacatecas'],
}

type SourceProperties = { shapeName: string }
export type StateFeature = Feature<Polygon | MultiPolygon, { code: string; name: string }>
const source = raw as unknown as FeatureCollection<Polygon | MultiPolygon, SourceProperties>
export const states: StateFeature[] = source.features.map((feature): StateFeature => {
  const entry = catalog[feature.properties.shapeName]
  if (!entry) throw new Error(`Entidad sin clave: ${feature.properties.shapeName}`)
  // D3 expects exterior rings clockwise; GeoJSON datasets may use the opposite winding.
  const geometry = structuredClone(feature.geometry)
  if (geoArea(geometry) > 2 * Math.PI) {
    if (geometry.type === 'Polygon') geometry.coordinates.forEach(ring => ring.reverse())
    else geometry.coordinates.forEach(polygon => polygon.forEach(ring => ring.reverse()))
  }
  return { type: 'Feature', geometry, properties: { code: entry[0], name: entry[1] } }
}).sort((a, b) => a.properties.name.localeCompare(b.properties.name, 'es'))

export const country: FeatureCollection<Polygon | MultiPolygon> = { type: 'FeatureCollection', features: states }
export const projection = geoMercator().fitExtent([[25, 25], [775, 475]], country)
export const path = geoPath(projection)
export const nationalView = '0 0 800 500'
export function stateView(feature: StateFeature) {
  const [[x0, y0], [x1, y1]] = path.bounds(feature)
  // Keep a stable landscape viewport and include a little surrounding territory.
  const width = Math.max((x1 - x0) * 1.35, (y1 - y0) * 1.35 * 1.6, 30)
  const height = width / 1.6
  return `${(x0 + x1 - width) / 2} ${(y0 + y1 - height) / 2} ${width} ${height}`
}
