import { useEffect, useMemo, useState, type KeyboardEvent } from 'react'
import { Icon } from '../../components/Icon'
import { nationalView, path, states, stateView } from './geography'
import { useAnimatedViewBox } from './useAnimatedViewBox'
import type { Municipality } from './municipalities'
import { useMapGestures } from './useMapGestures'
import { panViewBox, parseViewBox } from './viewBoxMotion'
import { useThematicMap } from './useThematicMap'
import { MapValueCard, ThematicLegend, ThematicMapControls } from './ThematicMapControls'
import { layerValueLabel, layerDefinitions, layerPalette, layerStatusLabel, thematicFill, type LayerId, type ThematicTerritory } from './thematicData'
import { createThematicScale, scaleClassIndex, type ThematicScale } from './thematicScale'
import type { Counts } from './territorialData'
import { mapKeyboardHelp } from './AtlasGuide'
import type { SectionProfile } from './sectionStatistics'

const statePaths = states.map(item => ({ item, d: path(item) ?? undefined }))
const categoricalScale: ThematicScale = { classes: [], breaks: [], count: 0, distinctCount: 0 }

export function TerritoryMap({ year, stateCode, municipalityCode, items, loading, failed, onState, onMunicipality, onRetry, onContextChange, onChangeState }: {
  year: number; stateCode: string; municipalityCode: string; items: Municipality[]; loading: boolean; failed: boolean;
  onState: (code: string) => void; onMunicipality: (code: string) => void; onRetry: () => void
  onContextChange: (context: { key: string; totals: Counts | null; ready: boolean; nationalRate: number | null; sectionProfile: SectionProfile | null }) => void
  onChangeState: () => void
}) {
  const [hoveredName, setHoveredName] = useState('')
  const [focusedCode, setFocusedCode] = useState('')
  const [hoveredCode, setHoveredCode] = useState('')
  const [dismissed, setDismissed] = useState(false)
  const [layer, setLayer] = useState<LayerId>('participation')
  const thematic = useThematicMap(year, stateCode, items, layer, !loading && !failed, municipalityCode)
  const scale = useMemo(() => layer === 'section_dominant' ? categoricalScale : createThematicScale(thematic.ready ? thematic.territories.filter(row => row.result.status === 'defined').map(row => row.result.value) : []), [layer, thematic.ready, thematic.territories])
  useEffect(() => onContextChange({ key: `${year}:${stateCode}:${municipalityCode}`, totals: thematic.totals, ready: thematic.ready, nationalRate: thematic.nationalRate, sectionProfile: thematic.sectionProfile }), [year, stateCode, municipalityCode, thematic.totals, thematic.ready, thematic.nationalRate, thematic.sectionProfile, onContextChange])
  const state = states.find(item => item.properties.code === stateCode)
  const municipality = items.find(item => item.properties.inegiCode === municipalityCode)
  const isCity = stateCode === '09'
  const unit = isCity ? 'alcaldía' : 'municipio'
  const units = isCity ? 'alcaldías' : 'municipios'
  const name = municipality?.properties.name ?? state?.properties.name ?? 'México'
  const municipalPaths = useMemo(() => items.map(item => ({ item, d: path(item) ?? undefined })), [items])
  const targetView = municipality ? stateView(municipality, .5) : state ? stateView(state) : nationalView
  const camera = useAnimatedViewBox(targetView)
  const { view, reduced, svgRef } = camera
  const gestures = useMapGestures(camera)
  useEffect(() => { setFocusedCode(''); setHoveredName(''); setHoveredCode(''); setDismissed(false) }, [stateCode, year])
  const tabCode = focusedCode || municipalityCode || (state ? items[0]?.properties.inegiCode : states[0]?.properties.code)
  const selectedValue = municipalityCode ? thematic.values.get(municipalityCode) : thematic.states.find(item => item.code === stateCode)
  const inspected = thematic.values.get(hoveredCode) ?? selectedValue
  const selectedPath = municipality ? municipalPaths.find(row => row.item.properties.inegiCode === municipalityCode)?.d : state ? statePaths.find(row => row.item.properties.code === stateCode)?.d : null
  function selectTerritory(code: string) { if (code.length === 2) onState(code); else selectMunicipality(code) }

  function inspect(code: string, territoryName: string) {
    setHoveredCode(code); setHoveredName(territoryName); setDismissed(false)
  }
  function describe(territory: ThematicTerritory | undefined, territoryName: string) {
    return `${territoryName} · ${year} · ${layerDefinitions[layer].label}: ${thematic.ready && territory ? `${layerValueLabel(layer, territory.result)}. ${layerStatusLabel(territory.result.status)}${territory.result.highNs ? '. No especificación elevada' : ''}` : 'Cargando valores'}`
  }

  function moveMapFocus(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key === '+' || event.key === '=') { event.preventDefault(); camera.zoom(1.5); return }
    if (event.key === '-') { event.preventDefault(); camera.zoom(1 / 1.5); return }
    if (event.key === 'Escape') { setDismissed(true); gestures.deactivate(); event.currentTarget.blur(); return }
    if (event.shiftKey && event.key.startsWith('Arrow')) {
      event.preventDefault(); camera.stop()
      const box = parseViewBox(camera.getView())
      camera.setCamera(panViewBox(camera.getView(), event.key === 'ArrowLeft' ? -box[2] * .15 : event.key === 'ArrowRight' ? box[2] * .15 : 0, event.key === 'ArrowUp' ? -box[3] * .15 : event.key === 'ArrowDown' ? box[3] * .15 : 0), true)
      return
    }
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return
    const paths = [...event.currentTarget.querySelectorAll<SVGPathElement>('path[role="button"]')]
    const index = paths.indexOf(event.target as SVGPathElement)
    if (index < 0 || !paths.length) return
    event.preventDefault()
    const step = event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 1
    const next = paths[(index + step + paths.length) % paths.length]
    setFocusedCode(next.dataset.mapCode ?? '')
    next.focus()
  }

  function selectMunicipality(code: string) {
    onMunicipality(code)
    setHoveredName(''); setHoveredCode(''); setDismissed(false)
  }

  return <div className="territory-map-atlas" data-map-palette={layerPalette(layer)}>
    <nav className="territory-breadcrumb" aria-label="Ruta territorial">
      <Icon name="location" />{state ? <><button type="button" onClick={() => onState('')}>México</button><span aria-hidden="true">›</span>
      {municipality ? <button type="button" onClick={() => selectMunicipality('')}>{state.properties.name}</button> : <strong aria-current="location">{state.properties.name}</strong>}
      {municipality && <><span aria-hidden="true">›</span><strong aria-current="location">{municipality.properties.name}</strong></>}</> : <strong aria-current="location">Todo México</strong>}
      {state && <button className="change-state" type="button" onClick={onChangeState}><Icon name="location" /> Cambiar estado</button>}
      {municipality && <button className="state-return" type="button" onClick={() => selectMunicipality('')}>Volver al estado</button>}
    </nav>
    <ThematicMapControls year={year} layer={layer} onChange={value => { setLayer(value); setDismissed(false) }} registeredSexes={thematic.registeredSexes} ready={thematic.status === 'ready'} />
    {loading && <p className="municipal-status" role="status">Cargando {units} de {state?.properties.name}…</p>}
    {failed && <div className="municipal-status" role="alert"><p>No pudimos cargar los {units}. Reintenta o elige otro estado.</p><button className="map-reset" onClick={onRetry}>Reintentar carga</button></div>}
    {thematic.status === 'error' && <div className="thematic-error" role="alert"><p>No se pudieron cargar los valores de la capa de {year}. El mapa sigue disponible para navegar.</p><button className="map-reset" type="button" onClick={thematic.retry}>Reintentar capa</button></div>}
    <div className={`interactive-map${gestures.dragging ? ' is-dragging' : ''}`} aria-busy={loading || thematic.status === 'loading'}
      onPointerDown={gestures.onPointerDown} onPointerMove={gestures.onPointerMove} onPointerUp={gestures.onPointerUp} onPointerCancel={gestures.onPointerCancel}
      onDoubleClick={event => { if (!(event.target as Element).closest('button')) gestures.onDoubleClick(event) }}
      onKeyDown={event => { if (event.key === 'Escape') { setDismissed(true); gestures.deactivate() } }}
      onPointerLeave={() => { setHoveredCode(''); setHoveredName(''); gestures.onPointerLeave() }}>
      <div className="map-location" aria-hidden="true"><Icon name="location" /><span>{hoveredName && hoveredCode !== (municipalityCode || stateCode) ? 'En consulta' : stateCode ? 'Seleccionado' : 'Alcance'}</span><strong>{hoveredName || name}</strong></div>
      <div className="map-floating-controls" role="group" aria-label="Navegación del mapa">
        <button type="button" aria-label="Ver todo México" title="Ver todo México" disabled={!state && view === nationalView} onClick={() => { onState(''); camera.animateTo(nationalView) }}><Icon name="mapa" /></button>
        <button type="button" aria-label="Acercar mapa" title="Acercar (+)" disabled={!camera.canZoomIn} onClick={() => camera.zoom(1.5)}>+</button>
        <button type="button" aria-label="Alejar mapa" title="Alejar (−)" disabled={!camera.canZoomOut} onClick={() => camera.zoom(1 / 1.5)}>−</button>
        <button type="button" aria-label="Encuadrar territorio seleccionado" title="Encuadrar selección" disabled={view === targetView} onClick={() => camera.animateTo(targetView)}><Icon name="location" /></button>
      </div>
      <svg ref={svgRef} className="mexico-map" tabIndex={0} viewBox={view} data-map-layer={layer} data-map-scale={layer === 'section_dominant' ? 'categorical' : 'relative'} data-layer-year={year} data-layer-ready={thematic.ready} data-target-viewbox={targetView} data-reduced-motion={reduced} data-wheel-active={gestures.active} aria-label={`${state ? `Mapa de ${units} de ${state.properties.name}` : 'Mapa de las 32 entidades de México'} · ${layerDefinitions[layer].label} · ${year}`} aria-describedby="map-keyboard-help" role="group" onKeyDown={moveMapFocus}
        onBlur={event => { if (!event.currentTarget.parentElement?.contains(event.relatedTarget as Node | null)) { gestures.deactivate(); setHoveredCode(''); setHoveredName('') } }}
        onClickCapture={event => { if (gestures.shouldSuppressClick()) { event.preventDefault(); event.stopPropagation() } }}>
        <defs><pattern id="atlas-section-tie" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="var(--territory-soft)" /><path d="M-1 1L1-1M0 6L6 0M5 7L7 5" stroke="var(--territory-muted)" strokeWidth="1" /></pattern></defs>
        {statePaths.map(({ item, d }) => <path key={item.properties.code} d={d}
          style={{ fill: state ? 'var(--territory-soft)' : thematicFill(thematic.values.get(item.properties.code)?.result, scale) }}
          data-thematic-class={!state && thematic.ready ? scaleClassIndex(thematic.values.get(item.properties.code)?.result.status === 'defined' ? thematic.values.get(item.properties.code)!.result.value : null, scale) ?? undefined : undefined}
          data-thematic-value={!state && thematic.ready ? thematic.values.get(item.properties.code)?.result.value ?? undefined : undefined}
          data-thematic-status={!state && thematic.ready ? thematic.values.get(item.properties.code)?.result.status : undefined}
          data-thematic-category={!state && thematic.ready ? thematic.values.get(item.properties.code)?.result.dominantTypes?.join('|') : undefined}
          className={`state-shape${state ? ' state-context' : ''}${stateCode === item.properties.code ? ' is-selected' : ''}`}
          role={state ? undefined : 'button'} pointerEvents={state ? 'none' : undefined} aria-hidden={state ? true : undefined} data-map-code={item.properties.code} tabIndex={state ? undefined : item.properties.code === tabCode ? 0 : -1} aria-label={state ? undefined : describe(thematic.values.get(item.properties.code), item.properties.name)}
          onClick={state ? undefined : event => { if (event.detail < 2) onState(item.properties.code) }}
          onKeyDown={state ? undefined : event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onState(item.properties.code) } }}
          onPointerEnter={state ? undefined : () => inspect(item.properties.code, item.properties.name)}
          onFocus={state ? undefined : () => inspect(item.properties.code, item.properties.name)}><title>{describe(thematic.values.get(item.properties.code), item.properties.name)}</title></path>)}
        {municipalPaths.map(({ item, d }) => <path key={item.properties.inegiCode} d={d}
          className={`state-shape municipality-shape${municipalityCode === item.properties.inegiCode ? ' is-selected' : ''}`}
          style={{ fill: thematicFill(thematic.ready ? thematic.values.get(item.properties.inegiCode)?.result : undefined, scale) }}
          data-thematic-class={thematic.ready ? scaleClassIndex(thematic.values.get(item.properties.inegiCode)?.result.status === 'defined' ? thematic.values.get(item.properties.inegiCode)!.result.value : null, scale) ?? undefined : undefined}
          data-thematic-value={thematic.ready ? thematic.values.get(item.properties.inegiCode)?.result.value ?? undefined : undefined}
          data-thematic-status={thematic.ready ? thematic.values.get(item.properties.inegiCode)?.result.status : undefined}
          data-thematic-category={thematic.ready ? thematic.values.get(item.properties.inegiCode)?.result.dominantTypes?.join('|') : undefined}
          role="button" data-map-code={item.properties.inegiCode} tabIndex={item.properties.inegiCode === tabCode ? 0 : -1} aria-label={`${unit}: ${describe(thematic.values.get(item.properties.inegiCode), item.properties.name)}`} aria-pressed={municipalityCode === item.properties.inegiCode}
          onClick={event => { if (event.detail < 2) selectMunicipality(item.properties.inegiCode) }}
          onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectMunicipality(item.properties.inegiCode) } }}
          onPointerEnter={() => inspect(item.properties.inegiCode, item.properties.name)} onFocus={() => inspect(item.properties.inegiCode, item.properties.name)}>
          <title>{describe(thematic.values.get(item.properties.inegiCode), item.properties.name)} · {item.properties.ineCode ? `INE ${item.properties.ineCode}` : 'Correspondencia pendiente'}</title>
        </path>)}
        {selectedPath && <g key={municipalityCode || stateCode} className="territory-selection" aria-hidden="true" pointerEvents="none"><path className="selection-halo" d={selectedPath} /><path className="selection-outline" d={selectedPath} /></g>}
      </svg>
      {!dismissed && inspected && <MapValueCard territory={inspected} layer={layer} year={year} ready={thematic.ready} selected={inspected.code === (municipalityCode || stateCode)} onClose={() => { setDismissed(true); svgRef.current?.focus({ preventScroll: true }) }} onOpen={() => { selectTerritory(inspected.code); requestAnimationFrame(() => document.getElementById('territory-detail')?.focus()) }} />}
      <p className="map-instruction">{gestures.active ? 'Zoom con rueda activo · Escape para liberar' : 'Arrastra para explorar · Ctrl + rueda o pellizco para zoom'}</p>
    </div>
    <ThematicLegend layer={layer} year={year} territories={thematic.territories} ready={thematic.ready} unmappedRecords={thematic.unmappedRecords} onSelect={selectTerritory} scale={scale} scope={state ? `Ámbito estatal: ${state.properties.name} · ${units}` : 'Ámbito nacional · 32 entidades'} />
    <p id="map-keyboard-help" className="atlas-sr-only">{mapKeyboardHelp}</p>
    <div className="map-keyboard-tools"><button className="map-detail-action" type="button" onClick={() => document.getElementById('territory-detail')?.focus()}><Icon name="ballot" /> Ver ficha electoral <span aria-hidden="true">→</span></button></div>
    <details className="map-sources"><summary>Cartografía INEGI · fuentes y límites</summary><p className="map-attribution">Estados: INEGI (2020), vía <a href="https://www.geoboundaries.org/api/current/gbOpen/MEX/ADM1/" target="_blank" rel="noreferrer">geoBoundaries</a> · <a href="https://creativecommons.org/licenses/by/3.0/igo/" target="_blank" rel="noreferrer">CC BY 3.0 IGO</a>. Municipios: <a href="https://lcidsig.inegi.org.mx/server/rest/services/Hosted/%C3%81reas_geoestad%C3%ADsticas_municipales_2024/FeatureServer/0" target="_blank" rel="noreferrer">INEGI, marco 2024</a> · <a href="https://www.inegi.org.mx/inegi/terminos.html" target="_blank" rel="noreferrer">Términos de libre uso</a>. Geometrías generalizadas; marcos de años distintos. El nombre único no certifica continuidad de límites históricos.</p></details>
  </div>
}
