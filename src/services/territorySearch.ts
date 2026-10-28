import { validateSearchIndex, type SearchIndex } from '../features/map/territorySearchData'

let cache: SearchIndex | null = null
export async function getTerritorySearch(signal?: AbortSignal): Promise<SearchIndex> {
  signal?.throwIfAborted()
  if (cache) return cache
  const response = await fetch(`${import.meta.env.BASE_URL}data/territorial/search-index.json`, { signal })
  if (!response.ok) throw new Error('No se pudo cargar el catálogo territorial')
  const data = validateSearchIndex(await response.json())
  signal?.throwIfAborted()
  cache = data
  return data
}
