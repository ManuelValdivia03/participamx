# Explorador Territorial 2.0 · entrega para revisión

## Entrega actual · cuarta categoría visible y predominio nominal

**«Tipo de sección electoral» es la cuarta categoría principal de «Colorear mapa por»**, junto a Participación, Sexo y Edad. Se elimina el acceso «Más indicadores». Conserva iconos y estados activos; la cuadrícula usa cuatro columnas cuando el contenedor dispone de al menos 720 px y dos columnas en espacios menores. La etiqueta completa se envuelve sin recortarse. Cambiar categoría sólo cambia la capa: conserva elección, entidad y municipio.

Al abrirla se selecciona **Composición nominal → Predominante**. Esta modalidad ofrece Predominante / Urbana / Rural / Mixta; **Participación observada** ofrece Urbana / Rural / Mixta. Una explicación visible bajo las opciones distingue composición LN/LN de participación SV/(SV+NV). Las seis capas cuantitativas existentes conservan fórmulas, paletas, cuantiles, rangos, rankings, cifras y advertencias.

La vista **Predominante** compara los conteos LN_U/R/M del territorio, equivalentes a sus proporciones con denominador común. Usa tres colores fijos: Urbana morado, Rural terracota, Mixta verde azulado. Es categórica: no calcula cuantiles, no ordena las categorías y no ofrece un ranking de predominancia. Predominante no exige superar 50 % del nominal. Un empate exacto conserva todos los tipos líderes mediante una trama neutra y una etiqueta explícita; no se desempata por redondeo, orden o código. La tarjeta y la tabla muestran la proporción y LN de cada líder, sin sumar sus porcentajes como si fueran uno.

Se respetan ausencia de archivo/clave, correspondencia pendiente, base nominal nula y soporte reducido, con estados y neutros propios. Sólo se colorea cuando el total y cada tipo líder satisfacen los criterios exploratorios existentes LN≥100, SV+NV≥100 y filas fuente≥5. NS alto en total/líderes permanece como advertencia y no altera el máximo. No se identifica residencia individual, localidad, nivel socioeconómico ni causa electoral. La guía de cinco pasos incorpora la cuarta categoría y explica los colores categóricos cuando esta vista está activa.

Se reutilizan los servicios y JSON U/R/M existentes, **sin volver a generar datos ni modificar fórmulas, criterios o el algoritmo de cuantiles**. Se añade `SectionDominanceLegend.tsx`; se ajustan controles, presentación de valores, rellenos SVG y reglas de cuadrícula en los módulos del Atlas, junto con la descripción de la guía y una prueba de predominio en `scripts/section-statistics.test.mjs`. `sectionStatistics.ts` incorpora la clasificación pura sobre agregados disponibles; no se modifica el servicio de carga, los perfiles ni el Laboratorio.

**Validación actual:** pasan `npm.cmd run typecheck`, `npm.cmd run build` y las cuatro pruebas específicas de `section-statistics.test.mjs`. El nuevo caso cubre máximos sin mayoría absoluta, empates de dos/tres tipos, diferencias que redondearían igual, colores fijos sin escala, falta de información, base cero, soporte y NS. Las otras pruebas verifican integridad de los JSON existentes y conciliación de sus conteos. No se ejecutó la suite extensa. La compilación conserva el aviso cartográfico (aproximadamente 1,858 KB / 528 KB gzip).

La revisión dirigida en Chrome verificó cuatro botones visibles a 1920 px y disposición 2×2 a 1440/390 px; siete opciones U/R/M con clics sobre controles visibles; valores, rellenos y leyendas contra los agregados de 2024; ausencia de rampa y cortes en Predominante; selección municipal de Aguascalientes conservada al alternar las cuatro categorías; claro/oscuro, tarjeta categórica, guía y móvil sin desbordamiento ni etiquetas cortadas. En México 2024 predominan U en 30 entidades y R en dos; M conserva su leyenda con cero entidades predominantes, sin inventar un caso. Los empates se verificaron con casos sintéticos porque no aparecieron en esa vista nacional. Evidencia local ignorada: `node_modules/.cache/section-category-review/review.json` y capturas de controles, mapa, leyenda y móvil. Quedan pendientes las regresiones extensas, tecnologías de apoyo y dispositivos físicos ya enumerados más abajo. No hubo commits, push o merges.

## Antecedente · incorporación de tipo de sección electoral U/R/M

Se incorpora el **tipo de sección electoral** al Atlas sin reemplazar Participación / Sexo / Edad ni sus fórmulas o cuantiles. U = Urbana, R = Rural, M = Mixta. La clasificación describe secciones del marco electoral: **no identifica residencia individual, localidad, nivel socioeconómico ni causas de participación o abstención**. Se mantienen los cambios locales anteriores en `feat/explorador-territorial-v2`; no se crean commits, push, merges o PR.

### Auditoría y disponibilidad real

Antes de incorporar los cálculos se revisaron los esquemas reales y scripts existentes. `cluster_features/reference/exact_age_2024.parquet` y los JSON demográficos del Atlas no ofrecen el cruce TIPOSEC. Los campos `LN_U/R/M` y `section_ln_share_U/R/M` de los escenarios contextuales de 2024 describen segmentos específicos; no acreditan por sí mismos disponibilidad en otros años o ámbitos.

La fuente reutilizada es **`data/processed/descriptive/municipality_section_type/table.parquet`**, con 34,206 agregados de las seis elecciones. Contiene TIPOSEC, LN, SV, NV, NS, filas fuente y las dos métricas de SEXO=2. No hay nulos ni categorías fuera de U/R/M. Se concilian siete conteos aditivos por municipio contra `descriptive/municipality`, y por tipo/año contra `descriptive/section_type_year`; los cinco conteos del Atlas coinciden además con todos sus archivos municipales, estatales y nacionales. Los JSON previos `participamx_multiyear/elections/YEAR/section_statistics.json` ya ofrecen el marginal nacional y también se contrastan. Los diccionarios conservados definen el tipo de sección en el año correspondiente, con U/R/M explícito en 2024.

| Elección | México | Entidades con U/R/M | Municipios con desglose | Combinaciones municipio–tipo observadas | Tipos no observados dentro de municipios conciliados | Presentes con SV+NV=0 | Presentes con tasa definida y soporte reducido |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2009 | Disponible | 32, los tres tipos en cada entidad | 2,458 | 5,678 | 1,696 | 26 | 11 |
| 2012 | Disponible | 32, los tres tipos en cada entidad | 2,455 | 5,655 | 1,710 | 6 | 13 |
| 2015 | Disponible | 32, los tres tipos en cada entidad | 2,458 | 5,687 | 1,687 | 94 | 11 |
| 2018 | Disponible | 32, los tres tipos en cada entidad | 2,463 | 5,705 | 1,684 | 60 | 11 |
| 2021 | Disponible | 32, los tres tipos en cada entidad | 2,468 | 5,727 | 1,677 | 50 | 7 |
| 2024 | Disponible | 32, los tres tipos en cada entidad | 2,477 | 5,754 | 1,677 | 55 | 5 |

Hay conteos SV/NV/NS por tipo en todos estos ámbitos, por lo que fue viable implementar también las tasas. Las ausencias de un tipo municipal **no son archivos faltantes**: las celdas presentes concilian con el total completo. Una categoría sin registros puede tener LN=0 en esa partición exhaustiva; su tasa de participación sin base permanece no definida. Los 14,779 municipios–elección conservan la cobertura nominal completa del Atlas, todas las edades (incluidas 101+) y todas las categorías de sexo registradas. Esto no garantiza soporte de cada tipo ni correspondencia cartográfica: las uniones históricas pendientes siguen sin colorearse.

En 2024 se conserva LN total=98,330,348: Urbana=68,291,361 (**69.45 %**), Rural=17,216,522 (**17.51 %**), Mixta=12,822,465 (**13.04 %**). Las participaciones por tipo son, respectivamente, **59.88 %, 60.11 % y 57.94 %**. Son cocientes de sumas, no promedios municipales ni inferencias de conducta individual. Hay 1,159 celdas municipio–tipo presentes con NS/LN≥10 % en 2024; esa alerta no elimina sus conteos.

### Tarjetas, capas e interpretación

La ficha de México, entidad o municipio incorpora **«Composición por tipo de sección electoral»** en Resumen: barra horizontal apilada, Urbana morado, Rural terracota y Mixta verde azulado; leyenda textual con porcentaje y LN, base total y explicación. El detalle desplegable muestra participación por tipo, SV, NV, SV+NV, NS, NS/LN y filas fuente. Las advertencias de soporte y NS siguen visibles fuera del detalle. Carga, error y clave sin desglose tienen estados propios; no se retienen cifras de otro año ni se sustituyen por cero.

**«Más indicadores» → «Tipo de sección electoral»** añade un acceso secundario sin rediseñar los tres botones principales. Permite elegir Composición nominal o Participación observada y después Urbana / Rural / Mixta: seis capas. Se reutilizan las paletas morada, terracota y turquesa, los cuantiles, rangos reales, tarjeta contextual, geometrías, buscador, selección y cámara actuales. El mapa no introduce clasificación ordinal U=1/R=2/M=3.

En «Ver rangos y metodología», la tabla U/R/M ofrece un **ranking del indicador seleccionado**, descendente por fracción exacta, con desempate por clave INE. Los valores sin soporte o sin tasa permanecen al final, sin posición. El ranking general inferior conserva su indicador de participación total, identificado por su título; no se presenta como un ranking U/R/M.

«Lo más destacado» incorpora **como máximo un hallazgo U/R/M**, sustituyendo el tercer hallazgo de base cuando existe un contraste no nulo de al menos 0.01 pp entre dos o más tipos con tasas y soporte. Describe la distancia máxima observada en ese territorio y elección, sin ajuste por edad/sexo ni atribución causal. El umbral evita comunicar diferencias redondeadas a cero y no es una prueba estadística. Si sólo dos tipos son comparables, lo explicita; una categoría ausente o sin soporte no participa en ese contraste. NS alto advierte cautela. Sin contraste elegible se conserva el hallazgo de base. Nunca se superan tres hallazgos totales. La guía conserva sus cinco pasos y menciona el nuevo acceso secundario.

### Fórmulas y criterios

- Composición: **LN del tipo / LN total territorial**, todas las edades y categorías registradas. No se utiliza número de secciones ni SV como denominador.
- Participación: **SV del tipo / (SV del tipo + NV del tipo)**; primero se suman los conteos. Denominador cero produce NULL/«No disponible», nunca participación cero. NS no se suma a NV.
- Cobertura no especificada: **NS del tipo / LN del tipo**; alerta desde 10 %. No mide causalidad, abstención ni representatividad.
- Soporte cartográfico: mismos criterios exploratorios LN≥100, SV+NV≥100 y filas fuente≥5 por tipo presente. Para un cero nominal de tipo no observado, sólo es comparable si la partición completa está conciliada y su total satisface el soporte; su tasa sin denominador sigue fuera de la escala. Los valores calculables con soporte reducido se muestran, usando el neutro y sin posición comparable. La barra de composición conserva las cantidades conocidas, incluso con advertencia.

