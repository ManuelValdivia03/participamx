import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Icon } from '../../components/Icon'
import { getTerritorySearch } from '../../services/territorySearch'
import { searchTerritories, type SearchPlace } from './territorySearchData'
import { useTerritorialResource } from './useTerritorialResource'

export function TerritorySearch({ year, currentTerritory, onSelect }: { year: number; currentTerritory: string; onSelect: (place: SearchPlace) => void }) {
  const loader = useCallback((signal: AbortSignal) => getTerritorySearch(signal), [])
  const { active, retry } = useTerritorialResource('national-search', loader)
  const [query, setQuery] = useState(''), [open, setOpen] = useState(false), [highlight, setHighlight] = useState(-1)
  const root = useRef<HTMLDivElement>(null)
  const id = useId()
  const results = active?.status === 'ready' ? searchTerritories(active.data, query, year) : []
  const selected = results[highlight]
  useEffect(() => { setHighlight(-1) }, [year])
  useEffect(() => {
    const close = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])
  useEffect(() => { if (open && selected) document.getElementById(`${id}-${selected.kind}-${selected.code}`)?.scrollIntoView({ block: 'nearest' }) }, [highlight, open, selected?.code, selected?.kind, id])
  function choose(place: SearchPlace) {
    setQuery(''); setOpen(false); setHighlight(-1); onSelect(place)
  }
  return <div className="territory-search" ref={root} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false) }}>
    <label htmlFor="territory-search-input">Encuentra tu territorio</label>
    <div className="territory-search-field"><Icon name="location" /><input id="territory-search-input" role="combobox" type="text" autoComplete="off" placeholder="Busca un estado, municipio o clave…" value={query} aria-expanded={open} aria-autocomplete="list" aria-controls={`${id}-listbox`} aria-activedescendant={open && selected ? `${id}-${selected.kind}-${selected.code}` : undefined}
      onFocus={() => setOpen(true)} onChange={event => { setQuery(event.target.value); setOpen(true); setHighlight(-1) }}
      onKeyDown={event => {
        if (event.key === 'Escape') { setOpen(false); setHighlight(-1); return }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setOpen(true); setHighlight(index => !results.length ? -1 : index < 0 ? (event.key === 'ArrowDown' ? 0 : results.length - 1) : (index + (event.key === 'ArrowDown' ? 1 : -1) + results.length) % results.length) }
        if (event.key === 'Enter' && open && results.length) { event.preventDefault(); choose(results[Math.max(0, Math.min(highlight, results.length - 1))]) }
      }} />
      {query && <button type="button" aria-label="Limpiar búsqueda" onClick={() => { setQuery(''); setOpen(true); setHighlight(-1); document.getElementById('territory-search-input')?.focus() }}>×</button>}
    </div>
    <p className="search-scope" role="status"><span className="selection-dot" aria-hidden="true" /> Explorando: <strong>{currentTerritory}</strong></p>
    {open && <div className="territory-suggestions">
      {!active ? <p role="status">Cargando catálogo territorial…</p> : active.status === 'error' ? <div role="alert"><p>No se pudo cargar la búsqueda.</p><button className="map-reset" onClick={retry}>Reintentar catálogo</button></div> : !query.trim() ? <p>Escribe un nombre o clave. Por ejemplo, «Chih» o «Xalapa».</p> : !results.length ? <p role="status">Sin coincidencias. Prueba otro nombre, clave o agrega la entidad.</p> : <p className="suggestion-count" role="status">{results.length} sugerencias · usa flechas y Enter</p>}
      <ul id={`${id}-listbox`} role="listbox" aria-label="Territorios encontrados">{results.map((place, index) => {
        const state = active?.status === 'ready' ? active.data.states.find(item => item.code === place.state_code)?.name : ''
        const ineCode = active?.status === 'ready' ? place.ine_codes[active.data.years.indexOf(year)] : null
        const pending = place.kind === 'municipality' && !ineCode
        return <li key={`${place.kind}:${place.code}`} id={`${id}-${place.kind}-${place.code}`} role="option" data-place-kind={place.kind} data-place-code={place.code} data-place-state={place.state_code} aria-selected={index === highlight} onPointerDown={event => event.preventDefault()} onPointerEnter={() => setHighlight(index)} onClick={() => choose(place)}>
          <span className="suggestion-kind">{place.kind === 'state' ? 'Entidad' : 'Municipio'}</span><strong>{place.name}</strong><small>{place.kind === 'municipality' ? `${state} · INEGI ${place.code}${ineCode ? ` · INE ${ineCode} (${year})` : ''}` : `Clave ${place.code}`}{pending ? ` · Correspondencia pendiente ${year}` : ''}</small>
        </li>
      })}</ul>
    </div>}
  </div>
}
