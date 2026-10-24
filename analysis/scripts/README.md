# Auditoría exploratoria inicial

`initial_audit.py` lee exclusivamente los seis ZIP originales de `data/raw/`,
sin extraerlos ni modificar registros. Produce el informe y la evidencia en
`analysis/reports/` y cuatro gráficos PNG en `analysis/charts/`.

Desde la raíz del repositorio, con el entorno Python del proyecto:

```powershell
.venv/Scripts/python.exe -m pip install -r analysis/scripts/requirements.txt
.venv/Scripts/python.exe analysis/scripts/initial_audit.py --chunk-size 100000
```

La instalación sólo es necesaria si faltan las dependencias. Los requisitos
fijan las versiones utilizadas en esta auditoría. También se guardan en
`analysis/reports/run_metadata.json`.

Para regenerar únicamente el informe y los gráficos a partir de los seis
`audit_YEAR.json` y sus tablas de frecuencias existentes:

```powershell
.venv/Scripts/python.exe analysis/scripts/initial_audit.py --report-only
```

Esta opción no vuelve a validar los ZIP. Una ejecución completa vuelve a
calcular la evidencia y comprueba sus SHA-256 antes y después. Los archivos
de evidencia con el mismo nombre se sobrescriben; los originales no se abren
en modo escritura. Las salidas de duplicados sólo se generan cuando existen
candidatos, por lo que conviene usar directorios de salida de una misma
ejecución al compartir resultados.

La memoria se controla con bloques de lectura, frecuencias agregadas y
particiones de hashes en disco temporal. Las colisiones de hashes se
descartan comparando las tuplas originales en SQLite. No se calculan
estadísticas sobre una muestra. El máximo de memoria también depende de la
cantidad de categorías diferentes; no se fija un límite absoluto.

Las claves de estado y municipio permanecen como texto. Los CSV auxiliares
son evidencia de auditoría, no una base corregida. Las reglas de validación,
la clave candidata y las limitaciones están documentadas en
`analysis/reports/initial_audit.md`.

Comprobaciones con datos sintéticos temporales, sin tocar `data/raw/`:

```powershell
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_initial_audit.py -v
```

Se verifican cuantiles exactos frente a un cálculo expandido, separación de
faltantes y ceros, categorías según el año, excepciones aritméticas,
duplicados entre bloques y archivos, colisiones forzadas de hashes y
conservación de ceros iniciales e integridad de los originales.

Las reglas existentes de `.gitignore` excluyen `analysis/reports/` y
`analysis/charts/`; los resultados permanecen disponibles localmente.

# Limpieza técnica segura

`clean_data.py` implementa exclusivamente las transformaciones técnicas de
`analysis/cleaning_plan.md`. Preserva las 16 columnas originales como texto,
añade versiones enteras de edad y conteos, distritos nullable, etiquetas sin
espacios periféricos y banderas de revisión. Conserva fechas, claves,
categorías, edades extremas, conteos y ceros. No genera tasas ni ejecuta
normalización estadística, imputación o clustering.

Requiere también PyArrow, fijado en `requirements.txt`:

```powershell
.venv/Scripts/python.exe -m pip install -r analysis/scripts/requirements.txt
.venv/Scripts/python.exe analysis/scripts/clean_data.py --chunk-size 100000
```

El destino predeterminado es `data/processed/technical_cleaned/`. Contiene:

- `records/election_year=YEAR/state_code=CODE/part-*.parquet`: filas completas
  en Parquet con compresión Zstandard, particionadas por año y entidad.
- `metadata/schema.md` y `schema.json`: contrato de columnas y tipos.
- `metadata/state_validation.csv`: filas, sumas y ceros de origen y salida
  por año/entidad, con diferencias explícitas.
- `metadata/quality_summary.csv` e `incidents.json`: indicadores conservados
  y errores de ejecución, si ocurrieran.
- `metadata/iqr_thresholds.json` y `source_dictionaries.json`: límites por
  año y diccionarios de origen.
- `metadata/run_manifest.json`: parámetros, versiones, hashes de fuentes,
  auditorías, documentos y script, y procedencia de cada parte.
- `_SUCCESS`: marcador de validación completa, con el hash del manifiesto.

