import { useCallback } from 'react'
import { getNationalStatistics } from '../../services/electionData'
import { getTerritorialDemographics } from '../../services/territorialDemographics'
import { DataQuality, ElectionMetricCards, ElectionLoading } from './ElectionMetricCards'
import { DemographicPanel } from './DemographicPanel'
import { useTerritorialResource } from './useTerritorialResource'

export function MunicipalElectionSummary({ year, ineCode, view }: { year: string; ineCode: string | null; view: 'summary' | 'demographics' }) {
  const valid = ineCode !== null && /^\d{5}$/.test(ineCode)
  const loader = useCallback(async (signal: AbortSignal) => {
    const [response, national] = await Promise.all([
      getTerritorialDemographics(Number(year), ineCode?.slice(0, 2) ?? '', signal),
      getNationalStatistics(Number(year), signal),
    ])
    return { municipality: response.data.find(item => item.ine_code === ineCode) ?? null, national }
  }, [year, ineCode])
  const { active, retry } = useTerritorialResource(valid ? `${year}:${ineCode}` : null, loader)
  if (!valid) return <div className="territorial-status"><h3>Correspondencia INE pendiente</h3><p>No se asignan cifras por proximidad ni usando la clave INEGI como sustituto. Es necesario validar la correspondencia para esta elección.</p></div>
  if (!active) return <ElectionLoading label={`Cargando ficha municipal de ${year}…`} />
  if (active.status === 'error') return <div className="territorial-status" role="alert"><p>No se pudo cargar la ficha municipal de {year}.</p><button className="map-reset" onClick={retry}>Reintentar ficha</button></div>
  const { municipality, national } = active.data
  if (!municipality) return <p className="territorial-status">No hay datos para esta clave INE en {year}. No se sustituyen por otra elección.</p>
  return <div className="territorial-data-content" key={`${year}:${ineCode}`}>
    <div hidden={view !== 'summary'}><ElectionMetricCards totals={municipality.totals} nationalRate={national.participation_observed} territory={municipality.municipality_name} year={Number(year)} />
    <DataQuality totals={municipality.totals} sourceRows={municipality.totals.source_row_count}>
      <p>Consulta de {municipality.municipality_name}, INE {ineCode}, elección {year}. La correspondencia por nombre único permite consultar la clave; no valida límites territoriales históricos idénticos.</p>
    </DataQuality></div>
    <div hidden={view !== 'demographics'}><DemographicPanel data={municipality} territory={municipality.municipality_name} year={Number(year)} /></div>
  </div>
}
