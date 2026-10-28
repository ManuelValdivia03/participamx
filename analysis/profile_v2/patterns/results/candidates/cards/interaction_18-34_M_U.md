# Contraste diagnóstico 18-34 · M-U

**Estado:** not_supported_as_candidate_under_protocol · ID `interaction_18-34_M_U`

18–34 años · comparación mujeres−hombres en secciones mixtas y urbanas dentro del mismo municipio.

En 1,227 municipios con cuatro celdas de soporte, el contraste es +1.26 pp con igual peso municipal y +1.47 pp con peso LN. 63.33 % de municipios mantiene el signo de la media. La comparación mide cómo cambia la brecha entre sexos según tipo de sección electoral, no una participación individual ni una causa.

## Tres hallazgos

- Contraste municipal +1.26 pp; con LN +1.47; desde tasas agregadas +3.20.
- La mitad central municipal va de -1.38 a +3.98 pp; 63.33 % comparte signo.
- Incluye 1,227 municipios y 32 entidades, LN=23,255,907 (23.65 % anual), con D=21,702,104.

## Tasas y referencias de sus cuatro componentes

| Sexo | Tipo de sección | Municipios | LN | SV+NV | Participación (%) | Referencia nacional (%) | Diferencia nacional (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | M | 1227 | 2199389 | 2062758 | 54.27 | 55.97 | -1.70 |
| 0 | M | 1227 | 2127175 | 1994322 | 40.99 | 43.74 | -2.75 |
| 1 | U | 1227 | 9484970 | 8842636 | 53.28 | 55.97 | -2.69 |
| 0 | U | 1227 | 9444373 | 8802388 | 43.20 | 43.74 | -0.54 |

Las tasas se calculan desde conteos en los mismos municipios emparejados. Referencia: tasa nacional original de esa banda/sexo, sin filtro de soporte. El contraste principal compara la **brecha mujeres−hombres entre T y U**; su referencia es la brecha urbana, no la tasa nacional ni una participación predicha. Los cuatro roles son parte del patrón comparativo, no cuatro clases de personas.

## Confirmación municipal independiente del reparto inicial

| Reparto | Municipios | LN | Media municipal (pp) | Media con LN (pp) | Desde tasas agregadas (pp) |
| --- | --- | --- | --- | --- | --- |
| confirmation | 517 | 8517410 | 1.20 | 1.54 | 3.10 |
| discovery | 710 | 14738497 | 1.31 | 1.43 | 3.27 |

El reparto se fijó por municipio y entidad; cada municipio aparece en un único grupo. No se ajustó un modelo ni se seleccionaron umbrales en confirmación. La revisión simultánea posterior no es una evaluación predictiva ciega ni validación externa.

## Calidad y estabilidad

| Escenario | Municipios | LN | Media municipal (pp) | Media con LN (pp) |
| --- | --- | --- | --- | --- |
| support_200 | 1055 | 22888850 | 1.25 | 1.46 |
| low_ns | 810 | 15915447 | 1.45 | 1.68 |
| five_sections | 281 | 14273580 | 1.90 | 1.60 |

| Estimando | Contraste (pp) | Banda diagnóstica inferior (pp) | Banda diagnóstica superior (pp) | Fracción de réplicas con mismo signo |
| --- | --- | --- | --- | --- |
| equal_municipality | 1.26 | 0.87 | 1.66 | 1.00 |
| nominal | 1.47 | 0.79 | 2.15 | 1.00 |
| pooled_counts | 3.20 | 2.65 | 3.76 | 1.00 |

Bandas diagnósticas simultáneas de la familia de 18 estimandos; no intervalos de votantes. Con NS extremo, la media municipal del contraste puede estar entre -10.69 y +13.36 pp. Es sensibilidad algebraica, no una imputación.

## Evidencia territorial

| EDOCVE | Municipios | LN | Media municipal (pp) | Fracción municipal con mismo signo |
| --- | --- | --- | --- | --- |
| 15 | 79 | 2385661 | 1.05 | 0.65 |
| 14 | 95 | 1775449 | 0.95 | 0.57 |
| 11 | 36 | 1352204 | 4.42 | 0.89 |

Se muestran las tres entidades de mayor LN emparejado, no las de mayor prevalencia. La media coincide en signo en 96.88 % de las entidades con cinco o más municipios comparables. El mayor municipio aporta 2.68 % del LN del bloque; los diez primeros 17.17 %.

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
 
