// Chrome real: persistencia anual, fallos/reintentos y las 72 descargas individuales.
import assert from 'node:assert/strict'
import {createServer} from 'node:http'
import {spawn} from 'node:child_process'
import {readFileSync,writeFileSync,mkdirSync,mkdtempSync,existsSync,renameSync} from 'node:fs'
import {resolve,join,extname,sep} from 'node:path'
const root=resolve('dist'),cache=resolve('node_modules/.cache/historical-profiles-ui'),downloads=join(cache,'downloads');mkdirSync(downloads,{recursive:true})
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
const selected=['young_favorable','young_unfavorable']
const payload=year=>JSON.parse(readFileSync(`public/data/profiles/enriched-${year}.json`,'utf8'))
async function checkComparison(year,view,measure='participation'){
 assert.deepEqual(await evaluate(`[...document.querySelectorAll('[data-compared-profile]')].map(n=>n.dataset.comparedProfile)`),selected)
 assert.equal(await evaluate(`document.querySelector('[data-comparison-view="${view}"]').getAttribute('aria-pressed')`),'true')
 const data=payload(year)
 assert.equal(await evaluate(`document.querySelector('[data-comparison-measure="${measure}"]').getAttribute('aria-pressed')`),'true')
 for(const id of selected){const p=data.profiles.find(p=>p.id===id),text=await evaluate(`document.querySelector('[data-compared-profile="${id}"]').innerText`);for(const c of view==='sex'?p.sexCells:p.sectionCells)assert.ok(text.includes((c[measure==='composition'?'nominalShare':'participation']*100).toFixed(2)),`${year}/${id}/${view}`)}
 assert.equal(await evaluate(`document.querySelectorAll('[data-transversal-finding]').length`),year===2024?1:0)
}
try{
 let pages;for(let n=0;n<120;n++){try{pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();if(pages.length)break}catch{}await sleep(100)}
 socket=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise(r=>socket.addEventListener('open',r,{once:true}));socket.addEventListener('message',e=>{const r=JSON.parse(e.data);if(r.id&&pending.has(r.id)){const p=pending.get(r.id);clearTimeout(p.timer);pending.delete(r.id);r.error?p.reject(Error(JSON.stringify(r.error))):p.resolve(r.result)}else if(r.method==='Runtime.exceptionThrown')errors.push(r.params.exceptionDetails)})
 await send('Page.enable');await send('Runtime.enable');await send('Page.bringToFront');await send('Emulation.setFocusEmulationEnabled',{enabled:true});await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloads});await viewport(1480)
 await send('Page.navigate',{url:`http://127.0.0.1:${server.address().port}/#perfiles`});await ready(2024)
 if(await evaluate(`document.documentElement.dataset.theme!=='light'`))await click('.theme-toggle')
 for(const id of selected)await click(`[data-profile-card="${id}"] .pp-compare`)
 await click('[data-comparison-view="sex"]');await checkComparison(2024,'sex')
 delayYear=2009;await year(2009);await wait(`!!document.querySelector('.dashboard-loading')`);assert.equal(await evaluate(`document.querySelectorAll('[data-compared-profile]').length`),0);await ready(2009);delayYear=null;await checkComparison(2009,'sex');await shot('comparison-2009-sex')
 await click('[data-comparison-view="section"]')
 for(const y of [2012,2015,2018,2021,2024]){await year(y);await ready(y);await checkComparison(y,'section')}
 await click('[data-comparison-measure="composition"]');await year(2018);await ready(2018);await checkComparison(2018,'section','composition');await year(2024);await ready(2024);await checkComparison(2024,'section','composition');await click('[data-comparison-measure="participation"]')
 delayYear=2021;await year(2021);await wait(`!!document.querySelector('.dashboard-loading')`);await year(2024);await ready(2024);await sleep(850);await checkComparison(2024,'section');delayYear=null
 await click('[data-open-profile="young_favorable"]');await wait(`!!document.querySelector('[data-profile-detail]')`);await click('.pp-back');await checkComparison(2024,'section')
 failYear=2015;await year(2015);await wait(`!!document.querySelector('.pp-year-note[role="alert"]')`);assert.equal(await evaluate(`document.querySelector('[data-comparison-count]').dataset.comparisonCount`),'2');assert.equal(await evaluate(`document.querySelectorAll('.pp-compare-column .pp-rate-track').length`),0)
 failYear=null;await click('.pp-year-note[role="alert"] button');await ready(2015);await checkComparison(2015,'section')
 checks.push('Dos IDs, pestaña y medida persistentes en las seis elecciones, catálogo/detalle y reintento; carga sin cifras antiguas')
 for(const y of [2009,2012,2015,2018,2021,2024]){
   await year(y);await ready(y)
   for(const [index,p] of payload(y).profiles.entries()){
     await click(`[data-open-profile="${p.id}"]`);await wait(`document.querySelector('[data-profile-detail]')?.dataset.profileDetail===${JSON.stringify(p.id)}`)
     assert.equal(await evaluate(`document.querySelector('.pp-export-actions p').innerText`),`Ficha nacional · ${y}`)
     const name=`participamx_perfil_${String(index+1).padStart(2,'0')}_${p.name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(' con ',' ').replace(/[^a-z0-9]+/g,'_')}_${y}`
     for(const format of ['pdf','png']){
       const path=join(downloads,name+'.'+format);if(existsSync(path))renameSync(path,join(downloads,name+'-previous-'+Date.now()+'.'+format))
       await click(`[data-export-format="${format}"]`);const buffer=await file(path);await wait(`!document.querySelector('[data-export-format="png"]').disabled`)
       if(format==='pdf')assert.equal(buffer.subarray(0,5).toString(),'%PDF-');else{assert.equal(buffer.subarray(0,8).toString('hex'),'89504e470d0a1a0a');assert.equal(buffer.readUInt32BE(16),1600);assert.equal(buffer.readUInt32BE(20),4526)}
       exports.push({year:y,id:p.id,format,bytes:buffer.length,path})
     }
     if(index===0&&[2009,2018,2024].includes(y)){if(y===2018)await click('.theme-toggle');await shot(`detail-${y}`);if(y===2018)await click('.theme-toggle')}
     await click('.pp-back')
   }
   console.log(`✓ ${y}: seis PDF y seis PNG descargados`)
 }
 checks.push('72 descargas reales: 36 perfiles/año en ambos formatos')
 for(const width of [1480,950,390,320]){await viewport(width);await wait(`document.querySelectorAll('[data-profile-card]').length===6`);assert.ok(await evaluate(`document.documentElement.scrollWidth<=innerWidth+1`));await click('[data-comparison-view="sex"]');await checkComparison(2024,'sex');if(width===390)await shot('comparison-mobile')}
 await viewport(950);await evaluate(`document.querySelector('[data-election-year="2024"]').focus()`);await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Home',code:'Home',windowsVirtualKeyCode:36});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Home',code:'Home',windowsVirtualKeyCode:36});await ready(2009);await checkComparison(2009,'sex')
 checks.push('Claro/oscuro, escritorio/tableta/móvil y teclado; V2.1 sólo visible en 2024')
 assert.equal(errors.length,0,JSON.stringify(errors));writeFileSync(join(cache,'results.json'),JSON.stringify({status:'passed',checks,exports,errors},null,2));console.log('✓ Persistencia, carga, errores, responsive y teclado')
}catch(error){try{await shot('failure')}catch{}writeFileSync(join(cache,'results.json'),JSON.stringify({status:'failed',error:String(error),checks,exports,errors},null,2));throw error}
finally{if(socket?.readyState===WebSocket.OPEN){try{await send('Browser.close')}catch{}socket.close()}browser.kill();server.closeAllConnections();await new Promise(r=>server.close(r))}
