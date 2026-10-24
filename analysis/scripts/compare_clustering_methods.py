"""Control R1/R2 sobre segmentos de 2024 y factibilidad de algoritmos alternativos.

Reutiliza fuentes validadas y Lloyd existente. No implementa GMM, HDBSCAN ni
K-Medoids artesanales cuando no hay bibliotecas/pilotos utilizables.
"""
from __future__ import annotations

import os
for thread_variable in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[thread_variable] = '1'

import argparse
from datetime import datetime, timezone
import importlib
from itertools import combinations
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np
import pandas as pd

from clean_data import require, save_json, file_hash
from build_cluster_features import save_table, snapshot_inputs
from build_descriptive import METRICS, markdown_table, number, pct
from clustering_core import adjusted_rand, fit_scaler, transform
from compare_demographic_features import (FEATURE_SETS, KEYS, MUNICIPAL_KEYS, SEEDS,
    initialization_bank, fit_bank, predict, diagnostics, explained_fraction,
    membership, nullable_labels, source_validation, pandas_numerical_check)
from evaluate_cluster_separation import silhouette_blocks, align_partition, decision_edges
from run_demographic_pilot import anchor_sample, anchor_distances, sampled_metrics, cluster_tables

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from matplotlib.lines import Line2D

KS = [2, 3, 4, 5, 6]
REPRESENTATIONS = ['r1', 'r2']
COLORS = [plt.get_cmap('tab10')(i) for i in range(10)]


def scalar_engine(values):
    """Adapta una dimensión al Lloyd probado de dos columnas: [0, diferencia_z].

    La columna constante no se guarda como característica, no agrega distancia
    y no se usa como edad. Evita implementar otro algoritmo de agrupamiento.
    """
    values = np.asarray(values, dtype=float).reshape(-1)
    require(np.isfinite(values).all(), 'Coordenada escalar no finita.')
    return np.column_stack([np.zeros(len(values)), values])


def scalar_silhouette(values, labels):
    """Silhouette individual exacto en R: sumas de |x−y| mediante prefijos.

    O(K N log N), memoria O(K N); no usa distancias N×N ni aproximaciones.
    El propio punto aporta cero y se divide por n_c−1; singleton=0.
    """
    values, labels = np.asarray(values, dtype=float).reshape(-1), np.asarray(labels)
    require(len(values) == len(labels) and np.isfinite(values).all(), 'Silhouette no alineado.')
    groups, encoded = np.unique(labels, return_inverse=True)
    require(2 <= len(groups) < len(values), 'Silhouette requiere 2…N−1 grupos.')
    counts = np.bincount(encoded)
    sums = np.empty((len(values), len(groups)))
    for group in range(len(groups)):
        ordered = np.sort(values[encoded == group])
        prefix = np.r_[0., np.cumsum(ordered)]
        left = np.searchsorted(ordered, values, side='left')
        sums[:, group] = np.maximum(0., values*left-prefix[left]+prefix[-1]-prefix[left]-values*(len(ordered)-left))
    own = sums[np.arange(len(values)), encoded]/np.maximum(counts[encoded]-1, 1)
    means = sums/counts
    means[np.arange(len(values)), encoded] = np.inf
    other = means.min(axis=1)
    result = np.divide(other-own, np.maximum(own, other), out=np.zeros(len(values)), where=np.maximum(own, other) > 0)
    result[counts[encoded] == 1] = 0.
    require(np.isfinite(result).all() and (np.abs(result) <= 1+1e-10).all(), 'Silhouette escalar inválido.')
    return result


def paired_matrices(raw, scaler):
    """R2 retira sólo edad; población, referencia y escala de diferencia idénticas."""
    r1 = transform(raw[FEATURE_SETS['relative']].to_numpy(dtype=float), scaler)
    require(np.isfinite(r1).all(), 'Población elegible con coordenadas incompletas.')
    return {'r1': r1, 'r2': scalar_engine(r1[:, 1])}


def shared_bank(matrices, k, seed):
    # El generador existente admite dos geometrías: aquí se le pasan R1 y R2.
    bank = initialization_bank({'absolute': matrices['r1'], 'relative': matrices['r2']}, k, seed, 10)
    for record in bank:
        record['source'] = 'r1' if record['source'] == 'absolute' else 'r2'
    return bank


