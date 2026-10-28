import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { resolve, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { electionYears, normalizeStateCode, aggregateSegments, isCoreSegment, sumCounts, sexLabels, validateTerritorialResponse, validateTerritorySummary } from '../src/features/map/territorialData.ts'

const root = fileURLToPath(new URL('../', import.meta.url))
const fields = ['LN', 'SV', 'NV', 'NS', 'source_row_count']
const hash = text => createHash('sha256').update(text).digest('hex')
export function buildTerritorialSummaries({ check = false } = {}) {
  const sources = {}, files = new Map(), coverage = []
  const read = relative => {
    const text = readFileSync(join(root, relative), 'utf8')
    sources[relative] = hash(text)
    return JSON.parse(text)
  }
  const same = (actual, expected, context) => { for (const field of fields) assert.equal(actual[field], expected[field], `${context}:${field}`) }
  const source = (year, file) => {
    const result = read(`data/processed/participamx_multiyear/elections/${year}/${file}.json`)
    assert.equal(result.schema_version, '2.0.0'); assert.equal(result.election_year, year); assert.equal(result.rate_unit, 'proportion')
    return result.data
  }
  for (const year of electionYears) {
    const national = source(year, 'national_statistics')[0], ages = source(year, 'age_statistics'), sexes = source(year, 'sex_statistics')
    const states = source(year, 'states')
    assert.equal(states.length, 32)
    for (const sex of sexes) assert.equal(sex.sex_label, sexLabels[sex.sex_code])
    same(sumCounts(ages), national, `${year}:age-total`)
    same(sumCounts(sexes), national, `${year}:sex-total`)
    const all = [], profiles = new Set()
    function summary(rows, totals, state, name, ids) {
      const grouped = aggregateSegments(rows)
      return validateTerritorySummary({ schema_version: 'territorial-summary-1', election_year: year,
        level: state ? 'state' : 'national', state_code: state, territory_name: name, totals: Object.fromEntries(fields.map(field => [field, totals[field]])),
        registered_sexes: sexes.map(row => row.sex_code), profile_ids: ids,
        segments: grouped.filter(isCoreSegment), complementary: grouped.filter(row => !isCoreSegment(row)),
      }, year, state)
    }
    for (const state of states) {
      const code = normalizeStateCode(state.state_code)
      const payload = validateTerritorialResponse(read(`public/data/territorial/${year}/${code}.json`), year, code)
      const rows = payload.data.flatMap(row => [...row.segments, ...row.complementary])
      same(sumCounts(rows), state, `${year}:${code}`)
      const result = summary(rows, state, code, state.state_name, state.profile_ids)
      files.set(`${year}/${code}.json`, JSON.stringify(result) + '\n')
      all.push(...rows); state.profile_ids.forEach(id => profiles.add(id))
    }
    const result = summary(all, national, null, 'México', [...profiles].sort())
    for (const cell of [...result.segments, ...result.complementary]) {
      const matching = ages.filter(row => row.sex_code === cell.sex_code && (cell.age_band === '101+' ? row.exact_age > 100 : row.exact_age >= Number(cell.age_band.split('-')[0]) && row.exact_age <= Number(cell.age_band.split('-')[1])))
      same(cell, sumCounts(matching), `${year}:${cell.age_band}:${cell.sex_code}:age-reference`)
    }
    for (const sex of sexes) same(sumCounts(all.filter(row => row.sex_code === sex.sex_code)), sex, `${year}:${sex.sex_code}:sex-reference`)
    files.set(`${year}/national.json`, JSON.stringify(result) + '\n')
    coverage.push({ election_year: year, states: states.length, registered_sexes: result.registered_sexes, age_rows: ages.length,
      total_LN: national.LN, represented_age_LN: sumCounts(all.filter(row => row.age_band !== '101+')).LN,
      complementary_LN: sumCounts(result.complementary).LN, reconciliation_difference: 0 })
  }
  const index = { schema_version: 'territorial-summary-1', sources, coverage,
    files: Object.fromEntries([...files].map(([name, text]) => [name, { sha256: hash(text), bytes: Buffer.byteLength(text) }])) }
  files.set('index.json', JSON.stringify(index) + '\n')
  for (const [name, text] of files) {
    const target = join(root, 'public/data/territorial/summaries', name)
    if (check) assert.equal(readFileSync(target, 'utf8'), text, `Resumen desactualizado: ${name}`)
    else {
      if (existsSync(target)) assert.equal(JSON.parse(readFileSync(target, 'utf8')).schema_version, 'territorial-summary-1')
      mkdirSync(join(target, '..'), { recursive: true }); writeFileSync(target, text)
    }
  }
  return { files: files.size, bytes: [...files.values()].reduce((sum, text) => sum + Buffer.byteLength(text), 0), coverage }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) console.log(JSON.stringify(buildTerritorialSummaries({ check: process.argv.includes('--check') }), null, 2))
