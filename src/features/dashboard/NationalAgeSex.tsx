
import { useEffect, useMemo, useState } from 'react'
import { SectionCard } from '../../components/SectionCard'
import { getElectionsIndex } from '../../services/electionData'
import { getTerritorySummary } from '../../services/territorialDemographics'

type AgeRow = {
  election_year: number
  exact_age?: number
  age_band?: string
  sex_code: string
  LN: number
  SV: number
  NV: number
  has_low_support: boolean
}

type AgeResource = {
  schema_version: string
  election_year: number
  rate_unit: string
  data: AgeRow[]
}

type SexOption = 'all' | '0' | '1' | '2'

const cache = new Map<string, AgeRow[]>()

const bands = [
  { label: '18–34 años', min: 18, max: 34 },
  { label: '35–59 años', min: 35, max: 59 },
  { label: '60–100 años', min: 60, max: 100 }
]

function formatCount(value: number | null) {
  return value === null
    ? 'No registrado'
    : value.toLocaleString('es-MX')
}

function formatRate(value: number | null) {
  return value === null
    ? 'No registrado'
    : `${(value * 100).toFixed(2)} %`
}

export function NationalAgeSex({ year, territoryCode = 'MX', territoryName = 'México' }: { year: number; territoryCode?: string; territoryName?: string }) {
  const [sex, setSex] = useState<SexOption>('all')
  const [retry, setRetry] = useState(0)

  const [resource, setResource] = useState<{
    key: string
    status: 'loading' | 'ready' | 'error'
    rows: AgeRow[]
  } | null>(null)
  const key = `${year}:${territoryCode}`

  useEffect(() => {
    const controller = new AbortController()

    setResource({
      key,
      status: 'loading',
      rows: []
    })

    async function load() {
      const cached = cache.get(key)

      if (cached) return cached
      if (territoryCode !== 'MX') {
        const summary = await getTerritorySummary(year, territoryCode, controller.signal)
        const rows = [...summary.segments, ...summary.complementary].map(row => ({ election_year: year, age_band: row.age_band, sex_code: row.sex_code, LN: row.LN, SV: row.SV, NV: row.NV, has_low_support: !row.sufficient_support }))
        controller.signal.throwIfAborted(); cache.set(key, rows); return rows
      }

      const index = await getElectionsIndex(controller.signal)

      const election = index.elections.find(
        item => item.election_year === year
      )

      if (!election) {
        throw new Error(`Elección ${year} no disponible`)
      }

      const url =
        `${import.meta.env.BASE_URL}data/participamx_multiyear/` +
        `${election.base_path}age_statistics.json`

      const response = await fetch(url, {
        signal: controller.signal
      })

      if (!response.ok) {
        throw new Error(`Error al cargar edades de ${year}`)
      }

      const data: AgeResource = await response.json()

      if (
        data.schema_version !== '2.0.0' ||
        data.election_year !== year ||
        data.rate_unit !== 'proportion' ||
        !Array.isArray(data.data) ||
        !data.data.every(row =>
          row.election_year === year &&
          Number.isInteger(row.exact_age) &&
          typeof row.sex_code === 'string' &&
          Number.isFinite(row.LN) &&
          Number.isFinite(row.SV) &&
          Number.isFinite(row.NV)
        )
      ) {
        throw new Error('Formato de edades inválido')
      }

      if (!controller.signal.aborted) {
        cache.set(key, data.data)
      }

      return data.data
    }

    load()
      .then(rows => {
        if (controller.signal.aborted) return

        setResource({
          key,
          status: 'ready',
          rows
        })
      })
      .catch(error => {
        if (controller.signal.aborted) return

        console.error('Error en datos por edad y sexo:', error)

        setResource({
          key,
          status: 'error',
          rows: []
        })
      })

    return () => controller.abort()
  }, [year, territoryCode, retry, key])

  const active =
    resource?.key === key ? resource : null

  const results = useMemo(() => {
    if (!active || active.status !== 'ready') {
      return []
    }

    return bands.map(band => {
      const selectedRows = active.rows.filter(
        row =>
          (row.age_band === `${band.min}-${band.max}` || (row.exact_age !== undefined && row.exact_age >= band.min && row.exact_age <= band.max)) &&
          (sex === 'all' || row.sex_code === sex)
      )

      if (selectedRows.length === 0) {
        return {
          label: band.label,
          nominal: null,
          rate: null,
          lowSupport: false
        }
      }

      const totals = selectedRows.reduce(
        (sum, row) => ({
          nominal: sum.nominal + row.LN,
          votes: sum.votes + row.SV,
          nonVotes: sum.nonVotes + row.NV
        }),
        {
          nominal: 0,
          votes: 0,
          nonVotes: 0
        }
      )

      const specified = totals.votes + totals.nonVotes

      return {
        label: band.label,
        nominal: totals.nominal,
        rate:
          specified > 0
            ? totals.votes / specified
            : null,
        lowSupport: selectedRows.some(
          row => row.has_low_support
        )
      }
    })
  }, [active, sex])

  return (
    <SectionCard
      title={territoryCode === 'MX' ? `Participación nacional por edad y sexo · ${year}` : `Participación por edad y sexo · ${territoryName}`}
      subtitle={`${territoryName} · Elección ${year}`}
    >
      <div className="age-sex-toolbar" data-age-territory={territoryCode} data-age-year={year}>
        <div>
          <label htmlFor="age-sex-filter">
            Sexo registrado
          </label>

          <select
            id="age-sex-filter"
            value={sex}
            onChange={event =>
              setSex(event.target.value as SexOption)
            }
          >
            <option value="all">Todos los registros</option>
            <option value="0">Hombres</option>
            <option value="1">Mujeres</option>
            <option value="2">No binario{year !== 2024 ? ' · no registrado en esta elección' : ''}</option>
          </select>
        </div>
      </div>

      {(!active || active.status === 'loading') && (
        <p role="status" className="dashboard-chart-definition">
          Cargando datos de edad y sexo…
        </p>
      )}

      {active?.status === 'error' && (
        <div role="alert" className="dashboard-error">
          <p>No hay desglose disponible para {territoryName} en {year} o no se pudo cargar. No se utilizan datos nacionales como sustituto.</p>
          <button
            type="button"
            className="profile-button secondary"
            onClick={() => setRetry(value => value + 1)}
          >
            Reintentar
          </button>
        </div>
      )}

      {active?.status === 'ready' && (
        <>
          <div className="age-sex-table-wrap">
            <table className="age-sex-table">
              <caption>
                Participación observada y lista nominal
                por grupo de edad
              </caption>

              <thead>
                <tr>
                  <th scope="col">Edad</th>
                  <th scope="col">Participación</th>
                  <th scope="col">Lista nominal</th>
                </tr>
              </thead>

              <tbody>
                {results.map(row => (
                  <tr key={row.label}>
                    <th scope="row">{row.label}</th>
                    <td>
                      {formatRate(row.rate)}
                      {row.lowSupport && ' *'}
                    </td>
                    <td>{formatCount(row.nominal)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {sex === '2' && year !== 2024 && (
            <p className="dashboard-chart-definition">
              La categoría No binario no está registrada
              en esta elección. Su ausencia no significa
              cero personas.
            </p>
          )}

          {sex === '2' && year === 2024 && (
            <p className="dashboard-chart-definition">
              La categoría No binario tiene pocos registros.
              Puede no haber datos en este territorio; una ausencia no equivale a cero personas.
              Las tasas disponibles requieren cautela, especialmente con soporte reducido.
            </p>
          )}

          {results.some(row => row.lowSupport) && (
            <p className="dashboard-chart-definition">
              * El conjunto incluye edades con soporte
              reducido. La tasa agregada es descriptiva
              y requiere cautela.
            </p>
          )}
        </>
      )}

      <p className="dashboard-chart-definition">
        Alcance: {territoryCode === 'MX' ? 'nacional' : territoryName}, elección {year}, edades de 18 a 100 años.
        La participación se calcula como SV / (SV + NV)
        a partir de los conteos, no promediando
        porcentajes. No incluye automáticamente edades
        mayores de 100 años ni permite inferir
        comportamientos individuales.
      </p>
      {territoryCode !== 'MX' && <p className="dashboard-chart-definition">Fuente: resumen estatal validado del Atlas, con soporte evaluado en sus bandas agregadas. La vista nacional conserva su diagnóstico por edad exacta; las alertas de ambos niveles no son equivalentes.</p>}
    </SectionCard>
  )
}
