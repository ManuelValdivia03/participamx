# Candidatos sociodemográficos agregados de participación · 2024

**Seis candidatos son viables como segmentación explícita para revisión, no como seis clusters naturales.** Cada uno reúne segmentos con soporte y diferencias medibles frente a pares nacionales; edad y signo de participación definen las etiquetas. El contexto U/R/M enriquece la descripción, pero no valida seis tipos independientes. No se declaran perfiles definitivos.

Se propone revisar las seis fichas, mostrar intensidad y advertencia cerca de cero, y conservar R2 como complemento. Reducir a cuatro o cinco no aumenta cobertura: las fusiones diagnósticas sólo eliminan detalle etario o mezclan signos opuestos. La evidencia no exige un número natural de perfiles.

## Alcance y alineación con el reto

Se atienden los entregables de cuatro a seis perfiles descritos en la solicitud: reglas, caracterización demográfica/territorial, fichas visuales y estrategias cívicas. La convocatoria oficial no está incorporada en el repositorio y la búsqueda pública de esta revisión no localizó una fuente primaria verificable del Reto 1. La conformidad formal con la rúbrica queda pendiente; no se afirma certificación oficial.

Se revisaron los informes demographic_pilot, demographic_representation_comparison, participation_pattern_review, pattern_algorithm_comparison, age_band_representation_review, cluster_feature_review, technical_cleaning, outlier_review y el plan de limpieza. Se reutilizan broad/life_stage, contratos, diccionarios oficiales conservados y referencias nacionales. No se entrenó ningún modelo, no se reinterpretaron CSV ni registros limpios.

Unidad B = municipio × intervalo × sexo. Unidad R2 = municipio × sexo con tasas de tres edades como coordenadas. Una segmentación por reglas, un clustering aprendido y el comportamiento individual son conceptos distintos. Ningún registro analítico identifica votantes individuales.

## Regla, denominadores y población

Para cada intervalo y sexo la referencia es ΣSV/Σ(SV+NV), usando **todos** los segmentos originales de 2024 antes de seleccionar soporte. La participación local es SV/(SV+NV), NULL con denominador cero; NS no se suma a NV. El signo se determina por productos cruzados de enteros Python, evitando errores de redondeo y desbordamiento int64. Un empate exacto queda `at_reference`, sin forzarlo a favorable/desfavorable.

Las fichas principales requieren H/M, 18–100, LN≥100, SV+NV≥100 y filas fuente≥5, con tasa definida. NS≥10 % advierte cobertura y **no excluye** automáticamente. `rule_candidate_id` conserva la pertenencia por signo de los segmentos definidos sin soporte; `candidate_id` sólo identifica fichas con soporte. `assignment_status` es disjunto; las banderas de calidad pueden superponerse. 101+ y SEXO=2 quedan complementarios sin inventar pares H/M.

Las filas fuente son celdas originales, no personas ni secciones independientes. Se mantiene la edad exacta por referencia al Parquet previo y su hash, sin sustituirla por el intervalo. Claves territoriales y SEXO siguen como texto; district_reference_year se conserva.

| assignment_status | segments | LN | SV | NV | NS | source_row_count |
| --- | --- | --- | --- | --- | --- | --- |
| complementary | 2873 | 13302 | 2328 | 10127 | 847 | 12996 |
| insufficient_support | 600 | 47293 | 22033 | 15620 | 9640 | 15724 |
| supported_candidate | 14190 | 98203780 | 54874867 | 37079719 | 6249194 | 9738289 |
| undefined_rate | 72 | 65973 | 0 | 0 | 65973 | 6721 |

Las proporciones del informe están en [0,1]; multiplicar por 100 para porcentaje. Las diferencias de proporciones se multiplican por 100 para puntos porcentuales (pp). Los seis candidatos son disjuntos a nivel de segmento y sus conteos sí se suman; sus municipios se superponen y **no** se suman como cobertura única.

Referencias nacionales H/M del núcleo:

| age_band | SEXO | LN | SV | NV | NS | national_rate |
| --- | --- | --- | --- | --- | --- | --- |
| 18-34 | 0 | 18233040 | 7452388 | 9586174 | 1194478 | 0.4374 |
| 18-34 | 1 | 18541903 | 9699349 | 7630162 | 1212392 | 0.5597 |
| 35-59 | 0 | 20461145 | 10964998 | 8172194 | 1323953 | 0.5730 |
| 35-59 | 1 | 22361112 | 14238016 | 6698205 | 1424891 | 0.6801 |
| 60-100 | 0 | 8527600 | 5766990 | 2219183 | 541427 | 0.7221 |
| 60-100 | 1 | 10192246 | 6775159 | 2789421 | 627666 | 0.7084 |

## Tamaño, participación y cobertura

