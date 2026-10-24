"""Validación final recuperable de AA2 K2/K3, sin sustituir los seis perfiles.

Se separan dispersión entre arranques sobre datos fijos y perturbación municipal
con optimización equivalente. Se reutilizan ajustes íntegros sin repetirlos.
"""
from __future__ import annotations
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MPLCONFIGDIR']=str(ROOT/'.venv_archetypal_patterns/mplconfig')
for variable in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
    os.environ[variable]='1'
import sys
sys.dont_write_bytecode=True
import argparse
import hashlib
import itertools
import json
import subprocess
import time
import traceback
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from archetypes import AA

from clean_data import require,file_hash
from build_cluster_features import snapshot_inputs
from build_profile_candidates import table_text
from compare_pattern_algorithms import Comparison
from evaluate_participation_patterns import atomic_bytes,experiment_lock,memory_estimate,utc,save_figure
from evaluate_archetypal_patterns import (fit_scaler,transform,inverse,validate_convex,
    synthetic_validation,mixture_statistics,aligned,errors_summary,write_json,KEYS,MUNICIPAL_KEYS)

BANDS=['18-34','35-59','60-100']
SEEDS=[17,42,2024,1009,2027,4001,5003,7001,9001,11003]
OWN_FILES=['validate_archetypal_stability.py','test_validate_archetypal_stability.py']
CONFIG=dict(version='1.0',geometry='AA2',bands=BANDS,ks=[2,3],seeds=SEEDS,starts=10,
    max_iter=300,tol=1e-4,initialization='random',subsamples=10,extreme_fraction=.01,
    high_ns=.10,minimum_sections=5,dominance=.8,convex_tolerance=1e-8,
    near_best_sse_fraction=.01,curve_review_alert_pp=5.,similar_reconstruction_alert_pp=1.,
    selection='SSE geométrica de entrenamiento recalculada con transform; nunca OOB',
    sensitivity_scaler='escala E0 fija para aislar población; no es validación predictiva',
    sample_scaler='reajustada sólo dentro de cada entrenamiento municipal')


def choose_best(frame):
    """La selección es ajena a OOB, estética de curvas y etiquetas electorales."""
    valid=frame[np.isfinite(frame.sse)].copy()
    require(len(valid)>0,'Ningún ajuste válido para seleccionar.')
    return valid.sort_values(['sse','seed'],kind='stable').iloc[0]


def extreme_mask(x,row_ids,fraction=.01):
    radial=np.linalg.norm(x-x.mean(0),axis=1)
    order=np.lexsort((np.asarray(row_ids,dtype=str),-radial))
    excluded=order[:int(np.ceil(len(x)*fraction))]
    mask=np.ones(len(x),bool);mask[excluded]=False
    return mask,radial


def curve_contrasts(curves):
    curves=np.asarray(curves,float)
    return pd.DataFrame(dict(level_pp=curves.mean(1)*100,
        young_minus_older_pp=(curves[:,0]-curves[:,2])*100,
        adult_minus_endpoint_mean_pp=(curves[:,1]-(curves[:,0]+curves[:,2])/2)*100,
        shape_range_pp=np.ptp(curves,axis=1)*100))


def paired_effects(reference,alternative):
    """Alineación en curvas originales; reconstrucción se compara sin etiquetas."""
    order,dist=aligned(reference['archetypes_original'],alternative['archetypes_original'])
    alpha_l1=np.abs(reference['alpha']-alternative['alpha'][:,order]).sum(1)
    difference=np.sqrt(np.mean((reference['reconstruction_original']-alternative['reconstruction_original'])**2,1))*100
    return dict(order=order,curve_distances_pp=dist*100,alpha_l1=alpha_l1,
        reconstruction_difference_pp=difference,
        max_curve_shift_pp=float(dist.max()*100),median_curve_shift_pp=float(np.median(dist)*100),
        alpha_l1_mean=float(alpha_l1.mean()),alpha_l1_p95=float(np.quantile(alpha_l1,.95)),
        alpha_l1_max=float(alpha_l1.max()),reconstruction_difference_rmse_pp=float(np.sqrt(np.mean(difference**2))))


def variance_partition(values):
    """Identidad descriptiva balanceada; no estima efectos causales ni votantes."""
    values=np.asarray(values,float)
    require(values.ndim==3 and np.isfinite(values).all(),'Descomposición requiere muestras×semillas×coordenadas completas.')
    group_mean=values.mean(1);overall=values.mean((0,1))
    within=float(np.mean((values-group_mean[:,None,:])**2))
    between=float(np.mean((group_mean-overall)**2));total=float(np.mean((values-overall)**2))
    require(np.isclose(within+between,total,atol=1e-9),'Identidad de varianzas no satisfecha.')
    return dict(within_seed_pp2=within,between_sample_means_pp2=between,total_pp2=total,
        within_fraction=within/total if total>1e-20 else None,
        between_fraction=between/total if total>1e-20 else None,
        identity_residual=float(abs(within+between-total)))


