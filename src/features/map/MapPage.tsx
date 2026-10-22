import { SectionCard } from '../../components/SectionCard'

export function MapPage() {
  return <><p className="page-intro">Una mirada territorial a la participación: del panorama nacional al contexto de cada municipio.</p><div className="two-columns"><SectionCard title="Explorador territorial" subtitle="México → Estado → Municipio"><div className="map-placeholder"><span className="map-target" aria-hidden="true">◎</span><h3>El territorio será nuestro punto de partida</h3><p>Aquí podrás explorar el mapa interactivo cuando se integren las geometrías y los indicadores territoriales.</p><span className="badge">Mapa pendiente de integración</span></div></SectionCard><SectionCard title="Detalle del territorio" subtitle="Contexto para interpretar los indicadores"><div className="empty-detail"><span className="tile-icon" aria-hidden="true">↗</span><h3>Primero, una ubicación</h3><p>Al seleccionar un estado o municipio, aquí aparecerán su participación, perfil y fuentes.</p></div><div className="info-row"><span>Nivel inicial</span><strong>Nacional</strong></div><div className="info-row"><span>Datos territoriales</span><strong>Pendientes</strong></div></SectionCard></div></>
}

