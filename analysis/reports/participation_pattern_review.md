# Patrones de participación entre edades · experimento recuperable de 2024

## Diagnóstico de recuperación y alcance

El turno anterior se interrumpió durante lecturas y planificación: no existían script, informe ni destinos de este experimento y no se encontraron procesos Python activos con Get-Process. La consulta CIM fue denegada, por lo que se usó una consulta alternativa no destructiva. No había modelos incompletos que recuperar ni se reinició un experimento ya ejecutado. Se reutilizaron las comprobaciones previas de esquema y cobertura. El diagnóstico original se conserva en metadata/recovery_diagnosis.json; estado e incidencias de ejecución quedan en metadata/state.json.

Se completaron las etapas A–F: validación, matrices, **45 ajustes completos**, métricas, hasta dos candidatas con 10 submuestras municipales y reporte final. Sólo se utiliza K-Means NumPy validado del proyecto; no se ejecutaron GMM, HDBSCAN o K-Medoids. No se eligieron perfiles definitivos. La unidad es **municipio + sexo**, con tres coordenadas de edad; no personas ni segmentos individuales de edad.

**Resultado:** R2 permite describir diferencias entre edades que R1 oculta detrás del nivel general. Sin embargo, el contraste jóvenes–mayores concentra 86.30 % de la varianza de forma: los grupos son principalmente divisiones de ese gradiente, sin demostrar tipos discretos. R2 K=2 merece continuar como resumen exploratorio parsimonioso; K=4 añade resolución y presenta una peor cola de estabilidad. No hay evidencia suficiente para imponer cuatro a seis perfiles definitivos ni reemplazar automáticamente C o B.

## Cobertura y soporte antes de entrenar

Hay **4,954 perfiles H/M disponibles**, 4,930 con tres tasas definidas y **4,648 con soporte en las tres coordenadas**, correspondientes a **2,341 municipios** y LN=98,153,652 (99.82 % del LN nacional). En 2,307 municipios entran ambos sexos y en 34 entra uno; 136 no aportan ningún perfil elegible. No se interpreta la cobertura nominal alta como representatividad territorial completa.

| SEXO | Perfiles disponibles | Tres tasas definidas | Elegibles | LN disponible 18–100 |
| --- | --- | --- | --- | --- |
| 0 | 2477 | 2465 | 2312 | 47221785 |
| 1 | 2477 | 2465 | 2336 | 51095261 |

El C broad anterior tenía 2,307 municipios elegibles, LN municipal total=98,146,493 y LN núcleo H/M 18–100=98,133,253. La comparación de alcance usa ese núcleo para evitar mezclar edades/categorías. Los 34 municipios adicionales se representan parcialmente: no recuperan automáticamente un perfil territorial de ambos sexos. El corte preventivo definido antes de entrenar era caída >5 pp en municipios o >1 pp de LN respecto al núcleo C; no se activó. No se relajaron umbrales.

Los criterios siguen siendo LN≥100, SV+NV≥100 y filas fuente≥5 en **cada** banda. Las filas fuente son celdas, no cinco secciones independientes ni un tamaño de muestra de votantes. NS alto no excluye del principal. Cada perfil conserva los cuatro conteos por banda, denominadores, NS/LN, soporte, claves textuales, sexo y marco distrital. Las tasas NULL no se imputan; los pendientes conservan etiquetas NULL. Las coordenadas presentes conocidas permanecen en referencia aunque el perfil completo no sea elegible.

Se conservan 306 perfiles pendientes: 24 con alguna tasa no definida y 282 definidos pero sin soporte en las tres coordenadas. Los motivos y soporte por banda se guardan por observación, sin filtros permanentes.

| Alcance | Perfiles | LN | Perfiles NULL | Alguna banda NS≥10 % | NS/LN agregado | Q1 NS/LN | Mediana | Q3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| available | 4954 | 98317046 | 24 | 1059 | 0.0643 | 0.0000 | 0.0263 | 0.0778 |
| eligible | 4648 | 98153652 | 0 | 999 | 0.0635 | 0.0000 | 0.0302 | 0.0787 |

