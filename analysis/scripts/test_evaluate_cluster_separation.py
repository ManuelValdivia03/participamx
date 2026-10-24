"""Contrastes de Silhouette completo, márgenes, fronteras afines y alineación."""
import unittest
from unittest.mock import patch

import numpy as np

from clustering_core import pairwise_distances, validation_metrics
from run_clustering_pilot import label_change_fraction
from run_demographic_pilot import anchor_distances
from evaluate_cluster_separation import (silhouette_blocks, centroid_proximity, decision_edges,
    align_partition, recover_centers, centers_in_common_scale, relative_bands)


def dense_individual(values, labels):
    """Referencia literal para n pequeño, independiente de la suma matricial por bloques."""
    distance = pairwise_distances(values)
    result = []
    for index, label in enumerate(labels):
        own = np.flatnonzero(labels == label)
        own = own[own != index]
        if not len(own): result.append(0.); continue
        a = sum(distance[index, j] for j in own)/len(own)
        other = [distance[index, labels == group].mean() for group in np.unique(labels) if group != label]
        b = min(other)
        result.append((b-a)/max(a, b) if max(a, b) else 0.)
    return np.array(result)


class SeparationChecks(unittest.TestCase):
    def test_blocked_multiple_silhouettes_match_dense_reference(self):
        values = np.random.default_rng(31).normal(size=(17, 2))
        labels = np.repeat([0, 1, 2, 3], [5, 5, 6, 1])
        second = np.arange(17) % 3
        scores = silhouette_blocks(values, {'first': labels, 'second': second}, 4)
        for name, partition in [('first', labels), ('second', second)]:
            np.testing.assert_allclose(scores[name], dense_individual(values, partition), atol=1e-13)
            expected = validation_metrics(values, partition, pairwise_distances(values))['silhouette']
            self.assertAlmostEqual(scores[name].mean(), expected, places=13)
        self.assertEqual(scores['first'][-1], 0.)

    def test_blocks_never_allocate_full_distance_matrix_and_are_invariant(self):
        values = np.random.default_rng(2).normal(size=(19, 2)); labels = np.arange(19) % 4
        with patch('evaluate_cluster_separation.anchor_distances', wraps=anchor_distances) as distances:
            scores = silhouette_blocks(values, {'model': labels}, 5)['model']
            self.assertTrue(all(len(call.args[1]) <= 5 and len(call.args[1]) < len(values) for call in distances.call_args_list))
        np.testing.assert_allclose(scores, silhouette_blocks(values, {'model': labels}, 1)['model'], atol=1e-13)
        np.testing.assert_allclose(scores, silhouette_blocks(values, {'model': 8-labels}, 999)['model'], atol=1e-13)
        np.testing.assert_allclose(silhouette_blocks(np.zeros((4, 2)), {'model': np.array([0, 0, 1, 1])}, 2)['model'], 0)

    def test_negative_silhouette_can_coexist_with_maximum_centroid_margin(self):
        values = np.array([[-10., 0.], [0., 0.], [10., 0.], [0., 2.], [0., 2.1]])
        labels = np.array([0, 0, 0, 1, 1])
        centers = recover_centers(values, labels, 2)
        proximity = centroid_proximity(values, centers)
        np.testing.assert_array_equal(proximity.nearest_cluster, labels)
        self.assertEqual(proximity.normalized_margin.iloc[1], 1.)
        score = silhouette_blocks(values, {'model': labels}, 2)['model']
        self.assertLess(score[1], -.7)

    def test_margin_has_expected_endpoints_and_no_probability_semantics(self):
        centers = np.array([[-1., 0.], [1., 0.]])
        values = np.array([[-1., 0.], [0., 0.], [-.5, 0.]])
        frame = centroid_proximity(values, centers)
        np.testing.assert_allclose(frame.normalized_margin, [1., 0., 2/3])
        self.assertTrue(frame.centroid_tie.iloc[1])
        np.testing.assert_allclose(frame.normalized_margin, centroid_proximity(values*10, centers*10).normalized_margin)
        self.assertTrue(np.isnan(centroid_proximity(np.zeros((1, 2)), np.zeros((2, 2))).normalized_margin.iloc[0]))

    def test_voronoi_edges_are_true_bisectors_and_not_hidden_by_other_centers(self):
        centers = np.array([[-1., 0.], [1., 0.], [0., 3.]])
        bounds = [-4., 4., -3., 5.]
        edges = decision_edges(centers, bounds)
        self.assertEqual(len(edges), 3)
        for row in edges:
            for point in [np.array([row['x1'], row['y1']]), np.array([row['x2'], row['y2']]),
                          np.array([row['x1']+row['x2'], row['y1']+row['y2']])/2]:
                squared = ((centers-point)**2).sum(axis=1)
                self.assertAlmostEqual(squared[row['left_cluster']], squared[row['right_cluster']], places=11)
                self.assertLessEqual(squared[row['left_cluster']], squared.min()+1e-10)
        vertical = [row for row in edges if row['left_cluster'] == 0 and row['right_cluster'] == 1][0]
        self.assertAlmostEqual(vertical['x1'], 0.); self.assertAlmostEqual(vertical['x2'], 0.)

    def test_affine_frontiers_use_sample_metric_on_common_axes(self):
        centers = np.array([[0., 0.], [1., 1.], [-2., 1.]])
        scale, offset = np.array([2., .5]), np.array([.2, -.3])
        edges = decision_edges(centers, [-3., 3., -3., 3.], scale, offset)
        self.assertGreaterEqual(len(edges), 2)
        for row in edges:
            common = np.array([(row['x1']+row['x2'])/2, (row['y1']+row['y2'])/2])
            metric_point = common*scale+offset
            squared = ((centers-metric_point)**2).sum(axis=1)
            self.assertAlmostEqual(squared[row['left_cluster']], squared[row['right_cluster']], places=11)
            self.assertLessEqual(squared[row['left_cluster']], squared.min()+1e-10)

    def test_alignment_matches_exact_overlap_reference_and_handles_permutation(self):
        reference = np.array([0, 0, 0, 1, 1, 1, 2, 2])
        candidate = np.array([2, 2, 1, 0, 0, 0, 1, 1])
        aligned, mapping = align_partition(reference, candidate, 3)
        self.assertAlmostEqual((aligned != reference).mean(), label_change_fraction(reference, candidate))
        self.assertEqual(len(np.unique(mapping)), 3)
        permuted = np.array([2, 0, 1])[reference]
        np.testing.assert_array_equal(align_partition(reference, permuted, 3)[0], reference)

    def test_recovered_centers_transform_to_common_scale_without_refitting(self):
        values = np.array([[0., 2.], [2., 4.], [5., 6.], [7., 8.]])
        labels = np.array([0, 0, 1, 1])
        centers = recover_centers(values, labels, 2)
        np.testing.assert_allclose(centers, [[1., 3.], [6., 7.]])
        sample = dict(location=[10., .2], scale=[2., .1])
        global_scaler = dict(location=[9., .1], scale=[4., .2])
        common, raw = centers_in_common_scale(centers, sample, global_scaler)
        np.testing.assert_allclose(raw, [[12., .5], [22., .9]])
        np.testing.assert_allclose(common, [[.75, 2.], [3.25, 4.]])

    def test_relative_bands_are_descriptive_signed_half_open_intervals(self):
        values = np.array([-.3, -.2, -.1, 0., .1, .2, .3])
        self.assertEqual(relative_bands(values).tolist(), ['below_minus_20pp', 'minus_20_to_minus_10pp',
            'minus_10_to_zero', 'zero_to_10pp', '10_to_20pp', 'at_least_20pp', 'at_least_20pp'])


if __name__ == '__main__':
    unittest.main()
