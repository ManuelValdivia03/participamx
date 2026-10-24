"""Pruebas de geometría, restricciones convexas, biblioteca y entregables."""
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from evaluate_archetypal_patterns import (ROOT, basis, fit_scaler, transform, inverse,
    validate_convex, synthetic_validation, mixture_statistics, aligned, errors_summary, json_safe)


class GeometryTests(unittest.TestCase):
    def setUp(self):self.rng=np.random.default_rng(42)

    def test_orthogonal_level_shape_and_distance_identity(self):
        for p in [3,4]:
            q=basis(p);d=self.rng.normal(size=(30,p));m=d.mean(1);c=d@q
            np.testing.assert_allclose(q.T@q,np.eye(p-1),atol=1e-12)
            np.testing.assert_allclose(q.T@np.ones(p),0,atol=1e-12)
            np.testing.assert_allclose(d,m[:,None]+c@q.T,atol=1e-12)
            diff=d[0]-d[1]
            self.assertAlmostEqual(float(diff@diff),p*(m[0]-m[1])**2+float(np.sum((c[0]-c[1])**2)))

    def test_scalers_reversible_training_only_and_balanced(self):
        for p in [3,4]:
            d=self.rng.normal(size=(30,p));out=self.rng.normal(100,5,size=(7,p))
            for geometry in ['AA1','AA2']:
                s=fit_scaler(d,geometry,[str(i) for i in range(30)])
                np.testing.assert_allclose(inverse(transform(out,s),s),out,atol=1e-12)
                self.assertEqual(s['n'],30)
                x=transform(d,s)
                if geometry=='AA2':
                    self.assertAlmostEqual(float(x[:,0].var()),.5)
                    self.assertAlmostEqual(float(x[:,1:].var(0).sum()),.5)
                b=self.rng.dirichlet(np.ones(30),size=3)
                np.testing.assert_allclose(inverse(b@x,s),b@d,atol=1e-12)

    def test_convex_guards_and_affine_reconstruction(self):
        x=np.array([[0.,0.],[1.,0.],[0.,1.]])
        a=np.array([[.2,.3,.5],[1,0,0]])
        validate_convex(a,np.eye(3),x,x,np.zeros((2,2)))
        with self.assertRaises((ValueError,AssertionError,RuntimeError)):
            validate_convex(a*2,np.eye(3),x,x,np.zeros((2,2)))
        with self.assertRaises((ValueError,AssertionError,RuntimeError)):
            validate_convex(a,np.eye(3),x+1,x,np.zeros((2,2)))

    def test_alignment_invariant_to_numbering(self):
        z=self.rng.normal(size=(4,3));permutation=np.array([2,0,3,1]);order,dist=aligned(z,z[permutation])
        np.testing.assert_allclose(z,z[permutation][order]);np.testing.assert_allclose(dist,0)

    def test_entropy_and_nonunique_mixtures(self):
        a=np.array([[1.,0.,0.],[1/3,1/3,1/3],[.5,.5,0]])
        s=mixture_statistics(a)
        self.assertTrue(s.dominated.iloc[0]);self.assertAlmostEqual(s.normalized_entropy.iloc[1],1.)
        # Cuatro vértices en 2D: el centro admite mezclas distintas.
        z=np.array([[0.,0.],[1.,0.],[1.,1.],[0.,1.]])
        np.testing.assert_allclose(np.array([.5,0,.5,0])@z,np.array([0,.5,0,.5])@z)
        self.assertLess(np.linalg.matrix_rank(z[1:]-z[0]),len(z)-1)

    def test_error_vs_training_mean_and_strict_json(self):
        x=np.array([[1.,2.],[3.,4.]])
        e=errors_summary(x,x,x,x,x.mean(0));self.assertEqual(e['normalized_rmse'],0)
        self.assertEqual(json.dumps(json_safe({'x':np.nan}),allow_nan=False),'{"x": null}')


class LibraryTests(unittest.TestCase):
    def test_actual_aa_fit_transform_and_independent_projection(self):
        result=synthetic_validation()
        self.assertEqual(result['status'],'passed')
        self.assertLess(result['projection_sse_excess_slsqp'],1e-6)


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=ROOT/'data/processed/archetypal_pattern_review'
        if not (cls.base/'metadata/checkpoint_e.json').exists():raise unittest.SkipTest('El experimento todavía no terminó la etapa E.')

    def test_common_population_and_metadata(self):
        a=pd.read_parquet(self.base/'matrices/three_common/metadata.parquet')
        b=pd.read_parquet(self.base/'matrices/four_natural/metadata.parquet')
        self.assertEqual(len(a),4571);self.assertTrue(a.row_id.equals(b.row_id))
        for name in ['LN','SV','NV','NS','source_row_count']:
            np.testing.assert_array_equal(a[name],b[name])
        self.assertEqual(int(a.LN.sum()),98119426)

    def test_resampling_keeps_municipalities_together_and_oob_scaler(self):
        tables=pd.read_csv(self.base/'metadata/municipal_resampling.csv')
        for _,row in tables.iterrows():
            f=pd.read_parquet(self.base/f'matrices/{row.context}/metadata.parquet')
            with np.load(self.base/'models'/row.model_id/'arrays.npz') as values:
                mask=values['training_mask'];self.assertTrue(mask.any() and (~mask).any())
                flags=f[['EDOCVE','MPIOCVE']].copy();flags['flag']=mask
                self.assertTrue(flags.groupby(['EDOCVE','MPIOCVE']).flag.nunique().eq(1).all())
            details=json.loads((self.base/'models'/row.model_id/'details.json').read_text())
            self.assertEqual(details['scaler']['n'],int(mask.sum()))

    def test_pending_complement_and_all_convex_models(self):
        full=pd.read_parquet(self.base/'reference/complementary_and_full_broad.parquet')
        self.assertEqual(len(full),17735);self.assertEqual(int(full.LN.sum()),98330348)
        self.assertEqual(int(full.sex_2_nominal_count.sum()),105)
        for path in (self.base/'models').rglob('arrays.npz'):
            with np.load(path) as a:
                validate_convex(a['alpha'],a['beta'],a['archetypes'],a['values'][a['training_mask']],a['values'])
                np.testing.assert_allclose(a['reconstruction'],a['alpha']@a['archetypes'],atol=1e-10)
                np.testing.assert_allclose(a['archetypes_original'],a['archetypes_absolute']-a['archetypes_peer_reference'],atol=1e-10)

    def test_original_vs_common_status_and_source_manifests(self):
        status=pd.read_parquet(self.base/'matrices/three_common/observation_status.parquet')
        self.assertEqual(int((status.matrix_status=='outside_common_population').sum()),77)
        sources=json.loads((self.base/'metadata/validated_sources.json').read_text())
        self.assertEqual(len(sources),3)
        self.assertTrue(all(s['validated_artifacts']>0 for s in sources))


if __name__=='__main__':unittest.main()
