# Perfiles de participación electoral · integración V1, V2 y V2.1

La revisión vigente de hallazgos, lenguaje público y descargas de dos/tres perfiles está en [Lectura y exportación de comparaciones](profile_reading_and_comparison_exports.md). Se conservan los datos y definiciones de esta integración; las advertencias repetidas se agrupan en desplegables y los hallazgos se obtienen mediante reglas verificables.

La escala compartida de tipografía y las convenciones actualizadas de explicación de indicadores se documentan en [Tipografía y lectura de estadísticas](typography_and_statistics.md). Mantienen las cifras y la definición de estas fichas.

La integración de elecciones, contexto estatal y descargas nacionales PDF/PNG se documenta en [Selectores y exportaciones](selectors_and_profile_exports.md). La ampliación actual a las seis elecciones, con matriz de cobertura, conciliaciones y comparación persistente, está en [Perfiles históricos](historical_profile_enrichment.md).

## Decisión y alcance

Se mantienen exactamente los seis IDs, pertenencias, tasas y conteos V1. Son categorías por reglas de banda de edad y signo frente a la referencia nacional de esa banda/sexo/elección. La investigación no justificó sustituirlas por cuatro a seis clases multivariables nuevas. Sexo y tipo de sección electoral caracterizan las fichas; no se afirma que las cuatro dimensiones hayan definido simultáneamente los perfiles. V2.1 aparece como un hallazgo separado, nunca como una séptima ficha.

La caracterización ampliada está disponible para **las seis elecciones**. Las de 2009–2021 reutilizan los cruces Parquet multianuales conciliados con su propio V1; no reciben cifras, superlativos o interacciones de 2024. El hallazgo transversal V2.1 sigue exclusivamente en 2024. Si falla el contrato o la carga ampliada, se conserva V1, se oculta el complemento y se ofrece reintento sin perder la selección. No se asignan estrategias institucionales ni se modifican Atlas o Laboratorio.

## Seis nombres acordados

| ID conservado | Nombre de consumo | Contexto de 2024 |
| --- | --- | --- |
| young_favorable | Jóvenes con mayor participación | +7.69 pp frente a pares comparables. |
| young_unfavorable | Jóvenes con menor participación | −6.83 pp frente a pares comparables. |
| adult_favorable | Adultos con mayor participación | +6.51 pp frente a pares comparables. |
| adult_unfavorable | Adultos con menor participación | −5.96 pp frente a pares comparables. |
| older_favorable | Personas mayores con mayor participación | +5.78 pp frente a pares comparables. |
| older_unfavorable | Personas mayores con menor participación | −7.34 pp frente a pares comparables. |

Los nombres se aplican a tarjetas, detalles y comparador sin cambiar los IDs. «Mayor/menor» indica posición frente a la referencia de la misma elección, edad y sexo; no un juicio sobre las personas ni máximos/mínimos absolutos entre las seis fichas o en el país. Los mismos nombres se usan en años anteriores con sus propias cifras y referencias. El contrato de consumo marca `namesStatus` y `nameStatus` como `agreed`; no cambia pertenencias ni resultados.

El catálogo explica una sola vez: «Los perfiles comparan la participación de grupos de edad con una referencia nacional de grupos similares. Al abrir una ficha puedes conocer sus diferencias por sexo y tipo de sección electoral». Cada tarjeta conserva sólo su criterio breve y un hallazgo respaldado, sin repetir el párrafo completo.

## Fuentes y transformación

`scripts/build_profile_enrichment.py` genera **únicamente** `public/data/profiles/enriched-2024.json`. No entrena, reprocesa CSV ni modifica los JSON analíticos. Copia indicadores ya validados y adapta nombres de campos/estructura al consumo. Su modo `--check` comprueba regeneración determinista. `scripts/build_historical_profile_enrichment.py` añade cinco payloads históricos sin sobrescribir 2024: hereda las pertenencias V1 y agrega sus hijos U/R/M ya procesados. Las fuentes, cobertura y reglas de reproducción se detallan en el documento histórico.

Fuentes exactas y filtros:

- V1: `data/processed/participamx_multiyear/elections/2024/profiles.json`, `data[profile_id=ID]`, contrastado con la copia pública que ya usa React.
- V2: `analysis/profile_v2/results/reference/all_observations.parquet`, mediante los agregados editoriales ya conciliados.
- Editorial: `analysis/profile_v2/editorial/results/experimental_profile_names_2024.json`, `profiles[id]`, campos `statistics`, `sex_statistics`, `section_statistics`, `joint_age_sex_section`, descripciones e interpretaciones. Los cruces incluyen todos los hijos de cada padre V1; no se recortan sólo a los hijos elegibles para recalcular una ficha distinta.
- V2.1: `analysis/profile_v2/patterns/results/candidates/experimental_patterns.json`, sólo el patrón validado `interaction_18-34_R_U`; `statistics.equal_municipality_pp`, `nominal_pp`, `municipalities`, `municipality_same_sign_fraction`, `annual_LN_fraction`, LN y D.
- Heterogeneidad global: `analysis/profile_v2/patterns/results/sign_reversals/summary.json`. Las cantidades por perfil proceden de los campos editoriales `eligible_flip_cells`, `eligible_cells`, `eligible_flip_fraction`, `eligible_flip_LN` y `eligible_flip_nominal_fraction`.

Se comprueban `_SUCCESS`, estado y hashes de los artefactos reutilizados. La copia de consumo contiene procedencia y SHA-256 por fuente. **En producción sólo se solicitan datos bajo `public/data/`**; las rutas `analysis/` se presentan como procedencia textual, nunca se consultan desde el navegador.

## Tasas, referencias y bases

- Participación observada = SV/(SV+NV); NULL si D=SV+NV=0. NS permanece separado de NV.
- Referencia nacional = suma SV/suma D antes del filtro de soporte, para la misma elección/banda/sexo.
- Referencia de ficha o tipo = suma(D del segmento × referencia propia)/suma D. Ajusta mezcla de sexo, no edad exacta ni contexto causal.
- Diferencia = 100×(participación−referencia), en pp. Las tasas y composiciones del contrato son proporciones [0,1]; los campos `deltaPp` y del contraste son pp. La UI convierte proporciones a porcentaje sólo para mostrar.
- Composición nominal = LN del sexo/tipo dividido por LN de la ficha. No mide participación ni cantidad de secciones. Los cruces conjuntos sexo×tipo conservan sus propios denominadores.
- Soporte exploratorio: LN≥100, D≥100 y filas fuente≥5. Filas fuente no son personas ni secciones independientes. NS/LN≥10 % y proximidad ≤2 pp son cautelas descriptivas, no significación estadística o filtros automáticos.
- Las celdas agregadas pueden tener soporte aunque algunos hijos no lo tengan. La ficha muestra ambos niveles; no presenta todos los hijos como entrenables. Los municipios se superponen y no se suman entre fichas.
- U/R/M identifica tipo de sección electoral, no localidad ni residencia individual. Las paletas clara/oscura son las mismas del Atlas: U `#69388f`/`#b398ca`, R `#a95536`/`#d5a784`, M `#267565`/`#95c5b7`.

`ProfileValueStatus` distingue `defined`, `missing`, `undefined`, `low_support` y `unavailable_category`. Un valor válido cero se muestra como cero; NULL conserva su ausencia. SEXO=2 está conservado en 2024 con LN=105 pero sin soporte para las fichas H/M; no se distribuye entre esos sexos. Su ausencia histórica se explica como categoría no disponible, nunca como cero población. Las edades 101+ permanecen en las fuentes complementarias, no dentro de estas fichas 18–100.

## Hallazgo transversal y heterogeneidad

Para 18–34 años, la diferencia entre la brecha mujeres−hombres rural y urbana es **3.8193 pp**, promediando contrastes dentro de los mismos municipios con igual peso municipal. Con peso del LN del bloque es **5.2988 pp**. Son estimandos distintos. No se restan cuatro tasas nacionales para representar el contraste municipal: esa resta agregada daría otro resultado (8.7327 pp en el estudio).

