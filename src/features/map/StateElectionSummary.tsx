import { useCallback } from 'react'
import { getNationalStatistics } from '../../services/electionData'
import { getTerritorySummary } from '../../services/territorialDemographics'
import { DataQuality, ElectionMetricCards, ElectionLoading } from './ElectionMetricCards'
import { DemographicPanel } from './DemographicPanel'
import { useTerritorialResource } from './useTerritorialResource'
import { profileLabels } from './profileLabels'

// México y entidades comparten el sistema de fichas; la selección vacía tiene datos propios.
export function StateElectionSummary({ year, stateCode }: { year: number; stateCode: string }) {
  const loader = useCallback(async (signal: AbortSignal) => {
    const [summary, national] = await Promise.all([getTerritorySummary(year, stateCode || null, signal), getNationalStatistics(year, signal)])
    return { summary, national }
  }, [year, stateCode])
  const { active, retry } = useTerritorialResource(`${year}:${stateCode || 'national'}`, loader)
  if (!active) return <ElectionLoading label={`Cargando ficha ${stateCode ? 'estatal' : 'nacional'} de ${year}…`} />
  if (active.status === 'error') return <div className="territorial-status" role="alert"><p>No se pudieron cargar los indicadores de esta elección.</p><button className="map-reset" onClick={retry}>Reintentar indicadores</button></div>
  const { summary, national } = active.data
  return <div className="territorial-data-content" key={`${year}:${stateCode}`}>
    <ElectionMetricCards totals={summary.totals} nationalRate={national.participation_observed} territory={summary.territory_name} year={year} compareNational={!!stateCode} />
    <DemographicPanel data={summary} territory={summary.territory_name} year={year} registeredSexes={summary.registered_sexes} />
    <DataQuality totals={summary.totals} sourceRows={summary.totals.source_row_count}>
      <p>{stateCode ? 'Estadísticas de toda la entidad, no de un municipio. El soporte agregado no garantiza el soporte de cada segmento municipal.' : 'Totales nacionales de las 32 entidades, conciliados con los resúmenes de edad y sexo de esta elección.'}</p>
    </DataQuality>
    <section className="territorial-profiles"><h3>Perfiles presentes · {year}</h3><p>Segmentos con soporte. No son clasificaciones exclusivas de {stateCode ? 'la entidad' : 'México'}.</p>
      {summary.profile_ids.length ? <ul className="profile-presence">{summary.profile_ids.map(id => <li key={id}>{profileLabels[id] ?? id}</li>)}</ul> : <p>No hay perfiles con soporte disponibles.</p>}
    </section>
  </div>
}
