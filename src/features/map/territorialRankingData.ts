import { ratio, type Counts, type MunicipalityDemographics } from './territorialData'

export type RankRow = {
  code: string; geometry_code: string | null; name: string; totals: Counts | null; rate: number | null;
  status: 'ranked' | 'low_support' | 'undefined' | 'unmapped' | 'missing'; high_ns: boolean
}
export type RankingOrder = 'highest' | 'lowest'

export function rankStatus(totals: Counts | null, mapped = true): RankRow['status'] {
  if (!mapped) return 'unmapped'
  if (!totals) return 'missing'
  if (totals.SV + totals.NV === 0) return 'undefined'
  return totals.LN >= 100 && totals.SV + totals.NV >= 100 && totals.source_row_count >= 5 ? 'ranked' : 'low_support'
}

export function sortRanking(rows: RankRow[], order: RankingOrder): RankRow[] {
  return rows.filter(row => row.status === 'ranked' && row.rate !== null && row.totals !== null).sort((a, b) => {
    if (a.rate === null || b.rate === null || !a.totals || !b.totals) return a.code.localeCompare(b.code)
    // Comparación exacta de fracciones: no ordena por porcentajes redondeados.
    const delta = BigInt(a.totals.SV) * BigInt(b.totals.SV + b.totals.NV) - BigInt(b.totals.SV) * BigInt(a.totals.SV + a.totals.NV)
    return delta === 0n ? a.code.localeCompare(b.code) : (delta < 0n ? -1 : 1) * (order === 'highest' ? -1 : 1)
  })
}

export function municipalRanking(records: MunicipalityDemographics[], geometries: { code: string; name: string; ineCode: string | null }[]): RankRow[] {
  const mapped = new Map(geometries.filter(row => row.ineCode).map(row => [row.ineCode!, row]))
  const available = new Set(records.map(record => record.ine_code))
  return [
    ...records.map(record => ({ code: record.ine_code, geometry_code: mapped.get(record.ine_code)?.code ?? null,
      name: record.municipality_name, totals: record.totals,
      rate: ratio(record.totals.SV, record.totals.SV + record.totals.NV),
      status: rankStatus(record.totals, mapped.has(record.ine_code)), high_ns: (ratio(record.totals.NS, record.totals.LN) ?? 0) >= .1 })),
    ...geometries.filter(row => !row.ineCode || !available.has(row.ineCode)).map(row => ({ code: row.ineCode ?? `pending:${row.code}`, geometry_code: row.code, name: row.name, totals: null, rate: null, status: row.ineCode ? 'missing' as const : 'unmapped' as const, high_ns: false })),
  ]
}
