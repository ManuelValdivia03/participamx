import { Icon } from '../../components/Icon'
import { SectionCard } from '../../components/SectionCard'

export function Profiles() {
  return <><p className="page-intro">Reconocer patrones de participación para comprender contextos y orientar estrategias cívicas.</p><SectionCard title="Perfiles que surgirán de los datos" subtitle="Agrupaciones construidas mediante análisis no supervisado"><div className="profiles-empty"><div className="profile-symbols" aria-hidden="true"><span><Icon name="perfiles" /></span><span><Icon name="ballot" /></span><span><Icon name="location" /></span></div><h3>Primero el análisis, después los perfiles</h3><p>Los nombres, características y cantidad final de perfiles se definirán a partir de los resultados. No hay clusters publicados todavía.</p><a className="text-link" href="#metodologia">Conocer el proceso de análisis</a></div></SectionCard><div className="two-columns feature-notes"><SectionCard title="Comparar para comprender"><p>La comparación permitirá revisar indicadores entre perfiles y reconocer sus diferencias.</p><span className="badge">Próxima etapa</span></SectionCard><SectionCard title="Del contexto a la acción"><p>Las fichas reunirán características, estrategias cívicas y opciones de exportación de reportes.</p><span className="badge">Próxima etapa</span></SectionCard></div></>
}

