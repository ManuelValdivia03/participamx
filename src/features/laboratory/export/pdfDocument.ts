export type PdfPage = { commands: string[] }

const encoder = new TextEncoder()

export function createPdfDocument(pages: PdfPage[]) {
  if (pages.length === 0) throw new Error('No hay páginas para generar el PDF.')
  const objects: Uint8Array[] = []
  const add = (value: string | Uint8Array) => {
    const bytes = typeof value === 'string' ? encoder.encode(value) : value
    objects.push(bytes)
    return objects.length
  }
  const pagesId = add('')
  const fontId = add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
  const boldId = add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>')
  const pageIds = pages.map(page => {
    const streamBytes = encoder.encode(page.commands.join('\n'))
    const contentId = add(joinBytes(encoder.encode(`<< /Length ${streamBytes.length} >>\nstream\n`), streamBytes, encoder.encode('\nendstream')))
    return add(`<< /Type /Page /Parent ${pagesId} 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 ${fontId} 0 R /F2 ${boldId} 0 R >> >> /Contents ${contentId} 0 R >>`)
  })
  objects[pagesId - 1] = encoder.encode(`<< /Type /Pages /Kids [${pageIds.map(id => `${id} 0 R`).join(' ')}] /Count ${pageIds.length} >>`)
  const catalogId = add(`<< /Type /Catalog /Pages ${pagesId} 0 R >>`)
  const header = encoder.encode('%PDF-1.4\n')
  const offsets = [0]
  let length = header.length
  const body: Uint8Array[] = [header]
  objects.forEach((object, index) => {
    const prefix = encoder.encode(`${index + 1} 0 obj\n`)
    const suffix = encoder.encode('\nendobj\n')
    offsets.push(length)
    body.push(prefix, object, suffix)
    length += prefix.length + object.length + suffix.length
  })
  const xref = length
  const trailer = encoder.encode(`xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, '0')} 00000 n `).join('\n')}\ntrailer\n<< /Size ${objects.length + 1} /Root ${catalogId} 0 R >>\nstartxref\n${xref}\n%%EOF`)
  const allBytes = joinBytes(...body, trailer)
  return new Blob([allBytes.buffer as ArrayBuffer], { type: 'application/pdf' })
}

function joinBytes(...parts: Uint8Array[]) {
  const result = new Uint8Array(parts.reduce((total, part) => total + part.length, 0))
  let offset = 0
  parts.forEach(part => { result.set(part, offset); offset += part.length })
  return result
}

export function validatePdf(blob: Blob) {
  return blob.type === 'application/pdf' && blob.size > 500
}

export async function extractPdfText(blob: Blob) {
  const bytes = new Uint8Array(await blob.arrayBuffer())
  const content = new TextDecoder('latin1').decode(bytes)
  return [...content.matchAll(/<([0-9a-f]+)> Tj/g)].map(match => decodeWinAnsi(match[1])).join(' ')
}

function decodeWinAnsi(hex: string) {
  const map: Record<number, string> = { 0x80: '€', 0x95: '•', 0x96: '–', 0x97: '—', 0xa1: '¡', 0xbf: '¿', 0xd1: 'Ñ', 0xd3: 'Ó', 0xdc: 'Ü', 0xe1: 'á', 0xe9: 'é', 0xed: 'í', 0xf1: 'ñ', 0xf3: 'ó', 0xfa: 'ú', 0xfc: 'ü' }
  return (hex.match(/../g) ?? []).map(pair => map[parseInt(pair, 16)] ?? String.fromCharCode(parseInt(pair, 16))).join('')
}
