import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { loadMapModule } from './load_map_module.mjs'
const { validateSectionPayload, validateSectionProfile, sectionTypes, sectionValue, rankSectionTerritories, dominantSectionValue, dominantSectionLabel } = await loadMapModule('sectionStatistics')
const { layerValue, thematicFill } = await loadMapModule('thematicData')
const { buildTerritoryHighlights } = await loadMapModule('electoralInterpretation')
const read = path => JSON.parse(readFileSync(path, 'utf8'))
const base = 'public/data/territorial/sections/'
const fields = ['LN', 'SV', 'NV', 'NS', 'source_row_count']

test('U/R/M: integridad del export y conciliación nacional, estatal y municipal en seis elecciones', () => {
  const manifest = read(base + 'manifest.json')
  for (const [name, hash] of Object.entries(manifest.files)) assert.equal(createHash('sha256').update(readFileSync(base + name)).digest('hex'), hash)
  let municipalities = 0
  for (const year of [2009, 2012, 2015, 2018, 2021, 2024]) {
    const index = validateSectionPayload(read(`${base}${year}/index.json`), year, null)
    assert.equal(index.states.length, 32)
    const summary = read(`public/data/territorial/summaries/${year}/national.json`)
    assert.deepEqual(index.national.totals, summary.totals)
    for (const state of index.states) {
      const file = validateSectionPayload(read(`${base}${year}/${state.code}.json`), year, state.code)
      const original = read(`public/data/territorial/${year}/${state.code}.json`).data
      assert.equal(file.data.length, original.length)
      for (const field of fields) assert.equal(file.data.reduce((sum, profile) => sum + profile.totals[field], 0), state.totals[field])
      for (const profile of file.data) {
        municipalities++
        assert.deepEqual(profile.totals, original.find(row => row.ine_code === profile.code).totals)
        assert.ok(Math.abs(sectionTypes.reduce((sum, kind) => sum + sectionValue(profile, kind, false).value, 0) - 1) < 1e-12)
        for (const kind of sectionTypes) {
          const cell = profile.sections.find(row => row.section_type === kind)
          const rate = sectionValue(profile, kind, true)
          assert.equal(rate.denominator, cell ? cell.SV + cell.NV : 0)
          assert.equal(rate.value, cell && cell.SV + cell.NV > 0 ? cell.SV / (cell.SV + cell.NV) : null)
          const key = { U: 'section_urban', R: 'section_rural', M: 'section_mixed' }[kind]
          assert.deepEqual(layerValue(null, key, [], true, profile), sectionValue(profile, kind, false))
          assert.deepEqual(layerValue(null, key + '_turnout', [], true, profile), rate)
        }
      }
    }
  }
  assert.equal(municipalities, 14779)
})

test('ceros conciliados, denominador cero, soporte, NS, ausencias y contratos inválidos se distinguen', () => {
  const profile = { code:'01001', name:'Ejemplo', complete:true, totals:{LN:200,SV:80,NV:100,NS:20,source_row_count:10}, sections:[{section_type:'U',LN:200,SV:80,NV:100,NS:20,source_row_count:10}] }
  validateSectionProfile(profile)
  assert.equal(sectionValue(profile,'R',false).value,0)
  assert.equal(sectionValue(profile,'R',false).status,'defined')
  assert.equal(sectionValue(profile,'R',true).value,null)
  assert.equal(sectionValue(profile,'U',true).highNs,true)
  assert.equal(sectionValue(null,'U',false).status,'missing')
  assert.equal(sectionValue(profile,'U',false,false).status,'unmapped')
  const sparse=structuredClone(profile); sparse.sections[0].source_row_count=1;sparse.totals.source_row_count=1
  assert.equal(sectionValue(sparse,'U',true).status,'low_support')
  for (const mutate of [p=>p.sections.push(p.sections[0]),p=>p.sections[0].section_type='X',p=>p.totals.LN++,p=>p.complete=false,p=>p.sections[0].SV=null]) {
    const invalid=structuredClone(profile);mutate(invalid);assert.throws(()=>validateSectionProfile(invalid))
  }
  const index=read(base+'2024/index.json')
  assert.throws(()=>validateSectionPayload(index,2021,null))
  assert.throws(()=>validateSectionPayload(index,2024,'01'))
})

