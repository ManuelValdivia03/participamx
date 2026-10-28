import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { loadMapModule } from './load_map_module.mjs'
import { buildTerritorialLayers } from './build-territorial-layers.mjs'

import { createThematicScale } from '../src/features/map/thematicScale.ts'
const { layerValue, layerDefinitions, validateLayerIndex, thematicFill, layerUniverse, layerExplanation, formatLayerPercent } = await loadMapModule('thematicData')
const read = path => JSON.parse(readFileSync(path, 'utf8'))
const years = [2009, 2012, 2015, 2018, 2021, 2024]
const close = (a, b) => assert.ok(Math.abs(a - b) < 1e-13, `${a} != ${b}`)

test('capas estatales: generación determinista, contratos, categorías oficiales y totales de seis elecciones', () => {
  const result = buildTerritorialLayers({ check: true })
  assert.equal(result.files, 7)
  assert.ok(result.bytes < 450000)
  for (const year of years) {
    const data = validateLayerIndex(read(`public/data/territorial/layers/${year}.json`), year)
    const labels = read(`data/processed/participamx_multiyear/elections/${year}/sex_statistics.json`).data
    assert.deepEqual(data.registered_sexes, labels.map(row => row.sex_code))
    assert.deepEqual(labels.map(row => row.sex_label), year === 2024 ? ['Hombres', 'Mujeres', 'No binario'] : ['Hombres', 'Mujeres'])
    for (const state of data.states) assert.deepEqual(state, read(`public/data/territorial/summaries/${year}/${state.state_code}.json`))
    const duplicate = structuredClone(data); duplicate.states[1] = duplicate.states[0]
    assert.throws(() => validateLayerIndex(duplicate, year))
    assert.throws(() => validateLayerIndex(data, year + 1))
  }
})

function verifyProfile(profile, sexes) {
  const total = profile.totals, cells = [...profile.segments, ...profile.complementary]
  for (const [key, definition] of Object.entries(layerDefinitions)) {
    if (definition.group === 'section') continue // El marginal TIPOSEC tiene su propia prueba y fuente.
    const result = layerValue(profile, key, sexes)
    if (definition.sex && !sexes.includes(definition.sex)) { assert.equal(result.status, 'unavailable_category'); assert.equal(result.value, null); continue }
    const matching = definition.sex ? cells.filter(cell => cell.sex_code === definition.sex) : definition.band ? cells.filter(cell => cell.age_band === definition.band) : null
    if (matching && !matching.length) { assert.equal(result.value, null); assert.equal(result.status, 'missing'); continue }
    const counts = matching ? Object.fromEntries(['LN', 'SV', 'NV', 'NS', 'source_row_count'].map(field => [field, matching.reduce((sum, row) => sum + row[field], 0)])) : total
    const numerator = key === 'participation' ? total.SV : key === 'nonparticipation' ? total.NV : definition.kind === 'participant_composition' ? counts.SV : counts.LN
    const denominator = definition.kind === 'rate' ? total.SV + total.NV : definition.kind === 'participant_composition' ? total.SV : total.LN
    assert.equal(result.numerator, numerator); assert.equal(result.denominator, denominator)
    assert.deepEqual(result.counts, counts)
    if (!denominator) assert.equal(result.value, null)
    else {
      close(result.value, numerator / denominator)
      assert.equal(result.status, counts.LN >= 100 && counts.SV + counts.NV >= 100 && counts.source_row_count >= 5 ? 'defined' : 'low_support')
    }
    assert.equal(result.highNs, counts.LN > 0 && counts.NS / counts.LN >= .1)
  }
  if (total.SV + total.NV > 0) close(layerValue(profile, 'participation', sexes).value + layerValue(profile, 'nonparticipation', sexes).value, 1)
  const included = ['age18_34', 'age35_59', 'age60_100'].reduce((sum, layer) => sum + (layerValue(profile, layer, sexes).numerator ?? 0), 0)
  const older = cells.filter(row => row.age_band === '101+').reduce((sum, row) => sum + row.LN, 0)
  assert.equal(included + older, total.LN, '101+ se conserva fuera de los tres numeradores')
}