| candidate_id | segments | municipalities | states | LN | SV | NV | NS | participation_observed | matched_peer_reference | participation_delta | nominal_coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adult_favorable | 3015 | 1641 | 31 | 20337701 | 13282203 | 5876703 | 1178795 | 0.6933 | 0.6282 | 0.0651 | 0.2068 |
| adult_unfavorable | 1767 | 1018 | 31 | 22444975 | 11914868 | 8989939 | 1540168 | 0.5700 | 0.6296 | -0.0596 | 0.2283 |
| older_favorable | 2606 | 1445 | 30 | 10367836 | 7581710 | 2231358 | 554768 | 0.7726 | 0.7148 | 0.0578 | 0.1054 |
| older_unfavorable | 2078 | 1189 | 30 | 8319793 | 4949523 | 2772367 | 597903 | 0.6410 | 0.7144 | -0.0734 | 0.0846 |
| young_favorable | 2688 | 1522 | 31 | 17237993 | 9276190 | 6888087 | 1073716 | 0.5739 | 0.4969 | 0.0769 | 0.1753 |
| young_unfavorable | 2036 | 1200 | 31 | 19495482 | 7870373 | 10321265 | 1303844 | 0.4326 | 0.5010 | -0.0683 | 0.1983 |

| available_segments | classified_segments | municipalities | original_municipalities | LN | nominal_fraction | high_ns_segments | near_reference_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 17735 | 14190 | 2402 | 2477 | 98203780 | 0.9987 | 2782 | 0.1320 |

La referencia agregada de cada ficha ajusta la mezcla local de sexo: Σ(denominador del segmento × referencia de su mismo sexo/banda)/Σdenominador. La diferencia agregada resta esa referencia de ΣSV/Σ(SV+NV). Se conserva también media simple, mediana y cuartiles de diferencias, que responden a otra ponderación. No se resta una única tasa nacional incondicional ni se promedian tasas municipales para obtener la participación agregada.

![Tamaño y diferencias](../charts/profile_candidates_review/candidate_overview.png)

| candidate_id | delta_q1 | delta_median | delta_q3 | specified_min | specified_median | sections_min | sections_median | low_section_segments | high_ns_fraction | near_reference_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adult_favorable | 0.0484 | 0.0996 | 0.1635 | 101 | 2,036.0000 | 1 | 9.0000 | 792 | 0.2126 | 0.1058 |
| adult_unfavorable | -0.1087 | -0.0595 | -0.0283 | 100 | 2,694.0000 | 1 | 13.0000 | 566 | 0.1669 | 0.1822 |
| older_favorable | 0.0370 | 0.0703 | 0.1090 | 100 | 1,010.5000 | 1 | 9.0000 | 717 | 0.2015 | 0.1324 |
| older_unfavorable | -0.1319 | -0.0754 | -0.0334 | 100 | 1,339.0000 | 1 | 13.0000 | 546 | 0.1891 | 0.1554 |
| young_favorable | 0.0571 | 0.1129 | 0.1857 | 101 | 1,841.0000 | 1 | 9.0000 | 660 | 0.2254 | 0.0941 |
| young_unfavorable | -0.1450 | -0.0782 | -0.0348 | 100 | 2,230.0000 | 1 | 12.0000 | 640 | 0.1582 | 0.1528 |

## Frontera e intensidad: sensibilidad

La frontera cero es una convención transparente, no una discontinuidad electoral. Se mide la zona inclusiva abs(Δ)≤1, 2 y 5 pp. Estas bandas son diagnósticos operativos, no errores de estimación ni umbrales oficiales. Los segmentos próximos a cero mantienen su etiqueta provisional y una advertencia; no se afirma que ±0.01 pp describa conductas distintas. La versión conservadora para comunicar diferencias destacaría magnitud y podría dejar esa zona sin rótulo favorable/desfavorable, previa decisión humana.

| candidate_id | threshold_pp | near_segments | near_fraction | near_LN | strong_segments | strong_LN |
| --- | --- | --- | --- | --- | --- | --- |
| adult_favorable | 2.0000 | 319 | 0.1058 | 4419448 | 2696 | 15918253 |
| adult_unfavorable | 2.0000 | 322 | 0.1822 | 5847545 | 1445 | 16597430 |
| older_favorable | 2.0000 | 345 | 0.1324 | 1744789 | 2261 | 8623047 |
| older_unfavorable | 2.0000 | 323 | 0.1554 | 1650510 | 1755 | 6669283 |
| young_favorable | 2.0000 | 253 | 0.0941 | 3661580 | 2435 | 13576413 |
| young_unfavorable | 2.0000 | 311 | 0.1528 | 4212412 | 1725 | 15283070 |

![Frontera e intensidad](../charts/profile_candidates_review/threshold_distributions.png)

Las bandas descriptivas de no especificación [SV/LN, (SV+NS)/LN] abarcan escenarios extremos de NS, no intervalos de confianza. Se calcula qué segmentos conservarían el signo ante todos esos escenarios respecto de la referencia observada fija. Esto no resuelve la no especificación de la propia referencia nacional; también se guarda el diagnóstico más exigente contra su intervalo NS. No son imputaciones ni predicciones.

## Edad, sexo y contexto territorial