test('ranking por fracción exacta y hallazgo máximo uno por tipo, sin inventar diferencias', () => {
  const profile = read(base+'2024/index.json').national
  const findings=buildTerritoryHighlights(profile.totals,true,null,false,profile)
  assert.ok(findings.length<=3);assert.equal(findings.filter(row=>row.id==='section').length,1)
  assert.ok(findings.find(row=>row.id==='section').text.includes('sin ajuste demográfico'))
  const undefinedRates=structuredClone(profile)
  for(const cell of undefinedRates.sections) { cell.SV=0;cell.NV=0;cell.NS=cell.LN }
  assert.equal(buildTerritoryHighlights(undefinedRates.totals,true,null,false,undefinedRates).filter(row=>row.id==='section').length,0)
  const rows=[...sectionTypes].reverse().map((kind,i)=>({code:String(i),name:kind,ineCode:null,result:sectionValue(profile,kind,false)}))
  const ranked=rankSectionTerritories(rows)
  assert.deepEqual(ranked.map(row=>row.name),['U','R','M'])
  assert.deepEqual(rows.map(row=>row.name),['M','R','U'])
  const exact=[{code:'2',name:'mayor',ineCode:null,result:{...rows[0].result,status:'defined',numerator:100001,denominator:1000000,value:.100001}}, {code:'1',name:'menor',ineCode:null,result:{...rows[0].result,status:'defined',numerator:100000,denominator:1000000,value:.1}}]
  assert.equal(rankSectionTerritories(exact)[0].name,'mayor')
})

test('predominante categórico: máximo sin redondeo, empates, soporte y ausencias sin cuantiles', () => {
  const profile = values => {
    const sections=values.map(([section_type,LN,source_row_count=10])=>({section_type,LN,SV:Math.floor(LN/2),NV:LN-Math.floor(LN/2),NS:0,source_row_count}))
    const totals=Object.fromEntries(fields.map(field=>[field,sections.reduce((sum,cell)=>sum+cell[field],0)]))
    return {code:'01001',name:'Ejemplo',complete:true,totals,sections}
  }
  const noScale={classes:[],breaks:[],count:0,distinctCount:0}
  const p=profile([['U',400],['R',350],['M',250]])
  const result=dominantSectionValue(p)
  assert.equal(result.value,null) // La categoría no se trata como porcentaje ni código ordinal.
  assert.equal(result.numerator/result.denominator,.4)
  assert.equal(result.status,'defined');assert.deepEqual(result.dominantTypes,['U'])
  assert.equal(dominantSectionLabel(result),'Urbana')
  assert.equal(thematicFill(result,noScale),'var(--atlas-section-U)')
  assert.deepEqual(layerValue(null,'section_dominant',[],true,p),result)
  for(const [kind,fill] of [['R','var(--atlas-section-R)'],['M','var(--atlas-section-M)']]) assert.equal(thematicFill(dominantSectionValue(profile([[kind,1000]])),noScale),fill)
  const tie=dominantSectionValue(profile([['R',400],['U',400],['M',200]]))
  assert.deepEqual(tie.dominantTypes,['U','R']);assert.equal(dominantSectionLabel(tie),'Empate · Urbana / Rural')
  assert.equal(thematicFill(tie,noScale),'url(#atlas-section-tie)')
  assert.equal(dominantSectionValue(profile([['U',300],['R',300],['M',300]])).dominantTypes.length,3)
  assert.deepEqual(dominantSectionValue(profile([['U',10001],['R',10000]])).dominantTypes,['U'])
  const sparse=dominantSectionValue(profile([['U',400,1],['R',350],['M',250]]))
  assert.equal(sparse.status,'low_support');assert.equal(thematicFill(sparse,noScale),'var(--atlas-low-support)')
  assert.equal(dominantSectionValue(profile([['U',0]])).status,'undefined')
  assert.equal(dominantSectionValue(null).status,'missing');assert.equal(dominantSectionValue(p,false).status,'unmapped')
  assert.equal(thematicFill(dominantSectionValue(null),noScale),'var(--atlas-no-data)')
  const highNs=profile([['U',400],['R',350]])
  highNs.sections[0].NS=100;highNs.sections[0].NV-=100;highNs.totals.NS=100;highNs.totals.NV-=100
  assert.equal(dominantSectionValue(highNs).highNs,true);assert.deepEqual(dominantSectionValue(highNs).dominantTypes,['U'])
})
