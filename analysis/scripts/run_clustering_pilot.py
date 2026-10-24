"""Primer piloto territorial 2024: Ward, K-Means y DBSCAN reproducibles.

No instala dependencias, asigna municipios pendientes ni selecciona un modelo.
Sólo las copias nuevas del experimento se transforman estadísticamente.
"""

from __future__ import annotations

import os
# Control local del proceso para reducir variación de reducciones BLAS.
for thread_variable in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[thread_variable] = '1'

import argparse
from datetime import datetime, timezone
from itertools import combinations
import json
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd
import pyarrow as pa

from clean_data import file_hash, require, save_json
from build_descriptive import COUNTS, METRICS, number, pct, markdown_table
from build_cluster_features import save_table, snapshot_inputs
from clustering_core import (adjusted_rand, centroid_matching, cut_linkage, dbscan, fit_scaler,
    geometric_elbow, inverse_transform, kmeans, pairwise_distances, pattern_decomposition,
    transform, validation_metrics, ward_linkage)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

KS = list(range(2, 11))
SEEDS = [17, 42, 2024]
SCALINGS = ['original', 'standard', 'robust']
EPS_QUANTILES = [.50, .75, .90, .95]
N_INIT = 10
MAX_ITER = 300
PAPER_URL = 'https://arxiv.org/html/2502.00851v2'


def eligibility(metadata, ns_filter=False):
    mask = metadata.can_use_complete_algorithms & ~metadata.has_low_support_features
    if ns_filter: mask &= ~metadata.has_high_ns_features
    return mask.to_numpy(dtype=bool)


def experiment_metadata(metadata, mask, scenario):
    result = metadata.copy()
    result['is_training'] = mask
    result['pending_reason'] = np.where(mask, 'in_experiment',
        np.where(~result.can_use_complete_algorithms, 'incomplete_rates',
            np.where(result.has_low_support_features, 'low_support',
                'outside_closed_main_population' if scenario == 'tail_75plus' else 'ns_at_least_10_percent')))
    result['scenario'] = scenario
    return result


def build_open_tail(root, closed_features, closed_metadata, feature_names):
    """Las diez coordenadas se alinean con Etapas, sustituyendo sólo 75–100 por 75+."""
    source = pd.read_parquet(root/'data/processed/cluster_features/matrices/b_life_stage_open/metadata.parquet')
    core = source[source.SEXO.isin(['0', '1'])].copy()
    core['feature_name'] = 'participation_'+core.age_band.str.replace('-', '_', regex=False).str.replace('+', '_plus', regex=False)+'_'+core.SEXO.map({'0': 'men', '1': 'women'})
    keys = ['election_year', 'EDOCVE', 'MPIOCVE']
    names = [name.replace('75_100', '75_plus') for name in feature_names]
    wide = core.pivot(index=keys, columns='feature_name', values='participation_observed')
    index = pd.MultiIndex.from_frame(closed_metadata[keys])
    values = wide.reindex(index=index, columns=names).to_numpy(dtype=float)
    raw = pd.DataFrame(values, columns=names)
    raw.insert(0, 'row_id', closed_features.row_id.to_numpy())
    quality = core.groupby(keys, observed=True).agg(core_LN=('LN', 'sum'),
        core_specified_count=('specified_count', 'sum'),
        low_support_feature_count=('has_low_support', 'sum'), high_ns_feature_count=('has_high_unspecified_rate', 'sum'))
    metadata = closed_metadata.copy()
    for name in quality:
        metadata[name] = quality.reindex(index)[name].to_numpy()
    metadata['has_low_support_features'] = metadata.low_support_feature_count.gt(0)
    metadata['has_high_ns_features'] = metadata.high_ns_feature_count.gt(0)
    metadata['can_use_complete_algorithms'] = np.isfinite(values).all(axis=1)
    metadata['null_feature_count'] = np.isnan(values).sum(axis=1)
    metadata['complement_LN'] = metadata.LN-metadata.core_LN
    require(np.allclose(values[:, :8], closed_features[feature_names].to_numpy()[:, :8], equal_nan=True), 'La cola alteró edades anteriores a 75.')
    require((~eligibility(closed_metadata) | eligibility(metadata)).all(), 'La comparación de cola no comparte todos los municipios principales.')
    return raw, metadata, names


def epsilon_grid(distances, dimensions):
    """Vecino min_samples incluye el propio punto; eps cubre densidades diferentes."""
    base = max(5, dimensions+1)
    rows, curves = [], []
    for min_samples in [base, 2*base]:
        require(min_samples <= len(distances), 'Muestra demasiado pequeña para el min_samples configurado.')
        kth = np.partition(distances, min_samples-1, axis=1)[:, min_samples-1]
        ordered = np.sort(kth)
        for rank, value in enumerate(ordered):
            curves.append(dict(min_samples=min_samples, rank=rank+1, distance=float(value)))
        for quantile in EPS_QUANTILES:
            eps = float(np.quantile(kth, quantile))
            if eps > 0:
                rows.append(dict(min_samples=min_samples, eps=eps, eps_rule=f'q{int(100*quantile)}', neighbor_quantile=quantile))
    return rows, curves


def label_change_fraction(left, right):
    """Cambio mínimo después de permutar etiquetas; no compara números arbitrarios."""
    _, a = np.unique(left, return_inverse=True)
    _, b = np.unique(right, return_inverse=True)
    k = max(a.max(initial=-1), b.max(initial=-1))+1
    if not len(a) or k > 10: return np.nan
    counts = np.zeros((k, k), dtype=int)
    np.add.at(counts, (a, b), 1)
    states = {0: (0, [])}
    for mask in range(1 << k):
        if mask not in states: continue
        score, selected = states[mask]
        row = len(selected)
        if row == k: continue
        for column in range(k):
            if mask & (1 << column): continue
            new_mask, new_score = mask | (1 << column), score+counts[row, column]
            if new_mask not in states or new_score > states[new_mask][0]: states[new_mask] = (new_score, selected+[column])
    return float(1-states[(1 << k)-1][0]/len(a))


def compare_partitions(left, right):
    left, right = np.asarray(left), np.asarray(right)
    common = np.isfinite(left) & np.isfinite(right)
    left, right = left[common].astype(int), right[common].astype(int)
    nonnoise = (left != -1) & (right != -1)
    return dict(common_observations=len(left), ari_including_noise=adjusted_rand(left, right),
        common_nonnoise_observations=int(nonnoise.sum()),
        ari_common_nonnoise=adjusted_rand(left[nonnoise], right[nonnoise]),
        changed_fraction_after_label_alignment=label_change_fraction(left, right),
        trivial_all_noise=bool(len(left) and (left == -1).all() and (right == -1).all()))