| age_band | context_total_variation | mean_delta_gap_pp | median_delta_gap_pp | women_segment_fraction_gap |
| --- | --- | --- | --- | --- |
| 18-34 | 0.0165 | 23.3002 | 19.1109 | 0.1164 |
| 35-59 | 0.0756 | 19.0360 | 15.9171 | 0.0231 |
| 60-100 | 0.0742 | 16.8071 | 14.5725 | -0.0774 |

Diferencias U/R/M entre signos de la misma edad se expresan como distancia de variación total de composiciones LN (0 idénticas, 1 disjuntas). No demuestran separación natural ni efectos causales. Se muestran volumen por entidad y proporción de su núcleo estatal: el mayor volumen de un estado no equivale a mayor prevalencia relativa. No se inventan regiones socioculturales.

| candidate_id | state_name_label | segments | LN | share_of_candidate_LN | share_of_state_core_LN |
| --- | --- | --- | --- | --- | --- |
| adult_favorable | MEXICO | 222 | 4376534 | 0.2152 | 0.3360 |
| adult_favorable | CIUDAD DE MEXICO | 32 | 3529579 | 0.1735 | 0.4458 |
| adult_favorable | PUEBLA | 411 | 1493554 | 0.0734 | 0.3000 |
| adult_unfavorable | JALISCO | 128 | 2322873 | 0.1035 | 0.3510 |
| adult_unfavorable | NUEVO LEON | 40 | 1649162 | 0.0735 | 0.3693 |
| adult_unfavorable | VERACRUZ | 202 | 1625540 | 0.0724 | 0.2674 |
| older_favorable | MEXICO | 238 | 2217018 | 0.2138 | 0.1702 |
| older_favorable | CIUDAD DE MEXICO | 32 | 1808586 | 0.1744 | 0.2284 |
| older_favorable | VERACRUZ | 341 | 1031177 | 0.0995 | 0.1696 |
| older_unfavorable | JALISCO | 232 | 897250 | 0.1078 | 0.1356 |
| older_unfavorable | MICHOACAN | 196 | 759796 | 0.0913 | 0.2027 |
| older_unfavorable | NUEVO LEON | 72 | 694893 | 0.0835 | 0.1556 |
| young_favorable | MEXICO | 215 | 3856223 | 0.2237 | 0.2960 |
| young_favorable | CIUDAD DE MEXICO | 32 | 2578840 | 0.1496 | 0.3257 |
| young_favorable | PUEBLA | 379 | 1345660 | 0.0781 | 0.2703 |
| young_unfavorable | VERACRUZ | 357 | 1856783 | 0.0952 | 0.3054 |
| young_unfavorable | GUANAJUATO | 55 | 1354661 | 0.0695 | 0.2804 |
| young_unfavorable | JALISCO | 74 | 1325025 | 0.0680 | 0.2002 |

![Secciones electorales](../charts/profile_candidates_review/section_context.png)

U/R/M significa sección Urbana/Rural/Mixta del marco electoral, no localidad ni residencia urbana individual. Las sumas LN_U/LN_R/LN_M concilian con cada segmento. Se dispone de secciones distintas **por segmento** y de un inventario territorial general, pero no de sus claves por banda/sexo en los agregados reutilizados. Por eso se informa distribución de section_count y no una suma falsa de secciones únicas por candidato. Una sección puede aportar a ambos sexos y varios candidatos.

## Antecedentes de clustering y alternativas de cuatro/cinco

| scheme | k | n | silhouette | age_r2 | age_band_purity | within_age_sex_rate_r2 |
| --- | --- | --- | --- | --- | --- | --- |
| life_stage | 4 | 22282 | 0.3964 | 0.8025 | 0.5749 | 0.5801 |
| life_stage | 5 | 22282 | 0.3798 | 0.8252 | 0.6392 | 0.6631 |
| life_stage | 6 | 22282 | 0.4100 | 0.8874 | 0.6851 | 0.6827 |
| broad | 4 | 14190 | 0.4629 | 0.8494 | 0.8092 | 0.5642 |
| broad | 5 | 14190 | 0.5025 | 0.9359 | 0.9478 | 0.6008 |
| broad | 6 | 14190 | 0.5141 | 0.9561 | 0.9579 | 0.7018 |

Estas métricas se reutilizan del piloto B broad/life_stage, K=4/5/6, semilla 17; no son nuevas validaciones de las reglas. En broad se enlazan etiquetas originales a los mismos row_id y se guardan cruces descriptivos. No se calcula ARI entre broad y life_stage ni entre B y R2. Los informes posteriores hallaron gradientes y componentes superpuestas; la nitidez de una regla no prueba existencia de clusters.

| design | groups | segments | LN | within_group_delta_sd_pp | groups_mixing_signs | coverage_gain |
| --- | --- | --- | --- | --- | --- | --- |
| six | 6 | 14190 | 98203780 | 7.6822 | 0 | 0 |
| four | 4 | 14190 | 98203780 | 7.7602 | 0 | 0 |
| five | 5 | 14190 | 98203780 | 9.0571 | 1 | 0 |