Los 136 municipios sin representación se localizan en metadata/unrepresented_municipalities.parquet; metadata/state_coverage.csv describe las 32 entidades. SEXO=2, edades 101+ y sus 105 filas fuente/LN de la categoría de sexo se conservan en la referencia broad completa, sin integrarse a H/M ni inventar tasas; no entran en esta matriz comparable de tres bandas. La base exacta anterior sigue intacta y trazable.

Entidades con menor cobertura nominal dentro del núcleo H/M 18–100 (denominador distinto del LN nacional completo):

| Entidad | Nombre | Perfiles | Municipios | LN elegible | Fracción LN del núcleo estatal |
| --- | --- | --- | --- | --- | --- |
| 20 | OAXACA | 883 | 456 | 3039403 | 0.9754 |
| 7 | CHIAPAS | 243 | 122 | 3958724 | 0.9890 |
| 26 | SONORA | 125 | 63 | 2276346 | 0.9937 |
| 16 | MICHOACAN | 224 | 112 | 3734051 | 0.9962 |
| 29 | TLAXCALA | 118 | 59 | 1039956 | 0.9975 |
| 21 | PUEBLA | 422 | 212 | 4973791 | 0.9992 |
| 5 | COAHUILA | 74 | 37 | 2408646 | 0.9992 |
| 31 | YUCATAN | 210 | 105 | 1764964 | 0.9995 |

![Cobertura municipal y nominal](../charts/participation_pattern_review/coverage.png)

## Construcción de nivel y forma

Las tasas 18–34, 35–59 y 60–100 se verificaron contra c_broad/cell_metadata.parquet y sus seis columnas originales. La referencia nacional por intervalo/sexo es ΣSV/Σ(SV+NV), calculada con todos los conteos antes de seleccionar soporte. No se promedian tasas de municipios para obtenerla. Para cada perfil, d=(d₁,d₂,d₃) son las diferencias nacionales, m=(d₁+d₂+d₃)/3 y s=d−m·1.

**m no es participación agregada**: esta última es ΣSV/Σ(SV+NV), con denominadores distintos por banda y una referencia contextual distinta. Se guardan ambas. Los tres intervalos tienen igual peso conceptual en m, independientemente de su anchura o LN. s suma cero y tiene dos grados de libertad. Se usa una base fija ortonormal Q, no un PCA aprendido: q₁=(d₁−d₂)/√2 y q₂=(d₁+d₂−2d₃)/√6. ||d||²=3m²+||q||² y s=qQᵀ. Los valores s de las tres bandas se conservan para interpretar curvas.

- **R1:** tres diferencias, centradas por su media poblacional y divididas por una sola escala RMS del vector. Preserva distancia euclídea con igual peso de bandas. No estandariza cada banda por separado. En el universo elegible, el nivel aporta **82.34 %** de la varianza total de d.
- **R2:** retira el promedio de cada observación; guarda dos contrastes equivalentes a la forma de tres bandas. Sólo centra globalmente los contrastes y aplica una escala RMS al bloque. No divide cada fila por su norma: conserva amplitud de las diferencias. Es invariante a añadir una constante a las tres diferencias de una observación. La edad es nombre de coordenada, no edad media numérica.
- **R3:** un bloque de nivel m con DE poblacional y un bloque de forma con RMS total; cada uno recibe 50 % de varianza a priori. No repite las tres diferencias junto con m. El peso es predefinido, no elegido por Silhouette. La contribución entre clusters puede diferir de 50 %.

Las escalas se ajustan sólo sobre los mismos 4,648 elegibles; cada remuestra las reajusta sólo in-bag. R2 puede conservar asociación indirecta con nivel o sexo si éstos se relacionan con la forma, aunque no entren como coordenadas. No se introduce edad media, TIPOSEC, identidad territorial ni SEXO como magnitud de distancia. Se da igual peso a cada perfil; un municipio con ambos sexos aporta dos observaciones y uno parcialmente cubierto aporta una.

