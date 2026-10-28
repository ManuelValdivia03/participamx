# Síntesis crítica previa a la investigación V2.1

Esta síntesis se redacta antes de calcular nuevos contrastes. Se revisaron auditoría, contrato, geometría, métricas K=4/5/6, estabilidad, sensibilidades, fichas experimentales y revisión editorial V2. No se inicia un nuevo clustering: los agregados existentes permiten investigar primero relaciones que los centroides anteriores no resumían.

## Qué descubrió V2

V2 recuperó el cruce real municipio × banda × sexo × tipo de sección electoral en 2024, sin reconstruirlo desde marginales. Hay 38,805 celdas originales; 31,470 cumplen los criterios exploratorios de soporte, con 2,392 municipios y LN=97,999,677 (99.6637 % del nominal anual reportado). Los pendientes permanecen en referencia. Los 2,704 hijos elegibles con signo contrario a su padre V1 son heterogeneidad observable dentro del mismo municipio/banda/sexo; no un porcentaje de personas ni, por sí solos, una paradoja de Simpson.

V1 clasifica por reglas de edad/signo; V2 divide sus segmentos por tipo de sección y aplica K-Means. Ni las bandas de agregación, ni la unidad estadística, ni el algoritmo son conceptos intercambiables. Las seis fichas V1 no constituyen seis clases naturales demostradas. La edición posterior mejoró sus descripciones, sin cambiar su definición.

## Seis respuestas críticas

1. **Separación por edad, sexo o participación.** Las categorías eran coordenadas de distancia, además del indicador electoral. Reproducir una categoría introducida en la distancia no demuestra una interacción electoral ni un grupo nuevo. En K4 relativo dos clases centrales reproducían sobre todo H/M; los extremos distinguían niveles relativos.
2. **Dominio geométrico.** El diseño principal asignó 50 % de la varianza de entrada a participación y 50 % a los tres bloques categóricos, con pesos iguales entre bloques. Eso no obliga a cada bloque a separar centroides. Las contribuciones observadas de U/R/M fueron muy pequeñas en las soluciones relativas. Se reutilizarán las métricas exactas, sin reajustar modelos. Estabilidad ante semillas o remuestras bajo geometría fija tampoco implica estabilidad ante cambiar pesos o representación; K5 mostró sensibilidad importante al peso municipal.
3. **Representación de U/R/M.** One-hot completo, centrado y dividido por una escala RMS común del bloque; sin orden numérico U/R/M ni distancia geográfica. Todas las diferencias categóricas del mismo bloque tenían la misma distancia. LN, NS y territorio eran metadatos. U/R/M es tipo de sección electoral, no localidad o residencia individual.
4. **Peso del cruce conjunto.** Cada celda real era una observación, con peso principal uno; un municipio con más tipos/bandas/sexos elegibles aportaba más masa. El control municipal corrigió esa suma, sin cambiar escalas. El cruce no tenía una variable de interacción explícita: la suma de distancias de bloques no representa una comparación de brechas dentro del mismo municipio. One-hot conjunto tampoco garantizaría encontrar patrones sustantivos.
5. **Información resumida.** Los datos no perdieron el cruce. Lo que ocultaban los resúmenes de cluster eran contrastes emparejados, distribución territorial de sus signos, respuestas distintas de hombres/mujeres entre tipos y cambios locales detrás de medias nacionales. Restar la referencia banda/sexo/tipo además descuenta precisamente parte del contraste contextual que ahora interesa estudiar. Las bandas siguen ocultando edad exacta; no se cambia aquí ese soporte.
6. **Hallazgos que merecen examinarse.** Las referencias nacionales sugieren que el contraste rural−urbano cambia con edad y sexo; sus medias no prueban que se mantenga dentro de municipios comparables. Los cambios de signo V1 también pueden ser pequeños, próximos a cero o dependientes de composición. V2.1 contrastará esas posibilidades, sin nombrar perfiles antes de medirlas.

## Fuentes exactas revisadas

- [Auditoría V2](../../results/reports/variable_audit.md): cobertura, categorías, referencias y pendientes.
- [Metodología](../../reports/methodology.md), [contrato](../../results/metadata/feature_contract.json) y [parámetros de bloques](../../results/metadata/block_parameters.json).
- [Métricas de modelos](../../results/diagnostics/model_metrics.csv), [semillas](../../results/diagnostics/seed_stability.csv), [sensibilidades](../../results/diagnostics/sensitivity_metrics.csv) y [estabilidad municipal](../../results/diagnostics/municipal_stability.csv).
- [Fichas K4 conjunto](../../results/reports/candidates/age_sex_section_50_k4.md), fichas K5/K6 del mismo directorio y [recomendación V2](../../results/reports/final_recommendation.md).
- [Revisión editorial](../../editorial/results/reports/editorial_recommendation.md): rasgos V1, 36 cruces internos y cambios locales; no una nueva clasificación.

Los resultados V2 y la investigación editorial se mantienen intactos. Esta revisión no interpreta motivación, abstención de NS, preferencias políticas ni eficacia de estrategias.
