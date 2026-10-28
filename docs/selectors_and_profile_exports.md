# Selectores compartidos, contexto territorial y descargas de perfiles

Las comparaciones completas PDF/PNG y la revisión editorial posterior se documentan en [Lectura y exportación de comparaciones](profile_reading_and_comparison_exports.md). Reutilizan los renderizadores descritos aquí, sin nuevas dependencias.

La ampliación posterior a **las seis elecciones** está documentada en [Perfiles históricos y comparación persistente](historical_profile_enrichment.md), con cobertura y conciliación por año. Las capturas de la entrega inicial se conservan como evidencia de esa versión; las muestras actuales están enlazadas en el documento histórico.

## Resultado por fase

| Fases | Resultado |
| --- | --- |
| Revisión y nombres | Se conservan los datos existentes. Metodología, Dashboard, Atlas, catálogo, detalle, comparador y exportaciones usan el mapa de nombres acordados de `profilePresentation.ts`. Los seis identificadores técnicos se mantienen. |
| Selector de elecciones | Un único `ElectionSelector` controlado se utiliza en Dashboard, Perfiles y Atlas. `ElectionTimeline` queda como alias compatible del Atlas. Se mantienen los seis años y sus tipos, el estado global y el comportamiento de teclado. |
| Búsqueda de entidades | `StateSearch` permite elegir México o una de las 32 entidades. Dashboard y Perfiles usan el mismo control; comparte la normalización de acentos y consultas del buscador del Atlas. El Atlas conserva su búsqueda completa de estados y municipios. |
| Edad y sexo | Dashboard muestra el desglose del territorio y año elegidos. Las filas y los títulos cambian conjuntamente; una falta de información no utiliza resultados nacionales como sustituto. |
| Contexto en Perfiles | La tabla estatal muestra datos ya publicados de participación, referencia nacional y composición nominal por perfil. Se presenta separada de las fichas nacionales. No cambia las reglas, las referencias ni los cruces enriquecidos de las seis fichas. |
| PDF y PNG | Cada detalle nacional verificado de las seis elecciones permite descargar ambos formatos. PDF A4 vertical de dos páginas con texto seleccionable; PNG de 1600 × 4526 píxeles. Ambos utilizan la misma plantilla y los mismos datos que consume la ficha. |
| Claridad, validación y documentación | Explicaciones breves, seis nombres con sus edades en Metodología, pruebas de teclado/temas/reflujo, contraste con fuentes y validación independiente de archivos descargados. |

## Fuentes y cobertura

- **Indicadores de Dashboard:** los adaptadores existentes continúan leyendo los resultados nacionales y estatales de `public/data/participamx_multiyear/elections/YEAR/`. La selección estatal cambia cifras, serie temporal y proporciones de lista nominal por perfil, no sólo el título.
- **Edad y sexo nacional:** se conserva `age_statistics.json` por elección y su agregación previa 18–34, 35–59 y 60–100. Se suman LN/SV/NV antes de calcular SV/(SV+NV).
- **Edad y sexo estatal:** se reutilizan los resúmenes validados de `public/data/territorial/summaries/YEAR/STATE.json`, con sus segmentos y complementos. Existen recursos para México y 32 entidades en las seis elecciones. Se seleccionan las mismas tres bandas; no se introducen edades exactas ficticias ni se incluyen 101+ en 60–100.
- **Soporte:** la vista nacional conserva la alerta de edades exactas de su fuente original. La estatal utiliza el soporte de las bandas agregadas del resumen existente. Esos diagnósticos pertenecen a niveles distintos; la interfaz lo explica y no los equipara. No se cambian umbrales.
- **Contexto de perfiles:** `states.json` aporta el catálogo de entidades y `state_profiles.json` las filas de composición y participación disponibles por año/entidad. Se validan año, claves, IDs, unicidad, conteos, denominadores y coherencia de tasas/referencias. Una categoría ausente sigue sin información.
- **Fichas enriquecidas:** los cruces por sexo y tipo de sección electoral proceden de `public/data/profiles/enriched-YEAR.json`, conciliados con V1 de su propia elección. La selección estatal no filtra ni recalcula esos archivos. La tabla contextual indica expresamente que las fichas ampliadas y sus descargas son nacionales. El hallazgo V2.1 permanece sólo en 2024.

