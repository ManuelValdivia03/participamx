# Plan de limpieza de ParticipaMX

Estado: propuesta para revisión, previa a cualquier normalización estadística o clustering. Este documento no aplica limpieza, no selecciona variables definitivas para modelos y no modifica los ZIP originales.

## Base de evidencia y alcance

Se revisaron el [informe de auditoría](reports/initial_audit.md), los perfiles de columnas, las frecuencias por año, las estadísticas descriptivas, los valores atípicos y los diccionarios incluidos en `audit_YEAR.json`. La auditoría cubre 54,872,712 filas de 192 CSV correspondientes a 2009, 2012, 2015, 2018, 2021 y 2024.

Para precisar las distribuciones conjuntas que no estaban en el informe, se hizo una lectura adicional de los seis ZIP por bloques de 100,000 filas, en modo de lectura, sin extraer ni guardar una base transformada. Se sumaron `LN`, `SV`, `NV` y `NS` por intervalos de `EDAD`; se cruzaron los faltantes de `DEF` y `DEL` con las claves territoriales. Estas comprobaciones adicionales se presentan aquí y no sustituyen el informe original.

Se distinguen tres clases de hallazgo:

- **Defecto de completitud o formato comprobado:** espacios o texto vacío en distritos, espacios periféricos en nombres y diferencias de serialización. Su existencia está verificada; su causa y el valor distrital correcto siguen sin conocerse.
- **Valor estadísticamente atípico o de plausibilidad pendiente:** edades extremas y colas de los conteos. Un umbral IQR no demuestra un error de captura ni autoriza una corrección.
- **Diferencia válida de categoría, significado o cobertura:** `SEXO=2` en 2024, referencias cartográficas diferentes y variación de `NS`. Requiere respetar el diccionario y evaluar comparabilidad.

No hay errores aritméticos comprobados: todas las filas cumplen `LN = SV + NV + NS`, no hay conteos negativos ni faltantes en esos cuatro campos, `LN` siempre es positivo y ningún componente supera `LN`. Tampoco se encontraron duplicados completos o por la clave candidata. Esto no valida por sí solo las edades ni la pertenencia de cada código a un catálogo oficial: la auditoría no impuso un máximo de edad ni contrastó todos los identificadores con catálogos externos.

## Reglas propuestas para las ocho variables

En esta tabla, **segura** significa que una futura transformación técnica puede preservar el contenido y ser reversible; **decisión humana** exige resolver el significado, la cobertura o una modificación sustantiva. Ninguna propuesta se ha ejecutado.

