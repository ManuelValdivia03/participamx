import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs'
import ts from 'typescript'

mkdirSync('node_modules/.cache', { recursive: true })
const modulePath = 'node_modules/.cache/ine-keys-check.mjs'
writeFileSync(modulePath, ts.transpileModule(readFileSync('src/features/map/ineKeys.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText)
try {
  const { electoralYears, resolveIneKey, electoralJoinKey } = await import(`../${modulePath}`)
  const totals = Object.fromEntries(electoralYears.map(year => [year, 0]))
  for (const year of electoralYears) {
    const seen = new Set()
    for (let state = 1; state <= 32; state++) {
      const code = String(state).padStart(2, '0')
      const table = JSON.parse(readFileSync(`public/data/ine-crosswalk/${code}.json`, 'utf8'))
      const geometryCodes = new Set(JSON.parse(readFileSync(`public/data/municipalities/${code}.json`, 'utf8')).features.map(f => f.properties.code))
      for (const inegi of Object.keys(table.years[year])) {
        assert.ok(geometryCodes.has(inegi))
        const resolved = resolveIneKey(inegi, year, table)
        assert.ok(!seen.has(resolved.ineCode), `Duplicate INE key ${year}:${resolved.ineCode}`)
        seen.add(resolved.ineCode)
        assert.equal(resolved.code, resolved.ineCode)
        assert.equal(electoralJoinKey(resolved), `${year}:${resolved.ineCode}`)
        totals[year]++
      }
    }
  }
  const ags = JSON.parse(readFileSync('public/data/ine-crosswalk/01.json', 'utf8'))
  assert.equal(resolveIneKey('01011', '2024', ags).code, '01010', 'San Francisco de los Romo must use its INE key')
  assert.equal(resolveIneKey('01010', '2024', ags).code, '01011', 'El Llano must not receive its neighbor’s data')
  const slp = JSON.parse(readFileSync('public/data/ine-crosswalk/24.json', 'utf8'))
  const pending = resolveIneKey('24059', '2024', slp)
  assert.equal(pending.ineCode, null, 'Never reuse an INEGI code as fallback')
  assert.equal(electoralJoinKey(pending), null)
  const oaxaca = JSON.parse(readFileSync('public/data/ine-crosswalk/20.json', 'utf8'))
  assert.equal(resolveIneKey('20208', '2024', oaxaca).code, null, 'Duplicate names require review')
  assert.equal(resolveIneKey('20209', '2024', oaxaca).code, null)
  const metadata = JSON.parse(readFileSync('public/data/ine-crosswalk/metadata.json', 'utf8'))
  for (const record of metadata.years) {
    assert.equal(totals[record.year], record.mapped)
    assert.equal(record.mapped + record.unresolved.length, record.ineMunicipalities)
  }
  console.log('INE keys: six years, unique correspondences, swapped codes and unresolved cases OK.')
} finally { rmSync(modulePath, { force: true }) }
