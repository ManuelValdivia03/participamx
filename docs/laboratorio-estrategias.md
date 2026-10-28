# Laboratorio de Estrategias Cívicas

## Objetivo y alcance

Módulo autónomo para explorar escenarios hipotéticos de recursos de seis propuestas informativas e institucionales. No es un servicio del INE, no usa perfiles para asignar intervenciones y no predice voto, abstención ni participación.

## Arquitectura e integración

`src/features/laboratory/` separa catálogo (`strategies.ts`), contratos (`types.ts`), cálculos puros (`calculations.ts`) y componentes de catálogo, constructor, resultados y comparación. `LaboratoryPage` importa `src/styles/laboratory.css` y se exporta nombrada.

Está integrado en `src/app/App.tsx` mediante carga diferida con la ruta `#laboratorio` y la entrada lateral “Laboratorio de Estrategias”. `LaboratoryPage` sigue siendo un módulo independiente y la navegación principal conserva Dashboard, Atlas, Perfiles y Metodología.

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

Campos vacíos, negativos, no finitos, desbordamientos y divisiones por cero no se convierten en resultados válidos. Las unidades planificadas y la capacidad operativa deben ser enteras. Un saldo negativo se presenta como déficit. Con costo cero la capacidad no se reporta como un número artificialmente infinito.

## Comparación y evaluación

Los escenarios se guardan temporalmente en estado React sólo cuando todos los valores son válidos. Se pueden seleccionar dos o más y comparar presupuesto, costos, unidades, capacidades, restricciones y supuestos, además de una gráfica de barras de costos previstos. Si las unidades son diferentes, aparece una advertencia metodológica y no se comparan cantidades como equivalentes.

La sección “¿Cómo evaluaríamos esta propuesta?” distingue resultados matemáticos de supuestos, indicadores que podrían levantarse durante una implementación y resultados reales todavía no disponibles. No se inventan porcentajes de eficacia ni efectos electorales.

## U/R/M y restricciones

El adaptador U/R/M está deliberadamente en estado “Información no disponible”: el módulo no duplica procesamiento del Atlas. Si se integra un contrato validado, debe mostrar año, universo, fuente, denominador, cobertura y limitaciones sólo como contexto descriptivo. U/R/M no identifica residencia individual, no modifica recursos y no decide destinatarios.

No se infieren necesidades individuales, comportamientos ni preferencias; no hay rankings de eficacia, segmentación por edad/sexo/municipio ni causalidad atribuida a datos agregados.

## Pruebas

Ejecutar `npm run test:lab`, `npm run typecheck`, `npm run test:map` y `npm run build`. Las pruebas Vitest cubren el escenario de referencia, déficit, cero, entradas inválidas, desbordamiento, unidades indivisibles, restricciones, formato MXN, catálogo, guardado, comparación, eliminación, indicadores y el estado U/R/M. La revisión manual debe cubrir teclado, modo oscuro y anchos móvil/escritorio.

## Limitaciones conocidas

No hay persistencia, backend, autenticación ni indicadores U/R/M integrados. Los recursos y costos se introducen como supuestos del usuario y no representan presupuesto, capacidad o servicios oficiales.
