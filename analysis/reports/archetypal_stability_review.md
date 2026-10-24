# Validación final de estabilidad de arquetipos electorales · 2024

**Recomendación B: utilizar indicadores continuos sin arquetipos como complemento de los seis perfiles por reglas.** Diez arranques estabilizan parte del ajuste AA2 K3 y mantienen su ventaja de reconstrucción frente a K2. Persisten cambios de curvas de hasta **8.22 pp** entre muestras y hasta **9.65 pp** al cambiar los criterios de calidad. Los indicadores de nivel y forma ya conservan toda la información medida y permiten explicar esos gradientes sin elegir extremos aprendidos. AA queda en la documentación técnica; no se integra a React ni sustituye los seis perfiles principales.

Esta decisión reconoce una mejora real: excluir individualmente los tres mayores aportantes cambia curvas sólo hasta **2.06 pp**. La concentración β no demuestra por sí misma que un único registro sea indispensable o erróneo. El límite principal de comunicación es la variación residual de extremos, la optimización y la utilidad adicional no demostrada frente a los indicadores existentes.

## Recuperación, datos y alcance

Se revisaron archetypal_pattern_review.md, profile_candidates_review.md, participation_pattern_review.md y age_band_representation_review.md, junto con rutas reales, contratos, _SUCCESS, manifiestos, checkpoints y modelos. Se conservaron los **138 ajustes del experimento anterior**; 32 ajustes exactamente compatibles se reutilizan por referencias y hashes, sin volver a entrenarlos. Esta revisión reúne **270 resultados de inicialización: 238 nuevos y 32 reutilizados**. No se reprocesaron CSV ni registros individuales.

El universo es idéntico en todas las comparaciones principales: **4,571 perfiles municipio×sexo**, **2,296 municipios**, LN=98,119,426 (**99.7855 % del LN nacional reportado**). Las coordenadas corresponden a 18–34, 35–59 y 60–100 años; no edad media. Se exige LN≥100, SV+NV≥100 y filas fuente≥5 en cada banda. Edad, sexo y claves territoriales se conservan como metadatos, no magnitudes de distancia. No se ensayan K4, K5, K6 ni variables nuevas.

La referencia conserva 4,954 perfiles H/M disponibles, incluidos 383 fuera de la población común. Las 77 filas elegibles bajo tres bandas pero fuera del universo común siguen explícitas. La referencia broad completa conserva los 17,735 segmentos y todos los conteos de 2024, incluidos 101+ y SEXO=2 (105 filas fuente/LN). Los pendientes mantienen coeficientes NULL: no se imputan, no se borran datos y no se suman vistas alternativas.

Las tasas son SV/(SV+NV), NULL si el denominador es cero; NS no es abstención. La referencia nacional por banda/sexo utiliza todos los conteos antes de soporte y permanece fija. AA2 descompone d en nivel m y forma ortonormal q; centra/escala cada bloque por entrenamiento y reparte 50/50 su varianza. No se añade información ni se duplica una dimensión. El peso es uno por perfil municipio×sexo: un municipio con ambos sexos aporta dos filas, sin asumir independencia; no se pondera automáticamente por LN.

## Entorno y protocolo de optimización

Se utiliza .venv_archetypal_patterns, Python 3.13, archetypes 0.6.2, sklearn 1.5.2, NumPy 2.5.4; pip check y prueba sintética pasan. No se instala ni modifica ninguna dependencia. Se reutilizan las funciones geométricas y validaciones del [experimento anterior](archetypal_pattern_review.md), sin ejecutar su programa principal.

Semillas predefinidas, en orden: **17, 42, 2024, 1009, 2027, 4001, 5003, 7001, 9001, 11003**. Cada ajuste usa n_init=1, inicializador nativo random, máximo300 iteraciones y tolerancia absoluta1e−4 de la norma de Frobenius. Diez ajustes independientes constituyen cada protocolo de múltiples arranques. K2 recibe el mismo presupuesto que K3. Se guarda todo, incluidos arranques desfavorables y límites de iteración: hubo **0** resultados que alcanzaron300, conservados con bandera; 0 fueron seleccionados en muestras municipales. No se certifica convergencia global.

La versión instalada expone alphas_, betas_ y archetypes_; transform recalcula α sobre arquetipos finales. Se verifican α≥0, β≥0, sumas de fila uno, Z=βX, dimensiones, reconstrucciones e inversión afín con tolerancia1e−8. rss_ nativo no es SSE: todas las SSE y RMSE se recomputan. Se selecciona **sólo la menor SSE geométrica de entrenamiento**, desempate por semilla, sin consultar OOB ni atractivo visual. La RMSE original en pp no es el mismo objetivo que la SSE geométrica AA2: ordenar por ambas puede diferir.

Para curvas y coeficientes se fija una referencia completa por K, elegida entre los diez arranques por esa misma SSE. Se alinea mediante Hungarian con RMS entre curvas originales, únicamente K×K, nunca N×N. **El desplazamiento de cada curva es RMS de sus tres bandas en pp; el máximo informado toma el mayor RMS entre arquetipos, no la mayor diferencia puntual de una banda.** Las permutaciones, coeficientes originales/alineados y referencias se conservan. α describe una reconstrucción convexa, no probabilidad de votar ni porcentaje de ciudadanos. No se convierte el coeficiente dominante en un perfil rígido.

