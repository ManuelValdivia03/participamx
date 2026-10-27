import { Icon, type IconName } from '../../components/Icon'
import { differencePoints, formatCount, formatPercent, formatPoints, ratio } from './territorialData'

type Totals = { LN: number; SV: number; NV: number; NS: number }

export function ElectionLoading({ label }: { label: string }) {
  return <div className="territorial-loading" role="status"><p>{label}</p><div className="territorial-loading-shapes" aria-hidden="true"><span /><span /><span /><span /><span /></div></div>
}

export function ElectionMetricCards({ totals, nationalRate, territory, year, compareNational = true }: {
  totals: Totals; nationalRate: number | null; territory: string; year: number; compareNational?: boolean
}) {
  const participation = ratio(totals.SV, totals.SV + totals.NV)
  return <section className="election-metrics" aria-label={`Indicadores de ${territory}, elección ${year}`}>
    <div className="turnout-spotlight">
      <span className="territorial-kicker"><Icon name="ballot" /> Participación observada · {year}</span>
      <strong>{formatPercent(participation)}</strong>
      <div className="turnout-track" aria-hidden="true">{participation !== null && <span style={{ width: `${participation * 100}%` }} />}</div>
      <p>{territory} · Participaron / registros con participación especificada</p>
      {compareNational ? <><div className="national-comparison"><span>Frente a México · {year}</span><b>{formatPoints(differencePoints(participation, nationalRate))}</b></div>
      <small>Tasa nacional: {formatPercent(nationalRate)} · diferencia sin ajuste demográfico.</small></> : <small>Panorama de las 32 entidades · no especificados por separado.</small>}
    </div>
    <dl className="territorial-counts">
      {[
        ['Lista nominal', totals.LN, 'Conteo nominal reportado', 'list'],
        ['Participaron', totals.SV, 'Participación registrada', 'ballot'],
        ['No participaron', totals.NV, 'No participación registrada', 'perfiles'],
        ['No especificado', totals.NS, `${formatPercent(ratio(totals.NS, totals.LN))} de la lista nominal`, 'info'],
      ].map(([label, value, note, icon]) => <div key={String(label)}><dt><Icon name={icon as IconName} />{label}</dt><dd>{formatCount(value as number)}</dd><small>{note}</small></div>)}
    </dl>
  </section>
}

export function DataQuality({ totals, sourceRows, children }: {
  totals: Totals; sourceRows?: number; children?: React.ReactNode
}) {
  const ns = ratio(totals.NS, totals.LN)
  const lowSupport = totals.LN < 100 || totals.SV + totals.NV < 100 || (sourceRows !== undefined && sourceRows < 5)
  return <section className="territorial-quality" aria-label="Calidad y alcance de los datos">
    <h3><Icon name="coverage" /> Cobertura y calidad</h3>
    <div className="quality-coverage"><strong>{formatPercent(ratio(totals.SV + totals.NV, totals.LN))}</strong><span>de la lista nominal con participación especificada</span></div>
    <p className="quality-base">Base de la tasa: <strong>{formatCount(totals.SV + totals.NV)}</strong> registros.</p>
    {lowSupport && <p className="quality-warning quality-callout"><Icon name="warning" /> Soporte reducido en el total; consulta los criterios.</p>}
    {ns !== null && ns >= .1 && <p className="quality-warning quality-callout"><Icon name="warning" /> No especificación elevada (≥10 %).</p>}
    <details className="quality-details"><summary>Cómo leer estos datos</summary>
      <p>Denominador de participación: <strong>{formatCount(totals.SV + totals.NV)} registros con participación especificada</strong>. Participación no especificada: <strong>{formatPercent(ns)} de la lista nominal</strong>; no significa abstención y la tasa observada no describe a esos registros.</p>
      <p>Soporte reducido: lista nominal o participación especificada menor de 100, o menos de 5 filas fuente. Son criterios exploratorios, no una certificación de calidad.</p>
      <p>Conteos agregados; la lista nominal reportada no identifica personas únicas. Las filas fuente son celdas, no personas ni secciones independientes. El porcentaje de participación especificada describe disponibilidad, no representatividad ni confianza estadística.</p>
      {children}
    </details>
  </section>
}
