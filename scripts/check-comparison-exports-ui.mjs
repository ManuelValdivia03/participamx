// Chrome real: hallazgos, lenguaje claro y comparación completa PDF/PNG.
import assert from 'node:assert/strict'
import {createServer} from 'node:http'
import {spawn} from 'node:child_process'
import {readFileSync,writeFileSync,mkdirSync,mkdtempSync,existsSync,renameSync} from 'node:fs'
import {resolve,join,extname,sep} from 'node:path'
const root=resolve('dist'),cache=resolve('node_modules/.cache/comparison-exports-ui'),downloads=join(cache,'downloads');mkdirSync(downloads,{recursive:true})
let failYear=null,delayYear=null
const server=createServer((req,res)=>{
 const path=resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname)),target=path===root?join(root,'index.html'):path
 if(path!==root&&!path.startsWith(root+sep)){res.writeHead(403).end();return}
 if(failYear&&path.endsWith(`enriched-${failYear}.json`)){res.writeHead(503).end();return}
 const reply=()=>{try{res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'})[extname(target)]??'application/octet-stream');res.end(readFileSync(target))}catch{res.writeHead(404).end()}}
 if(delayYear&&path.endsWith(`enriched-${delayYear}.json`))setTimeout(reply,650);else reply()
})
await new Promise(r=>server.listen(0,'127.0.0.1',r))
const reservation=createServer();await new Promise(r=>reservation.listen(0,'127.0.0.1',r));const port=reservation.address().port;await new Promise(r=>reservation.close(r))
const browser=spawn(process.env.CHROME_PATH??'C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless=new','--no-first-run','--no-default-browser-check',`--remote-debugging-port=${port}`,`--user-data-dir=${mkdtempSync(join(cache,'chrome-'))}`,'about:blank'],{windowsHide:true,stdio:'ignore'})
const sleep=ms=>new Promise(r=>setTimeout(r,ms)),pending=new Map(),errors=[],checks=[],exports=[];let socket,id=0
function send(method,params={}){return new Promise((resolve,reject)=>{const key=++id,timer=setTimeout(()=>reject(Error(method+' timeout')),20000);pending.set(key,{resolve,reject,timer});socket.send(JSON.stringify({id:key,method,params}))})}
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function wait(expression){for(let n=0;n<220;n++){if(await evaluate(expression))return;await sleep(100)}throw Error('Tiempo agotado: '+expression)}
async function click(selector){await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`)}
async function shot(name){const r=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,fromSurface:true});writeFileSync(join(cache,name+'.png'),Buffer.from(r.data,'base64'))}
async function viewport(width,height=1000){await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});await sleep(120)}
async function year(value){await click(`[role="radio"][data-election-year="${value}"]`)}
async function ready(value){await wait(`document.querySelector('.participation-profiles')?.dataset.profileYear==='${value}' && !document.querySelector('.pp-year-note[role="alert"]')`)}
async function file(path){for(let n=0;n<200;n++){if(existsSync(path)&&!existsSync(path+'.crdownload'))return readFileSync(path);await sleep(100)}throw Error('Descarga ausente: '+path)}

const ids=['young_favorable','young_unfavorable','adult_favorable','adult_unfavorable','older_favorable','older_unfavorable']
const payload=y=>JSON.parse(readFileSync('public/data/profiles/enriched-'+y+'.json','utf8'))
const cases=[[0,1],[0,3],[0,3,4]]
function filename(indices,y){return 'participamx_comparacion_'+indices.map(i=>String(i+1).padStart(2,'0')+'_'+(i<2?'jovenes':i<4?'adultos':'mayores')+'_'+(i%2?'menor':'mayor')).join('_')+'_'+y}
async function select(indices){if(await evaluate("!!document.querySelector('.pp-compare-tools .pp-compare')"))await click('.pp-compare-tools .pp-compare');else if(await evaluate("!!document.querySelector('.pp-selected-chip button')"))await click('.pp-selected-chip button');for(const i of indices)await click('[data-profile-card="'+ids[i]+'"] .pp-compare')}
async function checkState(y,indices){assert.deepEqual(await evaluate("[...document.querySelectorAll('[data-compared-profile]')].map(n=>n.dataset.comparedProfile)"),indices.map(i=>ids[i]));assert.equal(await evaluate("document.querySelector('.participation-profiles').dataset.profileYear"),String(y));assert.equal(await evaluate("document.querySelector('[data-comparison-view=\"section\"]').getAttribute('aria-pressed')"),'true');assert.equal(await evaluate("document.querySelector('[data-comparison-measure=\"composition\"]').getAttribute('aria-pressed')"),'true')}
try{
 let pages;for(let n=0;n<120;n++){try{pages=await(await fetch('http://127.0.0.1:'+port+'/json')).json();if(pages.length)break}catch{}await sleep(100)}
 socket=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise(r=>socket.addEventListener('open',r,{once:true}));socket.addEventListener('message',e=>{const r=JSON.parse(e.data);if(r.id&&pending.has(r.id)){const p=pending.get(r.id);clearTimeout(p.timer);pending.delete(r.id);r.error?p.reject(Error(JSON.stringify(r.error))):p.resolve(r.result)}else if(r.method==='Runtime.exceptionThrown')errors.push(r.params.exceptionDetails)})
 await send('Page.enable');await send('Runtime.enable');await send('Page.bringToFront');await send('Emulation.setFocusEmulationEnabled',{enabled:true});await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloads});await viewport(1480)
 await send('Page.navigate',{url:'http://127.0.0.1:'+server.address().port+'/#perfiles'});await ready(2024)
 assert.ok(await evaluate("[...document.querySelectorAll('[data-comparison-export]')].every(b=>b.disabled)"))
 await select([0]);assert.ok(await evaluate("[...document.querySelectorAll('[data-comparison-export]')].every(b=>b.disabled)"))
 await select([0,1]);await click('[data-comparison-view="section"]');await click('[data-comparison-measure="composition"]')
 for(const y of [2009,2012,2015,2018,2021,2024]){
  await year(y);await ready(y)
  if(y===2018&&await evaluate("document.documentElement.dataset.theme!=='dark'"))await click('.theme-toggle')
  if(y===2024&&await evaluate("document.documentElement.dataset.theme!=='light'"))await click('.theme-toggle')
  for(const indices of cases){
   await select(indices);await checkState(y,indices)
   assert.ok(!await evaluate("document.querySelector('.participation-profiles').innerText.includes('SEXO=')"))
   for(const format of ['pdf','png']){
    const path=join(downloads,filename(indices,y)+'.'+format);if(existsSync(path))renameSync(path,path.replace('.'+format,'-previous-'+Date.now()+'.'+format))
    await click('[data-comparison-export="'+format+'"]');const buffer=await file(path);await wait("!document.querySelector('[data-comparison-export=\"png\"]').disabled")
    assert.ok(await evaluate("document.querySelector('.pp-comparison-exports [role=status]').innerText.includes('preparada')"))
    if(format==='pdf')assert.equal(buffer.subarray(0,5).toString(),'%PDF-');else{assert.equal(buffer.readUInt32BE(16),1600);assert.equal(buffer.readUInt32BE(20),2357)}
    exports.push({year:y,ids:indices.map(i=>ids[i]),format,path,bytes:buffer.length})
    await checkState(y,indices)
   }
  }
  if([2009,2018,2024].includes(y))await shot('comparison-'+y)
  await click('[data-open-profile="young_favorable"]');await wait("!!document.querySelector('[data-profile-detail]')")
  assert.equal(await evaluate("document.querySelectorAll('[data-profile-insight]').length"),4)
  assert.ok(!await evaluate("document.querySelector('[data-profile-detail]').innerText.includes('SEXO=')"))
  assert.equal(await evaluate("getComputedStyle(document.querySelector('.pp-dimension-grid')).alignItems"),'start')
  assert.ok(await evaluate("document.querySelectorAll('.pp-detail>details:not([open])').length>=3"))
  for(const f of ['Cómo se calcularon estos datos','Cobertura y calidad de la información','Fuentes y limitaciones'])assert.ok(await evaluate("document.querySelector('[data-profile-detail]').innerText.includes("+JSON.stringify(f)+")"))
  if([2009,2018,2024].includes(y))await shot('detail-'+y)
  await click('.pp-back');await checkState(y,[0,3,4])
  console.log('✓ '+y+': 3 selecciones, PDF/PNG completos y detalle con 4 hallazgos')
 }
 // Una imagen fallida comunica el error y permite reintentar sin borrar la selección.
 await evaluate("window.originalToBlob=HTMLCanvasElement.prototype.toBlob;HTMLCanvasElement.prototype.toBlob=function(callback){callback(null)}")
 await click('[data-comparison-export="png"]');await wait("document.querySelector('.pp-comparison-exports [role=status]').innerText.includes('No se pudo')")
 await evaluate("HTMLCanvasElement.prototype.toBlob=window.originalToBlob");await checkState(2024,[0,3,4])
 checks.push('36 descargas comparativas: dos perfiles de igual/distinta edad y tres perfiles en las seis elecciones; selección, pestaña y medida conservadas')
 for(const width of [1480,950,390,320]){await viewport(width);assert.ok(await evaluate("document.documentElement.scrollWidth<=innerWidth+1"));if(width===390){await shot('comparison-mobile');await click('[data-open-profile="young_favorable"]');await wait("!!document.querySelector('[data-profile-detail]')");assert.ok(await evaluate("document.documentElement.scrollWidth<=innerWidth+1"));await shot('detail-mobile');await click('.pp-back')}}
 await viewport(950);await evaluate("document.querySelector('[data-comparison-export=\"pdf\"]').focus()");assert.equal(await evaluate("document.activeElement.dataset.comparisonExport"),'pdf')
 checks.push('Claro/oscuro, teclado, escritorio/tableta/móvil, errores recuperables y categorías legibles por elección')
 assert.equal(errors.length,0,JSON.stringify(errors));writeFileSync(join(cache,'results.json'),JSON.stringify({status:'passed',checks,exports,errors},null,2))
}catch(error){try{await shot('failure')}catch{}writeFileSync(join(cache,'results.json'),JSON.stringify({status:'failed',error:String(error),checks,exports,errors},null,2));throw error}
finally{if(socket?.readyState===WebSocket.OPEN){try{await send('Browser.close')}catch{}socket.close()}browser.kill();server.closeAllConnections();await new Promise(r=>server.close(r))}

