"""Piloto E1/E2 con edades exactas de 2024 y soporte explícito.

Sólo lee agregados existentes; conserva pendientes, categorías y conteos.
Reutiliza Lloyd probado y calcula Silhouette de anclas por bloques acotados.
"""
from __future__ import annotations

import os
for thread_variable in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[thread_variable] = '1'

import argparse
from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from clean_data import require, file_hash, save_json
from build_cluster_features import make_ids, save_table, snapshot_inputs
from build_descriptive import METRICS, markdown_table, pct, number
from clustering_core import fit_scaler, transform, adjusted_rand
from compare_demographic_features import (initialization_bank, fit_bank, predict, nullable_labels,
    explained_fraction, weighted_group_sse, pandas_numerical_check, membership, source_validation)
from compare_clustering_methods import scalar_engine, scalar_silhouette
from evaluate_cluster_separation import align_partition, decision_edges
from run_demographic_pilot import anchor_sample

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

KEYS = ['election_year', 'EDOCVE', 'MPIOCVE', 'age_value', 'SEXO']
MUNICIPAL_KEYS = ['EDOCVE', 'MPIOCVE']
FEATURES = ['age_value', 'participation_deviation_exact']
KS = [2, 3, 4, 5, 6]
SEEDS = [17, 42, 2024]
MAIN_THRESHOLD = 100
MIN_SOURCE_ROWS = 5
THRESHOLDS = [1, 25, 50, 100, 200, 500]
COLORS = [plt.get_cmap('tab10')(i) for i in range(10)]


def ratio(numerator, denominator):
    """Cociente nullable: cero en el denominador no se vuelve participación cero."""
    numerator, denominator = np.asarray(numerator, dtype=float), np.asarray(denominator, dtype=float)
    return np.divide(numerator, denominator, out=np.full(numerator.shape, np.nan), where=denominator > 0)


def prepare_segments(reference):
    """El esquema confirmado ya tiene la unidad exacta; evita volver a sumar filas.

    Las etiquetas de intervalos previas permanecen sólo como metadatos heredados.
    La referencia nacional usa todos los conteos antes de seleccionar soporte.
    """
    require(set([*KEYS, *METRICS, 'state_name_label', 'municipality_name_label', 'district_reference_year']).issubset(reference.columns), 'Esquema exacto incompleto.')
    require(not reference.duplicated(KEYS).any(), 'La referencia no es única por municipio/edad/sexo.')
    require(reference.election_year.eq(2024).all() and reference.age_value.ge(18).all(), 'Año/edad fuera del alcance auditado.')
    require(reference.age_value.map(lambda value: isinstance(value, (int, np.integer))).all(), 'Edad no entera.')
    require(reference.LN.eq(reference.SV+reference.NV+reference.NS).all(), 'Identidad de conteos inválida.')
    for field in ['EDOCVE', 'MPIOCVE', 'SEXO']:
        require(reference[field].map(lambda value: isinstance(value, str)).all(), 'Clave no textual.')
    frame = reference.copy().reset_index(drop=True)
    frame.insert(0, 'row_id', make_ids(frame, KEYS, 'exact_age'))
    frame['specified_count'] = frame.SV+frame.NV
    observed = ratio(frame.SV, frame.specified_count)
    require(np.allclose(observed, frame.participation_observed, equal_nan=True), 'Tasas originales no corresponden a conteos.')
    frame['participation_observed'] = observed
    frame['unspecified_rate'] = ratio(frame.NS, frame.LN)
    national = frame.groupby(['election_year', 'age_value', 'SEXO'], observed=True, as_index=False)[METRICS].sum()
    national['specified_count'] = national.SV+national.NV
    national['national_participation_exact'] = ratio(national.SV, national.specified_count)
    frame = frame.merge(national[['age_value', 'SEXO', 'national_participation_exact']],
        on=['age_value', 'SEXO'], how='left', validate='many_to_one', sort=False)
    require(frame.row_id.equals(pd.Series(make_ids(reference, KEYS, 'exact_age'), name='row_id').reset_index(drop=True)), 'Orden alterado al añadir referencia.')
    frame['participation_deviation_exact'] = frame.participation_observed-frame.national_participation_exact
    frame['in_age_scope'] = frame.age_value.between(18, 100)
    frame['has_complete_features'] = np.isfinite(frame[FEATURES].to_numpy(dtype=float)).all(axis=1)
    frame['has_sufficient_support'] = frame.LN.ge(MAIN_THRESHOLD) & frame.specified_count.ge(MAIN_THRESHOLD) & frame.source_row_count.ge(MIN_SOURCE_ROWS)
    frame['is_eligible'] = frame.in_age_scope & frame.has_complete_features & frame.has_sufficient_support
    frame['pending_reason'] = np.select([~frame.in_age_scope, ~frame.has_complete_features, ~frame.has_sufficient_support],
        ['age_over_100_complementary', 'undefined_features', 'low_support'], default='eligible')
    return frame, national


def support_mask(frame, count_threshold, source_threshold=MIN_SOURCE_ROWS):
    return (frame.in_age_scope & frame.has_complete_features & frame.LN.ge(count_threshold) &
        frame.specified_count.ge(count_threshold) & frame.source_row_count.ge(source_threshold)).to_numpy()


def support_review(frame):
    """Compara umbrales sin retirar ni modificar ninguna observación guardada."""
    core = frame.in_age_scope
    available_municipalities = frame.groupby(MUNICIPAL_KEYS).ngroups
    scenarios = [(threshold, MIN_SOURCE_ROWS) for threshold in THRESHOLDS]
    scenarios += [(MAIN_THRESHOLD, count) for count in [1, 10]]
    rows = []
    for threshold, source_threshold in scenarios:
        mask = support_mask(frame, threshold, source_threshold)
        selected = frame.loc[mask]
        rows.append(dict(count_threshold=threshold, source_threshold=source_threshold,
            eligible_segments=len(selected), segment_fraction_core=len(selected)/core.sum(),
            municipalities=selected.groupby(MUNICIPAL_KEYS).ngroups,
            municipality_fraction=selected.groupby(MUNICIPAL_KEYS).ngroups/available_municipalities,
            LN=int(selected.LN.sum()), nominal_fraction_all=selected.LN.sum()/frame.LN.sum(),
            nominal_fraction_core=selected.LN.sum()/frame.loc[core, 'LN'].sum(),
            excluded_core_segments=int(core.sum()-mask.sum()), excluded_core_LN=int(frame.loc[core & ~mask, 'LN'].sum()),
            high_ns_segments=int(selected.unspecified_rate.ge(.1).sum())))
    age_rows = []
    for (age, sex), group in frame.loc[core].groupby(['age_value', 'SEXO'], observed=True):
        eligible = group[group.is_eligible]
        age_rows.append(dict(age_value=age, SEXO=sex, available_segments=len(group), eligible_segments=len(eligible),
            municipalities=group.groupby(MUNICIPAL_KEYS).ngroups, eligible_municipalities=eligible.groupby(MUNICIPAL_KEYS).ngroups,
            LN=int(group.LN.sum()), eligible_LN=int(eligible.LN.sum()), nominal_fraction=eligible.LN.sum()/group.LN.sum(),
            undefined_rates=int(group.specified_count.eq(0).sum()),
            high_ns_segments=int(group.unspecified_rate.ge(.1).sum()),
            small_extreme_segments=int((group.specified_count.between(1, 99) & (group.participation_observed.le(.05) | group.participation_observed.ge(.95))).sum())))
    municipalities = frame.groupby(MUNICIPAL_KEYS, as_index=False, observed=True).agg(
        LN=('LN', 'sum'), SV=('SV', 'sum'), NV=('NV', 'sum'), NS=('NS', 'sum'), source_row_count=('source_row_count', 'sum'),
        state_name_label=('state_name_label', 'first'), municipality_name_label=('municipality_name_label', 'first'))
    selected = frame[frame.is_eligible].groupby(MUNICIPAL_KEYS, observed=True, as_index=False).agg(
        eligible_segments=('row_id', 'size'), eligible_LN=('LN', 'sum'), eligible_ages=('age_value', 'nunique'))
    municipalities = municipalities.merge(selected, on=MUNICIPAL_KEYS, how='left', validate='one_to_one')
    # Estos ceros son resúmenes de una selección vacía; no se crean tasas o segmentos.
    for column in ['eligible_segments', 'eligible_LN', 'eligible_ages']:
        municipalities[column] = municipalities[column].fillna(0).astype('int64')
    municipalities['nominal_fraction'] = municipalities.eligible_LN/municipalities.LN
    municipalities['has_eligible_segments'] = municipalities.eligible_segments.gt(0)
    municipalities['unspecified_rate'] = ratio(municipalities.NS, municipalities.LN)
    quality_rows = []
    sets = {'all_reference': np.ones(len(frame), dtype=bool), 'age_18_100': core.to_numpy(), 'eligible': frame.is_eligible.to_numpy()}
    for scope, mask in sets.items():
        group = frame.loc[mask]
        quality_rows.append(dict(scope=scope, segments=len(group), LN=int(group.LN.sum()),
            specified_count=int(group.specified_count.sum()), source_row_count=int(group.source_row_count.sum()),
            null_rates=int(group.specified_count.eq(0).sum()), low_support=int((~group.has_sufficient_support).sum()),
            high_ns=int(group.unspecified_rate.ge(.1).sum()), ns_nominal_fraction=group.NS.sum()/group.LN.sum(),
            ns_q1=group.unspecified_rate.quantile(.25), ns_median=group.unspecified_rate.median(), ns_q3=group.unspecified_rate.quantile(.75),
            LN_q1=group.LN.quantile(.25), LN_median=group.LN.median(), LN_q3=group.LN.quantile(.75),
            specified_q1=group.specified_count.quantile(.25), specified_median=group.specified_count.median(), specified_q3=group.specified_count.quantile(.75),
            small_extreme=int((group.specified_count.between(1, 99) & (group.participation_observed.le(.05) | group.participation_observed.ge(.95))).sum())))
    return pd.DataFrame(rows), pd.DataFrame(age_rows), municipalities, pd.DataFrame(quality_rows)