## Inicializaciones con exactamente los mismos datos

| seed | iterations | stopped_before_limit | sse | excess_sse_fraction | geometry_rmse | raw_rmse_pp | max_curve_shift_pp | alpha_l1_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1009 | 241 | True | 375.7301 | 0.0000 | 0.1655 | 2.5148 | 0.0000 | 0.0000 |
| 17 | 69 | True | 379.7895 | 0.0108 | 0.1664 | 2.5652 | 2.9337 | 0.0301 |
| 2027 | 89 | True | 379.7909 | 0.0108 | 0.1664 | 2.5653 | 2.9344 | 0.0301 |
| 11003 | 125 | True | 379.7912 | 0.0108 | 0.1664 | 2.5653 | 2.9346 | 0.0301 |
| 4001 | 111 | True | 379.7915 | 0.0108 | 0.1664 | 2.5653 | 2.9348 | 0.0301 |
| 42 | 125 | True | 379.7919 | 0.0108 | 0.1664 | 2.5653 | 2.9350 | 0.0301 |
| 5003 | 46 | True | 395.5483 | 0.0527 | 0.1698 | 2.4182 | 14.3854 | 0.1827 |
| 7001 | 45 | True | 395.5501 | 0.0528 | 0.1698 | 2.4187 | 14.3695 | 0.1827 |
| 2024 | 51 | True | 395.5519 | 0.0528 | 0.1698 | 2.4193 | 14.3539 | 0.1826 |
| 9001 | 17 | True | 395.5648 | 0.0528 | 0.1698 | 2.4218 | 14.2846 | 0.1822 |

Con datos fijos, los arquetipos K3 difieren hasta **17.32 pp** entre arranques; la SSE oscila entre 375.730 y 395.565 (5.28 % sobre el mínimo). Es evidencia de distintas soluciones detenidas compatibles con atracción a mínimos locales; el algoritmo aproximado y el criterio de parada no prueban que cada una sea un mínimo local exacto.

La mejor SSE corresponde a semilla **1009**. Sólo **1/10** cae dentro del margen diagnóstico del1 % del mejor objetivo completo. Con un único resultado próximo al óptimo observado no puede estimarse la estabilidad de ese óptimo ni concluir que la menor SSE garantiza curvas estables. Los diez arranques tienen igual legitimidad para el diagnóstico; no se elige la semilla por su interpretación.

Para evitar la tautología de medir al mejor contra sí mismo, se calcula también para cada semilla su distancia media de curvas a las otras nueve, sin referencia privilegiada:

| seed | sse | mean_pair_curve_shift_pp | median_pair_curve_shift_pp | maximum_pair_curve_shift_pp |
| --- | --- | --- | --- | --- |
| 1009 | 375.7301 | 8.0073 | 2.9350 | 14.3854 |
| 17 | 379.7895 | 8.0073 | 2.9337 | 17.3191 |
| 2027 | 379.7909 | 8.0075 | 2.9344 | 17.3199 |
| 11003 | 379.7912 | 8.0076 | 2.9346 | 17.3201 |
| 4001 | 379.7915 | 8.0077 | 2.9348 | 17.3202 |
| 42 | 379.7919 | 8.0079 | 2.9350 | 17.3204 |
| 5003 | 395.5483 | 11.2371 | 17.3191 | 17.3204 |
| 7001 | 395.5501 | 11.2229 | 17.3032 | 17.3045 |
| 2024 | 395.5519 | 11.2125 | 17.2876 | 17.2889 |
| 9001 | 395.5648 | 11.1817 | 17.2183 | 17.2196 |

En este banco, Spearman entre SSE y distancia media a otros arranques es **0.8667**: los objetivos menores suelen ser más centrales entre las soluciones observadas. La mejor SSE tiene distancia media 8.007 pp, dentro del rango 8.007–11.237 pp. Centralidad entre diez arranques no es exactitud, estabilidad territorial ni una prueba universal de que minimizar SSE identifica un extremo fiable. No se calculan p-valores ni se cambió el criterio de selección.

El1 % de exceso de SSE, 5 pp de desplazamiento y 1 pp de diferencia entre reconstrucciones son referencias operativas de revisión declaradas, **no umbrales oficiales, pruebas de error, intervalos de confianza o aceptación automática**. Los valores completos se entregan para juzgar otras tolerancias.

![fixed initialization curves](../charts/archetypal_stability_review/fixed_initialization_curves.png)

## Separación entre optimización y perturbación municipal

Se reutilizan las **diez mismas submuestras**, cada una con1,981 de2,477 municipios originales, sin reemplazo; ambos sexos elegibles permanecen juntos. Aportan 3,645–3,658 perfiles entrenados por sorteo; LN de entrenamiento equivale a 77.50–82.73 % del LN elegible común. Se registran municipios sorteados que no aportan perfiles, municipios activos, OOB, LN y filas para cada muestra.