## Experimento principal acotado

Se ejecutan R1/R2/R3 × K=2…6 × semillas 17/42/2024: **45 ajustes**, cada uno con 10 arranques k-means++, máximo 1000 iteraciones, parada con etiquetas estables y comprobación de K grupos no vacíos. K=6 es sensibilidad. Se conserva cada modelo y sus inicializaciones, SSE, convergencia, tiempos y centroides. No se cambian segmentos para mejorar índices.

Silhouette es **aproximado**, con 512 anclas uniformes reproducibles compartidas; cada ancla se compara contra todos los elegibles mediante bloques de 32×N. Se guarda su error Monte Carlo. DB usa todos los perfiles. No se construye matriz N×N ni se generan gráficas durante ajustes. La memoria del buffer de distancias es aproximadamente 1.13 MiB, más matrices/indicadores; working set y pico observados por API Windows constan en cada checkpoint (no son una garantía de cota máxima). Los segundos por modelo y etapa se registran. Las métricas de geometrías distintas no clasifican universalmente utilidad.

| Representación | K | S aproximado | DB | Grupo mínimo medio | R² nivel | R² forma | Nivel/separación | Pureza sexo | ARI semillas mín. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| r1 | 2 | 0.4435 | 0.8061 | 2210.0000 | 0.6251 | 0.1143 | 0.9623 | 0.5349 | 1.0000 |
| r1 | 3 | 0.3595 | 0.9084 | 1241.0000 | 0.7949 | 0.1401 | 0.9636 | 0.5340 | 1.0000 |
| r1 | 4 | 0.3273 | 0.9434 | 613.6667 | 0.8696 | 0.1708 | 0.9596 | 0.5345 | 0.9938 |
| r1 | 5 | 0.3408 | 0.9075 | 585.6667 | 0.8655 | 0.4511 | 0.8995 | 0.5517 | 0.9957 |
| r1 | 6 | 0.3296 | 0.8998 | 278.6667 | 0.8992 | 0.4698 | 0.8992 | 0.5707 | 0.9952 |
| r2 | 2 | 0.4365 | 0.7903 | 2180.0000 | 0.1448 | 0.5363 | 0.0000 | 0.5882 | 1.0000 |
| r2 | 3 | 0.3838 | 0.8723 | 1181.6667 | 0.1665 | 0.6848 | 0.0000 | 0.5749 | 0.9911 |
| r2 | 4 | 0.3468 | 0.8765 | 606.0000 | 0.1738 | 0.7591 | 0.0000 | 0.5828 | 1.0000 |
| r2 | 5 | 0.3643 | 0.8618 | 555.3333 | 0.1731 | 0.7988 | 0.0000 | 0.5972 | 0.9967 |
| r2 | 6 | 0.3663 | 0.8303 | 397.0000 | 0.1887 | 0.8322 | 0.0000 | 0.5914 | 1.0000 |
| r3 | 2 | 0.3581 | 1.0447 | 2321.0000 | 0.4626 | 0.3760 | 0.5516 | 0.5695 | 1.0000 |
| r3 | 3 | 0.3374 | 1.0142 | 891.0000 | 0.5936 | 0.5050 | 0.5403 | 0.5721 | 1.0000 |
| r3 | 4 | 0.3024 | 1.0241 | 802.0000 | 0.7282 | 0.5615 | 0.5646 | 0.5714 | 1.0000 |
| r3 | 5 | 0.2760 | 1.0935 | 593.6667 | 0.7935 | 0.5956 | 0.5712 | 0.5658 | 0.9878 |
| r3 | 6 | 0.2718 | 1.0196 | 439.3333 | 0.7966 | 0.6728 | 0.5422 | 0.5734 | 0.9848 |