Los cuantiles siguen siendo relativos al ámbito y elección, sin ponderación nominal de los cortes. No se alteró `thematicScale.ts`. La clasificación U/R/M y los límites pueden variar entre años: se habilita consulta dentro de cada elección, **no transiciones municipales ni efectos históricos atribuibles al tipo de sección**. Los diccionarios comparables no prueban continuidad territorial. Persisten las limitaciones de cuadernillos, NS, casillas especiales y voto exterior de la fuente original.

### Datos derivados, contratos y reproducción

Se crean **199 archivos nuevos** (aproximadamente 5.07 MB en conjunto) bajo `public/data/territorial/sections/`: seis `YEAR/index.json` (México y 32 entidades), 192 `YEAR/STATE.json` municipales y `manifest.json`. La carga nacional no descarga todos los municipios; se solicita sólo la entidad pertinente y se reutiliza caché por elección/ámbito. Las respuestas se validan antes de almacenar: versión, año, ámbito, claves únicas, categorías, enteros no negativos e identidades de conteos. Cancelación e invalidación por clave evitan mostrar datos de una selección anterior. Un error U/R/M no impide consultar las capas originales.

`sectionStatistics.ts` declara `SectionType`, `SectionCell`, `SectionProfile`, `SectionIndex` y `SectionMunicipalities`; el servicio homónimo permite reutilizar los conteos como contexto agregado en futuras investigaciones. Los archivos son **marginales territoriales**, no un cruce nuevo edad×sexo×tipo. No deben asignarse a segmentos multiplicando marginales o suponiendo independencia. Para caracterizar perfiles por edad/sexo habrá que reutilizar cruces validados como los escenarios contextuales de 2024 y revisar su soporte. No se crean perfiles ni se modifican reglas, estrategias, laboratorio o exportaciones.

El exportador `scripts/build_section_statistics.py` lee sólo Parquet descriptivos y JSON agregados. No lee CSV, ZIP ni los 54 millones de registros limpios. Audita antes de escribir, protege destinos distintos, compara lectura posterior y hashes de fuentes; los resultados analíticos previos permanecen intactos. `--check` no escribe y un destino ya idéntico se conserva. Requiere Pandas/PyArrow del entorno existente, sin nuevas dependencias.

```powershell
.venv_pattern_algorithms/Scripts/python.exe scripts/build_section_statistics.py --audit-only
.venv_pattern_algorithms/Scripts/python.exe scripts/build_section_statistics.py
.venv_pattern_algorithms/Scripts/python.exe scripts/build_section_statistics.py --check
node --experimental-strip-types --test scripts/section-statistics.test.mjs
npm.cmd run typecheck
npm.cmd run build
```

Archivos nuevos: exportador y prueba anteriores, `scripts/load_map_module.mjs` (carga de módulos puros para pruebas), `src/features/map/sectionStatistics.ts`, `useSectionStatistics.ts`, `SectionComposition.tsx`, `src/services/sectionStatistics.ts`, `src/styles/section-statistics.css` y los JSON nuevos. Se integran cambios locales en `thematicData.ts`, `useThematicMap.ts`, `ThematicMapControls.tsx`, `TerritoryMap.tsx`, `StateElectionSummary.tsx`, `MunicipalElectionSummary.tsx`, `AtlasContext.tsx`, `electoralInterpretation.ts` y la descripción del paso de indicadores de `AtlasGuide.tsx`. `package.json` incorpora la prueba específica a la futura suite territorial; se adaptan importaciones/expectativas de las pruebas anteriores sin ejecutarlas extensivamente.

### Validación de esta entrega y pendientes

Pasaron **TypeScript, compilación, tres pruebas específicas y el exportador en modo `--check`**. Las pruebas comprueban huellas de todos los JSON nuevos, 192 entidades, 14,779 municipios, conciliación, las seis fórmulas nuevas, ausencias, ceros, denominadores nulos, soporte, NS, contratos inválidos, ranking y máximo de hallazgos. Sigue la advertencia del fragmento cartográfico (aproximadamente 1,849 KB / 526 KB gzip).

La revisión básica dirigida en Chrome cubrió México 2024 (seis capas y cifras cartográficas), Aguascalientes estatal/municipal, cambio a 2009, Cuauhtémoc sin R/M, claro/oscuro, pantalla de 390 px, movimiento reducido, apertura/cierre de guía y fallo simulado de archivos U/R/M. No hubo excepciones JavaScript ni desbordamiento horizontal en el móvil revisado. La tabla extensa se desplaza dentro de su región. Se inspeccionaron capturas; el fallo de U/R/M muestra error y conserva disponible el mapa de participación total. Evidencia local ignorada: `node_modules/.cache/section-basic-review/review.json` y sus capturas nacionales, estatales, municipales, móviles y de fallo. Los intentos iniciales fallidos del guion fueron esperas durante desmontaje y una expectativa de formato decimal de cero; no se presentan como fallos de los datos ni de la interfaz.

**No se ejecutó la batería extensa.** Quedan pendientes regresiones completas de las seis elecciones, navegación/ranking/búsqueda/cámara y todas las fichas; cobertura cartográfica de casos extremos; lectores de pantalla, recorrido completo de teclado, contraste integral/simulaciones cromáticas, Safari/iOS y dispositivos físicos. También conviene evaluar deduplicación de solicitudes simultáneas y tamaños de transferencia antes de una optimización posterior. La interpretación o segmentación futura requiere revisión específica del cruce edad/sexo/tipo; la cobertura nominal alta no elimina las carencias por categoría. No se modificaron datos originales, resultados analíticos previos, cuantiles, módulo del Laboratorio ni perfiles actuales.

## Antecedente · contraste claro y exploración guiada

Se continúa sobre los cambios locales de `feat/explorador-territorial-v2`. Se conservan Participación / Sexo / Edad, subopciones, datos, fórmulas, cuantiles, navegación y ranking. **La validación de esta entrega es básica y dirigida**: TypeScript, compilación y cuatro recorridos acotados en Chrome. Las 23 pruebas y 33 comprobaciones extensivas documentadas como antecedentes más abajo no se repitieron.

### Cambios visuales y selección

- **Claro:** seis paletas de cinco niveles con primeros tonos más distinguibles del fondo frío `#f4f6fa`. Participación utiliza `#dcc5eb`, `#b893d4`, `#9263bb`, `#69388f`, `#421b65`. La tabla de paletas de este documento recoge los extremos actuales. Mapa y leyenda comparten variables CSS. Los colores oscuros y neutros anteriores se conservan.
- **Contorno:** doble trazo continuo, sin relleno ni eventos, dibujado al final. Los estados de contexto en la vista municipal no reciben puntero. En selección se evita que las reglas discontinuas generales de hover/foco compitan con el borde; el foco por teclado refuerza el halo hasta 13 px. Los territorios no seleccionados mantienen su indicador de foco.
- **Sonora:** la captura señalada no se reprodujo exactamente: la inspección inicial en reposo registró `stroke-dasharray: none`. Sí se identificaron reglas generales discontinuas aplicables al hover/foco de los caminos de estado. Se limitaron en selección/contexto y se comprobaron después Sonora y un municipio. No se corrigieron ni eliminaron islas o partes de geometrías compuestas.
- **Encuadre:** se ajusta la proporción visual del SVG al espacio disponible para reducir el espacio vacío; no se cambian proyección, geometrías, cálculo de cámara ni gestos. La ruta territorial queda en una fila encima del SVG para no cubrir Baja California.
- **Tarjeta:** permanece dentro del contenedor, debajo de la geometría también en escritorio, con dos columnas; en móvil usa una columna. Así conserva márgenes y tipografía sin cubrir territorios ni los controles de zoom. Su botón sigue abriendo la ficha electoral.

### Guía de cinco pasos y ayuda bajo demanda

El botón **«¿Cómo usar el Atlas?»** abre `AtlasGuide.tsx`: elección, búsqueda, indicador, leyenda y tarjeta/ficha. Una invitación discreta permite empezar u omitir; no se abre automáticamente el diálogo. El recorrido utiliza controles reales, resalta el destino, lo desplaza a la vista y ofrece progreso, Anterior, Siguiente, Omitir y Finalizar. Sin escala cuantitativa señala la leyenda neutral y adapta la explicación. Si falta un destino usa las alternativas disponibles y mantiene operativa la navegación.

Se usa un `dialog` nativo, foco en el título de cada paso y retorno al botón de origen al cerrar; Escape omite la guía. Se respeta movimiento reducido. El estado `completed`/`skipped` se guarda bajo `participamx-atlas-guide-v1` cuando está disponible `localStorage`, sin datos personales. Un fallo de almacenamiento no impide usarla y el botón permite reabrirla. Los atajos anteriores de «Cómo navegar» se reutilizan en el paso final y en la descripción accesible del mapa, evitando dos bloques visibles de instrucciones.

Las ayudas informativas de participación, no participación, LN, SV, NV y NS se abren mediante desplegables nativos. La tarjeta y la leyenda conservan los detalles de composición nominal/participantes, edad, cuantiles y soporte. Las advertencias críticas continúan visibles.

### Hallazgos del territorio

**«Lo más destacado» reemplaza la franja anterior de tres métricas**; no se añade otra copia de esa franja. La función pura `buildTerritoryHighlights` en `electoralInterpretation.ts` genera hasta tres observaciones desde los conteos existentes: participación en contexto o diferencia frente a México, condición no especificada y base conocida. La ficha conserva sus cifras exactas y su lectura detallada.

La referencia nacional suma los conteos estatales del índice de la misma elección y utiliza la función de tasa existente. La diferencia es descriptiva, sin ajuste demográfico; sólo se presenta con tasa y soporte suficientes. No se infieren cambios históricos, causas, preferencias ni necesidades individuales. Un denominador cero produce un estado informativo y no una tasa cero; soporte insuficiente produce cautela. NS sigue separado de NV. Al cambiar territorio/año se invalida el contexto anterior hasta recibir la base correspondiente.

Ejemplos del recorrido: México 2024 tiene base especificada **92,004,694** y NS/LN **6.43 %**; Xalapa 2024 muestra base **342,843** y diferencia nacional **+2.96 pp**. Ziracuaretiro muestra «Sin tasa disponible», sin diferencia nacional inventada. Son ejemplos verificados, no valores fijados en el componente.

### Archivos y comprobaciones actuales

Se añaden `src/features/map/AtlasGuide.tsx` y `src/styles/atlas-guide.css`. Se extiende `electoralInterpretation.ts` y se integran `AtlasContext.tsx`, `useThematicMap.ts`, `MapPage.tsx`, `TerritoryMap.tsx`, `ThematicMapControls.tsx`, `ElectionMetricCards.tsx` y `territorial-atlas.css`. Se conservan los otros cambios locales previos. `scripts/check-territorial-ui.mjs` adapta selectores y expectativas al nuevo contexto y ayuda; **la suite extensa no se ejecutó**.

Se ejecutaron `npm.cmd run typecheck` y `npm.cmd run build` correctamente. Persiste la advertencia del paquete cartográfico: aproximadamente **1,836 KB / 522 KB gzip** en el fragmento del mapa. `git diff --check` no detecta errores de espacios. La revisión dirigida en Chrome comprobó:

1. Los cinco pasos, destinos reales, progreso, Finalizar, persistencia de finalización, retorno de foco, reapertura y Escape; invitación sin diálogo automático.
2. Sonora, foco de selección municipal, tema oscuro y tarjeta fuera de la geometría; cambio directo Sonora → Veracruz y selección de Xalapa.
3. Hallazgos nacionales, referencia de la misma elección y protección ante denominador cero.
4. Pantalla de 390 px, movimiento reducido, guía con leyenda sin comparables, omisión y ausencia de desbordamiento horizontal en ese recorrido.

No se observaron excepciones JavaScript en estos recorridos. Evidencia local ignorada: `node_modules/.cache/atlas-final-review/final-review.json` y capturas `guide-step-1.png`, `guide-step-4.png`, `national-map-light.png`, `sonora-light.png`, `municipality-dark.png`, `highlights-xalapa.png`, `guide-mobile-no-comparable.png` y `mobile-neutral.png`. El guion temporal de revisión queda en caché; no es una nueva suite del producto.

**Pendientes:** repetir regresiones extensas de datos, búsqueda/ranking, seis elecciones, cámara/gestos, fichas y capas; revisar geometrías extremas y pantallas pequeñas/bajas adicionales; probar navegación Tab/Shift+Tab completa, lectores de pantalla, almacenamiento bloqueado, persistencia tras recarga, zoom de texto y contraste/simulaciones cromáticas de todas las paletas. También quedan teléfonos físicos y Safari/iOS. El uso de controles nativos y la revisión dirigida no certifican accesibilidad completa.

Para revisar: `npm.cmd run dev -- --host 127.0.0.1`, abrir `/#mapa`, iniciar la guía y recorrer los cinco pasos. Contrastar el mapa claro y oscuro, seleccionar Sonora/Hermosillo, cambiar a Veracruz/Xalapa, consultar la ficha y comprobar los hallazgos. En móvil revisar No binario y su leyenda sin comparables. No se modificaron datos, JSON, correspondencias, algoritmo de cuantiles, ranking, laboratorio, perfiles/exportaciones ni estilos globales. No se hicieron commits, push, merges ni PR.

## Antecedente · contraste oscuro, navegación y lectura

La iteración anterior se centró en contraste oscuro, navegación directa e interpretación. Los párrafos siguientes conservan su alcance y evidencia histórica; el encabezado de entrega actual indica los cambios y verificaciones más recientes.

- **Oscuro:** cinco tonos más luminosos en cada una de las seis paletas, fondo separado `#251d2d`–`#1b1521` y fronteras `#201728`. No cambian clases ni valores; mapa y leyenda comparten las mismas variables CSS. Los dos neutros mantienen sus colores y motivos.
- **Selección:** halo exterior de 9 px y borde interior de 3.5 px, constantes al acercar. Claro: halo `#fff9e9`, borde `#6d301c`; oscuro: halo `#181120`, borde `#ffe2a6`. Se dibujan después de todos los territorios, sin relleno ni eventos de puntero. Aparición de 160 ms, desactivada con movimiento reducido. Cursor y foco mantienen trazos discontinuos distintos de la selección sólida.
- **Cambiar estado:** botón compacto en las migas de pan; abre el buscador existente, enfoca el campo y muestra las 32 entidades. Se puede filtrar por nombre, recorrer con flechas y elegir con Enter. La entidad actual se identifica por texto y borde. «Buscar también municipios» devuelve el mismo campo al buscador general. No hay otro servicio ni catálogo. Elegir otra entidad limpia el municipio, conserva año/capa y actualiza geometría, ficha, contexto y ranking.
- **Lectura:** `electoralInterpretation.ts` genera textos desde los conteos/valores ya calculados. «¿Qué nos dicen estos datos?» aparece en Resumen; la tarjeta del mapa explica la capa consultada. Se distingue tasa observada, composición nominal y composición de participantes. Ante denominador cero, ausencia o soporte insuficiente se comunica el límite en lugar de interpretar un porcentaje comparable.
- **Texto:** se retira la repetición del título del Atlas, territorio/año en líneas cercanas y notas repetidas bajo los cuatro conteos. Las cifras exactas siguen visibles; fórmulas, definición nominal y base de la tasa siguen en los detalles. Alertas de NS y soporte permanecen visibles.

Ejemplos revisados: México 2024 explica aproximadamente **60 de cada 100 registros con condición de voto especificada** con participación y 40 sin ella; **6.43 %** del nominal es no especificado, sin convertirlo en abstención. Xalapa 2024 muestra aproximadamente **63/37** y **13.03 %** no especificado; la capa Mujeres entre participantes muestra **57.13 % de participaciones registradas**, no tasa de participación femenina. El redondeo sólo facilita la lectura, conserva el porcentaje original y no identifica personas.

### Archivos y validación del antecedente oscuro

Nuevo: `src/features/map/electoralInterpretation.ts`. Modificados: `ElectionMetricCards.tsx`, `ThematicMapControls.tsx`, `DemographicPanel.tsx`, `TerritorySearch.tsx`, `MapPage.tsx`, `TerritoryMap.tsx` (todos en `src/features/map/`), `src/styles/territorial-atlas.css`, `scripts/check-territorial-ui.mjs` y este documento. El guion extenso sólo adapta su comprobación del contorno seleccionado a los nuevos colores; **no se ejecutó**. No se alteraron conteos, perfiles, datos generados, correspondencias, ordenamiento, búsqueda general ni algoritmo de cuantiles.

Se ejecutaron `npm.cmd run typecheck` y `npm.cmd run build`. La compilación conserva la advertencia de tamaño cartográfico (aproximadamente 1.828 MB / 520 KB gzip). La revisión básica usó Chrome para navegar y capturar México oscuro, Oaxaca municipal → Veracruz desde «Cambiar estado», Xalapa, cambio 2024→2018 y móvil de 390 px con movimiento reducido. Se inspeccionaron las capturas; no se observaron excepciones JavaScript en ese recorrido. Se verificó que el contorno no recibe clics ni introduce relleno, y que no hay desbordamiento horizontal en el móvil revisado. Es un recorrido limitado, no una regresión completa ni una certificación de accesibilidad.

Un cálculo puntual de luminancia de los colores CSS frente al extremo más claro del nuevo fondo oscuro dio un contraste mínimo aproximado de **3.16:1** en violeta, 3.62 en cálido, 3.51 en rosa, 3.91 en azul, 3.96 en turquesa y 4.30 en ámbar. Describe separación relleno/fondo, no contraste entre todos los niveles ni legibilidad de todo el sitio. Faltan repetir simulaciones cromáticas y la batería extensa con las nuevas tonalidades.

Evidencia local ignorada por Git: `node_modules/.cache/atlas-basic-review/`, con `review.json`, `national-dark.png`, `national-map-dark.png`, `change-state-search.png`, `state-dark.png`, `municipality-dark.png`, `municipality-panel-dark.png` y `municipality-mobile.png`. El guion temporal utilizado para guiar la revisión está en la caché; no forma parte del producto ni sustituye la suite. Los marcadores/capturas de la suite extensa anterior no representan una validación de este cambio.

Para revisión humana: iniciar Vite, abrir `/#mapa`, activar oscuro y contrastar una capa baja/alta con la leyenda. Seleccionar un municipio, usar «Cambiar estado», escribir otra entidad y elegir con teclado. Comprobar que se conserva año/capa y desaparece el municipio anterior. Revisar las lecturas de Resumen y las capas nominal/participantes, luego abrir los detalles para sus bases. Pendientes: regresiones completas de mapas/datos/navegación, casos límite de lectura, contraste integral, lectores de pantalla, teléfonos físicos y Safari/iOS. No se hicieron commits, push, merges ni PR.

## Refinamiento anterior · funciones conservadas

La entrega anterior incorporó diez capas, cuantiles permanentes, leyenda compacta y neutros para datos no comparables. Los 193 archivos municipales, 199 resúmenes, índice de búsqueda y siete archivos de capas mantienen sus contratos y cifras. Esta revisión no regenera JSON ni modifica datos analíticos; el archivo local extraño sin seguimiento permanece intacto.

Esta revisión trabaja en la rama encontrada al inicio: **`feat/explorador-territorial-v2`**. El rediseño de navegación anterior se desarrolló en `feat/mapa-fichas-demograficas`; se reutiliza su implementación en la rama actual.

### Organización temática y leyenda heredadas

| Etapa | Implementación |
| --- | --- |
| 1 · Controles | Se retira la fila de escalas sin reemplazarla; se conserva la organización temática completa. Cuantiles permanentes, sin estado ni rama de escala absoluta sin uso. |
| 2 · Leyenda | Indicador, año, ámbito, colores de menor a mayor y explicación contextual. «Ver rangos y metodología» conserva límites calculados, conteos, denominadores y criterios; tabla territorial secundaria. |
| 3 · No binario y ausencias | Dos neutros sin rayados: información ausente frente a información con soporte insuficiente. Mensajes de disponibilidad reales según año/ámbito; cifras y motivos consultables. |
| 4 · Tarjetas | Nombre destacado, año, cifra, base, estado de soporte e iconos. «Ver ficha electoral» y cálculo desplegable. Barra proporcional sólo para valores comparables. |
| 5 · Pulido y validación | Tipografía legible, menos filas y texto permanente, mismos colores cuantitativos, temas, foco y movimiento reducido. Conciliación, regresiones y revisión visual. |

La franja de contexto original mostraba participación observada, LN total y NS/LN del territorio **seleccionado**. En la entrega actual se sustituye por «Lo más destacado», conservando el ámbito seleccionado y la invalidación al cambiar territorio/año. La ficha lateral conserva su indicador general aunque se consulte una capa de composición.

La tarjeta del mapa muestra nombre/año, capa, porcentaje y base. Con soporte, la barra representa la proporción real sobre 0–100, no el cuantil. Un valor con soporte insuficiente conserva su cifra con texto neutro y advertencia, sin barra cuantitativa; una ausencia conserva su motivo, nunca cero. El estado de soporte y NS alto permanecen visibles; «Cómo se calcula» contiene universo y conteos. «Ver ficha electoral» selecciona el territorio consultado y lleva el foco al panel. En móvil la tarjeta queda debajo del SVG. Cursor/foco se diferencian de selección: borde señalado discontinuo frente a contorno sólido cálido con halo neutro. El contorno nunca sustituye el relleno temático.

La leyenda visible muestra el indicador, año y ámbito nacional/estatal, una progresión de colores con etiquetas Menor/Mayor porcentaje y una explicación de la métrica. Una advertencia breve mantiene visible que los colores son relativos al año y ámbito. Los intervalos y frecuencias quedan en «Ver rangos y metodología». Allí se muestran los límites calculados con su precisión numérica y extremos inclusivos/exclusivos, el denominador, NS y soporte. «Consultar valores por territorio» abre una tabla independiente, que no se monta al desplegar sólo la metodología. Las advertencias de soporte y correspondencias pendientes permanecen fuera de los desplegables.

### Paletas estadísticas

| Capa | Paleta | Claro: menor → mayor | Oscuro: menor → mayor |
| --- | --- | --- | --- |
| Participación, 35–59 y No binario cuando hubiera soporte | Violeta | `#dcc5eb` → `#421b65` | `#7b658d` → `#f0dffd` |
| No participación | Durazno/terracota | `#efc5ad` → `#78331f` | `#996d58` → `#ffe8ce` |
| Mujeres: nominal o participantes | Rosa/magenta | `#e9b6cf` → `#6d204b` | `#98667f` → `#ffe2f0` |
| Hombres: nominal o participantes | Azul | `#b6d1e8` → `#1f466f` | `#5e809e` → `#e4f3ff` |
| 18–34 | Turquesa | `#9fd4c8` → `#115347` | `#51877e` → `#e2f8ef` |
| 60–100 | Ámbar | `#e6cf8c` → `#6d4e16` | `#97814d` → `#fff0c9` |