def paired_matrices(frame, scaler):
    e1 = transform(frame[FEATURES].to_numpy(dtype=float), scaler)
    require(np.isfinite(e1).all(), 'Características no finitas en población declarada.')
    return {'e1': e1, 'e2': scalar_engine(e1[:, 1])}


def municipality_exclusions(full, municipalities):
    """Distingue pérdida por no especificación, conteos y filas fuente.

    Clasificación diagnóstica exhaustiva; no cambia el criterio de elegibilidad.
    Un municipio puede tener mucho LN y aun fallar sólo en filas fuente.
    """
    core = full.loc[full.in_age_scope].copy()
    core['has_count_support'] = core.LN.ge(MAIN_THRESHOLD) & core.specified_count.ge(MAIN_THRESHOLD)
    groups = core.groupby(MUNICIPAL_KEYS, observed=True, as_index=False).agg(
        scope_specified_count=('specified_count', 'sum'), count_supported_segments=('has_count_support', 'sum'),
        maximum_source_rows=('source_row_count', 'max'))
    result = municipalities.merge(groups, on=MUNICIPAL_KEYS, how='left', validate='one_to_one')
    require(result.scope_specified_count.notna().all(), 'Municipio sin referencia de edades en alcance.')
    result['exclusion_reason'] = np.select([result.has_eligible_segments, result.scope_specified_count.eq(0), result.count_supported_segments.gt(0)],
        ['has_eligible_segments', 'all_unspecified', 'source_rows_only'], default='counts_below_threshold')
    return result


def previous_metric_context(root):
    """Reutiliza métricas previas; no compara etiquetas de unidades diferentes."""
    folder = Path(root)/'data/processed/clustering_methods_review/metadata'
    metrics = pd.read_csv(folder/'best_models.csv'); stability = pd.read_csv(folder/'municipal_stability.csv')
    rows = []
    for item in metrics.itertuples():
        samples = stability[stability.representation.eq(item.representation) & stability.k.eq(item.k)]
        rows.append(dict(representation=item.representation.upper(), k=item.k, silhouette_exact=item.silhouette_exact,
            age_r2=item.age_r2, oob_median=samples.ari_oob.median(), oob_minimum=samples.ari_oob.min(),
            municipal_replicates=samples.replicate.nunique()))
    return pd.DataFrame(rows)


def shared_bank(matrices, k, seed):
    bank = initialization_bank({'absolute': matrices['e1'], 'relative': matrices['e2']}, k, seed, 10)
    for item in bank: item['source'] = 'e1' if item['source'] == 'absolute' else 'e2'
    return bank


def save_features(full, output):
    """Escribe matrices nuevas desde un destino vacío, ajustando sólo elegibles."""
    folder = Path(output)/'features'; folder.mkdir(parents=True, exist_ok=True)
    mask = full.is_eligible.to_numpy()
    scaler = fit_scaler(full.loc[mask, FEATURES].to_numpy(dtype=float), 'standard')
    training_hash = hashlib.sha256('\n'.join(full.loc[mask, 'row_id']).encode()).hexdigest()
    for representation, columns in [('e1', FEATURES), ('e2', FEATURES[1:])]:
        parameters = scaler if representation == 'e1' else dict(method='standard', location=[scaler['location'][1]], scale=[scaler['scale'][1]])
        require(not (folder/f'{representation}_scaler.json').exists(), 'No sobrescribir escaladores.')
        save_json(folder/f'{representation}_scaler.json', dict(**parameters, feature_columns=columns,
            training_row_ids_sha256=training_hash, fitted_on='eligible_exact_segments_only'))
        values = pd.DataFrame(transform(full[columns].to_numpy(dtype=float), parameters), columns=columns)
        values.insert(0, 'row_id', full.row_id)
        save_table(folder/f'{representation}_standardized.parquet', values)
    return scaler, training_hash


def anchor_silhouettes(values, partitions, anchors, block_size=32):
    """S de cada ancla contra TODOS los segmentos; nunca reserva M×N completo.

    Reutiliza cada bloque de distancias para múltiples semillas/K. Memoria de
    distancias O(BN), más indicadores N×ΣK. No calcula S exacto para no-anclas.
    """
    values, anchors = np.asarray(values, dtype=float), np.asarray(anchors, dtype=int)
    n = len(values)
    require(block_size > 0 and len(anchors) >= 2 and len(np.unique(anchors)) == len(anchors), 'Anclas/bloque no válidos.')
    require(((anchors >= 0) & (anchors < n)).all() and np.isfinite(values).all(), 'Índices o valores no válidos.')
    encodings, counts, slices, columns = {}, {}, {}, []
    start_column = 0
    for name, labels in partitions.items():
        require(len(labels) == n, 'Partición no alineada.')
        _, encoded = np.unique(labels, return_inverse=True); k = encoded.max()+1
        require(2 <= k < n, 'Silhouette requiere 2…N−1 grupos.')
        encodings[name] = encoded; counts[name] = np.bincount(encoded)
        columns.append(np.eye(k)[encoded]); slices[name] = slice(start_column, start_column+k); start_column += k
    indicator = np.ascontiguousarray(np.column_stack(columns)); del columns
    scores = {name: np.empty(len(anchors)) for name in partitions}
    for start in range(0, len(anchors), min(block_size, n-1)):
        stop = min(len(anchors), start+min(block_size, n-1)); indices = anchors[start:stop]
        distances = np.zeros((len(indices), n))
        for column in range(values.shape[1]): distances += (values[indices, column, None]-values[None, :, column])**2
        np.sqrt(distances, out=distances)
        sums = distances@indicator
        for name in partitions:
            own_group = encodings[name][indices]; sizes = counts[name]
            partial = sums[:, slices[name]]; means = partial/sizes
            own = partial[np.arange(len(indices)), own_group]/np.maximum(1, sizes[own_group]-1)
            means[np.arange(len(indices)), own_group] = np.inf; other = means.min(axis=1)
            score = np.divide(other-own, np.maximum(own, other), out=np.zeros(len(indices)), where=np.maximum(own, other) > 0)
            score[sizes[own_group] == 1] = 0.; scores[name][start:stop] = score
    return scores


def db_index(values, labels):
    """Davies–Bouldin usual sobre toda la población, sólo K×K distancias."""
    _, encoded = np.unique(labels, return_inverse=True); k = encoded.max()+1
    require(2 <= k < len(values), 'DB requiere al menos dos grupos.')
    centers = np.array([values[encoded == group].mean(axis=0) for group in range(k)])
    scatter = np.array([np.linalg.norm(values[encoded == group]-centers[group], axis=1).mean() for group in range(k)])
    distances = np.linalg.norm(centers[:, None]-centers[None, :], axis=2)
    if (distances[~np.eye(k, dtype=bool)] <= 1e-14).any(): return np.nan
    np.fill_diagonal(distances, np.inf)
    return float(((scatter[:, None]+scatter[None, :])/distances).max(axis=1).mean())


def exact_age_diagnostics(frame, values, labels):
    """Dependencia de edad y diferencias dentro de cada edad/sexo, sin bandas."""
    weights = np.ones(len(frame)); labels = np.asarray(labels, dtype=int); k = labels.max()+1
    cells = pd.factorize(pd.MultiIndex.from_frame(frame[['age_value', 'SEXO']]))[0]
    rate = frame.participation_observed.to_numpy(); delta = frame.participation_deviation_exact.to_numpy()
    baseline = weighted_group_sse(rate, cells, weights)
    require(np.isclose(baseline, weighted_group_sse(delta, cells, weights), rtol=1e-9, atol=1e-9), 'Referencia no constante dentro de edad/sexo.')
    after = weighted_group_sse(rate, cells*k+labels, weights)
    between = [np.sum((values[:, c]-values[:, c].mean())**2)-weighted_group_sse(values[:, c], labels, weights) for c in range(2)]
    return dict(age_r2=explained_fraction(frame.age_value.to_numpy(), labels, weights),
        absolute_rate_r2=explained_fraction(rate, labels, weights), relative_rate_r2=explained_fraction(delta, labels, weights),
        within_age_sex_rate_r2=1-after/baseline if baseline > 1e-14 else np.nan,
        age_share_between=between[0]/sum(between) if sum(between) > 1e-14 else np.nan)


def cluster_profiles(training, labels, representation, k, seed):
    """Perfiles de segmentos agregados; nunca se reconstruyen personas."""
    frame = training.copy(); frame['cluster'] = labels; frame['is_woman'] = frame.SEXO.eq('1')
    frame['high_ns'] = frame.unspecified_rate.ge(.1)
    summary = frame.groupby('cluster', as_index=False, observed=True).agg(
        observations=('row_id', 'size'), **{field: (field, 'sum') for field in METRICS},
        mean_age=('age_value', 'mean'), age_min=('age_value', 'min'), age_q1=('age_value', lambda v: v.quantile(.25)),
        age_median=('age_value', 'median'), age_q3=('age_value', lambda v: v.quantile(.75)), age_max=('age_value', 'max'),
        mean_delta=('participation_deviation_exact', 'mean'), mean_participation=('participation_observed', 'mean'),
        women_fraction=('is_woman', 'mean'), high_ns_fraction=('high_ns', 'mean'))
    summary['participation_observed'] = ratio(summary.SV, summary.SV+summary.NV)
    summary['unspecified_rate'] = ratio(summary.NS, summary.LN)
    municipal = frame.groupby(['cluster', *MUNICIPAL_KEYS], observed=True, as_index=False).agg(
        segments=('row_id', 'size'), LN=('LN', 'sum'), SV=('SV', 'sum'), NV=('NV', 'sum'), NS=('NS', 'sum'))
    summary = summary.merge(municipal.groupby('cluster', as_index=False).agg(municipalities=('segments', 'size')), on='cluster', validate='one_to_one')
    age_sex = frame.groupby(['cluster', 'age_value', 'SEXO'], observed=True, as_index=False).agg(
        observations=('row_id', 'size'), **{field: (field, 'sum') for field in METRICS},
        mean_delta=('participation_deviation_exact', 'mean'))
    age_sex['participation_observed'] = ratio(age_sex.SV, age_sex.SV+age_sex.NV)
    for table in [summary, municipal, age_sex]:
        table.insert(0, 'seed', seed); table.insert(0, 'k', k); table.insert(0, 'representation', representation)
    require(summary[METRICS].sum().equals(training[METRICS].sum()), 'Conteos por cluster no concilian.')
    return summary, municipal, age_sex


