import type { Strategy } from './types'
import { strategies } from './strategies'

export function StrategyCatalog({ selectedId, onSelect }: { selectedId: string; onSelect: (strategy: Strategy) => void }) {
  return <section aria-labelledby="lab-catalog-title"><div className="lab-section-heading"><p className="eyebrow">PASO 1</p><h2 id="lab-catalog-title" data-lab-heading tabIndex={-1}>Elige una estrategia</h2><p>Seis propuestas hipotéticas para revisar; no son servicios oficiales implementados.</p></div><div className="lab-catalog">{strategies.map(strategy => { const isSelected = selectedId === strategy.id; return <article className={`lab-strategy ${isSelected ? 'selected' : ''}`} key={strategy.id} aria-current={isSelected ? 'true' : undefined}><p className="lab-type">{strategy.component}</p><h3>{strategy.name}</h3>{isSelected && <p className="lab-selected-label"><span aria-hidden="true">✓</span> Seleccionada</p>}<p>{strategy.description}</p><dl><div><dt>¿Para qué sirve?</dt><dd>{strategy.purpose}</dd></div><div><dt>¿Qué vamos a calcular?</dt><dd>{activityExplanation[strategy.id]} La unidad del simulador es <strong>{strategy.unit}</strong>: al escribir una cantidad, puedes estimar su costo, el presupuesto que usarías y cuántas actividades podrías realizar.</dd></div></dl><p className="lab-contribution"><strong>¿Cómo podría ayudar?</strong> {strategy.contribution}</p><div className="lab-indicators"><strong>¿Cómo comprobaríamos si ayuda?</strong><ul>{strategy.indicators.map(indicator => <li key={indicator}>{indicator}</li>)}</ul></div><button type="button" className="lab-button secondary" aria-pressed={isSelected} onClick={() => onSelect(strategy)}>{isSelected ? 'Estrategia elegida' : 'Elegir esta estrategia'}</button></article>})}</div></section>
}

const activityExplanation: Record<string, string> = {
  'clear-guide': 'Cada guía revisada representa un procedimiento que se prepararía y validaría.',
  'source-finder': 'Cada ficha representa una fuente oficial que se organizaría y verificaría.',
  'content-register': 'Cada versión auditada representa una revisión interna de un contenido y su historial.',
  'question-desk': 'Cada consulta documentada representa una pregunta con respuesta validada o derivación registrada.',
  'accessible-library': 'Cada formato equivalente validado representa una versión revisada para conservar el mismo contenido.',
  'referral-directory': 'Cada servicio confirmado representa un destino cuya competencia y contacto se comprobaron.',
}
