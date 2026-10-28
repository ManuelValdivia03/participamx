"""Genera una revisión editorial independiente a partir de los agregados validados."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "data/processed/participamx_multiyear/elections/2024"
PRIOR = ROOT / "analysis/profile_v2/results"
DEFAULT_OUTPUT = ROOT / "analysis/profile_v2/editorial/results"
COUNTS = ["LN", "SV", "NV", "NS", "source_row_count", "sex_2_source_rows", "sex_2_nominal_count"]
KEYS = ["EDOCVE", "MPIOCVE", "age_band", "SEXO"]
ORDER = ["young_favorable", "young_unfavorable", "adult_favorable", "adult_unfavorable", "older_favorable", "older_unfavorable"]
SEX = {"0": "Hombres", "1": "Mujeres"}
SECTION = {"U": "Urbana", "R": "Rural", "M": "Mixta"}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def exact_direction(sv, denominator, national_sv, national_denominator):
    if int(denominator) == 0 or int(national_denominator) == 0:
        return None
    difference = int(sv) * int(national_denominator) - int(national_sv) * int(denominator)
    return (difference > 0) - (difference < 0)


def aggregate(group):
    d = int(group.specified_count.sum())
    ref = float((group.specified_count * group.reference_age_sex).sum() / d) if d else None
    rate = float(group.SV.sum() / d) if d else None
    eligible = group[group.is_eligible]
    flips = eligible[eligible.exact_sign_opposes_parent]
    return {
        **{k: int(group[k].sum()) for k in COUNTS}, "specified_count": d,
        "joint_cells": len(group), "municipalities": group.municipal_id.nunique(),
        "defined_cells": int(group.participation_observed.notna().sum()),
        "undefined_cells": int(group.participation_observed.isna().sum()),
        "undefined_LN": int(group.loc[group.participation_observed.isna(), "LN"].sum()),
        "participation_observed": rate, "matched_age_sex_reference": ref,
        "delta_pp": (rate - ref) * 100 if d else None,
        "unspecified_rate": float(group.NS.sum() / group.LN.sum()),
        "eligible_cells": len(eligible), "eligible_LN": int(eligible.LN.sum()),
        "eligible_flip_cells": len(flips), "eligible_flip_LN": int(flips.LN.sum()),
        "eligible_flip_fraction": len(flips) / len(eligible) if len(eligible) else None,
        "eligible_flip_nominal_fraction": float(flips.LN.sum() / eligible.LN.sum()) if len(eligible) else None,
        "all_defined_flip_cells": int(group.exact_sign_opposes_parent.sum()),
        "high_ns_cells": int(group.high_ns.sum()),
        "eligible_high_ns_cells": int(eligible.high_ns.sum()),
    }


def build_evidence(parents, children, references, published):
    assert not parents.duplicated(KEYS).any()
    assert not children.duplicated(KEYS + ["TIPOSEC"]).any()
    assert parents.SEXO.map(type).eq(str).all() and children.EDOCVE.map(type).eq(str).all()
    original_counts = parents[COUNTS].sum()
    pd.testing.assert_series_equal(original_counts, children[COUNTS].sum(), check_names=False)
    assert int(original_counts.LN) == 98330348
    assert int(original_counts.source_row_count) == 9773730
    assert int(children.loc[children.SEXO.eq("2"), "LN"].sum()) == 105
    assert (children.LN == children.SV + children.NV + children.NS).all()
    assert (children.specified_count == children.SV + children.NV).all()
    assert children.participation_observed.isna().equals(children.specified_count.eq(0))
    national = children.groupby(["age_band", "SEXO"])[["SV", "specified_count"]].sum()
    for r in references.itertuples():
        a = national.loc[(r.age_band, r.SEXO)]
        assert int(a.SV) == int(r.SV) and int(a.specified_count) == int(r.national_specified_count)
    selected = parents[parents.candidate_id.notna()].copy()
    assert len(selected) == 14190 and int(selected.LN.sum()) == 98203780
    # Todos los hijos de cada padre V1; no se seleccionan solamente hijos con soporte.
    joint = children.merge(selected[KEYS + ["row_id", "candidate_id", "direction", "national_SV", "national_specified_count"]],
                           on=KEYS, how="inner", validate="many_to_one", suffixes=("", "_parent"))
    assert joint.v1_parent_profile.eq(joint.candidate_id).all()
    joint["exact_child_direction"] = pd.array([
        exact_direction(r.SV, r.specified_count, r.national_SV, r.national_specified_count)
        for r in joint.itertuples()], dtype="Int8")
    joint["exact_sign_opposes_parent"] = (joint.exact_child_direction * joint.direction).lt(0).fillna(False)
    assert joint.exact_sign_opposes_parent.eq(joint.split_sign_opposes_parent).all()
    assert int(joint.loc[joint.is_eligible, "exact_sign_opposes_parent"].sum()) == 2704
    assert len(joint[joint.is_eligible]) == 31470
    assert np.allclose(joint.reference_age_sex, joint.national_SV / joint.national_specified_count, atol=1e-14)
    assert np.allclose(joint.loc[joint.specified_count.gt(0), "participation_observed"],
                       (joint.SV / joint.specified_count)[joint.specified_count.gt(0)], atol=1e-14)
    tables = {"profile_summary": [], "profile_sex": [], "profile_section": [], "profile_sex_section": [],
              "profile_state": [], "reversal_quality": [], "parent_reconciliation": []}
    for profile_id in ORDER:
        p = selected[selected.candidate_id.eq(profile_id)]
        j = joint[joint.candidate_id.eq(profile_id)]
        record = dict(published[profile_id])
        summary = aggregate(j)
        for key in COUNTS:
            assert int(p[key].sum()) == summary[key] == int(record[key])
            tables["parent_reconciliation"].append({"profile_id": profile_id, "field": key,
                "parent_value": int(p[key].sum()), "joint_value": summary[key], "published_value": int(record[key]), "difference": 0})
        assert np.isclose(summary["participation_observed"], record["participation_observed"])
        assert np.isclose(summary["matched_age_sex_reference"], record["matched_peer_reference"])
        summary.update({"profile_id": profile_id, "age_band": record["age_band"],
            "parent_segments": len(p), "states": p.EDOCVE.nunique(), "delta_sd_pp": float(p.participation_delta.std(ddof=0) * 100),
            "delta_q1_pp": record["delta_q1"] * 100, "delta_median_pp": record["delta_median"] * 100,
            "delta_q3_pp": record["delta_q3"] * 100,
            "near_reference_parent_fraction": record["near_reference_fraction"],
            "high_ns_parent_fraction": record["high_ns_fraction"],
            "women_segment_fraction": record["women_segment_fraction"], "women_nominal_fraction": record["women_nominal_fraction"]})
        for t in SECTION:
            summary[f"nominal_share_{t}"] = float(j.loc[j.TIPOSEC.eq(t), "LN"].sum() / j.LN.sum())
            assert np.isclose(summary[f"nominal_share_{t}"], record[f"nominal_share_{t}"])
        tables["profile_summary"].append(summary)
        for columns, name in [(["SEXO"], "profile_sex"), (["TIPOSEC"], "profile_section"),
                              (["SEXO", "TIPOSEC"], "profile_sex_section"), (["EDOCVE", "state_name_label"], "profile_state")]:
            for keys, group in j.groupby(columns, sort=True):
                row = {"profile_id": profile_id, **dict(zip(columns, keys)), **aggregate(group)}
                row["share_of_profile_LN"] = row["LN"] / int(p.LN.sum())
                if name == "profile_state":
                    state_core = parents[parents.EDOCVE.eq(row["EDOCVE"]) & parents.in_scope]
                    row["state_core_LN"] = int(state_core.LN.sum())
                    row["share_of_state_core_LN"] = row["LN"] / row["state_core_LN"]
                tables[name].append(row)
        for status, group in [("all_children", j), ("eligible_children", j[j.is_eligible]),
                              ("pending_children", j[~j.is_eligible])]:
            f = group[group.exact_sign_opposes_parent]
            tables["reversal_quality"].append({"profile_id": profile_id, "population": status,
                "joint_cells": len(group), "LN": int(group.LN.sum()), "defined_cells": int(group.specified_count.gt(0).sum()),
                "flip_cells": len(f), "flip_LN": int(f.LN.sum()),
                "flip_near_reference_cells": int(f.delta_age_sex.abs().le(.02).sum()),
                "flip_parent_near_reference_cells": int(f.v1_parent_delta.abs().le(.02).sum()),
                "flip_high_ns_cells": int(f.high_ns.sum()), "flip_few_sections_cells": int(f.few_sections.sum())})
    return joint, {k: pd.DataFrame(v) for k, v in tables.items()}


def table_markdown(frame, columns):
    def fmt(v):
        if v is None or pd.isna(v):
            return "No definida"
        return f"{v:.2f}" if isinstance(v, (float, np.floating)) else str(v)
    return "| " + " | ".join(columns) + " |\n| " + " | ".join(["---"] * len(columns)) + " |\n" + "\n".join(
        "| " + " | ".join(fmt(row[c]) for c in columns) + " |" for row in frame.to_dict("records"))


def protected_snapshot(output):
    roots = [ROOT / "src", ROOT / "public", ROOT / "docs/perfiles", ROOT / "analysis/profile_v2",
             ROOT / "data/processed/participamx_multiyear"]
    files = {p for root in roots for p in root.rglob("*") if p.is_file() and output not in p.parents
             and "__pycache__" not in p.parts and ".cache" not in p.parts}
    files.update([ROOT / "package.json", ROOT / ".gitignore"])
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(files)}


def verify_prior():
    assert (PRIOR / "_SUCCESS").is_file()
    manifest = json.loads((PRIOR / "metadata/run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "validated"
    checked = {}
    for name, value in manifest["artifacts"].items():
        path = PRIOR / name.replace("\\", "/")
        assert digest(path) == value, f"Resultado previo alterado: {path}"
        checked[path.relative_to(ROOT).as_posix()] = value
    for name, value in manifest["source_hashes"].items():
        path = ROOT / name.replace("\\", "/")
        if "/2024/" in path.as_posix():
            assert digest(path) == value, f"Fuente alterada: {path}"
            checked[path.relative_to(ROOT).as_posix()] = value
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "analysis/profile_v2/editorial"):
        raise ValueError("El destino debe estar dentro del espacio editorial nuevo")
    if output.exists():
        raise FileExistsError("Destino existente: use --output con una ruta nueva")
    protected = protected_snapshot(output)
    verified = verify_prior()
    print(f"Integridad previa: {len(protected)} archivos protegidos; {len(verified)} huellas previas verificadas", flush=True)
    parents = pd.read_parquet(BASE / "tables/segments.parquet")
    children = pd.read_parquet(PRIOR / "reference/all_observations.parquet")
    references = pd.read_parquet(BASE / "tables/national_references.parquet")
    published = {r["profile_id"]: r for r in json.loads((BASE / "profiles.json").read_text(encoding="utf-8"))["data"]}
    joint, tables = build_evidence(parents, children, references, published)
    output.mkdir(parents=True)
    evidence = output / "evidence"
    evidence.mkdir()
    for name, frame in tables.items():
        frame.to_csv(evidence / f"{name}.csv", index=False, encoding="utf-8")
    reference_path = evidence / "child_trace.parquet"
    joint.to_parquet(reference_path, index=False)
    pd.testing.assert_frame_equal(joint, pd.read_parquet(reference_path))
    reversal = joint[joint.is_eligible & joint.exact_sign_opposes_parent].copy()
    reversal.to_parquet(evidence / "eligible_sign_reversals.parquet", index=False)
    examples = reversal.sort_values(["candidate_id", "LN", "row_id"], ascending=[True, False, True]).groupby("candidate_id").head(1)
    examples.to_csv(evidence / "reversal_examples.csv", index=False, encoding="utf-8")
    # Importación local: el contenido editorial se mantiene separado de los cálculos.
    from naming_content import render_deliverables
    payload = render_deliverables(output, tables, published, examples)
    validate_payload(payload, tables)
    write_json(output / "experimental_profile_names_2024.json", payload)
    for name, value in protected.items():
        assert digest(ROOT / name) == value, f"Archivo protegido alterado: {name}"
    manifest = {"status": "validated", "experimental": True, "election_year": 2024,
        "model_fits": 0, "original_CSV_reads": 0, "protected_files": len(protected),
        "protected_hashes": protected, "verified_prior_hashes": verified,
        "script_hashes": {p.relative_to(ROOT).as_posix(): digest(p) for p in Path(__file__).parent.glob("*.py")},
        "artifacts": {p.relative_to(output).as_posix(): digest(p) for p in sorted(output.rglob("*")) if p.is_file()},
        "validation": {"profiles": 6, "name_proposals": 18, "parent_segments": 14190,
            "eligible_child_cells": 31470, "eligible_sign_reversals": 2704,
            "additive_reconciliations": len(tables["parent_reconciliation"]), "descriptions_words":
                {r["profile_id"]: len(r["description"].split()) for r in payload["profiles"]}}}
    write_json(output / "metadata/run_manifest.json", manifest)
    (output / "_SUCCESS").write_text("Revisión editorial y conciliaciones verificadas; sin publicación.\n", encoding="utf-8")
    print(json.dumps(manifest["validation"], ensure_ascii=False), flush=True)


def validate_payload(payload, tables):
    profiles = payload["profiles"]
    assert [p["profile_id"] for p in profiles] == ORDER
    assert len({p["recommended_name"] for p in profiles}) == 6
    assert len(profiles) == 6
    forbidden = ["participación esperada", "ciudadanos comprometidos", "jóvenes apáticos", "electores difíciles", "votantes persuadibles",
                 "participación superior a sus pares", "participación inferior a sus pares", "grupo favorable", "grupo desfavorable"]
    for profile in profiles:
        assert 40 <= len(profile["description"].split()) <= 70
        assert len(profile["findings"]) == 3
        assert len(profile["name_proposals"]) == 3
        for proposal in profile["name_proposals"]:
            assert 4 <= len(proposal["name"].split()) <= 9
            assert all(proposal[key] for key in ["subtitle", "distinctive_feature", "statistical_justification", "sources", "limitation"])
            assert all(source in payload["sources"] for source in proposal["sources"])
            assert not any(term in proposal["name"].lower() for term in forbidden)
        assert profile["recommended_name"] == profile["name_proposals"][0]["name"]
        assert len(profile["joint_age_sex_section"]) == 6
        assert profile["statistics"]["LN"] == int(tables["profile_summary"].set_index("profile_id").loc[profile["profile_id"], "LN"])
    json.dumps(clean(payload), ensure_ascii=False, allow_nan=False)


if __name__ == "__main__":
    main()
