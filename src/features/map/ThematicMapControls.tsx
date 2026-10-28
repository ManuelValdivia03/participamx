import { useState } from 'react'
import { Icon } from '../../components/Icon'
import { formatCount, ratio } from './territorialData'
import { formatLayerPercent, layerDefinitions, layerExplanation, layerStatusLabel, layerUniverse, layerValueLabel, type LayerGroup, type LayerId, type ThematicTerritory } from './thematicData'
import { formatScaleInterval, type ThematicScale } from './thematicScale'
import { describeLayerValue } from './electoralInterpretation'
import { rankSectionTerritories, sectionCaution, sectionLabels } from './sectionStatistics'
import { SectionDominanceLegend } from './SectionDominanceLegend'

const groups = [
  { id: 'participation', label: 'Participación', icon: 'ballot', initial: 'participation' },
  { id: 'sex', label: 'Sexo', icon: 'sex', initial: 'women' },
  { id: 'age', label: 'Edad', icon: 'age', initial: 'age18_34' },
  { id: 'section', label: 'Tipo de sección electoral', icon: 'mapa', initial: 'section_dominant' },
] as const

export function ThematicMapControls({ year, layer, onChange, registeredSexes, ready }: {
  year: number; layer: LayerId; onChange: (layer: LayerId) => void; registeredSexes: string[]; ready: boolean;
}) {
  const group: LayerGroup = layerDefinitions[layer].group
  const participants = layerDefinitions[layer].kind === 'participant_composition'
  const sectionRate = group === 'section' && layerDefinitions[layer].kind === 'rate'
  const options = (Object.keys(layerDefinitions) as LayerId[]).filter(key => layerDefinitions[key].group === group &&
    (group !== 'sex' || (layerDefinitions[key].kind === 'participant_composition') === participants) &&
    (group !== 'section' || (layerDefinitions[key].kind === 'rate') === sectionRate))
  return <section className="thematic-controls" aria-label="Capas estadísticas del mapa">
    <h3>Colorear mapa por</h3>
    <div className="thematic-groups" role="group" aria-label="Grupo de capas">{groups.map(item => <button type="button" key={item.id} data-layer-group={item.id} aria-pressed={group === item.id} onClick={() => onChange(item.initial)}><Icon name={item.icon} /><span>{item.label}</span></button>)}</div>
    {group === 'section' && <div className="thematic-sex-basis" role="group" aria-label="Indicador por tipo de sección electoral"><button type="button" aria-pressed={!sectionRate} onClick={() => onChange('section_dominant')}>Composición nominal</button><button type="button" aria-pressed={sectionRate} onClick={() => onChange('section_urban_turnout')}>Participación observada</button></div>}
    {group === 'sex' && <div className="thematic-sex-basis" role="group" aria-label="Universo de composición por sexo">
      <button type="button" data-sex-basis="nominal" aria-pressed={!participants} onClick={() => onChange(layer === 'men_participants' ? 'men' : 'women')}>Lista nominal</button>
      <button type="button" data-sex-basis="participants" aria-pressed={participants} onClick={() => onChange(layer === 'men' ? 'men_participants' : 'women_participants')}>Participantes</button>
    </div>}
    <div className="thematic-options" role="group" aria-label={`Indicadores de ${group === 'section' ? 'tipo de sección electoral' : groups.find(item => item.id === group)!.label.toLowerCase()}`}>{options.map(key => {
      const disabled = key === 'nonbinary' && (!ready || !registeredSexes.includes('2'))
      const definition = layerDefinitions[key]
      return <button type="button" key={key} data-map-layer={key} aria-label={definition.label} aria-pressed={key === layer} disabled={disabled} title={disabled ? `No binario: ${ready ? `categoría no registrada en ${year}` : 'consultando categorías'}` : undefined} onClick={() => onChange(key)}>{key === 'section_dominant' ? 'Predominante' : 'section' in definition ? sectionLabels[definition.section] : 'sex' in definition ? key.startsWith('women') ? 'Mujeres' : key.startsWith('men') ? 'Hombres' : 'No binario' : definition.label}</button>
    })}</div>
    {group === 'section' && <><p className="thematic-section-explanation" role="status">{layer === 'section_dominant' ? 'Composición nominal: el color identifica el tipo de sección electoral con mayor proporción de LN. Empates explícitos; no se usan cuantiles.' : sectionRate ? 'Participación observada: SV/(SV+NV) dentro del tipo de sección electoral elegido. NS permanece separado; el color no demuestra causalidad.' : 'Composición nominal: LN del tipo de sección electoral elegido / LN total del territorio. Un tono más intenso representa una proporción mayor, no mayor participación.'}</p><details className="section-context-help"><summary>Qué significa este indicador</summary><p>{layerUniverse(layer)}</p><p>{sectionCaution}</p></details></>}
    {group === 'sex' && !participants && (!ready || !registeredSexes.includes('2')) && <p className="thematic-category-note" role="status">{ready ? `No binario no está registrado como categoría en ${year}; su ausencia no equivale a cero.` : 'Consultando las categorías registradas de esta elección…'}</p>}
  </section>
}