Cada paleta tiene cinco niveles discretos definidos localmente en `territorial-atlas.css`. En oscuro la progresión asciende en luminosidad; conserva el orden estadístico y cambia los colores, no los valores. Rosa/azul son identificadores visuales solicitados, sin significado demográfico adicional. Leyenda numérica, títulos, consulta y tabla evitan depender sólo del matiz. La entrega anterior incluyó simulaciones cromáticas; falta repetirlas para estas tonalidades oscuras. No constituyen certificación clínica ni auditoría exhaustiva de accesibilidad.

### Archivos de esta iteración

- `src/features/map/thematicScale.ts`: cuantiles permanentes; se retiran el tipo, parámetro y rama de escala alternativa sin uso. El algoritmo de cortes no cambia.
- `src/features/map/thematicData.ts`: explicaciones por indicador y rellenos neutros; las diez fórmulas y criterios se conservan.
- `src/features/map/ThematicMapControls.tsx`: misma organización temática, leyenda progresiva, mensajes de disponibilidad y tarjeta refinada.
- `src/features/map/TerritoryMap.tsx`: retirada del estado del selector y patrones SVG, sin cambiar cámara, navegación ni correspondencias.
- `src/styles/territorial-atlas.css`: neutros, tipografía, leyenda y tarjeta; paletas cuantitativas intactas.
- `scripts/thematic-scale.test.mjs`, `scripts/territorial-layers.test.mjs`, `scripts/check-territorial-ui.mjs`: regresiones adaptadas; esta documentación completa los nueve archivos de la revisión.

Los archivos de fases anteriores que ya estaban modificados se conservan. La configuración de datos, cartografía, correspondencias y estilos globales no se modifica en esta iteración.

## Funciones conservadas e integradas

Se revisó `git status` antes de modificar archivos: estaban pendientes los cambios locales de las fases 1–3 y el archivo extraño sin seguimiento. Se continuó sobre ellos, sin restablecerlos ni incorporarlos a un commit. No se modificaron datos analíticos, JSON de perfiles/estrategias, cartografía, correspondencias, reglas de ranking o estilos globales.

| Fase | Estado | Resultado |
| --- | --- | --- |
| 4.1 · Interfaz | Implementada | Tres botones permanentes Por sexo / Por edad / Edad y sexo, con iconos, nombre y estado accesible. Acción principal «Ver ficha electoral», foco visible y ancho completo en móvil. |
| 4.2 · Participación | Implementada | Participación ciudadana y No participación, sobre los totales completos de estados y municipios del año. |
| 4.3 · Sexo | Implementada con límites de soporte | Composición nominal y composición de participantes de Mujeres/Hombres, con universos separados; No binario nominal sólo habilitado cuando la categoría está registrada. Las cifras escasas mantienen advertencia y tono neutro. |
| 4.4 · Edad | Implementada | Proporciones nominales de 18–34, 35–59 y 60–100, sobre el nominal total. 101+ se conserva en la base y fuera de los tres numeradores. |
| 4.5 · Leyenda e interacción | Implementada | Cuantiles permanentes, progresión menor/mayor y rangos desplegables, dos neutros con etiquetas para ausencia/soporte insuficiente, contorno cálido, consulta y tabla accesible. |
| 4.6 · Integración | Validada | Búsqueda, ranking, ficha, año, capas, temas, teclado, cámara, gestos, nulos y correspondencias pendientes. Se mantienen las limitaciones de pruebas físicas y tecnologías de apoyo. |

### Capas, fórmulas y denominadores

Los cálculos son proporciones en [0,1]; la interfaz muestra porcentajes. Primero se suman conteos, después se divide. Las celdas `segments` y `complementary` son disjuntas y concilian con el total territorial: se reutilizan todas, no sólo segmentos con perfiles o soporte. Las etiquetas Hombres, Mujeres y No binario se contrastan en las seis fuentes procesadas `sex_statistics.json`, campo `sex_label`; la categoría No binario aparece en 2024 y no se fabrica históricamente.

| Capa | Numerador | Denominador |
| --- | --- | --- |
| Participación ciudadana | SV total | SV+NV total |
| No participación | NV total | SV+NV total |
| Mujeres / Hombres / No binario | Suma LN de la categoría, todas las edades | LN total del territorio, todas las edades y categorías registradas |
| Mujeres / Hombres entre participantes | Suma SV de la categoría, todas las edades | SV total del territorio, todas las edades y categorías registradas |
| 18–34 / 35–59 / 60–100 | Suma LN del intervalo, todos los sexos registrados | LN total del territorio, todas las edades y categorías registradas |

NS no entra como NV ni SV. La composición nominal no es participación por categoría ni población censal. **Mujeres/Hombres entre participantes no es la tasa dentro de cada sexo**: usa SV categoría/SV total, no SV categoría/(SV+NV de categoría). El total SV incluye 101+ y todas las categorías registradas, incluido No binario en 2024. Las cifras describen participación registrada en el universo de cuadernillos, no personas únicas seguidas entre años ni toda participación posible fuera de la cobertura de la fuente. Si SV total es cero, el porcentaje no está definido. No se presume que H/M sumen 100 % cuando existen otras categorías. **El denominador de las capas de edad incluye 101+**; por eso las tres proporciones no tienen que sumar 100 %. No se reinterpreta la distribución de participantes de la ficha, que conserva su universo previo. Todas las fuentes reutilizadas concilian; una combinación ausente no se fuerza a cero.

Para colorear se conserva el soporte exploratorio existente: LN≥100, SV+NV≥100 y filas fuente≥5, sobre el total para participación y sobre la categoría agregada para composición. Aplicarlo a composición es una precaución conservadora de captura, no una necesidad algebraica de LN/LN ni una certificación estadística. Un porcentaje calculable con soporte reducido se guarda y se muestra, pero usa un neutro fuera de la escala comparable. NS/LN≥10 % se advierte y no excluye por sí solo si el resto del soporte alcanza los criterios. Las filas fuente son celdas, no personas independientes.

### Escala, consulta y disponibilidad

**Cuantiles permanentes:** ordenar las proporciones finitas con estado `defined` de las 32 entidades, o de todas las geometrías municipales con unión validada del estado seleccionado. Cada territorio pesa uno; LN no pondera los cortes. Con más de cinco valores distintos, los cortes son las observaciones de rango `ceil(i×n/5)`, i=1…4 (inversa de la distribución empírica). Se deduplican cortes y se descartan los iguales al máximo. Con hasta cinco valores distintos se conserva una clase por valor. No se dividen empates ni se crean clases vacías. El primer intervalo incluye ambos límites; los siguientes son abiertos por abajo y cerrados por arriba. La metodología muestra «>» para ese extremo abierto. Un único valor usa el tono medio y una etiqueta que no sugiere variación; ningún comparable produce una leyenda sin colores cuantitativos, con explicación explícita. Con dos a cuatro clases se distribuyen entre los niveles extremos de la paleta.

El alcance estadístico no es el rectángulo de zoom: acercar o desplazar no recalibra cortes. Seleccionar otro estado, año o capa sí puede hacerlo. **Colores relativos iguales entre elecciones o alcances no significan porcentajes iguales.** Los cuantiles hacen visibles diferencias pequeñas sin modificarlas; amplitud de intervalo y porcentaje real deben leerse para no exagerar su importancia. Los rangos desplegados conservan la precisión numérica de los límites calculados, que no expresa incertidumbre estadística. Los porcentajes territoriales siguen redondeados para lectura, conservando los conteos y la precisión original.

Se eliminó por completo el selector «Contraste territorial / Escala absoluta» y su alternativa fija, sin añadir controles sustitutos. Los botones temáticos y Lista nominal / Participantes mantienen su orden, acciones, estados y accesibilidad. La advertencia de comparación entre años/ámbitos queda visible en la leyenda; los detalles amplían su explicación. No se modifican porcentajes para producir contraste. La cartografía 2024 no certifica continuidad municipal histórica.

**Sin información:** gris lavanda `#eeeaf1` (oscuro `#342d3e`). **Información con soporte insuficiente:** neutro `#c7c2ce` (oscuro `#5b5067`). Se retiraron los patrones SVG de diagonales/cuadrículas en todas las capas. Los límites neutrales usan `#9b8fa7` / `#a396b3` para que las divisiones territoriales sigan legibles. Leyenda, iconos, atributos accesibles y tabla distinguen ambas situaciones; la diferencia de tono no es cuantitativa. Ninguna significa cero ni entra en cuantiles. El cero observado con denominador positivo conserva su color cuantitativo cuando tiene soporte. Falta de correspondencia, combinación ausente, categoría no registrada y denominador cero mantienen motivos distintos. El contorno cálido sólido indica selección sin reemplazar el relleno. Movimiento reducido elimina transiciones.

La tarjeta contextual presenta nombre, año, indicador, porcentaje, numerador/base, estado de soporte y universo. Se activa con cursor, foco o selección táctil; se puede cerrar con su botón y con Escape desde el mapa. Al salir del mapa vuelve al territorio seleccionado. La tabla desplegable permite consultar valores y seleccionar un territorio sin interpretar colores; sus filas sólo se montan al abrirla. El zoom/pan usa el contenedor interactivo para que la tarjeta no intercepte el pellizco; los botones conservan acciones propias. La rueda sigue siendo cooperativa y no captura la página fuera del mapa. El doble toque se verifica sobre el territorio ya seleccionado y su tarjeta; un toque sobre otro polígono puede seleccionar y encuadrar ese territorio antes de una interacción posterior.

Si No binario está activo y se cambia a un año sin esa categoría, conserva su nombre, muestra ausencia y deshabilita esa opción con explicación; no cambia silenciosamente de indicador ni produce ceros. En 2024 hay registros, pero **ningún estado o municipio alcanza soporte suficiente para colorear No binario**. El mensaje aclara que hay registros sin soporte territorial comparable, el mapa usa neutros y las cifras positivas siguen consultables con advertencia. Si en el ámbito no hay combinaciones observadas, se indica falta de información local; no se atribuyen registros de otros ámbitos. La categoría conserva LN=105 en los datos nacionales de 2024, sin extrapolar a otras elecciones.

Cobertura cartográfica de 2024, sumada sobre los 32 estados (2,478 geometrías; no equivale a 2,478 municipios electorales):

| Capa | Estados en escala | Estados con soporte reducido | Estados sin combinación | Geometrías municipales en escala | Con soporte reducido | Sin información |
| --- | --- | --- | --- | --- | --- | --- |
| Participación / No participación | 32 | 0 | 0 | 2,437 | 2 | 39 |
| Mujeres | 32 | 0 | 0 | 2,433 | 18 | 27 |
| Hombres | 32 | 0 | 0 | 2,429 | 22 | 27 |
| No binario | 0 | 18 | 14 | 0 | 55 | 2,423 |
| 18–34 | 32 | 0 | 0 | 2,400 | 51 | 27 |
| 35–59 | 32 | 0 | 0 | 2,422 | 29 | 27 |
| 60–100 | 32 | 0 | 0 | 2,407 | 44 | 27 |

