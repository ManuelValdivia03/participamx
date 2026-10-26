
import { useEffect, useRef } from 'react'

import {
  formatProfileMetric,
  profileMetrics,
  realProfileMetrics,
  type CitizenProfile,
  type ProfileDataset
} from './types'

function formatRealMetric(
  value: number | null | undefined,
  key: string,
  suffix: string
): string {
  if (value === null || value === undefined) {
    return 'Sin información'
  }

  const isPercentage = suffix === '%' || suffix === ' pp'

  const formatter = new Intl.NumberFormat('es-MX', {
    minimumFractionDigits: isPercentage ? 2 : 0,
    maximumFractionDigits: isPercentage ? 2 : 0
  })

  if (key === 'participationDelta') {
    const sign = value > 0 ? '+' : value < 0 ? '-' : ''
    return `${sign}${formatter.format(Math.abs(value))} pp`
  }

  return `${formatter.format(value)}${suffix}`
}

export function ProfileDetail({
  profile,
  dataset,
  onClose
}: {
  profile: CitizenProfile
  dataset: ProfileDataset
  onClose: () => void
}) {
  const heading = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    heading.current?.focus()
  }, [profile.id])

  const metrics =
    dataset.mode === 'real'
      ? realProfileMetrics
      : profileMetrics

  return (
    <section
      className="profile-detail"
      aria-labelledby="profile-detail-title"
    >
      <header className="profile-detail-heading">
        <div>
          <p className="eyebrow">
            FICHA DEL PERFIL · {dataset.year}
            {dataset.mode === 'demo' && ' · EJEMPLO FICTICIO'}
          </p>

          <h2
            id="profile-detail-title"
            ref={heading}
            tabIndex={-1}
          >
            {profile.name}
          </h2>
        </div>

        <button
          className="profile-button secondary"
          onClick={onClose}
        >
          Cerrar ficha
        </button>
      </header>

      <p className="profile-description">
        {profile.description}
      </p>

      <dl className="profile-metric-grid">
        {metrics.map(metric => (
          <div key={metric.key}>
            <dt>{metric.label}</dt>

            <dd>
              {dataset.mode === 'real'
                ? formatRealMetric(
                    profile[metric.key],
                    metric.key,
                    metric.suffix
                  )
                : formatProfileMetric(
                    profile[metric.key],
                    metric.suffix
                  )}
            </dd>
          </div>
        ))}
      </dl>

      <div className="profile-detail-columns">
        <section>
          <h3>Características</h3>

          <ul>
            {profile.characteristics.map(item => (
              <li key={item}>{item}</li>
            ))}
          </ul>

          {!profile.characteristics.length && (
            <p>Características pendientes de entrega.</p>
          )}
        </section>

        <section>
          <h3>
            {dataset.mode === 'demo'
              ? 'Acciones ilustrativas'
              : 'Estrategias cívicas'}
          </h3>

          <ul>
            {profile.strategies.map(item => (
              <li key={item}>{item}</li>
            ))}
          </ul>

          {!profile.strategies.length && (
            <p>Estrategias pendientes de entrega.</p>
          )}
        </section>
      </div>

      <section className="profile-limitations">
        <h3>Alcance y limitaciones</h3>

        <ul>
          {profile.limitations.map(item => (
            <li key={item}>{item}</li>
          ))}
        </ul>

        <p>{dataset.participationDefinition}</p>
      </section>

      <p className="profile-source">
        Fuente: {dataset.source}
        {dataset.updatedAt &&
          ` · Actualización: ${dataset.updatedAt}`}
      </p>
    </section>
  )
}
