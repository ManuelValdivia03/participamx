
import { getElectionsIndex } from './electionData'

export interface MunicipalityProfile {
  election_year: number
  state_code: string
  municipality_code: string
  profile_id: string
  LN: number | null
  segments: number | null
  participation_observed: number | null
  matched_peer_reference: number | null
  relative_turnout: number | null
  has_low_support: boolean | null
  has_high_ns: boolean | null
}

interface MunicipalityProfilesResponse {
  schema_version: string
  election_year: number
  rate_unit: string
  data: MunicipalityProfile[]
}

const cache = new Map<string, MunicipalityProfile[]>()

export async function getMunicipalityProfiles(
  year: number,
  stateCode: string,
  signal?: AbortSignal
): Promise<MunicipalityProfile[]> {
  const state = stateCode.padStart(2, '0')

  if (!/^(0[1-9]|[12]\d|3[0-2])$/.test(state)) {
    throw new Error('Clave estatal inválida')
  }

  const cacheKey = `${year}:${state}`

  const cached = cache.get(cacheKey)

  if (cached) {
    return cached
  }

  const index = await getElectionsIndex(signal)

  const election = index.elections.find(
    item => item.election_year === year
  )

  if (!election) {
    throw new Error(`Elección ${year} no disponible`)
  }

  const stateFile = Number(state)

  const resourcePath =
    `${election.base_path}municipality_profiles/${stateFile}.json`

  const response = await fetch(
    `${import.meta.env.BASE_URL}data/participamx_multiyear/${resourcePath}`,
    { signal }
  )

  if (!response.ok) {
    throw new Error(
      `No se pudieron cargar los perfiles de ${state} en ${year}`
    )
  }

  const result: MunicipalityProfilesResponse =
    await response.json()

  if (
    result.schema_version !== '2.0.0' ||
    result.election_year !== year ||
    result.rate_unit !== 'proportion' ||
    !Array.isArray(result.data) ||
    !result.data.every(item =>
      item.election_year === year &&
      typeof item.state_code === 'string' &&
      item.state_code.padStart(2, '0') === state &&
      typeof item.municipality_code === 'string' &&
      typeof item.profile_id === 'string'
    )
  ) {
    throw new Error('Formato de perfiles municipales inválido')
  }

  const profiles = result.data.map(item => ({
    ...item,
    state_code: item.state_code.padStart(2, '0'),
    municipality_code: item.municipality_code.padStart(3, '0')
  }))

  if (!signal?.aborted) {
    cache.set(cacheKey, profiles)
  }

  return profiles
}
