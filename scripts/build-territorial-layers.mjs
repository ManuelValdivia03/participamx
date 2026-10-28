import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { resolve, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { electionYears, sexLabels, sumCounts, validateTerritorySummary } from '../src/features/map/territorialData.ts'

const root = fileURLToPath(new URL('../', import.meta.url))
const hash = text => createHash('sha256').update(text).digest('hex')
const fields = ['LN', 'SV', 'NV', 'NS', 'source_row_count']

// Empaqueta resúmenes ya conciliados: una consulta pequeña por elección, sin geometrías.
export function buildTerritorialLayers({ check = false } = {}) {
  const sources = {}, files = new Map(), coverage = []
  const read = relative => {
    const text = readFileSync(join(root, relative), 'utf8')
    sources[relative] = hash(text)
    return JSON.parse(text)
  }
  for (const year of electionYears) {
    const national = validateTerritorySummary(read(`public/data/territorial/summaries/${year}/national.json`), year, null)
    const labels = read(`data/processed/participamx_multiyear/elections/${year}/sex_statistics.json`)
    assert.equal(labels.election_year, year)
    assert.deepEqual(labels.data.map(row => row.sex_code), national.registered_sexes)
    labels.data.forEach(row => assert.equal(row.sex_label, sexLabels[row.sex_code]))
    const states = Array.from({ length: 32 }, (_, i) => {
      const code = String(i + 1).padStart(2, '0')
      return validateTerritorySummary(read(`public/data/territorial/summaries/${year}/${code}.json`), year, code)
    })
    for (const field of fields) assert.equal(sumCounts(states.map(state => state.totals))[field], national.totals[field], `${year}:${field}`)
    for (const cell of [...national.segments, ...national.complementary]) {
      const matching = states.flatMap(state => [...state.segments, ...state.complementary]).filter(row => row.age_band === cell.age_band && row.sex_code === cell.sex_code)
      for (const field of fields) assert.equal(sumCounts(matching)[field], cell[field], `${year}:${cell.age_band}:${cell.sex_code}:${field}`)
    }
    const text = JSON.stringify({ schema_version: 'territorial-layers-1', election_year: year, registered_sexes: national.registered_sexes, states }) + '\n'
    files.set(`${year}.json`, text)
    coverage.push({ election_year: year, states: states.length, registered_sexes: national.registered_sexes, LN: national.totals.LN })
  }
  const manifest = { schema_version: 'territorial-layers-1', sources, coverage,
    files: Object.fromEntries([...files].map(([name, text]) => [name, { sha256: hash(text), bytes: Buffer.byteLength(text) }])) }
  files.set('index.json', JSON.stringify(manifest) + '\n')
  for (const [name, text] of files) {
    const target = join(root, 'public/data/territorial/layers', name)
    if (check) assert.equal(readFileSync(target, 'utf8'), text, `Capa desactualizada: ${name}`)
    else { mkdirSync(join(target, '..'), { recursive: true }); writeFileSync(target, text) }
  }
  return { files: files.size, bytes: [...files.values()].reduce((sum, text) => sum + Buffer.byteLength(text), 0), coverage }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) console.log(JSON.stringify(buildTerritorialLayers({ check: process.argv.includes('--check') }), null, 2))
