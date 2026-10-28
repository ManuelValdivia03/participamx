import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { createThematicScale, scaleClassIndex, formatScaleInterval } from '../src/features/map/thematicScale.ts'

test('cuantiles: min/mediana/máximo, límites inclusivos y empates indivisibles', () => {
  const values = Array.from({length: 100}, (_,i)=>i/100)
  const scale = createThematicScale(values)
  assert.deepEqual(scale.breaks, [.19,.39,.59,.79])
  assert.deepEqual(scale.classes.map(row=>row.count), [20,20,20,20,20])
  assert.deepEqual([0,.5,.99].map(x=>scaleClassIndex(x,scale)), [0,2,4])
  assert.equal(scaleClassIndex(.19,scale),0)
  assert.equal(scaleClassIndex(.19001,scale),1)
  assert.equal(scaleClassIndex(null,scale),null)
  assert.equal(scaleClassIndex(NaN,scale),null)
  assert.equal(scaleClassIndex(1,scale),null)
  assert.ok(formatScaleInterval(scale.classes[1],2).startsWith('>19–39'))
  const tied = [...Array(90).fill(.4),.5,.6,.7,.8,.9,1]
  const reduced = createThematicScale(tied)
  assert.deepEqual(reduced.breaks,[.4])
  assert.equal(reduced.classes.length,2)
  assert.equal(reduced.classes.reduce((n,row)=>n+row.count,0),tied.length)
  assert.deepEqual(reduced,createThematicScale(tied.toReversed()))
})

test('pocos valores, ceros y nulos: clases sin inventar variación ni categorías', () => {
  for (const values of [[],[.4],[.4,.4],[0,1],[0,.3,.5,1]]) {
    const scale=createThematicScale([...values,null,NaN,Infinity])
    assert.equal(scale.classes.length,new Set(values).size)
    assert.equal(scale.count,values.length)
    assert.ok(scale.classes.every(row=>row.count>0))
    if (scale.classes.length===1) assert.equal(scale.classes[0].colorLevel,2)
  }
  assert.throws(()=>createThematicScale([-.01]))
  assert.throws(()=>createThematicScale([1.1]))
})

test('cuantiles permanentes: valores originales intactos y colores relativos al ámbito', () => {
  const values=Object.freeze([1,.5,null,0,.5,.25])
  const before=[...values], a=createThematicScale(values), b=createThematicScale([.4,.5,.6])
  assert.deepEqual(values,before)
  assert.notDeepEqual(a.breaks,b.breaks)
  assert.equal(scaleClassIndex(.5,a),2)
  assert.equal(scaleClassIndex(.5,b),1)
  assert.equal(scaleClassIndex(0,a),0)
  assert.equal(scaleClassIndex(1,a),3)
  assert.equal(createThematicScale([]).classes.length,0)
})

test('paletas: cinco niveles de luminancia ordenada también bajo simulaciones cromáticas', () => {
  const css=readFileSync('src/styles/territorial-atlas.css','utf8')
  const palettes=[...css.matchAll(/--atlas-color-0:(#[a-f\d]{6});--atlas-color-1:(#[a-f\d]{6});--atlas-color-2:(#[a-f\d]{6});--atlas-color-3:(#[a-f\d]{6});--atlas-color-4:(#[a-f\d]{6});/g)]
  assert.equal(palettes.length,12)
  // Simulaciones lineales de protanopía/deuteranopía/tritanopía; diagnóstico, no certificación.
  const transforms=[[[1,0,0],[0,1,0],[0,0,1]],[[.152286,1.052583,-.204868],[.114503,.786281,.099216],[-.003882,-.048116,1.051998]],[[.367322,.860646,-.227968],[.280085,.672501,.047413],[-.01182,.04294,.968881]],[[1.255528,-.076749,-.178779],[-.078411,.930809,.147602],[.004733,.691367,.3039]]]
  for(const [paletteIndex,palette] of palettes.entries()) for(const transform of transforms) {
    const lum=palette.slice(1).map(hex=>{
      const rgb=hex.slice(1).match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4)
      const simulated=transform.map(row=>Math.max(0,Math.min(1,row.reduce((s,v,i)=>s+v*rgb[i],0))))
      return simulated[0]*.2126+simulated[1]*.7152+simulated[2]*.0722
    })
    const sign=Math.sign(lum[4]-lum[0])
    for(let i=1;i<5;i++) assert.ok(sign*(lum[i]-lum[i-1])>.025, `Niveles distintos: ${palette[0]}`)
    if(transform===transforms[0]) {
      const hex=paletteIndex<6?'#fffdf9':'#29212f'
      const rgb=hex.slice(1).match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4)
      const surface=rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722
      const contrast=(Math.max(surface,lum[4])+.05)/(Math.min(surface,lum[4])+.05)
      assert.ok(contrast>=4.5, `Texto de tarjeta: ${palette[5]} / ${hex}: ${contrast}`)
    }
  }
})
