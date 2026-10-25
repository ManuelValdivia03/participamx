
import { useEffect, useState } from 'react'
import {
  getMunicipalStatistics,
  type MunicipalStatistics
} from '../../services/electionData'

type MunicipalElectionSummaryProps = {
  year: string
  ineCode: string | null
}

export function MunicipalElectionSummary({
  year,
  ineCode
}: MunicipalElectionSummaryProps) {
  const [result, setResult] = useState<{
    key: string
    municipality: MunicipalStatistics | null
  } | null>(null)

  const [failedKey, setFailedKey] = useState<string | null>(null)

  const key = `${year}:${ineCode ?? ''}`

  useEffect(() => {
    if (year !== '2024' || !ineCode) return

    const controller = new AbortController()

    getMunicipalStatistics(2024, controller.signal)
      .then(data => {
        if (controller.signal.aborted) return

        const municipality = data.find(
          item =>
            item.state_code + item.municipality_code === ineCode
        ) ?? null

        setResult({
          key: `${year}:${ineCode}`,
          municipality
        })

        setFailedKey(null)
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setFailedKey(`${year}:${ineCode}`)
        }
      })

    return () => controller.abort()
  }, [year, ineCode])

  if (!ineCode) {
    return (
      <div className="territory-indicator">
        <span>Indicadores municipales</span>
        <p>
          No existe una correspondencia INE validada
          para este municipio y año.
        </p>
      </div>
    )
  }

  if (year !== '2024') {
    return (
      <div className="territory-indicator">
        <span>Indicadores municipales</span>
        <p>
          Los datos municipales de este año todavía
          no están integrados.
        </p>
      </div>
    )
  }

  if (failedKey === key) {
    return (
      <div className="territory-indicator" role="alert">
        <p>No se pudieron cargar los indicadores municipales.</p>
      </div>
    )
  }

  if (!result || result.key !== key) {
    return (
      <div className="territory-indicator" role="status">
        <p>Cargando indicadores municipales…</p>
      </div>
    )
  }

  const municipality = result.municipality

  if (!municipality) {
    return (
      <div className="territory-indicator">
        <p>No hay estadísticas para esta clave INE.</p>
      </div>
    )
  }

  const participation =
    municipality.participation_observed === null
      ? 'Sin información'
      : `${(municipality.participation_observed * 100).toFixed(1)}%`

  const nominalList =
    municipality.LN === null
      ? 'Sin información'
      : new Intl.NumberFormat('es-MX').format(municipality.LN)

  return (
    <div>
      <div className="territory-indicator">
        <span>Participación electoral municipal · {year}</span>
        <strong>{participation}</strong>
        <p>Participación observada</p>
      </div>

      <div className="territory-indicator">
        <span>Lista nominal municipal</span>
        <strong>{nominalList}</strong>
        <p>Registros reportados para este municipio</p>
      </div>

      <p className="territory-disclaimer">
        Datos municipales vinculados mediante la clave INE.
        Los registros NS no se consideran abstenciones.
      </p>
    </div>
  )
}
