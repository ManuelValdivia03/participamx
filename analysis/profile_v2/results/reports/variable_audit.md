# Auditoría de variables y cruce multivariable · V2 experimental

Se recuperó el cruce real, no se reconstruyó desde marginales. Se reutilizaron Parquet validados, sus manifiestos y referencias. No se leyeron CSV originales ni registros limpios individuales. Las fuentes y comprobaciones completas están en metadata/audit.json.

| year | cells | eligible | municipalities | eligible_municipalities | LN | eligible_LN | nominal_fraction | undefined | high_ns | sex_2_available | sex_2_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2009 | 40743 | 30619 | 2458 | 2387 | 77481831 | 77125896 | 0.9954 | 235 | 2168 | False | n/d |
| 2012 | 37691 | 30418 | 2455 | 2384 | 76490962 | 76246080 | 0.9968 | 42 | 355 | False | n/d |
| 2015 | 38324 | 30337 | 2458 | 2354 | 83563462 | 83149610 | 0.9950 | 705 | 5945 | False | n/d |
| 2018 | 38155 | 30689 | 2463 | 2379 | 89123997 | 88722387 | 0.9955 | 553 | 7548 | False | n/d |
| 2021 | 38835 | 31247 | 2468 | 2387 | 93532133 | 93124001 | 0.9956 | 426 | 4972 | False | n/d |
| 2024 | 38805 | 31470 | 2477 | 2392 | 98330348 | 97999677 | 0.9966 | 493 | 7436 | True | 67.0000 |

Las mismas 32 entidades están presentes cada año; municipios y categorías se interpretan dentro de cada elección. Las 888,405 comprobaciones de siete conteos aditivos concilian el cruce con padres, municipios y tipos nacionales; también se contrasta la tasa nacional de banda/sexo publicada.

En 2024 hay 38,805 celdas observadas y 10,062 combinaciones H/M de tres bandas y tres tipos no observadas frente al universo municipal de 18 posibilidades. Las ausencias no se completan con ceros. Los conteos y claves de origen no tienen nulos. Hay 493 tasas no definidas en la referencia completa, sin imputación.

| pending_reason | segments | eligible_segments | LN | eligible_LN | nominal_fraction | municipalities | eligible_municipalities | undefined | high_ns | few_sections |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| complementary | 4281 | 0 | 13302 | 0 | 0.0000 | 1752 | 0 | 163 | 503 | 3861 |
| eligible | 31470 | 31470 | 97999677 | 97999677 | 1.0000 | 2392 | 2392 | 0 | 6216 | 17898 |
| insufficient_support | 2724 | 0 | 214372 | 0 | 0.0000 | 686 | 0 | 0 | 387 | 2712 |
| undefined_rate | 330 | 0 | 102997 | 0 | 0.0000 | 45 | 0 | 330 | 330 | 312 |

La población común elegible es 31,470 celdas, 2,392 municipios y LN=97,999,677 (99.6637% del reportado). Se conservan 7,335 pendientes con sus motivos disjuntos y banderas superpuestas.

## Comparación de soporte y alternativas etarias

| design | threshold | min_source_rows | segments | municipalities | LN | nominal_fraction |
| --- | --- | --- | --- | --- | --- | --- |
| broad_split | 25 | 1 | 34028 | 2462 | 98210516 | 0.9988 |
| broad_split | 25 | 5 | 34028 | 2462 | 98210516 | 0.9988 |
| broad_split | 50 | 1 | 33440 | 2453 | 98183333 | 0.9985 |
| broad_split | 50 | 5 | 33440 | 2453 | 98183333 | 0.9985 |
| broad_split | 100 | 1 | 31470 | 2392 | 97999677 | 0.9966 |
| broad_split | 100 | 5 | 31470 | 2392 | 97999677 | 0.9966 |
| broad_split | 200 | 1 | 27187 | 2252 | 97279052 | 0.9893 |
| broad_split | 200 | 5 | 27187 | 2252 | 97279052 | 0.9893 |
| broad_split | 500 | 1 | 18794 | 1845 | 94245302 | 0.9585 |
| broad_split | 500 | 5 | 18794 | 1845 | 94245302 | 0.9585 |
| v1_unsplit | 100 | 5 | 14190 | 2402 | 98203780 | 0.9987 |
| life_stage_split | 100 | 5 | 45692 | 2337 | 97482392 | 0.9914 |

Las cinco bandas aumentan la fragmentación: no se entrenan en esta comparación ni se calcula ARI entre unidades distintas. Los umbrales exploratorios no equivalen a precisión o independencia estadística.