def run_context(context_id, representation, scenario, scaling, features, metadata, feature_names, mask,
                output, charts, scaler=None, eps_parameters=None, seeds=SEEDS, ks=KS, n_init=N_INIT):
    """Un contexto comparte población y distancia; nunca modifica fuentes."""
    folder = output/'contexts'/context_id
    folder.mkdir(parents=True)
    raw_all = features[feature_names].to_numpy(dtype=float)
    raw = raw_all[mask]
    require(np.isfinite(raw).all() and len(raw) > max(ks), 'Matriz principal incompleta o insuficiente.')
    parameters = fit_scaler(raw, scaling) if scaler is None else scaler
    values = transform(raw, parameters)
    transformed = pd.DataFrame(values, columns=feature_names)
    transformed.insert(0, 'row_id', features.loc[mask, 'row_id'].to_numpy())
    save_table(folder/'training_matrix.parquet', transformed)
    save_table(folder/'raw_features.parquet', features)
    context_metadata = experiment_metadata(metadata, mask, scenario)
    save_table(folder/'metadata.parquet', context_metadata)
    save_table(folder/'pending_assignment.parquet', context_metadata[~mask])
    save_json(folder/'scaler.json', dict(**parameters, feature_columns=feature_names,
        fitted_on='this_context' if scaler is None else 'main_context_same_representation_and_scaling',
        backend='NumPy, fórmulas de StandardScaler/RobustScaler; sin instalar scikit-learn'))
    distances = pairwise_distances(values)
    linkage = ward_linkage(distances)
    save_table(folder/'ward_linkage.parquet', pd.DataFrame(linkage, columns=['left', 'right', 'distance', 'members']))
    if eps_parameters is None:
        eps_parameters, distance_curves = epsilon_grid(distances, raw.shape[1])
        save_table(folder/'k_distance.csv', pd.DataFrame(distance_curves))
    else:
        _, distance_curves = epsilon_grid(distances, raw.shape[1])
        save_table(folder/'k_distance.csv', pd.DataFrame(distance_curves))
    save_json(folder/'dbscan_grid.json', eps_parameters)
    all_labels = pd.DataFrame(dict(row_id=features.row_id))
    metrics, centers_rows, sizes_rows, initializations, stability, comparisons = [], [], [], [], [], []
    labels_by_model, km_runs, model_info = {}, {}, {}
    q1, q3 = np.percentile(raw, [25, 75], axis=0)
    extreme = ((raw < q1-1.5*(q3-q1)) | (raw > q3+1.5*(q3-q1))).any(axis=1)
    training_metadata = metadata.loc[mask].reset_index(drop=True)

    def record(model_id, algorithm, labels, inertia=np.nan, seed=None, k=None, eps=None, min_samples=None,
               converged=True, iterations=None):
        labels = np.asarray(labels, dtype=int)
        nonnoise = labels >= 0
        cluster_labels = np.unique(labels[nonnoise])
        validation_all = validation_metrics(values, labels, distances)
        if nonnoise.all(): validation = validation_all
        else:
            validation = validation_metrics(values[nonnoise], labels[nonnoise], distances[np.ix_(nonnoise, nonnoise)])
        counts = {str(int(label)): int((labels == label).sum()) for label in np.unique(labels)}
        row = dict(context_id=context_id, representation=representation, scenario=scenario, scaling=scaling,
            model_id=model_id, algorithm=algorithm, k=k, seed=seed, eps=eps, min_samples=min_samples,
            clusters=len(cluster_labels), observations=len(raw), total_municipalities=len(metadata),
            represented_LN=int(training_metadata.LN.sum()), training_LN_share=float(training_metadata.LN.sum()/metadata.LN.sum()),
            inertia=inertia, silhouette=validation['silhouette'], davies_bouldin=validation['davies_bouldin'],
            metric_status=validation['metric_status'], metric_observations=int(nonnoise.sum()),
            silhouette_including_noise=validation_all['silhouette'], davies_bouldin_including_noise=validation_all['davies_bouldin'],
            metric_status_including_noise=validation_all['metric_status'],
            noise_observations=int((~nonnoise).sum()), noise_fraction=float((~nonnoise).mean()),
            noise_LN=int(training_metadata.loc[~nonnoise, 'LN'].sum()),
            noise_LN_fraction=float(training_metadata.loc[~nonnoise, 'LN'].sum()/training_metadata.LN.sum()),
            noise_LN_fraction_all_municipalities=float(training_metadata.loc[~nonnoise, 'LN'].sum()/metadata.LN.sum()),
            smallest_cluster=min([count for key, count in counts.items() if key != '-1'], default=0),
            largest_cluster=max([count for key, count in counts.items() if key != '-1'], default=0),
            cluster_sizes=json.dumps(counts, sort_keys=True), converged=converged, iterations=iterations,
            stability=np.nan, stability_type='not_evaluated',
            **(pattern_decomposition(raw[nonnoise], labels[nonnoise]) if len(cluster_labels) >= 2 else
               dict(between_level_share=np.nan, between_shape_share=np.nan, level_explained=np.nan, shape_explained=np.nan)))
        if algorithm == 'kmeans':
            centers = np.array([values[labels == index].mean(axis=0) for index in cluster_labels])
            errors = np.sum((values-centers[labels])**2, axis=1)
            row.update(top_one_percent_sse_share=float(np.sort(errors)[-max(1, int(np.ceil(.01*len(errors)))):].sum()/errors.sum()),
                       iqr_extreme_observations=int(extreme.sum()), iqr_extreme_sse_share=float(errors[extreme].sum()/errors.sum()))
        metrics.append(row)
        full = np.full(len(metadata), np.nan)
        full[mask] = labels
        all_labels[model_id] = pd.array(full, dtype='Int64')
        labels_by_model[model_id] = full
        model_info[model_id] = dict(algorithm=algorithm, k=k, seed=seed, eps=eps, min_samples=min_samples)
        for label, count in counts.items():
            selected = labels == int(label)
            sizes_rows.append(dict(context_id=context_id, model_id=model_id, cluster=int(label), municipalities=count,
                LN=int(training_metadata.loc[selected, 'LN'].sum()), NS=int(training_metadata.loc[selected, 'NS'].sum()),
                is_noise=label == '-1'))
        for label in cluster_labels:
            center_raw, center_scaled = raw[labels == label].mean(axis=0), values[labels == label].mean(axis=0)
            for index, name in enumerate(feature_names):
                centers_rows.append(dict(context_id=context_id, model_id=model_id, cluster=int(label), feature=name,
                    rate_mean_original=float(center_raw[index]), centroid_transformed=float(center_scaled[index]),
                    municipalities=int((labels == label).sum())))

    for k in ks:
        ward_labels = cut_linkage(linkage, k)
        record(f'ward_k{k:02}', 'ward', ward_labels, k=k)
        seed_runs = []
        for seed in seeds:
            result = kmeans(values, k, seed, n_init=n_init, max_iter=MAX_ITER)
            model_id = f'kmeans_k{k:02}_seed{seed}'
            record(model_id, 'kmeans', result['labels'], inertia=result['inertia'], seed=seed, k=k,
                   converged=result['converged'], iterations=result['iterations'])
            seed_runs.append((seed, result))
            initializations.extend(dict(context_id=context_id, model_id=model_id, **row) for row in result['initializations'])
            comparisons.append(dict(context_id=context_id, comparison='ward_vs_kmeans', k=k, seed=seed,
                                    **compare_partitions(ward_labels, result['labels'])))
        km_runs[k] = seed_runs
        for (seed_a, a), (seed_b, b) in combinations(seed_runs, 2):
            matched = centroid_matching(a['centers'], b['centers'])
            raw_a, raw_b = inverse_transform(a['centers'], parameters), inverse_transform(b['centers'][matched], parameters)
            stability.append(dict(context_id=context_id, k=k, seed_a=seed_a, seed_b=seed_b,
                centroid_rmse_original_rates=float(np.sqrt(np.mean((raw_a-raw_b)**2))),
                max_centroid_coordinate_change_pp=float(100*np.max(np.abs(raw_a-raw_b))),
                **compare_partitions(a['labels'], b['labels'])))
    dbscan_models = []
    for configuration in eps_parameters:
        labels, core = dbscan(distances, configuration['eps'], configuration['min_samples'])
        model_id = f"dbscan_ms{configuration['min_samples']}_{configuration['eps_rule']}"
        record(model_id, 'dbscan', labels, eps=configuration['eps'], min_samples=configuration['min_samples'])
        model_info[model_id]['eps_rule'] = configuration['eps_rule']
        metrics[-1]['core_observations'] = int(core.sum())
        dbscan_models.append((model_id, labels, configuration))
    density_stability = []
    for a, b in zip(dbscan_models, dbscan_models[1:]):
        if a[2]['min_samples'] != b[2]['min_samples']: continue
        density_stability.append(dict(context_id=context_id, model_a=a[0], model_b=b[0],
                                     **compare_partitions(a[1], b[1])))
    metrics_frame, stability_frame = pd.DataFrame(metrics), pd.DataFrame(stability)
    for k, selected in stability_frame.groupby('k'):
        mask_k = metrics_frame.algorithm.eq('kmeans') & metrics_frame.k.eq(k)
        metrics_frame.loc[mask_k, 'stability'] = selected.ari_including_noise.mean()
        metrics_frame.loc[mask_k, 'stability_type'] = 'mean_pairwise_seed_ari'
    for model_id in metrics_frame.loc[metrics_frame.algorithm.eq('dbscan'), 'model_id']:
        selected = [row for row in density_stability if row['model_a'] == model_id or row['model_b'] == model_id]
        valid = [row['ari_including_noise'] for row in selected if not row['trivial_all_noise']]
        if valid:
            metrics_frame.loc[metrics_frame.model_id.eq(model_id), 'stability'] = np.mean(valid)
            metrics_frame.loc[metrics_frame.model_id.eq(model_id), 'stability_type'] = 'adjacent_eps_ari_including_noise'
    save_table(folder/'labels.parquet', all_labels)
    for name, frame in [('metrics.csv', metrics_frame), ('cluster_sizes.csv', pd.DataFrame(sizes_rows)),
        ('centroids.csv', pd.DataFrame(centers_rows)), ('kmeans_initializations.csv', pd.DataFrame(initializations)),
        ('seed_stability.csv', stability_frame), ('ward_kmeans_ari.csv', pd.DataFrame(comparisons)),
        ('dbscan_parameter_stability.csv', pd.DataFrame(density_stability))]: save_table(folder/name, frame)
    elbow_rows, elbow_choices = [], []
    best_sse = [min(result['inertia'] for _, result in km_runs[k]) for k in ks]
    for axis_mode in ['raw', 'sse_relative', 'unit_axes']:
        selected, rows, status = geometric_elbow(ks, best_sse, axis_mode)
        elbow_choices.append(dict(context_id=context_id, axis_mode=axis_mode, suggested_k=selected, status=status))
        elbow_rows.extend(dict(context_id=context_id, **row) for row in rows)
    save_table(folder/'geometric_elbow.csv', pd.DataFrame(elbow_rows))
    save_table(folder/'elbow_candidates.csv', pd.DataFrame(elbow_choices))
    save_table(folder/'sse_curve.csv', pd.DataFrame(dict(k=ks, best_sse=best_sse)))
    if scenario == 'main':
        plot_context(charts, context_id, linkage, metrics_frame, pd.DataFrame(sizes_rows),
                     pd.DataFrame(distance_curves), best_sse, ks, elbow_choices, labels_by_model, mask)
        order = dendrogram_order(linkage)
        save_table(folder/'ward_leaf_order.csv', pd.DataFrame(dict(leaf_position=np.arange(len(order)),
                   training_position=order, row_id=transformed.row_id.to_numpy()[order])))
    return dict(context_id=context_id, representation=representation, scenario=scenario, scaling=scaling,
        metrics=metrics_frame, labels=labels_by_model, model_info=model_info, scaler=parameters,
        eps_parameters=eps_parameters, stability=stability_frame, comparisons=pd.DataFrame(comparisons),
        density_stability=pd.DataFrame(density_stability), elbow_choices=elbow_choices,
        coverage=dict(context_id=context_id, representation=representation, scenario=scenario, scaling=scaling,
            training_municipalities=int(mask.sum()), pending_municipalities=int((~mask).sum()),
            training_LN=int(metadata.loc[mask, 'LN'].sum()), total_LN=int(metadata.LN.sum()),
            training_LN_share=float(metadata.loc[mask, 'LN'].sum()/metadata.LN.sum())))


