"""Pruebas de reglas, frontera, conservación, uniones y contrato público."""
import copy
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from build_profile_candidates import (assign_candidates, national_reference, exact_direction,
    join_r2, validate_contract, build_schema, table_text, METRICS)


def fixture():
    rows=[]
    for index,(sv,nv,ns,band,sex,source_rows) in enumerate([
        (60,40,0,'18-34','0',8), (40,60,0,'18-34','0',8),
        (50,50,0,'18-34','0',8), (0,0,100,'18-34','0',8),
        (1,1,0,'18-34','0',2), (60,40,0,'18-34','0',4),
        (1,1,0,'101+','0',2), (1,0,0,'18-34','2',1)]):
        rows.append(dict(row_id=str(index),EDOCVE='01',MPIOCVE=str(index),age_band=band,SEXO=sex,
                         LN=sv+nv+ns,SV=sv,NV=nv,NS=ns,source_row_count=source_rows,
                         sex_2_source_rows=source_rows if sex=='2' else 0,
                         sex_2_nominal_count=sv+nv+ns if sex=='2' else 0))
    return pd.DataFrame(rows)


class RuleTests(unittest.TestCase):
    def test_reference_uses_sums_before_support(self):
        source=fixture();segments,reference=assign_candidates(source)
        peer=reference[reference.age_band.eq('18-34')&reference.SEXO.eq('0')].iloc[0]
        self.assertEqual(peer.SV,211)
        self.assertEqual(peer.national_specified_count,402)
        self.assertAlmostEqual(peer.national_rate,211/402)
        self.assertEqual(len(source),len(segments))
        pd.testing.assert_series_equal(source[METRICS].sum(),segments[METRICS].sum())

    def test_no_undefined_zero_imputation(self):
        result,_=assign_candidates(fixture())
        row=result[result.row_id.eq('3')].iloc[0]
        self.assertTrue(pd.isna(row.local_turnout))
        self.assertTrue(pd.isna(row.participation_delta))
        self.assertEqual(row.assignment_status,'undefined_rate')
        self.assertTrue(pd.isna(row.candidate_id))

    def test_support_separate_from_rule(self):
        result,_=assign_candidates(fixture())
        row=result[result.row_id.eq('5')].iloc[0]
        self.assertEqual(row.rule_candidate_id,'young_favorable')
        self.assertTrue(pd.isna(row.candidate_id))
        self.assertEqual(row.assignment_status,'insufficient_support')
        self.assertFalse(row.low_ln);self.assertFalse(row.low_specified)
        self.assertTrue(row.few_source_rows)

    def test_exact_tie_is_not_favorable(self):
        source=fixture().iloc[:3].copy()
        result,_=assign_candidates(source)
        row=result[result.row_id.eq('2')].iloc[0]
        self.assertEqual(row.assignment_status,'at_reference')
        self.assertEqual(row.direction,0)
        self.assertTrue(pd.isna(row.candidate_id))

    def test_sign_does_not_overflow_int64(self):
        result=exact_direction([10**15,10**15-1,5],[2*10**15,2*10**15,10],
                               [10**15,10**15,50],[2*10**15,2*10**15,100])
        np.testing.assert_array_equal(result,[0,-1,0])

    def test_complementary_keeps_sex2_and_extreme_age(self):
        result,_=assign_candidates(fixture())
        tail=result[result.row_id.isin(['6','7'])]
        self.assertTrue(tail.assignment_status.eq('complementary').all())
        self.assertTrue(tail.candidate_id.isna().all())
        self.assertEqual(tail.sex_2_nominal_count.sum(),1)

    def test_duplicate_segments_fail(self):
        with self.assertRaises(Exception):
            assign_candidates(pd.concat([fixture(),fixture().iloc[:1]],ignore_index=True))

    def test_join_many_to_one_preserves_rows(self):
        source=fixture()
        lookup=source[['EDOCVE','MPIOCVE','SEXO']].drop_duplicates().assign(is_eligible=True,pending_reason='eligible',k2_seed17=1)
        joined=join_r2(source,lookup)
        self.assertEqual(len(joined),len(source))
        self.assertEqual(joined.LN.sum(),source.LN.sum())
        with self.assertRaises(Exception):
            join_r2(source,pd.concat([lookup,lookup.iloc[:1]],ignore_index=True))

    def test_unknown_r2_stays_null(self):
        source=fixture();lookup=source.iloc[:1][['EDOCVE','MPIOCVE','SEXO']].assign(is_eligible=True,pending_reason='eligible',k2_seed17=0)
        result=join_r2(source,lookup)
        self.assertEqual(result.r2_label.isna().sum(),len(source)-1)

    def test_markdown_escapes_pipes(self):
        text=table_text(pd.DataFrame({'name|test':['a|b']}))
        self.assertIn('name\\|test',text);self.assertIn('a\\|b',text)