V1 conserva 14,190 segmentos, 2,402 municipios y LN=98,203,780. V2 pierde 10 municipios adicionales y LN=204,103 respecto a V1; no se confunde aumento de filas con aumento de cobertura. Los 85 municipios sin celdas elegibles están enumerados, incluyendo cuáles aportaban una ficha V1.

## Sexo no binario, edades extremas y sección

SEXO=2 conserva 67 celdas, LN=105, SV=79, NV=23, NS=3; el mayor denominador es 7. Ninguna entra al experimento H/M ni se le inventa etiqueta. Antes de 2024 la categoría no está registrada: no se declara cero población. 101+ conserva LN=13,197 y 12,891 filas fuente, fuera del núcleo pero dentro de la contabilidad.

U/R/M clasifica tipo de sección electoral, no localidad, residencia efectiva o nivel socioeconómico. Se dispone del número distinto de secciones por celda, no de la unión de claves por cluster. La suma de section_count entre celdas duplicaría secciones.

## Referencias de 2024: qué se conserva y qué se descuenta

| age_band | SEXO | TIPOSEC | reference_age_sex | reference_age_sex_section | reference_shift_pp |
| --- | --- | --- | --- | --- | --- |
| 18-34 | 0 | M | 0.4374 | 0.4154 | -2.1957 |
| 18-34 | 0 | R | 0.4374 | 0.4022 | -3.5189 |
| 18-34 | 0 | U | 0.4374 | 0.4508 | 1.3454 |
| 18-34 | 1 | M | 0.5597 | 0.5532 | -0.6538 |
| 18-34 | 1 | R | 0.5597 | 0.5945 | 3.4841 |
| 18-34 | 1 | U | 0.5597 | 0.5516 | -0.8116 |
| 35-59 | 0 | M | 0.5730 | 0.5621 | -1.0866 |
| 35-59 | 0 | R | 0.5730 | 0.5876 | 1.4595 |
| 35-59 | 0 | U | 0.5730 | 0.5715 | -0.1447 |
| 35-59 | 1 | M | 0.6801 | 0.6726 | -0.7438 |
| 35-59 | 1 | R | 0.6801 | 0.7122 | 3.2107 |
| 35-59 | 1 | U | 0.6801 | 0.6740 | -0.6019 |
| 60-100 | 0 | M | 0.7221 | 0.7017 | -2.0447 |
| 60-100 | 0 | R | 0.7221 | 0.7114 | -1.0731 |
| 60-100 | 0 | U | 0.7221 | 0.7287 | 0.6561 |
| 60-100 | 1 | M | 0.7084 | 0.6854 | -2.2991 |
| 60-100 | 1 | R | 0.7084 | 0.6773 | -3.1103 |
| 60-100 | 1 | U | 0.7084 | 0.7191 | 1.0707 |

La referencia conjunta cambia hasta 3.519 pp la referencia por edad/sexo. Descuenta diferencias promedio entre tipos, pero no elimina asociaciones locales ni corrige captura. No se usa una tasa nacional incondicional ni una media de tasas municipales.

## Cobertura estatal y flags de calidad