Los R² son fracciones de varianza descriptiva explicada por etiquetas, sin validación predictiva ni causalidad. R² forma usa la suma de cuadrados de los dos contrastes; nivel/separación mide su contribución real en el espacio del ajuste. R2 fuerza contribución directa de nivel cero por construcción, pero no fuerza R² nivel cero. La menor SSE entre semillas representa cada configuración/K sin elegir un K definitivo.

![Métricas por K](../charts/participation_pattern_review/metrics_by_k.png)

![Nivel y forma originales; proyección parcial](../charts/participation_pattern_review/level_and_shape.png)

Un contraste fijo entre jóvenes y mayores, (d₁−d₃)/√2, concentra **86.30 %** de la varianza de forma; la curvatura (d₁−2d₂+d₃)/√6 aporta 13.70 %. Su correlación es -0.0274. Esta rotación ortonormal es sólo un diagnóstico de las mismas dos dimensiones: no se entrena otro modelo ni se hace reducción de dimensión. Un gradiente predominante puede producir particiones reproducibles aunque no existan poblaciones discretas; este piloto no prueba multimodalidad.

| Contraste fijo | Media (pp) | DE (pp) | Fracción de varianza de forma |
| --- | --- | --- | --- |
| young_older | 2.1145 | 8.3383 | 0.8630 |
| middle_curvature | -1.9350 | 3.3222 | 0.1370 |

![Plano completo de forma y densidad sin etiquetas](../charts/participation_pattern_review/shape_space.png)

## Curvas y composición

![Curvas R2, K=2](../charts/participation_pattern_review/curves_r2_k2.png)

![Curvas R2, K=4](../charts/participation_pattern_review/curves_r2_k4.png)

Las curvas muestran diferencias relativas originales, forma tras retirar nivel y tasas absolutas medias. Las medias de perfiles dan peso uno a municipio/sexo; la tasa agregada por banda usa conteos sumados y se guarda separadamente. Una forma positiva en jóvenes y negativa en mayores significa desvío respecto al nivel relativo de ese perfil, no que la participación absoluta juvenil sea mayor que la de mayores.

| Representación | K | Etiqueta local | Perfiles | Municipios | LN | Fracción LN entrenado | Fracción mujeres | Participación agregada | Nivel relativo medio | NS/LN | Alguna banda NS alto |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| r2 | 2 | 0 | 2180 | 1371 | 23263657 | 0.2370 | 0.5968 | 0.6365 | 0.0714 | 0.0671 | 0.2670 |
| r2 | 2 | 1 | 2468 | 1521 | 74889995 | 0.7630 | 0.4194 | 0.5845 | -0.0139 | 0.0624 | 0.1690 |
| r2 | 4 | 0 | 1597 | 1163 | 22717991 | 0.2315 | 0.6024 | 0.6254 | 0.0646 | 0.0652 | 0.2611 |
| r2 | 4 | 1 | 738 | 485 | 4168600 | 0.0425 | 0.5474 | 0.6505 | 0.0821 | 0.0794 | 0.2724 |
| r2 | 4 | 2 | 606 | 475 | 3633868 | 0.0370 | 0.2327 | 0.5248 | -0.0505 | 0.0535 | 0.1386 |
| r2 | 4 | 3 | 1707 | 1222 | 67633193 | 0.6891 | 0.4856 | 0.5878 | -0.0070 | 0.0625 | 0.1740 |

Forma media en puntos porcentuales para los controles R2 K=2 y K=4, usando la semilla de menor SSE de cada K:

| K | Etiqueta local | 18–34 (pp) | 35–59 (pp) | 60–100 (pp) |
| --- | --- | --- | --- | --- |
| 2.0000 | 0.0000 | 5.4944 | 1.8789 | -7.3733 |
| 2.0000 | 1.0000 | -3.5250 | 1.3158 | 2.2092 |
| 4.0000 | 0.0000 | 3.0096 | 2.0530 | -5.0626 |
| 4.0000 | 1.0000 | 9.6775 | 1.7554 | -11.4329 |
| 4.0000 | 2.0000 | -9.3430 | 2.6370 | 6.7060 |
| 4.0000 | 3.0000 | -1.7624 | 0.6862 | 1.0762 |

