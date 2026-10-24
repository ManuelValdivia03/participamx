"""Pruebas sintéticas y semánticas del paquete electoral multianual."""
from __future__ import annotations
import os
import json
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
import build_multiyear_profiles as pipeline
from build_profile_candidates import exact_direction


def segment(municipality='1',band='18-34',sex='0',sv=100,nv=100,ns=0,rows=5):
    return dict(EDOCVE='1',MPIOCVE=municipality,age_band=band,SEXO=sex,
        LN=sv+nv+ns,SV=sv,NV=nv,NS=ns,source_row_count=rows,sex_2_source_rows=0,sex_2_nominal_count=0)


class FormulaTests(unittest.TestCase):
    def test_ns_is_not_abstention_and_undefined_is_not_zero(self):
        frame=pipeline.add_rates(pd.DataFrame([segment(sv=0,nv=0,ns=100),segment(sv=0,nv=100,ns=20),segment(sv=60,nv=40,ns=100)]))
        self.assertTrue(np.isnan(frame.participation_observed.iloc[0]))
        self.assertEqual(frame.participation_observed.iloc[1],0)
        self.assertEqual(frame.participation_observed.iloc[2],.6)
        self.assertEqual(frame.unspecified_rate.iloc[2],.5)

    def test_reference_uses_insufficient_segments_before_support(self):
        frame=pd.DataFrame([segment(sv=100,nv=100),segment('2',sv=0,nv=99,rows=1)])
        result,reference=pipeline.assign_candidates(frame)
        self.assertAlmostEqual(reference.national_rate.iloc[0],100/299)
        self.assertEqual(result.assignment_status.iloc[1],'insufficient_support')
        self.assertEqual(result.direction.iloc[0],1)

    def test_references_are_separate_election_calls(self):
        _,first=pipeline.assign_candidates(pd.DataFrame([segment(sv=100,nv=300)]))
        _,second=pipeline.assign_candidates(pd.DataFrame([segment(sv=300,nv=100)]))
        self.assertEqual(first.national_rate.iloc[0],.25)
        self.assertEqual(second.national_rate.iloc[0],.75)

    def test_exact_tie_and_integer_cross_products(self):
        huge=10**18
        directions=exact_direction([huge,huge,huge+1],[2*huge,2*huge+1,2*huge],[1,1,1],[2,2,2])
        np.testing.assert_array_equal(directions,[0,-1,1])
        result,_=pipeline.assign_candidates(pd.DataFrame([segment()]))
        self.assertEqual(result.assignment_status.iloc[0],'at_reference')
        self.assertTrue(pd.isna(result.candidate_id.iloc[0]))

    def test_each_quality_condition_is_preserved(self):
        frame=pd.DataFrame([segment(sv=20,nv=20,rows=6),segment('2',sv=90,nv=0,ns=30),segment('3',sv=100,nv=100,rows=4)])
        result,_=pipeline.assign_candidates(frame)
        self.assertEqual(result.low_ln.tolist(),[True,False,False])
        self.assertEqual(result.low_specified.tolist(),[True,True,False])
        self.assertEqual(result.few_source_rows.tolist(),[False,False,True])

    def test_complements_are_not_assigned_to_hm(self):
        frame=pd.DataFrame([segment(band='101+',sv=100,nv=200),segment('2',sex='2',sv=150,nv=100)])
        result,_=pipeline.assign_candidates(frame)
        self.assertTrue(result.assignment_status.eq('complementary').all())
        self.assertTrue(result.candidate_id.isna().all())
        self.assertEqual(result.SV.sum(),250)

    def test_age_boundaries_do_not_drop_extreme_ages(self):
        self.assertEqual(pipeline.age_bands([18,34,35,59,60,100,101,140]).tolist(),
            ['18-34','18-34','35-59','35-59','60-100','60-100','101+','101+'])

    def test_continuous_absence_keeps_null_and_separate_support(self):
        raw=pd.DataFrame([segment(band=b) for b in pipeline.BANDS]+[segment('2')])
        assigned,_=pipeline.assign_candidates(raw);assigned['section_count']=2
        municipalities=pd.DataFrame([dict(EDOCVE='1',MPIOCVE=m,state_name_label='Estado',municipality_name_label=m,district_reference_year=2021) for m in ['1','2']])
        continuous,gaps,_=pipeline.build_continuous(assigned,municipalities,2009)
        self.assertEqual(len(continuous),4)
        partial=continuous[(continuous.MPIOCVE=='2')&(continuous.SEXO=='0')].iloc[0]
        self.assertFalse(partial.complete_profile)
        self.assertTrue(pd.isna(partial.LN_1))
        self.assertTrue(pd.isna(partial.relative_level))
        self.assertFalse(gaps.S_available.any())
        complete=continuous[(continuous.MPIOCVE=='1')&(continuous.SEXO=='0')].iloc[0]
        self.assertTrue(complete.is_eligible)
        self.assertAlmostEqual(sum(complete['shape_'+str(j)] for j in range(3)),0)

    def test_empty_candidate_is_explicit_not_fabricated(self):
        result,_=pipeline.assign_candidates(pd.DataFrame([segment()]))
        result['section_count']=1
        summary=pipeline.summarize_profiles(result,200)
        self.assertEqual(set(summary.candidate_id),set(pipeline.IDS))
        self.assertTrue(summary.status.eq('no_supported_segments').all())
        self.assertTrue(summary.participation_observed.isna().all())
        self.assertEqual(summary.LN.sum(),0)

    def test_duplicate_segments_fail(self):
        with self.assertRaises(Exception):pipeline.assign_candidates(pd.DataFrame([segment(),segment()]))


