# Clustering multidimensional sociodemográfico · B broad 2024

**Añadir forma por edades y brecha entre sexos produce diferenciación descriptiva adicional, pero no demuestra cuatro a seis clases naturales ni una mejora global sobre F0.** Los bloques cambian lo que se considera cercano. La recomendación es conservar las seis reglas como presentación transparente y usar las ampliaciones como diagnósticos complementarios sujetos a validación electoral, sin publicar nuevos perfiles aprendidos.

Se completaron 198 ajustes principales/contextuales, 30 de estabilidad municipal y 11 sensibilidades. Sólo K-Means y GaussianMixture de scikit-learn; no se ejecutaron Ward, HDBSCAN o K-Medoids. No se exportó a React ni se modificaron fuentes o resultados anteriores.

## Población, unidad y recuperación de evidencia

Unidad: **municipio × sexo × intervalo de edad** (18–34, 35–59, 60–100). No son personas, patrones individuales ni coordenadas geográficas. Se verificaron las ocho rutas de informes solicitados, contratos, hashes, manifiestos y _SUCCESS de las fuentes antes de construir matrices. Se reutilizan profile_candidates_review, cluster_features, contextual_feature_review, participation_pattern_review y demographic_pilot; no se releen CSV ni registros históricos.

El entorno .venv_pattern_algorithms tiene Python 3.13 y bibliotecas importables; pip check no encontró dependencias rotas. Versiones y diagnóstico inicial del repositorio están en metadata/repository_diagnosis.json. No se instalaron paquetes. La consulta inicial no detectó procesos Python activos; un lock exclusivo impide duplicar este experimento.

| representation | blocks | segments | municipalities | LN | nominal_fraction | municipal_loss_pp | nominal_loss_pp | high_ns_segments | few_sections_segments | null_features |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F0 | P | 14190 | 2402 | 98203780 | 0.9987 | 0.0000 | 0.0000 | 2782 | 3921 | 0 |
| F1 | P+A | 13944 | 2341 | 98153652 | 0.9982 | 2.4627 | 0.0510 | 2742 | 3679 | 0 |
| F2 | P+S | 14126 | 2392 | 98195403 | 0.9986 | 0.4037 | 0.0085 | 2775 | 3857 | 0 |
| F3 | P+A+S | 13908 | 2341 | 98149089 | 0.9982 | 2.4627 | 0.0556 | 2739 | 3643 | 0 |
| all_common | P+A+S+M+T | 13908 | 2341 | 98149089 | 0.9982 | 2.4627 | 0.0556 | 2739 | 3643 | 0 |
| F4M | P+S+M | 14126 | 2392 | 98195403 | 0.9986 | 0.4037 | 0.0085 | 2775 | 3857 | 0 |
| F4T | P+S+T | 14126 | 2392 | 98195403 | 0.9986 | 0.4037 | 0.0085 | 2775 | 3857 | 0 |

Base validada: **14,190 segmentos, 2,402 municipios, LN=98,203,780 (99.8713 %)**. La comparación común usa **13,908 segmentos, 2,341 municipios y LN=98,149,089 (99.8157%)**. A pierde 246 segmentos de la base por no disponer de las tres edades con soporte; S pierde 64 por falta de soporte de ambos sexos. La intersección pierde 282 segmentos; los motivos se superponen. Ningún índice se atribuye al bloque por cambiar esa población.

Se mantienen LN≥100, SV+NV≥100, filas fuente≥5, H/M, edad de núcleo y tasa definida. NS≥10 % es advertencia, no filtro principal. Filas fuente no son secciones distintas ni observaciones independientes. reference/ conserva las 17,735 filas B, 9,773,730 filas fuente, LN=98,330,348 y 105 filas/LN de SEXO=2; 101+ y categorías complementarias conservan estados y etiquetas NULL. La referencia exacta anterior permanece intacta y trazable.

| block | segments | missing_among_base | municipalities | LN | features |
| --- | --- | --- | --- | --- | --- |
| P | 14190 | 0 | 2402 | 98203780 | 1 |
| A | 13944 | 246 | 2341 | 98153652 | 2 |
| S | 14126 | 64 | 2392 | 98195403 | 1 |
| M | 14190 | 0 | 2402 | 98203780 | 1 |
| T | 14190 | 0 | 2402 | 98203780 | 2 |

![Cobertura natural y común](../charts/multidimensional_profile_review/representation_coverage.png)

Entidades con menor cobertura nominal común:

| EDOCVE | state_name_label | segments | eligible_segments | eligible_municipalities | nominal_fraction |
| --- | --- | --- | --- | --- | --- |
| 20 | OAXACA | 3759 | 2618 | 456 | 0.9741 |
| 7 | CHIAPAS | 907 | 728 | 122 | 0.9888 |
| 26 | SONORA | 468 | 374 | 63 | 0.9935 |
| 16 | MICHOACAN | 856 | 672 | 112 | 0.9960 |
| 29 | TLAXCALA | 420 | 354 | 59 | 0.9974 |
| 21 | PUEBLA | 1524 | 1264 | 212 | 0.9990 |
| 5 | COAHUILA | 265 | 222 | 37 | 0.9992 |
| 31 | YUCATAN | 679 | 630 | 105 | 0.9994 |

## Características y significado electoral

