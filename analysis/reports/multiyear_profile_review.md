# Análisis electoral multianual independiente · 2009–2024

**Se construyeron 6 análisis completos con la misma metodología, referencias propias y contratos comunes.** Elecciones procesadas: 2009, 2012, 2015, 2018, 2021, 2024. Los seis candidatos por reglas tienen segmentos con soporte en todas las elecciones de esta entrega. El paquete permite preparar un selector de elección con datos nacionales, estatales y municipales propios; su conexión al frontend queda pendiente, conforme a la restricción de no modificar React ni `public/data`. No se entrenó ningún algoritmo ni se transfirieron etiquetas de 2024.

Se leyeron los informes de candidatos, patrones, representación multidimensional y estabilidad de arquetipos, además de la limpieza técnica y sus diccionarios. Se reutilizan los agregados históricos y los contextos validados de 2024. Para recuperar U/R/M y secciones por intervalo/sexo en 2009–2021 se recorrieron por bloques los Parquet limpios, exclusivamente sus columnas necesarias. No se releen los CSV originales, no se repiten auditorías de registros ni ajustes de modelos. El detalle de edad exacta procede de los agregados descriptivos existentes.

## Unidades, reglas y denominadores

Las fichas usan **municipio × intervalo × sexo**; nivel y forma usan **municipio × sexo**, con tres coordenadas; las brechas usan **municipio × intervalo**. El municipio total incluye todas las edades y categorías. Son vistas alternativas: sus conteos no se suman entre sí. Las filas fuente son celdas originales, no personas ni secciones independientes. La misma clave entre años no identifica un territorio de límites constantes.

Participación local = SV/(SV+NV), NULL cuando SV+NV=0. NS permanece independiente. La referencia r se calcula por **la misma elección, intervalo y sexo antes de soporte**, como ΣSV/Σ(SV+NV); diferencia d = participación local − r. No se promedian tasas municipales ni se utiliza una referencia de 2024 para otros años. Los signos se calculan mediante productos cruzados de enteros Python; un empate exacto permanece `at_reference`. Los identificadores young/adult/older × favorable/unfavorable se conservan, con año obligatorio. Las bandas 18–34, 35–59 y 60–100 son reglas de diseño, no agrupamientos aprendidos ni límites de edad válidos.

Soporte: LN≥100, SV+NV≥100 y filas fuente≥5, H/M y edades 18–100. NS/LN≥10 % advierte cobertura, sin excluir automáticamente. Cerca de cero significa |d|≤2 pp; también se conserva sensibilidad a 1 y 5 pp. Las categorías >100 y SEXO=2 siguen en referencia, totales y recursos complementarios. `rule_candidate_id` conserva el signo sin soporte; `profile_id`/`candidate_id` sólo asigna fichas con soporte. Los estados son disjuntos; las banderas de calidad pueden superponerse.

## Disponibilidad y diferencias estructurales

| election_year | min_age | max_age | sex_codes | section_type_codes | district_reference_year | municipalities | source_rows |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2009 | 18 | 130 | 0\|1 | M\|R\|U | 2021 | 2458 | 8706843 |
| 2012 | 18 | 132 | 0\|1 | M\|R\|U | 2021 | 2455 | 8604456 |
| 2015 | 18 | 117 | 0\|1 | M\|R\|U | 2021 | 2458 | 9106059 |
| 2018 | 18 | 137 | 0\|1 | M\|R\|U | 2021 | 2463 | 9251122 |
| 2021 | 18 | 139 | 0\|1 | M\|R\|U | 2021 | 2468 | 9430502 |
| 2024 | 18 | 140 | 0\|1\|2 | M\|R\|U | 2023 | 2477 | 9773730 |

La edad es cumplida al día de la elección; H/M mantiene códigos 0/1 y U/R/M representa sección Urbana/Rural/Mixta en los diccionarios conservados. SEXO=2 aparece sólo en 2024: 105 filas fuente y LN=105, sin fusionarse con H/M. Las tablas contables históricas preservan los ceros de métricas de control de SEXO=2, pero la API de disponibilidad indica **categoría no registrada y conteos NULL** antes de 2024: no afirma cero personas no binarias.