Sólo se diagnostican fusiones explícitas sobre los mismos segmentos: cuatro reúne adultos y mayores del mismo signo; cinco reúne ambos signos de mayores. No se cambia la referencia por banda ni se reconstruyen observaciones. La reducción conserva exactamente cobertura/LN, pero aumenta heterogeneidad o mezcla signos: no se promueve una alternativa de cuatro/cinco sin una mejora sustantiva de claridad respaldada por revisión electoral. La tasa y el signo son parte de la definición; no usar Silhouette para “demostrar” esos perfiles.

## Complemento R2

| candidate_id | r2_status | segments | LN | SV | NV | NS | source_row_count | sex_2_source_rows | sex_2_nominal_count | within_candidate_segment_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adult_favorable | r2_0 | 1686 | 6615676 | 4498868 | 1716920 | 399888 | 620665 | 0 | 0 | 0.5592 |
| adult_favorable | r2_1 | 1272 | 13709014 | 8777257 | 4157872 | 773885 | 1004353 | 0 | 0 | 0.4219 |
| adult_favorable | unavailable | 57 | 13011 | 6078 | 1911 | 5022 | 1818 | 0 | 0 | 0.0189 |
| adult_unfavorable | r2_0 | 494 | 3325577 | 1687339 | 1371031 | 267207 | 319970 | 0 | 0 | 0.2796 |
| adult_unfavorable | r2_1 | 1196 | 19105461 | 10222025 | 7613628 | 1269808 | 1512809 | 0 | 0 | 0.6769 |
| adult_unfavorable | unavailable | 77 | 13937 | 5504 | 5280 | 3153 | 2385 | 0 | 0 | 0.0436 |
| older_favorable | r2_0 | 1145 | 2051507 | 1527428 | 409794 | 114285 | 458124 | 0 | 0 | 0.4394 |
| older_favorable | r2_1 | 1450 | 8314991 | 6053315 | 1821277 | 440399 | 1595532 | 0 | 0 | 0.5564 |
| older_favorable | unavailable | 11 | 1338 | 967 | 287 | 84 | 508 | 0 | 0 | 0.0042 |
| older_unfavorable | r2_0 | 1035 | 2692292 | 1522926 | 981571 | 187795 | 628877 | 0 | 0 | 0.4981 |
| older_unfavorable | r2_1 | 1018 | 5624315 | 3424706 | 1789501 | 410108 | 1232029 | 0 | 0 | 0.4899 |
| older_unfavorable | unavailable | 25 | 3186 | 1891 | 1295 | 0 | 1215 | 0 | 0 | 0.0120 |
| young_favorable | r2_0 | 1840 | 6467013 | 3743724 | 2297983 | 425306 | 478805 | 0 | 0 | 0.6845 |
| young_favorable | r2_1 | 823 | 10764309 | 5530014 | 4588985 | 645310 | 612181 | 0 | 0 | 0.3062 |
| young_favorable | unavailable | 25 | 6671 | 2452 | 1119 | 3100 | 653 | 0 | 0 | 0.0093 |
| young_unfavorable | r2_0 | 340 | 2111592 | 834764 | 1111099 | 165729 | 162528 | 0 | 0 | 0.1670 |
| young_unfavorable | r2_1 | 1645 | 17371905 | 7033184 | 9204155 | 1134566 | 1104825 | 0 | 0 | 0.8080 |
| young_unfavorable | unavailable | 51 | 11985 | 2425 | 6011 | 3549 | 1012 | 0 | 0 | 0.0250 |

Se reutiliza R2 K=2, semilla 17. La etiqueta local 0 favorece relativamente el contraste joven frente a mayor y 1 el contraste inverso, según las curvas previas; “favorece” aquí describe forma tras retirar nivel, no participación absoluta alta. Se guardan medias de curvas para verificar esa interpretación. La unión es muchos a uno por entidad/municipio/sexo, sin expandir filas B, y se conserva el estado no disponible. Cada segmento contribuye una vez a los cruces; sus hermanos comparten etiqueta R2 y no son observaciones R2 independientes. R2 nunca determina candidate_id.

![R2 como contexto](../charts/profile_candidates_review/r2_context.png)

## Historia compatible y límites

Los diccionarios conservados definen edad cumplida al día de la elección, H/M y SV/NV/NS de manera comparable. Se verificaron categorías y referencias sobre broad 2009–2024, y sus siete conteos aditivos contra año/entidad descriptivos. Se agregan nacionalmente por las mismas bandas H/M: son cortes transversales repetidos, no trayectorias de personas o municipios. La ausencia histórica de SEXO=2 no significa cero personas de esa categoría.

| election_year | election_type | municipalities | core_LN | participation_observed | unspecified_rate |
| --- | --- | --- | --- | --- | --- |
| 2009 | midterm | 2458 | 77447803 | 0.4408 | 0.0241 |
| 2012 | presidential | 2455 | 76480440 | 0.6209 | 0.0022 |
| 2015 | midterm | 2458 | 83551117 | 0.4708 | 0.0613 |
| 2018 | presidential | 2463 | 89113529 | 0.6237 | 0.0683 |
| 2021 | midterm | 2468 | 93518603 | 0.5184 | 0.0432 |
| 2024 | presidential | 2477 | 98317046 | 0.5968 | 0.0643 |