export function ThematicLegend({ layer, year, territories, ready, unmappedRecords, onSelect, scale, scope }: {
  layer: LayerId; year: number; territories: ThematicTerritory[]; ready: boolean; unmappedRecords: number; onSelect: (code: string) => void;
  scale: ThematicScale; scope: string
}) {
  const [showTable, setShowTable] = useState(false)
  if (layer === 'section_dominant') return <SectionDominanceLegend year={year} territories={territories} ready={ready} unmappedRecords={unmappedRecords} onSelect={onSelect} scope={scope} />
  const defined = territories.filter(row => row.result.status === 'defined')
  const reduced = territories.filter(row => row.result.status === 'low_support').length
  const missing = territories.length - defined.length - reduced
  const values = defined.map(row => row.result.value!)
  const isSection = layerDefinitions[layer].group === 'section'
  const tableRows = isSection ? rankSectionTerritories(territories) : territories
  const unregistered = layer === 'nonbinary' && territories.some(row => row.result.status === 'unavailable_category')
  const availability = !ready ? 'Consultando los datos de esta elección…' : defined.length ? null
    : unregistered ? `No binario no está registrado en los datos de ${year}. Su ausencia no equivale a cero.`
    : reduced ? `Existen registros disponibles${layer === 'nonbinary' ? ' de No binario' : ''} en ${year}, pero el soporte territorial no es suficiente para compararlos mediante colores.`
    : `No hay información disponible de este indicador en el ámbito de ${year}. La ausencia no equivale a cero.`
  return <section className="thematic-legend" aria-label="Leyenda estadística" data-legend-layer={layer} data-legend-mode="relative" data-scale-breaks={JSON.stringify(scale.breaks)}>
    <header><div><strong>{layerDefinitions[layer].label}</strong><span>{year} · {scope}</span></div><Icon name="info" /></header>
    {scale.classes.length > 0 && <><div className="thematic-ramp" aria-hidden="true">{scale.classes.map((item, index) => <i key={index} style={{ background: `var(--atlas-color-${item.colorLevel})` }} />)}</div>
      <div className="thematic-direction">{scale.distinctCount === 1 ? <span>Un único porcentaje comparable</span> : <><span>Menor porcentaje</span><span>Mayor porcentaje</span></>}</div>
      <p className="thematic-explanation">{layerExplanation(layer)}</p></>}
    <p className="thematic-scale-note">Colores relativos al año y ámbito seleccionados; un mismo color puede representar porcentajes distintos en otra elección.</p>
    {availability && <p className="thematic-availability" role="status"><Icon name="info" />{availability}</p>}
    <div className="thematic-keys"><span><i className="no-data-key" /><Icon name="info" />Sin información</span><span><i className="low-support-key" /><Icon name="warning" />Soporte insuficiente</span></div>
    {ready && unmappedRecords > 0 && <p className="quality-warning">{unmappedRecords} registros municipales con datos no tienen unión cartográfica validada y no se colorean.</p>}
    {ready && reduced > 0 && defined.length > 0 && <p className="quality-warning">{reduced} territorios tienen información con soporte insuficiente; sus cifras siguen consultables.</p>}
    <details className="thematic-values"><summary>Ver rangos y metodología</summary>
      <p className="thematic-coverage">{ready ? `${defined.length} comparables · ${reduced} con soporte insuficiente · ${missing} sin información.` : 'Preparando valores del año seleccionado…'}</p>
      <div className="thematic-class-list" role="list" aria-label="Rangos de color">{scale.classes.map((item, index) => <div role="listitem" key={index} data-scale-class={index} data-class-lower={item.lower} data-class-upper={item.upper} title={`Límites sin redondear: ${item.lower * 100} / ${item.upper * 100} %`}>
        <i style={{ background: `var(--atlas-color-${item.colorLevel})` }} aria-hidden="true" /><strong>{formatScaleInterval(item)}</strong><small>{ready ? item.count : '—'} territorios</small>
      </div>)}</div>
      <p>{layerUniverse(layer)}</p><p>Soporte exploratorio: LN≥100, participación especificada≥100 y filas fuente≥5 en el total o categoría representada. No certifica representatividad. NS son registros no especificados: no se consideran abstención ni se imputan. NS/LN≥10 % advierte cobertura.</p>
      <p>Los cuantiles comparan territorios con soporte del mismo ámbito y año, sin dividir empates. Los colores no son equivalentes entre elecciones ni ámbitos. Contorno cálido: territorio seleccionado; borde discontinuo: territorio señalado.</p>
      {values.length > 0 && <p>Rango observado comparable: {formatLayerPercent(Math.min(...values))}–{formatLayerPercent(Math.max(...values))}. Los límites de cada clase incluyen el extremo superior; «&gt;» excluye el inferior. La clasificación relativa usa todos los territorios del alcance, aunque se acerque o desplace el mapa.</p>}
      <details className="thematic-territories" onToggle={event => setShowTable(event.currentTarget.open)}><summary>{isSection ? 'Consultar ranking del indicador por territorio' : 'Consultar valores por territorio'}</summary>{isSection && <p>Orden descendente de fracciones sin redondear; empates por clave INE. Sólo los territorios con soporte reciben posición; los demás siguen al final. El ranking general inferior conserva participación total.</p>}{showTable && <div className="territorial-table-scroll" role="region" aria-label="Valores del mapa" tabIndex={0}><table className="territorial-table"><caption>{layerDefinitions[layer].label}, {year}. {layerUniverse(layer)}</caption><thead><tr>{isSection && <th scope="col">Posición</th>}<th scope="col">Territorio</th><th scope="col">Porcentaje</th><th scope="col">Numerador</th><th scope="col">Denominador</th><th scope="col">Calidad</th></tr></thead><tbody>{tableRows.map((row, index) => <tr key={row.code}>{isSection && <td>{ready && row.result.status === 'defined' ? index + 1 : '—'}</td>}<th scope="row"><button type="button" onClick={() => onSelect(row.code)}>{row.name}</button></th><td>{ready ? formatLayerPercent(row.result.value) : 'Cargando'}</td><td>{ready ? formatCount(row.result.numerator) : '—'}</td><td>{ready ? formatCount(row.result.denominator) : '—'}</td><td>{ready ? layerStatusLabel(row.result.status) : 'Cargando'}{row.result.highNs ? ' · No especificación ≥10 %' : ''}</td></tr>)}</tbody></table></div>}</details>
    </details>
  </section>
}

