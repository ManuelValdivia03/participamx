# V2.1 · Interacciones electorales de 2024

Se revisa primero la evidencia V2; después se estudian cruces y contrastes emparejados por municipio. No se ajusta clustering nuevo ni se alteran resultados anteriores.

**Resultado:** una de seis interacciones predefinidas supera los controles operativos: la brecha mujeres−hombres de 18–34 años es más amplia en secciones rurales que urbanas del mismo municipio. Esto aporta un patrón descriptivo complementario; no respalda cuatro a seis perfiles conjuntos ni una sustitución exhaustiva de V1.

## Lectura de resultados

- [Síntesis crítica V2, previa al cálculo](reports/v2_critical_review.md) y [protocolo fijado](reports/protocol.md).
- [Recomendación final](results/reports/final_recommendation.md) y [métricas V2 reutilizadas](results/reports/v2_review_metrics.md).
- [Análisis de interacciones](results/reports/interaction_analysis.md), con 18 cruces nacionales, 27 contrastes emparejados, control descriptivo por edad y cambios entre edades.
- [Investigación de los 2,704 cambios de signo](results/reports/sign_reversal_review.md): edad/sexo/tipo/territorio, intensidad, soporte, NS y denominadores separados.
- [Seis pruebas candidatas](results/reports/candidate_patterns.md), con una ficha respaldada y cinco diagnósticos no promovidos; [ficha candidata](results/candidates/cards/interaction_18-34_R_U.md).
- [Comparación A/B/C](results/reports/alternative_comparison.md), [tres nombres del patrón respaldado](results/reports/name_proposals.md) y [JSON experimental](results/candidates/experimental_patterns.json).

C son patrones comparativos que admiten superposición, **no una partición**. Sus miembros son las cuatro celdas de cada bloque municipal; el referente es la brecha por sexo en secciones urbanas del mismo municipio. El JSON conserva también tasas y referencias nacionales de cada componente, sin confundirlas con ese contraste. No se cuentan esas cuatro celdas como cuatro perfiles diferentes.

## Reproducción

Desde la raíz del repositorio, con las dependencias ya instaladas:

```powershell
.venv_pattern_algorithms/Scripts/python.exe -B analysis/profile_v2/patterns/scripts/analyze_patterns.py
.venv_pattern_algorithms/Scripts/python.exe -B -m unittest discover -s analysis/profile_v2/patterns/scripts -p test_analyze_patterns.py -v
```

El programa rechaza destinos existentes. Para repetir usar `--output analysis/profile_v2/patterns/results_rerun`. `--refresh-reports` regenera exclusivamente los documentos, JSON y gráficas de esta entrega verificada, sin repetir contrastes ni remuestreo; comprueba sus artefactos y fuentes antes de actualizarla. Las pruebas de artefactos usan el destino principal. El protocolo no se puede cambiar durante esa regeneración.

Se reutilizan únicamente los Parquet agregados de V2 y 2024. LN=98,330,348, 38,805 filas originales y 7,335 pendientes permanecen en la referencia de la entrega; no se imputan tasas. SEXO=2 y 101+ quedan complementarios. La ausencia histórica de una categoría no se interpreta como cero personas; no se repite investigación histórica.

`resampling/municipal_bootstrap.npz` conserva los índices municipales y sus multiplicidades en 1,000 réplicas compartidas. Las bandas simultáneas son diagnósticos, no intervalos de confianza de votantes; no se presume muestreo probabilístico de los registros. El contraste sintético del remuestreo emparejado se verifica con SciPy. `validation/` conserva división 60/40, cobertura, sensibilidad y consistencia estatal. `candidates/` distingue membresías superpuestas de cobertura única. El JSON usa proporciones, salvo sufijos `_pp`; los campos `sources` de cada patrón se resuelven desde `results/`, y los del catálogo general desde la raíz del repositorio.

El manifiesto registra versiones, protocolo, scripts y hashes. Se verificaron 3,000 archivos previos protegidos, incluyendo V1, V2, revisión editorial, documentación, frontend y datos reutilizados. `_SUCCESS` identifica una generación con fuentes, cálculos y conservación verificados; la batería de pruebas se ejecuta por separado.

No se publica a React, Atlas o Laboratorio, no se asignan estrategias institucionales, no se diseñan campañas ni se predice voto. Los patrones no describen motivaciones individuales; U/R/M es tipo de sección electoral. No se crean commits, push, merges o PR.
