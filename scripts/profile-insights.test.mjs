import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs'
import {resolve} from 'node:path'
import {pathToFileURL} from 'node:url'
import {buildSync} from 'esbuild'
import {createElement} from 'react'
import {renderToStaticMarkup} from 'react-dom/server'
const cache=resolve('node_modules/.cache/interpretation-comparison');mkdirSync(cache,{recursive:true})
async function bundle(entry,name){const r=buildSync({entryPoints:[entry],bundle:true,write:false,platform:'node',format:'esm',jsx:'automatic',packages:'external',loader:{'.css':'empty'}});const path=resolve(cache,name+'.mjs');writeFileSync(path,r.outputFiles[0].text);return import(pathToFileURL(path).href)}
const {profileInsights,comparisonInsights}=await bundle('src/features/profiles/profileInsights.ts','insights')
const {buildComparisonExportPlan,comparisonExportFilename}=await bundle('src/features/profiles/comparisonExport.ts','comparison-export')
const {buildProfileExportPlan,renderProfilePdf}=await bundle('src/features/profiles/profileExport.ts','individual-export')
const {EnrichedProfileDetail}=await bundle('src/features/profiles/EnrichedProfileDetail.tsx','detail')
const {ComparisonExportButtons}=await bundle('src/features/profiles/ComparisonExportButtons.tsx','buttons')
const language=await bundle('src/features/profiles/profileLanguage.ts','language')
const read=path=>JSON.parse(readFileSync(path,'utf8'))
const dictionaries=read('data/processed/participamx_multiyear/metadata/source_dictionaries.json')
const fixtures=[]
for(const year of [2009,2012,2015,2018,2021,2024]){
 const enrichment=read(`public/data/profiles/enriched-${year}.json`)
 const profiles=enrichment.profiles.map(p=>({id:p.id,name:p.name,ageBand:p.ageBand,participation:p.participation*100,peerReference:p.reference*100,participationDelta:p.deltaPp,nominalList:p.counts.LN,coverage:p.nominalShare*100,municipalityCount:p.municipalities,enriched:p}))
 const dataset={year,enrichment,enrichmentStatus:'ready',profiles,source:'INE'};fixtures.push({dataset,profiles})
 test(`${year}: nombres respaldados por el diccionario`,()=>{
  const line=dictionaries[year].flatMap(d=>d.text.split('\n')).find(s=>s.startsWith('SEXO'))
  for(const code of language.sexCategoriesByYear[year])assert.ok(line.includes(`${code} ${language.sexLabels[code]}`))
  assert.equal(line.includes('2 No binario'),year===2024);assert.ok(!language.additionalSexNote(year).includes('SEXO='))
 })
 test(`${year}: 6 fichas con cuatro hallazgos, sin códigos ni textos de otro año`,()=>{
  for(const p of profiles){
   const insights=profileInsights(p.enriched,year);assert.equal(insights.length,4);assert.equal(new Set(insights.map(f=>f.id)).size,4)
   for(const i of insights)for(const field of ['title','metric','text','context'])assert.ok(i[field].length)
   const w=p.enriched.sexCells.find(c=>c.code==='1'),m=p.enriched.sexCells.find(c=>c.code==='0')
   assert.ok(insights[1].metric.includes(Math.abs((w.participation-m.participation)*100).toFixed(2)))
   const html=renderToStaticMarkup(createElement(EnrichedProfileDetail,{profile:p,dataset,onClose:()=>{}}))
   assert.equal((html.match(/data-profile-insight=/g)??[]).length,4);assert.ok(!html.includes('SEXO=2'));assert.ok(html.includes('Cómo se calcularon estos datos'));assert.ok(html.includes('Fuentes y limitaciones'))
   const plan=buildProfileExportPlan(p,dataset),text=plan.pages.flat().filter(c=>c.kind==='text').map(c=>c.text).join(' ')
   assert.equal(plan.pages.length,2);assert.ok(!text.includes('SEXO=2'));if(year!==2024)assert.ok(!text.includes('2024'))
   writeFileSync(resolve(cache,plan.filename+'.pdf'),Buffer.from(renderProfilePdf(plan).output('arraybuffer')))
  }
 })
 test(`${year}: todas las selecciones de dos/tres perfiles caben en PDF y PNG`,()=>{
  let combinations=0
  for(let a=0;a<6;a++)for(let b=a+1;b<6;b++)for(const c of [null,...Array.from({length:5-b},(_,i)=>b+i+1)]){
   const selected=[profiles[a],profiles[b],...(c===null?[]:[profiles[c]])]
   const analysis=comparisonInsights(selected.map(p=>p.enriched),year);assert.equal(analysis.findings.length,4)
   for(const format of ['pdf','png']){
    const plan=buildComparisonExportPlan(selected,dataset,format),text=plan.pages.flat().filter(c=>c.kind==='text').map(c=>c.text).join(' ')
    assert.equal(plan.pages.length,format==='pdf'?3:1);assert.ok(text.includes('Mujeres'));assert.ok(text.includes('Mixta'));assert.ok(!text.includes('SEXO='));if(year!==2024)assert.ok(!text.includes('2024'))
    for(const p of selected)assert.ok(text.includes(p.name))
   }
   combinations++
  }
  assert.equal(combinations,35)
 })
}
test('Reglas editoriales: cercanía, soporte, signos y cero sin exageración',()=>{
 const p=structuredClone(fixtures[0].profiles[0].enriched)
 p.sexCells.forEach(c=>{c.participation=.5;c.status='defined'})
 p.sectionCells.forEach((c,i)=>{c.participation=.5+i*.001;c.status='defined'})
 assert.ok(profileInsights(p,2009)[1].title.includes('cercanas'));assert.ok(profileInsights(p,2009)[2].title.includes('próximas'))
 p.sexCells[0].status='low_support';assert.equal(profileInsights(p,2009)[1].metric,'Sin comparación')
 p.sexCells[0].status='defined';p.sexCells[0].participation=0;assert.ok(profileInsights(p,2009)[1].metric.includes('50.00'))
 p.quality.signReversals=0;assert.ok(profileInsights(p,2009)[3].title.includes('se mantiene'))
})
test('Comparación: referencias propias, contextos distintos y selección verificada',()=>{
 const {profiles,dataset}=fixtures[0]
 assert.ok(comparisonInsights(profiles.slice(0,2).map(p=>p.enriched),2009).context.includes('Comparten'))
 assert.ok(comparisonInsights([profiles[0].enriched,profiles[2].enriched],2009).context.includes('edades distintas'))
 assert.throws(()=>buildComparisonExportPlan(profiles.slice(0,1),dataset,'pdf'))
 assert.throws(()=>buildComparisonExportPlan([profiles[0],profiles[0]],dataset,'pdf'))
 assert.throws(()=>buildComparisonExportPlan(profiles.slice(0,2),{...dataset,year:2024},'png'))
 assert.notEqual(comparisonExportFilename(profiles.slice(0,2),2009),comparisonExportFilename([profiles[0],profiles[2]],2009))
 for(const n of [0,1,2,3]){const html=renderToStaticMarkup(createElement(ComparisonExportButtons,{profiles:profiles.slice(0,n),dataset}));assert.equal((html.match(/disabled=""/g)??[]).length,n<2?2:0)}
})
