"""Investigación independiente de segmentos mixtos; no publica ni modifica V1."""
from __future__ import annotations

import os
for variable in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
    os.environ[variable] = '1'
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import importlib.metadata
import itertools
import json
from pathlib import Path
import platform
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
HOME = ROOT / 'analysis/profile_v2'
os.environ.setdefault('MPLCONFIGDIR', str(HOME / '.cache/matplotlib'))
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, davies_bouldin_score, normalized_mutual_info_score, pairwise_distances
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

YEARS = [2009, 2012, 2015, 2018, 2021, 2024]
BANDS = ['18-34', '35-59', '60-100']
METRICS = ['LN', 'SV', 'NV', 'NS', 'source_row_count', 'sex_2_source_rows', 'sex_2_nominal_count']
MUNICIPAL = ['EDOCVE', 'MPIOCVE']
PARENT = [*MUNICIPAL, 'age_band', 'SEXO']
KEYS = [*PARENT, 'TIPOSEC']
CATEGORIES = dict(age_band=BANDS, SEXO=['0', '1'], TIPOSEC=['U', 'R', 'M'])
NAMES = {'age_band': dict(zip(BANDS, BANDS)), 'SEXO': {'0': 'Hombres', '1': 'Mujeres'}, 'TIPOSEC': {'U': 'Urbana', 'R': 'Rural', 'M': 'Mixta'}}
CONFIGS = dict(
    absolute_50=dict(variable='participation_observed', numeric_weight=.5),
    age_sex_50=dict(variable='delta_age_sex', numeric_weight=.5),
    age_sex_section_50=dict(variable='delta_age_sex_section', numeric_weight=.5),
    age_sex_75=dict(variable='delta_age_sex', numeric_weight=.75),
    relative_only=dict(variable='delta_age_sex', numeric_weight=1.0),
)
SEEDS = [17, 42, 2024]
SPEC = dict(experiment='profile-v2-mixed-2024-v1', k=[4, 5, 6], seeds=SEEDS, n_init=20,
            max_iter=1000, tol=1e-6, resamples=10, resample_fraction=.8, resample_seed=8102024,
            resample_n_init=10, silhouette_anchors=384, support=dict(LN=100, specified=100, source_rows=5), configs=CONFIGS)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def clean(value):
    if value is pd.NA or value is None:
        return None
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(item) for item in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(clean(value), ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def table(frame):
    def cell(value):
        if isinstance(value, float):
            return f'{value:.4f}' if np.isfinite(value) else 'n/d'
        return str(value).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(frame.columns) + ' |', '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |'] +
                     ['| ' + ' | '.join(map(cell, row)) + ' |' for row in frame.itertuples(index=False, name=None)])


def save_frame(output, name, frame):
    path = output / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.parquet':
        frame.to_parquet(path, index=False)
        pd.testing.assert_frame_equal(frame, pd.read_parquet(path))
    else:
        frame.to_csv(path, index=False)