La definición conceptual de NS es no especificación, pero la lista histórica de situaciones incluye una petición jurisdiccional explícita que no figura en la enumeración de 2024. Se conserva esa diferencia documental; no se fuerza igualdad de procesos de captura. Los datos reportados de cuadernillos no incluyen casillas especiales ni voto del extranjero según su diccionario. LN no es un censo validado de personas únicas. Los campos distritales faltantes se contabilizan por año en `metadata.json`; no se inventan distritos ni equivalencias entre marcos 2021 y 2023.

La matriz `historical/availability.csv` contiene una fila por elección y funcionalidad, con unidad, estado, base con soporte y pendientes. Nacional, entidad, municipio, edad exacta, edad/sexo, seis reglas, nivel/forma, brecha ajustada, U/R/M e inventarios de secciones están disponibles en los seis años, con las advertencias de calidad de cada registro. No se empaquetan geometrías cartográficas, correspondencias municipales históricas ni etiquetas de modelos aprendidos.

## Conteos, participación y cobertura por elección

| election_year | election_type | LN | SV | NV | NS | turnout_pct | NS_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2009 | Intermedia | 77481831 | 33316974 | 42298963 | 1865894 | 44.0608 | 2.4082 |
| 2012 | Presidencial | 76490962 | 47383154 | 28939159 | 168649 | 62.0830 | 0.2205 |
| 2015 | Intermedia | 83563462 | 36926612 | 41517874 | 5118976 | 47.0736 | 6.1259 |
| 2018 | Presidencial | 89123997 | 51784399 | 31249856 | 6089742 | 62.3651 | 6.8329 |
| 2021 | Intermedia | 93532133 | 46389189 | 43099624 | 4043320 | 51.8380 | 4.3229 |
| 2024 | Presidencial | 98330348 | 54899228 | 37105466 | 6325654 | 59.6700 | 6.4331 |

Porcentajes calculados sobre todos los conteos anuales, incluidas edades complementarias. Presidenciales: 2012, 2018 y 2024; intermedias: 2009, 2015 y 2021. Son cortes transversales repetidos, no trayectorias individuales. Las diferencias de participación no identifican por sí mismas cambios conductuales o efectos del tipo de elección.

![Participación y no especificación](../../data/processed/participamx_multiyear/charts/national_participation_and_ns.png)

| election_year | available_segments | supported_segments | supported_municipalities | available_municipalities | LN_coverage_pct | municipality_coverage_pct | undefined_segment_rates | high_ns_segments | near_reference_supported_segments |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2009 | 18545 | 14096 | 2398 | 2458 | 99.8233 | 97.5590 | 65 | 625 | 1515 |
| 2012 | 17313 | 14060 | 2397 | 2455 | 99.9198 | 97.6375 | 8 | 126 | 2484 |
| 2015 | 17549 | 13934 | 2369 | 2458 | 99.8399 | 96.3792 | 249 | 2217 | 1496 |
| 2018 | 17451 | 14045 | 2386 | 2463 | 99.8358 | 96.8737 | 168 | 3004 | 1877 |
| 2021 | 17771 | 14148 | 2398 | 2468 | 99.7831 | 97.1637 | 125 | 1812 | 1243 |
| 2024 | 17735 | 14190 | 2402 | 2477 | 99.8713 | 96.9721 | 137 | 2782 | 1873 |

LN_coverage_pct usa como denominador **todo el LN anual**; municipality_coverage_pct usa los municipios observados de esa elección. Se cuenta la unión de municipios clasificados, nunca la suma de las seis fichas. NULL, falta de soporte, empates y complementos permanecen en los Parquet/JSON originales del nuevo paquete. `historical/quality_reasons.csv` separa LN, especificados, filas fuente y NS; sus banderas se superponen y no se suman como exclusiones únicas.

![Cobertura anual](../../data/processed/participamx_multiyear/charts/coverage_by_election.png)

## Referencias propias por edad y sexo

