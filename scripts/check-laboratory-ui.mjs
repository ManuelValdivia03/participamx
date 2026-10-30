// Verificación local en Chrome, sin dependencias nuevas. Requiere npm run build.
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { createServer as createTcpServer } from 'node:net'
import { spawn } from 'node:child_process'
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, existsSync } from 'node:fs'
import { resolve, extname, join, sep } from 'node:path'

const root = resolve('dist'), cache = resolve('node_modules/.cache/laboratory-ui')
mkdirSync(cache, { recursive: true })
const executable = process.env.CHROME_PATH ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
assert.ok(existsSync(join(root, 'index.html')), 'Ejecutar npm run build antes de esta prueba')
assert.ok(existsSync(executable), 'Definir CHROME_PATH con un ejecutable Chromium instalado')
const runDirectory = mkdtempSync(join(cache, 'run-'))
const server = createServer((request, response) => {
  const path = resolve(root, '.' + decodeURIComponent(new URL(request.url, 'http://localhost').pathname))
  if (path !== root && !path.startsWith(root + sep)) { response.writeHead(403).end(); return }
  try {
    const target = path === root ? join(root, 'index.html') : path
    response.setHeader('Content-Type', ({ '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json' })[extname(target)] ?? 'application/octet-stream')
    response.end(readFileSync(target))
  } catch { response.writeHead(404).end() }
})
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
const reservation = createTcpServer()
await new Promise(resolve => reservation.listen(0, '127.0.0.1', resolve))
const port = reservation.address().port
await new Promise(resolve => reservation.close(resolve))
const browser = spawn(executable, ['--headless=new', '--no-first-run', '--no-default-browser-check', `--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(cache, 'chrome-'))}`, 'about:blank'], { windowsHide: true, stdio: 'ignore' })
let socket, nextId = 0
const pending = new Map(), errors = [], downloads = new Map(), checks = []
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++nextId
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)) }, 15000)
    pending.set(id, { resolve, reject, timer }); socket.send(JSON.stringify({ id, method, params }))
  })
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}
async function waitFor(check, message = 'Condición de navegador') {
  const deadline = Date.now() + 20000
  while (Date.now() < deadline) { if (await check()) return; await sleep(100) }
  throw new Error(`Tiempo agotado: ${message}`)
}
const wait = expression => waitFor(() => evaluate(expression), expression)
async function click(text) {
  await evaluate(`(() => { const button = [...document.querySelectorAll('button')].find(button => button.textContent.trim() === ${JSON.stringify(text)}); if (!button) throw new Error('Botón ausente: ' + ${JSON.stringify(text)}); button.click() })()`)
}
async function key(key, code, shiftKey = false) {
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key, code: key, windowsVirtualKeyCode: code, modifiers: shiftKey ? 8 : 0 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key, code: key, windowsVirtualKeyCode: code, modifiers: shiftKey ? 8 : 0 })
}
async function screenshot(name) {
  const { data } = await send('Page.captureScreenshot', { format: 'png' })
  writeFileSync(join(cache, name + '.png'), Buffer.from(data, 'base64'))
}
async function download(text, format) {
  const initial = downloads.size
  await click(text)
  await waitFor(() => [...downloads.values()].filter(item => item.state === 'completed').length > initial, text)
  await wait(`![...document.querySelectorAll('button')].some(button => button.textContent.includes('Generando'))`)
  const file = [...downloads.values()].at(-1)
  const bytes = readFileSync(join(runDirectory, file.name))
  if (format === 'pdf') {
    assert.equal(bytes.subarray(0, 5).toString(), '%PDF-')
    const content = bytes.toString('latin1')
    assert.match(content, /\(ParticipaMX\) Tj/)
    assert.match(content, /validaci.n institucional/)
    assert.doesNotMatch(content, /\/Subtype \/Image/)
  } else {
    assert.equal(bytes.subarray(1, 4).toString(), 'PNG')
    assert.equal(bytes.readUInt32BE(16), 1600)
    assert.ok(bytes.readUInt32BE(20) > 2000)
  }
  assert.ok(bytes.length > 3000)
  return file.name
}
function contrast(a, b) {
  const luminance = color => {
    const values = color.match(/[\d.]+/g).slice(0, 3).map(Number).map(v => { v /= 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4 })
    return values[0] * .2126 + values[1] * .7152 + values[2] * .0722
  }
  const x = luminance(a), y = luminance(b)
  return (Math.max(x, y) + .05) / (Math.min(x, y) + .05)
}

