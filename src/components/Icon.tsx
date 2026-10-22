export type IconName = 'dashboard' | 'mapa' | 'perfiles' | 'metodologia' | 'info' | 'location' | 'ballot'

const paths: Record<IconName, React.ReactNode> = {
  dashboard: <><path d="M3 16h18M5 13V8h3v5m4 0V3h3v10m4 0V6h2v7M5 21h14" /></>,
  mapa: <><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Zm6-3v15m6-12v15" /><circle cx="15" cy="10" r="2" /></>,
  perfiles: <><circle cx="9" cy="7" r="3" /><path d="M3 21v-4a6 6 0 0 1 12 0v4M16 4a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 5v2M6 17h6" /></>,
  metodologia: <><path d="M5 3h12l3 3v15H5V3Zm9 0v5h6M8 12h8M8 16h5" /><path d="m2 6 3-3" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v1" /></>,
  location: <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
  ballot: <><path d="m9 3 10 4-4 9-10-4 4-9Zm-6 12-1 6h20l-2-6M8 17h8m-6-8 2 2 3-3" /></>,
}

export function Icon({ name, className = '' }: { name: IconName; className?: string }) {
  return <svg className={`icon ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" strokeLinejoin="miter" aria-hidden="true">{paths[name]}</svg>
}
