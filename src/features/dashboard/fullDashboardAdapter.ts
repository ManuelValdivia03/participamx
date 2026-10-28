
import { getElectionsIndex } from '../../services/electionData'
import { loadRealDashboard } from './dashboardAdapter'
import { profileNames as profileLabels } from '../profiles/profilePresentation'
import type {
  DashboardDataset,
  DashboardSnapshot
} from './types'

type StateRow = {
  state_code: string
  state_name: string
  LN: number | null
  participation_observed: number | null
  supported_nominal_fraction: number | null
}

type StateProfileRow = {
  state_code: string
  profile_id: string
  share_of_territorial_LN: number | null
}

type DataResource<T> = {
  schema_version: string
  election_year: number
  rate_unit: string
  data: T[]
}

async function readResource<T>(
  path: string,
  year: number,
  signal: AbortSignal
): Promise<T[]> {
  const url =
    `${import.meta.env.BASE_URL}data/participamx_multiyear/${path}`

  const response = await fetch(url, { signal })

  if (!response.ok) {
    throw new Error(`No se pudo cargar ${path}`)
  }

  const resource: DataResource<T> = await response.json()

  if (
    resource.schema_version !== '2.0.0' ||
    resource.election_year !== year ||
    resource.rate_unit !== 'proportion' ||
    !Array.isArray(resource.data)
  ) {
    throw new Error(`Formato de datos inválido: ${path}`)
  }

  return resource.data
}

export async function loadFullDashboard(
  signal: AbortSignal
): Promise<DashboardDataset> {
  const [national, index] = await Promise.all([
    loadRealDashboard(signal),
    getElectionsIndex(signal)
  ])

  const results = await Promise.all(
    index.elections.map(async election => {
      const year = election.election_year

      const [states, profiles] = await Promise.all([
        readResource<StateRow>(
          election.states_path,
          year,
          signal
        ),
        readResource<StateProfileRow>(
          `${election.base_path}state_profiles.json`,
          year,
          signal
        )
      ])

      return { year, states, profiles }
    })
  )

  const territories = new Map(
    national.territories.map(territory => [
      territory.code,
      territory
    ])
  )

  const stateSnapshots: DashboardSnapshot[] = []

  for (const { year, states, profiles } of results) {
    for (const state of states) {
      const code = state.state_code.padStart(2, '0')

      territories.set(code, {
        code,
        name: state.state_name
      })

      const stateProfiles = profiles.filter(
        profile =>
          profile.state_code.padStart(2, '0') === code
      )

      stateSnapshots.push({
        year,
        territoryCode: code,
        metrics: {
          participation:
            state.participation_observed === null
              ? null
              : state.participation_observed * 100,

          coverage:
            state.supported_nominal_fraction === null
              ? null
              : state.supported_nominal_fraction * 100,

          nominalList: state.LN,

          profileCount: stateProfiles.length
        },

        distribution: stateProfiles.map(profile => ({
          id: profile.profile_id,
          name:
            profileLabels[profile.profile_id] ??
            profile.profile_id,

          percentage:
            profile.share_of_territorial_LN === null
              ? null
              : profile.share_of_territorial_LN * 100
        })),

        notes: [
          'Participación observada: SV / (SV + NV).',
          'La distribución representa la proporción de lista nominal territorial cubierta por cada perfil, no la tasa de participación.',
          'Las seis elecciones son cortes independientes; no demuestran cambios de conducta individual.'
        ]
      })
    }
  }

  const allTerritories = Array.from(territories.values())

  return {
    ...national,
    territories: [
      ...allTerritories.filter(item => item.code === 'MX'),
      ...allTerritories
        .filter(item => item.code !== 'MX')
        .sort((a, b) =>
          a.name.localeCompare(b.name, 'es')
        )
    ],
    snapshots: [
      ...national.snapshots,
      ...stateSnapshots
    ]
  }
}
