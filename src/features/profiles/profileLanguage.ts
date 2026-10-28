// Diccionarios conservados: source_dictionaries.json, línea SEXO de cada elección.
export const sexCategoriesByYear: Record<number, readonly string[]> = {
  2009: ['0', '1'], 2012: ['0', '1'], 2015: ['0', '1'],
  2018: ['0', '1'], 2021: ['0', '1'], 2024: ['0', '1', '2'],
}
export const sexLabels: Record<string, string> = { '0': 'Hombres', '1': 'Mujeres', '2': 'No binario' }
export const sectionNames: Record<string, string> = { U: 'Urbana', R: 'Rural', M: 'Mixta' }
export const electionType = (year: number) => [2012, 2018, 2024].includes(year) ? 'presidencial' : 'intermedia'
export function additionalSexNote(year: number) {
  return sexCategoriesByYear[year]?.includes('2')
    ? 'No binario está registrado en la fuente, pero sus pocos registros no permiten una comparación equivalente en estas fichas.'
    : sexCategoriesByYear[year]
      ? 'La fuente de esta elección no incluye un desglose para personas no binarias.'
      : 'Consulta las categorías disponibles en el diccionario de esta elección.'
}