Las 39 ausencias de participación son 12 denominadores cero y 27 geometrías sin correspondencia. En No binario, son 2,396 combinaciones no observadas y esas 27 geometrías. Se conservan además 26 registros municipales con datos sin unión cartográfica en 2024: no se suman a las geometrías como si fueran unidades disjuntas certificadas. La categoría No binario conserva LN=105 en la referencia nacional, incluidos registros sin unión al mapa.

### Fuentes, archivos y pruebas de la fase 4

Se añaden `public/data/territorial/layers/{year}.json` (seis) e `index.json`: **391,296 bytes**, manifiesto incluido. Cada archivo de elección empaqueta los 32 resúmenes estatales completos ya validados. Así el atlas nacional usa una consulta por elección, sin 32 consultas de resúmenes ni geometrías municipales. El generador concilia totales y celdas nacionales, verifica etiquetas y registra hashes de 204 entradas; el manifiesto identifica hashes/tamaños de los seis archivos. Los archivos anteriores se mantienen intactos.

Archivos nuevos: `src/features/map/thematicData.ts` (fórmulas, estados y validación), `useThematicMap.ts` (selección/carga), `ThematicMapControls.tsx` (controles, leyenda y tarjeta), `src/services/territorialLayers.ts` (servicio/cache por año), `src/styles/territorial-atlas.css`, `scripts/build-territorial-layers.mjs`, `scripts/territorial-layers.test.mjs` y el directorio público `layers/`.

Archivos ampliados sobre los cambios locales previos: `MapPage.tsx`, `TerritoryMap.tsx`, `TerritoryPanel.tsx`, `DemographicPanel.tsx`, `useMapGestures.ts`, `territorial.css`, `scripts/check-territorial-ui.mjs`, `package.json` y este documento. El resto de los cambios de fases 1–3 encontrados al inicio siguen pendientes localmente y no se atribuyen como archivos nuevos de esta fase.

`typecheck`, `test:map` (23 pruebas), `check:territorial-data` y `build` pasan. Se verifican generación determinista, contratos, etiquetas, las diez capas sobre **192 combinaciones estado–elección y 14,779 registros municipales**, ausencia/soporte, cuantiles repetidos, pocos valores, extremos, nulos, límites y paletas. Chrome contrasta valores crudos, clases y límites contra fuentes independientes: 32 polígonos nacionales en seis elecciones y municipios de Veracruz en 2024/2018. Comprueba que la presentación progresiva no altera cifras, que zoom/pan no cambia cortes y que «Ver ficha electoral» abre el territorio consultado. Se conservan todas las regresiones de navegación. La advertencia de bundle cartográfico permanece, aproximadamente 1.825 MB / 519 KB gzip. No hay dependencias nuevas.

## Iteración por fases 1–3: antecedentes conservados

Se implementaron primero las fases 1 y 2. Pasaron tipos, quince pruebas del mapa, build y 25 comprobaciones de Chrome antes de continuar con la fase 3. Aquella entrega pasó 26 comprobaciones de navegador. No se instalaron dependencias ni se reconstruyeron agregados en esa revisión. Su alcance se conserva a continuación como antecedente; la fase 4 actual se describe arriba.

| Fase | Estado | Cambios de esta revisión |
| --- | --- | --- |
| 1 · Diseño y jerarquía | Implementada | Cabecera más breve, mapa más alto, tarjeta lateral con pestañas Resumen / Edad y sexo, ranking existente en un bloque inferior independiente; ayuda, cartografía y metodología desplegables. |
| 2 · Navegación | Refinada y validada | Ruta México › entidad › municipio siempre visible, ubicación activa junto al buscador, campo limpio después de seleccionar, recorrido circular de sugerencias con flechas y reinicio seguro de la opción activa al cambiar de elección. Se conservan cámara, gestos, controles flotantes y selección persistente. |
| 3 · Tarjetas y demografía | Implementada tras validar 1–2 | Iconos reutilizables, barra visual de participación, cuatro conteos legibles, participación especificada sobre lista nominal, alcance por vista, alertas visibles y detalle metodológico expandible en México, entidades y municipios. |
| 4 · Nuevos hallazgos y rankings | Atlas implementado en revisión posterior | Véase la fase 4 actual: se añaden capas estadísticas descriptivas. El ranking mantiene datos, orden, criterios y paginación. No se generan interpretaciones causales. |
| 5 · Nuevas fichas de perfiles | Pendiente | Se conserva el contenido existente en un desplegable; sólo se añade su icono. No se cambian interpretaciones, estrategias ni reglas. |
| 6 · Preparación final de demo | Pendiente | Se comprueba la compatibilidad de esta entrega; una revisión final de presentación sigue después de la aprobación visual y de las siguientes fases. |

### Jerarquía y uso de la ficha

La vista inicial es **Resumen**: tasa, conteos y cobertura. **Edad y sexo** muestra las mismas tres desagregaciones y dos indicadores existentes, sin cargar una segunda copia de los datos. El panel inactivo usa `hidden`, por lo que no deja controles invisibles en el recorrido de teclado. Las pestañas tienen un punto de Tab; flechas y Home/End cambian de vista y mueven el foco. La vista elegida se conserva al navegar y cambiar de elección; las gráficas vuelven a su estado inicial cuando se renueva su recurso, como antes. Ninguna cifra del recurso anterior se presenta como actual.

Los detalles de correspondencia validada se pueden abrir; la correspondencia pendiente permanece como advertencia visible. En Resumen, las alertas de soporte reducido y no especificación elevada siguen visibles aunque «Cómo leer estos datos» esté cerrado. En demografía, las bases reducidas, tasas indefinidas y combinaciones ausentes mantienen señales visibles. La ayuda de teclado y las fuentes cartográficas no compiten con el mapa, pero conservan enlaces, atribuciones y límites históricos.

**Cobertura** distingue dos cocientes descriptivos: (SV+NV)/LN en el total y conteos incluidos/total en cada vista demográfica. No miden representatividad territorial ni confianza estadística; no se modifican tasas, ponderaciones o umbrales. «No especificado» abrevia la etiqueta de participación no especificada; su conteo y porcentaje siguen presentes y no se convierten en abstención. «No binario» se conserva donde hay registros, sin inventar ceros históricos.

### Archivos modificados en esta iteración

- `src/features/map/MapPage.tsx`, `TerritoryPanel.tsx`: composición, selección y pestañas.
- `src/features/map/TerritoryMap.tsx`, `TerritorySearch.tsx`, `ElectionTimeline.tsx`: ruta, ayuda, búsqueda y jerarquía de navegación.
- `src/features/map/ElectionMetricCards.tsx`, `DemographicPanel.tsx`, `StateElectionSummary.tsx`, `MunicipalElectionSummary.tsx`: tarjetas, cobertura y presentación progresiva de las vistas.
- `src/features/map/MunicipalityProfiles.tsx`: icono en el desplegable existente, sin rediseño de perfiles.
- `src/components/Icon.tsx`: cinco iconos SVG añadidos al catálogo, sin alterar los existentes.
- `src/styles/territorial.css`, `territorial-navigation.css`: ajustes locales; los colores base y las reglas globales se mantienen.
- `scripts/check-territorial-ui.mjs`: regresiones adaptadas a las pestañas y verificaciones adicionales de visibilidad, cobertura, búsqueda y alertas.
- `docs/explorador-territorial.md`: alcance, pruebas, instrucciones y siguientes fases.

### Checklist para continuar

- [x] Revisar lo existente antes de implementar y reutilizar componentes/servicios.
- [x] Mantener temas, paleta, foco, movimiento reducido y navegación de las seis elecciones.
- [x] Comprobar datos, tipos, build y Chrome en escritorio, 1024 px y 390 px.
- [ ] Revisar visualmente esta entrega con el equipo, incluyendo los textos plegados y la ficha en móvil.
- [ ] Probar lectores de pantalla y dispositivos táctiles físicos, incluido Safari/iOS.
- [x] Implementar la fase 4 como atlas estadístico trazable; la revisión visual del equipo sigue pendiente antes de fases 5 y 6.
- [ ] Evaluar optimización del paquete cartográfico y exportaciones PDF/PNG en entregas posteriores.

## Navegación y ranking: nueva experiencia

La búsqueda y la línea de elecciones sustituyen los selectores tradicionales. La lista alfabética se reemplaza por un ranking paginado, sin perder la posibilidad de buscar cualquier municipio. El botón exterior «Vista nacional» se elimina: el regreso a México está dentro del mapa, junto a acercar, alejar y encuadrar selección. La proporción mapa/ficha favorece ahora al mapa y el ranking queda debajo de ambos. Los estilos de navegación y ranking están en `src/styles/territorial-navigation.css`; se retiraron de la hoja local los selectores que ya no se usan y se aumentó la tipografía pequeña. Dashboard, Perfiles y Metodología no reciben estas reglas.

### Decisión técnica de cámara

La cartografía ya utiliza una proyección común y un `viewBox` SVG validado. Para estos requisitos bastan transformaciones de cámara, eventos de puntero y rueda: **no se incorpora una dependencia adicional ni se reemplazan las geometrías**. No se necesitan teselas, rutas o un motor cartográfico externo. Esto conserva la trazabilidad y las correspondencias previas.

`useAnimatedViewBox` ahora expone acercar, encuadrar, detener y establecer una vista. `useMapGestures` gestiona arrastre con ratón o un dedo, pellizco de dos dedos, doble clic y doble toque. Los botones +/− acercan/alejan; las entradas de usuario interrumpen una animación desde la posición alcanzada. Sólo se escribe el atributo SVG por cuadro y las rutas proyectadas se memorizan: no se recalculan cientos de polígonos en cada movimiento. No se afirma una frecuencia de cuadros garantizada para cualquier dispositivo.

La rueda funciona de forma cooperativa: **Ctrl/Meta + rueda** hace zoom directamente; un clic en el mapa activa la rueda normal hasta salir del mapa o pulsar Escape. Antes de esa activación, la rueda conserva el desplazamiento normal de la página. El mensaje dentro del mapa informa el modo. El gesto táctil se captura en el contenedor interactivo del mapa (`touch-action: none`), incluida la tarjeta contextual, no en toda la página.

El zoom limita el ancho de la vista a 0.25–1,200 unidades de la proyección nacional (su vista inicial es 800×500). El centro se limita al rectángulo nacional 0–800 / 0–500: impide desplazamientos arbitrariamente lejanos, pero no garantiza que cada centro caiga sobre tierra. «Ver todo México» y «Encuadrar territorio seleccionado» permiten recuperar el encuadre. Los controles se deshabilitan al alcanzar los límites o cuando la vista ya está encuadrada. Estos límites son de interfaz, no umbrales estadísticos ni precisión geográfica adicional.

Un movimiento de más de cinco píxeles se trata como arrastre y suprime el clic accidental de cierre. Un pellizco tampoco selecciona polígonos. Flechas recorren territorios; Mayús+flechas desplazan; +/− hacen zoom; Enter/espacio seleccionan; Escape libera la rueda. Se mantienen el foco visible, la búsqueda y el salto directo a la ficha. El movimiento reducido elimina las animaciones automáticas, pero conserva la manipulación directa del usuario.