class ContractTests(unittest.TestCase):
    def test_nullable_history_does_not_fix_all_years_to_null(self):
        records=[dict(election_year=2009,LN=None),dict(election_year=2024,LN=105)]
        schema=pipeline.value_schema(records)
        pipeline.validate_json(records,schema)
        with self.assertRaises(Exception):pipeline.validate_json([dict(election_year=2024,LN='105')],schema)

    def test_null_zero_nan_and_infinity(self):
        result=json.loads(pipeline.json_bytes(dict(known_zero=0,unknown=np.nan,missing=pd.NA)))
        self.assertEqual(result,dict(known_zero=0,unknown=None,missing=None))
        with self.assertRaises(ValueError):pipeline.json_bytes(dict(value=np.inf))

    def test_schema_signed_adjusted_and_rate_named_count(self):
        schema=pipeline.frame_schema(pd.DataFrame(dict(election_year=[2024],municipal_adjusted_turnout=[-.2],undefined_segment_rates=[137],unspecified_rate=[.2])),'test','Prueba')
        row=schema['properties']['data']['items']
        pipeline.validate_json(dict(election_year=2009,municipal_adjusted_turnout=-.4,undefined_segment_rates=500,unspecified_rate=.3),row)
        with self.assertRaises(Exception):pipeline.validate_json(dict(election_year=2009,municipal_adjusted_turnout=-.4,undefined_segment_rates=500,unspecified_rate=1.3),row)

    def test_closed_schema_and_bool_is_not_integer(self):
        schema=pipeline.object_schema(dict(count=dict(type='integer',minimum=0)))
        for bad in [dict(count=True),dict(count=1,extra=2),dict(),dict(count=-1)]:
            with self.assertRaises(Exception):pipeline.validate_json(bad,schema)

    def test_codes_are_text_and_year_is_mandatory(self):
        schema=pipeline.frame_schema(pd.DataFrame(dict(election_year=[2024],state_code=['1'],municipality_code=['10'],sex_code=['0'])),'test','Prueba')['properties']['data']['items']
        pipeline.validate_json(dict(election_year=2009,state_code='1',municipality_code='10',sex_code='0'),schema)
        with self.assertRaises(Exception):pipeline.validate_json(dict(election_year=2009,state_code=1,municipality_code='10',sex_code='0'),schema)
        with self.assertRaises(Exception):pipeline.validate_json(dict(state_code='1',municipality_code='10',sex_code='0'),schema)


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output=Path(os.environ.get('PARTICIPAMX_MULTIYEAR_OUTPUT',pipeline.ROOT/'data/processed/participamx_multiyear'))
        if not (cls.output/'historical/quality_summary.parquet').exists():raise unittest.SkipTest('Aún no se han generado los artefactos históricos.')
        cls.index=json.loads((cls.output/'elections_index.json').read_text(encoding='utf8'))
        cls.years=[e['election_year'] for e in cls.index['elections']]
        cls.tables={year:{name:pd.read_parquet(cls.output/f'elections/{year}/tables/{name}.parquet') for name in ['segments','profiles','continuous','sex_gaps','municipalities','states','year','national_references','quality_summary']} for year in cls.years}

    def test_full_delivery_or_requested_subset(self):
        state=json.loads((self.output/'metadata/state.json').read_text(encoding='utf8'))
        self.assertEqual(self.years,state['years'])
        self.assertEqual(len(self.index['elections']),len(set(self.years)))
        self.assertFalse(self.index['municipal_history_enabled'])

    def test_conservation_unique_keys_and_disjoint_assignments(self):
        for year,tables in self.tables.items():
            with self.subTest(year=year):
                segments=tables['segments'];total=tables['year'].iloc[0]
                self.assertTrue(segments.LN.eq(segments.SV+segments.NV+segments.NS).all())
                for metric in pipeline.METRICS:self.assertEqual(int(segments[metric].sum()),int(total[metric]))
                self.assertFalse(segments.duplicated(['election_year',*pipeline.SEGMENT_KEYS]).any())
                self.assertEqual(segments.election_year.unique().tolist(),[year])
                self.assertTrue(segments.candidate_id.notna().equals(segments.assignment_status.eq('supported_candidate')))
                self.assertTrue(segments.local_turnout.isna().equals(segments.specified_count.eq(0)))
                self.assertFalse(segments.loc[segments.SEXO.eq('2'),'in_scope'].any())
        if self.years==pipeline.YEARS:
            self.assertEqual(sum(int(t['year'].source_row_count.iloc[0]) for t in self.tables.values()),54872712)

    def test_own_references_before_support(self):
        for year,tables in self.tables.items():
            result=tables['segments'].groupby(['age_band','SEXO'])[pipeline.METRICS].sum().sort_index()
            reference=tables['national_references'].set_index(['age_band','SEXO']).sort_index()
            pd.testing.assert_frame_equal(result,reference[pipeline.METRICS],check_dtype=False)
            np.testing.assert_allclose(pipeline.safe_ratio(result.SV,result.SV+result.NV),reference.national_rate,atol=1e-15,rtol=0,equal_nan=True)

    def test_profile_counts_and_union_municipal_coverage(self):
        for year,tables in self.tables.items():
            profiles=tables['profiles'];segments=tables['segments'];chosen=segments[segments.candidate_id.notna()]
            self.assertEqual(set(profiles.candidate_id),set(pipeline.IDS));self.assertEqual(len(profiles),6)
            quality=tables['quality_summary'].iloc[0]
            self.assertEqual(int(profiles.LN.sum()),int(quality.supported_LN))
            self.assertEqual(int(profiles.segments.sum()),len(chosen))
            self.assertEqual(chosen.groupby(pipeline.MUNICIPAL_KEYS).ngroups,int(quality.supported_municipalities))
            self.assertAlmostEqual(float(quality.supported_nominal_fraction),chosen.LN.sum()/segments.LN.sum())
            for profile,row in profiles.set_index('candidate_id').iterrows():
                group=chosen[chosen.candidate_id.eq(profile)]
                if len(group):
                    self.assertAlmostEqual(row.participation_observed,group.SV.sum()/group.specified_count.sum())
                    expected=np.sum(group.specified_count*group.national_rate)/group.specified_count.sum()
                    self.assertAlmostEqual(row.matched_peer_reference,expected)

    def test_shape_identity_and_gaps_support(self):
        for year,tables in self.tables.items():
            continuous=tables['continuous'];gaps=tables['sex_gaps']
            self.assertEqual(len(continuous),2*len(tables['municipalities']))
            self.assertFalse(continuous.duplicated(pipeline.PROFILE_KEYS).any())
            complete=continuous[continuous.complete_profile]
            d=complete[['participation_delta_'+str(j) for j in range(3)]].to_numpy(float)
            q=complete[['contrast_0','contrast_1']].to_numpy(float)
            np.testing.assert_allclose(d,complete.relative_level.to_numpy()[:,None]+q@pipeline.Q.T,atol=1e-14,rtol=0)
            self.assertTrue(continuous.loc[~continuous.complete_profile,'relative_level'].isna().all())
            self.assertTrue(gaps.loc[~gaps.S_available,'sex_gap_adjusted'].isna().all())
            valid=gaps[gaps.S_available]
            np.testing.assert_allclose(valid.sex_gap_adjusted,valid.female_participation_delta-valid.male_participation_delta,atol=1e-15,rtol=0)

    def test_context_exhaustive_and_section_uniqueness(self):
        for year,tables in self.tables.items():
            segment=tables['segments'];inventory=pd.read_parquet(self.output/f'elections/{year}/tables/section_inventory.parquet')
            for metric in pipeline.METRICS:self.assertTrue(segment[[metric+'_'+t for t in pipeline.TYPES]].sum(axis=1).eq(segment[metric]).all())
            self.assertFalse(inventory.duplicated(['EDOCVE','MPIOCVE','SECCION','TIPOSEC']).any())
            self.assertFalse(inventory.groupby(['EDOCVE','MPIOCVE','SECCION']).TIPOSEC.nunique().gt(1).any())
            self.assertTrue(tables['profiles'].distinct_sections.isna().all())

    def test_state_reconciliation_and_2024_regression(self):
        check=pd.read_csv(self.output/'validation/state_reconciliation.csv')
        self.assertEqual(len(check),32*len(self.years))
        self.assertTrue(check.filter(like='difference_').eq(0).all().all())
        regression=pd.read_csv(self.output/'validation/regression_2024.csv')
        self.assertEqual(len(regression),6)
        self.assertTrue(regression.status.eq('passed').all())
        self.assertLessEqual(regression.max_absolute_difference.max(),1e-12)

    def test_json_contracts_paths_years_and_no_nonstandard_numbers(self):
        for year,tables in self.tables.items():
            base=self.output/f'elections/{year}';metadata=json.loads((base/'metadata.json').read_text(encoding='utf8'))
            self.assertEqual(metadata['election_year'],year)
            self.assertFalse(metadata['municipal_history_enabled'])
            self.assertEqual(metadata['district_reference_year'],2023 if year==2024 else 2021)
            self.assertEqual([x['code'] for x in metadata['sex_categories']],['0','1','2'] if year==2024 else ['0','1'])
            for name,relative in metadata['resources'].items():
                paths=[base/relative.format(state_code=code) for code in metadata['state_codes']] if '{state_code}' in relative else [base/relative]
                self.assertTrue(all(p.exists() for p in paths))
                # Todas las filas se validaron al exportar; aquí se relee cada recurso global y un shard de cada clase.
                for path in paths[:1]:
                    value=json.loads(path.read_text(encoding='utf8'),parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))
                    if name=='metadata':continue
                    self.assertEqual(value['election_year'],year)
                    self.assertTrue(all(r['election_year']==year for r in value['data']))
                    schema=json.loads((self.output/f'schemas/{name}.schema.json').read_text(encoding='utf8'))
                    pipeline.validate_json(value,schema)
            continuous=json.loads((base/'continuous_indicators.json').read_text(encoding='utf8'))
            self.assertEqual(continuous['unit'],'municipality_sex')
            self.assertEqual(len(continuous['data']),2*len(tables['municipalities']))

    def test_no_fabricated_sex2_history_or_municipal_trajectories(self):
        comparison=json.loads((self.output/'historical_comparison.json').read_text(encoding='utf8'))
        for row in comparison['nonbinary_availability']:
            if row['election_year']!=2024:
                self.assertEqual(row['status'],'category_not_recorded')
                self.assertTrue(all(row[field] is None for field in pipeline.COUNTS))
        def visit(value):
            if isinstance(value,dict):
                self.assertNotIn('municipality_code',value)
                for child in value.values():visit(child)
            elif isinstance(value,list):
                for child in value:visit(child)
        visit(comparison)


if __name__=='__main__':unittest.main()
