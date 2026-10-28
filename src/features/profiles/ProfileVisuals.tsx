import { count, percent, points, valueStatusLabels } from './profileEnrichment'
import type { ProfileCrossCell } from './types'
import { comparableReferenceHelp, percentagePointsHelp } from '../../components/statisticsPresentation'

export function CompositionBar({ cells, labels, label, kind, showCounts = false }: { cells: ProfileCrossCell[]; labels: Record<string, string>; label: string; kind: 'sex' | 'section'; showCounts?: boolean }) {
  return <div className="pp-composition">
    <div className="pp-stack" role="img" aria-label={`${label}. ${cells.map(c => `${labels[c.code]}: ${percent(c.nominalShare)}`).join('; ')}`}>
      {cells.map(c => c.nominalShare !== null && <span key={c.code} data-section={kind === 'section' ? c.code : undefined} data-sex={kind === 'sex' ? c.code : undefined} style={{ width: `${c.nominalShare * 100}%` }} />)}
    </div>
    <ul className="pp-composition-legend">{cells.map(c => <li key={c.code}>
      <i aria-hidden="true" data-section={kind === 'section' ? c.code : undefined} data-sex={kind === 'sex' ? c.code : undefined} />
      <span>{labels[c.code]}{showCounts && <small>LN {count(c.LN)}</small>}</span><strong>{percent(c.nominalShare)}</strong>
    </li>)}</ul>
    <p className="pp-caption">{label}. Es composición de la lista nominal, no participación ni número de secciones.</p>
  </div>
}

export function RateComparison({ observed, reference, label, section, sex, showReference = true, status = 'defined' }: {
  observed: number | null; reference: number | null; label: string; section?: string; sex?: string; showReference?: boolean; status?: ProfileCrossCell['status']
}) {
  const hasRate = observed !== null && Number.isFinite(observed)
  return <div className="pp-rate" data-rate-label={label} data-rate-status={status}>
    <div className="pp-rate-label"><strong>{label}</strong><span>{hasRate ? percent(observed) : status === 'undefined' ? 'Sin base para calcular' : valueStatusLabels[status === 'defined' ? 'missing' : status]}</span></div>
    {hasRate && <div className="pp-rate-track" aria-hidden="true">
      <span data-section={section} data-sex={sex} style={{ width: `${observed * 100}%` }} />
      {showReference && reference !== null && <i style={{ left: `${reference * 100}%` }} />}
    </div>}
    {showReference && <p className="pp-caption">Referencia: {percent(reference)}{hasRate && reference !== null ? ` · Diferencia: ${points((observed - reference) * 100)}` : ''}</p>}
    {status === 'low_support' && <p className="pp-caption">Información limitada: soporte reducido.</p>}
  </div>
}

export function RateKey() {
  return <p className="pp-chart-key"><span aria-hidden="true">━</span> Barra: participación observada <span aria-hidden="true">│</span> Marca: referencia comparable. Escala de 0 a 100 %.</p>
}

export function MeaningHelp() {
  return <details className="pp-help"><summary>¿Qué significan la referencia y los puntos porcentuales?</summary>
    <p>{comparableReferenceHelp} La referencia de la ficha respeta su mezcla de grupos comparables.</p>
    <p>{percentagePointsHelp} El redondeo puede hacer que la resta visual difiera en 0.01 pp.</p>
  </details>
}