| age_band | SEXO | 2009 | 2012 | 2015 | 2018 | 2021 | 2024 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 18-34 | 0 | 31.5789 | 48.9541 | 32.7313 | 49.9129 | 37.3158 | 43.7384 |
| 18-34 | 1 | 41.1756 | 59.7160 | 42.5740 | 60.1823 | 47.4343 | 55.9701 |
| 35-59 | 0 | 44.6978 | 62.5697 | 47.1269 | 61.7383 | 50.7734 | 57.2968 |
| 35-59 | 1 | 52.1927 | 71.6980 | 56.2317 | 71.1077 | 59.8350 | 68.0066 |
| 60-100 | 0 | 54.6400 | 70.2862 | 59.5036 | 69.3857 | 64.5377 | 72.2122 |
| 60-100 | 1 | 50.3679 | 67.5281 | 57.1198 | 67.6958 | 62.1129 | 70.8359 |

La tabla muestra porcentajes H/M de las tres bandas antes de soporte. Cada `national_references.json` incluye conteos y referencias completas, también categorías complementarias cuando existen. `age_statistics.json` aporta edad exacta × sexo nacional; `exact_age_segments/{state_code}.json` conserva el detalle municipal y una referencia de **edad exacta y sexo**, distinta de la referencia por intervalo usada para las seis fichas. No se sustituyen unas por otras.

| election_year | SEXO | LN | turnout_pct | NS_pct |
| --- | --- | --- | --- | --- |
| 2009 | 0 | 37353906 | 40.5280 | 2.4132 |
| 2009 | 1 | 40127925 | 47.3490 | 2.4035 |
| 2012 | 0 | 36821304 | 57.7755 | 0.2217 |
| 2012 | 1 | 39669658 | 66.0810 | 0.2194 |
| 2015 | 0 | 40219786 | 42.9540 | 6.1481 |
| 2015 | 1 | 43343676 | 50.8944 | 6.1052 |
| 2018 | 0 | 42913845 | 58.1431 | 6.8556 |
| 2018 | 1 | 46210152 | 66.2841 | 6.8118 |
| 2021 | 0 | 45067547 | 47.7622 | 4.3773 |
| 2021 | 1 | 48464586 | 55.6239 | 4.2723 |
| 2024 | 0 | 47226431 | 54.7598 | 6.4798 |
| 2024 | 1 | 51103812 | 64.2033 | 6.3899 |
| 2024 | 2 | 105 | 77.4510 | 2.8571 |

![Referencias nacionales](../../data/processed/participamx_multiyear/charts/age_sex_references.png)

## Seis candidatos por elección e intensidad

