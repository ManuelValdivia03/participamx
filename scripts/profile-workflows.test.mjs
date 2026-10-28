import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs'
import {resolve} from 'node:path'
import {pathToFileURL} from 'node:url'
import {buildSync} from 'esbuild'
import {renderToStaticMarkup} from 'react-dom/server'
import {createElement} from 'react'
const cache=resolve('node_modules/.cache/selectors-exports');mkdirSync(cache,{recursive:true})
async function bundle(path,name){const r=buildSync({entryPoints:[path],bundle:true,write:false,platform:'node',format:'esm',jsx:'automatic',packages:'external',loader:{'.css':'empty'},define:{'import.meta.env.BASE_URL':'"/"'}});const target=resolve(cache,name+'.mjs');writeFileSync(target,r.outputFiles[0].text);return import(pathToFileURL(target).href)}
const {buildProfileExportPlan,renderProfilePdf,profileExportFilename}=await bundle('src/features/profiles/profileExport.ts','export')
const {ElectionSelector}=await bundle('src/components/ElectionSelector.tsx','elections')
const {StateSearch,findStates}=await bundle('src/components/StateSearch.tsx','state-search')
const {Methodology}=await bundle('src/features/methodology/Methodology.tsx','method')
const {validateStateProfileContext}=await bundle('src/services/profileTerritoryContext.ts','context')
const payload=JSON.parse(readFileSync('public/data/profiles/enriched-2024.json','utf8'))
export const profiles=payload.profiles.map(p=>({id:p.id,name:p.name,ageBand:p.ageBand,participation:p.participation*100,peerReference:p.reference*100,participationDelta:p.deltaPp,nominalList:p.counts.LN,coverage:p.nominalShare*100,municipalityCount:p.municipalities,enriched:p}))
export const dataset={year:2024,source:'INE',enrichment:payload,enrichmentStatus:'ready',profiles}
test('Selector único: seis elecciones, tipos correctos y un punto de Tab',()=>{
 const html=renderToStaticMarkup(createElement(ElectionSelector,{year:2021,onChange:()=>{}}))
 assert.equal((html.match(/role="radio"/g)??[]).length,6);assert.equal((html.match(/tabindex="0"/g)??[]).length,1)
 assert.equal((html.match(/>Presidencial</g)??[]).length,3);assert.equal((html.match(/>Intermedia</g)??[]).length,3)
 assert.ok(html.includes('aria-checked="true" tabindex="0" data-election-year="2021"'))
})
test('Búsqueda comparte normalización del Atlas: acentos, fragmentos y sin coincidencias',()=>{
 const options=[{code:'MX',name:'México'},{code:'08',name:'CHIHUAHUA'},{code:'30',name:'VERACRUZ'},{code:'19',name:'NUEVO LEÓN'}]
 assert.equal(findStates(options,'leo')[0].code,'19');assert.equal(findStates(options,'  Chih ')[0].code,'08');assert.equal(findStates(options,'ver')[0].code,'30');assert.equal(findStates(options,'zzzzz').length,0)
 const html=renderToStaticMarkup(createElement(StateSearch,{options,value:'30',onChange:()=>{}}));assert.ok(html.includes('role="combobox"'));assert.ok(html.includes('Volver a México'))
})
test('Metodología usa los mismos seis nombres e intervalos sin etiquetas antiguas',()=>{
 const html=renderToStaticMarkup(createElement(Methodology))
 for(const p of profiles)assert.ok(html.includes(p.name))
 assert.ok(!html.includes('por encima de sus pares'));assert.ok(!html.includes('por debajo de sus pares'))
 for(const band of ['18–34 años','35–59 años','60–100 años'])assert.ok(html.includes(band))
})
test('Contexto estatal: referencia, conteos y año; rechaza denominadores y duplicados',()=>{
 for(const year of [2009,2012,2015,2018,2021,2024]){
   const rows=JSON.parse(readFileSync(`public/data/participamx_multiyear/elections/${year}/state_profiles.json`,'utf8')).data
   for(const code of ['08','30']){const selected=validateStateProfileContext(rows,year,code);assert.ok(selected.length);for(const r of selected)assert.equal(r.specified_count,r.SV+r.NV)}
   assert.throws(()=>validateStateProfileContext(rows,year+1,'08'))
 }
 const rows=JSON.parse(readFileSync('public/data/participamx_multiyear/elections/2024/state_profiles.json','utf8')).data
 const duplicate=[...rows,rows.find(r=>r.state_code==='8')];assert.throws(()=>validateStateProfileContext(duplicate,2024,'08'))
 const changed=structuredClone(rows);changed.find(r=>r.state_code==='8').specified_count++;assert.throws(()=>validateStateProfileContext(changed,2024,'08'))
})
test('Seis PDF A4 reales, dos páginas, texto seleccionable y ninguna cifra recalculada',()=>{
 const results=[]
 for(const p of profiles){
   const plan=buildProfileExportPlan(p,dataset),pdf=renderProfilePdf(plan),buffer=Buffer.from(pdf.output('arraybuffer'))
   assert.ok(buffer.subarray(0,5).toString()==='%PDF-');assert.equal(pdf.getNumberOfPages(),2)
   assert.ok(Math.abs(plan.width-595.28)<.02);assert.ok(Math.abs(plan.height-841.89)<.02)
   assert.equal(plan.pages.length,2);assert.ok(plan.pages.every(page=>page.some(c=>c.kind==='text')))
   const text=plan.pages.flat().filter(c=>c.kind==='text').map(c=>c.text).join(' ')
   assert.ok(text.includes(p.name));assert.ok(!text.includes(p.id));assert.ok(text.includes('INE'))
   assert.ok(text.includes((p.enriched.participation*100).toFixed(2)+' %'))
   assert.ok(text.includes(p.enriched.counts.LN.toLocaleString('es-MX')))
   assert.equal((buffer.toString('latin1').match(/\/Type \/Page\b/g)??[]).length,2)
   writeFileSync(resolve(cache,plan.filename+'.pdf'),buffer)
   results.push({id:p.id,pages:2,bytes:buffer.length,commands:plan.pages.map(p=>p.length)})
 }
 writeFileSync(resolve(cache,'pdf-validation.json'),JSON.stringify(results,null,2))
})
test('Exportación bloquea mezclas de años y fichas sin datos verificados',()=>{
 assert.throws(()=>buildProfileExportPlan(profiles[0],{...dataset,year:2021}))
 assert.throws(()=>buildProfileExportPlan({...profiles[0],enriched:undefined},dataset))
 assert.throws(()=>buildProfileExportPlan(profiles[0],{...dataset,enrichmentStatus:'error'}))
 assert.throws(()=>buildProfileExportPlan({...profiles[0],peerReference:99},dataset))
 assert.throws(()=>profileExportFilename('invented'))
 assert.equal(new Set(profiles.map(p=>profileExportFilename(p.id))).size,6)
})
