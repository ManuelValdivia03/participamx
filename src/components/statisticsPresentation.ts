// Sólo presentación: recibe porcentajes originales, nunca valores ya redondeados.
export function describeObservedParticipation(percentage: number | null | undefined) {
  if (percentage == null || !Number.isFinite(percentage) || percentage < 0 || percentage > 100) return 'No hay una tasa disponible para esta selección; no equivale a participación cero.'
  const approximate = Math.round(percentage)
  return `De cada 100 registros con condición de voto especificada, aproximadamente ${approximate} ${approximate === 1 ? 'registró' : 'registraron'} participación.`
}

export const percentagePointsHelp = 'pp = puntos porcentuales. Expresan una resta entre porcentajes: 60 % menos 55 % son 5 pp, no un aumento del 5 %.'
export const comparableReferenceHelp = 'La referencia comparable es el valor nacional de la misma elección, grupo de edad y sexo utilizado para comparar estos grupos. No es una predicción ni un promedio histórico.'
export const countDefinitions = [
  ['LN', 'Lista nominal', 'Conteo nominal reportado en los cuadernillos disponibles; no es un conteo validado de personas únicas.'],
  ['SV', 'Registros con participación', 'Registros cuya condición de voto especifica que participaron.'],
  ['NV', 'Registros sin participación', 'Registros cuya condición de voto especifica que no participaron.'],
  ['NS', 'Registros con condición de voto no especificada', 'Su condición de voto no se conoce. No se convierten automáticamente en abstención.'],
] as const