| election_year | candidate_id | segments | municipalities | states | LN | participation_observed_pct | matched_peer_reference_pct | delta_pp | near_reference_fraction_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2009 | adult_favorable | 2582 | 1397 | 31 | 15494999 | 57.4218 | 48.6291 | 8.7928 | 8.8691 |
| 2009 | adult_unfavorable | 2171 | 1191 | 28 | 18184641 | 40.9982 | 48.5472 | -7.5490 | 10.3178 |
| 2009 | older_favorable | 2397 | 1334 | 30 | 5837479 | 58.8767 | 52.3179 | 6.5588 | 12.2653 |
| 2009 | older_unfavorable | 2230 | 1259 | 30 | 5470611 | 45.3559 | 52.3970 | -7.0411 | 12.2870 |
| 2009 | young_favorable | 2376 | 1305 | 31 | 14971661 | 45.5680 | 36.6808 | 8.8872 | 10.1852 |
| 2009 | young_unfavorable | 2340 | 1291 | 27 | 17385510 | 28.6331 | 36.3191 | -7.6860 | 10.7692 |
| 2012 | adult_favorable | 2988 | 1654 | 31 | 17659824 | 72.2277 | 67.5288 | 4.6990 | 15.4618 |
| 2012 | adult_unfavorable | 1764 | 1044 | 31 | 15284797 | 61.6902 | 67.1163 | -5.4261 | 21.8821 |
| 2012 | older_favorable | 2440 | 1387 | 31 | 6463559 | 73.1735 | 68.8233 | 4.3502 | 18.9344 |
| 2012 | older_unfavorable | 2139 | 1250 | 32 | 4651928 | 62.7753 | 68.7933 | -6.0180 | 20.1964 |
| 2012 | young_favorable | 2669 | 1484 | 31 | 16352656 | 60.4997 | 54.6305 | 5.8692 | 14.4998 |
| 2012 | young_unfavorable | 2060 | 1181 | 29 | 16016845 | 48.2518 | 54.2369 | -5.9851 | 17.2330 |
| 2015 | adult_favorable | 2955 | 1591 | 31 | 16001024 | 62.2827 | 52.1340 | 10.1487 | 7.8173 |
| 2015 | adult_unfavorable | 1750 | 989 | 27 | 20051284 | 43.6613 | 51.7016 | -8.0402 | 12.6286 |
| 2015 | older_favorable | 2387 | 1323 | 31 | 6763968 | 65.0386 | 58.2075 | 6.8311 | 11.6883 |
| 2015 | older_unfavorable | 2168 | 1222 | 29 | 6344358 | 50.9636 | 58.2407 | -7.2771 | 13.7915 |
| 2015 | young_favorable | 2755 | 1488 | 31 | 14412365 | 48.8933 | 37.7743 | 11.1190 | 8.2033 |
| 2015 | young_unfavorable | 1919 | 1072 | 27 | 19856709 | 29.6888 | 37.6836 | -7.9948 | 12.5065 |
| 2018 | adult_favorable | 3385 | 1818 | 31 | 19993692 | 72.9051 | 66.7582 | 6.1469 | 10.5465 |
| 2018 | adult_unfavorable | 1355 | 801 | 30 | 18752934 | 59.8810 | 66.5058 | -6.6248 | 21.5498 |
| 2018 | older_favorable | 2773 | 1515 | 31 | 7928616 | 74.5846 | 68.4876 | 6.0970 | 12.8741 |
| 2018 | older_unfavorable | 1835 | 1055 | 31 | 6982924 | 61.3964 | 68.4578 | -7.0614 | 14.7684 |
| 2018 | young_favorable | 3088 | 1702 | 31 | 17525840 | 62.2584 | 55.1736 | 7.0848 | 10.7837 |
| 2018 | young_unfavorable | 1609 | 964 | 29 | 17793627 | 47.9757 | 55.0275 | -7.0518 | 16.5942 |
| 2021 | adult_favorable | 3511 | 1838 | 31 | 17388344 | 65.1470 | 55.5121 | 9.6349 | 5.4116 |
| 2021 | adult_unfavorable | 1257 | 706 | 30 | 23449337 | 48.3593 | 55.4929 | -7.1337 | 14.4789 |
| 2021 | older_favorable | 2897 | 1548 | 30 | 8651318 | 69.3831 | 63.2211 | 6.1620 | 8.2154 |
| 2021 | older_unfavorable | 1776 | 992 | 32 | 7942647 | 56.4414 | 63.2215 | -6.7801 | 15.4279 |
| 2021 | young_favorable | 3408 | 1798 | 31 | 14575762 | 53.5633 | 42.4094 | 11.1539 | 5.6338 |
| 2021 | young_unfavorable | 1299 | 745 | 31 | 21321818 | 34.8184 | 42.4086 | -7.5902 | 12.8560 |
| 2024 | adult_favorable | 3015 | 1641 | 31 | 20337701 | 69.3265 | 62.8210 | 6.5056 | 10.5804 |
| 2024 | adult_unfavorable | 1767 | 1018 | 31 | 22444975 | 56.9958 | 62.9576 | -5.9618 | 18.2230 |
| 2024 | older_favorable | 2606 | 1445 | 30 | 10367836 | 77.2614 | 71.4790 | 5.7824 | 13.2387 |
| 2024 | older_unfavorable | 2078 | 1189 | 30 | 8319793 | 64.0973 | 71.4406 | -7.3433 | 15.5438 |
| 2024 | young_favorable | 2688 | 1522 | 31 | 17237993 | 57.3870 | 49.6931 | 7.6939 | 9.4122 |
| 2024 | young_unfavorable | 2036 | 1200 | 31 | 19495482 | 43.2637 | 50.0952 | -6.8315 | 15.2750 |

La referencia de cada ficha ajusta su mezcla local: Σ(denominador del segmento × referencia de su banda/sexo)/Σdenominador. Delta es la resta de esa referencia a ΣSV/Σ(SV+NV); no equivale a la media simple de las diferencias, que se guarda por separado con cuartiles y extremos. Los municipios de distintas fichas se superponen. Los rótulos describen nivel relativo, sin inferir motivaciones, preferencias políticas o tipos de personas.

