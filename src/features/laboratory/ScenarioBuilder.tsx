import type { ScenarioDraft, Strategy } from './types'

const fields: { key: keyof ScenarioDraft; label: string; hint?: string; optional?: boolean }[] = [
  { key: 'name', label: 'Nombre del escenario' },
  { key: 'budget', label: 'Presupuesto hipotético (MXN)' },
  { key: 'unitCost', label: 'Costo unitario supuesto (MXN)' },
  { key: 'plannedUnits', label: 'Unidades de actividad planificadas' },
  { key: 'operationalCapacity', label: 'Capacidad operativa', hint: 'Opcional: cantidad máxima que una operación podría atender.', optional: true },
]

export function ScenarioBuilder({ strategy, draft, onChange }: { strategy: Strategy; draft: ScenarioDraft; onChange: (draft: ScenarioDraft) => void }) {
  return <section className="lab-builder" aria-labelledby="lab-builder-title"><div className="lab-section-heading"><p className="eyebrow">PASO 2</p><h2 id="lab-builder-title">Configurar escenario</h2><p>Los montos son supuestos de exploración, no costos ni presupuestos oficiales del INE.</p></div><div className="lab-form-grid">{fields.map(field => <label key={field.key}>{field.label}{field.optional && <span> (opcional)</span>}<input type={field.key === 'name' ? 'text' : 'number'} min={field.key === 'name' ? undefined : '0'} step="any" value={draft[field.key]} onChange={event => onChange({ ...draft, [field.key]: event.target.value })} aria-describedby={field.hint ? `${field.key}-hint` : undefined} />{field.hint && <small id={`${field.key}-hint`}>{field.hint}</small>}</label>)}<label className="lab-full">Supuestos y alcance<textarea value={draft.assumptions} onChange={event => onChange({ ...draft, assumptions: event.target.value })} placeholder={`Describe qué significa una ${strategy.unit.replace(/s$/, '')}, fuentes a validar y condiciones.`} rows={4} /></label></div><p className="lab-unit-note">Unidad para esta estrategia: <strong>{strategy.unit}</strong>. No representa automáticamente personas alcanzadas.</p></section>
}
