# Lectura de perfiles y exportación de comparaciones

Se revisa la comunicación de las 36 fichas y se añade descarga de comparaciones de dos o tres perfiles en las seis elecciones. No se modifican datos publicados, conteos, tasas validadas, referencias, asignaciones V1 ni investigaciones V2/V2.1. Las nuevas diferencias y textos son descriptores de esos valores, sin nuevos modelos o servicios externos.

## Auditoría editorial

| Contenido anterior | Nivel y decisión |
| --- | --- |
| Tres indicadores repetidos en otra gráfica general | Principal: se conservan los tres KPI y se retira la gráfica duplicada. |
| Párrafos históricos que enumeraban tasas sin contraste | Principal: cuatro hallazgos con título, diferencia concreta, explicación y contexto. |
| Frases fijas de 2024 y superlativos al elegir otras fichas | Los hallazgos del detalle y exportación se construyen con sus valores propios en todas las elecciones; se retira la tabla de lecturas fijas. Las estadísticas/editoriales fuente se conservan intactas. |
| Brechas completas repetidas arriba y debajo de las gráficas | Principal: explicación arriba; gráficas como evidencia, con una ayuda breve sobre sus bases. |
| Fórmulas, denominadores y conteos | Secundario: «Cómo se calcularon estos datos», con tabla conjunta y ayuda de referencia/pp. |
| Heterogeneidad, NS, segmentos pequeños y cobertura | Secundario: «Cobertura y calidad de la información». El hallazgo de variación resume el resultado, sin ocultar sus límites. |
| Rutas, hashes, causalidad y comparabilidad histórica | Secundario: «Fuentes y limitaciones», accesible con teclado. |
| Mensajes repetidos sobre códigos de sexo | Una denominación compartida y una explicación por elección junto a la dimensión afectada. Los códigos permanecen sólo en contratos/datos internos o documentación metodológica. |
| Tarjetas estiradas y encabezados de comparación altos | `align-items: start`, eliminación de altura mínima del encabezado y espaciado menor; tipografía y paletas conservadas. |

La referencia sigue definida junto a sus indicadores; la tasa usa registros especificados y lo no especificado no es abstención. Las celdas sin información o con soporte reducido mantienen su aviso cerca de su gráfica. La metodología sigue disponible, no eliminada.

## Denominaciones verificadas

Se revisó `data/processed/participamx_multiyear/metadata/source_dictionaries.json`, línea `SEXO` de cada elección:

- 2009, 2012, 2015, 2018 y 2021: Hombres y Mujeres. Mensaje público: «La fuente de esta elección no incluye un desglose para personas no binarias».
- 2024: Hombres, Mujeres y No binario. Esta última categoría sigue complementaria por soporte; no se incorpora ficticiamente a las fichas H/M.

`profileLanguage.ts` centraliza esas categorías y mensajes. La ausencia de una clasificación no significa cero personas. Dashboard y Atlas ya usan «No binario» y no necesitaron cambios. Los JSON fuente conservan códigos y textos originales; los componentes no muestran su explicación técnica en la lectura pública. El ID individual se conserva en metadatos PDF y atributos internos, no como rótulo de lectura.

## Reglas de interpretación

`profileInsights.ts` produce cuatro hallazgos deterministas por perfil/año:

1. **Nivel relativo:** tasa, referencia y diferencia original. Una distancia de hasta 2 pp se describe como cercana a su referencia, conservando el diagnóstico previo y sin reclasificar.
2. **Sexo:** resta de tasas de mujeres/hombres con soporte. Se muestra magnitud y dirección; menos de 1 pp se describe como cercanía, no como una diferencia extraordinaria.
3. **Sección:** si las tres tasas con soporte difieren menos de 1 pp, se explica su cercanía. En los demás casos se usa el contraste rural–urbano fijo, no una búsqueda automática del máximo. Mixta continúa visible en las gráficas. Una tasa o categoría faltante limita sólo su contraste.
4. **Variación interna:** cantidad y proporción de cruces con soporte que cambian de signo respecto al agregado original. No se presenta como personas que cambiaron de conducta, ni incluye cruces sin soporte en ese denominador.

El umbral de 1 pp es **una regla editorial explícita**, no significación, incertidumbre estimada ni un nuevo filtro. Las diferencias se calculan con proporciones originales antes del redondeo. No se atribuyen necesidades, motivaciones o causas.

`comparisonInsights` añade cuatro conclusiones: nivel absoluto y contexto etario común/distinto; distancia frente a referencias propias; brechas internas por sexo, rangos de tasas entre fichas y composición femenina; contraste rural–urbano y composición urbana en cada ficha. Los empates no eligen un ganador arbitrario. Las limitaciones explican las bases, NS, soporte y municipios superpuestos. Las conclusiones dependen de los perfiles/año recibidos y cambian con ellos.

## Exportaciones

Los botones «Descargar comparación PDF» y «Descargar comparación PNG» se habilitan con dos o tres fichas verificadas de la elección activa. Conservan IDs, año, pestaña y medida; indican generación, éxito o error recuperable. Si falla la verificación, no generan un archivo con datos de otra elección.

