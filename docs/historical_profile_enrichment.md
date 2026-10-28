# Perfiles históricos completos y comparación persistente

La revisión posterior de textos, hallazgos deterministas y exportación de comparaciones está en [Lectura y exportación de comparaciones](profile_reading_and_comparison_exports.md). La cobertura y los derivados históricos descritos aquí permanecen intactos.

La integración amplía las seis fichas nacionales a 2009, 2012, 2015, 2018, 2021 y 2024. Conserva las definiciones, nombres e identificadores V1; no ejecuta clustering ni modifica investigaciones anteriores. Cada elección tiene cifras, referencias, cruces, textos y descargas propios.

## Auditoría y matriz de cobertura

Antes de cambiar React se comprobó el esquema real de los Parquet multianuales. `segments.parquet` conserva las pertenencias V1 y los conteos por municipio/banda/sexo. `section_segments.parquet` conserva además TIPOSEC; no hace falta leer CSV ni Parquet de registros originales. Los archivos por elección ya estaban completos y validados. Sólo faltaba agregar sus cruces por perfil y adaptarlos al contrato público.

| Elección | V1 | Edad | Sexo en fichas | U/R/M | Composición LN | Participación | LN/SV/NV/NS | Sexo × U/R/M | Contexto territorial | Exportación actual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2009 · intermedia | 6 | 3 bandas | 0/1 | Sí | Sí | Sí | Sí | Sí | Sí | 6 PDF + 6 PNG |
| 2012 · presidencial | 6 | 3 bandas | 0/1 | Sí | Sí | Sí | Sí | Sí | Sí | 6 PDF + 6 PNG |
| 2015 · intermedia | 6 | 3 bandas | 0/1 | Sí | Sí | Sí | Sí | Sí | Sí | 6 PDF + 6 PNG |
| 2018 · presidencial | 6 | 3 bandas | 0/1 | Sí | Sí | Sí | Sí | Sí | Sí | 6 PDF + 6 PNG |
| 2021 · intermedia | 6 | 3 bandas | 0/1 | Sí | Sí | Sí | Sí | Sí | Sí | 6 PDF + 6 PNG |
| 2024 · presidencial | 6 | 3 bandas | 0/1; 2 complementario | Sí | Sí | Sí | Sí | Sí | Sí | 6 PDF + 6 PNG |

Las tres bandas V1 permanecen 18–34, 35–59 y 60–100. Los agregados completos conservan 101+ y, en 2024, SEXO=2. Antes de 2024 esa categoría no está registrada: no equivale a cero personas. La cobertura de una dimensión no garantiza soporte en cada subsegmento municipal.

| Elección | Segmentos originales | Segmentos V1 con soporte | Municipios representados | LN en fichas | % LN anual | Hijos U/R/M presentes | Hijos con soporte reducido | Hijos con tasa indefinida |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2009 | 18,545 | 14,096 | 2,398 | 77,344,901 | 99.8233 % | 33,290 | 2,671 | 67 |
| 2012 | 17,313 | 14,060 | 2,397 | 76,429,609 | 99.9198 % | 33,169 | 2,751 | 22 |
| 2015 | 17,549 | 13,934 | 2,369 | 83,429,708 | 99.8399 % | 33,103 | 2,766 | 262 |
| 2018 | 17,451 | 14,045 | 2,386 | 88,977,633 | 99.8358 % | 33,338 | 2,649 | 200 |
| 2021 | 17,771 | 14,148 | 2,398 | 93,329,226 | 99.7831 % | 33,553 | 2,306 | 164 |
| 2024 | 17,735 | 14,190 | 2,402 | 98,203,780 | 99.8713 % | 33,709 | 2,239 | 183 |

Los hijos indefinidos se incluyen entre los de soporte reducido; no se suman ambas columnas. Todos los hijos de un segmento V1 asignado contribuyen a sus totales, incluso si no superan soporte individual. No se reclasifican esos hijos. Los municipios pueden aparecer en varias fichas y no se suman entre perfiles. El porcentaje usa todo el LN anual observado, incluidos complementos y pendientes, no sólo el núcleo H/M.

## Fuentes, reglas y conciliación

`scripts/build_historical_profile_enrichment.py` utiliza por elección los Parquet `segments`, `section_segments` y `national_references`, además de `profiles.json`, bajo `data/processed/participamx_multiyear/elections/YEAR/`. Verifica `_SUCCESS`, el estado del manifiesto y hashes de cada fuente contra su checkpoint anual. Contrasta también el V1 público que usa React.

