
import { useEffect, useState } from 'react'
import {
  getStatesStatistics,
  type StateStatistics
} from '../../services/electionData'

type StateElectionSummaryProps = {
  year: number
  stateCode: string
}

export function StateElectionSummary({
  year,
  stateCode
}: StateElectionSummaryProps) {
  const [states, setStates] = useState<StateStatistics[]>([])
  const [status, setStatus] = useState<
    'loading' | 'ready' | 'error'
  >('loading')

  useEffect(() => {
    const controller = new AbortController()

    setStatus('loading')

    getStatesStatistics(year, controller.signal)
      .then(data => {
        if (controller.signal.aborted) return

        setStates(data)
        setStatus('ready')
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setStatus('error')
        }
      })

    return () => controller.abort()
  }, [year])

  if (!stateCode) {
    return (
      <div className="territory-indicator">
        <span>Indicadores electorales</span>
        <p>
          Selecciona una entidad federativa para consultar
          sus estadísticas.
        </p>
      </div>
    )
  }

  if (status === 'loading') {
    return (
      <div className="territory-indicator" role="status">
        <p>Cargando estadísticas electorales…</p>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="territory-indicator" role="alert">
        <p>No se pudieron cargar las estadísticas estatales.</p>
      </div>
    )
  }

  const state = states.find(
    item => item.state_code === stateCode
  )

  if (!state) {
    return (
      <div className="territory-indicator">
        <p>No hay estadísticas disponibles para esta entidad.</p>
      </div>
    )
  }

  const participation =
    state.participation_observed === null
      ? 'Sin información'
      : `${(state.participation_observed * 100).toFixed(1)}%`

  const nominalList = new Intl.NumberFormat('es-MX').format(
    state.LN
  )

  return (
    <div>
      <div className="territory-indicator">
        <span>Participación electoral estatal · {year}</span>
        <strong>{participation}</strong>
        <p>Participación observada</p>
      </div>

      <div className="territory-indicator">
        <span>Lista nominal estatal</span>
        <strong>{nominalList}</strong>
        <p>Registros reportados para esta entidad</p>
      </div>

      <p className="territory-disclaimer">
        Indicadores correspondientes a la entidad federativa,
        no al municipio. Los registros NS no se consideran
        abstenciones.
      </p>
    </div>
  )
}
