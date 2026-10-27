import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { buildTerritorialData } from './build-territorial-data.mjs'
import { buildTerritorialSummaries } from './build-territorial-summaries.mjs'
import { parseViewBox, interpolateViewBox } from '../src/features/map/viewBoxMotion.ts'
import {
  normalizeStateCode, normalizeMunicipalityCode, normalizeIneCode,
  ratio, turnout, differencePoints, demographicCells, demographicBreakdown, aggregateSegments, sumCounts, validateTerritorialResponse, validateTerritorySummary,
} from '../src/features/map/territorialData.ts'

const read = path => JSON.parse(readFileSync(path, 'utf8'))
const file = (year, state) => read(`public/data/territorial/${year}/${state}.json`)

test('claves INE: ceros iniciales, sin truncar, sin claves ordinales o valores vacíos', () => {
  assert.equal(normalizeIneCode('1', '10'), '01010')
  assert.equal(normalizeIneCode('09', '003'), '09003')
  assert.equal(normalizeMunicipalityCode('001'), '001')
  for (const value of ['', '0', '33', '001', '-1', ' 1', 'A1', '1.0']) assert.throws(() => normalizeStateCode(value))
  for (const value of ['', '0', '1000', '01x', '-2', ' 10']) assert.throws(() => normalizeMunicipalityCode(value))
})

test('tasas, nulos, cero observado y diferencia en puntos porcentuales', () => {
  assert.equal(turnout({ SV: 30, NV: 70 }), .3)
  assert.equal(turnout({ SV: 0, NV: 100 }), 0)
  assert.equal(turnout({ SV: 0, NV: 0 }), null)
  assert.equal(ratio(null, 100), null)
  assert.equal(ratio(10, null), null)
  assert.equal(ratio(0, 0), null)
  assert.equal(ratio(Number.NaN, 100), null)
  assert.equal(differencePoints(.4, .6).toFixed(2), '-20.00')
  assert.equal(differencePoints(null, .6), null)
})

test('distribución parcial conserva ausencia, no incluye 101+ ni categoría sexo 2', () => {
  const cell = (band, sex, SV, NV) => ({ age_band: band, sex_code: sex, LN: SV + NV, SV, NV, NS: 0, source_row_count: 5, sufficient_support: SV + NV >= 100, high_ns: false, assignment_status: 'test' })
  const municipality = {
    ine_code: '01001', municipality_name: 'Prueba', profile_ids: [],
    segments: [cell('18-34', '0', 30, 70), cell('18-34', '1', 70, 30)],
    complementary: [cell('101+', '0', 100, 0), cell('18-34', '2', 20, 0)],
  }
  municipality.totals = sumCounts([...municipality.segments, ...municipality.complementary])
  const cells = demographicCells(municipality)
  assert.equal(cells.length, 6)
  assert.equal(cells[0].distribution, .3)
  assert.equal(cells[1].distribution, .7)
  assert.equal(cells[2].distribution, null)
  assert.equal(cells[2].participation, null)
  assert.equal(cells[2].segment, null)
  const response = { schema_version: 'territorial-explorer-1', election_year: 2024, state_code: '01', rate_unit: 'proportion', source: 'synthetic', warnings: [], data: [municipality] }
  assert.doesNotThrow(() => validateTerritorialResponse(response, 2024, '01'))
  municipality.segments[0].SV = 0
  municipality.segments[0].NV = 100
  assert.equal(demographicCells(municipality)[0].participation, 0)
  municipality.segments[1].SV = 0
  municipality.segments[1].NV = 100
  assert.ok(demographicCells(municipality).every(row => row.distribution === null))
})

