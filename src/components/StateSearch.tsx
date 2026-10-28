import { useEffect, useId, useRef, useState } from 'react'
import { normalizeSearch } from '../features/map/territorySearchData'
import { Icon } from './Icon'
import '../styles/shared-selectors.css'

export type StateOption = { code: string; name: string }
export function findStates(options: StateOption[], query: string) {
  const words = normalizeSearch(query).split(' ').filter(Boolean)
  return options.filter(p => words.every(word => `${normalizeSearch(p.name)} ${p.code}`.includes(word)))
}
export function StateSearch({ options, value, onChange, label = 'Busca una entidad', disabled = false }: { options: StateOption[]; value: string; onChange: (code: string) => void; label?: string; disabled?: boolean }) {
  const id = useId(), input = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState(''), [open, setOpen] = useState(false), [highlight, setHighlight] = useState(-1)
  const results = findStates(options, query)
  const choose = (code: string) => { onChange(code); setQuery(''); setHighlight(-1); input.current?.focus({ preventScroll: true }); setOpen(false) }
  useEffect(()=>{if(open&&highlight>=0&&results[highlight])document.getElementById(`${id}-${results[highlight].code}`)?.scrollIntoView({block:'nearest'})},[open,highlight,id,results])
  return <div className="state-search" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false) }}>
    <label htmlFor={id}>{label}</label><div className="state-search-field"><Icon name="location" /><input ref={input} id={id} data-state-search role="combobox" autoComplete="off" placeholder="México, Veracruz, Chihuahua…" disabled={disabled} value={query} aria-autocomplete="list" aria-expanded={open} aria-controls={`${id}-results`} aria-activedescendant={open && highlight >= 0 && results[highlight] ? `${id}-${results[highlight].code}` : undefined}
      onFocus={() => setOpen(true)} onClick={() => setOpen(true)} onChange={event => { setQuery(event.target.value); setOpen(true); setHighlight(-1) }} onKeyDown={event => {
        if (event.key === 'Escape') { event.preventDefault(); setOpen(false); setHighlight(-1) }
        if (['ArrowDown', 'ArrowUp'].includes(event.key)) { event.preventDefault(); setOpen(true); setHighlight(n => !results.length ? -1 : n < 0 ? event.key === 'ArrowDown' ? 0 : results.length - 1 : (n + (event.key === 'ArrowDown' ? 1 : -1) + results.length) % results.length) }
        if (event.key === 'Enter' && open && results.length) { event.preventDefault(); choose(results[Math.max(0, highlight)]?.code ?? results[0].code) }
      }} />{query && <button type="button" aria-label="Limpiar búsqueda de entidad" onClick={() => { setQuery(''); setHighlight(-1); setOpen(true); input.current?.focus() }}>×</button>}</div>
    <div className="state-current"><span role="status">Selección: <strong>{options.find(p => p.code === value)?.name ?? 'México'}</strong></span>{value !== 'MX' && <button type="button" onClick={() => choose('MX')}>Volver a México</button>}</div>
    {open && <div className="state-search-results"><p>{results.length ? 'Usa flechas y Enter para seleccionar.' : 'Sin coincidencias. Prueba otro nombre.'}</p><ul id={`${id}-results`} role="listbox" aria-label="Entidades encontradas">{results.map((p, index) => <li key={p.code} id={`${id}-${p.code}`} role="option" aria-selected={index === highlight} data-state-option={p.code} onPointerDown={event => event.preventDefault()} onClick={() => choose(p.code)}><strong>{p.name}</strong>{p.code === 'MX' ? <small>Vista nacional</small> : <small>Entidad federativa</small>}</li>)}</ul></div>}
  </div>
}
