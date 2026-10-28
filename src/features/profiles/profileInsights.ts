import { count, percent, points } from './profileEnrichment'
import { electionType } from './profileLanguage'
import type { EnrichedProfile, ProfileCrossCell } from './types'

export type ProfileInsight = { id: string; title: string; metric: string; text: string; context: string }
export const closeRateThresholdPp = 1 // Regla editorial, no umbral de significación estadística.
const finite = (v: number | null | undefined): v is number => v != null && Number.isFinite(v)
export const hasComparableRate = (cell: ProfileCrossCell | undefined): cell is ProfileCrossCell & { participation: number } => !!cell && cell.status === 'defined' && finite(cell.participation) && (cell.specifiedCount ?? 0) > 0
const magnitude = (value: number) => points(Math.abs(value)).replace('+', '')

export function profileInsights(data: EnrichedProfile, year: number): ProfileInsight[] {
  const valid = finite(data.participation) && finite(data.reference) && finite(data.deltaPp)
  const delta = data.deltaPp ?? 0
  const women = data.sexCells.find(c => c.code === '1'), men = data.sexCells.find(c => c.code === '0')
  const sexGap = hasComparableRate(women) && hasComparableRate(men) ? (women.participation-men.participation)*100 : null
  const urban = data.sectionCells.find(c=>c.code==='U'), rural=data.sectionCells.find(c=>c.code==='R')
  const available = data.sectionCells.filter(hasComparableRate)
  const range = available.length > 1 ? (Math.max(...available.map(c=>c.participation))-Math.min(...available.map(c=>c.participation)))*100 : null
  const sectionGap = hasComparableRate(urban) && hasComparableRate(rural) ? (rural.participation-urban.participation)*100 : null
  const closeSections = range !== null && available.length === 3 && range < closeRateThresholdPp
  return [
    { id:'level',title:valid ? Math.abs(delta)<=2 ? 'Una distancia cercana a la referencia' : delta>0 ? 'Por encima de su referencia' : 'Por debajo de su referencia' : 'Participación sin base suficiente',metric:points(data.deltaPp),
      text:valid ? `La participación fue ${percent(data.participation)}, frente a ${percent(data.reference)} de referencia. La diferencia de ${magnitude(delta)} sitúa al conjunto ${delta>0?'por encima':delta<0?'por debajo':'al nivel'} de sus pares comparables.` : 'No hay una tasa y referencia definidas para establecer esta comparación.',
      context:`${year} · ${data.ageBand} años. La referencia respeta la mezcla de edad y sexo; no es una meta.` },
    { id:'sex',title:sexGap===null ? 'Comparación por sexo limitada' : Math.abs(sexGap)<closeRateThresholdPp ? 'Tasas cercanas entre mujeres y hombres' : sexGap>0 ? 'Mayor tasa entre mujeres' : 'Mayor tasa entre hombres',metric:sexGap===null?'Sin comparación':magnitude(sexGap),
      text:sexGap===null ? 'No hay dos tasas con soporte suficiente. Los resultados disponibles se conservan en las gráficas.' : `Participaron ${percent(women!.participation)} de los registros especificados de mujeres y ${percent(men!.participation)} de los de hombres. ${Math.abs(sexGap)<closeRateThresholdPp?'Las tasas difieren menos de un punto porcentual.':'La diferencia compara tasas, no la cantidad de mujeres y hombres.'}`,
      context:`Dentro de esta ficha de ${year}; cada sexo conserva su propia referencia nacional.` },
    { id:'section', title:closeSections ? 'Tasas próximas entre tipos de sección' : sectionGap===null ? 'Comparación por sección limitada' : Math.abs(sectionGap)<closeRateThresholdPp ? 'Urbana y Rural tienen tasas cercanas' : sectionGap>0 ? 'Mayor tasa rural que urbana' : 'Mayor tasa urbana que rural',metric:closeSections ? `${magnitude(range!)} de rango` : sectionGap===null ? 'Sin comparación' : magnitude(sectionGap),
      text:closeSections ? `La distancia entre la mayor y la menor de las tres tasas es inferior a 1 pp. Esta cercanía agregada no implica que todos los municipios sean iguales.` : sectionGap===null ? 'No hay tasas Urbana y Rural con soporte suficiente para el contraste. Se muestran las categorías disponibles.' : `En secciones rurales la participación fue ${percent(rural!.participation)}, frente a ${percent(urban!.participation)} en urbanas. ${Math.abs(sectionGap)<closeRateThresholdPp?'La diferencia es menor de 1 pp.':'El contraste describe los registros de esta ficha, sin explicar sus causas.'}`,
      context:'Urbana, Rural y Mixta clasifican secciones electorales, no la residencia individual.' },
    { id:'variation',title:data.quality.signReversals>0 ? 'El promedio no resume todos los cruces' : 'El signo se mantiene en los cruces evaluables',metric:`${count(data.quality.signReversals)} de ${count(data.quality.eligibleCells)}`,
      text:data.quality.signReversals>0 ? `${percent(data.quality.reversalShare)} de los grupos con información suficiente, al separar por tipo de sección, queda al otro lado de su referencia respecto al conjunto al que pertenece.` : 'No se observan cambios de signo en los cruces con soporte. Eso no demuestra que sus tasas sean iguales.',
      context:'Son grupos agregados, no personas que hayan cambiado de comportamiento. Los cruces sin soporte quedan fuera de este contraste.' },
  ]
}

