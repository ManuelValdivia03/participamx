import { normalizeStateCode, validateTerritorialResponse, validateTerritorySummary, type TerritorialResponse, type TerritorySummary } from '../features/map/territorialData'

const cache = new Map<string, TerritorialResponse>()
const summaryCache = new Map<string, TerritorySummary>()

export async function getTerritorySummary(year: number, stateCode: string | null, signal?: AbortSignal): Promise<TerritorySummary> {
  const state = stateCode ? normalizeStateCode(stateCode) : null
  const key = `${year}:${state ?? 'national'}`
  signal?.throwIfAborted()
  const cached = summaryCache.get(key)
  if (cached) return cached
  const response = await fetch(`${import.meta.env.BASE_URL}data/territorial/summaries/${year}/${state ?? 'national'}.json`, { signal })
  if (!response.ok) throw new Error('No se pudo cargar el resumen demográfico de la elección.')
  const result = validateTerritorySummary(await response.json(), year, state)
  signal?.throwIfAborted()
  summaryCache.set(key, result)
  return result
}

export async function getTerritorialDemographics(year: number, stateCode: string, signal?: AbortSignal): Promise<TerritorialResponse> {
  const state = normalizeStateCode(stateCode)
  const key = `${year}:${state}`
  signal?.throwIfAborted()
  const cached = cache.get(key)
  if (cached) return cached
  const response = await fetch(`${import.meta.env.BASE_URL}data/territorial/${year}/${state}.json`, { signal })
  if (!response.ok) throw new Error('No se pudo cargar la ficha demográfica de esta elección.')
  const result = validateTerritorialResponse(await response.json(), year, state)
  signal?.throwIfAborted()
  cache.set(key, result)
  return result
}