Distribución como porcentaje de **todo el LN de la elección**:

| election_year | young_favorable | young_unfavorable | adult_favorable | adult_unfavorable | older_favorable | older_unfavorable |
| --- | --- | --- | --- | --- | --- | --- |
| 2009 | 19.3228 | 22.4382 | 19.9982 | 23.4696 | 7.5340 | 7.0605 |
| 2012 | 21.3785 | 20.9395 | 23.0875 | 19.9825 | 8.4501 | 6.0817 |
| 2015 | 17.2472 | 23.7624 | 19.1483 | 23.9953 | 8.0944 | 7.5923 |
| 2018 | 19.6646 | 19.9650 | 22.4336 | 21.0414 | 8.8962 | 7.8351 |
| 2021 | 15.5837 | 22.7962 | 18.5908 | 25.0709 | 9.2496 | 8.4919 |
| 2024 | 17.5307 | 19.8265 | 20.6830 | 22.8261 | 10.5439 | 8.4611 |

Entre elecciones consecutivas, el mayor cambio absoluto de una cuota es **-4.13 pp**, young_favorable, 2012→2015. `historical/profile_distribution_changes.csv` contiene 30 contrastes. Son cambios de distribución entre poblaciones reportadas; no transiciones de los mismos segmentos o municipios.

![Distribución de perfiles](../../data/processed/participamx_multiyear/charts/profile_nominal_distribution.png)

| election_year | near_segments | near_LN |
| --- | --- | --- |
| 2009 | 1515 | 11152421 |
| 2012 | 2484 | 21553929 |
| 2015 | 1496 | 12340874 |
| 2018 | 1877 | 15061998 |
| 2021 | 1243 | 16540516 |
| 2024 | 1873 | 21536284 |

Los segmentos próximos a la frontera mantienen su etiqueta y advertencia; un signo pequeño no representa una discontinuidad electoral. `historical/intensity_sensitivity.csv` documenta 1/2/5 pp por perfil y año. Las fichas conservan fracción de NS alto y distribuciones de denominadores/secciones; no se confunde estabilidad descriptiva del signo con incertidumbre estadística o un intervalo de confianza.

## Indicadores continuos y brechas

Para cada municipio/sexo se guardan las tres diferencias d, nivel m=media simple(d), contraste joven−mayor=d18–34−d60–100 y forma centrada s=d−m. Dos contrastes ortonormales q=dQ conservan sus dos grados de libertad: d=m1+qQᵀ. No se estandariza, ajusta modelo, añade edad media ni divide por amplitud individual. Una media de diferencias no es participación municipal agregada. La forma requiere todas las tasas definidas; la elegibilidad exige además soporte en cada banda. Los valores definidos de perfiles sin soporte se conservan con sus banderas, no se presentan como entrenamiento.

| election_year | continuous_profiles | continuous_complete_profiles | supported_continuous_profiles | continuous_municipalities | continuous_supported_LN | continuous_LN_pct |
| --- | --- | --- | --- | --- | --- | --- |
| 2009 | 4916 | 4902 | 4583 | 2313 | 77244799 | 99.6941 |
| 2012 | 4910 | 4908 | 4555 | 2304 | 76362650 | 99.8323 |
| 2015 | 4916 | 4856 | 4528 | 2287 | 83364521 | 99.7619 |
| 2018 | 4926 | 4900 | 4577 | 2307 | 88900817 | 99.7496 |
| 2021 | 4936 | 4916 | 4633 | 2332 | 93279810 | 99.7302 |
| 2024 | 4954 | 4930 | 4648 | 2341 | 98153652 | 99.8203 |

