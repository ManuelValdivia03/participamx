import { electoralYears, type ElectoralYear } from './ineKeys'
import { useEffect, useMemo, useState } from 'react'
import { Icon } from '../../components/Icon'
import { SectionCard } from '../../components/SectionCard'
import { nationalView, path, states, stateView } from './geography'
import { loadMunicipalities, searchKey, type Municipality } from './municipalities'

export function MapPage() {
  const [stateCode, setStateCode] = useState('')
  const [year, setYear] = useState<ElectoralYear>('2024')
  const [municipalityCode, setMunicipalityCode] = useState('')
  const [hoveredName, setHoveredName] = useState('')
  const [query, setQuery] = useState('')
  const [retry, setRetry] = useState(0)
  const [load, setLoad] = useState<{ state: string; status: 'loading' | 'ready' | 'error'; items: Municipality[] }>({ state: '', status: 'ready', items: [] })
  const state = states.find(item => item.properties.code === stateCode)
  const items = load.state === `${stateCode}:${year}` && load.status === 'ready' ? load.items : []
  const municipality = items.find(item => item.properties.inegiCode === municipalityCode)
  const loading = !!state && (load.state !== `${stateCode}:${year}` || load.status === 'loading')
  const failed = !!state && load.state === `${stateCode}:${year}` && load.status === 'error'
  const isCity = stateCode === '09'
  const unit = isCity ? 'alcaldía' : 'municipio'
  const units = isCity ? 'alcaldías' : 'municipios'
  const visibleItems = useMemo(() => items.filter(item => searchKey(`${item.properties.name} ${item.properties.ineName ?? ''} ${item.properties.ineCode ?? ''}`).includes(searchKey(query))), [items, query])

  function selectState(code: string) {
    setStateCode(code); setMunicipalityCode(''); setQuery(''); setHoveredName('')
  }
  function selectMunicipality(code: string) { setMunicipalityCode(code); setHoveredName('') }
  useEffect(() => {
    if (!stateCode) return
    const controller = new AbortController()
    setLoad({ state: `${stateCode}:${year}`, status: 'loading', items: [] })
    loadMunicipalities(stateCode, year, controller.signal).then(result => {
      if (!controller.signal.aborted) setLoad({ state: `${stateCode}:${year}`, status: 'ready', items: result })
    }).catch(() => {
      if (!controller.signal.aborted) setLoad({ state: `${stateCode}:${year}`, status: 'error', items: [] })
    })
    return () => controller.abort()
  }, [stateCode, year, retry])
  const collection = useMemo(() => ({ type: 'FeatureCollection' as const, features: items }), [items])
  const view = municipality ? stateView(municipality, .5) : items.length ? stateView(collection, 5) : state ? stateView(state) : nationalView
  const name = municipality?.properties.name ?? state?.properties.name ?? 'México'
  const subtitle = ['México', state?.properties.name, municipality?.properties.name].filter(Boolean).join(' / ')

  return <>
    <p className="page-intro">Explora México por estado y {isCity ? 'alcaldía' : 'municipio'}. Selecciona un territorio en el mapa o búscalo por nombre y clave.</p>
    <div className="territory-layout">
      <SectionCard title="Explorador territorial" subtitle={subtitle}>
        <div className="map-toolbar"><div className="state-picker year-picker"><label htmlFor="electoral-year">Año de claves INE</label><select id="electoral-year" value={year} onChange={event => { setYear(event.target.value as ElectoralYear); setMunicipalityCode(''); setQuery(''); setHoveredName('') }}>{electoralYears.map(value => <option key={value} value={value}>{value}</option>)}</select></div><div className="state-picker"><label htmlFor="state-picker">Seleccionar estado</label><select id="state-picker" value={stateCode} onChange={event => selectState(event.target.value)}><option value="">Todo México</option>{states.map(item => <option key={item.properties.code} value={item.properties.code}>{item.properties.name}</option>)}</select></div><button className="map-reset" disabled={!state} onClick={() => selectState('')}>Vista nacional</button></div>
        {state && <div className="territory-breadcrumb"><button type="button" onClick={() => selectState('')}>México</button><span>/</span>{municipality ? <button type="button" onClick={() => selectMunicipality('')}>{state.properties.name}</button> : <strong>{state.properties.name}</strong>}{municipality && <><span>/</span><strong>{municipality.properties.name}</strong></>}{municipality && <button className="state-return" onClick={() => selectMunicipality('')}>Volver al estado</button>}</div>}
        {loading && <p className="municipal-status" role="status">Cargando {units} de {state?.properties.name}…</p>}
        {failed && <div className="municipal-status" role="alert"><p>No pudimos cargar los {units}. Puedes reintentar o elegir otro estado.</p><button className="map-reset" onClick={() => setRetry(value => value + 1)}>Reintentar carga</button></div>}
        <div className="interactive-map" aria-busy={loading}>
          <div className="map-location" aria-hidden="true"><Icon name="location" />{hoveredName || name}</div>
          <svg className="mexico-map" viewBox={view} aria-label={state ? `Mapa de ${units} de ${state.properties.name}` : 'Mapa de las 32 entidades de México'} role="group" onPointerLeave={() => setHoveredName('')}>
            {states.map(item => <path key={item.properties.code} d={path(item) ?? undefined} className={`state-shape${state ? ' state-context' : ''}${stateCode === item.properties.code ? ' is-selected' : ''}`} role={state ? undefined : 'button'} tabIndex={state ? undefined : 0} aria-label={state ? undefined : `Seleccionar ${item.properties.name}`} onClick={state ? undefined : () => selectState(item.properties.code)} onKeyDown={state ? undefined : event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectState(item.properties.code) } }} onPointerEnter={state ? undefined : () => setHoveredName(item.properties.name)} onFocus={state ? undefined : () => setHoveredName(item.properties.name)} onBlur={() => setHoveredName('')} />)}
            {items.map(item => <path key={item.properties.inegiCode} d={path(item) ?? undefined} className={`state-shape municipality-shape${municipalityCode === item.properties.inegiCode ? ' is-selected' : ''}`} role="button" tabIndex={0} aria-label={`Seleccionar ${unit} ${item.properties.name}`} aria-pressed={municipalityCode === item.properties.inegiCode} onClick={() => selectMunicipality(item.properties.inegiCode)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectMunicipality(item.properties.inegiCode) } }} onPointerEnter={() => setHoveredName(item.properties.name)} onFocus={() => setHoveredName(item.properties.name)} onBlur={() => setHoveredName('')}><title>{item.properties.name} · {item.properties.ineCode ? `INE ${item.properties.ineCode}` : 'Correspondencia pendiente'}</title></path>)}
          </svg>
          <p className="map-instruction">{municipality ? `Usa “Volver al estado” para explorar más ${units}.` : state ? `Elige ${isCity ? 'una' : 'un'} ${unit} en el mapa o en la lista inferior.` : 'Haz clic o toca un estado para explorar sus municipios.'}</p>
        </div>
        <div className="map-legend"><span><i />Sin indicadores integrados</span><span><i className="selected-swatch" />Territorio seleccionado</span></div>
        {state && <section className="municipality-search" aria-labelledby="municipalities-title"><div className="municipality-search-heading"><h3 id="municipalities-title">{isCity ? 'Alcaldías' : 'Municipios'} de {state.properties.name}</h3>{items.length > 0 && <span>{items.length} territorios · marco 2024</span>}</div><label htmlFor="municipality-search">Buscar por nombre o clave INE</label><input id="municipality-search" type="search" placeholder={isCity ? 'Ej. Coyoacán o 09003' : 'Nombre o clave INE de cinco dígitos'} value={query} onChange={event => setQuery(event.target.value)} disabled={loading || failed} /><p className="search-count" role="status">{!loading && !failed ? `${visibleItems.length} ${visibleItems.length === 1 ? 'resultado' : 'resultados'}` : ''}</p><div className="municipality-results">{visibleItems.map(item => <button type="button" key={item.properties.inegiCode} aria-pressed={municipalityCode === item.properties.inegiCode} onClick={() => selectMunicipality(item.properties.inegiCode)}><span>{item.properties.name}</span><small>{item.properties.ineCode ? `INE ${item.properties.ineCode}` : 'Clave INE pendiente'}</small></button>)}</div>{!loading && !failed && visibleItems.length === 0 && <p className="municipal-status">No hay coincidencias. Prueba otro nombre o clave.</p>}</section>}
        <p className="map-attribution">Estados: INEGI (2020), vía <a href="https://www.geoboundaries.org/api/current/gbOpen/MEX/ADM1/" target="_blank" rel="noreferrer">geoBoundaries</a> · <a href="https://creativecommons.org/licenses/by/3.0/igo/" target="_blank" rel="noreferrer">CC BY 3.0 IGO</a>. Municipios: <a href="https://lcidsig.inegi.org.mx/server/rest/services/Hosted/%C3%81reas_geoestad%C3%ADsticas_municipales_2024/FeatureServer/0" target="_blank" rel="noreferrer">INEGI, Áreas geoestadísticas municipales 2024</a> · <a href="https://www.inegi.org.mx/inegi/terminos.html" target="_blank" rel="noreferrer">Términos de libre uso</a>. Geometrías generalizadas por ParticipaMX; cortes territoriales de años distintos.</p>
      </SectionCard>
      <aside className="territory-detail" aria-label="Detalle del territorio" aria-live="polite" aria-atomic="true"><SectionCard title={name} subtitle={municipality ? `${isCity ? 'Alcaldía' : 'Municipio'} de ${state?.properties.name}` : state ? 'Entidad seleccionada' : 'Panorama nacional'}><div className="territory-heading"><Icon name={state ? 'location' : 'mapa'} /><span>{municipality ? `Clave INE ${municipality.properties.ineCode ?? 'pendiente'} · ${year}` : state ? `Clave estatal ${state.properties.code}` : '32 entidades federativas'}</span></div><div className="info-row"><span>Nivel territorial</span><strong>{municipality ? (isCity ? 'Alcaldía' : 'Municipal') : state ? 'Estatal' : 'Nacional'}</strong></div>{municipality && <div className="info-row"><span>Clave INEGI (geometría)</span><strong>{municipality.properties.inegiCode}</strong></div>}{state && <div className="info-row"><span>{isCity ? 'Alcaldías' : 'Municipios'} (2024)</span><strong>{loading ? 'Cargando…' : failed ? 'Sin cargar' : items.length}</strong></div>}{municipality && <div className="key-correspondence"><strong>{municipality.properties.ineCode ? `Referencia INE ${year}` : 'Correspondencia territorial pendiente'}</strong><p>{municipality.properties.ineCode ? 'Correspondencia por nombre único dentro del estado. La geometría sigue siendo de 2024; no acredita límites históricos idénticos.' : 'No se asignarán indicadores ni perfiles hasta validar la equivalencia con el catálogo INE de este año.'}</p></div>}<div className="territory-indicator"><span>Participación electoral</span><strong>—</strong><p>Pendiente de integrar datos</p></div><div className="territory-indicator"><span>Perfil ciudadano</span><strong>Por definir</strong><p>Disponible después del análisis</p></div><p className="territory-next">{municipality ? 'La integración electoral usará la clave INE y el año seleccionados, solo con equivalencia disponible.' : state ? `Selecciona ${isCity ? 'una' : 'un'} ${unit} para consultar su ficha.` : 'Selecciona un estado para explorar su división municipal.'}</p></SectionCard><p className="territory-disclaimer">Los colores indican selección, no niveles de participación ni clusters. Los límites municipales corresponden a 2024; se validará su equivalencia con cada año electoral.</p></aside>
    </div>
  </>
}
