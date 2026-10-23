# Menú principal: dashboard de demostración

La vista presenta indicadores y gráficas entregados como agregados. No lee los ZIP, calcula tasas, limpia datos ni define perfiles.

## Funciones

- Filtros por territorio y año, restablecimiento de la selección y contexto visible.
- Indicadores de participación, cobertura, lista nominal y cantidad de perfiles.
- Serie temporal SVG con escala fija de 0–100%, año seleccionado, botones por año y tabla textual alternativa. Los faltantes cortan la línea y no aparecen como cero.
- Distribución horizontal por perfiles con porcentajes y definición del universo visible.
- Estados de carga, error con reintento, falta de selección disponible y valores parcialmente informados.
- Avisos de demostración, fuente y definiciones junto a las gráficas; colores compatibles con modo claro y oscuro.

## Datos de demostración

`demoDashboard.ts` contiene fixtures ficticios para seis años (2009, 2012, 2015, 2018, 2021 y 2024) y cuatro territorios (México, Aguascalientes, Ciudad de México y Veracruz). Son ejemplos para validar controles, no resultados ni estimaciones.

Ciudad de México 2012 omite intencionalmente el corte para probar la falta de resultados. Veracruz 2021 omite cobertura y distribución para probar datos parciales. Estas ausencias no describen la cobertura de los ZIP reales.

## Contrato de integración propuesto

`DashboardDataset` en `types.ts` define:

- `mode`: `demo` o `real`.
- `source`, `updatedAt`: fuente y fecha de actualización, sin inventar una fecha si no existe.
- `participationDefinition`: universo, denominador y tratamiento de faltantes que el equipo de análisis haya aplicado.
- `distributionDefinition`: unidad de distribución (por ejemplo, municipios), universo y significado de los porcentajes.
- `years`, `territories`: opciones disponibles con códigos estables; el prototipo usa `MX` para la vista nacional y claves estatales de dos dígitos.
- `snapshots`: un registro único por `year + territoryCode`, con `metrics`, `distribution` y `notes`.

`metrics` contiene `participation` y `coverage` como porcentajes 0–100, `nominalList` y `profileCount` como cantidades no negativas. Todos admiten `null` (no disponible). El cero numérico se conserva. `distribution` contiene `id`, `name` y `percentage` por perfil; lista vacía significa distribución no entregada. Sus identificadores deben acordarse con la sección Perfiles.

El frontend selecciona el registro y formatea las cifras; no agrega municipios, calcula porcentajes ni infiere perfiles a partir de otros valores. Los cambios de coordenadas para dibujar la gráfica son solo presentación.

## Conexión futura

`Dashboard` admite `loadDataset(signal: AbortSignal): Promise<DashboardDataset>`. Por defecto carga los fixtures mediante importación diferida. Un adaptador futuro puede descargar y validar el JSON real usando ese mismo contrato; las solicitudes se cancelan al desmontar la pantalla y un rechazo muestra Reintentar carga.

Los filtros contienen solo las opciones de la entrega y no realizan solicitudes por cada cambio. Si un corte no está presente, se muestra Sin información. Antes de cambiar a `mode: real`, sustituir todo el conjunto, validar los agregados con el equipo de análisis y retirar los fixtures de la ruta de datos reales.
