export type ScaleClass = { lower: number; upper: number; lowerClosed: boolean; count: number; colorLevel: number }
export type ThematicScale = {
  classes: ScaleClass[]
  breaks: number[]
  count: number
  distinctCount: number
}

// Cuantiles de la distribución empírica inversa; los empates nunca se dividen.
// Con ≤5 valores distintos se conserva una clase por valor, sin clases vacías.
export function createThematicScale(input: readonly (number | null)[]): ThematicScale {
  const values = input.filter((value): value is number => value !== null && Number.isFinite(value)).sort((a, b) => a - b)
  if (values.some(value => value < 0 || value > 1)) throw new Error('Proporción de capa fuera de [0,1]')
  const distinct = [...new Set(values)]
  const breaks = distinct.length <= 5 ? distinct.slice(0, -1)
    : [...new Set([1, 2, 3, 4].map(i => values[Math.ceil(i * values.length / 5) - 1]))].filter(value => value < values.at(-1)!)
  const ends = values.length ? [...breaks, values.at(-1)!] : []
  const classes = ends.map((upper, index): ScaleClass => ({
    lower: index ? ends[index - 1] : values[0], upper, lowerClosed: index === 0,
    count: values.filter(value => (index ? value > ends[index - 1] : true) && value <= upper).length,
    colorLevel: ends.length === 1 ? 2 : Math.round(index * 4 / (ends.length - 1)),
  }))
  return { classes, breaks, count: values.length, distinctCount: distinct.length }
}

export function scaleClassIndex(value: number | null, scale: ThematicScale): number | null {
  if (value === null || !Number.isFinite(value)) return null
  const index = scale.classes.findIndex(item => (item.lowerClosed ? value >= item.lower : value > item.lower) && value <= item.upper)
  return index < 0 ? null : index
}

export function formatScaleInterval(item: ScaleClass, precision = 20): string {
  const format = (value: number) => (value * 100).toLocaleString('es-MX', { maximumFractionDigits: precision })
  if (item.lower === item.upper) return `${format(item.upper)} %`
  return `${item.lowerClosed ? '' : '>'}${format(item.lower)}–${format(item.upper)} %`
}
