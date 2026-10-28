import { useState } from 'react'
import type { CitizenProfile, ProfileDataset } from './types'

export function ComparisonExportButtons({profiles,dataset}:{profiles:CitizenProfile[];dataset?:ProfileDataset}) {
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('')
  const available=profiles.length>=2&&profiles.length<=3&&dataset?.enrichmentStatus==='ready'&&dataset.enrichment?.year===dataset.year&&profiles.every(p=>!!p.enriched)
  async function download(format:'pdf'|'png') {
    if(!available||busy||!dataset)return
    setBusy(true);setMessage(`Preparando comparación ${format.toUpperCase()}…`)
    try{const {downloadComparisonExport}=await import('./comparisonExport');await downloadComparisonExport(profiles,dataset,format);setMessage(`Comparación ${format.toUpperCase()} preparada para descargar.`)}catch{setMessage('No se pudo preparar la comparación. Vuelve a intentarlo.')}finally{setBusy(false)}
  }
  return <div className="pp-comparison-exports" aria-label="Descargar comparación completa"><div>{(['pdf','png'] as const).map(format=><button key={format} type="button" className="pp-button pp-button-outline" data-comparison-export={format} disabled={!available||busy} onClick={()=>download(format)}>Descargar comparación {format.toUpperCase()}</button>)}</div><small>{profiles.length<2?'Elige dos o tres perfiles para descargar.':!available?'Se necesita la caracterización verificada de esta elección.':'Incluye todas las vistas, además de la pestaña seleccionada.'}</small><p role="status" aria-live="polite">{message}</p></div>
}
