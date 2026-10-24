# Integración multianual preparada para React

Los componentes actuales de `src/` son pantallas de presentación sin un cargador de datos. Este paquete prepara sus contratos y recursos; no modifica React ni publica en `public/data`.

1. Leer `elections_index.json` y poblar el selector usando `elections[].election_year` y `label`.
2. Al cambiar la elección, limpiar municipio/perfil activo y cargar sus recursos mediante las rutas del índice. La identidad siempre incluye elección + entidad + municipio; nunca reutilizar el objeto de otro año sólo porque coincide su código.
3. `profiles.json` contiene seis candidatos por reglas, con su estado; un candidato sin segmentos con soporte mantiene tasas NULL. `national_statistics.json`, `age_statistics.json`, `sex_statistics.json` y `section_statistics.json` alimentan los indicadores propios de la elección.
4. `states.json` y `municipalities.json` describen los territorios observados ese año. Para un municipio, cargar `municipality_segments/{state_code}.json`, `municipality_profiles/{state_code}.json` y, si se necesita edad exacta, `exact_age_segments/{state_code}.json`. Filtrar por ambos códigos textuales. Las rutas se resuelven respecto de `base_path` de la elección.
5. `continuous_indicators.json` usa municipio × sexo; `sex_gaps.json` usa municipio × intervalo. Sus conteos no se suman entre sí ni a los segmentos. Mostrar soporte y cobertura antes de interpretar forma o brechas. No contiene etiquetas R2/arquetipos.
6. Las tasas se almacenan como proporciones. Mostrar 100×tasa como porcentaje y 100×diferencia como puntos porcentuales. Si un valor es NULL, mostrar «No disponible»; no usar `value || 0`, porque cero puede ser un valor válido.
7. Los indicadores de contexto son proporciones de LN por tipo de sección electoral. No equivalen a residencia urbana/rural individual. `distinct_sections` de una ficha es NULL: no se dispone de unión de claves por candidato en los agregados comunes, aunque sí de conteos por segmento e inventarios territoriales.
8. `historical_comparison.json` es una vista de cortes transversales nacionales/estatales y distribuciones. `municipal_history_enabled=false` bloquea comparaciones municipales longitudinales. No hay geometrías en este paquete; deben validarse catálogo/cartografía y correspondencias antes de activar un mapa.

Las advertencias y categorías disponibles se leen de `metadata.json`, no se suponen desde 2024. SEXO=2 no existe como categoría registrada en las elecciones anteriores: no dibujar ceros históricos. Edades >100 siguen en los archivos; 18–100 es la vista principal recomendada y el núcleo de las seis reglas, no una corrección de edad.

Los esquemas son JSON Schema 2020-12. Se incluye un validador local del subconjunto declarado y pruebas semánticas. Deben añadirse validaciones con un motor estándar al integrar si se necesita ampliar el lenguaje. No es un contrato idéntico al v1 fijado a 2024: v2 conserva conceptos/identificadores y añade el año como dimensión obligatoria.