| election_year | SEXO | indicator | profiles | mean_pp | q1_pp | median_pp | q3_pp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2009 | 0 | relative_level | 2278 | 1.9441 | -6.9669 | 0.7809 | 10.5376 |
| 2009 | 0 | young_older_difference | 2278 | 1.3616 | -4.0296 | 0.5109 | 6.3234 |
| 2009 | 1 | relative_level | 2305 | 2.0729 | -8.1350 | 0.8352 | 12.1413 |
| 2009 | 1 | young_older_difference | 2305 | 2.9045 | -2.0372 | 2.4854 | 8.0386 |
| 2012 | 0 | relative_level | 2256 | 1.8892 | -3.8369 | 1.6523 | 7.5870 |
| 2012 | 0 | young_older_difference | 2256 | 1.0393 | -4.1157 | 0.5926 | 5.7760 |
| 2012 | 1 | relative_level | 2299 | 1.6431 | -4.2534 | 1.8421 | 7.9674 |
| 2012 | 1 | young_older_difference | 2299 | 2.7359 | -1.2296 | 2.7118 | 6.8163 |
| 2015 | 0 | relative_level | 2249 | 5.0914 | -5.3841 | 2.9296 | 14.7499 |
| 2015 | 0 | young_older_difference | 2249 | 5.0029 | -1.6219 | 3.6416 | 10.6913 |
| 2015 | 1 | relative_level | 2279 | 5.2159 | -6.0296 | 3.7580 | 16.6530 |
| 2015 | 1 | young_older_difference | 2279 | 7.1492 | 1.1082 | 6.7181 | 13.3536 |
| 2018 | 0 | relative_level | 2275 | 3.8245 | -2.7540 | 3.7654 | 10.2358 |
| 2018 | 0 | young_older_difference | 2275 | 1.7383 | -3.8047 | 1.4856 | 7.0506 |
| 2018 | 1 | relative_level | 2302 | 4.3432 | -2.2528 | 4.5622 | 11.5173 |
| 2018 | 1 | young_older_difference | 2302 | 4.7373 | -0.3405 | 4.6533 | 9.4568 |
| 2021 | 0 | relative_level | 2305 | 7.5844 | -2.2429 | 7.7186 | 17.6507 |
| 2021 | 0 | young_older_difference | 2305 | 6.4497 | -1.0089 | 5.2588 | 12.7553 |
| 2021 | 1 | relative_level | 2328 | 8.7131 | -1.3196 | 10.0204 | 19.8857 |
| 2021 | 1 | young_older_difference | 2328 | 9.1247 | 3.0118 | 9.3408 | 15.1394 |
| 2024 | 0 | relative_level | 2312 | 2.2461 | -4.7623 | 1.6684 | 8.9691 |
| 2024 | 0 | young_older_difference | 2312 | 0.8015 | -7.0861 | 0.3595 | 8.2068 |
| 2024 | 1 | relative_level | 2336 | 2.9651 | -4.8634 | 2.9631 | 11.1385 |
| 2024 | 1 | young_older_difference | 2336 | 5.1568 | -2.4176 | 5.1320 | 12.0600 |

Distribuciones con igual peso por perfil municipio/sexo elegible; no ponderan personas. La brecha ajustada es (tasa_mujeres−referencia_mujeres)−(tasa_hombres−referencia_hombres) para la misma banda y elección. `S_available` exige soporte y tasa definida en ambos segmentos; el indicador publicable es NULL si falla. Las diferencias crudas permanecen separadas. La participación municipal general usa todas las categorías, y su diferencia ajustada del núcleo pondera referencias de edad/sexo por los denominadores locales.

## Contexto y territorio propio del año

| election_year | U | R | M |
| --- | --- | --- | --- |
| 2009 | 69.5176 | 19.4216 | 11.0608 |
| 2012 | 69.6446 | 18.1762 | 12.1791 |
| 2015 | 69.5545 | 17.9384 | 12.5071 |
| 2018 | 68.8109 | 17.5565 | 13.6326 |
| 2021 | 68.8742 | 17.4986 | 13.6271 |
| 2024 | 69.4510 | 17.5089 | 13.0402 |

| election_year | observed_distinct_sections | section_keys_in_multiple_municipalities | few_section_supported_segments | over_100_source_rows | over_100_LN |
| --- | --- | --- | --- | --- | --- |
| 2009 | 64934 | 0 | 3949 | 32761 | 34028 |
| 2012 | 65599 | 0 | 3939 | 10318 | 10522 |
| 2015 | 68362 | 0 | 3784 | 12123 | 12345 |
| 2018 | 68408 | 0 | 3882 | 10320 | 10468 |
| 2021 | 68812 | 0 | 3955 | 13216 | 13530 |
| 2024 | 70751 | 0 | 3921 | 12891 | 13197 |

