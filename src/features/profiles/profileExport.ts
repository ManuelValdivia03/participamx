import { jsPDF } from 'jspdf'
import { count, percent, points } from './profileEnrichment'
import { orderedSections, orderedSexes, profileCatalog, getProfileReading, sexDifferenceText, sectionDifferenceText, sexLabels } from './profilePresentation'
import type { CitizenProfile, ProfileCrossCell, ProfileDataset } from './types'
import { additionalSexNote } from './profileLanguage'

export type TextCommand = { kind:'text'; x:number; y:number; text:string; size:number; bold:boolean; color:string }
export type RectCommand = { kind:'rect'; x:number; y:number; width:number; height:number; color:string }
export type ExportPlan = { width:number; height:number; pages:(TextCommand|RectCommand)[][]; filename:string; name:string; profileId:string; year:number }
export const exportColors = { ink:'#382742', muted:'#66566f', purple:'#694382', paper:'#fffdf9', soft:'#f3edf6', line:'#d9cddd', U:'#69388f', R:'#a95536', M:'#267565', '0':'#5e92bb', '1':'#bf6093' }
const colors = exportColors
export const exportPlainText = (text:string) => text.replace(/[–—−]/g,'-').replace(/[“”]/g,'"').replace(/[‘’]/g,"'").replace(/≥/g,'>=').replace(/≤/g,'<=').replace(/Σ/g,'suma ')
const plain = exportPlainText
export function profileExportFilename(id:string, year = 2024) {
  const entry = profileCatalog.find(p=>p.id===id)
  if (!entry || ![2009,2012,2015,2018,2021,2024].includes(year)) throw new Error('Perfil o elección no reconocidos')
  const slug = entry.name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(' con ',' ').replace(/[^a-z0-9]+/g,'_')
  return `participamx_perfil_${entry.number}_${slug}_${year}`
}

export function requireExportProfile(profile:CitizenProfile, dataset:ProfileDataset) {
  const data=profile.enriched, entry=profileCatalog.find(p=>p.id===profile.id)
  if (![2009,2012,2015,2018,2021,2024].includes(dataset.year) || dataset.enrichment?.year!==dataset.year || dataset.enrichmentStatus!=='ready' || !data || !entry || data.id!==profile.id || !dataset.enrichment.profiles.includes(data) || profile.name!==entry.name || profile.nominalList!==data.counts.LN || profile.participation!==data.participation!*100 || profile.peerReference!==data.reference!*100 || profile.participationDelta==null || data.deltaPp==null || Math.abs(profile.participationDelta-data.deltaPp)>1e-9) throw new Error('La exportación requiere la ficha nacional validada de la elección activa.')
  return {data,entry}
}

