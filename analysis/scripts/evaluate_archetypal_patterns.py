"""Arquetipos electorales recuperables: combinaciones convexas, no clusters.

Reutiliza perfiles validados. La biblioteca AA no se reimplementa; sus atributos
reales, aproximación NNLS y criterio de parada se auditan antes del entrenamiento.
"""
from __future__ import annotations

import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.environ['MPLCONFIGDIR'] = str(ROOT/'.venv_archetypal_patterns/mplconfig')
for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
    os.environ[name] = '1'
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import inspect
import io
import itertools
import json
import platform
import subprocess
import time
import traceback

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment, minimize
from scipy.spatial.distance import cdist
from archetypes import AA
import archetypes
import sklearn
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from clean_data import require, file_hash
from build_descriptive import METRICS
from build_cluster_features import snapshot_inputs
from build_profile_candidates import table_text
from compare_pattern_algorithms import Comparison
from evaluate_participation_patterns import (atomic_bytes, write_table, save_figure,
    experiment_lock, memory_estimate, utc)

BANDS = {'three': ['18-34', '35-59', '60-100'], 'four': ['18-29', '30-44', '45-59', '60-100']}
KEYS = ['EDOCVE', 'MPIOCVE', 'SEXO']
MUNICIPAL_KEYS = KEYS[:2]
SEEDS = [17, 42, 2024]
NATIONAL_LN = 98330348
OWN_FILES = ['evaluate_archetypal_patterns.py', 'test_evaluate_archetypal_patterns.py']
CONFIG = dict(version='1.0', seeds=SEEDS, ks=[2,3,4,5,6], max_iter=300, tol=1e-4,
    initialization='random', starts_per_seed=1, extreme_fraction=.01, high_ns=.10,
    minimum_sections=5, convex_tolerance=1e-8, subsamples=10,
    maximum_validation_configurations=3, dominance_threshold=.8)
SOURCES = {
    'cutler_breiman_1994': 'https://www.stat.cmu.edu/technometrics/90-00/vol-36-04/v3604338.pdf',
    'eugster_leisch_2011': 'https://www.sciencedirect.com/science/article/pii/S0167947310004056',
    'robust_author_preprint_2010': 'https://epub.ub.uni-muenchen.de/11498/1/tr82.pdf',
    'official_documentation': 'https://archetypes.readthedocs.io/en/latest/',
    'official_repository': 'https://github.com/aleixalcacer/archetypes'}


def json_safe(value):
    if isinstance(value, dict): return {str(k): json_safe(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray): return json_safe(value.tolist())
    if isinstance(value, np.generic): return json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value): return None
    if isinstance(value, Path): return str(value)
    return value


def write_json(path, value):
    atomic_bytes(Path(path), json.dumps(json_safe(value), ensure_ascii=False,
        indent=2, allow_nan=False).encode('utf8'))


def basis(p):
    q = np.zeros((p,p-1))
    for j in range(p-1):
        q[:j+1,j] = 1/np.sqrt((j+1)*(j+2))
        q[j+1,j] = -(j+1)/np.sqrt((j+1)*(j+2))
    return q


def fit_scaler(d, geometry, row_ids):
    d = np.asarray(d, float)
    require(np.isfinite(d).all() and len(d)>1, 'Matriz de entrenamiento inválida.')
    p = d.shape[1]; q = basis(p); m = d.mean(1); c = d@q
    result = dict(geometry=geometry,p=p, n=len(d), basis=q.tolist(),
        delta_mean=d.mean(0).tolist(), common_scale=float(np.sqrt(np.mean(np.sum((d-d.mean(0))**2,1)))),
        level_mean=float(m.mean()), level_scale=float(m.std(ddof=0)),
        shape_mean=c.mean(0).tolist(), shape_scale=float(np.sqrt(np.mean(np.sum((c-c.mean(0))**2,1)))),
        fitted_row_ids_sha256=hashlib.sha256('\n'.join(row_ids).encode()).hexdigest(),
        level_original_variance_fraction=float(p*m.var()/np.var(d,axis=0).sum()), ddof=0)
    require(min(result['common_scale'],result['level_scale'],result['shape_scale'])>1e-12, 'Escala degenerada.')
    return result


def transform(d, s):
    d=np.asarray(d,float)
    if s['geometry']=='AA1': return (d-s['delta_mean'])/s['common_scale']
    return np.column_stack([(d.mean(1)-s['level_mean'])/s['level_scale'],
        (d@np.asarray(s['basis'])-s['shape_mean'])/s['shape_scale']])/np.sqrt(2)


def inverse(x, s):
    x=np.asarray(x,float)
    if s['geometry']=='AA1': return x*s['common_scale']+s['delta_mean']
    level=x[:,0]*np.sqrt(2)*s['level_scale']+s['level_mean']
    shape=x[:,1:]*np.sqrt(2)*s['shape_scale']+s['shape_mean']
    return level[:,None]+shape@np.asarray(s['basis']).T


def validate_convex(alpha, beta, z, train, evaluation):
    n,p=evaluation.shape; k=len(z); tol=CONFIG['convex_tolerance']
    require(alpha.shape==(n,k) and beta.shape==(k,len(train)) and z.shape==(k,p), 'Dimensiones convexas incorrectas.')
    for name,a in [('alpha',alpha),('beta',beta)]:
        require(np.isfinite(a).all() and a.min()>=-tol and np.max(abs(a.sum(1)-1))<=tol, name+' no convexo.')
    residual=float(np.max(abs(z-beta@train)))
    require(residual<=tol*max(1.,np.max(abs(train))), 'Arquetipos fuera de combinación convexa declarada.')
    require((z>=train.min(0)-tol).all() and (z<=train.max(0)+tol).all(), 'Límites marginales violados.')
    require(np.isfinite(alpha@z).all(),'Reconstrucción no finita.')
    return dict(alpha_min=float(alpha.min()), beta_min=float(beta.min()),
        alpha_sum_error=float(np.max(abs(alpha.sum(1)-1))), beta_sum_error=float(np.max(abs(beta.sum(1)-1))),
        archetype_convex_residual=residual)


def synthetic_validation():
    """Verifica AA y contrasta transform con SLSQP independiente en un triángulo."""
    x=np.array([[0.,0.],[1.,0.],[0.,1.],[.2,.3],[.7,.1],[.1,.7]])
    m=AA(n_archetypes=3, algorithm_init='random', n_init=1,max_iter=200,tol=1e-6,random_state=17).fit(x)
    held=np.array([[.3,.4],[-.1,.1],[.8,.7]])
    a=m.transform(held); z=m.archetypes_
    checks=validate_convex(a,m.betas_,z,x,held)
    errors=[]
    for y,coef in zip(held,a):
        opt=minimize(lambda w: np.sum((w@z-y)**2),np.ones(3)/3,method='SLSQP',
            bounds=[(0,1)]*3,constraints={'type':'eq','fun':lambda w:w.sum()-1},
            options={'ftol':1e-12,'maxiter':200})
        require(opt.success, 'SLSQP sintético falló.')
        errors.append(float(np.sum((coef@z-y)**2)-opt.fun))
    rmse=float(np.sqrt(np.mean((x-m.transform(x)@z)**2)))
    require(rmse<1e-4 and max(errors)<1e-6,'Biblioteca no supera el contraste sintético.')
    return dict(status='passed',api_signature=str(inspect.signature(AA)), fit_signature=str(inspect.signature(AA.fit)),
        alpha_attribute='alphas_', beta_attribute='betas_', archetypes_attribute='archetypes_',
        coefficients_attribute_available=hasattr(m,'coefficients_'), arch_coefficients_attribute_available=hasattr(m,'arch_coefficients_'),
        convergence_attribute_available=hasattr(m,'converged_'),iterations=int(m.n_iter_)+1,
        synthetic_rmse=rmse, projection_sse_excess_slsqp=max(errors),constraints=checks,
        source_sha256=file_hash(Path(inspect.getfile(AA))),
        implementation='NNLS con coordenada aumentada 200 y renormalización; parada por cambio absoluto de norma de Frobenius; no RSS cuadrática.',
        default_initialization_rejected='furthest_sum tiene una rama para muestras pequeñas con np.mat retirado y matriz N×N; la prueba triangular activa esa rama. Su rama para N grande es lineal. random evita ambos riesgos sin parchear código.',
        formal_robust_available=False)


def mixture_statistics(alpha):
    entropy=-np.sum(alpha*np.log(np.maximum(alpha,1e-300)),1)/np.log(alpha.shape[1])
    return pd.DataFrame(dict(max_coefficient=alpha.max(1),normalized_entropy=entropy,
        substantial_coefficients=(alpha>=.1).sum(1), dominated=alpha.max(1)>=CONFIG['dominance_threshold']))


def aligned(reference, alternative):
    # Sólo K×K; nunca observaciones×observaciones.
    cost=cdist(reference,alternative)/np.sqrt(reference.shape[1])
    left,right=linear_sum_assignment(cost)
    require(np.array_equal(left,np.arange(len(reference))),'Alineación incompleta.')
    return right,cost[left,right]


def errors_summary(x,recon,d,raw_recon,baseline):
    squared=np.sum((x-recon)**2,1); base=float(np.sum((x-baseline)**2))
    individual=np.sqrt(np.mean((d-raw_recon)**2,1))*100
    return dict(n=len(x),sse=float(squared.sum()),geometry_rmse=float(np.sqrt(squared.mean()/x.shape[1])),
        normalized_rmse=float(np.sqrt(squared.sum()/base)) if base>1e-15 else None,
        raw_rmse_pp=float(np.sqrt(np.mean((d-raw_recon)**2))*100),
        error_median_pp=float(np.median(individual)),error_p90_pp=float(np.quantile(individual,.9)),
        error_p95_pp=float(np.quantile(individual,.95)),error_max_pp=float(individual.max()))