Se comprueba primero la clasificación V1 del padre mediante productos cruzados de enteros Python: SV local × D nacional frente a SV nacional × D local. Se exige H/M, 18–100, LN≥100, D=SV+NV≥100 y filas fuente≥5. Los empates exactos y tasas indefinidas no se fuerzan a favorable/desfavorable. Se verifica igualdad con las pertenencias guardadas; después los hijos U/R/M heredan ese ID, sin clasificarse por separado.

La referencia nacional de cada elección/banda/sexo se valida sumando todos los padres antes del soporte. Las tasas agregadas utilizan suma SV/suma D. La referencia de ficha, sexo o sección combina las referencias de edad/sexo mediante sus D locales; **no es una nueva referencia ajustada por U/R/M**. La composición usa LN de categoría/LN del perfil. NS no se suma a NV.

Resultados: **744,898 comprobaciones aditivas** entre padres/hijos y referencias, más **252 conciliaciones perfil/año/campo** para siete conteos originales, sin diferencias. Se verifican además bases, tasas, referencias, composiciones, unicidad y ausencia de expansión en las uniones. Cada desglose sexo, U/R/M y conjunto concilia con V1. El cálculo independiente de 2024 reproduce conteos, cruces y calidad publicados; se reutiliza literalmente su payload anterior, incluida la edición revisada. `public/data/profiles/enriched-2024.json` no se sobrescribe.

Se contrastaron hashes de **3,029 archivos anteriores** sin cambios: resultados multianuales, datos públicos existentes, V2/V2.1, componentes del Atlas y Dashboard y documentación analítica de perfiles. Los cinco payloads públicos nuevos pesan aproximadamente 35–36 KB cada uno; no se descargan conjuntamente ni requieren nuevas dependencias.

Los cruces agregados tienen `defined`, `low_support`, `undefined` o `missing`. Ausencia implica conteos NULL; una celda presente con cero conserva ese cero. Una agregación nacional con soporte puede reunir hijos con denominadores pequeños; `availableCells`, `eligibleCells` y `undefinedCells` hacen explícita esa diferencia. Los cambios de signo internos se calculan sólo en hijos con soporte frente a la misma referencia de edad/sexo de su padre. No son pruebas de causalidad ni nuevos perfiles.

## Derivados e idempotencia

- `data/processed/profile_enrichment_history/coverage.json`: matriz de auditoría, cobertura y hashes de entradas por año.
- `reconciliation.json`: 252 conciliaciones con diferencia cero.
- `elections/YEAR/enriched.json`: resultados anuales separados de las investigaciones previas.
- `manifest.json` y `_SUCCESS`: fuentes, hashes de productos, estado validado, cero lecturas CSV y cero modelos.
- `public/data/profiles/enriched-2009.json` a `enriched-2021.json`: cinco archivos nuevos, pequeños y solicitados sólo para el año activo; 2024 reutiliza el existente.

El script compara los destinos existentes y no los modifica: repetir produce el mismo contenido o falla si algo difiere. `--audit-only` ejecuta auditoría y conciliación sin publicar los payloads; `--check` exige que todos los derivados ya existan y coincidan. Se lee una elección agregada por vez, sin matrices de distancias ni registros individuales.

## Interfaz, comparación y textos

`ProfileInteractionContext` conserva únicamente IDs estables del detalle/comparación, pestaña y medida. Vive por encima de la carga anual. Los objetos estadísticos se buscan nuevamente en el dataset validado de la elección activa. Al cambiar de año se desmontan las cifras anteriores, se muestra carga y se conservan las selecciones; una respuesta cancelada no sustituye el año nuevo. Un fallo del enriquecimiento deja V1 disponible con reintento, manteniendo IDs y pestaña; los desgloses no verificados se ocultan.

El comparador conserva dos o tres perfiles al alternar año, catálogo y detalle. Mantiene Resumen/Sexo/Tipo de sección electoral y Participación/Composición. Resumen incluye lista nominal. Si falta una categoría se indica en esa celda, sin ocultar los otros resultados ni inventar ceros.

