"""Piloto controlado de participación y composición U/R/M, únicamente K-Means.

Conserva referencias y pendientes; no modifica datos o experimentos anteriores.
Las geometrías y pesos se declaran antes de observar métricas de agrupamiento.
"""
from __future__ import annotations

import os
for thread_variable in ['OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[thread_variable] = '1'

import argparse
from datetime import datetime, timezone
from itertools import combinations
import importlib.util
import json
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd
import pyarrow as pa

from clean_data import require, file_hash, save_json
from build_cluster_features import snapshot_inputs, save_table
from build_descriptive import METRICS, compare_sums, markdown_table, pct
from clustering_core import kmeans, kmeans_plus_plus, adjusted_rand
from compare_demographic_features import fit_weights, weighted_group_sse, explained_fraction, membership, nullable_labels
from evaluate_exact_age_clustering import anchor_silhouettes, db_index
from evaluate_cluster_separation import align_partition
from run_demographic_pilot import anchor_sample

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from matplotlib.lines import Line2D

MUNICIPAL_KEYS = ['EDOCVE', 'MPIOCVE']
SHARE_COLUMNS = ['section_ln_share_U', 'section_ln_share_R', 'section_ln_share_M']
SEEDS = [17, 42, 2024]
KS = [2, 3, 4, 5, 6]
ROBUST_KS = [3, 4, 5]
ROBUST_CONFIGS = ['p', 't_euclidean', 't_hellinger', 'pt_euclidean_w20', 'pt_euclidean_w50',
                  'pt_hellinger_w20', 'pt_hellinger_w50', 'at_hellinger_w50']


def configurations():
    """Pesos de bloques predefinidos; no dependen de Silhouette."""
    result = {'p': dict(behavior='relative', geometry='none', alpha=0.)}
    for geometry in ['euclidean', 'hellinger']:
        result['t_'+geometry] = dict(behavior='none', geometry=geometry, alpha=1.)
        for prefix, behavior in [('pt', 'relative'), ('at', 'absolute')]:
            for weight in [20, 50, 80]:
                result[f'{prefix}_{geometry}_w{weight}'] = dict(behavior=behavior, geometry=geometry, alpha=weight/100)
    return result


def fit_blocks(frame):
    """P y A: DE poblacional; T: una escala RMS para todo el bloque, sin whiten."""
    require(len(frame) > 1, 'Población insuficiente para calibrar bloques.')
    result = dict(n=len(frame), fitted_on='training_eligible_segments_only', behavioral={}, contextual={})
    for name, column in [('relative', 'participation_deviation_national'), ('absolute', 'participation_observed')]:
        values = frame[column].to_numpy(float)
        require(np.isfinite(values).all() and values.std(ddof=0) > 1e-12, 'Bloque de participación no finito o constante.')
        result['behavioral'][name] = dict(column=column, mean=float(values.mean()), scale=float(values.std(ddof=0)))
    shares = frame[SHARE_COLUMNS].to_numpy(float)
    require(np.isfinite(shares).all() and (shares >= 0).all() and (shares <= 1).all(), 'Composición fuera de dominio.')
    require(np.allclose(shares.sum(axis=1), 1., atol=1e-12, rtol=0), 'Composición no exhaustiva.')
    for geometry in ['euclidean', 'hellinger']:
        raw = shares if geometry == 'euclidean' else np.sqrt(shares)/np.sqrt(2.)
        mean = raw.mean(axis=0)
        scale = float(np.sqrt(np.mean(np.sum((raw-mean)**2, axis=1))))
        require(scale > 1e-12, 'Bloque territorial constante.')
        result['contextual'][geometry] = dict(mean=mean.tolist(), scale=scale,
            source_columns=SHARE_COLUMNS, raw_mapping='p' if geometry == 'euclidean' else 'sqrt(p)/sqrt(2)')
    return result


def transform_blocks(frame, config, parameters):
    """d²=(1−alpha) dP² + alpha dT²; todo bloque tiene varianza total uno."""
    columns, names = [], []
    if config['behavior'] != 'none':
        block = parameters['behavioral'][config['behavior']]
        value = (frame[block['column']].to_numpy(float)-block['mean'])/block['scale']
        columns.append(np.sqrt(1-config['alpha'])*value[:, None]); names.append('participation_block')
    if config['geometry'] != 'none':
        block = parameters['contextual'][config['geometry']]
        raw = frame[SHARE_COLUMNS].to_numpy(float)
        if config['geometry'] == 'hellinger': raw = np.sqrt(raw)/np.sqrt(2.)
        value = (raw-np.asarray(block['mean']))/block['scale']
        columns.append(np.sqrt(config['alpha'])*value)
        names.extend(['context_U', 'context_R', 'context_M'])
    result = np.ascontiguousarray(np.column_stack(columns))
    require(np.isfinite(result).all(), 'Características no finitas.')
    return result, names


def predict_nd(values, centers):
    """Sólo N×K distancias; nunca N×N."""
    squared = np.zeros((len(values), len(centers)))
    for column in range(values.shape[1]):
        squared += (values[:, column, None]-centers[None, :, column])**2
    return squared.argmin(axis=1), squared


def weighted_lloyd_nd(values, weights, centers, max_iter=1000):
    """Extensión dimensional de Lloyd ponderado existente, sólo para sensibilidad.

    El algoritmo previo está fijado a dos columnas. Aquí se conserva su lógica,
    recorriendo p columnas; se prueba contra él y contra replicación literal.
    """
    values, weights = np.asarray(values, float), np.asarray(weights, float)
    centers = np.asarray(centers, float).copy()
    require(values.ndim == 2 and centers.shape[1] == values.shape[1], 'Dimensiones no compatibles.')
    require(len(weights) == len(values) and np.isfinite(values).all() and np.isfinite(weights).all() and
        np.isfinite(centers).all() and (weights > 0).all(), 'Entrada ponderada no válida.')
    previous, converged = None, False
    for iteration in range(1, max_iter+1):
        labels, squared = predict_nd(values, centers)
        mass = np.bincount(labels, weights=weights, minlength=len(centers))
        if previous is not None and np.array_equal(previous, labels) and (mass > 0).all():
            converged = True
            break
        for column in range(values.shape[1]):
            sums = np.bincount(labels, weights=weights*values[:, column], minlength=len(centers))
            centers[:, column] = np.divide(sums, mass, out=centers[:, column].copy(), where=mass > 0)
        if (mass == 0).any():
            farthest = np.argsort(weights*squared[np.arange(len(values)), labels])[::-1]
            for empty, index in zip(np.flatnonzero(mass == 0), farthest): centers[empty] = values[index]
        previous = labels.copy()
    labels, squared = predict_nd(values, centers)
    return dict(labels=labels, centers=centers, inertia=float(np.dot(weights, squared[np.arange(len(values)), labels])),
        converged=converged, iterations=iteration)


def fit_model(values, k, seed, n_init, weights=None):
    """Principal: K-Means n-dimensional existente. Ponderado: mismo banco RNG."""
    if weights is None:
        fitted = kmeans(values, k, seed, n_init=n_init, max_iter=1000)
    else:
        rng = np.random.default_rng(seed); best, records = None, []
        for index in range(n_init):
            initial_seed = int(rng.integers(0, 2**32-1))
            initial = kmeans_plus_plus(values, k, np.random.default_rng(initial_seed))
            candidate = weighted_lloyd_nd(values, weights, initial)
            records.append(dict(initialization=index, seed=initial_seed, inertia=candidate['inertia'],
                iterations=candidate['iterations'], converged=candidate['converged']))
            if best is None or candidate['inertia'] < best['inertia']:
                best = dict(**candidate, selected_initialization=index)
        fitted = dict(**best, initializations=records)
    require(fitted['converged'] and len(np.unique(fitted['labels'])) == k, 'Ajuste no convergente o con grupos vacíos.')
    return fitted


def initialization_records(fitted, **context):
    """Distingue semilla del ajuste de semilla de cada inicialización."""
    return [dict(**context, initialization=row['initialization'], initial_seed=row['seed'],
        sse=row['inertia'], iterations=row['iterations'], converged=row['converged']) for row in fitted['initializations']]


def numerical_check(values, weights, fitted):
    """Centroides/SSE contrastados con groupby independiente del ajuste."""
    frame = pd.DataFrame(values, columns=[f'x{column}' for column in range(values.shape[1])])
    frame['cluster'] = fitted['labels']; frame['w'] = weights
    for column in range(values.shape[1]): frame[f'wx{column}'] = weights*values[:, column]
    total = frame.groupby('cluster', sort=True)[['w', *[f'wx{i}' for i in range(values.shape[1])]]].sum()
    centers = total.drop(columns='w').to_numpy()/total.w.to_numpy()[:, None]
    residual = float(np.max(np.abs(centers-fitted['centers'])))
    objective = float(np.dot(weights, ((values-centers[fitted['labels']])**2).sum(axis=1)))
    require(residual < 1e-8 and np.isclose(objective, fitted['inertia'], rtol=1e-9, atol=1e-8), 'Centros/SSE no conciliados.')
    return dict(maximum_center_residual=residual, sse_residual=abs(objective-fitted['inertia']))


def margins(values, centers):
    labels, squared = predict_nd(values, centers)
    nearest = np.sort(np.sqrt(squared), axis=1)[:, :2]
    margin = np.divide(nearest[:, 1]-nearest[:, 0], nearest[:, 1], out=np.full(len(values), np.nan), where=nearest[:, 1] > 0)
    return labels, margin


def codes(frame, columns):
    return pd.factorize(pd.MultiIndex.from_frame(frame[columns]), sort=True)[0]


def conditional_rate_r2(frame, labels, columns, min_cell_size=1):
    """Descriptivo in-sample, con bases explícitas; no equivale a efecto causal."""
    groups = codes(frame, columns)
    sizes = np.bincount(groups)
    keep = sizes[groups] >= min_cell_size
    rate = frame.participation_observed.to_numpy()[keep]
    group, cluster = groups[keep], np.asarray(labels)[keep]
    weight = np.ones(len(rate))
    base = weighted_group_sse(rate, group, weight)
    after = weighted_group_sse(rate, group*(int(np.max(labels))+1)+cluster, weight)
    return (float(1-after/base) if base > 1e-14 else np.nan), int(keep.sum())


def pattern_diagnostics(frame, values, labels, config):
    labels = np.asarray(labels, int); n, k = len(labels), labels.max()+1
    ones = np.ones(n); result = {}
    for name, column in [('relative_rate', 'participation_deviation_national'), ('absolute_rate', 'participation_observed'), ('age', 'mean_age_nominal')]:
        result[name+'_r2'] = explained_fraction(frame[column].to_numpy(), labels, ones)
    result['within_age_sex_rate_r2'], _ = conditional_rate_r2(frame, labels, ['age_band', 'SEXO'])
    result['within_municipality_rate_r2'], _ = conditional_rate_r2(frame, labels, MUNICIPAL_KEYS)
    for divisions in [5, 10]:
        work = frame.copy()
        # Rejillas sólo descriptivas, predefinidas; no son nuevos intervalos demográficos.
        for column in ['R', 'M']:
            work['bin_'+column] = np.minimum(divisions-1, np.floor(work[f'section_ln_share_{column}']*divisions+1e-12)).astype(int)
        fraction, support = conditional_rate_r2(work, labels, ['age_band', 'SEXO', 'bin_R', 'bin_M'], 20)
        result[f'within_age_sex_context_{divisions}_rate_r2'] = fraction
        result[f'context_{divisions}_diagnostic_n'] = support
    bands = codes(frame, ['age_band'])
    result['age_band_ari'] = adjusted_rand(labels, bands)
    table = pd.crosstab(labels, frame.age_band)
    result['age_band_purity'] = float(table.max(axis=1).sum()/n)
    municipal = pd.crosstab(pd.Series(codes(frame, MUNICIPAL_KEYS), name='municipality'), labels)
    result['municipality_label_purity'] = float(municipal.max(axis=1).sum()/n)
    result['single_cluster_municipality_fraction'] = float(municipal.gt(0).sum(axis=1).eq(1).mean())
    result['municipality_conditional_entropy_ratio'] = conditional_entropy_ratio(labels, codes(frame, MUNICIPAL_KEYS))
    totals, between = [], []
    for column in range(values.shape[1]):
        total = float(np.sum((values[:, column]-values[:, column].mean())**2))
        totals.append(total); between.append(max(0., total-weighted_group_sse(values[:, column], labels, ones)))
    split = 1 if config['behavior'] != 'none' else 0
    result['participation_share_between'] = sum(between[:split])/sum(between) if sum(between) > 0 else np.nan
    result['context_share_between'] = sum(between[split:])/sum(between) if sum(between) > 0 else np.nan
    result['context_composition_r2'] = float(np.mean([explained_fraction(frame[c].to_numpy(), labels, ones) for c in SHARE_COLUMNS]))
    return result


def conditional_entropy_ratio(labels, groups):
    """H(cluster|municipio)/H(cluster); sesgado por pocos segmentos por municipio."""
    table = pd.crosstab(groups, labels).to_numpy(float)
    probabilities = table.sum(axis=0)/table.sum()
    entropy = -np.sum(probabilities[probabilities > 0]*np.log(probabilities[probabilities > 0]))
    mass = table.sum(axis=1); conditional = table/mass[:, None]
    logs = np.zeros_like(conditional); np.log(conditional, out=logs, where=conditional > 0)
    after = float(np.dot(mass, -(conditional*logs).sum(axis=1))/mass.sum())
    return after/entropy if entropy > 0 else np.nan


def cluster_profiles(frame, labels, config_id, k, seed):
    work = frame.copy(); work['cluster'] = labels
    rows = []
    for cluster, group in work.groupby('cluster', observed=True):
        row = dict(config_id=config_id, k=k, seed=seed, cluster=int(cluster), segments=len(group),
            municipalities=group.groupby(MUNICIPAL_KEYS).ngroups, **{field:int(group[field].sum()) for field in METRICS},
            specified_count=int(group.specified_count.sum()), participation_observed=group.SV.sum()/group.specified_count.sum(),
            mean_segment_rate=float(group.participation_observed.mean()), mean_relative_rate=float(group.participation_deviation_national.mean()),
            relative_q1=group.participation_deviation_national.quantile(.25), relative_median=group.participation_deviation_national.median(),
            relative_q3=group.participation_deviation_national.quantile(.75), unspecified_rate=group.NS.sum()/group.LN.sum(),
            high_ns_fraction=group.has_high_unspecified_rate.mean(), few_sections_fraction=group.section_count.lt(5).mean(),
            women_fraction=group.SEXO.eq('1').mean(), dominant_band=group.age_band.value_counts().index[0],
            dominant_band_fraction=group.age_band.value_counts(normalize=True).iloc[0])
        for t in ['U', 'R', 'M']:
            row[f'mean_section_share_{t}'] = group[f'section_ln_share_{t}'].mean()
            row[f'nominal_section_share_{t}'] = group[f'LN_{t}'].sum()/group.LN.sum()
        rows.append(row)
    distribution = work.groupby(['cluster', 'age_band', 'SEXO'], observed=True, as_index=False).agg(
        segments=('row_id', 'size'), LN=('LN', 'sum'), SV=('SV', 'sum'), NV=('NV', 'sum'), NS=('NS', 'sum'),
        mean_relative_rate=('participation_deviation_national', 'mean'))
    distribution['config_id'] = config_id; distribution['k'] = k; distribution['seed'] = seed
    municipal = work.groupby([*MUNICIPAL_KEYS, 'cluster'], observed=True, as_index=False).agg(segments=('row_id', 'size'), LN=('LN', 'sum'))
    municipal['config_id'] = config_id; municipal['k'] = k; municipal['seed'] = seed
    return pd.DataFrame(rows), distribution, municipal


def validate_reference(root, full):
    """Verifica selección original, referencias nacionales y alineación por row_id."""
    require(full.row_id.is_unique and not full.row_id.isna().any(), 'row_id no es único/completo.')
    require(full.election_year.eq(2024).all(), 'Año distinto de 2024.')
    for field in [*MUNICIPAL_KEYS, 'SEXO']:
        require(full[field].map(lambda value:isinstance(value, str)).all(), 'Clave no textual.')
    require(full.LN.eq(full.SV+full.NV+full.NS).all(), 'Conteos no conciliados.')
    require(full.participation_observed.isna().equals(full.specified_count.eq(0)), 'NULL no corresponde a denominador cero.')
    national = full.groupby(['age_band', 'SEXO'], observed=True, as_index=False)[METRICS].sum()
    national['national_participation'] = np.divide(national.SV, national.SV+national.NV,
        out=np.full(len(national), np.nan), where=(national.SV+national.NV).gt(0))
    merged = full.merge(national[['age_band', 'SEXO', 'national_participation']], on=['age_band','SEXO'],
        suffixes=('_previous', '_check'), validate='many_to_one', sort=False)
    require(merged.row_id.equals(full.row_id), 'Orden alterado en la validación nacional.')
    require(np.allclose(merged.national_participation_previous, merged.national_participation_check, equal_nan=True), 'Referencia nacional incorrecta.')
    require(np.allclose(full.participation_deviation_national, full.participation_observed-full.national_participation, equal_nan=True), 'Desviaciones no conciliadas.')
    shares = full[SHARE_COLUMNS].to_numpy(float)
    require(np.isfinite(shares).all() and (shares >= 0).all() and np.allclose(shares.sum(axis=1),1.,rtol=0,atol=1e-12), 'Composición no válida.')
    base = full.age_band.ne('101+') & full.LN.ge(100) & full.specified_count.ge(100) & full.source_row_count.ge(5)
    base &= np.isfinite(full[['participation_observed','participation_deviation_national']].to_numpy()).all(axis=1)
    require(base.equals(full.context_is_eligible) and base.equals(full.is_eligible), 'Umbrales/población cambiados.')
    require(base.sum()==22_282 and full.loc[base].groupby(MUNICIPAL_KEYS).ngroups==2356, 'Universo principal distinto.')
    require(full.sex_2_source_rows.sum()==full.sex_2_nominal_count.sum()==105, 'SEXO=2 perdido.')
    previous = pd.read_parquet(root/'data/processed/demographic_representation_comparison/reference/b_life_stage.parquet')
    require(set(full.row_id)==set(previous.row_id), 'Conjunto previo de row_id distinto.')
    aligned = previous.set_index('row_id').loc[full.row_id]
    require(np.array_equal(aligned.is_eligible, base), 'Selección previa no alineada.')
    compare_sums(full, previous, ['age_band','SEXO',*MUNICIPAL_KEYS])
    return base.to_numpy(), national


def model_record(frame, values, fitted, config_id, config, k, seed, weights):
    labels, margin = margins(values, fitted['centers'])
    require(np.array_equal(labels,fitted['labels']), 'Predicción distinta de entrenamiento.')
    sizes = np.bincount(labels,minlength=k)
    return dict(config_id=config_id, behavior=config['behavior'], geometry=config['geometry'], alpha=config['alpha'], k=k, seed=seed,
        n=len(frame), dimensions=values.shape[1], municipalities=frame.groupby(MUNICIPAL_KEYS).ngroups, LN=int(frame.LN.sum()),
        sse=fitted['inertia'], sse_per_weight=fitted['inertia']/weights.sum(), converged=fitted['converged'], iterations=fitted['iterations'],
        minimum_cluster=int(sizes.min()), maximum_cluster=int(sizes.max()), db=db_index(values,labels),
        margin_q10=float(np.nanquantile(margin,.1)), margin_median=float(np.nanmedian(margin)), low_margin_fraction=float(np.mean(margin<.1)),
        **pattern_diagnostics(frame,values,labels,config), **numerical_check(values,weights,fitted))


def main_experiments(full, base, output, anchor_count, n_init):
    training=full.loc[base].reset_index(drop=True); parameters=fit_blocks(training)
    save_json(output/'metadata/block_parameters.json',parameters)
    anchors=anchor_sample(training.row_id,maximum=anchor_count,seed=319)
    save_table(output/'metadata/silhouette_anchors.parquet',training.loc[anchors,['row_id',*MUNICIPAL_KEYS]])
    metric_rows, init_rows, profile_rows, seed_rows, all_models, best = [], [], [], [], {}, {}
    distribution_parts, municipal_parts = [], []
    for config_id, config in configurations().items():
        values, names=transform_blocks(training,config,parameters)
        save_table(output/f'features/{config_id}.parquet',pd.DataFrame(values,columns=names).assign(row_id=training.row_id)[['row_id',*names]])
        labels_frame=full[['row_id',*MUNICIPAL_KEYS,'age_band','SEXO','context_is_eligible','pending_reason_context']].copy()
        partition={}; records={}
        for k in KS:
            for seed in SEEDS:
                fitted=fit_model(values,k,seed,n_init)
                all_models[config_id,k,seed]=fitted
                token=f'k{k}_seed{seed}'; partition[token]=fitted['labels']
                labels_frame[token]=nullable_labels(full,base,fitted['labels'])
                records[token]=model_record(training,values,fitted,config_id,config,k,seed,np.ones(len(training)))
                init_rows.extend(initialization_records(fitted,config_id=config_id,k=k,fit_seed=seed))
                profiles,distribution,municipal=cluster_profiles(training,fitted['labels'],config_id,k,seed)
                profile_rows.append(profiles); distribution_parts.append(distribution); municipal_parts.append(municipal)
                save_table(output/f'models/{config_id}/centers_{token}.parquet',pd.DataFrame(fitted['centers'],columns=names).rename_axis('cluster').reset_index())
            chosen=min(SEEDS,key=lambda seed:all_models[config_id,k,seed]['inertia'])
            best[config_id,k]=(chosen,all_models[config_id,k,chosen])
            for a,b in combinations(SEEDS,2):
                seed_rows.append(dict(config_id=config_id,k=k,seed_left=a,seed_right=b,
                    ari=adjusted_rand(all_models[config_id,k,a]['labels'],all_models[config_id,k,b]['labels'])))
            labels,margin=margins(values,best[config_id,k][1]['centers'])
            save_table(output/f'models/{config_id}/margins_k{k}.parquet',pd.DataFrame(dict(row_id=training.row_id,cluster=labels,normalized_margin=margin)))
            print(f'{config_id}: K={k}, tres semillas; menor SSE={best[config_id,k][1]["inertia"]:.3f}.',flush=True)
        scores=anchor_silhouettes(values,partition,anchors)
        for token,record in records.items():
            sample=scores[token]
            record.update(silhouette=float(sample.mean()),silhouette_mc_se=float(sample.std(ddof=1)/np.sqrt(len(sample))*np.sqrt((len(training)-len(sample))/len(training))),silhouette_anchor_n=len(sample),silhouette_reference_n=len(training))
            metric_rows.append(record)
        save_table(output/f'models/{config_id}/labels.parquet',labels_frame)
    comparisons=[]
    for k in KS:
        for left,right in combinations(configurations(),2):
            a,b=best[left,k][1]['labels'],best[right,k][1]['labels']
            aligned=align_partition(a,b,k)[0]
            comparisons.append(dict(k=k,left=left,right=right,ari=adjusted_rand(a,b),changed_fraction=float(np.mean(a!=aligned))))
    for name,frame in [('model_metrics',pd.DataFrame(metric_rows)),('initializations',pd.DataFrame(init_rows)),
        ('seed_stability',pd.DataFrame(seed_rows)),('partition_comparisons',pd.DataFrame(comparisons)),
        ('cluster_profiles',pd.concat(profile_rows,ignore_index=True)),('age_sex_distributions',pd.concat(distribution_parts,ignore_index=True))]:
        save_table(output/f'metadata/{name}.csv',frame)
    save_table(output/'metadata/municipality_cluster_distribution.parquet',pd.concat(municipal_parts,ignore_index=True))
    return parameters,best,pd.DataFrame(metric_rows)


def sensitivity_experiments(full,base,parameters,best,output,n_init,anchor_count):
    training=full.loc[base].reset_index(drop=True)
    scopes={'municipality_weight':np.ones(len(training),bool), 'low_ns':~training.has_high_unspecified_rate.to_numpy(),
        'at_least_5_sections':training.section_count.ge(5).to_numpy()}
    rows,coverage,initializations,subgroup_rows,selected_best=[],[],[],[],{}
    for scope,mask in scopes.items():
        frame=training.loc[mask].reset_index(drop=True)
        coverage.append(dict(scope=scope,segments=len(frame),municipalities=frame.groupby(MUNICIPAL_KEYS).ngroups,
            LN=int(frame.LN.sum()),LN_fraction_original=frame.LN.sum()/full.LN.sum(),
            eligible_segment_fraction=mask.mean(),high_ns_segments=int(frame.has_high_unspecified_rate.sum()),
            few_section_segments=int(frame.section_count.lt(5).sum())))
        weighting='equal_municipality' if scope=='municipality_weight' else 'equal_segment'
        weights=fit_weights(frame,weighting)
        for config_id in ROBUST_CONFIGS:
            config=configurations()[config_id];whole,names=transform_blocks(training,config,parameters);values=whole[mask]
            output_labels=full[['row_id',*MUNICIPAL_KEYS,'age_band','SEXO']].copy()
            fit_mask=np.zeros(len(full),bool);fit_mask[np.flatnonzero(base)[mask]]=True
            output_labels['is_training']=fit_mask;output_labels['is_projected_main_eligible']=base & ~fit_mask
            partitions={};records={};models={}
            for k in ROBUST_KS:
                for seed in SEEDS:
                    fitted=fit_model(values,k,seed,n_init,weights if weighting=='equal_municipality' else None)
                    projected,_=predict_nd(whole,fitted['centers']);reference=best[config_id,k][1]['labels']
                    token=f'k{k}_seed{seed}';partitions[token]=fitted['labels'];models[k,seed]=fitted
                    record=model_record(frame,values,fitted,config_id,config,k,seed,weights)
                    record.update(scope=scope,weighting=weighting,ari_common=adjusted_rand(reference[mask],projected[mask]),
                        ari_all_eligible=adjusted_rand(reference,projected),changed_fraction=float(np.mean(reference!=align_partition(reference,projected,k)[0])))
                    records[token]=record
                    initializations.extend(initialization_records(fitted,scope=scope,config_id=config_id,k=k,fit_seed=seed))
                    output_labels['training_'+token]=nullable_labels(full,fit_mask,fitted['labels'])
                    output_labels['projected_'+token]=nullable_labels(full,base,projected)
                chosen=min(SEEDS,key=lambda seed:models[k,seed]['inertia']);selected_best[scope,config_id,k]=models[k,chosen]
            anchors=anchor_sample(frame.row_id,maximum=anchor_count,seed=319)
            scores=anchor_silhouettes(values,partitions,anchors)
            for token,record in records.items(): record['silhouette']=float(scores[token].mean());rows.append(record)
            save_table(output/f'sensitivity/{scope}/{config_id}/labels.parquet',output_labels)
        print(f'Sensibilidad {scope}: {len(frame):,} segmentos; ocho configuraciones.',flush=True)
    # Diagnósticos de grupos especiales sobre las soluciones principales, sin retirar filas.
    for config_id in ROBUST_CONFIGS:
        for k in ROBUST_KS:
            labels=best[config_id,k][1]['labels']
            for flag,mask in [('high_ns',training.has_high_unspecified_rate.to_numpy()),('few_sections',training.section_count.lt(5).to_numpy())]:
                for value in [False,True]:
                    keep=mask==value;frame=training[keep]
                    for cluster in range(k):
                        part=frame[labels[keep]==cluster]
                        subgroup_rows.append(dict(config_id=config_id,k=k,flag=flag,flag_value=value,cluster=cluster,
                            segments=len(part),municipalities=part.groupby(MUNICIPAL_KEYS).ngroups,LN=int(part.LN.sum()),
                            mean_relative_rate=part.participation_deviation_national.mean(),
                            participation_observed=part.SV.sum()/part.specified_count.sum() if len(part) else np.nan))
    for name,frame in [('sensitivity_metrics',pd.DataFrame(rows)),('sensitivity_coverage',pd.DataFrame(coverage)),
        ('sensitivity_initializations',pd.DataFrame(initializations)),('quality_subgroup_profiles',pd.DataFrame(subgroup_rows))]:
        save_table(output/f'metadata/{name}.csv',frame)
    return pd.DataFrame(rows),selected_best


def municipal_resampling(full,base,best,root,output,n_init,replicates):
    """Reutiliza membresías originales: mismo sorteo municipal en todos los modelos."""
    source=root/'data/processed/demographic_representation_comparison/resampling/municipality_membership.parquet'
    samples=pd.read_parquet(source)
    require(2<=replicates<=30 and samples.shape==(2477,32), 'Membresías/repeticiones no válidas.')
    keys=samples[MUNICIPAL_KEYS]
    require(not keys.duplicated().any(), 'Municipios repetidos en membresía.')
    save_table(output/'resampling/municipality_membership.parquet',samples[[*MUNICIPAL_KEYS,*[f'sample_{i:03d}' for i in range(replicates)]]])
    records,coverage,initializations,case_rows=[],[],[],[]
    main=full.loc[base].reset_index(drop=True)
    for replicate in range(replicates):
        draw=samples[f'sample_{replicate:03d}'].to_numpy()
        require(draw.dtype==bool and int(draw.sum())==1981,'Sorteo municipal distinto del validado.')
        chosen=membership(full,keys,draw);mask=chosen & base
        training=full.loc[mask].reset_index(drop=True);inbag=chosen[base];oob=~inbag
        parameters=fit_blocks(training)
        folder=output/f'resampling/sample_{replicate:03d}';folder.mkdir(parents=True)
        save_json(folder/'block_parameters.json',parameters)
        labels_frame=full[['row_id',*MUNICIPAL_KEYS,'age_band','SEXO']].copy()
        labels_frame['is_training']=mask;labels_frame['is_oob_eligible']=base & ~chosen
        coverage.append(dict(replicate=replicate,sampled_municipalities=int(draw.sum()),training_segments=int(mask.sum()),
            training_municipalities=training.groupby(MUNICIPAL_KEYS).ngroups,training_LN=int(training.LN.sum()),
            eligible_LN_fraction=training.LN.sum()/main.LN.sum(),original_LN_fraction=training.LN.sum()/full.LN.sum(),
            sampled_original_segments=int(chosen.sum()),sampled_original_LN=int(full.loc[chosen,'LN'].sum()),
            oob_segments=int(oob.sum()),oob_municipalities=main.loc[oob].groupby(MUNICIPAL_KEYS).ngroups))
        for config_id in ROBUST_CONFIGS:
            config=configurations()[config_id]
            values,_=transform_blocks(training,config,parameters);whole,_=transform_blocks(main,config,parameters)
            for k in ROBUST_KS:
                fitted=fit_model(values,k,17,n_init);projected,_=predict_nd(whole,fitted['centers'])
                reference=best[config_id,k][1]['labels'];aligned=align_partition(reference[oob],projected[oob],k)[0]
                records.append(dict(config_id=config_id,k=k,replicate=replicate,n=len(training),
                    ari_oob=adjusted_rand(reference[oob],projected[oob]),ari_inbag=adjusted_rand(reference[inbag],projected[inbag]),
                    ari_all_eligible=adjusted_rand(reference,projected),oob_changed_fraction=float(np.mean(reference[oob]!=aligned)),
                    minimum_cluster=int(np.bincount(fitted['labels'],minlength=k).min()),
                    **numerical_check(values,np.ones(len(training)),fitted)))
                initializations.extend(initialization_records(fitted,config_id=config_id,k=k,replicate=replicate,fit_seed=17))
                labels_frame[f'{config_id}_k{k}']=nullable_labels(full,base,projected)
                cases=main.loc[oob,MUNICIPAL_KEYS].copy();cases['changed']=reference[oob]!=aligned
                cases=cases.groupby(MUNICIPAL_KEYS,as_index=False).agg(oob_segments=('changed','size'),changed_segments=('changed','sum'))
                cases['config_id']=config_id;cases['k']=k;cases['replicate']=replicate;case_rows.append(cases)
        save_table(folder/'labels.parquet',labels_frame)
        print(f'Submuestra {replicate+1}/{replicates}: {len(training):,} segmentos y {oob.sum():,} OOB.',flush=True)
    for name,frame in [('resampling_metrics',pd.DataFrame(records)),('resampling_coverage',pd.DataFrame(coverage)),
        ('resampling_initializations',pd.DataFrame(initializations))]:save_table(output/f'metadata/{name}.csv',frame)
    save_table(output/'metadata/oob_municipality_changes.parquet',pd.concat(case_rows,ignore_index=True))
    return pd.DataFrame(records),pd.DataFrame(coverage)


def audit_outputs(output,full,base):
    """Comprueba artefactos completos sin volver a ajustar modelos."""
    training=full.loc[base].reset_index(drop=True)
    metrics=pd.read_csv(output/'metadata/model_metrics.csv')
    profiles=pd.read_csv(output/'metadata/cluster_profiles.csv')
    sums=profiles.groupby(['config_id','k','seed'])[METRICS].sum()
    expected=training[METRICS].sum().to_numpy()
    require(np.array_equal(sums.to_numpy(),np.tile(expected,(len(sums),1))),'Conteos de perfiles no conservados.')
    records=[]
    for config_id,group in metrics.groupby('config_id',sort=False):
        values=pd.read_parquet(output/f'features/{config_id}.parquet')
        require(values.row_id.equals(training.row_id),'Orden de características distinto.')
        expected_names=transform_blocks(training,configurations()[config_id],fit_blocks(training))[1]
        require(list(values.columns)==['row_id',*expected_names],'Columnas no autorizadas en distancia.')
        require(np.isfinite(values[expected_names].to_numpy(float)).all(),'Matriz no finita.')
        labels=pd.read_parquet(output/f'models/{config_id}/labels.parquet')
        require(labels.row_id.equals(full.row_id),'Orden de etiquetas distinto.')
        for row in group.itertuples():
            column=f'k{row.k}_seed{row.seed}'
            require(labels.loc[~base,column].isna().all() and labels.loc[base,column].notna().all(),'Pendientes etiquetados o entrenamiento incompleto.')
            require(labels.loc[base,column].nunique()==row.k,'Grupos vacíos en etiquetas escritas.')
        records.append(dict(check='main_labels_and_counts',config_id=config_id,models=len(group),differences=0))
    for path in (output/'resampling').glob('sample_*/labels.parquet'):
        labels=pd.read_parquet(path)
        require(labels.row_id.equals(full.row_id),'Remuestra fuera de orden.')
        require(not (labels.is_training & labels.is_oob_eligible).any(),'OOB usado para entrenar.')
        require(np.array_equal(labels.is_training | labels.is_oob_eligible,base),'Pérdida de elegibles en remuestra.')
        for column in labels.columns:
            if column not in ['row_id',*MUNICIPAL_KEYS,'age_band','SEXO','is_training','is_oob_eligible']:
                require(labels.loc[~base,column].isna().all() and labels.loc[base,column].notna().all(),'Proyección de pendientes no autorizada.')
        records.append(dict(check='oob_labels_and_membership',config_id=path.parent.name,models=len(labels.columns)-7,differences=0))
    for path in (output/'sensitivity').glob('*/*/labels.parquet'):
        labels=pd.read_parquet(path)
        require(labels.row_id.equals(full.row_id),'Sensibilidad fuera de orden.')
        for column in labels.columns:
            if column.startswith('training_'):
                require(labels.loc[~labels.is_training,column].isna().all(),'Proyecciones confundidas con entrenamiento.')
        records.append(dict(check='sensitivity_training_labels',config_id=str(path.parent.relative_to(output)),models=9,differences=0))
    return pd.DataFrame(records)


def previous_incidents(root):
    """Registra intentos fallidos propios conservados, sin tocarlos."""
    archive=root/'data/processed/contextual_clustering_pilot_failed_traceability/metadata/run_manifest.json'
    if not archive.is_file():return []
    return [dict(stage='initial_output_traceability',archive=str(archive.relative_to(root)),
        manifest_sha256=file_hash(archive),status='resolved',
        description='El primer intento se detuvo por colisión entre semilla de ajuste e inicialización. Se separaron fit_seed e initial_seed y se añadió prueba de escritura completa. Sin cambios en fuentes ni resultados previos.')]


def plot_results(full,base,best,metrics,stability,sensitivity,charts):
    training=full.loc[base].reset_index(drop=True)
    colors={.2:'#2788a5',.5:'#c07032',.8:'#8060a8'}
    means=metrics.groupby(['config_id','k'],as_index=False).mean(numeric_only=True)
    fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    for column,geometry in enumerate(['euclidean','hellinger']):
        for alpha in [.2,.5,.8]:
            name=f'pt_{geometry}_w{int(alpha*100)}';frame=means[means.config_id.eq(name)]
            axes[0,column].plot(frame.k,frame.silhouette,'o-',color=colors[alpha],label=f'P+T · contexto {alpha:.0%}')
            axes[1,column].plot(frame.k,frame.db,'o-',color=colors[alpha])
            absolute=means[means.config_id.eq(f'at_{geometry}_w{int(alpha*100)}')]
            axes[0,column].plot(absolute.k,absolute.silhouette,'s--',color=colors[alpha],label=f'A+T · contexto {alpha:.0%}')
            axes[1,column].plot(absolute.k,absolute.db,'s--',color=colors[alpha])
        for name,style,label in [('p','--','P'),('t_'+geometry,':','T')]:
            frame=means[means.config_id.eq(name)]
            axes[0,column].plot(frame.k,frame.silhouette,style,color='gray' if label=='T' else 'black',label=label)
            axes[1,column].plot(frame.k,frame.db,style,color='gray' if label=='T' else 'black')
        axes[0,column].set(title=geometry,ylabel='Silhouette aproximado');axes[0,column].legend(fontsize=8)
        axes[1,column].set(xlabel='K (6: sensibilidad)',ylabel='Davies–Bouldin')
    fig.suptitle('Índices en cada espacio real · no clasifican universalmente las representaciones')
    fig.savefig(charts/'internal_metrics.png',dpi=160);plt.close(fig)
    selected=ROBUST_CONFIGS
    rng=np.random.default_rng(2301);sample=np.sort(rng.choice(len(training),min(12000,len(training)),replace=False))
    shares=training[SHARE_COLUMNS].to_numpy();x=shares[:,1]+.5*shares[:,2];y=np.sqrt(3)/2*shares[:,2]
    fig,axes=plt.subplots(2,4,figsize=(17,8),layout='constrained')
    for ax,name in zip(axes.flat,selected):
        ax.scatter(x[sample],y[sample],c=best[name,4][1]['labels'][sample],s=3,cmap='tab10',vmin=0,vmax=9,alpha=.4,rasterized=True)
        ax.plot([0,1,.5,0],[0,0,np.sqrt(3)/2,0],color='black',linewidth=.6)
        ax.set(title=f'{name} · K=4',xlim=(-.04,1.04),ylim=(-.05,.92),xticks=[],yticks=[])
        for label,xx,yy in [('U',0,-.04),('R',1,-.04),('M',.5,.88)]:ax.text(xx,yy,label,ha='center')
    fig.suptitle('Vista de composición original · omite participación y no conserva la geometría Hellinger\nColores locales a cada ajuste; 12,000 segmentos sólo para dibujar')
    fig.legend(handles=[Line2D([0],[0],marker='o',linestyle='',color=plt.get_cmap('tab10')(i),label=f'Etiqueta local {i}')
        for i in range(4)],loc='outside lower center',ncol=4)
    fig.savefig(charts/'composition_views.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,4,figsize=(17,8),layout='constrained')
    for ax,name in zip(axes.flat,selected):
        labels=best[name,4][1]['labels'];groups=[training.loc[labels==c,'participation_deviation_national'].to_numpy()*100 for c in range(4)]
        ax.boxplot(groups,tick_labels=[str(c) for c in range(4)],showfliers=False)
        ax.axhline(0,color='gray',linewidth=.6);ax.set(title=name,xlabel='Etiqueta local · K=4',ylabel='Diferencia nacional (pp)',ylim=(-60,65))
    fig.suptitle('Distribución de participación relativa por cluster · variables originales\nLas cajas omiten puntos atípicos del dibujo; todos se conservan en cálculos y tablas')
    fig.savefig(charts/'participation_distributions.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,4,figsize=(17,9),layout='constrained')
    for ax,name in zip(axes.flat,selected):
        frame=training[['age_band','SEXO']].copy();frame['cluster']=best[name,4][1]['labels']
        frame['demographic_cell']=frame.age_band+' · '+frame.SEXO.map({'0':'H','1':'M'})
        counts=pd.crosstab(frame.demographic_cell,frame.cluster)
        proportions=counts/counts.sum(axis=0)
        image=ax.imshow(proportions,vmin=0,vmax=.5,cmap='Blues',aspect='auto')
        ax.set(title=name,xticks=range(4),xticklabels=range(4),yticks=range(len(counts)),yticklabels=counts.index,xlabel='Etiqueta local · K=4')
    fig.colorbar(image,ax=axes,label='Fracción de segmentos del cluster en esa edad/sexo')
    fig.suptitle('Composición demográfica de las etiquetas · H hombres, M mujeres\nEdad y sexo son metadatos; no coordenadas de distancia')
    fig.savefig(charts/'demographic_composition.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(15,5),layout='constrained')
    for k in [3,4,5]:
        for geometry,style in [('euclidean','-'),('hellinger','--')]:
            names=[f'pt_{geometry}_w{weight}' for weight in [20,50,80]]
            frame=means[means.k.eq(k)].set_index('config_id').loc[names]
            for ax,field in zip(axes,['within_age_sex_context_5_rate_r2','context_share_between','municipality_label_purity']):
                ax.plot([.2,.5,.8],frame[field],style,marker='o',label=f'{geometry} · K={k}')
    for ax,title in zip(axes,['R² tasa dentro de edad/sexo/contexto','Fracción de separación aportada por contexto','Pureza de etiqueta dentro de municipio']):
        ax.set(title=title,xlabel='Peso predefinido del contexto',ylim=(0,1));ax.yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].legend(fontsize=7)
    fig.suptitle('Consecuencias de aumentar el peso contextual · descriptivos in-sample')
    fig.savefig(charts/'block_tradeoffs.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(13,7),layout='constrained')
    labels=[f'{name} · K={k}' for name in ROBUST_CONFIGS for k in ROBUST_KS]
    arrays=[stability.loc[stability.config_id.eq(name)&stability.k.eq(k),'ari_oob'].to_numpy() for name in ROBUST_CONFIGS for k in ROBUST_KS]
    ax.boxplot(arrays,orientation='horizontal',tick_labels=labels,showfliers=True)
    ax.set(xlabel='ARI en municipios OOB frente al ajuste completo',xlim=(0,1.02),title='Submuestras municipales compartidas · incluye casos extremos')
    fig.savefig(charts/'municipality_stability.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(17,8),layout='constrained')
    for name in selected:
        config=configurations()[name];parameters=fit_blocks(training);matrix,_=transform_blocks(training,config,parameters)
        _,margin=margins(matrix,best[name,4][1]['centers']);margin=np.sort(margin[np.isfinite(margin)])
        axes[0].plot(margin,np.arange(1,len(margin)+1)/len(margin),label=name)
        frame=sensitivity[sensitivity.config_id.eq(name)&sensitivity.k.eq(4)]
        for scope,group in frame.groupby('scope'):
            axes[1].scatter(group.changed_fraction.mean(),name+' · '+scope,s=25)
    axes[0].set(xlabel='Margen (d₂−d₁)/d₂',ylabel='Fracción acumulada',title='Márgenes · K=4 (no son probabilidades)')
    axes[0].legend(fontsize=7);axes[1].set(xlabel='Fracción de cambios tras alinear',title='Cambios al variar pesos o cobertura · K=4')
    axes[0].yaxis.set_major_formatter(PercentFormatter(1));axes[1].xaxis.set_major_formatter(PercentFormatter(1))
    fig.savefig(charts/'margins_and_sensitivity.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(11,10),layout='constrained')
    names=list(configurations());matrix=np.eye(len(names))
    for i,j in combinations(range(len(names)),2):matrix[i,j]=matrix[j,i]=adjusted_rand(best[names[i],4][1]['labels'],best[names[j],4][1]['labels'])
    image=ax.imshow(matrix,vmin=0,vmax=1,cmap='viridis');ax.set(xticks=range(len(names)),yticks=range(len(names)),xticklabels=names,yticklabels=names,title='ARI entre representaciones · K=4 · misma población')
    plt.setp(ax.get_xticklabels(),rotation=90);fig.colorbar(image,ax=ax)
    fig.savefig(charts/'partition_agreement.png',dpi=160);plt.close(fig)


def summary_tables(metrics,stability,sensitivity):
    rows=[]
    for (name,k),group in metrics.groupby(['config_id','k'],sort=False):
        row=group.mean(numeric_only=True).to_dict();row.update(config_id=name,k=int(k))
        oob=stability[stability.config_id.eq(name)&stability.k.eq(k)].ari_oob
        row.update(oob_median=oob.median(),oob_q10=oob.quantile(.1),oob_min=oob.min(),oob_below_90=int(oob.lt(.9).sum()),oob_n=len(oob))
        for scope,selected in sensitivity[sensitivity.config_id.eq(name)&sensitivity.k.eq(k)].groupby('scope'):
            row[f'{scope}_ari']=selected.ari_all_eligible.mean()
            row[f'{scope}_changed_fraction']=selected.changed_fraction.mean()
        rows.append(row)
    return pd.DataFrame(rows)


def write_report(root,output,charts,report,full,metrics,stability,sensitivity,coverage,protected_count,anchor_count,n_init):
    summary=summary_tables(metrics,stability,sensitivity)
    seed=pd.read_csv(output/'metadata/seed_stability.csv')
    seed_summary=seed.groupby(['config_id','k'],as_index=False).agg(seed_ari_min=('ari','min'),seed_ari_median=('ari','median'))
    summary=summary.merge(seed_summary,on=['config_id','k'],validate='one_to_one')
    summary_path=output/'metadata/comparison_summary.csv'
    if summary_path.exists():
        pd.testing.assert_frame_equal(pd.read_csv(summary_path),summary,check_dtype=False,check_exact=False,rtol=1e-9,atol=1e-10)
    else:save_table(summary_path,summary)
    comparisons=pd.read_csv(output/'metadata/partition_comparisons.csv')
    profiles=pd.read_csv(output/'metadata/cluster_profiles.csv')
    count_scopes=pd.read_csv(output/'metadata/sensitivity_coverage.csv')
    main=full[full.context_is_eligible]
    def figure(name,title):return f'![{title}]({Path(os.path.relpath(charts/name,report.parent)).as_posix()})'
    def format_value(value):
        if isinstance(value,(bool,np.bool_)):return 'Sí' if value else 'No'
        if isinstance(value,(int,np.integer)):return f'{value:,}'
        if isinstance(value,(float,np.floating)):return 'n/d' if pd.isna(value) else f'{value:.4f}'
        return str(value)
    def table(frame,columns,headers=None):return markdown_table(headers or columns,[[format_value(row[column]) for column in columns] for _,row in frame.iterrows()])
    chosen=summary[summary.config_id.isin(ROBUST_CONFIGS)&summary.k.isin(ROBUST_KS)].copy()
    for field in ['within_age_sex_rate_r2','within_age_sex_context_5_rate_r2','context_share_between','municipality_label_purity','low_margin_fraction']:
        chosen[field]=chosen[field].map(pct)
    def example(name,k=4):return summary[(summary.config_id==name)&(summary.k==k)].iloc[0]
    p,low,balanced,territorial=[example(name) for name in ['p','pt_hellinger_w20','pt_hellinger_w50','t_hellinger']]
    high=example('pt_hellinger_w80')
    low_ari=comparisons[(comparisons.k==4)&(comparisons.left=='p')&(comparisons.right=='pt_hellinger_w20')].iloc[0]
    candidate_comparisons=comparisons[comparisons.k.eq(4)&(comparisons.left.eq('p')|comparisons.left.eq('t_hellinger'))].copy()
    sorted_oob=stability.sort_values('ari_oob').head(12)
    profile_sample=[]
    for name in ['p','t_hellinger','pt_hellinger_w20','pt_hellinger_w50','at_hellinger_w50']:
        group=metrics[metrics.config_id.eq(name)&metrics.k.eq(4)]
        selected_seed=int(group.loc[group.sse.idxmin(),'seed'])
        profile_sample.append(profiles[profiles.config_id.eq(name)&profiles.k.eq(4)&profiles.seed.eq(selected_seed)])
    profile_sample=pd.concat(profile_sample,ignore_index=True)
    for field in ['participation_observed','mean_section_share_U','mean_section_share_R','mean_section_share_M','high_ns_fraction','few_sections_fraction','women_fraction']:
        profile_sample[field]=profile_sample[field].map(pct)
    profile_sample['mean_relative_rate']=profile_sample.mean_relative_rate*100
    kscan=summary[summary.config_id.isin(['p','t_hellinger','pt_hellinger_w20','pt_hellinger_w50'])].copy()
    for field in ['within_age_sex_context_5_rate_r2','context_share_between']:kscan[field]=kscan[field].map(pct)
    sensitivity_summary=summary[summary.config_id.isin(ROBUST_CONFIGS)&summary.k.isin(ROBUST_KS)]
    stable_summary=sensitivity_summary.sort_values(['oob_min','oob_median'],ascending=False).head(6)
    incident_text=('metadata/incidents.json registra el intento inicial detenido por colisión de nombres entre semilla del ajuste y semilla de inicialización. Se corrigió antes de la ejecución completa y se añadió una prueba de escritura de artefactos desde directorio vacío; el intento queda archivado sin _SUCCESS. No se modificaron datos previos.'
        if previous_incidents(root) else 'No se detectaron intentos fallidos propios archivados en este proyecto.')
    test_path=output/'metadata/test_validation.json'
    test_text='El comando de pruebas se incluye al final para reproducir las verificaciones.'
    if test_path.is_file():
        tests=json.loads(test_path.read_text(encoding='utf-8'))
        test_text=f"Pasaron {tests['project_tests_passed']} pruebas del proyecto, incluidas {tests['new_tests_passed']} de este piloto. El registro queda en metadata/test_validation.json."
    text=f'''# Piloto K-Means con contexto electoral U/R/M · 2024

## Resultado y alcance

Se compararon **P**, participación relativa; **T**, composición nominal U/R/M; **P+T**; y **A+T**, participación absoluta más contexto, sobre exactamente **22,282 segmentos de 2,356 municipios**. Ningún modelo incorpora edad media, SEXO, municipio, distrito o claves como coordenadas. La unidad sigue siendo municipio × intervalo candidato × sexo: son segmentos agregados, no personas ni perfiles individuales de residencia.

El contexto introduce una dimensión territorial medible; que una partición sea más compacta o estable no prueba que descubra mejores perfiles de participación. En K=4, P explica {pct(p.within_age_sex_context_5_rate_r2)} de la variación de tasas dentro de los mismos intervalos/sexos y celdas contextuales descriptivas; P+T Hellinger con 20 % y 50 % de contexto explica {pct(low.within_age_sex_context_5_rate_r2)} y {pct(balanced.within_age_sex_context_5_rate_r2)}, respectivamente. T Hellinger explica {pct(territorial.within_age_sex_context_5_rate_r2)} en esa misma evaluación. Son medidas in-sample y no efectos causales ni capacidad predictiva.

Las fracciones de separación aportadas por contexto en P+T Hellinger son {pct(low.context_share_between)} (peso 20 %) y {pct(balanced.context_share_between)} (peso 50 %). Sus purezas municipales son {pct(low.municipality_label_purity)} y {pct(balanced.municipality_label_purity)}, frente a {pct(p.municipality_label_purity)} en P. La composición puede hacer que muchos segmentos de un municipio compartan etiqueta, aunque su identidad jamás entre como variable.

Con 20 % contextual, P+T Hellinger tiene ARI={low_ari.ari:.4f} respecto a P en la solución de menor SSE de K=4 y sólo {pct(low.context_share_between)} de separación contextual: añade poca diferenciación territorial a esas etiquetas. Con 80 %, el contexto explica {pct(high.context_share_between)} de la separación y la variación de participación condicional explicada cae a {pct(high.within_age_sex_context_5_rate_r2)}. Los pesos pueden pasar de casi reproducir niveles relativos a casi reproducir contextos municipales.

La sensibilidad de calidad limita cualquier promoción: al exigir ≥5 secciones distintas para entrenar, el ARI sobre todas las predicciones principales de K=4 es {p.at_least_5_sections_ari:.4f} en P, {low.at_least_5_sections_ari:.4f} en P+T Hellinger reducido y {balanced.at_least_5_sections_ari:.4f} en P+T Hellinger equilibrado. Cambian población y distribución de variables; no se estima un efecto causal de tener pocas secciones. Esta sensibilidad no queda resuelta por estabilidad entre semillas o por submuestras municipales aleatorias.

**Recomendación provisional:** si el objetivo es distinguir participación, conservar P como control y describir U/R/M por separado antes de darles peso en la distancia. Si el objetivo se redefine explícitamente como una tipología conjunta de participación y contexto, P+T equilibrado ofrece una lectura interpretable para revisión electoral, con P+T reducido y T como controles, pero **no debe promoverse sin resolver su sensibilidad a cobertura/secciones**. El equilibrio permite describir diferencias relativas en composiciones distintas, pero no ha mejorado la separación de participación frente a P. No hay un ganador definitivo de geometría, peso, K o perfiles. La utilidad no se selecciona por el Silhouette más alto.

## Población y validación previa

Se verificaron _SUCCESS, manifiestos y hashes de los resultados previos. La referencia contextual conserva los **27,650 segmentos**, incluidos 101+, SEXO=2 y los pendientes. LN/SV/NV/NS suman 98,330,348 / 54,899,228 / 37,105,466 / 6,325,654 y representan 9,773,730 filas fuente. La población principal conserva LN=98,090,941, {pct(main.LN.sum()/full.LN.sum())} del original; quedan 5,368 pendientes con etiquetas de entrenamiento NULL. SEXO=2 mantiene 105 filas fuente y LN=105 sin integrarse a H/M; sus segmentos no superan el soporte anterior.

Selección inalterada: 18–100, LN≥100, SV+NV≥100, filas fuente≥5 y variables finitas. Se concilió con la selección demográfica previa por row_id; claves únicas, orden común y tasas se contrastaron con conteos. Las proporciones U/R/M son finitas, no negativas y suman uno. Las referencias nacionales se recalculan sólo como validación de los agregados existentes: suma SV/suma(SV+NV) del mismo intervalo/sexo **antes** de filtrar soporte. Se conservan las referencias fijas, no se reemplazan por medias de tasas elegibles ni se intercambian con referencias de edad exacta.

Se leyeron exclusivamente Parquet agregados y artefactos de análisis; no CSV originales ni filas individuales de la base limpia. Los CSV de métricas derivados sí se usan para revisar y documentar resultados. Se conservan conteos, denominadores, edad/sexo, etiquetas territoriales, marco distrital y número de secciones como metadatos, junto con la trazabilidad hacia la referencia exacta anterior.

## Geometría y pesos de bloques predefinidos

P y A se centran por su media y se dividen por su DE poblacional, ajustadas únicamente sobre la población elegible. No se utilizan simultáneamente ambas como coordenadas. Para T se comparan:

1. **Euclídea en proporciones:** q=(pU,pR,pM).
2. **Tipo Hellinger:** q=(√pU,√pR,√pM)/√2. Admite ceros exactos, sin pseudoconteos; la distancia entre dos q es la Hellinger bajo esta convención. El uso de raíces de probabilidades tiene una interpretación geométrica documentada en [Knuth, investigación primaria](https://arxiv.org/abs/1603.08427).

Cada bloque T se centra por su vector medio y se divide por **una sola escala** sT=√media(||q−media(q)||²). No se estandariza cada categoría por separado ni se aplica whiten. Se mantiene la simetría de las categorías y la restricción composicional: las tres proporciones tienen dos grados de libertad afines; en raíces la superficie es curva y ocupa tres coordenadas sin representar tres evidencias independientes. Tras calibrar, P/A tiene varianza uno y T tiene varianza total uno. La constante 1/√2 queda absorbida por la calibración, pero la diferencia de geometría respecto a proporciones permanece.

Distancia compuesta: **d²=(1−α)·dP²+α·dT²**. Coordenadas almacenadas: √(1−α)·P_z y √α·T_calibrado. Pesos predefinidos α=0.20, 0.50, 0.80; controles P solo y T solo. Hay 15 configuraciones: P, dos T, seis P+T y seis A+T. El peso controla la variación total a priori de los bloques; no fuerza la contribución observada entre clusters a ese porcentaje. El término de cada bloque en la separación se calcula posteriormente por suma de cuadrados entre centroides. No es importancia causal.

Calibración y escala de bloques se guardan en metadata/block_parameters.json. Se fijan al comparar pesos municipales y sensibilidades NS/secciones para aislarlas de cambios de escala. Cada submuestra municipal reajusta sus parámetros sólo con segmentos in-bag. La referencia nacional permanece contextual y fija, incluso para municipios OOB: no es validación predictiva independiente de todo el proceso nacional.

K-Means calcula medias en el espacio transformado. Los centroides Hellinger no se fuerzan de nuevo a la esfera ni se interpretan al cuadrado como una composición media original. Los perfiles descriptivos de U/R/M se obtienen directamente de las proporciones originales y sus LN. [Objetivo y pesos de KMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html).

## Ajustes y métricas

Se usa K-Means n-dimensional existente en clustering_core.py: K=2…5 y 6 sensibilidad, semillas 17/42/2024, {n_init} inicializaciones k-means++ por ajuste, máximo 1,000 iteraciones y parada con asignaciones estables. Se ejecutaron **225 ajustes principales**. Los mismos identificadores y semillas se usan en todas las geometrías; k-means++ puede escoger distintos índices al cambiar las distancias. Los inicios no constituyen un banco común entre todas las representaciones. Al comparar pesos para una misma población/geometría se regenera el mismo banco de centros iniciales, modificando el objetivo ponderado.

El principal da peso uno por segmento. La sensibilidad de peso total uno por municipio usa 1/n_segmentos_elegibles_del_municipio; la extensión dimensional del Lloyd ponderado previo recorre p columnas sin modificar su criterio. Se prueba contra el Lloyd anterior en dos dimensiones, contra replicación literal de pesos enteros y contra el K-Means n-dimensional existente con pesos uno. No se modificaron implementaciones previas.

Silhouette usa {anchor_count} anclas uniformes compartidas, cada una contra los 22,282 puntos, por bloques de hasta 32×N. Se guardan error Monte Carlo y bases. No se construye matriz N×N. DB usa toda la población; centroides aritméticos para su definición habitual incluso bajo entrenamiento ponderado. Las métricas no ponderadas son descriptores comunes de evaluación. En subconjuntos NS/secciones se calculan sobre su propio entrenamiento y no tienen la misma población de evaluación. [Silhouette](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html), [Davies–Bouldin](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.davies_bouldin_score.html).

**No se comparan SSE o índices internos entre espacios como una clasificación universal de utilidad.** P es un control unidimensional; T evalúa composición; P+T cambia la pregunta. Una métrica mayor puede reflejar categorías contextuales casi puras. La menor SSE entre semillas se usa para representar cada configuración/K sin decidir cuál K es verdadero.

## Separación de participación, contexto y municipio

Medias de tres semillas; OOB mediana/mínimo sobre submuestras compartidas. R² condicional compara residuos antes y después de añadir la etiqueta local; no mide ajuste fuera de muestra ni incertidumbre de votantes. La rejilla contextual descriptiva tiene anchura 0.20 en pR y pM (pU implícita), junto con edad/sexo; sólo evalúa celdas con al menos 20 segmentos. Se guarda también anchura 0.10 y su población evaluable. No son nuevos intervalos de edad ni clusters de entrenamiento. El control T muestra cuánto puede variar el índice sólo por refinar contextos dentro de una rejilla todavía gruesa.

{table(chosen,['config_id','k','silhouette','db','within_age_sex_rate_r2','within_age_sex_context_5_rate_r2','context_share_between','municipality_label_purity','low_margin_fraction','seed_ari_min','oob_median','oob_min'],['Configuración','K','S anclas','DB','R² dentro edad/sexo','R² dentro edad/sexo/contexto','Contexto/separación','Pureza municipal','Margen<0.1','ARI semillas mín.','ARI OOB mediana','ARI OOB mín.'])}

La pureza municipal = Σmunicipio máximo número de segmentos en una etiqueta / N. Es un diagnóstico descriptivo, sesgado por municipios con pocos segmentos, no un test de dependencia ni exactitud. Se conserva además H(cluster|municipio)/H(cluster), fracción de municipios con una sola etiqueta, ARI/pureza de banda y R² de edad (sólo diagnóstico). Municipio nunca entra en la distancia.

{figure('block_tradeoffs.png','Participación y contexto al variar pesos')}

{figure('internal_metrics.png','Índices en sus espacios propios')}

Las participaciones absoluta y relativa dentro de cluster son descriptivas. El perfil usa ΣSV/Σ(SV+NV) para participación agregada y media simple de diferencias para participación relativa media; los dos denominadores no son intercambiables. Composición media por segmento y composición ponderada por LN se guardan separadamente.

Ejemplos K=4, menor SSE entre semillas por configuración; etiquetas locales sin identidad entre ajustes:

{table(profile_sample,['config_id','cluster','segments','municipalities','participation_observed','mean_relative_rate','mean_section_share_U','mean_section_share_R','mean_section_share_M','dominant_band','women_fraction','high_ns_fraction','few_sections_fraction'],['Configuración','Etiqueta','Segmentos','Municipios','Participación agregada','Δ medio (pp)','Media U','Media R','Media M','Banda dominante','Mujeres','NS alto','<5 secciones'])}

Los municipios de distintos clusters se superponen porque un municipio aporta varios segmentos. No sumarlos como territorios únicos. Las distribuciones completas de intervalos/sexo y segmentos por municipio se guardan para cada semilla/K; no se infieren conductas individuales o residencia efectiva a partir de TIPOSEC. Las diferencias pueden reflejar cobertura, composición y contexto electoral, sin causalidad demostrada.

{figure('participation_distributions.png','Diferencias de participación por cluster')}

{figure('demographic_composition.png','Distribuciones por edad y sexo')}

{figure('composition_views.png','Vista composicional de las etiquetas')}

La vista triangular muestra únicamente proporciones originales. Omite la coordenada de participación y no preserva la métrica Hellinger. No se usa una proyección bidimensional para afirmar separación del espacio completo. Las métricas se calculan con todas las coordenadas transformadas.

## Concordancia, márgenes y sensibilidad de calidad

ARI se calcula sólo sobre los mismos row_id; números de etiqueta arbitrarios se alinean por máximo solapamiento para contar cambios. No se compara ARI con modelos de edad exacta porque sus unidades son diferentes. Aquí sí se comparan P/T/P+T/A+T sobre población común:

{table(candidate_comparisons,['left','right','k','ari','changed_fraction'],['Izquierda','Derecha','K','ARI','Fracción de cambio alineada'])}

{figure('partition_agreement.png','ARI entre representaciones')}

Margen=(d₂−d₁)/d₂ sobre distancias a los dos centros más cercanos, con NULL si d₂=0. No es probabilidad, confianza ni error validado. metadata/model_metrics.csv contiene q10, mediana y fracción<0.1; modelos/*/margins_kK.parquet conserva cada segmento. Compararlo entre geometrías describe ambigüedad relativa en cada espacio, no una mejora electoral automática.

Sensibilidades predefinidas para P, T euclídea/Hellinger, P+T 20/50 % en ambas geometrías y A+T Hellinger 50 %, K=3/4/5. Se preservan todos los registros; estas vistas cambian el entrenamiento, sin redefinir el principal. NS<10 % no estima qué habrían votado los NS. Exigir ≥5 secciones distintas es un diagnóstico separado, no un nuevo umbral oficial de limpieza.

{table(count_scopes,['scope','segments','municipalities','LN','LN_fraction_original','high_ns_segments','few_section_segments'],['Sensibilidad','Segmentos entrenados','Municipios','LN','Fracción LN original','NS alto','<5 secciones'])}

El siguiente ARI evalúa las predicciones sobre **todos los elegibles principales** para mantener la misma base. Los archivos conservan además ARI sobre el entrenamiento común cuando cambia NS/secciones. Promedios de las tres semillas:

{table(sensitivity_summary,['config_id','k','municipality_weight_ari','low_ns_ari','at_least_5_sections_ari','municipality_weight_changed_fraction','low_ns_changed_fraction','at_least_5_sections_changed_fraction'],['Configuración','K','ARI peso municipal','ARI NS<10 %','ARI ≥5 secciones','Cambio peso','Cambio NS','Cambio secciones'])}

{figure('margins_and_sensitivity.png','Márgenes y sensibilidad')}

Los 4,423 segmentos NS alto y los 5,217 con menos de cinco secciones están incluidos en el principal; sus perfiles se estudian por separado en metadata/quality_subgroup_profiles.csv. source_row_count cuenta celdas sección/edad/sexo; cinco filas no equivalen a cinco secciones. Las proyecciones de segmentos fuera de cada ajuste se distinguen de etiquetas de entrenamiento. Ponderación municipal puede cambiar influencia pero no recupera municipios sin segmentos elegibles ni corrige por sí sola sesgos de captura. LN no se usa como peso de ajuste en esta entrega.

## Estabilidad municipal y casos extremos

Se reutilizan las primeras **{coverage.replicate.nunique()} membresías** de las 30 submuestras anteriores, sin reemplazo, 1,981 de 2,477 municipios originales por muestra. Todos los segmentos elegibles de un municipio entran juntos. Las mismas claves se emplean en las ocho configuraciones robustas y K=3/4/5. Cada remuestra usa semilla 17, {n_init} arranques y escala ajustada sólo in-bag; se predice después en todos los elegibles y se compara con el mejor ajuste completo para esa geometría/K. Estos ensayos OOB utilizan peso igual por segmento; la sensibilidad de peso municipal se estudia en población completa, sin afirmar estabilidad OOB de esa ponderación.

Rango de cobertura: {int(coverage.training_segments.min()):,}–{int(coverage.training_segments.max()):,} segmentos, {pct(coverage.eligible_LN_fraction.min())}–{pct(coverage.eligible_LN_fraction.max())} del LN elegible, {int(coverage.oob_segments.min()):,}–{int(coverage.oob_segments.max()):,} segmentos OOB. Se conservan municipios sorteados sin segmentos elegibles y bases OOB. Son submuestras exploratorias limitadas, no bootstrap, intervalos de confianza ni validación independiente de la referencia nacional fija. K=2/6 tienen sensibilidad entre semillas en población completa, sin remuestreo municipal en este piloto.

Los doce casos de menor ARI OOB, sin ocultar las colas, son:

{table(sorted_oob,['config_id','k','replicate','ari_oob','ari_inbag','oob_changed_fraction','minimum_cluster'],['Configuración','K','Muestra','ARI OOB','ARI in-bag','Cambio OOB alineado','Grupo mínimo'])}

{figure('municipality_stability.png','Estabilidad municipal y extremos')}

Las seis configuraciones/K con mayor mínimo OOB entre los candidatos revisados son las siguientes. Este orden describe robustez en estas submuestras; no selecciona utilidad electoral ni favorece un número de perfiles por un índice interno:

{table(stable_summary,['config_id','k','seed_ari_min','oob_median','oob_q10','oob_min','oob_below_90'],['Configuración','K','ARI semillas mín.','OOB mediana','OOB q10','OOB mínimo','Muestras OOB<0.90'])}

metadata/oob_municipality_changes.parquet identifica los municipios con cambios en cada remuestra. ARI es concordancia de asignaciones y no precisión frente a clases verdaderas. Medianas altas no invalidan mínimos bajos. La perturbación combina selección municipal, cambio de escala y optimización finita; no permite atribuir todos los cambios a un solo factor.

## ¿Se justifican cuatro a seis grupos?

Se evaluó K=2…6; no se impuso el rango 4–6. Cambian unidades de distancia y compacidad al añadir contexto; una partición estable de T puede corresponder principalmente a mezcla urbana/rural/mixta, no a varios comportamientos electorales. La comparación completa de controles y dos pesos Hellinger es:

{table(kscan,['config_id','k','silhouette','db','minimum_cluster','within_age_sex_context_5_rate_r2','context_share_between','oob_median'],['Configuración','K','S anclas','DB','Grupo mínimo medio','R² condicional','Contexto/separación','ARI OOB mediana'])}

K-Means siempre construye K particiones si converge. Ni Silhouette, DB, SSE ni estabilidad por sí solos prueban un número natural de perfiles. No hay en esta etapa base suficiente para fijar cuatro, cinco o seis perfiles definitivos; K menores deben permanecer como controles y la elección debe depender de pregunta, redundancia, márgenes, estabilidad y validación electoral.

Por ejemplo, en P el Silhouette medio es mayor con K=2 ({example('p',2).silhouette:.4f}) que con K=4 ({p.silhouette:.4f}), mientras DB favorece una resolución mayor dentro del rango ensayado. En T euclídea, el máximo S aparece con K=3. Esos desacuerdos dentro de espacios distintos y las diferencias cercanas a la precisión de anclas no autorizan imponer 4–6. Aumentar el R² descriptivo al aumentar K tampoco prueba grupos naturales.

## Evidencia, hipótesis y siguientes decisiones

**Evidencia observada:** cobertura común, cambios ARI, separación de cada bloque, diferencias de participación condicionales, distribución territorial, márgenes y estabilidad de estos ajustes. **Hipótesis:** un peso contextual reducido podría producir una tipología útil para comparar participación en contextos electorales, mientras que pesos altos podrían reproducir sobre todo composición municipal. Esa utilidad no queda probada por un índice interno. **Pendiente:** si se busca agrupar niveles de participación o contextos, geometría y pesos admisibles, confiabilidad por secciones/NS, evaluación con referentes electorales y ampliación de remuestras antes de seleccionar candidatos finales.

Para avanzar, aclarar primero si se busca participación o una tipología conjunta con contexto. En el primer caso, conservar P y U/R/M como diagnóstico descriptivo; P sigue siendo un control unidimensional, no un perfil multivariable nuevo. En el segundo, revisar P+T equilibrado frente a P, T y P+T reducido sin fijar todavía geometría o K; mantener A+T como control de niveles absolutos. Si el objetivo es territorial y los segmentos repiten principalmente composición municipal, considerar perfiles C de municipios con tasas por edad/sexo y contexto separado, revisando antes completitud y soporte. No confundir esa alternativa con tipos individuales de ciudadanos.

## Integridad, pruebas y reproducción

Se comprobaron alineación row_id, selección idéntica, referencia nacional, categorías de texto, composición exhaustiva, finitud, conservación LN=SV+NV+NS y conteos SEXO=2; parámetros ajustados sólo en poblaciones declaradas; convergencia y K grupos no vacíos; centroides/SSE por groupby separado; NULL de pendientes; conteos por cluster; lectura posterior de Parquet; membresías municipales compartidas. Las pruebas incluyen geometrías con ceros, invariancia al orden de U/R/M, pesos, contribuciones, márgenes, métricas por bloques y una ejecución pequeña completa de los componentes numéricos.

{test_text}

{incident_text} Los cambios municipales OOB se alinean con la misma correspondencia de etiquetas usada para el porcentaje de cambio OOB.

Scikit-learn/SciPy no están importables en este entorno; se registran sondeos en metadata/dependencies.json sin instalar paquetes. Los contrastes matemáticos y con implementaciones previas no sustituyen una validación con biblioteca independiente. Se verificaron hashes de **{protected_count:,} archivos previos** antes/después; no se modificaron fuentes, resultados, informes anteriores ni frontend. No se ajustaron otros algoritmos ni se crearon commits.

Entregables: reference/ (todos los segmentos, pendientes y referencia nacional), features/ (coordenadas nuevas), models/ (etiquetas, centros y márgenes), sensitivity/ (entrenamiento y proyecciones separados), resampling/ (membresías, escalas y etiquetas), metadata/ (métricas, perfiles, distribuciones, conciliaciones y manifiesto). Cada representación es una vista alternativa, nunca se suman sus conteos entre sí. El marcador _SUCCESS se escribe únicamente al terminar validaciones e informe.

```powershell
.venv/Scripts/python.exe analysis/scripts/run_contextual_clustering_pilot.py
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_run_contextual_clustering_pilot.py
```

Destinos existentes protegidos; repetir con --output, --charts y --report nuevos. --replicates (2…30) controla las membresías compartidas; --anchor-count y --n-init controlan precisión Monte Carlo y arranques. Las tasas originales permanecen como proporciones; tablas o ejes indicados en porcentaje o puntos porcentuales sólo cambian su presentación.
'''
    report.write_text(text,encoding='utf-8')


def validate_sources(root,protected):
    for name in ['contextual_feature_review','demographic_representation_comparison']:
        source=root/'data/processed'/name;manifest_path=source/'metadata/run_manifest.json'
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        marker=json.loads((source/'_SUCCESS').read_text(encoding='utf-8'))
        require(manifest['status']=='validated' and marker['manifest_sha256']==file_hash(manifest_path),'Fuente sin validación completa.')
        for relative,digest in manifest['artifact_hashes'].items():
            require(protected[str(root/relative)]==digest,f'Artefacto previo alterado: {relative}')
    for name in ['contextual_feature_review.md','clustering_methods_review.md','demographic_representation_comparison.md']:
        require((root/'analysis/reports'/name).is_file(),'Falta informe previo requerido.')


def run_pilot(root,output,charts,report,anchor_count=512,n_init=10,replicates=10):
    root,output,charts,report=[Path(path).resolve() for path in [root,output,charts,report]]
    require(output.is_relative_to(root/'data/processed') and charts.is_relative_to(root/'analysis/charts') and report.is_relative_to(root/'analysis/reports'),'Destinos fuera de áreas autorizadas.')
    require(not output.exists() and not charts.exists() and not report.exists(),'Elegir destinos nuevos; no se sobrescribe.')
    require(anchor_count>=2 and n_init>=2 and 2<=replicates<=30,'Parámetros fuera de alcance.')
    print('Verificando fuentes y experimentos existentes...',flush=True)
    protected=snapshot_inputs(root,output,charts)
    for base in [root/'src',root/'analysis/scripts']:
        for path in base.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.name not in [Path(__file__).name,'test_run_contextual_clustering_pilot.py']:
                protected[str(path)]=file_hash(path)
    protected[str(root/'.gitignore')]=file_hash(root/'.gitignore')
    validate_sources(root,protected)
    for path in [output,charts,output/'metadata',output/'reference']:path.mkdir(parents=True,exist_ok=True)
    report.parent.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();manifest_path=output/'metadata/run_manifest.json'
    manifest=dict(status='running',errors=[],started_at_utc=datetime.now(timezone.utc).isoformat(),protected_hashes=protected,
        calculation_script_sha256=file_hash(Path(__file__)),
        configuration=dict(configurations=configurations(),seeds=SEEDS,ks=KS,n_init=n_init,anchor_count=anchor_count,
            robust_configs=ROBUST_CONFIGS,robust_ks=ROBUST_KS,replicates=replicates,weighting='equal_segment'),
        versions=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,pyarrow=pa.__version__,matplotlib=matplotlib.__version__))
    save_json(manifest_path,manifest)
    try:
        full=pd.read_parquet(root/'data/processed/contextual_feature_review/reference/context_segments_life_stage.parquet').sort_values('row_id').reset_index(drop=True)
        base,national=validate_reference(root,full)
        save_table(output/'reference/segments.parquet',full)
        save_table(output/'reference/pending_segments.parquet',full.loc[~base])
        save_table(output/'reference/national_reference.parquet',national)
        save_json(output/'metadata/dependencies.json',{name:dict(importable=importlib.util.find_spec(name) is not None) for name in ['sklearn','scipy']})
        contract=dict(unit='municipality_candidate_age_band_sex',year=2024,training_segments=int(base.sum()),
            training_municipalities=full.loc[base].groupby(MUNICIPAL_KEYS).ngroups,training_LN=int(full.loc[base,'LN'].sum()),
            transformations='P/A con DE poblacional; T con una escala RMS por bloque; sqrt(1-alpha) y sqrt(alpha).',
            configurations=configurations(),context_columns=SHARE_COLUMNS,
            feature_columns={name:((['participation_block'] if config['behavior']!='none' else [])+
                (['context_U','context_R','context_M'] if config['geometry']!='none' else [])) for name,config in configurations().items()},
            row_id_is_alignment_only=True,
            excluded_from_distance=['mean_age_nominal','age_band','SEXO',*MUNICIPAL_KEYS,'district_reference_year','LN','SV','NV','NS','specified_count','unspecified_rate'],
            source_exact_reference='data/processed/cluster_features/reference/exact_age_2024.parquet',
            source_exact_sha256=file_hash(root/'data/processed/cluster_features/reference/exact_age_2024.parquet'),
            national_reference='Fija por intervalo/sexo, todos los conteos antes de selección; no referencia por edad exacta.')
        save_json(output/'metadata/feature_contract.json',contract)
        save_json(output/'metadata/incidents.json',previous_incidents(root))
        parameters,best,metrics=main_experiments(full,base,output,anchor_count,n_init)
        sensitivity,_=sensitivity_experiments(full,base,parameters,best,output,n_init,anchor_count)
        stability,coverage=municipal_resampling(full,base,best,root,output,n_init,replicates)
        save_table(output/'metadata/output_validation.csv',audit_outputs(output,full,base))
        plot_results(full,base,best,metrics,stability,sensitivity,charts)
        write_report(root,output,charts,report,full,metrics,stability,sensitivity,coverage,len(protected),anchor_count,n_init)
        for path,digest in protected.items():require(file_hash(path)==digest,f'Archivo previo modificado: {path}')
        manifest.update(status='validated',finished_at_utc=datetime.now(timezone.utc).isoformat(),seconds=time.monotonic()-started,
            main_models=len(metrics),sensitivity_models=len(sensitivity),resampling_models=len(stability),protected_files=len(protected),
            report_sha256=file_hash(report),script_sha256=file_hash(Path(__file__)),test_script_sha256=file_hash(root/'analysis/scripts/test_run_contextual_clustering_pilot.py'),
            artifact_hashes={str(path.relative_to(root)):file_hash(path) for base_path in [output,charts] for path in base_path.rglob('*') if path.is_file() and path!=manifest_path})
        save_json(manifest_path,manifest);save_json(output/'_SUCCESS',dict(manifest_sha256=file_hash(manifest_path)))
        print(f'VALIDADO: {report}',flush=True)
    except Exception as error:
        manifest.update(status='failed',errors=[repr(error)]);save_json(manifest_path,manifest);raise


def review_existing(root,output,charts,report,calculation_script_sha256=None):
    """Revisa artefactos propios ya validados sin repetir ajustes ni fuentes.

    Verifica todos sus hashes antes de actualizar documentación y diagnósticos.
    Es útil para añadir tablas/gráficas sin reejecutar cientos de modelos.
    """
    root,output,charts,report=[Path(path).resolve() for path in [root,output,charts,report]]
    require(output.is_relative_to(root/'data/processed') and charts.is_relative_to(root/'analysis/charts') and
        report.is_relative_to(root/'analysis/reports'),'Revisión fuera de áreas autorizadas.')
    manifest_path=output/'metadata/run_manifest.json';marker_path=output/'_SUCCESS'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    marker=json.loads(marker_path.read_text(encoding='utf-8'))
    require(manifest['status']=='validated' and marker['manifest_sha256']==file_hash(manifest_path),'Resultados propios sin validación completa.')
    for relative,digest in manifest['artifact_hashes'].items():require(file_hash(root/relative)==digest,f'Artefacto propio alterado: {relative}')
    for path,digest in manifest['protected_hashes'].items():require(file_hash(path)==digest,f'Archivo previo alterado: {path}')
    require(manifest['report_sha256']==file_hash(report),'Informe propio alterado antes de revisión.')
    marker_path.unlink();manifest['status']='reviewing_documentation';save_json(manifest_path,manifest)
    try:
        full=pd.read_parquet(output/'reference/segments.parquet');base,_=validate_reference(root,full)
        training=full.loc[base].reset_index(drop=True)
        metrics=pd.read_csv(output/'metadata/model_metrics.csv');best={}
        for config_id,frame in metrics.groupby('config_id',sort=False):
            labels=pd.read_parquet(output/f'models/{config_id}/labels.parquet')
            for k,group in frame.groupby('k',sort=False):
                row=group.loc[group.sse.idxmin()];seed=int(row.seed);k=int(k)
                centers=pd.read_parquet(output/f'models/{config_id}/centers_k{k}_seed{seed}.parquet').drop(columns='cluster').to_numpy(float)
                best[config_id,k]=(seed,dict(labels=labels.loc[base,f'k{k}_seed{seed}'].to_numpy(int),centers=centers,inertia=row.sse))
        stability=pd.read_csv(output/'metadata/resampling_metrics.csv');coverage=pd.read_csv(output/'metadata/resampling_coverage.csv')
        sensitivity=pd.read_csv(output/'metadata/sensitivity_metrics.csv')
        # Alineación OOB única para porcentaje de cambio y listado municipal.
        cases=[]
        for replicate in sorted(stability.replicate.unique()):
            labels=pd.read_parquet(output/f'resampling/sample_{int(replicate):03d}/labels.parquet')
            require(labels.row_id.equals(full.row_id),'Orden OOB distinto.')
            oob=labels.loc[base,'is_oob_eligible'].to_numpy(bool)
            for config_id in manifest['configuration']['robust_configs']:
                for k in manifest['configuration']['robust_ks']:
                    reference=best[config_id,k][1]['labels']
                    projected=labels.loc[base,f'{config_id}_k{k}'].to_numpy(int)
                    aligned=align_partition(reference[oob],projected[oob],k)[0]
                    changed=reference[oob]!=aligned
                    row=stability[(stability.config_id==config_id)&(stability.k==k)&(stability.replicate==replicate)].iloc[0]
                    require(np.isclose(changed.mean(),row.oob_changed_fraction,atol=1e-12),'Cambios OOB distintos de la métrica.')
                    part=training.loc[oob,MUNICIPAL_KEYS].copy();part['changed']=changed
                    part=part.groupby(MUNICIPAL_KEYS,as_index=False).agg(oob_segments=('changed','size'),changed_segments=('changed','sum'))
                    part['config_id']=config_id;part['k']=k;part['replicate']=replicate;cases.append(part)
        temporary=output/'metadata/oob_municipality_changes_review.parquet'
        save_table(temporary,pd.concat(cases,ignore_index=True));temporary.replace(output/'metadata/oob_municipality_changes.parquet')
        validation=output/'metadata/output_validation.csv'
        if validation.exists():validation.unlink()
        save_table(validation,audit_outputs(output,full,base))
        save_json(output/'metadata/incidents.json',previous_incidents(root))
        contract_path=output/'metadata/feature_contract.json';contract=json.loads(contract_path.read_text(encoding='utf-8'))
        contract['feature_columns']={name:((['participation_block'] if config['behavior']!='none' else [])+
            (['context_U','context_R','context_M'] if config['geometry']!='none' else [])) for name,config in configurations().items()}
        contract['row_id_is_alignment_only']=True;save_json(contract_path,contract)
        plot_results(full,base,best,metrics,stability,sensitivity,charts)
        config=manifest['configuration']
        write_report(root,output,charts,report,full,metrics,stability,sensitivity,coverage,
            len(manifest['protected_hashes']),config['anchor_count'],config['n_init'])
        for path,digest in manifest['protected_hashes'].items():require(file_hash(path)==digest,f'Archivo previo modificado: {path}')
        manifest.update(status='validated',report_sha256=file_hash(report),script_sha256=file_hash(Path(__file__)),
            calculation_script_sha256=calculation_script_sha256 or manifest.get('calculation_script_sha256',manifest['script_sha256']),
            test_script_sha256=file_hash(root/'analysis/scripts/test_run_contextual_clustering_pilot.py'),
            documentation_revision=dict(date=datetime.now(timezone.utc).isoformat(),
                description='Añade interpretación de cobertura, tablas de sensibilidad, mujeres y gráfica demográfica; alinea el listado municipal con el mismo mapeo OOB de la métrica. Audita salidas. No repite ni cambia ajustes, etiquetas, escalas, métricas de modelos o fuentes.'),
            artifact_hashes={str(path.relative_to(root)):file_hash(path) for base_path in [output,charts] for path in base_path.rglob('*')
                if path.is_file() and path!=manifest_path and path!=marker_path})
        save_json(manifest_path,manifest);save_json(marker_path,dict(manifest_sha256=file_hash(manifest_path)))
        print('Revisión de artefactos validada; no se repitieron modelos.',flush=True)
    except Exception as error:
        manifest.update(status='failed',errors=[repr(error)]);save_json(manifest_path,manifest);raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output',type=Path,default=Path('data/processed/contextual_clustering_pilot'))
    parser.add_argument('--charts',type=Path,default=Path('analysis/charts/contextual_clustering_pilot'))
    parser.add_argument('--report',type=Path,default=Path('analysis/reports/contextual_clustering_pilot.md'))
    parser.add_argument('--anchor-count',type=int,default=512)
    parser.add_argument('--n-init',type=int,default=10)
    parser.add_argument('--replicates',type=int,default=10)
    parser.add_argument('--review-existing',action='store_true',help='Revisa sólo artefactos propios con hashes validados; no vuelve a entrenar.')
    args=parser.parse_args()
    if args.review_existing:review_existing(args.root,args.root/args.output,args.root/args.charts,args.root/args.report)
    else:run_pilot(args.root,args.root/args.output,args.root/args.charts,args.root/args.report,args.anchor_count,args.n_init,args.replicates)


if __name__=='__main__':main()
