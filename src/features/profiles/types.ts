export type CitizenProfile = {
  id: string
  name: string
  summary: string
  description: string
  participation: number | null
  coverage: number | null
  medianAge: number | null
  municipalityCount: number | null
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

export const profileMetrics = [
  { key: 'participation', label: 'Participación', suffix: '%', description: 'Indicador entregado por el equipo de análisis.' },
  { key: 'coverage', label: 'Cobertura de información', suffix: '%', description: 'Cobertura reportada para el perfil; no equivale a participación.' },
  { key: 'medianAge', label: 'Edad mediana', suffix: ' años', description: 'Edad mediana proporcionada en los resultados.' },
  { key: 'municipalityCount', label: 'Municipios asociados', suffix: '', description: 'Cantidad reportada de municipios vinculados al perfil.' },
] as const

export function formatProfileMetric(value: number | null, suffix: string) {
  return value === null ? 'Sin información' : `${new Intl.NumberFormat('es-MX', { maximumFractionDigits: 1 }).format(value)}${suffix}`
}