Para cada muestra y K se ajustan las escalas sólo con entrenamiento y se prueban diez semillas con esa misma escala y población. El modelo de menor SSE de entrenamiento proyecta todos los OOB; no se usan sus errores para seleccionarlo. La referencia nacional incluye conteos de todo2024, también OOB: **estabilidad condicional a referencias nacionales fijas**, no predicción independiente de todo el procedimiento.

Los siguientes protocolos se comparan contra **la misma referencia completa nueva**. «Un arranque» es la semilla17 anterior, reutilizada; «diez» selecciona entre el banco predefinido. El anterior máximo20.72 pp utilizaba otra referencia completa; no se resta directamente como si todo el cambio fuese optimización.

| k | starts | samples | oob_rmse_median_pp | oob_rmse_max_pp | max_curve_shift_median_pp | max_curve_shift_max_pp | alpha_oob_l1_median | alpha_oob_l1_max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 1 | 10 | 6.4414 | 6.6752 | 0.9217 | 1.6269 | 0.0153 | 0.0278 |
| 2 | 10 | 10 | 6.4393 | 6.6721 | 0.2688 | 1.2023 | 0.0034 | 0.0141 |
| 3 | 1 | 10 | 2.4636 | 3.0019 | 3.5103 | 17.7850 | 0.0486 | 0.2001 |
| 3 | 10 | 10 | 2.5439 | 3.0066 | 2.4832 | 8.2159 | 0.0253 | 0.0804 |

En K3, el máximo municipal pasa de **17.78 a 8.22 pp**, y la mediana del máximo de 3.51 a 2.48 pp. Disminuye la variación inducida por la lotería de arranques, pero **2/10 muestras** todavía superan la referencia operativa de5 pp. El error OOB mediano cambia de 2.464 a 2.544 pp: más arranques no mejoraron ese indicador original fuera de entrenamiento, pese a reducir SSE de entrenamiento. No se oculta este resultado.

Para cuantificar dispersión sin atribuirla toda a municipios se usa una identidad balanceada: en10 muestras×10 semillas, cada curva alineada es un vector de9 coordenadas. La varianza total con ddof=0 es la media de varianzas **entre semillas dentro del mismo entrenamiento** más la varianza **entre medias de muestras**.

| k | samples | seeds | aligned_coordinates | within_seed_pp2 | between_sample_means_pp2 | total_pp2 | within_fraction | between_fraction | identity_residual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 10 | 10 | 6 | 0.2037 | 0.1919 | 0.3955 | 0.5149 | 0.4851 | 0.0000 |
| 3 | 10 | 10 | 9 | 19.0175 | 9.6050 | 28.6225 | 0.6644 | 0.3356 | 0.0000 |

Para K3, el componente dentro de muestras representa **66.44 %** de la dispersión total de este diseño; el componente entre medias, **33.56 %**. Son fracciones descriptivas de estos100 ajustes/alineación, **no el porcentaje causal de la inestabilidad anterior**, ni incertidumbre de votantes. El componente entre medias también puede contener distinta frecuencia de soluciones del optimizador. La perturbación municipal tras elegir el mejor de diez conserva optimización residual: no se afirma haberla eliminado.

El mayor desplazamiento entre soluciones a ≤1 % de la mejor SSE de su muestra es 20.84 pp. La tabla de pares permite comprobar que un pequeño margen de SSE no implica curvas próximas. Tampoco una mediana municipal favorable certifica el peor caso.

![optimization vs municipal variation](../charts/archetypal_stability_review/optimization_vs_municipal_variation.png)
![municipal multistart curves](../charts/archetypal_stability_review/municipal_multistart_curves.png)
![initialization budget effects](../charts/archetypal_stability_review/initialization_budget_effects.png)

## Reconstrucción OOB: K2 frente a K3

| sample | k2_oob_rmse_pp | k3_oob_rmse_pp | reduction_pp | relative_reduction |
| --- | --- | --- | --- | --- |
| 0 | 6.6721 | 2.8513 | 3.8209 | 0.5727 |
| 1 | 6.4137 | 2.6020 | 3.8117 | 0.5943 |
| 2 | 6.2795 | 2.3465 | 3.9330 | 0.6263 |
| 3 | 6.5954 | 2.4653 | 4.1301 | 0.6262 |
| 4 | 6.2450 | 3.0066 | 3.2385 | 0.5186 |
| 5 | 6.4649 | 2.5049 | 3.9600 | 0.6125 |
| 6 | 6.1185 | 2.7983 | 3.3201 | 0.5426 |
| 7 | 6.3407 | 2.5829 | 3.7578 | 0.5926 |
| 8 | 6.4983 | 2.5046 | 3.9937 | 0.6146 |
| 9 | 6.6592 | 2.3461 | 4.3131 | 0.6477 |

K3 conserva menor RMSE OOB en **10/10** muestras. Medianas: K2=6.439 pp y K3=2.544 pp; peor RMSE K3=3.007 pp. La reducción emparejada mediana es **3.877 pp**, con rango 3.238–4.313 pp. Las medianas de reducciones y la diferencia entre medianas no tienen por qué coincidir.

