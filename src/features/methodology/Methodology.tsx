import { SectionCard } from '../../components/SectionCard'

const steps = [
  ['Preparar los datos', 'Revisar las fuentes electorales del INE del periodo 2009–2024, limpiar inconsistencias y documentar valores faltantes.'],
  ['Explorar y transformar', 'Seleccionar variables, normalizar las características numéricas y explorar posibles agrupaciones.'],
  ['Encontrar patrones', 'Evaluar alternativas de clustering y la cantidad de grupos mediante dendrogramas y la técnica del codo (SSE).'],
  ['Interpretar y compartir', 'Validar los resultados, describir entre 4 y 6 perfiles según el análisis e integrar gráficas, fichas y estrategias en la plataforma.'],
]
export function Methodology() {
  return <><p className="page-intro">Una ruta transparente para convertir datos electorales en una lectura comprensible de la participación ciudadana.</p><SectionCard title="De los datos a los perfiles" subtitle="Proceso previsto · sujeto a la validación del equipo de análisis"><ol className="method-steps">{steps.map(([title, description], i) => <li key={title}><span className="step-number">0{i + 1}</span><div><h3>{title}</h3><p>{description}</p></div><span className="step-state">Previsto</span></li>)}</ol></SectionCard><div className="two-columns feature-notes"><SectionCard title="Fuentes y trazabilidad"><p>Al integrar los resultados se publicarán las fuentes, variables, cobertura y fecha de actualización de cada conjunto de datos.</p></SectionCard><SectionCard title="Lectura responsable"><p>Los perfiles describen patrones agregados de los datos analizados. Su interpretación deberá acompañarse de las limitaciones y métricas del modelo.</p></SectionCard></div></>
}
