"""Experimento recuperable P/A/S/M/T sobre segmentos B broad de 2024.

Se comparan geometrías sobre la misma población, sin imputar ni usar claves
territoriales, edad media o códigos de sexo como coordenadas. Etapas A–G.
"""
from __future__ import annotations
import os
for variable in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
    os.environ[variable]='1'
import sys
sys.dont_write_bytecode=True
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import traceback
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.metrics import adjusted_rand_score, davies_bouldin_score

from clean_data import require, file_hash
from build_descriptive import METRICS, compare_sums
from build_cluster_features import snapshot_inputs
from build_profile_candidates import table_text
from compare_pattern_algorithms import Comparison, probe_dependencies, posterior_summary
from evaluate_participation_patterns import (atomic_bytes,write_json,write_table,save_figure,
    experiment_lock,memory_estimate,utc,safe_ratio,Q)
from evaluate_exact_age_clustering import anchor_silhouettes
from compare_demographic_features import weighted_group_sse,explained_fraction
from run_contextual_clustering_pilot import conditional_rate_r2,codes

os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[2]/'.venv_pattern_algorithms/matplotlib_cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

BANDS=['18-34','35-59','60-100']
SUFFIXES=['18_34','35_59','60_100']
MUNICIPAL_KEYS=['EDOCVE','MPIOCVE']
PROFILE_KEYS=[*MUNICIPAL_KEYS,'SEXO']
SEGMENT_KEYS=[*PROFILE_KEYS,'age_band']
BLOCKS={'P':['relative_turnout'],'A':['age_shape_1','age_shape_2'],
        'S':['sex_gap_adjusted'],'M':['municipal_adjusted_turnout'],
        'T':['section_contrast_1','section_contrast_2']}
REPRESENTATIONS={'F0':['P'],'F1':['P','A'],'F2':['P','S'],'F3':['P','A','S']}
SEEDS=[17,42,2024]
OWN_FILES=['evaluate_multidimensional_profiles.py','test_evaluate_multidimensional_profiles.py']
NATIONAL_LN=98330348
CONFIG=dict(version='1.0',seeds=SEEDS,kmeans_ks=[2,3,4,5,6],gmm_ks=[1,2,3,4,5,6],
    kmeans_starts=10,gmm_starts=5,max_iter=1000,gmm_reg_covar=1e-5,gmm_tol=1e-4,
    municipal_alert_pp=5,nominal_alert_pp=1,minimum_residual_fraction=.05,
    maximum_matrix_condition=1e6,minimum_cluster_fraction=.02,seed_stability_gate=.90,
    retained_conditional_turnout=.80,selection_excludes_k6=True,
    sensitivity='peso P doble respecto de cada otro bloque; NS<10%; secciones>=5; peso municipio sólo K-Means')


def join_metadata(left,right,keys):
    """Las propiedades agregadas se unen sin expandir segmentos."""
    result=left.merge(right,on=keys,how='left',sort=False,validate='many_to_one')
    require(len(result)==len(left) and result.row_id.equals(left.row_id),'Unión expandió o reordenó segmentos.')
    for metric in METRICS:require(result[metric].sum()==left[metric].sum(),'Unión modificó '+metric)
    return result


def build_features(full,profiles,municipalities):
    """Construye bloques y sus estados; conserva todos los conteos originales."""
    full=full.copy().reset_index(drop=True)
    require(full.row_id.is_unique and not full.duplicated(SEGMENT_KEYS).any(),'Claves duplicadas.')
    require(full.LN.eq(full.SV+full.NV+full.NS).all(),'Conteos fuente incompatibles.')
    full['participation_rate']=safe_ratio(full.SV,full.SV+full.NV)
    core=full.age_band.isin(BANDS)&full.SEXO.isin(['0','1'])
    national=full[core].groupby(['age_band','SEXO'],as_index=False,observed=True)[METRICS].sum()
    national['national_peer_rate']=national.SV/(national.SV+national.NV)
    full=join_metadata(full,national[['age_band','SEXO','national_peer_rate']],['age_band','SEXO'])
    full['relative_turnout']=full.participation_rate-full.national_peer_rate
    full['base_eligible']=core & full.LN.ge(100)&(full.SV+full.NV).ge(100)&full.source_row_count.ge(5)&full.participation_rate.notna()
    full['P_available']=full.base_eligible
    raw_delta=profiles[['delta_'+s for s in SUFFIXES]].to_numpy(float)
    shape=raw_delta@Q
    pattern=profiles[PROFILE_KEYS+['is_eligible']].rename(columns={'is_eligible':'A_available'}).copy()
    for j in range(2):pattern[f'age_shape_{j+1}']=np.where(pattern.A_available,shape[:,j],np.nan)
    for suffix in SUFFIXES:
        pattern['pattern_delta_'+suffix]=profiles['delta_'+suffix]
        pattern['pattern_shape_'+suffix]=profiles['shape_'+suffix]
    pattern['pattern_max_ns']=profiles[['unspecified_rate_'+s for s in SUFFIXES]].max(axis=1)
    full=join_metadata(full,pattern,PROFILE_KEYS)
    full['A_available']=full.A_available.eq(True)&full.base_eligible
    pairs=[]
    scoped=full[core]
    for sex,prefix in [('0','male'),('1','female')]:
        part=scoped[scoped.SEXO.eq(sex)][MUNICIPAL_KEYS+['age_band','participation_rate','relative_turnout','base_eligible','unspecified_rate']].copy()
        part=part.rename(columns={c:prefix+'_'+c for c in ['participation_rate','relative_turnout','base_eligible','unspecified_rate']})
        pairs.append(part)
    gap=pairs[0].merge(pairs[1],on=MUNICIPAL_KEYS+['age_band'],how='outer',validate='one_to_one')
    gap['S_available']=gap.male_base_eligible.eq(True)&gap.female_base_eligible.eq(True)
    gap['sex_gap_observed']=(gap.female_participation_rate-gap.male_participation_rate).where(gap.S_available)
    gap['sex_gap_adjusted']=(gap.female_relative_turnout-gap.male_relative_turnout).where(gap.S_available)
    gap['gap_max_ns']=gap[['male_unspecified_rate','female_unspecified_rate']].max(axis=1)
    full=join_metadata(full,gap[MUNICIPAL_KEYS+['age_band','S_available','sex_gap_observed','sex_gap_adjusted','gap_max_ns']],MUNICIPAL_KEYS+['age_band'])
    full['S_available']=full.S_available.eq(True)&full.base_eligible
    # M utiliza todos los conteos H/M 18–100 del municipio, antes del soporte.
    scoped=full[core].copy();scoped['expected_peer_votes']=scoped.specified_count*scoped.national_peer_rate
    municipal=scoped.groupby(MUNICIPAL_KEYS,as_index=False,observed=True)[COUNTS_AND_EXPECTED()].sum()
    municipal['municipal_turnout_core']=safe_ratio(municipal.SV,municipal.SV+municipal.NV)
    municipal['municipal_peer_reference']=safe_ratio(municipal.expected_peer_votes,municipal.SV+municipal.NV)
    municipal['municipal_adjusted_turnout']=municipal.municipal_turnout_core-municipal.municipal_peer_reference
    municipal['municipal_core_ns']=safe_ratio(municipal.NS,municipal.LN)
    raw=municipalities[municipalities.election_year.eq(2024)][MUNICIPAL_KEYS+['participation_observed']].rename(columns={'participation_observed':'municipal_turnout_all'})
    municipal=municipal.merge(raw,on=MUNICIPAL_KEYS,validate='one_to_one')
    full=join_metadata(full,municipal[MUNICIPAL_KEYS+['municipal_turnout_core','municipal_peer_reference','municipal_adjusted_turnout','municipal_core_ns','municipal_turnout_all']],MUNICIPAL_KEYS)
    full['M_available']=full.base_eligible&np.isfinite(full.municipal_adjusted_turnout)
    shares=full[['section_ln_share_U','section_ln_share_R','section_ln_share_M']].to_numpy(float)
    require(np.isfinite(shares).all() and (shares>=0).all() and np.allclose(shares.sum(axis=1),1,atol=1e-12),'Composición incompleta.')
    coordinates=shares@Q
    full[['section_contrast_1','section_contrast_2']]=coordinates
    full['T_available']=full.base_eligible
    full['common_eligible']=full.base_eligible&full.A_available&full.S_available&full.M_available&full.T_available
    full['common_pending_reason']=np.select([~core,full.participation_rate.isna(),~full.base_eligible,~full.A_available,~full.S_available],
        ['complementary','undefined_rate','insufficient_segment_support','pattern_without_all_supported_ages','gap_without_both_supported_sexes'],default='eligible')
    require(full.loc[full.common_eligible,'common_pending_reason'].eq('eligible').all(),'Estado común incorrecto.')
    return full,national,gap,municipal


def COUNTS_AND_EXPECTED():return ['LN','SV','NV','NS','expected_peer_votes']


def fit_scalers(frame,blocks):
    result={}
    for block in blocks:
        values=frame[BLOCKS[block]].to_numpy(float)
        require(np.isfinite(values).all(),'Bloque con NULL: '+block)
        mean=values.mean(axis=0);scale=float(np.sqrt(np.mean(np.sum((values-mean)**2,axis=1))))
        require(scale>1e-12,'Bloque constante: '+block)
        result[block]=dict(columns=BLOCKS[block],mean=mean.tolist(),rms_scale=scale,n=len(frame),ddof=0,
                           fitted_row_ids_sha256=hashlib.sha256('\n'.join(frame.row_id).encode()).hexdigest())
    return result


def transform(frame,blocks,parameters,p_heavy=False):
    raw_weights={block:(2. if p_heavy and block=='P' else 1.) for block in blocks}
    weights={block:weight/sum(raw_weights.values()) for block,weight in raw_weights.items()}
    arrays=[];slices={};offset=0
    for block in blocks:
        p=parameters[block];raw=frame[p['columns']].to_numpy(float)
        array=(raw-np.asarray(p['mean']))/p['rms_scale']*np.sqrt(weights[block])
        arrays.append(array);slices[block]=(offset,offset+array.shape[1]);offset+=array.shape[1]
    values=np.ascontiguousarray(np.column_stack(arrays))
    require(np.isfinite(values).all(),'Matriz con valores no finitos.')
    return values,slices,weights


def residual_fraction(target,predictors):
    """Diagnóstico OLS in-sample, no validación predictiva ni prueba de novedad."""
    target=np.asarray(target,float)
    if target.ndim==1:target=target[:,None]
    design=np.column_stack([np.ones(len(target)),np.asarray(predictors,float)])
    prediction=design@np.linalg.lstsq(design,target,rcond=None)[0]
    denominator=float(np.sum((target-target.mean(axis=0))**2))
    return float(np.sum((target-prediction)**2)/denominator) if denominator>1e-20 else 0.


def feature_audit(main):
    columns=[c for block in BLOCKS.values() for c in block]
    raw=main[columns];standard=(raw-raw.mean())/raw.std(ddof=0)
    correlations=[]
    for method in ['pearson','spearman']:
        matrix=raw.corr(method=method)
        for a,b in combinations(columns,2):correlations.append(dict(method=method,feature_1=a,feature_2=b,value=float(matrix.loc[a,b]),n=len(main)))
    rows=[]
    for block,features in BLOCKS.items():
        other=[c for b,cs in BLOCKS.items() if b!=block for c in cs]
        values=raw[features].to_numpy(float)
        for j,feature in enumerate(features):
            rows.append(dict(block=block,feature=feature,n=len(raw),mean=float(values[:,j].mean()),sd=float(values[:,j].std()),
                minimum=float(values[:,j].min()),q1=float(np.quantile(values[:,j],.25)),median=float(np.median(values[:,j])),
                q3=float(np.quantile(values[:,j],.75)),maximum=float(values[:,j].max()),
                residual_fraction_other_blocks=residual_fraction(values[:,j],standard[other].to_numpy())))
    rank=[]
    for name,blocks in {**REPRESENTATIONS,'all_diagnostic':list(BLOCKS)}.items():
        cols=[c for b in blocks for c in BLOCKS[b]]
        x=standard[cols].to_numpy();singular=np.linalg.svd(x,compute_uv=False)
        rank.append(dict(representation=name,features=len(cols),rank=int(np.linalg.matrix_rank(x)),condition=float(singular[0]/singular[-1]),
                         min_singular=float(singular[-1]),max_singular=float(singular[0])))
    return pd.DataFrame(correlations),pd.DataFrame(rows),pd.DataFrame(rank)


def model_id(representation,algorithm,k,seed):return f'{representation.lower()}/{algorithm}/k{k}/seed{seed}'


def block_separation(values,labels,slices):
    """Descompone varianza entre grupos, sin atribuir causalidad al bloque."""
    ones=np.ones(len(labels));between={};within={}
    for block,(start,stop) in slices.items():
        total=float(np.sum((values[:,start:stop]-values[:,start:stop].mean(axis=0))**2))
        intra=sum(weighted_group_sse(values[:,j],labels,ones) for j in range(start,stop))
        between[block]=max(0.,total-intra);within[block]=float(1-intra/total) if total>1e-20 else np.nan
    denominator=sum(between.values())
    return {b:float(v/denominator) if denominator else np.nan for b,v in between.items()},within


def conditional_fraction(values,labels,groups):
    values=np.asarray(values,float)
    if values.ndim==1:values=values[:,None]
    ones=np.ones(len(labels));k=int(np.max(labels))+1
    base=sum(weighted_group_sse(values[:,j],groups,ones) for j in range(values.shape[1]))
    after=sum(weighted_group_sse(values[:,j],groups*k+labels,ones) for j in range(values.shape[1]))
    return float(1-after/base) if base>1e-16 else np.nan


def partition_diagnostics(main,values,labels,slices):
    labels=np.asarray(labels,int);ones=np.ones(len(main));rules=pd.factorize(main.candidate_id,sort=True)[0]
    age=pd.crosstab(labels,main.age_band);sex=pd.crosstab(labels,main.SEXO)
    municipality=pd.crosstab(codes(main,MUNICIPAL_KEYS),labels)
    shares,explained=block_separation(values,labels,slices)
    result=dict(age_band_purity=float(age.max(axis=1).sum()/len(main)),sex_purity=float(sex.max(axis=1).sum()/len(main)),
        age_band_ari=float(adjusted_rand_score(labels,codes(main,['age_band']))),rules_ari=float(adjusted_rand_score(labels,rules)),
        municipality_label_purity=float(municipality.max(axis=1).sum()/len(main)),
        single_label_municipality_fraction=float(municipality.gt(0).sum(axis=1).eq(1).mean()),
        relative_r2=explained_fraction(main.relative_turnout.to_numpy(),labels,ones),
        absolute_r2=explained_fraction(main.participation_rate.to_numpy(),labels,ones),
        shape_r2=float(np.mean([explained_fraction(main[c].to_numpy(),labels,ones) for c in BLOCKS['A']])),
        sex_gap_r2=explained_fraction(main.sex_gap_adjusted.to_numpy(),labels,ones),
        municipal_level_r2=explained_fraction(main.municipal_adjusted_turnout.to_numpy(),labels,ones),
        context_r2=float(np.mean([explained_fraction(main[c].to_numpy(),labels,ones) for c in BLOCKS['T']])),
        age_mean_r2=explained_fraction(main.mean_age_nominal.to_numpy(),labels,ones),
        delta_within_rules_r2=conditional_fraction(main.relative_turnout,labels,rules),
        shape_within_rules_r2=conditional_fraction(main[BLOCKS['A']],labels,rules),
        gap_within_rules_r2=conditional_fraction(main.sex_gap_adjusted,labels,rules))
    # Se usa la columna original de tasas; no se promedian tasas para conteos.
    result['within_age_sex_rate_r2']=conditional_rate_r2(main,labels,['age_band','SEXO'])[0]
    for block in BLOCKS:
        result['separation_'+block]=shares.get(block,np.nan);result['explained_'+block]=explained.get(block,np.nan)
    return result


