import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { buildSync } from 'esbuild'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { validateProfileEnrichment, enrichProfiles } from '../src/features/profiles/profileEnrichment.ts'

const cache=resolve('node_modules/.cache/historical-profiles');mkdirSync(cache,{recursive:true})
async function bundle(entry,name){const result=buildSync({entryPoints:[entry],bundle:true,write:false,platform:'node',format:'esm',jsx:'automatic',packages:'external',loader:{'.css':'empty'}});const path=resolve(cache,name+'.mjs');writeFileSync(path,result.outputFiles[0].text);return import(pathToFileURL(path).href)}
const exporter=await bundle('src/features/profiles/profileExport.ts','export')
const {EnrichedProfileDetail}=await bundle('src/features/profiles/EnrichedProfileDetail.tsx','detail')
const read=path=>JSON.parse(readFileSync(path,'utf8'))
const outputs=[]
for(const year of [2009,2012,2015,2018,2021,2024]){
 const payload=validateProfileEnrichment(read(`public/data/profiles/enriched-${year}.json`),year)
 const originals=read(`public/data/participamx_multiyear/elections/${year}/profiles.json`).data
 const base=originals.map(p=>({id:p.profile_id,participation:p.participation_observed*100,peerReference:p.matched_peer_reference*100,participationDelta:p.participation_delta*100,nominalList:p.LN,segmentCount:p.segments,municipalityCount:p.municipalities,coverage:p.nominal_coverage*100}))
 const profiles=enrichProfiles(base,payload,year),dataset={year,enrichment:payload,enrichmentStatus:'ready',profiles,source:'INE'}
 test(`${year}: contrato anual, sin V2.1 histórico ni categoría inventada`,()=>{
   assert.equal(profiles.length,6);assert.equal(!!payload.transversalFinding,year===2024)
   assert.throws(()=>validateProfileEnrichment(payload,year===2024?2009:2024))
   if(year!==2024){const contaminated=structuredClone(payload);contaminated.transversalFinding=read('public/data/profiles/enriched-2024.json').transversalFinding;assert.throws(()=>validateProfileEnrichment(contaminated,year))}
 })
 for(const profile of profiles)test(`${year}/${profile.id}: ficha y PDF del mismo universo`,()=>{
   const plan=exporter.buildProfileExportPlan(profile,dataset)
   const text=plan.pages.flat().filter(c=>c.kind==='text').map(c=>c.text).join(' ')
   assert.equal(plan.year,year);assert.ok(plan.filename.endsWith('_'+year));assert.equal(plan.pages.length,2)
   assert.ok(text.includes(`elección ${year}`));assert.ok(text.includes(profile.name));assert.ok(text.includes(profile.nominalList.toLocaleString('es-MX')))
   if(year!==2024)assert.ok(!text.includes('2024'))
   const html=renderToStaticMarkup(createElement(EnrichedProfileDetail,{profile,dataset,onClose:()=>{}}))
   assert.ok(html.includes(profile.name));assert.ok(html.includes('Cruce')||html.includes('cruce completo'));assert.ok(!html.includes('Desglose ampliado no disponible'))
   for(const c of profile.enriched.jointCells)assert.equal(c.specifiedCount,c.SV+c.NV)
   const pdf=Buffer.from(exporter.renderProfilePdf(plan).output('arraybuffer'));assert.equal(pdf.subarray(0,5).toString(),'%PDF-')
   writeFileSync(resolve(cache,plan.filename+'.pdf'),pdf)
   outputs.push({year,id:profile.id,pdfBytes:pdf.length})
 })
}
test('Exportación rechaza mezcla anual y fichas de otra población',()=>{
 const e=read('public/data/profiles/enriched-2009.json'),p=e.profiles[0]
 const profile={id:p.id,name:p.name,nominalList:p.counts.LN,participation:p.participation*100,peerReference:p.reference*100,participationDelta:p.deltaPp,enriched:p}
 assert.throws(()=>exporter.buildProfileExportPlan(profile,{year:2024,enrichment:e,enrichmentStatus:'ready'}))
 assert.throws(()=>exporter.profileExportFilename(p.id,2010))
})
process.on('beforeExit',()=>writeFileSync(resolve(cache,'pdf-generation-results.json'),JSON.stringify(outputs,null,2)))
