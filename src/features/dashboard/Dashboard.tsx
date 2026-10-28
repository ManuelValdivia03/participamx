import { useEffect, useMemo, useState } from 'react'
import { Icon } from '../../components/Icon'
import { CivicArt } from '../../components/CivicArt'
import { SectionCard } from '../../components/SectionCard'
import { TrendChart } from './TrendChart'
import { dashboardNumber, type DashboardDataset } from './types'
import { loadFullDashboard } from './fullDashboardAdapter'
import { useElectionYear } from '../../context/ElectionYearContext'
import { NationalAgeSex } from './NationalAgeSex'
import { StatisticalHelp } from '../../components/StatisticalHelp'
import { describeObservedParticipation } from '../../components/statisticsPresentation'
import { profileNames } from '../profiles/profilePresentation'
import { ElectionSelector } from '../../components/ElectionSelector'
import { StateSearch } from '../../components/StateSearch'

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
        setTerritoryCode(current => data.territories.some(item => item.code === current) ? current : data.territories[0]?.code ?? 'MX')
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
      label: 'Participación observada',
      value: snapshot?.metrics.participation,
      suffix: '%',
      note: describeObservedParticipation(snapshot?.metrics.participation)
    },
    {
      label: demo ? 'Cobertura de información' : 'Lista nominal con soporte',
      value: snapshot?.metrics.coverage,
      suffix: '%',
      note: snapshot?.metrics.coverage == null ? 'Este indicador no está publicado para la selección actual.' : 'Proporción de lista nominal en segmentos con soporte para los perfiles; no es una tasa de participación.'
    },
    {
      label: 'Lista nominal',
      value: snapshot?.metrics.nominalList,
      suffix: '',
      note: 'Conteo nominal reportado en los cuadernillos disponibles (LN); no identifica personas únicas validadas.'
    },
    {
      label: 'Perfiles descriptivos',
      value: snapshot?.metrics.profileCount,
      suffix: '',
      note: 'Categorías por reglas de edad y participación relativa; no son tipos de personas.'
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
            className="dashboard-filters dashboard-controls-unified"
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

            <div className="dashboard-unified-controls">
              <StateSearch options={dataset.territories} value={territoryCode} onChange={setTerritoryCode} />
              <ElectionSelector year={year} onChange={setYear} />

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
              title={demo ? 'Distribución por perfiles' : territoryCode === 'MX' ? 'Participación por perfil' : 'Lista nominal por perfil'}
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
                          <span>{!demo ? profileNames[item.id] ?? item.name : item.name}</span>
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

              {!demo && (
                <NationalAgeSex year={year} territoryCode={territoryCode} territoryName={territory?.name ?? ''} />
              )}
          <div className="dashboard-footnotes">
            <h2>Cómo leer esta vista</h2>

            <p>
              La cobertura de información y la participación son
              indicadores distintos. “Sin información” indica un
              valor no disponible; un cero solo se muestra si fue
              entregado como tal.
            </p>

            <StatisticalHelp />

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