| Variable | Problema | Evidencia | Tratamiento propuesto | Justificación |
| --- | --- | --- | --- | --- |
| `DEF` | Faltantes comprobados; código categórico y cambio de referencia territorial. Los valores altos en su boxplot no prueban errores. | 28,477 valores de un espacio en 2009 y 15,677 en 2012; sin faltantes en los otros años. Valores presentes entre 1 y 41 hasta 2021 y entre 1 y 40 en 2024. Los TXT indican DERFE 2021 para 2009–2021 y DERFE 2023 para 2024. | **Segura:** conservar el token original y representar el faltante como nulo explícito en un campo derivado, con una bandera; conservar todas las filas. Tratar los valores presentes como códigos. **Decisión humana:** cualquier recuperación de distrito mediante un catálogo de la referencia correcta y una correspondencia única documentada. No usar moda, vecinos, arrastre ni asignación de otro año. | El vacío es comprobado, pero su reemplazo correcto no está determinado. El número de distrito sólo tiene significado junto con entidad y referencia cartográfica; no es una magnitud para recortar por IQR. |
| `DEL` | Faltantes comprobados con dos representaciones; posible pérdida territorial si se eliminan casos incompletos. | Un espacio en 28,477 filas de 2009 y 15,677 de 2012; texto vacío en 20,912 filas de 2024. Sin faltantes en 2015–2021; sin ceros observados. Los códigos presentes abarcan 1–45 a nivel nacional, sin validar límites por entidad. | **Segura:** conservar el valor original, crear un nulo explícito derivado y distinguir `blank_space` de `empty_string`; no excluir las filas de análisis estatal o municipal. **Decisión humana:** investigar causa y completar únicamente con evidencia oficial y una relación inequívoca. No deducir `DEL` de `DEF`: son divisiones distintas. | Una representación coherente del faltante no inventa un distrito. Borrar estas filas retiraría conteos válidos de municipios identificados. Los límites distritales deben validarse por entidad y marco, no mediante un máximo nacional. |
| `SEXO` | Cambio válido de categorías; categoría poco frecuente en 2024. | Sin nulos ni categorías ajenas al diccionario de cada año. `0` y `1` en 2009–2021; en 2024 se añade `2`, definido como no binario: 105 filas y suma de `LN` de 105. | **Segura:** conservar `0`, `1` y `2` como códigos categóricos y registrar el diccionario por año. **Decisión humana:** presentación y comparación histórica de la categoría añadida. No convertir `2` en nulo, `0` o `1`, ni eliminarlo por baja frecuencia; no representar su ausencia histórica como cero personas observadas. | La categoría está documentada y no es un error ni una distancia numérica. La falta de esa categoría en el esquema anterior no demuestra ausencia de personas. |
| `EDAD` | Edades extremas de plausibilidad pendiente; el IQR depende del año y de la unidad de observación. | Enteros sin nulos ni edades menores de 18. Máximos: 130, 132, 117, 137, 139 y 140. Hay de 10,318 a 32,761 celdas con edad mayor de 100 por año; véase el desglose siguiente. En 2015 existen 359 celdas de 111–117 años y cero atípicos de edad por IQR. | **Segura:** conservar la edad exacta y añadir banderas de revisión separadas: `age_over_100`, `age_over_120` y `age_iqr_outlier`, sin cambiar su valor. **Decisión humana:** validar con la fuente si hay errores de captura o códigos especiales y acordar cualquier regla de exclusión, corrección o agrupación. No truncar a 100/120 ni imputar la mediana. | Las banderas son filtros de revisión, no diagnósticos. Una edad extrema puede pasar el IQR; que sea un entero válido tampoco prueba su plausibilidad. Corregirla cambia la distribución demográfica. |
| `LN` | Cola derecha y diferencias de tamaño de las celdas; sin error estructural comprobado. | Mínimo 1 en todos los años; máximos por año: 969, 550, 506, 982, 452 y 550. Entre 362,320 y 629,786 filas por año superan el límite IQR superior. Sin negativos, nulos ni ceros; igualdad aritmética satisfecha en todas las filas. | **Segura:** conversión exacta a entero de 64 bits en una vista derivada y conservación del conteo; señalar extremos para revisión conjunta con territorio, edad y sexo. **Decisión humana:** investigar casos concretos con documentación antes de excluir o corregir. No recortar, winsorizar, dividir ni aplicar logaritmos como limpieza. | Un conteo grande puede corresponder a una celda poblada. La asimetría y el tamaño territorial no son errores; modificar `LN` aisladamente rompería la relación con sus componentes. |
| `SV` | Cola derecha y ceros válidos; diferencias temporales que no se explican sólo por calidad de datos. | Enteros no negativos, sin nulos; máximo nacional observado 424 en 2009. Hay ceros en todos los años y entre 408,280 y 601,753 atípicos IQR por año. Nunca supera `LN`. | **Segura:** conservar ceros y valores altos, convertir de forma exacta a entero y mantener controles conjuntos. **Decisión humana:** correcciones respaldadas por fuente, o la definición de futuros indicadores y denominadores. No convertir ceros en faltantes ni considerar `SV` un conteo de votos válidos por partido. | El diccionario lo define como registros con marca de voto. Los ceros y las diferencias entre elecciones son observaciones posibles; un extremo IQR no demuestra inconsistencia. |
| `NV` | Cola derecha y riesgo de confundir ausencia de marca con participación no especificada. | Enteros no negativos, sin nulos; máximo observado 603 en 2018. Entre 594,980 y 823,541 atípicos IQR por año; hay ceros válidos y ningún valor mayor que `LN`. | **Segura:** conservar íntegramente sus valores y ceros; validar como componente separado. **Decisión humana:** interpretar y comunicar los indicadores según cobertura. No sumar `NS` a `NV`, no imputar participación desconocida como ausencia de marca y no recortar valores grandes. | `NV` significa registros sin marca de voto, mientras que `NS` tiene otro significado. Mezclarlos modifica la interpretación de la participación y puede introducir sesgos temporales o territoriales. |
| `NS` | No especificación real, con fuerte variación entre años; IQR degenerado. No es un nulo técnico. | Sin faltantes ni negativos. `Q1 = Q3 = 0` en los seis años: todo valor positivo queda marcado por IQR. Su suma representa entre 0.220 % y 6.833 % de `LN`, según el año. | **Segura:** conservar `NS` y sus ceros como conteos; añadir indicadores de cobertura sin imputar. **Decisión humana:** denominador, umbrales de cobertura y análisis de sensibilidad para cada uso. No sustituirlo por cero, repartirlo entre `SV`/`NV` ni eliminar las filas con `NS>0`. | El diccionario incluye cuadernillos o páginas no disponibles y otros supuestos de participación no especificada. La etiqueta de atípico refleja una distribución con muchos ceros; no demuestra error ni abstención. |

