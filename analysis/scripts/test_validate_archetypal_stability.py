"""Pruebas de selección sin OOB, separación de variabilidad y trazabilidad."""
import hashlib
import json
import unittest
import numpy as np
import pandas as pd

from validate_archetypal_stability import (ROOT,CONFIG,SEEDS,choose_best,extreme_mask,
    paired_effects,variance_partition,curve_contrasts,validate_convex,synthetic_validation)


class MathematicalTests(unittest.TestCase):
    def test_selection_ignores_oob_and_curve_appearance(self):
        f=pd.DataFrame(dict(seed=[17,42,2024],sse=[3.,1.,2.],oob_rmse_pp=[0.,999.,.1]))
        self.assertEqual(int(choose_best(f).seed),42)
        f.oob_rmse_pp=[999.,0.,999.]
        self.assertEqual(int(choose_best(f).seed),42)

    def test_extreme_fraction_and_deterministic_tie_breaking(self):
        x=np.zeros((101,3));ids=np.array([f'row_{i:03d}' for i in range(101)])
        mask,dist=extreme_mask(x,ids)
        self.assertEqual(int((~mask).sum()),2);self.assertFalse(mask[0]);self.assertFalse(mask[1])
        np.testing.assert_array_equal(dist,0)

    def test_variance_identity_and_limits(self):
        rng=np.random.default_rng(42);values=rng.normal(size=(10,10,9))
        v=variance_partition(values)
        self.assertAlmostEqual(v['within_seed_pp2']+v['between_sample_means_pp2'],v['total_pp2'])
        self.assertAlmostEqual(v['within_fraction']+v['between_fraction'],1)
        deterministic=np.repeat(rng.normal(size=(10,1,9)),10,axis=1)
        self.assertAlmostEqual(variance_partition(deterministic)['within_seed_pp2'],0.)
        identical_samples=np.repeat(rng.normal(size=(1,10,9)),10,axis=0)
        self.assertAlmostEqual(variance_partition(identical_samples)['between_sample_means_pp2'],0.)

    def test_curve_permutations_do_not_change_metrics(self):
        z=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])
        a=np.array([[.2,.3,.5],[.1,.8,.1]]);p=np.array([2,0,1]);ref=dict(archetypes_original=z,alpha=a,reconstruction_original=a@z)
        alt=dict(archetypes_original=z[p],alpha=a[:,p],reconstruction_original=a@z)
        effect=paired_effects(ref,alt)
        self.assertAlmostEqual(effect['max_curve_shift_pp'],0.)
        self.assertAlmostEqual(effect['alpha_l1_mean'],0.)
        self.assertAlmostEqual(effect['reconstruction_difference_rmse_pp'],0.)

    def test_contrasts_and_real_library(self):
        contrasts=curve_contrasts(np.array([[.1,.2,.3]]))
        self.assertAlmostEqual(contrasts.level_pp.iloc[0],20.)
        self.assertAlmostEqual(contrasts.young_minus_older_pp.iloc[0],-20.)
        self.assertEqual(synthetic_validation()['status'],'passed')


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=ROOT/'data/processed/archetypal_stability_review'
        if not (cls.base/'metadata/checkpoint_e.json').exists():raise unittest.SkipTest('Etapa E todavía no terminada.')
        cls.catalog=pd.read_parquet(cls.base/'metadata/all_initializations.parquet')

    def test_all_starts_retained_and_no_other_k(self):
        self.assertEqual(len(self.catalog),270)
        self.assertTrue(self.catalog.trial_id.is_unique)
        self.assertEqual(set(self.catalog.k),{2,3})
        for _,rows in self.catalog.groupby(['experiment','sample','scenario','k']):
            self.assertEqual(len(rows),10);self.assertEqual(set(rows.seed),set(SEEDS))
        self.assertEqual(int(self.catalog.reused.sum()),32)

    def test_common_coverage_and_complementary_observations(self):
        f=pd.read_parquet(self.base/'reference/eligible_profiles.parquet')
        self.assertEqual(len(f),4571);self.assertEqual(f.groupby(['EDOCVE','MPIOCVE']).ngroups,2296)
        self.assertEqual(int(f.LN.sum()),98119426)
        b=pd.read_parquet(self.base/'reference/broad_complete_reference.parquet')
        self.assertEqual(len(b),17735);self.assertEqual(int(b.LN.sum()),98330348)
        self.assertEqual(int(b.sex_2_nominal_count.sum()),105)
        for k in [2,3]:
            full=pd.read_parquet(self.base/f'selected/fixed_k{k}/all_observations.parquet')
            self.assertEqual(len(full),4954)
            self.assertTrue(full.loc[~full.in_matrix,[f'alpha_{j}' for j in range(k)]].isna().all().all())

    def test_convexity_models_scales_and_grouped_resampling(self):
        f=pd.read_parquet(self.base/'reference/eligible_profiles.parquet')
        for _,row in self.catalog.iterrows():
            folder=ROOT/row.artifact_folder
            with np.load(folder/'arrays.npz') as a:
                mask=a['training_mask'];x=a['values'];validate_convex(a['alpha'],a['beta'],a['archetypes'],x[mask],x)
                np.testing.assert_allclose(a['reconstruction'],a['alpha']@a['archetypes'],atol=1e-10)
                np.testing.assert_allclose(a['archetypes_original'],a['archetypes_absolute']-a['archetypes_peer_reference'],atol=1e-10)
                if row.experiment=='municipal':
                    flag=f[['EDOCVE','MPIOCVE']].copy();flag['training']=mask
                    self.assertTrue(flag.groupby(['EDOCVE','MPIOCVE']).training.nunique().eq(1).all())
                    np.testing.assert_allclose(x[mask].mean(0),0,atol=1e-12)
                    detail=json.loads((folder/'details.json').read_text())
                    self.assertEqual(detail['scaler']['n'],int(mask.sum()))
                    self.assertEqual(detail['scaler']['fitted_row_ids_sha256'],hashlib.sha256('\n'.join(f.loc[mask,'row_id']).encode()).hexdigest())

    def test_best_is_selected_only_by_training_objective(self):
        for name,keys in [('fixed',['k']),('municipal',['sample','k']),('sensitivity',['scenario'])]:
            all_rows=pd.read_parquet(self.base/f'metadata/{name}_initializations.parquet')
            selected=pd.read_csv(self.base/f'metadata/{name}_best.csv')
            for group,rows in all_rows.groupby(keys):
                expected=choose_best(rows)
                self.assertTrue((selected.trial_id==expected.trial_id).any())

    def test_single_observation_sensitivities_and_information_identity(self):
        excluded=pd.read_parquet(self.base/'sensitivity/exclusion_membership.parquet')
        self.assertEqual(int((~excluded.training_E1).sum()),46)
        self.assertEqual(int(excluded.training_E2.sum()),2641)
        for c in excluded.columns:
            if c.startswith('training_E3'):self.assertEqual(int((~excluded[c]).sum()),1)
        info=json.loads((self.base/'comparisons/information_identity.json').read_text())
        self.assertLess(info['max_original_reconstruction_error'],1e-12)
        linked=pd.read_parquet(self.base/'comparisons/rules_and_continuous_indicators.parquet')
        self.assertEqual(len(linked),4571);self.assertTrue(linked.row_id.is_unique)


if __name__=='__main__':unittest.main()
