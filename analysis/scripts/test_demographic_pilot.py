"""Pruebas de selección, referencias y validación numérica del piloto B."""
import tempfile
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from clustering_core import fit_scaler, pairwise_distances, validation_metrics
from run_demographic_pilot import (FEATURES, add_reference, anchor_distances, anchor_sample,
    pattern_diagnostics, run_context, sampled_metrics, selection)


def example_metadata():
    rows = []
    for index in range(24):
        age_band = '18-34' if index < 12 else '35-59'
        sv = 20+index*6
        rows.append(dict(row_id=f'segment_{index:02d}', election_year=2024,
            EDOCVE='01', MPIOCVE=f'{index//4:03d}', age_band=age_band, SEXO=str(index % 2),
            LN=200, SV=sv, NV=190-sv, NS=10, specified_count=190, source_row_count=10,
            sex_2_source_rows=0, sex_2_nominal_count=0, participation_observed=sv/190,
            mean_age_nominal=(24 if index < 12 else 47)+index/10,
            age_min_observed=18 if index < 12 else 35, age_max_observed=34 if index < 12 else 59,
            has_high_unspecified_rate=False))
    return pd.DataFrame(rows)


class DemographicPilotTests(unittest.TestCase):
    def test_national_reference_uses_sums_before_selection(self):
        source = example_metadata().iloc[:3].copy()
        source.loc[2, ['LN', 'SV', 'NV', 'NS', 'specified_count', 'source_row_count']] = [10, 9, 0, 1, 9, 1]
        source.loc[2, 'participation_observed'] = 1.
        enriched, reference = add_reference(source)
        expected = (source.SV.iloc[0]+9)/(190+9)
        self.assertAlmostEqual(reference.query("SEXO == '0'").national_participation.iloc[0], expected)
        self.assertFalse(selection(enriched)[0][2])
        self.assertAlmostEqual(enriched.national_participation.iloc[0], expected)

    def test_selection_preserves_tail_sex_and_null(self):
        source = example_metadata()
        source.loc[0, ['age_band', 'age_min_observed', 'age_max_observed', 'mean_age_nominal']] = ['101+', 101, 110, 105]
        source.loc[1, ['SEXO', 'LN', 'specified_count', 'source_row_count']] = ['2', 1, 1, 1]
        source.loc[2, 'participation_observed'] = np.nan
        mask, full = selection(source)
        self.assertEqual(len(full), len(source))
        self.assertFalse(mask[:3].any())
        self.assertEqual(full.pending_reason.iloc[:3].tolist(), ['age_101_plus_complementary', 'low_support', 'undefined_features'])
        self.assertTrue(selection(source, include_tail=True)[0][0])
        men_mask, _ = selection(source, scope='men')
        self.assertFalse((men_mask & source.SEXO.ne('0').to_numpy()).any())

    def test_anchor_metrics_match_exact_with_all_anchors(self):
        values = np.array([[0., 0.], [0., 1.], [1., 0.], [6., 5.], [5., 6.], [9., 9.]])
        labels = np.array([0, 0, 0, 1, 1, 2])  # El singleton tiene Silhouette cero.
        anchors = np.arange(len(values))
        distance = anchor_distances(values, anchors, 2)
        result = sampled_metrics(values, labels, anchors, distance)
        expected = validation_metrics(values, labels, pairwise_distances(values))
        self.assertAlmostEqual(result['silhouette'], expected['silhouette'], places=13)
        self.assertAlmostEqual(result['davies_bouldin'], expected['davies_bouldin'], places=13)
        self.assertEqual(result['silhouette_mc_se'], 0)
        self.assertTrue(np.array_equal(distance, anchor_distances(values, anchors, 3)))

    def test_sampling_reproducible_and_distances_use_full_reference(self):
        values = np.arange(200).reshape(100, 2)/100
        anchors = anchor_sample(np.arange(100), 7)
        self.assertEqual(len(np.unique(anchors)), 7)
        self.assertTrue(np.array_equal(anchors, anchor_sample(np.arange(100), 7)))
        distances = anchor_distances(values, anchors, 2)
        self.assertEqual(distances.shape, (7, 100))
        self.assertTrue(np.allclose(distances, pairwise_distances(values)[anchors]))
        self.assertTrue(np.array_equal(anchor_sample(np.arange(4), 7), np.arange(4)))
        labels = np.repeat([0, 1], 50)
        result = sampled_metrics(values, labels, anchors, distances)
        exact_scores = []
        for index in anchors:
            same = np.flatnonzero(labels == labels[index]); same = same[same != index]
            own = np.linalg.norm(values[same]-values[index], axis=1).mean()
            other = np.linalg.norm(values[labels != labels[index]]-values[index], axis=1).mean()
            exact_scores.append((other-own)/max(own, other))
        expected_se = np.std(exact_scores, ddof=1)/np.sqrt(7)*np.sqrt(1-7/100)
        self.assertAlmostEqual(result['silhouette_mc_se'], expected_se, places=14)

    def test_purity_alone_does_not_measure_within_band_patterns(self):
        source, _ = add_reference(example_metadata())
        raw = source[FEATURES].to_numpy()
        band_labels = (np.arange(len(source)) >= 12).astype(int)
        centers = np.array([raw[band_labels == k].mean(axis=0) for k in range(2)])
        diagnostics = pattern_diagnostics(raw, source, band_labels, centers, raw)
        self.assertEqual(diagnostics['age_band_purity'], 1)
        self.assertAlmostEqual(diagnostics['within_age_sex_rate_r2'], 0, places=10)
        labels = band_labels*2+(np.arange(24) % 12 >= 6)
        centers = np.array([raw[labels == k].mean(axis=0) for k in range(4)])
        diagnostics = pattern_diagnostics(raw, source, labels, centers, raw)
        self.assertGreater(diagnostics['within_age_sex_rate_r2'], .6)

    def test_small_context_preserves_pending_and_shared_scaler(self):
        source = example_metadata()
        source.loc[0, ['SV', 'NV', 'NS', 'specified_count', 'participation_observed']] = [0, 0, 200, 0, np.nan]
        enriched, _ = add_reference(source)
        original = enriched.copy(deep=True)
        mask, _ = selection(enriched)
        scaler = fit_scaler(enriched.loc[mask, FEATURES], 'standard')
        with tempfile.TemporaryDirectory() as directory:
            result = run_context('test', 'broad', 'standard', 'men', False, enriched, scaler, Path(directory),
                anchor_count=7, n_init=2, ks=[2, 3, 4], seeds=[17, 42])
            folder = Path(directory)/'contexts/test'
            labels = pd.read_parquet(folder/'labels.parquet')
            features = pd.read_parquet(folder/'features.parquet')
            self.assertEqual(len(labels), len(source))
            self.assertTrue(labels.loc[~result['mask'], 'k02_seed17'].isna().all())
            expected = (enriched[FEATURES].to_numpy()-scaler['location'])/scaler['scale']
            self.assertTrue(np.allclose(features[FEATURES], expected, equal_nan=True))
            self.assertTrue(result['metrics'].converged.all())
            self.assertEqual(result['coverage']['training_segments'], 11)
        pd.testing.assert_frame_equal(original, enriched)


if __name__ == '__main__':
    unittest.main()
