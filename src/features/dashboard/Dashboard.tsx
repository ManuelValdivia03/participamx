import { Icon } from '../../components/Icon'
import { CivicArt } from '../../components/CivicArt'
import { SectionCard } from '../../components/SectionCard'

export function Dashboard() {
  return <>
    <section className="hero"><div><p className="eyebrow">OBSERVATORIO DE PARTICIPACIÓN CIUDADANA</p><h2>La participación<br /><span>tiene muchas<br />formas.</span></h2><p>Explora cómo participa la ciudadanía y descubre las diferencias que dan forma a nuestro territorio.</p><a className="button" href="#mapa">Explorar el territorio</a></div><CivicArt /></section>
    <div className="metrics">{['Participación electoral', 'Cobertura territorial', 'Perfiles identificados'].map((title, i) => <section className="card metric" key={title}><span className="metric-index">0{i + 1} / INDICADOR</span><h2>{title}</h2><p className="metric-value">—</p><p>Pendiente de integrar datos</p></section>)}</div>
    <div className="two-columns"><SectionCard title="Participación a través del tiempo" subtitle="Evolución de los indicadores electorales"><div className="chart-placeholder"><Icon name="dashboard" /><h3>Una historia por descubrir</h3><p>La gráfica aparecerá cuando estén disponibles las series de datos validadas.</p></div><div className="chart-caption"><span>2009</span><span>Periodo de análisis</span><span>2024</span></div></SectionCard><SectionCard title="Explora desde otra perspectiva" subtitle="Dos formas de acercarte a la ciudadanía"><a className="explore-link" href="#mapa"><span className="tile-icon"><Icon name="mapa" /></span><div><h3>El territorio</h3><p>De México a sus estados y municipios.</p></div><span className="link-action">Explorar</span></a><a className="explore-link" href="#perfiles"><span className="tile-icon purple"><Icon name="perfiles" /></span><div><h3>Los perfiles</h3><p>Patrones de participación y sus diferencias.</p></div><span className="link-action">Explorar</span></a><p className="small-note">Los resultados se mostrarán con su fuente y contexto.</p></SectionCard></div>
  </>
}

