import { useRef, useState } from 'react'
import { Icon } from '../../components/Icon'
import { demoProfiles } from './demoProfiles'
import { ProfileDetail } from './ProfileDetail'
import { ProfileComparison } from './ProfileComparison'
import { formatProfileMetric, type ProfileDataset } from './types'
import { EnrichedProfiles } from './EnrichedProfiles'

export function Profiles({ dataset = demoProfiles, onRetry }: { dataset?: ProfileDataset; onRetry?: () => void }) {
  return dataset.mode === 'real' ? <EnrichedProfiles dataset={dataset} onRetry={onRetry} /> : <LegacyProfiles dataset={dataset} />
}

function LegacyProfiles({ dataset }: { dataset: ProfileDataset }) {
  const [detailId, setDetailId] = useState<string | null>(null)
  const [comparisonIds, setComparisonIds] = useState<string[]>([])
  const [message, setMessage] = useState('')
  const comparisonHeading = useRef<HTMLDivElement>(null)
  const opener = useRef<HTMLButtonElement | null>(null)
  const detail = dataset.profiles.find(profile => profile.id === detailId)
  const compared = dataset.profiles.filter(profile => comparisonIds.includes(profile.id))

  function toggleComparison(id: string) {
    if (comparisonIds.includes(id)) {
      setComparisonIds(value => value.filter(item => item !== id))
      setMessage('Perfil retirado de la comparación.')
    } else if (compared.length < 3) {
      setComparisonIds([...compared.map(profile => profile.id), id])
      setMessage('Perfil añadido a la comparación.')
    } else setMessage('Puedes comparar hasta tres perfiles. Quita uno para añadir otro.')
  }
  function closeDetail() { setDetailId(null); opener.current?.focus() }

  return <>
    <p className="page-intro">Explora las fichas y coloca sus indicadores lado a lado para conocer sus características y contexto.</p>
    {dataset.mode === 'demo' && <div className="profiles-demo-notice" role="note"><Icon name="info" /><div><strong>Demostración · Todos los datos son ficticios</strong><p>Estas fichas permiten probar la interfaz. No son resultados del INE ni perfiles definidos por el modelo. El equipo de análisis entregará los nombres, indicadores y estrategias reales.</p></div></div>}
    <div className="profiles-toolbar"><div><span className="eyebrow">{dataset.mode === 'demo' ? 'CATÁLOGO DE EJEMPLOS' : 'PERFILES CIUDADANOS'}</span><h2>{dataset.profiles.length} fichas disponibles <small>· {dataset.year}</small></h2></div><button className="profile-button" disabled={!dataset.profiles.length} onClick={() => { comparisonHeading.current?.focus(); comparisonHeading.current?.scrollIntoView({ behavior: 'instant', block: 'start' }) }}>Ver comparación ({compared.length}/3)</button></div>
    {!dataset.profiles.length && <section className="card comparison-empty"><h2>Los perfiles todavía no están disponibles</h2><p>Aparecerán cuando el equipo de análisis entregue sus resultados.</p></section>}
    <div className="profiles-catalog">{dataset.profiles.map((profile, index) => <article className="profile-card" key={profile.id} aria-labelledby={`profile-${profile.id}`}>
      <div className="profile-card-top"><span className={`profile-emblem emblem-${index % 4}`} aria-hidden="true"><Icon name="perfiles" /></span><span>{dataset.mode === 'demo' ? 'EJEMPLO FICTICIO' : `PERFIL · ${dataset.year}`}</span></div><h2 id={`profile-${profile.id}`}>{profile.name}</h2><p>{profile.summary}</p>
      <dl className="profile-card-metrics"><div><dt>Participación{dataset.mode === 'demo' && ' simulada'}</dt><dd>{formatProfileMetric(profile.participation, '%')}</dd></div><div><dt>Municipios{dataset.mode === 'demo' && ' de ejemplo'}</dt><dd>{formatProfileMetric(profile.municipalityCount, '')}</dd></div></dl>
      <div className="profile-card-actions"><button className="profile-button secondary" aria-expanded={detailId === profile.id} aria-controls={detailId === profile.id ? 'profile-detail-title' : undefined} onClick={event => { opener.current = event.currentTarget; setDetailId(profile.id) }}>Ver ficha</button><button className="profile-compare-toggle" aria-pressed={comparisonIds.includes(profile.id)} onClick={() => toggleComparison(profile.id)}>{comparisonIds.includes(profile.id) ? 'Quitar de comparación' : 'Añadir a comparación'}</button></div>
    </article>)}</div>
    <p className="profile-selection-message" role="status" aria-live="polite">{message || 'Selecciona entre dos y tres fichas para compararlas.'}</p>
    {detail && <ProfileDetail profile={detail} dataset={dataset} onClose={closeDetail} />}
    <div className="comparison-anchor" ref={comparisonHeading} tabIndex={-1}><ProfileComparison profiles={compared} dataset={dataset} onRemove={toggleComparison} />{compared.length > 0 && <button className="profile-button secondary clear-comparison" onClick={() => { setComparisonIds([]); setMessage('Comparación vaciada.') }}>Vaciar comparación</button>}</div>
    <p className="profile-source">Fuente: {dataset.source} {dataset.mode === 'demo' && 'Los ejemplos incluyen datos incompletos para probar su presentación.'}</p>
  </>
}
