import { useState } from 'react'
import { Icon } from '../../components/Icon'
import { dominantSectionLabel, sectionCaution, sectionLabels, sectionTypes } from './sectionStatistics'
import { formatCount, ratio } from './territorialData'
import { formatLayerPercent, layerExplanation, layerStatusLabel, type ThematicTerritory } from './thematicData'

export function SectionDominanceLegend({ year, territories, ready, unmappedRecords, onSelect, scope }: {
  year: number; territories: ThematicTerritory[]; ready: boolean; unmappedRecords: number; onSelect: (code: string) => void; scope: string
}) {
  const [showTable, setShowTable] = useState(false)
  const defined = territories.filter(row => row.result.status === 'defined')
  const reduced = territories.filter(row => row.result.status === 'low_support').length
  const ties = defined.filter(row => row.result.dominantTypes!.length > 1).length
  return <section className="thematic-legend section-dominance-legend" aria-label="Leyenda de tipo de sección electoral predominante" data-legend-layer="section_dominant" data-legend-mode="categorical" data-scale-breaks="[]">
    <header><div><strong>Tipo de sección electoral · Predominante</strong><span>{year} · {scope}</span></div><Icon name="info" /></header>
    <div className="section-dominance-keys">{sectionTypes.map(kind => <span key={kind}><i data-section-category={kind} aria-hidden="true" />{sectionLabels[kind]} <small>{ready ? defined.filter(row => row.result.dominantTypes?.length === 1 && row.result.dominantTypes[0] === kind).length : '—'}</small></span>)}<span><i data-section-category="tie" aria-hidden="true" />Empate exacto <small>{ready ? ties : '—'}</small></span></div>
    <p className="thematic-explanation">{layerExplanation('section_dominant')}</p>
    <p className="thematic-scale-note">Colores categóricos fijos: no hay cuantiles ni escala de menor a mayor. Predominante no significa necesariamente más del 50 % del nominal.</p>
    <div className="thematic-keys"><span><i className="no-data-key" /><Icon name="info" />Sin información</span><span><i className="low-support-key" /><Icon name="warning" />Soporte insuficiente</span></div>
    {!ready ? <p className="thematic-availability" role="status">Consultando la composición nominal de esta elección…</p> : !defined.length && <p className="thematic-availability" role="status">No hay territorios con información y soporte suficientes para asignar un tipo de sección electoral predominante. Las cifras disponibles siguen consultables.</p>}
    {ready && reduced > 0 && <p className="quality-warning">{reduced} territorios tienen soporte reducido y no reciben color categórico.</p>}
    {ready && unmappedRecords > 0 && <p className="quality-warning">{unmappedRecords} registros municipales tienen correspondencia cartográfica pendiente y no se colorean.</p>}
    <details className="thematic-values"><summary>Ver composición y metodología</summary>
      <p>{ready ? `${defined.length} con soporte · ${ties} empates incluidos · ${reduced} con soporte reducido · ${territories.length - defined.length - reduced} sin información.` : 'Preparando las categorías…'}</p>
      <p>Se compara LN_U, LN_R y LN_M sobre el mismo LN total. El máximo se determina con conteos enteros, sin redondear proporciones. Los tipos empatados se conservan y se muestran con trama neutra, sin elegir uno arbitrariamente. Un tipo no observado sólo aporta cero dentro de una partición completa conciliada; no se inventan datos faltantes.</p>
      <p>Soporte exploratorio: LN≥100, SV+NV≥100 y filas fuente≥5 en el total y en cada tipo líder. NS/LN≥10 % en el total o un líder advierte cobertura; no cambia la categoría. Las filas fuente no son personas ni secciones independientes. {sectionCaution}</p>
      <details className="thematic-territories" onToggle={event => setShowTable(event.currentTarget.open)}><summary>Consultar composición por territorio</summary>{showTable && <div className="territorial-table-scroll" role="region" aria-label="Tipos de sección electoral predominantes" tabIndex={0}><table className="territorial-table"><caption>Tipo de sección electoral predominante · {year}. Clasificación sin ranking.</caption><thead><tr><th scope="col">Territorio</th><th scope="col">Tipo predominante</th><th scope="col">Proporción de cada líder</th><th scope="col">LN de cada líder</th><th scope="col">LN total</th><th scope="col">Calidad</th></tr></thead><tbody>{territories.map(row => <tr key={row.code}><th scope="row"><button type="button" onClick={() => onSelect(row.code)}>{row.name}</button></th><td>{ready ? dominantSectionLabel(row.result) : 'Cargando…'}</td><td>{ready ? formatLayerPercent(ratio(row.result.numerator, row.result.denominator)) : '—'}</td><td>{ready ? formatCount(row.result.numerator) : '—'}</td><td>{ready ? formatCount(row.result.denominator) : '—'}</td><td>{ready ? layerStatusLabel(row.result.status) : 'Cargando…'}{row.result.highNs && ' · No especificación ≥10 %'}</td></tr>)}</tbody></table></div>}</details>
    </details>
  </section>
}
