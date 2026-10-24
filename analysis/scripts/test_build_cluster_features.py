"""Pruebas de matrices sin exclusión, pesos descriptivos y nulos explícitos."""

from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from build_descriptive import DEFAULT_THRESHOLDS, METRICS, add_indicators, sum_groups
from evaluate_representation import MUNICIPAL_KEYS, group_ages
from build_cluster_features import (age_moments, build_segments, build_profiles, correlation_statistics,
    diagnostic_tables, feature_status, profile_feature_names, save_table, weighted_summary)


def fixtures():
    frame = pd.DataFrame(dict(election_year=np.array([2024]*6, dtype='int16'), EDOCVE=['01']*6,
        MPIOCVE=['001', '001', '001', '001', '001', '002'], age_value=[18, 29, 35, 30, 140, 18],
        SEXO=['0', '0', '1', '2', '1', '0'], LN=[10, 90, 10, 105, 1, 10],
        SV=[10, 0, 0, 79, 0, 0], NV=[0, 90, 0, 23, 1, 0], NS=[0, 0, 10, 3, 0, 10],
        source_row_count=[5, 5, 5, 105, 1, 5], sex_2_source_rows=[0, 0, 0, 105, 0, 0],
        sex_2_nominal_count=[0, 0, 0, 105, 0, 0]))
    frame = add_indicators(frame, DEFAULT_THRESHOLDS)
    municipalities = add_indicators(sum_groups(frame, MUNICIPAL_KEYS), DEFAULT_THRESHOLDS)
    municipalities['municipality_name_label'] = 'Municipio'
    municipalities['state_name_label'] = 'Entidad'
    municipalities['district_reference_year'] = 2023
    return frame, municipalities


class ClusterFeatureChecks(unittest.TestCase):
    def test_segments_preserve_counts_and_use_real_weighted_ages(self):
        reference, municipalities = fixtures()
        original = reference.copy(deep=True)
        grouped = group_ages(reference, 'life_stage', DEFAULT_THRESHOLDS)
        features, metadata = build_segments(grouped, reference, municipalities, 'life_stage')
        row = metadata[metadata.MPIOCVE.eq('001') & metadata.SEXO.eq('0')].iloc[0]
        self.assertAlmostEqual(row.mean_age_nominal, 27.9)
        self.assertAlmostEqual(row.participation_observed, .1)
        self.assertEqual(set(features.columns), {'row_id', 'participation_observed', 'mean_age_nominal'})
        self.assertEqual(metadata.loc[metadata.age_band.eq('101+'), 'over_100_nominal_count'].sum(), 1)
        self.assertEqual(metadata.loc[metadata.SEXO.eq('2'), 'LN'].sum(), 105)
        self.assertTrue(metadata.groupby(MUNICIPAL_KEYS).equal_municipality_weight.sum().eq(1).all())
        for metric in METRICS: self.assertEqual(metadata[metric].sum(), reference[metric].sum())
        self.assertEqual(set(metadata.EDOCVE), {'01'})
        self.assertEqual(set(metadata.MPIOCVE), {'001', '002'})
        self.assertTrue(features.row_id.equals(metadata.row_id))
        pd.testing.assert_frame_equal(reference, original)

    def test_profiles_keep_all_municipalities_and_distinguish_absent_and_undefined(self):
        reference, municipalities = fixtures()
        grouped = group_ages(reference, 'broad', DEFAULT_THRESHOLDS)
        features, metadata, cells = build_profiles(grouped, municipalities, 'broad')
        self.assertEqual(len(features), 2)
        self.assertEqual(len(features.columns)-1, 6)
        self.assertEqual(list(features.columns[1:]), profile_feature_names('broad'))
        first = metadata[metadata.MPIOCVE.eq('001')].iloc[0]
        feature = features[features.row_id.eq(first.row_id)].iloc[0]
        self.assertAlmostEqual(feature.participation_18_34_men, .1)
        self.assertTrue(pd.isna(feature.participation_18_34_women))
        absent = cells[cells.MPIOCVE.eq('001') & cells.age_band.eq('18-34') & cells.SEXO.eq('1')].iloc[0]
        undefined = cells[cells.MPIOCVE.eq('001') & cells.age_band.eq('35-59') & cells.SEXO.eq('1')].iloc[0]
        self.assertEqual(absent.value_status, 'absent_combination')
        self.assertTrue(pd.isna(absent.LN))
        self.assertEqual(undefined.value_status, 'undefined_rate')
        self.assertEqual(undefined.LN, 10)
        self.assertEqual(undefined.specified_count, 0)
        self.assertTrue(pd.isna(undefined.participation_observed))
        self.assertEqual(first.complement_LN, 106)
        self.assertEqual(metadata.sex_2_source_rows.sum(), 105)
        self.assertFalse(metadata.can_use_complete_algorithms.any())
        for metric in METRICS: self.assertEqual(metadata[metric].sum(), reference[metric].sum())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'cells.parquet'
            save_table(path, cells)
            stored = pd.read_parquet(path)
            self.assertEqual(str(stored.LN.dtype), 'Int64')
            self.assertEqual(stored.LN.isna().sum(), (~cells.is_present).sum())

    def test_weighted_summaries_and_correlations_use_defined_pairs(self):
        result = weighted_summary([0., 1., np.nan], [1, 9, 10])
        self.assertAlmostEqual(result['mean'], .9)
        self.assertAlmostEqual(result['std'], .3)
        self.assertEqual(result['valid_observations'], 2)
        self.assertEqual(result['valid_weight'], 10)
        self.assertEqual(result['total_weight'], 20)
        self.assertEqual(result['median'], 1)
        self.assertTrue(np.isnan(weighted_summary([np.nan], [1])['mean']))
        result = correlation_statistics([0, 1, 2, np.nan], [4, 2, 0, 8], [1, 2, 3, 4])
        self.assertAlmostEqual(result['pearson'], -1)
        self.assertEqual(result['pair_observations'], 3)
        self.assertEqual(result['pair_weight'], 6)
        self.assertTrue(np.isnan(correlation_statistics([.1, .1], [2, 3], [1, 9])['pearson']))

    def test_nonfinite_status_and_quality_do_not_filter_features(self):
        features = pd.DataFrame(dict(row_id=['a', 'b', 'c'], rate=[0., np.nan, 1.], age=[18., 25., np.inf]))
        status = feature_status(features)
        self.assertEqual(status.can_use_complete_algorithms.tolist(), [True, False, False])
        self.assertEqual(status.null_feature_count.tolist(), [0, 1, 0])
        self.assertEqual(status.nonfinite_feature_count.tolist(), [0, 0, 1])
        reference, municipalities = fixtures()
        grouped = group_ages(reference, 'broad', DEFAULT_THRESHOLDS)
        features, metadata = build_segments(grouped, reference, municipalities, 'broad')
        original = features.copy(deep=True)
        summary, distributions, correlations, weights = diagnostic_tables('b_broad', features, metadata, 'B')
        self.assertEqual(summary['observations'], len(grouped))
        self.assertEqual(summary['numeric_features'], 2)
        self.assertEqual(summary['incomplete_observations'], 2)
        self.assertEqual(len(weights), 3)
        self.assertTrue(all(row['total_weight'] > 0 for row in weights))
        pd.testing.assert_frame_equal(features, original)


if __name__ == '__main__':
    unittest.main()