def fit_models(full, scaler, output, anchor_count=512):
    mask = full.is_eligible.to_numpy(); training = full.loc[mask].reset_index(drop=True)
    matrices = paired_matrices(training, scaler)
    anchors = anchor_sample(training.row_id, anchor_count)
    save_table(output/'metadata/silhouette_anchors.parquet', training.iloc[anchors][['row_id', *KEYS]])
    banks = {(k, seed): shared_bank(matrices, k, seed) for k in KS for seed in SEEDS}
    save_json(output/'metadata/initialization_banks.json', [dict(k=k, seed=seed, initialization=index,
        source=item['source'], initial_seed=item['initial_seed'], positions=item['indices'].tolist(),
        row_ids=training.iloc[item['indices']].row_id.tolist())
        for (k, seed), bank in banks.items() for index, item in enumerate(bank)])
    models, rows, validations, trials, centers = {}, [], [], [], []
    for representation in ['e1', 'e2']:
        labels = full[['row_id', *KEYS, 'is_eligible', 'pending_reason']].copy()
        for k in KS:
            for seed in SEEDS:
                fitted = fit_bank(matrices[representation], np.ones(len(training)), banks[k, seed])
                models[representation, k, seed] = fitted
                numerical = pandas_numerical_check(matrices[representation], np.ones(len(training)), fitted['labels'], fitted['centers'], fitted['inertia'])
                validations.append(dict(representation=representation, k=k, seed=seed, **numerical))
                labels[f'k{k:02d}_seed{seed}'] = nullable_labels(full, mask, fitted['labels'])
                rows.append(dict(representation=representation, k=k, seed=seed, n=len(training), LN=int(training.LN.sum()),
                    municipalities=training.groupby(MUNICIPAL_KEYS).ngroups, sse=fitted['inertia'],
                    converged=fitted['converged'], iterations=fitted['iterations'],
                    minimum_cluster=int(np.bincount(fitted['labels']).min()), maximum_cluster=int(np.bincount(fitted['labels']).max()),
                    davies_bouldin=db_index(matrices[representation], fitted['labels']),
                    **exact_age_diagnostics(training, matrices[representation], fitted['labels'])))
                trials.extend(dict(representation=representation, k=k, seed=seed, **item) for item in fitted['initializations'])
                for group, center in enumerate(fitted['centers']):
                    centers.append(dict(representation=representation, k=k, seed=seed, cluster=group,
                        age_z=center[0] if representation == 'e1' else np.nan,
                        age_original=center[0]*scaler['scale'][0]+scaler['location'][0] if representation == 'e1' else np.nan,
                        delta_z=center[1], delta_original=center[1]*scaler['scale'][1]+scaler['location'][1]))
            print(f'{representation}: K={k}, tres semillas, diez arranques; n={len(training):,}.', flush=True)
        save_table(output/'models'/representation/'labels.parquet', labels)
        partitions = {f'k{k:02d}_seed{seed}': models[representation, k, seed]['labels'] for k in KS for seed in SEEDS}
        anchor_scores = anchor_silhouettes(matrices[representation], partitions, anchors, 32)
        anchor_frame = training.iloc[anchors][['row_id', *KEYS]].reset_index(drop=True).copy()
        for k in KS:
            for seed in SEEDS:
                column = f'k{k:02d}_seed{seed}'; scores = anchor_scores[column]
                anchor_frame[column] = scores
                record = next(row for row in rows if row['representation'] == representation and row['k'] == k and row['seed'] == seed)
                record.update(silhouette_anchors=float(scores.mean()),
                    silhouette_mc_se=float(scores.std(ddof=1)/np.sqrt(len(anchors))*np.sqrt((len(training)-len(anchors))/len(training))),
                    silhouette_anchor_n=len(anchors), silhouette_reference_n=len(training),
                    silhouette_exact=np.nan if representation == 'e1' else float(scalar_silhouette(matrices['e2'][:, 1], models['e2', k, seed]['labels']).mean()))
        save_table(output/'models'/representation/'anchor_silhouettes.parquet', anchor_frame)
        print(f'{representation}: Silhouette de {len(anchors)} anclas contra todos los segmentos, por bloques.', flush=True)
    best = {(representation, k): min(SEEDS, key=lambda seed: models[representation, k, seed]['inertia']) for representation in ['e1', 'e2'] for k in KS}
    summaries, profiles, municipal_tables, age_tables, stability = [], [], [], [], []
    scalar_scores = full[['row_id', *KEYS]].copy()
    for representation in ['e1', 'e2']:
        for k in KS:
            seed = best[representation, k]; fitted = models[representation, k, seed]
            record = next(row for row in rows if row['representation'] == representation and row['k'] == k and row['seed'] == seed)
            comparisons = [adjusted_rand(models[representation, k, a]['labels'], models[representation, k, b]['labels']) for a, b in combinations(SEEDS, 2)]
            summaries.append(dict(record, minimum_seed_ari=min(comparisons)))
            for (a, b), ari in zip(combinations(SEEDS, 2), comparisons):
                stability.append(dict(representation=representation, k=k, left_seed=a, right_seed=b, ari=ari))
            a, b, c = cluster_profiles(training, fitted['labels'], representation, k, seed)
            profiles.append(a); municipal_tables.append(b); age_tables.append(c)
            if representation == 'e2':
                scalar_scores[f'k{k:02d}'] = np.nan
                scalar_scores.loc[mask, f'k{k:02d}'] = scalar_silhouette(matrices['e2'][:, 1], fitted['labels'])
    save_table(output/'models/exact_silhouette_e2.parquet', scalar_scores)
    tables = dict(model_metrics=pd.DataFrame(rows), best_models=pd.DataFrame(summaries), initializations=pd.DataFrame(trials),
        numerical_validation=pd.DataFrame(validations), seed_stability=pd.DataFrame(stability),
        cluster_profiles=pd.concat(profiles, ignore_index=True), cluster_municipalities=pd.concat(municipal_tables, ignore_index=True),
        cluster_age_sex=pd.concat(age_tables, ignore_index=True), centroids=pd.DataFrame(centers))
    for name, table in tables.items(): save_table(output/'metadata'/f'{name}.csv', table)
    return matrices, models, best, tables['best_models']


def municipal_stability(full, models, best, source, output, replicates=5):
    """Prueba limitada con municipios juntos y escaladores ajustados sólo inbag."""
    mask = full.is_eligible.to_numpy(); raw = full.loc[mask].reset_index(drop=True)
    selections = pd.read_parquet(source/'resampling/municipality_membership.parquet')
    columns = [f'sample_{i:03d}' for i in range(replicates)]
    save_table(output/'resampling/municipality_membership.parquet', selections[[*MUNICIPAL_KEYS, *columns]])
    rows, coverage, centroid_rows = [], [], []
    for replicate in range(replicates):
        inside_full = membership(full, selections[MUNICIPAL_KEYS], selections[columns[replicate]].to_numpy())
        inside = inside_full[mask]; oob = ~inside; sample_mask = mask & inside_full
        selected = full.loc[sample_mask].reset_index(drop=True)
        require(len(selected) > 20 and oob.sum() > 20, 'Cobertura insuficiente para submuestreo.')
        scaler = fit_scaler(selected[FEATURES].to_numpy(dtype=float), 'standard')
        matrices = paired_matrices(selected, scaler); projected = paired_matrices(raw, scaler)
        coverage.append(dict(replicate=replicate, drawn_municipalities=int(selections[columns[replicate]].sum()),
            training_municipalities=selected.groupby(MUNICIPAL_KEYS).ngroups,
            oob_municipalities=raw.loc[oob].groupby(MUNICIPAL_KEYS).ngroups,
            training_segments=len(selected), oob_segments=int(oob.sum()), training_LN=int(selected.LN.sum()),
            eligible_nominal_fraction=selected.LN.sum()/raw.LN.sum(), eligible_segment_fraction=len(selected)/len(raw)))
        labels = full[['row_id', *KEYS]].copy(); labels['is_training'] = sample_mask; labels['is_oob_eligible'] = mask & ~inside_full
        for k in KS:
            bank = shared_bank(matrices, k, 17)
            for representation in ['e1', 'e2']:
                fitted = fit_bank(matrices[representation], np.ones(len(selected)), bank)
                predictions, _ = predict(projected[representation], fitted['centers'])
                reference = models[representation, k, best[representation, k]]['labels']
                aligned, _ = align_partition(reference[oob], predictions[oob], k)
                rows.append(dict(replicate=replicate, representation=representation, k=k, n=len(selected), oob_n=int(oob.sum()),
                    sse=fitted['inertia'], converged=fitted['converged'], iterations=fitted['iterations'],
                    ari_all_eligible=adjusted_rand(reference, predictions), ari_oob=adjusted_rand(reference[oob], predictions[oob]),
                    changed_fraction_oob=float((aligned != reference[oob]).mean())))
                labels[f'{representation}_k{k:02d}'] = nullable_labels(full, mask, predictions)
                for group, center in enumerate(fitted['centers']):
                    centroid_rows.append(dict(replicate=replicate, representation=representation, k=k, cluster=group,
                        age_z=center[0] if representation == 'e1' else np.nan, delta_z=center[1]))
        folder = output/'resampling'/f'sample_{replicate:03d}'
        save_table(folder/'labels.parquet', labels)
        save_json(folder/'scaler.json', dict(**scaler, feature_columns=FEATURES, n=len(selected), fitted_on='inbag_eligible_only'))
        print(f'Submuestra municipal {replicate+1}/{replicates}: {len(selected):,} segmentos, {oob.sum():,} OOB.', flush=True)
    stability, coverage = pd.DataFrame(rows), pd.DataFrame(coverage)
    save_table(output/'metadata/municipal_stability.csv', stability); save_table(output/'metadata/resampling_coverage.csv', coverage)
    save_table(output/'metadata/resample_centroids.csv', pd.DataFrame(centroid_rows))
    return stability, coverage


