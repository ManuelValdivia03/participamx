import { useMemo, useState } from 'react'
import '../../styles/laboratory.css'
import '../../styles/laboratory-charts.css'
import { ScenarioBuilder } from './ScenarioBuilder'
import { ScenarioComparison } from './ScenarioComparison'
import { ScenarioResults } from './ScenarioResults'
import { StrategyCatalog } from './StrategyCatalog'
import { calculateScenario } from './calculations'
import { strategies } from './strategies'
import type { SavedScenario, ScenarioDraft, Strategy } from './types'

const newDraft = (strategy: Strategy): ScenarioDraft => ({ name: `Escenario: ${strategy.name}`, strategyId: strategy.id, budget: '', unitCost: '', plannedUnits: '', operationalCapacity: '', assumptions: '' })

export function LaboratoryPage() {
  const [draft, setDraft] = useState(() => newDraft(strategies[0]))
  const [saved, setSaved] = useState<SavedScenario[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const strategy = useMemo(() => strategies.find(item => item.id === draft.strategyId) ?? strategies[0], [draft.strategyId])
  const validForSave = Boolean(draft.name.trim() && calculateScenario(draft).errors.length === 0)
  function choose(next: Strategy) { setDraft(current => ({ ...newDraft(next), name: current.strategyId === next.id ? current.name : `Escenario: ${next.name}` })) }
  function save() { if (!validForSave) return; const item = { ...draft, id: crypto.randomUUID(), createdAt: new Date().toISOString() }; setSaved(value => [...value, item]); setSelected(value => [...value, item.id].slice(-2)) }
  function toggle(id: string) { setSelected(value => value.includes(id) ? value.filter(item => item !== id) : [...value, id].slice(-3)) }
  function remove(id: string) { setSaved(value => value.filter(item => item.id !== id)); setSelected(value => value.filter(item => item !== id)) }
  return <div className="laboratory-page"><section className="lab-hero"><p className="eyebrow">EXPLORACIÓN HIPOTÉTICA</p><h2>Laboratorio de Estrategias Cívicas</h2><p>Diseña y contrasta escenarios de recursos para propuestas informativas, institucionales y de acceso universal.</p><p className="lab-hero-note">No predice votos, abstención ni cambios de participación. Las estrategias no se asignan a personas, perfiles o tipos de sección.</p></section><StrategyCatalog selectedId={strategy.id} onSelect={choose} /><ScenarioBuilder strategy={strategy} draft={draft} onChange={setDraft} /><ScenarioResults draft={draft} onSave={save} canSave={validForSave} /><ScenarioComparison scenarios={saved} selected={selected} onToggle={toggle} onRemove={remove} /><section className="lab-urm" aria-labelledby="lab-urm-title"><p className="eyebrow">CONTEXTO DESCRIPTIVO OPCIONAL</p><h2 id="lab-urm-title">Indicadores de secciones U/R/M</h2><p><strong>Información no disponible.</strong> El contrato del Atlas Electoral no está integrado en este módulo.</p><p>Cuando exista, se mostrará únicamente su año, universo, fuente, denominador, cobertura y limitaciones. U/R/M describe secciones electorales agregadas; no residencia individual, necesidades ni destinatarios, y nunca modifica automáticamente este escenario.</p></section></div>
}