![Historia de las referencias](../charts/profile_candidates_review/historical_peer_references.png)

No existe correspondencia territorial oficial validada. Las claves repetidas no prueban límites constantes; los distritos usan marco 2021 en 2009–2021 y 2023 en 2024. No se publican transiciones municipales de perfiles. Hay NS y disponibilidad de cuadernillos diferentes; presidenciales 2012/2018/2024 e intermedias 2009/2015/2021 tienen contextos distintos. La fuente de cuadernillos no cubre casillas especiales ni voto del extranjero según su diccionario; LN aquí significa el nominal reportado, no un censo validado de personas únicas. No se atribuyen cambios exclusivamente a conducta ciudadana.

## Fichas y estrategias preliminares

Las propuestas son de educación cívica y participación no partidista. El hallazgo de nivel relativo respalda dónde revisar acceso y cobertura; no demuestra causas ni eficacia de una intervención. Los canales son hipótesis abiertas, sin suponer preferencias por edad o sexo. Las actividades diferenciadas no deben restringir acceso a otros grupos.

### 35–59 años · por encima de sus pares

`adult_favorable` · candidato sujeto a revisión.

Segmentos municipio × sexo H/M × 35-59, LN y SV+NV ≥100, filas fuente ≥5; diferencia nacional de igual intervalo/sexo estrictamente positiva.

LN=20,337,701; segmentos=3,015; municipios=1,641; observada=69.33%; referencia con mezcla local=62.82%; diferencia=+6.51 pp.

Sexo: mujeres 50.98% de segmentos y 51.57% del LN.

Entidades destacadas por volumen: MEXICO, CIUDAD DE MEXICO, PUEBLA.

![adult_favorable](../charts/profile_candidates_review/card_adult_favorable.png)

Resumen agregado definido por edad y signo relativo; la distribución interna sigue siendo continua. U/R/M describe secciones electorales, no residencia individual ni causa de participación.

- **Hallazgo:** En 35-59, la diferencia agregada frente a pares es +6.51 pp; no identifica motivaciones.
- **Objetivo:** Sostener acceso a información cívica y evaluar su alcance.
- **Mensaje:** Tu participación cuenta. Consulta información oficial, verifica fechas y ejerce libremente tus derechos.
- **Canal como hipótesis:** Probar módulos presenciales accesibles y materiales digitales abiertos, con acceso para todas las edades; no se conoce el canal preferido.
- **Actividad:** Módulo abierto de consulta de trámites, calendario y mecanismos de participación. Invitar voluntariamente a compartir información oficial, sin asumir liderazgo.
- **Evaluación:** Cambio pre/post en conocimiento del calendario y derechos; alcance por canal y accesibilidad. Evaluar participación agregada posterior sólo con diseño de comparación y cobertura documentados.
- **Validación:** Propuesta cívica no partidista. Validar con población y personal electoral; los datos no prueban eficacia, preferencias ni causalidad.

Limitaciones: 10.58 % de segmentos están a no más de 2 pp de la referencia; no deben presentarse como diferencias sustantivas. La frontera cero y los intervalos son reglas de diseño, no tipos naturales ni intervalos de confianza. Municipios compartidos entre candidatos; no sumar coberturas territoriales. No se identifican personas. NS no es abstención; falta de soporte, SEXO=2 y 101+ permanecen en referencia y pendientes. Las estrategias y canales requieren validación; no hay variables de escolaridad, motivación ni preferencias.

### 35–59 años · por debajo de sus pares

`adult_unfavorable` · candidato sujeto a revisión.

Segmentos municipio × sexo H/M × 35-59, LN y SV+NV ≥100, filas fuente ≥5; diferencia nacional de igual intervalo/sexo estrictamente negativa.

LN=22,444,975; segmentos=1,767; municipios=1,018; observada=57.00%; referencia con mezcla local=62.96%; diferencia=-5.96 pp.

Sexo: mujeres 48.67% de segmentos y 52.81% del LN.

Entidades destacadas por volumen: JALISCO, NUEVO LEON, VERACRUZ.

![adult_unfavorable](../charts/profile_candidates_review/card_adult_unfavorable.png)

Resumen agregado definido por edad y signo relativo; la distribución interna sigue siendo continua. U/R/M describe secciones electorales, no residencia individual ni causa de participación.

- **Hallazgo:** En 35-59, la diferencia agregada frente a pares es -5.96 pp; no identifica motivaciones.
- **Objetivo:** Evaluar si información cívica accesible aumenta conocimiento y acceso, sin presumir una causa de menor participación.
- **Mensaje:** Tu participación cuenta. Consulta información oficial, verifica fechas y ejerce libremente tus derechos.
- **Canal como hipótesis:** Probar módulos presenciales accesibles y materiales digitales abiertos, con acceso para todas las edades; no se conoce el canal preferido.
- **Actividad:** Módulo abierto de consulta de trámites, calendario y mecanismos de participación. Recabar barreras declaradas voluntariamente antes de diseñar apoyos.
- **Evaluación:** Cambio pre/post en conocimiento del calendario y derechos; alcance por canal y accesibilidad. Evaluar participación agregada posterior sólo con diseño de comparación y cobertura documentados.
- **Validación:** Propuesta cívica no partidista. Validar con población y personal electoral; los datos no prueban eficacia, preferencias ni causalidad.

