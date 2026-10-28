import { Icon } from '../../components/Icon'
import { count, percent, points } from './profileEnrichment'
import type { TransversalProfileFinding } from './types'

export function TransversalFinding({ finding }: { finding: TransversalProfileFinding }) {
  return <section className="pp-transversal" aria-labelledby="pp-transversal-title" data-transversal-finding={finding.id}>
    <header><span className="pp-section-icon"><Icon name="sex" /></span><div><p className="pp-kicker">LECTURA TRANSVERSAL · {finding.year}</p><h2 id="pp-transversal-title">Hallazgos que cruzan las dimensiones</h2></div></header>
    <div className="pp-finding-layout"><div>
      <h3>{finding.title}</h3>
      <p>En los municipios incluidos en el análisis, la diferencia de participación entre mujeres y hombres jóvenes de <strong>{finding.ageBand.replace('-', '–')} años</strong> fue mayor en secciones rurales que urbanas, según los métodos evaluados.</p>
      <p>No significa que todas las mujeres, todos los hombres o todos los municipios sigan ese patrón.</p>
      <p className="stat-unit-help">pp = puntos porcentuales; aquí se compara la brecha mujeres–hombres rural con la urbana.</p>
    </div><div className="pp-finding-contrast">
      <dl className="pp-contrast-values"><div><dt>Contraste municipal</dt><dd>{points(finding.municipalContrastPp).replace('+', '')}<p>Cada municipio aporta el mismo peso.</p></dd></div><div><dt>Contraste ponderado</dt><dd>{points(finding.nominalContrastPp).replace('+', '')}<p>Los municipios con más lista nominal aportan más peso.</p></dd></div></dl>
      <div className="pp-contrast-dots pp-dot-plot" role="img" aria-label={`Contraste municipal: ${points(finding.municipalContrastPp)}; ponderado por lista nominal: ${points(finding.nominalContrastPp)}. Puntos sobre una escala de diferencias, sin meta ni máximo natural.`}>
        <div className="pp-dot-row"><span>Municipal</span><span className="pp-dot-field" aria-hidden="true"><i style={{ left: `${finding.municipalContrastPp / 8 * 100}%` }} /></span></div>
        <div className="pp-dot-row"><span>Ponderado</span><span className="pp-dot-field" aria-hidden="true"><i style={{ left: `${finding.nominalContrastPp / 8 * 100}%` }} /></span></div>
        <div className="pp-dot-ticks" aria-hidden="true">{[0, 2, 4, 6, 8].map(v => <span key={v}>{v}</span>)}</div><p className="pp-caption">Diferencia en pp</p>
      </div>
      <p className="pp-caption">Es un contraste entre brechas, no una tasa de participación. La escala sirve para leer diferencias; no es una meta.</p>
    </div></div>
    <dl className="pp-finding-metrics"><div><dt>Municipios comparables</dt><dd>{count(finding.municipalities)}</dd></div><div><dt>Coinciden en la dirección</dt><dd>{percent(finding.directionShare)}</dd></div><div><dt>Lista nominal anual incluida</dt><dd>{percent(finding.annualNominalShare)}</dd></div></dl>
    <details className="pp-help"><summary>Qué se comparó y hasta dónde llega</summary>
      <p>En cada municipio se requieren cuatro celdas con soporte: hombres y mujeres de 18–34 años, en secciones rurales y urbanas. Se resta la brecha mujeres–hombres urbana de la rural. El dato principal promedia esos contrastes municipales; no se obtiene restando cuatro tasas nacionales.</p>
      <p>El {percent(finding.directionShare)} se refiere a municipios con el mismo signo del contraste, no a personas. El {percent(finding.annualNominalShare)} corresponde a LN={count(finding.LN)} de los cuatro componentes, frente al nominal anual reportado. La base especificada es SV+NV={count(finding.specifiedCount)}.</p>
      <p>La relación mantiene dirección en los controles de soporte, ponderación y calidad del estudio. La no especificación y la selección de municipios comparables limitan su alcance; no demuestra causalidad ni una regla universal.</p>
      <p>Fuente: investigación V2.1, interacción 18–34 R−U. Es un hallazgo complementario, <strong>no un séptimo perfil</strong>; no asigna estrategias ni clasifica individuos.</p>
    </details>
  </section>
}
