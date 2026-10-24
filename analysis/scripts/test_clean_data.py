"""Pruebas de conservación, validación y fallos con ZIP sintéticos temporales."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from clean_data import (
    COUNT_COLUMNS, ORIGINAL_COLUMNS, YEARS, ValidationError, file_hash,
    open_dataset, output_schema, run_cleaning, transform_chunk, verify_part,
)


def sample_frame(year, state="01"):
    base = dict(zip(ORIGINAL_COLUMNS, [str(year), "06/02/2024" if year == 2024 else f"1/7/{year}", state,
                " Estado ", "001", " Bacalar", "0001", "U", "1", "1", "0", "18", "5", "3", "0", "2"]))
    second = dict(base, SECCION="0002", EDAD="101", LN="2", SV="0", NV="2", NS="0")
    third = dict(base, SECCION="0003", EDAD="130", LN="1", SV="1", NV="0", NS="0",
                 SEXO="2" if year == 2024 else "1")
    if year in (2009, 2012):
        base.update(DEF=" ", DEL=" ")
    if year == 2024:
        base["DEL"] = ""
    return pd.DataFrame([base, second, third], columns=ORIGINAL_COLUMNS, dtype=str)


def sample_statistics(frame):
    stats = {}
    for name in ["EDAD", *COUNT_COLUMNS]:
        values = frame[name].astype("int64")
        lower, upper = (0, 125) if name == "EDAD" else (0, 0) if name == "NS" else (0, 20)
        stats[name] = dict(q1=0, q3=0, lower_fence=lower, upper_fence=upper,
                           lower_outliers=int((values < lower).sum()), upper_outliers=int((values > upper).sum()),
                           total=int(values.sum()), zero_count=int((values == 0).sum()))
    return stats


def create_fixture(root):
    """Prepara seis años y dos entidades con ceros iniciales y vacíos distintos."""
    reports = root / "analysis/reports"
    reports.mkdir(parents=True)
    (root / "analysis/scripts").mkdir()
    (root / "data/raw").mkdir(parents=True)
    for relative in ["analysis/cleaning_plan.md", "analysis/reports/initial_audit.md", "analysis/scripts/clean_data.py"]:
        (root / relative).write_text("Fuente sintética aislada para las pruebas.", encoding="utf-8")
    for year in YEARS:
        path = root / f"data/raw/fixture_{year}.zip"
        frames = [sample_frame(year, state) for state in ("01", "02")]
        files = []
        with zipfile.ZipFile(path, "w") as archive:
            for index, frame in enumerate(frames):
                member = f"folder/state_{index}.csv"
                archive.writestr(member, frame.to_csv(index=False).encode("utf-8-sig"))
                files.append(dict(member=member, rows=len(frame), states=frame["EDOCVE"].iloc[0]))
        combined = pd.concat(frames, ignore_index=True)
        checksum = file_hash(path)
        audit = dict(year=year, archive=path.name, sha256_before=checksum, sha256_after=checksum,
                     rows=len(combined), files=files, dictionaries=[], statistics=sample_statistics(combined),
                     checks=dict(equation_mismatch=0, equation_unevaluable=0),
                     profiles=[dict(column=name, missing=int(combined[name].str.strip().eq("").sum())) for name in ORIGINAL_COLUMNS])
        (reports / f"audit_{year}.json").write_text(json.dumps(audit), encoding="utf-8")


class CleaningChecks(unittest.TestCase):
    def test_original_tokens_typed_counts_and_flags(self):
        frame = sample_frame(2024)
        table, _ = transform_chunk(frame, 2024, "fixture.zip", "folder/member.csv", "a" * 64, 10, sample_statistics(frame))
        self.assertTrue(table.schema.equals(output_schema(), check_metadata=True))
        self.assertEqual(table.select(ORIGINAL_COLUMNS).to_pydict(), frame.to_dict(orient="list"))
        self.assertEqual(table["local_district_code"].to_pylist(), [None, "1", "1"])
        self.assertEqual(table["local_district_missing_reason"].to_pylist(), ["empty_string", None, None])
        self.assertEqual(table["source_record"].to_pylist(), [11, 12, 13])
        self.assertEqual(table["age_iqr_outlier"].to_pylist(), [False, False, True])
        self.assertEqual(table["age_over_100"].to_pylist(), [False, True, True])
        self.assertEqual(table["ns_iqr_outlier"].to_pylist(), [True, False, False])
        self.assertEqual(table["SEXO"].to_pylist(), ["0", "0", "2"])
        self.assertEqual(table["not_voted_count"].to_pylist(), [0, 2, 0])
        self.assertEqual(table["municipality_name_label"].to_pylist(), ["Bacalar"] * 3)
        self.assertEqual(table["EDOCVE"].to_pylist(), ["01"] * 3)
        self.assertEqual(table["MPIOCVE"].to_pylist(), ["001"] * 3)
        self.assertEqual(table["district_reference_year"].to_pylist(), [2023] * 3)
        old = sample_frame(2009)
        stored, _ = transform_chunk(old, 2009, "fixture.zip", "member.csv", "a" * 64, 0, sample_statistics(old))
        self.assertEqual(stored["federal_district_missing_reason"].to_pylist(), ["blank_space", None, None])
        self.assertEqual(stored["DEF"].to_pylist()[0], " ")
        self.assertEqual(stored["district_reference_year"].to_pylist(), [2021] * 3)

    def test_invalid_counts_are_not_coerced_or_repaired(self):
        for token in ("", "1.5", "-1", "9223372036854775808"):
            frame = sample_frame(2024)
            frame.loc[0, "LN"] = token
            with self.subTest(token=token), self.assertRaises(ValidationError):
                transform_chunk(frame, 2024, "fixture.zip", "member.csv", "a" * 64, 0, sample_statistics(sample_frame(2024)))
        frame = sample_frame(2024)
        frame.loc[0, "SV"] = "4"
        with self.assertRaisesRegex(ValidationError, "LN != SV"):
            transform_chunk(frame, 2024, "fixture.zip", "member.csv", "a" * 64, 0, sample_statistics(frame))

    def test_parquet_mutation_is_detected(self):
        frame = sample_frame(2024)
        expected, _ = transform_chunk(frame, 2024, "fixture.zip", "member.csv", "a" * 64, 0, sample_statistics(frame))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "part.parquet"
            changed = expected.set_column(expected.schema.get_field_index("voted_count"), expected.schema.field("voted_count"), pa.array([4, 0, 1], type=pa.int64()))
            pq.write_table(changed, path)
            with self.assertRaises(ValidationError):
                verify_part(path, expected)

    def test_full_run_is_lossless_and_independent_of_chunk_size(self):
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(io.StringIO()):
            root = Path(temporary)
            create_fixture(root)
            first = root / "data/processed/first"
            second = root / "data/processed/second"
            first_run = run_cleaning(root, first, chunk_size=1, expected_total=36)
            second_run = run_cleaning(root, second, chunk_size=2, expected_total=36)
            self.assertEqual(first_run["rows"], 36)
            self.assertEqual(first_run["state_partitions"], 12)
            one = open_dataset(first).to_table().sort_by([(key, "ascending") for key in ("source_archive", "source_member", "source_record")])
            two = open_dataset(second).to_table().sort_by([(key, "ascending") for key in ("source_archive", "source_member", "source_record")])
            self.assertTrue(one.equals(two))
            self.assertEqual(one.schema.field("state_code").type, pa.string())
            self.assertEqual(set(one["state_code"].to_pylist()), {"01", "02"})
            self.assertEqual(first_run["yearly_summary"][2024]["sex_2_rows"], 2)
            self.assertEqual(first_run["yearly_summary"], second_run["yearly_summary"])
            for source in first_run["sources"]:
                self.assertEqual(source["sha256_before"], source["sha256_after"])
            with self.assertRaises(ValidationError):
                run_cleaning(root, first, expected_total=36)
            self.assertTrue((first / "_SUCCESS").is_file())

    def test_changed_zip_produces_incident_and_no_success_marker(self):
        with tempfile.TemporaryDirectory() as temporary, redirect_stdout(io.StringIO()):
            root = Path(temporary)
            create_fixture(root)
            path = root / "data/raw/fixture_2009.zip"
            with path.open("ab") as stream:
                stream.write(b"changed")
            output = root / "data/processed/failed"
            with self.assertRaises(ValidationError):
                run_cleaning(root, output, expected_total=36)
            self.assertFalse((output / "_SUCCESS").exists())
            manifest = json.loads((output / "metadata/run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(len(manifest["errors"]), 1)
            with self.assertRaises(ValidationError):
                open_dataset(output)


if __name__ == "__main__":
    unittest.main()
