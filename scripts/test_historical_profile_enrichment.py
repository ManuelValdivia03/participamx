"""Pruebas de asignación heredada, ausencias y conciliación de los derivados históricos."""
import json
from pathlib import Path
import unittest

import pandas as pd

from build_historical_profile_enrichment import aggregate_cell, direction, supported, build_year, YEARS, PUBLIC, OUTPUT, sha


class HistoricalEnrichmentTests(unittest.TestCase):
    def test_integer_sign_tie_and_undefined(self):
        self.assertEqual(direction(10**15+1, 2*10**15, 1, 2), 1)
        self.assertEqual(direction(3, 6, 1, 2), 0)
        self.assertIsNone(direction(0, 0, 1, 2))

    def test_absence_differs_from_observed_zero(self):
        missing = aggregate_cell(pd.DataFrame(), 'R', 200)
        self.assertIsNone(missing['LN'])
        self.assertEqual(missing['status'], 'missing')
        frame = pd.DataFrame([dict(LN=200,SV=0,NV=200,NS=0,source_row_count=5,sex_2_source_rows=0,sex_2_nominal_count=0,specified_count=200,national_rate=.5)])
        cell = aggregate_cell(frame, 'R', 200)
        self.assertEqual(cell['participation'], 0)
        self.assertEqual(cell['status'], 'defined')
        frame.loc[0,['NV','NS','specified_count']] = [0,200,0]
        self.assertIsNone(aggregate_cell(frame,'R',200)['participation'])

    def test_all_three_support_conditions(self):
        f = pd.DataFrame(dict(LN=[100,99,100,100],specified_count=[100,99,99,100],source_row_count=[5,5,5,4]))
        self.assertEqual(supported(f).tolist(), [True,False,False,False])

    def test_all_elections_reproduce_and_reconcile(self):
        manifest = json.loads((OUTPUT/'manifest.json').read_text(encoding='utf-8'))
        for relative, digest in manifest['inputs'].items():
            self.assertEqual(sha(Path(relative)), digest)
        for year in YEARS:
            with self.subTest(year=year):
                payload, audit, rows = build_year(year)
                published = json.loads((PUBLIC/f'enriched-{year}.json').read_text(encoding='utf-8'))
                self.assertEqual(payload,published)
                self.assertEqual(len(payload['profiles']),6)
                self.assertEqual(len(rows),42)
                self.assertTrue(all(r['difference']==0 for r in rows))
                self.assertGreater(audit['low_support_child_cells'],0)
                self.assertEqual(payload['transversalFinding'] is None, year != 2024)
                for p in payload['profiles']:
                    self.assertEqual(p['additionalCategory']['status'], 'low_support' if year==2024 else 'unavailable_category')
                    for dimension in ['sexCells','sectionCells','jointCells']:
                        self.assertEqual(sum(c['sourceRows'] or 0 for c in p[dimension]),p['counts']['source_row_count'])


if __name__ == '__main__':
    unittest.main()