El informe se guarda en `analysis/reports/technical_cleaning.md` y una copia
en `metadata/technical_cleaning.md`. El programa rechaza destinos existentes:
para repetir la ejecución sin sobrescribir resultados, elegir un destino
nuevo dentro de `data/processed/`:

```powershell
.venv/Scripts/python.exe analysis/scripts/clean_data.py --output data/processed/technical_cleaned_v2
```

Cada bloque se vuelve a leer del Parquet y se compara completo con el origen
y los derivados esperados. Se verifican la identidad aritmética, las filas,
sumas y ceros por año/entidad, los totales de auditoría, las banderas IQR,
el inventario de salida y los SHA-256. Una discrepancia detiene el proceso y
registra la incidencia; el directorio incompleto queda sin `_SUCCESS` y no
debe utilizarse. El script no elimina automáticamente resultados parciales.

Las particiones territoriales deben abrirse con tipo texto explícito. Desde
la raíz del repositorio, este ejemplo lee únicamente una selección por
bloques, sin cargar el conjunto completo en memoria:

```python
import sys
from pathlib import Path
import pyarrow.dataset as ds

sys.path.insert(0, "analysis/scripts")
from clean_data import open_dataset

dataset = open_dataset(Path("data/processed/technical_cleaned"))
scanner = dataset.scanner(
    columns=["EDOCVE", "MPIOCVE", "EDAD", "LN", "age_value", "registered_count"],
    filter=(ds.field("election_year") == 2024) & (ds.field("state_code") == "1"),
    batch_size=100_000,
)
for batch in scanner.to_batches():
    print(batch.num_rows)
```

`state_code` es un alias de partición que conserva el texto de `EDOCVE`;
`MPIOCVE` también permanece como texto dentro de cada archivo. La referencia
cartográfica se conserva en `district_reference_year` y los diccionarios.
Las columnas de procedencia permiten volver al ZIP, CSV y registro exactos.
Los datos procesados permanecen excluidos de Git por las reglas existentes.

Pruebas con ZIP sintéticos temporales, sin modificar las fuentes reales:

```powershell
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_clean_data.py -v
```

Se comprueban nulos derivados con originales intactos, ceros iniciales,
SEXO=2, conteos y ceros, banderas, rechazo de cambios en Parquet y ZIP,
fallos sin marcador de éxito y resultados equivalentes con bloques de
tamaños diferentes. No se aplican decisiones metodológicas pendientes.

# Base descriptiva territorial, demográfica e histórica

`build_descriptive.py` lee el conjunto técnico con `open_dataset()` y crea
tablas nuevas, sin modificar las fuentes. Verifica los hashes de todos los
Parquet limpios y sus metadatos, y los de los seis ZIP, antes y después.

```powershell
.venv/Scripts/python.exe analysis/scripts/build_descriptive.py --batch-size 100000
```

El destino predeterminado es `data/processed/descriptive/`. Se protegen los
destinos existentes; una repetición debe usar otro `--output` dentro de
`data/processed/`. El proceso selecciona columnas y lee por bloques, con
acumuladores reducidos periódicamente y limitados a una entidad/elección.
Los niveles pequeños se mantienen en memoria; no se cargan las 54 millones
de filas completas ni toda la tabla demográfica a la vez.

Las cinco tablas principales son `year`, `state`, `municipality`,
`municipality_age_sex` y `municipality_section_type`. Las tablas auxiliares
`age_sex_year`, `sex_year` y `section_type_year` se derivan de esos conteos
para el informe y los gráficos. La tabla demográfica se reparte en archivos
por año y entidad; las otras tablas contienen un Parquet cada una.

En todos los niveles se suman LN/SV/NV/NS antes de calcular los indicadores:

- `specified_count = SV + NV`.
- `participation_observed = SV / specified_count`.
- `nonparticipation_observed = NV / specified_count`.
- `participation_nominal = SV / LN`.
- `unspecified_rate = NS / LN`.

Las tasas son proporciones 0–1, sin normalización estadística. Para mostrar
un porcentaje se multiplica por 100. Si un denominador es cero, la tasa es
NULL, nunca cero. No se rellenan combinaciones ausentes, no se promedian
tasas de celdas ni se suman las tablas de niveles distintos entre sí.