def ratio(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return np.divide(a, b, out=np.full(np.broadcast_shapes(a.shape, b.shape), np.nan), where=b > 0)


def eligible(frame, threshold=100, source_rows=5):
    return (frame.age_band.isin(BANDS) & frame.SEXO.isin(['0', '1']) & frame.LN.ge(threshold) &
            (frame.SV + frame.NV).ge(threshold) & frame.source_row_count.ge(source_rows))


def references(frame, keys):
    result = frame.groupby(keys, observed=True, as_index=False)[METRICS].sum()
    result['reference'] = ratio(result.SV, result.SV + result.NV)
    return result


def group_match(left, right, keys):
    a = left.groupby(keys, observed=True)[METRICS].sum().sort_index()
    b = right.groupby(keys, observed=True)[METRICS].sum().sort_index()
    pd.testing.assert_frame_equal(a, b, check_dtype=False)
    return len(a) * len(METRICS)


def protected_snapshot():
    paths = set()
    for directory in ['src', 'docs', 'scripts', 'public', 'analysis/reports', 'analysis/scripts',
                      'data/processed/participamx_multiyear', 'data/processed/contextual_feature_review']:
        paths.update(path for path in (ROOT / directory).rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    for name in ['package.json', 'package-lock.json', '.gitignore']:
        if (ROOT / name).is_file():
            paths.add(ROOT / name)
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(paths)}


def audit(output):
    source = ROOT / 'data/processed/participamx_multiyear'
    require((source / '_SUCCESS').is_file(), 'Falta _SUCCESS multianual')
    manifest = json.loads((source / 'metadata/run_manifest.json').read_text(encoding='utf-8'))
    require(manifest['status'] == 'validated', 'Fuente multianual no validada')
    known = {key.replace('\\', '/'): value for key, value in manifest['artifact_hashes'].items()}
    inputs = {}

    def read(relative):
        path = source / relative
        key = path.relative_to(ROOT).as_posix()
        value = digest(path)
        require(known.get(key) == value, 'Hash multianual no válido: ' + key)
        inputs[key] = value
        return pd.read_parquet(path) if path.suffix == '.parquet' else json.loads(path.read_text(encoding='utf-8'))

    history, availability, checks, frames = [], [], 0, {}
    for year in YEARS:
        frame = read(f'elections/{year}/tables/section_segments.parquet')
        parents = read(f'elections/{year}/tables/segments.parquet')
        municipalities = read(f'elections/{year}/tables/municipalities.parquet')
        marginal = read(f'elections/{year}/tables/section_statistics.parquet')
        require(not frame.duplicated(KEYS).any(), 'Cruce duplicado')
        require(frame.election_year.eq(year).all(), 'Año incorrecto')
        require(not frame[[*KEYS, *METRICS, 'section_count']].isna().any().any(), 'Nulos en claves o conteos')
        require(set(frame.TIPOSEC) <= {'U', 'R', 'M'} and set(frame.SEXO) <= {'0', '1', '2'}, 'Categorías incorrectas')
        require(set(frame.age_band) <= {*BANDS, '101+'}, 'Bandas inesperadas')
        require((frame[METRICS] >= 0).all().all() and frame.LN.eq(frame.SV + frame.NV + frame.NS).all(), 'Identidad o conteos incorrectos')
        np.testing.assert_allclose(frame.participation_observed, ratio(frame.SV, frame.SV + frame.NV), equal_nan=True)
        checks += group_match(frame, parents, PARENT)
        checks += group_match(frame, municipalities, MUNICIPAL)
        checks += group_match(frame, marginal, ['TIPOSEC'])
        mask = eligible(frame)
        core = frame[frame.age_band.isin(BANDS) & frame.SEXO.isin(['0', '1'])]
        ref = references(core, ['age_band', 'SEXO', 'TIPOSEC'])
        ref['election_year'] = year
        ref['election_type'] = 'Presidencial' if year in [2012, 2018, 2024] else 'Intermedia'
        ref['unspecified_rate'] = ratio(ref.NS, ref.LN)
        history.append(ref)
        availability.append(dict(year=year, cells=len(frame), eligible=int(mask.sum()), municipalities=len(municipalities),
            eligible_municipalities=len(frame.loc[mask, MUNICIPAL].drop_duplicates()),
            LN=int(frame.LN.sum()), eligible_LN=int(frame.loc[mask, 'LN'].sum()), nominal_fraction=frame.loc[mask, 'LN'].sum()/frame.LN.sum(),
            undefined=int((frame.SV + frame.NV).eq(0).sum()), high_ns=int((ratio(frame.NS, frame.LN) >= .1).sum()),
            sex_2_available=year == 2024, sex_2_cells=int(frame.SEXO.eq('2').sum()) if year == 2024 else None))
        if year == 2024:
            frames = dict(full=frame, parents=parents, municipalities=municipalities)
    full, parents = frames['full'].copy(), frames['parents']
    full = full.sort_values(KEYS, kind='stable').reset_index(drop=True)
    full['row_id'] = ['experimental_2024|' + '|'.join(row) for row in full[KEYS].itertuples(index=False, name=None)]
    full['municipal_id'] = full.EDOCVE + '|' + full.MPIOCVE
    r1 = references(full, ['age_band', 'SEXO']).rename(columns={'reference': 'reference_age_sex'})
    r2 = references(full, ['age_band', 'SEXO', 'TIPOSEC']).rename(columns={'reference': 'reference_age_sex_section'})
    published = read('elections/2024/tables/national_references.parquet')
    check = r1.merge(published[['age_band','SEXO','national_rate']],on=['age_band','SEXO'],validate='one_to_one')
    require(len(check)==len(r1),'Referencia nacional publicada incompleta')
    np.testing.assert_allclose(check.reference_age_sex,check.national_rate,equal_nan=True,atol=1e-14)
    full = full.merge(r1[['age_band', 'SEXO', 'reference_age_sex']], on=['age_band', 'SEXO'], validate='many_to_one', sort=False)
    full = full.merge(r2[['age_band', 'SEXO', 'TIPOSEC', 'reference_age_sex_section']], on=['age_band', 'SEXO', 'TIPOSEC'], validate='many_to_one', sort=False)
    full['delta_age_sex'] = full.participation_observed - full.reference_age_sex
    full['delta_age_sex_section'] = full.participation_observed - full.reference_age_sex_section
    full['high_ns'] = ratio(full.NS, full.LN) >= .1
    full['few_sections'] = full.section_count.lt(5)
    full['is_eligible'] = eligible(full)
    full['pending_reason'] = np.select([~full.age_band.isin(BANDS) | ~full.SEXO.isin(['0', '1']), (full.SV + full.NV).eq(0), ~full.is_eligible], ['complementary', 'undefined_rate', 'insufficient_support'], default='eligible')
    for name, flag in [('low_LN', full.LN.lt(100)), ('low_specified', (full.SV + full.NV).lt(100)), ('few_source_rows', full.source_row_count.lt(5))]:
        full[name] = flag
    original = parents[[*PARENT, 'candidate_id', 'sufficient_support', 'participation_delta']].rename(columns={'candidate_id': 'v1_parent_profile', 'sufficient_support': 'v1_parent_supported', 'participation_delta': 'v1_parent_delta'})
    full = full.merge(original, on=PARENT, how='left', validate='many_to_one', sort=False)
    full = full.merge(frames['municipalities'][[*MUNICIPAL, 'state_name_label', 'municipality_name_label', 'district_reference_year']], on=MUNICIPAL, validate='many_to_one', sort=False)
    require(len(full) == len(frames['full']) and full.row_id.is_unique, 'La preparación expandió filas')
    require(full.loc[full.is_eligible, 'v1_parent_supported'].all(), 'Un hijo elegible no tiene padre con soporte')
    require(np.isfinite(full.loc[full.is_eligible, list(c['variable'] for c in CONFIGS.values())]).all().all(), 'Características no finitas')
    full['split_sign_opposes_parent'] = (full.delta_age_sex * full.v1_parent_delta).lt(0)
    save_frame(output, 'reference/all_observations.parquet', full)
    save_frame(output, 'reference/pending_observations.parquet', full[~full.is_eligible].reset_index(drop=True))
    save_frame(output, 'reference/national_age_sex.csv', r1)
    save_frame(output, 'reference/national_age_sex_section.csv', r2)
    save_frame(output, 'historical/national_joint_references.csv', pd.concat(history, ignore_index=True))
    save_frame(output, 'diagnostics/historical_coverage.csv', pd.DataFrame(availability))
    supported = parents[parents.candidate_id.notna()]
    baseline = read('elections/2024/profiles.json')['data']
    cols = ['profile_id', 'segments', 'municipalities', 'states', 'LN', 'SV', 'NV', 'NS', 'participation_observed', 'matched_peer_reference', 'participation_delta', 'near_reference_fraction', 'high_ns_fraction']
    save_frame(output, 'comparisons/v1_six_profiles.csv', pd.DataFrame(baseline)[cols])
    coverage = []
    for threshold in [25, 50, 100, 200, 500]:
        for rows in [1, 5]:
            mask = eligible(full, threshold, rows)
            coverage.append(dict(design='broad_split',threshold=threshold,min_source_rows=rows,segments=int(mask.sum()),municipalities=full.loc[mask, 'municipal_id'].nunique(),LN=int(full.loc[mask, 'LN'].sum()),nominal_fraction=full.loc[mask, 'LN'].sum()/full.LN.sum()))
    coverage.append(dict(design='v1_unsplit',threshold=100,min_source_rows=5,segments=len(supported),municipalities=len(supported[MUNICIPAL].drop_duplicates()),LN=int(supported.LN.sum()),nominal_fraction=supported.LN.sum()/full.LN.sum()))
    # Escenario previo de cinco bandas: sólo auditoría; no se comparan ARI entre unidades distintas.
    path = ROOT / 'data/processed/contextual_feature_review/reference/section_segments_life_stage.parquet'
    inputs[path.relative_to(ROOT).as_posix()] = digest(path)
    life = pd.read_parquet(path)
    checks += group_match(life, full, [*MUNICIPAL, 'TIPOSEC'])
    mask = life.age_band.ne('101+') & life.SEXO.isin(['0','1']) & life.LN.ge(100) & (life.SV+life.NV).ge(100) & life.source_row_count.ge(5)
    coverage.append(dict(design='life_stage_split',threshold=100,min_source_rows=5,segments=int(mask.sum()),municipalities=len(life.loc[mask,MUNICIPAL].drop_duplicates()),LN=int(life.loc[mask,'LN'].sum()),nominal_fraction=life.loc[mask,'LN'].sum()/full.LN.sum()))
    save_frame(output, 'diagnostics/support_sensitivity.csv', pd.DataFrame(coverage))
    dimensions = [(['EDOCVE','state_name_label'],'state'), (['age_band','SEXO','TIPOSEC'],'joint_cell'), (['pending_reason'],'status')]
    for keys, name in dimensions:
        records=[]
        for key, part in full.groupby(keys, observed=True, dropna=False):
            key = key if isinstance(key, tuple) else (key,)
            train=part[part.is_eligible]
            records.append(dict(zip(keys,key), segments=len(part),eligible_segments=len(train),LN=int(part.LN.sum()),eligible_LN=int(train.LN.sum()),nominal_fraction=train.LN.sum()/part.LN.sum() if part.LN.sum() else None,municipalities=part.municipal_id.nunique(),eligible_municipalities=train.municipal_id.nunique(),undefined=int((part.SV+part.NV).eq(0).sum()),high_ns=int(part.high_ns.sum()),few_sections=int(part.few_sections.sum())))
        save_frame(output, f'diagnostics/coverage_{name}.csv', pd.DataFrame(records))
    contrast = r2.merge(r1[['age_band','SEXO','reference_age_sex']],on=['age_band','SEXO'],validate='many_to_one')
    contrast['reference_shift_pp'] = 100*(contrast.reference_age_sex_section-contrast.reference_age_sex)
    save_frame(output,'comparisons/reference_effect.csv',contrast)
    write_json(output/'metadata/audit.json',dict(inputs=inputs,source_schema={name:str(dtype) for name,dtype in frames['full'].dtypes.items()},additive_checks=checks,original_rows=9773730,cross_rows=len(full),missing_values={name:int(full[name].isna().sum()) for name in ['participation_observed','delta_age_sex','delta_age_sex_section']},unobserved_core_combinations=2477*18-int((full.age_band.isin(BANDS)&full.SEXO.isin(['0','1'])).sum()),sex_2_counts=full[full.SEXO.eq('2')][METRICS].sum().to_dict(),over_100_counts=full[full.age_band.eq('101+')][METRICS].sum().to_dict()))
    return full


def fit_parameters(frame, config):
    variable = config['variable']
    scaler = StandardScaler().fit(frame[[variable]])
    require(scaler.var_[0] > 0, 'Coordenada numérica constante')
    result = dict(variable=variable,numeric_weight=config['numeric_weight'],mean=float(scaler.mean_[0]),scale=float(scaler.scale_[0]),n=len(frame),blocks={})
    for field, categories in CATEGORIES.items():
        encoder=OneHotEncoder(categories=[categories],sparse_output=False,handle_unknown='error')
        block=encoder.fit_transform(frame[[field]])
        mean=block.mean(axis=0)
        total_variance=float(np.mean(np.sum((block-mean)**2,axis=1)))
        require(total_variance>0,'Bloque categórico constante')
        result['blocks'][field]=dict(categories=categories,mean=mean.tolist(),scale=np.sqrt(total_variance),weight=(1-config['numeric_weight'])/3)
    return result


def transform(frame, parameters):
    blocks=[np.sqrt(parameters['numeric_weight'])*((frame[parameters['variable']].to_numpy(float)-parameters['mean'])/parameters['scale'])[:,None]]
    for field, item in parameters['blocks'].items():
        if item['weight'] == 0:
            continue
        raw=np.column_stack([frame[field].eq(category).to_numpy(float) for category in item['categories']])
        require(np.all(raw.sum(axis=1)==1),'Categoría desconocida')
        blocks.append(np.sqrt(item['weight'])*(raw-np.array(item['mean']))/item['scale'])
    result=np.column_stack(blocks)
    require(np.isfinite(result).all(),'Matriz no finita')
    return result


def fit(values,k,seed,n_init,weights=None):
    model=KMeans(n_clusters=k,random_state=seed,n_init=n_init,max_iter=SPEC['max_iter'],tol=SPEC['tol'],algorithm='lloyd').fit(values,sample_weight=weights)
    require(len(np.unique(model.labels_))==k,'Grupos vacíos')
    require(model.n_iter_ < SPEC['max_iter'],'No convergió antes del límite')
    return model


def checkpoint(output, token, values, parameters, k, seed, n_init=20, weights=None):
    path=output/'models'/f'{token}.npz'
    fingerprint=hashlib.sha256(values.tobytes()+(np.asarray(weights).tobytes() if weights is not None else b'')).hexdigest()
    if path.exists():
        meta=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        require(meta['fingerprint']==fingerprint and meta['k']==k and meta['seed']==seed and meta['n_init']==n_init and meta['artifact_hash']==digest(path),'Checkpoint incompatible')
        with np.load(path,allow_pickle=False) as stored:
            return stored['labels'],stored['centers'],meta
    model=fit(values,k,seed,n_init,weights)
    path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path,labels=model.labels_,centers=model.cluster_centers_)
    meta=dict(fingerprint=fingerprint,k=k,seed=seed,n_init=n_init,inertia=model.inertia_,iterations=model.n_iter_,parameters=parameters,artifact_hash=digest(path))
    write_json(path.with_suffix('.json'),meta)
    return model.labels_,model.cluster_centers_,meta