Limitaciones: 18.22 % de segmentos están a no más de 2 pp de la referencia; no deben presentarse como diferencias sustantivas. La frontera cero y los intervalos son reglas de diseño, no tipos naturales ni intervalos de confianza. Municipios compartidos entre candidatos; no sumar coberturas territoriales. No se identifican personas. NS no es abstención; falta de soporte, SEXO=2 y 101+ permanecen en referencia y pendientes. Las estrategias y canales requieren validación; no hay variables de escolaridad, motivación ni preferencias.

### 60–100 años · por encima de sus pares

`older_favorable` · candidato sujeto a revisión.

Segmentos municipio × sexo H/M × 60-100, LN y SV+NV ≥100, filas fuente ≥5; diferencia nacional de igual intervalo/sexo estrictamente positiva.

LN=10,367,836; segmentos=2,606; municipios=1,445; observada=77.26%; referencia con mezcla local=71.48%; diferencia=+5.78 pp.

Sexo: mujeres 46.93% de segmentos y 53.16% del LN.

Entidades destacadas por volumen: MEXICO, CIUDAD DE MEXICO, VERACRUZ.

![older_favorable](../charts/profile_candidates_review/card_older_favorable.png)

Resumen agregado definido por edad y signo relativo; la distribución interna sigue siendo continua. U/R/M describe secciones electorales, no residencia individual ni causa de participación.

- **Hallazgo:** En 60-100, la diferencia agregada frente a pares es +5.78 pp; no identifica motivaciones.
- **Objetivo:** Sostener acceso a información cívica y evaluar su alcance.
- **Mensaje:** Tu participación cuenta. Consulta información oficial, verifica fechas y ejerce libremente tus derechos.
- **Canal como hipótesis:** Probar módulos presenciales accesibles y materiales digitales abiertos, con acceso para todas las edades; no se conoce el canal preferido.
- **Actividad:** Jornada accesible de información sobre derechos, asistencia y organización de la jornada. Invitar voluntariamente a compartir información oficial, sin asumir liderazgo.
- **Evaluación:** Cambio pre/post en conocimiento del calendario y derechos; alcance por canal y accesibilidad. Evaluar participación agregada posterior sólo con diseño de comparación y cobertura documentados.
- **Validación:** Propuesta cívica no partidista. Validar con población y personal electoral; los datos no prueban eficacia, preferencias ni causalidad.

Limitaciones: 13.24 % de segmentos están a no más de 2 pp de la referencia; no deben presentarse como diferencias sustantivas. La frontera cero y los intervalos son reglas de diseño, no tipos naturales ni intervalos de confianza. Municipios compartidos entre candidatos; no sumar coberturas territoriales. No se identifican personas. NS no es abstención; falta de soporte, SEXO=2 y 101+ permanecen en referencia y pendientes. Las estrategias y canales requieren validación; no hay variables de escolaridad, motivación ni preferencias.

### 60–100 años · por debajo de sus pares

`older_unfavorable` · candidato sujeto a revisión.

Segmentos municipio × sexo H/M × 60-100, LN y SV+NV ≥100, filas fuente ≥5; diferencia nacional de igual intervalo/sexo estrictamente negativa.

LN=8,319,793; segmentos=2,078; municipios=1,189; observada=64.10%; referencia con mezcla local=71.44%; diferencia=-7.34 pp.

Sexo: mujeres 54.67% de segmentos y 56.08% del LN.

Entidades destacadas por volumen: JALISCO, MICHOACAN, NUEVO LEON.

![older_unfavorable](../charts/profile_candidates_review/card_older_unfavorable.png)

Resumen agregado definido por edad y signo relativo; la distribución interna sigue siendo continua. U/R/M describe secciones electorales, no residencia individual ni causa de participación.

- **Hallazgo:** En 60-100, la diferencia agregada frente a pares es -7.34 pp; no identifica motivaciones.
- **Objetivo:** Evaluar si información cívica accesible aumenta conocimiento y acceso, sin presumir una causa de menor participación.
- **Mensaje:** Tu participación cuenta. Consulta información oficial, verifica fechas y ejerce libremente tus derechos.
- **Canal como hipótesis:** Probar módulos presenciales accesibles y materiales digitales abiertos, con acceso para todas las edades; no se conoce el canal preferido.
- **Actividad:** Jornada accesible de información sobre derechos, asistencia y organización de la jornada. Recabar barreras declaradas voluntariamente antes de diseñar apoyos.
- **Evaluación:** Cambio pre/post en conocimiento del calendario y derechos; alcance por canal y accesibilidad. Evaluar participación agregada posterior sólo con diseño de comparación y cobertura documentados.
- **Validación:** Propuesta cívica no partidista. Validar con población y personal electoral; los datos no prueban eficacia, preferencias ni causalidad.