| EDOCVE | state_name_label | segments | eligible_segments | LN | eligible_LN | nominal_fraction | municipalities | eligible_municipalities | undefined | high_ns | few_sections |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | AGUASCALIENTES | 222 | 192 | 1097171 | 1097073 | 0.9999 | 11 | 11 | 0 | 9 | 100 |
| 10 | DURANGO | 677 | 581 | 1397549 | 1394888 | 0.9981 | 39 | 39 | 2 | 22 | 330 |
| 11 | GUANAJUATO | 939 | 761 | 4831159 | 4828916 | 0.9995 | 46 | 46 | 2 | 83 | 329 |
| 12 | GUERRERO | 1615 | 1293 | 2643256 | 2639667 | 0.9986 | 85 | 85 | 11 | 291 | 838 |
| 13 | HIDALGO | 1423 | 1214 | 2386306 | 2381615 | 0.9980 | 84 | 84 | 8 | 274 | 796 |
| 14 | JALISCO | 2398 | 2010 | 6619379 | 6611409 | 0.9988 | 125 | 125 | 21 | 435 | 1574 |
| 15 | MEXICO | 2099 | 1795 | 13026772 | 13021046 | 0.9996 | 125 | 125 | 12 | 320 | 1136 |
| 16 | MICHOACAN | 2121 | 1790 | 3748985 | 3730326 | 0.9950 | 113 | 112 | 47 | 604 | 1101 |
| 17 | MORELOS | 667 | 557 | 1549606 | 1544726 | 0.9969 | 36 | 36 | 7 | 154 | 407 |
| 18 | NAYARIT | 390 | 332 | 950653 | 949947 | 0.9993 | 20 | 20 | 2 | 98 | 145 |
| 19 | NUEVO LEON | 846 | 649 | 4466271 | 4454943 | 0.9975 | 51 | 50 | 16 | 213 | 527 |
| 2 | BAJA CALIFORNIA | 154 | 120 | 3197817 | 3197425 | 0.9999 | 7 | 7 | 0 | 32 | 54 |
| 20 | OAXACA | 6297 | 4505 | 3116671 | 3007123 | 0.9649 | 570 | 496 | 77 | 640 | 5674 |
| 21 | PUEBLA | 3176 | 2689 | 4978673 | 4961135 | 0.9965 | 217 | 217 | 32 | 554 | 2400 |
| 22 | QUERETARO | 334 | 281 | 1899053 | 1898711 | 0.9998 | 18 | 18 | 0 | 20 | 143 |
| 23 | QUINTANA ROO | 212 | 180 | 1460071 | 1459938 | 0.9999 | 11 | 11 | 0 | 22 | 90 |
| 24 | SAN LUIS POTOSI | 1065 | 859 | 2185470 | 2181271 | 0.9981 | 58 | 58 | 14 | 163 | 572 |
| 25 | SINALOA | 433 | 356 | 2360619 | 2359566 | 0.9996 | 20 | 20 | 6 | 223 | 93 |
| 26 | SONORA | 994 | 733 | 2291013 | 2266963 | 0.9895 | 72 | 67 | 92 | 344 | 760 |
| 27 | TABASCO | 349 | 287 | 1811510 | 1811221 | 0.9998 | 17 | 17 | 3 | 100 | 99 |
| 28 | TAMAULIPAS | 784 | 605 | 2848982 | 2842791 | 0.9978 | 43 | 42 | 12 | 172 | 460 |
| 29 | TLAXCALA | 789 | 658 | 1042696 | 1037292 | 0.9948 | 60 | 60 | 9 | 138 | 523 |
| 3 | BAJA CALIFORNIA SUR | 104 | 88 | 613613 | 613256 | 0.9994 | 5 | 5 | 0 | 13 | 24 |
| 30 | VERACRUZ | 3630 | 3089 | 6080517 | 6073047 | 0.9988 | 212 | 212 | 4 | 466 | 2124 |
| 31 | YUCATAN | 1593 | 1298 | 1766077 | 1747420 | 0.9894 | 106 | 106 | 28 | 381 | 1417 |
| 32 | ZACATECAS | 1089 | 921 | 1265939 | 1260881 | 0.9960 | 58 | 58 | 4 | 145 | 565 |
| 4 | CAMPECHE | 262 | 214 | 694600 | 693360 | 0.9982 | 13 | 13 | 8 | 151 | 136 |
| 5 | COAHUILA | 642 | 509 | 2410670 | 2403788 | 0.9971 | 38 | 37 | 8 | 109 | 377 |
| 6 | COLIMA | 192 | 162 | 584921 | 584835 | 0.9999 | 10 | 10 | 0 | 18 | 75 |
| 7 | CHIAPAS | 2005 | 1675 | 4003376 | 3956768 | 0.9884 | 124 | 122 | 55 | 861 | 1238 |
| 8 | CHIHUAHUA | 1112 | 929 | 3082363 | 3071325 | 0.9964 | 67 | 67 | 13 | 381 | 634 |
| 9 | CIUDAD DE MEXICO | 192 | 138 | 7918590 | 7917005 | 0.9998 | 16 | 16 | 0 | 0 | 42 |

| flag | segments | LN | eligible_segments | eligible_LN |
| --- | --- | --- | --- | --- |
| low_LN | 6764 | 170123 | 0 | 0 |
| low_specified | 7330 | 329945 | 0 | 0 |
| few_source_rows | 3806 | 6205 | 0 | 0 |
| high_ns | 7436 | 17071442 | 6216 | 16899810 |
| few_sections | 24783 | 9951289 | 17898 | 9669021 |
| split_sign_opposes_parent | 3541 | 5712790 | 2704 | 5688327 |

Las banderas se superponen, no son exclusiones aditivas. NS≥10 % no excluye del principal. Filas fuente≥5 no exige cinco secciones; 17,898 celdas elegibles (56.87%) proceden de menos de cinco secciones. La pérdida bajo ese requisito se estudia como sensibilidad, no como corrección automática.
