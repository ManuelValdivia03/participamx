export function parseViewBox(value: string): number[] {
  const coordinates = value.trim().split(/\s+/).map(Number)
  if (coordinates.length !== 4 || !coordinates.every(Number.isFinite) || coordinates[2] <= 0 || coordinates[3] <= 0) throw new Error('Vista SVG inválida')
  return coordinates
}

export function interpolateViewBox(from: string, to: string, progress: number): string {
  if (progress <= 0) return from
  if (progress >= 1) return to
  const a = parseViewBox(from), b = parseViewBox(to)
  const t = progress < .5 ? 4 * progress ** 3 : 1 - (-2 * progress + 2) ** 3 / 2
  const width = a[2] * (b[2] / a[2]) ** t, height = a[3] * (b[3] / a[3]) ** t
  const cx = a[0] + a[2] / 2 + (b[0] + b[2] / 2 - a[0] - a[2] / 2) * t
  const cy = a[1] + a[3] / 2 + (b[1] + b[3] / 2 - a[1] - a[3] / 2) * t
  return [cx - width / 2, cy - height / 2, width, height].join(' ')
}

export const MIN_VIEW_WIDTH = .25
export const MAX_VIEW_WIDTH = 1200

export function constrainViewBox(value: string): string {
  const [x, y, w, h] = parseViewBox(value)
  const width = Math.max(MIN_VIEW_WIDTH, Math.min(MAX_VIEW_WIDTH, w))
  const height = h * width / w
  const cx = Math.max(0, Math.min(800, x + w / 2)), cy = Math.max(0, Math.min(500, y + h / 2))
  const result = [cx - width / 2, cy - height / 2, width, height]
  return result.every((number, index) => Math.abs(number - [x, y, w, h][index]) < 1e-10) ? value : result.join(' ')
}

export function zoomViewBox(value: string, factor: number, anchor?: { x: number; y: number }): string {
  if (!Number.isFinite(factor) || factor <= 0) throw new Error('Factor de zoom inválido')
  const [x, y, w, h] = parseViewBox(value)
  const width = Math.max(MIN_VIEW_WIDTH, Math.min(MAX_VIEW_WIDTH, w / factor))
  const scale = width / w
  const point = anchor ?? { x: x + w / 2, y: y + h / 2 }
  return constrainViewBox([point.x - (point.x - x) * scale, point.y - (point.y - y) * scale, width, h * scale].join(' '))
}

export function panViewBox(value: string, dx: number, dy: number): string {
  const [x, y, width, height] = parseViewBox(value)
  return constrainViewBox([x + dx, y + dy, width, height].join(' '))
}
