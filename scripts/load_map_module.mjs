// Compila sólo módulos puros locales para las pruebas Node, sin escribir el código fuente.
import { readFileSync } from 'node:fs'
import ts from 'typescript'
const cache = new Map()
function moduleUrl(url) {
  if (cache.has(url.href)) return cache.get(url.href)
  const source = ts.transpileModule(readFileSync(url, 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText
  const text = source.replace(/from (['"])(\.\.?\/[^'"]+)\1/g, (_, quote, relative) => {
    const dependency = new URL(relative.endsWith('.ts') ? relative : `${relative}.ts`, url)
    return `from ${quote}${moduleUrl(dependency)}${quote}`
  })
  const result = `data:text/javascript;base64,${Buffer.from(text).toString('base64')}`
  cache.set(url.href, result)
  return result
}
export function loadMapModule(name) { return import(moduleUrl(new URL(`../src/features/map/${name}.ts`, import.meta.url))) }