Limitaciones: 15.54 % de segmentos están a no más de 2 pp de la referencia; no deben presentarse como diferencias sustantivas. La frontera cero y los intervalos son reglas de diseño, no tipos naturales ni intervalos de confianza. Municipios compartidos entre candidatos; no sumar coberturas territoriales. No se identifican personas. NS no es abstención; falta de soporte, SEXO=2 y 101+ permanecen en referencia y pendientes. Las estrategias y canales requieren validación; no hay variables de escolaridad, motivación ni preferencias.

### 18–34 años · por encima de sus pares

`young_favorable` · candidato sujeto a revisión.

Segmentos municipio × sexo H/M × 18-34, LN y SV+NV ≥100, filas fuente ≥5; diferencia nacional de igual intervalo/sexo estrictamente positiva.

LN=17,237,993; segmentos=2,688; municipios=1,522; observada=57.39%; referencia con mezcla local=49.69%; diferencia=+7.69 pp.

Sexo: mujeres 55.06% de segmentos y 48.58% del LN.

Entidades destacadas por volumen: MEXICO, CIUDAD DE MEXICO, PUEBLA.

![young_favorable](../charts/profile_candidates_review/card_young_favorable.png)

Resumen agregado definido por edad y signo relativo; la distribución interna sigue siendo continua. U/R/M describe secciones electorales, no residencia individual ni causa de participación.

- **Hallazgo:** En 18-34, la diferencia agregada frente a pares es +7.69 pp; no identifica motivaciones.
- **Objetivo:** Sostener acceso a información cívica y evaluar su alcance.
- **Mensaje:** Tu participación cuenta. Consulta información oficial, verifica fechas y ejerce libremente tus derechos.
- **Canal como hipótesis:** Probar módulos presenciales accesibles y materiales digitales abiertos, con acceso para todas las edades; no se conoce el canal preferido.
- **Actividad:** Taller abierto de primera participación y verificación de información electoral. Invitar voluntariamente a compartir información oficial, sin asumir liderazgo.
- **Evaluación:** Cambio pre/post en conocimiento del calendario y derechos; alcance por canal y accesibilidad. Evaluar participación agregada posterior sólo con diseño de comparación y cobertura documentados.
- **Validación:** Propuesta cívica no partidista. Validar con población y personal electoral; los datos no prueban eficacia, preferencias ni causalidad.

Limitaciones: 9.41 % de segmentos están a no más de 2 pp de la referencia; no deben presentarse como diferencias sustantivas. La frontera cero y los intervalos son reglas de diseño, no tipos naturales ni intervalos de confianza. Municipios compartidos entre candidatos; no sumar coberturas territoriales. No se identifican personas. NS no es abstención; falta de soporte, SEXO=2 y 101+ permanecen en referencia y pendientes. Las estrategias y canales requieren validación; no hay variables de escolaridad, motivación ni preferencias.

### 18–34 años · por debajo de sus pares

`young_unfavorable` · candidato sujeto a revisión.

Segmentos municipio × sexo H/M × 18-34, LN y SV+NV ≥100, filas fuente ≥5; diferencia nacional de igual intervalo/sexo estrictamente negativa.

LN=19,495,482; segmentos=2,036; municipios=1,200; observada=43.26%; referencia con mezcla local=50.10%; diferencia=-6.83 pp.

Sexo: mujeres 43.42% de segmentos y 52.05% del LN.

Entidades destacadas por volumen: VERACRUZ, GUANAJUATO, JALISCO.

![young_unfavorable](../charts/profile_candidates_review/card_young_unfavorable.png)

Resumen agregado definido por edad y signo relativo; la distribución interna sigue siendo continua. U/R/M describe secciones electorales, no residencia individual ni causa de participación.

- **Hallazgo:** En 18-34, la diferencia agregada frente a pares es -6.83 pp; no identifica motivaciones.
- **Objetivo:** Evaluar si información cívica accesible aumenta conocimiento y acceso, sin presumir una causa de menor participación.
- **Mensaje:** Tu participación cuenta. Consulta información oficial, verifica fechas y ejerce libremente tus derechos.
- **Canal como hipótesis:** Probar módulos presenciales accesibles y materiales digitales abiertos, con acceso para todas las edades; no se conoce el canal preferido.
- **Actividad:** Taller abierto de primera participación y verificación de información electoral. Recabar barreras declaradas voluntariamente antes de diseñar apoyos.
- **Evaluación:** Cambio pre/post en conocimiento del calendario y derechos; alcance por canal y accesibilidad. Evaluar participación agregada posterior sólo con diseño de comparación y cobertura documentados.
- **Validación:** Propuesta cívica no partidista. Validar con población y personal electoral; los datos no prueban eficacia, preferencias ni causalidad.