export function buildProfileExportPlan(profile:CitizenProfile, dataset:ProfileDataset):ExportPlan {
  const {data,entry}=requireExportProfile(profile,dataset)
  const year=dataset.year
  const pdf=new jsPDF({unit:'pt',format:'a4',orientation:'portrait'}), width=pdf.internal.pageSize.getWidth(), height=pdf.internal.pageSize.getHeight()
  const pages:ExportPlan['pages']=[[],[]];let page=0
  const rect=(x:number,y:number,w:number,h:number,color:string)=>{if(w<0||h<0||x<0||y<0||x+w>width+.1||y+h>height+.1)throw new Error('Gráfica fuera de márgenes');pages[page].push({kind:'rect',x,y,width:w,height:h,color})}
  function text(value:string,x:number,y:number,size=11.5,bold=false,maxWidth=width-x-40,color=colors.ink) {
    pdf.setFont('helvetica',bold?'bold':'normal');pdf.setFontSize(size)
    const lines=pdf.splitTextToSize(plain(value),maxWidth) as string[]
    for(const line of lines){if(y-size<24||y>height-20||pdf.getTextWidth(line)>maxWidth+.5)throw new Error('No se pudo acomodar el texto sin recortes.');pages[page].push({kind:'text',x,y,text:line,size,bold,color});y+=size*1.4}
    return y
  }
  const heading=(value:string,y:number)=>text(value,40,y,17,true)
  function base(number:number){page=number-1;rect(0,0,width,height,colors.paper);rect(0,0,width,10,colors.purple);text('ParticipaMX',40,49,24,true);text('Perfil de participación electoral · Ficha nacional',40,70,10.5,false,515,colors.muted);text(`Ficha ${entry!.number} / ${number===1?'Resumen e indicadores':'Interpretación y método'} · ${year}`,40,91,10,false,515,colors.muted);text(`Elección ${year} · Ficha ${entry!.number} · ${number}/2`,40,height-22,9,false,515,colors.muted)}
  base(1)
  let y=text(entry.name,40,126,21,true)
  y=text(`${entry.ageBand.replace('-', '–')} años · Referencias nacionales por edad y sexo`,40,y+6,11,false,515,colors.muted)
  const kpiY=y+10
  for(const [i,label,value] of [[0,'Participación observada',percent(data.participation)],[1,'Referencia comparable',percent(data.reference)],[2,'Diferencia',points(data.deltaPp)]] as const){const x=40+i*174;rect(x,kpiY,163,76,colors.soft);text(label,x+12,kpiY+23,10.5,false,140,colors.muted);text(value,x+12,kpiY+54,22,true,140,colors.purple)}
  y=text(`Lista nominal anual incluida: ${percent(data.nominalShare)} · Municipios presentes: ${count(data.municipalities)}`,40,kpiY+99,11)
  y=text('pp = puntos porcentuales. La referencia no es una predicción ni una meta.',40,y+2,10.5,false,515,colors.muted)
  function measures(title:string,cells:ProfileCrossCell[],labels:Record<string,string>,start:number){
    let rowY=heading(title,start)+10
    text('Composición nominal',150,rowY,10.5,true,170);text('Participación observada',355,rowY,10.5,true,195);rowY+=25
    for(const cell of cells){
      const color=colors[cell.code as keyof typeof colors]??colors.purple
      text(labels[cell.code],40,rowY+10,11.5,true,100)
      for(const [x,value] of [[150,cell.nominalShare],[355,cell.participation]] as const){rect(x,rowY,110,11,colors.line);if(value!==null&&Number.isFinite(value))rect(x,rowY,110*value,11,color);text(percent(value),x+119,rowY+10,10.5,false,72)}
      if(cell.status==='low_support')text('Soporte reducido',355,rowY+25,9,false,180,colors.muted)
      rowY+=43
    }
    return rowY
  }
  y=measures('Mujeres y hombres',orderedSexes(data.sexCells),sexLabels,y+21)
  y=text(sexDifferenceText(data.sexCells),40,y+5,11.5)
  y=measures('Tipo de sección electoral',orderedSections(data.sectionCells),{U:'Urbana',R:'Rural',M:'Mixta'},y+25)
  y=text(sectionDifferenceText(data.sectionCells),40,y+4,11.5)
  y=text('Composición: proporción de lista nominal. Participación: SV/(SV+NV). Barras de 0 a 100 %. Las diferencias son descriptivas, no causales.',40,y+6,10.5,false,515,colors.muted)
  if(y>height-48)throw new Error('La ficha excede una página de indicadores')
  base(2)
  y=text(entry.name,40,124,19,true)
  y=heading('¿Qué revelan los datos?',y+22)
  for(const finding of getProfileReading(data,year).findings)y=text(`- ${finding}`,40,y+8,10.5)+2
  y=heading('Conteos y cobertura de la ficha',y+20)
  y=text(`Lista nominal (LN): ${count(data.counts.LN)} · Registros con participación (SV): ${count(data.counts.SV)} · Registros sin participación (NV): ${count(data.counts.NV)}.`,40,y+6)
  y=text(`Condición de voto no especificada (NS): ${count(data.counts.NS)} · Base especificada SV+NV: ${count(data.counts.specified_count)} · Filas fuente: ${count(data.counts.source_row_count)} · Segmentos: ${count(data.segments)}.`,40,y+4)
  y=heading('Fuente, definición y límites',y+20)
  const notes=[
    `Fuente: datos abiertos del Instituto Nacional Electoral (INE), Conteos Censales de Participación Ciudadana, elección ${year} (${[2012,2018,2024].includes(year)?'presidencial':'intermedia'}). Ficha nacional de ParticipaMX.`,
    `Regla: municipio x intervalo x sexo, ${entry.direction} de su referencia nacional comparable. Soporte del segmento: LN>=100, SV+NV>=100 y filas fuente>=5. Las filas fuente no son personas ni secciones independientes.`,
    'Participación = suma SV / suma (SV+NV). La referencia combina las nacionales de edad y sexo con los denominadores locales. Composición = LN de categoría / LN de ficha. NS no es abstención; una tasa ausente no es cero.',
    `${percent(data.quality.highNsShare)} de segmentos con NS/LN>=10 %; ${percent(data.quality.nearReferenceShare)} a no más de 2 pp de la referencia. ${additionalSexNote(year)} 101+ permanece complementario.`,
    'U/R/M clasifica secciones electorales, no residencia individual. Son resultados agregados, sin causalidad ni seguimiento individual. Los municipios se superponen; no sumar su cobertura. Diferencias menores de 1 pp: cercanía editorial, no significación estadística.',
  ]
  for(const note of notes)y=text(note,40,y+9,10.5,false,515,colors.muted)
  if(y-10.5*1.4>height-44)throw new Error('La ficha excede dos páginas')
  return {width,height,pages,filename:profileExportFilename(profile.id,year),name:entry.name,profileId:profile.id,year}
}