U/R/M es composición de LN asociada a **secciones electorales**, no localidad ni residencia de personas. Secciones únicas anuales: entidad+sección; la consulta municipal añade municipio. Los inventarios y conteos por segmento se preservan. No se suman secciones de bandas o sexos para fabricar una unión: una sección puede aportar a varios. `distinct_sections` por ficha es NULL en todos los años porque los agregados comunes, incluido 2024, no conservan esa unión por candidato; sí se informa mínimo/mediana y frecuencia de segmentos con menos de cinco secciones. Filas fuente≥5 no equivale a cinco secciones distintas.

![Contexto electoral](../../data/processed/participamx_multiyear/charts/section_context_history.png)

Cada año dispone de sus municipios, entidades, conteos, etiquetas, calidad y perfiles presentes. No se unen municipios entre elecciones, no se publican transiciones y `municipal_history_enabled=false` permanece en índice, metadatos y comparación histórica. Para un mapa harán falta cartografía/catálogos apropiados y correspondencias verificadas; las claves del INE no se convierten implícitamente a otro catálogo.

## Regresión de 2024 y procedencia

| check | rows | fields | max_absolute_difference | status |
| --- | --- | --- | --- | --- |
| segments_counts_references_flags_context | 17735 | 51 | 0.0000 | passed |
| national_references | 10 | 9 | 0.0000 | passed |
| six_profiles | 6 | 38 | 0.0000 | passed |
| continuous_indicators | 4954 | 53 | 0.0000 | passed |
| adjusted_sex_gaps | 7431 | 4 | 0.0000 | passed |
| municipal_adjusted_indicators | 2477 | 4 | 0.0000 | passed |

La regresión se ejecutó **antes de los otros años**, con igualdad de claves/flags y tolerancia absoluta 1e-12, rtol=0 y NULL en la misma posición. Segmentos, referencias, seis perfiles e indicadores de forma reprodujeron exactamente los valores comparados; el ajuste municipal difiere como máximo 2.22e-16 por orden de operaciones flotantes. Se excluye intencionalmente sólo `r2_missing_segments` del resumen antiguo: depende de un modelo de 2024 y no pertenece a la metodología común sin entrenamiento. Los indicadores crudos y de soporte coinciden con las fuentes validadas.

**Incidencia heredada de trazabilidad:** el manifiesto descriptivo conserva una huella antigua de `build_descriptive.py`; el archivo actual ya tenía otra huella antes de esta entrega. Cuatro manifiestos posteriores corroboran la huella actual y los Parquet reutilizados concilian sus propias huellas. Se admite únicamente esa discrepancia de código identificada, registrada en `metadata/input_incidents.json`; no se editó el script ni el manifiesto antiguos. No se presenta la cadena histórica como libre de incidencias.

Se concilian 192 combinaciones elección–entidad contra los conteos de limpieza, y siete métricas aditivas por municipio en cada vista. Se conservan **54,872,712 filas fuente representadas**, sin interpretarlas como personas únicas; cada elección satisface LN=SV+NV+NS. U/R/M concilia con los segmentos, y el detalle exacto con los totales anuales. Claves y uniones tienen cardinalidad declarada; los Parquet se releen y comparan. Se verifican por hash 8,438 archivos previos al cerrar; los checkpoints contienen huellas y permiten reanudar sin repetir etapas válidas.

## Recursos JSON e integración futura

Destino: `data/processed/participamx_multiyear/`. `elections_index.json` enumera elecciones, tipo, rutas, cobertura y marco distrital. Cada `elections/YEAR/` conserva `profiles.json`, `municipalities.json`, `states.json`, `national_references.json`, `national_statistics.json`, `age_statistics.json`, `sex_statistics.json`, `section_statistics.json`, `continuous_indicators.json`, `sex_gaps.json`, `quality_summary.json`, `assignment_status.json` y `metadata.json`. Los directorios `municipality_segments/`, `municipality_profiles/` y `exact_age_segments/` se dividen por entidad para cargar sólo el territorio solicitado. `tables/` conserva los Parquet analíticos, pendientes y referencias.

