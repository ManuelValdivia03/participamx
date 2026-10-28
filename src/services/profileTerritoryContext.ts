import { getElectionsIndex } from './electionData'
import { profileNames } from '../features/profiles/profilePresentation'
import type { StateOption } from '../components/StateSearch'

export type StateProfileContext = { election_year: number; state_code: string; profile_id: string; LN: number; SV: number; NV: number; NS: number; specified_count: number; segments: number; participation_observed: number | null; matched_peer_reference: number | null; relative_turnout: number | null; share_of_territorial_LN: number | null; has_low_support: boolean }
async function resource(path: string, year: number, signal?: AbortSignal) {
  const response = await fetch(`${import.meta.env.BASE_URL}data/participamx_multiyear/${path}`, { signal })
  if (!response.ok) throw new Error('Contexto territorial no disponible')
  const data = await response.json()
  if (data.schema_version !== '2.0.0' || data.election_year !== year || data.rate_unit !== 'proportion' || !Array.isArray(data.data)) throw new Error('Contexto de otra elección o contrato inválido')
  return data.data
}
export async function getProfileStateOptions(year: number, signal?: AbortSignal): Promise<StateOption[]> {
  const index = await getElectionsIndex(signal), election = index.elections.find(e => e.election_year === year)
  if (!election) throw new Error('Elección no disponible')
  const rows = await resource(election.states_path, year, signal)
  const states = rows.map((r: { state_code: string; state_name: string }) => ({ code: String(r.state_code).padStart(2, '0'), name: r.state_name }))
  if (states.length !== 32 || new Set(states.map((r: StateOption) => r.code)).size !== 32 || states.some((r: StateOption) => !/^(0[1-9]|[12]\d|3[0-2])$/.test(r.code) || typeof r.name !== 'string')) throw new Error('Catálogo estatal inválido')
  return [{ code: 'MX', name: 'México' }, ...states.sort((a: StateOption, b: StateOption) => a.name.localeCompare(b.name, 'es'))]
}
export function validateStateProfileContext(rows: unknown[], year: number, state: string): StateProfileContext[] {
  const selected = (rows as StateProfileContext[]).filter(r => String(r.state_code).padStart(2, '0') === state)
  if (!selected.length || new Set(selected.map(r => r.profile_id)).size !== selected.length) throw new Error('No hay contexto estatal válido')
  for (const r of selected) {
    if (r.election_year !== year || !Object.hasOwn(profileNames, r.profile_id) || !['LN','SV','NV','NS','specified_count','segments'].every(k => Number.isSafeInteger(r[k as keyof StateProfileContext]) && Number(r[k as keyof StateProfileContext]) >= 0) || r.LN !== r.SV + r.NV + r.NS || r.specified_count !== r.SV + r.NV) throw new Error('Conteos de contexto inválidos')
    for (const rate of [r.participation_observed, r.matched_peer_reference, r.share_of_territorial_LN]) if (rate !== null && (!Number.isFinite(rate) || rate < 0 || rate > 1)) throw new Error('Tasa estatal inválida')
    if (r.specified_count === 0 ? r.participation_observed !== null : r.participation_observed === null || Math.abs(r.participation_observed - r.SV / r.specified_count) > 1e-10) throw new Error('Denominador estatal inválido')
    if (typeof r.has_low_support !== 'boolean' || (r.participation_observed !== null && r.matched_peer_reference !== null ? r.relative_turnout === null || !Number.isFinite(r.relative_turnout) || Math.abs(r.relative_turnout - (r.participation_observed-r.matched_peer_reference))>1e-10 : r.relative_turnout !== null)) throw new Error('Referencia estatal inválida')
  }
  return selected
}
export async function getProfileStateContext(year: number, state: string, signal?: AbortSignal) {
  const index = await getElectionsIndex(signal), election = index.elections.find(e => e.election_year === year)
  if (!election) throw new Error('Elección no disponible')
  return validateStateProfileContext(await resource(`${election.base_path}state_profiles.json`, year, signal), year, state)
}