`source_row_count` cuenta filas fuente, no personas. Los campos
`sex_2_source_rows` y `sex_2_nominal_count` permiten conciliar SEXO=2 también
en niveles sin esa clave. Los códigos territoriales, SEXO y TIPOSEC son
texto; las edades son exactas y se conservan las extremas. Cada año mantiene
sus categorías y la referencia cartográfica, sin suponer continuidad de
territorios entre elecciones. Las etiquetas no se usan como claves.

Las banderas de revisión usan por defecto LN<100, SV+NV<100 o menos de cinco
filas fuente para soporte pequeño, y NS/LN≥10 % para no especificación
elevada. Son umbrales exploratorios configurables mediante
`--min-registered-count`, `--min-specified-count`, `--min-source-rows` y
`--high-unspecified-rate`; no son criterios oficiales, filtros de exclusión
o pruebas de error.

Los metadatos incluyen:

- `table_contract.json`: claves, fórmulas, categorías y umbrales.
- `state_reconciliation.csv`: diferencias de conteos por nivel/año/entidad.
- `group_quality.csv`: soporte pequeño, NS alto y tasas no definidas.
- `input_hashes.json` y `run_manifest.json`: fuentes, versiones, archivos
  generados y validaciones; `_SUCCESS` sólo aparece al completar el proceso.

El informe queda en `analysis/reports/descriptive_analysis.md`, con copia
en `metadata/`, y cinco gráficos en `analysis/charts/descriptive/`. Las
comparaciones son descriptivas, sin interpretación causal ni selección
definitiva de variables de clustering.

Para regenerar únicamente la presentación desde los agregados ya validados:

```powershell
.venv/Scripts/python.exe analysis/scripts/build_descriptive.py --report-only
```

Esta opción verifica los hashes de los agregados y conserva su manifiesto
de construcción. Registra el hash de la versión del código que genera la
presentación en `metadata/presentation_manifest.json`; no vuelve a agregar
las fuentes ni modifica los Parquet.

Ejemplo de lectura por bloques de una tabla, manteniendo claves textuales:

```python
import pyarrow.dataset as ds

dataset = ds.dataset(
    "data/processed/descriptive/municipality_age_sex", format="parquet"
)
scanner = dataset.scanner(
    filter=(ds.field("election_year") == 2024) & (ds.field("EDOCVE") == "1"),
    batch_size=100_000,
)
for batch in scanner.to_batches():
    print(batch.num_rows)
```

Pruebas de denominadores nulos, ponderación correcta, conservación entre
niveles, claves y equivalencia entre tamaños de bloque:

```powershell
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_build_descriptive.py -v
```

# Revisión de extremos y visualización demográfica

`analyze_outliers.py` reutiliza las tablas descriptivas, las frecuencias de
la auditoría y sus estadísticas. No vuelve a procesar los 54 millones de
registros: la lectura más grande recorre por bloques los 2.4 millones de
agregados municipio–edad–sexo. Los ZIP y Parquet previos sólo se leen como
archivos binarios para verificar sus hashes, sin volver a interpretar sus
registros. Los datos, informes y gráficos anteriores permanecen intactos.

```powershell
.venv/Scripts/python.exe analysis/scripts/analyze_outliers.py
```

El informe queda en `analysis/reports/outlier_review.md`, la evidencia CSV
y el manifiesto en `analysis/reports/outliers/` y cinco gráficos nuevos en
`analysis/charts/outliers/`:

- `age_boxplots.png`: distribuciones de edad por filas fuente y por LN.
- `age_sex_profiles_reviewed.png`: vista principal 18–100; soporte reducido
  señalado y líneas interrumpidas; SEXO=2 sólo con puntos.
- `age_extremes.png`: frecuencias exactas >100, con filas y LN por separado.
- `count_boxplots.png`: LN/SV/NV por celda fuente y total municipal.
- `unspecified_rate_boxplots.png`: NS/LN municipal con dos ponderaciones.

Los cuantiles lineales ponderados reproducen una distribución expandida de
frecuencias enteras sin expandirla en memoria. Se usa la regla de Tukey de
1.5 IQR como señal estadística, separada de las bandas descriptivas 101–110,
111–120 y >120. Ninguna señal demuestra que un registro sea erróneo.

