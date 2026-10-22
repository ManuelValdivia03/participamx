import { Icon, type IconName } from '../components/Icon'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { Dashboard } from '../features/dashboard/Dashboard'
import { Profiles } from '../features/profiles/Profiles'
import { Methodology } from '../features/methodology/Methodology'

const MapPage = lazy(() => import('../features/map/MapPage').then(module => ({ default: module.MapPage })))

const pages = [
  { id: 'dashboard', label: 'Menú principal', icon: 'dashboard' as IconName, component: Dashboard },
  { id: 'mapa', label: 'Mapa territorial', icon: 'mapa' as IconName, component: MapPage },
  { id: 'perfiles', label: 'Perfiles ciudadanos', icon: 'perfiles' as IconName, component: Profiles },
  { id: 'metodologia', label: 'Metodología', icon: 'metodologia' as IconName, component: Methodology },
]
const currentPage = () => pages.find(page => page.id === location.hash.slice(1)) ?? pages[0]

export default function App() {
  const [page, setPage] = useState(currentPage)
  const [dark, setDark] = useState(() => document.documentElement.dataset.theme !== 'light')
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    try { localStorage.setItem('participamx-theme', dark ? 'dark' : 'light') } catch { /* Storage may be unavailable in private sessions. */ }
  }, [dark])
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
      <a className="brand" href="#dashboard"><span className="brand-symbol"><Icon name="ballot" /></span><span>Participa<span className="accent">MX</span><small>CIUDADANÍA EN PERSPECTIVA</small></span></a>
      <p className="nav-label">EXPLORA LA PARTICIPACIÓN</p>
      <nav aria-label="Navegación principal">{pages.map(item => <a key={item.id} href={`#${item.id}`} aria-current={page.id === item.id ? 'page' : undefined}><Icon name={item.icon} />{item.label}</a>)}</nav>
      <div className="sidebar-note"><span className="status-dot" /> Proyecto en construcción<p>Datos para comprender.<br />Ideas para participar.</p><small>HACKATHON INE · 2026</small></div>
    </aside>
    <div className="workspace">
      <header className="topbar"><span>Explorador de participación ciudadana</span><div className="topbar-actions"><span>México · 2009–2024</span><button className="theme-toggle" type="button" aria-label="Modo oscuro" aria-pressed={dark} onClick={() => setDark(value => !value)}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">{dark ? <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2" /></> : <path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z" />}</svg><span>{dark ? 'Modo claro' : 'Modo oscuro'}</span></button></div></header>
      <main id="contenido">
        <div className="page-heading"><div><p className="eyebrow">PARTICIPAMX / EXPLORAR</p><h1 ref={heading} tabIndex={-1}>{page.label}</h1></div><span className="badge">Versión inicial</span></div>
        <div className="notice"><Icon name="info" /><p><strong>Estamos preparando los datos.</strong> Esta versión presenta la estructura de la plataforma. Los indicadores y perfiles estarán disponibles al integrar el análisis.</p></div>
        <Suspense fallback={<p role="status" className="page-intro">Preparando el mapa de México…</p>}><Page /></Suspense>
        <footer>ParticipaMX <span>Participación ciudadana, una mirada desde los datos.</span></footer>
      </main>
    </div>
  </div>
}
