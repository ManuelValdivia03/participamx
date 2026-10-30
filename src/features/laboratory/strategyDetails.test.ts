import { describe, expect, it } from 'vitest'
import profiles from '../../../docs/perfiles/perfiles_2024.json'
import { strategies } from './strategies'
import { getStrategyDetail } from './strategyDetails'
import { createStrategyPdf, extractPdfText } from './export'

const expectedProfiles = ['young_favorable', 'young_unfavorable', 'adult_favorable', 'adult_unfavorable', 'older_favorable', 'older_unfavorable']

describe('desarrollo documental de las estrategias', () => {
  strategies.forEach((strategy, index) => {
    it(`conserva perfil, cifras y desarrollo completo: ${strategy.id}`, async () => {
      const detail = getStrategyDetail(strategy)
      const profile = profiles.find(item => item.profile_id === expectedProfiles[index])!
      expect(detail.profileId).toBe(profile.profile_id)
      expect(detail.profileName).toBe(profile.public_name)
      expect(detail.statistics.find(([label]) => label.startsWith('Lista nominal'))?.[1]).toBe(new Intl.NumberFormat('es-MX').format(profile.statistics.LN))
      expect(detail.sections).toHaveLength(13)
      expect(detail.sections.every(section => section.paragraphs.length > 0)).toBe(true)
      expect(detail.sections.find(section => section.id === 'activities')?.paragraphs).toHaveLength(4)
      const indicators = detail.sections.find(section => section.id === 'indicators')!.paragraphs
      expect(indicators.filter(value => value.includes('Evidencia necesaria:'))).toHaveLength(4)
      expect(indicators.join(' ')).toContain('denominador vacío')
      const pdfText = (await extractPdfText(createStrategyPdf(strategy))).replace(/\s+/g, ' ')
      expect(pdfText).toContain(strategy.name)
      expect(pdfText).toContain('pendiente de validación institucional')
      expect(pdfText).toContain('Acceso para toda la ciudadanía')
      expect(pdfText).toContain('No se han demostrado efectos sobre la participación electoral')
      expect(pdfText).toContain('perfiles_2024.json')
      expect(pdfText).toContain('Evidencia necesaria:')
      // Comprueba que el PDF llega hasta la última advertencia, tras recursos e indicadores.
      expect(pdfText).toContain('No hay líneas base, costos ni metas oficiales')
      for (const section of detail.sections) expect(pdfText).toContain(section.title.replace(/[–—]/g, '-'))
    })
  })
})
