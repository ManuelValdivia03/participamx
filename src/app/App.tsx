const modules = [
  'Dashboard de participación electoral',
  'Mapa de estados y municipios',
  'Clusters y perfiles ciudadanos',
  'Comparación de perfiles',
  'Estrategias cívicas',
  'Metodología y reportes',
]

export default function App() {
  return (
    <main>
      <header>
        <p className="eyebrow">Hackathon INE</p>
        <h1>ParticipaMX</h1>
        <p>Perfiles ciudadanos de participación</p>
      </header>
      <section aria-labelledby="status-title">
        <h2 id="status-title">Comenzamos a construir</h2>
        <p>Base del frontend lista. Los módulos se implementarán con los resultados del equipo de análisis.</p>
        <ul>{modules.map(module => <li key={module}>{module}</li>)}</ul>
        <p className="notice">Todavía no se muestran datos ni resultados electorales.</p>
      </section>
    </main>
  )
}
