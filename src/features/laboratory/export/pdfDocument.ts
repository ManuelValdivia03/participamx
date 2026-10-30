export function validatePdf(blob: Blob) {
  return blob.type === 'application/pdf' && blob.size > 500
}

// Lectura del texto nativo emitido por jsPDF sin comprimir, usada en verificaciones.
export async function extractPdfText(blob: Blob) {
  const content = new TextDecoder('windows-1252').decode(await blob.arrayBuffer())
  return [...content.matchAll(/\(((?:\\[\s\S]|[^\\)])*)\)\s*Tj/g)].map(match => match[1].replace(/\\([0-7]{1,3}|[\s\S])/g, (_, escaped: string) => /^[0-7]+$/.test(escaped) ? String.fromCharCode(parseInt(escaped, 8)) : ({ n: '\n', r: '\r', t: '\t' }[escaped] ?? escaped))).join(' ')
}
