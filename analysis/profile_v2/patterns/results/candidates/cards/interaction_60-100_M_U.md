# Contraste diagnóstico 60-100 · M-U

**Estado:** not_supported_as_candidate_under_protocol · ID `interaction_60-100_M_U`

60–100 años · comparación mujeres−hombres en secciones mixtas y urbanas dentro del mismo municipio.

En 1,122 municipios con cuatro celdas de soporte, el contraste es -0.12 pp con igual peso municipal y -0.25 pp con peso LN. 51.69 % de municipios mantiene el signo de la media. La comparación mide cómo cambia la brecha entre sexos según tipo de sección electoral, no una participación individual ni una causa.

## Tres hallazgos

- Contraste municipal -0.12 pp; con LN -0.25; desde tasas agregadas -0.06.
- La mitad central municipal va de -2.55 a +2.18 pp; 51.69 % comparte signo.
- Incluye 1,122 municipios y 32 entidades, LN=10,839,539 (11.02 % anual), con D=10,184,538.

## Tasas y referencias de sus cuatro componentes

| Sexo | Tipo de sección | Municipios | LN | SV+NV | Participación (%) | Referencia nacional (%) | Diferencia nacional (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | M | 1122 | 906511 | 855491 | 67.93 | 70.84 | -2.91 |
| 0 | M | 1122 | 819239 | 772005 | 69.37 | 72.21 | -2.85 |
| 1 | U | 1122 | 5034513 | 4728141 | 69.90 | 70.84 | -0.93 |
| 0 | U | 1122 | 4079276 | 3828901 | 71.29 | 72.21 | -0.92 |

Las tasas se calculan desde conteos en los mismos municipios emparejados. Referencia: tasa nacional original de esa banda/sexo, sin filtro de soporte. El contraste principal compara la **brecha mujeres−hombres entre T y U**; su referencia es la brecha urbana, no la tasa nacional ni una participación predicha. Los cuatro roles son parte del patrón comparativo, no cuatro clases de personas.

## Confirmación municipal independiente del reparto inicial

| Reparto | Municipios | LN | Media municipal (pp) | Media con LN (pp) | Desde tasas agregadas (pp) |
| --- | --- | --- | --- | --- | --- |
| confirmation | 474 | 4111013 | -0.08 | -0.04 | -0.28 |
| discovery | 648 | 6728526 | -0.15 | -0.38 | 0.08 |

El reparto se fijó por municipio y entidad; cada municipio aparece en un único grupo. No se ajustó un modelo ni se seleccionaron umbrales en confirmación. La revisión simultánea posterior no es una evaluación predictiva ciega ni validación externa.

## Calidad y estabilidad

| Escenario | Municipios | LN | Media municipal (pp) | Media con LN (pp) |
| --- | --- | --- | --- | --- |
| support_200 | 811 | 10136252 | -0.14 | -0.24 |
| low_ns | 743 | 7538723 | -0.02 | -0.29 |
| five_sections | 280 | 6616816 | -0.49 | -0.18 |

| Estimando | Contraste (pp) | Banda diagnóstica inferior (pp) | Banda diagnóstica superior (pp) | Fracción de réplicas con mismo signo |
| --- | --- | --- | --- | --- |
| equal_municipality | -0.12 | -0.47 | 0.24 | 0.83 |
| nominal | -0.25 | -0.65 | 0.15 | 0.97 |
| pooled_counts | -0.06 | -0.47 | 0.36 | 0.66 |

Bandas diagnósticas simultáneas de la familia de 18 estimandos; no intervalos de votantes. Con NS extremo, la media municipal del contraste puede estar entre -10.61 y +10.38 pp. Es sensibilidad algebraica, no una imputación.

## Evidencia territorial

| EDOCVE | Municipios | LN | Media municipal (pp) | Fracción municipal con mismo signo |
| --- | --- | --- | --- | --- |
| 15 | 77 | 993835 | -0.54 | 0.58 |
| 14 | 92 | 822200 | -0.13 | 0.52 |
| 30 | 111 | 717306 | -0.01 | 0.54 |

Se muestran las tres entidades de mayor LN emparejado, no las de mayor prevalencia. La media coincide en signo en 53.12 % de las entidades con cinco o más municipios comparables. El mayor municipio aporta 2.39 % del LN del bloque; los diez primeros 16.96 %.

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
 
