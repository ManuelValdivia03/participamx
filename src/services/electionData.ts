
export interface Election {
  election_year: number
  election_type: 'midterm' | 'presidential'
  label: string
  base_path: string
  profiles_path: string
  states_path: string
  municipalities_path: string
  profiles_with_support: number
  municipal_history_enabled: boolean
}

export interface ElectionsIndex {
  schema_version: string
  status: string
  default_election_year: number
  elections: Election[]
  historical_comparison_path: string
  municipal_history_enabled: boolean
  warnings: string[]
}

const DATA_BASE = `${import.meta.env.BASE_URL}data/participamx_multiyear/`

export async function getElectionsIndex(
  signal?: AbortSignal
): Promise<ElectionsIndex> {
  const response = await fetch(`${DATA_BASE}elections_index.json`, {
    signal
  })

  if (!response.ok) {
    throw new Error(
      `No se pudo cargar el índice electoral: ${response.status}`
    )
  }

  const data: unknown = await response.json()

  if (
    typeof data !== 'object' ||
    data === null ||
    !('schema_version' in data) ||
    data.schema_version !== '2.0.0' ||
    !('elections' in data) ||
    !Array.isArray(data.elections) ||
    !data.elections.every(
      (election: unknown) =>
        typeof election === 'object' &&
        election !== null &&
        'election_year' in election &&
        typeof election.election_year === 'number' &&
        'label' in election &&
        typeof election.label === 'string'
    )
  ) {
    throw new Error('El índice electoral no tiene el formato esperado')
  }

  return data as unknown as ElectionsIndex
}


export interface NationalStatistics {
  election_year: number
  LN: number
  SV: number
  NV: number
  NS: number
  specified_count: number
  participation_observed: number | null
  participation_nominal: number | null
  nonparticipation_observed: number | null
  unspecified_rate: number | null
}

interface NationalStatisticsResponse {
  schema_version: string
  election_year: number
  rate_unit: 'proportion'
  data: NationalStatistics[]
  warnings: string[]
}

export async function getNationalStatistics(
  year: number,
  signal?: AbortSignal
): Promise<NationalStatistics> {
  const index = await getElectionsIndex(signal)

  const election = index.elections.find(
    item => item.election_year === year
  )

  if (!election) {
    throw new Error(`Elección ${year} no disponible`)
  }

  const response = await fetch(
    `${DATA_BASE}${election.base_path}national_statistics.json`,
    { signal }
  )

  if (!response.ok) {
    throw new Error(`No se pudieron cargar las estadísticas de ${year}`)
  }

  const result: NationalStatisticsResponse = await response.json()

  if (
    result.schema_version !== '2.0.0' ||
    result.election_year !== year ||
    result.rate_unit !== 'proportion' ||
    !Array.isArray(result.data) ||
    result.data.length !== 1 ||
    result.data[0].election_year !== year
  ) {
    throw new Error('Formato de estadísticas nacionales no válido')
  }

  return result.data[0]
}


export interface ElectionProfile {
  election_year: number
  profile_id: string
  label: string
  status: string
  age_band: string
  segments: number
  municipalities: number
  states: number
  LN: number
  participation_observed: number | null
  matched_peer_reference: number | null
  participation_delta: number | null
  nominal_coverage: number | null
}

interface ElectionProfilesResponse {
  schema_version: string
  election_year: number
  rate_unit: 'proportion'
  data: ElectionProfile[]
  warnings: string[]
}

export async function getElectionProfiles(
  year: number,
  signal?: AbortSignal
): Promise<ElectionProfile[]> {
  const index = await getElectionsIndex(signal)

  const election = index.elections.find(
    item => item.election_year === year
  )

  if (!election) {
    throw new Error(`Elección ${year} no disponible`)
  }

  const response = await fetch(
    `${DATA_BASE}${election.profiles_path}`,
    { signal }
  )

  if (!response.ok) {
    throw new Error(
      `No se pudieron cargar los perfiles de ${year}`
    )
  }

  const result: ElectionProfilesResponse = await response.json()

  if (
    result.schema_version !== '2.0.0' ||
    result.election_year !== year ||
    result.rate_unit !== 'proportion' ||
    !Array.isArray(result.data) ||
    !result.data.every(profile =>
      profile.election_year === year &&
      typeof profile.profile_id === 'string' &&
      typeof profile.label === 'string' &&
      typeof profile.segments === 'number'
    )
  ) {
    throw new Error('Formato de perfiles electorales no válido')
  }

  return result.data
}


