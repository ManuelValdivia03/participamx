"""Pruebas de población emparejada, pesos, arranques comunes y remuestreo en bloques."""
from itertools import product
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from clustering_core import fit_scaler, transform
from compare_demographic_features import (FEATURE_SETS, diagnostics, fit_bank, fit_weights,
    initialization_bank, lloyd, membership, municipality_samples, paired_population,
    pandas_numerical_check, weighted_group_sse)
from compare_demographic_features import run_models, run_resampling
from test_demographic_pilot import example_metadata
from run_demographic_pilot import add_reference


class ComparisonChecks(unittest.TestCase):
    def test_weighted_lloyd_matches_literal_replication(self):
        values = np.array([[0., 0.], [.2, .1], [.4, .4], [3., 3.], [3.3, 3.], [3.7, 3.4]])
        weights = np.array([1, 2, 4, 3, 1, 2])
        initial = values[[0, 5]]
        weighted = lloyd(values, weights, initial)
        expanded = lloyd(np.repeat(values, weights, axis=0), np.ones(weights.sum()), initial)
        self.assertTrue(weighted['converged'])
        np.testing.assert_allclose(weighted['centers'], expanded['centers'], atol=1e-13)
        self.assertAlmostEqual(weighted['inertia'], expanded['inertia'], places=12)
        pandas_numerical_check(values, weights, weighted['labels'], weighted['centers'], weighted['inertia'])

    def test_weighted_lloyd_matches_exhaustive_small_reference(self):
        points = [(0., 0.), (.2, .1), (.4, .4), (3., 3.), (3.3, 3.), (3.7, 3.4)]
        weights = [1, 2, 4, 3, 1, 2]
        objectives = []
        for tail in product([0, 1], repeat=5):
            labels = [0, *tail]
            if 1 not in labels: continue
            centers = []
            for group in range(2):
                indices = [i for i, label in enumerate(labels) if label == group]
                total = sum(weights[i] for i in indices)
                centers.append([sum(weights[i]*points[i][j] for i in indices)/total for j in range(2)])
            objectives.append(sum(weights[i]*sum((points[i][j]-centers[labels[i]][j])**2 for j in range(2)) for i in range(6)))
        fit = lloyd(np.array(points), np.array(weights), np.array([points[0], points[-1]]))
        self.assertAlmostEqual(fit['inertia'], min(objectives), places=12)

    def test_shared_bank_is_symmetric_and_reproducible(self):
        metadata, _ = add_reference(example_metadata())
        matrices = {name: transform(metadata[columns].to_numpy(), fit_scaler(metadata[columns].to_numpy(), 'standard'))
            for name, columns in FEATURE_SETS.items()}
        bank = initialization_bank(matrices, 4, 17)
        same = initialization_bank(matrices, 4, 17)
        self.assertEqual([item['source'] for item in bank].count('absolute'), 5)
        self.assertEqual([item['source'] for item in bank].count('relative'), 5)
        for left, right in zip(bank, same):
            np.testing.assert_array_equal(left['indices'], right['indices'])
            self.assertEqual(len(np.unique(left['indices'])), 4)
        fit = fit_bank(matrices['relative'], np.ones(len(metadata)), bank)
        self.assertTrue(fit['converged'])
        self.assertEqual(len(fit['initializations']), 10)

    def test_equal_municipality_weights_do_not_equal_nominal_weights(self):
        metadata = example_metadata().iloc[[0, 1, 2, 4, 8, 9]].copy()
        weights = fit_weights(metadata, 'equal_municipality')
        municipal = metadata[['EDOCVE', 'MPIOCVE']].copy(); municipal['weight'] = weights
        np.testing.assert_allclose(municipal.groupby(['EDOCVE', 'MPIOCVE']).weight.sum(), 1)
        self.assertEqual(fit_weights(metadata, 'equal_segment').sum(), len(metadata))
        self.assertEqual(fit_weights(metadata, 'nominal').sum(), metadata.LN.sum())

    def test_relative_population_must_not_silently_drop_eligible_rows(self):
        metadata, _ = add_reference(example_metadata())
        mask, preserved = paired_population(metadata)
        self.assertEqual(mask.sum(), len(metadata))
        self.assertEqual(len(preserved), len(metadata))
        metadata.loc[0, 'participation_deviation_national'] = np.nan
        with self.assertRaises((ValueError, AssertionError, RuntimeError)):
            paired_population(metadata)

    def test_municipal_sampling_never_splits_segments(self):
        metadata = example_metadata()
        keys, draws = municipality_samples(metadata, replicates=5, fraction=.8)
        other_keys, other_draws = municipality_samples(metadata, replicates=5, fraction=.8)
        pd.testing.assert_frame_equal(keys, other_keys)
        np.testing.assert_array_equal(draws, other_draws)
        for draw in draws:
            inside = membership(metadata, keys, draw)
            check = metadata[['EDOCVE', 'MPIOCVE']].copy(); check['inside'] = inside
            self.assertTrue(check.groupby(['EDOCVE', 'MPIOCVE']).inside.nunique().eq(1).all())
            self.assertEqual(draw.sum(), int(.8*len(keys)))

    def test_age_only_partition_has_no_additional_within_cell_separation(self):
        metadata, _ = add_reference(example_metadata())
        labels = (metadata.age_band.eq('35-59')).to_numpy(dtype=int)
        raw = metadata[FEATURE_SETS['relative']].to_numpy()
        result = diagnostics(metadata, raw, labels, np.ones(len(metadata)))
        self.assertAlmostEqual(result['within_age_sex_rate_r2'], 0., places=12)
        self.assertEqual(result['age_band_purity'], 1.)
        groups = pd.factorize(pd.MultiIndex.from_frame(metadata[['age_band', 'SEXO']]))[0]
        weights = fit_weights(metadata, 'equal_municipality')
        self.assertAlmostEqual(weighted_group_sse(metadata.participation_observed.to_numpy(), groups, weights),
            weighted_group_sse(metadata.participation_deviation_national.to_numpy(), groups, weights), places=14)

    def test_context_and_resampling_keep_all_pending_rows(self):
        metadata, _ = add_reference(example_metadata())
        metadata['unspecified_rate'] = metadata.NS/metadata.LN
        metadata.loc[0, ['SV', 'NV', 'NS', 'specified_count', 'participation_observed', 'participation_deviation_national']] = [0, 0, 200, 0, np.nan, np.nan]
        base, full = paired_population(metadata)
        full['is_eligible'] = base
        scalers = {name: fit_scaler(full.loc[base, columns].to_numpy(), 'standard') for name, columns in FEATURE_SETS.items()}
        original = full.copy(deep=True)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            contexts, metrics, stability, comparisons, validation, coverage, initializations = run_models(
                'test', full, base, scalers, output, 7, 2, 'unavailable')
            self.assertEqual(len(metrics), 72)
            self.assertTrue(all(row['converged'] for row in metrics))
            self.assertEqual(len(contexts), 8)
            self.assertEqual(len(stability), 72)
            source = pd.read_parquet(output/'contexts/test_relative_equal_municipality_main/labels.parquet')
            self.assertEqual(len(source), len(full))
            self.assertTrue(source.loc[~base, 'k04_seed17'].isna().all())
            keys, draws = municipality_samples(full, replicates=2, fraction=.8)
            rows, _, coverage, _ = run_resampling('test', full, base, contexts, keys, draws, output, 2)
            self.assertEqual(len(rows), 24)
            self.assertEqual(len(coverage), 2)
            projected = pd.read_parquet(output/'resampling/test/sample_000/labels.parquet')
            self.assertTrue(projected.loc[~base, 'relative_equal_municipality_k4'].isna().all())
            self.assertTrue(projected.is_oob_eligible.any())
        pd.testing.assert_frame_equal(original, full)


if __name__ == '__main__':
    unittest.main()
