import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getStatesStatistics } from '../../services/electionData'
import { getTerritorialDemographics } from '../../services/territorialDemographics'
import { useTerritorialResource } from './useTerritorialResource'
import { formatCount, formatPercent, normalizeStateCode, ratio } from './territorialData'
import { municipalRanking, rankStatus, sortRanking, type RankRow, type RankingOrder } from './territorialRankingData'
import type { Municipality } from './municipalities'
import { Icon } from '../../components/Icon'

export function TerritorialRanking({ year, stateCode, stateName, items, loading, failed, selectedCode, onState, onMunicipality }: {
  year: number; stateCode: string; stateName?: string; items: Municipality[]; loading: boolean; failed: boolean; selectedCode: string;
  onState: (code: string) => void; onMunicipality: (code: string) => void
}) {
  const [order, setOrder] = useState<RankingOrder>('highest'), [page, setPage] = useState(0)
  const selectionToken = useRef('')
  const loader = useCallback(async (signal: AbortSignal) => {
    if (stateCode) return { kind: 'municipal' as const, records: (await getTerritorialDemographics(year, stateCode, signal)).data }
    return { kind: 'states' as const, records: await getStatesStatistics(year, signal) }
  }, [year, stateCode])
  const { active, retry } = useTerritorialResource(`${year}:${stateCode || 'national'}:ranking`, loader)
  const rows = useMemo((): RankRow[] => {
    if (active?.status !== 'ready') return []
    if (active.data.kind === 'municipal') return municipalRanking(active.data.records, items.map(item => ({ code: item.properties.inegiCode, name: item.properties.name, ineCode: item.properties.ineCode })))
    return active.data.records.map(state => ({ code: normalizeStateCode(state.state_code), geometry_code: normalizeStateCode(state.state_code), name: state.state_name,
      totals: { LN: state.LN, SV: state.SV, NV: state.NV, NS: state.NS, source_row_count: state.source_row_count },
      rate: ratio(state.SV, state.SV + state.NV), status: rankStatus(state), high_ns: (ratio(state.NS, state.LN) ?? 0) >= .1 }))
  }, [active, items])
  const ranked = useMemo(() => sortRanking(rows.filter(row => row.status === 'ranked'), order), [rows, order])
  const caution = rows.filter(row => row.status !== 'ranked').sort((a, b) => a.name.localeCompare(b.name, 'es') || a.code.localeCompare(b.code))
  useEffect(() => { setPage(0) }, [year, stateCode, order])
  useEffect(() => {
    const token = `${year}:${stateCode}:${selectedCode}`
    if (selectionToken.current === token) return
    const selectedIndex = ranked.findIndex(row => row.geometry_code === selectedCode)
    if (selectedIndex >= 0) { setPage(Math.floor(selectedIndex / 10)); selectionToken.current = token }
    else if (!selectedCode) selectionToken.current = token
  }, [year, stateCode, selectedCode, ranked])
  const pages = Math.max(1, Math.ceil(ranked.length / 10)), currentPage = Math.min(page, pages - 1)
  function choose(row: RankRow) { if (row.geometry_code) { if (stateCode) onMunicipality(row.geometry_code); else onState(row.geometry_code) } }
  return <section className="territorial-ranking" aria-labelledby="ranking-title">
    <header className="ranking-heading"><div><span className="territorial-kicker"><Icon name="dashboard" /> Comparar territorios · {year}</span><h3 id="ranking-title">{stateCode ? `Participación municipal · ${stateName}` : 'Las 32 entidades en perspectiva'}</h3></div><span className="ranking-count">{active?.status === 'ready' && (!stateCode || (!loading && !failed)) ? `${ranked.length} con soporte` : 'Preparando'}</span></header>
    <div className="ranking-order" role="group" aria-label="Orden del ranking"><button type="button" aria-pressed={order === 'highest'} onClick={() => setOrder('highest')}>↓ Mayor participación</button><button type="button" aria-pressed={order === 'lowest'} onClick={() => setOrder('lowest')}>↑ Menor participación</button></div>
    {(!active || (stateCode && loading)) ? <p className="ranking-status" role="status">Preparando ranking de {year}…</p> : (active.status === 'error' || (stateCode && failed)) ? <div className="ranking-status" role="alert"><p>No se pudo cargar el ranking. Si falta la cartografía, reintenta la carga del mapa.</p><button className="map-reset" onClick={retry}>Reintentar ranking</button></div> : <>
      <p className="ranking-description">Participaron / (participaron + no participaron), sobre los totales completos de {stateCode ? 'cada municipio' : 'cada entidad'} en {year}. Las barras no representan volumen de población.</p>
      {!ranked.length && <p className="ranking-status">No hay territorios que cumplan los criterios de comparación para esta selección.</p>}
      <ol className="ranking-list" start={currentPage * 10 + 1}>{ranked.slice(currentPage * 10, (currentPage + 1) * 10).map((row, index) => <li key={row.code}>
        <button type="button" className="ranking-row" data-rank-code={row.code} aria-pressed={stateCode ? row.geometry_code === selectedCode : false} onClick={() => choose(row)}>
          <span className="ranking-position">{currentPage * 10 + index + 1}</span><span className="ranking-place"><strong>{row.name}</strong><span className="ranking-track" aria-hidden="true"><i style={{ width: `${row.rate! * 100}%` }} /></span><small>INE {row.code} · Base: {formatCount(row.totals!.SV + row.totals!.NV)}{row.high_ns && <b className="quality-warning"> · No especificación ≥10 %</b>}</small></span><span className="ranking-rate">{formatPercent(row.rate)}</span>
        </button>
      </li>)}</ol>
      {ranked.length > 10 && <div className="ranking-pagination" aria-label="Páginas del ranking"><button type="button" disabled={currentPage === 0} onClick={() => setPage(value => Math.max(0, value - 1))}>Anterior</button><span role="status">{currentPage + 1} / {pages}</span><button type="button" disabled={currentPage === pages - 1} onClick={() => setPage(value => value + 1)}>Siguiente</button></div>}
      <p className="ranking-criteria">Comparación con lista nominal≥100, participación especificada≥100 y filas fuente≥5. Sólo correspondencias disponibles; no certifican límites históricos. Empates de tasa exacta: clave INE ascendente. No se ordenan tasas no definidas como cero.</p>
      {!!caution.length && <details className="ranking-cautions"><summary>Fuera de la comparación · {caution.length} territorios</summary><p>Se conservan y pueden consultarse geográficamente cuando hay geometría; no reciben una posición comparable.</p><ul>{caution.map(row => <li key={row.code}><button type="button" disabled={!row.geometry_code} onClick={() => choose(row)}><strong>{row.name}</strong><span>{row.status === 'unmapped' ? 'Correspondencia pendiente' : row.status === 'undefined' ? 'Participación no especificada: tasa no disponible' : row.status === 'low_support' ? `Soporte reducido · ${formatPercent(row.rate)} · Base: ${formatCount(row.totals ? row.totals.SV + row.totals.NV : null)}` : 'Sin información'}{row.high_ns ? ' · No especificación elevada' : ''}</span></button></li>)}</ul></details>}
    </>}
  </section>
}
