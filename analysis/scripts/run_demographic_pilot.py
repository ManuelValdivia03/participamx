"""Piloto B de 2024: K-Means conjunto y estratificado, con trazabilidad completa.

Sólo escribe derivados nuevos. Los datos incompletos, escasos, 101+ y SEXO=2
permanecen en metadatos y etiquetas nullable. No aplica filtros a las fuentes.
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
import pyarrow as pa

from clean_data import file_hash, require, save_json
from build_cluster_features import save_table, snapshot_inputs
from build_descriptive import METRICS, number, pct, markdown_table
from clustering_core import (adjusted_rand, centroid_matching, fit_scaler, geometric_elbow,
    kmeans, pairwise_distances, transform)
from run_clustering_pilot import label_change_fraction

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

FEATURES = ['participation_observed', 'mean_age_nominal']
KEYS = ['election_year', 'EDOCVE', 'MPIOCVE', 'age_band', 'SEXO']
MUNICIPAL_KEYS = ['EDOCVE', 'MPIOCVE']
SCHEMES = ['life_stage', 'broad']
SCALINGS = ['original', 'standard']
SCOPES = {'joint': None, 'men': '0', 'women': '1'}
KS = list(range(2, 11))
SEEDS = [17, 42, 2024]
SEX_LABELS = {'0': 'Hombres', '1': 'Mujeres', '2': 'No binario'}


def add_reference(metadata):
    """La referencia nacional incluye todas las filas, antes de seleccionar soporte."""
    reference = metadata.groupby(['age_band', 'SEXO'], as_index=False, observed=True)[METRICS].sum()
    reference['specified_count'] = reference.SV+reference.NV
    reference['national_participation'] = reference.SV/reference.specified_count.replace(0, np.nan)
    reference['national_unspecified_rate'] = reference.NS/reference.LN.replace(0, np.nan)
    result = metadata.merge(reference[['age_band', 'SEXO', 'national_participation']],
        on=['age_band', 'SEXO'], how='left', validate='many_to_one', sort=False)
    require(result.row_id.tolist() == metadata.row_id.tolist(), 'Se alteró el orden al unir la referencia.')
    result['participation_deviation_national'] = result.participation_observed-result.national_participation
    return result, reference


def selection(metadata, scope='joint', include_tail=False):
    """Separa alcance, completitud y soporte; NS alto se conserva en entrenamiento."""
    raw = metadata[FEATURES].to_numpy(dtype=float)
    finite = np.isfinite(raw).all(axis=1)
    support = (metadata.LN.ge(100) & metadata.specified_count.ge(100) & metadata.source_row_count.ge(5)).to_numpy()
    scope_mask = np.ones(len(metadata), dtype=bool) if SCOPES[scope] is None else metadata.SEXO.eq(SCOPES[scope]).to_numpy()
    age_mask = np.ones(len(metadata), dtype=bool) if include_tail else metadata.age_max_observed.le(100).to_numpy()
    require(metadata.age_min_observed.ge(18).all(), 'Aparecieron edades fuera del alcance auditado.')
    mask = finite & support & scope_mask & age_mask
    result = metadata.copy()
    result['in_sex_scope'] = scope_mask
    result['in_age_scope'] = age_mask
    result['has_complete_features'] = finite
    result['has_sufficient_support'] = support
    result['is_training'] = mask
    result['pending_reason'] = np.select([~scope_mask, ~age_mask, ~finite, ~support],
        ['outside_sex_stratum', 'age_101_plus_complementary', 'undefined_features', 'low_support'], default='in_training')
    return mask, result


def anchor_sample(row_ids, maximum=1200, seed=319):
    """Muestra uniforme reproducible sin reemplazo; idéntica entre escalas/semillas."""
    require(maximum >= 2, 'Se requieren al menos dos anclas.')
    # El orden de entrada está fijado por row_id y contrastado con el contrato.
    return np.sort(np.random.default_rng(seed).choice(len(row_ids), size=min(maximum, len(row_ids)), replace=False))


def anchor_distances(values, anchors, block_size=128):
    """Rectángulo m×n, nunca n×n para B; diferencias directas evitan cancelación."""
    require(block_size > 0, 'El bloque de distancias debe ser positivo.')
    result = np.empty((len(anchors), len(values)), dtype=float)
    for start in range(0, len(anchors), block_size):
        index = anchors[start:start+block_size]
        squared = np.zeros((len(index), len(values)))
        for column in range(values.shape[1]):
            squared += (values[index, column, None]-values[None, :, column])**2
        result[start:start+len(index)] = np.sqrt(squared)
    return result


def sampled_metrics(values, labels, anchors, distances):
    """Silhouette de anclas contra TODOS los puntos; DB exacto del entrenamiento."""
    labels = np.asarray(labels)
    groups, encoded = np.unique(labels, return_inverse=True)
    n, k = len(labels), len(groups)
    require(2 <= k < n, 'Métricas requieren de 2 a n−1 grupos.')
    counts = np.bincount(encoded)
    means = np.column_stack([distances[:, encoded == group].sum(axis=1)/counts[group] for group in range(k)])
    own_group = encoded[anchors]
    own = means[np.arange(len(anchors)), own_group]*counts[own_group]/np.maximum(1, counts[own_group]-1)
    means[np.arange(len(anchors)), own_group] = np.inf
    other = means.min(axis=1)
    denominator = np.maximum(own, other)
    scores = np.divide(other-own, denominator, out=np.zeros(len(anchors)), where=denominator > 0)
    scores[counts[own_group] == 1] = 0.
    centers = np.array([values[encoded == group].mean(axis=0) for group in range(k)])
    scatter = np.array([np.linalg.norm(values[encoded == group]-centers[group], axis=1).mean() for group in range(k)])
    center_distances = pairwise_distances(centers)  # Sólo K×K, K<=10.
    require((center_distances[~np.eye(k, dtype=bool)] > 1e-14).all(), 'Centroides coincidentes; DB indefinido.')
    np.fill_diagonal(center_distances, np.inf)
    db = ((scatter[:, None]+scatter[None, :])/center_distances).max(axis=1).mean()
    error = scores.std(ddof=1)/np.sqrt(len(anchors))*np.sqrt((n-len(anchors))/n) if len(anchors) < n else 0.
    return dict(silhouette=float(scores.mean()), silhouette_mc_se=float(error), davies_bouldin=float(db),
        silhouette_evaluation_n=len(anchors), silhouette_reference_n=n,
        silhouette_method='all_points_exact' if len(anchors) == n else 'uniform_anchors_all_reference_points')


def group_sse(values, codes):
    values, codes = np.asarray(values, dtype=float), np.asarray(codes, dtype=int)
    counts = np.bincount(codes)
    sums = np.bincount(codes, weights=values)
    return max(0., float(np.dot(values, values)-np.sum(sums[counts > 0]**2/counts[counts > 0])))


def pattern_diagnostics(raw, metadata, labels, centers_scaled, scaled):
    """Distingue bandas predefinidas de diferencias de tasa dentro de edad/sexo."""
    labels = np.asarray(labels, dtype=int)
    total = ((raw-raw.mean(axis=0))**2).sum(axis=0)
    within = np.zeros(raw.shape[1])
    counts = np.bincount(labels)
    between_scaled = (counts[:, None]*(centers_scaled-scaled.mean(axis=0))**2).sum(axis=0)
    for group in np.unique(labels):
        values = raw[labels == group]
        within += ((values-values.mean(axis=0))**2).sum(axis=0)
    r2 = np.divide(total-within, total, out=np.full(2, np.nan), where=total > 0)
    band_codes = pd.factorize(metadata.age_band, sort=True)[0]
    cell_codes = pd.factorize(pd.MultiIndex.from_frame(metadata[['age_band', 'SEXO']]), sort=True)[0]
    baseline = group_sse(raw[:, 0], cell_codes)
    after = group_sse(raw[:, 0], cell_codes*len(counts)+labels)
    contingency = np.zeros((len(counts), band_codes.max()+1), dtype=int)
    np.add.at(contingency, (labels, band_codes), 1)
    deviations = metadata.participation_deviation_national.to_numpy(dtype=float)
    deviation_total = np.sum((deviations-deviations.mean())**2)
    return dict(participation_r2=float(r2[0]), age_r2=float(r2[1]),
        age_share_between_scaled=float(between_scaled[1]/between_scaled.sum()),
        age_band_purity=float(contingency.max(axis=1).sum()/len(labels)),
        age_band_ari=adjusted_rand(labels, band_codes),
        within_age_sex_rate_r2=float(1-after/baseline) if baseline > 1e-14 else np.nan,
        national_deviation_r2=float(1-group_sse(deviations, labels)/deviation_total) if deviation_total > 1e-14 else np.nan)


def cluster_tables(metadata, labels, k, seed):
    """Conteos y distribuciones para cada ajuste, sin convertir segmentos en personas."""
    frame = metadata.copy()
    frame['cluster'] = labels
    frame['age_nominal_sum'] = frame.mean_age_nominal*frame.LN
    summary = frame.groupby('cluster', as_index=False, observed=True).agg(
        observations=('row_id', 'size'), **{column: (column, 'sum') for column in METRICS},
        specified_count=('specified_count', 'sum'), mean_participation=('participation_observed', 'mean'),
        mean_age=('mean_age_nominal', 'mean'), age_nominal_sum=('age_nominal_sum', 'sum'),
        mean_national_deviation=('participation_deviation_national', 'mean'),
        deviation_q1=('participation_deviation_national', lambda s: s.quantile(.25)),
        deviation_q3=('participation_deviation_national', lambda s: s.quantile(.75)))
    summary['participation_observed'] = summary.SV/summary.specified_count
    summary['unspecified_rate'] = summary.NS/summary.LN
    summary['mean_age_nominal'] = summary.age_nominal_sum/summary.LN
    municipalities = frame.groupby(['cluster', *MUNICIPAL_KEYS], as_index=False, observed=True).agg(
        segments=('row_id', 'size'), LN=('LN', 'sum'), specified_count=('specified_count', 'sum'))
    summary = summary.merge(municipalities.groupby('cluster', as_index=False).agg(
        municipalities=('segments', 'size'), segments_per_municipality_median=('segments', 'median'),
        segments_per_municipality_max=('segments', 'max')), on='cluster', validate='one_to_one')
    distributions = []
    for category in ['age_band', 'SEXO']:
        grouped = frame.groupby(['cluster', category], as_index=False, observed=True).agg(
            observations=('row_id', 'size'), LN=('LN', 'sum'), SV=('SV', 'sum'), NV=('NV', 'sum'), NS=('NS', 'sum'))
        grouped = grouped.rename(columns={category: 'category'})
        grouped['dimension'] = category
        grouped['cluster_fraction'] = grouped.observations/grouped.cluster.map(summary.set_index('cluster').observations)
        distributions.append(grouped)
    distribution = pd.concat(distributions, ignore_index=True)
    for table in [summary, municipalities, distribution]:
        table.insert(0, 'seed', seed); table.insert(0, 'k', k)
    require(summary[METRICS].sum().equals(metadata[METRICS].sum()), 'Perfiles de clusters no concilian conteos.')
    return summary, municipalities, distribution


def weight_review(training, context_id):
    """Ponderaciones descriptivas de la población de entrenamiento, sin ajustar modelos."""
    count = training.groupby(MUNICIPAL_KEYS, observed=True).row_id.transform('size')
    rows = []
    for mode, weights in [('equal_segment', np.ones(len(training))), ('equal_municipality', 1/count.to_numpy()),
                          ('nominal', training.LN.to_numpy(dtype=float))]:
        municipal = training[MUNICIPAL_KEYS].copy(); municipal['weight'] = weights
        municipal = municipal.groupby(MUNICIPAL_KEYS, observed=True).weight.sum().sort_values(ascending=False)
        rows.append(dict(context_id=context_id, weighting=mode,
            equivalent_segment_units=float(weights.sum()**2/np.dot(weights, weights)),
            top_ten_municipality_weight=float(municipal.head(10).sum()/weights.sum()),
            maximum_municipality_weight=float(municipal.max()/weights.sum()),
            mean_participation=float(np.average(training.participation_observed, weights=weights)),
            mean_age=float(np.average(training.mean_age_nominal, weights=weights)),
            mean_national_deviation=float(np.average(training.participation_deviation_national, weights=weights)),
            high_ns_weight=float(weights[training.has_high_unspecified_rate.to_numpy()].sum()/weights.sum())))
    return rows


def run_context(context_id, scheme, scaling, scope, include_tail, metadata, scaler, output,
                anchor_count=1200, n_init=10, max_iter=1000, ks=KS, seeds=SEEDS):
    folder = output/'contexts'/context_id
    folder.mkdir(parents=True)
    mask, full = selection(metadata, scope, include_tail)
    training = full.loc[mask].reset_index(drop=True)
    raw = training[FEATURES].to_numpy(dtype=float)
    values = transform(raw, scaler)
    require(len(training) > max(ks) and np.isfinite(values).all(), 'Población de entrenamiento insuficiente.')
    anchors = anchor_sample(training.row_id, anchor_count)
    distances = anchor_distances(values, anchors)
    save_table(folder/'silhouette_anchors.parquet', training.loc[anchors, ['row_id', *KEYS]])
    save_table(folder/'metadata.parquet', full)
    save_table(folder/'pending_observations.parquet', full.loc[~mask])
    # El escalador sólo se ajusta al entrenamiento conjunto principal de este esquema.
    save_json(folder/'scaler.json', dict(**scaler, fitted_population=f'{scheme}_joint_main',
        feature_columns=FEATURES, reused_for_strata_and_tail=True))
    transformed = pd.DataFrame(transform(full[FEATURES].to_numpy(dtype=float), scaler), columns=FEATURES)
    transformed.insert(0, 'row_id', full.row_id)
    save_table(folder/'features.parquet', transformed)
    labels_frame = full[['row_id', *KEYS]].copy()
    results, labels_by_model, centers_by_model = [], {}, {}
    summaries, municipality_tables, distributions, initializations, stability = [], [], [], [], []
    for k in ks:
        for seed in seeds:
            model_id = f'k{k:02d}_seed{seed}'
            fitted = kmeans(values, k, seed, n_init=n_init, max_iter=max_iter)
            labels = fitted['labels']
            require(len(np.unique(labels)) == k and fitted['converged'], f'Ajuste no convergente: {context_id}/{model_id}')
            measured = float(((values-fitted['centers'][labels])**2).sum())
            require(np.isclose(measured, fitted['inertia']), 'La SSE no coincide con etiquetas y centroides.')
            metrics = sampled_metrics(values, labels, anchors, distances)
            diagnostic = pattern_diagnostics(raw, training, labels, fitted['centers'], values)
            counts = np.bincount(labels, minlength=k)
            results.append(dict(context_id=context_id, scheme=scheme, scaling=scaling, scope=scope,
                scenario='with_101_plus' if include_tail else 'main', k=k, seed=seed, n=len(training),
                sse=fitted['inertia'], iterations=fitted['iterations'], converged=fitted['converged'],
                minimum_cluster=int(counts.min()), maximum_cluster=int(counts.max()),
                minimum_cluster_fraction=float(counts.min()/len(labels)), **metrics, **diagnostic))
            labels_by_model[model_id] = labels
            centers_by_model[model_id] = fitted['centers']
            column = pd.array([pd.NA]*len(full), dtype='Int64'); column[mask] = labels
            labels_frame[model_id] = column
            initializations.extend(dict(context_id=context_id, model_id=model_id, **item) for item in fitted['initializations'])
            summary, municipalities, distribution = cluster_tables(training, labels, k, seed)
            summaries.append(summary); municipality_tables.append(municipalities); distributions.append(distribution)
        for left, right in combinations(seeds, 2):
            a, b = f'k{k:02d}_seed{left}', f'k{k:02d}_seed{right}'
            assignment = centroid_matching(centers_by_model[a], centers_by_model[b])
            raw_a = centers_by_model[a]*np.array(scaler['scale'])+np.array(scaler['location'])
            raw_b = centers_by_model[b][assignment]*np.array(scaler['scale'])+np.array(scaler['location'])
            delta = np.sqrt(np.mean((raw_a-raw_b)**2, axis=0))
            stability.append(dict(context_id=context_id, k=k, left_seed=left, right_seed=right,
                ari=adjusted_rand(labels_by_model[a], labels_by_model[b]),
                changed_fraction=label_change_fraction(labels_by_model[a], labels_by_model[b]),
                matched_centroid_rate_rmse_pp=100*float(delta[0]), matched_centroid_age_rmse=float(delta[1])))
    del distances
    metrics = pd.DataFrame(results)
    elbow_choices, elbow_rows = [], []
    curves = [(f'seed{seed}', metrics[metrics.seed.eq(seed)].set_index('k').loc[ks].sse.to_numpy()) for seed in seeds]
    curves.append(('best_across_seeds', metrics.groupby('k').sse.min().reindex(ks).to_numpy()))
    for curve, sse in curves:
        for axis_mode in ['raw', 'sse_relative', 'unit_axes']:
            chosen, rows, status = geometric_elbow(ks, sse, axis_mode)
            elbow_choices.append(dict(context_id=context_id, curve=curve, axis_mode=axis_mode, selected_k=chosen, status=status))
            elbow_rows.extend(dict(context_id=context_id, curve=curve, **row) for row in rows)
    counts = training.groupby(MUNICIPAL_KEYS, observed=True).row_id.size()
    total_scope = metadata if scope == 'joint' else metadata[metadata.SEXO.eq(SCOPES[scope])]
    coverage = dict(context_id=context_id, scheme=scheme, scaling=scaling, scope=scope,
        scenario='with_101_plus' if include_tail else 'main', original_segments=len(full), training_segments=int(mask.sum()),
        pending_segments=int((~mask).sum()), training_LN=int(training.LN.sum()), original_LN=int(full.LN.sum()),
        training_LN_fraction=float(training.LN.sum()/full.LN.sum()),
        within_sex_LN_fraction=float(training.LN.sum()/total_scope.LN.sum()),
        municipalities=int(len(counts)), original_municipalities=int(metadata.groupby(MUNICIPAL_KEYS).ngroups),
        minimum_segments_per_municipality=int(counts.min()), median_segments_per_municipality=float(counts.median()),
        maximum_segments_per_municipality=int(counts.max()), high_ns_training=int(training.has_high_unspecified_rate.sum()),
        sex_2_training=int(training.SEXO.eq('2').sum()), tail_training=int(training.age_band.eq('101+').sum()))
    # Las etiquetas se releen y los NULL pendientes se contrastan explícitamente.
    save_table(folder/'labels.parquet', labels_frame)
    require(labels_frame.iloc[:, 6:].notna().all(axis=1).to_numpy().tolist() == mask.tolist(), 'Etiquetas fuera del alcance.')
    for filename, frame in [('model_metrics.csv', metrics), ('initializations.csv', pd.DataFrame(initializations)),
        ('cluster_summary.csv', pd.concat(summaries, ignore_index=True)),
        ('municipality_cluster_counts.parquet', pd.concat(municipality_tables, ignore_index=True)),
        ('cluster_distributions.csv', pd.concat(distributions, ignore_index=True)),
        ('seed_stability.csv', pd.DataFrame(stability)), ('geometric_elbow_details.csv', pd.DataFrame(elbow_rows))]:
        save_table(folder/filename, frame)
    municipal = counts.rename('training_segments').reset_index()
    save_table(folder/'municipality_training_counts.parquet', municipal)
    print(f'{context_id}: {len(training):,} segmentos; {len(metrics)} ajustes completos.', flush=True)
    return dict(context_id=context_id, metadata=full, training=training, mask=mask, raw=raw,
        labels=labels_by_model, metrics=metrics, stability=pd.DataFrame(stability), coverage=coverage,
        elbows=elbow_choices, weights=weight_review(training, context_id))


def compare_contexts(left, right, comparison):
    rows = []
    # El identificador de segmento es estable dentro de un esquema, nunca entre intervalos distintos.
    li = pd.Index(left['training'].row_id); ri = pd.Index(right['training'].row_id)
    common = li.intersection(ri, sort=False)
    a, b = li.get_indexer(common), ri.get_indexer(common)
    require(len(common) > 0, 'Comparación sin segmentos comunes.')
    for model_id in left['labels'].keys() & right['labels'].keys():
        x, y = left['labels'][model_id][a], right['labels'][model_id][b]
        rows.append(dict(comparison=comparison, left_context=left['context_id'], right_context=right['context_id'],
            k=int(model_id[1:3]), seed=int(model_id.split('seed')[1]), common_segments=len(common),
            ari=adjusted_rand(x, y), changed_fraction=label_change_fraction(x, y)))
    return rows


def plot_context(charts, context):
    context_id, metrics = context['context_id'], context['metrics']
    summary = metrics.groupby('k').agg(sse=('sse', 'min'), silhouette=('silhouette', 'mean'),
        silhouette_min=('silhouette', 'min'), silhouette_max=('silhouette', 'max'),
        db=('davies_bouldin', 'mean'), rate_r2=('participation_r2', 'mean'), age_r2=('age_r2', 'mean'),
        conditional=('within_age_sex_rate_r2', 'mean'))
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.3), layout='constrained')
    ax = axes[0, 0]; ax.plot(summary.index, summary.sse, 'o-'); ax.set_ylabel('SSE mínima entre semillas')
    choices = [item for item in context['elbows'] if item['curve'] == 'best_across_seeds']
    for item, style in zip(choices, ['--', ':', '-.']):
        if item['selected_k'] is not None: ax.axvline(item['selected_k'], ls=style, alpha=.6, label=item['axis_mode']+f" K={item['selected_k']}")
    ax.legend(fontsize=7); ax.set_title('Codo tradicional y geométrico')
    ax = axes[0, 1]; ax.plot(summary.index, summary.silhouette, 'o-')
    ax.fill_between(summary.index, summary.silhouette_min, summary.silhouette_max, alpha=.2)
    ax.set_ylabel('Silhouette medio de anclas'); ax.set_title('Rango entre semillas; aproximación')
    ax = axes[0, 2]; ax.plot(summary.index, summary.db, 'o-'); ax.set_ylabel('Davies–Bouldin exacto')
    ax = axes[1, 0]; stable = context['stability'].groupby('k').ari.agg(['mean', 'min'])
    ax.plot(stable.index, stable['mean'], 'o-', label='ARI medio'); ax.plot(stable.index, stable['min'], ':', label='ARI mínimo')
    ax.set_ylim(0, 1.03); ax.legend(); ax.set_ylabel('Estabilidad entre semillas')
    ax = axes[1, 1]
    for name, label in [('age_r2', 'Edad'), ('rate_r2', 'Tasa'), ('conditional', 'Tasa dentro de edad/sexo')]:
        ax.plot(summary.index, summary[name], 'o-', label=label)
    ax.set_ylim(0, 1.03); ax.legend(fontsize=8); ax.set_ylabel('Fracción descriptiva explicada')
    ax = axes[1, 2]
    for seed, group in metrics.groupby('seed'):
        ax.plot(group.k, group.minimum_cluster_fraction, 'o-', label=str(seed))
    ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.set_ylabel('Fracción del cluster más pequeño'); ax.legend(title='Semilla')
    for ax in axes.ravel(): ax.set_xlabel('K'); ax.set_xticks(KS); ax.grid(alpha=.2)
    fig.suptitle(f'Piloto B · {context_id} · n={len(context["training"]):,}\nPeso igual por segmento; ningún K seleccionado')
    fig.savefig(charts/f'{context_id}_diagnostics.png', dpi=150); plt.close(fig)


def plot_profiles(charts, context):
    data = context['training']
    fig, axes = plt.subplots(3, 3, figsize=(16, 13), layout='constrained')
    for row, k in enumerate([4, 5, 6]):
        labels = context['labels'][f'k{k:02d}_seed17']
        ax = axes[row, 0]
        ax.scatter(data.mean_age_nominal, data.participation_observed, c=labels, cmap='tab10', vmin=0, vmax=9, s=3, alpha=.25, rasterized=True)
        ax.set_xlabel('Edad media del segmento (peso LN)'); ax.set_ylabel('Participación observada')
        ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.set_title(f'K={k} · coordenadas originales')
        table = pd.crosstab(pd.Series(labels, name='cluster'), data.age_band, normalize='index')
        ax = axes[row, 1]; mesh = ax.imshow(table.to_numpy().T, cmap='Blues', vmin=0, vmax=1, aspect='auto')
        ax.set_xticks(range(k), [f'c{i}' for i in range(k)]); ax.set_yticks(range(len(table.columns)), table.columns)
        ax.set_title('Composición etaria: proporción de segmentos')
        for i in range(k):
            for j in range(len(table.columns)):
                ax.text(i, j, f'{table.iloc[i,j]:.0%}', ha='center', va='center', fontsize=8,
                    color='white' if table.iloc[i,j] > .55 else 'black')
        ax = axes[row, 2]
        values = [100*data.loc[labels == cluster, 'participation_deviation_national'].to_numpy() for cluster in range(k)]
        ax.boxplot(values, tick_labels=[f'c{i}' for i in range(k)], showfliers=False)
        ax.axhline(0, color='black', lw=.8); ax.set_ylabel('Diferencia nacional misma edad/sexo (pp)')
        ax.set_title('Dispersión dentro del cluster; sin puntos extremos')
    fig.suptitle(f'{context["context_id"]} · semilla 17 · K=4,5,6 como candidatos\nColores/etiquetas locales; segmentos agregados, no personas')
    fig.savefig(charts/f'{context["context_id"]}_profiles.png', dpi=150); plt.close(fig)


def plot_overview(charts, coverage, comparisons, contexts):
    main = coverage[coverage.scenario.eq('main') & coverage.scope.eq('joint') & coverage.scaling.eq('standard')]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout='constrained')
    x = np.arange(len(main))
    axes[0].bar(x-.15, main.training_segments/main.original_segments, .3, label='Segmentos')
    axes[0].bar(x+.15, main.training_LN_fraction, .3, label='LN'); axes[0].legend()
    axes[0].set_xticks(x, main.scheme); axes[0].set_ylim(0, 1.05); axes[0].yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].set_title('Cobertura principal · 18–100 y soporte suficiente')
    for context_id, context in contexts.items():
        if context['coverage']['scenario'] == 'main' and context['coverage']['scope'] == 'joint' and context['coverage']['scaling'] == 'standard':
            counts = context['training'].groupby(MUNICIPAL_KEYS).size().value_counts().sort_index()
            axes[1].plot(counts.index, counts.values, 'o-', label=context['coverage']['scheme'])
    axes[1].set_xlabel('Segmentos de entrenamiento por municipio'); axes[1].set_ylabel('Municipios'); axes[1].legend()
    fig.savefig(charts/'coverage_and_territorial_weight.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.7), layout='constrained')
    for ax, comparison, title in zip(axes, ['scaling', 'joint_vs_stratified', 'tail_101_plus'],
        ['Escalas original / estándar', 'Conjunto / por sexo', 'Principal / añade 101+ con soporte']):
        selected = comparisons[comparisons.comparison.eq(comparison)]
        for (left, right), group in selected.groupby(['left_context', 'right_context']):
            curve = group.groupby('k').ari.mean()
            ax.plot(curve.index, curve, 'o-', label=right.replace('_main', ''))
        ax.set_title(title); ax.set_xlabel('K'); ax.set_ylabel('ARI en segmentos comunes'); ax.set_ylim(-.03, 1.03)
        ax.legend(fontsize=6); ax.grid(alpha=.2)
    fig.suptitle('Sensibilidad de asignaciones · ARI medio entre las mismas semillas')
    fig.savefig(charts/'partition_sensitivity.png', dpi=160); plt.close(fig)


def supplementary_diagnostics(output, charts, contexts):
    """Resumen legible de candidatos, con composición por sexo y sin ajustar modelos."""
    tables = []
    for context_id, context in contexts.items():
        if context['coverage']['scenario'] != 'main':
            continue
        folder = output/'contexts'/context_id
        summary = pd.read_csv(folder/'cluster_summary.csv')
        distribution = pd.read_csv(folder/'cluster_distributions.csv', dtype={'category': str})
        summary = summary[summary.seed.eq(17) & summary.k.isin([4, 5, 6])].copy()
        for sex, name in [('0', 'men_fraction'), ('1', 'women_fraction'), ('2', 'nonbinary_fraction')]:
            sex_rows = distribution[distribution.dimension.eq('SEXO') & distribution.category.eq(sex)]
            indexed = sex_rows.set_index(['k', 'seed', 'cluster']).cluster_fraction
            summary[name] = indexed.reindex(pd.MultiIndex.from_frame(summary[['k', 'seed', 'cluster']])).fillna(0).to_numpy()
            # Cero aquí expresa ausencia comprobada de una categoría en un cluster entrenado,
            # nunca sustituye una tasa desconocida o una combinación fuente ausente.
        bands = distribution[distribution.dimension.eq('age_band')].sort_values(
            ['k', 'seed', 'cluster', 'cluster_fraction', 'category'], ascending=[True, True, True, False, True])
        bands = bands.drop_duplicates(['k', 'seed', 'cluster']).set_index(['k', 'seed', 'cluster'])
        index = pd.MultiIndex.from_frame(summary[['k', 'seed', 'cluster']])
        summary['dominant_band'] = bands.category.reindex(index).to_numpy()
        summary['dominant_band_fraction'] = bands.cluster_fraction.reindex(index).to_numpy()
        summary.insert(0, 'context_id', context_id)
        tables.append(summary)
        full = context['metadata'].copy()
        full['training_LN'] = np.where(full.is_training, full.LN, 0)
        municipal = full.groupby(MUNICIPAL_KEYS, as_index=False, observed=True).agg(
            original_segments=('row_id', 'size'), training_segments=('is_training', 'sum'),
            original_LN=('LN', 'sum'), training_LN=('training_LN', 'sum'))
        save_table(folder/'municipality_coverage.parquet', municipal)
    candidates = pd.concat(tables, ignore_index=True)
    save_table(output/'metadata/candidate_profiles.csv', candidates)
    plot_sex_summary(charts, candidates)
    return candidates


def plot_sex_summary(charts, candidates):
    """Etiquetas de cluster como categorías: puntos sin líneas o distancias ordinales."""
    for scheme in SCHEMES:
        selected = candidates[candidates.context_id.eq(f'{scheme}_standard_joint_main')]
        fig, axes = plt.subplots(2, 3, figsize=(15, 8), layout='constrained')
        for column, k in enumerate([4, 5, 6]):
            group = selected[selected.k.eq(k)].sort_values('cluster')
            ax = axes[0, column]
            ax.bar(group.cluster, group.men_fraction, label='Hombres', color='#386cb0')
            ax.bar(group.cluster, group.women_fraction, bottom=group.men_fraction, label='Mujeres', color='#e78ac3')
            ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.set_ylim(0, 1.05)
            ax.set_xticks(group.cluster, [f'c{value}' for value in group.cluster])
            ax.set_title(f'K={k} · composición de segmentos'); ax.set_xlabel('Etiqueta local'); ax.legend(fontsize=8)
            ax = axes[1, column]
            ax.scatter(group.cluster-.08, group.mean_participation, marker='o', label='Media de tasas por segmento')
            ax.scatter(group.cluster+.08, group.participation_observed, marker='s', label='ΣSV / Σ(SV+NV)')
            ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.set_ylim(0, 1)
            ax.set_xticks(group.cluster, [f'c{value}' for value in group.cluster])
            ax.set_xlabel('Etiqueta local (sin orden cuantitativo)'); ax.legend(fontsize=7)
        fig.suptitle(f'{scheme} · estándar conjunto · semilla 17\nSexo como metadato; dos formas distintas de resumir participación')
        fig.savefig(charts/f'{scheme}_sex_and_participation.png', dpi=160); plt.close(fig)


def write_report(output, charts, report, contexts, metrics, coverage, stability, elbows, comparisons,
                 weights, baselines, protected_count, n_init, anchor_count):
    """Sólo cifras calculadas; diagnóstico in-sample, sin elegir perfiles definitivos."""
    main = metrics[metrics.scenario.eq('main')]
    mean = main.groupby(['context_id', 'scheme', 'scaling', 'scope', 'k'], as_index=False).agg(
        silhouette=('silhouette', 'mean'), mc_se=('silhouette_mc_se', 'max'), db=('davies_bouldin', 'mean'),
        age_r2=('age_r2', 'mean'), rate_r2=('participation_r2', 'mean'),
        conditional_r2=('within_age_sex_rate_r2', 'mean'), band_purity=('age_band_purity', 'mean'),
        band_ari=('age_band_ari', 'mean'), age_share=('age_share_between_scaled', 'mean'),
        minimum_cluster=('minimum_cluster', 'min'))
    stable = stability.groupby(['context_id', 'k'], as_index=False).agg(ari_mean=('ari', 'mean'), ari_min=('ari', 'min'))
    mean = mean.merge(stable, on=['context_id', 'k'], validate='one_to_one')
    joint = mean[mean.scope.eq('joint')]
    quality = []
    for context_id, group in mean.groupby('context_id', sort=False):
        best_sil = group.loc[group.silhouette.idxmax()]; best_db = group.loc[group.db.idxmin()]
        choice = elbows[(elbows.context_id.eq(context_id)) & elbows.curve.eq('best_across_seeds')]
        by_mode = choice.set_index('axis_mode').selected_k
        quality.append([context_id, int(best_sil.k), f'{best_sil.silhouette:.4f}', int(best_db.k),
            f'{best_db.db:.4f}', str(by_mode.get('raw')), str(by_mode.get('unit_axes'))])
    coverage_rows = []
    for row in coverage[coverage.scenario.eq('main') & coverage.scaling.eq('standard')].itertuples():
        coverage_rows.append([row.scheme, row.scope, number(row.training_segments), number(row.training_LN),
            pct(row.training_LN_fraction), pct(row.within_sex_LN_fraction), number(row.municipalities), number(row.high_ns_training)])
    candidate_rows = []
    for row in joint[joint.k.isin([4, 5, 6])].itertuples():
        candidate_rows.append([row.scheme, row.scaling, row.k, f'{row.silhouette:.4f}', f'{row.db:.4f}',
            pct(row.band_purity), f'{row.band_ari:.3f}', pct(row.age_r2), pct(row.rate_r2),
            pct(row.conditional_r2), f'{row.ari_min:.3f}', number(row.minimum_cluster)])
    stratified_rows = []
    for row in mean[mean.scope.ne('joint') & mean.scaling.eq('standard') & mean.k.isin([4, 5, 6])].itertuples():
        stratified_rows.append([row.scheme, row.scope, row.k, f'{row.silhouette:.4f}', pct(row.age_r2),
            pct(row.rate_r2), pct(row.conditional_r2), f'{row.ari_min:.3f}'])
    comparison_rows = []
    selected_comparisons = comparisons[comparisons.k.isin([4, 5, 6])]
    for (kind, left, right, k), group in selected_comparisons.groupby(['comparison', 'left_context', 'right_context', 'k']):
        comparison_rows.append([kind, left, right, k, number(group.common_segments.iloc[0]),
            f'{group.ari.mean():.3f}', pct(group.changed_fraction.mean())])
    baseline_rows = []
    for scheme, reference in baselines.items():
        for row in reference.itertuples():
            baseline_rows.append([scheme, row.age_band, SEX_LABELS[row.SEXO], number(row.LN), number(row.specified_count),
                pct(row.national_participation), pct(row.national_unspecified_rate)])
    weight_rows = []
    for row in weights[weights.context_id.str.endswith('standard_joint_main')].itertuples():
        weight_rows.append([row.context_id, row.weighting, pct(row.top_ten_municipality_weight),
            pct(row.mean_participation), f'{row.mean_age:.2f}', f'{100*row.mean_national_deviation:.2f}', pct(row.high_ns_weight)])
    relative = pd.read_csv(output/'metadata/relative_representation_review.csv')
    relative_rows = [[row.scheme, row.variable, number(row.n), f'{row.mean:.4f}', f'{row.std:.4f}',
        f'{row.q1:.4f}', f'{row.median:.4f}', f'{row.q3:.4f}', f'{row.pearson_age:.3f}']
        for row in relative[relative.population.eq('training_main')].itertuples()]
    profile_path = output/'metadata/candidate_profiles.csv'
    profile_rows = []
    if profile_path.exists():
        profiles = pd.read_csv(profile_path)
        profiles = profiles[profiles.context_id.isin([f'{scheme}_standard_joint_main' for scheme in SCHEMES])]
        for row in profiles.itertuples():
            profile_rows.append([row.context_id.split('_standard')[0], row.k, row.cluster, number(row.observations),
                number(row.municipalities), f'{row.mean_age:.2f}', pct(row.women_fraction),
                row.dominant_band, pct(row.dominant_band_fraction), pct(row.participation_observed),
                pct(row.unspecified_rate), f'{100*row.mean_national_deviation:.2f}'])
    representation_findings = []
    for scheme in SCHEMES:
        principal = contexts[f'{scheme}_standard_joint_main']
        bands_n = principal['training'].age_band.nunique()
        raw_row = joint[joint.scheme.eq(scheme) & joint.scaling.eq('original') & joint.k.eq(bands_n)].iloc[0]
        standard = joint[joint.scheme.eq(scheme) & joint.scaling.eq('standard')]
        affected = standard[standard.ari_min.lt(.9)]
        representation_findings.append(f'- {scheme}: la solución original K={bands_n} tiene pureza de banda '
            f'{pct(raw_row.band_purity)} y R² de tasa dentro de edad/sexo {pct(raw_row.conditional_r2)}: '
            'reproduce el diseño etario en vez de descubrir nuevos perfiles. '
            + ('En escala estándar, los K con ARI mínimo entre semillas <0.90 son '
               +', '.join(str(int(value)) for value in affected.k)+'. ' if len(affected) else
               'Todos los K estandarizados mantienen ARI mínimo ≥0.90 entre las semillas ensayadas. ')
            +f'{2477-principal["coverage"]["municipalities"]} municipios no aportan ningún segmento al entrenamiento principal, '
            'aunque permanecen conservados en los metadatos.')
    tail_example = comparisons[comparisons.comparison.eq('tail_101_plus') & comparisons.k.eq(6)
        & comparisons.left_context.eq('life_stage_standard_joint_main')].sort_values('seed')
    tail_findings = '; '.join(f'semilla {int(row.seed)}: ARI={row.ari:.3f}, '
        f'cambio alineado={pct(row.changed_fraction)}' for row in tail_example.itertuples())
    sex_example = comparisons[comparisons.comparison.eq('joint_vs_stratified') & comparisons.k.eq(5)
        & comparisons.left_context.eq('life_stage_standard_joint_main')]
    sex_findings = '; '.join(f'{right.split("_standard_")[1].replace("_main", "")}: ARI medio={group.ari.mean():.3f}'
        for right, group in sex_example.groupby('right_context'))
    # Interpretación explícita, apoyada en los diagnósticos calculados, no en nombres de clusters.
    findings = []
    for scheme in SCHEMES:
        for scaling in SCALINGS:
            part = joint[joint.scheme.eq(scheme) & joint.scaling.eq(scaling) & joint.k.isin([4, 5, 6])]
            findings.append(f'- **{scheme} / {scaling}, K=4–6:** pureza de banda {pct(part.band_purity.min())}–{pct(part.band_purity.max())}; '
                f'fracción explicada de edad {pct(part.age_r2.min())}–{pct(part.age_r2.max())}; de tasa {pct(part.rate_r2.min())}–{pct(part.rate_r2.max())}; '
                f'mejora de tasa dentro de edad/sexo {pct(part.conditional_r2.min())}–{pct(part.conditional_r2.max())}; '
                f'ARI mínimo entre semillas {part.ari_min.min():.3f}.')
    main_joint = coverage[coverage.scenario.eq('main') & coverage.scope.eq('joint') & coverage.scaling.eq('standard')]
    sources = [contexts[f'{scheme}_standard_joint_main']['metadata'] for scheme in SCHEMES]
    preserved = []
    for scheme, frame in zip(SCHEMES, sources):
        subset = frame[frame.SEXO.eq('2')]
        preserved.append(f'{scheme}: {len(subset)} segmentos SEXO=2, {int(subset.source_row_count.sum())} filas fuente, LN={int(subset.LN.sum())}')
    text = f'''# Primer piloto demográfico B · 2024

## Resultado y alcance

Se ajustaron **{len(metrics)} modelos K-Means**, en {len(contexts)} contextos: dos esquemas experimentales, escalas original y estándar, análisis conjunto y por sexo, más sensibilidad conjunta que incorpora 101+ con soporte. Se evalúa K=2–10, con las semillas {SEEDS} y {n_init} inicializaciones k-means++ por semilla. No se elige K ni perfiles definitivos. La unidad es un segmento municipal de edad/sexo, **no una persona**. Municipio, entidad, distrito, SEXO y año no son características ni distancias.

El escalamiento original produce principalmente cortes de edad; el estándar permite que la tasa contribuya a la separación. Los diagnósticos siguientes cuantifican esa diferencia y evitan llamar «patrones ciudadanos» a particiones que reproducen intervalos predefinidos. Se recomienda continuar evaluando los escenarios estandarizados frente a referencias por edad/sexo, sin considerar validada una taxonomía. Una puntuación interna alta o una solución estable no prueba utilidad sustantiva.

{chr(10).join(findings)}

{chr(10).join(representation_findings)}

Como candidatos de seguimiento, life_stage estandarizado K=4/5 permite examinar diferencias de participación dentro de bandas, sin reproducirlas exactamente. K=6 debe contrastarse especialmente con la cola: {tail_findings}. Los candidatos broad estandarizados también separan tasas dentro de bandas, pero con pureza etaria alta; a K elevados se parecen más a subdivisiones de cada banda por nivel. Esta es una lectura de las dos características disponibles, no el hallazgo de tipos individuales. Los máximos de métricas que caen fuera de 4–6 se mantienen en la evaluación.

## Población, soporte y conservación

{markdown_table(['Esquema', 'Alcance', 'Entrenamiento', 'LN entrenamiento', '% LN de toda B', '% LN de su sexo', 'Municipios', 'NS≥10 % en entrenamiento'], coverage_rows)}

Soporte suficiente exige LN≥100, SV+NV≥100 y filas fuente≥5, además de ambas características finitas. El principal limita el alcance a 18–100. NS≥10 % **no excluye** observaciones: se registra como limitación. Los porcentajes LN por sexo usan como denominador todo su LN original, incluidas edades 101+; en el conjunto coinciden con la cobertura total. Las coberturas de los sexos no deben sumarse como porcentajes de una misma base.

Cada contexto conserva **todas** las filas de la matriz de origen, sus conteos, claves de texto y motivos de no entrenamiento; las etiquetas de pendientes son NULL. Las banderas de alcance, completitud y soporte permiten ver motivos simultáneos; pending_reason sólo presenta un motivo prioritario. Referencias originales a edad exacta: data/processed/cluster_features/reference/exact_age_2024.parquet. No se agrupan de nuevo las edades ni se vuelve a los registros originales.

Se preservan {('; '.join(preserved))}. Ningún segmento SEXO=2 supera el soporte y no se ajusta un estrato sin observaciones elegibles. Sus registros no se convierten en H/M. Los mayores de 100 representan LN=13,197 y 12,891 filas fuente en cada vista; seis segmentos 101+ de mujeres superan soporte y entran sólo en la sensibilidad. Esta sensibilidad tiene alcance limitado: no valida la plausibilidad de las edades ni estudia el efecto de entrenar con todos los segmentos escasos.

![Cobertura y reparto territorial]({os.path.relpath(charts/'coverage_and_territorial_weight.png', report.parent).replace(chr(92), '/')})

## Variables, estandarización y referencia nacional

Sólo se usan participation_observed=SV/(SV+NV) y mean_age_nominal=Σ(edad×LN)/ΣLN. Son las dos columnas del contrato B. El escalador estándar usa media y DE poblacional (ddof=0) **del conjunto principal elegible de cada esquema**, sin ponderar, y se reutiliza en sus estratos y sensibilidad 101+. Así se mantiene una geometría común al comparar modelos conjuntos y por sexo. Se guardan parámetros y copias experimentales nuevas; las matrices anteriores permanecen intactas. La versión original usa centro cero y escala uno. Edad en años y tasa en proporción son unidades distintas: comparar SSE entre escalas no evalúa cuál modelo es mejor.

La tasa nacional de cada intervalo/sexo se calcula con todos sus conteos, antes de seleccionar el entrenamiento. La diferencia firmada es tasa del segmento menos esa tasa nacional; es un descriptor alternativo, **no una tercera característica añadida al modelo**. Los ceros válidos se mantienen y SV+NV=0 sigue NULL. Una media de diferencias por segmento no tiene por qué ser cero: la referencia nacional pondera por SV+NV. En national_reference_SCHEME.csv y relative_representation_review.csv se conservan distribución, correlaciones y base válida; weight_review.csv documenta pesos. El rango propio de las diferencias es [−1,1]; los boxplots lo expresan en puntos porcentuales.

{markdown_table(['Esquema', 'Intervalo', 'Sexo', 'LN', 'SV+NV', 'Participación nacional', 'NS/LN'], baseline_rows)}

Diagnóstico de la alternativa relativa en la misma población principal, sin otro ajuste (todos los valores de tasa/diferencia se muestran como proporciones; multiplicar por 100 para porcentajes o pp):

{markdown_table(['Esquema', 'Variable', 'n', 'Media', 'DE', 'Q1', 'Mediana', 'Q3', 'Correlación con edad media'], relative_rows)}

La correlación con edad disminuye y cambia de signo al usar diferencias relativas en ambos esquemas; queda una asociación residual y no se declara independencia. Su menor dispersión refleja la resta de referencias demográficas, no una mejora validada de clustering. Esta evidencia justifica comparar posteriormente una representación relativa separada si la pregunta es participación frente a pares, en lugar de añadir tasa y diferencia como información duplicada parcialmente.

Una representación futura [diferencia nacional, edad media] preguntaría por participación relativa a pares demográficos y seguiría necesitando decidir el papel de edad y sexo. La resta por celda es una referencia descriptiva, no un ajuste causal ni una estimación individual. Se conserva para sensibilidad futura; no se ejecutó ese modelo ni se añadió junto a la tasa original. Eliminar el nivel nacional puede ocultar diferencias absolutas relevantes; usar sólo el residuo también pierde posición etaria en la distancia.

## K-Means, codos y métricas

Se reutiliza clustering_core.py del piloto territorial: Lloyd con k-means++ D², selección de menor SSE entre inicializaciones y parada por asignaciones estables (máximo 1,000 iteraciones). No se afirma equivalencia exacta con la implementación de scikit-learn. Todos los mejores ajustes convergieron y tienen K grupos no vacíos. Se guardan las {len(metrics)*n_init:,} inicializaciones, incluida convergencia de cada una. Ajustes y comparaciones usan peso uno por segmento.

SSE y Davies–Bouldin se calculan exactamente en todo el entrenamiento. Silhouette se estima con hasta **{anchor_count} anclas uniformes sin reemplazo**, semilla 319; cada ancla se compara contra **todos** los puntos del entrenamiento. No se calcula Silhouette sólo dentro de la submuestra. Se reutilizan anclas entre K, semillas y escalas con la misma población. El rectángulo de distancias m×n se construye por bloques de 128 anclas; no se crea una matriz B n×n. silhouette_mc_se informa el error de aproximación de la media por muestreo de anclas (con corrección por población finita), no incertidumbre electoral; no debe confundirse con variación entre semillas. Diferencias pequeñas necesitan más anclas o evaluación exacta por bloques antes de decidir. [Definición de Silhouette](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html), [Davies–Bouldin](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.davies_bouldin_score.html).

El codo tradicional muestra SSE frente a K. El geométrico reutiliza la ecuación (4), teorema 2.5, del [método implementado previamente](https://arxiv.org/html/2502.00851v2), sin cambiarlo: pendientes consecutivas a,b, candidato elegible b>a, mínimo de (a−b)/(1+ab). Sólo puede escoger K interiores 3–9. Se muestran controles con SSE relativa y ambos ejes llevados a [0,1] **sólo para calcular el ángulo**; esto no es otro escalamiento del entrenamiento. El ángulo depende de las unidades de los ejes y no decide por sí mismo K. Se conserva el cálculo por semilla y con SSE mínima entre semillas. No se fuerza monotonía ni se ajusta la curva.

{markdown_table(['Contexto principal', 'K máx. Silhouette medio', 'Silhouette', 'K mín. DB medio', 'DB', 'K geométrico crudo', 'K geométrico ejes unitarios'], quality)}

Los extremos de métricas son candidatos internos sobre los K probados, sin evidencia de un K verdadero. No se comparan directamente Silhouettes de poblaciones o geometrías diferentes como una clasificación universal de modelos. Cada PNG *_diagnostics muestra codo, Silhouette, DB, estabilidad y tamaño mínimo.

## K=4, 5 y 6: edad, nivel y variación dentro de pares demográficos

Pureza de banda = Σ máximo número de segmentos de una banda por cluster / n. Puede aumentar con K aunque sólo se partan intervalos. ARI de banda compara las etiquetas con bandas predefinidas. R² de edad/tasa es la fracción de su suma de cuadrados explicada por los centroides de los clusters, sin ponderar. R² de tasa dentro de edad/sexo compara el residuo usando medias de cada intervalo/sexo frente a medias intervalo/sexo/cluster: mide separación adicional **descriptiva dentro de la misma celda demográfica**, no predicción fuera de muestra ni causalidad. Se calcula en entrenamiento y crece con la flexibilidad; no valida perfiles por sí solo.

{markdown_table(['Esquema', 'Escala', 'K', 'Silhouette', 'DB', 'Pureza banda', 'ARI banda', 'R² edad', 'R² tasa', 'R² tasa dentro edad/sexo', 'ARI semilla mín.', 'Cluster mín.'], candidate_rows)}

Las configuraciones originales permiten verificar el dominio de la edad en las unidades crudas. Las estandarizadas son candidatas más informativas para separar niveles de participación a edades semejantes si su mejora dentro de edad/sexo es apreciable; siguen mezclando edad y nivel absoluto. No se demuestra aquí una dimensión de comportamiento distinta de edad, sexo y tasa: ésas son las únicas fuentes demográficas disponibles en esta matriz. Un cluster que sólo ordene niveles altos/bajos puede ser descriptivamente útil, pero no constituye un tipo de ciudadano ni una explicación del nivel.

Los archivos cluster_summary.csv y cluster_distributions.csv de **cada contexto y de cada ajuste** incluyen conteos, tasas por suma de conteos, media de tasas de segmentos, diferencia nacional media y cuartiles, composición por intervalo y sexo y municipios representados. municipality_cluster_counts.parquet conserva cuántos segmentos aporta cada municipio a cada cluster y sus denominadores. Un mismo municipio puede aparecer en varios clusters y no se suman sus frecuencias como municipios únicos entre clusters. Las etiquetas c0,c1,… son locales a cada ajuste y no tienen orden, nombre o correspondencia automática.

Resumen de candidatos conjuntos estandarizados, semilla 17, sin nombres ni perfiles definitivos. La tasa de cluster usa suma de conteos; Δ nacional es la media no ponderada de las diferencias de sus segmentos contra su propio intervalo/sexo. Son dos resúmenes distintos, con denominadores distintos:

{markdown_table(['Esquema', 'K', 'Etiqueta local', 'Segmentos', 'Municipios', 'Edad media', '% mujeres', 'Banda dominante', '% banda', 'Tasa ΣSV/Σesp.', 'NS/LN', 'Δ nacional medio (pp)'], profile_rows)}

![Sexo y participación por cluster]({os.path.relpath(charts/'life_stage_sex_and_participation.png', report.parent).replace(chr(92), '/')})

![Etapas original: candidatos]({os.path.relpath(charts/'life_stage_original_joint_main_profiles.png', report.parent).replace(chr(92), '/')})

![Etapas estándar: candidatos]({os.path.relpath(charts/'life_stage_standard_joint_main_profiles.png', report.parent).replace(chr(92), '/')})

## Conjunto frente a estratos por sexo

El conjunto usa sexo sólo para interpretación. Los estratos H/M usan las mismas dos variables y el mismo escalador que su conjunto, con la selección de soporte aplicada a cada segmento. Comparar K del conjunto con K por sexo cambia el número total de grupos disponibles en el sistema estratificado (hasta 2K); no son particiones equivalentes por construcción. ARI se calcula sólo en segmentos comunes del mismo sexo, sin comparar números de etiquetas. No se ajustó una categoría histórica ausente o insuficiente.

{markdown_table(['Esquema', 'Estrato estándar', 'K', 'Silhouette', 'R² edad', 'R² tasa', 'R² tasa dentro edad/sexo', 'ARI semilla mín.'], stratified_rows)}

Los resultados estratificados permiten separar qué diferencias se mantienen dentro de hombres o mujeres y cuáles dependen de la mezcla del modelo conjunto. Que sus asignaciones difieran no prueba que existan tipos naturales distintos por sexo. Se necesita contrastar perfiles y estabilidad fuera de esta elección antes de interpretarlos sustantivamente.

En life_stage estándar K=5, la concordancia conjunto/estratos es {sex_findings}. Las diferencias son materiales: el conjunto no sustituye automáticamente el análisis por sexo. Las tasas y la composición de los clusters permiten estudiar esa diferencia sin asignar a SEXO una distancia numérica.

## Sensibilidad de asignaciones

{markdown_table(['Comparación', 'Contexto izquierdo', 'Contexto derecho', 'K', 'Segmentos comunes', 'ARI medio', '% cambio tras alinear'], comparison_rows)}

Se alinean etiquetas por máximo solapamiento antes de contar cambios; ARI no requiere esa alineación. Se comparan las mismas semillas. No se calcula ARI entre broad y life_stage: sus unidades no tienen correspondencia uno a uno. La sensibilidad 101+ reutiliza escaladores y parámetros principales y sólo agrega las seis observaciones elegibles; una estabilidad elevada o baja bajo este cambio pequeño no justifica incorporar automáticamente todas las edades extremas.

En particular, life_stage estándar K=6 cambia aproximadamente 20 % de las asignaciones principales con dos semillas al incorporar sólo seis segmentos elegibles. La semilla 17 permanece muy cercana al principal. **Una misma semilla no conserva los centros iniciales cuando cambia la población**: el muestreo k-means++ depende de sus puntos. Por ello, esta comparación combina el efecto de ampliar la población con la selección de mínimos locales y no aísla una causa atribuible a edades extremas. La estabilidad alta entre semillas del principal no basta para garantizar robustez. Antes de elegir K=6, contrastar más inicializaciones y centros iniciales comunes entre poblaciones, además de los cambios en SSE y perfiles. No se inventa un efecto causal de seis edades.

![Comparación de asignaciones]({os.path.relpath(charts/'partition_sensitivity.png', report.parent).replace(chr(92), '/')})

## Ponderación y sesgo territorial potencial

{markdown_table(['Contexto', 'Peso diagnóstico', '% peso diez municipios mayores', 'Media tasa', 'Edad media', 'Diferencia nacional media (pp)', '% peso NS≥10 %'], weight_rows)}

Estos pesos se comparan descriptivamente; todos los ajustes usan igual peso por segmento. Ello da mayor peso total a municipios que aportan más segmentos elegibles, incluidas diferencias de soporte entre sexos/edades. Los municipios sin ningún segmento elegible no influyen en los centroides y permanecen pendientes; no equivalen a territorios de participación cero. municipality_training_counts.parquet y coverage.csv cuantifican ese reparto.

Peso total uno por municipio se calcula como 1/n de sus segmentos **de entrenamiento**, distinto del peso precalculado sobre todos los segmentos originales. Peso LN del segmento acentúa municipios y segmentos grandes y cambia la pregunta a volumen nominal; no corrige NS o sesgos de captura. La media de tasas con peso LN no equivale necesariamente a SV nacional/(SV+NV nacional). La concentración equivalente de pesos no es tamaño muestral efectivo. Se debe ejecutar una sensibilidad ponderada autorizada antes de elegir una interpretación territorial; este piloto sólo identifica sus posibles efectos.

## Validaciones, archivos y reproducción

Se leyeron únicamente las dos matrices B existentes y sus metadatos/contratos. Cada vista conserva LN=98,330,348, SV=54,899,228, NV=37,105,466, NS=6,325,654 y 9,773,730 filas fuente representadas. Ambas vistas son alternativas y no se suman. Se concilian por entidad contra los descriptivos de 2024 y LN=SV+NV+NS por segmento. Para cada ajuste, todos los conteos de los clusters se concilian con su entrenamiento; las filas pendientes permanecen sin etiqueta. Se comprueban unicidad de claves, alineación, tipos territoriales de texto, finitud de entrenamiento, K grupos no vacíos, SSE/centroides y dominios de métricas. El método de anclas y DB se contrastan en pruebas pequeñas con el cálculo exacto del núcleo existente.

Se contrastan hashes de **{protected_count:,} archivos existentes** antes y después, incluidas fuentes, Parquet previos, gráficas e informes anteriores. Se verifica el marcador _SUCCESS de matrices candidatas, su manifiesto y hashes. Los derivados nuevos se releen tras escribirlos. El manifiesto guarda versiones, parámetros, fuentes, hashes y estado; _SUCCESS sólo se escribe tras completar todas las verificaciones. Los nuevos algoritmos no se ejecutan desde el frontend.

Estructura de data/processed/demographic_pilot/: reference/b_SCHEME.parquet conserva todos los segmentos con su diferencia nacional; contexts/CONTEXT/ contiene features.parquet (copias escaladas experimentales, ambas variables), metadata.parquet, pending_observations.parquet, labels.parquet con claves y etiquetas nullable por K/semilla, scaler.json, anclas, métricas, inicializaciones y distribuciones. metadata/ contiene conciliaciones, cobertura, referencias nacionales, pesos, correlaciones relativas, estabilidad, codos, comparaciones y manifiesto. La referencia de edad exacta sigue en cluster_features; no se duplica ni se modifica. No incorporar row_id, claves, etiquetas, banderas o conteos al arreglo numérico de entrenamiento.

```powershell
.venv/Scripts/python.exe analysis/scripts/run_demographic_pilot.py
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_demographic_pilot.py
```

El script rechaza destinos existentes; otra ejecución requiere rutas nuevas --output, --charts y --report. --anchor-count controla únicamente la precisión/coste de Silhouette; el ajuste siempre usa todo el entrenamiento elegible. No requiere dependencias nuevas. No ejecuta Ward, K-Medoids o DBSCAN; no modifica fuentes, matrices previas, informes anteriores o src/ y no crea commits.

--review-existing permite regenerar exclusivamente la documentación de esta entrega y añadir resúmenes a partir de sus ajustes, sin volver a entrenar. Antes comprueba el marcador, hashes de todos los derivados y fuentes y el informe esperado; actualiza el manifiesto y _SUCCESS al finalizar. No sirve para modificar informes de pilotos anteriores.

## Decisiones y validación pendientes

Antes de seleccionar perfiles: decidir si se quieren niveles absolutos o diferencias frente a pares; contrastar rangos sin fijarlos aún; comprobar que las separaciones no se expliquen sólo por bandas predefinidas; validar estabilidad de semillas, escalamiento, ponderación, denominadores y NS; revisar edades extremas con documentación de origen; definir una estrategia para segmentos incompletos/escasos y SEXO=2 sin inventar datos; ampliar precisión de Silhouette cuando los candidatos sean cercanos. La conservación íntegra no implica que todos los segmentos sean entrenables con estas reglas.

K=4,5,6 se inspeccionan como candidatos, no como un rango obligatorio. SSE siempre favorece más flexibilidad; codos, DB, Silhouette y estabilidad pueden discrepar. Ni correlaciones ni clusters demuestran causalidad o conductas individuales. Este piloto de 2024 no establece persistencia histórica y no justifica extrapolar a otros años sin correspondencias territoriales y soporte comparables.
'''
    report.write_text(text, encoding='utf-8')


def run_pilot(root, output, charts, report, anchor_count=1200, n_init=10):
    root, output, charts, report = [Path(path).resolve() for path in [root, output, charts, report]]
    require(output.is_relative_to(root/'data/processed') and charts.is_relative_to(root/'analysis/charts') and
        report.is_relative_to(root/'analysis/reports'), 'Destinos fuera del área autorizada.')
    require(not output.exists() and not charts.exists() and not report.exists(), 'Elegir rutas nuevas: no se sobrescriben resultados.')
    require(anchor_count >= 2 and n_init >= 2, 'Se requieren múltiples inicializaciones y anclas.')
    protected = snapshot_inputs(root, output, charts)
    source = root/'data/processed/cluster_features'
    manifest_path = source/'metadata/run_manifest.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8'))
    success = json.loads((source/'_SUCCESS').read_text(encoding='utf-8'))
    require(previous['status'] == 'validated' and success['manifest_sha256'] == file_hash(manifest_path), 'Matrices sin validar.')
    for relative, digest in previous['artifact_hashes'].items():
        require(file_hash(root/relative) == digest, f'Matriz anterior alterada: {relative}')
    contract = json.loads((source/'metadata/feature_contract.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True); charts.mkdir(parents=True); (output/'metadata').mkdir(); (output/'reference').mkdir()
    start = time.monotonic()
    manifest = dict(status='running', errors=[], election_year=2024, protected_hashes=protected,
        configuration=dict(schemes=SCHEMES, scalings=SCALINGS, scopes=SCOPES, ks=KS, seeds=SEEDS,
            n_init=n_init, max_iter=1000, anchor_count=anchor_count, anchor_seed=319, distance_block=128,
            features=FEATURES, fit_weight='equal_segment', min_LN=100, min_specified=100, min_source_rows=5,
            high_ns=.1, national_reference='all_original_segments', scaler_fit='joint_primary_per_scheme'),
        started_at_utc=datetime.now(timezone.utc).isoformat(), versions=dict(python=platform.python_version(),
            numpy=np.__version__, pandas=pd.__version__, pyarrow=pa.__version__, matplotlib=matplotlib.__version__))
    save_json(output/'metadata/run_manifest.json', manifest)
    manifest['configuration']['silhouette_mc_se_convention'] = 'sample_sd_ddof1_times_sqrt_1_minus_m_over_n_over_sqrt_m'
    try:
        contexts, baselines, reconciliation, relative_review = {}, {}, [], []
        states = pd.read_parquet(root/'data/processed/descriptive/state/table.parquet').query('election_year == 2024')
        for scheme in SCHEMES:
            folder = source/'matrices'/('b_'+scheme)
            features, metadata = pd.read_parquet(folder/'features.parquet'), pd.read_parquet(folder/'metadata.parquet')
            require(contract['matrices']['b_'+scheme]['feature_columns'] == FEATURES, 'Contrato de características inesperado.')
            require(features.columns.tolist() == ['row_id', *FEATURES] and features.row_id.equals(metadata.row_id), 'Alineación inválida.')
            require(not metadata.duplicated(KEYS).any() and not metadata.row_id.duplicated().any(), 'Claves B duplicadas.')
            require(np.allclose(features[FEATURES], metadata[FEATURES], equal_nan=True), 'Variables y metadatos difieren.')
            for name in ['EDOCVE', 'MPIOCVE', 'SEXO']:
                require(metadata[name].map(lambda v: isinstance(v, str)).all(), f'Clave no textual: {name}')
            require(metadata.LN.eq(metadata.SV+metadata.NV+metadata.NS).all(), 'Identidad de conteos inválida.')
            require(metadata.source_row_count.sum() == 9_773_730 and metadata.LN.sum() == 98_330_348, 'Población 2024 alterada.')
            sex_2 = metadata[metadata.SEXO.eq('2')]
            require(sex_2.source_row_count.sum() == 105 and sex_2.LN.sum() == 105, 'Se perdió SEXO=2.')
            for state, group in metadata.groupby('EDOCVE', observed=True):
                expected = states[states.EDOCVE.eq(state)]
                require(len(expected) == 1, 'Entidad sin referencia.')
                for metric in METRICS:
                    difference = int(group[metric].sum()-expected[metric].iloc[0])
                    require(difference == 0, 'Suma por entidad no conciliada.')
                    reconciliation.append(dict(scheme=scheme, EDOCVE=state, metric=metric, difference=difference))
            enriched, reference = add_reference(metadata)
            save_table(output/'reference'/f'b_{scheme}.parquet', enriched)
            baselines[scheme] = reference
            save_table(output/'metadata'/f'national_reference_{scheme}.csv', reference)
            for population, frame in [('all_defined', enriched[enriched.participation_observed.notna()]),
                                      ('training_main', enriched.loc[selection(enriched)[0]])]:
                for name in ['participation_observed', 'participation_deviation_national']:
                    values = frame[name]
                    relative_review.append(dict(scheme=scheme, population=population, variable=name, n=len(frame),
                        mean=float(values.mean()), std=float(values.std(ddof=0)), q1=float(values.quantile(.25)),
                        median=float(values.median()), q3=float(values.quantile(.75)),
                        pearson_age=float(values.corr(frame.mean_age_nominal)),
                        pearson_absolute_rate=float(values.corr(frame.participation_observed))))
            main_mask = selection(enriched)[0]
            require(not (main_mask & enriched.SEXO.eq('2').to_numpy()).any(), 'Se requiere revisar alcance de SEXO=2 ahora elegible.')
            for scaling in SCALINGS:
                scaler = fit_scaler(enriched.loc[main_mask, FEATURES].to_numpy(dtype=float), scaling)
                for scope in SCOPES:
                    context_id = f'{scheme}_{scaling}_{scope}_main'
                    contexts[context_id] = run_context(context_id, scheme, scaling, scope, False, enriched,
                        scaler, output, anchor_count, n_init)
                    plot_context(charts, contexts[context_id]); plot_profiles(charts, contexts[context_id])
                context_id = f'{scheme}_{scaling}_joint_with_101_plus'
                contexts[context_id] = run_context(context_id, scheme, scaling, 'joint', True, enriched,
                    scaler, output, anchor_count, n_init)
                plot_context(charts, contexts[context_id])
        metrics = pd.concat([c['metrics'] for c in contexts.values()], ignore_index=True)
        coverage = pd.DataFrame([c['coverage'] for c in contexts.values()])
        stability = pd.concat([c['stability'] for c in contexts.values()], ignore_index=True)
        elbows = pd.DataFrame([row for c in contexts.values() for row in c['elbows']])
        weights = pd.DataFrame([row for c in contexts.values() for row in c['weights']])
        comparison_rows = []
        for scheme in SCHEMES:
            for scope in SCOPES:
                comparison_rows.extend(compare_contexts(contexts[f'{scheme}_original_{scope}_main'],
                    contexts[f'{scheme}_standard_{scope}_main'], 'scaling'))
            for scaling in SCALINGS:
                joint = contexts[f'{scheme}_{scaling}_joint_main']
                comparison_rows.extend(compare_contexts(joint, contexts[f'{scheme}_{scaling}_joint_with_101_plus'], 'tail_101_plus'))
                for scope in ['men', 'women']:
                    comparison_rows.extend(compare_contexts(joint, contexts[f'{scheme}_{scaling}_{scope}_main'], 'joint_vs_stratified'))
        comparisons = pd.DataFrame(comparison_rows).sort_values(['comparison', 'left_context', 'right_context', 'k', 'seed']).reset_index(drop=True)
        for filename, frame in [('model_metrics.csv', metrics), ('coverage.csv', coverage), ('seed_stability.csv', stability),
            ('elbow_candidates.csv', elbows), ('partition_comparisons.csv', comparisons), ('weight_review.csv', weights),
            ('state_reconciliation.csv', pd.DataFrame(reconciliation)), ('relative_representation_review.csv', pd.DataFrame(relative_review))]:
            save_table(output/'metadata'/filename, frame)
        require(len(metrics) == 432 and metrics.converged.all(), 'Cantidad o convergencia de ajustes inesperada.')
        require(metrics.silhouette.between(-1, 1).all() and metrics.davies_bouldin.ge(0).all(), 'Métricas fuera de dominio.')
        plot_overview(charts, coverage, comparisons, contexts)
        supplementary_diagnostics(output, charts, contexts)
        write_report(output, charts, report, contexts, metrics, coverage, stability, elbows, comparisons,
            weights, baselines, len(protected), n_init, anchor_count)
        for path, digest in protected.items(): require(file_hash(path) == digest, f'Archivo existente modificado: {path}')
        manifest.update(status='validated', seconds=round(time.monotonic()-start, 2),
            finished_at_utc=datetime.now(timezone.utc).isoformat(), contexts=len(contexts), fitted_models=len(metrics),
            protected_files=len(protected), script_hashes={name: file_hash(root/'analysis/scripts'/name)
                for name in ['run_demographic_pilot.py', 'clustering_core.py', 'run_clustering_pilot.py']},
            report_sha256=file_hash(report), artifact_hashes={str(path.relative_to(root)): file_hash(path)
                for directory in [output, charts] for path in directory.rglob('*')
                if path.is_file() and path != output/'metadata/run_manifest.json'})
        save_json(output/'metadata/run_manifest.json', manifest)
        save_json(output/'_SUCCESS', dict(manifest_sha256=file_hash(output/'metadata/run_manifest.json')))
        print(f'VALIDADO: {len(metrics)} ajustes; informe {report.relative_to(root)}', flush=True)
        return manifest
    except Exception as error:
        manifest.update(status='failed'); manifest['errors'].append(dict(type=type(error).__name__, message=str(error)))
        save_json(output/'metadata/run_manifest.json', manifest)
        raise


def review_existing(root, output, charts, report, anchor_count=1200, n_init=10):
    """Regenera únicamente la revisión de ESTA entrega a partir de ajustes validados.

    Permite ampliar la documentación y gráficos sin volver a ajustar modelos.
    Verifica primero todos los hashes del piloto y de las fuentes protegidas.
    """
    root, output, charts, report = [Path(path).resolve() for path in [root, output, charts, report]]
    require(output.is_relative_to(root/'data/processed') and charts.is_relative_to(root/'analysis/charts') and
        report.is_relative_to(root/'analysis/reports'), 'Destinos fuera del área autorizada.')
    manifest_path = output/'metadata/run_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(manifest.get('configuration', {}).get('features') == FEATURES and manifest['status'] == 'validated',
        'Este destino no es un piloto B validado.')
    require(json.loads((output/'_SUCCESS').read_text(encoding='utf-8'))['manifest_sha256'] == file_hash(manifest_path), 'Marcador inválido.')
    require(file_hash(report) == manifest['report_sha256'], 'El informe no coincide con el piloto indicado.')
    for relative, digest in manifest['artifact_hashes'].items():
        require(file_hash(root/relative) == digest, f'Derivado del piloto alterado: {relative}')
    for path, digest in manifest['protected_hashes'].items():
        require(file_hash(path) == digest, f'Fuente protegida alterada: {path}')
    coverage = pd.read_csv(output/'metadata/coverage.csv')
    metrics = pd.read_csv(output/'metadata/model_metrics.csv')
    stability = pd.read_csv(output/'metadata/seed_stability.csv')
    elbows = pd.read_csv(output/'metadata/elbow_candidates.csv')
    comparisons = pd.read_csv(output/'metadata/partition_comparisons.csv')
    weights = pd.read_csv(output/'metadata/weight_review.csv')
    contexts, baselines = {}, {}
    for item in coverage.to_dict('records'):
        context_id = item['context_id']; folder = output/'contexts'/context_id
        full = pd.read_parquet(folder/'metadata.parquet')
        training = full.loc[full.is_training].reset_index(drop=True)
        labels_frame = pd.read_parquet(folder/'labels.parquet')
        contexts[context_id] = dict(context_id=context_id, metadata=full, training=training,
            metrics=metrics[metrics.context_id.eq(context_id)], coverage=item,
            stability=stability[stability.context_id.eq(context_id)],
            elbows=elbows[elbows.context_id.eq(context_id)].to_dict('records'),
            labels={name: labels_frame.loc[full.is_training, name].to_numpy(dtype=int)
                    for name in labels_frame.columns if name.startswith('k')})
    for scheme in SCHEMES:
        baselines[scheme] = pd.read_csv(output/'metadata'/f'national_reference_{scheme}.csv', dtype={'SEXO': str})
    success_path = output/'_SUCCESS'
    success_path.unlink()  # Sólo el marcador verificado de esta entrega; vuelve al finalizar.
    try:
        if 'silhouette_mc_se_convention' not in manifest['configuration']:
            # Revisión numérica del factor finito del error de aproximación, sin cambiar
            # Silhouette, etiquetas, SSE o ajustes. No vuelve a calcular distancias.
            for context_id in coverage.context_id:
                path = output/'contexts'/context_id/'model_metrics.csv'
                frame = pd.read_csv(path)
                frame['silhouette_mc_se'] *= np.sqrt((frame.silhouette_reference_n-1)/frame.silhouette_reference_n)
                frame.to_csv(path, index=False, encoding='utf-8-sig')
            metrics['silhouette_mc_se'] *= np.sqrt((metrics.silhouette_reference_n-1)/metrics.silhouette_reference_n)
            metrics.to_csv(output/'metadata/model_metrics.csv', index=False, encoding='utf-8-sig')
            manifest['configuration']['silhouette_mc_se_convention'] = 'sample_sd_ddof1_times_sqrt_1_minus_m_over_n_over_sqrt_m'
            manifest.setdefault('review_notes', []).append('Error Monte Carlo de Silhouette: DE muestral ddof=1 y FPC sqrt(1−m/n). Sin cambios en modelos o métricas centrales.')
        if not (output/'metadata/candidate_profiles.csv').exists():
            supplementary_diagnostics(output, charts, contexts)
        else:
            plot_sex_summary(charts, pd.read_csv(output/'metadata/candidate_profiles.csv'))
        write_report(output, charts, report, contexts, metrics, coverage, stability, elbows, comparisons,
            weights, baselines, len(manifest['protected_hashes']), manifest['configuration']['n_init'],
            manifest['configuration']['anchor_count'])
        for path, digest in manifest['protected_hashes'].items():
            require(file_hash(path) == digest, f'Fuente modificada durante revisión: {path}')
        manifest.update(review_refreshed_at_utc=datetime.now(timezone.utc).isoformat(),
            review_script_sha256=file_hash(Path(__file__)), report_sha256=file_hash(report),
            artifact_hashes={str(path.relative_to(root)): file_hash(path) for directory in [output, charts]
                for path in directory.rglob('*') if path.is_file() and path != manifest_path})
        save_json(manifest_path, manifest)
        save_json(success_path, dict(manifest_sha256=file_hash(manifest_path)))
        print('REVISIÓN VALIDADA: sin reajustar modelos.', flush=True)
    except Exception as error:
        manifest['status'] = 'failed'; manifest['errors'].append(dict(type=type(error).__name__, message=str(error)))
        save_json(manifest_path, manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, default=Path('data/processed/demographic_pilot'))
    parser.add_argument('--charts', type=Path, default=Path('analysis/charts/demographic_pilot'))
    parser.add_argument('--report', type=Path, default=Path('analysis/reports/demographic_pilot.md'))
    parser.add_argument('--anchor-count', type=int, default=1200)
    parser.add_argument('--n-init', type=int, default=10)
    parser.add_argument('--review-existing', action='store_true', help='Revisar sólo los resultados B verificados de esta entrega, sin reajustar.')
    args = parser.parse_args()
    root = args.root.resolve()
    runner = review_existing if args.review_existing else run_pilot
    runner(root, *[p if p.is_absolute() else root/p for p in [args.output, args.charts, args.report]],
        anchor_count=args.anchor_count, n_init=args.n_init)


if __name__ == '__main__':
    main()
