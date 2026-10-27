import { useId, useState } from 'react'
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
  const [view, setView] = useState<'summary' | 'demographics'>('summary')
  const id = useId()
  const isCity = stateCode === '09'
  const title = municipality?.properties.name ?? pendingMunicipalityName ?? stateName ?? 'México'
  return <aside id="territory-detail" className="territory-detail" data-view={view} tabIndex={-1} aria-label="Ficha electoral del territorio">
    <SectionCard title={title} subtitle={`Elección ${year} · ${municipality ? (isCity ? 'Alcaldía' : 'Municipio') : stateName ? 'Entidad federativa' : 'Panorama nacional'}`}>
      <div className="territory-heading"><Icon name={stateName ? 'location' : 'mapa'} /><span>{municipality ? `INE ${municipality.properties.ineCode ?? 'pendiente'} · INEGI ${municipality.properties.inegiCode}` : stateName ? `INE ${stateCode} · ${loading ? 'Cargando división…' : failed ? 'División sin cargar' : `${municipalityCount} ${isCity ? 'alcaldías' : 'municipios'} en el mapa 2024`}` : 'México · 32 entidades federativas'}</span></div>
      {municipality && (municipality.properties.ineCode ? <details className="key-correspondence"><summary>Correspondencia por nombre · {year}</summary><p>El nombre coincide de forma única en el estado. La geometría municipal es de 2024; esto no acredita límites históricos idénticos.</p></details> : <div className="key-correspondence quality-warning"><strong>Correspondencia territorial pendiente</strong><p>No se asignarán indicadores o perfiles mientras la equivalencia con el catálogo INE de esta elección esté pendiente.</p></div>)}
      <div className="territory-view-tabs" role="tablist" aria-label="Contenido de la ficha">{(['summary', 'demographics'] as const).map((value, index) => <button key={value} type="button" role="tab" id={`${id}-${value}`} data-territory-view={value} aria-selected={view === value} aria-controls={`${id}-panel`} tabIndex={view === value ? 0 : -1} onClick={() => setView(value)} onKeyDown={event => {
        const next = ['ArrowRight', 'ArrowLeft'].includes(event.key) ? 1 - index : event.key === 'Home' ? 0 : event.key === 'End' ? 1 : null
        if (next !== null) { event.preventDefault(); setView(next === 0 ? 'summary' : 'demographics'); event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('button')[next].focus() }
      }}><Icon name={value === 'summary' ? 'ballot' : 'perfiles'} />{value === 'summary' ? 'Resumen' : 'Edad y sexo'}</button>)}</div>
      <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-${view}`} tabIndex={0}>
      {(municipality || pendingMunicipalityName) && failed ? <p className="territorial-status" role="alert">No se pudo resolver la correspondencia de {title} en {year}. Reintenta la carga del mapa.</p> : pendingMunicipalityName || (municipality && loading) ? <ElectionLoading label={`Localizando y resolviendo datos de ${title} para ${year}…`} /> : municipality ? <>
        <MunicipalElectionSummary key={`${year}:${municipality.properties.ineCode ?? municipality.properties.inegiCode}`} year={year} ineCode={municipality.properties.ineCode} view={view} />
        <div hidden={view !== 'summary'}><MunicipalityProfiles year={year} stateCode={stateCode} ineCode={municipality.properties.ineCode} /></div>
      </> : <StateElectionSummary year={Number(year)} stateCode={stateCode} view={view} />}
      </div>
    </SectionCard>
    <p className="territory-disclaimer">Datos agregados de cuadernillos. No describen motivaciones individuales. El color representa el indicador elegido; el contorno cálido identifica la selección, no clusters.</p>
  </aside>
}
