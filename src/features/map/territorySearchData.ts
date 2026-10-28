export type SearchPlace = { kind: 'state' | 'municipality'; code: string; state_code: string; name: string; ine_codes: (string | null)[] }
export type SearchIndex = { schema_version: 'territory-search-1'; years: number[]; states: SearchPlace[]; municipalities: SearchPlace[] }

export function normalizeSearch(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').trim().replace(/\s+/g, ' ')
}

export function searchTerritories(index: SearchIndex, query: string, year: number, limit = 10): SearchPlace[] {
  const needle = normalizeSearch(query)
  if (!needle) return []
  const tokens = needle.split(' ')
  const stateNames = new Map(index.states.map(state => [state.code, state.name]))
  const yearIndex = index.years.indexOf(year)
  return [...index.states, ...index.municipalities].map(place => {
    const name = normalizeSearch(place.name)
    const text = `${name} ${normalizeSearch(stateNames.get(place.state_code) ?? '')} ${place.code} ${place.ine_codes[yearIndex] ?? ''}`
    const exact = name === needle || place.code === needle || place.ine_codes[yearIndex] === needle
    const score = exact ? (place.kind === 'state' ? 0 : 1) : name.startsWith(needle) ? (place.kind === 'state' ? 2 : 3) : 4
    return { place, score, matches: tokens.every(token => text.includes(token)) }
  }).filter(result => result.matches).sort((a, b) => a.score - b.score || a.place.name.localeCompare(b.place.name, 'es') || a.place.code.localeCompare(b.place.code)).slice(0, limit).map(result => result.place)
}

export function validateSearchIndex(value: unknown): SearchIndex {
  const data = value as SearchIndex
  if (!data || data.schema_version !== 'territory-search-1' || !Array.isArray(data.years) || data.years.join(',') !== '2009,2012,2015,2018,2021,2024' || !Array.isArray(data.states) || data.states.length !== 32 || !Array.isArray(data.municipalities)) throw new Error('Índice territorial inválido')
  const keys = new Set<string>()
  for (const place of [...data.states, ...data.municipalities]) {
    const key = `${place.kind}:${place.code}`
    if (!['state', 'municipality'].includes(place.kind) || !/^(0[1-9]|[12]\d|3[0-2])$/.test(place.state_code) ||
      !(place.kind === 'state' ? /^\d{2}$/ : /^\d{5}$/).test(place.code) || !place.code.startsWith(place.state_code) ||
      typeof place.name !== 'string' || !place.name || keys.has(key) || !Array.isArray(place.ine_codes) || place.ine_codes.length !== data.years.length ||
      place.ine_codes.some(code => code !== null && (!(place.kind === 'state' ? /^\d{2}$/ : /^\d{5}$/).test(code) || !code.startsWith(place.state_code)))) throw new Error('Entrada territorial inválida')
    keys.add(key)
  }
  return data
}
