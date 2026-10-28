import { useRef, useState } from 'react'
import { Icon } from '../../components/Icon'
import { EnrichedProfileDetail } from './EnrichedProfileDetail'
import { ProfileComparePanel } from './ProfileComparePanel'
import { MeaningHelp } from './ProfileVisuals'
import { TransversalFinding } from './TransversalFinding'
import { count, percent, points } from './profileEnrichment'
import type { ProfileDataset } from './types'
import { useProfileInteraction } from './ProfileInteractionContext'
import { additionalSexNote, electionType } from './profileLanguage'
import '../../styles/profiles-enriched.css'

export function EnrichedProfiles({ dataset, onRetry }: { dataset: ProfileDataset; onRetry?: () => void }) {
  const { detailId, setDetailId, comparisonIds, setComparisonIds } = useProfileInteraction()
  const [message, setMessage] = useState('')
  const scrollPosition = useRef(0)
  const detail = dataset.profiles.find(p => p.id === detailId)
  const compared = dataset.profiles.filter(p => comparisonIds.includes(p.id))
  const comparison = useRef<HTMLDivElement>(null)
  const catalog = useRef<HTMLHeadingElement>(null)
  function showComparison() {
    requestAnimationFrame(() => { const title = comparison.current?.querySelector<HTMLElement>('#pp-comparison-title'); title?.focus({ preventScroll: true }); title?.scrollIntoView({ block: 'start', behavior: 'instant' }) })
  }
  function showCatalog() { catalog.current?.focus({ preventScroll: true }); catalog.current?.scrollIntoView({ block: 'start', behavior: 'instant' }) }
  function closeDetail() {
    const id = detailId
    setDetailId(null)
    requestAnimationFrame(() => { document.querySelector<HTMLButtonElement>(`[data-open-profile="${id}"]`)?.focus({ preventScroll: true }); window.scrollTo({ top: scrollPosition.current, behavior: 'instant' }) })
  }
  function toggleComparison(id: string) {
    if (comparisonIds.includes(id)) { setComparisonIds(v => v.filter(item => item !== id)); setMessage('Perfil retirado de la comparación.') }
    else if (comparisonIds.length < 3) { setComparisonIds(v => [...v, id]); setMessage(comparisonIds.length === 0 ? 'Perfil añadido. Elige otro para comparar.' : 'Comparación disponible.'); if (comparisonIds.length >= 1) showComparison() }
    else setMessage('Puedes comparar hasta tres perfiles. Retira uno antes de añadir otro.')
  }
  return <div className="participation-profiles" data-profile-year={dataset.year}>
    {detail ? <EnrichedProfileDetail key={detail.id} profile={detail} dataset={dataset} onClose={closeDetail} /> : <>
      <header className="pp-hero"><div className="pp-hero-heading"><span className="pp-section-icon"><Icon name="perfiles" /></span><p className="pp-kicker">SEIS MIRADAS · {dataset.year}</p></div>
        <h2>Perfiles de participación electoral</h2><p className="pp-lead">Los perfiles comparan la participación de grupos de edad con una referencia nacional de grupos similares. Al abrir una ficha puedes conocer sus diferencias por sexo y tipo de sección electoral.</p>
        <p>«Mayor» y «menor» indican posición frente a la referencia del mismo año, edad y sexo; no un juicio sobre las personas ni las tasas más altas o bajas del país. Son resultados agregados, no descripciones individuales.</p>
        <p className="stat-unit-help">pp = puntos porcentuales: la diferencia entre la participación y su referencia comparable.</p>
      </header>
      {dataset.year !== 2024 && <details className="pp-help pp-year-note"><summary>Sobre la elección {electionType(dataset.year)} de {dataset.year}</summary><p>Son cortes transversales: no siguen a las mismas personas ni garantizan continuidad municipal.</p><p data-category-status="unavailable_category">{additionalSexNote(dataset.year)}</p></details>}
      {dataset.enrichmentStatus === 'error' && <div className="pp-year-note" role="alert"><p>No se pudo verificar el desglose ampliado de {dataset.year}. Las seis fichas siguen disponibles con sus cifras originales.</p><button type="button" className="pp-button" onClick={onRetry}>Reintentar caracterización</button></div>}
      <div className="pp-comparison-anchor" ref={comparison}><ProfileComparePanel profiles={compared} year={dataset.year} dataset={dataset} onRemove={id => { toggleComparison(id); showComparison() }} onAdd={showCatalog} onClear={() => { setComparisonIds([]); setMessage('Comparación vaciada.'); showComparison() }} /></div>
      <div className="pp-catalog-heading"><div><p className="pp-kicker">ELIGE UNA FICHA</p><h3 ref={catalog} tabIndex={-1}>Un mismo marco, seis resultados</h3></div></div>
      <div className="pp-grid">{dataset.profiles.map((profile, index) => <article className="pp-card" key={profile.id} data-profile-card={profile.id} data-comparison-selected={comparisonIds.includes(profile.id)} aria-labelledby={`pp-name-${profile.id}`}>
        <div className="pp-card-top"><span className={`pp-card-icon pp-family-${Math.floor(index / 2)}`}><Icon name="perfiles" /></span><span className="pp-age-tag">{profile.ageBand?.replace('-', '–')} años</span></div>
        <h3 id={`pp-name-${profile.id}`}>{profile.name}</h3><p className="pp-card-criterion">{profile.id.endsWith('_unfavorable') ? 'Por debajo de su referencia comparable' : 'Por encima de su referencia comparable'}</p>
        <dl className="pp-card-metrics"><div><dt>Participación observada</dt><dd>{percent(profile.participation === null ? null : profile.participation / 100)}</dd></div><div><dt>Frente a su referencia</dt><dd>{points(profile.participationDelta)}</dd></div></dl>
        <p className="pp-card-finding"><Icon name="info" /><span>{profile.enriched ? dataset.year === 2024 && profile.id === 'adult_unfavorable' ? 'La lista nominal más amplia de las seis fichas de 2024.' : profile.enriched.distinctive : `${count(profile.segmentCount)} grupos con información suficiente en ${count(profile.municipalityCount)} municipios.`}</span></p>
        <div className="pp-card-actions"><button type="button" className="pp-button" data-open-profile={profile.id} onClick={() => { scrollPosition.current = window.scrollY; setDetailId(profile.id) }}>Explorar perfil <span aria-hidden="true">↗</span><span className="pp-sr-only">: {profile.name}</span></button><button type="button" className="pp-compare" aria-pressed={comparisonIds.includes(profile.id)} onClick={() => toggleComparison(profile.id)}>{comparisonIds.includes(profile.id) ? 'Quitar de comparación' : 'Añadir a comparación'}<span className="pp-sr-only">: {profile.name}</span></button></div>
      </article>)}</div>
      <p role="status" aria-live="polite" className="pp-selection-status">{message || 'Puedes seleccionar hasta tres fichas para comparar sus indicadores.'}</p>
      <MeaningHelp />
      {dataset.enrichment && <>
        {dataset.year === 2024 && dataset.enrichment.transversalFinding && <TransversalFinding finding={dataset.enrichment.transversalFinding} />}
        <section className="pp-overview-note" aria-labelledby="pp-average-title"><Icon name="coverage" /><div><h3 id="pp-average-title">Lo que no muestra el promedio</h3><p>Un resultado del conjunto puede ocultar diferencias entre tipos de sección electoral. Cada ficha permite explorar esos contrastes y consultar la información disponible.</p><details className="pp-help"><summary>Ver la variación interna documentada</summary><p>{count(dataset.enrichment.heterogeneity.signReversals)} de {count(dataset.enrichment.heterogeneity.eligibleCells)} subsegmentos elegibles tienen cambio de signo frente a su agregado V1. Sólo {count(dataset.enrichment.heterogeneity.bothBeyond2Pp)} tienen agregado y subsegmento a más de 2 pp de sus referencias. Son subsegmentos, no personas; la calidad de los conteos limita la interpretación.</p></details></div></section>
      </>}
      <p className="pp-caption pp-footer-source">Fuente: INE · Conteos Censales de Participación Ciudadana. Los municipios pueden aparecer en varias fichas. Los detalles estadísticos están disponibles al abrir cada perfil.</p>
      {compared.length > 0 && <div className="pp-comparison-dock"><span>{compared.length}/3 seleccionados</span><button type="button" className="pp-button" onClick={showComparison}>Ver comparación</button><button type="button" className="pp-compare" onClick={showCatalog}>Elegir perfiles</button></div>}
    </>}
  </div>
}
