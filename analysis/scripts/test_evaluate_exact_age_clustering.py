"""Pruebas de referencia exacta, soporte, métricas por bloques y piloto pequeño."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from clustering_core import fit_scaler
from run_demographic_pilot import anchor_distances, sampled_metrics
from test_evaluate_cluster_separation import dense_individual
from evaluate_exact_age_clustering import (prepare_segments, support_review, support_mask,
    paired_matrices, anchor_silhouettes, db_index, exact_age_diagnostics, fit_models, save_features, municipality_exclusions)


def make_reference(records):
    rows = []
    for item in records:
        record = dict(election_year=2024, EDOCVE='1', MPIOCVE='1', age_value=18, SEXO='0',
            LN=200, SV=100, NV=95, NS=5, source_row_count=10, sex_2_source_rows=0,
            sex_2_nominal_count=0, state_name_label='State', municipality_name_label='Municipality', district_reference_year=2023)
        record.update(item)
        if record['SEXO'] == '2': record.update(sex_2_source_rows=record['source_row_count'], sex_2_nominal_count=record['LN'])
        denominator = record['SV']+record['NV']
        record['participation_observed'] = record['SV']/denominator if denominator else np.nan
        rows.append(record)
    return pd.DataFrame(rows)


def example_reference():
    records = []
    for municipality in range(1, 13):
        for age in [18, 25, 40, 60, 80]:
            for sex in ['0', '1']:
                ln = 200+municipality*17+age; ns = 3*(municipality % 4)
                sv = int((ln-ns)*(.3+.003*age+.04*int(sex)+.012*municipality))
                records.append(dict(MPIOCVE=str(municipality), age_value=age, SEXO=sex, LN=ln, SV=sv, NV=ln-ns-sv, NS=ns))
    records += [dict(age_value=100, LN=80, SV=40, NV=39, NS=1, source_row_count=3),
        dict(age_value=101, LN=300, SV=200, NV=98, NS=2),
        dict(MPIOCVE='2', age_value=30, LN=150, SV=0, NV=0, NS=150),
        dict(MPIOCVE='2', age_value=25, SEXO='2', LN=1, SV=1, NV=0, NS=0, source_row_count=1)]
    return make_reference(records)


class ExactAgeChecks(unittest.TestCase):
    def test_exact_reference_sums_counts_and_does_not_average_municipal_rates(self):
        reference = make_reference([dict(LN=100, SV=90, NV=10, NS=0),
            dict(MPIOCVE='2', LN=900, SV=90, NV=810, NS=0), dict(SEXO='1')])
        frame, national = prepare_segments(reference)
        group = national[national.SEXO.eq('0')].iloc[0]
        self.assertAlmostEqual(group.national_participation_exact, .18)
        self.assertNotAlmostEqual(group.national_participation_exact, reference.iloc[:2].participation_observed.mean())
        self.assertEqual(frame.LN.sum(), 1200)
        np.testing.assert_allclose(frame.loc[frame.SEXO.eq('0'), 'participation_deviation_exact'], [.72, -.08])

    def test_undefined_rates_and_complementary_categories_remain_null_pending(self):
        frame, _ = prepare_segments(example_reference())
        undefined = frame[frame.age_value.eq(30)].iloc[0]
        self.assertTrue(np.isnan(undefined.participation_observed)); self.assertTrue(np.isnan(undefined.participation_deviation_exact))
        self.assertEqual(undefined.pending_reason, 'undefined_features')
        self.assertEqual(frame[frame.age_value.eq(101)].iloc[0].pending_reason, 'age_over_100_complementary')
        self.assertFalse(frame[frame.SEXO.eq('2')].is_eligible.any())
        self.assertEqual(frame[frame.SEXO.eq('2')].LN.sum(), 1)

    def test_duplicate_keys_are_rejected_instead_of_double_counted(self):
        reference = example_reference()
        with self.assertRaises(RuntimeError): prepare_segments(pd.concat([reference, reference.iloc[[0]]], ignore_index=True))

    def test_support_scenarios_are_nested_without_changing_source_and_zeros_mean_selection(self):
        reference = example_reference(); before = reference.copy(deep=True)
        frame, _ = prepare_segments(reference)
        for low, high in [(25, 50), (50, 100), (100, 200), (200, 500)]:
            self.assertTrue((~support_mask(frame, high) | support_mask(frame, low)).all())
        thresholds, ages, municipalities, quality = support_review(frame)
        self.assertEqual(ages[ages.age_value.eq(100)].eligible_segments.sum(), 0)
        self.assertEqual(quality[quality.scope.eq('age_18_100')].null_rates.iloc[0], 1)
        pd.testing.assert_frame_equal(reference, before)

    def test_paired_standardization_uses_exact_age_and_same_deviation_scale(self):
        frame, _ = prepare_segments(example_reference()); raw = frame[frame.is_eligible]
        scaler = fit_scaler(raw[['age_value', 'participation_deviation_exact']].to_numpy(dtype=float), 'standard')
        matrices = paired_matrices(raw, scaler)
        np.testing.assert_allclose(matrices['e1'].mean(axis=0), [0., 0.], atol=1e-13)
        np.testing.assert_allclose(matrices['e1'].std(axis=0), [1., 1.], atol=1e-13)
        np.testing.assert_array_equal(matrices['e1'][:, 1], matrices['e2'][:, 1])
        self.assertTrue((matrices['e2'][:, 0] == 0).all())

    def test_streamed_silhouette_matches_literal_reference_for_all_and_subset_anchors(self):
        values = np.random.default_rng(14).normal(size=(17, 2)); first = np.repeat([0, 1, 2, 3], [5, 5, 6, 1]); second = np.arange(17) % 3
        with patch('evaluate_exact_age_clustering.np.zeros', wraps=np.zeros) as zeros:
            scores = anchor_silhouettes(values, {'first': first, 'second': second}, np.arange(17), 4)
            self.assertTrue(all(call.args[0] != (17, 17) for call in zeros.call_args_list if isinstance(call.args[0], tuple)))
        for name, labels in [('first', first), ('second', second)]:
            np.testing.assert_allclose(scores[name], dense_individual(values, labels), atol=1e-13)
        subset = np.array([1, 5, 10, 16]); values2 = anchor_silhouettes(values, {'first': first}, subset, 2)['first']
        np.testing.assert_allclose(values2, scores['first'][subset], atol=1e-13)
        self.assertEqual(scores['first'][-1], 0.)

    def test_db_and_conditional_rate_diagnostics_match_existing_definitions(self):
        frame, _ = prepare_segments(example_reference()); raw = frame[frame.is_eligible].reset_index(drop=True)
        scaler = fit_scaler(raw[['age_value', 'participation_deviation_exact']].to_numpy(dtype=float), 'standard')
        values = paired_matrices(raw, scaler)['e1']; labels = pd.factorize(raw.age_value)[0]
        anchors = np.arange(len(values)); metrics = sampled_metrics(values, labels, anchors, anchor_distances(values, anchors))
        self.assertAlmostEqual(db_index(values, labels), metrics['davies_bouldin'], places=13)
        diagnostics = exact_age_diagnostics(raw, values, labels)
        self.assertAlmostEqual(diagnostics['age_r2'], 1.)
        self.assertAlmostEqual(diagnostics['within_age_sex_rate_r2'], 0., places=12)

    def test_small_fit_preserves_original_rows_pending_and_additive_counts(self):
        frame, _ = prepare_segments(example_reference()); raw = frame[frame.is_eligible]
        scaler = fit_scaler(raw[['age_value', 'participation_deviation_exact']].to_numpy(dtype=float), 'standard')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory); (output/'metadata').mkdir()
            matrices, models, best, metrics = fit_models(frame, scaler, output, anchor_count=24)
            self.assertEqual(len(models), 30); self.assertEqual(len(metrics), 10)
            profiles = pd.read_csv(output/'metadata/cluster_profiles.csv')
            for representation in ['e1', 'e2']:
                labels = pd.read_parquet(output/'models'/representation/'labels.parquet')
                self.assertTrue(labels.row_id.equals(frame.row_id))
                self.assertTrue(labels.loc[~frame.is_eligible].filter(regex='^k').isna().all().all())
                for k in [2, 3, 4, 5, 6]:
                    group = profiles[profiles.representation.eq(representation) & profiles.k.eq(k)]
                    self.assertEqual(group.observations.sum(), len(raw)); self.assertEqual(group.LN.sum(), raw.LN.sum())

    def test_fresh_destination_writes_scalers_and_excludes_pending_from_fit(self):
        frame, _ = prepare_segments(example_reference())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'fresh_output'
            scaler, training_hash = save_features(frame, output)
            expected = frame.loc[frame.is_eligible, ['age_value', 'participation_deviation_exact']].mean().to_numpy()
            np.testing.assert_allclose(scaler['location'], expected)
            e1 = pd.read_parquet(output/'features/e1_standardized.parquet')
            e2 = pd.read_parquet(output/'features/e2_standardized.parquet')
            self.assertTrue(e1.row_id.equals(frame.row_id)); self.assertTrue(e2.row_id.equals(frame.row_id))
            np.testing.assert_allclose(e1.participation_deviation_exact, e2.participation_deviation_exact, equal_nan=True)
            self.assertEqual(json.loads((output/'features/e2_scaler.json').read_text())['training_row_ids_sha256'], training_hash)

    def test_municipal_exclusion_distinguishes_large_counts_few_sources_and_no_specification(self):
        reference = make_reference([dict(MPIOCVE='1', source_row_count=4),
            dict(MPIOCVE='2', LN=50, SV=20, NV=25, NS=5),
            dict(MPIOCVE='3', LN=200, SV=0, NV=0, NS=200), dict(MPIOCVE='4')])
        frame, _ = prepare_segments(reference)
        _, _, municipalities, _ = support_review(frame)
        reasons = municipality_exclusions(frame, municipalities).set_index('MPIOCVE')
        self.assertEqual(reasons.loc['1', 'exclusion_reason'], 'source_rows_only')
        self.assertEqual(reasons.loc['2', 'exclusion_reason'], 'counts_below_threshold')
        self.assertEqual(reasons.loc['3', 'exclusion_reason'], 'all_unspecified')
        self.assertEqual(reasons.loc['4', 'exclusion_reason'], 'has_eligible_segments')
        self.assertEqual(reasons.LN.sum(), frame.LN.sum())


if __name__ == '__main__':
    unittest.main()
