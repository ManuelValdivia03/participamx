// Revisión visual en Chrome real, sin dependencias ni cambios de datos.
import assert from 'node:assert/strict'
import {createServer} from 'node:http'
import {createServer as tcpServer} from 'node:net'
import {spawn} from 'node:child_process'
import {readFileSync,writeFileSync,mkdirSync,mkdtempSync} from 'node:fs'
import {resolve,join,extname,sep} from 'node:path'
const root=resolve('dist'),cache=resolve('node_modules/.cache/typography-ui');mkdirSync(cache,{recursive:true})
const server=createServer((req,res)=>{const path=resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname)),target=path===root?join(root,'index.html'):path;if(path!==root&&!path.startsWith(root+sep)){res.writeHead(403).end();return}try{res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'})[extname(target)]??'application/octet-stream');res.end(readFileSync(target))}catch{res.writeHead(404).end()}})
await new Promise(r=>server.listen(0,'127.0.0.1',r));const reservation=tcpServer();await new Promise(r=>reservation.listen(0,'127.0.0.1',r));const port=reservation.address().port;await new Promise(r=>reservation.close(r))
const browser=spawn(process.env.CHROME_PATH??'C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless=new','--no-first-run','--no-default-browser-check',`--remote-debugging-port=${port}`,`--user-data-dir=${mkdtempSync(join(cache,'chrome-'))}`,'about:blank'],{windowsHide:true,stdio:'ignore'})
const sleep=ms=>new Promise(r=>setTimeout(r,ms)),pending=new Map(),checks=[],errors=[];let socket,id=0
function send(method,params={}){return new Promise((resolve,reject)=>{const key=++id,timer=setTimeout(()=>{pending.delete(key);reject(Error(method+' timeout'))},15000);pending.set(key,{resolve,reject,timer});socket.send(JSON.stringify({id:key,method,params}))})}
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function wait(expression){for(let n=0;n<160;n++){if(await evaluate(expression))return;await sleep(100)}throw Error(expression)}
async function click(selector){await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`)}
async function viewport(width,height=1000,deviceScaleFactor=1){await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor,mobile:false});await sleep(100)}
async function screenshot(name){const r=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,fromSurface:true});writeFileSync(join(cache,name+'.png'),Buffer.from(r.data,'base64'))}
function record(name,details={}){checks.push({name,...details});console.log('✓ '+name)}
const ready={dashboard:`document.querySelectorAll('.dashboard-metric').length===4`,metodologia:`!!document.querySelector('.method-formula')`,perfiles:`document.querySelectorAll('[data-profile-card]').length===6`,mapa:`!!document.querySelector('.thematic-legend') && !!document.querySelector('.territory-map-atlas')`}
async function page(route){await evaluate(`location.hash=${JSON.stringify(route)}`);await wait(ready[route]);await sleep(150)}
async function noOverflow(label){const layout=await evaluate(`({width:innerWidth,scroll:document.documentElement.scrollWidth,offenders:[...document.querySelectorAll('main *')].filter(n=>{const r=n.getBoundingClientRect();return r.width>0&&r.right>innerWidth+2&&getComputedStyle(n).position!=='fixed'&&!n.closest('[class*="scroll"],.pp-compare-scroll,.territorial-table-scroll')}).slice(0,8).map(n=>n.className)})`);assert.ok(layout.scroll<=layout.width+1,`${label}: ${JSON.stringify(layout)}`)}
async function contrast(route){
 const selectors={dashboard:['.dashboard-metric h2','.dashboard-metric-note','.state-search>label','.dashboard-chart-definition','.dashboard-filters p','.notice','.dashboard-distribution strong','.trend-year-buttons button small','.dashboard-reset','.dashboard-text-link','.dashboard-current'],metodologia:['.method-steps p','.methodology .card>p','.methodology .card-heading h2'],perfiles:['.pp-card h3','.pp-card-criterion','.pp-kicker','.pp-card .pp-button'],mapa:['.territorial-source','.thematic-scale-note','.thematic-section-explanation','.territorial-kicker']}
 const rows=await evaluate(`(() => {const rgb=c=>c.match(/[\\d.]+/g).map(Number),lum=c=>rgb(c).slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);return ${JSON.stringify(selectors[route])}.flatMap(selector=>{const n=document.querySelector(selector);if(!n)return [];let a=n,bg='rgb(255,255,255)';while(a){const c=getComputedStyle(a).backgroundColor,v=rgb(c);if(v.length===3||v[3]>.99){bg=c;break}a=a.parentElement}const x=lum(getComputedStyle(n).color),y=lum(bg);return [{selector,ratio:(Math.max(x,y)+.05)/(Math.min(x,y)+.05),size:parseFloat(getComputedStyle(n).fontSize)}]})})()`)
 for(const row of rows)assert.ok(row.ratio>=4.5,`${route} ${JSON.stringify(row)}`)
 return rows
}
try{
 let pages;for(let n=0;n<120;n++){try{pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();if(pages.length)break}catch{}await sleep(100)}
 socket=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise(r=>socket.addEventListener('open',r,{once:true}));socket.addEventListener('message',e=>{const r=JSON.parse(e.data);if(r.id&&pending.has(r.id)){const p=pending.get(r.id);clearTimeout(p.timer);pending.delete(r.id);r.error?p.reject(Error(JSON.stringify(r.error))):p.resolve(r.result)}else if(r.method==='Runtime.exceptionThrown')errors.push(r.params.exceptionDetails)})
 await send('Page.enable');await send('Runtime.enable');await send('Page.bringToFront');await send('Emulation.setFocusEmulationEnabled',{enabled:true});await viewport(1480)
 await send('Page.navigate',{url:`http://127.0.0.1:${server.address().port}/#dashboard`});await wait(ready.dashboard)
 const national=JSON.parse(readFileSync('public/data/participamx_multiyear/elections/2024/national_statistics.json','utf8')).data[0]
 for(const theme of ['light','dark']){
   await evaluate(`document.querySelector('.theme-toggle').click()`);if(await evaluate(`document.documentElement.dataset.theme!==${JSON.stringify(theme)}`))await click('.theme-toggle')
   for(const route of Object.keys(ready)){
     await viewport(1480);await page(route);const ratios=await contrast(route)
     const controls=await evaluate(`[...document.querySelectorAll('main input,main select')].filter(n=>n.checkVisibility()).map(n=>({id:n.id,size:parseFloat(getComputedStyle(n).fontSize)}))`)
     for(const control of controls)assert.ok(control.size>=16,`${route}: input pequeño ${JSON.stringify(control)}`)
     if(route==='metodologia')assert.ok(await evaluate(`parseFloat(getComputedStyle(document.querySelector('.method-steps p')).fontSize)>=16`))
     for(const width of [1480,950,390,320]){await viewport(width,900);await noOverflow(`${theme}/${route}/${width}`);if(width===1480||width===390)await screenshot(`${route}-${theme}-${width}`)}
     record(`${route}: tamaños, contraste y reflujo ${theme}`,{ratios})
   }
 }
 await viewport(1480);await page('dashboard')
 const metrics=await evaluate(`[...document.querySelectorAll('.dashboard-metric-value')].map(n=>n.innerText)`)
 assert.ok(metrics[0].includes(new Intl.NumberFormat('es-MX',{maximumFractionDigits:1}).format(national.participation_observed*100)))
 assert.ok(await evaluate(`document.querySelector('.dashboard-metric-note').innerText.includes('aproximadamente '+Math.round(${national.participation_observed}*100))`))
 await click('.statistics-help summary');assert.ok(await evaluate(`document.querySelector('.statistics-help').open && document.querySelector('.statistics-help').innerText.includes('pp = puntos porcentuales')`))
 await click('[data-election-year="2009"]')
 await wait(`document.querySelector('.dashboard-current').innerText.includes('2009')`)
 const original2009=JSON.parse(readFileSync('public/data/participamx_multiyear/elections/2009/national_statistics.json','utf8')).data[0]
 assert.ok(await evaluate(`document.querySelector('.dashboard-metric-note').innerText.includes('aproximadamente '+Math.round(${original2009.participation_observed}*100))`))
 await click('[data-state-search]');await click('[data-state-option="09"]')
 await wait(`!![...document.querySelectorAll('.card-heading h2')].find(n=>n.innerText==='Lista nominal por perfil')`)
 record('Dashboard: explicación dinámica de tasa nacional 2024/2009, ayuda y base estatal diferenciada',{metrics})
 await page('metodologia');assert.ok(await evaluate(`document.querySelector('.methodology').innerText.includes('SV / (SV + NV) × 100')`))
 record('Metodología: fórmula visible y advertencias conservadas')
 await viewport(390,844);await page('mapa');await click('.atlas-guide-open')
 await wait(`document.querySelector('.atlas-guide-dialog').open`)
 assert.ok(await evaluate(`(() => {const r=document.querySelector('.atlas-guide-panel').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1})()`))
 await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27})
 await wait(`!document.querySelector('.atlas-guide-dialog').open`)
 await wait(`document.activeElement.classList.contains('atlas-guide-open')`)
 record('Guía del Atlas: texto y controles contenidos en móvil, Escape y foco de retorno')
 // El zoom nativo no está expuesto de forma fiable por DevTools en Chrome headless.
 // Equivalente de reflujo: ventana física 1480×1000, viewport CSS y DPR correspondientes.
 for(const zoom of [1,1.25,1.5,2]){for(const route of Object.keys(ready)){await viewport(Math.floor(1480/zoom),Math.floor(1000/zoom),zoom);await page(route);await noOverflow(`${route}/zoom-equivalente-${zoom}`)}}
 record('Reflujo equivalente a 100/125/150/200 % en las cuatro páginas',{method:'Emulación de viewport CSS y DPR, no zoom nativo de Chrome'})
 assert.equal(errors.length,0,JSON.stringify(errors));writeFileSync(join(cache,'results.json'),JSON.stringify({status:'passed',checks,errors},null,2))
}catch(error){try{await screenshot('failure')}catch{}writeFileSync(join(cache,'results.json'),JSON.stringify({status:'failed',error:String(error),checks,errors},null,2));throw error}
finally{if(socket?.readyState===WebSocket.OPEN){try{await send('Browser.close')}catch{}socket.close()}browser.kill();server.closeAllConnections();await new Promise(r=>server.close(r))}
