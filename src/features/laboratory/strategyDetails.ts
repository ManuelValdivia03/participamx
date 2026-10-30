import proposals from '../../../docs/perfiles/propuestas_institucionales.md?raw'
import teamSummary from '../../../docs/perfiles/resumen_estrategias_equipo.md?raw'
import profiles from '../../../docs/perfiles/perfiles_2024.json'
import { formatNumber } from './calculations'
import type { Strategy } from './types'

export type DetailSection = { id: string; title: string; paragraphs: string[] }
export type StrategyDetail = {
  strategy: Strategy
  profileId: string
  profileName: string
  statistics: [string, string][]
  sections: DetailSection[]
}

export const proposalNotice = 'Propuesta contextual e hipotética, pendiente de validación institucional. La asociación con un perfil no demuestra una necesidad ni define destinatarios exclusivos. Acceso para toda la ciudadanía. No se han demostrado efectos sobre la participación electoral.'

// El contenido se lee de los documentos existentes: no se mantiene otra copia editorial.
export function plainMarkdown(value: string) {
  return value.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/\*\*|`/g, '').trim()
}

function paragraphs(value: string) {
  return value.trim().split(/\r?\n\s*\r?\n/).flatMap(block => {
    if (/^\s*(?:-|\d+\.)\s/m.test(block)) return block.split(/\r?\n/).filter(Boolean).map(line => plainMarkdown(line.replace(/^\s*(?:-|\d+\.)\s+/, '')))
    return [plainMarkdown(block.replace(/\r?\n/g, ' '))]
  }).filter(Boolean)
}

function documentSection(document: string, title: string) {
  const section = document.split(`## ${title}`)[1]?.split(/\r?\n## /)[0]
  if (!section) throw new Error(`Falta la sección documental: ${title}`)
  return paragraphs(section)
}

export function getStrategyDetail(strategy: Strategy): StrategyDetail {
  const block = proposals.split(/\r?\n(?=## \d+\. )/).find(part => part.startsWith('## ') && part.split(/\r?\n/)[0].endsWith(strategy.name))
  if (!block) throw new Error('No se encontró la propuesta documentada.')
  const source = Object.fromEntries([...block.matchAll(/### ([A-K])\. [^\r\n]+\r?\n([\s\S]*?)(?=\r?\n### |\r?\n## |$)/g)].map(match => [match[1], match[2].trim()]))
  for (const key of 'ABCDEFGHIJK') if (!source[key]) throw new Error(`Propuesta incompleta: ${strategy.id}, apartado ${key}`)
  const profileId = source.A.match(/`([^`]+)`/)?.[1]
  const profile = profiles.find(item => item.profile_id === profileId)
  if (!profile) throw new Error('La propuesta requiere un perfil validado de 2024.')
  const stats = profile.statistics
  const statistics: [string, string][] = [
    ['Participación observada · 2024', `${formatNumber(stats.participation_observed * 100, 2)} %`],
    ['Referencia comparable', `${formatNumber(stats.matched_peer_reference * 100, 2)} %`],
    ['Diferencia frente a pares', `${stats.participation_delta > 0 ? '+' : ''}${formatNumber(stats.participation_delta * 100, 2)} pp`],
    ['Lista nominal reportada (LN)', formatNumber(stats.LN)],
    ['Municipios presentes (no exclusivos)', formatNumber(stats.municipalities)],
    ['Segmentos municipio × edad × sexo', formatNumber(stats.segments)],
  ]
  const section = (id: string, title: string, values: string[]): DetailSection => ({ id, title, paragraphs: values })
  const indicators = source.H.split(/\r?\n/).filter(line => line.startsWith('|')).slice(2).map(line => {
    const [name, measure, method, evidence] = line.split('|').slice(1, -1).map(plainMarkdown)
    return `${name}. Qué mide: ${measure}. Método: ${method}. Evidencia necesaria: ${evidence}.`
  })
  return {
    strategy, profileId: profile.profile_id, profileName: profile.public_name, statistics,
    sections: [
      section('description', 'Nombre y descripción', [strategy.description]),
      section('profile', 'Perfil ciudadano relacionado', [profile.public_name, profile.summary]),
      section('statistics', 'Datos estadísticos del perfil · 2024', statistics.map(([label, value]) => `${label}: ${value}`)),
      section('question', 'Problemática o necesidad por investigar', paragraphs(source.C)),
      section('justification', 'Justificación y relación contextual con el perfil', paragraphs(source.B)),
      section('objective', 'Objetivo institucional', paragraphs(source.D)),
      section('proposal', 'Descripción detallada de la propuesta', paragraphs(source.E)),
      section('activities', 'Actividades de implementación', paragraphs(source.F)),
      section('resources', 'Recursos humanos, tecnológicos y operativos', paragraphs(source.G)),
      section('benefits', 'Beneficios potenciales para el INE y los OPLE', paragraphs(source.K)),
      section('indicators', 'Indicadores y métodos de evaluación', [...indicators, ...documentSection(proposals, 'Criterios comunes de evaluación')]),
      section('risks', 'Riesgos, limitaciones y validación pendiente', [...paragraphs(source.I), ...documentSection(teamSummary, 'Advertencias esenciales y validación pendiente').filter(value => !value.startsWith('Las cifras proceden') && !value.startsWith('Esta revisión actualiza'))]),
      section('sources', 'Fuentes de datos y alcance metodológico', [
        'Fuente de datos: INE, Conteos Censales de Participación Ciudadana, elección 2024. Fichas validadas: docs/perfiles/perfiles_2024.json.',
        'Desarrollo de la propuesta: docs/perfiles/propuestas_institucionales.md, apartados A–K. Síntesis y validación pendiente: docs/perfiles/resumen_estrategias_equipo.md.',
        profile.methodology.description,
        'Participación = SV/(SV+NV), agregando conteos antes de dividir. Referencia ponderada de la misma elección, banda y sexo. pp significa puntos porcentuales. NS no equivale a abstención; LN no representa personas únicas validadas. Los municipios pueden estar presentes en varios perfiles.',
        'Son categorías descriptivas por reglas, sin inferencias causales ni necesidades individuales demostradas. El contexto corresponde exclusivamente a 2024. No hay líneas base, costos ni metas oficiales para estas propuestas.',
        proposalNotice,
      ]),
    ],
  }
}