def predict(values,centers):
    return np.argmin(np.sum((values[:,None,:]-centers[None,:,:])**2,axis=2),axis=1)


def silhouette_anchors(values,labels,anchors):
    result=[]
    groups=np.unique(labels)
    for start in range(0,len(anchors),32):
        ids=anchors[start:start+32]
        distances=pairwise_distances(values[ids],values,metric='euclidean')
        for index,observation in enumerate(ids):
            own=labels[observation]
            inside=labels==own
            if inside.sum()<=1:
                result.append(0.0)
                continue
            a=distances[index,inside].sum()/(inside.sum()-1)
            b=min(distances[index,labels==group].mean() for group in groups if group!=own)
            result.append((b-a)/max(a,b) if max(a,b)>0 else 0)
    return np.asarray(result)


def conditional_r2(frame,labels,keys):
    data=frame[[*keys,'participation_observed']].copy()
    data['cluster']=labels
    base=data.groupby(keys,observed=True).participation_observed.transform('mean')
    refined=data.groupby([*keys,'cluster'],observed=True).participation_observed.transform('mean')
    denominator=float(np.sum((data.participation_observed-base)**2))
    return 1-float(np.sum((data.participation_observed-refined)**2))/denominator if denominator>0 else None


def diagnostics(frame,values,labels):
    mean=values.mean(axis=0)
    between=np.zeros(values.shape[1])
    for label in np.unique(labels):
        part=values[labels==label]
        between+=len(part)*(part.mean(axis=0)-mean)**2
    shares=between/between.sum() if between.sum()>0 else between
    result=dict(db=davies_bouldin_score(values,labels),conditional_age_sex_r2=conditional_r2(frame,labels,['age_band','SEXO']),conditional_joint_r2=conditional_r2(frame,labels,['age_band','SEXO','TIPOSEC']),participation_separation_share=float(shares[0]))
    result.update(age_separation_share=float(shares[1:4].sum()),sex_separation_share=float(shares[4:6].sum()),section_separation_share=float(shares[6:9].sum()))
    for field in CATEGORIES:
        cross=pd.crosstab(labels,frame[field].to_numpy())
        result[field+'_purity']=cross.max(axis=1).sum()/len(frame)
        result[field+'_nmi']=normalized_mutual_info_score(frame[field],labels)
    strata=frame[['age_band','SEXO','TIPOSEC']].agg('|'.join,axis=1)
    result['joint_nmi']=normalized_mutual_info_score(strata,labels)
    sizes=np.bincount(labels)
    result.update(cluster_min=int(sizes.min()),cluster_max=int(sizes.max()),cluster_sizes=sizes.tolist())
    return result


