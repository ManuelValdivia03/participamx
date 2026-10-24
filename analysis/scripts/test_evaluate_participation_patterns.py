"""Pruebas sintéticas de forma/nivel, recuperación e integridad atómica."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from clean_data import ValidationError
from evaluate_participation_patterns import (Q,DELTA_COLUMNS,SHAPE_COLUMNS,KEYS,SUFFIXES,BANDS,
    prepare_profiles,fit_parameters,transform_patterns,block_diagnostics,write_table,write_json,
    experiment_lock,Experiment,shape_direction_summary)
from clustering_core import kmeans


def sample_profiles(n=60):
    rng=np.random.default_rng(164)
    d=rng.normal(0,.03,(n,3))+rng.normal(0,.12,(n,1))
    f=pd.DataFrame(d,columns=DELTA_COLUMNS)
    f['relative_level']=d.mean(axis=1)
    for i,c in enumerate(SHAPE_COLUMNS):f[c]=d[:,i]-d.mean(axis=1)
    f['participation_observed']=.6+d.mean(axis=1)
    f['SEXO']=['0','1']*(n//2)
    return f


def sample_cells():
    rows=[]
    for municipality in ['1','2']:
        for sex in ['0','1']:
            for i,band in enumerate(BANDS):
                ln=200+i*100;sv=80+i*50
                rows.append(dict(EDOCVE='1',MPIOCVE=municipality,SEXO=sex,age_band=band,LN=ln,SV=sv,NV=ln-sv,NS=0,
                    specified_count=ln,source_row_count=8,sex_2_source_rows=0,sex_2_nominal_count=0,unspecified_rate=0.,
                    participation_observed=sv/ln,is_present=True,row_id='c|'+municipality))
    cells=pd.DataFrame(rows);broad=cells.copy()
    municipalities=pd.DataFrame(dict(EDOCVE=['1','1'],MPIOCVE=['1','2'],state_name_label=['Estado']*2,
        municipality_name_label=['Uno','Dos'],district_reference_year=[2023]*2))
    return cells,municipalities,broad


class PatternChecks(unittest.TestCase):
    def test_orthogonal_decomposition_and_reconstruction(self):
        d=sample_profiles()[DELTA_COLUMNS].to_numpy();m=d.mean(axis=1);q=d@Q
        np.testing.assert_allclose(Q.T@Q,np.eye(2),atol=1e-14)
        np.testing.assert_allclose(Q.T@np.ones(3),0,atol=1e-14)
        np.testing.assert_allclose(m[:,None]+q@Q.T,d,atol=1e-14)
        np.testing.assert_allclose((d*d).sum(axis=1),3*m*m+(q*q).sum(axis=1),atol=1e-14)

    def test_shape_removes_level_without_normalizing_amplitude(self):
        f=sample_profiles();parameters=fit_parameters(f)
        modified=f.copy();offset=np.linspace(-.3,.3,len(f))
        modified[DELTA_COLUMNS]=modified[DELTA_COLUMNS].to_numpy()+offset[:,None]
        np.testing.assert_allclose(transform_patterns(f,'r2',parameters),transform_patterns(modified,'r2',parameters),atol=1e-13)
        q=f[DELTA_COLUMNS].to_numpy()@Q
        self.assertGreater(np.linalg.norm(q,axis=1).std(),0)

    def test_scalar_shape_scale_preserves_all_pair_distances(self):
        f=sample_profiles();parameters=fit_parameters(f);values=transform_patterns(f,'r2',parameters)
        raw=f[SHAPE_COLUMNS].to_numpy()
        np.testing.assert_allclose(np.linalg.norm(values[1:]-values[:-1],axis=1)*parameters['shape_scale'],np.linalg.norm(raw[1:]-raw[:-1],axis=1),atol=1e-13)

    def test_r3_block_variance_is_balanced(self):
        f=sample_profiles();parameters=fit_parameters(f);values=transform_patterns(f,'r3',parameters)
        self.assertAlmostEqual(values[:,0].var(ddof=0),.5)
        self.assertAlmostEqual(values[:,1:].var(axis=0,ddof=0).sum(),.5)
        self.assertAlmostEqual(transform_patterns(f,'r1',parameters).var(axis=0).sum(),1)

    def test_fixed_direction_diagnostics_preserve_shape_variance(self):
        frame=sample_profiles();delta=frame[DELTA_COLUMNS].to_numpy()
        summary=shape_direction_summary(frame)
        self.assertAlmostEqual(summary.shape_variance_fraction.sum(),1)
        self.assertAlmostEqual(np.square(summary.sd_pp/100).sum(),(delta@Q).var(axis=0).sum())
        shifted=frame.copy();shifted[DELTA_COLUMNS]=delta+np.arange(len(frame))[:,None]
        np.testing.assert_allclose(summary.sd_pp,shape_direction_summary(shifted).sd_pp,atol=1e-12)

    def test_projection_uses_only_training_parameters(self):
        f=sample_profiles();parameters=fit_parameters(f.iloc[:40]);original=parameters.copy()
        f.loc[40:,DELTA_COLUMNS]=100
        transform_patterns(f,'r3',parameters)
        self.assertEqual(parameters,original)

    def test_references_counts_and_three_coordinates(self):
        cells,municipalities,broad=sample_cells();profiles,reference,national=prepare_profiles(cells,municipalities,broad)
        self.assertEqual(len(profiles),4);self.assertTrue(profiles.row_id.is_unique)
        self.assertTrue(profiles.is_eligible.all());self.assertEqual(profiles.LN.sum(),broad.LN.sum())
        for band in BANDS:
            expected=cells[cells.age_band.eq(band)].SV.sum()/cells[cells.age_band.eq(band)].specified_count.sum()
            np.testing.assert_allclose(national[national.age_band.eq(band)].national_rate,expected)
        np.testing.assert_allclose(profiles[SHAPE_COLUMNS].sum(axis=1),0,atol=1e-14)

    def test_undefined_band_propagates_to_shape_and_is_not_imputed(self):
        cells,municipalities,broad=sample_cells()
        for frame in [cells,broad]:
            frame.loc[0,['SV','NV','specified_count']]=0;frame.loc[0,'NS']=frame.loc[0,'LN']
            frame.loc[0,'participation_observed']=np.nan;frame.loc[0,'unspecified_rate']=1.
        profiles,_,_=prepare_profiles(cells,municipalities,broad)
        blocked=profiles[(profiles.MPIOCVE=='1')&(profiles.SEXO=='0')].iloc[0]
        self.assertFalse(blocked.is_eligible);self.assertTrue(np.isnan(blocked.relative_level))
        self.assertTrue(blocked[SHAPE_COLUMNS].isna().all())

    def test_simple_average_is_not_aggregate_rate(self):
        cells,municipalities,broad=sample_cells();profiles,_,_=prepare_profiles(cells,municipalities,broad)
        self.assertFalse(np.isclose(profiles.mean_observed_rate.iloc[0],profiles.participation_observed.iloc[0]))

    def test_atomic_parquet_and_lock_prevent_second_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'table.parquet';frame=pd.DataFrame(dict(code=['01','02'],value=[1.,np.nan]))
            write_table(path,frame);pd.testing.assert_frame_equal(frame,pd.read_parquet(path))
            self.assertFalse(list(root.glob('*.tmp.*')))
            with experiment_lock(root):
                with self.assertRaises(ValidationError):
                    with experiment_lock(root):pass
            self.assertFalse((root/'_RUNNING.json').exists())

    def test_checkpoint_detects_corruption_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);experiment=Experiment.__new__(Experiment)
            experiment.root=root;experiment.output=root/'output';experiment.state_path=experiment.output/'metadata/state.json';experiment.state={'stages':{}}
            path=experiment.output/'table.parquet';write_table(path,pd.DataFrame({'value':[1,2]}))
            import time
            experiment.checkpoint('B',[path],time.monotonic(),'Prueba')
            self.assertTrue(experiment.valid_stage('B'));path.write_bytes(b'incomplete')
            with self.assertRaises(ValidationError):experiment.valid_stage('B')
            self.assertEqual(path.read_bytes(),b'incomplete')

    def test_model_bundle_is_reused_without_a_second_fit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);experiment=Experiment.__new__(Experiment)
            experiment.root=root;experiment.output=root/'output';experiment.state_path=experiment.output/'metadata/state.json'
            experiment.state={};experiment.config=dict(n_init=3,max_iter=1000)
            values=transform_patterns(sample_profiles(),'r2',fit_parameters(sample_profiles()))
            folder=experiment.output/'model';fit=experiment.model(folder,values,3,17)
            with patch('evaluate_participation_patterns.kmeans',side_effect=AssertionError('No repetir ajuste')):
                resumed=experiment.model(folder,values,3,17)
            np.testing.assert_array_equal(fit['labels'],resumed['labels']);self.assertEqual(fit['inertia'],resumed['inertia'])

    def test_level_contribution_is_zero_for_r2_even_if_correlated(self):
        frame=sample_profiles();parameters=fit_parameters(frame);values=transform_patterns(frame,'r2',parameters)
        fit=kmeans(values,3,17,n_init=3)
        diagnosis=block_diagnostics(frame,fit['labels'],'r2',parameters)
        self.assertEqual(diagnosis['between_level_share'],0.)
        self.assertAlmostEqual(diagnosis['between_shape_share'],1.)


if __name__=='__main__':unittest.main()
