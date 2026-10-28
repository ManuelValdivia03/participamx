# Protocolo V2.1 fijado antes de calcular los contrastes nuevos

## Pregunta y método

Se investigan relaciones descriptivas, no nuevos clusters. Se usan tasas calculadas desde conteos, estratos nacionales y contrastes emparejados dentro de municipio. No se necesitan árboles ni un nuevo optimizador para observar interacciones en una tabla de 3×2×3 combinaciones. No se altera V1 ni se eligen cortes a partir de un árbol ajustado a sus propias tasas.

Principal: los mismos 31,470 segmentos V2 elegibles H/M 18–100, LN≥100, SV+NV≥100 y filas fuente≥5. Los complementos, tasas NULL y segmentos sin soporte permanecen en referencia. Las referencias nacionales se calculan con todos los conteos originales antes de soporte.

## Familia primaria: seis interacciones

Para cada una de tres bandas y cada contraste T−U (T=R o M), medir:

I = (t_mujeres,T − t_hombres,T) − (t_mujeres,U − t_hombres,U).

Cada bloque municipal requiere sus cuatro celdas elegibles, sin fabricar combinaciones ausentes. La diferencia de diferencias es descriptiva; **no** un estimador causal de diferencias en diferencias. Una interacción positiva significa que la brecha mujeres−hombres es mayor en T que en U; no afirma participación alta en todos sus componentes. Las diferencias se expresan en puntos porcentuales.

Se informa: media con igual peso por bloque municipal; media de contrastes ponderada por el LN total del bloque; y contraste de tasas obtenidas de sumar SV y SV+NV en cada una de sus cuatro celdas. Son tres estimandos distintos: las medias de contrastes son justificadas para estudiar territorios o volumen; no se presentan como tasas nacionales.

Los seis contrastes se mantienen aunque no pasen la revisión. Los contrastes simples por edad/sexo/tipo y las diferencias entre edades son secundarios descriptivos, sin búsqueda de significación entre todos ellos.

## Controles y reglas provisionales de evidencia

Antes de ver resultados se fijan criterios operativos para llamar a una interacción candidata sólida en esta entrega:

- Al menos 200 municipios emparejados, diez entidades y 0.5 % del LN anual dentro de sus cuatro celdas; ningún municipio aporta ≥10 % de ese LN.
- Magnitud ≥2 pp y mismo signo con peso municipal y LN, y contraste agregado del mismo signo. Dos pp es una decisión práctica exploratoria, no un umbral oficial ni de significación.
- Confirmación territorial separada: reparto municipal reproducible 60/40 estratificado por entidad, sin dividir las celdas de un municipio. Ambos grupos deben conservar signo y magnitud ≥2 pp con los dos pesos. Es replicación interna, no predicción de votantes ni validación externa.
- Al menos 60 % de municipios con contraste del mismo signo. En al menos dos tercios de las entidades con cinco municipios emparejados, la media municipal debe tener ese signo. Se cuantifican excepciones.
- Banda simultánea diagnóstica por remuestreo municipal para los seis contrastes × tres estimandos, sin atravesar cero en los dos pesos de medias. Se usa máximo estandarizado centrado de 1,000 réplicas bootstrap de municipios completos; se guarda el procedimiento, todos sus resultados y advertencias. No es un intervalo de confianza de votantes: la base de cuadernillos y sus municipios no son una muestra probabilística de personas.
- Sensibilidades temporales: soporte de celdas≥200, NS<10 % en las cuatro celdas y ≥5 secciones distintas por celda. Se exige al menos cien municipios en cada sensibilidad para evaluar signo, que debe mantenerse con peso municipal y LN. Las magnitudes y pérdidas se muestran; si no hay soporte, el candidato no se declara sólido. No se borran datos ni se cambian umbrales principales.

Las bandas simultáneas y el reparto territorial reducen la libertad de buscar cruces favorables; no garantizan control inferencial formal de errores en una población no muestreada aleatoriamente. Se evita declarar «estadísticamente significativo» por grandes conteos. La familia y los umbrales quedan documentados para futuras réplicas; no se afinarán para obtener cuatro a seis resultados.

## Cambios de signo y cobertura

Verificar por productos cruzados enteros los 2,704 cambios respecto de la **misma referencia banda/sexo**. Separar filas, municipios únicos, LN y D=SV+NV, con denominadores explícitos. Examinar umbrales 50/100/200/500, fuentes 1/5, NS, secciones y zona ±2/5 pp en padre e hijo. Variar soporte exige informar dos cantidades: supervivencia del conjunto original de 2,704 y número de cambios en la nueva población. No interpretar desagregación como cambio temporal ni llamar paradoja a una inversión local sin demostrar sus condiciones.

## Definición de posibles perfiles

Alternativa C = **patrones representativos superpuestos**, no partición. Cada patrón comprende bloques municipales de una banda y dos tipos con ambos sexos. Las cuatro celdas tienen papeles de comparación; no reciben una etiqueta humana. Se guardan membresías, número de patrones por fila y unión única, LN dentro/fuera y municipios cubiertos. Una celda urbana puede participar como referencia en dos patrones; nunca se suman sus volúmenes como cobertura nueva.

Se redactarán tres nombres por patrón que supere estos controles, sólo después de obtener resultados. Si no hay cuatro a seis interacciones suficientemente sólidas, se dirá cuántas hay; las demás seguirán como diagnósticos o resultados descartados. Se compararán A (V1 enriquecida), B (clusters V2 existentes) y C sin favorecer automáticamente la novedad. No se publicará ni integrará nada en React.