Fuentes de los valores de la tabla: [perfiles](reports/column_profiles.csv), [faltantes y valores señalados](reports/invalid_values.csv), [estadísticas](reports/descriptive_statistics.csv), [valores fuera del IQR](reports/outlier_values.csv) y `value_frequencies_YEAR.csv`. Los máximos y las frecuencias describen celdas, no registros individuales de personas.

## Distribución de edades extremas

Los siguientes intervalos son exclusivamente una partición descriptiva para esta revisión; no constituyen grupos de edad definitivos ni umbrales de eliminación. Cada fila del origen representa una celda territorial por sexo y edad, de acuerdo con la clave candidata.

| Año | Celdas 101–110 | Celdas 111–120 | Celdas 121–130 | Celdas >130 | Edad máxima | Celdas >100 | Celdas de edad fuera del IQR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2009 | 31,098 | 1,451 | 212 | 0 | 130 | 32,761 | 159 |
| 2012 | 9,916 | 350 | 44 | 8 | 132 | 10,318 | 42 |
| 2015 | 11,764 | 359 | 0 | 0 | 117 | 12,123 | 0 |
| 2018 | 10,016 | 253 | 33 | 18 | 137 | 10,320 | 43 |
| 2021 | 12,840 | 338 | 15 | 23 | 139 | 13,216 | 29 |
| 2024 | 12,664 | 209 | 11 | 7 | 140 | 12,891 | 8 |

La mayoría de las celdas mayores de 100 está entre 101 y 110 años. La frecuencia de celdas >100 es 0.3763 % en 2009 y entre 0.1116 % y 0.1401 % en los otros años. Esta diferencia merece contrastarse con la metodología de captura y los diccionarios; no permite concluir que exista un error o una evolución demográfica real.

Los límites superiores IQR de `EDAD` son 122.5, 121.5, 121.5, 122.5, 122.5 y 125, respectivamente. Por tanto, `age_over_100` y `age_iqr_outlier` miden cosas distintas. Tampoco se deben interpretar los límites inferiores negativos del IQR como edades mínimas admisibles: la validación de dominio es independiente.

La lectura adicional permitió distinguir celdas de conteos nominales:

| Año | Suma de `LN` donde `EDAD>100` | Porcentaje del `LN` anual |
| --- | --- | --- |
| 2009 | 34,028 | 0.0439 % |
| 2012 | 10,522 | 0.0138 % |
| 2015 | 12,345 | 0.0148 % |
| 2018 | 10,468 | 0.0117 % |
| 2021 | 13,530 | 0.0145 % |
| 2024 | 13,197 | 0.0134 % |

Estos son conteos nominales reportados, sin validación individual de edad; no son personas únicas seguidas a lo largo de los años. Las 56 celdas con `EDAD>130` en el conjunto de elecciones suman `LN=56`. En 2024, las siete celdas de ese subconjunto se distribuyen entre las entidades `8`, `9`, `15`, `27` y `30`; no están concentradas en una única entidad. No debe atribuirse la anomalía a un solo archivo.

Antes de cualquier cambio sustantivo se propone revisar los casos con su edad exacta, conteos y procedencia; consultar si la fuente usa edades abiertas o códigos especiales y documentar su respuesta. Hasta resolverlo, conservar las filas y sus indicadores de revisión. Una eventual comparación de escenarios deberá cuantificar cambios en `LN`, `SV`, `NV` y `NS` por año, estado y municipio, sin sustituir silenciosamente la versión completa.

## Faltantes distritales y su impacto territorial

En 2009 y 2012, la lectura adicional confirmó que los faltantes de `DEF` y `DEL` coinciden en las mismas filas; no son dos conjuntos que deban sumarse. En 2024 sólo falta `DEL`, con `DEF` presente. Las claves de estado y municipio están disponibles en esas filas.

