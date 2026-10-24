"""Compara bibliotecas de clustering sobre la misma matriz electoral R2.

Etapas recuperables A–I; modelos y métricas individuales verificables.
No modifica fuentes ni experimentos anteriores. Ejecutar en el entorno aislado.
"""
from __future__ import annotations

import os
for thread_variable in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
    os.environ[thread_variable]='1'

import argparse
import hashlib
import importlib
import importlib.metadata
import inspect
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
import warnings
from itertools import combinations

import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[2]/'.venv_pattern_algorithms/matplotlib_cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from matplotlib.ticker import PercentFormatter

from clean_data import require,file_hash
from build_cluster_features import snapshot_inputs
from build_descriptive import METRICS,markdown_table,pct
from evaluate_participation_patterns import (atomic_bytes,write_json,write_table,save_figure,
    experiment_lock,memory_estimate,utc,KEYS,MUNICIPAL_KEYS,BANDS,SUFFIXES,DELTA_COLUMNS,
    SHAPE_COLUMNS,transform_patterns)

SEEDS=[17,42,2024]
FEATURES=['shape_contrast_1','shape_contrast_2']
GMM_SETTINGS=dict(n_init=5,max_iter=1000,tol=1e-4,reg_covar=1e-6,init_params='kmeans')


def probe_dependencies():
    """Importa bibliotecas reales; no instala ni simula algoritmos."""
    result=dict(executable=sys.executable,python=sys.version,architecture=platform.architecture(),machine=platform.machine(),imports={})
    for name in ['numpy','pandas','pyarrow','matplotlib','scipy','sklearn','joblib','kmedoids']:
        try:
            module=importlib.import_module(name)
            try:version=importlib.metadata.version('scikit-learn' if name=='sklearn' else name)
            except importlib.metadata.PackageNotFoundError:version=getattr(module,'__version__',None)
            result['imports'][name]=dict(available=True,version=version)
        except Exception as error:result['imports'][name]=dict(available=False,error=repr(error))
    try:
        from sklearn.cluster import HDBSCAN
        from sklearn.mixture import GaussianMixture
        from scipy.cluster.hierarchy import linkage
        result['required_algorithms']=dict(available=True,hdbscan_signature=str(inspect.signature(HDBSCAN)))
    except Exception as error:result['required_algorithms']=dict(available=False,error=repr(error))
    return result


def posterior_summary(probabilities):
    """Incertidumbre condicional al modelo, nunca certeza sobre personas."""
    probabilities=np.asarray(probabilities,float)
    require(probabilities.ndim==2 and np.isfinite(probabilities).all(),'Posteriores inválidas.')
    require(np.allclose(probabilities.sum(axis=1),1) and probabilities.min()>=0,'Posteriores no suman uno.')
    maximum=probabilities.max(axis=1);k=probabilities.shape[1]
    entropy=-(probabilities*np.log(np.maximum(probabilities,1e-300))).sum(axis=1)
    return dict(ambiguous_80=float((maximum<.8).mean()),ambiguous_60=float((maximum<.6).mean()),
        ambiguous_90=float((maximum<.9).mean()),mean_max_posterior=float(maximum.mean()),
        mean_normalized_entropy=float(entropy.mean()/np.log(k)) if k>1 else 0.)


def label_metrics(values,labels,profiles,baseline=None):
    """Métricas exactas por bloques sobre asignados; ruido se informa aparte."""
    from sklearn import config_context
    from sklearn.metrics import silhouette_samples,davies_bouldin_score,adjusted_rand_score
    labels=np.asarray(labels);assigned=labels>=0;unique,counts=np.unique(labels[assigned],return_counts=True)
    n=int(assigned.sum());total_ln=profiles.LN.sum()
    result=dict(groups=len(unique),assigned=n,unassigned=int((~assigned).sum()),noise_fraction=float((~assigned).mean()),
        sizes=json.dumps(dict(zip(map(str,unique),map(int,counts)))),smallest_cluster=int(counts.min()) if len(counts) else 0,
        assigned_municipalities=profiles.loc[assigned].groupby(MUNICIPAL_KEYS).ngroups,
        assigned_municipality_fraction=profiles.loc[assigned].groupby(MUNICIPAL_KEYS).ngroups/profiles.groupby(MUNICIPAL_KEYS).ngroups,
        assigned_LN=int(profiles.loc[assigned,'LN'].sum()),assigned_LN_fraction=float(profiles.loc[assigned,'LN'].sum()/total_ln),
        assigned_national_LN_fraction=float(profiles.loc[assigned,'LN'].sum()/98330348),
        silhouette=np.nan,db=np.nan,negative_silhouette_fraction=np.nan,ari_vs_kmeans=np.nan,
        metric_population=n,silhouette_method='exact_assigned_only_blocked_8MiB')
    if 2<=len(unique)<n:
        with config_context(working_memory=8):scores=silhouette_samples(values[assigned],labels[assigned],metric='euclidean')
        result.update(silhouette=float(scores.mean()),db=float(davies_bouldin_score(values[assigned],labels[assigned])),
            negative_silhouette_fraction=float((scores<0).mean()))
        if baseline is not None:result['ari_vs_kmeans']=float(adjusted_rand_score(np.asarray(baseline)[assigned],labels[assigned]))
    return result


def common_partition_stability(reference,alternative):
    """ARI sobre comunes; distingue ruido de una concordancia trivial."""
    from sklearn.metrics import adjusted_rand_score
    reference=np.asarray(reference);alternative=np.asarray(alternative)
    both=(reference>=0)&(alternative>=0);union=(reference>=0)|(alternative>=0)
    meaningful=both.sum()>1 and len(np.unique(reference[both]))>1 and len(np.unique(alternative[both]))>1
    return dict(ari_common_all=float(adjusted_rand_score(reference,alternative)),
        ari_common_both_assigned=float(adjusted_rand_score(reference[both],alternative[both])) if meaningful else np.nan,
        both_assigned=int(both.sum()),assignment_jaccard=float(both.sum()/union.sum()) if union.any() else np.nan,
        noise_status_agreement=float(np.mean((reference<0)==(alternative<0))),
        reference_groups=len(np.unique(reference[reference>=0])),sample_groups=len(np.unique(alternative[alternative>=0])))


def aligned_changes(reference,alternative):
    """Compara etiquetas nominales maximizando solapamiento, sin ordenar clusters."""
    from scipy.optimize import linear_sum_assignment
    reference=np.asarray(reference);alternative=np.asarray(alternative)
    left=np.unique(reference);right=np.unique(alternative)
    require(len(left)==len(right) and (left>=0).all() and (right>=0).all(),'Alineación sólo para soluciones completas con igual K.')
    contingency=np.array([[np.sum((reference==a)&(alternative==b)) for b in right] for a in left])
    rows,columns=linear_sum_assignment(-contingency)
    mapping=dict(zip(right[columns],left[rows]));aligned=np.array([mapping[v] for v in alternative])
    return reference!=aligned


def describe_groups(profiles,labels,model_id):
    """Conserva ruido como -1; concilia conteos sin mezclar niveles."""
    rows=[];curves=[];labels=np.asarray(labels)
    for cluster in np.unique(labels):
        part=profiles.loc[labels==cluster]
        row=dict(model_id=model_id,cluster=int(cluster),observations=len(part),municipalities=part.groupby(MUNICIPAL_KEYS).ngroups,
            women_fraction=float(part.SEXO.eq('1').mean()),relative_level=float(part.relative_level.mean()),
            high_ns_fraction=float(part.has_high_ns_coordinate.mean()),unspecified_rate=float(part.NS.sum()/part.LN.sum()),
            participation_observed=float(part.SV.sum()/part.specified_count.sum()),**{c:int(part[c].sum()) for c in METRICS})
        rows.append(row)
        for band,suffix in zip(BANDS,SUFFIXES):
            sv,nv=int(part['SV_'+suffix].sum()),int(part['NV_'+suffix].sum())
            curves.append(dict(model_id=model_id,cluster=int(cluster),age_band=band,
                mean_rate=float(part['rate_'+suffix].mean()),mean_delta=float(part['delta_'+suffix].mean()),
                mean_shape=float(part['shape_'+suffix].mean()),aggregate_rate=sv/(sv+nv) if sv+nv else np.nan,
                LN=int(part['LN_'+suffix].sum()),SV=sv,NV=nv,NS=int(part['NS_'+suffix].sum())))
    summary=pd.DataFrame(rows);require(np.array_equal(summary[METRICS].sum().to_numpy(),profiles[METRICS].sum().to_numpy()),'Conteos por grupo no concilian.')
    return summary,pd.DataFrame(curves)