def plot_diagnostics(full, thresholds, ages, municipalities, reference_comparison, matrices, models, best, metrics, stability, profiles, charts):
    fig, ax = plt.subplots(figsize=(10, 5), layout='constrained')
    rows = thresholds[thresholds.source_threshold.eq(MIN_SOURCE_ROWS)].sort_values('count_threshold')
    for field, label in [('nominal_fraction_all', 'LN conservado / LN total'), ('municipality_fraction', 'Municipios representados / 2,477'),
        ('segment_fraction_core', 'Segmentos elegibles / segmentos 18–100')]: ax.plot(rows.count_threshold, rows[field], 'o-', label=label)
    ax.axvline(MAIN_THRESHOLD, color='black', ls=':', label='Piloto: 100'); ax.set_xscale('log'); ax.set_ylim(0, 1.03)
    ax.set_xlabel('Umbral mínimo simultáneo LN y SV+NV (escala logarítmica)'); ax.set_ylabel('Fracción conservada'); ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.legend(fontsize=8); ax.grid(alpha=.2); ax.set_title('Coste de soporte · al menos cinco filas fuente\nNo se eliminan observaciones de las referencias')
    fig.savefig(charts/'support_thresholds.png', dpi=160); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    for sex, color, label in [('0', '#386cb0', 'Hombres'), ('1', '#d95f02', 'Mujeres')]:
        group = ages[ages.SEXO.eq(sex)].sort_values('age_value')
        axes[0].plot(group.age_value, group.eligible_segments/group.available_segments, color=color, label=label)
        axes[1].plot(group.age_value, group.nominal_fraction, color=color, label=label)
    for ax, title in zip(axes, ['Fracción de segmentos con soporte', 'LN conservado dentro de cada edad/sexo']):
        ax.set_title(title); ax.set_xlabel('Edad exacta'); ax.set_ylabel('Fracción elegible'); ax.set_ylim(0, 1.03)
        ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.legend(); ax.grid(alpha=.2)
    fig.suptitle('Soporte exacto 18–100 · LN y SV+NV≥100, filas fuente≥5\nEl cero de cobertura indica selección vacía; no es participación cero')
    fig.savefig(charts/'exact_age_support.png', dpi=160); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), layout='constrained')
    active = municipalities.has_eligible_segments
    axes[0].scatter(municipalities.loc[active, 'LN'], municipalities.loc[active, 'nominal_fraction'], s=8, alpha=.35, label='Con segmentos elegibles')
    axes[0].scatter(municipalities.loc[~active, 'LN'], municipalities.loc[~active, 'nominal_fraction'], s=8, alpha=.4, color='#d95f02', label='Sin segmentos elegibles')
    axes[0].set_xscale('log'); axes[0].set_xlabel('LN municipal total (escala logarítmica)'); axes[0].set_ylabel('LN elegible / LN municipal')
    axes[0].yaxis.set_major_formatter(PercentFormatter(1)); axes[0].legend(fontsize=8)
    states = municipalities.groupby('EDOCVE', observed=True).agg(municipalities=('LN', 'size'), represented=('has_eligible_segments', 'sum'), LN=('LN', 'sum'), eligible_LN=('eligible_LN', 'sum')).sort_index()
    x = np.arange(len(states)); axes[1].bar(x-.18, states.represented/states.municipalities, .36, label='Municipios')
    axes[1].bar(x+.18, states.eligible_LN/states.LN, .36, label='LN')
    axes[1].set_xticks(x, states.index, fontsize=7, rotation=90); axes[1].set_xlabel('Clave de entidad (texto)'); axes[1].set_ylabel('Fracción conservada')
    axes[1].yaxis.set_major_formatter(PercentFormatter(1)); axes[1].legend(fontsize=8)
    fig.suptitle('Sesgo potencial de cobertura · los totales grandes no garantizan representación territorial')
    fig.savefig(charts/'territorial_coverage.png', dpi=160); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    for ax, sex, label in zip(axes, ['0', '1'], ['Hombres', 'Mujeres']):
        group = reference_comparison[reference_comparison.SEXO.eq(sex) & reference_comparison.age_value.between(18, 100)].sort_values('age_value')
        ax.plot(group.age_value, group.national_participation_exact, label='Referencia por edad exacta')
        ax.step(group.age_value, group.national_participation_interval, where='mid', label='Referencia previa por intervalo', ls='--')
        ax.set_title(label); ax.set_xlabel('Edad exacta'); ax.set_ylabel('ΣSV / Σ(SV+NV)'); ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.legend(fontsize=8); ax.grid(alpha=.2)
    fig.suptitle('Referencias calculadas antes de seleccionar soporte\nCambiar de intervalo a edad exacta también cambia el contexto nacional')
    fig.savefig(charts/'national_references.png', dpi=160); plt.close(fig)

    fig, axes = plt.subplots(2, 5, figsize=(20, 10), layout='constrained')
    for column, k in enumerate(KS):
        for row, representation in enumerate(['e1', 'e2']):
            ax = axes[row, column]; fitted = models[representation, k, best[representation, k]]; values = matrices[representation]
            if representation == 'e1':
                for cluster in range(k):
                    chosen = fitted['labels'] == cluster
                    ax.scatter(values[chosen, 0], values[chosen, 1], s=1, alpha=.1, color=COLORS[cluster], rasterized=True)
                ax.scatter(fitted['centers'][:, 0], fitted['centers'][:, 1], color='black', marker='X', s=35)
                bounds = [values[:, 0].min()-.1, values[:, 0].max()+.1, values[:, 1].min()-.1, values[:, 1].max()+.1]
                for edge in decision_edges(fitted['centers'], bounds): ax.plot([edge['x1'], edge['x2']], [edge['y1'], edge['y2']], color='black', lw=.7)
                ax.set_xlim(bounds[:2]); ax.set_ylim(bounds[2:]); ax.set_aspect('equal', adjustable='box')
                ax.set_xlabel('Edad exacta z'); ax.set_ylabel('Diferencia exacta nacional z')
            else:
                bins = np.linspace(values[:, 1].min(), values[:, 1].max(), 90)
                ax.hist([values[fitted['labels'] == group, 1] for group in range(k)], bins=bins, stacked=True, color=COLORS[:k], alpha=.8)
                centers = np.sort(fitted['centers'][:, 1])
                for boundary in (centers[:-1]+centers[1:])/2: ax.axvline(boundary, color='black', ls='--', lw=.8)
                ax.set_xlabel('Diferencia exacta nacional z'); ax.set_ylabel('Segmentos por barra')
            ax.set_title(f'{representation.upper()} · K={k} · semilla {best[representation, k]}')
    fig.suptitle('Coordenadas estandarizadas reales · igual peso por segmento · sin jitter\nE1 conserva edades enteras; E2 es un control unidimensional; etiquetas locales')
    fig.savefig(charts/'standardized_geometries.png', dpi=160); plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(14, 8), layout='constrained')
    fields = [('silhouette_anchors', 'Silhouette: mismas anclas contra todos'), ('davies_bouldin', 'Davies–Bouldin: toda la población'),
        ('age_r2', 'Varianza de edad explicada por etiquetas'), ('age_share_between', 'Edad / separación estandarizada'),
        ('within_age_sex_rate_r2', 'Separación de tasa dentro de edad/sexo'), ('minimum_seed_ari', 'ARI mínimo entre semillas')]
    for ax, (field, title) in zip(axes.ravel(), fields):
        for representation, color in [('e1', '#386cb0'), ('e2', '#d95f02')]:
            group = metrics[metrics.representation.eq(representation)].sort_values('k')
            ax.errorbar(group.k, group[field], yerr=group.silhouette_mc_se if field == 'silhouette_anchors' else None,
                fmt='o-', color=color, label=representation.upper(), capsize=3)
        ax.set_title(title, fontsize=10); ax.set_xticks(KS); ax.set_xlabel('K (6 sensibilidad)'); ax.legend(); ax.grid(alpha=.2)
        if field in ['age_r2', 'age_share_between', 'within_age_sex_rate_r2']: ax.yaxis.set_major_formatter(PercentFormatter(1))
        if field == 'minimum_seed_ari': ax.set_ylim(0, 1.02)
    fig.suptitle('Métricas de menor SSE · barras S = un error Monte Carlo de anclas, no incertidumbre electoral\nNo usar un índice interno para declarar una representación superior')
    fig.savefig(charts/'metric_comparison.png', dpi=160); plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(14, 8), layout='constrained')
    # La frecuencia de edades se obtiene de las etiquetas, sin introducir bandas.
    raw_age = full.loc[full.is_eligible, 'age_value'].to_numpy()
    for row, representation in enumerate(['e1', 'e2']):
        for column, k in enumerate([3, 4, 5]):
            ax = axes[row, column]; labels = models[representation, k, best[representation, k]]['labels']
            for group in range(k):
                counts = pd.Series(raw_age[labels == group]).value_counts().sort_index()
                ax.plot(counts.index, counts/counts.sum(), color=COLORS[group], label=f'c{group} · n={(labels == group).sum():,}')
            ax.set_title(f'{representation.upper()} · K={k}'); ax.set_xlabel('Edad exacta'); ax.set_ylabel('Fracción de segmentos dentro del cluster')
            ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.legend(fontsize=6); ax.grid(alpha=.2)
    fig.suptitle('Distribución de edades por agrupación · etiquetas locales, no perfiles individuales')
    fig.savefig(charts/'cluster_age_distributions.png', dpi=160); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    for ax, field, title in [(axes[0], 'ari_oob', 'ARI sobre municipios OOB'), (axes[1], 'changed_fraction_oob', 'Cambio alineado en OOB')]:
        arrays, labels = [], []
        for k in KS:
            for representation in ['e1', 'e2']:
                arrays.append(stability[stability.k.eq(k) & stability.representation.eq(representation)][field].to_numpy()); labels.append(f'{representation.upper()}\nK={k}')
        result = ax.boxplot(arrays, tick_labels=labels, patch_artist=True)
        for i, box in enumerate(result['boxes']): box.set_facecolor('#386cb0' if i % 2 == 0 else '#d95f02'); box.set_alpha(.5)
        ax.set_title(title); ax.set_ylim(0, 1.02); ax.grid(axis='y', alpha=.2)
        if field == 'changed_fraction_oob': ax.yaxis.set_major_formatter(PercentFormatter(1))
    fig.suptitle(f'Prueba limitada de estabilidad municipal · {stability.replicate.nunique()} submuestras del 80 %\nResumen exploratorio, sin intervalos de confianza ni garantía de estabilidad futura')
    fig.savefig(charts/'municipal_stability.png', dpi=160); plt.close(fig)


