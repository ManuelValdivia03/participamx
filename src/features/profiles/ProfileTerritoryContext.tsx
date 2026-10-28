import { useEffect, useState } from 'react'
import { StateSearch, type StateOption } from '../../components/StateSearch'
import { getProfileStateContext, getProfileStateOptions, type StateProfileContext } from '../../services/profileTerritoryContext'
import { profileCatalog } from './profilePresentation'
import { count, percent, points } from './profileEnrichment'

export function ProfileTerritoryContext({ year }: { year: number }) {
  const [territory, setTerritory] = useState('MX'), [options, setOptions] = useState<StateOption[]>([{code:'MX',name:'México'}]), [attempt, setAttempt] = useState(0)
  const [catalogError, setCatalogError] = useState(false)
  const [resource, setResource] = useState<{ key: string; rows: StateProfileContext[]; error: boolean } | null>(null)
  const key = `${year}:${territory}`
  useEffect(() => { const controller = new AbortController(); setCatalogError(false); getProfileStateOptions(year,controller.signal).then(rows=>{if(!controller.signal.aborted)setOptions(rows)}).catch(()=>{if(!controller.signal.aborted)setCatalogError(true)});return()=>controller.abort() },[year,attempt])
  useEffect(() => {
    const controller = new AbortController(); setResource(null)
    if (territory !== 'MX') getProfileStateContext(year,territory,controller.signal).then(rows=>{if(!controller.signal.aborted)setResource({key,rows,error:false})}).catch(()=>{if(!controller.signal.aborted)setResource({key,rows:[],error:true})})
    return()=>controller.abort()
  },[year,territory,key,attempt])
  const active = resource?.key === key ? resource : null
  return <section className="profile-territory-context" aria-labelledby="profile-context-title" data-profile-context={territory} data-profile-context-year={year}><header><h3 id="profile-context-title">Contexto de los perfiles en tu entidad</h3><p>Busca una entidad o selecciona México para consultar la vista nacional. Las seis fichas y sus referencias nacionales mantienen su definición.</p></header>
    <StateSearch options={options} value={territory} onChange={setTerritory} />
    {catalogError && <p role="alert">No se pudo cargar el catálogo estatal. <button type="button" className="pp-button" onClick={()=>setAttempt(n=>n+1)}>Reintentar</button></p>}
    {territory === 'MX' ? <p>Las fichas siguientes describen el conjunto nacional de {year}. Los perfiles muestran grupos estadísticos, no personas identificadas individualmente.</p> : !active ? <p role="status">Cargando contexto estatal de {year}…</p> : active.error ? <p role="alert">No hay contexto estatal disponible o no se pudo verificar. Las fichas nacionales permanecen sin cambios. <button type="button" className="pp-button" onClick={()=>setAttempt(n=>n+1)}>Reintentar</button></p> : <>
      <p><strong>{options.find(o=>o.code===territory)?.name} · {year}</strong>. Composición y tasas de los segmentos estatales ya publicados, conservando su referencia nacional por edad y sexo. Esta tabla no convierte las fichas nacionales en fichas estatales ni traslada sus cruces enriquecidos.</p>
      <p className="stat-unit-help">pp = puntos porcentuales. La proporción nominal usa la lista nominal total de la entidad, no personas ni superficie.</p>
      <div className="profile-context-scroll" tabIndex={0} role="region" aria-label="Contexto estatal de perfiles"><table className="profile-context-table"><caption>Contexto estatal; las fichas ampliadas y sus descargas siguen siendo nacionales</caption><thead><tr>{['Perfil','Segmentos','Lista nominal','% del nominal estatal','Participación observada','Referencia nacional comparable','Diferencia'].map(t=><th key={t} scope="col">{t}</th>)}</tr></thead><tbody>{profileCatalog.map(p=>{const row=active.rows.find(r=>r.profile_id===p.id);return <tr key={p.id}><th scope="row">{p.name}</th><td>{count(row?.segments)}</td><td>{count(row?.LN)}</td><td>{percent(row?.share_of_territorial_LN)}</td><td>{percent(row?.participation_observed)}{row?.has_low_support ? ' · soporte reducido' : ''}</td><td>{percent(row?.matched_peer_reference)}</td><td>{points(row?.relative_turnout == null ? null : row.relative_turnout*100)}</td></tr>})}</tbody></table></div>
    </>}
  </section>
}
