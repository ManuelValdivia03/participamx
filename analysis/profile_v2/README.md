# Investigación experimental de perfiles V2

Este directorio conserva una investigación nueva, separada del Atlas, perfiles publicados y estrategias. Los resultados describen **segmentos municipales agregados**, nunca personas individuales. No se publican etiquetas ni se asignan propuestas institucionales.

Se reutiliza el cruce real municipio × banda × sexo × tipo de sección electoral de `participamx_multiyear/elections/YEAR/tables/section_segments.parquet`. No se leen CSV originales ni se cruzan marginales suponiendo independencia. El primer experimento utiliza 2024 y bandas 18–34 / 35–59 / 60–100 para comparar con V1; las bandas no se declaran definitivas. Cinco bandas se auditan sólo como alternativa de cobertura.

Desde la raíz del repositorio, con el entorno existente:

```powershell
.venv_pattern_algorithms/Scripts/python.exe -B -m unittest discover -s analysis/profile_v2/scripts -p test_research_profiles.py
.venv_pattern_algorithms/Scripts/python.exe -B -u analysis/profile_v2/scripts/research_profiles.py
.venv_pattern_algorithms/Scripts/python.exe -B analysis/profile_v2/scripts/write_review.py
```

`research_profiles.py --output NUEVA_RUTA` permite otra ubicación. Una ejecución interrumpida puede reanudarse con la misma ruta: verifica parámetros, huellas de datos/características y checkpoints NPZ antes de reutilizarlos. No se cargan objetos pickle. Un lock exclusivo evita procesos duplicados. No borrar un lock sin comprobar el proceso que lo creó. Parámetros diferentes requieren otra ruta. `write_review.py --output NUEVA_RUTA` genera el informe a partir de esos artefactos, comprueba las pruebas y la integridad antes de marcar `_SUCCESS`.

Dependencias disponibles: Python 3.13, NumPy, Pandas, PyArrow, SciPy, scikit-learn, Matplotlib y threadpoolctl. Las versiones exactas quedan en `results/metadata/environment.json` y `results/metadata/requirements.txt`; no se instalan paquetes. Las librerías se ejecutan con un hilo para reproducibilidad y control de memoria. `MPLCONFIGDIR` queda dentro de este directorio.

- `scripts/`: preparación, ajustes, pruebas y generación de informes.
- `results/reference/`: todas las observaciones originales, referencias previas a soporte y pendientes.
- `results/features/`: matrices nuevas y parámetros propios, sin modificar las anteriores.
- `results/models/` y `assignments/`: 45 ajustes principales, centros, parámetros y etiquetas completas; pendientes con NULL.
- `results/sensitivity/`: objetivos de peso municipal y entrenamientos temporales de cobertura/secciones.
- `results/resampling/`: membresía y cobertura municipal, etiquetas in-bag/OOB.
- `results/diagnostics/`, `comparisons/`, `historical/`: métricas, auditoría, controles V1 e historia agregada sin transferir etiquetas.
- `results/candidates/experimental_profiles.json`: fichas candidatas con estado experimental; no usa el contrato React de perfiles.
- `results/reports/`: auditoría, revisión final y fichas por configuración/K.
- `results/charts/`: gráficos descriptivos de composición, separación, estabilidad e historia.

Se comparan cinco representaciones y K=4/5/6, con tres semillas y 20 inicializaciones nativas por ajuste principal. Dos representaciones reciben sensibilidades y diez submuestras municipales. Son comparaciones acotadas, no una búsqueda exhaustiva de modelos ni prueba de cuatro a seis clases naturales. Las estrategias actuales siguen sin una correspondencia automática con estas etiquetas.
