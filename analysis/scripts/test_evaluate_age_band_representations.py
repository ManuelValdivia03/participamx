"""Pruebas de bases, cobertura, conteos, secciones y escalamiento."""
import unittest
import numpy as np
import pandas as pd
from evaluate_age_band_representations import (helmert_basis,shape_block,fit_block,apply_block,coverage_gate,
    combine_cells,section_counts,build_profiles,describe_covariance,SCHEMES,KEYS)
from evaluate_participation_patterns import Q
from build_descriptive import METRICS


class RepresentationTests(unittest.TestCase):
    def test_helmert_reproduces_previous_basis(self):np.testing.assert_array_equal(helmert_basis(3),Q)

    def test_reconstruction_and_isometry_all_dimensions(self):
        rng=np.random.default_rng(62)
        for n in [3,4,5]:
            delta=rng.normal(size=(20,n));basis=helmert_basis(n);level,shape,q=shape_block(delta)
            np.testing.assert_allclose(basis.T@basis,np.eye(n-1),atol=1e-14)
            np.testing.assert_allclose(basis.T@np.ones(n),0,atol=1e-14)
            np.testing.assert_allclose(q@basis.T,shape,atol=1e-14)
            np.testing.assert_allclose(level[:,None]+q@basis.T,delta,atol=1e-14)
            np.testing.assert_allclose(np.linalg.norm(q[1:]-q[:-1],axis=1),np.linalg.norm(shape[1:]-shape[:-1],axis=1),atol=1e-14)

    def test_level_invariance_and_amplitude_retention(self):
        d=np.random.default_rng(63).normal(size=(30,5));q=shape_block(d)[2]
        np.testing.assert_allclose(q,shape_block(d+np.arange(30)[:,None])[2],atol=1e-13)
        np.testing.assert_allclose(shape_block(2*d)[2],2*q,atol=1e-13)

    def test_block_has_unit_total_variance_and_training_parameters_only(self):
        q=np.random.default_rng(64).normal(size=(40,4));parameters=fit_block(q[:30]);copy=parameters.copy()
        self.assertAlmostEqual(apply_block(q[:30],parameters).var(axis=0).sum(),1)
        apply_block(q[30:]+100,parameters);self.assertEqual(copy,parameters)

    def test_gate_is_strict_and_either_alert_blocks(self):
        base=dict(municipalities=2000,eligible_LN=90000000)
        self.assertFalse(coverage_gate(dict(municipalities=1800,eligible_LN=90000000),base)['training_allowed'])
        self.assertFalse(coverage_gate(dict(municipalities=2000,eligible_LN=88000000),base)['training_allowed'])
        self.assertTrue(coverage_gate(base,base)['training_allowed'])
        edge=coverage_gate(dict(municipalities=1950,eligible_LN=90000000),base,total_municipalities=1000)
        self.assertEqual(edge['municipal_drop_pp'],5);self.assertTrue(edge['training_allowed'])

    def test_four_sums_counts_instead_of_averaging_rates(self):
        rows=[]
        for j,(a,b) in enumerate(SCHEMES['five']):
            rows.append(dict(EDOCVE='01',MPIOCVE='001',SEXO='0',age_band=f'{a}-{b}',LN=100+j*100,SV=20+j*30,NV=80+j*70,NS=0,source_row_count=10,sex_2_source_rows=0,sex_2_nominal_count=0))
        life=pd.DataFrame(rows);four=combine_cells(life,life,'four');old=four[four.age_band.eq('60-100')].iloc[0]
        self.assertEqual(old.LN,900);self.assertEqual(old.SV,250)
        self.assertNotAlmostEqual(old.SV/old.LN,np.mean([110/400,140/500]))

    def test_older_section_union_is_not_sum_of_overlapping_bands(self):
        def frame(bands,counts):
            rows=[]
            for band,count in zip(bands,counts):
                rows.append(dict(EDOCVE='01',MPIOCVE='001',SEXO='0',TIPOSEC='U',age_band=band,section_count=count,**{f:1 for f in METRICS}))
            return pd.DataFrame(rows)
        life=frame(['18-29','30-44','45-59','60-74','75-100'],[4,4,4,4,4]);broad=frame(['60-100'],[5])
        result=section_counts(life,broad,'four');self.assertEqual(result[result.age_band.eq('60-100')].section_count.iloc[0],5)

    def test_spectral_variance_is_diagnostic_and_conserved(self):
        d=np.random.default_rng(65).normal(size=(80,4));before=d.copy()
        eigen,coefficients,named,cov=describe_covariance(d,'four','toy')
        self.assertAlmostEqual(eigen.fraction.sum(),1);self.assertAlmostEqual(eigen.variance.sum(),np.trace(cov))
        np.testing.assert_array_equal(before,d)
        for _,part in coefficients.groupby('direction'):self.assertAlmostEqual(part.coefficient.sum(),0)

    def test_profile_nulls_do_not_become_zero_or_partial_means(self):
        base=pd.DataFrame([dict(row_id=f'{m}_{sex}',EDOCVE='01',MPIOCVE=m,SEXO=sex) for m in ['01','02'] for sex in ['0','1']])
        rows=[]
        for _,key in base.iterrows():
            for a,b in SCHEMES['three']:
                rows.append(dict(**{f:key[f] for f in KEYS},age_band=f'{a}-{b}',LN=200,SV=100,NV=80,NS=20,source_row_count=5,section_count=1,sex_2_source_rows=0,sex_2_nominal_count=0))
        cells=pd.DataFrame(rows);cells.loc[0,['SV','NV']]=0;cells.loc[0,'NS']=200
        profiles,_,_=build_profiles(cells,base,'three');bad=profiles.iloc[0]
        self.assertFalse(bad.is_eligible);self.assertTrue(np.isnan(bad.relative_level));self.assertTrue(bad[[f'shape_{j}' for j in range(3)]].isna().all())
        self.assertEqual(profiles.LN.sum(),cells.LN.sum());self.assertTrue(profiles.iloc[1].is_eligible)
        self.assertEqual(profiles.iloc[1].min_section_count,1)  # No confundir cinco filas con cinco secciones.


if __name__=='__main__':unittest.main()
