"""Pruebas sintéticas de bibliotecas, métricas, ruido y recuperación."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from clean_data import ValidationError
from compare_pattern_algorithms import (Comparison,posterior_summary,label_metrics,
    common_partition_stability,describe_groups,aligned_changes)
from evaluate_participation_patterns import SUFFIXES,KEYS


def toy_profiles():
    rng=np.random.default_rng(181);values=np.r_[rng.normal(-2,.15,(18,2)),rng.normal(2,.15,(18,2))]
    n=len(values);frame=pd.DataFrame(dict(EDOCVE=['01']*n,MPIOCVE=[str(i//2) for i in range(n)],SEXO=['0','1']*(n//2),
        LN=[900]*n,SV=[540]*n,NV=[330]*n,NS=[30]*n,source_row_count=[60]*n,sex_2_source_rows=[0]*n,
        sex_2_nominal_count=[0]*n,specified_count=[870]*n,relative_level=values[:,0]/100,has_high_ns_coordinate=[False]*n))
    for suffix in SUFFIXES:
        for field,value in [('LN',300),('SV',180),('NV',110),('NS',10),('rate',180/290),('delta',.02),('shape',0)]:frame[field+'_'+suffix]=value
    return values,frame


class PosteriorTests(unittest.TestCase):
    def test_uncertainty_is_conditional_probability(self):
        summary=posterior_summary(np.array([[.5,.5],[1.,0.]]))
        self.assertEqual(summary['ambiguous_80'],.5)
        self.assertAlmostEqual(summary['mean_normalized_entropy'],.5)
        self.assertEqual(posterior_summary(np.ones((3,1)))['mean_normalized_entropy'],0)

    def test_invalid_posterior_is_rejected(self):
        with self.assertRaises(ValidationError):posterior_summary([[.2,.3]])

    def test_counts_include_noise_without_duplicating_bands(self):
        values,frame=toy_profiles();labels=np.r_[[-1]*4,[0]*14,[1]*18]
        profiles,curves=describe_groups(frame,labels,'toy')
        self.assertEqual(profiles.observations.sum(),len(frame));self.assertEqual(profiles.LN.sum(),frame.LN.sum())
        self.assertEqual(curves.LN.sum(),frame.LN.sum());self.assertIn(-1,profiles.cluster.to_list())


@unittest.skipUnless(importlib.util.find_spec('sklearn') and importlib.util.find_spec('scipy'),'Requiere el entorno independiente de bibliotecas.')
class LibraryTests(unittest.TestCase):
    def test_alignment_does_not_confuse_label_permutation_with_change(self):
        self.assertFalse(aligned_changes([0,0,1,1],[1,1,0,0]).any())
        self.assertEqual(aligned_changes([0,0,0,1,1],[1,1,0,0,0]).sum(),1)

    def test_metrics_use_assigned_population_only_and_count_noise(self):
        values,frame=toy_profiles();labels=np.r_[[-1]*4,[0]*14,[1]*18]
        result=label_metrics(values,labels,frame)
        self.assertEqual(result['assigned'],32);self.assertEqual(result['metric_population'],32)
        self.assertEqual(result['unassigned'],4);self.assertGreater(result['silhouette'],.8)
        self.assertAlmostEqual(result['assigned_LN_fraction'],32/36)

    def test_no_silhouette_for_single_cluster_or_all_noise(self):
        values,frame=toy_profiles()
        for labels in [np.zeros(len(frame),int),np.full(len(frame),-1,int)]:
            self.assertTrue(np.isnan(label_metrics(values,labels,frame)['silhouette']))

    def test_noise_agreement_is_not_named_cluster_stability(self):
        result=common_partition_stability([0,0,-1,-1],[0,0,-1,-1])
        self.assertEqual(result['ari_common_all'],1)
        self.assertTrue(np.isnan(result['ari_common_both_assigned']))
        self.assertEqual(result['assignment_jaccard'],1)

    def test_library_gmm_regularizes_singular_data(self):
        from sklearn.mixture import GaussianMixture
        values=np.column_stack([np.linspace(-1,1,40)]*2)
        model=GaussianMixture(2,reg_covar=1e-6,n_init=2,random_state=17).fit(values)
        self.assertTrue(model.converged_);posterior_summary(model.predict_proba(values))
        self.assertGreater(np.linalg.eigvalsh(model.covariances_).min(),0)

    def test_ward_uses_one_tree_for_multiple_cuts(self):
        from scipy.cluster.hierarchy import linkage,cut_tree
        values,_=toy_profiles();tree=linkage(values,method='ward');labels=cut_tree(tree,n_clusters=[2,3,4])
        self.assertEqual(tree.shape,(len(values)-1,4))
        self.assertEqual([len(np.unique(labels[:,i])) for i in range(3)],[2,3,4])
        self.assertTrue((np.diff(tree[:,2])>=0).all())

    def test_hdbscan_native_has_noise_and_no_fabricated_predictions(self):
        from sklearn.cluster import HDBSCAN
        values,_=toy_profiles();model=HDBSCAN(min_cluster_size=8,min_samples=4,allow_single_cluster=True,algorithm='kd_tree').fit(values)
        self.assertEqual(len(model.labels_),len(values));self.assertFalse(hasattr(model,'predict'))
        self.assertTrue((model.probabilities_>=0).all())

    def test_bundle_recovers_without_running_callback(self):
        values,_=toy_profiles()
        with tempfile.TemporaryDirectory() as folder:
            experiment=Comparison.__new__(Comparison);experiment.output=Path(folder)
            calls=[]
            def create():calls.append(1);return None,dict(labels=np.zeros(len(values),int)),dict(converged=True)
            first=experiment.bundle('toy',values,dict(k=1),create)
            def forbidden():raise AssertionError('No repetir ajuste')
            second=experiment.bundle('toy',values,dict(k=1),forbidden)
            np.testing.assert_array_equal(first[1]['labels'],second[1]['labels']);self.assertEqual(calls,[1])
            with self.assertRaises(ValidationError):experiment.bundle('toy',values+1,dict(k=1),forbidden)

    @unittest.skipUnless(importlib.util.find_spec('kmedoids'),'Biblioteca opcional.')
    def test_native_medoid_objective_is_sum_of_unsquared_distances(self):
        from scipy.spatial.distance import cdist
        import kmedoids
        values,_=toy_profiles();distances=cdist(values,values)
        result=kmedoids.fasterpam(distances,2,random_state=17,n_cpu=1)
        self.assertEqual(len(np.unique(result.medoids)),2)
        self.assertAlmostEqual(result.loss,distances[np.arange(len(values)),np.asarray(result.medoids)[result.labels]].sum())


if __name__=='__main__':unittest.main()
