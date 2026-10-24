"""Evalúa representaciones demográficas sin normalizar ni ajustar modelos.

Lee únicamente los agregados descriptivos, por bloques y una elección a la vez.
Los intervalos son escenarios de diagnóstico; no sustituyen la edad original.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from clean_data import YEARS, EXPECTED_ROWS, file_hash, require, save_json
from build_descriptive import (COUNTS, METRICS, KEYS, add_indicators, validate_table,
                               compare_sums, safe_ratio, markdown_table, number, pct)

MUNICIPAL_KEYS = KEYS['municipality']
AGE_KEYS = KEYS['municipality_age_sex']
BAND_KEYS = [*MUNICIPAL_KEYS, 'age_band', 'SEXO']
AGE_SCHEMES = {
    'broad': [18, 35, 60, 101],
    'life_stage': [18, 30, 45, 60, 75, 101],
    'decade': [18, 25, 35, 45, 55, 65, 75, 85, 101],
    'life_stage_open': [18, 30, 45, 60, 75],
}
SCHEME_LABELS = {'exact': 'Edad exacta', 'broad': 'Amplios', 'life_stage': 'Etapas',
                 'decade': 'Decenales adaptados', 'life_stage_open': 'Etapas con 75+'}
SUPPORT_LIMITS = [25, 50, 100, 200, 500]
NS_LIMITS = [.05, .10, .20]


def band_labels(scheme):
    edges = AGE_SCHEMES[scheme]
    return [f'{lower}-{edges[index+1]-1}' if index+1 < len(edges) else f'{lower}+'
            for index, lower in enumerate(edges)]


def assign_bands(ages, scheme):
    values = np.asarray(ages)
    require(np.isfinite(values).all() and (values >= 18).all() and np.equal(values, np.floor(values)).all(),
            'Edad no entera o fuera del dominio observado; no se asignará un intervalo arbitrario.')
    return np.asarray(band_labels(scheme))[np.searchsorted(AGE_SCHEMES[scheme], values, side='right')-1]


def group_ages(frame, scheme, thresholds):
    """Suma conteos; la dispersión intrabanda sólo cuantifica pérdida de detalle."""
    work = frame[[*AGE_KEYS, *METRICS]].copy()
    work['age_band'] = assign_bands(work.age_value, scheme)
    specified = work.SV + work.NV
    work['rate_second_moment_sum'] = np.divide(
        work.SV.to_numpy(dtype=float)**2, specified, out=np.zeros(len(work)), where=specified.gt(0))
    grouped = work.groupby(BAND_KEYS, as_index=False, observed=True, dropna=False, sort=False)[
        [*METRICS, 'rate_second_moment_sum']].sum()
    grouped = add_indicators(grouped, thresholds)
    second = safe_ratio(grouped.rate_second_moment_sum, grouped.specified_count)
    grouped['within_band_rate_variance'] = np.maximum(0., second-grouped.participation_observed**2)
    validate_table(grouped, BAND_KEYS)
    compare_sums(grouped, frame, MUNICIPAL_KEYS)
    return grouped


def summarize(frame, alternative, scheme, year, **extra):
    result = dict(alternative=alternative, scheme=scheme, election_year=int(year), observations=len(frame),
                  **{name: int(frame[name].sum()) for name in METRICS},
                  low_support_groups=int(frame.has_low_support.sum()),
                  low_registered_groups=int(frame.has_low_registered_count.sum()),
                  low_specified_groups=int(frame.has_low_specified_count.sum()),
                  few_source_rows_groups=int(frame.has_few_source_rows.sum()),
                  undefined_groups=int(frame.is_observed_undefined.sum()),
                  high_ns_groups=int(frame.has_high_unspecified_rate.sum()),
                  zero_LN_groups=int(frame.LN.eq(0).sum()),
                  low_support_LN=int(frame.loc[frame.has_low_support, 'LN'].sum()),
                  high_ns_LN=int(frame.loc[frame.has_high_unspecified_rate, 'LN'].sum()))
    result['low_support_fraction'] = result['low_support_groups']/len(frame) if len(frame) else np.nan
    result['low_support_LN_fraction'] = result['low_support_LN']/result['LN'] if result['LN'] else np.nan
    result['national_unspecified_rate'] = result['NS']/result['LN'] if result['LN'] else np.nan
    for variable in ['LN', 'specified_count', 'unspecified_rate']:
        series = frame[variable]
        for label, probability in [('min', 0), ('q1', .25), ('median', .5), ('q3', .75), ('p95', .95), ('max', 1)]:
            result[f'{variable}_{label}'] = float(series.quantile(probability)) if len(series.dropna()) else np.nan
    return dict(**result, **extra)


def sensitivity_rows(frame, alternative, scheme, year, thresholds):
    rows = []
    for limit in SUPPORT_LIMITS:
        mask = frame.LN.lt(limit) | frame.specified_count.lt(limit) | frame.source_row_count.lt(thresholds['min_source_rows'])
        rows.append(dict(alternative=alternative, scheme=scheme, election_year=int(year),
            criterion='support', threshold=limit, affected_groups=int(mask.sum()), observations=len(frame),
            affected_LN=int(frame.loc[mask, 'LN'].sum()), total_LN=int(frame.LN.sum())))
    for limit in NS_LIMITS:
        mask = frame.unspecified_rate.ge(limit)
        rows.append(dict(alternative=alternative, scheme=scheme, election_year=int(year),
            criterion='unspecified_rate', threshold=limit, affected_groups=int(mask.sum()), observations=len(frame),
            affected_LN=int(frame.loc[mask, 'LN'].sum()), total_LN=int(frame.LN.sum())))
    return rows


def profile_diagnostics(frame, municipalities, scheme, min_source_rows=5):
    """Cuenta presencia y soporte del perfil; no rellena tasas o conteos ausentes.

    La rejilla común usa H/M. SEXO=2 y las edades de revisión siguen en los
    totales y tablas largas, y se cuantifican como información complementaria.
    """
    if scheme == 'exact':
        core = frame[frame.age_value.between(18, 100) & frame.SEXO.isin(['0', '1'])]
        expected = 83*2
    else:
        core = frame[frame.age_band.ne('101+') & frame.SEXO.isin(['0', '1'])]
        expected = 2*(len(band_labels(scheme))-int('101+' in band_labels(scheme)))
    result = municipalities[[*MUNICIPAL_KEYS, *METRICS, 'specified_count', 'unspecified_rate',
                             'municipality_name_label', 'state_name_label', 'district_reference_year']].copy()
    indexed = core.assign(core_defined=~core.is_observed_undefined, core_strong=~core.has_low_support,
                          core_high_ns=core.has_high_unspecified_rate)
    diagnostics = indexed.groupby(MUNICIPAL_KEYS, as_index=False, observed=True, dropna=False).agg(
        core_present_cells=('LN', 'size'), core_defined_cells=('core_defined', 'sum'),
        core_strong_cells=('core_strong', 'sum'), core_high_ns_cells=('core_high_ns', 'sum'),
        core_LN=('LN', 'sum'), core_specified_count=('specified_count', 'sum'))
    result = result.merge(diagnostics, on=MUNICIPAL_KEYS, how='left', validate='one_to_one')
    diagnostic_columns = ['core_present_cells', 'core_defined_cells', 'core_strong_cells',
                          'core_high_ns_cells', 'core_LN', 'core_specified_count']
    # Cero aquí cuenta celdas presentes; no imputa valores a una celda ausente.
    result[diagnostic_columns] = result[diagnostic_columns].fillna(0).astype('int64')
    result['scheme'] = scheme
    result['core_expected_cells'] = expected
    result['core_absent_cells'] = expected-result.core_present_cells
    result['core_undefined_present_cells'] = result.core_present_cells-result.core_defined_cells
    result['core_low_support_present_cells'] = result.core_present_cells-result.core_strong_cells
    result['core_complete_defined'] = result.core_defined_cells.eq(expected)
    result['core_complete_strong'] = result.core_strong_cells.eq(expected)
    result['core_complete_strong_low_ns'] = result.core_complete_strong & result.core_high_ns_cells.eq(0)
    result['core_LN_fraction'] = safe_ratio(result.core_LN, result.LN)
    # Sensibilidad de todas las coordenadas del perfil, distinta del total municipal.
    for limit in SUPPORT_LIMITS:
        strong = core.assign(strong=core.LN.ge(limit) & core.specified_count.ge(limit)
                             & core.source_row_count.ge(min_source_rows))
        count = strong.groupby(MUNICIPAL_KEYS, observed=True)['strong'].sum()
        index = pd.MultiIndex.from_frame(result[MUNICIPAL_KEYS])
        result[f'complete_support_{limit}'] = count.reindex(index, fill_value=0).to_numpy() == expected
    for limit in NS_LIMITS:
        high = core.assign(high_ns=core.unspecified_rate.ge(limit))
        count = high.groupby(MUNICIPAL_KEYS, observed=True)['high_ns'].sum()
        index = pd.MultiIndex.from_frame(result[MUNICIPAL_KEYS])
        result[f'complete_defined_ns_below_{int(100*limit)}'] = (
            result.core_complete_defined & (count.reindex(index, fill_value=0).to_numpy() == 0))
    require(result.core_absent_cells.ge(0).all(), 'Rejilla de perfil con celdas duplicadas.')
    require(len(result) == len(municipalities), 'Pérdida de municipios al diagnosticar perfiles.')
    return result


def summarize_profiles(profiles):
    rows = []
    for (scheme, year), frame in profiles.groupby(['scheme', 'election_year'], sort=True):
        rows.append(dict(scheme=scheme, election_year=int(year), municipalities=len(frame),
            core_features=int(frame.core_expected_cells.iloc[0]),
            expected_cells=int(frame.core_expected_cells.sum()), present_cells=int(frame.core_present_cells.sum()),
            absent_cells=int(frame.core_absent_cells.sum()), undefined_present_cells=int(frame.core_undefined_present_cells.sum()),
            low_support_present_cells=int(frame.core_low_support_present_cells.sum()),
            high_ns_present_cells=int(frame.core_high_ns_cells.sum()),
            complete_defined=int(frame.core_complete_defined.sum()), complete_strong=int(frame.core_complete_strong.sum()),
            complete_strong_low_ns=int(frame.core_complete_strong_low_ns.sum()),
            core_LN=int(frame.core_LN.sum()), LN=int(frame.LN.sum()),
            core_LN_fraction=float(frame.core_LN.sum()/frame.LN.sum()),
            municipalities_with_sex_2=int(frame.sex_2_source_rows.gt(0).sum()),
            sex_2_source_rows=int(frame.sex_2_source_rows.sum()), sex_2_nominal_count=int(frame.sex_2_nominal_count.sum()),
            **{name: int(frame[name].sum()) for name in frame.columns
               if name.startswith(('complete_support_', 'complete_defined_ns_below_'))}))
    return rows


def computational_cost(observations, dimensions):
    """Estimaciones algebraicas float64, sin asignar matrices ni medir modelos."""
    n, p = int(observations), int(dimensions)
    require(n >= 0 and p > 0, 'Dimensiones no válidas para estimar memoria.')
    pairs = n*(n-1)//2
    return dict(observations=n, dimensions=p, pairs=pairs, condensed_distance_bytes=8*pairs,
                condensed_distance_GiB=8*pairs/2**30, dense_feature_MiB=8*n*p/2**20,
                lloyd_distance_terms_per_iteration_k10=n*p*10)


def historical_inventory(municipalities):
    rows, previous = [], None
    for year, frame in municipalities.groupby('election_year', sort=True):
        current = set(frame[['EDOCVE', 'MPIOCVE']].itertuples(index=False, name=None))
        rows.append(dict(election_year=int(year), observed_keys=len(current),
            keys_added_since_previous=len(current-previous) if previous is not None else None,
            keys_absent_since_previous=len(previous-current) if previous is not None else None,
            same_key_since_previous=len(current & previous) if previous is not None else None))
        previous = current
    return rows


def evaluate_year(frame, municipalities, thresholds):
    """Todos los escenarios son vistas alternativas del mismo total anual."""
    year = int(frame.election_year.iloc[0])
    frame = add_indicators(frame, thresholds)
    validate_table(frame, AGE_KEYS)
    require(frame.age_value.ge(18).all(), 'Edad menor al dominio observado.')
    require(set(frame.SEXO) <= ({'0', '1', '2'} if year == 2024 else {'0', '1'}), 'SEXO fuera del diccionario anual.')
    compare_sums(frame, municipalities, MUNICIPAL_KEYS)
    summaries = [summarize(frame, 'A', 'exact', year), summarize(municipalities, 'C', 'municipal_totals', year)]
    sensitivity = sensitivity_rows(frame, 'A', 'exact', year, thresholds)
    sensitivity += sensitivity_rows(municipalities, 'C', 'municipal_totals', year, thresholds)
    profiles = [profile_diagnostics(frame, municipalities, 'exact', thresholds['min_source_rows'])]
    grouped_tables, band_rows, dispersion = {}, [], []
    for scheme in AGE_SCHEMES:
        grouped = group_ages(frame, scheme, thresholds)
        grouped_tables[scheme] = grouped
        summaries.append(summarize(grouped, 'B', scheme, year))
        sensitivity += sensitivity_rows(grouped, 'B', scheme, year, thresholds)
        profiles.append(profile_diagnostics(grouped, municipalities, scheme, thresholds['min_source_rows']))
        for (band, sex), selected in grouped.groupby(['age_band', 'SEXO'], observed=True, sort=True):
            band_rows.append(summarize(selected, 'B', scheme, year, age_band=band, SEXO=sex,
                possible_municipal_groups=len(municipalities), absent_groups=len(municipalities)-len(selected)))
        core = grouped[grouped.age_band.ne('101+') & grouped.SEXO.isin(['0', '1'])]
        defined = core[core.specified_count.gt(0)]
        dispersion.append(dict(election_year=year, scheme=scheme, core_groups=len(core),
            core_specified_count=int(core.specified_count.sum()),
            weighted_within_band_rate_rmse=float(np.sqrt(np.average(defined.within_band_rate_variance,
                                                                  weights=defined.specified_count))),
            median_within_band_rate_sd=float(np.sqrt(defined.within_band_rate_variance).median())))
    # Compara explícitamente 75+ con 75–100; es un contraste, no un nuevo dato corregido.
    open_old = grouped_tables['life_stage_open'].query("age_band == '75+'")
    closed_old = grouped_tables['life_stage'].query("age_band == '75-100'")
    paired = open_old.merge(closed_old, on=[*MUNICIPAL_KEYS, 'SEXO'], suffixes=('_open', '_closed'), how='outer', validate='one_to_one')
    paired['observed_difference_pp'] = 100*(paired.participation_observed_open-paired.participation_observed_closed)
    paired['scenario'] = '75plus_vs_75to100'
    return summaries, sensitivity, profiles, grouped_tables, band_rows, dispersion, paired


def snapshot_inputs(root, source, source_manifest):
    """Comprueba integridad binaria; no interpreta registros crudos o limpios."""
    require(source_manifest['status'] == 'validated', 'Conjunto descriptivo no validado.')
    success = json.loads((source/'_SUCCESS').read_text(encoding='utf-8'))
    require(success['manifest_sha256'] == file_hash(source/'metadata/run_manifest.json'), 'Manifiesto descriptivo alterado.')
    directories = [root/'data/raw', root/'data/processed/technical_cleaned', source, root/'analysis/charts']
    protected = {str(path): file_hash(path) for directory in directories for path in directory.rglob('*') if path.is_file()}
    for relative in ['analysis/cleaning_plan.md', 'analysis/reports/technical_cleaning.md',
                     'analysis/reports/descriptive_analysis.md', 'analysis/reports/outlier_review.md']:
        path = root/relative
        protected[str(path)] = file_hash(path)
    expected = {entry['path'] for entry in source_manifest['files']}
    require({path.relative_to(source).as_posix() for path in source.rglob('*.parquet')} == expected,
            'Inventario de tablas diferente del manifiesto descriptivo.')
    for entry in source_manifest['files']:
        require(protected[str(source/entry['path'])] == entry['sha256'], f"Agregado alterado: {entry['path']}")
    return protected


def save_frame(path, frame):
    require(not path.exists(), f'No se sobrescribirá {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.parquet':
        table = pa.Table.from_pandas(frame, preserve_index=False)
        pq.write_table(table, path, compression='zstd')
        require(table.equals(pq.read_table(path)), f'Parquet no coincide con el escenario: {path}')
    else:
        frame.to_csv(path, index=False, encoding='utf-8-sig')


def write_report(root, report, evidence, summary, profiles, bands, dispersion, comparison,
                 costs, history, sensitivity, protected, reconciliations, scanned):
    def table(headers, rows):
        return markdown_table(headers, rows)
    def label(scheme):
        return SCHEME_LABELS.get(scheme, scheme)
    def share(numerator, denominator):
        return pct(numerator/denominator) if denominator else 'n/d'
    exact = summary[summary.alternative.eq('A')]
    municipal = summary[summary.alternative.eq('C')]
    grouped = summary[summary.alternative.eq('B')]
    selected_year = 2024
    selected_exact = exact[exact.election_year.eq(selected_year)].iloc[0]
    reference_profile = profiles[profiles.election_year.eq(selected_year) & profiles.scheme.eq('life_stage')].iloc[0]
    broad_profile = profiles[profiles.election_year.eq(selected_year) & profiles.scheme.eq('broad')].iloc[0]
    lines = [
        '# Evaluación de representaciones demográficas para clustering futuro', '',
        '## Recomendación y alcance', '',
        '**Se recomienda preparar posteriormente la alternativa C, municipio–elección con un perfil demográfico, '
        'y comenzar por elecciones separadas.** La recomendación responde al objetivo territorial y al tamaño '
        'computacional, no identifica clusters ni fija una matriz definitiva. Los intervalos de B sirven para '
        'construir y contrastar perfiles de C; B sigue siendo útil si la pregunta es agrupar segmentos demográficos, '
        'mientras que A conserva el detalle para explicación y revisión.', '',
        f'En 2024, A tiene {number(selected_exact.observations)} observaciones y '
        f'{pct(selected_exact.low_support_fraction)} con soporte reducido. C conserva '
        f'{number(reference_profile.municipalities)} municipios, pero un perfil con las diez tasas H/M de '
        f'«Etapas», entre 18 y 100 años, sólo tiene {number(reference_profile.complete_defined)} municipios '
        f'con todas las tasas definidas y {number(reference_profile.complete_strong)} con todas las celdas '
        f'de soporte suficiente. Con seis tasas de «Amplios» son {number(broad_profile.complete_defined)} y '
        f'{number(broad_profile.complete_strong)}, respectivamente. La reducción de filas no resuelve '
        'automáticamente las carencias internas de los perfiles. No se recomienda eliminar los municipios restantes.', '',
        f'En el núcleo común 18–100 de 2024, «Amplios» conserva soporte en '
        f'{share(broad_profile.complete_strong, broad_profile.municipalities)} de los municipios y «Etapas» en '
        f'{share(reference_profile.complete_strong, reference_profile.municipalities)}. La dispersión '
        'intrabanda ponderada es '
        f"{100*dispersion.loc[dispersion.election_year.eq(2024) & dispersion.scheme.eq('broad'), 'weighted_within_band_rate_rmse'].iloc[0]:.2f} pp "
        'y '
        f"{100*dispersion.loc[dispersion.election_year.eq(2024) & dispersion.scheme.eq('life_stage'), 'weighted_within_band_rate_rmse'].iloc[0]:.2f} pp, "
        'respectivamente: ampliar intervalos gana soporte, pero mezcla más variación por edad. '
        'La comparación favorece contrastar ambos diseños antes de fijar rangos.', '',
        'Se leyeron el plan de limpieza y los informes descriptivo y de atípicos. El cálculo reutiliza únicamente '
        f'{number(scanned)} agregados municipio–edad–sexo y las tablas pequeñas de municipio, entidad y año. '
        'Se leen bloques y se conserva como máximo el detalle de una elección a la vez, además de escenarios '
        'agregados y diagnósticos. No se interpretan nuevamente los 54,872,712 registros ni los CSV de los ZIP. '
        'La lectura binaria para hashes sólo comprueba integridad.', '',
        'A/B agrupan **segmentos**: un municipio puede aportar muchas observaciones y recibir varias asignaciones '
        'en un futuro modelo. C agrupa **municipios de una elección**, con edades y sexos como coordenadas '
        'del perfil. No son tres formas equivalentes de responder exactamente la misma pregunta.', '',
        '## Definiciones, cobertura y umbrales', '',
        'En cada escenario se suman LN, SV, NV y NS antes de dividir. El soporte especificado es '
        '`specified_count=SV+NV`; participación observada = SV/(SV+NV), NULL si el denominador es cero; '
        'NS/LN es cobertura no especificada, no abstención. Las tasas se conservan como proporciones; '
        'en este informe se muestran como porcentajes. Las filas fuente no equivalen a personas y las '
        'elecciones no siguen personas únicas.', '',
        'Se reutilizan los umbrales del contrato descriptivo: soporte reducido si LN<100, SV+NV<100 '
        'o filas fuente<5; NS elevado si NS/LN≥10 %. Las banderas se superponen y no son pruebas de error '
        'ni filtros automáticos. También se cuantifican umbrales alternativos de soporte 25, 50, 200 y 500, '
        'y NS de 5 % y 20 %. Los cuartiles de LN y SV+NV describen observaciones con igual peso, '
        'no una distribución de personas.', '',
        '## A. Municipio, edad exacta, sexo y elección', '',
        table(['Año', 'Observaciones', 'LN Q1 / mediana / Q3', 'SV+NV Q1 / mediana / Q3',
               'Soporte reducido', '% grupos', '% LN en ellos', 'Tasas NULL', 'NS≥10 %'],
              [[r.election_year, number(r.observations),
                f'{r.LN_q1:g} / {r.LN_median:g} / {r.LN_q3:g}',
                f'{r.specified_count_q1:g} / {r.specified_count_median:g} / {r.specified_count_q3:g}',
                number(r.low_support_groups), pct(r.low_support_fraction), pct(r.low_support_LN_fraction),
                number(r.undefined_groups), number(r.high_ns_groups)] for r in exact.itertuples()]), '',
        f'Total de A: **{number(exact.observations.sum())} observaciones**. Los mínimos, máximos, p95, '
        'cuartiles de NS/LN y descomposición de banderas quedan en `representation_summary.csv`. '
        'La alta frecuencia de segmentos escasos no implica que concentren la misma proporción de LN; '
        'ambas magnitudes se distinguen en la tabla. Las tasas 0 o 1 pueden ser exactas para denominadores '
        'pequeños y poco útiles para describir un patrón municipal.', '',
        'A conserva edades exactas y permite volver al municipio, pero una distancia basada en edad, sexo '
        'y participación puede separar etapas de vida o categorías en vez de perfiles territoriales. '
        'Si la edad se deja sólo como etiqueta, se pierde su posición demográfica en la distancia; '
        'si entra como número, su escala determina parte de la geometría. Ninguna de esas decisiones se aplica aquí.', '',
        '## B. Municipio, intervalo de edad, sexo y elección', '',
        'Se evalúan cuatro particiones candidatas, continuas y exhaustivas desde 18 años. Son escenarios '
        'descriptivos propios, no categorías oficiales ni rangos definitivos. El último intervalo es abierto; '
        'ninguna edad se trunca, elimina o reemplaza.', '',
        table(['Escenario', 'Intervalos', 'Tasas H/M del perfil principal C'],
              [[label(scheme), ', '.join(band_labels(scheme)),
                2*(len(band_labels(scheme))-int('101+' in band_labels(scheme)))] for scheme in AGE_SCHEMES]), '',
        table(['Año', 'Escenario', 'Observaciones B', 'Mediana LN', 'Mediana SV+NV',
               'Soporte reducido', '% grupos', '% LN en ellos', 'Tasas NULL', 'NS≥10 %'],
              [[r.election_year, label(r.scheme), number(r.observations), f'{r.LN_median:g}',
                f'{r.specified_count_median:g}', number(r.low_support_groups), pct(r.low_support_fraction),
                pct(r.low_support_LN_fraction), number(r.undefined_groups), number(r.high_ns_groups)]
               for r in grouped.itertuples()]), '',
        'Las cifras corresponden a grupos realmente presentes. No se completan intervalos o categorías '
        'ausentes con conteos cero. `band_support.csv` documenta para cada año/intervalo/sexo tanto '
        'grupos presentes como combinaciones ausentes del universo municipal observado; una ausencia '
        'no prueba que no haya personas de ese grupo.', '',
        '### Tamaño y cobertura de los intervalos en 2024', '',
        table(['Escenario', 'Intervalo', 'SEXO', 'Grupos presentes', 'Mediana LN', 'Mediana SV+NV',
               '% soporte reducido', 'Tasas NULL', 'NS≥10 %'],
              [[label(r.scheme), r.age_band, r.SEXO, number(r.observations), f'{r.LN_median:g}',
                f'{r.specified_count_median:g}', pct(r.low_support_fraction), number(r.undefined_groups),
                number(r.high_ns_groups)] for r in bands[bands.election_year.eq(2024) & bands.SEXO.isin(['0', '1'])].itertuples()]), '',
        '### Pérdida de detalle e influencia de la cola', '',
        'Para medir el coste de agrupar, se calcula dentro de cada intervalo/sexo/municipio la dispersión '
        'de las tasas de edad exacta, ponderadas por SV+NV. La raíz del promedio ponderado de sus '
        'varianzas mide heterogeneidad intrabanda; no es un error de muestreo, incertidumbre o validación '
        'del agrupamiento. No se promedian tasas para construir los indicadores. Se omite del diagnóstico '
        'principal sólo la banda complementaria 101+ cuando está separada; en 75+ entra toda la cola.', '',
        table(['Año', 'Escenario', 'Dispersión intrabanda ponderada (pp)'],
              [[r.election_year, label(r.scheme), f'{100*r.weighted_within_band_rate_rmse:.3f}']
               for r in dispersion.itertuples()]), '',
    ]
    tail_rows = []
    for year, selected in comparison.groupby('election_year', sort=True):
        defined = selected.observed_difference_pp.dropna()
        tail_rows.append([year, number(len(selected)), number(len(defined)),
                          f'{defined.abs().median():.5f}', f'{defined.abs().max():.5f}',
                          number(selected.participation_observed_open.notna().sum()),
                          number(selected.participation_observed_closed.notna().sum())])
    lines += [
        table(['Año', 'Pares municipales/sexo presentes en unión', 'Contrastes definidos',
               'Mediana |Δ| (pp)', 'Máx. |Δ| (pp)', '75+ definidos', '75–100 definidos'], tail_rows), '',
        'Δ compara la tasa de 75+ con 75–100; una tasa ausente o no definida no se fuerza a cero. '
        'El contraste conserva ambos escenarios y no valida las edades >100. El archivo '
        '`older_age_comparison.parquet` permite localizar los pares y consultar sus conteos. '
        'Agrupar 75+ puede mejorar soporte y ocultar diferencias internas; separar 101+ hace visible '
        'la revisión de plausibilidad. El perfil con 75+ no es comparable sin esa advertencia al perfil '
        'acotado a 18–100.', '',
        'B mejora el soporte de muchos segmentos, pero sigue produciendo múltiples filas por municipio '
        'y requiere decidir cómo representar categorías y cómo ponderar municipios grandes o con más '
        'segmentos observados. Los intervalos más amplios no son automáticamente mejores: ganan '
        'denominador y pierden resolución de los patrones de edad.', '',
        '## C. Municipio y elección, con un perfil demográfico', '',
        'C conserva **14,779 observaciones municipio–elección**, entre 2,455 y 2,477 por elección. '
        'LN, SV+NV y NS/LN del municipio son el total de **todas las edades y categorías**, igual '
        'bajo cada esquema de perfil. Estos totales no describen el soporte de cada coordenada.', '',
        table(['Año', 'Municipios', 'LN Q1 / mediana / Q3', 'SV+NV Q1 / mediana / Q3',
               'Soporte reducido total', 'Tasa municipal NULL', 'Municipios NS≥10 %', 'NS/LN nacional'],
              [[r.election_year, number(r.observations), f'{r.LN_q1:g} / {r.LN_median:g} / {r.LN_q3:g}',
                f'{r.specified_count_q1:g} / {r.specified_count_median:g} / {r.specified_count_q3:g}',
                number(r.low_support_groups), number(r.undefined_groups), number(r.high_ns_groups),
                pct(r.national_unspecified_rate)] for r in municipal.itertuples()]), '',
        'Se diagnostican cinco perfiles candidatos: edad exacta 18–100 × H/M (166 tasas), y los '
        'cuatro esquemas de intervalos. No se construye ni se guarda una matriz final de entrenamiento. '
        'Para hacer explícita la cobertura, cada perfil cuenta las coordenadas esperadas por municipio, '
        'las ausentes, las presentes pero no definidas y las de soporte reducido. «Completo definido» '
        'requiere todas las tasas; «completo con soporte» requiere además que todas superen las '
        'banderas descriptivas; la última columna exige también NS<10 % en cada coordenada. '
        'Son escenarios de disponibilidad, no criterios de selección.', '',
        table(['Año', 'Perfil', 'Tasas esperadas por municipio', 'Celdas ausentes', 'Presentes NULL',
               'Presentes con soporte reducido', 'Municipios completos definidos',
               'Completos con soporte', 'Completos con soporte y NS<10 %', '% LN en perfil principal'],
              [[r.election_year, label(r.scheme), r.core_features, number(r.absent_cells),
                number(r.undefined_present_cells), number(r.low_support_present_cells), number(r.complete_defined),
                number(r.complete_strong), number(r.complete_strong_low_ns), pct(r.core_LN_fraction)]
               for r in profiles.itertuples()]), '',
        'El núcleo H/M es una propuesta de comparabilidad, no una decisión definitiva de variables. '
        'Todas las edades >100 y SEXO=2 siguen en los totales y tablas largas. En escenarios con '
        '101+ separado se trata como panel complementario de revisión; en 75+ se incluye en esa '
        'coordenada. La ausencia de SEXO=2 en el esquema histórico no se rellena con cero. '
        'Los 105 registros y LN=105 de 2024 se conservan bajo cada escenario; su soporte no permite '
        'construir una coordenada municipal común fiable por defecto. Se informa cuántos municipios '
        f'tienen esta categoría: {number(reference_profile.municipalities_with_sex_2)} en 2024, '
        'y se preserva su posibilidad de análisis específico.', '',
        'Para interpretar C deben acompañar al perfil las tasas originales por edad/sexo, sus cuatro '
        'conteos, denominadores y banderas, además de la participación total. Las diferencias entre '
        'sexos y la composición etaria se pueden estudiar como descriptores adicionales, pero no se '
        'añaden automáticamente a la distancia si ya están codificadas por todas las tasas. Un '
        'municipio con total grande puede seguir teniendo edades o sexos con poco soporte. '
        'La agregación no permite inferir conductas individuales dentro del municipio.', '',
        '## Categorías, redundancia y significado de la distancia', '',
        table(['Riesgo', 'Implicación para la representación futura'], [
            ['Códigos territoriales, distritos, SEXO o año como números continuos',
             'Son identificadores o categorías; su resta no representa una distancia de participación. Mantenerlos como metadatos; evaluar una codificación explícita sólo si responde al objetivo.'],
            ['One-hot de municipio en A/B',
             'Miles de columnas añaden separación por identidad municipal y pueden dominar el objetivo. La clave permite interpretar resultados sin entrar como predictor.'],
            ['Participación y no participación observadas juntas',
             'Suman uno: duplican exactamente la misma información de distancia.'],
            ['LN, SV, NV, NS y specified_count simultáneos',
             'LN=SV+NV+NS y specified_count=SV+NV introducen dependencia exacta; los conteos también reflejan tamaño poblacional. No proponerlos juntos como variables sin una justificación.'],
            ['Participación nominal, observada y NS/LN juntas',
             'SV/LN = participación observada × (1−NS/LN) cuando está definida. Hay redundancia funcional; cobertura y conducta deben tener funciones explícitas.'],
            ['Tasas por intervalo más totales, brechas y composiciones',
             'El total es un promedio ponderado por denominadores; brechas derivan de tasas y las composiciones suman uno. Se puede contar varias veces la misma dimensión o mezcla de tamaño/cobertura.'],
            ['NULL o combinaciones ausentes',
             'No equivalen a participación cero. No se ha resuelto una entrada numérica completa para K-Means ni una distancia finita para enlace jerárquico.'],
            ['Ponderación por municipio, LN o SV+NV',
             'Responde respectivamente a territorios, volumen nominal o volumen especificado; cambia el objetivo y puede reducir la influencia de territorios pequeños. No se adopta automáticamente.'],
        ]), '',
        'K-Means opera con coordenadas numéricas y una suma de distancias cuadráticas; codificar '
        'categorías no resuelve por sí mismo el significado de la distancia. El parámetro sample_weight '
        'permite ponderaciones por observación, pero no resuelve automáticamente fiabilidad diferente '
        'entre coordenadas del perfil. [Documentación primaria de KMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html).', '',
        '## Viabilidad computacional: estimaciones, sin ejecutar modelos', '',
        'Se calcula exactamente n(n−1)/2 y 8 bytes por distancia float64. Es únicamente el vector '
        'condensado, sin memoria adicional del enlace, copias, datos o sistema. No se asigna esa '
        'matriz y no es un benchmark. Para la matriz de características se usa 8np bytes; las '
        'dimensiones 4 de A/B y 10 de C municipal son ilustraciones de coste, no una selección de '
        'variables. Las filas C_profile usan el número real de tasas del perfil candidato.', '',
        table(['Alternativa', 'Escenario', 'Año', 'n', 'p ilustrativo / perfil', 'Pares',
               'Distancias condensadas (GiB)', 'Características (MiB)'],
              [[r.alternative, label(r.scheme), r.election_year, number(r.observations), r.dimensions,
                number(r.pairs), f'{r.condensed_distance_GiB:.3f}', f'{r.dense_feature_MiB:.3f}']
               for r in costs[costs.election_year.astype(str).isin(['2024', 'all'])].itertuples()]), '',
        'El enlace denso de SciPy documenta memoria O(n²); single, complete, average, weighted y '
        'Ward tienen tiempo O(n²), y otros enlaces O(n³). Exige distancias finitas. Ward corresponde '
        'a geometría euclídea; decidir el enlace después de definir la representación. '
        '[Referencia primaria de linkage](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html).', '',
        'Para A, un jerárquico denso sobre todas las observaciones es inviable en una estación '
        'ordinaria incluso por elección; B reduce mucho el coste pero puede requerir varios GiB '
        'sólo para distancias, según esquema y año. C por elección tiene un tamaño razonable para '
        'evaluar enlaces densos una vez resueltos los nulos y la distancia. Reunir todas las '
        'elecciones aumenta el coste cuadrático y cambia la pregunta estadística.', '',
        'Como orden de trabajo orientativo de Lloyd se usa O(tknp), con t iteraciones, k grupos y '
        'p dimensiones; no garantiza tiempo real o convergencia. K-Means no necesita guardar todas '
        'las distancias por pares, así que A/B son más plausibles para un método particional que '
        'para un jerárquico denso, aunque requieren una representación válida y control de recursos. '
        'Elkan puede añadir memoria n×k. C por elección es más manejable para ambos enfoques. '
        '[Costes documentados de KMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html).', '',
        'Si después se autoriza explorar A/B a gran escala, MiniBatchKMeans permite actualizaciones '
        'por bloques como aproximación particional; no reproduce necesariamente un ajuste completo '
        'ni resuelve los problemas de categorías o soporte. No se instaló ni ejecutó. '
        '[Documentación primaria de MiniBatchKMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.MiniBatchKMeans.html).', '',
        '## Sensibilidad sin exclusión automática', '',
        'Los porcentajes de NS se distinguen según unidad y ponderación. El cociente nacional NS/LN '
        'es idéntico entre representaciones que conservan todos los conteos; la distribución no '
        'ponderada de las proporciones de cada grupo sí cambia al agregar.', '',
        table(['Alternativa / escenario (2024)', 'NS/LN Q1', 'Mediana', 'Q3', 'NS/LN nacional'],
              [[r.alternative+' / '+label(r.scheme), pct(r.unspecified_rate_q1),
                pct(r.unspecified_rate_median), pct(r.unspecified_rate_q3), pct(r.national_unspecified_rate)]
               for r in summary[summary.election_year.eq(2024)].itertuples()]), '',
        'Los siguientes recuentos muestran el efecto de cambiar umbrales en 2024. Cada fila es '
        'un diagnóstico independiente; los conteos y las tasas permanecen intactos.', '',
        table(['Alternativa', 'Escenario', 'Criterio', 'Umbral', 'Grupos señalados', '% grupos', '% LN señalado'],
              [[r.alternative, label(r.scheme), r.criterion,
                pct(r.threshold) if r.criterion == 'unspecified_rate' else f'{r.threshold:g}',
                number(r.affected_groups), share(r.affected_groups, r.observations), share(r.affected_LN, r.total_LN)]
               for r in sensitivity[sensitivity.election_year.eq(2024)].itertuples()]), '',
        'Para C se cuenta también cuántos municipios tendrían **todas** las coordenadas del perfil '
        'con LN y SV+NV al menos iguales a cada umbral, manteniendo filas fuente≥5. Los perfiles '
        'incompletos no satisfacen esa condición y siguen conservados. Esto difiere de exigir '
        'soporte sólo al total municipal. Las columnas NS exigen todas las tasas definidas y NS '
        'inferior al umbral en cada coordenada, sin exigir adicionalmente el umbral de soporte.', '',
        table(['Perfil C (2024)', 'Soporte≥25', '≥50', '≥100', '≥200', '≥500',
               'Definido y NS<5 %', 'NS<10 %', 'NS<20 %'],
              [[label(row['scheme']), *[number(row[f'complete_support_{limit}']) for limit in SUPPORT_LIMITS],
                *[number(row[f'complete_defined_ns_below_{int(limit*100)}']) for limit in NS_LIMITS]]
               for row in profiles[profiles.election_year.eq(2024)].to_dict('records')]), '',
        table(['Aspecto', 'Estrategia futura que conserva una referencia completa'], [
            ['Edades extremas',
             'Contrastar perfiles con 101+ como panel explícito y con cola abierta 75+; mantener el detalle exacto y cotejar plausibilidad con fuente. La vista 18–100 no autoriza exclusión analítica. Revisar dónde cambia la representación, no sólo el total nacional.'],
            ['Grupos pequeños',
             'Contrastar los cuatro esquemas y los umbrales medidos; conservar denominadores y cuantificar municipios/coordenadas afectados. Comparar después pesos iguales y ponderaciones justificadas, sin asignar peso cero por defecto. Un modelo de suavizado, si se propone, requiere autorización, supuestos y una versión separada.'],
            ['NS elevado',
             'Usar NS como diagnóstico de cobertura. El intervalo [SV/LN, (SV+NS)/LN] contiene extremos compatibles con la no especificación y tiene amplitud NS/LN; no es una imputación ni un intervalo de confianza. Evaluar luego sensibilidad a cobertura sin convertir NS en NV.'],
            ['Perfiles incompletos',
             'Distinguir combinación ausente, tasa no definida y categoría no disponible históricamente. Comparar diseños más amplios o una futura distancia explícita para información incompleta; cualquier imputación, selección de muestra o distancia especial debe aprobarse y documentarse antes del modelo.'],
            ['Ponderaciones',
             'Separar el objetivo territorial con igual peso municipal de uno nominal o especificado. No considerar LN una garantía de ausencia de sesgo de captura. El esquema de pesos del particional no se traslada sin más a cada enlace jerárquico.'],
            ['Evaluación posterior',
             'Mantener las claves de todos los territorios y comparar estabilidad ante intervalos, cobertura, pesos, distancia/enlace y semillas del particional; informar perfiles y denominadores que expliquen inestabilidad. No se calcula estabilidad ni se decide k en esta etapa.'],
        ]), '',
        '## Elecciones por separado y comparación histórica', '',
        table(['Año', 'Claves observadas', 'Añadidas frente al anterior', 'Ausentes frente al anterior', 'Misma clave'],
              [[r.election_year, number(r.observed_keys),
                'n/a' if pd.isna(r.keys_added_since_previous) else number(r.keys_added_since_previous),
                'n/a' if pd.isna(r.keys_absent_since_previous) else number(r.keys_absent_since_previous),
                'n/a' if pd.isna(r.same_key_since_previous) else number(r.same_key_since_previous)] for r in history.itertuples()]), '',
        'El inventario sólo compara cadenas de claves, no demuestra continuidad territorial. Se recomienda '
        'iniciar cada elección por separado con un contrato común de indicadores y escenarios, porque '
        'la participación y la cobertura cambian entre presidenciales (2012, 2018, 2024) e intermedias '
        '(2009, 2015, 2021). Un modelo conjunto podría agrupar por elección o cobertura, y una codificación '
        'del año como número añadiría una distancia temporal arbitraria. Separar elecciones tampoco '
        'elimina la necesidad de comparar métodos, escalas y soporte antes de interpretar cambios.', '',
        'Una comparación histórica posterior requiere catálogos versionados y correspondencias territoriales '
        'oficiales; el par EDOCVE/MPIOCVE repetido no es prueba suficiente. Las etiquetas numéricas de '
        'clusters de ejecuciones distintas no tienen identidad compartida: comparar perfiles y, donde '
        'haya correspondencia territorial validada, pertenencias alineadas explícitamente. No atribuir '
        'cambios sólo al comportamiento ciudadano: también varían disponibilidad de cuadernillos, NS, '
        'composición etaria, contexto electoral y categorías de captura.', '',
        '## Conservación, reproducción y decisiones pendientes', '',
        'Las claves EDOCVE, MPIOCVE y SEXO siguen siendo texto. Año y par entidad/municipio identifican '
        'la unidad territorial observada; nombres son etiquetas. La referencia distrital se mantiene '
        'en los diagnósticos municipales, sin inferir distritos ni continuidad entre marcos 2021/2023. '
        'Las tablas descriptivas conservan el detalle original y son la referencia para volver a '
        'edad exacta y procedencia; los archivos de escenarios son derivados nuevos de esta evaluación.', '',
        f'Se verificaron {number(reconciliations)} controles escenario–año–entidad, correspondientes '
        'a seis vistas de las 192 combinaciones originales, con diferencias cero en LN, SV, NV, NS, '
        'filas fuente y métricas de SEXO=2. A y cada B se conciliaron además por municipio. '
        'Cada escenario conserva las 54,872,712 filas fuente representadas y los 105 registros '
        'SEXO=2 de 2024; LN=SV+NV+NS se cumple en todos los agregados evaluados. Las vistas son '
        'alternativas y nunca se suman entre sí. Se verificó igualdad tras escribir/releer los '
        f'Parquet nuevos, y la integridad de {number(len(protected))} archivos existentes antes y después.', '',
        'No se fijan rangos, variables, pesos, escala, k, distancias o enlaces definitivos. La siguiente '
        'decisión humana debe precisar si se desean perfiles de municipios (C) o segmentos (B), '
        'el detalle etario aceptable frente al soporte observado, el uso de cobertura en la distancia '
        'o en la interpretación, y el tratamiento autorizado de coordenadas incompletas. La '
        'recomendación es probar como candidatos C–Amplios y C–Etapas por elección, conservando '
        'C–Decenales y la cola abierta como sensibilidad. Ninguna alternativa queda lista para '
        'ajustar K-Means sólo por haber reducido su tamaño.', '',
        'No se modificaron ZIP, Parquet limpios, tablas descriptivas, informes anteriores ni src/. '
        'No se excluyeron registros, imputaron tasas, normalizaron variables ni ejecutaron modelos. '
        'Las agregaciones candidatas no sustituyen ninguna tabla existente. No se crearon commits.', '',
        'Reproducir desde la raíz del proyecto:', '',
        '```powershell', '.venv/Scripts/python.exe analysis/scripts/evaluate_representation.py', '```', '',
        f'Evidencia: `{evidence.relative_to(root).as_posix()}/`. Contiene resúmenes, soporte por intervalo, '
        'perfiles municipales, sensibilidad de umbrales, dispersión intrabanda, contraste 75+/75–100, '
        'costes algebraicos, conciliación, inventario histórico, escenarios Parquet y manifiesto de '
        'versiones/hashes. El programa rechaza destinos existentes; para repetir usar nuevas rutas '
        '`--evidence` y `--report`. No requiere nuevas dependencias.', '',
    ]
    report.write_text('\n'.join(lines), encoding='utf-8')


def run_evaluation(root, evidence, report, batch_size=100_000):
    root, evidence, report = Path(root).resolve(), Path(evidence).resolve(), Path(report).resolve()
    require(batch_size > 0, 'batch-size debe ser positivo.')
    require(evidence.is_relative_to(root/'analysis/reports') and report.is_relative_to(root/'analysis/reports'),
            'Las salidas deben quedar dentro de analysis/reports/.')
    require(not evidence.exists() and not report.exists(), 'Elegir rutas nuevas con --evidence y --report; no se sobrescribe.')
    require(not report.is_relative_to(evidence), 'El informe debe quedar fuera del directorio de evidencia.')
    source = root/'data/processed/descriptive'
    source_manifest = json.loads((source/'metadata/run_manifest.json').read_text(encoding='utf-8'))
    protected = snapshot_inputs(root, source, source_manifest)
    contract = json.loads((source/'metadata/table_contract.json').read_text(encoding='utf-8'))
    thresholds = contract['thresholds']
    started = time.monotonic()
    evidence.mkdir(parents=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    manifest = dict(status='running', errors=[], batch_size=batch_size, thresholds=thresholds,
        age_schemes=AGE_SCHEMES, support_sensitivity=SUPPORT_LIMITS, ns_sensitivity=NS_LIMITS,
        protected_hashes=protected, started_at_utc=datetime.now(timezone.utc).isoformat(),
        versions=dict(python=platform.python_version(), pandas=pd.__version__, numpy=np.__version__, pyarrow=pa.__version__),
        algorithm_policy='No se importa ni ejecuta clustering, escalado estadístico o imputación.')
    save_json(evidence/'run_manifest.json', manifest)
    try:
        municipalities = pd.read_parquet(source/'municipality/table.parquet')
        states = pd.read_parquet(source/'state/table.parquet')
        annual = pd.read_parquet(source/'year/table.parquet')
        dataset = ds.dataset(source/'municipality_age_sex', format='parquet')
        summaries, sensitivities, profiles, bands, dispersions, comparisons, reconciliations = [], [], [], [], [], [], []
        scanned = 0
        for year in YEARS:
            batches = dataset.scanner(columns=[*AGE_KEYS, *METRICS], filter=ds.field('election_year') == year,
                                      batch_size=batch_size).to_batches()
            frame = pd.concat([batch.to_pandas() for batch in batches if batch.num_rows], ignore_index=True)
            current_municipalities = municipalities[municipalities.election_year.eq(year)]
            result = evaluate_year(frame, current_municipalities, thresholds)
            summary, sensitivity, profile, tables, band, dispersion, paired = result
            summaries.extend(summary); sensitivities.extend(sensitivity); profiles.extend(profile)
            bands.extend(band); dispersions.extend(dispersion); comparisons.append(paired)
            for scheme, table in [('exact', frame), ('municipal_totals', current_municipalities), *tables.items()]:
                compare_sums(table, states[states.election_year.eq(year)], ['election_year', 'EDOCVE'])
                for state, selected in table.groupby('EDOCVE', sort=True):
                    expected = states[states.election_year.eq(year) & states.EDOCVE.eq(state)].iloc[0]
                    reconciliations.append(dict(scheme=scheme, election_year=year, EDOCVE=state,
                        **{f'{metric}_difference': int(selected[metric].sum())-int(expected[metric]) for metric in METRICS}))
                if scheme in AGE_SCHEMES:
                    save_frame(evidence/f'grouped_candidates/{scheme}/part-{year}.parquet', table)
            scanned += len(frame)
            print(f'{year}: {len(frame):,} agregados; cuatro esquemas y cinco diagnósticos de perfil conciliados.', flush=True)
        summary = pd.DataFrame(summaries)
        # El contrato Parquet usa int16; compare_sums exige igualdad de claves y tipos.
        summary['election_year'] = summary.election_year.astype(annual.election_year.dtype)
        profile = pd.concat(profiles, ignore_index=True)
        profile_summary = pd.DataFrame(summarize_profiles(profile))
        sensitivity = pd.DataFrame(sensitivities)
        band = pd.DataFrame(bands)
        dispersion = pd.DataFrame(dispersions)
        comparison = pd.concat(comparisons, ignore_index=True)
        reconciliation = pd.DataFrame(reconciliations)
        require(scanned == source_manifest['table_rows']['municipality_age_sex'], 'Pérdida de agregados de entrada.')
        for _, selected in summary.groupby(['alternative', 'scheme']):
            require(int(selected.source_row_count.sum()) == EXPECTED_ROWS, 'Filas fuente no conservadas.')
            require(int(selected.sex_2_source_rows.sum()) == int(selected.sex_2_nominal_count.sum()) == 105,
                    'SEXO=2 no conservado en un escenario.')
            compare_sums(selected, annual, ['election_year'])
        require(reconciliation.filter(like='_difference').eq(0).all().all(), 'Diferencias en conciliación estatal.')
        history = pd.DataFrame(historical_inventory(municipalities))
        cost_rows = []
        for row in summary.to_dict('records'):
            dimensions = 4 if row['alternative'] != 'C' else 10
            cost_rows.append(dict(alternative=row['alternative'], scheme=row['scheme'], election_year=row['election_year'],
                **computational_cost(row['observations'], dimensions)))
        for (alternative, scheme), selected in summary.groupby(['alternative', 'scheme']):
            cost_rows.append(dict(alternative=alternative, scheme=scheme, election_year='all',
                **computational_cost(selected.observations.sum(), 10 if alternative == 'C' else 4)))
        for row in profile_summary.to_dict('records'):
            cost_rows.append(dict(alternative='C_profile', scheme=row['scheme'], election_year=row['election_year'],
                **computational_cost(row['municipalities'], row['core_features'])))
        costs = pd.DataFrame(cost_rows)
        outputs = {'representation_summary.csv': summary, 'band_support.csv': band, 'profile_summary.csv': profile_summary,
                   'municipality_profile_diagnostics.parquet': profile, 'sensitivity_thresholds.csv': sensitivity,
                   'within_band_dispersion.csv': dispersion, 'older_age_comparison.parquet': comparison,
                   'state_reconciliation.csv': reconciliation, 'historical_key_inventory.csv': history,
                   'computational_cost.csv': costs}
        for name, table in outputs.items(): save_frame(evidence/name, table)
        write_report(root, report, evidence, summary, profile_summary, band, dispersion, comparison, costs,
                     history, sensitivity, protected, len(reconciliation), scanned)
        for path, digest in protected.items(): require(file_hash(path) == digest, f'Archivo protegido modificado: {path}')
        manifest.update(status='validated', scanned_aggregate_groups=scanned, protected_files=len(protected),
            state_reconciliations=len(reconciliation), seconds=round(time.monotonic()-started, 2),
            finished_at_utc=datetime.now(timezone.utc).isoformat(), script_sha256=file_hash(Path(__file__)),
            output_hashes={str(path.relative_to(root)): file_hash(path) for path in evidence.rglob('*')
                           if path.is_file() and path.name != 'run_manifest.json'}, report_sha256=file_hash(report))
        save_json(evidence/'run_manifest.json', manifest)
        print(f'VALIDADO: {scanned:,} agregados; informe: {report.relative_to(root)}', flush=True)
        return manifest
    except Exception as error:
        manifest.update(status='failed')
        manifest['errors'].append(dict(type=type(error).__name__, message=str(error)))
        save_json(evidence/'run_manifest.json', manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--evidence', type=Path, default=Path('analysis/reports/representation_evaluation'))
    parser.add_argument('--report', type=Path, default=Path('analysis/reports/clustering_representation.md'))
    parser.add_argument('--batch-size', type=int, default=100_000)
    args = parser.parse_args()
    root = args.root.resolve()
    run_evaluation(root, args.evidence if args.evidence.is_absolute() else root/args.evidence,
                   args.report if args.report.is_absolute() else root/args.report, args.batch_size)


if __name__ == '__main__':
    main()
