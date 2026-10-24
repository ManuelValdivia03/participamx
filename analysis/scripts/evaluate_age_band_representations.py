"""Audita y compara formas electorales de tres, cuatro y cinco intervalos.

Las alertas de cobertura impiden entrenar alternativas no viables. Se distinguen
poblaciones naturales, comunes y diagnósticos sin modelos. Etapas recuperables.
"""
from __future__ import annotations
import os
for thread_variable in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[thread_variable]='1'
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import traceback
from itertools import combinations

import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[2]/'.venv_pattern_algorithms/matplotlib_cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from clean_data import require,file_hash
from build_cluster_features import snapshot_inputs
from build_descriptive import METRICS,compare_sums,markdown_table,pct
from compare_pattern_algorithms import (Comparison,probe_dependencies,label_metrics,posterior_summary,
    common_partition_stability,aligned_changes)
from evaluate_participation_patterns import (atomic_bytes,write_json,write_table,save_figure,experiment_lock,
    memory_estimate,utc,KEYS,MUNICIPAL_KEYS,safe_ratio)
from run_contextual_clustering_pilot import numerical_check

SCHEMES={
    'three':[(18,34),(35,59),(60,100)],
    'four':[(18,29),(30,44),(45,59),(60,100)],
    'five':[(18,29),(30,44),(45,59),(60,74),(75,100)]}
SEEDS=[17,42,2024]
NATIONAL_LN=98330348
NEW_FILES=['evaluate_age_band_representations.py','test_evaluate_age_band_representations.py']


def band_names(scheme):return [f'{a}-{b}' for a,b in SCHEMES[scheme]]


def helmert_basis(n):
    """Qij=1/sqrt(j(j+1)) para i<j; Qjj=−j/sqrt(j(j+1))."""
    require(n>=2,'Al menos dos intervalos.')
    basis=np.zeros((n,n-1))
    for j in range(1,n):basis[:j,j-1]=1/np.sqrt(j*(j+1));basis[j,j-1]=-j/np.sqrt(j*(j+1))
    return basis


def shape_block(delta):
    delta=np.asarray(delta,float);basis=helmert_basis(delta.shape[1]);level=delta.mean(axis=1)
    shape=delta-level[:,None];contrasts=delta@basis
    return level,shape,contrasts


def fit_block(contrasts):
    require(np.isfinite(contrasts).all(),'Bloque no finito.')
    mean=contrasts.mean(axis=0);scale=float(np.sqrt(np.mean(np.sum((contrasts-mean)**2,axis=1))))
    require(scale>1e-12,'Bloque sin varianza; no se inventa escala.')
    return dict(mean=mean.tolist(),scale=scale,n=len(contrasts),policy='Una escala RMS del bloque; sin normalizar filas.')


def apply_block(contrasts,parameters):return (contrasts-np.asarray(parameters['mean']))/parameters['scale']


def coverage_gate(current,baseline,total_municipalities=2477):
    municipal_drop=(baseline['municipalities']-current['municipalities'])/total_municipalities*100
    nominal_drop=(baseline['eligible_LN']-current['eligible_LN'])/NATIONAL_LN*100
    return dict(municipal_drop_pp=municipal_drop,nominal_drop_pp=nominal_drop,
        municipal_alert=municipal_drop>5,nominal_alert=nominal_drop>1,training_allowed=bool(municipal_drop<=5 and nominal_drop<=1))


def combine_cells(life_stage,broad,scheme):
    """Cuatro intervalos une los conteos 60–74/75–100; nunca promedia tasas."""
    keys=[*KEYS,'age_band']
    if scheme=='three':result=broad[keys+METRICS].copy()
    else:
        result=life_stage[keys+METRICS].copy()
        if scheme=='four':result['age_band']=result.age_band.replace({'60-74':'60-100','75-100':'60-100'})
        result=result.groupby(keys,as_index=False,sort=True,observed=True)[METRICS].sum(min_count=1)
    require(not result.duplicated(keys).any() and set(result.age_band)==set(band_names(scheme)),'Celdas inesperadas.')
    require(result.LN.eq(result.SV+result.NV+result.NS).all(),'Conteos inconsistentes.')
    return result


def section_counts(life_stage,broad,scheme):
    """TIPOSEC es disjunto; la unión de edades mayores se toma de broad, no se suma."""
    if scheme=='three':source=broad[broad.age_band.isin(band_names(scheme))]
    elif scheme=='five':source=life_stage[life_stage.age_band.isin(band_names(scheme))]
    else:source=pd.concat([life_stage[life_stage.age_band.isin(['18-29','30-44','45-59'])],broad[broad.age_band.eq('60-100')]])
    source=source[source.SEXO.isin(['0','1'])]
    keys=[*KEYS,'age_band']
    return source.groupby(keys,as_index=False,observed=True)[['section_count',*METRICS]].sum(min_count=1)


def build_profiles(cells,base,scheme):
    national=cells.groupby(['age_band','SEXO'],as_index=False)[METRICS].sum(min_count=1)
    national['national_rate']=safe_ratio(national.SV,national.SV+national.NV)
    work=cells.merge(national[['age_band','SEXO','national_rate']],on=['age_band','SEXO'],validate='many_to_one')
    work['specified_count']=work.SV+work.NV;work['rate']=safe_ratio(work.SV,work.specified_count)
    work['delta']=work.rate-work.national_rate;work['unspecified_rate']=safe_ratio(work.NS,work.LN)
    for field,flag in [('LN','low_LN'),('specified_count','low_specified'),('source_row_count','few_source_rows')]:
        work[flag]=work[field].lt(5 if flag=='few_source_rows' else 100)|work[field].isna()
    work['undefined_rate']=~np.isfinite(work.rate)
    work['supported']=~work[['low_LN','low_specified','few_source_rows','undefined_rate']].any(axis=1)
    profiles=base.copy();index=pd.MultiIndex.from_frame(profiles[KEYS]);supported=[]
    for j,band in enumerate(band_names(scheme)):
        part=work[work.age_band.eq(band)].set_index(KEYS).reindex(index)
        for field in ['LN','SV','NV','NS','specified_count','source_row_count','section_count','rate','delta','unspecified_rate',
            'national_rate','low_LN','low_specified','few_source_rows','undefined_rate','supported']:
            profiles[f'{field}_{j}']=part[field].to_numpy()
        supported.append(part.supported.fillna(False).to_numpy(bool))
        profiles=profiles.copy()  # Consolida bloques pequeños sin alterar columnas ni valores.
    n=len(SCHEMES[scheme]);delta=profiles[[f'delta_{j}' for j in range(n)]].to_numpy(float)
    level,shape,contrasts=shape_block(delta)
    profiles['relative_level']=level;profiles['complete_profile']=np.isfinite(delta).all(axis=1)
    profiles['is_eligible']=profiles.complete_profile&np.column_stack(supported).all(axis=1)
    for field in METRICS:profiles[field]=profiles[[f'{field}_{j}' for j in range(n)]].sum(axis=1,min_count=n) if field in ['LN','SV','NV','NS','source_row_count'] else 0
    profiles['specified_count']=profiles.SV+profiles.NV;profiles['unspecified_rate']=safe_ratio(profiles.NS,profiles.LN)
    profiles['participation_observed']=safe_ratio(profiles.SV,profiles.specified_count)
    profiles['has_high_ns_coordinate']=profiles[[f'unspecified_rate_{j}' for j in range(n)]].ge(.1).any(axis=1)
    profiles['min_section_count']=profiles[[f'section_count_{j}' for j in range(n)]].min(axis=1)
    profiles['min_specified_count']=profiles[[f'specified_count_{j}' for j in range(n)]].min(axis=1)
    for flag in ['low_LN','low_specified','few_source_rows','undefined_rate']:
        profiles[flag]=profiles[[f'{flag}_{j}' for j in range(n)]].fillna(True).any(axis=1)
    profiles['pending_reason']=['eligible' if good else '|'.join(flag for flag in ['undefined_rate','low_LN','low_specified','few_source_rows'] if row[flag])
        for good,(_,row) in zip(profiles.is_eligible,profiles.iterrows())]
    for j in range(n):profiles[f'shape_{j}']=shape[:,j]
    for j in range(n-1):profiles[f'contrast_{j}']=contrasts[:,j]
    require(profiles.row_id.is_unique and len(profiles)==len(base),'Universo de perfiles alterado.')
    return profiles,work,national


def describe_covariance(delta,scheme,scope,weights=None):
    """Espectro descriptivo; los autovectores nunca se usan para entrenar."""
    delta=np.asarray(delta,float);q=delta@helmert_basis(delta.shape[1]);w=np.ones(len(q)) if weights is None else np.asarray(weights,float)
    mean=np.average(q,axis=0,weights=w);covariance=((q-mean)*w[:,None]).T@(q-mean)/w.sum()
    eigenvalues,eigenvectors=np.linalg.eigh(covariance);order=np.argsort(eigenvalues)[::-1];eigenvalues=eigenvalues[order];eigenvectors=eigenvectors[:,order]
    total=np.trace(covariance);rows=[];loadings=[];basis=helmert_basis(delta.shape[1])
    for rank,(value,direction) in enumerate(zip(eigenvalues,eigenvectors.T),1):
        coefficients=basis@direction
        if coefficients[0]<0:coefficients=-coefficients
        rows.append(dict(scheme=scheme,scope=scope,profiles=len(q),direction=rank,variance=float(value),fraction=float(value/total)))
        loadings.extend(dict(scheme=scheme,scope=scope,direction=rank,age_band=band,coefficient=float(coefficient)) for band,coefficient in zip(band_names(scheme),coefficients))
    named=[];n=delta.shape[1]
    for name,vector in [('young_older',np.eye(n)[0]-np.eye(n)[-1]),
        *([('young_adult_middle_adult',np.eye(n)[1]-np.eye(n)[2])] if n>=4 else []),
        *([('older_split',np.eye(n)[3]-np.eye(n)[4])] if n==5 else [])]:
        vector=vector/np.linalg.norm(vector);values=delta@vector;variance=np.average((values-np.average(values,weights=w))**2,weights=w)
        named.append(dict(scheme=scheme,scope=scope,contrast=name,mean_pp=float(np.average(values,weights=w)*100),sd_pp=float(np.sqrt(variance)*100),
            variance_fraction=float(variance/total),coefficients=json.dumps(vector.tolist())))
    return pd.DataFrame(rows),pd.DataFrame(loadings),pd.DataFrame(named),covariance


