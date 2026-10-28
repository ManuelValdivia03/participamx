# Participación de mayores en el nivel más alto

`older_favorable` · recomendación editorial provisional

60–100 años · 77.26 % de participación observada; referencia comparable 71.48 % (+5.78 pp). Segmentos municipales H/M de 2024; cruces por tipo de sección electoral en la ficha.

Estos segmentos de 60–100 años presentan la participación absoluta más alta de las seis fichas: 77.26 %. Su referencia también es elevada, 71.48 %, por lo que la diferencia relativa no es la mayor. Las tasas agregadas por tipo de sección electoral son cercanas, sin demostrar equivalencia estadística ni comportamiento uniforme. Las mujeres predominan en LN, pero no en número de segmentos.

## Tres hallazgos verificables

- Participación 77.26 %, referencia 71.48 %, Δ=+5.78 pp; no es la mayor diferencia positiva relativa. Fuentes: [v1_profiles](../source_catalog.md#v1-profiles)

- En 60–100, los hombres registran diferencias de +4.95 a +6.07 pp según tipo de sección; las mujeres, de +5.42 a +6.24 pp. El máximo entre hombres es rural y entre mujeres urbano. Las tasas agregadas U/R/M van de 76.71 % a 77.44 %: una amplitud de 0.73 pp, sin prueba de equivalencia ni homogeneidad local. Fuentes: [joint_evidence](../source_catalog.md#joint-evidence), [section_evidence](../source_catalog.md#section-evidence), [prior_interpretation](../source_catalog.md#prior-interpretation)

- 444/5,406 hijos con soporte (8.21 %) cambian de signo frente al padre V1, con LN=402,323 (3.90 % del LN de los hijos elegibles de la ficha). De esos cambios, 268 están a ≤2 pp de cero en el hijo y 263 en el padre; las dos cuentas se superponen. 96 tienen NS alto y 259 menos de cinco secciones, banderas también superpuestas. No todos los cambios son diferencias grandes ni datos erróneos. Fuentes: [profile_evidence](../source_catalog.md#profile-evidence), [reversal_evidence](../source_catalog.md#reversal-evidence), [reversal_quality](../source_catalog.md#reversal-quality)

## Participación y referencia

De 9,813,068 registros con participación especificada, 7,581,710 corresponden a SV: 77.26 %. La referencia de 71.48 % combina las tasas nacionales de esta banda para H/M usando los denominadores locales SV+NV como pesos. Su resta es +5.78 pp. NS no entra como abstención; la referencia es descriptiva, no una predicción.

## Sexo y tipo de sección electoral: cruce conjunto

Las mujeres aportan 46.93 % de los segmentos V1 y 53.16 % del LN. El resto corresponde a hombres en estas fichas H/M. Cada sexo se contrasta con su propia referencia; sus conjuntos de municipios pueden diferir. La tabla conjunta permite comparar U/R/M dentro del mismo sexo sin atribuirle un efecto causal.

Composición nominal por tipo de sección electoral: urbana 73.84 %; rural 15.95 %; mixta 10.21 %. Urbana reúne más de la mitad del LN en esta ficha, como en las otras cinco: no es un rasgo exclusivo. En 60–100, los hombres registran diferencias de +4.95 a +6.07 pp según tipo de sección; las mujeres, de +5.42 a +6.24 pp. El máximo entre hombres es rural y entre mujeres urbano. Las tasas agregadas U/R/M van de 76.71 % a 77.44 %: una amplitud de 0.73 pp, sin prueba de equivalencia ni homogeneidad local.

| SEXO | TIPOSEC | LN | specified_count | participation_observed_pct | matched_age_sex_reference_pct | delta_pp | eligible_cells | eligible_flip_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | M | 530368 | 497203 | 77.16 | 72.21 | 4.95 | 1045 | 113 |
| 0 | R | 915264 | 851133 | 78.29 | 72.21 | 6.07 | 936 | 65 |
| 0 | U | 3410980 | 3236613 | 77.57 | 72.21 | 5.36 | 888 | 49 |
| 1 | M | 528128 | 495342 | 76.25 | 70.84 | 5.42 | 924 | 86 |
| 1 | R | 738016 | 690922 | 76.40 | 70.84 | 5.56 | 818 | 95 |
| 1 | U | 4245080 | 4041855 | 77.08 | 70.84 | 6.24 | 795 | 36 |

SEXO: 0=Hombres, 1=Mujeres. U=Urbana, R=Rural, M=Mixta. Tasas en %; diferencias en pp. Cada fila suma hijos de una misma banda, sexo y tipo, en los municipios de la ficha V1. Las tasas conservan hijos con y sin soporte; las últimas dos columnas cuentan exclusivamente hijos elegibles. No son secciones únicas ni personas.

Fuentes exactas: [catálogo](../source_catalog.md), `joint_evidence`, `section_evidence`, `sex_evidence`; filtro `profile_id=older_favorable`. Datos descargables: [cruce conjunto](../../evidence/profile_sex_section.csv), [resumen U/R/M](../../evidence/profile_section.csv).

## Territorio

Mayores aportaciones de LN a la ficha: MEXICO 21.38 %; CIUDAD DE MEXICO 17.44 %; VERACRUZ 9.95 %. El denominador es el LN de esta ficha. En MEXICO, su LN representa 17.02 % del núcleo estatal H/M 18–100, un denominador distinto. Los municipios pueden participar en otras fichas; no se suman sus coberturas ni se atribuye el patrón a todos sus habitantes.

Fuente: [distribución estatal](../../evidence/profile_state.csv), mismo profile_id; se distingue cuota de la ficha de cuota del núcleo estatal.

## Cambios de signo al desagregar

444/5,406 hijos con soporte (8.21 %) cambian de signo frente al padre V1, con LN=402,323 (3.90 % del LN de los hijos elegibles de la ficha). De esos cambios, 268 están a ≤2 pp de cero en el hijo y 263 en el padre; las dos cuentas se superponen. 96 tienen NS alto y 259 menos de cinco secciones, banderas también superpuestas. No todos los cambios son diferencias grandes ni datos erróneos.

Ejemplo seleccionado por mayor LN entre los hijos elegibles que cambian de signo, sin elegir la diferencia máxima: entidad 22, municipio 14, mujeres, banda 60-100, sección electoral mixta. LN=7,029, SV+NV=6,824; tasa=68.17 %, referencia=70.84 %, Δ hijo=-2.66 pp; Δ padre=+4.28 pp. row_id=experimental_2024|22|14|60-100|1|M. No es un caso representativo de todos los cambios.

Los signos de padre e hijo usan la **misma referencia nacional de banda/sexo**. Se decide por productos cruzados de enteros Python, antes de redondear. No se confunde un cambio de signo por desagregación con un cambio provocado por usar una referencia U/R/M distinta.

Fuente: [cambios elegibles](../../evidence/eligible_sign_reversals.parquet), [calidad y todas las poblaciones](../../evidence/reversal_quality.csv) y [ejemplos deterministas](../../evidence/reversal_examples.csv).

## Variación interna y límites

La mitad central de las diferencias V1 va de +3.70 a +10.90 pp; mediana +7.03 pp, DE 5.15 pp con igual peso por segmento. 13.24 % de padres está a ≤2 pp de la referencia y 20.15 % tiene NS/LN≥10 %. Al separar U/R/M hay 33 hijos con tasa no definida (LN=2,550); no se vuelven cero. Los agregados de la ficha incluyen todos sus hijos, no sólo los elegibles. Las medias por cruce mantienen el signo del padre en esta evidencia, pero esconden cambios locales. Edad agrupada, signo convencional, NS y soporte desigual limitan la interpretación. U/R/M identifica secciones electorales, no localidad ni residencia individual; tampoco demuestra motivaciones o eficacia institucional.

No se proponen campañas, canales ni mensajes personalizados por edad, sexo, territorio o conducta. El uso de esta ficha es descriptivo y agregado.
