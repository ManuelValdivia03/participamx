"""Pruebas de conservación, criterios y ausencias del contexto electoral."""
import unittest

import numpy as np
import pandas as pd
import pyarrow as pa
from clean_data import ValidationError

from evaluate_contextual_features import (aggregate_state, grouped, indicators, exclusion_audit,
    build_context_segments, profile_review, BAND_KEYS, MUNICIPAL_KEYS, ratio)


def source_frame():
    return pd.DataFrame([
        dict(EDOCVE='1', MPIOCVE='10', age_value=20, SEXO='0', TIPOSEC='U', SECCION='1',
            election_year=2024, state_code='1', registered_count=110, voted_count=60, not_voted_count=40, unspecified_count=10),
        dict(EDOCVE='1', MPIOCVE='10', age_value=21, SEXO='0', TIPOSEC='U', SECCION='1',
            election_year=2024, state_code='1', registered_count=100, voted_count=30, not_voted_count=60, unspecified_count=10),
        dict(EDOCVE='1', MPIOCVE='10', age_value=21, SEXO='1', TIPOSEC='R', SECCION='2',
            election_year=2024, state_code='1', registered_count=100, voted_count=0, not_voted_count=0, unspecified_count=100),
        dict(EDOCVE='1', MPIOCVE='10', age_value=105, SEXO='2', TIPOSEC='R', SECCION='2',
            election_year=2024, state_code='1', registered_count=1, voted_count=1, not_voted_count=0, unspecified_count=0)])


class ContextualFeatureTests(unittest.TestCase):
    def test_batch_boundaries_do_not_duplicate_sections(self):
        frame = source_frame()
        one = aggregate_state([pa.RecordBatch.from_pandas(frame)])
        chunks = aggregate_state([pa.RecordBatch.from_pandas(frame.iloc[i:i+1]) for i in range(len(frame))])
        for scheme in ['life_stage', 'broad']:
            keys = [*BAND_KEYS, 'TIPOSEC']
            pd.testing.assert_frame_equal(one[0][scheme].sort_values(keys).reset_index(drop=True),
                chunks[0][scheme].sort_values(keys).reset_index(drop=True))
            men = one[0][scheme].query("SEXO == '0'").iloc[0]
            self.assertEqual(men.source_row_count, 2)
            self.assertEqual(men.section_count, 1)
        self.assertEqual(one[2].shape[0], 2)
        self.assertEqual(one[0]['life_stage'].sex_2_nominal_count.sum(), 1)

    def test_periodic_reduction_preserves_counts(self):
        frame = source_frame()
        one = aggregate_state(pa.Table.from_pandas(pd.concat([frame]*10, ignore_index=True)).combine_chunks().to_batches())
        repeated = aggregate_state([pa.RecordBatch.from_pandas(frame) for _ in range(10)])
        for scheme in ['life_stage', 'broad']:
            pd.testing.assert_frame_equal(one[0][scheme], repeated[0][scheme])

    def test_unknown_section_type_is_rejected(self):
        frame = source_frame(); frame.loc[0, 'TIPOSEC'] = 'X'
        with self.assertRaises(ValidationError):
            aggregate_state([pa.RecordBatch.from_pandas(frame)])

    def test_conflicting_section_classification_is_rejected(self):
        frame = source_frame(); frame.loc[1, 'TIPOSEC'] = 'R'
        with self.assertRaises(ValidationError):
            aggregate_state([pa.RecordBatch.from_pandas(frame)])

    def test_structural_zero_composition_is_not_zero_rate(self):
        part = indicators(aggregate_state([pa.RecordBatch.from_pandas(source_frame())])[0]['life_stage'])
        original = indicators(grouped(part, BAND_KEYS))
        parent = build_context_segments(part, original, 'life_stage')
        men = parent.query("SEXO == '0'").iloc[0]
        self.assertEqual(men.section_ln_share_R, 0)
        self.assertEqual(men.section_ln_share_U, 1)
        self.assertFalse(men.has_section_type_R)
        women = parent.query("SEXO == '1'").iloc[0]
        self.assertTrue(np.isnan(women.participation_observed))
        self.assertEqual(women.section_ln_share_R, 1)

    def test_territorial_grid_keeps_absent_and_undefined_separate(self):
        children = indicators(aggregate_state([pa.RecordBatch.from_pandas(source_frame())])[0]['life_stage'])
        parent = indicators(grouped(children, BAND_KEYS))
        parent['section_count'] = 1
        municipalities = indicators(grouped(parent, MUNICIPAL_KEYS))
        cells, status, features = profile_review(children, parent, municipalities, 'life_stage', True)
        self.assertEqual(len(cells), 30)
        self.assertEqual(cells.cell_status.eq('undefined_rate').sum(), 1)
        absent = cells[cells.cell_status.eq('absent_combination')]
        self.assertTrue(absent.LN.isna().all())
        self.assertTrue(absent.participation_observed.isna().all())
        self.assertFalse(status.is_complete.any())
        self.assertEqual(len(features), 1)

    def test_separate_criteria_and_conditional_redundancy(self):
        rows = []
        for municipality, ln, specified, count in [('1', 200, 150, 1), ('2', 150, 20, 6),
            ('3', 80, 60, 8), ('4', 200, 0, 8), ('5', 150, 120, 5)]:
            rows.append(dict(EDOCVE='1', MPIOCVE=municipality, age_value=30, SEXO='0', LN=ln,
                SV=specified, NV=0, NS=ln-specified, source_row_count=count, sex_2_source_rows=0, sex_2_nominal_count=0))
        exact = indicators(pd.DataFrame(rows))
        municipalities = indicators(grouped(exact, MUNICIPAL_KEYS))
        core, truth, counterfactual, exclusions = exclusion_audit(exact, municipalities)
        self.assertEqual(exclusions.exclusion_reason.tolist(), ['source_rows_only',
            'specified_count_only_after_ln', 'no_segment_reaches_ln', 'all_unspecified', 'has_eligible_segments'])
        with_ln = counterfactual.query('require_ln and require_specified and require_source_rows').iloc[0]
        without_ln = counterfactual.query('not require_ln and require_specified and require_source_rows').iloc[0]
        self.assertEqual(with_ln.segments, without_ln.segments)
        self.assertEqual(with_ln.LN, without_ln.LN)

    def test_ratio_zero_denominator_is_null(self):
        values = ratio([0, 1], [0, 2])
        self.assertTrue(np.isnan(values[0])); self.assertEqual(values[1], .5)


if __name__ == '__main__':
    unittest.main()