Limitaciones: 15.28 % de segmentos están a no más de 2 pp de la referencia; no deben presentarse como diferencias sustantivas. La frontera cero y los intervalos son reglas de diseño, no tipos naturales ni intervalos de confianza. Municipios compartidos entre candidatos; no sumar coberturas territoriales. No se identifican personas. NS no es abstención; falta de soporte, SEXO=2 y 101+ permanecen en referencia y pendientes. Las estrategias y canales requieren validación; no hay variables de escolaridad, motivación ni preferencias.

## Contrato React, validaciones y reproducción

Se separan contracts/profile_payload.schema.json (JSON Schema 2020-12), candidates/profile_candidates.json (seis fichas) y examples/profile_payload.example.json (una ficha derivada de las mismas cifras). No son datos publicados ni un contrato definitivo; no se escribió en public/data ni React. Nombres de campos en inglés, textos en español, tasas proporcionales, NULL explícito y JSON sin NaN/Infinity. No hay nombres de personas ni etiquetas individuales.

El validador local estricto cubre todos los keywords usados por este esquema y rechaza otros; no pretende implementar JSON Schema general. El esquema estándar permite validación adicional con un motor 2020-12 en la integración. Se prueban campos extra, ausentes, tipos, límites y ejemplos no válidos. Las comprobaciones semánticas adicionales concilian conteos y tasas del payload con los Parquet.

Se verifican conservación de las 17,735 filas B, 9,773,730 filas fuente, LN=98,330,348 y los cuatro conteos; SEXO=2 conserva 105 filas/LN. Se concilian siete métricas por entidad contra descriptivos; referencia nacional original antes del filtro, orden/claves únicas, unión R2 sin expansión, partición de estados, conteos de perfiles, mezclas contextuales y lectura posterior de Parquet. Los hashes de 5,128 archivos previos se verifican antes/después; manifiestos previos se contrastan con sus artefactos relevantes. La base exacta sigue trazable por hash. No se ejecutan modelos ni se crean commits.

Resultados: reference/ conserva todos los segmentos y referencias; candidates/ incluye fichas y resumen; diagnostics/ contiene calidad, sensibilidad, sexo, territorio, NS, R2, cruces de modelos y alternativas; historical/ conserva referencias compatibles; contracts/ y examples/ están separados. metadata/run_manifest.json registra versiones, parámetros, fuentes y hashes; _SUCCESS sólo se escribe tras verificar todo.

```powershell
.venv_pattern_algorithms/Scripts/python.exe analysis/scripts/build_profile_candidates.py
.venv_pattern_algorithms/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_build_profile_candidates.py
```

Los destinos existentes se rechazan: para repetir usar --output, --charts y --report nuevos. No se sobrescriben resultados anteriores.

## Respuestas para la decisión y pendientes

1. **Seis viables:** sí como candidatos por reglas con soporte y advertencias; no seis clases naturales demostradas.
2. **Diferenciación:** la edad y el signo son explícitos; intensidad y contexto se cuantifican. U/R/M se superpone y no convierte los cortes en tipos separados.
3. **Tamaño/cobertura:** tablas y fichas anteriores, con LN, segmentos y cobertura municipal no aditiva.
4. **Fronteras:** cero e intervalos son convencionales; la zona ±2 pp debe mostrarse y revisarse, no ocultarse.
5. **Número:** revisar seis como matriz informativa; cuatro/cinco no ganan cobertura y sus fusiones pierden información. No seleccionar número definitivo por narrativa.
6. **R2:** aporta forma relativa joven–mayor por municipio/sexo, sin determinar las etiquetas principales ni fingir concordancia de unidades.
7. **Estrategias:** información cívica accesible, talleres y evaluación de conocimiento/alcance; eficacia, barreras y canales siguen siendo hipótesis.
8. **React:** fichas candidatas, conteos, tasas, referencias por sexo, cobertura, contexto, territorios, estrategias y limitaciones, con contrato separado; publicación pendiente.
9. **Jurado:** agregación ecológica, gradientes, reglas arbitrarias, NS, soporte desigual, categorías complementarias y comparabilidad histórica limitada. No inferir motivación ni comportamiento individual.
10. **Siguiente revisión:** cotejar convocatoria oficial y rúbrica, validar interpretación electoral y lenguaje, acordar zona neutral/umbral, revisar cobertura territorial y privacidad de presentación, validar estrategias con población, confirmar diccionario/contrato en React y aprobar fichas/documento técnico definitivos. No se resuelven esos pendientes mediante nuevos clusters.

## Sensibilidad explícita a NS

| candidate_id | segments | high_ns_segments | robust_fixed_reference | robust_both_bounds |
| --- | --- | --- | --- | --- |
| adult_favorable | 3015 | 641 | 2373 | 1976 |
| adult_unfavorable | 1767 | 295 | 1435 | 887 |
| older_favorable | 2606 | 525 | 1887 | 1581 |
| older_unfavorable | 2078 | 393 | 1797 | 1175 |
| young_favorable | 2688 | 606 | 2215 | 1837 |
| young_unfavorable | 2036 | 322 | 1620 | 1218 |

Los conteos robustos son escenarios extremos descriptivos, no probabilidades ni intervalos de confianza.
