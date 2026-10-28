import { Icon, type IconName } from '../../components/Icon'
import { differencePoints, formatCount, formatPercent, formatPoints, ratio } from './territorialData'
import { describeTurnout, describeUnspecified } from './electoralInterpretation'

type Totals = { LN: number; SV: number; NV: number; NS: number; source_row_count?: number }

export function ElectionLoading({ label }: { label: string }) {
  return <div className="territorial-loading" role="status"><p>{label}</p><div className="territorial-loading-shapes" aria-hidden="true"><span /><span /><span /><span /><span /></div></div>
}

export function ElectionMetricCards({ totals, nationalRate, territory, year, compareNational = true }: {
  totals: Totals; nationalRate: number | null; territory: string; year: number; compareNational?: boolean
}) {
  const participation = ratio(totals.SV, totals.SV + totals.NV)
  const sufficientSupport = totals.LN >= 100 && totals.SV + totals.NV >= 100 && (totals.source_row_count === undefined || totals.source_row_count >= 5)
  return <section className="election-metrics" aria-label={`Indicadores de ${territory}, elección ${year}`}>
    <div className="turnout-spotlight">
      <details className="metric-help"><summary aria-label="Qué significa participación observada"><Icon name="info" /></summary><p>Proporción que registró participación entre quienes tienen condición de voto especificada. No incluye registros no especificados.</p></details>
      <span className="territorial-kicker"><Icon name="ballot" /> Participación observada</span>
      <strong>{formatPercent(participation)}</strong>
      <div className="turnout-track" aria-hidden="true">{participation !== null && <span style={{ width: `${participation * 100}%` }} />}</div>
      {compareNational && <><div className="national-comparison"><span>Frente a México</span><b>{formatPoints(differencePoints(participation, nationalRate))}</b></div>
      <small>Nacional: {formatPercent(nationalRate)} · sin ajuste demográfico. pp = puntos porcentuales: diferencia entre las tasas, no cambio porcentual.</small></>}
    </div>
    <section className="electoral-reading" aria-label={`Lectura de ${territory}, ${year}`}><h3><Icon name="info" /> ¿Qué nos dicen estos datos?</h3><p>{describeTurnout(totals, sufficientSupport)}</p><p>{describeUnspecified(totals)}</p></section>
    <dl className="territorial-counts">
      {[
        ['Lista nominal', totals.LN, 'list', 'Conteo nominal reportado en los cuadernillos disponibles. No identifica personas únicas validadas.'],
        ['Participaron', totals.SV, 'ballot', 'Registros que tienen participación especificada como realizada.'],
        ['No participaron', totals.NV, 'perfiles', 'Registros con condición especificada de no participación. No incluye los no especificados.'],
        ['No especificado', totals.NS, 'info', 'Registros sin condición de voto especificada. No se consideran automáticamente abstención.'],
      ].map(([label, value, icon, help]) => <div key={String(label)}><dt><Icon name={icon as IconName} />{label}<details className="metric-help"><summary aria-label={`Qué significa ${label}`}><Icon name="info" /></summary><p>{help}</p></details></dt><dd>{formatCount(value as number)}</dd></div>)}
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
    <div className="quality-coverage"><strong>{formatPercent(ratio(totals.SV + totals.NV, totals.LN))}</strong><span>del nominal tiene condición de voto conocida</span></div>
    {lowSupport && <p className="quality-warning quality-callout"><Icon name="warning" /> Soporte reducido en el total; consulta los criterios.</p>}
    {ns !== null && ns >= .1 && <p className="quality-warning quality-callout"><Icon name="warning" /> No especificación elevada (≥10 %).</p>}
    <details className="quality-details"><summary>Cómo leer estos datos</summary>
      <p className="quality-base">Base de la tasa: <strong>{formatCount(totals.SV + totals.NV)}</strong> registros. Participaron y No participaron son conteos con esa condición especificada.</p>
      <p>Denominador de participación: <strong>{formatCount(totals.SV + totals.NV)} registros con participación especificada</strong>. Participación no especificada: <strong>{formatPercent(ns)} de la lista nominal</strong>; no significa abstención y la tasa observada no describe a esos registros.</p>
      <p>Soporte reducido: lista nominal o participación especificada menor de 100, o menos de 5 filas fuente. Son criterios exploratorios, no una certificación de calidad.</p>
      <p>La lista nominal es el conteo nominal reportado en los cuadernillos disponibles, no un conteo validado de personas únicas. Las filas fuente son celdas, no personas ni secciones independientes. El porcentaje con condición de voto conocida describe disponibilidad, no representatividad ni confianza estadística.</p>
      {children}
    </details>
  </section>
}
