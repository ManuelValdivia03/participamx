# Contraste numérico de la revisión crítica V2

Se reutilizan modelos y fichas existentes; cero ajustes nuevos. Las fracciones siguientes son contribuciones a la separación entre centroides en la geometría elegida, no importancia causal.

| config | k | participation_separation_share | age_separation_share | sex_separation_share | section_separation_share | silhouette |
| --- | --- | --- | --- | --- | --- | --- |
| absolute_50 | 4 | 0.6661 | 0.0456 | 0.2881 | 0.0002 | 0.2387 |
| absolute_50 | 5 | 0.6752 | 0.0653 | 0.2591 | 0.0004 | 0.2404 |
| absolute_50 | 6 | 0.6346 | 0.1129 | 0.2521 | 0.0005 | 0.2408 |
| age_sex_50 | 4 | 0.7772 | 0.0100 | 0.2111 | 0.0016 | 0.2118 |
| age_sex_50 | 5 | 0.7197 | 0.0093 | 0.2695 | 0.0014 | 0.2104 |
| age_sex_50 | 6 | 0.7485 | 0.0086 | 0.2417 | 0.0013 | 0.1906 |
| age_sex_section_50 | 4 | 0.7814 | 0.0065 | 0.2098 | 0.0023 | 0.2145 |
| age_sex_section_50 | 5 | 0.7192 | 0.0072 | 0.2717 | 0.0019 | 0.2131 |
| age_sex_section_50 | 6 | 0.7466 | 0.0067 | 0.2449 | 0.0018 | 0.1919 |
| age_sex_75 | 4 | 0.9962 | 0.0029 | 0.0005 | 0.0004 | 0.2324 |
| age_sex_75 | 5 | 0.9452 | 0.0028 | 0.0516 | 0.0004 | 0.2255 |
| age_sex_75 | 6 | 0.9085 | 0.0028 | 0.0884 | 0.0004 | 0.2268 |
| relative_only | 4 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.5247 |
| relative_only | 5 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.5194 |
| relative_only | 6 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.5186 |

Comparar Silhouette entre geometrías no selecciona una representación universal. Las categorías fueron entradas al ajuste. Que sexo separe dos clases centrales no valida una interacción contextual. Fuentes copiadas sin modificar: model_metrics.csv, seed_stability.csv, municipal_stability.csv y sensitivity_metrics.csv, con sus huellas originales verificadas.

[Síntesis crítica previa](../../reports/v2_critical_review.md), [geometría V2](../../../reports/methodology.md) y [revisión editorial previa](../../../editorial/results/reports/editorial_recommendation.md).