Las tasas de los intervalos se calculan después de sumar conteos; un intervalo
vacío o con SV+NV=0 tiene tasa no definida. Se distinguen las celdas fuente,
los grupos demográficos y los municipios. La ponderación LN describe conteos
nominales reportados, no personas únicas seguidas entre elecciones.

La vista 18–100 no cambia edades, tasas, denominadores ni tablas; no es una
regla de exclusión para clustering. Los extremos se documentan aparte. La
escala logarítmica de algunos ejes de conteos es sólo una representación
visual y no se almacena como transformación estadística de los datos.

Para repetir sin sobrescribir salidas, elegir rutas nuevas:

```powershell
.venv/Scripts/python.exe analysis/scripts/analyze_outliers.py --charts analysis/charts/outliers_v2 --evidence analysis/reports/outliers_v2 --report analysis/reports/outlier_review_v2.md
```

Pruebas de cuantiles ponderados frente a expansión, límites de intervalos,
separación entre nulos y ceros y denominadores pequeños:

```powershell
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_analyze_outliers.py -v
```

# Evaluación de representaciones demográficas

`evaluate_representation.py` compara edad exacta (A), cuatro esquemas
candidatos de intervalos (B) y perfiles municipales (C). Reutiliza las
tablas descriptivas existentes, con lectura por bloques y detalle limitado
a una elección en memoria. No vuelve a procesar los 54 millones de registros.

```powershell
.venv/Scripts/python.exe analysis/scripts/evaluate_representation.py
```

El informe es `analysis/reports/clustering_representation.md`. La evidencia
queda en `analysis/reports/representation_evaluation/`: tamaños, cuantiles,
banderas de soporte y NS, cobertura de coordenadas, sensibilidad de
umbrales, pérdida de detalle intrabanda, contraste 75+/75–100, inventario
histórico de claves y costes algebraicos de memoria. Los Parquet candidatos
son escenarios nuevos de diagnóstico, sin sustituir las tablas descriptivas
ni constituir una matriz final de entrenamiento.

Los perfiles distinguen combinaciones ausentes de tasas presentes no
definidas, sin rellenar tasas con cero. El núcleo H/M y los intervalos
acotados son escenarios explícitos: las edades extremas y SEXO=2 permanecen
en las tablas largas y totales. La dispersión intrabanda pondera por SV+NV;
no es una estimación de incertidumbre. Los costes no asignan matrices de
distancias ni ejecutan modelos.

Cada escenario concilia los siete conteos de control por municipio y
año/entidad, conserva las filas fuente y SEXO=2 y verifica los hashes de
datos e informes anteriores. Los escenarios son vistas alternativas:
no deben concatenarse y sumarse como poblaciones distintas. El manifiesto
registra versiones, parámetros, hashes y cualquier error. No hay
normalización estadística, imputación, exclusión automática ni clustering.

El script rechaza destinos existentes; para repetir:

```powershell
.venv/Scripts/python.exe analysis/scripts/evaluate_representation.py --batch-size 50000 --evidence analysis/reports/representation_evaluation_v2 --report analysis/reports/clustering_representation_v2.md
```

Pruebas de límites de intervalos, conservación, tasas de sumas, distinción
entre ausencia y tasa no definida, dispersión ponderada y memoria calculada:

```powershell
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_evaluate_representation.py -v
```

# Matrices candidatas de clustering para 2024

`build_cluster_features.py` reutiliza los cuatro escenarios B de la
evaluación y prepara dos perfiles C (amplios y etapas). Sólo recorre los
401,486 agregados por edad exacta de 2024 para conservar la referencia y
calcular momentos de edad; no reprocesa los 54 millones de filas fuente.

```powershell
.venv/Scripts/python.exe analysis/scripts/build_cluster_features.py
```

Las seis matrices quedan en `data/processed/cluster_features/matrices/`.
Cada una separa `features.parquet` de `metadata.parquet`, alineados mediante
`row_id`. El contrato `metadata/feature_contract.json` enumera las únicas
columnas candidatas de cada matriz:

- B: participación observada y edad media ponderada por LN. Se declara
  también el subconjunto `rate_only`, con la tasa sola. Los códigos de
  sexo y territorio son metadatos, no magnitudes numéricas.
- C: seis o diez tasas por intervalo y sexo H/M. Cada coordenada conserva
  sus conteos, denominadores y banderas en `cell_metadata.parquet`.

`row_id` tampoco es una variable para distancias. Las tasas siguen siendo
proporciones 0–1 y las edades se guardan en años, sin escalado estadístico.
Los pesos candidatos quedan en metadatos; no se aplican a modelos. Los
cuartiles de diagnóstico usan inversa de la distribución empírica ponderada
y la DE descriptiva usa ddof=0; no deben confundirse con la convención
lineal de cuantiles de los informes anteriores.

Las matrices conservan todas sus filas y los NULL. `blocked_observations.parquet`
lista filas no completas que permanecen también en la matriz.
`can_use_complete_algorithms` sólo indica completitud numérica, no calidad
estadística o autorización para entrenar. No hay imputación ni selección
automática. Las combinaciones ausentes en C mantienen conteos NULL;
una celda presente con SV+NV=0 conserva sus conteos y la tasa NULL.

`reference/exact_age_2024.parquet` conserva edades exactas, mayores de 100,
SEXO=2 y la asignación a cada escenario. La referencia complementaria es
la unión EDAD>100 o SEXO=2, sin duplicar intersecciones. Las referencias,
matrices, totales municipales y metadatos de coordenadas son vistas
relacionadas: no se suman entre sí.

El informe es `analysis/reports/cluster_feature_review.md`; seis gráficas
de diagnóstico quedan en `analysis/charts/cluster_features/`. Se estudian
distribuciones, correlaciones por pares, redundancias, cobertura y pesos
iguales frente a LN. La viabilidad de curvas se documenta a partir de
soporte por edad, sin implementar suavizado o modelos.

El programa concilia los siete conteos aditivos por municipio y entidad,
contrasta los perfiles C con la evaluación previa, verifica el Parquet
escrito y los hashes de los archivos existentes. `_SUCCESS` sólo se crea
si todo pasa. No modifica fuentes ni resultados previos, normaliza,
ejecuta clustering o selecciona K. Para repetir sin sobrescribir:

```powershell
.venv/Scripts/python.exe analysis/scripts/build_cluster_features.py --output data/processed/cluster_features_v2 --charts analysis/charts/cluster_features_v2 --report analysis/reports/cluster_feature_review_v2.md --batch-size 50000
```

Pruebas con datos sintéticos temporales:

```powershell
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_build_cluster_features.py -v
```

# Primer piloto territorial de clustering · 2024

`run_clustering_pilot.py` compara C–Amplios y C–Etapas con tasas originales,
StandardScaler y RobustScaler, sin instalar dependencias adicionales. Los
algoritmos y métricas se implementan en `clustering_core.py` con NumPy:
Ward por cadena de vecinos recíprocos, Lloyd con k-means++ clásico, DBSCAN,
Silhouette exacto, Davies–Bouldin y Adjusted Rand Index. Se explicita la
limitación de no haberlos contrastado con una librería independiente.

```powershell
.venv/Scripts/python.exe analysis/scripts/run_clustering_pilot.py
```

El principal usa municipios con todas las tasas completas y soporte
suficiente en cada coordenada, con peso uno por municipio. Se conservan
los 2,477 municipios en cada contexto: pendientes con etiquetas NULL,
razón y metadatos; ruido DBSCAN con -1 sólo en el entrenamiento.
Los datos y las matrices anteriores permanecen intactos.

Se exploran K=2…10 para Ward y K-Means; K-Means usa semillas 17/42/2024
y diez inicializaciones por semilla. Para DBSCAN, min_samples incluye el
propio punto y vale max(5,p+1) o su doble; eps cubre los cuantiles
50/75/90/95 de las distancias al vecino correspondiente. No se fuerza
el número de grupos. Las métricas DBSCAN se guardan con y sin ruido y
con causa de indefinición cuando no aplican.

