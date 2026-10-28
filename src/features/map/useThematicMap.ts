import { useCallback, useMemo } from 'react'
import { getTerritorialLayers } from '../../services/territorialLayers'
import { getTerritorialDemographics } from '../../services/territorialDemographics'
import { useTerritorialResource } from './useTerritorialResource'
import { layerDefinitions, layerValue, type LayerId, type ThematicTerritory } from './thematicData'
import { getSectionStatistics } from '../../services/sectionStatistics'
import type { Municipality } from './municipalities'
import { sumCounts, turnout } from './territorialData'

export function useThematicMap(year: number, stateCode: string, items: Municipality[], layer: LayerId, geometryReady: boolean, selectedCode: string) {
  const loader = useCallback(async (signal: AbortSignal) => {
    const [index, municipal] = await Promise.all([
      getTerritorialLayers(year, signal), stateCode ? getTerritorialDemographics(year, stateCode, signal) : null,
    ])
    return { index, municipal }
  }, [year, stateCode])
  const { active, retry } = useTerritorialResource(`${year}:${stateCode || 'national'}:layers`, loader)
  const sectionLoader = useCallback(async (signal: AbortSignal) => {
    const [index, municipal] = await Promise.all([getSectionStatistics(year, null, signal), stateCode ? getSectionStatistics(year, stateCode, signal) : null])
    return { index, municipal }
  }, [year, stateCode])
  const sections = useTerritorialResource(`${year}:${stateCode || 'national'}:section-map`, sectionLoader)
  const isSection = layerDefinitions[layer].group === 'section'
  const ready = active?.status === 'ready' && (!isSection || sections.active?.status === 'ready') && (!stateCode || geometryReady)
  const registeredSexes = active?.status === 'ready' ? active.data.index.registered_sexes : []
  const states = useMemo((): ThematicTerritory[] => active?.status === 'ready' ? active.data.index.states.map(state => ({
    code: state.state_code!, ineCode: state.state_code, name: state.territory_name, result: layerValue(state, layer, active.data.index.registered_sexes, true,
      sections.active?.status === 'ready' ? sections.active.data.index.states.find(row => row.code === state.state_code) ?? null : null),
  })) : [], [active, layer, sections.active])
  const territories = useMemo((): ThematicTerritory[] => {
    if (!stateCode) return states
    const records = new Map(active?.status === 'ready' ? active.data.municipal?.data.map(record => [record.ine_code, record]) : [])
    const sectionRecords = new Map(sections.active?.status === 'ready' ? sections.active.data.municipal?.data.map(record => [record.code, record]) : [])
    return items.map(item => ({ code: item.properties.inegiCode, ineCode: ready ? item.properties.ineCode : null, name: item.properties.name,
      result: layerValue(ready && item.properties.ineCode ? records.get(item.properties.ineCode) ?? null : null, layer, registeredSexes, !!item.properties.ineCode,
        ready && item.properties.ineCode ? sectionRecords.get(item.properties.ineCode) ?? null : null) }))
  }, [stateCode, states, active, sections.active, items, ready, layer, registeredSexes])
  const values = useMemo(() => new Map(territories.map(territory => [territory.code, territory])), [territories])
  const unmappedRecords = useMemo(() => {
    if (active?.status !== 'ready' || !active.data.municipal || !geometryReady) return 0
    const mapped = new Set(items.map(item => item.properties.ineCode))
    return active.data.municipal.data.filter(record => !mapped.has(record.ine_code)).length
  }, [active, items, geometryReady])
  const totals = useMemo(() => {
    if (!ready || active?.status !== 'ready') return null
    if (!stateCode) return sumCounts(active.data.index.states.map(state => state.totals))
    if (!selectedCode) return active.data.index.states.find(state => state.state_code === stateCode)?.totals ?? null
    const ineCode = items.find(item => item.properties.inegiCode === selectedCode)?.properties.ineCode
    return active.data.municipal?.data.find(record => record.ine_code === ineCode)?.totals ?? null
  }, [ready, active, stateCode, selectedCode, items])
  const nationalRate = useMemo(() => active?.status === 'ready' ? turnout(sumCounts(active.data.index.states.map(state => state.totals))) : null, [active])
  const sectionProfile = useMemo(() => {
    if (sections.active?.status !== 'ready' || (stateCode && !geometryReady)) return null
    if (!stateCode) return sections.active.data.index.national
    if (!selectedCode) return sections.active.data.index.states.find(row => row.code === stateCode) ?? null
    const ineCode = items.find(row => row.properties.inegiCode === selectedCode)?.properties.ineCode
    return sections.active.data.municipal?.data.find(row => row.code === ineCode) ?? null
  }, [sections.active, stateCode, selectedCode, geometryReady, items])
  return { ready, status: isSection && sections.active?.status !== 'ready' ? sections.active?.status ?? 'loading' : active?.status ?? 'loading',
    retry: () => { retry(); if (isSection) sections.retry() }, registeredSexes, states, territories, values, unmappedRecords, totals, nationalRate, sectionProfile }
}
