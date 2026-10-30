import { useState } from 'react'
import { calculateScenario, formatMXN, formatNumber } from './calculations'
import { downloadScenarioPdf, downloadScenarioPng } from './export'
import { scenarioDiagnosis } from './diagnosis'
import { strategyById } from './strategies'
import type { ScenarioDraft } from './types'

export function ScenarioResults({ draft, onSave, canSave, showValidation = false, saveError = '' }: { draft: ScenarioDraft; onSave: () => void; canSave: boolean; showValidation?: boolean; saveError?: string }) {
  const [exportError, setExportError] = useState('')
  const [exporting, setExporting] = useState<'pdf' | 'png' | null>(null)
  const metrics = calculateScenario(draft)
  const strategy = strategyById(draft.strategyId)
  const plannedUnits = metrics.plannedUnits
  const operationalCapacity = metrics.operationalCapacity
  const hasCompleteData = metrics.errors.length === 0
  const budgetEnough = hasCompleteData && metrics.remainingBudget !== null && metrics.remainingBudget >= 0
  const operationKnown = operationalCapacity !== null
  const operationEnough = operationKnown && plannedUnits !== null && plannedUnits <= operationalCapacity
  const budgetCapacity = metrics.theoreticalCapacity
  const feasibleCapacity = metrics.feasibleCapacity ?? (operationKnown ? null : budgetCapacity)
  const capacityForChart = feasibleCapacity ?? 0
  const budgetPercent = metrics.budgetPercent ?? 0
  const budgetChartWidth = Math.min(Math.max(budgetPercent, 0), 100)
  const activityChartWidth = metrics.plannedUnits !== null && capacityForChart > 0 ? Math.min(metrics.plannedUnits / capacityForChart * 100, 100) : 0
  const diagnosis = scenarioDiagnosis(metrics, strategy.unit)
  async function exportScenario(format: 'pdf' | 'png') {
    setExportError('')
    setExporting(format)
    try { if (format === 'pdf') downloadScenarioPdf(draft); else await downloadScenarioPng(draft) } catch (error) { setExportError(error instanceof Error ? error.message : 'No se pudo generar el documento.') } finally { setExporting(null) }
  }

  return <section className="lab-results" aria-labelledby="lab-results-title">
    <div className="lab-section-heading">
      <p className="eyebrow">PASO 3</p>
      <h2 id="lab-results-title" data-lab-heading tabIndex={-1}>Descubre tus resultados</h2>
      <p>Lee estos cálculos como una revisión del escenario que escribiste. No son predicciones ni resultados reales.</p>
    </div>
    {showValidation && metrics.errors.length > 0 && <div className="lab-alert" role="alert">{metrics.errors.map(error => <p key={error}>{friendlyError(error)}</p>)}</div>}
    <section className="lab-diagnosis" aria-labelledby="lab-diagnosis-title">
      <div>
        <p className="eyebrow">RESUMEN DEL ESCENARIO</p>
        <h3 id="lab-diagnosis-title">{diagnosis.title}</h3>
      </div>
      <div className="lab-diagnosis-status">
        <Status label="Presupuesto" state={!hasCompleteData ? 'incomplete' : budgetEnough ? 'ok' : 'warning'} text={!hasCompleteData ? 'Información incompleta' : budgetEnough ? 'Suficiente' : 'Insuficiente'} />
        <Status label="Capacidad de trabajo" state={!hasCompleteData || !operationKnown ? 'incomplete' : operationEnough ? 'ok' : 'warning'} text={!hasCompleteData || !operationKnown ? 'Todavía no has indicado este dato' : operationEnough ? 'Suficiente' : 'Insuficiente'} />
      </div>
    </section>
    {hasCompleteData && <div className="lab-diagnosis-explanation"><p>{diagnosis.budget}</p><p>{diagnosis.operation}</p></div>}
    <dl className="lab-metrics lab-metrics-expanded">
      <Metric label="Presupuesto disponible" value={formatMXN(metrics.budget)} help="El dinero con el que comenzarías este escenario." />
      <Metric label="¿Cuánto costaría?" value={formatMXN(metrics.projectedCost)} help="Lo que costaría realizar las actividades que elegiste." />
      <Metric label="¿Cuánto dinero quedaría?" value={formatMXN(metrics.remainingBudget)} help="El dinero que quedaría después de cubrir el costo." negative={metrics.remainingBudget !== null && metrics.remainingBudget < 0} />
      <Metric label="¿Qué parte del presupuesto usarías?" value={metrics.budgetPercent === null ? 'Completa los datos para ver el resultado' : `${formatNumber(metrics.budgetPercent, 1)}%`} help="La parte del dinero disponible que usarías." />
      <Metric label="¿Cuántas actividades podrías pagar?" value={metrics.unitCost === 0 ? 'No se puede calcular con costo cero' : formatNumber(metrics.theoreticalCapacity, 2)} help="La cantidad de actividades que podrías pagar con el dinero indicado." suffix={metrics.theoreticalCapacity === null ? undefined : strategy.unit} />
      <Metric label="¿Cuántas actividades podrías realizar como máximo?" value={metrics.operationalCapacity === null ? 'Todavía no has indicado este dato' : formatNumber(metrics.operationalCapacity)} help="El máximo de actividades que indicaste que podrían realizarse." suffix={metrics.operationalCapacity === null ? undefined : strategy.unit} />
      <Metric label="¿Cuántas actividades podrías completar?" value={metrics.feasibleCapacity === null ? 'Completa los datos para ver el resultado' : formatNumber(metrics.feasibleCapacity, 2)} help="La cantidad que permiten al mismo tiempo el dinero y la capacidad de trabajo indicados." suffix={metrics.feasibleCapacity === null ? undefined : strategy.unit} />
    </dl>
    <div className="lab-result-charts">
      <ComparisonBar title="Dinero que usarías" detail={metrics.budgetPercent === null ? 'Completa los datos para ver el resultado.' : `Usarías ${formatNumber(metrics.budgetPercent, 1)}% del dinero disponible.`} valueLabel={metrics.budgetPercent === null ? 'Completa los datos' : `${formatNumber(metrics.budgetPercent, 1)} por ciento`} width={budgetChartWidth} />
      <ComparisonBar title="Actividades frente a lo que podrías completar" detail={plannedUnits === null || feasibleCapacity === null ? 'Completa los datos para comparar.' : `Quieres realizar ${formatNumber(plannedUnits)} y podrías completar ${formatNumber(feasibleCapacity, 2)}.`} valueLabel={plannedUnits === null ? 'Completa los datos' : `${formatNumber(plannedUnits)} planeadas`} width={activityChartWidth} warning={hasCompleteData && metrics.resourceDifference !== null && metrics.resourceDifference < 0} />
    </div>
    {hasCompleteData && metrics.resourceDifference !== null && <p className={metrics.resourceDifference < 0 ? 'lab-deficit' : 'lab-capacity'}>{metrics.resourceDifference < 0 ? `Planeaste ${formatNumber(plannedUnits)} ${strategy.unit}, pero con los recursos que indicaste sólo podrías completar ${formatNumber(Math.max(0, metrics.resourceDifference + (plannedUnits ?? 0)), 2)}. Te faltarían ${formatNumber(Math.abs(metrics.resourceDifference), 2)} para completar el plan.` : `Planeaste ${formatNumber(plannedUnits)} ${strategy.unit} y todavía podrías completar ${formatNumber(metrics.resourceDifference, 2)} más con los recursos indicados.`}</p>}
    <p className="lab-result-note">{!hasCompleteData ? 'Completa los datos para revisar si el dinero y la capacidad alcanzan.' : operationKnown && !operationEnough ? 'Planeaste más actividades de las que podrías realizar con la capacidad indicada. Revisa por separado la disponibilidad de presupuesto.' : !budgetEnough ? 'El costo de las actividades supera el dinero disponible. Puedes cambiar la cantidad, el costo o el presupuesto.' : 'El dinero y la capacidad indicados alcanzan para este plan. Esto sólo describe una relación matemática entre tus supuestos.'}</p>
    <button type="button" className="lab-button" onClick={onSave} disabled={!draft.name.trim()} aria-disabled={!canSave}>Guardar escenario</button>
    {saveError && <p className="lab-alert" role="alert">{saveError}</p>}
    <div className="lab-export-actions"><button type="button" className="lab-button secondary lab-export-button" onClick={() => exportScenario('pdf')} disabled={!canSave || exporting !== null}>{exporting === 'pdf' ? 'Generando PDF…' : 'Descargar resultados en PDF'}</button><button type="button" className="lab-button secondary lab-export-button" onClick={() => exportScenario('png')} disabled={!canSave || exporting !== null}>{exporting === 'png' ? 'Generando PNG…' : 'Descargar resultados en PNG'}</button></div>
    {exportError && <p className="lab-alert" role="alert">{exportError}</p>}
    <section id="lab-evaluation" className="lab-evaluation"><h3>¿Cómo evaluaríamos esta propuesta?</h3><p>Los indicadores de evaluación describen qué podría observarse durante una implementación; no son resultados logrados.</p><ol><li><strong>Resultados calculados:</strong> presupuesto, costo, saldo y capacidades provienen exclusivamente de los supuestos de este escenario.</li><li><strong>Indicadores durante una implementación:</strong> {strategy.indicators.join('; ')}.</li><li><strong>Resultados reales:</strong> todavía no disponibles. Ningún cálculo estima voto, abstención ni efecto electoral.</li></ol></section>
  </section>
}

