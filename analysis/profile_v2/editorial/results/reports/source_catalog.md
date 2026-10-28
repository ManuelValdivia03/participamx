# Fuentes, campos y reglas de cálculo

ID significa el profile_id técnico original. Las rutas de repositorio se resuelven desde su raíz; las rutas this_output desde esta entrega. Las huellas y la conciliación están en metadata/run_manifest.json y evidence/parent_reconciliation.csv.

## v1-profiles

**Archivo:** [data/processed/participamx_multiyear/elections/2024/profiles.json](../../../../../data/processed/participamx_multiyear/elections/2024/profiles.json).

**Filtro:** data[profile_id=ID].

**Campos:** `segments`, `municipalities`, `LN`, `participation_observed`, `matched_peer_reference`, `participation_delta`, `women_segment_fraction`, `women_nominal_fraction`, `near_reference_fraction`, `nominal_share_U`, `nominal_share_R`, `nominal_share_M`.

## v1-segments

**Archivo:** [data/processed/participamx_multiyear/elections/2024/tables/segments.parquet](../../../../../data/processed/participamx_multiyear/elections/2024/tables/segments.parquet).

**Filtro:** candidate_id=ID; todos sus padres con soporte V1.

**Campos:** `row_id`, `EDOCVE`, `MPIOCVE`, `age_band`, `SEXO`, `LN`, `SV`, `NV`, `NS`, `specified_count`, `participation_delta`, `direction`, `national_SV`, `national_specified_count`.

## national-references

**Archivo:** [data/processed/participamx_multiyear/elections/2024/tables/national_references.parquet](../../../../../data/processed/participamx_multiyear/elections/2024/tables/national_references.parquet).

**Filtro:** age_band del perfil; SEXO=0 o 1; antes de seleccionar soporte.

**Campos:** `SV`, `national_specified_count`, `national_rate`.

## v2-cells

**Archivo:** [analysis/profile_v2/results/reference/all_observations.parquet](../../../../../analysis/profile_v2/results/reference/all_observations.parquet).

**Filtro:** v1_parent_profile=ID; conservar hijos con y sin soporte.

**Campos:** `row_id`, `age_band`, `SEXO`, `TIPOSEC`, `LN`, `SV`, `NV`, `NS`, `source_row_count`, `section_count`, `is_eligible`, `reference_age_sex`, `reference_age_sex_section`, `v1_parent_delta`.

## profile-evidence

**Archivo:** [evidence/profile_summary.csv](../evidence/profile_summary.csv).

**Filtro:** profile_id=ID.

**Campos:** `delta_pp`, `delta_sd_pp`, `eligible_cells`, `eligible_flip_cells`, `eligible_flip_LN`, `undefined_cells`.

## joint-evidence

**Archivo:** [evidence/profile_sex_section.csv](../evidence/profile_sex_section.csv).

**Filtro:** profile_id=ID, SEXO, TIPOSEC.

**Campos:** `LN`, `SV`, `NV`, `NS`, `specified_count`, `participation_observed`, `matched_age_sex_reference`, `delta_pp`, `eligible_cells`, `eligible_flip_cells`.

## section-evidence

**Archivo:** [evidence/profile_section.csv](../evidence/profile_section.csv).

**Filtro:** profile_id=ID, TIPOSEC.

**Campos:** `share_of_profile_LN`, `participation_observed`, `matched_age_sex_reference`, `delta_pp`.

## sex-evidence

**Archivo:** [evidence/profile_sex.csv](../evidence/profile_sex.csv).

**Filtro:** profile_id=ID, SEXO.

**Campos:** `participation_observed`, `matched_age_sex_reference`, `delta_pp`.

## territory-evidence

**Archivo:** [evidence/profile_state.csv](../evidence/profile_state.csv).

**Filtro:** profile_id=ID, EDOCVE; ordenar LN descendente.

**Campos:** `state_name_label`, `LN`, `share_of_profile_LN`, `state_core_LN`, `share_of_state_core_LN`.

## reversal-evidence

**Archivo:** [evidence/eligible_sign_reversals.parquet](../evidence/eligible_sign_reversals.parquet).

**Filtro:** candidate_id=ID; is_eligible y exact_sign_opposes_parent.

**Campos:** `row_id`, `row_id_parent`, `LN`, `SV`, `NV`, `specified_count`, `exact_child_direction`, `direction`, `delta_age_sex`, `v1_parent_delta`.

## reversal-quality

**Archivo:** [evidence/reversal_quality.csv](../evidence/reversal_quality.csv).

**Filtro:** profile_id=ID, population=eligible_children/all_children/pending_children.

**Campos:** `defined_cells`, `flip_cells`, `flip_LN`, `flip_near_reference_cells`, `flip_parent_near_reference_cells`, `flip_high_ns_cells`, `flip_few_sections_cells`.

## v2-review

**Archivo:** [analysis/profile_v2/results/reports/final_recommendation.md](../../../../../analysis/profile_v2/results/reports/final_recommendation.md).

**Filtro:** Recuperación V1; recomendaciones, alcance y cambios al desagregar.

**Campos:** .

## prior-interpretation

**Archivo:** [analysis/reports/profile_interpretation_2024.md](../../../../../analysis/reports/profile_interpretation_2024.md).

**Filtro:** Comparación común; ficha con el mismo ID; variación total de las composiciones jóvenes.

**Campos:** .

## Fórmulas y denominadores

D=SV+NV; tasa=SV/D si D>0, NULL en otro caso. Referencia nacional r=ΣSV/ΣD de todos los originales de banda/sexo de 2024, antes de seleccionar soporte. Referencia mezclada de ficha o cruce U/R/M=Σ(Dᵢrᵢ)/ΣDᵢ; Δ=100×(ΣSV/ΣD−referencia). En un cruce de sexo fijo r es constante. No se usa una media simple de tasas para la participación agregada.

U/R/M es tipo de sección electoral, no residencia. Composición LN de un tipo=LN_tipo/LN_ficha. El soporte del hijo requiere LN≥100, D≥100, filas fuente≥5, banda 18–100 y H/M. No se exige cinco secciones: el número distinto de secciones se conserva como bandera separada. NS alto: NS/LN≥10 %. Filas fuente no equivalen a personas ni a secciones independientes.

Cambios de signo: signo(SV_hijo×D_nacional−SV_nacional×D_hijo), comparado con direction del padre; los productos usan enteros Python sin desbordamiento int64. D=0 produce signo NULL; un empate exacto es cero, nunca inversión. Se conserva cada hijo presente; no se fabrican tipos ausentes ni se imputan tasas. Todos los hijos de los padres V1 concilian los siete conteos originales; los hijos elegibles se separan sólo para el diagnóstico de fiabilidad.

No se suman section_count entre celdas para obtener secciones únicas de la ficha. No se suman municipios entre fichas. La zona ≤2 pp y las banderas no son pruebas de significación ni intervalos de confianza.
