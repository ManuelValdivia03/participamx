export type Strategy = {
  id: string
  name: string
  description: string
  purpose: string
  component: string
  unit: string
  resources: string[]
  contribution: string
  indicators: string[]
  limitations: string[]
}

export type ScenarioDraft = {
  name: string
  strategyId: string
  budget: string
  unitCost: string
  plannedUnits: string
  operationalCapacity: string
  assumptions: string
}

export type SavedScenario = ScenarioDraft & { id: string; createdAt: string }

export type ScenarioMetrics = {
  budget: number | null
  unitCost: number | null
  plannedUnits: number | null
  operationalCapacity: number | null
  projectedCost: number | null
  budgetPercent: number | null
  remainingBudget: number | null
  theoreticalCapacity: number | null
  feasibleCapacity: number | null
  resourceDifference: number | null
  errors: string[]
}
