import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import type { MapCamera } from './useAnimatedViewBox'
import { panViewBox, parseViewBox, zoomViewBox } from './viewBoxMotion'

type Point = { x: number; y: number }
type Gesture = { view: string; first: Point; scale: number; distance: number; anchor: Point }
const midpoint = (a: Point, b: Point) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 })
const distance = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y)

export function useMapGestures(camera: MapCamera) {
  const points = useRef(new Map<number, Point>()), gesture = useRef<Gesture | null>(null)
  const blockedUntil = useRef(0), moved = useRef(false), wheelActive = useRef(false), lastTap = useRef<{ time: number; point: Point } | null>(null)
  const [active, setActive] = useState(false), [dragging, setDragging] = useState(false)
  const { svgRef, stop, getView, setCamera, zoom } = camera
  function world(point: Point): Point {
    const matrix = svgRef.current?.getScreenCTM()?.inverse()
    return matrix ? new DOMPoint(point.x, point.y).matrixTransform(matrix) : { x: 400, y: 250 }
  }
  function begin() {
    const values = [...points.current.values()]
    const first = values.length > 1 ? midpoint(values[0], values[1]) : values[0]
    const matrix = svgRef.current?.getScreenCTM()?.inverse()
    gesture.current = first ? { view: getView(), first, scale: matrix?.a ?? 1,
      distance: values.length > 1 ? distance(values[0], values[1]) : 0, anchor: world(first) } : null
  }
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    let timer = 0
    const wheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey && !wheelActive.current) return
      event.preventDefault()
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? svg.clientHeight : 1)
      const matrix = svg.getScreenCTM()?.inverse()
      const anchor = matrix ? new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix) : undefined
      zoom(Math.exp(-Math.max(-200, Math.min(200, delta)) * .003), anchor, false)
      clearTimeout(timer)
      timer = window.setTimeout(() => setCamera(getView(), true), 100)
    }
    svg.addEventListener('wheel', wheel, { passive: false })
    return () => { svg.removeEventListener('wheel', wheel); clearTimeout(timer) }
  }, [svgRef, zoom, setCamera, getView])
  useEffect(() => {
    const releaseOutside = (event: PointerEvent) => {
      if (!points.current.has(event.pointerId)) return
      points.current.delete(event.pointerId)
      if (!points.current.size) { gesture.current = null; setDragging(false); blockedUntil.current = performance.now() + 350; setCamera(getView(), true) }
    }
    window.addEventListener('pointerup', releaseOutside)
    window.addEventListener('pointercancel', releaseOutside)
    return () => { window.removeEventListener('pointerup', releaseOutside); window.removeEventListener('pointercancel', releaseOutside) }
  }, [getView, setCamera])

  function onPointerDown(event: ReactPointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return
    stop()
    wheelActive.current = true; setActive(true)
    event.currentTarget.focus({ preventScroll: true })
    points.current.set(event.pointerId, { x: event.clientX, y: event.clientY })
    moved.current = points.current.size > 1
    if (points.current.size > 1) {
      blockedUntil.current = performance.now() + 600
      for (const id of points.current.keys()) event.currentTarget.setPointerCapture(id)
    }
    begin()
  }
  function onPointerMove(event: ReactPointerEvent<SVGSVGElement>) {
    if (!points.current.has(event.pointerId) || !gesture.current) return
    points.current.set(event.pointerId, { x: event.clientX, y: event.clientY })
    const values = [...points.current.values()], base = gesture.current
    if (values.length > 1 && base.distance > 0) {
      event.preventDefault(); moved.current = true; setDragging(true)
      const center = midpoint(values[0], values[1])
      const next = zoomViewBox(base.view, Math.max(.01, distance(values[0], values[1]) / base.distance), base.anchor)
      const scale = base.scale * parseViewBox(next)[2] / parseViewBox(base.view)[2]
      setCamera(panViewBox(next, -(center.x - base.first.x) * scale, -(center.y - base.first.y) * scale))
    } else if (values.length === 1) {
      const dx = values[0].x - base.first.x, dy = values[0].y - base.first.y
      if (Math.hypot(dx, dy) <= 5 && !moved.current) return
      event.preventDefault(); moved.current = true; setDragging(true)
      if (!event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.setPointerCapture(event.pointerId)
      setCamera(panViewBox(base.view, -dx * base.scale, -dy * base.scale))
    }
    if (moved.current) blockedUntil.current = performance.now() + 500
  }
  function finish(event: ReactPointerEvent<SVGSVGElement>, cancelled = false) {
    if (!points.current.has(event.pointerId)) return
    const point = { x: event.clientX, y: event.clientY }
    const wasMoved = moved.current
    points.current.delete(event.pointerId)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    if (wasMoved || cancelled) blockedUntil.current = performance.now() + 350
    if (!wasMoved && !cancelled && event.pointerType === 'touch') {
      const previous = lastTap.current
      if (previous && performance.now() - previous.time < 320 && distance(previous.point, point) < 24) {
        zoom(2, world(point)); blockedUntil.current = performance.now() + 350; lastTap.current = null
      } else lastTap.current = { time: performance.now(), point }
    }
    if (points.current.size) { begin(); moved.current = true }
    else { gesture.current = null; setDragging(false); setCamera(getView(), true) }
  }
  function deactivate() { wheelActive.current = false; setActive(false) }
  return { active, dragging, shouldSuppressClick: () => performance.now() < blockedUntil.current,
    onPointerDown, onPointerMove, onPointerUp: (event: ReactPointerEvent<SVGSVGElement>) => finish(event),
    onPointerCancel: (event: ReactPointerEvent<SVGSVGElement>) => finish(event, true),
    onPointerLeave: () => { if (!points.current.size) deactivate() }, deactivate,
    onDoubleClick: (event: React.MouseEvent<SVGSVGElement>) => { event.preventDefault(); if (performance.now() >= blockedUntil.current) zoom(2, world({ x: event.clientX, y: event.clientY })) } }
}