def describe(main,labels,identifier):
    """Resúmenes de segmentos; curvas únicas por municipio/sexo por separado."""
    rows=[];curves=[];ages=[];sexes=[];states=[];municipal=[];contingencies=[]
    for label in np.unique(labels):
        g=main.loc[np.asarray(labels)==label];den=int(g.specified_count.sum());expected=float(np.sum(g.specified_count*g.national_peer_rate)/den)
        row=dict(model_id=identifier,cluster=int(label),segments=len(g),municipalities=len(g[MUNICIPAL_KEYS].drop_duplicates()),
            states=g.EDOCVE.nunique(),**{c:int(g[c].sum()) for c in METRICS},specified_count=den,
            participation_observed=float(g.SV.sum()/den),matched_peer_reference=expected,
            aggregate_relative_turnout=float(g.SV.sum()/den-expected),mean_relative_turnout=float(g.relative_turnout.mean()),
            median_relative_turnout=float(g.relative_turnout.median()),relative_q1=float(g.relative_turnout.quantile(.25)),
            relative_q3=float(g.relative_turnout.quantile(.75)),mean_sex_gap_adjusted=float(g.sex_gap_adjusted.mean()),
            women_fraction=float(g.SEXO.eq('1').mean()),high_ns_fraction=float(g.unspecified_rate.ge(.1).mean()),
            unspecified_rate=float(g.NS.sum()/g.LN.sum()),few_sections_fraction=float(g.section_count.lt(5).mean()),
            near_rule_boundary_fraction=float(g.relative_turnout.abs().le(.02).mean()),
            shape_1=float(g.age_shape_1.mean()),shape_2=float(g.age_shape_2.mean()),
            municipal_adjusted_turnout=float(g.municipal_adjusted_turnout.mean()),
            top_state_segment_fraction=float(g.EDOCVE.value_counts(normalize=True).max()))
        for kind in ['U','R','M']:row['nominal_share_'+kind]=float(g['LN_'+kind].sum()/g.LN.sum())
        rows.append(row)
        unique=g.drop_duplicates(PROFILE_KEYS)
        for band,suffix in zip(BANDS,SUFFIXES):
            curves.append(dict(model_id=identifier,cluster=int(label),age_band=band,unique_municipality_sex=len(unique),
                mean_delta_unique=float(unique['pattern_delta_'+suffix].mean()),mean_shape_unique=float(unique['pattern_shape_'+suffix].mean()),
                mean_delta_segment_weight=float(g['pattern_delta_'+suffix].mean()),mean_shape_segment_weight=float(g['pattern_shape_'+suffix].mean())))
        for key,destination in [('age_band',ages),('SEXO',sexes),('EDOCVE',states),('candidate_id',contingencies)]:
            for value,part in g.groupby(key,observed=True):
                destination.append(dict(model_id=identifier,cluster=int(label),category=value,segments=len(part),LN=int(part.LN.sum()),
                    mean_relative_turnout=float(part.relative_turnout.mean()),mean_adjusted_gap=float(part.sex_gap_adjusted.mean())))
        for key,part in g.groupby(MUNICIPAL_KEYS,observed=True):
            municipal.append(dict(model_id=identifier,cluster=int(label),EDOCVE=key[0],MPIOCVE=key[1],segments=len(part),LN=int(part.LN.sum())))
    summary=pd.DataFrame(rows)
    require(np.array_equal(summary[METRICS].sum().to_numpy(),main[METRICS].sum().to_numpy()),'Conteos por cluster no concilian.')
    return dict(cluster_profiles=summary,cluster_curves=pd.DataFrame(curves),age_composition=pd.DataFrame(ages),
                sex_composition=pd.DataFrame(sexes),state_composition=pd.DataFrame(states),municipality_distribution=pd.DataFrame(municipal),rules_contingency=pd.DataFrame(contingencies))


def aligned_labels(reference,alternative):
    """Alineación nominal sobre la población declarada; ARI no la necesita."""
    reference=np.asarray(reference,int);alternative=np.asarray(alternative,int)
    left=np.unique(reference);right=np.unique(alternative)
    table=np.array([[np.sum((reference==a)&(alternative==b)) for b in right] for a in left])
    rows,cols=linear_sum_assignment(-table)
    mapping=dict(zip(right[cols],left[rows]))
    for label in right:
        if label not in mapping:mapping[label]=int(max(left))+1+len(mapping)
    aligned=np.array([mapping[x] for x in alternative])
    return aligned,{str(int(a)):int(b) for a,b in mapping.items()}


