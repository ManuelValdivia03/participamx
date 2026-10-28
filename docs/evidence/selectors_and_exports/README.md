# Evidencia de selectores y exportación de perfiles

Capturas y archivos reales de la validación local de Chrome, 28 de octubre de 2026. Los datos electorales y sus definiciones permanecen intactos. Las dimensiones móviles corresponden a emulación del viewport; no sustituyen pruebas en dispositivos físicos.

| Evidencia | Qué permite revisar |
| --- | --- |
| [Dashboard · Chihuahua 2024](dashboard-chihuahua-2024.png) | Búsqueda de entidad, selector horizontal y cifras por edad/sexo del territorio seleccionado. |
| [Perfiles · selector móvil](perfiles-mobile-selectors.png) | Reflujo y visibilidad de las seis elecciones sin desbordamiento de página. |
| [Contexto de Chihuahua](profiles-chihuahua-context.png) | Tabla estatal separada de las seis fichas nacionales, con referencia nacional explícita. |
| [Detalle en tema oscuro](profile-export-buttons-dark.png) | Botones PDF/PNG próximos al encabezado del perfil. |
| [PDF descargado](participamx_perfil_01_jovenes_mayor_participacion_2024.pdf) | Dos páginas A4, texto seleccionable, cifras, gráficas, fuente y limitaciones. |
| [PNG descargado](participamx_perfil_01_jovenes_mayor_participacion_2024.png) | Plantilla compartida, 1600 × 4526 píxeles, independiente del viewport y del tema. |
| [PDF · página 1 renderizada](pdf_preview_page_1.png), [página 2](pdf_preview_page_2.png) | Inspección visual mediante un lector independiente de jsPDF. |
| [Validación independiente](independent-export-validation.json) | Seis PDF, doce páginas, texto/márgenes y seis PNG comprobados. |
| [Recorrido del navegador](results.json) | Escenarios estatales, teclado, persistencia, errores, doce descargas y responsive. Las rutas de caché son referencias locales de esa ejecución. |

El PDF y PNG de muestra proceden de los botones de descarga. No son capturas de la interfaz. Las otras diez descargas permanecen en `node_modules/.cache/profile-workflows-ui/downloads/`. El PNG es idéntico entre los temas claro y oscuro, conforme al recorrido automatizado.

La exportación enriquecida está disponible para las fichas nacionales verificadas de 2024. El contexto estatal no cambia la definición ni el contenido de esas fichas. Para años anteriores permanece deshabilitada con explicación.

Consulta [implementación, dependencias, pruebas y límites](../../selectors_and_profile_exports.md).
