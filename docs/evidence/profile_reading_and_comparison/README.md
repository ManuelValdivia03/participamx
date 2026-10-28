# Comparaciones descargadas y detalle simplificado

Evidencia local del 28 de octubre de 2026. Los PDF y PNG de esta carpeta proceden de los botones del comparador en Chrome. No son capturas de la interfaz. Los PNG miden 1600×2357; los PDF tienen tres páginas A4 con texto seleccionable.

| Caso | PDF completo | PNG resumido | Vista del PDF |
| --- | --- | --- | --- |
| 2009 · dos perfiles jóvenes | [PDF](participamx_comparacion_01_jovenes_mayor_02_jovenes_menor_2009.pdf) | [PNG](participamx_comparacion_01_jovenes_mayor_02_jovenes_menor_2009.png) | [Conclusiones](pdf_2009_page_3.png) |
| 2018 · jóvenes/adultos | [PDF](participamx_comparacion_01_jovenes_mayor_04_adultos_menor_2018.pdf) | [PNG](participamx_comparacion_01_jovenes_mayor_04_adultos_menor_2018.png) | [Sexo y sección](pdf_2018_page_2.png) |
| 2024 · tres perfiles | [PDF](participamx_comparacion_01_jovenes_mayor_04_adultos_menor_05_mayores_mayor_2024.pdf) | [PNG](participamx_comparacion_01_jovenes_mayor_04_adultos_menor_05_mayores_mayor_2024.png) | [Conclusiones](pdf_2024_page_3.png) |

Las vistas PDF se renderizaron con PyMuPDF, independiente de jsPDF. Se inspeccionaron los tres casos y sus PNG reales. Los contrastes describen registros agregados, no personas individuales o causas.

- [Detalle de 2009](detail-2009.png): cuatro hallazgos, gráficas sin alturas igualadas y tres bloques metodológicos plegados. El foco del título permanece visible.
- [Comparador móvil](comparison-mobile.png): botones de descarga y desplazamiento local de columnas. Es un viewport emulado, no un dispositivo físico.
- [Recorrido Chrome](results.json): 18 selecciones (tres casos por cada elección) y 36 descargas comparativas; selección/pestaña/medida conservadas, error recuperable y responsive.
- [Lector independiente](independent-validation.json): 54 páginas PDF con cifras/años, texto seleccionable, márgenes y ausencia de solapamientos; 18 imágenes con dimensiones y paletas comprobadas.
- [Regresión individual](individual-export-validation.json): 36 PDF y 36 PNG con valores correctos tras la revisión editorial.
- [Integridad](integrity-result.json): 3,044 archivos anteriores sin cambios.

Los archivos completos de prueba están en `node_modules/.cache/comparison-exports-ui/` e `historical-profiles-ui/`. Las rutas absolutas del informe identifican la caché de esa ejecución. Las pruebas unitarias de disposición cubren las 210 selecciones posibles, aparte de estos archivos reales.

Consulta [reglas de interpretación, auditoría editorial, archivos y reproducción](../../profile_reading_and_comparison_exports.md).
