import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs'
import {resolve} from 'node:path'
import {pathToFileURL} from 'node:url'
import {buildSync} from 'esbuild'
import {createElement} from 'react'
import {renderToStaticMarkup} from 'react-dom/server'
import {describeObservedParticipation,percentagePointsHelp,comparableReferenceHelp,countDefinitions} from '../src/components/statisticsPresentation.ts'

test('Lectura de cada cien usa participación especificada real y sigue cada elección',()=>{
  for(const year of [2009,2012,2015,2018,2021,2024]){
    const totals=JSON.parse(readFileSync(`public/data/participamx_multiyear/elections/${year}/national_statistics.json`,'utf8')).data[0]
    const rate=totals.SV/(totals.SV+totals.NV)*100
    assert.ok(Math.abs(rate-totals.participation_observed*100)<1e-10)
    assert.ok(describeObservedParticipation(rate).includes(`aproximadamente ${Math.round(rate)} `))
    assert.ok(describeObservedParticipation(rate).includes('condición de voto especificada'))
    assert.notEqual(rate,totals.SV/totals.LN*100,`${year}: no confundir con tasa nominal`)
  }
})
test('Ausencia, tasa cero y extremos válidos no se confunden',()=>{
  for(const value of [null,undefined,NaN,Infinity,-1,101])assert.ok(describeObservedParticipation(value).includes('No hay una tasa'))
  assert.ok(describeObservedParticipation(0).includes('aproximadamente 0 registraron'))
  assert.ok(describeObservedParticipation(100).includes('aproximadamente 100 registraron'))
  assert.ok(describeObservedParticipation(1).includes('1 registró'))
})
test('Redondeo solamente en la frase: valor original no se redondea antes de convertir',()=>{
  assert.ok(describeObservedParticipation(59.4999).includes('aproximadamente 59 '))
  assert.ok(describeObservedParticipation(59.5001).includes('aproximadamente 60 '))
  assert.ok(percentagePointsHelp.includes('no un aumento del 5 %'))
  assert.ok(comparableReferenceHelp.includes('misma elección, grupo de edad y sexo'))
  assert.deepEqual(countDefinitions.map(c=>c[0]),['LN','SV','NV','NS'])
})
const cache=resolve('node_modules/.cache/statistics-tests');mkdirSync(cache,{recursive:true})
async function component(path,name){const r=buildSync({entryPoints:[path],bundle:true,write:false,platform:'node',format:'esm',jsx:'automatic',packages:'external'});const target=resolve(cache,name+'.mjs');writeFileSync(target,r.outputFiles[0].text);return import(pathToFileURL(target).href)}
const {StatisticalHelp}=await component('src/components/StatisticalHelp.tsx','help')
const {Methodology}=await component('src/features/methodology/Methodology.tsx','methodology')
const {TrendChart}=await component('src/features/dashboard/TrendChart.tsx','trend')
test('Ayuda nativa desplegable conserva bases, no especificación y referencia',()=>{
  const html=renderToStaticMarkup(createElement(StatisticalHelp))
  assert.ok(html.includes('<details'));assert.ok(!html.includes('<details open'))
  for(const term of ['pp = puntos porcentuales','SV + NV','sobre LN','no personas','no se sustituye por cero'])assert.ok(html.includes(term),term)
})
test('Metodología mantiene fórmulas visibles, criterios y límites históricos',()=>{
  const html=renderToStaticMarkup(createElement(Methodology))
  for(const term of ['SV / (SV + NV) × 100','SV / LN × 100','cinco filas fuente','100 registros','geometrías de 2024','no garantizan','no demuestran','U = Urbana, R = Rural y M = Mixta'])assert.ok(html.includes(term),term)
  assert.ok(html.includes('mide qué proporción'))
})
test('Gráfica temporal conserva huecos NULL y tabla accesible con cifras originales',()=>{
  const points=[{year:2009,value:44.082},{year:2012,value:null},{year:2015,value:47.084},{year:2024,value:59.67002944436727}]
  const html=renderToStaticMarkup(createElement(TrendChart,{points,selectedYear:2024,onSelectYear:()=>{},demo:false}))
  assert.equal((html.match(/class="trend-line"/g)??[]).length,2)
  assert.ok(html.includes('59.7%'));assert.ok(html.includes('Sin información'))
  assert.ok(html.includes('role="region"'));assert.ok(html.includes('<table>'))
  assert.ok(!html.includes('59.67002944436727%'))
})
