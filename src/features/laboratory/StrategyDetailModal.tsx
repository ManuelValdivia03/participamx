import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { downloadStrategyPdf, downloadStrategyPng } from './export'
import { getStrategyDetail, proposalNotice } from './strategyDetails'
import type { Strategy } from './types'

export function StrategyDetails({ strategy, onClose }: { strategy: Strategy; onClose: () => void }) {
  const detail = useMemo(() => getStrategyDetail(strategy), [strategy])
  const dialog = useRef<HTMLDivElement>(null)
  const [exporting, setExporting] = useState<'pdf' | 'png' | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    // Impide interacción de teclado y lector de pantalla con el contenido de fondo.
    const siblings = Array.from(document.body.children).filter((node): node is HTMLElement => node instanceof HTMLElement && !node.contains(dialog.current))
    const previousInert = siblings.map(node => node.inert)
    siblings.forEach(node => { node.inert = true })
    document.body.style.overflow = 'hidden'
    dialog.current?.focus()
    function keydown(event: KeyboardEvent) {
      if (event.key === 'Escape') { event.preventDefault(); onClose() }
      if (event.key !== 'Tab') return
      const elements = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not([disabled]), summary, a[href], [tabindex="0"]') ?? []).filter(element => !element.closest('details:not([open])') || element.tagName === 'SUMMARY')
      const first = elements[0], last = elements[elements.length - 1]
      if (!first) { event.preventDefault(); dialog.current?.focus(); return }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', keydown)
    return () => {
      document.removeEventListener('keydown', keydown)
      document.body.style.overflow = previousOverflow
      siblings.forEach((node, index) => { node.inert = previousInert[index] })
      previousFocus?.focus()
    }
  }, [onClose])

  async function download(format: 'pdf' | 'png') {
    setError(''); setExporting(format)
    try { if (format === 'pdf') downloadStrategyPdf(strategy); else await downloadStrategyPng(strategy) }
    catch (error) { setError(error instanceof Error ? error.message : 'No se pudo generar el documento.') }
    finally { setExporting(null) }
  }

  return createPortal(<div className="lab-details-backdrop" onClick={event => { if (event.target === event.currentTarget) onClose() }}>
    <div className="lab-details" role="dialog" aria-modal="true" aria-labelledby="lab-detail-title" aria-describedby="lab-detail-notice" tabIndex={-1} ref={dialog}>
      <header className="lab-details-header"><div><p className="eyebrow">PARTICIPAMX · PROPUESTA INSTITUCIONAL</p><h2 id="lab-detail-title">{strategy.name}</h2></div><button type="button" className="lab-button secondary" onClick={onClose} aria-label="Cerrar detalles de estrategia">Cerrar</button></header>
      <div className="lab-details-body">
        <p id="lab-detail-notice" className="lab-detail-notice">{proposalNotice}</p>
        <details className="lab-detail-index"><summary>Ir a una sección · {detail.sections.length} apartados</summary><nav aria-label="Secciones de la estrategia" className="lab-details-nav">{detail.sections.map(section => <a key={section.id} href={`#strategy-detail-${section.id}`} onClick={event => { event.preventDefault(); const target = document.getElementById(`strategy-detail-${section.id}`); target?.scrollIntoView?.({ block: 'start', behavior: 'auto' }); target?.focus() }}>{section.title}</a>)}</nav></details>
        {detail.sections.map((section, index) => <section className="lab-detail-section" key={section.id} aria-labelledby={`strategy-detail-${section.id}`}><h3 id={`strategy-detail-${section.id}`} tabIndex={-1}><span aria-hidden="true">{String(index + 1).padStart(2, '0')} · </span>{section.title}</h3>{section.id === 'statistics' ? <dl className="lab-detail-statistics">{detail.statistics.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl> : section.id === 'activities' ? <ol>{section.paragraphs.map(value => <li key={value}>{value}</li>)}</ol> : section.paragraphs.map(value => <p key={value}>{value}</p>)}</section>)}
      </div>
      <footer className="lab-details-footer"><div className="lab-export-actions"><button className="lab-button secondary lab-export-button" type="button" disabled={exporting !== null} onClick={() => download('pdf')}>{exporting === 'pdf' ? 'Generando PDF…' : 'Descargar PDF'}</button><button className="lab-button secondary lab-export-button" type="button" disabled={exporting !== null} onClick={() => download('png')}>{exporting === 'png' ? 'Generando PNG…' : 'Descargar PNG'}</button></div><small>Contenido completo. Los documentos muy extensos se dividen en imágenes numeradas.</small>{error && <p role="alert" className="lab-alert">{error}</p>}</footer>
    </div>
  </div>, document.body)
}
