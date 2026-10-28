# Evidencia de perfiles históricos y exportaciones

Validación local de Chrome del 28 de octubre de 2026. Estos archivos proceden de las descargas de la aplicación, no de capturas del viewport. Las vistas PDF se renderizaron con PyMuPDF, independiente de jsPDF.

| Elección | PDF real | PNG real | Revisión del PDF |
| --- | --- | --- | --- |
| 2009 | [Descargar PDF](participamx_perfil_01_jovenes_mayor_participacion_2009.pdf) | [Ver PNG](participamx_perfil_01_jovenes_mayor_participacion_2009.png) | [Página 1](pdf_2009_page_1.png) · [Página 2](pdf_2009_page_2.png) |
| 2018 | [Descargar PDF](participamx_perfil_01_jovenes_mayor_participacion_2018.pdf) | [Ver PNG](participamx_perfil_01_jovenes_mayor_participacion_2018.png) | [Página 1](pdf_2018_page_1.png) · [Página 2](pdf_2018_page_2.png) |
| 2024 | [Descargar PDF](participamx_perfil_01_jovenes_mayor_participacion_2024.pdf) | [Ver PNG](participamx_perfil_01_jovenes_mayor_participacion_2024.png) | [Página 1](pdf_2024_page_1.png) · [Página 2](pdf_2024_page_2.png) |

Las tres muestras muestran la misma ficha V1 en elecciones diferentes, con sus propias cifras y textos. No implican seguimiento de personas o municipios con límites constantes. Los 36 PDF y 36 PNG completos permanecen en `node_modules/.cache/historical-profiles-ui/downloads/`, fuera de los archivos que descarga inicialmente la aplicación.

- [Comparador en 2009, pestaña Sexo](comparison-2009-sex.png): mismos dos IDs elegidos inicialmente en 2024, con tasas de 2009.
- [Comparador móvil](comparison-mobile.png): desplazamiento local de columnas sin desbordar la página.
- [Detalle de 2018 en tema oscuro](detail-2018.png): cifras, fuente y botones de descarga de la elección activa.
- [Recorrido automatizado](results.json): persistencia de IDs/pestaña/medida, carga, cambios rápidos, errores/reintentos, 72 descargas, teclado y tamaños de pantalla emulados.
- [Validación independiente](independent-export-validation.json): 36 combinaciones, 72 páginas PDF y 36 PNG, con cifras/años, texto seleccionable, márgenes y dimensiones comprobados.
- [Integridad](integrity-result.json): 3,029 archivos anteriores sin cambios.

Consulta la [matriz de cobertura, conciliación, implementación y limitaciones](../../historical_profile_enrichment.md). Las rutas absolutas de los resultados de prueba identifican la caché local de esa ejecución. Las capturas móviles no sustituyen pruebas en dispositivos físicos.