La ecuación (4) del Teorema 2.5 del original arXiv:2502.00851v2 se verificó
antes de implementar el método geométrico del codo. Sólo se evalúan los
puntos interiores K=3…9. Se documenta su dependencia de los ejes y se
compara con controles de escala, sin adjudicarles garantías de optimalidad.

La sensibilidad NS<10 % por coordenada y la alternativa Etapas 75+
reutilizan escalador y cuadrícula DBSCAN del principal. La comparación
75+/75–100 mantiene los mismos municipios, K y semillas; las asignaciones
se comparan con ARI y alineación de etiquetas. No se ejecuta K-Medoids:
sólo se evalúa si los resultados justifican probarlo después.

Los datos quedan en `data/processed/clustering_pilot/contexts/` y los
resúmenes en `metadata/`. Cada contexto incluye matrices crudas y
transformadas, metadatos, pendientes, etiquetas, métricas, inicializaciones,
centroides, tamaños, parámetros del escalador y árbol Ward completo.
Las figuras principales incluyen dendrogramas truncados y SVG completos,
comparación de cortes, codo, métricas por K, tamaños, k-distance y DBSCAN.

El informe es `analysis/reports/clustering_pilot.md`; los gráficos quedan
en `analysis/charts/clustering_pilot/`. No se elige un modelo definitivo
ni se asignan nombres a perfiles ciudadanos. Los destinos se protegen;
para repetir elegir nuevos --output, --charts y --report.

Pruebas independientes de fórmulas, casos degenerados, retención de
pendientes y reproducibilidad de semillas y asignaciones:

```powershell
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_clustering_pilot.py -v
```

## Piloto de segmentos demográficos B · 2024

```powershell
.venv/Scripts/python.exe analysis/scripts/run_demographic_pilot.py
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_demographic_pilot.py -v
```

Reutiliza B–Etapas y B–Amplios, con participación observada y edad media
nominal como únicas características. Ajusta K-Means K=2…10, con semillas
17/42/2024 y diez inicializaciones por semilla. Compara escala original y
estándar, conjunto y estratos H/M. El escalador de cada conjunto principal
se reutiliza en sus estratos y en la sensibilidad conjunta que añade 101+
con soporte. Todos los ajustes usan peso uno por segmento; otros pesos
se comparan descriptivamente, sin incorporarlos a los modelos.

Se conservan todas las filas originales y sus conteos. Sólo se entrenan
segmentos completos con LN≥100, SV+NV≥100 y filas fuente≥5; el principal
abarca 18–100. NS elevado no se excluye. SEXO=2 y la cola permanecen
trazables; las etiquetas pendientes son NULL y se documenta el motivo.
La diferencia frente a la tasa nacional del mismo intervalo/sexo se guarda
como descriptor, calculado antes de seleccionar soporte, sin añadir una
tercera característica redundante.

SSE y Davies–Bouldin usan todo el entrenamiento. Silhouette usa hasta
1,200 anclas reproducibles, cada una frente a todos los puntos; conserva
su error de aproximación por muestreo. No construye distancias B n×n.
--anchor-count modifica precisión/coste de esa métrica, sin muestrear el
ajuste. Se reutiliza el codo geométrico del piloto territorial y se evalúa
estabilidad de semillas, escalas, estratos y cola sobre segmentos comunes.

Datos: `data/processed/demographic_pilot/`; informe:
`analysis/reports/demographic_pilot.md`; gráficas:
`analysis/charts/demographic_pilot/`. Cada contexto incluye copias de
características, metadatos, pendientes, etiquetas con claves, anclas,
parámetros, métricas e interpretación demográfica por ajuste. Los destinos
existentes se protegen; repetir con --output, --charts y --report nuevos.
No ejecuta Ward, DBSCAN o K-Medoids, no elige K ni perfiles definitivos.

--review-existing verifica fuentes y resultados de esta entrega y regenera
su informe y gráficos de composición sin reajustar modelos. No permite
editar informes anteriores; los parámetros y hashes se conservan en el
manifiesto y sólo se restaura _SUCCESS tras verificar la revisión.

## Comparación de participación absoluta y relativa · 2024

```powershell
.venv/Scripts/python.exe analysis/scripts/compare_demographic_features.py
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_compare_demographic_features.py
```

