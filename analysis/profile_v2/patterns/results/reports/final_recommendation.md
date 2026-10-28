# Recomendación metodológica V2.1 · 2024

**Esta investigación no respalda sustituir V1 por cuatro a seis perfiles conjuntos. 1 de seis interacciones predefinidas supera todos los controles; las otras se conservan como diagnósticos.** Es evidencia de relaciones multivariables, no de nuevas clases naturales ni de una partición exhaustiva de la ciudadanía.

| Contraste | Media municipal (pp) | Media con LN (pp) | Municipios | Supera controles | Controles no superados |
| --- | --- | --- | --- | --- | --- |
| interaction_18-34_M_U | 1.26 | 1.47 | 1227 | No | practical_and_weights;confirmation |
| interaction_18-34_R_U | 3.82 | 5.30 | 1226 | Sí |  |
| interaction_35-59_M_U | 0.25 | 0.27 | 1262 | No | practical_and_weights;territorial_consistency;confirmation;simultaneous_envelope |
| interaction_35-59_R_U | 0.88 | 2.01 | 1255 | No | practical_and_weights;territorial_consistency;confirmation |
| interaction_60-100_M_U | -0.12 | -0.25 | 1122 | No | practical_and_weights;territorial_consistency;confirmation;simultaneous_envelope |
| interaction_60-100_R_U | -1.32 | -0.83 | 1117 | No | practical_and_weights;confirmation |

## Qué se aprendió

El cruce real sí aporta relaciones que la regla edad/signo V1 no define y que K-Means no destacó: la brecha por sexo cambia entre tipos de sección y edades. En jóvenes, la comparación rural−urbana de esa brecha persiste dentro de municipios comparables. Sin embargo, muchas diferencias nacionales disminuyen o cambian de intensidad al igualar la influencia municipal: contexto, composición y ponderación deben permanecer visibles. Una diferencia pequeña no se vuelve un perfil propio por un gran denominador.

Los cambios de signo no desaparecen por exigir soporte, pero una parte es cercana a cero: 562/2,704 tienen hijo y padre a >2 pp; 101 a >5 pp. Revelan heterogeneidad local, sin validar por sí solos cuatro a seis tipos ni demostrar una paradoja específica.

## Decisión propuesta

**Mantener A, V1 enriquecida, como catálogo de reglas; añadir C como evidencia contextual complementaria.** No adoptar los clusters B como sustitución: la investigación previa mostró dependencia de geometría y peso. C mejora la lectura conjunta mediante contrastes interpretables, pero su cobertura selectiva y el número de relaciones respaldadas no permiten venderlo como seis perfiles. No se inventan cortes o nombres adicionales para completar una cuota de tarjetas. La unión C sólo cubre 22.97 % del LN anual en 1,226 municipios; no ofrece la cobertura de A ni B. El diagnóstico de magnitud de 1/2/3 pp está separado en candidatos. Se rechaza la sustitución con la evidencia probada, no se demuestra la inexistencia de cualquier otra tipología posible.

## Entregables y límites

[Síntesis crítica previa](../../reports/v2_critical_review.md), [protocolo previo](../../reports/protocol.md), [revisión numérica V2](v2_review_metrics.md), [análisis de interacciones](interaction_analysis.md), [2,704 inversiones](sign_reversal_review.md), [candidatos y cobertura](candidate_patterns.md), [alternativas A/B/C](alternative_comparison.md), [nombres](name_proposals.md) y [JSON experimental](../candidates/experimental_patterns.json). Las seis fichas diagnósticas enlazadas en candidatos distinguen aceptación y rechazo.

Se conservan todas las observaciones, conteos, NULL y pendientes. SEXO=2 mantiene 67 celdas y LN=105, con soporte insuficiente para comparaciones H/M; su ausencia histórica no equivale a cero personas. 101+ queda complementario con LN=13,197. La investigación se limita a 2024; no transfiere etiquetas entre años. No hay residencia individual identificada por U/R/M, causalidad, predicción partidista, estrategia asignada o personalización de campañas.

Pendientes antes de cualquier adopción: revisión electoral externa, replicación en otra elección con categorías/cobertura comparables, revisión de sesgo de cuadernillos y NS, robustez a granularidad etaria y validación de utilidad pública. Una investigación adicional puede examinar representación territorial de curvas, pero requiere auditar cobertura de cada coordenada; no se propone entrenar directamente edades exactas escasas ni afinar pesos para fabricar cuatro a seis perfiles.

Se verifica integridad antes/después, fuentes V2/editorial y conciliación de conteos. Los resultados no modifican React, Atlas, V1, estrategias, datos ni resultados anteriores. No se crean commits, push, merges o PR.