def profiles(frame,labels,config_id,k,seed):
    records=[]
    for label in range(k):
        part=frame[labels==label]
        counts={field:int(part[field].sum()) for field in METRICS}
        den=counts['SV']+counts['NV']
        composition={}
        for field in CATEGORIES:
            composition[field]=[]
            for category in CATEGORIES[field]:
                sub=part[part[field].eq(category)]
                composition[field].append(dict(code=category,label=NAMES[field][category],segments=len(sub),segment_fraction=len(sub)/len(part),LN=int(sub.LN.sum()),nominal_fraction=sub.LN.sum()/part.LN.sum()))
        dominant={field:max(items,key=lambda item:item['segments']) for field,items in composition.items()}
        nominal=part.groupby('municipal_id').LN.sum().sort_values(ascending=False)
        states=part.groupby(['EDOCVE','state_name_label']).agg(segments=('row_id','size'),LN=('LN','sum')).reset_index().sort_values('LN',ascending=False)
        state_totals=frame.groupby('EDOCVE').LN.sum()
        states['share_of_cluster_LN']=states.LN/part.LN.sum()
        states['share_of_eligible_state_LN']=states.LN/states.EDOCVE.map(state_totals)
        reference1=float(np.sum((part.SV+part.NV)*part.reference_age_sex)/den)
        reference2=float(np.sum((part.SV+part.NV)*part.reference_age_sex_section)/den)
        rate=counts['SV']/den
        name=f"Combinación C{label}: {dominant['age_band']['label']} / {dominant['SEXO']['label']} / {dominant['TIPOSEC']['label']}"
        records.append(dict(candidate_id=f'{config_id}_k{k}_c{label}',experimental=True,status='research_not_published',config=config_id,k=k,seed=seed,local_label=label,provisional_name=name,election_year=2024,unit='municipality_age_band_sex_section_type',assignment='K-Means en bloques numérico y categóricos; etiqueta local del ajuste',segments=len(part),municipalities=part.municipal_id.nunique(),states=part.EDOCVE.nunique(),counts=counts,participation_observed=rate,matched_reference_age_sex=reference1,matched_reference_joint=reference2,delta_age_sex_pp=100*(rate-reference1),delta_joint_pp=100*(rate-reference2),delta_segment_mean_pp=float(part.delta_age_sex.mean()*100),delta_segment_sd_pp=float(part.delta_age_sex.std(ddof=0)*100),delta_segment_q1_pp=float(part.delta_age_sex.quantile(.25)*100),delta_segment_median_pp=float(part.delta_age_sex.median()*100),delta_segment_q3_pp=float(part.delta_age_sex.quantile(.75)*100),specified_min=int((part.SV+part.NV).min()),specified_median=float((part.SV+part.NV).median()),NS_rate=counts['NS']/counts['LN'],high_NS_fraction=float(part.high_ns.mean()),few_sections_fraction=float(part.few_sections.mean()),sections_min=int(part.section_count.min()),sections_median=float(part.section_count.median()),top10_municipal_LN_share=float(nominal.head(10).sum()/nominal.sum()),largest_municipal_LN_share=float(nominal.iloc[0]/nominal.sum()),nominal_fraction_annual=counts['LN']/98330348,composition=composition,territories=states.to_dict('records'),distinctive_findings=[f"La combinación modal por segmentos es {dominant['age_band']['label']}, {dominant['SEXO']['label']} y tipo de sección {dominant['TIPOSEC']['label']}.",f"Diferencia agregada {100*(rate-reference1):+.2f} pp frente a edad/sexo y {100*(rate-reference2):+.2f} pp al incorporar tipo de sección a la referencia."],narrative=[f"Este conjunto contiene {len(part):,} segmentos agregados de {part.municipal_id.nunique():,} municipios. Por filas predominan {dominant['age_band']['label']} ({dominant['age_band']['segment_fraction']:.1%}), {dominant['SEXO']['label']} ({dominant['SEXO']['segment_fraction']:.1%}) y secciones {dominant['TIPOSEC']['label']} ({dominant['TIPOSEC']['segment_fraction']:.1%}). Son descriptores de variables utilizadas en el ajuste, no validación externa ni tipos individuales.",f"La participación agregada es {rate:.2%}; la dispersión de diferencias por segmento es {part.delta_age_sex.std(ddof=0)*100:.2f} pp. NS representa {counts['NS']/counts['LN']:.2%} del nominal y {part.few_sections.mean():.1%} de las celdas procede de menos de cinco secciones. Los diez municipios de mayor LN aportan {nominal.head(10).sum()/nominal.sum():.1%} del volumen del grupo; esto no identifica a todas sus personas ni causas electorales."],limitations=['Las categorías y tasas fueron utilizadas para agrupar: su diferenciación no es evidencia independiente.','Los municipios se superponen entre grupos y no se suman; U/R/M es tipo de sección electoral.','No se dispone de la unión de claves de sección por grupo; section_count no se suma como secciones únicas.','NS no es abstención; no se observan motivaciones o preferencias políticas.']))
    return records


