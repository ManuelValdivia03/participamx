# Evaluación de patrones candidatos

**1 de seis interacciones supera los controles predefinidos.** No se modifica el protocolo para obtener cuatro a seis perfiles. La ausencia de un contraste de ≥2 pp no demuestra identidad electoral: limita la fuerza práctica de ese patrón en este diseño.

| Contraste | Municipios | Media municipal (pp) | Media con LN (pp) | Supera controles | Controles no superados |
| --- | --- | --- | --- | --- | --- |
| interaction_18-34_M_U | 1227 | 1.26 | 1.47 | No | practical_and_weights;confirmation |
| interaction_18-34_R_U | 1226 | 3.82 | 5.30 | Sí |  |
| interaction_35-59_M_U | 1262 | 0.25 | 0.27 | No | practical_and_weights;territorial_consistency;confirmation;simultaneous_envelope |
| interaction_35-59_R_U | 1255 | 0.88 | 2.01 | No | practical_and_weights;territorial_consistency;confirmation |
| interaction_60-100_M_U | 1122 | -0.12 | -0.25 | No | practical_and_weights;territorial_consistency;confirmation;simultaneous_envelope |
| interaction_60-100_R_U | 1117 | -1.32 | -0.83 | No | practical_and_weights;confirmation |

Los detalles de todos los criterios están en [screening.csv](../candidates/screening.csv). Las seis fichas diagnósticas conservan las pruebas, incluidas las que no pueden promoverse. Los nombres sólo se proponen para las que pasan; las otras no se presentan como cinco perfiles descubiertos.

## Sensibilidad al umbral de magnitud

| Umbral práctico (pp) | Patrones que superarían controles |
| --- | --- |
| 1.00 | 2 |
| 2.00 | 1 |
| 3.00 | 1 |

Este diagnóstico secundario se añade después de la evaluación principal: varía únicamente la magnitud exigida en la población completa y los dos repartos municipales, manteniendo los demás controles. No sustituye el umbral principal de 2 pp ni convierte las variantes en nuevos perfiles. [Detalle de las 18 comprobaciones](../candidates/practical_threshold_sensitivity.csv). El resultado depende del protocolo; no es una demostración de que ninguna otra representación o familia de relaciones pueda contener cuatro a seis patrones.

## Población cubierta y superposición

La unión única de patrones aceptados contiene 4,904 celdas, 1,226 municipios y LN=22,587,270: 22.97 % anual y 23.05 % del LN elegible. Quedan fuera 26,566 celdas elegibles con LN=75,412,407. Hay 0 celdas en más de un patrón aceptado. No se suman coberturas de fichas: se unen row_id. El marco admite superposiciones porque una celda urbana puede servir como comparación en R−U y M−U. Por ello C es un conjunto de patrones representativos, no una partición alternativa exhaustiva.

[Membresías de las seis pruebas](../candidates/all_six_memberships.parquet), [unión única](../candidates/union_coverage.json) y [referencia íntegra con número de membresías](../reference/all_observations.parquet). Cero membresías no significa tasa cero ni ausencia de personas.

- [interaction_18-34_M_U](../candidates/cards/interaction_18-34_M_U.md): diagnóstico no promovido.

- [interaction_18-34_R_U](../candidates/cards/interaction_18-34_R_U.md): candidato.

- [interaction_35-59_M_U](../candidates/cards/interaction_35-59_M_U.md): diagnóstico no promovido.

- [interaction_35-59_R_U](../candidates/cards/interaction_35-59_R_U.md): diagnóstico no promovido.

- [interaction_60-100_M_U](../candidates/cards/interaction_60-100_M_U.md): diagnóstico no promovido.

- [interaction_60-100_R_U](../candidates/cards/interaction_60-100_R_U.md): diagnóstico no promovido.
