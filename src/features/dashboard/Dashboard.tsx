import { useEffect, useMemo, useState } from 'react'
import { Icon } from '../../components/Icon'
import { CivicArt } from '../../components/CivicArt'
import { SectionCard } from '../../components/SectionCard'
import { TrendChart } from './TrendChart'
import { dashboardNumber, type DashboardDataset } from './types'
import { loadFullDashboard } from './fullDashboardAdapter'
import { useElectionYear } from '../../context/ElectionYearContext'
import { NationalAgeSex } from './NationalAgeSex'

type DashboardProps = {
  loadDataset?: (signal: AbortSignal) => Promise<DashboardDataset>
}

export function Dashboard({
  loadDataset = loadFullDashboard
}: DashboardProps) {
  const [dataset, setDataset] = useState<DashboardDataset | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [attempt, setAttempt] = useState(0)
  const { year, setYear } = useElectionYear()
  const [territoryCode, setTerritoryCode] = useState('MX')

  useEffect(() => {
    const controller = new AbortController()

    setStatus('loading')
    setDataset(null)

    loadDataset(controller.signal)
      .then(data => {
        if (controller.signal.aborted) return

        setDataset(data)
        setTerritoryCode(
          data.territories.some(item => item.code === 'MX')
            ? 'MX'
            : data.territories[0]?.code ?? ''
        )
        setStatus('ready')
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus('error')
      })

    return () => controller.abort()
  }, [loadDataset, attempt])

  const snapshot = dataset?.snapshots.find(
    item => item.year === year && item.territoryCode === territoryCode
  )

  const territory = dataset?.territories.find(
    item => item.code === territoryCode
  )

  const points = useMemo(
    () =>
      dataset?.years.map(pointYear => ({
        year: pointYear,
        value:
          dataset.snapshots.find(
            item =>
              item.year === pointYear &&
              item.territoryCode === territoryCode
          )?.metrics.participation ?? null
      })) ?? [],
    [dataset, territoryCode]
  )

  const demo = dataset?.mode === 'demo'
  const context = `${territory?.name ?? ''} · ${year}`

  const metrics = [
    {
      label: 'Participación electoral',
      value: snapshot?.metrics.participation,
      suffix: '%',
      note: 'Indicador proporcionado por el análisis'
    },
    {
      label: 'Cobertura de información',
      value: snapshot?.metrics.coverage,
      suffix: '%',
      note: 'Alcance reportado de los registros'
    },
    {
      label: 'Lista nominal',
      value: snapshot?.metrics.nominalList,
      suffix: '',
      note: 'Registros reportados para este corte'
    },
    {
      label: 'Perfiles descriptivos',
      value: snapshot?.metrics.profileCount,
      suffix: '',
      note: 'Agrupaciones entregadas por el análisis'
    }
  ]

  return (
    <>
      <section className="hero dashboard-hero">
        <div>
          <p className="eyebrow">
            OBSERVATORIO DE PARTICIPACIÓN CIUDADANA
          </p>

          <h2>
            La participación
            <br />
            <span>
              tiene muchas
              <br />
              formas.
            </span>
          </h2>

          <p>
            Explora los indicadores de cada territorio y observa
            cómo se presentan a través del tiempo.
          </p>

          <a className="button" href="#mapa">
            Explorar el territorio
          </a>
        </div>

        <CivicArt />
      </section>

      {status === 'loading' && (
        <section
          className="dashboard-loading"
          role="status"
          aria-live="polite"
        >
          <span className="eyebrow">PREPARANDO LA VISTA</span>
          <h2>Cargando indicadores…</h2>
          <p>Estamos preparando el conjunto disponible para consultar.</p>

          <div className="dashboard-skeleton" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
          </div>
        </section>
      )}

      {status === 'error' && (
        <section className="dashboard-error" role="alert">
          <h2>No pudimos cargar los indicadores</h2>
          <p>
            La información no está disponible por el momento.
            Puedes volver a intentarlo.
          </p>

          <button
            className="profile-button secondary"
            onClick={() => setAttempt(value => value + 1)}
          >
            Reintentar carga
          </button>
        </section>
      )}

      {status === 'ready' && dataset && (
        <>
          {demo && (
            <div
              className="profiles-demo-notice dashboard-demo"
              role="note"
            >
              <Icon name="info" />
              <div>
                <strong>
                  Demostración · Cifras y gráficas ficticias
                </strong>
                <p>
                  Estos valores sirven para probar la interfaz.
                  No proceden de los ZIP ni representan resultados electorales.
                  El equipo de análisis entregará los indicadores reales.
                </p>
              </div>
            </div>
          )}

          <section
            className="dashboard-filters"
            aria-labelledby="dashboard-filters-title"
          >
            <div>
              <p className="eyebrow">TU VISTA DE LOS DATOS</p>

              <h2 id="dashboard-filters-title">
                Elige dónde y cuándo
              </h2>

              <p>
                {demo
                  ? 'La demostración incluye México y tres entidades de ejemplo.'
                  : 'Consulta los territorios y años disponibles en la entrega.'}
              </p>
            </div>

            <div className="dashboard-filter-fields">
              <div>
                <label htmlFor="dashboard-territory">
                  Territorio
                </label>

                <select
                  id="dashboard-territory"
                  value={territoryCode}
                  onChange={event =>
                    setTerritoryCode(event.target.value)
                  }
                >
                  {dataset.territories.map(item => (
                    <option key={item.code} value={item.code}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="dashboard-year">Año</label>

                <select
                  id="dashboard-year"
                  value={year}
                  onChange={event =>
                    setYear(Number(event.target.value))
                  }
                >
                  {dataset.years.map(item => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>

              <button
                className="dashboard-reset"
                onClick={() => {
                  setTerritoryCode(
                    dataset.territories.some(item => item.code === 'MX')
                      ? 'MX'
                      : dataset.territories[0]?.code ?? ''
                  )
                  setYear(dataset.years.at(-1) ?? 2024)
                }}
              >
                Restablecer
              </button>
            </div>
          </section>

          <p
            className="dashboard-current"
            role="status"
            aria-live="polite"
          >
            {context}
            {demo && ' · Ejemplo ficticio'}
            {!snapshot && ' · Sin datos en este conjunto'}
          </p>

          {!snapshot && (
            <div className="dashboard-empty dashboard-empty-banner">
              <strong>
                No hay indicadores para esta selección
              </strong>

              <p>
                {demo
                  ? 'La ausencia está incluida para probar la interfaz. No significa que falten datos electorales reales de este territorio.'
                  : 'El conjunto entregado no incluye este año y territorio. Cambia los filtros para consultar otro corte.'}
              </p>
            </div>
          )}

          {snapshot && snapshot.notes.length > 0 && (
            <div className="dashboard-notes">
              {snapshot.notes.map(note => (
                <p key={note}>{note}</p>
              ))}
            </div>
          )}

          <div className="dashboard-metrics">
            {metrics.map((metric, index) => (
              <section
                className="dashboard-metric"
                key={metric.label}
              >
                <span className="metric-index">
                  0{index + 1} / {demo ? 'EJEMPLO' : 'INDICADOR'}
                </span>

                <h2>{metric.label}</h2>

                <p
                  className={`dashboard-metric-value${
                    metric.value === null ||
                    metric.value === undefined
                      ? ' unavailable'
                      : ''
                  }`}
                >
                  {dashboardNumber(metric.value, metric.suffix)}
                </p>

                <p className="dashboard-metric-note">
                  {demo
                    ? 'Valor ficticio · Solo demostración'
                    : metric.note}
                </p>
              </section>
            ))}
          </div>

          <div className="dashboard-charts">
            <SectionCard
              title="Participación a través del tiempo"
              subtitle={`${territory?.name ?? ''}${
                demo ? ' · Serie ficticia' : ''
              }`}
            >
              <TrendChart
                points={points}
                selectedYear={year}
                onSelectYear={setYear}
                demo={!!demo}
              />

              <p className="dashboard-chart-definition">
                {dataset.participationDefinition}
              </p>
            </SectionCard>

            <SectionCard
              title={demo ? 'Distribución por perfiles' : 'Participación por perfil'}
              subtitle={`${context}${
                demo ? ' · Ejemplo ficticio' : ''
              }`}
            >
              {snapshot?.distribution.length ? (
                <>
                  <ul className="dashboard-distribution">
                    {snapshot.distribution.map((item, index) => (
                      <li key={item.id}>
                        <div>
                          <span>{item.name}</span>
                          <strong>
                            {dashboardNumber(item.percentage, '%')}
                          </strong>
                        </div>

                        <div
                          className={`distribution-track distribution-color-${
                            index % 4
                          }`}
                          aria-hidden="true"
                        >
                          {item.percentage !== null && (
                            <span
                              style={{
                                width: `${
                                  Math.max(
                                    0,
                                    Math.min(100, item.percentage)
                                  )
                                }%`
                              }}
                            />
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>

                  <p className="dashboard-chart-definition">
                    {!demo && territoryCode !== 'MX'
                      ? 'Cada barra representa la proporción de lista nominal estatal asociada al perfil. Los perfiles corresponden a segmentos agregados y no describen a todos los habitantes del estado.'
                      : dataset.distributionDefinition}
                  </p>
                </>
              ) : (
                <div className="dashboard-empty">
                  <Icon name="perfiles" />

                  <h3>
                    {demo
                      ? 'Distribución pendiente'
                      : 'Participación por perfiles no disponible'}
                  </h3>

                  <p>
                    {demo
                      ? 'No hay porcentajes de perfiles disponibles para esta selección.'
                      : 'No hay tasas de participación por perfil disponibles para esta selección.'}
                  </p>
                </div>
              )}

              <a
                className="dashboard-text-link"
                href="#perfiles"
              >
                Consultar fichas y comparar perfiles
              </a>
            </SectionCard>
          </div>

              {!demo && territoryCode === 'MX' && (
                <NationalAgeSex year={year} />
              )}
          <div className="dashboard-footnotes">
            <h2>Cómo leer esta vista</h2>

            <p>
              La cobertura de información y la participación son
              indicadores distintos. “Sin información” indica un
              valor no disponible; un cero solo se muestra si fue
              entregado como tal.
            </p>

            <p>
              Fuente: {dataset.source}
              {dataset.updatedAt
                ? ` · Actualización: ${dataset.updatedAt}`
                : ''}
            </p>
          </div>
        </>
      )}
    </>
  )
}