Con K=2 aparece un contraste relativo favorable a jóvenes frente a mayores y otro en sentido inverso. No significa que los jóvenes siempre voten más: la tasa absoluta media de cada banda figura en las gráficas. K=4 subdivide principalmente intensidades de esa inclinación; aumenta R² forma de 53.63 % a 75.91 %, con menor Silhouette (0.4365 frente a 0.3468) dentro del mismo espacio. No demuestra cuatro mecanismos electorales. El R² nivel de R2 K=2 es 14.48 %: retirar nivel de la distancia no elimina su asociación con forma.

Las diferencias de composición por sexo y de NS entre clusters exigen revisión sustantiva. Se usa la misma referencia nacional específica por sexo, pero no se garantiza independencia de sexo, cobertura o tamaño territorial. No se ejecutó aquí una sensibilidad de pesos o un ajuste sin NS alto: los 999 perfiles con alguna coordenada NS≥10 % permanecen en el principal. No se interpreta su asociación como causalidad.

Cada observación contiene las tres bandas: no existe una distribución de etiquetas de edad por observación como en B. La composición etaria se describe con LN por banda en cluster_curves.csv, no inventando edades individuales. Sexo y municipios representados se conservan para interpretar grupos. Un municipio puede aportar sus sexos a clusters diferentes; no sumar municipios de clusters como territorios únicos.

Entre los municipios con ambos sexos elegibles, la concordancia local se describe sin imponer etiquetas iguales a H/M:

| Representación | K | Municipios con H/M | Misma etiqueta local | Etiquetas distintas | Fracción con misma etiqueta |
| --- | --- | --- | --- | --- | --- |
| r2 | 2 | 2307 | 1756 | 551 | 0.7612 |
| r2 | 4 | 2307 | 1303 | 1004 | 0.5648 |

![Composición por sexo](../charts/participation_pattern_review/sex_composition.png)

## Estabilidad municipal limitada

Se seleccionaron como máximo dos configuraciones después de D; metadata/candidate_selection.json registra criterios, candidatas y hash de evidencia. Se reutilizan las primeras 10 membresías municipales anteriores: 1,981 de 2,477 municipios por submuestra sin reemplazo. Entran juntos ambos sexos elegibles de un municipio. No se reconstruyen perfiles ausentes ni se mezclan municipios para crear observaciones.

ARI OOB compara etiquetas proyectadas en municipios fuera del entrenamiento frente al mejor ajuste completo de la misma representación/K. La referencia nacional permanece fija y contiene información de todo 2024: no es validación predictiva independiente de ese contexto nacional. Las escalas y centroides sí se ajustan sin OOB. Los porcentajes de cambio se alinean por máximo solapamiento; etiquetas numéricas no tienen orden o identidad propia.

| Representación | K | ARI OOB mediana | q10 | Mínimo | Muestras <0.90 | Máx. fracción cambio |
| --- | --- | --- | --- | --- | --- | --- |
| r2 | 2 | 0.9829 | 0.9571 | 0.9533 | 0 | 0.0118 |
| r2 | 4 | 0.9737 | 0.9063 | 0.8368 | 1 | 0.0591 |

| Representación | K | Muestra | ARI OOB | ARI in-bag | Cambio OOB alineado |
| --- | --- | --- | --- | --- | --- |
| r2 | 4 | 3 | 0.8368 | 0.8714 | 0.0591 |
| r2 | 4 | 1 | 0.9140 | 0.9394 | 0.0314 |
| r2 | 2 | 5 | 0.9533 | 0.9711 | 0.0118 |
| r2 | 4 | 7 | 0.9571 | 0.9575 | 0.0161 |
| r2 | 2 | 7 | 0.9575 | 0.9417 | 0.0107 |
| r2 | 4 | 9 | 0.9592 | 0.9581 | 0.0151 |