La visualización destaca **Contraste municipal: 3.82 pp** y **Contraste ponderado: 5.30 pp**. Explica que en el primero cada municipio pesa igual y en el segundo pesan más los municipios con mayor lista nominal del bloque. Un diagrama de puntos los sitúa sobre el mismo eje, de 0 a 8 pp; son marcas de lectura, no una meta ni un máximo natural. Se retira la barra de progreso aparente. No se inventan tasas base para producir el 3.82. La cobertura es 1,226 municipios con las cuatro celdas elegibles y LN=22,587,270, 22.9708 % del nominal anual reportado; D=20,975,575. El 75.8564 % se refiere a municipios con el mismo signo, no a personas. No prueba causalidad, homogeneidad, independencia de NS ni generalización a todos los municipios.

En el panorama global, 2,704 de 31,470 subsegmentos elegibles invierten signo respecto a su padre V1; sólo 562 tienen padre e hijo a más de 2 pp. Dentro de cada ficha se usan exclusivamente sus propios cambios (446, 468, 491, 468, 444 y 387, en el orden de nombres anterior) y su denominador elegible. No se asignan 2,704 a cada perfil ni se confunde frecuencia de filas con fracción de LN. El detalle conserva NULL, falta de soporte y variación interna.

## Componentes y navegación

- `RealProfilesPage.tsx`: mantiene selección global de año, carga abortable y reintento; integra el selector compartido de elecciones y el contexto estatal separado.
- `profilesAdapter.ts`: integra V1 con el complemento de la elección activa y verifica consistencia antes de mostrarlo; no usa 2024 como sustituto histórico.
- `types.ts` y `profileEnrichment.ts`: contrato, validación, unidades y adaptación pura; se conservan IDs y se rechazan datos de otro año, duplicados y denominadores incoherentes.
- `Profiles.tsx`: conserva la demostración previa y deriva los datos reales a `EnrichedProfiles.tsx`.
- `EnrichedProfiles.tsx`: cuadrícula 3/2/1, tarjetas, selección de detalle, comparación y advertencias. `ProfileInteractionContext.tsx` conserva IDs, pestaña y medida entre años y cargas; restaura el foco al volver del detalle.
- `EnrichedProfileDetail.tsx`: encabezado de edad/año, tres KPI grandes y «¿Qué revelan los datos?» con tres hallazgos específicos antes de las gráficas. Conteos, soporte, reglas, cruces completos, heterogeneidad y territorio quedan en desplegables nativos accesibles.
- `profilePresentation.ts`: nombres acordados, edición pública de hallazgos, orden de categorías y frases de comparación de tasas; no cambia los datos.
- `ProfileVisuals.tsx`: barras, referencias, equivalentes textuales y ayuda de pp. No depende sólo del color.
- `TransversalFinding.tsx`: única interacción respaldada, separada de las seis fichas.
- `ProfileComparePanel.tsx`: nuevo comparador real junto al catálogo; estado vacío centrado y compacto, una selección con aviso, dos/tres con resultados directos. Vistas separadas Resumen/Sexo/Tipo de sección electoral y controles independientes de participación/composición. La selección se conserva al abrir/cerrar una ficha. Al añadir la segunda o tercera se enfoca el encabezado y se desplaza a él; «Añadir otro perfil» regresa al catálogo y una barra flotante permite volver a la comparación. Columnas desplazables con teclado en móvil sin desbordar la página. `ProfileComparison.tsx` conserva la demostración anterior.
- `src/styles/profiles-enriched.css`: estilos propios, responsive y claros/oscuros, sin cambiar CSS ni lógica del Atlas.

El detalle es una sección en flujo normal, no un diálogo: su título recibe foco; los botones nativos permiten teclado. Los indicadores tienen valores textuales, leyendas y estados; las gráficas no son la única forma de acceder a las cifras. Los metadatos técnicos están plegados para no saturar la lectura principal. La integración actual permite PDF/PNG nacionales de las seis elecciones, con plantilla independiente de la pantalla; véanse los documentos de selectores/exportaciones y ampliación histórica.