El peor RMSE anterior resume una muestra completa. El máximo RMSE de **un perfil OOB individual** es **29.82 pp**: hay curvas locales mal reconstruidas aunque el promedio sea pequeño. Las figuras de casos y los percentiles documentan esa cola, sin ocultarla con el error global.

Se preserva RMSE geométrica, original en pp, error normalizado frente a la media del entrenamiento, percentiles y desglose por sexo, LN, NS, secciones y entidad. SSE de espacios/poblaciones diferentes no se equipara para escoger geometría. Los controles OOB sí comparten entrenamiento, escala, unidades y observaciones de evaluación. Mejor reconstrucción no identifica tres clases naturales ni certifica utilidad de comunicación.

![paired oob error](../charts/archetypal_stability_review/paired_oob_error.png)

## Auditoría de aportantes y estabilidad de su influencia

Principales aportantes del modelo completo seleccionado; SV+NV y secciones se muestran por banda, no se suman como territorios únicos:

| archetype | rank | row_id | EDOCVE | MPIOCVE | SEXO | weight | LN | specified_count_0 | specified_count_1 | specified_count_2 | NS_0 | NS_1 | NS_2 | section_count_0 | section_count_1 | section_count_2 | radial_distance | radial_extreme | concentration_equivalent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | pattern_2024\|20\|351\|0 | 20 | 351 | 0 | 0.8430 | 942 | 398 | 382 | 162 | 0 | 0 | 0 | 1 | 1 | 1 | 2.5003 | True | 1.3705 |
| 0 | 2 | pattern_2024\|20\|231\|0 | 20 | 231 | 0 | 0.1363 | 961 | 437 | 354 | 170 | 0 | 0 | 0 | 1 | 1 | 1 | 2.8321 | True | 1.3705 |
| 0 | 3 | pattern_2024\|20\|108\|0 | 20 | 108 | 0 | 0.0207 | 1430 | 607 | 522 | 301 | 0 | 0 | 0 | 2 | 2 | 2 | 2.6347 | True | 1.3705 |
| 1 | 1 | pattern_2024\|16\|110\|0 | 16 | 110 | 0 | 0.4468 | 1860 | 419 | 762 | 679 | 0 | 0 | 0 | 9 | 9 | 9 | 2.6973 | True | 2.4809 |
| 1 | 2 | pattern_2024\|10\|36\|1 | 10 | 36 | 1 | 0.4354 | 5609 | 1422 | 2039 | 1842 | 89 | 140 | 77 | 26 | 26 | 26 | 1.9991 | False | 2.4809 |
| 1 | 3 | pattern_2024\|20\|233\|1 | 20 | 233 | 1 | 0.1178 | 882 | 272 | 349 | 261 | 0 | 0 | 0 | 1 | 1 | 1 | 3.0336 | True | 2.4809 |
| 2 | 1 | pattern_2024\|31\|22\|0 | 31 | 22 | 0 | 1.0000 | 1765 | 729 | 723 | 313 | 0 | 0 | 0 | 3 | 3 | 3 | 2.3187 | True | 1.0000 |

La auditoría completa añade NS/LN, filas fuente, peso β, distancia al centro, cola1 %, sexo, LN y concentración equivalente 1/Σβ². La concentración equivalente es un reparto de pesos, **no personas ni tamaño muestral efectivo**. Una sección puede estar presente en varias bandas: no se suman secciones como independientes.

| archetype | row_id | mean_beta | max_beta | starts_with_positive_weight | starts_as_largest_contributor | LN | min_sections | min_specified | high_ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | pattern_2024\|20\|351\|0 | 0.4907 | 0.8430 | 6 | 6 | 942 | 1 | 162 | False |
| 0 | pattern_2024\|30\|20\|0 | 0.4000 | 1.0000 | 4 | 4 | 2288 | 3 | 310 | False |
| 0 | pattern_2024\|20\|231\|0 | 0.1073 | 0.1873 | 6 | 0 | 961 | 1 | 170 | False |
| 0 | pattern_2024\|20\|108\|0 | 0.0021 | 0.0207 | 1 | 0 | 1430 | 2 | 301 | False |
| 1 | pattern_2024\|10\|36\|1 | 0.4119 | 0.4502 | 10 | 0 | 5609 | 26 | 1422 | False |
| 1 | pattern_2024\|16\|110\|0 | 0.3556 | 0.5103 | 10 | 6 | 1860 | 9 | 419 | False |
| 1 | pattern_2024\|20\|233\|1 | 0.2325 | 0.5034 | 10 | 4 | 882 | 1 | 261 | False |
| 2 | pattern_2024\|31\|22\|0 | 0.6000 | 1.0000 | 6 | 6 | 1765 | 3 | 313 | False |
| 2 | pattern_2024\|12\|55\|0 | 0.4000 | 1.0000 | 4 | 4 | 7010 | 38 | 1266 | True |

Un perfil sigue aportando β máximo=1.000; existen extremos con pocas secciones aun cumpliendo denominadores. Los aportantes cambian entre soluciones de semillas. Ello obliga a documentar el anclaje territorial, sin declarar errores por ser extremos o por recibir peso alto. El diagnóstico individual posterior es necesario para comprobar si ese anclaje es indispensable.