class Experiment:
    table=Comparison.table
    bundle=Comparison.bundle
    bundle_paths=Comparison.bundle_paths
    load_model=Comparison.load_model
    load_arrays=Comparison.load_arrays
    valid_stage=Comparison.valid_stage

    def __init__(self,root,output,charts,report,replicates=10,anchors=512):
        self.root,self.output,self.charts,self.report=map(lambda p:Path(p).resolve(),[root,output,charts,report])
        require(self.output.is_relative_to(self.root/'data/processed') and self.charts.is_relative_to(self.root/'analysis/charts') and self.report.is_relative_to(self.root/'analysis/reports'),'Destinos inválidos.')
        self.replicates,self.anchors=replicates,anchors;self.state_path=self.output/'metadata/state.json'
        self.dependencies=probe_dependencies()
        require(sys.version_info[:2]==(3,13),'Usar Python 3.13 de .venv_pattern_algorithms.')
        require(all(self.dependencies['imports'][name]['available'] for name in ['numpy','pandas','sklearn','scipy','pyarrow','joblib']),'Dependencias no disponibles.')
        self.configuration={**CONFIG,'replicates':replicates,'anchors':anchors}
        if self.state_path.exists():
            self.state=json.loads(self.state_path.read_text(encoding='utf8'))
            require(self.state['configuration']==self.configuration,'Parámetros distintos de la reanudación.')
            require(self.state['charts']==str(self.charts) and self.state['report']==str(self.report),'Destinos distintos.')
            require(self.state['dependencies']['imports']==self.dependencies['imports'],'Bibliotecas diferentes de los checkpoints.')
            self.verify_protected()
        else:
            require(not [p for p in self.output.rglob('*') if p.is_file() and p.name!='_RUNNING.json'] and not self.charts.exists() and not self.report.exists(),'Destinos anteriores sin estado; no se sobrescriben.')
            protected=snapshot_inputs(self.root,self.output,self.charts)
            for folder in ['analysis/scripts','src','public','docs']:
                for path in (self.root/folder).rglob('*'):
                    if path.is_file() and '__pycache__' not in path.parts and path.name not in OWN_FILES:
                        protected[str(path)]=file_hash(path)
            for name in ['.gitignore','.venv/pyvenv.cfg','.venv_pattern_algorithms/pyvenv.cfg']:
                path=self.root/name
                if path.exists():protected[str(path)]=file_hash(path)
            self.state=dict(started=utc(),status='running',configuration=self.configuration,protected_hashes=protected,
                dependencies=self.dependencies,charts=str(self.charts),report=str(self.report),stages={},errors=[])
            write_json(self.state_path,self.state)

    def verify_protected(self):
        for name,digest in self.state['protected_hashes'].items():require(file_hash(name)==digest,'Archivo previo modificado: '+name)

    def checkpoint(self,stage,paths,started,summary):
        record=dict(status='complete',stage=stage,finished=utc(),seconds=time.monotonic()-started,memory=memory_estimate(),
            summary=summary,script_sha256=file_hash(Path(__file__)),versions=self.dependencies['imports'],
            artifacts={str(p.relative_to(self.root)):file_hash(p) for p in paths})
        write_json(self.output/f'metadata/checkpoint_{stage}.json',record)
        self.state['stages'][stage]=dict(seconds=record['seconds'],summary=summary)
        self.state['status']='running';write_json(self.state_path,self.state)
        print(f'{stage}: {summary}',flush=True)

    def data(self):
        full=pd.read_parquet(self.output/'reference/segments.parquet')
        main=full[full.common_eligible].reset_index(drop=True)
        return full,main

    def representations(self):
        result=json.loads((self.output/'metadata/representations.json').read_text(encoding='utf8'))
        path=self.output/'metadata/context_representations.json'
        if path.exists():result.update(json.loads(path.read_text(encoding='utf8')))
        return result

    def verify_source(self,name):
        folder=self.root/'data/processed'/name;path=folder/'metadata/run_manifest.json'
        record=json.loads(path.read_text(encoding='utf8'));success=json.loads((folder/'_SUCCESS').read_text(encoding='utf8'))
        require(record['status']=='validated' and success['manifest_sha256']==file_hash(path),'Fuente sin validar: '+name)
        for relative,digest in record.get('artifact_hashes',{}).items():
            file=Path(relative) if Path(relative).is_absolute() else self.root/relative
            if not file.exists():file=folder/relative
            require(file_hash(file)==digest,'Artefacto fuente alterado: '+relative)

    def stage_a(self):
        started=time.monotonic();paths=[]
        reports=['demographic_pilot','demographic_representation_comparison','cluster_feature_review','contextual_clustering_pilot',
                 'participation_pattern_review','pattern_algorithm_comparison','age_band_representation_review','profile_candidates_review']
        diagnosis=dict(reports={},dependencies=self.dependencies,git_status=None,process_exclusion='Lock exclusivo del experimento y consulta no destructiva previa; no se usa os.kill.')
        for name in reports:
            path=self.root/f'analysis/reports/{name}.md';require(path.exists(),'Informe ausente: '+name)
            diagnosis['reports'][name]=dict(path=str(path.relative_to(self.root)),sha256=file_hash(path),characters=len(path.read_text(encoding='utf8')))
        diagnosis['git_status']=subprocess.run(['git','status','--short'],cwd=self.root,capture_output=True,text=True).stdout
        diagnosis['pip_check']=subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True).stdout
        for name in ['profile_candidates_review','participation_pattern_review','contextual_feature_review','cluster_features','demographic_pilot','demographic_representation_comparison']:
            self.verify_source(name)
        full=pd.read_parquet(self.root/'data/processed/profile_candidates_review/reference/segments_2024.parquet')
        profiles=pd.read_parquet(self.root/'data/processed/participation_pattern_review/reference/profiles.parquet')
        municipalities=pd.read_parquet(self.root/'data/processed/descriptive/municipality/table.parquet')
        full,national,gap,municipal=build_features(full,profiles,municipalities)
        base=full[full.base_eligible];main=full[full.common_eligible]
        require(len(full)==17735 and len(base)==14190 and len(base[MUNICIPAL_KEYS].drop_duplicates())==2402,'Población principal inesperada.')
        require(int(base.LN.sum())==98203780,'LN principal diferente.')
        require(len(main)==13908 and len(main[MUNICIPAL_KEYS].drop_duplicates())==2341,'Población común inesperada.')
        compare_sums(full,municipalities[municipalities.election_year.eq(2024)],MUNICIPAL_KEYS)
        compare_sums(full,pd.read_parquet(self.root/'data/processed/profile_candidates_review/reference/segments_2024.parquet'),SEGMENT_KEYS)
        require(np.allclose(base.relative_turnout,base.participation_delta),'Referencia nacional previa distinta.')
        require(full.loc[full.SEXO.eq('2'),'LN'].sum()==105 and full.loc[full.SEXO.eq('2'),'source_row_count'].sum()==105,'Categoría complementaria alterada.')
        for key in PROFILE_KEYS:require(full[key].map(lambda x:isinstance(x,str)).all(),'Código no textual.')
        old=pd.read_parquet(self.root/'data/processed/participation_pattern_review/features/r2.parquet')
        parameters=json.loads((self.root/'data/processed/participation_pattern_review/metadata/parameters.json').read_text(encoding='utf8'))
        recovered=(profiles.loc[profiles.is_eligible,['delta_'+s for s in SUFFIXES]].to_numpy()@Q-np.array(parameters['shape_mean']))/parameters['shape_scale']
        require(np.array_equal(recovered,old.drop(columns='row_id').to_numpy()),'Contrastes no reproducen exactamente R2.')
        coverage=[]
        for name,blocks in {**REPRESENTATIONS,'all_common':list(BLOCKS)}.items():
            mask=full.base_eligible.copy()
            for block in blocks:mask &= full[block+'_available']
            part=full[mask];muns=len(part[MUNICIPAL_KEYS].drop_duplicates())
            coverage.append(dict(representation=name,blocks='+'.join(blocks),segments=len(part),municipalities=muns,
                LN=int(part.LN.sum()),nominal_fraction=float(part.LN.sum()/NATIONAL_LN),
                municipal_loss_pp=(2402-muns)/2477*100,nominal_loss_pp=(base.LN.sum()-part.LN.sum())/NATIONAL_LN*100,
                high_ns_segments=int(part.unspecified_rate.ge(.1).sum()),few_sections_segments=int(part.section_count.lt(5).sum()),
                null_features=int(part[[c for b in blocks for c in BLOCKS[b]]].isna().sum().sum())))
        coverage=pd.DataFrame(coverage)
        common_record=coverage[coverage.representation.eq('all_common')].iloc[0]
        require(common_record.municipal_loss_pp<=CONFIG['municipal_alert_pp'] and common_record.nominal_loss_pp<=CONFIG['nominal_alert_pp'],'Cobertura común insuficiente: detener modelos y revisar.')
        columns=[*PROFILE_KEYS,'age_band','row_id','base_eligible','common_eligible','common_pending_reason',*METRICS]
        paths += [self.table('reference/segments.parquet',full),self.table('reference/national_peer_reference.parquet',national),
                  self.table('reference/gaps.parquet',gap),self.table('reference/municipal_context.parquet',municipal),
                  self.table('reference/pending.parquet',full.loc[~full.common_eligible]),
                  self.table('reference/population_membership.parquet',full[columns]),self.table('diagnostics/coverage.csv',coverage)]
        for kind in ['base_eligible','common_eligible']:
            state=full.groupby(['EDOCVE','state_name_label'],as_index=False,observed=True).agg(LN=('LN','sum'),segments=('row_id','size'))
            eligible=full[full[kind]].groupby('EDOCVE',as_index=False,observed=True).agg(eligible_LN=('LN','sum'),eligible_segments=('row_id','size'),eligible_municipalities=('MPIOCVE','nunique'))
            state=state.merge(eligible,on='EDOCVE',how='left',validate='one_to_one')
            state['nominal_fraction']=state.eligible_LN/state.LN
            paths.append(self.table('diagnostics/state_coverage_'+kind+'.csv',state))
        path=self.output/'metadata/repository_diagnosis.json';write_json(path,diagnosis);paths.append(path)
        self.checkpoint('A',paths,started,f'Fuentes verificadas; base {len(base):,} / común {len(main):,} segmentos, {common_record.municipalities:,} municipios, LN {common_record.nominal_fraction:.4%}.')

    def stage_b(self):
        started=time.monotonic();full,main=self.data();paths=[]
        correlations,distributions,ranks=feature_audit(main)
        paths += [self.table('diagnostics/correlations.csv',correlations),self.table('diagnostics/distributions.csv',distributions),self.table('diagnostics/matrix_rank.csv',ranks)]
        representations={};parameters=fit_scalers(main,list(BLOCKS));distance_rows=[]
        for name,blocks in REPRESENTATIONS.items():
            r=ranks[ranks.representation.eq(name)].iloc[0]
            valid=r['rank']==r.features and r.condition<CONFIG['maximum_matrix_condition']
            representations[name]=dict(blocks=blocks,training_allowed=bool(valid),reason='rank_full' if valid else 'rank_or_condition_failure',scope='common')
            if not valid:continue
            values,slices,weights=transform(main,blocks,parameters)
            matrix=pd.DataFrame(values,columns=[c for b in blocks for c in BLOCKS[b]]);matrix.insert(0,'row_id',main.row_id)
            paths.append(self.table(f'features/{name}/matrix.parquet',matrix))
            for block,(a,b) in slices.items():
                observed=float(np.mean(np.sum(values[:,a:b]**2,axis=1)))
                require(abs(observed-weights[block])<1e-12,'Un bloque pesa más por dimensión.')
                distance_rows.append(dict(representation=name,block=block,weight=weights[block],observed_total_variance=observed))
        path=self.output/'features/block_scalers.json';write_json(path,parameters);paths.append(path)
        paths.append(self.table('diagnostics/block_variance.csv',pd.DataFrame(distance_rows)))
        block_coverage=[]
        for block,columns in BLOCKS.items():
            available=full.base_eligible&full[block+'_available']
            block_coverage.append(dict(block=block,segments=int(available.sum()),missing_among_base=int((full.base_eligible&~available).sum()),
                municipalities=len(full.loc[available,MUNICIPAL_KEYS].drop_duplicates()),LN=int(full.loc[available,'LN'].sum()),features=len(columns)))
        paths.append(self.table('diagnostics/block_availability.csv',pd.DataFrame(block_coverage)))
        status=full.groupby(['common_pending_reason','A_available','S_available'],as_index=False,observed=True).agg(segments=('row_id','size'),LN=('LN','sum'))
        paths.append(self.table('diagnostics/exclusion_reasons.csv',status))
        contract=dict(unit='municipality_age_band_sex',year=2024,blocks=BLOCKS,definitions={
            'P':'SV/(SV+NV) − nacional del mismo intervalo/sexo; todos los conteos antes del soporte.',
            'A':'q=dQ, Q ortonormal fija; (d18−d35)/sqrt(2), (d18+d35−2d60)/sqrt(6). Compartido municipio/sexo.',
            'S':'d_mujeres − d_hombres, siempre dirigido así y NULL sin soporte de ambos. Compartido municipio/intervalo.',
            'M':'ΣSV_core/Σden_core − Σ(den_i*r_nacional_i)/Σden_core; core H/M 18–100. Compartido municipio.',
            'T':'pQ sobre p=(LN_U,LN_R,LN_M)/LN, dos contrastes isométricos del simplex con distancia euclídea. Ceros válidos; no lograzones ni Aitchison.'},
            algebra=['LN=SV+NV+NS','observada+no_observada=1','S=d_F−d_M; no es fuente independiente de los conteos',
                'M es promedio ponderado de diferencias de todas las celdas del municipio',
                'A transforma las mismas diferencias de las tres edades, elimina su media',
                'p_U+p_R+p_M=1; Q elimina sólo la dirección constante',
                'Con la edad como metadato, P−shape_edad recupera nivel del patrón; no se duplican coordenadas de nivel'],
            scaling='Centrar cada columna y dividir cada bloque por sqrt(mean(sum((x−media)^2))); multiplicar por sqrt(peso). Peso total igual entre bloques, no entre columnas.',
            dependence='A se repite hasta tres veces por municipio/sexo; S hasta dos por municipio/edad; M hasta seis por municipio. Las filas no son réplicas independientes de esas propiedades.',
            eligibility='LN>=100, SV+NV>=100, source_row_count>=5, H/M 18–100 y tasa finita; A exige las tres bandas; S ambos sexos.',
            common_row_ids_sha256=hashlib.sha256('\n'.join(main.row_id).encode()).hexdigest(),original_reference_rows=len(full),common_rows=len(main),
            age_mean_is_feature=False,identifiers_are_features=False)
        path=self.output/'metadata/feature_contract.json';write_json(path,contract);paths.append(path)
        path=self.output/'metadata/representations.json';write_json(path,representations);paths.append(path)
        self.checkpoint('B',paths,started,'Auditoría previa completa; parámetros RMS por bloque, rangos y dependencias guardados antes de entrenar.')

    def main_matrix(self,representation):
        _,main=self.data();blocks=self.representations()[representation]['blocks']
        parameters=json.loads((self.output/'features/block_scalers.json').read_text(encoding='utf8'))
        values,slices,weights=transform(main,blocks,parameters)
        return main,values,slices,weights

    def fit(self,identifier,values,algorithm,k,seed,weights=None,gmm_reg=None):
        starts=CONFIG['kmeans_starts'] if algorithm=='kmeans' else CONFIG['gmm_starts']
        weight_digest=None if weights is None else hashlib.sha256(np.ascontiguousarray(weights).tobytes()).hexdigest()
        params=dict(algorithm=algorithm,k=int(k),seed=int(seed),n_init=starts,max_iter=1000,
                    weights_sha256=weight_digest,reg_covar=gmm_reg or CONFIG['gmm_reg_covar'])
        def callback():
            if algorithm=='kmeans':
                initial_seeds=np.random.SeedSequence(seed).generate_state(starts)
                fits=[];initializations=[]
                for number,s in enumerate(initial_seeds):
                    model=KMeans(n_clusters=k,n_init=1,random_state=int(s),max_iter=1000,tol=0.,algorithm='lloyd').fit(values,sample_weight=weights)
                    fits.append(model);initializations.append(dict(initialization=number,seed=int(s),sse=float(model.inertia_),iterations=int(model.n_iter_),converged=bool(model.n_iter_<1000)))
                best=fits[int(np.argmin([m.inertia_ for m in fits]))]
                labels=best.labels_.copy();sample_weights=np.ones(len(values)) if weights is None else weights
                centers=np.vstack([np.average(values[labels==j],axis=0,weights=sample_weights[labels==j]) for j in range(k)])
                require(np.allclose(centers,best.cluster_centers_,atol=1e-9),'Centroides no reproducibles.')
                sse=float(np.sum(sample_weights*np.sum((values-centers[labels])**2,axis=1)))
                require(abs(sse-best.inertia_)<1e-7*max(1.,sse),'SSE no conciliada.')
                for record,model in zip(initializations,fits):record['ari_to_best']=float(adjusted_rand_score(labels,model.labels_))
                details=dict(sse=sse,sse_per_weight=sse/float(sample_weights.sum()),iterations=int(best.n_iter_),converged=bool(best.n_iter_<1000),
                    initializations=initializations,minimum_initialization_ari=min(x['ari_to_best'] for x in initializations))
                return best,dict(labels=labels,centers=best.cluster_centers_,initial_labels=np.vstack([m.labels_ for m in fits])),details
            model=GaussianMixture(n_components=k,covariance_type='full',n_init=starts,max_iter=1000,tol=CONFIG['gmm_tol'],
                random_state=seed,reg_covar=params['reg_covar'],init_params='kmeans').fit(values)
            posterior=model.predict_proba(values);eigenvalues=np.linalg.eigvalsh(model.covariances_)
            details=dict(aic=float(model.aic(values)),bic=float(model.bic(values)),converged=bool(model.converged_),iterations=int(model.n_iter_),
                lower_bound=float(model.lower_bound_),minimum_covariance_eigenvalue=float(eigenvalues.min()),
                maximum_covariance_condition=float(np.max(eigenvalues[:,-1]/eigenvalues[:,0])),
                regularization_touched_components=int(np.sum(eigenvalues[:,0]<=params['reg_covar']*1.1)),
                **posterior_summary(posterior))
            require(eigenvalues.min()>0 and details['maximum_covariance_condition']<1e7,'Covarianza mal condicionada; no continuar silenciosamente.')
            return model,dict(labels=model.predict(values),posterior=posterior,centers=model.means_,covariance_eigenvalues=eigenvalues),details
        return self.bundle(identifier,values,params,callback)

    def train_representations(self,names,index_relative):
        records=[];ids=[]
        for name in names:
            if not self.representations()[name]['training_allowed']:continue
            main,values,_,_=self.main_matrix(name)
            for algorithm,ks in [('kmeans',range(2,7)),('gmm',range(1,7))]:
                for k in ks:
                    for seed in SEEDS:
                        identifier=model_id(name,algorithm,k,seed)
                        _,arrays,details=self.fit(identifier,values,algorithm,k,seed);ids.append(identifier)
                        record={key:value for key,value in details.items() if key not in ['initializations','warnings','memory']}
                        records.append(dict(model_id=identifier,representation=name,algorithm=algorithm,k=k,seed=seed,**record))
                    print(f'{name} {algorithm} K={k}: tres semillas completas.',flush=True)
        paths=self.bundle_paths(ids)+[self.table(index_relative,pd.DataFrame(records))]
        return paths

    def stage_c(self):
        started=time.monotonic()
        paths=self.train_representations(list(REPRESENTATIONS),'metadata/main_model_index.csv')
        paths.extend(self.evaluate(list(REPRESENTATIONS),'principal'))
        self.checkpoint('C',paths,started,'F0–F3: K-Means K2–6 y GMM full 1–6, tres semillas, mismas filas; métricas y etiquetas incrementales.')

    def evaluate(self,names,prefix):
        full,main=self.data();records=[];profiles=[];curves=[];ages=[];sexes=[];states=[];municipal=[];contingencies=[];paths=[];seed_rows=[];best_rows=[]
        anchors=np.random.default_rng(20241023).choice(len(main),size=min(self.anchors,len(main)),replace=False)
        for name in names:
            if not self.representations()[name]['training_allowed']:continue
            _,values,slices,_=self.main_matrix(name)
            partitions={}
            for algorithm,ks in [('kmeans',range(2,7)),('gmm',range(1,7))]:
                for k in ks:
                    candidates=[];labels_by_seed=[]
                    for seed in SEEDS:
                        identifier=model_id(name,algorithm,k,seed);arrays=self.load_arrays(identifier)
                        details=json.loads((self.output/'models'/identifier/'details.json').read_text(encoding='utf8'))
                        objective=details['sse'] if algorithm=='kmeans' else details['bic'];candidates.append((objective,seed,identifier))
                        labels=arrays['labels'];labels_by_seed.append((seed,labels))
                        size=np.bincount(labels,minlength=k)
                        require(size.sum()==len(main),'Etiquetas no alineadas.')
                        record=dict(model_id=identifier,representation=name,algorithm=algorithm,k=k,seed=seed,n=len(main),groups=len(np.unique(labels)),
                            smallest_cluster=int(size.min()),largest_cluster=int(size.max()),smallest_fraction=float(size.min()/len(main)),
                            municipalities=len(main[MUNICIPAL_KEYS].drop_duplicates()),LN=int(main.LN.sum()),nominal_fraction=float(main.LN.sum()/NATIONAL_LN),
                            silhouette=np.nan,silhouette_mc_se=np.nan,db=np.nan,
                            converged=details['converged'],iterations=details['iterations'])
                        for key in ['sse','sse_per_weight','aic','bic','ambiguous_80','mean_max_posterior','mean_normalized_entropy',
                            'minimum_initialization_ari','minimum_covariance_eigenvalue','maximum_covariance_condition','regularization_touched_components']:
                            record[key]=details.get(key,np.nan)
                        if len(np.unique(labels))>=2:
                            partitions[identifier]=labels;record['db']=float(davies_bouldin_score(values,labels))
                        record.update(partition_diagnostics(main,values,labels,slices));records.append(record)
                        output=full[['row_id',*SEGMENT_KEYS,'base_eligible','common_eligible','common_pending_reason']].copy()
                        output['label']=pd.Series(pd.NA,index=output.index,dtype='Int64');output.loc[full.common_eligible,'label']=labels
                        paths.append(self.table('assignments/'+identifier+'.parquet',output))
                    objective,seed,identifier=min(candidates)
                    best_rows.append(dict(representation=name,algorithm=algorithm,k=k,seed=seed,model_id=identifier,objective=objective))
                    for (s1,l1),(s2,l2) in combinations(labels_by_seed,2):
                        seed_rows.append(dict(representation=name,algorithm=algorithm,k=k,seed_1=s1,seed_2=s2,ari=float(adjusted_rand_score(l1,l2))))
                    labels=self.load_arrays(identifier)['labels'];descriptions=describe(main,labels,identifier)
                    for key,destination in [('cluster_profiles',profiles),('cluster_curves',curves),('age_composition',ages),('sex_composition',sexes),('state_composition',states),('municipality_distribution',municipal),('rules_contingency',contingencies)]:destination.append(descriptions[key])
            scores=anchor_silhouettes(values,partitions,anchors,block_size=16)
            for record in records:
                if record['model_id'] in scores:
                    s=scores[record['model_id']];record['silhouette']=float(s.mean())
                    record['silhouette_mc_se']=float(s.std(ddof=1)/np.sqrt(len(s))*np.sqrt((len(main)-len(s))/(len(main)-1)))
                    record['negative_silhouette_fraction']=float(np.mean(s<0))
        for key,frames in [('cluster_profiles',profiles),('cluster_curves',curves),('age_composition',ages),('sex_composition',sexes),('state_composition',states),('municipality_distribution',municipal),('rules_contingency',contingencies)]:
            paths.append(self.table(f'metadata/{prefix}_{key}.parquet',pd.concat(frames,ignore_index=True)))
        paths += [self.table(f'metadata/{prefix}_metrics.csv',pd.DataFrame(records)),self.table(f'metadata/{prefix}_seed_stability.csv',pd.DataFrame(seed_rows)),
                  self.table(f'metadata/{prefix}_best_models.csv',pd.DataFrame(best_rows)),self.table(f'metadata/{prefix}_silhouette_anchors.parquet',pd.DataFrame(dict(row_id=main.row_id.iloc[anchors].to_numpy(),index=anchors)))]
        return paths

    def all_metrics(self):
        paths=[self.output/'metadata/principal_metrics.csv',self.output/'metadata/contextual_metrics.csv']
        return pd.concat([pd.read_csv(p) for p in paths if p.exists()],ignore_index=True)

    def best_models(self):
        paths=[self.output/'metadata/principal_best_models.csv',self.output/'metadata/contextual_best_models.csv']
        return pd.concat([pd.read_csv(p) for p in paths if p.exists()],ignore_index=True)

    def novelty_selection(self,metrics,only_base=False):
        """Selección operativa de diagnóstico, no decide representación ni K final."""
        averaged=metrics[metrics.algorithm.eq('kmeans')&metrics.k.between(2,5)].groupby(['representation','k'],as_index=False).mean(numeric_only=True)
        seed_paths=[self.output/'metadata/principal_seed_stability.csv',self.output/'metadata/contextual_seed_stability.csv']
        seeds=pd.concat([pd.read_csv(p) for p in seed_paths if p.exists()],ignore_index=True)
        minimum=seeds[seeds.algorithm.eq('kmeans')].groupby(['representation','k']).ari.min()
        reference=averaged[averaged.representation.eq('F0')].set_index('k')
        rows=[]
        for row in averaged.itertuples():
            if row.representation=='F0' or (only_base and row.representation not in ['F1','F2','F3']):continue
            r=reference.loc[row.k];gain=.5*((row.shape_r2-r.shape_r2)+(row.sex_gap_r2-r.sex_gap_r2))
            retention=row.within_age_sex_rate_r2/r.within_age_sex_rate_r2
            stable=float(minimum.loc[(row.representation,row.k)])
            accepted=retention>=CONFIG['retained_conditional_turnout'] and stable>=CONFIG['seed_stability_gate'] and row.smallest_fraction>=CONFIG['minimum_cluster_fraction']
            rows.append(dict(representation=row.representation,k=int(row.k),novelty_gain=float(gain),retained_turnout=float(retention),
                             seed_ari_min=stable,smallest_fraction=float(row.smallest_fraction),passes_operational_gate=bool(accepted)))
        return pd.DataFrame(rows).sort_values(['passes_operational_gate','novelty_gain','k'],ascending=[False,False,True]).reset_index(drop=True)

    def stage_d(self):
        started=time.monotonic();_,main=self.data();metrics=self.all_metrics();selection=self.novelty_selection(metrics,only_base=True)
        paths=[self.table('metadata/context_base_selection.csv',selection)]
        passing=selection[selection.passes_operational_gate&selection.novelty_gain.gt(.05)]
        if len(passing):
            chosen=passing.iloc[0];base=chosen.representation
            reason='Mayor ganancia media descriptiva en forma/brecha, conservando >=80% de separación condicional de tasas, ARI semillas>=.90 y cluster mínimo>=2%; K6 excluido.'
        else:
            base='F0';reason='Ninguna ampliación supera todas las puertas exploratorias; F0 es control para probar el contexto, no ganador.'
        predictors=main[[c for b in self.representations()[base]['blocks'] for c in BLOCKS[b]]].to_numpy(float)
        plans={};audit=[];scalers=json.loads((self.output/'features/block_scalers.json').read_text(encoding='utf8'))
        for block in ['M','T']:
            residual=residual_fraction(main[BLOCKS[block]].to_numpy(),predictors)
            blocks=self.representations()[base]['blocks']+[block]
            values,slices,weights=transform(main,blocks,scalers);singular=np.linalg.svd(values-values.mean(axis=0),compute_uv=False)
            condition=float(singular[0]/singular[-1]);rank=int(np.linalg.matrix_rank(values-values.mean(axis=0)))
            valid=residual>=CONFIG['minimum_residual_fraction'] and rank==values.shape[1] and condition<CONFIG['maximum_matrix_condition']
            name='F4'+block
            plans[name]=dict(blocks=blocks,base=base,training_allowed=bool(valid),reason='residual_variation_and_rank' if valid else 'redundancy_or_condition_gate',scope='common')
            audit.append(dict(representation=name,base=base,block=block,residual_fraction=residual,rank=rank,columns=values.shape[1],condition=condition,training_allowed=bool(valid)))
            if valid:
                frame=pd.DataFrame(values,columns=[c for b in blocks for c in BLOCKS[b]]);frame.insert(0,'row_id',main.row_id)
                paths.append(self.table(f'features/{name}/matrix.parquet',frame))
        path=self.output/'metadata/context_representations.json';write_json(path,plans);paths.append(path)
        paths.append(self.table('diagnostics/context_audit.csv',pd.DataFrame(audit)))
        path=self.output/'metadata/context_decision.json';write_json(path,dict(base=base,reason=reason,criterion='Predefinido; no utiliza Silhouette para seleccionar pesos.',F4_never_combines_M_T=True));paths.append(path)
        valid=[name for name,spec in plans.items() if spec['training_allowed']]
        if valid:
            paths.extend(self.train_representations(valid,'metadata/context_model_index.csv'))
            paths.extend(self.evaluate(valid,'contextual'))
        self.checkpoint('D',paths,started,f'F4 parte de {base}; contextualización auditada separadamente: {valid}. No se agregan M y T juntos.')

    def stage_e(self):
        """Concordancia, selección limitada y remuestreo sin separar municipios."""
        started=time.monotonic();full,main=self.data();metrics=self.all_metrics();best=self.best_models();paths=[]
        comparison=[]
        for row in best.itertuples():
            labels=self.load_arrays(row.model_id)['labels']
            if row.representation!='F0' and row.algorithm=='kmeans':
                base=best[best.representation.eq('F0')&best.algorithm.eq('kmeans')&best.k.eq(row.k)].iloc[0]
                comparison.append(dict(model_id=row.model_id,comparison='F0_same_K',reference_id=base.model_id,
                    ari=float(adjusted_rand_score(self.load_arrays(base.model_id)['labels'],labels))))
            comparison.append(dict(model_id=row.model_id,comparison='six_rules',reference_id='candidate_id',
                ari=float(adjusted_rand_score(pd.factorize(main.candidate_id,sort=True)[0],labels))))
        paths.append(self.table('metadata/partition_comparisons.csv',pd.DataFrame(comparison)))
        selection=self.novelty_selection(metrics)
        paths.append(self.table('metadata/candidate_selection_audit.csv',selection))
        choice=selection.iloc[0]
        augmented=best[best.representation.eq(choice.representation)&best.algorithm.eq('kmeans')&best.k.eq(choice.k)].iloc[0]
        baseline=best[best.representation.eq('F0')&best.algorithm.eq('kmeans')&best.k.eq(choice.k)].iloc[0]
        gmm_rows=best[best.representation.eq(choice.representation)&best.algorithm.eq('gmm')]
        # BIC se compara únicamente dentro de la MISMA representación.
        gmm=gmm_rows.sort_values('objective').iloc[0]
        selected=[baseline.model_id,augmented.model_id]
        if gmm.k>=2:selected.append(gmm.model_id)
        path=self.output/'metadata/selected_configurations.json'
        write_json(path,dict(model_ids=selected,maximum=3,augmented_passes_gate=bool(choice.passes_operational_gate),
            reason='F0 emparejado en K; ampliación con máxima ganancia de forma/brecha entre las que cumplen puertas, si existen; GMM BIC mínimo dentro de esa ampliación. No fija ganador.',
            gmm_selection=dict(model_id=gmm.model_id,k=int(gmm.k),bic=float(gmm.objective)),sampling='Primeras diez submuestras previas de municipios, sin reemplazo; no bootstrap.'))
        paths.append(path)
        membership=pd.read_parquet(self.root/'data/processed/demographic_representation_comparison/resampling/municipality_membership.parquet')
        paths.append(self.table('resampling/municipality_membership.parquet',membership))
        marks=main[MUNICIPAL_KEYS].merge(membership,on=MUNICIPAL_KEYS,validate='many_to_one',sort=False)
        full_marks=full[MUNICIPAL_KEYS].merge(membership,on=MUNICIPAL_KEYS,validate='many_to_one',sort=False)
        require(len(marks)==len(main) and len(full_marks)==len(full),'Membresía duplicó filas.')
        stability=[];coverage=[];profile_shifts=[]
        selected_rows=best[best.model_id.isin(selected)]
        for sample in range(self.replicates):
            train=marks[f'sample_{sample:03d}'].to_numpy(bool);oob=~train;whole=full_marks[f'sample_{sample:03d}'].to_numpy(bool)
            require(train.any() and oob.any(),'Remuestra vacía.')
            for _,group in main.assign(in_bag=train).groupby(MUNICIPAL_KEYS,observed=True):require(group.in_bag.nunique()==1,'Municipio partido entre in-bag y OOB.')
            coverage.append(dict(sample=sample,drawn_municipalities=int(membership[f'sample_{sample:03d}'].sum()),
                training_segments=int(train.sum()),oob_segments=int(oob.sum()),training_municipalities=len(main.loc[train,MUNICIPAL_KEYS].drop_duplicates()),
                oob_municipalities=len(main.loc[oob,MUNICIPAL_KEYS].drop_duplicates()),
                training_LN=int(main.loc[train,'LN'].sum()),training_fraction_eligible_LN=float(main.loc[train,'LN'].sum()/main.LN.sum()),
                selected_original_LN=int(full.loc[whole,'LN'].sum()),selected_original_segments=int(whole.sum())))
            for row in selected_rows.itertuples():
                spec=self.representations()[row.representation];parameters=fit_scalers(main.loc[train],spec['blocks'])
                values,_,_=transform(main,spec['blocks'],parameters)
                identifier=f'resampling/sample_{sample:03d}/'+row.model_id
                model,arrays,_=self.fit(identifier,values[train],row.algorithm,row.k,17)
                labels=model.predict(values);reference=self.load_arrays(row.model_id)['labels']
                aligned,mapping=aligned_labels(reference,labels)
                oob_ari=float(adjusted_rand_score(reference[oob],labels[oob]))
                record=dict(sample=sample,model_id=row.model_id,fit_id=identifier,algorithm=row.algorithm,representation=row.representation,k=row.k,
                    ari_all=float(adjusted_rand_score(reference,labels)),ari_oob=oob_ari,
                    aligned_change_fraction=float(np.mean(aligned!=reference)),aligned_oob_change_fraction=float(np.mean(aligned[oob]!=reference[oob])),
                    training_segments=int(train.sum()),oob_segments=int(oob.sum()),alignment=json.dumps(mapping),
                    ari_inbag=float(adjusted_rand_score(reference[train],labels[train])))
                if row.algorithm=='gmm':record.update(posterior_summary(model.predict_proba(values[oob])))
                stability.append(record)
                for label in np.unique(reference):
                    old=main[(reference==label)&oob];new=main[(aligned==label)&oob]
                    for feature in ['relative_turnout','age_shape_1','age_shape_2','sex_gap_adjusted','municipal_adjusted_turnout']:
                        profile_shifts.append(dict(sample=sample,model_id=row.model_id,cluster=int(label),feature=feature,
                            reference_oob_mean=float(old[feature].mean()),sample_oob_mean=float(new[feature].mean()),
                            difference=float(new[feature].mean()-old[feature].mean()),reference_segments=len(old),sample_segments=len(new)))
                assigned=main[['row_id',*SEGMENT_KEYS]].copy();assigned['is_training']=train;assigned['is_oob_eligible']=oob
                assigned['label']=labels;assigned['aligned_label']=aligned
                paths.append(self.table(f'resampling/sample_{sample:03d}/{row.representation}_{row.algorithm}_assignments.parquet',assigned))
                path=self.output/f'resampling/sample_{sample:03d}/{row.representation}_{row.algorithm}_scalers.json';write_json(path,parameters);paths.append(path)
                paths.extend(self.bundle_paths([identifier]))
            print(f'Remuestra municipal {sample+1}/{self.replicates}: {int(train.sum()):,} in-bag / {int(oob.sum()):,} OOB.',flush=True)
        paths += [self.table('metadata/municipal_stability.csv',pd.DataFrame(stability)),self.table('metadata/resampling_coverage.csv',pd.DataFrame(coverage)),
                  self.table('metadata/resampling_profile_shifts.csv',pd.DataFrame(profile_shifts))]
        self.checkpoint('E',paths,started,f'{len(selected)} configuraciones × {self.replicates} submuestras municipales; escalas sólo in-bag, referencia nacional fija y etiquetas OOB diferenciadas.')

    def stage_f(self):
        started=time.monotonic();full,main=self.data();best=self.best_models();paths=[];records=[];population_rows=[]
        selected=json.loads((self.output/'metadata/selected_configurations.json').read_text(encoding='utf8'))['model_ids']
        main_scalers=json.loads((self.output/'features/block_scalers.json').read_text(encoding='utf8'))
        for row in best[best.model_id.isin(selected)].itertuples():
            blocks=self.representations()[row.representation]['blocks'];reference=self.load_arrays(row.model_id)['labels']
            masks={'low_ns_segment':main.unspecified_rate.lt(.1).to_numpy(), 'five_sections':main.section_count.ge(5).to_numpy()}
            scenarios=list(masks)+(['equal_municipality'] if row.algorithm=='kmeans' else [])
            if len(blocks)>1:scenarios.append('p_heavy')
            if row.algorithm=='gmm':scenarios.append('regularization_x10')
            for scenario in scenarios:
                mask=masks.get(scenario,np.ones(len(main),bool))
                values,slices,weights=transform(main,blocks,main_scalers,p_heavy=scenario=='p_heavy')
                sample_weights=None
                if scenario=='equal_municipality':
                    counts=main.groupby(MUNICIPAL_KEYS,observed=True).row_id.transform('size').to_numpy()
                    sample_weights=1./counts
                    check=main[MUNICIPAL_KEYS].assign(weight=sample_weights).groupby(MUNICIPAL_KEYS).weight.sum()
                    require(np.allclose(check,1.),'El peso municipal no suma uno.')
                identifier='sensitivity/'+scenario+'/'+row.model_id
                model,arrays,details=self.fit(identifier,values[mask],row.algorithm,row.k,17,
                    weights=None if sample_weights is None else sample_weights[mask],gmm_reg=1e-4 if scenario=='regularization_x10' else None)
                predicted=model.predict(values);aligned,_=aligned_labels(reference,predicted)
                diagnostics=partition_diagnostics(main,values,predicted,slices)
                record=dict(model_id=row.model_id,scenario=scenario,algorithm=row.algorithm,representation=row.representation,k=row.k,
                    training_segments=int(mask.sum()),training_municipalities=len(main.loc[mask,MUNICIPAL_KEYS].drop_duplicates()),
                    training_LN=int(main.loc[mask,'LN'].sum()),training_nominal_fraction=float(main.loc[mask,'LN'].sum()/NATIONAL_LN),
                    ari_all=float(adjusted_rand_score(reference,predicted)),ari_common_training=float(adjusted_rand_score(reference[mask],predicted[mask])),
                    aligned_change_fraction=float(np.mean(aligned!=reference)),converged=details['converged'],**diagnostics)
                if row.algorithm=='gmm':record.update(posterior_summary(model.predict_proba(values)))
                records.append(record)
                a=main[['row_id',*SEGMENT_KEYS]].copy();a['is_training']=mask;a['is_projection']=~mask;a['label']=predicted;a['aligned_label']=aligned
                paths.append(self.table('sensitivity/'+scenario+'/'+row.representation+'_'+row.algorithm+'_assignments.parquet',a))
                paths.extend(self.bundle_paths([identifier]))
            for source,part in [('male',main.SEXO.eq('0')),('female',main.SEXO.eq('1'))]:
                labels=reference[part];population_rows.append(dict(model_id=row.model_id,scope=source,segments=int(part.sum()),LN=int(main.loc[part,'LN'].sum()),
                    mean_delta=float(main.loc[part,'relative_turnout'].mean()),groups=len(np.unique(labels)),
                    near_rule_boundary_fraction=float(main.loc[part,'relative_turnout'].abs().le(.02).mean())))
        paths += [self.table('metadata/sensitivity.csv',pd.DataFrame(records)),self.table('metadata/sex_diagnostics.csv',pd.DataFrame(population_rows))]
        # Los anteriores B y las reglas se evalúan en las MISMAS filas comunes.
        previous=pd.read_parquet(self.root/'data/processed/demographic_pilot/contexts/broad_standard_joint_main/labels.parquet')
        previous=main[['row_id']].merge(previous,on='row_id',validate='one_to_one',sort=False)
        reference_rows=[];reference_descriptions=[]
        values=main.relative_turnout.to_numpy()[:,None]
        for name,labels in [('six_rules',pd.factorize(main.candidate_id,sort=True)[0])]+[(f'previous_B_k{k}',previous[f'k{k:02d}_seed17'].to_numpy(int)) for k in [4,5,6]]:
            reference_rows.append(dict(reference=name,n=len(main),**partition_diagnostics(main,values,labels,{'P':(0,1)})))
            reference_descriptions.append(describe(main,labels,name)['cluster_profiles'])
        paths.append(self.table('metadata/reference_comparison.csv',pd.DataFrame(reference_rows)))
        paths.append(self.table('metadata/reference_cluster_profiles.parquet',pd.concat(reference_descriptions,ignore_index=True)))
        paths.append(self.table('reference/previous_B_common.parquet',previous))
        self.checkpoint('F',paths,started,'Sensibilidad limitada de NS/secciones/pesos; GMM sin pesos de observación; controles B y seis reglas sobre el mismo universo.')

    def combined(self,name):
        paths=[self.output/f'metadata/{prefix}_{name}.parquet' for prefix in ['principal','contextual']]
        return pd.concat([pd.read_parquet(p) for p in paths if p.exists()],ignore_index=True)

    def make_charts(self,metrics,best,main):
        """Diagnósticos completos; las proyecciones no prueban separación global."""
        self.charts.mkdir(parents=True,exist_ok=True)
        plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False})
        names=[name for name,spec in self.representations().items() if spec['training_allowed']]
        colors=dict(zip(names,plt.cm.tab10(np.linspace(0,.9,len(names)))))
        selected=json.loads((self.output/'metadata/selected_configurations.json').read_text(encoding='utf8'))['model_ids']
        profiles=self.combined('cluster_profiles');curves=self.combined('cluster_curves')
        coverage=pd.read_csv(self.output/'diagnostics/coverage.csv')
        contextual_coverage=self.output/'diagnostics/contextual_coverage.csv'
        if contextual_coverage.exists():coverage=pd.concat([coverage,pd.read_csv(contextual_coverage)],ignore_index=True)
        raw_columns=[c for block in BLOCKS.values() for c in block]
        corr=main[raw_columns].corr().to_numpy()
        fig,ax=plt.subplots(figsize=(9,7),layout='constrained');im=ax.imshow(corr,vmin=-1,vmax=1,cmap='RdBu_r')
        ax.set_xticks(range(len(raw_columns)),raw_columns,rotation=60,ha='right');ax.set_yticks(range(len(raw_columns)),raw_columns)
        for a in range(len(raw_columns)):
            for b in range(len(raw_columns)):ax.text(b,a,f'{corr[a,b]:.2f}',ha='center',va='center',fontsize=7)
        fig.colorbar(im,ax=ax,label='Pearson, población común');ax.set_title('Correlaciones; no prueban independencia ni causalidad')
        save_figure(fig,self.charts/'feature_correlations.png')
        fig,axes=plt.subplots(1,3,figsize=(12,4),layout='constrained')
        for ax,column,title in zip(axes,['segments','municipalities','nominal_fraction'],['Segmentos naturales','Municipios naturales','Fracción LN nacional']):
            ax.bar(coverage.representation,coverage[column],color='#427b8a');ax.tick_params(axis='x',rotation=25);ax.set_title(title)
            if column=='nominal_fraction':ax.yaxis.set_major_formatter(PercentFormatter(1));ax.set_ylim(.99,1)
        fig.suptitle('Cobertura natural por bloques y población común efectiva')
        save_figure(fig,self.charts/'representation_coverage.png')
        average=metrics.groupby(['representation','algorithm','k'],as_index=False).mean(numeric_only=True)
        fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
        fields=[('within_age_sex_rate_r2','R² tasa dentro de edad/sexo'),('shape_r2','Media R² de dos contrastes de forma'),
                ('sex_gap_r2','R² brecha ajustada'),('age_band_purity','Pureza por intervalo predefinido')]
        for ax,(field,title) in zip(axes.flat,fields):
            for name in names:
                g=average[average.representation.eq(name)&average.algorithm.eq('kmeans')]
                ax.plot(g.k,g[field],marker='o',label=name,color=colors[name])
            ax.set(title=title,xlabel='K (6 es sensibilidad)',xticks=range(2,7));ax.yaxis.set_major_formatter(PercentFormatter(1))
        axes[0,0].legend(ncols=3);fig.suptitle('K-Means: contrapartidas electorales, misma población')
        save_figure(fig,self.charts/'representation_comparison.png')
        fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
        for ax,field,title in zip(axes,['silhouette','db'],['Silhouette aproximado (anclas comunes)','Davies–Bouldin sobre todos los segmentos']):
            for name in names:
                for algorithm,style in [('kmeans','-'),('gmm','--')]:
                    g=average[average.representation.eq(name)&average.algorithm.eq(algorithm)]
                    ax.plot(g.k,g[field],style,marker='.',color=colors[name],label=name+' '+algorithm)
            ax.set(title=title,xlabel='K / componentes',xticks=range(1,7))
        axes[1].legend(ncols=2,fontsize=6);fig.suptitle('Índices en geometrías propias; no clasificación universal de calidad')
        save_figure(fig,self.charts/'algorithm_comparison.png')
        fig,ax=plt.subplots(figsize=(10,4.6),layout='constrained');bottom=np.zeros(len(names))
        k4=average[average.algorithm.eq('kmeans')&average.k.eq(4)].set_index('representation').reindex(names)
        for block in BLOCKS:
            values=k4['separation_'+block].fillna(0).to_numpy();ax.bar(names,values,bottom=bottom,label=block);bottom+=values
        ax.yaxis.set_major_formatter(PercentFormatter(1));ax.legend(ncols=5);ax.set(title='Contribución a separación entre clusters · K-Means K=4',ylabel='Fracción de suma de cuadrados entre grupos')
        save_figure(fig,self.charts/'block_contributions.png')
        chosen_k4=best[best.algorithm.eq('kmeans')&best.k.eq(4)].set_index('representation')
        for composition,title,file in [('age_composition','Edad: composición por cluster','age_composition.png'),('sex_composition','Sexo: composición por cluster','sex_composition.png')]:
            frame=self.combined(composition);fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
            for ax,name in zip(axes.flat,names):
                identifier=chosen_k4.loc[name,'model_id'];part=frame[frame.model_id.eq(identifier)]
                table=part.pivot(index='cluster',columns='category',values='segments').fillna(0)
                table=table.div(table.sum(axis=1),axis=0)
                table.plot.bar(stacked=True,ax=ax,rot=0,legend=False);ax.set_title(name+' · K=4');ax.set_xlabel('Etiqueta local');ax.yaxis.set_major_formatter(PercentFormatter(1))
                if ax is axes.flat[0]:ax.legend(title='Intervalo' if composition=='age_composition' else 'SEXO: 0 H / 1 M',fontsize=6)
            for ax in list(axes.flat)[len(names):]:ax.set_visible(False)
            fig.suptitle(title+' · misma población, sin categorías como magnitudes')
            save_figure(fig,self.charts/file)
        fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
        for ax,name in zip(axes.flat,names):
            g=profiles[profiles.model_id.eq(chosen_k4.loc[name,'model_id'])]
            ax.plot(g.cluster,g.participation_observed,'o-',label='ΣSV/Σden')
            ax.plot(g.cluster,g.matched_peer_reference,'s--',label='Referencia mezcla local')
            ax.set(title=name+' · K=4',xlabel='Etiqueta local',ylabel='Participación');ax.yaxis.set_major_formatter(PercentFormatter(1))
            ax.set_ylim(.2,1);ax.legend(fontsize=6)
        for ax in list(axes.flat)[len(names):]:ax.set_visible(False)
        fig.suptitle('Participación absoluta y referencia; la diferencia da el nivel relativo agregado')
        save_figure(fig,self.charts/'participation_levels.png')
        fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
        for ax,name in zip(axes.flat,names):
            g=curves[curves.model_id.eq(chosen_k4.loc[name,'model_id'])]
            for label,part in g.groupby('cluster'):
                part=part.set_index('age_band').reindex(BANDS);ax.plot(BANDS,part.mean_shape_unique*100,'o-',label=str(label))
            ax.axhline(0,color='black',lw=.6);ax.set(title=name+' · K=4',ylabel='Forma centrada (pp)');ax.legend(title='Etiqueta',ncols=4,fontsize=6)
        for ax in list(axes.flat)[len(names):]:ax.set_visible(False)
        fig.suptitle('Curvas descriptivas: peso uno por municipio/sexo único dentro del cluster\nUn mismo patrón puede aportar segmentos a varios clusters')
        save_figure(fig,self.charts/'age_pattern_curves.png')
        fig,axes=plt.subplots(2,len(selected),figsize=(5*len(selected),7),squeeze=False,layout='constrained')
        for column,identifier in enumerate(selected):
            g=curves[curves.model_id.eq(identifier)]
            for label,part in g.groupby('cluster'):
                part=part.set_index('age_band').reindex(BANDS)
                axes[0,column].plot(BANDS,part.mean_delta_unique*100,'o-',label=str(label))
                axes[1,column].plot(BANDS,part.mean_shape_unique*100,'o-',label=str(label))
            for ax in axes[:,column]:ax.axhline(0,color='black',lw=.6);ax.legend(ncols=5,fontsize=6)
            axes[0,column].set(title=identifier,ylabel='Diferencia nacional (pp)')
            axes[1,column].set(ylabel='Forma centrada (pp)')
        fig.suptitle('Candidatos de estabilidad: medias de patrones únicos por municipio/sexo\nLa misma propiedad compartida puede aparecer en varios clusters; curvas no individuales')
        save_figure(fig,self.charts/'selected_candidate_curves.png')
        fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
        for ax,name in zip(axes.flat,names):
            labels=self.load_arrays(chosen_k4.loc[name,'model_id'])['labels'];data=[main.loc[labels==j,'sex_gap_adjusted'].to_numpy()*100 for j in np.unique(labels)]
            ax.boxplot(data,tick_labels=[str(j) for j in np.unique(labels)],showfliers=False);ax.axhline(0,color='black',lw=.6)
            ax.set(title=name+' · K=4',xlabel='Etiqueta local',ylabel='Brecha ajustada M−H (pp)')
        for ax in list(axes.flat)[len(names):]:ax.set_visible(False)
        fig.suptitle('Distribución de brechas compartidas por municipio/edad; no contraste individual')
        save_figure(fig,self.charts/'sex_gap_distributions.png')
        augmented=selected[1];labels=self.load_arrays(augmented)['labels']
        states=self.combined('state_composition');part=states[states.model_id.eq(augmented)]
        table=part.pivot(index='category',columns='cluster',values='segments').fillna(0)
        table=table.div(table.sum(axis=1),axis=0);state_names=main[['EDOCVE','state_name_label']].drop_duplicates().set_index('EDOCVE').state_name_label
        fig,ax=plt.subplots(figsize=(8,11),layout='constrained');im=ax.imshow(table.to_numpy(),aspect='auto',vmin=0,vmax=1,cmap='Blues')
        ax.set_yticks(range(len(table)),[state_names.get(str(c),str(c)) for c in table.index]);ax.set_xticks(range(len(table.columns)),table.columns)
        ax.set(title=augmented+'\nDistribución de segmentos dentro de cada entidad',xlabel='Etiqueta local');fig.colorbar(im,ax=ax,label='Proporción estatal de segmentos')
        save_figure(fig,self.charts/'territorial_distribution.png')
        fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
        for ax,name in zip(axes.flat,names):
            row=best[best.representation.eq(name)&best.algorithm.eq('gmm')].sort_values('objective').iloc[0]
            p=self.load_arrays(row.model_id)['posterior'];ax.hist(p.max(axis=1),bins=np.linspace(0,1,31),color=colors[name])
            ax.axvline(.8,color='black',ls='--');ax.set(title=name+f' · GMM BIC mínimo K={row.k}',xlabel='Posterior máxima',ylabel='Segmentos')
        for ax in list(axes.flat)[len(names):]:ax.set_visible(False)
        fig.suptitle('Incertidumbre condicional a cada mezcla; componentes no son clases naturales\nBIC se minimiza sólo dentro de cada representación')
        save_figure(fig,self.charts/'gmm_uncertainty.png')
        fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
        for ax,name in zip(axes.flat,names):
            _,x,_,_=self.main_matrix(name);labels=self.load_arrays(chosen_k4.loc[name,'model_id'])['labels']
            if x.shape[1]==1:
                for label in np.unique(labels):ax.hist(x[labels==label,0],bins=35,histtype='step',label=str(label))
                ax.set(title=name+' · representación 1D completa',xlabel='P estandarizado',ylabel='Segmentos')
            else:
                sample=np.random.default_rng(17).choice(len(x),size=min(8000,len(x)),replace=False)
                ax.scatter(x[sample,0],x[sample,1],c=labels[sample],s=2,alpha=.25,cmap='tab10',rasterized=True)
                ax.set(title=name+(' · proyección 2D de '+str(x.shape[1])+' coordenadas' if x.shape[1]>2 else ' · dos coordenadas completas'),
                    xlabel='P centrado/escalado/ponderado',ylabel='Primera coordenada del segundo bloque')
        for ax in list(axes.flat)[len(names):]:ax.set_visible(False)
        fig.suptitle('Vistas de K=4: coincidencia en proyección no prueba superposición global')
        save_figure(fig,self.charts/'feature_space_projections.png')
        stability=pd.read_csv(self.output/'metadata/municipal_stability.csv');sampling=pd.read_csv(self.output/'metadata/resampling_coverage.csv')
        fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
        axes[0].boxplot([stability.loc[stability.model_id.eq(m),'ari_oob'] for m in selected],tick_labels=[m.replace('/','\n') for m in selected],showfliers=True)
        axes[0].set(title='ARI OOB municipal',ylim=(0,1.02),ylabel='Concordancia con solución completa')
        axes[1].plot(sampling['sample'],sampling.training_fraction_eligible_LN,'o-');axes[1].set(title='Cobertura in-bag de LN elegible',xlabel='Submuestra',ylabel='Fracción del LN común');axes[1].yaxis.set_major_formatter(PercentFormatter(1))
        fig.suptitle('Diez submuestras son un diagnóstico exploratorio; se muestran peores casos')
        save_figure(fig,self.charts/'municipal_stability.png')
        fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
        for ax,identifier in zip(axes,[selected[0],selected[1]]):
            labels=self.load_arrays(identifier)['labels'];table=pd.crosstab(main.candidate_id,labels,normalize='index')
            im=ax.imshow(table,aspect='auto',vmin=0,vmax=1,cmap='viridis');ax.set_yticks(range(len(table)),table.index)
            ax.set_xticks(range(len(table.columns)),table.columns);ax.set(title=identifier,xlabel='Etiqueta local')
        fig.colorbar(im,ax=list(axes),label='Proporción dentro de cada regla');fig.suptitle('Seis reglas frente a clusters: concordancia, no exactitud')
        save_figure(fig,self.charts/'rules_comparison.png')
        sensitivity_path=self.output/'diagnostics/sensitivity_same_seed.csv'
        sensitivity=pd.read_csv(sensitivity_path if sensitivity_path.exists() else self.output/'metadata/sensitivity.csv');fig,ax=plt.subplots(figsize=(11,5),layout='constrained')
        for i,identifier in enumerate(selected):
            g=sensitivity[sensitivity.model_id.eq(identifier)];ax.plot(g.scenario,g.ari_all,'o-',label=identifier)
        ax.legend(fontsize=7);ax.tick_params(axis='x',rotation=20);ax.set(ylim=(0,1.02),ylabel='ARI sobre toda la población común',title='Sensibilidades: no sustituyen el principal ni modifican fuentes')
        save_figure(fig,self.charts/'sensitivity_comparison.png')
        fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
        for ax,name in zip(axes.flat,names):
            g=average[average.representation.eq(name)&average.algorithm.eq('gmm')]
            ax.plot(g.k,g.bic-g.bic.min(),'o-',label='ΔBIC propio');ax.plot(g.k,g.aic-g.aic.min(),'s--',label='ΔAIC propio')
            ax.set(title=name,xlabel='Componentes',ylabel='Diferencia respecto a mínimo propio');ax.legend(fontsize=6)
        for ax in list(axes.flat)[len(names):]:ax.set_visible(False)
        fig.suptitle('Criterios de mezcla: no comparar BIC/AIC como ranking entre geometrías')
        save_figure(fig,self.charts/'gmm_component_criteria.png')

    def write_report(self,metrics,best,full,main):
        """Construye el informe desde resultados, sin conclusiones prefijadas por K."""
        def read(relative):return pd.read_csv(self.output/relative)
        def image(name,title):
            relative=Path(os.path.relpath(self.charts/name,self.report.parent)).as_posix()
            return f'![{title}]({relative})'
        coverage=read('diagnostics/coverage.csv');availability=read('diagnostics/block_availability.csv')
        if (self.output/'diagnostics/contextual_coverage.csv').exists():coverage=pd.concat([coverage,read('diagnostics/contextual_coverage.csv')],ignore_index=True)
        distributions=read('diagnostics/distributions.csv');rank=read('diagnostics/matrix_rank.csv');context=read('diagnostics/context_audit.csv')
        decision=json.loads((self.output/'metadata/context_decision.json').read_text(encoding='utf8'))
        selection=json.loads((self.output/'metadata/selected_configurations.json').read_text(encoding='utf8'))
        selected=selection['model_ids'];stability=read('metadata/municipal_stability.csv');sampling=read('metadata/resampling_coverage.csv')
        sensitivity=read('metadata/sensitivity.csv');references=read('metadata/reference_comparison.csv')
        seed_frames=[read(f'metadata/{p}_seed_stability.csv') for p in ['principal','contextual'] if (self.output/f'metadata/{p}_seed_stability.csv').exists()]
        seeds=pd.concat(seed_frames,ignore_index=True)
        average=metrics.groupby(['representation','algorithm','k'],as_index=False).mean(numeric_only=True)
        k4=average[average.algorithm.eq('kmeans')&average.k.eq(4)].copy()
        baseline=k4[k4.representation.eq('F0')].iloc[0]
        state_coverage=read('diagnostics/state_coverage_common_eligible.csv').sort_values('nominal_fraction').head(8)
        stable_rows=[]
        for identifier,g in stability.groupby('model_id',observed=True):
            stable_rows.append(dict(model_id=identifier,samples=len(g),ari_oob_median=g.ari_oob.median(),ari_oob_q10=g.ari_oob.quantile(.1),
                ari_oob_min=g.ari_oob.min(),samples_below_90=int(g.ari_oob.lt(.9).sum()),
                aligned_oob_change_max=g.aligned_oob_change_fraction.max()))
        stable=pd.DataFrame(stable_rows)
        gmm=[]
        for name in self.representations():
            candidates=best[best.representation.eq(name)&best.algorithm.eq('gmm')]
            if candidates.empty:continue
            row=candidates.sort_values('objective').iloc[0];m=metrics[metrics.model_id.eq(row.model_id)].iloc[0]
            gmm.append(dict(representation=name,k=int(row.k),bic=m.bic,aic=m.aic,ambiguous_80=m.ambiguous_80,
                mean_max_posterior=m.mean_max_posterior,normalized_entropy=m.mean_normalized_entropy,
                covariance_condition=m.maximum_covariance_condition,regularization_touched_components=int(m.regularization_touched_components)))
        gmm=pd.DataFrame(gmm)
        final=[]
        for row in k4.itertuples():
            matched=best[best.representation.eq(row.representation)&best.algorithm.eq('kmeans')&best.k.eq(4)].iloc[0]
            minimum=seeds[seeds.representation.eq(row.representation)&seeds.algorithm.eq('kmeans')&seeds.k.eq(4)].ari.min()
            final.append(dict(representation=row.representation,comparison_K=4,n=len(main),nominal_fraction=float(main.LN.sum()/NATIONAL_LN),
                within_age_sex_rate_r2=row.within_age_sex_rate_r2,delta_vs_F0=row.within_age_sex_rate_r2-baseline.within_age_sex_rate_r2,
                mean_shape_contrast_r2=row.shape_r2,sex_gap_r2=row.sex_gap_r2,municipal_level_r2=row.municipal_level_r2,
                context_r2=row.context_r2,age_band_purity=row.age_band_purity,rules_ari=row.rules_ari,seed_ari_min=minimum))
        reference=references[references.reference.eq('six_rules')].iloc[0]
        final.append(dict(representation='six_rules_descriptive',comparison_K=6,n=len(main),nominal_fraction=float(main.LN.sum()/NATIONAL_LN),
            within_age_sex_rate_r2=reference.within_age_sex_rate_r2,delta_vs_F0=reference.within_age_sex_rate_r2-baseline.within_age_sex_rate_r2,
            mean_shape_contrast_r2=reference.shape_r2,sex_gap_r2=reference.sex_gap_r2,municipal_level_r2=reference.municipal_level_r2,
            context_r2=reference.context_r2,age_band_purity=reference.age_band_purity,rules_ari=1.,seed_ari_min=np.nan))
        final=pd.DataFrame(final);self.table('metadata/final_comparison.csv',final)
        # Diagnóstico de variación total del bloque, distinto de media de R² por contraste.
        total_variance=[]
        for row in best[best.algorithm.eq('kmeans')&best.k.eq(4)].itertuples():
            labels=self.load_arrays(row.model_id)['labels'];zero=np.zeros(len(main),dtype=int)
            total_variance.append(dict(representation=row.representation,k=4,
                shape_total_variance_r2=conditional_fraction(main[BLOCKS['A']],labels,zero),
                context_total_variance_r2=conditional_fraction(main[BLOCKS['T']],labels,zero)))
        self.table('diagnostics/total_block_variance_r2.csv',pd.DataFrame(total_variance))
        profiles=self.combined('cluster_profiles');curves=self.combined('cluster_curves')
        selected_profiles=profiles[profiles.model_id.isin(selected)]
        example=selected_profiles[selected_profiles.model_id.eq(selected[1])].sort_values('mean_sex_gap_adjusted',ascending=False).iloc[0]
        init_summary=metrics[metrics.algorithm.eq('kmeans')].groupby(['representation','k'],as_index=False).agg(
            worst_initialization_ari=('minimum_initialization_ari','min'),maximum_best_iterations=('iterations','max'),all_best_converged=('converged','all'))
        near=main.relative_turnout.abs().le(.02)
        selected_models=best[best.model_id.isin(selected)]
        separation=metrics[metrics.model_id.isin(selected)][['model_id','separation_P','separation_A','separation_S','separation_M','separation_T']]
        sensitivity_summary=sensitivity[['model_id','scenario','training_segments','training_municipalities','training_nominal_fraction','ari_all','ari_common_training','aligned_change_fraction']]
        matched_path=self.output/'diagnostics/sensitivity_same_seed.csv'
        if matched_path.exists():
            matched=read('diagnostics/sensitivity_same_seed.csv')
            sensitivity_summary=sensitivity_summary.drop(columns=['ari_all','ari_common_training','aligned_change_fraction']).merge(
                matched[['model_id','scenario','baseline_same_seed','ari_all','ari_common_training','aligned_change_fraction']],on=['model_id','scenario'],validate='one_to_one')
        main_count=int(metrics.shape[0]);sample_count=len(stability);sens_count=len(sensitivity)
        shapes='; '.join(f"{r.representation}: forma {r.shape_r2:.1%}, brecha {r.sex_gap_r2:.1%}, tasa condicional {r.within_age_sex_rate_r2:.1%}" for r in k4.itertuples())
        worst=stable.sort_values('ari_oob_min').iloc[0]
        contextual_gmm=metrics[metrics.representation.eq('F4T')&metrics.algorithm.eq('gmm')].sort_values('bic')
        special_text='No se ejecutó F4T GMM.'
        if len(contextual_gmm):
            special=contextual_gmm.iloc[0]
            special_text=(f'**Excepción contextual importante:** `{special.model_id}` tiene sólo {special.ambiguous_80:.2%} de asignaciones ambiguas, '
                f'pero T aporta {special.separation_T:.2%} de la separación; la tasa condicional explicada es apenas '
                f'{special.within_age_sex_rate_r2:.2%}, la brecha ajustada {special.sex_gap_r2:.2%} y la pureza municipal '
                f'{special.municipality_label_purity:.2%}. Esta aparente nitidez describe sobre todo composición electoral, no mejores patrones de participación.')
            diagnostic=self.output/'diagnostics/contextual_gmm_regularization.json'
            if diagnostic.exists():
                numerical=json.loads(diagnostic.read_text(encoding='utf8'))
                special_text+=(f' Hay {numerical["context_boundary_segments"]:,} segmentos en bordes del simplex y '
                    f'{numerical["pure_context_segments"]:,} con un único tipo de sección. {int(special.regularization_touched_components)} componentes del ajuste principal '
                    f'tocan el piso de regularización. El control acotado reg_covar=10⁻⁴ da ARI={numerical["ari"]:.4f}, '
                    f'ambigüedad={numerical["sensitivity_ambiguous_80"]:.2%} y BIC={numerical["sensitivity_bic"]:.2f}, '
                    f'frente a BIC={numerical["main_bic"]:.2f} con 10⁻⁵. No es otra representación ni una búsqueda de K: '
                    'diagnostica sensibilidad numérica de una mezcla continua sobre composición con masas en sus fronteras. No se promueve esa solución por su posterior más tajante.')
        lines=['# Clustering multidimensional sociodemográfico · B broad 2024','',
            '**Añadir forma por edades y brecha entre sexos produce diferenciación descriptiva adicional, pero no demuestra cuatro a seis clases naturales ni una mejora global sobre F0.** Los bloques cambian lo que se considera cercano. La recomendación es conservar las seis reglas como presentación transparente y usar las ampliaciones como diagnósticos complementarios sujetos a validación electoral, sin publicar nuevos perfiles aprendidos.', '',
            f'Se completaron {main_count} ajustes principales/contextuales, {sample_count} de estabilidad municipal y {sens_count} sensibilidades. Sólo K-Means y GaussianMixture de scikit-learn; no se ejecutaron Ward, HDBSCAN o K-Medoids. No se exportó a React ni se modificaron fuentes o resultados anteriores.', '',
            '## Población, unidad y recuperación de evidencia','',
            'Unidad: **municipio × sexo × intervalo de edad** (18–34, 35–59, 60–100). No son personas, patrones individuales ni coordenadas geográficas. Se verificaron las ocho rutas de informes solicitados, contratos, hashes, manifiestos y _SUCCESS de las fuentes antes de construir matrices. Se reutilizan profile_candidates_review, cluster_features, contextual_feature_review, participation_pattern_review y demographic_pilot; no se releen CSV ni registros históricos.', '',
            'El entorno .venv_pattern_algorithms tiene Python 3.13 y bibliotecas importables; pip check no encontró dependencias rotas. Versiones y diagnóstico inicial del repositorio están en metadata/repository_diagnosis.json. No se instalaron paquetes. La consulta inicial no detectó procesos Python activos; un lock exclusivo impide duplicar este experimento.', '',
            table_text(coverage),'',
            f'Base validada: **14,190 segmentos, 2,402 municipios, LN=98,203,780 (99.8713 %)**. La comparación común usa **{len(main):,} segmentos, {len(main[MUNICIPAL_KEYS].drop_duplicates()):,} municipios y LN={int(main.LN.sum()):,} ({main.LN.sum()/NATIONAL_LN:.4%})**. A pierde 246 segmentos de la base por no disponer de las tres edades con soporte; S pierde 64 por falta de soporte de ambos sexos. La intersección pierde 282 segmentos; los motivos se superponen. Ningún índice se atribuye al bloque por cambiar esa población.', '',
            'Se mantienen LN≥100, SV+NV≥100, filas fuente≥5, H/M, edad de núcleo y tasa definida. NS≥10 % es advertencia, no filtro principal. Filas fuente no son secciones distintas ni observaciones independientes. reference/ conserva las 17,735 filas B, 9,773,730 filas fuente, LN=98,330,348 y 105 filas/LN de SEXO=2; 101+ y categorías complementarias conservan estados y etiquetas NULL. La referencia exacta anterior permanece intacta y trazable.', '',
            table_text(availability),'',image('representation_coverage.png','Cobertura natural y común'),'','Entidades con menor cobertura nominal común:', '',
            table_text(state_coverage[['EDOCVE','state_name_label','segments','eligible_segments','eligible_municipalities','nominal_fraction']]),'',
            '## Características y significado electoral','',
            '| Bloque | Definición | Alcance y dependencia |','| --- | --- | --- |',
            '| P | d = SV/(SV+NV) − r nacional del mismo intervalo/sexo. | Referencia de todos los conteos H/M de esas edades antes de soporte; no promedio municipal. |',
            '| A | q₁=(d₁−d₂)/√2; q₂=(d₁+d₂−2d₃)/√6. | Forma de tres edades centrada; exige las tres tasas con soporte y reproduce R2 previo. Hasta tres segmentos comparten q. |',
            '| S | d_mujeres−d_hombres; brecha observada también conservada como metadato. | Dirección fija, soporte de ambos sexos. Hasta dos segmentos del mismo municipio/edad comparten brecha; no es propiedad individual. |',
            '| M | Tasa municipal H/M 18–100 menos referencia nacional ajustada por sus denominadores edad/sexo. | Promedio ponderado de d de todas sus celdas antes del soporte. La tasa municipal de todas las edades/sexos queda sólo como metadato. Hasta seis filas comparten M. |',
            '| T | pQ, p=(LN_U,LN_R,LN_M)/LN y Q base ortonormal de contrastes. | Dos coordenadas del simplex. Conserva exactamente distancia euclídea entre composiciones; no es lograzón/Aitchison ni codificación ordinal. Ceros conservados sin pseudoconteos. |','',
            'A, S y M reexpresan los mismos conteos electorales en contextos compartidos; no son tres fuentes independientes. Su información adicional se evalúa respecto al vector P por segmento, no como datos individuales nuevos. La igualdad P=m+forma_de_su_banda permite reconstruir el nivel por municipio/sexo con la edad como metadato. M recupera un resumen territorial ya contenido en todas las celdas. No se añaden edad media, sexo, identidad municipal, estado ni distrito a la distancia.', '',
            'Las tres proporciones de T suman uno; pQ elimina la dirección constante sin duplicarla. Se adopta explícitamente geometría euclídea sobre composiciones cerradas porque admite ceros y es contrastable con el antecedente contextual. No se afirma invariancia de Aitchison ni equivalencia con la geometría Hellinger anterior. TIPOSEC identifica contexto de sección electoral, no residencia individual.', '',
            '## Auditoría previa, redundancia y ponderación de bloques','',
            table_text(rank),'',table_text(distributions[['block','feature','sd','q1','median','q3','residual_fraction_other_blocks']]),'',
            'No hay dependencia lineal exacta en F0–F3 ni en el conjunto diagnóstico. La regresión OLS sobre otras columnas cuantifica reconstrucción lineal in-sample; no prueba independencia, novedad causal ni capacidad predictiva. Las dependencias condicionadas a edad/sexo/municipio siguen existiendo aunque el rango global sea completo.', '',
            image('feature_correlations.png','Correlaciones y redundancias'),'','Para cada bloque b: z_b=(x_b−media_b)/RMS_b, donde RMS_b²=media(Σ_j(x_bj−media_bj)²). La matriz concatena √w_b z_b; por tanto d²=Σ_b w_b d_b² y cada bloque aporta varianza total w_b, independientemente de tener una o dos columnas. No se blanquean contrastes ni se normaliza la amplitud de cada fila. Inicialmente w_b=1/n_bloques.', '',
            'Parámetros ajustados sólo sobre la población común principal; en remuestras se reajustan sólo con municipios in-bag. La sensibilidad P-heavy duplica el peso de P respecto a cada otro bloque, antes de renormalizar. Es una sensibilidad predefinida pequeña, no pesos elegidos para maximizar Silhouette. Los controles NS/secciones/peso municipal mantienen las escalas principales, aislando el cambio de entrenamiento u objetivo.', '',
            'La repetición de A/S/M puede orientar la geometría hacia territorios. El peso inicial es uno por segmento; no se finge independencia de esas propiedades compartidas. El peso total uno por municipio cambia el objetivo y se prueba sólo en K-Means, sin repetir filas para simular pesos en GMM.', '',
            '## F0–F3 y decisión contextual F4','',
            'F0=P (control unidimensional), F1=P+A, F2=P+S y F3=P+A+S. Cobertura natural y común se guardan por separado; todos los ajustes de comparación usan las mismas filas y orden. Una representación inválida por rango/condición se bloquearía antes de entrenar.', '',
            f'F4 parte de **{decision["base"]}** bajo el criterio operativo registrado: {decision["reason"]} No es una selección definitiva ni demuestra que esa representación sea universalmente mejor. Se auditan M y T por separado; se exige al menos 5 % de variación residual lineal frente a los bloques base, rango completo y condición <10⁶, además de cobertura común ya aprobada.', '',
            table_text(context),'',
            'M y T no se introducen juntos. F4M añade nivel territorial; F4T añade composición electoral. El residual puede ser relevante para geometría y aun así no mejorar perfiles de participación. El umbral 5 % es una alerta exploratoria predefinida, no una prueba estadística.', '',
            '## Algoritmos, métricas y trazabilidad','',
            'K-Means: K=2–6 (6 sensibilidad), semillas 17/42/2024, diez arranques k-means++ explícitos por semilla, máximo 1,000 iteraciones y tol=0 para estabilizar etiquetas. Se guardan etiquetas/SSE/iteraciones de cada arranque y ARI contra el mejor; cada ajuste elige su SSE mínima. Las mismas semillas no garantizan los mismos índices iniciales entre geometrías. Centroides y SSE se recomputan desde asignaciones y pesos. [Implementación primaria KMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html).', '',
            f'Convergieron **{int(metrics.converged.sum())}/{len(metrics)}** ajustes principales/contextuales. La estabilidad de la mejor solución entre semillas no significa que todos los arranques converjan a la misma partición. Peores ARI de arranque frente al mejor, en K=4:', '',
            table_text(init_summary[init_summary.k.eq(4)]),'',
            'GMM: 1–6 componentes, covarianza completa, cinco inicializaciones, tres semillas, máximo 1,000 iteraciones, tol=10⁻⁴ y reg_covar=10⁻⁵. Se guardan posteriores por segmento, AIC/BIC, convergencia, entropía, fracción max posterior<0.8, autovalores y condición de cada covarianza. La regularización no es imputación. El control ×10 evalúa sensibilidad a esa elección. Los componentes pueden aproximar una densidad continua y no son clases naturales. [Documentación primaria de mezclas](https://scikit-learn.org/stable/modules/mixture.html).', '',
            'AIC/BIC se comparan únicamente dentro de cada representación y población, no entre espacios de dimensiones/escalas distintas. Sus supuestos de observaciones independientes son aproximados por propiedades compartidas dentro del municipio; aquí son criterios descriptivos de ajuste de mezclas, no evidencia formal de tipos ciudadanos.', '',
            f'Silhouette usa {self.anchors} anclas uniformes compartidas contra toda la población común, distancias por bloques de 16×N y error Monte Carlo con corrección finita. No hay matriz N×N. DB se calcula sobre todos los segmentos. Con una única etiqueta efectiva Silhouette/DB quedan NULL. Las métricas usuales se mantienen no ponderadas incluso cuando el entrenamiento utiliza pesos. [Definición primaria de Silhouette](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html).', '',
            'SSE y métricas internas de geometrías diferentes no constituyen ranking universal. Los indicadores de participación son descriptivos in-sample; diferencias inducidas por incluir A, S o T no prueban descubrimiento ni generalización.', '',
            '## Comparación electoral y nuevos patrones','',
            'Lectura controlada K=4, media de tres semillas (se muestran todos los K en CSV y gráficas): '+shapes+'.','',
            image('representation_comparison.png','Comparación electoral F0 a F4'),'',
            'R² dentro de edad/sexo compara residuo de tasas antes/después de añadir etiquetas a esas celdas. `shape_r2` y `context_r2` son medias de R² de sus dos contrastes fijos, **no** fracciones de varianza total del bloque ni medidas invariantes a rotación. Se conserva además diagnostics/total_block_variance_r2.csv, que suma cuadrados de ambos contrastes para describir la varianza total sobre los mejores ajustes K=4. Las contribuciones entre grupos usan siempre la suma de cuadrados total del bloque.', '',
            image('block_contributions.png','Contribución de cada bloque a separación'),'',table_text(separation),'',
            'Una contribución mayor de A/S/M/T confirma qué objetivo separa el modelo; no es importancia causal. F0 sólo ordena niveles relativos. F1 puede dividir formas, F2 brechas agregadas y F3 combina objetivos, con posible pérdida de separación de P. F4M favorece nivel municipal y F4T contexto U/R/M. La pureza municipal permite detectar cuándo muchos segmentos del mismo territorio reciben la misma etiqueta aunque su código no entre en la matriz.', '',
            image('algorithm_comparison.png','Comparación de algoritmos'),'',image('feature_space_projections.png','Vistas de coordenadas y proyecciones'),'',
            'No hay edad media en estas distancias, por lo que las cinco franjas inducidas por esa coordenada no se reproducen por construcción. La asociación con bandas puede persistir por patrones de tasas, brechas y forma. La pureza por edad es un diagnóstico de esa asociación; no se confunde con efecto causal ni con edad individual. Coincidir en una proyección bidimensional no prueba superposición en todo el espacio.', '',
            image('age_composition.png','Distribución de edades'),'',image('sex_composition.png','Distribución de sexo'),'',
            image('participation_levels.png','Participación absoluta y referencia'),'',image('age_pattern_curves.png','Curvas de forma por edad'),'',
            'Las curvas emplean un municipio/sexo único dentro de cada cluster. El mismo municipio/sexo puede aportar edades a varios clusters: no sumar sus frecuencias como patrones independientes. Se guardan también medias ponderadas por número de segmentos para mostrar el efecto de repetir propiedades compartidas. La participación agregada utiliza ΣSV/Σden, y la referencia del grupo ajusta mezcla local de edad/sexo. La media simple de diferencias es otra medida; no intercambiar denominadores.', '',
            'Perfiles descriptivos de las tres configuraciones enviadas a estabilidad, con etiquetas locales:', '',
            table_text(selected_profiles[['model_id','cluster','segments','municipalities','participation_observed','mean_relative_turnout','mean_sex_gap_adjusted','women_fraction','unspecified_rate','near_rule_boundary_fraction']]),'',
            f'Una combinación transversal concreta en `{selected[1]}`, etiqueta local {int(example.cluster)}, reúne **{int(example.segments):,} segmentos de {int(example.municipalities):,} municipios**: diferencia media frente a pares {example.mean_relative_turnout*100:+.2f} pp y brecha media ajustada mujeres−hombres **{example.mean_sex_gap_adjusted*100:+.2f} pp**, con {example.women_fraction:.2%} de segmentos de mujeres. Esa relación entre participación y brecha no está codificada en edad×signo. Es un hallazgo descriptivo de los conteos, no motivación individual, clase natural ni perfil validado; las sensibilidades y colas OOB impiden promoverlo automáticamente.', '',
            image('selected_candidate_curves.png','Curvas de las configuraciones sometidas a estabilidad'),'',
            image('sex_gap_distributions.png','Brechas ajustadas'),'',image('territorial_distribution.png','Distribución territorial'),'',
            'La composición por sexo no se incorporó como número. Una agrupación de brechas compartidas describe relaciones entre grupos agregados; no revela decisiones personales. Las diferencias por entidad son diagnósticos de cobertura y concentración, no distancias geográficas ni efectos de residencia.', '',
            '## Mezclas, incertidumbre y número de componentes','',table_text(gmm),'',
            image('gmm_component_criteria.png','Criterios de componentes dentro de cada representación'),'',image('gmm_uncertainty.png','Superposición e incertidumbre GMM'),'',
            f'En las soluciones BIC mínimas propias la fracción ambigua está entre **{gmm.ambiguous_80.min():.2%} y {gmm.ambiguous_80.max():.2%}**. Es incertidumbre condicional a cada mezcla, no probabilidad de que una persona pertenezca a un tipo. Menor ambigüedad en otra geometría no demuestra mayor utilidad electoral. AIC/BIC no se interpretan como prueba de cuatro a seis clases, aunque su mínimo caiga en ese rango.', '',
            special_text,'',
            '## Comparación con seis reglas y antecedentes B','',
            'Las seis reglas combinan edad y signo contra pares. Aquí se conserva su candidato original y se cruzan sólo los mismos segmentos comunes. ARI es concordancia, no precisión; no compara unidades distintas. Las etiquetas numéricas son locales a cada ajuste. Las distribuciones de intensidad, sexo, edad, NS y U/R/M acompañan las contingencias completas.', '',
            image('rules_comparison.png','Reglas frente a clusters'),'',
            'Se reutilizan etiquetas B broad estandarizadas de K4/5/6, semilla 17, sin volver a entrenar. metadata/reference_comparison.csv recalcula sus descriptores sobre la intersección común; no se copian índices de otra cobertura como si fueran comparables. B life_stage queda como antecedente documentado porque sus segmentos no corresponden uno a uno a broad. No se calcula ARI entre esos universos ni con las unidades municipio/sexo de R2.', '',
            table_text(references[['reference','n','age_band_purity','relative_r2','shape_r2','sex_gap_r2','within_age_sex_rate_r2']]),'',
            'Los nuevos clusters pueden atravesar las seis reglas o subdividir intensidades dentro de ellas; eso se cuantifica con contingencias y R² condicional a candidate_id. No significa por sí mismo que los nuevos cortes sean electoralmente útiles. Las reglas siguen siendo más transparentes para comunicar; los bloques adicionales sirven para revisar patrones que la matriz edad×signo no resume.', '',
            '## Estabilidad municipal y peores casos','',
            'Se seleccionaron como máximo tres configuraciones: '+', '.join(selected)+'. La selección excluye K6 y usa ganancia media descriptiva de forma/brecha frente a F0 al mismo K, retención de ≥80 % de separación de tasa condicional, ARI de semillas≥0.90 y grupo mínimo≥2 %. Son puertas exploratorias; si ninguna las supera se conserva la mejor como diagnóstico, sin llamarla validada. La GMM se escoge por BIC dentro de la representación seleccionada, nunca comparando BIC entre geometrías.', '',
            f'Se reutilizan las primeras {self.replicates} submuestras municipales del experimento previo: 1,981 de los 2,477 municipios originales por muestra, sin reemplazo. Todos los segmentos de cada municipio quedan juntos. Escalas reajustadas sólo in-bag; referencias nacionales descriptivas fijas, que incluyen también OOB. Esto no es validación predictiva independiente de todo el proceso nacional ni bootstrap con reemplazo.', '',
            table_text(stable),'',
            f'Peor concordancia OOB observada: **{worst.ari_oob_min:.4f}** en `{worst.model_id}`. Se muestran mediana, q10, mínimo y número de muestras bajo 0.90; una mediana alta no oculta la cola. Diez muestras no son prueba definitiva ni intervalo de confianza.', '',
            table_text(sampling),'',image('municipal_stability.png','Estabilidad y cobertura municipal'),'',
            'ARI se calcula sobre etiquetas sin necesidad de alineación. Para porcentaje de cambios y desplazamientos de perfiles se alinean etiquetas por máximo solapamiento sobre la población común; las asignaciones se distinguen como entrenamiento u OOB. Se conserva alineación, perfil OOB antes/después, todas las etiquetas y escaladores. No se presentan municipios sin características completas como usados en el entrenamiento.', '',
            '## Sensibilidades limitadas','',table_text(sensitivity_summary),'',image('sensitivity_comparison.png','Sensibilidades de los candidatos'),'',
            'NS<10 % es una selección temporal de segmentos, no modificación del principal ni imputación. Filtrar sólo el NS del segmento **no** elimina automáticamente otros NS utilizados en A/S/M; los máximos de NS de sus insumos están conservados para una revisión más estricta. La referencia nacional también permanece fija y puede contener NS. La no especificación no equivale a abstención.', '',
            'El control ≥5 secciones distintas utiliza section_count por segmento; no lo confunde con ≥5 filas fuente. Son filtros temporales de ajuste y las demás filas conservan proyecciones separadas. Cambian cobertura y población; no se atribuyen cambios a causalidad de NS o de tamaño. La cobertura y los row_id exactos de entrenamiento/proyección quedan guardados.', '',
            'Todos los ajustes de sensibilidad usan semilla 17. La tabla y gráfica de esta sección comparan contra el ajuste principal de semilla 17 correspondiente, además de conservar en metadata/sensitivity.csv la comparación contra la mejor solución entre semillas. Así se separa el cambio de semilla de referencia sin repetir ningún ajuste. Igual semilla no garantiza iguales índices k-means++ cuando cambian pesos, población o geometría: son sensibilidades con optimización finita y múltiples arranques, no efectos causales puros de los pesos.', '',
            'Peso municipal=1/n_segmentos_comunes_del_municipio; se comprueba suma uno por municipio. KMeans admite sample_weight. GaussianMixture.fit no admite ese argumento en este entorno, por lo que no se fabrican pesos mediante replicación de filas y esa sensibilidad queda explícitamente no ejecutada para GMM. LN se conserva como diagnóstico, no como coordenada ni ponderación automática.', '',
            '## Tabla final de comparación','',
            'K=4 se usa como corte descriptivo común para leer la tabla, **no** como K elegido. Las seis reglas tienen seis etiquetas por diseño. Las medias de métricas son de tres semillas; las reglas no requieren semillas. Todas las filas evalúan la misma población común. Valores de R² y pureza son proporciones; multiplicar por 100 para porcentajes.', '',
            table_text(final),'',
            '## Conclusiones para ParticipaMX','',
            '1. **Viabilidad:** F0, F1, F2 y F3 tienen rango completo y cobertura común; F4M/F4T quedan sujetos al control contextual registrado y nunca se combinan M+T. Los pendientes originales se conservan.',
            f'2. **Cobertura:** base 14,190/2,402 y comparación 13,908/2,341, con LN={int(main.LN.sum()):,} ({main.LN.sum()/NATIONAL_LN:.4%}). La pérdida territorial se explica por soporte de patrón y par sexual, no se oculta tras LN alto.',
            '3. **Información distinta:** A añade contraste entre edades y S relación de sexos respecto a P por segmento; M añade resumen del territorio y T composición electoral. Todos se derivan de agregados existentes; no son fuentes independientes ni información individual.',
            '4. **Edad:** no entra edad media como coordenada. La pureza por banda puede persistir y debe leerse junto a la intensidad relativa; no se demuestra independencia de edad sólo por retirarla de la matriz.',
            '5. **Más que niveles:** las ampliaciones separan forma/brecha/contexto además de P, pero esos objetivos se introdujeron deliberadamente. Se exige distinguir esa información descriptiva de clases naturales descubiertas.',
            '6. **Riqueza:** existen combinaciones transversales descriptivas de tasas, forma y brecha. Sus curvas y composiciones deben revisarse electoralmente; no basta añadir dimensiones o ver colores separados.',
            '7. **Estabilidad:** la tabla OOB compara sólo los tres candidatos seleccionados; no se atribuye estabilidad municipal a todas las configuraciones. Se conservan mínimos, semillas y sensibilidades.',
            f'8. **GMM:** ambigüedad de {gmm.ambiguous_80.min():.1%}–{gmm.ambiguous_80.max():.1%} en los mínimos BIC propios; la menor es contextual, dominada por T y apoyada en regularización, no evidencia de perfiles de participación superiores. Las demás mezclas siguen muy superpuestas.',
            '9. **Frente a reglas:** los clusters pueden añadir descriptores de intensidad, forma y brecha que las reglas no codifican. Las contingencias/R² condicionales muestran cuánto; mayor complejidad no demuestra que sean mejores para comunicar o intervenir.',
            '10. **Cuatro a seis:** no se obtiene evidencia suficiente de cuatro a seis clases naturales por convergencia, BIC o Silhouette. Se documentan candidatos de densidad/partición, no una tipología validada.',
            '11. **Interpretación:** F0 es el control de nivel relativo; los bloques son útiles si se expone su objetivo. Las seis reglas siguen siendo una matriz comunicable de edad×signo, con advertencias de frontera, y R2/brecha aportan paneles complementarios.',
            '12. **Recomendación:** combinar las reglas descriptivas con diagnósticos multidimensionales, sin sustituirlas aún por nuevos perfiles aprendidos. No se demuestra superioridad global de una ampliación. Revisar utilidad electoral, cobertura, colas de estabilidad y sensibilidad antes de otra adopción o publicación.', '',
            '## Integridad, artefactos y reproducción','',
            f'Se protegen {len(self.state["protected_hashes"]):,} archivos previos mediante SHA-256; se concilian conteos completos y por municipio con descriptivos. Todas las matrices tienen los mismos row_id comunes, columnas finitas, rangos auditados y parámetros propios. Los resúmenes por cluster conservan LN, SV, NV, NS y filas fuente; modelos y vistas son alternativas y nunca se suman entre sí.', '',
            'Cada modelo se guarda incrementalmente en joblib/NPZ con parámetros, huella de matriz y marcador verificado antes de reutilizarlo. Los posteriores se alinean a features/F*/matrix.parquet; labels conserva pendientes NULL. Escritura atómica, exclusión por lock, errores con traceback, memoria/tiempos por checkpoint y reanudación A–G evitan repetir modelos completos. Los joblib sólo se cargan del experimento propio tras verificar hashes.', '',
            'Las pruebas automatizadas comprueban signos y referencias, soporte, geometría del simplex, contraste R2, composición municipal, escalas sólo de entrenamiento, varianza por bloque, alineación y equivalencia de Silhouette con scikit-learn en un caso pequeño; además verifican conteos, matrices, posteriores, pendientes y muestreo municipal de los artefactos. El resultado exacto queda en metadata/test_validation.json. _SUCCESS se escribe sólo tras aprobar pruebas y comprobar integridad.', '',
            'Estructura: reference/ datos completos, pendientes y membresía; features/ matrices y escaladores; diagnostics/ auditoría, soporte y cobertura; models/ ajustes nativos; assignments/ etiquetas completas; resampling/ membresías, ajustes y OOB; sensitivity/ controles y proyecciones; metadata/ contratos, métricas, composiciones, curvas, contingencias, checkpoints y manifiestos.', '',
            '```powershell','.venv_pattern_algorithms/Scripts/python.exe analysis/scripts/evaluate_multidimensional_profiles.py --until B',
            '.venv_pattern_algorithms/Scripts/python.exe analysis/scripts/evaluate_multidimensional_profiles.py',
            '.venv_pattern_algorithms/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_evaluate_multidimensional_profiles.py','```','',
            'Con resultado íntegro, el comando sólo verifica y termina con cero ajustes nuevos. Para reproducción independiente usar --output, --charts y --report nuevos. --until permite detener después de una etapa y --replicates/--anchors fijan presupuestos limitados; no cambiarlos para reanudar el mismo destino.', '',
            'No se modificaron datos originales, agregados previos, informes anteriores, frontend o entornos. No se ejecutaron algoritmos adicionales ni se exportaron perfiles a React. No se crearon commits. Permanecen pendientes revisión electoral de curvas y brechas, sensibilidad adicional con insumos NS conjuntos, más remuestras si hay colas inestables y validación sustantiva de estrategias antes de perfiles definitivos.','']
        atomic_bytes(self.report,'\n'.join(lines).encode('utf8'))

    def stage_g(self):
        started=time.monotonic();paths=[];metrics=self.all_metrics();best=self.best_models();full,main=self.data()
        paths.append(self.table('metadata/all_metrics.csv',metrics))
        natural_context=[]
        for name,spec in self.representations().items():
            if not name.startswith('F4'):continue
            mask=full.base_eligible.copy()
            for block in spec['blocks']:mask &= full[block+'_available']
            part=full[mask];muns=len(part[MUNICIPAL_KEYS].drop_duplicates())
            natural_context.append(dict(representation=name,blocks='+'.join(spec['blocks']),segments=len(part),municipalities=muns,
                LN=int(part.LN.sum()),nominal_fraction=float(part.LN.sum()/NATIONAL_LN),
                municipal_loss_pp=(2402-muns)/2477*100,nominal_loss_pp=(98203780-part.LN.sum())/NATIONAL_LN*100,
                high_ns_segments=int(part.unspecified_rate.ge(.1).sum()),few_sections_segments=int(part.section_count.lt(5).sum()),
                null_features=int(part[[c for block in spec['blocks'] for c in BLOCKS[block]]].isna().sum().sum())))
        paths.append(self.table('diagnostics/contextual_coverage.csv',pd.DataFrame(natural_context)))
        # Mismos ajustes ya guardados, comparación adicional contra semilla
        # principal 17, que coincide con la usada por todas las sensibilidades.
        matched=[]
        for row in pd.read_csv(self.output/'metadata/sensitivity.csv').itertuples():
            reference_id=model_id(row.representation,row.algorithm,int(row.k),17)
            reference=self.load_arrays(reference_id)['labels']
            assignments=pd.read_parquet(self.output/'sensitivity'/row.scenario/f'{row.representation}_{row.algorithm}_assignments.parquet')
            require(assignments.row_id.equals(main.row_id),'Sensibilidad desalineada.')
            prediction=assignments.label.to_numpy();training=assignments.is_training.to_numpy(bool)
            aligned,_=aligned_labels(reference,prediction)
            matched.append(dict(model_id=row.model_id,scenario=row.scenario,baseline_same_seed=reference_id,fit_seed=17,
                ari_all=float(adjusted_rand_score(reference,prediction)),
                ari_common_training=float(adjusted_rand_score(reference[training],prediction[training])),
                aligned_change_fraction=float(np.mean(aligned!=reference))))
        paths.append(self.table('diagnostics/sensitivity_same_seed.csv',pd.DataFrame(matched)))
        # Hallazgo acotado: una GMM contextual puede aprovechar masas en bordes
        # del simplex y aparentar certeza sólo por la regularización.
        contextual=metrics[metrics.representation.eq('F4T')&metrics.algorithm.eq('gmm')]
        if len(contextual):
            row=contextual.sort_values('bic').iloc[0]
            if row.regularization_touched_components>0:
                _,values,slices,_=self.main_matrix('F4T')
                identifier='numerical_diagnostics/f4t_regularization_x10'
                model,arrays,details=self.fit(identifier,values,'gmm',int(row.k),int(row.seed),gmm_reg=1e-4)
                reference=self.load_arrays(row.model_id)['labels']
                shares=main[['section_ln_share_U','section_ln_share_R','section_ln_share_M']].to_numpy()
                numerical=dict(reference_model=row.model_id,diagnostic_model=identifier,
                    reason='Covarianzas al piso y separación dominada por composición: comprobar efecto de regularización, sin otra búsqueda.',
                    reg_covar_main=1e-5,reg_covar_sensitivity=1e-4,ari=float(adjusted_rand_score(reference,arrays['labels'])),
                    main_ambiguous_80=float(row.ambiguous_80),sensitivity_ambiguous_80=details['ambiguous_80'],
                    main_bic=float(row.bic),sensitivity_bic=details['bic'],
                    context_boundary_segments=int(np.any(shares==0,axis=1).sum()),
                    pure_context_segments=int((np.max(shares,axis=1)>=1-1e-12).sum()),
                    **partition_diagnostics(main,values,arrays['labels'],slices))
                numerical={key:(None if isinstance(value,(float,np.floating)) and not np.isfinite(value) else value) for key,value in numerical.items()}
                path=self.output/'diagnostics/contextual_gmm_regularization.json';write_json(path,numerical);paths.append(path)
                paths.extend(self.bundle_paths([identifier]))
                distribution=main[['row_id','relative_turnout','sex_gap_adjusted','section_ln_share_U','section_ln_share_R','section_ln_share_M']].copy()
                distribution['cluster']=reference
                distribution['pure_context']=np.max(shares,axis=1)>=1-1e-12
                distribution['boundary_context']=np.any(shares==0,axis=1)
                grouped=distribution.groupby('cluster',as_index=False).agg(segments=('row_id','size'),pure_context_fraction=('pure_context','mean'),
                    boundary_context_fraction=('boundary_context','mean'),mean_delta=('relative_turnout','mean'),mean_adjusted_gap=('sex_gap_adjusted','mean'),
                    mean_urban_share=('section_ln_share_U','mean'),mean_rural_share=('section_ln_share_R','mean'),mean_mixed_share=('section_ln_share_M','mean'))
                paths.append(self.table('diagnostics/contextual_gmm_clusters.csv',grouped))
        self.make_charts(metrics,best,main)
        self.write_report(metrics,best,full,main)
        # Pruebas pequeñas y validación de artefactos del experimento actual.
        test_environment={**os.environ,'PARTICIPAMX_MULTIDIM_OUTPUT':str(self.output),'PARTICIPAMX_MULTIDIM_REPORT':str(self.report)}
        run=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(self.root/'analysis/scripts'),'-p','test_evaluate_multidimensional_profiles.py'],cwd=self.root,capture_output=True,text=True,env=test_environment)
        path=self.output/'metadata/test_validation.json';write_json(path,dict(returncode=run.returncode,stdout=run.stdout,stderr=run.stderr,command='python -m unittest discover -s analysis/scripts -p test_evaluate_multidimensional_profiles.py'));paths.append(path)
        require(run.returncode==0,'Pruebas fallidas; ver metadata/test_validation.json.')
        for row in best.itertuples():
            assignments=pd.read_parquet(self.output/'assignments'/f'{row.model_id}.parquet')
            require(len(assignments)==len(full) and assignments.label.notna().equals(full.common_eligible),'Pendientes etiquetados o pérdidas de filas.')
        self.verify_protected()
        paths.extend([*self.charts.glob('*.png'),self.report])
        self.checkpoint('G',paths,started,'Gráficas, informe, pruebas automatizadas y conservación verificados; sin exportación React ni perfiles definitivos.')

    def run(self,until):
        final=self.output/'metadata/run_manifest.json'
        if (self.output/'_SUCCESS').exists():
            marker=json.loads((self.output/'_SUCCESS').read_text(encoding='utf8'));manifest=json.loads(final.read_text(encoding='utf8'))
            require(marker['manifest_sha256']==file_hash(final) and manifest['status']=='validated','Marcador final incoherente.')
            for relative,digest in manifest['artifact_hashes'].items():require(file_hash(self.root/relative)==digest,'Salida alterada: '+relative)
            print('Resultado validado: checkpoints verificados, cero ajustes repetidos.',flush=True);return
        stage='A'
        try:
            for stage in 'ABCDEFG':
                if self.valid_stage(stage):print(stage+': checkpoint verificado; no se repite.',flush=True)
                else:getattr(self,'stage_'+stage.lower())()
                if stage==until and stage!='G':return
            self.verify_protected();self.state.update(status='validated',finished=utc());write_json(self.state_path,self.state)
            artifacts={str(p.relative_to(self.root)):file_hash(p) for base in [self.output,self.charts] for p in base.rglob('*')
                if p.is_file() and p not in [final,self.output/'_SUCCESS',self.output/'_RUNNING.json']}
            artifacts[str(self.report.relative_to(self.root))]=file_hash(self.report)
            write_json(final,dict(status='validated',configuration=self.configuration,dependencies=self.dependencies,stages=self.state['stages'],
                protected_hashes=self.state['protected_hashes'],artifact_hashes=artifacts,script_sha256=file_hash(Path(__file__)),
                test_sha256=file_hash(self.root/'analysis/scripts'/OWN_FILES[1])))
            write_json(self.output/'_SUCCESS',dict(manifest_sha256=file_hash(final)))
            print('VALIDADO: '+str(self.report),flush=True)
        except Exception as error:
            self.state['status']='failed';self.state['errors'].append(dict(stage=stage,at=utc(),error=repr(error),traceback=traceback.format_exc()))
            write_json(self.state_path,self.state);raise

    def refresh_report(self):
        """Revisa sólo derivados de G y conserva el manifiesto anterior propio."""
        require(self.valid_stage('F'),'No se puede revisar informe sin F completo.')
        marker=self.output/'_SUCCESS';manifest_path=self.output/'metadata/run_manifest.json'
        require(marker.exists() and manifest_path.exists(),'La revisión requiere resultado propio validado.')
        manifest=json.loads(manifest_path.read_text(encoding='utf8'))
        require(json.loads(marker.read_text())['manifest_sha256']==file_hash(manifest_path),'Marcador previo inconsistente.')
        for relative,digest in manifest['artifact_hashes'].items():require(file_hash(self.root/relative)==digest,'Resultado propio previo alterado: '+relative)
        archive=self.output/'metadata/report_revisions'/str(time.time_ns());archive.mkdir(parents=True)
        for source in [manifest_path,marker,self.output/'metadata/checkpoint_G.json',self.report,self.charts/'sensitivity_comparison.png']:
            require(source.is_relative_to(self.root),'Archivo propio fuera del proyecto.')
            atomic_bytes(archive/source.name,source.read_bytes())
        # Sólo se invalidan el marcador y checkpoint de presentación propios.
        marker.unlink();(self.output/'metadata/checkpoint_G.json').unlink()
        self.state['stages'].pop('G',None);self.state['status']='running';write_json(self.state_path,self.state)
        write_json(archive/'revision.json',dict(reason='Añadir control de semilla emparejada y validación de escalas OOB; mismos modelos y datos.',model_refits=0))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output',type=Path,default=Path('data/processed/multidimensional_profile_review'))
    parser.add_argument('--charts',type=Path,default=Path('analysis/charts/multidimensional_profile_review'))
    parser.add_argument('--report',type=Path,default=Path('analysis/reports/multidimensional_profile_review.md'))
    parser.add_argument('--until',choices=list('ABCDEFG'),default='G')
    parser.add_argument('--replicates',type=int,default=10);parser.add_argument('--anchors',type=int,default=512)
    parser.add_argument('--refresh-report',action='store_true',help='Revisa derivados propios de G, archivando su versión validada; no repite modelos.')
    args=parser.parse_args();root=args.root.resolve();output=(root/args.output).resolve()
    require(2<=args.replicates<=10 and 64<=args.anchors<=1200,'Presupuesto de diagnóstico no permitido.')
    with experiment_lock(output):
        experiment=Experiment(root,output,root/args.charts,root/args.report,args.replicates,args.anchors)
        if args.refresh_report:experiment.refresh_report()
        experiment.run(args.until)


if __name__=='__main__':main()
