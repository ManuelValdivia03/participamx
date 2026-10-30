export function safeFileName(value: string) {
  const normalized = value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '')
  return normalized.slice(0, 70) || 'sin_nombre'
}

export function downloadPdf(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.append(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 3000)
}

export async function downloadPngs(images: Promise<Blob[]>, name: string) {
  const blobs = await images
  blobs.forEach((blob, index) => downloadPdf(blob, `${name}${blobs.length > 1 ? `_parte_${index + 1}_de_${blobs.length}` : ''}.png`))
}
