"""Contrastes independientes, casos degenerados y reproducibilidad del piloto."""

from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from clustering_core import (adjusted_rand, centroid_matching, cut_linkage, dbscan, fit_scaler,
    geometric_elbow, inverse_transform, kmeans, pairwise_distances, pattern_decomposition,
    transform, validation_metrics, ward_linkage)


def brute_ward(values):
    """Referencia exhaustiva independiente para contrastar la cadena de vecinos."""
    n = len(values)
    groups = {index: [index] for index in range(n)}
    rows = []
    while len(groups) > 1:
        candidates = []
        identifiers = sorted(groups)
        for i, left in enumerate(identifiers):
            for right in identifiers[i+1:]:
                a, b = values[groups[left]], values[groups[right]]
                delta = len(a)*len(b)/(len(a)+len(b))*np.sum((a.mean(axis=0)-b.mean(axis=0))**2)
                candidates.append((delta, left, right))
        delta, left, right = min(candidates)
        members = groups.pop(left)+groups.pop(right)
        rows.append([left, right, np.sqrt(2*delta), len(members)])
        groups[n+len(rows)-1] = members
    return np.array(rows)


class PilotChecks(unittest.TestCase):
    def test_scalers_are_fit_only_on_supplied_rows_and_are_invertible(self):
        values = np.array([[0., 4.], [1., 4.], [2., 4.], [3., 4.]])
        for method in ['original', 'standard', 'robust']:
            scaler = fit_scaler(values, method)
            transformed = transform(values, scaler)
            np.testing.assert_allclose(inverse_transform(transformed, scaler), values)
            if method == 'standard':
                np.testing.assert_allclose(transformed[:, 0].std(ddof=0), 1.)
            if method == 'robust': self.assertAlmostEqual(scaler['scale'][0], 1.5)
        scaler = fit_scaler(values, 'standard')
        self.assertEqual(scaler['location'], [1.5, 4.])
        self.assertEqual(scaler['scale'][1], 1.)
        self.assertGreater(transform([[100., 4.]], scaler)[0, 0], 50)

    def test_ward_matches_exhaustive_global_variance_merges(self):
        for seed in range(6):
            values = np.random.default_rng(seed).normal(size=(18, 4))
            first = ward_linkage(pairwise_distances(values))
            second = brute_ward(values)
            np.testing.assert_allclose(first[:, 2:], second[:, 2:], rtol=1e-10, atol=1e-10)
            for clusters in range(2, 11):
                self.assertEqual(adjusted_rand(cut_linkage(first, clusters), cut_linkage(second, clusters)), 1.)
        duplicates = np.array([[0., 0.], [0., 0.], [1., 1.], [1., 1.]])
        linkage = ward_linkage(pairwise_distances(duplicates))
        self.assertEqual(linkage[-1, 3], 4)
        self.assertEqual(adjusted_rand(cut_linkage(linkage, 2), [0, 0, 1, 1]), 1.)

    def test_kmeans_plus_plus_multiple_initializations_and_seed_reproducibility(self):
        values = np.array([[0.], [1.], [10.], [11.]])
        first, second = kmeans(values, 2, 42, n_init=10), kmeans(values, 2, 42, n_init=10)
        self.assertAlmostEqual(first['inertia'], 1.)
        np.testing.assert_array_equal(first['labels'], second['labels'])
        self.assertTrue(first['converged'])
        self.assertEqual(first['inertia'], min(row['inertia'] for row in first['initializations']))
        self.assertEqual(adjusted_rand(first['labels'], [0, 0, 1, 1]), 1.)
        np.testing.assert_allclose(np.sort(first['centers'][:, 0]), [.5, 10.5])

    def test_dbscan_core_border_noise_and_min_samples_includes_self(self):
        values = np.array([[0.], [.1], [.2], [10.], [10.1], [10.2], [30.]])
        distances = pairwise_distances(values)
        labels, core = dbscan(distances, .11, 3)
        np.testing.assert_array_equal(labels, [0, 0, 0, 1, 1, 1, -1])
        np.testing.assert_array_equal(core, [False, True, False, False, True, False, False])
        singleton, _ = dbscan(distances, .01, 1)
        self.assertEqual(len(np.unique(singleton)), 7)
        noise, _ = dbscan(distances, .01, 2)
        self.assertTrue((noise == -1).all())

    def test_silhouette_and_davies_bouldin_match_hand_calculation(self):
        values = np.array([[0.], [1.], [10.], [11.]])
        result = validation_metrics(values, [0, 0, 1, 1], pairwise_distances(values))
        expected = np.mean([(10.5-1)/10.5, (9.5-1)/9.5, (9.5-1)/9.5, (10.5-1)/10.5])
        self.assertAlmostEqual(result['silhouette'], expected)
        self.assertAlmostEqual(result['davies_bouldin'], .1)
        undefined = validation_metrics(values, [0, 0, 0, 0], pairwise_distances(values))
        self.assertTrue(np.isnan(undefined['silhouette']))
        self.assertTrue(np.isnan(undefined['davies_bouldin']))
        singleton = validation_metrics(values, [0, 0, 1, 2], pairwise_distances(values))
        self.assertTrue(np.isfinite(singleton['silhouette']))

    def test_ari_centroid_alignment_and_pattern_decomposition(self):
        self.assertEqual(adjusted_rand([0, 0, 1, 1], [8, 8, 3, 3]), 1.)
        self.assertAlmostEqual(adjusted_rand([0, 0, 1, 1], [0, 1, 0, 1]), -.5)
        order = centroid_matching(np.array([[0., 0.], [2., 2.]]), np.array([[2., 2.], [0., 0.]]))
        np.testing.assert_array_equal(order, [1, 0])
        level = pattern_decomposition(np.array([[.1, .1], [.2, .2], [.8, .8], [.9, .9]]), np.array([0, 0, 1, 1]))
        self.assertAlmostEqual(level['between_level_share'], 1.)
        shape = pattern_decomposition(np.array([[.1, .9], [.2, .8], [.8, .2], [.9, .1]]), np.array([0, 0, 1, 1]))
        self.assertAlmostEqual(shape['between_shape_share'], 1.)

    def test_paper_equation_4_checks_flattening_and_axis_sensitivity(self):
        ks, sse = [2, 3, 4, 5, 6], [100., 40., 20., 12., 8.]
        selected, rows, status = geometric_elbow(ks, sse)
        self.assertEqual(status, 'defined')
        self.assertEqual(selected, min(rows, key=lambda row: row['tan_psi'])['k'])
        self.assertAlmostEqual(rows[0]['tan_psi'], (-60+20)/(1+1200))
        self.assertEqual(geometric_elbow(ks, [100., 80., 90., 40., 30.])[2], 'nonmonotonic_sse')
        self.assertIsNone(geometric_elbow(ks, [10., 8., 6., 4., 2.])[0])
        unit_a = geometric_elbow(ks, sse, 'unit_axes')[0]
        unit_b = geometric_elbow(ks, np.array(sse)*100, 'unit_axes')[0]
        self.assertEqual(unit_a, unit_b)

    def test_context_pipeline_retains_pending_rows_and_reproduces_labels(self):
        from run_clustering_pilot import run_context
        rng = np.random.default_rng(90)
        values = np.r_[rng.normal(.25, .02, (40, 6)), rng.normal(.75, .02, (40, 6))]
        names = [f'rate_{index}' for index in range(6)]
        features = pd.DataFrame(values, columns=names)
        features.insert(0, 'row_id', [f'municipality_{index}' for index in range(80)])
        features.loc[0, 'rate_0'] = np.nan
        metadata = pd.DataFrame(dict(row_id=features.row_id, LN=[1000]*80, NS=[0]*80,
            can_use_complete_algorithms=[False]+[True]*79,
            has_low_support_features=[False, True]+[False]*78, has_high_ns_features=[False]*80))
        mask = np.array([False, False]+[True]*78)
        original = features.copy(deep=True)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = run_context('one', 'c_synthetic', 'synthetic', 'standard', features, metadata, names,
                mask, root, root, seeds=[17, 42], ks=[2, 3, 4], n_init=2)
            second = run_context('two', 'c_synthetic', 'synthetic', 'standard', features, metadata, names,
                mask, root, root, seeds=[17, 42], ks=[2, 3, 4], n_init=2)
            self.assertEqual(len(first['metrics']), 17)
            for model_id in first['labels']:
                np.testing.assert_array_equal(first['labels'][model_id], second['labels'][model_id])
                self.assertTrue(np.isnan(first['labels'][model_id][:2]).all())
            stored = pd.read_parquet(root/'contexts/one/labels.parquet')
            self.assertTrue(stored.drop(columns='row_id').iloc[:2].isna().all().all())
            self.assertEqual(len(pd.read_parquet(root/'contexts/one/pending_assignment.parquet')), 2)
            self.assertEqual(first['coverage']['training_municipalities'], 78)
            self.assertTrue(pd.read_parquet(root/'contexts/one/raw_features.parquet').rate_0.isna().iloc[0])
            np.testing.assert_allclose(first['scaler']['location'], features.loc[mask, names].mean().to_numpy(), rtol=1e-14)
        pd.testing.assert_frame_equal(features, original)


if __name__ == '__main__':
    unittest.main()