`getProfileReading` conserva los textos revisados de 2024 y usa los textos del payload anual para elecciones históricas. Describen tasas propias por sexo/U/R/M y heterogeneidad observable, sin atribuir necesidades o motivaciones. No se copian superlativos de 2024.

El hallazgo transversal V2.1 se muestra exclusivamente con 2024. Los payloads históricos llevan `transversalFinding: null` y el contrato rechaza un hallazgo de 2024 añadido a otra elección. No se ejecuta una investigación histórica de interacciones.

## Exportaciones

Se reutiliza `profileExport.ts`, jsPDF 4.2.1 y Canvas nativo. No hay dependencias nuevas. La plantilla compartida genera PDF A4 de dos páginas con texto seleccionable y PNG de 1600×4526, independiente del viewport. Usa cifras/textos de la ficha activa, año en encabezados, pies, metadatos y nombre de archivo. Rechaza mezclas de año, ID o población y datos no verificados. Las descargas siguen siendo nacionales, aunque se consulte contexto estatal.

Se comprobaron las **72 descargas reales** desde los botones en Chrome. Un lector independiente verificó las 72 páginas de los 36 PDF: nombres, años, texto seleccionable, tasas/referencias/diferencias, composiciones, conteos, márgenes y páginas con contenido. Pillow comprobó las 36 imágenes y sus dimensiones/opacidad. Se abrieron visualmente PDF renderizados y PNG reales de 2009, 2018 y 2024. [Ejemplos y capturas](evidence/historical_profiles/README.md).

## Pruebas y reproducción

```powershell
.venv_pattern_algorithms/Scripts/python.exe -B scripts/build_historical_profile_enrichment.py --audit-only
.venv_pattern_algorithms/Scripts/python.exe -B scripts/build_historical_profile_enrichment.py
.venv_pattern_algorithms/Scripts/python.exe -B scripts/build_historical_profile_enrichment.py --check
.venv_pattern_algorithms/Scripts/python.exe -B -m unittest discover -s scripts -p test_historical_profile_enrichment.py
npm.cmd run typecheck
npm.cmd run build
node --experimental-strip-types --test scripts/historical-profiles.test.mjs scripts/profile-workflows.test.mjs scripts/profiles-enriched.test.mjs scripts/statistics-presentation.test.mjs
node scripts/check-historical-profiles-ui.mjs
node scripts/check-profiles-ui.mjs
.venv_pattern_algorithms/Scripts/python.exe -B scripts/validate_historical_profile_exports.py
```

El lector opcional usa la caché PyMuPDF ya documentada en selectores/exportaciones, sin cambiar entornos analíticos. Las 68 pruebas Node y cuatro Python pasan. Chrome cubre la secuencia 2024→2009→2012→2015→2018→2021→2024, pestaña/medida persistentes, cambios rápidos con respuesta demorada, errores/reintentos, detalle/catálogo, temas, teclado y anchos 1480/950/390/320. La regresión anterior de perfiles comprueba también tres fichas, foco y contraste.

## Archivos y límites

Cambios React: `types.ts`, `profileEnrichment.ts`, `profilesAdapter.ts`, `RealProfilesPage.tsx`, nuevo `ProfileInteractionContext.tsx`, `EnrichedProfiles.tsx`, `EnrichedProfileDetail.tsx`, `ProfileComparePanel.tsx`, `profilePresentation.ts`, `profileExport.ts` y `ProfileExportButtons.tsx`, todos en `src/features/profiles/`. Procesamiento y pruebas: los cinco scripts nuevos de esta entrega y actualización de expectativas históricas en los recorridos existentes. Se actualizan los dos documentos de integración y este documento, sin sobrescribir informes de investigación.

Las elecciones son cortes transversales, no seguimiento de personas; se diferencian presidenciales e intermedias. No hay correspondencia territorial validada que garantice límites municipales constantes. Cobertura nominal alta no asegura representatividad territorial ni ausencia de sesgo de captura/NS. U/R/M no identifica residencia individual. Las propuestas institucionales y el Laboratorio permanecen intactos.

Pendientes: pruebas con dispositivos físicos, lectores de pantalla y otros navegadores; revisión electoral/editorial de los nuevos textos descriptivos. No se afirma PDF/UA ni eficacia de acciones cívicas. No se habilitan fichas enriquecidas estatales. No se modifican V1, V2, V2.1, fuentes originales, Atlas, Dashboard ni clasificaciones; no se crean commits, push, merges o PR.