class Experiment:
    # Sólo reutiliza almacenamiento atómico y checkpoints; no ejecuta clustering previo.
    valid_stage=Comparison.valid_stage
    table=Comparison.table
    bundle=Comparison.bundle
    bundle_paths=Comparison.bundle_paths
    load_arrays=Comparison.load_arrays
    load_model=Comparison.load_model

    def checkpoint(self,stage,paths,started,summary):
        record=dict(status='complete',stage=stage,finished=utc(),seconds=time.monotonic()-started,
            memory=memory_estimate(),summary=summary,versions=self.dependencies['imports'],
            script_sha256=file_hash(Path(__file__)),
            artifacts={str(p.relative_to(self.root)):file_hash(p) for p in paths})
        write_json(self.output/f'metadata/checkpoint_{stage}.json',record)
        self.state['stages'][stage]=dict(seconds=record['seconds'],summary=summary)
        write_json(self.state_path,self.state);print(f'Etapa {stage}: {summary}',flush=True)

    def __init__(self,root,output,charts,report):
        self.root,self.output,self.charts,self.report=[Path(p).resolve() for p in [root,output,charts,report]]
        require(self.output.is_relative_to(self.root/'data/processed') and self.charts.is_relative_to(self.root/'analysis/charts')
            and self.report.is_relative_to(self.root/'analysis/reports'),'Destinos fuera del proyecto.')
        self.source=self.root/'data/processed/age_band_representation_review'
        self.state_path=self.output/'metadata/state.json'
        import scipy,pyarrow,joblib
        self.dependencies=dict(imports={k:v.__version__ for k,v in [('numpy',np),('pandas',pd),('sklearn',sklearn),
            ('scipy',scipy),('pyarrow',pyarrow),('archetypes',archetypes),('joblib',joblib),('matplotlib',matplotlib)]})
        if self.state_path.exists():
            self.state=json.loads(self.state_path.read_text(encoding='utf8'))
            require(self.state['config']==CONFIG and self.state['dependencies']==self.dependencies,'Cambió el contrato o entorno; usar destinos nuevos.')
            require(self.state['charts']==str(self.charts) and self.state['report']==str(self.report),'Destinos distintos.')
            self.verify_protected()
        else:
            require(not self.report.exists() and not self.charts.exists(), 'Se protegen destinos anteriores.')
            protected=snapshot_inputs(self.root,self.output,self.charts)
            for directory in ['analysis/scripts','src','public']:
                for path in (self.root/directory).rglob('*'):
                    if path.is_file() and '__pycache__' not in path.parts and path.name not in OWN_FILES:
                        protected[str(path)]=file_hash(path)
            for name in ['.gitignore','.venv_pattern_algorithms/pyvenv.cfg',
                '.venv_pattern_algorithms/Lib/site-packages/sklearn/__init__.py']:
                path=self.root/name;protected[str(path)]=file_hash(path)
            self.state=dict(started=utc(),status='running',config=CONFIG,dependencies=self.dependencies,
                protected_hashes=protected,stages={},errors=[],charts=str(self.charts),report=str(self.report))
            write_json(self.state_path,self.state)

    def verify_protected(self):
        for path,digest in self.state['protected_hashes'].items(): require(file_hash(path)==digest, 'Entrada previa modificada: '+path)

    def frame(self,context): return pd.read_parquet(self.output/f'matrices/{context}/metadata.parquet')
    def scaler(self,context,geometry): return json.loads((self.output/f'matrices/{context}/{geometry}/scaler.json').read_text())
    def values(self,context,geometry):
        f=pd.read_parquet(self.output/f'matrices/{context}/{geometry}/features.parquet')
        return f.drop(columns='row_id').to_numpy(float)

    def stage_a(self):
        started=time.monotonic();paths=[]
        checks=synthetic_validation()  # Prohibido pasar a datos reales antes de este control.
        dependency=dict(**self.dependencies,python=sys.version,architecture=platform.architecture(),executable=sys.executable,
            sklearn_file=sklearn.__file__,archetypes_file=archetypes.__file__,synthetic=checks,
            isolation='Entorno nuevo; .pth reutiliza bibliotecas previas sólo para lectura. sklearn 1.5.2 y archetypes 0.6.2 instalados en el nuevo entorno.',
            failed_initial_probes=['sklearn 1.9.1: _validate_data ausente','furthest_sum: np.mat retirado en NumPy 2'],sources=SOURCES)
        result=subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True)
        require(result.returncode==0,'pip check falló: '+result.stdout+result.stderr)
        dependency['pip_check']=result.stdout
        write_json(self.output/'metadata/dependency_validation.json',dependency);paths.append(self.output/'metadata/dependency_validation.json')
        for name in ['installation_plan.json','installation_actual.json','sklearn_compatibility_install.json','prior_environment.pth']:
            source=self.root/'.venv_archetypal_patterns'/name
            if name.endswith('.pth'):source=self.root/'.venv_archetypal_patterns/Lib/site-packages'/name
            if source.exists():
                target=self.output/'metadata/bootstrap'/name;atomic_bytes(target,source.read_bytes());paths.append(target)
        atomic_bytes(self.output/'metadata/bootstrap/archetypes_source.py',Path(inspect.getfile(AA)).read_bytes())
        paths.append(self.output/'metadata/bootstrap/archetypes_source.py')
        freeze=subprocess.run([sys.executable,'-m','pip','freeze'],capture_output=True,text=True,check=True)
        atomic_bytes(self.output/'metadata/requirements.lock.txt',freeze.stdout.encode());paths.append(self.output/'metadata/requirements.lock.txt')
        diagnosis=subprocess.run(['powershell','-NoProfile','-Command',
            'Get-Process -Name python,pythonw,python3 -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,StartTime | ConvertTo-Json'],capture_output=True,text=True)
        git=subprocess.run(['git','status','--short'],capture_output=True,text=True)
        write_json(self.output/'metadata/repository_diagnosis.json',dict(processes=diagnosis.stdout,process_query_returncode=diagnosis.returncode,
            git_status=git.stdout,environment_not_modified='.venv_pattern_algorithms',started=utc()))
        paths.append(self.output/'metadata/repository_diagnosis.json')
        membership=pd.read_parquet(self.source/'reference/population_membership.parquet')
        counts=[]
        for scheme in ['three','four']:
            for item in ['profiles','cells','national_reference','pending']:
                f=pd.read_parquet(self.source/f'reference/{scheme}/{item}.parquet')
                paths.append(self.table(f'reference/{scheme}/{item}.parquet',f))
            full=pd.read_parquet(self.output/f'reference/{scheme}/profiles.parquet')
            require(len(full)==4954 and full.row_id.is_unique and not full.duplicated(KEYS).any(),'Universo perfil incorrecto.')
            require(full[KEYS].map(lambda x:isinstance(x,str)).all().all(),'Claves no textuales.')
            require(full.LN.eq(full.SV+full.NV+full.NS).all(),'Identidad nominal inválida.')
            p=len(BANDS[scheme]);national=pd.read_parquet(self.output/f'reference/{scheme}/national_reference.parquet')
            for j,band in enumerate(BANDS[scheme]):
                sums=full.groupby('SEXO')[[f'{m}_{j}' for m in ['LN','SV','NV','NS','source_row_count']]].sum()
                for sex in ['0','1']:
                    n=national[(national.age_band==band)&(national.SEXO==sex)].iloc[0]
                    for m in ['LN','SV','NV','NS','source_row_count']:require(int(sums.loc[sex,f'{m}_{j}'])==int(n[m]),'Referencia no concilia.')
                    require(np.isclose(n.national_rate,n.SV/(n.SV+n.NV),rtol=0,atol=1e-14),'Tasa nacional incorrecta.')
                require(np.allclose(full[f'rate_{j}']-full[f'national_rate_{j}'],full[f'delta_{j}'],equal_nan=True),'Diferencias inconsistentes.')
                require((full[f'rate_{j}'].isna()==full[f'specified_count_{j}'].eq(0)).all(),'NULL incorrecto.')
            mask=full.is_eligible if scheme=='three' else full.row_id.isin(membership.loc[membership.common_viable,'row_id'])
            contexts=[(scheme+'_natural',full[full.is_eligible].copy())]
            if scheme=='three': contexts.append(('three_common',full[full.row_id.isin(membership.loc[membership.common_viable,'row_id'])].copy()))
            for context,f in contexts:
                f=f.reset_index(drop=True);require(f.is_eligible.all(),'Comunes sin soporte.')
                require(len(f)==(4648 if context=='three_natural' else 4571),'Población distinta.')
                expected=98153652 if context=='three_natural' else 98119426
                require(int(f.LN.sum())==expected,'LN distinto.')
                paths.append(self.table(f'matrices/{context}/metadata.parquet',f))
                counts.append(dict(context=context,profiles=len(f),municipalities=f.groupby(MUNICIPAL_KEYS).ngroups,
                    LN=int(f.LN.sum()),nominal_fraction=float(f.LN.sum()/NATIONAL_LN),high_ns=int(f.has_high_ns_coordinate.sum()),
                    few_sections=int((f.min_section_count<5).sum()),sex_men=int((f.SEXO=='0').sum()),sex_women=int((f.SEXO=='1').sum())))
        broad=pd.read_parquet(self.source/'reference/complementary_and_full_broad.parquet')
        require(len(broad)==17735 and broad.LN.sum()==NATIONAL_LN and broad.sex_2_nominal_count.sum()==105,'Referencia complementaria alterada.')
        paths.append(self.table('reference/complementary_and_full_broad.parquet',broad))
        paths.append(self.table('metadata/coverage.csv',pd.DataFrame(counts)))
        rules=pd.read_parquet(self.root/'data/processed/profile_candidates_review/reference/segments_2024.parquet')
        paths.append(self.table('reference/rule_segments.parquet',rules))
        members=pd.read_parquet(self.root/'data/processed/demographic_representation_comparison/resampling/municipality_membership.parquet')
        paths.append(self.table('reference/municipal_subsamples.parquet',members))
        write_json(self.output/'metadata/feature_contract.json',dict(config=CONFIG,bands=BANDS,unit='municipality_sex',
            contexts=['three_natural','three_common','four_natural'],aliases={'four_common':'four_natural'},
            coefficient_semantics='combinaciones convexas de perfiles agregados; no probabilidades individuales',
            missing='NULL preservados en referencias y pendientes; ningún entrenamiento incompleto',
            national_reference='fija; todos los conteos antes de soporte',geometries=['AA1','AA2'],
            selected_variables='diferencias de participación únicamente; sin edad media/códigos/conteos como distancias',sources=SOURCES))
        paths.append(self.output/'metadata/feature_contract.json')
        self.checkpoint('a',paths,started,dict(synthetic='passed',contexts=counts,protected_files=len(self.state['protected_hashes'])))

    def stage_b(self):
        started=time.monotonic();paths=[];audit=[];blocks=[]
        for context in ['three_natural','three_common','four_natural']:
            f=self.frame(context);p=3 if context.startswith('three') else 4
            d=f[[f'delta_{j}' for j in range(p)]].to_numpy(float)
            for geometry in ['AA1','AA2']:
                s=fit_scaler(d,geometry,f.row_id);x=transform(d,s)
                require(np.allclose(inverse(x,s),d,atol=1e-12),'Inversión incorrecta.')
                require(np.linalg.matrix_rank(x)==p,'Coordenadas redundantes.')
                level=np.var(d.mean(1))*p/np.var(d,axis=0).sum()
                if geometry=='AA2':require(np.isclose(x[:,0].var(),.5) and np.isclose(x[:,1:].var(axis=0).sum(),.5),'Bloques no equilibrados.')
                matrix=pd.DataFrame(x,columns=[f'feature_{j}' for j in range(p)]);matrix.insert(0,'row_id',f.row_id)
                paths.append(self.table(f'matrices/{context}/{geometry}/features.parquet',matrix))
                sp=self.output/f'matrices/{context}/{geometry}/scaler.json';write_json(sp,s);paths.append(sp)
                if context=='three_natural':
                    old='r1' if geometry=='AA1' else 'r3'
                    previous=pd.read_parquet(self.root/f'data/processed/participation_pattern_review/features/{old}.parquet')
                    require(np.allclose(x,previous.drop(columns='row_id').to_numpy(),atol=1e-12),'Geometría no reproduce R1/R3.')
                blocks.append(dict(context=context,geometry=geometry,dimensions=p,rank=int(np.linalg.matrix_rank(x)),
                    level_fraction_original=float(level),level_fraction_geometry=float(level if geometry=='AA1' else .5),
                    shape_fraction_geometry=float(1-level if geometry=='AA1' else .5)))
                radial=np.linalg.norm(x-x.mean(0),axis=1);tail=np.argsort(-radial,kind='stable')[:int(np.ceil(len(x)*CONFIG['extreme_fraction']))]
                detail=f[['row_id',*KEYS,'LN','specified_count','unspecified_rate','has_high_ns_coordinate','min_section_count','min_specified_count']].copy()
                detail['radial_distance']=radial;detail['extreme_tail']=False;detail.loc[tail,'extreme_tail']=True
                detail['quality_excluded']=detail.has_high_ns_coordinate|(detail.min_section_count<5)
                paths.append(self.table(f'matrices/{context}/{geometry}/quality.parquet',detail))
                audit.append(dict(context=context,geometry=geometry,extremes=len(tail),tail_ln=int(f.loc[tail,'LN'].sum()),
                    quality_excluded=int(detail.quality_excluded.sum()),quality_ln=int(f.loc[detail.quality_excluded,'LN'].sum())))
        paths.append(self.table('metadata/block_geometry.csv',pd.DataFrame(blocks)))
        paths.append(self.table('metadata/pre_fit_audit.csv',pd.DataFrame(audit)))
        self.checkpoint('b',paths,started,dict(matrices=6,dimensions=[3,4],no_five_band_training=True))

    def fit(self,model_id,frame,geometry,k,seed,train_mask=None,scaler=None):
        p=3 if 'delta_3' not in frame else 4
        d=frame[[f'delta_{j}' for j in range(p)]].to_numpy(float)
        mask=np.ones(len(frame),bool) if train_mask is None else np.asarray(train_mask,bool)
        require(mask.sum()>k and np.isfinite(d).all(),'Entrenamiento insuficiente/no finito.')
        s=fit_scaler(d[mask],geometry,frame.loc[mask,'row_id']) if scaler is None else scaler
        x=transform(d,s);train=x[mask]
        parameters=dict(config=CONFIG,geometry=geometry,k=k,seed=seed,scaler=s,
            training_row_ids_sha256=hashlib.sha256('\n'.join(frame.loc[mask,'row_id']).encode()).hexdigest())
        def callback():
            print(f'Ajuste {model_id}: {len(train)} perfiles de entrenamiento',flush=True)
            m=AA(n_archetypes=int(k),n_init=1,max_iter=CONFIG['max_iter'],tol=CONFIG['tol'],algorithm_init='random',random_state=int(seed)).fit(train)
            alpha=m.transform(x);beta=m.betas_;z=m.archetypes_
            checks=validate_convex(alpha,beta,z,train,x)
            ar=inverse(z,s);raw=inverse(alpha@z,s)
            require(np.allclose(ar,beta@d[mask],atol=1e-9),'Inversión fuera de envolvente original.')
            require(np.allclose(raw,alpha@ar,atol=1e-9),'Reconstrucción afín inconsistente.')
            metrics=errors_summary(train,alpha[mask]@z,d[mask],raw[mask],train.mean(0))
            arrays=dict(alpha=alpha,beta=beta,archetypes=z,archetypes_original=ar,reconstruction=alpha@z,
                reconstruction_original=raw,training_alpha=m.alphas_,training_mask=mask,values=x,
                archetypes_absolute=beta@frame.loc[mask,[f'rate_{j}' for j in range(p)]].to_numpy(float),
                archetypes_peer_reference=beta@frame.loc[mask,[f'national_rate_{j}' for j in range(p)]].to_numpy(float))
            detail=dict(model_id=model_id,k=k,seed=seed,geometry=geometry,scaler=s,
                iterations=int(m.n_iter_)+1,stopped_before_limit=bool(m.n_iter_+1<CONFIG['max_iter']),
                convergence_status='inferred_library_stop' if m.n_iter_+1<CONFIG['max_iter'] else 'iteration_budget',
                legacy_rss_norm=float(m.rss_),training_alpha_sse=float(np.sum((train-m.alphas_@z)**2)),
                **metrics,**checks,affine_rank=int(np.linalg.matrix_rank(z[1:]-z[0])),
                coefficients_uniquely_identifiable_not_guaranteed=True,
                affine_dependence=bool(np.linalg.matrix_rank(z[1:]-z[0])<k-1))
            return m,arrays,detail
        return self.bundle(model_id,x,parameters,callback)

    def stage_c(self):
        started=time.monotonic();records=[];ids=[];failures=[]
        for context in ['three_natural','three_common','four_natural']:
            f=self.frame(context)
            for geometry,k,seed in itertools.product(['AA1','AA2'],CONFIG['ks'],SEEDS):
                model_id=f'main/{context}/{geometry}/k{k}/seed{seed}'
                try:
                    _,a,detail=self.fit(model_id,f,geometry,k,seed,scaler=self.scaler(context,geometry))
                    records.append(dict(context=context,**detail));ids.append(model_id)
                    print(f'AA {context} {geometry} K{k} seed{seed}: RMSE={detail["raw_rmse_pp"]:.3f} pp; iter={detail["iterations"]}',flush=True)
                except Exception as exc:
                    issue=dict(model_id=model_id,error=repr(exc),traceback=traceback.format_exc());failures.append(issue)
                    write_json(self.output/f'failures/{model_id.replace("/","_")}.json',issue)
                    print('Configuración fallida, se conserva el resto: '+model_id,flush=True)
        require(len(records)>0,'Ningún ajuste válido.')
        metrics=pd.DataFrame(records);metrics=metrics.drop(columns=['scaler'])
        paths=[self.table('metadata/model_metrics.parquet',metrics),self.table('metadata/model_metrics.csv',metrics)]
        write_json(self.output/'metadata/model_failures.json',failures);paths.append(self.output/'metadata/model_failures.json')
        self.checkpoint('c',paths+self.bundle_paths(ids),started,dict(valid=len(ids),failed=len(failures)))

    def best(self):
        metrics=pd.read_parquet(self.output/'metadata/model_metrics.parquet')
        return metrics.loc[metrics.groupby(['context','geometry','k']).sse.idxmin()].sort_values(['context','geometry','k']).reset_index(drop=True)

    def stage_d(self):
        started=time.monotonic();paths=[];mixrows=[];influence=[];arows=[];stability=[];errors=[];km=[]
        best=self.best();paths.append(self.table('metadata/best_models.csv',best))
        all_metrics=pd.read_parquet(self.output/'metadata/model_metrics.parquet')
        for _,rec in best.iterrows():
            f=self.frame(rec.context);a=self.load_arrays(rec.model_id);p=a['archetypes_original'].shape[1]
            alpha=a['alpha'];z=a['archetypes_original'];d=f[[f'delta_{j}' for j in range(p)]].to_numpy(float)
            mixture=mixture_statistics(alpha);mixture.insert(0,'row_id',f.row_id)
            mixture['reconstruction_rmse_pp']=np.sqrt(np.mean((d-a['reconstruction_original'])**2,1))*100
            for j in range(rec.k):mixture[f'alpha_{j}']=alpha[:,j]
            paths.append(self.table(f'diagnostics/{rec.context}/{rec.geometry}/k{rec.k}/mixtures.parquet',mixture))
            full=pd.read_parquet(self.output/f'reference/{"three" if p==3 else "four"}/profiles.parquet')
            pending=full[['row_id',*KEYS,'is_eligible','pending_reason']].merge(mixture,on='row_id',how='left',validate='one_to_one')
            pending['in_fit']=pending.row_id.isin(f.row_id)
            paths.append(self.table(f'diagnostics/{rec.context}/{rec.geometry}/k{rec.k}/all_observations.parquet',pending))
            mixrows.append(dict(context=rec.context,geometry=rec.geometry,k=rec.k,model_id=rec.model_id,
                mixed_fraction=float((~mixture.dominated).mean()),entropy_mean=float(mixture.normalized_entropy.mean()),
                multiple_substantial_fraction=float((mixture.substantial_coefficients>=2).mean()),
                max_coefficient_median=float(mixture.max_coefficient.median())))
            quality=pd.read_parquet(self.output/f'matrices/{rec.context}/{rec.geometry}/quality.parquet')
            for j in range(rec.k):
                weights=a['beta'][j];top=np.argsort(-weights)[:10]
                for rank,index in enumerate(top):
                    influence.append(dict(context=rec.context,geometry=rec.geometry,k=rec.k,archetype=j,rank=rank+1,
                        row_id=f.row_id.iloc[index],weight=float(weights[index]),LN=int(f.LN.iloc[index]),
                        max_ns=float(f[[f'unspecified_rate_{v}' for v in range(p)]].iloc[index].max()),
                        min_sections=int(f.min_section_count.iloc[index]),min_specified=int(f.min_specified_count.iloc[index]),
                        radial_extreme=bool(quality.extreme_tail.iloc[index]),
                        concentration_equivalent=float(1/np.sum(weights**2)),top10_share=float(weights[top].sum())))
                for b in range(p):
                    arows.append(dict(context=rec.context,geometry=rec.geometry,k=rec.k,archetype=j,
                        age_band=BANDS['three' if p==3 else 'four'][b],delta=float(z[j,b]),
                        level=float(z[j].mean()),shape=float(z[j,b]-z[j].mean()),
                        absolute_rate_mixture=float(a['archetypes_absolute'][j,b]),
                        peer_rate_mixture=float(a['archetypes_peer_reference'][j,b])))
            for grouping,column in [('sex','SEXO'),('state','EDOCVE'),('ns','has_high_ns_coordinate')]:
                for group,indices in f.groupby(column).groups.items():
                    ind=np.array(list(indices));err=mixture.reconstruction_rmse_pp.iloc[ind].to_numpy()
                    errors.append(dict(context=rec.context,geometry=rec.geometry,k=rec.k,grouping=grouping,group=str(group),n=len(ind),
                        LN=int(f.LN.iloc[ind].sum()),rmse_pp=float(np.sqrt(np.mean(err**2))),median_pp=float(np.median(err)),max_pp=float(err.max())))
            sizes=pd.qcut(f.LN,4,labels=False,duplicates='drop')
            for group in sorted(sizes.unique()):
                ind=np.flatnonzero(sizes==group);err=mixture.reconstruction_rmse_pp.iloc[ind].to_numpy()
                errors.append(dict(context=rec.context,geometry=rec.geometry,k=rec.k,grouping='nominal_quartile',group=str(group),n=len(ind),
                    LN=int(f.LN.iloc[ind].sum()),rmse_pp=float(np.sqrt(np.mean(err**2))),median_pp=float(np.median(err)),max_pp=float(err.max())))
            for j in range(p):
                err=(d[:,j]-a['reconstruction_original'][:,j])*100
                errors.append(dict(context=rec.context,geometry=rec.geometry,k=rec.k,grouping='age_band',group=BANDS['three' if p==3 else 'four'][j],
                    n=len(d),LN=int(f[f'LN_{j}'].sum()),rmse_pp=float(np.sqrt(np.mean(err**2))),median_pp=float(np.median(abs(err))),max_pp=float(abs(err).max())))
            relations=[]
            for column in ['LN','specified_count','unspecified_rate','min_specified_count','min_section_count']:
                relations.append(dict(variable=column,spearman_error=float(mixture.reconstruction_rmse_pp.corr(f[column],method='spearman'))))
            paths.append(self.table(f'diagnostics/{rec.context}/{rec.geometry}/k{rec.k}/error_correlations.csv',pd.DataFrame(relations)))
            candidates=all_metrics[(all_metrics.context==rec.context)&(all_metrics.geometry==rec.geometry)&(all_metrics.k==rec.k)]
            for _,alt in candidates.iterrows():
                b=self.load_arrays(alt.model_id);order,dist=aligned(z,b['archetypes_original'])
                stability.append(dict(context=rec.context,geometry=rec.geometry,k=rec.k,seed=int(alt.seed),
                    reference_seed=int(rec.seed),curve_mean_distance_pp=float(dist.mean()*100),curve_max_distance_pp=float(dist.max()*100),
                    coefficient_mean_l1=float(np.abs(alpha-b['alpha'][:,order]).sum(1).mean()),
                    reconstruction_difference_pp=float(np.sqrt(np.mean((a['reconstruction_original']-b['reconstruction_original'])**2))*100)))
            if rec.context=='three_natural':
                old='r1' if rec.geometry=='AA1' else 'r3'
                folder=self.root/f'data/processed/participation_pattern_review/models/{old}/k2/seed17'
                with np.load(folder/'fit.npz') as saved:
                    prediction=saved['centers'][saved['labels']]
                x=self.values(rec.context,rec.geometry);s=self.scaler(rec.context,rec.geometry)
                e=errors_summary(x,prediction,d,inverse(prediction,s),x.mean(0))
                km.append(dict(context=rec.context,geometry=rec.geometry,aa_k=int(rec.k),aa_rmse_pp=float(rec.raw_rmse_pp),
                    kmeans_k=2,kmeans_rmse_pp=e['raw_rmse_pp'],kmeans_normalized_rmse=e['normalized_rmse'],
                    previous_model=str(folder/'fit.npz'),new_fit=False))
        for name,data in [('mixture_summary',mixrows),('archetype_influence',influence),('archetypes_original',arows),
            ('seed_stability',stability),('grouped_errors',errors),('kmeans_descriptive_control',km)]:
            paths.append(self.table(f'metadata/{name}.csv',pd.DataFrame(data)))
        # Tres configuraciones: controlar complejidad K2/K3 y bandas en AA2 común.
        # AA1 conserva ajustes y diagnóstico de semillas, sin atribuirle validación OOB.
        selection=[]
        for context,geometry,target_k in [('three_common','AA2',2),('three_common','AA2',3),('four_natural','AA2',3)]:
            candidates=best[(best.context==context)&(best.geometry==geometry)&best.k.isin([2,3,4])].copy()
            seeds=pd.DataFrame(stability);seeds=seeds[(seeds.context==context)&(seeds.geometry==geometry)]
            maximum=seeds.groupby('k').curve_max_distance_pp.max()
            candidates['seed_max_curve_pp']=candidates.k.map(maximum)
            # Presupuestar K=3: prueba explícita de mezcla y curvatura, no ganador.
            chosen=candidates[candidates.k==target_k].iloc[0] if (candidates.k==target_k).any() else candidates.iloc[0]
            selection.append(dict(context=context,geometry=geometry,k=int(chosen.k),model_id=chosen.model_id,
                seed=int(chosen.seed),reason='AA2 equilibra nivel/forma; K2/K3 controlan complejidad y K3 tres/cuatro compara bandas sobre población común. No es selección definitiva.'))
        write_json(self.output/'metadata/validation_configurations.json',selection);paths.append(self.output/'metadata/validation_configurations.json')
        self.checkpoint('d',paths,started,dict(best_models=len(best),validation_configurations=selection))

    def stage_e(self):
        started=time.monotonic();paths=[];ids=[];sensitivity=[];resampling=[];coverage=[];comparisons=[];rule_rows=[];composition=[]
        selections=json.loads((self.output/'metadata/validation_configurations.json').read_text())
        members=pd.read_parquet(self.output/'reference/municipal_subsamples.parquet')
        for selected in selections:
            context,geometry,k=selected['context'],selected['geometry'],selected['k']
            f=self.frame(context);s=self.scaler(context,geometry);ref=self.load_arrays(selected['model_id']);zref=ref['archetypes_original']
            quality=pd.read_parquet(self.output/f'matrices/{context}/{geometry}/quality.parquet')
            for scenario in ['R0','R1','R2']:
                mask=np.ones(len(f),bool) if scenario=='R0' else (~quality.extreme_tail if scenario=='R1' else ~quality.quality_excluded).to_numpy()
                seeds=SEEDS if scenario!='R0' else [selected['seed']]
                for seed in seeds:
                    mid=selected['model_id'] if scenario=='R0' else f'sensitivity/{context}/{geometry}/{scenario}/k{k}/seed{seed}'
                    if scenario=='R0':arr=ref;detail=json.loads((self.output/'models'/mid/'details.json').read_text())
                    else:_,arr,detail=self.fit(mid,f,geometry,k,seed,train_mask=mask,scaler=s);ids.append(mid)
                    d=f[[f'delta_{j}' for j in range(s['p'])]].to_numpy(float)
                    x=transform(d,s);er=errors_summary(x,arr['reconstruction'],d,arr['reconstruction_original'],x[mask].mean(0))
                    order,dist=aligned(zref,arr['archetypes_original'])
                    sensitivity.append(dict(context=context,geometry=geometry,k=k,scenario=scenario,seed=seed,model_id=mid,
                        n_train=int(mask.sum()),municipalities=f[mask].groupby(MUNICIPAL_KEYS).ngroups,LN_train=int(f.loc[mask,'LN'].sum()),
                        nominal_fraction=float(f.loc[mask,'LN'].sum()/NATIONAL_LN),evaluation_n=len(f),evaluation_rmse_pp=er['raw_rmse_pp'],
                        max_curve_shift_pp=float(dist.max()*100),mean_curve_shift_pp=float(dist.mean()*100),
                        alpha_l1=float(np.abs(ref['alpha']-arr['alpha'][:,order]).sum(1).mean()),
                        reconstruction_shift_pp=float(np.sqrt(np.mean((ref['reconstruction_original']-arr['reconstruction_original'])**2))*100)))
                    flags=f[['row_id',*KEYS]].copy();flags['is_training']=mask;flags['is_evaluation']=True
                    paths.append(self.table(f'sensitivity/{context}/{geometry}/{scenario}/seed{seed}/membership.parquet',flags))
            attached=f.merge(members,on=MUNICIPAL_KEYS,how='left',validate='many_to_one',sort=False)
            require(len(attached)==len(f) and attached.row_id.equals(f.row_id),'Remuestreo expandió/reordenó perfiles.')
            for sample in range(CONFIG['subsamples']):
                flag=f'sample_{sample:03d}';mask=attached[flag].to_numpy(bool)
                mid=f'resampling/{context}/{geometry}/k{k}/sample{sample:03d}'
                _,arr,detail=self.fit(mid,f,geometry,k,17,train_mask=mask);ids.append(mid)
                d=f[[f'delta_{j}' for j in range(s['p'])]].to_numpy(float)
                x=arr['values'];er=errors_summary(x[~mask],arr['reconstruction'][~mask],d[~mask],arr['reconstruction_original'][~mask],x[mask].mean(0))
                order,dist=aligned(zref,arr['archetypes_original'])
                resampling.append(dict(context=context,geometry=geometry,k=k,sample=sample,model_id=mid,**er,
                    max_curve_shift_pp=float(dist.max()*100),mean_curve_shift_pp=float(dist.mean()*100),
                    alpha_oob_l1=float(np.abs(ref['alpha'][~mask]-arr['alpha'][~mask][:,order]).sum(1).mean()),
                    train_raw_rmse_pp=detail['raw_rmse_pp'],stopped_before_limit=detail['stopped_before_limit']))
                coverage.append(dict(context=context,sample=sample,municipalities_drawn=int(members[flag].sum()),
                    municipalities_train=f[mask].groupby(MUNICIPAL_KEYS).ngroups,municipalities_oob=f[~mask].groupby(MUNICIPAL_KEYS).ngroups,
                    profiles_train=int(mask.sum()),profiles_oob=int((~mask).sum()),LN_train=int(f.loc[mask,'LN'].sum()),
                    LN_oob=int(f.loc[~mask,'LN'].sum()),fraction_eligible_LN=float(f.loc[mask,'LN'].sum()/f.LN.sum()),
                    national_fraction=float(f.loc[mask,'LN'].sum()/NATIONAL_LN)))
                mixture=mixture_statistics(arr['alpha']);mixture.insert(0,'row_id',f.row_id);mixture['is_training']=mask;mixture['is_oob']=~mask
                for j in range(k):mixture[f'alpha_aligned_{j}']=arr['alpha'][:,order[j]]
                paths.append(self.table(f'resampling/{context}/{geometry}/k{k}/sample{sample:03d}/mixtures.parquet',mixture))
            # Contexto por reglas: una firma de tres etiquetas por municipio/sexo.
            if context=='three_common' and k==3:
                rules=pd.read_parquet(self.output/'reference/rule_segments.parquet')
                core=rules[rules.age_band.isin(BANDS['three'])&rules.SEXO.isin(['0','1'])]
                pivot=core.pivot(index=KEYS,columns='age_band',values='candidate_id').reset_index()
                joined=f.merge(pivot,on=KEYS,how='left',validate='one_to_one',sort=False)
                require(joined.row_id.equals(f.row_id) and joined[BANDS['three']].notna().all().all(),'Reglas sin enlace uno a uno.')
                joined['rule_signature']=joined[BANDS['three']].astype(str).agg(' / '.join,axis=1)
                mix=mixture_statistics(ref['alpha']);joined=pd.concat([joined.reset_index(drop=True),mix],axis=1)
                for j in range(k):joined[f'alpha_{j}']=ref['alpha'][:,j]
                paths.append(self.table('comparisons/rule_signatures_and_mixtures.parquet',joined))
                for signature,g in joined.groupby('rule_signature'):
                    co=g[[f'alpha_{j}' for j in range(k)]].to_numpy()
                    rule_rows.append(dict(signature=signature,profiles=len(g),municipalities=g.groupby(MUNICIPAL_KEYS).ngroups,
                        mean_max_coefficient=float(g.max_coefficient.mean()),mean_entropy=float(g.normalized_entropy.mean()),
                        coefficient_sd_max=float(co.std(0).max()),coefficient_range_max=float(np.ptp(co,axis=0).max())))
            for sex,g in f.groupby('SEXO'):
                ind=g.index.to_numpy();row=dict(context=context,geometry=geometry,k=k,grouping='sex',group=sex,profiles=len(g),LN=int(g.LN.sum()))
                for j in range(k):row[f'alpha_{j}']=float(ref['alpha'][ind,j].mean())
                composition.append(row)
            # Media de ambos sexos por municipio: no se confunde con personas.
            for keys,indices in f.groupby(MUNICIPAL_KEYS).groups.items():
                ind=np.array(list(indices));row=dict(context=context,geometry=geometry,k=k,grouping='municipality',group='/'.join(keys),profiles=len(ind),LN=int(f.loc[ind,'LN'].sum()))
                for j in range(k):row[f'alpha_{j}']=float(ref['alpha'][ind,j].mean())
                composition.append(row)
        # Comparación de bandas únicamente sobre las mismas filas; sólo 60–100 es coordenada idéntica.
        best=self.best()
        for geometry,k in itertools.product(['AA1','AA2'],CONFIG['ks']):
            r=best[(best.context=='three_common')&(best.geometry==geometry)&(best.k==k)].iloc[0]
            t=best[(best.context=='four_natural')&(best.geometry==geometry)&(best.k==k)].iloc[0]
            a,b=self.load_arrays(r.model_id),self.load_arrays(t.model_id)
            f,g=self.frame('three_common'),self.frame('four_natural');require(f.row_id.equals(g.row_id),'Comunes desalineados.')
            require(np.allclose(f.delta_2,g.delta_3),'Coordenada mayor no comparable.')
            comparisons.append(dict(geometry=geometry,k=k,n=len(f),
                three_older_rmse_pp=float(np.sqrt(np.mean((f.delta_2-a['reconstruction_original'][:,2])**2))*100),
                four_older_rmse_pp=float(np.sqrt(np.mean((g.delta_3-b['reconstruction_original'][:,3])**2))*100),
                three_own_normalized_rmse=float(r.normalized_rmse),four_own_normalized_rmse=float(t.normalized_rmse),
                common_older_reconstruction_difference_pp=float(np.sqrt(np.mean((a['reconstruction_original'][:,2]-b['reconstruction_original'][:,3])**2))*100)))
        for name,data in [('sensitivity_metrics',sensitivity),('municipal_resampling',resampling),('resampling_coverage',coverage),
            ('band_comparison',comparisons),('rule_signature_summary',rule_rows),('composition',composition)]:
            paths.append(self.table(f'metadata/{name}.csv',pd.DataFrame(data)))
        self.checkpoint('e',paths+self.bundle_paths(ids),started,dict(sensitivity_fits=18,resampling_fits=len(resampling),configurations=selections))

    def run(self,stop_after='f'):
        for stage in ['a','b','c','d','e','f']:
            if self.valid_stage(stage):print('Checkpoint verificado: '+stage,flush=True)
            else:getattr(self,'stage_'+stage)()
            if stage==stop_after:break
        if stop_after=='f':self.finalize()

    def refresh_render(self):
        """Revisa sólo esta entrega; conserva modelos y archiva el informe propio."""
        for stage in 'abcde':require(self.valid_stage(stage),'No se puede revisar sin etapas A–E válidas.')
        archive=self.output/'revisions'/f'render_{time.time_ns()}'
        require(archive.resolve().is_relative_to(self.root.resolve()),'Archivo de revisión fuera del proyecto.')
        archive.mkdir(parents=True)
        for path in [self.report,self.output/'metadata/checkpoint_f.json',self.output/'metadata/run_manifest.json',self.output/'_SUCCESS']:
            require(path.resolve().is_relative_to(self.root.resolve()),'Destino de revisión fuera del proyecto.')
            if path.exists():path.replace(archive/path.name)
        write_json(archive/'revision.json',dict(reason='Revisión de documentación y trazabilidad de esta entrega; cero reajustes.',time=utc()))
        self.state['status']='running';write_json(self.state_path,self.state)

    def figure(self,name,fig,paths):
        fig.tight_layout();path=self.charts/name;save_figure(fig,path);paths.append(path)

    def plot_diagnostics(self):
        paths=[];best=self.best();summary=pd.read_csv(self.output/'metadata/mixture_summary.csv')
        f=self.frame('three_common');d=f[[f'delta_{j}' for j in range(3)]].to_numpy()
        primary=best[(best.context=='three_common')&(best.geometry=='AA2')&(best.k==3)].iloc[0]
        a=self.load_arrays(primary.model_id);z=a['archetypes_original'];alpha=a['alpha']
        colors=plt.get_cmap('tab10').colors
        fig,axes=plt.subplots(1,3,figsize=(12,3.5))
        for j,ax in enumerate(axes):
            ax.hist(d[:,j]*100,bins=50,color=colors[j],alpha=.8);ax.set(title=BANDS['three'][j],xlabel='Diferencia frente a pares (pp)',ylabel='Perfiles municipio–sexo')
        fig.suptitle('Diferencias originales, tres bandas y población común')
        self.figure('original_distributions.png',fig,paths)
        fig,axes=plt.subplots(1,2,figsize=(11,4))
        for geometry,ax in zip(['AA1','AA2'],axes):
            r=best[(best.context=='three_common')&(best.geometry==geometry)&(best.k==3)].iloc[0]
            ar=self.load_arrays(r.model_id);x=ar['values'];zz=ar['archetypes']
            ax.hexbin(x[:,0],x[:,1],gridsize=55,mincnt=1,bins='log',cmap='Blues')
            ax.scatter(zz[:,0],zz[:,1],c=colors[:3],marker='*',s=200,edgecolor='black')
            for j in range(3):ax.annotate(f'A{j}',zz[j,:2],xytext=(6,5),textcoords='offset points')
            ax.set(title=geometry+' · proyección de dos coordenadas',xlabel='Diferencia joven escalada' if geometry=='AA1' else 'Nivel escalado',ylabel='Diferencia adulta escalada' if geometry=='AA1' else 'Contraste de forma 1 escalado')
        fig.suptitle('Arquetipos en proyecciones declaradas; la dimensión restante no aparece')
        self.figure('archetype_projections.png',fig,paths)
        fig,axes=plt.subplots(1,2,figsize=(11,4))
        for context,ax in zip(['three_common','four_natural'],axes):
            r=best[(best.context==context)&(best.geometry=='AA2')&(best.k==3)].iloc[0];zz=self.load_arrays(r.model_id)['archetypes_original']
            bands=BANDS['three' if context.startswith('three') else 'four']
            for j,curve in enumerate(zz):ax.plot(bands,curve*100,marker='o',label=f'Arquetipo local {j}',color=colors[j])
            ax.axhline(0,color='grey',lw=.8);ax.set(title=context,xlabel='Intervalo candidato',ylabel='Participación relativa (pp)');ax.legend(fontsize=8)
        fig.suptitle('Curvas AA2 K=3; números locales sin identidad entre esquemas')
        self.figure('archetype_curves.png',fig,paths)
        fig,axes=plt.subplots(1,2,figsize=(11,4))
        for j in range(3):axes[0].hist(alpha[:,j],bins=30,histtype='step',label=f'Coeficiente A{j}')
        axes[0].set(xlabel='Coeficiente convexo',ylabel='Perfiles');axes[0].legend()
        mix=mixture_statistics(alpha);axes[1].hist(mix.normalized_entropy,bins=40,color=colors[2]);axes[1].set(xlabel='Entropía normalizada de mezcla',ylabel='Perfiles')
        fig.suptitle('Mezclas AA2 tres bandas K=3; no son probabilidades de votar')
        self.figure('mixture_distributions.png',fig,paths)
        fig,ax=plt.subplots(figsize=(7,6));xy=np.column_stack([alpha[:,1]+alpha[:,2]/2,np.sqrt(3)*alpha[:,2]/2])
        ax.hexbin(xy[:,0],xy[:,1],gridsize=55,mincnt=1,bins='log',cmap='viridis')
        triangle=np.array([[0,0],[1,0],[.5,np.sqrt(3)/2],[0,0]]);ax.plot(triangle[:,0],triangle[:,1],color='black')
        for j,(x,y) in enumerate(triangle[:3]):ax.text(x,y+(.03 if j==2 else -.04),f'A{j}',ha='center')
        ax.set_aspect('equal');ax.axis('off');ax.set_title('Composición ternaria válida · AA2 K=3\nCada punto es una mezcla de un perfil municipio–sexo')
        self.figure('ternary_mixtures.png',fig,paths)
        err=np.sqrt(np.mean((d-a['reconstruction_original'])**2,1))*100
        order=np.argsort(err);indices=[order[len(order)//2],order[int(.95*len(order))],order[-1]]
        fig,axes=plt.subplots(1,3,figsize=(13,4),sharey=True)
        for index,ax in zip(indices,axes):
            ax.plot(BANDS['three'],d[index]*100,'o-',label='Observado')
            ax.plot(BANDS['three'],a['reconstruction_original'][index]*100,'s--',label='Reconstruido')
            row=f.iloc[index];ax.set(title=f'{row.EDOCVE}/{row.MPIOCVE} · sexo {row.SEXO}\nRMSE {err[index]:.2f} pp',xlabel='Intervalo',ylabel='Diferencia frente a pares (pp)');ax.legend(fontsize=8)
        fig.suptitle('Observaciones reales: error mediano, p95 y máximo; no son casos inventados')
        self.figure('real_reconstructions.png',fig,paths)
        fig,axes=plt.subplots(1,3,figsize=(13,4))
        for context,ax in zip(['three_natural','three_common','four_natural'],axes):
            for geometry in ['AA1','AA2']:
                g=best[(best.context==context)&(best.geometry==geometry)]
                ax.plot(g.k,g.raw_rmse_pp,'o-',label=geometry)
            ax.set(title=context,xlabel='Número de arquetipos',ylabel='RMSE original (pp)');ax.legend()
        fig.suptitle('Reconstrucción en entrenamiento; cada panel tiene sus propios objetivos por banda')
        self.figure('reconstruction_vs_k.png',fig,paths)
        oob=pd.read_csv(self.output/'metadata/municipal_resampling.csv')
        fig,axes=plt.subplots(1,2,figsize=(12,4))
        labels=[];groups=[]
        for (context,k),g in oob.groupby(['context','k']):labels.append(f'{context}\nK={k}');groups.append(g.raw_rmse_pp.to_numpy())
        axes[0].boxplot(groups,tick_labels=labels,showmeans=True);axes[0].set(ylabel='RMSE OOB original (pp)')
        axes[1].boxplot([g.max_curve_shift_pp.to_numpy() for _,g in oob.groupby(['context','k'])],tick_labels=labels,showmeans=True)
        axes[1].set(ylabel='Mayor desplazamiento de curva alineada (pp)')
        for ax in axes:ax.tick_params(axis='x',labelsize=8)
        fig.suptitle('Diez submuestras municipales: fuera de entrenamiento y peores desplazamientos')
        self.figure('out_of_training_error.png',fig,paths)
        fig,axes=plt.subplots(1,2,figsize=(12,4))
        for (context,k),g in oob.groupby(['context','k']):
            axes[0].plot(g['sample'],g.mean_curve_shift_pp,'o-',label=f'{context} K{k}')
            axes[1].plot(g['sample'],g.alpha_oob_l1,'o-',label=f'{context} K{k}')
        axes[0].set(xlabel='Submuestra municipal',ylabel='Distancia media de curvas (pp)');axes[1].set(xlabel='Submuestra municipal',ylabel='Cambio L1 de coeficientes OOB alineados')
        axes[1].legend(fontsize=7);fig.suptitle('Estabilidad condicional con referencias nacionales fijas')
        self.figure('municipal_stability.png',fig,paths)
        sens=pd.read_csv(self.output/'metadata/sensitivity_metrics.csv')
        influence=pd.read_csv(self.output/'metadata/archetype_influence.csv')
        fig,axes=plt.subplots(1,2,figsize=(12,4))
        for (context,k),g in sens.groupby(['context','k']):
            avg=g.groupby('scenario').mean(numeric_only=True).reindex(['R0','R1','R2'])
            axes[0].plot(['R0: todos','R1: cola 1%','R2: calidad'],avg.evaluation_rmse_pp,'o-',label=f'{context} K{k}')
        axes[0].set(ylabel='RMSE sobre todos los elegibles (pp)');axes[0].legend(fontsize=7)
        infl=influence[(influence.context=='three_common')&(influence.geometry=='AA2')&(influence.k==3)&(influence['rank']==1)]
        axes[1].bar(infl.archetype,infl.weight,color=colors[:3]);axes[1].set(xlabel='Arquetipo local',ylabel='Mayor peso β de una observación')
        fig.suptitle('Sensibilidades clásicas e influencia; no es AA robusto formal')
        self.figure('extreme_influence.png',fig,paths)
        cmp=pd.read_csv(self.output/'metadata/band_comparison.csv');fig,axes=plt.subplots(1,2,figsize=(11,4))
        for geom,ax in zip(['AA1','AA2'],axes):
            g=cmp[cmp.geometry==geom]
            ax.plot(g.k,g.three_older_rmse_pp,'o-',label='Tres bandas')
            ax.plot(g.k,g.four_older_rmse_pp,'s--',label='Cuatro bandas')
            ax.set(title=geom,xlabel='K',ylabel='RMSE de la misma tasa 60–100 (pp)');ax.legend()
        fig.suptitle('Comparación válida de una coordenada idéntica sobre 4,571 perfiles comunes')
        self.figure('three_four_comparison.png',fig,paths)
        composition=pd.read_csv(self.output/'metadata/composition.csv');fig,axes=plt.subplots(1,2,figsize=(11,4))
        comp=composition[(composition.context=='three_common')&(composition.k==3)]
        sex=comp[comp.grouping=='sex'];bottom=np.zeros(len(sex))
        for j in range(3):axes[0].bar(sex['group'].astype(str),sex[f'alpha_{j}'],bottom=bottom,label=f'A{j}',color=colors[j]);bottom+=sex[f'alpha_{j}'].to_numpy()
        axes[0].set(xlabel='SEXO: 0 hombres, 1 mujeres',ylabel='Media por perfil de coeficientes');axes[0].legend()
        muni=comp[comp.grouping=='municipality']
        for j in range(3):axes[1].hist(muni[f'alpha_{j}'],histtype='step',bins=35,label=f'A{j}')
        axes[1].set(xlabel='Coeficiente medio de perfiles del municipio',ylabel='Municipios');axes[1].legend()
        fig.suptitle('Composición descriptiva: no son proporciones de votantes')
        self.figure('sex_municipality_composition.png',fig,paths)
        rules=pd.read_parquet(self.output/'comparisons/rule_signatures_and_mixtures.parquet');fig,ax=plt.subplots(figsize=(11,5))
        signatures=rules.rule_signature.value_counts().head(8).index
        means=rules.groupby('rule_signature')[[f'alpha_{j}' for j in range(3)]].mean().reindex(signatures)
        short=[label.replace('favorable','encima').replace('unencima','debajo').replace('young','joven').replace('adult','adulto').replace('older','mayor') for label in signatures]
        bottom=np.zeros(len(means))
        for j in range(3):ax.barh(np.arange(len(means)),means[f'alpha_{j}'],left=bottom,label=f'A{j}',color=colors[j]);bottom+=means[f'alpha_{j}'].to_numpy()
        ax.set_yticks(np.arange(len(means)),short,fontsize=7);ax.set(xlabel='Coeficiente medio; una fila por municipio–sexo',title='Mismas etiquetas por reglas, mezclas interiores diferentes');ax.legend()
        self.figure('rule_profile_context.png',fig,paths)
        fig,ax=plt.subplots(figsize=(11,4))
        ordered=np.argsort(np.max(alpha,axis=1));selected=ordered[np.linspace(0,len(ordered)-1,80,dtype=int)]
        bottom=np.zeros(len(selected))
        for j in range(3):ax.bar(np.arange(len(selected)),alpha[selected,j],bottom=bottom,width=1,label=f'A{j}',color=colors[j]);bottom+=alpha[selected,j]
        ax.set(xlabel='80 perfiles reales ordenados por coeficiente máximo',ylabel='Coeficiente convexo',title='Mezclas sin asignación rígida · AA2 K=3');ax.legend()
        self.figure('mixture_bars.png',fig,paths)
        # K>3: barras apropiadas, sin ternario inválido.
        high=best[(best.context=='three_common')&(best.geometry=='AA2')&(best.k==5)].iloc[0]
        aa=self.load_arrays(high.model_id)['alpha'];selected=np.argsort(aa.max(1))[np.linspace(0,len(aa)-1,80,dtype=int)]
        fig,ax=plt.subplots(figsize=(11,4));bottom=np.zeros(80)
        for j in range(5):ax.bar(np.arange(80),aa[selected,j],bottom=bottom,width=1,label=f'A{j}',color=colors[j]);bottom+=aa[selected,j]
        ax.set(xlabel='80 perfiles reales',ylabel='Coeficiente convexo',title='K=5: composiciones no necesariamente únicas en tres dimensiones');ax.legend(ncol=5)
        self.figure('higher_k_mixture_bars.png',fig,paths)
        return paths

    def stage_f(self):
        started=time.monotonic();paths=[];validated=[]
        for name in ['age_band_representation_review','participation_pattern_review','profile_candidates_review']:
            folder=self.root/'data/processed'/name;mp=folder/'metadata/run_manifest.json'
            manifest=json.loads(mp.read_text(encoding='utf8'));marker=json.loads((folder/'_SUCCESS').read_text(encoding='utf8'))
            require(manifest['status']=='validated' and marker['manifest_sha256']==file_hash(mp),'Fuente sin validación: '+name)
            for relative,digest in manifest['artifact_hashes'].items():
                require(self.state['protected_hashes'].get(str(self.root/relative))==digest,'Artefacto fuente no coincide con manifiesto: '+relative)
            validated.append(dict(source=name,manifest_sha256=file_hash(mp),validated_artifacts=len(manifest['artifact_hashes'])))
        validation_path=self.output/'metadata/validated_sources.json';write_json(validation_path,validated);paths.append(validation_path)
        clarification=self.output/'metadata/implementation_clarifications.json'
        write_json(clarification,dict(initialization='furthest_sum sólo construye N×N en su rama para muestras pequeñas; esa rama falló en el triángulo. N grande tiene otra rama. Todos los ajustes entregados utilizan random sin NxN.',
            projected_alpha='transform sobre arquetipos finales; training_alpha conserva además la salida alternante antes de reproyección',
            optimizer='biblioteca nativa sin parches; NNLS aumentado 200 y renormalizado; no robusto formal'))
        paths.append(clarification)
        alignments=[]
        selected=json.loads((self.output/'metadata/validation_configurations.json').read_text())
        lookup={(s['context'],s['geometry'],s['k']):s for s in selected}
        for filename,kind in [('municipal_resampling','resampling'),('sensitivity_metrics','sensitivity')]:
            rows=pd.read_csv(self.output/f'metadata/{filename}.csv')
            for _,row in rows.iterrows():
                original=lookup[(row.context,row.geometry,int(row.k))]
                ref=self.load_arrays(original['model_id'])['archetypes_original']
                alt=self.load_arrays(row.model_id)['archetypes_original']
                order,dist=aligned(ref,alt)
                for j,index in enumerate(order):alignments.append(dict(kind=kind,model_id=row.model_id,
                    reference_model_id=original['model_id'],reference_archetype=j,alternative_archetype=int(index),distance_pp=float(dist[j]*100)))
        paths.append(self.table('metadata/archetype_alignments.parquet',pd.DataFrame(alignments)))
        for context in ['three_natural','three_common','four_natural']:
            scheme='three' if context.startswith('three') else 'four'
            full=pd.read_parquet(self.output/f'reference/{scheme}/profiles.parquet')
            status=full[['row_id',*KEYS,'is_eligible','pending_reason','LN','SV','NV','NS','source_row_count']].copy()
            status['in_matrix']=status.row_id.isin(self.frame(context).row_id)
            status['matrix_status']=np.select([status.in_matrix,~status.is_eligible],
                ['eligible_training_population','original_support_pending'],default='outside_common_population')
            paths.append(self.table(f'matrices/{context}/observation_status.parquet',status))
        paths+=self.plot_diagnostics()
        tests=subprocess.run([sys.executable,'-m','unittest','discover','-s','analysis/scripts','-p','test_evaluate_archetypal_patterns.py'],
            cwd=self.root,capture_output=True,text=True,encoding='utf8')
        test_path=self.output/'metadata/automated_tests.json'
        write_json(test_path,dict(returncode=tests.returncode,stdout=tests.stdout,stderr=tests.stderr,run_at=utc()));paths.append(test_path)
        require(tests.returncode==0,'Fallaron pruebas automatizadas: '+tests.stderr)
        self.write_report();paths.append(self.report)
        self.checkpoint('f',paths,started,dict(charts=len(list(self.charts.glob('*.png'))),tests='passed',report=str(self.report)))

    def write_report(self):
        best=self.best();metrics=pd.read_parquet(self.output/'metadata/model_metrics.parquet')
        coverage=pd.read_csv(self.output/'metadata/coverage.csv');mix=pd.read_csv(self.output/'metadata/mixture_summary.csv')
        sensitivity=pd.read_csv(self.output/'metadata/sensitivity_metrics.csv');oob=pd.read_csv(self.output/'metadata/municipal_resampling.csv')
        seeds=pd.read_csv(self.output/'metadata/seed_stability.csv');influence=pd.read_csv(self.output/'metadata/archetype_influence.csv')
        rules=pd.read_csv(self.output/'metadata/rule_signature_summary.csv');bands=pd.read_csv(self.output/'metadata/band_comparison.csv')
        archetypes_table=pd.read_csv(self.output/'metadata/archetypes_original.csv');km=pd.read_csv(self.output/'metadata/kmeans_descriptive_control.csv')
        failures=json.loads((self.output/'metadata/model_failures.json').read_text())
        main=best[(best.context=='three_common')&(best.geometry=='AA2')&(best.k==3)].iloc[0]
        mainmix=mix[(mix.context=='three_common')&(mix.geometry=='AA2')&(mix.k==3)].iloc[0]
        curves=archetypes_table[(archetypes_table.context=='three_common')&(archetypes_table.geometry=='AA2')&(archetypes_table.k==3)].copy()
        for column in ['delta','level','shape']:curves[column+'_pp']=curves[column]*100
        summary=[]
        for (context,k),g in oob.groupby(['context','k']):
            summary.append(dict(context=context,k=k,samples=len(g),oob_rmse_median_pp=float(g.raw_rmse_pp.median()),
                oob_rmse_max_pp=float(g.raw_rmse_pp.max()),normalized_rmse_median=float(g.normalized_rmse.median()),
                curve_shift_median_pp=float(g.max_curve_shift_pp.median()),curve_shift_max_pp=float(g.max_curve_shift_pp.max()),
                alpha_l1_median=float(g.alpha_oob_l1.median()),budget_hits=int((~g.stopped_before_limit).sum())))
        summary=pd.DataFrame(summary);self.table('metadata/oob_summary.csv',summary)
        # Contraste emparejado K2/K3: mismos municipios, filas, escalas y objetivos.
        two=oob[(oob.context=='three_common')&(oob.k==2)].set_index('sample')
        three=oob[(oob.context=='three_common')&(oob.k==3)].set_index('sample')
        paired=pd.DataFrame(dict(sample=two.index,k2_rmse_pp=two.raw_rmse_pp,k3_rmse_pp=three.raw_rmse_pp,
            reduction_pp=two.raw_rmse_pp-three.raw_rmse_pp,relative_reduction=1-three.raw_rmse_pp/two.raw_rmse_pp))
        self.table('metadata/paired_complexity_oob.csv',paired)
        seed_summary=seeds.groupby(['context','geometry','k'],as_index=False).agg(
            max_seed_curve_shift_pp=('curve_max_distance_pp','max'),max_seed_alpha_l1=('coefficient_mean_l1','max'))
        selected_best=best.merge(seed_summary,on=['context','geometry','k'])
        columns=['context','geometry','k','seed','iterations','stopped_before_limit','raw_rmse_pp','normalized_rmse','affine_dependence','max_seed_curve_shift_pp']
        sens_summary=sensitivity.groupby(['context','geometry','k','scenario'],as_index=False).agg(
            train_profiles=('n_train','first'),train_LN=('LN_train','first'),evaluation_profiles=('evaluation_n','first'),
            evaluation_rmse_mean_pp=('evaluation_rmse_pp','mean'),curve_shift_max_pp=('max_curve_shift_pp','max'),alpha_l1_max=('alpha_l1','max'))
        infl=influence[(influence.context=='three_common')&(influence.geometry=='AA2')&(influence.k==3)]
        inf_top=infl[infl['rank']==1]
        main_seed=seed_summary[(seed_summary.context=='three_common')&(seed_summary.geometry=='AA2')&(seed_summary.k==3)].iloc[0]
        nonunique=int(best.affine_dependence.sum());budget=int((~metrics.stopped_before_limit).sum())
        primary_oob=summary[(summary.context=='three_common')&(summary.k==3)].iloc[0]
        primary_sensitivity=sens_summary[(sens_summary.context=='three_common')&(sens_summary.k==3)].set_index('scenario')
        reasons=[]
        for _,r in curves.groupby('archetype').first().reset_index().iterrows():
            c=curves[curves.archetype==r.archetype].set_index('age_band').loc[BANDS['three']]
            v=c.delta_pp.to_numpy();level=float(v.mean());shape=v-level
            contrast=float(v[0]-v[-1]);label='nivel relativo alto' if level>0 else 'nivel relativo bajo'
            reasons.append(f'- A{int(r.archetype)}: nivel medio {level:+.2f} pp; joven−mayor {contrast:+.2f} pp; amplitud de forma {np.ptp(shape):.2f} pp. Describe {label}; el contraste por edad se informa por separado y no supone una motivación.')
        f=self.frame('three_common');a=self.load_arrays(main.model_id)
        raw=f[[f'delta_{j}' for j in range(3)]].to_numpy()
        # Selección determinista de dos casos extremos en una misma firma de reglas.
        linked=pd.read_parquet(self.output/'comparisons/rule_signatures_and_mixtures.parquet')
        signature=rules.sort_values(['coefficient_range_max','profiles'],ascending=False).iloc[0].signature
        group=linked[linked.rule_signature==signature]
        col=max([f'alpha_{j}' for j in range(3)],key=lambda c:group[c].max()-group[c].min())
        examples=group.loc[[group[col].idxmin(),group[col].idxmax()],['row_id',*KEYS,'rule_signature','alpha_0','alpha_1','alpha_2']]
        self.table('comparisons/same_rules_different_mixtures.csv',examples)
        chart_reference=lambda name: f'![{name.replace("_"," ")}]({os.path.relpath(self.charts/(name+".png"),self.report.parent).replace(chr(92),"/")})'
        report=f'''# Arquetipos continuos de participación electoral · 2024

**AA pudo ejecutarse y validar sus dos restricciones convexas. Aporta una representación continua complementaria, pero no demuestra nuevos tipos naturales ni justifica adoptar perfiles definitivos.** En AA2 tres-común, K3 reduce el RMSE OOB mediano de {summary[(summary.context=='three_common')&(summary.k==2)].iloc[0].oob_rmse_median_pp:.2f} a {primary_oob.oob_rmse_median_pp:.2f} pp frente a K2, pero una curva cambia hasta {primary_oob.curve_shift_max_pp:.2f} pp entre submuestras. La reconstrucción mejora con K; estabilidad de extremos, optimización local e identificación de mezclas limitan esa mejora. No se fuerza seis arquetipos ni se sustituyen las seis fichas por reglas.

## Fuentes, unidad y cobertura

Se leyeron los cinco informes solicitados: participation_pattern_review, pattern_algorithm_comparison, age_band_representation_review, multidimensional_profile_review y profile_candidates_review. Se reutilizan únicamente agregados validados de 2024, conteos y referencias anteriores; no se reprocesaron CSV ni experimentos históricos. Unidad: **municipio × sexo**, con tasas por edad como coordenadas. No son personas ni filas municipio/edad/sexo independientes. Claves, SEXO, TIPOSEC y edad media no entran en la distancia.

{table_text(coverage)}

Se conservan 4,954 perfiles H/M disponibles en cada referencia, sus pendientes y conteos por banda. La referencia broad completa conserva 17,735 segmentos, 9,773,730 filas fuente, LN=98,330,348, SV=54,899,228, NV=37,105,466 y NS=6,325,654; SEXO=2 conserva 105 filas/LN y las edades 101+ permanecen complementarias. Los perfiles tres/cuatro son vistas alternativas y sus conteos no se suman. Las edades exactas siguen en su Parquet previo, trazable por los manifiestos protegidos.

El principal mantiene LN≥100, SV+NV≥100 y filas fuente≥5 **en cada banda**. Filas fuente son celdas originales, no secciones distintas o personas independientes. NS no significa abstención. Las tasas NULL no se imputan; los perfiles incompletos no reciben coeficientes de entrenamiento. La elegibilidad no se amplió para favorecer AA. Tres natural reúne 2,341/2,477 municipios; cuatro y la comparación común, 2,296. Cobertura nominal alta no implica representatividad territorial completa.

## Fundamento, geometría y contrato

AA aproxima X≈αZ, Z=βX, con α y β no negativas y cada fila sumando uno. Los arquetipos son combinaciones de observaciones de entrenamiento y cada perfil es una mezcla de arquetipos. El problema alternante es no convexo: distintos arranques pueden producir soluciones distintas. El aumento de capacidad con K no implica nuevos grupos electorales. [Cutler y Breiman (1994)]({SOURCES['cutler_breiman_1994']}).

Para cada banda y sexo se fija r=ΣSV/Σ(SV+NV) con todos los conteos comparables **antes de soporte**. d_j=SV_j/(SV_j+NV_j)−r_j. Se concilian referencias por sexo/banda, identidad LN=SV+NV+NS y nulos. No se promedian tasas municipales para construir r. Se preservan tasa absoluta y referencia por perfil.

m=media simple de d; Q es una base ortonormal fija de dimensión p×(p−1), perpendicular a unos; q=dQ y d=m1+qQᵀ. ||d_i−d_l||²=p(m_i−m_l)²+||q_i−q_l||². No se añade un bloque redundante ni se normaliza amplitud por observación.

- **AA1:** (d−media de entrenamiento)/RMS común del vector centrado. Preserva todas las distancias euclídeas relativas entre bandas. El nivel explica aproximadamente 82 % de la variación original en tres bandas; no es una atribución causal.
- **AA2:** [(m−μ_m)/σ_m, (q−μ_q)/RMS_q]/√2. El bloque de nivel y el conjunto de forma aportan exactamente 50 % de la varianza de entrenamiento cada uno, según R3 previo. Es una decisión explícita de geometría, no información adicional. Ambas transformaciones son invertibles y no codifican edad media.

Se verifica rango p, reconstrucción exacta tras invertir y conservación de combinaciones convexas en la escala original. Los parámetros se ajustan sólo a la población declarada. Tres natural reproduce numéricamente R1/R3 anteriores. No se selecciona geometría comparando errores en escalas diferentes.

{chart_reference('original_distributions')}
{chart_reference('archetype_projections')}

## Entorno real, biblioteca y pruebas previas

Python 3.13 AMD64; `archetypes==0.6.2`, `scikit-learn==1.5.2`, NumPy {np.__version__}. Se creó **.venv_archetypal_patterns**: sus paquetes propios no alteran .venv_pattern_algorithms; un archivo .pth reutiliza sólo en lectura las demás bibliotecas previas. El lock de dependencias y los reportes pip permiten reconstruirlo; esa ruta compartida debe conservarse o reemplazarse por las versiones fijadas al trasladar el proyecto.

La documentación y rama principal consultadas describen una versión más reciente (0.12.2), pero el resolvedor binario accesible ofreció 0.6.2. No se afirma incompatibilidad universal de Python. La primera prueba falló con sklearn 1.9.1 (`_validate_data` retirado); se resolvió instalando 1.5.2 sólo en el entorno nuevo. `pip check` pasa. [Documentación oficial]({SOURCES['official_documentation']}), [repositorio]({SOURCES['official_repository']}).

La API instalada proporciona `fit`, `transform`, `archetypes_`, **`alphas_` y `betas_`**; no existen `coefficients_`, `arch_coefficients_` o `converged_`. No se inventan estos atributos. El inicializador `random` es nativo y reproducible. La prueba sintética activa una rama de `furthest_sum` para muestras pequeñas que usa `np.mat`, retirado en NumPy 2, y forma una matriz N×N. Su rama para N grande no necesita esa matriz: el diagnóstico inicial se precisa aquí, sin atribuirle coste cuadrático universal. Se utiliza `random` en todos los tamaños, sin modificar la biblioteca ni asignar distancias entre todas las observaciones.

La implementación usa NNLS con una coordenada constante 200 y renormalización posterior. Es una aproximación nativa al subproblema convexo; no se presenta como optimizador global exacto. El triángulo sintético comprueba ajuste, proyección fuera de entrenamiento, sumas y envolvente; la proyección se contrasta con SLSQP de SciPy, con exceso de SSE <1e−6. Las pruebas sintéticas se ejecutan **antes de leer matrices electorales para entrenar**.

`rss_` guarda una norma de Frobenius, no SSE, y puede conservar la norma previa al último cambio. Por eso SSE y RMSE se recomputan. `n_iter_` es índice desde cero: se registra n_iter_+1. «stopped_before_limit» sólo infiere que se activó el criterio nativo de cambio absoluto de norma <1e−4; no certifica un mínimo global. Se guardan α del último ajuste y α recalculada con `transform` sobre los arquetipos finales, esta última usada para reconstrucciones comparables. No hay historial por iteración disponible: no se inventa.

## Ajustes, reconstrucción y complejidad

Se completaron **{len(metrics)} ajustes principales**, tres semillas (17,42,2024), K=2–6, dos geometrías y tres contextos. Cada semilla es una inicialización nativa aleatoria, n_init=1, máximo 300 iteraciones y tol=1e−4. Se conservan todos los ajustes y se utiliza el de menor SSE recomputada por contexto/geometría/K para los diagnósticos; no equivale a elegir K. Hubo {len(failures)} fallos de configuración y **{budget} ajustes alcanzaron el límite**. No se ocultan los resultados no detenidos por tolerancia.

{table_text(selected_best[columns])}

RMSE original=100√media[(d−d̂)²], en pp; RMSE geométrico se guarda aparte. Error normalizado=√(SSE/SSE de la media de entrenamiento evaluada sobre esa misma población). Se guardan percentiles y errores por banda, sexo, entidad, cuartil de LN y NS. Ni la media simple de diferencias ni una mezcla de tasas son tasas poblacionales obtenidas de sumar conteos.

{chart_reference('reconstruction_vs_k')}

Hay {nonunique} soluciones representativas con dependencia afín entre arquetipos. En tres dimensiones, K≥5 implica esa dependencia; en cuatro, K≥6. Incluso con K menor puede haber ambigüedad, proximidad o inestabilidad. Distintas α pueden reconstruir el mismo punto: una mezcla no es necesariamente identificable. No convertir coeficiente dominante en categoría rígida ni probabilidad de votar.

## Curvas electorales e interpretación

Ejemplo de diagnóstico: **AA2, tres bandas, población común, K=3, semilla {int(main.seed)}**. Los identificadores A0/A1/A2 son locales; no equivalen a reglas ni tienen identidad entre ajustes.

{table_text(curves[['archetype','age_band','delta_pp','level_pp','shape_pp']])}

{chr(10).join(reasons)}

El nivel y la forma distinguen amplitudes y contrastes, pero no establecen que haya tres tipos naturales. Las curvas pueden representar grados de un gradiente. La participación absoluta de cada arquetipo se guarda como β×tasas de entrenamiento y su referencia como β×referencias: su resta coincide con la curva relativa. Esa combinación de perfiles no representa la participación de una población artificial ni un municipio real.

{chart_reference('archetype_curves')}

## Mezclas y reconstrucción de observaciones reales

En ese diagnóstico, **{100*mainmix.mixed_fraction:.2f} %** tiene coeficiente máximo <0.8, **{100*mainmix.multiple_substantial_fraction:.2f} %** al menos dos coeficientes ≥0.1; entropía normalizada media={mainmix.entropy_mean:.4f}. Los umbrales son descriptivos, no pruebas de pertenencia o incertidumbre electoral. La entropía depende de K y de la geometría, y puede cambiar con mezclas no únicas.

{table_text(mix[['context','geometry','k','mixed_fraction','entropy_mean','multiple_substantial_fraction']])}

{chart_reference('mixture_distributions')}
{chart_reference('ternary_mixtures')}
{chart_reference('mixture_bars')}
{chart_reference('higher_k_mixture_bars')}
{chart_reference('real_reconstructions')}

Los casos reales se eligen determinísticamente por error mediano, p95 y máximo; no se generan votantes ni observaciones artificiales. Coeficientes, conteos, row_id y banderas se mantienen alineados. Errores y coeficientes se relacionan descriptivamente con LN, denominadores, NS y secciones; las correlaciones no prueban causas ni fiabilidad individual.

## Valores extremos, influencia y sensibilidades obligatorias

La auditoría previa registra distancia al centro, cola radial 1 %, denominadores, NS y secciones por perfil. Un atípico estadístico no es un dato incorrecto. β identifica las observaciones que definen los arquetipos; se guardan diez contribuyentes por arquetipo, peso máximo, suma de los diez y 1/Σβ² como concentración equivalente, **no personas ni tamaño muestral efectivo**.

{table_text(inf_top[['archetype','row_id','weight','LN','max_ns','min_sections','min_specified','radial_extreme','concentration_equivalent','top10_share']])}

En este diagnóstico los tres mayores contribuyentes pertenecen a la cola radial extrema. A0 tiene β máximo=1: depende de un único perfil, con tres secciones en su banda de menor soporte; A1 concentra aproximadamente 81 % en un perfil con una sección. Los tres máximos tienen NS=0 en sus bandas: la influencia extrema no se explica aquí por NS alto. Tener denominadores suficientes no garantiza soporte territorial amplio. Estos son extremos válidos observados, no errores demostrados, ni prototipos representativos de la población.

- **R0:** todos los elegibles; ajuste clásico.
- **R1:** retira temporalmente ceil(1 %×n) perfiles de mayor distancia al centro en la geometría de entrenamiento, desempate por orden row_id estable. Se calcula sólo en entrenamiento; no se borran registros. Escala principal fija para aislar el cambio de población. Todos los elegibles se proyectan y evalúan después.
- **R2:** entrenamiento temporal con todas las bandas NS/LN<10 % y al menos cinco secciones distintas en cada banda. Son alertas operativas, no criterios oficiales. Todos se conservan y se evalúan en el universo común. Cambia cobertura y composición, no identifica lo que habrían votado los NS.

Se aplican a las tres configuraciones de validación, tres semillas para R1/R2, reutilizando R0. Los resultados promediados entre semillas y el peor desplazamiento son:

{table_text(sens_summary)}

Para AA2 tres-común K3, la cola temporal del 1 % produce desplazamientos de curva hasta {primary_sensitivity.loc['R1','curve_shift_max_pp']:.2f} pp y el escenario de calidad hasta {primary_sensitivity.loc['R2','curve_shift_max_pp']:.2f} pp. La calidad conserva 2,641/4,571 perfiles para ajustar; el resto sigue evaluado. Estas diferencias combinan cambio de soporte y optimización finita: no son efectos causales puros de quitar extremos o NS.

{chart_reference('extreme_influence')}

Los arquetipos clásicos privilegian extremos de la envolvente. Una β concentrada o el desplazamiento tras R1/R2 muestra sensibilidad, sin probar que ese registro sea falso. La bibliografía robusta propone M-estimadores y reponderación iterativa de residuos; un ajuste sobre una población temporalmente recortada **no es Robust Archetypal Analysis**. La versión instalada no expone una variante robusta formal verificable, ni pesos de ajuste explícitos: no se inventa o reimplementa un optimizador complejo. Se entrega esa limitación y las sensibilidades clásicas. [Eugster y Leisch, artículo de 2011]({SOURCES['eugster_leisch_2011']}), [prepublicación de autores de 2010]({SOURCES['robust_author_preprint_2010']}).

## Submuestreo municipal y validación fuera de entrenamiento

Se validan sólo tres configuraciones: AA2 tres-común K2/K3 y cuatro-común K3. K3 es una prueba parsimoniosa de mezcla, K2 controla complejidad y el cuarto intervalo controla detalle; no se seleccionaron por el menor error de entrenamiento ni se proclama ganador. AA1 no recibe validación OOB en este presupuesto y no debe adoptarse con base en sus errores de ajuste.

Se reutilizan diez sorteos municipales compartidos del protocolo previo (1,981 de 2,477 municipios por sorteo, sin reemplazo); ambos sexos permanecen juntos. Las escalas se reajustan **sólo dentro de entrenamiento**, así como β y los arquetipos. `transform` obtiene coeficientes convexos OOB. Las referencias nacionales permanecen fijas con todos los conteos de 2024: es estabilidad condicional, no predicción independiente de toda la construcción nacional. Cada remuestra usa semilla 17 y una inicialización: la variación mezcla perturbación territorial y optimización local, y no se atribuye toda a muestreo.

Se alinea con Hungarian sobre distancias RMS de curvas originales, una matriz K×K; no se compara por número arbitrario. Se guardan permutaciones implícitas mediante α alineada y curvas originales en modelos; los índices de evaluación y entrenamiento están explícitos. Comparar curvas no garantiza coeficientes identificables. La cobertura completa de cada sorteo está en resampling_coverage.csv: perfiles, municipios activos/inactivos, LN elegible y OOB.

{table_text(summary)}

**Complejidad emparejada:** en las diez mismas muestras, pasar K2→K3 reduce RMSE OOB una mediana de **{paired.reduction_pp.median():.3f} pp** (reducción relativa mediana **{100*paired.relative_reduction.median():.2f} %**), con rango de reducción {paired.reduction_pp.min():.3f}–{paired.reduction_pp.max():.3f} pp. Esto cuantifica beneficio de K3 para reconstrucción, no prueba una tercera clase electoral. K4–6 no tienen validación municipal OOB en este presupuesto: su error de entrenamiento no justifica todavía la complejidad adicional.

Peor caso del diagnóstico principal AA2 tres-común K3: RMSE OOB máximo **{primary_oob.oob_rmse_max_pp:.3f} pp**, máximo desplazamiento de una curva **{primary_oob.curve_shift_max_pp:.2f} pp**; la comparación de semillas de población completa registra hasta **{main_seed.max_seed_curve_shift_pp:.2f} pp**. Las medianas no deben ocultar esas colas. Ampliar inicializaciones y remuestras antes de adopción.

{chart_reference('out_of_training_error')}
{chart_reference('municipal_stability')}

## Tres y cuatro bandas: comparación controlada

Cuatro natural es idéntico a cuatro común, 4,571 filas; se documenta como alias, sin duplicar ajustes. Tres natural tiene 4,648 y tres común 4,571. Ambas poblaciones comunes comparten row_id, conteos totales y orden. Las bandas no son una partición anidada: no se equiparan errores globales con tres y cuatro objetivos diferentes. **60–100 sí es la misma coordenada y referencia**, por eso su error se contrasta sobre las mismas filas:

{table_text(bands[['geometry','k','n','three_older_rmse_pp','four_older_rmse_pp','common_older_reconstruction_difference_pp']])}

El error normalizado frente a la media propia es diagnóstico interno, no un ranking universal entre dimensiones. Cuatro ofrece separación descriptiva de edades adultas; su utilidad debe sopesarse con curvas, estabilidad y 77 perfiles/45 municipios menos que tres natural. No se entrena cinco bandas: mantiene el bloqueo preventivo anterior de cobertura. Ninguna diferencia se interpreta como cambio de comportamiento individual.

{chart_reference('three_four_comparison')}

## K-Means K2 y seis candidatos por reglas

Se reutilizan los centroides/etiquetas K-Means K2 semilla17 de R1/R3 previos, **sin reajuste**. Sobre tres natural, AA1/AA2 reproducen exactamente esas matrices y poblaciones. La reconstrucción K-Means es rígida al centro asignado; AA usa mezclas convexas, por lo que su mayor flexibilidad puede reducir error sin demostrar superioridad electoral. No se comparan Silhouette ni ARI como criterio para AA. No se atribuye validación OOB nueva a esos K-Means.

{table_text(km[['geometry','aa_k','aa_rmse_pp','kmeans_k','kmeans_rmse_pp','kmeans_normalized_rmse']])}

Las seis fichas previas son municipio×banda×sexo; AA es municipio×sexo. Se pivota una firma de las tres etiquetas y se une uno a uno a los 4,571 perfiles comunes. Cada perfil cuenta una vez; no se multiplican observaciones, ni se calcula ARI entre unidades incompatibles. Firmas de signo iguales permiten mezclas diferentes porque las reglas no codifican la intensidad ni todos los contrastes. Ejemplo determinista de rango máximo dentro de una firma:

{table_text(examples)}

Esto muestra información numérica complementaria, no eficacia, causalidad ni sustitución de las reglas. Las fichas siguen siendo una comunicación transparente por edad/signo; AA visualiza gradientes y extremos con advertencias. Los promedios de α por sexo/municipio son promedios de perfiles, no fracciones de personas.

{chart_reference('rule_profile_context')}
{chart_reference('sex_municipality_composition')}

## Respuestas para la decisión

1. **¿Pudo ejecutarse?** Sí: biblioteca real, pruebas previas y convexidad validadas, {len(metrics)} ajustes principales y 30 municipales; las limitaciones de versión, parada y optimización están documentadas.
2. **¿Cuántos son razonables?** K2 y K3 son candidatos parsimoniosos para describir nivel/contrastes. K3 reduce error OOB medido; K4–6 sólo amplían capacidad de entrenamiento por ahora. No hay K definitivo ni seis por requisito narrativo.
3. **¿Patrones distintos?** Las curvas cuantifican nivel y contraste joven–mayor; son extremos agregados de gradientes, no motivaciones ni clases naturales. Revisar diferencias sustantivas y sensibilidad antes de ponerles nombres electorales.
4. **¿Mayoría requiere mezclas?** En AA2 tres-común K3, {100*mainmix.mixed_fraction:.2f} % no está dominado por un coeficiente ≥0.8; la respuesta depende del umbral/K y no asegura unicidad.
5. **¿Información adicional?** Sí como magnitud continua y forma dentro de la misma firma de reglas. Su valor práctico y estabilidad de coeficientes requieren validación de uso; no son probabilidades individuales.
6. **¿Sensibilidad a extremos?** Las tablas R1/R2, β y sus máximos muestran cuánto cambian curvas/reconstrucción. Es una limitación central del clásico, no una autorización para eliminar observaciones ni una variante robusta formal.
7. **¿Estabilidad municipal?** Se informa media, mediana y peor caso, con desplazamiento máximo de {primary_oob.curve_shift_max_pp:.2f} pp en AA2 tres-común K3. No declarar estabilidad universal a partir de un promedio.
8. **¿Cobertura?** Principal tres: 4,648 perfiles, 2,341 municipios, 99.8203 % LN. Común/cuatro: 4,571, 2,296, 99.7855 %. Todos los pendientes y complementos se conservan; R1/R2 son entrenamientos temporales.
9. **¿Tres o cuatro?** Mantener tres como resumen principal y cuatro como complemento descriptivo. El error de espacios diferentes no decide; consultar el contraste válido 60–100 y OOB emparejado, sin afirmar mayor información sólo por dimensión.
10. **¿Complejidad OOB?** K3 frente a K2 tiene beneficio medido arriba; K4–6 necesitan validación adicional y control de mezclas no únicas. No basta el menor SSE de entrenamiento.
11. **¿Algo nuevo?** Frente al centro rígido K2, reconstrucción convexa y coordenadas de mezcla; frente a las reglas, intensidad dentro de los mismos signos. No demuestra superioridad global ni reemplazo de fichas.
12. **¿Complemento visual?** Sí, como herramienta exploratoria con curvas, mezclas, soporte y error visibles. Un ternario sólo corresponde a K3; proyecciones 2D no prueban separación total. No se publica a React.
13. **¿Adoptar o descartar?** Conservar como prototipo visual de investigación; evidencia insuficiente para adoptarlo como perfil definitivo. La sensibilidad, optimización y no unicidad deben resolverse o mostrarse explícitamente. No hace falta descartarlo por no producir clases, pero tampoco venderlo como solución validada.

## Conservación, integridad y reproducción

Se verifican marcadores _SUCCESS y manifiestos de las tres fuentes reutilizadas, referencias antes de soporte, conteos por sexo/banda, perfiles comunes idénticos, escalas de entrenamiento, restricciones α/β con tolerancia 1e−8, Z=βX, reconstrucciones en ambas escalas y modelos sin distancias N×N. Los modelos conservan α n×K, β K×n_entrenamiento y máscara de pertenencia; filas pendientes tienen coeficientes NULL en all_observations, nunca cero. observation_status distingue el soporte original de las 77 filas elegibles en tres pero fuera de la población común. archetype_alignments conserva permutaciones y distancias explícitas. Los Parquet se releen y comparan. Las pruebas cubren SLSQP sintético, geometría ortogonal/inversión, convexidad, permutaciones, mezclas no únicas, universo común y remuestreo agrupado.

Se protegen por hash **{len(self.state['protected_hashes'])} archivos existentes**: fuentes, tablas/resultados/reportes/gráficas anteriores, scripts previos, frontend, .gitignore y referencias del entorno anterior. El lock exclusivo impide procesos duplicados; cada modelo tiene marcador, parámetros, huellas, joblib y NPZ escritos atómicamente. Etapas A–F permiten reanudar sin repetir modelos verificados. Si falla una etapa se registra el error y se conservan resultados válidos. _SUCCESS sólo aparece tras pruebas y comprobación final de integridad.

Estructura: reference/ con todos los perfiles, pendientes y complementos; matrices/ con características, escalas y calidad; models/ con 90 ajustes principales y sensibilidades/remuestras; diagnostics/ con mezclas por observación, pendientes y relación de errores; sensitivity/ y resampling/ con membresía; comparisons/ con reglas; metadata/ con métricas, fuentes, API real, versiones, checkpoints y manifiesto. Los identificadores y rutas son ingleses; los textos de informe y gráficas, españoles. El estado de biblioteca robusta formal es **no disponible en esta implementación**.

```powershell
.venv_archetypal_patterns/Scripts/python.exe analysis/scripts/evaluate_archetypal_patterns.py
.venv_archetypal_patterns/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_evaluate_archetypal_patterns.py
```

La repetición con las mismas rutas verifica checkpoints; parámetros o entradas diferentes requieren nuevos --output, --charts y --report. --stop-after permite detenerse después de una etapa completa. --refresh-report archiva el informe de esta entrega y regenera únicamente sus diagnósticos finales, sin reajustar modelos. No se modifican datos previos, informes de otros experimentos, modelos históricos, frontend ni public/data; no se crean commits. No se ajusta AA robusto formal ni otros algoritmos de clustering.
'''
        atomic_bytes(self.report,report.encode('utf8'))

    def finalize(self):
        self.verify_protected()
        manifest_path=self.output/'metadata/run_manifest.json';success=self.output/'_SUCCESS'
        if success.exists():
            marker=json.loads(success.read_text());require(marker['manifest_sha256']==file_hash(manifest_path),'Marcador final alterado.')
            manifest=json.loads(manifest_path.read_text())
            for relative,digest in manifest['artifact_hashes'].items():require(file_hash(self.root/relative)==digest,'Artefacto final alterado: '+relative)
            print('Resultado completo verificado; no se repiten ajustes.',flush=True);return
        self.state['status']='validated';self.state['finished']=utc();write_json(self.state_path,self.state)
        artifacts=[p for p in self.output.rglob('*') if p.is_file() and p.name not in ['run_manifest.json','state.json','_RUNNING.json','_SUCCESS']]
        artifacts += [p for p in self.charts.rglob('*') if p.is_file()]+[self.report]+[self.root/'analysis/scripts'/name for name in OWN_FILES]
        write_json(manifest_path,dict(status='validated',finished=utc(),config=CONFIG,versions=self.dependencies,
            protected_files=len(self.state['protected_hashes']),protected_hashes=self.state['protected_hashes'],
            artifact_hashes={str(p.relative_to(self.root)):file_hash(p) for p in artifacts},
            model_counts=dict(main=len(list((self.output/'models/main').rglob('_COMPLETE.json'))),
                sensitivity=len(list((self.output/'models/sensitivity').rglob('_COMPLETE.json'))),
                resampling=len(list((self.output/'models/resampling').rglob('_COMPLETE.json'))))))
        write_json(success,dict(manifest_sha256=file_hash(manifest_path),finished=utc()))
        print('Validación final completa: '+str(self.report),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'data/processed/archetypal_pattern_review')
    parser.add_argument('--charts',type=Path,default=ROOT/'analysis/charts/archetypal_pattern_review')
    parser.add_argument('--report',type=Path,default=ROOT/'analysis/reports/archetypal_pattern_review.md')
    parser.add_argument('--stop-after',choices=list('abcdef'),default='f')
    parser.add_argument('--refresh-report',action='store_true',help='Revisar sólo el informe propio y diagnóstico final, conservando modelos.')
    args=parser.parse_args()
    with experiment_lock(args.output):
        experiment=None
        try:
            experiment=Experiment(ROOT,args.output,args.charts,args.report)
            if args.refresh_report:experiment.refresh_render()
            experiment.run(args.stop_after)
        except Exception as exc:
            if experiment is not None:
                experiment.state['status']='failed';experiment.state['errors'].append(dict(time=utc(),error=repr(exc),traceback=traceback.format_exc()))
                write_json(experiment.state_path,experiment.state)
            raise


if __name__=='__main__':main()
