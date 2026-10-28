"""Comprobaciones sintéticas del contrato y la geometría, antes del ajuste electoral."""
import unittest
import numpy as np
import pandas as pd
from sklearn.metrics import silhouette_samples
from research_profiles import (eligible, references, fit_parameters, transform, conditional_r2,
                               silhouette_anchors, fit, predict, CONFIGS, METRICS)


def fixture():
    rows=[]
    for band in ['18-34','35-59','60-100']:
        for sex in ['0','1']:
            for section in ['U','R','M']:
                for i in range(4):
                    rows.append(dict(age_band=band,SEXO=sex,TIPOSEC=section,LN=200,SV=40+i*30,NV=160-i*30,NS=0,source_row_count=10,sex_2_source_rows=0,sex_2_nominal_count=0,participation_observed=(40+i*30)/200,delta_age_sex=(i-1.5)*.15,delta_age_sex_section=(i-1.5)*.15))
    return pd.DataFrame(rows)


class ResearchTests(unittest.TestCase):
    def test_block_variances_and_unseen_training_values(self):
        frame=fixture()
        params=fit_parameters(frame,CONFIGS['age_sex_50'])
        values=transform(frame,params)
        self.assertEqual(values.shape,(72,9))
        np.testing.assert_allclose(np.var(values[:,:1],axis=0).sum(),.5)
        for columns in [slice(1,4),slice(4,6),slice(6,9)]:
            np.testing.assert_allclose(np.var(values[:,columns],axis=0).sum(),1/6)
        changed=frame.iloc[:2].copy();changed.delta_age_sex=10
        self.assertGreater(transform(changed,params)[0,0],10)
        self.assertEqual(params['n'],72)
        invalid=frame.copy();invalid.loc[0,'SEXO']='2'
        with self.assertRaises(ValueError):transform(invalid,params)

    def test_category_permutation_preserves_distances(self):
        frame=fixture();other=frame.copy()
        other.TIPOSEC=other.TIPOSEC.map({'U':'M','M':'R','R':'U'})
        a=transform(frame,fit_parameters(frame,CONFIGS['age_sex_50']))
        b=transform(other,fit_parameters(other,CONFIGS['age_sex_50']))
        np.testing.assert_allclose(((a[0]-a)**2).sum(axis=1),((b[0]-b)**2).sum(axis=1))

    def test_reference_sums_before_support_and_no_NS_as_NV(self):
        frame=fixture();frame.loc[0,['LN','SV','NV','NS','source_row_count']]=[200,0,0,200,1]
        result=references(frame,['age_band','SEXO'])
        part=frame[(frame.age_band=='18-34')&(frame.SEXO=='0')]
        self.assertAlmostEqual(result.iloc[0].reference,part.SV.sum()/(part.SV.sum()+part.NV.sum()))
        self.assertFalse(eligible(frame).iloc[0]);self.assertEqual(frame.NS.sum(),200)
        frame.loc[1,'SEXO']='2';self.assertFalse(eligible(frame).iloc[1])
        frame.loc[2,'age_band']='101+';self.assertFalse(eligible(frame).iloc[2])

    def test_silhouette_against_sklearn_and_real_optimizer(self):
        values=np.array([[0.,0.],[0.,1.],[1.,0.],[10.,10.],[10.,11.],[11.,10.]])
        model=fit(values,2,17,5)
        np.testing.assert_array_equal(model.labels_,predict(values,model.cluster_centers_))
        np.testing.assert_allclose(silhouette_anchors(values,model.labels_,np.arange(6)),silhouette_samples(values,model.labels_),atol=1e-12)

    def test_conditional_separation_does_not_reward_only_strata(self):
        frame=fixture()
        labels=pd.factorize(frame.age_band)[0]
        self.assertAlmostEqual(conditional_r2(frame,labels,['age_band','SEXO','TIPOSEC']),0)
        labels=np.tile(np.arange(4),18)
        self.assertAlmostEqual(conditional_r2(frame,labels,['age_band','SEXO','TIPOSEC']),1)


if __name__=='__main__':unittest.main()
