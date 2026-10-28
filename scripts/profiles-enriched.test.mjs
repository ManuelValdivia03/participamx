import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { createHash } from 'node:crypto'
import { buildSync } from 'esbuild'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement } from 'react'
import { validateProfileEnrichment, enrichProfiles, percent, points, profileIds } from '../src/features/profiles/profileEnrichment.ts'

const load = path => JSON.parse(readFileSync(path, 'utf8'))
const payload = load('public/data/profiles/enriched-2024.json')
const v1 = load('public/data/participamx_multiyear/elections/2024/profiles.json').data
const editorial = load('analysis/profile_v2/editorial/results/experimental_profile_names_2024.json')
const patterns = load('analysis/profile_v2/patterns/results/candidates/experimental_patterns.json')
const base = v1.map(p => ({ id:p.profile_id, name:p.label, description:'', summary:'', participation:p.participation_observed*100,
  peerReference:p.matched_peer_reference*100, participationDelta:p.participation_delta*100, coverage:p.nominal_coverage*100,
  medianAge:null, municipalityCount:p.municipalities, segmentCount:p.segments, nominalList:p.LN, characteristics:[],strategies:[],limitations:[] }))

test('Seis IDs V1, sin el hallazgo como séptimo perfil', () => {
  const parsed=validateProfileEnrichment(payload)
  assert.equal(parsed.profiles.length,6)
  assert.deepEqual(new Set(parsed.profiles.map(p=>p.id)),new Set(profileIds))
  assert.equal(parsed.transversalFinding.id,'interaction_18-34_R_U')
  assert.ok(!parsed.profiles.some(p=>p.id===parsed.transversalFinding.id))
})
test('Cifras V1 intactas; cruces reales concilian LN, SV, NV y NS', () => {
  for(const p of payload.profiles){
    const original=v1.find(x=>x.profile_id===p.id), source=editorial.profiles.find(x=>x.profile_id===p.id)
    assert.equal(p.counts.LN,original.LN)
    assert.equal(p.participation,original.participation_observed)
    assert.equal(p.reference,original.matched_peer_reference)
    for(const cells of [p.sexCells,p.sectionCells,p.jointCells]){
      for(const key of ['LN','SV','NV','NS']) assert.equal(cells.reduce((s,c)=>s+c[key],0),p.counts[key])
      assert.ok(Math.abs(cells.reduce((s,c)=>s+c.nominalShare,0)-1)<1e-12)
      for(const cell of cells) assert.ok(Math.abs(cell.participation-cell.SV/cell.specifiedCount)<1e-12)
    }
    assert.equal(p.quality.signReversals,source.statistics.eligible_flip_cells)
    assert.equal(p.quality.eligibleCells,source.statistics.eligible_cells)
  }
  assert.equal(payload.profiles.reduce((s,p)=>s+p.quality.signReversals,0),2704)
})
test('Proveniencia comprobable por SHA-256 de las fuentes originales', () => {
  for(const source of Object.values(payload.sources)) assert.equal(createHash('sha256').update(readFileSync(source.path)).digest('hex'),source.sha256)
})
test('V2.1 mantiene contraste municipal distinto de tasas agregadas', () => {
  assert.equal(payload.transversalFinding.municipalContrastPp,patterns.profiles[0].statistics.equal_municipality_pp)
  assert.equal(payload.transversalFinding.nominalContrastPp,patterns.profiles[0].statistics.nominal_pp)
  assert.equal(payload.transversalFinding.municipalities,1226)
  assert.equal(payload.heterogeneity.bothBeyond2Pp,562)
  assert.equal(payload.transversalFinding.annualNominalShare,patterns.profiles[0].statistics.annual_LN_fraction)
})
test('Adaptador conserva indicadores base, aplica nombres acordados y rechaza otros años', () => {
  const result=enrichProfiles(base,validateProfileEnrichment(payload),2024)
  assert.equal(result.length,6)
  assert.equal(result[0].name,payload.profiles[0].name)
  assert.equal(result[0].participation,base.find(p=>p.id===result[0].id).participation)
  assert.throws(()=>enrichProfiles(base,payload,2021))
  const bad=structuredClone(base);bad[0].nominalList++
  assert.throws(()=>enrichProfiles(bad,payload,2024))
})
test('Contrato rechaza duplicados, grupos no validados, denominadores erróneos y NaN', () => {
  for(const mutate of [p=>p.profiles.push(p.profiles[0]),p=>p.profiles[0].id='inventado',p=>p.profiles[0].sexCells[0].specifiedCount++,
    p=>p.profiles[0].jointCells[0].participation=NaN,p=>p.profiles[0].participation=.99,p=>p.profiles[0].deltaPp=99,
    p=>p.year=2021,p=>p.transversalFinding.id='interaction_35-59_M_U']){
    const bad=structuredClone(payload);mutate(bad);assert.throws(()=>validateProfileEnrichment(bad))
  }
})
test('Cero válido y NULL tienen representaciones diferentes', () => {
  assert.equal(percent(null),'Sin información');assert.equal(percent(undefined),'Sin información')
  assert.equal(percent(0),'0.00 %');assert.equal(points(0),'0.00 pp');assert.equal(points(null),'Sin información')
})
const cache=resolve('node_modules/.cache/profiles-tests');mkdirSync(cache,{recursive:true})
const result=buildSync({entryPoints:['src/features/profiles/ProfileVisuals.tsx'],bundle:true,write:false,platform:'node',format:'esm',jsx:'automatic',packages:'external'})
const modulePath=resolve(cache,'visuals.mjs');writeFileSync(modulePath,result.outputFiles[0].text)
const {RateComparison}=await import(pathToFileURL(modulePath).href)
test('Visualización explica ausencias, denominador indefinido y soporte reducido', () => {
  for(const [status,label] of [['missing','Sin información'],['undefined','Sin base para calcular'],['unavailable_category','Categoría no disponible']]){
    const html=renderToStaticMarkup(createElement(RateComparison,{observed:null,reference:null,label:'Prueba',status}))
    assert.ok(html.includes(label));assert.ok(!html.includes('width:0%'))
  }
  const html=renderToStaticMarkup(createElement(RateComparison,{observed:0,reference:.5,label:'Prueba',status:'low_support'}))
  assert.ok(html.includes('0.00 %'));assert.ok(html.includes('soporte reducido'));assert.ok(html.includes('width:0%'))
})