Se reutilizan jsPDF 4.2.1, Canvas, paletas, plan de dibujo, renderizadores y guardas de `profileExport.ts`. **No hay dependencias nuevas.** `comparisonExport.ts` añade las plantillas, no otro sistema de capturas. No se captura el DOM ni se usan servicios externos.

- **PDF:** tres páginas A4 verticales, texto seleccionable. Primera: contexto y tabla general con conteos/cobertura. Segunda: participación y composición por sexo y U/R/M, con escala común. Tercera: cuatro conclusiones, fuente, bases y límites. Siempre incluye todas las vistas, no sólo la pestaña activa.
- **PNG:** una infografía de 1600×2357 píxeles, independiente del viewport y del tema. Incluye nombres/edades, indicadores, nominal/municipios, las dos medidas por sexo y U/R/M, tres conclusiones, fuente y límites. No concatena las tres páginas del PDF. La tasa y referencia propias permanecen visibles aunque se omita el desarrollo narrativo completo de referencias.
- **Individuales:** se conserva la plantilla compartida de dos páginas A4 y PNG de 1600×4526. Los cuatro hallazgos nuevos se muestran con fuente y metodología, y se retiran códigos técnicos de los rótulos públicos. Permanecen año, cifras y procedencia.

Los nombres de archivo incluyen los perfiles reales seleccionados y el año, por ejemplo `participamx_comparacion_01_jovenes_mayor_02_jovenes_menor_2009.pdf`. La numeración estable sólo identifica las fichas; no implica orden estadístico. Las descargas siguen siendo nacionales, aunque se consulte contexto estatal.

## Validación y ejemplos

```powershell
npm.cmd run typecheck
npm.cmd run build
node --experimental-strip-types --test scripts/profile-insights.test.mjs scripts/historical-profiles.test.mjs scripts/profile-workflows.test.mjs scripts/profiles-enriched.test.mjs scripts/statistics-presentation.test.mjs
node scripts/check-comparison-exports-ui.mjs
node scripts/check-historical-profiles-ui.mjs
node scripts/check-profiles-ui.mjs
.venv_pattern_algorithms/Scripts/python.exe -B scripts/validate_comparison_exports.py
.venv_pattern_algorithms/Scripts/python.exe -B scripts/validate_historical_profile_exports.py
```

Las 88 pruebas Node comprueban los diccionarios, reglas de cercanía/soporte, ceros/ausencias, hallazgos de las 36 fichas y disposición de las **210 selecciones posibles**: 15 pares y 20 ternas por elección, en PDF y PNG. No equivalen a renderizar 420 archivos en Chrome: allí se generan tres selecciones por año (misma edad, distinta edad y tres perfiles), en ambos formatos, **36 archivos comparativos**. Además se descargan nuevamente las **72 exportaciones individuales**.

Chrome comprueba selección/pestaña/medida tras exportar y cambiar año, botones deshabilitados con cero/una ficha, un fallo de Canvas recuperable, textos públicos sin códigos, desplegables, alineación, temas y anchos 1480/950/390/320. La regresión anterior comprueba foco, apertura con Enter, contraste y carga/error/reintento.

PyMuPDF y Pillow se usan sólo desde la caché de validación existente. El lector independiente comprueba 18 PDF comparativos, 54 páginas, cifras/años, texto seleccionable, márgenes y ausencia de solapamiento textual; los 18 PNG se comprueban por dimensiones, opacidad y paletas. Las 36 fichas individuales se verifican de nuevo. Se inspeccionan visualmente PDF y PNG de 2009, 2018 y 2024, incluida una terna. [Muestras y resultados](evidence/profile_reading_and_comparison/README.md).

La comparación por SHA-256 de **3,044 archivos protegidos** no detecta cambios: datos públicos, derivados multianuales, investigaciones V2/V2.1, componentes de Atlas/Dashboard y documentación analítica. No se regenera ningún archivo estadístico.

## Archivos y límites

- Nuevos componentes/helpers: `profileLanguage.ts`, `profileInsights.ts`, `ComparisonExportButtons.tsx`, `comparisonExport.ts`, en `src/features/profiles/`.
- Integraciones: `EnrichedProfiles.tsx`, `EnrichedProfileDetail.tsx`, `ProfileComparePanel.tsx`, `profilePresentation.ts`, `profileExport.ts`; estilos en `src/styles/profiles-enriched.css`.
- Pruebas nuevas: `scripts/profile-insights.test.mjs`, `check-comparison-exports-ui.mjs`, `validate_comparison_exports.py`. Se ajustan las expectativas de códigos/IDs visibles de las pruebas anteriores, manteniendo sus comprobaciones numéricas.
- Documentación: este documento y enlaces de continuidad en los documentos de perfiles/exportación existentes. No se sobrescriben informes de investigación ni datos.

Pendientes: pruebas de comprensión con ciudadanía, revisión editorial/electoral de las reglas de lectura, dispositivos físicos, lectores de pantalla y otros navegadores. No se afirma PDF/UA. Tasas agregadas y referencias no identifican preferencias individuales, causalidad o efectos de una intervención. No se modifican estadísticas, fuentes, V1/V2/V2.1, Atlas, Dashboard o Laboratorio; no se crean commits, push, merges o PR.
