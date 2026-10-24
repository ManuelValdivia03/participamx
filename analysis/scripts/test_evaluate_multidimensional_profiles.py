"""Comprueba referencias, soporte, geometría por bloques y recuperación."""
import json
import os
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
from sklearn.metrics import silhouette_samples
from evaluate_multidimensional_profiles import (build_features,join_metadata,fit_scalers,transform,
    residual_fraction,block_separation,conditional_fraction,aligned_labels,Q,BLOCKS,METRICS,SEGMENT_KEYS,
    BANDS,PROFILE_KEYS,MUNICIPAL_KEYS,SUFFIXES)
from evaluate_exact_age_clustering import anchor_silhouettes


def fixture():
    rng=np.random.default_rng(12024);rows=[]
    for municipality in range(8):
        shares=rng.dirichlet([1,2,1])
        for sex in ['0','1']:
            for j,band in enumerate(BANDS):
                ln=1000;ns=30;sv=int(rng.integers(300,800));nv=ln-ns-sv
                u=int(ln*shares[0]);r=int(ln*shares[1]);m=ln-u-r
                rows.append(dict(row_id=f'{municipality}|{sex}|{band}',EDOCVE='01',MPIOCVE=str(municipality),SEXO=sex,
                    age_band=band,election_year=2024,LN=ln,SV=sv,NV=nv,NS=ns,specified_count=sv+nv,
                    source_row_count=20,sex_2_source_rows=0,sex_2_nominal_count=0,
                    participation_observed=sv/(sv+nv),unspecified_rate=ns/ln,
                    section_ln_share_U=u/ln,section_ln_share_R=r/ln,section_ln_share_M=m/ln))
    full=pd.DataFrame(rows)
    national=full.groupby(['age_band','SEXO'])[['SV','NV']].sum()
    refs=national.SV/(national.SV+national.NV)
    profiles=[]
    for key,g in full.groupby(PROFILE_KEYS,observed=True):
        row=dict(zip(PROFILE_KEYS,key));row['is_eligible']=True
        delta=[]
        for band,suffix in zip(BANDS,SUFFIXES):
            local=g[g.age_band.eq(band)].iloc[0];d=local.participation_observed-refs.loc[(band,key[-1])]
            row['delta_'+suffix]=d;row['unspecified_rate_'+suffix]=local.unspecified_rate;delta.append(d)
        for j,suffix in enumerate(SUFFIXES):row['shape_'+suffix]=delta[j]-np.mean(delta)
        profiles.append(row)
    municipalities=full.groupby(MUNICIPAL_KEYS,as_index=False)[['LN','SV','NV','NS']].sum()
    municipalities['election_year']=2024;municipalities['participation_observed']=municipalities.SV/(municipalities.SV+municipalities.NV)
    return full,pd.DataFrame(profiles),municipalities


class FeatureTests(unittest.TestCase):
    def test_references_use_all_counts_and_preserve_order(self):
        full,profiles,municipalities=fixture();result,reference,_,_=build_features(full,profiles,municipalities)
        self.assertTrue(result.row_id.equals(full.row_id));self.assertEqual(len(result),len(full))
        pd.testing.assert_series_equal(result[METRICS].sum(),full[METRICS].sum())
        local=full.groupby(['age_band','SEXO'])[['SV','NV']].sum()
        for r in reference.itertuples():self.assertAlmostEqual(r.national_peer_rate,local.loc[(r.age_band,r.SEXO),'SV']/local.loc[(r.age_band,r.SEXO)].sum())

    def test_gap_is_female_minus_male_and_shared(self):
        result,_,_,_=build_features(*fixture())
        for _,g in result.groupby(MUNICIPAL_KEYS+['age_band']):
            self.assertEqual(g.sex_gap_adjusted.nunique(),1)
            self.assertAlmostEqual(g.sex_gap_adjusted.iloc[0],g[g.SEXO.eq('1')].relative_turnout.iloc[0]-g[g.SEXO.eq('0')].relative_turnout.iloc[0])

    def test_gap_null_without_both_sexes_support(self):
        full,p,m=fixture();full.loc[0,'source_row_count']=4
        result,_,_,_=build_features(full,p,m)
        pair=result[result.MPIOCVE.eq('0')&result.age_band.eq(BANDS[0])]
        self.assertTrue(pair.sex_gap_adjusted.isna().all());self.assertFalse(pair.S_available.any())

    def test_shape_null_without_complete_supported_pattern(self):
        full,p,m=fixture();p.loc[0,'is_eligible']=False
        result,_,_,_=build_features(full,p,m)
        mask=result.MPIOCVE.eq('0')&result.SEXO.eq('0')
        self.assertTrue(result.loc[mask,BLOCKS['A']].isna().all().all())
        self.assertFalse(result.loc[mask,'common_eligible'].any())

    def test_shape_removes_constant_and_reconstructs_centered_curve(self):
        d=np.array([[.1,-.05,.03],[.1,.2,.3]])
        np.testing.assert_allclose(d@Q,(d+3)@Q,atol=1e-15)
        np.testing.assert_allclose((d@Q)@Q.T,d-d.mean(axis=1,keepdims=True),atol=1e-15)

    def test_composition_geometry_accepts_zeros_and_preserves_distances(self):
        p=np.array([[1.,0,0],[0,1,0],[.2,.3,.5]])
        for a,b in [(0,1),(0,2),(1,2)]:
            self.assertAlmostEqual(np.linalg.norm(p[a]-p[b]),np.linalg.norm(p[a]@Q-p[b]@Q))
        np.testing.assert_allclose(Q.T@Q,np.eye(2),atol=1e-15)
        np.testing.assert_allclose(np.ones(3)@Q,0,atol=1e-15)

    def test_municipal_indicator_is_weighted_peer_difference(self):
        result,_,_,_=build_features(*fixture())
        for _,g in result.groupby(MUNICIPAL_KEYS):
            expected=float(np.average(g.relative_turnout,weights=g.specified_count))
            self.assertAlmostEqual(g.municipal_adjusted_turnout.iloc[0],expected)
            self.assertEqual(g.municipal_adjusted_turnout.nunique(),1)

    def test_many_to_one_rejects_duplicate_metadata(self):
        f,_,_=fixture();right=f[MUNICIPAL_KEYS].copy()
        with self.assertRaises(Exception):join_metadata(f,right,MUNICIPAL_KEYS)


