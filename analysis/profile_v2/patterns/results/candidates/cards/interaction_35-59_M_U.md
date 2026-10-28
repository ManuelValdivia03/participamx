# Contraste diagnóstico 35-59 · M-U

**Estado:** not_supported_as_candidate_under_protocol · ID `interaction_35-59_M_U`

35–59 años · comparación mujeres−hombres en secciones mixtas y urbanas dentro del mismo municipio.

En 1,262 municipios con cuatro celdas de soporte, el contraste es +0.25 pp con igual peso municipal y +0.27 pp con peso LN. 53.49 % de municipios mantiene el signo de la media. La comparación mide cómo cambia la brecha entre sexos según tipo de sección electoral, no una participación individual ni una causa.

## Tres hallazgos

- Contraste municipal +0.25 pp; con LN +0.27; desde tasas agregadas +0.95.
- La mitad central municipal va de -1.85 a +2.45 pp; 53.49 % comparte signo.
- Incluye 1,262 municipios y 32 entidades, LN=27,189,542 (27.65 % anual), con D=25,385,698.

## Tasas y referencias de sus cuatro componentes

| Sexo | Tipo de sección | Municipios | LN | SV+NV | Participación (%) | Referencia nacional (%) | Diferencia nacional (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | M | 1262 | 2542140 | 2388188 | 66.21 | 68.01 | -1.80 |
| 0 | M | 1262 | 2320181 | 2177993 | 55.18 | 57.30 | -2.11 |
| 1 | U | 1262 | 11679766 | 10896391 | 65.78 | 68.01 | -2.23 |
| 0 | U | 1262 | 10647455 | 9923126 | 55.70 | 57.30 | -1.59 |

Las tasas se calculan desde conteos en los mismos municipios emparejados. Referencia: tasa nacional original de esa banda/sexo, sin filtro de soporte. El contraste principal compara la **brecha mujeres−hombres entre T y U**; su referencia es la brecha urbana, no la tasa nacional ni una participación predicha. Los cuatro roles son parte del patrón comparativo, no cuatro clases de personas.

## Confirmación municipal independiente del reparto inicial

| Reparto | Municipios | LN | Media municipal (pp) | Media con LN (pp) | Desde tasas agregadas (pp) |
| --- | --- | --- | --- | --- | --- |
| confirmation | 532 | 9984196 | -0.05 | 0.07 | 0.75 |
| discovery | 730 | 17205346 | 0.47 | 0.39 | 1.08 |

El reparto se fijó por municipio y entidad; cada municipio aparece en un único grupo. No se ajustó un modelo ni se seleccionaron umbrales en confirmación. La revisión simultánea posterior no es una evaluación predictiva ciega ni validación externa.

## Calidad y estabilidad

| Escenario | Municipios | LN | Media municipal (pp) | Media con LN (pp) |
| --- | --- | --- | --- | --- |
| support_200 | 1119 | 26858149 | 0.26 | 0.27 |
| low_ns | 834 | 19322494 | 0.39 | 0.36 |
| five_sections | 281 | 16681247 | 0.57 | 0.22 |

| Estimando | Contraste (pp) | Banda diagnóstica inferior (pp) | Banda diagnóstica superior (pp) | Fracción de réplicas con mismo signo |
| --- | --- | --- | --- | --- |
| equal_municipality | 0.25 | -0.07 | 0.56 | 0.99 |
| nominal | 0.27 | -0.23 | 0.78 | 0.95 |
| pooled_counts | 0.95 | 0.48 | 1.42 | 1.00 |

Bandas diagnósticas simultáneas de la familia de 18 estimandos; no intervalos de votantes. Con NS extremo, la media municipal del contraste puede estar entre -11.65 y +12.31 pp. Es sensibilidad algebraica, no una imputación.

## Evidencia territorial

| EDOCVE | Municipios | LN | Media municipal (pp) | Fracción municipal con mismo signo |
| --- | --- | --- | --- | --- |
| 15 | 79 | 2798482 | 0.20 | 0.57 |
| 14 | 98 | 2021541 | -0.01 | 0.51 |
| 11 | 36 | 1513967 | 3.31 | 0.83 |

Se muestran las tres entidades de mayor LN emparejado, no las de mayor prevalencia. La media coincide en signo en 65.62 % de las entidades con cinco o más municipios comparables. El mayor municipio aporta 2.71 % del LN del bloque; los diez primeros 17.07 %.

## Qué aporta frente a V1

Compara directamente brechas entre sexos y tipos dentro del mismo municipio; no hereda edad/signo V1 ni etiqueta niveles alto/bajo.

## Decisión y límites

No se promueve como perfil multivariable: no supera `practical_and_weights;territorial_consistency;confirmation;simultaneous_envelope`. Se conserva para revisión; no se le asigna un nombre atractivo para ocultar esos límites.

- Selección de municipios con cuatro celdas completas; no representa todos los municipios.
- Heterogeneidad local, NS, soporte y composición; no causalidad ni clases naturales.
- Bandas amplias y H/M; SEXO=2 y 101+ permanecen complementarios, sin imputación.
- Patrones superpuestos; la cobertura se calcula por unión única de row_id.
- Referencia de la interacción: brecha por sexo en U de los mismos municipios. La referencia nacional banda/sexo es contexto adicional, no el cero de esta interacción.

Fuentes exactas: [contrastes municipales](../../interactions/municipal_contrasts.parquet), [componentes](../../interactions/primary_components.csv), [filtros de aceptación](../screening.csv), [sensibilidades](../../validation/quality_sensitivity.csv). Filtrar siempre el contrast_id de esta ficha.
 
