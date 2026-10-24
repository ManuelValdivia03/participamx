"""Seis análisis electorales independientes; sin entrenamiento ni CSV originales.

Referencias antes de soporte, reglas exactas y unidades analíticas separadas.
Los recursos JSON son preparación de integración, sin publicar en React.
"""
from __future__ import annotations
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.venv_archetypal_patterns/mplconfig'))
import sys
sys.dont_write_bytecode=True
import argparse
import hashlib
import json
import subprocess
import time
import traceback
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import matplotlib.pyplot as plt

from clean_data import open_dataset,require,file_hash
from build_descriptive import METRICS,COUNTS,SOURCE_COUNTS,compare_sums
from build_cluster_features import snapshot_inputs
from build_profile_candidates import assign_candidates,table_text
from evaluate_participation_patterns import atomic_bytes,write_table,save_figure,experiment_lock,memory_estimate,utc,Q,safe_ratio

YEARS=[2009,2012,2015,2018,2021,2024]
BANDS=['18-34','35-59','60-100']
TYPES=['U','R','M']
MUNICIPAL_KEYS=['EDOCVE','MPIOCVE']
PROFILE_KEYS=[*MUNICIPAL_KEYS,'SEXO']
SEGMENT_KEYS=[*MUNICIPAL_KEYS,'age_band','SEXO']
IDS=[prefix+'_'+suffix for prefix in ['young','adult','older'] for suffix in ['favorable','unfavorable']]
SEX_LABELS={'0':'Hombres','1':'Mujeres','2':'No binario'}
OWN_FILES=['build_multiyear_profiles.py','test_build_multiyear_profiles.py']
CONFIG=dict(version='2.0.0',bands=BANDS,min_LN=100,min_specified=100,min_source_rows=5,high_ns=.10,
    near_reference=.02,intensity_thresholds=[.01,.02,.05],regression_atol=1e-12,batch_size=100000,
    municipal_history_enabled=False,model_fits=0)
WARNINGS=[
    'Son segmentos agregados, no personas ni clases naturales descubiertas.',
    'NS representa no especificación, no abstención. Las tasas no definidas son NULL.',
    'Las claves territoriales se consultan dentro de cada elección; no hay equivalencias municipales históricas oficiales validadas.',
    'U/R/M describe secciones electorales, no residencia individual ni localidad.',
    'La lista nominal reportada procede de cuadernillos; no incluye casillas especiales ni voto del extranjero según el diccionario.',
    'Los municipios pueden pertenecer a varios perfiles; su cobertura no se suma entre perfiles.',
    'Los intervalos y el signo relativo son reglas explícitas. Una diferencia cercana a cero requiere cautela.']


