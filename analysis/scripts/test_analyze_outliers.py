"""Pruebas de ponderaciones, cortes descriptivos y tasas no definidas."""

from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from analyze_outliers import age_statistics, distribution_statistics, scan_extreme_rates, unspecified_statistics
from clean_data import ValidationError


class OutlierChecks(unittest.TestCase):
    def test_weighted_quantiles_equal_expansion_without_expanding_in_production(self):
        values=np.array([18,25,40,90,140])
        weights=np.array([10,5,7,2,1])
        expanded=np.repeat(values,weights)
        result=distribution_statistics(values,weights)
        for key,probability in [('q1',.25),('median',.5),('q3',.75),('p99',.99)]:
            self.assertAlmostEqual(result[key],np.quantile(expanded,probability))
        self.assertAlmostEqual(result['mean'],expanded.mean())
        self.assertAlmostEqual(result['std'],expanded.std(ddof=1))
        self.assertEqual(result['outlier_count'],int(((expanded<result['lower_fence'])|(expanded>result['upper_fence'])).sum()))
        self.assertEqual(distribution_statistics([1,2],[0,0]),{})
        with self.assertRaises(ValidationError): distribution_statistics([1,2],[1,-1])
        with self.assertRaises(ValidationError): distribution_statistics([1,2],[1,.5])

    def test_age_interval_boundaries_and_empty_interval(self):
        frame=pd.DataFrame(dict(election_year=[2024]*7,age_value=[18,100,101,110,111,120,121],
            source_row_count=[2,1,1,1,1,1,1],LN=[10,1,1,2,1,2,1],SV=[5,0,1,0,0,1,1],
            NV=[4,1,0,2,1,1,0],NS=[1,0,0,0,0,0,0]))
        original=frame.copy(deep=True)
        _,bands,visibility=age_statistics(frame)
        self.assertEqual([r['source_row_count'] for r in bands],[2,2,1])
        self.assertEqual([r['LN'] for r in bands],[3,3,1])
        self.assertEqual(visibility[0]['hidden_LN'],7)
        self.assertEqual(visibility[0]['hidden_source_rows'],5)
        pd.testing.assert_frame_equal(frame,original)
        _,empty,_=age_statistics(frame[frame.age_value.le(120)])
        self.assertEqual(empty[-1]['LN'],0)
        self.assertIsNone(empty[-1]['participation_observed'])

    def test_ns_weighting_and_scant_rate_nulls(self):
        municipal=pd.DataFrame(dict(election_year=[2024,2024],LN=[10,90],NS=[0,90],
            source_row_count=[2,3],unspecified_rate=[0.,1.]))
        rows=unspecified_statistics(municipal)
        self.assertAlmostEqual(rows[0]['mean'],.5)
        self.assertAlmostEqual(rows[1]['mean'],.9)
        self.assertAlmostEqual(rows[1]['mean'],rows[1]['national_unspecified_rate'])
        frame=pd.DataFrame(dict(election_year=[2024]*3,EDOCVE=['01']*3,MPIOCVE=['001']*3,
            age_value=[105,30,40],SEXO=['2','0','1'],state_name_label=['Estado']*3,
            municipality_name_label=['Municipio']*3,source_row_count=[1]*3,
            LN=[1,10,200],SV=[1,0,100],NV=[0,0,100],NS=[0,10,0],specified_count=[1,0,200],
            participation_observed=[1.,np.nan,.5],unspecified_rate=[0.,1.,0.],
            sex_2_source_rows=[1,0,0],sex_2_nominal_count=[1,0,0]))
        with tempfile.TemporaryDirectory() as temporary:
            source=Path(temporary)
            (source/'municipality_age_sex').mkdir()
            frame.to_parquet(source/'municipality_age_sex/table.parquet',index=False)
            rows,examples,totals=scan_extreme_rates(source,batch_size=1)
            categories={row['category']:row for row in rows}
            self.assertEqual(categories['observed_undefined']['aggregate_groups'],1)
            self.assertEqual(categories['extreme_small_specified']['aggregate_groups'],1)
            self.assertEqual(categories['exact_zero']['aggregate_groups'] if 'exact_zero' in categories else 0,0)
            self.assertEqual(examples.age_value.tolist(),[105])
            self.assertEqual(totals['source_row_count'],3)
            self.assertEqual(totals['sex_2_source_rows'],1)


if __name__=='__main__':
    unittest.main()