Los JSON anuales ocupan aproximadamente **1,387.7 MiB** sin compresión. No se propone descargarlos todos al iniciar: el índice es ligero y el detalle exacto se solicita por entidad/año. `historical_comparison.json` contiene cortes transversales nacionales/estatales y distribuciones, sin filas municipales longitudinales. `historical/availability.json` habilita/explica funcionalidades por año. `integration/README.md` documenta selector, rutas, unidades y tratamiento de NULL.

Contrato v2 con año obligatorio, claves de código textuales y mismas columnas por recurso en los seis años. Identificadores/campos en inglés, mensajes y advertencias en español, tasas en [0,1] y diferencias en proporciones; multiplicar por 100 para porcentaje/pp. NULL explícito no se convierte en cero. Los ceros U/R/M sólo corresponden a subconjuntos vacíos conocidos de categorías exhaustivas. JSON no admite NaN/Infinity. Los esquemas estándar JSON Schema 2020-12 están en `schemas/`; el validador local cubre estrictamente el subconjunto usado, no todo el estándar. Una integración puede validar además con un motor estándar; no requiere instalar dependencias nuevas para producir esta entrega.

El contrato no es un reemplazo directo del antiguo payload v1 fijado a 2024: conserva conceptos e IDs, añade dimensión temporal y separa recursos por unidad. Los componentes actuales no tienen un cargador multianual conectado; este trabajo deja datos y guía concretos para implementarlo. No se cambió frontend ni `public/data`.

## Respuestas para la decisión y límites

1. **Mismo análisis:** sí, seis ejecuciones independientes de estadísticas, reglas, contexto e indicadores continuos, sin repetir algoritmos.
2. **Funciones:** todas las anteriores en los seis años con soporte por registro; SEXO=2 sólo está registrado en 2024.
3. **Diferencias:** cobertura municipal/nominal, NS, distribución etaria, tipos de elección, máximos de edad, categorías de sexo y marcos distritales; no son bases individuales idénticas.
4. **Cobertura:** las tablas anuales separan LN, unión municipal y perfiles de forma; una cobertura nominal alta no elimina huecos territoriales.
5. **Seis perfiles:** sí, todos tienen soporte en cada elección; son seis reglas explícitas, no seis clases naturales demostradas.
6. **Distribución:** las cuotas y contrastes anteriores cuantifican el cambio con referencia propia; no se interpretan como migración entre perfiles.
7. **No disponibles:** categoría no binaria histórica, unión única de secciones por candidato, equivalencias municipales/cartografía y etiquetas aprendidas históricas. Los huecos de tasa/soporte/distrito permanecen explícitos.
8. **2024:** los seis controles de regresión pasan antes de generalizar; no se sobrescribe el análisis original.
9. **React:** índice y recursos permiten seleccionar año y consultar estadísticas, perfiles, territorio, edad/sexo y calidad propios; conexión/publicación pendientes.
10. **Jurado:** agregación ecológica, reglas y frontera convencionales, NS/captura, cuadernillos incompletos respecto del universo electoral, soporte desigual, territorios sin correspondencia, comparación presidencial/intermedia y límites de procedencia. No se infieren motivaciones, eficacia de intervenciones o conducta individual.

## Reproducción y comprobaciones

```powershell
.venv_archetypal_patterns/Scripts/python.exe analysis/scripts/build_multiyear_profiles.py
.venv_archetypal_patterns/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_build_multiyear_profiles.py
```

`--year` acepta una elección y puede repetirse; cada ejecución recalcula únicamente sus referencias propias y conserva el control obligatorio de 2024 antes de generalizar. Para un subconjunto o parámetros distintos se deben elegir nuevos `--output` y `--report`. Con las mismas entradas/rutas se verifican y reutilizan checkpoints; `_SUCCESS` aparece sólo tras pruebas, lectura de artefactos e integridad final. `--stop-after-regression`, `--prepare-context` y `--prepare-years` permiten completar etapas sin repetir las anteriores. Los tests cubren signos exactos, ausencia frente a cero, referencias previas a soporte, unidades, coherencia/duplicación, esquemas, cobertura, regresión y casos sintéticos de huecos.

No se modificaron experimentos anteriores, fuentes, frontend ni `public/data`; no se imputaron tasas ni entrenaron modelos, y no se crearon commits. La integración visual y cualquier validación territorial longitudinal quedan como trabajo posterior explícito.
