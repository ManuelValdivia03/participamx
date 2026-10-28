import { createContext, useContext, useState, type ReactNode } from 'react'

function useSelectionState() {
  const [comparisonIds, setComparisonIds] = useState<string[]>([])
  const [detailId, setDetailId] = useState<string | null>(null)
  const [view, setView] = useState('summary')
  const [measure, setMeasure] = useState('participation')
  return { comparisonIds, setComparisonIds, detailId, setDetailId, view, setView, measure, setMeasure }
}
const ProfileInteraction = createContext<ReturnType<typeof useSelectionState> | null>(null)

export function ProfileInteractionProvider({ children }: { children: ReactNode }) {
  const selection = useSelectionState()
  return <ProfileInteraction.Provider value={selection}>{children}</ProfileInteraction.Provider>
}

export function useProfileInteraction() {
  const shared = useContext(ProfileInteraction)
  const local = useSelectionState()
  return shared ?? local
}
