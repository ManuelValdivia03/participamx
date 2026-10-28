import { useState } from 'react'
import { calculateScenario } from './calculations'
import type { ScenarioDraft, Strategy } from './types'

type Field = {
  key: 'budget' | 'unitCost' | 'plannedUnits' | 'operationalCapacity'
  label: string
  description: string
  example: string
  errorLabel: string
  optional?: boolean
  integer?: boolean
}

const fields: Field[] = [
  { key: 'budget', label: '¿Con cuánto dinero contarías? (MXN)', description: 'El dinero que tendrías disponible para este escenario.', example: '$10,000', errorLabel: 'El presupuesto' },
  { key: 'unitCost', label: '¿Cuánto costaría cada actividad? (MXN)', description: 'El costo que supones para realizar una actividad.', example: '$200', errorLabel: 'El costo unitario' },
  { key: 'plannedUnits', label: '¿Cuántas actividades quieres realizar?', description: 'La cantidad de actividades que te gustaría completar.', example: '30', errorLabel: 'Las unidades planificadas', integer: true },
  { key: 'operationalCapacity', label: '¿Cuántas actividades podrían realizarse como máximo?', description: 'El máximo de actividades que podrían realizarse. Es opcional.', example: '40', errorLabel: 'La capacidad operativa', optional: true, integer: true },
]

export function ScenarioBuilder({ strategy, draft, onChange, showValidation = false }: { strategy: Strategy; draft: ScenarioDraft; onChange: (draft: ScenarioDraft) => void; showValidation?: boolean }) {
  const metrics = calculateScenario(draft)
  const [touched, setTouched] = useState<Set<string>>(new Set())
  const errors = new Map(fields.map(field => [field.key, (showValidation || touched.has(field.key) || draft[field.key] !== '') ? metrics.errors.find(error => error.startsWith(field.errorLabel)) : undefined]))
  const unit = strategy.unit.replace(/s$/, '')

  function update(key: keyof ScenarioDraft, value: string) {
    onChange({ ...draft, [key]: value })
  }

  return <section className="lab-builder" aria-labelledby="lab-builder-title">
    <div className="lab-section-heading">
      <p className="eyebrow">PASO 2</p>
      <h2 id="lab-builder-title" data-lab-heading tabIndex={-1}>Prepara tu escenario</h2>
      <p>Define una situación hipotética para entender qué recursos necesitaría una propuesta. Puedes modificar los valores sin perderlos al recorrer las secciones.</p>
    </div>
    <div className="lab-builder-guide" aria-label="Cómo completar el escenario">
      <div><strong>1. Nómbralo</strong><span>Escribe un nombre y revisa qué actividad simula.</span></div>
      <div><strong>2. Revisa tus recursos</strong><span>Relaciona el dinero disponible con el costo de cada actividad.</span></div>
      <div><strong>3. Decide qué realizar</strong><span>Compara lo que quieres hacer con lo que podrías completar.</span></div>
    </div>
    <div className="lab-form-grid">
      <fieldset className="lab-form-group lab-full">
        <legend>Ponle un nombre a tu escenario</legend>
        <p className="lab-group-help">El nombre sólo sirve para reconocer este escenario cuando lo guardes.</p>
        <label htmlFor="scenario-name">Nombre del escenario
          <input id="scenario-name" type="text" value={draft.name} onChange={event => update('name', event.target.value)} />
        </label>
        <div className="lab-strategy-context"><strong>Estrategia elegida:</strong> {strategy.name}<span>En este escenario realizarías actividades como: {strategy.unit}.</span></div>
      </fieldset>
      <fieldset className="lab-form-group">
        <legend>¿Con qué recursos contarías?</legend>
        <p className="lab-group-help">Son cantidades supuestas, no costos oficiales. El costo total se calcula multiplicando el costo de cada actividad por la cantidad que quieres realizar.</p>
        {fields.slice(0, 2).map(field => <FieldInput key={field.key} field={field} value={draft[field.key]} error={errors.get(field.key)} onChange={value => update(field.key, value)} onBlur={() => setTouched(current => new Set(current).add(field.key))} />)}
      </fieldset>
      <fieldset className="lab-form-group">
        <legend>¿Qué quieres realizar?</legend>
        <p className="lab-group-help">Indica cuántas actividades te gustaría realizar y, si lo sabes, cuántas podrían hacerse como máximo.</p>
        {fields.slice(2).map(field => <FieldInput key={field.key} field={field} value={draft[field.key]} error={errors.get(field.key)} onChange={value => update(field.key, value)} onBlur={() => setTouched(current => new Set(current).add(field.key))} unit={strategy.unit} />)}
      </fieldset>
      <fieldset className="lab-form-group lab-full">
        <legend>Explica las condiciones de tu escenario</legend>
        <p className="lab-group-help">Anota qué incluye una actividad, qué información tendría que revisarse y qué condiciones podrían cambiar el resultado.</p>
        <label htmlFor="scenario-assumptions">Condiciones y notas del escenario
          <textarea id="scenario-assumptions" value={draft.assumptions} onChange={event => update('assumptions', event.target.value)} placeholder={`Ejemplo: una ${unit} requiere revisión y validación de contenido.`} rows={4} />
        </label>
      </fieldset>
    </div>
    <p className="lab-unit-note">Actividad de esta estrategia: <strong>{strategy.unit}</strong>. Es una medida de trabajo; no representa automáticamente personas alcanzadas.</p>
  </section>
}

function FieldInput({ field, value, error, onChange, onBlur, unit }: { field: Field; value: string; error?: string; onChange: (value: string) => void; onBlur: () => void; unit?: string }) {
  const id = `scenario-${field.key}`
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const accessibleLabel = `${field.label}${field.optional ? ' (opcional)' : ''}`
  const friendlyError = field.key === 'budget' ? 'Escribe cuánto dinero tendrías disponible.' : field.key === 'unitCost' ? 'Indica cuánto costaría cada actividad.' : field.key === 'plannedUnits' ? 'Indica cuántas actividades quieres realizar.' : 'Indica cuántas actividades podrían realizarse como máximo o deja este campo vacío.'
  return <label htmlFor={id}>{field.label}{field.optional && <span> (opcional)</span>}
    <input id={id} aria-label={accessibleLabel} type="number" min="0" step={field.integer ? '1' : 'any'} value={value} onChange={event => onChange(event.target.value)} onBlur={onBlur} aria-describedby={`${hintId}${error ? ` ${errorId}` : ''}`} aria-invalid={Boolean(error)} />
    <small id={hintId}>{field.description} Ejemplo: {field.example}{unit && ` (${unit})`}</small>
    {error && <span id={errorId} className="lab-field-error" role="alert">{friendlyError}</span>}
  </label>
}