def write_report(output, charts, report, full, thresholds, ages, municipalities, quality, metrics, stability, coverage, reference_comparison, prior_comparison, protected_count):
    def picture(name, title): return f'![{title}]({os.path.relpath(charts/name, report.parent).replace(chr(92), "/")})'
    training = full[full.is_eligible]; core = full[full.in_age_scope]
    main = thresholds[thresholds.count_threshold.eq(MAIN_THRESHOLD) & thresholds.source_threshold.eq(MIN_SOURCE_ROWS)].iloc[0]
    threshold_rows = [[r.count_threshold, r.source_threshold, number(r.eligible_segments), pct(r.segment_fraction_core),
        number(r.municipalities), pct(r.municipality_fraction), number(r.LN), pct(r.nominal_fraction_all), number(r.excluded_core_LN)] for r in thresholds.itertuples()]
    metric_rows = []
    for row in metrics.itertuples():
        samples = stability[stability.representation.eq(row.representation) & stability.k.eq(row.k)]
        metric_rows.append([row.representation.upper(), row.k, row.seed, f'{row.silhouette_anchors:.4f} ± {row.silhouette_mc_se:.4f}',
            'n/d' if pd.isna(row.silhouette_exact) else f'{row.silhouette_exact:.4f}', f'{row.davies_bouldin:.4f}',
            number(row.minimum_cluster), number(row.maximum_cluster), f'{row.minimum_seed_ari:.3f}',
            f'{samples.ari_oob.median():.3f}', f'{samples.ari_oob.min():.3f}', pct(row.age_r2), pct(row.age_share_between), pct(row.within_age_sex_rate_r2)])
    age_totals = ages.groupby('age_value', as_index=False).agg(available_segments=('available_segments', 'sum'), eligible_segments=('eligible_segments', 'sum'),
        LN=('LN', 'sum'), eligible_LN=('eligible_LN', 'sum'), undefined_rates=('undefined_rates', 'sum'), small_extreme=('small_extreme_segments', 'sum'))
    age_rows = [[r.age_value, number(r.available_segments), number(r.eligible_segments), number(r.LN), number(r.eligible_LN), pct(r.eligible_LN/r.LN), number(r.undefined_rates), number(r.small_extreme)]
        for r in age_totals[age_totals.age_value.isin([18, 25, 40, 60, 70, 80, 90, 95, 98, 99, 100])].itertuples()]
    quality_rows = [[r.scope, number(r.segments), number(r.null_rates), number(r.low_support), number(r.small_extreme), number(r.high_ns),
        pct(r.ns_nominal_fraction), pct(r.ns_q1), pct(r.ns_median), pct(r.ns_q3), f'{r.LN_q1:g}/{r.LN_median:g}/{r.LN_q3:g}',
        f'{r.specified_q1:g}/{r.specified_median:g}/{r.specified_q3:g}'] for r in quality.itertuples()]
    profiles = pd.read_csv(output/'metadata/cluster_profiles.csv')
    profile_rows = [[r.representation.upper(), r.k, r.cluster, number(r.observations), number(r.municipalities),
        f'{r.age_q1:.0f}/{r.age_median:.0f}/{r.age_q3:.0f}', pct(r.women_fraction), pct(r.participation_observed),
        f'{100*r.mean_delta:.2f}', pct(r.unspecified_rate), pct(r.high_ns_fraction)] for r in profiles[profiles.k.isin([3, 4, 5])].itertuples()]
    prior_rows = [[r.representation, number(r.segments), number(r.municipalities), pct(r.nominal_fraction), r.unit, r.reference]
        for r in prior_comparison.itertuples()]
    excluded = municipalities[~municipalities.has_eligible_segments]
    exclusions = pd.read_parquet(output/'metadata/municipality_exclusions.parquet')
    reason_summary = exclusions[~exclusions.has_eligible_segments].groupby('exclusion_reason', as_index=False).agg(municipalities=('LN', 'size'), LN=('LN', 'sum'))
    reason_labels = {'counts_below_threshold': 'Conteos insuficientes', 'source_rows_only': 'Sólo filas fuente insuficientes', 'all_unspecified': 'Todo no especificado en 18–100'}
    reason_rows = [[reason_labels[r.exclusion_reason], number(r.municipalities), number(r.LN)] for r in reason_summary.itertuples()]
    previous = pd.read_csv(output/'metadata/prior_metric_context.csv')
    previous_rows = [[r.representation, r.k, f'{r.silhouette_exact:.4f}', pct(r.age_r2), f'{r.oob_median:.3f}', f'{r.oob_minimum:.3f}', r.municipal_replicates]
        for r in previous[previous.k.isin([3, 4, 5])].itertuples()]
    lost_rows = [[r.EDOCVE, r.MPIOCVE, r.municipality_name_label, number(r.LN), pct(r.unspecified_rate)]
        for r in excluded.sort_values(['LN', 'EDOCVE', 'MPIOCVE'], ascending=[False, True, True]).head(10).itertuples()]
    states = municipalities.groupby('EDOCVE', as_index=False).agg(municipalities=('LN', 'size'), represented=('has_eligible_segments', 'sum'), LN=('LN', 'sum'), eligible_LN=('eligible_LN', 'sum'))
    states['coverage'] = states.represented/states.municipalities
    state_rows = [[r.EDOCVE, number(r.municipalities), number(r.represented), pct(r.coverage), pct(r.eligible_LN/r.LN)]
        for r in states.sort_values(['coverage', 'EDOCVE']).head(8).itertuples()]
    relative_reference = reference_comparison[reference_comparison.age_value.between(18, 100) & reference_comparison.SEXO.isin(['0', '1'])]
    maximum_reference_difference = relative_reference.reference_difference.abs().max()
    weighted_reference_difference = np.average(relative_reference.reference_difference.abs(), weights=relative_reference.LN)
    e1, e2 = [metrics[metrics.representation.eq(name)] for name in ['e1', 'e2']]
    e1_by_k = e1.set_index('k'); e2_by_k = e2.set_index('k')
    e1_best_anchor = e1.loc[e1.silhouette_anchors.idxmax()]
    e2_best_exact = e2.loc[e2.silhouette_exact.idxmax()]
    sample_group = lambda representation, k: stability[stability.representation.eq(representation) & stability.k.eq(k)].ari_oob
    anchors = int(metrics.silhouette_anchor_n.iloc[0]); replicate_count = stability.replicate.nunique()
    missing_ages = age_totals.loc[age_totals.eligible_segments.eq(0), 'age_value'].tolist()
    text = f'''# Piloto con edades exactas · K-Means 2024

## Resultado y alcance territorial

**Se retiran las cinco bandas de las características y se conservan edades enteras, pero la cobertura cae de forma importante.** El principal tiene **{len(training):,} segmentos de {int(main.municipalities):,} municipios**, {pct(main.municipality_fraction)} de los 2,477 observados, con LN={int(main.LN):,} ({pct(main.nominal_fraction_all)} del LN total de 2024). Sólo {pct(main.segment_fraction_core)} de los segmentos disponibles 18–100 supera el soporte. La presencia de mucho LN no equivale a cobertura territorial suficiente.

Se comunicó esta limitación antes del ajuste: **el piloto describe un subconjunto con soporte, insuficiente para generalizar perfiles a todos los municipios o edades**. No se relajó el umbral para obtener mejores índices ni se selecciona un modelo definitivo. Las edades sin segmentos elegibles son {', '.join(map(str, missing_ages)) or 'ninguna'}; el máximo entrenado es {int(training.age_value.max())}. Las observaciones pendientes siguen conservadas.

Se comparan **E1: edad exacta + diferencia nacional de esa misma edad/sexo**, y **E2: sólo la diferencia exacta**. E1 tiene {training.age_value.nunique()} edades distintas, no cinco edades medias. Las columnas finas que puedan verse corresponden a años enteros reales, sin jitter. E2 es un control unidimensional de niveles relativos, no un perfil demográfico multivariable.

## Esquema real y unidad de análisis

Se confirmó el esquema Arrow de exact_age_2024.parquet: **401,486 filas y 35 columnas**, ya únicas por election_year/EDOCVE/MPIOCVE/age_value/SEXO. age_value es int64, no existe una columna EDAD en ese archivo; las claves EDOCVE, MPIOCVE y SEXO son texto, LN/SV/NV/NS/source_row_count son int64 y las tasas double. El año es int16. Se guarda el esquema completo en metadata/input_schema.json.

Cada fila ya representa municipio + sexo + edad exacta. Se verificó unicidad y se reutilizaron sus conteos sin volver a sumar una unidad duplicada. Se recalcula SV/(SV+NV), NULL cuando SV+NV=0, y se comprueba contra la tasa almacenada. No se releen CSV ni los 54 millones de registros; los hashes de archivos originales son lecturas binarias de integridad.

Se conserva la referencia completa de {len(full):,} segmentos, LN={int(full.LN.sum()):,}, SV={int(full.SV.sum()):,}, NV={int(full.NV.sum()):,}, NS={int(full.NS.sum()):,} y {int(full.source_row_count.sum()):,} filas fuente representadas. Los segmentos 18–100 son {len(core):,}, LN={int(core.LN.sum()):,}, en 2,477 municipios. Las edades >100 y SEXO=2 mantienen conteos y trazabilidad; SEXO=2 conserva 99 segmentos, 105 filas fuente y LN=105. Su soporte no permite entrar en el principal, sin recodificar H/M ni inventar observaciones. Las referencias cartográficas y las etiquetas de intervalos heredadas se guardan sólo como metadatos.

## Soporte antes de entrenar

El criterio principal conserva el contrato exploratorio: **LN≥100, SV+NV≥100 y filas fuente≥5**, además de edad 18–100 y características finitas. Es una regla operativa de revisión, no una prueba de error ni un intervalo de confianza. Las filas fuente son celdas electorales agregadas, no personas independientes. Una combinación ausente no se rellena con conteos cero.

{markdown_table(['LN y SV+NV mín.', 'Filas fuente mín.', 'Segmentos', '% de 18–100', 'Municipios', '% municipios', 'LN elegible', '% LN total', 'LN 18–100 pendiente'], threshold_rows)}

Las últimas dos filas aíslan la sensibilidad de filas fuente con umbral de conteos fijo. Cada escenario es una selección diagnóstica separada; sus conteos no se suman. Sólo el criterio 100/5 se utiliza para modelos; los demás umbrales no se eligen por Silhouette. Los {len(full)-len(training):,} pendientes de la referencia completa se guardan con razones y etiquetas NULL.

{picture('support_thresholds.png', 'Coste de distintos umbrales')}

### Edades, denominadores pequeños y NS

{markdown_table(['Edad', 'Segmentos disponibles', 'Elegibles', 'LN disponible', 'LN elegible', '% LN de esa edad', 'Tasas NULL', 'Extremas y denominador<100'], age_rows)}

Se define tasa extrema sólo para este diagnóstico como ≤5 % o ≥95 %, con SV+NV positivo; denominador pequeño es <100. No se interpreta como error. Los diagnósticos incluyen todas las categorías de sexo presentes. Los conteos de edades/sexos completos están en age_support.csv, incluidos los ceros de selección; no son tasas imputadas.

{markdown_table(['Universo', 'Segmentos', 'Tasas NULL', 'Soporte bajo', 'Extremas y denom.<100', 'NS≥10 %', 'ΣNS/ΣLN', 'NS/LN Q1', 'Mediana', 'Q3', 'LN Q1/med./Q3', 'SV+NV Q1/med./Q3'], quality_rows)}

NS no se suma a NV ni se interpreta como abstención. Su cociente nacional y la distribución de cocientes por segmento responden a ponderaciones distintas. Los umbrales son banderas descriptivas; se mantienen todos los casos, incluidos los extremos. Las edades más avanzadas y territorios pequeños aportan muchas celdas con poco soporte, mientras el entrenamiento se concentra en territorios con más conteos.

{picture('exact_age_support.png', 'Soporte por edad exacta y sexo')}

### Municipios que pierden soporte

**{len(excluded):,} municipios quedan sin ningún segmento entrenable**; otros pierden una parte de sus edades. municipality_coverage.parquet conserva los 2,477 municipios con conteos, número de edades elegibles y fracción de LN. Un cero de elegibilidad resume una selección vacía, no participación cero. Los diez de mayor LN sin segmentos elegibles son ejemplos deterministas, no territorios señalados como erróneos:

{markdown_table(['Entidad', 'Municipio', 'Etiqueta municipal', 'LN total', 'NS/LN'], lost_rows)}

La pérdida no se explica sólo por municipios pequeños. La siguiente clasificación es exhaustiva para los municipios sin segmentos elegibles y se guarda en municipality_exclusions.parquet:

{markdown_table(['Motivo diagnóstico', 'Municipios', 'LN total'], reason_rows)}

Carmen (19/10) tiene LN=48,786 y 93 segmentos con LN y SV+NV≥100, pero un máximo de cuatro filas fuente por segmento: falla únicamente el mínimo de cinco. Así, filas fuente no equivale a tamaño nominal ni a observaciones personales independientes. Antes de cambiar esa regla debe decidirse si se exige amplitud de celdas fuente, tamaño de denominador u otro objetivo de calidad; aquí se conserva el contrato existente. Entre municipios representados, la mediana de edades exactas con soporte es {municipalities.loc[municipalities.has_eligible_segments, 'eligible_ages'].median():.0f} de las 83 posibles, de modo que estar representado no significa tener un perfil etario completo.

Entidades con menor fracción de municipios representados (claves como texto):

{markdown_table(['Entidad', 'Municipios observados', 'Representados', '% municipios', '% LN de entidad'], state_rows)}

{picture('territorial_coverage.png', 'Cobertura municipal y por entidad')}

## Referencia nacional exacta y estandarización

La nueva referencia es **ΣSV/Σ(SV+NV) por edad exacta y sexo**, calculada con todos los conteos originales agregados de 2024, antes de seleccionar soporte. Se suman conteos primero y no se promedian tasas municipales. Los grupos con denominador cero quedan NULL. Se verifican sus sumas, el enlace many-to-one y LN=SV+NV+NS. Un mismo año/edad/sexo tiene exactamente la misma referencia para todos los municipios.

**No es la referencia anterior por intervalos.** En H/M entre 18 y 100, la máxima diferencia absoluta entre referencias es {100*maximum_reference_difference:.2f} pp; la media absoluta ponderada por LN de los grupos nacionales es {100*weighted_reference_difference:.2f} pp. national_reference_comparison.csv permite localizar cada edad y sexo. Las referencias de categorías escasas se conservan aparte y no se convierten en tendencias comparables por defecto.

{picture('national_references.png', 'Referencia exacta frente a referencia por intervalo')}

Se ajusta StandardScaler, media y DE poblacional ddof=0, **sólo sobre el universo elegible común**. E2 hereda exactamente los parámetros de la segunda coordenada E1; ninguna fila se gana o pierde al retirar edad. Los parámetros, columnas y hash del orden de row_id quedan guardados. Pendientes no participan en el ajuste del escalador. Las tasas siguen expresadas en proporciones; los gráficos usan pp o porcentajes cuando se indica. [Definición de StandardScaler](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html).

E2 se adapta internamente como [0, diferencia_z] al Lloyd de dos columnas ya probado; la constante no aporta distancia ni se guarda como característica. Edad, sexo, claves y conteos quedan en metadatos. El archivo de características E1 contiene dos variables estandarizadas y E2 una, además de row_id para alinear. Las medias nacionales fijas no implican media cero de diferencias en la selección con peso uno por segmento.

## Ajustes K-Means y métricas

Se ejecutan K=2/3/4/5 y 6 sensibilidad, semillas 17/42/2024, diez inicializaciones por ajuste y peso uno por segmento. Cada pareja E1/E2 recibe los mismos índices iniciales, cinco D² originados en cada representación. Lloyd se detiene con asignaciones estables, máximo 1,000 iteraciones. Se utiliza la implementación NumPy ya probada; no se afirma que se haya validado contra scikit-learn en este entorno. Son **30 ajustes completos**, con inicializaciones, centros, SSE, convergencia y etiquetas conservados. [Objetivo de K-Means](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html).

Para describir cada K se usa la menor SSE entre semillas, sin fijar K final. Silhouette principal es **aproximado**, con {anchors} anclas uniformes reproducibles, compartidas E1/E2 y semillas, cada una contra todos los {len(training):,} segmentos. Se calcula en bloques de 32×N, sin matriz N×N ni reservar todo el rectángulo anclas×N. El ± es un error Monte Carlo con corrección por población finita; no es incertidumbre electoral ni incluye perturbación municipal. Davies–Bouldin usa toda la población. Para E2 se calcula además Silhouette individual exacto mediante sumas ordenadas de distancias absolutas, sin matriz completa; se conserva separado. [Silhouette](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html).

{markdown_table(['Representación', 'K', 'Semilla', 'S anclas ± error MC', 'S exacto E2', 'DB', 'Cluster mín.', 'Máx.', 'ARI semillas mín.', 'OOB mediana', 'OOB mín.', 'R² edad', 'Edad/separación', 'R² tasa dentro edad/sexo'], metric_rows)}

R² edad es la fracción de varianza de edad explicada por las etiquetas; edad/separación es la fracción de separación entre centroides correspondiente a edad en la geometría estandarizada. Ninguna es atribución causal. La mejora de tasa dentro de edad/sexo compara residuos con medias por edad exacta/sexo frente a medias por edad exacta/sexo/cluster. Es descripción in-sample, favorecida por mayor resolución, no validación predictiva. En E2 separar tasas relativas es justamente la única tarea de la distancia.

No todas las soluciones E1 son exclusivamente etarias: edad aporta {pct(e1_by_k.loc[2, 'age_share_between'])} de la separación con K=2, pero {pct(e1_by_k.loc[4, 'age_share_between'])} con K=4 y {pct(e1_by_k.loc[5, 'age_share_between'])} con K=5. En estos últimos casos se combina con niveles de diferencia de participación. El máximo S de anclas E1 aparece en K={int(e1_best_anchor.k)}, aunque las diferencias cercanas deben leerse con su error Monte Carlo. En E2, el S exacto máximo es K={int(e2_best_exact.k)} ({e2_best_exact.silhouette_exact:.4f}); eso no fija un número verdadero de grupos ni justifica forzar cuatro a seis.

{picture('standardized_geometries.png', 'Geometría de edades exactas')}

{picture('metric_comparison.png', 'Métricas E1 y E2')}

## Participación por agrupación

Los perfiles K=3/4/5 se muestran como candidatos descriptivos; los otros K y todos los detalles edad/sexo permanecen en metadata/. Participación agregada = ΣSV/Σ(SV+NV); Δ medio = media con peso uno de diferencias exactas, sin confundir ponderaciones. La edad Q1/mediana/Q3 usa segmentos, no distribución de personas.

{markdown_table(['Representación', 'K', 'Etiqueta local', 'Segmentos', 'Municipios', 'Edad Q1/med./Q3', '% mujeres', 'Participación agregada', 'Δ medio (pp)', 'NS/LN', '% segmentos NS alto'], profile_rows)}

Cada municipio puede aportar segmentos a varios clusters; no se suman municipios entre clusters como territorios únicos. Las etiquetas numéricas son locales a cada ajuste. Los archivos cluster_age_sex.csv y cluster_municipalities.csv preservan conteos y claves para interpretar la cobertura, sin inferir conductas individuales.

{picture('cluster_age_distributions.png', 'Edades dentro de los clusters')}

## Prueba limitada de estabilidad municipal

Se reutilizan las primeras {replicate_count} membresías de las submuestras municipales previas: cada una sortea 1,981 de 2,477 municipios sin reemplazo, incluidos municipios sin segmentos elegibles. Todos los segmentos elegibles de cada municipio entran juntos. Se ajustan {len(stability)} modelos nuevos con semilla 17 y diez arranques comunes por pareja, y se reajustan escalas **sólo inbag**. Las referencias exactas nacionales permanecen fijas e incluyen conteos OOB: es estabilidad contextual, no validación predictiva independiente de la referencia.

La cobertura de ajuste varía entre {int(coverage.training_segments.min()):,} y {int(coverage.training_segments.max()):,} segmentos, {int(coverage.training_municipalities.min()):,}–{int(coverage.training_municipalities.max()):,} municipios con soporte y {pct(coverage.eligible_nominal_fraction.min())}–{pct(coverage.eligible_nominal_fraction.max())} del LN elegible. OOB contiene {int(coverage.oob_segments.min()):,}–{int(coverage.oob_segments.max()):,} segmentos. Los flags distinguen entrenamiento y proyección; los pendientes siguen NULL.

ARI OOB compara sólo segmentos elegibles de municipios no usados para ajustar, respecto al benchmark completo de la misma representación/K. ari_all_eligible utiliza todos los elegibles y se conserva por separado. No se mezclan las bases. Esta prueba limitada permite detectar cambios grandes, pero no caracterizar bien una cola de inestabilidad; medianas y mínimos son descriptivos, no intervalos de confianza ni garantía de estabilidad futura.

En esta prueba, E1–K4 tiene ARI OOB mediano {sample_group('e1', 4).median():.3f} y mínimo {sample_group('e1', 4).min():.3f}; E1–K5 baja a mediana {sample_group('e1', 5).median():.3f}. E2–K5 conserva un mínimo {sample_group('e2', 5).min():.3f} y E2–K6 uno de {sample_group('e2', 6).min():.3f}. Las tres semillas completas son muy concordantes, pero eso no sustituye estabilidad municipal: el mínimo entre semillas es {metrics.minimum_seed_ari.min():.6f} en estos ajustes, mientras las perturbaciones municipales son mayores.

{picture('municipal_stability.png', 'Submuestreo municipal limitado')}

## Comparación contextual con el piloto por intervalos

{markdown_table(['Representación', 'Segmentos entrenados', 'Municipios', '% LN total', 'Unidad', 'Referencia nacional'], prior_rows)}

**No se calcula ARI contra etiquetas anteriores.** Las filas edad exacta y las filas intervalo no tienen correspondencia uno a uno. Tampoco se compara SSE entre representaciones distintas. La lectura contextual compara cobertura, dependencia de edad, métricas con método/denominador explícitos y estabilidad, reconociendo que ahora cambian unidad, referencia nacional, población elegible y escala. Las mejoras o empeoramientos no se atribuyen exclusivamente a quitar intervalos. El piloto anterior utilizó 30 submuestras; esta prueba sólo {replicate_count}, por lo que sus mínimos tampoco son estimaciones de colas equivalentes.

Métricas previas reutilizadas como contexto, **no como un ranking entre unidades diferentes** (Silhouette anterior exacto; E1 actual es de anclas):

{markdown_table(['Representación previa', 'K', 'S exacto previo', 'R² edad previo', 'OOB mediana previa', 'OOB mínimo previo', 'Submuestras previas'], previous_rows)}

Por ejemplo, el S exacto E2 actual con K=4 es {e2_by_k.loc[4, 'silhouette_exact']:.4f} y el R2 previo {previous[previous.representation.eq('R2') & previous.k.eq(4)].silhouette_exact.iloc[0]:.4f}: el detalle exacto no trae una mejora automática de compacidad en ese control. A la vez, el nuevo entrenamiento representa {int(prior_comparison.municipalities.iloc[0]-prior_comparison.municipalities.iloc[1])} municipios menos que el anterior. Son diferencias descriptivas con unidades y referencias distintas, no una prueba estadística de equivalencia o superioridad.

## Respuestas y recomendación provisional

1. **¿Desaparecen las cinco franjas?** Sí, se retiran las cinco edades medias agregadas de las características. Quedan {training.age_value.nunique()} edades enteras entrenadas, con columnas finas naturales de edad en E1. No se añade jitter ni se convierte edad discreta en continua artificialmente.
2. **¿Sigue agrupando por edad?** En E1 las etiquetas explican {pct(e1.age_r2.min())}–{pct(e1.age_r2.max())} de su varianza; edad aporta {pct(e1.age_share_between.min())}–{pct(e1.age_share_between.max())} de la separación estandarizada según K. Por tanto, quitar las bandas no elimina el papel geométrico de edad. En E2 R² edad es {pct(e2.age_r2.min())}–{pct(e2.age_r2.max())}; esa representación retira su contribución directa, pero conserva el contexto edad/sexo de la referencia.
3. **¿Patrones más útiles?** Se gana resolución para describir edades y diferencias dentro de la misma edad/sexo, pero se pierde soporte territorial y de edades avanzadas. E2 sigue separando niveles relativos unidimensionales; un S mayor no demuestra mejores perfiles ni estructuras naturales. La utilidad requiere una pregunta electoral y validación fuera del índice interno; no se declara superioridad general.
4. **¿Quién pierde soporte?** {len(excluded):,} municipios no aportan ningún segmento. Edades sin segmentos elegibles: {', '.join(map(str, missing_ages)) or 'ninguna'}. Las tablas localizan pérdidas parciales por edad, sexo, municipio y entidad. El umbral nominal total y los mínimos de filas fuente tienen efectos separados. La selección concentra LN y no recupera cobertura ciudadana individual.
5. **¿Conservar exactas o intervalos?** Conservar las edades exactas como referencia y diagnóstico, sin sustituir los experimentos previos. Para modelos generales territoriales, contrastar perfiles municipales C o intervalos candidatos con mejor soporte; para detalle etario, estudiar curvas o agregación adaptativa sólo después de revisar denominadores, huecos, NS, supuestos de suavizado y comparabilidad. El piloto exacto es complementario y restringido, no una nueva representación definitiva.

**Observado:** cobertura, resolución de edad, distancias, métricas y estabilidad de este subconjunto. **Hipótesis:** parte de los perfiles puede seguir reflejando la edad incluida y la selección por soporte, además de diferencias de participación. **Pendiente:** objetivo, soporte admisible, ponderación, alcance de inferencia, estabilidad ampliada y validación electoral. No se decide K ni se interpretan tipos individuales de ciudadanos.

## Validaciones, integridad y reproducción

Se comprueban el esquema real, unicidad y trazabilidad, tipos de claves, identidad LN=SV+NV+NS, tasas NULL correctas, referencias calculadas antes de selección y sus sumas, universo común E1/E2, escaladores ajustados sólo al conjunto declarado, centroides/SSE mediante groupby independiente de bincount, convergencia, K grupos no vacíos, conciliación de conteos por cluster y lectura posterior de Parquet. Las pruebas contrastan referencias, soporte, Silhouette de anclas por bloques, DB y una ejecución pequeña completa. Se concilian los siete conteos aditivos contra los 2,477 municipios y 32 entidades originales.

Se registró un fallo técnico previo a cualquier ajuste por un directorio de salida de escaladores que faltaba crear. Se corrigió y se añadió una prueba de escritura desde destino vacío; el intento fallido queda archivado y descrito en metadata/incidents.json. Los datos y experimentos anteriores no se alteraron. Las pruebas nuevas incluyen además la separación de motivos de pérdida territorial.

Pasaron 72 pruebas automatizadas del proyecto, diez de ellas nuevas. Los contrastes numéricos independientes de las salidas comprueban además asignaciones, SSE, anclas, referencias y alcance OOB; no equivalen a una validación contra otra biblioteca de clustering.

Se verifican hashes de {protected_count:,} archivos previos antes/después, incluidos fuentes, experimentos, informes, scripts y frontend. No se modifican datos originales ni resultados previos, no se imputan o fabrican individuos, no se introducen TIPOSEC/GMM/HDBSCAN/K-Medoids ni se crean commits. _SUCCESS se escribe sólo tras terminar validaciones; un fallo queda en el manifiesto sin ese marcador.

```powershell
.venv/Scripts/python.exe analysis/scripts/evaluate_exact_age_clustering.py
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_evaluate_exact_age_clustering.py
```

Los destinos existentes se protegen; repetir con --output, --charts y --report nuevos. --anchor-count controla la precisión Monte Carlo y --replicates el número limitado de muestras. reference/ conserva todos los segmentos, pendientes y referencias; features/ contiene matrices estandarizadas nuevas y escaladores; models/ guarda etiquetas de todas las filas, anclas y S exacto E2; resampling/ conserva etiquetas, membresías y escalas; metadata/ reúne soporte, perfiles, conteos, controles y manifiesto. Son vistas alternativas que no se suman como registros únicos.
'''
    report.write_text(text, encoding='utf-8')