### Búsqueda nacional y elección activa

`scripts/build-territory-search.mjs` crea **un índice de 363,904 bytes** con 32 entidades y 2,478 municipios/alcaldías de la cartografía 2024. No es un catálogo de localidades habitadas o residencias individuales. Se proyectan sólo nombres, claves y correspondencias de seis elecciones, nunca coordenadas. El archivo `public/data/territorial/search-index.json` registra las huellas de 65 recursos públicos: catálogos geográficos, correspondencias y nombres estatales. No se descargan las 32 geometrías municipales para sugerir resultados.

El buscador ignora acentos, mayúsculas y espacios repetidos, prioriza coincidencias exactas y prefijos, y muestra hasta diez sugerencias con entidad. Nombres municipales repetidos permanecen separados. Una consulta por clave puede encontrar tanto una clave INEGI como su correspondencia INE del año, **ambas etiquetadas**. Por ejemplo, El Llano y San Francisco de los Romo no intercambian indicadores aunque sus códigos 01010/01011 cambien entre sistemas.

El patrón de combobox/listbox mantiene foco en el campo, opción activa mediante `aria-activedescendant`, flechas/Enter/Escape y estados de vacío, carga, error, reintento y falta de coincidencias. Al elegir un municipio sólo se carga la geometría de su estado; la ficha espera esa resolución antes de presentar datos. Las búsquedas geográficas con correspondencia pendiente siguen siendo seleccionables, sin reutilizar cifras de otro municipio o elección.

La línea de elecciones usa seis botones de radio con un solo punto de Tab. Flechas y Home/End cambian elección; Enter/espacio activan el botón. Año, búsqueda, geometría, ficha y ranking usan la misma selección del componente de página. El regreso a México conserva la elección. El cambio de año mantiene la clave de geometría municipal y vuelve a resolver su correspondencia INE; se cancelan las peticiones anteriores y no se presentan sus resultados como actuales.

### Ranking: unidad, elegibilidad, desempate y cobertura

México muestra un ranking de **32 entidades**, usando `states.json` de la elección. Al elegir un estado se consultan los totales municipales completos de `public/data/territorial/{year}/{state}.json`; nunca se usa el subconjunto de perfiles. La unión a geometrías usa exclusivamente la correspondencia INE de ese año.

La tasa es SV/(SV+NV), presentada como porcentaje. En el listado comparable entran territorios con tasa definida, correspondencia disponible, LN≥100, SV+NV≥100 y filas fuente≥5: los criterios exploratorios ya documentados. NS/LN≥10 % no excluye, pero se advierte visiblemente. La base especificada aparece en cada fila. Los demás territorios se conservan en «Fuera de la comparación», distinguiendo falta de soporte, tasa indefinida, falta de datos y correspondencia pendiente; pueden localizarse cuando hay geometría. Un cero observado con denominador válido sí puede ordenarse; un NULL no se convierte en cero.

«Mayor participación» ordena de mayor a menor y «Menor participación» a la inversa. Se comparan fracciones por productos cruzados de enteros `BigInt`, no por porcentajes redondeados. Los empates exactos se resuelven por clave INE ascendente; cada fila recibe una posición ordinal, sin afirmar diferencias sustantivas entre tasas empatadas o próximas. La barra mide tasa, no cantidad de personas ni calidad institucional.

Se muestran **diez resultados por página**, con Anterior/Siguiente y posición global. Una selección desde búsqueda o mapa abre la página que contiene su fila y la resalta si cumple los criterios; los casos fuera de comparación siguen identificados en el apartado de cautelas. Cambiar el orden vuelve a la primera página. Así no se expanden automáticamente cientos de filas en estados grandes. El ranking siempre indica territorio y elección.

Cobertura sumada sobre los 32 rankings municipales (no es un nuevo ranking nacional municipal):

| Elección | Municipios comparables | Soporte insuficiente con tasa | Tasa no definida con correspondencia | Registros municipales sin unión cartográfica | Geometrías sin correspondencia INE |
| --- | --- | --- | --- | --- | --- |
| 2009 | 2,435 | 1 | 7 | 15 | 35 |
| 2012 | 2,437 | 2 | 1 | 15 | 38 |
| 2015 | 2,413 | 1 | 29 | 15 | 35 |
| 2018 | 2,434 | 1 | 13 | 15 | 30 |
| 2021 | 2,445 | 2 | 10 | 11 | 21 |
| 2024 | 2,437 | 2 | 12 | 26 | 27 |

Las primeras cuatro columnas de conteos particionan los registros municipales de cada elección; la última corresponde al catálogo geométrico 2024 y **no se suma** para obtener municipios electorales únicos. Es posible tener datos sin una geometría enlazada y geometrías pendientes por separado. La correspondencia por nombre no certifica continuidad de límites históricos. No se cambian umbrales ni se eliminan registros de origen para mejorar un ranking.

## Experiencia disponible

- Distribución de aproximadamente 63/37 entre mapa y ficha en escritorio amplio, con mínimo lateral de 340 px; una columna cuando el contenedor tiene hasta 850 px. El mapa tiene 470–660 px de alto en escritorio, 420 px en tableta y 360 px en móvil. En móvil la ficha sigue debajo del mapa y el ranking debajo de ambos.
- Identidad morada y cálida, modos claro/oscuro, tarjetas de conteos, comparación nacional y secciones de demografía, calidad y perfiles. Los estilos nuevos están organizados en `src/styles/territorial.css`; se revisó `global.css` y se conservó para las demás páginas.
- Ficha nacional: participación observada, lista nominal, participaron, no participaron, participación no especificada y su tasa; demografía y perfiles presentes. La selección vacía representa México y no un estado pendiente. No se compara México consigo mismo.
- Ficha estatal: los mismos indicadores, diferencia en pp frente a México del mismo año, perfiles y las tres vistas demográficas para cualquiera de las 32 entidades.
- Ficha municipal: los mismos indicadores generales para cualquiera de las seis elecciones, más participación por banda y sexo. Los servicios electorales y de perfiles existentes se conservan; el nuevo servicio consulta los archivos demográficos por año y estado.
- Barras para 18–34, 35–59 y 60–100 años. Tres botones permanentes alternan entre Por sexo, Por edad y Edad y sexo; en cada vista se puede elegir tasa o distribución de participantes. Hombres, Mujeres y No binario se muestran según registros disponibles, con etiquetas y patrones que no dependen sólo del color. No se muestran códigos internos de sexo.
- Tabla de valores y soporte por celda; categorías complementarias consultables; advertencias de soporte reducido, NS alto, tasa no definida y correspondencia territorial pendiente. Las tasas se muestran aun con advertencias, sin filtrar segmentos.
- Estados de carga, error con reintento y ausencia de información. Las peticiones se cancelan al cambiar la selección; la respuesta sólo se utiliza para su clave vigente. La caché demográfica separa año y estado y sólo almacena respuestas completas validadas.
- Las geometrías tienen un solo punto de entrada con Tab; las flechas recorren territorios y Enter/espacio seleccionan. El SVG también admite foco para los comandos de cámara. El botón principal «Ver ficha electoral» evita recorrer la lista municipal completa. La búsqueda, la tabla de valores y el ranking ofrecen alternativas al mapa.
- La navegación usa ahora la línea de elecciones, búsqueda nacional y controles flotantes; las referencias a selectores o lista municipal de las iteraciones previas quedan sustituidas por esos componentes y por el ranking.
- El acercamiento y alejamiento interpolan centro y tamaño de la vista SVG durante 480 ms con aceleración/desaceleración cúbica. Cada cuadro sólo modifica el atributo `viewBox`, sin recalcular cientos de geometrías. Una nueva selección interrumpe la anterior desde la vista alcanzada, sin volver al origen ni bloquear entradas. `prefers-reduced-motion` aplica el destino directamente y elimina transiciones y revelado.
- El estado y la geometría municipal seleccionados se conservan al cambiar de año. Se invalida la unión INE anterior y se resuelve la nueva; durante la carga sólo hay un estado de resolución y espacios de carga, sin cifras del año anterior. Una correspondencia pendiente conserva la selección visual y no recibe datos por sustitución.

Las etiquetas principales son «Lista nominal», «Participaron», «No participaron» y «Participación no especificada». Se conservaron los campos LN/SV/NV/NS y sus fórmulas. También se retiró el código técnico de la etiqueta No binario de la consulta nacional del menú principal; no se cambió su cálculo.

No se integraron estrategias institucionales ni se cambiaron definiciones de perfiles. PDF/PNG continúa pendiente: los componentes nuevos sirven de base para esa fase. Las capturas de las pruebas son evidencia local de navegador, no una función de exportación en la aplicación.

## Contrato, cálculos y conservación

Fuentes: `data/processed/participamx_multiyear/elections/{year}/municipality_segments/{state_code}.json`, más `municipalities.json`, `states.json` y `national_statistics.json` de cada elección. Se leyó el contrato real `2.0.0`: bandas, `sex_code` textual, cuatro conteos, `source_row_count`, `sufficient_support`, `high_ns` y `assignment_status`. La unidad nacional en la fuente es `election`.

El script produce `public/data/territorial/{year}/{state_code_2_digits}.json`, con contrato `territorial-explorer-1`. Cada municipio conserva su clave INE de cinco dígitos, nombre, totales de todas las categorías, identificadores de perfiles existentes y dos listas de celdas: `segments` (núcleo H/M de 18–100) y `complementary` (las demás). Los conteos y estados de soporte se proyectan de cada fila fuente, sin reestimar perfiles. La clave de trazabilidad es año + estado + municipio + banda + sexo; `source` identifica el archivo de agregados de procedencia.

Los códigos numéricos de la fuente se rellenan con ceros iniciales, sin truncarlos. Se rechazan códigos vacíos, fuera de rango, con espacios o caracteres no numéricos. Esto no transforma claves INEGI en claves INE: esa consulta continúa usando las correspondencias existentes por nombre único. Por ejemplo, San Francisco de los Romo usa geometría INEGI `01011` e indicadores INE `01010`.

Los archivos públicos incluyen **todas** las celdas disponibles, no sólo las de soporte suficiente. Las edades 101+ nunca se incorporan a 60–100; la categoría No binario conserva LN=105 en 2024. Su ausencia en otras elecciones no se convierte en una celda artificial de valor cero. Las categorías complementarias que se solapan aparecen una sola vez por combinación. La organización de almacenamiento de la primera iteración sigue separando núcleo Hombres/Mujeres y complementos; las vistas nuevas pueden consultar ambos sin duplicarlos.

| Indicador | Definición |
| --- | --- |
| Participación observada | SV / (SV + NV); no disponible si SV+NV=0 |
| Distribución de participantes | SV del grupo / suma SV del universo de la vista seleccionada; no disponible si esa suma es cero. No es la tasa de participación del grupo |
| No especificado | NS/LN; no disponible si LN=0; NS no se incorpora a NV |
| Diferencia nacional | 100 × (tasa del territorio − tasa nacional de la misma elección), en pp; no es un ajuste por edad/sexo |
| Soporte reducido | LN<100, SV+NV<100 o filas fuente<5; criterio exploratorio existente |
| NS elevado | NS/LN≥10 %; advertencia, no exclusión |

