
import {
  getElectionsIndex,
  getNationalStatistics,
  getElectionProfiles
} from '../../services/electionData'

import type { DashboardDataset } from './types'

export async function loadRealDashboard(
  signal: AbortSignal
): Promise<DashboardDataset> {
  const index = await getElectionsIndex(signal)

  const elections = [...index.elections].sort(
    (a, b) => a.election_year - b.election_year
  )

  const results = await Promise.all(
    elections.map(async election => {
      const year = election.election_year

      const [statistics, profiles] = await Promise.all([
        getNationalStatistics(year, signal),
        getElectionProfiles(year, signal)
      ])

      const supportedProfiles = profiles.filter(
        profile =>
          profile.status === 'supported' &&
          profile.segments > 0
      )

      return {
        year,
        statistics,
        supportedProfiles
      }
    })
  )

  return {
    mode: 'real',

    source: 'INE · Conteos Censales de Participación Ciudadana',

    updatedAt: null,

    participationDefinition:
      'Participación observada: proporción de votos registrados respecto de los registros con participación especificada. Los registros NS no se consideran abstenciones.',

    distributionDefinition:
      'Cada barra representa la tasa de participación observada de un perfil. Los perfiles son agrupaciones estadísticas definidas mediante reglas. Sus porcentajes son independientes y no deben sumarse.',

    years: elections.map(
      election => election.election_year
    ),

    territories: [
      { code: 'MX', name: 'México' }
    ],

    snapshots: results.map(result => ({
      year: result.year,

      territoryCode: 'MX',

      metrics: {
        participation:
          result.statistics.participation_observed === null
            ? null
            : result.statistics.participation_observed * 100,

        coverage: null,

        nominalList: result.statistics.LN,

        profileCount: result.supportedProfiles.length
      },

      distribution: result.supportedProfiles.map(profile => ({
        id: profile.profile_id,
        name: profile.label,
        percentage:
          profile.participation_observed === null
            ? null
            : profile.participation_observed * 100
      })),

      notes: [
        `Datos nacionales correspondientes a la elección de ${result.year}.`,
        'NS representa registros sin especificación de participación, no abstenciones.',
        'Los perfiles son agrupaciones estadísticas con soporte, no clasificaciones de personas individuales.'
      ]
    }))
  }
}
