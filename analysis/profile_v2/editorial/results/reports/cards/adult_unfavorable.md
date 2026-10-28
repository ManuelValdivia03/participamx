# Participación adulta con mayor volumen nominal

`adult_unfavorable` · recomendación editorial provisional

35–59 años · 57.00 % de participación observada; referencia comparable 62.96 % (-5.96 pp). Segmentos municipales H/M de 2024; cruces por tipo de sección electoral en la ficha.

Estos segmentos de 35–59 años concentran el mayor volumen nominal de las seis fichas, con 22.44 millones de registros LN. Su participación agregada es 57.00 %, frente a una referencia de 62.96 %. La distancia negativa varía por sexo y tipo de sección electoral. El volumen no equivale a mayor extensión municipal, y algunos subsegmentos presentan una diferencia positiva.

## Tres hallazgos verificables

- LN=22,444,975 (22.83 % del LN anual), 1,018 municipios; participación 57.00 %, referencia 62.96 %, Δ=−5.96 pp. Fuentes: [v1_profiles](../source_catalog.md#v1-profiles)

- En 35–59, la distancia urbana es −5.04 pp en hombres y −5.55 pp en mujeres; la mixta es −7.77 y −8.84 pp. El menor alejamiento urbano agregado también aparece al separar sexos. No convierte en positivos todos los segmentos urbanos ni demuestra que la sección determine la participación. Fuentes: [joint_evidence](../source_catalog.md#joint-evidence), [section_evidence](../source_catalog.md#section-evidence), [prior_interpretation](../source_catalog.md#prior-interpretation)

- 468/4,055 hijos con soporte (11.54 %) cambian de signo frente al padre V1, con LN=1,662,772 (7.41 % del LN de los hijos elegibles de la ficha). De esos cambios, 246 están a ≤2 pp de cero en el hijo y 276 en el padre; las dos cuentas se superponen. 95 tienen NS alto y 259 menos de cinco secciones, banderas también superpuestas. No todos los cambios son diferencias grandes ni datos erróneos. Fuentes: [profile_evidence](../source_catalog.md#profile-evidence), [reversal_evidence](../source_catalog.md#reversal-evidence), [reversal_quality](../source_catalog.md#reversal-quality)

## Participación y referencia

De 20,904,807 registros con participación especificada, 11,914,868 corresponden a SV: 57.00 %. La referencia de 62.96 % combina las tasas nacionales de esta banda para H/M usando los denominadores locales SV+NV como pesos. Su resta es -5.96 pp. NS no entra como abstención; la referencia es descriptiva, no una predicción.

## Sexo y tipo de sección electoral: cruce conjunto

Las mujeres aportan 48.67 % de los segmentos V1 y 52.81 % del LN. El resto corresponde a hombres en estas fichas H/M. Cada sexo se contrasta con su propia referencia; sus conjuntos de municipios pueden diferir. La tabla conjunta permite comparar U/R/M dentro del mismo sexo sin atribuirle un efecto causal.

Composición nominal por tipo de sección electoral: urbana 73.87 %; rural 13.27 %; mixta 12.86 %. Urbana reúne más de la mitad del LN en esta ficha, como en las otras cinco: no es un rasgo exclusivo. En 35–59, la distancia urbana es −5.04 pp en hombres y −5.55 pp en mujeres; la mixta es −7.77 y −8.84 pp. El menor alejamiento urbano agregado también aparece al separar sexos. No convierte en positivos todos los segmentos urbanos ni demuestra que la sección determine la participación.

| SEXO | TIPOSEC | LN | specified_count | participation_observed_pct | matched_age_sex_reference_pct | delta_pp | eligible_cells | eligible_flip_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | M | 1421546 | 1331310 | 49.52 | 57.30 | -7.77 | 772 | 81 |
| 0 | R | 1562489 | 1450257 | 49.73 | 57.30 | -7.57 | 680 | 80 |
| 0 | U | 7608522 | 7073708 | 52.25 | 57.30 | -5.04 | 647 | 96 |
| 1 | M | 1465878 | 1372143 | 59.16 | 68.01 | -8.84 | 728 | 72 |
| 1 | R | 1415011 | 1308114 | 61.08 | 68.01 | -6.93 | 633 | 79 |
| 1 | U | 8971529 | 8369275 | 62.46 | 68.01 | -5.55 | 595 | 60 |

SEXO: 0=Hombres, 1=Mujeres. U=Urbana, R=Rural, M=Mixta. Tasas en %; diferencias en pp. Cada fila suma hijos de una misma banda, sexo y tipo, en los municipios de la ficha V1. Las tasas conservan hijos con y sin soporte; las últimas dos columnas cuentan exclusivamente hijos elegibles. No son secciones únicas ni personas.

Fuentes exactas: [catálogo](../source_catalog.md), `joint_evidence`, `section_evidence`, `sex_evidence`; filtro `profile_id=adult_unfavorable`. Datos descargables: [cruce conjunto](../../evidence/profile_sex_section.csv), [resumen U/R/M](../../evidence/profile_section.csv).

## Territorio

Mayores aportaciones de LN a la ficha: JALISCO 10.35 %; NUEVO LEON 7.35 %; VERACRUZ 7.24 %. El denominador es el LN de esta ficha. En JALISCO, su LN representa 35.10 % del núcleo estatal H/M 18–100, un denominador distinto. Los municipios pueden participar en otras fichas; no se suman sus coberturas ni se atribuye el patrón a todos sus habitantes.

Fuente: [distribución estatal](../../evidence/profile_state.csv), mismo profile_id; se distingue cuota de la ficha de cuota del núcleo estatal.

## Cambios de signo al desagregar

468/4,055 hijos con soporte (11.54 %) cambian de signo frente al padre V1, con LN=1,662,772 (7.41 % del LN de los hijos elegibles de la ficha). De esos cambios, 246 están a ≤2 pp de cero en el hijo y 276 en el padre; las dos cuentas se superponen. 95 tienen NS alto y 259 menos de cinco secciones, banderas también superpuestas. No todos los cambios son diferencias grandes ni datos erróneos.

Ejemplo seleccionado por mayor LN entre los hijos elegibles que cambian de signo, sin elegir la diferencia máxima: entidad 11, municipio 20, mujeres, banda 35-59, sección electoral urbana. LN=249,437, SV+NV=242,862; tasa=68.34 %, referencia=68.01 %, Δ hijo=+0.33 pp; Δ padre=-0.25 pp. row_id=experimental_2024|11|20|35-59|1|U. No es un caso representativo de todos los cambios.

Los signos de padre e hijo usan la **misma referencia nacional de banda/sexo**. Se decide por productos cruzados de enteros Python, antes de redondear. No se confunde un cambio de signo por desagregación con un cambio provocado por usar una referencia U/R/M distinta.

Fuente: [cambios elegibles](../../evidence/eligible_sign_reversals.parquet), [calidad y todas las poblaciones](../../evidence/reversal_quality.csv) y [ejemplos deterministas](../../evidence/reversal_examples.csv).

## Variación interna y límites

La mitad central de las diferencias V1 va de -10.87 a -2.83 pp; mediana -5.95 pp, DE 7.21 pp con igual peso por segmento. 18.22 % de padres está a ≤2 pp de la referencia y 16.69 % tiene NS/LN≥10 %. Al separar U/R/M hay 20 hijos con tasa no definida (LN=7,067); no se vuelven cero. Los agregados de la ficha incluyen todos sus hijos, no sólo los elegibles. Las medias por cruce mantienen el signo del padre en esta evidencia, pero esconden cambios locales. Edad agrupada, signo convencional, NS y soporte desigual limitan la interpretación. U/R/M identifica secciones electorales, no localidad ni residencia individual; tampoco demuestra motivaciones o eficacia institucional.

No se proponen campañas, canales ni mensajes personalizados por edad, sexo, territorio o conducta. El uso de esta ficha es descriptivo y agregado.
