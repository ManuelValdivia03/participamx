import { useCallback } from 'react'
import { getMunicipalityProfiles } from '../../services/municipalityProfiles'
import { useTerritorialResource } from './useTerritorialResource'
import { profileLabels } from './profileLabels'
import { formatCount, formatPercent, formatPoints } from './territorialData'

export function MunicipalityProfiles({ year, stateCode, ineCode }: { year: string; stateCode: string; ineCode: string | null }) {
  const valid = ineCode !== null && /^\d{5}$/.test(ineCode) && ineCode.startsWith(stateCode)
  const loader = useCallback(async (signal: AbortSignal) => {
    const rows = await getMunicipalityProfiles(Number(year), stateCode, signal)
    return rows.filter(row => row.municipality_code === ineCode?.slice(2)).sort((a, b) => Object.keys(profileLabels).indexOf(a.profile_id) - Object.keys(profileLabels).indexOf(b.profile_id))
  }, [year, stateCode, ineCode])
  const { active, retry } = useTerritorialResource(valid ? `${year}:${ineCode}` : null, loader)
  if (!valid) return null
  if (!active) return <p className="territorial-status" role="status">Cargando perfiles municipales de {year}…</p>
  if (active.status === 'error') return <div className="territorial-status" role="alert"><p>No se pudieron cargar los perfiles de {year}.</p><button className="map-reset" onClick={retry}>Reintentar perfiles</button></div>
  return <details className="territorial-profiles"><summary>Perfiles presentes · {year} <span>{active.data.length}</span></summary>
    <p>Segmentos agregados del municipio; no clasificaciones exclusivas del territorio ni de personas. Referencias del mismo año, banda y sexo.</p>
    {!active.data.length && <p>No hay segmentos con perfil disponible para esta clave y elección.</p>}
    <div className="territorial-profile-list">{active.data.map(profile => <article className="territorial-profile-card" key={profile.profile_id}>
      <h4>{profileLabels[profile.profile_id] ?? profile.profile_id}</h4>
      <div className="profile-rate-pair"><span>Participación de sus segmentos <b>{formatPercent(profile.participation_observed)}</b></span><span>Frente a sus pares <b>{formatPoints(profile.relative_turnout === null ? null : profile.relative_turnout * 100)}</b></span></div>
      <p>Referencia de pares: {formatPercent(profile.matched_peer_reference)} · Segmentos: {formatCount(profile.segments)} · Lista nominal: {formatCount(profile.LN)}</p>
      {profile.has_low_support && <p className="quality-warning">Soporte reducido.</p>}{profile.has_high_ns && <p className="quality-warning">Participación no especificada elevada.</p>}
    </article>)}</div>
    <p>No sumar tasas o coberturas entre perfiles. No se infieren cambios individuales entre elecciones.</p>
  </details>
}
