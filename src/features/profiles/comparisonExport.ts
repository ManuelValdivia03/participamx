import { jsPDF } from 'jspdf'
import { count, percent, points } from './profileEnrichment'
import { comparisonInsights } from './profileInsights'
import { additionalSexNote, electionType, sectionNames, sexLabels } from './profileLanguage'
import { profileCatalog } from './profilePresentation'
import { exportColors as colors, exportPlainText, requireExportProfile, renderProfilePdf, renderProfilePng, type ExportPlan } from './profileExport'
import type { CitizenProfile, EnrichedProfile, ProfileDataset } from './types'

export function comparisonExportFilename(profiles: CitizenProfile[], year: number) {
  if(profiles.length<2||profiles.length>3||new Set(profiles.map(p=>p.id)).size!==profiles.length)throw new Error('Elige dos o tres perfiles distintos')
  const ids=profiles.map(p=>{const entry=profileCatalog.find(e=>e.id===p.id);if(!entry)throw new Error('Perfil no reconocido');return `${entry.number}_${p.id.startsWith('young')?'jovenes':p.id.startsWith('adult')?'adultos':'mayores'}_${p.id.endsWith('unfavorable')?'menor':'mayor'}`})
  return `participamx_comparacion_${ids.join('_')}_${year}`
}