class ContractTests(unittest.TestCase):
    def test_nullable_rate_and_bounds(self):
        schema={'type':['number','null'],'minimum':0,'maximum':1}
        for value in [None,0,.5,1]:validate_contract(value,schema)
        for value in [-.1,1.1,float('nan'),float('inf'),True,'0']:
            with self.subTest(value=value),self.assertRaises(Exception):validate_contract(value,schema)

    def test_closed_object(self):
        schema={'type':'object','required':['a'],'properties':{'a':{'type':'integer','minimum':0}},'additionalProperties':False}
        validate_contract({'a':1},schema)
        for value in [{},{'a':1,'b':2},{'a':True},{'a':-1}]:
            with self.subTest(value=value),self.assertRaises(Exception):validate_contract(value,schema)

    def test_unsupported_schema_fails_closed(self):
        with self.assertRaises(Exception):validate_contract('x',{'pattern':'x'})

    def test_strict_constants(self):
        with self.assertRaises(Exception):validate_contract(True,{'const':1})


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[2]
        cls.output=cls.root/'data/processed/profile_candidates_review'

    def setUp(self):
        if not (self.output/'_SUCCESS').exists():self.skipTest('Artefactos aún no generados.')

    def test_json_matches_actual_results(self):
        payload=json.loads((self.output/'candidates/profile_candidates.json').read_text(encoding='utf-8'))
        schema=json.loads((self.output/'contracts/profile_payload.schema.json').read_text(encoding='utf-8'))
        validate_contract(payload,schema)
        self.assertEqual(len(payload['profiles']),6)
        frame=pd.read_parquet(self.output/'reference/segments_2024.parquet')
        supported=frame[frame.candidate_id.notna()]
        for metric in METRICS:
            self.assertEqual(sum(x['counts'][metric] for x in payload['profiles']),supported[metric].sum())
        for card in payload['profiles']:
            data=supported[supported.candidate_id.eq(card['id'])]
            self.assertAlmostEqual(card['participation']['observed'],data.SV.sum()/(data.SV.sum()+data.NV.sum()))
            self.assertEqual(card['counts']['municipalities'],len(data[['EDOCVE','MPIOCVE']].drop_duplicates()))

    def test_example_is_validated_subset(self):
        full=json.loads((self.output/'candidates/profile_candidates.json').read_text(encoding='utf-8'))
        example=json.loads((self.output/'examples/profile_payload.example.json').read_text(encoding='utf-8'))
        validate_contract(example,build_schema())
        self.assertEqual(example['profiles'],full['profiles'][:1])
        bad=copy.deepcopy(example);bad['profiles'][0]['participation']['observed']=1.5
        with self.assertRaises(Exception):validate_contract(bad,build_schema())

    def test_count_conservation_and_pending(self):
        data=pd.read_parquet(self.output/'reference/segments_2024.parquet')
        self.assertEqual(len(data),17735);self.assertEqual(data.LN.sum(),98330348)
        self.assertEqual(data.source_row_count.sum(),9773730)
        self.assertTrue(data.LN.eq(data.SV+data.NV+data.NS).all())
        self.assertFalse(data.row_id.duplicated().any())
        self.assertTrue(data.candidate_id.notna().equals(data.assignment_status.eq('supported_candidate')))
        self.assertEqual(data[data.SEXO.eq('2')].LN.sum(),105)
        self.assertTrue(data[data.SEXO.eq('2')].candidate_id.isna().all())
        for code in ['EDOCVE','MPIOCVE','SEXO']:
            self.assertTrue(data[code].map(lambda x:isinstance(x,str)).all())

    def test_r2_crosswalk_has_no_count_expansion(self):
        data=pd.read_parquet(self.output/'reference/segments_2024.parquet')
        cross=pd.read_csv(self.output/'diagnostics/r2_crosswalk.csv')
        self.assertEqual(cross.segments.sum(),data.candidate_id.notna().sum())
        self.assertEqual(cross.LN.sum(),data.loc[data.candidate_id.notna(),'LN'].sum())
        np.testing.assert_allclose(cross.groupby('candidate_id').within_candidate_segment_fraction.sum(),1)

    def test_history_reconciles(self):
        reconciliation=pd.read_csv(self.output/'metadata/state_reconciliation.csv')
        self.assertEqual(len(reconciliation),6*32*7)
        self.assertTrue(reconciliation.difference.eq(0).all())
        history=pd.read_parquet(self.output/'historical/national_peer_references.parquet')
        self.assertEqual(len(history),36)
        self.assertFalse(history.duplicated(['election_year','age_band','SEXO']).any())
        self.assertTrue(history.LN.eq(history.SV+history.NV+history.NS).all())

    def test_ns_robustness_strict_subset(self):
        frame=pd.read_parquet(self.output/'diagnostics/ns_sensitivity.parquet')
        self.assertTrue((~frame.sign_robust_both_bounds|frame.sign_robust_fixed_reference).all())
        self.assertTrue(frame.local_lower.le(frame.local_upper).all())

    def test_manifest_and_report_integrity(self):
        from clean_data import file_hash
        manifest_path=self.output/'metadata/run_manifest.json'
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        marker=json.loads((self.output/'_SUCCESS').read_text(encoding='utf-8'))
        self.assertEqual(marker['manifest_sha256'],file_hash(manifest_path))
        self.assertEqual(manifest['model_fits'],0)
        self.assertEqual(manifest['status'],'validated')
        for name,digest in manifest['artifact_hashes'].items():
            self.assertEqual(file_hash(self.root/name),digest,name)

    def test_figure_links_and_markdown_tables(self):
        import re
        report=self.root/'analysis/reports/profile_candidates_review.md'
        text=report.read_text(encoding='utf-8');width=None
        for line in text.splitlines():
            if line.startswith('| '):
                count=len(re.split(r'(?<!\\)\|',line))
                if width is not None:self.assertEqual(count,width,line)
                width=count
            else:width=None
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',text):
            if '://' not in target:self.assertTrue((report.parent/target).exists(),target)


if __name__=='__main__':unittest.main()
