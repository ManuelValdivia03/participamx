"""Comparación controlada de participación absoluta/relativa en segmentos de 2024.

Conserva fuentes y pendientes. Ajusta únicamente K-Means; remuestrea municipios
completos y separa pesos de entrenamiento, geometría y métricas de evaluación.
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
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import pyarrow as pa

from clean_data import file_hash, require, save_json
from build_cluster_features import save_table, snapshot_inputs
from build_descriptive import METRICS, markdown_table, number, pct
from clustering_core import adjusted_rand, fit_scaler, transform
from run_clustering_pilot import label_change_fraction
from run_demographic_pilot import selection, anchor_sample, anchor_distances, sampled_metrics, cluster_tables

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, FuncFormatter
from matplotlib.lines import Line2D

SCHEMES = ['life_stage', 'broad']
FEATURE_SETS = {'absolute': ['mean_age_nominal', 'participation_observed'],
                'relative': ['mean_age_nominal', 'participation_deviation_national']}
WEIGHTINGS = ['equal_segment', 'equal_municipality']
KS = [4, 5, 6]
SEEDS = [17, 42, 2024]
KEYS = ['election_year', 'EDOCVE', 'MPIOCVE', 'age_band', 'SEXO']
MUNICIPAL_KEYS = ['EDOCVE', 'MPIOCVE']
MAX_ITER = 1000


def predict(values, centers):
    squared = (values[:, 0, None]-centers[None, :, 0])**2+(values[:, 1, None]-centers[None, :, 1])**2
    return squared.argmin(axis=1), squared


def initialization_bank(matrices, k, seed, n_init=10):
    """Banco simétrico: mitad k-means++ D² de A y mitad de B; mismos índices."""
    require(n_init >= 2 and n_init % 2 == 0, 'n-init debe ser par y al menos 2.')
    generator = np.random.default_rng(seed)
    bank = []
    require(matrices['absolute'].shape == matrices['relative'].shape, 'Poblaciones A/B distintas.')
    for representation in FEATURE_SETS:
        values = matrices[representation]
        require(np.isfinite(values).all() and len(values) > k, 'Banco sobre valores no finitos o insuficientes.')
        for _ in range(n_init//2):
            initial_seed = int(generator.integers(0, 2**32-1))
            rng = np.random.default_rng(initial_seed)
            indices = [int(rng.integers(len(values)))]
            closest = ((values-values[indices[0]])**2).sum(axis=1)
            while len(indices) < k:
                if closest.sum() > 0:
                    index = int(rng.choice(len(values), p=closest/closest.sum()))
                else:
                    index = next(index for index in range(len(values)) if index not in indices)
                indices.append(index)
                closest = np.minimum(closest, ((values-values[index])**2).sum(axis=1))
            bank.append(dict(source=representation, initial_seed=initial_seed, indices=np.asarray(indices)))
    return bank


def lloyd(values, weights, centers, max_iter=MAX_ITER):
    """Objetivo Σw||x−c||²; pesos positivos, centroides ponderados y parada estable."""
    values, weights = np.asarray(values, dtype=float), np.asarray(weights, dtype=float)
    centers = np.asarray(centers, dtype=float).copy()
    require(np.isfinite(values).all() and np.isfinite(weights).all() and (weights > 0).all(), 'Entrada ponderada inválida.')
    require(len(values) == len(weights), 'Pesos no alineados.')
    k = len(centers)
    previous, converged = None, False
    for iteration in range(1, max_iter+1):
        labels, squared = predict(values, centers)
        mass = np.bincount(labels, weights=weights, minlength=k)
        if previous is not None and np.array_equal(previous, labels) and (mass > 0).all():
            converged = True
            break
        for column in range(2):
            sums = np.bincount(labels, weights=weights*values[:, column], minlength=k)
            centers[:, column] = np.divide(sums, mass, out=centers[:, column].copy(), where=mass > 0)
        if (mass == 0).any():
            farthest = np.argsort(weights*squared[np.arange(len(values)), labels])[::-1]
            for empty, index in zip(np.flatnonzero(mass == 0), farthest):
                centers[empty] = values[index]
        previous = labels.copy()
    labels, squared = predict(values, centers)
    inertia = float(np.dot(weights, squared[np.arange(len(values)), labels]))
    return dict(labels=labels, centers=centers, inertia=inertia, iterations=iteration, converged=converged)


def fit_bank(values, weights, bank):
    best, records = None, []
    for index, initialization in enumerate(bank):
        fit = lloyd(values, weights, values[initialization['indices']])
        records.append(dict(initialization=index, source=initialization['source'],
            initial_seed=initialization['initial_seed'], sse=fit['inertia'], iterations=fit['iterations'], converged=fit['converged']))
        if best is None or fit['inertia'] < best['inertia']:
            best = dict(**fit, selected_initialization=index,
                        initial_centers=values[initialization['indices']].copy())
    require(best['converged'] and len(np.unique(best['labels'])) == len(best['centers']), 'Mejor ajuste incompleto/no convergente.')
    best['initializations'] = records
    return best


def fit_weights(metadata, weighting):
    if weighting == 'equal_segment':
        return np.ones(len(metadata))
    if weighting == 'equal_municipality':
        counts = metadata.groupby(MUNICIPAL_KEYS, observed=True).row_id.transform('size').to_numpy()
        return 1/counts
    if weighting == 'nominal':
        return metadata.LN.to_numpy(dtype=float)
    raise ValueError(weighting)


def weighted_group_sse(values, groups, weights):
    """Suma de cuadrados dentro de grupos; no usa identificadores como coordenadas."""
    values, groups, weights = np.asarray(values), np.asarray(groups), np.asarray(weights)
    mass = np.bincount(groups, weights=weights)
    sums = np.bincount(groups, weights=weights*values)
    means = np.divide(sums, mass, out=np.zeros(len(mass)), where=mass > 0)
    return float(np.dot(weights, (values-means[groups])**2))


def explained_fraction(values, groups, weights):
    denominator = float(np.dot(weights, (values-np.average(values, weights=weights))**2))
    return float(1-weighted_group_sse(values, groups, weights)/denominator) if denominator > 1e-14 else np.nan


def diagnostics(metadata, values, labels, weights):
    """Misma evaluación no ponderada para todos; añade la versión del objetivo con pesos."""
    labels = np.asarray(labels, dtype=int)
    bands = pd.factorize(metadata.age_band, sort=True)[0]
    cells = pd.factorize(pd.MultiIndex.from_frame(metadata[['age_band', 'SEXO']]), sort=True)[0]
    k = labels.max()+1
    rate = metadata.participation_observed.to_numpy()
    delta = metadata.participation_deviation_national.to_numpy()
    age = metadata.mean_age_nominal.to_numpy()
    table = np.zeros((k, bands.max()+1), dtype=int)
    np.add.at(table, (labels, bands), 1)
    result = dict(age_band_ari=adjusted_rand(labels, bands), age_band_purity=float(table.max(axis=1).sum()/len(labels)))
    for prefix, weight in [('', np.ones(len(labels))), ('weighted_', weights)]:
        age_r2 = explained_fraction(age, labels, weight)
        result[prefix+'age_r2'] = age_r2
        result[prefix+'absolute_rate_r2'] = explained_fraction(rate, labels, weight)
        result[prefix+'relative_rate_r2'] = explained_fraction(delta, labels, weight)
        baseline = weighted_group_sse(rate, cells, weight)
        after = weighted_group_sse(rate, cells*k+labels, weight)
        result[prefix+'within_age_sex_rate_r2'] = float(1-after/baseline) if baseline > 1e-14 else np.nan
        # La resta de la referencia nacional es constante dentro de intervalo/sexo.
        require(np.isclose(baseline, weighted_group_sse(delta, cells, weight), rtol=1e-9, atol=1e-10), 'Referencia no constante en celda.')
        between = []
        for column in range(2):
            total = np.dot(weight, (values[:, column]-np.average(values[:, column], weights=weight))**2)
            between.append(total-weighted_group_sse(values[:, column], labels, weight))
        result[prefix+'age_share_between'] = float(between[0]/sum(between)) if sum(between) else np.nan
    return result


def paired_population(metadata):
    base, result = selection(metadata)
    finite_relative = np.isfinite(metadata[FEATURE_SETS['relative']].to_numpy(dtype=float)).all(axis=1)
    require((~base | finite_relative).all(), 'B perdería filas elegibles respecto a A: revisar antes de modelar.')
    return base, result


def municipality_samples(keys, replicates=30, fraction=.8, seed=8102024):
    """Submuestreo sin reemplazo de claves compuestas; cada fila lleva todos sus segmentos."""
    require(0 < fraction < 1 and replicates >= 2, 'Remuestreo requiere fracción entre 0/1 y al menos dos réplicas.')
    unique = keys[MUNICIPAL_KEYS].drop_duplicates().sort_values(MUNICIPAL_KEYS).reset_index(drop=True)
    require(not unique.isna().any().any(), 'Claves nulas para remuestreo.')
    draws = np.zeros((replicates, len(unique)), dtype=bool)
    generator = np.random.default_rng(seed)
    for row in range(replicates):
        draws[row, generator.choice(len(unique), size=int(np.floor(fraction*len(unique))), replace=False)] = True
    return unique, draws


def membership(metadata, keys, draw):
    mapping = pd.MultiIndex.from_frame(keys).get_indexer(pd.MultiIndex.from_frame(metadata[MUNICIPAL_KEYS]))
    require((mapping >= 0).all(), 'Municipio fuera del universo de remuestreo.')
    return draw[mapping]


def coverage_record(metadata, mask, scheme, scenario, **extra):
    selected = metadata.loc[mask]
    return dict(scheme=scheme, scenario=scenario, original_segments=len(metadata), training_segments=int(mask.sum()),
        original_LN=int(metadata.LN.sum()), training_LN=int(selected.LN.sum()),
        LN_fraction=float(selected.LN.sum()/metadata.LN.sum()), segment_fraction=float(mask.mean()),
        municipalities=int(selected.groupby(MUNICIPAL_KEYS).ngroups),
        high_ns_segments=int(selected.has_high_unspecified_rate.sum()), **extra)


def pandas_numerical_check(values, weights, labels, centers, sse):
    """Contraste por groupby de Pandas; no se presenta como otra biblioteca de clustering."""
    frame = pd.DataFrame(dict(label=labels, w=weights, x=values[:, 0], y=values[:, 1]))
    frame['wx'] = frame.w*frame.x; frame['wy'] = frame.w*frame.y
    grouped = frame.groupby('label', sort=True)[['w', 'wx', 'wy']].sum()
    independent = np.column_stack([grouped.wx/grouped.w, grouped.wy/grouped.w])
    residual = float(np.max(np.abs(independent-centers)))
    objective = float(pd.Series(weights*((values-independent[labels])**2).sum(axis=1)).sum())
    require(residual < 1e-9 and np.isclose(objective, sse, rtol=1e-10, atol=1e-8), 'Centroides/SSE no coinciden con groupby independiente.')
    return dict(maximum_centroid_residual=residual, sse_absolute_residual=abs(objective-sse))


def nullable_labels(full, positions, values):
    result = pd.array([pd.NA]*len(full), dtype='Int64')
    result[positions] = values
    return result


def source_validation(root, protected):
    for folder in ['cluster_features', 'demographic_pilot']:
        source = root/'data/processed'/folder
        path = source/'metadata/run_manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        require(manifest['status'] == 'validated', f'{folder} sin validar.')
        require(json.loads((source/'_SUCCESS').read_text())['manifest_sha256'] == file_hash(path), 'Marcador alterado.')
        for relative, digest in manifest['artifact_hashes'].items():
            require(protected[str(root/relative)] == digest, f'Derivado previo alterado: {relative}')
        report = root/'analysis/reports'/('demographic_pilot.md' if folder == 'demographic_pilot' else 'cluster_feature_review.md')
        require(file_hash(report) == manifest['report_sha256'], f'Informe previo alterado: {report}')


def dependency_validation(output):
    """Prueba importación; si falta, consulta binarios sin instalar ni cambiar el entorno."""
    result = dict(status='unavailable', probes=[], interpretation='No se ha validado con una biblioteca independiente de clustering.')
    try:
        import sklearn
        import scipy
        result.update(status='available', sklearn=sklearn.__version__, scipy=scipy.__version__)
    except ImportError as error:
        result['import_error'] = str(error)
        for package, index in [('scikit-learn==1.9.1', None), ('scikit-learn', 'https://pypi.org/simple')]:
            command = [sys.executable, '-m', 'pip', 'install', '--dry-run', '--no-cache-dir', '--only-binary=:all:',
                '--disable-pip-version-check', '--timeout', '15', '--retries', '0', package]
            if index: command += ['--index-url', index]
            try:
                probe = subprocess.run(command, capture_output=True, text=True, timeout=35)
                result['probes'].append(dict(command=command, returncode=probe.returncode,
                    stdout=probe.stdout[-6000:], stderr=probe.stderr[-6000:]))
            except subprocess.TimeoutExpired:
                result['probes'].append(dict(command=command, status='timeout_35_seconds'))
        result['interpretation'] = ('Scikit-learn/SciPy no importables. Los sondeos no instalan paquetes. '
            'No se concluye incompatibilidad general de Python 3.14; no hubo distribuciones accesibles en este entorno. '
            'Queda pendiente el contraste con una biblioteca de clustering independiente; groupby Pandas y pruebas matemáticas no lo sustituyen.')
    save_json(output/'metadata/dependency_validation.json', result)
    return result


def independent_library_check(values, weights, fitted, raw, scaler):
    """Si está disponible, mismos centros iniciales y tol=0 evitan comparar inicializadores."""
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import adjusted_rand_score, davies_bouldin_score
    except ImportError:
        return dict(status='unavailable')
    independent = KMeans(n_clusters=len(fitted['centers']), init=fitted['initial_centers'], n_init=1,
        max_iter=MAX_ITER, tol=0., algorithm='lloyd', random_state=17).fit(values, sample_weight=weights)
    scale = StandardScaler().fit(raw)
    return dict(status='checked', ari=adjusted_rand_score(fitted['labels'], independent.labels_),
        relative_sse_difference=float((independent.inertia_-fitted['inertia'])/max(1., fitted['inertia'])),
        independent_davies_bouldin=float(davies_bouldin_score(values, fitted['labels'])),
        scaler_location_residual=float(np.max(np.abs(scale.mean_-scaler['location']))),
        scaler_scale_residual=float(np.max(np.abs(scale.scale_-scaler['scale']))))


def run_models(scheme, full, base, scalers, output, anchors_count, n_init, library_status):
    """Dos poblaciones emparejadas A/B: principal y sensibilidad de NS, sin filtrar fuentes."""
    contexts, metric_rows, stability_rows, comparisons, validation_rows, coverage_rows, initialization_rows = {}, [], [], [], [], [], []
    raw_all = {name: full[columns].to_numpy(dtype=float) for name, columns in FEATURE_SETS.items()}
    scaled_all = {name: transform(raw_all[name], scalers[name]) for name in FEATURE_SETS}
    for scenario in ['main', 'low_ns']:
        mask = base.copy()
        if scenario == 'low_ns': mask &= ~full.has_high_unspecified_rate.to_numpy()
        training = full.loc[mask].reset_index(drop=True)
        coverage_rows.append(coverage_record(full, mask, scheme, scenario))
        matrices = {name: values[mask] for name, values in scaled_all.items()}
        banks = {(k, seed): initialization_bank(matrices, k, seed, n_init) for k in KS for seed in SEEDS}
        anchors = anchor_sample(training.row_id, anchors_count)
        save_table(output/'metadata'/f'{scheme}_{scenario}_anchors.parquet', training.loc[anchors, ['row_id', *KEYS]])
        for representation in FEATURE_SETS:
            values = matrices[representation]
            distances = anchor_distances(values, anchors)
            for weighting in WEIGHTINGS:
                context_id = f'{scheme}_{representation}_{weighting}_{scenario}'
                folder = output/'contexts'/context_id
                folder.mkdir(parents=True)
                weights = fit_weights(training, weighting)
                metadata = full.copy()
                metadata['is_training'] = mask
                metadata['fit_weight'] = np.nan
                metadata.loc[mask, 'fit_weight'] = weights
                metadata['pending_reason'] = np.where(base & ~mask, 'high_ns_sensitivity_holdout', metadata.pending_reason)
                labels_frame = full[['row_id', *KEYS]].copy()
                predictions = full[['row_id', *KEYS]].copy()
                summaries, distributions, municipalities, center_rows = [], [], [], []
                models = {}
                for k in KS:
                    for seed in SEEDS:
                        fitted = fit_bank(values, weights, banks[k, seed])
                        labels = fitted['labels']
                        model_id = f'k{k:02d}_seed{seed}'
                        projected, _ = predict(scaled_all[representation][base], fitted['centers'])
                        counts = np.bincount(labels, minlength=k)
                        metrics = sampled_metrics(values, labels, anchors, distances)
                        metric_rows.append(dict(context_id=context_id, scheme=scheme, representation=representation,
                            weighting=weighting, scenario=scenario, k=k, seed=seed, n=len(training),
                            sse_weighted=fitted['inertia'], mean_weighted_sse=fitted['inertia']/weights.sum(),
                            sse_unweighted=float(((values-fitted['centers'][labels])**2).sum()),
                            minimum_cluster=int(counts.min()), maximum_cluster=int(counts.max()),
                            minimum_cluster_fraction=float(counts.min()/len(labels)), converged=fitted['converged'],
                            iterations=fitted['iterations'], **metrics, **diagnostics(training, values, labels, weights)))
                        validation = pandas_numerical_check(values, weights, labels, fitted['centers'], fitted['inertia'])
                        independent = dict(status='not_requested_for_this_seed')
                        if library_status == 'available' and seed == SEEDS[0]:
                            independent = independent_library_check(values, weights, fitted,
                                raw_all[representation][base], scalers[representation])
                        validation_rows.append(dict(context_id=context_id, k=k, seed=seed, **validation, **independent))
                        labels_frame[model_id] = nullable_labels(full, mask, labels)
                        predictions[model_id] = nullable_labels(full, base, projected)
                        models[k, seed] = dict(labels=labels, projected=projected, centers=fitted['centers'],
                            inertia=fitted['inertia'], selected_initialization=fitted['selected_initialization'])
                        initialization_rows.extend(dict(context_id=context_id, k=k, seed=seed, **record,
                            row_ids=';'.join(training.row_id.iloc[banks[k, seed][record['initialization']]['indices']]))
                            for record in fitted['initializations'])
                        summary, municipality, distribution = cluster_tables(training, labels, k, seed)
                        quality = training[['has_high_unspecified_rate', 'unspecified_rate']].copy()
                        quality['cluster'] = labels
                        by_cluster = quality.groupby('cluster').agg(high_ns_segments=('has_high_unspecified_rate', 'sum'),
                            mean_segment_ns=('unspecified_rate', 'mean'))
                        summary = summary.merge(by_cluster, on='cluster', validate='one_to_one')
                        summaries.append(summary); municipalities.append(municipality); distributions.append(distribution)
                        for group, center in enumerate(fitted['centers']):
                            center_rows.append(dict(k=k, seed=seed, cluster=group, scaled_age=float(center[0]), scaled_value=float(center[1]),
                                age=float(center[0]*scalers[representation]['scale'][0]+scalers[representation]['location'][0]),
                                value=float(center[1]*scalers[representation]['scale'][1]+scalers[representation]['location'][1])))
                    for left, right in combinations(SEEDS, 2):
                        x, y = models[k, left]['labels'], models[k, right]['labels']
                        stability_rows.append(dict(context_id=context_id, k=k, left_seed=left, right_seed=right,
                            ari=adjusted_rand(x, y), changed_fraction=label_change_fraction(x, y)))
                for filename, frame in [('metadata.parquet', metadata), ('labels.parquet', labels_frame),
                    ('projected_labels.parquet', predictions), ('pending_observations.parquet', metadata.loc[~mask]),
                    ('cluster_summary.csv', pd.concat(summaries, ignore_index=True)),
                    ('cluster_distributions.csv', pd.concat(distributions, ignore_index=True)),
                    ('municipality_cluster_counts.parquet', pd.concat(municipalities, ignore_index=True)),
                    ('centroids.csv', pd.DataFrame(center_rows))]:
                    save_table(folder/filename, frame)
                save_json(folder/'scaler.json', dict(**scalers[representation],
                    feature_columns=FEATURE_SETS[representation], fitted_population=f'{scheme}_paired_main',
                    fixed_across_weights_and_ns=True))
                require(labels_frame.iloc[:, 6:].notna().all(axis=1).to_numpy().tolist() == mask.tolist(), 'Etiquetas asignadas a pendientes.')
                contexts[context_id] = dict(models=models, mask=mask, representation=representation,
                    weighting=weighting, scenario=scenario, scheme=scheme, training=training)
                print(f'{context_id}: 9 ajustes; n={len(training):,}.', flush=True)
            del distances
    for kind in ['representation', 'weighting', 'ns']:
        for representation in (['absolute'] if kind == 'representation' else FEATURE_SETS):
            for weighting in (['equal_segment'] if kind == 'weighting' else WEIGHTINGS):
                for scenario in (['main'] if kind == 'ns' else ['main', 'low_ns']):
                    left = contexts[f'{scheme}_{representation}_{weighting}_{scenario}']
                    right_rep = 'relative' if kind == 'representation' else representation
                    right_weight = 'equal_municipality' if kind == 'weighting' else weighting
                    right_scenario = 'low_ns' if kind == 'ns' else scenario
                    right = contexts[f'{scheme}_{right_rep}_{right_weight}_{right_scenario}']
                    for k in KS:
                        for seed in SEEDS:
                            x, y = left['models'][k, seed]['projected'], right['models'][k, seed]['projected']
                            common = right['mask'][base] if kind == 'ns' else left['mask'][base]
                            comparisons.append(dict(scheme=scheme, comparison=kind, representation=representation,
                                weighting=weighting, scenario=scenario, k=k, seed=seed, common_n=int(common.sum()),
                                ari_common=adjusted_rand(x[common], y[common]),
                                ari_all_eligible=adjusted_rand(x, y),
                                changed_fraction_common=label_change_fraction(x[common], y[common])))
    return contexts, metric_rows, stability_rows, comparisons, validation_rows, coverage_rows, initialization_rows


def run_resampling(scheme, full, base, contexts, keys, draws, output, n_init):
    rows, initializations, coverages, comparison_rows = [], [], [], []
    baseline = {}
    for representation in FEATURE_SETS:
        for weighting in WEIGHTINGS:
            source = contexts[f'{scheme}_{representation}_{weighting}_main']
            for k in KS:
                seed = min(SEEDS, key=lambda seed: source['models'][k, seed]['inertia'])
                baseline[representation, weighting, k] = (seed, source['models'][k, seed]['projected'])
    for replicate, draw in enumerate(draws):
        chosen = membership(full, keys, draw)
        mask = base & chosen
        training = full.loc[mask].reset_index(drop=True)
        oob = ~chosen[base]
        scalers = {name: fit_scaler(training[columns].to_numpy(), 'standard') for name, columns in FEATURE_SETS.items()}
        matrices = {name: transform(training[FEATURE_SETS[name]].to_numpy(), scalers[name]) for name in FEATURE_SETS}
        banks = {k: initialization_bank(matrices, k, 17, n_init) for k in KS}
        coverage = coverage_record(full, mask, scheme, 'municipality_subsample', replicate=replicate,
            selected_municipalities=int(draw.sum()), selected_municipality_fraction=float(draw.mean()),
            sampled_original_segments=int(chosen.sum()), sampled_original_LN=int(full.loc[chosen, 'LN'].sum()),
            sampled_original_LN_fraction=float(full.loc[chosen, 'LN'].sum()/full.LN.sum()),
            eligible_fraction=float(mask.sum()/base.sum()), eligible_LN_fraction=float(full.loc[mask, 'LN'].sum()/full.loc[base, 'LN'].sum()),
            oob_eligible_segments=int(oob.sum()), oob_eligible_municipalities=int(full.loc[base & ~chosen].groupby(MUNICIPAL_KEYS).ngroups))
        coverages.append(coverage)
        labels_frame = full[['row_id', *KEYS]].copy()
        labels_frame['municipality_in_sample'] = chosen
        labels_frame['is_training'] = mask
        labels_frame['is_oob_eligible'] = base & ~chosen
        model_predictions = {}
        for representation in FEATURE_SETS:
            values = matrices[representation]
            whole = transform(full.loc[base, FEATURE_SETS[representation]].to_numpy(), scalers[representation])
            for weighting in WEIGHTINGS:
                weights = fit_weights(training, weighting)
                for k in KS:
                    fitted = fit_bank(values, weights, banks[k])
                    projected, _ = predict(whole, fitted['centers'])
                    seed, reference = baseline[representation, weighting, k]
                    model_predictions[representation, weighting, k] = projected
                    labels_frame[f'{representation}_{weighting}_k{k}'] = nullable_labels(full, base, projected)
                    rows.append(dict(scheme=scheme, replicate=replicate, representation=representation, weighting=weighting,
                        k=k, baseline_seed=seed, fit_seed=17, n=len(training), sse_weighted=fitted['inertia'],
                        converged=fitted['converged'], iterations=fitted['iterations'],
                        minimum_cluster=int(np.bincount(fitted['labels'], minlength=k).min()),
                        ari_all_eligible=adjusted_rand(reference, projected),
                        ari_inbag=adjusted_rand(reference[~oob], projected[~oob]),
                        ari_oob=adjusted_rand(reference[oob], projected[oob]),
                        changed_fraction_oob=label_change_fraction(reference[oob], projected[oob])))
                    initializations.extend(dict(scheme=scheme, replicate=replicate, representation=representation,
                        weighting=weighting, k=k, **item) for item in fitted['initializations'])
        for weighting in WEIGHTINGS:
            for k in KS:
                a, b = [model_predictions[representation, weighting, k] for representation in FEATURE_SETS]
                comparison_rows.append(dict(scheme=scheme, replicate=replicate, weighting=weighting, k=k,
                    ari_all_eligible=adjusted_rand(a, b), ari_oob=adjusted_rand(a[oob], b[oob])))
        folder = output/'resampling'/scheme/f'sample_{replicate:03d}'
        save_table(folder/'labels.parquet', labels_frame)
        save_json(folder/'scalers.json', {name: dict(**scaler, feature_columns=FEATURE_SETS[name],
            fitted_on='sampled_eligible_segments_only', n=len(training)) for name, scaler in scalers.items()})
        print(f'{scheme}: remuestra municipal {replicate+1}/{len(draws)}; {len(training):,} segmentos, {oob.sum():,} fuera de muestra.', flush=True)
    return rows, initializations, coverages, comparison_rows


def weight_diagnostics(full, mask, scheme):
    training = full.loc[mask]
    rows = []
    for mode in [*WEIGHTINGS, 'nominal']:
        weights = fit_weights(training, mode)
        frame = training[MUNICIPAL_KEYS].copy(); frame['weight'] = weights
        municipal = frame.groupby(MUNICIPAL_KEYS).weight.sum().sort_values(ascending=False)
        rows.append(dict(scheme=scheme, weighting=mode, fitted_models=mode != 'nominal',
            top_ten_municipalities_fraction=float(municipal.head(10).sum()/weights.sum()),
            equivalent_segment_units=float(weights.sum()**2/np.dot(weights, weights)),
            mean_age=float(np.average(training.mean_age_nominal, weights=weights)),
            mean_participation=float(np.average(training.participation_observed, weights=weights)),
            mean_national_deviation=float(np.average(training.participation_deviation_national, weights=weights)),
            high_ns_weight_fraction=float(weights[training.has_high_unspecified_rate.to_numpy()].sum()/weights.sum())))
    return rows


def age_dominated_control(root, output, references):
    """Reutiliza el control de unidades originales previo; no ajusta más modelos."""
    rows = []
    for scheme, (full, mask) in references.items():
        source = root/'data/processed/demographic_pilot/contexts'/f'{scheme}_original_joint_main'
        previous = pd.read_parquet(source/'metadata.parquet')
        labels = pd.read_parquet(source/'labels.parquet')
        require(full.row_id.equals(previous.row_id) and full.row_id.equals(labels.row_id), 'Control previo no alineado.')
        require(np.array_equal(previous.is_training.to_numpy(), mask), 'Control previo con otra población.')
        training = full.loc[mask]
        values = training[FEATURE_SETS['absolute']].to_numpy(dtype=float)  # Unidades originales, no estándar.
        for k in KS:
            for seed in SEEDS:
                partition = labels.loc[mask, f'k{k:02d}_seed{seed}'].to_numpy(dtype=int)
                rows.append(dict(scheme=scheme, k=k, seed=seed, source='previous_original_units_equal_segment',
                    n=int(mask.sum()), **diagnostics(training, values, partition, np.ones(mask.sum()))))
    frame = pd.DataFrame(rows)
    save_table(output/'metadata/age_dominated_reference.csv', frame)
    return frame


def resample_sizes(output, references):
    """Deriva tamaños y conteos de entrenamiento de etiquetas guardadas, sin ajustar."""
    tables = []
    for scheme, (full, base) in references.items():
        for path in sorted((output/'resampling'/scheme).glob('sample_*/labels.parquet')):
            labels = pd.read_parquet(path)
            require(labels.row_id.equals(full.row_id), 'Etiquetas de remuestra no alineadas.')
            mask = labels.is_training.to_numpy()
            train = full.loc[mask]
            replicate = int(path.parent.name.split('_')[-1])
            for representation in FEATURE_SETS:
                for weighting in WEIGHTINGS:
                    weights = fit_weights(train, weighting)
                    for k in KS:
                        column = f'{representation}_{weighting}_k{k}'
                        frame = train[['row_id', *METRICS]].copy()
                        frame['cluster'] = labels.loc[mask, column].to_numpy(dtype=int)
                        frame['fit_weight'] = weights
                        grouped = frame.groupby('cluster', as_index=False).agg(observations=('row_id', 'size'),
                            fit_weight=('fit_weight', 'sum'), **{name: (name, 'sum') for name in METRICS})
                        require(len(grouped) == k and grouped.observations.sum() == mask.sum(), 'Tamaños de remuestra no concilian.')
                        grouped.insert(0, 'k', k); grouped.insert(0, 'weighting', weighting)
                        grouped.insert(0, 'representation', representation); grouped.insert(0, 'replicate', replicate)
                        grouped.insert(0, 'scheme', scheme)
                        tables.append(grouped)
    result = pd.concat(tables, ignore_index=True)
    save_table(output/'metadata/resample_cluster_sizes.csv', result)
    return result


def plot_results(output, charts, metrics, stability, comparisons, resampling, coverage):
    for scheme in SCHEMES:
        fig, axes = plt.subplots(2, 3, figsize=(15, 8), layout='constrained')
        for representation, color in [('absolute', '#386cb0'), ('relative', '#d95f02')]:
            for weighting, style in [('equal_segment', '-'), ('equal_municipality', '--')]:
                selected = metrics[(metrics.scheme.eq(scheme)) & metrics.representation.eq(representation) &
                    metrics.weighting.eq(weighting) & metrics.scenario.eq('main')]
                grouped = selected.groupby('k').mean(numeric_only=True)
                text = ('A absoluta' if representation == 'absolute' else 'B relativa')+' · '+('segmento' if weighting == 'equal_segment' else 'municipio')
                for ax, field in zip(axes.ravel(), ['silhouette', 'davies_bouldin', 'age_r2', 'within_age_sex_rate_r2', 'age_band_purity', 'age_share_between']):
                    ax.plot(grouped.index, grouped[field], 'o'+style, label=text, color=color)
                    ax.set_xticks(KS); ax.set_xlabel('K (4/5 principales; 6 sensibilidad)'); ax.grid(alpha=.2)
        for ax, title in zip(axes.ravel(), ['Silhouette de anclas (aproximación)', 'Davies–Bouldin no ponderado',
            'Fracción de varianza de edad explicada', 'Fracción de tasa explicada dentro de edad/sexo', 'Pureza de banda predefinida', 'Edad: fracción de separación estandarizada']):
            ax.set_title(title)
        for ax in axes[1, :].tolist()+[axes[0, 2]]: ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.set_ylim(0, 1.03)
        axes[0, 0].legend(fontsize=7)
        fig.suptitle(f'{scheme} · misma población A/B · medias de tres semillas\nMétricas internas en geometrías distintas: no son un ranking universal')
        fig.savefig(charts/f'{scheme}_metric_comparison.png', dpi=160); plt.close(fig)
        fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), layout='constrained')
        for column, k in enumerate(KS):
            ax = axes[column]
            selected = resampling[resampling.scheme.eq(scheme) & resampling.k.eq(k)]
            arrays, labels = [], []
            for representation in FEATURE_SETS:
                for weighting in WEIGHTINGS:
                    group = selected[selected.representation.eq(representation) & selected.weighting.eq(weighting)]
                    arrays.append(group.ari_oob.to_numpy()); labels.append(('A' if representation == 'absolute' else 'B')+' / '+('segmento' if weighting == 'equal_segment' else 'municipio'))
            ax.boxplot(arrays, tick_labels=labels); ax.tick_params(axis='x', labelrotation=30)
            ax.set_title(f'K={k}'); ax.set_ylim(0, 1.03); ax.set_ylabel('ARI en municipios no usados en el ajuste'); ax.grid(axis='y', alpha=.2)
        sample_count = resampling[resampling.scheme.eq(scheme)].replicate.nunique()
        fig.suptitle(f'{scheme} · estabilidad del pipeline por submuestreo municipal\n{sample_count} muestras del 80 %; boxplots descriptivos, no intervalos de confianza')
        fig.savefig(charts/f'{scheme}_municipality_resampling.png', dpi=160); plt.close(fig)
        fig, axes = plt.subplots(2, 3, figsize=(15, 9), layout='constrained')
        full = pd.read_parquet(output/'reference'/f'b_{scheme}.parquet')
        base = full.is_eligible.to_numpy()
        for row, representation in enumerate(FEATURE_SETS):
            source = output/'contexts'/f'{scheme}_{representation}_equal_segment_main'/'labels.parquet'
            labels_frame = pd.read_parquet(source)
            for column, k in enumerate(KS):
                ax = axes[row, column]
                values = full.loc[base, FEATURE_SETS[representation]]
                ax.scatter(values.iloc[:, 0], values.iloc[:, 1], c=labels_frame.loc[base, f'k{k:02d}_seed17'],
                    cmap='tab10', vmin=0, vmax=9, s=3, alpha=.3, rasterized=True)
                ax.set_title(('A absoluta' if representation == 'absolute' else 'B relativa')+f' · K={k}')
                ax.set_xlabel('Edad media nominal'); ax.yaxis.set_major_formatter(PercentFormatter(1))
                if row == 0: ax.set_ylabel('Participación observada'); ax.set_ylim(0, 1)
                else:
                    ax.set_ylabel('Diferencia nacional misma edad/sexo (pp)')
                    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, position: f'{100*value:g}'))
                    ax.axhline(0, color='black', lw=.8)
                ax.legend(handles=[Line2D([0], [0], marker='o', linestyle='None', color=plt.get_cmap('tab10')(group),
                    label=f'c{group}', markersize=4) for group in range(k)], title='Etiqueta local', fontsize=6, title_fontsize=7)
        fig.suptitle(f'{scheme} · semilla 17, igual peso por segmento\nEtiquetas locales; intervalos candidatos, segmentos agregados')
        fig.savefig(charts/f'{scheme}_feature_spaces.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), layout='constrained')
    for ax, kind, title in zip(axes, ['representation', 'weighting', 'ns'],
        ['A/B: representaciones', 'Pesos: segmento/municipio', 'NS: principal/baja NS en comunes']):
        selected = comparisons[comparisons.comparison.eq(kind) & comparisons.scenario.eq('main')]
        for key, group in selected.groupby(['scheme', 'representation', 'weighting']):
            curve = group.groupby('k').ari_common.mean()
            ax.plot(curve.index, curve, 'o-', label=' / '.join(key))
        ax.set_title(title); ax.set_ylim(0, 1.03); ax.set_xticks(KS); ax.set_xlabel('K'); ax.set_ylabel('ARI medio de tres semillas'); ax.legend(fontsize=6)
    fig.savefig(charts/'partition_comparisons.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout='constrained')
    for ax, scheme in zip(axes, SCHEMES):
        selected = coverage[coverage.scheme.eq(scheme)]
        ax.scatter(selected.replicate, selected.eligible_fraction, label='Segmentos elegibles')
        ax.scatter(selected.replicate, selected.eligible_LN_fraction, marker='s', label='LN elegible')
        ax.set_title(scheme); ax.set_xlabel('Muestra municipal'); ax.set_ylabel('Cobertura respecto al principal'); ax.legend()
        ax.yaxis.set_major_formatter(PercentFormatter(1))
    fig.suptitle('Cobertura real de cada muestra · municipios completos sin reemplazo')
    fig.savefig(charts/'resampling_coverage.png', dpi=160); plt.close(fig)


def write_report(output, charts, report, metrics, stability, comparisons, resampling, coverage, samples,
                 weights, dependencies, validation, protected_count, n_init=10, anchor_count=1200):
    main = metrics[metrics.scenario.eq('main')]
    summary = main.groupby(['scheme', 'representation', 'weighting', 'k'], as_index=False).mean(numeric_only=True)
    seed_summary = stability.groupby(['context_id', 'k']).ari.agg(['mean', 'min'])
    rows = []
    for row in summary.itertuples():
        context_id = f'{row.scheme}_{row.representation}_{row.weighting}_main'
        seed = seed_summary.loc[(context_id, row.k)]
        sample = resampling[resampling.scheme.eq(row.scheme) & resampling.representation.eq(row.representation)
            & resampling.weighting.eq(row.weighting) & resampling.k.eq(row.k)]
        rows.append([row.scheme, 'A' if row.representation == 'absolute' else 'B', row.weighting, row.k,
            f'{row.silhouette:.4f}', f'{row.davies_bouldin:.4f}', f'{seed["min"]:.3f}',
            f'{sample.ari_oob.median():.3f}', f'{sample.ari_oob.quantile(.1):.3f}', f'{sample.ari_oob.min():.3f}',
            number(main[(main.context_id.eq(context_id)) & main.k.eq(row.k)].minimum_cluster.min()),
            pct(row.age_r2), pct(row.age_share_between), pct(row.within_age_sex_rate_r2), pct(row.age_band_purity)])
    comparison_rows = []
    for key, group in comparisons.groupby(['scheme', 'comparison', 'representation', 'weighting', 'scenario', 'k']):
        comparison_rows.append([*key, number(group.common_n.iloc[0]), f'{group.ari_common.mean():.3f}',
            f'{group.ari_common.min():.3f}', pct(group.changed_fraction_common.mean())])
    coverage_rows = [[row.scheme, row.scenario, number(row.training_segments), pct(row.segment_fraction),
        number(row.training_LN), pct(row.LN_fraction), number(row.municipalities), number(row.high_ns_segments)]
        for row in coverage.itertuples()]
    sample_rows = []
    for scheme, group in samples.groupby('scheme'):
        sample_rows.append([scheme, len(group), number(group.selected_municipalities.iloc[0]),
            f'{int(group.training_segments.min()):,}–{int(group.training_segments.max()):,}',
            f'{pct(group.eligible_LN_fraction.min())}–{pct(group.eligible_LN_fraction.max())}',
            f'{int(group.oob_eligible_segments.min()):,}–{int(group.oob_eligible_segments.max()):,}'])
    weight_rows = [[row.scheme, row.weighting, str(row.fitted_models), pct(row.top_ten_municipalities_fraction),
        pct(row.mean_participation), f'{100*row.mean_national_deviation:.2f}', pct(row.high_ns_weight_fraction)]
        for row in weights.itertuples()]
    main_findings = []
    for scheme in SCHEMES:
        for k in KS:
            a = summary[summary.scheme.eq(scheme) & summary.representation.eq('absolute') & summary.weighting.eq('equal_segment') & summary.k.eq(k)].iloc[0]
            b = summary[summary.scheme.eq(scheme) & summary.representation.eq('relative') & summary.weighting.eq('equal_segment') & summary.k.eq(k)].iloc[0]
            sample_a = resampling[resampling.scheme.eq(scheme) & resampling.representation.eq('absolute') & resampling.weighting.eq('equal_segment') & resampling.k.eq(k)]
            sample_b = resampling[resampling.scheme.eq(scheme) & resampling.representation.eq('relative') & resampling.weighting.eq('equal_segment') & resampling.k.eq(k)]
            main_findings.append(f'- **{scheme}, K={k}, igual peso por segmento:** A/B explican respectivamente '
                f'{pct(a.within_age_sex_rate_r2)} / {pct(b.within_age_sex_rate_r2)} de la variación de tasas dentro de intervalo/sexo; '
                f'edad explica {pct(a.age_r2)} / {pct(b.age_r2)} de su propia varianza; '
                f'ARI mediano fuera de muestra municipal {sample_a.ari_oob.median():.3f} / {sample_b.ari_oob.median():.3f}.')
    profile_rows = []
    for representation in FEATURE_SETS:
        folder = output/'contexts'/f'life_stage_{representation}_equal_segment_main'
        profile = pd.read_csv(folder/'cluster_summary.csv')
        distribution = pd.read_csv(folder/'cluster_distributions.csv', dtype={'category': str})
        for row in profile[profile.seed.eq(17) & profile.k.isin([4, 5])].itertuples():
            part = distribution[distribution.k.eq(row.k) & distribution.seed.eq(17) & distribution.cluster.eq(row.cluster)]
            bands = part[part.dimension.eq('age_band')].sort_values('observations', ascending=False).iloc[0]
            women = part[part.dimension.eq('SEXO') & part.category.eq('1')].observations.sum()/row.observations
            profile_rows.append(['A' if representation == 'absolute' else 'B', row.k, row.cluster,
                number(row.observations), number(row.municipalities), f'{row.mean_age:.1f}', pct(women),
                bands.category, pct(bands.cluster_fraction), pct(row.participation_observed),
                f'{100*row.mean_national_deviation:.2f}', pct(row.unspecified_rate), pct(row.high_ns_segments/row.observations)])
    relative = summary[summary.scheme.eq('life_stage') & summary.representation.eq('relative') & summary.k.isin([4, 5])]
    interpretation_rows = []
    for k in [4, 5]:
        for representation in FEATURE_SETS:
            weight_change = comparisons[comparisons.scheme.eq('life_stage') & comparisons.comparison.eq('weighting')
                & comparisons.representation.eq(representation) & comparisons.scenario.eq('main') & comparisons.k.eq(k)]
            ns_change = comparisons[comparisons.scheme.eq('life_stage') & comparisons.comparison.eq('ns')
                & comparisons.representation.eq(representation) & comparisons.scenario.eq('main')
                & comparisons.weighting.eq('equal_segment') & comparisons.k.eq(k)]
            sample = resampling[resampling.scheme.eq('life_stage') & resampling.representation.eq(representation)
                & resampling.weighting.eq('equal_segment') & resampling.k.eq(k)]
            interpretation_rows.append(['A' if representation == 'absolute' else 'B', k,
                f'{weight_change.ari_common.mean():.3f}', pct(weight_change.changed_fraction_common.mean()),
                f'{ns_change.ari_common.mean():.3f}', f'{sample.ari_oob.min():.3f}',
                f'{int(sample.ari_oob.lt(.9).sum())}/{len(sample)}'])
    sample_count = int(samples.groupby('scheme').size().iloc[0])
    control_path = output/'metadata/age_dominated_reference.csv'
    control_rows = []
    if control_path.exists():
        control = pd.read_csv(control_path)
        for (scheme, k), group in control.groupby(['scheme', 'k']):
            control_rows.append([scheme, k, pct(group.age_r2.mean()), pct(group.age_share_between.mean()),
                pct(group.age_band_purity.mean()), pct(group.within_age_sex_rate_r2.mean())])
    text = f'''# Comparación controlada de representaciones demográficas · 2024

## Resultado y recomendación provisional

Se comparan **A: edad media nominal + participación observada** y **B: edad media nominal + diferencia frente a la tasa nacional del mismo intervalo/sexo**. Ambas usan exactamente la misma población por escenario y sólo dos coordenadas; las claves territoriales y SEXO permanecen como metadatos. Se ajustaron {len(metrics)} modelos principales/de sensibilidad NS y {len(resampling)} modelos de remuestreo, únicamente K-Means. K=4/5 son candidatos y K=6 sensibilidad; no se declara un ganador.

**B merece continuar como candidata a K-Medoids para estudiar participación relativa a pares demográficos, manteniendo A como control de niveles absolutos.** La recomendación está condicionada a los resultados de estabilidad y cobertura de abajo; no equivale a que B gane en todas las métricas ni a una selección definitiva de K o de perfiles. Cambiar la referencia cambia la pregunta. Los segmentos no son personas y no se descubren tipos individuales de ciudadanos.

{chr(10).join(main_findings)}

En life_stage B, K=4/5, la separación dentro de los mismos intervalos/sexos es {pct(relative.within_age_sex_rate_r2.min())}–{pct(relative.within_age_sex_rate_r2.max())} según peso/K. Por tanto hay separación de tasas adicional a una partición que únicamente reprodujera las bandas (su mejora condicional sería cero). La resta nacional no añade datos: reexpresa la misma tasa contra una referencia; tampoco elimina la edad, que sigue en la distancia. La utilidad sustantiva y la robustez no se deducen de ese porcentaje in-sample.

La recomendación de continuar con B responde al objetivo relativo y a su menor reproducción de bandas y sensibilidad a pesos frente a A con K=5. **No mejora todas las métricas:** en life_stage K=4/5, A tiene Silhouette mayor y DB menor en sus geometrías respectivas. A con K=4 mantiene una cola de estabilidad municipal más favorable que B con K=4. B conserva aproximadamente la mitad de la separación estandarizada en la coordenada de edad; no es una representación independiente de edad. No hay base para declarar que B es universalmente superior o para retirar A como control.

Resumen de precauciones principales en life_stage (comparaciones medias de semillas; OOB sobre peso segmento):

{markdown_table(['Representación', 'K', 'ARI cambio de peso', '% cambio alineado de peso', 'ARI NS en comunes', 'ARI OOB mínimo', 'Muestras OOB ARI<0.90'], interpretation_rows)}

Las medianas altas ocultan cambios importantes en algunas muestras. A con K=5 es especialmente sensible a la perturbación municipal y al objetivo de pesos; B con K=5 mejora esa cola en estos ensayos, pero mantiene muestras con baja concordancia. En broad B, K=4 también aparece una muestra con ARI OOB cercano a 0.486, pese a su mediana alta. Esto exige revisar los casos y aumentar arranques/remuestras antes de fijar perfiles. K=6 sigue siendo sensibilidad: en broad B aumenta la separación etaria sin mejorar la fracción de tasa explicada dentro de edad/sexo frente a K=5.

## Contrato y control de la comparación

Se reutilizaron los contratos, las referencias national_reference_SCHEME.csv y los Parquet reference/b_SCHEME.parquet del piloto demográfico, comprobando sus manifiestos, _SUCCESS y hashes. Las referencias nacionales permanecen fijas: ΣSV/Σ(SV+NV) por intervalo/sexo, incluyendo todos los conteos originales antes de seleccionar soporte. Se contrastaron sus sumas y tasas contra los agregados originales, sin releer CSV ni registros individuales. B usa la diferencia ya calculada, con signo y sin añadirla junto a la tasa absoluta como tercera variable.

Principal: edades 18–100, ambas coordenadas finitas, LN≥100, SV+NV≥100 y filas fuente≥5. Se exige que B no pierda ninguna fila elegible de A. Cada esquema tiene un único orden de row_id y dos StandardScaler propios (media y DE poblacional ddof=0, sin pesos) ajustados **sólo a esa población elegible común**. La escala de edad es idéntica A/B. Se guardan parámetros y copias nuevas; las matrices previas no cambian. Los escaladores se mantienen fijos al variar pesos y al estudiar NS para no mezclar cambio de población con cambio de escala.

{markdown_table(['Esquema', 'Escenario', 'Segmentos entrenados', '% segmentos originales', 'LN entrenado', '% LN original', 'Municipios', 'Segmentos NS≥10 %'], coverage_rows)}

La sensibilidad low_ns entrena sólo con NS/LN<10 %, conservando todas las filas y el principal sin ese filtro. Las tasas NULL no se imputan ni se vuelven cero. Las edades 101+, SEXO=2 y todos los segmentos escasos siguen en referencia y pendientes, sin asignarles etiquetas de entrenamiento. SEXO=2 mantiene 105 filas fuente y LN=105 en cada vista; sus segmentos no superan soporte. El detalle exacto sigue trazable a cluster_features/reference/exact_age_2024.parquet. Los dos esquemas son vistas alternativas y no se suman.

## Inicialización, pesos y métricas

Cada ajuste usa un banco común de {n_init} inicializaciones: {n_init//2} k-means++ D² originadas en A y {n_init//2} en B. Se reutilizan **los mismos índices de segmentos iniciales** al comparar representaciones y pesos, evitando favorecer sólo una geometría o confundir pesos con una nueva lotería de arranques. Se ensayan semillas 17/42/2024 en las poblaciones completas; cada ajuste elige su menor SSE entre esos {n_init} arranques. Lloyd actualiza centroides ponderados hasta asignaciones estables, máximo 1,000 iteraciones. El banco simétrico difiere del piloto anterior; no se copian sus métricas ni se exige igualdad exacta con sus mínimos locales.

Peso segmento=1; peso municipio=1/n de sus segmentos **en la población de ajuste**, de modo que cada municipio representado aporta peso total uno. Se mantiene el mismo escalador sin ponderar, por lo que esta sensibilidad modifica el objetivo, no la geometría de las variables. En low_ns se recalcula n: cambia la población y su reparto de pesos; no es un efecto causal puro de NS. LN se documenta por separado y no se usa en ningún ajuste de esta entrega. [Pesos de observación en KMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html).

SSE ponderada=Σw||x−c||²; también se conserva SSE/Σw y SSE sin pesos. SSE entre geometrías distintas no identifica una representación mejor. Silhouette y Davies–Bouldin son las definiciones usuales **no ponderadas**, calculadas sobre las mismas observaciones de evaluación, incluso cuando el entrenamiento usa pesos municipales. DB usa centros aritméticos de las etiquetas para conservar la definición estándar, no los centroides ponderados del ajuste. No se presenta un índice ponderado inventado. Silhouette usa hasta {anchor_count:,} anclas uniformes compartidas A/B/pesos, cada una contra todo el entrenamiento; se guarda su error Monte Carlo con corrección finita. No se crea una matriz de distancias n×n. [Silhouette](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html), [Davies–Bouldin](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.davies_bouldin_score.html).

## Métricas, separación demográfica y estabilidad

Medias de tres semillas salvo los mínimos indicados. ARI OOB compara las asignaciones de municipios no usados en el ajuste de cada remuestra frente a la solución de población completa con menor SSE entre semillas, para la misma representación/peso/K. Es concordancia, no exactitud contra etiquetas verdaderas. q10 y mínimo describen las remuestras; no son intervalos de confianza.

{markdown_table(['Esquema', 'Representación', 'Peso', 'K', 'Silhouette', 'DB', 'ARI semillas mín.', 'ARI OOB mediana', 'OOB q10', 'OOB mín.', 'Cluster mín.', 'R² edad', 'Edad / separación', 'R² tasa dentro edad/sexo', 'Pureza banda'], rows)}

R² edad es la fracción de su varianza explicada por las etiquetas. Edad/separación es la proporción de la suma de cuadrados entre clusters correspondiente a la coordenada de edad en la geometría estandarizada: no es atribución causal ni importancia predictiva. R² tasa dentro edad/sexo compara el residuo con medias por intervalo/sexo frente a medias por intervalo/sexo/cluster; se calcula con tasas originales para ambas representaciones. La resta nacional es constante dentro de cada celda, por lo que ese residuo es igual usando tasa o diferencia para una misma partición. Los resultados ponderados se guardan aparte en model_metrics.csv; la tabla común usa igual peso por segmento para evaluar ambos objetivos sobre la misma base.

Pureza y ARI de banda detectan reproducción de los intervalos predefinidos. Las métricas internas valoran compacidad/separación en su propia geometría, no una clasificación universal A/B. Una mejora condicional no prueba que los grupos se generalicen ni responde por sí sola a la estabilidad. No se nombran perfiles ciudadanos definitivos.

Como control empírico, se reutilizaron las etiquetas del piloto anterior en unidades originales, sobre exactamente los mismos segmentos y con peso uno por segmento. La edad domina esa geometría; **no es un modelo exclusivamente unidimensional de edad**. Sólo se contrastan descriptores de separación, sin presentar sus métricas internas como comparables entre escalas. No se hicieron ajustes nuevos para este control:

{markdown_table(['Control previo', 'K', 'R² edad', 'Edad / separación', 'Pureza banda', 'R² tasa dentro edad/sexo'], control_rows)}

![Métricas life_stage]({os.path.relpath(charts/'life_stage_metric_comparison.png', report.parent).replace(chr(92), '/')})

![Geometrías life_stage]({os.path.relpath(charts/'life_stage_feature_spaces.png', report.parent).replace(chr(92), '/')})

## Perfiles descriptivos de los candidatos principales

Ejemplo reproducible: life_stage, semilla 17, peso segmento, K=4/5. Cada etiqueta es local al ajuste; no tiene orden ni identidad entre representaciones. Las tablas de cada contexto contienen todas las semillas/K, distribuciones por edad y sexo, conteos, municipios y segmentos por municipio. La participación del cluster usa ΣSV/Σ(SV+NV); Δ es la media no ponderada de las diferencias de sus segmentos contra la referencia propia. NS agregado y frecuencia de segmentos NS alto son medidas diferentes.

{markdown_table(['Representación', 'K', 'Etiqueta local', 'Segmentos', 'Municipios', 'Edad media', '% mujeres', 'Banda dominante', '% banda', 'Participación agregada', 'Δ nacional medio (pp)', 'NS/LN agregado', '% segmentos NS alto'], profile_rows)}

Un municipio puede tener segmentos en varios clusters; no se suman los municipios representados como territorios únicos entre grupos. El detalle por sexo permite distinguir composición de niveles: B descuenta referencias distintas H/M sin convertir SEXO en coordenada numérica. Eso no garantiza ausencia de diferencias o sesgos por sexo. Las diferencias son agregadas y no permiten inferir conductas individuales.

## Concordancia A/B, ponderación y NS

{markdown_table(['Esquema', 'Comparación', 'Representación izquierda', 'Peso izquierdo', 'Población izquierda', 'K', 'Segmentos comunes', 'ARI medio', 'ARI mín.', '% cambio alineado medio'], comparison_rows)}

representation compara A/B bajo mismo peso/población; weighting compara segmento/municipio bajo misma representación/población; ns compara principal/low_ns. Para NS, ARI common se calcula sólo sobre el entrenamiento low_ns común; ari_all_eligible guarda también la comparación de predicciones sobre toda la población principal. Las proyecciones de segmentos NS alto se guardan aparte y no se presentan como usados en el ajuste low_ns. Se alinea por máximo solapamiento para contar cambios, sin comparar números arbitrarios de etiquetas. No se calcula ARI entre broad y life_stage: sus segmentos no tienen correspondencia uno a uno.

NS alto puede reflejar cobertura de captura y afectar los perfiles observados. Conservamos sus conteos y banderas. La sensibilidad que cambia el entrenamiento no identifica el resultado que tendríamos si los registros NS hubieran sido observados; no convierte NS en abstención ni lo imputa. Los campos NS/LN y las distribuciones por cluster permiten localizar agrupaciones asociadas con cobertura; no se declara causalidad.

![Comparación de particiones]({os.path.relpath(charts/'partition_comparisons.png', report.parent).replace(chr(92), '/')})

## Peso LN separado del objetivo principal

{markdown_table(['Esquema', 'Peso descriptivo', 'Usado en ajustes', '% peso diez municipios mayores', 'Media tasa', 'Δ nacional medio (pp)', '% peso NS alto'], weight_rows)}

Peso uno por segmento puede sobrerrepresentar municipios que aportan más segmentos con soporte. Peso municipal igual corrige esa suma de influencia entre municipios representados, pero no recupera municipios sin segmentos entrenables. LN orientaría el objetivo hacia volumen nominal; no es una corrección automática de fiabilidad, cobertura o sesgo. La media con peso LN no equivale necesariamente a la tasa nacional de suma SV/suma SV+NV. Se conserva concentración de pesos y referencia LN sin ajustar modelos con ella.

## Remuestreo por municipio y cobertura

Se generaron {sample_count} submuestras sin reemplazo, cada una con floor(0.8×2,477)=1,981 municipios del universo original de 2024; semilla de muestreo 8102024. **No es un bootstrap con reemplazo.** Se usan las mismas claves muestreadas en A/B, pesos, K y ambos esquemas. Entran juntos todos los segmentos elegibles de un municipio; los no elegibles siguen conservados. Los municipios sin segmentos suficientes también forman parte del universo sorteado y se contabilizan, aunque no aporten filas de entrenamiento.

{markdown_table(['Esquema', 'Muestras', 'Municipios sorteados por muestra', 'Rango segmentos entrenados', 'Rango % LN elegible', 'Rango segmentos OOB'], sample_rows)}

Cada muestra reajusta sus dos StandardScaler únicamente sobre sus propios segmentos elegibles y después predice en todos los elegibles principales. No usa municipios OOB para ajustar escalas o centroides. La referencia nacional sigue fija e incluye conteos de todo 2024, también OOB: esta es estabilidad bajo una referencia contextual fija, **no una validación predictiva independiente del proceso nacional de referencia**. El banco inicial simétrico se genera dentro de cada muestra; semilla de ajuste 17 y {n_init} arranques. Los cambios combinan perturbación municipal y optimización finita; no prueban causalidad ni incertidumbre de votantes. La variación entre semillas de población completa sirve de diagnóstico separado.

Se registra para cada muestra cobertura municipal, filas agregadas originales, LN original, entrenamiento elegible y LN elegible, municipios y segmentos OOB. Se guardan membresía municipal, escaladores y todas las etiquetas experimentales: is_training/is_oob_eligible distingue ajustes de proyecciones. Los pendientes originales conservan NULL. Los resúmenes de {sample_count} muestras son exploratorios; aumentar réplicas y arranques si los candidatos están próximos o las colas son inestables. No se ensamblan votos ni segmentos de municipios diferentes para formar observaciones artificiales.

![Estabilidad municipal life_stage]({os.path.relpath(charts/'life_stage_municipality_resampling.png', report.parent).replace(chr(92), '/')})

![Cobertura de remuestras]({os.path.relpath(charts/'resampling_coverage.png', report.parent).replace(chr(92), '/')})

## Contraste numérico y dependencias

Estado de biblioteca independiente: **{dependencies['status']}**. {dependencies.get('interpretation', '')} Se registran comandos, códigos de salida e importaciones en metadata/dependency_validation.json. Los sondeos pip usan --dry-run y --only-binary; no instalan ni cambian dependencias. Python={platform.python_version()}. No se afirma que Python 3.14 sea incompatible en general. [Versiones soportadas de scikit-learn](https://scikit-learn.org/stable/install.html).

En todos los ajustes principales/NS, centroides y SSE ponderados se recomputan mediante groupby de Pandas, separado de bincount del algoritmo: residuo máximo de centro {validation.maximum_centroid_residual.max():.3g} y de SSE {validation.sse_absolute_residual.max():.3g}. Las pruebas pequeñas contrastan Lloyd con expansión literal de pesos enteros, un caso exhaustivo y referencias de métricas. **Son comprobaciones numéricas, no sustituyen una biblioteca independiente de clustering.** Si scikit-learn está disponible, el script activa el contraste con KMeans desde los mismos centros iniciales/tol=0, StandardScaler y DB; conserva sus resultados y diferencias sin afirmar equivalencia automática de inicializadores.

## Conservación, entregables y reproducción

Se conservaron todos los segmentos originales: 27,650 en life_stage y 17,735 en broad. Cada vista mantiene LN=98,330,348, SV=54,899,228, NV=37,105,466, NS=6,325,654 y 9,773,730 filas fuente representadas. Se conciliaron 448 sumas esquema/entidad/campo contra los descriptivos de 2024. Las claves siguen como texto. Se comprobaron poblaciones A/B idénticas, orden/row_id, escalas ajustadas sólo a las poblaciones declaradas, pesos municipales con masa uno, conteos por cluster, etiquetas NULL de pendientes, finitud, K grupos no vacíos, convergencia, y lectura posterior de Parquet. Se verifican hashes de {protected_count:,} archivos existentes antes y después. _SUCCESS sólo aparece tras validar artefactos e informe.

- reference/: todos los segmentos, metadatos, referencia nacional y elegibilidad; copia de características A/B con escaladores y contrato.
- contexts/: por esquema/representación/peso/población, metadatos completos, pendientes, etiquetas de entrenamiento, proyecciones separadas, centroides, distribuciones y conteos municipales.
- resampling/: membresía municipal, etiquetas de cada muestra y escaladores propios.
- metadata/: métricas, estabilidad, comparaciones, coberturas, inicializaciones, conciliaciones, pesos, dependencias y manifiesto.

```powershell
.venv/Scripts/python.exe analysis/scripts/compare_demographic_features.py
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_compare_demographic_features.py
```

Los destinos existentes se rechazan; para repetir usar nuevas rutas --output, --charts y --report. No se modifican informes anteriores, fuentes, matrices existentes ni frontend. No se ejecutan Ward, K-Medoids o DBSCAN; no se fijan intervalos de edad, K ni perfiles definitivos y no se crean commits.

Antes de pasar a K-Medoids deben revisarse conjuntamente la separación dentro de edad/sexo, la reproducción de bandas, la estabilidad municipal/semillas, sensibilidad a pesos y NS y la viabilidad de una distancia en el objetivo absoluto o relativo elegido. Se recomienda llevar B como candidata explícita de patrones relativos y A como control, sin convertir un único índice interno en decisión final. La validación con una biblioteca independiente sigue pendiente cuando no hay dependencias accesibles.
'''
    report.write_text(text, encoding='utf-8')


def run_comparison(root, output, charts, report, replicates=30, anchor_count=1200, n_init=10):
    root, output, charts, report = [Path(path).resolve() for path in [root, output, charts, report]]
    require(output.is_relative_to(root/'data/processed') and charts.is_relative_to(root/'analysis/charts') and
        report.is_relative_to(root/'analysis/reports'), 'Destinos fuera del área autorizada.')
    require(not output.exists() and not charts.exists() and not report.exists(), 'Elegir destinos nuevos; no se sobrescriben resultados.')
    require(replicates >= 2 and anchor_count >= 2 and n_init >= 2 and n_init % 2 == 0, 'Parámetros inválidos.')
    protected = snapshot_inputs(root, output, charts)
    source_validation(root, protected)
    output.mkdir(parents=True); charts.mkdir(parents=True); (output/'metadata').mkdir()
    started = time.monotonic()
    manifest = dict(status='running', errors=[], started_at_utc=datetime.now(timezone.utc).isoformat(),
        protected_hashes=protected, configuration=dict(feature_sets=FEATURE_SETS, schemes=SCHEMES, ks=KS, seeds=SEEDS,
            n_init=n_init, max_iter=MAX_ITER, weighting=WEIGHTINGS, ns_threshold=.1, min_LN=100, min_specified=100,
            min_source_rows=5, age_range=[18, 100], anchor_count=anchor_count, anchor_seed=319,
            replicates=replicates, sample_fraction=.8, sample_seed=8102024, resample_fit_seed=17,
            sampling='municipality_without_replacement', scaler='unweighted_standard_ddof0',
            initialization='shared_symmetric_bank_half_A_half_B'),
        versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__,
            pyarrow=pa.__version__, matplotlib=matplotlib.__version__))
    save_json(output/'metadata/run_manifest.json', manifest)
    try:
        dependencies = dependency_validation(output)
        metric_rows, stability_rows, comparison_rows, validation_rows, coverage_rows, initialization_rows = [], [], [], [], [], []
        resample_rows, resample_initializations, sample_coverage, sample_comparisons, weights, reconciliation = [], [], [], [], [], []
        contexts, references = {}, {}
        source = root/'data/processed/demographic_pilot'
        states = pd.read_parquet(root/'data/processed/descriptive/state/table.parquet').query('election_year == 2024')
        keys, draws = None, None
        for scheme in SCHEMES:
            full = pd.read_parquet(source/'reference'/f'b_{scheme}.parquet')
            reference = pd.read_csv(source/'metadata'/f'national_reference_{scheme}.csv', dtype={'SEXO': str})
            totals = full.groupby(['age_band', 'SEXO'], observed=True)[METRICS].sum()
            expected = reference.set_index(['age_band', 'SEXO'])[METRICS].sort_index()
            pd.testing.assert_frame_equal(totals.sort_index(), expected, check_dtype=False)
            require(np.allclose(reference.national_participation, reference.SV/(reference.SV+reference.NV), equal_nan=True), 'Referencia nacional alterada.')
            merged = full.merge(reference[['age_band', 'SEXO', 'national_participation']], on=['age_band', 'SEXO'], validate='many_to_one', suffixes=('', '_check'))
            require(np.allclose(merged.national_participation, merged.national_participation_check, equal_nan=True), 'Tasa nacional no corresponde.')
            require(np.allclose(full.participation_deviation_national, full.participation_observed-full.national_participation, equal_nan=True), 'Diferencia nacional alterada.')
            require(not full.duplicated(KEYS).any() and not full.row_id.duplicated().any(), 'Claves duplicadas.')
            for name in ['EDOCVE', 'MPIOCVE', 'SEXO']:
                require(full[name].map(lambda value: isinstance(value, str)).all(), 'Clave no textual.')
            require(full.LN.eq(full.SV+full.NV+full.NS).all(), 'Identidad de conteos fallida.')
            require(full[full.SEXO.eq('2')].source_row_count.sum() == 105, 'SEXO=2 perdido.')
            for state, group in full.groupby('EDOCVE'):
                expected = states[states.EDOCVE.eq(state)].iloc[0]
                for field in METRICS:
                    difference = int(group[field].sum()-expected[field])
                    require(difference == 0, 'Conteo de entidad no conciliado.')
                    reconciliation.append(dict(scheme=scheme, EDOCVE=state, field=field, difference=difference))
            base, full = paired_population(full)
            full['is_eligible'] = base
            require(base.sum() == (22282 if scheme == 'life_stage' else 14190), 'Población distinta del piloto validado.')
            references[scheme] = (full, base)
            if keys is None:
                keys, draws = municipality_samples(full, replicates)
                membership_frame = keys.copy()
                for index, draw in enumerate(draws): membership_frame[f'sample_{index:03d}'] = draw
                save_table(output/'resampling/municipality_membership.parquet', membership_frame)
            else:
                pd.testing.assert_frame_equal(keys, full[MUNICIPAL_KEYS].drop_duplicates().sort_values(MUNICIPAL_KEYS).reset_index(drop=True))
            save_table(output/'reference'/f'b_{scheme}.parquet', full)
            save_table(output/'reference'/f'national_reference_{scheme}.csv', reference)
            scalers = {name: fit_scaler(full.loc[base, columns].to_numpy(), 'standard') for name, columns in FEATURE_SETS.items()}
            require(scalers['absolute']['location'][0] == scalers['relative']['location'][0] and
                scalers['absolute']['scale'][0] == scalers['relative']['scale'][0], 'Escala de edad A/B distinta.')
            for name, columns in FEATURE_SETS.items():
                values = pd.DataFrame(transform(full[columns].to_numpy(dtype=float), scalers[name]), columns=columns)
                values.insert(0, 'row_id', full.row_id)
                save_table(output/'reference'/f'{scheme}_{name}_features.parquet', values)
                save_json(output/'reference'/f'{scheme}_{name}_scaler.json', dict(**scalers[name], feature_columns=columns,
                    training_row_ids_sha256=hashlib.sha256('\n'.join(full.loc[base, 'row_id']).encode()).hexdigest()))
            results = run_models(scheme, full, base, scalers, output, anchor_count, n_init, dependencies['status'])
            scheme_contexts, a, b, c, d, e, f = results
            contexts.update(scheme_contexts)
            metric_rows.extend(a); stability_rows.extend(b); comparison_rows.extend(c); validation_rows.extend(d)
            coverage_rows.extend(e); initialization_rows.extend(f)
            a, b, c, d = run_resampling(scheme, full, base, scheme_contexts, keys, draws, output, n_init)
            resample_rows.extend(a); resample_initializations.extend(b); sample_coverage.extend(c); sample_comparisons.extend(d)
            weights.extend(weight_diagnostics(full, base, scheme))
        frames = {name: pd.DataFrame(rows) for name, rows in [
            ('model_metrics', metric_rows), ('seed_stability', stability_rows), ('partition_comparisons', comparison_rows),
            ('numerical_validation', validation_rows), ('coverage', coverage_rows), ('initializations', initialization_rows),
            ('resample_metrics', resample_rows), ('resample_initializations', resample_initializations),
            ('resample_coverage', sample_coverage), ('resample_representation_comparisons', sample_comparisons),
            ('weight_diagnostics', weights), ('state_reconciliation', reconciliation)]}
        for name, frame in frames.items(): save_table(output/'metadata'/f'{name}.csv', frame)
        age_dominated_control(root, output, references)
        resample_sizes(output, references)
        save_json(output/'metadata/feature_contract.json', dict(election_year=2024, feature_sets=FEATURE_SETS,
            identifiers=['row_id', *KEYS], counts_as_metadata=METRICS, weights_as_metadata=WEIGHTINGS,
            primary_population='complete_supported_18_100_shared_A_B', nulls='preserved_no_imputation',
            projected_labels='only_original_eligible_segments_not_training_claims', reference='previous_national_rates_fixed'))
        require(len(frames['model_metrics']) == 144 and len(frames['resample_metrics']) == 24*replicates, 'Número de ajustes inesperado.')
        require(frames['model_metrics'].converged.all() and frames['resample_metrics'].converged.all(), 'Ajuste sin convergencia.')
        require(frames['model_metrics'].silhouette.between(-1, 1).all() and frames['model_metrics'].davies_bouldin.ge(0).all(), 'Métrica fuera de dominio.')
        plot_results(output, charts, frames['model_metrics'], frames['seed_stability'], frames['partition_comparisons'],
            frames['resample_metrics'], frames['resample_coverage'])
        write_report(output, charts, report, frames['model_metrics'], frames['seed_stability'], frames['partition_comparisons'],
            frames['resample_metrics'], frames['coverage'], frames['resample_coverage'], frames['weight_diagnostics'],
            dependencies, frames['numerical_validation'], len(protected), n_init, anchor_count)
        for path, digest in protected.items(): require(file_hash(path) == digest, f'Archivo existente modificado: {path}')
        manifest.update(status='validated', seconds=round(time.monotonic()-started, 2),
            finished_at_utc=datetime.now(timezone.utc).isoformat(), fitted_main_and_ns_models=len(metric_rows),
            fitted_resample_models=len(resample_rows), protected_files=len(protected),
            dependency_status=dependencies['status'], report_sha256=file_hash(report),
            script_hashes={name: file_hash(root/'analysis/scripts'/name) for name in
                ['compare_demographic_features.py', 'clustering_core.py', 'run_demographic_pilot.py']},
            artifact_hashes={str(path.relative_to(root)): file_hash(path) for directory in [output, charts]
                for path in directory.rglob('*') if path.is_file() and path != output/'metadata/run_manifest.json'})
        save_json(output/'metadata/run_manifest.json', manifest)
        save_json(output/'_SUCCESS', dict(manifest_sha256=file_hash(output/'metadata/run_manifest.json')))
        print(f'VALIDADO: {len(metric_rows)+len(resample_rows)} ajustes; {report.relative_to(root)}', flush=True)
    except Exception as error:
        manifest['status'] = 'failed'; manifest['errors'].append(dict(type=type(error).__name__, message=str(error)))
        save_json(output/'metadata/run_manifest.json', manifest)
        raise


def review_existing(root, output, charts, report, **unused):
    """Revisa sólo los derivados propios ya validados; no vuelve a ajustar modelos."""
    root, output, charts, report = [Path(path).resolve() for path in [root, output, charts, report]]
    require(output.is_relative_to(root/'data/processed') and charts.is_relative_to(root/'analysis/charts') and
        report.is_relative_to(root/'analysis/reports'), 'Destinos fuera del área autorizada.')
    manifest_path = output/'metadata/run_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(manifest['status'] == 'validated' and manifest['configuration'].get('feature_sets') == FEATURE_SETS,
        'Este destino no corresponde a una comparación A/B validada.')
    marker = output/'_SUCCESS'
    require(json.loads(marker.read_text())['manifest_sha256'] == file_hash(manifest_path), 'Marcador de resultados inválido.')
    require(file_hash(report) == manifest['report_sha256'], 'Informe distinto del registrado.')
    for relative, digest in manifest['artifact_hashes'].items():
        require(file_hash(root/relative) == digest, f'Derivado alterado antes de revisión: {relative}')
    for path, digest in manifest['protected_hashes'].items():
        require(file_hash(path) == digest, f'Fuente previa alterada: {path}')
    frames = {name: pd.read_csv(output/'metadata'/f'{name}.csv') for name in ['model_metrics', 'seed_stability',
        'partition_comparisons', 'resample_metrics', 'coverage', 'resample_coverage', 'weight_diagnostics', 'numerical_validation']}
    dependencies = json.loads((output/'metadata/dependency_validation.json').read_text(encoding='utf-8'))
    marker.unlink()  # Únicamente el marcador propio, previamente comprobado.
    try:
        control = output/'metadata/age_dominated_reference.csv'
        if not control.exists():
            references = {}
            for scheme in SCHEMES:
                full = pd.read_parquet(output/'reference'/f'b_{scheme}.parquet')
                references[scheme] = (full, full.is_eligible.to_numpy())
            age_dominated_control(root, output, references)
        if not (output/'metadata/resample_cluster_sizes.csv').exists():
            references = {}
            for scheme in SCHEMES:
                full = pd.read_parquet(output/'reference'/f'b_{scheme}.parquet')
                references[scheme] = (full, full.is_eligible.to_numpy())
            resample_sizes(output, references)
        plot_results(output, charts, frames['model_metrics'], frames['seed_stability'], frames['partition_comparisons'],
            frames['resample_metrics'], frames['resample_coverage'])
        write_report(output, charts, report, frames['model_metrics'], frames['seed_stability'], frames['partition_comparisons'],
            frames['resample_metrics'], frames['coverage'], frames['resample_coverage'], frames['weight_diagnostics'],
            dependencies, frames['numerical_validation'], len(manifest['protected_hashes']),
            manifest['configuration']['n_init'], manifest['configuration']['anchor_count'])
        initial_attempt = root/'analysis/.run_failures/demographic_comparison_01/data/metadata/run_manifest.json'
        if initial_attempt.exists():
            previous = json.loads(initial_attempt.read_text(encoding='utf-8'))
            manifest['development_incidents'] = dict(initial_attempt_status=previous['status'],
                errors=previous['errors'], resolution='Corregido antes de ajustar modelos; prueba integrada de contextos/remuestreo añadida.')
        for path, digest in manifest['protected_hashes'].items():
            require(file_hash(path) == digest, f'Fuente previa alterada durante revisión: {path}')
        manifest.update(review_refreshed_at_utc=datetime.now(timezone.utc).isoformat(), review_script_sha256=file_hash(Path(__file__)),
            report_sha256=file_hash(report), artifact_hashes={str(path.relative_to(root)): file_hash(path)
                for directory in [output, charts] for path in directory.rglob('*')
                if path.is_file() and path != manifest_path})
        save_json(manifest_path, manifest)
        save_json(marker, dict(manifest_sha256=file_hash(manifest_path)))
        print('REVISIÓN VALIDADA: sin reajustar modelos.', flush=True)
    except Exception as error:
        manifest['status'] = 'failed'; manifest['errors'].append(dict(type=type(error).__name__, message=str(error)))
        save_json(manifest_path, manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, default=Path('data/processed/demographic_representation_comparison'))
    parser.add_argument('--charts', type=Path, default=Path('analysis/charts/demographic_representation_comparison'))
    parser.add_argument('--report', type=Path, default=Path('analysis/reports/demographic_representation_comparison.md'))
    parser.add_argument('--replicates', type=int, default=30)
    parser.add_argument('--anchor-count', type=int, default=1200)
    parser.add_argument('--n-init', type=int, default=10)
    parser.add_argument('--review-existing', action='store_true', help='Revisar sólo la documentación de estos resultados validados, sin ajustar.')
    args = parser.parse_args()
    root = args.root.resolve()
    runner = review_existing if args.review_existing else run_comparison
    runner(root, *[path if path.is_absolute() else root/path for path in [args.output, args.charts, args.report]],
        replicates=args.replicates, anchor_count=args.anchor_count, n_init=args.n_init)


if __name__ == '__main__':
    main()