class Validation:
    valid_stage=Comparison.valid_stage
    table=Comparison.table
    bundle=Comparison.bundle

    def __init__(self,root,output,charts,report):
        self.root,self.output,self.charts,self.report=[Path(p).resolve() for p in [root,output,charts,report]]
        require(self.output.is_relative_to(self.root/'data/processed') and self.charts.is_relative_to(self.root/'analysis/charts')
            and self.report.is_relative_to(self.root/'analysis/reports'),'Destinos fuera del área de análisis.')
        self.source=self.root/'data/processed/archetypal_pattern_review'
        self.state_path=self.output/'metadata/state.json'
        import archetypes,sklearn,scipy,matplotlib,pyarrow
        self.dependencies=dict(imports={name:module.__version__ for name,module in [('archetypes',archetypes),('sklearn',sklearn),
            ('scipy',scipy),('numpy',np),('pandas',pd),('matplotlib',matplotlib),('pyarrow',pyarrow),('joblib',joblib)]})
        if self.state_path.exists():
            self.state=json.loads(self.state_path.read_text(encoding='utf8'))
            require(self.state['config']==CONFIG and self.state['dependencies']==self.dependencies,'Cambió configuración o entorno; usar destinos nuevos.')
            require(self.state['charts']==str(self.charts) and self.state['report']==str(self.report),'Destinos de recuperación diferentes.')
            self.verify_protected()
        else:
            existing=[p for p in self.output.rglob('*') if p.is_file() and p.name!='_RUNNING.json']
            require(not existing and not self.charts.exists() and not self.report.exists(),'Se protegen destinos anteriores.')
            protected=snapshot_inputs(self.root,self.output,self.charts)
            for directory in ['analysis/scripts','src','public']:
                for path in (self.root/directory).rglob('*'):
                    if path.is_file() and '__pycache__' not in path.parts and path.name not in OWN_FILES:
                        protected[str(path)]=file_hash(path)
            for path in [self.root/'.gitignore',self.root/'.venv_archetypal_patterns/pyvenv.cfg']:
                protected[str(path)]=file_hash(path)
            self.state=dict(started=utc(),status='running',config=CONFIG,dependencies=self.dependencies,
                protected_hashes=protected,stages={},errors=[],charts=str(self.charts),report=str(self.report))
            write_json(self.state_path,self.state)

    def verify_protected(self):
        for path,digest in self.state['protected_hashes'].items():require(file_hash(path)==digest,'Archivo previo alterado: '+path)

    def checkpoint(self,stage,paths,started,summary):
        unique=list(dict.fromkeys(paths))
        record=dict(status='complete',stage=stage,seconds=time.monotonic()-started,finished=utc(),summary=summary,
            memory=memory_estimate(),script_sha256=file_hash(Path(__file__)),versions=self.dependencies['imports'],
            artifacts={str(p.relative_to(self.root)):file_hash(p) for p in unique})
        write_json(self.output/f'metadata/checkpoint_{stage}.json',record)
        self.state['stages'][stage]=dict(seconds=record['seconds'],summary=summary);write_json(self.state_path,self.state)
        print(f'Etapa {stage}: {summary}',flush=True)

    def frame(self):return pd.read_parquet(self.output/'reference/eligible_profiles.parquet')
    def scaler(self):return json.loads((self.output/'matrices/scaler.json').read_text())
    def arrays(self,row):
        with np.load(self.root/row['artifact_folder']/'arrays.npz',allow_pickle=False) as a:
            return {name:a[name].copy() for name in a.files}

    def model_paths(self,records):
        paths=[]
        for row in records:
            folder=self.root/row['artifact_folder']
            if not row['reused']:
                paths += [folder/name for name in ['arrays.npz','model.joblib','details.json','_COMPLETE.json']]
        return paths

    def stage_a(self):
        started=time.monotonic();paths=[];checks=synthetic_validation()
        require(checks['status']=='passed','Falló la biblioteca antes del entrenamiento.')
        dep=subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True)
        require(dep.returncode==0,'Dependencias incompatibles: '+dep.stdout+dep.stderr)
        manifests=[]
        for name in ['archetypal_pattern_review','profile_candidates_review','participation_pattern_review','age_band_representation_review']:
            folder=self.root/'data/processed'/name;mp=folder/'metadata/run_manifest.json'
            marker=json.loads((folder/'_SUCCESS').read_text());manifest=json.loads(mp.read_text(encoding='utf8'))
            require(marker['manifest_sha256']==file_hash(mp) and manifest['status']=='validated','Fuente no validada: '+name)
            for relative,digest in manifest['artifact_hashes'].items():
                require(self.state['protected_hashes'].get(str(self.root/relative))==digest,'Fuente distinta de manifiesto: '+relative)
            manifests.append(dict(source=name,manifest_sha256=file_hash(mp),artifacts=len(manifest['artifact_hashes'])))
        for source,target in [('matrices/three_common/metadata.parquet','reference/eligible_profiles.parquet'),
            ('reference/three/profiles.parquet','reference/all_profiles.parquet'),
            ('reference/three/national_reference.parquet','reference/national_reference.parquet'),
            ('reference/complementary_and_full_broad.parquet','reference/broad_complete_reference.parquet'),
            ('reference/municipal_subsamples.parquet','reference/municipal_subsamples.parquet'),
            ('reference/rule_segments.parquet','reference/rule_segments.parquet'),
            ('matrices/three_common/AA2/features.parquet','matrices/features.parquet')]:
            paths.append(self.table(target,pd.read_parquet(self.source/source)))
        scale=json.loads((self.source/'matrices/three_common/AA2/scaler.json').read_text());write_json(self.output/'matrices/scaler.json',scale);paths.append(self.output/'matrices/scaler.json')
        frame=self.frame();d=frame[[f'delta_{j}' for j in range(3)]].to_numpy(float);x=transform(d,scale)
        require(len(frame)==4571 and frame.row_id.is_unique and frame.groupby(MUNICIPAL_KEYS).ngroups==2296,'Universo diferente.')
        require(frame.LN.sum()==98119426 and frame.LN.eq(frame.SV+frame.NV+frame.NS).all(),'Conteos distintos.')
        require(frame[KEYS].map(lambda v:isinstance(v,str)).all().all(),'Claves no textuales.')
        stored=pd.read_parquet(self.output/'matrices/features.parquet')
        require(stored.row_id.equals(frame.row_id) and np.array_equal(x,stored.drop(columns='row_id').to_numpy()),'Matriz AA2 no idéntica.')
        full=pd.read_parquet(self.output/'reference/all_profiles.parquet');broad=pd.read_parquet(self.output/'reference/broad_complete_reference.parquet')
        require(len(full)==4954 and len(broad)==17735 and broad.sex_2_nominal_count.sum()==105,'Referencias incompletas.')
        status=full[['row_id',*KEYS,'is_eligible','pending_reason','LN','SV','NV','NS','source_row_count']].copy()
        status['in_matrix']=status.row_id.isin(frame.row_id)
        status['matrix_status']=np.select([status.in_matrix,~status.is_eligible],['eligible','source_support_pending'],default='outside_common_population')
        paths.append(self.table('reference/observation_status.parquet',status))
        diagnosis=subprocess.run(['powershell','-NoProfile','-Command','Get-Process -Name python,pythonw,python3 -ErrorAction SilentlyContinue | Select-Object Id,StartTime,ProcessName | ConvertTo-Json'],capture_output=True,text=True)
        git=subprocess.run(['git','status','--short'],capture_output=True,text=True)
        write_json(self.output/'metadata/initial_diagnosis.json',dict(versions=self.dependencies,python=sys.version,
            executable=sys.executable,processes=diagnosis.stdout,git_status=git.stdout,synthetic=checks,
            pip_check=dep.stdout,validated_sources=manifests,config=CONFIG,package_installations=0))
        paths.append(self.output/'metadata/initial_diagnosis.json')
        write_json(self.output/'metadata/feature_contract.json',dict(config=CONFIG,unit='municipality_sex',
            eligible_profiles=4571,municipalities=2296,LN=98119426,nominal_fraction=98119426/98330348,
            unchanged_rule_profiles=6,selection_uses_oob=False,features=['AA2_level','AA2_shape_1','AA2_shape_2'],
            mixture_meaning='coeficientes convexos agregados; no porcentajes de ciudadanos ni probabilidades de votar',
            review_alerts='5 pp y SSE 1% son diagnósticos predefinidos de esta revisión, no umbrales oficiales ni intervalos de confianza'))
        paths.append(self.output/'metadata/feature_contract.json')
        self.checkpoint('a',paths,started,dict(profiles=4571,municipalities=2296,protected_files=len(self.state['protected_hashes']),synthetic='passed'))

    def fit(self,trial_id,k,seed,mask=None,scaler=None,previous=None):
        frame=self.frame();d=frame[[f'delta_{j}' for j in range(3)]].to_numpy(float)
        mask=np.ones(len(frame),bool) if mask is None else np.asarray(mask,bool)
        s=fit_scaler(d[mask],'AA2',frame.loc[mask,'row_id']) if scaler is None else scaler
        x=transform(d,s);train=x[mask]
        base_record=dict(trial_id=trial_id,k=int(k),seed=int(seed),training_profiles=int(mask.sum()),
            training_municipalities=frame[mask].groupby(MUNICIPAL_KEYS).ngroups,LN_training=int(frame.loc[mask,'LN'].sum()),
            oob_profiles=int((~mask).sum()),oob_municipalities=frame[~mask].groupby(MUNICIPAL_KEYS).ngroups,
            training_nominal_fraction=float(frame.loc[mask,'LN'].sum()/98330348))
        if previous is not None:
            folder=self.source/'models'/previous;marker_path=folder/'_COMPLETE.json'
            if marker_path.exists():
                marker=json.loads(marker_path.read_text());params=marker['parameters']
                require(params['k']==k and params['seed']==seed and params['geometry']=='AA2','Modelo previo con otros parámetros.')
                require(params['scaler']==s and params['config']['max_iter']==CONFIG['max_iter'] and params['config']['tol']==CONFIG['tol'],'Preprocesamiento previo distinto.')
                require(marker['input_sha256']==hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest(),'Huella de matriz previa distinta.')
                for name,digest in marker['files'].items():require(file_hash(folder/name)==digest,'Modelo previo alterado.')
                with np.load(folder/'arrays.npz') as a:arrays={name:a[name].copy() for name in a.files}
                require(np.array_equal(arrays['training_mask'],mask),'Entrenamiento previo distinto.')
                details=json.loads((folder/'details.json').read_text());validate_convex(arrays['alpha'],arrays['beta'],arrays['archetypes'],train,x)
                record=dict(**base_record,artifact_folder=str(folder.relative_to(self.root)),reused=True,
                    sse=float(details['sse']),raw_rmse_pp=float(details['raw_rmse_pp']),normalized_rmse=float(details['normalized_rmse']),
                    iterations=int(details['iterations']),stopped_before_limit=bool(details['stopped_before_limit']),
                    seconds=float(details['seconds']),peak_memory_mib=details['memory'].get('peak_working_set_MiB'))
                write_json(self.output/f'reused/{trial_id}.json',dict(record=record,previous_marker_sha256=file_hash(marker_path),
                    previous_file_hashes=marker['files'],reason='Identidad exacta de matriz, escala, semilla, máscara y presupuesto. No se vuelve a ajustar.'))
                print('Reutilizado: '+trial_id,flush=True)
                return record
        parameters=dict(config=CONFIG,k=int(k),seed=int(seed),scaler=s,
            training_row_ids_sha256=hashlib.sha256('\n'.join(frame.loc[mask,'row_id']).encode()).hexdigest())
        def callback():
            print('Ajuste nuevo: '+trial_id,flush=True)
            model=AA(n_archetypes=int(k),n_init=1,algorithm_init='random',random_state=int(seed),max_iter=CONFIG['max_iter'],tol=CONFIG['tol']).fit(train)
            alpha=model.transform(x);beta=model.betas_;z=model.archetypes_
            checks=validate_convex(alpha,beta,z,train,x);zraw=inverse(z,s);recon=inverse(alpha@z,s)
            require(np.allclose(zraw,beta@d[mask],atol=1e-9),'Envolvente original distinta.')
            require(np.allclose(recon,alpha@zraw,atol=1e-9),'Reconstrucción no coherente.')
            arrays=dict(alpha=alpha,beta=beta,archetypes=z,archetypes_original=zraw,reconstruction=alpha@z,
                reconstruction_original=recon,training_alpha=model.alphas_,training_mask=mask,values=x,
                archetypes_absolute=beta@frame.loc[mask,[f'rate_{j}' for j in range(3)]].to_numpy(float),
                archetypes_peer_reference=beta@frame.loc[mask,[f'national_rate_{j}' for j in range(3)]].to_numpy(float))
            error=errors_summary(train,arrays['reconstruction'][mask],d[mask],recon[mask],train.mean(0))
            details=dict(trial_id=trial_id,k=k,seed=seed,scaler=s,**error,**checks,
                iterations=int(model.n_iter_)+1,stopped_before_limit=bool(model.n_iter_+1<CONFIG['max_iter']),
                legacy_rss_norm=float(model.rss_),training_alpha_sse=float(np.sum((train-model.alphas_@z)**2)))
            return model,arrays,details
        _,arrays,details=self.bundle(trial_id,x,parameters,callback)
        return dict(**base_record,artifact_folder=str((self.output/'models'/trial_id).relative_to(self.root)),reused=False,
            sse=float(details['sse']),raw_rmse_pp=float(details['raw_rmse_pp']),normalized_rmse=float(details['normalized_rmse']),
            iterations=int(details['iterations']),stopped_before_limit=bool(details['stopped_before_limit']),seconds=float(details['seconds']),
            peak_memory_mib=details['memory'].get('peak_working_set_MiB'))

    def stage_b(self):
        started=time.monotonic();records=[]
        for k,seed in itertools.product([2,3],SEEDS):
            record=self.fit(f'fixed/k{k}/seed{seed}',k,seed,scaler=self.scaler(),previous=f'main/three_common/AA2/k{k}/seed{seed}')
            record.update(experiment='fixed',sample=-1,scenario='E0');records.append(record)
        frame=pd.DataFrame(records);paths=[self.table('metadata/fixed_initializations.parquet',frame),self.table('metadata/fixed_initializations.csv',frame)]
        best=frame.loc[frame.groupby('k').sse.idxmin()].sort_values('k').reset_index(drop=True)
        paths.append(self.table('metadata/fixed_best.csv',best))
        for rec in records:
            if rec['reused']:paths.append(self.output/f'reused/{rec["trial_id"]}.json')
        self.checkpoint('b',paths+self.model_paths(records),started,dict(initializations=len(records),reused=int(frame.reused.sum()),new=int((~frame.reused).sum())))

    def stage_c(self):
        started=time.monotonic();records=[];paths=[];coverage=[];f=self.frame()
        members=pd.read_parquet(self.output/'reference/municipal_subsamples.parquet')
        attached=f.merge(members,on=MUNICIPAL_KEYS,how='left',sort=False,validate='many_to_one')
        require(attached.row_id.equals(f.row_id),'Remuestreo alteró filas.')
        for sample in range(CONFIG['subsamples']):
            flag=f'sample_{sample:03d}';mask=attached[flag].to_numpy(bool)
            require(f.assign(mask=mask).groupby(MUNICIPAL_KEYS)['mask'].nunique().eq(1).all(),'Sexos separados en muestreo.')
            member=f[['row_id',*KEYS,'LN']].copy();member['is_training']=mask;member['is_oob']=~mask
            paths.append(self.table(f'resampling/sample{sample:03d}/membership.parquet',member))
            coverage.append(dict(sample=sample,municipalities_drawn=int(members[flag].sum()),profiles_train=int(mask.sum()),profiles_oob=int((~mask).sum()),
                municipalities_train=f[mask].groupby(MUNICIPAL_KEYS).ngroups,municipalities_oob=f[~mask].groupby(MUNICIPAL_KEYS).ngroups,
                LN_train=int(f.loc[mask,'LN'].sum()),LN_oob=int(f.loc[~mask,'LN'].sum()),fraction_eligible_LN=float(f.loc[mask,'LN'].sum()/f.LN.sum())))
            for k,seed in itertools.product([2,3],SEEDS):
                previous=f'resampling/three_common/AA2/k{k}/sample{sample:03d}' if seed==17 else None
                record=self.fit(f'municipal/sample{sample:03d}/k{k}/seed{seed}',k,seed,mask=mask,previous=previous)
                record.update(experiment='municipal',sample=sample,scenario='E0');records.append(record)
        frame=pd.DataFrame(records);best=frame.loc[frame.groupby(['sample','k']).sse.idxmin()].sort_values(['sample','k'])
        for name,data in [('municipal_initializations',frame),('municipal_best',best),('sample_coverage',pd.DataFrame(coverage))]:
            paths.append(self.table(f'metadata/{name}.parquet',data));paths.append(self.table(f'metadata/{name}.csv',data))
        paths += [self.output/f'reused/{r["trial_id"]}.json' for r in records if r['reused']]
        self.checkpoint('c',paths+self.model_paths(records),started,dict(initializations=len(records),reused=int(frame.reused.sum()),new=int((~frame.reused).sum())))

    def stage_d(self):
        started=time.monotonic();paths=[];records=[];f=self.frame();s=self.scaler()
        full_best=pd.read_csv(self.output/'metadata/fixed_best.csv');reference=full_best[full_best.k==3].iloc[0]
        a=self.arrays(reference);x=a['values'];extreme,radial=extreme_mask(x,f.row_id)
        masks={'E1':extreme,'E2':(~f.has_high_ns_coordinate & f.min_section_count.ge(5)).to_numpy()}
        influence=[]
        for j,weights in enumerate(a['beta']):
            top=int(np.argmax(weights));scenario=f'E3_archetype{j}'
            masks[scenario]=np.arange(len(f))!=top
            influence.append(dict(scenario=scenario,archetype=j,excluded_row_id=f.row_id.iloc[top],weight=float(weights[top]),
                radial_distance=float(radial[top]),LN=int(f.LN.iloc[top])))
        exclusion=f[['row_id',*KEYS,'LN','has_high_ns_coordinate','min_section_count']].copy();exclusion['radial_distance']=radial
        for scenario,mask in masks.items():exclusion['training_'+scenario]=mask
        paths.append(self.table('sensitivity/exclusion_membership.parquet',exclusion))
        paths.append(self.table('metadata/individual_influence_design.csv',pd.DataFrame(influence)))
        for scenario,mask in masks.items():
            for seed in SEEDS:
                previous=f'sensitivity/three_common/AA2/R{scenario[-1]}/k3/seed{seed}' if scenario in ['E1','E2'] else None
                rec=self.fit(f'sensitivity/{scenario}/k3/seed{seed}',3,seed,mask=mask,scaler=s,previous=previous)
                rec.update(experiment='sensitivity',sample=-1,scenario=scenario);records.append(rec)
        all_records=pd.DataFrame(records);best=all_records.loc[all_records.groupby('scenario').sse.idxmin()]
        for name,data in [('sensitivity_initializations',all_records),('sensitivity_best',best)]:
            paths.append(self.table(f'metadata/{name}.parquet',data));paths.append(self.table(f'metadata/{name}.csv',data))
        paths += [self.output/f'reused/{r["trial_id"]}.json' for r in records if r['reused']]
        self.checkpoint('d',paths+self.model_paths(records),started,dict(initializations=len(records),reused=int(all_records.reused.sum()),new=int((~all_records.reused).sum())))

    def stage_e(self):
        started=time.monotonic();paths=[];f=self.frame();d=f[[f'delta_{j}' for j in range(3)]].to_numpy(float)
        catalog=pd.concat([pd.read_parquet(self.output/f'metadata/{name}_initializations.parquet') for name in ['fixed','municipal','sensitivity']],ignore_index=True)
        require(catalog.trial_id.is_unique and set(catalog.k)=={2,3},'Catálogo duplicado o K fuera de alcance.')
        paths.append(self.table('metadata/all_initializations.parquet',catalog))
        paths.append(self.table('metadata/all_initializations.csv',catalog))
        fixed=pd.read_csv(self.output/'metadata/fixed_best.csv');municipal=pd.read_parquet(self.output/'metadata/municipal_best.parquet')
        sensitivities=pd.read_parquet(self.output/'metadata/sensitivity_best.parquet')
        reference={int(row.k):row.to_dict() for _,row in fixed.iterrows()}
        ref_arrays={k:self.arrays(row) for k,row in reference.items()}
        metrics=[];curves=[];alignments=[];influence=[];pairs=[];group_rows=[];budgets=[];prefixes=[]
        best_ids=set(fixed.trial_id)|set(municipal.trial_id)|set(sensitivities.trial_id)
        curve_cache={};beta_stack=[];individual=[]
        # Procesamiento de una solución cada vez, sin matrices N×N.
        for _,row in catalog.iterrows():
            rec=row.to_dict();a=self.arrays(rec);k=int(row.k);ref=ref_arrays[k];effect=paired_effects(ref,a)
            mask=a['training_mask'];x=a['values'];recon=a['reconstruction_original'];raw_error=np.sqrt(np.mean((d-recon)**2,1))*100
            order=effect['order'];z=a['archetypes_original'][order];coefs=a['alpha'][:,order]
            curve_cache[row.trial_id]=z
            # Sólo las coordenadas de referencia necesarias para pares; las matrices de mezcla se releen por grupo.
            r=dict(**rec,is_selected=row.trial_id in best_ids,**{key:value for key,value in effect.items()
                if key not in ['order','curve_distances_pp','alpha_l1','reconstruction_difference_pp']})
            all_metrics=errors_summary(x,a['reconstruction'],d,recon,x[mask].mean(0))
            r.update(evaluation_rmse_pp=all_metrics['raw_rmse_pp'],evaluation_normalized_rmse=all_metrics['normalized_rmse'],
                train_rmse_pp=float(np.sqrt(np.mean(raw_error[mask]**2))),evaluation_n=len(f),
                error_p95_pp=float(np.quantile(raw_error,.95)),error_max_pp=float(raw_error.max()),
                oob_rmse_pp=float(np.sqrt(np.mean(raw_error[~mask]**2))) if (~mask).any() else None,
                oob_alpha_l1_mean=float(effect['alpha_l1'][~mask].mean()) if (~mask).any() else None,
                oob_alpha_l1_p95=float(np.quantile(effect['alpha_l1'][~mask],.95)) if (~mask).any() else None,
                oob_alpha_l1_max=float(effect['alpha_l1'][~mask].max()) if (~mask).any() else None,
                affine_rank=int(np.linalg.matrix_rank(z[1:]-z[0])))
            mix=mixture_statistics(coefs);r.update(dominated_fraction=float(mix.dominated.mean()),entropy_mean=float(mix.normalized_entropy.mean()),
                max_coefficient_median=float(mix.max_coefficient.median()),multiple_coefficients_fraction=float((mix.substantial_coefficients>=2).mean()))
            metrics.append(r)
            for j,index in enumerate(order):
                alignments.append(dict(trial_id=row.trial_id,reference_trial_id=reference[k]['trial_id'],reference_archetype=j,
                    original_archetype=int(index),distance_pp=float(effect['curve_distances_pp'][j])))
                contrast=curve_contrasts(z[[j]]).iloc[0].to_dict()
                for b,band in enumerate(BANDS):curves.append(dict(trial_id=row.trial_id,experiment=row.experiment,sample=row['sample'],scenario=row.scenario,
                    k=k,seed=row.seed,is_selected=row.trial_id in best_ids,archetype=j,age_band=band,delta_pp=float(z[j,b]*100),**contrast))
                weights=a['beta'][index];top=np.argsort(-weights,kind='stable')[:10];global_indices=np.flatnonzero(mask)[top]
                _,radial=extreme_mask(x[mask],f.loc[mask,'row_id'])
                keep,_=extreme_mask(x[mask],f.loc[mask,'row_id'])
                for rank,(local,global_index) in enumerate(zip(top,global_indices)):
                    source=f.iloc[global_index]
                    item=dict(trial_id=row.trial_id,experiment=row.experiment,sample=row['sample'],scenario=row.scenario,k=k,seed=row.seed,
                        is_selected=row.trial_id in best_ids,archetype=j,rank=rank+1,row_id=source.row_id,EDOCVE=source.EDOCVE,MPIOCVE=source.MPIOCVE,SEXO=source.SEXO,
                        weight=float(weights[local]),LN=int(source.LN),SV=int(source.SV),NV=int(source.NV),NS=int(source.NS),
                        min_sections=int(source.min_section_count),min_specified=int(source.min_specified_count),
                        radial_distance=float(radial[local]),radial_extreme=bool(not keep[local]),
                        concentration_equivalent=float(1/np.sum(weights**2)),top10_share=float(weights[top].sum()))
                    for b in range(3):
                        for col in ['LN','specified_count','NS','unspecified_rate','section_count','source_row_count']:
                            item[f'{col}_{b}']=source[f'{col}_{b}']
                    influence.append(item)
            if row.experiment=='fixed' and k==3:beta_stack.append(a['beta'][order])
            if row.trial_id in best_ids:
                mixture=f[['row_id',*KEYS,'LN','SV','NV','NS','specified_count','unspecified_rate','min_section_count','min_specified_count']].copy()
                mixture['is_training']=mask;mixture['is_oob']=~mask;mixture['rmse_pp']=raw_error
                mixture['aligned_alpha_l1']=effect['alpha_l1'];mixture['dominant_coefficient']=mix.max_coefficient
                mixture['dominated']=mix.dominated;mixture['normalized_entropy']=mix.normalized_entropy
                for j in range(k):mixture[f'alpha_{j}']=coefs[:,j]
                for b in range(3):mixture[f'reconstructed_delta_{b}']=recon[:,b]
                paths.append(self.table(f'selected/{row.trial_id}/observations.parquet',mixture))
                if row.experiment=='fixed':
                    status=pd.read_parquet(self.output/'reference/observation_status.parquet')
                    complete=status.merge(mixture[['row_id',*[f'alpha_{j}' for j in range(k)]]],on='row_id',how='left',validate='one_to_one')
                    paths.append(self.table(f'selected/fixed_k{k}/all_observations.parquet',complete))
                for scope,scope_mask in [('all',np.ones(len(f),bool)),('training',mask),('oob',~mask)]:
                    if not scope_mask.any():continue
                    labels={'sex':f.SEXO,'state':f.EDOCVE,'nominal_quartile':pd.qcut(f.LN,4,labels=False),
                        'high_ns':f.has_high_ns_coordinate,'few_sections':f.min_section_count<5}
                    for grouping,groups in labels.items():
                        for group in pd.unique(groups):
                            sel=scope_mask & np.asarray(groups==group)
                            if not sel.any():continue
                            group_rows.append(dict(trial_id=row.trial_id,experiment=row.experiment,sample=row['sample'],scenario=row.scenario,k=k,
                                scope=scope,grouping=grouping,group=str(group),profiles=int(sel.sum()),LN=int(f.loc[sel,'LN'].sum()),
                                rmse_pp=float(np.sqrt(np.mean(raw_error[sel]**2))),error_max_pp=float(raw_error[sel].max()),
                                alpha_l1_mean=float(effect['alpha_l1'][sel].mean()),alpha_l1_max=float(effect['alpha_l1'][sel].max()),
                                dominated_fraction=float(mix.dominated[sel].mean())))
                if row.experiment=='municipal':
                    for i in np.flatnonzero(~mask):individual.append(dict(trial_id=row.trial_id,sample=row['sample'],k=k,row_id=f.row_id.iloc[i],
                        alpha_l1=float(effect['alpha_l1'][i]),reconstruction_difference_pp=float(effect['reconstruction_difference_pp'][i]),rmse_pp=float(raw_error[i]),
                        **{f'alpha_{j}':float(coefs[i,j]) for j in range(k)}))
        m=pd.DataFrame(metrics);influence=pd.DataFrame(influence)
        for name,data in [('all_metrics',m),('archetype_curves',pd.DataFrame(curves)),('alignments',pd.DataFrame(alignments)),
            ('contributor_audit',influence),('grouped_metrics',pd.DataFrame(group_rows)),('oob_individual_changes',pd.DataFrame(individual))]:
            paths.append(self.table(f'diagnostics/{name}.parquet',data));paths.append(self.table(f'diagnostics/{name}.csv',data))
        # Dispersión de semillas y curva/reconstrucción para exactamente el mismo entrenamiento.
        grouping=catalog.groupby(['experiment','sample','scenario','k'],sort=False)
        for group,rows in grouping:
            require(len(rows)==10,'Se requieren diez soluciones por población/K.')
            best=choose_best(rows);ids=rows.trial_id.tolist()
            loaded={tid:self.arrays(rows[rows.trial_id==tid].iloc[0]) for tid in ids}
            pair_metrics=[]
            for left,right in itertools.combinations(ids,2):
                e=paired_effects(loaded[left],loaded[right]);lr=rows[rows.trial_id==left].iloc[0];rr=rows[rows.trial_id==right].iloc[0]
                entry=dict(experiment=group[0],sample=group[1],scenario=group[2],k=int(group[3]),left_trial=left,right_trial=right,
                    left_sse=float(lr.sse),right_sse=float(rr.sse),
                    left_excess_sse=float(lr.sse/best.sse-1),right_excess_sse=float(rr.sse/best.sse-1),
                    near_best_pair=bool(lr.sse<=best.sse*(1+CONFIG['near_best_sse_fraction']) and rr.sse<=best.sse*(1+CONFIG['near_best_sse_fraction'])),
                    max_curve_shift_pp=e['max_curve_shift_pp'],median_curve_shift_pp=e['median_curve_shift_pp'],
                    alpha_l1_mean=e['alpha_l1_mean'],reconstruction_difference_rmse_pp=e['reconstruction_difference_rmse_pp'])
                pairs.append(entry);pair_metrics.append(entry)
            pair_frame=pd.DataFrame(pair_metrics);near=rows.sse<=best.sse*(1+CONFIG['near_best_sse_fraction'])
            near_pairs=pair_frame[pair_frame.near_best_pair]
            budgets.append(dict(experiment=group[0],sample=group[1],scenario=group[2],k=int(group[3]),starts=len(rows),
                minimum_sse=float(best.sse),maximum_sse=float(rows.sse.max()),relative_sse_range=float(rows.sse.max()/best.sse-1),
                near_best_starts=int(near.sum()),near_best_max_curve_shift_pp=float(near_pairs.max_curve_shift_pp.max()) if len(near_pairs) else None,
                all_pair_max_curve_shift_pp=float(pair_frame.max_curve_shift_pp.max()),
                all_pair_median_curve_shift_pp=float(pair_frame.max_curve_shift_pp.median()),budget_hits=int((~rows.stopped_before_limit).sum()),
                different_curves_similar_reconstruction_pairs=int(((pair_frame.max_curve_shift_pp>CONFIG['curve_review_alert_pp']) &
                    (pair_frame.reconstruction_difference_rmse_pp<CONFIG['similar_reconstruction_alert_pp'])).sum())))
            if group[0] in ['fixed','municipal']:
                for count in range(1,11):
                    chosen=choose_best(rows.set_index('seed').loc[SEEDS[:count]].reset_index())
                    values=m[m.trial_id==chosen.trial_id].iloc[0]
                    prefixes.append(dict(experiment=group[0],sample=group[1],k=int(group[3]),starts=count,trial_id=chosen.trial_id,
                        seed=int(chosen.seed),sse=float(chosen.sse),raw_rmse_pp=float(chosen.raw_rmse_pp),oob_rmse_pp=values.oob_rmse_pp,
                        max_curve_shift_pp=values.max_curve_shift_pp,oob_alpha_l1_mean=values.oob_alpha_l1_mean))
        paths.append(self.table('diagnostics/same_training_pairs.parquet',pd.DataFrame(pairs)))
        paths.append(self.table('diagnostics/same_training_pairs.csv',pd.DataFrame(pairs)))
        paths.append(self.table('metadata/optimization_dispersion.csv',pd.DataFrame(budgets)))
        paths.append(self.table('metadata/start_budget_effects.csv',pd.DataFrame(prefixes)))
        variance=[]
        for k in [2,3]:
            tensor=[]
            for sample in range(10):
                rows=catalog[(catalog.experiment=='municipal')&(catalog['sample']==sample)&(catalog.k==k)].set_index('seed').loc[SEEDS]
                tensor.append(np.array([curve_cache[tid].ravel()*100 for tid in rows.trial_id]))
            variance.append(dict(k=k,samples=10,seeds=10,aligned_coordinates=k*3,**variance_partition(np.asarray(tensor))))
        paths.append(self.table('metadata/variance_partition.csv',pd.DataFrame(variance)))
        # Influencia sistemática con ceros explícitos de peso beta, no imputación de datos.
        stack=np.stack(beta_stack);mean=stack.mean(0);counts=(stack>1e-8).sum(0);influence_summary=[]
        for j in range(3):
            for index in np.argsort(-mean[j])[:20]:
                source=f.iloc[index];influence_summary.append(dict(archetype=j,row_id=source.row_id,mean_beta=float(mean[j,index]),
                    max_beta=float(stack[:,j,index].max()),starts_with_positive_weight=int(counts[j,index]),
                    starts_as_largest_contributor=int((stack[:,j,:].argmax(1)==index).sum()),LN=int(source.LN),
                    min_sections=int(source.min_section_count),min_specified=int(source.min_specified_count),high_ns=bool(source.has_high_ns_coordinate)))
        paths.append(self.table('metadata/fixed_influence_stability.csv',pd.DataFrame(influence_summary)))
        # Comparaciones emparejadas entre municipios y con el control K2 optimizado igual.
        selected=m[m.is_selected];oob=selected[selected.experiment=='municipal'].copy()
        two=oob[oob.k==2].set_index('sample');three=oob[oob.k==3].set_index('sample')
        comparisons=pd.DataFrame(dict(sample=two.index,k2_oob_rmse_pp=two.oob_rmse_pp,k3_oob_rmse_pp=three.oob_rmse_pp,
            reduction_pp=two.oob_rmse_pp-three.oob_rmse_pp,relative_reduction=1-three.oob_rmse_pp/two.oob_rmse_pp))
        paths.append(self.table('metadata/paired_oob_comparison.csv',comparisons))
        prefix=pd.DataFrame(prefixes);comparison=[]
        for k in [2,3]:
            for starts in [1,10]:
                g=prefix[(prefix.experiment=='municipal')&(prefix.k==k)&(prefix.starts==starts)]
                comparison.append(dict(k=k,starts=starts,samples=len(g),oob_rmse_median_pp=float(g.oob_rmse_pp.median()),oob_rmse_max_pp=float(g.oob_rmse_pp.max()),
                    max_curve_shift_median_pp=float(g.max_curve_shift_pp.median()),max_curve_shift_max_pp=float(g.max_curve_shift_pp.max()),
                    alpha_oob_l1_median=float(g.oob_alpha_l1_mean.median()),alpha_oob_l1_max=float(g.oob_alpha_l1_mean.max())))
        paths.append(self.table('metadata/start_protocol_comparison.csv',pd.DataFrame(comparison)))
        # Uniones de reglas sin expansión: una firma por municipio×sexo.
        rules=pd.read_parquet(self.output/'reference/rule_segments.parquet')
        core=rules[rules.age_band.isin(BANDS)&rules.SEXO.isin(['0','1'])]
        pivot=core.pivot(index=KEYS,columns='age_band',values='candidate_id').reset_index()
        joined=f.merge(pivot,on=KEYS,sort=False,validate='one_to_one')
        require(len(joined)==4571 and joined.row_id.equals(f.row_id) and joined[BANDS].notna().all().all(),'Unión con reglas incorrecta.')
        joined['rule_signature']=joined[BANDS].astype(str).agg(' / '.join,axis=1)
        main=ref_arrays[3];level=d.mean(1);q=d@np.asarray(self.scaler()['basis'])
        joined['relative_level']=level;joined['shape_contrast_1']=q[:,0];joined['shape_contrast_2']=q[:,1]
        for j in range(3):joined[f'alpha_{j}']=main['alpha'][:,j]
        paths.append(self.table('comparisons/rules_and_continuous_indicators.parquet',joined))
        signature_rows=[]
        for signature,g in joined.groupby('rule_signature'):
            signature_rows.append(dict(signature=signature,profiles=len(g),municipalities=g.groupby(MUNICIPAL_KEYS).ngroups,
                max_alpha_range=float(g[[f'alpha_{j}' for j in range(3)]].max().sub(g[[f'alpha_{j}' for j in range(3)]].min()).max()),
                level_range_pp=float(np.ptp(g.relative_level)*100),shape_1_range_pp=float(np.ptp(g.shape_contrast_1)*100),shape_2_range_pp=float(np.ptp(g.shape_contrast_2)*100)))
        paths.append(self.table('comparisons/rule_signature_variation.csv',pd.DataFrame(signature_rows)))
        indicator_audit=[]
        exact=level[:,None]+q@np.asarray(self.scaler()['basis']).T
        require(np.max(abs(d-exact))<1e-12,'Nivel/forma no conservan d.')
        for j in range(3):
            for name,values in [('relative_level',level),('shape_contrast_1',q[:,0]),('shape_contrast_2',q[:,1])]:
                indicator_audit.append(dict(archetype=j,indicator=name,spearman=float(pd.Series(main['alpha'][:,j]).corr(pd.Series(values),method='spearman'))))
        paths.append(self.table('comparisons/mixture_indicator_correlations.csv',pd.DataFrame(indicator_audit)))
        write_json(self.output/'comparisons/information_identity.json',dict(max_original_reconstruction_error=float(np.max(abs(d-exact))),
            original_dimensions=3,indicator_dimensions=3,alpha_free_dimensions_k3=2,
            interpretation='Nivel y dos contrastes conservan exactamente d. AA es una transformación aprendida y con pérdida, sin nuevas observaciones. Error cero de la identidad no compara modelos con la misma complejidad.',
            fixed_reference_conditional_raw_indicator_change=0.0))
        paths.append(self.output/'comparisons/information_identity.json')
        # Juicio metodológico explícito, sustentado en reconstrucción e influencia; no un test oficial.
        summary=pd.DataFrame(comparison);final3=summary[(summary.k==3)&(summary.starts==10)].iloc[0]
        e3=selected[selected.scenario.str.startswith('E3')]
        fixed_pairs=pd.DataFrame(budgets);fixed3=fixed_pairs[(fixed_pairs.experiment=='fixed')&(fixed_pairs.k==3)].iloc[0]
        largest_beta=float(influence[(influence.trial_id==reference[3]['trial_id'])&(influence['rank']==1)].weight.max())
        decision=dict(option='B',title='Utilizar indicadores continuos sin arquetipos',
            basis=dict(oob_rmse_median_k3=float(final3.oob_rmse_median_pp),municipal_curve_shift_max_pp=float(final3.max_curve_shift_max_pp),
                fixed_seed_curve_shift_max_pp=float(fixed3.all_pair_max_curve_shift_pp),individual_exclusion_curve_shift_max_pp=float(e3.max_curve_shift_pp.max()),
                largest_construction_weight=largest_beta,median_oob_reduction_pp=float(comparisons.reduction_pp.median())),
            reasoning='La reconstrucción puede mejorar sin identificar extremos reproducibles. Los indicadores existentes conservan toda la información numérica y no dependen de perfiles ancla. AA permanece como evidencia técnica; no sustituye los seis perfiles.',
            operational_alert_pp=CONFIG['curve_review_alert_pp'],official_threshold=False,
            no_user_communication_efficacy_study=True)
        write_json(self.output/'metadata/decision.json',decision);paths.append(self.output/'metadata/decision.json')
        self.checkpoint('e',paths,started,dict(initializations=len(catalog),new=int((~catalog.reused).sum()),reused=int(catalog.reused.sum()),decision=decision))

    def run(self,stop_after='f'):
        if (self.output/'_SUCCESS').exists():self.verify_success();return
        for stage in 'abcdef':
            if self.valid_stage(stage):print('Checkpoint verificado: '+stage,flush=True)
            else:getattr(self,'stage_'+stage)()
            if stage==stop_after:break
        if stop_after=='f':self.finalize()

    def refresh_report(self):
        """Revisa únicamente la entrega actual; preserva cada ajuste verificado."""
        for stage in 'abcde':require(self.valid_stage(stage),'Se requieren etapas A–E íntegras para revisar el informe.')
        archive=self.output/'revisions'/f'render_{time.time_ns()}'
        require(archive.resolve().is_relative_to(self.root.resolve()),'Archivo de revisión fuera del proyecto.')
        archive.mkdir(parents=True)
        for path in [self.report,self.output/'metadata/checkpoint_f.json',self.output/'metadata/run_manifest.json',self.output/'_SUCCESS']:
            require(path.resolve().is_relative_to(self.root.resolve()),'Destino fuera del proyecto.')
            if path.exists():path.replace(archive/path.name)
        write_json(archive/'revision.json',dict(time=utc(),reason='Precisiones del informe propio; cero reajustes.'))
        self.state['status']='running';write_json(self.state_path,self.state)

    def figure(self,name,figure,paths):
        figure.tight_layout();path=self.charts/name;save_figure(figure,path);paths.append(path)

    def plot_diagnostics(self):
        paths=[];colors=plt.get_cmap('tab10').colors
        curves=pd.read_parquet(self.output/'diagnostics/archetype_curves.parquet')
        metrics=pd.read_parquet(self.output/'diagnostics/all_metrics.parquet')
        fixed=metrics[(metrics.experiment=='fixed')&(metrics.k==3)]
        reference=fixed[fixed.is_selected].iloc[0];ref=self.arrays(reference)
        fixed_curves=curves[(curves.experiment=='fixed')&(curves.k==3)]
        fig,axes=plt.subplots(1,3,figsize=(14,4))
        for j,ax in enumerate(axes):
            for index,(_,r) in enumerate(fixed.iterrows()):
                g=fixed_curves[(fixed_curves.trial_id==r.trial_id)&(fixed_curves.archetype==j)].set_index('age_band').loc[BANDS]
                ax.plot(BANDS,g.delta_pp,color=colors[index],alpha=.8,lw=2 if r.is_selected else 1,
                    linestyle='-' if r.sse<=fixed.sse.min()*1.01 else '--',label=f'Semilla {int(r.seed)}')
            ax.axhline(0,lw=.6,color='grey');ax.set(title=f'Arquetipo alineado {j}',xlabel='Intervalo',ylabel='Diferencia frente a pares (pp)')
        axes[-1].legend(fontsize=6,ncol=2);fig.suptitle('Datos fijos: diez inicializaciones; discontinua = SSE >1 % sobre la mejor')
        self.figure('fixed_initialization_curves.png',fig,paths)
        fig,axes=plt.subplots(1,3,figsize=(14,4))
        municipal=curves[(curves.experiment=='municipal')&curves.is_selected&(curves.k==3)]
        for j,ax in enumerate(axes):
            for sample in range(10):
                g=municipal[(municipal['sample']==sample)&(municipal.archetype==j)].set_index('age_band').loc[BANDS]
                ax.plot(BANDS,g.delta_pp,color=colors[sample],alpha=.7,label=f'Muestra {sample}')
            ax.plot(BANDS,ref['archetypes_original'][j]*100,'k--',lw=2,label='Referencia completa')
            ax.set(title=f'Arquetipo alineado {j}',xlabel='Intervalo',ylabel='Diferencia frente a pares (pp)')
        axes[-1].legend(fontsize=6,ncol=2);fig.suptitle('Municipios: mejor SSE entre diez arranques por muestra; no sólo una semilla')
        self.figure('municipal_multistart_curves.png',fig,paths)
        paired=pd.read_csv(self.output/'metadata/paired_oob_comparison.csv');fig,axes=plt.subplots(1,2,figsize=(11,4))
        axes[0].plot(paired['sample'],paired.k2_oob_rmse_pp,'o-',label='K=2 · diez arranques')
        axes[0].plot(paired['sample'],paired.k3_oob_rmse_pp,'s-',label='K=3 · diez arranques')
        axes[0].set(xlabel='Submuestra municipal',ylabel='RMSE fuera de entrenamiento (pp)');axes[0].legend(fontsize=8)
        axes[1].bar(paired['sample'],paired.reduction_pp,color=colors[2]);axes[1].set(xlabel='La misma submuestra',ylabel='Reducción de RMSE K2−K3 (pp)')
        fig.suptitle('Reconstrucción OOB emparejada; selección sólo por SSE de entrenamiento')
        self.figure('paired_oob_error.png',fig,paths)
        contributors=pd.read_parquet(self.output/'diagnostics/contributor_audit.parquet')
        top=contributors[(contributors.experiment=='fixed')&(contributors.k==3)&(contributors['rank']==1)]
        fig,axes=plt.subplots(1,2,figsize=(12,4))
        for j in range(3):
            g=top[top.archetype==j].set_index('seed').loc[SEEDS]
            axes[0].plot(np.arange(10),g.weight,'o-',label=f'Arquetipo {j}',color=colors[j])
            axes[1].plot(np.arange(10),g.concentration_equivalent,'o-',label=f'Arquetipo {j}',color=colors[j])
        for ax in axes:ax.set_xticks(np.arange(10),[str(s) for s in SEEDS],rotation=45);ax.legend(fontsize=8);ax.set_xlabel('Semilla · población fija')
        axes[0].set_ylabel('Mayor peso de construcción β');axes[1].set_ylabel('Concentración equivalente 1/Σβ²')
        fig.suptitle('Dependencia de aportantes; concentración no equivale a personas o tamaño muestral')
        self.figure('extreme_contributor_concentration.png',fig,paths)
        sens=curves[(curves.experiment=='sensitivity')&curves.is_selected];fig,axes=plt.subplots(1,3,figsize=(14,4))
        names={'E1':'Excluir cola 1 %','E2':'NS y secciones',**{f'E3_archetype{j}':f'Excluir aportante A{j}' for j in range(3)}}
        for j,ax in enumerate(axes):
            ax.plot(BANDS,ref['archetypes_original'][j]*100,'k--',lw=2,label='E0: todos')
            for index,(scenario,g) in enumerate(sens[sens.archetype==j].groupby('scenario')):
                g=g.set_index('age_band').loc[BANDS];ax.plot(BANDS,g.delta_pp,'o-',color=colors[index],alpha=.8,label=names[scenario])
            ax.set(title=f'Arquetipo alineado {j}',xlabel='Intervalo',ylabel='Participación relativa (pp)')
        axes[-1].legend(fontsize=6);fig.suptitle('Sensibilidades de entrenamiento: mejor de diez arranques; todas las filas se conservan')
        self.figure('exclusion_sensitivity_curves.png',fig,paths)
        fig,axes=plt.subplots(1,2,figsize=(11,4));mix=mixture_statistics(ref['alpha'])
        for j in range(3):axes[0].hist(ref['alpha'][:,j],bins=35,histtype='step',label=f'A{j}',color=colors[j])
        axes[0].set(xlabel='Coeficiente convexo',ylabel='Perfiles municipio–sexo');axes[0].legend()
        axes[1].hist(mix.max_coefficient,bins=35,color=colors[2],alpha=.7);axes[1].axvline(.8,color='black',ls='--',label='Umbral descriptivo 0.8')
        axes[1].set(xlabel='Coeficiente máximo del perfil',ylabel='Perfiles');axes[1].legend(fontsize=8)
        fig.suptitle('Mezclas de la referencia K3; coeficientes no son probabilidades de votar')
        self.figure('mixture_distributions.png',fig,paths)
        changes=pd.read_parquet(self.output/'diagnostics/oob_individual_changes.parquet');g=changes[changes.k==3]
        prefix=pd.read_csv(self.output/'metadata/start_budget_effects.csv')
        fig,axes=plt.subplots(1,2,figsize=(12,4))
        for starts in [1,10]:
            gg=prefix[(prefix.experiment=='municipal')&(prefix.k==3)&(prefix.starts==starts)]
            axes[0].plot(gg['sample'],gg.oob_alpha_l1_mean,'o-',label=f'{starts} arranque(s)')
        axes[0].set(xlabel='Submuestra municipal',ylabel='Cambio L1 medio de coeficientes OOB');axes[0].legend()
        axes[1].hist(g.alpha_l1,bins=50,color=colors[3]);axes[1].set(xlabel='Cambio L1 por perfil OOB · diez arranques',ylabel='Evaluaciones OOB de perfiles')
        fig.suptitle('Cambio de mezclas frente a referencia completa fija; repeticiones OOB no son personas')
        self.figure('municipal_coefficient_changes.png',fig,paths)
        worst=g.sort_values('alpha_l1',ascending=False).drop_duplicates('row_id').head(3)
        profile=self.frame().set_index('row_id');fig,axes=plt.subplots(2,3,figsize=(14,8))
        for col,(_,r) in enumerate(worst.iterrows()):
            case=profile.loc[r.row_id];index=int(np.flatnonzero(self.frame().row_id.eq(r.row_id))[0])
            trial=metrics[metrics.trial_id==r.trial_id].iloc[0];arr=self.arrays(trial);effect=paired_effects(ref,arr)
            alpha=arr['alpha'][index,effect['order']];bottom=np.zeros(2)
            for j in range(3):
                vals=[ref['alpha'][index,j],alpha[j]];axes[0,col].bar([0,1],vals,bottom=bottom,color=colors[j],label=f'A{j}');bottom+=vals
            axes[0,col].set_xticks([0,1],['Referencia','OOB']);axes[0,col].set(ylabel='Coeficiente',title=f'{case.EDOCVE}/{case.MPIOCVE} · sexo {case.SEXO}\nL1={r.alpha_l1:.3f} · muestra {int(r["sample"])}')
            observed=case[[f'delta_{j}' for j in range(3)]].to_numpy(float)
            axes[1,col].plot(BANDS,observed*100,'ko-',label='Observado')
            axes[1,col].plot(BANDS,ref['reconstruction_original'][index]*100,'s--',label='Reconstrucción completa')
            axes[1,col].plot(BANDS,arr['reconstruction_original'][index]*100,'^--',label='Reconstrucción OOB')
            axes[1,col].set(xlabel='Intervalo',ylabel='Diferencia frente a pares (pp)');axes[1,col].legend(fontsize=7)
        axes[0,-1].legend(fontsize=7);fig.suptitle('Tres casos reales con mayor cambio de mezcla; comparar también sus reconstrucciones')
        self.figure('most_unstable_observations.png',fig,paths)
        fig,axes=plt.subplots(1,2,figsize=(11,4));z=ref['archetypes_original']*100
        for j in range(3):axes[0].plot(BANDS,z[j],'o-',label=f'Arquetipo {j}',color=colors[j])
        axes[0].axhline(0,color='grey',lw=.8);axes[0].set(xlabel='Intervalo',ylabel='Diferencia absoluta frente a pares (pp)');axes[0].legend()
        for j in range(3):axes[1].plot(BANDS,z[j]-z[j].mean(),'o-',label=f'A{j}: nivel {z[j].mean():+.1f} pp',color=colors[j])
        axes[1].axhline(0,color='grey',lw=.8);axes[1].set(xlabel='Intervalo',ylabel='Forma centrada del arquetipo (pp)');axes[1].legend(fontsize=8)
        fig.suptitle('Nivel y forma: descripción agregada, sin motivaciones individuales inferidas')
        self.figure('electoral_level_and_shape.png',fig,paths)
        rules=pd.read_csv(self.output/'comparisons/rule_signature_variation.csv').sort_values('profiles',ascending=False)
        fig,axes=plt.subplots(1,2,figsize=(12,4));positions=np.arange(len(rules))
        axes[0].bar(positions,rules.max_alpha_range,color=colors[0]);axes[0].set(xlabel='Firma de tres reglas (orden por frecuencia)',ylabel='Mayor rango de un coeficiente')
        axes[1].bar(positions,rules.level_range_pp,label='Nivel',color=colors[1]);axes[1].plot(positions,rules.shape_1_range_pp,'o-',label='Forma 1');axes[1].plot(positions,rules.shape_2_range_pp,'s-',label='Forma 2')
        axes[1].set(xlabel='La misma firma por municipio–sexo',ylabel='Rango de indicadores continuos (pp)');axes[1].legend()
        for ax in axes:ax.set_xticks(positions,[f'F{i+1}' for i in positions])
        fig.suptitle('Variación dentro de iguales reglas: mezclas e indicadores existentes; unidades diferentes en cada panel')
        self.figure('rule_profiles_and_simple_indicators.png',fig,paths)
        fig,axes=plt.subplots(1,2,figsize=(12,4));partition=pd.read_csv(self.output/'metadata/variance_partition.csv')
        axes[0].bar(partition.k,partition.within_seed_pp2,label='Entre semillas del mismo entrenamiento',color=colors[0])
        axes[0].bar(partition.k,partition.between_sample_means_pp2,bottom=partition.within_seed_pp2,label='Entre medias de muestras',color=colors[1])
        axes[0].set(xlabel='K',ylabel='Dispersión alineada (pp² por coordenada)');axes[0].legend(fontsize=7)
        axes[1].scatter(fixed.sse,fixed.max_curve_shift_pp,c=np.arange(10),cmap='viridis')
        for _,r in fixed.iterrows():axes[1].annotate(str(int(r.seed)),(r.sse,r.max_curve_shift_pp),fontsize=6)
        axes[1].set(xlabel='SSE con población fija',ylabel='Desplazamiento máximo frente a referencia (pp)')
        fig.suptitle('Optimización y muestras: descomposición descriptiva, sin atribución causal')
        self.figure('optimization_vs_municipal_variation.png',fig,paths)
        pairs=pd.read_parquet(self.output/'diagnostics/same_training_pairs.parquet');pairs=pairs[pairs.k==3]
        fig,ax=plt.subplots(figsize=(8,5))
        for kind,label in [('fixed','Datos fijos'),('municipal','Dentro de la misma muestra municipal'),('sensitivity','Dentro del mismo escenario E')]:
            gg=pairs[pairs.experiment==kind];ax.scatter(gg.reconstruction_difference_rmse_pp,gg.max_curve_shift_pp,s=12,alpha=.5,label=label)
        ax.axvline(1,color='grey',ls='--');ax.axhline(5,color='grey',ls='--')
        ax.set(xlabel='Diferencia RMS entre reconstrucciones (pp)',ylabel='Mayor distancia de curvas alineadas (pp)',title='Curvas diferentes pueden producir reconstrucciones próximas');ax.legend(fontsize=8)
        self.figure('curve_reconstruction_equivalence.png',fig,paths)
        fig,axes=plt.subplots(1,2,figsize=(12,4))
        for k in [2,3]:
            gg=prefix[(prefix.experiment=='municipal')&(prefix.k==k)]
            med=gg.groupby('starts').max_curve_shift_pp.median();axes[0].plot(med.index,med,'o-',label=f'K={k}')
            er=gg.groupby('starts').oob_rmse_pp.median();axes[1].plot(er.index,er,'o-',label=f'K={k}')
        axes[0].set(xlabel='Arranques disponibles en orden predefinido',ylabel='Mediana del máximo desplazamiento de curvas (pp)')
        axes[1].set(xlabel='Arranques disponibles',ylabel='RMSE OOB mediano (pp)')
        for ax in axes:ax.legend();ax.set_xticks(range(1,11))
        fig.suptitle('Presupuesto de arranques: selecciona por SSE de entrenamiento, nunca por estas curvas OOB')
        self.figure('initialization_budget_effects.png',fig,paths)
        return paths

    def stage_f(self):
        started=time.monotonic();paths=self.plot_diagnostics()
        tests=subprocess.run([sys.executable,'-m','unittest','discover','-s','analysis/scripts','-p','test_validate_archetypal_stability.py'],
            cwd=self.root,capture_output=True,text=True,encoding='utf8')
        tp=self.output/'metadata/automated_tests.json';write_json(tp,dict(returncode=tests.returncode,stdout=tests.stdout,stderr=tests.stderr,time=utc()));paths.append(tp)
        require(tests.returncode==0,'Fallaron pruebas: '+tests.stderr)
        self.write_report();paths.append(self.report)
        self.checkpoint('f',paths,started,dict(charts=len(list(self.charts.glob('*.png'))),tests='passed',report=str(self.report)))

    def write_report(self):
        metrics=pd.read_parquet(self.output/'diagnostics/all_metrics.parquet')
        fixed=metrics[(metrics.experiment=='fixed')&(metrics.k==3)].sort_values('sse').copy()
        fixed['excess_sse_fraction']=fixed.sse/fixed.sse.min()-1
        fixed['geometry_rmse']=np.sqrt(fixed.sse/(fixed.training_profiles*3))
        best=fixed[fixed.is_selected].iloc[0];ref=self.arrays(best)
        f=self.frame();d=f[[f'delta_{j}' for j in range(3)]].to_numpy(float)
        protocols=pd.read_csv(self.output/'metadata/start_protocol_comparison.csv')
        before=protocols[(protocols.k==3)&(protocols.starts==1)].iloc[0]
        after=protocols[(protocols.k==3)&(protocols.starts==10)].iloc[0]
        control=protocols[(protocols.k==2)&(protocols.starts==10)].iloc[0]
        variance=pd.read_csv(self.output/'metadata/variance_partition.csv');part=variance[variance.k==3].iloc[0]
        dispersion=pd.read_csv(self.output/'metadata/optimization_dispersion.csv')
        fixeddisp=dispersion[(dispersion.experiment=='fixed')&(dispersion.k==3)].iloc[0]
        near=dispersion[(dispersion.experiment=='municipal')&(dispersion.k==3)]
        pair=pd.read_parquet(self.output/'diagnostics/same_training_pairs.parquet')
        fixed_pairs=pair[(pair.experiment=='fixed')&(pair.k==3)]
        centrality=[]
        for _,r in fixed.iterrows():
            relevant=fixed_pairs[(fixed_pairs.left_trial==r.trial_id)|(fixed_pairs.right_trial==r.trial_id)]
            centrality.append(dict(trial_id=r.trial_id,seed=int(r.seed),sse=float(r.sse),
                mean_pair_curve_shift_pp=float(relevant.max_curve_shift_pp.mean()),
                median_pair_curve_shift_pp=float(relevant.max_curve_shift_pp.median()),
                maximum_pair_curve_shift_pp=float(relevant.max_curve_shift_pp.max())))
        centrality=pd.DataFrame(centrality)
        self.table('metadata/fixed_seed_centrality.csv',centrality)
        rho=float(centrality.sse.corr(centrality.mean_pair_curve_shift_pp,method='spearman'))
        central_best=centrality[centrality.trial_id==best.trial_id].iloc[0]
        equivalent=pair[(pair.k==3)&(pair.max_curve_shift_pp>5)&(pair.reconstruction_difference_rmse_pp<1)].sort_values('max_curve_shift_pp',ascending=False)
        equivalent_near=equivalent[equivalent.near_best_pair]
        selected=metrics[metrics.is_selected].copy();sens=selected[selected.experiment=='sensitivity'].sort_values('scenario')
        municipal=selected[(selected.experiment=='municipal')&(selected.k==3)].sort_values('sample')
        paired=pd.read_csv(self.output/'metadata/paired_oob_comparison.csv')
        influence=pd.read_parquet(self.output/'diagnostics/contributor_audit.parquet')
        contributors=influence[(influence.trial_id==best.trial_id)&(influence['rank']<=3)&(influence.weight>1e-12)].copy()
        biggest=contributors[contributors['rank']==1]
        top_stability=pd.read_csv(self.output/'metadata/fixed_influence_stability.csv')
        top_stability=top_stability[top_stability.mean_beta>1e-12]
        curves=pd.read_parquet(self.output/'diagnostics/archetype_curves.parquet')
        maincurves=curves[curves.trial_id==best.trial_id]
        maincontrasts=maincurves.drop_duplicates('archetype')[['archetype','level_pp','young_minus_older_pp','adult_minus_endpoint_mean_pp','shape_range_pp']]
        mix=mixture_statistics(ref['alpha']);cov=pd.read_parquet(self.output/'metadata/sample_coverage.parquet')
        changes=pd.read_parquet(self.output/'diagnostics/oob_individual_changes.parquet')
        maximum_individual_oob=float(changes.loc[changes.k==3,'rmse_pp'].max())
        worst=changes[changes.k==3].sort_values('alpha_l1',ascending=False).drop_duplicates('row_id').head(5)
        groups=pd.read_parquet(self.output/'diagnostics/grouped_metrics.parquet')
        sex=groups[(groups.trial_id==best.trial_id)&(groups.scope=='all')&(groups.grouping=='sex')]
        quality=groups[(groups.trial_id==best.trial_id)&(groups.scope=='all')&groups.grouping.isin(['high_ns','few_sections'])]
        risks=metrics[~metrics.stopped_before_limit]
        cat=pd.read_parquet(self.output/'metadata/all_initializations.parquet')
        rules=pd.read_parquet(self.output/'comparisons/rules_and_continuous_indicators.parquet')
        signatures=pd.read_csv(self.output/'comparisons/rule_signature_variation.csv')
        simple=json.loads((self.output/'comparisons/information_identity.json').read_text())
        positives=[]
        for j in range(3):
            g=curves[(curves.experiment=='municipal')&curves.is_selected&(curves.k==3)&(curves.archetype==j)].drop_duplicates('trial_id')
            positives.append(dict(archetype=j,level_min_pp=float(g.level_pp.min()),level_max_pp=float(g.level_pp.max()),
                young_older_min_pp=float(g.young_minus_older_pp.min()),young_older_max_pp=float(g.young_minus_older_pp.max())))
        # Resumen del alcance temporal de cada escenario, sin sumar vistas.
        scenario_rows=[dict(scenario='E0',seed=int(best.seed),training_profiles=4571,training_municipalities=2296,LN_training=98119426,
            evaluation_profiles=4571,evaluation_rmse_pp=float(best.evaluation_rmse_pp),max_curve_shift_pp=0.,alpha_l1_mean=0.,alpha_l1_p95=0.,alpha_l1_max=0.)]
        for _,r in sens.iterrows():scenario_rows.append(dict(scenario=r.scenario,seed=int(r.seed),training_profiles=int(r.training_profiles),
            training_municipalities=int(r.training_municipalities),LN_training=int(r.LN_training),evaluation_profiles=4571,
            evaluation_rmse_pp=float(r.evaluation_rmse_pp),max_curve_shift_pp=float(r.max_curve_shift_pp),
            alpha_l1_mean=float(r.alpha_l1_mean),alpha_l1_p95=float(r.alpha_l1_p95),alpha_l1_max=float(r.alpha_l1_max)))
        scenario_table=pd.DataFrame(scenario_rows)
        self.table('metadata/final_scenario_summary.csv',scenario_table)
        self.table('metadata/final_fixed_review.csv',fixed)
        self.table('metadata/contrast_stability.csv',pd.DataFrame(positives))
        self.table('metadata/worst_individual_cases.csv',worst)
        self.table('metadata/similar_reconstruction_examples.csv',equivalent_near.head(10))
        e1=sens[sens.scenario=='E1'].iloc[0];e2=sens[sens.scenario=='E2'].iloc[0]
        e3=sens[sens.scenario.str.startswith('E3')]
        signature=signatures[signatures.profiles>=10].sort_values('max_alpha_range',ascending=False).iloc[0].signature
        same=rules[rules.rule_signature==signature]
        column=max([f'alpha_{j}' for j in range(3)],key=lambda c:np.ptp(same[c]))
        cases=same.loc[[same[column].idxmin(),same[column].idxmax()],['row_id',*KEYS,'rule_signature','relative_level','shape_contrast_1','shape_contrast_2','alpha_0','alpha_1','alpha_2']]
        self.table('comparisons/same_rules_real_examples.csv',cases)
        # Distancia al centro / cola y metadatos completos para los aportantes del principal.
        detailed=contributors[['archetype','rank','row_id',*KEYS,'weight','LN',
            *[f'specified_count_{j}' for j in range(3)],*[f'NS_{j}' for j in range(3)],*[f'section_count_{j}' for j in range(3)],
            'radial_distance','radial_extreme','concentration_equivalent']]
        chart=lambda name:f'![{name.replace("_"," ")}]({os.path.relpath(self.charts/(name+".png"),self.report.parent).replace(chr(92),"/")})'
        near_text=(f'El mayor desplazamiento entre soluciones a ≤1 % de la mejor SSE de su muestra es {near.near_best_max_curve_shift_pp.max():.2f} pp.'
            if near.near_best_max_curve_shift_pp.notna().any() else 'No hay pares suficientes dentro de 1 % del mejor objetivo para estimar esa dispersión.')
        lines=[]
        for _,r in maincontrasts.iterrows():
            lines.append(f'- A{int(r.archetype)}: nivel medio {r.level_pp:+.2f} pp, contraste joven−mayor {r.young_minus_older_pp:+.2f} pp y curvatura adulta {r.adult_minus_endpoint_mean_pp:+.2f} pp. Son diferencias agregadas frente a pares, no motivaciones.')
        report=f'''# Validación final de estabilidad de arquetipos electorales · 2024

**Recomendación B: utilizar indicadores continuos sin arquetipos como complemento de los seis perfiles por reglas.** Diez arranques estabilizan parte del ajuste AA2 K3 y mantienen su ventaja de reconstrucción frente a K2. Persisten cambios de curvas de hasta **{after.max_curve_shift_max_pp:.2f} pp** entre muestras y hasta **{e2.max_curve_shift_pp:.2f} pp** al cambiar los criterios de calidad. Los indicadores de nivel y forma ya conservan toda la información medida y permiten explicar esos gradientes sin elegir extremos aprendidos. AA queda en la documentación técnica; no se integra a React ni sustituye los seis perfiles principales.

Esta decisión reconoce una mejora real: excluir individualmente los tres mayores aportantes cambia curvas sólo hasta **{e3.max_curve_shift_pp.max():.2f} pp**. La concentración β no demuestra por sí misma que un único registro sea indispensable o erróneo. El límite principal de comunicación es la variación residual de extremos, la optimización y la utilidad adicional no demostrada frente a los indicadores existentes.

## Recuperación, datos y alcance

Se revisaron archetypal_pattern_review.md, profile_candidates_review.md, participation_pattern_review.md y age_band_representation_review.md, junto con rutas reales, contratos, _SUCCESS, manifiestos, checkpoints y modelos. Se conservaron los **138 ajustes del experimento anterior**; {int(cat.reused.sum())} ajustes exactamente compatibles se reutilizan por referencias y hashes, sin volver a entrenarlos. Esta revisión reúne **{len(cat)} resultados de inicialización: {int((~cat.reused).sum())} nuevos y {int(cat.reused.sum())} reutilizados**. No se reprocesaron CSV ni registros individuales.

El universo es idéntico en todas las comparaciones principales: **4,571 perfiles municipio×sexo**, **2,296 municipios**, LN=98,119,426 (**99.7855 % del LN nacional reportado**). Las coordenadas corresponden a 18–34, 35–59 y 60–100 años; no edad media. Se exige LN≥100, SV+NV≥100 y filas fuente≥5 en cada banda. Edad, sexo y claves territoriales se conservan como metadatos, no magnitudes de distancia. No se ensayan K4, K5, K6 ni variables nuevas.

La referencia conserva 4,954 perfiles H/M disponibles, incluidos 383 fuera de la población común. Las 77 filas elegibles bajo tres bandas pero fuera del universo común siguen explícitas. La referencia broad completa conserva los 17,735 segmentos y todos los conteos de 2024, incluidos 101+ y SEXO=2 (105 filas fuente/LN). Los pendientes mantienen coeficientes NULL: no se imputan, no se borran datos y no se suman vistas alternativas.

Las tasas son SV/(SV+NV), NULL si el denominador es cero; NS no es abstención. La referencia nacional por banda/sexo utiliza todos los conteos antes de soporte y permanece fija. AA2 descompone d en nivel m y forma ortonormal q; centra/escala cada bloque por entrenamiento y reparte 50/50 su varianza. No se añade información ni se duplica una dimensión. El peso es uno por perfil municipio×sexo: un municipio con ambos sexos aporta dos filas, sin asumir independencia; no se pondera automáticamente por LN.

## Entorno y protocolo de optimización

Se utiliza .venv_archetypal_patterns, Python 3.13, archetypes {self.dependencies['imports']['archetypes']}, sklearn {self.dependencies['imports']['sklearn']}, NumPy {self.dependencies['imports']['numpy']}; pip check y prueba sintética pasan. No se instala ni modifica ninguna dependencia. Se reutilizan las funciones geométricas y validaciones del [experimento anterior](archetypal_pattern_review.md), sin ejecutar su programa principal.

Semillas predefinidas, en orden: **{', '.join(str(v) for v in SEEDS)}**. Cada ajuste usa n_init=1, inicializador nativo random, máximo300 iteraciones y tolerancia absoluta1e−4 de la norma de Frobenius. Diez ajustes independientes constituyen cada protocolo de múltiples arranques. K2 recibe el mismo presupuesto que K3. Se guarda todo, incluidos arranques desfavorables y límites de iteración: hubo **{len(risks)}** resultados que alcanzaron300, conservados con bandera; {int(((risks.experiment=='municipal')&risks.is_selected).sum())} fueron seleccionados en muestras municipales. No se certifica convergencia global.

La versión instalada expone alphas_, betas_ y archetypes_; transform recalcula α sobre arquetipos finales. Se verifican α≥0, β≥0, sumas de fila uno, Z=βX, dimensiones, reconstrucciones e inversión afín con tolerancia1e−8. rss_ nativo no es SSE: todas las SSE y RMSE se recomputan. Se selecciona **sólo la menor SSE geométrica de entrenamiento**, desempate por semilla, sin consultar OOB ni atractivo visual. La RMSE original en pp no es el mismo objetivo que la SSE geométrica AA2: ordenar por ambas puede diferir.

Para curvas y coeficientes se fija una referencia completa por K, elegida entre los diez arranques por esa misma SSE. Se alinea mediante Hungarian con RMS entre curvas originales, únicamente K×K, nunca N×N. **El desplazamiento de cada curva es RMS de sus tres bandas en pp; el máximo informado toma el mayor RMS entre arquetipos, no la mayor diferencia puntual de una banda.** Las permutaciones, coeficientes originales/alineados y referencias se conservan. α describe una reconstrucción convexa, no probabilidad de votar ni porcentaje de ciudadanos. No se convierte el coeficiente dominante en un perfil rígido.

## Inicializaciones con exactamente los mismos datos

{table_text(fixed[['seed','iterations','stopped_before_limit','sse','excess_sse_fraction','geometry_rmse','raw_rmse_pp','max_curve_shift_pp','alpha_l1_mean']])}

Con datos fijos, los arquetipos K3 difieren hasta **{fixeddisp.all_pair_max_curve_shift_pp:.2f} pp** entre arranques; la SSE oscila entre {fixeddisp.minimum_sse:.3f} y {fixeddisp.maximum_sse:.3f} ({100*fixeddisp.relative_sse_range:.2f} % sobre el mínimo). Es evidencia de distintas soluciones detenidas compatibles con atracción a mínimos locales; el algoritmo aproximado y el criterio de parada no prueban que cada una sea un mínimo local exacto.

La mejor SSE corresponde a semilla **{int(best.seed)}**. Sólo **{int(fixeddisp.near_best_starts)}/10** cae dentro del margen diagnóstico del1 % del mejor objetivo completo. Con un único resultado próximo al óptimo observado no puede estimarse la estabilidad de ese óptimo ni concluir que la menor SSE garantiza curvas estables. Los diez arranques tienen igual legitimidad para el diagnóstico; no se elige la semilla por su interpretación.

Para evitar la tautología de medir al mejor contra sí mismo, se calcula también para cada semilla su distancia media de curvas a las otras nueve, sin referencia privilegiada:

{table_text(centrality[['seed','sse','mean_pair_curve_shift_pp','median_pair_curve_shift_pp','maximum_pair_curve_shift_pp']])}

En este banco, Spearman entre SSE y distancia media a otros arranques es **{rho:.4f}**: los objetivos menores suelen ser más centrales entre las soluciones observadas. La mejor SSE tiene distancia media {central_best.mean_pair_curve_shift_pp:.3f} pp, dentro del rango {centrality.mean_pair_curve_shift_pp.min():.3f}–{centrality.mean_pair_curve_shift_pp.max():.3f} pp. Centralidad entre diez arranques no es exactitud, estabilidad territorial ni una prueba universal de que minimizar SSE identifica un extremo fiable. No se calculan p-valores ni se cambió el criterio de selección.

El1 % de exceso de SSE, 5 pp de desplazamiento y 1 pp de diferencia entre reconstrucciones son referencias operativas de revisión declaradas, **no umbrales oficiales, pruebas de error, intervalos de confianza o aceptación automática**. Los valores completos se entregan para juzgar otras tolerancias.

{chart('fixed_initialization_curves')}

## Separación entre optimización y perturbación municipal

Se reutilizan las **diez mismas submuestras**, cada una con1,981 de2,477 municipios originales, sin reemplazo; ambos sexos elegibles permanecen juntos. Aportan {cov.profiles_train.min():,}–{cov.profiles_train.max():,} perfiles entrenados por sorteo; LN de entrenamiento equivale a {100*cov.fraction_eligible_LN.min():.2f}–{100*cov.fraction_eligible_LN.max():.2f} % del LN elegible común. Se registran municipios sorteados que no aportan perfiles, municipios activos, OOB, LN y filas para cada muestra.

Para cada muestra y K se ajustan las escalas sólo con entrenamiento y se prueban diez semillas con esa misma escala y población. El modelo de menor SSE de entrenamiento proyecta todos los OOB; no se usan sus errores para seleccionarlo. La referencia nacional incluye conteos de todo2024, también OOB: **estabilidad condicional a referencias nacionales fijas**, no predicción independiente de todo el procedimiento.

Los siguientes protocolos se comparan contra **la misma referencia completa nueva**. «Un arranque» es la semilla17 anterior, reutilizada; «diez» selecciona entre el banco predefinido. El anterior máximo20.72 pp utilizaba otra referencia completa; no se resta directamente como si todo el cambio fuese optimización.

{table_text(protocols)}

En K3, el máximo municipal pasa de **{before.max_curve_shift_max_pp:.2f} a {after.max_curve_shift_max_pp:.2f} pp**, y la mediana del máximo de {before.max_curve_shift_median_pp:.2f} a {after.max_curve_shift_median_pp:.2f} pp. Disminuye la variación inducida por la lotería de arranques, pero **{int((municipal.max_curve_shift_pp>5).sum())}/10 muestras** todavía superan la referencia operativa de5 pp. El error OOB mediano cambia de {before.oob_rmse_median_pp:.3f} a {after.oob_rmse_median_pp:.3f} pp: más arranques no mejoraron ese indicador original fuera de entrenamiento, pese a reducir SSE de entrenamiento. No se oculta este resultado.

Para cuantificar dispersión sin atribuirla toda a municipios se usa una identidad balanceada: en10 muestras×10 semillas, cada curva alineada es un vector de9 coordenadas. La varianza total con ddof=0 es la media de varianzas **entre semillas dentro del mismo entrenamiento** más la varianza **entre medias de muestras**.

{table_text(variance)}

Para K3, el componente dentro de muestras representa **{100*part.within_fraction:.2f} %** de la dispersión total de este diseño; el componente entre medias, **{100*part.between_fraction:.2f} %**. Son fracciones descriptivas de estos100 ajustes/alineación, **no el porcentaje causal de la inestabilidad anterior**, ni incertidumbre de votantes. El componente entre medias también puede contener distinta frecuencia de soluciones del optimizador. La perturbación municipal tras elegir el mejor de diez conserva optimización residual: no se afirma haberla eliminado.

{near_text} La tabla de pares permite comprobar que un pequeño margen de SSE no implica curvas próximas. Tampoco una mediana municipal favorable certifica el peor caso.

{chart('optimization_vs_municipal_variation')}
{chart('municipal_multistart_curves')}
{chart('initialization_budget_effects')}

## Reconstrucción OOB: K2 frente a K3

{table_text(paired)}

K3 conserva menor RMSE OOB en **{int((paired.reduction_pp>0).sum())}/10** muestras. Medianas: K2={control.oob_rmse_median_pp:.3f} pp y K3={after.oob_rmse_median_pp:.3f} pp; peor RMSE K3={after.oob_rmse_max_pp:.3f} pp. La reducción emparejada mediana es **{paired.reduction_pp.median():.3f} pp**, con rango {paired.reduction_pp.min():.3f}–{paired.reduction_pp.max():.3f} pp. Las medianas de reducciones y la diferencia entre medianas no tienen por qué coincidir.

El peor RMSE anterior resume una muestra completa. El máximo RMSE de **un perfil OOB individual** es **{maximum_individual_oob:.2f} pp**: hay curvas locales mal reconstruidas aunque el promedio sea pequeño. Las figuras de casos y los percentiles documentan esa cola, sin ocultarla con el error global.

Se preserva RMSE geométrica, original en pp, error normalizado frente a la media del entrenamiento, percentiles y desglose por sexo, LN, NS, secciones y entidad. SSE de espacios/poblaciones diferentes no se equipara para escoger geometría. Los controles OOB sí comparten entrenamiento, escala, unidades y observaciones de evaluación. Mejor reconstrucción no identifica tres clases naturales ni certifica utilidad de comunicación.

{chart('paired_oob_error')}

## Auditoría de aportantes y estabilidad de su influencia

Principales aportantes del modelo completo seleccionado; SV+NV y secciones se muestran por banda, no se suman como territorios únicos:

{table_text(detailed)}

La auditoría completa añade NS/LN, filas fuente, peso β, distancia al centro, cola1 %, sexo, LN y concentración equivalente 1/Σβ². La concentración equivalente es un reparto de pesos, **no personas ni tamaño muestral efectivo**. Una sección puede estar presente en varias bandas: no se suman secciones como independientes.

{table_text(top_stability.head(12))}

Un perfil sigue aportando β máximo={biggest.weight.max():.3f}; existen extremos con pocas secciones aun cumpliendo denominadores. Los aportantes cambian entre soluciones de semillas. Ello obliga a documentar el anclaje territorial, sin declarar errores por ser extremos o por recibir peso alto. El diagnóstico individual posterior es necesario para comprobar si ese anclaje es indispensable.

{chart('extreme_contributor_concentration')}

## Exclusiones temporales: E0, E1, E2 y E3

- **E0:** todos los4,571 elegibles.
- **E1:** excluye temporalmente ceil(0.01×4,571)=46 mayores distancias al centro de la geometría de entrenamiento E0; desempate por row_id. No utiliza OOB para diseñar el recorte.
- **E2:** excluye del entrenamiento cualquier perfil con alguna banda NS/LN≥10 % o con menos de cinco secciones distintas. No se relajan umbrales originales.
- **E3:** tres diagnósticos separados, cada uno retira sólo el mayor contribuyente β de un arquetipo del modelo E0. No se trata de retirar municipios completos ni demostrar error del perfil.

Todos usan diez inicializaciones y se eligen por SSE del entrenamiento correspondiente. E1/E2/E3 mantienen la escala E0 fija para aislar el cambio de población; se declaran sensibilidades, **no validaciones predictivas independientes de esas exclusiones**. En el remuestreo municipal la escala sí se reajusta exclusivamente en cada entrenamiento. Todos los escenarios se proyectan/evalúan sobre las mismas4,571 filas, incluidas las retiradas; no se modifica una fuente.

{table_text(scenario_table)}

E1 cambia curvas hasta **{e1.max_curve_shift_pp:.2f} pp**. E2 deja {int(e2.training_profiles):,} perfiles, LN={int(e2.LN_training):,}, y cambia curvas hasta **{e2.max_curve_shift_pp:.2f} pp**. No se interpreta ese cambio como efecto causal de NS: cambian cobertura y composición, además del ajuste finito. Excluir aproximadamente42 % de perfiles en E2 es una perturbación sustancial y no puede presentarse como una pequeña limpieza.

**E3 es más favorable que lo que sugería observar sólo β:** retirar uno a uno los mayores aportantes produce cambios máximos de {e3.max_curve_shift_pp.min():.2f}–{e3.max_curve_shift_pp.max():.2f} pp. No aparece un colapso por una sola observación. Otros extremos próximos pueden sostener la envolvente. No se concluye que cada ancla individual vuelva inválido el modelo, pero tampoco que la estabilidad individual resuelva la sensibilidad a conjuntos extremos o a la población territorial.

Son ajustes clásicos sobre entrenamientos temporalmente distintos. **No se implementa Robust Archetypal Analysis formal**, M-estimadores ni reponderación iterativa. No se eliminan registros, no se imputa NS y no se declara errónea una observación por pertenecer a una cola.

{chart('exclusion_sensitivity_curves')}

## Mezclas, diferencias por calidad y casos de mayor cambio

En la referencia completa K3, **{100*(~mix.dominated).mean():.2f} %** tiene coeficiente máximo<0.8; {100*mix.dominated.mean():.2f} % supera o iguala ese umbral descriptivo. Entropía normalizada media={mix.normalized_entropy.mean():.4f}. Las mezclas describen una reconstrucción agregada, no una proporción de ciudadanos asignables a tipos.

El cambio L1 OOB medio por muestra tiene mediana **{after.alpha_oob_l1_median:.4f}**, peor media {after.alpha_oob_l1_max:.4f}; el mayor cambio individual OOB es **{municipal.oob_alpha_l1_max.max():.4f}** (escala L1 de0 a2). Se informan también p95 y máximo. Las medias pequeñas no deben esconder perfiles cuya mezcla cambia más.

{table_text(municipal[['sample','seed','oob_rmse_pp','max_curve_shift_pp','oob_alpha_l1_mean','oob_alpha_l1_p95','oob_alpha_l1_max']])}

{table_text(sex[['group','profiles','LN','rmse_pp','error_max_pp','dominated_fraction']])}

{table_text(quality[['grouping','group','profiles','LN','rmse_pp','error_max_pp','dominated_fraction']])}

Los estratos LN y entidades están en grouped_metrics; los grupos de NS y secciones se superponen y no se suman como observaciones únicas. Su diferencia de error no identifica causalidad, comportamiento individual o sesgo corregido.

Mayores casos individuales OOB, sin inventar observaciones ni asignar etiquetas rígidas:

{table_text(worst[['row_id','sample','alpha_l1','reconstruction_difference_pp','rmse_pp']])}

{chart('mixture_distributions')}
{chart('municipal_coefficient_changes')}
{chart('most_unstable_observations')}

## Curvas diferentes, reconstrucciones próximas e interpretación electoral

En comparaciones de semillas sobre **exactamente el mismo entrenamiento**, hay {len(equivalent)} pares K3 con cambio de curvas>5 pp y diferencia RMS de reconstrucciones<1 pp. {len(equivalent_near)} de esos pares sitúan ambas SSE dentro del1 % del mínimo de su muestra. Ejemplos:

{table_text(equivalent_near.head(5)[['sample','left_trial','right_trial','left_excess_sse','right_excess_sse','max_curve_shift_pp','reconstruction_difference_rmse_pp','alpha_l1_mean']])}

Es evidencia de identificación empírica débil de los **extremos aprendidos**, o de soluciones cercanas del optimizador que representan de modo parecido el interior. No demuestra que todas sean mínimos globales equivalentes. K3 tiene rango afín2 en estas soluciones; para un triángulo fijo no degenerado los coeficientes de un punto de su plano son únicos. La variación al mover el triángulo es distinta de afirmar no unicidad formal de α con Z fijo. El optimizador NNLS aumentado es aproximado, como ya se documentó.

{chart('curve_reconstruction_equivalence')}

Contrastes de la referencia elegida por SSE:

{table_text(maincontrasts)}

{chr(10).join(lines)}

Rangos de nivel y contraste entre las diez muestras seleccionadas con diez arranques:

{table_text(pd.DataFrame(positives))}

Los contrastes amplios permiten describir un nivel positivo y dos patrones de nivel negativo con contrastes de edad diferentes. Las amplitudes y algunas diferencias cercanas a cero cambian; no debe presentarse la curva exacta como una esencia territorial. Los arquetipos son mezclas de perfiles, pueden corresponder a vértices excepcionales de la envolvente y **no estiman la prevalencia de un tipo ciudadano**. Sus coeficientes se extienden por el interior; un peso β alto no significa que ese patrón sea frecuente. Las características disponibles no explican motivaciones, preferencias partidistas o barreras personales.

{chart('electoral_level_and_shape')}

## Utilidad frente a los seis perfiles y a indicadores sencillos

Las seis reglas permanecen intactas y son la propuesta principal del proyecto. Su unidad es municipio×sexo×banda; AA usa municipio×sexo. Se pivota una firma de tres etiquetas y se une uno a uno a4,571 perfiles; no se multiplican filas para métricas, no se calcula ARI entre unidades incompatibles y no se entrenan las reglas de nuevo. Los municipios y sexos pueden compartir firmas y tener intensidades distintas.

Ejemplos reales con la misma firma, cuyos niveles, formas y mezclas son diferentes:

{table_text(cases)}

La identidad d=m1+qQᵀ reconstruye los datos desde **nivel y dos contrastes existentes** con residuo máximo {simple['max_original_reconstruction_error']:.2e}. Estos indicadores conservan los tres grados de libertad; los coeficientes K3 suman uno y tienen dos grados de libertad para un triángulo aprendido. La identidad sin pérdida y AA no son modelos con la misma complejidad: su error cero no es una victoria predictiva de otro algoritmo.

AA es una función aprendida de esos mismos datos: no añade información observacional. Puede aportar una metáfora visual de mezclas, pero no se demostró una ventaja de comunicación frente a mostrar m y la curva de forma por edades. Ambos describen intensidad dentro de los mismos signos de reglas. Los indicadores originales con referencia nacional fija no cambian al retirar municipios del ajuste; esto es estabilidad algebraica condicional, no ausencia de error electoral o validación predictiva. No requieren seleccionar perfiles ancla, ni resolver qué semilla o triángulo comunicar.

La opción B aprovecha esos indicadores como contexto de las seis fichas: nivel relativo, contrastes por edad, conteos, NS y soporte. Esta entrega **no cambia la app ni crea variables nuevas de clustering**. AA se conserva íntegro como evidencia de investigación; no se transforma su mayor capacidad de reconstrucción en una nueva tipología.

{chart('rule_profiles_and_simple_indicators')}

## Decisión y respuestas obligatorias

**Opción elegida: B. Utilizar indicadores continuos sin arquetipos.** El beneficio es una comunicación directa y reproducible de magnitud/forma con la cobertura intacta, sin anclas dependientes del ajuste. El riesgo es renunciar al resumen visual de mezclas que puede ser útil para exploración especializada. No se adopta A porque persisten diferencias de extremos de {after.max_curve_shift_max_pp:.2f} pp entre muestras y {e2.max_curve_shift_pp:.2f} pp ante calidad, soluciones de SSE cercana con curvas diferentes y utilidad adicional de comunicación no comprobada. No se elige C como recomendación principal porque los indicadores continuos sí proporcionan una alternativa interpretable para complementar las fichas; AA permanece documentado, sin publicación.

1. **¿Cuánto provenía de inicializaciones?** Con datos fijos hay hasta {fixeddisp.all_pair_max_curve_shift_pp:.2f} pp entre curvas de semillas. En el diseño balanceado actual, {100*part.within_fraction:.2f} % de la dispersión alineada está dentro de entrenamientos. No se identifica un porcentaje causal exacto de la inestabilidad del informe anterior.
2. **¿Cuánto persiste con múltiples arranques?** El peor desplazamiento municipal baja de {before.max_curve_shift_max_pp:.2f} a {after.max_curve_shift_max_pp:.2f} pp frente a la misma referencia nueva. Persisten pares a≤1 % del mejor SSE con curvas diferentes; selección entre diez reduce, no elimina, optimización residual.
3. **¿K3 mantiene su mejora OOB?** Sí: {after.oob_rmse_median_pp:.3f} frente a {control.oob_rmse_median_pp:.3f} pp de K2, con reducción en las diez muestras. La mayor reconstrucción no certifica tres clases naturales.
4. **¿Siguen dependiendo de extremos?** Sí en su construcción β y sensibilidad a la cola de perfiles; el máximo β es {biggest.weight.max():.3f}. Pero retirar individualmente cada mayor aportante sólo desplaza hasta {e3.max_curve_shift_pp.max():.2f} pp: no hay evidencia de colapso por una observación aislada.
5. **¿Sensibilidad a calidad?** E2 conserva {int(e2.training_profiles):,} perfiles entrenados y desplaza hasta {e2.max_curve_shift_pp:.2f} pp; evalúa todos. Es una perturbación fuerte de población/cobertura, no prueba de error, ni efecto causal puro de NS o secciones.
6. **¿Coeficientes reproducibles e interpretables?** Son interpretables como reconstrucciones convexas agregadas, con L1 OOB mediano entre muestras {after.alpha_oob_l1_median:.4f} y máximo individual {municipal.oob_alpha_l1_max.max():.4f}. Su interpretación depende del triángulo alineado y no representa probabilidades de comportamiento.
7. **¿K3 aporta frente a K2?** Sí para reconstruir contrastes, con menor error OOB; su estabilidad de extremos es menor que la del control. No hay suficiente base para una tipología electoral definitiva.
8. **¿Supera indicadores continuos?** No se demostró una utilidad adicional de comunicación. Nivel y dos contrastes conservan exactamente los datos medidos, sin seleccionar extremos; AA resume con pérdida y añade una metáfora, no observaciones.
9. **¿Usarlo como complemento en ParticipaMX?** En esta entrega se recomienda B: indicadores continuos junto a las seis reglas; no publicar AA. Un uso posterior requeriría validar con usuarios la comprensión de curvas/mezclas y las advertencias, además de resolver la sensibilidad residual.
10. **¿Límites para el jurado?** Unidades agregadas/ecológicas; referencias nacionales fijas; soporte y NS desiguales; cobertura municipal parcial; geometría50/50 elegida; optimización finita; sólo diez muestras; arquetipos próximos a extremos; no inferir prevalencia, motivaciones, probabilidades individuales o causalidad. Los seis perfiles por reglas siguen siendo la entrega principal conforme al alcance solicitado; estos tres arquetipos no los sustituyen ni son tres clusters exigidos.

## Entregables, integridad y recuperación

`reference/` conserva perfiles completos/elegibles, pendientes, referencias y broad complementaria. `matrices/` guarda matriz y escala principal; cada modelo registra su escala, máscara y hash de entrenamiento. `models/` conserva nuevos modelos joblib y arrays α/β/arquetipos/reconstrucciones; `reused/` guarda referencias verificadas a modelos anteriores, sin copiarlos o sobrescribirlos. `metadata/` contiene todos los arranques, selección, presupuestos, dispersión, cobertura y decisión. `diagnostics/` conserva alineaciones, curvas, aportantes con conteos por banda, pares y casos OOB. `selected/` mantiene coeficientes y NULL de pendientes; `comparisons/` enlaza reglas e indicadores.

Hay checkpoints A–F y marcadores por modelo, escrituras atómicas y comprobación de lectura de Parquet. Se conserva cada ajuste desfavorable y el estado de parada; una incidencia se registra en state.json y no borra modelos válidos. Un lock exclusivo y consulta de procesos evitan duplicados. Las pruebas verifican selección sin OOB, identidad de varianza, permutaciones, convexidad, escalas de entrenamiento, agrupación de sexos por municipio, todos los arranques, conservación de conteos, E3 y uniones sin expansión. Se verifican por hash **{len(self.state['protected_hashes'])} archivos previos** y los manifiestos de las cuatro fuentes. _SUCCESS se escribe sólo tras pruebas e integridad final.

```powershell
.venv_archetypal_patterns/Scripts/python.exe analysis/scripts/validate_archetypal_stability.py
.venv_archetypal_patterns/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_validate_archetypal_stability.py
```

Reanudar con las mismas rutas verifica y omite etapas/modelos íntegros. --stop-after permite detener tras una etapa; --refresh-report archiva únicamente el informe de esta entrega y regenera su documentación final sin reajustar modelos. Cambios de parámetros o versiones exigen --output, --charts y --report nuevos. No se modifican los experimentos anteriores, las seis reglas, datos originales, frontend ni public/data; no se crean commits. No se ejecuta AA robusto formal ni se prueban K4–6.
'''
        atomic_bytes(self.report,report.encode('utf8'))

    def verify_success(self):
        mp=self.output/'metadata/run_manifest.json';marker=json.loads((self.output/'_SUCCESS').read_text())
        require(marker['manifest_sha256']==file_hash(mp),'Marcador final alterado.')
        manifest=json.loads(mp.read_text(encoding='utf8'))
        for relative,digest in manifest['artifact_hashes'].items():require(file_hash(self.root/relative)==digest,'Artefacto final distinto: '+relative)
        print('Resultado verificado; cero ajustes repetidos.',flush=True)

    def finalize(self):
        self.verify_protected();self.state['status']='validated';self.state['finished']=utc();write_json(self.state_path,self.state)
        artifacts=[p for p in self.output.rglob('*') if p.is_file() and p.name not in ['run_manifest.json','state.json','_RUNNING.json','_SUCCESS']]
        artifacts += [p for p in self.charts.rglob('*') if p.is_file()]+[self.report]+[self.root/'analysis/scripts'/name for name in OWN_FILES]
        catalog=pd.read_parquet(self.output/'metadata/all_initializations.parquet')
        mp=self.output/'metadata/run_manifest.json';write_json(mp,dict(status='validated',finished=utc(),config=CONFIG,versions=self.dependencies,
            protected_hashes=self.state['protected_hashes'],artifact_hashes={str(p.relative_to(self.root)):file_hash(p) for p in artifacts},
            fits=dict(total=len(catalog),new=int((~catalog.reused).sum()),reused=int(catalog.reused.sum())),
            recommendation=json.loads((self.output/'metadata/decision.json').read_text())['option']))
        write_json(self.output/'_SUCCESS',dict(manifest_sha256=file_hash(mp),finished=utc()))
        print('Validación final completa: '+str(self.report),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'data/processed/archetypal_stability_review')
    parser.add_argument('--charts',type=Path,default=ROOT/'analysis/charts/archetypal_stability_review')
    parser.add_argument('--report',type=Path,default=ROOT/'analysis/reports/archetypal_stability_review.md')
    parser.add_argument('--stop-after',choices=list('abcdef'),default='f')
    parser.add_argument('--refresh-report',action='store_true')
    args=parser.parse_args();run=None
    with experiment_lock(args.output):
        try:
            run=Validation(ROOT,args.output,args.charts,args.report)
            if args.refresh_report:run.refresh_report()
            run.run(args.stop_after)
        except Exception as exc:
            if run is not None:
                run.state['status']='failed';run.state['errors'].append(dict(time=utc(),error=repr(exc),traceback=traceback.format_exc()))
                write_json(run.state_path,run.state)
            raise


if __name__=='__main__':main()
