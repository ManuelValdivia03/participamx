import { useEffect, useRef, useState } from 'react'
import { Dashboard } from '../features/dashboard/Dashboard'
import { MapPage } from '../features/map/MapPage'
import { Profiles } from '../features/profiles/Profiles'
import { Methodology } from '../features/methodology/Methodology'

const pages = [
  { id: 'dashboard', label: 'Dashboard', icon: '◫', component: Dashboard },
  { id: 'mapa', label: 'Mapa territorial', icon: '◎', component: MapPage },
  { id: 'perfiles', label: 'Perfiles ciudadanos', icon: '◇', component: Profiles },
  { id: 'metodologia', label: 'Metodología', icon: '≡', component: Methodology },
]
const currentPage = () => pages.find(page => page.id === location.hash.slice(1)) ?? pages[0]

export default function App() {
  const [page, setPage] = useState(currentPage)
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    const navigate = () => {
      setPage(currentPage())
      requestAnimationFrame(() => heading.current?.focus())
    }
    addEventListener('hashchange', navigate)
    return () => removeEventListener('hashchange', navigate)
  }, [])
  useEffect(() => { document.title = `${page.label} · ParticipaMX` }, [page])
  const Page = page.component
  return <div className="app-shell">
    <a className="skip-link" href="#contenido" onClick={event => { event.preventDefault(); heading.current?.focus() }}>Saltar al contenido</a>
    <aside className="sidebar">
      <a className="brand" href="#dashboard"><span className="brand-symbol">p•</span><span>Participa<span className="accent">MX</span><small>CIUDADANÍA EN PERSPECTIVA</small></span></a>
      <p className="nav-label">EXPLORA LA PARTICIPACIÓN</p>
      <nav aria-label="Navegación principal">{pages.map(item => <a key={item.id} href={`#${item.id}`} aria-current={page.id === item.id ? 'page' : undefined}><span aria-hidden="true">{item.icon}</span>{item.label}</a>)}</nav>
      <div className="sidebar-note"><span className="status-dot" /> Proyecto en construcción<p>Datos para comprender.<br />Ideas para participar.</p><small>HACKATHON INE · 2026</small></div>
    </aside>
    <div className="workspace">
      <header className="topbar"><span>Explorador de participación ciudadana</span><span>México · 2009–2024</span></header>
      <main id="contenido">
        <div className="page-heading"><div><p className="eyebrow">PARTICIPAMX / EXPLORAR</p><h1 ref={heading} tabIndex={-1}>{page.label}</h1></div><span className="badge">Versión inicial</span></div>
        <div className="notice"><span aria-hidden="true">ⓘ</span><p><strong>Estamos preparando los datos.</strong> Esta versión presenta la estructura de la plataforma. Los indicadores y perfiles estarán disponibles al integrar el análisis.</p></div>
        <Page />
        <footer>ParticipaMX <span>Participación ciudadana, una mirada desde los datos.</span></footer>
      </main>
    </div>
  </div>
}
