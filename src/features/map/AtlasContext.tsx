import { Icon } from '../../components/Icon'
import type { Counts } from './territorialData'
import { buildTerritoryHighlights } from './electoralInterpretation'
import type { SectionProfile } from './sectionStatistics'

export type AtlasContextData = { key: string; totals: Counts | null; ready: boolean; nationalRate: number | null; sectionProfile: SectionProfile | null }

export function AtlasContext({ data, territory, year, compareNational }: { data: AtlasContextData | null; territory: string; year: number; compareNational: boolean }) {
  const totals = data?.totals
  const sufficient = !!totals && totals.LN >= 100 && totals.SV + totals.NV >= 100 && totals.source_row_count >= 5
  const findings = totals ? buildTerritoryHighlights(totals, sufficient, data?.nationalRate ?? null, compareNational, data?.sectionProfile ?? null) : []
  return <section className="atlas-context atlas-highlights" aria-label={`Hallazgos de ${territory}, ${year}`} aria-busy={!data?.ready}>
    <header><h3><Icon name="info" /> Lo más destacado</h3><span>{territory} · {year}</span></header>
    {findings.length ? <div className="atlas-highlight-list">{findings.map(item => <article key={item.id} className={item.caution ? 'is-caution' : undefined} data-highlight={item.id}><h4><Icon name={item.icon} />{item.title}</h4><strong>{item.value}</strong><p>{item.text}</p></article>)}</div>
      : <p className="atlas-highlight-empty" role="status">{data?.ready ? 'No hay información suficiente para generar hallazgos de este territorio. Consulta su ficha para conocer el motivo.' : 'Consultando los datos del territorio…'}</p>}
  </section>
}
