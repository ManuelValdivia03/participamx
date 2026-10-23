import { formatProfileMetric, profileMetrics, type CitizenProfile, type ProfileDataset } from './types'

export function ProfileComparison({ profiles, dataset, onRemove }: { profiles: CitizenProfile[]; dataset: ProfileDataset; onRemove: (id: string) => void }) {
  return <section className="profile-comparison" aria-labelledby="comparison-title"><div className="comparison-heading"><div><p className="eyebrow">LECTURA EN PARALELO</p><h2 id="comparison-title">Comparar perfiles</h2></div><span>{profiles.length} de 3 seleccionados</span></div>
    {profiles.length < 2 ? <div className="comparison-empty"><h3>Elige al menos dos perfiles</h3><p>Usa “Añadir a comparación” en las fichas. Puedes comparar hasta tres a la vez.</p>{profiles.map(profile => <button className="profile-button secondary" key={profile.id} onClick={() => onRemove(profile.id)}>Quitar {profile.name}</button>)}</div> : <>
      <p className="comparison-context">{dataset.mode === 'demo' ? 'Comparación de datos ficticios' : 'Resultados entregados por el equipo de análisis'} · {dataset.year}. Los perfiles se muestran sin orden de clasificación.</p>
      <div className="comparison-scroll" role="region" aria-label="Tabla comparativa de perfiles; desplázate horizontalmente en pantallas pequeñas" tabIndex={0}><table><caption>Indicadores y contexto de los perfiles {dataset.mode === 'demo' && '(ejemplos ficticios)'}</caption><thead><tr><th scope="col">Indicador / contexto</th>{profiles.map(profile => <th scope="col" key={profile.id}><span>{profile.name}</span><button onClick={() => onRemove(profile.id)} aria-label={`Quitar ${profile.name} de la comparación`}>Quitar</button></th>)}</tr></thead><tbody>
        {profileMetrics.map(metric => <tr key={metric.key}><th scope="row">{metric.label}<small>{metric.description}</small></th>{profiles.map(profile => <td key={profile.id}>{formatProfileMetric(profile[metric.key], metric.suffix)}</td>)}</tr>)}
        <tr><th scope="row">Características</th>{profiles.map(profile => <td key={profile.id}><ul>{profile.characteristics.map(item => <li key={item}>{item}</li>)}</ul>{!profile.characteristics.length && 'Pendientes de entrega'}</td>)}</tr>
        <tr><th scope="row">{dataset.mode === 'demo' ? 'Acciones ilustrativas' : 'Estrategias cívicas'}</th>{profiles.map(profile => <td key={profile.id}><ul>{profile.strategies.map(item => <li key={item}>{item}</li>)}</ul>{!profile.strategies.length && 'Pendientes de entrega'}</td>)}</tr>
        <tr><th scope="row">Limitaciones</th>{profiles.map(profile => <td key={profile.id}><ul>{profile.limitations.map(item => <li key={item}>{item}</li>)}</ul></td>)}</tr>
      </tbody></table></div><p className="profile-source">{dataset.participationDefinition}</p>
    </>}
  </section>
}
