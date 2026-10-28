# Contraste diagnóstico 60-100 · R-U

**Estado:** not_supported_as_candidate_under_protocol · ID `interaction_60-100_R_U`

60–100 años · comparación mujeres−hombres en secciones rurales y urbanas dentro del mismo municipio.

En 1,117 municipios con cuatro celdas de soporte, el contraste es -1.32 pp con igual peso municipal y -0.83 pp con peso LN. 62.76 % de municipios mantiene el signo de la media. La comparación mide cómo cambia la brecha entre sexos según tipo de sección electoral, no una participación individual ni una causa.

## Tres hallazgos

- Contraste municipal -1.32 pp; con LN -0.83; desde tasas agregadas -1.94.
- La mitad central municipal va de -3.61 a +1.19 pp; 62.76 % comparte signo.
- Incluye 1,117 municipios y 32 entidades, LN=10,862,621 (11.05 % anual), con D=10,107,938.

## Tasas y referencias de sus cuatro componentes

| Sexo | Tipo de sección | Municipios | LN | SV+NV | Participación (%) | Referencia nacional (%) | Diferencia nacional (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | R | 1117 | 1339957 | 1246999 | 66.69 | 70.84 | -4.15 |
| 0 | R | 1117 | 1303689 | 1210522 | 70.06 | 72.21 | -2.15 |
| 1 | U | 1117 | 4542982 | 4229438 | 69.55 | 70.84 | -1.29 |
| 0 | U | 1117 | 3675993 | 3420979 | 70.98 | 72.21 | -1.23 |

Las tasas se calculan desde conteos en los mismos municipios emparejados. Referencia: tasa nacional original de esa banda/sexo, sin filtro de soporte. El contraste principal compara la **brecha mujeres−hombres entre T y U**; su referencia es la brecha urbana, no la tasa nacional ni una participación predicha. Los cuatro roles son parte del patrón comparativo, no cuatro clases de personas.

## Confirmación municipal independiente del reparto inicial

| Reparto | Municipios | LN | Media municipal (pp) | Media con LN (pp) | Desde tasas agregadas (pp) |
| --- | --- | --- | --- | --- | --- |
| confirmation | 455 | 4147184 | -0.96 | -0.87 | -2.14 |
| discovery | 662 | 6715437 | -1.57 | -0.81 | -1.82 |

El reparto se fijó por municipio y entidad; cada municipio aparece en un único grupo. No se ajustó un modelo ni se seleccionaron umbrales en confirmación. La revisión simultánea posterior no es una evaluación predictiva ciega ni validación externa.

## Calidad y estabilidad

| Escenario | Municipios | LN | Media municipal (pp) | Media con LN (pp) |
| --- | --- | --- | --- | --- |
| support_200 | 863 | 10010612 | -1.28 | -0.88 |
| low_ns | 725 | 6808230 | -1.32 | -0.66 |
| five_sections | 512 | 8382385 | -1.40 | -0.93 |

| Estimando | Contraste (pp) | Banda diagnóstica inferior (pp) | Banda diagnóstica superior (pp) | Fracción de réplicas con mismo signo |
| --- | --- | --- | --- | --- |
| equal_municipality | -1.32 | -1.68 | -0.96 | 1.00 |
| nominal | -0.83 | -1.30 | -0.35 | 1.00 |
| pooled_counts | -1.94 | -2.47 | -1.42 | 1.00 |

Bandas diagnósticas simultáneas de la familia de 18 estimandos; no intervalos de votantes. Con NS extremo, la media municipal del contraste puede estar entre -12.88 y +10.50 pp. Es sensibilidad algebraica, no una imputación.

## Evidencia territorial

| EDOCVE | Municipios | LN | Media municipal (pp) | Fracción municipal con mismo signo |
| --- | --- | --- | --- | --- |
| 30 | 135 | 997375 | -1.55 | 0.67 |
| 15 | 69 | 882429 | -0.14 | 0.49 |
| 11 | 39 | 782955 | 0.07 | 0.56 |

Se muestran las tres entidades de mayor LN emparejado, no las de mayor prevalencia. La media coincide en signo en 90.00 % de las entidades con cinco o más municipios comparables. El mayor municipio aporta 2.37 % del LN del bloque; los diez primeros 16.77 %.

## Qué aporta frente a V1

Compara directamente brechas entre sexos y tipos dentro del mismo municipio; no hereda edad/signo V1 ni etiqueta niveles alto/bajo.

## Decisión y límites

No se promueve como perfil multivariable: no supera `practical_and_weights;confirmation`. Se conserva para revisión; no se le asigna un nombre atractivo para ocultar esos límites.

- Selección de municipios con cuatro celdas completas; no representa todos los municipios.
- Heterogeneidad local, NS, soporte y composición; no causalidad ni clases naturales.
- Bandas amplias y H/M; SEXO=2 y 101+ permanecen complementarios, sin imputación.
- Patrones superpuestos; la cobertura se calcula por unión única de row_id.
- Referencia de la interacción: brecha por sexo en U de los mismos municipios. La referencia nacional banda/sexo es contexto adicional, no el cero de esta interacción.

Fuentes exactas: [contrastes municipales](../../interactions/municipal_contrasts.parquet), [componentes](../../interactions/primary_components.csv), [filtros de aceptación](../screening.csv), [sensibilidades](../../validation/quality_sensitivity.csv). Filtrar siempre el contrast_id de esta ficha.
 