def run_pilot(root, output, charts, report, anchor_count=512, replicates=5):
    root, output, charts, report = [Path(path).resolve() for path in [root, output, charts, report]]
    require(output.is_relative_to(root/'data/processed') and charts.is_relative_to(root/'analysis/charts') and report.is_relative_to(root/'analysis/reports'), 'Destinos fuera del área autorizada.')
    require(not output.exists() and not charts.exists() and not report.exists(), 'Elegir destinos nuevos; no sobrescribir experimentos.')
    require(2 <= anchor_count <= 2000 and 2 <= replicates <= 10, 'Parámetros fuera del piloto limitado.')
    protected = snapshot_inputs(root, output, charts)
    for directory in [root/'analysis/scripts', root/'src']:
        for path in directory.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.name not in ['evaluate_exact_age_clustering.py', 'test_evaluate_exact_age_clustering.py']:
                protected[str(path)] = file_hash(path)
    protected[str(root/'.gitignore')] = file_hash(root/'.gitignore')
    source_validation(root, protected)
    for name in ['clustering_methods_review', 'demographic_representation_comparison']:
        folder = root/'data/processed'/name; manifest_path = folder/'metadata/run_manifest.json'
        previous = json.loads(manifest_path.read_text(encoding='utf-8'))
        require(previous['status'] == 'validated' and json.loads((folder/'_SUCCESS').read_text())['manifest_sha256'] == file_hash(manifest_path), f'Experimento previo no validado: {name}')
        require(file_hash(root/'analysis/reports'/f'{name}.md') == previous['report_sha256'], f'Informe previo modificado: {name}')
        for path, digest in previous['artifact_hashes'].items(): require(protected[str(root/path)] == digest, f'Archivo previo modificado: {path}')
    output.mkdir(parents=True); charts.mkdir(parents=True); (output/'metadata').mkdir()
    started = time.monotonic(); manifest_path = output/'metadata/run_manifest.json'
    manifest = dict(status='running', errors=[], started_at_utc=datetime.now(timezone.utc).isoformat(), protected_hashes=protected,
        configuration=dict(year=2024, age_scope=[18, 100], count_threshold=MAIN_THRESHOLD, min_source_rows=MIN_SOURCE_ROWS,
            threshold_scenarios=THRESHOLDS, ks=KS, sensitivity_k=6, seeds=SEEDS, n_init=10, weighting='equal_segment',
            anchor_count=anchor_count, distance_block_size=32, replicates=replicates, feature_columns={'e1': FEATURES, 'e2': FEATURES[1:]}),
        versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, matplotlib=matplotlib.__version__))
    save_json(manifest_path, manifest)
    try:
        failed_preflight = root/'data/processed/exact_age_clustering_review_failed_preflight/metadata/run_manifest.json'
        incidents = []
        if failed_preflight.exists():
            failed = json.loads(failed_preflight.read_text(encoding='utf-8'))
            incidents.append(dict(stage='pre_training_output', status='resolved', archive=str(failed_preflight.relative_to(root)),
                errors=failed.get('errors', []), resolution='Se crea el directorio de características antes de escribir escaladores; se añadió prueba de destino vacío. No hubo modelos ni modificaciones de fuentes en el intento fallido.'))
        save_json(output/'metadata/incidents.json', incidents)
        source_path = root/'data/processed/cluster_features/reference/exact_age_2024.parquet'
        parquet = pq.ParquetFile(source_path)
        save_json(output/'metadata/input_schema.json', dict(source=str(source_path.relative_to(root)), sha256=file_hash(source_path),
            rows=parquet.metadata.num_rows, row_groups=parquet.num_row_groups, columns=len(parquet.schema_arrow),
            fields=[dict(name=field.name, type=str(field.type), nullable=field.nullable) for field in parquet.schema_arrow],
            unique_keys=KEYS, source_unit='municipality_exact_age_sex_2024'))
        reference = pd.read_parquet(source_path)
        require(len(reference) == 401486 and len(reference.columns) == 35, 'Cambió el esquema/volumen confirmado.')
        full, national = prepare_segments(reference)
        require(full.LN.sum() == 98330348 and full.source_row_count.sum() == 9773730 and full.sex_2_source_rows.sum() == 105 and full.sex_2_nominal_count.sum() == 105, 'Conteos originales alterados.')
        municipal_reference = pd.read_parquet(root/'data/processed/cluster_features/matrices/c_life_stage/metadata.parquet')
        original = full.groupby(MUNICIPAL_KEYS, observed=True)[METRICS].sum().sort_index()
        expected = municipal_reference.set_index(MUNICIPAL_KEYS)[METRICS].sort_index()
        pd.testing.assert_frame_equal(original, expected, check_dtype=False)
        reconciliation = (original-expected).reset_index(); save_table(output/'metadata/municipality_reconciliation.csv', reconciliation)
        state_check = reconciliation.groupby('EDOCVE', as_index=False)[METRICS].sum()
        require(len(state_check) == 32 and state_check[METRICS].eq(0).all().all(), 'No concilian las entidades.')
        save_table(output/'metadata/state_reconciliation.csv', state_check)
        source = root/'data/processed/demographic_representation_comparison'
        interval_reference = pd.read_csv(source/'reference/national_reference_life_stage.csv', dtype={'SEXO': str})
        mapping = full[['age_value', 'SEXO', 'age_band_life_stage']].drop_duplicates()
        require(not mapping.duplicated(['age_value', 'SEXO']).any(), 'Una edad tiene más de un intervalo heredado.')
        reference_comparison = national.merge(mapping, on=['age_value', 'SEXO'], validate='one_to_one').merge(
            interval_reference[['age_band', 'SEXO', 'national_participation']].rename(columns={'age_band': 'age_band_life_stage', 'national_participation': 'national_participation_interval'}),
            on=['age_band_life_stage', 'SEXO'], how='left', validate='many_to_one')
        reference_comparison['reference_difference'] = reference_comparison.national_participation_exact-reference_comparison.national_participation_interval
        save_table(output/'metadata/national_reference_comparison.csv', reference_comparison)
        thresholds, ages, municipalities, quality = support_review(full)
        for name, table in [('support_thresholds', thresholds), ('age_support', ages), ('quality_summary', quality)]: save_table(output/'metadata'/f'{name}.csv', table)
        save_table(output/'metadata/municipality_coverage.parquet', municipalities)
        save_table(output/'metadata/municipality_exclusions.parquet', municipality_exclusions(full, municipalities))
        save_table(output/'metadata/prior_metric_context.csv', previous_metric_context(root))
        save_table(output/'reference/segments.parquet', full); save_table(output/'reference/pending_segments.parquet', full.loc[~full.is_eligible])
        save_table(output/'reference/national_reference_exact.csv', national)
        main = thresholds[thresholds.count_threshold.eq(MAIN_THRESHOLD) & thresholds.source_threshold.eq(MIN_SOURCE_ROWS)].iloc[0]
        save_json(output/'metadata/coverage_assessment_before_fit.json', dict(status='restricted_exploratory_subset_not_territorially_generalizable',
            eligible_segments=int(main.eligible_segments), represented_municipalities=int(main.municipalities), municipality_fraction=float(main.municipality_fraction),
            eligible_LN=int(main.LN), nominal_fraction_all=float(main.nominal_fraction_all), age_100_eligible=int(full[full.is_eligible & full.age_value.eq(100)].shape[0]),
            decision='Se ejecuta el piloto solicitado sobre el subconjunto de soporte existente; no se elige modelo ni se relajan umbrales para mejorar métricas.'))
        print(f'ANTES DEL AJUSTE: {int(main.eligible_segments):,} segmentos; {int(main.municipalities):,}/2477 municipios; {100*main.nominal_fraction_all:.2f}% LN. Cobertura territorial restringida.', flush=True)
        mask = full.is_eligible.to_numpy()
        require(mask.sum() == 125406 and np.array_equal(mask, support_mask(full, MAIN_THRESHOLD)), 'Cambió el universo elegible confirmado.')
        scaler, training_hash = save_features(full, output)
        save_json(output/'metadata/feature_contract.json', dict(unit='municipality_exact_age_sex_2024', key_columns=['row_id', *KEYS],
            feature_columns={'e1': FEATURES, 'e2': FEATURES[1:]}, metadata_columns=['LN', 'SV', 'NV', 'NS', 'source_row_count', 'specified_count', 'unspecified_rate', 'is_eligible', 'pending_reason'],
            row_ids_sha256=training_hash, national_reference='all_original_aggregated_counts_by_exact_age_and_sex_before_selection',
            engine_padding_e2='constant_zero_first_column_no_distance', no_cross_unit_ari=True))
        prior = pd.read_parquet(root/'data/processed/clustering_methods_review/reference/segments.parquet')
        prior_rows = [dict(representation='R1/R2 · life_stage', segments=int(prior.is_eligible.sum()),
            municipalities=prior[prior.is_eligible].groupby(MUNICIPAL_KEYS).ngroups,
            nominal_fraction=prior.loc[prior.is_eligible, 'LN'].sum()/prior.LN.sum(), unit='municipio/intervalo/sexo', reference='intervalo/sexo'),
            dict(representation='E1/E2 · edad exacta', segments=int(mask.sum()), municipalities=int(main.municipalities),
                nominal_fraction=float(main.nominal_fraction_all), unit='municipio/edad exacta/sexo', reference='edad exacta/sexo')]
        prior_comparison = pd.DataFrame(prior_rows); save_table(output/'metadata/prior_coverage_comparison.csv', prior_comparison)
        matrices, models, best, metrics = fit_models(full, scaler, output, anchor_count)
        stability, coverage = municipal_stability(full, models, best, source, output, replicates)
        profiles = pd.read_csv(output/'metadata/cluster_profiles.csv')
        plot_diagnostics(full, thresholds, ages, municipalities, reference_comparison, matrices, models, best, metrics, stability, profiles, charts)
        write_report(output, charts, report, full, thresholds, ages, municipalities, quality, metrics, stability, coverage, reference_comparison, prior_comparison, len(protected))
        for representation in ['e1', 'e2']:
            labels = pd.read_parquet(output/'models'/representation/'labels.parquet')
            require(labels.row_id.equals(full.row_id), 'Etiquetas no alineadas.')
            for k in KS:
                for seed in SEEDS:
                    column = f'k{k:02d}_seed{seed}'
                    require(labels.loc[~mask, column].isna().all() and labels.loc[mask, column].notna().all(), 'Pendientes o cobertura alterados.')
        for name, digest in protected.items(): require(file_hash(name) == digest, f'Archivo previo modificado: {name}')
        manifest.update(status='validated', finished_at_utc=datetime.now(timezone.utc).isoformat(), seconds=round(time.monotonic()-started, 2),
            full_models=30, municipal_models=len(stability), protected_files=len(protected),
            report_sha256=file_hash(report), script_sha256=file_hash(Path(__file__)),
            test_script_sha256=file_hash(root/'analysis/scripts/test_evaluate_exact_age_clustering.py'),
            artifact_hashes={str(path.relative_to(root)): file_hash(path) for directory in [output, charts]
                for path in directory.rglob('*') if path.is_file() and path != manifest_path})
        save_json(manifest_path, manifest); save_json(output/'_SUCCESS', dict(manifest_sha256=file_hash(manifest_path)))
        print(f'VALIDADO: 30 modelos completos, {len(stability)} municipales; {report.relative_to(root)}', flush=True)
    except Exception as error:
        manifest['status'] = 'failed'; manifest['errors'].append(dict(type=type(error).__name__, message=str(error)))
        save_json(manifest_path, manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, default=Path('data/processed/exact_age_clustering_review'))
    parser.add_argument('--charts', type=Path, default=Path('analysis/charts/exact_age_clustering_review'))
    parser.add_argument('--report', type=Path, default=Path('analysis/reports/exact_age_clustering_review.md'))
    parser.add_argument('--anchor-count', type=int, default=512)
    parser.add_argument('--replicates', type=int, default=5)
    args = parser.parse_args(); root = args.root.resolve()
    run_pilot(root, *[path if path.is_absolute() else root/path for path in [args.output, args.charts, args.report]], args.anchor_count, args.replicates)


if __name__ == '__main__':
    main()
