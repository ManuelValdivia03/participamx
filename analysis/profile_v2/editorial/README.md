# Revisión editorial experimental de las seis fichas V1

Esta entrega añade nombres e interpretaciones al cruce real de edad, sexo, tipo de sección electoral y participación de 2024. Conserva IDs y reglas V1; no renombra clusters aprendidos ni publica cambios en React, Atlas o estrategias.

Punto de entrada: [recomendación editorial](results/reports/editorial_recommendation.md). Incluye [18 propuestas](results/reports/name_proposals.md), [tabla comparativa](results/reports/name_comparison.md), seis fichas en `results/reports/cards/`, evidencia y [JSON experimental](results/experimental_profile_names_2024.json). Las tasas del JSON son proporciones, salvo campos con sufijo `_pp`; las tablas de fichas muestran tasas en porcentaje.

Reproducir desde la raíz del repositorio:

```powershell
.venv_pattern_algorithms/Scripts/python.exe -B analysis/profile_v2/editorial/scripts/build_profile_naming.py
.venv_pattern_algorithms/Scripts/python.exe -B -m unittest discover -s analysis/profile_v2/editorial/scripts -p test_build_profile_naming.py -v
```

El programa rechaza destinos existentes. Para repetir, usar `--output analysis/profile_v2/editorial/results_rerun`. Las pruebas de entrega utilizan el destino principal; las pruebas matemáticas son independientes. No se instalan paquetes ni se entrenan modelos; se reutiliza Pandas/NumPy/PyArrow del entorno existente.

`evidence/child_trace.parquet` conserva todos los hijos de los padres V1 con trazabilidad; no es una nueva fuente publicada. `eligible_sign_reversals.parquet` separa el diagnóstico de hijos con soporte, sin excluir a los demás del resumen V1. Se preservan NULL y conteos; no se suman municipios o secciones entre fichas. Las otras observaciones, incluidas 101+ y SEXO=2, permanecen en las fuentes anteriores intactas.

El catálogo de fuentes documenta archivos, campos y filtros. El manifiesto verifica los resultados V2 previos y huellas antes/después de las fuentes multianuales, V2 anterior, documentación de perfiles, `src/` y `public/`. `_SUCCESS` sólo aparece al terminar las conciliaciones, la validación del contenido y la comprobación de integridad. Las pruebas automatizadas se ejecutan por separado y comprueban además los artefactos generados.