![Estabilidad y cambio de patrones](../charts/participation_pattern_review/municipality_stability.png)

Se conservan coberturas de cada muestra, pertenencias, etiquetas/proyecciones y cambios RMS de las curvas de forma alineadas (pp). Diez submuestras sólo aportan un diagnóstico exploratorio: no prueban estabilidad general, grupos naturales o ausencia de sesgo por NS/soporte. No se entrenaron todas las combinaciones mediante remuestreo.

R2 K=2: ARI OOB mediano 0.983, mínimo 0.953, 0/10 muestras por debajo de 0.90; máximo cambio alineado 1.18 %. R2 K=4: ARI OOB mediano 0.974, mínimo 0.837, 1/10 muestras por debajo de 0.90; máximo cambio alineado 5.91 %.

Las submuestras contienen 3,702–3,723 perfiles de 1,865–1,876 municipios elegibles, y 77.50 %–82.73 % del LN elegible completo. Quedan 925–946 perfiles OOB. El cambio RMS máximo de los centros de forma alineados es 0.420 pp; un centro medio poco desplazado no garantiza etiquetas individuales estables. La peor muestra se conserva junto con las demás, sin descartarla para mejorar el resumen.

## Comparación con el C territorial anterior

El C anterior tenía una fila por municipio y seis tasas H/M. Aquí hay una fila por municipio/sexo y tres tasas con referencia nacional explícita; las etiquetas no se comparan mediante ARI entre unidades incompatibles. Los índices internos tampoco tienen la misma geometría. Como antecedente descriptivo, C broad estandarizado daba:

| K previo | S previo | Nivel/separación previo | Forma/separación previa | R² nivel previo | R² forma previa |
| --- | --- | --- | --- | --- | --- |
| 2.0000 | 0.4193 | 0.9792 | 0.0208 | 0.6283 | 0.0544 |
| 3.0000 | 0.3379 | 0.9781 | 0.0219 | 0.7927 | 0.0722 |
| 4.0000 | 0.2993 | 0.9734 | 0.0266 | 0.8705 | 0.0967 |
| 5.0000 | 0.3150 | 0.9074 | 0.0926 | 0.8684 | 0.3607 |
| 6.0000 | 0.2857 | 0.9099 | 0.0901 | 0.9040 | 0.3644 |

La forma anterior incluía las seis coordenadas de edad/sexo y no es idéntica a los dos contrastes actuales; no restar sus R² como si midieran exactamente lo mismo. En R1 actual, K=2 aporta 96.23 % de separación de nivel; R2 permite examinar forma independientemente de ese término, con asociación residual de nivel cuantificada arriba. Ésta es la aportación metodológica nueva, no una demostración automática de mejores perfiles.

## Conclusiones y decisiones pendientes

