import { useEffect, useLayoutEffect, useRef, useState } from 'react'

type TourStep = { target: string; title: string; what: string; why: string; how: string }
type Position = { top: number; left: number; placement: 'top' | 'bottom' | 'left' | 'right' | 'center' }

export const tourSteps: TourStep[] = [
  { target: '#lab-catalog .lab-strategy:first-child', title: '1. Elige una estrategia', what: 'Cada tarjeta presenta una propuesta hipotética.', why: 'Te ayuda a explorar una forma distinta de ofrecer información clara y accesible.', how: 'Lee la tarjeta y elige la que quieras revisar. No representa un servicio oficial ni una campaña.' },
  { target: '#lab-catalog .lab-strategy.selected', title: '2. Confirma tu elección', what: 'Esta tarjeta muestra la estrategia que usarás.', why: 'La actividad de esta estrategia define cómo leerás los resultados.', how: 'Revísala y continúa. Puedes elegir otra antes de guardar tu escenario.' },
  { target: '#scenario-budget', title: '3. Indica con cuánto dinero contarías', what: 'Es el dinero que supones que tendrías disponible.', why: 'Sirve para calcular cuántas actividades podrías pagar.', how: 'Escribe una cantidad en pesos. Es un ejemplo, no un presupuesto oficial.' },
  { target: '#scenario-unitCost', title: '4. Indica cuánto costaría cada actividad', what: 'Es el costo que supones para realizar una actividad.', why: 'Al multiplicarlo por la cantidad de actividades se obtiene el costo total.', how: 'Escribe un costo y explica en tus condiciones qué incluye.' },
  { target: '#scenario-plannedUnits', title: '5. Decide cuántas actividades quieres realizar', what: 'Es la cantidad de actividades que te gustaría completar.', why: 'Permite comparar tu plan con el dinero y la capacidad disponibles.', how: 'Escribe un número entero y usa la actividad de la estrategia como referencia.' },
  { target: '#scenario-operationalCapacity', title: '6. Indica cuántas podrían realizarse', what: 'Es el máximo de actividades que podrían hacerse.', why: 'Ayuda a saber si tu plan supera la capacidad de trabajo.', how: 'Es opcional. Escríbelo sólo si tienes un límite que quieras probar.' },
  { target: '#scenario-assumptions', title: '7. Explica las condiciones', what: 'Aquí puedes anotar qué incluye una actividad y qué información debe revisarse.', why: 'Tus notas ayudan a entender el cálculo y comparar escenarios.', how: 'Escribe las condiciones que estás suponiendo. Recuerda que son datos hipotéticos.' },
  { target: '#lab-results .lab-diagnosis', title: '8. Lee el diagnóstico', what: 'Resume si el dinero y la capacidad alcanzan.', why: 'Te muestra por separado qué límite puede afectar tu plan.', how: 'Si falta información o algo es insuficiente, completa los datos y no lo consideres viable todavía.' },
  { target: '#lab-results .lab-metrics-expanded', title: '9. Revisa los resultados', what: 'Estas tarjetas muestran el dinero, el costo y las actividades.', why: 'Te permiten entender qué se puede pagar y qué se podría completar.', how: 'Lee la explicación de cada tarjeta y revisa siempre la actividad indicada.' },
  { target: '#lab-results .lab-result-charts', title: '10. Observa las gráficas', what: 'Las barras comparan el dinero y las actividades.', why: 'Ayudan a ver rápidamente qué límite condiciona el escenario.', how: 'Úsalas junto con los números. No miden eficacia electoral.' },
  { target: '#lab-results button[aria-label], #lab-results > button.lab-button', title: '11. Guarda tu escenario', what: 'Este botón guarda temporalmente lo que escribiste.', why: 'Así puedes modificar las condiciones y comparar otra opción.', how: 'Guárdalo cuando los datos sean válidos y después prepara otro escenario.' },
  { target: '#lab-comparison .lab-saved-card:first-child, #lab-comparison .lab-compare-instructions', title: '12. Compara tus escenarios', what: 'Estas tarjetas reúnen los escenarios que guardaste.', why: 'Te ayudan a ver cómo cambian el dinero, el costo y la capacidad.', how: 'Elige dos escenarios. Si usan actividades distintas, revisa la advertencia y no compares sus cantidades.' },
  { target: '#lab-evaluation', title: '13. Interpreta con cuidado', what: 'Esta sección separa cálculos, posibles indicadores y resultados reales.', why: 'Una simulación no demuestra que una propuesta funcione en la realidad.', how: 'Usa los cálculos para explorar. Los resultados reales todavía no están disponibles.' },
]

const focusable = 'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), a[href]'