![extreme contributor concentration](../charts/archetypal_stability_review/extreme_contributor_concentration.png)

## Exclusiones temporales: E0, E1, E2 y E3

- **E0:** todos los4,571 elegibles.
- **E1:** excluye temporalmente ceil(0.01×4,571)=46 mayores distancias al centro de la geometría de entrenamiento E0; desempate por row_id. No utiliza OOB para diseñar el recorte.
- **E2:** excluye del entrenamiento cualquier perfil con alguna banda NS/LN≥10 % o con menos de cinco secciones distintas. No se relajan umbrales originales.
- **E3:** tres diagnósticos separados, cada uno retira sólo el mayor contribuyente β de un arquetipo del modelo E0. No se trata de retirar municipios completos ni demostrar error del perfil.

Todos usan diez inicializaciones y se eligen por SSE del entrenamiento correspondiente. E1/E2/E3 mantienen la escala E0 fija para aislar el cambio de población; se declaran sensibilidades, **no validaciones predictivas independientes de esas exclusiones**. En el remuestreo municipal la escala sí se reajusta exclusivamente en cada entrenamiento. Todos los escenarios se proyectan/evalúan sobre las mismas4,571 filas, incluidas las retiradas; no se modifica una fuente.

| scenario | seed | training_profiles | training_municipalities | LN_training | evaluation_profiles | evaluation_rmse_pp | max_curve_shift_pp | alpha_l1_mean | alpha_l1_p95 | alpha_l1_max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E0 | 1009 | 4571 | 2296 | 98119426 | 4571 | 2.5148 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| E1 | 1009 | 4525 | 2283 | 98040950 | 4571 | 2.8243 | 5.7667 | 0.0595 | 0.1189 | 0.1944 |
| E2 | 9001 | 2641 | 1333 | 79726708 | 4571 | 3.3413 | 9.6488 | 0.1148 | 0.2321 | 0.3331 |
| E3_archetype0 | 42 | 4570 | 2296 | 98118484 | 4571 | 2.5957 | 1.0482 | 0.0269 | 0.0412 | 0.0531 |
| E3_archetype1 | 42 | 4570 | 2296 | 98117566 | 4571 | 2.5219 | 0.6021 | 0.0101 | 0.0250 | 0.0437 |
| E3_archetype2 | 1009 | 4570 | 2296 | 98117661 | 4571 | 2.5553 | 2.0560 | 0.0246 | 0.0538 | 0.0750 |

E1 cambia curvas hasta **5.77 pp**. E2 deja 2,641 perfiles, LN=79,726,708, y cambia curvas hasta **9.65 pp**. No se interpreta ese cambio como efecto causal de NS: cambian cobertura y composición, además del ajuste finito. Excluir aproximadamente42 % de perfiles en E2 es una perturbación sustancial y no puede presentarse como una pequeña limpieza.

**E3 es más favorable que lo que sugería observar sólo β:** retirar uno a uno los mayores aportantes produce cambios máximos de 0.60–2.06 pp. No aparece un colapso por una sola observación. Otros extremos próximos pueden sostener la envolvente. No se concluye que cada ancla individual vuelva inválido el modelo, pero tampoco que la estabilidad individual resuelva la sensibilidad a conjuntos extremos o a la población territorial.

Son ajustes clásicos sobre entrenamientos temporalmente distintos. **No se implementa Robust Archetypal Analysis formal**, M-estimadores ni reponderación iterativa. No se eliminan registros, no se imputa NS y no se declara errónea una observación por pertenecer a una cola.

![exclusion sensitivity curves](../charts/archetypal_stability_review/exclusion_sensitivity_curves.png)

## Mezclas, diferencias por calidad y casos de mayor cambio

En la referencia completa K3, **95.69 %** tiene coeficiente máximo<0.8; 4.31 % supera o iguala ese umbral descriptivo. Entropía normalizada media=0.8230. Las mezclas describen una reconstrucción agregada, no una proporción de ciudadanos asignables a tipos.

El cambio L1 OOB medio por muestra tiene mediana **0.0253**, peor media 0.0804; el mayor cambio individual OOB es **0.2589** (escala L1 de0 a2). Se informan también p95 y máximo. Las medias pequeñas no deben esconder perfiles cuya mezcla cambia más.

| sample | seed | oob_rmse_pp | max_curve_shift_pp | oob_alpha_l1_mean | oob_alpha_l1_p95 | oob_alpha_l1_max |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 2024 | 2.8513 | 4.2871 | 0.0419 | 0.0960 | 0.1364 |
| 1 | 2027 | 2.6020 | 1.2474 | 0.0236 | 0.0356 | 0.0402 |
| 2 | 2024 | 2.3465 | 0.4518 | 0.0052 | 0.0100 | 0.0137 |
| 3 | 17 | 2.4653 | 2.7334 | 0.0252 | 0.0561 | 0.0825 |
| 4 | 1009 | 3.0066 | 8.2159 | 0.0706 | 0.1590 | 0.2424 |
| 5 | 9001 | 2.5049 | 0.5427 | 0.0055 | 0.0105 | 0.0158 |
| 6 | 9001 | 2.7983 | 0.7311 | 0.0120 | 0.0195 | 0.0283 |
| 7 | 2024 | 2.5829 | 6.5339 | 0.0804 | 0.1596 | 0.2589 |
| 8 | 11003 | 2.5046 | 2.9944 | 0.0253 | 0.0566 | 0.0889 |
| 9 | 2024 | 2.3461 | 2.2330 | 0.0300 | 0.0665 | 0.0884 |