test('contrato rechaza año, clave, conteos o soporte incoherentes y duplicados', () => {
  const original = file(2024, '01')
  assert.doesNotThrow(() => validateTerritorialResponse(original, 2024, '1'))
  const mutations = [
    data => { data.election_year = 2009 },
    data => { data.data[0].ine_code = '01000' },
    data => { data.data[0].totals.LN++ },
    data => { data.data[0].segments[0].SV = null },
    data => { data.data[0].segments[0].sufficient_support = false },
    data => { data.data[0].segments[0].high_ns = true },
    data => { data.data[0].segments.push(data.data[0].segments[0]) },
    data => { data.data.push(data.data[0]) },
    data => { data.data[0].complementary.push(data.data[0].segments.pop()) },
  ]
  for (const mutation of mutations) {
    const changed = structuredClone(original)
    mutation(changed)
    assert.throws(() => validateTerritorialResponse(changed, 2024, '01'))
  }
})

test('regresión: varios municipios 2024 y elección 2009 usan exclusivamente su fuente', () => {
  for (const [year, state, municipality] of [[2024, '01', '001'], [2024, '01', '010'], [2024, '09', '003'], [2024, '16', '112'], [2009, '11', '008']]) {
    const source = read(`data/processed/participamx_multiyear/elections/${year}/municipality_segments/${Number(state)}.json`)
    const expected = source.data.filter(row => normalizeIneCode(row.state_code, row.municipality_code) === state + municipality)
    const record = file(year, state).data.find(row => row.ine_code === state + municipality)
    assert.ok(record)
    assert.deepEqual(record.totals, sumCounts(expected))
    for (const row of [...record.segments, ...record.complementary]) {
      const original = expected.find(item => item.age_band === row.age_band && item.sex_code === row.sex_code)
      for (const key of Object.keys(row)) assert.equal(row[key], original[key])
    }
    assert.ok(Math.abs(demographicCells(record).reduce((sum, row) => sum + (row.distribution ?? 0), 0) - (record.segments.some(row => row.SV > 0) ? 1 : 0)) < 1e-12)
  }
  const unavailable = file(2024, '16').data.find(row => row.ine_code === '16112')
  assert.ok(demographicCells(unavailable).every(row => row.participation === null))
  assert.equal(file(2024, '01').data.find(row => row.ine_code === '01010').municipality_name, 'San Francisco de los Romo')
})

test('generación determinista: 192 archivos, manifiesto, hashes, totales y celdas conciliados', () => {
  const result = buildTerritorialData({ check: true })
  assert.equal(result.files, 193)
  assert.deepEqual(result.coverage.map(row => row.municipalities), [2458, 2455, 2458, 2463, 2468, 2477])
  assert.deepEqual(result.coverage.map(row => row.undefined_core_rates), [42, 6, 180, 78, 60, 72])
  assert.ok(result.coverage.every(row => row.missing_core_cells === 0))
})

test('los servicios estatales y nacionales existentes concilian con la nueva ficha municipal', () => {
  for (const year of [2009, 2012, 2015, 2018, 2021, 2024]) {
    const states = read(`public/data/participamx_multiyear/elections/${year}/states.json`).data
    const national = read(`public/data/participamx_multiyear/elections/${year}/national_statistics.json`).data[0]
    const municipalTotals = []
    let sexTwoLN = 0
    for (const state of states) {
      const response = file(year, normalizeStateCode(state.state_code))
      const total = sumCounts(response.data.map(row => row.totals))
      for (const field of ['LN', 'SV', 'NV', 'NS', 'source_row_count']) assert.equal(total[field], state[field])
      sexTwoLN += response.data.flatMap(row => row.complementary).filter(row => row.sex_code === '2').reduce((sum, row) => sum + row.LN, 0)
      municipalTotals.push(total)
    }
    const total = sumCounts(municipalTotals)
    for (const field of ['LN', 'SV', 'NV', 'NS', 'source_row_count']) assert.equal(total[field], national[field])
    assert.equal(sexTwoLN, year === 2024 ? 105 : 0)
  }
})

