import { readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import assert from 'node:assert/strict'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { validateSearchIndex } from '../src/features/map/territorySearchData.ts'

export function buildTerritorySearch({ check = false } = {}) {
  const years = [2009, 2012, 2015, 2018, 2021, 2024], states = [], municipalities = [], sources = {}
  function read(path) {
    const text = readFileSync(path, 'utf8')
    sources[path] = createHash('sha256').update(text).digest('hex')
    return JSON.parse(text)
  }
  const labels = read('public/data/participamx_multiyear/elections/2024/states.json').data
  for (let state = 1; state <= 32; state++) {
    const code = String(state).padStart(2, '0')
    const features = read(`public/data/municipalities/${code}.json`).features
    const crosswalk = read(`public/data/ine-crosswalk/${code}.json`)
    assert.equal(crosswalk.stateCode, code)
    const name = labels.find(row => Number(row.state_code) === state).state_name
    states.push({ kind: 'state', code, state_code: code, name, ine_codes: years.map(() => code) })
    for (const feature of features) {
      const p = feature.properties
      assert.equal(p.stateCode, code)
      assert.equal(p.code, p.stateCode + p.municipalityCode)
      municipalities.push({ kind: 'municipality', code: p.code, state_code: code, name: p.name,
        ine_codes: years.map(year => {
          const entry = crosswalk.years[year][p.code]
          if (!entry) return null
          assert.equal(entry.method, 'unique-normalized-name')
          return entry.ineCode
        }) })
    }
  }
  const data = validateSearchIndex({ schema_version: 'territory-search-1', years, states, municipalities })
  const text = JSON.stringify({ ...data, sources }) + '\n'
  const target = 'public/data/territorial/search-index.json'
  if (check) assert.equal(readFileSync(target, 'utf8'), text)
  else writeFileSync(target, text)
  return { states: states.length, municipalities: municipalities.length, bytes: Buffer.byteLength(text), sources: Object.keys(sources).length }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) console.log(buildTerritorySearch({ check: process.argv.includes('--check') }))
