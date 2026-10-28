import { useEffect, useId, useRef, useState } from 'react'
import { Icon } from '../../components/Icon'

export const mapKeyboardHelp = 'Flechas: recorrer territorios. Enter/espacio: seleccionar. Mayús + flechas: desplazar. +/−: zoom. Escape: liberar rueda. Un clic activa el zoom con rueda hasta salir del mapa. La búsqueda y el ranking son alternativas accesibles.'
const storageKey = 'participamx-atlas-guide-v1'
const steps = [
  { title: 'Elige una elección', text: 'Usa la línea de años para consultar procesos electorales de 2009 a 2024. El territorio se conserva cuando hay correspondencia disponible.', selectors: ['.election-timeline'] },
  { title: 'Encuentra un territorio', text: 'Busca un estado o municipio por nombre. Las flechas y Enter permiten elegir una sugerencia. «Cambiar estado» abre este mismo buscador.', selectors: ['.territory-search'] },
  { title: 'Cambia el indicador', text: 'Participación, Sexo, Edad y Tipo de sección electoral son las cuatro categorías principales. Esta última permite consultar composición nominal o participación observada por Urbana, Rural y Mixta.', selectors: ['.thematic-controls'] },
  { title: 'Lee los colores', text: 'Los tonos ordenan porcentajes entre territorios comparables. Abre los rangos para ver sus límites. Un mismo color puede significar otro porcentaje en otra elección o ámbito.', selectors: ['.thematic-ramp', '.thematic-legend'] },
  { title: 'Consulta la ficha', text: 'Al señalar o seleccionar un territorio aparece su tarjeta. «Ver ficha electoral» lleva a los conteos, interpretaciones, fuentes y advertencias del territorio.', selectors: ['.map-value-open', '.map-detail-action', '.territory-detail'] },
]
type Placement = { target: { left: number; top: number; width: number; height: number } | null; left: number; top: number; width: number }