test('resúmenes de México y 32 entidades: conciliación independiente de edad y sexo, seis elecciones', () => {
  const result = buildTerritorialSummaries({ check: true })
  assert.equal(result.files, 199)
  for (const year of [2009, 2012, 2015, 2018, 2021, 2024]) {
    const national = read(`public/data/territorial/summaries/${year}/national.json`)
    validateTerritorySummary(national, year, null)
    assert.deepEqual(national.registered_sexes, year === 2024 ? ['0', '1', '2'] : ['0', '1'])
    const sexReference = read(`data/processed/participamx_multiyear/elections/${year}/sex_statistics.json`).data
    const sex = demographicBreakdown(national, 'sex')
    assert.deepEqual(sex.included, national.totals)
    assert.equal(sex.rows.length, sexReference.length)
    for (const row of sex.rows) {
      const original = sexReference.find(item => item.sex_code === row.sex_code)
      for (const field of ['LN', 'SV', 'NV', 'NS', 'source_row_count']) assert.equal(row.counts[field], original[field])
      assert.equal(row.participation, original.participation_observed)
      assert.equal(row.label, original.sex_label)
    }
    for (const axis of ['crossed', 'age', 'sex']) {
      const { rows, included } = demographicBreakdown(national, axis)
      assert.deepEqual(sumCounts(rows.filter(row => row.counts).map(row => row.counts)), included)
      assert.ok(Math.abs(rows.reduce((sum, row) => sum + (row.distribution ?? 0), 0) - 1) < 1e-12)
    }
    const stateTotals = []
    for (let state = 1; state <= 32; state++) {
      const code = normalizeStateCode(state)
      const summary = read(`public/data/territorial/summaries/${year}/${code}.json`)
      validateTerritorySummary(summary, year, code)
      const expected = aggregateSegments(file(year, code).data.flatMap(row => [...row.segments, ...row.complementary]))
      assert.deepEqual([...summary.segments, ...summary.complementary].sort((a, b) => a.age_band.localeCompare(b.age_band) || a.sex_code.localeCompare(b.sex_code)), expected)
      stateTotals.push(summary.totals)
    }
    assert.deepEqual(sumCounts(stateTotals), national.totals)
  }
})

test('sumar conteos antes de dividir: tasa agregada distinta de media municipal y ausencia sin cero', () => {
  const first = file(2024, '01').data[0].segments[0]
  const rows = [
    { ...first, LN: 100, SV: 90, NV: 10, NS: 0, source_row_count: 5 },
    { ...first, LN: 1000, SV: 100, NV: 900, NS: 0, source_row_count: 5 },
  ]
  const summary = { segments: aggregateSegments(rows), complementary: [], totals: sumCounts(rows) }
  assert.equal(demographicBreakdown(summary, 'sex').rows[0].participation, 190 / 1100)
  assert.notEqual(demographicBreakdown(summary, 'sex').rows[0].participation, (.9 + .1) / 2)
  assert.equal(demographicBreakdown(summary, 'sex').rows[1].counts, null)
  assert.equal(demographicBreakdown(summary, 'sex').rows[1].participation, null)
})

test('interpolación de vista: extremos exactos, dimensiones positivas, continuidad y reinicio desde vista alcanzada', () => {
  const from = '0 0 1000 600', to = '500 200 10 6'
  assert.equal(interpolateViewBox(from, to, 0), from)
  assert.equal(interpolateViewBox(from, to, 1), to)
  let previousWidth = 1001
  for (let n = 0; n <= 100; n++) {
    const rectangle = parseViewBox(interpolateViewBox(from, to, n / 100))
    assert.ok(rectangle[2] > 0 && rectangle[2] < previousWidth)
    previousWidth = rectangle[2]
  }
  const interrupted = interpolateViewBox(from, to, .4)
  assert.equal(interpolateViewBox(interrupted, from, 0), interrupted)
  for (const invalid of ['0 0 0 1', 'NaN 0 1 1', '0 0 1']) assert.throws(() => parseViewBox(invalid))
})
