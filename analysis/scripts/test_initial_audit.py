"""Pruebas de las comprobaciones críticas con datos sintéticos aislados."""

from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
import pandas as pd

from initial_audit import (
    COLUMNS, KEY, audit_year, duplicate_candidates, invalid_reason, missing,
    save_hashes, verify_duplicates, weighted_statistics,
)


class AuditChecks(unittest.TestCase):
    def test_full_audit_preserves_source_and_distinguishes_unevaluable(self):
        """Valida excepciones reales, faltantes y procedencia en bloques de una fila."""
        first = dict(zip(COLUMNS, ["2024", "06/02/2024", "01", "Estado", "001", "Municipio", "1", "U", "1", "", "0", "18", "5", "3", "2", "0"]))
        mismatch = dict(first, SECCION="2", NV="1")
        unevaluable = dict(first, SECCION="3", LN="0", SV="0", NV="0", NS="")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "fixture_2024.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("first.csv", pd.DataFrame([first, mismatch], columns=COLUMNS).to_csv(index=False))
                archive.writestr("second.csv", pd.DataFrame([unevaluable, first], columns=COLUMNS).to_csv(index=False))
            original = path.read_bytes()
            result = audit_year(path, 2024, 1, directory)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(result["checks"]["equation_mismatch"], 1)
            self.assertEqual(result["checks"]["equation_unevaluable"], 1)
            self.assertEqual(result["duplicates"]["full"]["excess_rows"], 1)
            evidence = pd.read_csv(directory / "row_exceptions_2024.csv", dtype=str, na_filter=False)
            self.assertEqual(evidence["issue"].tolist(), ["equation_mismatch", "equation_unevaluable"])
            self.assertEqual(evidence["difference"].tolist(), ["1", ""])
            self.assertEqual(evidence["NS"].tolist(), ["0", ""])

    def test_exact_statistics_match_expanded_values(self):
        """Comprueba cuantiles interpolados, varianza y atípicos sin muestreo."""
        values = np.array([0, 0, 1, 2, 2, 3, 5, 100])
        stats = weighted_statistics(Counter(map(str, values)))
        self.assertAlmostEqual(stats["mean"], values.mean())
        self.assertAlmostEqual(stats["std"], values.std(ddof=1))
        for field, probability in (("q1", .25), ("median", .5), ("q3", .75), ("p99", .99)):
            self.assertAlmostEqual(stats[field], np.quantile(values, probability))
        self.assertEqual(stats["upper_outliers"], 1)
        self.assertEqual(stats["total"], int(values.sum()))
        self.assertEqual(weighted_statistics(Counter({"": 5})), {})

    def test_missing_and_year_specific_categories(self):
        """Distingue cero de faltante y respeta el diccionario por año."""
        self.assertFalse(missing("0"))
        self.assertTrue(missing("  "))
        self.assertEqual(invalid_reason("SEXO", "2", 2024), "")
        self.assertEqual(invalid_reason("SEXO", "2", 2021), "unknown_sex_category")
        self.assertEqual(invalid_reason("DEL", "0", 2021), "nonpositive_identifier")
        self.assertEqual(invalid_reason("LN", "-1", 2024), "negative_count")
        self.assertEqual(invalid_reason("LN", "1.5", 2024), "not_integer_literal")
        self.assertEqual(invalid_reason("EDAD", "118", 2024), "")

    def test_duplicates_cross_files_blocks_and_hash_collision(self):
        """Confirma tuplas, incluso al forzar una colisión de hash candidata."""
        first = dict(zip(COLUMNS, ["2024", "06/02/2024", "01", "Estado", "001", "Municipio", "1", "U", "1", "", "0", "18", "5", "3", "2", "0"]))
        changed_counts = dict(first, LN="6", NV="3")
        distinct = dict(first, SECCION="2")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "fixture.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("first.csv", pd.DataFrame([first, distinct], columns=COLUMNS).to_csv(index=False))
                archive.writestr("second.csv", pd.DataFrame([first, changed_counts], columns=COLUMNS).to_csv(index=False))
            frames = [pd.DataFrame([first, distinct], columns=COLUMNS), pd.DataFrame([first, changed_counts], columns=COLUMNS)]
            for kind, columns in (("full", COLUMNS), ("key", KEY)):
                for frame in frames:
                    save_hashes(directory, kind, pd.util.hash_pandas_object(frame[columns], index=False).to_numpy())
            candidates = {kind: duplicate_candidates(directory, kind) for kind in ("full", "key")}
            # Añade el hash de una fila única: no debe declararse duplicada.
            unique_hash = pd.util.hash_pandas_object(frames[0][COLUMNS], index=False).to_numpy()[1]
            candidates["full"] = np.append(candidates["full"], unique_hash)
            with zipfile.ZipFile(path) as archive:
                totals = verify_duplicates(archive, archive.namelist(), 1, candidates, 2024, directory)
            self.assertEqual(totals["full"], dict(groups=1, excess_rows=1, involved_rows=2))
            self.assertEqual(totals["key"], dict(groups=1, excess_rows=2, involved_rows=3))
            evidence = pd.read_csv(directory / "duplicates_full_2024.csv", dtype=str, na_filter=False)
            self.assertEqual(evidence["EDOCVE"].tolist(), ["01", "01"])
            self.assertEqual(evidence["MPIOCVE"].tolist(), ["001", "001"])
            self.assertEqual(evidence["DEL"].tolist(), ["", ""])
            self.assertEqual(evidence["record"].tolist(), ["1", "1"])
            # Fuerza realmente el mismo hash en todas las filas; sólo las tuplas
            # iguales deben contarse como duplicados, aunque los hashes colisionen.
            def constant_hash(frame, index):
                return pd.Series(np.full(len(frame), 42, dtype=np.uint64))
            forced_candidates = {kind: np.array([42], dtype=np.uint64) for kind in ("full", "key")}
            with patch("initial_audit.pd.util.hash_pandas_object", side_effect=constant_hash):
                with zipfile.ZipFile(path) as archive:
                    collided = verify_duplicates(archive, archive.namelist(), 1, forced_candidates, 2024, directory)
            self.assertEqual(collided, totals)


if __name__ == "__main__":
    unittest.main()
