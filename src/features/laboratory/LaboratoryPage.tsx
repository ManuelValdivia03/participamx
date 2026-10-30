import { useMemo, useRef, useState } from 'react'
import '../../styles/laboratory.css'
import '../../styles/laboratory-charts.css'
import '../../styles/laboratory-usability.css'
import '../../styles/laboratory-details.css'
import { ScenarioBuilder } from './ScenarioBuilder'
import { ScenarioComparison } from './ScenarioComparison'
import { ScenarioResults } from './ScenarioResults'
import { StrategyCatalog } from './StrategyCatalog'
import { calculateScenario } from './calculations'
import { GuidedTour } from './GuidedTour'
import { strategies } from './strategies'
import type { SavedScenario, ScenarioDraft, Strategy } from './types'

const newDraft = (strategy: Strategy): ScenarioDraft => ({ name: `Escenario: ${strategy.name}`, strategyId: strategy.id, budget: '', unitCost: '', plannedUnits: '', operationalCapacity: '', assumptions: '' })

export function LaboratoryPage() {
  const [draft, setDraft] = useState(() => newDraft(strategies[0]))
  const [saved, setSaved] = useState<SavedScenario[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [tourStep, setTourStep] = useState<number | null>(null)
  const [showValidation, setShowValidation] = useState(false)
  const [duplicateAttempt, setDuplicateAttempt] = useState(false)
  const [activeSection, setActiveSection] = useState('catalog')
  const [builderFocus, setBuilderFocus] = useState(false)
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const strategy = useMemo(() => strategies.find(item => item.id === draft.strategyId) ?? strategies[0], [draft.strategyId])
  const validForSave = Boolean(draft.name.trim() && calculateScenario(draft).errors.length === 0)
  const isDuplicate = saved.some(scenario => sameScenarioValues(scenario, draft))
  const saveError = duplicateAttempt && isDuplicate ? 'Este escenario ya está guardado. Modifica alguno de sus valores para guardar una nueva alternativa' : ''
  function navigateTo(section: string) {
    const container = sectionRefs.current[section]
    if (!container) return
    setActiveSection(section)
    container.scrollIntoView?.({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' })
    window.setTimeout(() => container.querySelector<HTMLElement>('[data-lab-heading]')?.focus(), prefersReducedMotion() ? 0 : 250)
  }
  function choose(next: Strategy) {
    if (strategy.id === next.id) {
      navigateTo('builder')
      return
    }
    if (strategy.id !== next.id && hasDraftValues(draft) && !window.confirm('Cambiar de estrategia reemplazará los datos de este escenario. ¿Quieres continuar?')) return
    setDraft(newDraft(next))
    setBuilderFocus(true)
    navigateTo('builder')
    window.setTimeout(() => setBuilderFocus(false), 900)
  }
  function save() {
    setShowValidation(true)
    setDuplicateAttempt(false)
    if (!validForSave) return
    if (isDuplicate) { setDuplicateAttempt(true); return }
    const item = { ...draft, id: crypto.randomUUID(), createdAt: new Date().toISOString() }
    setSaved(value => [...value, item])
    setSelected(value => [...value, item.id].slice(-2))
  }
  function toggle(id: string) { setSelected(value => value.includes(id) ? value.filter(item => item !== id) : [...value, id].slice(-3)) }
  function remove(id: string) { setSaved(value => value.filter(item => item.id !== id)); setSelected(value => value.filter(item => item !== id)) }
  function loadExample() { if (draft.budget || draft.unitCost || draft.plannedUnits || draft.assumptions) { if (!window.confirm('Esto reemplazará los valores que estás editando con un ejemplo ficticio. ¿Deseas continuar?')) return } setDraft({ name: 'Ejemplo didáctico: guía clara', strategyId: 'clear-guide', budget: '10000', unitCost: '200', plannedUnits: '30', operationalCapacity: '40', assumptions: 'Ejemplo ficticio para entender los cálculos. No representa costos, recursos ni capacidades oficiales del INE.' }) }
  return <div className="laboratory-page"><section className="lab-hero"><p className="eyebrow">EXPLORACIÓN HIPOTÉTICA</p><h2>Laboratorio de Estrategias Cívicas</h2><p>Diseña y contrasta escenarios de recursos para propuestas informativas, institucionales y de acceso universal.</p><div className="lab-hero-actions"><button type="button" className="lab-button" onClick={() => setTourStep(0)}>¿Cómo funciona?</button><button type="button" className="lab-button secondary" onClick={loadExample}>Probar con un ejemplo</button></div><p className="lab-hero-note">No predice votos, abstención ni cambios de participación. Las estrategias no se asignan a personas, perfiles o tipos de sección.</p></section><nav className="lab-flow" aria-label="Pasos del laboratorio">{[['catalog', '1. Elige'], ['builder', '2. Prepara'], ['results', '3. Descubre'], ['comparison', '4. Compara']].map(([section, label]) => <a key={section} href={`#lab-${section}`} className={activeSection === section ? 'active' : ''} aria-current={activeSection === section ? 'step' : undefined} onClick={event => { event.preventDefault(); navigateTo(section) }}>{label}</a>)}</nav><div id="lab-catalog" ref={element => { sectionRefs.current.catalog = element }}><StrategyCatalog selectedId={strategy.id} onSelect={choose} /></div><div id="lab-builder" ref={element => { sectionRefs.current.builder = element }} className={builderFocus ? 'lab-section-focus' : ''}><ScenarioBuilder strategy={strategy} draft={draft} onChange={setDraft} showValidation={showValidation} /></div><div id="lab-results" ref={element => { sectionRefs.current.results = element }}><ScenarioResults draft={draft} onSave={save} canSave={validForSave} showValidation={showValidation} saveError={saveError} /></div><div id="lab-comparison" ref={element => { sectionRefs.current.comparison = element }}><ScenarioComparison scenarios={saved} selected={selected} onToggle={toggle} onRemove={remove} /></div>{tourStep !== null && <GuidedTour step={tourStep} onStep={setTourStep} onClose={() => setTourStep(null)} />}</div>
}

function hasDraftValues(draft: ScenarioDraft) {
  return Boolean(draft.budget || draft.unitCost || draft.plannedUnits || draft.operationalCapacity || draft.assumptions)
}

function sameScenarioValues(first: ScenarioDraft, second: ScenarioDraft) {
  const numericValue = (value: string) => value.trim() === '' ? null : Number(value)
  return first.strategyId === second.strategyId &&
    (['budget', 'unitCost', 'plannedUnits', 'operationalCapacity'] as const).every(key => numericValue(first[key]) === numericValue(second[key]))
}

function prefersReducedMotion() {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}
