import { useCallback, useEffect, useRef, useState } from 'react'
import { constrainViewBox, interpolateViewBox, parseViewBox, zoomViewBox, MAX_VIEW_WIDTH, MIN_VIEW_WIDTH } from './viewBoxMotion'

export function useAnimatedViewBox(target: string) {
  const [view, setView] = useState(target)
  const svgRef = useRef<SVGSVGElement>(null), current = useRef(target), frame = useRef(0)
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReduced(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  const stop = useCallback(() => { cancelAnimationFrame(frame.current) }, [])
  const getView = useCallback(() => current.current, [])
  const setCamera = useCallback((next: string, commit = false) => {
    current.current = constrainViewBox(next)
    svgRef.current?.setAttribute('viewBox', current.current)
    if (commit) setView(current.current)
  }, [])
  const animateTo = useCallback((next: string) => {
    stop()
    const to = constrainViewBox(next), from = current.current
    if (reduced || to === from) { setCamera(to, true); return }
    const start = performance.now()
    function animate(now: number) {
      const progress = Math.min(1, (now - start) / 480)
      setCamera(interpolateViewBox(from, to, progress), progress === 1)
      if (progress < 1) frame.current = requestAnimationFrame(animate)
    }
    frame.current = requestAnimationFrame(animate)
  }, [stop, setCamera, reduced])
  const zoom = useCallback((factor: number, anchor?: { x: number; y: number }, smooth = true) => {
    const next = zoomViewBox(current.current, factor, anchor)
    if (smooth) animateTo(next)
    else { stop(); setCamera(next) }
  }, [animateTo, stop, setCamera])
  useEffect(() => { animateTo(target); return stop }, [target, reduced, animateTo, stop])
  const width = parseViewBox(view)[2]
  return { view, reduced, svgRef, stop, getView, setCamera, animateTo, zoom,
    canZoomIn: width > MIN_VIEW_WIDTH + 1e-9, canZoomOut: width < MAX_VIEW_WIDTH - 1e-9 }
}

export type MapCamera = ReturnType<typeof useAnimatedViewBox>
