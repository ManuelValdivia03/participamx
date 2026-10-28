import { useEffect, useRef, useState } from 'react'
import { Icon } from '../../components/Icon'
import { count, percent, points, profileSectionLabels } from './profileEnrichment'
import { orderedSections, orderedSexes, getProfileReading, sectionOrder, sectionPlural, sexLabels } from './profilePresentation'
import { CompositionBar, MeaningHelp, RateComparison, RateKey } from './ProfileVisuals'
import type { CitizenProfile, ProfileDataset, ProfileSectionType } from './types'
import { ProfileExportButtons } from './ProfileExportButtons'
import { additionalSexNote } from './profileLanguage'

export function EnrichedProfileDetail({ profile, dataset, onClose }: { profile: CitizenProfile; dataset: ProfileDataset; onClose: () => void }) {
  const heading = useRef<HTMLHeadingElement>(null)
  const [section, setSection] = useState<ProfileSectionType>('U')
  const [sexView, setSexView] = useState('participation')
  const data = profile.enriched
  const reading = data ? getProfileReading(data, dataset.year) : undefined
  useEffect(() => {
    const frame = requestAnimationFrame(() => { heading.current?.focus({ preventScroll: true }); heading.current?.scrollIntoView({ block: 'start', behavior: 'instant' }) })
    return () => cancelAnimationFrame(frame)
  }, [profile.id])
  const observed = profile.participation === null ? null : profile.participation / 100
  const reference = profile.peerReference == null ? null : profile.peerReference / 100
  return <section className="pp-detail" data-profile-detail={profile.id} aria-labelledby="pp-detail-title">
    <button className="pp-back" type="button" onClick={onClose}>← Volver a los seis perfiles</button>
    <header className="pp-detail-header"><div><p className="pp-kicker">{profile.ageBand?.replace('-', '–')} AÑOS · {dataset.year}</p><h2 id="pp-detail-title" ref={heading} tabIndex={-1}>{profile.name}</h2><p>{reading?.intro ?? `Grupos municipales de ${profile.ageBand?.replace('-', '–')} años comparados con la referencia nacional de su misma edad y sexo en ${dataset.year}. Mayor o menor participación expresa esa diferencia relativa.`}</p></div></header>
    <ProfileExportButtons profile={profile} dataset={dataset} />
    <dl className="pp-summary-kpis"><div><dt>Participación observada</dt><dd>{percent(observed)}</dd></div><div><dt>Referencia comparable</dt><dd>{percent(reference)}</dd></div><div><dt>Diferencia</dt><dd>{points(profile.participationDelta)}</dd></div></dl>
    <p className="stat-unit-help">pp = puntos porcentuales. La tasa usa registros con participación especificada; lo no especificado no es abstención.</p>
    {reading && <section className="pp-interpretation" aria-labelledby="pp-character-title"><h3 id="pp-character-title">¿Qué revelan los datos?</h3><div className="pp-insights-grid">{reading.insights.map(f => <article key={f.id} data-profile-insight={f.id}><h4>{f.title}</h4><strong className="pp-insight-metric">{f.metric}</strong><p>{f.text}</p><small>{f.context}</small></article>)}</div></section>}
    {data ? <>
      <div className="pp-dimension-grid">
        <section className="pp-panel" aria-labelledby="pp-sex-title"><header><Icon name="sex" /><h3 id="pp-sex-title">Mujeres y hombres</h3></header>
          <div className="pp-view-switch" role="group" aria-label="Vista por sexo"><button type="button" data-sex-view="participation" aria-pressed={sexView === 'participation'} onClick={() => setSexView('participation')}>Participación</button><button type="button" data-sex-view="composition" aria-pressed={sexView === 'composition'} onClick={() => setSexView('composition')}>Composición nominal</button></div>
          <div data-sex-visual={sexView}>{sexView === 'participation' ? <><h4>Participación observada</h4>{orderedSexes(data.sexCells).map(c => <RateComparison key={c.code} observed={c.participation} reference={c.reference} status={c.status} sex={c.code} showReference={false} label={sexLabels[c.code]} />)}<p className="pp-caption">La distancia entre las barras permite ver la diferencia descrita en los hallazgos. Escala de 0 a 100 %.</p></> : <><h4>Composición de la lista nominal</h4><CompositionBar cells={orderedSexes(data.sexCells)} labels={sexLabels} kind="sex" label="Proporción de la lista nominal por sexo" /></>}</div>
          <p className="pp-category-note" data-category-status={data.additionalCategory.status}>{additionalSexNote(dataset.year)}</p>
        </section>
        <section className="pp-panel" aria-labelledby="pp-section-title"><header><Icon name="mapa" /><h3 id="pp-section-title">Tipo de sección electoral</h3></header>
          <h4>Composición de la lista nominal</h4><CompositionBar cells={orderedSections(data.sectionCells)} labels={profileSectionLabels} kind="section" label="Proporción por tipo de sección electoral" />
          <h4>Participación observada</h4>{orderedSections(data.sectionCells).map(c => <RateComparison key={c.code} observed={c.participation} reference={c.reference} status={c.status} showReference={false} label={profileSectionLabels[c.code as ProfileSectionType]} section={c.code} />)}
          <p className="pp-caption">La barra de composición muestra cuánto nominal reúne cada tipo; las tasas muestran cuánto participó su base especificada. U/R/M no identifica residencia individual.</p>
          <details className="pp-help pp-joint-disclosure"><summary>Ver mujeres y hombres dentro de cada tipo</summary>
            <div className="pp-section-picker" role="group" aria-label="Explorar el cruce de sexo y tipo de sección electoral">{sectionOrder.map(t => <button type="button" key={t} data-profile-section={t} aria-pressed={section === t} onClick={() => setSection(t)}>{profileSectionLabels[t]}</button>)}</div>
            <div className="pp-joint-detail" data-selected-section={section}><h4>Dentro de secciones {sectionPlural(section)}</h4>{[...data.jointCells.filter(c => c.code === section)].sort((a, b) => Number(b.sexCode) - Number(a.sexCode)).map(c => <RateComparison key={c.sexCode} observed={c.participation} reference={c.reference} status={c.status} label={sexLabels[c.sexCode!]} sex={c.sexCode} />)}<RateKey /></div>
          </details>
        </section>
      </div>
      <details className="pp-help pp-quality"><summary>Cobertura y calidad de la información</summary>
          <p>Al separar por tipo de sección electoral, {count(data.quality.signReversals)} de {count(data.quality.eligibleCells)} subsegmentos con soporte tienen cambio de signo respecto a su agregado V1: {percent(data.quality.reversalShare)}. Representan LN={count(data.quality.reversalLN)}, el {percent(data.quality.reversalNominalShare)} del LN elegible de la ficha.</p>
          <p>{percent(data.quality.nearReferenceShare)} de segmentos está a no más de 2 pp de su referencia y {percent(data.quality.highNsShare)} tiene NS/LN≥10 %. Son alertas descriptivas, no pruebas de error ni significación.</p>
          <p>Se conservan {count(data.quality.availableCells)} cruces U/R/M: {count(data.quality.availableCells - data.quality.eligibleCells)} sin soporte completo, incluidos {count(data.quality.undefinedCells)} sin tasa definida. Los totales incluyen todos los cruces; NULL no se convierte en cero.</p>
          <dl className="pp-small-metrics"><div><dt>Municipios presentes</dt><dd>{count(profile.municipalityCount)}</dd></div><div><dt>Lista nominal anual incluida</dt><dd>{percent(profile.coverage == null ? null : profile.coverage / 100)}</dd></div></dl><p>{data.territoryAnalysis}</p><p>Los municipios pueden aparecer en más de una ficha. Sus cantidades no se suman como territorios únicos.</p>
      </details>
    </> : <section className="pp-panel"><h3>Desglose ampliado no disponible</h3><p>No se pudo verificar la caracterización de {dataset.year}. Se conservan las cifras originales de esa elección.</p><p>Vuelve al listado para reintentar la carga del desglose.</p></section>}
    <details className="pp-help pp-method"><summary>Cómo se calcularon estos datos</summary>
      <p>Unidad V1: municipio × intervalo × sexo. La edad y el signo frente a su referencia definen la ficha; V2 la caracteriza con cruces de sexo y tipo de sección electoral. No son seis clusters naturales ni categorías individuales. Bandas y frontera cero son convenciones de diseño.</p>
      <p>Soporte: LN≥100, SV+NV≥100 y filas fuente≥5. Las filas fuente son celdas originales, no personas o secciones independientes. Participación=ΣSV/Σ(SV+NV), con denominador positivo. NS no es abstención; una tasa ausente no es cero. La referencia combina las nacionales de la misma elección, edad y sexo, ponderadas por los denominadores SV+NV locales.</p>
      <MeaningHelp />
      {data && <><dl className="pp-counts"><div><dt>Lista nominal (LN)</dt><dd>{count(data.counts.LN)}</dd></div><div><dt>Con marca de voto (SV)</dt><dd>{count(data.counts.SV)}</dd></div><div><dt>Sin marca de voto (NV)</dt><dd>{count(data.counts.NV)}</dd></div><div><dt>Base especificada (SV+NV)</dt><dd>{count(data.counts.specified_count)}</dd></div><div><dt>No especificados (NS)</dt><dd>{count(data.counts.NS)}</dd></div><div><dt>Filas fuente</dt><dd>{count(data.counts.source_row_count)}</dd></div><div><dt>Segmentos</dt><dd>{count(data.segments)}</dd></div></dl>
        <div className="pp-table-scroll" tabIndex={0} role="region" aria-label="Conteos por sexo y tipo de sección electoral"><table className="pp-method-table"><caption>Conteos y tasas del cruce completo</caption><thead><tr>{['Tipo de sección', 'Sexo', 'LN', 'SV', 'NV', 'NS', 'SV+NV', 'Tasa', 'Referencia', 'Diferencia'].map(h => <th scope="col" key={h}>{h}</th>)}</tr></thead><tbody>{sectionOrder.flatMap(t => data.jointCells.filter(c => c.code === t).sort((a, b) => Number(b.sexCode) - Number(a.sexCode))).map(c => <tr key={`${c.code}-${c.sexCode}`}><th scope="row">{profileSectionLabels[c.code as ProfileSectionType]}</th><td>{sexLabels[c.sexCode!]}</td>{[c.LN, c.SV, c.NV, c.NS, c.specifiedCount].map((v, i) => <td key={i}>{count(v)}</td>)}<td>{percent(c.participation)}</td><td>{percent(c.reference)}</td><td>{points(c.deltaPp)}</td></tr>)}</tbody></table></div></>}
    </details>
    <details className="pp-help pp-sources"><summary>Fuentes y limitaciones</summary>
      <p>Los nombres indican posición relativa frente a pares, no preferencias ni motivaciones. No se infiere causalidad o eficacia institucional. Las elecciones son cortes transversales y los límites municipales pueden cambiar.</p><p>{dataset.source}</p>
      {dataset.enrichment && <ul className="pp-source-list">{Object.entries(dataset.enrichment.sources).map(([key, s]) => <li key={key}><strong>{key}</strong><code>{s.path}</code><span>SHA-256: {s.sha256}</span></li>)}</ul>}
    </details>
    <button type="button" className="pp-button pp-back-bottom" onClick={onClose}>← Volver a los perfiles</button>
  </section>
}
