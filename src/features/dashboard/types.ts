export type DashboardMetrics = {
  participation: number | null
  coverage: number | null
  nominalList: number | null
  profileCount: number | null
}
export type DashboardSnapshot = {
  year: number
  territoryCode: string
  metrics: DashboardMetrics
  distribution: { id: string; name: string; percentage: number | null }[]
  notes: string[]
}
export type DashboardDataset = {
  mode: 'demo' | 'real'
  source: string
  updatedAt: string | null
  participationDefinition: string
  distributionDefinition: string
  years: number[]
  territories: { code: string; name: string }[]
  snapshots: DashboardSnapshot[]
}

export function dashboardNumber(value: number | null | undefined, suffix = '') {
  return value === null || value === undefined ? 'Sin información' : `${new Intl.NumberFormat('es-MX', { maximumFractionDigits: 1 }).format(value)}${suffix}`
}