Compara edad media nominal + participación observada (A) con edad media
nominal + diferencia nacional de su intervalo/sexo (B), en life_stage y
broad. Reutiliza las referencias del piloto; la población elegible es
exactamente la misma A/B, conservando todas las filas originales y NULL.
Los StandardScaler se ajustan sin pesos sólo al principal compartido y
se mantienen fijos para comparar pesos y sensibilidad NS. El entrenamiento
usa peso uno por segmento o peso total uno por municipio representado;
LN sólo tiene un diagnóstico descriptivo, sin ajustar modelos con ese peso.

K=4/5 son candidatos y K=6 sensibilidad. Cada semilla 17/42/2024 usa diez
arranques comunes: mitad originados en cada representación, con los mismos
índices iniciales al comparar geometrías y pesos. Sólo se ejecuta K-Means
con centroides ponderados. SSE y centroides se contrastan mediante groupby
independiente del algoritmo y pruebas exhaustivas/replicación de pesos.
Si scikit-learn está instalado se activa además su validación; si falta,
se documentan importación y sondeos pip --dry-run, sin instalar paquetes.

La estabilidad usa 30 submuestras del 80 % de los municipios originales,
sin reemplazo, compartidas entre representaciones, pesos, K y esquemas.
Cada municipio conserva juntos todos sus segmentos elegibles. Se reajustan
escaladores sólo dentro de la muestra y se evalúan asignaciones en municipios
no usados para el ajuste, manteniendo fija la referencia nacional previa.
--replicates, --n-init (par) y --anchor-count permiten controlar los costes;
el último sólo modifica la aproximación de Silhouette, nunca el ajuste.

Resultados: `data/processed/demographic_representation_comparison/`;
gráficas: `analysis/charts/demographic_representation_comparison/`;
informe: `analysis/reports/demographic_representation_comparison.md`.
Los destinos existentes se rechazan: para repetir usar --output, --charts y
--report nuevos. No se eligen perfiles definitivos ni se ejecutan K-Medoids,
Ward o DBSCAN; no se modifican los informes o matrices anteriores.

## Separación geométrica y evaluación ampliada de K

```powershell
.venv/Scripts/python.exe analysis/scripts/evaluate_cluster_separation.py
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_evaluate_cluster_separation.py
```

Reutiliza life_stage/2024, los 22,282 segmentos elegibles, referencias y
StandardScaler de la comparación A/B. Repite K=2…10 con peso por segmento,
tres semillas y diez arranques comunes, comprobando K=4/5/6 contra el
experimento anterior. No cambia ninguna matriz previa ni ajusta otros
algoritmos. El codo geométrico conserva sus controles de escala de ejes.

Silhouette individual es exacto para la solución de menor SSE de cada K:
recorre distancias por bloques, sin asignar N×N, y comparte cada bloque
entre particiones. Conserva aparte la aproximación de 1,200 anclas para
las tres semillas. --distance-block-size controla memoria del cálculo
exacto; --anchor-count sólo afecta las métricas aproximadas por semilla.

Para A/B y K=4/5 guarda centroides y fronteras analíticas en coordenadas
estandarizadas, Silhouette por segmento/cluster, primer/segundo centroide,
margen (d2−d1)/d2 y composición demográfica de fronteras. Las banderas son
descriptivas y no se interpretan como probabilidades o filtros de datos.

Revisa las tres peores muestras municipales por ARI OOB de B4/B5/A5.
Recupera centroides de las etiquetas de entrenamiento guardadas sin volver
a ajustar, valida SSE/asignaciones, y compara OOB y todos los elegibles
por separado. Lleva los centroides a una escala común y conserva la métrica
propia de cada remuestra al representar sus fronteras. --worst-cases permite
ampliar el número de casos revisados, sin volver a entrenar las remuestras.

Datos: `data/processed/cluster_separation_review/`; informe:
`analysis/reports/cluster_separation_review.md`; gráficos:
`analysis/charts/cluster_separation_review/`. Las referencias originales,
pendientes y experimentos se conservan. Los destinos existentes se rechazan;
otra ejecución requiere --output, --charts y --report nuevos. No se fijan
perfiles definitivos ni K y no se ejecutan K-Medoids, Ward o DBSCAN.