| group | profiles | LN | rmse_pp | error_max_pp | dominated_fraction |
| --- | --- | --- | --- | --- | --- |
| 0 | 2276 | 47120572 | 2.5866 | 21.2873 | 0.0545 |
| 1 | 2295 | 50998854 | 2.4416 | 26.9404 | 0.0318 |

| grouping | group | profiles | LN | rmse_pp | error_max_pp | dominated_fraction |
| --- | --- | --- | --- | --- | --- | --- |
| high_ns | False | 3576 | 81261674 | 2.5754 | 26.9404 | 0.0397 |
| high_ns | True | 995 | 16857752 | 2.2838 | 23.3675 | 0.0553 |
| few_sections | False | 3421 | 96141059 | 1.9673 | 23.3675 | 0.0164 |
| few_sections | True | 1150 | 1978367 | 3.6912 | 26.9404 | 0.1226 |

Los estratos LN y entidades están en grouped_metrics; los grupos de NS y secciones se superponen y no se suman como observaciones únicas. Su diferencia de error no identifica causalidad, comportamiento individual o sesgo corregido.

Mayores casos individuales OOB, sin inventar observaciones ni asignar etiquetas rígidas:

| row_id | sample | alpha_l1 | reconstruction_difference_pp | rmse_pp |
| --- | --- | --- | --- | --- |
| pattern_2024\|20\|321\|1 | 7 | 0.2589 | 2.1742 | 17.4753 |
| pattern_2024\|20\|233\|1 | 4 | 0.2424 | 3.3443 | 29.8201 |
| pattern_2024\|21\|60\|1 | 7 | 0.2392 | 2.7380 | 6.1468 |
| pattern_2024\|20\|569\|0 | 7 | 0.2342 | 1.5138 | 15.9140 |
| pattern_2024\|16\|95\|1 | 4 | 0.2338 | 6.3193 | 7.1263 |

![mixture distributions](../charts/archetypal_stability_review/mixture_distributions.png)
![municipal coefficient changes](../charts/archetypal_stability_review/municipal_coefficient_changes.png)
![most unstable observations](../charts/archetypal_stability_review/most_unstable_observations.png)

## Curvas diferentes, reconstrucciones próximas e interpretación electoral

En comparaciones de semillas sobre **exactamente el mismo entrenamiento**, hay 46 pares K3 con cambio de curvas>5 pp y diferencia RMS de reconstrucciones<1 pp. 8 de esos pares sitúan ambas SSE dentro del1 % del mínimo de su muestra. Ejemplos:

| sample | left_trial | right_trial | left_excess_sse | right_excess_sse | max_curve_shift_pp | reconstruction_difference_rmse_pp | alpha_l1_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8 | municipal/sample008/k3/seed17 | municipal/sample008/k3/seed1009 | 0.0021 | 0.0005 | 11.7225 | 0.7908 | 0.1165 |
| 8 | municipal/sample008/k3/seed17 | municipal/sample008/k3/seed2027 | 0.0021 | 0.0005 | 11.7220 | 0.7908 | 0.1165 |
| 8 | municipal/sample008/k3/seed17 | municipal/sample008/k3/seed2024 | 0.0021 | 0.0005 | 11.7217 | 0.7908 | 0.1165 |
| 8 | municipal/sample008/k3/seed17 | municipal/sample008/k3/seed11003 | 0.0021 | 0.0000 | 11.6133 | 0.7854 | 0.1156 |
| 7 | municipal/sample007/k3/seed42 | municipal/sample007/k3/seed5003 | 0.0097 | 0.0000 | 6.4790 | 0.5246 | 0.0727 |

Es evidencia de identificación empírica débil de los **extremos aprendidos**, o de soluciones cercanas del optimizador que representan de modo parecido el interior. No demuestra que todas sean mínimos globales equivalentes. K3 tiene rango afín2 en estas soluciones; para un triángulo fijo no degenerado los coeficientes de un punto de su plano son únicos. La variación al mover el triángulo es distinta de afirmar no unicidad formal de α con Z fijo. El optimizador NNLS aumentado es aproximado, como ya se documentó.

![curve reconstruction equivalence](../charts/archetypal_stability_review/curve_reconstruction_equivalence.png)

Contrastes de la referencia elegida por SSE:

| archetype | level_pp | young_minus_older_pp | adult_minus_endpoint_mean_pp | shape_range_pp |
| --- | --- | --- | --- | --- |
| 0 | -17.5824 | -34.9217 | 1.7632 | 34.9217 |
| 1 | -17.7573 | 34.4380 | 1.2033 | 34.4380 |
| 2 | 35.7764 | 20.5576 | 2.7139 | 20.5576 |

