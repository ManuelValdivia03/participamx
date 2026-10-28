import { useState } from 'react'
import type { CitizenProfile, ProfileDataset } from './types'

export function ProfileExportButtons({profile,dataset}:{profile:CitizenProfile;dataset:ProfileDataset}) {
  const [busy,setBusy]=useState<string|null>(null),[message,setMessage]=useState('')
  const available=dataset.enrichment?.year===dataset.year&&!!profile.enriched&&dataset.enrichmentStatus==='ready'
  async function download(format:'pdf'|'png') {
    if(!available||busy)return
    setBusy(format);setMessage(`Preparando ${format.toUpperCase()}…`)
    try{const {downloadProfileExport}=await import('./profileExport');await downloadProfileExport(profile,dataset,format);setMessage(`Archivo ${format.toUpperCase()} preparado para descargar.`)}catch{setMessage('No se pudo preparar la descarga. Vuelve a intentarlo.')}finally{setBusy(null)}
  }
  return <div className="pp-export-actions" aria-label="Descargar ficha nacional">{available&&<p>Ficha nacional · {dataset.year}</p>}<div>{(['pdf','png'] as const).map(format=><button type="button" key={format} className="pp-button pp-button-outline" data-export-format={format} disabled={!available||!!busy} onClick={()=>download(format)}>Descargar {format.toUpperCase()}</button>)}</div>{!available&&<p>La descarga requiere el desglose nacional verificado de {dataset.year}. Reintenta la caracterización desde el catálogo.</p>}<p role="status" aria-live="polite">{message}</p></div>
}
