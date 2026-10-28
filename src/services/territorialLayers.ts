import { validateLayerIndex, type TerritorialLayerIndex } from '../features/map/thematicData'

const cache = new Map<number, TerritorialLayerIndex>()

export async function getTerritorialLayers(year: number, signal?: AbortSignal): Promise<TerritorialLayerIndex> {
  signal?.throwIfAborted()
  const cached = cache.get(year)
  if (cached) return cached
  const response = await fetch(`${import.meta.env.BASE_URL}data/territorial/layers/${year}.json`, { signal })
  if (!response.ok) throw new Error('No se pudieron cargar las capas electorales')
  const data = validateLayerIndex(await response.json(), year)
  signal?.throwIfAborted()
  cache.set(year, data)
  return data
}