| Bloque | Definición | Alcance y dependencia |
| --- | --- | --- |
| P | d = SV/(SV+NV) − r nacional del mismo intervalo/sexo. | Referencia de todos los conteos H/M de esas edades antes de soporte; no promedio municipal. |
| A | q₁=(d₁−d₂)/√2; q₂=(d₁+d₂−2d₃)/√6. | Forma de tres edades centrada; exige las tres tasas con soporte y reproduce R2 previo. Hasta tres segmentos comparten q. |
| S | d_mujeres−d_hombres; brecha observada también conservada como metadato. | Dirección fija, soporte de ambos sexos. Hasta dos segmentos del mismo municipio/edad comparten brecha; no es propiedad individual. |
| M | Tasa municipal H/M 18–100 menos referencia nacional ajustada por sus denominadores edad/sexo. | Promedio ponderado de d de todas sus celdas antes del soporte. La tasa municipal de todas las edades/sexos queda sólo como metadato. Hasta seis filas comparten M. |
| T | pQ, p=(LN_U,LN_R,LN_M)/LN y Q base ortonormal de contrastes. | Dos coordenadas del simplex. Conserva exactamente distancia euclídea entre composiciones; no es lograzón/Aitchison ni codificación ordinal. Ceros conservados sin pseudoconteos. |

A, S y M reexpresan los mismos conteos electorales en contextos compartidos; no son tres fuentes independientes. Su información adicional se evalúa respecto al vector P por segmento, no como datos individuales nuevos. La igualdad P=m+forma_de_su_banda permite reconstruir el nivel por municipio/sexo con la edad como metadato. M recupera un resumen territorial ya contenido en todas las celdas. No se añaden edad media, sexo, identidad municipal, estado ni distrito a la distancia.

Las tres proporciones de T suman uno; pQ elimina la dirección constante sin duplicarla. Se adopta explícitamente geometría euclídea sobre composiciones cerradas porque admite ceros y es contrastable con el antecedente contextual. No se afirma invariancia de Aitchison ni equivalencia con la geometría Hellinger anterior. TIPOSEC identifica contexto de sección electoral, no residencia individual.

## Auditoría previa, redundancia y ponderación de bloques

| representation | features | rank | condition | min_singular | max_singular |
| --- | --- | --- | --- | --- | --- |
| F0 | 1 | 1 | 1.0000 | 117.9322 | 117.9322 |
| F1 | 3 | 3 | 2.4358 | 66.5327 | 162.0572 |
| F2 | 2 | 2 | 1.0463 | 115.2315 | 120.5724 |
| F3 | 4 | 4 | 2.4415 | 66.3783 | 162.0634 |
| all_diagnostic | 7 | 7 | 4.6760 | 39.4713 | 184.5693 |

| block | feature | sd | q1 | median | q3 | residual_fraction_other_blocks |
| --- | --- | --- | --- | --- | --- | --- |
| P | relative_turnout | 0.1243 | -0.0517 | 0.0281 | 0.1059 | 0.2164 |
| A | age_shape_1 | 0.0500 | -0.0325 | -0.0014 | 0.0239 | 0.8296 |
| A | age_shape_2 | 0.0746 | -0.0219 | 0.0262 | 0.0782 | 0.8252 |
| S | sex_gap_adjusted | 0.0535 | -0.0241 | 0.0026 | 0.0335 | 0.9598 |
| M | municipal_adjusted_turnout | 0.1152 | -0.0472 | 0.0249 | 0.1058 | 0.2050 |
| T | section_contrast_1 | 0.3810 | -0.3109 | -0.0025 | 0.3011 | 0.7738 |
| T | section_contrast_2 | 0.3297 | -0.1377 | 0.1101 | 0.2887 | 0.9942 |

No hay dependencia lineal exacta en F0–F3 ni en el conjunto diagnóstico. La regresión OLS sobre otras columnas cuantifica reconstrucción lineal in-sample; no prueba independencia, novedad causal ni capacidad predictiva. Las dependencias condicionadas a edad/sexo/municipio siguen existiendo aunque el rango global sea completo.

![Correlaciones y redundancias](../charts/multidimensional_profile_review/feature_correlations.png)

Para cada bloque b: z_b=(x_b−media_b)/RMS_b, donde RMS_b²=media(Σ_j(x_bj−media_bj)²). La matriz concatena √w_b z_b; por tanto d²=Σ_b w_b d_b² y cada bloque aporta varianza total w_b, independientemente de tener una o dos columnas. No se blanquean contrastes ni se normaliza la amplitud de cada fila. Inicialmente w_b=1/n_bloques.

Parámetros ajustados sólo sobre la población común principal; en remuestras se reajustan sólo con municipios in-bag. La sensibilidad P-heavy duplica el peso de P respecto a cada otro bloque, antes de renormalizar. Es una sensibilidad predefinida pequeña, no pesos elegidos para maximizar Silhouette. Los controles NS/secciones/peso municipal mantienen las escalas principales, aislando el cambio de entrenamiento u objetivo.

La repetición de A/S/M puede orientar la geometría hacia territorios. El peso inicial es uno por segmento; no se finge independencia de esas propiedades compartidas. El peso total uno por municipio cambia el objetivo y se prueba sólo en K-Means, sin repetir filas para simular pesos en GMM.

## F0–F3 y decisión contextual F4

