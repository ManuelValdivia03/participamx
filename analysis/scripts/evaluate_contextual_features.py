"""Evalúa cobertura y contexto de sección electoral, sin ajustar modelos.

Lee sólo Parquet validado de 2024 por bloques. Los criterios son diagnósticos;
ninguna fila se elimina de las referencias y ninguna tasa NULL se imputa.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from itertools import product
import json
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from clean_data import require, file_hash, save_json, open_dataset
from build_cluster_features import snapshot_inputs, save_table, make_ids
from build_descriptive import METRICS, SOURCE_COUNTS, compare_sums, markdown_table, pct
from evaluate_representation import assign_bands, band_labels

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

MUNICIPAL_KEYS = ['EDOCVE', 'MPIOCVE']
EXACT_KEYS = [*MUNICIPAL_KEYS, 'age_value', 'SEXO']
BAND_KEYS = [*MUNICIPAL_KEYS, 'age_band', 'SEXO']
TYPES = ['U', 'R', 'M']
SCHEMES = ['life_stage', 'broad']
REPORT_INPUTS = ['exact_age_clustering_review.md', 'demographic_representation_comparison.md',
                 'cluster_feature_review.md', 'clustering_methods_review.md']


def ratio(numerator, denominator):
    """La falta de denominador produce NULL, incluso en las composiciones."""
    numerator, denominator = np.asarray(numerator, float), np.asarray(denominator, float)
    return np.divide(numerator, denominator, out=np.full(numerator.shape, np.nan), where=denominator > 0)


def grouped(frame, keys):
    return frame.groupby(keys, observed=True, sort=False, dropna=False, as_index=False)[METRICS].sum()


def indicators(frame):
    result = frame.copy()
    require(result.LN.eq(result.SV + result.NV + result.NS).all(), 'Identidad de conteos incorrecta.')
    result['specified_count'] = result.SV + result.NV
    result['participation_observed'] = ratio(result.SV, result.specified_count)
    result['unspecified_rate'] = ratio(result.NS, result.LN)
    result['has_low_support'] = result.LN.lt(100) | result.specified_count.lt(100) | result.source_row_count.lt(5)
    result['has_high_unspecified_rate'] = result.unspecified_rate.ge(.1)
    return result


def exclusion_audit(exact, municipalities):
    """Separa criterios marginales, condicionales y causas municipales exclusivas."""
    core = exact[exact.age_value.between(18, 100)].copy()
    core['ln_ok'] = core.LN.ge(100)
    core['specified_ok'] = (core.SV + core.NV).ge(100)
    core['source_rows_ok'] = core.source_row_count.ge(5)
    core['is_eligible'] = core.ln_ok & core.specified_ok & core.source_rows_ok
    truth = core.groupby(['ln_ok', 'specified_ok', 'source_rows_ok'], as_index=False).agg(
        segments=('LN', 'size'), LN=('LN', 'sum'), SV=('SV', 'sum'), NV=('NV', 'sum'), NS=('NS', 'sum'))
    scenarios = []
    for use_ln, use_specified, use_rows in product([False, True], repeat=3):
        mask = (core.SV + core.NV).gt(0)
        for enabled, column in [(use_ln, 'ln_ok'), (use_specified, 'specified_ok'), (use_rows, 'source_rows_ok')]:
            if enabled:
                mask &= core[column]
        selected = core[mask]
        scenarios.append(dict(require_ln=use_ln, require_specified=use_specified, require_source_rows=use_rows,
            segments=len(selected), municipalities=selected.groupby(MUNICIPAL_KEYS).ngroups, LN=int(selected.LN.sum())))
    totals = core.groupby(MUNICIPAL_KEYS, as_index=False).agg(
        scope_specified_count=('specified_count', 'sum'), ln_supported_segments=('ln_ok', 'sum'),
        count_supported_segments=('specified_ok', 'sum'), eligible_segments=('is_eligible', 'sum'),
        maximum_source_rows=('source_row_count', 'max'))
    supported = core[core.specified_ok].groupby(MUNICIPAL_KEYS, as_index=False).agg(
        count_supported_LN=('LN', 'sum'), count_supported_source_max=('source_row_count', 'max'),
        count_supported_source_min=('source_row_count', 'min'))
    result = municipalities.merge(totals, on=MUNICIPAL_KEYS, validate='one_to_one').merge(
        supported, on=MUNICIPAL_KEYS, how='left', validate='one_to_one')
    result['exclusion_reason'] = np.select([
        result.eligible_segments.gt(0), result.scope_specified_count.eq(0),
        result.count_supported_segments.gt(0), result.ln_supported_segments.gt(0)],
        ['has_eligible_segments', 'all_unspecified', 'source_rows_only', 'specified_count_only_after_ln'],
        default='no_segment_reaches_ln')
    return core, truth, pd.DataFrame(scenarios), result


def aggregate_state(batches):
    """Acumula una entidad; deduplica secciones entre bloques y edades.

    source_row_count cuenta celdas; section_count cuenta claves de sección.
    Se mantiene por separado la marginal exacta para conciliar con la referencia.
    """
    exact_parts, sections = [], []
    sums = {scheme: [] for scheme in SCHEMES}
    section_parts = {scheme: [] for scheme in SCHEMES}
    for batch in batches:
        if not batch.num_rows:
            continue
        frame = batch.to_pandas().rename(columns=SOURCE_COUNTS)
        require(frame.TIPOSEC.notna().all() and set(frame.TIPOSEC) <= set(TYPES), 'TIPOSEC desconocido o NULL.')
        require(set(frame.SEXO) <= {'0', '1', '2'}, 'SEXO desconocido.')
        require(frame.election_year.eq(2024).all(), 'Lectura fuera de 2024.')
        require(frame.state_code.eq(frame.EDOCVE).all(), 'Partición y entidad distintas.')
        frame['source_row_count'] = 1
        frame['sex_2_source_rows'] = frame.SEXO.eq('2').astype('int64')
        frame['sex_2_nominal_count'] = np.where(frame.SEXO.eq('2'), frame.LN, 0)
        require(frame.LN.eq(frame.SV + frame.NV + frame.NS).all(), 'Conteos fuente no conciliados.')
        exact_parts.append(grouped(frame, EXACT_KEYS))
        sections.append(frame[[*MUNICIPAL_KEYS, 'SECCION', 'TIPOSEC']].drop_duplicates())
        for scheme in SCHEMES:
            work = frame.assign(age_band=assign_bands(frame.age_value, scheme))
            sums[scheme].append(grouped(work, [*BAND_KEYS, 'TIPOSEC']))
            section_parts[scheme].append(work[[*BAND_KEYS, 'TIPOSEC', 'SECCION']].drop_duplicates())
        # La reducción periódica acota memoria sin contar dos veces una sección.
        if len(exact_parts) >= 8:
            exact_parts = [grouped(pd.concat(exact_parts, ignore_index=True), EXACT_KEYS)]
            sections = [pd.concat(sections, ignore_index=True).drop_duplicates()]
            for scheme in SCHEMES:
                sums[scheme] = [grouped(pd.concat(sums[scheme], ignore_index=True), [*BAND_KEYS, 'TIPOSEC'])]
                section_parts[scheme] = [pd.concat(section_parts[scheme], ignore_index=True).drop_duplicates()]
    require(bool(exact_parts), 'Entidad sin filas.')
    inventory = pd.concat(sections, ignore_index=True).drop_duplicates()
    require(not inventory.duplicated([*MUNICIPAL_KEYS, 'SECCION']).any(), 'Sección con tipos incompatibles.')
    result = {}
    for scheme in SCHEMES:
        distinct = pd.concat(section_parts[scheme], ignore_index=True).drop_duplicates()
        distinct = distinct.groupby([*BAND_KEYS, 'TIPOSEC'], observed=True, as_index=False).size().rename(columns={'size': 'section_count'})
        result[scheme] = grouped(pd.concat(sums[scheme], ignore_index=True), [*BAND_KEYS, 'TIPOSEC']).merge(
            distinct, on=[*BAND_KEYS, 'TIPOSEC'], validate='one_to_one')
    return result, grouped(pd.concat(exact_parts, ignore_index=True), EXACT_KEYS), inventory


def build_context_segments(children, original, scheme):
    """Añade composición nominal sin exigir tasas definidas en tipos ausentes."""
    compare_sums(children, original, BAND_KEYS)
    parent = original.copy()
    if 'is_training' in parent:
        parent = parent.drop(columns='is_training')
    for section_type in TYPES:
        component = children[children.TIPOSEC.eq(section_type)][[*BAND_KEYS, *METRICS, 'section_count']]
        component = component.rename(columns={field: f'{field}_{section_type}' for field in [*METRICS, 'section_count']})
        parent = parent.merge(component, on=BAND_KEYS, how='left', validate='one_to_one', indicator='_presence')
        parent[f'has_section_type_{section_type}'] = parent._presence.eq('both')
        # Ceros sólo para sumas de subconjuntos vacíos de un universo exhaustivo U/R/M.
        # No se crean tasas por tipo ni observaciones fuente.
        for field in [*METRICS, 'section_count']:
            parent[f'{field}_{section_type}'] = parent[f'{field}_{section_type}'].fillna(0).astype('int64')
        parent = parent.drop(columns='_presence')
        parent[f'section_ln_share_{section_type}'] = ratio(parent[f'LN_{section_type}'], parent.LN)
    require(parent.LN.eq(parent[[f'LN_{t}' for t in TYPES]].sum(axis=1)).all(), 'Composición no exhaustiva.')
    shares = parent[[f'section_ln_share_{t}' for t in TYPES]]
    require(np.allclose(shares.sum(axis=1), 1.), 'Las proporciones de contexto no suman uno.')
    parent['section_count'] = parent[[f'section_count_{t}' for t in TYPES]].sum(axis=1)
    parent['section_types_present'] = parent[[f'has_section_type_{t}' for t in TYPES]].sum(axis=1)
    parent['in_scope'] = parent.age_band.ne('101+')
    parent['is_eligible'] = parent.in_scope & ~parent.has_low_support & np.isfinite(parent.participation_observed)
    parent['context_is_eligible'] = parent.is_eligible & np.isfinite(shares.to_numpy()).all(axis=1)
    parent['pending_reason_context'] = np.select([~parent.in_scope, parent.specified_count.eq(0), parent.has_low_support],
        ['age_over_100_complementary', 'undefined_rate', 'low_support'], default='eligible')
    parent['scheme'] = scheme
    require(parent.is_eligible.eq(parent.context_is_eligible).all(), 'La composición introduce faltantes no previstos.')
    if 'is_eligible' in original:
        previous = original.set_index(BAND_KEYS).is_eligible.sort_index()
        require(parent.set_index(BAND_KEYS).is_eligible.sort_index().equals(previous), 'Se modificó elegibilidad previa.')
    return parent


def profile_review(children, parents, municipalities, scheme, split_types):
    """Rejilla territorial: ausencia, tasa no definida y soporte no se confunden."""
    bands = [band for band in band_labels(scheme) if band != '101+']
    dimensions = [dict(age_band=band, SEXO=sex, **({'TIPOSEC': t} if split_types else {}))
        for band in bands for sex in ['0', '1'] for t in (TYPES if split_types else ['all'])]
    dimension_keys = ['age_band', 'SEXO'] + (['TIPOSEC'] if split_types else [])
    source = children if split_types else parents
    base = municipalities[MUNICIPAL_KEYS].merge(pd.DataFrame(dimensions), how='cross')
    keep = [*METRICS, 'specified_count', 'participation_observed', 'unspecified_rate', 'has_low_support', 'section_count']
    cells = base.merge(source[[*MUNICIPAL_KEYS, *dimension_keys, *keep]], on=[*MUNICIPAL_KEYS, *dimension_keys],
        how='left', validate='one_to_one', indicator=True)
    cells['is_present'] = cells._merge.eq('both')
    cells['cell_status'] = np.select([~cells.is_present, cells.specified_count.eq(0)],
        ['absent_combination', 'undefined_rate'], default='defined')
    cells['is_supported'] = cells.is_present & cells.specified_count.gt(0) & cells.has_low_support.eq(False)
    cells['is_defined'] = cells.cell_status.eq('defined')
    cells['has_high_ns'] = cells.unspecified_rate.ge(.1)
    cells['has_few_sections'] = cells.section_count.lt(5) & cells.is_present
    cells['feature_name'] = cells[dimension_keys].astype(str).agg('|'.join, axis=1)
    cells = cells.drop(columns='_merge')
    status = cells.groupby(MUNICIPAL_KEYS, as_index=False).agg(
        expected_cells=('is_present', 'size'), present_cells=('is_present', 'sum'),
        defined_cells=('is_defined', 'sum'), supported_cells=('is_supported', 'sum'),
        high_ns_cells=('has_high_ns', 'sum'), few_section_cells=('has_few_sections', 'sum'))
    status = municipalities.merge(status, on=MUNICIPAL_KEYS, validate='one_to_one')
    status['is_eligible'] = status.supported_cells.eq(len(dimensions))
    status['is_complete'] = status.defined_cells.eq(len(dimensions))
    status['is_complete_low_ns'] = status.is_eligible & status.high_ns_cells.eq(0)
    values = cells.pivot(index=MUNICIPAL_KEYS, columns='feature_name', values='participation_observed').reset_index()
    values.columns.name = None
    return cells, status, values


def quality_row(name, frame, eligible, nominal_total, profile=False, expected_cells=None):
    selected = frame[eligible]
    rates = frame.unspecified_rate
    return dict(alternative=name, unit='municipality' if profile else 'segment', observations=len(frame),
        municipalities=frame.groupby(MUNICIPAL_KEYS).ngroups, LN=int(frame.LN.sum()),
        eligible_observations=len(selected), eligible_municipalities=selected.groupby(MUNICIPAL_KEYS).ngroups,
        eligible_LN=int(selected.LN.sum()), eligible_nominal_fraction=selected.LN.sum()/nominal_total,
        undefined_rates=int(frame.participation_observed.isna().sum()),
        high_ns_observations=int(rates.ge(.1).sum()), ns_q1=rates.quantile(.25),
        ns_median=rates.median(), ns_q3=rates.quantile(.75), ns_nominal=frame.NS.sum()/frame.LN.sum(),
        LN_q1=frame.LN.quantile(.25), LN_median=frame.LN.median(), LN_q3=frame.LN.quantile(.75),
        specified_q1=frame.specified_count.quantile(.25), specified_median=frame.specified_count.median(),
        specified_q3=frame.specified_count.quantile(.75), eligible_high_ns=int(selected.unspecified_rate.ge(.1).sum()),
        eligible_ns_nominal=selected.NS.sum()/selected.LN.sum() if len(selected) else np.nan,
        expected_profile_cells=expected_cells)


def state_coverage(name, frame, eligible, states):
    selected = frame[eligible]
    result = states[['EDOCVE', 'state_name_label', 'LN']].rename(columns={'LN': 'state_LN'}).copy()
    full = frame.groupby('EDOCVE').agg(available_observations=('LN', 'size'))
    chosen = selected.groupby('EDOCVE').agg(eligible_observations=('LN', 'size'), eligible_LN=('LN', 'sum'))
    municipal = selected[MUNICIPAL_KEYS].drop_duplicates().groupby('EDOCVE').size().rename('eligible_municipalities')
    available = frame[MUNICIPAL_KEYS].drop_duplicates().groupby('EDOCVE').size().rename('available_municipalities')
    result = result.join(full, on='EDOCVE').join(chosen, on='EDOCVE').join(municipal, on='EDOCVE').join(available, on='EDOCVE')
    for column in ['available_observations', 'eligible_observations', 'eligible_LN', 'eligible_municipalities']:
        result[column] = result[column].fillna(0).astype('int64')
    result['eligible_nominal_fraction'] = result.eligible_LN/result.state_LN
    result['eligible_municipality_fraction'] = result.eligible_municipalities/result.available_municipalities
    result['alternative'] = name
    return result


def numeric_diagnostics(parent, scheme):
    """Distribuciones, dependencia composicional y asociación descriptiva, sin modelos."""
    frame = parent[parent.context_is_eligible]
    fields = ['participation_observed', 'participation_deviation_national', *[f'section_ln_share_{t}' for t in TYPES]]
    rows, correlations = [], []
    for field in fields:
        values = frame[field]
        rows.append(dict(scheme=scheme, variable=field, n=len(values), mean=values.mean(), sd=values.std(ddof=0),
            minimum=values.min(), q1=values.quantile(.25), median=values.median(), q3=values.quantile(.75), maximum=values.max()))
    for i, first in enumerate(fields):
        for second in fields[i+1:]:
            correlations.append(dict(scheme=scheme, first=first, second=second, n=len(frame),
                pearson=frame[first].corr(frame[second]), spearman=frame[first].rank().corr(frame[second].rank())))
    # Constancia del contexto dentro del municipio: mide cuánto se repite entre segmentos.
    ranges = frame.groupby(MUNICIPAL_KEYS)[[f'section_ln_share_{t}' for t in TYPES]].agg(lambda value: value.max()-value.min())
    spread = pd.DataFrame([dict(scheme=scheme, section_type=t,
        median_within_municipality_range=ranges[f'section_ln_share_{t}'].median(),
        p95_within_municipality_range=ranges[f'section_ln_share_{t}'].quantile(.95)) for t in TYPES])
    return pd.DataFrame(rows), pd.DataFrame(correlations), spread


def plot_diagnostics(charts, quality, exclusions, truth, national, parents, profiles, state_table):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    selected = quality[quality.alternative.isin(['exact_age', 'life_stage_previous', 'life_stage_context',
        'life_stage_split_type', 'broad_context', 'broad_split_type'])]
    x = np.arange(len(selected))
    axes[0].barh(x, selected.eligible_municipalities/2477, color='#267c83')
    axes[1].barh(x, selected.eligible_nominal_fraction, color='#785ba7')
    for ax, title in zip(axes, ['Municipios con alguna observación elegible', 'LN en observaciones elegibles / LN total']):
        ax.set(yticks=x, yticklabels=selected.alternative, title=title, xlim=(0, 1))
        ax.xaxis.set_major_formatter(PercentFormatter(1))
    fig.suptitle('Cobertura 2024 · umbrales originales sin cambios')
    fig.savefig(charts/'coverage_comparison.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout='constrained')
    counts = exclusions[exclusions.eligible_segments.eq(0)].exclusion_reason.value_counts()
    axes[0].barh(counts.index, counts.values, color='#b75c42')
    axes[0].set(title='1,061 municipios sin segmentos exactos elegibles', xlabel='Municipios (causas exclusivas)')
    labels = ['LN '+('sí' if r.ln_ok else 'no')+' / SV+NV '+('sí' if r.specified_ok else 'no')+
        ' / filas '+('sí' if r.source_rows_ok else 'no') for r in truth.itertuples()]
    axes[1].barh(labels, truth.segments, color='#4285a8'); axes[1].set(title='Criterios exactos 18–100', xlabel='Segmentos')
    fig.savefig(charts/'exclusion_audit.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout='constrained')
    axes[0].bar(national.TIPOSEC, national.LN/national.LN.sum(), color=['#5586ac', '#70a572', '#d2ad55'])
    axes[0].yaxis.set_major_formatter(PercentFormatter(1)); axes[0].set(title='Composición nominal de 2024', ylabel='LN del tipo / LN total')
    for t in TYPES:
        values = parents['life_stage'].query('context_is_eligible')[f'section_ln_share_{t}'].sort_values()
        axes[1].plot(values, np.arange(1, len(values)+1)/len(values), label=t)
    axes[1].set(title='Distribución entre segmentos life_stage elegibles', xlabel='Proporción nominal asociada al tipo', ylabel='Fracción acumulada de segmentos')
    axes[1].xaxis.set_major_formatter(PercentFormatter(1)); axes[1].yaxis.set_major_formatter(PercentFormatter(1)); axes[1].legend()
    fig.savefig(charts/'section_composition.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout='constrained')
    for ax, scheme in zip(axes, SCHEMES):
        cells = profiles[f'{scheme}_cross'][0]
        frame = cells.groupby(['age_band', 'SEXO', 'TIPOSEC']).is_supported.mean().unstack('TIPOSEC').reindex(columns=TYPES)
        image = ax.imshow(frame, vmin=0, vmax=1, cmap='viridis', aspect='auto')
        ax.set(xticks=np.arange(3), xticklabels=TYPES, yticks=np.arange(len(frame)),
            yticklabels=[f'{band} · sexo {sex}' for band, sex in frame.index], title=scheme)
    fig.colorbar(image, ax=axes, label='Fracción de 2,477 municipios con celda y soporte')
    fig.suptitle('Fragmentación al cruzar edad, sexo y tipo de sección')
    fig.savefig(charts/'section_fragmentation.png', dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(13, 7), layout='constrained')
    matrix = state_table[state_table.alternative.isin(['exact_age', 'life_stage_context', 'broad_context', 'life_stage_split_type'])].pivot(
        index='state_name_label', columns='alternative', values='eligible_nominal_fraction')
    image = ax.imshow(matrix, vmin=0, vmax=1, cmap='viridis', aspect='auto')
    ax.set(yticks=np.arange(len(matrix)), yticklabels=matrix.index, xticks=np.arange(len(matrix.columns)),
        xticklabels=matrix.columns, title='Cobertura de LN elegible por entidad · denominador LN total 2024')
    fig.colorbar(image, ax=ax, label='Fracción de LN'); fig.savefig(charts/'state_coverage.png', dpi=160); plt.close(fig)


def write_report(path, charts, quality, exclusions, truth, counterfactual, national, parents, profiles,
                 correlations, spread, fragmentation, section_support, protected_count, rows_read, coverage):
    def table(frame, columns, headers=None):
        rows = []
        for _, row in frame.iterrows():
            rows.append([f'{row[c]:,}' if isinstance(row[c], (int, np.integer)) else
                ('n/d' if pd.isna(row[c]) else f'{row[c]:.5f}' if isinstance(row[c], float) else str(row[c])) for c in columns])
        return markdown_table(headers or columns, rows)
    def picture(filename, title):
        import os
        return f'![{title}]({Path(os.path.relpath(charts/filename, path.parent)).as_posix()})'
    absent = exclusions[exclusions.eligible_segments.eq(0)]
    reasons = absent.groupby('exclusion_reason', as_index=False).agg(municipalities=('LN', 'size'), LN=('LN', 'sum'))
    source_only = exclusions[exclusions.exclusion_reason.eq('source_rows_only')].sort_values(['EDOCVE', 'MPIOCVE'])
    summary = quality[['alternative', 'observations', 'eligible_observations', 'eligible_municipalities', 'eligible_LN', 'eligible_nominal_fraction', 'undefined_rates']].copy()
    summary['eligible_nominal_fraction'] = summary.eligible_nominal_fraction.map(pct)
    context_rows = []
    profile_rows = []
    for scheme in SCHEMES:
        parent = parents[scheme]; eligible = parent[parent.context_is_eligible]
        context_rows.append([scheme, len(eligible), eligible.groupby(MUNICIPAL_KEYS).ngroups,
            int(eligible.section_count.lt(5).sum()), int(eligible.section_types_present.eq(1).sum()),
            int(eligible.section_types_present.eq(3).sum()), int(eligible.has_high_unspecified_rate.sum()), pct(eligible.NS.sum()/eligible.LN.sum())])
        for suffix in ['base', 'cross']:
            cells, status, values = profiles[f'{scheme}_{suffix}']
            profile_rows.append([scheme, suffix, values.shape[1]-2, int((~cells.is_present).sum()),
                int(cells.cell_status.eq('undefined_rate').sum()), int(status.is_complete.sum()),
                int(status.is_eligible.sum()), int(status.is_complete_low_ns.sum()),
                int(status.loc[status.is_eligible, 'LN'].sum())])
    largest = source_only.sort_values('LN', ascending=False).head(8)
    diagnostics = quality[quality.alternative.isin(['exact_age', 'life_stage_context', 'broad_context',
        'life_stage_split_type', 'broad_split_type', 'life_stage_territorial_base', 'life_stage_territorial_cross'])].copy()
    for column in ['ns_q1', 'ns_median', 'ns_q3', 'ns_nominal']:
        diagnostics[column] = diagnostics[column].map(pct)
    worst_states = coverage[coverage.alternative.eq('life_stage_context')].sort_values('eligible_municipality_fraction').head(6).copy()
    for column in ['eligible_nominal_fraction', 'eligible_municipality_fraction']:
        worst_states[column] = worst_states[column].map(pct)
    recovered = []
    for scheme, parent in parents.items():
        selected = parent[parent.context_is_eligible][MUNICIPAL_KEYS].drop_duplicates()
        recovered.append(f'{scheme}: {len(source_only.merge(selected, on=MUNICIPAL_KEYS))}/49')
    text = f'''# Viabilidad de características electorales y territoriales · 2024

## Resultado y recomendación

**El siguiente piloto debería contrastar segmentos life_stage con diferencia de participación nacional por intervalo/sexo y composición nominal U/R/M, sin edad media como coordenada; broad queda como sensibilidad.** Usar participación absoluta como control separado. La propuesta aporta contexto electoral además de un nivel relativo, conserva el soporte previo y permite estudiar si el contexto añade información. Todavía no demuestra clusters naturales, causalidad ni perfiles individuales. No se entrenó ningún algoritmo ni se seleccionaron variables, pesos o distancias definitivos.

La comparación de cobertura, con LN nacional como denominador común, es:

{table(summary, list(summary.columns), ['Alternativa', 'Observaciones en alcance', 'Elegibles', 'Municipios elegibles', 'LN elegible', '% LN total', 'Tasas NULL observadas'])}

En las filas de segmentos, un municipio se cuenta si aporta al menos un segmento elegible; eso no significa que todo su perfil esté cubierto. En perfiles territoriales la condición exige **todas** las coordenadas con soporte; LN elegible es el total municipal de todas las categorías de esos municipios, no el LN del núcleo H/M. Las alternativas son vistas distintas y nunca se suman. Las tasas NULL de la tabla anterior son tasas totales de observaciones presentes; los faltantes internos de perfiles se presentan más adelante.

{picture('coverage_comparison.png', 'Comparación de cobertura')}

## Auditoría de los 1,061 municipios sin segmentos exactos elegibles

Se verifican los resultados previos desde la referencia exacta, con edades 18–100, tasa definida, LN≥100, SV+NV≥100 y filas fuente≥5. Los criterios siguen vigentes; las relajaciones siguientes son contrafactuales descriptivos, sin cambiar la selección anterior.

{table(reasons, ['exclusion_reason', 'municipalities', 'LN'], ['Causa exclusiva', 'Municipios', 'LN municipal total'])}

Clasificación exclusiva: primero se detecta si toda la especificación 18–100 es cero; después si hay algún segmento que supera ambos conteos y sólo falla filas; después si existe LN≥100 pero ningún SV+NV≥100; el resto no alcanza LN en ninguna celda. **Denominador especificado≥100 implica LN≥100** por la identidad de conteos. Quitar únicamente LN no recupera filas mientras se mantiene el mismo mínimo especificado; quitar SV+NV sí puede aceptar tasas con muy poca especificación. Los fallos marginales se superponen y no se suman.

{table(truth, ['ln_ok', 'specified_ok', 'source_rows_ok', 'segments', 'LN', 'NS'])}

{table(counterfactual, ['require_ln', 'require_specified', 'require_source_rows', 'segments', 'municipalities', 'LN'], ['Exige LN≥100', 'Exige SV+NV≥100', 'Exige filas≥5', 'Segmentos', 'Municipios', 'LN seleccionado'])}

Todos los contrafactuales mantienen SV+NV>0 y 18–100; ninguna tasa NULL se vuelve cero. **Los 49 municipios source_rows_only suman LN={int(source_only.LN.sum()):,}; sus {int(source_only.count_supported_segments.sum()):,} segmentos que cumplen conteos representan LN={int(source_only.count_supported_LN.sum()):,}.** Esa última cifra sería la ganancia del mínimo de una fila dentro de esos 49; la ganancia total nacional sería 1,082 segmentos y LN=171,965, pues incluye celdas adicionales de municipios ya representados. Ninguna de esas ganancias es el LN municipal total. El máximo de filas entre sus celdas que cumplen conteos es {int(source_only.count_supported_source_max.max())}; hay datos nominales suficientes según los dos conteos, pero pocas celdas fuente. No son 49 municipios sin información. Con los intervalos existentes, sin modificar umbrales, aportan algún segmento elegible: {'; '.join(recovered)}. Mejorar soporte agregando edades no incrementa automáticamente el número de secciones distintas.

{table(largest, ['EDOCVE', 'MPIOCVE', 'municipality_name_label', 'LN', 'count_supported_segments', 'count_supported_source_max'], ['Entidad', 'Municipio', 'Nombre', 'LN municipal', 'Celdas con conteos suficientes', 'Máx. filas en ellas'])}

El archivo metadata/source_rows_only_municipalities.parquet y su CSV enumeran los **49**, con nombres, claves, NS y rangos de soporte. source_row_count mide celdas sección/edad/sexo, no individuos, votantes independientes, secciones independientes ni precisión inferencial. En una edad exacta puede aproximar presencia de secciones; al agrupar edades se suman muchas celdas de la misma sección. Por eso se calcula además section_count distinto, sin sustituir automáticamente el umbral histórico.

{picture('exclusion_audit.png', 'Causas y criterios separados')}

## Dónde está TIPOSEC y cómo se reconstruyó el cruce

Se confirmó el esquema real. exact_age_2024.parquet tiene edad/sexo/municipio pero **no TIPOSEC**. Los descriptivos municipality_section_type y section_type_year conservan el marginal por sección, pero no el cruce con edad/sexo. No se pueden unir esos dos marginales para reconstruir el conjunto: multiplicaría filas o supondría independencia inexistente.

Se reutilizó open_dataset() de clean_data.py y se leyeron **{rows_read:,} filas de Parquet limpio, sólo de 2024**, por bloques y por entidad, proyectando claves, SECCION, TIPOSEC, edad, sexo y los cuatro conteos técnicos. No se leyeron CSV ni se recorrieron las otras cinco elecciones. Se reconstruyeron life_stage y broad × municipio × sexo × tipo de sección; ambos conservan 101+ y SEXO=2. Se deduplican claves de sección entre bloques para section_count. La marginal exacta se concilia con la referencia existente y se descarta de memoria por entidad.

El diccionario original 2024, preservado en metadata/source_dictionary_2024.json, define **U Urbana; R Rural; M Mixta**, tipo de sección en el año correspondiente. Se conserva su texto extraído, incluidos caracteres de codificación heredados. Es una clasificación de **sección electoral**, no tipo de localidad, residencia individual observada, estatus socioeconómico o categoría oficial del municipio completo. La referencia de sección procede de la residencia consignada en la credencial según el diccionario; no prueba residencia efectiva actual. No se deducen distritos ni continuidad territorial histórica.

{table(national, ['TIPOSEC', 'LN', 'SV', 'NV', 'NS', 'source_row_count', 'participation_observed', 'unspecified_rate'])}

Las diferencias nacionales anteriores no son efectos causales de U/R/M: mezclan composición demográfica, territorial y disponibilidad de cuadernillos. NS no es abstención. Sus tasas se muestran como proporciones; multiplicar por 100 produce porcentajes.

{picture('section_composition.png', 'Composición de tipo de sección')}

## Segmentos con contexto, sin edad en la distancia

Unidad: municipio + intervalo candidato + sexo, **sin dividirla por tipo de sección**. Por segmento se suman primero LN/SV/NV/NS y se calcula SV/(SV+NV). La diferencia nacional usa la referencia existente del mismo intervalo/sexo, obtenida con todos los conteos antes de seleccionar soporte. Se valida contra los nuevos agregados. La referencia exacta por año de edad responde a otra pregunta y no se intercambia con ella.

La composición se define como LN_U/LN, LN_R/LN y LN_M/LN. La cobertura U/R/M es exhaustiva y sin categorías faltantes en esta lectura. Un tipo ausente tiene **suma nominal cero y proporción cero válidas** dentro del segmento presente; su tasa de participación permanece no definida. Esto no imputa conductas ni crea observaciones. Si faltara TIPOSEC o apareciera un código distinto, el programa detendría la ejecución para revisión, sin redistribuir su LN.

{markdown_table(['Esquema', 'Segmentos elegibles', 'Municipios', 'Elegibles con <5 secciones', 'Con un solo tipo', 'Con tres tipos', 'NS≥10 %', 'NS/LN elegible'], context_rows)}

El criterio de soporte parental no exige que cada componente U/R/M tenga SV+NV≥100. Las proporciones describen composición nominal conocida, no tres estimaciones de participación igualmente fiables. metadata/section_support.csv conserva conteos, denominadores y fragmentación por intervalo/sexo/tipo. Se guardan además section_count, número de tipos presentes, soporte bajo en hijos y sus tasas para revisión; no se eleva su fiabilidad mediante la agregación.

### Características y redundancia

- **Conducta agregada:** participación absoluta **o** diferencia nacional con signo, en modelos separados. No incorporar ambas automáticamente: dentro de intervalo/sexo difieren por una constante conocida.
- **Contexto:** composición U/R/M como bloque. Las tres proporciones suman uno y tienen sólo dos grados de libertad. Mantener las tres conserva simetría en una posible distancia euclídea del bloque; no aporta tres fuentes independientes de información. El contrato declara esa dependencia. Retirar una proporción cambia la geometría al privilegiar categorías; dos contrastes ortonormales podrían conservarla, pero aquí no se transforman datos ni se fija distancia. Log-ratios requerirían resolver ceros estructurales y no se aplican pseudoconteos.
- **Metadatos:** edad, sexo, municipio, entidad, distrito de referencia, LN/SV/NV/NS, denominadores y banderas. Códigos U/R/M no se convierten a 0/1/2 ordinal. Edad media y conteos absolutos no entran como coordenadas propuestas. NS/LN y soporte sirven para diagnosticar disponibilidad, evitando agrupar captura sin explicitarlo.

Se guardan las variables crudas candidatas en reference/context_segments_SCHEME.parquet, un contrato de alternativas y correlaciones/distribuciones en metadata/. No se entrega una selección filtrada como matriz final. La referencia exacta anterior se enlaza mediante ruta, hash y claves; se preservan sus edades exactas sin copiar o alterar toda la base. Ambos escenarios mantienen explícitos >100 y SEXO=2, que no se incorporan a H/M ni se inventan para completar perfiles.

{table(correlations[correlations['first'].eq('participation_deviation_national')], ['scheme', 'first', 'second', 'n', 'pearson', 'spearman'])}

Estas correlaciones sobre segmentos elegibles son descriptivas, no efectos ni validación de clusters. La composición puede repetir un contexto territorial casi constante en muchos segmentos y orientar grupos hacia tipos de municipios, incluso sin introducir identidad municipal. Los rangos intramunicipales ayudan a cuantificarlo:

{table(spread, list(spread.columns))}

La representación propuesta merece un piloto controlado porque añade contexto medido y mantiene cobertura, **no porque se haya demostrado que mejore perfiles**. Comparar después tasa sola, diferencia sola, y cada una con el bloque contextual, sobre el mismo universo; mantener edad/sexo para interpretación y revisar cuánto explica la composición frente a conducta. Acordar pesos de bloques y escalas antes de entrenar. Con peso uno por segmento, municipios con más segmentos elegibles pesan más; igual peso total municipal cambia ese objetivo; LN priorizaría volumen y no corrige automáticamente NS o sesgo.

## Riesgo de fragmentar por TIPOSEC

Separar tipo en una nueva unidad municipio/intervalo/sexo/TIPOSEC aumenta observaciones y reparte denominadores. La tabla de cobertura distingue un padre sin dividir y sus hijos. Que un municipio mantenga algún hijo elegible no significa conservar todos sus tipos o edades. metadata/fragmentation.csv cuantifica número de hijos, soporte, LN y padres que conservan cero, alguno o todos sus hijos observados con soporte.

{table(fragmentation, list(fragmentation.columns))}

{picture('section_fragmentation.png', 'Soporte del cruce de categorías')}

Los ceros de composición no autorizan tasas cero en tipos ausentes. Tampoco exigir los tres tipos convierte a un municipio puramente rural o urbano en dato erróneo: es una carencia estructural para una rejilla común cruzada. No se excluyen estas observaciones de las tablas guardadas.

## Alternativas territoriales: municipios como observaciones

Se evalúan perfiles H/M de edades 18–100: participación por edad/sexo sin cruzar tipo, y por edad/sexo/**U/R/M**. El primero puede acompañarse de composición nominal municipal como bloque contextual sin fragmentar coordenadas. Todas las referencias municipales y complementos se conservan. Edad/sexo/tipo son nombres de coordenadas, no códigos ordinales.

{markdown_table(['Esquema', 'Perfil', 'Coordenadas', 'Ausentes', 'Presentes NULL', 'Municipios completos definidos', 'Todas con soporte', 'Además NS<10 % en cada celda', 'LN municipal con soporte'], profile_rows)}

Los archivos territorial/*/cells.parquet diferencian absent_combination, undefined_rate y defined. Los values.parquet conservan todos los municipios y sus NULL; metadata.parquet conserva totales y banderas por perfil. El perfil cruzado no se recomienda como primera matriz completa si exige recuperar coordenadas estructuralmente ausentes. Una alternativa es estudiar cada contexto por separado o distancias para información incompleta, que necesitan un contrato propio y no se implementan aquí. **Estas alternativas agruparían municipios, no segmentos ni personas.** El perfil sin cruce más composición conserva la completitud del perfil base; añadir tres participaciones municipales por tipo introduciría otra vez ausencia estructural y redundancia con el perfil, por lo que no se añade automáticamente.

## Cobertura por entidad y confiabilidad

metadata/state_coverage.csv presenta todas las alternativas y 32 entidades: observaciones, municipios y LN elegibles, contra LN total de cada entidad; municipality_coverage.parquet permite localizar pérdidas. metadata/quality_summary.csv contiene cuartiles de LN y SV+NV, NULL, cuartiles y agregado de NS/LN, tanto alcance observado como soporte elegible. Los criterios se aplican al grupo que se evalúa, no a la suma nacional.

{table(diagnostics, ['alternative', 'LN_median', 'specified_median', 'high_ns_observations', 'eligible_high_ns', 'ns_q1', 'ns_median', 'ns_q3', 'ns_nominal'], ['Alternativa', 'Mediana LN', 'Mediana SV+NV', 'NS alto en alcance', 'NS alto elegibles', 'NS/LN Q1', 'Mediana NS/LN', 'Q3 NS/LN', 'NS/LN agregado'])}

Las distribuciones anteriores dan igual peso a cada observación; NS/LN agregado es suma NS/suma LN, con otra ponderación. En filas territoriales corresponden al total municipal, no a la distribución de coordenadas; la rejilla cells.parquet conserva las banderas internas. Las seis entidades con menor cobertura municipal de life_stage contextual son:

{table(worst_states, ['EDOCVE', 'state_name_label', 'eligible_municipalities', 'available_municipalities', 'eligible_municipality_fraction', 'eligible_nominal_fraction'], ['Entidad', 'Nombre', 'Municipios elegibles', 'Observados', '% municipios', '% LN total'])}

{picture('state_coverage.png', 'Cobertura por entidad')}

Ningún tamaño de LN elimina el sesgo potencial de cuadernillos no disponibles. Las tasas son descriptivas del conjunto especificado. Un segmento pequeño puede tener tasa 0 o 1 válida; soporte y NS son diagnósticos, no pruebas de error. En perfiles, el soporte municipal total no garantiza soporte de cada coordenada. Se conserva un escenario NS<10 % como diagnóstico de cobertura adicional, sin sustituir el principal ni borrar registros.

## Validaciones, entregables y decisiones pendientes

Se verifican: identidad de conteos en fuentes y agregados; categorías/texto; tipo único por clave de sección municipal; conciliación exacta por municipio/edad/sexo, municipal por TIPOSEC y por entidad; igualdad de bandas con escenarios existentes; referencia nacional previa; elegibilidad parental idéntica; suma de proporciones; NULL de tasas con denominador cero; unicidad y lectura posterior de Parquet. Las dos vistas conservan por separado LN=98,330,348, SV=54,899,228, NV=37,105,466, NS=6,325,654 y 9,773,730 filas fuente, incluidos los 105 de SEXO=2 (LN=105). No se suman vistas alternativas.

Se verificaron hashes antes/después de **{protected_count:,} archivos previos**, con fuentes, resultados, informes, scripts y frontend. Manifiestos de entrada y marcadores _SUCCESS se contrastan antes de calcular. El manifiesto nuevo registra parámetros, versiones, esquemas, entradas, conciliaciones, incidencias y hashes de artefactos. _SUCCESS sólo aparece al completar validaciones y el informe. Las pruebas automatizadas cubren casos de bloques repetidos, secciones compartidas entre edades, ceros estructurales, NULL y redundancia de criterios. No se leyeron CSV originales, modificaron umbrales, normalizaron variables, ajustaron modelos ni crearon commits.

Pendiente: objetivo segmentos/territorios; alcance de inferencia; revisar el mínimo de filas frente a secciones distintas con evidencia electoral; decisión documentada sobre los 49 municipios; rangos candidatos; cobertura admisible por edad/sexo; papel de NS; representación y peso del bloque composicional; ponderación municipal/segmento/LN; sensibilidad a categorías/contextos dominantes y a tasas relativas versus absolutas. Edades exactas siguen disponibles como referencia y para diagnóstico de soporte; no se recupera cobertura mediante suavizado o imputación implícita.

Reproducir desde la raíz:

```powershell
.venv/Scripts/python.exe analysis/scripts/evaluate_contextual_features.py
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_evaluate_contextual_features.py
```

Destinos protegidos; repetir con --output, --charts y --report nuevos. --batch-size controla bloques. Datos nuevos en data/processed/contextual_feature_review/: aggregates/ contiene cruces conservados completos por entidad, reference/ segmentos con contexto y catálogo de secciones, territorial/ rejillas y perfiles sin imputar, metadata/ auditoría de exclusiones, coberturas, distribuciones, correlaciones, conciliaciones, contrato y manifiesto. Las gráficas son diagnósticos, sin agrupaciones estimadas.
'''
    path.write_text(text, encoding='utf-8')


def validate_sources(root, protected):
    """Contrasta marcadores y hashes declarados antes de usar resultados previos."""
    for name in ['technical_cleaned', 'cluster_features', 'exact_age_clustering_review', 'demographic_representation_comparison']:
        base = root/'data/processed'/name
        manifest_path = base/'metadata/run_manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        success = json.loads((base/'_SUCCESS').read_text(encoding='utf-8'))
        require(manifest['status'] == 'validated' and success['manifest_sha256'] == file_hash(manifest_path), f'Fuente no validada: {name}')
        if name == 'technical_cleaned':
            for part in manifest['parts']:
                if part['year'] == 2024:
                    require(protected[str(base/part['path'])] == part['sha256'], 'Parte limpia alterada.')
        else:
            for relative, digest in manifest['artifact_hashes'].items():
                require(protected[str(root/relative)] == digest, f'Artefacto anterior alterado: {relative}')
    for report in REPORT_INPUTS:
        require((root/'analysis/reports'/report).is_file(), 'Informe requerido ausente.')


def evaluate(root, output, charts, report, batch_size=100_000):
    root, output, charts, report = [Path(value).resolve() for value in [root, output, charts, report]]
    require(output.is_relative_to(root/'data/processed') and charts.is_relative_to(root/'analysis/charts') and
        report.is_relative_to(root/'analysis/reports'), 'Destinos fuera de áreas autorizadas.')
    require(not output.exists() and not charts.exists() and not report.exists(), 'Elegir destinos nuevos; no se sobrescribe.')
    require(batch_size > 0, 'Bloque debe ser positivo.')
    print('Comprobando integridad de entradas...', flush=True)
    protected = snapshot_inputs(root, output, charts)
    for base in [root/'src', root/'analysis/scripts']:
        for path in base.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.name not in [Path(__file__).name, 'test_evaluate_contextual_features.py']:
                protected[str(path)] = file_hash(path)
    protected[str(root/'.gitignore')] = file_hash(root/'.gitignore')
    validate_sources(root, protected)
    output.mkdir(parents=True); (output/'metadata').mkdir(); charts.mkdir(parents=True)
    started = time.monotonic()
    manifest = dict(status='running', errors=[], started_at_utc=datetime.now(timezone.utc).isoformat(),
        protected_hashes=protected, configuration=dict(year=2024, schemes=SCHEMES, batch_size=batch_size,
        min_LN=100, min_specified=100, min_source_rows=5, high_ns=.1),
        versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, pyarrow=pa.__version__, matplotlib=matplotlib.__version__))
    manifest_path = output/'metadata/run_manifest.json'
    save_json(manifest_path, manifest)
    try:
        descriptive = root/'data/processed/descriptive'
        exact = pd.read_parquet(root/'data/processed/exact_age_clustering_review/reference/segments.parquet')
        municipalities = pd.read_parquet(descriptive/'municipality/table.parquet').query('election_year == 2024').reset_index(drop=True)
        states = pd.read_parquet(descriptive/'state/table.parquet').query('election_year == 2024').reset_index(drop=True)
        prior_types = pd.read_parquet(descriptive/'municipality_section_type/table.parquet').query('election_year == 2024')
        core, truth, counterfactual, exclusions = exclusion_audit(exact, municipalities)
        previous = pd.read_parquet(root/'data/processed/exact_age_clustering_review/metadata/municipality_exclusions.parquet')
        require(exclusions.eligible_segments.eq(0).sum() == 1061, 'Exclusiones municipales distintas.')
        require(exclusions.exclusion_reason.eq('source_rows_only').sum() == 49, 'Casos de filas fuente distintos.')
        pd.testing.assert_series_equal(exclusions.set_index(MUNICIPAL_KEYS).eligible_segments.sort_index(), previous.set_index(MUNICIPAL_KEYS).eligible_segments.sort_index())
        for name, frame in [('exclusion_truth_table', truth), ('exclusion_counterfactuals', counterfactual), ('municipality_exclusions', exclusions),
            ('source_rows_only_municipalities', exclusions[exclusions.exclusion_reason.eq('source_rows_only')])]:
            save_table(output/f'metadata/{name}.csv', frame)
            if 'municipalit' in name: save_table(output/f'metadata/{name}.parquet', frame)
        source = open_dataset(root/'data/processed/technical_cleaned')
        require('TIPOSEC' in source.schema.names, 'No se conserva TIPOSEC en la fuente.')
        save_json(output/'metadata/input_schema.json', dict(cleaned=str(source.schema), exact_reference_columns=list(exact.columns)))
        dictionary = json.loads((root/'data/processed/technical_cleaned/metadata/source_dictionaries.json').read_text(encoding='utf-8'))['2024']
        save_json(output/'metadata/source_dictionary_2024.json', dictionary)
        columns = [*EXACT_KEYS, 'TIPOSEC', 'SECCION', 'election_year', 'state_code', *SOURCE_COUNTS]
        # EXACT_KEYS no contiene año: se selecciona una sola vez.
        all_parts = {scheme: [] for scheme in SCHEMES}; inventory_parts = []; reconciliations = []; rows_read = 0
        for state in sorted(states.EDOCVE, key=int):
            batches = source.scanner(columns=columns, filter=(ds.field('election_year') == 2024) & (ds.field('state_code') == state),
                batch_size=batch_size, use_threads=False).to_batches()
            parts, marginal, inventory = aggregate_state(batches)
            compare_sums(marginal, exact[exact.EDOCVE.eq(state)], EXACT_KEYS)
            rows_read += int(marginal.source_row_count.sum()); inventory_parts.append(inventory)
            for scheme, part in parts.items():
                part['election_year'] = np.int16(2024)
                save_table(output/f'aggregates/{scheme}/state_{state}.parquet', part)
                all_parts[scheme].append(part)
            reconciliations.append(dict(EDOCVE=state, level='exact_municipality_age_sex', groups=len(marginal), rows=int(marginal.source_row_count.sum()), differences=0))
            print(f'Entidad {state}: {int(marginal.source_row_count.sum()):,} filas conciliadas.', flush=True)
        require(rows_read == 9_773_730, 'Pérdida de filas fuente 2024.')
        save_table(output/'reference/section_inventory_2024.parquet', pd.concat(inventory_parts, ignore_index=True))
        parents, profiles, quality, coverage, fragments = {}, {}, [], [], []
        distributions, correlations, spreads, supports = [], [], [], []
        nominal_total = int(municipalities.LN.sum())
        quality.append(quality_row('exact_age', core, core.is_eligible, nominal_total))
        coverage.append(state_coverage('exact_age', core, core.is_eligible, states))
        national = None
        for scheme in SCHEMES:
            children = indicators(pd.concat(all_parts[scheme], ignore_index=True))
            compare_sums(children, prior_types, [*MUNICIPAL_KEYS, 'TIPOSEC'])
            compare_sums(children, municipalities, MUNICIPAL_KEYS)
            require(children.sex_2_source_rows.sum() == children.sex_2_nominal_count.sum() == 105, 'SEXO=2 perdido.')
            original = pd.read_parquet(root/f'data/processed/demographic_representation_comparison/reference/b_{scheme}.parquet')
            parent = build_context_segments(children, original, scheme)
            national_parent = grouped(children, ['age_band', 'SEXO'])
            national_parent['national_participation'] = ratio(national_parent.SV, national_parent.SV+national_parent.NV)
            check = parent.merge(national_parent[['age_band', 'SEXO', 'national_participation']],
                on=['age_band', 'SEXO'], suffixes=('_previous', '_new'), validate='many_to_one')
            require(np.allclose(check.national_participation_previous, check.national_participation_new, equal_nan=True), 'Referencia nacional diferente.')
            require(np.allclose(parent.participation_deviation_national, parent.participation_observed-parent.national_participation, equal_nan=True), 'Diferencia nacional incorrecta.')
            parents[scheme] = parent
            save_table(output/f'reference/context_segments_{scheme}.parquet', parent)
            save_table(output/f'reference/national_reference_{scheme}.parquet', national_parent)
            save_table(output/f'reference/pending_segments_{scheme}.parquet', parent[~parent.context_is_eligible])
            save_table(output/f'reference/section_segments_{scheme}.parquet', children)
            if national is None: national = indicators(grouped(children, ['TIPOSEC']))
            active = parent[parent.in_scope]
            for suffix, mask in [('previous', active.is_eligible), ('context', active.context_is_eligible),
                ('context_low_ns', active.context_is_eligible & ~active.has_high_unspecified_rate)]:
                name = f'{scheme}_{suffix}'
                quality.append(quality_row(name, active, mask, nominal_total)); coverage.append(state_coverage(name, active, mask, states))
            split = children[children.age_band.ne('101+')].copy()
            split['is_eligible'] = ~split.has_low_support & split.specified_count.gt(0)
            quality.append(quality_row(f'{scheme}_split_type', split, split.is_eligible, nominal_total))
            coverage.append(state_coverage(f'{scheme}_split_type', split, split.is_eligible, states))
            support = split.groupby(['age_band', 'SEXO', 'TIPOSEC'], as_index=False).agg(
                segments=('LN', 'size'), eligible_segments=('is_eligible', 'sum'), LN=('LN', 'sum'),
                median_LN=('LN', 'median'), median_specified=('specified_count', 'median'),
                high_ns=('has_high_unspecified_rate', 'sum'), median_sections=('section_count', 'median'))
            support['scheme'] = scheme; supports.append(support)
            children_status = split.groupby(BAND_KEYS, as_index=False).agg(children=('LN', 'size'), supported_children=('is_eligible', 'sum'))
            status = active.merge(children_status, on=BAND_KEYS, validate='one_to_one')
            selected = status[status.is_eligible]
            fragments.append(dict(scheme=scheme, eligible_parents=len(selected),
                all_present_children_supported=int(selected.supported_children.eq(selected.children).sum()),
                some_but_not_all_children_supported=int((selected.supported_children.gt(0) & selected.supported_children.lt(selected.children)).sum()),
                no_supported_children=int(selected.supported_children.eq(0).sum()),
                eligible_parents_fewer_than_5_sections=int(selected.section_count.lt(5).sum())))
            for suffix, split_types in [('base', False), ('cross', True)]:
                cells, status, values = profile_review(children, parent, municipalities, scheme, split_types)
                profiles[f'{scheme}_{suffix}'] = (cells, status, values)
                for name, frame in [('cells', cells), ('metadata', status), ('values', values)]:
                    save_table(output/f'territorial/{scheme}_{suffix}/{name}.parquet', frame)
                quality.append(quality_row(f'{scheme}_territorial_{suffix}', status, status.is_eligible, nominal_total, True, values.shape[1]-2))
                coverage.append(state_coverage(f'{scheme}_territorial_{suffix}', status, status.is_eligible, states))
            dist, corr, spread = numeric_diagnostics(parent, scheme)
            distributions.append(dist); correlations.append(corr); spreads.append(spread)
            reconciliations.append(dict(EDOCVE='all', level=f'{scheme}_municipality_section_and_band', groups=len(children), rows=int(children.source_row_count.sum()), differences=0))
        # Clasifica recuperación de municipios frente al exacto, conservando cada universo.
        municipal_coverage = municipalities.copy()
        for scheme, parent in parents.items():
            selected = parent[parent.context_is_eligible].groupby(MUNICIPAL_KEYS, as_index=False).agg(
                **{f'{scheme}_eligible_segments': ('LN', 'size'), f'{scheme}_eligible_LN': ('LN', 'sum')})
            municipal_coverage = municipal_coverage.merge(selected, on=MUNICIPAL_KEYS, how='left', validate='one_to_one')
            for col in [f'{scheme}_eligible_segments', f'{scheme}_eligible_LN']:
                municipal_coverage[col] = municipal_coverage[col].fillna(0).astype('int64')
        municipal_coverage = municipal_coverage.merge(exclusions[[*MUNICIPAL_KEYS, 'eligible_segments', 'exclusion_reason']], on=MUNICIPAL_KEYS, validate='one_to_one')
        quality, coverage = pd.DataFrame(quality), pd.concat(coverage, ignore_index=True)
        corr, spread, fragments, supports = pd.concat(correlations, ignore_index=True), pd.concat(spreads, ignore_index=True), pd.DataFrame(fragments), pd.concat(supports, ignore_index=True)
        for name, frame in [('quality_summary', quality), ('state_coverage', coverage), ('feature_distributions', pd.concat(distributions, ignore_index=True)),
            ('correlations', corr), ('composition_within_municipality', spread), ('fragmentation', fragments), ('section_support', supports),
            ('national_section_counts', national), ('reconciliation', pd.DataFrame(reconciliations))]:
            save_table(output/f'metadata/{name}.csv', frame)
        save_table(output/'metadata/municipality_coverage.parquet', municipal_coverage)
        save_json(output/'metadata/feature_contract.json', dict(
            unit='municipality_age_band_sex', year=2024, schemes=SCHEMES, fit_performed=False, normalization_performed=False,
            behavioral_alternatives=[['participation_observed'], ['participation_deviation_national']],
            contextual_block=[f'section_ln_share_{t}' for t in TYPES], contextual_affine_dimension=2,
            contextual_geometry='Tres proporciones simétricas; suma uno. No tres variables independientes. Peso y distancia pendientes.',
            metadata_only=['age_band', 'SEXO', *MUNICIPAL_KEYS, 'LN', 'SV', 'NV', 'NS', 'specified_count', 'unspecified_rate', 'section_count', 'district_reference_year'],
            exact_reference=dict(path='data/processed/cluster_features/reference/exact_age_2024.parquet',
                sha256=file_hash(root/'data/processed/cluster_features/reference/exact_age_2024.parquet'), keys=EXACT_KEYS),
            section_labels=dict(U='Urbana', R='Rural', M='Mixta'),
            provenance='Parquet limpio 2024, año/entidad/municipio/sección/edad/sexo; agregado por intervalos candidatos.'))
        plot_diagnostics(charts, quality, exclusions, truth, national, parents, profiles, coverage)
        write_report(report, charts, quality, exclusions, truth, counterfactual, national, parents, profiles,
            corr, spread, fragments, supports, len(protected), rows_read, coverage)
        for path, digest in protected.items():
            require(file_hash(path) == digest, f'Archivo previo modificado: {path}')
        manifest.update(status='validated', finished_at_utc=datetime.now(timezone.utc).isoformat(), seconds=time.monotonic()-started,
            rows_read_2024=rows_read, protected_files=len(protected), report_sha256=file_hash(report),
            script_sha256=file_hash(Path(__file__)),
            test_script_sha256=file_hash(root/'analysis/scripts/test_evaluate_contextual_features.py'),
            artifact_hashes={str(path.relative_to(root)): file_hash(path) for base in [output, charts] for path in base.rglob('*')
                if path.is_file() and path != manifest_path})
        save_json(manifest_path, manifest)
        save_json(output/'_SUCCESS', dict(manifest_sha256=file_hash(manifest_path)))
        print(f'Validado: {report}', flush=True)
    except Exception as error:
        manifest.update(status='failed', errors=[repr(error)])
        save_json(manifest_path, manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, default=Path('data/processed/contextual_feature_review'))
    parser.add_argument('--charts', type=Path, default=Path('analysis/charts/contextual_feature_review'))
    parser.add_argument('--report', type=Path, default=Path('analysis/reports/contextual_feature_review.md'))
    parser.add_argument('--batch-size', type=int, default=100_000)
    args = parser.parse_args()
    evaluate(args.root, args.root/args.output, args.root/args.charts, args.root/args.report, args.batch_size)


if __name__ == '__main__':
    main()
