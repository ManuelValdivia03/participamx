# Tipografía y lectura de estadísticas de ParticipaMX

## Alcance y auditoría

La mejora conserva la identidad morada, los títulos editoriales, las rutas de navegación y los resultados. No instala fuentes, paquetes o servicios. No cambia los cálculos, las capas, los seis perfiles, el Laboratorio ni las propuestas institucionales.

La revisión de las siete hojas previas encontró 567 declaraciones de tipografía/interlineado, incluidas **255 declaraciones de tamaño inferior a 14 px**. Son reglas CSS, a veces repetidas entre media queries, no 255 textos visibles distintos. Dashboard y Metodología tenían muchas notas y etiquetas de 8–12 px; Atlas y Perfiles tenían escalas locales más grandes pero inconsistentes. Había mezclas de Segoe UI, fuentes monoespaciadas y Georgia también en cifras y textos auxiliares.

Se migraron 386 declaraciones de tamaño/familia a tokens compartidos, conservando las otras propiedades de las hojas anteriores. No se sustituyó cada archivo ni se multiplicó el tamaño de toda la página. Los ajustes de lectura, contraste y reflujo se concentran en `src/styles/typography.css`.

## Tokens reutilizables

Los tamaños en rem respetan el tamaño de texto preferido del navegador; los equivalentes siguientes corresponden a una raíz de 16 px.

| Token | Uso | Valor |
| --- | --- | --- |
| `--font-body` | Párrafos, tablas, controles y estadísticas | Segoe UI Variable Text, Segoe UI, system-ui, alternativas del sistema |
| `--font-editorial` | Títulos editoriales conservados | Georgia, Times New Roman, serif |
| `--text-body` | Texto principal, explicaciones e inputs | 1rem / 16 px |
| `--text-body-large` | Texto principal destacado | 1.0625rem / 17 px |
| `--text-label` | Etiquetas, botones y controles compactos | .9375rem / 15 px |
| `--text-caption` | Notas, ayudas y fuentes | .875rem / 14 px |
| `--text-lead` | Introducciones | 1.125rem / 18 px |
| `--text-card-title` | Títulos de tarjetas | 20–24 px responsivos |
| `--text-section-title` | Encabezados de sección | 26–34 px responsivos |
| `--text-metric` | Indicadores de Dashboard | 28–40 px responsivos |
| `--weight-regular/medium/bold` | Jerarquía de texto | 400 / 600 / 700 |
| `--leading-body/heading` | Interlineado | 1.65 / 1.25 |
| `--tracking-label` | Rótulos cortos | .04em |
| `--reading-width` | Anchura máxima de lectura | 72ch |
| `--reading-ink/muted` | Texto principal/secundario | Variantes contrastadas para cada tema |

La fuente sans-serif usa recursos locales, con una variante variable cuando el sistema la ofrece. No se presupone que Inter o Source Sans estén instaladas ni se solicitan fuentes a terceros. Georgia conserva la estética editorial. Las cifras principales usan sans-serif y números tabulares. El lema pequeño del logotipo mantiene una excepción de 11 px; no se usa para información estadística.

Los inputs y selectores tienen al menos 16 px para evitar el zoom automático asociado a texto pequeño en móviles. Los controles tienen una altura mínima de 44 px. No hay `transform: scale()`, zoom CSS ni cambios del zoom del usuario para aumentar la fuente.

## Ajustes de los componentes