class Comparison:
    def __init__(self,root,output,charts,report,replicates=10):
        self.root,self.output,self.charts,self.report=[Path(p).resolve() for p in [root,output,charts,report]]
        require(self.output.is_relative_to(self.root/'data/processed') and self.charts.is_relative_to(self.root/'analysis/charts') and self.report.is_relative_to(self.root/'analysis/reports'),'Destinos inválidos.')
        self.source=self.root/'data/processed/participation_pattern_review'
        self.state_path=self.output/'metadata/state.json';self.replicates=replicates
        self.dependencies=probe_dependencies()
        require(self.dependencies['required_algorithms']['available'],'Faltan bibliotecas principales. Usar el entorno aislado; no se repetirá K-Means como sustituto.')
        if self.state_path.exists():
            self.state=json.loads(self.state_path.read_text(encoding='utf8'))
            require(self.state['replicates']==replicates,'Parámetros distintos; elegir destinos nuevos.')
            require(self.state['charts']==str(self.charts) and self.state['report']==str(self.report),'Destinos de reanudación distintos.')
            require(self.state['dependencies']['imports']==self.dependencies['imports'],'Versiones distintas de los checkpoints.')
            self.verify_protected()
        else:
            existing=[p for p in self.output.rglob('*') if p.is_file() and p.name!='_RUNNING.json' and 'bootstrap' not in p.parts]
            require(not existing and not self.charts.exists() and not self.report.exists(),'Destino previo sin estado verificable; no se sobrescribe.')
            protected=snapshot_inputs(self.root,self.output,self.charts)
            for base in [self.root/'analysis/scripts',self.root/'src']:
                for path in base.rglob('*'):
                    if path.is_file() and '__pycache__' not in path.parts and path.name not in ['compare_pattern_algorithms.py','test_compare_pattern_algorithms.py']:
                        protected[str(path)]=file_hash(path)
            for path in [self.root/'.gitignore',self.root/'.venv/pyvenv.cfg']:
                protected[str(path)]=file_hash(path)
            self.state=dict(started=utc(),status='running',replicates=replicates,dependencies=self.dependencies,
                protected_hashes=protected,stages={},errors=[],charts=str(self.charts),report=str(self.report))
            write_json(self.state_path,self.state)

    def verify_protected(self):
        for path,digest in self.state['protected_hashes'].items():require(file_hash(path)==digest,f'Archivo previo alterado: {path}')

    def valid_stage(self,stage):
        path=self.output/f'metadata/checkpoint_{stage}.json'
        if not path.exists():return False
        checkpoint=json.loads(path.read_text(encoding='utf8'))
        require(checkpoint['status']=='complete','Checkpoint incompleto.')
        for relative,digest in checkpoint['artifacts'].items():require(file_hash(self.root/relative)==digest,f'Artefacto alterado: {relative}')
        return True

    def checkpoint(self,stage,paths,started,summary):
        record=dict(status='complete',stage=stage,finished=utc(),seconds=time.monotonic()-started,
            memory=memory_estimate(),summary=summary,versions=self.dependencies['imports'],script_sha256=file_hash(Path(__file__)),
            artifacts={str(p.relative_to(self.root)):file_hash(p) for p in paths})
        write_json(self.output/f'metadata/checkpoint_{stage}.json',record)
        self.state['stages'][stage]=dict(seconds=record['seconds'],summary=summary);write_json(self.state_path,self.state)
        print(f'Etapa {stage}: {summary}',flush=True)

    def table(self,relative,frame):
        path=self.output/relative
        if path.exists():
            if path.suffix=='.parquet':pd.testing.assert_frame_equal(pd.read_parquet(path),frame,check_dtype=False)
            else:require(path.read_bytes()==frame.to_csv(index=False).encode('utf-8-sig'),f'Tabla parcial distinta: {path}')
        else:write_table(path,frame)
        return path

    def bundle(self,model_id,values,parameters,callback):
        """Un modelo sólo es recuperable tras verificar su marcador individual."""
        import joblib
        folder=self.output/'models'/model_id;marker=folder/'_COMPLETE.json'
        fingerprint=hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()
        if marker.exists():
            manifest=json.loads(marker.read_text(encoding='utf8'))
            require(manifest['input_sha256']==fingerprint and manifest['parameters']==parameters,'Modelo de otra población/configuración.')
            for name,digest in manifest['files'].items():require(file_hash(folder/name)==digest,'Modelo incompleto o alterado.')
            with np.load(folder/'arrays.npz',allow_pickle=False) as stored:arrays={k:stored[k].copy() for k in stored.files}
            return joblib.load(folder/'model.joblib'),arrays,json.loads((folder/'details.json').read_text(encoding='utf8'))
        if folder.exists():
            archived=self.output/'incomplete'/f'{model_id.replace("/","_")}_{time.time_ns()}'
            archived.parent.mkdir(parents=True,exist_ok=True);folder.replace(archived)
        folder.mkdir(parents=True);started=time.monotonic()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always');model,arrays,details=callback()
        details.update(seconds=time.monotonic()-started,memory=memory_estimate(),warnings=[str(w.message) for w in caught])
        buffer=io.BytesIO();np.savez_compressed(buffer,**arrays);atomic_bytes(folder/'arrays.npz',buffer.getvalue())
        buffer=io.BytesIO();joblib.dump(model,buffer,compress=3);atomic_bytes(folder/'model.joblib',buffer.getvalue())
        write_json(folder/'details.json',details)
        with np.load(folder/'arrays.npz',allow_pickle=False) as stored:
            for name,value in arrays.items():require(np.array_equal(stored[name],value,equal_nan=True),'Modelo escrito distinto.')
        write_json(marker,dict(input_sha256=fingerprint,parameters=parameters,
            files={name:file_hash(folder/name) for name in ['arrays.npz','model.joblib','details.json']}))
        return model,arrays,details

    def bundle_paths(self,model_ids):
        return [self.output/'models'/model_id/name for model_id in model_ids for name in ['arrays.npz','model.joblib','details.json','_COMPLETE.json']]

    def load_model(self,model_id):
        import joblib
        return joblib.load(self.output/'models'/model_id/'model.joblib')

    def load_arrays(self,model_id):
        with np.load(self.output/'models'/model_id/'arrays.npz',allow_pickle=False) as stored:return {k:stored[k].copy() for k in stored.files}

    def data(self):
        profiles=pd.read_parquet(self.output/'reference/profiles.parquet');main=profiles[profiles.is_eligible].reset_index(drop=True)
        features=pd.read_parquet(self.output/'features/r2.parquet')
        require(features.row_id.equals(main.row_id),'Desalineación de matriz y metadatos.')
        return profiles,main,features[FEATURES].to_numpy(float)

    def stage_a(self):
        started=time.monotonic();manifest=json.loads((self.source/'metadata/run_manifest.json').read_text(encoding='utf8'))
        marker=json.loads((self.source/'_SUCCESS').read_text())
        require(marker['manifest_sha256']==file_hash(self.source/'metadata/run_manifest.json') and manifest['status']=='validated','R2 sin validar.')
        for relative,digest in manifest['artifact_hashes'].items():require(self.state['protected_hashes'][str(self.root/relative)]==digest,'Entrada R2 alterada.')
        paths=[]
        for name in ['reference/profiles.parquet','reference/national_reference.parquet','reference/broad_complete_reference.parquet','features/r2.parquet']:
            paths.append(self.table(name,pd.read_parquet(self.source/name)))
        full,main,values=self.data()
        require(len(full)==4954 and len(main)==4648 and main.groupby(MUNICIPAL_KEYS).ngroups==2341,'Población diferente.')
        require(main.LN.sum()==98153652 and np.isfinite(values).all() and values.shape==(4648,2),'Conteos o matriz diferentes.')
        require(full.row_id.is_unique and full.LN.eq(full.SV+full.NV+full.NS).all(),'Claves o conteos inválidos.')
        require(full[KEYS].map(lambda x:isinstance(x,str)).all().all(),'Identificadores no textuales.')
        parameters=json.loads((self.source/'metadata/parameters.json').read_text(encoding='utf8'))
        require(np.array_equal(values,transform_patterns(main,'r2',parameters)),'No es exactamente la matriz R2 validada.')
        national=pd.read_parquet(self.output/'reference/national_reference.parquet')
        require(np.allclose(national.national_rate,national.SV/(national.SV+national.NV)),'Referencia nacional incorrecta.')
        broad=pd.read_parquet(self.output/'reference/broad_complete_reference.parquet')
        require(broad.sex_2_source_rows.sum()==105 and broad.LN.sum()==98330348,'Referencia completa no conservada.')
        validation=dict(eligible_profiles=len(main),municipalities=main.groupby(MUNICIPAL_KEYS).ngroups,eligible_LN=int(main.LN.sum()),
            national_LN=98330348,pending_profiles=len(full)-len(main),matrix_sha256=hashlib.sha256(values.tobytes()).hexdigest(),
            feature_columns=FEATURES,ward_condensed_MiB=len(main)*(len(main)-1)*4/2**20,kmedoids_square_MiB=len(main)**2*8/2**20,
            ward_strategy='SciPy linkage sobre vectores: distancia condensada interna, sin cuadrado adicional.',
            kmedoids_strategy='Sólo si hay wheel nativo y presupuesto: único cuadrado euclídeo reutilizable, liberado antes de métricas.',
            weight='one_per_municipality_sex_profile',scale='Exactamente R2 previo; sin ajustar otro escalador.',parameters=parameters)
        for name,value in [('input_validation',validation),('dependency_validation',self.dependencies)]:
            path=self.output/f'metadata/{name}.json';write_json(path,value);paths.append(path)
        lock=subprocess.run([sys.executable,'-m','pip','freeze','--all'],capture_output=True,text=True,check=True)
        path=self.output/'metadata/requirements.lock.txt';atomic_bytes(path,lock.stdout.encode('utf8'));paths.append(path)
        self.checkpoint('A',paths,started,'Bibliotecas reales disponibles; R2 exacto 4,648×2, 2,341 municipios; pendientes preservados.')

    def stage_b(self):
        from sklearn.cluster import KMeans
        from sklearn.metrics import adjusted_rand_score
        started=time.monotonic();_,main,values=self.data();records=[];paths=[]
        for k in range(2,7):
            for seed in SEEDS:
                source=self.source/f'models/r2/k{k}/seed{seed}'
                manifest=json.loads((source/'_COMPLETE.json').read_text(encoding='utf8'))
                for name,digest in manifest['files'].items():require(file_hash(source/name)==digest,'K-Means previo alterado.')
                with np.load(source/'fit.npz',allow_pickle=False) as fit:labels,centers=fit['labels'].copy(),fit['centers'].copy()
                details=json.loads((source/'fit.json').read_text(encoding='utf8'))
                model_id=f'kmeans_k{k}_seed{seed}'
                model,arrays,info=self.bundle(model_id,values,dict(reused=True,k=k,seed=seed),
                    lambda labels=labels,centers=centers,details=details:(None,dict(labels=labels,centers=centers),dict(sse=details['inertia'],source=str(source.relative_to(self.root)),reused=True)))
                records.append(dict(model_id=model_id,algorithm='kmeans',configuration=f'k{k}',k=k,seed=seed,sse=info['sse']))
                paths.extend(self.bundle_paths([model_id]))
        first=self.load_arrays('kmeans_k2_seed17')
        def crosscheck():
            model=KMeans(n_clusters=2,init=first['centers'],n_init=1,tol=0,max_iter=1000,algorithm='lloyd',random_state=17).fit(values)
            ari=adjusted_rand_score(first['labels'],model.labels_)
            previous=json.loads((self.source/'models/r2/k2/seed17/fit.json').read_text())['inertia']
            require(ari==1 and abs(model.inertia_-previous)<1e-8,'Discrepancia con biblioteca independiente; revisar antes de comparar.')
            return model,dict(labels=model.labels_,centers=model.cluster_centers_),dict(ari=float(ari),previous_sse=previous,
                library_sse=float(model.inertia_),sse_difference=float(model.inertia_-previous),iterations=int(model.n_iter_),
                initialization='Mismos centroides finales previos: prueba de punto fijo; no replica k-means++ ni todos los mínimos.')
        self.bundle('kmeans_library_check',values,dict(k=2,init='previous_final_centers',tol=0,n_init=1),crosscheck)
        paths.extend(self.bundle_paths(['kmeans_library_check']))
        paths.append(self.table('metadata/kmeans_index.csv',pd.DataFrame(records)))
        self.checkpoint('B',paths,started,'15 soluciones previas reutilizadas (K=6 sensibilidad); un contraste independiente desde idénticos centros.')

    def fit_gmm(self,model_id,values,k,covariance,seed,starts=None):
        from sklearn.mixture import GaussianMixture
        parameters=dict(n_components=k,covariance_type=covariance,random_state=seed,**GMM_SETTINGS)
        if starts is not None:parameters['n_init']=starts
        def fit():
            model=GaussianMixture(**parameters).fit(values);posterior=model.predict_proba(values)
            return model,dict(labels=model.predict(values),posterior=posterior),dict(aic=float(model.aic(values)),bic=float(model.bic(values)),
                converged=bool(model.converged_),iterations=int(model.n_iter_),lower_bound=float(model.lower_bound_),**posterior_summary(posterior))
        return self.bundle(model_id,values,parameters,fit)

    def stage_c(self):
        started=time.monotonic();_,main,values=self.data();records=[];ids=[]
        for covariance in ['full','diag','tied']:
            for k in range(1,7):
                for seed in SEEDS:
                    model_id=f'gmm_{covariance}_k{k}_seed{seed}'
                    model,arrays,details=self.fit_gmm(model_id,values,k,covariance,seed);ids.append(model_id)
                    records.append(dict(model_id=model_id,algorithm='gmm',configuration=f'{covariance}_k{k}',k=k,covariance=covariance,seed=seed,**details))
                    print(f'GMM {covariance} K={k} semilla={seed}: BIC={details["bic"]:.2f}, converge={details["converged"]}.',flush=True)
        paths=self.bundle_paths(ids)+[self.table('metadata/gmm_index.csv',pd.DataFrame(records))]
        self.checkpoint('C',paths,started,'54 GMM reales: 1–6 componentes, tres covarianzas, tres semillas y cinco arranques.')

    def fit_hdbscan(self,model_id,values,min_cluster_size,min_samples,allow_single_cluster):
        from sklearn.cluster import HDBSCAN
        parameters=dict(min_cluster_size=min_cluster_size,min_samples=min_samples,allow_single_cluster=allow_single_cluster,
            metric='euclidean',algorithm='kd_tree',cluster_selection_method='eom',n_jobs=1,copy=True)
        def fit():
            model=HDBSCAN(**parameters).fit(values)
            details=dict(persistence_available=hasattr(model,'cluster_persistence_'),
                membership_strength_mean=float(model.probabilities_.mean()))
            if hasattr(model,'cluster_persistence_'):details['persistence']=model.cluster_persistence_.tolist()
            return model,dict(labels=model.labels_,membership_strength=model.probabilities_),details
        return self.bundle(model_id,values,parameters,fit)

    def stage_d(self):
        started=time.monotonic();_,main,values=self.data();records=[];ids=[]
        grid=[(m,s,True) for m in [50,100,200,400] for s in [10,30,60]]+[(50,10,False),(200,30,False)]
        for minimum,samples,single in grid:
            model_id=f'hdbscan_m{minimum}_s{samples}_single{int(single)}';ids.append(model_id)
            model,arrays,details=self.fit_hdbscan(model_id,values,minimum,samples,single)
            labels=arrays['labels'];groups=len(np.unique(labels[labels>=0]))
            records.append(dict(model_id=model_id,algorithm='hdbscan',configuration=model_id,k=groups,
                min_cluster_size=minimum,min_samples=samples,allow_single_cluster=single,**details))
            print(f'HDBSCAN m={minimum}, s={samples}, single={single}: {groups} grupos, ruido={np.mean(labels<0):.2%}.',flush=True)
        self.checkpoint('D',self.bundle_paths(ids)+[self.table('metadata/hdbscan_index.csv',pd.DataFrame(records))],started,
            'Rejilla HDBSCAN 12 parámetros permitiendo un grupo; dos controles de selección por defecto. Sin imponer K.')

    def fit_ward(self,model_id,values,ks):
        from scipy.cluster.hierarchy import linkage,cut_tree
        def fit():
            tree=linkage(values,method='ward',metric='euclidean',optimal_ordering=False)
            cuts=cut_tree(tree,n_clusters=ks)
            return dict(tree=tree),dict(tree=tree,**{f'labels_k{k}':cuts[:,i] for i,k in enumerate(ks)}),dict(condensed_MiB=len(values)*(len(values)-1)*4/2**20)
        return self.bundle(model_id,values,dict(method='ward',metric='euclidean',ks=ks),fit)

    def stage_e(self):
        started=time.monotonic();_,main,values=self.data()
        model,arrays,details=self.fit_ward('ward_tree',values,list(range(2,7)))
        tree=arrays['tree'];records=[]
        for k in range(2,7):
            before=float(tree[-k,2]);after=float(tree[-k+1,2])
            records.append(dict(model_id=f'ward_k{k}',bundle_id='ward_tree',label_field=f'labels_k{k}',algorithm='ward',configuration=f'k{k}',k=k,
                height_before=before,height_after=after,height_gap=after-before,height_ratio=after/before))
        self.checkpoint('E',self.bundle_paths(['ward_tree'])+[self.table('metadata/ward_index.csv',pd.DataFrame(records))],started,
            'Un árbol Ward, cortes K=2–6; 82.4 MiB de distancia condensada, sin cuadrado adicional.')

    def stage_f(self):
        started=time.monotonic();path=self.output/'metadata/kmedoids_status.json'
        if not self.dependencies['imports']['kmedoids']['available']:
            write_json(path,dict(status='not_run_missing_binary',reason='No hay implementación nativa instalada; no se implementa otra ni se bloquean las familias principales.'))
            self.checkpoint('F',[path],started,'K-Medoids pendiente por dependencia opcional.');return
        import kmedoids
        from scipy.spatial.distance import cdist
        _,main,values=self.data();required=len(values)**2*8
        require(required<=256*2**20,'K-Medoids supera presupuesto predefinido de 256 MiB para un cuadrado.')
        distances=cdist(values,values,metric='euclidean');records=[];ids=[]
        for k in [2,3,4]:
            for seed in SEEDS:
                model_id=f'kmedoids_k{k}_seed{seed}';ids.append(model_id)
                def fit(k=k,seed=seed):
                    trials=[];best=None
                    for start in range(3):
                        init_seed=seed+start*100003
                        result=kmedoids.fasterpam(distances,k,max_iter=1000,init='random',random_state=init_seed,n_cpu=1)
                        trials.append(dict(seed=init_seed,loss=float(result.loss),iterations=int(result.n_iter)))
                        if best is None or result.loss<best.loss:best=result
                    require(np.isclose(distances[np.arange(len(values)),np.asarray(best.medoids)[best.labels]].sum(),best.loss),'Objetivo K-Medoids no concilia.')
                    return None,dict(labels=best.labels,medoid_indices=np.asarray(best.medoids)),dict(loss=float(best.loss),trials=trials,
                        objective='Suma de distancias euclídeas a medoide: no SSE.',iterations=int(best.n_iter))
                model,arrays,details=self.bundle(model_id,values,dict(k=k,seed=seed,n_init=3,max_iter=1000),fit)
                records.append(dict(model_id=model_id,algorithm='kmedoids',configuration=f'k{k}',k=k,seed=seed,loss=details['loss']))
                print(f'K-Medoids K={k}, semilla={seed}: objetivo euclídeo {details["loss"]:.2f}.',flush=True)
        del distances
        write_json(path,dict(status='executed',implementation='kmedoids.fasterpam',square_MiB=required/2**20,
            justification='La API nativa exige el cuadrado; único buffer reutilizado para 27 inicializaciones, separado del árbol Ward.'))
        self.checkpoint('F',self.bundle_paths(ids)+[path,self.table('metadata/kmedoids_index.csv',pd.DataFrame(records))],started,
            'Nueve ajustes K-Medoids nativos con tres arranques; único cuadrado euclídeo de 164.8 MiB liberado.')

    def labels(self,row):
        bundle=row.get('bundle_id',row['model_id'])
        if not isinstance(bundle,str):bundle=row['model_id']
        field=row.get('label_field','labels')
        if not isinstance(field,str):field='labels'
        return self.load_arrays(bundle)[field]

    def indices(self):
        return pd.concat([pd.read_csv(self.output/f'metadata/{name}_index.csv')
            for name in ['kmeans','gmm','hdbscan','ward','kmedoids'] if (self.output/f'metadata/{name}_index.csv').exists()],ignore_index=True)

    def stage_g(self):
        from sklearn.metrics import adjusted_rand_score
        started=time.monotonic();_,main,values=self.data();index=self.indices();records=[];profiles=[];curves=[];paths=[]
        baseline={}
        km=index[index.algorithm.eq('kmeans')]
        for k,part in km.groupby('k'):baseline[int(k)]=self.labels(part.loc[part.sse.idxmin()])
        for i,row in index.iterrows():
            labels=self.labels(row);model_id=row.model_id
            cache=self.output/f'metadata/metric_cache/{model_id}.json'
            signature=hashlib.sha256(values.tobytes()+labels.tobytes()).hexdigest()
            if cache.exists():
                stored=json.loads(cache.read_text(encoding='utf8'));require(stored['signature']==signature,'Métrica de otra población.');result=stored['metrics']
            else:
                result=label_metrics(values,labels,main,baseline.get(int(row.k)))
                write_json(cache,dict(signature=signature,metrics=result))
            records.append({**row.to_dict(),**result});paths.append(cache)
            part,curve=describe_groups(main,labels,model_id);profiles.append(part);curves.append(curve)
            if (i+1)%5==0:print(f'G: métricas exactas por bloques {i+1}/{len(index)}.',flush=True)
        metrics=pd.DataFrame(records);seeds=[];selected=[]
        for (algorithm,configuration),part in metrics.groupby(['algorithm','configuration']):
            if algorithm in ['kmeans','gmm','kmedoids']:
                for left,right in combinations(part.index,2):seeds.append(dict(algorithm=algorithm,configuration=configuration,
                    left=metrics.loc[left,'model_id'],right=metrics.loc[right,'model_id'],
                    ari=float(adjusted_rand_score(self.labels(metrics.loc[left]),self.labels(metrics.loc[right])))))
            objective='sse' if algorithm=='kmeans' else 'bic' if algorithm=='gmm' else 'loss' if algorithm=='kmedoids' else None
            selected.append(part.loc[part[objective].idxmin()] if objective else part.iloc[0])
        summary=pd.DataFrame(selected)
        seed_table=pd.DataFrame(seeds)
        if not seed_table.empty:
            ss=seed_table.groupby(['algorithm','configuration']).agg(seed_ari_min=('ari','min'),seed_ari_median=('ari','median')).reset_index()
            summary=summary.merge(ss,on=['algorithm','configuration'],how='left',validate='one_to_one')
        pairs=[]
        hdb=summary[summary.algorithm.eq('hdbscan')]
        for left,right in combinations(hdb.index,2):
            a,b=summary.loc[left],summary.loc[right]
            pairs.append(dict(left=a.model_id,right=b.model_id,**common_partition_stability(self.labels(a),self.labels(b))))
        for relative,frame in [('metadata/model_metrics.csv',metrics),('metadata/solution_comparison.csv',summary),
            ('metadata/seed_stability.csv',seed_table),('metadata/cluster_profiles.csv',pd.concat(profiles)),
            ('metadata/cluster_curves.csv',pd.concat(curves)),('metadata/hdbscan_parameter_stability.csv',pd.DataFrame(pairs))]:
            paths.append(self.table(relative,frame))
        self.checkpoint('G',paths,started,f'{len(index)} soluciones/semillas evaluadas en R2; métricas exactas de asignados, ruido y coberturas separados.')

    def choose_candidates(self,explicit):
        summary=pd.read_csv(self.output/'metadata/solution_comparison.csv')
        gmm=summary[summary.algorithm.eq('gmm')&summary.converged.eq(True)]
        require(not gmm.empty,'Ningún GMM convergente.')
        gmm_id=explicit.get('gmm') or gmm.loc[gmm.bic.idxmin(),'model_id']
        ward_id=f'ward_k{explicit.get("ward") or 2}'
        hdb_id=explicit.get('hdbscan') or 'hdbscan_m50_s10_single0'
        selected=[gmm_id,ward_id,hdb_id]
        if summary.algorithm.eq('kmedoids').any():
            part=summary[summary.algorithm.eq('kmedoids')&summary.k.eq(2)];selected.append(part.loc[part.loss.idxmin(),'model_id'])
        require(set(selected)<=set(summary.model_id),'Candidata no calculada en la comparación principal.')
        previous=self.state.get('candidates');require(previous is None or previous==selected,'Selección distinta de la estabilidad iniciada.')
        self.state['candidates']=selected;write_json(self.state_path,self.state)
        path=self.output/'metadata/candidate_selection.json'
        if not path.exists():write_json(path,dict(candidates=selected,comparison_sha256=file_hash(self.output/'metadata/solution_comparison.csv'),
            rationale='Tras G: GMM de BIC mínimo (densidad, sin equiparar componentes a perfiles); Ward K=2 por parsimonia y salto superior; '
            'HDBSCAN 50/10 sin grupo único como control diagnóstico de los pequeños grupos detectados, no candidato de cobertura electoral; '
            'K-Medoids K=2 como contraste parsimonioso casi concordante con K-Means. Diez muestras, sin forzar 4–6 grupos.'))
        return summary.set_index('model_id').loc[selected].reset_index()

    def sample_fit(self,row,values,model_id):
        algorithm=row.algorithm
        if algorithm=='gmm':return self.fit_gmm(model_id,values,int(row.k),row.covariance,17)
        if algorithm=='ward':return self.fit_ward(model_id,values,[int(row.k)])
        if algorithm=='hdbscan':return self.fit_hdbscan(model_id,values,int(row.min_cluster_size),int(row.min_samples),bool(row.allow_single_cluster))
        if algorithm=='kmedoids':
            import kmedoids
            from scipy.spatial.distance import cdist
            def fit():
                require(len(values)**2*8<=256*2**20,'Buffer nativo sobre presupuesto.')
                distances=cdist(values,values);best=None;trials=[]
                for start in range(3):
                    result=kmedoids.fasterpam(distances,int(row.k),max_iter=1000,init='random',random_state=17+start*100003,n_cpu=1)
                    trials.append(float(result.loss))
                    if best is None or result.loss<best.loss:best=result
                return None,dict(labels=best.labels,medoid_coordinates=values[best.medoids]),dict(loss=float(best.loss),trials=trials)
            return self.bundle(model_id,values,dict(algorithm='kmedoids',k=int(row.k),seed=17,n_init=3),fit)
        raise ValueError(algorithm)

    def project(self,row,model,arrays,values):
        if row.algorithm=='gmm':return model.predict(values)
        if row.algorithm=='kmedoids':return ((values[:,None,:]-arrays['medoid_coordinates'][None,:,:])**2).sum(axis=2).argmin(axis=1)
        raise ValueError('Ward/HDBSCAN no tienen predicción fuera de muestra en esta comparación.')

    def stage_h(self,explicit):
        from sklearn.metrics import adjusted_rand_score
        from sklearn.cluster import KMeans
        started=time.monotonic();selected=self.choose_candidates(explicit);full,main,values=self.data();paths=[];records=[];coverage=[];ids=[];profiles=[];curves=[]
        samples=pd.read_parquet(self.source/'reference/municipality_membership.parquet')
        sample_keys=pd.MultiIndex.from_frame(samples[MUNICIPAL_KEYS]);main_keys=pd.MultiIndex.from_frame(main[MUNICIPAL_KEYS])
        self.table('resampling/municipality_membership.parquet',samples)
        for replicate in range(self.replicates):
            draw=samples[f'sample_{replicate:03d}'].to_numpy(bool);require(draw.sum()==1981,'Muestra municipal incorrecta.')
            inbag=main_keys.isin(sample_keys[draw]);oob=~inbag
            coverage.append(dict(replicate=replicate,drawn_municipalities=int(draw.sum()),training_profiles=int(inbag.sum()),
                training_municipalities=main.loc[inbag].groupby(MUNICIPAL_KEYS).ngroups,training_LN=int(main.loc[inbag,'LN'].sum()),
                eligible_LN_fraction=float(main.loc[inbag,'LN'].sum()/main.LN.sum()),oob_profiles=int(oob.sum()),
                oob_municipalities=main.loc[oob].groupby(MUNICIPAL_KEYS).ngroups))
            for _,row in selected.iterrows():
                reference=self.labels(row);model_id=f'resampling/sample_{replicate:03d}/{row.model_id}';ids.append(model_id)
                model,arrays,details=self.sample_fit(row,values[inbag],model_id)
                training_labels=arrays[f'labels_k{int(row.k)}'] if row.algorithm=='ward' else arrays['labels']
                common=common_partition_stability(reference[inbag],training_labels)
                predictive=row.algorithm in ['gmm','kmedoids'];ari_oob=np.nan
                assignment=full[['row_id',*KEYS,'is_eligible']].copy()
                raw=pd.array([pd.NA]*len(main),dtype='Int64');raw[inbag]=training_labels
                projected=None
                if predictive:
                    projected=self.project(row,model,arrays,values);ari_oob=float(adjusted_rand_score(reference[oob],projected[oob]))
                all_labels=pd.array([pd.NA]*len(full),dtype='Int64');all_labels[full.is_eligible]=raw
                assignment['training_label']=all_labels
                flag=np.zeros(len(full),bool);flag[full.is_eligible]=inbag;assignment['is_training']=flag
                projection=pd.array([pd.NA]*len(full),dtype='Int64')
                if predictive:projection[full.is_eligible]=projected
                assignment['projected_label']=projection
                path=f'resampling/assignments/sample_{replicate:03d}/{row.model_id}.parquet';paths.append(self.table(path,assignment))
                record=dict(model_id=row.model_id,algorithm=row.algorithm,replicate=replicate,ari_oob=ari_oob,
                    evaluation='oob_prediction_and_common' if predictive else 'common_inbag_only_no_prediction',
                    sample_noise_fraction=float((training_labels<0).mean()),seconds=details['seconds'],**common)
                if row.algorithm=='gmm':record.update(posterior_summary(model.predict_proba(values[oob])))
                records.append(record)
                part,curve=describe_groups(main.loc[inbag].reset_index(drop=True),training_labels,model_id);profiles.append(part);curves.append(curve)
            # Reutiliza predicciones K-Means previas: cambiar el origen/escala escalar R2 no cambia esa partición euclídea.
            previous=self.source/f'resampling/sample_{replicate:03d}/r2_k2'
            assignment=pd.read_parquet(previous/'assignment.parquet')
            require(assignment.row_id.equals(full.row_id),'Orden previo de remuestra distinto.')
            require(np.array_equal(assignment.loc[full.is_eligible,'is_training'],inbag),'Membresía previa distinta.')
            prediction=assignment.loc[full.is_eligible,'projected_label'].to_numpy(int)
            baseline=self.load_arrays('kmeans_k2_seed17')['labels']
            records.append(dict(model_id='kmeans_k2_seed17',algorithm='kmeans',replicate=replicate,
                ari_oob=float(adjusted_rand_score(baseline[oob],prediction[oob])),evaluation='reused_oob_prediction',
                reused=True,**common_partition_stability(baseline[inbag],prediction[inbag])))
            print(f'H: muestra {replicate+1}/{self.replicates}; {int(inbag.sum()):,} entrenamiento, {int(oob.sum()):,} OOB; Ward/HDB sólo comunes.',flush=True)
        for relative,frame in [('metadata/resampling_metrics.csv',pd.DataFrame(records)),('metadata/resampling_coverage.csv',pd.DataFrame(coverage)),
            ('metadata/resampling_profiles.csv',pd.concat(profiles)),('metadata/resampling_curves.csv',pd.concat(curves))]:paths.append(self.table(relative,frame))
        paths.extend(self.bundle_paths(ids));paths.extend([self.output/'metadata/candidate_selection.json',self.output/'resampling/municipality_membership.parquet'])
        # Sensibilidad limitada: NS cambia población, nunca se imputa ni se alteran las referencias/escala R2.
        low=~main.has_high_ns_coordinate.to_numpy();sensitivities=[]
        km_reference=self.load_arrays('kmeans_k2_seed17');municipal_weights=1/main.groupby(MUNICIPAL_KEYS).row_id.transform('size').to_numpy()
        for scenario,mask,weight in [('equal_municipality',np.ones(len(main),bool),municipal_weights),('low_ns',low,np.ones(len(main)))]:
            model_id=f'sensitivity/kmeans_k2_{scenario}';ids.append(model_id)
            def fit(mask=mask,weight=weight):
                model=KMeans(n_clusters=2,init=km_reference['centers'],n_init=1,tol=0,max_iter=1000,algorithm='lloyd',random_state=17).fit(values[mask],sample_weight=weight[mask])
                return model,dict(labels=model.labels_,projected_labels=model.predict(values)),dict(sse=float(model.inertia_))
            model,arrays,details=self.bundle(model_id,values[mask],dict(k=2,scenario=scenario,init='reference_centers',n_init=1),fit)
            sensitivities.append(dict(model_id='kmeans_k2_seed17',algorithm='kmeans',scenario=scenario,training_profiles=int(mask.sum()),
                training_LN=int(main.loc[mask,'LN'].sum()),ari_common=float(adjusted_rand_score(km_reference['labels'][mask],arrays['labels'])),
                ari_all_eligible=float(adjusted_rand_score(km_reference['labels'],arrays['projected_labels']))))
        for _,row in selected.iterrows():
            if row.algorithm=='kmedoids':continue  # Se reserva el contraste de NS a las familias principales.
            model_id=f'sensitivity/low_ns/{row.model_id}';ids.append(model_id)
            model,arrays,details=self.sample_fit(row,values[low],model_id)
            labels=arrays[f'labels_k{int(row.k)}'] if row.algorithm=='ward' else arrays['labels'];reference=self.labels(row)
            result=dict(model_id=row.model_id,algorithm=row.algorithm,scenario='low_ns',training_profiles=int(low.sum()),
                training_LN=int(main.loc[low,'LN'].sum()),**common_partition_stability(reference[low],labels))
            if row.algorithm=='gmm':result.update(ari_all_eligible=float(adjusted_rand_score(reference,model.predict(values))),**posterior_summary(model.predict_proba(values)))
            sensitivities.append(result)
            frame=full[['row_id',*KEYS,'is_eligible']].copy();raw=pd.array([pd.NA]*len(main),dtype='Int64');raw[low]=labels
            all_labels=pd.array([pd.NA]*len(full),dtype='Int64');all_labels[full.is_eligible]=raw;frame['training_label']=all_labels
            projection=pd.array([pd.NA]*len(full),dtype='Int64')
            if row.algorithm=='gmm':projection[full.is_eligible]=model.predict(values)
            frame['projected_label']=projection;paths.append(self.table(f'sensitivity/assignments/{row.model_id}.parquet',frame))
        paths.extend(self.bundle_paths(ids[-5:]));paths.append(self.table('metadata/quality_sensitivity.csv',pd.DataFrame(sensitivities)))
        write_json(self.output/'metadata/weight_capabilities.json',dict(
            kmeans='sample_weight: control local desde mismos centros; no se repite el ajuste principal.',
            gmm='GaussianMixture.fit no admite sample_weight.',ward='linkage no admite sample_weight.',
            hdbscan='HDBSCAN.fit no admite sample_weight.',kmedoids='fasterpam sin pesos.',
            omitted='No se replican perfiles artificialmente para simular pesos; LN no se usa como referencia automática.'))
        paths.append(self.output/'metadata/weight_capabilities.json')
        self.checkpoint('H',paths,started,f'{len(selected)} candidatas, diez muestras compartidas; K-Means OOB reutilizado; NS y peso municipal acotados.')

    def candidate_rows(self):
        summary=pd.read_csv(self.output/'metadata/solution_comparison.csv').set_index('model_id')
        ids=['kmeans_k2_seed17',*self.state['candidates']]
        return summary.loc[ids].reset_index()

    def plot_space(self,ax,values,labels,title):
        noise=labels<0
        if noise.any():ax.scatter(*values[noise].T,c='#b6b6b6',s=7,alpha=.4,label=f'Sin asignar: {noise.sum():,}',rasterized=True)
        for cluster in np.unique(labels[~noise]):
            selected=labels==cluster
            ax.scatter(*values[selected].T,s=8,alpha=.4,color=plt.get_cmap('tab10')(int(cluster)%10),label=f'{int(cluster)}: {selected.sum():,}',rasterized=True)
        ax.set(title=title,xlabel='Contraste de forma 1 (R2)',ylabel='Contraste de forma 2 (R2)')
        ax.set_xlim(self.space_limits[0]);ax.set_ylim(self.space_limits[1]);ax.set_aspect('equal',adjustable='box')
        ax.legend(fontsize=7,loc='best',markerscale=1.6)

    def plot_results(self,main,values,summary,stability):
        from scipy.cluster.hierarchy import dendrogram
        from scipy.stats import chi2
        candidates=self.candidate_rows();curves=pd.read_csv(self.output/'metadata/cluster_curves.csv')
        self.space_limits=[(values[:,i].min()-.1,values[:,i].max()+.1) for i in range(2)]
        fig,ax=plt.subplots(figsize=(8,7),layout='constrained')
        density=ax.hexbin(*values.T,gridsize=50,mincnt=1,bins='log',cmap='viridis');fig.colorbar(density,ax=ax,label='Perfiles por celda (color logarítmico)')
        ax.set(title='R2 sin etiquetas · 4,648 perfiles municipio/sexo',xlabel='Contraste de forma 1 (R2)',ylabel='Contraste de forma 2 (R2)')
        ax.set_xlim(self.space_limits[0]);ax.set_ylim(self.space_limits[1]);ax.set_aspect('equal',adjustable='box');save_figure(fig,self.charts/'r2_unlabeled.png')
        fig,axes=plt.subplots(2,3,figsize=(15,10),layout='constrained')
        for ax,(_,row) in zip(axes.flat,candidates.iterrows()):self.plot_space(ax,values,self.labels(row),row.model_id)
        single=summary[summary.model_id.eq('hdbscan_m100_s30_single1')].iloc[0]
        self.plot_space(axes.flat[-1],values,self.labels(single),'HDBSCAN 100/30 · permite un único grupo')
        fig.suptitle('Misma matriz, mismos ejes y población · colores y etiquetas locales a cada ajuste')
        save_figure(fig,self.charts/'algorithm_comparison.png')
        gmm_row=candidates[candidates.algorithm.eq('gmm')].iloc[0];gmm=self.load_model(gmm_row.model_id)
        labels=self.labels(gmm_row);posterior=gmm.predict_proba(values)
        fig,axes=plt.subplots(1,2,figsize=(14,6.5),layout='constrained')
        self.plot_space(axes[0],values,labels,'GMM · etiquetas duras y elipses de componentes')
        for j,mean in enumerate(gmm.means_):
            covariance=gmm.covariances_[j] if gmm.covariance_type=='full' else np.diag(gmm.covariances_[j]) if gmm.covariance_type=='diag' else gmm.covariances_
            eigenvalues,eigenvectors=np.linalg.eigh(covariance);order=np.argsort(eigenvalues)[::-1];eigenvalues=eigenvalues[order];eigenvectors=eigenvectors[:,order]
            angle=np.degrees(np.arctan2(eigenvectors[1,0],eigenvectors[0,0]));diameters=2*np.sqrt(chi2.ppf(.95,2)*eigenvalues)
            axes[0].add_patch(Ellipse(mean,*diameters,angle=angle,fill=False,color=plt.get_cmap('tab10')(j),lw=2))
            axes[0].scatter(*mean,c='black',marker='x',s=60,zorder=5)
        xx,yy=np.meshgrid(np.linspace(*self.space_limits[0],220),np.linspace(*self.space_limits[1],220));grid=np.column_stack([xx.ravel(),yy.ravel()])
        probs=gmm.predict_proba(grid);regions=probs.argmax(axis=1).reshape(xx.shape);maximum=probs.max(axis=1).reshape(xx.shape)
        axes[1].contourf(xx,yy,regions,levels=np.arange(gmm.n_components+1)-.5,colors=[plt.get_cmap('tab10')(j) for j in range(gmm.n_components)],alpha=.25)
        axes[1].contourf(xx,yy,maximum,levels=[0,.8,1],colors=['#777777','white'],alpha=.22)
        axes[1].contour(xx,yy,maximum,levels=[.8],colors='black',linestyles='--',linewidths=.8)
        self.plot_space(axes[1],values,labels,'Regiones argmax · gris: posterior máximo <0.8')
        fig.suptitle('GMM: elipses de masa 95 % de cada componente normal\nNo son intervalos de centroides ni certeza sobre individuos')
        save_figure(fig,self.charts/'gmm_overlap.png')
        fig,axes=plt.subplots(1,2,figsize=(14,6.5),layout='constrained')
        hdb=candidates[candidates.algorithm.eq('hdbscan')].iloc[0]
        self.plot_space(axes[0],values,self.labels(hdb),'HDBSCAN 50/10 · selección sin grupo único')
        self.plot_space(axes[1],values,self.labels(single),'HDBSCAN 100/30 · permite grupo único')
        fig.suptitle('Ruido gris: observaciones conservadas, sin etiqueta de cluster')
        save_figure(fig,self.charts/'hdbscan_noise.png')
        tree=self.load_arrays('ward_tree')['tree'];fig,axes=plt.subplots(1,2,figsize=(14,5.5),layout='constrained')
        dendrogram(tree,truncate_mode='lastp',p=30,show_leaf_counts=True,color_threshold=0,ax=axes[0])
        axes[0].set(title='Ward · últimas 30 ramas (hojas comprimidas)',xlabel='Subárbol; paréntesis: número de perfiles',ylabel='Altura Ward euclídea')
        last=tree[-12:,2];axes[1].plot(range(13,1,-1),last,'o-');axes[1].set(xlabel='Grupos antes de la fusión',ylabel='Altura de fusión',title='Saltos finales · no son prueba de grupos naturales')
        axes[1].invert_xaxis();save_figure(fig,self.charts/'ward_dendrogram.png')
        for field,name,ylabel in [('mean_delta','relative_curves.png','Diferencia nacional media (pp)'),
            ('mean_rate','absolute_curves.png','Participación observada media (%)'),('mean_shape','shape_curves.png','Forma tras retirar nivel (pp)')]:
            fig,axes=plt.subplots(2,3,figsize=(15,8),layout='constrained',sharey=True)
            for ax,(_,row) in zip(axes.flat,candidates.iterrows()):
                part=curves[curves.model_id.eq(row.model_id)]
                for cluster,group in part.groupby('cluster'):
                    group=group.set_index('age_band').loc[BANDS]
                    ax.plot(BANDS,group[field]*100,marker='o',color='#888888' if cluster<0 else plt.get_cmap('tab10')(int(cluster)%10),
                        linestyle='--' if cluster<0 else '-',label='Sin asignar' if cluster<0 else str(cluster))
                ax.set(title=row.model_id,xlabel='Intervalo candidato',ylabel=ylabel);ax.legend(fontsize=8);ax.grid(alpha=.2)
                if field=='mean_rate':ax.set_ylim(0,100)
                else:ax.axhline(0,color='black',lw=.5)
            axes.flat[-1].axis('off');fig.suptitle('Medias de perfiles con igual peso · las tasas por conteos se guardan separadamente')
            save_figure(fig,self.charts/name)
        fig,axes=plt.subplots(2,2,figsize=(12,9),layout='constrained')
        for algorithm in ['kmeans','ward','kmedoids']:
            group=summary[summary.algorithm.eq(algorithm)].sort_values('k')
            for ax,field in zip(axes[0],['silhouette','db']):ax.plot(group.k,group[field],'o-',label=algorithm)
        group=summary[summary.algorithm.eq('gmm')&summary.covariance.eq('full')].sort_values('k')
        for ax,field in zip(axes[0],['silhouette','db']):ax.plot(group.k,group[field],'o-',label='GMM full')
        for ax,title in zip(axes[0],['Silhouette exacto · todos los elegibles','Davies–Bouldin · todos los elegibles']):ax.set(title=title,xlabel='K / componentes');ax.legend()
        for covariance in ['full','diag','tied']:
            group=summary[summary.algorithm.eq('gmm')&summary.covariance.eq(covariance)].sort_values('k')
            for ax,field in zip(axes[1],['bic','aic']):ax.plot(group.k,group[field],'o-',label=covariance);ax.set(title=field.upper()+' · sólo familia GMM',xlabel='Componentes');ax.legend()
        fig.suptitle('HDBSCAN se evalúa aparte por su distinta cobertura; K=6 es sensibilidad')
        save_figure(fig,self.charts/'metrics.png')
        fig,axes=plt.subplots(1,3,figsize=(15,5),layout='constrained')
        predictive=stability[stability.algorithm.isin(['kmeans','gmm','kmedoids'])]
        groups=list(predictive.groupby('algorithm'))
        axes[0].boxplot([g.ari_oob.dropna() for _,g in groups],tick_labels=[name for name,_ in groups],showfliers=True)
        axes[0].set(title='ARI fuera de muestra municipal',ylabel='Concordancia con solución completa',ylim=(-.1,1.02))
        groups=list(stability[stability.algorithm.isin(['ward','hdbscan'])].groupby('algorithm'))
        axes[1].boxplot([g.ari_common_all for _,g in groups],tick_labels=[name for name,_ in groups],showfliers=True)
        axes[1].set(title='ARI sobre entrenamiento común\nHDBSCAN: ruido como una etiqueta',ylabel='No es predicción OOB',ylim=(-.1,1.02))
        hdb_stability=stability[stability.algorithm.eq('hdbscan')]
        axes[2].boxplot([hdb_stability.ari_common_both_assigned.dropna(),hdb_stability.assignment_jaccard.dropna()],tick_labels=['ARI asignados\nen ambos','Jaccard\nasignación'],showfliers=True)
        axes[2].set(title='HDBSCAN · bases de cobertura distintas',ylim=(-.1,1.02))
        fig.suptitle('Diez submuestras municipales compartidas · incluye peores casos; no son IC')
        save_figure(fig,self.charts/'municipality_stability.png')
        fig,axes=plt.subplots(1,2,figsize=(14,5),layout='constrained')
        axes[0].hist(posterior.max(axis=1),bins=np.linspace(0,1,26),color='#477e9b');axes[0].axvline(.8,color='#b35239',ls='--')
        axes[0].set(title=f'GMM · {pct(np.mean(posterior.max(axis=1)<.8))} con máximo <0.8',xlabel='Posterior máximo condicional al modelo',ylabel='Perfiles')
        hdb_all=summary[summary.algorithm.eq('hdbscan')].sort_values(['allow_single_cluster','min_cluster_size','min_samples'])
        tick=[f'{int(r.min_cluster_size)}/{int(r.min_samples)}/{int(r.allow_single_cluster)}' for _,r in hdb_all.iterrows()]
        axes[1].bar(range(len(hdb_all)),1-hdb_all.noise_fraction,label='Fracción de perfiles asignados',color='#38827e')
        axes[1].plot(range(len(hdb_all)),hdb_all.assigned_LN_fraction,'o',label='Fracción de LN elegible asignado',color='#bc8735')
        axes[1].set_xticks(range(len(tick)),tick,rotation=90);axes[1].set(title='Cobertura HDBSCAN · no equivale a ausencia de datos',xlabel='Tamaño mínimo / vecinos / permite único',ylim=(0,1))
        axes[1].yaxis.set_major_formatter(PercentFormatter(1));axes[1].legend(fontsize=8)
        save_figure(fig,self.charts/'uncertainty_and_coverage.png')

    def stage_i(self):
        from sklearn.metrics import adjusted_rand_score
        started=time.monotonic();full,main,values=self.data();summary=pd.read_csv(self.output/'metadata/solution_comparison.csv');index=self.indices()
        for target in [self.charts,self.report,self.output/'assignments']:
            if target.exists():
                archived=self.output/'incomplete'/f'{target.name}_{time.time_ns()}'
                require(target.is_relative_to(self.output) or target==self.charts or target==self.report,'Destino ajeno al experimento.')
                archived.parent.mkdir(parents=True,exist_ok=True);target.replace(archived)
        self.charts.mkdir(parents=True);paths=[];checks=[]
        for _,row in index.iterrows():
            labels=self.labels(row);frame=full[['row_id',*KEYS,'is_eligible','pending_reason']].copy()
            assigned=pd.array([pd.NA]*len(full),dtype='Int64');assigned[full.is_eligible]=labels;frame['experimental_label']=assigned
            noise=pd.array([pd.NA]*len(full),dtype='boolean');noise[full.is_eligible]=labels<0;frame['is_noise']=noise
            require(frame.loc[~full.is_eligible,'experimental_label'].isna().all(),'Pendientes asignados.')
            paths.append(self.table(f'assignments/{row.model_id}.parquet',frame))
        # Comprueba que los K-Means municipales reutilizados son la misma regla en R2, aunque antes se recalibrara sólo su escala escalar.
        parameters=json.loads((self.source/'metadata/parameters.json').read_text(encoding='utf8'))
        for replicate in range(self.replicates):
            folder=self.source/f'resampling/sample_{replicate:03d}/r2_k2'
            previous=json.loads((folder/'fit.json').read_text(encoding='utf8'))['parameters']
            with np.load(folder/'fit.npz',allow_pickle=False) as fit:
                centers=(fit['centers']*previous['shape_scale']+np.asarray(previous['shape_mean'])-np.asarray(parameters['shape_mean']))/parameters['shape_scale']
            predictions=((values[:,None,:]-centers[None,:,:])**2).sum(axis=2).argmin(axis=1)
            original=pd.read_parquet(folder/'assignment.parquet').loc[full.is_eligible,'projected_label'].to_numpy(int)
            require(np.array_equal(predictions,original),'K-Means remuestreado no equivalente en R2 fijo.')
            checks.append(dict(check='reused_kmeans_affine_equivalence',replicate=replicate,differences=0))
        candidates=self.candidate_rows();pairwise=[]
        for left,right in combinations(candidates.index,2):
            a,b=candidates.loc[left],candidates.loc[right]
            pairwise.append(dict(left=a.model_id,right=b.model_id,**common_partition_stability(self.labels(a),self.labels(b))))
        paths.append(self.table('metadata/candidate_pairwise_ari.csv',pd.DataFrame(pairwise)))
        paths.append(self.table('metadata/final_validation.csv',pd.DataFrame(checks)))
        stability=pd.read_csv(self.output/'metadata/resampling_metrics.csv')
        self.plot_results(main,values,summary,stability)
        paths.extend(self.write_report(full,main,summary,stability))
        self.verify_protected()
        paths.extend([*self.charts.glob('*.png'),self.report])
        self.checkpoint('I',paths,started,'Etiquetas completas, gráficas, informe, conteos, equivalencia de remuestras e integridad de fuentes verificados.')

    def write_report(self,full,main,summary,stability):
        started=time.monotonic();paths=[];candidates=self.candidate_rows();_,_,values=self.data()
        gmm=summary[summary.algorithm.eq('gmm')];gmm_best=gmm.loc[gmm.bic.idxmin()];aic_best=gmm.loc[gmm.aic.idxmin()]
        hdb=summary[summary.algorithm.eq('hdbscan')];hdb_selected=candidates[candidates.algorithm.eq('hdbscan')].iloc[0]
        ward=pd.read_csv(self.output/'metadata/ward_index.csv');curves=pd.read_csv(self.output/'metadata/cluster_curves.csv')
        profiles=pd.read_csv(self.output/'metadata/cluster_profiles.csv');sensitivity=pd.read_csv(self.output/'metadata/quality_sensitivity.csv')
        metrics=pd.read_csv(self.output/'metadata/model_metrics.csv');coverage=pd.read_csv(self.output/'metadata/resampling_coverage.csv')
        pairwise=pd.read_csv(self.output/'metadata/candidate_pairwise_ari.csv')
        def table(frame,columns,headers):
            rows=[]
            for _,row in frame.iterrows():
                result=[]
                for field in columns:
                    value=row[field]
                    result.append('n/d' if pd.isna(value) else f'{value:.4f}' if isinstance(value,(float,np.floating)) else str(value))
                rows.append(result)
            return markdown_table(headers,rows)
        def image(name,title):return f'![{title}]({Path(os.path.relpath(self.charts/name,self.report.parent)).as_posix()})'
        def model_title(name):return name.replace('_seed17','').replace('_seed2024','').replace('_seed42','')
        robust=[]
        for (algorithm,model_id),group in stability.groupby(['algorithm','model_id']):
            def median(field):return float(group[field].median()) if group[field].notna().any() else np.nan
            def minimum(field):return float(group[field].min()) if group[field].notna().any() else np.nan
            robust.append(dict(algorithm=algorithm,model_id=model_id,samples=len(group),oob_median=median('ari_oob'),oob_min=minimum('ari_oob'),
                common_median=median('ari_common_all'),common_min=minimum('ari_common_all'),
                both_assigned_median=median('ari_common_both_assigned'),both_assigned_min=minimum('ari_common_both_assigned'),
                assignment_jaccard_median=median('assignment_jaccard'),assignment_jaccard_min=minimum('assignment_jaccard')))
        robust=pd.DataFrame(robust);paths.append(self.table('metadata/stability_summary.csv',robust))
        r=robust.set_index('algorithm');support=[];worst=[];changes=[]
        for _,row in candidates.iterrows():
            labels=self.labels(row)
            for cluster in np.unique(labels):
                part=main[labels==cluster]
                support.append(dict(model_id=row.model_id,cluster=int(cluster),profiles=len(part),LN=int(part.LN.sum()),
                    median_profile_LN=float(part.LN.median()),median_min_specified=float(part[['specified_count_'+s for s in SUFFIXES]].min(axis=1).median()),
                    high_ns_fraction=float(part.has_high_ns_coordinate.mean())))
            group=stability[stability.model_id.eq(row.model_id)]
            column='ari_oob' if group.ari_oob.notna().any() else 'ari_common_all';case=group.loc[group[column].idxmin()];replicate=int(case.replicate)
            path=self.source/f'resampling/sample_{replicate:03d}/r2_k2/assignment.parquet' if row.algorithm=='kmeans' else self.output/f'resampling/assignments/sample_{replicate:03d}/{row.model_id}.parquet'
            assignment=pd.read_parquet(path);require(assignment.row_id.equals(full.row_id),'Desalineación en peor caso.')
            assignment=assignment.loc[full.is_eligible].reset_index(drop=True)
            cohort=~assignment.is_training.to_numpy() if column=='ari_oob' else assignment.is_training.to_numpy()
            field='projected_label' if column=='ari_oob' else 'training_label'
            sample=assignment.loc[cohort,field].to_numpy(int);reference=labels[cohort]
            changed=(reference<0)!=(sample<0) if row.algorithm=='hdbscan' else aligned_changes(reference,sample)
            rule='noise_status_only_not_label_alignment' if row.algorithm=='hdbscan' else 'maximum_overlap_label_alignment'
            frame=main.loc[cohort,['row_id',*KEYS,'LN','has_high_ns_coordinate']].copy()
            frame['model_id']=row.model_id;frame['replicate']=replicate;frame['comparison_base']='oob' if column=='ari_oob' else 'common_inbag'
            frame['reference_label']=reference;frame['sample_label']=sample;frame['changed']=changed;frame['change_rule']=rule;changes.append(frame)
            worst.append(dict(model_id=row.model_id,replicate=replicate,comparison_base=frame.comparison_base.iloc[0],ari=float(case[column]),
                profiles=int(cohort.sum()),changed=int(changed.sum()),changed_fraction=float(changed.mean()),change_rule=rule))
        paths.append(self.table('metadata/candidate_support.csv',pd.DataFrame(support)))
        paths.append(self.table('metadata/worst_case_summary.csv',pd.DataFrame(worst)))
        paths.append(self.table('metadata/worst_case_changes.parquet',pd.concat(changes,ignore_index=True)))
        # Auditoría acotada de inicializaciones individuales: no repite los bancos de cinco ya validados.
        initialization=[];gmm_ids=[];reference=self.labels(gmm_best)
        for seed in SEEDS:
            model_id=f'initialization_audit/gmm_{gmm_best.covariance}_k{int(gmm_best.k)}_seed{seed}';gmm_ids.append(model_id)
            model,arrays,details=self.fit_gmm(model_id,values,int(gmm_best.k),gmm_best.covariance,seed,starts=1)
            from sklearn.metrics import adjusted_rand_score
            initialization.append(dict(seed=seed,n_init=1,bic=details['bic'],aic=details['aic'],converged=details['converged'],
                ari_vs_best_bank=float(adjusted_rand_score(reference,arrays['labels']))))
        init_summary=pd.DataFrame(initialization)
        paths.extend(self.bundle_paths(gmm_ids));paths.append(self.table('metadata/gmm_initialization_audit.csv',init_summary))
        controls=json.loads((self.output/'models/kmeans_library_check/details.json').read_text(encoding='utf8'))
        full_curves=curves[curves.model_id.isin(candidates.model_id)]
        shape_table=full_curves.pivot(index=['model_id','cluster'],columns='age_band',values='mean_shape').reset_index()
        shape_table[BANDS]=shape_table[BANDS]*100
        candidate_profiles=profiles[profiles.model_id.isin(candidates.model_id)]
        support_table=pd.DataFrame(support)
        gsupport=support_table[support_table.model_id.eq(gmm_best.model_id)]
        hdb_assigned=hdb_selected['assigned'];sensitivity['common_ari_display']=sensitivity.ari_common.fillna(sensitivity.ari_common_all)
        dependencies=self.dependencies['imports']
        versions=pd.DataFrame([dict(package=k,version=v.get('version','n/d'),available=v['available']) for k,v in dependencies.items()])
        timings=pd.DataFrame([dict(stage=stage,seconds=info['seconds'],**json.loads((self.output/f'metadata/checkpoint_{stage}.json').read_text(encoding='utf8'))['memory'])
            for stage,info in self.state['stages'].items()])
        medoid=candidates[candidates.algorithm.eq('kmedoids')]
        medoid_ari=float(medoid.iloc[0].ari_vs_kmeans) if len(medoid) else np.nan
        labels_pairs=pairwise.copy();labels_pairs['left']=labels_pairs.left.map(model_title);labels_pairs['right']=labels_pairs.right.map(model_title)
        gmm_best_seed=summary[summary.algorithm.eq('gmm')&summary.covariance.eq(gmm_best.covariance)&summary.k.eq(gmm_best.k)].iloc[0]
        report=f'''# Comparación de algoritmos sobre patrones electorales R2 · 2024

## Resultado principal

**Cambiar de algoritmo no produjo una tipología electoral claramente superior.** K-Means y K-Medoids K=2 describen cortes muy parecidos de un gradiente. GMM añade una descripción probabilística con componentes superpuestas; HDBSCAN sólo encuentra núcleos de cobertura baja e inestable; Ward permite explorar una jerarquía, pero sus cortes son sensibles al remuestreo. No se justifican automáticamente cuatro a seis perfiles ni se declara ganador.

Se ejecutaron realmente **GMM, HDBSCAN, Ward y K-Medoids con bibliotecas reconocidas**. Se reutilizaron quince soluciones K-Means previas (K=2–5 y K=6 de sensibilidad), sin volver a ajustar sus modelos completos. Se hizo un único contraste de punto fijo con KMeans de scikit-learn y dos sensibilidades limitadas, distintas del ajuste principal. La comparación conserva exactamente las **4,648 observaciones × dos coordenadas R2**, con **2,341 municipios** y **LN=98,153,652 (99.82 % del nacional)**. No se releyeron CSV originales ni registros históricos.

## Entorno resuelto y reproducible

El entorno principal sigue siendo Python 3.14.3 AMD64 y carece de SciPy/scikit-learn. El lanzador `py` no enumeraba intérpretes, pero la inspección directa encontró Python 3.13.0 AMD64 en `C:/Users/irene/AppData/Local/Programs/Python/Python313/python.exe`. Los intentos restringidos de PyPI fallaron por sockets bloqueados (WinError 10013), no por una incompatibilidad demostrada de Python 3.14. Se autorizó acceso de red para consultar/instalar wheels en **.venv_pattern_algorithms**, sin instalar en .venv ni en el Python global. No se afirma que 3.14 sea incompatible en general.

{table(versions,['package','version','available'],['Paquete','Versión','Importable'])}

`sklearn.cluster.HDBSCAN` está disponible. `pip check` no encontró dependencias rotas. Los logs de instalación están en metadata/bootstrap; metadata/dependency_validation.json registra intérprete, arquitectura, importaciones y firma de HDBSCAN; metadata/requirements.lock.txt fija todas las dependencias. Se usa NumPy/scikit-learn/SciPy de este entorno para la comparación y la implementación nativa `kmedoids.fasterpam` como contraste opcional. No se implementó GMM o HDBSCAN manualmente. Un aviso inicial de caché de fuentes sin permisos se resolvió usando MPLCONFIGDIR dentro del entorno independiente.

## Población, representación y conservación

Unidad: **municipio + sexo**, no personas ni municipio/edad/sexo como filas separadas. Las bandas 18–34, 35–59 y 60–100 son coordenadas candidatas, no clusters descubiertos. Se revisaron participation_pattern_review.md, contextual_clustering_pilot.md, clustering_methods_review.md y cluster_separation_review.md: cambiar U/R/M puede dominar el contexto, y la edad media agregada generaba franjas. Aquí no se añade edad media, sexo, claves o TIPOSEC a la distancia.

Para cada banda/sexo se mantiene la referencia nacional ΣSV/Σ(SV+NV) de todos los conteos, antes de seleccionar soporte. d es el vector de tres diferencias contra esa referencia. R2 retira su media simple y representa los dos grados de libertad con la base ortonormal fija previa, centrada globalmente y dividida por una única escala RMS. No hay nuevo escalador, rotación aprendida ni normalización de amplitud por perfil. La matriz nueva se contrastó **valor por valor** con el Parquet validado y con sus parámetros. El promedio simple de diferencias no es la participación agregada.

La población elegible sigue exigiendo LN≥100, SV+NV≥100 y filas fuente≥5 **en cada banda**, tasas finitas y edades del núcleo comparable. De los 4,954 perfiles H/M quedan 306 pendientes, con NULL de entrenamiento. Los 999 elegibles con alguna banda NS/LN≥10 % siguen en el principal. Se conservan LN/SV/NV/NS y denominadores por banda; los conteos no entran como coordenadas. Las claves son texto. NS no es abstención. Las filas fuente no prueban independencia entre secciones.

Los 136 municipios sin ningún perfil elegible y los 34 con sólo un sexo siguen siendo límites territoriales; cobertura nominal alta no implica cobertura municipal completa (2,341/2,477 = {pct(2341/2477)}). SEXO=2 (105 filas fuente/LN) y 101+ permanecen en reference/broad_complete_reference.parquet; la edad exacta sigue intacta en la referencia anterior. No se inventan perfiles ni se imputan nulos.

{image('r2_unlabeled.png','Matriz R2 antes de cualquier etiqueta')}

## Diseño controlado y memoria

Todos los ajustes principales reciben la misma matriz R2, mismo orden de row_id y peso uno por perfil. El contexto nacional y la escala R2 se mantienen fijos también en las submuestras: se estudia estabilidad de algoritmos bajo una geometría común, **no validación predictiva independiente de la referencia y el preprocesamiento nacionales**. Un municipio con ambos sexos aporta dos observaciones; no se asume independencia entre ellos.

- **K-Means:** quince modelos previos íntegros. El control sklearn usa sus mismos centroides finales K=2/semilla 17, n_init=1, tol=0 y máximo 1,000 iteraciones. ARI={controls['ari']:.12f}; diferencia de SSE={controls['sse_difference']:.3g}. Es una prueba de punto fijo, no reproducción de la lotería k-means++ ni de todos sus mínimos. Los nuevos Silhouette son exactos; los anteriores eran estimaciones de anclas, por eso pueden diferir sin cambiar etiquetas.
- **GMM:** 54 ajustes = componentes 1–6 × full/diag/tied × semillas 17/42/2024; cinco arranques por banco, tol=1e−4, máximo 1,000 iteraciones, reg_covar=1e−6, todos convergentes. Se conservan modelos nativos, probabilidades y parámetros. Las covarianzas diag dependen de los ejes de la base R2, mientras full permite correlación; más componentes diagonales pueden aproximar una orientación alargada sin implicar más tipos electorales. [GaussianMixture](https://scikit-learn.org/stable/modules/generated/sklearn.mixture.GaussianMixture.html).
- **HDBSCAN:** doce combinaciones tamaño mínimo=50/100/200/400 y min_samples=10/30/60, selección eom, KD-tree, un hilo y allow_single_cluster=True para no impedir una sola región. Dos controles predefinidos con False: 50/10 y 200/30. No se retocó la rejilla después de ver resultados. min_samples de sklearn incluye el propio punto. probabilities_ es fuerza de pertenencia, no posterior GMM; la API no ofrece cluster_persistence_ en este entorno y no se inventó persistencia. [HDBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html).
- **Ward:** un único árbol sobre vectores euclídeos, cortes 2–6; unos 82.4 MiB para distancias condensadas, más memoria interna. No se crea un cuadrado adicional. Los cortes no tienen predicción OOB nativa en esta evaluación. [linkage](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html).
- **K-Medoids:** K=2/3/4, tres semillas y tres arranques aleatorios por ajuste; FasterPAM nativo, máximo 1,000 iteraciones y un hilo. La API exige un cuadrado: se justificó y reutilizó un único buffer euclídeo de 164.8 MiB, bajo presupuesto de 256 MiB, liberado antes de métricas. En remuestras se usa el buffer menor correspondiente. Su objetivo es suma de distancias a medoides, **no SSE**. [Biblioteca nativa](https://python-kmedoids.readthedocs.io/en/latest/index.html).

Silhouette exacto se calcula con sklearn por bloques bajo working_memory=8 MiB; DB usa la misma población asignada. No se almacena una matriz completa para estas métricas. Para un grupo o todo ruido son **n/d**, no cero. HDBSCAN se mide sólo entre asignados y se informa siempre su denominador; no se coloca su índice como si evaluara los 4,648 perfiles.

## Comparación principal

Configuraciones escogidas después de revisar todos los resultados para curvas y estabilidad. La tabla completa de **45 configuraciones**, tamaños de cada grupo y los **97 resultados por semilla/corte** están en metadata/solution_comparison.csv y model_metrics.csv. Para K-Means/K-Medoids se representa el objetivo mínimo dentro de cada configuración; para GMM, BIC mínimo entre semillas del mismo modelo. No se escoge K por esa regla.

{table(candidates,['model_id','groups','sizes','unassigned','metric_population','silhouette','db','ari_vs_kmeans'],['Modelo','Grupos','Tamaños por etiqueta local','Sin asignar','Base índices','S exacto','DB','ARI vs KM del mismo K'])}

{table(candidates,['model_id','assigned_municipalities','assigned_LN','assigned_LN_fraction','assigned_national_LN_fraction','seed_ari_min'],['Modelo','Municipios asignados','LN asignado','Fracción LN elegible','Fracción LN nacional','ARI semillas mín.'])}

En el control completo, K-Medoids K=2 es muy parecido a K-Means K=2 (ARI={medoid_ari:.4f}). La diferencia de Silhouette es mínima y no añade una interpretación electoral distinta por sí sola. Ward K=2 tiene menos concordancia y grupos asimétricos. El Silhouette de HDBSCAN aparece mayor, pero se calculó sobre sólo {int(hdb_assigned):,} asignados: no es una mejora de cobertura ni una evaluación comparable de todos los perfiles.

{image('algorithm_comparison.png','Comparación con misma población, escala y ejes')}

{image('metrics.png','Métricas y criterios dentro de cada familia')}

## GMM: selección de densidad e incertidumbre

{table(gmm.sort_values(['covariance','k']),['covariance','k','bic','aic','ambiguous_80','mean_normalized_entropy','seed_ari_min'],['Covarianza','Componentes','BIC','AIC','Fracción posterior máx.<0.8','Entropía normalizada media','ARI bancos mín.'])}

El BIC mínimo es {gmm_best.bic:.2f} en **{gmm_best.covariance}, K={int(gmm_best.k)}**; AIC favorece {aic_best.covariance}, K={int(aic_best.k)} ({aic_best.aic:.2f}). BIC K=4 full queda a sólo {float(gmm[gmm.covariance.eq('full')&gmm.k.eq(4)].bic.iloc[0]-gmm_best.bic):.2f} del mínimo K=3: no fija un número verdadero de grupos. AIC/BIC comparan densidades GMM ajustadas a esta misma matriz, no clasifican universalmente frente a Ward o K-Means. Su interpretación usual supone observaciones independientes; ambos sexos del municipio pueden depender entre sí, por lo que aquí son criterios exploratorios acompañados de remuestreo. [Criterios y métodos GMM](https://scikit-learn.org/stable/modules/generated/sklearn.mixture.GaussianMixture.html).

En GMM full K=3, **{pct(gmm_best.ambiguous_80)}** tiene posterior máximo<0.8 y entropía normalizada media={gmm_best.mean_normalized_entropy:.3f}. El umbral 0.8 es operativo, no validación de certeza ni probabilidad sobre personas. Las elipses son regiones de masa normal de cada componente, no intervalos de confianza de centroides. Hay superposición significativa en este sentido descriptivo; no se realizó una prueba de significación estadística.

El ARI de bancos usa tres soluciones ganadoras, cada una de cinco arranques; no afirma estabilidad de todos los inicios internos. Como auditoría adicional sólo del candidato, se guardaron tres ajustes de un arranque:

{table(init_summary,['seed','n_init','bic','converged','ari_vs_best_bank'],['Semilla','Arranques','BIC','Converge','ARI con mejor banco'])}

Los componentes separan aproximadamente un núcleo de forma cercana al promedio y desviaciones de inclinación opuesta. No son tres bloques electorales sin solapamiento. Los extremos pueden estar asociados a tamaño y soporte: la tabla muestra medianas de LN por perfil y del menor denominador entre sus bandas; esa asociación no prueba error o sesgo.

{table(gsupport,['cluster','profiles','LN','median_profile_LN','median_min_specified','high_ns_fraction'],['Componente duro','Perfiles','LN','Mediana LN perfil','Mediana menor SV+NV','Fracción alguna banda NS alto'])}

{image('gmm_overlap.png','GMM, superposición y regiones de asignación')}

## HDBSCAN: cobertura y sensibilidad

{table(hdb.sort_values(['allow_single_cluster','min_cluster_size','min_samples']),['min_cluster_size','min_samples','allow_single_cluster','groups','assigned','noise_fraction','assigned_municipalities','assigned_LN_fraction','silhouette'],['Tamaño mínimo','Vecinos','Permite único','Grupos','Asignados','Fracción ruido','Municipios asignados','Fracción LN elegible','S sólo asignados'])}

La rejilla que permite un solo grupo produce un núcleo y **{pct(hdb[hdb.allow_single_cluster.eq(True)].noise_fraction.min())}–{pct(hdb[hdb.allow_single_cluster.eq(True)].noise_fraction.max())} de ruido**. El control 50/10 sin grupo único encuentra tres grupos, pero deja {pct(hdb_selected.noise_fraction)} sin asignar; cubre {int(hdb_selected.assigned_municipalities)} municipios y {pct(hdb_selected.assigned_LN_fraction)} del LN elegible. El control 200/30 sin único deja todo ruido. No se ensayaron nuevos parámetros para lograr cuatro a seis grupos.

Ruido significa sin asignación por este algoritmo y parámetros, no registro inválido o abstención. Las curvas del ruido se conservan en gris, sin incluirlo como cluster electoral. Las sensibilidades por pares de toda la rejilla están en metadata/hdbscan_parameter_stability.csv; incluyen ARI con ruido, ARI sólo de asignados en ambos y Jaccard de cobertura. Un ARI alto de ruido o un único grupo no prueba varios clusters estables.

{image('hdbscan_noise.png','Clusters detectados y observaciones sin asignar')}

{image('uncertainty_and_coverage.png','Incertidumbre GMM y cobertura HDBSCAN')}

## Ward: jerarquía útil para explorar, cortes frágiles

{table(ward,['k','height_before','height_after','height_gap','height_ratio'],['Corte K','Altura anterior','Altura siguiente','Salto','Cociente'])}

El salto final mayor está entre dos y un grupo (cociente {ward.loc[ward.k.eq(2),'height_ratio'].iloc[0]:.3f}); también hay fusiones progresivas para K=3/4. Eso describe el árbol bajo Ward y no constituye prueba de clases naturales: una nube continua alargada también tiene saltos al final. La inestabilidad municipal y frente a NS de abajo impide presentar ese salto como confirmación robusta de dos o más perfiles. Las etiquetas son locales al corte y no tienen orden electoral.

{image('ward_dendrogram.png','Dendrograma truncado y alturas finales')}

## Curvas y concordancia electoral

Las curvas promedian perfiles con peso uno. Las tablas guardan también ΣSV/Σ(SV+NV) por banda y cluster, y participación agregada del perfil completo; no confundir esos cocientes con medias simples. Una forma positiva en jóvenes significa desviación respecto al nivel relativo propio, no mayor tasa juvenil absoluta que la de mayores.

{table(shape_table,['model_id','cluster',*BANDS],['Modelo','Etiqueta local','Forma 18–34 (pp)','35–59 (pp)','60–100 (pp)'])}

{table(candidate_profiles,['model_id','cluster','observations','municipalities','women_fraction','participation_observed','unspecified_rate'],['Modelo','Etiqueta','Perfiles','Municipios','Fracción mujeres','Participación agregada','NS/LN'])}

K-Means y K-Medoids describen el mismo contraste principal jóvenes–mayores con pequeñas diferencias de frontera. Ward K=2 aísla una parte de ese gradiente y agrupa el resto; GMM añade un centro y colas con distinta dispersión, muy superpuestos. Los pequeños núcleos de HDBSCAN no amplían esa lectura a la mayoría de municipios. No se infieren conductas individuales ni efectos causales de edad, sexo, municipio o NS.

{image('relative_curves.png','Diferencias relativas originales por grupo')}

{image('shape_curves.png','Formas tras retirar el nivel general')}

{image('absolute_curves.png','Tasas absolutas medias por grupo')}

{table(labels_pairs,['left','right','ari_common_all','ari_common_both_assigned','both_assigned'],['Izquierda','Derecha','ARI total (ruido=etiqueta)','ARI asignados en ambos','Base asignada común'])}

El ARI no requiere alinear números de etiqueta y no es exactitud contra verdad electoral. Para HDBSCAN ambas bases son distintas; una concordancia parcial en el subconjunto asignado no equivale a concordancia global. No se comparó ARI con B, edades exactas u otras unidades incompatibles.

## Estabilidad municipal y peores casos

Se seleccionaron después de G: GMM full K=3 por BIC y lectura de densidad, Ward K=2 como corte parsimonioso, HDBSCAN 50/10 sin único como diagnóstico de sus pequeños núcleos y K-Medoids K=2 como control próximo a K-Means. La selección no es una recomendación de desplegar HDBSCAN de baja cobertura. Se ejecutaron **cuarenta modelos municipales** en diez submuestras compartidas de 1,981/2,477 municipios; ambos sexos elegibles entran o salen juntos. Se reutilizaron las diez predicciones K-Means K=2 previas, verificando que la recalibración escalar anterior es una transformación afín que produce exactamente las mismas etiquetas en el R2 fijo actual.

Cada muestra conserva {coverage.training_profiles.min():,}–{coverage.training_profiles.max():,} perfiles, {coverage.training_municipalities.min():,}–{coverage.training_municipalities.max():,} municipios elegibles y {pct(coverage.eligible_LN_fraction.min())}–{pct(coverage.eligible_LN_fraction.max())} del LN elegible. OOB tiene {coverage.oob_profiles.min():,}–{coverage.oob_profiles.max():,} perfiles. Las membresías y coberturas completas están guardadas. No es bootstrap con reemplazo ni una estimación de incertidumbre de votantes.

GMM predice OOB con su modelo nativo. K-Medoids proyecta al medoide de entrenamiento más cercano bajo la misma distancia, guardando esa regla. Ward/HDBSCAN se vuelven a agrupar sólo en la submuestra y se comparan **sobre observaciones comunes de entrenamiento**: no se les atribuye predicción OOB ni se les asignan los municipios restantes por centroides. Los n/d de OOB no son cero ni un fallo oculto.

{table(robust,['model_id','oob_median','oob_min','common_median','common_min','both_assigned_median','assignment_jaccard_median','assignment_jaccard_min'],['Modelo','ARI OOB med.','Mín.','ARI comunes med.','Mín.','ARI asignados ambos med.','Jaccard asignación med.','Mín.'])}

K-Means K=2 tiene ARI OOB mediano {r.loc['kmeans','oob_median']:.3f}, mínimo {r.loc['kmeans','oob_min']:.3f}; K-Medoids, {r.loc['kmedoids','oob_median']:.3f}/{r.loc['kmedoids','oob_min']:.3f}. GMM K=3, {r.loc['gmm','oob_median']:.3f}/{r.loc['gmm','oob_min']:.3f}. Ward sólo en comunes baja hasta {r.loc['ward','common_min']:.3f}. HDBSCAN cambia el número de grupos entre {int(stability[stability.algorithm.eq('hdbscan')].sample_groups.min())} y {int(stability[stability.algorithm.eq('hdbscan')].sample_groups.max())}, con Jaccard mínimo de asignación {r.loc['hdbscan','assignment_jaccard_min']:.3f}. Los índices sobre distintas bases no son una clasificación común de estabilidad.

{table(pd.DataFrame(worst),['model_id','replicate','comparison_base','ari','profiles','changed','changed_fraction','change_rule'],['Modelo','Peor muestra','Base','ARI','Perfiles','Cambian','Fracción','Regla de cambio'])}

Para modelos con igual K se cuentan cambios tras maximizar solapamiento; no se comparan etiquetas arbitrarias. En HDBSCAN se muestra **cambio de estado ruido/asignado**, sin forzar correspondencias entre distintos números de clusters. Las observaciones y claves de cada peor caso se conservan en metadata/worst_case_changes.parquet; curvas y tamaños de todas las muestras quedan en resampling_profiles.csv y resampling_curves.csv. Las colas débiles no se ocultan tras las medianas. Diez muestras son exploratorias; las semillas estables no sustituyen esta prueba territorial.

{image('municipality_stability.png','Estabilidad con bases de evaluación explícitas')}

## Sensibilidad de NS y pesos

El principal conserva todos los 999 perfiles con alguna coordenada NS/LN≥10 %. Como sensibilidad separada se entrena sobre los restantes **3,649 perfiles**, LN=81,293,260, manteniendo la referencia nacional y R2 fijos. Los perfiles de NS alto permanecen en fuentes y etiquetas/proyecciones separadas. Esto cambia población y distribución de variables; no estima lo que votarían los registros NS ni un efecto causal de NS.

{table(sensitivity,['model_id','scenario','training_profiles','training_LN','common_ari_display','ari_all_eligible','assignment_jaccard'],['Modelo','Escenario','Perfiles entrenados','LN entrenado','ARI comunes','ARI proyecciones todos','Jaccard asignación'])}

GMM y K-Means pueden proyectar el subconjunto NS alto sin fingir que entrenó. Ward/HDBSCAN no lo proyectan. Para HDBSCAN la sensibilidad NS cambia también la cantidad de clusters; ARI sobre ruido y cobertura se conservan separados. No se mezclan índices de calidad obtenidos con distintas poblaciones.

Peso uno por municipio equivale aquí a 1/n_perfiles_elegibles del municipio: los 2,307 con ambos sexos tienen masa total uno igual a los 34 con sólo uno. El control ponderado K-Means K=2 tiene ARI={sensitivity[sensitivity.scenario.eq('equal_municipality')].ari_all_eligible.iloc[0]:.4f}. Se inicia desde los mismos centros principales, n_init=1: es sensibilidad local al objetivo, no una exploración global de mínimos. Las APIs usadas de GMM, HDBSCAN, linkage y FasterPAM no admiten sample_weight; no se inventan réplicas de perfiles para simularlo. LN concentraría influencia en municipios grandes y no es garantía de calidad; **no se usa automáticamente como peso** ni se declara resuelta esta limitación para otras familias.

## Qué estructura respaldan los resultados

| Posibilidad | Evidencia observada | Alcance de la conclusión |
| --- | --- | --- |
| A. Regiones diferenciadas | HDBSCAN encuentra tres pequeños núcleos sólo en un control, con ruido alto y sensibilidad. | No respalda una partición densa y estable de la mayoría de la población. |
| B. Componentes superpuestas | GMM full mejora densidad con tres/cuatro componentes y muchos posteriores máximos bajos. | Componentes de una mezcla no equivalen a tipos electorales separados. |
| C. Gradiente continuo | R2 previo concentra 86.30 % de variación de forma en jóvenes–mayores; K-Means/medoides cortan ese mismo eje dominante. | Es la lectura descriptiva más consistente, sin una prueba formal que descarte toda multimodalidad. |
| D. Jerarquía útil | Ward tiene saltos finales visibles, pero cortes sensibles a municipios y NS. | Útil para explorar niveles de detalle; no confirma fronteras naturales robustas. |

## Respuestas y recomendación

1. **Ejecutados realmente:** GMM (54 bancos), HDBSCAN (14 configuraciones), Ward (un árbol/cinco cortes) y K-Medoids (nueve ajustes). K-Means principal se reutilizó; hubo un contraste independiente, sensibilidades explícitas y tres auditorías GMM de un arranque. No se simulan algoritmos inaccesibles.
2. **Más diferenciados:** ningún método demuestra una mejora global clara. HDBSCAN tiene S alto sólo en un pequeño subconjunto; K-Medoids K=2 apenas cambia K-Means; GMM reconoce superposición en lugar de eliminarla; Ward no mejora robustez.
3. **Estructura o gradiente:** los métodos describen sobre todo un mismo gradiente y un núcleo con colas, con distintas fronteras y dispersiones. La comparación no demuestra clases electorales discretas.
4. **GMM superpuesto:** sí, {pct(gmm_best.ambiguous_80)} de posterior máximo<0.8 en full K=3; elipses, entropía y curvas lo documentan. No son certezas individuales ni una prueba de significación.
5. **HDBSCAN:** principalmente ruido bajo esta rejilla; los tres núcleos del control sólo cubren {pct(hdb_selected.assigned_LN_fraction)} del LN elegible y no mantienen asignaciones estables al remuestrear. No permite asignar perfiles a toda la cobertura municipal.
6. **Ward:** muestra jerarquía matemática y saltos, pero el mínimo ARI común {r.loc['ward','common_min']:.3f} y sensibilidad NS no confirman una estructura electoral robusta. No tiene OOB en esta entrega.
7. **Concordancia:** alta entre K-Means/K-Medoids K=2 (ARI {medoid_ari:.3f}), parcial o baja con otros métodos. Diferencias entre componentes, cortes y ruido no se resuelven por nombres de etiquetas.
8. **Cuatro a seis:** no hay evidencia suficiente para imponerlos. BIC favorece tres componentes GMM y AIC cuatro, muy superpuestos; HDBSCAN no descubre ese rango robusto. Más cortes no prueban más perfiles.
9. **Continuar:** mantener K-Means K=2 como resumen provisional y K-Medoids K=2 como control de robustez; GMM full K=3 merece seguimiento **como densidad y asignación incierta**, con K=4 como contraste AIC pendiente de mayor validación, no como tres perfiles definitivos. No hay ganador general ni motivo para promover Ward/HDBSCAN como taxonomía de cobertura completa.
10. **Representación:** no conviene seguir cambiando algoritmos sólo para obtener fronteras visuales. Es más defendible mostrar el contraste continuo y las curvas con denominadores. Si la pregunta exige mayor riqueza electoral, revisar soporte por coordenada, NS, amplitud de forma, patrones H/M conjuntos, bandas o curvas suaves y validación externa antes de construir otra matriz. La evidencia previa de edades exactas advierte pérdida de soporte; agregar U/R/M cambia el objetivo hacia contexto. No se modifica aquí ninguna representación ni se presupone que otra producirá clusters naturales.

La elección para ParticipaMX debe precisar si se quiere un resumen continuo o etiquetas operativas y qué ambigüedad/cobertura son aceptables. Una etiqueta estable no es un comportamiento individual, y un modelo probabilístico de densidad no valida por sí solo perfiles ciudadanos.

## Integridad, tiempos y recuperación

Se completaron A–I. A–G verifican dependencias, matriz, familias y comparación; H limita estabilidad y calidad; I genera gráficas y valida salidas. No quedan algoritmos principales sin ejecutar. Persisten decisiones metodológicas y validación externa, no una comparación inventada por falta de paquetes.

{table(timings,['stage','seconds','working_set_MiB','peak_working_set_MiB'],['Etapa A–H','Segundos','Working set MiB','Pico del proceso MiB'])}

La etapa I se registra al terminar en checkpoint_I.json. Los picos de Windows son máximos del proceso y no sumas entre etapas; las distintas invocaciones reinician ese contador. No incluyen la instalación del entorno. Se limitó BLAS/OMP a un hilo. Los modelos tienen marcadores individuales, hashes de entradas/parámetros, NPZ y modelos nativos joblib del propio experimento; los temporales se publican atómicamente y un lock impide duplicados. Un checkpoint válido se verifica y omite, sin repetir ajustes. Un error conserva etapas previas y traceback en state.json; _SUCCESS sólo se publica al terminar todas las comprobaciones.

Se conciliaron tasas y referencia nacional, unicidad, claves de texto, LN=SV+NV+NS, las 4,648 filas comunes, metadatos y pendientes, conteos por grupo **incluido ruido**, escritura/lectura de Parquet, finitud, convergencia GMM, SSE/etiquetas del control sklearn y equivalencia afín de las diez remuestras K-Means. Se preservan los 4,954 perfiles H/M, el agregado broad completo y la referencia de SEXO=2/101+. Los hashes de {len(self.state['protected_hashes']):,} archivos previos se verifican antes de finalizar; no se modifican datos, informes anteriores, scripts previos, ZIP ni frontend. No se crean commits.

Resultados: reference/ y features/ conservan población y matriz; models/ guarda bibliotecas y modelos recuperables; assignments/ contiene etiquetas experimentales con pendientes NULL y ruido −1; resampling/ guarda membresías y etiquetas/proyecciones distinguidas; metadata/ contiene métricas, probabilidades de configuración, soporte, composición/curvas, incertidumbre, estabilidad, peores casos, dependencias y manifiestos. Los posteriores individuales GMM y fuerza HDBSCAN se guardan en cada arrays.npz, alineados a features/r2.parquet. No sumar vistas/modelos alternativos como registros independientes.

## Reproducción

Desde la raíz, crear un entorno nuevo con Python 3.13 y las versiones fijadas; no instalar sobre .venv:

```powershell
& 'C:/Users/irene/AppData/Local/Programs/Python/Python313/python.exe' -m venv .venv_pattern_algorithms
.venv_pattern_algorithms/Scripts/python.exe -m pip install --only-binary=:all: -r data/processed/pattern_algorithm_comparison/metadata/requirements.lock.txt
.venv_pattern_algorithms/Scripts/python.exe -m pip check
.venv_pattern_algorithms/Scripts/python.exe analysis/scripts/compare_pattern_algorithms.py --until G
.venv_pattern_algorithms/Scripts/python.exe analysis/scripts/compare_pattern_algorithms.py --until H --gmm-model {gmm_best.model_id} --ward-k 2 --hdbscan-model {hdb_selected.model_id}
.venv_pattern_algorithms/Scripts/python.exe analysis/scripts/compare_pattern_algorithms.py --gmm-model {gmm_best.model_id} --ward-k 2 --hdbscan-model {hdb_selected.model_id}
.venv_pattern_algorithms/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_compare_pattern_algorithms.py
```

No recrear un entorno ya instalado sólo para reanudar. Cada comando retoma checkpoints; con _SUCCESS íntegro sólo verifica y termina. Para una reproducción completa nueva elegir --output, --charts y --report nuevos. Si las bibliotecas principales no están importables, el script guarda diagnóstico y se detiene sin repetir K-Means como sustituto. Los archivos derivados existentes sin estado verificable se conservan y se rechaza sobrescribirlos. Los modelos joblib sólo se cargan tras comprobar los hashes del propio experimento.
'''
        atomic_bytes(self.report,report.encode('utf8'))
        return paths

    def run(self,until,selection):
        final=self.output/'metadata/run_manifest.json'
        if (self.output/'_SUCCESS').exists():
            marker=json.loads((self.output/'_SUCCESS').read_text());manifest=json.loads(final.read_text(encoding='utf8'))
            require(marker['manifest_sha256']==file_hash(final) and manifest['status']=='validated','Marcador final inconsistente.')
            for relative,digest in manifest['artifact_hashes'].items():require(file_hash(self.root/relative)==digest,'Salida final alterada.')
            print('Resultado validado y verificado; cero modelos repetidos.',flush=True);return
        stage='A'
        try:
            for stage in 'ABCDEFGHI':
                if self.valid_stage(stage):print(f'{stage}: checkpoint verificado; no se repite.',flush=True)
                elif stage=='H':self.stage_h(selection)
                else:getattr(self,'stage_'+stage.lower())()
                if stage==until and stage!='I':return
            self.verify_protected();self.state.update(status='validated',finished=utc());write_json(self.state_path,self.state)
            artifacts={str(p.relative_to(self.root)):file_hash(p) for base in [self.output,self.charts] for p in base.rglob('*')
                if p.is_file() and p not in [final,self.output/'_RUNNING.json',self.output/'_SUCCESS']}
            artifacts[str(self.report.relative_to(self.root))]=file_hash(self.report)
            write_json(final,dict(status='validated',dependencies=self.dependencies,stages=self.state['stages'],
                protected_hashes=self.state['protected_hashes'],artifact_hashes=artifacts,
                script_sha256=file_hash(Path(__file__)),test_sha256=file_hash(self.root/'analysis/scripts/test_compare_pattern_algorithms.py')))
            write_json(self.output/'_SUCCESS',dict(manifest_sha256=file_hash(final)));print(f'VALIDADO: {self.report}',flush=True)
        except Exception as error:
            self.state['status']='failed';self.state['errors'].append(dict(stage=stage,at=utc(),error=repr(error),traceback=traceback.format_exc()))
            write_json(self.state_path,self.state);raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output',type=Path,default=Path('data/processed/pattern_algorithm_comparison'))
    parser.add_argument('--charts',type=Path,default=Path('analysis/charts/pattern_algorithm_comparison'))
    parser.add_argument('--report',type=Path,default=Path('analysis/reports/pattern_algorithm_comparison.md'))
    parser.add_argument('--until',choices=list('ABCDEFGHI'),default='I')
    parser.add_argument('--replicates',type=int,default=10)
    parser.add_argument('--gmm-model');parser.add_argument('--hdbscan-model');parser.add_argument('--ward-k',type=int)
    args=parser.parse_args();root=args.root.resolve();output=(root/args.output).resolve()
    require(2<=args.replicates<=10,'Estabilidad limitada a 2–10 submuestras.')
    dependencies=probe_dependencies()
    if not dependencies['required_algorithms']['available']:
        diagnostic=root/'analysis/reports/pattern_algorithm_dependency_diagnosis.md'
        require(not diagnostic.exists(),'Ya existe diagnóstico; no sobrescribir.')
        atomic_bytes(diagnostic,('# Dependencias no resueltas\n\nNo se entrenaron modelos alternativos ni se repitió K-Means.\n\n```json\n'+json.dumps(dependencies,indent=2,ensure_ascii=False)+'\n```\n\nUsar el entorno independiente descrito en metadata/requirements.lock.txt, si existe.').encode('utf8'))
        raise SystemExit('Faltan bibliotecas; se guardó diagnóstico y se detuvo la etapa.')
    with experiment_lock(output):
        experiment=Comparison(root,output,root/args.charts,root/args.report,args.replicates)
        experiment.run(args.until,dict(gmm=args.gmm_model,hdbscan=args.hdbscan_model,ward=args.ward_k))


if __name__=='__main__':main()