export function GuidedTour({ step, onStep, onClose }: { step: number; onStep: (step: number) => void; onClose: () => void }) {
  const dialog = useRef<HTMLDivElement>(null)
  const previousFocus = useRef<HTMLElement | null>(null)
  const [position, setPosition] = useState<Position>({ top: 0, left: 0, placement: 'center' })
  const current = tourSteps[step] ?? tourSteps[0]

  useEffect(() => {
    previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    return () => previousFocus.current?.focus()
  }, [])

  useLayoutEffect(() => {
    const target = document.querySelector<HTMLElement>(current.target)
    document.querySelectorAll<HTMLElement>('.lab-tour-target').forEach(element => element.classList.remove('lab-tour-target'))
    target?.classList.add('lab-tour-target')
    if (target) {
      const reducedMotion = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
      if (typeof target.scrollIntoView === 'function') {
        const block = target.getBoundingClientRect().width > window.innerWidth * 0.7 ? 'start' : 'center'
        target.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block })
      }
      requestAnimationFrame(() => setPosition(getPosition(target, dialog.current)))
    } else {
      setPosition({ top: 24, left: Math.max(16, (window.innerWidth - 420) / 2), placement: 'center' })
    }
    dialog.current?.focus()
    return () => target?.classList.remove('lab-tour-target')
  }, [current.target])

  useEffect(() => {
    const target = document.querySelector<HTMLElement>(current.target)
    const update = () => setPosition(target ? getPosition(target, dialog.current) : { top: 24, left: Math.max(16, (window.innerWidth - 420) / 2), placement: 'center' })
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
      }
      if (event.key !== 'Tab' || !dialog.current) return
      const elements = Array.from(dialog.current.querySelectorAll<HTMLElement>(focusable))
      if (elements.length === 0) return
      const first = elements[0]
      const last = elements[elements.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('resize', update)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('resize', update)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [current.target, onClose])

  const target = document.querySelector<HTMLElement>(current.target)
  const isWideTarget = target ? target.getBoundingClientRect().width > window.innerWidth * 0.7 : false
  return <div className={`lab-tour-backdrop${isWideTarget ? ' lab-tour-wide-target' : ''}`} role="presentation">
    <div className={`lab-tour lab-tour-${position.placement}`} role="dialog" aria-modal="true" aria-labelledby="lab-tour-title" tabIndex={-1} ref={dialog} style={{ top: position.top, left: position.left }}>
      <p className="eyebrow">GUÍA {step + 1} DE {tourSteps.length}</p>
      <h2 id="lab-tour-title">{current.title}</h2>
      <p><strong>Qué es:</strong> {current.what}</p>
      <p><strong>Para qué sirve:</strong> {current.why}</p>
      <p><strong>Cómo usarlo:</strong> {current.how}</p>
      <div className="lab-tour-progress" role="progressbar" aria-label={`Paso ${step + 1} de ${tourSteps.length}`} aria-valuemin={1} aria-valuemax={tourSteps.length} aria-valuenow={step + 1}><span style={{ width: `${(step + 1) / tourSteps.length * 100}%` }} /></div>
      <div className="lab-tour-actions"><button type="button" className="lab-button secondary" onClick={onClose}>Salir</button><button type="button" className="lab-button secondary" onClick={() => onStep(step - 1)} disabled={step === 0}>Anterior</button><button type="button" className="lab-button" onClick={() => step === tourSteps.length - 1 ? onClose() : onStep(step + 1)}>{step === tourSteps.length - 1 ? 'Finalizar' : 'Siguiente'}</button></div>
    </div>
  </div>
}

function getPosition(target: HTMLElement, dialog: HTMLElement | null): Position {
  const rect = target.getBoundingClientRect()
  const measured = dialog?.getBoundingClientRect()
  const cardWidth = measured?.width || Math.min(390, window.innerWidth - 32)
  const cardHeight = measured?.height || Math.min(420, window.innerHeight - 32)
  const gap = 18
  const spaces = [
    { placement: 'right' as const, top: rect.top, left: rect.right + gap, fits: rect.right + gap + cardWidth <= window.innerWidth - 16 },
    { placement: 'left' as const, top: rect.top, left: rect.left - gap - cardWidth, fits: rect.left - gap - cardWidth >= 16 },
    { placement: 'bottom' as const, top: rect.bottom + gap, left: rect.left, fits: rect.bottom + gap + cardHeight <= window.innerHeight - 16 },
    { placement: 'top' as const, top: rect.top - gap - cardHeight, left: rect.left, fits: rect.top - gap - cardHeight >= 16 },
  ]
  const chosen = spaces.find(space => space.fits) ?? spaces
    .map(space => ({ ...space, overlap: getOverlap(space, rect, cardWidth, cardHeight) }))
    .sort((first, second) => first.overlap - second.overlap)[0]
  return { top: Math.max(16, Math.min(chosen.top, window.innerHeight - cardHeight - 16)), left: Math.max(16, Math.min(chosen.left, window.innerWidth - cardWidth - 16)), placement: chosen.placement }
}

function getOverlap(space: { top: number; left: number }, target: DOMRect, width: number, height: number) {
  const horizontal = Math.max(0, Math.min(space.left + width, target.right) - Math.max(space.left, target.left))
  const vertical = Math.max(0, Math.min(space.top + height, target.bottom) - Math.max(space.top, target.top))
  return horizontal * vertical
}