| Año | Campos faltantes | Filas afectadas | Porcentaje de filas del año | Entidades / municipios / secciones afectadas | Suma de `LN` afectada | Porcentaje del `LN` anual |
| --- | --- | --- | --- | --- | --- | --- |
| 2009 | `DEF` y `DEL` | 28,477 | 0.3271 % | 30 / 182 / 318 | 1,522,844 | 1.9654 % |
| 2012 | `DEF` y `DEL` | 15,677 | 0.1822 % | 28 / 153 / 221 | 909,923 | 1.1896 % |
| 2015 | Ninguno | 0 | 0 % | 0 / 0 / 0 | 0 | 0 % |
| 2018 | Ninguno | 0 | 0 % | 0 / 0 / 0 | 0 | 0 % |
| 2021 | Ninguno | 0 | 0 % | 0 / 0 / 0 | 0 | 0 % |
| 2024 | `DEL` | 20,912 | 0.2140 % | 32 / 75 / 136 | 1,862,959 | 1.8946 % |

Municipios y secciones se cuentan con `EDOCVE`, no por su número aislado. La proporción de `LN` afectada es mucho mayor que la de filas: una eliminación global de casos incompletos retiraría una cantidad relevante de conteos nominales. Además, la distribución no es uniforme: en 2024 Jalisco (`EDOCVE=14`) aporta 2,953 filas sin `DEL` y el Estado de México (`EDOCVE=15`), 2,278. Son frecuencias absolutas, no tasas de faltantes de cada entidad.

El tratamiento propuesto conserva estas filas para análisis por estado y municipio. Si se presenta un resultado por distrito, debe mostrarse también el subtotal «sin distrito identificado» y la cobertura correspondiente. No se debe redistribuir ese subtotal entre distritos conocidos ni omitirlo del total general.

Una futura recuperación de claves requiere el catálogo INE del marco indicado por el diccionario y una correspondencia inequívoca con la sección del año observado. Debe revisarse si hay secciones divididas, reasignadas o sin correspondencia; una relación múltiple queda pendiente de decisión. `DEF` y `DEL` necesitan validaciones independientes. No se ha identificado la causa de sus faltantes ni demostrado que correspondan a una única clase de cambio cartográfico.

## Diferencias entre años que condicionan la limpieza

- **Cartografía:** 2009–2021 usa distritos referidos a DERFE 2021 y 2024 a DERFE 2023, según los TXT. Conservar `AELEC` y `district_reference_year` por separado: el año electoral no equivale al año del marco. Una etiqueta distrital idéntica no garantiza territorio idéntico. Los rangos nacionales 1–41/1–40 de `DEF` y 1–45 de `DEL` no sustituyen un catálogo por entidad.
- **Fechas y serialización:** 2009–2021 usa UTF-8 sin BOM y LF; 2024, UTF-8 con BOM y CRLF. Leer correctamente estos formatos es seguro y no cambia el contenido. La cadena de 2024 es `06/02/2024`: confirmar el orden día/mes antes de producir una fecha derivada. El parser de la auditoría aceptaba ambas interpretaciones, por lo que su validación no resuelve esta ambigüedad. Mantener `FELECCION` original y no imponer una interpretación global sin metadatos.
- **Categorías:** mantener el diccionario de `SEXO` por año y la categoría añadida en 2024. No tratar su ausencia en 2009–2021 como un faltante técnico imputable.
- **Cobertura observada:** hay 32 entidades por año, pero 2,458, 2,455, 2,458, 2,463, 2,468 y 2,477 pares estado–municipio, respectivamente. Son coberturas observadas; no autorizan a completar combinaciones ausentes con ceros ni prueban por sí solas cambios territoriales. Las comparaciones históricas necesitan un inventario de presencia y catálogos versionados.
- **Calidad de especificación:** `NS/LN` es 2.408 %, 0.220 %, 6.126 %, 6.833 %, 4.323 % y 6.433 %, respectivamente. Las diferencias de participación no deben atribuirse únicamente al comportamiento ciudadano sin examinar esta cobertura y las diferencias metodológicas. Según los TXT, esta fuente excluye casillas especiales y residentes en el extranjero.