def safe_json(value):
    if value is None or value is pd.NA or value is pd.NaT:return None
    if isinstance(value,dict):return {str(k):safe_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [safe_json(v) for v in value]
    if isinstance(value,np.generic):return safe_json(value.item())
    if isinstance(value,float) and np.isinf(value):raise ValueError('Infinity no representa un dato faltante.')
    if isinstance(value,float) and np.isnan(value):return None
    if isinstance(value,Path):return str(value)
    return value


def json_bytes(value):return json.dumps(safe_json(value),ensure_ascii=False,allow_nan=False,indent=2).encode('utf8')


def write_json(path,value,protect=False):
    data=json_bytes(value);path=Path(path)
    if protect and path.exists():require(path.read_bytes()==data,'Salida parcial diferente: '+str(path))
    else:atomic_bytes(path,data)


def safe_ratio(numerator,denominator):
    def array(value):return value.to_numpy(dtype=float,na_value=np.nan) if isinstance(value,pd.Series) else np.asarray(value,float)
    a,b=array(numerator),array(denominator)
    return np.divide(a,b,out=np.full(a.shape,np.nan),where=np.isfinite(b)&(b>0))


def add_rates(frame):
    result=frame.copy();require(result.LN.eq(result.SV+result.NV+result.NS).all(),'LN no concilia.')
    result['specified_count']=result.SV+result.NV
    result['participation_observed']=safe_ratio(result.SV,result.specified_count)
    result['nonparticipation_observed']=safe_ratio(result.NV,result.specified_count)
    result['participation_nominal']=safe_ratio(result.SV,result.LN)
    result['unspecified_rate']=safe_ratio(result.NS,result.LN)
    result['has_low_support']=result.LN.lt(100)|result.specified_count.lt(100)|result.source_row_count.lt(5)
    result['has_high_ns']=result.unspecified_rate.ge(.1)
    return result


def group_counts(frame,keys):
    return frame.groupby(keys,observed=True,dropna=False,as_index=False,sort=False)[METRICS].sum()


def age_bands(values):
    age=np.asarray(values);require((age>=18).all(),'Edad menor de 18 no prevista; revisar contrato.')
    return np.select([age<=34,age<=59,age<=100],BANDS,default='101+')


def add_context(segments,children):
    """Ceros de subconjuntos vacíos conocidos, no imputación de tasas ausentes."""
    compare_sums(children,segments,SEGMENT_KEYS)
    result=segments.copy()
    for kind in TYPES:
        part=children[children.TIPOSEC.eq(kind)][SEGMENT_KEYS+METRICS+['section_count']]
        part=part.rename(columns={c:c+'_'+kind for c in METRICS+['section_count']})
        result=result.merge(part,on=SEGMENT_KEYS,how='left',validate='one_to_one',indicator=True)
        present=result._merge.eq('both');result['has_section_type_'+kind]=present
        for column in METRICS+['section_count']:result[column+'_'+kind]=result[column+'_'+kind].fillna(0).astype('int64')
        result['section_ln_share_'+kind]=safe_ratio(result['LN_'+kind],result.LN)
        result=result.drop(columns='_merge')
    result['section_count']=result[['section_count_'+t for t in TYPES]].sum(axis=1)
    for column in METRICS:require(result[[column+'_'+t for t in TYPES]].sum(axis=1).eq(result[column]).all(),'Contexto no exhaustivo: '+column)
    require(np.allclose(result[['section_ln_share_'+t for t in TYPES]].sum(axis=1),1),'Composición contextual inválida.')
    return result


def summarize_profiles(segments,total_ln):
    rows=[];core_ln=int(segments.loc[segments.in_scope,'LN'].sum())
    for candidate in IDS:
        group=segments[segments.candidate_id.eq(candidate)];den=int(group.specified_count.sum());ln=int(group.LN.sum());n=len(group)
        reference=float(np.sum(group.specified_count*group.national_rate)/den) if den else np.nan
        row=dict(candidate_id=candidate,status='supported' if n else 'no_supported_segments',
            age_band=BANDS[['young','adult','older'].index(candidate.split('_')[0])],
            segments=n,municipalities=group.groupby(MUNICIPAL_KEYS).ngroups,states=group.EDOCVE.nunique(),
            **{m:int(group[m].sum()) for m in METRICS},specified_count=den,
            participation_observed=float(group.SV.sum()/den) if den else np.nan,matched_peer_reference=reference,
            participation_delta=float(group.SV.sum()/den-reference) if den else np.nan,
            mean_segment_delta=float(group.participation_delta.mean()),delta_q1=float(group.participation_delta.quantile(.25)),
            delta_median=float(group.participation_delta.median()),delta_q3=float(group.participation_delta.quantile(.75)),
            delta_min=float(group.participation_delta.min()),delta_max=float(group.participation_delta.max()),
            near_reference_segments=int(group.near_reference.sum()),near_reference_fraction=float(group.near_reference.mean()) if n else np.nan,
            high_ns_segments=int(group.high_ns.sum()),high_ns_fraction=float(group.high_ns.mean()) if n else np.nan,
            unspecified_rate=float(group.NS.sum()/ln) if ln else np.nan,nominal_coverage=ln/total_ln,
            core_nominal_coverage=ln/core_ln if core_ln else np.nan,
            women_segment_fraction=float(group.SEXO.eq('1').mean()) if n else np.nan,
            women_nominal_fraction=float(group.loc[group.SEXO.eq('1'),'LN'].sum()/ln) if ln else np.nan,
            specified_min=int(group.specified_count.min()) if n else None,specified_median=float(group.specified_count.median()) if n else np.nan,
            source_rows_median=float(group.source_row_count.median()) if n else np.nan,
            sections_median=float(group.section_count.median()) if n else np.nan,sections_min=int(group.section_count.min()) if n else None,
            low_section_segments=int(group.section_count.lt(5).sum()),distinct_sections=None)
        for kind in TYPES:row['nominal_share_'+kind]=float(group['LN_'+kind].sum()/ln) if ln else np.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values('candidate_id').reset_index(drop=True)


def build_continuous(segments,municipalities,year):
    """Rejilla H/M por municipio; ausencia, tasa NULL y falta de soporte separados."""
    core=segments[segments.in_scope].copy();national=core[['age_band','SEXO','national_rate']].drop_duplicates()
    base=municipalities[MUNICIPAL_KEYS+['state_name_label','municipality_name_label','district_reference_year']].merge(pd.DataFrame({'SEXO':['0','1']}),how='cross')
    rates=[];deltas=[];support=[]
    for j,band in enumerate(BANDS):
        part=core[core.age_band.eq(band)][PROFILE_KEYS+METRICS+['section_count','specified_count','local_turnout','national_rate','participation_delta','unspecified_rate','sufficient_support']]
        renamed={c:c+'_'+str(j) for c in part if c not in PROFILE_KEYS}
        base=base.merge(part.rename(columns=renamed),on=PROFILE_KEYS,how='left',validate='one_to_one',indicator=True)
        base['present_'+str(j)]=base._merge.eq('both');base=base.drop(columns='_merge')
        for field in METRICS+['section_count','specified_count']:base[field+'_'+str(j)]=pd.array(base[field+'_'+str(j)],dtype='Int64')
        rates.append(base['local_turnout_'+str(j)].to_numpy(float));deltas.append(base['participation_delta_'+str(j)].to_numpy(float))
        supported=base['present_'+str(j)]&base['sufficient_support_'+str(j)].eq(True)&base['local_turnout_'+str(j)].notna()
        base['supported_'+str(j)]=supported;support.append(supported.to_numpy())
    d=np.column_stack(deltas);r=np.column_stack(rates);s=np.column_stack(support)
    base['relative_level']=d.mean(1);base['mean_observed_rate']=r.mean(1);base['young_older_difference']=d[:,0]-d[:,2]
    base['complete_profile']=np.isfinite(d).all(1);base['is_eligible']=base.complete_profile&s.all(1)
    base['supported_coordinates']=s.sum(1);base['has_high_ns_coordinate']=base[['unspecified_rate_'+str(j) for j in range(3)]].ge(.1).any(axis=1)
    base['min_section_count']=base[['section_count_'+str(j) for j in range(3)]].min(axis=1)
    base['min_specified_count']=base[['specified_count_'+str(j) for j in range(3)]].min(axis=1)
    base['pending_reason']=np.select([~base.complete_profile,~base.is_eligible],['undefined_or_absent_rate','insufficient_coordinate_support'],default='eligible')
    for j in range(3):base['shape_'+str(j)]=d[:,j]-base.relative_level
    contrast=d@Q
    for j in range(2):base['contrast_'+str(j)]=contrast[:,j]
    totals=group_counts(core,PROFILE_KEYS)
    base=base.merge(totals,on=PROFILE_KEYS,how='left',validate='one_to_one')
    base['specified_count']=base.SV+base.NV;base['participation_observed']=safe_ratio(base.SV,base.specified_count);base['unspecified_rate']=safe_ratio(base.NS,base.LN)
    base.insert(0,'election_year',year);base.insert(1,'row_id',base[PROFILE_KEYS].astype(str).agg('|'.join,axis=1).map(lambda x:f'pattern_{year}|'+x))
    base=base.sort_values(PROFILE_KEYS).reset_index(drop=True)
    pairs=[]
    for sex,prefix in [('0','male'),('1','female')]:
        part=core[core.SEXO.eq(sex)][MUNICIPAL_KEYS+['age_band','local_turnout','participation_delta','sufficient_support','specified_count','unspecified_rate']].copy()
        pairs.append(part.rename(columns={c:prefix+'_'+c for c in part if c not in MUNICIPAL_KEYS+['age_band']}))
    gaps=pairs[0].merge(pairs[1],on=MUNICIPAL_KEYS+['age_band'],how='outer',validate='one_to_one')
    gaps['S_available']=gaps.male_sufficient_support.eq(True)&gaps.female_sufficient_support.eq(True)&gaps.male_local_turnout.notna()&gaps.female_local_turnout.notna()
    gaps['raw_sex_gap_observed']=gaps.female_local_turnout-gaps.male_local_turnout
    gaps['raw_sex_gap_adjusted']=gaps.female_participation_delta-gaps.male_participation_delta
    gaps['sex_gap_observed']=gaps.raw_sex_gap_observed.where(gaps.S_available)
    gaps['sex_gap_adjusted']=gaps.raw_sex_gap_adjusted.where(gaps.S_available)
    gaps['gap_max_ns']=gaps[['male_unspecified_rate','female_unspecified_rate']].max(axis=1);gaps.insert(0,'election_year',year)
    core['expected_peer_votes']=core.specified_count*core.national_rate
    municipal=core.groupby(MUNICIPAL_KEYS,as_index=False)[COUNTS+['expected_peer_votes']].sum()
    municipal['municipal_turnout_core']=safe_ratio(municipal.SV,municipal.SV+municipal.NV)
    municipal['municipal_peer_reference']=safe_ratio(municipal.expected_peer_votes,municipal.SV+municipal.NV)
    municipal['municipal_adjusted_turnout']=municipal.municipal_turnout_core-municipal.municipal_peer_reference
    municipal['municipal_core_ns']=safe_ratio(municipal.NS,municipal.LN)
    municipal=municipal.rename(columns={c:'core_'+c for c in COUNTS+['expected_peer_votes']})
    municipal=municipalities.merge(municipal,on=MUNICIPAL_KEYS,how='left',validate='one_to_one')
    eligible=base.groupby(MUNICIPAL_KEYS).is_eligible.sum().rename('supported_continuous_profiles')
    municipal=municipal.join(eligible,on=MUNICIPAL_KEYS)
    return base,gaps,municipal


def validate_json(value,schema,path='$'):
    """Validador cerrado del subconjunto utilizado; esquema estándar 2020-12."""
    supported={'$schema','title','description','type','properties','required','additionalProperties','items','enum','const','minimum','maximum','minItems','maxItems','minLength'}
    require(set(schema)<=supported,'Keyword no implementado: '+path)
    if 'const' in schema:require(type(value) is type(schema['const']) and value==schema['const'],'Constante incorrecta: '+path)
    if 'enum' in schema:require(value in schema['enum'],'Categoría incorrecta: '+path)
    types=schema.get('type',[]);types=[types] if isinstance(types,str) else types
    checks={'null':value is None,'object':isinstance(value,dict),'array':isinstance(value,list),'string':isinstance(value,str),
        'boolean':type(value) is bool,'integer':type(value) is int,'number':type(value) in [int,float] and np.isfinite(value)}
    require(not types or any(checks[t] for t in types),'Tipo incorrecto: '+path)
    if value is None:return
    if isinstance(value,dict):
        require(set(schema.get('required',[]))<=set(value),'Campo requerido ausente: '+path)
        props=schema.get('properties',{})
        require(schema.get('additionalProperties') is not False or set(value)<=set(props),'Campo desconocido: '+path)
        for key,item in value.items():
            if key in props:validate_json(item,props[key],path+'.'+key)
    elif isinstance(value,list):
        require(schema.get('minItems',0)<=len(value)<=schema.get('maxItems',float('inf')),'Longitud incorrecta: '+path)
        for i,item in enumerate(value):validate_json(item,schema['items'],f'{path}[{i}]')
    elif isinstance(value,str):require(len(value)>=schema.get('minLength',0),'Texto vacío: '+path)
    elif type(value) in [int,float]:
        require(np.isfinite(value) and schema.get('minimum',-float('inf'))<=value<=schema.get('maximum',float('inf')),'Número inválido: '+path)


def object_schema(properties):return dict(type='object',properties=properties,required=list(properties),additionalProperties=False)


def frame_schema(frame,unit,title):
    """Se congela una vez con 2024; todos los años deben cumplir las mismas claves."""
    properties={}
    key_fields={'election_year','state_code','municipality_code','sex_code','age_band','exact_age','section_type','row_id'}
    for name,series in frame.items():
        if pd.api.types.is_bool_dtype(series):kind='boolean'
        elif pd.api.types.is_integer_dtype(series):kind='integer'
        elif pd.api.types.is_float_dtype(series):kind='number'
        elif name=='distinct_sections':kind='integer'
        else:
            values=[v for v in series if v is not None and v is not pd.NA]
            kind='array' if values and isinstance(values[0],list) else 'string'
        item=dict(type=kind if name in key_fields else [kind,'null'])
        if kind=='array':item['items']=dict(type='string')
        if name=='election_year':item['enum']=YEARS
        if name=='sex_code':item['enum']=['0','1','2']
        if name=='age_band':item['enum']=BANDS+['101+']
        if name=='section_type':item['enum']=TYPES
        if name=='profile_id':item['enum']=IDS+[None]
        if kind in ['integer','number']:
            signed=any(token in name for token in ['delta','relative','shape','contrast','gap','difference','direction','adjusted'])
            if not signed:item['minimum']=0
            if name=='direction':item.update(minimum=-1,maximum=1)
            proportion=(name.endswith(('_rate','_fraction','_coverage','_turnout','_reference')) or
                any(token in name for token in ['_rate_','_fraction_','_share_','_turnout_']) or
                name in ['participation_observed','nonparticipation_observed','participation_nominal'])
            if not signed and proportion:item['maximum']=1
        properties[name]=item
    header=object_schema(dict(schema_version=dict(const=CONFIG['version']),election_year=dict(type='integer',enum=YEARS),
        election_type=dict(type='string',enum=['presidential','midterm']),unit=dict(const=unit),source_id=dict(const='ine_counted_lists'),
        rate_unit=dict(const='proportion'),data=dict(type='array',items=object_schema(properties)),warnings=dict(type='array',items=dict(type='string'))))
    return {'$schema':'https://json-schema.org/draft/2020-12/schema','title':title,**header}


def public_frame(frame):
    result=frame.copy().rename(columns={'EDOCVE':'state_code','MPIOCVE':'municipality_code','SEXO':'sex_code','TIPOSEC':'section_type',
        'age_value':'exact_age','candidate_id':'profile_id','state_name_label':'state_name','municipality_name_label':'municipality_name'})
    if 'has_high_unspecified_rate' in result and 'has_high_ns' not in result:result=result.rename(columns={'has_high_unspecified_rate':'has_high_ns'})
    return result


def territorial_profile_summary(segments,keys,totals):
    selected=segments[segments.candidate_id.notna()].copy();selected['expected_peer_votes']=selected.specified_count*selected.national_rate
    counts=selected.groupby(keys+['candidate_id'],as_index=False,observed=True)[METRICS+['expected_peer_votes']].sum()
    size=selected.groupby(keys+['candidate_id'],as_index=False,observed=True).agg(segments=('row_id','size'),near_reference_segments=('near_reference','sum'),high_ns_segments=('high_ns','sum'))
    counts=add_rates(counts).merge(size,on=keys+['candidate_id'],validate='one_to_one')
    counts['matched_peer_reference']=safe_ratio(counts.expected_peer_votes,counts.specified_count)
    counts['relative_turnout']=counts.participation_observed-counts.matched_peer_reference
    counts=counts.merge(totals[keys+['LN']].rename(columns={'LN':'territorial_LN'}),on=keys,validate='many_to_one')
    counts['share_of_territorial_LN']=safe_ratio(counts.LN,counts.territorial_LN)
    return counts


def public_tables(data,year):
    seg=data['segments'];assigned=seg[seg.candidate_id.notna()];profile=data['profiles'].copy()
    profile['label']=[f'{band} años · '+('por encima de sus pares' if name.endswith('_favorable') else 'por debajo de sus pares') for band,name in zip(profile.age_band,profile.candidate_id)]
    resources=dict(profiles=public_frame(profile),national_references=public_frame(data['national_references']),
        national_statistics=public_frame(data['year']),age_statistics=public_frame(data['age_statistics']),
        sex_statistics=public_frame(data['sex_statistics']),section_statistics=public_frame(data['section_statistics']))
    for name,keys in [('municipalities',MUNICIPAL_KEYS),('states',['EDOCVE'])]:
        f=data[name].copy();lookup=assigned.groupby(keys).candidate_id.agg(lambda v:sorted(set(v)))
        f['profile_ids']=[lookup.get(tuple(r) if len(keys)>1 else r[0],[]) for r in f[keys].itertuples(index=False,name=None)]
        resources[name]=public_frame(f)
    state_profiles=territorial_profile_summary(seg,['EDOCVE'],data['states']);state_profiles.insert(0,'election_year',year)
    municipal_profiles=territorial_profile_summary(seg,MUNICIPAL_KEYS,data['municipalities']);municipal_profiles.insert(0,'election_year',year)
    resources['state_profiles']=public_frame(state_profiles);resources['municipality_profiles']=public_frame(municipal_profiles)
    segment_columns=['row_id','election_year',*SEGMENT_KEYS,*METRICS,'specified_count','local_turnout','national_rate','relative_turnout','unspecified_rate',
        'candidate_id','rule_candidate_id','assignment_status','direction','near_reference','sufficient_support','low_ln','low_specified','few_source_rows','high_ns','section_count',
        *['section_ln_share_'+t for t in TYPES]]
    resources['municipality_segments']=public_frame(seg[segment_columns])
    c=data['continuous'];base=['election_year','row_id',*PROFILE_KEYS,'state_name_label','municipality_name_label','district_reference_year',*METRICS,'specified_count','participation_observed','unspecified_rate',
        'relative_level','mean_observed_rate','young_older_difference','complete_profile','is_eligible','supported_coordinates','pending_reason','has_high_ns_coordinate','min_section_count','min_specified_count']
    names={}
    for j,band in enumerate(BANDS):
        suffix=band.replace('-','_')
        for col in METRICS+['section_count','specified_count','local_turnout','national_rate','participation_delta','unspecified_rate','supported','shape','present']:
            original=col+'_'+str(j)
            if original in c:base.append(original);names[original]=col+'_'+suffix
    base+=['contrast_0','contrast_1'];names.update(contrast_0='shape_contrast_1',contrast_1='shape_contrast_2')
    resources['continuous_indicators']=public_frame(c[base].rename(columns=names))
    resources['sex_gaps']=public_frame(data['sex_gaps'])
    for name,f in resources.items():
        if 'election_year' not in f:f.insert(0,'election_year',year)
        require(f.election_year.eq(year).all(),'Recurso contiene otra elección: '+name)
    return resources


UNITS={'profiles':'rule_candidate','national_references':'national_age_band_sex','national_statistics':'election',
    'age_statistics':'national_exact_age_sex','sex_statistics':'national_sex','section_statistics':'national_section_type',
    'municipalities':'municipality','states':'state','state_profiles':'state_rule_candidate','municipality_profiles':'municipality_rule_candidate',
    'municipality_segments':'municipality_age_band_sex','continuous_indicators':'municipality_sex','sex_gaps':'municipality_age_band',
    'exact_age_segments':'municipality_exact_age_sex','quality_summary':'election_quality','assignment_status':'segment_assignment_status'}


def value_schema(value,name=''):
    """Esquemas de metadatos estructurados; sin keywords ajenos al validador."""
    if value is None:return dict(type='null')
    if isinstance(value,dict):return object_schema({k:value_schema(v,k) for k,v in value.items()})
    if isinstance(value,list):
        items={}
        for item in value:items=merge_value_schemas(items,value_schema(item))
        return dict(type='array',items=items)
    if type(value) is bool:return dict(type=['boolean','null'])
    if type(value) is int:return dict(type='integer' if name=='election_year' else ['integer','null'],**({'enum':YEARS} if name=='election_year' else {}))
    if type(value) is float:return dict(type=['number','null'])
    return dict(type=['string','null'])


def merge_value_schemas(left,right):
    """Une tipos NULL/número observados en metadatos sin relajar sus claves."""
    if not left:return right
    result=dict(left)
    lt=left.get('type',[]);rt=right.get('type',[])
    lt=[lt] if isinstance(lt,str) else lt;rt=[rt] if isinstance(rt,str) else rt
    types=list(dict.fromkeys(lt+rt));result['type']=types[0] if len(types)==1 else types
    if 'properties' in right:
        if 'properties' in left:require(set(left['properties'])==set(right['properties']),'Metadatos con campos no homogéneos.')
        result['properties']={key:merge_value_schemas(left.get('properties',{}).get(key,{}),schema) for key,schema in right['properties'].items()}
        result['required']=right['required'];result['additionalProperties']=False
    if 'items' in right:result['items']=merge_value_schemas(left.get('items',{}),right['items'])
    return result


class Pipeline:
    def __init__(self,root,output,report,years):
        self.root,self.output,self.report=[Path(p).resolve() for p in [root,output,report]]
        self.charts=self.output/'charts';self.years=sorted(years);self.state_path=self.output/'metadata/state.json'
        require(self.output.is_relative_to(self.root/'data/processed') and self.report.is_relative_to(self.root/'analysis/reports'),'Destinos fuera del área prevista.')
        self.context_cache={}
        if self.state_path.exists():
            self.state=json.loads(self.state_path.read_text(encoding='utf8'))
            require(self.state['years']==self.years and self.state['config']==CONFIG and self.state['report']==str(self.report),'Cambió el contrato; elegir destinos nuevos.')
            self.verify_protected()
        else:
            require(not self.report.exists() and not [p for p in self.output.rglob('*') if p.is_file() and p.name!='_RUNNING.json'],'Destino anterior protegido.')
            protected=snapshot_inputs(self.root,self.output,self.charts)
            for directory in ['src','public','analysis/scripts','docs']:
                for p in (self.root/directory).rglob('*'):
                    if p.is_file() and '__pycache__' not in p.parts and p.name not in OWN_FILES:protected[str(p)]=file_hash(p)
            protected[str(self.root/'.gitignore')]=file_hash(self.root/'.gitignore')
            self.state=dict(started=utc(),status='running',years=self.years,config=CONFIG,report=str(self.report),protected_hashes=protected,stages={},errors=[])
            write_json(self.state_path,self.state)

    def verify_protected(self):
        for p,digest in self.state['protected_hashes'].items():require(file_hash(p)==digest,'Entrada previa alterada: '+p)

    def valid_stage(self,name):
        marker=self.output/f'metadata/checkpoint_{name}.json'
        if not marker.exists():return False
        m=json.loads(marker.read_text())
        for relative,digest in m['artifacts'].items():require(file_hash(self.root/relative)==digest,'Checkpoint alterado: '+relative)
        return True

    def checkpoint(self,name,paths,started,summary):
        record=dict(status='complete',stage=name,finished=utc(),seconds=time.monotonic()-started,memory=memory_estimate(),summary=summary,
            artifacts={str(p.relative_to(self.root)):file_hash(p) for p in dict.fromkeys(paths)},script_sha256=file_hash(Path(__file__)))
        write_json(self.output/f'metadata/checkpoint_{name}.json',record);self.state['stages'][name]=dict(summary=summary,seconds=record['seconds']);write_json(self.state_path,self.state)
        print(f'Etapa {name}: {summary}',flush=True)

    def table(self,relative,frame):
        p=self.output/relative
        if p.exists():
            if p.suffix=='.parquet':pd.testing.assert_frame_equal(frame,pd.read_parquet(p),check_dtype=False)
            else:require(p.read_bytes()==frame.to_csv(index=False).encode('utf-8-sig'),'Tabla parcial distinta: '+str(p))
        else:write_table(p,frame)
        return p

    def descriptive(self,name,year):
        return pd.read_parquet(self.root/f'data/processed/descriptive/{name}/table.parquet').query('election_year == @year').reset_index(drop=True)

    def audit(self):
        started=time.monotonic();paths=[];rows=[];incidents=[];dictionaries=json.loads((self.root/'data/processed/technical_cleaned/metadata/source_dictionaries.json').read_text(encoding='utf8'))
        for name in ['technical_cleaned','descriptive','profile_candidates_review','participation_pattern_review','multidimensional_profile_review','archetypal_stability_review','contextual_feature_review']:
            folder=self.root/'data/processed'/name;mp=folder/'metadata/run_manifest.json';m=json.loads(mp.read_text(encoding='utf8'))
            marker=json.loads((folder/'_SUCCESS').read_text());require(m['status']=='validated' and marker['manifest_sha256']==file_hash(mp),'Fuente sin validar: '+name)
            for relative,digest in m.get('artifact_hashes',{}).items():
                path=self.root/relative;current=self.state['protected_hashes'].get(str(path))
                if current is None:
                    current=file_hash(path);self.state['protected_hashes'][str(path)]=current
                if current!=digest and name=='descriptive' and path==self.root/'analysis/scripts/build_descriptive.py':
                    corroboration=[]
                    for later in ['profile_candidates_review','participation_pattern_review','multidimensional_profile_review','archetypal_stability_review']:
                        document=json.loads((self.root/f'data/processed/{later}/metadata/run_manifest.json').read_text(encoding='utf8'))
                        if document.get('protected_hashes',{}).get(str(path))==current:corroboration.append(later)
                    require(len(corroboration)>=2,'Deriva de código sin procedencia suficiente.')
                    incidents.append(dict(kind='legacy_code_hash_drift',path=str(path.relative_to(self.root)),declared_sha256=digest,
                        current_sha256=current,corroborating_later_manifests=corroboration,
                        treatment='Se preservan script y manifiesto anteriores; datos descriptivos verificados por files[].sha256 y regresión numérica 2024 obligatoria.'))
                else:require(current==digest,'Fuente distinta: '+relative)
            if name=='technical_cleaned':
                for part in m['parts']:require(self.state['protected_hashes'][str(folder/part['path'])]==part['sha256'],'Parquet limpio modificado.')
        for year in YEARS:
            age=self.descriptive('age_sex_year',year);b=pd.read_parquet(self.root/f'analysis/reports/representation_evaluation/grouped_candidates/broad/part-{year}.parquet')
            types=self.descriptive('section_type_year',year);mun=self.descriptive('municipality',year)
            expected_sexes=['0','1']+(['2'] if year==2024 else [])
            require(set(age.SEXO)==set(expected_sexes) and set(types.TIPOSEC)==set(TYPES),'Categorías inesperadas.')
            text='\n'.join(i['text'] for i in dictionaries[str(year)])
            require('cumplidos al día de la elección' in text and '0 Hombres' in text and '1 Mujeres' in text,'Definiciones históricas no verificadas.')
            reference=2023 if year==2024 else 2021;require(set(mun.district_reference_year)=={reference},'Marco distrital inesperado.')
            rows.append(dict(election_year=year,min_age=int(age.age_value.min()),max_age=int(age.age_value.max()),sex_codes='|'.join(expected_sexes),
                section_type_codes='|'.join(sorted(types.TIPOSEC)),district_reference_year=reference,municipalities=len(mun),source_rows=int(b.source_row_count.sum()),
                LN=int(b.LN.sum()),SV=int(b.SV.sum()),NV=int(b.NV.sum()),NS=int(b.NS.sum()),
                dictionary_sha256=hashlib.sha256(text.encode()).hexdigest(),ns_jurisdiction_item_explicit='jurisdiccional' in text,
                age_definition_compatible=True,sex_hm_definition_compatible=True,territorial_longitudinal_compatible=False))
        paths.append(self.table('metadata/historical_audit.csv',pd.DataFrame(rows)))
        write_json(self.output/'metadata/input_incidents.json',incidents);paths.append(self.output/'metadata/input_incidents.json')
        write_json(self.state_path,self.state)
        write_json(self.output/'metadata/source_dictionaries.json',dictionaries);paths.append(self.output/'metadata/source_dictionaries.json')
        self.checkpoint('audit',paths,started,dict(elections=6,csv_reads=0,model_fits=0))

    def context(self,year):
        if year in self.context_cache:return self.context_cache[year]
        if year==2024:
            source=self.root/'data/processed/contextual_feature_review/reference'
            children=pd.read_parquet(source/'section_segments_broad.parquet');inventory=pd.read_parquet(source/'section_inventory_2024.parquet')
            inventory.insert(0,'election_year',year)
            self.context_cache[year]=(children,inventory);return children,inventory
        dataset=open_dataset(self.root/'data/processed/technical_cleaned')
        source_mun=self.descriptive('municipality',year);child_parts=[];inventory_parts=[]
        for state in source_mun.EDOCVE.unique():
            stage=f'context_{year}_{state}';folder=f'context_cache/{year}/{state}'
            if not self.valid_stage(stage):
                started=time.monotonic();sums=[];section_parts=[];inventories=[];rows=0
                batches=dataset.scanner(columns=['election_year','state_code',*MUNICIPAL_KEYS,'age_value','SEXO','SECCION','TIPOSEC',*SOURCE_COUNTS],
                    filter=(ds.field('election_year')==year)&(ds.field('state_code')==state),batch_size=CONFIG['batch_size']).to_batches()
                for batch in batches:
                    f=batch.to_pandas().rename(columns=SOURCE_COUNTS);rows+=len(f)
                    require(f.election_year.eq(year).all() and f.EDOCVE.eq(state).all(),'Lectura fuera de partición.')
                    require(set(f.TIPOSEC)<=set(TYPES) and f.TIPOSEC.notna().all(),'Tipo de sección no compatible.')
                    require(set(f.SEXO)<={'0','1'},'Categoría de sexo histórica no prevista.')
                    f['age_band']=age_bands(f.age_value);f['source_row_count']=1;f['sex_2_source_rows']=0;f['sex_2_nominal_count']=0
                    require(f.LN.eq(f.SV+f.NV+f.NS).all(),'Conteos no conciliados en bloque.')
                    sums.append(group_counts(f,SEGMENT_KEYS+['TIPOSEC']))
                    section_parts.append(f[SEGMENT_KEYS+['TIPOSEC','SECCION']].drop_duplicates())
                    inventories.append(f[MUNICIPAL_KEYS+['SECCION','TIPOSEC']].drop_duplicates())
                    if len(sums)>=8:
                        sums=[group_counts(pd.concat(sums,ignore_index=True),SEGMENT_KEYS+['TIPOSEC'])]
                        section_parts=[pd.concat(section_parts,ignore_index=True).drop_duplicates()]
                        inventories=[pd.concat(inventories,ignore_index=True).drop_duplicates()]
                require(rows>0,'Entidad sin registros.')
                children=group_counts(pd.concat(sums,ignore_index=True),SEGMENT_KEYS+['TIPOSEC'])
                distinct=pd.concat(section_parts,ignore_index=True).drop_duplicates().groupby(SEGMENT_KEYS+['TIPOSEC'],as_index=False,observed=True).size().rename(columns={'size':'section_count'})
                children=children.merge(distinct,on=SEGMENT_KEYS+['TIPOSEC'],validate='one_to_one');children.insert(0,'election_year',year)
                inventory=pd.concat(inventories,ignore_index=True).drop_duplicates();inventory.insert(0,'election_year',year)
                require(not inventory.duplicated(MUNICIPAL_KEYS+['SECCION']).any(),'Sección municipal con tipos incompatibles.')
                paths=[self.table(folder+'/children.parquet',children),self.table(folder+'/inventory.parquet',inventory)]
                self.checkpoint(stage,paths,started,dict(rows=rows,sections=len(inventory),groups=len(children)))
            child_parts.append(pd.read_parquet(self.output/folder/'children.parquet'));inventory_parts.append(pd.read_parquet(self.output/folder/'inventory.parquet'))
        result=pd.concat(child_parts,ignore_index=True),pd.concat(inventory_parts,ignore_index=True)
        self.context_cache[year]=result;return result

    def build_year(self,year):
        """Cálculo puro por elección; todas las referencias pertenecen a ese año."""
        require(year in YEARS,'Elección no admitida.')
        broad=pd.read_parquet(self.root/f'analysis/reports/representation_evaluation/grouped_candidates/broad/part-{year}.parquet')
        require(broad.election_year.eq(year).all() and not broad.duplicated(SEGMENT_KEYS).any(),'Segmentos de otra elección o duplicados.')
        children,inventory=self.context(year);broad=add_context(broad,children)
        municipalities=self.descriptive('municipality',year);states=self.descriptive('state',year);year_table=self.descriptive('year',year)
        broad=broad.merge(municipalities[MUNICIPAL_KEYS+['state_name_label','municipality_name_label','district_reference_year']],on=MUNICIPAL_KEYS,validate='many_to_one')
        segments,national=assign_candidates(broad)
        segments['relative_turnout']=segments.participation_delta;segments['election_year']=year
        segments.insert(0,'row_id',segments[SEGMENT_KEYS].astype(str).agg('|'.join,axis=1).map(lambda key:f'segment_{year}|'+key))
        national.insert(0,'election_year',year)
        summary=summarize_profiles(segments,int(year_table.LN.iloc[0]));summary.insert(0,'election_year',year)
        continuous,gaps,municipalities=build_continuous(segments,municipalities,year)
        for territorial,keys in [(municipalities,MUNICIPAL_KEYS),(states,['EDOCVE'])]:
            sizes=inventory.groupby(keys,as_index=False).agg(section_count=('SECCION','nunique'))
            if keys==['EDOCVE']:sizes=inventory.drop_duplicates(['EDOCVE','SECCION']).groupby('EDOCVE',as_index=False).size().rename(columns={'size':'section_count'})
            lookup=sizes.set_index(keys).section_count
            territorial['section_count']=[int(lookup.loc[tuple(r) if len(keys)>1 else r[0]]) for r in territorial[keys].itertuples(index=False,name=None)]
            kind_totals=self.descriptive('municipality_section_type',year)
            if keys==['EDOCVE']:kind_totals=group_counts(kind_totals,['EDOCVE','TIPOSEC'])
            for kind in TYPES:
                sub=kind_totals[kind_totals.TIPOSEC.eq(kind)].set_index(keys).LN
                territorial['LN_'+kind]=[int(sub.get(tuple(r) if len(keys)>1 else r[0],0)) for r in territorial[keys].itertuples(index=False,name=None)]
                territorial['section_ln_share_'+kind]=safe_ratio(territorial['LN_'+kind],territorial.LN)
            assigned=segments[segments.candidate_id.notna()]
            chosen=assigned.groupby(keys).agg(supported_segments=('row_id','size'),supported_LN=('LN','sum'))
            territorial['supported_segments']=[int(chosen.supported_segments.get(tuple(r) if len(keys)>1 else r[0],0)) for r in territorial[keys].itertuples(index=False,name=None)]
            territorial['supported_LN']=[int(chosen.supported_LN.get(tuple(r) if len(keys)>1 else r[0],0)) for r in territorial[keys].itertuples(index=False,name=None)]
            territorial['supported_nominal_fraction']=safe_ratio(territorial.supported_LN,territorial.LN)
        compare_sums(segments,states,['EDOCVE']);compare_sums(segments,municipalities,MUNICIPAL_KEYS)
        require(int(segments.source_row_count.sum())==int(year_table.source_row_count.iloc[0]),'Pérdida de filas fuente.')
        return dict(segments=segments,national_references=national,profiles=summary,continuous=continuous,sex_gaps=gaps,
            municipalities=municipalities,states=states,year=year_table,
            section_segments=add_rates(children[['election_year',*SEGMENT_KEYS,'TIPOSEC',*METRICS,'section_count']]),section_inventory=inventory,
            age_statistics=self.descriptive('age_sex_year',year),sex_statistics=self.descriptive('sex_year',year),section_statistics=self.descriptive('section_type_year',year))

    def regression_2024(self):
        started=time.monotonic();data=self.build_year(2024);checks=[]
        def compare(name,left,right,keys,columns):
            require(not left.duplicated(keys).any() and not right.duplicated(keys).any(),'Claves duplicadas en regresión: '+name)
            a=left.set_index(keys).sort_index();b=right.set_index(keys).sort_index()
            require(a.index.equals(b.index),'Cobertura distinta en regresión: '+name)
            maximum=0.
            for column in columns:
                la,rb=a[column],b[column]
                if pd.api.types.is_numeric_dtype(la) and pd.api.types.is_numeric_dtype(rb):
                    av,bv=la.to_numpy(float),rb.to_numpy(float)
                    require(np.allclose(av,bv,atol=CONFIG['regression_atol'],rtol=0,equal_nan=True),'Diferencia de regresión: '+name+'/'+column)
                    finite=np.isfinite(av)&np.isfinite(bv)
                    if finite.any():maximum=max(maximum,float(np.max(abs(av[finite]-bv[finite]))))
                else:require(la.astype('string').fillna('__NULL__').equals(rb.astype('string').fillna('__NULL__')),'Categoría/flag distinto: '+name+'/'+column)
            checks.append(dict(check=name,rows=len(a),fields=len(columns),max_absolute_difference=maximum,status='passed'))
        old=self.root/'data/processed/profile_candidates_review'
        reference=pd.read_parquet(old/'reference/segments_2024.parquet')
        common=[*METRICS,'specified_count','local_turnout','national_rate','participation_delta','unspecified_rate','in_scope','low_ln','low_specified','few_source_rows','sufficient_support','high_ns','direction','near_reference','rule_candidate_id','assignment_status','candidate_id','section_count',
            *[m+'_'+t for t in TYPES for m in METRICS+['section_count']],*['section_ln_share_'+t for t in TYPES]]
        compare('segments_counts_references_flags_context',data['segments'],reference,SEGMENT_KEYS,common)
        compare('national_references',data['national_references'],pd.read_parquet(old/'reference/national_reference.parquet'),['age_band','SEXO'],METRICS+['national_rate','national_specified_count'])
        summary=pd.read_parquet(old/'candidates/summary.parquet')
        compare('six_profiles',data['profiles'],summary,['candidate_id'],[c for c in summary if c!='r2_missing_segments' and c!='candidate_id'])
        patterns=pd.read_parquet(self.root/'data/processed/participation_pattern_review/reference/profiles.parquet')
        new=data['continuous'].copy();suffixes=['18_34','35_59','60_100']
        for j,suffix in enumerate(suffixes):
            for metric in METRICS+['specified_count','unspecified_rate','national_rate']:
                if metric+'_'+suffix in patterns:new[metric+'_'+suffix]=new[metric+'_'+str(j)]
            new['rate_'+suffix]=new['local_turnout_'+str(j)];new['delta_'+suffix]=new['participation_delta_'+str(j)]
            new['shape_'+suffix]=new['shape_'+str(j)]
            new['supported_'+suffix]=new['supported_'+str(j)]
        fields=[*METRICS,'relative_level','mean_observed_rate','complete_profile','is_eligible','supported_coordinates','specified_count','participation_observed','unspecified_rate','has_high_ns_coordinate','pending_reason',
            *[c for c in patterns if any(c.endswith('_'+suffix) for suffix in suffixes)]]
        compare('continuous_indicators',new,patterns,PROFILE_KEYS,list(dict.fromkeys(fields)))
        previous=self.root/'data/processed/multidimensional_profile_review/reference'
        compare('adjusted_sex_gaps',data['sex_gaps'],pd.read_parquet(previous/'gaps.parquet'),MUNICIPAL_KEYS+['age_band'],['S_available','sex_gap_observed','sex_gap_adjusted','gap_max_ns'])
        compare('municipal_adjusted_indicators',data['municipalities'],pd.read_parquet(previous/'municipal_context.parquet'),MUNICIPAL_KEYS,['municipal_turnout_core','municipal_peer_reference','municipal_adjusted_turnout','municipal_core_ns'])
        require(len(data['segments'])==17735 and int(data['segments'].candidate_id.notna().sum())==14190,'Cobertura de candidatos 2024 distinta.')
        path=self.table('validation/regression_2024.csv',pd.DataFrame(checks))
        self.checkpoint('regression_2024',[path],started,dict(status='passed',checks=len(checks),tolerance=CONFIG['regression_atol']))
        return data

    def quality(self,data,year):
        s=data['segments'];c=data['continuous'];chosen=s[s.candidate_id.notna()];inventory=data['section_inventory']
        total=int(s.LN.sum());unique_sections=len(inventory.drop_duplicates(['EDOCVE','SECCION']))
        overlap=inventory.groupby(['EDOCVE','SECCION']).MPIOCVE.nunique().gt(1)
        row=dict(election_year=year,available_segments=len(s),supported_segments=len(chosen),available_municipalities=len(data['municipalities']),
            supported_municipalities=chosen.groupby(MUNICIPAL_KEYS).ngroups,supported_states=chosen.EDOCVE.nunique(),
            LN=total,SV=int(s.SV.sum()),NV=int(s.NV.sum()),NS=int(s.NS.sum()),source_row_count=int(s.source_row_count.sum()),
            sex_2_source_rows=int(s.sex_2_source_rows.sum()),sex_2_nominal_count=int(s.sex_2_nominal_count.sum()),
            supported_LN=int(chosen.LN.sum()),supported_nominal_fraction=float(chosen.LN.sum()/total),
            supported_municipality_fraction=float(chosen.groupby(MUNICIPAL_KEYS).ngroups/len(data['municipalities'])),
            continuous_profiles=len(c),supported_continuous_profiles=int(c.is_eligible.sum()),
            continuous_municipalities=c[c.is_eligible].groupby(MUNICIPAL_KEYS).ngroups,
            continuous_supported_LN=int(c.loc[c.is_eligible,'LN'].sum()),continuous_nominal_fraction=float(c.loc[c.is_eligible,'LN'].sum()/total),
            continuous_complete_profiles=int(c.complete_profile.sum()),
            high_ns_segments=int(chosen.high_ns.sum()),near_reference_supported_segments=int(chosen.near_reference.sum()),
            near_reference_supported_fraction=float(chosen.near_reference.mean()) if len(chosen) else np.nan,
            undefined_segment_rates=int(s.local_turnout.isna().sum()),undefined_continuous_profiles=int((~c.complete_profile).sum()),
            supported_exact_tie_segments=int(s.assignment_status.eq('at_reference').sum()),
            exact_tie_segments=int((s.in_scope&s.local_turnout.notna()&s.direction.eq(0)).sum()),
            few_section_supported_segments=int(chosen.section_count.lt(5).sum()),
            observed_distinct_sections=unique_sections,section_keys_in_multiple_municipalities=int(overlap.sum()),
            over_100_source_rows=int(s.loc[s.age_band.eq('101+'),'source_row_count'].sum()),over_100_LN=int(s.loc[s.age_band.eq('101+'),'LN'].sum()),
            profiles_with_support=int(data['profiles'].status.eq('supported').sum()),unspecified_rate=float(s.NS.sum()/total),
            district_reference_year=2023 if year==2024 else 2021)
        return pd.DataFrame([row])

    def exact_public(self,frame,year):
        cols=['election_year',*MUNICIPAL_KEYS,'age_value','SEXO',*METRICS,'specified_count','participation_observed','nonparticipation_observed','participation_nominal','unspecified_rate','has_low_support','has_high_unspecified_rate']
        f=frame[cols].copy();national=self.descriptive('age_sex_year',year)[['age_value','SEXO','participation_observed']].rename(columns={'participation_observed':'national_exact_age_rate'})
        f=f.merge(national,on=['age_value','SEXO'],how='left',validate='many_to_one',sort=False)
        f['relative_turnout']=f.participation_observed-f.national_exact_age_rate;f['age_over_100']=f.age_value.gt(100)
        return public_frame(f)

    def prepare_schemas(self):
        if self.valid_stage('schemas'):return
        started=time.monotonic();data=self.build_year(2024);tables=public_tables(data,2024)
        tables['quality_summary']=self.quality(data,2024)
        status=data['segments'].groupby('assignment_status',observed=True,as_index=False)[METRICS].sum();status.insert(0,'election_year',2024)
        tables['assignment_status']=status
        first=next((self.root/'data/processed/descriptive/municipality_age_sex').glob('part-2024-*.parquet'))
        tables['exact_age_segments']=self.exact_public(pd.read_parquet(first),2024)
        paths=[]
        for name,frame in tables.items():
            schema=frame_schema(frame,UNITS[name],'ParticipaMX · '+name)
            if name=='profiles':schema['properties']['data'].update(minItems=6,maxItems=6)
            p=self.output/f'schemas/{name}.schema.json';write_json(p,schema,protect=True);paths.append(p)
        self.checkpoint('schemas',paths,started,dict(resources=len(tables),version=CONFIG['version']))

    def emit(self,name,frame,year,relative=None):
        """Valida cada fila y el año antes de escribir JSON compacto, sin NaN."""
        schema=json.loads((self.output/f'schemas/{name}.schema.json').read_text(encoding='utf8'))
        payload=dict(schema_version=CONFIG['version'],election_year=year,election_type='presidential' if year in [2012,2018,2024] else 'midterm',
            unit=UNITS[name],source_id='ine_counted_lists',rate_unit='proportion',data=safe_json(frame.to_dict(orient='records')),warnings=WARNINGS)
        validate_json(payload,schema)
        require(all(row['election_year']==year for row in payload['data']),'Recurso mezcla elecciones.')
        p=self.output/(relative or f'elections/{year}/{name}.json')
        raw=json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf8')
        if p.exists():require(p.read_bytes()==raw,'Recurso parcial diferente: '+str(p))
        else:atomic_bytes(p,raw)
        # El lector y validador nunca aceptan constantes JSON no estándar.
        stored=json.loads(p.read_text(encoding='utf8'),parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))
        require(len(stored['data'])==len(frame) and stored['election_year']==year,'Lectura JSON no coincide.')
        return p

    def availability(self,data,year):
        q=self.quality(data,year).iloc[0];age=self.descriptive('age_sex_year',year);rows=[]
        available=[('national_statistics','election',1,0),('state_statistics','state',len(data['states']),0),
            ('municipality_statistics','municipality',len(data['municipalities']),0),('six_rule_profiles','rule_candidate',int(q.profiles_with_support),6-int(q.profiles_with_support)),
            ('municipality_age_band_sex','municipality_age_band_sex',int(q.supported_segments),int(q.undefined_segment_rates)),
            ('exact_age_statistics','municipality_exact_age_sex',None,None),
            ('continuous_level_shape','municipality_sex',int(q.supported_continuous_profiles),int(q.undefined_continuous_profiles)),
            ('adjusted_sex_gap','municipality_age_band',int(data['sex_gaps'].S_available.sum()),int((~data['sex_gaps'].S_available).sum())),
            ('section_context','municipality_age_band_sex',len(data['segments']),0),('distinct_sections','section',int(q.observed_distinct_sections),0)]
        for feature,unit,supported,missing in available:rows.append(dict(election_year=year,feature=feature,unit=unit,available=True,
            status='available_with_quality_flags',supported_records=supported,undefined_or_pending_records=missing,
            note='Datos propios de la elección; consultar soporte, NS y estados de cada registro.'))
        rows.extend([
            dict(election_year=year,feature='sex_2_statistics',unit='national_sex',available=year==2024,status='available_small_support' if year==2024 else 'not_recorded',
                supported_records=int(q.sex_2_source_rows) if year==2024 else None,undefined_or_pending_records=None,
                note='Categoría no binaria conservada; no se fusiona con H/M.' if year==2024 else 'El diccionario histórico no registra SEXO=2; su ausencia no significa cero personas.'),
            dict(election_year=year,feature='municipal_longitudinal_comparison',unit='municipality_history',available=False,status='blocked_unvalidated_crosswalk',supported_records=None,undefined_or_pending_records=None,
                note='No existe correspondencia territorial histórica oficial validada; sólo consultas independientes por elección.'),
            dict(election_year=year,feature='learned_model_labels',unit='model_assignment',available=False,status='not_generated',supported_records=None,undefined_or_pending_records=None,
                note='No se ajustan algoritmos ni se transfieren R2 o arquetipos aprendidos en 2024.'),
            dict(election_year=year,feature='map_geometries',unit='geometry',available=False,status='not_packaged',supported_records=None,undefined_or_pending_records=None,
                note='Se preparan claves INE y estadísticas, sin geometrías ni equivalencias INE/INEGI validadas.')])
        result=pd.DataFrame(rows)
        for name in ['supported_records','undefined_or_pending_records']:result[name]=pd.array(result[name],dtype='Int64')
        return result

    def write_year(self,year):
        stage=f'year_{year}'
        if self.valid_stage(stage):print('Elección verificada: '+str(year),flush=True);return
        started=time.monotonic();data=self.build_year(year);paths=[]
        for name,frame in data.items():paths.append(self.table(f'elections/{year}/tables/{name}.parquet',frame))
        quality=self.quality(data,year);paths.append(self.table(f'elections/{year}/tables/quality_summary.parquet',quality))
        availability=self.availability(data,year);paths.append(self.table(f'elections/{year}/tables/availability.parquet',availability))
        tables=public_tables(data,year);tables['quality_summary']=quality
        status=data['segments'].groupby('assignment_status',observed=True,as_index=False)[METRICS].sum();status.insert(0,'election_year',year)
        tables['assignment_status']=status
        for name,f in tables.items():
            if name in ['municipality_segments','municipality_profiles']:
                for state,part in f.groupby('state_code',sort=False):paths.append(self.emit(name,part,year,f'elections/{year}/{name}/{state}.json'))
            else:paths.append(self.emit(name,f,year))
        exact_counts=[]
        for state in data['states'].EDOCVE:
            stage_exact=f'exact_{year}_{state}';p=self.root/f'data/processed/descriptive/municipality_age_sex/part-{year}-{state}.parquet'
            if not self.valid_stage(stage_exact):
                exact_started=time.monotonic();source=pd.read_parquet(p)
                require(source.election_year.eq(year).all() and source.EDOCVE.eq(state).all(),'Detalle exacto fuera de elección/entidad.')
                exact=self.exact_public(source,year);out=self.emit('exact_age_segments',exact,year,f'elections/{year}/exact_age_segments/{state}.json')
                self.checkpoint(stage_exact,[out],exact_started,dict(groups=len(exact),LN=int(exact.LN.sum())))
            paths.append(self.output/f'elections/{year}/exact_age_segments/{state}.json')
            # Métricas desde el agregado original; no desde tasas ni perfiles superpuestos.
            original=pd.read_parquet(p,columns=METRICS)
            exact_counts.append(original[METRICS].sum())
        total_exact=pd.DataFrame(exact_counts).sum()
        require(all(int(total_exact[m])==int(data['year'][m].iloc[0]) for m in METRICS),'Detalle exacto no conserva conteos.')
        refs=self.descriptive('age_sex_year',year)
        gaps_data=data['sex_gaps'];resources={name:name+'.json' for name in tables if name not in ['municipality_segments','municipality_profiles']}
        resources.update(municipality_segments='municipality_segments/{state_code}.json',municipality_profiles='municipality_profiles/{state_code}.json',
            exact_age_segments='exact_age_segments/{state_code}.json',metadata='metadata.json')
        missing=pd.read_csv(self.root/'data/processed/technical_cleaned/metadata/quality_summary.csv')
        missing=missing[missing.election_year.eq(year)]
        missing_fields={c:int(missing[c].sum()) for c in ['is_federal_district_missing','is_local_district_missing'] if c in missing}
        metadata=dict(schema_version=CONFIG['version'],election_year=year,election_type='presidential' if year in [2012,2018,2024] else 'midterm',
            election_label=f'Elección {year} · '+('Presidencial' if year in [2012,2018,2024] else 'Intermedia'),
            status='validated_candidate_data',created_at_utc=self.state['started'],method='rule_based_segmentation_and_continuous_indicators',
            resources=resources,schemas={name:f'../../schemas/{name}.schema.json' for name in [*tables,'exact_age_segments']},
            state_codes=data['states'].EDOCVE.tolist(),units={name:UNITS[name] for name in [*tables,'exact_age_segments']},
            definitions=dict(observed_participation='SV/(SV+NV), NULL si SV+NV=0',nominal_participation='SV/LN',unspecified_rate='NS/LN; no abstención',
                national_reference='ΣSV/Σ(SV+NV) de la misma elección, intervalo y sexo, antes de soporte',
                relative_turnout='Participación local menos referencia nacional propia del intervalo/sexo',
                exact_age_reference='La referencia de exact_age_segments usa edad exacta y sexo, no el intervalo de las seis reglas.',
                relative_level='Media simple de las tres diferencias por edad, no participación municipal agregada',
                shape='Diferencias centradas respecto a su media; dos contrastes ortonormales conservan sus dos grados de libertad',
                adjusted_sex_gap='Diferencia de participación relativa mujeres−hombres; requiere ambos segmentos con soporte',
                distinct_sections='Clave año+entidad+sección; por municipio se distingue también la clave municipal. No sumar secciones de bandas/sexos.',
                candidate_section_union='No disponible en estos agregados; distinct_sections es NULL en las fichas. Se informa distribución por segmento.',
                empty_subset_zero='Los ceros U/R/M sólo representan subconjuntos vacíos de categorías exhaustivas observadas; no se imputan tasas ausentes.'),
            quality_thresholds=dict(min_LN=100,min_specified_count=100,min_source_rows=5,high_ns=.10,near_reference=.02),
            coordinate_order=BANDS,sex_categories=[dict(code=code,label=SEX_LABELS[code]) for code in sorted(refs.SEXO.unique())],
            age_min=int(refs.age_value.min()),age_max=int(refs.age_value.max()),main_visual_age_range=[18,100],
            district_reference_year=2023 if year==2024 else 2021,missing_district_source_cells=missing_fields,
            municipal_history_enabled=False,map_geometries=None,availability=safe_json(availability.to_dict('records')),
            source=dict(id='ine_counted_lists',description='Cuadernillos de lista nominal del INE; definiciones oficiales conservadas.',
                dictionary_path='../../metadata/source_dictionaries.json',
                technical_cleaning_manifest='data/processed/technical_cleaned/metadata/run_manifest.json',
                technical_cleaning_manifest_sha256=file_hash(self.root/'data/processed/technical_cleaned/metadata/run_manifest.json')),
            warnings=WARNINGS)
        schema={'$schema':'https://json-schema.org/draft/2020-12/schema',**value_schema(safe_json(metadata))}
        schema_path=self.output/f'schemas/metadata_{year}.schema.json';write_json(schema_path,schema,protect=True);paths.append(schema_path)
        validate_json(safe_json(metadata),schema);mp=self.output/f'elections/{year}/metadata.json';write_json(mp,metadata,protect=True);paths.append(mp)
        self.checkpoint(stage,paths,started,dict(profiles=int(quality.profiles_with_support.iloc[0]),supported_segments=int(quality.supported_segments.iloc[0]),
            supported_LN=int(quality.supported_LN.iloc[0]),municipalities=int(quality.supported_municipalities.iloc[0]),exact_groups=int(sum(len(pd.read_parquet(self.root/f'data/processed/descriptive/municipality_age_sex/part-{year}-{s}.parquet',columns=['age_value'])) for s in data['states'].EDOCVE))))

    def run(self,prepare_only=False):
        if (self.output/'_SUCCESS').exists():self.verify_success();return
        self.prepare_schemas()
        order=([2024] if 2024 in self.years else [])+[year for year in self.years if year!=2024]
        for year in order:self.write_year(year)
        if not prepare_only:
            if not self.valid_stage('historical'):self.historical()
            if not self.valid_stage('final'):self.presentation()
            self.finalize()

    def historical(self):
        started=time.monotonic();paths=[];tables={}
        for name in ['year','profiles','quality_summary','national_references','age_statistics','sex_statistics','section_statistics','states','availability']:
            tables[name]=pd.concat([pd.read_parquet(self.output/f'elections/{y}/tables/{name}.parquet') for y in self.years],ignore_index=True)
            paths.append(self.table(f'historical/{name}.parquet',tables[name]))
            paths.append(self.table(f'historical/{name}.csv',tables[name]))
        entries=[]
        for year in self.years:
            m=json.loads((self.output/f'elections/{year}/metadata.json').read_text(encoding='utf8'))
            q=tables['quality_summary'][tables['quality_summary'].election_year.eq(year)].iloc[0]
            entries.append(dict(election_year=year,election_type=m['election_type'],label=m['election_label'],base_path=f'elections/{year}/',
                metadata_path=f'elections/{year}/metadata.json',profiles_path=f'elections/{year}/profiles.json',
                municipalities_path=f'elections/{year}/municipalities.json',states_path=f'elections/{year}/states.json',
                national_references_path=f'elections/{year}/national_references.json',continuous_indicators_path=f'elections/{year}/continuous_indicators.json',
                quality_summary_path=f'elections/{year}/quality_summary.json',
                profiles_with_support=int(q.profiles_with_support),municipalities=int(q.available_municipalities),
                supported_municipalities=int(q.supported_municipalities),supported_nominal_fraction=float(q.supported_nominal_fraction),
                district_reference_year=m['district_reference_year'],municipal_history_enabled=False))
        index=dict(schema_version=CONFIG['version'],status='validated_candidate_data',default_election_year=max(self.years),
            elections=entries,historical_comparison_path='historical_comparison.json',
            availability_matrix_path='historical/availability.json',schemas_path='schemas/',
            municipal_history_enabled=False,warnings=WARNINGS)
        nonbinary=[]
        for year in self.years:
            rows=tables['sex_statistics'][(tables['sex_statistics'].election_year==year)&tables['sex_statistics'].SEXO.eq('2')]
            nonbinary.append(dict(election_year=year,status='observed' if len(rows) else 'category_not_recorded',
                LN=int(rows.LN.sum()) if len(rows) else None,SV=int(rows.SV.sum()) if len(rows) else None,
                NV=int(rows.NV.sum()) if len(rows) else None,NS=int(rows.NS.sum()) if len(rows) else None))
        comparison=dict(schema_version=CONFIG['version'],scope='repeated_election_cross_sections',rate_unit='proportion',municipal_history_enabled=False,
            definitions=dict(relative='Cada elección usa sus propios pares nacionales; mismo ID no significa misma población.',
                national_reference='Todas las celdas, antes de filtrar soporte.',
                people='No son trayectorias individuales; los registros nominales de elecciones distintas no son personas únicas.',
                election_context='Presidenciales 2012/2018/2024 e intermedias 2009/2015/2021; no atribuir diferencias exclusivamente a conducta ciudadana.'),
            tables={name:safe_json(public_frame(tables[name]).to_dict('records')) for name in ['year','profiles','quality_summary','national_references','age_statistics','sex_statistics','section_statistics','states']},
            nonbinary_availability=nonbinary,warnings=WARNINGS)
        for filename,obj in [('elections_index',index),('historical_comparison',comparison)]:
            schema={'$schema':'https://json-schema.org/draft/2020-12/schema',**value_schema(safe_json(obj))}
            validate_json(safe_json(obj),schema)
            sp=self.output/f'schemas/{filename}.schema.json';write_json(sp,schema,protect=True);paths.append(sp)
            jp=self.output/(filename+'.json');write_json(jp,obj,protect=True);paths.append(jp)
        availability=dict(schema_version=CONFIG['version'],unit='election_feature',data=safe_json(tables['availability'].to_dict('records')))
        ap=self.output/'historical/availability.json';write_json(ap,availability,protect=True);paths.append(ap)
        changes=[]
        profiles=tables['profiles']
        for before,after in zip(self.years[:-1],self.years[1:]):
            left=profiles[profiles.election_year==before].set_index('candidate_id');right=profiles[profiles.election_year==after].set_index('candidate_id')
            for profile in IDS:changes.append(dict(from_year=before,to_year=after,profile_id=profile,
                nominal_fraction_before=float(left.loc[profile,'nominal_coverage']),nominal_fraction_after=float(right.loc[profile,'nominal_coverage']),
                nominal_difference_pp=float((right.loc[profile,'nominal_coverage']-left.loc[profile,'nominal_coverage'])*100),
                segments_before=int(left.loc[profile,'segments']),segments_after=int(right.loc[profile,'segments']),
                interpretation='Diferencia de distribuciones transversales, no transición individual o municipal.'))
        change_columns=['from_year','to_year','profile_id','nominal_fraction_before','nominal_fraction_after','nominal_difference_pp',
            'segments_before','segments_after','interpretation']
        paths.append(self.table('historical/profile_distribution_changes.csv',pd.DataFrame(changes,columns=change_columns)))
        clean=pd.read_csv(self.root/'data/processed/technical_cleaned/metadata/state_validation.csv',dtype={'EDOCVE':str})
        validations=[]
        for year in self.years:
            segment=pd.read_parquet(self.output/f'elections/{year}/tables/segments.parquet')
            grouped=group_counts(segment,['EDOCVE']).set_index('EDOCVE')
            baseline=clean[clean.election_year.eq(year)].set_index('EDOCVE')
            require(grouped.index.sort_values().equals(baseline.index.sort_values()),'Entidades distintas de limpieza.')
            for state in grouped.index:
                record=dict(election_year=year,EDOCVE=state)
                for m in COUNTS:
                    delta=int(grouped.loc[state,m])-int(baseline.loc[state,'source_sum_'+m]);require(delta==0,'Suma estatal difiere de fuente.')
                    record['difference_'+m]=delta
                record['difference_source_rows']=int(grouped.loc[state,'source_row_count'])-int(baseline.loc[state,'source_rows'])
                require(record['difference_source_rows']==0,'Filas estatales no conciliadas.');validations.append(record)
        paths.append(self.table('validation/state_reconciliation.csv',pd.DataFrame(validations)))
        intensity=[];quality_reasons=[];continuous_summary=[]
        for year in self.years:
            segment=pd.read_parquet(self.output/f'elections/{year}/tables/segments.parquet')
            for candidate in IDS:
                group=segment[segment.candidate_id.eq(candidate)]
                for threshold in CONFIG['intensity_thresholds']:
                    near=group.participation_delta.abs().le(threshold)
                    intensity.append(dict(election_year=year,profile_id=candidate,threshold_pp=100*threshold,
                        segments=len(group),near_segments=int(near.sum()),near_LN=int(group.loc[near,'LN'].sum()),
                        near_fraction=float(near.mean()) if len(group) else np.nan))
            for flag in ['low_ln','low_specified','few_source_rows','high_ns']:
                mask=segment.in_scope&segment[flag]
                quality_reasons.append(dict(election_year=year,reason=flag,segments=int(mask.sum()),LN=int(segment.loc[mask,'LN'].sum()),
                    municipalities=segment.loc[mask].groupby(MUNICIPAL_KEYS).ngroups,overlapping_flags=True))
            continuous=pd.read_parquet(self.output/f'elections/{year}/tables/continuous.parquet')
            for sex in ['0','1']:
                group=continuous[continuous.SEXO.eq(sex)&continuous.is_eligible]
                for metric in ['relative_level','young_older_difference','shape_0','shape_1','shape_2']:
                    continuous_summary.append(dict(election_year=year,SEXO=sex,indicator=metric,profiles=len(group),
                        mean=float(group[metric].mean()),q1=float(group[metric].quantile(.25)),median=float(group[metric].median()),
                        q3=float(group[metric].quantile(.75)),unit='proportion_difference',weight='equal_municipality_sex_profile'))
        paths.append(self.table('historical/intensity_sensitivity.csv',pd.DataFrame(intensity)))
        paths.append(self.table('historical/quality_reasons.csv',pd.DataFrame(quality_reasons)))
        paths.append(self.table('historical/continuous_distributions.csv',pd.DataFrame(continuous_summary)))
        # No hay series municipales en el contrato histórico ni etiquetas aprendidas transferidas.
        def scan_keys(value):
            if isinstance(value,dict):
                require('municipality_code' not in value and 'MPIOCVE' not in value,'Historia municipal no autorizada.')
                for item in value.values():scan_keys(item)
            elif isinstance(value,list):
                for item in value:scan_keys(item)
        scan_keys(comparison)
        guide='''# Integración multianual preparada para React

Los componentes actuales de `src/` son pantallas de presentación sin un cargador de datos. Este paquete prepara sus contratos y recursos; no modifica React ni publica en `public/data`.

1. Leer `elections_index.json` y poblar el selector usando `elections[].election_year` y `label`.
2. Al cambiar la elección, limpiar municipio/perfil activo y cargar sus recursos mediante las rutas del índice. La identidad siempre incluye elección + entidad + municipio; nunca reutilizar el objeto de otro año sólo porque coincide su código.
3. `profiles.json` contiene seis candidatos por reglas, con su estado; un candidato sin segmentos con soporte mantiene tasas NULL. `national_statistics.json`, `age_statistics.json`, `sex_statistics.json` y `section_statistics.json` alimentan los indicadores propios de la elección.
4. `states.json` y `municipalities.json` describen los territorios observados ese año. Para un municipio, cargar `municipality_segments/{state_code}.json`, `municipality_profiles/{state_code}.json` y, si se necesita edad exacta, `exact_age_segments/{state_code}.json`. Filtrar por ambos códigos textuales. Las rutas se resuelven respecto de `base_path` de la elección.
5. `continuous_indicators.json` usa municipio × sexo; `sex_gaps.json` usa municipio × intervalo. Sus conteos no se suman entre sí ni a los segmentos. Mostrar soporte y cobertura antes de interpretar forma o brechas. No contiene etiquetas R2/arquetipos.
6. Las tasas se almacenan como proporciones. Mostrar 100×tasa como porcentaje y 100×diferencia como puntos porcentuales. Si un valor es NULL, mostrar «No disponible»; no usar `value || 0`, porque cero puede ser un valor válido.
7. Los indicadores de contexto son proporciones de LN por tipo de sección electoral. No equivalen a residencia urbana/rural individual. `distinct_sections` de una ficha es NULL: no se dispone de unión de claves por candidato en los agregados comunes, aunque sí de conteos por segmento e inventarios territoriales.
8. `historical_comparison.json` es una vista de cortes transversales nacionales/estatales y distribuciones. `municipal_history_enabled=false` bloquea comparaciones municipales longitudinales. No hay geometrías en este paquete; deben validarse catálogo/cartografía y correspondencias antes de activar un mapa.

Las advertencias y categorías disponibles se leen de `metadata.json`, no se suponen desde 2024. SEXO=2 no existe como categoría registrada en las elecciones anteriores: no dibujar ceros históricos. Edades >100 siguen en los archivos; 18–100 es la vista principal recomendada y el núcleo de las seis reglas, no una corrección de edad.

Los esquemas son JSON Schema 2020-12. Se incluye un validador local del subconjunto declarado y pruebas semánticas. Deben añadirse validaciones con un motor estándar al integrar si se necesita ampliar el lenguaje. No es un contrato idéntico al v1 fijado a 2024: v2 conserva conceptos/identificadores y añade el año como dimensión obligatoria.
'''
        gp=self.output/'integration/README.md';atomic_bytes(gp,guide.encode('utf8'));paths.append(gp)
        self.checkpoint('historical',paths,started,dict(elections=self.years,state_controls=len(validations),source_rows=int(tables['year'].source_row_count.sum()),municipal_longitudinal=False))

    def write_report(self):
        """Informe con resultados calculados; sin extrapolar transiciones municipales."""
        read=lambda name:pd.read_parquet(self.output/f'historical/{name}.parquet')
        year=read('year');profiles=read('profiles');quality=read('quality_summary');reference=read('national_references')
        audit=pd.read_csv(self.output/'metadata/historical_audit.csv');availability=read('availability')
        intensity=pd.read_csv(self.output/'historical/intensity_sensitivity.csv')
        changes=pd.read_csv(self.output/'historical/profile_distribution_changes.csv')
        regression=pd.read_csv(self.output/'validation/regression_2024.csv')
        continuous=pd.read_csv(self.output/'historical/continuous_distributions.csv')
        q=quality.copy();q['LN_coverage_pct']=100*q.supported_nominal_fraction
        q['municipality_coverage_pct']=100*q.supported_municipality_fraction
        q['continuous_LN_pct']=100*q.continuous_nominal_fraction
        y=year.copy();y['turnout_pct']=100*y.participation_observed;y['NS_pct']=100*y.unspecified_rate
        y['election_type']=np.where(y.election_year.isin([2012,2018,2024]),'Presidencial','Intermedia')
        p=profiles.copy()
        for field in ['participation_observed','matched_peer_reference','nominal_coverage','unspecified_rate','near_reference_fraction']:
            p[field+'_pct']=100*p[field]
        p['delta_pp']=100*p.participation_delta
        shares=p.pivot(index='election_year',columns='candidate_id',values='nominal_coverage_pct').reindex(columns=IDS).reset_index()
        percent_reference=reference[reference.age_band.isin(BANDS)&reference.SEXO.isin(['0','1'])].copy()
        percent_reference['rate_pct']=100*percent_reference.national_rate
        peer=percent_reference.pivot(index=['age_band','SEXO'],columns='election_year',values='rate_pct').reset_index()
        sex=read('sex_statistics').copy();sex['turnout_pct']=100*sex.participation_observed;sex['NS_pct']=100*sex.unspecified_rate
        section=read('section_statistics').copy()
        total=year.set_index('election_year').LN
        section['LN_share_pct']=[100*ln/total.loc[yr] for yr,ln in zip(section.election_year,section.LN)]
        section['turnout_pct']=100*section.participation_observed
        section_table=section.pivot(index='election_year',columns='TIPOSEC',values='LN_share_pct').reset_index()
        dist=continuous[continuous.indicator.isin(['relative_level','young_older_difference'])].copy()
        for field in ['mean','q1','median','q3']:dist[field+'_pp']=100*dist[field]
        max_change=changes.iloc[changes.nominal_difference_pp.abs().argmax()] if len(changes) else None
        source_rows=int(year.source_row_count.sum());protected=len(self.state['protected_hashes'])
        json_size=sum(path.stat().st_size for path in (self.output/'elections').rglob('*.json'))/2**20
        parts=[]
        def add(text):parts.append(text)
        def table(frame,columns):parts.append(table_text(frame[columns])+'\n')
        add('# Análisis electoral multianual independiente · 2009–2024\n')
        add(f'**Se construyeron {len(self.years)} análisis completos con la misma metodología, referencias propias y contratos comunes.** Elecciones procesadas: '+', '.join(map(str,self.years))+'. Los seis candidatos por reglas tienen segmentos con soporte en todas las elecciones de esta entrega. El paquete permite preparar un selector de elección con datos nacionales, estatales y municipales propios; su conexión al frontend queda pendiente, conforme a la restricción de no modificar React ni `public/data`. No se entrenó ningún algoritmo ni se transfirieron etiquetas de 2024.\n')
        add('Se leyeron los informes de candidatos, patrones, representación multidimensional y estabilidad de arquetipos, además de la limpieza técnica y sus diccionarios. Se reutilizan los agregados históricos y los contextos validados de 2024. Para recuperar U/R/M y secciones por intervalo/sexo en 2009–2021 se recorrieron por bloques los Parquet limpios, exclusivamente sus columnas necesarias. No se releen los CSV originales, no se repiten auditorías de registros ni ajustes de modelos. El detalle de edad exacta procede de los agregados descriptivos existentes.\n')
        add('## Unidades, reglas y denominadores\n')
        add('Las fichas usan **municipio × intervalo × sexo**; nivel y forma usan **municipio × sexo**, con tres coordenadas; las brechas usan **municipio × intervalo**. El municipio total incluye todas las edades y categorías. Son vistas alternativas: sus conteos no se suman entre sí. Las filas fuente son celdas originales, no personas ni secciones independientes. La misma clave entre años no identifica un territorio de límites constantes.\n')
        add('Participación local = SV/(SV+NV), NULL cuando SV+NV=0. NS permanece independiente. La referencia r se calcula por **la misma elección, intervalo y sexo antes de soporte**, como ΣSV/Σ(SV+NV); diferencia d = participación local − r. No se promedian tasas municipales ni se utiliza una referencia de 2024 para otros años. Los signos se calculan mediante productos cruzados de enteros Python; un empate exacto permanece `at_reference`. Los identificadores young/adult/older × favorable/unfavorable se conservan, con año obligatorio. Las bandas 18–34, 35–59 y 60–100 son reglas de diseño, no agrupamientos aprendidos ni límites de edad válidos.\n')
        add('Soporte: LN≥100, SV+NV≥100 y filas fuente≥5, H/M y edades 18–100. NS/LN≥10 % advierte cobertura, sin excluir automáticamente. Cerca de cero significa |d|≤2 pp; también se conserva sensibilidad a 1 y 5 pp. Las categorías >100 y SEXO=2 siguen en referencia, totales y recursos complementarios. `rule_candidate_id` conserva el signo sin soporte; `profile_id`/`candidate_id` sólo asigna fichas con soporte. Los estados son disjuntos; las banderas de calidad pueden superponerse.\n')
        add('## Disponibilidad y diferencias estructurales\n')
        table(audit,['election_year','min_age','max_age','sex_codes','section_type_codes','district_reference_year','municipalities','source_rows'])
        add('La edad es cumplida al día de la elección; H/M mantiene códigos 0/1 y U/R/M representa sección Urbana/Rural/Mixta en los diccionarios conservados. SEXO=2 aparece sólo en 2024: 105 filas fuente y LN=105, sin fusionarse con H/M. Las tablas contables históricas preservan los ceros de métricas de control de SEXO=2, pero la API de disponibilidad indica **categoría no registrada y conteos NULL** antes de 2024: no afirma cero personas no binarias.\n')
        add('La definición conceptual de NS es no especificación, pero la lista histórica de situaciones incluye una petición jurisdiccional explícita que no figura en la enumeración de 2024. Se conserva esa diferencia documental; no se fuerza igualdad de procesos de captura. Los datos reportados de cuadernillos no incluyen casillas especiales ni voto del extranjero según su diccionario. LN no es un censo validado de personas únicas. Los campos distritales faltantes se contabilizan por año en `metadata.json`; no se inventan distritos ni equivalencias entre marcos 2021 y 2023.\n')
        add('La matriz `historical/availability.csv` contiene una fila por elección y funcionalidad, con unidad, estado, base con soporte y pendientes. Nacional, entidad, municipio, edad exacta, edad/sexo, seis reglas, nivel/forma, brecha ajustada, U/R/M e inventarios de secciones están disponibles en los seis años, con las advertencias de calidad de cada registro. No se empaquetan geometrías cartográficas, correspondencias municipales históricas ni etiquetas de modelos aprendidos.\n')
        add('## Conteos, participación y cobertura por elección\n')
        table(y,['election_year','election_type','LN','SV','NV','NS','turnout_pct','NS_pct'])
        add('Porcentajes calculados sobre todos los conteos anuales, incluidas edades complementarias. Presidenciales: 2012, 2018 y 2024; intermedias: 2009, 2015 y 2021. Son cortes transversales repetidos, no trayectorias individuales. Las diferencias de participación no identifican por sí mismas cambios conductuales o efectos del tipo de elección.\n')
        add('![Participación y no especificación](../../data/processed/participamx_multiyear/charts/national_participation_and_ns.png)\n')
        table(q,['election_year','available_segments','supported_segments','supported_municipalities','available_municipalities','LN_coverage_pct','municipality_coverage_pct','undefined_segment_rates','high_ns_segments','near_reference_supported_segments'])
        add('LN_coverage_pct usa como denominador **todo el LN anual**; municipality_coverage_pct usa los municipios observados de esa elección. Se cuenta la unión de municipios clasificados, nunca la suma de las seis fichas. NULL, falta de soporte, empates y complementos permanecen en los Parquet/JSON originales del nuevo paquete. `historical/quality_reasons.csv` separa LN, especificados, filas fuente y NS; sus banderas se superponen y no se suman como exclusiones únicas.\n')
        add('![Cobertura anual](../../data/processed/participamx_multiyear/charts/coverage_by_election.png)\n')
        add('## Referencias propias por edad y sexo\n')
        table(peer,['age_band','SEXO',*self.years])
        add('La tabla muestra porcentajes H/M de las tres bandas antes de soporte. Cada `national_references.json` incluye conteos y referencias completas, también categorías complementarias cuando existen. `age_statistics.json` aporta edad exacta × sexo nacional; `exact_age_segments/{state_code}.json` conserva el detalle municipal y una referencia de **edad exacta y sexo**, distinta de la referencia por intervalo usada para las seis fichas. No se sustituyen unas por otras.\n')
        table(sex,['election_year','SEXO','LN','turnout_pct','NS_pct'])
        add('![Referencias nacionales](../../data/processed/participamx_multiyear/charts/age_sex_references.png)\n')
        add('## Seis candidatos por elección e intensidad\n')
        table(p,['election_year','candidate_id','segments','municipalities','states','LN','participation_observed_pct','matched_peer_reference_pct','delta_pp','near_reference_fraction_pct'])
        add('La referencia de cada ficha ajusta su mezcla local: Σ(denominador del segmento × referencia de su banda/sexo)/Σdenominador. Delta es la resta de esa referencia a ΣSV/Σ(SV+NV); no equivale a la media simple de las diferencias, que se guarda por separado con cuartiles y extremos. Los municipios de distintas fichas se superponen. Los rótulos describen nivel relativo, sin inferir motivaciones, preferencias políticas o tipos de personas.\n')
        add('Distribución como porcentaje de **todo el LN de la elección**:\n')
        table(shares,['election_year',*IDS])
        if max_change is not None:
            add(f'Entre elecciones consecutivas, el mayor cambio absoluto de una cuota es **{max_change.nominal_difference_pp:+.2f} pp**, {max_change.profile_id}, {int(max_change.from_year)}→{int(max_change.to_year)}. `historical/profile_distribution_changes.csv` contiene {len(changes)} contrastes. Son cambios de distribución entre poblaciones reportadas; no transiciones de los mismos segmentos o municipios.\n')
        add('![Distribución de perfiles](../../data/processed/participamx_multiyear/charts/profile_nominal_distribution.png)\n')
        near=intensity[intensity.threshold_pp.eq(2)].groupby('election_year',as_index=False).agg(near_segments=('near_segments','sum'),near_LN=('near_LN','sum'))
        table(near,['election_year','near_segments','near_LN'])
        add('Los segmentos próximos a la frontera mantienen su etiqueta y advertencia; un signo pequeño no representa una discontinuidad electoral. `historical/intensity_sensitivity.csv` documenta 1/2/5 pp por perfil y año. Las fichas conservan fracción de NS alto y distribuciones de denominadores/secciones; no se confunde estabilidad descriptiva del signo con incertidumbre estadística o un intervalo de confianza.\n')
        add('## Indicadores continuos y brechas\n')
        add('Para cada municipio/sexo se guardan las tres diferencias d, nivel m=media simple(d), contraste joven−mayor=d18–34−d60–100 y forma centrada s=d−m. Dos contrastes ortonormales q=dQ conservan sus dos grados de libertad: d=m1+qQᵀ. No se estandariza, ajusta modelo, añade edad media ni divide por amplitud individual. Una media de diferencias no es participación municipal agregada. La forma requiere todas las tasas definidas; la elegibilidad exige además soporte en cada banda. Los valores definidos de perfiles sin soporte se conservan con sus banderas, no se presentan como entrenamiento.\n')
        table(q,['election_year','continuous_profiles','continuous_complete_profiles','supported_continuous_profiles','continuous_municipalities','continuous_supported_LN','continuous_LN_pct'])
        table(dist,['election_year','SEXO','indicator','profiles','mean_pp','q1_pp','median_pp','q3_pp'])
        add('Distribuciones con igual peso por perfil municipio/sexo elegible; no ponderan personas. La brecha ajustada es (tasa_mujeres−referencia_mujeres)−(tasa_hombres−referencia_hombres) para la misma banda y elección. `S_available` exige soporte y tasa definida en ambos segmentos; el indicador publicable es NULL si falla. Las diferencias crudas permanecen separadas. La participación municipal general usa todas las categorías, y su diferencia ajustada del núcleo pondera referencias de edad/sexo por los denominadores locales.\n')
        add('## Contexto y territorio propio del año\n')
        table(section_table,['election_year','U','R','M'])
        table(q,['election_year','observed_distinct_sections','section_keys_in_multiple_municipalities','few_section_supported_segments','over_100_source_rows','over_100_LN'])
        add('U/R/M es composición de LN asociada a **secciones electorales**, no localidad ni residencia de personas. Secciones únicas anuales: entidad+sección; la consulta municipal añade municipio. Los inventarios y conteos por segmento se preservan. No se suman secciones de bandas o sexos para fabricar una unión: una sección puede aportar a varios. `distinct_sections` por ficha es NULL en todos los años porque los agregados comunes, incluido 2024, no conservan esa unión por candidato; sí se informa mínimo/mediana y frecuencia de segmentos con menos de cinco secciones. Filas fuente≥5 no equivale a cinco secciones distintas.\n')
        add('![Contexto electoral](../../data/processed/participamx_multiyear/charts/section_context_history.png)\n')
        add('Cada año dispone de sus municipios, entidades, conteos, etiquetas, calidad y perfiles presentes. No se unen municipios entre elecciones, no se publican transiciones y `municipal_history_enabled=false` permanece en índice, metadatos y comparación histórica. Para un mapa harán falta cartografía/catálogos apropiados y correspondencias verificadas; las claves del INE no se convierten implícitamente a otro catálogo.\n')
        add('## Regresión de 2024 y procedencia\n')
        table(regression,['check','rows','fields','max_absolute_difference','status'])
        add(f'La regresión se ejecutó **antes de los otros años**, con igualdad de claves/flags y tolerancia absoluta {CONFIG["regression_atol"]:g}, rtol=0 y NULL en la misma posición. Segmentos, referencias, seis perfiles e indicadores de forma reprodujeron exactamente los valores comparados; el ajuste municipal difiere como máximo {regression.max_absolute_difference.max():.3g} por orden de operaciones flotantes. Se excluye intencionalmente sólo `r2_missing_segments` del resumen antiguo: depende de un modelo de 2024 y no pertenece a la metodología común sin entrenamiento. Los indicadores crudos y de soporte coinciden con las fuentes validadas.\n')
        add('**Incidencia heredada de trazabilidad:** el manifiesto descriptivo conserva una huella antigua de `build_descriptive.py`; el archivo actual ya tenía otra huella antes de esta entrega. Cuatro manifiestos posteriores corroboran la huella actual y los Parquet reutilizados concilian sus propias huellas. Se admite únicamente esa discrepancia de código identificada, registrada en `metadata/input_incidents.json`; no se editó el script ni el manifiesto antiguos. No se presenta la cadena histórica como libre de incidencias.\n')
        add(f'Se concilian {len(self.years)*32} combinaciones elección–entidad contra los conteos de limpieza, y siete métricas aditivas por municipio en cada vista. Se conservan **{source_rows:,} filas fuente representadas**, sin interpretarlas como personas únicas; cada elección satisface LN=SV+NV+NS. U/R/M concilia con los segmentos, y el detalle exacto con los totales anuales. Claves y uniones tienen cardinalidad declarada; los Parquet se releen y comparan. Se verifican por hash {protected:,} archivos previos al cerrar; los checkpoints contienen huellas y permiten reanudar sin repetir etapas válidas.\n')
        add('## Recursos JSON e integración futura\n')
        add('Destino: `data/processed/participamx_multiyear/`. `elections_index.json` enumera elecciones, tipo, rutas, cobertura y marco distrital. Cada `elections/YEAR/` conserva `profiles.json`, `municipalities.json`, `states.json`, `national_references.json`, `national_statistics.json`, `age_statistics.json`, `sex_statistics.json`, `section_statistics.json`, `continuous_indicators.json`, `sex_gaps.json`, `quality_summary.json`, `assignment_status.json` y `metadata.json`. Los directorios `municipality_segments/`, `municipality_profiles/` y `exact_age_segments/` se dividen por entidad para cargar sólo el territorio solicitado. `tables/` conserva los Parquet analíticos, pendientes y referencias.\n')
        add(f'Los JSON anuales ocupan aproximadamente **{json_size:,.1f} MiB** sin compresión. No se propone descargarlos todos al iniciar: el índice es ligero y el detalle exacto se solicita por entidad/año. `historical_comparison.json` contiene cortes transversales nacionales/estatales y distribuciones, sin filas municipales longitudinales. `historical/availability.json` habilita/explica funcionalidades por año. `integration/README.md` documenta selector, rutas, unidades y tratamiento de NULL.\n')
        add('Contrato v2 con año obligatorio, claves de código textuales y mismas columnas por recurso en los seis años. Identificadores/campos en inglés, mensajes y advertencias en español, tasas en [0,1] y diferencias en proporciones; multiplicar por 100 para porcentaje/pp. NULL explícito no se convierte en cero. Los ceros U/R/M sólo corresponden a subconjuntos vacíos conocidos de categorías exhaustivas. JSON no admite NaN/Infinity. Los esquemas estándar JSON Schema 2020-12 están en `schemas/`; el validador local cubre estrictamente el subconjunto usado, no todo el estándar. Una integración puede validar además con un motor estándar; no requiere instalar dependencias nuevas para producir esta entrega.\n')
        add('El contrato no es un reemplazo directo del antiguo payload v1 fijado a 2024: conserva conceptos e IDs, añade dimensión temporal y separa recursos por unidad. Los componentes actuales no tienen un cargador multianual conectado; este trabajo deja datos y guía concretos para implementarlo. No se cambió frontend ni `public/data`.\n')
        add('## Respuestas para la decisión y límites\n')
        add('1. **Mismo análisis:** sí, seis ejecuciones independientes de estadísticas, reglas, contexto e indicadores continuos, sin repetir algoritmos.\n2. **Funciones:** todas las anteriores en los seis años con soporte por registro; SEXO=2 sólo está registrado en 2024.\n3. **Diferencias:** cobertura municipal/nominal, NS, distribución etaria, tipos de elección, máximos de edad, categorías de sexo y marcos distritales; no son bases individuales idénticas.\n4. **Cobertura:** las tablas anuales separan LN, unión municipal y perfiles de forma; una cobertura nominal alta no elimina huecos territoriales.\n5. **Seis perfiles:** sí, todos tienen soporte en cada elección; son seis reglas explícitas, no seis clases naturales demostradas.\n6. **Distribución:** las cuotas y contrastes anteriores cuantifican el cambio con referencia propia; no se interpretan como migración entre perfiles.\n7. **No disponibles:** categoría no binaria histórica, unión única de secciones por candidato, equivalencias municipales/cartografía y etiquetas aprendidas históricas. Los huecos de tasa/soporte/distrito permanecen explícitos.\n8. **2024:** los seis controles de regresión pasan antes de generalizar; no se sobrescribe el análisis original.\n9. **React:** índice y recursos permiten seleccionar año y consultar estadísticas, perfiles, territorio, edad/sexo y calidad propios; conexión/publicación pendientes.\n10. **Jurado:** agregación ecológica, reglas y frontera convencionales, NS/captura, cuadernillos incompletos respecto del universo electoral, soporte desigual, territorios sin correspondencia, comparación presidencial/intermedia y límites de procedencia. No se infieren motivaciones, eficacia de intervenciones o conducta individual.\n')
        add('## Reproducción y comprobaciones\n')
        add('```powershell\n.venv_archetypal_patterns/Scripts/python.exe analysis/scripts/build_multiyear_profiles.py\n.venv_archetypal_patterns/Scripts/python.exe -m unittest discover -s analysis/scripts -p test_build_multiyear_profiles.py\n```\n')
        add('`--year` acepta una elección y puede repetirse; cada ejecución recalcula únicamente sus referencias propias y conserva el control obligatorio de 2024 antes de generalizar. Para un subconjunto o parámetros distintos se deben elegir nuevos `--output` y `--report`. Con las mismas entradas/rutas se verifican y reutilizan checkpoints; `_SUCCESS` aparece sólo tras pruebas, lectura de artefactos e integridad final. `--stop-after-regression`, `--prepare-context` y `--prepare-years` permiten completar etapas sin repetir las anteriores. Los tests cubren signos exactos, ausencia frente a cero, referencias previas a soporte, unidades, coherencia/duplicación, esquemas, cobertura, regresión y casos sintéticos de huecos.\n')
        add('No se modificaron experimentos anteriores, fuentes, frontend ni `public/data`; no se imputaron tasas ni entrenaron modelos, y no se crearon commits. La integración visual y cualquier validación territorial longitudinal quedan como trabajo posterior explícito.\n')
        atomic_bytes(self.report,('\n'.join(parts)).encode('utf8'))

    def presentation(self):
        started=time.monotonic();paths=[]
        national=pd.read_parquet(self.output/'historical/year.parquet');profiles=pd.read_parquet(self.output/'historical/profiles.parquet')
        quality=pd.read_parquet(self.output/'historical/quality_summary.parquet');reference=pd.read_parquet(self.output/'historical/national_references.parquet')
        def figure(name,fig):
            fig.tight_layout();p=self.charts/name;save_figure(fig,p);paths.append(p)
        fig,axes=plt.subplots(1,2,figsize=(12,4))
        colors=['#5461a7' if y in [2012,2018,2024] else '#bc6d57' for y in national.election_year]
        axes[0].bar(national.election_year.astype(str),national.participation_observed*100,color=colors)
        axes[0].set(xlabel='Elección',ylabel='Participación observada (%)',title='ΣSV / Σ(SV+NV) · población reportada')
        axes[1].bar(national.election_year.astype(str),national.unspecified_rate*100,color=colors)
        axes[1].set(xlabel='Elección',ylabel='NS / LN (%)',title='No especificación, distinta de abstención')
        fig.suptitle('Presidenciales en azul e intermedias en naranja; cortes transversales independientes')
        figure('national_participation_and_ns.png',fig)
        fig,axes=plt.subplots(1,2,figsize=(12,4))
        for sex,ax in zip(['0','1'],axes):
            for band in BANDS:
                g=reference[(reference.SEXO==sex)&(reference.age_band==band)].sort_values('election_year')
                ax.plot(g.election_year,g.national_rate*100,'o-',label=band)
            ax.set(xlabel='Elección',ylabel='Referencia propia de participación (%)',title=SEX_LABELS[sex]);ax.legend()
        fig.suptitle('Referencias nacionales por intervalo y sexo; todos los conteos antes de soporte')
        figure('age_sex_references.png',fig)
        fig,ax=plt.subplots(figsize=(11,5));bottom=np.zeros(len(self.years));palette=plt.get_cmap('tab10').colors
        for j,candidate in enumerate(IDS):
            g=profiles[profiles.candidate_id==candidate].set_index('election_year').loc[self.years]
            ax.bar([str(y) for y in self.years],g.nominal_coverage*100,bottom=bottom,color=palette[j],label=candidate);bottom+=g.nominal_coverage.to_numpy()*100
        ax.bar([str(y) for y in self.years],100-bottom,bottom=bottom,color='#dddddd',label='Fuera de fichas con soporte')
        ax.set(xlabel='Elección',ylabel='Fracción del LN anual (%)',title='Seis perfiles por reglas: distribución propia de cada elección');ax.legend(fontsize=7,bbox_to_anchor=(1.02,1),loc='upper left')
        figure('profile_nominal_distribution.png',fig)
        fig,axes=plt.subplots(1,2,figsize=(12,4));pos=np.arange(len(self.years));q=quality.set_index('election_year').loc[self.years]
        axes[0].bar(pos-.18,q.supported_nominal_fraction*100,width=.36,label='LN anual')
        axes[0].bar(pos+.18,q.supported_municipality_fraction*100,width=.36,label='Municipios observados')
        axes[0].set(title='Cobertura de segmentos clasificados',ylabel='Cobertura (%)');axes[0].legend()
        axes[1].bar(pos,q.continuous_nominal_fraction*100,color=palette[2]);axes[1].set(title='LN cubierto por perfiles de forma con soporte',ylabel='Fracción LN anual (%)')
        for ax in axes:ax.set_xticks(pos,[str(y) for y in self.years]);ax.set_xlabel('Elección')
        figure('coverage_by_election.png',fig)
        section=pd.read_parquet(self.output/'historical/section_statistics.parquet');fig,ax=plt.subplots(figsize=(10,4));bottom=np.zeros(len(self.years))
        for kind,label,color in [('U','Urbana',palette[0]),('R','Rural',palette[2]),('M','Mixta',palette[1])]:
            counts=section[section.TIPOSEC.eq(kind)].set_index('election_year').LN.reindex(self.years)
            total=national.set_index('election_year').LN.reindex(self.years);values=(counts/total*100).to_numpy()
            ax.bar([str(y) for y in self.years],values,bottom=bottom,label=label,color=color);bottom+=values
        ax.set(xlabel='Elección',ylabel='Proporción del LN reportado (%)',title='Contexto de secciones electorales; no clasificación individual de residencia');ax.legend()
        figure('section_context_history.png',fig)
        self.write_report();paths.append(self.report)
        tests=subprocess.run([sys.executable,'-m','unittest','discover','-s','analysis/scripts','-p','test_build_multiyear_profiles.py'],cwd=self.root,
            env={**os.environ,'PARTICIPAMX_MULTIYEAR_OUTPUT':str(self.output)},capture_output=True,text=True,encoding='utf8')
        test_path=self.output/'metadata/automated_tests.json';write_json(test_path,dict(returncode=tests.returncode,stdout=tests.stdout,stderr=tests.stderr,time=utc()));paths.append(test_path)
        require(tests.returncode==0,'Fallaron pruebas: '+tests.stderr)
        self.checkpoint('final',paths,started,dict(charts=5,tests='passed',report=str(self.report)))

    def verify_success(self):
        mp=self.output/'metadata/run_manifest.json';marker=json.loads((self.output/'_SUCCESS').read_text())
        require(marker['manifest_sha256']==file_hash(mp),'Marcador final alterado.')
        manifest=json.loads(mp.read_text(encoding='utf8'))
        for relative,digest in manifest['artifact_hashes'].items():require(file_hash(self.root/relative)==digest,'Artefacto final alterado: '+relative)
        print('Paquete multianual íntegro; sin repetir cálculos.',flush=True)

    def finalize(self):
        self.verify_protected();self.state['status']='validated';self.state['finished']=utc();write_json(self.state_path,self.state)
        artifacts=[p for p in self.output.rglob('*') if p.is_file() and p.name not in ['run_manifest.json','state.json','_RUNNING.json','_SUCCESS']]
        artifacts += [self.report]+[self.root/'analysis/scripts'/name for name in OWN_FILES]
        mp=self.output/'metadata/run_manifest.json'
        write_json(mp,dict(status='validated',years=self.years,finished=utc(),config=CONFIG,protected_hashes=self.state['protected_hashes'],
            artifact_hashes={str(p.relative_to(self.root)):file_hash(p) for p in artifacts},
            regression_2024='passed',model_fits=0,original_csv_reads=0,json_bytes=sum(p.stat().st_size for p in (self.output/'elections').rglob('*.json')),
            input_incidents=json.loads((self.output/'metadata/input_incidents.json').read_text(encoding='utf8'))))
        write_json(self.output/'_SUCCESS',dict(manifest_sha256=file_hash(mp),finished=utc()))
        print('Paquete multianual validado: '+str(self.report),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'data/processed/participamx_multiyear')
    parser.add_argument('--report',type=Path,default=ROOT/'analysis/reports/multiyear_profile_review.md')
    parser.add_argument('--year',type=int,choices=YEARS,action='append')
    parser.add_argument('--stop-after-regression',action='store_true')
    parser.add_argument('--prepare-context',action='store_true')
    parser.add_argument('--prepare-years',action='store_true')
    args=parser.parse_args();run=None
    with experiment_lock(args.output):
        try:
            run=Pipeline(ROOT,args.output,args.report,args.year or YEARS)
            if not run.valid_stage('audit'):run.audit()
            if not run.valid_stage('regression_2024'):run.regression_2024()
            if args.prepare_context:
                for year in run.years:run.context(year)
            elif not args.stop_after_regression:run.run(prepare_only=args.prepare_years)
        except Exception as exc:
            if run is not None:
                run.state['status']='failed';run.state['errors'].append(dict(time=utc(),error=repr(exc),traceback=traceback.format_exc()));write_json(run.state_path,run.state)
            raise


if __name__=='__main__':main()
