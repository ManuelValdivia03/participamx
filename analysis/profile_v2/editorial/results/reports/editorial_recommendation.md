# Recomendación editorial provisional · seis fichas V1 de 2024

Se recomienda conservar los identificadores y reglas originales y probar los siguientes títulos junto a su subtítulo. La revisión cambia la comunicación, no la pertenencia: son resúmenes por reglas de edad/signo, no seis clusters naturales, perfiles individuales o etiquetas morales.

| ID interno | Título propuesto | Rasgo comprobado | Ficha |
| --- | --- | --- | --- |
| young_favorable | Participación joven con mayor diferencia positiva | Mayor diferencia positiva agregada de las seis fichas. | [Ver ficha](cards/young_favorable.md) |
| young_unfavorable | Participación joven en el nivel más bajo | Menor tasa absoluta entre las seis fichas. | [Ver ficha](cards/young_unfavorable.md) |
| adult_favorable | Participación adulta con mayor presencia municipal | Máximo número de municipios representados entre las seis fichas. | [Ver ficha](cards/adult_favorable.md) |
| adult_unfavorable | Participación adulta con mayor volumen nominal | Mayor LN reportado de las seis fichas. | [Ver ficha](cards/adult_unfavorable.md) |
| older_favorable | Participación de mayores en el nivel más alto | Mayor tasa absoluta entre las seis fichas. | [Ver ficha](cards/older_favorable.md) |
| older_unfavorable | Participación de mayores con mayor distancia negativa | Mayor déficit relativo agregado entre las seis fichas. | [Ver ficha](cards/older_unfavorable.md) |

## Qué diferencia y qué no diferencia

Los títulos recomendados alternan diferencia relativa positiva, tasa absoluta mínima, presencia municipal, volumen nominal, tasa máxima y diferencia relativa negativa. Estos ejes son distintos: volumen no equivale a presencia, ni tasa absoluta a distancia respecto de referencia. Los superlativos requieren mostrar «entre las seis fichas de 2024» en ayuda o contexto. No implican que todas las edades o municipios del país tengan ese rasgo.

La diferenciación adicional es limitada. Todos tienen mayoría nominal asociada a secciones urbanas (66.31–73.87 %), ambos sexos y variación interna. El 73.87 % urbano adulto negativo y el 73.84 % mayor positivo difieren apenas 0.03 pp: esa proximidad no justifica nombres de tipos urbanos distintos. La semejanza de composiciones de las dos fichas jóvenes tampoco permite atribuir sus tasas a ruralidad. En mayores negativos la diferencia relativa entre sexos es sólo 0.03 pp: no se propone una gran división por sexo. Las alternativas contextuales son válidas dentro de cada ficha, pero a menudo describen un subconjunto o un rasgo compartido; por eso no desplazan al título principal.

## Evidencia conjunta y variación interna

| profile_id | parent_segments | joint_cells | eligible_cells | eligible_flip_cells | eligible_flip_fraction_pct | eligible_flip_LN |
| --- | --- | --- | --- | --- | --- | --- |
| young_favorable | 2688 | 6442 | 6030 | 446 | 7.40 | 954821 |
| young_unfavorable | 2036 | 4784 | 4551 | 468 | 10.28 | 1247061 |
| adult_favorable | 3015 | 7081 | 6778 | 491 | 7.24 | 996893 |
| adult_unfavorable | 1767 | 4215 | 4055 | 468 | 11.54 | 1662772 |
| older_favorable | 2606 | 6074 | 5406 | 444 | 8.21 | 402323 |
| older_unfavorable | 2078 | 5113 | 4650 | 387 | 8.32 | 424457 |

Los seis padres V1 incluyen 14,190 segmentos, LN=98,203,780 y 2,402 municipios. Sus 33,709 hijos U/R/M presentes se mantienen completos, sin exigir soporte al hijo para reconstruir la ficha. El análisis de cambios con soporte usa 31,470 hijos, LN=97,999,677 y 2,392 municipios. Los 2,704 cambios de signo corresponden al 8.59 % de esos hijos y LN=5,688,327, el 5.80 % de su LN. No son municipios únicos, cambios temporales ni nuevos perfiles; pueden corresponder a diferencias próximas a cero. Cada ficha muestra cuántos cambios tienen esa cautela, NS alto o pocas secciones, con bases y advertencias separadas.

El signo se comprueba frente a la referencia **banda/sexo**, igual en padre e hijo. La referencia nacional adicional banda/sexo/tipo de V2 se conserva en la traza, pero no sustituye la base V1 ni se usa para justificar estos nombres. Cambiar la referencia cambiaría la pregunta. Ninguna media por sexo/tipo de estas fichas invierte el signo agregado del padre; las inversiones son locales y no se deben ocultar detrás de esas medias.

## Uso editorial propuesto

Mostrar título, subtítulo con edad/tasa/referencia/Δ y condición experimental. Acompañar con tres hallazgos, el cruce real sexo×tipo de sección electoral y una advertencia de variación. Las descripciones principales contienen 40–70 palabras; los títulos tienen 4–9. Para tarjetas pequeñas, permitir salto de línea: los nombres no se validaron aún visualmente en React o PDF. El JSON es un contrato experimental independiente, no un reemplazo directo del JSON publicado ni una aprobación de integración.

No se proponen estrategias, mensajes persuasivos ni campañas diferenciadas por conducta o demografía. Los cruces informan patrones agregados y no necesidades, preferencias partidistas, causas de abstención o eficacia institucional.

## Fuentes y verificación

[Catálogo exacto de fuentes y campos](source_catalog.md), [18 propuestas justificadas](name_proposals.md), [comparación editorial](name_comparison.md), [tabla CSV](../name_comparison.csv), [JSON experimental](../experimental_profile_names_2024.json). Se cotejan perfiles publicados, agregados originales y cruces V2; 42 conciliaciones perfil/campo dan diferencia cero. Los cálculos sólo leen agregados; no entrenan modelos ni cambian umbrales. La integridad de las fuentes y de los archivos previos protegidos se comprueba antes y después; los artefactos V2 se validan con su manifiesto original.

Pendientes antes de adoptar: revisión del lenguaje por el equipo y personal electoral, prueba de comprensión con usuarios y de legibilidad en tarjetas/PDF, decisión explícita sobre cómo comunicar la zona cercana a la referencia y las inversiones locales, y revisión del futuro contrato de integración. Esta entrega no demuestra utilidad de intervención ni autoriza inferencias individuales; no modifica React, Atlas, estrategias o V1.
