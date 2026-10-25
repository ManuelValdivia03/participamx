
import { useEffect, useState } from 'react'

import {
  getMunicipalityProfiles,
  type MunicipalityProfile
} from '../../services/municipalityProfiles'

type Props = {
  year: string
  stateCode: string
  ineCode: string | null
}

const labels: Record<string, string> = {
  young_favorable: '18–34 años · por encima de sus pares',
  young_unfavorable: '18–34 años · por debajo de sus pares',
  adult_favorable: '35–59 años · por encima de sus pares',
  adult_unfavorable: '35–59 años · por debajo de sus pares',
  older_favorable: '60–100 años · por encima de sus pares',
  older_unfavorable: '60–100 años · por debajo de sus pares'
}

const order = Object.keys(labels)

function percentage(value: number | null): string {
  return value === null
    ? 'Sin información'
    : `${(value * 100).toFixed(2)} %`
}

function difference(value: number | null): string {
  if (value === null) return 'Sin información'

  const points = value * 100
  const sign = points > 0 ? '+' : ''

  return `${sign}${points.toFixed(2)} pp`
}

function count(value: number | null): string {
  return value === null
    ? 'Sin información'
    : value.toLocaleString('es-MX')
}

export function MunicipalityProfiles({
  year,
  stateCode,
  ineCode
}: Props) {
  const [attempt, setAttempt] = useState(0)

  const [result, setResult] = useState<{
    key: string
    status: 'loading' | 'ready' | 'error'
    profiles: MunicipalityProfile[]
  } | null>(null)

  const key = `${year}:${stateCode}:${ineCode ?? ''}`

  const validCode =
    ineCode !== null &&
    /^\d{5}$/.test(ineCode) &&
    ineCode.startsWith(stateCode)

  useEffect(() => {
    if (!validCode || !ineCode) return

    const controller = new AbortController()

    setResult({
      key,
      status: 'loading',
      profiles: []
    })

    getMunicipalityProfiles(
      Number(year),
      stateCode,
      controller.signal
    )
      .then(data => {
        if (controller.signal.aborted) return

        const municipalCode = ineCode.slice(2)

        const profiles = data
          .filter(item =>
            item.municipality_code === municipalCode
          )
          .sort(
            (a, b) =>
              order.indexOf(a.profile_id) -
              order.indexOf(b.profile_id)
          )

        setResult({
          key,
          status: 'ready',
          profiles
        })
      })
      .catch(error => {
        if (controller.signal.aborted) return

        console.error('Error al cargar perfiles municipales:', error)

        setResult({
          key,
          status: 'error',
          profiles: []
        })
      })

    return () => controller.abort()
  }, [key, year, stateCode, ineCode, validCode, attempt])

  if (!validCode) {
    return (
      <section className="territory-indicator">
        <span>Perfiles municipales</span>
        <p>Correspondencia territorial pendiente.</p>
      </section>
    )
  }

  const active = result?.key === key ? result : null

  if (!active || active.status === 'loading') {
    return (
      <section className="territory-indicator" role="status">
        <span>Perfiles municipales · {year}</span>
        <p>Cargando perfiles…</p>
      </section>
    )
  }

  if (active.status === 'error') {
    return (
      <section className="territory-indicator" role="alert">
        <span>Perfiles municipales · {year}</span>
        <p>No se pudieron cargar los datos.</p>

        <button
          type="button"
          className="profile-button secondary"
          onClick={() => setAttempt(value => value + 1)}
        >
          Reintentar
        </button>
      </section>
    )
  }

  if (active.profiles.length === 0) {
    return (
      <section className="territory-indicator">
        <span>Perfiles municipales · {year}</span>
        <p>No hay segmentos con perfil disponible para este territorio.</p>
      </section>
    )
  }

  return (
    <section aria-label={`Perfiles municipales de ${year}`}>
      <h3>Perfiles municipales · {year}</h3>

      <p className="territory-disclaimer">
        Se encontraron {active.profiles.length} perfiles con
        segmentos en este municipio. No son clasificaciones
        exclusivas del territorio.
      </p>

      {active.profiles.map(profile => (
        <div
          className="territory-indicator"
          key={profile.profile_id}
        >
          <span>
            {labels[profile.profile_id] ?? profile.profile_id}
          </span>

          <p>
            Participación de los segmentos:{' '}
            {percentage(profile.participation_observed)}
          </p>

          <p>
            Referencia de pares:{' '}
            {percentage(profile.matched_peer_reference)}
          </p>

          <p>
            Diferencia relativa:{' '}
            {difference(profile.relative_turnout)}
          </p>

          <p>
            Segmentos: {count(profile.segments)}
          </p>

          <p>
            Lista nominal: {count(profile.LN)}
          </p>

          {profile.has_low_support && (
            <p>Advertencia: soporte estadístico reducido.</p>
          )}

          {profile.has_high_ns && (
            <p>Advertencia: proporción elevada de NS.</p>
          )}
        </div>
      ))}

      <p className="territory-disclaimer">
        Los perfiles representan segmentos agregados.
        Un mismo municipio puede contener varios.
        Las referencias dependen de la elección, edad y sexo.
        No se deben sumar sus tasas ni interpretar
        diferencias entre elecciones como cambios
        del comportamiento de personas individuales.
      </p>
    </section>
  )
}