export function comparisonInsights(profiles: EnrichedProfile[], year: number) {
  if (profiles.length<2 || profiles.length>3 || new Set(profiles.map(p=>p.id)).size!==profiles.length) throw new Error('Elige dos o tres perfiles diferentes')
  const bands=[...new Set(profiles.map(p=>p.ageBand))]
  const valid=profiles.filter(p=>finite(p.participation))
  const min=valid.length?Math.min(...valid.map(p=>p.participation!)):null,max=valid.length?Math.max(...valid.map(p=>p.participation!)):null
  const highest=valid.filter(p=>Math.abs(p.participation!-max!)<1e-12),lowest=valid.filter(p=>Math.abs(p.participation!-min!)<1e-12)
  const names=(items:EnrichedProfile[])=>items.map(p=>p.name).join(' y ')
  const context=`Elección ${electionType(year)} de ${year}. ${bands.length===1?`Comparten la banda ${bands[0]} años, pero sus referencias agregadas pueden variar por la mezcla de sexo.`:'Incluyen edades distintas y referencias propias; una tasa absoluta mayor no equivale a una mejor posición relativa.'}`
  const sexSpread=(code:string)=>{const cells=profiles.map(p=>p.sexCells.find(c=>c.code===code)).filter(hasComparableRate);return cells.length>=2?magnitude((Math.max(...cells.map(c=>c.participation))-Math.min(...cells.map(c=>c.participation)))*100):'sin comparación'}
  const womenShares=profiles.map(p=>p.sexCells.find(c=>c.code==='1')?.nominalShare).filter(finite)
  const result:ProfileInsight[]=[
    {id:'general',title:'Participación dentro de esta comparación',metric:min===null||max===null?'Sin comparación':magnitude((max-min)*100),
      text:min===null||max===null?'No hay tasas suficientes para comparar.':Math.abs(max-min)<1e-12?`Los perfiles seleccionados tienen la misma tasa observada: ${percent(max)}. No hay un perfil con tasa mayor dentro de esta comparación.`:`La tasa más alta corresponde a ${names(highest)} (${percent(max)}), y la más baja a ${names(lowest)} (${percent(min)}). ${Math.abs(max-min)*100<1?'La distancia es menor de 1 pp; las tasas son cercanas.':'Esta distancia compara niveles absolutos, no causas.'}`,context},
    {id:'reference',title:'Distancia frente a sus propias referencias',metric:'Posición relativa',
      text:profiles.map(p=>`${p.name}: ${points(p.deltaPp)} frente a ${percent(p.reference)} de referencia`).join('; ')+'.',context:'Cada referencia es del mismo año, banda y sexo, combinada con los denominadores de su ficha. No es una referencia única para todas.'},
    {id:'sex',title:'Diferencias internas entre mujeres y hombres',metric:'Tasas y composición',
      text:profiles.map(p=>{const w=p.sexCells.find(c=>c.code==='1'),m=p.sexCells.find(c=>c.code==='0');return hasComparableRate(w)&&hasComparableRate(m)?`${p.name}: ${magnitude((w.participation-m.participation)*100)}${Math.abs(w.participation-m.participation)*100<1?' entre tasas cercanas':w.participation>m.participation?' más entre mujeres':' más entre hombres'}`:`${p.name}: sin dos tasas con soporte para comparar`}).join('; ')+`. Entre fichas, el rango de tasas es ${sexSpread('1')} en mujeres y ${sexSpread('0')} en hombres.`,context:`${womenShares.length>1?`Las mujeres reúnen entre ${percent(Math.min(...womenShares))} y ${percent(Math.max(...womenShares))} del nominal de cada ficha. `:''}Composición nominal y participación tienen bases distintas.`},
    {id:'section',title:'Contraste rural–urbano y composición',metric:'Misma comparación en cada ficha',
      text:profiles.map(p=>{const u=p.sectionCells.find(c=>c.code==='U'),r=p.sectionCells.find(c=>c.code==='R');return hasComparableRate(u)&&hasComparableRate(r)?`${p.name}: Rural menos Urbana = ${points((r.participation-u.participation)*100)}; Urbana reúne ${percent(u.nominalShare)} del nominal`:`${p.name}: contraste rural–urbano no disponible`}).join('; ')+'.',context:'El contraste fijo evita elegir automáticamente el máximo. Mixta se conserva en las gráficas. U/R/M no indica residencia individual ni una causa electoral.'},
  ]
  return {context,findings:result,limitations:[
    'Son segmentos agregados por reglas, no personas identificadas ni clases naturales. Las tasas no explican motivaciones ni causalidad.',
    'Los municipios se superponen entre fichas; sus cantidades no se suman como cobertura única. No se mezclan elecciones.',
    'Participación = suma SV / suma (SV+NV). NS no es abstención; las tasas ausentes no se convierten en cero. Soporte del segmento: LN≥100, SV+NV≥100 y filas fuente≥5.',
    'Las diferencias menores de 1 pp se describen como cercanas por una regla editorial; no se ha realizado una prueba de significación. Cada ficha conserva sus alertas de cobertura.',
  ]}
}
