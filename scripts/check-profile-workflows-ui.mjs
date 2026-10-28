// Prueba de usuario en Chrome: selectores, contexto territorial y descargas reales.
import assert from 'node:assert/strict'
import {createServer} from 'node:http'
import {createServer as tcpServer} from 'node:net'
import {spawn} from 'node:child_process'
import {readFileSync,writeFileSync,mkdirSync,mkdtempSync,existsSync,renameSync} from 'node:fs'
import {createHash} from 'node:crypto'
import {resolve,join,extname,sep} from 'node:path'
const root=resolve('dist'),cache=resolve('node_modules/.cache/profile-workflows-ui'),downloads=join(cache,'downloads');mkdirSync(downloads,{recursive:true})
let failAge=false
const server=createServer((req,res)=>{const path=resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname)),target=path===root?join(root,'index.html'):path;if(path!==root&&!path.startsWith(root+sep)){res.writeHead(403).end();return}if(failAge&&path.endsWith('summaries'+sep+'2018'+sep+'14.json')){res.writeHead(503).end();return}try{res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'})[extname(target)]??'application/octet-stream');res.end(readFileSync(target))}catch{res.writeHead(404).end()}})
await new Promise(r=>server.listen(0,'127.0.0.1',r));const reservation=tcpServer();await new Promise(r=>reservation.listen(0,'127.0.0.1',r));const port=reservation.address().port;await new Promise(r=>reservation.close(r))
const browser=spawn(process.env.CHROME_PATH??'C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless=new','--no-first-run','--no-default-browser-check',`--remote-debugging-port=${port}`,`--user-data-dir=${mkdtempSync(join(cache,'chrome-'))}`,'about:blank'],{windowsHide:true,stdio:'ignore'})
const sleep=ms=>new Promise(r=>setTimeout(r,ms)),pending=new Map(),checks=[],errors=[],requests=[];let socket,id=0
function send(method,params={}){return new Promise((resolve,reject)=>{const key=++id,timer=setTimeout(()=>{pending.delete(key);reject(Error(method+' timeout'))},15000);pending.set(key,{resolve,reject,timer});socket.send(JSON.stringify({id:key,method,params}))})}
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function wait(expression){for(let n=0;n<180;n++){if(await evaluate(expression))return;await sleep(100)}throw Error('Tiempo agotado: '+expression)}
async function click(selector){await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`)}
async function key(key,code,number,text){await send('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:number,...(text?{text,unmodifiedText:text}:{})});await send('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:number})}
async function viewport(width,height=1000){await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});await sleep(80)}
async function screenshot(name){const r=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,fromSurface:true});writeFileSync(join(cache,name+'.png'),Buffer.from(r.data,'base64'))}
function record(name,details={}){checks.push({name,...details});console.log('✓ '+name)}
async function year(value){await click(`[data-election-year="${value}"]`);await wait(`document.querySelector('[data-election-year="${value}"]').getAttribute('aria-checked')==='true'`)}
async function state(code){await click('[data-state-search]');await wait(`!!document.querySelector('[data-state-option="${code}"]')`);await click(`[data-state-option="${code}"]`)}
async function query(value){await evaluate(`(() => {const input=document.querySelector('[data-state-search]');input.focus();Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(value)});input.dispatchEvent(new Event('input',{bubbles:true}));})()`)}
async function file(path){for(let n=0;n<180;n++){if(existsSync(path)&&!existsSync(path+'.crdownload'))return readFileSync(path);await sleep(100)}throw Error('Descarga ausente: '+path)}
async function ageRows(code,selectedYear,sex='all'){
 const summary=JSON.parse(readFileSync(`public/data/territorial/summaries/${selectedYear}/${code==='MX'?'national':code}.json`,'utf8'))
 await wait(`document.querySelector('.age-sex-table tbody')?.rows.length===3 && document.querySelector('.age-sex-toolbar').dataset.ageTerritory===${JSON.stringify(code)} && document.querySelector('.age-sex-toolbar').dataset.ageYear==='${selectedYear}'`)
 const rows=await evaluate(`[...document.querySelectorAll('.age-sex-table tbody tr')].map(n=>n.innerText)`)
 for(const [i,band] of ['18-34','35-59','60-100'].entries()){
   const cells=[...summary.segments,...summary.complementary].filter(r=>r.age_band===band&&(sex==='all'||r.sex_code===sex))
   if(!cells.length){assert.ok(rows[i].includes('No registrado'));continue}
   const sums=cells.reduce((s,r)=>({LN:s.LN+r.LN,SV:s.SV+r.SV,NV:s.NV+r.NV}),{LN:0,SV:0,NV:0})
   assert.ok(rows[i].includes(sums.LN.toLocaleString('es-MX')),`${code}/${selectedYear}/${band}/${sex}: nominal`)
   const rate=sums.SV+sums.NV?(sums.SV/(sums.SV+sums.NV)*100).toFixed(2):'No registrado'
   assert.ok(rows[i].includes(rate),`${code}/${selectedYear}/${band}/${sex}: tasa`)
 }
}
try{
 let pages;for(let n=0;n<120;n++){try{pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();if(pages.length)break}catch{}await sleep(100)}
 socket=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise(r=>socket.addEventListener('open',r,{once:true}));socket.addEventListener('message',e=>{const r=JSON.parse(e.data);if(r.id&&pending.has(r.id)){const p=pending.get(r.id);clearTimeout(p.timer);pending.delete(r.id);r.error?p.reject(Error(JSON.stringify(r.error))):p.resolve(r.result)}else if(r.method==='Runtime.exceptionThrown')errors.push(r.params.exceptionDetails);else if(r.method==='Network.requestWillBeSent')requests.push(r.params.request.url)})
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');await send('Page.bringToFront');await send('Emulation.setFocusEmulationEnabled',{enabled:true});await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloads});await viewport(1480)
 await send('Page.navigate',{url:`http://127.0.0.1:${server.address().port}/#dashboard`});await wait(`document.querySelectorAll('.dashboard-metric').length===4`)
 if(await evaluate(`document.documentElement.dataset.theme!=='light'`))await click('.theme-toggle')
 assert.equal(await evaluate(`document.querySelectorAll('[role="radio"][data-election-year]').length`),6)
 await year(2009);await ageRows('MX',2009);await year(2024);await ageRows('MX',2024)
 await query('zzzzz');assert.ok(await evaluate(`document.querySelector('.state-search-results').innerText.includes('Sin coincidencias')`));await key('Escape','Escape',27)
 await query('Chih');await key('ArrowDown','ArrowDown',40);await key('Enter','Enter',13,'\r');await wait(`document.querySelector('.state-current').innerText.includes('CHIHUAHUA')`);await ageRows('08',2024)
 const state2024=JSON.parse(readFileSync('public/data/participamx_multiyear/elections/2024/states.json','utf8')).data.find(r=>String(r.state_code).padStart(2,'0')==='08')
 assert.ok(await evaluate(`document.querySelector('.dashboard-metric-value').innerText.includes(${JSON.stringify(new Intl.NumberFormat('es-MX',{maximumFractionDigits:1}).format(state2024.participation_observed*100))})`))
 await evaluate(`(() => {const n=document.getElementById('age-sex-filter');n.value='1';n.dispatchEvent(new Event('change',{bubbles:true}));})()`);await ageRows('08',2024,'1');await screenshot('dashboard-chihuahua-2024')
 await query('Verac');await key('ArrowDown','ArrowDown',40);await key('Enter','Enter',13,'\r');await year(2021);await ageRows('30',2021,'1');await screenshot('dashboard-veracruz-2021')
 await evaluate(`document.querySelector('[data-election-year="2021"]').focus()`);await key('ArrowRight','ArrowRight',39);await wait(`document.querySelector('[data-election-year="2024"]').getAttribute('aria-checked')==='true'`);assert.ok(await evaluate(`document.querySelector('.state-current').innerText.includes('VERACRUZ')`))
 await state('MX');await ageRows('MX',2024,'1')
 failAge=true;await state('14');await year(2018);await wait(`document.querySelector('.age-sex-toolbar').closest('section').querySelector('[role="alert"]')!==null`);assert.equal(await evaluate(`document.querySelectorAll('.age-sex-table').length`),0)
 failAge=false;await click('.age-sex-toolbar + .dashboard-error button');await ageRows('14',2018,'1')
 record('Dashboard: México 2009/2024, Chihuahua 2024, Veracruz 2021, sexo, teclado, persistencia y fallo sin fallback nacional')
 await evaluate(`location.hash='metodologia'`);await wait(`!!document.querySelector('.methodology')`)
 const payload=JSON.parse(readFileSync('public/data/profiles/enriched-2024.json','utf8'))
 for(const p of payload.profiles)assert.ok(await evaluate(`document.querySelector('.methodology').innerText.includes(${JSON.stringify(p.name)})`))
 assert.ok(await evaluate(`!document.querySelector('.methodology').innerText.includes('por encima de sus pares')`));await screenshot('methodology-names')
 await evaluate(`location.hash='perfiles'`);await wait(`document.querySelectorAll('[data-profile-card]').length===6`);await year(2024);await wait(`document.querySelector('.participation-profiles')?.dataset.profileYear==='2024' && !!document.querySelector('[data-transversal-finding]')`)
 await state('08');await wait(`document.querySelectorAll('.profile-context-table tbody tr').length===6`)
 const contexts=JSON.parse(readFileSync('public/data/participamx_multiyear/elections/2024/state_profiles.json','utf8')).data.filter(r=>String(r.state_code).padStart(2,'0')==='08')
 const contextText=await evaluate(`document.querySelector('.profile-context-table').innerText`)
 for(const row of contexts)assert.ok(contextText.includes((row.participation_observed*100).toFixed(2)))
 await screenshot('profiles-chihuahua-context')
 await year(2021);await wait(`document.querySelector('[data-profile-context]').dataset.profileContextYear==='2021' && !!document.querySelector('.profile-context-table')`);assert.equal(await evaluate(`document.querySelector('[data-profile-context]').dataset.profileContext`),'08')
 await wait(`document.querySelectorAll('[data-profile-card]').length===6 && document.querySelector('.participation-profiles').dataset.profileYear==='2021'`);await click('[data-open-profile="young_favorable"]');await wait(`!!document.querySelector('[data-profile-detail]')`)
 assert.ok(await evaluate(`[...document.querySelectorAll('[data-export-format]')].every(b=>!b.disabled)`));assert.equal(await evaluate(`document.querySelectorAll('[data-transversal-finding]').length`),0);await click('.pp-back')
 await year(2024);await wait(`document.querySelectorAll('[data-profile-card]').length===6 && !!document.querySelector('[data-transversal-finding]')`)
 record('Perfiles: contexto estatal separado, seis reglas y exportación histórica con datos propios')
 const exports=[]
 for(const [index,p] of payload.profiles.entries()){
   await click(`[data-open-profile="${p.id}"]`);await wait(`document.querySelector('[data-profile-detail]')?.dataset.profileDetail===${JSON.stringify(p.id)}`)
   const base=`participamx_perfil_${String(index+1).padStart(2,'0')}_${p.name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(' con ',' ').replace(/[^a-z0-9]+/g,'_')}_2024`
   for(const format of ['pdf','png']){
     const path=join(downloads,`${base}.${format}`)
     // Cada ejecución conserva los archivos anteriores con un nombre de evidencia distinto.
     if(existsSync(path))renameSync(path,join(downloads,`${base}-previous-${Date.now()}.${format}`))
     await click(`[data-export-format="${format}"]`);const buffer=await file(path)
     await wait(`document.querySelector('[data-export-format="png"]').disabled===false`)
     if(format==='pdf')assert.equal(buffer.subarray(0,5).toString(),'%PDF-')
     else {assert.equal(buffer.subarray(0,8).toString('hex'),'89504e470d0a1a0a');assert.equal(buffer.readUInt32BE(16),1600);assert.equal(buffer.readUInt32BE(20),4526)}
     exports.push({id:p.id,format,bytes:buffer.length,path})
   }
   if(index===0){await screenshot('profile-export-buttons');const path=join(downloads,base+'.png'),before=readFileSync(path);renameSync(path,join(downloads,base+'-light.png'));await click('.theme-toggle');await click('[data-export-format="png"]');const after=await file(path);assert.equal(createHash('sha256').update(before).digest('hex'),createHash('sha256').update(after).digest('hex'));await screenshot('profile-export-buttons-dark');await click('.theme-toggle')}
   await click('.pp-back');await wait(`document.querySelectorAll('[data-profile-card]').length===6`)
 }
 assert.ok(!requests.some(url=>/html2canvas|purify/.test(url)))
 record('Doce descargas reales: seis PDF y seis PNG de 1600×4526; exportación estable entre temas y sin capturas DOM',{exports})
 for(const width of [1480,950,390,320]){await viewport(width,900);for(const route of ['dashboard','perfiles','mapa']){await evaluate(`location.hash=${JSON.stringify(route)}`);await wait(`document.querySelectorAll('[role="radio"][data-election-year]').length===6`);await sleep(200);assert.ok(await evaluate(`document.documentElement.scrollWidth<=innerWidth+1`),`${route}/${width}`);assert.ok(await evaluate(`[...document.querySelectorAll('.shared-election-selector button small')].every(n=>n.scrollWidth<=n.clientWidth+1)`),`${route}/${width}: etiqueta de elección cortada`);if(width===390)await screenshot(`${route}-mobile-selectors`)}}
 assert.equal(errors.length,0,JSON.stringify(errors));record('Selectores en escritorio, tableta y móvil sin desbordamiento de página')
 writeFileSync(join(cache,'results.json'),JSON.stringify({status:'passed',checks,errors},null,2))
}catch(error){try{await screenshot('failure')}catch{}let page;try{page=await evaluate(`document.body.innerText.slice(-3000)`)}catch{}writeFileSync(join(cache,'results.json'),JSON.stringify({status:'failed',error:String(error),checks,errors,page},null,2));throw error}
finally{if(socket?.readyState===WebSocket.OPEN){try{await send('Browser.close')}catch{}socket.close()}browser.kill();server.closeAllConnections();await new Promise(r=>server.close(r))}