async function bundleModule(entry,name){
  const result=buildSync({entryPoints:[entry],bundle:true,write:false,platform:'node',format:'esm',jsx:'automatic',packages:'external'})
  const path=resolve(cache,name+'.mjs');writeFileSync(path,result.outputFiles[0].text)
  return import(pathToFileURL(path).href)
}
const presentation=await bundleModule('src/features/profiles/profilePresentation.ts','presentation')
const {ProfileComparePanel}=await bundleModule('src/features/profiles/ProfileComparePanel.tsx','comparison')
const {EnrichedProfileDetail}=await bundleModule('src/features/profiles/EnrichedProfileDetail.tsx','detail')
const {TransversalFinding}=await bundleModule('src/features/profiles/TransversalFinding.tsx','finding')
const enriched=enrichProfiles(base,validateProfileEnrichment(payload),2024)
test('Seis nombres acordados exactos sin cambiar IDs ni números',()=>{
  assert.deepEqual(Object.values(presentation.profileNames),['Jóvenes con mayor participación','Jóvenes con menor participación','Adultos con mayor participación','Adultos con menor participación','Personas mayores con mayor participación','Personas mayores con menor participación'])
  for(const p of enriched){assert.equal(p.name,presentation.profileNames[p.id]);assert.equal(p.enriched.nameStatus,'agreed')}
  assert.equal(payload.namesStatus,'agreed')
})
test('Orden U/R/M no muta datos y brechas usan tasas con soporte, no composición',()=>{
  for(const p of payload.profiles){
    const before=JSON.stringify(p.sectionCells)
    assert.deepEqual(presentation.orderedSections(p.sectionCells).map(c=>c.code),['U','R','M'])
    assert.equal(JSON.stringify(p.sectionCells),before)
    const women=p.sexCells.find(c=>c.code==='1'),men=p.sexCells.find(c=>c.code==='0')
    assert.equal(presentation.sexRateDifference(p.sexCells),(women.participation-men.participation)*100)
  }
  const cells=structuredClone(payload.profiles[0].sexCells);cells[0].participation=null
  assert.equal(presentation.sexRateDifference(cells),null)
  cells[0].participation=0;cells[0].status='low_support'
  assert.equal(presentation.sexRateDifference(cells),null)
  assert.ok(presentation.sectionDifferenceText([]).includes('información suficiente'))
})
test('Fichas conservan conteos en detalles; tres KPI y hallazgos específicos antes de gráficas',()=>{
  for(const p of enriched){
    const html=renderToStaticMarkup(createElement(EnrichedProfileDetail,{profile:p,dataset:{year:2024,source:'INE',profiles:enriched,enrichment:payload},onClose:()=>{}}))
    assert.ok(html.includes(p.name));assert.ok(html.includes('¿Qué revelan los datos?'))
    assert.ok(html.indexOf('pp-summary-kpis')<html.indexOf('pp-character-title'))
    assert.ok(html.indexOf('pp-character-title')<html.indexOf('pp-sex-title'))
    assert.ok(html.includes(new Intl.NumberFormat('es-MX').format(p.enriched.counts.LN)))
    assert.ok(!html.includes('<details open'))
  }
})
test('Comparador compacto distingue cero, uno, dos y tres perfiles',()=>{
  const render=n=>renderToStaticMarkup(createElement(ProfileComparePanel,{profiles:enriched.slice(0,n),year:2024,onRemove:()=>{},onAdd:()=>{},onClear:()=>{}}))
  assert.ok(render(0).includes('Elige dos o tres'))
  assert.ok(render(1).includes('Añade otro'));assert.ok(!render(1).includes('pp-compare-columns'))
  for(const n of [2,3]){const html=render(n);assert.equal((html.match(/data-compared-profile=/g)??[]).length,n);assert.ok(html.includes('Referencia comparable'))}
})
test('Hallazgo muestra ambos estimandos en puntos, sin barra de progreso ni tasas base inventadas',()=>{
  const html=renderToStaticMarkup(createElement(TransversalFinding,{finding:payload.transversalFinding}))
  assert.ok(html.includes('3.82 pp'));assert.ok(html.includes('5.30 pp'));assert.ok(html.includes('pp-contrast-dots'))
  assert.ok(!html.includes('pp-contrast-scale'));assert.ok(!html.includes('progressbar'));assert.ok(!html.includes('8.73'))
})
