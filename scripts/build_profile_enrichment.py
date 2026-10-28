"""Transforma resultados validados de 2024 al contrato público de perfiles, sin nuevos modelos."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "public/data/profiles/enriched-2024.json"
EDITORIAL = ROOT / "analysis/profile_v2/editorial/results"
PATTERNS = ROOT / "analysis/profile_v2/patterns/results"
NAMES = {
    "young_favorable": ("Jóvenes con mayor participación", "La diferencia positiva agregada más amplia de las seis fichas: +7.69 pp."),
    "young_unfavorable": ("Jóvenes con menor participación", "La participación absoluta más baja de las seis fichas: 43.26 %."),
    "adult_favorable": ("Adultos con mayor participación", "La presencia más extensa de las seis fichas: 1,641 municipios."),
    "adult_unfavorable": ("Adultos con menor participación", "El mayor volumen de las seis fichas: LN de 22,444,975."),
    "older_favorable": ("Personas mayores con mayor participación", "La participación absoluta más alta de las seis fichas: 77.26 %."),
    "older_unfavorable": ("Personas mayores con menor participación", "La diferencia negativa agregada más amplia: −7.34 pp frente a su referencia."),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_validated(folder, relative):
    manifest = json.loads((folder / "metadata/run_manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "validated" or not (folder / "_SUCCESS").exists():
        raise ValueError(f"Entrega sin validar: {folder}")
    source = folder / relative
    assert digest(source) == manifest["artifacts"][relative]
    return json.loads(source.read_text(encoding="utf-8"))


def cell(source, code):
    # Los indicadores y denominadores se copian; sólo se transforma el formato de consumo.
    rate = source["participation_observed"]
    status = "undefined" if source["specified_count"] == 0 else "low_support" if (
        source["LN"] < 100 or source["specified_count"] < 100 or source["source_row_count"] < 5) else "defined"
    return {"code": code, "status": status, "LN": source["LN"], "SV": source["SV"], "NV": source["NV"], "NS": source["NS"],
        "specifiedCount": source["specified_count"], "sourceRows": source["source_row_count"],
        "nominalShare": source["share_of_profile_LN"], "participation": rate,
        "reference": source["matched_age_sex_reference"], "deltaPp": source["delta_pp"],
        "availableCells": source["joint_cells"], "eligibleCells": source["eligible_cells"], "undefinedCells": source["undefined_cells"]}


def build():
    editorial = read_validated(EDITORIAL, "experimental_profile_names_2024.json")
    patterns = read_validated(PATTERNS, "candidates/experimental_patterns.json")
    reversals = read_validated(PATTERNS, "sign_reversals/summary.json")
    published_path = ROOT / "public/data/participamx_multiyear/elections/2024/profiles.json"
    published = {p["profile_id"]: p for p in json.loads(published_path.read_text(encoding="utf-8"))["data"]}
    profiles = []
    for source in editorial["profiles"]:
        profile_id = source["profile_id"]
        stats = source["statistics"]
        original = published[profile_id]
        assert stats["LN"] == original["LN"] and stats["parent_segments"] == original["segments"]
        assert abs(stats["participation_observed"] - original["participation_observed"]) < 1e-12
        name, distinctive = NAMES[profile_id]
        direction = "por debajo" if profile_id.endswith("unfavorable") else "por encima"
        profiles.append({"id": profile_id, "name": name, "ageBand": stats["age_band"],
            "subtitle": f"{stats['age_band'].replace('-', '–')} años · participación {direction} de la referencia de su misma banda y sexo.",
            "description": source["description"], "distinctive": distinctive, "nameStatus": "agreed",
            "participation": original["participation_observed"], "reference": original["matched_peer_reference"],
            "deltaPp": stats["delta_pp"], "nominalShare": original["nominal_coverage"],
            "counts": {k: stats[k] for k in ["LN", "SV", "NV", "NS", "specified_count", "source_row_count"]},
            "segments": stats["parent_segments"], "municipalities": stats["municipalities"], "states": stats["states"],
            "findings": [distinctive, source["findings"][1]["text"]],
            "sexAnalysis": source["sex_analysis"], "sectionAnalysis": source["section_analysis"],
            "territoryAnalysis": source["territorial_observation"],
            "sexCells": [cell(c, c["SEXO"]) for c in source["sex_statistics"]],
            "sectionCells": [cell(c, c["TIPOSEC"]) for c in source["section_statistics"]],
            "jointCells": [{**cell(c, c["TIPOSEC"]), "sexCode": c["SEXO"]} for c in source["joint_age_sex_section"]],
            "quality": {"nearReferenceShare": stats["near_reference_parent_fraction"], "highNsShare": stats["high_ns_parent_fraction"],
                "availableCells": stats["joint_cells"], "eligibleCells": stats["eligible_cells"], "undefinedCells": stats["undefined_cells"],
                "signReversals": stats["eligible_flip_cells"], "reversalShare": stats["eligible_flip_fraction"],
                "reversalLN": stats["eligible_flip_LN"], "reversalNominalShare": stats["eligible_flip_nominal_fraction"]},
            "additionalCategory": {"code": "2", "status": "low_support", "value": None,
                "explanation": "SEXO=2 se conserva en la referencia de 2024 (LN=105). Su soporte no permite incorporarlo a estas fichas H/M; no se reparte entre hombres y mujeres."},
            "sourceRefs": ["v1", "editorial", "v2", "v21"]})
    assert len(profiles) == 6 and {p["id"] for p in profiles} == set(NAMES)
    assert sum(p["quality"]["signReversals"] for p in profiles) == 2704
    accepted = patterns["profiles"]
    assert len(accepted) == 1 and accepted[0]["statistics"]["passes_screen"]
    pattern = accepted[0]
    finding = {"id": pattern["pattern_id"], "year": 2024, "title": "La brecha entre mujeres y hombres cambia entre secciones rurales y urbanas",
        "ageBand": pattern["age_band"], "municipalContrastPp": pattern["statistics"]["equal_municipality_pp"],
        "nominalContrastPp": pattern["statistics"]["nominal_pp"], "municipalities": pattern["statistics"]["municipalities"],
        "directionShare": pattern["statistics"]["municipality_same_sign_fraction"],
        "annualNominalShare": pattern["statistics"]["annual_LN_fraction"], "LN": pattern["statistics"]["LN"],
        "specifiedCount": pattern["statistics"]["specified_count"], "sourceRefs": ["v21"]}
    sources = {
        "v1": "data/processed/participamx_multiyear/elections/2024/profiles.json",
        "v2": "analysis/profile_v2/results/reference/all_observations.parquet",
        "editorial": "analysis/profile_v2/editorial/results/experimental_profile_names_2024.json",
        "v21": "analysis/profile_v2/patterns/results/candidates/experimental_patterns.json",
        "reversals": "analysis/profile_v2/patterns/results/sign_reversals/summary.json"}
    hashes = {key: digest(ROOT / path) for key, path in sources.items()}
    return {"schemaVersion": "profiles-enriched-1", "year": 2024, "rateUnit": "proportion", "namesStatus": "agreed",
        "profiles": profiles, "transversalFinding": finding,
        "heterogeneity": {"eligibleCells": reversals["eligible"]["segments"], "signReversals": reversals["reversals"]["segments"],
            "bothBeyond2Pp": reversals["both_beyond_2pp"], "unit": "municipality_age_band_sex_section_type"},
        "sources": {key: {"path": path, "sha256": hashes[key]} for key, path in sources.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = json.dumps(build(), ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    if args.check:
        assert TARGET.read_text(encoding="utf-8") == content, "Regenerar el archivo de consumo de perfiles"
        print("Perfiles enriquecidos: seis IDs, conteos y fuentes verificados")
    else:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(content, encoding="utf-8")
        print(TARGET.relative_to(ROOT))


if __name__ == "__main__":
    main()
