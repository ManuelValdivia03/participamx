import type { ReactNode } from 'react'

export function SectionCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return <section className="card"><header className="card-heading"><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</header>{children}</section>
}
