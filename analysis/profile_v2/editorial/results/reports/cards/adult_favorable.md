# Participación adulta con mayor presencia municipal

`adult_favorable` · recomendación editorial provisional

35–59 años · 69.33 % de participación observada; referencia comparable 62.82 % (+6.51 pp). Segmentos municipales H/M de 2024; cruces por tipo de sección electoral en la ficha.

Estos segmentos de 35–59 años tienen la presencia municipal más extensa de las seis fichas: 1,641 municipios. Su participación agregada es 69.33 %, frente a una referencia de 62.82 %. Las diferencias positivas son más amplias en secciones electorales rurales que urbanas al resumir esta categoría, pero no abarcan uniformemente a todos sus subsegmentos ni prueban un efecto del contexto.

## Tres hallazgos verificables

- 3,015 segmentos en 1,641 municipios; participación 69.33 %, referencia 62.82 %, Δ=+6.51 pp. Fuentes: [v1_profiles](../source_catalog.md#v1-profiles)

- En 35–59, la diferencia rural es +8.96 pp en hombres y +9.53 pp en mujeres; la urbana es +5.30 y +5.86 pp. Este orden se observa en ambos sexos dentro de la ficha seleccionada. No estima un efecto rural: cambian los municipios y su composición, y las referencias sólo ajustan banda/sexo. Fuentes: [joint_evidence](../source_catalog.md#joint-evidence), [section_evidence](../source_catalog.md#section-evidence), [prior_interpretation](../source_catalog.md#prior-interpretation)

- 491/6,778 hijos con soporte (7.24 %) cambian de signo frente al padre V1, con LN=996,893 (4.91 % del LN de los hijos elegibles de la ficha). De esos cambios, 255 están a ≤2 pp de cero en el hijo y 279 en el padre; las dos cuentas se superponen. 119 tienen NS alto y 300 menos de cinco secciones, banderas también superpuestas. No todos los cambios son diferencias grandes ni datos erróneos. Fuentes: [profile_evidence](../source_catalog.md#profile-evidence), [reversal_evidence](../source_catalog.md#reversal-evidence), [reversal_quality](../source_catalog.md#reversal-quality)

## Participación y referencia

De 19,158,906 registros con participación especificada, 13,282,203 corresponden a SV: 69.33 %. La referencia de 62.82 % combina las tasas nacionales de esta banda para H/M usando los denominadores locales SV+NV como pesos. Su resta es +6.51 pp. NS no entra como abstención; la referencia es descriptiva, no una predicción.

## Sexo y tipo de sección electoral: cruce conjunto

Las mujeres aportan 50.98 % de los segmentos V1 y 51.57 % del LN. El resto corresponde a hombres en estas fichas H/M. Cada sexo se contrasta con su propia referencia; sus conjuntos de municipios pueden diferir. La tabla conjunta permite comparar U/R/M dentro del mismo sexo sin atribuirle un efecto causal.

Composición nominal por tipo de sección electoral: urbana 66.31 %; rural 20.34 %; mixta 13.35 %. Urbana reúne más de la mitad del LN en esta ficha, como en las otras cinco: no es un rasgo exclusivo. En 35–59, la diferencia rural es +8.96 pp en hombres y +9.53 pp en mujeres; la urbana es +5.30 y +5.86 pp. Este orden se observa en ambos sexos dentro de la ficha seleccionada. No estima un efecto rural: cambian los municipios y su composición, y las referencias sólo ajustan banda/sexo.

| SEXO | TIPOSEC | LN | specified_count | participation_observed_pct | matched_age_sex_reference_pct | delta_pp | eligible_cells | eligible_flip_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | M | 1249442 | 1171482 | 63.80 | 57.30 | 6.50 | 1222 | 117 |
| 0 | R | 1882861 | 1745894 | 66.26 | 57.30 | 8.96 | 1117 | 115 |
| 0 | U | 6716521 | 6359307 | 62.60 | 57.30 | 5.30 | 959 | 43 |
| 1 | M | 1466197 | 1377465 | 75.33 | 68.01 | 7.32 | 1275 | 95 |
| 1 | R | 2253946 | 2099104 | 77.54 | 68.01 | 9.53 | 1176 | 69 |
| 1 | U | 6768734 | 6405654 | 73.87 | 68.01 | 5.86 | 1029 | 52 |

SEXO: 0=Hombres, 1=Mujeres. U=Urbana, R=Rural, M=Mixta. Tasas en %; diferencias en pp. Cada fila suma hijos de una misma banda, sexo y tipo, en los municipios de la ficha V1. Las tasas conservan hijos con y sin soporte; las últimas dos columnas cuentan exclusivamente hijos elegibles. No son secciones únicas ni personas.

Fuentes exactas: [catálogo](../source_catalog.md), `joint_evidence`, `section_evidence`, `sex_evidence`; filtro `profile_id=adult_favorable`. Datos descargables: [cruce conjunto](../../evidence/profile_sex_section.csv), [resumen U/R/M](../../evidence/profile_section.csv).

## Territorio

Mayores aportaciones de LN a la ficha: MEXICO 21.52 %; CIUDAD DE MEXICO 17.35 %; PUEBLA 7.34 %. El denominador es el LN de esta ficha. En MEXICO, su LN representa 33.60 % del núcleo estatal H/M 18–100, un denominador distinto. Los municipios pueden participar en otras fichas; no se suman sus coberturas ni se atribuye el patrón a todos sus habitantes.

Fuente: [distribución estatal](../../evidence/profile_state.csv), mismo profile_id; se distingue cuota de la ficha de cuota del núcleo estatal.

## Cambios de signo al desagregar

491/6,778 hijos con soporte (7.24 %) cambian de signo frente al padre V1, con LN=996,893 (4.91 % del LN de los hijos elegibles de la ficha). De esos cambios, 255 están a ≤2 pp de cero en el hijo y 279 en el padre; las dos cuentas se superponen. 119 tienen NS alto y 300 menos de cinco secciones, banderas también superpuestas. No todos los cambios son diferencias grandes ni datos erróneos.

Ejemplo seleccionado por mayor LN entre los hijos elegibles que cambian de signo, sin elegir la diferencia máxima: entidad 22, municipio 14, hombres, banda 35-59, sección electoral mixta. LN=24,927, SV+NV=24,211; tasa=53.42 %, referencia=57.30 %, Δ hijo=-3.88 pp; Δ padre=+0.68 pp. row_id=experimental_2024|22|14|35-59|0|M. No es un caso representativo de todos los cambios.

Los signos de padre e hijo usan la **misma referencia nacional de banda/sexo**. Se decide por productos cruzados de enteros Python, antes de redondear. No se confunde un cambio de signo por desagregación con un cambio provocado por usar una referencia U/R/M distinta.

Fuente: [cambios elegibles](../../evidence/eligible_sign_reversals.parquet), [calidad y todas las poblaciones](../../evidence/reversal_quality.csv) y [ejemplos deterministas](../../evidence/reversal_examples.csv).

## Variación interna y límites

La mitad central de las diferencias V1 va de +4.84 a +16.35 pp; mediana +9.96 pp, DE 7.66 pp con igual peso por segmento. 10.58 % de padres está a ≤2 pp de la referencia y 21.26 % tiene NS/LN≥10 %. Al separar U/R/M hay 44 hijos con tasa no definida (LN=7,908); no se vuelven cero. Los agregados de la ficha incluyen todos sus hijos, no sólo los elegibles. Las medias por cruce mantienen el signo del padre en esta evidencia, pero esconden cambios locales. Edad agrupada, signo convencional, NS y soporte desigual limitan la interpretación. U/R/M identifica secciones electorales, no localidad ni residencia individual; tampoco demuestra motivaciones o eficacia institucional.

No se proponen campañas, canales ni mensajes personalizados por edad, sexo, territorio o conducta. El uso de esta ficha es descriptivo y agregado.
