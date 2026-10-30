import { useState } from 'react'
import { calculateScenario, formatMXN, formatNumber } from './calculations'
import { downloadComparisonPdf, downloadScenarioPdf, downloadComparisonPng, downloadScenarioPng } from './export'
import { strategyById } from './strategies'
import type { SavedScenario, ScenarioMetrics } from './types'

export function ScenarioComparison({ scenarios, selected, onToggle, onRemove }: { scenarios: SavedScenario[]; selected: string[]; onToggle: (id: string) => void; onRemove: (id: string) => void }) {
  const [exportError, setExportError] = useState('')
  const [exporting, setExporting] = useState(false)
  const compared = scenarios.filter(scenario => selected.includes(scenario.id)).slice(0, 2)
  const differentUnits = compared.length > 1 && new Set(compared.map(scenario => strategyById(scenario.strategyId).unit)).size > 1
  const values = compared.map(scenario => ({ scenario, metrics: calculateScenario(scenario), strategy: strategyById(scenario.strategyId) }))
  const maxCost = Math.max(...values.map(item => item.metrics.projectedCost ?? 0), 1)
  const maxCapacity = Math.max(...values.map(item => item.metrics.feasibleCapacity ?? 0), 1)

  return <section className="lab-comparison" aria-labelledby="lab-comparison-title">
    <div className="lab-section-heading">
      <p className="eyebrow">ESCENARIOS GUARDADOS</p>
      <h2 id="lab-comparison-title" data-lab-heading tabIndex={-1}>Compara tus escenarios</h2>
      <p>Compara dos escenarios para ver qué cambia en el dinero, las actividades y la capacidad. La comparación no determina cuál estrategia es más eficaz.</p>
    </div>
    {scenarios.length === 0 && <div className="lab-compare-instructions"><strong>Para comparar tus escenarios:</strong><ol><li>Prepara tu primer escenario.</li><li>Guarda escenario.</li><li>Modifica las condiciones y guarda otro escenario.</li><li>Elige dos escenarios para ver sus diferencias.</li></ol></div>}
    {scenarios.length > 0 && <div className="lab-saved-list lab-scenario-cards" aria-label="Tus escenarios">{scenarios.map(scenario => {
      const isSelected = selected.includes(scenario.id)
      const selectionBlocked = !isSelected && compared.length >= 2
      return <article className={`lab-saved-card${isSelected ? ' selected' : ''}`} key={scenario.id} aria-labelledby={`saved-scenario-${scenario.id}`}>
        <div className="lab-saved-card-heading"><div><p className="lab-type">{strategyById(scenario.strategyId).name}</p><h3 id={`saved-scenario-${scenario.id}`}>{scenario.name}</h3></div><button type="button" className="lab-card-remove" onClick={() => onRemove(scenario.id)} aria-label={`Eliminar ${scenario.name}`}>Eliminar</button></div>
        <p className="lab-card-assumptions">{scenario.assumptions || 'No has escrito condiciones para este escenario.'}</p>
        <label className="lab-compare-check"><input type="checkbox" checked={isSelected} disabled={selectionBlocked} onChange={() => onToggle(scenario.id)} /> {isSelected ? 'Elegido para comparar' : 'Elegir para comparar'}</label>
        <button type="button" className="lab-button secondary lab-export-button" onClick={() => exportSavedScenario(scenario, 'pdf')} disabled={exporting}>Descargar PDF</button><button type="button" className="lab-button secondary lab-export-button" onClick={() => exportSavedScenario(scenario, 'png')} disabled={exporting}>Descargar PNG</button>
      </article>
    })}</div>}
    {compared.length === 1 && <p className="lab-compare-prompt">Elige un segundo escenario para ver la comparación.</p>}
    {compared.length >= 2 && <ComparisonView values={values} differentUnits={differentUnits} maxCost={maxCost} maxCapacity={maxCapacity} exporting={exporting} onExport={exportComparison} />}
    {exportError && <p className="lab-alert" role="alert">{exportError}</p>}
  </section>

  async function exportSavedScenario(scenario: SavedScenario, format: 'pdf' | 'png') {
    setExportError('')
    setExporting(true)
    try { if (format === 'pdf') downloadScenarioPdf(scenario); else await downloadScenarioPng(scenario) } catch (error) { setExportError(error instanceof Error ? error.message : 'No se pudo generar el documento.') } finally { setExporting(false) }
  }

  async function exportComparison(format: 'pdf' | 'png') {
    setExportError('')
    setExporting(true)
    try { if (format === 'pdf') downloadComparisonPdf(compared); else await downloadComparisonPng(compared) } catch (error) { setExportError(error instanceof Error ? error.message : 'No se pudo generar el documento.') } finally { setExporting(false) }
  }
}

