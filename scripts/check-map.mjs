import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs'
import { geoArea } from 'd3-geo'
import ts from 'typescript'

// Exercise the same normalization and projection used by the UI, with the committed dataset.
const source = readFileSync('src/features/map/geography.ts', 'utf8').replace(
  "import raw from './data/mexico-states.json'",
  "import { readFileSync } from 'node:fs'; const raw = JSON.parse(readFileSync('src/features/map/data/mexico-states.json', 'utf8'))",
)
mkdirSync('node_modules/.cache', { recursive: true })
const modulePath = 'node_modules/.cache/map-regression.mjs'
writeFileSync(modulePath, ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText)

try {
  const { states, country, path, projection, stateView } = await import(`../${modulePath}`)
  assert.equal(states.length, 32)
  assert.equal(new Set(states.map(state => state.properties.code)).size, 32)
  for (const state of states) {
    const area = geoArea(state)
    assert.ok(area > 0 && area < 0.01, `${state.properties.name}: unexpected spherical area`)
    assert.ok(path(state) && !path(state).includes('NaN'))
    const view = stateView(state).split(' ').map(Number)
    assert.ok(view.every(Number.isFinite) && view[2] > 0 && view[3] > 0)
  }
  // A polygon interpreted as the globe used to shrink mainland Mexico to a tiny dot.
  const west = projection([-117, 32])
  const east = projection([-87, 21])
  assert.ok(east[0] - west[0] > 500, 'Mexico must occupy most of the viewport')
  assert.ok(geoArea(country) > 0.04 && geoArea(country) < 0.06)
  assert.equal(states.find(state => state.properties.code === '09').properties.name, 'Ciudad de México')
  assert.equal(states.find(state => state.properties.code === '15').properties.name, 'Estado de México')
  console.log('Map regression: 32 states, valid areas, national framing and state zooms OK.')
} finally {
  rmSync(modulePath, { force: true })
}