Si posteriormente se construyen indicadores, la decisión humana deberá distinguir `SV/LN` —proporción con marca sobre toda la lista reportada— de `SV/(SV+NV)` —proporción entre registros con participación especificada—. No estiman lo mismo. Este último no está definido cuando `SV+NV=0`; se deberá detectar ese caso y conservar un estado «no definido», sin sustituirlo por cero. Con conteos no negativos, `SV/LN` y `(SV+NS)/LN` delimitan un intervalo de participación posible si todos los no especificados se asignaran a los dos extremos; no constituyen una imputación ni una estimación puntual. Aquí no se han calculado ni elegido indicadores definitivos para clustering.

## Transformaciones seguras y decisiones pendientes

### Propuestas técnicas seguras para una implementación posterior

1. Mantener los ZIP inmutables y su SHA-256; leer por bloques con decodificación estricta. Conservar la procedencia de cada fila antes de cualquier conversión.
2. Crear campos derivados para los nulos distritales identificados, preservando el token original y la razón. Convertir espacio o texto vacío en una representación explícita de ausencia no equivale a imputar el distrito.
3. Convertir `EDAD`, `LN`, `SV`, `NV` y `NS` a enteros de 64 bits tras verificar que el parseo es exacto; conservar ceros y valores extremos. Mantener `DEF`, `DEL` y `SEXO` como códigos categóricos, sin atribuirles orden cuantitativo.
4. Añadir banderas como `is_federal_district_missing`, `is_local_district_missing`, `age_over_100`, `age_over_120`, `age_iqr_outlier` y `count_iqr_outlier`. Esta última debe identificar además el campo y el año del umbral; las banderas no deben filtrar automáticamente ninguna fila.
5. Conservar nombres originales y, si se requiere una etiqueta de presentación, retirar únicamente espacios periféricos en un campo derivado. En `MPIONOM` se observa `' Bacalar'` en 2009–2018: 3,270, 3,257, 3,324 y 3,389 filas. No cambiar nombres oficiales, acentos o claves mediante reglas generales ni usar el nombre como identificador.

Estas propuestas no alteran las sumas de los conteos ni la cantidad de filas. La elección de un nuevo tipo o representación deberá acompañarse de su contrato de esquema; no implica normalización estadística.

### Decisiones que debe resolver el equipo con evidencia

| Decisión | Información necesaria antes de resolverla | Conducta propuesta mientras está pendiente |
| --- | --- | --- |
| Corrección, exclusión o agrupación de edades extremas | Explicación de la fuente, catálogo de posibles códigos especiales y evaluación del impacto territorial y temporal. | Conservar la edad exacta y todas las filas con banderas. |
| Recuperación de `DEF` y `DEL` | Catálogos INE, referencias 2021/2023, correspondencias de secciones y resolución de relaciones múltiples. | Conservar el faltante explícito y los conteos; distinguir cobertura distrital. |
| Comparación histórica de municipios y distritos | Universo observado por año, catálogos versionados y correspondencias territoriales oficiales; validación de compatibilidad con geometrías. | Mantener las claves y el marco originales de cada año. |
| Interpretación de `FELECCION` | Metadatos oficiales que indiquen el formato, especialmente en 2024. | Conservar el texto y `AELEC`; no derivar una fecha ambigua. |
| Comparación de `SEXO=2` entre años | Alcance de la categoría según el diccionario de cada edición y acuerdo de presentación. | Conservar `2` en 2024 y distinguir categoría no disponible en el esquema histórico. |
| Tratamiento analítico de `NS` y denominadores | Definición del indicador y de su población objetivo, distribución de cobertura por estado/municipio/año y escenarios de sensibilidad. | Conservar `NS` separado y comunicar la cobertura; no asignarlo a `NV` ni a `SV`. |
| Modificación de registros que posteriormente resulten erróneos | Evidencia del valor correcto, motivo, responsable y versión de la regla; si no hay reemplazo conocido, una política explícita de exclusión para un uso concreto. | Señalar el caso para revisión; no reconstruir valores sólo para forzar una igualdad o un rango. |

No se propone eliminación general por nulos, deduplicación, recorte de colas, imputación, balanceo de categorías ni conversión automática de categorías a distancias. La auditoría no encontró duplicados que justifiquen eliminaciones. Tampoco se define todavía el conjunto de variables, la unidad de agrupación o la transformación estadística para el futuro clustering.

## Información que debe conservarse para estado y municipio

