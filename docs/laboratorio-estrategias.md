# Laboratorio de Estrategias Cívicas

## Objetivo y alcance

Módulo autónomo para explorar escenarios hipotéticos de recursos de seis propuestas informativas e institucionales. No es un servicio del INE, no usa perfiles para asignar intervenciones y no predice voto, abstención ni participación.

## Arquitectura e integración

`src/features/laboratory/` separa catálogo (`strategies.ts`), contratos (`types.ts`), cálculos puros (`calculations.ts`) y componentes de catálogo, constructor, resultados y comparación. `LaboratoryPage` importa `src/styles/laboratory.css` y se exporta nombrada.

Para integrarlo después en `src/app/App.tsx`: importar `LaboratoryPage`, añadirlo a `pages` con un identificador y etiqueta, y elegir un icono ya disponible. No se debe modificar el módulo para esa integración.

## Catálogo y procedencia

Las seis propuestas —Guía de pasos; Localizador de fuentes; Registro de consistencia; Mesa de dudas; Biblioteca de formatos; Directorio de orientación— proceden de `docs/perfiles/propuestas_institucionales.md`. Son propuestas pendientes de validación, de acceso universal y no partidistas. El catálogo conserva propósito, tipo, recursos, contribución hipotética, indicadores y límites documentados.

## Escenarios y fórmulas

Variables editables: nombre, estrategia, presupuesto hipotético MXN, costo unitario supuesto, unidades planificadas, capacidad operativa opcional y supuestos. Cada estrategia conserva una unidad propia (por ejemplo, guías revisadas, versiones auditadas o servicios confirmados), nunca una medida universal de personas.

- Costo previsto = costo unitario × unidades planificadas.
- Presupuesto utilizado = costo previsto / presupuesto × 100, sólo si el presupuesto es mayor que cero.
- Presupuesto restante = presupuesto − costo previsto.
- Capacidad teórica = presupuesto / costo unitario, sólo si el costo es mayor que cero.
- Capacidad factible = mínimo(capacidad teórica, capacidad operativa), sólo cuando hay restricción cuantificada.
- Diferencia de recursos = capacidad disponible − unidades planificadas.

Campos vacíos, negativos, no finitos y divisiones por cero no se convierten en resultados válidos. Un saldo negativo se presenta como déficit. Con costo cero la capacidad no se reporta como un número artificialmente infinito.

## Comparación y evaluación

Los escenarios se guardan temporalmente en estado React. Se pueden seleccionar dos o más y comparar presupuesto, costos, unidades, capacidades, restricciones y supuestos. Si las unidades son diferentes, aparece una advertencia metodológica y no se comparan cantidades como equivalentes.

La sección “¿Cómo evaluaríamos esta propuesta?” distingue resultados matemáticos de supuestos, indicadores que podrían levantarse durante una implementación y resultados reales todavía no disponibles. No se inventan porcentajes de eficacia ni efectos electorales.

## U/R/M y restricciones

El adaptador U/R/M está deliberadamente en estado “Información no disponible”: el módulo no duplica procesamiento del Atlas. Si se integra un contrato validado, debe mostrar año, universo, fuente, denominador, cobertura y limitaciones sólo como contexto descriptivo. U/R/M no identifica residencia individual, no modifica recursos y no decide destinatarios.

No se infieren necesidades individuales, comportamientos ni preferencias; no hay rankings de eficacia, segmentación por edad/sexo/municipio ni causalidad atribuida a datos agregados.

## Pruebas

Ejecutar `npm run typecheck`, `npm run test:map` y `npm run build`. La revisión manual debe cubrir entradas vacías/negativas, costo cero, déficit, restricción operativa, comparación con unidades distintas, estado U/R/M, teclado, modo oscuro y ancho móvil. El repositorio no tiene un ejecutor de pruebas unitarias TypeScript configurado; los cálculos están aislados en `calculations.ts` para incorporar el mecanismo acordado sin dependencias adicionales.

## Limitaciones conocidas

No hay persistencia, backend, autenticación ni indicadores U/R/M integrados. Los recursos y costos se introducen como supuestos del usuario y no representan presupuesto, capacidad o servicios oficiales.