- A0: nivel medio -17.58 pp, contraste joven−mayor -34.92 pp y curvatura adulta +1.76 pp. Son diferencias agregadas frente a pares, no motivaciones.
- A1: nivel medio -17.76 pp, contraste joven−mayor +34.44 pp y curvatura adulta +1.20 pp. Son diferencias agregadas frente a pares, no motivaciones.
- A2: nivel medio +35.78 pp, contraste joven−mayor +20.56 pp y curvatura adulta +2.71 pp. Son diferencias agregadas frente a pares, no motivaciones.

Rangos de nivel y contraste entre las diez muestras seleccionadas con diez arranques:

| archetype | level_min_pp | level_max_pp | young_older_min_pp | young_older_max_pp |
| --- | --- | --- | --- | --- |
| 0 | -18.2698 | -12.7597 | -36.9277 | -33.7623 |
| 1 | -23.5404 | -10.2643 | 26.9974 | 42.6928 |
| 2 | 33.6957 | 35.7764 | 19.5330 | 26.8691 |

Los contrastes amplios permiten describir un nivel positivo y dos patrones de nivel negativo con contrastes de edad diferentes. Las amplitudes y algunas diferencias cercanas a cero cambian; no debe presentarse la curva exacta como una esencia territorial. Los arquetipos son mezclas de perfiles, pueden corresponder a vértices excepcionales de la envolvente y **no estiman la prevalencia de un tipo ciudadano**. Sus coeficientes se extienden por el interior; un peso β alto no significa que ese patrón sea frecuente. Las características disponibles no explican motivaciones, preferencias partidistas o barreras personales.

![electoral level and shape](../charts/archetypal_stability_review/electoral_level_and_shape.png)

## Utilidad frente a los seis perfiles y a indicadores sencillos

Las seis reglas permanecen intactas y son la propuesta principal del proyecto. Su unidad es municipio×sexo×banda; AA usa municipio×sexo. Se pivota una firma de tres etiquetas y se une uno a uno a4,571 perfiles; no se multiplican filas para métricas, no se calcula ARI entre unidades incompatibles y no se entrenan las reglas de nuevo. Los municipios y sexos pueden compartir firmas y tener intensidades distintas.

Ejemplos reales con la misma firma, cuyos niveles, formas y mezclas son diferentes:

| row_id | EDOCVE | MPIOCVE | SEXO | rule_signature | relative_level | shape_contrast_1 | shape_contrast_2 | alpha_0 | alpha_1 | alpha_2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pattern_2024\|20\|455\|0 | 20 | 455 | 0 | young_unfavorable / adult_unfavorable / older_unfavorable | -0.1679 | -0.1226 | -0.1868 | 0.9483 | 0.0369 | 0.0148 |
| pattern_2024\|16\|95\|0 | 16 | 95 | 0 | young_unfavorable / adult_unfavorable / older_unfavorable | -0.1729 | 0.1010 | 0.1867 | 0.0622 | 0.9297 | 0.0082 |

La identidad d=m1+qQᵀ reconstruye los datos desde **nivel y dos contrastes existentes** con residuo máximo 1.11e-16. Estos indicadores conservan los tres grados de libertad; los coeficientes K3 suman uno y tienen dos grados de libertad para un triángulo aprendido. La identidad sin pérdida y AA no son modelos con la misma complejidad: su error cero no es una victoria predictiva de otro algoritmo.

AA es una función aprendida de esos mismos datos: no añade información observacional. Puede aportar una metáfora visual de mezclas, pero no se demostró una ventaja de comunicación frente a mostrar m y la curva de forma por edades. Ambos describen intensidad dentro de los mismos signos de reglas. Los indicadores originales con referencia nacional fija no cambian al retirar municipios del ajuste; esto es estabilidad algebraica condicional, no ausencia de error electoral o validación predictiva. No requieren seleccionar perfiles ancla, ni resolver qué semilla o triángulo comunicar.

La opción B aprovecha esos indicadores como contexto de las seis fichas: nivel relativo, contrastes por edad, conteos, NS y soporte. Esta entrega **no cambia la app ni crea variables nuevas de clustering**. AA se conserva íntegro como evidencia de investigación; no se transforma su mayor capacidad de reconstrucción en una nueva tipología.

![rule profiles and simple indicators](../charts/archetypal_stability_review/rule_profiles_and_simple_indicators.png)

## Decisión y respuestas obligatorias

**Opción elegida: B. Utilizar indicadores continuos sin arquetipos.** El beneficio es una comunicación directa y reproducible de magnitud/forma con la cobertura intacta, sin anclas dependientes del ajuste. El riesgo es renunciar al resumen visual de mezclas que puede ser útil para exploración especializada. No se adopta A porque persisten diferencias de extremos de 8.22 pp entre muestras y 9.65 pp ante calidad, soluciones de SSE cercana con curvas diferentes y utilidad adicional de comunicación no comprobada. No se elige C como recomendación principal porque los indicadores continuos sí proporcionan una alternativa interpretable para complementar las fichas; AA permanece documentado, sin publicación.

