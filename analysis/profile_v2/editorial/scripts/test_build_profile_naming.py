"""Pruebas matemáticas, de conciliación y de la entrega editorial."""
import json
from pathlib import Path
import re
import unittest

import numpy as np
import pandas as pd

from build_profile_naming import DEFAULT_OUTPUT, ORDER, aggregate, digest, exact_direction, validate_payload


class CalculationTests(unittest.TestCase):
    def test_exact_sign_ties_null_and_large_integer_products(self):
        self.assertIsNone(exact_direction(0, 0, 7, 10))
        self.assertIsNone(exact_direction(1, 2, 0, 0))
        self.assertEqual(exact_direction(7, 10, 7, 10), 0)
        self.assertEqual(exact_direction(8, 10, 7, 10), 1)
        self.assertEqual(exact_direction(6, 10, 7, 10), -1)
        self.assertEqual(exact_direction(10**15 + 1, 2 * 10**15, 1, 2), 1)
        self.assertEqual(exact_direction(10**15 - 1, 2 * 10**15, 1, 2), -1)

    def test_aggregation_uses_counts_and_keeps_undefined_nominal(self):
        frame = pd.DataFrame({"LN": [100, 1000, 50], "SV": [80, 200, 0], "NV": [20, 800, 0],
            "NS": [0, 0, 50], "source_row_count": [5, 8, 1], "sex_2_source_rows": [0, 0, 0],
            "sex_2_nominal_count": [0, 0, 0], "specified_count": [100, 1000, 0],
            "reference_age_sex": [.5, .4, .3], "participation_observed": [.8, .2, np.nan],
            "is_eligible": [True, True, False], "exact_sign_opposes_parent": [False, True, False],
            "municipal_id": ["01|1", "01|2", "01|3"], "high_ns": [False, False, True]})
        result = aggregate(frame)
        self.assertEqual(result["LN"], 1150)
        self.assertEqual(result["undefined_LN"], 50)
        self.assertEqual(result["eligible_cells"], 2)
        self.assertEqual(result["eligible_flip_LN"], 1000)
        self.assertAlmostEqual(result["participation_observed"], 280 / 1100)
        self.assertAlmostEqual(result["matched_age_sex_reference"], 450 / 1100)
        self.assertNotAlmostEqual(result["participation_observed"], .5)


class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DEFAULT_OUTPUT / "_SUCCESS").is_file():
            raise unittest.SkipTest("Ejecutar primero build_profile_naming.py para validar artefactos")
        cls.payload = json.loads((DEFAULT_OUTPUT / "experimental_profile_names_2024.json").read_text(encoding="utf-8"))
        cls.summary = pd.read_csv(DEFAULT_OUTPUT / "evidence/profile_summary.csv")

    def test_payload_and_editorial_constraints(self):
        validate_payload(self.payload, {"profile_summary": self.summary})
        names = [p["recommended_name"] for p in self.payload["profiles"]]
        self.assertEqual(len(set(names)), 6)
        self.assertFalse(self.payload["published"])
        self.assertFalse(self.payload["replaces_published_V1"])
        for p in self.payload["profiles"]:
            for proposal in p["name_proposals"]:
                self.assertIn("2024", proposal["subtitle"])
                self.assertIn("referencia", proposal["subtitle"])

    def test_reconciliation_and_all_children_not_just_eligible(self):
        r = pd.read_csv(DEFAULT_OUTPUT / "evidence/parent_reconciliation.csv")
        self.assertEqual(len(r), 42)
        self.assertTrue(r.difference.eq(0).all())
        self.assertEqual(self.summary.LN.sum(), 98203780)
        self.assertEqual(self.summary.joint_cells.sum(), 33709)
        self.assertEqual(self.summary.eligible_cells.sum(), 31470)
        self.assertEqual(self.summary.eligible_flip_cells.sum(), 2704)
        self.assertEqual(self.summary.eligible_flip_LN.sum(), 5688327)
        self.assertGreater(self.summary.undefined_cells.sum(), 0)
        self.assertEqual(self.summary.parent_segments.sum(), 14190)

    def test_six_recommended_distinctive_features_are_true(self):
        s = self.summary.set_index("profile_id")
        self.assertEqual(s.delta_pp.idxmax(), "young_favorable")
        self.assertEqual(s.participation_observed.idxmin(), "young_unfavorable")
        self.assertEqual(s.municipalities.idxmax(), "adult_favorable")
        self.assertEqual(s.LN.idxmax(), "adult_unfavorable")
        self.assertEqual(s.participation_observed.idxmax(), "older_favorable")
        self.assertEqual(s.delta_pp.idxmin(), "older_unfavorable")
        self.assertEqual(s.delta_sd_pp.idxmax(), "young_favorable")
        self.assertEqual(s.near_reference_parent_fraction.idxmax(), "adult_unfavorable")
        self.assertTrue(s.nominal_share_U.gt(.5).all())

    def test_joint_counts_and_same_reference_sign_reversal(self):
        j = pd.read_parquet(DEFAULT_OUTPUT / "evidence/child_trace.parquet")
        f = pd.read_parquet(DEFAULT_OUTPUT / "evidence/eligible_sign_reversals.parquet")
        self.assertEqual(len(f), 2704)
        self.assertFalse(j.row_id.duplicated().any())
        self.assertTrue(f.is_eligible.all())
        self.assertTrue((f.exact_child_direction * f.direction).eq(-1).all())
        self.assertTrue(j.loc[j.specified_count.eq(0), "exact_child_direction"].isna().all())
        self.assertTrue(j.loc[j.specified_count.eq(0), "participation_observed"].isna().all())
        self.assertTrue(np.allclose(j.reference_age_sex, j.national_SV / j.national_specified_count))
        self.assertTrue((j.LN == j.SV + j.NV + j.NS).all())
        self.assertEqual(j.groupby("municipal_id").ngroups, 2402)
        self.assertEqual(j.loc[j.is_eligible].groupby("municipal_id").ngroups, 2392)

    def test_each_cross_mean_keeps_parent_sign_without_hiding_local_flips(self):
        joint = pd.read_csv(DEFAULT_OUTPUT / "evidence/profile_sex_section.csv")
        self.assertEqual(len(joint), 36)
        for profile_id in ORDER:
            g = joint[joint.profile_id.eq(profile_id)]
            expected = -1 if profile_id.endswith("unfavorable") else 1
            self.assertTrue((g.delta_pp * expected > 0).all())
            self.assertGreater(g.eligible_flip_cells.sum(), 0)

    def test_generated_markdown_links_resolve(self):
        for path in (DEFAULT_OUTPUT / "reports").rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                local = target.split("#")[0]
                if local and "://" not in local:
                    self.assertTrue((path.parent / local).resolve().exists(), f"{path}: {target}")

    def test_artifact_hashes(self):
        manifest = json.loads((DEFAULT_OUTPUT / "metadata/run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "validated")
        for name, value in manifest["artifacts"].items():
            self.assertEqual(digest(DEFAULT_OUTPUT / name), value, name)


if __name__ == "__main__":
    unittest.main()
