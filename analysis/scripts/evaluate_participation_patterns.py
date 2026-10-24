"""Experimento recuperable de nivel y forma por municipio/sexo, sólo K-Means.

Etapas A–F, checkpoints con hashes, exclusión mutua y escritura atómica.
Las referencias completas se conservan; los pendientes nunca se imputan.
"""
from __future__ import annotations

import os
for thread_variable in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[thread_variable]='1'

import argparse
from contextlib import contextmanager
import ctypes
from datetime import datetime,timezone
import io
from itertools import combinations
import json
from pathlib import Path
import platform
import time
import uuid

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from clean_data import require,file_hash
from build_cluster_features import snapshot_inputs,make_ids
from build_descriptive import METRICS,compare_sums,markdown_table,pct
from clustering_core import kmeans,adjusted_rand
from compare_demographic_features import weighted_group_sse,explained_fraction,membership
from evaluate_exact_age_clustering import anchor_silhouettes,db_index
from run_contextual_clustering_pilot import numerical_check
from evaluate_cluster_separation import align_partition

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

BANDS=['18-34','35-59','60-100']
SUFFIXES=['18_34','35_59','60_100']
KEYS=['EDOCVE','MPIOCVE','SEXO']
MUNICIPAL_KEYS=['EDOCVE','MPIOCVE']
KS=[2,3,4,5,6]
SEEDS=[17,42,2024]
Q=np.array([[1/np.sqrt(2),1/np.sqrt(6)],[-1/np.sqrt(2),1/np.sqrt(6)],[0,-2/np.sqrt(6)]])
RATE_COLUMNS=['rate_'+s for s in SUFFIXES]
DELTA_COLUMNS=['delta_'+s for s in SUFFIXES]
SHAPE_COLUMNS=['shape_'+s for s in SUFFIXES]


def utc():return datetime.now(timezone.utc).isoformat()


