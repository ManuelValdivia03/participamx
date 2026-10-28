# Contraste diagnóstico 35-59 · R-U

**Estado:** not_supported_as_candidate_under_protocol · ID `interaction_35-59_R_U`

35–59 años · comparación mujeres−hombres en secciones rurales y urbanas dentro del mismo municipio.

En 1,255 municipios con cuatro celdas de soporte, el contraste es +0.88 pp con igual peso municipal y +2.01 pp con peso LN. 58.41 % de municipios mantiene el signo de la media. La comparación mide cómo cambia la brecha entre sexos según tipo de sección electoral, no una participación individual ni una causa.

## Tres hallazgos

- Contraste municipal +0.88 pp; con LN +2.01; desde tasas agregadas +2.54.
- La mitad central municipal va de -2.04 a +3.64 pp; 58.41 % comparte signo.
- Incluye 1,255 municipios y 32 entidades, LN=26,007,663 (26.45 % anual), con D=24,161,953.

## Tasas y referencias de sus cuatro componentes

| Sexo | Tipo de sección | Municipios | LN | SV+NV | Participación (%) | Referencia nacional (%) | Diferencia nacional (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | R | 1255 | 3032513 | 2813220 | 70.11 | 68.01 | 2.11 |
| 0 | R | 1255 | 2847929 | 2639474 | 57.52 | 57.30 | 0.22 |
| 1 | U | 1255 | 10535031 | 9797337 | 65.63 | 68.01 | -2.37 |
| 0 | U | 1255 | 9592190 | 8911922 | 55.58 | 57.30 | -1.72 |

Las tasas se calculan desde conteos en los mismos municipios emparejados. Referencia: tasa nacional original de esa banda/sexo, sin filtro de soporte. El contraste principal compara la **brecha mujeres−hombres entre T y U**; su referencia es la brecha urbana, no la tasa nacional ni una participación predicha. Los cuatro roles son parte del patrón comparativo, no cuatro clases de personas.

## Confirmación municipal independiente del reparto inicial

| Reparto | Municipios | LN | Media municipal (pp) | Media con LN (pp) | Desde tasas agregadas (pp) |
| --- | --- | --- | --- | --- | --- |
| confirmation | 516 | 9839604 | 0.76 | 2.38 | 2.24 |
| discovery | 739 | 16168059 | 0.96 | 1.79 | 2.75 |

El reparto se fijó por municipio y entidad; cada municipio aparece en un único grupo. No se ajustó un modelo ni se seleccionaron umbrales en confirmación. La revisión simultánea posterior no es una evaluación predictiva ciega ni validación externa.

## Calidad y estabilidad

| Escenario | Municipios | LN | Media municipal (pp) | Media con LN (pp) |
| --- | --- | --- | --- | --- |
| support_200 | 1119 | 25477140 | 0.99 | 2.03 |
| low_ns | 807 | 15910056 | 1.19 | 2.54 |
| five_sections | 512 | 19293420 | 1.39 | 2.40 |

| Estimando | Contraste (pp) | Banda diagnóstica inferior (pp) | Banda diagnóstica superior (pp) | Fracción de réplicas con mismo signo |
| --- | --- | --- | --- | --- |
| equal_municipality | 0.88 | 0.47 | 1.29 | 1.00 |
| nominal | 2.01 | 1.25 | 2.77 | 1.00 |
| pooled_counts | 2.54 | 1.83 | 3.25 | 1.00 |

Bandas diagnósticas simultáneas de la familia de 18 estimandos; no intervalos de votantes. Con NS extremo, la media municipal del contraste puede estar entre -11.57 y +13.35 pp. Es sensibilidad algebraica, no una imputación.

## Evidencia territorial

| EDOCVE | Municipios | LN | Media municipal (pp) | Fracción municipal con mismo signo |
| --- | --- | --- | --- | --- |
| 15 | 80 | 2468848 | 1.73 | 0.70 |
| 30 | 142 | 1992852 | -0.37 | 0.54 |
| 11 | 40 | 1815762 | 6.73 | 0.97 |

Se muestran las tres entidades de mayor LN emparejado, no las de mayor prevalencia. La media coincide en signo en 67.74 % de las entidades con cinco o más municipios comparables. El mayor municipio aporta 2.76 % del LN del bloque; los diez primeros 17.19 %.

## Qué aporta frente a V1

Compara directamente brechas entre sexos y tipos dentro del mismo municipio; no hereda edad/signo V1 ni etiqueta niveles alto/bajo.

## Decisión y límites

No se promueve como perfil multivariable: no supera `practical_and_weights;territorial_consistency;confirmation`. Se conserva para revisión; no se le asigna un nombre atractivo para ocultar esos límites.

- Selección de municipios con cuatro celdas completas; no representa todos los municipios.
- Heterogeneidad local, NS, soporte y composición; no causalidad ni clases naturales.
- Bandas amplias y H/M; SEXO=2 y 101+ permanecen complementarios, sin imputación.
- Patrones superpuestos; la cobertura se calcula por unión única de row_id.
- Referencia de la interacción: brecha por sexo en U de los mismos municipios. La referencia nacional banda/sexo es contexto adicional, no el cero de esta interacción.

Fuentes exactas: [contrastes municipales](../../interactions/municipal_contrasts.parquet), [componentes](../../interactions/primary_components.csv), [filtros de aceptación](../screening.csv), [sensibilidades](../../validation/quality_sensitivity.csv). Filtrar siempre el contrast_id de esta ficha.
 
