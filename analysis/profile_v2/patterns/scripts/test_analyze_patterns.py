"""Verificaciones de contrastes, remuestreo, cobertura y artefactos V2.1."""
import json
from pathlib import Path
import re
import tempfile
import unittest

import numpy as np
import pandas as pd
from scipy.stats import bootstrap

from analyze_patterns import (OUTPUT, BANDS, digest, eligible, estimators, exact_direction, matched_block, municipal_split, save)


class MathematicalTests(unittest.TestCase):
    def test_integer_sign_without_overflow_nulls_and_ties(self):
        self.assertIsNone(exact_direction(0, 0, 1, 2))
        self.assertEqual(exact_direction(10**15 + 1, 2 * 10**15, 1, 2), 1)
        self.assertEqual(exact_direction(10**15 - 1, 2 * 10**15, 1, 2), -1)
        self.assertEqual(exact_direction(10**15, 2 * 10**15, 1, 2), 0)

    def test_support_is_not_sections_or_ns(self):
        frame=pd.DataFrame({"age_band":["18-34"]*3+["101+"],"SEXO":["0","1","2","0"],"LN":[100]*4,
            "specified_count":[100]*4,"source_row_count":[5]*4,"section_count":[1]*4,"unspecified_rate":[.5]*4})
        self.assertEqual(eligible(frame).tolist(),[True,True,False,False])

    def test_matched_blocks_use_four_cells_and_exclude_missing(self):
        rows=[]
        for municipality in ["1","2"]:
            for n,(sex,section,sv) in enumerate([("1","R",80),("0","R",40),("1","U",60),("0","U",30)]):
                if municipality=="2" and n==3:
                    continue
                rows.append({"municipal_id":"1|"+municipality,"EDOCVE":"1","MPIOCVE":municipality,"row_id":f"{municipality}_{n}",
                    "age_band":"18-34","SEXO":sex,"TIPOSEC":section,"LN":100,"SV":sv,"NV":100-sv,"NS":0,
                    "specified_count":100,"source_row_count":5,"section_count":1,"high_ns":False})
        result=matched_block(pd.DataFrame(rows),[("1","R",1),("0","R",-1),("1","U",-1),("0","U",1)],
                             "synthetic","interaction","18-34","R-U")
        self.assertEqual(len(result),1)
        self.assertAlmostEqual(result.interaction_pp.iloc[0],10)
        self.assertEqual(result.LN.iloc[0],400)
        self.assertTrue(np.allclose(estimators(result),[10,10,10]))
        expanded=pd.concat([result,result],ignore_index=True)
        self.assertTrue(np.allclose(estimators(expanded,[1,3]),estimators(pd.concat([result]*4,ignore_index=True))))

    def test_paired_resampling_matches_independent_scipy(self):
        values=np.array([-2.,3.,10.,-4.,7.]);weights=np.array([2.,1.,5.,3.,4.])
        def statistic(v,w):
            return np.sum(v*w)/np.sum(w)
        independent=bootstrap((values,weights),statistic,paired=True,vectorized=False,method="percentile",n_resamples=120,batch=120,
                              rng=np.random.default_rng(72)).bootstrap_distribution
        rng=np.random.default_rng(72)
        own=[]
        for _ in range(120):
            indices=rng.integers(len(values),size=len(values))
            multiplicity=np.bincount(indices,minlength=len(values))
            own.append(np.sum(multiplicity*values*weights)/np.sum(multiplicity*weights))
        np.testing.assert_allclose(own,independent,atol=1e-12)

    def test_parquet_verification_uses_keys_not_filtered_index(self):
        frame=pd.DataFrame({"row_id":["a","b"],"flag":pd.array([True,None],dtype="boolean")},index=[6,19])
        with tempfile.TemporaryDirectory() as temp:
            save(Path(temp),"subset.parquet",frame)
            self.assertEqual(pd.read_parquet(Path(temp)/"subset.parquet").row_id.tolist(),["a","b"])


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (OUTPUT/"_SUCCESS").exists():
            raise unittest.SkipTest("Ejecutar primero el análisis para comprobar la entrega")
        cls.screen=pd.read_csv(OUTPUT/"candidates/screening.csv")
        cls.original=pd.read_parquet(OUTPUT/"reference/all_observations.parquet")

    def test_preserved_original_counts_and_pending_nulls(self):
        frame=self.original
        self.assertEqual(len(frame),38805)
        self.assertEqual(int(frame.LN.sum()),98330348)
        self.assertEqual(int(frame.source_row_count.sum()),9773730)
        self.assertEqual(int(frame.is_eligible.sum()),31470)
        self.assertEqual(int((~frame.is_eligible).sum()),7335)
        self.assertEqual(int(frame.loc[frame.SEXO.eq("2"),"LN"].sum()),105)
        self.assertEqual(int(frame.loc[frame.age_band.eq("101+"),"LN"].sum()),13197)
        self.assertTrue(frame.participation_observed.isna().equals(frame.specified_count.eq(0)))
        self.assertTrue(frame.EDOCVE.map(type).eq(str).all())

    def test_screening_cannot_promote_failed_criteria(self):
        criteria=[c for c in self.screen.columns if c.startswith("pass_")]
        self.assertEqual(len(self.screen),6)
        self.assertEqual(len(criteria),7)
        self.assertTrue(self.screen.passes_screen.equals(self.screen[criteria].all(axis=1)))
        for r in self.screen[self.screen.passes_screen].itertuples():
            self.assertGreaterEqual(abs(r.equal_municipality_pp),2)
            self.assertGreaterEqual(abs(r.nominal_pp),2)
            self.assertGreaterEqual(r.municipalities,200)

    def test_reversals_correct_reference_and_support(self):
        frame=pd.read_parquet(OUTPUT/"sign_reversals/all_2704.parquet")
        self.assertEqual(len(frame),2704)
        self.assertTrue(frame.is_eligible.all())
        self.assertTrue((frame.exact_direction*frame.parent_direction).eq(-1).all())
        self.assertTrue(np.allclose(frame.national_rate,frame.reference_age_sex))
        self.assertEqual(int(frame.LN.sum()),5688327)
        sensitivity=pd.read_csv(OUTPUT/"sign_reversals/sensitivity.csv").set_index("scenario")
        self.assertEqual(sensitivity.loc["support_100_sources_5","original_reversals_surviving"],2704)
        self.assertLessEqual(sensitivity.loc["support_500_sources_5","original_reversals_surviving"],2704)

    def test_memberships_no_inflated_coverage(self):
        membership=pd.read_parquet(OUTPUT/"candidates/all_six_memberships.parquet")
        self.assertFalse(membership.duplicated(["pattern_id","row_id"]).any())
        accepted=membership[membership.passes_screen]
        unique=set(accepted.row_id)
        union=self.original[self.original.row_id.isin(unique)]
        expected=json.loads((OUTPUT/"candidates/union_coverage.json").read_text(encoding="utf-8"))
        self.assertEqual(len(unique),expected["union_rows"])
        self.assertEqual(int(union.LN.sum()),expected["union"]["LN"])
        self.assertTrue(union.is_eligible.all())

    def test_split_and_resampling_keeps_municipal_blocks(self):
        split=pd.read_parquet(OUTPUT/"validation/municipal_split.parquet")
        self.assertEqual(len(split),2477)
        self.assertFalse(split.municipal_id.duplicated().any())
        data=np.load(OUTPUT/"resampling/municipal_bootstrap.npz",allow_pickle=False)
        self.assertEqual(data["multiplicities"].shape,(1000,2477))
        self.assertTrue((data["multiplicities"].sum(axis=1)==2477).all())
        self.assertEqual(data["estimates"].shape,(1000,6,3))
        self.assertTrue(np.isfinite(data["estimates"]).all())
        bands=pd.read_csv(OUTPUT/"validation/simultaneous_envelopes.csv")
        self.assertEqual(len(bands),18)
        self.assertEqual(bands.max_standardized_critical.nunique(),1)

    def test_json_names_only_after_screening(self):
        payload=json.loads((OUTPUT/"candidates/experimental_patterns.json").read_text(encoding="utf-8"))
        self.assertEqual(len(payload["profiles"]),int(self.screen.passes_screen.sum()))
        self.assertEqual(len(payload["profiles"])+len(payload["diagnostic_not_validated"]),6)
        self.assertFalse(payload["published"])
        for p in payload["profiles"]:
            self.assertEqual(len(p["name_proposals"]),3)
            self.assertEqual(len(p["components"]),4)
        for p in payload["diagnostic_not_validated"]:
            self.assertEqual(p["name_proposals"],[])
        json.dumps(payload,allow_nan=False)

    def test_report_links_and_hashes(self):
        for path in list((OUTPUT/"reports").glob("*.md"))+list((OUTPUT/"candidates/cards").glob("*.md")):
            for target in re.findall(r"\]\(([^)]+)\)",path.read_text(encoding="utf-8")):
                if "://" not in target:
                    self.assertTrue((path.parent/target.split("#")[0]).resolve().exists(),f"{path}: {target}")
        manifest=json.loads((OUTPUT/"metadata/run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["new_clustering_fits"],0)
        for name,value in manifest["artifacts"].items():
            self.assertEqual(digest(OUTPUT/name),value,name)


if __name__=="__main__":
    unittest.main()
