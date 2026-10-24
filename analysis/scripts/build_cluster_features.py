"""Prepara matrices candidatas de 2024 sin escalar, imputar o ajustar modelos.

Reutiliza los cuatro escenarios ya evaluados. Conserva todas las filas y
separa las variables numéricas de claves, conteos y señales de revisión.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from clean_data import file_hash, require, save_json
from build_descriptive import (COUNTS, METRICS, add_indicators, compare_sums, validate_table,
                               safe_ratio, pct, number, markdown_table)
from evaluate_representation import AGE_SCHEMES, SCHEME_LABELS, MUNICIPAL_KEYS, BAND_KEYS, assign_bands, band_labels

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

YEAR = 2024
PROFILE_SCHEMES = ['broad', 'life_stage']
SEX_NAMES = {'0': 'men', '1': 'women'}
B_FEATURES = ['participation_observed', 'mean_age_nominal']
REPORT_INPUTS = ['analysis/reports/clustering_representation.md', 'analysis/reports/outlier_review.md',
                 'analysis/reports/descriptive_analysis.md']


def make_ids(frame, columns, prefix):
    """Identidad legible; las claves nunca se convierten a magnitudes numéricas."""
    for column in columns:
        require(not frame[column].isna().any(), f'Clave nula: {column}')
        require(not frame[column].astype(str).str.contains('|', regex=False).any(), 'Separador reservado en clave.')
    values = frame[columns].astype(str).agg('|'.join, axis=1)
    return prefix+'|'+values


def age_moments(reference, scheme):
    """Momentos descriptivos de edad nominal sin sustituir las edades exactas."""
    frame = reference[[*MUNICIPAL_KEYS, 'age_value', 'SEXO', 'LN']].copy()
    frame['age_band'] = assign_bands(frame.age_value, scheme)
    frame['age_nominal_sum'] = frame.age_value*frame.LN
    frame['age_squared_nominal_sum'] = frame.age_value**2*frame.LN
    frame['over_100_nominal_count'] = np.where(frame.age_value.gt(100), frame.LN, 0)
    result = frame.groupby(BAND_KEYS, as_index=False, observed=True, sort=False).agg(
        age_nominal_sum=('age_nominal_sum', 'sum'), age_squared_nominal_sum=('age_squared_nominal_sum', 'sum'),
        age_min_observed=('age_value', 'min'), age_max_observed=('age_value', 'max'),
        over_100_nominal_count=('over_100_nominal_count', 'sum'), moment_LN=('LN', 'sum'))
    result['mean_age_nominal'] = safe_ratio(result.age_nominal_sum, result.moment_LN)
    variance = safe_ratio(result.age_squared_nominal_sum, result.moment_LN)-result.mean_age_nominal**2
    result['age_nominal_sd'] = np.sqrt(np.maximum(0., variance))
    return result


def feature_status(features):
    values = features.drop(columns='row_id').to_numpy(dtype=float)
    return pd.DataFrame(dict(row_id=features.row_id,
        null_feature_count=np.isnan(values).sum(axis=1),
        nonfinite_feature_count=(~np.isfinite(values) & ~np.isnan(values)).sum(axis=1),
        can_use_complete_algorithms=np.isfinite(values).all(axis=1)))


def build_segments(grouped, reference, municipalities, scheme):
    """B conserva cola y SEXO=2; los conteos permanecen fuera de la matriz."""
    moments = age_moments(reference, scheme)
    metadata = grouped.merge(moments, on=BAND_KEYS, how='outer', validate='one_to_one', indicator=True)
    require(metadata['_merge'].eq('both').all(), 'Escenario y momentos no tienen las mismas claves.')
    metadata = metadata.drop(columns='_merge')
    require(metadata.LN.eq(metadata.moment_LN).all(), 'LN de momentos no coincide con el escenario.')
    metadata = metadata.drop(columns='moment_LN').merge(
        municipalities[[*MUNICIPAL_KEYS, 'municipality_name_label', 'state_name_label', 'district_reference_year']],
        on=MUNICIPAL_KEYS, how='left', validate='many_to_one')
    metadata = metadata.sort_values(BAND_KEYS).reset_index(drop=True)
    metadata.insert(0, 'row_id', make_ids(metadata, BAND_KEYS, 'b_'+scheme))
    features = metadata[['row_id', *B_FEATURES]].copy()
    metadata = metadata.merge(feature_status(features), on='row_id', validate='one_to_one')
    metadata['equal_segment_weight'] = 1.0
    # Cada municipio aporta peso total uno, aunque varíe el número de segmentos presentes.
    metadata['equal_municipality_weight'] = 1/metadata.groupby(MUNICIPAL_KEYS, observed=True).row_id.transform('size')
    metadata['nominal_weight'] = metadata.LN
    validate_table(metadata, BAND_KEYS)
    require(not metadata.row_id.duplicated().any(), 'Identidad B repetida.')
    return features, metadata


def profile_feature_names(scheme):
    return [f'participation_{band.replace("-", "_")}_{SEX_NAMES[sex]}'
            for band in band_labels(scheme) if band != '101+' for sex in SEX_NAMES]


def build_profiles(grouped, municipalities, scheme):
    """C conserva todos los municipios; rejilla ausente mantiene metadatos NULL."""
    require(scheme in PROFILE_SCHEMES, 'Escenario C no solicitado.')
    metadata = municipalities.sort_values(MUNICIPAL_KEYS).reset_index(drop=True).copy()
    metadata.insert(0, 'row_id', make_ids(metadata, MUNICIPAL_KEYS, 'c_'+scheme))
    bands = [band for band in band_labels(scheme) if band != '101+']
    dimensions = pd.DataFrame([dict(age_band=band, SEXO=sex,
        feature_name=f'participation_{band.replace("-", "_")}_{SEX_NAMES[sex]}') for band in bands for sex in SEX_NAMES])
    grid = metadata[['row_id', *MUNICIPAL_KEYS]].merge(dimensions, how='cross')
    core = grouped[grouped.age_band.isin(bands) & grouped.SEXO.isin(SEX_NAMES)]
    cells = grid.merge(core, on=BAND_KEYS, how='left', validate='one_to_one', indicator=True)
    cells['is_present'] = cells['_merge'].eq('both')
    cells = cells.drop(columns='_merge')
    cells['value_status'] = np.where(~cells.is_present, 'absent_combination',
                                    np.where(cells.participation_observed.isna(), 'undefined_rate', 'defined'))
    # El contrato distingue enteros nullable de celdas presentes con conteo cero.
    for column in [*METRICS, 'specified_count']:
        cells[column] = cells[column].astype('Int64')
    for column in ['has_low_support', 'has_high_unspecified_rate', 'is_observed_undefined']:
        cells[column] = cells[column].astype('boolean')
    wide = cells.pivot(index='row_id', columns='feature_name', values='participation_observed')
    features = wide.reindex(index=metadata.row_id, columns=profile_feature_names(scheme)).reset_index()
    features.columns.name = None
    status = feature_status(features)
    metadata = metadata.merge(status, on='row_id', validate='one_to_one')
    by_id = cells.groupby('row_id', observed=True).agg(
        absent_feature_count=('is_present', lambda values: int((~values).sum())),
        undefined_feature_count=('value_status', lambda values: int(values.eq('undefined_rate').sum())),
        low_support_feature_count=('has_low_support', 'sum'), high_ns_feature_count=('has_high_unspecified_rate', 'sum'),
        core_LN=('LN', lambda values: values.sum(min_count=1)),
        core_specified_count=('specified_count', lambda values: values.sum(min_count=1)))
    metadata = metadata.merge(by_id, on='row_id', validate='one_to_one')
    metadata['complement_LN'] = metadata.LN-metadata.core_LN
    metadata['equal_municipality_weight'] = 1.0
    metadata['nominal_weight'] = metadata.LN
    metadata['has_low_support_features'] = metadata.low_support_feature_count.gt(0)
    metadata['has_high_ns_features'] = metadata.high_ns_feature_count.gt(0)
    require(metadata.null_feature_count.eq(metadata.absent_feature_count+metadata.undefined_feature_count).all(),
            'Nulos C no explicados por ausencia o no especificación.')
    require(len(features) == len(municipalities), 'Se perdió un municipio en C.')
    present = cells[cells.is_present]
    require(present.LN.eq(present.SV+present.NV+present.NS).all(), 'Identidad fallida en celdas C.')
    return features, metadata, cells


def weighted_summary(values, weights):
    """Resumen descriptivo: pesos relativos sólo en el cálculo, no en los datos."""
    values, weights = np.asarray(values, dtype=float), np.asarray(weights, dtype=float)
    require(np.isfinite(weights).all() and (weights >= 0).all(), 'Pesos no válidos.')
    mask = np.isfinite(values) & (weights > 0)
    result = dict(valid_observations=int(mask.sum()), missing_observations=int((~np.isfinite(values)).sum()),
                  valid_weight=float(weights[mask].sum()), total_weight=float(weights.sum()))
    if not mask.any():
        return dict(**result, mean=np.nan, std=np.nan, min=np.nan, q1=np.nan, median=np.nan, q3=np.nan,
                    max=np.nan, unique_values=0, concentration_equivalent_units=0.)
    values, weights = values[mask], weights[mask]
    mean = np.average(values, weights=weights)
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    quantiles = values[order][np.searchsorted(cumulative, cumulative[-1]*np.array([.25, .5, .75]), side='left')]
    return dict(**result, mean=float(mean), std=float(np.sqrt(np.average((values-mean)**2, weights=weights))),
                min=float(values.min()), q1=float(quantiles[0]), median=float(quantiles[1]), q3=float(quantiles[2]),
                max=float(values.max()), unique_values=int(len(np.unique(values))),
                concentration_equivalent_units=float(weights.sum()**2/np.dot(weights, weights)))


def correlation_statistics(left, right, weights):
    left, right, weights = map(lambda values: np.asarray(values, dtype=float), (left, right, weights))
    mask = np.isfinite(left) & np.isfinite(right) & np.isfinite(weights) & (weights > 0)
    n = int(mask.sum())
    if n < 2 or (n and (np.ptp(left[mask]) == 0 or np.ptp(right[mask]) == 0)):
        return dict(pair_observations=n, pair_weight=float(weights[mask].sum()), pearson=np.nan)
    x, y, w = left[mask], right[mask], weights[mask]
    x, y = x-np.average(x, weights=w), y-np.average(y, weights=w)
    denominator = np.sqrt(np.dot(w, x*x)*np.dot(w, y*y))
    correlation = np.dot(w, x*y)/denominator if denominator > 0 else np.nan
    return dict(pair_observations=n, pair_weight=float(w.sum()), pearson=float(np.clip(correlation, -1, 1)))


def diagnostic_tables(matrix_id, features, metadata, alternative):
    names = features.columns.drop('row_id').tolist()
    require(features.row_id.equals(metadata.row_id), 'Orden distinto entre matriz y metadatos.')
    weight_modes = ['equal_segment_weight', 'equal_municipality_weight', 'nominal_weight'] if alternative == 'B' else ['equal_municipality_weight', 'nominal_weight']
    distributions, correlations, weights_summary = [], [], []
    diagnostic_names = ['LN', 'SV', 'NV', 'NS', 'specified_count', 'participation_observed',
                        'nonparticipation_observed', 'participation_nominal', 'unspecified_rate']
    diagnostic = metadata[[name for name in diagnostic_names if name in metadata]].copy()
    if alternative == 'B': diagnostic['mean_age_nominal'] = features.mean_age_nominal
    for mode in weight_modes:
        weights = metadata[mode].to_numpy(dtype=float)
        low = metadata.has_low_support if alternative == 'B' else metadata.has_low_support_features
        high = metadata.has_high_unspecified_rate if alternative == 'B' else metadata.has_high_ns_features
        municipal_weights = metadata.assign(diagnostic_weight=weights).groupby(MUNICIPAL_KEYS, observed=True).diagnostic_weight.sum()
        weights_summary.append(dict(matrix_id=matrix_id, weighting=mode, total_weight=float(weights.sum()),
            concentration_equivalent_units=float(weights.sum()**2/np.dot(weights, weights)),
            top_10_municipal_weight_share=float(municipal_weights.nlargest(10).sum()/weights.sum()),
            incomplete_weight_share=float(weights[~metadata.can_use_complete_algorithms].sum()/weights.sum()),
            low_support_weight_share=float(weights[low].sum()/weights.sum()),
            high_ns_weight_share=float(weights[high].sum()/weights.sum())))
        for name in names:
            distributions.append(dict(matrix_id=matrix_id, weighting=mode, feature=name,
                                      **weighted_summary(features[name], weights)))
        for scope, frame in [('features', features[names]), ('metadata_redundancy', diagnostic)]:
            columns = frame.columns.tolist()
            for i, left in enumerate(columns):
                for right in columns[i:]:
                    stats = correlation_statistics(frame[left], frame[right], weights)
                    mask = frame[left].notna() & frame[right].notna()
                    spearman = (frame.loc[mask, left].rank().corr(frame.loc[mask, right].rank())
                                if mask.sum() >= 2 and frame.loc[mask, left].nunique() > 1
                                and frame.loc[mask, right].nunique() > 1 else np.nan)
                    correlations.append(dict(matrix_id=matrix_id, scope=scope, weighting=mode,
                        left=left, right=right, **stats, spearman_unweighted=float(spearman)))
    low = metadata.has_low_support if alternative == 'B' else metadata.has_low_support_features
    high = metadata.has_high_unspecified_rate if alternative == 'B' else metadata.has_high_ns_features
    summary = dict(matrix_id=matrix_id, alternative=alternative, observations=len(features), numeric_features=len(names),
        null_cells=int(features[names].isna().sum().sum()), incomplete_observations=int((~metadata.can_use_complete_algorithms).sum()),
        complete_observations=int(metadata.can_use_complete_algorithms.sum()),
        low_support_observations=int(low.sum()), high_ns_observations=int(high.sum()),
        complete_low_support=int((metadata.can_use_complete_algorithms & low).sum()),
        complete_strong=int((metadata.can_use_complete_algorithms & ~low).sum()),
        complete_strong_low_ns=int((metadata.can_use_complete_algorithms & ~low & ~high).sum()),
        **{metric: int(metadata[metric].sum()) for metric in METRICS})
    return summary, distributions, correlations, weights_summary


def redundancy_checks(grouped):
    checks = {
        'nominal_partition': grouped.LN-grouped.SV-grouped.NV-grouped.NS,
        'specified_partition': grouped.specified_count-grouped.SV-grouped.NV,
        'observed_complement': grouped.participation_observed+grouped.nonparticipation_observed-1,
        'nominal_rate_relation': grouped.participation_nominal-grouped.participation_observed*(1-grouped.unspecified_rate),
    }
    return [dict(identity=name, defined_groups=int(values.notna().sum()), max_absolute_residual=float(values.abs().max()))
            for name, values in checks.items()]


def curve_diagnostics(reference, municipalities):
    """Revisa soporte de curvas crudas; no ajusta ni interpola curvas."""
    rows = []
    for sex in SEX_NAMES:
        for age in range(18, 101):
            frame = reference[reference.SEXO.eq(sex) & reference.age_value.eq(age)]
            rows.append(dict(age_value=age, SEXO=sex, municipalities=len(municipalities), present=len(frame),
                absent=len(municipalities)-len(frame), undefined=int(frame.is_observed_undefined.sum()),
                low_support=int(frame.has_low_support.sum()), strong=int((~frame.has_low_support).sum()),
                high_ns=int(frame.has_high_unspecified_rate.sum()), LN=int(frame.LN.sum()),
                specified_count=int(frame.specified_count.sum())))
    return pd.DataFrame(rows)


def save_table(path, frame):
    require(not path.exists(), f'No se sobrescribirá {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.parquet':
        table = pa.Table.from_pandas(frame, preserve_index=False)
        pq.write_table(table, path, compression='zstd')
        require(table.equals(pq.read_table(path)), f'Lectura Parquet distinta de salida: {path}')
    else:
        frame.to_csv(path, index=False, encoding='utf-8-sig')


def plot_diagnostics(charts, matrices, summary, distribution, correlations, curves):
    labels = {matrix_id: matrix_id.replace('b_', 'B · ').replace('c_', 'C · ')
              .replace('life_stage_open', 'etapas 75+').replace('life_stage', 'etapas')
              .replace('broad', 'amplios').replace('decade', 'decenales') for matrix_id in matrices}
    fig, ax = plt.subplots(figsize=(11, 5.8), layout='constrained')
    positions = np.arange(len(summary))
    for offset, column, color, text in [(-.25, 'complete_observations', '#386cb0', 'Completitud numérica'),
        (0, 'complete_strong', '#1b9e77', 'Completa y soporte suficiente'),
        (.25, 'complete_strong_low_ns', '#e6ab02', 'Completa, soporte y NS<10 %')]:
        ax.bar(positions+offset, summary[column]/summary.observations, width=.24, color=color, label=text)
    ax.set_xticks(positions, [labels[value]+'\nn='+number(n) for value, n in zip(summary.matrix_id, summary.observations)])
    ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.set_ylim(0, 1.07)
    ax.set_ylabel('Proporción de observaciones de cada matriz'); ax.legend(loc='lower left')
    ax.set_title('Cobertura de matrices candidatas · 2024\nSoporte y NS: segmento B o cualquier coordenada del perfil C')
    fig.savefig(charts/'matrix_coverage.png', dpi=170); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8), layout='constrained')
    for ax, scheme in zip(axes, PROFILE_SCHEMES):
        features = matrices['c_'+scheme][0]
        names = profile_feature_names(scheme)
        ax.boxplot([features[name].dropna().to_numpy() for name in names],
                   tick_labels=[name.replace('participation_', '').replace('_men', ' H').replace('_women', ' M').replace('_', '–') for name in names],
                   flierprops=dict(markersize=2, alpha=.35))
        ax.tick_params(axis='x', labelrotation=60); ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_ylim(-.02, 1.02); ax.set_title('C · '+SCHEME_LABELS[scheme]); ax.set_ylabel('Participación observada')
    fig.suptitle('Distribuciones municipales por edad y sexo · 2024\nTasas definidas; los nulos permanecen en las matrices')
    fig.savefig(charts/'profile_distributions.png', dpi=170); plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(12, 11), layout='constrained')
    for column, scheme in enumerate(PROFILE_SCHEMES):
        matrix_id = 'c_'+scheme
        names = profile_feature_names(scheme)
        ticks = [name.replace('participation_', '').replace('_men', ' H').replace('_women', ' M').replace('_', '–') for name in names]
        for row, mode in enumerate(['equal_municipality_weight', 'nominal_weight']):
            selected = correlations[correlations.matrix_id.eq(matrix_id) & correlations.scope.eq('features') & correlations.weighting.eq(mode)]
            values = pd.DataFrame(np.nan, index=names, columns=names)
            for item in selected.itertuples(): values.loc[item.left, item.right] = values.loc[item.right, item.left] = item.pearson
            ax = axes[row, column]
            mesh = ax.imshow(values, vmin=-1, vmax=1, cmap='RdBu_r')
            ax.set_xticks(range(len(names)), ticks, rotation=65, ha='right'); ax.set_yticks(range(len(names)), ticks)
            ax.set_title(SCHEME_LABELS[scheme]+' · '+('municipios iguales' if row == 0 else 'peso LN'))
            if len(names) <= 6:
                for i in range(len(names)):
                    for j in range(len(names)):
                        if pd.notna(values.iloc[i, j]): ax.text(j, i, f'{values.iloc[i,j]:.2f}', ha='center', va='center', fontsize=8)
    fig.colorbar(mesh, ax=axes.ravel().tolist(), shrink=.7, label='Correlación de Pearson por pares definidos')
    fig.suptitle('Redundancia potencial entre tasas C · 2024\nCorrelación descriptiva; no causalidad ni variables descartadas')
    fig.savefig(charts/'profile_correlations.png', dpi=170); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.3), layout='constrained')
    for ax, scheme in zip(axes, PROFILE_SCHEMES):
        names = profile_feature_names(scheme)
        for mode, color, text in [('equal_municipality_weight', '#386cb0', 'Igual peso municipal'), ('nominal_weight', '#d95f02', 'Peso LN municipal')]:
            selected = distribution[distribution.matrix_id.eq('c_'+scheme) & distribution.weighting.eq(mode)].set_index('feature').reindex(names)
            ax.plot(range(len(names)), selected['mean'], 'o-', color=color, label=text)
        ax.set_xticks(range(len(names)), [name.replace('participation_', '').replace('_men', ' H').replace('_women', ' M').replace('_', '–') for name in names], rotation=60)
        ax.set_title('C · '+SCHEME_LABELS[scheme]); ax.set_ylim(0, 1); ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_ylabel('Media descriptiva entre municipios con tasa definida'); ax.legend()
    fig.suptitle('Efecto de la ponderación sobre los resúmenes · 2024\nNo se modifican variables ni se ajustan modelos')
    fig.savefig(charts/'weight_effects.png', dpi=170); plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(12, 9), layout='constrained')
    for ax, scheme in zip(axes.ravel(), AGE_SCHEMES):
        features, metadata = matrices['b_'+scheme]
        valid = metadata.can_use_complete_algorithms
        mesh = ax.hexbin(features.loc[valid, 'mean_age_nominal'], features.loc[valid, 'participation_observed'],
                         gridsize=35, mincnt=1, cmap='Blues', bins='log')
        nonbinary = valid & metadata.SEXO.eq('2')
        ax.scatter(features.loc[nonbinary, 'mean_age_nominal'], features.loc[nonbinary, 'participation_observed'],
                   marker='x', s=22, color='#e6550d', label='SEXO=2, sin líneas')
        ax.set_xlabel('Edad media del segmento ponderada por LN (años)'); ax.set_ylabel('Participación observada')
        ax.set_ylim(-.02, 1.02); ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.legend(fontsize=8)
        ax.set_title(SCHEME_LABELS[scheme]+f' · {int((~valid).sum())} filas no representables por NULL')
        fig.colorbar(mesh, ax=ax, label='Segmentos por hexágono (color logarítmico)')
    fig.suptitle('Espacio numérico candidato B · 2024\nHexágonos de frecuencia: no son clusters; se conservan todas las edades')
    fig.savefig(charts/'segment_feature_space.png', dpi=170); plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 5.4), layout='constrained')
    for sex, color, text in [('0', '#386cb0', 'Hombres'), ('1', '#d95f02', 'Mujeres')]:
        selected = curves[curves.SEXO.eq(sex)]
        ax.plot(selected.age_value, selected.strong/selected.municipalities, color=color, label=text)
    ax.set_ylim(0, 1); ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.legend()
    ax.set_xlabel('Edad exacta'); ax.set_ylabel('Municipios con soporte suficiente / municipios observados')
    ax.set_title('Viabilidad de perfiles por edad exacta · 2024\nSe mide soporte por edad; no se ajustan curvas de participación')
    fig.savefig(charts/'exact_age_support.png', dpi=170); plt.close(fig)


def write_report(root, output, charts, report, summary, distribution, correlations, weights, redundancy,
                 previous_profiles, reference, curves, protected_count):
    table = markdown_table
    def image(name, text): return f'![{text}]({Path(os.path.relpath(charts/name, report.parent)).as_posix()})'
    labels = lambda matrix_id: matrix_id.replace('b_', 'B / ').replace('c_', 'C / ')
    extreme = reference[reference.age_value.gt(100)][METRICS].sum()
    nonbinary = reference[reference.SEXO.eq('2')][METRICS].sum()
    exact_profile = previous_profiles[previous_profiles.scheme.eq('exact')].iloc[0]
    lines = [
        '# Revisión de matrices candidatas para clustering · 2024', '',
        '## Resultado y recomendación provisional', '',
        'Se prepararon **cuatro matrices B de segmentos** y **dos matrices C de municipios**. '
        'Son escenarios experimentales: los intervalos se toman de la evaluación previa, no son '
        'grupos descubiertos ni rangos definitivos. Las matrices conservan todas sus observaciones, '
        'incluidas las que contienen NULL; no hay una selección automática para entrenamiento.', '',
        '**Para estudiar segmentos demográficos de participación, B permite conservar la identidad '
        'edad/sexo/municipio de cada segmento; para perfiles territoriales, C es la opción más directa.** '
        'B no representa personas individuales ni permite interpretar tipos de ciudadanos sin reconocer '
        'su carácter agregado. C agrupa potencialmente municipios mediante sus tasas por edad y sexo. '
        'Se propone contrastar C–Amplios frente a C–Etapas, sin elegir todavía uno definitivo.', '',
        table(['Matriz', 'Observaciones', 'Variables numéricas', 'Celdas NULL', 'Filas incompletas',
               'Filas completas', 'Soporte reducido', 'NS elevado', 'Completas con soporte', 'Completas con soporte y NS<10 %'],
              [[labels(r.matrix_id), number(r.observations), r.numeric_features, number(r.null_cells),
                number(r.incomplete_observations), number(r.complete_observations), number(r.low_support_observations),
                number(r.high_ns_observations), number(r.complete_strong), number(r.complete_strong_low_ns)] for r in summary.itertuples()]), '',
        'En B, soporte reducido y NS elevado describen el segmento. En C, señalan **al menos una '
        'coordenada** del perfil, no sólo el total municipal. Soporte reducido conserva el contrato '
        'LN<100, SV+NV<100 o filas fuente<5; NS elevado significa NS/LN≥10 %. No son criterios '
        'oficiales de validez o filtros. Las banderas se superponen.', '',
        image('matrix_coverage.png', 'Completitud y soporte por matriz'), '',
        '## Variables preparadas y significado', '',
        table(['Alternativa', 'Variable / conjunto', 'Definición y precaución'], [
            ['B', '`participation_observed`', 'SV/(SV+NV), tras sumar conteos del segmento; NULL si SV+NV=0.'],
            ['B', '`mean_age_nominal`', 'Σ(edad exacta × LN)/ΣLN del segmento, en años; no es el código, punto medio o límite del intervalo.'],
            ['B', '`rate_only`', 'Subconjunto experimental con la tasa sola: una única dimensión sólo separaría niveles de participación y no preservaría una distancia demográfica.'],
            ['B', '`rate_age`', 'Las dos variables anteriores, sin escalar. La edad puede dominar la distancia euclídea por su escala; se prepara para evaluación posterior, no se aplica K-Means directamente.'],
            ['C / broad', 'Seis tasas', '18–34, 35–59, 60–100 × Hombres/Mujeres.'],
            ['C / life_stage', 'Diez tasas', '18–29, 30–44, 45–59, 60–74, 75–100 × Hombres/Mujeres.'],
        ]), '',
        'Cada B guarda físicamente las dos columnas numéricas y declara ambos subconjuntos en '
        '`metadata/feature_contract.json`; no se duplican filas para rate_only. Los códigos SEXO, '
        'municipio, entidad, distrito y año no entran como magnitudes. `row_id` es una clave de '
        'alineación y debe retirarse al obtener el arreglo numérico. En B, sexo queda en metadatos: '
        'segmentos de sexos distintos pueden coincidir numéricamente si comparten edad media y tasa. '
        'Preservar su etiqueta no equivale a introducir su efecto en la distancia. Una futura '
        'codificación categórica o análisis por sexo necesita una decisión explícita.', '',
        'Los intervalos B se conservan completos, incluida 101+ cuando está separada; life_stage_open '
        'incluye toda la cola en 75+. La edad media y su DE nominal describen la distribución dentro '
        'del segmento; la DE y los extremos mínimo/máximo permanecen como metadatos. No se reemplaza '
        'ninguna edad exacta ni se presenta la media como edad individual.', '',
        'Las tasas C se llaman `participation_18_34_men`, `participation_18_34_women`, etc. '
        'El sexo y la edad identifican coordenadas del perfil sin codificar SEXO como número. '
        'Conteos, NS/LN, denominadores, tasas nominales, no participación y tamaño territorial '
        'quedan fuera de las variables candidatas, disponibles para diagnóstico y posibles '
        'alternativas futuras. No se fijan variables definitivas.', '',
        '## Referencias demográficas, cobertura y trazabilidad', '',
        f'Se leyeron solamente **{number(len(reference))} agregados de 2024**, que representan '
        f'{number(reference.source_row_count.sum())} filas fuente. Los cuatro escenarios se reutilizan '
        'desde `analysis/reports/representation_evaluation/grouped_candidates/`; sólo se calculan '
        'momentos de edad a partir de las edades exactas ya agregadas. No se releen los CSV ni '
        'los 54 millones de registros limpios. Los hashes leen archivos binarios sin interpretar filas.', '',
        f'Las edades >100 conservan {number(extreme.source_row_count)} filas fuente y LN='
        f'{number(extreme.LN)}; SEXO=2 conserva {number(nonbinary.source_row_count)} filas fuente, '
        f'LN={number(nonbinary.LN)}, SV={number(nonbinary.SV)}, NV={number(nonbinary.NV)} y '
        f'NS={number(nonbinary.NS)}. Ambos conjuntos se guardan en la referencia completa y su '
        'unión en `reference/complementary_2024.parquet`; la unión no duplica su intersección. '
        'No deben sumarse referencia completa y complementaria.', '',
        'C mantiene **todos los municipios**, sus totales de todas las edades y sexos, y sus '
        'referencias complementarias. Sus 6/10 coordenadas representan explícitamente H/M entre '
        '18 y 100; eso no elimina las otras observaciones de las referencias o totales. '
        'La categoría SEXO=2 no se convierte en cero ni se integra en H/M. La columna '
        '`complement_LN` cuantifica los conteos fuera del núcleo del perfil.', '',
        'Las claves territoriales se conservan como texto, junto con etiquetas y '
        '`district_reference_year`. La trazabilidad del agregado usa año/entidad/municipio/edad/sexo '
        'hacia la tabla descriptiva y, mediante las claves y manifiestos, hacia las filas con '
        'procedencia de la base limpia. No se inventa una única sección o archivo fuente para un '
        'agregado que suma varias secciones. La referencia exacta añade el intervalo asignado '
        'por cada escenario y banderas >100 / SEXO=2. No se supone continuidad territorial histórica.', '',
        '## Nulos y observaciones que requieren una decisión previa', '',
        '`can_use_complete_algorithms` es verdadero sólo si todas las variables de la fila son '
        'numéricas finitas. No certifica calidad de cobertura, suficiencia del denominador o '
        'idoneidad metodológica. `blocked_observations.parquet` enumera las filas incompletas con '
        'sus claves y conteos; esas mismas filas siguen en features.parquet y metadata.parquet. '
        'No se genera una matriz filtrada ni se imputa.', '',
        'En `cell_metadata.parquet`, C distingue `absent_combination` (combinación no observada, '
        'conteos NULL), `undefined_rate` (celda presente con SV+NV=0) y `defined`. No confundir '
        'una ausencia con conteos cero; las celdas presentes conservan ceros válidos. '
        'LN, SV, NV, NS, specified_count y banderas se conservan para cada coordenada y también '
        'como totales municipales separados. No sumar ambos niveles.', '',
        'Una futura decisión debe resolver esas filas antes de usar algoritmos que exijan matrices '
        'completas: no se propone convertir tasas desconocidas en abstención o participación cero. '
        'Cambiar a intervalos más amplios puede mejorar soporte, pero no recupera información '
        'cuando la participación municipal está enteramente no especificada.', '',
        '## Distribuciones y ponderaciones', '',
        'Los resúmenes usan inversa de la distribución empírica ponderada para cuartiles y DE '
        'descriptiva poblacional (ddof=0). Es una convención explícita, distinta de los cuantiles '
        'lineales de la auditoría; no es normalización estadística de las variables. Los nulos '
        'se omiten sólo del cálculo de cada resumen/correlación y se contabilizan con su peso '
        'faltante. Cada columna puede tener una base válida distinta.', '',
        table(['Matriz', 'Variable', 'Peso', 'n definido', 'Media', 'DE', 'Q1', 'Mediana', 'Q3'],
              [[labels(r.matrix_id), r.feature, r.weighting, number(r.valid_observations),
                f'{r.mean:.5f}', f'{r.std:.5f}', f'{r.q1:.5f}', f'{r.median:.5f}', f'{r.q3:.5f}']
               for r in distribution.itertuples() if r.weighting != 'equal_segment_weight']), '',
        image('profile_distributions.png', 'Distribuciones de las tasas municipales'), '',
        'Se comparan pesos **sin aplicarlos a modelos**. En C, peso uno por municipio responde '
        'a una pregunta territorial y peso LN municipal da más influencia a los territorios '
        'con mayor volumen nominal. Ponderar una tasa de coordenada por el LN municipal total '
        'no equivale a sumar sus SV y SV+NV ni produce automáticamente la tasa nacional de '
        'esa coordenada. LN tampoco corrige por sí mismo sesgos de captura o NS.', '',
        'En B se distingue peso uno por segmento, peso 1/n_segmentos del municipio '
        '(cada municipio aporta en total uno) y peso LN del segmento. Los pesos fraccionarios '
        'sólo describen un escenario de ponderación; no alteran conteos o variables. '
        'Si una tasa no está definida, su peso no se redistribuye a otras filas para construir '
        'la matriz; el resumen informa sólo su base válida.', '',
        table(['Matriz', 'Peso', 'Unidades equivalentes de concentración', '% peso de 10 municipios mayores',
               '% peso con fila incompleta', '% peso con soporte reducido', '% peso con NS elevado'],
              [[labels(r.matrix_id), r.weighting, f'{r.concentration_equivalent_units:.2f}', pct(r.top_10_municipal_weight_share),
                pct(r.incomplete_weight_share), pct(r.low_support_weight_share), pct(r.high_ns_weight_share)] for r in weights.itertuples()]), '',
        'La concentración equivalente = (Σw)²/Σw² es un diagnóstico del reparto de influencia, '
        'no tamaño muestral efectivo, incertidumbre o número de personas. La columna de diez '
        'municipios agrega sus pesos antes de ordenar; en B no se confunden segmentos con municipios.', '',
        'En C, los diez municipios de mayor peso concentran '
        f"{pct(weights.loc[weights.matrix_id.eq('c_broad') & weights.weighting.eq('nominal_weight'), 'top_10_municipal_weight_share'].iloc[0])} "
        'del peso con LN, frente a '
        f"{pct(weights.loc[weights.matrix_id.eq('c_broad') & weights.weighting.eq('equal_municipality_weight'), 'top_10_municipal_weight_share'].iloc[0])} "
        'con pesos municipales iguales. Esa diferencia cuantifica un cambio en el objetivo '
        'territorial o nominal, sin demostrar que una ponderación sea correcta para todos los usos.', '',
        image('weight_effects.png', 'Cambio de medias con pesos alternativos'), '',
        '## Correlaciones y redundancias', '',
        'Se calculan Pearson con cada ponderación y Spearman no ponderado sobre pares definidos, '
        'guardando n y peso de cada par en `metadata/correlations.csv`. Spearman se repite como '
        'referencia no ponderada y no cambia entre los escenarios de pesos. Las correlaciones '
        'de variables constantes son NULL. No se estiman p-valores ni causalidad. Una correlación '
        'alta no autoriza por sí misma a retirar una dimensión demográfica.', '',
    ]
    rows = []
    for matrix_id in summary.matrix_id:
        selected = correlations[correlations.matrix_id.eq(matrix_id) & correlations.scope.eq('features')
                                & correlations.left.ne(correlations.right)]
        for mode in ['equal_municipality_weight', 'nominal_weight']:
            current = selected[selected.weighting.eq(mode)].dropna(subset='pearson')
            if len(current):
                maximum = current.loc[current.pearson.abs().idxmax()]
                rows.append([labels(matrix_id), mode, maximum.left, maximum.right, f'{maximum.pearson:.5f}',
                             number(maximum.pair_observations), f'{maximum.spearman_unweighted:.5f}'])
    lines += [
        table(['Matriz', 'Peso', 'Variable 1', 'Variable 2', 'Pearson de mayor magnitud (con signo)', 'Pares definidos', 'Spearman sin pesos'], rows), '',
        image('profile_correlations.png', 'Correlaciones entre tasas de los perfiles'), '',
        table(['Relación comprobada', 'Máximo residuo absoluto entre los cuatro escenarios B'],
              [[name, f'{values.max_absolute_residual.max():.3g}'] for name, values in redundancy.groupby('identity')]), '',
        'LN=SV+NV+NS y specified_count=SV+NV son dependencias exactas de conteos; la '
        'no participación observada es 1−participación observada; participación nominal = '
        'participación observada × (1−NS/LN) donde está definida. Por eso no se incorporan '
        'simultáneamente todos esos indicadores a las matrices candidatas. Los conteos grandes '
        'también podrían orientar una distancia hacia tamaño territorial. El archivo de '
        'correlaciones incluye esos metadatos como diagnóstico separado, sin convertirlos '
        'en variables de entrenamiento.', '',
        'C mantiene tasas correlacionadas porque cada coordenada conserva edad/sexo; repetir '
        'tasas agregadas, brechas derivadas o variables complementarias puede contar varias '
        'veces información similar. B con dos variables conserva una edad resumen, pero aún '
        'pierde variación dentro de los intervalos. Los espacios numéricos siguientes muestran '
        'frecuencias observadas, sin modelos o interpretación de perfiles.', '',
        image('segment_feature_space.png', 'Frecuencias en el espacio de variables B'), '',
        'K-Means permite pesos por observación; esos pesos no resuelven automáticamente diferencias '
        'de fiabilidad entre coordenadas de C. Su geometría exige evaluar escalas, redundancia '
        'y significado de las variables antes de ajustar. No se fijan pesos, K ni modelos. '
        '[Documentación primaria de KMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html).', '',
        '## Viabilidad de curvas de participación por edad', '',
        f'La referencia cruda 18–100 × H/M implica 166 tasas por municipio. La evaluación previa '
        f'en 2024 encontró {number(exact_profile.absent_cells)} combinaciones ausentes, '
        f'{number(exact_profile.undefined_present_cells)} tasas presentes no definidas y '
        f'{number(exact_profile.low_support_present_cells)} celdas de soporte reducido; '
        f'sólo {number(exact_profile.complete_defined)} municipios tienen las 166 tasas '
        f'definidas y {number(exact_profile.complete_strong)} tienen soporte suficiente en todas. '
        'Una curva cruda no resuelve la escasez; el tamaño de una matriz 2,477×166 float64 '
        '(aproximadamente 3.14 MiB) no es aquí el principal obstáculo.', '',
        image('exact_age_support.png', 'Soporte municipal por edad exacta'), '',
        'Una futura representación funcional podría aproximar cada trayectoria H/M con una base '
        'suave de menor dimensión y conservar más detalle que intervalos fijos. Es una propuesta '
        'pendiente: necesitaría definir pesos por denominador, tratamiento de NS, complejidad '
        'y validación del suavizado, continuidad, límites de [0,1] y conducta ante huecos y '
        'edades extremas. Ajustar o interpolar curvas añadiría supuestos y no recuperaría '
        'información en municipios completamente no especificados. SEXO=2 requiere revisión '
        'separada por su escasez.', '',
        'Como referencia conceptual, las splines de suavizado ponderadas permiten regular el '
        'compromiso entre ajuste y suavidad; su definición no garantiza que una tasa estimada '
        'quede en [0,1]. No se implementa suavizado, interpolación, bases funcionales ni '
        'reducción de dimensión en esta entrega. '
        '[Definición primaria de smoothing spline](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.make_smoothing_spline.html).', '',
        '## Estructura, validaciones y reproducción', '',
        f'Destino: `{output.relative_to(root).as_posix()}/`.', '',
        table(['Archivo / directorio', 'Contenido'], [
            ['matrices/b_SCHEME/features.parquet', 'row_id y dos variables numéricas crudas; rate_only es un subconjunto declarado.'],
            ['matrices/c_SCHEME/features.parquet', 'row_id y 6/10 tasas por intervalo y sexo.'],
            ['matrices/*/metadata.parquet', 'Identificadores, conteos, denominadores, banderas, estado de completitud y pesos candidatos.'],
            ['matrices/c_SCHEME/cell_metadata.parquet', 'Conteos, denominadores y estado por coordenada esperada, sin completar ausentes con cero.'],
            ['matrices/*/blocked_observations.parquet', 'Listado de filas que requieren resolver NULL o valores no finitos; no se retiran de las matrices.'],
            ['reference/exact_age_2024.parquet', 'Todos los agregados exactos de 2024, con enlace a cada esquema experimental.'],
            ['reference/complementary_2024.parquet', 'Unión EDAD>100 o SEXO=2, sin duplicar intersección.'],
            ['metadata/', 'Contrato, calidad, distribuciones, correlaciones, pesos, soporte de curvas, conciliación y manifiesto.'],
        ]), '',
        'Los identificadores row_id deben unirse uno a uno con metadatos. Para leer una matriz '
        'numérica, seleccionar exclusivamente feature_columns del contrato: no convertir '
        'row_id, SEXO, claves o banderas en números. El contrato separa columnas de '
        'características y pesos; no hay llamadas automáticas a algoritmos.', '',
        f'Se verificaron {number(len(summary)*32)} controles matriz–entidad de los siete conteos '
        'aditivos contra los descriptivos de 2024, además de conciliación por municipio en B y '
        'referencia exacta. Cada matriz conserva por separado LN, SV, NV, NS, filas fuente y '
        'las métricas de SEXO=2. Los núcleos C se concilian con sus celdas presentes, '
        'y sus totales municipales con todas las categorías. Las matrices son vistas alternativas '
        'y no deben sumarse entre sí.', '',
        'Se comprobaron claves únicas, alineación por row_id, tipos numéricos de variables, '
        'claves territoriales de texto, LN=SV+NV+NS, denominadores, tasas NULL correctas, '
        'igualdad tras escribir/releer Parquet y coincidencia de los recuentos C con la evaluación '
        f'previa. Los hashes de {number(protected_count)} archivos existentes se contrastaron '
        'antes y después. `_SUCCESS` sólo se genera tras completar todas las validaciones. '
        'Una incidencia queda en el manifiesto con estado failed y sin ese marcador.', '',
        'Las gráficas son diagnósticos, con porcentajes en los ejes y colores logarítmicos de '
        'frecuencia cuando se indica. Eso no transforma los Parquet. No se modificaron fuentes, '
        'Parquet previos, informes previos o src/; no se eliminaron registros, imputaron tasas, '
        'normalizaron variables, ajustaron modelos, seleccionó K o crearon commits.', '',
        'Reproducir desde la raíz:', '', '```powershell',
        '.venv/Scripts/python.exe analysis/scripts/build_cluster_features.py', '```', '',
        'Los destinos existentes se protegen. Para otra ejecución, elegir rutas nuevas con '
        '`--output`, `--charts` y `--report`; `--batch-size` controla la lectura de los agregados.', '',
        '## Decisiones pendientes', '',
        'Decidir el objetivo (segmentos demográficos o municipios), comparar rangos amplios y '
        'etapas sin fijarlos aún, resolver la entrada incompleta, separar cobertura de conducta, '
        'acordar el papel de edad y sexo en la distancia B, y elegir la ponderación territorial '
        'o nominal. Después se podrá evaluar una normalización explícita, distancia/enlace y '
        'estabilidad de modelos. Las edades extremas y SEXO=2 se conservan para sensibilidad '
        'y validación documental; el límite gráfico 100 no se convierte en filtro definitivo. '
        'Las curvas requieren una evaluación metodológica y autorización de modelado adicional. '
        'No se decide ni interpreta ningún cluster en este informe.', '',
    ]
    report.write_text('\n'.join(lines), encoding='utf-8')


def snapshot_inputs(root, output, charts):
    """Protege fuentes existentes y comprueba manifiestos antes de leer tablas."""
    protected = {}
    for directory in [root/'data/raw', root/'data/processed', root/'analysis/charts', root/'analysis/reports']:
        for path in directory.rglob('*'):
            if path.is_file() and not path.is_relative_to(output) and not path.is_relative_to(charts):
                protected[str(path)] = file_hash(path)
    source = root/'data/processed/descriptive'
    manifest_path = source/'metadata/run_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    success = json.loads((source/'_SUCCESS').read_text(encoding='utf-8'))
    require(manifest['status'] == 'validated' and success['manifest_sha256'] == file_hash(manifest_path), 'Descriptivos no validados.')
    for item in manifest['files']:
        require(protected[str(source/item['path'])] == item['sha256'], f"Descriptivo alterado: {item['path']}")
    evaluation = root/'analysis/reports/representation_evaluation'
    previous = json.loads((evaluation/'run_manifest.json').read_text(encoding='utf-8'))
    require(previous['status'] == 'validated', 'Escenarios previos no validados.')
    require(file_hash(root/'analysis/reports/clustering_representation.md') == previous['report_sha256'], 'Informe previo alterado.')
    for relative, digest in previous['output_hashes'].items():
        require(protected[str(root/relative)] == digest, f'Escenario previo alterado: {relative}')
    for relative in REPORT_INPUTS: require((root/relative).exists(), f'Informe requerido ausente: {relative}')
    return protected


def build_features(root, output, charts, report, batch_size=100_000):
    root, output, charts, report = [Path(path).resolve() for path in [root, output, charts, report]]
    require(output.is_relative_to(root/'data/processed') and charts.is_relative_to(root/'analysis/charts')
            and report.is_relative_to(root/'analysis/reports'), 'Destinos fuera de las áreas de análisis autorizadas.')
    require(not output.exists() and not charts.exists() and not report.exists(), 'Elegir rutas nuevas; no se sobrescriben resultados.')
    require(batch_size > 0, 'batch-size debe ser positivo.')
    protected = snapshot_inputs(root, output, charts)
    source = root/'data/processed/descriptive'
    evaluation = root/'analysis/reports/representation_evaluation'
    thresholds = json.loads((source/'metadata/table_contract.json').read_text(encoding='utf-8'))['thresholds']
    output.mkdir(parents=True); charts.mkdir(parents=True); (output/'metadata').mkdir()
    report.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    manifest = dict(status='running', errors=[], election_year=YEAR, batch_size=batch_size,
        thresholds=thresholds, protected_hashes=protected, age_schemes=AGE_SCHEMES,
        started_at_utc=datetime.now(timezone.utc).isoformat(),
        versions=dict(python=platform.python_version(), pandas=pd.__version__, numpy=np.__version__,
                      pyarrow=pa.__version__, matplotlib=matplotlib.__version__))
    save_json(output/'metadata/run_manifest.json', manifest)
    try:
        municipalities = pd.read_parquet(source/'municipality/table.parquet').query('election_year == @YEAR').reset_index(drop=True)
        states = pd.read_parquet(source/'state/table.parquet').query('election_year == @YEAR')
        annual = pd.read_parquet(source/'year/table.parquet').query('election_year == @YEAR')
        dataset = ds.dataset(source/'municipality_age_sex', format='parquet')
        reference = pd.concat([batch.to_pandas() for batch in dataset.scanner(
            filter=ds.field('election_year') == YEAR, batch_size=batch_size).to_batches() if batch.num_rows], ignore_index=True)
        validate_table(reference, [*MUNICIPAL_KEYS, 'age_value', 'SEXO'])
        compare_sums(reference, municipalities, MUNICIPAL_KEYS)
        require(set(reference.SEXO) <= {'0', '1', '2'}, 'Categoría SEXO no documentada.')
        require(int(reference.sex_2_source_rows.sum()) == int(reference.sex_2_nominal_count.sum()) == 105, 'SEXO=2 no conciliado.')
        reference['age_over_100'] = reference.age_value.gt(100)
        reference['is_sex_2'] = reference.SEXO.eq('2')
        for scheme in AGE_SCHEMES: reference[f'age_band_{scheme}'] = assign_bands(reference.age_value, scheme)
        save_table(output/'reference/exact_age_2024.parquet', reference)
        save_table(output/'reference/complementary_2024.parquet', reference[reference.age_over_100 | reference.is_sex_2])
        summaries, distributions, correlations, weight_summaries, redundancies, reconciliations = [], [], [], [], [], []
        matrices, contracts = {}, {}
        for scheme in AGE_SCHEMES:
            grouped = pd.read_parquet(evaluation/f'grouped_candidates/{scheme}/part-2024.parquet')
            validate_table(grouped, BAND_KEYS)
            compare_sums(grouped, reference, MUNICIPAL_KEYS)
            features, metadata = build_segments(grouped, reference, municipalities, scheme)
            matrix_id = 'b_'+scheme
            matrices[matrix_id] = (features, metadata)
            contracts[matrix_id] = dict(alternative='B', scheme=scheme, feature_columns=B_FEATURES,
                feature_sets=dict(rate_only=['participation_observed'], rate_age=B_FEATURES),
                key_columns=BAND_KEYS, includes_over_100=True, includes_sex_2=True,
                weight_columns=['equal_segment_weight', 'equal_municipality_weight', 'nominal_weight'])
            for check in redundancy_checks(grouped): redundancies.append(dict(matrix_id=matrix_id, **check))
            if scheme in PROFILE_SCHEMES:
                features, metadata, cells = build_profiles(grouped, municipalities, scheme)
                matrix_id = 'c_'+scheme
                matrices[matrix_id] = (features, metadata)
                contracts[matrix_id] = dict(alternative='C', scheme=scheme,
                    feature_columns=profile_feature_names(scheme), feature_sets=dict(age_sex_rates=profile_feature_names(scheme)),
                    key_columns=MUNICIPAL_KEYS, core_sex_categories=['0', '1'], core_age_range=[18, 100],
                    complementary_reference='reference/complementary_2024.parquet',
                    weight_columns=['equal_municipality_weight', 'nominal_weight'])
                save_table(output/f'matrices/{matrix_id}/cell_metadata.parquet', cells)
            print(f'{scheme}: segmentos conservados y perfil candidato preparado cuando corresponde.', flush=True)
        for matrix_id, (features, metadata) in matrices.items():
            alternative = contracts[matrix_id]['alternative']
            result = diagnostic_tables(matrix_id, features, metadata, alternative)
            summary, distribution, correlation, weights = result
            summaries.append(summary); distributions.extend(distribution); correlations.extend(correlation); weight_summaries.extend(weights)
            save_table(output/f'matrices/{matrix_id}/features.parquet', features)
            save_table(output/f'matrices/{matrix_id}/metadata.parquet', metadata)
            save_table(output/f'matrices/{matrix_id}/blocked_observations.parquet', metadata[~metadata.can_use_complete_algorithms])
            compare_sums(metadata, states, ['election_year', 'EDOCVE'])
            compare_sums(metadata, annual, ['election_year'])
            for state, frame in metadata.groupby('EDOCVE', observed=True):
                baseline = states[states.EDOCVE.eq(state)].iloc[0]
                reconciliations.append(dict(matrix_id=matrix_id, EDOCVE=state,
                    **{f'{metric}_difference': int(frame[metric].sum())-int(baseline[metric]) for metric in METRICS}))
            require(not features.row_id.duplicated().any() and features.row_id.equals(metadata.row_id), 'Alineación o identidad de matriz incorrecta.')
            require(all(pd.api.types.is_numeric_dtype(features[column]) for column in contracts[matrix_id]['feature_columns']), 'Variable no numérica en matriz.')
        summary = pd.DataFrame(summaries)
        distribution = pd.DataFrame(distributions)
        correlation = pd.DataFrame(correlations)
        weights = pd.DataFrame(weight_summaries)
        redundancy = pd.DataFrame(redundancies)
        reconciliation = pd.DataFrame(reconciliations)
        curves = curve_diagnostics(reference, municipalities)
        previous_profiles = pd.read_csv(evaluation/'profile_summary.csv').query('election_year == @YEAR')
        for scheme in PROFILE_SCHEMES:
            current = summary[summary.matrix_id.eq('c_'+scheme)].iloc[0]
            previous = previous_profiles[previous_profiles.scheme.eq(scheme)].iloc[0]
            require(current.complete_observations == previous.complete_defined and current.complete_strong == previous.complete_strong
                    and current.complete_strong_low_ns == previous.complete_strong_low_ns, 'Perfil C no coincide con la evaluación anterior.')
        require(reconciliation.filter(like='_difference').eq(0).all().all(), 'Conciliación estatal fallida.')
        require(redundancy.max_absolute_residual.le(1e-12).all(), 'Redundancia algebraica no verificada.')
        for name, frame in [('matrix_quality.csv', summary), ('feature_distributions.csv', distribution),
            ('correlations.csv', correlation), ('weight_sensitivity.csv', weights), ('redundancy_checks.csv', redundancy),
            ('state_reconciliation.csv', reconciliation), ('curve_age_support.csv', curves)]:
            save_table(output/'metadata'/name, frame)
        contract = dict(version='1.0', election_year=YEAR, matrices=contracts,
            row_identity='row_id es sólo una clave de unión, nunca una variable de distancia.',
            null_policy='NULL no se sustituye por cero; can_use_complete_algorithms sólo señala completitud numérica.',
            input_reference='data/processed/descriptive/municipality_age_sex; procedencia mediante año/entidad/municipio/edad/sexo y manifiestos.',
            count_policy='Cada matriz es una vista alternativa; no sumar matrices, metadatos y celdas entre sí.',
            scale_policy='Proporciones originales y edades en años; sin normalización estadística.',
            weighted_quantile_policy='Inversa de la distribución empírica ponderada; DE descriptiva poblacional (ddof=0).')
        save_json(output/'metadata/feature_contract.json', contract)
        plot_diagnostics(charts, matrices, summary, distribution, correlation, curves)
        write_report(root, output, charts, report, summary, distribution, correlation, weights, redundancy,
                     previous_profiles, reference, curves, len(protected))
        for path, digest in protected.items(): require(file_hash(path) == digest, f'Archivo existente modificado: {path}')
        manifest.update(status='validated', seconds=round(time.monotonic()-started, 2),
            finished_at_utc=datetime.now(timezone.utc).isoformat(), script_sha256=file_hash(Path(__file__)),
            read_aggregate_groups=len(reference), source_rows_2024=int(reference.source_row_count.sum()),
            matrix_count=len(matrices), state_reconciliations=len(reconciliation), protected_files=len(protected),
            artifact_hashes={str(path.relative_to(root)): file_hash(path) for directory in [output, charts]
                for path in directory.rglob('*') if path.is_file() and path != output/'metadata/run_manifest.json'},
            report_sha256=file_hash(report))
        save_json(output/'metadata/run_manifest.json', manifest)
        save_json(output/'_SUCCESS', dict(manifest_sha256=file_hash(output/'metadata/run_manifest.json')))
        print(f'VALIDADO: {len(matrices)} matrices candidatas; {len(reference):,} agregados de 2024; {report.relative_to(root)}', flush=True)
        return manifest
    except Exception as error:
        manifest['status'] = 'failed'
        manifest['errors'].append(dict(type=type(error).__name__, message=str(error)))
        save_json(output/'metadata/run_manifest.json', manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, default=Path('data/processed/cluster_features'))
    parser.add_argument('--charts', type=Path, default=Path('analysis/charts/cluster_features'))
    parser.add_argument('--report', type=Path, default=Path('analysis/reports/cluster_feature_review.md'))
    parser.add_argument('--batch-size', type=int, default=100_000)
    args = parser.parse_args()
    root = args.root.resolve()
    destinations = [path if path.is_absolute() else root/path for path in [args.output, args.charts, args.report]]
    build_features(root, *destinations, args.batch_size)


if __name__ == '__main__':
    main()
