# Explorador Territorial 2.0 · entrega para revisión

Actualizado para el **rediseño de navegación y ranking electoral**: búsqueda nacional accesible, línea de elecciones, controles flotantes, cámara interactiva y ranking con cobertura y calidad explícitas. Se conservan las fichas de México, estados y municipios y sus tres vistas demográficas de las iteraciones anteriores. Los 193 archivos municipales y 199 resúmenes existentes mantienen sus contratos y cifras. No se crean commits, push o merges.

Implementado en `feat/mapa-fichas-demograficas`, creada desde `origin/main` actualizado en `ccf05b7` (PR #4 integrado). Se conservó el archivo local sin seguimiento encontrado al inicio. No se hicieron commits, push o merges.

## Navegación y ranking: nueva experiencia

La búsqueda y la línea de elecciones sustituyen los selectores tradicionales. La lista alfabética se reemplaza por un ranking paginado, sin perder la posibilidad de buscar cualquier municipio. El botón exterior «Vista nacional» se elimina: el regreso a México está dentro del mapa, junto a acercar, alejar y encuadrar selección. La distribución 60/40 y las fichas existentes se conservan. Los estilos nuevos de navegación y ranking están en `src/styles/territorial-navigation.css`; se retiraron de la hoja local los selectores que ya no se usan y se aumentó la tipografía pequeña. Dashboard, Perfiles y Metodología no reciben estas reglas.

### Decisión técnica de cámara

La cartografía ya utiliza una proyección común y un `viewBox` SVG validado. Para estos requisitos bastan transformaciones de cámara, eventos de puntero y rueda: **no se incorpora una dependencia adicional ni se reemplazan las geometrías**. No se necesitan teselas, rutas o un motor cartográfico externo. Esto conserva la trazabilidad y las correspondencias previas.

`useAnimatedViewBox` ahora expone acercar, encuadrar, detener y establecer una vista. `useMapGestures` gestiona arrastre con ratón o un dedo, pellizco de dos dedos, doble clic y doble toque. Los botones +/− acercan/alejan; las entradas de usuario interrumpen una animación desde la posición alcanzada. Sólo se escribe el atributo SVG por cuadro y las rutas proyectadas se memorizan: no se recalculan cientos de polígonos en cada movimiento. No se afirma una frecuencia de cuadros garantizada para cualquier dispositivo.

La rueda funciona de forma cooperativa: **Ctrl/Meta + rueda** hace zoom directamente; un clic en el mapa activa la rueda normal hasta salir del mapa o pulsar Escape. Antes de esa activación, la rueda conserva el desplazamiento normal de la página. El mensaje dentro del mapa informa el modo. El gesto táctil se captura únicamente dentro del SVG (`touch-action: none`), no en toda la página.

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

- Distribución aproximada 60/40 entre mapa y ficha cuando el contenedor dispone de más de 850 px; una columna debajo de ese ancho. En móvil la ficha está debajo del mapa.
- Identidad morada y cálida, modos claro/oscuro, tarjetas de conteos, comparación nacional y secciones de demografía, calidad y perfiles. Los estilos nuevos están organizados en `src/styles/territorial.css`; se revisó `global.css` y se conservó para las demás páginas.
- Ficha nacional: participación observada, lista nominal, participaron, no participaron, participación no especificada y su tasa; demografía y perfiles presentes. La selección vacía representa México y no un estado pendiente. No se compara México consigo mismo.
- Ficha estatal: los mismos indicadores, diferencia en pp frente a México del mismo año, perfiles y las tres vistas demográficas para cualquiera de las 32 entidades.
- Ficha municipal: los mismos indicadores generales para cualquiera de las seis elecciones, más participación por banda y sexo. Los servicios electorales y de perfiles existentes se conservan; el nuevo servicio consulta los archivos demográficos por año y estado.
- Barras para 18–34, 35–59 y 60–100 años. Un selector alterna entre edad y sexo cruzados, sólo edad y sólo sexo; en cada vista se puede elegir tasa o distribución de participantes. Hombres, Mujeres y No binario se muestran según registros disponibles, con etiquetas y patrones que no dependen sólo del color. No se muestran códigos internos de sexo.
- Tabla de valores y soporte por celda; categorías complementarias consultables; advertencias de soporte reducido, NS alto, tasa no definida y correspondencia territorial pendiente. Las tasas se muestran aun con advertencias, sin filtrar segmentos.
- Estados de carga, error con reintento y ausencia de información. Las peticiones se cancelan al cambiar la selección; la respuesta sólo se utiliza para su clave vigente. La caché demográfica separa año y estado y sólo almacena respuestas completas validadas.
- Las geometrías tienen un solo punto de entrada con Tab; las flechas recorren territorios y Enter/espacio seleccionan. El SVG también admite foco para los comandos de cámara. El botón «Ir a la ficha electoral» evita recorrer la lista municipal completa. La búsqueda y el ranking ofrecen alternativas al mapa.
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

## Archivos de implementación

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

## Reproducción y resultados de pruebas

Desde la raíz, con las dependencias existentes instaladas. En PowerShell se utiliza `npm.cmd` porque la política local bloquea `npm.ps1`; no se cambia esa política.

```powershell
npm.cmd run data:territorial
npm.cmd run check:territorial-data
npm.cmd run typecheck
npm.cmd run test:map
npm.cmd run build
npm.cmd run test:territorial-ui
```

`data:territorial` ejecuta la proyección municipal, los resúmenes y el índice de búsqueda; `check:territorial-data` comprueba los tres conjuntos. La generación requiere las fuentes procesadas locales (ignoradas por Git); su comprobación falla explícitamente si faltan. Los JSON públicos permiten consultar la aplicación sin distribuir esas fuentes privadas completas. El script municipal conserva `--output RUTA`; el de resúmenes usa `summaries/`, y el buscador su archivo público separado. Los archivos de datos existentes conservan su contrato. Node debe admitir `--experimental-strip-types` (el proyecto requiere Node≥22.12; comprobado aquí con Node 24.13.1).

Resultados:

- `typecheck`: pasa.
- `test:map`: pasan los controles de 32 entidades, 2,478 geometrías municipales, seis años de correspondencias INE y quince pruebas de datos/navegación. Incluyen los 14,779 registros municipales de las seis elecciones, las dos direcciones de ranking, empates exactos, cero observado frente a NULL y criterios separados de soporte. No se interpreta el número de geometrías como municipios electorales de una elección.
- Datos: claves con ceros, nulos frente a cero observado, pp, distribución parcial, soporte, duplicados, conservación de categorías y conciliación por municipio/entidad/nación. Los servicios estatales y nacionales públicos existentes concilian con las fichas. La regeneración determinista pasa para los 193 archivos previos y los 199 resúmenes nuevos. Se comprueba explícitamente un ejemplo donde la tasa de sumas difiere de la media municipal, los tres universos de vista y la interpolación con reinicio desde una posición intermedia.
- `build`: pasa. Persiste una advertencia de tamaño del chunk cartográfico: aproximadamente 1.80 MB sin compresión / 512 KB gzip, que incluye geometrías estatales existentes. Los segmentos, resúmenes e índice se sirven como JSON selectivo, no dentro de ese chunk. No se añaden dependencias.
- Chrome real: pasan **24 comprobaciones**. Se comprueban México en seis elecciones y las tres vistas, demografía estatal de Aguascalientes, No binario según el año, acercamiento SVG con cuadros intermedios sin desmontar el mapa, San Francisco de los Romo con claves distintas, persistencia de Coyoacán 2024→2009, Ziracuaretiro sin participación especificada y persistencia de Villa de Pozos con correspondencia pendiente. Se conservan pruebas de error/reintento, cambios rápidos, caché, flechas, Tab/Enter, tema y móvil de 390 px sin desbordamiento. Movimiento reducido aplica la vista destino directamente y elimina transiciones. El contraste mínimo de los pares de texto evaluados es 5.09:1 en claro y 6.00:1 en oscuro; no se presenta como auditoría de todo el sitio. No hubo excepciones JavaScript de la aplicación.

La suite de Chrome añade autocompletado por teclado, nombres duplicados y estados de carga/error/vacío; verifica que las sugerencias no descargan las 32 geometrías. Comprueba Chihuahua, Xalapa desde otro estado, ranking nacional y municipal ascendente/descendente, paginación y resaltado de selección, y clic real sobre polígonos. Prueba botones de zoom, rueda normal con desplazamiento de página, Ctrl+rueda, rueda activada, arrastre sin selección accidental, doble clic y cancelación de animación. Usa eventos táctiles de Chrome para arrastre de un dedo, pellizco y doble toque; comprueba límites y controles deshabilitados con movimiento reducido. Se mantienen las regresiones de fichas y categorías. La tableta se verifica a 1024 px y el móvil a 390 px.

El navegador de prueba utiliza Chrome instalado o `CHROME_PATH`, un servidor temporal del build y un perfil propio dentro de `node_modules/.cache/territorial-ui/`. Se cierra al terminar. Allí quedan `results.json` y capturas `desktop-light.png`, `desktop-dark.png`, `mobile-light.png`, `tablet-light.png`, `national-search-ranking.png`, `national-overview-light.png` y `state-overview-light.png`. Si falla una prueba se registra estado `failed` y, cuando es posible, `failure.png`, sin conservar un resultado anterior como si fuera el actual. Son artefactos locales ignorados por Git: no se implementa exportación de producto. El sandbox de este entorno impidió el arranque funcional de Chrome y la lectura de la carpeta padre por esbuild; los controles pasan fuera de él, sin cambiar dependencias ni configuración de seguridad.

## Verificación visual manual

```powershell
npm.cmd run dev -- --host 127.0.0.1
```

Abrir la dirección que indique Vite y entrar a `/#mapa`. Las instrucciones siguientes se usan con la línea visual de elecciones y el buscador, no con los selectores retirados.

1. Sin elegir estado, México 2024 muestra lista nominal 98,330,348; participaron 54,899,228; no participaron 37,105,466; participación no especificada 6,325,654. Probar las tres vistas y ambos modos. Por sexo se muestra No binario (105 registros nominales); al cambiar a 2009 la categoría no está registrada y no se fabrica un cero.
2. Escribir «Chih» y elegir Chihuahua; probar Mayor/Menor participación y Anterior/Siguiente. Buscar «Xalapa» sin volver a México: debe cambiar a Veracruz y resaltar su municipio en la página correspondiente del ranking. Probar «San Pedro» para ver nombres repetidos con su entidad.
3. Buscar Aguascalientes: lista nominal estatal 1,097,171; participaron 626,084; no participaron 441,222; no especificados 29,865 en 2024. Probar las tres vistas estatales. Buscar San Francisco de los Romo: INEGI 01011 e INE 01010, lista nominal municipal 45,230.
4. Buscar Coyoacán: INE 09003, LN=571,993, SV=401,449, NV=148,552 y NS=21,992 en 2024. Alternar modos y abrir tablas.
5. Cambiar a 2009 **sin volver a seleccionar el municipio**: Coyoacán permanece resaltado, con lista nominal 559,912. Comprobar año, ficha y ranking; no deben conservarse cifras de 2024.
6. Buscar Ziracuaretiro en 2024: tasa municipal y tasas H/M no disponibles porque SV+NV=0; se conserva en cautelas fuera del ranking comparable, con sus conteos.
7. Buscar Villa de Pozos y cambiar de año: mantener la geometría seleccionada y correspondencia pendiente, sin asignar indicadores por la clave INEGI.
8. Probar +/−, encuadre, arrastre, doble clic, Ctrl+rueda y rueda tras clic. Escape o salir del mapa devuelve la rueda a la página. Probar pellizco/doble toque en pantalla táctil. «Ver todo México» debe conservar el año.
9. Probar combobox y línea temporal con teclado, tema claro/oscuro y anchos de tableta/móvil. Activar movimiento reducido: no hay animaciones automáticas; la manipulación directa sigue disponible.

## Límites y trabajo posterior

La correspondencia por nombre único no es una equivalencia territorial histórica oficial. La cartografía municipal sigue siendo de 2024; no se presentan transiciones municipales entre elecciones. Los indicadores describen conteos agregados de cuadernillos, con las exclusiones de cobertura de la fuente, no motivaciones o conductas individuales.

La accesibilidad se revisó mediante teclado, texto, patrones, contraste de la paleta y adaptación real; no equivale a una certificación exhaustiva con lectores de pantalla o todas las tecnologías de apoyo. Debe continuar la revisión humana de lectura y navegación. La composición móvil es más larga porque conserva información y advertencias, con tablas y perfiles desplegables.

Los gestos se verifican con eventos reales del motor Chromium en emulación táctil; falta revisión física en distintos teléfonos y Safari/iOS. Los límites de cámara son rectangulares y el acercamiento no mejora la precisión de las geometrías generalizadas. La búsqueda se limita al catálogo municipal disponible, no a todas las localidades del país. El ranking es descriptivo y condicional a soporte, captura y correspondencias; no mide causas de participación, eficacia institucional ni calidad democrática.

Quedan para otra fase la exportación PDF/PNG y posibles optimizaciones de carga de geometrías. No se añade interpretación causal ni reglas nuevas de perfiles. Se mantuvieron intactos análisis, datos procesados anteriores, documentos de estrategias y sus JSON. No se hicieron commits, push o merges; la experiencia queda en la rama para revisión local.