def atomic_bytes(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp.'+uuid.uuid4().hex)
    with temporary.open('xb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


def write_json(path,value):atomic_bytes(path,json.dumps(value,ensure_ascii=False,indent=2).encode('utf-8'))


def save_figure(figure,path):
    """Publica PNG completo de forma atómica; no deja una gráfica truncada."""
    stream=io.BytesIO();figure.savefig(stream,format='png',dpi=160)
    atomic_bytes(path,stream.getvalue());plt.close(figure)


def write_table(path,frame):
    """Escribe en temporal único, valida lectura y publica mediante replace."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.suffix=='.csv':
        atomic_bytes(path,frame.to_csv(index=False).encode('utf-8-sig'));return
    temporary=path.with_name(path.stem+'.tmp.'+uuid.uuid4().hex+'.parquet')
    table=pa.Table.from_pandas(frame,preserve_index=False)
    pq.write_table(table,temporary,compression='zstd')
    require(table.equals(pq.read_table(temporary)),'Lectura Parquet distinta del temporal.')
    temporary.replace(path)


def safe_ratio(numerator,denominator):
    a,b=np.asarray(numerator,float),np.asarray(denominator,float)
    return np.divide(a,b,out=np.full(a.shape,np.nan),where=b>0)


def pid_status(pid):
    """Consulta no destructiva; no utiliza os.kill en Windows."""
    if pid==os.getpid():return 'active'
    if os.name!='nt':return 'unknown'
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(0x1000,False,int(pid))
    if not handle:return 'absent' if ctypes.get_last_error()==87 else 'unknown'
    code=ctypes.c_ulong()
    try:return ('active' if code.value==259 else 'absent') if kernel.GetExitCodeProcess(handle,ctypes.byref(code)) else 'unknown'
    finally:kernel.CloseHandle(handle)


@contextmanager
def experiment_lock(output):
    """No inicia un segundo proceso; un lock muerto se conserva como evidencia."""
    output.mkdir(parents=True,exist_ok=True);path=output/'_RUNNING.json'
    if path.exists():
        previous=json.loads(path.read_text(encoding='utf-8'));status=pid_status(previous['pid'])
        require(status=='absent',f"Hay un proceso activo o no verificable: PID {previous['pid']}; no se duplicará.")
        path.replace(output/f'_RUNNING.stale.{uuid.uuid4().hex}.json')
    token=uuid.uuid4().hex
    descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    with os.fdopen(descriptor,'w',encoding='utf-8') as stream:json.dump(dict(pid=os.getpid(),token=token,started=utc()),stream)
    try:yield
    finally:
        if path.exists() and json.loads(path.read_text())['token']==token:path.unlink()


def memory_estimate():
    """Working set del proceso en Windows; NULL si la API no está disponible."""
    if os.name!='nt':return {}
    try:
        class Counters(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(name,ctypes.c_size_t) for name in
                ['peak','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile']]
        kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=ctypes.c_void_p
        psapi=ctypes.WinDLL('psapi');psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong]
        value=Counters();value.cb=ctypes.sizeof(value)
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(value),value.cb):
            return dict(working_set_MiB=value.working/2**20,peak_working_set_MiB=value.peak/2**20)
    except (OSError,AttributeError):pass
    return {}


def prepare_profiles(cells,municipalities,broad):
    """Reutiliza C broad, sumando conteos antes de referencias y tasas."""
    require(not cells.duplicated([*KEYS,'age_band']).any(),'Celdas repetidas.')
    require(set(cells.age_band)==set(BANDS) and set(cells.SEXO)=={'0','1'},'Categorías inesperadas en C broad.')
    present=cells[cells.is_present].copy()
    require(present.LN.eq(present.SV+present.NV+present.NS).all(),'Conteos de entrada incorrectos.')
    compare_sums(present,broad[broad.age_band.isin(BANDS)&broad.SEXO.isin(['0','1'])],[*KEYS,'age_band'])
    national=present.groupby(['age_band','SEXO'],as_index=False,observed=True)[METRICS].sum()
    national['national_rate']=safe_ratio(national.SV,national.SV+national.NV)
    work=cells.drop(columns='row_id').merge(national[['age_band','SEXO','national_rate']],on=['age_band','SEXO'],validate='many_to_one')
    work['rate']=safe_ratio(work.SV,work.SV+work.NV)
    require(np.allclose(work.rate,work.participation_observed,equal_nan=True),'Tasas de C no concilian.')
    work['delta']=work.rate-work.national_rate
    index=pd.MultiIndex.from_frame(work[KEYS].drop_duplicates().sort_values(KEYS))
    metadata=present.groupby(KEYS,as_index=True,observed=True)[METRICS].sum(min_count=1).reindex(index)
    rates=[];deltas=[];support=[]
    for band,suffix in zip(BANDS,SUFFIXES):
        part=work[work.age_band.eq(band)].set_index(KEYS).reindex(index)
        for field in ['LN','SV','NV','NS','source_row_count','specified_count','unspecified_rate','national_rate']:
            metadata[field+'_'+suffix]=part[field]
        metadata['rate_'+suffix]=part.rate;metadata['delta_'+suffix]=part.delta
        sufficient=part.is_present.eq(True)&part.LN.ge(100)&part.specified_count.ge(100)&part.source_row_count.ge(5)&np.isfinite(part.rate)
        metadata['supported_'+suffix]=sufficient
        rates.append(part.rate.to_numpy());deltas.append(part.delta.to_numpy());support.append(sufficient.to_numpy())
    rates,deltas,support=np.column_stack(rates),np.column_stack(deltas),np.column_stack(support)
    level=deltas.mean(axis=1);shape=deltas-level[:,None]
    metadata['relative_level']=level
    metadata['mean_observed_rate']=rates.mean(axis=1)
    metadata['complete_profile']=np.isfinite(rates).all(axis=1)&np.isfinite(deltas).all(axis=1)
    metadata['supported_coordinates']=support.sum(axis=1)
    metadata['is_eligible']=metadata.complete_profile&support.all(axis=1)
    metadata['specified_count']=metadata.SV+metadata.NV
    metadata['participation_observed']=safe_ratio(metadata.SV,metadata.specified_count)
    metadata['unspecified_rate']=safe_ratio(metadata.NS,metadata.LN)
    metadata['has_high_ns_coordinate']=metadata[['unspecified_rate_'+s for s in SUFFIXES]].ge(.1).any(axis=1)
    metadata['pending_reason']=np.select([~metadata.complete_profile,~metadata.is_eligible],['undefined_or_absent_rate','insufficient_coordinate_support'],default='eligible')
    for i,suffix in enumerate(SUFFIXES):metadata['shape_'+suffix]=shape[:,i]
    metadata=metadata.reset_index().merge(municipalities[[*MUNICIPAL_KEYS,'state_name_label','municipality_name_label','district_reference_year']],on=MUNICIPAL_KEYS,validate='many_to_one')
    metadata.insert(0,'row_id',make_ids(metadata,KEYS,'pattern_2024'))
    require(metadata.row_id.is_unique,'Perfiles repetidos.')
    for field in KEYS:require(metadata[field].map(lambda value:isinstance(value,str)).all(),'Clave no textual.')
    work=work.merge(metadata[[*KEYS,'row_id']],on=KEYS,validate='many_to_one')
    return metadata,work,national


def fit_parameters(frame):
    delta=frame[DELTA_COLUMNS].to_numpy(float);level=delta.mean(axis=1);contrasts=delta@Q
    require(np.isfinite(delta).all(),'Población no finita.')
    total_scale=float(np.sqrt(np.mean(np.sum((delta-delta.mean(axis=0))**2,axis=1))))
    shape_scale=float(np.sqrt(np.mean(np.sum((contrasts-contrasts.mean(axis=0))**2,axis=1))))
    level_scale=float(level.std(ddof=0))
    require(min(total_scale,shape_scale,level_scale)>1e-12,'Bloque constante; no se inventará una escala.')
    return dict(n=len(frame),delta_mean=delta.mean(axis=0).tolist(),total_scale=total_scale,
        level_mean=float(level.mean()),level_scale=level_scale,shape_mean=contrasts.mean(axis=0).tolist(),
        shape_scale=shape_scale,shape_basis=Q.tolist(),level_variance_fraction=3*level_scale**2/total_scale**2,
        fitted_on='eligible_training_profiles_only',r3_level_weight=.5,r3_shape_weight=.5)


def transform_patterns(frame,representation,parameters):
    delta=frame[DELTA_COLUMNS].to_numpy(float);level=delta.mean(axis=1);contrasts=delta@Q
    shape=(contrasts-np.asarray(parameters['shape_mean']))/parameters['shape_scale']
    if representation=='r1':values=(delta-np.asarray(parameters['delta_mean']))/parameters['total_scale']
    elif representation=='r2':values=shape
    elif representation=='r3':values=np.column_stack([(level-parameters['level_mean'])/parameters['level_scale'],shape])/np.sqrt(2.)
    else:raise ValueError(representation)
    require(np.isfinite(values).all(),'Transformación no finita.')
    return np.ascontiguousarray(values)


def block_diagnostics(frame,labels,representation,parameters):
    delta=frame[DELTA_COLUMNS].to_numpy(float);level=delta.mean(axis=1);shape=delta@Q;ones=np.ones(len(frame))
    total_shape=float(np.sum((shape-shape.mean(axis=0))**2))
    within_shape=sum(weighted_group_sse(shape[:,i],labels,ones) for i in range(2))
    level_between=float(np.sum((level-level.mean())**2)-weighted_group_sse(level,labels,ones))
    shape_between=max(0.,total_shape-within_shape)
    if representation=='r1':lb=3*level_between/parameters['total_scale']**2;sb=shape_between/parameters['total_scale']**2
    elif representation=='r2':lb=0.;sb=shape_between/parameters['shape_scale']**2
    else:lb=.5*level_between/parameters['level_scale']**2;sb=.5*shape_between/parameters['shape_scale']**2
    sex=pd.factorize(frame.SEXO)[0]
    return dict(level_explained=explained_fraction(level,labels,ones),shape_explained=1-within_shape/total_shape,
        between_level_share=lb/(lb+sb) if lb+sb>0 else np.nan,between_shape_share=sb/(lb+sb) if lb+sb>0 else np.nan,
        aggregate_rate_explained=explained_fraction(frame.participation_observed.to_numpy(),labels,ones),
        sex_ari=adjusted_rand(labels,sex),sex_purity=pd.crosstab(labels,sex).max(axis=1).sum()/len(frame))


def shape_direction_summary(frame):
    """Contrastes fijos descriptivos: pendiente joven/mayor y curvatura adulta."""
    delta=frame[DELTA_COLUMNS].to_numpy(float)
    values=np.column_stack([(delta[:,0]-delta[:,2])/np.sqrt(2),
        (delta[:,0]-2*delta[:,1]+delta[:,2])/np.sqrt(6)])
    variances=values.var(axis=0,ddof=0)
    return pd.DataFrame(dict(contrast=['young_older','middle_curvature'],
        mean_pp=values.mean(axis=0)*100,sd_pp=np.sqrt(variances)*100,
        shape_variance_fraction=variances/variances.sum(),
        contrast_correlation=np.corrcoef(values.T)[0,1]))


class Experiment:
    """Estado por etapas y por modelo; un checkpoint sólo referencia artefactos completos."""
    def __init__(self,root,output,charts,report,config):
        self.root,self.output,self.charts,self.report=[Path(v).resolve() for v in [root,output,charts,report]]
        require(self.output.is_relative_to(self.root/'data/processed') and self.charts.is_relative_to(self.root/'analysis/charts') and self.report.is_relative_to(self.root/'analysis/reports'),'Destinos fuera del área autorizada.')
        self.config=config;self.state_path=self.output/'metadata/state.json'
        if self.state_path.exists():
            self.state=json.loads(self.state_path.read_text(encoding='utf-8'))
            require(self.state['config']==config,'Parámetros distintos del checkpoint; usar otro destino.')
            require(self.state['charts']==str(self.charts) and self.state['report']==str(self.report),'Rutas de reanudación distintas.')
            for path,digest in self.state['protected_hashes'].items():require(file_hash(path)==digest,f'Entrada previa alterada: {path}')
        else:
            require(not any(self.output.iterdir()) or set(p.name for p in self.output.iterdir())=={'_RUNNING.json'},'Destino sin estado reconocible; se conservará sin sobrescribir.')
            require(not self.charts.exists() and not self.report.exists(),'Gráficas/informe previos: usar destinos nuevos.')
            protected=snapshot_inputs(self.root,self.output,self.charts)
            for base in [self.root/'analysis/scripts',self.root/'src']:
                for path in base.rglob('*'):
                    if path.is_file() and '__pycache__' not in path.parts and path.name not in ['evaluate_participation_patterns.py','test_evaluate_participation_patterns.py']:
                        protected[str(path)]=file_hash(path)
            protected[str(self.root/'.gitignore')]=file_hash(self.root/'.gitignore')
            self.state=dict(status='running',config=config,protected_hashes=protected,stages={},errors=[],started=utc(),
                charts=str(self.charts),report=str(self.report),versions=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,pyarrow=pa.__version__,matplotlib=matplotlib.__version__))
            self.charts.mkdir(parents=True);write_json(self.state_path,self.state)

    def valid_stage(self,stage):
        path=self.output/f'metadata/checkpoint_{stage}.json'
        if not path.exists():return False
        checkpoint=json.loads(path.read_text(encoding='utf-8'))
        require(checkpoint['status']=='complete','Checkpoint no completo.')
        for relative,digest in checkpoint['artifacts'].items():require(file_hash(self.root/relative)==digest,f'Checkpoint alterado: {relative}')
        return True

    def checkpoint(self,stage,paths,started,summary):
        hashes={str(p.relative_to(self.root)):file_hash(p) for p in paths}
        info=dict(status='complete',stage=stage,finished=utc(),seconds=time.monotonic()-started,summary=summary,
            memory=memory_estimate(),script_sha256=file_hash(Path(__file__)),artifacts=hashes)
        write_json(self.output/f'metadata/checkpoint_{stage}.json',info)
        self.state['stages'][stage]=dict(seconds=info['seconds'],summary=summary);self.state['status']='running'
        write_json(self.state_path,self.state);print(f'Etapa {stage} completa: {summary}',flush=True)

    def preserve_incomplete(self,folder):
        if folder.exists():
            require(folder.is_relative_to(self.output) or folder.is_relative_to(self.charts) or folder==self.report,'Archivo fuera del experimento.')
            relative=folder.relative_to(self.output) if folder.is_relative_to(self.output) else Path(folder.name)
            target=self.output/'incomplete'/uuid.uuid4().hex/relative
            target.parent.mkdir(parents=True,exist_ok=True);folder.replace(target)
            self.state.setdefault('incidents',[]).append(dict(at=utc(),preserved=str(target.relative_to(self.output))))
            write_json(self.state_path,self.state)

    def model(self,folder,values,k,seed,parameters=None):
        marker=folder/'_COMPLETE.json';fingerprint=__import__('hashlib').sha256(values.tobytes()).hexdigest()
        if marker.exists():
            manifest=json.loads(marker.read_text(encoding='utf-8'))
            require(manifest['matrix_sha256']==fingerprint and manifest['k']==k and manifest['seed']==seed,'Modelo de otra población/configuración.')
            for name,digest in manifest['files'].items():require(file_hash(folder/name)==digest,'Modelo parcial o alterado.')
            with np.load(folder/'fit.npz',allow_pickle=False) as arrays:result={name:arrays[name].copy() for name in arrays.files}
            details=json.loads((folder/'fit.json').read_text(encoding='utf-8'));return dict(**result,**details)
        self.preserve_incomplete(folder);folder.mkdir(parents=True)
        started=time.monotonic();fit=kmeans(values,k,seed,n_init=self.config['n_init'],max_iter=self.config['max_iter'])
        require(fit['converged'] and len(np.unique(fit['labels']))==k,'Ajuste no convergente o con grupos vacíos.')
        check=numerical_check(values,np.ones(len(values)),fit)
        stream=io.BytesIO();np.savez_compressed(stream,labels=fit['labels'],centers=fit['centers'])
        atomic_bytes(folder/'fit.npz',stream.getvalue())
        details={name:fit[name] for name in ['inertia','iterations','converged','selected_initialization','initializations']}
        details.update(seconds=time.monotonic()-started,numerical_check=check,parameters=parameters)
        write_json(folder/'fit.json',details)
        with np.load(folder/'fit.npz',allow_pickle=False) as saved:require(np.array_equal(saved['labels'],fit['labels']) and np.array_equal(saved['centers'],fit['centers']),'Modelo escrito distinto.')
        write_json(marker,dict(matrix_sha256=fingerprint,k=k,seed=seed,files={name:file_hash(folder/name) for name in ['fit.npz','fit.json']}))
        return dict(labels=fit['labels'],centers=fit['centers'],**details)

    def stage_a(self):
        if self.valid_stage('A'):return
        started=time.monotonic();source=self.root/'data/processed/cluster_features'
        self.preserve_incomplete(self.output/'reference');self.preserve_incomplete(self.output/'metadata/coverage.json')
        for name in ['cluster_features','clustering_pilot','demographic_representation_comparison']:
            base=self.root/'data/processed'/name;manifest_path=base/'metadata/run_manifest.json'
            manifest=json.loads(manifest_path.read_text(encoding='utf-8'));marker=json.loads((base/'_SUCCESS').read_text())
            require(manifest['status']=='validated' and marker['manifest_sha256']==file_hash(manifest_path),'Fuente sin validar.')
            for relative,digest in manifest['artifact_hashes'].items():require(self.state['protected_hashes'][str(self.root/relative)]==digest,'Artefacto previo alterado.')
        cells=pd.read_parquet(source/'matrices/c_broad/cell_metadata.parquet')
        municipalities=pd.read_parquet(source/'matrices/c_broad/metadata.parquet')
        broad=pd.read_parquet(source/'matrices/b_broad/metadata.parquet')
        features=pd.read_parquet(source/'matrices/c_broad/features.parquet')
        profiles,cells,national=prepare_profiles(cells,municipalities,broad)
        require(len(profiles)==4954 and profiles.is_eligible.sum()==4648,'Población distinta del diagnóstico.')
        for sex,name in [('0','men'),('1','women')]:
            check=profiles[profiles.SEXO.eq(sex)].merge(features.merge(municipalities[['row_id',*MUNICIPAL_KEYS]],on='row_id',validate='one_to_one'),on=MUNICIPAL_KEYS,validate='one_to_one',suffixes=('','_c'))
            for suffix in SUFFIXES:require(np.allclose(check['rate_'+suffix],check[f'participation_{suffix}_{name}'],equal_nan=True),'C broad y nuevas tasas no coinciden.')
        old_mask=municipalities.can_use_complete_algorithms&~municipalities.has_low_support_features
        eligible=profiles[profiles.is_eligible];new_municipalities=eligible.groupby(MUNICIPAL_KEYS).ngroups
        old_keys=set(map(tuple,municipalities.loc[old_mask,MUNICIPAL_KEYS].to_numpy()))
        both=eligible.groupby(MUNICIPAL_KEYS).size();both=set(both[both.eq(2)].index)
        require(both==old_keys,'Cobertura de ambos sexos no concilia con C broad.')
        full_LN=int(broad.LN.sum());baseline_core=int(municipalities.loc[old_mask,'core_LN'].sum())
        coverage=dict(available_profiles=len(profiles),complete_profiles=int(profiles.complete_profile.sum()),eligible_profiles=len(eligible),
            available_municipalities=len(municipalities),eligible_municipalities=new_municipalities,both_sexes_municipalities=len(both),
            one_sex_municipalities=new_municipalities-len(both),no_eligible_municipalities=len(municipalities)-new_municipalities,
            eligible_LN=int(eligible.LN.sum()),national_LN=full_LN,eligible_LN_fraction=eligible.LN.sum()/full_LN,
            previous_c_municipalities=int(old_mask.sum()),previous_c_LN=int(municipalities.loc[old_mask,'LN'].sum()),previous_c_core_LN=baseline_core,
            gate_municipal_drop_pp=5,gate_nominal_drop_pp=1)
        coverage['training_allowed']=bool(new_municipalities>=old_mask.sum()-.05*len(municipalities) and eligible.LN.sum()>=baseline_core-.01*full_LN)
        paths=[]
        for relative,frame in [('reference/profiles.parquet',profiles),('reference/cells.parquet',cells),('reference/national_reference.parquet',national),
            ('reference/broad_complete_reference.parquet',broad),('reference/municipalities.parquet',municipalities),
            ('reference/pending_profiles.parquet',profiles[~profiles.is_eligible])]:
            path=self.output/relative;write_table(path,frame);paths.append(path)
        path=self.output/'metadata/coverage.json';write_json(path,coverage);paths.append(path)
        self.checkpoint('A',paths,started,f'{len(eligible):,} perfiles, {new_municipalities:,} municipios, LN {pct(coverage["eligible_LN_fraction"])}; puerta de cobertura={coverage["training_allowed"]}.')

    def stage_b(self):
        if self.valid_stage('B'):return
        started=time.monotonic();full=pd.read_parquet(self.output/'reference/profiles.parquet');training=full[full.is_eligible].reset_index(drop=True)
        for path in ['features','metadata/parameters.json','metadata/feature_contract.json']:self.preserve_incomplete(self.output/path)
        parameters=fit_parameters(training);paths=[]
        for representation in ['r1','r2','r3']:
            values=transform_patterns(training,representation,parameters)
            names=['delta_'+s for s in SUFFIXES] if representation=='r1' else ['shape_contrast_1','shape_contrast_2'] if representation=='r2' else ['relative_level','shape_contrast_1','shape_contrast_2']
            path=self.output/f'features/{representation}.parquet';write_table(path,pd.DataFrame(values,columns=names).assign(row_id=training.row_id)[['row_id',*names]]);paths.append(path)
        path=self.output/'metadata/parameters.json';write_json(path,parameters);paths.append(path)
        path=self.output/'metadata/feature_contract.json';write_json(path,dict(unit='municipality_sex',bands=BANDS,shape_basis=Q.tolist(),
            excluded_from_distance=['age_mean','SEXO',*MUNICIPAL_KEYS,'TIPOSEC','LN','NS','specified_count'],
            r1='Tres diferencias; una sola escala RMS común. No escalado por banda.',r2='Forma centrada por fila, dos contrastes ortonormales equivalentes; una escala RMS del bloque. Conserva amplitud.',
            r3='Nivel con DE poblacional y forma con RMS del bloque; 50/50 de varianza a priori.',source_counts='reference/broad_complete_reference.parquet',
            reference='ΣSV/Σ(SV+NV) por banda/sexo, antes de seleccionar soporte.',main_fits=45,max_bootstrap_fits=20));paths.append(path)
        self.checkpoint('B',paths,started,f'Mismo universo R1/R2/R3; nivel explica {pct(parameters["level_variance_fraction"])} de la varianza del vector relativo completo.')

    def stage_c(self):
        if self.valid_stage('C'):return
        started=time.monotonic();records=[];paths=[]
        for representation in ['r1','r2','r3']:
            features=pd.read_parquet(self.output/f'features/{representation}.parquet');values=features.drop(columns='row_id').to_numpy(float)
            for k in KS:
                for seed in SEEDS:
                    folder=self.output/f'models/{representation}/k{k}/seed{seed}'
                    fit=self.model(folder,values,k,seed)
                    records.append(dict(representation=representation,k=k,seed=seed,sse=fit['inertia'],n=len(values),dimensions=values.shape[1],
                        converged=fit['converged'],iterations=fit['iterations'],seconds=fit['seconds'],**fit['numerical_check']))
                    paths.extend(folder/name for name in ['fit.npz','fit.json','_COMPLETE.json'])
                    print(f'C: {representation} K={k} semilla={seed}; modelo guardado/verificado.',flush=True)
        path=self.output/'metadata/model_runs.csv';write_table(path,pd.DataFrame(records));paths.append(path)
        require(len(records)==45,'Se excedió o no completó el presupuesto principal.')
        self.checkpoint('C',paths,started,'45 ajustes completos; diez arranques por ajuste; sin matriz N×N.')

    def load_fit(self,representation,k,seed):
        folder=self.output/f'models/{representation}/k{int(k)}/seed{int(seed)}'
        details=json.loads((folder/'fit.json').read_text(encoding='utf-8'))
        with np.load(folder/'fit.npz',allow_pickle=False) as arrays:return dict(**details,labels=arrays['labels'].copy(),centers=arrays['centers'].copy())

    def stage_d(self):
        if self.valid_stage('D'):return
        started=time.monotonic();full=pd.read_parquet(self.output/'reference/profiles.parquet');training=full[full.is_eligible].reset_index(drop=True)
        parameters=json.loads((self.output/'metadata/parameters.json').read_text(encoding='utf-8'))
        count=min(self.config['anchor_count'],len(training));anchors=np.sort(np.random.default_rng(319).choice(len(training),count,replace=False))
        records=[];stability=[];profiles=[];curves=[];paths=[]
        for representation in ['r1','r2','r3']:
            values=transform_patterns(training,representation,parameters)
            fits={(k,seed):self.load_fit(representation,k,seed) for k in KS for seed in SEEDS}
            scores=anchor_silhouettes(values,{f'{k}_{seed}':fit['labels'] for (k,seed),fit in fits.items()},anchors,block_size=32)
            for (k,seed),fit in fits.items():
                sample=scores[f'{k}_{seed}'];sizes=np.bincount(fit['labels'],minlength=k)
                records.append(dict(representation=representation,k=k,seed=seed,sse=fit['inertia'],silhouette=float(sample.mean()),
                    silhouette_mc_se=float(sample.std(ddof=1)/np.sqrt(len(sample))*np.sqrt((len(training)-len(sample))/len(training))),
                    silhouette_anchors=len(sample),silhouette_reference=len(training),db=db_index(values,fit['labels']),
                    smallest_cluster=int(sizes.min()),largest_cluster=int(sizes.max()),**block_diagnostics(training,fit['labels'],representation,parameters)))
                for cluster in range(k):
                    part=training[fit['labels']==cluster]
                    profiles.append(dict(representation=representation,k=k,seed=seed,cluster=cluster,observations=len(part),
                        municipalities=part.groupby(MUNICIPAL_KEYS).ngroups,women_fraction=part.SEXO.eq('1').mean(),
                        **{field:int(part[field].sum()) for field in METRICS},participation_observed=part.SV.sum()/part.specified_count.sum(),
                        relative_level=part.relative_level.mean(),unspecified_rate=part.NS.sum()/part.LN.sum(),
                        high_ns_fraction=part.has_high_ns_coordinate.mean()))
                    for suffix,band in zip(SUFFIXES,BANDS):
                        curves.append(dict(representation=representation,k=k,seed=seed,cluster=cluster,age_band=band,
                            mean_rate=part['rate_'+suffix].mean(),mean_delta=part['delta_'+suffix].mean(),mean_shape=part['shape_'+suffix].mean(),
                            LN=int(part['LN_'+suffix].sum()),SV=int(part['SV_'+suffix].sum()),NV=int(part['NV_'+suffix].sum()),NS=int(part['NS_'+suffix].sum()),
                            aggregate_rate=part['SV_'+suffix].sum()/(part['SV_'+suffix].sum()+part['NV_'+suffix].sum())))
            for k in KS:
                for a,b in combinations(SEEDS,2):stability.append(dict(representation=representation,k=k,seed_left=a,seed_right=b,ari=adjusted_rand(fits[k,a]['labels'],fits[k,b]['labels'])))
            print(f'D: métricas por bloques de {representation} completas.',flush=True)
        metrics=pd.DataFrame(records);seed_metrics=pd.DataFrame(stability)
        summary=metrics.groupby(['representation','k'],as_index=False).mean(numeric_only=True).merge(
            seed_metrics.groupby(['representation','k'],as_index=False).agg(seed_ari_min=('ari','min')),on=['representation','k'],validate='one_to_one')
        old=pd.read_csv(self.root/'data/processed/clustering_pilot/metadata/model_comparison.csv')
        old=old[(old.context_id=='c_broad_standard_main')&(old.algorithm=='kmeans')&old.k.isin(KS)]
        for relative,frame in [('metadata/model_metrics.csv',metrics),('metadata/seed_stability.csv',seed_metrics),('metadata/model_summary.csv',summary),
            ('metadata/cluster_profiles.csv',pd.DataFrame(profiles)),('metadata/cluster_curves.csv',pd.DataFrame(curves)),
            ('metadata/previous_c_metrics.csv',old),('metadata/anchors.parquet',training.loc[anchors,['row_id',*KEYS]])]:
            path=self.output/relative;self.preserve_incomplete(path);write_table(path,frame);paths.append(path)
        self.checkpoint('D',paths,started,'Silhouette aproximado de anclas frente a todos los perfiles; DB, nivel/forma, curvas y semillas de los 45 ajustes.')

    def choose_candidates(self,explicit):
        summary=pd.read_csv(self.output/'metadata/model_summary.csv')
        full=pd.read_parquet(self.output/'reference/profiles.parquet');n=int(full.is_eligible.sum())
        if explicit:
            require(1<=len(explicit)<=2 and len(set(explicit))==len(explicit),'Máximo dos candidatas distintas.')
            selected=[]
            for token in explicit:
                representation,k=token.split(':');k=int(k)
                require(representation in ['r1','r2','r3'] and k in [2,3,4,5],'K=6 sólo sensibilidad, no candidata principal.')
                selected.append((representation,k))
            rationale='Candidatas explícitas tras revisar D: contraste de forma/nivel, parsimonia, tamaño y estabilidad de semillas; no selección de perfiles definitivos.'
            if set(selected)=={('r2',2),('r2',4)}:
                rationale=('Tras revisar los 45 ajustes: R2 K=2 contrasta una descripción parsimoniosa de forma; '
                    'R2 K=4 evalúa la resolución adicional y la hipótesis de cuatro a seis perfiles. '
                    'Se revisaron curvas, tamaños y concordancia entre semillas; el S máximo de R2 está en K=2. '
                    'R1 sigue dominada por nivel y R3 conserva deliberadamente ese bloque, por lo que no se priorizan '
                    'para este remuestreo acotado. Dos candidatas de diagnóstico, sin elegir K definitivo.')
        else:
            viable=summary[(summary.k<=5)&summary.seed_ari_min.ge(.9)&summary.smallest_cluster.ge(.05*n)]
            require(not viable[viable.representation.eq('r2')].empty,'No hay candidata de forma con tamaño/semillas mínimos; revisar D.')
            choices=viable[viable.representation.eq('r2')]
            first=choices[choices.silhouette>=choices.silhouette.max()-.02].sort_values('k').iloc[0]
            selected=[('r2',int(first.k))]
            alternatives=viable[viable.representation.eq('r3')&viable.between_shape_share.ge(.25)]
            if not alternatives.empty:
                second=alternatives[alternatives.silhouette>=alternatives.silhouette.max()-.02].sort_values('k').iloc[0]
                selected.append(('r3',int(second.k)))
            rationale='Regla acotada: semillas ARI≥0.90, grupos medios≥5 %, forma explícita; K menor a ≤0.02 del S máximo en su representación. Segundo contraste R3 sólo con ≥25 % de separación de forma. Umbrales operativos, no pruebas de clusters naturales.'
        frozen=self.state.get('candidates')
        require(frozen is None or frozen==[list(v) for v in selected],'Candidatas distintas de la validación iniciada; no se repetirán modelos.')
        self.state['candidates']=[list(v) for v in selected];write_json(self.state_path,self.state)
        path=self.output/'metadata/candidate_selection.json'
        if not path.exists():write_json(path,dict(candidates=self.state['candidates'],rationale=rationale,summary_sha256=file_hash(self.output/'metadata/model_summary.csv')))
        return selected

    def stage_e(self,candidates):
        if self.valid_stage('E'):return
        started=time.monotonic();full=pd.read_parquet(self.output/'reference/profiles.parquet');base=full.is_eligible.to_numpy();main=full.loc[base].reset_index(drop=True)
        metrics=pd.read_csv(self.output/'metadata/model_metrics.csv');baseline={}
        for representation,k in candidates:
            rows=metrics[(metrics.representation==representation)&(metrics.k==k)]
            seed=int(rows.loc[rows.sse.idxmin(),'seed']);baseline[representation,k]=self.load_fit(representation,k,seed)['labels']
        samples=pd.read_parquet(self.root/'data/processed/demographic_representation_comparison/resampling/municipality_membership.parquet')
        keys=samples[MUNICIPAL_KEYS];require(not keys.duplicated().any(),'Municipios duplicados en muestras.')
        records=[];coverages=[];patterns=[];paths=[]
        for replicate in range(self.config['replicates']):
            draw=samples[f'sample_{replicate:03d}'].to_numpy(bool)
            require(int(draw.sum())==1981,'Membresía municipal inesperada.')
            chosen=membership(full,keys,draw);mask=chosen&base;inbag=chosen[base];oob=~inbag
            training=full.loc[mask].reset_index(drop=True);parameters=fit_parameters(training)
            coverages.append(dict(replicate=replicate,selected_municipalities=int(draw.sum()),training_profiles=len(training),
                training_municipalities=training.groupby(MUNICIPAL_KEYS).ngroups,training_LN=int(training.LN.sum()),
                fraction_eligible_LN=training.LN.sum()/main.LN.sum(),oob_profiles=int(oob.sum()),oob_municipalities=main.loc[oob].groupby(MUNICIPAL_KEYS).ngroups))
            for representation,k in candidates:
                values=transform_patterns(training,representation,parameters);whole=transform_patterns(main,representation,parameters)
                folder=self.output/f'resampling/sample_{replicate:03d}/{representation}_k{k}'
                fit=self.model(folder,values,k,17,parameters)
                squared=((whole[:,None,:]-fit['centers'][None,:,:])**2).sum(axis=2);prediction=squared.argmin(axis=1)
                reference=baseline[representation,k];aligned,mapping=align_partition(reference[oob],prediction[oob],k)
                records.append(dict(representation=representation,k=k,replicate=replicate,ari_oob=adjusted_rand(reference[oob],prediction[oob]),
                    ari_inbag=adjusted_rand(reference[inbag],prediction[inbag]),oob_changed_fraction=float(np.mean(reference[oob]!=aligned)),
                    smallest_cluster=int(np.bincount(fit['labels'],minlength=k).min()),seconds=fit['seconds']))
                for cluster in range(k):
                    original=main[reference==cluster];sample=training[mapping[fit['labels']]==cluster]
                    shape_change=float(np.sqrt(np.mean((sample[SHAPE_COLUMNS].mean().to_numpy()-original[SHAPE_COLUMNS].mean().to_numpy())**2))*100)
                    for suffix,band in zip(SUFFIXES,BANDS):patterns.append(dict(representation=representation,k=k,replicate=replicate,cluster=cluster,
                        age_band=band,mean_delta=sample['delta_'+suffix].mean(),mean_shape=sample['shape_'+suffix].mean(),mean_rate=sample['rate_'+suffix].mean(),shape_change_RMS_pp=shape_change))
                frame=full[['row_id',*KEYS]].copy();frame['is_training']=mask;frame['is_oob_eligible']=base&~chosen
                label=pd.array([pd.NA]*len(full),dtype='Int64');label[base]=prediction;frame['projected_label']=label
                path=folder/'assignment.parquet'
                if path.exists():
                    pd.testing.assert_frame_equal(pd.read_parquet(path),frame,check_dtype=False)
                else:write_table(path,frame)
                paths.extend(folder/name for name in ['fit.npz','fit.json','_COMPLETE.json','assignment.parquet'])
            print(f'E: submuestra {replicate+1}/{self.config["replicates"]}, {len(training):,} perfiles; {int(oob.sum()):,} OOB.',flush=True)
        for relative,frame in [('metadata/resampling_metrics.csv',pd.DataFrame(records)),('metadata/resampling_coverage.csv',pd.DataFrame(coverages)),
            ('metadata/resampling_patterns.csv',pd.DataFrame(patterns)),('reference/municipality_membership.parquet',samples)]:
            path=self.output/relative;self.preserve_incomplete(path);write_table(path,frame);paths.append(path)
        paths.append(self.output/'metadata/candidate_selection.json')
        self.checkpoint('E',paths,started,f'{len(records)} ajustes limitados; mismas muestras municipales, ambos sexos juntos.')

    def final_data(self):
        full=pd.read_parquet(self.output/'reference/profiles.parquet');main=full[full.is_eligible].reset_index(drop=True)
        metrics=pd.read_csv(self.output/'metadata/model_metrics.csv');best={}
        for (representation,k),group in metrics.groupby(['representation','k']):
            row=group.loc[group.sse.idxmin()];seed=int(row.seed);best[representation,int(k)]=(seed,self.load_fit(representation,int(k),seed))
        return full,main,metrics,best

    def plot_results(self,full,main,metrics,best):
        candidates=[tuple(v) for v in self.state['candidates']]
        curves=pd.read_csv(self.output/'metadata/cluster_curves.csv')
        profiles=pd.read_csv(self.output/'metadata/cluster_profiles.csv')
        summary=pd.read_csv(self.output/'metadata/model_summary.csv')
        fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
        for representation in ['r1','r2','r3']:
            frame=summary[summary.representation.eq(representation)]
            axes[0].plot(frame.k,frame.silhouette,'o-',label=representation.upper());axes[1].plot(frame.k,frame.db,'o-',label=representation.upper())
        axes[0].set(ylabel='Silhouette aproximado',xlabel='K (6: sensibilidad)');axes[1].set(ylabel='Davies–Bouldin',xlabel='K')
        axes[0].legend();axes[1].legend();fig.suptitle('Métricas en cada geometría · no son una clasificación universal')
        save_figure(fig,self.charts/'metrics_by_k.png')
        fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
        q=main[DELTA_COLUMNS].to_numpy()@Q
        for ax,representation in zip(axes,['r1','r2','r3']):
            # K=2 compartido como control de lectura; no se afirma que sea óptimo.
            labels=best[representation,2][1]['labels']
            scatter=ax.scatter(main.relative_level*100,(q[:,0])*100,c=labels,s=8,alpha=.45,cmap='tab10',vmin=0,vmax=9,rasterized=True)
            ax.set(title=representation.upper()+' · control K=2',xlabel='Nivel medio relativo (pp)',ylabel='Contraste 18–34 vs 35–59 (pp)')
        fig.suptitle('Variables originales · se omite el segundo contraste de forma\nLa proyección no muestra todas las distancias utilizadas')
        save_figure(fig,self.charts/'level_and_shape.png')
        delta=main[DELTA_COLUMNS].to_numpy()
        slope=(delta[:,0]-delta[:,2])*100/np.sqrt(2)
        curvature=(delta[:,0]-2*delta[:,1]+delta[:,2])*100/np.sqrt(6)
        fig,axes=plt.subplots(1,3,figsize=(14,4.8),layout='constrained',sharex=True,sharey=True)
        density=axes[0].hexbin(slope,curvature,gridsize=45,mincnt=1,bins='log',cmap='viridis')
        fig.colorbar(density,ax=axes[0],label='Perfiles por celda (color logarítmico)');axes[0].set_title('Densidad observada · sin etiquetas')
        for ax,k in zip(axes[1:],[2,4]):
            ax.scatter(slope,curvature,c=best['r2',k][1]['labels'],cmap='tab10',vmin=0,vmax=9,s=7,alpha=.4,rasterized=True)
            ax.set_title(f'R2 K={k} · etiquetas locales')
        for ax in axes:
            ax.set(xlabel='Contraste jóvenes−mayores / √2 (pp)',ylabel='Curvatura (jóvenes−2 adultos+mayores) / √6 (pp)')
            ax.set_aspect('equal',adjustable='box')
        fig.suptitle('Plano completo de forma · rotación fija isométrica, sin reducción de dimensión\nUn corte de K-Means no prueba poblaciones discretas')
        save_figure(fig,self.charts/'shape_space.png')
        for representation,k in candidates:
            seed=best[representation,k][0]
            frame=curves[(curves.representation==representation)&(curves.k==k)&(curves.seed==seed)]
            fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
            for cluster,part in frame.groupby('cluster'):
                part=part.set_index('age_band').loc[BANDS]
                for ax,field in zip(axes,['mean_delta','mean_shape','mean_rate']):ax.plot(BANDS,part[field]*100,'o-',label=f'Etiqueta {cluster}')
            for ax,title in zip(axes,['Diferencia nacional original (pp)','Forma tras retirar nivel (pp)','Tasa absoluta media (%)']):
                ax.set(title=title,xlabel='Intervalo candidato');ax.grid(alpha=.2);ax.legend(fontsize=8)
            axes[0].axhline(0,color='gray',lw=.5);axes[1].axhline(0,color='gray',lw=.5);axes[2].set_ylim(0,100)
            fig.suptitle(f'{representation.upper()} · K={k} · medias de perfiles con igual peso\nLas tasas agregadas por conteos se conservan por separado en las tablas')
            save_figure(fig,self.charts/f'curves_{representation}_k{k}.png')
        fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
        groups=main.groupby(MUNICIPAL_KEYS).size();counts=[int(groups.eq(2).sum()),int(groups.eq(1).sum()),2477-len(groups)]
        axes[0].bar(['Ambos sexos','Un sexo','Sin perfil'],counts,color=['#38827e','#d89b41','#b66b65']);axes[0].set(ylabel='Municipios',title='Cobertura municipal de perfiles con soporte')
        available=full.groupby('SEXO').LN.sum();eligible=main.groupby('SEXO').LN.sum()
        axes[1].bar(['Hombres','Mujeres'],eligible.reindex(['0','1'])/available.reindex(['0','1']),color=['#578cad','#ae6a8a'])
        axes[1].yaxis.set_major_formatter(PercentFormatter(1));axes[1].set(ylim=(0,1),ylabel='LN elegible / LN 18–100 del sexo',title='Cobertura nominal · no mide captura individual')
        save_figure(fig,self.charts/'coverage.png')
        fig,axes=plt.subplots(2,len(candidates),figsize=(7*len(candidates),8),layout='constrained',squeeze=False)
        for column,(representation,k) in enumerate(candidates):
            ax=axes[0,column]
            seed=best[representation,k][0];part=profiles[(profiles.representation==representation)&(profiles.k==k)&(profiles.seed==seed)]
            ax.bar(part.cluster,part.women_fraction,label='Mujeres',color='#ae6a8a');ax.bar(part.cluster,1-part.women_fraction,bottom=part.women_fraction,label='Hombres',color='#578cad')
            ax.set(title=f'{representation.upper()} K={k}',xlabel='Etiqueta local',ylabel='Fracción de observaciones municipio/sexo');ax.yaxis.set_major_formatter(PercentFormatter(1));ax.legend()
            ax=axes[1,column];bottom=np.zeros(k)
            subset=curves[(curves.representation==representation)&(curves.k==k)&(curves.seed==seed)]
            totals=subset.groupby('cluster').LN.sum().reindex(range(k))
            for band,color in zip(BANDS,['#d89b41','#38827e','#7565a6']):
                shares=subset[subset.age_band.eq(band)].set_index('cluster').LN.reindex(range(k))/totals
                ax.bar(range(k),shares,bottom=bottom,label=band,color=color);bottom+=shares.to_numpy()
            ax.set(xlabel='Etiqueta local',ylabel='Fracción de LN del cluster por edad');ax.yaxis.set_major_formatter(PercentFormatter(1));ax.legend()
        fig.suptitle('Composición por sexo · cada observación contiene las tres edades')
        save_figure(fig,self.charts/'sex_composition.png')
        stability=pd.read_csv(self.output/'metadata/resampling_metrics.csv')
        fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
        arrays=[stability.loc[(stability.representation==r)&(stability.k==k),'ari_oob'] for r,k in candidates]
        axes[0].boxplot(arrays,tick_labels=[f'{r.upper()} K={k}' for r,k in candidates],showfliers=True);axes[0].set(ylabel='ARI OOB',ylim=(0,1.02),title='Diez submuestras compartidas · incluye extremos')
        changes=pd.read_csv(self.output/'metadata/resampling_patterns.csv').drop_duplicates(['representation','k','replicate','cluster'])
        arrays=[changes.loc[(changes.representation==r)&(changes.k==k),'shape_change_RMS_pp'] for r,k in candidates]
        axes[1].boxplot(arrays,tick_labels=[f'{r.upper()} K={k}' for r,k in candidates]);axes[1].set(ylabel='Cambio RMS de forma (pp)',title='Centros descriptivos alineados · todas las muestras')
        save_figure(fig,self.charts/'municipality_stability.png')

    def stage_f(self):
        if self.valid_stage('F'):return
        started=time.monotonic();full,main,metrics,best=self.final_data()
        if self.charts.exists() and any(self.charts.iterdir()):self.preserve_incomplete(self.charts)
        self.charts.mkdir(parents=True,exist_ok=True)
        if self.report.exists():self.preserve_incomplete(self.report)
        for name in ['state_coverage.csv','unrepresented_municipalities.parquet','profile_quality.csv','candidate_stability.csv','shape_directions.csv','municipality_pair_summary.csv']:
            self.preserve_incomplete(self.output/'metadata'/name)
        self.plot_results(full,main,metrics,best)
        validations=[]
        profiles=pd.read_csv(self.output/'metadata/cluster_profiles.csv')
        sums=profiles.groupby(['representation','k','seed'])[METRICS].sum()
        require(np.array_equal(sums.to_numpy(),np.tile(main[METRICS].sum().to_numpy(),(45,1))),'Conteos de clusters no conservados.')
        for representation in ['r1','r2','r3']:
            labels=full[['row_id',*KEYS,'is_eligible','pending_reason']].copy()
            for k in KS:
                for seed in SEEDS:
                    fitted=self.load_fit(representation,k,seed)
                    column=pd.array([pd.NA]*len(full),dtype='Int64');column[full.is_eligible]=fitted['labels'];labels[f'k{k}_seed{seed}']=column
            path=self.output/f'assignments/{representation}.parquet';self.preserve_incomplete(path);write_table(path,labels)
            require(labels.loc[~full.is_eligible,[c for c in labels if c.startswith('k')]].isna().all().all(),'Pendientes asignados.')
            validations.append(dict(check='labels_and_counts',representation=representation,differences=0))
        for path,digest in self.state['protected_hashes'].items():require(file_hash(path)==digest,f'Archivo previo modificado: {path}')
        path=self.output/'metadata/output_validation.csv';self.preserve_incomplete(path);write_table(path,pd.DataFrame(validations))
        self.write_report(full,main,metrics,best)
        paths=[*self.charts.glob('*.png'),self.report,path,*list((self.output/'assignments').glob('*.parquet')),
            *[self.output/'metadata'/name for name in ['state_coverage.csv','unrepresented_municipalities.parquet','profile_quality.csv','candidate_stability.csv','shape_directions.csv','municipality_pair_summary.csv']]]
        diagnosis=self.output/'metadata/recovery_diagnosis.json'
        if diagnosis.exists():paths.append(diagnosis)
        self.checkpoint('F',paths,started,'Gráficas, informe, etiquetas completas, conteos e integridad comprobados.')

    def write_report(self,full,main,metrics,best):
        summary=pd.read_csv(self.output/'metadata/model_summary.csv');stability=pd.read_csv(self.output/'metadata/resampling_metrics.csv')
        coverage=json.loads((self.output/'metadata/coverage.json').read_text());parameters=json.loads((self.output/'metadata/parameters.json').read_text())
        old=pd.read_csv(self.output/'metadata/previous_c_metrics.csv')
        old=old.groupby('k',as_index=False)[['silhouette','between_level_share','between_shape_share','level_explained','shape_explained']].mean()
        candidates=[tuple(v) for v in self.state['candidates']]
        def table(frame,columns,headers=None):
            rows=[]
            for _,row in frame.iterrows():
                rows.append(['n/d' if pd.isna(row[c]) else f'{row[c]:.4f}' if isinstance(row[c],(float,np.floating)) else str(row[c]) for c in columns])
            return markdown_table(headers or columns,rows)
        def image(name,title):return f'![{title}]({Path(os.path.relpath(self.charts/name,self.report.parent)).as_posix()})'
        rows=[]
        for (representation,k),group in stability.groupby(['representation','k']):
            rows.append(dict(representation=representation,k=k,median=group.ari_oob.median(),minimum=group.ari_oob.min(),q10=group.ari_oob.quantile(.1),
                below_90=int(group.ari_oob.lt(.9).sum()),maximum_change=group.oob_changed_fraction.max()))
        robust=pd.DataFrame(rows)
        profiles=pd.read_csv(self.output/'metadata/cluster_profiles.csv')
        candidate_profiles=pd.concat([profiles[(profiles.representation==r)&(profiles.k==k)&(profiles.seed==best[r,k][0])] for r,k in candidates])
        candidate_profiles['nominal_fraction']=candidate_profiles.LN/main.LN.sum()
        pair_rows=[]
        for r,k in candidates:
            assignments=main[[*MUNICIPAL_KEYS,'SEXO']].assign(cluster=best[r,k][1]['labels'])
            paired=assignments.pivot(index=MUNICIPAL_KEYS,columns='SEXO',values='cluster').dropna()
            same=int(paired['0'].eq(paired['1']).sum())
            pair_rows.append(dict(representation=r,k=k,paired_municipalities=len(paired),
                same_cluster=same,different_clusters=len(paired)-same,same_fraction=same/len(paired)))
        pair_summary=pd.DataFrame(pair_rows);write_table(self.output/'metadata/municipality_pair_summary.csv',pair_summary)
        counts=full.groupby('SEXO',as_index=False).agg(available=('row_id','size'),defined=('complete_profile','sum'),eligible=('is_eligible','sum'),LN=('LN','sum'))
        states=[]
        for state,group in full.groupby('EDOCVE'):
            chosen=group[group.is_eligible];states.append(dict(EDOCVE=state,state_name_label=group.state_name_label.iloc[0],profiles=len(chosen),
                municipalities=chosen.groupby(MUNICIPAL_KEYS).ngroups,eligible_LN=int(chosen.LN.sum()),nominal_fraction=chosen.LN.sum()/group.LN.sum()))
        write_table(self.output/'metadata/state_coverage.csv',pd.DataFrame(states))
        no_profile=full.groupby(MUNICIPAL_KEYS).is_eligible.any();no_keys=no_profile[~no_profile].reset_index()[MUNICIPAL_KEYS]
        absent=full.merge(no_keys,on=MUNICIPAL_KEYS,validate='many_to_one')[[*MUNICIPAL_KEYS,'municipality_name_label']].drop_duplicates()
        write_table(self.output/'metadata/unrepresented_municipalities.parquet',absent)
        quality=[]
        for label,frame in [('available',full),('eligible',main)]:
            quality.append(dict(scope=label,profiles=len(frame),LN=int(frame.LN.sum()),null_profiles=int((~frame.complete_profile).sum()),
                high_ns_coordinates=int(frame.has_high_ns_coordinate.sum()),ns_nominal=frame.NS.sum()/frame.LN.sum(),
                ns_q1=frame.unspecified_rate.quantile(.25),ns_median=frame.unspecified_rate.median(),ns_q3=frame.unspecified_rate.quantile(.75)))
        for name,frame in [('profile_quality',pd.DataFrame(quality)),('candidate_stability',robust)]:write_table(self.output/f'metadata/{name}.csv',frame)
        direction=shape_direction_summary(main);write_table(self.output/'metadata/shape_directions.csv',direction)
        resampling_coverage=pd.read_csv(self.output/'metadata/resampling_coverage.csv')
        changed_shapes=pd.read_csv(self.output/'metadata/resampling_patterns.csv').drop_duplicates(['representation','k','replicate','cluster'])
        stability_text=' '.join(f'{r.upper()} K={int(k)}: ARI OOB mediano {g.ari_oob.median():.3f}, mínimo {g.ari_oob.min():.3f}, '
            f'{int(g.ari_oob.lt(.9).sum())}/{len(g)} muestras por debajo de 0.90; máximo cambio alineado {pct(g.oob_changed_fraction.max())}.'
            for (r,k),g in stability.groupby(['representation','k']))
        explicit=' '.join(f'{r}:{k}' for r,k in candidates)
        candidate_charts='\n\n'.join(image(f'curves_{r}_k{k}.png',f'Curvas {r.upper()}, K={k}') for r,k in candidates)
        r1=summary[(summary.representation=='r1')&summary.k.eq(2)].iloc[0]
        shape_rows=summary[summary.representation.eq('r2')]
        best_shape=shape_rows.loc[shape_rows.silhouette.idxmax()]
        shape_k2=shape_rows[shape_rows.k.eq(2)].iloc[0];shape_k4=shape_rows[shape_rows.k.eq(4)].iloc[0]
        r3=summary[summary.representation.eq('r3')]
        curves=pd.read_csv(self.output/'metadata/cluster_curves.csv')
        shape_table=pd.concat([curves[(curves.representation=='r2')&curves.k.eq(k)&curves.seed.eq(best['r2',k][0])]
            for k in [2,4]]).pivot(index=['k','cluster'],columns='age_band',values='mean_shape').reset_index()
        shape_table[BANDS]=shape_table[BANDS]*100
        text=f'''# Patrones de participación entre edades · experimento recuperable de 2024

## Diagnóstico de recuperación y alcance

El turno anterior se interrumpió durante lecturas y planificación: no existían script, informe ni destinos de este experimento y no se encontraron procesos Python activos con Get-Process. La consulta CIM fue denegada, por lo que se usó una consulta alternativa no destructiva. No había modelos incompletos que recuperar ni se reinició un experimento ya ejecutado. Se reutilizaron las comprobaciones previas de esquema y cobertura. El diagnóstico original se conserva en metadata/recovery_diagnosis.json; estado e incidencias de ejecución quedan en metadata/state.json.

Se completaron las etapas A–F: validación, matrices, **45 ajustes completos**, métricas, hasta dos candidatas con {self.config['replicates']} submuestras municipales y reporte final. Sólo se utiliza K-Means NumPy validado del proyecto; no se ejecutaron GMM, HDBSCAN o K-Medoids. No se eligieron perfiles definitivos. La unidad es **municipio + sexo**, con tres coordenadas de edad; no personas ni segmentos individuales de edad.

**Resultado:** R2 permite describir diferencias entre edades que R1 oculta detrás del nivel general. Sin embargo, el contraste jóvenes–mayores concentra {pct(direction.shape_variance_fraction.iloc[0])} de la varianza de forma: los grupos son principalmente divisiones de ese gradiente, sin demostrar tipos discretos. R2 K=2 merece continuar como resumen exploratorio parsimonioso; K=4 añade resolución y presenta una peor cola de estabilidad. No hay evidencia suficiente para imponer cuatro a seis perfiles definitivos ni reemplazar automáticamente C o B.

## Cobertura y soporte antes de entrenar

Hay **{coverage['available_profiles']:,} perfiles H/M disponibles**, {coverage['complete_profiles']:,} con tres tasas definidas y **{coverage['eligible_profiles']:,} con soporte en las tres coordenadas**, correspondientes a **{coverage['eligible_municipalities']:,} municipios** y LN={coverage['eligible_LN']:,} ({pct(coverage['eligible_LN_fraction'])} del LN nacional). En {coverage['both_sexes_municipalities']:,} municipios entran ambos sexos y en {coverage['one_sex_municipalities']} entra uno; {coverage['no_eligible_municipalities']} no aportan ningún perfil elegible. No se interpreta la cobertura nominal alta como representatividad territorial completa.

{table(counts,['SEXO','available','defined','eligible','LN'],['SEXO','Perfiles disponibles','Tres tasas definidas','Elegibles','LN disponible 18–100'])}

El C broad anterior tenía {coverage['previous_c_municipalities']:,} municipios elegibles, LN municipal total={coverage['previous_c_LN']:,} y LN núcleo H/M 18–100={coverage['previous_c_core_LN']:,}. La comparación de alcance usa ese núcleo para evitar mezclar edades/categorías. Los {coverage['one_sex_municipalities']} municipios adicionales se representan parcialmente: no recuperan automáticamente un perfil territorial de ambos sexos. El corte preventivo definido antes de entrenar era caída >5 pp en municipios o >1 pp de LN respecto al núcleo C; no se activó. No se relajaron umbrales.

Los criterios siguen siendo LN≥100, SV+NV≥100 y filas fuente≥5 en **cada** banda. Las filas fuente son celdas, no cinco secciones independientes ni un tamaño de muestra de votantes. NS alto no excluye del principal. Cada perfil conserva los cuatro conteos por banda, denominadores, NS/LN, soporte, claves textuales, sexo y marco distrital. Las tasas NULL no se imputan; los pendientes conservan etiquetas NULL. Las coordenadas presentes conocidas permanecen en referencia aunque el perfil completo no sea elegible.

Se conservan {len(full)-len(main):,} perfiles pendientes: {int((~full.complete_profile).sum())} con alguna tasa no definida y {int((full.complete_profile&~full.is_eligible).sum())} definidos pero sin soporte en las tres coordenadas. Los motivos y soporte por banda se guardan por observación, sin filtros permanentes.

{table(pd.DataFrame(quality),['scope','profiles','LN','null_profiles','high_ns_coordinates','ns_nominal','ns_q1','ns_median','ns_q3'],['Alcance','Perfiles','LN','Perfiles NULL','Alguna banda NS≥10 %','NS/LN agregado','Q1 NS/LN','Mediana','Q3'])}

Los 136 municipios sin representación se localizan en metadata/unrepresented_municipalities.parquet; metadata/state_coverage.csv describe las 32 entidades. SEXO=2, edades 101+ y sus 105 filas fuente/LN de la categoría de sexo se conservan en la referencia broad completa, sin integrarse a H/M ni inventar tasas; no entran en esta matriz comparable de tres bandas. La base exacta anterior sigue intacta y trazable.

Entidades con menor cobertura nominal dentro del núcleo H/M 18–100 (denominador distinto del LN nacional completo):

{table(pd.DataFrame(states).sort_values('nominal_fraction').head(8),['EDOCVE','state_name_label','profiles','municipalities','eligible_LN','nominal_fraction'],['Entidad','Nombre','Perfiles','Municipios','LN elegible','Fracción LN del núcleo estatal'])}

{image('coverage.png','Cobertura municipal y nominal')}

## Construcción de nivel y forma

Las tasas 18–34, 35–59 y 60–100 se verificaron contra c_broad/cell_metadata.parquet y sus seis columnas originales. La referencia nacional por intervalo/sexo es ΣSV/Σ(SV+NV), calculada con todos los conteos antes de seleccionar soporte. No se promedian tasas de municipios para obtenerla. Para cada perfil, d=(d₁,d₂,d₃) son las diferencias nacionales, m=(d₁+d₂+d₃)/3 y s=d−m·1.

**m no es participación agregada**: esta última es ΣSV/Σ(SV+NV), con denominadores distintos por banda y una referencia contextual distinta. Se guardan ambas. Los tres intervalos tienen igual peso conceptual en m, independientemente de su anchura o LN. s suma cero y tiene dos grados de libertad. Se usa una base fija ortonormal Q, no un PCA aprendido: q₁=(d₁−d₂)/√2 y q₂=(d₁+d₂−2d₃)/√6. ||d||²=3m²+||q||² y s=qQᵀ. Los valores s de las tres bandas se conservan para interpretar curvas.

- **R1:** tres diferencias, centradas por su media poblacional y divididas por una sola escala RMS del vector. Preserva distancia euclídea con igual peso de bandas. No estandariza cada banda por separado. En el universo elegible, el nivel aporta **{pct(parameters['level_variance_fraction'])}** de la varianza total de d.
- **R2:** retira el promedio de cada observación; guarda dos contrastes equivalentes a la forma de tres bandas. Sólo centra globalmente los contrastes y aplica una escala RMS al bloque. No divide cada fila por su norma: conserva amplitud de las diferencias. Es invariante a añadir una constante a las tres diferencias de una observación. La edad es nombre de coordenada, no edad media numérica.
- **R3:** un bloque de nivel m con DE poblacional y un bloque de forma con RMS total; cada uno recibe 50 % de varianza a priori. No repite las tres diferencias junto con m. El peso es predefinido, no elegido por Silhouette. La contribución entre clusters puede diferir de 50 %.

Las escalas se ajustan sólo sobre los mismos {len(main):,} elegibles; cada remuestra las reajusta sólo in-bag. R2 puede conservar asociación indirecta con nivel o sexo si éstos se relacionan con la forma, aunque no entren como coordenadas. No se introduce edad media, TIPOSEC, identidad territorial ni SEXO como magnitud de distancia. Se da igual peso a cada perfil; un municipio con ambos sexos aporta dos observaciones y uno parcialmente cubierto aporta una.

## Experimento principal acotado

Se ejecutan R1/R2/R3 × K=2…6 × semillas 17/42/2024: **45 ajustes**, cada uno con {self.config['n_init']} arranques k-means++, máximo {self.config['max_iter']} iteraciones, parada con etiquetas estables y comprobación de K grupos no vacíos. K=6 es sensibilidad. Se conserva cada modelo y sus inicializaciones, SSE, convergencia, tiempos y centroides. No se cambian segmentos para mejorar índices.

Silhouette es **aproximado**, con {self.config['anchor_count']} anclas uniformes reproducibles compartidas; cada ancla se compara contra todos los elegibles mediante bloques de 32×N. Se guarda su error Monte Carlo. DB usa todos los perfiles. No se construye matriz N×N ni se generan gráficas durante ajustes. La memoria del buffer de distancias es aproximadamente {32*len(main)*8/2**20:.2f} MiB, más matrices/indicadores; working set y pico observados por API Windows constan en cada checkpoint (no son una garantía de cota máxima). Los segundos por modelo y etapa se registran. Las métricas de geometrías distintas no clasifican universalmente utilidad.

{table(summary,['representation','k','silhouette','db','smallest_cluster','level_explained','shape_explained','between_level_share','sex_purity','seed_ari_min'],['Representación','K','S aproximado','DB','Grupo mínimo medio','R² nivel','R² forma','Nivel/separación','Pureza sexo','ARI semillas mín.'])}

Los R² son fracciones de varianza descriptiva explicada por etiquetas, sin validación predictiva ni causalidad. R² forma usa la suma de cuadrados de los dos contrastes; nivel/separación mide su contribución real en el espacio del ajuste. R2 fuerza contribución directa de nivel cero por construcción, pero no fuerza R² nivel cero. La menor SSE entre semillas representa cada configuración/K sin elegir un K definitivo.

{image('metrics_by_k.png','Métricas por K')}

{image('level_and_shape.png','Nivel y forma originales; proyección parcial')}

Un contraste fijo entre jóvenes y mayores, (d₁−d₃)/√2, concentra **{pct(direction.shape_variance_fraction.iloc[0])}** de la varianza de forma; la curvatura (d₁−2d₂+d₃)/√6 aporta {pct(direction.shape_variance_fraction.iloc[1])}. Su correlación es {direction.contrast_correlation.iloc[0]:.4f}. Esta rotación ortonormal es sólo un diagnóstico de las mismas dos dimensiones: no se entrena otro modelo ni se hace reducción de dimensión. Un gradiente predominante puede producir particiones reproducibles aunque no existan poblaciones discretas; este piloto no prueba multimodalidad.

{table(direction,['contrast','mean_pp','sd_pp','shape_variance_fraction'],['Contraste fijo','Media (pp)','DE (pp)','Fracción de varianza de forma'])}

{image('shape_space.png','Plano completo de forma y densidad sin etiquetas')}

## Curvas y composición

{candidate_charts}

Las curvas muestran diferencias relativas originales, forma tras retirar nivel y tasas absolutas medias. Las medias de perfiles dan peso uno a municipio/sexo; la tasa agregada por banda usa conteos sumados y se guarda separadamente. Una forma positiva en jóvenes y negativa en mayores significa desvío respecto al nivel relativo de ese perfil, no que la participación absoluta juvenil sea mayor que la de mayores.

{table(candidate_profiles,['representation','k','cluster','observations','municipalities','LN','nominal_fraction','women_fraction','participation_observed','relative_level','unspecified_rate','high_ns_fraction'],['Representación','K','Etiqueta local','Perfiles','Municipios','LN','Fracción LN entrenado','Fracción mujeres','Participación agregada','Nivel relativo medio','NS/LN','Alguna banda NS alto'])}

Forma media en puntos porcentuales para los controles R2 K=2 y K=4, usando la semilla de menor SSE de cada K:

{table(shape_table,['k','cluster',*BANDS],['K','Etiqueta local','18–34 (pp)','35–59 (pp)','60–100 (pp)'])}

Con K=2 aparece un contraste relativo favorable a jóvenes frente a mayores y otro en sentido inverso. No significa que los jóvenes siempre voten más: la tasa absoluta media de cada banda figura en las gráficas. K=4 subdivide principalmente intensidades de esa inclinación; aumenta R² forma de {pct(shape_k2.shape_explained)} a {pct(shape_k4.shape_explained)}, con menor Silhouette ({shape_k2.silhouette:.4f} frente a {shape_k4.silhouette:.4f}) dentro del mismo espacio. No demuestra cuatro mecanismos electorales. El R² nivel de R2 K=2 es {pct(shape_k2.level_explained)}: retirar nivel de la distancia no elimina su asociación con forma.

Las diferencias de composición por sexo y de NS entre clusters exigen revisión sustantiva. Se usa la misma referencia nacional específica por sexo, pero no se garantiza independencia de sexo, cobertura o tamaño territorial. No se ejecutó aquí una sensibilidad de pesos o un ajuste sin NS alto: los 999 perfiles con alguna coordenada NS≥10 % permanecen en el principal. No se interpreta su asociación como causalidad.

Cada observación contiene las tres bandas: no existe una distribución de etiquetas de edad por observación como en B. La composición etaria se describe con LN por banda en cluster_curves.csv, no inventando edades individuales. Sexo y municipios representados se conservan para interpretar grupos. Un municipio puede aportar sus sexos a clusters diferentes; no sumar municipios de clusters como territorios únicos.

Entre los municipios con ambos sexos elegibles, la concordancia local se describe sin imponer etiquetas iguales a H/M:

{table(pair_summary,['representation','k','paired_municipalities','same_cluster','different_clusters','same_fraction'],['Representación','K','Municipios con H/M','Misma etiqueta local','Etiquetas distintas','Fracción con misma etiqueta'])}

{image('sex_composition.png','Composición por sexo')}

## Estabilidad municipal limitada

Se seleccionaron como máximo dos configuraciones después de D; metadata/candidate_selection.json registra criterios, candidatas y hash de evidencia. Se reutilizan las primeras {self.config['replicates']} membresías municipales anteriores: 1,981 de 2,477 municipios por submuestra sin reemplazo. Entran juntos ambos sexos elegibles de un municipio. No se reconstruyen perfiles ausentes ni se mezclan municipios para crear observaciones.

ARI OOB compara etiquetas proyectadas en municipios fuera del entrenamiento frente al mejor ajuste completo de la misma representación/K. La referencia nacional permanece fija y contiene información de todo 2024: no es validación predictiva independiente de ese contexto nacional. Las escalas y centroides sí se ajustan sin OOB. Los porcentajes de cambio se alinean por máximo solapamiento; etiquetas numéricas no tienen orden o identidad propia.

{table(robust,['representation','k','median','q10','minimum','below_90','maximum_change'],['Representación','K','ARI OOB mediana','q10','Mínimo','Muestras <0.90','Máx. fracción cambio'])}

{table(stability.sort_values('ari_oob').head(6),['representation','k','replicate','ari_oob','ari_inbag','oob_changed_fraction'],['Representación','K','Muestra','ARI OOB','ARI in-bag','Cambio OOB alineado'])}

{image('municipality_stability.png','Estabilidad y cambio de patrones')}

Se conservan coberturas de cada muestra, pertenencias, etiquetas/proyecciones y cambios RMS de las curvas de forma alineadas (pp). Diez submuestras sólo aportan un diagnóstico exploratorio: no prueban estabilidad general, grupos naturales o ausencia de sesgo por NS/soporte. No se entrenaron todas las combinaciones mediante remuestreo.

{stability_text}

Las submuestras contienen {resampling_coverage.training_profiles.min():,}–{resampling_coverage.training_profiles.max():,} perfiles de {resampling_coverage.training_municipalities.min():,}–{resampling_coverage.training_municipalities.max():,} municipios elegibles, y {pct(resampling_coverage.fraction_eligible_LN.min())}–{pct(resampling_coverage.fraction_eligible_LN.max())} del LN elegible completo. Quedan {resampling_coverage.oob_profiles.min():,}–{resampling_coverage.oob_profiles.max():,} perfiles OOB. El cambio RMS máximo de los centros de forma alineados es {changed_shapes.shape_change_RMS_pp.max():.3f} pp; un centro medio poco desplazado no garantiza etiquetas individuales estables. La peor muestra se conserva junto con las demás, sin descartarla para mejorar el resumen.

## Comparación con el C territorial anterior

El C anterior tenía una fila por municipio y seis tasas H/M. Aquí hay una fila por municipio/sexo y tres tasas con referencia nacional explícita; las etiquetas no se comparan mediante ARI entre unidades incompatibles. Los índices internos tampoco tienen la misma geometría. Como antecedente descriptivo, C broad estandarizado daba:

{table(old,['k','silhouette','between_level_share','between_shape_share','level_explained','shape_explained'],['K previo','S previo','Nivel/separación previo','Forma/separación previa','R² nivel previo','R² forma previa'])}

La forma anterior incluía las seis coordenadas de edad/sexo y no es idéntica a los dos contrastes actuales; no restar sus R² como si midieran exactamente lo mismo. En R1 actual, K=2 aporta {pct(r1.between_level_share)} de separación de nivel; R2 permite examinar forma independientemente de ese término, con asociación residual de nivel cuantificada arriba. Ésta es la aportación metodológica nueva, no una demostración automática de mejores perfiles.

## Conclusiones y decisiones pendientes

1. **Patrones o niveles:** sí hay diferencias descriptivas entre edades en R2, principalmente un gradiente jóvenes–mayores ({pct(direction.shape_variance_fraction.iloc[0])} de varianza de forma). R1 K=2 sigue separando niveles: {pct(r1.between_level_share)} de la separación corresponde a nivel. R3 conserva entre {pct(r3.between_level_share.min())} y {pct(r3.between_level_share.max())} de separación en ese bloque por diseño mixto. No se descubren tipos individuales ni se prueba que el gradiente tenga cortes naturales.
2. **Interpretación:** separar nivel y forma mejora la lectura del patrón relativo. R2 diferencia trayectorias que una tasa total no describe; K=4 añade principalmente intensidad al contraste, no cuatro formas cualitativas demostradas. El promedio simple no sustituye la participación agregada y las tasas absolutas siguen siendo necesarias.
3. **Cobertura:** {coverage['eligible_municipalities']:,} municipios y {pct(coverage['eligible_LN_fraction'])} del LN, con {coverage['one_sex_municipalities']} municipios parcialmente representados. La cobertura no cae frente al núcleo C broad, pero quedan municipios y perfiles pendientes.
4. **Estabilidad:** {stability_text} K=2 tiene concordancia suficiente para continuar como exploración; K=4 requiere cautela por su peor muestra. Semillas concordantes no sustituyen estabilidad municipal, y diez submuestras no bastan para adopción definitiva.
5. **Cuatro a seis perfiles:** no están justificados como rango obligatorio. En R2 el máximo S de anclas está en K={int(best_shape.k)} ({best_shape.silhouette:.4f}); el gradiente y la estabilidad limitada favorecen comenzar con menos grupos para resumir, manteniendo K=4 como detalle experimental. Los mayores R² de K altos son esperables al refinar una partición y no prueban nuevos perfiles. K=6 sigue siendo sensibilidad; no se selecciona K definitivo.
6. **Novedad:** pasa de seis tasas municipales dominadas por nivel a trayectorias relativas por sexo y forma explícita. Cambia la unidad y la pregunta; no reemplaza directamente al C o B anteriores ni justifica inferencias individuales.
7. **Uso en ParticipaMX:** sí merece continuar R2 como vista exploratoria de patrones relativos por edad y sexo, con R1/C/B como controles de nivel y de otras unidades. No se recomienda publicar cuatro a seis perfiles ciudadanos definitivos ni sustituir automáticamente C territorial. Para una presentación es más defendible mostrar curvas, denominadores y un resumen parsimonioso provisional, reconociendo el gradiente continuo y las exclusiones por soporte. Antes de adoptar etiquetas deben contrastarse pesos por municipio, NS elevado, sensibilidad de bandas/escala y referencias, sexos y validación electoral. No se atribuye a esta entrega una robustez que no se probó.

## Recuperación, integridad y reproducción

Checkpoints A–F incluyen hashes, resumen, duración, versiones y memoria aproximada. Los modelos y remuestras tienen bundles NPZ/JSON con marcador verificable individual: se omiten al reanudar, aunque la etapa no hubiera terminado. Los temporales sólo se publican por reemplazo atómico tras validar lectura. Un lock exclusivo impide duplicar procesos; locks muertos se archivan y procesos no verificables bloquean otro inicio. Los archivos incompletos propios se preservan en incomplete/; un hash incorrecto de un checkpoint detiene la ejecución sin sobrescribirlo. No se repiten automáticamente pasos costosos validados.

Se verificaron referencias por conteos, unicidad, claves de texto, LN=SV+NV+NS, igualdad con C broad, elegibilidad de ambos sexos, suma cero/identidades de forma, finitud, centroides/SSE por groupby independiente, conservación por cluster, NULL de pendientes y lectura posterior de salidas. Los hashes de {len(self.state['protected_hashes']):,} archivos previos se comprueban antes de finalizar. No se modificaron datos, informes anteriores, ZIP, frontend ni se crearon commits. No se procesaron CSV originales ni la base histórica. Scikit-learn/SciPy siguen sin usarse; las pruebas NumPy y matemáticas no sustituyen un contraste de biblioteca independiente.

```powershell
.venv/Scripts/python.exe analysis/scripts/evaluate_participation_patterns.py --until D
.venv/Scripts/python.exe analysis/scripts/evaluate_participation_patterns.py --candidates {explicit}
.venv/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_evaluate_participation_patterns.py
```

El segundo comando continúa A–D sin repetirlos. Una ejecución posterior verifica _SUCCESS y termina sin entrenar. Para otro experimento usar --output, --charts y --report nuevos. Un fallo queda en state.json con traceback; no se marca validado hasta completar F. Reference/ conserva perfiles, celdas, referencia nacional, broad completa y pendientes; features/ matrices y contrato; models/ los 45 ajustes; resampling/ las candidatas; assignments/ etiquetas completas; metadata/ evidencia y checkpoints. Las referencias y vistas alternativas no deben sumarse entre sí.
'''
        self.report.parent.mkdir(parents=True,exist_ok=True);atomic_bytes(self.report,text.encode('utf-8'))

    def run(self,until,candidates):
        manifest_path=self.output/'metadata/run_manifest.json'
        if (self.output/'_SUCCESS').exists():
            marker=json.loads((self.output/'_SUCCESS').read_text());manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
            require(marker['manifest_sha256']==file_hash(manifest_path) and manifest['status']=='validated','Marcador final inconsistente.')
            for relative,digest in manifest['artifact_hashes'].items():require(file_hash(self.root/relative)==digest,'Artefacto final alterado.')
            print('Experimento validado: se verificaron artefactos; cero ajustes nuevos.',flush=True);return
        current_stage='A'
        try:
            for stage,method in [('A',self.stage_a),('B',self.stage_b),('C',self.stage_c),('D',self.stage_d)]:
                current_stage=stage
                if self.valid_stage(stage):print(f'Etapa {stage}: checkpoint verificado, se omite.',flush=True)
                else:method()
                if stage=='A':
                    coverage=json.loads((self.output/'metadata/coverage.json').read_text())
                    if not coverage['training_allowed']:
                        self.state['status']='stopped_for_coverage';write_json(self.state_path,self.state)
                        atomic_bytes(self.report,('# Diagnóstico de cobertura\n\nNo se entrenaron modelos: la puerta preventiva de cobertura no se cumple.\n\n'+json.dumps(coverage,ensure_ascii=False,indent=2)).encode('utf-8'));return
                if until==stage:return
            selected=self.choose_candidates(candidates)
            for stage,method in [('E',lambda:self.stage_e(selected)),('F',self.stage_f)]:
                current_stage=stage
                if self.valid_stage(stage):print(f'Etapa {stage}: checkpoint verificado, se omite.',flush=True)
                else:method()
                if until==stage and stage!='F':return
            self.state['status']='validated';self.state['finished']=utc();write_json(self.state_path,self.state)
            files={str(path.relative_to(self.root)):file_hash(path) for base in [self.output,self.charts] for path in base.rglob('*')
                if path.is_file() and path not in [manifest_path,self.output/'_RUNNING.json',self.output/'_SUCCESS'] and '.tmp.' not in path.name}
            files[str(self.report.relative_to(self.root))]=file_hash(self.report)
            manifest=dict(status='validated',configuration=self.config,stages=self.state['stages'],candidates=self.state['candidates'],
                main_models=45,municipal_models=len(selected)*self.config['replicates'],protected_hashes=self.state['protected_hashes'],
                artifact_hashes=files,script_sha256=file_hash(Path(__file__)),test_sha256=file_hash(self.root/'analysis/scripts/test_evaluate_participation_patterns.py'))
            write_json(manifest_path,manifest);write_json(self.output/'_SUCCESS',dict(manifest_sha256=file_hash(manifest_path)))
            print(f'VALIDADO: {self.report}',flush=True)
        except Exception as error:
            import traceback
            self.state['status']='failed';self.state['errors'].append(dict(stage=current_stage,at=utc(),error=repr(error),traceback=traceback.format_exc()))
            write_json(self.state_path,self.state);raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output',type=Path,default=Path('data/processed/participation_pattern_review'))
    parser.add_argument('--charts',type=Path,default=Path('analysis/charts/participation_pattern_review'))
    parser.add_argument('--report',type=Path,default=Path('analysis/reports/participation_pattern_review.md'))
    parser.add_argument('--until',choices=list('ABCDEF'),default='F')
    parser.add_argument('--candidates',nargs='*',default=[])
    parser.add_argument('--anchor-count',type=int,default=512)
    parser.add_argument('--n-init',type=int,default=10)
    parser.add_argument('--replicates',type=int,default=10)
    args=parser.parse_args();require(args.anchor_count>=2 and args.n_init>=2 and 2<=args.replicates<=10,'Parámetros no válidos.')
    root=args.root.resolve();output=(root/args.output).resolve()
    require(output.is_relative_to(root/'data/processed'),'Destino fuera del proyecto.')
    config=dict(anchor_count=args.anchor_count,n_init=args.n_init,replicates=args.replicates,max_iter=1000,ks=KS,seeds=SEEDS)
    with experiment_lock(output):Experiment(root,output,root/args.charts,root/args.report,config).run(args.until,args.candidates)


if __name__=='__main__':main()
