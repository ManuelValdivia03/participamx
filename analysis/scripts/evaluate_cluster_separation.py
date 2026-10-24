"""Separación geométrica, Silhouette exacto por bloques, codo y remuestras previas.

Sólo deriva nuevos artefactos de life_stage/2024. No altera fuentes o modelos
anteriores ni ejecuta otros algoritmos de agrupamiento.
"""
from __future__ import annotations

import os
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
from build_cluster_features import save_table, snapshot_inputs
from build_descriptive import METRICS, markdown_table, number, pct
from clustering_core import adjusted_rand, geometric_elbow, transform
from compare_demographic_features import (FEATURE_SETS, KEYS, MUNICIPAL_KEYS, SEEDS,
    initialization_bank, fit_bank, diagnostics, predict, nullable_labels, source_validation)
from run_demographic_pilot import anchor_sample, anchor_distances, sampled_metrics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter

KS = list(range(2, 11))
MAIN_KS = [4, 5]
MARGIN_LIMIT = .10
SILHOUETTE_LIMIT = .10
PALETTE = [plt.get_cmap('tab10')(index) for index in range(10)]


def silhouette_blocks(values, partitions, block_size=128, progress=False):
    """Silhouette individual exacto de varias particiones; distancias B×N, no N×N.

    Reutiliza el mismo bloque para todos los K. La multiplicación por indicadores
    de grupos obtiene las sumas de distancias sin copiar submatrices por cluster.
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    require(block_size > 0 and np.isfinite(values).all(), 'Bloque/valores no válidos.')
    indicators, encodings, counts, slices = [], {}, {}, {}
    offset = 0
    for name, labels in partitions.items():
        require(len(labels) == n, 'Partición no alineada para Silhouette.')
        _, encoded = np.unique(labels, return_inverse=True)
        k = encoded.max()+1
        require(2 <= k < n, 'Silhouette requiere 2…n−1 grupos.')
        encodings[name] = encoded
        counts[name] = np.bincount(encoded)
        indicators.append(np.eye(k)[encoded])
        slices[name] = slice(offset, offset+k)
        offset += k
    group_indicators = np.ascontiguousarray(np.column_stack(indicators))
    result = {name: np.empty(n) for name in partitions}
    # Incluso si B>=N por argumento, para N>2 se limita a N−1 filas.
    block_size = min(block_size, n-1)
    for start in range(0, n, block_size):
        stop = min(n, start+block_size)
        indices = np.arange(start, stop)
        distances = anchor_distances(values, indices, block_size)
        sums = distances@group_indicators
        for name in partitions:
            encoded = encodings[name]
            sizes = counts[name]
            own_groups = encoded[start:stop]
            means = sums[:, slices[name]]/sizes
            own = sums[:, slices[name]][np.arange(stop-start), own_groups]/np.maximum(1, sizes[own_groups]-1)
            means[np.arange(stop-start), own_groups] = np.inf
            other = means.min(axis=1)
            denominator = np.maximum(own, other)
            scores = np.divide(other-own, denominator, out=np.zeros(stop-start), where=denominator > 0)
            scores[sizes[own_groups] == 1] = 0.
            result[name][start:stop] = scores
        if progress and (start == 0 or stop == n or start//block_size % 40 == 0):
            print(f'Silhouette exacto: {stop:,}/{n:,} puntos; bloque {len(indices)}×{n:,}.', flush=True)
    for scores in result.values():
        require(np.isfinite(scores).all() and (np.abs(scores) <= 1+1e-12).all(), 'Silhouette fuera de dominio.')
    return result


def centroid_proximity(values, centers):
    """Margen (d2−d1)/d2; no es probabilidad, confianza o error de clasificación."""
    _, squared = predict(np.asarray(values), np.asarray(centers))
    order = np.argsort(squared, axis=1, kind='stable')
    first, second = order[:, 0], order[:, 1]
    distances = np.sqrt(squared)
    d1, d2 = distances[np.arange(len(values)), first], distances[np.arange(len(values)), second]
    margin = np.divide(d2-d1, d2, out=np.full(len(values), np.nan), where=d2 > 0)
    return pd.DataFrame(dict(nearest_cluster=first, second_cluster=second, nearest_distance=d1,
        second_distance=d2, normalized_margin=margin,
        centroid_tie=np.isclose(d1, d2, rtol=1e-12, atol=1e-14)))


def decision_edges(centers, bounds, axis_scale=None, offset=None):
    """Bisectrices verdaderas recortadas por todas las celdas y el rectángulo.

    Admite x_métrica=axis_scale*x_gráfico+offset. Así se muestran las fronteras
    de una remuestra con su métrica propia en los ejes comunes del principal.
    No se interpola un mapa de etiquetas ordinales para inventar contornos.
    """
    centers = np.asarray(centers, dtype=float)
    axis_scale = np.ones(2) if axis_scale is None else np.asarray(axis_scale)
    offset = np.zeros(2) if offset is None else np.asarray(offset)
    xmin, xmax, ymin, ymax = bounds
    result = []
    for left, right in combinations(range(len(centers)), 2):
        normal_metric = 2*(centers[right]-centers[left])
        normal = normal_metric*axis_scale
        rhs = np.dot(centers[right], centers[right])-np.dot(centers[left], centers[left])-np.dot(normal_metric, offset)
        if np.dot(normal, normal) <= 1e-24: continue
        point = normal*rhs/np.dot(normal, normal)
        direction = np.array([-normal[1], normal[0]])/np.linalg.norm(normal)
        constraints = [(np.array([1., 0.]), xmax), (np.array([-1., 0.]), -xmin),
            (np.array([0., 1.]), ymax), (np.array([0., -1.]), -ymin)]
        for other in range(len(centers)):
            if other in [left, right]: continue
            metric = 2*(centers[other]-centers[left])
            constraints.append((metric*axis_scale, np.dot(centers[other], centers[other])-
                np.dot(centers[left], centers[left])-np.dot(metric, offset)))
        low, high = -np.inf, np.inf
        for coefficient, bound in constraints:
            slope, remaining = float(np.dot(coefficient, direction)), float(bound-np.dot(coefficient, point))
            if abs(slope) < 1e-12:
                if remaining < -1e-10: high = -np.inf; break
            elif slope > 0: high = min(high, remaining/slope)
            else: low = max(low, remaining/slope)
        if np.isfinite(low) and np.isfinite(high) and high-low > 1e-10:
            a, b = point+low*direction, point+high*direction
            result.append(dict(left_cluster=left, right_cluster=right, x1=float(a[0]), y1=float(a[1]), x2=float(b[0]), y2=float(b[1])))
    return result


def align_partition(reference, candidate, k):
    """Máximo solapamiento exacto; devuelve candidatos alineados, no cambia modelos."""
    reference, candidate = np.asarray(reference, dtype=int), np.asarray(candidate, dtype=int)
    require(len(reference) == len(candidate) and len(reference) > 0, 'Alineación sin población común.')
    counts = np.zeros((k, k), dtype=int)
    np.add.at(counts, (reference, candidate), 1)
    states = {0: (0, [])}
    for mask in range(1 << k):
        if mask not in states: continue
        score, chosen = states[mask]
        row = len(chosen)
        if row == k: continue
        for column in range(k):
            if mask & (1 << column): continue
            next_mask = mask | (1 << column)
            new_score = score+int(counts[row, column])
            if next_mask not in states or new_score > states[next_mask][0]:
                states[next_mask] = (new_score, chosen+[column])
    chosen = states[(1 << k)-1][1]
    mapping = np.empty(k, dtype=int)
    for ref, cand in enumerate(chosen): mapping[cand] = ref
    return mapping[candidate], mapping


def recover_centers(values, labels, k):
    """Recupera medias de entrenamiento ya asignado; no reoptimiza ni hace clustering."""
    counts = np.bincount(labels, minlength=k)
    require((counts > 0).all(), 'Remuestra con cluster vacío.')
    return np.column_stack([np.bincount(labels, weights=values[:, column], minlength=k)/counts for column in range(2)])


def centers_in_common_scale(centers, sample_scaler, global_scaler):
    raw = centers*np.asarray(sample_scaler['scale'])+np.asarray(sample_scaler['location'])
    return transform(raw, global_scaler), raw


def relative_bands(values):
    return pd.cut(values, [-np.inf, -.20, -.10, 0., .10, .20, np.inf], right=False,
        labels=['below_minus_20pp', 'minus_20_to_minus_10pp', 'minus_10_to_zero', 'zero_to_10pp', '10_to_20pp', 'at_least_20pp']).astype(str)


def fit_curve(full, mask, matrices, source, output, anchor_count=1200, n_init=10):
    """Repite K=2…10 y verifica K=4/5/6 contra el experimento anterior."""
    previous = pd.read_csv(source/'metadata/model_metrics.csv')
    resamples = pd.read_csv(source/'metadata/resample_metrics.csv')
    contexts = {representation: {} for representation in FEATURE_SETS}
    rows, initializations, stability, checks = [], [], [], []
    anchors = anchor_sample(full.loc[mask, 'row_id'], anchor_count)
    save_table(output/'metadata/silhouette_anchors.parquet', full.loc[mask].iloc[anchors][['row_id', *KEYS]])
    banks = {(k, seed): initialization_bank(matrices, k, seed, n_init) for k in KS for seed in SEEDS}
    for representation in FEATURE_SETS:
        values = matrices[representation]
        distances = anchor_distances(values, anchors)
        folder = output/'curve'/representation
        labels_frame = full[['row_id', *KEYS]].copy()
        center_rows = []
        previous_folder = source/'contexts'/f'life_stage_{representation}_equal_segment_main'
        previous_labels = pd.read_parquet(previous_folder/'labels.parquet')
        require(previous_labels.row_id.equals(full.row_id), 'Etiquetas previas no alineadas.')
        for k in KS:
            for seed in SEEDS:
                fitted = fit_bank(values, np.ones(len(values)), banks[k, seed])
                metrics = sampled_metrics(values, fitted['labels'], anchors, distances)
                rows.append(dict(representation=representation, k=k, seed=seed, sse=fitted['inertia'], n=len(values),
                    converged=fitted['converged'], iterations=fitted['iterations'],
                    minimum_cluster=int(np.bincount(fitted['labels'], minlength=k).min()), **metrics))
                contexts[representation][k, seed] = fitted
                labels_frame[f'k{k:02d}_seed{seed}'] = nullable_labels(full, mask, fitted['labels'])
                initializations.extend(dict(representation=representation, k=k, seed=seed, **record)
                    for record in fitted['initializations'])
                for group, center in enumerate(fitted['centers']):
                    center_rows.append(dict(k=k, seed=seed, cluster=group, standardized_age=center[0], standardized_value=center[1]))
                if k in [4, 5, 6]:
                    old = previous[(previous.context_id.eq(previous_folder.name)) & previous.k.eq(k) & previous.seed.eq(seed)].iloc[0]
                    ari = adjusted_rand(previous_labels.loc[mask, f'k{k:02d}_seed{seed}'].to_numpy(dtype=int), fitted['labels'])
                    difference = fitted['inertia']-old.sse_weighted
                    require(ari > 1-1e-12 and np.isclose(difference, 0., atol=1e-7), 'No se reprodujo el experimento anterior.')
                    same_anchor_count = len(anchors) == int(old.silhouette_evaluation_n)
                    if same_anchor_count:
                        require(np.isclose(metrics['silhouette'], old.silhouette, atol=1e-11), 'Cambió Silhouette de las mismas anclas.')
                    checks.append(dict(representation=representation, k=k, seed=seed, ari=ari, sse_difference=difference,
                        anchor_silhouette_difference=metrics['silhouette']-old.silhouette,
                        same_anchor_count=same_anchor_count))
            for left, right in combinations(SEEDS, 2):
                stability.append(dict(representation=representation, k=k, left_seed=left, right_seed=right,
                    ari=adjusted_rand(contexts[representation][k, left]['labels'], contexts[representation][k, right]['labels'])))
            print(f'{representation}: K={k}, tres semillas × {n_init} arranques reproducidos.', flush=True)
        del distances
        save_table(folder/'labels.parquet', labels_frame)
        save_table(folder/'centroids.csv', pd.DataFrame(center_rows))
    best = {}
    for representation in FEATURE_SETS:
        for k in KS:
            seed = min(SEEDS, key=lambda seed: contexts[representation][k, seed]['inertia'])
            if k in [4, 5, 6]:
                candidates = resamples[(resamples.scheme.eq('life_stage')) & resamples.representation.eq(representation)
                    & resamples.weighting.eq('equal_segment') & resamples.k.eq(k)].baseline_seed.unique()
                require(len(candidates) == 1, 'Referencia de remuestreo ambigua.')
                original_seed = int(candidates[0])
                require(np.isclose(contexts[representation][k, original_seed]['inertia'], contexts[representation][k, seed]['inertia'], atol=1e-7), 'La referencia anterior dejó de minimizar SSE.')
                seed = original_seed  # Desempate/benchmark anterior, sin cambiar partición.
            best[representation, k] = dict(contexts[representation][k, seed], seed=seed)
    return best, pd.DataFrame(rows), pd.DataFrame(initializations), pd.DataFrame(stability), pd.DataFrame(checks)


def separation_table(training, values, fitted, silhouette):
    frame = training.copy().reset_index(drop=True)
    labels = fitted['labels']
    frame['cluster'] = labels
    frame['silhouette'] = silhouette
    proximity = centroid_proximity(values, fitted['centers'])
    require(np.array_equal(proximity.nearest_cluster, labels), 'Etiqueta distinta del centroide más cercano.')
    for column in proximity: frame[column] = proximity[column].to_numpy()
    frame['negative_silhouette'] = frame.silhouette.lt(0)
    frame['weak_silhouette'] = frame.silhouette.between(0, SILHOUETTE_LIMIT, inclusive='both')
    frame['low_margin'] = frame.normalized_margin.le(MARGIN_LIMIT)
    frame['relative_rate_band'] = relative_bands(frame.participation_deviation_national)
    summary = frame.groupby('cluster', as_index=False).agg(observations=('row_id', 'size'),
        LN=('LN', 'sum'), SV=('SV', 'sum'), NV=('NV', 'sum'), NS=('NS', 'sum'),
        silhouette_mean=('silhouette', 'mean'), negative_count=('negative_silhouette', 'sum'),
        weak_count=('weak_silhouette', 'sum'), low_margin_count=('low_margin', 'sum'),
        margin_mean=('normalized_margin', 'mean'), margin_q10=('normalized_margin', lambda v: v.quantile(.1)),
        margin_median=('normalized_margin', 'median'), margin_q90=('normalized_margin', lambda v: v.quantile(.9)))
    for column in ['negative', 'weak', 'low_margin']:
        summary[column+'_fraction'] = summary[column+'_count']/summary.observations
    groups = frame.groupby(['age_band', 'SEXO', 'relative_rate_band'], as_index=False, observed=True).agg(
        observations=('row_id', 'size'), LN=('LN', 'sum'), low_margin_count=('low_margin', 'sum'),
        negative_count=('negative_silhouette', 'sum'), weak_count=('weak_silhouette', 'sum'))
    groups['low_margin_fraction'] = groups.low_margin_count/groups.observations
    groups['share_of_all_low_margin'] = groups.low_margin_count/max(1, frame.low_margin.sum())
    model_summary = dict(n=len(frame), LN=int(frame.LN.sum()), silhouette_exact=float(silhouette.mean()),
        negative_count=int(frame.negative_silhouette.sum()), negative_fraction=float(frame.negative_silhouette.mean()),
        weak_count=int(frame.weak_silhouette.sum()), weak_fraction=float(frame.weak_silhouette.mean()),
        low_margin_count=int(frame.low_margin.sum()), low_margin_fraction=float(frame.low_margin.mean()),
        negative_and_low_margin=int((frame.negative_silhouette & frame.low_margin).sum()),
        margin_median=float(frame.normalized_margin.median()),
        maximum_negative_cluster_fraction=float(summary.negative_fraction.max()))
    return frame, summary, groups, model_summary


def plot_bounds(values):
    lower, upper = values.min(axis=0), values.max(axis=0)
    padding = .05*np.maximum(upper-lower, 1.)
    return [lower[0]-padding[0], upper[0]+padding[0], lower[1]-padding[1], upper[1]+padding[1]]


def draw_edges(ax, edges, **style):
    for row in edges: ax.plot([row['x1'], row['x2']], [row['y1'], row['y2']], **style)


def plot_geometry(values, fitted, representation, k, charts, output):
    centers, labels = fitted['centers'], fitted['labels']
    bounds = plot_bounds(values)
    xx, yy = np.meshgrid(np.linspace(bounds[0], bounds[1], 320), np.linspace(bounds[2], bounds[3], 320))
    z, _ = predict(np.column_stack([xx.ravel(), yy.ravel()]), centers)
    fig, ax = plt.subplots(figsize=(10, 9), layout='constrained')
    ax.pcolormesh(xx, yy, z.reshape(xx.shape), shading='nearest', cmap=ListedColormap(PALETTE[:k]),
        norm=BoundaryNorm(np.arange(-.5, k+.5), k), alpha=.10, rasterized=True)
    ax.scatter(values[:, 0], values[:, 1], c=labels, cmap=ListedColormap(PALETTE[:k]),
        norm=BoundaryNorm(np.arange(-.5, k+.5), k), s=5, alpha=.25, rasterized=True)
    edges = decision_edges(centers, bounds)
    draw_edges(ax, edges, color='black', lw=1.1)
    ax.scatter(centers[:, 0], centers[:, 1], c=PALETTE[:k], marker='X', s=200, edgecolors='black', linewidths=1.4, zorder=4)
    for group, center in enumerate(centers): ax.annotate(f'c{group}', center, xytext=(6, 8), textcoords='offset points', weight='bold')
    counts = np.bincount(labels, minlength=k)
    handles = [Line2D([0], [0], marker='o', ls='None', color=PALETTE[group], label=f'c{group}: n={counts[group]:,}') for group in range(k)]
    handles.append(Line2D([0], [0], marker='X', ls='None', color='white', markeredgecolor='black', markersize=10, label='Centroide'))
    ax.legend(handles=handles, fontsize=8)
    ax.set(xlim=bounds[:2], ylim=bounds[2:], xlabel='Edad media nominal estandarizada (z)',
        ylabel=('Participación observada' if representation == 'absolute' else 'Diferencia nacional de intervalo/sexo')+' estandarizada (z)')
    ax.set_aspect('equal', adjustable='box')
    ax.set_title(f'{"A absoluta" if representation == "absolute" else "B relativa"} · K={k} · equal_segment · 2024\n'
        f'Semilla {fitted["seed"]}; todos los {len(values):,} segmentos, sin jitter\nFronteras analíticas; sombreado indica centroide más cercano, no probabilidad')
    fig.savefig(charts/f'{representation}_k{k:02d}_standardized_geometry.png', dpi=170); plt.close(fig)
    save_table(output/'models'/f'{representation}_k{k:02d}'/'decision_edges.csv', pd.DataFrame(edges))


def plot_silhouette(frame, representation, k, charts):
    fig, ax = plt.subplots(figsize=(10, 7), layout='constrained')
    lower = 10; ticks = []
    for group in range(k):
        scores = np.sort(frame.loc[frame.cluster.eq(group), 'silhouette'].to_numpy())
        upper = lower+len(scores)
        ax.fill_betweenx(np.arange(lower, upper), 0, scores, color=PALETTE[group], alpha=.75)
        ticks.append(((lower+upper)/2, f'c{group} · n={len(scores):,} · media={scores.mean():.3f}'))
        lower = upper+100
    ax.axvline(frame.silhouette.mean(), color='red', ls='--', label=f'Media exacta={frame.silhouette.mean():.4f}')
    ax.axvline(0, color='black', lw=.8); ax.axvline(SILHOUETTE_LIMIT, color='gray', ls=':', label='0.10: advertencia descriptiva')
    ax.set_yticks([item[0] for item in ticks], [item[1] for item in ticks]); ax.set_xlabel('Silhouette individual exacto')
    ax.set_xlim(min(-.25, frame.silhouette.min()-.02), 1.); ax.legend()
    ax.set_title(f'{representation} · K={k} · equal_segment\nCálculo de toda la población por bloques; orden interno sin significado demográfico')
    fig.savefig(charts/f'{representation}_k{k:02d}_silhouette.png', dpi=170); plt.close(fig)


def plot_margins(frames, charts):
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), layout='constrained')
    fig2, axes2 = plt.subplots(2, 2, figsize=(13, 9), layout='constrained')
    for ax, bx, ((representation, k), frame) in zip(axes.ravel(), axes2.ravel(), frames.items()):
        ax.hist(frame.normalized_margin, bins=np.linspace(0, 1, 41), color='#386cb0', alpha=.8)
        ax.axvline(MARGIN_LIMIT, color='red', ls='--'); ax.set_xlabel('Margen (d2−d1)/d2'); ax.set_ylabel('Segmentos')
        bx.boxplot([frame.loc[frame.cluster.eq(group), 'normalized_margin'] for group in range(k)],
            tick_labels=[f'c{group}' for group in range(k)], showfliers=True, flierprops=dict(markersize=2, alpha=.3))
        bx.axhline(MARGIN_LIMIT, color='red', ls='--'); bx.set_ylabel('Margen normalizado'); bx.set_ylim(0, 1.02)
        for axis in [ax, bx]: axis.set_title(f'{representation} · K={k} · equal_segment')
    fig.suptitle('Proximidad a fronteras: geométrica, sin interpretación probabilística')
    fig2.suptitle('Distribución de márgenes por cluster · todas las observaciones elegibles')
    fig.savefig(charts/'margin_histograms.png', dpi=160); fig2.savefig(charts/'margin_by_cluster.png', dpi=160)
    plt.close(fig); plt.close(fig2)


def plot_curve(metrics, best_metrics, elbow_choices, stability, charts):
    fig, axes = plt.subplots(2, 3, figsize=(15, 9), layout='constrained')
    for row, representation in enumerate(FEATURE_SETS):
        selected = metrics[metrics.representation.eq(representation)]
        best = best_metrics[best_metrics.representation.eq(representation)].sort_values('k')
        for seed, group in selected.groupby('seed'):
            axes[row, 0].plot(group.k, group.sse, alpha=.35, label=f'semilla {seed}')
        axes[row, 0].plot(best.k, best.sse, 'ko-', label='Menor SSE entre semillas')
        for choice in elbow_choices:
            if choice['representation'] == representation and choice['curve'] == 'best_across_seeds' and choice['axis_mode'] in ['raw', 'unit_axes'] and choice['selected_k'] is not None:
                axes[row, 0].axvline(choice['selected_k'], ls='--' if choice['axis_mode'] == 'raw' else ':', label=f'{choice["axis_mode"]}: K={choice["selected_k"]}')
        axes[row, 0].legend(fontsize=7); axes[row, 0].set_ylabel('SSE · su propia geometría')
        axes[row, 1].bar(best.k, best.reduction_fraction); axes[row, 1].yaxis.set_major_formatter(PercentFormatter(1))
        axes[row, 1].set_ylabel('Reducción frente a K−1 (K=2 no definida)')
        axes[row, 2].plot(best.k, best.silhouette_exact, 'o-', label='Silhouette exacto del mejor SSE')
        axes[row, 2].set_ylabel('Silhouette exacto')
        twin = axes[row, 2].twinx(); twin.plot(best.k, best.davies_bouldin, 's--', color='#d95f02', label='DB exacto')
        twin.set_ylabel('Davies–Bouldin exacto'); axes[row, 2].legend(loc='upper left', fontsize=7); twin.legend(loc='upper right', fontsize=7)
        for ax in axes[row]: ax.set_xlabel('K'); ax.set_xticks(KS); ax.set_title(representation); ax.grid(alpha=.2)
    fig.suptitle('Codo actualizado · misma población, equal_segment, StandardScaler fijo\nLos ángulos dependen de los ejes; no se compara SSE entre A/B')
    fig.savefig(charts/'elbow_and_metrics.png', dpi=160); plt.close(fig)


def instability_cases(full, mask, scalers, source, diagnostic_frames, output, charts, worst_count=3):
    """Reutiliza remuestras, reconstruye centroides y compara OOB y todos por separado."""
    raw = full.loc[mask].reset_index(drop=True)
    previous = pd.read_csv(source/'metadata/resample_metrics.csv')
    rankings, summaries, impacts, demographics, shifts, associations = [], [], [], [], [], []
    plot_cases = []
    for representation, k in [('relative', 4), ('relative', 5), ('absolute', 5)]:
        records = previous[previous.scheme.eq('life_stage') & previous.representation.eq(representation)
            & previous.weighting.eq('equal_segment') & previous.k.eq(k)].sort_values(['ari_oob', 'replicate'])
        require(len(records) == 30, 'No hay 30 remuestras previas comparables.')
        rankings.extend(dict(rank=index+1, **item) for index, item in enumerate(records.to_dict('records')))
        old_folder = source/'contexts'/f'life_stage_{representation}_equal_segment_main'
        old_labels = pd.read_parquet(old_folder/'labels.parquet')
        old_centers = pd.read_csv(old_folder/'centroids.csv')
        require(old_labels.row_id.equals(full.row_id), 'Referencias municipales no alineadas.')
        global_scaler = scalers[representation]
        global_values = transform(raw[FEATURE_SETS[representation]].to_numpy(), global_scaler)
        for position, record in enumerate(records.head(worst_count).itertuples()):
            replicate = int(record.replicate)
            baseline = old_labels.loc[mask, f'k{k:02d}_seed{record.baseline_seed}'].to_numpy(dtype=int)
            baseline_centers = old_centers[old_centers.k.eq(k) & old_centers.seed.eq(record.baseline_seed)].sort_values('cluster')[['scaled_age', 'scaled_value']].to_numpy()
            sample_folder = source/'resampling/life_stage'/f'sample_{replicate:03d}'
            sample = pd.read_parquet(sample_folder/'labels.parquet')
            require(sample.row_id.equals(full.row_id), 'Remuestra no alineada.')
            inbag = sample.loc[mask, 'is_training'].to_numpy()
            oob = sample.loc[mask, 'is_oob_eligible'].to_numpy()
            require(np.array_equal(~inbag, oob), 'OOB no complementa el entrenamiento elegible.')
            candidate = sample.loc[mask, f'{representation}_equal_segment_k{k}'].to_numpy(dtype=int)
            sample_scaler = json.loads((sample_folder/'scalers.json').read_text())[representation]
            sample_values = transform(raw[FEATURE_SETS[representation]].to_numpy(), sample_scaler)
            centers = recover_centers(sample_values[inbag], candidate[inbag], k)
            projected, squared = predict(sample_values, centers)
            proximity = centroid_proximity(sample_values, centers)
            mismatches = projected != candidate
            require((~mismatches | proximity.centroid_tie.to_numpy()).all(), 'Centroides recuperados no reproducen etiquetas.')
            sse = float(squared[np.flatnonzero(inbag), candidate[inbag]].sum())
            require(np.isclose(sse, record.sse_weighted, rtol=1e-10, atol=1e-7), 'No se recuperó SSE de remuestra.')
            common_centers, raw_centers = centers_in_common_scale(centers, sample_scaler, global_scaler)
            base_proximity = centroid_proximity(global_values, baseline_centers)
            require(adjusted_rand(baseline, diagnostic_frames[representation, k].cluster) > 1-1e-12, 'Base diagnóstica no equivale al benchmark municipal.')
            case_id = f'{representation}_k{k:02d}_sample_{replicate:03d}'
            folder = output/'instability'/case_id
            individual = raw.copy()
            individual['baseline_cluster'] = baseline
            individual['sample_cluster'] = candidate
            individual['is_oob'] = oob
            individual['baseline_margin'] = base_proximity.normalized_margin.to_numpy()
            individual['baseline_low_margin'] = individual.baseline_margin.le(MARGIN_LIMIT)
            for scope, scope_mask in [('oob', oob), ('all_eligible', np.ones(len(raw), dtype=bool))]:
                aligned, mapping = align_partition(baseline[scope_mask], candidate[scope_mask], k)
                changed = aligned != baseline[scope_mask]
                original = baseline[scope_mask]
                individual[f'aligned_{scope}'] = nullable_labels(raw, scope_mask, aligned)
                changed_column = pd.array([pd.NA]*len(raw), dtype='boolean')
                changed_column[scope_mask] = changed
                individual[f'changed_{scope}'] = changed_column
                ari = adjusted_rand(original, aligned)
                expected = record.ari_oob if scope == 'oob' else record.ari_all_eligible
                require(np.isclose(ari, expected, atol=1e-12), 'ARI recuperado distinto del anterior.')
                if scope == 'oob': require(np.isclose(changed.mean(), record.changed_fraction_oob, atol=1e-12), 'Alineación OOB no reproduce cambios previos.')
                margins = base_proximity.normalized_margin.to_numpy()[scope_mask]
                summaries.append(dict(case_id=case_id, representation=representation, k=k, replicate=replicate,
                    scope=scope, n=int(scope_mask.sum()), baseline_seed=int(record.baseline_seed), ari=ari,
                    changed_count=int(changed.sum()), changed_fraction=float(changed.mean()),
                    changed_low_margin_fraction=float((margins[changed] <= MARGIN_LIMIT).mean()) if changed.any() else np.nan,
                    unchanged_low_margin_fraction=float((margins[~changed] <= MARGIN_LIMIT).mean()) if (~changed).any() else np.nan,
                    changed_median_margin=float(np.median(margins[changed])) if changed.any() else np.nan,
                    unchanged_median_margin=float(np.median(margins[~changed])) if (~changed).any() else np.nan,
                    maximum_centroid_shift_common_z=float(np.linalg.norm(common_centers-np.asarray([baseline_centers[mapping[c]] for c in range(k)]), axis=1).max()),
                    recovered_sse_difference=sse-record.sse_weighted, boundary_tie_disagreements=int(mismatches.sum())))
                transition = pd.DataFrame(dict(from_cluster=original, to_cluster=aligned))
                transition['LN'] = raw.loc[scope_mask, 'LN'].to_numpy()
                transition = transition.groupby(['from_cluster', 'to_cluster'], as_index=False).agg(observations=('LN', 'size'), LN=('LN', 'sum'))
                transition.insert(0, 'scope', scope); transition.insert(0, 'case_id', case_id)
                save_table(folder/f'transition_{scope}.csv', transition)
                for group in range(k):
                    before, after = original == group, aligned == group
                    same = before & after
                    impacts.append(dict(case_id=case_id, scope=scope, cluster=group,
                        before_n=int(before.sum()), after_n=int(after.sum()), unchanged_n=int(same.sum()),
                        outgoing_n=int((before & ~after).sum()), incoming_n=int((after & ~before).sum()),
                        outgoing_fraction=float((before & ~after).sum()/before.sum()) if before.any() else np.nan,
                        jaccard=float(same.sum()/(before | after).sum()) if (before | after).any() else np.nan))
                frame = raw.loc[scope_mask, ['age_band', 'SEXO', 'participation_deviation_national', 'LN']].copy()
                frame['relative_rate_band'] = relative_bands(frame.participation_deviation_national)
                frame['changed'] = changed; frame['baseline_low_margin'] = margins <= MARGIN_LIMIT
                groups = frame.groupby(['age_band', 'SEXO', 'relative_rate_band'], as_index=False, observed=True).agg(
                    observations=('changed', 'size'), changed_count=('changed', 'sum'), LN=('LN', 'sum'))
                groups['changed_fraction'] = groups.changed_count/groups.observations
                groups.insert(0, 'scope', scope); groups.insert(0, 'case_id', case_id)
                demographics.append(groups)
                for low, part in frame.groupby('baseline_low_margin'):
                    associations.append(dict(case_id=case_id, scope=scope, baseline_low_margin=bool(low),
                        observations=len(part), changed_count=int(part.changed.sum()), changed_fraction=float(part.changed.mean())))
                for candidate_group in range(k):
                    reference_group = mapping[candidate_group]
                    baseline_raw = baseline_centers[reference_group]*np.asarray(global_scaler['scale'])+np.asarray(global_scaler['location'])
                    shifts.append(dict(case_id=case_id, scope=scope, reference_cluster=int(reference_group), sample_cluster=candidate_group,
                        age_shift_years=float(raw_centers[candidate_group, 0]-baseline_raw[0]),
                        value_shift_pp=float(100*(raw_centers[candidate_group, 1]-baseline_raw[1])),
                        centroid_shift_common_z=float(np.linalg.norm(common_centers[candidate_group]-baseline_centers[reference_group]))))
            save_table(folder/'segment_changes.parquet', individual)
            save_json(folder/'recovered_centers.json', dict(sample_scaler=sample_scaler, global_scaler=global_scaler,
                sample_centers_z=centers.tolist(), sample_centers_common_z=common_centers.tolist(), baseline_centers_z=baseline_centers.tolist(),
                recovered_by='arithmetic_means_of_saved_training_labels_not_refitting'))
            if position == 0:
                plot_cases.append(dict(case_id=case_id, representation=representation, k=k, values=global_values,
                    baseline_centers=baseline_centers, sample_centers=centers, sample_centers_common=common_centers,
                    sample_scaler=sample_scaler, global_scaler=global_scaler, baseline=baseline, candidate=candidate, oob=oob,
                    baseline_margin=base_proximity.normalized_margin.to_numpy()))
    tables = dict(instability_ranking=pd.DataFrame(rankings), instability_summary=pd.DataFrame(summaries),
        cluster_impacts=pd.DataFrame(impacts), change_demographics=pd.concat(demographics, ignore_index=True),
        centroid_shifts=pd.DataFrame(shifts), margin_change_associations=pd.DataFrame(associations))
    for name, frame in tables.items(): save_table(output/'metadata'/f'{name}.csv', frame)
    plot_instability(plot_cases, charts)
    return tables


def plot_instability(cases, charts):
    fig, axes = plt.subplots(len(cases), 3, figsize=(16, 5*len(cases)), layout='constrained')
    for row, case in enumerate(cases):
        values, k, oob = case['values'], case['k'], case['oob']
        aligned, mapping = align_partition(case['baseline'][oob], case['candidate'][oob], k)
        changed = aligned != case['baseline'][oob]
        bounds = plot_bounds(values)
        ax = axes[row, 0]
        ax.scatter(values[oob, 0], values[oob, 1], c='#bdbdbd', s=4, alpha=.25)
        ax.scatter(values[oob][changed, 0], values[oob][changed, 1], c='#d95f02', s=7, alpha=.6, label='Cambio OOB alineado')
        draw_edges(ax, decision_edges(case['baseline_centers'], bounds), color='black', lw=.9)
        axis_scale = np.asarray(case['global_scaler']['scale'])/np.asarray(case['sample_scaler']['scale'])
        offset = (np.asarray(case['global_scaler']['location'])-np.asarray(case['sample_scaler']['location']))/np.asarray(case['sample_scaler']['scale'])
        draw_edges(ax, decision_edges(case['sample_centers'], bounds, axis_scale, offset), color='#386cb0', ls='--', lw=.9)
        ax.scatter(*case['baseline_centers'].T, marker='X', c='black', s=65, label='Centroides principal')
        ax.scatter(*case['sample_centers_common'].T, marker='D', facecolors='none', edgecolors='#386cb0', s=65, label='Centroides remuestra')
        ax.set(xlim=bounds[:2], ylim=bounds[2:], xlabel='Edad z del principal', ylabel='Valor z del principal')
        ax.set_aspect('equal', adjustable='box'); ax.legend(fontsize=6)
        ax.set_title(case['case_id']+'\nFronteras: principal sólidas, remuestra discontinuas')
        ax = axes[row, 1]
        margins = case['baseline_margin'][oob]
        ax.hist(margins[~changed], bins=np.linspace(0, 1, 26), density=True, histtype='step', label='Sin cambio OOB')
        if changed.any(): ax.hist(margins[changed], bins=np.linspace(0, 1, 26), density=True, histtype='step', label='Cambio OOB')
        ax.axvline(MARGIN_LIMIT, color='black', ls=':'); ax.set_xlabel('Margen del modelo principal'); ax.set_ylabel('Densidad por grupo'); ax.legend(fontsize=8)
        ax.set_title('Asociación descriptiva entre margen y cambio')
        ax = axes[row, 2]
        counts = np.zeros((k, k), dtype=int)
        np.add.at(counts, (case['baseline'][oob], aligned), 1)
        proportions = counts/np.maximum(1, counts.sum(axis=1)[:, None])
        ax.imshow(proportions, cmap='Blues', vmin=0, vmax=1)
        for i in range(k):
            for j in range(k): ax.text(j, i, f'{counts[i,j]}\n{proportions[i,j]:.0%}', ha='center', va='center', fontsize=8,
                color='white' if proportions[i,j] > .6 else 'black')
        ax.set_xticks(range(k), [f'c{i}' for i in range(k)]); ax.set_yticks(range(k), [f'c{i}' for i in range(k)])
        ax.set_xlabel('Remuestra alineada por solapamiento OOB'); ax.set_ylabel('Principal'); ax.set_title('Transiciones únicamente OOB')
    fig.suptitle('Peor remuestra OOB de cada candidato · no son comparaciones causales')
    fig.savefig(charts/'worst_municipality_samples.png', dpi=160); plt.close(fig)


def write_report(output, charts, report, model_summary, cluster_summary, best_metrics, elbows, stability, instability,
                 reproduction, scaler_parameters, protected_count, block_size):
    """Describe medidas y limitaciones sin declarar perfiles o K definitivos."""
    def chart(name): return os.path.relpath(charts/name, report.parent).replace('\\', '/')
    band_labels = dict(below_minus_20pp='<−20', minus_20_to_minus_10pp='[−20, −10)',
        minus_10_to_zero='[−10, 0)', zero_to_10pp='[0, 10)',
        **{'10_to_20pp': '[10, 20)', 'at_least_20pp': '≥20'})
    overview = [[row.representation, row.k, row.seed, number(row.n), f'{row.silhouette_exact:.4f}',
        number(row.negative_count), pct(row.negative_fraction), pct(row.weak_fraction), pct(row.low_margin_fraction),
        f'{row.margin_median:.3f}'] for row in model_summary.itertuples()]
    clusters = [[row.representation, row.k, row.cluster, number(row.observations), f'{row.silhouette_mean:.4f}',
        pct(row.negative_fraction), pct(row.weak_fraction), pct(row.low_margin_fraction), f'{row.margin_median:.3f}']
        for row in cluster_summary.itertuples()]
    curve_rows = [[row.representation, row.k, row.seed, f'{row.sse:.4f}',
        'n/d' if pd.isna(row.reduction_absolute) else f'{row.reduction_absolute:.4f}', pct(row.reduction_fraction),
        f'{row.silhouette_exact:.4f}', f'{row.davies_bouldin:.4f}'] for row in best_metrics.itertuples()]
    elbow_rows = [[row['representation'], row['curve'], row['axis_mode'], row['selected_k'] or 'n/d', row['status']]
        for row in elbows if row['curve'] == 'best_across_seeds']
    worst = instability['instability_summary'].sort_values(['representation', 'k', 'ari', 'replicate', 'scope'])
    worst_rows = [[row.representation, row.k, row.replicate, row.scope, number(row.n), f'{row.ari:.3f}',
        pct(row.changed_fraction), pct(row.changed_low_margin_fraction), f'{row.maximum_centroid_shift_common_z:.3f}'] for row in worst.itertuples()]
    body = []
    for representation in FEATURE_SETS:
        scores = best_metrics[best_metrics.representation.eq(representation)]
        silhouette_best = scores.loc[scores.silhouette_exact.idxmax()]
        db_best = scores.loc[scores.davies_bouldin.idxmin()]
        body.append(f'- {representation}: mayor Silhouette exacto entre K=2…10 en **K={int(silhouette_best.k)}** '
            f'({silhouette_best.silhouette_exact:.4f}); menor DB en K={int(db_best.k)} ({db_best.davies_bouldin:.4f}). '
            'Son extremos de esta rejilla, no validación de un número verdadero de grupos.')
    weakest = cluster_summary.sort_values(['silhouette_mean', 'representation', 'k', 'cluster']).iloc[0]
    top_boundary = []
    for row in model_summary.itertuples():
        table = pd.read_csv(output/'models'/f'{row.representation}_k{row.k:02d}'/'boundary_composition.csv', dtype={'SEXO': str})
        for item in table.sort_values(['low_margin_count', 'age_band', 'SEXO'], ascending=[False, True, True]).head(3).itertuples():
            top_boundary.append([row.representation, row.k, item.age_band, item.SEXO, item.relative_rate_band,
                number(item.observations), number(item.low_margin_count), pct(item.low_margin_fraction), pct(item.share_of_all_low_margin)])
            top_boundary[-1][4] = band_labels[item.relative_rate_band]
    effect_rows = []
    for case_id, group in instability['cluster_impacts'].query("scope == 'oob'").groupby('case_id'):
        for item in group.sort_values('outgoing_n', ascending=False).head(2).itertuples():
            effect_rows.append([case_id, item.cluster, number(item.before_n), number(item.after_n), number(item.outgoing_n), pct(item.outgoing_fraction), f'{item.jaccard:.3f}'])
    worst_oob = worst.query("scope == 'oob'").sort_values(['ari', 'replicate']).groupby(['representation', 'k'], sort=False).head(1)
    demographic_rows, association_rows, instability_notes = [], [], []
    for case in worst_oob.itertuples():
        groups = instability['change_demographics']
        groups = groups[groups.case_id.eq(case.case_id) & groups.scope.eq('oob')]
        for item in groups.sort_values(['changed_count', 'age_band', 'SEXO'], ascending=[False, True, True]).head(3).itertuples():
            demographic_rows.append([case.case_id, item.age_band, item.SEXO, band_labels[item.relative_rate_band],
                number(item.observations), number(item.changed_count), pct(item.changed_fraction)])
        associations = instability['margin_change_associations']
        associations = associations[associations.case_id.eq(case.case_id) & associations.scope.eq('oob')]
        for item in associations.sort_values('baseline_low_margin', ascending=False).itertuples():
            association_rows.append([case.case_id, '≤0.10' if item.baseline_low_margin else '>0.10',
                number(item.observations), number(item.changed_count), pct(item.changed_fraction)])
        instability_notes.append(f'- {case.representation}, K={case.k}, muestra {case.replicate}: cambia '
            f'{pct(case.changed_fraction)} de OOB; sólo {pct(case.changed_low_margin_fraction)} de esos cambios '
            f'tenía margen bajo previo. El máximo desplazamiento de centroide es {case.maximum_centroid_shift_common_z:.3f} '
            'en coordenadas z comunes.')
    weakest_negative = cluster_summary.sort_values('negative_fraction', ascending=False).iloc[0]
    worst_per_candidate = instability['instability_summary'].query("scope == 'oob'").groupby(['representation', 'k']).size().iloc[0]
    anchor_count = len(pd.read_parquet(output/'metadata/silhouette_anchors.parquet'))
    text = f'''# Separación de clusters, ambigüedad y evaluación de K · 2024

## Alcance y resultados observados

Se revisa life_stage con exactamente los **22,282 segmentos elegibles** del experimento anterior, LN=98,090,941, y peso equal_segment. A usa edad media nominal y participación observada; B usa edad media nominal y diferencia nacional de su intervalo/sexo. Se conservan las 27,650 observaciones originales en referencia, con pendientes sin etiqueta. No se vuelven a leer CSV. No se elige un modelo ni perfiles definitivos.

Se repitieron 54 ajustes K-Means (K=2…10 × tres semillas × A/B), cada uno con diez arranques simétricos comunes. Se verificó reproducción de las 18 soluciones anteriores K=4/5/6: ARI mínimo={reproduction.ari.min():.12f}, diferencia máxima de SSE={reproduction.sse_difference.abs().max():.3g}. Los criterios de soporte, referencias nacionales, población y escaladores permanecen fijos. Se reutilizaron las 30 submuestras municipales para el diagnóstico de inestabilidad, sin volver a entrenarlas.

{chr(10).join(body)}

La separación debe juzgarse con medias por cluster, observaciones negativas o próximas a cero y márgenes de distancia, no sólo con el promedio global. El cluster con menor media Silhouette de los cuatro escenarios es {weakest.representation}, K={int(weakest.k)}, c{int(weakest.cluster)}: media={weakest.silhouette_mean:.4f}, negativos={pct(weakest.negative_fraction)}, margen≤0.10={pct(weakest.low_margin_fraction)}. Estos son diagnósticos de proximidad, no probabilidades de error ni evidencia de tipos naturales de personas.

**Hay separación parcial, con zonas de ambigüedad y fragilidad ante ciertas submuestras.** En los cuatro escenarios, {pct(1-model_summary.low_margin_fraction.max())}–{pct(1-model_summary.low_margin_fraction.min())} de los segmentos supera el margen exploratorio 0.10 y todas las medias por cluster son positivas, pero eso no certifica una separación suficiente para cualquier uso. El porcentaje de Silhouette negativo es {pct(model_summary.negative_fraction.min())}–{pct(model_summary.negative_fraction.max())}; la cola débil y los cambios municipales impiden describir los grupos como perfiles definitivos. Los índices actuales tampoco obligan a mantener K=4/5: conviene revisar menos grupos como controles.

## Población, unidades y conservación

La unidad es municipio + intervalo experimental de edad + sexo, elección 2024. Se reutiliza elegibilidad 18–100, LN≥100, SV+NV≥100, filas fuente≥5 y características finitas. NS elevado permanece en el principal. Los segmentos 101+, SEXO=2 y los insuficientes permanecen en la referencia y los pendientes originales; SEXO=2 conserva 105 filas fuente y LN=105. Los identificadores son texto y no se usan como distancias. El detalle de edad exacta sigue en cluster_features/reference/exact_age_2024.parquet. No se imputan NULL, no se alteran conteos y no se filtran fuentes.

StandardScaler se toma de la comparación validada: edad, media={scaler_parameters['absolute']['location'][0]:.6f} años y DE={scaler_parameters['absolute']['scale'][0]:.6f}; participación A, DE={scaler_parameters['absolute']['scale'][1]:.6f}; diferencia B, DE={scaler_parameters['relative']['scale'][1]:.6f}. Cada coordenada se expresa como (x−media)/DE, con parámetros ajustados sólo a la población elegible común. Las gráficas en años y porcentajes conservan tasas y orden, pero no las distancias euclídeas de los ejes estandarizados: una unidad de edad y una unidad de tasa tenían unidades y escalas distintas. Tampoco basta cambiar el tamaño de una figura para interpretar correctamente esa métrica. [Definición de StandardScaler](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html).

## Geometría realmente usada por K-Means

Los cuatro gráficos usan todos los puntos en coordenadas z y aspecto igual en ambos ejes, sin jitter. Las X son centroides del modelo completo. Las líneas son bisectrices analíticas recortadas por las celdas de todos los centroides; no son contornos interpolados de etiquetas numéricas. El fondo es sólo una malla visual de la regla «centroide más cercano». No indica densidad, probabilidad o soporte fuera de las regiones con observaciones. Las etiquetas y colores son locales a cada ajuste. Se usa el benchmark de menor SSE del experimento anterior para K=4/5, reproducido aquí; no se alinea artificialmente A con B.

![A K4]({chart('absolute_k04_standardized_geometry.png')})

![A K5]({chart('absolute_k05_standardized_geometry.png')})

![B K4]({chart('relative_k04_standardized_geometry.png')})

![B K5]({chart('relative_k05_standardized_geometry.png')})

## Silhouette exacto y márgenes

Se calculó **Silhouette individual exacto de toda la población**, para la solución de menor SSE de cada K=2…10 en cada representación. No se muestrearon personas, segmentos ni distancias para esos resultados. Se recorren bloques de hasta {block_size} filas contra los 22,282 segmentos y se reutiliza cada bloque entre K: memoria de distancias O(B×N), tiempo cuadrático, sin asignar N×N. La diagonal se excluye de la media del propio grupo y los singleton tienen cero. «Exacto» significa toda la distribución observada con precisión numérica float64, no exactitud estadística de las edades o de la captura. [Definición de Silhouette](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_samples.html).

En contraste, model_metrics.csv contiene además Silhouette **aproximado** de {anchor_count:,} anclas para las tres semillas por K, con sus errores de aproximación, conservando el método anterior para comprobar consistencia cuando se mantiene el número de anclas. Se nombra silhouette_exact en tablas/vector completo y silhouette en métricas de anclas; no se mezclan sus interpretaciones. Davies–Bouldin y SSE usan todo el entrenamiento.

Definiciones exploratorias: negativo S<0; débil 0≤S≤0.10 (inclusive); margen bajo m≤0.10. Son señales descriptivas, no umbrales oficiales de validez o filtros. El margen es m=(d2−d1)/d2, con d1 y d2 distancias al primer y segundo centroide; si ambos fueran cero quedaría NULL con empate documentado. Una etiqueta puede ser la del centroide más cercano y aun tener Silhouette negativo, porque Silhouette compara medias de distancias a todos los puntos de los clusters, no sólo centroides. No se convierte ninguna bandera en probabilidad o confianza.

{markdown_table(['Representación', 'K', 'Semilla', 'Segmentos', 'Silhouette exacto', 'Negativos', '% negativos', '% S de 0 a .10', '% margen≤.10', 'Margen mediano'], overview)}

{markdown_table(['Representación', 'K', 'Cluster', 'n', 'Silhouette medio', '% negativos', '% S de 0 a .10', '% margen≤.10', 'Margen mediano'], clusters)}

La mayor frecuencia de Silhouette negativo corresponde a {weakest_negative.representation}, K={int(weakest_negative.k)}, c{int(weakest_negative.cluster)}: {number(weakest_negative.negative_count)} de {number(weakest_negative.observations)} segmentos ({pct(weakest_negative.negative_fraction)}), con media {weakest_negative.silhouette_mean:.4f}. B con K=5, c0, no tiene negativos y aun así es el de menor media: sus {number(weakest.weak_count)} segmentos con 0≤S≤0.10 y {number(weakest.low_margin_count)} con margen bajo describen debilidad que no detectaría contar sólo negativos. Las dos banderas pueden superponerse; no se suman como observaciones únicas. En B5, c4 tiene 10.66 % de Silhouette débil. Las etiquetas citadas son locales a estos ajustes.

![Silhouette A4]({chart('absolute_k04_silhouette.png')})

![Silhouette A5]({chart('absolute_k05_silhouette.png')})

![Silhouette B4]({chart('relative_k04_silhouette.png')})

![Silhouette B5]({chart('relative_k05_silhouette.png')})

![Márgenes]({chart('margin_histograms.png')})

![Márgenes por cluster]({chart('margin_by_cluster.png')})

## Composición demográfica próxima a fronteras

Las siguientes combinaciones son las tres de mayor **número** de segmentos con margen bajo por escenario. Se muestra también su tasa interna para no confundir tamaño del grupo con mayor propensión a estar en una frontera. Los intervalos de diferencia nacional son sólo paneles descriptivos (pp), sin cambiar la variable continua ni los intervalos de edad. Las tablas completas contienen todas las combinaciones presentes; no se rellenan combinaciones ausentes con observaciones inventadas. SEXO 0=Hombres, 1=Mujeres; SEXO=2 se conserva fuera del entrenamiento por soporte insuficiente.

{markdown_table(['Representación', 'K', 'Edad', 'SEXO', 'Banda de diferencia nacional', 'n grupo', 'Margen bajo n', '% dentro del grupo', '% de todos los márgenes bajos'], top_boundary)}

Los Parquet por escenario guardan, para cada segmento, ambas distancias, margen, Silhouette, segundo centroide y banderas, junto con claves, LN/SV/NV/NS, denominadores, edad y sexo. ambiguous_segments.parquet es sólo un índice de revisión: esas mismas filas permanecen en el diagnóstico completo y en las fuentes.

## Método del codo actualizado

Se usa el mismo banco de diez inicializaciones simétricas (cinco originadas en A y cinco en B), compartiendo sus índices al comparar geometrías. Semillas 17/42/2024; Lloyd hasta asignaciones estables, máximo 1,000 iteraciones. Para cada K se retiene la menor SSE entre semillas; en K=4/5/6 se conserva el benchmark anterior cuando coincide con ese mínimo numéricamente. La selección de una inicialización no es selección definitiva de K.

{markdown_table(['Representación', 'K', 'Semilla mínima', 'SSE', 'Reducción absoluta frente a K−1', 'Reducción relativa', 'Silhouette exacto', 'DB exacto'], curve_rows)}

Las reducciones comienzan en 3 frente a 2: no se ajustó K=1. Una reducción en SSE recompensa flexibilidad y no demuestra necesidad de un cluster adicional. No se compara el valor de SSE entre A/B porque cambió la geometría.

El codo geométrico reutiliza la ecuación (4), teorema 2.5 del [método previo](https://arxiv.org/html/2502.00851v2): pendientes a,b, candidato elegible b>a, mínimo de (a−b)/(1+ab). Se muestran raw (unidades originales de los ejes K/SSE), unit_axes (ambos ejes a [0,1]) y sse_relative como control. Normalizar ejes de la curva no cambia datos, distancias o ajustes. El ángulo depende de esas unidades; sólo examina K interiores 3…9 y no puede escoger K=2 como extremo. Se conservan resultados por semilla y curva mínima, sin forzar monotonía ni un ganador.

{markdown_table(['Representación', 'Curva', 'Ejes', 'K geométrico', 'Estado'], elbow_rows)}

![Codo y métricas]({chart('elbow_and_metrics.png')})

El codo con ambos ejes a [0,1] sugiere **A: K=4 y B: K=3**; con ejes crudos cambia a **A: K=9 y B: K=8**, y con sólo SSE relativo resulta K=3 en ambas. Esa dependencia de escala impide usar un ángulo aislado como decisión automática. La curva tradicional muestra las mayores reducciones al pasar de 2 a 3 (A: 34.08 %, B: 35.45 %); luego las ganancias disminuyen en términos generales, sin un corte único que imponga 4/5.

Silhouette exacto favorece **A: K=2 y B: K=3** en esta rejilla; B con K=7 queda próximo a K=3 (0.3932 frente a 0.3953). Los mínimos de DB en A8/B9 discrepan con esos máximos. Por tanto **K=4/5 no están suficientemente justificados como elección definitiva**: pueden conservarse por resolución descriptiva, pero deben contrastarse con A2 y B3, y K=5 tiene menor Silhouette que K=4 en ambas representaciones. No se investigó aquí la estabilidad municipal ni el detalle de perfiles de K=2/3, por lo que tampoco se los adopta. Exactitud de Silhouette no elimina la incertidumbre metodológica ni garantiza el mínimo global de SSE con arranques finitos.

## Investigación de las submuestras municipales

Se ordenaron las 30 muestras anteriores por ARI OOB para B4, B5 y A5, todos equal_segment, y se analizaron las {worst_per_candidate} peores por candidato. Cada modelo se compara con su benchmark previo, utilizando sus claves exactas. OOB incluye sólo segmentos elegibles de municipios **no usados para entrenar** esa muestra; all_eligible incluye los 22,282 segmentos elegibles completos. Las alineaciones se optimizan por separado en cada población y no se mezclan sus porcentajes. No se suman observaciones entre escenarios o scopes. Los índices de muestra son los identificadores originales desde cero. La referencia nacional sigue fija e incluye conteos OOB; esta es concordancia de particiones, no una validación predictiva independiente del proceso de referencia nacional.

{markdown_table(['Representación', 'K', 'Muestra', 'Población de comparación', 'n', 'ARI', '% cambio alineado', '% cambiados con margen bajo previo', 'Máx. desplazamiento centroide (z común)'], worst_rows)}

Se recuperaron los centroides mediante medias de coordenadas de los segmentos de entrenamiento con sus etiquetas guardadas; se verificó SSE y se reprodujeron las asignaciones, permitiendo sólo discrepancias de empates numéricos registradas. No se entrenó un modelo nuevo para reconstruirlos. Como cada remuestra había reajustado su StandardScaler, los centroides se invierten a unidades originales y luego se llevan al z del principal antes de medir desplazamientos; no se restan coordenadas de escaladores distintos. Las fronteras de remuestra se dibujan en ejes comunes aplicando su transformación afín y su propia métrica, sin sustituirla por la métrica del principal.

Clusters con más salidas en OOB, con tamaños sobre **la misma población de evaluación** antes/después:

{markdown_table(['Caso', 'Cluster de referencia', 'n antes', 'n después alineado', 'Salidas', '% salidas', 'Jaccard'], effect_rows)}

![Peores muestras]({chart('worst_municipality_samples.png')})

En la peor muestra OOB de cada candidato:

{chr(10).join(instability_notes)}

En consecuencia, la inestabilidad importante **no se limita a los segmentos previamente próximos a fronteras**. B4 muestra una excepción amplia en la muestra 22; las siguientes peores, 7 y 6, cambian menos de 0.7 % de OOB y sus cambios sí tenían todos margen bajo. En B5 y especialmente A5 los peores casos redistribuyen fracciones mayores. Esto documenta distintas escalas de cambio, sin demostrar qué mecanismo las produjo.

La siguiente tabla invierte el condicionamiento: proporción que cambia **dentro de cada categoría de margen**, no proporción con margen bajo entre los cambiados. Los segmentos con margen bajo cambian más frecuentemente en estos tres casos, aunque la mayoría de los cambios proviene del conjunto mucho mayor con margen >0.10.

{markdown_table(['Caso OOB', 'Margen previo', 'n en categoría', 'Cambian n', '% cambian dentro de categoría'], association_rows)}

Combinaciones con más cambios en la peor muestra OOB de cada candidato (tres por caso; diferencias frente a la referencia nacional en pp). Los denominadores pertenecen a cada submuestra OOB y no son los de toda la elección:

{markdown_table(['Caso OOB', 'Edad', 'SEXO', 'Diferencia nacional (pp)', 'n en combinación', 'Cambian n', '% cambian'], demographic_rows)}

cluster_impacts.csv, centroid_shifts.csv y change_demographics.csv detallan los grupos, intervalos, sexos y diferencias relativas que concentran cambios, tanto por número como por proporción. margin_change_associations.csv compara tasas de cambio entre márgenes bajos y el resto, con denominadores explícitos. segment_changes.parquet permite localizar las observaciones. Una asociación entre cambio y margen bajo no demuestra la causa de la inestabilidad: también cambia la población, los escaladores y el mínimo local elegido con un número finito de arranques. Las medianas de ARI altas no descartan cambios amplios en las peores muestras.

## Observaciones, explicaciones posibles y decisiones

**Observado:** la separación es desigual entre clusters; los cuatro promedios globales van de 0.3599 a 0.4087 y entre 5.84 % y 6.40 % tiene margen≤0.10. K=2/3 merecen controles adicionales y el codo depende de la escala de sus ejes. En la peor muestra A5 cambia 29.15 % de OOB y sólo 10.73 % de esos cambios tenía margen bajo, frente a 11.87 %/23.32 % en B4 y 10.78 %/30.00 % en B5. La estabilidad alta entre semillas del principal no excluye esas reorganizaciones municipales.

**Posible explicación:** K-Means puede ofrecer particiones distintas de un continuo de edad/participación; grupos alargados o mínimos locales cercanos pueden contribuir a desacuerdos. Es una hipótesis compatible con las geometrías, no una causa demostrada. El margen se refiere a centroides y Silhouette al conjunto de cada grupo: no tienen por qué señalar los mismos segmentos.

**Pendiente:** acordar la resolución útil y los costes de ambigüedad, evaluar mayor número de arranques y sensibilidad a escaladores/pesos/NS, y confirmar las bibliotecas independientes antes de fijar perfiles. Esta revisión justifica **comparar** K-Medoids con las mismas representaciones/población, conservando B como candidata relativa y A como control de niveles, e incluyendo menos grupos como controles si se autoriza esa siguiente etapa. Cambiar a medoides no garantiza fronteras fuertes ni estabilidad: deberán contrastarse etiquetas, márgenes, detalle demográfico y coste computacional. No se ejecutaron K-Medoids, Ward o DBSCAN.

## Preguntas recomendadas para el analista

1. Con 5.84 %–6.40 % de márgenes bajos, A4/c2 con 5.09 % de negativos y B5/c0 con media 0.2933, ¿qué ambigüedad es aceptable para presentar segmentos agregados?
2. Si Silhouette favorece A2/B3 y B7 queda próximo a B3, ¿qué detalle demográfico justificaría mantener cuatro o cinco grupos frente a resúmenes más amplios o un continuo?
3. El ángulo normalizado sugiere A4/B3 y el crudo A9/B8, mientras DB favorece A8/B9: ¿qué criterio externo al índice interno debe orientar la resolución útil?
4. En las combinaciones edad/sexo/diferencia nacional señaladas, ¿cómo comunicar tasas de ambigüedad internas frente a frecuencias absolutas, sin inferir conductas individuales?
5. Cuando la mayoría de los cambios OOB de los peores casos tenía margen>0.10 y los centroides se desplazan hasta 0.764 z, ¿qué experimentos controlados permitirían distinguir optimización finita, cambios de escala y composición municipal?
6. Dada la sensibilidad a peso y NS documentada en la comparación previa, ¿cómo mantener una población y geometría comunes al contrastar K-Medoids, incluyendo controles de K menores?
7. Sin biblioteca independiente disponible y con mínimos locales explorados mediante diez arranques, ¿qué contraste numérico y ampliación de estabilidad se necesitan antes de fijar perfiles?

## Validación y reproducción

Los controles comparan etiquetas/SSE/Silhouette de anclas contra el experimento anterior, exactitud del método por bloques contra casos pequeños, bisectrices y márgenes analíticos, y alineación bajo permutaciones. Se concilian conteos y segmentos por cluster con el entrenamiento; se preserva LN=SV+NV+NS. Se verifican claves únicas, estado NULL de pendientes y conservación de los 27,650 segmentos, 9,773,730 filas fuente representadas y los 105 registros SEXO=2. Se comprueban hashes de {protected_count:,} archivos existentes antes/después; _SUCCESS sólo se escribe tras validar todos los artefactos y el informe.

Scikit-learn/SciPy siguen documentados como no disponibles en dependency_validation.json de la comparación previa. La presente implementación NumPy reutiliza los algoritmos ya contrastados y añade pruebas matemáticas; no se presenta como una validación contra otra biblioteca de clustering. Los valores exactos individuales son nuevos y no sustituyen resultados anteriores.

```powershell
.venv/Scripts/python.exe analysis/scripts/evaluate_cluster_separation.py
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_evaluate_cluster_separation.py
```

Resultados: reference/ conserva fuente, elegibilidad y escaladores; curve/ contiene las 54 particiones experimentales y centroides; exact_silhouette/ contiene vectores completos por K; models/ contiene cuatro diagnósticos, índices de ambiguos y fronteras; instability/ contiene {len(instability['instability_summary'])//2} comparaciones municipales detalladas; metadata/ contiene resúmenes, controles, SSE, codos, estabilidad y manifiesto. Son vistas alternativas, no se suman como registros únicos. Los destinos existentes se rechazan; repetir con --output, --charts y --report nuevos. No se modifican experimentos, informes anteriores, fuentes ni frontend y no se crean commits.
'''
    report.write_text(text, encoding='utf-8')


def run_review(root, output, charts, report, block_size=128, anchor_count=1200, worst_count=3):
    root, output, charts, report = [Path(path).resolve() for path in [root, output, charts, report]]
    require(output.is_relative_to(root/'data/processed') and charts.is_relative_to(root/'analysis/charts') and
        report.is_relative_to(root/'analysis/reports'), 'Destinos fuera del área autorizada.')
    require(not output.exists() and not charts.exists() and not report.exists(), 'Elegir rutas nuevas; se protegen los resultados existentes.')
    require(0 < block_size <= 512 and anchor_count > 1 and 0 < worst_count <= 30, 'Parámetros no válidos.')
    protected = snapshot_inputs(root, output, charts)
    source_validation(root, protected)
    source = root/'data/processed/demographic_representation_comparison'
    source_manifest_path = source/'metadata/run_manifest.json'
    previous = json.loads(source_manifest_path.read_text(encoding='utf-8'))
    require(previous['status'] == 'validated' and json.loads((source/'_SUCCESS').read_text())['manifest_sha256'] == file_hash(source_manifest_path), 'Comparación previa sin validar.')
    require(file_hash(root/'analysis/reports/demographic_representation_comparison.md') == previous['report_sha256'], 'Informe previo alterado.')
    for name, digest in previous['artifact_hashes'].items(): require(protected[str(root/name)] == digest, 'Artefacto previo alterado.')
    output.mkdir(parents=True); charts.mkdir(parents=True); (output/'metadata').mkdir()
    started = time.monotonic()
    manifest = dict(status='running', errors=[], protected_hashes=protected, started_at_utc=datetime.now(timezone.utc).isoformat(),
        configuration=dict(ks=KS, main_ks=MAIN_KS, seeds=SEEDS, n_init=10, block_size=block_size, anchor_count=anchor_count,
            worst_cases_per_candidate=worst_count, margin_limit=MARGIN_LIMIT, silhouette_weak_limit=SILHOUETTE_LIMIT,
            weighting='equal_segment', features=FEATURE_SETS, scheme='life_stage', election_year=2024,
            exact_silhouette='best_sse_solution_for_every_k_blocked_all_observations'),
        versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, pyarrow=pa.__version__, matplotlib=matplotlib.__version__))
    save_json(output/'metadata/run_manifest.json', manifest)
    try:
        full = pd.read_parquet(source/'reference/b_life_stage.parquet')
        mask = full.is_eligible.to_numpy()
        require(len(full) == 27650 and mask.sum() == 22282 and not full.row_id.duplicated().any(), 'Población previa inesperada.')
        require(full.LN.eq(full.SV+full.NV+full.NS).all(), 'Identidad de conteos inválida.')
        save_table(output/'reference/segments.parquet', full)
        training = full.loc[mask].reset_index(drop=True)
        matrices, scalers = {}, {}
        for representation, columns in FEATURE_SETS.items():
            scaled = pd.read_parquet(source/'reference'/f'life_stage_{representation}_features.parquet')
            scalers[representation] = json.loads((source/'reference'/f'life_stage_{representation}_scaler.json').read_text())
            require(scaled.row_id.equals(full.row_id) and scaled.columns.tolist() == ['row_id', *columns], 'Matriz previa no alineada.')
            require(np.allclose(scaled[columns], transform(full[columns].to_numpy(dtype=float), scalers[representation]), equal_nan=True), 'Escala distinta de parámetros guardados.')
            matrices[representation] = scaled.loc[mask, columns].to_numpy(dtype=float)
            require(np.isfinite(matrices[representation]).all(), 'Coordenadas incompletas elegibles.')
            save_table(output/'reference'/f'{representation}_features.parquet', scaled)
            save_json(output/'reference'/f'{representation}_scaler.json', scalers[representation])
        best, metrics, initializations, stability, checks = fit_curve(full, mask, matrices, source, output, anchor_count)
        best_rows, model_rows, cluster_rows, diagnostic_frames = [], [], [], {}
        for representation in FEATURE_SETS:
            partitions = {f'k{k:02d}': best[representation, k]['labels'] for k in KS}
            exact = silhouette_blocks(matrices[representation], partitions, block_size, progress=True)
            scores_frame = full[['row_id', *KEYS]].copy()
            previous_sse = None
            for k in KS:
                fitted = best[representation, k]
                scores = exact[f'k{k:02d}']
                scores_frame[f'k{k:02d}'] = np.nan
                scores_frame.loc[mask, f'k{k:02d}'] = scores
                measured = metrics[metrics.representation.eq(representation) & metrics.k.eq(k) & metrics.seed.eq(fitted['seed'])].iloc[0]
                best_rows.append(dict(representation=representation, k=k, seed=fitted['seed'], sse=fitted['inertia'],
                    reduction_absolute=np.nan if previous_sse is None else previous_sse-fitted['inertia'],
                    reduction_fraction=np.nan if previous_sse is None else (previous_sse-fitted['inertia'])/previous_sse,
                    silhouette_exact=float(scores.mean()), silhouette_anchor=measured.silhouette,
                    davies_bouldin=measured.davies_bouldin, minimum_cluster=measured.minimum_cluster))
                previous_sse = fitted['inertia']
                if k in MAIN_KS:
                    frame, summary, groups, model_summary = separation_table(training, matrices[representation], fitted, scores)
                    for table in [summary, groups]: table.insert(0, 'k', k); table.insert(0, 'representation', representation)
                    folder = output/'models'/f'{representation}_k{k:02d}'
                    save_table(folder/'segments.parquet', frame)
                    save_table(folder/'ambiguous_segments.parquet', frame[frame.negative_silhouette | frame.weak_silhouette | frame.low_margin])
                    save_table(folder/'cluster_summary.csv', summary); save_table(folder/'boundary_composition.csv', groups)
                    save_json(folder/'model.json', dict(representation=representation, k=k, seed=fitted['seed'],
                        centers_z=fitted['centers'].tolist(), scaler=scalers[representation], weighting='equal_segment', n=len(training)))
                    model_rows.append(dict(representation=representation, k=k, seed=fitted['seed'], **model_summary))
                    cluster_rows.append(summary); diagnostic_frames[representation, k] = frame
                    require(summary.observations.sum() == mask.sum() and summary.LN.sum() == training.LN.sum(), 'Resumen de clusters no concilia.')
                    plot_geometry(matrices[representation], fitted, representation, k, charts, output)
                    plot_silhouette(frame, representation, k, charts)
            save_table(output/'exact_silhouette'/f'{representation}.parquet', scores_frame)
        best_metrics = pd.DataFrame(best_rows)
        elbow_choices, elbow_details = [], []
        for representation in FEATURE_SETS:
            curves = [(f'seed{seed}', metrics[metrics.representation.eq(representation) & metrics.seed.eq(seed)].sort_values('k').sse.to_numpy()) for seed in SEEDS]
            curves.append(('best_across_seeds', best_metrics[best_metrics.representation.eq(representation)].sort_values('k').sse.to_numpy()))
            for curve, sse in curves:
                for mode in ['raw', 'sse_relative', 'unit_axes']:
                    chosen, details, status = geometric_elbow(KS, sse, mode)
                    elbow_choices.append(dict(representation=representation, curve=curve, axis_mode=mode, selected_k=chosen, status=status))
                    elbow_details.extend(dict(representation=representation, curve=curve, **item) for item in details)
        model_summary = pd.DataFrame(model_rows); cluster_summary = pd.concat(cluster_rows, ignore_index=True)
        for name, frame in [('model_metrics', metrics), ('best_curve', best_metrics), ('initializations', initializations),
            ('seed_stability', stability), ('previous_reproduction', checks), ('model_summary', model_summary),
            ('cluster_summary', cluster_summary), ('elbow_choices', pd.DataFrame(elbow_choices)), ('elbow_details', pd.DataFrame(elbow_details))]:
            save_table(output/'metadata'/f'{name}.csv', frame)
        plot_curve(metrics, best_metrics, elbow_choices, stability, charts); plot_margins(diagnostic_frames, charts)
        instability = instability_cases(full, mask, scalers, source, diagnostic_frames, output, charts, worst_count)
        write_report(output, charts, report, model_summary, cluster_summary, best_metrics, elbow_choices,
            stability, instability, checks, scalers, len(protected), block_size)
        for path, digest in protected.items(): require(file_hash(path) == digest, f'Archivo previo modificado: {path}')
        manifest.update(status='validated', seconds=round(time.monotonic()-started, 2), finished_at_utc=datetime.now(timezone.utc).isoformat(),
            fitted_models=len(metrics), exact_partitions=len(best_metrics), protected_files=len(protected),
            script_hashes={name: file_hash(root/'analysis/scripts'/name) for name in ['evaluate_cluster_separation.py', 'compare_demographic_features.py', 'clustering_core.py']},
            report_sha256=file_hash(report), artifact_hashes={str(path.relative_to(root)): file_hash(path) for directory in [output, charts]
                for path in directory.rglob('*') if path.is_file() and path != output/'metadata/run_manifest.json'})
        save_json(output/'metadata/run_manifest.json', manifest)
        save_json(output/'_SUCCESS', dict(manifest_sha256=file_hash(output/'metadata/run_manifest.json')))
        print(f'VALIDADO: {len(metrics)} ajustes, {len(best_metrics)} Silhouette completos; {report.relative_to(root)}', flush=True)
    except Exception as error:
        manifest['status'] = 'failed'; manifest['errors'].append(dict(type=type(error).__name__, message=str(error)))
        save_json(output/'metadata/run_manifest.json', manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, default=Path('data/processed/cluster_separation_review'))
    parser.add_argument('--charts', type=Path, default=Path('analysis/charts/cluster_separation_review'))
    parser.add_argument('--report', type=Path, default=Path('analysis/reports/cluster_separation_review.md'))
    parser.add_argument('--distance-block-size', type=int, default=128)
    parser.add_argument('--anchor-count', type=int, default=1200)
    parser.add_argument('--worst-cases', type=int, default=3)
    args = parser.parse_args(); root = args.root.resolve()
    run_review(root, *[path if path.is_absolute() else root/path for path in [args.output, args.charts, args.report]],
        block_size=args.distance_block_size, anchor_count=args.anchor_count, worst_count=args.worst_cases)


if __name__ == '__main__':
    main()
