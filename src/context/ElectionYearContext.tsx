
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from 'react'

import { getElectionsIndex } from '../services/electionData'

type ElectionYearContextValue = {
  year: number
  setYear: (year: number) => void
  availableYears: number[]
}

const ElectionYearContext =
  createContext<ElectionYearContextValue | null>(null)

export function ElectionYearProvider({
  children
}: {
  children: ReactNode
}) {
  const [year, setYear] = useState(2024)
  const [availableYears, setAvailableYears] = useState<number[]>([])

  useEffect(() => {
    const controller = new AbortController()

    getElectionsIndex(controller.signal)
      .then(index => {
        if (controller.signal.aborted) return

        const years = index.elections
          .map(election => election.election_year)
          .sort((a, b) => a - b)

        setAvailableYears(years)
        setYear(current => years.includes(current) ? current : index.default_election_year)
      })
      .catch(error => {
        if (!controller.signal.aborted) {
          console.error(
            'No se pudo cargar el índice electoral:',
            error
          )
        }
      })

    return () => controller.abort()
  }, [])

  const value = useMemo(
    () => ({
      year,
      setYear,
      availableYears
    }),
    [year, availableYears]
  )

  return (
    <ElectionYearContext.Provider value={value}>
      {children}
    </ElectionYearContext.Provider>
  )
}

export function useElectionYear() {
  const context = useContext(ElectionYearContext)

  if (!context) {
    throw new Error(
      'useElectionYear debe utilizarse dentro de ElectionYearProvider'
    )
  }

  return context
}