| Información | Regla de conservación y propósito |
| --- | --- |
| `EDOCVE`, `MPIOCVE` | Conservar como texto, con los valores originales y cualquier cero inicial. La identidad municipal es el par (`EDOCVE`, `MPIOCVE`). No concatenar sin separadores ni rellenar posiciones hasta confirmar el catálogo. Las claves son INE; no asumir equivalencia automática con claves INEGI o de geometrías externas. |
| `AELEC` | Conservar para distinguir cada elección. La identidad de una observación municipal de un año incluye (`AELEC`, `EDOCVE`, `MPIOCVE`). La misma clave entre años requiere revisar continuidad territorial. |
| `EDONOM`, `MPIONOM` | Mantener las etiquetas originales y cualquier etiqueta de presentación por separado; no unir tablas únicamente por nombre. Conservar una tabla de correspondencias con fuente y versión si se homologa una etiqueta. |
| `SECCION`, `TIPOSEC`, `DEF`, `DEL` | Conservar las claves y categorías de origen, incluidos distritos faltantes. Una sección se interpreta con entidad y año. Las dimensiones distritales necesitan también `district_reference_year`. Permiten revisar cobertura y asignaciones sin perder el nivel de detalle. |
| `SEXO`, `EDAD` | Conservar el detalle y el diccionario por año para desagregar resultados posteriormente y revisar casos extremos; no sustituirlo por grupos agregados sin guardar el origen. |
| `LN`, `SV`, `NV`, `NS` | Conservar los cuatro conteos para calcular sumas territoriales y denominadores explícitos. En una futura agregación, calcular tasas a partir de sumas compatibles; no promediar tasas de celdas sin sus denominadores ni sumar tasas. |
| Procedencia y control de cambios | Conservar `source_archive`, `source_member`, `source_record`, `source_sha256`, `schema_version`, banderas de calidad y el identificador/versionado de cada regla. `source_record` debe seguir siendo el ordinal de fila de datos, excluido el encabezado. Una futura corrección registra valor anterior, valor nuevo, motivo y evidencia. |

La clave candidata de detalle sigue siendo (`AELEC`, `EDOCVE`, `MPIOCVE`, `SECCION`, `SEXO`, `EDAD`). No tuvo repeticiones en la auditoría, pero debe validarse con la fuente antes de convertirla en una restricción definitiva. La identidad de procedencia es independiente de esa hipótesis de desagregación.

## Secuencia de trabajo y criterios de aceptación

1. Registrar las decisiones pendientes, el contrato de tipos y las versiones de catálogos. Conservar como línea base los hashes, filas, frecuencias y sumas de la auditoría.
2. Implementar sólo después la vista derivada con las transformaciones técnicas acordadas, por bloques y con registro de reglas. Mantener separada la evidencia de origen.
3. Evaluar la plausibilidad de edades, la cobertura de `NS` y las correspondencias territoriales; documentar cualquier cambio sustantivo aprobado y su impacto antes/después por año, estado y municipio.
4. Verificar que las transformaciones técnicas conservan las 54,872,712 filas, la relación de procedencia y las sumas de `LN`, `SV`, `NV` y `NS` por año/estado/municipio. No admitir pérdidas silenciosas por nulos al agrupar ni multiplicación de filas por uniones con catálogos. Revisar faltantes y duplicados otra vez tras cualquier conversión de claves.
5. Revalidar tipos, dominio, categorías por año y `LN = SV + NV + NS`. Si en una versión futura aparece una inconsistencia, señalarla y consultar su causa; no alterar un componente para cuadrar la ecuación. Conservar y verificar explícitamente los 105 registros de `SEXO=2` de esta versión.
6. Exigir que cada corrección o exclusión sustantiva tenga una conciliación de filas y conteos, evidencia y decisión registrada. Verificar que los ZIP mantienen sus SHA-256 y que cualquier resultado territorial informa la cobertura de distritos y participación especificada.

Las comprobaciones adicionales de este documento se obtuvieron con las condiciones exactas `101 <= EDAD <= 110`, `111 <= EDAD <= 120`, `121 <= EDAD <= 130`, `EDAD > 130` y `EDAD > 100`; los distritos faltantes se detectaron mediante texto vacío después de quitar espacios sólo para construir la máscara de consulta. Se sumaron los cuatro conteos sin reemplazar sus valores y se contaron municipios y secciones con su entidad. Los porcentajes de filas usan las filas del año; los porcentajes de `LN` usan la suma anual de `LN`. No se consultaron catálogos externos ni se diagnosticó la causa de los casos señalados.

El único entregable nuevo de esta revisión es este plan. La normalización, la selección definitiva de variables y la ejecución de modelos quedan fuera de su alcance.