class GeometryTests(unittest.TestCase):
    def setUp(self):self.frame=build_features(*fixture())[0]

    def test_rms_equal_total_variance_for_unequal_block_dimensions(self):
        blocks=['P','A','S'];parameters=fit_scalers(self.frame,blocks)
        x,slices,weights=transform(self.frame,blocks,parameters)
        for b,(a,z) in slices.items():
            self.assertAlmostEqual(float(np.mean(np.sum(x[:,a:z]**2,axis=1))),1/3)
            self.assertAlmostEqual(weights[b],1/3)
        np.testing.assert_allclose(x.mean(axis=0),0,atol=1e-14)

    def test_train_only_scaling(self):
        p=fit_scalers(self.frame.iloc[:20],['P']);shifted=self.frame.copy();shifted.loc[20:,'relative_turnout']=999
        p2=fit_scalers(shifted.iloc[:20],['P'])
        self.assertEqual(p,p2)
        x,_,_=transform(shifted,['P'],p)
        self.assertGreater(float(x[20,0]),100)

    def test_block_weight_sensitivity_is_explicit(self):
        p=fit_scalers(self.frame,['P','A','S']);_,_,w=transform(self.frame,['P','A','S'],p,p_heavy=True)
        self.assertEqual(w,dict(P=.5,A=.25,S=.25))

    def test_distance_and_between_decompositions(self):
        p=fit_scalers(self.frame,['P','A']);x,slices,_=transform(self.frame,['P','A'],p)
        squared=np.sum((x[0]-x[1])**2)
        self.assertAlmostEqual(squared,sum(np.sum((x[0,a:b]-x[1,a:b])**2) for a,b in slices.values()))
        labels=(x[:,0]>=0).astype(int);shares,_=block_separation(x,labels,slices)
        self.assertAlmostEqual(sum(shares.values()),1.)

    def test_linear_dependence_diagnostic(self):
        x=np.arange(20)[:,None]
        self.assertLess(residual_fraction(2*x+3,x),1e-25)

    def test_no_conditional_gain_from_rules_themselves(self):
        values=np.arange(20,dtype=float);groups=np.repeat([0,1],10)
        self.assertAlmostEqual(conditional_fraction(values,groups,groups),0)

    def test_silhouette_anchors_match_independent_library(self):
        x=np.array([[-2.,0],[-1.9,0],[-2.1,0],[2.,.1],[2.1,0],[1.9,0]])
        labels=np.array([0,0,0,1,1,1]);anchors=np.array([0,2,3,5])
        own=anchor_silhouettes(x,{'test':labels},anchors,block_size=2)['test']
        np.testing.assert_allclose(own,silhouette_samples(x,labels)[anchors],atol=1e-13)

    def test_alignment_is_label_invariant_and_handles_missing_components(self):
        a=np.array([0,0,1,1]);b=np.array([2,2,7,7]);aligned,_=aligned_labels(a,b)
        np.testing.assert_array_equal(a,aligned)
        aligned,_=aligned_labels(a,np.array([0,0,0,0]));self.assertEqual(len(aligned),len(a))


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[2]
        cls.output=Path(os.environ.get('PARTICIPAMX_MULTIDIM_OUTPUT',str(cls.root/'data/processed/multidimensional_profile_review')))
        cls.report=Path(os.environ.get('PARTICIPAMX_MULTIDIM_REPORT',str(cls.root/'analysis/reports/multidimensional_profile_review.md')))

    def setUp(self):
        if not (self.output/'metadata/checkpoint_F.json').exists():self.skipTest('Validación de artefactos tras etapa F.')

    def test_reference_counts_and_common_population(self):
        d=pd.read_parquet(self.output/'reference/segments.parquet');main=d[d.common_eligible]
        self.assertEqual(len(d),17735);self.assertEqual(d.LN.sum(),98330348);self.assertEqual(d.source_row_count.sum(),9773730)
        self.assertEqual(d[d.SEXO.eq('2')].LN.sum(),105)
        self.assertEqual(len(main),13908);self.assertEqual(len(main[MUNICIPAL_KEYS].drop_duplicates()),2341)
        self.assertEqual(main.LN.sum(),98149089)
        self.assertFalse(d.duplicated(SEGMENT_KEYS).any())

    def test_all_matrices_have_identical_row_ids_and_full_rank(self):
        d=pd.read_parquet(self.output/'reference/segments.parquet');ids=d.loc[d.common_eligible,'row_id'].reset_index(drop=True)
        for path in (self.output/'features').glob('*/matrix.parquet'):
            frame=pd.read_parquet(path);self.assertTrue(frame.row_id.equals(ids))
            x=frame.drop(columns='row_id').to_numpy();self.assertTrue(np.isfinite(x).all())
            self.assertEqual(np.linalg.matrix_rank(x-x.mean(axis=0)),x.shape[1])

    def test_resampling_keeps_municipalities_together(self):
        for path in (self.output/'resampling').glob('sample_*/*_assignments.parquet'):
            frame=pd.read_parquet(path)
            self.assertTrue(frame.is_oob_eligible.equals(~frame.is_training))
            self.assertTrue(frame.groupby(MUNICIPAL_KEYS).is_training.nunique().eq(1).all())

    def test_posteriors_and_pending_assignments(self):
        for path in (self.output/'models').glob('f*/gmm/k*/seed*/arrays.npz'):
            with np.load(path) as a:
                self.assertEqual(a['posterior'].shape[0],13908)
                np.testing.assert_allclose(a['posterior'].sum(axis=1),1,atol=1e-12)
        full=pd.read_parquet(self.output/'reference/segments.parquet')
        for path in (self.output/'assignments').rglob('*.parquet'):
            frame=pd.read_parquet(path);self.assertEqual(len(frame),len(full))
            self.assertTrue(frame.label.notna().equals(full.common_eligible))

    def test_primary_cluster_profiles_conserve_counts(self):
        source=pd.read_parquet(self.output/'reference/segments.parquet');main=source[source.common_eligible]
        for name in ['principal','contextual']:
            path=self.output/f'metadata/{name}_cluster_profiles.parquet'
            if not path.exists():continue
            frame=pd.read_parquet(path)
            for _,part in frame.groupby('model_id'):
                np.testing.assert_array_equal(part[METRICS].sum().to_numpy(),main[METRICS].sum().to_numpy())

    def test_oob_scaler_hash_matches_training_rows_only(self):
        import hashlib
        for path in (self.output/'resampling').glob('sample_*/*_scalers.json'):
            assignments=path.with_name(path.name.replace('_scalers.json','_assignments.parquet'))
            frame=pd.read_parquet(assignments);parameters=json.loads(path.read_text(encoding='utf8'))
            ids=frame.loc[frame.is_training,'row_id']
            digest=hashlib.sha256('\n'.join(ids).encode()).hexdigest()
            for block in parameters.values():
                self.assertEqual(block['n'],len(ids));self.assertEqual(block['fitted_row_ids_sha256'],digest)

    def test_same_seed_sensitivity_is_explicit(self):
        path=self.output/'diagnostics/sensitivity_same_seed.csv'
        if not path.exists():self.skipTest('Se genera al presentar resultados.')
        frame=pd.read_csv(path)
        self.assertTrue(frame.fit_seed.eq(17).all())
        self.assertTrue(frame.baseline_same_seed.str.endswith('/seed17').all())
        self.assertFalse(frame.duplicated(['model_id','scenario']).any())

    def test_report_tables_and_local_figures(self):
        import re
        report=self.report
        if not report.exists():self.skipTest('Informe aún no generado.')
        text=report.read_text(encoding='utf8');width=None
        for line in text.splitlines():
            if line.startswith('| '):
                n=len(re.split(r'(?<!\\)\|',line))
                if width is not None:self.assertEqual(n,width,line)
                width=n
            else:width=None
        for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',text):
            if '://' not in link:self.assertTrue((report.parent/link).exists(),link)

    def test_numerical_diagnostic_json_uses_null_not_nonstandard_nan(self):
        path=self.output/'diagnostics/contextual_gmm_regularization.json'
        if not path.exists():self.skipTest('No se necesitó diagnóstico contextual.')
        def reject_constant(value):raise ValueError(value)
        diagnostic=json.loads(path.read_text(encoding='utf8'),parse_constant=reject_constant)
        self.assertIsNone(diagnostic['separation_A'])
        self.assertIsNone(diagnostic['separation_M'])
        self.assertGreaterEqual(diagnostic['ari'],0)


if __name__=='__main__':unittest.main()