export function renderProfilePdf(plan:ExportPlan) {
  const pdf=new jsPDF({unit:'pt',format:[plan.width,plan.height],orientation:plan.width>plan.height?'landscape':'portrait',compress:true})
  pdf.setProperties({title:`ParticipaMX - ${plan.name} - ${plan.year}`,subject:`${plan.profileId.includes(',')?'Comparación de perfiles':'Ficha nacional de participación electoral'}: ${plan.profileId} - ${plan.year}`,author:'ParticipaMX',creator:'ParticipaMX'})
  plan.pages.forEach((commands,index)=>{if(index)pdf.addPage();for(const c of commands){if(c.kind==='rect'){pdf.setFillColor(c.color);pdf.rect(c.x,c.y,c.width,c.height,'F')}else{pdf.setTextColor(c.color);pdf.setFont('helvetica',c.bold?'bold':'normal');pdf.setFontSize(c.size);pdf.text(c.text,c.x,c.y)}}})
  return pdf
}
export async function renderProfilePng(plan:ExportPlan):Promise<Blob> {
  const canvas=document.createElement('canvas'),scale=1600/plan.width
  canvas.width=1600;canvas.height=Math.ceil(plan.height*plan.pages.length*scale)
  const ctx=canvas.getContext('2d');if(!ctx)throw new Error('No se pudo preparar la imagen')
  ctx.fillStyle=colors.paper;ctx.fillRect(0,0,canvas.width,canvas.height);ctx.scale(scale,scale)
  plan.pages.forEach((commands,index)=>{ctx.save();ctx.translate(0,index*plan.height);for(const c of commands){ctx.fillStyle=c.color;if(c.kind==='rect')ctx.fillRect(c.x,c.y,c.width,c.height);else{ctx.font=`${c.bold?'bold':'normal'} ${c.size}px Arial, sans-serif`;ctx.fillText(c.text,c.x,c.y)}}ctx.restore()})
  return new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('No se pudo generar el PNG')),'image/png'))
}
export async function downloadProfileExport(profile:CitizenProfile,dataset:ProfileDataset,format:'pdf'|'png') {
  const plan=buildProfileExportPlan(profile,dataset)
  const blob=format==='pdf'?renderProfilePdf(plan).output('blob'):await renderProfilePng(plan)
  const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`${plan.filename}.${format}`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),3000)
}
