
export type CitizenProfile = {
  id: string
  name: string
  summary: string
  description: string

  participation: number | null
  coverage: number | null
  medianAge: number | null
  municipalityCount: number | null

  // Indicadores adicionales de los perfiles reales
  peerReference?: number | null
  participationDelta?: number | null
  segmentCount?: number | null
  nominalList?: number | null

  characteristics: string[]
  strategies: string[]
  limitations: string[]
}

export type ProfileDataset = {
  mode: 'demo' | 'real'
  year: number
  source: string
  updatedAt: string | null
  participationDefinition: string
  profiles: CitizenProfile[]
}

// Indicadores originales de la interfaz
export const profileMetrics = [
  {
    key: 'participation',
    label: 'Participación',
    suffix: '%',
    description: 'Indicador entregado por el equipo de análisis.'
  },
  {
    key: 'coverage',
    label: 'Cobertura de información',
    suffix: '%',
    description: 'Cobertura reportada para el perfil; no equivale a participación.'
  },
  {
    key: 'medianAge',
    label: 'Edad mediana',
    suffix: ' años',
    description: 'Edad mediana proporcionada en los resultados.'
  },
  {
    key: 'municipalityCount',
    label: 'Municipios asociados',
    suffix: '',
    description: 'Cantidad reportada de municipios vinculados al perfil.'
  }
] as const

// Indicadores que utilizaremos en las fichas reales
export const realProfileMetrics = [
  {
    key: 'participation',
    label: 'Participación observada',
    suffix: '%',
    description: 'SV / (SV + NV).'
  },
  {
    key: 'peerReference',
    label: 'Referencia de sus pares',
    suffix: '%',
    description: 'Referencia comparable de la misma elección, edad y sexo.'
  },
  {
    key: 'participationDelta',
    label: 'Diferencia respecto a sus pares',
    suffix: ' pp',
    description: 'Diferencia en puntos porcentuales.'
  },
  {
    key: 'segmentCount',
    label: 'Segmentos con soporte',
    suffix: '',
    description: 'Cantidad de segmentos estadísticos incluidos.'
  },
  {
    key: 'municipalityCount',
    label: 'Municipios asociados',
    suffix: '',
    description: 'Los municipios pueden pertenecer a varios perfiles.'
  },
  {
    key: 'nominalList',
    label: 'Lista nominal',
    suffix: '',
    description: 'Lista nominal agregada de los segmentos del perfil.'
  },
  {
    key: 'coverage',
    label: 'Cobertura de lista nominal',
    suffix: '%',
    description: 'Proporción de la lista nominal correspondiente al perfil.'
  }
] as const

export function formatProfileMetric(
  value: number | null | undefined,
  suffix: string
) {
  return value === null || value === undefined
    ? 'Sin información'
    : `${new Intl.NumberFormat('es-MX', {
        maximumFractionDigits: 1
      }).format(value)}${suffix}`
}
