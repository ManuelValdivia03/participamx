"""Comprueba límites, sumas, nulos y significado de los perfiles candidatos."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from build_descriptive import DEFAULT_THRESHOLDS, METRICS, add_indicators, sum_groups
from clean_data import ValidationError, file_hash
from evaluate_representation import (MUNICIPAL_KEYS, assign_bands, computational_cost,
                                     group_ages, profile_diagnostics, sensitivity_rows, run_evaluation)


def make_frame():
    frame = pd.DataFrame(dict(election_year=[2024]*6, EDOCVE=['01']*6,
        MPIOCVE=['001', '001', '001', '001', '002', '002'],
        age_value=[18, 29, 101, 30, 18, 140], SEXO=['0', '0', '0', '2', '1', '1'],
        LN=[10, 90, 1, 105, 20, 1], SV=[10, 0, 1, 79, 0, 0],
        NV=[0, 90, 0, 23, 0, 1], NS=[0, 0, 0, 3, 20, 0],
        source_row_count=[5, 5, 1, 105, 5, 1], sex_2_source_rows=[0, 0, 0, 105, 0, 0],
        sex_2_nominal_count=[0, 0, 0, 105, 0, 0]))
    return add_indicators(frame, DEFAULT_THRESHOLDS)


class RepresentationChecks(unittest.TestCase):
    def test_band_boundaries_preserve_extremes_without_truncation(self):
        self.assertEqual(assign_bands([18, 29, 30, 44, 45, 59, 60, 74, 75, 100, 101, 140], 'life_stage').tolist(),
                         ['18-29', '18-29', '30-44', '30-44', '45-59', '45-59', '60-74', '60-74', '75-100', '75-100', '101+', '101+'])
        self.assertEqual(assign_bands([75, 100, 101, 140], 'life_stage_open').tolist(), ['75+']*4)
        with self.assertRaises(ValidationError): assign_bands([17], 'broad')
        with self.assertRaises(ValidationError): assign_bands([18.5], 'broad')

    def test_counts_rates_and_weighted_loss_conserve_source(self):
        frame = make_frame()
        original = frame.copy(deep=True)
        grouped = group_ages(frame, 'life_stage', DEFAULT_THRESHOLDS)
        first = grouped[grouped.MPIOCVE.eq('001') & grouped.age_band.eq('18-29')].iloc[0]
        self.assertAlmostEqual(first.participation_observed, .1)
        self.assertAlmostEqual(first.within_band_rate_variance, .09)
        undefined = grouped[grouped.MPIOCVE.eq('002') & grouped.age_band.eq('18-29')].iloc[0]
        self.assertTrue(pd.isna(undefined.participation_observed))
        self.assertEqual(undefined.NS, 20)
        for metric in METRICS:
            self.assertEqual(grouped[metric].sum(), frame[metric].sum())
        self.assertEqual(set(grouped.EDOCVE), {'01'})
        self.assertEqual(set(grouped.MPIOCVE), {'001', '002'})
        self.assertEqual(grouped[grouped.SEXO.eq('2')].LN.sum(), 105)
        pd.testing.assert_frame_equal(frame, original)

    def test_profile_absent_and_undefined_are_separate_and_not_imputed(self):
        frame = make_frame()
        municipalities = add_indicators(sum_groups(frame, MUNICIPAL_KEYS), DEFAULT_THRESHOLDS)
        municipalities['municipality_name_label'] = 'Municipio'
        municipalities['state_name_label'] = 'Entidad'
        municipalities['district_reference_year'] = 2023
        grouped = group_ages(frame, 'life_stage', DEFAULT_THRESHOLDS)
        result = profile_diagnostics(grouped, municipalities, 'life_stage').set_index('MPIOCVE')
        self.assertEqual(len(result), 2)
        self.assertEqual(result.loc['001', 'core_expected_cells'], 10)
        self.assertEqual(result.loc['001', 'core_present_cells'], 1)
        self.assertEqual(result.loc['001', 'core_absent_cells'], 9)
        self.assertEqual(result.loc['001', 'core_undefined_present_cells'], 0)
        self.assertEqual(result.loc['002', 'core_present_cells'], 1)
        self.assertEqual(result.loc['002', 'core_absent_cells'], 9)
        self.assertEqual(result.loc['002', 'core_undefined_present_cells'], 1)
        self.assertEqual(result.loc['001', 'core_LN'], 100)
        self.assertEqual(result.loc['001', 'LN'], 206)
        self.assertEqual(result.sex_2_source_rows.sum(), 105)
        self.assertFalse(result.core_complete_defined.any())

    def test_costs_are_algebraic_and_thresholds_do_not_exclude(self):
        cost = computational_cost(10, 6)
        self.assertEqual(cost['pairs'], 45)
        self.assertEqual(cost['condensed_distance_bytes'], 360)
        self.assertEqual(cost['dense_feature_MiB'], 480/2**20)
        frame = make_frame()
        original = frame.copy(deep=True)
        rows = sensitivity_rows(frame, 'A', 'exact', 2024, DEFAULT_THRESHOLDS)
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row['observations'] == len(frame) for row in rows))
        high_ns = next(row for row in rows if row['criterion'] == 'unspecified_rate' and row['threshold'] == .1)
        self.assertEqual(high_ns['affected_groups'], 1)
        pd.testing.assert_frame_equal(frame, original)

    def test_full_pipeline_is_independent_of_batch_size_and_preserves_inputs(self):
        frame = make_frame()
        frame['election_year'] = frame.election_year.astype('int16')
        municipal = add_indicators(sum_groups(frame, MUNICIPAL_KEYS), DEFAULT_THRESHOLDS)
        municipal['municipality_name_label'] = 'Municipio'
        municipal['state_name_label'] = 'Entidad'
        municipal['district_reference_year'] = 2023
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root/'data/processed/descriptive'
            (source/'metadata').mkdir(parents=True)
            files = []
            for name, table in [('municipality_age_sex', frame), ('municipality', municipal),
                                ('state', sum_groups(frame, ['election_year', 'EDOCVE'])),
                                ('year', sum_groups(frame, ['election_year']))]:
                path = source/name/'table.parquet'
                path.parent.mkdir()
                table.to_parquet(path, index=False)
                files.append(dict(path=path.relative_to(source).as_posix(), sha256=file_hash(path)))
            manifest = dict(status='validated', files=files, table_rows={'municipality_age_sex': len(frame)})
            (source/'metadata/run_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            (source/'metadata/table_contract.json').write_text(json.dumps({'thresholds': DEFAULT_THRESHOLDS}), encoding='utf-8')
            (source/'_SUCCESS').write_text(json.dumps({'manifest_sha256': file_hash(source/'metadata/run_manifest.json')}), encoding='utf-8')
            for relative in ['analysis/cleaning_plan.md', 'analysis/reports/technical_cleaning.md',
                             'analysis/reports/descriptive_analysis.md', 'analysis/reports/outlier_review.md']:
                path = root/relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('Documento de entrada sintético.', encoding='utf-8')
            with patch('evaluate_representation.YEARS', [2024]), patch('evaluate_representation.EXPECTED_ROWS', int(frame.source_row_count.sum())):
                first = run_evaluation(root, root/'analysis/reports/evidence_one', root/'analysis/reports/report_one.md', 1)
                second = run_evaluation(root, root/'analysis/reports/evidence_many', root/'analysis/reports/report_many.md', 100)
            self.assertEqual(first['status'], 'validated')
            self.assertEqual(second['status'], 'validated')
            self.assertEqual(first['scanned_aggregate_groups'], len(frame))
            for name in ['representation_summary.csv', 'band_support.csv', 'profile_summary.csv', 'state_reconciliation.csv']:
                pd.testing.assert_frame_equal(pd.read_csv(root/'analysis/reports/evidence_one'/name),
                                              pd.read_csv(root/'analysis/reports/evidence_many'/name))
            for path, digest in first['protected_hashes'].items():
                self.assertEqual(file_hash(path), digest)


if __name__ == '__main__':
    unittest.main()