def run_models(full,output):
    train=full[full.is_eligible].reset_index(drop=True)
    anchors=np.sort(np.random.default_rng(42024).choice(len(train),min(SPEC['silhouette_anchors'],len(train)),replace=False))
    save_frame(output,'metadata/silhouette_anchors.csv',train.loc[anchors,['row_id']].reset_index(drop=True))
    metrics=[]; best={}; parameters={}; seed_rows=[]; all_profiles=[]
    for config_id,config in CONFIGS.items():
        params=fit_parameters(train,config);parameters[config_id]=params
        values=transform(train,params)
        save_frame(output,f'features/{config_id}.parquet',pd.DataFrame(values,columns=[f'x{i}' for i in range(values.shape[1])]).assign(row_id=train.row_id))
        for k in SPEC['k']:
            fits=[]
            for seed in SEEDS:
                token=f'main_{config_id}_k{k}_seed{seed}'
                labels,centers,meta=checkpoint(output,token,values,params,k,seed)
                row=dict(config=config_id,k=k,seed=seed,inertia=meta['inertia'],iterations=meta['iterations'],**diagnostics(train,values,labels))
                metrics.append(row);fits.append((meta['inertia'],seed,labels,centers))
                labeled=full[['row_id',*KEYS,'is_eligible','pending_reason']].copy()
                labeled['cluster']=pd.Series(pd.NA,index=labeled.index,dtype='Int64')
                labeled.loc[full.is_eligible,'cluster']=labels
                save_frame(output,f'assignments/{token}.parquet',labeled)
            chosen=min(fits,key=lambda item:item[0]);_,seed,labels,centers=chosen
            best[config_id,k]=dict(seed=seed,labels=labels,centers=centers,values=values,parameters=params)
            for a,b in itertools.combinations(fits,2):
                seed_rows.append(dict(config=config_id,k=k,seed_a=a[1],seed_b=b[1],ARI=adjusted_rand_score(a[2],b[2])))
            silhouettes=silhouette_anchors(values,labels,anchors)
            row=next(item for item in metrics if item['config']==config_id and item['k']==k and item['seed']==seed)
            row.update(representative=True,silhouette=float(silhouettes.mean()),silhouette_mc_se=float(silhouettes.std(ddof=1)/np.sqrt(len(silhouettes))*np.sqrt((len(train)-len(silhouettes))/(len(train)-1))))
            save_frame(output,f'diagnostics/silhouette_{config_id}_k{k}.csv',pd.DataFrame(dict(row_id=train.loc[anchors,'row_id'],silhouette=silhouettes)))
            all_profiles.extend(profiles(train,labels,config_id,k,seed))
            print(f'Principal {config_id} K{k} semilla representativa {seed}',flush=True)
    write_json(output/'metadata/block_parameters.json',parameters)
    save_frame(output,'diagnostics/model_metrics.csv',pd.DataFrame(metrics))
    save_frame(output,'diagnostics/seed_stability.csv',pd.DataFrame(seed_rows))
    write_json(output/'candidates/experimental_profiles.json',all_profiles)
    comparison=[]
    for k in SPEC['k']:
        for a,b in [('age_sex_50','absolute_50'),('age_sex_50','age_sex_section_50'),('age_sex_50','age_sex_75'),('age_sex_50','relative_only')]:
            comparison.append(dict(k=k,left=a,right=b,ARI=adjusted_rand_score(best[a,k]['labels'],best[b,k]['labels'])))
    save_frame(output,'comparisons/representations.csv',pd.DataFrame(comparison))
    inherited=train.v1_parent_profile.fillna('at_reference').astype(str)
    v1=[]
    for (config_id,k),item in best.items():
        v1.append(dict(config=config_id,k=k,conditional_joint_r2=conditional_r2(train,item['labels'],['age_band','SEXO','TIPOSEC']),v1_parent_conditional_joint_r2=conditional_r2(train,inherited,['age_band','SEXO','TIPOSEC']),ARI_inherited_parent=adjusted_rand_score(inherited,item['labels'])))
        cross=pd.crosstab(inherited,item['labels']).reset_index()
        cross.columns=cross.columns.astype(str)
        save_frame(output,f'comparisons/v1_inherited_{config_id}_k{k}.csv',cross)
    save_frame(output,'comparisons/v1_common_children.csv',pd.DataFrame(v1))
    return train,best,pd.DataFrame(metrics),all_profiles


