# Fichas y comparación de perfiles

Esta entrega implementa únicamente la interfaz web. No limpia los ZIP, calcula indicadores ni define clusters.

## Funciones

- Catálogo de fichas y detalle con características, indicadores, acciones y limitaciones.
- Selección de dos a tres perfiles para una tabla comparativa, con quitar y vaciar selección.
- Presentación de valores faltantes como “Sin información”. El cero sigue siendo un valor numérico válido.
- Diseño adaptable a móvil; la tabla permite desplazamiento horizontal y acceso por teclado.
- La ficha traslada el foco a su título al abrir y lo devuelve al botón de origen al cerrar.
- Avisos visibles de datos ficticios en catálogo, fichas y comparación.

## Entrega esperada del equipo de análisis

El contrato TypeScript `ProfileDataset` está en `src/features/profiles/types.ts`. `Profiles` acepta una propiedad opcional `dataset` con este formato; actualmente usa `demoProfiles` como demostración local.

Por conjunto: `mode` (`demo` o `real`), `year`, `source`, `updatedAt`, `participationDefinition` y `profiles`. La definición debe explicar el universo y denominador que el equipo usó para calcular la participación. Todos los perfiles comparados pertenecen al año del conjunto.

Por perfil: `id` estable y único, `name`, `summary`, `description`, indicadores numéricos `participation` y `coverage` (porcentajes 0–100), `medianAge`, `municipalityCount`, y listas `characteristics`, `strategies`, `limitations`.

Los cuatro indicadores numéricos admiten `null`. No enviar ceros como sustituto de faltantes. Las listas sin información pueden estar vacías. El frontend formatea los valores entregados; no calcula tasas, medias, cobertura ni asociaciones territoriales.

Los ejemplos usan nombres A–D y cifras ficticias, separadas en `demoProfiles.ts`. No anticipan el número de perfiles, sus características o las estrategias que resultarán del análisis. Sustituir el conjunto completo al recibir resultados reales y cambiar `mode` a `real`; nunca retirar las etiquetas demo conservando valores de prueba.

El contrato es una propuesta de integración que debe acordarse con el equipo de análisis. La descarga desde un backend, filtros por año, exportación de reportes y publicación de resultados reales no forman parte de esta entrega.
