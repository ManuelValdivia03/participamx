# Laboratorio de Estrategias Cívicas

## Objetivo y alcance

Módulo autónomo para explorar escenarios hipotéticos de recursos de seis propuestas informativas e institucionales. No es un servicio del INE, no usa perfiles para asignar intervenciones y no predice voto, abstención ni participación.

## Arquitectura e integración

`src/features/laboratory/` separa catálogo (`strategies.ts`), contratos (`types.ts`), cálculos puros (`calculations.ts`) y componentes de catálogo, constructor, resultados y comparación. `LaboratoryPage` importa `src/styles/laboratory.css` y se exporta nombrada.

Está integrado en `src/app/App.tsx` mediante carga diferida con la ruta `#laboratorio` y la entrada lateral “Laboratorio de Estrategias”. `LaboratoryPage` sigue siendo un módulo independiente y la navegación principal conserva Dashboard, Atlas, Perfiles y Metodología.

## Catálogo y procedencia

Las seis propuestas —Guía de pasos; Localizador de fuentes; Registro de consistencia; Mesa de dudas; Biblioteca de formatos; Directorio de orientación— proceden de `docs/perfiles/propuestas_institucionales.md`. Son propuestas pendientes de validación, de acceso universal y no partidistas. El catálogo conserva propósito, tipo, recursos, contribución hipotética, indicadores y límites documentados.

Cada tarjeta conserva su contenido y selección e incorpora **Ver detalles**. `StrategyDetailModal.tsx` presenta trece apartados con índice desplegable, desplazamiento interno, aislamiento del fondo, navegación por teclado, cierre con Escape y devolución del foco al botón de origen. `strategyDetails.ts` lee directamente el desarrollo institucional, la síntesis del equipo y las cifras de `docs/perfiles/perfiles_2024.json`; no mantiene una segunda copia editorial ni cambia los datos. La relación perfil–estrategia se conserva como contexto hipotético de 2024, sin asignación exclusiva de servicios.

## Escenarios y fórmulas

Variables editables: nombre, estrategia, presupuesto hipotético MXN, costo unitario supuesto, unidades planificadas, capacidad operativa opcional y supuestos. El constructor las organiza en identificación, recursos, planificación y supuestos; explica cada término con ejemplos, distingue valores obligatorios y opcionales y muestra errores junto al campo. Cada estrategia conserva una unidad propia (por ejemplo, guías revisadas, versiones auditadas o servicios confirmados), nunca una medida universal de personas.

- Costo previsto = costo unitario × unidades planificadas.
- Presupuesto utilizado = costo previsto / presupuesto × 100, sólo si el presupuesto es mayor que cero.
- Presupuesto restante = presupuesto − costo previsto.
- Capacidad teórica = presupuesto / costo unitario, sólo si el costo es mayor que cero.
- Capacidad factible = mínimo(capacidad teórica, capacidad operativa), sólo cuando hay restricción cuantificada.
- Diferencia de recursos = capacidad disponible − unidades planificadas.

Campos vacíos, negativos, no finitos, desbordamientos y divisiones por cero no se convierten en resultados válidos. Las unidades planificadas y la capacidad operativa deben ser enteras. Un saldo negativo se presenta como déficit. Con costo cero la capacidad no se reporta como un número artificialmente infinito.

## Comparación y evaluación

Los escenarios se guardan temporalmente en estado React sólo cuando todos los valores son válidos. Se muestran como tarjetas y se pueden seleccionar dos alternativas para comparar presupuesto, costos, saldo, unidades, capacidades, restricciones y supuestos, además de barras de costos y capacidad factible. Si las unidades son diferentes, aparece una advertencia metodológica y no se comparan cantidades como equivalentes.

La sección “¿Cómo evaluaríamos esta propuesta?” distingue resultados matemáticos de supuestos, indicadores que podrían levantarse durante una implementación y resultados reales todavía no disponibles. No se inventan porcentajes de eficacia ni efectos electorales.

El análisis muestra un diagnóstico separado para presupuesto y capacidad operativa, siete indicadores principales y comparaciones visuales de presupuesto utilizado y actividades planificadas frente a la capacidad disponible. Cuando faltan datos o existe una restricción, se comunica como información incompleta o insuficiente; no se presenta el escenario como viable.