function ComparisonView({ values, differentUnits, maxCost, maxCapacity, exporting, onExport }: { values: { scenario: SavedScenario; metrics: ScenarioMetrics; strategy: ReturnType<typeof strategyById> }[]; differentUnits: boolean; maxCost: number; maxCapacity: number; exporting: boolean; onExport: (format: 'pdf' | 'png') => void }) {
  const [first, second] = values
  const costDifference = (second.metrics.projectedCost ?? 0) - (first.metrics.projectedCost ?? 0)
  const budgetDifference = (second.metrics.budget ?? 0) - (first.metrics.budget ?? 0)
  const capacityDifference = (second.metrics.feasibleCapacity ?? 0) - (first.metrics.feasibleCapacity ?? 0)
  return <div className="lab-comparison-results">
    <button type="button" className="lab-button lab-export-button" onClick={() => onExport('pdf')} disabled={exporting || values.length !== 2 || values.some(item => item.metrics.errors.length > 0)}>{exporting ? 'Generando documento…' : 'Descargar comparación en PDF'}</button><button type="button" className="lab-button secondary lab-export-button" onClick={() => onExport('png')} disabled={exporting || values.length !== 2 || values.some(item => item.metrics.errors.length > 0)}>Descargar comparación en PNG</button>
    <p className="lab-compare-reading">La primera tarjeta sirve como referencia. Las diferencias dependen de las condiciones que escribiste en cada escenario.</p>
    <div className="lab-compare-summary" role="status"><strong>Lo que cambia:</strong> {formatDifference('El dinero disponible', budgetDifference)}; {formatDifference('el costo', costDifference)}.{differentUnits ? ' Las actividades usan medidas distintas, así que sus capacidades no se comparan como equivalentes.' : ` La diferencia en lo que podrías completar es de ${formatNumber(Math.abs(capacityDifference), 2)} ${first.strategy.unit}.`}</div>
    <div className="lab-cost-chart" aria-label="Gráfica comparativa de costos">{values.map(item => <ComparisonBar key={item.scenario.id} label={item.scenario.name} value={item.metrics.projectedCost} max={maxCost} format={formatMXN} />)}</div>
    {!differentUnits && <div className="lab-cost-chart lab-capacity-chart" aria-label="Gráfica comparativa de actividades que podrías completar">{values.map(item => <ComparisonBar key={item.scenario.id} label={item.scenario.name} value={item.metrics.feasibleCapacity} max={maxCapacity} format={value => `${formatNumber(value, 2)} ${item.strategy.unit}`} />)}</div>}
    {differentUnits && <p className="lab-alert" role="note">Las estrategias usan medidas distintas. Revisa cada tarjeta por separado; sus actividades y capacidades no se pueden comparar directamente.</p>}
    <div className="lab-comparison-grid">{values.map(item => <ScenarioCard key={item.scenario.id} scenario={item.scenario} metrics={item.metrics} strategy={item.strategy} />)}</div>
  </div>
}

function ScenarioCard({ scenario, metrics, strategy }: { scenario: SavedScenario; metrics: ScenarioMetrics; strategy: ReturnType<typeof strategyById> }) {
  return <article className="lab-comparison-card"><h3>{scenario.name}</h3><p className="lab-card-strategy">{strategy.name}</p><dl><div><dt>Dinero disponible</dt><dd>{formatMXN(metrics.budget)}</dd></div><div><dt>¿Cuánto costaría?</dt><dd>{formatMXN(metrics.projectedCost)}</dd></div><div><dt>¿Cuánto dinero quedaría?</dt><dd>{formatMXN(metrics.remainingBudget)}</dd></div><div><dt>Actividades que quieres realizar</dt><dd>{formatNumber(metrics.plannedUnits)} {strategy.unit}</dd></div><div><dt>Actividades que podrías completar</dt><dd>{formatNumber(metrics.feasibleCapacity, 2)} {strategy.unit}</dd></div><div><dt>Máximo de actividades</dt><dd>{formatNumber(metrics.operationalCapacity)} {strategy.unit}</dd></div></dl><p><strong>Condiciones:</strong> {scenario.assumptions || 'No has escrito condiciones.'}</p></article>
}

function ComparisonBar({ label, value, max, format }: { label: string; value: number | null; max: number; format: (value: number | null) => string }) {
  const width = value === null ? 0 : value / max * 100
  return <div><span>{label}</span><i><b style={{ width: `${width}%` }} /></i><strong>{format(value)}</strong></div>
}

function formatDifference(label: string, difference: number) {
  return `${label} ${difference === 0 ? 'no cambia' : difference > 0 ? `aumenta ${formatMXN(difference)}` : `disminuye ${formatMXN(Math.abs(difference))}`}`
}
