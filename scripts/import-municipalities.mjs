import { readFileSync, writeFileSync, mkdirSync, rmSync, existsSync } from 'node:fs'
const service = 'https://lcidsig.inegi.org.mx/server/rest/services/Hosted/%C3%81reas_geoestad%C3%ADsticas_municipales_2024/FeatureServer/0'
const directory = 'public/data/municipalities'
mkdirSync(directory, { recursive: true })
const local = process.argv.includes('--local')
const readJson = path => JSON.parse(readFileSync(path, 'utf8').replace(/^\uFEFF/, ''))
const getJson = async url => { const response = await fetch(url); if (!response.ok) throw new Error(`HTTP ${response.status}`); const data = await response.json(); if (data.error) throw new Error(JSON.stringify(data.error)); return data }
const metadata = local ? readJson(`${directory}/source-layer.json`) : await getJson(`${service}?f=pjson`)
const expected = local ? 2478 : (await getJson(`${service}/query?where=1%3D1&returnCountOnly=true&f=json`)).count
const features = []
for (let offset = 0; offset < expected; offset += 1500) {
  const params = new URLSearchParams({ where: '1=1', outFields: 'cvegeo,cve_ent,cve_mun,nomgeo', outSR: '4326', maxAllowableOffset: '0.001', geometryPrecision: '5', orderByFields: 'cvegeo', resultOffset: String(offset), resultRecordCount: '1500', f: 'geojson' })
  const data = local ? readJson(`${directory}/source-${offset}.json`) : await getJson(`${service}/query?${params}`)
  if (!Array.isArray(data.features)) throw new Error('Missing features')
  features.push(...data.features)
}
if (features.length !== expected) throw new Error('Incomplete municipal download')
const seen = new Set()
const groups = new Map()
for (const feature of features) {
  const p = feature.properties
  if (!/^\d{5}$/.test(p.cvegeo) || p.cvegeo !== p.cve_ent + p.cve_mun || seen.has(p.cvegeo) || !p.nomgeo || !feature.geometry) throw new Error(`Invalid municipality ${p.cvegeo}`)
  seen.add(p.cvegeo)
  const state = groups.get(p.cve_ent) ?? []
  state.push({ type: 'Feature', properties: { code: p.cvegeo, stateCode: p.cve_ent, municipalityCode: p.cve_mun, name: p.nomgeo }, geometry: feature.geometry })
  groups.set(p.cve_ent, state)
}
if (groups.size !== 32) throw new Error('Expected 32 state groups')
const counts = {}
for (const [code, items] of groups) {
  counts[code] = items.length
  writeFileSync(`${directory}/${code}.json`, JSON.stringify({ type: 'FeatureCollection', features: items }) + '\n')
}
writeFileSync(`${directory}/metadata.json`, JSON.stringify({ source: 'INEGI. Áreas geoestadísticas municipales 2024', service, retrievedOn: new Date().toISOString().slice(0,10), featureCount: features.length, counts, terms: 'https://www.inegi.org.mx/inegi/terminos.html', transformations: 'WGS84; generalización del servicio a 0.001 grados; coordenadas con cinco decimales; agrupación por cve_ent y selección de atributos.', layer: { name: metadata.name, description: metadata.description, copyrightText: metadata.copyrightText, extent: metadata.extent, editingInfo: metadata.editingInfo } }, null, 2) + '\n')
if (local) for (const file of ['source-0.json','source-1500.json','source-layer.json']) if (existsSync(`${directory}/${file}`)) rmSync(`${directory}/${file}`)
console.log(`${features.length} municipalities / ${groups.size} states exported.`)