def sensitivities(full,train,best,output):
    rows=[]
    for config_id in ['age_sex_50','age_sex_section_50']:
        for scope in ['equal_municipality','low_ns','five_sections']:
            mask=np.ones(len(train),dtype=bool)
            if scope=='low_ns':mask=~train.high_ns.to_numpy()
            if scope=='five_sections':mask=~train.few_sections.to_numpy()
            part=train[mask].reset_index(drop=True)
            weights=(1/part.groupby('municipal_id').row_id.transform('size')).to_numpy() if scope=='equal_municipality' else None
            if weights is not None:np.testing.assert_allclose(pd.Series(weights).groupby(part.municipal_id).sum(),1)
            params=best[config_id,4]['parameters']
            values=transform(part,params)
            whole=transform(train,params)
            for k in SPEC['k']:
                labels,centers,meta=checkpoint(output,f'sensitivity_{config_id}_{scope}_k{k}',values,params,k,17,weights=weights)
                projected=predict(whole,centers)
                original=best[config_id,k]['labels']
                rows.append(dict(config=config_id,scope=scope,k=k,n=len(part),municipalities=part.municipal_id.nunique(),LN=int(part.LN.sum()),nominal_fraction=part.LN.sum()/full.LN.sum(),ARI_common=adjusted_rand_score(original[mask],projected[mask]),ARI_all_main=adjusted_rand_score(original,projected),**diagnostics(train,whole,projected)))
                save_frame(output,f'sensitivity/{config_id}_{scope}_k{k}.parquet',pd.DataFrame(dict(row_id=train.row_id,cluster=projected,is_training=mask,is_projection=~mask)))
            print(f'Sensibilidad {config_id} {scope}',flush=True)
    save_frame(output,'diagnostics/sensitivity_metrics.csv',pd.DataFrame(rows))


