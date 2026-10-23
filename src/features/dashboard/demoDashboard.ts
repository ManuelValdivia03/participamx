import type { DashboardDataset, DashboardSnapshot } from './types'

// Fixtures for interface testing, not calculations or results from electoral ZIPs.
const years = [2009, 2012, 2015, 2018, 2021, 2024]
const fixtures = [
  { code: 'MX', values: [48.5, 63.2, 49.8, 65.1, 53.7, 61.4], coverage: 95.2, nominalList: 90000000 },
  { code: '01', values: [45.3, 58.1, 47.9, 62.8, 51.4, 59.7], coverage: 97.1, nominalList: 1050000 },
  { code: '09', values: [52.4, null, 55.3, 69.7, 58.6, 66.2], coverage: 96.4, nominalList: 7500000 },
  { code: '30', values: [46.2, 60.8, 51.2, 64.3, 52.6, 60.5], coverage: 92.6, nominalList: 6000000 },
]
const snapshots: DashboardSnapshot[] = fixtures.flatMap(fixture => years.flatMap((year, index) => {
  const participation = fixture.values[index]
  if (participation === null) return []
  const partial = fixture.code === '30' && year === 2021
  return [{ year, territoryCode: fixture.code,
    metrics: { participation, coverage: partial ? null : fixture.coverage, nominalList: fixture.nominalList, profileCount: partial ? null : 4 },
    distribution: partial ? [] : [
      { id: 'demo-a', name: 'Perfil de ejemplo A', percentage: 35 },
      { id: 'demo-b', name: 'Perfil de ejemplo B', percentage: 30 },
      { id: 'demo-c', name: 'Perfil de ejemplo C', percentage: 20 },
      { id: 'demo-d', name: 'Perfil de ejemplo D', percentage: 15 },
    ],
    notes: [partial ? 'Ejemplo con cobertura y distribución de perfiles pendientes. No representa falta de datos reales en Veracruz.' : 'Cifras ficticias para probar la presentación. No representan resultados electorales.'],
  }]
}))

export const demoDashboard: DashboardDataset = {
  mode: 'demo', source: 'Ejemplos ficticios de ParticipaMX; no extraídos de los ZIP electorales.', updatedAt: null,
  participationDefinition: 'Indicador simulado. Su universo, denominador y tratamiento de NS serán definidos y entregados por el equipo de análisis.',
  distributionDefinition: 'Distribución ficticia de municipios entre perfiles, expresada en porcentajes entregados para la interfaz. No se han clasificado municipios reales.',
  years,
  territories: [{ code: 'MX', name: 'México · Nacional' }, { code: '01', name: 'Aguascalientes' }, { code: '09', name: 'Ciudad de México' }, { code: '30', name: 'Veracruz' }],
  snapshots,
}
