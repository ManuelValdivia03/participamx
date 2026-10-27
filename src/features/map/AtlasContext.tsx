import { Icon } from '../../components/Icon'
import { formatCount, formatPercent, ratio, type Counts } from './territorialData'

export type AtlasContextData = { key: string; totals: Counts | null; ready: boolean }

export function AtlasContext({ data, territory, year }: { data: AtlasContextData | null; territory: string; year: number }) {
  const totals = data?.totals
  const value = (field: 'participation' | 'nominal' | 'unspecified') => !totals ? data?.ready ? 'No disponible' : '—'
    : field === 'nominal' ? formatCount(totals.LN) : formatPercent(field === 'participation' ? ratio(totals.SV, totals.SV + totals.NV) : ratio(totals.NS, totals.LN))
  return <section className="atlas-context" aria-label={`Contexto de ${territory}, ${year}`} aria-busy={!data?.ready}>
    <p><Icon name="location" /><strong>{territory}</strong><span>Contexto electoral · {year}</span></p>
    <dl>{([
      ['participation', 'Participación observada', 'ballot'], ['nominal', 'Lista nominal total', 'list'], ['unspecified', 'No especificado / nominal', 'info'],
    ] as const).map(([key, label, icon]) => <div key={key}><dt><Icon name={icon} />{label}</dt><dd data-context-metric={key}>{value(key)}</dd></div>)}</dl>
  </section>
}