def dependency_probe(root):
    """Sondea importaciones y resolución binaria sin instalar ni alterar paquetes."""
    imports = {}
    for name in ['scipy', 'sklearn', 'sklearn_extra', 'hdbscan']:
        try:
            module = importlib.import_module(name)
            imports[name] = dict(available=True, version=getattr(module, '__version__', None))
        except Exception as error:
            imports[name] = dict(available=False, error=f'{type(error).__name__}: {error}')
    probes = []
    if not imports['sklearn']['available']:
        command = [sys.executable, '-m', 'pip', 'install', '--dry-run', '--only-binary=:all:', '--no-cache-dir',
            '--disable-pip-version-check', '--timeout', '15', '--retries', '0', '--index-url', 'https://pypi.org/simple', 'scikit-learn']
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=45)
            probes.append(dict(command=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        except subprocess.TimeoutExpired:
            probes.append(dict(command=command, returncode=None, error='timeout_45_seconds'))
    return dict(python=platform.python_version(), executable=sys.executable, imports=imports, probes=probes,
        kmedoids_pilot_exists=(root/'analysis/reports/kmedoids_pilot.md').exists(),
        interpretation='La disponibilidad se comprueba en este entorno; no se concluye incompatibilidad general de Python. No se instalaron paquetes.')


def algorithm_plan(dependencies):
    """Explicita pruebas pendientes; los parámetros no son resultados simulados."""
    return dict(
        kmeans=dict(status='executed_existing_tested_numpy_lloyd', ks=KS, seeds=SEEDS, n_init=10, max_iter=1000),
        kmedoids=dict(status='pending_review_existing_pilot' if dependencies['kmedoids_pilot_exists'] else 'not_run_no_existing_pilot',
            note='No se sustituye por PAM artesanal ni distancias completas.'),
        gmm=dict(status='pending_library_adapter_validation' if dependencies['imports']['sklearn']['available'] else 'not_run_missing_dependency',
            planned_backend='sklearn.mixture.GaussianMixture',
            ks=KS, covariance_r1=['full', 'diag'], covariance_r2=['full'], seeds=SEEDS, n_init=10,
            reg_covar=1e-6, tol=1e-5, max_iter=1000,
            required_metrics=['aic', 'bic', 'converged', 'log_likelihood', 'posterior_max', 'posterior_entropy', 'seed_ari', 'municipality_resampling'],
            note='AIC/BIC se comparan dentro de la misma representación; la probabilidad es condicional al modelo.'),
        hdbscan=dict(status='pending_library_adapter_validation' if dependencies['imports']['sklearn']['available'] or dependencies['imports']['hdbscan']['available'] else 'not_run_missing_dependency',
            planned_backend='sklearn.cluster.HDBSCAN',
            min_cluster_size=[100, 300, 1000], min_samples=[10, 50], metric='euclidean',
            algorithm='kd_tree', cluster_selection_method='eom', allow_single_cluster=True,
            required_metrics=['detected_clusters', 'noise_fraction', 'assigned_segment_fraction', 'assigned_LN_fraction',
                'assigned_municipalities', 'assigned_only_silhouette', 'common_assignment_ari', 'noise_membership_stability'],
            note='No hay número de grupos objetivo; exigir búsqueda por árbol, sin matriz precomputed N×N. El Silhouette de asignados no cubre el ruido.'))


def band_diagnosis(training):
    """Cuantifica la geometría inducida por cinco intervalos ya agregados."""
    rows = []
    for band, frame in training.groupby('age_band', observed=True):
        ages = frame.mean_age_nominal
        rows.append(dict(age_band=band, observations=len(frame), municipalities=frame.groupby(MUNICIPAL_KEYS).ngroups,
            LN=int(frame.LN.sum()), age_min=ages.min(), age_q1=ages.quantile(.25), age_median=ages.median(),
            age_q3=ages.quantile(.75), age_max=ages.max(), age_sd=ages.std(ddof=0),
            delta_mean=frame.participation_deviation_national.mean(), delta_sd=frame.participation_deviation_national.std(ddof=0)))
    codes = pd.factorize(training.age_band)[0]
    cells = pd.factorize(pd.MultiIndex.from_frame(training[['age_band', 'SEXO']]))[0]
    ones = np.ones(len(training))
    fractions = dict(age_variance_explained_by_band=explained_fraction(training.mean_age_nominal.to_numpy(), codes, ones),
        delta_variance_explained_by_band=explained_fraction(training.participation_deviation_national.to_numpy(), codes, ones),
        delta_variance_explained_by_band_sex=explained_fraction(training.participation_deviation_national.to_numpy(), cells, ones))
    return pd.DataFrame(rows), fractions


def fit_models(full, mask, scaler, source, output, anchor_count):
    training = full.loc[mask].reset_index(drop=True)
    matrices = paired_matrices(training, scaler)
    anchors = anchor_sample(training.row_id, anchor_count)
    save_table(output/'metadata/silhouette_anchors.parquet', training.iloc[anchors][['row_id', *KEYS]])
    banks = {(k, seed): shared_bank(matrices, k, seed) for k in KS for seed in SEEDS}
    models, rows, trials, validation, controls = {}, [], [], [], []
    previous_metrics = pd.read_csv(source/'metadata/model_metrics.csv')
    previous_labels = pd.read_parquet(source/'curve/relative/labels.parquet')
    require(previous_labels.row_id.equals(full.row_id), 'Referencia anterior sin alinear.')
    for representation in REPRESENTATIONS:
        values = matrices[representation]
        distances = anchor_distances(values, anchors)
        labels = full[['row_id', *KEYS, 'is_eligible', 'pending_reason']].copy()
        centers = []
        for k in KS:
            for seed in SEEDS:
                fitted = fit_bank(values, np.ones(len(values)), banks[k, seed])
                models[representation, k, seed] = fitted
                labels[f'k{k:02d}_seed{seed}'] = nullable_labels(full, mask, fitted['labels'])
                numerical = pandas_numerical_check(values, np.ones(len(values)), fitted['labels'], fitted['centers'], fitted['inertia'])
                validation.append(dict(representation=representation, k=k, seed=seed, **numerical))
                metrics = sampled_metrics(values, fitted['labels'], anchors, distances)
                rows.append(dict(representation=representation, k=k, seed=seed, n=len(values), sse=fitted['inertia'],
                    converged=fitted['converged'], iterations=fitted['iterations'],
                    minimum_cluster=np.bincount(fitted['labels']).min(), maximum_cluster=np.bincount(fitted['labels']).max(),
                    **metrics, **diagnostics(training, values, fitted['labels'], np.ones(len(values)))))
                for item in fitted['initializations']:
                    trials.append(dict(representation=representation, k=k, seed=seed, **item))
                for cluster, center in enumerate(fitted['centers']):
                    centers.append(dict(k=k, seed=seed, cluster=cluster, age_z=center[0] if representation == 'r1' else np.nan,
                        delta_z=center[1], delta_original=center[1]*scaler['scale'][1]+scaler['location'][1]))
                if representation == 'r1':
                    old = previous_metrics[previous_metrics.representation.eq('relative') & previous_metrics.k.eq(k) & previous_metrics.seed.eq(seed)].iloc[0]
                    controls.append(dict(k=k, seed=seed, ari_previous=adjusted_rand(previous_labels.loc[mask, f'k{k:02d}_seed{seed}'].to_numpy(dtype=int), fitted['labels']),
                        previous_sse=old.sse, new_sse=fitted['inertia'], sse_difference=fitted['inertia']-old.sse))
            print(f'{representation}: K={k}, tres semillas y diez arranques comunes.', flush=True)
        del distances
        save_table(output/'models'/representation/'labels.parquet', labels)
        save_table(output/'models'/representation/'centroids.csv', pd.DataFrame(centers))
    best = {(representation, k): min(SEEDS, key=lambda seed: models[representation, k, seed]['inertia'])
        for representation in REPRESENTATIONS for k in KS}
    summary, profiles, distributions, municipalities, agreements = [], [], [], [], []
    exact_r1 = silhouette_blocks(matrices['r1'], {f'k{k}': models['r1', k, best['r1', k]]['labels'] for k in KS}, 128, True)
    scores = full[['row_id', *KEYS]].copy()
    for representation in REPRESENTATIONS:
        for k in KS:
            seed = best[representation, k]; fitted = models[representation, k, seed]
            exact = exact_r1[f'k{k}'] if representation == 'r1' else scalar_silhouette(matrices['r2'][:, 1], fitted['labels'])
            scores[f'{representation}_k{k:02d}'] = np.nan; scores.loc[mask, f'{representation}_k{k:02d}'] = exact
            record = next(row for row in rows if row['representation'] == representation and row['k'] == k and row['seed'] == seed)
            summary.append(dict(record, silhouette_exact=float(exact.mean()), negative_fraction=float((exact < 0).mean()),
                weak_fraction=float(((exact >= 0) & (exact <= .1)).mean()),
                minimum_seed_ari=min(adjusted_rand(models[representation, k, a]['labels'], models[representation, k, b]['labels']) for a, b in combinations(SEEDS, 2))))
            a, b, c = cluster_tables(training, fitted['labels'], k, seed)
            per_cluster = pd.DataFrame(dict(cluster=fitted['labels'], silhouette=exact)).groupby('cluster', as_index=False).agg(
                silhouette_mean=('silhouette', 'mean'), negative_fraction=('silhouette', lambda v: v.lt(0).mean()))
            a = a.merge(per_cluster, on='cluster', validate='one_to_one')
            for table in [a, b, c]: table.insert(0, 'representation', representation)
            profiles.append(a); municipalities.append(b); distributions.append(c)
            # Cruza intervalo, sexo y cluster para interpretar diferencias dentro de pares.
            cells = training[['age_band', 'SEXO', 'LN', 'SV', 'NV', 'NS', 'participation_deviation_national']].copy()
            cells['cluster'] = fitted['labels']
            cells = cells.groupby(['cluster', 'age_band', 'SEXO'], observed=True, as_index=False).agg(
                observations=('LN', 'size'), LN=('LN', 'sum'), SV=('SV', 'sum'), NV=('NV', 'sum'), NS=('NS', 'sum'),
                mean_delta=('participation_deviation_national', 'mean'))
            cells.insert(0, 'k', k); cells.insert(0, 'representation', representation)
            save_table(output/'models'/representation/f'k{k:02d}_age_sex_cells.csv', cells)
        print(f'{representation}: métricas exactas del mejor ajuste por K.', flush=True)
    for k in KS:
        left = models['r1', k, best['r1', k]]['labels']; right = models['r2', k, best['r2', k]]['labels']
        aligned, _ = align_partition(left, right, k)
        agreements.append(dict(k=k, n=len(left), ari=adjusted_rand(left, right), aligned_change_fraction=float((aligned != left).mean())))
    save_table(output/'models/exact_silhouette.parquet', scores)
    for name, frame in [('model_metrics', pd.DataFrame(rows)), ('best_models', pd.DataFrame(summary)), ('initializations', pd.DataFrame(trials)),
        ('numerical_validation', pd.DataFrame(validation)), ('previous_kmeans_control', pd.DataFrame(controls)),
        ('cluster_profiles', pd.concat(profiles, ignore_index=True)), ('cluster_distributions', pd.concat(distributions, ignore_index=True)),
        ('cluster_municipalities', pd.concat(municipalities, ignore_index=True)), ('representation_agreement', pd.DataFrame(agreements))]:
        save_table(output/'metadata'/f'{name}.csv', frame)
    return matrices, models, best, pd.DataFrame(summary)


def municipal_stability(full, mask, models, best, source, output):
    """Mismas treinta membresías, escalas sólo inbag y banco R1/R2 simétrico."""
    membership_table = pd.read_parquet(source/'resampling/municipality_membership.parquet')
    save_table(output/'resampling/municipality_membership.parquet', membership_table)
    rows, coverages = [], []
    for replicate in range(30):
        inside_full = membership(full, membership_table[MUNICIPAL_KEYS], membership_table[f'sample_{replicate:03d}'].to_numpy())
        training_mask = mask & inside_full; inside = inside_full[mask]; oob = ~inside
        raw = full.loc[training_mask].reset_index(drop=True)
        scaler = fit_scaler(raw[FEATURE_SETS['relative']].to_numpy(), 'standard')
        matrices = paired_matrices(raw, scaler)
        projected = paired_matrices(full.loc[mask], scaler)
        labels = full[['row_id', *KEYS]].copy(); labels['is_training'] = training_mask; labels['is_oob_eligible'] = mask & ~inside_full
        coverages.append(dict(replicate=replicate, selected_municipalities=int(membership_table[f'sample_{replicate:03d}'].sum()),
            training_segments=int(training_mask.sum()), training_municipalities=raw.groupby(MUNICIPAL_KEYS).ngroups,
            training_LN=int(raw.LN.sum()), eligible_LN_fraction=float(raw.LN.sum()/full.loc[mask, 'LN'].sum()),
            eligible_segment_fraction=float(training_mask.sum()/mask.sum()), oob_segments=int(oob.sum())))
        for k in KS:
            bank = shared_bank(matrices, k, 17)
            for representation in REPRESENTATIONS:
                fitted = fit_bank(matrices[representation], np.ones(len(raw)), bank)
                predictions, _ = predict(projected[representation], fitted['centers'])
                reference = models[representation, k, best[representation, k]]['labels']
                aligned, _ = align_partition(reference[oob], predictions[oob], k)
                labels[f'{representation}_k{k:02d}'] = nullable_labels(full, mask, predictions)
                rows.append(dict(representation=representation, k=k, replicate=replicate, n=len(raw), oob_n=int(oob.sum()),
                    converged=fitted['converged'], iterations=fitted['iterations'], sse=fitted['inertia'],
                    ari_all=adjusted_rand(reference, predictions), ari_oob=adjusted_rand(reference[oob], predictions[oob]),
                    changed_fraction_oob=float((aligned != reference[oob]).mean())))
        folder = output/'resampling'/f'sample_{replicate:03d}'
        save_table(folder/'labels.parquet', labels); save_json(folder/'scaler.json', scaler)
        print(f'Remuestra municipal {replicate+1}/30: {len(raw):,} segmentos, {oob.sum():,} OOB.', flush=True)
    stability, coverage = pd.DataFrame(rows), pd.DataFrame(coverages)
    save_table(output/'metadata/municipal_stability.csv', stability); save_table(output/'metadata/resampling_coverage.csv', coverage)
    return stability, coverage


def plot_diagnostics(training, matrices, models, best, summary, stability, bands, charts):
    """Gráficas sin jitter; etiquetas locales y escala explícita."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    for index, (band, frame) in enumerate(training.groupby('age_band', observed=True)):
        axes[0].hist(frame.mean_age_nominal, bins=np.arange(18, 100.1, .1), histtype='step', label=f'{band} · n={len(frame):,}', color=COLORS[index])
        positions = training.index[training.age_band.eq(band)].to_numpy()
        axes[1].scatter(matrices['r1'][positions, 0], matrices['r1'][positions, 1], s=3, alpha=.18, color=COLORS[index], label=band)
    axes[0].set_xlabel('Edad media ponderada por LN (años)'); axes[0].set_ylabel('Segmentos por intervalo de 0.1 años'); axes[0].legend(fontsize=8)
    axes[1].set_xlabel('Edad media estandarizada'); axes[1].set_ylabel('Diferencia nacional estandarizada'); axes[1].legend(fontsize=8)
    axes[1].set_aspect('equal', adjustable='box')
    fig.suptitle('Franjas antes del clustering · colores = intervalos predefinidos\nMisma agregación life_stage; no son grupos descubiertos')
    fig.savefig(charts/'age_band_origin.png', dpi=160); plt.close(fig)

    fig, axes = plt.subplots(2, 5, figsize=(20, 10), layout='constrained')
    for column, k in enumerate(KS):
        for row, representation in enumerate(REPRESENTATIONS):
            ax = axes[row, column]; fitted = models[representation, k, best[representation, k]]
            if representation == 'r1':
                values = matrices[representation]
                for cluster in range(k):
                    selected = fitted['labels'] == cluster
                    ax.scatter(values[selected, 0], values[selected, 1], s=2, alpha=.18, color=COLORS[cluster])
                ax.scatter(fitted['centers'][:, 0], fitted['centers'][:, 1], marker='X', color='black', s=35)
                bounds = [values[:, 0].min()-.1, values[:, 0].max()+.1, values[:, 1].min()-.15, values[:, 1].max()+.15]
                for edge in decision_edges(fitted['centers'], bounds):
                    ax.plot([edge['x1'], edge['x2']], [edge['y1'], edge['y2']], color='black', lw=.7)
                ax.set_xlim(bounds[:2]); ax.set_ylim(bounds[2:]); ax.set_aspect('equal', adjustable='box')
                ax.set_xlabel('Edad media z'); ax.set_ylabel('Diferencia nacional z')
            else:
                values = matrices[representation][:, 1]
                bins = np.linspace(values.min(), values.max(), 85)
                ax.hist([values[fitted['labels'] == cluster] for cluster in range(k)], bins=bins,
                    stacked=True, color=COLORS[:k], alpha=.8)
                ordered = np.sort(fitted['centers'][:, 1])
                for boundary in (ordered[:-1]+ordered[1:])/2: ax.axvline(boundary, color='black', lw=.8, ls='--')
                ax.set_xlabel('Única coordenada: diferencia nacional z'); ax.set_ylabel('Segmentos por barra')
            ax.set_title(f'{representation.upper()} · K={k} · semilla {best[representation, k]}')
    fig.suptitle('Geometría del mejor SSE de cada configuración · equal_segment\nR2 es un control unidimensional; colores locales a cada modelo')
    fig.savefig(charts/'representation_geometries.png', dpi=160); plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(14, 8), layout='constrained')
    fields = [('silhouette_exact', 'Silhouette exacto · geometrías distintas'), ('davies_bouldin', 'Davies–Bouldin · geometrías distintas'),
        ('age_r2', 'Varianza de edad explicada por etiquetas'), ('age_band_purity', 'Pureza de intervalo de edad'),
        ('within_age_sex_rate_r2', 'Varianza de tasa separada dentro de edad/sexo'), ('minimum_seed_ari', 'ARI mínimo entre semillas')]
    for ax, (field, title) in zip(axes.ravel(), fields):
        for representation, color in [('r1', '#386cb0'), ('r2', '#d95f02')]:
            rows = summary[summary.representation.eq(representation)].sort_values('k')
            ax.plot(rows.k, rows[field], 'o-', color=color, label=representation.upper())
        ax.set_title(title, fontsize=10); ax.set_xticks(KS); ax.set_xlabel('K (6: sensibilidad)'); ax.grid(alpha=.2); ax.legend()
        if field in ['age_r2', 'age_band_purity', 'within_age_sex_rate_r2']: ax.yaxis.set_major_formatter(PercentFormatter(1))
    fig.suptitle('Misma población y algoritmo · retirar edad cambia la pregunta y la geometría')
    fig.savefig(charts/'metric_comparison.png', dpi=160); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    for ax, field, label in [(axes[0], 'ari_oob', 'ARI en segmentos OOB'), (axes[1], 'changed_fraction_oob', 'Cambio alineado en OOB')]:
        arrays, names = [], []
        for k in KS:
            for representation in REPRESENTATIONS:
                group = stability[stability.k.eq(k) & stability.representation.eq(representation)]
                arrays.append(group[field].to_numpy()); names.append(f'{representation.upper()}\nK={k}')
        boxes = ax.boxplot(arrays, tick_labels=names, patch_artist=True)
        for index, box in enumerate(boxes['boxes']): box.set_facecolor('#386cb0' if index % 2 == 0 else '#d95f02'); box.set_alpha(.5)
        ax.set_ylabel(label); ax.set_ylim(0, 1.02); ax.grid(axis='y', alpha=.2)
        if field == 'changed_fraction_oob': ax.yaxis.set_major_formatter(PercentFormatter(1))
    fig.suptitle('Estabilidad del pipeline · 30 submuestras municipales compartidas, sin reemplazo\nSe reajustan escalas sólo inbag; no son intervalos de confianza')
    fig.savefig(charts/'municipal_stability.png', dpi=160); plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(13, 8), layout='constrained')
    age_order = bands.age_band.tolist()
    for row, representation in enumerate(REPRESENTATIONS):
        for column, k in enumerate([3, 4, 5]):
            ax = axes[row, column]; labels = models[representation, k, best[representation, k]]['labels']
            table = pd.crosstab(pd.Series(labels, name='cluster'), training.age_band).reindex(columns=age_order, fill_value=0)
            bottom = np.zeros(k)
            for index, band in enumerate(age_order):
                fraction = table[band].to_numpy()/table.sum(axis=1).to_numpy()
                ax.bar(np.arange(k), fraction, bottom=bottom, color=COLORS[index], label=band); bottom += fraction
            ax.set_title(f'{representation.upper()} · K={k}'); ax.set_xticks(range(k), [f'c{i}' for i in range(k)])
            ax.set_ylim(0, 1); ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.set_ylabel('Composición de segmentos por intervalo')
    axes[0, 0].legend(fontsize=7)
    fig.suptitle('Dependencia de intervalos · cada barra pertenece a un ajuste local\nLos municipios pueden aportar segmentos a varias agrupaciones')
    fig.savefig(charts/'age_composition.png', dpi=160); plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(13, 7), layout='constrained')
    for row, representation in enumerate(REPRESENTATIONS):
        for column, k in enumerate([3, 4, 5]):
            ax = axes[row, column]; labels = models[representation, k, best[representation, k]]['labels']
            for cluster in range(k):
                part = training.loc[labels == cluster]
                delta = part.participation_deviation_national
                center = delta.mean(); low, high = delta.quantile([.25, .75])
                ax.plot([100*low, 100*high], [cluster, cluster], color=COLORS[cluster], lw=5, alpha=.5)
                ax.scatter(100*center, cluster, color=COLORS[cluster], s=35)
            ax.axvline(0, color='black', lw=.7); ax.set_yticks(range(k), [f'c{i}' for i in range(k)])
            ax.set_xlabel('Diferencia nacional (pp): media y Q1–Q3'); ax.set_title(f'{representation.upper()} · K={k}')
    fig.suptitle('Participación relativa por agrupación · segmentos con peso uno\nCuartiles descriptivos, no intervalos de confianza; no son perfiles individuales')
    fig.savefig(charts/'relative_participation.png', dpi=160); plt.close(fig)


def write_report(output, charts, report, full, mask, summary, stability, coverage, bands, fractions, dependencies, plan, protected_count):
    def picture(name, title): return f'![{title}]({os.path.relpath(charts/name, report.parent).replace(chr(92), "/")})'
    rows = []
    for item in summary.itertuples():
        samples = stability[stability.representation.eq(item.representation) & stability.k.eq(item.k)]
        rows.append([item.representation.upper(), item.k, item.seed, f'{item.silhouette_exact:.4f}', f'{item.davies_bouldin:.4f}',
            number(item.minimum_cluster), number(item.maximum_cluster), f'{item.minimum_seed_ari:.3f}',
            f'{samples.ari_oob.median():.3f}', f'{samples.ari_oob.min():.3f}', pct(item.age_r2),
            pct(item.age_band_purity), f'{item.age_band_ari:.3f}', pct(item.within_age_sex_rate_r2)])
    agreement = pd.read_csv(output/'metadata/representation_agreement.csv')
    controls = pd.read_csv(output/'metadata/previous_kmeans_control.csv')
    profiles = pd.read_csv(output/'metadata/cluster_profiles.csv')
    composition = pd.read_csv(output/'metadata/cluster_distributions.csv', dtype={'category': str})
    women = composition[composition.dimension.eq('SEXO') & composition.category.eq('1')].set_index(['representation', 'k', 'cluster']).cluster_fraction
    profile_rows = [[r.representation.upper(), r.k, r.cluster, number(r.observations), number(r.municipalities),
        f'{r.mean_age:.1f}', pct(women.get((r.representation, r.k, r.cluster), 0.)), pct(r.participation_observed), f'{100*r.mean_national_deviation:.2f}',
        pct(r.unspecified_rate), f'{r.silhouette_mean:.3f}'] for r in profiles[profiles.k.isin([3, 4, 5])].itertuples()]
    cell_rows = []
    for representation in REPRESENTATIONS:
        cells = pd.read_csv(output/'models'/representation/'k04_age_sex_cells.csv', dtype={'SEXO': str})
        contrasts = cells.groupby(['age_band', 'SEXO'], as_index=False).agg(
            clusters_present=('cluster', 'nunique'), minimum_delta=('mean_delta', 'min'), maximum_delta=('mean_delta', 'max'),
            minimum_segments_in_cluster=('observations', 'min'))
        contrasts['range_pp'] = 100*(contrasts.maximum_delta-contrasts.minimum_delta)
        for row in contrasts.sort_values(['range_pp', 'age_band', 'SEXO'], ascending=[False, True, True]).head(3).itertuples():
            cell_rows.append([representation.upper(), 4, row.age_band, row.SEXO, row.clusters_present,
                number(row.minimum_segments_in_cluster), f'{100*row.minimum_delta:.2f}', f'{100*row.maximum_delta:.2f}', f'{row.range_pp:.2f}'])
    band_rows = [[r.age_band, number(r.observations), number(r.LN), f'{r.age_min:.2f}', f'{r.age_q1:.2f}',
        f'{r.age_median:.2f}', f'{r.age_q3:.2f}', f'{r.age_max:.2f}', f'{r.age_sd:.3f}', f'{100*r.delta_sd:.2f}'] for r in bands.itertuples()]
    limits = pd.read_csv(output/'metadata/alternative_readiness.csv')
    readiness_rows = [[r.representation, r.municipalities, r.complete_defined, r.complete_with_support,
        r.missing_coordinates, r.present_undefined] for r in limits.itertuples()]
    best_s = {name: summary[summary.representation.eq(name)].sort_values('silhouette_exact', ascending=False).iloc[0] for name in REPRESENTATIONS}
    native_rows = [[name, config['status'], 'n/d' if name != 'kmeans' else number(int(mask.sum())),
        'n/d' if name != 'kmeans' else '0 %'] for name, config in plan.items()]
    text = f'''# Algoritmos y representación demográfica · 2024

## Respuesta al diagnóstico del analista

**Las franjas verticales provienen de la representación agregada de edad, antes de aplicar clustering.** Los cinco intervalos explican {pct(fractions['age_variance_explained_by_band'])} de la varianza de la edad media nominal de los 22,282 segmentos elegibles. K-Means añade fronteras al espacio ya construido; cambiar de algoritmo no recupera variación etaria que dejó de representarse al agregar. La observación externa es una hipótesis útil, no prueba que un algoritmo alternativo sea superior.

Este experimento aísla el efecto de retirar edad con **R1 = edad media nominal + diferencia nacional por intervalo/sexo** y **R2 = sólo esa diferencia**. Usa la misma población, peso igual por segmento y escala de diferencia. El ARI entre R1/R2 va de {agreement.ari.min():.3f} a {agreement.ari.max():.3f}; cambia {pct(agreement.aligned_change_fraction.min())}–{pct(agreement.aligned_change_fraction.max())} tras alinear etiquetas, según K. La representación afecta materialmente las asignaciones bajo el mismo algoritmo.

**La comparación empírica entre algoritmos queda limitada por el entorno.** Scikit-learn, SciPy y HDBSCAN no están importables; el sondeo binario de scikit-learn no encontró distribución accesible. No existe analysis/reports/kmedoids_pilot.md. Se ejecutó K-Means existente y probado en el proyecto; GMM/HDBSCAN se documentan como pendientes, sin versiones artesanales ni resultados inventados. Esto impide atribuir globalmente la estructura principalmente al algoritmo o afirmar que otro método sea más estable. No se concluye incompatibilidad general de Python {dependencies['python']}.

## Unidad, segmentación y algoritmo

- **Unidad:** municipio + intervalo de edad + sexo, elección 2024; cada observación suma celdas electorales, no representa una persona.
- **Segmentación previa:** life_stage, 18–29, 30–44, 45–59, 60–74 y 75–100 en el entrenamiento. Los intervalos son decisiones de agregación existentes, no agrupaciones descubiertas.
- **Representación:** R1 usa dos coordenadas continuas; R2 una. Las claves y SEXO son metadatos, nunca distancias.
- **Algoritmo:** K-Means divide el espacio recibido minimizando SSE. K no modifica los intervalos originales ni define tipos individuales de ciudadanos.

## Población, escalas y diseño controlado

Se conservan los {len(full):,} segmentos originales, LN={int(full.LN.sum()):,} y {int(full.source_row_count.sum()):,} filas fuente representadas. El principal mantiene exactamente {int(mask.sum()):,} segmentos, {pct(mask.mean())} de las filas agregadas y LN={int(full.loc[mask, 'LN'].sum()):,} ({pct(full.loc[mask, 'LN'].sum()/full.LN.sum())}), en {full.loc[mask].groupby(MUNICIPAL_KEYS).ngroups:,} municipios de los 2,477 observados. Los {int((~mask).sum()):,} pendientes permanecen con etiquetas NULL y razones originales; no se imputan ni se retiran de las fuentes.

Elegibilidad común: edades 18–100, características originales completas, LN≥100, SV+NV≥100 y filas fuente≥5. No se amplía R2 a segmentos sin edad válida: se evita cambiar población al retirar una característica. NS≥10 % sigue incluido: {int(full.loc[mask, 'has_high_unspecified_rate'].sum()):,} segmentos. SEXO=2 conserva 105 filas fuente y LN=105, y 101+ conserva todas sus referencias, sin fusionar categorías ni asignar pendientes. El detalle exacto continúa en cluster_features/reference/exact_age_2024.parquet.

Se reutiliza StandardScaler de la representación relativa anterior. R2 toma exactamente su columna de diferencia estandarizada; no vuelve a ajustar otra población. Para reutilizar Lloyd de dos columnas se adapta internamente como [0, diferencia_z]: la constante aporta distancia cero y no se almacena como característica. r2_features.parquet contiene una única variable; esa constante nunca se interpreta como edad. La referencia nacional fija es ΣSV/Σ(SV+NV) de todos los segmentos originales de cada intervalo/sexo, antes de filtrar soporte. R2 conserva por ello dependencia contextual de edad/sexo, aunque no los incluya como coordenadas.

Se ajustaron 30 modelos completos (R1/R2 × K=2…6 × semillas 17/42/2024), diez arranques por modelo; K=6 es sensibilidad. Cada pareja usa los mismos índices iniciales: cinco inicializaciones D² originadas en R1 y cinco en R2, con Lloyd hasta asignaciones estables, máximo 1,000 iteraciones. Es un banco nuevo simétrico al control actual, distinto del banco absoluta/relativa anterior: por eso se conserva un contraste con las 15 soluciones R1 previas (ARI mínimo {controls.ari_previous.min():.3f}; cambio de SSE entre {controls.sse_difference.min():.6g} y {controls.sse_difference.max():.6g}). No se exige igualdad de mínimos locales cuando cambian arranques y no se atribuye esa diferencia a la representación.

El peso es uno por segmento; municipios con más segmentos elegibles aportan más masa. La ponderación municipal/LN sigue como sensibilidad documentada previamente, no se mezcla con este control de características. No se compara SSE entre R1/R2 como si tuvieran la misma geometría.

## Franjas inducidas por la agregación

{markdown_table(['Intervalo', 'Segmentos', 'LN', 'Edad media mín.', 'Q1', 'Mediana', 'Q3', 'Máx.', 'DE edad', 'DE diferencia (pp)'], band_rows)}

Cada edad media está dentro del intervalo fuente y reúne varios años exactos; sus escasas diferencias entre municipios producen las franjas. En R1 ambas coordenadas tienen varianza uno: edad representa exactamente la mitad de la dispersión euclídea total, sin que eso implique igual utilidad sustantiva. No se necesita una matriz N×N para demostrarlo: la dispersión es suma de varianzas de columnas.

La fracción de varianza de diferencia nacional explicada sólo por intervalo es {pct(fractions['delta_variance_explained_by_band'])}, y por intervalo/sexo {pct(fractions['delta_variance_explained_by_band_sex'])}. Restar la tasa nacional no fuerza media cero en los segmentos con peso uno: la referencia pondera denominadores y aquí además se selecciona soporte.

Las dispersiones tampoco son idénticas: la DE de la diferencia por intervalo va de {100*bands.delta_sd.min():.2f} a {100*bands.delta_sd.max():.2f} pp. Centrar contra la referencia nacional no iguala esas varianzas. R2 puede conservar asociaciones con edad aun sin usarla como coordenada; la dispersión observada no demuestra si procede de heterogeneidad electoral, cobertura o denominadores. Decidir si interesan diferencias en pp o posiciones relativas a distribuciones demográficas sería otra decisión de representación, no una corrección automática aplicada aquí.

{picture('age_band_origin.png', 'Franjas antes del clustering')}

{picture('representation_geometries.png', 'Geometrías R1 y R2')}

## Separación, dependencia de edad y estabilidad

Para cada K se describe la menor SSE entre semillas, sin elegir K definitivo. Silhouette es **exacto** en toda la población elegible: R1 usa bloques de 128×N; R2 obtiene distancias absolutas mediante ordenación y sumas de prefijos O(K N log N), sin matrices N×N. Las métricas por semilla conservan además anclas reproducibles contra toda la población, con error Monte Carlo explícito. Davies–Bouldin usa todos los segmentos.

{markdown_table(['Representación', 'K', 'Semilla', 'Silhouette exacto', 'DB', 'Cluster mín.', 'Máx.', 'ARI semillas mín.', 'ARI OOB mediano', 'OOB mín.', 'R² edad', 'Pureza intervalo', 'ARI intervalo', 'R² tasa dentro edad/sexo'], rows)}

R² edad mide varianza de edad explicada por etiquetas; pureza y ARI de intervalo miden cuánto reproducen las bandas. R² tasa dentro edad/sexo compara residuos con medias intervalo/sexo frente a intervalo/sexo/cluster. Es ajuste descriptivo in-sample y crece con resolución; no equivale a predicción, evidencia causal o validez externa. Las correlaciones residuales con edad pueden persistir en R2 porque tasas, referencia, cobertura y composición siguen relacionadas con ella.

En K=4, R² edad cae de **74.54 % a 3.20 %** al pasar de R1 a R2 y la pureza de intervalo de 45.48 % a 24.66 %; en K=5, de **75.78 % a 3.65 %** y de 47.20 % a 24.28 %. Retirar edad reduce materialmente su asociación con las etiquetas. La mayor fracción de tasa explicada por R2 dentro de edad/sexo (87.28 % y 91.31 %) es coherente con haber dedicado toda la distancia a esa tasa relativa; no demuestra que haya descubierto una estructura multivariable adicional.

{picture('metric_comparison.png', 'Métricas del control')}

{picture('age_composition.png', 'Composición de edades')}

### Cambios R1/R2 en los mismos segmentos

{markdown_table(['K', 'Segmentos comunes', 'ARI', '% cambio alineado'], [[r.k, number(r.n), f'{r.ari:.3f}', pct(r.aligned_change_fraction)] for r in agreement.itertuples()])}

La alineación maximiza solapamiento; los números de etiqueta no tienen identidad entre ajustes. R2 divide una línea de diferencias de participación: sus fronteras son puntos medios entre centroides ordenados y sus grupos son intervalos de esa coordenada. Por construcción aporta niveles relativos, sin un perfil demográfico multivariable ni una mejora automática. Un Silhouette mayor en una dimensión no demuestra superioridad sobre una geometría de dos dimensiones.

### Estabilidad municipal

Se reutilizan las 30 membresías municipales previas, cada una con 1,981 de 2,477 municipios sin reemplazo. Entran juntos todos los segmentos elegibles del municipio. Ahora se ajustan **300 modelos nuevos** (R1/R2 × cinco K × 30 muestras) con el mismo banco compartido por pareja y semilla 17; no se sobrescriben remuestras previas. Se recalculan escalas únicamente inbag y se predice en todos los elegibles. Los rangos de cobertura son {int(coverage.training_segments.min()):,}–{int(coverage.training_segments.max()):,} segmentos y {pct(coverage.eligible_LN_fraction.min())}–{pct(coverage.eligible_LN_fraction.max())} del LN elegible; OOB tiene {int(coverage.oob_segments.min()):,}–{int(coverage.oob_segments.max()):,} segmentos.

ARI OOB compara únicamente municipios no usados para ajustar con el benchmark completo correspondiente. ari_all usa todos los elegibles; ambos quedan separados. Se guardan todas las etiquetas, membresías, escaladores y coberturas, con flags de entrenamiento/proyección. Las referencias nacionales permanecen fijas e incluyen conteos OOB: es estabilidad bajo un contexto fijo, no validación predictiva independiente. Las variaciones combinan composición municipal, escala y optimización finita; las 30 muestras son exploratorias.

En K=4, R2 mejora la peor concordancia OOB (0.928 frente a 0.747 en R1), aunque su mediana es ligeramente menor (0.984 frente a 0.989). En K=5 también mejora el mínimo (0.904 frente a 0.781), pero baja la mediana (0.957 frente a 0.978) y su ARI mínimo entre semillas es 0.985. **No mejora toda medida de estabilidad.** R2–K3 conserva una muestra OOB con ARI 0.882; retirar edad tampoco resuelve automáticamente la inestabilidad. Los controles K2 son estables en estas muestras, sin que ello fije la resolución electoral útil.

{picture('municipal_stability.png', 'Estabilidad municipal')}

## Interpretación electoral descriptiva

Para K=3/4/5 se muestran todas las etiquetas locales; los otros K permanecen en CSV. La tasa agregada es ΣSV/Σ(SV+NV), mientras Δ medio promedia diferencias por segmento con peso uno. NS/LN agregado no equivale a frecuencia de segmentos con NS alto. Los archivos kNN_age_sex_cells.csv permiten examinar diferencias entre clusters dentro del mismo intervalo y sexo.

{markdown_table(['Representación', 'K', 'Cluster local', 'Segmentos', 'Municipios', 'Edad media', '% segmentos mujeres', 'Participación agregada', 'Δ medio (pp)', 'NS/LN', 'Silhouette medio'], profile_rows)}

Como ejemplos verificables dentro de pares demográficos, se muestran las tres combinaciones con mayor rango de Δ medio entre clusters para K=4 en cada representación. Se indica el menor número de segmentos de una celda de cluster, porque una diferencia de medias no tiene el mismo soporte en todas las celdas. SEXO 0=Hombres y 1=Mujeres; las categorías no son coordenadas continuas.

{markdown_table(['Representación', 'K', 'Intervalo', 'SEXO', 'Clusters presentes', 'Celda menor n', 'Δ medio mín. (pp)', 'Máx. (pp)', 'Rango (pp)'], cell_rows)}

Esos rangos se calculan con las etiquetas aprendidas sobre la misma variable y son descriptivos in-sample. En R2 constituyen justamente la separación por niveles relativos: no son evidencia independiente de un efecto electoral ni una prueba de significancia. La tabla completa de cada K mantiene todas las combinaciones observadas y sus conteos.

{picture('relative_participation.png', 'Diferencias de participación')}

Un municipio aparece en varios clusters si sus segmentos tienen tasas o edades diferentes; no se suman municipios entre grupos como territorios únicos. R2 compara tasas relativas a pares demográficos, no niveles absolutos intercambiables: una misma diferencia puede corresponder a participaciones absolutas distintas. NS mide cobertura, no abstención; la agregación no permite inferencias individuales ni atribuir diferencias a causas ciudadanas.

## Algoritmos alternativos: factibilidad y protocolo pendiente

{markdown_table(['Método', 'Estado observado', 'Segmentos entrenados', 'Proporción sin asignar'], native_rows)}

En GMM/HDBSCAN **n/d significa no ejecutado**, no cero grupos, cero ruido ni cobertura del 100 %. No existen probabilidades, AIC/BIC o etiquetas alternativas con las que declarar un ganador. metadata/dependency_validation.json registra importaciones, comandos y errores; algorithm_plan.json conserva parámetros y métricas requeridas. Los sondeos usan --dry-run y no alteran dependencias.

Para una siguiente ejecución con bibliotecas verificadas:

- **GMM:** K=2/3/4/5 y 6 sensibilidad; covarianzas full/diag en R1 (sólo full en R2, donde son equivalentes), diez inicios, tres semillas, regularización 1e−6. Registrar convergencia, AIC/BIC y log-verosimilitud dentro de cada representación; probabilidades posteriores máximas y entropía para incertidumbre condicional. Los componentes pueden aproximar una distribución continua o las franjas inducidas, sin equivaler a grupos electorales reales. AIC/BIC se minimizan y no permiten comparar directamente estas dos representaciones. La dependencia entre segmentos del mismo municipio limita su interpretación como muestras independientes y refuerza la necesidad del remuestreo municipal. [GaussianMixture](https://scikit-learn.org/stable/modules/generated/sklearn.mixture.GaussianMixture.html).
- **HDBSCAN:** min_cluster_size=100/300/1000 y min_samples=10/50; distancias euclídeas, búsqueda por árbol, selección eom y permitir un solo grupo. No fijar número objetivo. Conservar ruido como −1, separado de NULL de pendientes; registrar segmentos, LN y municipios asignados, proporción sin asignar y estabilidad de ruido. Silhouette sólo sobre asignados debe indicar ese denominador y no compararse como evaluación de todos los segmentos. El plan apunta a sklearn.cluster.HDBSCAN; otro paquete requiere revisar nombres de parámetros y convenciones de vecindario. [HDBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html).
- **K-Medoids:** no hay piloto previo para reutilizar. Revisar una implementación validada con memoria acotada y su aproximación antes de ejecutarlo; no sustituir por distancias N×N.

El presente script ejecuta el control NumPy disponible y registra los demás como pendientes. Si cambia la disponibilidad, el adaptador a estas bibliotecas requiere validación antes de activar esos experimentos; no se presenta código de ajuste no probado como experimento completado.

## Alternativas conceptuales y soporte existente

La unidad actual responde a segmentos agregados. Para perfiles territoriales se pueden reutilizar C–Amplios/C–Etapas (municipio como fila, tasas edad×sexo como coordenadas) sin introducir códigos como magnitudes. Su preparación existente conserva:

{markdown_table(['Perfil C', 'Municipios', 'Completos definidos', 'Completos con soporte', 'Coordenadas ausentes', 'Presentes NULL'], readiness_rows)}

Ese cambio responde a otra pregunta: similitud entre perfiles municipales, no entre segmentos. Los conteos y NS deben permanecer como diagnósticos, evitando añadir simultáneamente indicadores algebraicamente redundantes. Otra posibilidad es describir niveles y brechas relativas de un municipio, con una selección explícita de coordenadas que no duplique tasas y diferencias derivadas.

Conservar edad exacta o curvas sería otra representación, pero se ha documentado escasez de soporte en edades avanzadas y celdas municipales. Antes de implementarla deben revisarse denominadores, huecos, NS, complejidad/suavizado y sensibilidad de extremos; interpolar no recupera información. Este trabajo no modifica bandas ni ajusta modelos sobre edades exactas. Tampoco prueba que la distribución latente tenga necesariamente grupos discretos: un continuo descriptivo puede ser más fiel, cuestión pendiente de validación sustantiva.

## Respuestas y decisiones pendientes

1. **¿Algoritmo o representación?** Se comprueba que las franjas y una parte importante de las asignaciones dependen de la agregación y de incluir edad. K-Means determina fronteras dentro de ese espacio. Falta el contraste entre algoritmos para repartir responsabilidades más allá de este hallazgo geométrico; no se demuestra una causa exclusiva.
2. **¿Qué cambia al retirar edad?** Desaparece su contribución directa a la distancia y se obtienen intervalos unidimensionales de diferencia nacional; se conservan como contexto edad/sexo/municipio. ARI, pureza y R² de la tabla cuantifican cuánto cambia cada K. R2 no es una representación multidimensional superior.
3. **¿Algún algoritmo más interpretable y estable?** Se pueden describir estabilidad y separación de R1/R2 con el mismo K-Means, pero no comparar algoritmos no ejecutados. Los niveles relativos R2 son transparentes por construcción; su estabilidad no prueba nuevos tipos demográficos ni fiabilidad individual. Hace falta contraste con bibliotecas accesibles y evaluación electoral externa.
4. **¿Entre cuatro y seis grupos?** No hay respaldo suficiente para fijar ese rango. Dentro de esta rejilla, el máximo Silhouette es R1–K={int(best_s['r1'].k)} ({best_s['r1'].silhouette_exact:.4f}) y R2–K={int(best_s['r2'].k)} ({best_s['r2'].silhouette_exact:.4f}). Son índices internos en geometrías diferentes, no un número verdadero de grupos; el informe previo ya mostró dependencia del codo respecto a sus ejes. K=6 sigue como sensibilidad y más componentes no añaden evidencia por sí mismos.
5. **¿Ajustes antes de continuar?** Acordar si interesa edad, desviación relativa, nivel absoluto o perfil territorial; resolver la pregunta antes de cambiar algoritmo. Mantener el control R2, revisar estabilidad municipal/NS/pesos y alternativas con menos grupos, contrastar con bibliotecas independientes, y documentar el coste de agregación antes de alterar bandas o ajustar curvas. No se seleccionan perfiles definitivos.

**Observado:** tablas, formas inducidas antes del ajuste, cambios de etiquetas y estabilidad numérica. **Hipótesis:** parte de la apariencia extraña puede ser cuantización de un continuo o interacción entre agregación y objetivo de K-Means. **Pendiente:** algoritmos alternativos, validación sustantiva y elección de unidad/representación. No se interpreta una asociación como causalidad.

## Validaciones y reproducción

Se verifican población común R1/R2, escalas y referencias previas, claves textuales, conteos originales, LN=SV+NV+NS, conservación de 105 registros SEXO=2, pendientes NULL, convergencia y K grupos no vacíos, centroides/SSE por groupby de Pandas, conciliación de conteos por cluster, y lectura posterior de Parquet. Las pruebas contrastan Silhouette escalar contra distancias literales pequeñas, la adaptación de una dimensión y las fronteras escalares. Pasaron las 62 pruebas automatizadas del proyecto, siete de ellas nuevas. La comprobación matemática no sustituye una biblioteca independiente de clustering.

Se comparan hashes de {protected_count:,} archivos previos antes/después, incluidos experimentos, informes y scripts; no se reprocesan CSV originales ni se alteran ZIP, datos, informes anteriores o frontend. No se crean commits. _SUCCESS se escribe sólo después de validar artefactos e informe.

```powershell
.venv/Scripts/python.exe analysis/scripts/compare_clustering_methods.py
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_compare_clustering_methods.py
```

Los destinos existentes se rechazan; para repetir usar --output, --charts y --report nuevos. reference/ conserva todos los segmentos y las dos matrices candidatas; models/ contiene etiquetas y Silhouette con pendientes NULL; resampling/ guarda los 300 ajustes municipales; metadata/ contiene contratos, métricas, controles, cobertura y manifiesto. Los escenarios son vistas alternativas y no se suman.
'''
    report.write_text(text, encoding='utf-8')


def run_comparison(root, output, charts, report, anchor_count=600):
    root, output, charts, report = [Path(path).resolve() for path in [root, output, charts, report]]
    require(output.is_relative_to(root/'data/processed') and charts.is_relative_to(root/'analysis/charts') and
        report.is_relative_to(root/'analysis/reports'), 'Destinos fuera del área autorizada.')
    require(not output.exists() and not charts.exists() and not report.exists(), 'Elegir destinos nuevos; no se sobrescriben resultados.')
    require(2 <= anchor_count <= 5000, 'Número de anclas no válido.')
    protected = snapshot_inputs(root, output, charts)
    for folder in [root/'analysis/scripts', root/'src']:
        for path in folder.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.name not in ['compare_clustering_methods.py', 'test_compare_clustering_methods.py']:
                protected[str(path)] = file_hash(path)
    protected[str(root/'.gitignore')] = file_hash(root/'.gitignore')
    source_validation(root, protected)
    for name in ['demographic_representation_comparison', 'cluster_separation_review']:
        folder = root/'data/processed'/name
        prior_path = folder/'metadata/run_manifest.json'; prior = json.loads(prior_path.read_text(encoding='utf-8'))
        require(prior['status'] == 'validated' and json.loads((folder/'_SUCCESS').read_text())['manifest_sha256'] == file_hash(prior_path), f'Experimento no validado: {name}')
        for relative, digest in prior['artifact_hashes'].items(): require(protected[str(root/relative)] == digest, f'Artefacto previo modificado: {relative}')
        require(file_hash(root/'analysis/reports'/f'{name}.md') == prior['report_sha256'], f'Informe previo modificado: {name}')
    output.mkdir(parents=True); charts.mkdir(parents=True); (output/'metadata').mkdir()
    started = time.monotonic()
    manifest_path = output/'metadata/run_manifest.json'
    manifest = dict(status='running', errors=[], protected_hashes=protected, started_at_utc=datetime.now(timezone.utc).isoformat(),
        configuration=dict(ks=KS, sensitivity_k=6, seeds=SEEDS, n_init=10, anchor_count=anchor_count,
            weighting='equal_segment', scheme='life_stage', election_year=2024, municipal_replicates=30,
            feature_columns=dict(r1=FEATURE_SETS['relative'], r2=['participation_deviation_national'])),
        versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, matplotlib=matplotlib.__version__))
    save_json(manifest_path, manifest)
    try:
        dependencies = dependency_probe(root); plan = algorithm_plan(dependencies)
        save_json(output/'metadata/dependency_validation.json', dependencies)
        save_json(output/'metadata/algorithm_plan.json', plan)
        source = root/'data/processed/demographic_representation_comparison'
        separation = root/'data/processed/cluster_separation_review'
        full = pd.read_parquet(source/'reference/b_life_stage.parquet')
        mask = full.is_eligible.to_numpy(); training = full.loc[mask].reset_index(drop=True)
        require(len(full) == 27650 and mask.sum() == 22282 and not full.row_id.duplicated().any(), 'Cambió la población de referencia.')
        for field in ['EDOCVE', 'MPIOCVE', 'SEXO']: require(full[field].map(lambda value: isinstance(value, str)).all(), 'Código no textual.')
        require(full.LN.eq(full.SV+full.NV+full.NS).all(), 'LN no concilia.')
        require(int(full.source_row_count.sum()) == 9773730 and int(full.sex_2_source_rows.sum()) == 105 and int(full.sex_2_nominal_count.sum()) == 105, 'Conteos originales alterados.')
        national = pd.read_csv(source/'reference/national_reference_life_stage.csv', dtype={'SEXO': str})
        expected = full.groupby(['age_band', 'SEXO'], observed=True)[METRICS].sum().sort_index()
        pd.testing.assert_frame_equal(expected, national.set_index(['age_band', 'SEXO'])[METRICS].sort_index(), check_dtype=False)
        require(np.allclose(full.participation_deviation_national, full.participation_observed-full.national_participation, equal_nan=True), 'Diferencia no corresponde a referencia.')
        scaler = json.loads((source/'reference/life_stage_relative_scaler.json').read_text())
        features = pd.read_parquet(source/'reference/life_stage_relative_features.parquet')
        require(features.row_id.equals(full.row_id) and np.allclose(features.iloc[:, 1:], transform(full[FEATURE_SETS['relative']].to_numpy(dtype=float), scaler), equal_nan=True), 'Escala previa alterada.')
        save_table(output/'reference/segments.parquet', full)
        save_table(output/'reference/pending_segments.parquet', full.loc[~mask])
        save_table(output/'reference/r1_features.parquet', features)
        save_table(output/'reference/r2_features.parquet', features[['row_id', 'participation_deviation_national']])
        save_table(output/'reference/national_reference.csv', national)
        save_json(output/'reference/r1_scaler.json', scaler)
        save_json(output/'reference/r2_scaler.json', dict(location=[scaler['location'][1]], scale=[scaler['scale'][1]],
            feature_columns=['participation_deviation_national'], inherited_from='r1_second_coordinate_same_eligible_population'))
        save_json(output/'metadata/feature_contract.json', dict(
            unit='municipality_age_band_sex_2024', scheme='life_stage',
            feature_columns={'r1': FEATURE_SETS['relative'], 'r2': ['participation_deviation_national']},
            key_columns=['row_id', *KEYS], population='identical_previous_is_eligible', national_reference='fixed_original_counts_by_age_band_and_sex',
            engine_padding='r2_only_constant_zero_age_slot_preserves_scalar_distances',
            nulls='pending_rows_kept_unassigned_not_zero', weights='equal_segment',
            full_segments=len(full), training_segments=int(mask.sum()), pending_segments=int((~mask).sum())))
        readiness = []
        for scheme in ['broad', 'life_stage']:
            metadata = pd.read_parquet(root/'data/processed/cluster_features/matrices'/f'c_{scheme}'/'metadata.parquet')
            readiness.append(dict(representation=f'C–{scheme}', municipalities=len(metadata), complete_defined=int(metadata.can_use_complete_algorithms.sum()),
                complete_with_support=int((metadata.can_use_complete_algorithms & ~metadata.has_low_support_features).sum()),
                missing_coordinates=int(metadata.absent_feature_count.sum()), present_undefined=int(metadata.undefined_feature_count.sum())))
        save_table(output/'metadata/alternative_readiness.csv', pd.DataFrame(readiness))
        bands, fractions = band_diagnosis(training)
        save_table(output/'metadata/age_band_geometry.csv', bands); save_json(output/'metadata/aggregation_diagnosis.json', fractions)
        matrices, models, best, summary = fit_models(full, mask, scaler, separation, output, anchor_count)
        stability, coverage = municipal_stability(full, mask, models, best, source, output)
        plot_diagnostics(training, matrices, models, best, summary, stability, bands, charts)
        write_report(output, charts, report, full, mask, summary, stability, coverage, bands, fractions, dependencies, plan, len(protected))
        for representation in REPRESENTATIONS:
            labels = pd.read_parquet(output/'models'/representation/'labels.parquet')
            require(labels.row_id.equals(full.row_id), 'Etiquetas no alineadas.')
            for k in KS:
                for seed in SEEDS:
                    column = f'k{k:02d}_seed{seed}'
                    require(labels.loc[~mask, column].isna().all() and labels.loc[mask, column].notna().all(), 'NULL de pendientes o cobertura incorrectos.')
        for name, digest in protected.items(): require(file_hash(name) == digest, f'Archivo existente modificado: {name}')
        manifest.update(status='validated', finished_at_utc=datetime.now(timezone.utc).isoformat(), seconds=round(time.monotonic()-started, 2),
            full_models=30, municipal_models=len(stability), protected_files=len(protected),
            deferred_algorithms={name: item['status'] for name, item in plan.items() if name != 'kmeans'},
            report_sha256=file_hash(report), script_sha256=file_hash(Path(__file__)),
            artifact_hashes={str(path.relative_to(root)): file_hash(path) for directory in [output, charts]
                for path in directory.rglob('*') if path.is_file() and path != manifest_path})
        save_json(manifest_path, manifest); save_json(output/'_SUCCESS', dict(manifest_sha256=file_hash(manifest_path)))
        print(f'VALIDADO: 30 modelos completos, {len(stability)} municipales; {report.relative_to(root)}', flush=True)
    except Exception as error:
        manifest.update(status='failed'); manifest['errors'].append(dict(type=type(error).__name__, message=str(error)))
        save_json(manifest_path, manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, default=Path('data/processed/clustering_methods_review'))
    parser.add_argument('--charts', type=Path, default=Path('analysis/charts/clustering_methods_review'))
    parser.add_argument('--report', type=Path, default=Path('analysis/reports/clustering_methods_review.md'))
    parser.add_argument('--anchor-count', type=int, default=600)
    args = parser.parse_args(); root = args.root.resolve()
    run_comparison(root, *[path if path.is_absolute() else root/path for path in [args.output, args.charts, args.report]], args.anchor_count)


if __name__ == '__main__':
    main()