test('diez capas: valores y denominadores independientes en 192 entidades y 14,779 municipios', () => {
  let municipalities = 0
  for (const year of years) {
    const data = read(`public/data/territorial/layers/${year}.json`)
    for (const state of data.states) {
      verifyProfile(state, data.registered_sexes)
      for (const municipality of read(`public/data/territorial/${year}/${state.state_code}.json`).data) {
        verifyProfile(municipality, data.registered_sexes); municipalities++
      }
    }
  }
  assert.equal(municipalities, 14779)
})

test('capas: cero válido, denominador cero, ausencia, correspondencia y categoría escasa son estados distintos', () => {
  const counts = { LN: 200, SV: 0, NV: 100, NS: 100, source_row_count: 8 }
  const cell = { ...counts, age_band: '18-34', sex_code: '0' }
  const profile = { totals: counts, segments: [cell], complementary: [] }
  assert.equal(layerValue(profile, 'participation', ['0', '1']).value, 0)
  assert.equal(layerValue(profile, 'nonparticipation', ['0', '1']).value, 1)
  assert.equal(layerValue(profile, 'participation', ['0', '1']).highNs, true)
  assert.equal(layerValue(profile, 'women', ['0', '1']).status, 'missing')
  assert.equal(layerValue(profile, 'nonbinary', ['0', '1']).status, 'unavailable_category')
  assert.equal(layerValue(profile, 'men', ['0', '1'], false).status, 'unmapped')
  assert.equal(layerValue(null, 'participation', ['0', '1']).status, 'missing')
  const undefinedProfile = { ...profile, totals: { ...counts, SV: 0, NV: 0, NS: 200 } }
  assert.equal(layerValue(undefinedProfile, 'participation', ['0', '1']).status, 'undefined')
  const sparse = { totals: { ...counts, source_row_count: 4 }, segments: [], complementary: [] }
  assert.equal(layerValue(sparse, 'participation', ['0', '1']).status, 'low_support')
  const nonbinary = { ...profile, complementary: [{ LN: 1, SV: 1, NV: 0, NS: 0, source_row_count: 1, age_band: '35-59', sex_code: '2' }] }
  assert.equal(layerValue(nonbinary, 'nonbinary', ['0', '1', '2']).status, 'low_support')
  assert.equal(layerValue(nonbinary, 'nonbinary', ['0', '1', '2']).value, .005)
})

test('cuantiles, neutros separados, precisión de proporciones pequeñas y explicación fiel al universo', () => {
  const defined = { value: .6, status: 'defined' }
  const scale = createThematicScale([.6])
  assert.equal(thematicFill(defined, scale), 'var(--atlas-color-2)')
  assert.equal(thematicFill({ ...defined, status: 'low_support' }, scale), 'var(--atlas-low-support)')
  assert.equal(thematicFill({ ...defined, value: null, status: 'undefined' }, scale), 'var(--atlas-no-data)')
  assert.equal(thematicFill({ ...defined, status: 'unavailable_category' }, scale), 'var(--atlas-no-data)')
  const zeroScale=createThematicScale([0,.6])
  assert.equal(thematicFill({value:0,status:'defined'},zeroScale),'var(--atlas-color-0)')
  assert.equal(formatLayerPercent(null), 'Sin información')
  assert.notEqual(formatLayerPercent(.0000001), '0 %')
  assert.ok(layerUniverse('age60_100').includes('101+ sólo en el denominador'))
  assert.ok(layerUniverse('women').includes('No es población censal'))
  for(const layer of Object.keys(layerDefinitions)) assert.ok(layerExplanation(layer).length>20)
  assert.ok(layerExplanation('women').includes('lista nominal total'))
  assert.ok(layerExplanation('women_participants').includes('total de participantes'))
  assert.ok(layerExplanation('nonparticipation').includes('no incluye NS'))
})