def cross_context_comparisons(reference, candidate, comparison_type):
    rows = []
    for model_id in reference['labels'].keys() & candidate['labels'].keys():
        info = reference['model_info'][model_id]
        rows.append(dict(comparison=comparison_type, reference_context=reference['context_id'],
            candidate_context=candidate['context_id'], model_id=model_id, **info,
            **compare_partitions(reference['labels'][model_id], candidate['labels'][model_id])))
    return rows


def dendrogram_order(linkage):
    n = len(linkage)+1
    leaves = []
    def visit(node):
        if node < n: leaves.append(node)
        else:
            visit(int(linkage[node-n, 0])); visit(int(linkage[node-n, 1]))
    visit(2*n-2)
    return np.array(leaves)


def draw_dendrogram(linkage, ax, truncate=None):
    n = len(linkage)+1
    labels, position = [], [0]
    def visit(node):
        if node < n or (truncate is not None and node < 2*n-truncate):
            x = position[0]; position[0] += 1
            size = 1 if node < n else int(linkage[node-n, 3])
            labels.append(str(node) if size == 1 else f'n={size}')
            if size > 1: ax.scatter([x], [0], marker='^', s=25, color='#555555')
            return x, 0.
        left, right, height, _ = linkage[node-n]
        a, ha = visit(int(left)); b, hb = visit(int(right))
        ax.plot([a, a, b, b], [ha, height, height, hb], color='#386cb0', linewidth=.6)
        return (a+b)/2, height
    visit(2*n-2)
    ax.set_ylabel('Altura Ward (unidades de la configuración)')
    if truncate:
        ax.set_xticks(range(len(labels)), labels, rotation=65, fontsize=7)
        ax.set_xlabel('Subárboles contraídos; n indica municipios, sin nombres de perfiles')
    else:
        ax.set_xticks([]); ax.set_xlabel(f'{n:,} hojas; correspondencia territorial en metadata y orden del árbol')