1. **Patrones o niveles:** sí hay diferencias descriptivas entre edades en R2, principalmente un gradiente jóvenes–mayores (86.30 % de varianza de forma). R1 K=2 sigue separando niveles: 96.23 % de la separación corresponde a nivel. R3 conserva entre 54.03 % y 57.12 % de separación en ese bloque por diseño mixto. No se descubren tipos individuales ni se prueba que el gradiente tenga cortes naturales.
2. **Interpretación:** separar nivel y forma mejora la lectura del patrón relativo. R2 diferencia trayectorias que una tasa total no describe; K=4 añade principalmente intensidad al contraste, no cuatro formas cualitativas demostradas. El promedio simple no sustituye la participación agregada y las tasas absolutas siguen siendo necesarias.
3. **Cobertura:** 2,341 municipios y 99.82 % del LN, con 34 municipios parcialmente representados. La cobertura no cae frente al núcleo C broad, pero quedan municipios y perfiles pendientes.
4. **Estabilidad:** R2 K=2: ARI OOB mediano 0.983, mínimo 0.953, 0/10 muestras por debajo de 0.90; máximo cambio alineado 1.18 %. R2 K=4: ARI OOB mediano 0.974, mínimo 0.837, 1/10 muestras por debajo de 0.90; máximo cambio alineado 5.91 %. K=2 tiene concordancia suficiente para continuar como exploración; K=4 requiere cautela por su peor muestra. Semillas concordantes no sustituyen estabilidad municipal, y diez submuestras no bastan para adopción definitiva.
5. **Cuatro a seis perfiles:** no están justificados como rango obligatorio. En R2 el máximo S de anclas está en K=2 (0.4365); el gradiente y la estabilidad limitada favorecen comenzar con menos grupos para resumir, manteniendo K=4 como detalle experimental. Los mayores R² de K altos son esperables al refinar una partición y no prueban nuevos perfiles. K=6 sigue siendo sensibilidad; no se selecciona K definitivo.
6. **Novedad:** pasa de seis tasas municipales dominadas por nivel a trayectorias relativas por sexo y forma explícita. Cambia la unidad y la pregunta; no reemplaza directamente al C o B anteriores ni justifica inferencias individuales.
7. **Uso en ParticipaMX:** sí merece continuar R2 como vista exploratoria de patrones relativos por edad y sexo, con R1/C/B como controles de nivel y de otras unidades. No se recomienda publicar cuatro a seis perfiles ciudadanos definitivos ni sustituir automáticamente C territorial. Para una presentación es más defendible mostrar curvas, denominadores y un resumen parsimonioso provisional, reconociendo el gradiente continuo y las exclusiones por soporte. Antes de adoptar etiquetas deben contrastarse pesos por municipio, NS elevado, sensibilidad de bandas/escala y referencias, sexos y validación electoral. No se atribuye a esta entrega una robustez que no se probó.

## Recuperación, integridad y reproducción

Checkpoints A–F incluyen hashes, resumen, duración, versiones y memoria aproximada. Los modelos y remuestras tienen bundles NPZ/JSON con marcador verificable individual: se omiten al reanudar, aunque la etapa no hubiera terminado. Los temporales sólo se publican por reemplazo atómico tras validar lectura. Un lock exclusivo impide duplicar procesos; locks muertos se archivan y procesos no verificables bloquean otro inicio. Los archivos incompletos propios se preservan en incomplete/; un hash incorrecto de un checkpoint detiene la ejecución sin sobrescribirlo. No se repiten automáticamente pasos costosos validados.

Se verificaron referencias por conteos, unicidad, claves de texto, LN=SV+NV+NS, igualdad con C broad, elegibilidad de ambos sexos, suma cero/identidades de forma, finitud, centroides/SSE por groupby independiente, conservación por cluster, NULL de pendientes y lectura posterior de salidas. Los hashes de 2,820 archivos previos se comprueban antes de finalizar. No se modificaron datos, informes anteriores, ZIP, frontend ni se crearon commits. No se procesaron CSV originales ni la base histórica. Scikit-learn/SciPy siguen sin usarse; las pruebas NumPy y matemáticas no sustituyen un contraste de biblioteca independiente.

```powershell
.venv/Scripts/python.exe analysis/scripts/evaluate_participation_patterns.py --until D
.venv/Scripts/python.exe analysis/scripts/evaluate_participation_patterns.py --candidates r2:2 r2:4
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_evaluate_participation_patterns.py
```

El segundo comando continúa A–D sin repetirlos. Una ejecución posterior verifica _SUCCESS y termina sin entrenar. Para otro experimento usar --output, --charts y --report nuevos. Un fallo queda en state.json con traceback; no se marca validado hasta completar F. Reference/ conserva perfiles, celdas, referencia nacional, broad completa y pendientes; features/ matrices y contrato; models/ los 45 ajustes; resampling/ las candidatas; assignments/ etiquetas completas; metadata/ evidencia y checkpoints. Las referencias y vistas alternativas no deben sumarse entre sí.
