import { useEffect, useMemo, useState } from 'react'
import { SectionCard } from '../../components/SectionCard'
import { Icon } from '../../components/Icon'
import { useElectionYear } from '../../context/ElectionYearContext'
import type { ElectoralYear } from './ineKeys'
import { states } from './geography'
import { loadMunicipalities, type Municipality } from './municipalities'
import { TerritoryMap } from './TerritoryMap'
import { TerritoryPanel } from './TerritoryPanel'
import { TerritorySearch } from './TerritorySearch'
import { ElectionTimeline } from './ElectionTimeline'
import { TerritorialRanking } from './TerritorialRanking'
import type { SearchPlace } from './territorySearchData'
import { AtlasContext, type AtlasContextData } from './AtlasContext'
import { AtlasGuide } from './AtlasGuide'
import '../../styles/territorial.css'
import '../../styles/territorial-navigation.css'
import '../../styles/territorial-atlas.css'
import '../../styles/atlas-guide.css'

export function MapPage() {
  const { year: sharedYear, setYear } = useElectionYear()
  const year = String(sharedYear) as ElectoralYear
  const [stateCode, setStateCode] = useState('')
  const [municipalityCode, setMunicipalityCode] = useState('')
  const [requestedName, setRequestedName] = useState('')
  const [retry, setRetry] = useState(0)
  const [context, setContext] = useState<AtlasContextData | null>(null)
  const [stateSearchRequest, setStateSearchRequest] = useState(0)
  const [load, setLoad] = useState<{ key: string; status: 'loading' | 'ready' | 'error'; items: Municipality[] }>({ key: '', status: 'ready', items: [] })
  const key = `${stateCode}:${year}`
  const state = states.find(item => item.properties.code === stateCode)
  // La geometría sigue siendo 2024; al cambiar de año se retiene, pero se invalida su unión electoral anterior.
  const items = useMemo(() => load.key.split(':')[0] !== stateCode ? [] : load.key === key && load.status === 'ready' ? load.items : load.items.map(item => ({
    ...item, properties: { ...item.properties, year, ineCode: null, ineName: null, code: null, correspondence: 'pending' as const },
  })), [load, stateCode, key, year])
  const municipality = items.find(item => item.properties.inegiCode === municipalityCode)
  const loading = !!state && (load.key !== key || load.status === 'loading')
  const failed = !!state && load.key === key && load.status === 'error'
  const currentTerritory = municipality?.properties.name || (municipalityCode ? requestedName : '') || state?.properties.name || 'Todo México'
  const contextKey = `${sharedYear}:${stateCode}:${municipalityCode}`

  useEffect(() => {
    if (!stateCode) return
    const controller = new AbortController()
    setLoad(previous => ({ key, status: 'loading', items: previous.key.split(':')[0] === stateCode ? previous.items : [] }))
    loadMunicipalities(stateCode, year, controller.signal).then(result => {
      if (!controller.signal.aborted) setLoad({ key, status: 'ready', items: result })
    }).catch(() => {
      if (!controller.signal.aborted) setLoad(previous => ({ key, status: 'error', items: previous.items }))
    })
    return () => controller.abort()
  }, [key, stateCode, year, retry])

  function selectState(code: string) {
    setStateCode(code)
    setMunicipalityCode(''); setRequestedName('')
  }
  function selectPlace(place: SearchPlace) {
    setStateCode(place.state_code)
    setMunicipalityCode(place.kind === 'municipality' ? place.code : '')
    setRequestedName(place.kind === 'municipality' ? place.name : '')
  }

  return <div className="territory-explorer" data-state-code={stateCode} data-municipality-code={municipalityCode} data-election-year={year}>
    <header className="territorial-intro"><h2>Descubre cómo <span>participa México.</span></h2><span className="territorial-source"><Icon name="ballot" /> Seis elecciones · INE</span></header>
    <AtlasGuide />
    <div className="explorer-command"><TerritorySearch year={sharedYear} currentTerritory={currentTerritory} stateCode={stateCode} stateRequest={stateSearchRequest} onSelect={selectPlace} /><ElectionTimeline year={year} onChange={setYear} /></div>
    <AtlasContext data={context?.key === contextKey ? context : null} territory={currentTerritory} year={sharedYear} compareNational={!!stateCode} />
    <div className="territory-layout">
      <SectionCard title="Explora el mapa">
        <TerritoryMap year={sharedYear} stateCode={stateCode} municipalityCode={municipalityCode} items={items} loading={loading} failed={failed} onState={selectState} onMunicipality={setMunicipalityCode} onRetry={() => setRetry(value => value + 1)} onContextChange={setContext} onChangeState={() => setStateSearchRequest(value => value + 1)} />
      </SectionCard>
      <TerritoryPanel year={year} stateCode={stateCode} stateName={state?.properties.name} municipality={municipality} municipalityCount={items.length} loading={loading} failed={failed} pendingMunicipalityName={municipalityCode && !municipality ? requestedName || 'Municipio seleccionado' : undefined} />
    </div>
    <div className="territory-comparison"><TerritorialRanking year={sharedYear} stateCode={stateCode} stateName={state?.properties.name} items={items} loading={loading} failed={failed} selectedCode={municipalityCode} onState={selectState} onMunicipality={setMunicipalityCode} /></div>
  </div>
}