def resampling(full,train,best,output):
    universe=np.sort(full.municipal_id.unique())
    rng=np.random.default_rng(SPEC['resample_seed'])
    n=int(np.floor(len(universe)*SPEC['resample_fraction']))
    coverage=[];scores=[];members=[]
    for repetition in range(SPEC['resamples']):
        chosen=rng.choice(universe,n,replace=False)
        mask=train.municipal_id.isin(chosen).to_numpy()
        part=train[mask].reset_index(drop=True)
        selected=full.municipal_id.isin(chosen)
        members.extend(dict(sample=repetition,municipal_id=key,is_sampled=key in set(chosen)) for key in universe)
        coverage.append(dict(sample=repetition,drawn_municipalities=n,active_municipalities=part.municipal_id.nunique(),training_segments=len(part),training_LN=int(part.LN.sum()),fraction_of_eligible_LN=part.LN.sum()/train.LN.sum(),fraction_of_annual_LN=part.LN.sum()/full.LN.sum(),original_segments=int(selected.sum()),original_LN=int(full.loc[selected,'LN'].sum()),oob_segments=int((~mask).sum()),oob_municipalities=train.loc[~mask,'municipal_id'].nunique()))
        for config_id in ['age_sex_50','age_sex_section_50']:
            params=fit_parameters(part,CONFIGS[config_id])
            values=transform(part,params);whole=transform(train,params)
            for k in SPEC['k']:
                token=f'resample_{repetition}_{config_id}_k{k}'
                labels,centers,meta=checkpoint(output,token,values,params,k,17,n_init=SPEC['resample_n_init'])
                projected=predict(whole,centers)
                original=best[config_id,k]['labels']
                scores.append(dict(sample=repetition,config=config_id,k=k,ARI_oob=adjusted_rand_score(original[~mask],projected[~mask]),ARI_inbag=adjusted_rand_score(original[mask],projected[mask])))
                save_frame(output,f'resampling/{token}.parquet',pd.DataFrame(dict(row_id=train.row_id,cluster=projected,is_training=mask,is_oob=~mask)))
        print(f'Remuestra municipal {repetition+1}/{SPEC["resamples"]}',flush=True)
    save_frame(output,'resampling/coverage.csv',pd.DataFrame(coverage))
    save_frame(output,'resampling/membership.parquet',pd.DataFrame(members))
    save_frame(output,'diagnostics/municipal_stability.csv',pd.DataFrame(scores))


def charts(output,metrics,candidates):
    directory=output/'charts';directory.mkdir(exist_ok=True)
    representative=metrics[metrics.representative.fillna(False)]
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for name,part in representative.groupby('config'):
        axes[0].plot(part.k,part.silhouette,marker='o',label=name)
        axes[1].plot(part.k,part.conditional_joint_r2,marker='o',label=name)
    axes[0].set(title='Separación en cada geometría',xlabel='K',ylabel='Silhouette · anclas compartidas')
    axes[1].set(title='Separación de tasas dentro de edad/sexo/tipo',xlabel='K',ylabel='Fracción descriptiva de varianza')
    for ax in axes:ax.set_xticks(SPEC['k'])
    axes[1].legend(fontsize=8);fig.tight_layout();fig.savefig(directory/'candidate_comparison.png',dpi=150);plt.close(fig)
    scores=pd.read_csv(output/'diagnostics/municipal_stability.csv')
    fig,ax=plt.subplots(figsize=(10,4))
    values=[part.ARI_oob for _,part in scores.groupby(['config','k'])]
    names=[f'{name} K{k}' for (name,k),_ in scores.groupby(['config','k'])]
    ax.boxplot(values,tick_labels=names);ax.tick_params(axis='x',rotation=25);ax.set(title='Estabilidad municipal fuera del ajuste',ylabel='ARI OOB, 10 submuestras');fig.tight_layout();fig.savefig(directory/'municipal_stability.png',dpi=150);plt.close(fig)
    for config_id in ['age_sex_50','age_sex_section_50']:
        for k in SPEC['k']:
            items=[row for row in candidates if row['config']==config_id and row['k']==k]
            fig,axes=plt.subplots(1,3,figsize=(12,4))
            for ax,field in zip(axes,CATEGORIES):
                values=np.array([[item['segment_fraction'] for item in row['composition'][field]] for row in items])
                image=ax.imshow(values,vmin=0,vmax=1,cmap='Purples',aspect='auto')
                ax.set(xticks=range(len(CATEGORIES[field])),xticklabels=[NAMES[field][c] for c in CATEGORIES[field]],yticks=range(k),yticklabels=[f'C{i}' for i in range(k)],title={'age_band':'Banda de edad','SEXO':'Sexo','TIPOSEC':'Tipo de sección electoral'}[field])
            fig.colorbar(image,ax=axes,shrink=.6,label='Proporción de segmentos');fig.suptitle(f'Composición del ajuste · {config_id} · K{k} (no validación externa)');fig.savefig(directory/f'composition_{config_id}_k{k}.png',dpi=150,bbox_inches='tight');plt.close(fig)
    history=pd.read_csv(output/'historical/national_joint_references.csv',dtype={'SEXO':str})
    fig,axes=plt.subplots(1,3,figsize=(12,4),sharey=True)
    for ax,band in zip(axes,BANDS):
        for (sex,kind),part in history[history.age_band.eq(band)].groupby(['SEXO','TIPOSEC']):
            ax.plot(part.election_year,100*part.reference,marker='o',label=f'{NAMES["SEXO"][sex]} {kind}')
        ax.set(title=band,xlabel='Elección',ylabel='Participación observada (%)')
    axes[2].legend(fontsize=7);fig.suptitle('Contexto nacional de cortes independientes, no etiquetas transferidas');fig.tight_layout();fig.savefig(directory/'historical_joint_context.png',dpi=150);plt.close(fig)


