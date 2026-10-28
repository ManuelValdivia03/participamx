import { useEffect, useRef } from 'react'
import { electoralYears } from '../features/map/ineKeys'
import '../styles/shared-selectors.css'

export function ElectionSelector({ year, onChange }: { year: number | string; onChange: (year: number) => void }) {
  const group = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const reveal = () => {
      const active = group.current?.querySelector<HTMLElement>('[aria-checked="true"]')
      if (!active || !group.current) return
      const box = active.getBoundingClientRect(), parent = group.current.getBoundingClientRect()
      if (box.left < parent.left) group.current.scrollLeft -= parent.left - box.left
      else if (box.right > parent.right) group.current.scrollLeft += box.right - parent.right
    }
    reveal(); const observer = new ResizeObserver(reveal)
    if(group.current)observer.observe(group.current)
    return()=>observer.disconnect()
  }, [year])
  return <section className="election-timeline shared-election-selector" aria-label="Selección de elección"><p>Elige la elección que quieres analizar</p><div ref={group} role="radiogroup" aria-label="Año electoral">
    {electoralYears.map((value, index) => <button type="button" role="radio" aria-checked={String(year) === value} tabIndex={String(year) === value ? 0 : -1} key={value} data-election-year={value} onClick={() => onChange(Number(value))} onKeyDown={event => {
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? electoralYears.length - 1 : ['ArrowRight', 'ArrowDown'].includes(event.key) ? (index + 1) % electoralYears.length : ['ArrowLeft', 'ArrowUp'].includes(event.key) ? (index - 1 + electoralYears.length) % electoralYears.length : null
      if (next !== null) { event.preventDefault(); onChange(Number(electoralYears[next])); event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('button')[next].focus() }
    }}><span className="election-marker" aria-hidden="true" /><strong>{value}</strong><small>{['2012', '2018', '2024'].includes(value) ? 'Presidencial' : 'Intermedia'}</small></button>)}
  </div></section>
}
