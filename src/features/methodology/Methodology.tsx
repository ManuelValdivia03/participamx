
import { SectionCard } from '../../components/SectionCard'

const steps = [
  {
    title: 'Preparación de los datos',
    description:
      'Se procesaron los conteos censales de participación ciudadana del INE correspondientes a las elecciones de 2009, 2012, 2015, 2018, 2021 y 2024. Se revisaron registros, valores faltantes, claves y unidades.',
  },
  {
    title: 'Exploración de patrones',
    description:
      'Se evaluaron alternativas de agrupamiento y diferentes patrones demográficos y territoriales. Los resultados no demostraron la existencia de seis grupos naturales estables de ciudadanía.',
  },
  {
    title: 'Construcción de perfiles',
    description:
      'Se definieron seis perfiles descriptivos mediante reglas explícitas, combinando tres grupos de edad con participación superior o inferior a una referencia comparable.',
  },
  {
    title: 'Validación e integración',
    description:
      'Se realizaron controles de integridad y conciliación de resultados. Los indicadores se publicaron en archivos JSON para su consulta por año electoral y territorio.',
  },
]

const rules = [
  '18–34 años · por encima de sus pares',
  '18–34 años · por debajo de sus pares',
  '35–59 años · por encima de sus pares',
  '35–59 años · por debajo de sus pares',
  '60–100 años · por encima de sus pares',
  '60–100 años · por debajo de sus pares',
]

export function Methodology() {
  return (
    <>
      <p className="page-intro">
        Conoce cómo se prepararon los datos electorales,
        cómo se definieron los perfiles y qué límites
        deben considerarse al interpretar los resultados.
      </p>

      <SectionCard
        title="De los datos a los perfiles"
        subtitle="Metodología aplicada · Elecciones 2009–2024"
      >
        <ol className="method-steps">
          {steps.map((step, index) => (
            <li key={step.title}>
              <span className="step-number">
                0{index + 1}
              </span>

              <div>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </div>

              <span className="step-state">
                Realizado
              </span>
            </li>
          ))}
        </ol>
      </SectionCard>

      <div className="two-columns feature-notes">
        <SectionCard title="¿Cómo se calcula la participación?">
          <p>
            <strong>Participación observada:</strong>{' '}
            registros que sí votaron (SV) divididos entre
            los registros con condición de voto especificada
            (SV + NV).
          </p>

          <p>
            <strong>Participación nominal:</strong>{' '}
            SV dividido entre la lista nominal (LN).
            Es un indicador diferente y no debe confundirse
            con la participación observada.
          </p>

          <p>
            <strong>NS:</strong>{' '}
            registros sin especificación de la condición
            de voto. No se consideran automáticamente
            abstenciones.
          </p>
        </SectionCard>

        <SectionCard title="Referencia de comparación">
          <p>
            Cada segmento se compara con una referencia
            nacional correspondiente a la misma elección,
            grupo de edad y sexo.
          </p>

          <p>
            La diferencia se expresa en puntos porcentuales
            (pp). Un valor positivo indica participación
            superior a la referencia; uno negativo,
            participación inferior.
          </p>

          <p>
            Las diferencias de hasta ±2 puntos porcentuales
            requieren cautela porque están cerca de la
            frontera convencional de clasificación.
          </p>
        </SectionCard>
      </div>

      <SectionCard
        title="Los seis perfiles ciudadanos"
        subtitle="Candidatos descriptivos definidos por reglas"
      >
        <p>
          Los perfiles no son categorías naturales
          descubiertas automáticamente ni representan
          personas identificadas de manera individual.
        </p>

        <p>
          La unidad de clasificación es el segmento
          formado por municipio, grupo de edad y sexo.
          Se exige un soporte mínimo de 100 registros
          en lista nominal, 100 registros con condición
          de voto especificada y cinco filas fuente.
        </p>

        <ul>
          {rules.map(rule => (
            <li key={rule}>{rule}</li>
          ))}
        </ul>

        <p>
          Un municipio puede contener segmentos de varios
          perfiles. Por ello, sus cantidades no deben
          sumarse como si los municipios pertenecieran
          exclusivamente a una sola categoría.
        </p>
      </SectionCard>

      <div className="two-columns feature-notes">
        <SectionCard title="Cobertura y datos no disponibles">
          <p>
            Los resultados conservan los valores faltantes
            como información no disponible; no se
            sustituyen por cero.
          </p>

          <p>
            Los perfiles principales utilizan edades
            de 18 a 100 años. Otros registros, cuando
            existen, permanecen en los recursos
            complementarios y totales correspondientes.
          </p>

          <p>
            La información registrada puede cambiar
            entre elecciones. No se deben interpretar
            categorías ausentes como cantidades iguales a cero.
          </p>
        </SectionCard>

        <SectionCard title="Interpretación responsable">
          <p>
            Se utilizan datos agregados, no historiales
            de voto de personas identificables.
            Los resultados no permiten determinar
            motivaciones, preferencias políticas
            ni conductas individuales.
          </p>

          <p>
            Las elecciones presidenciales e intermedias
            tienen contextos diferentes. Las variaciones
            observadas no demuestran por sí mismas
            relaciones causales.
          </p>

          <p>
            La clasificación urbana, rural o mixta
            corresponde a secciones electorales y no
            identifica necesariamente el tipo de
            residencia de cada persona.
          </p>
        </SectionCard>
      </div>

      <SectionCard
        title="Alcance territorial e histórico"
        subtitle="Precauciones para interpretar el mapa"
      >
        <p>
          Los indicadores se consultan utilizando el año
          electoral y las claves territoriales
          correspondientes.
        </p>

        <p>
          La cartografía municipal presentada utiliza
          geometrías de 2024. Las correspondencias entre
          claves INE e INEGI requieren verificación
          y no garantizan que los límites territoriales
          sean idénticos en distintas elecciones.
        </p>

        <p>
          No se realizan comparaciones históricas
          municipales automáticas. Los indicadores
          nacionales y estatales pueden consultarse
          por elección.
        </p>

        <p>
          Los indicadores municipales publicados en la
          versión actual de ParticipaMX corresponden a 2024.
          Los recursos que no estén integrados se mostrarán
          como no disponibles.
        </p>
      </SectionCard>

      <SectionCard title="Fuente de información">
        <p>
          Instituto Nacional Electoral (INE).
          Conteos Censales de Participación Ciudadana,
          elecciones de 2009, 2012, 2015, 2018,
          2021 y 2024.
        </p>

        <p>
          Procesamiento y construcción de perfiles:
          equipo de análisis de ParticipaMX.
          Contrato de datos utilizado: versión 2.0.0.
        </p>

        <p>
          Los seis perfiles se presentan como candidatos
          descriptivos por reglas. No deben interpretarse
          como resultados de un modelo de clustering
          definitivo.
        </p>
      </SectionCard>
    </>
  )
}
