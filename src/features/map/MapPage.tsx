import { useState } from 'react'
import { Icon } from '../../components/Icon'
import { SectionCard } from '../../components/SectionCard'
import { nationalView, path, states, stateView } from './geography'

export function MapPage() {
  const [selectedCode, setSelectedCode] = useState('')
  const [hoveredCode, setHoveredCode] = useState('')
  const selected = states.find(state => state.properties.code === selectedCode)
  const hovered = states.find(state => state.properties.code === hoveredCode)
  const activeName = hovered?.properties.name ?? selected?.properties.name ?? 'México'

  return <>
    <p className="page-intro">Elige un estado para conocer su territorio. Puedes seleccionarlo en el mapa o buscarlo en la lista.</p>
    <div className="territory-layout">
      <SectionCard title="Explorador territorial" subtitle={selected ? `México / ${selected.properties.name}` : 'México / Vista nacional'}>
        <div className="map-toolbar">
          <div className="state-picker"><label htmlFor="state-picker">Seleccionar estado</label><select id="state-picker" value={selectedCode} onChange={event => { setSelectedCode(event.target.value); setHoveredCode('') }}><option value="">Todo México</option>{states.map(state => <option key={state.properties.code} value={state.properties.code}>{state.properties.name}</option>)}</select></div>
          <button className="map-reset" disabled={!selected} onClick={() => { setSelectedCode(''); setHoveredCode('') }}>Vista nacional</button>
        </div>
        <div className="interactive-map">
          <div className="map-location" aria-hidden="true"><Icon name="location" />{activeName}</div>
          <svg className="mexico-map" viewBox={selected ? stateView(selected) : nationalView} aria-label="Mapa interactivo de las 32 entidades de México" role="group" onPointerLeave={() => setHoveredCode('')}>
            {states.map(state => <path key={state.properties.code} d={path(state) ?? undefined} className={`state-shape${selectedCode === state.properties.code ? ' is-selected' : ''}`} role="button" tabIndex={0} aria-label={`Seleccionar ${state.properties.name}`} aria-pressed={selectedCode === state.properties.code} onClick={() => setSelectedCode(state.properties.code)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedCode(state.properties.code) } }} onPointerEnter={() => setHoveredCode(state.properties.code)} onFocus={() => setHoveredCode(state.properties.code)} onBlur={() => setHoveredCode('')}><title>{state.properties.name}</title></path>)}
          </svg>
          <p className="map-instruction">{selected ? 'Estado enfocado · Usa “Vista nacional” para volver a México.' : 'Haz clic o toca un estado. También puedes usar la lista superior.'}</p>
        </div>
        <div className="map-legend"><span><i />Sin indicadores integrados</span><span><i className="selected-swatch" />Estado seleccionado</span></div>
        <p className="map-attribution">Límites: INEGI (2020), vía <a href="https://www.geoboundaries.org/api/current/gbOpen/MEX/ADM1/" target="_blank" rel="noreferrer">geoBoundaries</a> · <a href="https://creativecommons.org/licenses/by/3.0/igo/" target="_blank" rel="noreferrer">CC BY 3.0 IGO</a>. Geometría simplificada para visualización.</p>
      </SectionCard>
      <aside className="territory-detail" aria-label="Detalle del territorio" aria-live="polite" aria-atomic="true">
        <SectionCard title={selected ? selected.properties.name : 'México'} subtitle={selected ? 'Entidad seleccionada' : 'Panorama nacional'}>
          <div className="territory-heading"><Icon name={selected ? 'location' : 'mapa'} /><span>{selected ? `Clave estatal ${selected.properties.code}` : '32 entidades federativas'}</span></div>
          <div className="info-row"><span>Nivel territorial</span><strong>{selected ? 'Estatal' : 'Nacional'}</strong></div>
          <div className="territory-indicator"><span>Participación electoral</span><strong>—</strong><p>Pendiente de integrar datos</p></div>
          <div className="territory-indicator"><span>Perfil ciudadano</span><strong>Por definir</strong><p>Disponible después del análisis</p></div>
          <p className="territory-next">{selected ? 'La exploración de municipios se incorporará en la siguiente etapa.' : 'Selecciona un estado para enfocar su geometría y consultar su ficha.'}</p>
        </SectionCard>
        <p className="territory-disclaimer">Los colores indican la selección territorial; no representan niveles de participación ni resultados de clusters.</p>
      </aside>
    </div>
  </>
}