Se verificaron 32 entidades en cada catálogo y archivo de contexto estatal de las seis elecciones. Las filas disponibles de entidad/perfil son 177 (2009), 185 (2012), 176 (2015), 183 (2018), 185 (2021) y 184 (2024): no todas las entidades tienen las seis categorías. Una fila ausente se muestra como información no disponible, sin inventar un cero.

Las solicitudes se cancelan al cambiar de territorio/año y sus respuestas se identifican por ambas claves. Un resultado anterior no se muestra bajo el título nuevo. Las ausencias, errores y tasas no definidas se conservan; no se imputan ceros ni se reasigna NS a NV. Se mantiene SEXO=2 donde está registrado, con avisos de escasez o ausencia correspondientes.

## Controles y accesibilidad

El selector de año tiene semántica `radiogroup`/`radio`, un único punto de Tab, flechas, Home y End. Las elecciones presidenciales son 2012, 2018 y 2024; las restantes son intermedias. En escritorio se ordenan en una fila y en móvil en tres columnas/dos filas. Si el contenedor resulta excepcionalmente estrecho se desplaza sólo el control, manteniendo visible la opción activa también al redimensionar. No se corta el nombre del tipo de elección ni se desborda la página.

El buscador estatal es un combobox etiquetado: filtra fragmentos y acentos, permite flechas/Enter, Escape, retorno a México y muestra la selección actual. No descarga geometrías municipales. El año se conserva al elegir una entidad; cambiar de año conserva la entidad. La llegada del índice electoral tampoco restablece un año válido ya elegido.

Metodología muestra los seis nombres acordados, banda y criterio correspondiente. «Mayor/menor» expresa posición frente a la referencia nacional comparable por edad/sexo; no máximos o mínimos absolutos del país.

## Plantilla y formatos de exportación

`profileExport.ts` construye un plan de dibujo independiente del viewport y del tema. Contiene encabezado ParticipaMX, nombre/ID/banda/año, indicadores, cobertura, composición nominal y participación por sexo, Urbana/Rural/Mixta en ese orden, comparaciones válidas, tres hallazgos, conteos, fuente y límites.

Ese plan se dibuja como texto y formas vectoriales en PDF, y sobre un Canvas de tamaño fijo en PNG. No se imprime la pantalla interactiva ni se rasteriza el DOM. Los archivos excluyen menús y botones. La plantilla usa papel claro y las paletas del Atlas: mujeres rosa, hombres azul, urbana morada, rural terracota y mixta verde. No depende del tema activo.

La fuente del PDF es Helvetica estándar; el PNG utiliza Arial/sans-serif del sistema. Los acentos se conservan y se verificaron mediante extracción del texto PDF. Se normalizan únicamente algunos símbolos tipográficos para el repertorio de la fuente, como guiones y signos de comparación; no se alteran cifras. Las tasas y diferencias se toman de los valores originales de la ficha y se redondean sólo para mostrarse.

Las dimensiones y posiciones se comprueban para evitar desbordamientos. Ambas páginas contienen información y conservan el ID y la elección. La segunda incluye los hallazgos y el detalle metodológico. El PNG concatena esas dos páginas como una infografía vertical de alta resolución.

Los botones se bloquean mientras se genera un archivo y anuncian preparación, éxito o error. Los desgloses no verificados tienen exportación deshabilitada con explicación. La función de generación rechaza mezclas de año o población, aunque se invoque directamente. Las fichas históricas verificadas utilizan sus propias cifras y textos, con el año correspondiente en el nombre de archivo y el contenido.

Nombres de archivo:

```text
participamx_perfil_01_jovenes_mayor_participacion_2024.pdf
participamx_perfil_01_jovenes_mayor_participacion_2024.png
```

Los seis números siguen el orden joven mayor/menor, adulto mayor/menor y personas mayores mayor/menor; los IDs analíticos no cambian.

## Dependencias

