import { useCallback } from 'react'
import { getSectionStatistics } from '../../services/sectionStatistics'
import { useTerritorialResource } from './useTerritorialResource'

export function useSectionStatistics(year: number, stateCode: string, ineCode?: string | null) {
  const loader = useCallback(async (signal: AbortSignal) => {
    if (ineCode) return (await getSectionStatistics(year, stateCode, signal)).data.find(row => row.code === ineCode) ?? null
    const index = await getSectionStatistics(year, null, signal)
    return stateCode ? index.states.find(row => row.code === stateCode) ?? null : index.national
  }, [year, stateCode, ineCode])
  return useTerritorialResource(ineCode === null ? null : `${year}:${stateCode}:${ineCode ?? 'summary'}:sections`, loader)
}