export function AtlasGuide() {
  const [invitation, setInvitation] = useState(() => { try { return !localStorage.getItem(storageKey) } catch { return true } })
  const [step, setStep] = useState<number | null>(null)
  const [placement, setPlacement] = useState<Placement | null>(null)
  const dialog = useRef<HTMLDialogElement>(null), heading = useRef<HTMLHeadingElement>(null), trigger = useRef<HTMLButtonElement>(null), opener = useRef<HTMLElement | null>(null)
  const panel = useRef<HTMLDivElement>(null)
  const id = useId()
  const description = step === 3 && document.querySelector('.territory-explorer [data-legend-mode="categorical"]')
    ? 'Los tres colores identifican Urbana, Rural y Mixta según la mayor proporción nominal del territorio. No son niveles de participación ni cuantiles; la trama neutra conserva empates exactos. Consulta la leyenda y las advertencias de soporte.'
    : step === 3 && !document.querySelector('.territory-explorer .thematic-ramp')
    ? 'Sin porcentajes comparables, el mapa usa tonos neutros. La leyenda distingue ausencia de información y soporte insuficiente; las cifras disponibles siguen consultables. No significa cero.'
    : step !== null ? steps[step].text : ''
  function start(element: HTMLElement) { opener.current = element; setStep(0) }
  function finish(status: 'completed' | 'skipped') {
    try { localStorage.setItem(storageKey, status) } catch { /* La guía funciona también sin almacenamiento. */ }
    setInvitation(false); setStep(null); setPlacement(null); dialog.current?.close()
    requestAnimationFrame(() => (opener.current?.isConnected ? opener.current : trigger.current)?.focus({ preventScroll: true }))
  }
  useEffect(() => {
    if (step === null) return
    const node = dialog.current
    if (!node) return
    if (!node.open) node.showModal()
    heading.current?.focus({ preventScroll: true })
    const target = steps[step].selectors.map(selector => document.querySelector<HTMLElement>(`.territory-explorer ${selector}`)).find(item => item?.checkVisibility())
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches
    target?.scrollIntoView({ block: 'center', behavior: reduced ? 'instant' : 'smooth' })
    let frame = 0, animationFrame = 0
    const update = () => {
      const box = target?.isConnected ? target.getBoundingClientRect() : null
      const width = Math.min(370, window.innerWidth - 28), height = Math.min(panel.current?.getBoundingClientRect().height || 300, window.innerHeight - 28)
      const targetBox = box ? { left: Math.max(7, box.left - 5), top: Math.max(7, box.top - 5), width: Math.max(0, Math.min(box.right + 5, innerWidth - 7) - Math.max(7, box.left - 5)), height: Math.max(0, Math.min(box.bottom + 5, innerHeight - 7) - Math.max(7, box.top - 5)) } : null
      const left = box && innerWidth - box.right > width + 26 ? box.right + 14 : Math.max(14, Math.min(box?.left ?? 14, innerWidth - width - 14))
      const preferredTop = box && box.bottom + height + 28 < innerHeight ? box.bottom + 14 : box && box.top > height + 28 ? box.top - height - 14 : innerHeight - height - 14
      setPlacement({ target: targetBox, width, left, top: Math.max(14, Math.min(preferredTop, innerHeight - height - 14)) })
    }
    const schedule = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(update) }
    const until = performance.now() + 650
    const animate = () => { update(); if (performance.now() < until) animationFrame = requestAnimationFrame(animate) }
    animate()
    const observer = new ResizeObserver(schedule)
    if (panel.current) observer.observe(panel.current); if (target) observer.observe(target)
    window.addEventListener('resize', schedule); window.addEventListener('scroll', schedule, true)
    return () => { cancelAnimationFrame(frame); cancelAnimationFrame(animationFrame); observer.disconnect(); window.removeEventListener('resize', schedule); window.removeEventListener('scroll', schedule, true) }
  }, [step])

  return <div className="atlas-guide-launcher">
    <button ref={trigger} type="button" className="atlas-guide-open" onClick={event => start(event.currentTarget)}><Icon name="info" /> ¿Cómo usar el Atlas?</button>
    {invitation && <p className="atlas-guide-invitation">¿Primera visita? Conoce el Atlas en cinco pasos. <button type="button" onClick={event => start(event.currentTarget)}>Iniciar guía</button><button type="button" onClick={() => finish('skipped')}>Ahora no</button></p>}
    <dialog ref={dialog} className="atlas-guide-dialog" aria-labelledby={`${id}-title`} aria-describedby={`${id}-description`} onCancel={event => { event.preventDefault(); finish('skipped') }}>
      {step !== null && <>
        {placement?.target && <div className="atlas-guide-spotlight" aria-hidden="true" style={placement.target} />}
        <div ref={panel} className="atlas-guide-panel" style={placement ? { left: placement.left, top: placement.top, width: placement.width } : undefined}>
        <div className="atlas-guide-progress" aria-live="polite">Paso {step + 1} de {steps.length}</div>
        <h3 id={`${id}-title`} ref={heading} tabIndex={-1}>{steps[step].title}</h3><p id={`${id}-description`}>{description}</p>
        {step === 4 && <details className="atlas-guide-keyboard"><summary>Atajos del mapa</summary><p>{mapKeyboardHelp}</p></details>}
        <div className="atlas-guide-navigation"><button type="button" disabled={step === 0} onClick={() => setStep(value => Math.max(0, value! - 1))}>Anterior</button><button type="button" className="atlas-guide-next" onClick={() => step === steps.length - 1 ? finish('completed') : setStep(step + 1)}>{step === steps.length - 1 ? 'Finalizar' : 'Siguiente'}</button></div>
        <button className="atlas-guide-skip" type="button" onClick={() => finish('skipped')}>Omitir guía</button>
        </div>
      </>}
    </dialog>
  </div>
}
