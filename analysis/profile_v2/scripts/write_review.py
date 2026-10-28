"""Genera auditoría y recomendación desde los resultados experimentales verificados."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score
from threadpoolctl import threadpool_limits
from research_profiles import (ROOT, HOME, SPEC, CONFIGS, METRICS, BANDS, audit, diagnostics,
                               charts, digest, eligible, fit_parameters, table, transform, save_frame, write_json, require)


def finalize(output):
    require(not (output/'run.lock').exists(),'Hay un proceso de modelos activo')
    manifest=json.loads((output/'metadata/run_manifest.json').read_text(encoding='utf-8'))
    require(manifest['status'] in ['models_validated_report_pending','validated'],'Estado del experimento no válido')
    (output/'_SUCCESS').unlink(missing_ok=True)
    # El informe puede regenerar sólo sus diagnósticos; nunca ajusta modelos.
    full=audit(output)
    train=full[full.is_eligible].reset_index(drop=True)
    metrics=pd.read_csv(output/'diagnostics/model_metrics.csv')
    numerical_checks=[]
    labels={}
    for index,row in metrics.iterrows():
        config_id=row['config'];k=int(row.k);seed=int(row.seed)
        path=output/'models'/f'main_{config_id}_k{k}_seed{seed}.npz'
        meta=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        require(digest(path)==meta['artifact_hash'],'Modelo alterado')
        params=fit_parameters(train,CONFIGS[config_id])
        values=transform(train,params)
        with np.load(path,allow_pickle=False) as stored:
            assigned=stored['labels'];centers=stored['centers']
        require(len(assigned)==len(train),'Longitud de etiquetas incorrecta')
        require(len(np.unique(assigned))==k,'No hay K grupos')
        sums=0.0;center_residue=0.0
        for cluster in range(k):
            part=values[assigned==cluster]
            # Con parada por tol, sklearn reasigna etiquetas y puede conservar
            # centros ligeramente distintos de la media final: se cuantifica.
            center_residue=max(center_residue,float(np.max(np.abs(part.mean(axis=0)-centers[cluster]))))
            sums+=float(np.sum((part-centers[cluster])**2))
        np.testing.assert_allclose(sums,meta['inertia'],rtol=1e-12,atol=1e-8)
        distances=np.sum((values[:,None,:]-centers[None,:,:])**2,axis=2)
        excess=float(np.max(distances[np.arange(len(values)),assigned]-distances.min(axis=1)))
        require(excess<1e-10,'Etiqueta no asignada a un centro mínimo')
        numerical_checks.append(dict(config=config_id,k=k,seed=seed,center_mean_residual=center_residue,SSE_residual=abs(sums-meta['inertia']),nearest_center_excess=excess))
        for name,value in diagnostics(train,values,assigned).items():
            if name=='cluster_sizes':continue
            metrics.loc[index,name]=value
        if row.get('representative') is True or str(row.get('representative')).lower()=='true':labels[config_id,k]=assigned
    save_frame(output,'diagnostics/model_metrics.csv',metrics)
    save_frame(output,'diagnostics/numerical_checks.csv',pd.DataFrame(numerical_checks))
    representative=metrics[metrics.representative.fillna(False)].copy()
    require(len(representative)==15,'Faltan representantes')
    seed=pd.read_csv(output/'diagnostics/seed_stability.csv')
    municipal=pd.read_csv(output/'diagnostics/municipal_stability.csv')
    sensitivity=pd.read_csv(output/'diagnostics/sensitivity_metrics.csv')
    comparisons=pd.read_csv(output/'comparisons/representations.csv')
    comparisons=pd.concat([comparisons[~comparisons.left.eq('age_sex_75')],pd.DataFrame([dict(k=k,left='age_sex_75',right='relative_only',ARI=adjusted_rand_score(labels['age_sex_75',k],labels['relative_only',k])) for k in SPEC['k']])],ignore_index=True)
    save_frame(output,'comparisons/representations.csv',comparisons)
    summary=[]
    strengths=dict(absolute_50='Niveles absolutos y composición demográfica explícita',age_sex_50='Diferencias frente a pares de banda/sexo; comparable con V1',age_sex_section_50='Pares de banda/sexo/tipo; controla la referencia contextual',age_sex_75='Comprueba dependencia del peso de categorías',relative_only='Control simple de intensidad relativa')
    limits=dict(absolute_50='Separación fuerte por sexo/edad utilizados en la distancia',age_sex_50='Sexo domina parte de la partición; U/R/M poco separador',age_sex_section_50='Descuenta diferencias promedio U/R/M que también podrían interesar',age_sex_75='Puede aproximarse a un control unidimensional',relative_only='No es un perfil multivariable ni prueba clases naturales')
    for _,row in representative.iterrows():
        config_id=row['config'];k=int(row.k)
        seeds=seed[(seed['config']==config_id)&seed.k.eq(k)]
        samples=municipal[(municipal['config']==config_id)&municipal.k.eq(k)]
        summary.append(dict(config=config_id,K=k,method='K-Means con bloques' if config_id!='relative_only' else 'K-Means 1D (control)',segments=len(train),municipalities=train.municipal_id.nunique(),nominal_fraction=train.LN.sum()/full.LN.sum(),sizes=row.cluster_sizes,silhouette=row.silhouette,DB=row.db,seed_ARI_min=seeds.ARI.min(),OOB_median=samples.ARI_oob.median() if len(samples) else None,OOB_min=samples.ARI_oob.min() if len(samples) else None,conditional_joint_R2=row.conditional_joint_r2,participation_separation_share=row.participation_separation_share,age_share=row.age_separation_share,sex_share=row.sex_separation_share,section_share=row.section_separation_share,age_purity=row.age_band_purity,sex_purity=row.SEXO_purity,section_purity=row.TIPOSEC_purity,advantage=strengths[config_id],limitation=limits[config_id],interpretability='Descripción condicional de celdas; revisar las fichas, sin etiqueta individual'))
    summary=pd.DataFrame(summary)
    save_frame(output,'comparisons/candidate_summary.csv',summary)
    quality=[]
    for name in ['low_LN','low_specified','few_source_rows','high_ns','few_sections','split_sign_opposes_parent']:
        mask=full[name]
        quality.append(dict(flag=name,segments=int(mask.sum()),LN=int(full.loc[mask,'LN'].sum()),eligible_segments=int((mask&full.is_eligible).sum()),eligible_LN=int(full.loc[mask&full.is_eligible,'LN'].sum())))
    save_frame(output,'diagnostics/quality_flags.csv',pd.DataFrame(quality))
    eligible_universe=set(train.municipal_id)
    original_universe=set(full.municipal_id)
    supported_parents=set(full.loc[full.v1_parent_profile.notna(),'municipal_id'])
    lost=full[full.municipal_id.isin(original_universe-eligible_universe)].groupby(['municipal_id','EDOCVE','MPIOCVE','state_name_label','municipality_name_label']).agg(LN=('LN','sum'),cells=('row_id','size')).reset_index()
    lost['had_v1_profile']=lost.municipal_id.isin(supported_parents)
    save_frame(output,'diagnostics/municipalities_without_eligible_cells.csv',lost)
    weights=[]
    for name,weight in [('equal_segment',np.ones(len(train))),('equal_municipality',(1/train.groupby('municipal_id').row_id.transform('size')).to_numpy()),('LN_descriptive_only',train.LN.to_numpy(float))]:
        w=pd.Series(weight).groupby(train.municipal_id).sum().sort_values(ascending=False)
        weights.append(dict(weighting=name,used_in_models=name!='LN_descriptive_only',top10_municipal_share=w.head(10).sum()/w.sum(),equivalent_municipal_concentration=w.sum()**2/np.sum(w**2),mean_turnout=np.average(train.participation_observed,weights=weight),mean_relative_pp=100*np.average(train.delta_age_sex,weights=weight)))
    save_frame(output,'diagnostics/weight_concentration.csv',pd.DataFrame(weights))
    # Los pendientes se conservan; se valida nuevamente cada columna de asignación.
    for path in (output/'assignments').glob('*.parquet'):
        assigned=pd.read_parquet(path)
        require(assigned.row_id.equals(full.row_id),'Desalineación con referencia')
        require(assigned.loc[~full.is_eligible,'cluster'].isna().all(),'Pendientes etiquetados')
    candidates=json.loads((output/'candidates/experimental_profiles.json').read_text(encoding='utf-8'))
    require(len(candidates)==75,'Número de fichas incompleto')
    for config_id in CONFIGS:
        for k in SPEC['k']:
            group=[row for row in candidates if row['config']==config_id and row['k']==k]
            require(len(group)==k and sum(row['segments'] for row in group)==len(train),'Fichas no particionan el entrenamiento')
            for field in METRICS:require(sum(row['counts'][field] for row in group)==int(train[field].sum()),'Conteos de fichas no concilian')
    charts(output,metrics,candidates)
    membership=pd.read_parquet(output/'resampling/membership.parquet')
    require(len(membership)==2477*10,'Membresía de remuestras incompleta')
    require((membership.groupby('sample').is_sampled.sum()==1981).all(),'Sorteo municipal incorrecto')
    for path in (output/'resampling').glob('resample_*.parquet'):
        assigned=pd.read_parquet(path)
        require(assigned.row_id.equals(train.row_id),'Etiquetas OOB desalineadas')
        require((assigned.is_training==~assigned.is_oob).all(),'Roles de remuestra incorrectos')
        require(pd.DataFrame(dict(municipal_id=train.municipal_id,is_training=assigned.is_training)).groupby('municipal_id').is_training.nunique().max()==1,'Se separaron segmentos del municipio')
    reports=output/'reports';reports.mkdir(exist_ok=True)
    audit_info=json.loads((output/'metadata/audit.json').read_text(encoding='utf-8'))
    historical=pd.read_csv(output/'diagnostics/historical_coverage.csv')
    status=pd.read_csv(output/'diagnostics/coverage_status.csv')
    support=pd.read_csv(output/'diagnostics/support_sensitivity.csv')
    reference=pd.read_csv(output/'comparisons/reference_effect.csv',dtype={'SEXO':str})
    reference=reference[reference.age_band.isin(BANDS)&reference.SEXO.isin(['0','1'])]
    state=pd.read_csv(output/'diagnostics/coverage_state.csv')
    nonbinary=full[full.SEXO.eq('2')]
    original=pd.read_csv(output/'comparisons/v1_six_profiles.csv')
    audit_text=f'''# Auditoría de variables y cruce multivariable · V2 experimental

Se recuperó el cruce real, no se reconstruyó desde marginales. Se reutilizaron Parquet validados, sus manifiestos y referencias. No se leyeron CSV originales ni registros limpios individuales. Las fuentes y comprobaciones completas están en metadata/audit.json.

{table(historical)}

Las mismas 32 entidades están presentes cada año; municipios y categorías se interpretan dentro de cada elección. Las {audit_info['additive_checks']:,} comprobaciones de siete conteos aditivos concilian el cruce con padres, municipios y tipos nacionales; también se contrasta la tasa nacional de banda/sexo publicada.

En 2024 hay {len(full):,} celdas observadas y {audit_info['unobserved_core_combinations']:,} combinaciones H/M de tres bandas y tres tipos no observadas frente al universo municipal de 18 posibilidades. Las ausencias no se completan con ceros. Los conteos y claves de origen no tienen nulos. Hay {audit_info['missing_values']['participation_observed']} tasas no definidas en la referencia completa, sin imputación.

{table(status)}

La población común elegible es {len(train):,} celdas, {train.municipal_id.nunique():,} municipios y LN={int(train.LN.sum()):,} ({train.LN.sum()/full.LN.sum():.4%} del reportado). Se conservan {len(full)-len(train):,} pendientes con sus motivos disjuntos y banderas superpuestas.

## Comparación de soporte y alternativas etarias

{table(support)}

Las cinco bandas aumentan la fragmentación: no se entrenan en esta comparación ni se calcula ARI entre unidades distintas. Los umbrales exploratorios no equivalen a precisión o independencia estadística.

V1 conserva 14,190 segmentos, 2,402 municipios y LN=98,203,780. V2 pierde {2402-train.municipal_id.nunique()} municipios adicionales y LN={98203780-int(train.LN.sum()):,} respecto a V1; no se confunde aumento de filas con aumento de cobertura. Los {len(lost)} municipios sin celdas elegibles están enumerados, incluyendo cuáles aportaban una ficha V1.

## Sexo no binario, edades extremas y sección

SEXO=2 conserva {len(nonbinary)} celdas, LN={int(nonbinary.LN.sum())}, SV={int(nonbinary.SV.sum())}, NV={int(nonbinary.NV.sum())}, NS={int(nonbinary.NS.sum())}; el mayor denominador es {int((nonbinary.SV+nonbinary.NV).max())}. Ninguna entra al experimento H/M ni se le inventa etiqueta. Antes de 2024 la categoría no está registrada: no se declara cero población. 101+ conserva LN={audit_info['over_100_counts']['LN']:,} y {audit_info['over_100_counts']['source_row_count']:,} filas fuente, fuera del núcleo pero dentro de la contabilidad.

U/R/M clasifica tipo de sección electoral, no localidad, residencia efectiva o nivel socioeconómico. Se dispone del número distinto de secciones por celda, no de la unión de claves por cluster. La suma de section_count entre celdas duplicaría secciones.

## Referencias de 2024: qué se conserva y qué se descuenta

{table(reference[['age_band','SEXO','TIPOSEC','reference_age_sex','reference_age_sex_section','reference_shift_pp']])}

La referencia conjunta cambia hasta {reference.reference_shift_pp.abs().max():.3f} pp la referencia por edad/sexo. Descuenta diferencias promedio entre tipos, pero no elimina asociaciones locales ni corrige captura. No se usa una tasa nacional incondicional ni una media de tasas municipales.

## Cobertura estatal y flags de calidad

{table(state)}

{table(pd.DataFrame(quality))}

Las banderas se superponen, no son exclusiones aditivas. NS≥10 % no excluye del principal. Filas fuente≥5 no exige cinco secciones; {int(train.few_sections.sum()):,} celdas elegibles ({train.few_sections.mean():.2%}) proceden de menos de cinco secciones. La pérdida bajo ese requisito se estudia como sensibilidad, no como corrección automática.
'''
    (reports/'variable_audit.md').write_text(audit_text,encoding='utf-8')
    stability=municipal.groupby(['config','k']).ARI_oob.agg(OOB_median='median',OOB_min='min',OOB_max='max').reset_index()
    stability['below_090']=[int(((municipal['config']==row['config'])&municipal.k.eq(row.k)&municipal.ARI_oob.lt(.9)).sum()) for _,row in stability.iterrows()]
    resampling=pd.read_csv(output/'resampling/coverage.csv')
    seed_summary=seed.groupby(['config','k']).ARI.min().reset_index(name='ARI_min')
    before_after=pd.read_csv(output/'comparisons/v1_common_children.csv')
    simplified=summary[['config','K','sizes','silhouette','DB','seed_ARI_min','OOB_median','OOB_min','conditional_joint_R2','sex_purity','section_purity']]
    contributions=summary[['config','K','participation_separation_share','age_share','sex_share','section_share']]
    sensitivity_table=sensitivity[['config','scope','k','n','municipalities','nominal_fraction','ARI_common','ARI_all_main']]
    features=CONFIGS
    # Hechos contrastables para la recomendación; no se elige K por un máximo de índice.
    same=summary[summary['config'].isin(['age_sex_50','age_sex_section_50'])]
    weight_sensitivity=sensitivity[sensitivity.scope.eq('equal_municipality')&sensitivity.k.eq(5)].ARI_all_main
    fraction_source=f'{int(train.LN.sum()):,} / {int(full.LN.sum()):,}'
    context_table=pd.read_csv(output/'historical/national_joint_references.csv',dtype={'SEXO':str})
    piv=context_table.pivot(index=['election_year','election_type','age_band','SEXO'],columns='TIPOSEC',values='reference').reset_index()
    piv['R_minus_U_pp']=100*(piv.R-piv.U);piv['M_minus_U_pp']=100*(piv.M-piv.U)
    save_frame(output,'historical/section_contrasts.csv',piv)
    historical_sign=piv.groupby(['age_band','SEXO']).agg(elections=('election_year','size'),R_U_min_pp=('R_minus_U_pp','min'),R_U_max_pp=('R_minus_U_pp','max'),R_above_U_elections=('R_minus_U_pp',lambda x:int((x>0).sum()))).reset_index()
    report=f'''# Segmentación multivariable experimental de perfiles · 2024

**Los datos permiten construir particiones reproducibles de cuatro, cinco y seis grupos, pero esta prueba no respalda sustituir las seis fichas actuales por una tipología conjunta estable de edad, sexo y tipo de sección.** La principal ampliación verificable es observar tasas e intensidad dentro del cruce real, antes ocultas por la agregación. Las categorías añadidas cambian la distancia; no se convierten por ello en clases naturales o rasgos individuales.

**Recomendación:** conservar V1 como clasificación descriptiva comunicable y enriquecer su evidencia con el cruce U/R/M, denominadores y referencias alternativas. Si se continúa investigando una partición, mantener `age_sex_50`, K=4, como candidato parsimonioso de revisión y `age_sex_section_50`, K=4, como control contextual, **sin adoptarlos ni presentarlos como cuatro perfiles definitivos**. K=5/6 permanecen documentados: el número solicitado por el reto no determina la existencia de grupos naturales. La recomendación no selecciona un ganador por Silhouette.

En las tablas, tasas, coberturas, purezas y R² son proporciones en [0,1], salvo columnas explícitas en puntos porcentuales. Una proporción de 0.99 corresponde a 99 %, no 0.99 %. Los conteos de segmentos, municipios y LN son unidades distintas.

## Recuperación y comparación de las seis fichas actuales

Unidad V1: municipio × banda × sexo. Reglas: tres bandas H/M 18–100 × signo exacto frente a la referencia nacional propia de banda/sexo. Soporte LN≥100, SV+NV≥100 y filas fuente≥5; NS advierte y no se imputa. Son reglas transparentes con 14,190 segmentos, 2,402 municipios y LN=98,203,780. Edad/signo definen su diferenciación, con 13.20 % de segmentos a ≤2 pp de la referencia; ni esa frontera ni su nombre identifican motivación o seis clases naturales.

{table(original)}

Sus fortalezas son claridad, referencias verificables y cobertura. Sus límites son frontera convencional, bandas amplias, soporte territorial desigual y contexto no incorporado a la asignación. Los antecedentes multidimensionales y de arquetipos ya mostraban gradientes, dependencia de representación y colas de inestabilidad; este trabajo no los ignora ni reinterpreta como una validación previa de V2. La revisión de documentos fuente queda en metadata/source_review.json. No se modifican fichas, JSON publicados o estrategias.

## Disponibilidad y unidad V2

Se recuperó el cruce real de las seis elecciones desde Parquet validados. No se leyeron CSV originales ni se multiplicaron marginales del Atlas. V2 = municipio × banda × sexo × tipo de sección × elección; los 38,805 registros de 2024 representan 9,773,730 celdas fuente, no personas ni 38,805 secciones independientes.

{table(historical)}

Principal común: **{len(train):,} segmentos, {train.municipal_id.nunique():,}/2,477 municipios, LN={int(train.LN.sum()):,}, {train.LN.sum()/full.LN.sum():.4%} del anual** ({fraction_source}). Los {len(full)-len(train):,} pendientes siguen en referencia, con etiquetas NULL. La pérdida frente a V1 es 10 municipios y LN=204,103, pese al mayor número de filas. Hay soporte suficiente para un piloto acotado, no para afirmar cobertura territorial completa o fiabilidad universal. El [informe de auditoría](variable_audit.md) desglosa estados, denominadores, ausencias, umbrales, NS y no binarios.

{table(status)}

SEXO=2 conserva LN=105 y sus 105 filas fuente; su soporte no permite la comparación H/M de este experimento. 101+ permanece en los totales y complementos. No se imputa ni se transforma NS en NV. Las tres bandas actuales mantienen la comparación con V1; cinco bandas pierden más soporte ({int(support.loc[support.design.eq('life_stage_split'),'municipalities'].iloc[0]):,} municipios y {support.loc[support.design.eq('life_stage_split'),'nominal_fraction'].iloc[0]:.4%} LN), por lo que no se amplía la búsqueda de modelos a ese escenario. No se fijan bandas definitivas.

## Método, normalización y controles

Se utiliza K-Means de scikit-learn con representación de datos mixtos documentada: una coordenada electoral estandarizada más one-hot simétricos de banda, sexo y tipo. En el principal, 50 % de la varianza de entrada corresponde a participación y 50 % al conjunto de categorías; cada categoría aporta un tercio de ese segundo bloque. Las escalas se ajustan sólo a los elegibles. No se usan edad media, códigos ordinales, municipio/distancia geográfica, conteos absolutos o NS como coordenadas. La normalización por bloque impide que el simple número de dummies imponga su peso; **no elimina la dependencia respecto del peso elegido**.

Las cinco configuraciones son absoluta; diferencia frente a banda/sexo; diferencia frente a banda/sexo/tipo; esa diferencia con 75 % electoral; y un control relativo de una dimensión. No se introducen tasa y diferencia simultáneamente. El referente nacional se calcula con todos los conteos antes de soporte. Incorporar tipo a la referencia cambia los umbrales hasta {reference.reference_shift_pp.abs().max():.2f} pp en el núcleo; puede retirar precisamente parte de las diferencias contextuales que se quieren describir.

Se completaron **123 ajustes**: 45 principales (5 configuraciones × 3 K × 3 semillas), 18 sensibilidades y 60 de remuestreo. Tres semillas 17/42/2024, 20 inicios principales, Lloyd, tol=10⁻⁶, máximo 1,000 iteraciones, un hilo; todos se detuvieron antes del límite. Las 15 soluciones representativas son las de menor SSE dentro de cada configuración/K, no un K ganador. K-prototypes no está disponible (`kmodes` no instalado); no se instala ni inventa un optimizador mixto propio. La [metodología completa](../../reports/methodology.md) detalla geometría, presupuestos y límites. [KMeans, documentación primaria](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html).

## Comparación de cuatro, cinco y seis grupos

Silhouette: 384 anclas uniformes compartidas contra todos los segmentos, por bloques; no matriz N×N. DB usa la población completa. Se guardan SSE, tamaños y métricas de todas las semillas. El R² condicional compara varianza de tasas dentro de edad/sexo/tipo antes/después de añadir etiquetas; mide separación descriptiva, no exactitud o información externa. Las métricas internas pertenecen a sus propias geometrías y no prueban superioridad universal. [Silhouette, referencia primaria](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html).

{table(simplified)}

La tabla estructurada `comparisons/candidate_summary.csv` añade cobertura, método, ventajas, límites e interpretabilidad de cada una de las 15 alternativas. No se comparan municipios como observaciones disjuntas entre clusters: un mismo municipio aporta varias celdas y puede aparecer en varios grupos. Las fichas completas están en [candidates](candidates/), con 75 caracterizaciones (incluidos controles), conteos, distribuciones por filas/LN, tasas, referencias mezcladas, heterogeneidad, NS, soporte y entidades.

![Comparación de candidatos](../charts/candidate_comparison.png)

## Qué aporta realmente cada dimensión

En las dos representaciones relativas de 50 %, la pureza por sexo va de {same.sex_purity.min():.2%} a {same.sex_purity.max():.2%}. La pureza U/R/M permanece cerca de su distribución global por segmentos: el contexto no genera aquí una separación fuerte entre tipos. Que las categorías estén en la matriz no demuestra que cuatro a seis perfiles combinen de manera sustantiva todas ellas. La representación absoluta alcanza purezas por sexo cercanas al 98 %; eso responde también al diseño de la distancia y a las tasas absolutas diferentes.

{table(contributions)}

Estas proporciones corresponden a suma de cuadrados entre centroides en cada bloque; no son importancia causal ni variables independientes. Al subir a 75 % la participación, K4 se aproxima al control relativo puro: la separación de categorías puede casi desaparecer. La sensibilidad muestra que un reparto matemático explícito sigue siendo una decisión sustantiva. No se recomienda subir el peso de U/R/M sólo para obtener nombres más diversos.

{table(comparisons)}

La referencia conjunta cambia asignaciones (ARI entre las dos representaciones relativas en torno a 0.78–0.81), sin convertir U/R/M en una nueva tipología claramente separada. La decisión de descontar tipo debe responder a la pregunta de comparación; no se elige la referencia por el mejor índice interno.

Un aporte verificable del cruce, independiente de elegir K, es que **{int(train.split_sign_opposes_parent.sum()):,} hijos elegibles ({train.split_sign_opposes_parent.mean():.2%} de segmentos, {train.loc[train.split_sign_opposes_parent,'LN'].sum()/train.LN.sum():.2%} del LN entrenado)** cambian de signo frente a la referencia edad/sexo respecto al agregado V1 de su mismo municipio/banda/sexo. Esto identifica heterogeneidad oculta por agregar tipos; no prueba que los clusters la describan mejor ni convierte esos hijos en personas distintas.

En el candidato `age_sex_50`, K4, las etiquetas locales C1 y C3 son íntegramente Hombres y Mujeres, respectivamente, con diferencias agregadas de aproximadamente +1.81 y +1.29 pp frente a sus pares. C0 y C2 describen contrastes relativos más amplios (+17.66 y −12.80 pp). No son cuatro combinaciones equilibradas de edad/sexo/U/R/M: dos etiquetas centrales se distinguen principalmente por una categoría ya introducida en la distancia. Es un motivo concreto para mantenerlo como diagnóstico y no promoverlo a perfiles definitivos.

## Estabilidad, cobertura y sensibilidad de calidad

{table(stability)}

Diez submuestras sin reemplazo de 1,981/2,477 municipios mantienen juntos todos sus segmentos. Se recalibran escalas sólo in-bag y se evalúa ARI sobre municipios OOB frente al ajuste principal de la misma configuración/K. Las referencias nacionales siguen fijas e incluyen OOB: **estabilidad condicional, no predicción independiente del proceso nacional**. ARI no requiere alinear números de etiquetas. [Definición primaria de ARI](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.adjusted_rand_score.html).

{table(resampling)}

Las medianas y mínimos OOB son altos dentro de una geometría fija, pero no solucionan su dependencia de pesos ni demuestran clases naturales. Diez muestras son exploratorias; no son intervalos de confianza ni incertidumbre de personas.

{table(sensitivity_table)}

**K5 es especialmente sensible al peso municipal:** ARI={weight_sensitivity.min():.3f}–{weight_sensitivity.max():.3f} al cambiar el objetivo de peso segmento a peso total municipal uno. No se deduce ese resultado de las semillas estables: son perturbaciones distintas. Exigir cinco secciones por celda deja 13,572 segmentos y 89.83 % del LN anual; sus cambios de asignación son importantes, aunque mezclan selección territorial, distribución y optimización. NS bajo deja 25,254 segmentos y 82.48 % del LN anual, con concordancia mucho mayor. Esto no demuestra ausencia de sesgo de NS ni el comportamiento que tendrían los registros no especificados.

{table(pd.DataFrame(weights))}

La ponderación LN se documenta sin ajustar modelos con ella. La concentración equivalente describe reparto municipal de masa; no es tamaño muestral efectivo ni número de personas. Los criterios de soporte no garantizan independencia: {train.few_sections.mean():.2%} de los segmentos elegibles procede de menos de cinco secciones distintas.

![Estabilidad municipal](../charts/municipal_stability.png)

## Caracterización y comparación honesta con V1

Cada ficha candidata tiene ID experimental, año, unidad y método, dos párrafos descriptivos, composición por edad/sexo/tipo tanto por filas como por LN, registros SV/NV/NS, referencias mezcladas por D, diferencia, dispersión, bases mínimas/medianas, municipios, entidades y concentración. Los nombres provisionales identifican combinaciones modales del ajuste; **no diagnostican personalidad, preferencias, necesidad de atención o eficacia de estrategias**. Las variables usadas para construir la partición no se presentan como validación externa de sus diferencias.

V1 y V2 tienen unidades distintas. Para el contraste numérico se hereda la etiqueta V1 del padre a cada hijo, sin expandir hijos ni tratarlos como perfiles V1 independientes. El R² y ARI siguientes se calculan sólo sobre las mismas celdas V2; no son un ARI directo entre las 14,190 filas previas y 31,470 actuales.

{table(before_after)}

1. **Información adicional:** el cruce real permite localizar heterogeneidad entre tipos dentro de una misma banda/sexo/municipio, intensidad y cobertura antes ocultas. Los grupos aprendidos reexpresan esos conteos, no añaden información individual.
2. **Mejor caracterización:** diferencias de tasas y referencias contextuales, concentraciones y soporte pueden comunicarse explícitamente. No se verifica que cada cluster combine de manera robusta las cuatro dimensiones como rasgos propios.
3. **Pérdidas:** más celdas pequeñas, 10 municipios y 204,103 LN respecto a V1, menor transparencia de reglas y dependencia de escalas, pesos y centros. La falta de equivalencia de etiquetas impide llamar a una clase nueva la sucesora directa de una ficha anterior.
4. **Límites de ambos:** agregación ecológica, bandas amplias, cobertura de cuadernillos, NS y ausencia de variables externas. En V1 la frontera cero es convencional; en V2 también lo son geometría y K.
5. **Defensa metodológica:** V1 es más sencilla para una presentación explícita por reglas, con contexto U/R/M y magnitud visibles. V2 sirve como investigación contrastable, pero no elimina las decisiones convencionales ni valida cuatro a seis tipos naturales.
6. **Objetivo del reto:** cuatro a seis fichas útiles no requieren afirmar clases naturales. Con la evidencia actual, mantener las seis fichas transparentes enriquecidas resulta más defendible que sustituirlas por clusters cuya pertenencia cambia con objetivos plausibles de peso/soporte. La conformidad formal con una rúbrica oficial no se certifica sin incorporarla como fuente primaria.

## Contexto histórico compatible

Se guardan las 108 referencias nacionales banda×H/M×tipo×elección. Las categorías y definiciones permiten describir cortes transversales; no justifican transferir etiquetas 2024. Tres presidenciales y tres intermedias poseen composición, cobertura y NS distintos.

{table(historical_sign)}

Los contrastes R−U cambian por sexo/banda y elección; las diferencias nacionales no sustentan un efecto uniforme del tipo de sección electoral. No se atribuyen cambios a las mismas personas ni a límites municipales constantes. El detalle `historical/section_contrasts.csv` permite revisar cada elección con su referencia propia.

![Contexto histórico conjunto](../charts/historical_joint_context.png)

## Recomendación y revisión pendiente

No promover ninguna solución como reemplazo definitivo. K4 relativo es un punto de revisión más parsimonioso y presenta buena concordancia municipal dentro del diseño fijo; no satisface por sí mismo el objetivo de perfiles propios de edad+sexo+U/R/M+participación. K5 cambia fuertemente con el objetivo municipal, y K6 no resuelve la falta de diferenciación contextual por el simple hecho de añadir etiquetas.

Antes de otro piloto: acordar si el objetivo es celdas demográficas o perfiles territoriales, revisar si se requiere un patrón de tasas por edad/sexo/tipo en vez de categorías como coordenadas, exigir auditoría de soporte antes de ese pivote, validar el papel de la referencia U/R/M, evaluar más remuestras/arranques si se retienen candidatos, y contrastar interpretaciones con evidencia electoral externa. Un algoritmo mixto adicional podría ser un contraste futuro, no una garantía de perfiles mejores. No cambiar pesos para forzar cuatro a seis narrativas.

Las estrategias institucionales actuales siguen independientes: no se asignan a los nuevos grupos. No se diseñan mensajes persuasivos ni campañas segmentadas. No se incorporan perfiles a React, Atlas, servicios publicados o fichas oficiales.

## Integridad y reproducción

Se utilizaron bibliotecas reales del entorno disponible; versiones exactas en metadata/environment.json. Pasan pruebas sintéticas de geometría, referencias, soporte, permutación de categorías, Silhouette frente a scikit-learn y R² condicional. Se verifican SSE y asignación al centro mínimo de los 45 ajustes principales; la parada por tolerancia nativa puede dejar centros ligeramente diferentes de las medias de etiquetas finales (residuo máximo {max(row['center_mean_residual'] for row in numerical_checks):.6g} en coordenadas transformadas). Se cuantifica en numerical_checks.csv sin modificar modelos ni afirmar mínimos globales exactos. Se verifican también partición de las 75 fichas, etiquetas NULL de pendientes, alineación de archivos, roles de remuestreo y 888,405 controles aditivos. El manifiesto final registra fuentes, parámetros, modelos y huellas de todos los artefactos. _SUCCESS se escribe sólo tras pruebas, informes e integridad final.

Desde la raíz: ejecutar los tres comandos del [README](../../README.md). El ajuste reutiliza checkpoints compatibles; el generador de informes no entrena. No se modificaron archivos previos, frontend, datos originales, perfiles publicados, documentos de estrategias o resultados anteriores. No se crearon commits, push, merges o PR. Los resultados son **experimentales y no definitivos**.
'''
    (reports/'final_recommendation.md').write_text(report,encoding='utf-8')
    read_paths=['docs/perfiles/interpretacion_2024.md','docs/perfiles/perfiles_2024.json','docs/perfiles/contexto_historico.md','docs/perfiles/propuestas_institucionales.md','docs/perfiles/resumen_estrategias_equipo.md','analysis/reports/profile_interpretation_2024.md','analysis/reports/profile_interpretation_review.md','analysis/reports/multiyear_profile_review.md','analysis/reports/multidimensional_profile_review.md','analysis/reports/contextual_feature_review.md','analysis/reports/contextual_clustering_pilot.md','analysis/scripts/build_profile_candidates.py','analysis/scripts/build_multiyear_profiles.py']
    write_json(output/'metadata/source_review.json',[dict(path=name,sha256=digest(ROOT/name),lines=len((ROOT/name).read_text(encoding='utf-8').splitlines()),role='Recuperación de reglas, denominadores, fuentes o límites; sin modificación') for name in read_paths])
    dependencies=dict(kmodes_available=importlib.util.find_spec('kmodes') is not None,clustering_library='scikit-learn',new_packages_installed=False)
    write_json(output/'metadata/dependency_validation.json',dependencies)
    versions=json.loads((output/'metadata/environment.json').read_text(encoding='utf-8'))
    write_json(output/'metadata/feature_contract.json',dict(experimental=True,unit='municipality_age_band_sex_section_type_2024',
        main_population='H/M, 18-100; LN>=100, SV+NV>=100, source_row_count>=5; referencias antes de soporte',
        excluded_from_distance=['EDOCVE','MPIOCVE','election_year','LN','SV','NV','NS','source_row_count','section_count'],
        columns=dict(x0='Coordenada electoral estandarizada y ponderada según configuración',x1='18-34 one-hot centrado/RMS',x2='35-59 one-hot centrado/RMS',x3='60-100 one-hot centrado/RMS',x4='Hombres one-hot centrado/RMS',x5='Mujeres one-hot centrado/RMS',x6='Urbana one-hot centrado/RMS',x7='Rural one-hot centrado/RMS',x8='Mixta one-hot centrado/RMS'),
        control='relative_only conserva únicamente x0; no es representación multivariable',
        scalers='metadata/block_parameters.json; entrenamiento principal sólo sobre elegibles; remuestras con parámetros in-bag propios en metadata de cada modelo',
        labels='assignments/: todas las celdas originales; cluster NULL para pendientes; claves sólo para alineación',
        redundancy='Las categorías de cada bloque suman uno antes de centrar; 9 columnas, rango máximo 6. No son nueve fuentes independientes.'))
    (output/'metadata/requirements.txt').write_text('\n'.join(f'{key}=={value}' for key,value in versions['packages'].items())+'\n',encoding='utf-8')
    test=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(HOME/'scripts'),'-p','test_research_profiles.py'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    write_json(output/'metadata/test_validation.json',dict(returncode=test.returncode,stdout=test.stdout,stderr=test.stderr))
    require(test.returncode==0,'Fallaron las pruebas sintéticas')
    protected=json.loads((output/'metadata/protected_hashes.json').read_text(encoding='utf-8'))
    for path,expected in protected.items():require(digest(ROOT/path)==expected,'Archivo previo modificado: '+path)
    require(len(list((output/'models').glob('*.npz')))==123,'Cantidad de modelos incorrecta')
    artifacts={path.relative_to(output).as_posix():digest(path) for path in output.rglob('*') if path.is_file() and path.name not in ['run_manifest.json','_SUCCESS','run.lock']}
    code={path.relative_to(HOME).as_posix():digest(path) for path in (HOME/'scripts').glob('*.py')}
    write_json(output/'metadata/run_manifest.json',dict(status='validated',experimental=True,model_fits=123,original_CSV_reads=0,protected_files=len(protected),source_hashes=audit_info['inputs'],artifacts=artifacts,code_hashes=code,tests_passed=True,report='reports/final_recommendation.md'))
    (output/'_SUCCESS').write_text('validated experimental research; not published\n',encoding='utf-8')
    print(summary[['config','K','silhouette','OOB_median','OOB_min','sex_share','section_share']].to_string(index=False))
    print(f'Validado: {output}',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HOME/'results')
    args=parser.parse_args()
    with threadpool_limits(limits=1):finalize(args.output)
