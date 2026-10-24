"""Pruebas de denominadores, conservación entre niveles e invariancia por bloques."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from build_descriptive import (
    DEFAULT_THRESHOLDS, KEYS, METRICS, add_indicators, aggregate_batches,
    build_descriptive, compare_sums, sum_groups, validate_table, write_frame,
    refresh_presentation,
)
from clean_data import run_cleaning, file_hash
from test_clean_data import create_fixture


class DescriptiveChecks(unittest.TestCase):
    def test_weighted_rates_and_undefined_values_are_preserved(self):
        frame = pd.DataFrame(dict(election_year=[2024,2024,2024], EDOCVE=['01']*3,
            MPIOCVE=['001','001','002'], LN=[1,99,10], SV=[1,8,0], NV=[0,91,0], NS=[0,0,10],
            source_row_count=[1,1,1], sex_2_source_rows=[0,1,0], sex_2_nominal_count=[0,99,0]))
        aggregated = add_indicators(sum_groups(frame, KEYS['municipality']), DEFAULT_THRESHOLDS)
        validate_table(aggregated, KEYS['municipality'])
        self.assertEqual(aggregated.loc[0,'participation_observed'], .09)
        self.assertNotAlmostEqual(aggregated.loc[0,'participation_observed'], (1+8/99)/2)
        self.assertTrue(np.isnan(aggregated.loc[1,'participation_observed']))
        self.assertTrue(np.isnan(aggregated.loc[1,'nonparticipation_observed']))
        self.assertEqual(aggregated.loc[1,'unspecified_rate'], 1)
        self.assertEqual(aggregated.loc[1,'participation_nominal'], 0)
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'table.parquet'
            write_frame(aggregated,path,KEYS['municipality'])
            table=ds.dataset(path,format='parquet').to_table()
            self.assertEqual(table['participation_observed'].null_count,1)
            self.assertEqual(table['nonparticipation_observed'].null_count,1)
            self.assertEqual(table['MPIOCVE'].to_pylist(),['001','002'])

    def test_keys_separate_years_and_entities(self):
        frame=pd.DataFrame(dict(election_year=[2021,2024,2024], EDOCVE=['01','01','02'], MPIOCVE=['001']*3,
            **{metric:[1,2,3] for metric in METRICS}))
        grouped=sum_groups(frame,KEYS['municipality'])
        self.assertEqual(len(grouped),3)
        compare_sums(grouped,frame,KEYS['state'])

    def test_full_pipeline_and_chunk_invariance(self):
        with tempfile.TemporaryDirectory() as temporary,redirect_stdout(io.StringIO()):
            root=Path(temporary)
            create_fixture(root)
            source=root/'data/processed/cleaned'
            run_cleaning(root,source,chunk_size=2,expected_total=36)
            first=root/'data/processed/descriptive_one'
            second=root/'data/processed/descriptive_two'
            one=build_descriptive(root,source,first,batch_size=1,expected_total=36)
            two=build_descriptive(root,source,second,batch_size=4,expected_total=36)
            self.assertEqual(one['table_rows'],two['table_rows'])
            for name,keys in KEYS.items():
                left=ds.dataset(first/name,format='parquet').to_table().sort_by([(key,'ascending') for key in keys])
                right=ds.dataset(second/name,format='parquet').to_table().sort_by([(key,'ascending') for key in keys])
                self.assertTrue(left.equals(right),name)
                self.assertEqual(sum(left['source_row_count'].to_pylist()),36)
                self.assertEqual(sum(left['sex_2_source_rows'].to_pylist()),2)
                self.assertEqual(sum(left['sex_2_nominal_count'].to_pylist()),2)
                if 'EDOCVE' in keys:
                    self.assertEqual(left.schema.field('EDOCVE').type,pa.string())
            self.assertTrue((first/'_SUCCESS').is_file())
            baseline_hashes={str(path):file_hash(path) for path in [first/'metadata/run_manifest.json', *first.rglob('*.parquet')]}
            refresh_presentation(root,first)
            self.assertTrue((first/'metadata/presentation_manifest.json').is_file())
            self.assertTrue(all(file_hash(path)==digest for path,digest in baseline_hashes.items()))


if __name__=='__main__':
    unittest.main()
