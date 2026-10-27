import { Icon } from '../../components/Icon'
import { SectionCard } from '../../components/SectionCard'
import { StateElectionSummary } from './StateElectionSummary'
import { MunicipalElectionSummary } from './MunicipalElectionSummary'
import { MunicipalityProfiles } from './MunicipalityProfiles'
import { ElectionLoading } from './ElectionMetricCards'
import type { Municipality } from './municipalities'

export function TerritoryPanel({ year, stateCode, stateName, municipality, municipalityCount, loading, failed, pendingMunicipalityName }: {
  year: string; stateCode: string; stateName?: string; municipality?: Municipality;
  municipalityCount: number; loading: boolean; failed: boolean; pendingMunicipalityName?: string
}) {
  const isCity = stateCode === '09'
  const title = municipality?.properties.name ?? pendingMunicipalityName ?? stateName ?? 'México'
  return <aside id="territory-detail" className="territory-detail" tabIndex={-1} aria-label="Ficha electoral del territorio">
    <SectionCard title={title} subtitle={`Elección ${year} · ${municipality ? (isCity ? 'Alcaldía' : 'Municipio') : stateName ? 'Entidad federativa' : 'Panorama nacional'}`}>
      <div className="territory-heading"><Icon name={stateName ? 'location' : 'mapa'} /><span>{municipality ? `INE ${municipality.properties.ineCode ?? 'pendiente'} · INEGI ${municipality.properties.inegiCode}` : stateName ? `INE ${stateCode} · ${loading ? 'Cargando división…' : failed ? 'División sin cargar' : `${municipalityCount} ${isCity ? 'alcaldías' : 'municipios'} en el mapa 2024`}` : 'México · 32 entidades federativas'}</span></div>
      {municipality && <div className="key-correspondence"><strong>{municipality.properties.ineCode ? `Correspondencia por nombre · ${year}` : 'Correspondencia territorial pendiente'}</strong><p>{municipality.properties.ineCode ? 'El nombre coincide de forma única en el estado. La geometría municipal es de 2024; esto no acredita límites históricos idénticos.' : 'No se asignarán indicadores o perfiles mientras la equivalencia con el catálogo INE de esta elección esté pendiente.'}</p></div>}
      {(municipality || pendingMunicipalityName) && failed ? <p className="territorial-status" role="alert">No se pudo resolver la correspondencia de {title} en {year}. Reintenta la carga del mapa.</p> : pendingMunicipalityName || (municipality && loading) ? <ElectionLoading label={`Localizando y resolviendo datos de ${title} para ${year}…`} /> : municipality ? <>
        <MunicipalElectionSummary key={`${year}:${municipality.properties.ineCode ?? municipality.properties.inegiCode}`} year={year} ineCode={municipality.properties.ineCode} />
        <MunicipalityProfiles year={year} stateCode={stateCode} ineCode={municipality.properties.ineCode} />
      </> : <StateElectionSummary year={Number(year)} stateCode={stateCode} />}
    </SectionCard>
    <p className="territory-disclaimer">Datos agregados de cuadernillos. No describen motivaciones individuales. Los colores del mapa indican selección, no participación ni clusters.</p>
  </aside>
}
