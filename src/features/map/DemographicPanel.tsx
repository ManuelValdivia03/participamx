import { useId, useState } from 'react'
import { Icon } from '../../components/Icon'
import { ageBands, demographicBreakdown, formatCount, formatPercent, ratio, sexLabels, type DemographicProfile, type DemographicAxis } from './territorialData'

export function DemographicPanel({ data, territory, year, registeredSexes = year === 2024 ? ['0', '1', '2'] : ['0', '1'] }: {
  data: DemographicProfile; territory: string; year: number; registeredSexes?: string[]
}) {
  const [mode, setMode] = useState<'participation' | 'distribution'>('participation')
  const [axis, setAxis] = useState<DemographicAxis>('crossed')
  const id = useId()
  const { rows, included, sexes } = demographicBreakdown(data, axis)
  const scope = axis === 'sex' ? 'Todas las edades registradas, incluidas las mayores de 100 años' : `Edades 18–100, ${sexes.map(sex => sexLabels[sex]).join(', ')}`
  const lowSupport = rows.filter(row => row.counts && !row.sufficient_support).length
  const highNs = rows.filter(row => row.high_ns).length
  const missing = rows.filter(row => !row.counts).length
  const undefinedRates = rows.filter(row => row.counts && row.participation === null).length
  const title = mode === 'participation' ? 'Tasa de participación' : 'Distribución de participantes'
  const explanation = mode === 'participation'
    ? 'Participaron / (participaron + no participaron) dentro de cada grupo. Se excluye la participación no especificada; si no hay registros especificados, la tasa no está disponible.'
    : `Participaron en el grupo / ${formatCount(included.SV)} participantes del universo mostrado. ${axis === 'sex' ? 'Incluye todas las edades registradas.' : 'Es un universo parcial: edades de 18 a 100 años; no todos los participantes del territorio.'}`
  const groups = axis === 'crossed' ? [...ageBands] : ['all']
  return <section className="demographic-panel" data-axis={axis} aria-labelledby={`${id}-heading`}>
    <header className="demographic-heading"><span className="territorial-kicker"><Icon name={axis === 'age' ? 'age' : 'sex'} /> Edad y sexo · {year}</span><h3 id={`${id}-heading`}>Participación por edad y sexo</h3><p>{territory} · Datos agregados de la elección {year}</p></header>
    <div className="demographic-axis" role="group" aria-label="Explora la distribución">{([
      ['sex', 'Por sexo', 'sex'], ['age', 'Por edad', 'age'], ['crossed', 'Edad y sexo', 'perfiles'],
    ] as const).map(([value, label, icon]) => <button key={value} type="button" data-demographic-axis={value} aria-pressed={axis === value} onClick={() => setAxis(value)}><Icon name={icon} />{label}</button>)}</div>
    <div className="demographic-switch" role="group" aria-label="Indicador de la gráfica demográfica"><button type="button" aria-pressed={mode === 'participation'} onClick={() => setMode('participation')}>Tasa de participación</button><button type="button" aria-pressed={mode === 'distribution'} onClick={() => setMode('distribution')}>Distribución de participantes</button></div>
    <p className="demographic-definition" id={`${id}-definition`}>{mode === 'participation' ? 'Cada barra indica qué proporción participó entre los registros con condición de voto conocida de ese grupo.' : `Reparto de participantes del universo mostrado: ${axis === 'sex' ? 'todas las edades registradas' : '18–100 años, universo parcial'}.`}</p>
    {lowSupport > 0 && <p className="demographic-support-note quality-warning"><Icon name="warning" /> † Soporte reducido en {lowSupport} grupos. Consulta las bases y criterios.</p>}
    {axis !== 'age' && <div className="demographic-legend">{sexes.map(sex => <span key={sex}><i className={`sex-key sex-${sex}`} />{sexLabels[sex]}</span>)}</div>}
    <figure className="demographic-chart" aria-describedby={`${id}-definition`}><figcaption>{title}</figcaption>
      <div className="demographic-scale" aria-hidden="true"><span>0 %</span><span>50 %</span><span>100 %</span></div>
      {groups.map(group => <div className="demographic-age" key={group}>{axis === 'crossed' && <h4>{group.replace('-', '–')} <small>años</small></h4>}
        {rows.filter(row => axis !== 'crossed' || row.age_band === group).map(row => <div className={`demographic-bar-row sex-${row.sex_code ?? 'age'}`} key={row.key}>
          <span className="demographic-sex">{row.label}{row.counts && !row.sufficient_support && <small>Base: {formatCount(row.counts.SV + row.counts.NV)}</small>}</span><div className="demographic-track" aria-hidden="true">{row[mode] !== null && <span className="demographic-bar" style={{ width: `${row[mode]! * 100}%` }} />}</div><strong className={row[mode] === null ? 'unavailable-value' : ''}>{formatPercent(row[mode])}{row.counts && !row.sufficient_support && <span aria-label="Soporte reducido"> †</span>}</strong>
        </div>)}
      </div>)}
    </figure>
    <div className="demographic-coverage"><strong><Icon name="coverage" /> Universo visible: {scope}</strong>
      <dl className="coverage-metrics"><div><dt>Lista nominal incluida</dt><dd>{formatPercent(ratio(included.LN, data.totals.LN), 4)}</dd></div><div><dt>Participantes incluidos</dt><dd>{formatPercent(ratio(included.SV, data.totals.SV), 4)}</dd></div></dl>
      <details className="coverage-details"><summary>Conteos y alcance de la gráfica</summary>
      <p>Lista nominal incluida: {formatCount(included.LN)} de {formatCount(data.totals.LN)} ({formatPercent(ratio(included.LN, data.totals.LN), 4)}). Participaron: {formatCount(included.SV)} de {formatCount(data.totals.SV)} ({formatPercent(ratio(included.SV, data.totals.SV), 4)}).</p>
      {axis !== 'sex' && <p>Fuera de esta gráfica: lista nominal {formatCount(data.totals.LN - included.LN)}, participantes {formatCount(data.totals.SV - included.SV)}. Las edades 101+ se conservan aparte; no se mezclan con 60–100.</p>}
      {!registeredSexes.includes('2') ? <p>No binario no está registrado como categoría en esta elección; su ausencia no significa cero personas.</p> : !sexes.includes('2') ? <p>No binario está registrado a nivel nacional, pero no hay combinaciones observadas en este territorio para mostrar una tasa. No se presenta como cero.</p> : <p>No binario se muestra donde hay registros; las celdas ausentes siguen no disponibles. Su presencia o soporte agregado no garantiza cobertura municipal suficiente.</p>}
      <p>La proporción incluida describe el alcance de esta vista, no una garantía de cobertura territorial o representatividad.</p></details>
    </div>
    <ul className="demographic-quality-flags" aria-label="Advertencias de las celdas demográficas">
      {lowSupport > 0 && <li className="quality-warning">{lowSupport} de {rows.length} grupos con soporte reducido.</li>}{highNs > 0 && <li className="quality-warning">{highNs} grupos con participación no especificada elevada (≥10 %).</li>}{undefinedRates > 0 && <li className="quality-warning">{undefinedRates} tasas no definidas: sin participación especificada.</li>}{missing > 0 && <li className="quality-warning">{missing} combinaciones no observadas; no equivalen a cero.</li>}
      {!lowSupport && !highNs && !undefinedRates && !missing && <li>Sin alertas agregadas de soporte o no especificación según los umbrales exploratorios.</li>}
    </ul>
    <details className="demographic-method"><summary><Icon name="info" /> Cómo se calcula este indicador</summary><p>{explanation}</p><p>Las bases son registros con participación especificada, no una muestra de personas independientes. Los conteos se suman antes de calcular tasas; las combinaciones ausentes y tasas no definidas nunca se sustituyen por cero.</p></details>
    <details className="demographic-details"><summary>Consultar valores exactos y soporte</summary><p>Soporte suficiente: lista nominal≥100, participación especificada≥100 y filas fuente≥5. Criterios exploratorios, no certificación de calidad. Las alertas no eliminan datos.</p>
      <div className="territorial-table-scroll" tabIndex={0} role="region" aria-label="Tabla demográfica con desplazamiento horizontal"><table className="territorial-table"><caption>{territory} · Elección {year} · {scope}. Las tasas se calculan después de sumar conteos.</caption><thead><tr><th scope="col">Grupo</th>{['Lista nominal', 'Participaron', 'No participaron', 'Participación no especificada', 'Participación especificada', 'Tasa de participación', 'Distribución de participantes', 'No especificada / lista nominal', 'Filas fuente', 'Soporte'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>
        {rows.map(row => <tr key={row.key}><th scope="row">{axis === 'crossed' ? `${row.age_band?.replace('-', '–')} · ${row.label}` : row.label}</th>{(['LN', 'SV', 'NV', 'NS'] as const).map(field => <td key={field}>{formatCount(row.counts?.[field] ?? null)}</td>)}<td>{formatCount(row.counts ? row.counts.SV + row.counts.NV : null)}</td><td>{formatPercent(row.participation)}</td><td>{formatPercent(row.distribution)}</td><td>{formatPercent(row.counts ? ratio(row.counts.NS, row.counts.LN) : null)}</td><td>{formatCount(row.counts?.source_row_count ?? null)}</td><td>{row.counts ? `${row.sufficient_support ? 'Suficiente' : 'Reducido'}${row.high_ns ? ' · No especificación elevada' : ''}` : 'Combinación ausente'}</td></tr>)}
      </tbody></table></div><p>Un cero observado conserva su valor. Una tasa indefinida o una combinación ausente se muestra como «No disponible».</p>
    </details>
    {data.complementary.length > 0 && <details className="demographic-details"><summary>Categorías complementarias conservadas ({data.complementary.length})</summary><p>Referencia complementaria al núcleo Hombres/Mujeres de 18–100 años. No binario puede aparecer también en las vistas anteriores: no sumar ambas tablas.</p><div className="territorial-table-scroll" tabIndex={0} role="region" aria-label="Tabla de categorías complementarias"><table className="territorial-table"><caption>Conteos de referencia · {territory}, {year}</caption><thead><tr><th scope="col">Edad</th><th scope="col">Sexo registrado</th>{['Lista nominal', 'Participaron', 'No participaron', 'Participación no especificada', 'Filas fuente', 'Soporte'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{data.complementary.map(row => <tr key={`${row.age_band}:${row.sex_code}`}><th scope="row">{row.age_band}</th><td>{sexLabels[row.sex_code] ?? 'Categoría no disponible'}</td>{(['LN', 'SV', 'NV', 'NS', 'source_row_count'] as const).map(field => <td key={field}>{formatCount(row[field])}</td>)}<td>{row.sufficient_support ? 'Suficiente' : 'Reducido'}{row.high_ns ? ' · No especificación elevada' : ''}</td></tr>)}</tbody></table></div></details>}
  </section>
}
