
import { useEffect, useState } from 'react'
import { useElectionYear } from '../../context/ElectionYearContext'
import { Profiles } from './Profiles'
import { loadRealProfiles } from './profilesAdapter'
import type { ProfileDataset } from './types'

export function RealProfilesPage() {
  const { year, availableYears, setYear } = useElectionYear()

  const [dataset, setDataset] = useState<ProfileDataset | null>(null)

  const [status, setStatus] = useState<
    'loading' | 'ready' | 'error'
  >('loading')

  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    setStatus('loading')
    setDataset(null)

    loadRealProfiles(year, controller.signal)
      .then(data => {
        if (controller.signal.aborted) return
        setDataset(data)
        setStatus('ready')
      })
      .catch(error => {
        if (controller.signal.aborted) return
        console.error('Error al cargar perfiles:', error)
        setStatus('error')
      })

    return () => controller.abort()
  }, [year, attempt])

  return (
    <>
      <section
        className="dashboard-filters"
        aria-labelledby="profiles-year-title"
      >
        <div>
          <p className="eyebrow">PERFILES POR ELECCIÓN</p>
          <h2 id="profiles-year-title">Año electoral</h2>
          <p>
            Consulta los perfiles descriptivos de cada elección.
          </p>
        </div>

        <div className="dashboard-filter-fields">
          <div>
            <label htmlFor="profiles-year">Año</label>
            <select
              id="profiles-year"
              value={year}
              onChange={event => setYear(Number(event.target.value))}
            >
              {(availableYears.length
                ? availableYears
                : [2024]
              ).map(item => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {(status === 'loading' ||
        (status === 'ready' && dataset?.year !== year)) && (
        <section role="status" className="dashboard-loading">
          <h2>Cargando perfiles de {year}…</h2>
        </section>
      )}

      {status === 'error' && (
        <section role="alert" className="dashboard-error">
          <h2>No se pudieron cargar los perfiles</h2>
          <p>Los datos de {year} no están disponibles.</p>

          <button
            type="button"
            className="profile-button secondary"
            onClick={() => setAttempt(value => value + 1)}
          >
            Reintentar
          </button>
        </section>
      )}

      {status === 'ready' && dataset?.year === year && (
        <Profiles key={year} dataset={dataset} />
      )}
    </>
  )
}