export function MapValueCard({ territory, layer, year, ready, onClose, onOpen, selected }: {
  territory: ThematicTerritory; layer: LayerId; year: number; ready: boolean; onClose: () => void; onOpen: () => void; selected: boolean
}) {
  const { result } = territory
  return <aside className="map-value-card" aria-label={`Consulta de ${territory.name}`} data-tooltip-code={territory.code} data-tooltip-year={year} data-tooltip-selected={selected} data-tooltip-status={result.status}>
    <button type="button" className="map-value-close" aria-label="Ocultar valor del mapa" onClick={onClose}>×</button>
    <header><Icon name="location" /><div><h3>{territory.name}</h3><span>{selected ? 'Seleccionado' : 'En consulta'} · {year}</span></div></header>
    <div className="map-value-primary">
    <p className="map-value-label">{layerDefinitions[layer].label}</p><strong className="map-value-number" role="status" aria-live="polite">{ready ? layerValueLabel(layer, result) : 'Cargando…'}</strong>
    {ready && <>{layer !== 'section_dominant' && result.status === 'defined' && <div className="map-value-track" aria-hidden="true"><span style={{ width: `${result.value! * 100}%` }} /></div>}
      {layer === 'section_dominant' && result.dominantTypes?.length && <p className="map-value-dominance">Proporción {result.dominantTypes.length > 1 ? 'de cada tipo empatado' : 'del tipo predominante'}: {formatLayerPercent(ratio(result.numerator, result.denominator))}</p>}
      {result.denominator !== null && <p className="map-value-base">Base {layerDefinitions[layer].kind === 'rate' ? 'especificada' : layerDefinitions[layer].kind === 'participant_composition' ? 'de participantes' : 'nominal'}: {formatCount(result.denominator)}</p>}
      {result.status !== 'defined' && <p className="map-value-support quality-warning"><Icon name="warning" />{describeLayerValue(layer, result)}</p>}
      {result.highNs && <p className="quality-warning">No especificación ≥10 %</p>}</>}
    </div><div className="map-value-secondary">
    {ready && result.status === 'defined' && <p className="map-value-reading">{describeLayerValue(layer, result)}</p>}
    <details className="map-value-method"><summary>Cómo se calcula</summary><p className="map-value-universe">{layerUniverse(layer)}</p><p>{layer === 'section_dominant' ? 'LN de cada tipo líder' : 'Numerador'}: {formatCount(result.numerator)} · Denominador: {formatCount(result.denominator)}. {layerStatusLabel(result.status)}. {layer === 'section_dominant' ? 'El color identifica una categoría; no ordena porcentajes ni participación.' : 'El color clasifica, no cambia el porcentaje.'}</p></details>
    <button type="button" className="map-value-open" onClick={onOpen}>Ver ficha electoral <span aria-hidden="true">↗</span></button>
    </div>
  </aside>
}