F0=P (control unidimensional), F1=P+A, F2=P+S y F3=P+A+S. Cobertura natural y común se guardan por separado; todos los ajustes de comparación usan las mismas filas y orden. Una representación inválida por rango/condición se bloquearía antes de entrenar.

F4 parte de **F2** bajo el criterio operativo registrado: Mayor ganancia media descriptiva en forma/brecha, conservando >=80% de separación condicional de tasas, ARI semillas>=.90 y cluster mínimo>=2%; K6 excluido. No es una selección definitiva ni demuestra que esa representación sea universalmente mejor. Se auditan M y T por separado; se exige al menos 5 % de variación residual lineal frente a los bloques base, rango completo y condición <10⁶, además de cobertura común ya aprobada.

| representation | base | block | residual_fraction | rank | columns | condition | training_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F4M | F2 | M | 0.2144 | 3 | 3 | 4.0783 | True |
| F4T | F2 | T | 0.9925 | 4 | 4 | 1.6666 | True |

M y T no se introducen juntos. F4M añade nivel territorial; F4T añade composición electoral. El residual puede ser relevante para geometría y aun así no mejorar perfiles de participación. El umbral 5 % es una alerta exploratoria predefinida, no una prueba estadística.

## Algoritmos, métricas y trazabilidad

K-Means: K=2–6 (6 sensibilidad), semillas 17/42/2024, diez arranques k-means++ explícitos por semilla, máximo 1,000 iteraciones y tol=0 para estabilizar etiquetas. Se guardan etiquetas/SSE/iteraciones de cada arranque y ARI contra el mejor; cada ajuste elige su SSE mínima. Las mismas semillas no garantizan los mismos índices iniciales entre geometrías. Centroides y SSE se recomputan desde asignaciones y pesos. [Implementación primaria KMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html).

Convergieron **198/198** ajustes principales/contextuales. La estabilidad de la mejor solución entre semillas no significa que todos los arranques converjan a la misma partición. Peores ARI de arranque frente al mejor, en K=4:

| representation | k | worst_initialization_ari | maximum_best_iterations | all_best_converged |
| --- | --- | --- | --- | --- |
| F0 | 4 | 0.9927 | 34 | True |
| F1 | 4 | 0.9967 | 44 | True |
| F2 | 4 | 0.2975 | 80 | True |
| F3 | 4 | 0.9928 | 27 | True |
| F4M | 4 | 0.9921 | 41 | True |
| F4T | 4 | 0.9971 | 19 | True |

