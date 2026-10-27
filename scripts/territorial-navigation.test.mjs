import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { buildTerritorySearch } from './build-territory-search.mjs'
import { validateSearchIndex, searchTerritories } from '../src/features/map/territorySearchData.ts'
import { constrainViewBox, zoomViewBox, panViewBox, parseViewBox, MAX_VIEW_WIDTH, MIN_VIEW_WIDTH } from '../src/features/map/viewBoxMotion.ts'

// Ejecuta el módulo TS de producción en memoria, resolviendo su importación local para Node.
const source = readFileSync('src/features/map/territorialRankingData.ts', 'utf8').replace("from './territorialData'", `from '${new URL('../src/features/map/territorialData.ts', import.meta.url).href}'`)
const { municipalRanking, sortRanking, rankStatus } = await import('data:text/javascript;base64,' + Buffer.from(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText).toString('base64'))
const read = path => JSON.parse(readFileSync(path, 'utf8'))

test('índice nacional compacto: 32 entidades, 2478 geometrías, seis correspondencias y ninguna geometría', () => {
  const metadata = buildTerritorySearch({ check: true })
  assert.equal(metadata.states, 32); assert.equal(metadata.municipalities, 2478)
  assert.ok(metadata.bytes < 400000)
  const index = validateSearchIndex(read('public/data/territorial/search-index.json'))
  assert.ok(!JSON.stringify(index).includes('coordinates'))
  for (const place of index.municipalities) {
    const crosswalk = read(`public/data/ine-crosswalk/${place.state_code}.json`)
    index.years.forEach((year, i) => assert.equal(place.ine_codes[i], crosswalk.years[year][place.code]?.ineCode ?? null))
  }
})

test('autocompletado: acentos, mayúsculas, duplicados, claves INE/INEGI y ausencia por elección', () => {
  const index = read('public/data/territorial/search-index.json')
  assert.equal(searchTerritories(index, ' ChIh ', 2024)[0].state_code, '08')
  const xalapa = searchTerritories(index, 'XÁLAPA', 2024)[0]
  assert.equal(xalapa.kind, 'municipality'); assert.equal(xalapa.state_code, '30')
  const duplicates = searchTerritories(index, 'San Pedro', 2024, 100)
  assert.ok(new Set(duplicates.map(place => place.state_code)).size > 1)
  const codes = searchTerritories(index, '01010', 2024)
  assert.ok(codes.some(place => place.name === 'El Llano' && place.code === '01010' && place.ine_codes[5] === '01011'))
  assert.ok(codes.some(place => place.name === 'San Francisco de los Romo' && place.code === '01011' && place.ine_codes[5] === '01010'))
  const pending = searchTerritories(index, 'Villa de Pozos', 2009)[0]
  assert.equal(pending.ine_codes[0], null)
  assert.deepEqual(searchTerritories(index, '   ', 2024), [])
  assert.deepEqual(searchTerritories(index, 'zzzzzzzzzz', 2024), [])
})

test('rankings de seis elecciones: totales completos, cobertura y orden exacto en los 32 estados', () => {
  let count = 0
  for (const year of [2009, 2012, 2015, 2018, 2021, 2024]) for (let state = 1; state <= 32; state++) {
    const code = String(state).padStart(2, '0')
    const records = read(`public/data/territorial/${year}/${code}.json`).data
    const features = read(`public/data/municipalities/${code}.json`).features
    const crosswalk = read(`public/data/ine-crosswalk/${code}.json`)
    const geometries = features.map(feature => ({ code: feature.properties.code, name: feature.properties.name, ineCode: crosswalk.years[year][feature.properties.code]?.ineCode ?? null }))
    const rows = municipalRanking(records, geometries)
    assert.equal(rows.length, records.length + geometries.filter(row => !row.ineCode).length)
    for (const row of rows.filter(row => row.totals)) {
      const original = records.find(record => record.ine_code === row.code)
      assert.deepEqual(row.totals, original.totals)
      assert.equal(row.rate, original.totals.SV + original.totals.NV > 0 ? original.totals.SV / (original.totals.SV + original.totals.NV) : null)
      assert.equal(row.status, rankStatus(original.totals, !!row.geometry_code))
    }
    for (const order of ['highest', 'lowest']) {
      const ranked = sortRanking(rows, order)
      assert.ok(ranked.every(row => row.rate !== null && row.status === 'ranked'))
      for (let i = 1; i < ranked.length; i++) assert.ok(order === 'highest' ? ranked[i - 1].rate >= ranked[i].rate : ranked[i - 1].rate <= ranked[i].rate)
    }
    count += records.length
  }
  assert.equal(count, 14779)
})

test('nulos, soporte pequeño, casos sin correspondencia y empates no se presentan como tasas comparables', () => {
  const base = read('public/data/territorial/2024/01.json').data[0]
  const make = (code, SV, NV, NS = 0, source_row_count = 5) => ({ ...base, ine_code: code, totals: { LN: SV + NV + NS, SV, NV, NS, source_row_count } })
  const records = [make('01001', 50, 50), make('01002', 100, 100), make('01003', 0, 0, 200), make('01004', 1, 0), make('01005', 100, 100, 0, 4), make('01006', 0, 100)]
  const geometries = records.map(record => ({ code: record.ine_code, ineCode: record.ine_code, name: record.municipality_name })).concat([{ code: '01099', ineCode: null, name: 'Pendiente' }, { code: '01098', ineCode: '01098', name: 'Sin datos' }])
  const rows = municipalRanking(records, geometries)
  assert.deepEqual(sortRanking(rows, 'highest').map(row => row.code), ['01001', '01002', '01006'])
  assert.equal(sortRanking(rows, 'lowest')[0].code, '01006', 'Un cero observado con denominador válido sí puede ordenarse')
  assert.equal(rows.find(row => row.code === '01003').status, 'undefined')
  assert.equal(rows.find(row => row.code === '01004').status, 'low_support')
  assert.equal(rows.find(row => row.code === '01005').status, 'low_support')
  assert.equal(rows.find(row => row.code === 'pending:01099').rate, null)
  assert.equal(rows.find(row => row.code === '01098').status, 'missing')
})

test('cámara: zoom anclado, pellizco, límites, desplazamiento y recuperación', () => {
  const initial = '0 0 800 500'
  assert.deepEqual(parseViewBox(zoomViewBox(initial, 2)), [200, 125, 400, 250])
  assert.deepEqual(parseViewBox(zoomViewBox(initial, 2, { x: 0, y: 0 })), [0, 0, 400, 250])
  assert.equal(parseViewBox(zoomViewBox(initial, 1e10))[2], MIN_VIEW_WIDTH)
  assert.equal(parseViewBox(zoomViewBox(initial, 1e-10))[2], MAX_VIEW_WIDTH)
  const moved = parseViewBox(panViewBox(initial, 1e9, -1e9))
  assert.equal(moved[0] + moved[2] / 2, 800)
  assert.equal(moved[1] + moved[3] / 2, 0)
  assert.equal(constrainViewBox(initial), initial)
  assert.throws(() => zoomViewBox(initial, 0))
  assert.throws(() => panViewBox(initial, NaN, 0))
})
