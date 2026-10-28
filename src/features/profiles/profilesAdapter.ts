
import {
  getElectionProfiles
} from '../../services/electionData'

import type {
  CitizenProfile,
  ProfileDataset
} from './types'
import { enrichProfiles, validateProfileEnrichment } from './profileEnrichment'
import { profileNames } from './profilePresentation'

export async function loadRealProfiles(
  year: number,
  signal?: AbortSignal
): Promise<ProfileDataset> {
  const data = await getElectionProfiles(year, signal)

  const supportedProfiles = data.filter(
    profile =>
      profile.status === 'supported' &&
      profile.segments > 0
  )

  const profiles: CitizenProfile[] = supportedProfiles.map(
    profile => {
      const participation =
        profile.participation_observed === null
          ? null
          : profile.participation_observed * 100

      const peerReference =
        profile.matched_peer_reference === null
          ? null
          : profile.matched_peer_reference * 100

      const participationDelta =
        profile.participation_delta === null
          ? null
          : profile.participation_delta * 100

      return {
        id: profile.profile_id,
        name: profileNames[profile.profile_id] ?? profile.label,
        ageBand: profile.age_band,

        summary:
          `Perfil estadístico del grupo de ${profile.age_band} años, ` +
          `definido mediante reglas de comparación con sus pares.`,

        description:
          `Este perfil reúne segmentos agregados de la elección de ${year}. ` +
          `Su clasificación depende de la diferencia de participación ` +
          `respecto a grupos comparables de la misma elección, edad y sexo.`,

        participation,
        peerReference,
        participationDelta,

        segmentCount: profile.segments,
        municipalityCount: profile.municipalities,
        nominalList: profile.LN,

        coverage:
          profile.nominal_coverage === null
            ? null
            : profile.nominal_coverage * 100,

        // El archivo no proporciona edad mediana.
        medianAge: null,

        characteristics: [
          `Grupo de edad: ${profile.age_band} años.`,
          `Segmentos con soporte: ${profile.segments.toLocaleString('es-MX')}.`,
          `Municipios asociados: ${profile.municipalities.toLocaleString('es-MX')}.`
        ],

        // No inventamos estrategias que no están en el JSON.
        strategies: [],

        limitations: [
          'Es una agrupación de segmentos estadísticos, no de personas individuales.',
          'Un municipio puede contener segmentos de varios perfiles.',
          'La cobertura corresponde a la proporción de lista nominal nacional asociada al perfil.',
          'Las diferencias de participación son descriptivas y no demuestran causas.',
          ...(participationDelta !== null &&
          Math.abs(participationDelta) <= 2
            ? [
                'La diferencia está dentro de ±2 puntos porcentuales de la referencia y requiere cautela.'
              ]
            : [])
        ]
      }
    }
  )

  let enrichment: ProfileDataset['enrichment'] = null
  let enrichmentStatus: ProfileDataset['enrichmentStatus'] = 'error'
  let activeProfiles = profiles
  {
    try {
      const response = await fetch(`${import.meta.env.BASE_URL}data/profiles/enriched-${year}.json`, { signal })
      if (!response.ok) throw new Error('No se pudo cargar la caracterización ampliada')
      const candidate = validateProfileEnrichment(await response.json(), year)
      activeProfiles = enrichProfiles(profiles, candidate, year)
      enrichment = candidate
      enrichmentStatus = 'ready'
    } catch (error) {
      if (signal?.aborted) throw error
      // V1 permanece disponible, sin mostrar datos ampliados de otra población o elección.
      enrichmentStatus = 'error'
    }
  }
  return {
    mode: 'real',

    year,

    source:
      'INE · Conteos Censales de Participación Ciudadana. ' +
      'Perfiles descriptivos por reglas de ParticipaMX.',

    updatedAt: null,

    participationDefinition:
      'Participación observada = SV / (SV + NV). ' +
      'La referencia se calcula con grupos comparables de la misma elección, edad y sexo. ' +
      'Las diferencias se expresan en puntos porcentuales. ' +
      'NS significa condición de voto no especificada, no abstención.',

    profiles: activeProfiles,
    enrichment,
    enrichmentStatus
  }
}