export function buildComparisonExportPlan(profiles: CitizenProfile[], dataset: ProfileDataset, format: 'pdf'|'png'): ExportPlan {
  const filename=comparisonExportFilename(profiles,dataset.year)
  const data=profiles.map(p=>requireExportProfile(p,dataset).data)
  const analysis=comparisonInsights(data,dataset.year)
  const width=format==='pdf'?595.28:842, height=format==='pdf'?841.89:1240
  const pages:ExportPlan['pages']=Array.from({length:format==='pdf'?3:1},()=>[])
  const pdf=new jsPDF({unit:'pt',format:[width,height]})
  let page=0
  function rect(x:number,y:number,w:number,h:number,color:string){if(x<0||y<0||w<0||h<0||x+w>width+.1||y+h>height+.1)throw new Error('Gráfica fuera de la página');pages[page].push({kind:'rect',x,y,width:w,height:h,color})}
  function text(value:string,x:number,y:number,size=11,bold=false,maxWidth=width-x-36,color=colors.ink,footer=false){
    pdf.setFont('helvetica',bold?'bold':'normal');pdf.setFontSize(size)
    for(const line of pdf.splitTextToSize(exportPlainText(value),maxWidth) as string[]){if(y-size<20||y>height-(footer?18:44)||pdf.getTextWidth(line)>maxWidth+.5)throw new Error(`La comparación excede el espacio legible: página ${page+1}, y=${y}, ${line}`);pages[page].push({kind:'text',x,y,text:line,size,bold,color});y+=size*1.35}
    return y
  }
  function base(index:number,title:string){page=index;rect(0,0,width,height,colors.paper);rect(0,0,width,9,colors.purple);text('ParticipaMX',36,43,22,true);text('Comparación de perfiles ciudadanos',36,66,15,true);text(`Elección ${dataset.year} · ${electionType(dataset.year)} · ${title}`,36,86,10.5,false,width-72,colors.muted);text(`INE · ParticipaMX · ${dataset.year} · ${index+1}/${pages.length}`,36,height-18,9,false,width-72,colors.muted,true)}
  const columnWidth=(width-72)/data.length
  function names(start:number){let end=start;data.forEach((p,i)=>{end=Math.max(end,text(p.name,36+i*columnWidth,start,12.5,true,columnWidth-14))});data.forEach((p,i)=>text(`${p.ageBand} años`,36+i*columnWidth,end+6,10.5,false,columnWidth-14,colors.muted));return end+28}
  function summaries(start:number,compact:boolean){
    const rows:[string,(p:EnrichedProfile)=>string][]=[['Participación observada',p=>percent(p.participation)],['Referencia comparable',p=>percent(p.reference)],['Diferencia',p=>points(p.deltaPp)],['Lista nominal',p=>count(p.counts.LN)],['Municipios presentes',p=>count(p.municipalities)]]
    if(!compact)rows.push(['Cobertura nominal anual',p=>percent(p.nominalShare)],['Segmentos',p=>count(p.segments)],['Con marca de voto (SV)',p=>count(p.counts.SV)],['Sin marca de voto (NV)',p=>count(p.counts.NV)],['No especificados (NS)',p=>count(p.counts.NS)],['Base especificada (SV+NV)',p=>count(p.counts.specified_count)],['Filas fuente',p=>count(p.counts.source_row_count)])
    let y=start
    rows.forEach(([label,format],row)=>{data.forEach((p,i)=>{const x=36+i*columnWidth;rect(x,y-12,columnWidth-10,38,row%2?colors.paper:colors.soft);text(label,x+7,y,9.5,false,columnWidth-24,colors.muted);text(format(p),x+7,y+18,12.5,true,columnWidth-24)});y+=41})
    return y
  }
  function cellBars(start:number,dimension:'sexCells'|'sectionCells'){
    const title=dimension==='sexCells'?'Sexo · tasas y composición nominal':'Tipo de sección electoral · tasas y composición nominal'
    let y=text(title,36,start,14,true)+10
    const codes=dimension==='sexCells'?['1','0']:['U','R','M']
    for(const code of codes){data.forEach((p,i)=>{const x=36+i*columnWidth,cell=p[dimension].find(c=>c.code===code),color=colors[code as keyof typeof colors]??colors.purple
      text((dimension==='sexCells'?sexLabels:sectionNames)[code],x,y,11.5,true,columnWidth-14)
      for(const [offset,field,label] of [[17,'participation','Participación'],[36,'nominalShare','Nominal']] as const){const value=cell?.[field]??null,barWidth=columnWidth-86;rect(x,y+offset,barWidth,7,colors.line);if(value!==null)rect(x,y+offset,barWidth*value,7,color);text(percent(value),x+barWidth+5,y+offset+7,10,false,69);text(label,x,y+offset+17,8.5,false,barWidth,colors.muted)}
      if(cell&&cell.status!=='defined')text(cell.status==='low_support'?'Soporte reducido':'Información no disponible',x,y+64,9,false,columnWidth-12,colors.muted)
    });y+=76}
    return y
  }
  function narrative(index:number,start:number,compact=false){const finding=analysis.findings[index];let y=text(finding.title,36,start,13,true);y=text(finding.text,36,y+3,11.5);if(!compact)y=text(finding.context,36,y+2,10,false,width-72,colors.muted);return y+13}
  if(format==='pdf'){
    base(0,'Resultados generales')
    let y=text(analysis.context,36,110,10.5,false,width-72,colors.muted)
    y=names(Math.max(163,y+13));y=summaries(y+10,false)
    text('Los municipios pueden estar en varias fichas: no sumar sus cantidades. Las referencias son propias de cada perfil, no una meta común.',36,y+8,10,false,width-72,colors.muted)
    base(1,'Sexo y tipo de sección electoral')
    y=names(116);y=cellBars(y+6,'sexCells');y=cellBars(y+21,'sectionCells')
    y=text('Barras de 0 a 100 %. Nominal = proporción de lista nominal; participación = SV/(SV+NV). No se compara una composición con una tasa.',36,y+5,10.5,false,width-72,colors.muted)
    text(additionalSexNote(dataset.year),36,y+6,10.5,false,width-72,colors.muted)
    base(2,'Qué nos permite observar esta comparación')
    y=110
    for(let i=0;i<4;i++)y=narrative(i,y)
    y=text('Fuentes, calidad y límites',36,y+3,13,true)
    for(const note of analysis.limitations)y=text(note,36,y+4,10,false,width-72,colors.muted)
    y=text(`NS/LN≥10 % en segmentos: ${data.map(p=>`${p.name}: ${percent(p.quality.highNsShare)}`).join('; ')}.`,36,y+4,10,false,width-72,colors.muted)
    text(`Fuente: INE · Conteos Censales de Participación Ciudadana, ${dataset.year}. Archivos enriquecidos nacionales y resultados V1 de esta elección. El contexto estatal no modifica estas fichas.`,36,y+4,10,false,width-72,colors.muted)
  }else{
    base(0,'Resumen de la comparación completa')
    let y=names(116);y=summaries(y+5,true);y=cellBars(y+12,'sexCells');y=cellBars(y+14,'sectionCells')
    y=text('Tres claves para leer los resultados',36,y+5,14,true)
    // La infografía resume tres contrastes; el PDF desarrolla las cuatro conclusiones.
    for(const index of [0,2,3])y=narrative(index,y+4,true)
    text(`Fuente: INE, ${dataset.year}. Nominal = composición LN; participación = SV/(SV+NV). pp = puntos porcentuales. Referencias propias por edad y sexo. U/R/M no es residencia individual. Resultados agregados, sin causalidad; municipios superpuestos. ${additionalSexNote(dataset.year)}`,36,y+3,10,false,width-72,colors.muted)
  }
  return {width,height,pages,filename,name:'Comparación de perfiles ciudadanos',profileId:data.map(p=>p.id).join(','),year:dataset.year}
}

export async function downloadComparisonExport(profiles:CitizenProfile[],dataset:ProfileDataset,format:'pdf'|'png') {
  const plan=buildComparisonExportPlan(profiles,dataset,format)
  const blob=format==='pdf'?renderProfilePdf(plan).output('blob'):await renderProfilePng(plan)
  const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`${plan.filename}.${format}`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),3000)
}
