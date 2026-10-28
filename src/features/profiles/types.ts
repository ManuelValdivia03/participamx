
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
  ageBand?: string
  enriched?: EnrichedProfile
}

export type ProfileDataset = {
  mode: 'demo' | 'real'
  year: number
  source: string
  updatedAt: string | null
  participationDefinition: string
  profiles: CitizenProfile[]
  enrichment?: ProfileEnrichment | null
  enrichmentStatus?: 'ready' | 'unavailable_year' | 'error'
}

export type ProfileValueStatus = 'defined' | 'missing' | 'undefined' | 'low_support' | 'unavailable_category'
export type ProfileSectionType = 'U' | 'R' | 'M'
export interface ProfileCrossCell {
  code: string
  sexCode?: string
  status: ProfileValueStatus
  LN: number | null
  SV: number | null
  NV: number | null
  NS: number | null
  specifiedCount: number | null
  sourceRows: number | null
  nominalShare: number | null
  participation: number | null
  reference: number | null
  deltaPp: number | null
  availableCells: number
  eligibleCells: number
  undefinedCells: number
}
export interface EnrichedProfile {
  id: string
  name: string
  ageBand: string
  subtitle: string
  description: string
  distinctive: string
  nameStatus: 'agreed'
  participation: number | null
  reference: number | null
  deltaPp: number | null
  nominalShare: number | null
  counts: { LN: number; SV: number; NV: number; NS: number; specified_count: number; source_row_count: number }
  segments: number
  municipalities: number
  states: number
  findings: string[]
  sexAnalysis: string
  sectionAnalysis: string
  territoryAnalysis: string
  sexCells: ProfileCrossCell[]
  sectionCells: ProfileCrossCell[]
  jointCells: ProfileCrossCell[]
  quality: {
    nearReferenceShare: number
    highNsShare: number
    availableCells: number
    eligibleCells: number
    undefinedCells: number
    signReversals: number
    reversalShare: number
    reversalLN: number
    reversalNominalShare: number
  }
  additionalCategory: { code: '2'; status: 'low_support' | 'unavailable_category'; value: null; explanation: string }
  sourceRefs: string[]
}
export interface TransversalProfileFinding {
  id: string
  year: number
  title: string
  ageBand: string
  municipalContrastPp: number
  nominalContrastPp: number
  municipalities: number
  directionShare: number
  annualNominalShare: number
  LN: number
  specifiedCount: number
  sourceRefs: string[]
}
export interface ProfileEnrichment {
  schemaVersion: 'profiles-enriched-1'
  year: number
  rateUnit: 'proportion'
  namesStatus: 'agreed'
  profiles: EnrichedProfile[]
  transversalFinding: TransversalProfileFinding | null
  heterogeneity: { eligibleCells: number; signReversals: number; bothBeyond2Pp: number; unit: string }
  sources: Record<string, { path: string; sha256: string }>
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
    label: 'Referencia comparable',
    suffix: '%',
    description: 'Referencia comparable de la misma elección, edad y sexo.'
  },
  {
    key: 'participationDelta',
    label: 'Diferencia frente a la referencia',
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
