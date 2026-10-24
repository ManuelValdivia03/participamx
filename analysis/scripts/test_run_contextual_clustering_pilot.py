"""Pruebas numéricas del piloto por bloques, sin tocar datos electorales."""
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd

from clean_data import ValidationError
from clustering_core import kmeans, validation_metrics
from compare_demographic_features import lloyd, weighted_group_sse
from evaluate_exact_age_clustering import anchor_silhouettes, db_index
from run_contextual_clustering_pilot import (SHARE_COLUMNS, configurations, fit_blocks, transform_blocks,
    fit_model, weighted_lloyd_nd, predict_nd, numerical_check, margins, conditional_rate_r2,
    conditional_entropy_ratio, pattern_diagnostics, main_experiments, initialization_records, audit_outputs,
    sensitivity_experiments, municipal_resampling)


def example_frame(n=60):
    rng=np.random.default_rng(190)
    shares=rng.dirichlet([.6,.5,.4],n)
    shares[0]=[1,0,0];shares[1]=[0,1,0];shares[2]=[0,0,1]
    frame=pd.DataFrame(shares,columns=SHARE_COLUMNS)
    frame['participation_deviation_national']=rng.normal(0,.1,n)
    frame['participation_observed']=np.clip(.6+frame.participation_deviation_national,0,1)
    frame['mean_age_nominal']=np.tile([24,36,51,66,81],n//5+1)[:n]
    frame['age_band']=np.tile(['18-29','30-44','45-59','60-74','75-100'],n//5+1)[:n]
    frame['SEXO']=np.tile(['0','1'],n//2+1)[:n]
    frame['EDOCVE']='1';frame['MPIOCVE']=[str(index//10) for index in range(n)]
    return frame


class ContextualPilotChecks(unittest.TestCase):
    def test_all_configurations_have_known_block_variance(self):
        frame=example_frame();parameters=fit_blocks(frame)
        self.assertEqual(len(configurations()),15)
        for config in configurations().values():
            values,names=transform_blocks(frame,config,parameters)
            self.assertAlmostEqual(values.var(axis=0).sum(),1,places=12)
            self.assertTrue(np.isfinite(values).all())
            self.assertEqual(len(names),values.shape[1])

    def test_square_root_geometry_accepts_zeros_and_matches_formula(self):
        frame=example_frame();parameters=fit_blocks(frame)
        config=configurations()['t_hellinger']
        values,_=transform_blocks(frame,config,parameters)
        scale=parameters['contextual']['hellinger']['scale']
        self.assertAlmostEqual(np.linalg.norm(values[0]-values[1])*scale,1.)
        for i,j in [(3,4),(7,9)]:
            a,b=frame.loc[i,SHARE_COLUMNS].to_numpy(float),frame.loc[j,SHARE_COLUMNS].to_numpy(float)
            expected=np.sqrt(.5*((np.sqrt(a)-np.sqrt(b))**2).sum())
            self.assertAlmostEqual(np.linalg.norm(values[i]-values[j])*scale,expected)

    def test_category_permutation_preserves_geometry(self):
        frame=example_frame();permuted=frame.copy()
        permuted[SHARE_COLUMNS]=frame[SHARE_COLUMNS].to_numpy()[:,[2,0,1]]
        for name in ['pt_euclidean_w20','pt_hellinger_w50']:
            config=configurations()[name]
            left,_=transform_blocks(frame,config,fit_blocks(frame))
            right,_=transform_blocks(permuted,config,fit_blocks(permuted))
            np.testing.assert_allclose(((left[1:]-left[:-1])**2).sum(axis=1),((right[1:]-right[:-1])**2).sum(axis=1),atol=1e-12)

    def test_parameters_are_not_refitted_during_projection(self):
        frame=example_frame();parameters=fit_blocks(frame.iloc[:40])
        expected=parameters['behavioral']['relative']['mean']
        changed=frame.copy();changed.loc[40:,'participation_deviation_national']=10
        transform_blocks(changed,configurations()['pt_hellinger_w20'],parameters)
        self.assertEqual(parameters['behavioral']['relative']['mean'],expected)
        self.assertNotEqual(expected,changed.participation_deviation_national.mean())

    def test_invalid_compositions_are_rejected(self):
        frame=example_frame();frame.loc[0,SHARE_COLUMNS]=[.5,.5,.5]
        with self.assertRaises(ValidationError):fit_blocks(frame)

    def test_weighted_extension_matches_previous_two_dimensional_lloyd(self):
        rng=np.random.default_rng(82);values=rng.normal(size=(50,2));weights=rng.integers(1,5,len(values))
        initial=values[[2,25,40]]
        previous=lloyd(values,weights,initial);current=weighted_lloyd_nd(values,weights,initial)
        np.testing.assert_array_equal(previous['labels'],current['labels'])
        np.testing.assert_allclose(previous['centers'],current['centers'],atol=1e-12)
        self.assertAlmostEqual(previous['inertia'],current['inertia'],places=11)

    def test_weighted_extension_matches_literal_replication_in_four_dimensions(self):
        rng=np.random.default_rng(56);values=rng.normal(size=(15,4));weights=rng.integers(1,4,len(values))
        initial=values[[0,6,12]]
        weighted=weighted_lloyd_nd(values,weights,initial)
        expanded=weighted_lloyd_nd(np.repeat(values,weights,axis=0),np.ones(weights.sum()),initial)
        np.testing.assert_allclose(weighted['centers'],expanded['centers'],atol=1e-12)
        self.assertAlmostEqual(weighted['inertia'],expanded['inertia'],places=11)
        numerical_check(values,weights,weighted)

    def test_weighted_unit_mass_reproduces_existing_kmeans_and_initializations(self):
        frame=example_frame();values,_=transform_blocks(frame,configurations()['pt_hellinger_w20'],fit_blocks(frame))
        previous=kmeans(values,4,17,n_init=4,max_iter=1000)
        current=fit_model(values,4,17,4,np.ones(len(values)))
        np.testing.assert_array_equal(previous['labels'],current['labels'])
        np.testing.assert_allclose(previous['centers'],current['centers'],atol=1e-12)
        self.assertAlmostEqual(previous['inertia'],current['inertia'],places=11)
        self.assertEqual([i['seed'] for i in previous['initializations']],[i['seed'] for i in current['initializations']])

    def test_nd_prediction_and_margin_use_all_coordinates(self):
        centers=np.array([[0,0,0,0],[0,0,0,2]],float)
        values=np.array([[0,0,0,.2],[0,0,0,1],[0,0,0,1.8]],float)
        labels,margin=margins(values,centers)
        np.testing.assert_array_equal(labels,[0,0,1])
        self.assertAlmostEqual(margin[1],0.)
        self.assertGreater(margin[0],.8)

    def test_block_metrics_match_small_exact_reference(self):
        frame=example_frame();values,_=transform_blocks(frame,configurations()['pt_euclidean_w50'],fit_blocks(frame))
        fit=fit_model(values,3,17,4)
        labels=fit['labels'];anchors=np.arange(len(frame))
        scores=anchor_silhouettes(values,{'test':labels},anchors,block_size=7)['test']
        distances=np.linalg.norm(values[:,None,:]-values[None,:,:],axis=2)
        reference=validation_metrics(values,labels,distances)
        self.assertAlmostEqual(scores.mean(),reference['silhouette'],places=12)
        self.assertAlmostEqual(db_index(values,labels),reference['davies_bouldin'],places=12)

    def test_conditional_participation_is_zero_for_labels_constant_in_cell(self):
        frame=example_frame();labels=pd.factorize(frame.age_band)[0]
        r2,n=conditional_rate_r2(frame,labels,['age_band','SEXO'])
        self.assertAlmostEqual(r2,0.,places=12)
        self.assertEqual(n,len(frame))

    def test_municipal_entropy_detects_within_municipality_constancy(self):
        groups=np.repeat(np.arange(4),5)
        self.assertAlmostEqual(conditional_entropy_ratio(groups%2,groups),0)
        self.assertAlmostEqual(conditional_entropy_ratio(np.tile([0,1,0,1],5),groups),.97095,places=4)

    def test_small_pipeline_profiles_and_block_contributions(self):
        frame=example_frame(1200);config=configurations()['pt_hellinger_w20']
        values,_=transform_blocks(frame,config,fit_blocks(frame));fit=fit_model(values,4,42,4)
        diagnostics=pattern_diagnostics(frame,values,fit['labels'],config)
        self.assertAlmostEqual(diagnostics['participation_share_between']+diagnostics['context_share_between'],1.)
        self.assertGreaterEqual(diagnostics['within_age_sex_context_5_rate_r2'],0)
        self.assertLessEqual(diagnostics['within_age_sex_context_5_rate_r2'],1)
        numerical_check(values,np.ones(len(values)),fit)

    def test_initialization_seeds_and_full_output_writing(self):
        frame=example_frame(120)
        frame['row_id']=[f'test|{i}' for i in range(len(frame))]
        frame['context_is_eligible']=True;frame['pending_reason_context']='eligible'
        frame['LN']=300;frame['SV']=(frame.participation_observed*300).round().astype(int)
        frame['NV']=frame.LN-frame.SV;frame['NS']=0;frame['specified_count']=frame.LN
        frame['source_row_count']=10;frame['sex_2_source_rows']=0;frame['sex_2_nominal_count']=0
        frame['has_high_unspecified_rate']=False;frame['section_count']=5
        for t in ['U','R','M']:frame[f'LN_{t}']=300*frame[f'section_ln_share_{t}']
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'output';(output/'metadata').mkdir(parents=True)
            with patch('run_contextual_clustering_pilot.configurations',return_value={'p':configurations()['p']}),\
                 patch('run_contextual_clustering_pilot.KS',[2,3]),patch('run_contextual_clustering_pilot.SEEDS',[17]),\
                 patch('run_contextual_clustering_pilot.ROBUST_CONFIGS',['p']),patch('run_contextual_clustering_pilot.ROBUST_KS',[2,3]):
                base=np.ones(len(frame),bool)
                parameters,best,metrics=main_experiments(frame,base,output,8,2)
                sensitivity,_=sensitivity_experiments(frame,base,parameters,best,output,2,8)
                self.assertEqual(len(sensitivity),6)
                keys=pd.DataFrame({'EDOCVE':['1']*2477,'MPIOCVE':[str(i) for i in range(2477)]})
                rng=np.random.default_rng(52)
                for i in range(30):
                    # El municipio sintético 0 queda OOB en ambas muestras.
                    draw=np.zeros(2477,bool);draw[rng.choice(np.arange(1,2477),1981,replace=False)]=True
                    keys[f'sample_{i:03d}']=draw
                path=root/'data/processed/demographic_representation_comparison/resampling/municipality_membership.parquet'
                path.parent.mkdir(parents=True);keys.to_parquet(path,index=False)
                stability,coverage=municipal_resampling(frame,base,best,root,output,2,2)
                self.assertEqual(len(stability),4);self.assertEqual(len(coverage),2)
                cases=pd.read_parquet(output/'metadata/oob_municipality_changes.parquet')
                grouped=cases.groupby(['config_id','k','replicate'])[['changed_segments','oob_segments']].sum()
                for row in stability.itertuples():
                    point=grouped.loc[row.config_id,row.k,row.replicate]
                    self.assertAlmostEqual(point.changed_segments/point.oob_segments,row.oob_changed_fraction)
            initial=pd.read_csv(output/'metadata/initializations.csv')
            self.assertEqual(len(initial),4)
            self.assertTrue(initial.fit_seed.eq(17).all())
            self.assertIn('initial_seed',initial)
            labels=pd.read_parquet(output/'models/p/labels.parquet')
            self.assertEqual(len(labels),len(frame));self.assertFalse(labels.k2_seed17.isna().any())
            self.assertEqual(len(metrics),2)
            checks=audit_outputs(output,frame,np.ones(len(frame),bool))
            self.assertTrue(checks.differences.eq(0).all())


if __name__=='__main__':unittest.main()
