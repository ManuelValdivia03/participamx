# Participación joven con mayor diferencia positiva

`young_favorable` · recomendación editorial provisional

18–34 años · 57.39 % de participación observada; referencia comparable 49.69 % (+7.69 pp). Segmentos municipales H/M de 2024; cruces por tipo de sección electoral en la ficha.

Estos segmentos de 18–34 años reúnen la mayor diferencia positiva agregada de las seis fichas: +7.69 puntos frente a su referencia. La intensidad varía entre municipios. El cruce por sexo y tipo de sección electoral muestra diferencias internas, aunque sus composiciones U/R/M se parecen a las de la otra categoría joven. La etiqueta agregada tampoco describe todos sus subsegmentos.

## Tres hallazgos verificables

- 57.39 % frente a 49.69 %; Δ=+7.69 pp, mayor que +6.51 y +5.78 pp de las otras fichas positivas. Fuentes: [v1_profiles](../source_catalog.md#v1-profiles), [profile_evidence](../source_catalog.md#profile-evidence)

- Entre mujeres de 18–34, la diferencia es +11.34 pp en secciones rurales y +7.04 pp en urbanas; entre hombres es +6.66 y +7.18 pp, respectivamente. El orden rural/urbano cambia según sexo: no existe una única ventaja rural común. La composición U/R/M apenas diferencia las dos fichas jóvenes (variación total 0.0165 en V1). Fuentes: [joint_evidence](../source_catalog.md#joint-evidence), [section_evidence](../source_catalog.md#section-evidence), [prior_interpretation](../source_catalog.md#prior-interpretation)

- 446/6,030 hijos con soporte (7.40 %) cambian de signo frente al padre V1, con LN=954,821 (5.55 % del LN de los hijos elegibles de la ficha). De esos cambios, 202 están a ≤2 pp de cero en el hijo y 250 en el padre; las dos cuentas se superponen. 98 tienen NS alto y 223 menos de cinco secciones, banderas también superpuestas. No todos los cambios son diferencias grandes ni datos erróneos. Fuentes: [profile_evidence](../source_catalog.md#profile-evidence), [reversal_evidence](../source_catalog.md#reversal-evidence), [reversal_quality](../source_catalog.md#reversal-quality)

## Participación y referencia

De 16,164,277 registros con participación especificada, 9,276,190 corresponden a SV: 57.39 %. La referencia de 49.69 % combina las tasas nacionales de esta banda para H/M usando los denominadores locales SV+NV como pesos. Su resta es +7.69 pp. NS no entra como abstención; la referencia es descriptiva, no una predicción.

## Sexo y tipo de sección electoral: cruce conjunto

Las mujeres aportan 55.06 % de los segmentos V1 y 48.58 % del LN. El resto corresponde a hombres en estas fichas H/M. Cada sexo se contrasta con su propia referencia; sus conjuntos de municipios pueden diferir. La tabla conjunta permite comparar U/R/M dentro del mismo sexo sin atribuirle un efecto causal.

Composición nominal por tipo de sección electoral: urbana 67.56 %; rural 19.11 %; mixta 13.33 %. Urbana reúne más de la mitad del LN en esta ficha, como en las otras cinco: no es un rasgo exclusivo. Entre mujeres de 18–34, la diferencia es +11.34 pp en secciones rurales y +7.04 pp en urbanas; entre hombres es +6.66 y +7.18 pp, respectivamente. El orden rural/urbano cambia según sexo: no existe una única ventaja rural común. La composición U/R/M apenas diferencia las dos fichas jóvenes (variación total 0.0165 en V1).

| SEXO | TIPOSEC | LN | specified_count | participation_observed_pct | matched_age_sex_reference_pct | delta_pp | eligible_cells | eligible_flip_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | M | 1062396 | 993304 | 50.24 | 43.74 | 6.50 | 981 | 80 |
| 0 | R | 1306417 | 1207291 | 50.40 | 43.74 | 6.66 | 870 | 160 |
| 0 | U | 6495469 | 6094462 | 50.92 | 43.74 | 7.18 | 841 | 26 |
| 1 | M | 1235931 | 1157960 | 65.38 | 55.97 | 9.41 | 1207 | 61 |
| 1 | R | 1987656 | 1844017 | 67.31 | 55.97 | 11.34 | 1123 | 75 |
| 1 | U | 5150124 | 4867243 | 63.02 | 55.97 | 7.04 | 1008 | 44 |

SEXO: 0=Hombres, 1=Mujeres. U=Urbana, R=Rural, M=Mixta. Tasas en %; diferencias en pp. Cada fila suma hijos de una misma banda, sexo y tipo, en los municipios de la ficha V1. Las tasas conservan hijos con y sin soporte; las últimas dos columnas cuentan exclusivamente hijos elegibles. No son secciones únicas ni personas.

Fuentes exactas: [catálogo](../source_catalog.md), `joint_evidence`, `section_evidence`, `sex_evidence`; filtro `profile_id=young_favorable`. Datos descargables: [cruce conjunto](../../evidence/profile_sex_section.csv), [resumen U/R/M](../../evidence/profile_section.csv).

## Territorio

Mayores aportaciones de LN a la ficha: MEXICO 22.37 %; CIUDAD DE MEXICO 14.96 %; PUEBLA 7.81 %. El denominador es el LN de esta ficha. En MEXICO, su LN representa 29.60 % del núcleo estatal H/M 18–100, un denominador distinto. Los municipios pueden participar en otras fichas; no se suman sus coberturas ni se atribuye el patrón a todos sus habitantes.

Fuente: [distribución estatal](../../evidence/profile_state.csv), mismo profile_id; se distingue cuota de la ficha de cuota del núcleo estatal.

## Cambios de signo al desagregar

446/6,030 hijos con soporte (7.40 %) cambian de signo frente al padre V1, con LN=954,821 (5.55 % del LN de los hijos elegibles de la ficha). De esos cambios, 202 están a ≤2 pp de cero en el hijo y 250 en el padre; las dos cuentas se superponen. 98 tienen NS alto y 223 menos de cinco secciones, banderas también superpuestas. No todos los cambios son diferencias grandes ni datos erróneos.

Ejemplo seleccionado por mayor LN entre los hijos elegibles que cambian de signo, sin elegir la diferencia máxima: entidad 22, municipio 10, hombres, banda 18-34, sección electoral mixta. LN=23,674, SV+NV=23,509; tasa=42.55 %, referencia=43.74 %, Δ hijo=-1.18 pp; Δ padre=+1.43 pp. row_id=experimental_2024|22|10|18-34|0|M. No es un caso representativo de todos los cambios.

Los signos de padre e hijo usan la **misma referencia nacional de banda/sexo**. Se decide por productos cruzados de enteros Python, antes de redondear. No se confunde un cambio de signo por desagregación con un cambio provocado por usar una referencia U/R/M distinta.

Fuente: [cambios elegibles](../../evidence/eligible_sign_reversals.parquet), [calidad y todas las poblaciones](../../evidence/reversal_quality.csv) y [ejemplos deterministas](../../evidence/reversal_examples.csv).

## Variación interna y límites

La mitad central de las diferencias V1 va de +5.71 a +18.57 pp; mediana +11.29 pp, DE 9.62 pp con igual peso por segmento. 9.41 % de padres está a ≤2 pp de la referencia y 22.54 % tiene NS/LN≥10 %. Al separar U/R/M hay 46 hijos con tasa no definida (LN=6,484); no se vuelven cero. Los agregados de la ficha incluyen todos sus hijos, no sólo los elegibles. Las medias por cruce mantienen el signo del padre en esta evidencia, pero esconden cambios locales. Edad agrupada, signo convencional, NS y soporte desigual limitan la interpretación. U/R/M identifica secciones electorales, no localidad ni residencia individual; tampoco demuestra motivaciones o eficacia institucional.

No se proponen campañas, canales ni mensajes personalizados por edad, sexo, territorio o conducta. El uso de esta ficha es descriptivo y agregado.