1. **¿Cuánto provenía de inicializaciones?** Con datos fijos hay hasta 17.32 pp entre curvas de semillas. En el diseño balanceado actual, 66.44 % de la dispersión alineada está dentro de entrenamientos. No se identifica un porcentaje causal exacto de la inestabilidad del informe anterior.
2. **¿Cuánto persiste con múltiples arranques?** El peor desplazamiento municipal baja de 17.78 a 8.22 pp frente a la misma referencia nueva. Persisten pares a≤1 % del mejor SSE con curvas diferentes; selección entre diez reduce, no elimina, optimización residual.
3. **¿K3 mantiene su mejora OOB?** Sí: 2.544 frente a 6.439 pp de K2, con reducción en las diez muestras. La mayor reconstrucción no certifica tres clases naturales.
4. **¿Siguen dependiendo de extremos?** Sí en su construcción β y sensibilidad a la cola de perfiles; el máximo β es 1.000. Pero retirar individualmente cada mayor aportante sólo desplaza hasta 2.06 pp: no hay evidencia de colapso por una observación aislada.
5. **¿Sensibilidad a calidad?** E2 conserva 2,641 perfiles entrenados y desplaza hasta 9.65 pp; evalúa todos. Es una perturbación fuerte de población/cobertura, no prueba de error, ni efecto causal puro de NS o secciones.
6. **¿Coeficientes reproducibles e interpretables?** Son interpretables como reconstrucciones convexas agregadas, con L1 OOB mediano entre muestras 0.0253 y máximo individual 0.2589. Su interpretación depende del triángulo alineado y no representa probabilidades de comportamiento.
7. **¿K3 aporta frente a K2?** Sí para reconstruir contrastes, con menor error OOB; su estabilidad de extremos es menor que la del control. No hay suficiente base para una tipología electoral definitiva.
8. **¿Supera indicadores continuos?** No se demostró una utilidad adicional de comunicación. Nivel y dos contrastes conservan exactamente los datos medidos, sin seleccionar extremos; AA resume con pérdida y añade una metáfora, no observaciones.
9. **¿Usarlo como complemento en ParticipaMX?** En esta entrega se recomienda B: indicadores continuos junto a las seis reglas; no publicar AA. Un uso posterior requeriría validar con usuarios la comprensión de curvas/mezclas y las advertencias, además de resolver la sensibilidad residual.
10. **¿Límites para el jurado?** Unidades agregadas/ecológicas; referencias nacionales fijas; soporte y NS desiguales; cobertura municipal parcial; geometría50/50 elegida; optimización finita; sólo diez muestras; arquetipos próximos a extremos; no inferir prevalencia, motivaciones, probabilidades individuales o causalidad. Los seis perfiles por reglas siguen siendo la entrega principal conforme al alcance solicitado; estos tres arquetipos no los sustituyen ni son tres clusters exigidos.

## Entregables, integridad y recuperación

`reference/` conserva perfiles completos/elegibles, pendientes, referencias y broad complementaria. `matrices/` guarda matriz y escala principal; cada modelo registra su escala, máscara y hash de entrenamiento. `models/` conserva nuevos modelos joblib y arrays α/β/arquetipos/reconstrucciones; `reused/` guarda referencias verificadas a modelos anteriores, sin copiarlos o sobrescribirlos. `metadata/` contiene todos los arranques, selección, presupuestos, dispersión, cobertura y decisión. `diagnostics/` conserva alineaciones, curvas, aportantes con conteos por banda, pares y casos OOB. `selected/` mantiene coeficientes y NULL de pendientes; `comparisons/` enlaza reglas e indicadores.

Hay checkpoints A–F y marcadores por modelo, escrituras atómicas y comprobación de lectura de Parquet. Se conserva cada ajuste desfavorable y el estado de parada; una incidencia se registra en state.json y no borra modelos válidos. Un lock exclusivo y consulta de procesos evitan duplicados. Las pruebas verifican selección sin OOB, identidad de varianza, permutaciones, convexidad, escalas de entrenamiento, agrupación de sexos por municipio, todos los arranques, conservación de conteos, E3 y uniones sin expansión. Se verifican por hash **7323 archivos previos** y los manifiestos de las cuatro fuentes. _SUCCESS se escribe sólo tras pruebas e integridad final.

```powershell
.venv_archetypal_patterns/Scripts/python.exe analysis/scripts/validate_archetypal_stability.py
.venv_archetypal_patterns/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_validate_archetypal_stability.py
```

Reanudar con las mismas rutas verifica y omite etapas/modelos íntegros. --stop-after permite detener tras una etapa; --refresh-report archiva únicamente el informe de esta entrega y regenera su documentación final sin reajustar modelos. Cambios de parámetros o versiones exigen --output, --charts y --report nuevos. No se modifican los experimentos anteriores, las seis reglas, datos originales, frontend ni public/data; no se crean commits. No se ejecuta AA robusto formal ni se prueban K4–6.
