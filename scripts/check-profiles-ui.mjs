// Navegador real sobre dist/: flujo de perfiles, temas, teclado, ausencias y años históricos.
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { createServer as createTcpServer } from 'node:net'
import { spawn } from 'node:child_process'
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, existsSync } from 'node:fs'
import { resolve, extname, join, sep } from 'node:path'

const root=resolve('dist'),cache=resolve('node_modules/.cache/profiles-ui')
mkdirSync(cache,{recursive:true})
assert.ok(existsSync(join(root,'index.html')),'Ejecutar npm run build')
const payload=JSON.parse(readFileSync('public/data/profiles/enriched-2024.json','utf8'))
let enrichmentMode='normal'
const server=createServer((request,response)=>{
  const path=resolve(root,'.'+decodeURIComponent(new URL(request.url,'http://localhost').pathname))
  if(path!==root&&!path.startsWith(root+sep)){response.writeHead(403).end();return}
  if(path.endsWith('enriched-2024.json')&&enrichmentMode!=='normal'){
    response.setHeader('Content-Type','application/json')
    if(enrichmentMode==='error'){response.writeHead(503).end('{}');return}
    const invalid=structuredClone(payload);invalid.year=2021;response.end(JSON.stringify(invalid));return
  }
  const target=path===root?join(root,'index.html'):path
  try{response.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'})[extname(target)]??'application/octet-stream');response.end(readFileSync(target))}
  catch{response.writeHead(404).end()}
})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
const reservation=createTcpServer();await new Promise(resolve=>reservation.listen(0,'127.0.0.1',resolve))
const port=reservation.address().port;await new Promise(resolve=>reservation.close(resolve))
const executable=process.env.CHROME_PATH??'C:/Program Files/Google/Chrome/Application/chrome.exe'
assert.ok(existsSync(executable),'Chrome no disponible')
const browser=spawn(executable,['--headless=new','--no-first-run','--no-default-browser-check',`--remote-debugging-port=${port}`,`--user-data-dir=${mkdtempSync(join(cache,'chrome-'))}`,'about:blank'],{windowsHide:true,stdio:'ignore'})
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms))
let socket,id=0
const pending=new Map(),errors=[],checks=[]
function send(method,params={}){return new Promise((resolve,reject)=>{const key=++id;const timer=setTimeout(()=>{pending.delete(key);reject(new Error(`CDP timeout ${method}`))},15000);pending.set(key,{resolve,reject,timer});socket.send(JSON.stringify({id:key,method,params}))})}
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function wait(expression){const until=Date.now()+15000;while(Date.now()<until){if(await evaluate(expression))return;await sleep(100)}throw new Error(`Tiempo agotado: ${expression}`)}
async function click(selector){await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`)}
async function screenshot(name){const r=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,fromSurface:true});writeFileSync(join(cache,name+'.png'),Buffer.from(r.data,'base64'))}
async function theme(value){if(await evaluate(`document.documentElement.dataset.theme!==${JSON.stringify(value)}`))await click('.theme-toggle');await wait(`document.documentElement.dataset.theme===${JSON.stringify(value)}`)}
async function viewport(width,height=1000){await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<620});await sleep(100)}
async function checkContrast(mode){
  const ratios=await evaluate(`(() => {
    const rgb=c=>c.match(/[\\d.]+/g).map(Number);
    const luminance=c=>rgb(c).slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
    return ['.pp-card h3','.pp-card-criterion','.pp-kicker','.pp-card-metrics dd','.pp-card .pp-button'].map(selector=>{
      const element=document.querySelector(selector);let node=element,background='rgb(255,255,255)';
      while(node){const c=getComputedStyle(node).backgroundColor;const channels=rgb(c);if(channels.length===3||channels[3]>0.99){background=c;break}node=node.parentElement}
      const a=luminance(getComputedStyle(element).color),b=luminance(background);
      return {selector,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
    })
  })()`)
  for(const row of ratios)assert.ok(row.ratio>=4.5,`${mode}: ${row.selector} ${row.ratio}`)
  record(`Contraste de texto ≥4.5:1 en ${mode}`,{ratios})
}
function record(name,details={}){checks.push({name,...details});console.log('✓ '+name)}
const formatted=n=>new Intl.NumberFormat('es-MX',{minimumFractionDigits:2,maximumFractionDigits:2}).format(n)
try{
  let pages
  for(let n=0;n<100;n++){try{pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();if(pages.length)break}catch{}await sleep(100)}
  assert.ok(pages?.length,'Chrome no inició')
  socket=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl)
  await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true})})
  socket.addEventListener('message',event=>{const r=JSON.parse(event.data);if(r.id&&pending.has(r.id)){const p=pending.get(r.id);clearTimeout(p.timer);pending.delete(r.id);r.error?p.reject(new Error(JSON.stringify(r.error))):p.resolve(r.result)}else if(r.method==='Runtime.exceptionThrown')errors.push(r.params.exceptionDetails)})
  await send('Page.enable');await send('Runtime.enable');await send('Page.bringToFront')
  await send('Emulation.setFocusEmulationEnabled',{enabled:true});await viewport(1480)
  await send('Page.navigate',{url:`http://127.0.0.1:${server.address().port}/#perfiles`})
  await wait(`document.querySelectorAll('[data-profile-card]').length===6 && !!document.querySelector('[data-transversal-finding]')`)
  assert.deepEqual(new Set(await evaluate(`[...document.querySelectorAll('[data-profile-card]')].map(n=>n.dataset.profileCard)`)),new Set(payload.profiles.map(p=>p.id)))
  assert.equal(await evaluate(`document.querySelectorAll('[data-transversal-finding]').length`),1)
  assert.deepEqual(await evaluate(`[...document.querySelectorAll('[data-profile-card] h3')].map(n=>n.textContent)`),payload.profiles.map(p=>p.name))
  assert.ok(await evaluate(`!/(V1|V2|subsegmento|denominador|cambio de signo|variación total)/i.test(document.querySelector('.participation-profiles').innerText)`))
  assert.equal(await evaluate(`document.querySelector('.pp-compare-panel').dataset.comparisonCount`),'0')
  assert.ok(await evaluate(`document.querySelector('.pp-transversal').innerText.includes('3.82 pp') && document.querySelector('.pp-transversal').innerText.includes('5.30 pp') && !document.querySelector('.pp-contrast-scale')`))
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.pp-grid')).gridTemplateColumns.split(' ').length`),3)
  await theme('light');await checkContrast('claro');await screenshot('desktop-light-list')
  record('Seis IDs originales, cuadrícula de tres columnas y V2.1 separado')
  for(const p of payload.profiles){
    const selector=`[data-open-profile="${p.id}"]`
    await evaluate(`document.querySelector(${JSON.stringify(selector)}).focus()`)
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r',unmodifiedText:'\r'})
    await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13})
    await wait(`document.querySelector('[data-profile-detail]')?.dataset.profileDetail===${JSON.stringify(p.id)}`)
    await wait(`document.activeElement.id==='pp-detail-title'`)
    assert.ok(await evaluate(`document.getElementById('pp-detail-title').getBoundingClientRect().top>=80`),'Título visible bajo navegación fija')
    assert.ok(await evaluate(`!/(V1|V2|subsegmento|denominador|cambio de signo|variación total)/i.test(document.querySelector('[data-profile-detail]').innerText)`))
    const detail=await evaluate(`document.querySelector('[data-profile-detail]').textContent`)
    assert.ok(detail.includes(formatted(p.participation*100)),p.id)
    assert.ok(detail.includes(formatted(p.reference*100)),p.id)
    assert.ok(detail.includes(new Intl.NumberFormat('es-MX').format(p.quality.signReversals)),p.id)
    assert.equal(await evaluate(`document.querySelectorAll('.pp-composition .pp-stack').length`),1)
    assert.deepEqual(await evaluate(`[...document.getElementById('pp-section-title').closest('section').querySelectorAll('.pp-composition .pp-stack span')].map(n=>n.dataset.section)`),['U','R','M'])
    const women=p.sexCells.find(c=>c.code==='1'),men=p.sexCells.find(c=>c.code==='0')
    assert.ok(await evaluate(`document.querySelector('[data-profile-insight="sex"]').textContent.includes(${JSON.stringify(formatted(Math.abs(women.participation-men.participation)*100))})`))
    await click('[data-sex-view="composition"]')
    assert.equal(await evaluate(`document.querySelectorAll('.pp-composition .pp-stack').length`),2)
    await click('[data-sex-view="participation"]')
    await click('.pp-joint-disclosure summary')
    for(const typ of ['U','R','M']){
      await click(`[data-profile-section="${typ}"]`)
      await wait(`document.querySelector('.pp-joint-detail').dataset.selectedSection===${JSON.stringify(typ)}`)
      const text=await evaluate(`document.querySelector('.pp-joint-detail').textContent`)
      for(const cell of p.jointCells.filter(c=>c.code===typ)) assert.ok(text.includes(formatted(cell.participation*100)),`${p.id}/${typ}/${cell.sexCode}`)
    }
    assert.equal(await evaluate(`document.querySelector('[data-category-status]').dataset.categoryStatus`),'low_support')
    if(p.id==='young_favorable'){
      await screenshot('desktop-light-detail')
      await theme('dark');await screenshot('desktop-dark-detail');await theme('light')
    }
    await click('.pp-back')
    await wait(`document.querySelectorAll('[data-profile-card]').length===6 && document.activeElement.dataset.openProfile===${JSON.stringify(p.id)}`)
  }
  record('Las seis fichas abren con teclado, muestran cifras/cruces reales y restauran el foco al volver')
  await click('.pp-card .pp-compare')
  assert.ok(await evaluate(`document.querySelector('.pp-compare-panel').innerText.includes('Añade otro')`))
  await evaluate(`document.querySelectorAll('.pp-card .pp-compare')[1].click()`)
  await wait(`document.querySelectorAll('[data-compared-profile]').length===2 && document.activeElement.id==='pp-comparison-title'`)
  assert.ok(await evaluate(`document.getElementById('pp-comparison-title').getBoundingClientRect().top>=80 && document.getElementById('pp-comparison-title').getBoundingClientRect().top<200`))
  await screenshot('desktop-light-comparison-two')
  await click('.pp-compare-tools .pp-button')
  assert.ok(await evaluate(`document.activeElement===document.querySelector('.pp-catalog-heading h3')`))
  await evaluate(`document.querySelectorAll('.pp-card .pp-compare')[2].click()`)
  await wait(`document.querySelectorAll('[data-compared-profile]').length===3 && document.activeElement.id==='pp-comparison-title'`)
  for(const view of ['sex','section']){
    await click(`[data-comparison-view="${view}"]`)
    assert.equal(await evaluate(`document.querySelectorAll('.pp-compare-column .pp-rate').length`),view==='sex'?6:9)
    const ids=payload.profiles.slice(0,3)
    for(const p of ids){const visible=await evaluate(`document.querySelector('[data-compared-profile="${p.id}"]').innerText`);for(const c of view==='sex'?p.sexCells:p.sectionCells)assert.ok(visible.includes(formatted(c.participation*100)),`${p.id}/${view}`)}
    await click('[data-comparison-measure="composition"]')
    assert.equal(await evaluate(`document.querySelectorAll('.pp-compare-column .pp-stack').length`),3)
    if(view==='section')assert.deepEqual(await evaluate(`[...document.querySelector('.pp-compare-column .pp-stack').children].map(n=>n.dataset.section)`),['U','R','M'])
    await click('[data-comparison-measure="participation"]')
  }
  await screenshot('desktop-light-comparison-three');await click('[data-comparison-view="summary"]')
  await click('.pp-compare-column .pp-compare-remove')
  await wait(`document.querySelectorAll('[data-compared-profile]').length===2 && document.activeElement.id==='pp-comparison-title'`)
  await evaluate(`document.querySelectorAll('.pp-card .pp-compare')[0].click()`)
  await wait(`document.querySelectorAll('[data-compared-profile]').length===3 && document.activeElement.id==='pp-comparison-title'`)
  record('Comparador: vacío, una selección, dos/tres perfiles, foco inmediato, cifras, sexo y U/R/M ordenado')
  await theme('dark');await checkContrast('oscuro');await screenshot('desktop-dark-list')
  await viewport(950)
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.pp-grid')).gridTemplateColumns.split(' ').length`),2)
  assert.ok(await evaluate(`document.documentElement.scrollWidth<=innerWidth+1`))
  await screenshot('tablet-dark-list');record('Tableta: dos columnas sin desbordamiento horizontal')
  await viewport(390,844)
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.pp-grid')).gridTemplateColumns.split(' ').length`),1)
  assert.ok(await evaluate(`document.documentElement.scrollWidth<=innerWidth+1`))
  await click('.pp-comparison-dock .pp-button');await screenshot('mobile-dark-comparison-three')
  await evaluate(`document.querySelector('.pp-compare-scroll').scrollLeft=300`)
  assert.ok(await evaluate(`document.querySelector('.pp-compare-scroll').scrollLeft>0`))
  assert.ok(await evaluate(`document.documentElement.scrollWidth<=innerWidth+1`))
  await screenshot('mobile-dark-list');await theme('light');await screenshot('mobile-light-list')
  await click('[data-open-profile="adult_unfavorable"]')
  await wait(`!!document.querySelector('[data-profile-detail="adult_unfavorable"]')`)
  await wait(`document.activeElement.id==='pp-detail-title'`)
  assert.ok(await evaluate(`document.documentElement.scrollWidth<=innerWidth+1`));await screenshot('mobile-light-detail')
  await theme('dark');await screenshot('mobile-dark-detail')
  await click('.pp-back');await wait(`!!document.querySelector('.pp-compare-tools')`)
  await click('.pp-compare-tools .pp-compare');await wait(`document.querySelector('.pp-compare-panel').dataset.comparisonCount==='0' && document.activeElement.id==='pp-comparison-title'`)
  assert.equal(await evaluate(`document.querySelectorAll('[data-comparison-selected="true"]').length`),0)
  record('Móvil 390px: lista y detalle en claro/oscuro, sin recortes horizontales')
  await click('[data-election-year="2021"]')
  await wait(`document.querySelector('.participation-profiles')?.dataset.profileYear==='2021' && document.querySelectorAll('[data-profile-card]').length===6`)
  assert.equal(await evaluate(`document.querySelectorAll('[data-transversal-finding]').length`),0)
  assert.ok(await evaluate(`document.querySelector('[data-category-status="unavailable_category"]').textContent.includes('La fuente de esta elección no incluye un desglose para personas no binarias')`))
  record('Cambio a 2021 conserva V1 y no filtra caracterización ni hallazgo de 2024')
  for(const mode of ['error','invalid']){
    enrichmentMode=mode;await send('Page.reload',{ignoreCache:true})
    await wait(`document.querySelectorAll('[data-profile-card]').length===6 && !!document.querySelector('.pp-year-note[role="alert"]')`)
    assert.equal(await evaluate(`document.querySelectorAll('[data-transversal-finding]').length`),0)
    enrichmentMode='normal';await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Reintentar caracterización').click()`)
    await wait(`!!document.querySelector('[data-transversal-finding]')`)
  }
  record('Errores HTTP y datos de año incorrecto: V1 disponible, sin mezclar datos, con reintento funcional')
  assert.equal(errors.length,0,JSON.stringify(errors))
  writeFileSync(join(cache,'results.json'),JSON.stringify({status:'passed',checks,errors},null,2))
  console.log('Capturas y resultados: '+cache)
}catch(error){
  try{await screenshot('failure')}catch{}
  let page=null
  try{page=await evaluate(`({url:location.href,text:document.body.innerText.slice(0,3000)})`)}catch{}
  writeFileSync(join(cache,'results.json'),JSON.stringify({status:'failed',error:String(error),checks,errors,page},null,2));throw error
}finally{
  if(socket?.readyState===WebSocket.OPEN){try{await send('Browser.close')}catch{}socket.close()}
  browser.kill();server.closeAllConnections();await new Promise(resolve=>server.close(resolve))
}