def plot_context(charts, context_id, linkage, metrics, sizes, distances, sse, ks, elbows, labels, mask):
    folder = charts/context_id
    folder.mkdir()
    fig, ax = plt.subplots(figsize=(15, 5), layout='constrained')
    draw_dendrogram(linkage, ax, truncate=30)
    ax.set_title(context_id+' · Ward, últimos 30 subárboles\nEl árbol completo se conserva en SVG y Parquet')
    fig.savefig(folder/'ward_dendrogram.png', dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(18, 5), layout='constrained')
    draw_dendrogram(linkage, ax)
    ax.set_title(context_id+' · dendrograma completo, ampliable')
    fig.savefig(folder/'ward_dendrogram_full.svg'); plt.close(fig)
    order = dendrogram_order(linkage)
    fig, ax = plt.subplots(figsize=(14, 4), layout='constrained')
    cuts = np.array([labels[f'ward_k{k:02}'][mask][order] for k in ks])
    ax.imshow(cuts, cmap='tab20', interpolation='nearest', aspect='auto', vmin=0, vmax=19)
    ax.set_yticks(range(len(ks)), [f'K={k}' for k in ks]); ax.set_xticks([])
    ax.set_title(context_id+' · comparación de cortes Ward\nColores son etiquetas locales; no perfiles definitivos')
    ax.set_xlabel('Municipios en orden de hojas del mismo árbol')
    fig.savefig(folder/'ward_cuts.png', dpi=150); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
    axes[0].plot(ks, sse, 'o-', color='#386cb0')
    axes[0].set(xlabel='K experimental', ylabel='SSE mínima entre semillas', title='Codo tradicional · ejes originales')
    axes[0].set_xticks(ks); axes[0].set_ylim(bottom=0)
    normalized = (np.array(sse)-min(sse))/(max(sse)-min(sse))
    x = (np.array(ks)-min(ks))/(max(ks)-min(ks))
    axes[1].plot(x, normalized, 'o-', color='#1b9e77')
    axes[1].set_xticks(x, ks); axes[1].set_aspect('equal', adjustable='box')
    axes[1].set(xlabel='K, posiciones normalizadas 0–1', ylabel='SSE, rango normalizado 0–1', title='Control de aspecto · misma SSE')
    for choice, color in zip(elbows, ['#d95f02', '#7570b3', '#e6ab02']):
        if choice['suggested_k']:
            axes[0].axvline(choice['suggested_k'], color=color, linestyle=':', alpha=.8,
                            label=f"Geom. {choice['axis_mode']}: K={choice['suggested_k']}")
    axes[0].legend(fontsize=7)
    fig.suptitle(context_id+' · sugerencias geométricas experimentales, sin elegir K')
    fig.savefig(folder/'kmeans_elbow.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
    for ax, variable, title in zip(axes, ['silhouette', 'davies_bouldin'], ['Silhouette (mayor)', 'Davies–Bouldin (menor)']):
        ward = metrics[metrics.algorithm.eq('ward')].set_index('k').reindex(ks)
        km = metrics[metrics.algorithm.eq('kmeans')].groupby('k')[variable].agg(['mean', 'min', 'max']).reindex(ks)
        ax.plot(ks, ward[variable], 's-', color='#386cb0', label='Ward')
        ax.plot(ks, km['mean'], 'o-', color='#d95f02', label='K-Means, media de semillas')
        ax.fill_between(ks, km['min'], km['max'], color='#d95f02', alpha=.18, label='Rango de semillas; no IC')
        ax.set(xlabel='K experimental', ylabel=title); ax.set_xticks(ks); ax.legend(fontsize=8)
    fig.suptitle(context_id+' · validación interna, todos los municipios del entrenamiento')
    fig.savefig(folder/'validation_by_k.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
    for ax, algorithm in zip(axes, ['ward', 'kmeans']):
        for position, k in enumerate(ks):
            model_id = f'ward_k{k:02}' if algorithm == 'ward' else f'kmeans_k{k:02}_seed{SEEDS[0]}'
            selected = sizes[sizes.model_id.eq(model_id)].sort_values('cluster')
            bottom = 0
            for row in selected.itertuples():
                ax.bar(position, row.municipalities, bottom=bottom, color=plt.get_cmap('tab20')(row.cluster % 20))
                bottom += row.municipalities
        ax.set_xticks(range(len(ks)), ks); ax.set(xlabel='K', ylabel='Municipios', title=algorithm+' · tamaños por etiqueta local')
    fig.suptitle(context_id+' · tamaños, K-Means semilla '+str(SEEDS[0]))
    fig.savefig(folder/'cluster_sizes.png', dpi=160); plt.close(fig)
    groups = list(distances.groupby('min_samples', sort=True))
    fig, axes = plt.subplots(1, len(groups), figsize=(12, 4.5), layout='constrained', squeeze=False)
    for ax, (minimum, frame) in zip(axes.ravel(), groups):
        ax.plot(frame['rank'], frame.distance, color='#386cb0')
        models = metrics[metrics.algorithm.eq('dbscan') & metrics.min_samples.eq(minimum)]
        for row in models.itertuples(): ax.axhline(row.eps, alpha=.5, linestyle=':', label=f'eps={row.eps:.3g}')
        ax.set(xlabel='Municipios ordenados', ylabel='Distancia al vecino min_samples (incluye propio)', title=f'min_samples={minimum}')
        ax.legend(fontsize=8)
    fig.suptitle(context_id+' · k-distance y eps por cuantiles 50/75/90/95')
    fig.savefig(folder/'dbscan_k_distance.png', dpi=160); plt.close(fig)
    density = metrics[metrics.algorithm.eq('dbscan')]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
    for minimum, frame in density.groupby('min_samples', sort=True):
        axes[0].plot(frame.eps, frame.noise_fraction, 'o-', label=f'min_samples={minimum}')
        axes[1].plot(frame.eps, frame.silhouette, 'o-', label=f'min_samples={minimum}')
        for row in frame.itertuples(): axes[0].annotate(f'{row.clusters} grupos', (row.eps, row.noise_fraction), fontsize=7)
    axes[0].yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].set(xlabel='eps', ylabel='Municipios ruido / entrenamiento')
    axes[1].set(xlabel='eps', ylabel='Silhouette sin ruido; hueco si no definido')
    for ax in axes: ax.legend(fontsize=8)
    fig.suptitle(context_id+' · DBSCAN; ruido no implica error')
    fig.savefig(folder/'dbscan_results.png', dpi=160); plt.close(fig)


def plot_summary(charts, metrics, stability, sensitivity, tail_rates):
    main = metrics[metrics.scenario.eq('main')]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), layout='constrained')
    for row, representation in enumerate(['c_broad', 'c_life_stage']):
        for column, scaling in enumerate(SCALINGS):
            frame = stability[stability.context_id.eq(f'{representation}_{scaling}_main')]
            summary = frame.groupby('k').ari_including_noise.agg(['mean', 'min', 'max'])
            ax = axes[row, column]
            ax.plot(summary.index, summary['mean'], 'o-', color='#386cb0')
            ax.fill_between(summary.index, summary['min'], summary['max'], color='#386cb0', alpha=.2)
            ax.set(ylim=(0, 1.02), xlabel='K', ylabel='ARI entre semillas', title=representation+' · '+scaling)
    fig.suptitle('Estabilidad de asignaciones K-Means · tres semillas, diez inicializaciones cada una')
    fig.savefig(charts/'seed_stability.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), layout='constrained')
    for row, representation in enumerate(['c_broad', 'c_life_stage']):
        for column, scaling in enumerate(SCALINGS):
            ax = axes[row, column]
            for algorithm, color in [('ward', '#386cb0'), ('kmeans', '#d95f02')]:
                selected = main[main.representation.eq(representation) & main.scaling.eq(scaling) & main.algorithm.eq(algorithm)]
                summary = selected.groupby('k').between_shape_share.mean()
                ax.plot(summary.index, summary, 'o-', color=color, label=algorithm)
            ax.set(ylim=(0, 1), xlabel='K', ylabel='Fracción de separación debida a forma', title=representation+' · '+scaling)
            ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.legend(fontsize=8)
    fig.suptitle('Nivel general frente a patrón por edad/sexo · descomposición en tasas originales\nForma = perfil menos su media de coordenadas; no participación nacional')
    fig.savefig(charts/'level_shape_separation.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
    for ax, comparison, title in zip(axes,
        ['ns_threshold_same_scale_and_grid', 'over_100_same_municipalities_and_parameters'],
        ['Sensibilidad NS<10 % por coordenada', 'Sensibilidad 75+ frente a 75–100']):
        frame = sensitivity[sensitivity.comparison.eq(comparison) & sensitivity.algorithm.ne('dbscan')]
        for algorithm, color in [('ward', '#386cb0'), ('kmeans', '#d95f02')]:
            selected = frame[frame.algorithm.eq(algorithm)]
            summary = selected.groupby('k').ari_including_noise.agg(['mean', 'min', 'max'])
            ax.plot(summary.index, summary['mean'], 'o-', color=color, label=algorithm)
            ax.fill_between(summary.index, summary['min'], summary['max'], color=color, alpha=.15)
        ax.set(ylim=(0, 1.02), xlabel='K', ylabel='ARI en municipios compartidos', title=title); ax.legend()
    fig.suptitle('Sensibilidad de agrupaciones; bandas resumen configuraciones y semillas, no IC')
    fig.savefig(charts/'sensitivity_ari.png', dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4.6), layout='constrained')
    for in_main, color, label in [(False, '#aaaaaa', 'Pendientes en Etapas principal'), (True, '#386cb0', 'Entrenamiento principal')]:
        values = tail_rates.loc[tail_rates.in_main.eq(in_main), 'difference_pp'].dropna()
        ax.hist(values, bins=60, histtype='step', color=color, label=label)
    ax.set_yscale('symlog', linthresh=1)
    ax.set(xlabel='Participación 75+ menos 75–100 (pp)', ylabel='Coordenadas municipales H/M (frecuencia)',
           title='Cambio de tasas al incorporar >100 en 75+ · se conservan todas las referencias')
    ax.legend(); fig.savefig(charts/'tail_rate_changes.png', dpi=160); plt.close(fig)


def write_report(root, output, charts, report, metrics, coverage, stability, ward_comparison,
                 elbows, sensitivity, scaling_comparisons, representation_comparisons, tail_rates, protected_count):
    table = markdown_table
    main = metrics[metrics.scenario.eq('main')]
    main_stability = stability[stability.context_id.str.endswith('_main')]
    def fmt(value): return 'n/d' if pd.isna(value) else f'{value:.4f}'
    def image(name, text): return f'![{text}]({Path(os.path.relpath(charts/name, report.parent)).as_posix()})'
    def short(context): return context.replace('c_', '').replace('_main', '')
    best_rows, guidance = [], []
    for context, selected in main.groupby('context_id', sort=True):
        for algorithm in ['ward', 'kmeans', 'dbscan']:
            current = selected[selected.algorithm.eq(algorithm)].dropna(subset='silhouette')
            if current.empty:
                best_rows.append([short(context), algorithm, 'sin métrica definida', '', '', '', '', '', ''])
                continue
            best = current.loc[current.silhouette.idxmax()]
            parameters = f'K={int(best.k)}' if algorithm != 'dbscan' else f'eps={best.eps:.5g}; min_samples={int(best.min_samples)}'
            if algorithm == 'kmeans': parameters += f'; seed={int(best.seed)}'
            best_rows.append([short(context), algorithm, parameters, best.clusters, best.observations,
                fmt(best.silhouette), fmt(best.davies_bouldin), fmt(best.stability), pct(best.noise_fraction)])
        km = selected[selected.algorithm.eq('kmeans')]
        grouped = km.groupby('k').agg(silhouette=('silhouette', 'mean'), db=('davies_bouldin', 'mean'),
                                     stability=('stability', 'mean'), sse=('inertia', 'min'))
        choices = elbows[elbows.context_id.eq(context)].set_index('axis_mode')
        guidance.append([short(context), int(grouped.silhouette.idxmax()), int(grouped.db.idxmin()),
            'n/d' if pd.isna(choices.loc['raw', 'suggested_k']) else int(choices.loc['raw', 'suggested_k']),
            'n/d' if pd.isna(choices.loc['sse_relative', 'suggested_k']) else int(choices.loc['sse_relative', 'suggested_k']),
            'n/d' if pd.isna(choices.loc['unit_axes', 'suggested_k']) else int(choices.loc['unit_axes', 'suggested_k']),
            fmt(grouped.stability.min()), fmt(grouped.stability.max())])
    km_main = main[main.algorithm.eq('kmeans')]
    unstable = float(main_stability.ari_including_noise.min())
    drift = float(main_stability.max_centroid_coordinate_change_pp.max())
    concentration = float(km_main.top_one_percent_sse_share.max())
    medoid_justified = unstable < .90 or drift > 5 or concentration > .10
    lines = [
        '# Primer piloto exploratorio de clustering territorial · 2024', '',
        '## Alcance y resultado', '',
        f'Se ejecutaron **{number(len(metrics))} ajustes** en **{number(len(coverage))} contextos**: '
        'Amplios y Etapas; tasas originales, StandardScaler y RobustScaler; Ward, K-Means y DBSCAN. '
        'Se añadió sensibilidad NS<10 % por coordenada y, para Etapas, 75+ frente a 75–100. '
        'Son agrupaciones municipales experimentales: no se selecciona un modelo final, no se '
        'asignan nombres a perfiles ciudadanos y no se infieren características individuales.', '',
        'Los resultados destacados abajo son máximos de Silhouette **dentro de cada contexto y algoritmo**, '
        'no una selección final. Para DBSCAN se mide sobre municipios no ruido; no comparar ese máximo '
        'sin considerar cuántos municipios y cuánto LN quedan como ruido. Las métricas de geometrías '
        'y poblaciones distintas no forman un ranking universal.', '',
        table(['Contexto principal', 'Algoritmo', 'Parámetros del máximo interno', 'Grupos', 'n entrenamiento',
               'Silhouette', 'Davies–Bouldin', 'Estabilidad', '% ruido'], best_rows), '',
        'La estabilidad de K-Means es ARI medio entre semillas al mismo K; la de DBSCAN compara '
        'eps adyacentes con el mismo min_samples e incluye ruido. No son el mismo experimento. '
        'Ward es determinista con el orden documentado, pero no se ha hecho remuestreo: su '
        'estabilidad figura n/d. La tabla completa de todos los ajustes está en '
        '`metadata/model_comparison.csv`.', '',
        '## Poblaciones, soporte y pendientes', '',
        'Sólo se seleccionaron las seis/diez tasas declaradas en el contrato C de 2024. '
        'El experimento principal requiere tasas completas y ninguna coordenada con LN<100, '
        'SV+NV<100 o filas fuente<5. Cada municipio pesa uno; LN se usa exclusivamente para '
        'informar cobertura. NS elevado no impide entrar en el principal y se estudia aparte. '
        'Los umbrales son exploratorios, no reglas definitivas de limpieza.', '',
        table(['Representación', 'Escenario', 'Municipios entrenamiento', 'Pendientes', 'LN entrenamiento', '% LN total'],
              [[r.representation, r.scenario, number(r.training_municipalities), number(r.pending_municipalities),
                number(r.training_LN), pct(r.training_LN_share)] for r in coverage[coverage.scaling.eq('original')].itertuples()]), '',
        'Cada contexto conserva los 2,477 municipios en metadata.parquet y labels.parquet. '
        'Los no incluidos mantienen etiquetas NULL y razón en pending_assignment.parquet; '
        'no se les asigna por proximidad, no se imputa participación y no se confunden con '
        'ruido DBSCAN. El ruido recibe -1 sólo dentro del entrenamiento. Se conservan claves '
        'territoriales de texto, LN/SV/NV/NS, denominadores y referencias cartográficas.', '',
        '## Implementación, escalas y reproducibilidad', '',
        'El entorno no contiene SciPy, scikit-learn ni threadpoolctl. Para respetar la restricción '
        'de no instalar dependencias adicionales, `clustering_core.py` implementa con NumPy '
        'los algoritmos y métricas. No se afirma identidad bit a bit con las librerías: '
        'k-means++ es el muestreo clásico proporcional a distancia cuadrática, no su variante '
        'voraz con ensayos locales. Se fijan orden de filas, semillas y un hilo BLAS. '
        'Esta implementación propia es una limitación que debe contrastarse con una librería '
        'independiente antes de usar el piloto como base definitiva.', '',
        'StandardScaler usa (x−media)/DE con ddof=0; RobustScaler usa (x−mediana)/(Q3−Q1), '
        'cuartiles lineales 25–75 y sin unit_variance. Una escala nula se sustituye por uno '
        'en el transformador, no en los datos fuente. Se ajustan únicamente sobre los '
        'municipios del principal; parámetros y columnas se guardan en scaler.json. '
        '[StandardScaler](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html), '
        '[RobustScaler](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.RobustScaler.html).', '',
        'NS y 75+ reutilizan el escalador y la cuadrícula DBSCAN del principal correspondiente '
        'para controlar cambios de escala y parámetros. Las transformaciones sólo se escriben '
        'en training_matrix.parquet del nuevo piloto. No se modifican matrices candidatas. '
        'Las correlaciones elevadas entre tasas siguen presentes: escalar no descorrelaciona '
        'ni elimina la ponderación implícita de dimensiones redundantes. No se aplicó PCA.', '',
        '## Ward y comparación con K-Means', '',
        'Ward utiliza distancia euclídea y actualización de varianza de Lance–Williams, con '
        'cadena de vecinos recíprocos. Se conserva el árbol completo y se corta en K=2…10. '
        'Las pruebas contrastan sus fusiones/alturas con una búsqueda exhaustiva independiente '
        'del mínimo incremento de SSE en datos sintéticos. Los empates se resuelven por '
        'orden estable; pueden existir árboles equivalentes ante distancias iguales. '
        '[Definición de Ward](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html).', '',
        'Cada contexto principal tiene un dendrograma PNG con los últimos 30 subárboles, '
        'un SVG completo ampliable, ward_linkage.parquet, ward_leaf_order.csv y una comparación '
        'de cortes. Las hojas contraídas indican n; los colores y números sólo identifican '
        'clusters locales.', '',
        table(['Contexto', 'ARI Ward/K-Means mínimo', 'Mediana', 'Máximo'],
              [[short(context), fmt(frame.ari_including_noise.min()), fmt(frame.ari_including_noise.median()),
                fmt(frame.ari_including_noise.max())] for context, frame in
               ward_comparison[ward_comparison.context_id.str.endswith('_main')].groupby('context_id', sort=True)]), '',
        '## K-Means, K experimental y método del codo', '',
        'Se probaron K=2…10, semillas 17/42/2024 y diez inicializaciones k-means++ por semilla. '
        'Lloyd se detiene cuando las asignaciones son estables, con máximo 300 iteraciones. '
        'Se guarda cada inicialización y se conserva la menor SSE de las diez; no se supone '
        'haber encontrado el óptimo global. La curva del codo usa la menor SSE entre las '
        'tres semillas para cada K. La SSE no es comparable directamente entre escalamientos, '
        'dimensiones o tamaños de población.', '',
        table(['Contexto', 'K máximo Silhouette medio', 'K mínimo DB medio', 'K geométrico SSE original',
               'K geométrico SSE relativa', 'K geométrico ejes 0–1', 'ARI semillas mínimo por K', 'Máximo'], guidance), '',
        'El codo tradicional se presenta como inspección visual, sin asignarle una regla '
        'numérica universal. Las curvas son decrecientes o se documenta su incumplimiento; '
        'no se corrige SSE para forzar monotonicidad. Los máximos de Silhouette, mínimos '
        'Davies–Bouldin y candidatos geométricos pueden discrepar; los K altos o bajos en '
        'los bordes de la cuadrícula son límites de exploración, no evidencia de optimalidad.', '',
        'Se verificó el original arXiv:2502.00851v2, Teorema 2.5, ecuación (4). Con pendientes '
        'a=SSE(k)−SSE(k−1), b=SSE(k+1)−SSE(k), se minimiza (a−b)/(1+ab) sólo si b>a. '
        'En K=2…10 únicamente k=3…9 tiene ambos vecinos. Se aplica a SSE original; los '
        'controles SSE/SSE(2) y ejes 0–1 son sensibilidades explícitas de escala, no '
        'recomendaciones del artículo. En ejes 0–1 las pendientes incluyen ΔK. '
        '[Documento original](https://arxiv.org/html/2502.00851v2).', '',
        'La ecuación geométrica depende de las unidades de los ejes y de la ventana de K. '
        'No certifica el número verdadero de grupos. Se usó la definición SSE del texto; '
        'el pseudocódigo simplifica sumatorias y no sustituye esa definición. El artículo '
        'presupone ausencia de outliers al introducir el método; ese supuesto no se considera '
        'demostrado en ParticipaMX.', '',
        image('seed_stability.png', 'Estabilidad entre semillas'), '',
        table(['Contexto principal', 'ARI mínimo entre semillas', 'Mediana ARI', 'Mayor cambio de coordenada de centroide (pp)'],
              [[short(context), fmt(frame.ari_including_noise.min()), fmt(frame.ari_including_noise.median()),
                f'{frame.max_centroid_coordinate_change_pp.max():.3f}'] for context, frame in main_stability.groupby('context_id', sort=True)]), '',
        'Los centroides se alinean mediante asignación mínima exacta y se expresan también '
        'en tasas originales. ARI ignora permutaciones de etiquetas. El porcentaje de cambios '
        'de asignación usa la mejor permutación por solapamiento, hasta diez etiquetas; '
        'con más etiquetas figura n/d, conservando ARI. No se compara directamente el '
        'número de etiqueta entre ejecuciones.', '',
        '## DBSCAN y significado del ruido', '',
        'Se exploraron min_samples=max(5,p+1) y el doble: 7/14 para Amplios, 11/22 para '
        'Etapas. La distancia al vecino min_samples incluye el propio punto. eps usa '
        'cuantiles 50/75/90/95 de esas distancias en el entrenamiento principal; cubre '
        'densidades diferentes sin forzar un número de clusters. Las curvas k-distance '
        'y todos los valores numéricos se guardan.', '',
        table(['Contexto principal', 'Grupos mínimo–máximo', '% ruido mínimo–máximo', '% LN entrenamiento ruido mínimo–máximo',
               'Ajustes con métricas sin ruido definidas'],
              [[short(context), f'{frame.clusters.min()}–{frame.clusters.max()}',
                f'{pct(frame.noise_fraction.min())} – {pct(frame.noise_fraction.max())}',
                f'{pct(frame.noise_LN_fraction.min())} – {pct(frame.noise_LN_fraction.max())}',
                f'{frame.silhouette.notna().sum()}/{len(frame)}'] for context, frame in main[main.algorithm.eq('dbscan')].groupby('context_id', sort=True)]), '',
        'DBSCAN asigna bordes alcanzables en orden estable. Ruido significa no pertenecer '
        'a una región densa con esos parámetros; no implica datos incorrectos. Se informa '
        'ruido como porcentaje de entrenamiento y LN de entrenamiento, además de su '
        'porcentaje sobre LN municipal total. '
        '[Definición de DBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html).', '',
        'Silhouette y Davies–Bouldin principales de DBSCAN excluyen ruido y requieren al '
        'menos dos grupos y menos grupos que observaciones evaluadas. También se guardan '
        'métricas incluyendo -1 como etiqueta adicional; esa etiqueta no debe interpretarse '
        'como cluster coherente. Las causas de n/d quedan explícitas. ARI de parámetros '
        'y sensibilidades se guarda con ruido y sobre la intersección no ruido, informando '
        'su n. Un ARI=1 entre dos soluciones enteramente ruido se marca trivial y no '
        'se usa como evidencia de estabilidad. '
        '[Silhouette](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html), '
        '[Davies–Bouldin](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.davies_bouldin_score.html), '
        '[ARI](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.adjusted_rand_score.html).', '',
        '## Sensibilidad de edades extremas y NS', '',
        'El principal usa 18–100. La alternativa de Etapas 75+ se reconstruye desde el '
        'escenario B ya evaluado, conservando H/M y los mismos 1,897 municipios principales. '
        'Las primeras ocho coordenadas no cambian; las últimas dos incorporan >100. '
        'Se mantienen escalador, K, semillas, eps y min_samples. Semillas idénticas no '
        'garantizan los mismos centros iniciales: k-means++ depende de las distancias '
        'que cambian. El contraste se contextualiza con la variación entre semillas.', '',
        table(['Población de tasas 75', 'Coordenadas con tasa definida', 'Mediana diferencia (pp)', 'Máx. diferencia absoluta (pp)'],
              [[name, number(frame.difference_pp.notna().sum()), f'{frame.difference_pp.median():.5f}',
                f'{frame.difference_pp.abs().max():.5f}'] for name, frame in
               [('Todos los municipios', tail_rates), ('Entrenamiento compartido', tail_rates[tail_rates.in_main])]]), '',
        image('tail_rate_changes.png', 'Cambios de tasas al incorporar edades extremas'), '',
        'NS<10 % por coordenada reduce la población; reutiliza escalas y parámetros '
        'para aislar el cambio de cobertura, aunque cambiar la población modifica densidades '
        'y centroides. El contraste de asignaciones se hace exclusivamente en municipios '
        'compartidos, sin asignar los excluidos de esta sensibilidad. Los conjuntos completos '
        'permanecen disponibles y el umbral no se adopta como regla definitiva.', '',
        table(['Comparación', 'Algoritmo', 'Ajustes comparados', 'n compartido mínimo–máximo', 'ARI con ruido mediana', 'Mínimo', 'ARI no ruido mediana'],
              [[name, algorithm, len(frame), f'{frame.common_observations.min()}–{frame.common_observations.max()}',
                fmt(frame.ari_including_noise.median()), fmt(frame.ari_including_noise.min()),
                fmt(frame.ari_common_nonnoise.median())] for (name, algorithm), frame in sensitivity.groupby(['comparison', 'algorithm'], sort=True)]), '',
        image('sensitivity_ari.png', 'Sensibilidad de asignaciones'), '',
        'Las métricas completas antes/después se conservan en model_comparison.csv; '
        'sensitivity_comparisons.csv alinea cada modelo por parámetros y semillas. '
        'No se interpreta una pequeña variación de tasas como garantía de etiquetas '
        'idénticas cerca de fronteras de agrupación.', '',
        '## Nivel general frente a diferencias de edad y sexo', '',
        'En tasas originales se descompone la separación entre centroides en dos partes '
        'ortogonales: nivel (media simple de las 6/10 coordenadas de cada municipio) y '
        'forma (perfil menos esa media). La media de coordenadas no es la participación '
        'municipal agregada y no pondera edades por población. Las dos sumas de cuadrados '
        'reconcilian exactamente; se guarda la fracción de separación y la variación '
        'explicada de cada componente, sin modificar la matriz del modelo.', '',
        table(['Contexto', 'Algoritmo', 'Separación por nivel mediana', 'Separación por forma mediana', 'Forma mínimo–máximo'],
              [[short(context), algorithm, pct(frame.between_level_share.median()),
                pct(frame.between_shape_share.median()),
                f'{pct(frame.between_shape_share.min())} – {pct(frame.between_shape_share.max())}']
               for (context, algorithm), frame in main[main.algorithm.ne('dbscan')].groupby(['context_id', 'algorithm'], sort=True)]), '',
        image('level_shape_separation.png', 'Separación por nivel y forma demográfica'), '',
        'Una fracción predominante de nivel indica que gran parte de la separación refleja '
        'participación generalmente alta o baja entre coordenadas; la fracción de forma '
        'cuantifica diferencias relativas de edad/sexo adicionales. No se afirma que la '
        'presencia de forma pruebe perfiles ciudadanos individuales ni causalidad. '
        'Centroids.csv permite revisar cada tasa y el tamaño de los grupos sin asignar nombres.', '',
        '## Escalas y representaciones: estabilidad adicional', '',
        table(['Comparación', 'Algoritmo', 'ARI mediana', 'Mínimo', 'Máximo', 'n común mínimo'],
              [[name, algorithm, fmt(frame.ari_including_noise.median()), fmt(frame.ari_including_noise.min()),
                fmt(frame.ari_including_noise.max()), number(frame.common_observations.min())]
               for data, name in [(scaling_comparisons, 'Escalamientos'), (representation_comparisons, 'Amplios/Etapas')]
               for algorithm, frame in data.groupby('algorithm', sort=True)]), '',
        'Se comparan métodos sobre las mismas observaciones y, entre representaciones, '
        'sólo la intersección territorial. Escalar altera la geometría; ampliar intervalos '
        'cambia resolución y soporte. No hay una equivalencia automática de números '
        'de clusters o etiquetas entre esas decisiones.', '',
        '## Decisión provisional sobre K-Medoids', '',
        f'El ARI mínimo entre semillas principales fue {unstable:.4f}; el mayor cambio de '
        f'una coordenada de centroide alineado fue {drift:.3f} pp. La mayor fracción de SSE '
        f'concentrada en el 1 % de municipios de mayor error fue {pct(concentration)}. '
        'Se guardan también la cantidad de municipios fuera de IQR en alguna coordenada '
        'y su participación en SSE; IQR no demuestra error y no se excluyeron esos casos.', '',
        ('**Sí se justifica comparar K-Medoids en una siguiente iteración** como sensibilidad a '
         'estabilidad o influencia de extremos, sin anticipar que mejore las métricas.' if medoid_justified else
         '**K-Medoids no es prioritario con estas señales del piloto**, aunque puede aportar '
         'una comparación posterior con representantes observados. No hay evidencia aquí '
         'de que necesariamente mejore el resultado.'), '',
        'Se usaron como alertas operativas ARI<0.90, desplazamiento de coordenada >5 pp '
        'o más del 10 % de SSE en el 1 % de mayores errores; no son umbrales oficiales '
        'ni una evaluación ejecutada de K-Medoids. No se instaló ni ejecutó.', '',
        '## Entregables, verificaciones y límites', '',
        f'Datos: `{output.relative_to(root).as_posix()}`. Cada contexto conserva tasas crudas, '
        'matriz transformada de entrenamiento, metadatos de todos los municipios, pendientes, '
        'parámetros de escalamiento, etiquetas experimentales, árbol Ward, SSE, métricas, '
        'inicializaciones, centroides, tamaños y comparaciones. metadata/ reúne configuración, '
        'cobertura, sensibilidad, estabilidad y manifiesto. Las figuras principales tienen '
        'sus datos numéricos en el contexto correspondiente.', '',
        f'Se verificaron hashes de {number(protected_count)} archivos existentes antes y después; '
        'ningún ZIP, Parquet previo, informe anterior o src/ fue modificado. No se reprocesaron '
        'los 54 millones de registros. La referencia exacta y SEXO=2 permanecen en los '
        'datos de referencia: el piloto C no inventa coordenadas históricas o municipales '
        'de una categoría escasa. No se crearon commits.', '',
        'Las comprobaciones incluyen fórmulas de escaladores e inversión, Ward contra '
        'fusiones exhaustivas, K-Means contra soluciones conocidas y semillas repetidas, '
        'DBSCAN con núcleos/bordes/ruido, métricas calculadas a mano, ARI invariante '
        'a etiquetas, emparejamiento de centroides y fórmula geométrica con casos '
        'degenerados. El proceso valida convergencia de los mejores K-Means, K encontrado, '
        'rangos de métricas, conservación de observaciones pendientes y escritura/relectura '
        'Parquet. `_SUCCESS` sólo aparece al validar la ejecución.', '',
        'Reproducir:', '', '```powershell',
        '.venv/Scripts/python.exe analysis/scripts/run_clustering_pilot.py',
        '.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_clustering_pilot.py -v',
        '```', '',
        'Para repetir sin sobrescribir, elegir nuevos --output, --charts y --report. '
        'Semillas, versiones, límite de hilos, parámetros y hashes de código se registran. '
        'No hay una evaluación de generalización, validación externa o comparación '
        'independiente con implementaciones de librería; falta revisar estabilidad por '
        'remuestreo, límites de K, efectos de NS, significado de la distancia y '
        'cartografía antes de elegir un modelo final. Los resultados son exploratorios.', '',
    ]
    # Ejemplos representativos de los seis contextos; las demás imágenes quedan junto a ellos.
    insertion = lines.index('## K-Means, K experimental y método del codo')
    examples = []
    for context in ['c_broad_original_main', 'c_life_stage_standard_main']:
        examples += [image(context+'/ward_dendrogram.png', context+' Ward'), '',
                     image(context+'/kmeans_elbow.png', context+' codo'), '',
                     image(context+'/validation_by_k.png', context+' métricas'), '',
                     image(context+'/dbscan_k_distance.png', context+' k-distance'), '',
                     image(context+'/dbscan_results.png', context+' DBSCAN'), '']
    lines[insertion:insertion] = examples
    report.write_text('\n'.join(lines), encoding='utf-8')


def run_pilot(root, output, charts, report):
    root, output, charts, report = map(lambda value: Path(value).resolve(), [root, output, charts, report])
    require(output.is_relative_to(root/'data/processed') and charts.is_relative_to(root/'analysis/charts')
            and report.is_relative_to(root/'analysis/reports'), 'Destinos no permitidos.')
    require(not output.exists() and not charts.exists() and not report.exists(), 'No se sobrescriben resultados; elegir rutas nuevas.')
    protected = snapshot_inputs(root, output, charts)
    source = root/'data/processed/cluster_features'
    prior = json.loads((source/'metadata/run_manifest.json').read_text(encoding='utf-8'))
    require(prior['status'] == 'validated' and json.loads((source/'_SUCCESS').read_text())['manifest_sha256'] == file_hash(source/'metadata/run_manifest.json'), 'Matrices no validadas.')
    for relative, digest in prior['artifact_hashes'].items(): require(file_hash(root/relative) == digest, f'Matriz previa alterada: {relative}')
    contract = json.loads((source/'metadata/feature_contract.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True); charts.mkdir(parents=True); (output/'metadata').mkdir()
    started = time.monotonic()
    configuration = dict(election_year=2024, representations=['c_broad', 'c_life_stage'], scalings=SCALINGS,
        algorithms=['ward_euclidean', 'kmeans_plusplus_lloyd', 'dbscan_euclidean'], ks=KS, seeds=SEEDS,
        n_init=N_INIT, max_iter=MAX_ITER, eps_quantiles=EPS_QUANTILES,
        min_samples_rule='max(5,p+1) y dos veces ese valor; incluye el propio punto',
        main_rule='complete rates and no low-support coordinate', ns_rule='main and NS/LN<0.10 in every coordinate',
        equal_municipality_weights=True, tail_policy='same life_stage main municipalities, scaler, seeds, K and DBSCAN eps/min_samples',
        ns_policy='subset; reuse main scaler and DBSCAN eps/min_samples to control transformations',
        backend='NumPy; no scipy, sklearn, threadpoolctl or K-Medoids installed', paper_url=PAPER_URL,
        paper_method='Theorem 2.5 equation (4), original arXiv v2 verified before implementation; interior K=3..9 only')
    save_json(output/'metadata/experiment_config.json', configuration)
    manifest = dict(status='running', errors=[], configuration=configuration, protected_hashes=protected,
        started_at_utc=datetime.now(timezone.utc).isoformat(),
        versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__,
                      pyarrow=pa.__version__, matplotlib=matplotlib.__version__),
        thread_limits={name: os.environ.get(name) for name in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS']})
    save_json(output/'metadata/run_manifest.json', manifest)
    try:
        inputs, contexts, sensitivity, tail_rates = {}, {}, [], []
        for representation in configuration['representations']:
            features = pd.read_parquet(source/f'matrices/{representation}/features.parquet')
            metadata = pd.read_parquet(source/f'matrices/{representation}/metadata.parquet')
            require(features.row_id.equals(metadata.row_id), 'Matriz y metadatos desalineados.')
            names = contract['matrices'][representation]['feature_columns']
            require(features.columns.tolist() == ['row_id', *names], 'Se usarían variables fuera del contrato.')
            inputs[representation] = (features, metadata, names)
            for scaling in SCALINGS:
                context_id = f'{representation}_{scaling}_main'
                contexts[context_id] = run_context(context_id, representation, 'main', scaling, features, metadata,
                    names, eligibility(metadata), output, charts)
                print(f'{context_id}: completado; {len(contexts[context_id]["metrics"])} ajustes.', flush=True)
                filtered_id = f'{representation}_{scaling}_ns_lt_10'
                baseline = contexts[context_id]
                contexts[filtered_id] = run_context(filtered_id, representation, 'ns_lt_10', scaling, features, metadata,
                    names, eligibility(metadata, True), output, charts, scaler=baseline['scaler'], eps_parameters=baseline['eps_parameters'])
                sensitivity.extend(cross_context_comparisons(baseline, contexts[filtered_id], 'ns_threshold_same_scale_and_grid'))
                print(f'{filtered_id}: completado.', flush=True)
        closed, metadata, names = inputs['c_life_stage']
        opened, opened_metadata, opened_names = build_open_tail(root, closed, metadata, names)
        deltas = opened[opened_names].to_numpy()-closed[names].to_numpy()
        for index, name in enumerate(opened_names):
            for i in range(len(metadata)):
                if index >= 8:
                    tail_rates.append(dict(row_id=metadata.row_id.iloc[i], EDOCVE=metadata.EDOCVE.iloc[i], MPIOCVE=metadata.MPIOCVE.iloc[i],
                        feature=name, original_75_100=float(closed[names[index]].iloc[i]), alternative_75_plus=float(opened[name].iloc[i]),
                        difference_pp=float(100*deltas[i, index]), in_main=bool(eligibility(metadata)[i])))
        save_table(output/'metadata/tail_rate_changes.parquet', pd.DataFrame(tail_rates))
        for scaling in SCALINGS:
            baseline = contexts[f'c_life_stage_{scaling}_main']
            context_id = f'c_life_stage_{scaling}_tail_75plus'
            contexts[context_id] = run_context(context_id, 'c_life_stage', 'tail_75plus', scaling, opened, opened_metadata,
                opened_names, eligibility(metadata), output, charts, scaler=baseline['scaler'], eps_parameters=baseline['eps_parameters'])
            sensitivity.extend(cross_context_comparisons(baseline, contexts[context_id], 'over_100_same_municipalities_and_parameters'))
            print(f'{context_id}: completado.', flush=True)
        scaling_comparisons = []
        for representation in configuration['representations']:
            for first, second in combinations(SCALINGS, 2):
                a, b = contexts[f'{representation}_{first}_main'], contexts[f'{representation}_{second}_main']
                rows = cross_context_comparisons(a, b, 'scaling_same_municipalities')
                scaling_comparisons.extend(row for row in rows if row['algorithm'] != 'dbscan')
        representation_comparisons = []
        # Los row_id tienen prefijos distintos por representación: alinea las claves territoriales.
        for scaling in SCALINGS:
            a, b = contexts[f'c_broad_{scaling}_main'], contexts[f'c_life_stage_{scaling}_main']
            keys = ['election_year', 'EDOCVE', 'MPIOCVE']
            left_index = pd.MultiIndex.from_frame(inputs['c_broad'][1][keys])
            right_index = pd.MultiIndex.from_frame(inputs['c_life_stage'][1][keys])
            reindex = right_index.get_indexer(left_index)
            require((reindex >= 0).all(), 'Universos municipales distintos en representaciones.')
            b_aligned = dict(b, labels={model: values[reindex] for model, values in b['labels'].items()})
            rows = cross_context_comparisons(a, b_aligned, 'representation_common_municipalities')
            representation_comparisons.extend(row for row in rows if row['algorithm'] != 'dbscan')
        metrics = pd.concat([context['metrics'] for context in contexts.values()], ignore_index=True)
        coverage = pd.DataFrame([context['coverage'] for context in contexts.values()])
        seed_stability = pd.concat([context['stability'] for context in contexts.values()], ignore_index=True)
        ward_comparison = pd.concat([context['comparisons'] for context in contexts.values()], ignore_index=True)
        elbows = pd.DataFrame([row for context in contexts.values() for row in context['elbow_choices']])
        sensitivity_frame = pd.DataFrame(sensitivity)
        for name, frame in [('model_comparison.csv', metrics), ('coverage.csv', coverage),
            ('seed_stability.csv', seed_stability), ('ward_kmeans_ari.csv', ward_comparison),
            ('elbow_candidates.csv', elbows), ('sensitivity_comparisons.csv', sensitivity_frame),
            ('scaling_comparisons.csv', pd.DataFrame(scaling_comparisons)),
            ('representation_comparisons.csv', pd.DataFrame(representation_comparisons))]:
            save_table(output/'metadata'/name, frame)
        require(metrics[metrics.algorithm.ne('dbscan')].clusters.eq(metrics[metrics.algorithm.ne('dbscan')].k).all(), 'K solicitado y encontrado no coinciden.')
        require(metrics.loc[metrics.algorithm.eq('kmeans'), 'converged'].all(), 'Algún mejor ajuste K-Means no convergió.')
        require(metrics.silhouette.dropna().between(-1, 1).all() and metrics.davies_bouldin.dropna().ge(0).all(), 'Métrica fuera de dominio.')
        plot_summary(charts, metrics, seed_stability, sensitivity_frame, pd.DataFrame(tail_rates))
        write_report(root, output, charts, report, metrics, coverage, seed_stability, ward_comparison,
            elbows, sensitivity_frame, pd.DataFrame(scaling_comparisons), pd.DataFrame(representation_comparisons),
            pd.DataFrame(tail_rates), len(protected))
        for path, digest in protected.items(): require(file_hash(path) == digest, f'Archivo protegido modificado: {path}')
        manifest.update(status='validated', seconds=round(time.monotonic()-started, 2),
            finished_at_utc=datetime.now(timezone.utc).isoformat(), contexts=len(contexts), fitted_models=len(metrics),
            protected_files=len(protected), script_hashes={name: file_hash(root/'analysis/scripts'/name)
                for name in ['run_clustering_pilot.py', 'clustering_core.py']}, report_sha256=file_hash(report),
            artifact_hashes={str(path.relative_to(root)): file_hash(path) for directory in [output, charts]
                for path in directory.rglob('*') if path.is_file() and path != output/'metadata/run_manifest.json'})
        save_json(output/'metadata/run_manifest.json', manifest)
        save_json(output/'_SUCCESS', dict(manifest_sha256=file_hash(output/'metadata/run_manifest.json')))
        print(f'VALIDADO: {len(metrics)} ajustes en {len(contexts)} contextos; informe: {report.relative_to(root)}', flush=True)
        return manifest
    except Exception as error:
        manifest['status'] = 'failed'
        manifest['errors'].append(dict(type=type(error).__name__, message=str(error)))
        save_json(output/'metadata/run_manifest.json', manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, default=Path('data/processed/clustering_pilot'))
    parser.add_argument('--charts', type=Path, default=Path('analysis/charts/clustering_pilot'))
    parser.add_argument('--report', type=Path, default=Path('analysis/reports/clustering_pilot.md'))
    args = parser.parse_args()
    root = args.root.resolve()
    destinations = [path if path.is_absolute() else root/path for path in [args.output, args.charts, args.report]]
    run_pilot(root, *destinations)


if __name__ == '__main__':
    main()
