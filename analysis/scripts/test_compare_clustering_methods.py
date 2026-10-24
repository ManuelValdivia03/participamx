"""Contrastes matemáticos nuevos, sin dependencias de clustering adicionales."""
import unittest

import numpy as np
import pandas as pd

from clustering_core import fit_scaler, transform, kmeans
from compare_demographic_features import fit_bank, predict
from evaluate_cluster_separation import silhouette_blocks
from compare_clustering_methods import scalar_engine, scalar_silhouette, paired_matrices, shared_bank, band_diagnosis


def literal_scalar_silhouette(values, labels):
    result = []
    for i, value in enumerate(values):
        own = [abs(value-other) for j, other in enumerate(values) if labels[j] == labels[i] and j != i]
        if not own:
            result.append(0.); continue
        a = sum(own)/len(own)
        b = min(np.mean([abs(value-other) for j, other in enumerate(values) if labels[j] == group])
                for group in np.unique(labels) if group != labels[i])
        result.append((b-a)/max(a, b) if max(a, b) else 0.)
    return np.array(result)


class MethodChecks(unittest.TestCase):
    def test_scalar_silhouette_matches_literal_and_blocked_duplicates_singleton(self):
        values = np.array([-3., -2., -2., 0., .1, .3, .3, 1., 4., 5., 9.])
        labels = np.array([0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 3])
        exact = scalar_silhouette(values, labels)
        np.testing.assert_allclose(exact, literal_scalar_silhouette(values, labels), atol=1e-13)
        blocked = silhouette_blocks(scalar_engine(values), {'model': labels}, 3)['model']
        np.testing.assert_allclose(exact, blocked, atol=1e-13)
        self.assertEqual(exact[-1], 0.)

    def test_scalar_silhouette_random_permuted_labels_and_uniform_scale(self):
        generator = np.random.default_rng(28)
        values = generator.normal(size=79); labels = generator.integers(0, 5, len(values))
        expected = literal_scalar_silhouette(values, labels)
        np.testing.assert_allclose(scalar_silhouette(values, labels), expected, atol=1e-12)
        np.testing.assert_allclose(scalar_silhouette(3*values+2, 11-labels), expected, atol=1e-12)
        np.testing.assert_allclose(scalar_silhouette(np.zeros(6), np.repeat([0, 1], 3)), 0.)

    def test_constant_padding_preserves_all_distances_and_scalar_lloyd(self):
        scalar = np.array([-2., -1.9, -1.8, .1, .2, .3, 2., 2.1, 2.2])
        values = scalar_engine(scalar)
        np.testing.assert_allclose(np.linalg.norm(values[:, None]-values[None, :], axis=2), np.abs(scalar[:, None]-scalar[None, :]))
        bank = [dict(source='r2', initial_seed=17, indices=np.array([0, 3, 6]))]
        fitted = fit_bank(values, np.ones(len(values)), bank)
        np.testing.assert_allclose(np.sort(fitted['centers'][:, 1]), [-1.9, .2, 2.1])
        self.assertAlmostEqual(fitted['inertia'], .06, places=13)
        reference = kmeans(scalar[:, None], 3, seed=17)
        self.assertAlmostEqual(fitted['inertia'], reference['inertia'], places=13)

    def test_scalar_nearest_centers_define_midpoint_intervals(self):
        scalar = np.linspace(-4, 4, 81); centers = np.array([-2., 0., 3.])
        labels, _ = predict(scalar_engine(scalar), scalar_engine(centers))
        expected = np.searchsorted((centers[:-1]+centers[1:])/2, scalar, side='left')
        np.testing.assert_array_equal(labels, expected)

    def test_same_population_and_scale_r2_does_not_depend_on_metadata_age(self):
        raw = pd.DataFrame(dict(mean_age_nominal=[20., 35., 45., 65., 80.], participation_deviation_national=[-.2, -.1, 0., .1, .2]))
        scaler = fit_scaler(raw.to_numpy(), 'standard')
        before = paired_matrices(raw, scaler)
        shifted = raw.copy(); shifted.mean_age_nominal = shifted.mean_age_nominal.iloc[::-1].to_numpy()
        after = paired_matrices(shifted, scaler)
        self.assertEqual(before['r1'].shape, before['r2'].shape)
        np.testing.assert_array_equal(before['r1'][:, 1], before['r2'][:, 1])
        np.testing.assert_array_equal(before['r2'], after['r2'])
        self.assertFalse(np.array_equal(before['r1'], after['r1']))

    def test_shared_initializations_use_both_geometries_without_different_rows(self):
        raw = pd.DataFrame(dict(mean_age_nominal=np.arange(25.), participation_deviation_national=np.sin(np.arange(25.))))
        matrices = paired_matrices(raw, fit_scaler(raw.to_numpy(), 'standard'))
        bank = shared_bank(matrices, 4, 17); repeated = shared_bank(matrices, 4, 17)
        self.assertEqual([item['source'] for item in bank], ['r1']*5+['r2']*5)
        for left, right in zip(bank, repeated):
            np.testing.assert_array_equal(left['indices'], right['indices'])
            self.assertEqual(len(np.unique(left['indices'])), 4)

    def test_band_explanation_measures_predefined_geometry_not_discovered_groups(self):
        frame = pd.DataFrame(dict(age_band=['young']*3+['old']*3, SEXO=['0', '1', '0']*2,
            EDOCVE=['1']*6, MPIOCVE=['1', '2', '3']*2, mean_age_nominal=[20., 20., 20., 70., 70., 70.],
            participation_deviation_national=[-.1, 0., .1, -.1, 0., .1], LN=[100]*6))
        bands, fractions = band_diagnosis(frame)
        self.assertEqual(len(bands), 2)
        self.assertAlmostEqual(fractions['age_variance_explained_by_band'], 1.)
        self.assertAlmostEqual(fractions['delta_variance_explained_by_band'], 0.)


if __name__ == '__main__':
    unittest.main()