- **Dashboard:** etiquetas más grandes, mayor separación de valores y notas, contraste reforzado, tarjetas en cuatro/dos/una columnas según el espacio y filtros que se reorganizan sin recortar etiquetas. La gráfica conserva el eje 0–100 y todos sus datos; usa desplazamiento local con indicación visible cuando falta ancho y mantiene tabla y botones de años como alternativas. No se reduce la letra para hacer caber los años.
- **Metodología:** párrafos de 16 px y anchura controlada, títulos claros, definiciones sencillas y fórmulas separadas visualmente. Se mantienen los criterios de soporte, las advertencias ecológicas, la falta de correspondencia histórica y las demás limitaciones.
- **Atlas:** los estilos existentes de controles, búsqueda, leyendas, ranking, tarjetas, notas, ayuda y guía consumen los mismos tokens. Se ajusta el ancho de la etiqueta de procedencia a 320 px. La geometría y altura del mapa, paletas, capas, cuantiles y funcionamiento permanecen iguales.
- **Perfiles:** etiquetas y botones migran a la escala común; el comparador conserva sus vistas, cifras y desplazamiento local. Se explica pp al comienzo del catálogo, ficha, comparación y hallazgo transversal, sin añadir una nueva dimensión o perfil. El diagrama de puntos del hallazgo usa etiquetas HTML y posiciones relativas: los textos mantienen su tamaño al estrecharse la gráfica, a diferencia del SVG escalado anterior. Conserva exactamente sus dos valores y la escala de lectura, sin barra de progreso.
- **Navegación:** conserva enlaces y rutas. Rótulos y menús son legibles; la barra superior puede ajustar su altura y envolver contenido en vez de recortarlo.

## Convenciones estadísticas

`src/components/statisticsPresentation.ts` contiene sólo ayudas de presentación. No estima indicadores nuevos ni sustituye los adaptadores analíticos. `StatisticalHelp.tsx` ofrece un desplegable nativo accesible, reutilizado donde corresponde.

1. **Participación observada:** SV/(SV+NV). En porcentaje, `SV / (SV + NV) × 100`. La frase «De cada 100 registros…» usa el porcentaje original del indicador seleccionado y redondea únicamente su equivalente aproximado. La base son registros con condición de voto especificada, no toda la lista nominal. Los valores NULL conservan su ausencia; cero sigue siendo válido.
2. **Participación nominal:** SV/LN; su fórmula porcentual permanece visible y separada de la observada. No se usa para explicar la tasa observada.
3. **Abreviaturas:** LN = lista nominal; SV = registros con participación; NV = registros sin participación; NS = registros con condición de voto no especificada. LN es el conteo reportado en cuadernillos, no personas únicas validadas. NS no se convierte en abstención.
4. **pp = puntos porcentuales:** resta entre porcentajes; 60 % menos 55 % son 5 pp. Las diferencias existentes siguen usando valores originales; no se restan etiquetas redondeadas. El redondeo puede explicar una centésima aparente.
5. **Referencia comparable:** valor nacional de la misma elección, banda de edad y sexo. No es predicción, meta o promedio histórico. La referencia de ficha mantiene su mezcla de denominadores conforme a la metodología previa.
6. **Bases diferentes:** los porcentajes de participación, lista nominal, municipios o segmentos se nombran por separado. Un porcentaje de segmentos no es un porcentaje de personas.
7. **Dashboard estatal:** las barras existentes son proporciones de lista nominal estatal por perfil; el título ahora dice «Lista nominal por perfil». Las nacionales siguen siendo tasas, con «Participación por perfil». El indicador estatal de soporte se rotula «Lista nominal con soporte»; el nacional no publicado permanece sin información. Son aclaraciones de presentación de campos existentes.
8. **Tipo de sección electoral:** U = Urbana, R = Rural, M = Mixta. Clasifica secciones electorales y no determina la localidad o residencia individual. Se conserva el orden y las paletas existentes.

## Archivos de esta iteración

