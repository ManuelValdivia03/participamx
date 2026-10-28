# Participación de mayores con mayor distancia negativa

`older_unfavorable` · recomendación editorial provisional

60–100 años · 64.10 % de participación observada; referencia comparable 71.44 % (-7.34 pp). Segmentos municipales H/M de 2024; cruces por tipo de sección electoral en la ficha.

Estos segmentos de 60–100 años muestran la mayor distancia negativa agregada frente a su referencia: −7.34 puntos. Su participación es 64.10 %, una tasa que no es la más baja de las seis fichas. El cruce por sexo y tipo de sección electoral sitúa distancias más amplias en secciones rurales y mixtas, sin describir por igual a todos los subsegmentos.

## Tres hallazgos verificables

- Participación 64.10 %, referencia 71.44 %, Δ=−7.34 pp, frente a −6.83 y −5.96 de las otras fichas negativas. Fuentes: [v1_profiles](../source_catalog.md#v1-profiles)

- En 60–100, las distancias rurales son −9.98 pp en hombres y −9.76 pp en mujeres; las urbanas son −6.10 y −6.22 pp. La diferencia entre los deltas agregados de hombres y mujeres es sólo 0.03 pp; no respalda un nombre centrado en una gran separación por sexo. El contraste observado es contextual, no causal. Fuentes: [joint_evidence](../source_catalog.md#joint-evidence), [section_evidence](../source_catalog.md#section-evidence), [prior_interpretation](../source_catalog.md#prior-interpretation)

- 387/4,650 hijos con soporte (8.32 %) cambian de signo frente al padre V1, con LN=424,457 (5.13 % del LN de los hijos elegibles de la ficha). De esos cambios, 250 están a ≤2 pp de cero en el hijo y 244 en el padre; las dos cuentas se superponen. 81 tienen NS alto y 236 menos de cinco secciones, banderas también superpuestas. No todos los cambios son diferencias grandes ni datos erróneos. Fuentes: [profile_evidence](../source_catalog.md#profile-evidence), [reversal_evidence](../source_catalog.md#reversal-evidence), [reversal_quality](../source_catalog.md#reversal-quality)

## Participación y referencia

De 7,721,890 registros con participación especificada, 4,949,523 corresponden a SV: 64.10 %. La referencia de 71.44 % combina las tasas nacionales de esta banda para H/M usando los denominadores locales SV+NV como pesos. Su resta es -7.34 pp. NS no entra como abstención; la referencia es descriptiva, no una predicción.

## Sexo y tipo de sección electoral: cruce conjunto

Las mujeres aportan 54.67 % de los segmentos V1 y 56.08 % del LN. El resto corresponde a hombres en estas fichas H/M. Cada sexo se contrasta con su propia referencia; sus conjuntos de municipios pueden diferir. La tabla conjunta permite comparar U/R/M dentro del mismo sexo sin atribuirle un efecto causal.

Composición nominal por tipo de sección electoral: urbana 66.43 %; rural 20.51 %; mixta 13.06 %. Urbana reúne más de la mitad del LN en esta ficha, como en las otras cinco: no es un rasgo exclusivo. En 60–100, las distancias rurales son −9.98 pp en hombres y −9.76 pp en mujeres; las urbanas son −6.10 y −6.22 pp. La diferencia entre los deltas agregados de hombres y mujeres es sólo 0.03 pp; no respalda un nombre centrado en una gran separación por sexo. El contraste observado es contextual, no causal.

| SEXO | TIPOSEC | LN | specified_count | participation_observed_pct | matched_age_sex_reference_pct | delta_pp | eligible_cells | eligible_flip_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | M | 485575 | 455197 | 62.50 | 72.21 | -9.71 | 759 | 56 |
| 0 | R | 735591 | 682389 | 62.23 | 72.21 | -9.98 | 723 | 65 |
| 0 | U | 2432697 | 2254844 | 66.12 | 72.21 | -6.10 | 624 | 42 |
| 1 | M | 601318 | 565306 | 61.78 | 70.84 | -9.05 | 931 | 96 |
| 1 | R | 970744 | 899986 | 61.07 | 70.84 | -9.76 | 862 | 48 |
| 1 | U | 3093868 | 2864168 | 64.61 | 70.84 | -6.22 | 751 | 80 |

SEXO: 0=Hombres, 1=Mujeres. U=Urbana, R=Rural, M=Mixta. Tasas en %; diferencias en pp. Cada fila suma hijos de una misma banda, sexo y tipo, en los municipios de la ficha V1. Las tasas conservan hijos con y sin soporte; las últimas dos columnas cuentan exclusivamente hijos elegibles. No son secciones únicas ni personas.

Fuentes exactas: [catálogo](../source_catalog.md), `joint_evidence`, `section_evidence`, `sex_evidence`; filtro `profile_id=older_unfavorable`. Datos descargables: [cruce conjunto](../../evidence/profile_sex_section.csv), [resumen U/R/M](../../evidence/profile_section.csv).

## Territorio

Mayores aportaciones de LN a la ficha: JALISCO 10.78 %; MICHOACAN 9.13 %; NUEVO LEON 8.35 %. El denominador es el LN de esta ficha. En JALISCO, su LN representa 13.56 % del núcleo estatal H/M 18–100, un denominador distinto. Los municipios pueden participar en otras fichas; no se suman sus coberturas ni se atribuye el patrón a todos sus habitantes.

Fuente: [distribución estatal](../../evidence/profile_state.csv), mismo profile_id; se distingue cuota de la ficha de cuota del núcleo estatal.

## Cambios de signo al desagregar

387/4,650 hijos con soporte (8.32 %) cambian de signo frente al padre V1, con LN=424,457 (5.13 % del LN de los hijos elegibles de la ficha). De esos cambios, 250 están a ≤2 pp de cero en el hijo y 244 en el padre; las dos cuentas se superponen. 81 tienen NS alto y 236 menos de cinco secciones, banderas también superpuestas. No todos los cambios son diferencias grandes ni datos erróneos.

Ejemplo seleccionado por mayor LN entre los hijos elegibles que cambian de signo, sin elegir la diferencia máxima: entidad 11, municipio 17, mujeres, banda 60-100, sección electoral urbana. LN=35,092, SV+NV=34,048; tasa=71.69 %, referencia=70.84 %, Δ hijo=+0.85 pp; Δ padre=-0.98 pp. row_id=experimental_2024|11|17|60-100|1|U. No es un caso representativo de todos los cambios.

Los signos de padre e hijo usan la **misma referencia nacional de banda/sexo**. Se decide por productos cruzados de enteros Python, antes de redondear. No se confunde un cambio de signo por desagregación con un cambio provocado por usar una referencia U/R/M distinta.

Fuente: [cambios elegibles](../../evidence/eligible_sign_reversals.parquet), [calidad y todas las poblaciones](../../evidence/reversal_quality.csv) y [ejemplos deterministas](../../evidence/reversal_examples.csv).

## Variación interna y límites

La mitad central de las diferencias V1 va de -13.19 a -3.34 pp; mediana -7.54 pp, DE 7.14 pp con igual peso por segmento. 15.54 % de padres está a ≤2 pp de la referencia y 18.91 % tiene NS/LN≥10 %. Al separar U/R/M hay 23 hijos con tasa no definida (LN=2,833); no se vuelven cero. Los agregados de la ficha incluyen todos sus hijos, no sólo los elegibles. Las medias por cruce mantienen el signo del padre en esta evidencia, pero esconden cambios locales. Edad agrupada, signo convencional, NS y soporte desigual limitan la interpretación. U/R/M identifica secciones electorales, no localidad ni residencia individual; tampoco demuestra motivaciones o eficacia institucional.

No se proponen campañas, canales ni mensajes personalizados por edad, sexo, territorio o conducta. El uso de esta ficha es descriptivo y agregado.
