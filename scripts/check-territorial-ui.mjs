// Prueba de navegador real sin dependencias adicionales: Chrome y protocolo DevTools.
// Usa exclusivamente dist/ y un perfil temporal dentro de node_modules/.cache.
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { createServer as createTcpServer } from 'node:net'
import { spawn } from 'node:child_process'
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, existsSync } from 'node:fs'
import { resolve, extname, join, sep } from 'node:path'

const root = resolve('dist')
assert.ok(existsSync(join(root, 'index.html')), 'Ejecutar npm run build antes de la prueba de navegador')
const cache = resolve('node_modules/.cache/territorial-ui')
mkdirSync(cache, { recursive: true })
const executable = process.env.CHROME_PATH ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
assert.ok(existsSync(executable), 'Definir CHROME_PATH con un ejecutable Chromium instalado')
const server = createServer((request, response) => {
  const path = resolve(root, '.' + decodeURIComponent(new URL(request.url, 'http://localhost').pathname))
  if (path !== root && !path.startsWith(root + sep)) { response.writeHead(403).end(); return }
  const target = path === root ? join(root, 'index.html') : path
  try {
    const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json' }
    response.setHeader('Content-Type', mime[extname(target)] ?? 'application/octet-stream')
    response.end(readFileSync(target))
  } catch { response.writeHead(404).end() }
})
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
const url = `http://127.0.0.1:${server.address().port}/#mapa`
const reservation = createTcpServer()
await new Promise(resolve => reservation.listen(0, '127.0.0.1', resolve))
const port = reservation.address().port
await new Promise(resolve => reservation.close(resolve))
const browser = spawn(executable, ['--headless=new', '--no-first-run', '--no-default-browser-check',
  `--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(cache, 'chrome-'))}`, 'about:blank'],
{ windowsHide: true, stdio: 'ignore' })
let socket
let messageId = 0
const waiting = new Map()
const errors = []
const requests = []
const checks = []
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++messageId
    const timer = setTimeout(() => { waiting.delete(id); reject(new Error(`CDP timeout: ${method}`)) }, 15000)
    waiting.set(id, { resolve, reject, timer })
    socket.send(JSON.stringify({ id, method, params }))
  })
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}
async function wait(expression) {
  const until = Date.now() + 15000
  while (Date.now() < until) {
    if (await evaluate(expression)) return
    await sleep(100)
  }
  throw new Error(`Tiempo agotado: ${expression}`)
}
async function select(id, value) {
  if (id === 'electoral-year') {
    await evaluate(`document.querySelector('[data-election-year="${value}"][role="radio"]').click()`)
    return
  }
  if (id === 'state-picker') {
    if (!value) await evaluate(`document.querySelector('button[aria-label="Ver todo México"]').click()`)
    else {
      await typeSearch(value)
      await wait(`!!document.querySelector('[role="option"][data-place-kind="state"][data-place-code="${value}"]')`)
      await evaluate(`document.querySelector('[role="option"][data-place-kind="state"][data-place-code="${value}"]').click()`)
    }
    return
  }
  await evaluate(`(() => { const select = document.getElementById(${JSON.stringify(id)}); select.value = ${JSON.stringify(value)}; select.dispatchEvent(new Event('change', {bubbles:true})); })()`)
}
async function typeSearch(query) {
  // Este flujo prueba teclado: un cursor residual no debe activar otra sugerencia por hover.
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 20, y: 20 })
  await evaluate(`(() => { const input=document.getElementById('territory-search-input'); input.focus(); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(query)}); input.dispatchEvent(new Event('input',{bubbles:true})); })()`)
}
async function pickMunicipality(name) {
  const state = await evaluate(`document.querySelector('.territory-explorer').dataset.stateCode`)
  await typeSearch(name)
  const selector = `[role="option"][data-place-kind="municipality"]${state ? `[data-place-state="${state}"]` : ''}`
  await wait(`[...document.querySelectorAll(${JSON.stringify(selector)})].some(button => button.querySelector('strong').textContent === ${JSON.stringify(name)})`)
  await evaluate(`[...document.querySelectorAll(${JSON.stringify(selector)})].find(button => button.querySelector('strong').textContent === ${JSON.stringify(name)}).click()`)
}
async function setTheme(theme) {
  if (await evaluate(`document.documentElement.dataset.theme !== ${JSON.stringify(theme)}`)) {
    await evaluate(`document.querySelector('.theme-toggle').click()`)
  }
  await wait(`document.documentElement.dataset.theme === ${JSON.stringify(theme)}`)
}
async function chooseMunicipality(name) {
  await pickMunicipality(name)
  await wait(`document.querySelector('.demographic-heading > p')?.textContent.includes(${JSON.stringify(name)})`)
}
async function chooseView(view) {
  await evaluate(`document.querySelector('[data-territory-view="${view}"]').click()`)
  await wait(`document.querySelector('.territory-detail').dataset.view === '${view}'`)
}
async function changeAxis(axis) {
  await chooseView('demographics')
  await evaluate(`document.querySelector('[data-demographic-axis="${axis}"]').click()`)
  await wait(`document.querySelector('.demographic-panel')?.dataset.axis === ${JSON.stringify(axis)}`)
}
async function pressKey(key, code, windowsVirtualKeyCode, text) {
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode, ...(text ? { text, unmodifiedText: text } : {}) })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode })
}
async function mapPoint() {
  await evaluate(`document.querySelector('.mexico-map').scrollIntoView({block:'center',behavior:'instant'})`)
  return evaluate(`(() => {const r=document.querySelector('.mexico-map').getBoundingClientRect();return {x:r.left+r.width*.85,y:r.top+r.height*.8}})()`)
}
const layerGroup = layer => ['women', 'men', 'nonbinary','women_participants','men_participants'].includes(layer) ? 'sex' : layer.startsWith('age') ? 'age' : 'participation'
async function chooseLayer(layer) {
  await evaluate(`document.querySelector('[data-layer-group="${layerGroup(layer)}"]').click()`)
  if (layer.endsWith('_participants')) await evaluate(`document.querySelector('[data-sex-basis="participants"]').click()`)
  await evaluate(`document.querySelector('button[data-map-layer="${layer}"]').click()`)
  await wait(`document.querySelector('.mexico-map').dataset.mapLayer === '${layer}' && document.querySelector('.mexico-map').dataset.layerReady === 'true'`)
}
async function assertMapValues(year, layer, state = '') {
  await wait(`document.querySelector('.mexico-map').dataset.layerReady === 'true' && document.querySelector('.mexico-map').dataset.layerYear === '${year}'`)
  const rows = await evaluate(`[...document.querySelectorAll('.mexico-map path[role="button"]')].map(node=>({code:node.dataset.mapCode,value:node.getAttribute('data-thematic-value'),status:node.dataset.thematicStatus,fill:node.style.fill,classIndex:node.getAttribute('data-thematic-class'),label:node.getAttribute('aria-label')}))`)
  const legend = await evaluate(`({mode:document.querySelector('.thematic-legend').dataset.legendMode,breaks:JSON.parse(document.querySelector('.thematic-legend').dataset.scaleBreaks),classes:[...document.querySelectorAll('[data-scale-class]')].map(node=>({lower:Number(node.dataset.classLower),upper:Number(node.dataset.classUpper),count:Number(node.querySelector('small').textContent.split(' ')[0])}))})`)
  const expectedValues = []
  const data = JSON.parse(readFileSync(state ? `public/data/territorial/${year}/${state}.json` : `public/data/territorial/layers/${year}.json`, 'utf8'))
  const records = new Map((state ? data.data : data.states).map(row => [state ? row.ine_code : row.state_code, row]))
  const crosswalk = state ? JSON.parse(readFileSync(`public/data/ine-crosswalk/${state}.json`, 'utf8')).years[year] : null
  for (const row of rows) {
    const key = state ? crosswalk[row.code]?.ineCode : row.code
    const record = records.get(key)
    let expected = null, status = key ? 'missing' : 'unmapped'
    if (record) {
      const cells = [...record.segments, ...record.complementary], sex = { women: '1', men: '0', nonbinary: '2',women_participants:'1',men_participants:'0' }[layer], band = { age18_34: '18-34', age35_59: '35-59', age60_100: '60-100' }[layer]
      if (layer === 'nonbinary' && year !== 2024) status = 'unavailable_category'
      else {
        const matching = sex ? cells.filter(cell=>cell.sex_code===sex) : band ? cells.filter(cell=>cell.age_band===band) : null
        if (!matching || matching.length) {
          const counts = matching ? Object.fromEntries(['LN','SV','NV','NS','source_row_count'].map(field=>[field,matching.reduce((sum,cell)=>sum+cell[field],0)])) : record.totals
          const denominator = layerGroup(layer) === 'participation' ? counts.SV+counts.NV : layer.endsWith('_participants') ? record.totals.SV : record.totals.LN
          const numerator = layer === 'participation' ? counts.SV : layer === 'nonparticipation' ? counts.NV : layer.endsWith('_participants') ? counts.SV : counts.LN
          expected = denominator ? numerator/denominator : null
          status = expected === null ? 'undefined' : counts.LN>=100&&counts.SV+counts.NV>=100&&counts.source_row_count>=5 ? 'defined' : 'low_support'
        }
      }
    }
    assert.equal(row.status, status, `${year}:${row.code}:${layer}:status`)
    if (expected === null) assert.equal(row.value, null)
    else assert.ok(Math.abs(Number(row.value)-expected)<1e-13, `${year}:${row.code}:${layer}:value`)
    if (status === 'defined') {
      expectedValues.push(expected)
      const classIndex = legend.classes.findIndex((item,i)=>(i===0?expected>=item.lower:expected>item.lower)&&expected<=item.upper)
      assert.notEqual(classIndex,-1)
      assert.equal(Number(row.classIndex),classIndex)
      const level=legend.classes.length===1?2:Math.round(classIndex*4/(legend.classes.length-1))
      assert.equal(row.fill,`var(--atlas-color-${level})`,`${row.code}:color`)
    } else { assert.equal(row.fill,status==='low_support'?'var(--atlas-low-support)':'var(--atlas-no-data)', `${row.code}:neutro`); assert.equal(row.classIndex,null) }
    assert.ok(row.label.includes(String(year)))
  }
  assert.equal(await evaluate(`document.querySelector('.thematic-legend').dataset.legendLayer`), layer)
  expectedValues.sort((a,b)=>a-b)
  const unique=[...new Set(expectedValues)]
  assert.equal(legend.mode,'relative')
  const cuts=unique.length<=5?unique.slice(0,-1):[...new Set([.2,.4,.6,.8].map(q=>expectedValues[Math.ceil(q*expectedValues.length)-1]))].filter(value=>value<expectedValues.at(-1))
  assert.deepEqual(legend.breaks,cuts)
  assert.equal(legend.classes.reduce((n,item)=>n+item.count,0),expectedValues.length)
  assert.equal(await evaluate(`document.querySelectorAll('.thematic-ramp i').length`),legend.classes.length)
  if(legend.classes.length) assert.ok((await evaluate(`document.querySelector('.thematic-explanation').textContent`)).length>20)
  return rows.length
}
async function mapWidth() { return evaluate(`Number(document.querySelector('.mexico-map').getAttribute('viewBox').split(' ')[2])`) }
async function waitCamera() { await sleep(550) }
async function clickGeometry(code) {
  await mapPoint()
  const point = await evaluate(`(() => { const path=document.querySelector('.mexico-map path[data-map-code="${code}"][role="button"]');const b=path.getBBox(), matrix=path.getScreenCTM();for(let i=1;i<10;i++)for(let j=1;j<10;j++){const p=new DOMPoint(b.x+b.width*i/10,b.y+b.height*j/10);if(path.isPointInFill(p)){const client=p.matrixTransform(matrix);if(client.y>0&&client.y<innerHeight&&document.elementFromPoint(client.x,client.y)===path)return {x:client.x,y:client.y}}}return null })()`)
  assert.ok(point, `Punto interior visible: ${code}`)
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', clickCount: 1 })
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', clickCount: 1 })
}
async function screenshot(name, selector) {
  await evaluate(`document.activeElement?.blur(); window.scrollTo({top:0,left:0,behavior:'instant'})`)
  await waitCamera()
  const { cssContentSize } = await send('Page.getLayoutMetrics')
  const clip = selector ? await evaluate(`(() => {const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:Math.floor(r.left+scrollX),y:Math.floor(r.top+scrollY),width:Math.ceil(r.width),height:Math.ceil(r.height),scale:1}})()`) : { x: 0, y: 0, width: cssContentSize.width, height: cssContentSize.height, scale: 1 }
  const { data } = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true,
    clip })
  writeFileSync(join(cache, name + '.png'), Buffer.from(data, 'base64'))
}
function record(name, data) { checks.push({ name, ...data }); console.log(`OK: ${name}`) }
async function checkContrast(theme) {
  const palette = await evaluate(`(() => { const style=getComputedStyle(document.querySelector('.territory-explorer')); return Object.fromEntries(['ink','muted','purple','warm','third','surface','soft'].map(name=>[name,style.getPropertyValue('--territory-'+name).trim()])) })()`)
  const luminance = hex => {
    const rgb = hex.slice(1).match(/../g).map(value => parseInt(value, 16) / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
    return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722
  }
  const ratios = []
  for (const foreground of ['ink', 'muted', 'purple', 'warm', 'third']) for (const background of ['surface', 'soft']) {
    const a = luminance(palette[foreground]), b = luminance(palette[background])
    const contrast = (Math.max(a, b) + .05) / (Math.min(a, b) + .05)
    assert.ok(contrast >= 4.5, `${theme}: ${foreground}/${background}: ${contrast}`)
    ratios.push(contrast)
  }
  record(`Contraste de texto de la paleta ${theme} ≥4.5:1`, { minimum: Math.min(...ratios) })
}

try {
  let targets
  const until = Date.now() + 15000
  while (Date.now() < until) {
    try { targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); break } catch { await sleep(150) }
  }
  assert.ok(targets?.length, 'Chrome no inició DevTools')
  socket = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl)
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data)
    const pending = waiting.get(message.id)
    if (pending) {
      clearTimeout(pending.timer); waiting.delete(message.id)
      if (message.error) pending.reject(new Error(JSON.stringify(message.error)))
      else pending.resolve(message.result)
    }
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails)
    if (message.method === 'Network.requestWillBeSent') requests.push(message.params.request.url)
    if (message.method === 'Fetch.requestPaused') send('Fetch.failRequest', { requestId: message.params.requestId, errorReason: 'Failed' }).catch(() => {})
  })
  await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }))
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable'); await send('Page.bringToFront')
  await send('Emulation.setFocusEmulationEnabled', { enabled: true })
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false })
  await send('Fetch.enable', { patterns: [{ urlPattern: '*/territorial/search-index.json', requestStage: 'Request' }, { urlPattern: '*/territorial/layers/2024.json', requestStage: 'Request' }] })
  await send('Page.navigate', { url })
  await wait(`!!document.querySelector('#territory-search-input')`)
  await evaluate(`document.querySelector('#territory-search-input').focus()`)
  await wait(`document.querySelector('.territory-suggestions [role="alert"]')?.textContent.includes('No se pudo cargar')`)
  await send('Fetch.disable')
  await wait(`!!document.querySelector('.thematic-error')`)
  await evaluate(`[...document.querySelectorAll('button')].find(button=>button.textContent==='Reintentar capa').click()`)
  await wait(`document.querySelector('.mexico-map').dataset.layerReady === 'true'`)
  record('Capas: error de red explícito, reintento y recuperación sin bloquear el mapa', {})
  await evaluate(`[...document.querySelectorAll('button')].find(button=>button.textContent==='Reintentar catálogo').click()`)
  await typeSearch('Chih')
  await wait(`!!document.querySelector('[role="option"][data-place-kind="state"][data-place-code="08"]')`)
  assert.equal(requests.filter(url => /\/data\/municipalities\/\d{2}\.json$/.test(url)).length, 0)
  await pressKey('ArrowDown', 'ArrowDown', 40)
  assert.ok(await evaluate(`!!document.querySelector('#territory-search-input').getAttribute('aria-activedescendant')`))
  await pressKey('Escape', 'Escape', 27)
  assert.equal(await evaluate(`document.querySelector('#territory-search-input').getAttribute('aria-expanded')`), 'false')
  await typeSearch('San Pedro')
  await wait(`document.querySelectorAll('.territory-suggestions [role="option"]').length > 1`)
  assert.ok((await evaluate(`[...new Set([...document.querySelectorAll('.territory-suggestions [role="option"]')].map(node=>node.dataset.placeState))].length`)) > 1)
  await pressKey('ArrowUp', 'ArrowUp', 38)
  assert.equal(await evaluate(`document.querySelector('#territory-search-input').getAttribute('aria-activedescendant') === [...document.querySelectorAll('.territory-suggestions [role="option"]')].at(-1).id`), true)
  await select('electoral-year', '2009')
  await wait(`document.querySelector('#territory-search-input').getAttribute('aria-activedescendant') === null`)
  assert.equal(await evaluate(`document.querySelector('#territory-search-input').getAttribute('aria-activedescendant')`), null)
  await select('electoral-year', '2024')
  await typeSearch('zzzzzzzzzz')
  await wait(`document.querySelector('.territory-suggestions')?.textContent.includes('Sin coincidencias')`)
  await typeSearch('')
  assert.ok((await evaluate(`document.querySelector('.territory-suggestions').textContent`)).includes('Escribe un nombre'))
  await pressKey('Escape', 'Escape', 27)
  record('Autocompletado: carga/error/reintento, vacío, sin coincidencias, duplicados y Escape sin descargar geometrías', {})
  await setTheme('light')
  await checkContrast('light')
  await select('electoral-year', '2024')
  await wait(`document.querySelector('.demographic-heading > p')?.textContent.includes('México')`)
  assert.equal(await evaluate(`document.querySelector('.territory-detail .card-heading h2').textContent`), 'México')
  assert.deepEqual(await evaluate(`[...document.querySelectorAll('.territorial-counts dd')].map(node=>node.textContent)`), ['98,330,348', '54,899,228', '37,105,466', '6,325,654'])
  assert.ok((await evaluate(`document.querySelector('.quality-coverage').textContent`)).includes('93.57 %'))
  assert.equal(await evaluate(`document.querySelector('.quality-details').open`), false)
  assert.equal(await evaluate(`document.querySelector('.map-sources').open`), false)
  assert.equal(await evaluate(`document.querySelector('.atlas-guide-dialog').open`), false)
  assert.equal(await evaluate(`document.querySelectorAll('.territorial-counts dt > .icon').length`), 4)
  assert.equal(await evaluate(`document.querySelector('.demographic-panel').checkVisibility()`), false)
  await evaluate(`document.querySelector('[data-territory-view="summary"]').focus()`)
  await pressKey('ArrowRight', 'ArrowRight', 39)
  assert.equal(await evaluate(`document.querySelector('.demographic-panel').checkVisibility()`), true)
  assert.equal(await evaluate(`document.querySelector('.election-metrics').checkVisibility()`), false)
  assert.equal(await evaluate(`document.querySelectorAll('.territory-view-tabs [tabindex="0"]').length`), 1)
  await pressKey('Home', 'Home', 36)
  assert.equal(await evaluate(`document.querySelector('.election-metrics').checkVisibility()`), true)
  record('Ficha por vistas: resumen inicial, demografía accesible con teclado y panel inactivo oculto', {})
  assert.equal(await evaluate(`document.querySelectorAll('.demographic-bar-row').length`), 9)
  await changeAxis('sex')
  assert.equal(await evaluate(`document.querySelectorAll('.demographic-bar-row').length`), 3)
  assert.ok((await evaluate(`document.querySelector('.demographic-chart').textContent`)).includes('77.45 %'))
  await changeAxis('age')
  assert.equal(await evaluate(`document.querySelectorAll('.demographic-bar-row').length`), 3)
  assert.ok((await evaluate(`document.querySelector('.demographic-coverage').textContent`)).includes('98,317,151'))
  assert.equal(await evaluate(`document.querySelector('.demographic-method').open`), false)
  await evaluate(`document.querySelector('.coverage-details summary').click()`)
  assert.ok(await evaluate(`[...document.querySelectorAll('.coverage-details p')].some(p=>p.checkVisibility()&&p.textContent.includes('98,317,151'))`))
  await screenshot('national-demographics-light')
  await evaluate(`document.querySelector('.coverage-details summary').click()`)
  record('Tarjetas, cobertura y detalle progresivo: cifras reales, iconos, alcance y fórmulas accesibles', {})
  for (const year of [2009, 2012, 2015, 2018, 2021, 2024]) {
    await select('electoral-year', String(year))
    await wait(`document.querySelector('.demographic-heading > p')?.textContent.includes('México') && document.querySelector('.demographic-heading > p')?.textContent.includes('${year}')`)
    const reference = JSON.parse(readFileSync(`public/data/territorial/summaries/${year}/national.json`, 'utf8'))
    assert.equal(await evaluate(`document.querySelector('.territorial-counts dd').textContent`), reference.totals.LN.toLocaleString('es-MX'))
    assert.equal(await evaluate(`[...document.querySelectorAll('.demographic-legend span')].some(node=>node.textContent==='No binario')`), year === 2024)
  }
  record('Ficha de México, tres vistas y seis elecciones; No binario sólo donde está registrado', {})
  assert.equal(await evaluate(`document.querySelector('.demographic-axis select') === null && document.querySelectorAll('.demographic-axis button .icon').length === 3`), true)
  await evaluate(`document.querySelector('[data-demographic-axis="sex"]').focus()`)
  await pressKey('Enter', 'Enter', 13, '\r')
  await wait(`document.querySelector('.demographic-panel').dataset.axis === 'sex'`)
  assert.equal(await evaluate(`document.querySelector('.mexico-map').dataset.mapScale`),'relative')
  assert.equal(await evaluate(`document.querySelector('[data-highlight="coverage"] > strong').textContent`),'6.43 %')
  for (const layer of ['participation','nonparticipation','women','men','women_participants','men_participants','nonbinary','age18_34','age35_59','age60_100']) {
    await chooseLayer(layer)
    assert.equal(await assertMapValues(2024,layer),32)
  }
  await chooseLayer('participation')
  const relativeValues=await evaluate(`[...document.querySelectorAll('.mexico-map path[role="button"]')].map(node=>node.dataset.thematicValue)`)
  await wait(`new Set([...document.querySelectorAll('.mexico-map path[role="button"]')].map(node=>getComputedStyle(node).fill)).size===5`)
  assert.equal(await evaluate(`new Set([...document.querySelectorAll('.mexico-map path[role="button"]')].map(node=>getComputedStyle(node).fill)).size`),5)
  await chooseView('summary')
  await screenshot('atlas-national-participation')
  assert.equal(await evaluate(`document.querySelector('.thematic-scale-control')===null && document.querySelectorAll('button[data-map-scale]').length===0 && !document.body.textContent.includes('Escala absoluta')`),true)
  assert.deepEqual(await evaluate(`[...document.querySelectorAll('[data-layer-group]')].map(node=>node.textContent)`),['Participación','Sexo','Edad','Tipo de sección electoral'])
  assert.equal(await evaluate(`document.querySelector('.thematic-values').open`),false)
  assert.equal(await evaluate(`document.querySelector('.thematic-class-list').checkVisibility()`),false)
  await evaluate(`document.querySelector('.thematic-values summary').focus()`)
  await pressKey('Enter','Enter',13,'\r')
  await wait(`document.querySelector('.thematic-values').open`)
  assert.equal(await evaluate(`document.querySelector('.thematic-class-list').checkVisibility()`),true)
  assert.equal(await evaluate(`document.querySelectorAll('.thematic-values tbody tr').length`),0)
  await screenshot('atlas-legend-methodology','.territory-layout > .card')
  await evaluate(`document.querySelector('.thematic-territories summary').click()`)
  await wait(`document.querySelectorAll('.thematic-values tbody tr').length===32`)
  assert.equal(await evaluate(`document.querySelectorAll('.thematic-values tbody tr').length`),32)
  await assertMapValues(2024,'participation')
  assert.deepEqual(await evaluate(`[...document.querySelectorAll('.mexico-map path[role="button"]')].map(node=>node.dataset.thematicValue)`),relativeValues)
  await evaluate(`document.querySelector('.thematic-territories summary').click()`)
  await evaluate(`document.querySelector('.thematic-values summary').click()`)
  await chooseLayer('nonparticipation')
  await screenshot('atlas-national-nonparticipation')
  record('Cuantiles permanentes: controles conservados, selector retirado y metodología accesible sin alterar porcentajes',{})
  await chooseLayer('nonbinary')
  await assertMapValues(2024,'nonbinary')
  assert.equal(await evaluate(`document.querySelectorAll('.mexico-map path[style*="url("]').length`),0)
  assert.equal(await evaluate(`document.querySelectorAll('.thematic-ramp i').length`),0)
  assert.ok((await evaluate(`document.querySelector('.thematic-availability').textContent`)).includes('registros disponibles de No binario en 2024'))
  await wait(`new Set([...document.querySelectorAll('.mexico-map path[role="button"]')].map(node=>getComputedStyle(node).fill)).size===2`)
  assert.equal(await evaluate(`new Set([...document.querySelectorAll('.mexico-map path[role="button"]')].map(node=>getComputedStyle(node).fill)).size`),2)
  await screenshot('atlas-nonbinary-support','.territory-layout > .card')
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:20,y:20})
  await evaluate(`document.querySelector('.mexico-map path[data-thematic-status="low_support"]').focus({preventScroll:true})`)
  await wait(`document.querySelector('.map-value-card')?.dataset.tooltipStatus==='low_support'`)
  assert.ok((await evaluate(`document.querySelector('.map-value-support').textContent`)).includes('insuficiente'))
  assert.ok(!(await evaluate(`document.querySelector('.map-value-number').textContent`)).includes('Sin información'))
  assert.equal(await evaluate(`document.querySelector('.map-value-track')===null`),true)
  await setTheme('dark')
  await assertMapValues(2024,'nonbinary')
  await screenshot('atlas-nonbinary-dark','.territory-layout > .card')
  await setTheme('light')
  await select('electoral-year','2018')
  await assertMapValues(2018,'nonbinary')
  assert.ok((await evaluate(`document.querySelector('.thematic-availability').textContent`)).includes('no está registrado en los datos de 2018'))
  assert.equal(await evaluate(`document.querySelector('.mexico-map [data-thematic-status="unavailable_category"]').getAttribute('data-thematic-value')`),null)
  await screenshot('atlas-nonbinary-unregistered','.territory-layout > .card')
  record('No binario: neutros sin patrones, registros escasos conservados y ausencia histórica sin cero',{})
  for (const year of [2009,2012,2015,2018,2021,2024]) {
    await select('electoral-year',String(year))
    for (const layer of ['participation','nonparticipation','women','men','women_participants','men_participants','age18_34','age35_59','age60_100']) {
      await chooseLayer(layer); await assertMapValues(year,layer)
    }
    await evaluate(`document.querySelector('[data-layer-group="sex"]').click()`)
    assert.equal(await evaluate(`document.querySelector('button[data-map-layer="nonbinary"]').disabled`),year!==2024)
  }
  await chooseLayer('participation')
  await mapPoint()
  const hoverPoint = await evaluate(`(() => {const path=document.querySelector('.mexico-map path[data-map-code="30"]'), b=path.getBBox(), m=path.getScreenCTM();for(let i=1;i<10;i++)for(let j=1;j<10;j++){const p=new DOMPoint(b.x+b.width*i/10,b.y+b.height*j/10);if(path.isPointInFill(p)){const c=p.matrixTransform(m);if(document.elementFromPoint(c.x,c.y)===path)return {x:c.x,y:c.y}}}return null})()`)
  assert.ok(hoverPoint)
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',...hoverPoint})
  await wait(`document.querySelector('.map-value-card')?.dataset.tooltipCode === '30'`)
  const veracruzReference = JSON.parse(readFileSync('public/data/territorial/summaries/2024/30.json','utf8')).totals
  const veracruzRate = veracruzReference.SV/(veracruzReference.SV+veracruzReference.NV)
  assert.equal(await evaluate(`document.querySelector('.map-value-number').textContent`),`${(veracruzRate*100).toLocaleString('es-MX',{minimumFractionDigits:1,maximumFractionDigits:2})} %`)
  await evaluate(`document.querySelector('.mexico-map path[data-map-code="30"][role="button"]').focus()`)
  await wait(`document.querySelector('.map-value-card').dataset.tooltipCode === '30'`)
  assert.equal(await evaluate(`document.querySelector('.map-value-card').dataset.tooltipYear`),'2024')
  await pressKey('Escape','Escape',27)
  assert.equal(await evaluate(`document.querySelector('.map-value-card') === null`),true)
  await evaluate(`document.querySelector('.map-detail-action').click()`)
  assert.equal(await evaluate(`document.activeElement.id`),'territory-detail')
  await chooseView('summary')
  await screenshot('atlas-national-light')
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:20,y:20})
  await evaluate(`document.querySelector('.mexico-map path[data-map-code="30"][role="button"]').focus({preventScroll:true})`)
  await wait(`document.querySelector('.map-value-card')?.dataset.tooltipCode === '30'`)
  await evaluate(`document.querySelector('.map-value-open').scrollIntoView({block:'center',behavior:'instant'})`)
  const openPoint=await evaluate(`(() => {const r=document.querySelector('.map-value-open').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()`)
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',...openPoint})
  await send('Input.dispatchMouseEvent',{type:'mousePressed',...openPoint,button:'left',clickCount:1})
  await send('Input.dispatchMouseEvent',{type:'mouseReleased',...openPoint,button:'left',clickCount:1})
  await wait(`document.querySelector('.territory-explorer').dataset.stateCode==='30' && document.querySelector('.territory-detail .card-heading h2')?.textContent==='Veracruz'`)
  assert.equal(await evaluate(`document.activeElement.id`),'territory-detail')
  await select('state-picker','')
  await wait(`document.querySelector('.territory-detail .card-heading h2')?.textContent==='México'`)
  record('Acción contextual: abre la ficha del territorio consultado y lleva el foco a su panel',{})
  record('Atlas nacional: diez capas, seis elecciones, cifras y clases fuente, categorías, leyenda, teclado y acción de ficha', {})
  await wait(`document.querySelectorAll('.ranking-list .ranking-row').length === 10`)
  const statesReference = JSON.parse(readFileSync('public/data/participamx_multiyear/elections/2024/states.json', 'utf8')).data.sort((a,b)=>b.SV/(b.SV+b.NV)-a.SV/(a.SV+a.NV))
  assert.equal(await evaluate(`document.querySelector('.ranking-row').dataset.rankCode`), statesReference[0].state_code.padStart(2,'0'))
  await evaluate(`[...document.querySelectorAll('.ranking-order button')].find(button=>button.textContent.includes('Menor')).click()`)
  await wait(`document.querySelector('.ranking-row')?.dataset.rankCode === '${statesReference.at(-1).state_code.padStart(2,'0')}'`)
  assert.equal(await evaluate(`document.querySelector('.ranking-row').dataset.rankCode`), statesReference.at(-1).state_code.padStart(2,'0'))
  await evaluate(`[...document.querySelectorAll('.ranking-pagination button')].find(button=>button.textContent==='Siguiente').click()`)
  assert.equal(await evaluate(`document.querySelector('.ranking-position').textContent`), '11')
  await evaluate(`[...document.querySelectorAll('.ranking-order button')].find(button=>button.textContent.includes('Mayor')).click()`)
  await wait(`document.querySelector('.ranking-position')?.textContent === '1'`)
  record('Ranking nacional de 32 entidades: orden ascendente/descendente y páginas de diez', {})
  await chooseView('summary')
  await screenshot('national-overview-light')

  await typeSearch('Chih')
  await wait(`!!document.querySelector('[role="option"][data-place-kind="state"][data-place-code="08"]')`)
  await pressKey('ArrowDown', 'ArrowDown', 40); await pressKey('Enter', 'Enter', 13, '\r')
  await wait(`document.querySelector('.territory-explorer')?.dataset.stateCode === '08' && document.querySelectorAll('.ranking-row').length === 10`)
  const chihuahua = JSON.parse(readFileSync('public/data/territorial/2024/08.json', 'utf8')).data.filter(row=>row.totals.LN>=100&&row.totals.SV+row.totals.NV>=100&&row.totals.source_row_count>=5).sort((a,b)=>b.totals.SV/(b.totals.SV+b.totals.NV)-a.totals.SV/(a.totals.SV+a.totals.NV)||a.ine_code.localeCompare(b.ine_code))
  assert.equal(await evaluate(`document.querySelector('.ranking-row').dataset.rankCode`), chihuahua[0].ine_code)
  await evaluate(`[...document.querySelectorAll('.ranking-order button')].find(button=>button.textContent.includes('Menor')).click()`)
  await wait(`document.querySelector('.ranking-row')?.dataset.rankCode === '${chihuahua.at(-1).ine_code}'`)
  assert.equal(await evaluate(`document.querySelector('.ranking-row').dataset.rankCode`), chihuahua.at(-1).ine_code)
  await evaluate(`document.querySelector('.ranking-row').click()`)
  await wait(`!!document.querySelector('.demographic-panel') && !!document.querySelector('.ranking-row[aria-pressed="true"]') && !!document.querySelector('.territory-explorer').dataset.municipalityCode`)
  assert.equal(await evaluate(`document.querySelector('.territory-explorer').dataset.electionYear`), '2024')
  record('Chihuahua por teclado: ranking municipal real y selección compartida con ficha y mapa', {})
  await typeSearch('XÁLAPA')
  await wait(`!!document.querySelector('[role="option"][data-place-kind="municipality"][data-place-state="30"]')`)
  await pressKey('ArrowDown', 'ArrowDown', 40); await pressKey('Enter', 'Enter', 13, '\r')
  await wait(`document.querySelector('.territory-explorer').dataset.stateCode === '30' && document.querySelector('.demographic-heading > p')?.textContent.includes('Xalapa')`)
  await wait(`!!document.querySelector('.ranking-row[aria-pressed="true"]')`)
  assert.ok((await evaluate(`document.querySelectorAll('.ranking-row').length`)) <= 10)
  for (const layer of ['participation','nonparticipation','women','men','women_participants','men_participants','nonbinary','age18_34','age35_59','age60_100']) {
    await chooseLayer(layer); await assertMapValues(2024,layer,'30')
  }
  await chooseLayer('women')
  await wait(`document.querySelector('.map-value-card')?.dataset.tooltipCode === '30087'`)
  assert.ok((await evaluate(`document.querySelector('.map-value-card').textContent`)).includes('Lista nominal total'))
  await evaluate(`document.querySelector('.state-return').click()`)
  await waitCamera()
  await screenshot('atlas-state-women','.territory-layout > .card')
  await chooseLayer('men'); await screenshot('atlas-state-men','.territory-layout > .card')
  await chooseLayer('women_participants'); await screenshot('atlas-state-women-participants','.territory-layout > .card')
  await chooseLayer('age18_34'); await screenshot('atlas-age18-34','.territory-layout > .card')
  await pickMunicipality('Xalapa')
  await wait(`document.querySelector('.territory-explorer').dataset.municipalityCode==='30087'`)
  await chooseLayer('women')
  await evaluate(`document.querySelector('.thematic-values summary').click()`)
  await evaluate(`document.querySelector('.thematic-territories summary').click()`)
  await wait(`document.querySelectorAll('.thematic-values tbody tr').length===212`)
  assert.equal(await evaluate(`document.querySelectorAll('.thematic-values tbody tr').length`),212)
  await evaluate(`document.querySelector('.thematic-territories summary').click()`)
  await evaluate(`document.querySelector('.thematic-values summary').click()`)
  await select('electoral-year','2018')
  for (const layer of ['women','men','women_participants','men_participants','age18_34','age35_59','age60_100','participation','nonparticipation']) {
    await chooseLayer(layer); await assertMapValues(2018,layer,'30')
  }
  assert.equal(await evaluate(`document.querySelector('.territory-explorer').dataset.municipalityCode`),'30087')
  await select('electoral-year','2024')
  await chooseLayer('nonbinary')
  await select('electoral-year','2018')
  await wait(`document.querySelector('.mexico-map').dataset.layerReady === 'true'`)
  await assertMapValues(2018,'nonbinary','30')
  assert.ok((await evaluate(`document.querySelector('.thematic-category-note').textContent`)).includes('2018'))
  await select('electoral-year','2024'); await chooseLayer('participation')
  await chooseView('summary')
  await screenshot('atlas-municipal-light')
  await screenshot('atlas-selected-municipality','.territory-layout > .card')
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.selection-outline')).fill`),'none')
  await wait(`document.querySelector('.atlas-highlights > header > span')?.textContent.includes('Xalapa') && document.querySelector('[data-highlight="coverage"] > strong')?.textContent === '13.03 %'`)
  record('Atlas municipal: diez capas fuente, contorno sin relleno, contexto real, Xalapa persistente y categoría ausente sin cero', {})
  await screenshot('national-search-ranking')
  record('Búsqueda nacional Xalapa desde otro estado: ficha, selección y ranking sincronizados', {})
  await select('state-picker', '')
  assert.ok((await evaluate(`document.querySelector('.search-scope').textContent`)).includes('Todo México'))
  assert.equal(await evaluate(`document.querySelector('#territory-search-input').value`), '')
  await wait(`document.querySelector('.demographic-heading > p')?.textContent.includes('México')`)
  await waitCamera()
  const beforeButton = await mapWidth()
  await evaluate(`document.querySelector('[aria-label="Acercar mapa"]').click()`)
  await waitCamera()
  assert.ok((await mapWidth()) < beforeButton)
  await evaluate(`document.querySelector('[aria-label="Alejar mapa"]').click()`)
  await waitCamera()
  assert.ok(Math.abs((await mapWidth()) - beforeButton) < 1e-6)
  let point = await mapPoint()
  const normalWheelWidth = await mapWidth(), scrollBefore = await evaluate('scrollY')
  const stableBreaks=await evaluate(`document.querySelector('.thematic-legend').dataset.scaleBreaks`)
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point })
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', ...point, deltaX: 0, deltaY: 120 })
  await sleep(200)
  assert.equal(await mapWidth(), normalWheelWidth)
  assert.ok((await evaluate('scrollY')) > scrollBefore)
  point = await mapPoint()
  const ctrlScrollBefore = await evaluate('scrollY')
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', ...point, deltaX: 0, deltaY: -120, modifiers: 2 })
  await sleep(200)
  assert.ok((await mapWidth()) < normalWheelWidth)
  assert.equal(await evaluate('scrollY'), ctrlScrollBefore)
  const stateBeforeDrag = await evaluate(`document.querySelector('.territory-explorer').dataset.stateCode`)
  const viewBeforeDrag = await evaluate(`document.querySelector('.mexico-map').getAttribute('viewBox')`)
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', clickCount: 1 })
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: point.x + 45, y: point.y + 25, buttons: 1 })
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: point.x + 45, y: point.y + 25, button: 'left', clickCount: 1 })
  assert.notEqual(await evaluate(`document.querySelector('.mexico-map').getAttribute('viewBox')`), viewBeforeDrag)
  assert.equal(await evaluate(`document.querySelector('.territory-explorer').dataset.stateCode`), stateBeforeDrag)
  const activeWheelWidth = await mapWidth()
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', ...point, deltaX: 0, deltaY: -80 })
  await sleep(200)
  assert.ok((await mapWidth()) < activeWheelWidth)
  await pressKey('Escape', 'Escape', 27)
  assert.equal(await evaluate(`document.querySelector('.mexico-map').dataset.wheelActive`), 'false')
  await sleep(400)
  const beforeDouble = await mapWidth()
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', clickCount: 2 })
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', clickCount: 2 })
  await waitCamera()
  assert.ok((await mapWidth()) < beforeDouble)
  await evaluate(`document.querySelector('[aria-label="Ver todo México"]').click()`)
  await waitCamera()
  assert.equal(await evaluate(`document.querySelector('.territory-explorer').dataset.electionYear`), '2024')
  assert.equal(await mapWidth(), 800)
  point = await mapPoint()
  await evaluate(`document.querySelector('[aria-label="Acercar mapa"]').click()`)
  await sleep(90)
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', ...point, deltaX: 0, deltaY: -50, modifiers: 2 })
  await sleep(150)
  const interruptedWidth = await mapWidth()
  await sleep(450)
  assert.equal(await mapWidth(), interruptedWidth)
  await evaluate(`document.querySelector('[aria-label="Encuadrar territorio seleccionado"]').click()`)
  await waitCamera()
  assert.equal(await evaluate(`document.querySelector('.thematic-legend').dataset.scaleBreaks`),stableBreaks)
  record('Zoom y desplazamiento no recalibran los cortes del alcance estadístico',{})
  record('Zoom +/−, rueda cooperativa, Ctrl+rueda, arrastre sin clic accidental, doble clic y regreso nacional', {})
  record('Interacción de rueda interrumpe animación sin retorno al destino anterior', {})
  await clickGeometry('08')
  await wait(`document.querySelector('.territory-explorer').dataset.stateCode === '08' && !!document.querySelector('path[data-map-code="08001"]')`)
  await waitCamera()
  await clickGeometry('08001')
  await wait(`document.querySelector('.demographic-heading > p')?.textContent.includes('Ahumada')`)
  assert.equal(await evaluate(`document.querySelector('.territory-explorer').dataset.municipalityCode`), '08001')
  record('Clic real sobre geometrías: Chihuahua y municipio Ahumada', {})
  await select('state-picker', '')
  await waitCamera()
  await evaluate(`document.querySelector('.mexico-map [role="button"][tabindex="0"]').focus()`)
  const firstCode = await evaluate(`document.activeElement.dataset.mapCode`)
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39 })
  assert.notEqual(await evaluate(`document.activeElement.dataset.mapCode`), firstCode)
  assert.equal(await evaluate(`document.querySelectorAll('.mexico-map [role="button"][tabindex="0"]').length`), 1)
  record('Mapa con un punto de Tab y recorrido por flechas', {})
  const animation = await evaluate(`new Promise(resolve => { const map=document.querySelector('.mexico-map'); const from=map.getAttribute('viewBox'); map.querySelector('path[data-map-code="01"]').dispatchEvent(new MouseEvent('click',{bubbles:true}));const frames=[];function sample(){frames.push(map.getAttribute('viewBox'));if(frames.length<40)requestAnimationFrame(sample);else resolve({from,frames,target:map.dataset.targetViewbox,connected:map.isConnected});}requestAnimationFrame(sample);})`)
  assert.equal(animation.connected, true)
  assert.ok(animation.frames.some(frame => frame !== animation.from && frame !== animation.target))
  await wait(`document.querySelector('.mexico-map').getAttribute('viewBox') === document.querySelector('.mexico-map').dataset.targetViewbox`)
  record('Acercamiento SVG gradual sin remontar el mapa', { frames: animation.frames.length })
  await wait(`document.querySelector('.territory-explorer').dataset.stateCode === '01'`)
  await wait(`document.querySelector('.territory-detail .card-heading h2')?.textContent.toLocaleUpperCase('es-MX').includes('AGUASCALIENTES')`)
  await changeAxis('sex')
  assert.equal(await evaluate(`document.querySelectorAll('.demographic-bar-row').length`), 3)
  await changeAxis('age')
  assert.equal(await evaluate(`document.querySelectorAll('.demographic-bar-row').length`), 3)
  await changeAxis('crossed')
  await screenshot('state-overview-light')
  const stateCounts = await evaluate(`[...document.querySelectorAll('.territorial-counts dd')].map(node => node.textContent)`)
  assert.deepEqual(stateCounts, ['1,097,171', '626,084', '441,222', '29,865'])
  await chooseMunicipality('San Francisco de los Romo')
  assert.equal(await evaluate(`document.querySelector('.territory-heading').textContent.includes('INE 01010 · INEGI 01011')`), true)
  assert.equal(await evaluate(`document.querySelectorAll('.demographic-bar-row').length`), 6)
  const layout = await evaluate(`(() => {const map=document.querySelector('.territory-layout > .card').getBoundingClientRect();const panel=document.querySelector('.territory-detail').getBoundingClientRect();return {map:map.width,panel:panel.width,share:map.width/(map.width+panel.width)}})()`)
  assert.ok(layout.share > .55 && layout.share < .65)
  record('Estado real, municipio con claves INE/INEGI distintas y distribución de escritorio', layout)
  await screenshot('desktop-light')

  await evaluate(`[...document.querySelectorAll('.demographic-switch button')].find(button => button.textContent.includes('Distribución')).click()`)
  assert.ok((await evaluate(`document.querySelector('.demographic-definition').textContent`)).includes('universo parcial'))
  const shares = await evaluate(`[...document.querySelectorAll('.demographic-bar')].map(node => parseFloat(node.style.width))`)
  // CSSOM redondea porcentajes al serializarlos; los cálculos crudos se prueban a 1e-12.
  assert.ok(Math.abs(shares.reduce((sum, value) => sum + value, 0) - 100) < 1e-3)
  await evaluate(`document.querySelector('.demographic-details summary').click()`)
  assert.equal(await evaluate(`document.querySelector('.demographic-details .territorial-table tbody').rows.length`), 6)
  record('Distribución SV parcial suma 100 y tabla accesible de seis celdas', { shares })

  await select('state-picker', '09')
  await chooseMunicipality('Coyoacán')
  await chooseView('demographics')
  assert.equal(await evaluate(`document.querySelector('.territory-heading').textContent.includes('INE 09003')`), true)
  await setTheme('dark')
  await checkContrast('dark')
  await assertMapValues(2024,'participation','09')
  await wait(`getComputedStyle(document.querySelector('.selection-outline')).stroke === 'rgb(255, 226, 166)'`)
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.selection-outline')).stroke`),'rgb(255, 226, 166)')
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.selection-outline')).fill`),'none')
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.turnout-spotlight')).backgroundColor`), 'rgb(54, 42, 64)')
  await evaluate(`document.querySelector('.demographic-switch button').focus()`)
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  assert.equal(await evaluate(`getComputedStyle(document.activeElement).outlineStyle`), 'solid')
  assert.ok((await evaluate(`document.activeElement.textContent`)).includes('Distribución'))
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: '\r', unmodifiedText: '\r' })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
  await wait(`document.querySelector('.demographic-definition')?.textContent.includes('universo parcial')`)
  await evaluate(`document.querySelector('.demographic-switch button').click()`)
  await screenshot('desktop-dark')
  await screenshot('atlas-dark','.territory-layout > .card')
  record('Coyoacán 2024, modo oscuro y foco visible', {})

  await select('electoral-year', '2009')
  await wait(`document.querySelector('.demographic-heading > p')?.textContent.includes('Coyoacán') && document.querySelector('.demographic-heading > p')?.textContent.includes('2009')`)
  assert.equal(await evaluate(`document.querySelector('.territory-explorer').dataset.municipalityCode`), '09003')
  const historical = JSON.parse(readFileSync('public/data/territorial/2009/09.json', 'utf8')).data.find(row => row.ine_code === '09003')
  const displayedLN = await evaluate(`document.querySelector('.territorial-counts dd').textContent`)
  assert.equal(displayedLN, historical.totals.LN.toLocaleString('es-MX'))
  assert.ok((await evaluate(`document.querySelector('.demographic-heading').textContent`)).includes('2009'))
  record('Municipio persiste al cambiar de elección sin reutilizar cifras de 2024', { year: 2009, LN: historical.totals.LN })
  await evaluate(`document.querySelector('[role="radio"][data-election-year="2009"]').focus()`)
  await pressKey('ArrowRight', 'ArrowRight', 39)
  await wait(`document.querySelector('.demographic-heading > p')?.textContent.includes('2012')`)
  assert.equal(await evaluate(`document.querySelector('.territory-explorer').dataset.municipalityCode`), '09003')
  await pressKey('End', 'End', 35)
  await wait(`document.querySelector('.demographic-heading > p')?.textContent.includes('2024')`)
  assert.equal(await evaluate(`document.querySelectorAll('.election-timeline [role="radio"][tabindex="0"]').length`), 1)
  record('Línea de elecciones por teclado con territorio persistente y un punto de Tab', {})

  await select('electoral-year', '2024'); await select('state-picker', '16')
  const unavailable = JSON.parse(readFileSync('public/data/territorial/2024/16.json', 'utf8')).data.find(row => row.ine_code === '16112')
  await chooseMunicipality(unavailable.municipality_name)
  assert.equal(await evaluate(`document.querySelector('.turnout-spotlight > strong').textContent`), 'No disponible')
  await wait(`document.querySelector('.mexico-map').dataset.layerReady === 'true'`)
  assert.equal(await evaluate(`document.querySelector('.municipality-shape[aria-pressed="true"]').dataset.thematicStatus`),'undefined')
  assert.equal(await evaluate(`document.querySelector('.municipality-shape[aria-pressed="true"]').getAttribute('data-thematic-value')`),null)
  assert.equal(await evaluate(`document.querySelectorAll('.demographic-bar').length`), 0)
  await chooseView('summary')
  assert.ok((await evaluate(`document.querySelector('.quality-coverage').textContent`)).includes('0 %'))
  assert.equal(await evaluate(`document.querySelector('.quality-details').open`), false)
  assert.ok(await evaluate(`[...document.querySelectorAll('.quality-callout')].some(p=>p.checkVisibility()&&p.textContent.includes('No especificación elevada'))`))
  await chooseView('demographics')
  assert.ok(await evaluate(`[...document.querySelectorAll('.demographic-quality-flags li')].some(p=>p.checkVisibility()&&p.textContent.includes('tasas no definidas'))`))
  record('Municipio sin participación especificada mantiene tasas no disponibles', { municipality: unavailable.municipality_name })

  await select('state-picker', '24')
  await pickMunicipality('Villa de Pozos')
  await wait(`document.querySelector('.key-correspondence')?.textContent.includes('pendiente')`)
  assert.equal(await evaluate(`document.querySelector('.demographic-panel') === null`), true)
  await select('electoral-year', '2009')
  await wait(`!document.querySelector('.territorial-loading') && document.querySelector('.territory-heading')?.textContent.includes('pendiente')`)
  assert.equal(await evaluate(`document.querySelector('.territory-explorer').dataset.municipalityCode`), '24059')
  await wait(`document.querySelector('.mexico-map').dataset.layerReady === 'true'`)
  assert.equal(await evaluate(`document.querySelector('.municipality-shape[data-map-code="24059"]').dataset.thematicStatus`),'unmapped')
  assert.equal(await evaluate(`document.querySelector('.demographic-panel') === null`), true)
  await select('electoral-year', '2024')
  record('Correspondencia pendiente no recibe cifras por fallback INEGI', {})

  await send('Fetch.enable', { patterns: [{ urlPattern: '*/data/territorial/2024/02.json', requestStage: 'Request' }] })
  await select('state-picker', '02')
  await chooseMunicipalityForError('Mexicali')
  await wait(`document.querySelector('.territorial-status[role="alert"]')?.textContent.includes('No se pudo cargar la ficha')`)
  await send('Fetch.disable')
  await evaluate(`[...document.querySelectorAll('button')].find(button => button.textContent === 'Reintentar ficha').click()`)
  await wait(`document.querySelector('.demographic-heading > p')?.textContent.includes('Mexicali')`)
  record('Error de red y reintento recuperable', {})

  const cachedCount = requests.filter(url => url.endsWith('/territorial/2024/09.json')).length
  await select('state-picker', '01'); await select('state-picker', '09')
  await chooseMunicipality('Coyoacán')
  assert.equal(requests.filter(url => url.endsWith('/territorial/2024/09.json')).length, cachedCount)
  record('Cambio rápido de entidad y caché por año/estado sin datos obsoletos', { requests2024CDMX: cachedCount })
  await send('Emulation.setDeviceMetricsOverride', { width: 1024, height: 900, deviceScaleFactor: 1, mobile: false })
  await setTheme('light')
  const tablet = await evaluate(`(() => {const r=document.querySelector('.interactive-map').getBoundingClientRect(), controls=document.querySelector('.map-floating-controls').getBoundingClientRect();return {width:innerWidth,clientWidth:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth,controlsInside:controls.left>=r.left&&controls.right<=r.right&&controls.top>=r.top&&controls.bottom<=r.bottom}})()`)
  assert.equal(tablet.clientWidth, tablet.scrollWidth); assert.equal(tablet.controlsInside, true)
  await screenshot('tablet-light')
  record('Tableta 1024px: controles dentro del mapa y sin desbordamiento horizontal', tablet)
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
  await setTheme('light')
  await sleep(200)
  const mobile = await evaluate(`(() => {const map=document.querySelector('.territory-layout > .card').getBoundingClientRect();const panel=document.querySelector('.territory-detail').getBoundingClientRect();return {mapBottom:map.bottom,panelTop:panel.top,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,motion:getComputedStyle(document.querySelector('.demographic-bar')).transitionDuration}})()`)
  assert.ok(mobile.panelTop >= mobile.mapBottom)
  assert.equal(mobile.scrollWidth, mobile.width)
  assert.equal(mobile.motion, '0s')
  await select('state-picker', '')
  await wait(`document.querySelector('.mexico-map')?.dataset.reducedMotion === 'true'`)
  assert.equal(await evaluate(`document.querySelector('.mexico-map').getAttribute('viewBox') === document.querySelector('.mexico-map').dataset.targetViewbox`), true)
  await wait(`document.querySelector('.demographic-heading > p')?.textContent.includes('México')`)
  await select('state-picker', '09'); await chooseMunicipality('Coyoacán')
  await send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 2 })
  let touchPoint = await mapPoint()
  const beforeTouchDrag = await evaluate(`document.querySelector('.mexico-map').getAttribute('viewBox')`)
  await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: touchPoint.x, y: touchPoint.y, id: 1, radiusX: 2, radiusY: 2, force: 1 }] })
  await send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: touchPoint.x + 18, y: touchPoint.y + 10, id: 1, radiusX: 2, radiusY: 2, force: 1 }] })
  await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  assert.notEqual(await evaluate(`document.querySelector('.mexico-map').getAttribute('viewBox')`), beforeTouchDrag)
  assert.equal(await evaluate(`document.querySelector('.territory-explorer').dataset.municipalityCode`), '09003')
  const pinchBefore = await mapWidth(), pinchCode = await evaluate(`document.querySelector('.territory-explorer').dataset.municipalityCode`)
  const touches = (gap) => [{ x: touchPoint.x - gap, y: touchPoint.y, id: 1, radiusX: 2, radiusY: 2, force: 1 }, { x: touchPoint.x + gap, y: touchPoint.y, id: 2, radiusX: 2, radiusY: 2, force: 1 }]
  await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: touches(22) })
  await send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: touches(44) })
  await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  assert.ok((await mapWidth()) < pinchBefore * .8)
  assert.equal(await evaluate(`document.querySelector('.territory-explorer').dataset.municipalityCode`), pinchCode)
  await sleep(400)
  await evaluate(`document.querySelector('[aria-label="Encuadrar territorio seleccionado"]').click()`)
  // Doble toque sobre la tarjeta del territorio seleccionado: no cambia primero a otro polígono.
  await evaluate(`document.querySelector('.map-value-number').scrollIntoView({block:'center',behavior:'instant'})`)
  touchPoint = await evaluate(`(() => {const r=document.querySelector('.map-value-number').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()`)
  const beforeTap = await mapWidth()
  for (let n = 0; n < 2; n++) {
    await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: touchPoint.x, y: touchPoint.y, id: 1, radiusX: 2, radiusY: 2, force: 1 }] })
    await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await sleep(80)
  }
  await sleep(150)
  assert.ok((await mapWidth()) < beforeTap, `Doble toque: ${beforeTap} -> ${await mapWidth()}`)
  await evaluate(`for(let n=0;n<60;n++)document.querySelector('[aria-label="Alejar mapa"]').click()`)
  assert.equal(await mapWidth(), 1200)
  assert.equal(await evaluate(`document.querySelector('[aria-label="Alejar mapa"]').disabled`), true)
  await evaluate(`for(let n=0;n<60;n++)document.querySelector('[aria-label="Acercar mapa"]').click()`)
  assert.equal(await mapWidth(), .25)
  assert.equal(await evaluate(`document.querySelector('[aria-label="Acercar mapa"]').disabled`), true)
  await evaluate(`document.querySelector('[aria-label="Ver todo México"]').click()`)
  assert.equal(await mapWidth(), 800)
  await select('state-picker', '09'); await chooseMunicipality('Coyoacán')
  record('Pellizco y doble toque reales, límites de zoom y controles deshabilitados con movimiento reducido', {})
  await screenshot('mobile-light')
  await screenshot('atlas-mobile','.territory-layout > .card')
  record('Pantalla 390px: ficha debajo del mapa, sin desbordamiento y movimiento reducido', mobile)
  assert.equal(errors.length, 0, JSON.stringify(errors))
  writeFileSync(join(cache, 'results.json'), JSON.stringify({ status: 'passed', checks, errors }, null, 2))
  console.log(`Capturas y resultados: ${cache}`)
} catch (error) {
  let page = null
  try {
    page = await evaluate(`({selection:document.querySelector('.territory-explorer')?.dataset,heading:document.querySelector('.territory-detail .card-heading')?.textContent, status:[...document.querySelectorAll('[role="alert"],[role="status"]')].map(node=>node.textContent)})`)
    await screenshot('failure')
  } catch { /* Conservar el error original si Chrome dejó de responder. */ }
  writeFileSync(join(cache, 'results.json'), JSON.stringify({ status: 'failed', error: String(error), checks, errors, page }, null, 2))
  throw error
} finally {
  if (socket?.readyState === WebSocket.OPEN) {
    try { await send('Browser.close') } catch { /* Chrome puede cerrar antes de responder. */ }
    socket.close()
  }
  browser.kill()
  server.closeAllConnections()
  await new Promise(resolve => server.close(resolve))
}

async function chooseMunicipalityForError(name) {
  await pickMunicipality(name)
}