try {
  let targets
  await waitFor(async () => { try { targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); return targets.length } catch { return false } }, 'Inicio de Chrome')
  socket = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl)
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data), request = pending.get(message.id)
    if (request) { clearTimeout(request.timer); pending.delete(message.id); if (message.error) request.reject(new Error(JSON.stringify(message.error))); else request.resolve(message.result) }
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails)
    if (message.method === 'Browser.downloadWillBegin') downloads.set(message.params.guid, { name: message.params.suggestedFilename, state: 'started' })
    if (message.method === 'Browser.downloadProgress') { const file = downloads.get(message.params.guid); if (file) file.state = message.params.state }
  })
  await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }))
  await send('Page.enable'); await send('Runtime.enable')
  await send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: runDirectory, eventsEnabled: true })
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: `http://127.0.0.1:${server.address().port}/#laboratorio` })
  await wait(`document.querySelectorAll('.lab-details-button').length === 6`)
  assert.equal(await evaluate(`!!document.querySelector('.lab-urm')`), false)
  assert.equal(await evaluate(`document.querySelector('.lab-export-button').disabled`), true)
  for (const theme of ['light', 'dark']) {
    await evaluate(`document.documentElement.dataset.theme = '${theme}'`)
    await click('Probar con un ejemplo')
    for (const button of await evaluate(`Array.from(document.querySelectorAll('.lab-results .lab-export-button'), button => { const style = getComputedStyle(button); return { color: style.color, background: style.backgroundColor, disabled: button.disabled } })`)) {
      assert.equal(button.disabled, false); assert.ok(contrast(button.color, button.background) >= 4.5)
    }
    await evaluate(`document.querySelector('.lab-details-button').focus(); document.querySelector('.lab-details-button').click()`)
    await wait(`!!document.querySelector('[role="dialog"]')`)
    assert.equal(await evaluate(`document.activeElement === document.querySelector('[role="dialog"]')`), true)
    await key('Tab', 9)
    assert.equal(await evaluate(`document.activeElement.getAttribute('aria-label')`), 'Cerrar detalles de estrategia')
    await key('Tab', 9, true)
    assert.equal(await evaluate(`document.activeElement.textContent`), 'Descargar PNG')
    await screenshot(`details-desktop-${theme}`)
    await key('Escape', 27)
    await wait(`!document.querySelector('[role="dialog"]')`)
    assert.equal(await evaluate(`document.activeElement.classList.contains('lab-details-button')`), true)
    checks.push(`Contraste >=4.5:1, teclado y foco: ${theme}`)
    // Limpiar el ejemplo evita la confirmación intencional al volver a cargarlo.
    await send('Page.reload')
    await wait(`document.querySelectorAll('.lab-details-button').length === 6`)
  }
  for (let index = 0; index < 6; index++) {
    await evaluate(`document.querySelectorAll('.lab-details-button')[${index}].click()`)
    await wait(`!!document.querySelector('[role="dialog"]')`)
    assert.equal(await evaluate(`document.querySelectorAll('.lab-detail-section').length`), 13)
    await download('Descargar PDF', 'pdf')
    await download('Descargar PNG', 'png')
    await key('Escape', 27)
    checks.push(`PDF con texto seleccionable y PNG real de estrategia ${index + 1}`)
  }
  await click('Probar con un ejemplo')
  await download('Descargar resultados en PDF', 'pdf')
  await download('Descargar resultados en PNG', 'png')
  await click('Guardar escenario')
  await evaluate(`(() => { const input = document.querySelector('#scenario-plannedUnits'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '60'); input.dispatchEvent(new Event('input', {bubbles:true})) })()`)
  await wait(`document.querySelector('#lab-diagnosis-title').textContent.includes('supera el presupuesto')`)
  assert.ok((await evaluate(`document.querySelector('.lab-diagnosis-explanation').textContent`)).includes('$2,000.00'))
  await click('Guardar escenario')
  await download('Descargar comparación en PDF', 'pdf')
  await download('Descargar comparación en PNG', 'png')
  checks.push('Escenarios con déficit, exportaciones individuales y comparativas reales')
  for (const theme of ['light', 'dark']) {
    await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
    await evaluate(`document.documentElement.dataset.theme = '${theme}'; document.querySelector('.lab-details-button').click()`)
    await wait(`!!document.querySelector('[role="dialog"]')`)
    const dimensions = await evaluate(`(() => {const dialog = document.querySelector('.lab-details'), body = document.querySelector('.lab-details-body'), rect = dialog.getBoundingClientRect(); return {left:rect.left, right:rect.right, top:rect.top, bottom:rect.bottom, width:innerWidth, height:innerHeight, scroll:body.scrollHeight > body.clientHeight, overflow:body.scrollWidth > body.clientWidth} })()`)
    assert.ok(dimensions.left >= 0 && dimensions.right <= dimensions.width && dimensions.bottom <= dimensions.height && dimensions.top >= 0)
    assert.equal(dimensions.scroll, true); assert.equal(dimensions.overflow, false)
    await screenshot(`details-mobile-${theme}`)
    await key('Escape', 27)
    checks.push(`Modal móvil 390px, desplazamiento interno sin desbordamiento: ${theme}`)
  }
  assert.equal(errors.length, 0, JSON.stringify(errors))
  writeFileSync(join(cache, 'results.json'), JSON.stringify({ status: 'passed', checks, downloads: [...downloads.values()], runDirectory }, null, 2))
  console.log(`${checks.length} verificaciones de navegador correctas; ${downloads.size} descargas verificadas. Evidencia: ${cache}`)
} catch (error) {
  try { await screenshot('failure') } catch { /* Conservar el error original. */ }
  writeFileSync(join(cache, 'results.json'), JSON.stringify({ status: 'failed', error: String(error), errors, checks }, null, 2))
  throw error
} finally {
  if (socket?.readyState === WebSocket.OPEN) { try { await send('Browser.close') } catch { /* Chrome puede cerrar antes de responder. */ } socket.close() }
  browser.kill(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve))
}