Las vistas por edad y cruzada se identifican como **universo parcial de 18–100 años**, incluyendo las categorías de sexo observadas. La vista sólo por sexo incluye todas las edades registradas, también 101+. No se denomina porcentaje de todos los votantes a una distribución parcial. Se muestran lista nominal y participantes incluidos frente a los totales del territorio, con conteos exactos y porcentajes de cobertura hasta cuatro decimales. Las tasas de la tabla se muestran redondeadas hasta dos decimales porcentuales; los cálculos conservan su precisión numérica.

### Resúmenes nuevos por escala y conciliación

`scripts/build-territorial-summaries.mjs` reutiliza los archivos municipales compactos validados, los suma por banda/sexo para cada estado y después para México. Primero se suman LN, SV, NV, NS y filas fuente; las tasas se calculan al consultar cada vista. Nunca se promedian porcentajes municipales. Las banderas del resumen se calculan sobre los conteos agregados de su propia unidad; no certifican soporte de todos los municipios que contribuyen.

Se verificó disponibilidad de `national_statistics.json`, `age_statistics.json` y `sex_statistics.json` en las seis elecciones procesadas, con unidades reales `election`, `national_exact_age_sex` y `national_sex`. Sexo contiene Hombres/Mujeres en 2009–2021 y añade No binario en 2024. Las etiquetas se contrastan con `sex_label` de la fuente. La edad exacta nacional se utiliza sólo para conciliar las nuevas bandas, no para publicar datos municipales masivos.

Cada suma estatal se contrasta con `states.json`. Cada banda/sexo nacional se compara con la suma correspondiente de `age_statistics.json`; los totales por sexo, con `sex_statistics.json`; la suma completa, con `national_statistics.json`. Las diferencias de los cinco conteos son cero en todos estos controles.

Los **199 archivos nuevos** (192 resúmenes estatales, seis nacionales y un índice) ocupan 423,702 bytes en `public/data/territorial/summaries/`. Usan un contrato separado `territorial-summary-1`; no cambian el contrato municipal ni los originales analíticos. Su índice contiene huellas de 216 recursos de entrada y de los 198 resúmenes, además de cobertura por año. El servicio carga únicamente el resumen del año y escala elegidos, con validación, cancelación y caché.

| Escala | Recursos públicos consultados | Demografía disponible |
| --- | --- | --- |
| México | Resumen `summaries/{year}/national.json` y estadística nacional existente | Sexo de todas las edades; tres bandas por todos los sexos observados; cruce banda/sexo, tasas y distribución |
| Estado | Resumen `summaries/{year}/{state}.json` y referencia nacional del mismo año | Las mismas vistas sobre sumas estatales, para las 32 entidades; no promedios de municipios |
| Municipio | Archivo compacto `{year}/{state}.json`, referencia nacional y perfiles existentes | Las mismas vistas, conservando celdas ausentes, tasas no definidas, soporte y correspondencia INE |

En 2024 la lista nominal nacional es 98,330,348. El núcleo Hombres/Mujeres de 18–100 suma 98,317,046; al incluir No binario en esas edades la vista nueva suma **98,317,151**. Quedan 13,197 registros nominales de edades 101+ fuera de las vistas por edad. Esta diferencia de universo está declarada, no es una pérdida de registros. La vista por sexo vuelve al total nacional completo. En elecciones anteriores la cobertura 18–100 es la ya documentada abajo, porque No binario no está registrado.

Si hay No binario a nivel nacional pero ninguna combinación observada en el territorio, la interfaz informa la limitación y no dibuja un cero. Si existe al menos una combinación local, las combinaciones faltantes siguen no disponibles y las escasas conservan su advertencia. Las tasas de soporte reducido llevan † y su base especificada junto a la barra, con explicación antes de la gráfica; así una tasa de 100 % basada en uno o pocos registros no se presenta sin contexto. No se deduce representatividad territorial de los 105 registros nacionales. La tabla complementaria es una referencia conservada y puede compartir categorías con las vistas nuevas; se advierte que no deben sumarse entre sí.

Una combinación ausente aparece como no disponible y no equivale a una fila presente con conteos cero. No se imputan tasas ni se crean registros individuales. Los totales municipales se concilian con la unión disjunta de núcleo y complementos. Las filas fuente son celdas originales, no personas o secciones independientes.

## Cobertura comprobada

| Elección | Municipios en los datos | Segmentos de todas las categorías | Tasas del núcleo no definidas | Celdas del núcleo con soporte reducido | Celdas del núcleo con NS≥10 % |
| --- | --- | --- | --- | --- | --- |
| 2009 | 2,458 | 18,545 | 42 | 652 | 680 |
| 2012 | 2,455 | 17,313 | 6 | 670 | 134 |
| 2015 | 2,458 | 17,549 | 180 | 814 | 2,480 |
| 2018 | 2,463 | 17,451 | 78 | 733 | 3,155 |
| 2021 | 2,468 | 17,771 | 60 | 660 | 1,901 |
| 2024 | 2,477 | 17,735 | 72 | 672 | 2,920 |

En estas fuentes no faltan combinaciones del núcleo esperado de seis celdas por municipio; sí existen tasas presentes no definidas. Esa observación no garantiza futuras fuentes completas ni disponibilidad de correspondencia cartográfica para todos los municipios. La interfaz contempla ambos casos.

Se generan **192 archivos estatales y un índice/manifiesto**, aproximadamente 22.51 MB sin compresión en total. El mayor archivo estatal ocupa 829,955 bytes. Se consulta sólo el estado y elección necesarios; no se incorporan los archivos de edad exacta ni los segmentos al bundle JavaScript. El índice registra hashes SHA-256 de 210 fuentes y de cada archivo estatal, tamaños, umbrales y cobertura por elección. La salida es determinista, sin fecha variable. `--check` compara íntegramente los archivos públicos y sus referencias con una nueva proyección de las fuentes.

## Arquitectura del explorador, incluidas iteraciones previas

| Archivos | Función |
| --- | --- |
| `src/features/map/MapPage.tsx` | Selección y carga de cartografía, composición del explorador |
| `src/features/map/TerritorySearch.tsx` y `territorySearchData.ts` | Combobox nacional, validación del índice y relevancia de sugerencias |
| `src/services/territorySearch.ts` y `scripts/build-territory-search.mjs` | Carga/caché del índice y generación reproducible sin geometrías |
| `src/features/map/ElectionTimeline.tsx` | Línea de elecciones accesible |
| `src/features/map/TerritorialRanking.tsx` y `territorialRankingData.ts` | Ranking de entidades/municipios, paginación, calidad y comparación exacta |
| `src/features/map/TerritoryMap.tsx` | Mapa, navegación territorial, controles flotantes y cámara |
| `src/features/map/viewBoxMotion.ts` y `useAnimatedViewBox.ts` | Interpolación SVG, cancelación desde la vista actual y preferencia de movimiento reducido |
| `src/features/map/useMapGestures.ts` | Punteros, pellizco, arrastre, doble toque y rueda cooperativa |
| `src/features/map/TerritoryPanel.tsx` | Composición de ficha y advertencias de correspondencia |
| `src/features/map/StateElectionSummary.tsx` y `MunicipalElectionSummary.tsx` | Indicadores estatales/municipales de la elección seleccionada |
| `src/features/map/ElectionMetricCards.tsx` | Tarjetas reutilizables y sección de calidad |
| `src/features/map/DemographicPanel.tsx` | Barras, modos de consulta, cobertura y tablas |
| `src/features/map/MunicipalityProfiles.tsx` y `profileLabels.ts` | Perfiles existentes en una sección desplegable, sin estrategias |
| `src/features/map/territorialData.ts` | Contrato, validaciones, normalización, cálculo y formato |
| `src/features/map/useTerritorialResource.ts` | Carga cancelable, clave de respuesta y reintento |
| `src/services/territorialDemographics.ts` | Servicio de consulta selectiva y caché validada |
| `src/styles/territorial.css` | Diseño del explorador, temas, adaptación y movimiento reducido |
| `src/styles/territorial-navigation.css` | Buscador, línea temporal, controles y ranking; reglas locales legibles |
| `scripts/build-territorial-data.mjs` | Proyección reproducible, conciliación y manifiesto |
| `scripts/build-territorial-summaries.mjs` | Resúmenes nacionales/estatales y conciliación adicional de edad/sexo |
| `scripts/territorial-data.test.mjs` | Pruebas de cálculo, contrato, claves y datos |
| `scripts/territorial-navigation.test.mjs` | Búsqueda, cobertura/orden de rankings, nulos, empates, zoom y límites |
| `scripts/check-territorial-ui.mjs` | Pruebas en Chromium real, sin instalar librerías de navegador |
| `package.json` | Comandos de generación y comprobación; pruebas de datos añadidas a `test:map` |
| `public/data/territorial/` | Únicos archivos de datos públicos nuevos de esta entrega |
| `src/features/dashboard/NationalAgeSex.tsx` | Ajuste editorial de etiqueta No binario, sin cambiar cálculos |
| `src/services/electionData.ts` | Validación de conteos estatales completos y filas fuente para el ranking |

## Reproducción y resultados extensivos de la entrega anterior

Esta sección conserva el alcance de la suite anterior como referencia. No se ejecutó la batería completa para los cambios de contraste/navegación/lectura de la entrega actual; consultar su validación limitada al inicio del documento.

Desde la raíz, con las dependencias existentes instaladas. En PowerShell se utiliza `npm.cmd` porque la política local bloquea `npm.ps1`; no se cambia esa política.

```powershell
npm.cmd run data:territorial
npm.cmd run check:territorial-data
npm.cmd run typecheck
npm.cmd run test:map
npm.cmd run build
npm.cmd run test:territorial-ui
```

`data:territorial` ejecuta la proyección municipal, los resúmenes, el índice de búsqueda y el paquete de capas; `check:territorial-data` comprueba los cuatro conjuntos. La generación requiere las fuentes procesadas locales (ignoradas por Git); su comprobación falla explícitamente si faltan. Los JSON públicos permiten consultar la aplicación sin distribuir esas fuentes privadas completas. El script municipal conserva `--output RUTA`; el de resúmenes usa `summaries/`, el de capas `layers/` y el buscador su archivo separado. Para regenerar sólo las capas: `node --experimental-strip-types scripts/build-territorial-layers.mjs`; con `--check` se comprueban sin escribir. Los archivos de datos anteriores conservan su contrato. Node debe admitir `--experimental-strip-types` (el proyecto requiere Node≥22.12; comprobado aquí con Node 24.13.1).

Resultados:

- `typecheck`: pasa.
- `test:map`: pasan los controles de 32 entidades, 2,478 geometrías municipales, seis años de correspondencias INE y **23 pruebas** de datos/navegación/capas/escalas. Incluyen los 14,779 registros municipales de las seis elecciones, las dos direcciones de ranking, empates exactos, cero observado frente a NULL, criterios separados de soporte, las diez fórmulas y cinco niveles de las doce paletas claro/oscuro. No se interpreta el número de geometrías como municipios electorales de una elección.
- Datos: claves con ceros, nulos frente a cero observado, pp, distribución parcial, soporte, duplicados, conservación de categorías y conciliación por municipio/entidad/nación. Los servicios estatales y nacionales públicos existentes concilian con las fichas. La regeneración determinista pasa para los 193 archivos previos y los 199 resúmenes nuevos. Se comprueba explícitamente un ejemplo donde la tasa de sumas difiere de la media municipal, los tres universos de vista y la interpolación con reinicio desde una posición intermedia.
- `build`: pasa. Persiste una advertencia de tamaño del chunk cartográfico: aproximadamente 1.825 MB sin compresión / 519 KB gzip, que incluye geometrías estatales existentes. Los segmentos, resúmenes, capas e índice se sirven como JSON selectivo, no dentro de ese chunk. No se añaden dependencias.
- Chrome real: **33 comprobaciones**. Incluyen cinco colores reales, límites contra fuentes, ausencia del selector, mismo orden de botones temáticos y apertura de metodología con teclado, conservando porcentajes. La tabla se abre por separado y conserva 32 filas nacionales / 212 de Veracruz. Se comprueban ambos neutros sin patrones ni clases cuantitativas para No binario, cifra positiva con soporte insuficiente, ausencia histórica sin cero y tema oscuro. También zoom/pan sin recalibrar cortes y clic real de «Ver ficha electoral» con destino/foco correctos. Se mantienen México en seis elecciones, demografía de Aguascalientes, San Francisco de los Romo con claves distintas, Coyoacán 2024→2009, Ziracuaretiro sin denominador y Villa de Pozos con correspondencia pendiente. Error/reintento, cambios rápidos, caché, flechas, Tab/Enter, tema, tableta y móvil de 390 px sin desbordamiento siguen cubiertos. Movimiento reducido elimina transiciones. El contraste mínimo de texto base evaluado es 5.09:1 en claro y 6.00:1 en oscuro; las pruebas de paletas comprueban ≥4.5:1 para el número sobre su superficie. No es una auditoría exhaustiva de accesibilidad.

La suite de Chrome añade autocompletado por teclado, nombres duplicados y estados de carga/error/vacío; verifica que las sugerencias no descargan las 32 geometrías. Comprueba Chihuahua, Xalapa desde otro estado, ranking nacional y municipal ascendente/descendente, paginación y resaltado de selección, y clic real sobre polígonos. Prueba botones de zoom, rueda normal con desplazamiento de página, Ctrl+rueda, rueda activada, arrastre sin selección accidental, doble clic y cancelación de animación. Usa eventos táctiles de Chrome para arrastre de un dedo, pellizco y doble toque; comprueba límites y controles deshabilitados con movimiento reducido. Se mantienen las regresiones de fichas y categorías. La tableta se verifica a 1024 px y el móvil a 390 px.

El navegador de prueba utiliza Chrome instalado o `CHROME_PATH`, un servidor temporal del build y un perfil propio dentro de `node_modules/.cache/territorial-ui/`. Se cierra al terminar. Allí quedan `results.json` y las capturas. La evidencia específica del rediseño es:

| Vista | Captura PNG |
| --- | --- |
| Nacional · participación relativa | `atlas-national-participation.png` |
| Leyenda · rangos y metodología desplegados | `atlas-legend-methodology.png` |
| Nacional · no participación cálida | `atlas-national-nonparticipation.png` |
| Veracruz · mujeres nominales | `atlas-state-women.png` |
| Veracruz · hombres nominales | `atlas-state-men.png` |
| Veracruz · mujeres entre participantes | `atlas-state-women-participants.png` |
| Veracruz · 18–34 | `atlas-age18-34.png` |
| Xalapa · selección y tarjeta | `atlas-selected-municipality.png` |
| Oscuro · Coyoacán | `atlas-dark.png` |
| Móvil · 390 px | `atlas-mobile.png` |
| No binario · soporte insuficiente en 2024 | `atlas-nonbinary-support.png` |
| No binario · categoría no registrada en 2018 | `atlas-nonbinary-unregistered.png` |
| No binario · neutros en oscuro | `atlas-nonbinary-dark.png` |

Las capturas estatales, selección, oscuro y móvil incluyen también un recorte del componente a resolución legible. Se revisaron visualmente la vista nacional, los colores rosa/azul, la selección, oscuro y móvil. Se conservan las capturas completas `desktop-light.png`, `desktop-dark.png`, `mobile-light.png`, `tablet-light.png`, `national-search-ranking.png`, `national-overview-light.png`, `national-demographics-light.png`, `state-overview-light.png`, `atlas-national-light.png`, `atlas-municipal-light.png` y `atlas-nonbinary-support.png`. Algunas muestran demografía, no el Resumen inicial. Si falla una prueba se registra estado `failed` y, cuando es posible, `failure.png`; ese archivo puede conservar la incidencia de un intento anterior, mientras que `results.json` es el estado de la última ejecución. Son artefactos locales ignorados por Git: no se implementa exportación de producto. El sandbox de este entorno impidió el arranque funcional de Chrome y la lectura de la carpeta padre por esbuild; los controles pasan fuera de él, sin cambiar dependencias ni configuración de seguridad.

## Verificación visual manual

```powershell
npm.cmd run dev -- --host 127.0.0.1
```

Abrir la dirección que indique Vite y entrar a `/#mapa`. Las instrucciones siguientes se usan con la línea visual de elecciones y el buscador, no con los selectores retirados.

Recorrido de la fase 4:

1. En Todo México, elegir 2024 y Participación → Participación ciudadana. Las 32 entidades muestran valores fuente con cuantiles y hasta cinco clases. No aparece una fila de escalas. La leyenda muestra menor/mayor porcentaje y el ámbito. Abrir «Ver rangos y metodología» con clic o Enter para consultar límites, frecuencias y denominador; «Consultar valores por territorio» abre la tabla. Pasar el cursor o enfocar un polígono para consultar su cifra; Escape cierra la tarjeta.
2. Elegir No participación: cambia el numerador a NV; NS sigue fuera del denominador especificado. El ranking inferior continúa siendo de participación, como indica su título; no cambia de significado al cambiar la capa.
3. Elegir Sexo → Lista nominal → Mujeres/Hombres: composición nominal rosa/azul. Cambiar a Participantes: SV de la categoría/SV total; no es la tasa dentro del sexo. La base y el nombre del universo cambian explícitamente. No binario nominal en 2024 usa dos neutros y explica soporte insuficiente/ausencia local, nunca ceros inventados; no hay rayado ni colores cuantitativos. Consultar una entidad con registros y comprobar su cifra positiva y advertencia. Cambiar a 2018 con No binario activo: categoría no registrada, no cero. Abrir la metodología y tabla para leer bases y motivos.
4. Buscar Veracruz y después Xalapa. Se representan municipios usando correspondencias INE del año, manteniendo el indicador activo. La tarjeta del mapa muestra la capa; la ficha Resumen conserva la participación general, que es una métrica distinta cuando la capa es demográfica.
5. Cambiar a 2018: Xalapa sigue seleccionado y se recalculan las capas con datos de 2018. No binario queda deshabilitado; si era la capa activa, explica la ausencia sin sustituirla silenciosamente por otra.
6. Elegir Edad → 60–100 años. El numerador no incluye 101+; el denominador sí conserva todo el nominal. Probar las otras dos bandas y comprobar numerador/base en la tarjeta o tabla.
7. Pulsar Ver ficha electoral; el foco llega a la ficha. Abrir Edad y sexo y usar los tres botones permanentes, incluido teclado. Las tasas y distribuciones de la ficha mantienen sus denominadores propios, distintos de composición nominal del mapa.
8. Probar tema oscuro, 390 px y movimiento reducido; acercar/arrastrar/pellizcar con la tarjeta visible y cerrada. Las cifras siguen disponibles sin depender exclusivamente de color o hover.

Datos de referencia para comprobar las fichas conservadas:

1. Sin elegir estado, Resumen de México 2024 muestra lista nominal 98,330,348; participaron 54,899,228; no participaron 37,105,466; no especificado 6,325,654; 93.57 % con participación especificada. Abrir Edad y sexo para probar las tres desagregaciones y ambos indicadores. Por sexo se muestra No binario (105 registros nominales); al cambiar a 2009 la categoría no está registrada y no se fabrica un cero.
2. Escribir «Chih» y elegir Chihuahua; probar Mayor/Menor participación y Anterior/Siguiente. Buscar «Xalapa» sin volver a México: debe cambiar a Veracruz y resaltar su municipio en la página correspondiente del ranking. Probar «San Pedro» para ver nombres repetidos con su entidad.
3. Buscar Aguascalientes: lista nominal estatal 1,097,171; participaron 626,084; no participaron 441,222; no especificados 29,865 en 2024. Probar las tres vistas estatales. Buscar San Francisco de los Romo: INEGI 01011 e INE 01010, lista nominal municipal 45,230.
4. Buscar Coyoacán: INE 09003, LN=571,993, SV=401,449, NV=148,552 y NS=21,992 en 2024. Alternar modos y abrir tablas.
5. Cambiar a 2009 **sin volver a seleccionar el municipio**: Coyoacán permanece resaltado, con lista nominal 559,912. Comprobar año, ficha y ranking; no deben conservarse cifras de 2024.
6. Buscar Ziracuaretiro en 2024: tasa municipal y tasas H/M no disponibles porque SV+NV=0; se conserva en cautelas fuera del ranking comparable, con sus conteos.
7. Buscar Villa de Pozos y cambiar de año: mantener la geometría seleccionada y correspondencia pendiente, sin asignar indicadores por la clave INEGI.
8. Probar +/−, encuadre, arrastre, doble clic, Ctrl+rueda y rueda tras clic. Escape o salir del mapa devuelve la rueda a la página. Probar pellizco/doble toque en pantalla táctil. «Ver todo México» debe conservar el año.
9. Probar combobox, línea temporal y pestañas de la ficha con teclado, tema claro/oscuro y anchos de tableta/móvil. Abrir Cómo navegar, Cartografía, Cómo leer estos datos y Conteos y alcance de la gráfica; las fórmulas y límites siguen disponibles. Activar movimiento reducido: no hay animaciones automáticas; la manipulación directa sigue disponible.

## Límites y trabajo posterior

La correspondencia por nombre único no es una equivalencia territorial histórica oficial. La cartografía municipal sigue siendo de 2024; no se presentan transiciones municipales entre elecciones. Los indicadores describen conteos agregados de cuadernillos, con las exclusiones de cobertura de la fuente, no motivaciones o conductas individuales.

La accesibilidad se revisó mediante teclado, texto, patrones, contraste de la paleta y adaptación real; no equivale a una certificación exhaustiva con lectores de pantalla o todas las tecnologías de apoyo. Debe continuar la revisión humana de lectura y navegación. La composición móvil es más larga porque conserva información y advertencias, con tablas y perfiles desplegables.

Los gestos se verifican con eventos reales del motor Chromium en emulación táctil; falta revisión física en distintos teléfonos y Safari/iOS. Los límites de cámara son rectangulares y el acercamiento no mejora la precisión de las geometrías generalizadas. La búsqueda se limita al catálogo municipal disponible, no a todas las localidades del país. El ranking es descriptivo y condicional a soporte, captura y correspondencias; no mide causas de participación, eficacia institucional ni calidad democrática.

Quedan para otra fase la exportación PDF/PNG y posibles optimizaciones de carga de geometrías. No se añade interpretación causal ni reglas nuevas de perfiles. Se mantuvieron intactos análisis, datos procesados anteriores, documentos de estrategias y sus JSON. No se hicieron commits, push o merges; la experiencia queda en la rama para revisión local.