function friendlyError(error: string) {
  if (error.includes('obligatorio')) return error.includes('presupuesto') ? 'Escribe cuánto dinero tendrías disponible.' : error.includes('costo') ? 'Indica cuánto costaría cada actividad.' : 'Indica cuántas actividades quieres realizar.'
  if (error.includes('finito')) return 'Escribe una cantidad válida, igual o mayor que cero.'
  if (error.includes('cantidad entera')) return 'Escribe una cantidad entera, sin decimales.'
  if (error.includes('límite numérico')) return 'La cantidad es demasiado grande para calcularla.'
  return error
}

function Metric({ label, value, suffix, help, negative = false }: { label: string; value: string; suffix?: string; help: string; negative?: boolean }) {
  return <div className={negative ? 'negative' : ''}><dt>{label}</dt><dd>{value}</dd>{suffix && <small>{suffix}</small>}<p>{help}</p></div>
}

function Status({ label, state, text }: { label: string; state: 'ok' | 'warning' | 'incomplete'; text: string }) {
  return <div className={`lab-status lab-status-${state}`}><strong>{label}</strong><span>{text}</span></div>
}

function ComparisonBar({ title, detail, valueLabel, width, warning = false }: { title: string; detail: string; valueLabel: string; width: number; warning?: boolean }) {
  return <div className="lab-comparison-bar"><div><strong>{title}</strong><span>{valueLabel}</span></div><div className={`lab-bar-track${warning ? ' warning' : ''}`} role="img" aria-label={`${title}: ${detail}`}><span style={{ width: `${width}%` }} /></div><p>{detail}</p></div>
}
