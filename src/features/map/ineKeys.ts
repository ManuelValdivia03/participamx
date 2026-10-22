export const electoralYears = ['2009', '2012', '2015', '2018', '2021', '2024'] as const
export type ElectoralYear = typeof electoralYears[number]
export type Correspondence = { ineCode: string; ineName: string; method: 'unique-normalized-name' }
export type Crosswalk = { stateCode: string; years: Record<ElectoralYear, Record<string, Correspondence>> }

export function electoralJoinKey(properties: { ineCode: string | null; year: ElectoralYear }) {
  return properties.ineCode ? `${properties.year}:${properties.ineCode}` : null
}

export function resolveIneKey(inegiCode: string, year: ElectoralYear, crosswalk: Crosswalk) {
  const entry = crosswalk.years[year]?.[inegiCode]
  if (entry && (!/^\d{5}$/.test(entry.ineCode) || entry.ineCode.slice(0, 2) !== crosswalk.stateCode || entry.method !== 'unique-normalized-name')) throw new Error('Equivalencia INE inválida.')
  return {
    code: entry?.ineCode ?? null,
    ineCode: entry?.ineCode ?? null,
    ineName: entry?.ineName ?? null,
    inegiCode,
    year,
    correspondence: entry ? 'name-match' as const : 'pending' as const,
  }
}
