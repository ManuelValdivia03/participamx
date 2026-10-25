
import assert from 'node:assert/strict'
import { readFile, access } from 'node:fs/promises'
import { join } from 'node:path'

const base = join(
  process.cwd(),
  'public',
  'data',
  'participamx_multiyear'
)

async function read(path) {
  const content = await readFile(join(base, path), 'utf8')
  return JSON.parse(content)
}

const index = await read('elections_index.json')
const expectedYears = [2009, 2012, 2015, 2018, 2021, 2024]

assert.equal(index.schema_version, '2.0.0')
assert.equal(index.default_election_year, 2024)
assert.deepEqual(
  index.elections.map(item => item.election_year),
  expectedYears
)

for (const election of index.elections) {
  const year = election.election_year
  const path = `elections/${year}`

  const [national, profiles, states, stateProfiles, ages] =
    await Promise.all([
      read(`${path}/national_statistics.json`),
      read(`${path}/profiles.json`),
      read(`${path}/states.json`),
      read(`${path}/state_profiles.json`),
      read(`${path}/age_statistics.json`)
    ])

  for (const resource of [
    national,
    profiles,
    states,
    stateProfiles,
    ages
  ]) {
    assert.equal(resource.election_year, year)
    assert.equal(resource.rate_unit, 'proportion')
    assert.ok(Array.isArray(resource.data))
  }

  assert.equal(profiles.data.length, 6)
  assert.equal(states.data.length, 32)

  const sex2 = ages.data.some(row => row.sex_code === '2')

  assert.equal(sex2, year === 2024)

  for (let state = 1; state <= 32; state++) {
    await access(
      join(path, 'municipality_profiles', `${state}.json`)
        .replace(/^/, `${base}/`)
    )
  }

  console.log(
    `OK ${year}: seis perfiles, 32 entidades y recursos de edad`
  )
}

const national2024 = await read(
  'elections/2024/national_statistics.json'
)

assert.ok(
  Math.abs(
    national2024.data[0].participation_observed - 0.5967002944
  ) < 0.00001
)

const profiles2024 = await read(
  'elections/2024/profiles.json'
)

const adult = profiles2024.data.find(
  item => item.profile_id === 'adult_favorable'
)

assert.ok(adult)
assert.equal(adult.segments, 3015)
assert.equal(adult.municipalities, 1641)
assert.equal(adult.LN, 20337701)

for (const year of [2009, 2024]) {
  const resource = await read(
    `elections/${year}/municipality_profiles/30.json`
  )

  const coatepec = resource.data.filter(
    item => item.municipality_code === '40'
  )

  assert.equal(coatepec.length, 4)
}

console.log(
  'PRUEBAS DE DATOS REALES SUPERADAS'
)