GMM: 1–6 componentes, covarianza completa, cinco inicializaciones, tres semillas, máximo 1,000 iteraciones, tol=10⁻⁴ y reg_covar=10⁻⁵. Se guardan posteriores por segmento, AIC/BIC, convergencia, entropía, fracción max posterior<0.8, autovalores y condición de cada covarianza. La regularización no es imputación. El control ×10 evalúa sensibilidad a esa elección. Los componentes pueden aproximar una densidad continua y no son clases naturales. [Documentación primaria de mezclas](https://scikit-learn.org/stable/modules/mixture.html).

AIC/BIC se comparan únicamente dentro de cada representación y población, no entre espacios de dimensiones/escalas distintas. Sus supuestos de observaciones independientes son aproximados por propiedades compartidas dentro del municipio; aquí son criterios descriptivos de ajuste de mezclas, no evidencia formal de tipos ciudadanos.

Silhouette usa 512 anclas uniformes compartidas contra toda la población común, distancias por bloques de 16×N y error Monte Carlo con corrección finita. No hay matriz N×N. DB se calcula sobre todos los segmentos. Con una única etiqueta efectiva Silhouette/DB quedan NULL. Las métricas usuales se mantienen no ponderadas incluso cuando el entrenamiento utiliza pesos. [Definición primaria de Silhouette](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html).

SSE y métricas internas de geometrías diferentes no constituyen ranking universal. Los indicadores de participación son descriptivos in-sample; diferencias inducidas por incluir A, S o T no prueban descubrimiento ni generalización.

## Comparación electoral y nuevos patrones

Lectura controlada K=4, media de tres semillas (se muestran todos los K en CSV y gráficas): F0: forma 9.8%, brecha 0.8%, tasa condicional 87.4%; F1: forma 50.2%, brecha 0.6%, tasa condicional 71.4%; F2: forma 7.5%, brecha 52.2%, tasa condicional 72.7%; F3: forma 41.0%, brecha 51.4%, tasa condicional 56.4%; F4M: forma 8.5%, brecha 48.5%, tasa condicional 73.2%; F4T: forma 5.4%, brecha 52.3%, tasa condicional 55.6%.

![Comparación electoral F0 a F4](../charts/multidimensional_profile_review/representation_comparison.png)

R² dentro de edad/sexo compara residuo de tasas antes/después de añadir etiquetas a esas celdas. `shape_r2` y `context_r2` son medias de R² de sus dos contrastes fijos, **no** fracciones de varianza total del bloque ni medidas invariantes a rotación. Se conserva además diagnostics/total_block_variance_r2.csv, que suma cuadrados de ambos contrastes para describir la varianza total sobre los mejores ajustes K=4. Las contribuciones entre grupos usan siempre la suma de cuadrados total del bloque.

![Contribución de cada bloque a separación](../charts/multidimensional_profile_review/block_contributions.png)

| model_id | separation_P | separation_A | separation_S | separation_M | separation_T |
| --- | --- | --- | --- | --- | --- |
| f0/kmeans/k5/seed17 | 1.0000 | n/d | n/d | n/d | n/d |
| f4m/kmeans/k5/seed42 | 0.3688 | n/d | 0.2489 | 0.3822 | n/d |
| f4m/gmm/k5/seed17 | 0.3465 | n/d | 0.2858 | 0.3677 | n/d |

Una contribución mayor de A/S/M/T confirma qué objetivo separa el modelo; no es importancia causal. F0 sólo ordena niveles relativos. F1 puede dividir formas, F2 brechas agregadas y F3 combina objetivos, con posible pérdida de separación de P. F4M favorece nivel municipal y F4T contexto U/R/M. La pureza municipal permite detectar cuándo muchos segmentos del mismo territorio reciben la misma etiqueta aunque su código no entre en la matriz.

![Comparación de algoritmos](../charts/multidimensional_profile_review/algorithm_comparison.png)

![Vistas de coordenadas y proyecciones](../charts/multidimensional_profile_review/feature_space_projections.png)

No hay edad media en estas distancias, por lo que las cinco franjas inducidas por esa coordenada no se reproducen por construcción. La asociación con bandas puede persistir por patrones de tasas, brechas y forma. La pureza por edad es un diagnóstico de esa asociación; no se confunde con efecto causal ni con edad individual. Coincidir en una proyección bidimensional no prueba superposición en todo el espacio.

![Distribución de edades](../charts/multidimensional_profile_review/age_composition.png)

![Distribución de sexo](../charts/multidimensional_profile_review/sex_composition.png)

![Participación absoluta y referencia](../charts/multidimensional_profile_review/participation_levels.png)

![Curvas de forma por edad](../charts/multidimensional_profile_review/age_pattern_curves.png)

Las curvas emplean un municipio/sexo único dentro de cada cluster. El mismo municipio/sexo puede aportar edades a varios clusters: no sumar sus frecuencias como patrones independientes. Se guardan también medias ponderadas por número de segmentos para mostrar el efecto de repetir propiedades compartidas. La participación agregada utiliza ΣSV/Σden, y la referencia del grupo ajusta mezcla local de edad/sexo. La media simple de diferencias es otra medida; no intercambiar denominadores.

Perfiles descriptivos de las tres configuraciones enviadas a estabilidad, con etiquetas locales:

| model_id | cluster | segments | municipalities | participation_observed | mean_relative_turnout | mean_sex_gap_adjusted | women_fraction | unspecified_rate | near_rule_boundary_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| f0/kmeans/k5/seed17 | 0 | 1478 | 538 | 0.7992 | 0.2406 | 0.0035 | 0.5683 | 0.0759 | 0.0000 |
| f0/kmeans/k5/seed17 | 1 | 3160 | 1184 | 0.5094 | -0.0798 | 0.0031 | 0.4794 | 0.0667 | 0.0000 |
| f0/kmeans/k5/seed17 | 2 | 3876 | 1330 | 0.7001 | 0.1111 | 0.0165 | 0.5186 | 0.0482 | 0.0000 |
| f0/kmeans/k5/seed17 | 3 | 1091 | 459 | 0.4157 | -0.2156 | 0.0016 | 0.5096 | 0.0926 | 0.0000 |
| f0/kmeans/k5/seed17 | 4 | 4303 | 1575 | 0.6134 | 0.0158 | 0.0082 | 0.4778 | 0.0658 | 0.4302 |
| f4m/kmeans/k5/seed42 | 0 | 2005 | 546 | 0.4677 | -0.1643 | -0.0103 | 0.5172 | 0.0794 | 0.0015 |
| f4m/kmeans/k5/seed42 | 1 | 4030 | 1073 | 0.6933 | 0.0978 | 0.0107 | 0.5072 | 0.0527 | 0.0298 |
| f4m/kmeans/k5/seed42 | 2 | 4690 | 1247 | 0.5806 | -0.0177 | -0.0136 | 0.4940 | 0.0641 | 0.3028 |
| f4m/kmeans/k5/seed42 | 3 | 1728 | 706 | 0.5633 | 0.0295 | 0.1057 | 0.4942 | 0.0624 | 0.1782 |
| f4m/kmeans/k5/seed42 | 4 | 1455 | 379 | 0.7939 | 0.2296 | -0.0175 | 0.4983 | 0.0711 | 0.0000 |
| f4m/gmm/k5/seed17 | 0 | 3409 | 1428 | 0.5269 | -0.0675 | -0.0188 | 0.4749 | 0.0767 | 0.1162 |
| f4m/gmm/k5/seed17 | 1 | 2155 | 830 | 0.7237 | 0.1285 | 0.0301 | 0.5847 | 0.0598 | 0.0093 |
| f4m/gmm/k5/seed17 | 2 | 2147 | 947 | 0.5426 | -0.0034 | 0.0758 | 0.4923 | 0.0586 | 0.1635 |
| f4m/gmm/k5/seed17 | 3 | 4941 | 1507 | 0.5971 | 0.0119 | -0.0042 | 0.4924 | 0.0617 | 0.2190 |
| f4m/gmm/k5/seed17 | 4 | 1256 | 314 | 0.8214 | 0.2139 | -0.0218 | 0.4841 | 0.0778 | 0.0016 |

Una combinación transversal concreta en `f4m/kmeans/k5/seed42`, etiqueta local 3, reúne **1,728 segmentos de 706 municipios**: diferencia media frente a pares +2.95 pp y brecha media ajustada mujeres−hombres **+10.57 pp**, con 49.42% de segmentos de mujeres. Esa relación entre participación y brecha no está codificada en edad×signo. Es un hallazgo descriptivo de los conteos, no motivación individual, clase natural ni perfil validado; las sensibilidades y colas OOB impiden promoverlo automáticamente.

![Curvas de las configuraciones sometidas a estabilidad](../charts/multidimensional_profile_review/selected_candidate_curves.png)

![Brechas ajustadas](../charts/multidimensional_profile_review/sex_gap_distributions.png)

![Distribución territorial](../charts/multidimensional_profile_review/territorial_distribution.png)

La composición por sexo no se incorporó como número. Una agrupación de brechas compartidas describe relaciones entre grupos agregados; no revela decisiones personales. Las diferencias por entidad son diagnósticos de cobertura y concentración, no distancias geográficas ni efectos de residencia.

## Mezclas, incertidumbre y número de componentes

| representation | k | bic | aic | ambiguous_80 | mean_max_posterior | normalized_entropy | covariance_condition | regularization_touched_components |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F0 | 3 | 39,443.1310 | 39,382.8092 | 0.8792 | 0.6714 | 0.6835 | 1.0000 | 0 |
| F1 | 6 | 52,135.9280 | 51,691.0551 | 0.7530 | 0.6523 | 0.4871 | 23.3297 | 0 |
| F2 | 4 | 57,191.3980 | 57,017.9729 | 0.9114 | 0.5272 | 0.7550 | 4.6480 | 0 |
| F3 | 6 | 55,426.9346 | 54,755.8551 | 0.6521 | 0.6931 | 0.4466 | 28.6743 | 0 |
| F4M | 5 | 46,221.9437 | 45,852.4730 | 0.8432 | 0.6296 | 0.5525 | 43.4335 | 0 |
| F4T | 6 | 18,675.9156 | 18,004.8360 | 0.1677 | 0.9158 | 0.1161 | 52,142.5423 | 3 |

![Criterios de componentes dentro de cada representación](../charts/multidimensional_profile_review/gmm_component_criteria.png)

![Superposición e incertidumbre GMM](../charts/multidimensional_profile_review/gmm_uncertainty.png)

En las soluciones BIC mínimas propias la fracción ambigua está entre **16.77% y 91.14%**. Es incertidumbre condicional a cada mezcla, no probabilidad de que una persona pertenezca a un tipo. Menor ambigüedad en otra geometría no demuestra mayor utilidad electoral. AIC/BIC no se interpretan como prueba de cuatro a seis clases, aunque su mínimo caiga en ese rango.

**Excepción contextual importante:** `f4t/gmm/k6/seed42` tiene sólo 16.77% de asignaciones ambiguas, pero T aporta 90.62% de la separación; la tasa condicional explicada es apenas 5.83%, la brecha ajustada 1.66% y la pureza municipal 96.46%. Esta aparente nitidez describe sobre todo composición electoral, no mejores patrones de participación. Hay 6,870 segmentos en bordes del simplex y 1,494 con un único tipo de sección. 3 componentes del ajuste principal tocan el piso de regularización. El control acotado reg_covar=10⁻⁴ da ARI=0.9618, ambigüedad=18.46% y BIC=34064.17, frente a BIC=18675.92 con 10⁻⁵. No es otra representación ni una búsqueda de K: diagnostica sensibilidad numérica de una mezcla continua sobre composición con masas en sus fronteras. No se promueve esa solución por su posterior más tajante.

## Comparación con seis reglas y antecedentes B

Las seis reglas combinan edad y signo contra pares. Aquí se conserva su candidato original y se cruzan sólo los mismos segmentos comunes. ARI es concordancia, no precisión; no compara unidades distintas. Las etiquetas numéricas son locales a cada ajuste. Las distribuciones de intensidad, sexo, edad, NS y U/R/M acompañan las contingencias completas.

![Reglas frente a clusters](../charts/multidimensional_profile_review/rules_comparison.png)

Se reutilizan etiquetas B broad estandarizadas de K4/5/6, semilla 17, sin volver a entrenar. metadata/reference_comparison.csv recalcula sus descriptores sobre la intersección común; no se copian índices de otra cobertura como si fueran comparables. B life_stage queda como antecedente documentado porque sus segmentos no corresponden uno a uno a broad. No se calcula ARI entre esos universos ni con las unidades municipio/sexo de R2.

| reference | n | age_band_purity | relative_r2 | shape_r2 | sex_gap_r2 | within_age_sex_rate_r2 |
| --- | --- | --- | --- | --- | --- | --- |
| six_rules | 13908 | 1.0000 | 0.6234 | 0.1154 | 0.1277 | 0.6150 |
| previous_B_k4 | 13908 | 0.8087 | 0.4037 | 0.1002 | 0.0755 | 0.5618 |
| previous_B_k5 | 13908 | 0.9487 | 0.4623 | 0.1210 | 0.1154 | 0.5979 |
| previous_B_k6 | 13908 | 0.9588 | 0.6040 | 0.1337 | 0.1183 | 0.7011 |

Los nuevos clusters pueden atravesar las seis reglas o subdividir intensidades dentro de ellas; eso se cuantifica con contingencias y R² condicional a candidate_id. No significa por sí mismo que los nuevos cortes sean electoralmente útiles. Las reglas siguen siendo más transparentes para comunicar; los bloques adicionales sirven para revisar patrones que la matriz edad×signo no resume.

## Estabilidad municipal y peores casos

Se seleccionaron como máximo tres configuraciones: f0/kmeans/k5/seed17, f4m/kmeans/k5/seed42, f4m/gmm/k5/seed17. La selección excluye K6 y usa ganancia media descriptiva de forma/brecha frente a F0 al mismo K, retención de ≥80 % de separación de tasa condicional, ARI de semillas≥0.90 y grupo mínimo≥2 %. Son puertas exploratorias; si ninguna las supera se conserva la mejor como diagnóstico, sin llamarla validada. La GMM se escoge por BIC dentro de la representación seleccionada, nunca comparando BIC entre geometrías.

Se reutilizan las primeras 10 submuestras municipales del experimento previo: 1,981 de los 2,477 municipios originales por muestra, sin reemplazo. Todos los segmentos de cada municipio quedan juntos. Escalas reajustadas sólo in-bag; referencias nacionales descriptivas fijas, que incluyen también OOB. Esto no es validación predictiva independiente de todo el proceso nacional ni bootstrap con reemplazo.

| model_id | samples | ari_oob_median | ari_oob_q10 | ari_oob_min | samples_below_90 | aligned_oob_change_max |
| --- | --- | --- | --- | --- | --- | --- |
| f0/kmeans/k5/seed17 | 10 | 0.9742 | 0.8657 | 0.8458 | 2 | 0.0607 |
| f4m/gmm/k5/seed17 | 10 | 0.8198 | 0.5326 | 0.5317 | 9 | 0.3052 |
| f4m/kmeans/k5/seed42 | 10 | 0.9229 | 0.8033 | 0.3337 | 3 | 0.4571 |

Peor concordancia OOB observada: **0.3337** en `f4m/kmeans/k5/seed42`. Se muestran mediana, q10, mínimo y número de muestras bajo 0.90; una mediana alta no oculta la cola. Diez muestras no son prueba definitiva ni intervalo de confianza.

| sample | drawn_municipalities | training_segments | oob_segments | training_municipalities | oob_municipalities | training_LN | training_fraction_eligible_LN | selected_original_LN | selected_original_segments |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1981 | 11119 | 2789 | 1872 | 469 | 76062777 | 0.7750 | 76209764 | 14189 |
| 1 | 1981 | 11138 | 2770 | 1876 | 465 | 81186665 | 0.8272 | 81318329 | 14169 |
| 2 | 1981 | 11110 | 2798 | 1870 | 471 | 79827000 | 0.8133 | 79974830 | 14204 |
| 3 | 1981 | 11120 | 2788 | 1875 | 466 | 80423551 | 0.8194 | 80581914 | 14213 |
| 4 | 1981 | 11110 | 2798 | 1870 | 471 | 78959709 | 0.8045 | 79110505 | 14188 |
| 5 | 1981 | 11120 | 2788 | 1871 | 470 | 77645794 | 0.7911 | 77804636 | 14200 |
| 6 | 1981 | 11107 | 2801 | 1870 | 471 | 77048313 | 0.7850 | 77211150 | 14177 |
| 7 | 1981 | 11118 | 2790 | 1872 | 469 | 81195387 | 0.8273 | 81336817 | 14181 |
| 8 | 1981 | 11076 | 2832 | 1865 | 476 | 79164225 | 0.8066 | 79325730 | 14204 |
| 9 | 1981 | 11126 | 2782 | 1872 | 469 | 78581332 | 0.8006 | 78716100 | 14211 |

![Estabilidad y cobertura municipal](../charts/multidimensional_profile_review/municipal_stability.png)

ARI se calcula sobre etiquetas sin necesidad de alineación. Para porcentaje de cambios y desplazamientos de perfiles se alinean etiquetas por máximo solapamiento sobre la población común; las asignaciones se distinguen como entrenamiento u OOB. Se conserva alineación, perfil OOB antes/después, todas las etiquetas y escaladores. No se presentan municipios sin características completas como usados en el entrenamiento.

## Sensibilidades limitadas

| model_id | scenario | training_segments | training_municipalities | training_nominal_fraction | baseline_same_seed | ari_all | ari_common_training | aligned_change_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| f0/kmeans/k5/seed17 | low_ns_segment | 11169 | 1947 | 0.8380 | f0/kmeans/k5/seed17 | 0.9380 | 0.9422 | 0.0246 |
| f0/kmeans/k5/seed17 | five_sections | 10265 | 1711 | 0.9778 | f0/kmeans/k5/seed17 | 0.7402 | 0.7516 | 0.1282 |
| f0/kmeans/k5/seed17 | equal_municipality | 13908 | 2341 | 0.9982 | f0/kmeans/k5/seed17 | 0.9860 | 0.9860 | 0.0055 |
| f4m/kmeans/k5/seed42 | low_ns_segment | 11169 | 1947 | 0.8380 | f4m/kmeans/k5/seed17 | 0.8268 | 0.8298 | 0.0701 |
| f4m/kmeans/k5/seed42 | five_sections | 10265 | 1711 | 0.9778 | f4m/kmeans/k5/seed17 | 0.3577 | 0.3227 | 0.4394 |
| f4m/kmeans/k5/seed42 | equal_municipality | 13908 | 2341 | 0.9982 | f4m/kmeans/k5/seed17 | 0.9745 | 0.9745 | 0.0099 |
| f4m/kmeans/k5/seed42 | p_heavy | 13908 | 2341 | 0.9982 | f4m/kmeans/k5/seed17 | 0.7245 | 0.7245 | 0.1150 |
| f4m/gmm/k5/seed17 | low_ns_segment | 11169 | 1947 | 0.8380 | f4m/gmm/k5/seed17 | 0.4913 | 0.4945 | 0.3598 |
| f4m/gmm/k5/seed17 | five_sections | 10265 | 1711 | 0.9778 | f4m/gmm/k5/seed17 | 0.5449 | 0.6046 | 0.3274 |
| f4m/gmm/k5/seed17 | p_heavy | 13908 | 2341 | 0.9982 | f4m/gmm/k5/seed17 | 0.8639 | 0.8639 | 0.0589 |
| f4m/gmm/k5/seed17 | regularization_x10 | 13908 | 2341 | 0.9982 | f4m/gmm/k5/seed17 | 0.9084 | 0.9084 | 0.0365 |

![Sensibilidades de los candidatos](../charts/multidimensional_profile_review/sensitivity_comparison.png)

NS<10 % es una selección temporal de segmentos, no modificación del principal ni imputación. Filtrar sólo el NS del segmento **no** elimina automáticamente otros NS utilizados en A/S/M; los máximos de NS de sus insumos están conservados para una revisión más estricta. La referencia nacional también permanece fija y puede contener NS. La no especificación no equivale a abstención.

El control ≥5 secciones distintas utiliza section_count por segmento; no lo confunde con ≥5 filas fuente. Son filtros temporales de ajuste y las demás filas conservan proyecciones separadas. Cambian cobertura y población; no se atribuyen cambios a causalidad de NS o de tamaño. La cobertura y los row_id exactos de entrenamiento/proyección quedan guardados.

Todos los ajustes de sensibilidad usan semilla 17. La tabla y gráfica de esta sección comparan contra el ajuste principal de semilla 17 correspondiente, además de conservar en metadata/sensitivity.csv la comparación contra la mejor solución entre semillas. Así se separa el cambio de semilla de referencia sin repetir ningún ajuste. Igual semilla no garantiza iguales índices k-means++ cuando cambian pesos, población o geometría: son sensibilidades con optimización finita y múltiples arranques, no efectos causales puros de los pesos.

Peso municipal=1/n_segmentos_comunes_del_municipio; se comprueba suma uno por municipio. KMeans admite sample_weight. GaussianMixture.fit no admite ese argumento en este entorno, por lo que no se fabrican pesos mediante replicación de filas y esa sensibilidad queda explícitamente no ejecutada para GMM. LN se conserva como diagnóstico, no como coordenada ni ponderación automática.

## Tabla final de comparación

K=4 se usa como corte descriptivo común para leer la tabla, **no** como K elegido. Las seis reglas tienen seis etiquetas por diseño. Las medias de métricas son de tres semillas; las reglas no requieren semillas. Todas las filas evalúan la misma población común. Valores de R² y pureza son proporciones; multiplicar por 100 para porcentajes.

| representation | comparison_K | n | nominal_fraction | within_age_sex_rate_r2 | delta_vs_F0 | mean_shape_contrast_r2 | sex_gap_r2 | municipal_level_r2 | context_r2 | age_band_purity | rules_ari | seed_ari_min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F0 | 4 | 13908 | 0.9982 | 0.8738 | 0.0000 | 0.0976 | 0.0077 | 0.6867 | 0.0138 | 0.3813 | 0.1932 | 1.0000 |
| F1 | 4 | 13908 | 0.9982 | 0.7141 | -0.1597 | 0.5018 | 0.0059 | 0.5975 | 0.0181 | 0.4293 | 0.1664 | 1.0000 |
| F2 | 4 | 13908 | 0.9982 | 0.7269 | -0.1469 | 0.0751 | 0.5221 | 0.6034 | 0.0234 | 0.4696 | 0.1294 | 1.0000 |
| F3 | 4 | 13908 | 0.9982 | 0.5640 | -0.3098 | 0.4098 | 0.5142 | 0.5093 | 0.0204 | 0.4594 | 0.1399 | 0.9970 |
| F4M | 4 | 13908 | 0.9982 | 0.7325 | -0.1413 | 0.0855 | 0.4852 | 0.7271 | 0.0253 | 0.4390 | 0.1244 | 0.9988 |
| F4T | 4 | 13908 | 0.9982 | 0.5559 | -0.3179 | 0.0541 | 0.5230 | 0.4242 | 0.3361 | 0.4497 | 0.1542 | 1.0000 |
| six_rules_descriptive | 6 | 13908 | 0.9982 | 0.6150 | -0.2587 | 0.1154 | 0.1277 | 0.4857 | 0.0034 | 1.0000 | 1.0000 | n/d |

## Conclusiones para ParticipaMX

1. **Viabilidad:** F0, F1, F2 y F3 tienen rango completo y cobertura común; F4M/F4T quedan sujetos al control contextual registrado y nunca se combinan M+T. Los pendientes originales se conservan.
2. **Cobertura:** base 14,190/2,402 y comparación 13,908/2,341, con LN=98,149,089 (99.8157%). La pérdida territorial se explica por soporte de patrón y par sexual, no se oculta tras LN alto.
3. **Información distinta:** A añade contraste entre edades y S relación de sexos respecto a P por segmento; M añade resumen del territorio y T composición electoral. Todos se derivan de agregados existentes; no son fuentes independientes ni información individual.
4. **Edad:** no entra edad media como coordenada. La pureza por banda puede persistir y debe leerse junto a la intensidad relativa; no se demuestra independencia de edad sólo por retirarla de la matriz.
5. **Más que niveles:** las ampliaciones separan forma/brecha/contexto además de P, pero esos objetivos se introdujeron deliberadamente. Se exige distinguir esa información descriptiva de clases naturales descubiertas.
6. **Riqueza:** existen combinaciones transversales descriptivas de tasas, forma y brecha. Sus curvas y composiciones deben revisarse electoralmente; no basta añadir dimensiones o ver colores separados.
7. **Estabilidad:** la tabla OOB compara sólo los tres candidatos seleccionados; no se atribuye estabilidad municipal a todas las configuraciones. Se conservan mínimos, semillas y sensibilidades.
8. **GMM:** ambigüedad de 16.8%–91.1% en los mínimos BIC propios; la menor es contextual, dominada por T y apoyada en regularización, no evidencia de perfiles de participación superiores. Las demás mezclas siguen muy superpuestas.
9. **Frente a reglas:** los clusters pueden añadir descriptores de intensidad, forma y brecha que las reglas no codifican. Las contingencias/R² condicionales muestran cuánto; mayor complejidad no demuestra que sean mejores para comunicar o intervenir.
10. **Cuatro a seis:** no se obtiene evidencia suficiente de cuatro a seis clases naturales por convergencia, BIC o Silhouette. Se documentan candidatos de densidad/partición, no una tipología validada.
11. **Interpretación:** F0 es el control de nivel relativo; los bloques son útiles si se expone su objetivo. Las seis reglas siguen siendo una matriz comunicable de edad×signo, con advertencias de frontera, y R2/brecha aportan paneles complementarios.
12. **Recomendación:** combinar las reglas descriptivas con diagnósticos multidimensionales, sin sustituirlas aún por nuevos perfiles aprendidos. No se demuestra superioridad global de una ampliación. Revisar utilidad electoral, cobertura, colas de estabilidad y sensibilidad antes de otra adopción o publicación.

## Integridad, artefactos y reproducción

Se protegen 5,176 archivos previos mediante SHA-256; se concilian conteos completos y por municipio con descriptivos. Todas las matrices tienen los mismos row_id comunes, columnas finitas, rangos auditados y parámetros propios. Los resúmenes por cluster conservan LN, SV, NV, NS y filas fuente; modelos y vistas son alternativas y nunca se suman entre sí.

Cada modelo se guarda incrementalmente en joblib/NPZ con parámetros, huella de matriz y marcador verificado antes de reutilizarlo. Los posteriores se alinean a features/F*/matrix.parquet; labels conserva pendientes NULL. Escritura atómica, exclusión por lock, errores con traceback, memoria/tiempos por checkpoint y reanudación A–G evitan repetir modelos completos. Los joblib sólo se cargan del experimento propio tras verificar hashes.

Las pruebas automatizadas comprueban signos y referencias, soporte, geometría del simplex, contraste R2, composición municipal, escalas sólo de entrenamiento, varianza por bloque, alineación y equivalencia de Silhouette con scikit-learn en un caso pequeño; además verifican conteos, matrices, posteriores, pendientes y muestreo municipal de los artefactos. El resultado exacto queda en metadata/test_validation.json. _SUCCESS se escribe sólo tras aprobar pruebas y comprobar integridad.

Estructura: reference/ datos completos, pendientes y membresía; features/ matrices y escaladores; diagnostics/ auditoría, soporte y cobertura; models/ ajustes nativos; assignments/ etiquetas completas; resampling/ membresías, ajustes y OOB; sensitivity/ controles y proyecciones; metadata/ contratos, métricas, composiciones, curvas, contingencias, checkpoints y manifiestos.

```powershell
.venv_pattern_algorithms/Scripts/python.exe analysis/scripts/evaluate_multidimensional_profiles.py --until B
.venv_pattern_algorithms/Scripts/python.exe analysis/scripts/evaluate_multidimensional_profiles.py
.venv_pattern_algorithms/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_evaluate_multidimensional_profiles.py
```

Con resultado íntegro, el comando sólo verifica y termina con cero ajustes nuevos. Para reproducción independiente usar --output, --charts y --report nuevos. --until permite detener después de una etapa y --replicates/--anchors fijan presupuestos limitados; no cambiarlos para reanudar el mismo destino.

No se modificaron datos originales, agregados previos, informes anteriores, frontend o entornos. No se ejecutaron algoritmos adicionales ni se exportaron perfiles a React. No se crearon commits. Permanecen pendientes revisión electoral de curvas y brechas, sensibilidad adicional con insumos NS conjuntos, más remuestras si hay colas inestables y validación sustantiva de estrategias antes de perfiles definitivos.
