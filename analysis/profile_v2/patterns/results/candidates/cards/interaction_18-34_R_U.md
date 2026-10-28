# Brecha joven ampliada en secciones rurales

**Estado:** candidate_supported_within_protocol · ID `interaction_18-34_R_U`

18–34 años · comparación mujeres−hombres en secciones rurales y urbanas dentro del mismo municipio.

En 1,226 municipios con cuatro celdas de soporte, el contraste es +3.82 pp con igual peso municipal y +5.30 pp con peso LN. 75.86 % de municipios mantiene el signo de la media. La comparación mide cómo cambia la brecha entre sexos según tipo de sección electoral, no una participación individual ni una causa.

## Tres hallazgos

- Contraste municipal +3.82 pp; con LN +5.30; desde tasas agregadas +8.73.
- La mitad central municipal va de +0.20 a +7.37 pp; 75.86 % comparte signo.
- Incluye 1,226 municipios y 32 entidades, LN=22,587,270 (22.97 % anual), con D=20,975,575.

## Tasas y referencias de sus cuatro componentes

| Sexo | Tipo de sección | Municipios | LN | SV+NV | Participación (%) | Referencia nacional (%) | Diferencia nacional (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | R | 1226 | 2796840 | 2592186 | 58.62 | 55.97 | 2.65 |
| 0 | R | 1226 | 2665197 | 2469839 | 39.69 | 43.74 | -4.05 |
| 1 | U | 1226 | 8589917 | 7983335 | 53.06 | 55.97 | -2.91 |
| 0 | U | 1226 | 8535316 | 7930215 | 42.86 | 43.74 | -0.88 |

Las tasas se calculan desde conteos en los mismos municipios emparejados. Referencia: tasa nacional original de esa banda/sexo, sin filtro de soporte. El contraste principal compara la **brecha mujeres−hombres entre T y U**; su referencia es la brecha urbana, no la tasa nacional ni una participación predicha. Los cuatro roles son parte del patrón comparativo, no cuatro clases de personas.

## Confirmación municipal independiente del reparto inicial

| Reparto | Municipios | LN | Media municipal (pp) | Media con LN (pp) | Desde tasas agregadas (pp) |
| --- | --- | --- | --- | --- | --- |
| confirmation | 505 | 8495944 | 3.74 | 5.81 | 8.82 |
| discovery | 721 | 14091326 | 3.87 | 4.99 | 8.68 |

El reparto se fijó por municipio y entidad; cada municipio aparece en un único grupo. No se ajustó un modelo ni se seleccionaron umbrales en confirmación. La revisión simultánea posterior no es una evaluación predictiva ciega ni validación externa.

## Calidad y estabilidad

| Escenario | Municipios | LN | Media municipal (pp) | Media con LN (pp) |
| --- | --- | --- | --- | --- |
| support_200 | 1063 | 21948659 | 4.05 | 5.33 |
| low_ns | 785 | 13733361 | 4.22 | 6.29 |
| five_sections | 512 | 16625900 | 4.80 | 5.69 |

| Estimando | Contraste (pp) | Banda diagnóstica inferior (pp) | Banda diagnóstica superior (pp) | Fracción de réplicas con mismo signo |
| --- | --- | --- | --- | --- |
| equal_municipality | 3.82 | 3.33 | 4.31 | 1.00 |
| nominal | 5.30 | 4.10 | 6.49 | 1.00 |
| pooled_counts | 8.73 | 7.85 | 9.62 | 1.00 |

Bandas diagnósticas simultáneas de la familia de 18 estimandos; no intervalos de votantes. Con NS extremo, la media municipal del contraste puede estar entre -8.61 y +15.84 pp. Es sensibilidad algebraica, no una imputación.

## Evidencia territorial

| EDOCVE | Municipios | LN | Media municipal (pp) | Fracción municipal con mismo signo |
| --- | --- | --- | --- | --- |
| 15 | 79 | 2171169 | 3.70 | 0.75 |
| 11 | 40 | 1633631 | 11.38 | 1.00 |
| 30 | 140 | 1593961 | 4.02 | 0.81 |

Se muestran las tres entidades de mayor LN emparejado, no las de mayor prevalencia. La media coincide en signo en 96.67 % de las entidades con cinco o más municipios comparables. El mayor municipio aporta 2.67 % del LN del bloque; los diez primeros 16.98 %.

## Qué aporta frente a V1

Compara directamente brechas entre sexos y tipos dentro del mismo municipio; no hereda edad/signo V1 ni etiqueta niveles alto/bajo.

## Decisión y límites

Supera los controles del protocolo como patrón descriptivo candidato; no se convierte en perfil definitivo.

- Selección de municipios con cuatro celdas completas; no representa todos los municipios.
- Heterogeneidad local, NS, soporte y composición; no causalidad ni clases naturales.
- Bandas amplias y H/M; SEXO=2 y 101+ permanecen complementarios, sin imputación.
- Patrones superpuestos; la cobertura se calcula por unión única de row_id.
- Referencia de la interacción: brecha por sexo en U de los mismos municipios. La referencia nacional banda/sexo es contexto adicional, no el cero de esta interacción.

Fuentes exactas: [contrastes municipales](../../interactions/municipal_contrasts.parquet), [componentes](../../interactions/primary_components.csv), [filtros de aceptación](../screening.csv), [sensibilidades](../../validation/quality_sensitivity.csv). Filtrar siempre el contrast_id de esta ficha.
 