class Experiment:
    valid_stage=Comparison.valid_stage
    verify_protected=Comparison.verify_protected
    checkpoint=Comparison.checkpoint
    table=Comparison.table
    bundle=Comparison.bundle
    bundle_paths=Comparison.bundle_paths
    load_arrays=Comparison.load_arrays
    load_model=Comparison.load_model
    fit_gmm=Comparison.fit_gmm
    fit_hdbscan=Comparison.fit_hdbscan

    def __init__(self,root,output,charts,report,replicates):
        self.root,self.output,self.charts,self.report=[Path(p).resolve() for p in [root,output,charts,report]]
        require(self.output.is_relative_to(self.root/'data/processed') and self.charts.is_relative_to(self.root/'analysis/charts') and self.report.is_relative_to(self.root/'analysis/reports'),'Destinos no autorizados.')
        self.replicates=replicates;self.dependencies=probe_dependencies();self.state_path=self.output/'metadata/state.json'
        require(self.dependencies['required_algorithms']['available'],'Usar .venv_pattern_algorithms; no se sustituyen bibliotecas.')
        self.source=self.root/'data/processed/participation_pattern_review';self.algorithm_source=self.root/'data/processed/pattern_algorithm_comparison'
        if self.state_path.exists():
            self.state=json.loads(self.state_path.read_text(encoding='utf8'))
            require(self.state['replicates']==replicates and self.state['charts']==str(self.charts) and self.state['report']==str(self.report),'Configuración de reanudación diferente.')
            require(self.state['dependencies']['imports']==self.dependencies['imports'],'Bibliotecas diferentes.')
            self.verify_protected()
        else:
            require(set(p.name for p in self.output.iterdir())=={'_RUNNING.json'} and not self.charts.exists() and not self.report.exists(),'Destinos previos: no sobrescribir.')
            protected=snapshot_inputs(self.root,self.output,self.charts)
            for base in [self.root/'analysis/scripts',self.root/'src']:
                for path in base.rglob('*'):
                    if path.is_file() and '__pycache__' not in path.parts and path.name not in NEW_FILES:protected[str(path)]=file_hash(path)
            for path in [self.root/'.gitignore',self.root/'.venv/pyvenv.cfg',self.root/'.venv_pattern_algorithms/pyvenv.cfg']:protected[str(path)]=file_hash(path)
            self.state=dict(started=utc(),status='running',replicates=replicates,dependencies=self.dependencies,protected_hashes=protected,
                stages={},errors=[],charts=str(self.charts),report=str(self.report))
            write_json(self.state_path,self.state)

    def stage_a(self):
        started=time.monotonic();paths=[];source=self.root/'data/processed/cluster_features';context=self.root/'data/processed/contextual_feature_review'
        for parent in [source,context,self.source,self.algorithm_source]:
            manifest=json.loads((parent/'metadata/run_manifest.json').read_text(encoding='utf8'));marker=json.loads((parent/'_SUCCESS').read_text())
            require(manifest['status']=='validated' and marker['manifest_sha256']==file_hash(parent/'metadata/run_manifest.json'),'Fuente no validada.')
            for relative,digest in manifest['artifact_hashes'].items():require(self.state['protected_hashes'][str(self.root/relative)]==digest,'Fuente alterada.')
        old=pd.read_parquet(self.source/'reference/profiles.parquet')
        base=old[['row_id',*KEYS,'state_name_label','municipality_name_label','district_reference_year']]
        cells={s:pd.read_parquet(source/f'matrices/c_{s}/cell_metadata.parquet') for s in ['broad','life_stage']}
        sections={s:pd.read_parquet(context/f'reference/section_segments_{s}.parquet') for s in ['broad','life_stage']}
        inventory=pd.read_parquet(context/'reference/section_inventory_2024.parquet')
        require(not inventory.duplicated([*MUNICIPAL_KEYS,'SECCION']).any(),'TIPOSEC no disjunto: no sumar conteos de sección.')
        rows=[];all_profiles={};bands=[];exclusions=[]
        for scheme in SCHEMES:
            cell=combine_cells(cells['life_stage'],cells['broad'],scheme)
            section=section_counts(sections['life_stage'],sections['broad'],scheme)
            compare_sums(cell,section,[*KEYS,'age_band'])
            cell=cell.merge(section[[*KEYS,'age_band','section_count']],on=[*KEYS,'age_band'],validate='one_to_one')
            profile,cell,national=build_profiles(cell,base,scheme);all_profiles[scheme]=profile
            compare_sums(profile,old,KEYS)
            eligible=profile[profile.is_eligible];municipal=eligible.groupby(MUNICIPAL_KEYS).size()
            row=dict(scheme=scheme,bands=len(SCHEMES[scheme]),available=len(profile),defined=int(profile.complete_profile.sum()),eligible=len(eligible),
                municipalities=len(municipal),both_sexes=int(municipal.eq(2).sum()),one_sex=int(municipal.eq(1).sum()),none=2477-len(municipal),
                eligible_LN=int(eligible.LN.sum()),national_LN_fraction=float(eligible.LN.sum()/NATIONAL_LN),
                high_ns_profiles=int(eligible.has_high_ns_coordinate.sum()),ns_rate=float(eligible.NS.sum()/eligible.LN.sum()),
                ns_q1=float(eligible.unspecified_rate.quantile(.25)),ns_median=float(eligible.unspecified_rate.median()),ns_q3=float(eligible.unspecified_rate.quantile(.75)),
                eligible_few_sections=int(eligible.min_section_count.lt(5).sum()))
            row.update(coverage_gate(row,row if not rows else rows[0]));rows.append(row)
            for band,part in cell.groupby('age_band'):
                bands.append(dict(scheme=scheme,age_band=band,profiles=len(part),median_LN=float(part.LN.median()),
                    median_specified=float(part.specified_count.median()),low_LN=int(part.low_LN.sum()),low_specified=int(part.low_specified.sum()),
                    few_source_rows=int(part.few_source_rows.sum()),fewer_five_sections=int(part.section_count.lt(5).sum()),
                    undefined=int(part.undefined_rate.sum()),NS=int(part.NS.sum()),LN=int(part.LN.sum())))
            for reason,part in profile[~profile.is_eligible].groupby('pending_reason'):
                exclusions.append(dict(scheme=scheme,reason=reason,profiles=len(part),LN=int(part.LN.sum())))
            for relative,frame in [(f'reference/{scheme}/profiles.parquet',profile),(f'reference/{scheme}/cells.parquet',cell),
                (f'reference/{scheme}/national_reference.parquet',national),(f'reference/{scheme}/pending.parquet',profile[~profile.is_eligible])]:paths.append(self.table(relative,frame))
        viable=[row['scheme'] for row in rows if row['training_allowed']]
        common=np.logical_and.reduce([all_profiles[s].is_eligible.to_numpy() for s in viable])
        all_common=np.logical_and.reduce([p.is_eligible.to_numpy() for p in all_profiles.values()])
        membership=base.copy();membership['common_viable']=common;membership['common_all_descriptive_only']=all_common
        for s,p in all_profiles.items():membership['eligible_'+s]=p.is_eligible.to_numpy()
        paths.append(self.table('reference/population_membership.parquet',membership))
        for relative,frame in [('metadata/coverage.csv',pd.DataFrame(rows)),('metadata/band_support.csv',pd.DataFrame(bands)),('metadata/exclusions.csv',pd.DataFrame(exclusions))]:paths.append(self.table(relative,frame))
        gate=dict(viable=viable,not_trained=[r['scheme'] for r in rows if not r['training_allowed']],common_profiles=int(common.sum()),
            all_common_descriptive_only=int(all_common.sum()),rule='Alertas >5 pp municipal o >1 pp LN; cualquiera impide entrenamiento.',
            section_policy='Número exacto por banda; cuatro/60–100 usa broad para evitar doble conteo. No cambia umbral de filas fuente.')
        path=self.output/'metadata/coverage_gate.json';write_json(path,gate);paths.append(path)
        paths.append(self.table('reference/complementary_and_full_broad.parquet',pd.read_parquet(self.source/'reference/broad_complete_reference.parquet')))
        self.checkpoint('A',paths,started,f'Cobertura auditada; viables={viable}; cinco no se entrenará si falla; común={int(common.sum()):,}.')

    def gate(self):return json.loads((self.output/'metadata/coverage_gate.json').read_text(encoding='utf8'))

    def profile(self,scheme):return pd.read_parquet(self.output/f'reference/{scheme}/profiles.parquet')

    def delta(self,profiles,scheme):return profiles[[f'delta_{j}' for j in range(len(SCHEMES[scheme]))]].to_numpy(float)

    def contexts(self):return json.loads((self.output/'metadata/contexts.json').read_text(encoding='utf8'))

    def context_data(self,context):
        spec=self.contexts()[context];profile=self.profile(spec['scheme']);membership=pd.read_parquet(self.output/'reference/population_membership.parquet')
        mask=profile.is_eligible.to_numpy() if spec['scope']=='natural' else membership.common_viable.to_numpy()
        main=profile.loc[mask].reset_index(drop=True);features=pd.read_parquet(self.output/f'features/{context}/matrix.parquet')
        require(features.row_id.equals(main.row_id),'Matriz y población desalineadas.')
        return profile,main,features.drop(columns='row_id').to_numpy(float),mask

    def stage_b(self):
        started=time.monotonic();gate=self.gate();membership=pd.read_parquet(self.output/'reference/population_membership.parquet')
        common=membership.common_viable.to_numpy();all_common=membership.common_all_descriptive_only.to_numpy();paths=[];contexts={};spectra=[];loadings=[];named=[];bandwidth=[]
        profiles={s:self.profile(s) for s in SCHEMES}
        high=all_common.copy()
        for p in profiles.values():high&=p.min_specified_count.ge(500).to_numpy()
        for scheme,profile in profiles.items():
            n=len(SCHEMES[scheme]);q=self.delta(profile,scheme)@helmert_basis(n)
            params=fit_block(q[profile.is_eligible]);matrix=pd.DataFrame(apply_block(q[profile.is_eligible],params),columns=[f'shape_contrast_{j+1}' for j in range(n-1)])
            matrix.insert(0,'row_id',profile.loc[profile.is_eligible,'row_id'].to_numpy())
            paths.append(self.table(f'diagnostic_features/{scheme}.parquet',matrix))
            masks={'natural':profile.is_eligible.to_numpy(),'common_all_descriptive':all_common,'high_support_all_descriptive':high}
            if scheme in gate['viable']:masks['common_viable']=common
            for scope,mask in masks.items():
                delta=self.delta(profile.loc[mask],scheme)
                for weight_name,weights in [('equal_profile',None),('LN_descriptive',profile.loc[mask,'LN'].to_numpy())] if scope=='common_all_descriptive' else [('equal_profile',None)]:
                    scope_name=scope+'_'+weight_name
                    eigen,coefficient,contrast,cov=describe_covariance(delta,scheme,scope_name,weights)
                    spectra.append(eigen);loadings.append(coefficient);named.append(contrast)
                    paths.append(self.table(f'diagnostics/covariance_{scheme}_{scope_name}.parquet',pd.DataFrame(cov)))
            for scope,mask in [('natural',profile.is_eligible.to_numpy()),('common_all_descriptive',all_common)]:
                delta=self.delta(profile.loc[mask],scheme);widths=np.array([b-a+1 for a,b in SCHEMES[scheme]],float);weights=widths/widths.sum()
                weighted_mean=delta@weights;weighted_shape=(delta-weighted_mean[:,None])*np.sqrt(weights)
                variance=np.cov(weighted_shape,rowvar=False,ddof=0);eigen=np.linalg.eigvalsh(variance)[::-1]
                rng=np.random.default_rng(2184);left=rng.integers(0,len(delta),20000);right=rng.integers(0,len(delta),20000)
                equal_shape=delta@helmert_basis(n);de=np.linalg.norm(equal_shape[left]-equal_shape[right],axis=1);dw=np.linalg.norm(weighted_shape[left]-weighted_shape[right],axis=1)
                from scipy.stats import spearmanr
                bandwidth.append(dict(scheme=scheme,scope=scope,profiles=len(delta),width_weights=json.dumps(weights.tolist()),
                    dominant_width_fraction=float(eigen[0]/eigen.sum()),median_mean_change_pp=float(np.median(np.abs(weighted_mean-delta.mean(axis=1)))*100),
                    distance_spearman=float(spearmanr(de,dw).statistic),pairs=20000))
            if scheme not in gate['viable']:continue
            for scope,mask in [('natural',profile.is_eligible.to_numpy()),('common',common)]:
                context=f'{scheme}_{scope}';parameters=fit_block(q[mask]);values=apply_block(q[mask],parameters)
                frame=pd.DataFrame(values,columns=[f'shape_contrast_{j+1}' for j in range(n-1)]);frame.insert(0,'row_id',profile.loc[mask,'row_id'].to_numpy())
                paths.append(self.table(f'features/{context}/matrix.parquet',frame))
                path=self.output/f'features/{context}/parameters.json';write_json(path,dict(**parameters,basis=helmert_basis(n).tolist(),bands=band_names(scheme),scope=scope));paths.append(path)
                fingerprint=hashlib.sha256(values.tobytes()).hexdigest();canonical=next((c for c,v in contexts.items() if v['scheme']==scheme and v['matrix_sha256']==fingerprint and v['profiles']==len(frame)),context)
                contexts[context]=dict(scheme=scheme,scope=scope,profiles=len(frame),dimensions=n-1,matrix_sha256=fingerprint,canonical=canonical)
        prior=pd.read_parquet(self.source/'features/r2.parquet');current=pd.read_parquet(self.output/'features/three_natural/matrix.parquet')
        require(prior.row_id.equals(current.row_id) and np.array_equal(prior.drop(columns='row_id').to_numpy(),current.drop(columns='row_id').to_numpy()),'Tres no reproduce exactamente R2.')
        for relative,frame in [('metadata/covariance_spectrum.csv',pd.concat(spectra)),('metadata/diagnostic_loadings.csv',pd.concat(loadings)),
            ('metadata/named_contrasts.csv',pd.concat(named)),('metadata/bandwidth_diagnostics.csv',pd.DataFrame(bandwidth))]:paths.append(self.table(relative,frame))
        path=self.output/'metadata/contexts.json';write_json(path,contexts);paths.append(path)
        path=self.output/'metadata/feature_contract.json';write_json(path,dict(unit='municipality_sex',year=2024,schemes={s:band_names(s) for s in SCHEMES},
            distance='Contrastes Helmert de d−media(d); centro por población y una escala RMS por bloque.',
            excluded=['age_mean','SEXO','EDOCVE','MPIOCVE','TIPOSEC','LN','NS'],
            five_status='diagnostic_only_if_coverage_gate_fails',covariance_spectrum='Sólo diagnóstico: no autovectores como características.',
            widths='Igual peso por intervalo en principal; sensibilidad descriptiva de anchos, no selección automática.',
            section_count='Conteos exactos previos por bandas originales; unión 60–100 tomada de broad.',
            exact_reference=dict(path='data/processed/cluster_features/reference/exact_age_2024.parquet',sha256=file_hash(self.root/'data/processed/cluster_features/reference/exact_age_2024.parquet'))));paths.append(path)
        self.checkpoint('B',paths,started,'Bases fijas 2/3/4D; tres reproduce R2; población común viable, espectros y anchos; cinco sólo descriptivo si no viable.')

    def fit_kmeans(self,model_id,values,k,seed,weights=None,initial=None):
        from sklearn.cluster import KMeans
        parameters=dict(n_clusters=k,random_state=seed,n_init=10 if initial is None else 1,max_iter=1000,tol=0,algorithm='lloyd')
        specification={**parameters,'initialization':'kmeans++' if initial is None else 'reference_centers',
            'weights_sha256':hashlib.sha256(weights.tobytes()).hexdigest() if weights is not None else None}
        def fit():
            model=KMeans(**parameters,init='k-means++' if initial is None else initial).fit(values,sample_weight=weights)
            require(model.n_iter_<1000 and len(np.unique(model.labels_))==k,'K-Means no convergente.')
            check=numerical_check(values,np.ones(len(values)) if weights is None else weights,dict(labels=model.labels_,centers=model.cluster_centers_,inertia=model.inertia_))
            return model,dict(labels=model.labels_,centers=model.cluster_centers_),dict(sse=float(model.inertia_),iterations=int(model.n_iter_),converged=True,numerical_check=check)
        return self.bundle(model_id,values,specification,fit)

    def stage_c(self):
        import joblib
        started=time.monotonic();records=[];ids=[]
        for context,spec in self.contexts().items():
            if spec['canonical']!=context:continue
            _,main,values,_=self.context_data(context)
            prior=context=='three_natural'
            configurations=([('kmeans',k,seed,None) for k in range(2,7) for seed in SEEDS]+[('gmm',k,seed,None) for k in range(1,7) for seed in SEEDS]+
                [('hdbscan',None,None,(m,s,single)) for m,s,single in [(m,s,True) for m in [50,100,200,400] for s in [10,30,60]]+[(50,10,False),(200,30,False)]])
            for algorithm,k,seed,hdb in configurations:
                local=f'kmeans_k{k}_seed{seed}' if algorithm=='kmeans' else f'gmm_full_k{k}_seed{seed}' if algorithm=='gmm' else f'hdbscan_m{hdb[0]}_s{hdb[1]}_single{int(hdb[2])}'
                model_id=f'{context}/{local}';ids.append(model_id)
                if prior:
                    folder=self.algorithm_source/'models'/local;manifest=json.loads((folder/'_COMPLETE.json').read_text(encoding='utf8'))
                    require(manifest['input_sha256']==hashlib.sha256(values.tobytes()).hexdigest(),'No se puede reutilizar sobre otra matriz.')
                    for name,digest in manifest['files'].items():require(file_hash(folder/name)==digest,'Modelo previo alterado.')
                    def reuse(folder=folder):
                        with np.load(folder/'arrays.npz',allow_pickle=False) as stored:arrays={name:stored[name].copy() for name in stored.files}
                        details=json.loads((folder/'details.json').read_text(encoding='utf8'));details['source_seconds']=details.get('seconds');details['reused']=True
                        return joblib.load(folder/'model.joblib'),arrays,details
                    model,arrays,details=self.bundle(model_id,values,dict(reused_from=str(folder.relative_to(self.root))),reuse)
                elif algorithm=='kmeans':model,arrays,details=self.fit_kmeans(model_id,values,k,seed)
                elif algorithm=='gmm':model,arrays,details=self.fit_gmm(model_id,values,k,'full',seed)
                else:model,arrays,details=self.fit_hdbscan(model_id,values,*hdb)
                actual_k=len(np.unique(arrays['labels'][arrays['labels']>=0]));configuration=f'k{k}' if algorithm!='hdbscan' else local
                records.append(dict(context=context,model_id=model_id,local_id=local,algorithm=algorithm,configuration=configuration,k=k if k is not None else actual_k,
                    seed=seed,reused=prior,**({key:details[key] for key in ['sse','bic','aic','converged','ambiguous_80','mean_normalized_entropy','seconds'] if key in details}),
                    min_cluster_size=hdb[0] if hdb else None,min_samples=hdb[1] if hdb else None,allow_single_cluster=hdb[2] if hdb else None))
                print(f'C: {context} {local}; '+('recuperado.' if prior else 'guardado.'),flush=True)
        self.checkpoint('C',self.bundle_paths(ids)+[self.table('metadata/model_index.csv',pd.DataFrame(records))],started,
            f'{len(records)} resultados principales; R2 natural reutilizado; contextos idénticos comparten modelos; ninguna ejecución cinco.')

    def labels(self,row):return self.load_arrays(row.model_id)['labels']

    def describe_groups(self,main,labels,context,model_id):
        scheme=self.contexts()[context]['scheme'];rows=[];curves=[];labels=np.asarray(labels)
        for cluster in np.unique(labels):
            part=main.loc[labels==cluster]
            rows.append(dict(context=context,model_id=model_id,cluster=int(cluster),profiles=len(part),municipalities=part.groupby(MUNICIPAL_KEYS).ngroups,
                women_fraction=float(part.SEXO.eq('1').mean()),median_LN=float(part.LN.median()),median_min_specified=float(part.min_specified_count.median()),
                low_section_fraction=float(part.min_section_count.lt(5).mean()),high_ns_fraction=float(part.has_high_ns_coordinate.mean()),
                participation=float(part.SV.sum()/part.specified_count.sum()),relative_level=float(part.relative_level.mean()),
                **{field:int(part[field].sum()) for field in METRICS}))
            for j,band in enumerate(band_names(scheme)):
                sv,nv=int(part[f'SV_{j}'].sum()),int(part[f'NV_{j}'].sum())
                curves.append(dict(context=context,model_id=model_id,cluster=int(cluster),age_band=band,mean_rate=float(part[f'rate_{j}'].mean()),
                    mean_delta=float(part[f'delta_{j}'].mean()),mean_shape=float(part[f'shape_{j}'].mean()),aggregate_rate=sv/(sv+nv) if sv+nv else np.nan,
                    LN=int(part[f'LN_{j}'].sum()),SV=sv,NV=nv,NS=int(part[f'NS_{j}'].sum())))
        profile=pd.DataFrame(rows);require(np.array_equal(profile[METRICS].sum().to_numpy(),main[METRICS].sum().to_numpy()),'Conteos de clusters alterados.')
        return profile,pd.DataFrame(curves)

    def stage_d(self):
        from sklearn.metrics import adjusted_rand_score
        started=time.monotonic();index=pd.read_csv(self.output/'metadata/model_index.csv');records=[];paths=[];groups=[];curves=[];incremental=[]
        prior_metrics=pd.read_csv(self.algorithm_source/'metadata/model_metrics.csv').set_index('model_id')
        base=self.profile('three')
        for context,part in index.groupby('context',sort=False):
            _,main,values,_=self.context_data(context);scheme=self.contexts()[context]['scheme']
            q=self.delta(main,scheme)@helmert_basis(len(SCHEMES[scheme]))
            aligned=base.set_index('row_id').loc[main.row_id];q0=self.delta(aligned,'three')@helmert_basis(3)
            design=np.column_stack([np.ones(len(main)),q0]);beta=np.linalg.lstsq(design,q,rcond=None)[0];residual=q-design@beta
            total=float(np.sum((q-q.mean(axis=0))**2));residual_total=float(np.sum(residual**2))
            incremental.append(dict(context=context,profiles=len(main),linear_residual_fraction=residual_total/total,
                interpretation='Variación no reconstruida linealmente desde R2; descriptiva, no información electoral validada.'))
            paths.append(self.table(f'diagnostics/{context}_linear_residuals.parquet',pd.DataFrame(residual).assign(row_id=main.row_id)))
            km=part[part.algorithm.eq('kmeans')];baseline={int(k):self.labels(p.loc[p.sse.idxmin()]) for k,p in km.groupby('k')}
            for i,(_,row) in enumerate(part.iterrows(),1):
                labels=self.labels(row);assigned=labels>=0;cache=self.output/f'metadata/metric_cache/{context}/{row.local_id}.json'
                if cache.exists():result=json.loads(cache.read_text(encoding='utf8'))
                else:
                    if bool(row.reused):result=prior_metrics.loc[row.local_id].to_dict()
                    else:result=label_metrics(values,labels,main,baseline.get(int(row.k)))
                    result={k:v for k,v in result.items() if not isinstance(v,(dict,list))}
                    result['metric_reused']=bool(row.reused)
                    if assigned.sum()>1:
                        z=q[assigned];r=residual[assigned];y=labels[assigned]
                        within=sum(float(np.sum((z[y==c]-z[y==c].mean(axis=0))**2)) for c in np.unique(y));variation=float(np.sum((z-z.mean(axis=0))**2))
                        result['shape_explained']=1-within/variation if variation>1e-15 else np.nan
                        rt=float(np.sum((r-r.mean(axis=0))**2));rw=sum(float(np.sum((r[y==c]-r[y==c].mean(axis=0))**2)) for c in np.unique(y))
                        result['linear_residual_explained']=1-rw/rt if rt>1e-12 else np.nan
                    result['margin_low_fraction']=np.nan
                    if row.algorithm=='kmeans':
                        centers=self.load_arrays(row.model_id)['centers'];dist=np.sort(np.linalg.norm(values[:,None,:]-centers[None,:,:],axis=2),axis=1)
                        margin=safe_ratio(dist[:,1]-dist[:,0],dist[:,1]);result['margin_low_fraction']=float((margin<=.1).mean())
                    write_json(cache,result)
                records.append({**result,**row.to_dict()});paths.append(cache)
                g,c=self.describe_groups(main,labels,context,row.model_id);groups.append(g);curves.append(c)
                if i%8==0:print(f'D: {context}, {i}/{len(part)} métricas; '+('referencia recuperada.' if context=='three_natural' else 'exactas por bloques.'),flush=True)
        metrics=pd.DataFrame(records);seeds=[];best=[]
        for (context,algorithm,configuration),part in metrics.groupby(['context','algorithm','configuration']):
            for a,b in combinations(part.index,2):seeds.append(dict(context=context,algorithm=algorithm,configuration=configuration,
                ari=float(adjusted_rand_score(self.labels(metrics.loc[a]),self.labels(metrics.loc[b])))))
            objective='sse' if algorithm=='kmeans' else 'bic' if algorithm=='gmm' else None
            best.append(part.loc[part[objective].idxmin()] if objective else part.iloc[0])
        seed_table=pd.DataFrame(seeds);summary=pd.DataFrame(best)
        ss=seed_table.groupby(['context','algorithm','configuration']).agg(seed_ari_min=('ari','min')).reset_index()
        summary=summary.merge(ss,on=['context','algorithm','configuration'],how='left',validate='one_to_one')
        common_three=summary[summary.context.eq('three_common')];other_context=self.contexts()['four_common']['canonical'];common_four=summary[summary.context.eq(other_context)]
        comparisons=[]
        _,a,_,_=self.context_data('three_common');_,b,_,_=self.context_data('four_common');require(a.row_id.equals(b.row_id),'Población común diferente.')
        for _,left in common_three.iterrows():
            match=common_four[common_four.algorithm.eq(left.algorithm)&common_four.configuration.eq(left.configuration)]
            if len(match)==1:
                right=match.iloc[0];comparisons.append(dict(left=left.model_id,right=right.model_id,algorithm=left.algorithm,configuration=left.configuration,
                    profiles=len(a),**common_partition_stability(self.labels(left),self.labels(right))))
        for relative,frame in [('metadata/model_metrics.csv',metrics),('metadata/solution_summary.csv',summary),('metadata/seed_stability.csv',seed_table),
            ('metadata/cluster_profiles.csv',pd.concat(groups)),('metadata/cluster_curves.csv',pd.concat(curves)),
            ('metadata/incremental_variance.csv',pd.DataFrame(incremental)),('metadata/common_representation_ari.csv',pd.DataFrame(comparisons))]:paths.append(self.table(relative,frame))
        self.checkpoint('D',paths,started,'Poblaciones naturales separadas de la comparación común; separación, curvas, residuos lineales y estabilidad de semillas.')

    def select(self,explicit):
        summary=pd.read_csv(self.output/'metadata/solution_summary.csv')
        if not explicit:
            c4=self.contexts()['four_common']['canonical'];rows=[]
            for context in ['three_common',c4]:
                part=summary[summary.context.eq(context)&summary.algorithm.eq('kmeans')&summary.k.eq(2)];rows.append(part.iloc[0].model_id)
            part=summary[summary.context.eq(c4)&summary.algorithm.eq('gmm')&summary.converged.eq(True)]
            rows.append(part.loc[part.bic.idxmin(),'model_id']);explicit=rows
        require(1<=len(explicit)<=3 and len(set(explicit))==len(explicit),'Máximo tres candidatas distintas.')
        require(set(explicit)<=set(summary.model_id),'Candidata no calculada o bloqueada por cobertura.')
        require(self.state.get('candidates',explicit)==explicit,'Candidatas distintas; no repetir estabilidad.')
        self.state['candidates']=explicit;write_json(self.state_path,self.state)
        path=self.output/'metadata/candidate_selection.json'
        if not path.exists():write_json(path,dict(candidates=explicit,metrics_sha256=file_hash(self.output/'metadata/solution_summary.csv'),
            rationale='Tras D: dos K-Means K=2 comparables por parsimonia y estabilidad de semillas; GMM de BIC mínimo dentro de cuatro intervalos como prueba de información adicional y solapamiento. No elección definitiva. HDBSCAN de baja cobertura no se promueve; cinco está bloqueado.'))
        return summary.set_index('model_id').loc[explicit].reset_index()

    def candidate_rows(self):return pd.read_csv(self.output/'metadata/solution_summary.csv').set_index('model_id').loc[self.state['candidates']].reset_index()

    def native_fit(self,row,values,model_id,weights=None,initial=None):
        if row.algorithm=='kmeans':return self.fit_kmeans(model_id,values,int(row.k),17,weights,initial)
        if row.algorithm=='gmm':return self.fit_gmm(model_id,values,int(row.k),'full',17)
        return self.fit_hdbscan(model_id,values,int(row.min_cluster_size),int(row.min_samples),bool(row.allow_single_cluster))

    def predictions(self,row,model,arrays,values):
        if row.algorithm=='gmm':return model.predict(values)
        if row.algorithm=='kmeans':return np.linalg.norm(values[:,None,:]-arrays['centers'][None,:,:],axis=2).argmin(axis=1)
        raise ValueError('HDBSCAN sólo se compara sobre observaciones comunes; sin OOB inventado.')

    def stage_e(self,explicit):
        from sklearn.metrics import adjusted_rand_score
        started=time.monotonic();selected=self.select(explicit);paths=[];records=[];coverages=[];ids=[];curves=[];group_rows=[]
        samples=pd.read_parquet(self.source/'reference/municipality_membership.parquet')
        keys=pd.MultiIndex.from_frame(samples[MUNICIPAL_KEYS]);data={row.context:self.context_data(row.context) for _,row in selected.iterrows()}
        common=pd.read_parquet(self.output/'reference/population_membership.parquet').common_viable.to_numpy()
        for _,row in selected.iterrows():require(np.array_equal(data[row.context][3],common),'Estabilidad debe usar la misma población común.')
        for replicate in range(self.replicates):
            draw=samples[f'sample_{replicate:03d}'].to_numpy(bool);require(draw.sum()==1981,'Muestra incorrecta.')
            first=next(iter(data.values()))[1];inbag=pd.MultiIndex.from_frame(first[MUNICIPAL_KEYS]).isin(keys[draw]);oob=~inbag
            coverages.append(dict(replicate=replicate,drawn_municipalities=int(draw.sum()),training_profiles=int(inbag.sum()),oob_profiles=int(oob.sum()),
                training_municipalities=first.loc[inbag].groupby(MUNICIPAL_KEYS).ngroups,training_LN=int(first.loc[inbag,'LN'].sum()),
                eligible_LN_fraction=float(first.loc[inbag,'LN'].sum()/first.LN.sum())))
            for _,row in selected.iterrows():
                full,main,values,mask=data[row.context];parameters=fit_block(values[inbag]);train=apply_block(values[inbag],parameters);whole=apply_block(values,parameters)
                model_id=f'resampling/sample_{replicate:03d}/{row.model_id}';ids.append(model_id)
                model,arrays,details=self.native_fit(row,train,model_id);labels=arrays['labels'];baseline=self.labels(row)
                projected=self.predictions(row,model,arrays,whole) if row.algorithm!='hdbscan' else None
                result=dict(model_id=row.model_id,context=row.context,algorithm=row.algorithm,replicate=replicate,seconds=details['seconds'],
                    ari_oob=float(adjusted_rand_score(baseline[oob],projected[oob])) if projected is not None else np.nan,
                    **common_partition_stability(baseline[inbag],labels))
                if row.algorithm=='gmm':result.update(posterior_summary(model.predict_proba(whole[oob])))
                records.append(result)
                assignment=full[['row_id',*KEYS,'is_eligible']].copy();flag=np.zeros(len(full),bool);flag[mask]=inbag;assignment['is_training']=flag;assignment['comparison_eligible']=mask
                raw=pd.array([pd.NA]*len(main),dtype='Int64');raw[inbag]=labels;column=pd.array([pd.NA]*len(full),dtype='Int64');column[mask]=raw;assignment['training_label']=column
                projection=pd.array([pd.NA]*len(full),dtype='Int64')
                if projected is not None:projection[mask]=projected
                assignment['projected_label']=projection
                paths.append(self.table(f'resampling/assignments/sample_{replicate:03d}/{row.model_id}.parquet',assignment))
                path=self.output/f'models/{model_id}/transform.json'
                if not path.exists():write_json(path,parameters)
                paths.append(path)
                g,c=self.describe_groups(main.loc[inbag].reset_index(drop=True),labels,row.context,model_id);group_rows.append(g);curves.append(c)
            print(f'E: muestra {replicate+1}/{self.replicates}; {int(inbag.sum()):,} perfiles, {int(oob.sum()):,} OOB comunes.',flush=True)
        paths.extend(self.bundle_paths(ids));paths.append(self.table('resampling/municipality_membership.parquet',samples))
        for relative,frame in [('metadata/resampling_metrics.csv',pd.DataFrame(records)),('metadata/resampling_coverage.csv',pd.DataFrame(coverages)),
            ('metadata/resampling_curves.csv',pd.concat(curves)),('metadata/resampling_profiles.csv',pd.concat(group_rows))]:paths.append(self.table(relative,frame))
        # Las sensibilidades NS comparan la misma población de NS bajo en las representaciones viables.
        low=np.ones(common.sum(),bool)
        for context in ['three_common','four_common']:low&=~self.context_data(context)[1].has_high_ns_coordinate.to_numpy()
        sensitivity=[];sex_rows=[];boundaries=[];ids=[]
        for _,row in selected.iterrows():
            full,main,values,mask=data[row.context];baseline=self.labels(row)
            scenarios=[('low_ns_common',low,None,None)]
            if row.algorithm=='kmeans':scenarios.append(('equal_municipality',np.ones(len(main),bool),1/main.groupby(MUNICIPAL_KEYS).row_id.transform('size').to_numpy(),self.load_arrays(row.model_id)['centers']))
            for scenario,chosen,weights,initial in scenarios:
                model_id=f'sensitivity/{scenario}/{row.model_id}';ids.append(model_id)
                model,arrays,details=self.native_fit(row,values[chosen],model_id,weights[chosen] if weights is not None else None,initial)
                projected=self.predictions(row,model,arrays,values) if row.algorithm!='hdbscan' else None
                sensitivity.append(dict(model_id=row.model_id,scenario=scenario,training_profiles=int(chosen.sum()),training_LN=int(main.loc[chosen,'LN'].sum()),
                    training_municipalities=main.loc[chosen].groupby(MUNICIPAL_KEYS).ngroups,
                    ari_all_eligible=float(adjusted_rand_score(baseline,projected)) if projected is not None else np.nan,
                    **common_partition_stability(baseline[chosen],arrays['labels'])))
                assignment=full[['row_id',*KEYS,'is_eligible']].copy();raw=pd.array([pd.NA]*len(main),dtype='Int64');raw[chosen]=arrays['labels']
                column=pd.array([pd.NA]*len(full),dtype='Int64');column[mask]=raw;assignment['training_label']=column
                projection=pd.array([pd.NA]*len(full),dtype='Int64')
                if projected is not None:projection[mask]=projected
                assignment['projected_label']=projection
                paths.append(self.table(f'sensitivity/assignments/{scenario}/{row.model_id}.parquet',assignment))
            if row.algorithm=='kmeans':
                dist=np.sort(np.linalg.norm(values[:,None,:]-self.load_arrays(row.model_id)['centers'][None,:,:],axis=2),axis=1)
                proximity=safe_ratio(dist[:,1]-dist[:,0],dist[:,1]);criterion='margin_le_0.1';uncertain=proximity<=.1
            elif row.algorithm=='gmm':
                proximity=self.load_model(row.model_id).predict_proba(values).max(axis=1);criterion='max_posterior_lt_0.8';uncertain=proximity<.8
            else:proximity=self.load_arrays(row.model_id)['membership_strength'];criterion='strength_lt_0.5';uncertain=proximity<.5
            for sex in ['0','1']:
                chosen=main.SEXO.eq(sex).to_numpy();g,c=self.describe_groups(main.loc[chosen].reset_index(drop=True),baseline[chosen],row.context,row.model_id)
                g['SEXO']=sex;sex_rows.append(g)
            for scope,chosen in [('all',np.ones(len(main),bool)),('high_ns',main.has_high_ns_coordinate.to_numpy()),('low_ns',~main.has_high_ns_coordinate.to_numpy()),
                ('min_specified_lt_500',main.min_specified_count.lt(500).to_numpy()),('few_sections',main.min_section_count.lt(5).to_numpy())]:
                boundaries.append(dict(model_id=row.model_id,scope=scope,profiles=int(chosen.sum()),criterion=criterion,
                    uncertain_fraction=float(uncertain[chosen].mean()) if chosen.any() else np.nan))
        paths.extend(self.bundle_paths(ids));paths.append(self.output/'metadata/candidate_selection.json')
        for relative,frame in [('metadata/quality_sensitivity.csv',pd.DataFrame(sensitivity)),('metadata/sex_composition.csv',pd.concat(sex_rows)),
            ('metadata/boundary_quality.csv',pd.DataFrame(boundaries))]:paths.append(self.table(relative,frame))
        self.checkpoint('E',paths,started,f'{len(selected)} candidatas, muestras municipales comunes; NS común y peso municipal sólo en API compatible; sin cinco.')

    def plot_space(self,ax,values,labels,pair,title):
        for cluster in np.unique(labels):
            mask=labels==cluster
            ax.scatter(values[mask,pair[0]],values[mask,pair[1]],s=7,alpha=.35,color='#aaaaaa' if cluster<0 else plt.get_cmap('tab10')(int(cluster)%10),
                label='Ruido' if cluster<0 else f'{int(cluster)}: {int(mask.sum()):,}',rasterized=True)
        ax.set(title=title,xlabel=f'Contraste fijo {pair[0]+1} / RMS',ylabel=f'Contraste fijo {pair[1]+1} / RMS');ax.set_aspect('equal',adjustable='box');ax.legend(fontsize=7)

    def plot_results(self):
        from matplotlib.patches import Ellipse
        from scipy.stats import chi2
        coverage=pd.read_csv(self.output/'metadata/coverage.csv');support=pd.read_csv(self.output/'metadata/band_support.csv')
        spectrum=pd.read_csv(self.output/'metadata/covariance_spectrum.csv');summary=pd.read_csv(self.output/'metadata/solution_summary.csv')
        curves=pd.read_csv(self.output/'metadata/cluster_curves.csv');candidates=self.candidate_rows()
        colors=['#38827e','#567eae','#b66b65'];names=['Tres','Cuatro','Cinco']
        fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
        axes[0,0].bar(names,coverage.eligible,color=colors);axes[0,0].set(title='Perfiles municipio/sexo con soporte',ylabel='Perfiles')
        axes[0,1].bar(names,coverage.municipalities/2477,color=colors);axes[0,1].yaxis.set_major_formatter(PercentFormatter(1));axes[0,1].set(title='Cobertura municipal · al menos un sexo',ylim=(0,1))
        axes[1,0].bar(names,coverage.national_LN_fraction,color=colors);axes[1,0].yaxis.set_major_formatter(PercentFormatter(1));axes[1,0].set(title='LN elegible / LN nacional',ylim=(.97,1))
        older=support[support.age_band.isin(['60-100','60-74','75-100'])]
        axes[1,1].bar([f'{r.scheme}\n{r.age_band}' for _,r in older.iterrows()],older.median_specified,color='#ba985c');axes[1,1].axhline(100,c='black',ls='--',label='Umbral de referencia')
        axes[1,1].set(title='Mediana SV+NV en perfiles disponibles',ylabel='Denominador');axes[1,1].legend(fontsize=8)
        fig.suptitle('Cinco intervalos: alerta municipal; matrices conservadas, sin entrenar modelos')
        save_figure(fig,self.charts/'coverage_support.png')
        membership=pd.read_parquet(self.output/'reference/population_membership.parquet');mask=membership.common_all_descriptive_only.to_numpy()
        fig,axes=plt.subplots(1,3,figsize=(15,5),layout='constrained')
        for ax,scheme,name in zip(axes,SCHEMES,names):
            profile=self.profile(scheme).loc[mask];values=profile[[f'shape_{j}' for j in range(len(SCHEMES[scheme]))]].to_numpy()*100
            ax.boxplot(values,tick_labels=band_names(scheme),showfliers=False);ax.set(title=f'{name}: {len(profile):,} perfiles comunes',ylabel='Forma centrada (pp)',xlabel='Intervalos candidatos');ax.tick_params(axis='x',rotation=35)
        fig.suptitle('Diagnóstico en la misma población de 3,907 perfiles · no son modelos de cinco intervalos\nLas colas se conservan en datos; sólo se omiten puntos de boxplot para lectura')
        save_figure(fig,self.charts/'feature_distributions.png')
        fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
        for ax,scope,title in zip(axes,['common_all_descriptive_equal_profile','high_support_all_descriptive_equal_profile'],['Mismos 3,907 perfiles','Mismos 1,788 con SV+NV≥500 en toda banda']):
            bottom=np.zeros(3)
            for rank in range(1,5):
                fractions=[float(spectrum[(spectrum.scheme==s)&(spectrum.scope==scope)&(spectrum.direction==rank)].fraction.sum()) for s in SCHEMES]
                ax.bar(names,fractions,bottom=bottom,label=f'Dirección {rank}');bottom+=fractions
            ax.yaxis.set_major_formatter(PercentFormatter(1));ax.set(title=title,ylabel='Fracción de varianza de forma',ylim=(0,1));ax.legend(fontsize=8)
        fig.suptitle('Espectro de covarianza sólo descriptivo · las direcciones no entran en el entrenamiento')
        save_figure(fig,self.charts/'contrast_variance.png')
        for algorithm,file_name in [('kmeans','kmeans_comparison.png'),('gmm','gmm_components.png'),('hdbscan','hdbscan_noise.png')]:
            fig,axes=plt.subplots(3,3,figsize=(15,13),layout='constrained')
            for row_index,context in enumerate(['three_common',self.contexts()['four_common']['canonical']]):
                part=summary[summary.context.eq(context)&summary.algorithm.eq(algorithm)]
                row=part[part.k.eq(2)].iloc[0] if algorithm=='kmeans' else part.loc[part.bic.idxmin()] if algorithm=='gmm' else part[part.local_id.eq('hdbscan_m50_s10_single0')].iloc[0]
                _,main,values,_=self.context_data(context);labels=self.labels(row)
                pairs=list(combinations(range(values.shape[1]),2))
                for j,pair in enumerate(pairs):
                    title=f'{"Tres" if row_index==0 else "Cuatro"} · {algorithm} · K/grupos={int(row.groups)}'
                    self.plot_space(axes[row_index,j],values,labels,pair,title)
                    if algorithm=='gmm':
                        model=self.load_model(row.model_id)
                        for cluster in range(model.n_components):
                            covariance=model.covariances_[cluster][np.ix_(pair,pair)];eigen,vectors=np.linalg.eigh(covariance);order=np.argsort(eigen)[::-1];eigen=eigen[order];vectors=vectors[:,order]
                            angle=np.degrees(np.arctan2(vectors[1,0],vectors[0,0]));diameters=2*np.sqrt(chi2.ppf(.95,2)*eigen)
                            axes[row_index,j].add_patch(Ellipse(model.means_[cluster,list(pair)],*diameters,angle=angle,fill=False,lw=1.4,color=plt.get_cmap('tab10')(cluster)))
                for j in range(len(pairs),3):axes[row_index,j].axis('off')
            for ax in axes[2]:ax.axis('off')
            axes[2,1].text(.5,.5,'Cinco intervalos\nSin entrenamiento: no supera el control de cobertura\nCuatro dimensiones sólo descriptivas en sus matrices y diagnósticos.',ha='center',va='center',fontsize=12)
            fig.suptitle('Población común: 4,571 perfiles · etiquetas calculadas en todas las dimensiones\nTres: plano completo 2D; cuatro: los tres pares marginales de un espacio 3D. Elipses GMM: masa marginal 95 %.')
            save_figure(fig,self.charts/file_name)
        for field,file_name,ylabel in [('mean_rate','absolute_curves.png','Tasa absoluta media (%)'),('mean_delta','relative_curves.png','Diferencia nacional media (pp)'),('mean_shape','centered_shapes.png','Forma centrada media (pp)')]:
            fig,axes=plt.subplots(1,len(candidates),figsize=(6*len(candidates),5),layout='constrained',squeeze=False)
            for ax,(_,row) in zip(axes.flat,candidates.iterrows()):
                scheme=self.contexts()[row.context]['scheme'];part=curves[curves.model_id.eq(row.model_id)]
                for cluster,group in part.groupby('cluster'):
                    group=group.set_index('age_band').loc[band_names(scheme)];ax.plot(band_names(scheme),group[field]*100,'o-',label=f'{int(cluster)}')
                ax.set(title=f'{"Tres" if scheme=="three" else "Cuatro"} · {row.algorithm} K={int(row.k)}',ylabel=ylabel,xlabel='Bandas candidatas');ax.grid(alpha=.2);ax.legend(fontsize=8);ax.tick_params(axis='x',rotation=25)
                if field=='mean_rate':ax.set_ylim(0,100)
                else:ax.axhline(0,c='black',lw=.5)
            fig.suptitle('Medias de perfiles con peso uno · bandas diferentes, ejes categóricos propios\nNo se interpola edad exacta; tasas agregadas por conteos disponibles en tablas')
            save_figure(fig,self.charts/file_name)
        stability=pd.read_csv(self.output/'metadata/resampling_metrics.csv');fig,ax=plt.subplots(figsize=(11,5),layout='constrained')
        arrays=[stability[stability.model_id.eq(row.model_id)].ari_oob.dropna() for _,row in candidates.iterrows()]
        tick=[f'{self.contexts()[r.context]["scheme"]}\n{r.algorithm} K={int(r.k)}' for _,r in candidates.iterrows()]
        ax.boxplot(arrays,tick_labels=tick,showfliers=True);ax.set(title='Diez submuestras municipales comunes · ARI OOB, incluidos extremos',ylabel='Concordancia con solución completa',ylim=(0,1.02))
        save_figure(fig,self.charts/'municipality_stability.png')
        fig,axes=plt.subplots(1,len(candidates),figsize=(6*len(candidates),5),layout='constrained',squeeze=False)
        for ax,(_,row) in zip(axes.flat,candidates.iterrows()):
            _,main,_,_=self.context_data(row.context);scheme=self.contexts()[row.context]['scheme'];labels=self.labels(row)
            for cluster in np.unique(labels):
                for sex,style in [('0','-'),('1','--')]:
                    part=main[(labels==cluster)&main.SEXO.eq(sex)];curve=[part[f'shape_{j}'].mean()*100 for j in range(len(SCHEMES[scheme]))]
                    ax.plot(band_names(scheme),curve,marker='o',ls=style,color=plt.get_cmap('tab10')(int(cluster)%10),label=f'{int(cluster)} {"H" if sex=="0" else "M"} n={len(part)}')
            ax.set(title=f'{scheme} · {row.algorithm} K={int(row.k)}',ylabel='Forma media (pp)');ax.legend(fontsize=7);ax.tick_params(axis='x',rotation=25)
        fig.suptitle('Sexo como metadato · no son ajustes separados; referencias nacionales específicas por sexo')
        save_figure(fig,self.charts/'sex_differences.png')
        fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
        for context,name in [('three_common','Tres'),(self.contexts()['four_common']['canonical'],'Cuatro')]:
            part=summary[summary.context.eq(context)&summary.algorithm.eq('kmeans')].sort_values('k');axes[0].plot(part.k,part.silhouette,'o-',label=name)
            part=summary[summary.context.eq(context)&summary.algorithm.eq('gmm')].sort_values('k');axes[1].plot(part.k,part.bic-part.bic.min(),'o-',label=name)
        axes[0].set(title='Silhouette exacto · geometrías 2D y 3D distintas',xlabel='K',ylabel='S (no clasificación universal)');axes[0].legend()
        axes[1].set(title='GMM · ΔBIC respecto al mínimo propio',xlabel='Componentes',ylabel='Sólo preferencia interna por K');axes[1].legend()
        save_figure(fig,self.charts/'model_metrics.png')
        fig,axes=plt.subplots(1,3,figsize=(14,5),layout='constrained')
        axes[0].bar(names,coverage.municipalities/2477,color=colors);axes[0].set(title='Cobertura municipal disponible',ylim=(0,1));axes[0].yaxis.set_major_formatter(PercentFormatter(1))
        fractions=[spectrum[(spectrum.scheme==s)&(spectrum.scope=='common_all_descriptive_equal_profile')&spectrum.direction.eq(1)].fraction.iloc[0] for s in SCHEMES]
        axes[1].bar(names,fractions,color=colors);axes[1].set(title='Dominio de una dirección · mismo universo',ylim=(0,1));axes[1].yaxis.set_major_formatter(PercentFormatter(1))
        means=[]
        for scheme in ['three','four']:
            row=candidates[(candidates.algorithm=='kmeans')&candidates.context.map(lambda c:self.contexts()[c]['scheme']==scheme)].iloc[0]
            means.append(stability[stability.model_id.eq(row.model_id)].ari_oob.median())
        axes[2].bar(names[:2],means,color=colors[:2]);axes[2].set_xticks(range(3),names);axes[2].text(2,.5,'No entrenado',ha='center',rotation=90,color=colors[2]);axes[2].set(title='ARI OOB mediano · K-Means K=2',ylim=(0,1.02))
        fig.suptitle('Métricas distintas: cobertura, riqueza y estabilidad no se sustituyen entre sí')
        save_figure(fig,self.charts/'representation_summary.png')

    def stage_f(self):
        from scipy.stats import spearmanr
        started=time.monotonic();paths=[];summary=pd.read_csv(self.output/'metadata/solution_summary.csv');index=pd.read_csv(self.output/'metadata/model_index.csv')
        for target in [self.charts,self.report,self.output/'assignments']:
            if target.exists():
                require(target.is_relative_to(self.output) or target==self.charts or target==self.report,'No archivar rutas ajenas.')
                archived=self.output/'incomplete'/f'{target.name}_{time.time_ns()}';archived.parent.mkdir(parents=True,exist_ok=True);target.replace(archived)
        self.charts.mkdir(parents=True);validation=[];state_coverage=[];losses=[];diagnostic_parameters={};quality=[]
        membership=pd.read_parquet(self.output/'reference/population_membership.parquet');common_all=membership.common_all_descriptive_only.to_numpy()
        high=common_all.copy();profiles={s:self.profile(s) for s in SCHEMES}
        for profile in profiles.values():high&=profile.min_specified_count.ge(500).to_numpy()
        for scheme,profile in profiles.items():
            q=self.delta(profile[profile.is_eligible],scheme)@helmert_basis(len(SCHEMES[scheme]));parameters=fit_block(q)
            stored=pd.read_parquet(self.output/f'diagnostic_features/{scheme}.parquet').drop(columns='row_id').to_numpy()
            require(np.array_equal(stored,apply_block(q,parameters)),'Matriz diagnóstica diferente.')
            diagnostic_parameters[scheme]=dict(**parameters,basis=helmert_basis(len(SCHEMES[scheme])).tolist(),bands=band_names(scheme))
            for state,part in profile.groupby('EDOCVE'):
                eligible=part[part.is_eligible];state_coverage.append(dict(scheme=scheme,EDOCVE=state,state_name_label=part.state_name_label.iloc[0],
                    eligible_profiles=len(eligible),eligible_municipalities=eligible.groupby(MUNICIPAL_KEYS).ngroups,
                    eligible_LN=int(eligible.LN.sum()),available_core_LN=int(part.LN.sum()),fraction_core_LN=float(eligible.LN.sum()/part.LN.sum())))
            if scheme=='three':continue
            vector=np.zeros(len(SCHEMES[scheme]));vector[1 if scheme=='four' else 3]=1;vector[2 if scheme=='four' else 4]=-1
            for scope,mask in [('common_all_descriptive',common_all),('high_support_descriptive',high),('common_female',common_all&profile.SEXO.eq('1').to_numpy()),('common_male',common_all&profile.SEXO.eq('0').to_numpy())]:
                part=profile.loc[mask];delta=self.delta(part,scheme);contrast=delta@vector
                original=profiles['three'].loc[mask];q0=self.delta(original,'three')@helmert_basis(3);design=np.column_stack([np.ones(len(part)),q0])
                residual=contrast-design@np.linalg.lstsq(design,contrast,rcond=None)[0]
                quality.append(dict(scheme=scheme,scope=scope,contrast='adult_30_44_vs_45_59' if scheme=='four' else 'older_60_74_vs_75_100',profiles=len(part),
                    contrast_mean_pp=float(contrast.mean()*100),contrast_sd_pp=float(contrast.std(ddof=0)*100),linear_residual_sd_pp=float(residual.std(ddof=0)*100),
                    min_specified_median=float(part.min_specified_count.median()),abs_contrast_denominator_spearman=float(spearmanr(np.abs(contrast),part.min_specified_count).statistic),
                    abs_residual_denominator_spearman=float(spearmanr(np.abs(residual),part.min_specified_count).statistic)))
        for previous,current in [('three','four'),('four','five'),('three','five')]:
            lost=profiles[previous].is_eligible.to_numpy()&~profiles[current].is_eligible.to_numpy()
            frame=profiles[current].loc[lost,['row_id',*KEYS,'state_name_label','municipality_name_label','LN','pending_reason','min_specified_count','min_section_count']].copy()
            frame['transition']=previous+'_to_'+current;losses.append(frame)
        for relative,frame in [('metadata/state_coverage.csv',pd.DataFrame(state_coverage)),('metadata/coverage_losses.parquet',pd.concat(losses)),('metadata/contrast_quality.csv',pd.DataFrame(quality))]:paths.append(self.table(relative,frame))
        path=self.output/'metadata/diagnostic_parameters.json';write_json(path,diagnostic_parameters);paths.append(path)
        for _,row in index.iterrows():
            full,main,values,mask=self.context_data(row.context);labels=self.labels(row)
            frame=full[['row_id',*KEYS,'is_eligible','pending_reason']].copy();frame['fit_eligible']=mask
            frame.loc[frame.is_eligible&~frame.fit_eligible,'pending_reason']='outside_common_population'
            column=pd.array([pd.NA]*len(full),dtype='Int64');column[mask]=labels;frame['experimental_label']=column
            require(frame.loc[~mask,'experimental_label'].isna().all(),'Etiquetas de pendientes no nulas.')
            paths.append(self.table(f'assignments/{row.model_id}.parquet',frame));validation.append(dict(model_id=row.model_id,profiles=len(main),source_rows=int(main.source_row_count.sum()),LN=int(main.LN.sum()),differences=0))
        if 'five' not in self.gate()['viable']:
            blocked=profiles['five'][['row_id',*KEYS,'is_eligible','pending_reason']].copy();blocked.loc[blocked.is_eligible,'pending_reason']='coverage_gate_blocked'
            blocked['experimental_label']=pd.array([pd.NA]*len(blocked),dtype='Int64');paths.append(self.table('assignments/five_not_trained.parquet',blocked))
        require(not index.context.str.contains('five').any(),'Se entrenó indebidamente cinco intervalos.')
        paths.append(self.table('metadata/final_validation.csv',pd.DataFrame(validation)))
        # Peores casos con cambios alineados; las bases son los mismos municipios OOB.
        stability=pd.read_csv(self.output/'metadata/resampling_metrics.csv');worst=[];changed_rows=[]
        for _,row in self.candidate_rows().iterrows():
            group=stability[stability.model_id.eq(row.model_id)];score='ari_oob' if group.ari_oob.notna().any() else 'ari_common_all'
            case=group.loc[group[score].idxmin()];replicate=int(case.replicate)
            full,main,values,mask=self.context_data(row.context)
            assignment=pd.read_parquet(self.output/f'resampling/assignments/sample_{replicate:03d}/{row.model_id}.parquet')
            require(assignment.row_id.equals(full.row_id),'Peor caso desalineado.')
            training=assignment.loc[mask,'is_training'].to_numpy();cohort=~training if score=='ari_oob' else training
            projected=assignment.loc[mask].loc[cohort,'projected_label' if score=='ari_oob' else 'training_label'].to_numpy(int)
            baseline=self.labels(row);changed=(baseline[cohort]<0)!=(projected<0) if row.algorithm=='hdbscan' else aligned_changes(baseline[cohort],projected)
            frame=main.loc[cohort,['row_id',*KEYS,'LN','has_high_ns_coordinate','min_specified_count']].copy();frame['model_id']=row.model_id;frame['replicate']=replicate;frame['changed']=changed
            changed_rows.append(frame);worst.append(dict(model_id=row.model_id,replicate=replicate,ari_oob=float(case.ari_oob),comparison_base=score,
                profiles=int(cohort.sum()),changed=int(changed.sum()),changed_fraction=float(changed.mean())))
        paths.append(self.table('metadata/worst_case_summary.csv',pd.DataFrame(worst)));paths.append(self.table('metadata/worst_case_changes.parquet',pd.concat(changed_rows)))
        self.plot_results();paths.extend(self.write_report());self.verify_protected()
        paths.extend([self.report,*self.charts.glob('*.png')]);self.checkpoint('F',paths,started,'Informe, gráficas, etiquetas/pendientes, exclusiones, escalas y conservación validados; cinco sin modelos.')

    def write_report(self):
        paths=[];coverage=pd.read_csv(self.output/'metadata/coverage.csv');support=pd.read_csv(self.output/'metadata/band_support.csv')
        summary=pd.read_csv(self.output/'metadata/solution_summary.csv');candidates=self.candidate_rows();spectrum=pd.read_csv(self.output/'metadata/covariance_spectrum.csv')
        contrasts=pd.read_csv(self.output/'metadata/named_contrasts.csv');quality=pd.read_csv(self.output/'metadata/contrast_quality.csv')
        incremental=pd.read_csv(self.output/'metadata/incremental_variance.csv');cross=pd.read_csv(self.output/'metadata/common_representation_ari.csv')
        stability=pd.read_csv(self.output/'metadata/resampling_metrics.csv');samples=pd.read_csv(self.output/'metadata/resampling_coverage.csv')
        sensitivity=pd.read_csv(self.output/'metadata/quality_sensitivity.csv');boundaries=pd.read_csv(self.output/'metadata/boundary_quality.csv')
        worst=pd.read_csv(self.output/'metadata/worst_case_summary.csv');width=pd.read_csv(self.output/'metadata/bandwidth_diagnostics.csv')
        curves=pd.read_csv(self.output/'metadata/cluster_curves.csv');groups=pd.read_csv(self.output/'metadata/cluster_profiles.csv')
        state_coverage=pd.read_csv(self.output/'metadata/state_coverage.csv');losses=pd.read_parquet(self.output/'metadata/coverage_losses.parquet')
        def table(frame,columns,headers):
            rows=[]
            for _,row in frame.iterrows():
                rows.append(['n/d' if pd.isna(row[c]) else f'{row[c]:.4f}' if isinstance(row[c],(float,np.floating)) else str(row[c]) for c in columns])
            return markdown_table(headers,rows)
        def image(name,title):return f'![{title}]({Path(os.path.relpath(self.charts/name,self.report.parent)).as_posix()})'
        robust=[]
        for model_id,g in stability.groupby('model_id'):
            robust.append(dict(model_id=model_id,samples=len(g),median=g.ari_oob.median(),minimum=g.ari_oob.min(),q10=g.ari_oob.quantile(.1),below_90=int(g.ari_oob.lt(.9).sum())))
        robust=pd.DataFrame(robust);paths.append(self.table('metadata/stability_summary.csv',robust))
        c4=self.contexts()['four_common']['canonical'];common=summary[summary.context.isin(['three_common',c4])]
        km=common[common.algorithm.eq('kmeans')];gmm=common[common.algorithm.eq('gmm')];hdb=common[common.algorithm.eq('hdbscan')]
        spectra_common=spectrum[spectrum.scope.eq('common_all_descriptive_equal_profile')]
        first=spectra_common[spectra_common.direction.eq(1)].set_index('scheme')
        named_common=contrasts[contrasts.scope.eq('common_all_descriptive_equal_profile')]
        kp=candidates[candidates.algorithm.eq('kmeans')].set_index('context');r=robust.set_index('model_id')
        b2=kp.loc[c4];a2=kp.loc['three_common'];g4=candidates[candidates.algorithm.eq('gmm')].iloc[0]
        extra=float(incremental[incremental.context.eq(c4)].linear_residual_fraction.iloc[0])
        final_rows=[]
        for _,row in coverage.iterrows():
            scheme=row.scheme;profile=self.profile(scheme);eigen=first.loc[scheme,'fraction'];model_id=a2.model_id if scheme=='three' else b2.model_id if scheme=='four' else None
            final_rows.append(dict(scheme=scheme,dimensions=int(row.bands)-1,eligible_profiles=int(row.eligible),municipalities=int(row.municipalities),
                nominal_fraction=row.national_LN_fraction,dominant_share_common=eigen,
                k2_oob_median=r.loc[model_id,'median'] if model_id else np.nan,k2_oob_minimum=r.loc[model_id,'minimum'] if model_id else np.nan,
                status='Modelos y estabilidad sobre población común' if row.training_allowed else 'Diagnóstico solamente; control municipal no superado'))
        final=pd.DataFrame(final_rows);paths.append(self.table('metadata/final_comparison.csv',final))
        scale_rows=[]
        for context in self.contexts():
            p=json.loads((self.output/f'features/{context}/parameters.json').read_text(encoding='utf8'))
            scale_rows.append(dict(context=context,n=p['n'],mean=json.dumps(p['mean']),scale=p['scale']))
        diagnostic=json.loads((self.output/'metadata/diagnostic_parameters.json').read_text(encoding='utf8'))
        scale_rows.append(dict(context='five_diagnostic_only',n=diagnostic['five']['n'],mean=json.dumps(diagnostic['five']['mean']),scale=diagnostic['five']['scale']))
        candidate_groups=groups[groups.model_id.isin(candidates.model_id)].copy();candidate_groups['unspecified_rate']=candidate_groups.NS/candidate_groups.LN
        shapes=curves[curves.model_id.isin(candidates.model_id)][['model_id','cluster','age_band','mean_rate','mean_delta','mean_shape','aggregate_rate']].copy()
        shapes[['mean_rate','mean_delta','mean_shape','aggregate_rate']]*=100
        gmm_best=gmm.loc[gmm.groupby('context').bic.idxmin()];aic_best=gmm.loc[gmm.groupby('context').aic.idxmin()]
        losses_by_state=losses.groupby(['transition','EDOCVE','state_name_label'],as_index=False).agg(profiles=('row_id','size'),LN=('LN','sum')).sort_values(['transition','profiles'],ascending=[True,False])
        c5=coverage[coverage.scheme.eq('five')].iloc[0];c3=coverage[coverage.scheme.eq('three')].iloc[0];c4cov=coverage[coverage.scheme.eq('four')].iloc[0]
        older=support[support.age_band.isin(['60-100','60-74','75-100'])]
        high=spectrum[spectrum.scope.eq('high_support_all_descriptive_equal_profile')&spectrum.direction.eq(1)]
        versions=pd.DataFrame([dict(package=k,version=v.get('version','n/d')) for k,v in self.dependencies['imports'].items() if v['available']])
        timings=pd.DataFrame([dict(stage=s,seconds=info['seconds'],**json.loads((self.output/f'metadata/checkpoint_{s}.json').read_text(encoding='utf8'))['memory']) for s,info in self.state['stages'].items()])
        report=f'''# Representaciones electorales de tres, cuatro y cinco intervalos · 2024

## Resultado y recomendación

**Cuatro intervalos añade detalle descriptivo entre edades adultas y mantiene casi todo el LN, pero no demostró nuevos perfiles discretos.** Su K-Means K=2 es más estable en estas diez submuestras que el control de tres; aun así, sus grupos siguen cortando principalmente el gradiente dominante. Se recomienda **conservar tres intervalos como resumen principal de clustering y cuatro como complemento descriptivo y candidato de validación**, sin publicar una nueva tipología por el solo hecho de añadir una dimensión. Cinco queda en diagnóstico: no supera el control de cobertura municipal.

La representación de cuatro reduce la primera fracción espectral de {pct(first.loc['three','fraction'])} a {pct(first.loc['four','fraction'])} sobre los mismos 3,907 perfiles descriptivos. Sin embargo, en la población común viable de 4,571 perfiles, sólo **{pct(extra)}** de su variación no se reconstruye **linealmente** desde R2. Esto no mide toda la información nueva ni valida su origen electoral; indica que el cambio conserva gran parte de la estructura anterior.

{table(final,['scheme','dimensions','eligible_profiles','municipalities','nominal_fraction','dominant_share_common','k2_oob_median','k2_oob_minimum','status'],['Representación','Dimensiones de forma','Perfiles elegibles','Municipios','Fracción LN nacional','Primera dirección (misma base descriptiva)','ARI OOB K2 med.','Mínimo','Estado'])}

No se fuerza cuatro a seis grupos. Los intervalos son divisiones analíticas previas; **no son agrupaciones descubiertas**, edades individuales ni clases de ciudadanos.

## Fuentes, unidad y entorno

Se revisaron participation_pattern_review.md, pattern_algorithm_comparison.md, clustering_methods_review.md y los contratos de cluster_features/contextual_feature_review. Se reutilizan c_broad, c_life_stage y section_segments_broad/life_stage validados, con hashes y _SUCCESS. No se procesaron CSV originales, Parquet de los 54 millones de registros ni otras elecciones. La referencia de edad exacta anterior sigue trazable por ruta/hash en feature_contract.json; el agregado broad completo conserva 101+ y SEXO=2 (105 filas fuente/LN) sin fusionarlos con H/M.

Unidad: **municipio + sexo**, una observación con todas sus tasas por edad. EDOCVE, MPIOCVE y SEXO son texto/metadatos; no se usan edad media, identidad territorial, TIPOSEC ni conteos como coordenadas. Las tasas son ΣSV/Σ(SV+NV), NULL con denominador cero. NS no es abstención. La referencia nacional se calcula por intervalo y sexo con **todos los conteos del núcleo**, antes de seleccionar soporte o población común; no promedia tasas municipales.

Se reutilizó .venv_pattern_algorithms, Python 3.13.0 AMD64. pip check pasó; no se instalaron ni modificaron dependencias ni el entorno principal. Bibliotecas:

{table(versions,['package','version'],['Paquete','Versión'])}

GMM/HDBSCAN son implementaciones reales de scikit-learn. No se ejecutaron nuevos Ward o K-Medoids. La validación independiente de R2/K-Means del informe anterior permanece como antecedente; aquí las alternativas comunes usan las mismas bibliotecas y protocolos.

## Auditoría previa y control preventivo

| Representación | Intervalos | Papel |
| --- | --- | --- |
| three | 18–34, 35–59, 60–100 | Referencia R2, dos grados de libertad. |
| four | 18–29, 30–44, 45–59, 60–100 | Tres grados de libertad; detalle adulto adicional. |
| five | 18–29, 30–44, 45–59, 60–74, 75–100 | Cuatro grados de libertad; diagnóstico de separación entre mayores. |

{table(coverage,['scheme','available','defined','eligible','municipalities','both_sexes','one_sex','none','eligible_LN','national_LN_fraction','municipal_drop_pp','nominal_drop_pp','training_allowed'],['Escenario','Disponibles','Todas definidas','Con soporte','Municipios','Ambos sexos','Un sexo','Sin perfil','LN elegible','Fracción LN nacional','Pérdida municipal pp','Pérdida LN pp','Entrenar'])}

Se mantuvieron LN≥100, SV+NV≥100 y filas fuente≥5 en **cada banda**, sin relajar umbrales. El control usa caída municipal sobre los 2,477 municipios originales y caída nominal sobre LN nacional, respecto a R2 comparable. Basta superar **5 pp municipales o 1 pp nominal** para bloquear modelos; son alertas operativas, no pruebas estadísticas.

Cinco pierde **{c5.municipal_drop_pp:.2f} pp municipales** y {c5.nominal_drop_pp:.3f} pp de LN respecto a tres. Falla sólo la alerta municipal; no se le atribuye falsamente una pérdida nominal >1 pp. Se documentó y comunicó el diagnóstico antes de entrenar. **No se ejecutó ningún K-Means/GMM/HDBSCAN con cinco intervalos**, tampoco sobre una selección reducida para eludir la alerta. Sus matrices, conteos y 3,907 perfiles elegibles quedan conservados sin etiquetas.

Cuatro pierde 77 perfiles y 45 municipios frente a tres, LN=34,226 (0.035 pp nacionales), y supera el control. Cinco pierde 741 perfiles frente a tres y 664 frente a cuatro; no son registros eliminados. reference/ conserva los 4,954 perfiles por alternativa y las razones solapadas de falta de soporte. Los 24 perfiles incompletos tienen alguna tasa desconocida: no son participación cero ni equivalen a sólo 24 celdas NULL entre todas las bandas.

{table(support,['scheme','age_band','median_LN','median_specified','low_LN','low_specified','few_source_rows','fewer_five_sections','undefined'],['Escenario','Banda','Mediana LN','Mediana SV+NV','LN<100','SV+NV<100','Filas fuente<5','Secciones<5','Tasa NULL'])}

El tramo 75–100 tiene mediana SV+NV=308, con 1,043 de 4,954 celdas por debajo de 100; 60–74 tiene mediana 698.5, frente a 1,011.5 al reunir 60–100. Los conteos por banda y motivos pueden superponerse: no sumar sus frecuencias como perfiles únicos. Los detalles de pérdida y entidades están en coverage_losses.parquet/state_coverage.csv. Entidades con más perfiles perdidos (primeras filas de cada transición):

{table(losses_by_state.groupby('transition',sort=False).head(4),['transition','state_name_label','profiles','LN'],['Transición','Entidad','Perfiles perdidos','LN de esos perfiles'])}

{image('coverage_support.png','Cobertura y soporte antes de entrenar')}

## Secciones distintas y NS

Sí había conteos de secciones distintas en los agregados contextuales previos. El inventario de 70,751 secciones verifica una sola TIPOSEC por entidad/municipio/sección. Se suman los conteos de tipos disjuntos dentro de la misma banda/sexo. Para four/60–100 se usa directamente el conteo broad: **no se suman** 60–74 y 75–100, porque podrían contener las mismas secciones. Los conteos electorales sí se suman. No se reinterpretó tipo de sección como residencia individual.

{table(coverage,['scheme','high_ns_profiles','ns_rate','ns_q1','ns_median','ns_q3','eligible_few_sections'],['Escenario','Elegibles con alguna NS≥10 %','NS/LN agregado','Q1 NS/LN','Mediana','Q3','Elegibles con alguna banda <5 secciones'])}

Hay {int(c3.eligible_few_sections)} perfiles de tres y {int(c4cov.eligible_few_sections)} de cuatro que pasan cinco filas fuente pero tienen menos de cinco secciones en alguna banda. No se cambia el criterio: cinco filas son celdas de edades, **no cinco secciones independientes**. Esta limitación persiste aunque el remuestreo mantenga juntos los sexos del municipio.

## Construcción de forma y poblaciones comparables

Para n bandas, dⱼ=tasaⱼ−referencia nacionalⱼ; m=Σdⱼ/n; s=d−m·1. La media simple da el mismo peso a intervalos de diferente anchura; m **no es** participación agregada. Una base Helmert fija Q de n×(n−1) satisface QᵀQ=I y Qᵀ1=0: para columna j=1…n−1, los primeros j elementos son 1/√[j(j+1)], el siguiente −j/√[j(j+1)] y los demás cero. q=dQ, s=qQᵀ. Tres reproduce exactamente la base y la matriz R2 previa.

Por población de ajuste, μ=media(q) y σ=√media(||q−μ||²); X=(q−μ)/σ. Sólo una escala por bloque, sin escalar individualmente bandas, sin normalizar filas por su norma y sin PCA para crear características. Se conserva amplitud. Las tasas, d, m, s, q, conteos, soporte y coordenadas de sección permanecen separadas como referencia.

{table(pd.DataFrame(scale_rows),['context','n','mean','scale'],['Contexto','Perfiles para escala','μ de contrastes crudos','σ RMS'])}

La **cobertura real** usa cada población natural. La **comparación de modelos** usa la intersección viable de tres/cuatro: 4,571 perfiles, 2,296 municipios, LN=98,119,426. Cuatro natural y común son idénticos: comparten modelos mediante canonical en contexts.json, sin repetir ajustes. Tres común requiere nuevos modelos porque su población es distinta de los 4,648 previos; no se trasladan etiquetas como si fueran entrenadas con la misma selección.

La intersección de los tres escenarios (3,907 perfiles) se usa **sólo para diagnósticos descriptivos de covarianza/distribución**, nunca para entrenar cinco. Así se evita confundir selección con riqueza espectral y se cumple el bloqueo. Debe distinguirse del universo común de modelos viable. Además, pasar de tres a cuatro **cambia límites de edad, no sólo añade una coordenada**; sólo four→five es una división anidada de la banda de mayores. La población común no elimina esa diferencia de diseño.

{image('feature_distributions.png','Distribuciones sobre la misma base descriptiva')}

## Riqueza: covarianza, contrastes e información adicional

Se calculó covarianza poblacional (ddof=0) de los contrastes q y su espectro. Los autovectores son **diagnósticos**, no características de entrenamiento ni un PCA que determine la matriz. Los signos de sus cargas son arbitrarios; diagnostic_loadings.csv permite leerlos por edad.

{table(spectra_common,['scheme','direction','variance','fraction'],['Escenario','Dirección descriptiva','Varianza','Fracción del total'])}

Sobre el mismo universo, la primera dirección baja de {pct(first.loc['three','fraction'])} a {pct(first.loc['four','fraction'])} y {pct(first.loc['five','fraction'])}. Hay más de un contraste, pero ninguna tabla demuestra por sí sola regiones discretas. El dominio de una dirección sigue siendo alto, y añadir dimensiones reparte el total sin garantizar perfiles útiles.

{table(named_common,['scheme','contrast','mean_pp','sd_pp','variance_fraction'],['Escenario','Contraste fijo','Media pp','DE pp','Varianza/total'])}

young_older=(primera diferencia−última)/√2; young_adult_middle_adult=(30–44−45–59)/√2; older_split=(60–74−75–100)/√2. Sus extremos cambian entre diseños. **No todos son ortogonales entre sí**, por lo que no se suman sus fracciones como descomposición completa. Las cargas explican qué edades se contraponen y no asignan edad media a los perfiles.

{table(high,['scheme','profiles','fraction'],['Escenario','Perfiles comunes con SV+NV≥500 en todas las bandas','Primera dirección'])}

El patrón espectral adicional persiste al exigir denominadores≥500 (sólo diagnóstico), por lo que no se explica exclusivamente por las celdas más escasas; eso tampoco descarta sesgos de captura. La variante descriptiva ponderada por LN se conserva aparte: cambia la pregunta hacia volumen nominal, no es tamaño efectivo de votantes ni se aplicó automáticamente al entrenamiento.

{table(quality,['scheme','scope','profiles','contrast_mean_pp','contrast_sd_pp','linear_residual_sd_pp','min_specified_median','abs_contrast_denominator_spearman'],['Escenario','Base','Perfiles','Contraste no normalizado medio pp','DE pp','DE residual de R2 pp','Mediana mínimo SV+NV','Spearman abs(contraste)/denominador'])}

Esta tabla usa diferencias **sin √2**, de ahí sus DE distintas de los contrastes unitarios anteriores. Evalúa también sexos y soporte. Una asociación con denominador no demuestra ruido o error, y una diferencia residual no demuestra comportamiento causal de edad. El contraste mayor permite explorar heterogeneidad 60–74/75–100, pero su estabilidad de clustering queda pendiente por cobertura.

Para cuatro se proyectan linealmente sus contrastes sobre [1,R2] en la población común, sólo como diagnóstico. Queda {pct(extra)} de varianza residual. K-Means K=2 explica {pct(b2.linear_residual_explained)} de ese residuo; GMM K={int(g4.k)}, {pct(g4.linear_residual_explained)}. Son fracciones descriptivas in-sample de **separación de medias**, no información causal, validación predictiva ni toda la heterogeneidad de covarianza que puede modelar GMM. Los centroides del agrupamiento todavía usan muy poco de la dimensión no reconstruida desde R2. Aumentar K refina particiones y no prueba nuevas clases.

{image('contrast_variance.png','Espectro descriptivo y control de soporte')}

## Algoritmos, reutilización y resultados comunes

Se recuperaron 47 resultados y sus métricas de tres natural: quince K-Means K=2–6/tres semillas, dieciocho GMM full K=1–6/tres semillas y catorce HDBSCAN. Tres común y cuatro natural/común requieren **94 ajustes nuevos**: treinta K-Means, treinta y seis GMM y veintiocho HDBSCAN. No se repiten contextos idénticos. Los 141 resultados totales están en model_index.csv; 75 configuraciones representativas en solution_summary.csv.

K-Means sklearn: 10 arranques, semillas 17/42/2024, Lloyd, tol=0, máximo 1,000 iteraciones y centroides/SSE contrastados por groupby. El R2 natural anterior conserva su implementación NumPy validada, sin mezclarla con una nueva lotería de inicializaciones; el contraste **común** usa el mismo protocolo sklearn para ambos diseños. GMM: full, cinco arranques/banco, mismas semillas, tol=1e−4, reg_covar=1e−6, máximo 1,000 iteraciones. Se guardan AIC/BIC, convergencia, covarianzas y posteriores. La sensibilidad diag ya existe para R2; no se abrió otra rejilla sin justificación: una covarianza diagonal depende de los ejes elegidos de la base. [KMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html), [GaussianMixture](https://scikit-learn.org/stable/modules/generated/sklearn.mixture.GaussianMixture.html).

HDBSCAN mantiene exactamente la rejilla anterior: tamaño mínimo 50/100/200/400 × min_samples 10/30/60, eom, allow_single_cluster=True, y controles False de 50/10 y 200/30. KD-tree, un hilo, sin imponer K. No se modificaron parámetros para obtener grupos. Ruido es −1 y no equivale a NULL de pendiente; sklearn no ofrece aquí persistencia por cluster. [HDBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html).

Silhouette exacto y DB son de la misma población asignada, por bloques de 8 MiB. HDBSCAN tiene denominador propio; un único grupo/todo ruido da n/d, no cero. No se crean matrices N×N. Las métricas de espacios 2D/3D no son una clasificación universal de representaciones. Las tres semillas comparan ganadores de bancos de arranques, no cada inicio interno individual.

{table(km,['context','k','silhouette','db','smallest_cluster','seed_ari_min','linear_residual_explained','margin_low_fraction'],['Contexto común','K','S exacto','DB','Grupo menor','ARI semillas mín.','R² residuo lineal','Margen≤0.1'])}

{image('kmeans_comparison.png','K-Means en planos completos y proyecciones marginales')}

{table(gmm,['context','k','bic','aic','ambiguous_80','seed_ari_min','groups'],['Contexto','Componentes','BIC propio','AIC propio','Fracción posterior máx.<0.8','ARI bancos mín.','Grupos duros'])}

Los mínimos BIC por contexto son {', '.join(f'{r.context}: K={int(r.k)}' for _,r in gmm_best.iterrows())}; AIC: {', '.join(f'{r.context}: K={int(r.k)}' for _,r in aic_best.iterrows())}. **No se comparan valores absolutos AIC/BIC entre dos y tres dimensiones**, ni con K-Means o HDBSCAN. La diferencia de densidad tiene distinta unidad/volumen. Cuatro bandas favorece cuatro componentes por BIC, pero {pct(g4.ambiguous_80)} de sus posteriores máximos está bajo 0.8. Ese umbral es operativo, no certeza individual o evidencia de cuatro perfiles. Menor ambigüedad que otro modelo dimensional no es automáticamente mayor exactitud.

{image('gmm_components.png','GMM y elipses marginales: superposición, no certeza individual')}

{table(hdb,['context','local_id','groups','assigned','noise_fraction','assigned_municipalities','assigned_LN_fraction','silhouette'],['Contexto','Parámetros','Grupos','Asignados','Fracción ruido','Municipios asignados','Fracción LN elegible','S sólo asignados'])}

El control 50/10 sin grupo único cambia sustancialmente entre R2 natural y común al retirar sólo 77 perfiles: su ruido pasa de 87.56 % a 46.45 %. Esto es **sensibilidad a población**, no mejora por una dimensión nueva; cuatro se compara con tres común para evitar atribuirlo falsamente a la representación. En cuatro, la misma rejilla sigue produciendo principalmente ruido o un núcleo, y el control 50/10 detecta dos grupos con 88.58 % de ruido. Los índices de asignados no valoran todos los municipios.

{image('hdbscan_noise.png','Ruido y cobertura con población común')}

{image('model_metrics.png','Métricas en geometrías distintas y preferencia GMM dentro de cada representación')}

## Curvas electorales, composición e interpretación nueva

{table(candidate_groups,['model_id','cluster','profiles','municipalities','women_fraction','participation','unspecified_rate','median_min_specified','low_section_fraction'],['Modelo','Etiqueta local','Perfiles','Municipios','Fracción mujeres','Participación agregada','NS/LN','Mediana menor SV+NV','Fracción <5 secciones'])}

{table(shapes,['model_id','cluster','age_band','mean_rate','mean_delta','mean_shape','aggregate_rate'],['Modelo','Etiqueta','Banda','Tasa media %','Diferencia media pp','Forma media pp','Tasa por conteos %'])}

Las tasas medias ponderan perfiles por igual; tasa por conteos=ΣSV/Σ(SV+NV). Son preguntas diferentes. Las curvas nuevas desglosan edades adultas, pero las dos clases K-Means siguen mostrando inclinaciones opuestas del patrón relativo. El GMM descompone núcleos/colas y dispersiones, con superposición y poco residuo lineal separado por sus medias. No se da nombre de perfil ciudadano definitivo a cada etiqueta ni se infiere que personas concretas cambien de conducta al envejecer.

{image('absolute_curves.png','Curvas absolutas por cluster')}

{image('relative_curves.png','Diferencias relativas originales por cluster')}

{image('centered_shapes.png','Formas centradas, sin nivel común en la distancia')}

ARI entre representaciones se calcula sólo sobre los 4,571 row_id comunes y con el mismo algoritmo/configuración; no sobre universos distintos. ARI=1 con un grupo es trivial. Para HDBSCAN se separan ruido, asignados comunes y cobertura.

{table(cross[cross.algorithm.eq('kmeans')],['configuration','profiles','ari_common_all'],['K común','Perfiles idénticos','ARI tres/cuatro'])}

## Estabilidad, NS, sexo y ponderación

Se escogieron tres candidatas después de comparar resultados completos: K-Means K=2 de tres y cuatro, más GMM K=4 full de cuatro por BIC. Son pruebas de parsimonia y detalle, no selección final. Se ejecutaron 30 ajustes en diez submuestras municipales compartidas, sin reemplazo: 1,981 de los 2,477 municipios originales, conservando juntos los perfiles de ambos sexos que son elegibles. Cada muestra tiene {int(samples.training_profiles.min()):,}–{int(samples.training_profiles.max()):,} perfiles de entrenamiento; {int(samples.oob_profiles.min()):,}–{int(samples.oob_profiles.max()):,} OOB.

Se reajustan centro y RMS escalar sólo con perfiles in-bag, por representación, y se proyecta OOB con K-Means/GMM. La referencia nacional permanece fija e incluye OOB: es estabilidad descriptiva bajo ese contexto, no predicción independiente de todo el proceso electoral. No se reutilizaron remuestras R2 con 4,648 perfiles como si pertenecieran al nuevo universo de 4,571. HDBSCAN, si fuese candidata, sólo admitiría comparación sobre observaciones comunes, sin OOB inventado; no se seleccionó por baja cobertura y sensibilidad.

{table(robust,['model_id','samples','median','q10','minimum','below_90'],['Configuración','Muestras','ARI OOB mediano','q10','Mínimo','Muestras <0.90'])}

{table(worst,['model_id','replicate','ari_oob','profiles','changed','changed_fraction'],['Configuración','Peor muestra','ARI OOB','Perfiles OOB','Cambian tras alinear','Fracción'])}

Cuatro K=2 alcanza {r.loc[b2.model_id,'median']:.3f}/{r.loc[b2.model_id,'minimum']:.3f} de ARI mediano/mínimo frente a {r.loc[a2.model_id,'median']:.3f}/{r.loc[a2.model_id,'minimum']:.3f} de tres. Es una mejora observada de concordancia en estos ensayos, **no prueba de nuevos tipos electorales**. GMM K=4 cae hasta {r.loc[g4.model_id,'minimum']:.3f}; las medianas no ocultan esa cola. Se guardan claves y cambios de peores casos, y curvas/tamaños de todas las muestras. Diez submuestras no permiten declarar estabilidad general.

{image('municipality_stability.png','Estabilidad municipal en población común')}

Para NS se entrenó un subconjunto **común** sin ninguna banda NS≥10 % en tres/cuatro: 3,556 perfiles de 1,804 municipios, LN=80,994,777. Se conservan el principal completo y las proyecciones de NS alto separadas del entrenamiento. Al comparar esta sensibilidad se mantienen las escalas principales para aislar el cambio de población; no se convierte NS en abstención ni se estima un efecto causal de NS.

{table(sensitivity,['model_id','scenario','training_profiles','training_LN','ari_common_all','ari_all_eligible'],['Modelo','Sensibilidad','Entrenamiento','LN','ARI comunes','ARI proyecciones en todos'])}

La ponderación municipal usa 1/n_perfiles_elegibles y se aplica sólo a K-Means, desde los mismos centros principales con un arranque: control local del objetivo, no una exploración completa de mínimos. Aquí no cambia etiquetas. GMM/HDBSCAN no admiten pesos de observación en las APIs usadas; no se replican filas para simular compatibilidad ni se aplica LN como peso automático.

{table(boundaries,['model_id','scope','profiles','criterion','uncertain_fraction'],['Modelo','Subconjunto descriptivo','Perfiles','Criterio de proximidad','Fracción señalada'])}

Margen≤0.1 compara las dos distancias más cercanas a centros K-Means; posterior máximo<0.8 mide ambigüedad condicional GMM. No son probabilidades de error ni medidas intercambiables. Sexo se conserva para composición y curvas específicas, con referencias nacionales diferentes por sexo; no se codifica como magnitud ni se interpreta una diferencia como causalidad. No se entrenaron modelos separados por sexo en esta entrega.

{image('sex_differences.png','Formas por sexo dentro de las etiquetas conjuntas')}

## Sensibilidad al peso de intervalos y límites de interpretación

La media simple principal pondera bandas igualmente, aunque cubren 17/25/41 edades en tres, 12/15/15/41 en cuatro y 12/15/15/15/26 en cinco. Como diagnóstico **predefinido antes de entrenar**, se calculó m_w=Σwⱼdⱼ con w=anchura/83 y vⱼ=√wⱼ(dⱼ−m_w). No se aplicó esa geometría a los modelos ni se asignó un valor de edad individual. Se contrastaron 20,000 pares reproducibles de distancias, sin matriz N×N.

{table(width,['scheme','scope','median_mean_change_pp','dominant_width_fraction','distance_spearman'],['Escenario','Universo','Mediana abs(m_w−m) pp','Primera dirección ponderada','Spearman de distancias'])}

La alta correlación de distancias no garantiza identidad de etiquetas ni estabilidad al cambiar pesos de bandas. El diagnóstico muestra que la pregunta sobre ponderación sigue siendo relevante; no se presenta como una sensibilidad de clustering ya ejecutada. Los cambios tres→cuatro combinan nuevas fronteras, dimensiones y pesos implícitos: no atribuir todo al número de bandas. Los datos siguen agregados, con disponibilidad desigual, NS y dependencia territorial.

## Respuestas finales

1. **Cobertura:** tres: 4,648 perfiles/2,341 municipios/99.82 % LN; cuatro: 4,571/2,296/99.79 %; cinco: 3,907/2,010/98.92 %. Cinco bloquea entrenamiento por pérdida municipal de 13.36 pp; no se relajan umbrales.
2. **Información adicional:** cuatro permite observar 30–44 frente a 45–59; cinco distingue 60–74 de 75–100. Los contrastes existen descriptivamente y persisten con mayor soporte, pero no se traducen automáticamente en nuevos clusters.
3. **Dominio jóvenes–mayores:** disminuye la primera dirección del espectro (86.45→79.27→72.27 % en la misma base descriptiva), pero sigue concentrando la mayor parte. El contraste de extremos no es idéntico entre diseños y sus fracciones no deben interpretarse como una prueba causal.
4. **Interpretación electoral distinta:** hay más resolución de curvas, no una tipología cualitativamente nueva demostrada. R2 reconstruye linealmente 93.85 % de la forma de cuatro; sus principales etiquetas separan poco de la variación restante.
5. **Algoritmo por representación:** K-Means K=2 es un resumen transparente y estable del gradiente en tres/cuatro, sin demostrar clases naturales; GMM full es útil para densidad e incertidumbre (BIC de cuatro favorece cuatro componentes), pero sigue superpuesto. HDBSCAN no ofrece cobertura y robustez suficientes bajo la rejilla. Cinco no tiene comparación de algoritmos por el control preventivo. No hay ganador universal.
6. **Separación o dimensiones:** añadir una dimensión no produjo una mejora global de separación demostrada. Silhouette cambia de geometría; GMM continúa ambiguo; el residuo de medias añade poco a las etiquetas principales. No se fuerza una lectura positiva.
7. **Estabilidad municipal:** cuatro K=2 fue más concordante que tres en las diez muestras comunes; GMM conserva casos débiles. Hay estabilidad exploratoria de algunos cortes, no validación general o individual.
8. **Perfiles o gradiente:** la evidencia sigue siendo más consistente con un gradiente y heterogeneidad de curvas/densidades superpuestas. No valida cuatro a seis perfiles ciudadanos discretos.
9. **Cinco justifica perder cobertura:** no se demostró. El detalle de mayores es informativo, pero el control impidió evaluar modelos y estabilidad. Conservarlo descriptivamente; no promoverlo ni afirmar que sus modelos fallaron, porque no se ejecutaron.
10. **Para ParticipaMX:** mantener tres como resumen principal ya auditado; ofrecer cuatro como alternativa descriptiva y candidata de revisión electoral por su detalle adulto y buena estabilidad sin pérdida nominal importante. Antes de sustituir el resumen deben demostrar utilidad adicional de esos contrastes, revisar secciones/NS y sensibilidad de bandas/pesos. No adoptar cinco ni publicar perfiles definitivos con estos resultados. No se exporta nada a React.

{image('representation_summary.png','Comparación final: cobertura, riqueza descriptiva y estabilidad son criterios separados')}

## Reproducción, integridad y pendientes

Se completaron A–F: auditoría/control antes de entrenar; construcción y diagnósticos; modelos recuperables; métricas; tres candidatas con estabilidad y sensibilidades; gráficas/informe/validación. Cinco queda **metodológicamente pendiente por cobertura**, no por un error técnico oculto. Se mantienen centro/RMS y universos naturales/comunes, copias nuevas de datos originales de referencia, contratos, modelos nativos, posteriores GMM, etiquetas con pendientes NULL, metadatos de sección, NS y curvas.

Los checkpoints y modelos individuales tienen hashes verificables; se guardan incrementalmente mediante temporales y reemplazo atómico. Un lock exclusivo evita duplicados. Un fallo conserva etapas previas y traceback en state.json; no obliga a repetir ajustes completos. Los archivos parciales propios se archivan antes de reconstruir el informe. _SUCCESS sólo se escribe tras todas las validaciones. Se limitó BLAS/OMP a un hilo, sin distancias N×N. Memoria Windows y tiempos están en cada checkpoint; el pico es del proceso y no se suma entre etapas.

{table(timings,['stage','seconds','working_set_MiB','peak_working_set_MiB'],['Etapa A–E','Segundos','Working set MiB','Pico del proceso MiB'])}

La etapa F registra su duración al terminar. Se validaron referencias por sumas, perfiles únicos/claves textuales, LN=SV+NV+NS, conservación de conteos por municipio/sexo y por cluster incluido ruido, escalas/bases, R2 natural **exactamente idéntico** al previo, ausencia de modelos five, población común y alias de cuatro, pendientes NULL, lectura posterior de Parquet y centroides/SSE K-Means mediante cálculo independiente. Se verifican hashes de {len(self.state['protected_hashes']):,} archivos previos; no se modifican experimentos, matrices, datos originales, informes anteriores, entorno principal ni frontend. No se crean commits.

```powershell
.venv_pattern_algorithms/Scripts/python.exe analysis/scripts/evaluate_age_band_representations.py --until B
.venv_pattern_algorithms/Scripts/python.exe analysis/scripts/evaluate_age_band_representations.py --until D
.venv_pattern_algorithms/Scripts/python.exe analysis/scripts/evaluate_age_band_representations.py --candidates {' '.join(self.state['candidates'])}
.venv_pattern_algorithms/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_evaluate_age_band_representations.py
```

Reanudar verifica y omite checkpoints válidos; _SUCCESS íntegro termina sin ajustar modelos. Para una reproducción nueva, usar --output, --charts y --report distintos. El entorno independiente y sus versiones quedan registrados, sin instalaciones adicionales. Los escenarios son vistas alternativas, no observaciones que deban sumarse. reference/ conserva tasas/conteos/soporte y pendientes completos; features/ matrices y parámetros de modelos; diagnostic_features/ incluye cinco sin autorización de entrenamiento; diagnostics/ y metadata/ guardan espectros, cargas, calidad, cobertura, comparaciones y peores casos; models/, assignments/ y resampling/ conservan parámetros y trazabilidad experimental.
'''
        atomic_bytes(self.report,report.encode('utf8'));return paths

    def run(self,until,selection):
        manifest_path=self.output/'metadata/run_manifest.json'
        if (self.output/'_SUCCESS').exists():
            marker=json.loads((self.output/'_SUCCESS').read_text());manifest=json.loads(manifest_path.read_text(encoding='utf8'))
            require(marker['manifest_sha256']==file_hash(manifest_path) and manifest['status']=='validated','Marcador final incorrecto.')
            for relative,digest in manifest['artifact_hashes'].items():require(file_hash(self.root/relative)==digest,'Salida final alterada.')
            print('Validado y verificado: cero ajustes nuevos.',flush=True);return
        stage='A'
        try:
            for stage in 'ABCDEF':
                if self.valid_stage(stage):print(f'{stage}: checkpoint verificado; se omite.',flush=True)
                elif stage=='E':self.stage_e(selection)
                else:getattr(self,'stage_'+stage.lower())()
                if stage==until and stage!='F':return
            self.verify_protected();self.state.update(status='validated',finished=utc());write_json(self.state_path,self.state)
            artifacts={str(path.relative_to(self.root)):file_hash(path) for base in [self.output,self.charts] for path in base.rglob('*')
                if path.is_file() and path not in [manifest_path,self.output/'_SUCCESS',self.output/'_RUNNING.json']}
            artifacts[str(self.report.relative_to(self.root))]=file_hash(self.report)
            write_json(manifest_path,dict(status='validated',stages=self.state['stages'],dependencies=self.dependencies,protected_hashes=self.state['protected_hashes'],
                artifact_hashes=artifacts,script_sha256=file_hash(Path(__file__)),test_sha256=file_hash(self.root/'analysis/scripts/test_evaluate_age_band_representations.py')))
            write_json(self.output/'_SUCCESS',dict(manifest_sha256=file_hash(manifest_path)));print(f'VALIDADO: {self.report}',flush=True)
        except Exception as error:
            self.state['status']='failed';self.state['errors'].append(dict(stage=stage,at=utc(),error=repr(error),traceback=traceback.format_exc()))
            write_json(self.state_path,self.state);raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output',type=Path,default=Path('data/processed/age_band_representation_review'))
    parser.add_argument('--charts',type=Path,default=Path('analysis/charts/age_band_representation_review'))
    parser.add_argument('--report',type=Path,default=Path('analysis/reports/age_band_representation_review.md'))
    parser.add_argument('--until',choices=list('ABCDEF'),default='F');parser.add_argument('--replicates',type=int,default=10)
    parser.add_argument('--candidates',nargs='*',default=[])
    args=parser.parse_args();root=args.root.resolve();output=(root/args.output).resolve();require(2<=args.replicates<=10,'Máximo diez muestras.')
    with experiment_lock(output):Experiment(root,output,root/args.charts,root/args.report,args.replicates).run(args.until,args.candidates)


if __name__=='__main__':main()