Los textos principales usan 16 px y los secundarios 14 px (rótulos pequeños 13 px). Se reduce espacio vacío en tarjetas y se reserva margen de desplazamiento para que los títulos no queden bajo la cabecera. V1/V2, denominadores, variación total, subsegmentos y cambios de signo se mantienen en el nivel ampliado.

Las tasas por sexo usan barras horizontales, mujeres en rosa y hombres en azul, tomando el nivel intermedio de las paletas del Atlas: `#bf6093`/`#5e92bb` en claro, `#d69fba`/`#9bbdd6` en oscuro. La brecha se calcula a partir de las tasas reales, no de composiciones ni del redondeo de las etiquetas, y sólo con dos tasas definidas y soporte disponible. Se indica su dirección sin causalidad. La composición nominal tiene un control separado. SEXO=2 continúa advertido sin inventar una barra comparable.

Tipo de sección electoral conserva **Urbana → Rural → Mixta** en barras, leyendas, selectores, tabla técnica y comparador; el orden visual se aplica a copias, sin reordenar las fuentes. Las tres tasas comparten escala 0–100 %, con diferencia descriptiva entre máximo y mínimo sólo cuando son comparables; el texto específico aclara los contrastes por sexo. La composición nominal se muestra aparte. Ni esa diferencia ni las tasas se interpretan como efecto causal o residencia individual.

## Comprobaciones realizadas

```powershell
.venv_pattern_algorithms/Scripts/python.exe -B scripts/build_profile_enrichment.py --check
npm.cmd run typecheck
node --experimental-strip-types --test scripts/profiles-enriched.test.mjs
npm.cmd run test:territorial
npm.cmd run build
node scripts/check-profiles-ui.mjs
```

Las 13 pruebas dirigidas comprueban IDs/nombres acordados, conteos y cruces, procedencia, estimandos V2.1, adaptación, rechazo de datos inválidos, cero frente a NULL, ausencias/soporte, orden U/R/M sin mutación, brecha por sexo, jerarquía de ficha, estados del comparador y ausencia de barra de progreso. Pasan también las 27 pruebas territoriales existentes. El test de Chrome usa `dist/`, un servidor local y un perfil temporal en `node_modules/.cache/profiles-ui/`: comprueba seis nombres, cifras de las seis fichas, selección U/R/M, vistas de sexo, apertura con Enter, título visible y foco de retorno, comparación de dos/tres perfiles con foco inmediato, vacío/primera selección/vaciado, temas, contraste ≥4.5:1 en textos comprobados, cuadrícula 3/2/1, desplazamiento local del comparador sin desbordar la página a 950/390 px, cambio a 2021, errores HTTP/contrato y reintento. Guarda capturas y `results.json` en esa caché, no como exportaciones de producto.

En el entorno gestionado, esbuild necesitó ejecutar compilación/pruebas fuera del sandbox por restricciones de lectura de directorios superiores; Chrome también requirió ejecución fuera del sandbox para responder por DevTools. No se instalaron dependencias nuevas. Se protege por hashes la investigación previa, documentación analítica, datos publicados existentes y archivos del Atlas; no se hace commit, push o merge.

En esta iteración se verificaron **1,435 archivos protegidos sin cambios**. La comparación recursiva del archivo de consumo contra su copia previa confirma igualdad completa salvo los campos de nombre y su estado acordado: todos los conteos, tasas, denominadores, referencias, límites y procedencia permanecen idénticos. Los textos públicos y el orden visual se resuelven en componentes/helpers, sin reescribir los resultados de investigación.

## Pendientes

Pruebas de comprensión con usuarios y lectores de pantalla, además de las verificaciones realizadas de teclado/contraste; revisión editorial/electoral de la presentación histórica. Los nombres ya son los acordados, no una propuesta pendiente de selección. Las descargas nacionales históricas están disponibles y conciliadas; las fichas enriquecidas estatales siguen fuera de alcance. V2.1 no se extiende a otras elecciones. No se añaden estrategias. La integración visual no convierte estos perfiles en clases naturales ni aporta evidencia sobre causas o eficacia institucional.
