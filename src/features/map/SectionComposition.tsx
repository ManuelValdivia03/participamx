import { useId } from 'react'
import { useSectionStatistics } from './useSectionStatistics'
import { sectionCaution, sectionLabels, sectionSupport, sectionTypes, sectionValue } from './sectionStatistics'
import { formatCount, formatPercent, ratio } from './territorialData'
import '../../styles/section-statistics.css'

export function SectionComposition({ year, stateCode, ineCode }: { year: number; stateCode: string; ineCode?: string | null }) {
  const { active, retry } = useSectionStatistics(year, stateCode, ineCode)
  const id = useId()
  return <section className="section-composition" aria-labelledby={id} aria-busy={!active} data-section-year={year} data-section-code={ineCode ?? (stateCode || 'national')}>
    <h3 id={id}>Composición por tipo de sección electoral</h3>
    {!active ? <p role="status">Consultando el tipo de sección electoral…</p> : active.status === 'error' ? <div role="alert"><p>No se pudo cargar el desglose de esta elección. No se sustituye por otro año.</p><button type="button" onClick={retry}>Reintentar desglose</button></div> : !active.data ? <p role="status">No hay desglose disponible para esta clave y elección. No equivale a cero.</p> : (() => {
      const profile = active.data
      const nominal = sectionTypes.map(kind => ({ kind, result: sectionValue(profile, kind, false) }))
      const rates = sectionTypes.map(kind => ({ kind, result: sectionValue(profile, kind, true) }))
      return <>
        <p className="section-basis">{profile.name} · {year} · LN total: <strong>{formatCount(profile.totals.LN)}</strong></p>
        {profile.totals.LN > 0 ? <div className="section-stack" aria-hidden="true">{nominal.map(({ kind, result }) => <span key={kind} data-section-type={kind} style={{ width: `${(result.value ?? 0) * 100}%` }} />)}</div> : <p className="quality-warning">Sin base nominal para calcular composición.</p>}
        <ul className="section-legend">{nominal.map(({ kind, result }) => <li key={kind} data-section-type={kind}><i aria-hidden="true" /><span>{sectionLabels[kind]}</span><strong data-section-share={kind}>{formatPercent(result.value)}</strong><small>LN {formatCount(result.numerator)}{!profile.sections.some(cell => cell.section_type === kind) ? ' · Sin registros de este tipo en la partición conciliada' : result.status === 'low_support' ? ' · Soporte reducido' : ''}</small></li>)}</ul>
        <p className="section-interpretation">{profile.totals.LN > 0 ? 'La barra distribuye registros nominales entre tipos de sección electoral; no distribuye el número de secciones ni muestra participación.' : 'No se inventan porcentajes cuando falta denominador.'}</p>
        <details className="section-rates"><summary>Participación observada por tipo de sección electoral</summary><p>Se suman SV y NV de cada tipo antes de dividir. NS permanece separado. Una diferencia no demuestra un efecto del tipo de sección.</p><div className="territorial-table-scroll" role="region" tabIndex={0} aria-label="Participación y cobertura por tipo de sección electoral"><table className="territorial-table"><caption>{profile.name} · {year}. Participación = SV/(SV+NV) de cada tipo.</caption><thead><tr><th scope="col">Tipo</th><th scope="col">Participación</th><th scope="col">SV</th><th scope="col">NV</th><th scope="col">Base SV+NV</th><th scope="col">NS</th><th scope="col">NS/LN</th><th scope="col">Filas fuente</th></tr></thead><tbody>{rates.map(({ kind, result }) => <tr key={kind}><th scope="row">{sectionLabels[kind]}</th><td data-section-turnout={kind}>{formatPercent(result.value)}{result.status === 'low_support' ? ' · Soporte reducido' : result.value === null ? ' · Sin denominador' : ''}</td><td>{formatCount(result.counts?.SV ?? null)}</td><td>{formatCount(result.counts?.NV ?? null)}</td><td>{formatCount(result.denominator)}</td><td>{formatCount(result.counts?.NS ?? null)}</td><td>{formatPercent(result.counts ? ratio(result.counts.NS, result.counts.LN) : null)}{result.highNs && <span className="quality-warning"> · NS elevado</span>}</td><td>{formatCount(result.counts?.source_row_count ?? null)}</td></tr>)}</tbody></table></div></details>
        {(!sectionSupport(profile.totals) || rates.some(row => row.result.status === 'low_support' || row.result.highNs)) && <p className="quality-warning">Hay soporte reducido o no especificación elevada. Consulta el detalle por tipo; la cobertura agregada no certifica representatividad.</p>}
        <details className="section-context-help"><summary>Fuente, denominadores y límites</summary><p>{sectionCaution}</p><p>Fuente: tablas descriptivas municipio–TIPOSEC conciliadas con los totales del Atlas. Composición = LN del tipo / LN total, incluyendo todas las edades y categorías registradas. El cero nominal de un tipo no observado sólo se presenta dentro de una partición exhaustiva conciliada; su tasa sin base sigue no definida.</p><p>Soporte exploratorio: LN≥100, SV+NV≥100 y filas fuente≥5; NS/LN≥10 % advierte cobertura. Las filas fuente son celdas, no personas o secciones independientes. Las categorías y límites pueden cambiar entre elecciones: no son transiciones de residencia ni efectos causales.</p></details>
      </>
    })()}
  </section>
}
