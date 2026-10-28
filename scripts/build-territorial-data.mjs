import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  electionYears, normalizeStateCode, normalizeIneCode, isCoreSegment,
  sumCounts, turnout, ratio, validateTerritorialResponse,
} from '../src/features/map/territorialData.ts'

const root = fileURLToPath(new URL('../', import.meta.url))
const sourceRoot = join(root, 'data/processed/participamx_multiyear/elections')
const countFields = ['LN', 'SV', 'NV', 'NS', 'source_row_count']
const digest = text => createHash('sha256').update(text).digest('hex')

// Sólo se proyectan agregados validados; no se leen CSV, ZIP ni edad exacta.
export function buildTerritorialData({ output = join(root, 'public/data/territorial'), check = false } = {}) {
  const sources = {}
  const files = new Map()
  const coverage = []
  function readSource(relative, year, unit) {
    const text = readFileSync(join(sourceRoot, relative), 'utf8')
    sources[relative] = digest(text)
    const payload = JSON.parse(text)
    assert.equal(payload.schema_version, '2.0.0')
    assert.equal(payload.election_year, year)
    assert.equal(payload.rate_unit, 'proportion')
    assert.equal(payload.unit, unit)
    assert.ok(Array.isArray(payload.data))
    return payload
  }
  for (const year of electionYears) {
    const municipalities = readSource(`${year}/municipalities.json`, year, 'municipality')
    const states = readSource(`${year}/states.json`, year, 'state')
    const national = readSource(`${year}/national_statistics.json`, year, 'election')
    const allSegments = []
    let missingCells = 0
    for (let number = 1; number <= 32; number++) {
      const state = normalizeStateCode(number)
      const source = `${year}/municipality_segments/${number}.json`
      const original = readSource(source, year, 'municipality_age_band_sex')
      const groups = new Map()
      for (const row of original.data) {
        assert.equal(row.election_year, year)
        assert.equal(normalizeStateCode(row.state_code), state)
        assert.equal(row.specified_count, row.SV + row.NV)
        assert.equal(row.local_turnout, turnout(row))
        assert.equal(row.unspecified_rate, ratio(row.NS, row.LN))
        const key = normalizeIneCode(row.state_code, row.municipality_code)
        if (!groups.has(key)) groups.set(key, [])
        groups.get(key).push(Object.fromEntries([
          ...countFields.map(field => [field, row[field]]),
          ...['age_band', 'sex_code', 'sufficient_support', 'high_ns', 'assignment_status'].map(field => [field, row[field]]),
        ]))
      }
      const data = municipalities.data.filter(row => normalizeStateCode(row.state_code) === state).map(row => {
        const ine_code = normalizeIneCode(row.state_code, row.municipality_code)
        const segments = groups.get(ine_code)
        assert.ok(segments, `Sin segmentos: ${year}:${ine_code}`)
        groups.delete(ine_code)
        const total = sumCounts(segments)
        for (const field of countFields) assert.equal(total[field], row[field], `${year}:${ine_code}:${field}`)
        const core = segments.filter(isCoreSegment)
        missingCells += 6 - core.length
        allSegments.push(...segments)
        return {
          ine_code, municipality_name: row.municipality_name,
          totals: Object.fromEntries(countFields.map(field => [field, row[field]])),
          profile_ids: row.profile_ids,
          segments: core.sort((a, b) => a.age_band.localeCompare(b.age_band) || a.sex_code.localeCompare(b.sex_code)),
          complementary: segments.filter(segment => !isCoreSegment(segment)),
        }
      }).sort((a, b) => a.ine_code.localeCompare(b.ine_code))
      assert.equal(groups.size, 0, 'Segmentos sin municipio de referencia')
      const payload = validateTerritorialResponse({
        schema_version: 'territorial-explorer-1', election_year: year, state_code: state,
        rate_unit: 'proportion', source: `data/processed/participamx_multiyear/elections/${source}`,
        warnings: original.warnings, data,
      }, year, state)
      const total = sumCounts(data.map(row => row.totals))
      const reference = states.data.find(row => normalizeStateCode(row.state_code) === state)
      for (const field of countFields) assert.equal(total[field], reference[field], `${year}:${state}:${field}`)
      files.set(`${year}/${state}.json`, JSON.stringify(payload) + '\n')
    }
    const total = sumCounts(allSegments)
    for (const field of countFields) assert.equal(total[field], national.data[0][field], `${year}:national:${field}`)
    coverage.push({ election_year: year, municipalities: municipalities.data.length,
      segments: allSegments.length, missing_core_cells: missingCells,
      undefined_core_rates: allSegments.filter(row => isCoreSegment(row) && turnout(row) === null).length,
      low_support_core_cells: allSegments.filter(row => isCoreSegment(row) && !row.sufficient_support).length,
      high_ns_core_cells: allSegments.filter(row => isCoreSegment(row) && row.high_ns).length,
      ...total,
    })
  }
  const manifest = {
    schema_version: 'territorial-explorer-1', rate_unit: 'proportion',
    source_root: 'data/processed/participamx_multiyear/elections',
    counts_unit: 'reported_counts', age_bands: ['18-34', '35-59', '60-100'], sex_codes: ['0', '1'],
    support: { min_LN: 100, min_specified: 100, min_source_rows: 5, high_ns_fraction: .1 },
    coverage, sources,
    files: Object.fromEntries([...files].map(([path, text]) => [path, { sha256: digest(text), bytes: Buffer.byteLength(text) }])),
  }
  files.set('index.json', JSON.stringify(manifest) + '\n')
  for (const [relative, text] of files) {
    const target = join(output, relative)
    if (check) assert.equal(readFileSync(target, 'utf8'), text, `Archivo desactualizado: ${relative}`)
    else {
      if (existsSync(target)) assert.equal(JSON.parse(readFileSync(target, 'utf8')).schema_version, 'territorial-explorer-1')
      mkdirSync(join(target, '..'), { recursive: true })
      writeFileSync(target, text, 'utf8')
      assert.equal(readFileSync(target, 'utf8'), text)
    }
  }
  return { files: files.size, bytes: [...files.values()].reduce((sum, text) => sum + Buffer.byteLength(text), 0), coverage }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const outputIndex = process.argv.indexOf('--output')
  if (outputIndex >= 0 && !process.argv[outputIndex + 1]) throw new Error('Falta --output')
  console.log(JSON.stringify(buildTerritorialData({
    check: process.argv.includes('--check'),
    ...(outputIndex >= 0 ? { output: resolve(process.argv[outputIndex + 1]) } : {}),
  }), null, 2))
}