| Área | Archivos |
| --- | --- |
| Sistema compartido | `src/styles/typography.css`, `src/main.tsx` |
| Migración de estilos | `src/styles/global.css`, `territorial.css`, `territorial-navigation.css`, `territorial-atlas.css`, `atlas-guide.css`, `section-statistics.css`, `profiles-enriched.css` |
| Ayudas | `src/components/statisticsPresentation.ts`, `src/components/StatisticalHelp.tsx` |
| Dashboard | `src/features/dashboard/Dashboard.tsx`, `TrendChart.tsx` |
| Metodología y ayuda del Atlas | `src/features/methodology/Methodology.tsx`, `src/features/map/ElectionMetricCards.tsx`, `src/app/App.tsx` |
| Contexto en perfiles | `EnrichedProfiles.tsx`, `EnrichedProfileDetail.tsx`, `ProfileComparePanel.tsx`, `ProfileVisuals.tsx`, `TransversalFinding.tsx`, bajo `src/features/profiles/` |
| Validación | `scripts/statistics-presentation.test.mjs`, `scripts/check-typography-ui.mjs`, expectativas actualizadas de `scripts/check-territorial-ui.mjs` |
| Documentación | Este documento y enlace desde `docs/perfiles_enriquecidos.md` |

Las expectativas del test del Atlas se actualizaron para las cuatro categorías principales que ya existían, para distinguir el patrón de empates U/R/M, definido en SVG, de su utilización real en polígonos y para verificar el territorio por su clave y encabezado actual, en lugar de un párrafo retirado en una iteración previa. No se retiraron controles ni pruebas de valores/cuantiles para hacer pasar el nuevo diseño.

## Validación y reproducción

```powershell
npm.cmd run typecheck
npm.cmd run build
node --experimental-strip-types --test scripts/statistics-presentation.test.mjs scripts/profiles-enriched.test.mjs
npm.cmd run test:territorial
node scripts/check-typography-ui.mjs
node scripts/check-profiles-ui.mjs
node scripts/check-territorial-ui.mjs
```

Las pruebas de presentación contrastan las seis elecciones contra los conteos publicados, distinguen la tasa observada de la nominal y prueban ausencias, cero, redondeo, definiciones, fórmulas, advertencias y huecos de la serie temporal. Las pruebas previas de perfiles y territorio comprueban cifras, referencias, paletas, capas y cuantiles.

Resultado: **19 pruebas de presentación/perfiles y 27 territoriales aprobadas**, junto con TypeScript, compilación y los tres recorridos de Chrome. Los controles visibles revisados conservan al menos 16 px en inputs/selectores y el texto de los pasos metodológicos al menos 16 px.

Chrome revisa Dashboard, Metodología, Atlas y Perfiles en ambos temas a 1480, 950, 390 y 320 px, con contraste ≥4.5:1 en los textos seleccionados y sin desbordamiento de la página. La regresión de perfiles cubre también el comparador, el hallazgo, teclado y foco. La prueba del Atlas conserva sus recorridos de búsqueda, selección, leyendas, ranking, movimiento del mapa y guía.

La prueba de reflujo cubre equivalentes a 100 %, 125 %, 150 % y 200 % mediante viewport CSS y DPR de una ventana física de referencia. **Es emulación de reflujo, no zoom nativo de Chrome**: DevTools en modo headless no expone de forma fiable ese control. No se altera la escala de los estilos de la aplicación para realizarla. Queda pendiente la comprobación manual del zoom nativo y con lectores de pantalla.

Capturas y resultados de diagnóstico se guardan en `node_modules/.cache/typography-ui/`, `profiles-ui/` y `territorial-ui/`; no son exportaciones de producto. El entorno gestionado requiere ejecución autorizada fuera del sandbox para esbuild y Chrome. No se añadieron dependencias ni se crearon commits, push, merges o PR.

La comprobación final de integridad contrasta **1,511 archivos protegidos** de datos publicados, investigación, documentación analítica, servicios y lógica territorial/estadística contra sus hashes iniciales. También comprueba que las siete hojas anteriores sólo cambiaron declaraciones de tamaño/familia, conservando sus paletas y demás propiedades. Las nuevas reglas de tipografía y adaptación están aisladas en la hoja compartida; los cambios de texto del Dashboard y las ayudas no cambian números ni indicadores.