Se añade **`jspdf` 4.2.1**, con versión fijada y lockfile, como única dependencia directa de aplicación. Se carga dinámicamente al solicitar una descarga. Su API permite crear documentos y texto sin capturar HTML. [Documentación oficial de jsPDF](https://parallax.github.io/jsPDF/docs/jsPDF.html).

PNG usa Canvas nativo. No se instala una dependencia directa de capturas. Los módulos opcionales de captura/HTML que incluye jsPDF no se solicitan durante el flujo probado de exportación. No se añaden servidores, fuentes remotas o procesos de análisis.

Para la validación independiente se usa **PyMuPDF 1.26.7**, instalado sólo en `node_modules/.cache/pdf-render-minimal`, sin dependencias y sin cambiar los entornos analíticos. Pillow, ya disponible, comprueba el PNG. No son dependencias de producción ni intervienen en la descarga del navegador.

## Validación y evidencias

```powershell
npm.cmd run typecheck
npm.cmd run build
node --experimental-strip-types --test scripts/profile-workflows.test.mjs scripts/statistics-presentation.test.mjs scripts/profiles-enriched.test.mjs
npm.cmd run test:territorial
node scripts/check-profile-workflows-ui.mjs
node scripts/check-profiles-ui.mjs
node scripts/check-typography-ui.mjs
node scripts/check-territorial-ui.mjs
.venv_pattern_algorithms/Scripts/python.exe -B scripts/validate_profile_exports.py
```

La última comprobación requiere el visor temporal. Para prepararlo, sin alterar las dependencias de la aplicación:

```powershell
.venv_pattern_algorithms/Scripts/python.exe -m pip install --target node_modules/.cache/pdf-render-minimal PyMuPDF==1.26.7 --no-deps --only-binary=:all:
```

Pasaron TypeScript, compilación y 52 pruebas automatizadas: 25 de presentación estadística, perfiles y exportación, y 27 territoriales. Las pruebas dirigidas cubren los nombres, tipos de elección, unicidad, búsqueda, contratos estatales y seis PDF A4 reales. Se mantienen las pruebas anteriores de tasas, denominadores, perfiles, capas y cuantiles.

Chrome comprueba México 2009/2024, Chihuahua 2024, Veracruz 2021, cambio de sexo, falta temporal de desglose sin fallback nacional y reintento. También contexto estatal de perfiles, persistencia de entidad, coherencia del enriquecimiento histórico, las doce descargas de 2024 desde sus botones, igualdad del PNG entre temas y reflujo a 1480/950/390/320 px. El recorrido histórico adicional valida las 72 descargas y la selección persistente entre elecciones. Los otros recorridos verifican comparador, Atlas y teclado. Se revisaron visualmente PDF renderizados y PNG reales de 2009, 2018 y 2024.

El lector PDF independiente verifica doce páginas A4, texto seleccionable, nombres/IDs, tasas/referencias/diferencias, conteos, ausencia de controles y márgenes. Los PNG se comprueban por firma, dimensiones, opacidad y contenido. La documentación de tipografía conserva la distinción entre reflujo emulado y zoom nativo.

Muestras y capturas para revisión: [evidencia local](evidence/selectors_and_exports/). Los resultados completos y las doce descargas están en `node_modules/.cache/profile-workflows-ui/`; la validación independiente se guarda en `independent-export-validation.json`. Se contrastan por hash 1,466 archivos de datos publicados, investigación y documentación analítica, sin cambios.

## Archivos y límites

| Área | Archivos principales |
| --- | --- |
| Componentes compartidos | `src/components/ElectionSelector.tsx`, `StateSearch.tsx`, `src/styles/shared-selectors.css` |
| Estado global y Atlas | `src/context/ElectionYearContext.tsx`, alias `src/features/map/ElectionTimeline.tsx`, alias `profileLabels.ts` |
| Dashboard | `Dashboard.tsx`, `NationalAgeSex.tsx`, nombres de `fullDashboardAdapter.ts` |
| Perfiles | `RealProfilesPage.tsx`, `ProfileTerritoryContext.tsx`, `profilePresentation.ts`, `EnrichedProfileDetail.tsx`, `ProfileExportButtons.tsx`, `profileExport.ts` |
| Lectura de contexto | `src/services/profileTerritoryContext.ts` |
| Metodología | `src/features/methodology/Methodology.tsx` |
| Dependencia | `package.json`, `package-lock.json` |
| Pruebas | `scripts/profile-workflows.test.mjs`, `check-profile-workflows-ui.mjs`, `validate_profile_exports.py`; selectores actualizados de los recorridos de perfiles/tipografía |

Se exporta enriquecimiento nacional de las seis elecciones; no se exporta una ficha enriquecida estatal. La extensión histórica usa agregados propios conciliados y no simula resultados con contenido de 2024. Quedan pendientes pruebas de uso con lectores de pantalla, navegadores distintos de Chrome y dispositivos reales. No se certifica PDF/UA. No se modifican cálculos V1, investigación, fuentes del INE, clasificación U/R/M, capas, estrategias ni Laboratorio. No se crean commits, push, merges o PR.
