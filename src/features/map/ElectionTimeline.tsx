import { electoralYears, type ElectoralYear } from './ineKeys'

export function ElectionTimeline({ year, onChange }: { year: ElectoralYear; onChange: (year: number) => void }) {
  return <section className="election-timeline" aria-label="Selección de elección"><p>Elige una elección</p><div role="radiogroup" aria-label="Año electoral">
    {electoralYears.map((value, index) => <button type="button" role="radio" aria-checked={year === value} tabIndex={year === value ? 0 : -1} key={value} data-election-year={value} onClick={() => onChange(Number(value))} onKeyDown={event => {
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? electoralYears.length - 1 : ['ArrowRight', 'ArrowDown'].includes(event.key) ? (index + 1) % electoralYears.length : ['ArrowLeft', 'ArrowUp'].includes(event.key) ? (index - 1 + electoralYears.length) % electoralYears.length : null
      if (next !== null) { event.preventDefault(); onChange(Number(electoralYears[next])); event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('button')[next].focus() }
    }}><strong>{value}</strong><small>{['2012', '2018', '2024'].includes(value) ? 'Presidencial' : 'Intermedia'}</small></button>)}
  </div></section>
}