def candidate_reports(output,candidates):
    directory=output/'reports/candidates';directory.mkdir(parents=True,exist_ok=True)
    for config_id in CONFIGS:
        for k in SPEC['k']:
            items=[row for row in candidates if row['config']==config_id and row['k']==k]
            text=[f'# Fichas experimentales · {config_id} · K={k} · 2024','No son perfiles publicados ni clases naturales. Etiquetas locales. No hay asignación de estrategias institucionales.']
            for row in items:
                text += [f'## {row["candidate_id"]}',row['provisional_name'],f'Unidad: {row["unit"]}. Método: {row["assignment"]}. Semilla representativa: {row["seed"]}.',*row['narrative'],table(pd.DataFrame([dict(field=field,**item) for field,items in row['composition'].items() for item in items])),table(pd.DataFrame([row['counts']])),f'Referencia mezclada edad/sexo: {row["matched_reference_age_sex"]:.6f}; conjunta: {row["matched_reference_joint"]:.6f}. Δ: {row["delta_age_sex_pp"]:+.3f} / {row["delta_joint_pp"]:+.3f} pp. D mínimo/mediana: {row["specified_min"]} / {row["specified_median"]}.',table(pd.DataFrame(row['territories'])),*row['limitations']]
            (directory/f'{config_id}_k{k}.md').write_text('\n\n'.join(text)+'\n',encoding='utf-8')


def run(output):
    started=time.time()
    output.mkdir(parents=True,exist_ok=True)
    spec_path=output/'metadata/config.json'
    if spec_path.exists():
        require(json.loads(spec_path.read_text())==SPEC,'Usar una nueva ruta para parámetros distintos')
    else:
        require(all(path.name=='run.lock' for path in output.iterdir()),'El destino contiene archivos ajenos; usar otra ruta')
    write_json(spec_path,SPEC)
    (output/'_SUCCESS').unlink(missing_ok=True)
    snapshot_path=output/'metadata/protected_hashes.json'
    if snapshot_path.exists():
        protected=json.loads(snapshot_path.read_text(encoding='utf-8'))
        for path,expected in protected.items():require(digest(ROOT/path)==expected,'Fuente previa alterada: '+path)
    else:
        print('Inventario de integridad de los archivos previos…',flush=True)
        protected=protected_snapshot();write_json(snapshot_path,protected)
    full=audit(output)
    print(f'Auditoría: {len(full)} celdas, {int(full.is_eligible.sum())} elegibles.',flush=True)
    train,best,metrics,candidates=run_models(full,output)
    sensitivities(full,train,best,output)
    resampling(full,train,best,output)
    charts(output,metrics,candidates);candidate_reports(output,candidates)
    # Conciliación de etiquetas y artefactos: pendientes NULL, cada vista por separado.
    for path in (output/'assignments').glob('*.parquet'):
        assigned=pd.read_parquet(path)
        require(len(assigned)==len(full) and assigned.row_id.equals(full.row_id),'Alineación de etiquetas incorrecta')
        require(assigned.loc[~full.is_eligible,'cluster'].isna().all(),'Pendientes con etiqueta de entrenamiento')
        require(assigned.loc[full.is_eligible,'cluster'].notna().all(),'Elegibles sin etiqueta')
    for path,expected in protected.items():require(digest(ROOT/path)==expected,'Archivo previo modificado: '+path)
    versions={name:importlib.metadata.version(name) for name in ['numpy','pandas','scikit-learn','scipy','pyarrow','matplotlib','threadpoolctl']}
    write_json(output/'metadata/environment.json',dict(python=platform.python_version(),packages=versions))
    artifacts={path.relative_to(output).as_posix():digest(path) for path in output.rglob('*') if path.is_file() and path.name not in ['run_manifest.json','_SUCCESS','run.lock']}
    write_json(output/'metadata/run_manifest.json',dict(status='models_validated_report_pending',experimental=True,seconds=time.time()-started,protected_files=len(protected),artifacts=artifacts,model_fits=45+18+60,original_CSV_reads=0))
    print('Modelos y artefactos verificados; informe de decisión pendiente de revisión de resultados.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HOME/'results')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    lock=args.output/'run.lock'
    try:
        handle=lock.open('x',encoding='utf-8')
    except FileExistsError:
        raise SystemExit('Existe un proceso/lock de esta investigación; revisar antes de duplicarlo.')
    try:
        handle.write(str(os.getpid()));handle.close()
        with threadpool_limits(limits=1):run(args.output)
    except Exception:
        write_json(args.output/'metadata/failure.json',dict(error=traceback.format_exc()))
        raise
    finally:
        handle.close();lock.unlink()
