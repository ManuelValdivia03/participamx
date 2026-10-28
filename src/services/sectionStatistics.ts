import { validateSectionPayload, type SectionIndex, type SectionMunicipalities } from '../features/map/sectionStatistics'

const cache = new Map<string, SectionIndex | SectionMunicipalities>()
export function getSectionStatistics(year: number, stateCode: null, signal?: AbortSignal): Promise<SectionIndex>
export function getSectionStatistics(year: number, stateCode: string, signal?: AbortSignal): Promise<SectionMunicipalities>
export async function getSectionStatistics(year: number, stateCode: string | null, signal?: AbortSignal): Promise<SectionIndex | SectionMunicipalities> {
  if (![2009, 2012, 2015, 2018, 2021, 2024].includes(year) || (stateCode !== null && !/^(0[1-9]|[12]\d|3[0-2])$/.test(stateCode))) throw new Error('Solicitud de sección inválida')
  signal?.throwIfAborted()
  const key = `${year}:${stateCode ?? 'index'}`
  const saved = cache.get(key)
  if (saved) return saved
  const response = await fetch(`${import.meta.env.BASE_URL}data/territorial/sections/${year}/${stateCode ?? 'index'}.json`, { signal })
  if (!response.ok) throw new Error('No se pudo cargar el tipo de sección electoral')
  const data = validateSectionPayload(await response.json(), year, stateCode)
  signal?.throwIfAborted()
  cache.set(key, data)
  return data
}
