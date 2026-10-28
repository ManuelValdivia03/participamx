
import { SectionCard } from '../../components/SectionCard'
import { StatisticalHelp } from '../../components/StatisticalHelp'
import { profileCatalog } from '../profiles/profilePresentation'

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

export function Methodology() {
  return (
    <section className="methodology" aria-label="Cómo se calculan e interpretan los indicadores">
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
          <p className="method-plain"><strong>Participación observada:</strong> mide qué proporción de los registros con condición de voto especificada registró participación.</p>
          <p className="method-formula"><strong>En porcentaje:</strong> <code>SV / (SV + NV) × 100</code></p>
          <p>SV son registros con participación; NV son registros sin participación. Se suman los conteos antes de dividir. Los registros no especificados quedan fuera de esta tasa.</p>

          <p>
            <strong>Lista nominal (LN):</strong> conteo nominal reportado en los cuadernillos disponibles, no un conteo validado de personas únicas. <strong>Participación nominal:</strong>{' '}
            SV dividido entre LN.
            Es un indicador diferente y no debe confundirse
            con la participación observada.
          </p>
          <p className="method-formula"><code>SV / LN × 100</code></p>

          <p>
            <strong>Registros con condición de voto no especificada (NS):</strong>{' '}
            registros sin especificación de la condición
            de voto. No se consideran automáticamente
            abstenciones.
          </p>
        </SectionCard>

        <SectionCard title="Referencia de comparación">
          <p>
            Es el valor nacional utilizado para comparar grupos equivalentes según la metodología. Cada segmento se compara con una referencia
            nacional correspondiente a la misma elección,
            grupo de edad y sexo.
          </p>

          <p>
            <strong>pp = puntos porcentuales.</strong> La diferencia es una resta entre porcentajes, no un cambio porcentual. Un valor positivo indica participación
            superior a la referencia; uno negativo,
            participación inferior.
          </p>
          <p>Por ejemplo: 60 % menos 55 % son 5 pp. Se calcula con los valores originales y sólo después se redondea. La referencia no es una participación esperada ni un promedio histórico.</p>

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
          {profileCatalog.map(rule => (
            <li key={rule.id}><strong>{rule.name}</strong><p>{rule.ageBand.replace('-', '–')} años · Participación {rule.direction} de la referencia nacional comparable.</p></li>
          ))}
        </ul>
        <p>Mayor y menor indican si la participación del segmento estuvo por encima o por debajo de una referencia nacional comparable por edad y sexo. No representan necesariamente la participación máxima o mínima del país.</p>

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
            Tipo de sección electoral: U = Urbana, R = Rural y M = Mixta. La clasificación urbana, rural o mixta
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
      <StatisticalHelp />
    </section>
  )
}