export interface StateStatistics {
  election_year: number
  source_row_count: number
  state_code: string
  state_name: string
  LN: number
  SV: number
  NV: number
  NS: number
  participation_observed: number | null
  participation_nominal: number | null
  unspecified_rate: number | null
  supported_segments: number
  supported_nominal_fraction: number | null
  profile_ids: string[]
}

interface StatesStatisticsResponse {
  schema_version: string
  election_year: number
  rate_unit: 'proportion'
  data: StateStatistics[]
  warnings: string[]
}

export async function getStatesStatistics(
  year: number,
  signal?: AbortSignal
): Promise<StateStatistics[]> {
  const index = await getElectionsIndex(signal)

  const election = index.elections.find(
    item => item.election_year === year
  )

  if (!election) {
    throw new Error(`Elección ${year} no disponible`)
  }

  const response = await fetch(
    `${DATA_BASE}${election.states_path}`,
    { signal }
  )

  if (!response.ok) {
    throw new Error(
      `No se pudieron cargar las estadísticas estatales de ${year}`
    )
  }

  const result: StatesStatisticsResponse = await response.json()

  if (
    result.schema_version !== '2.0.0' ||
    result.election_year !== year ||
    result.rate_unit !== 'proportion' ||
    !Array.isArray(result.data) ||
    !result.data.every(state =>
      state.election_year === year &&
      typeof state.state_code === 'string' &&
      typeof state.state_name === 'string' &&
      typeof state.LN === 'number' &&
      [state.LN, state.SV, state.NV, state.NS, state.source_row_count].every(value => Number.isSafeInteger(value) && value >= 0) &&
      state.LN === state.SV + state.NV + state.NS &&
      (
        state.participation_observed === null ||
        typeof state.participation_observed === 'number'
      )
    )
  ) {
    throw new Error('Formato de estadísticas estatales no válido')
  }

  return result.data.map(state => ({
    ...state,
    state_code: state.state_code.padStart(2, '0')
  }))
}

export interface MunicipalStatistics {
  election_year: number
  state_code: string
  municipality_code: string
  municipality_name: string | null
  state_name: string | null
  LN: number | null
  participation_observed: number | null
  participation_nominal: number | null
  unspecified_rate: number | null
  has_low_support: boolean | null
  has_high_ns: boolean | null
  profile_ids: string[] | null
}

interface MunicipalStatisticsResponse {
  schema_version: string
  election_year: number
  rate_unit: 'proportion'
  data: MunicipalStatistics[]
  warnings: string[]
}

export async function getMunicipalStatistics(
  year: number,
  signal?: AbortSignal
): Promise<MunicipalStatistics[]> {
  const index = await getElectionsIndex(signal)

  const election = index.elections.find(
    item => item.election_year === year
  )

  if (!election) {
    throw new Error(`Elección ${year} no disponible`)
  }

  const response = await fetch(
    `${DATA_BASE}${election.municipalities_path}`,
    { signal }
  )

  if (!response.ok) {
    throw new Error(
      `No se pudieron cargar las estadísticas municipales de ${year}`
    )
  }

  const result: MunicipalStatisticsResponse = await response.json()

  if (
    result.schema_version !== '2.0.0' ||
    result.election_year !== year ||
    result.rate_unit !== 'proportion' ||
    !Array.isArray(result.data) ||
    !result.data.every(item =>
      item.election_year === year &&
      typeof item.state_code === 'string' &&
      typeof item.municipality_code === 'string'
    )
  ) {
    throw new Error('Formato de estadísticas municipales no válido')
  }

  return result.data.map(item => ({
    ...item,
    state_code: item.state_code.padStart(2, '0'),
    municipality_code: item.municipality_code.padStart(3, '0')
  }))
}