`diagnosis.ts` comparte los mensajes entre pantalla y documentos. Si el costo supera el presupuesto, informa el déficit y las actividades completas financiables. La capacidad operativa se evalúa de manera independiente. Se permite guardar y exportar escenarios con déficit, incluso cuando el costo unitario supera todo el presupuesto; las fórmulas y las condiciones de validez se conservan.

## Exportación de reportes

El laboratorio genera PDF y PNG directamente en el navegador, sin servidor ni envío de datos a servicios externos. La exportación individual sólo se habilita con un escenario válido y usa la copia propia del escenario guardado; la comparación sólo se habilita cuando hay exactamente dos escenarios válidos seleccionados. También se exporta el detalle completo de las seis estrategias, independientemente del escenario.

La exportación está separada en `src/features/laboratory/export/`: preparación de datos, plano de dibujo paginado, renderizado con jsPDF o canvas, descarga y validación. El mismo plano asegura contenido equivalente en PDF y PNG. El diseño sigue la identidad de las fichas de perfiles: papel claro, franja morada, indicadores en recuadros lilas, jerarquía de títulos y pies numerados. El PDF conserva texto seleccionable y gráficas vectoriales. El PNG tiene 1600 píxeles de ancho; los documentos muy largos se dividen en imágenes numeradas para limitar el tamaño del canvas.

Los escenarios y comparaciones incluyen todos los indicadores, diagnóstico independiente de presupuesto y operación, gráficas con escala compartida y barras cero vacías, supuestos, indicadores todavía no evaluados, fuentes y limitaciones. Las unidades incompatibles se advierten y no se comparan como equivalentes. Las estrategias conservan actividades, recursos, métodos de medición, evidencia requerida y validaciones pendientes. Los botones de descarga distinguen estados habilitado/deshabilitado, hover y foco en ambos temas. Los documentos no agregan predicciones electorales ni resultados de implementación.

## Guía y uso asistido

El botón **¿Cómo funciona?** abre un recorrido contextual de trece pasos: destaca el elemento explicado, desplaza la vista hacia él y coloca una tarjeta cercana con flecha, progreso, botones Anterior/Siguiente/Salir, foco de teclado y salida con Escape. Explica qué es, para qué sirve y cómo usar el catálogo, campos, indicadores, gráficas, guardado, comparación y evaluación. Mantiene visible el resto de la interfaz, se adapta a móvil y ofrece un fallback si un objetivo no está disponible. Puede abrirse nuevamente en cualquier momento.

**Probar con un ejemplo** carga una guía ficticia con $10,000, $200 por unidad, 30 actividades y capacidad operativa de 40. El ejemplo es modificable y se advierte antes de reemplazar valores ya introducidos. Las ayudas visibles junto a cada campo y resultado explican términos y ejemplos sin depender de punteros o tooltips.

## U/R/M y restricciones

Se retiró únicamente el apartado incompleto “Tipos de sección electoral” del Laboratorio. Los datos U/R/M del Atlas y los perfiles se conservan intactos. U/R/M no identifica residencia individual, no modifica recursos y no decide destinatarios.

No se infieren necesidades individuales, comportamientos ni preferencias; no hay rankings de eficacia, segmentación por edad/sexo/municipio ni causalidad atribuida a datos agregados.

## Pruebas

Ejecutar `npm run typecheck`, `npm run test:lab` y `npm run build`. En PowerShell con scripts deshabilitados puede usarse `npm.cmd`. Las pruebas Vitest cubren cálculos existentes, déficit, cero, entradas inválidas, restricciones, catálogo, guardado, comparación, eliminación, navegación, tour y ejemplo. Se verifican además las seis asociaciones documentales y sus cifras, el contenido completo de los PDF, teclado y foco del modal, fallos de exportación, igualdad de contenido PNG/PDF, barras, límites de página, ausencia de superposiciones y conservación de textos extensos.

Después del build, `node scripts/check-laboratory-ui.mjs` verifica en Chrome local los modos claro/oscuro, contraste de botones de al menos 4.5:1, foco y Escape, modal de 390 px y descargas reales de PDF/PNG de seis estrategias, un escenario y una comparación. Requiere Chrome instalado (o `CHROME_PATH`). Guarda capturas, descargas y resultados en `node_modules/.cache/laboratory-ui/`, sin publicar ni desplegar.

## Limitaciones conocidas

No hay persistencia, backend, autenticación ni indicadores U/R/M integrados. Los recursos y costos se introducen como supuestos del usuario y no representan presupuesto, capacidad o servicios oficiales.
