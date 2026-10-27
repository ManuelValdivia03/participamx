import { useEffect, useMemo, useState, type KeyboardEvent } from 'react'
import { Icon } from '../../components/Icon'
import { nationalView, path, states, stateView } from './geography'
import { useAnimatedViewBox } from './useAnimatedViewBox'
import type { Municipality } from './municipalities'
import { useMapGestures } from './useMapGestures'
import { panViewBox, parseViewBox } from './viewBoxMotion'

const statePaths = states.map(item => ({ item, d: path(item) ?? undefined }))

export function TerritoryMap({ stateCode, municipalityCode, items, loading, failed, onState, onMunicipality, onRetry }: {
  stateCode: string; municipalityCode: string; items: Municipality[]; loading: boolean; failed: boolean;
  onState: (code: string) => void; onMunicipality: (code: string) => void; onRetry: () => void
}) {
  const [hoveredName, setHoveredName] = useState('')
  const [focusedCode, setFocusedCode] = useState('')
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
  useEffect(() => { setFocusedCode(''); setHoveredName('') }, [stateCode])
  const tabCode = focusedCode || municipalityCode || (state ? items[0]?.properties.inegiCode : states[0]?.properties.code)

  function moveMapFocus(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key === '+' || event.key === '=') { event.preventDefault(); camera.zoom(1.5); return }
    if (event.key === '-') { event.preventDefault(); camera.zoom(1 / 1.5); return }
    if (event.key === 'Escape') { gestures.deactivate(); event.currentTarget.blur(); return }
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
    setHoveredName('')
  }

  return <>
    {state && <nav className="territory-breadcrumb" aria-label="Ruta territorial">
      <button type="button" onClick={() => onState('')}>México</button><span aria-hidden="true">/</span>
      {municipality ? <button type="button" onClick={() => selectMunicipality('')}>{state.properties.name}</button> : <strong>{state.properties.name}</strong>}
      {municipality && <><span aria-hidden="true">/</span><strong>{municipality.properties.name}</strong><button className="state-return" type="button" onClick={() => selectMunicipality('')}>Volver al estado</button></>}
    </nav>}
    {loading && <p className="municipal-status" role="status">Cargando {units} de {state?.properties.name}…</p>}
    {failed && <div className="municipal-status" role="alert"><p>No pudimos cargar los {units}. Reintenta o elige otro estado.</p><button className="map-reset" onClick={onRetry}>Reintentar carga</button></div>}
    <div className={`interactive-map${gestures.dragging ? ' is-dragging' : ''}`} aria-busy={loading}>
      <div className="map-location" aria-hidden="true"><Icon name="location" />{hoveredName || name}</div>
      <div className="map-floating-controls" role="group" aria-label="Navegación del mapa">
        <button type="button" aria-label="Ver todo México" title="Ver todo México" disabled={!state && view === nationalView} onClick={() => { onState(''); camera.animateTo(nationalView) }}><Icon name="mapa" /></button>
        <button type="button" aria-label="Acercar mapa" title="Acercar (+)" disabled={!camera.canZoomIn} onClick={() => camera.zoom(1.5)}>+</button>
        <button type="button" aria-label="Alejar mapa" title="Alejar (−)" disabled={!camera.canZoomOut} onClick={() => camera.zoom(1 / 1.5)}>−</button>
        <button type="button" aria-label="Encuadrar territorio seleccionado" title="Encuadrar selección" disabled={view === targetView} onClick={() => camera.animateTo(targetView)}><Icon name="location" /></button>
      </div>
      <svg ref={svgRef} className="mexico-map" tabIndex={0} viewBox={view} data-target-viewbox={targetView} data-reduced-motion={reduced} data-wheel-active={gestures.active} aria-label={state ? `Mapa de ${units} de ${state.properties.name}` : 'Mapa de las 32 entidades de México'} aria-describedby="map-keyboard-help" role="group" onKeyDown={moveMapFocus}
        onPointerDown={gestures.onPointerDown} onPointerMove={gestures.onPointerMove} onPointerUp={gestures.onPointerUp} onPointerCancel={gestures.onPointerCancel}
        onPointerLeave={() => { setHoveredName(''); gestures.onPointerLeave() }} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) gestures.deactivate() }}
        onDoubleClick={gestures.onDoubleClick} onClickCapture={event => { if (gestures.shouldSuppressClick()) { event.preventDefault(); event.stopPropagation() } }}>
        {statePaths.map(({ item, d }) => <path key={item.properties.code} d={d}
          className={`state-shape${state ? ' state-context' : ''}${stateCode === item.properties.code ? ' is-selected' : ''}`}
          role={state ? undefined : 'button'} data-map-code={item.properties.code} tabIndex={state ? undefined : item.properties.code === tabCode ? 0 : -1} aria-label={state ? undefined : `Seleccionar ${item.properties.name}`}
          onClick={state ? undefined : event => { if (event.detail < 2) onState(item.properties.code) }}
          onKeyDown={state ? undefined : event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onState(item.properties.code) } }}
          onPointerEnter={state ? undefined : () => setHoveredName(item.properties.name)}
          onFocus={state ? undefined : () => setHoveredName(item.properties.name)} onBlur={() => setHoveredName('')} />)}
        {municipalPaths.map(({ item, d }) => <path key={item.properties.inegiCode} d={d}
          className={`state-shape municipality-shape${municipalityCode === item.properties.inegiCode ? ' is-selected' : ''}`}
          role="button" data-map-code={item.properties.inegiCode} tabIndex={item.properties.inegiCode === tabCode ? 0 : -1} aria-label={`Seleccionar ${unit} ${item.properties.name}`} aria-pressed={municipalityCode === item.properties.inegiCode}
          onClick={event => { if (event.detail < 2) selectMunicipality(item.properties.inegiCode) }}
          onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectMunicipality(item.properties.inegiCode) } }}
          onPointerEnter={() => setHoveredName(item.properties.name)} onFocus={() => setHoveredName(item.properties.name)} onBlur={() => setHoveredName('')}>
          <title>{item.properties.name} · {item.properties.ineCode ? `INE ${item.properties.ineCode}` : 'Correspondencia pendiente'}</title>
        </path>)}
      </svg>
      <p className="map-instruction">{gestures.active ? 'Rueda activa para zoom · Esc o salir del mapa para volver al desplazamiento de página.' : 'Arrastra para desplazarte · pellizca para zoom · clic activa la rueda · Ctrl + rueda siempre acerca.'}</p>
    </div>
    <div className="map-legend"><span><i />Territorios disponibles</span><span><i className="selected-swatch" />Selección actual</span><span>El color no representa participación.</span></div>
    <div className="map-keyboard-tools"><p id="map-keyboard-help">Flechas: recorrer territorios. Enter/espacio: seleccionar. Mayús + flechas: desplazar. +/−: zoom. Escape: liberar rueda. La búsqueda y el ranking son alternativas accesibles.</p><button type="button" onClick={() => document.getElementById('territory-detail')?.focus()}>Ir a la ficha electoral</button></div>
    <p className="map-attribution">Estados: INEGI (2020), vía <a href="https://www.geoboundaries.org/api/current/gbOpen/MEX/ADM1/" target="_blank" rel="noreferrer">geoBoundaries</a> · <a href="https://creativecommons.org/licenses/by/3.0/igo/" target="_blank" rel="noreferrer">CC BY 3.0 IGO</a>. Municipios: <a href="https://lcidsig.inegi.org.mx/server/rest/services/Hosted/%C3%81reas_geoestad%C3%ADsticas_municipales_2024/FeatureServer/0" target="_blank" rel="noreferrer">INEGI, marco 2024</a> · <a href="https://www.inegi.org.mx/inegi/terminos.html" target="_blank" rel="noreferrer">Términos de libre uso</a>. Geometrías generalizadas; marcos de años distintos.</p>
  </>
}
