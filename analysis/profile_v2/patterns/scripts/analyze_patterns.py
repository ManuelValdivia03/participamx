"""Contrastes multivariables descriptivos V2.1, sin ajustar clustering."""
from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
HOME = ROOT / "analysis/profile_v2/patterns"
PRIOR = ROOT / "analysis/profile_v2/results"
BASE = ROOT / "data/processed/participamx_multiyear/elections/2024"
OUTPUT = HOME / "results"
BANDS = ["18-34", "35-59", "60-100"]
COUNTS = ["LN", "SV", "NV", "NS", "source_row_count", "sex_2_source_rows", "sex_2_nominal_count"]
ESTIMANDS = ["equal_municipality", "nominal", "pooled_counts"]
SEED = 28102026
BOOTSTRAPS = 1000


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def clean(value):
    if value is None or value is pd.NA:
        return None
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def save(output, name, frame):
    path = output / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        frame.to_parquet(path, index=False)
        pd.testing.assert_frame_equal(frame.reset_index(drop=True), pd.read_parquet(path))
    else:
        frame.to_csv(path, index=False, encoding="utf-8")


def exact_direction(sv, d, national_sv, national_d):
    if int(d) == 0 or int(national_d) == 0:
        return None
    v = int(sv) * int(national_d) - int(national_sv) * int(d)
    return (v > 0) - (v < 0)


def eligible(frame, threshold=100, source_rows=5):
    return (frame.age_band.isin(BANDS) & frame.SEXO.isin(["0", "1"]) & frame.LN.ge(threshold)
            & frame.specified_count.ge(threshold) & frame.source_row_count.ge(source_rows))


def load_inputs():
    original = pd.read_parquet(PRIOR / "reference/all_observations.parquet")
    parents = pd.read_parquet(BASE / "tables/segments.parquet")
    municipalities = pd.read_parquet(BASE / "tables/municipalities.parquet")
    assert len(original) == 38805 and len(municipalities) == 2477
    assert not original.row_id.duplicated().any()
    assert not original.duplicated(["EDOCVE", "MPIOCVE", "age_band", "SEXO", "TIPOSEC"]).any()
    pd.testing.assert_series_equal(original[COUNTS].sum(), parents[COUNTS].sum(), check_names=False)
    assert int(original.LN.sum()) == 98330348
    assert (original.LN == original.SV + original.NV + original.NS).all()
    assert (original.specified_count == original.SV + original.NV).all()
    assert original.participation_observed.isna().equals(original.specified_count.eq(0))
    assert original.is_eligible.equals(eligible(original))
    refs = original.groupby(["age_band", "SEXO"], as_index=False)[COUNTS].sum()
    refs["national_D"] = refs.SV + refs.NV
    refs["national_rate"] = refs.SV / refs.national_D
    refs = refs.rename(columns={"SV": "national_SV", "LN": "national_LN", "NS": "national_NS"})
    original = original.merge(refs[["age_band", "SEXO", "national_SV", "national_D", "national_rate", "national_LN", "national_NS"]],
                              on=["age_band", "SEXO"], how="left", validate="many_to_one")
    keys = ["EDOCVE", "MPIOCVE", "age_band", "SEXO"]
    original = original.merge(parents[keys + ["direction", "candidate_id", "specified_count"]].rename(
        columns={"direction": "parent_direction", "candidate_id": "v1_profile_id", "specified_count": "parent_D"}),
        on=keys, how="left", validate="many_to_one")
    assert np.allclose(original.reference_age_sex, original.national_rate, equal_nan=True)
    original["exact_direction"] = pd.array([exact_direction(r.SV, r.specified_count, r.national_SV, r.national_D)
                                             for r in original.itertuples()], dtype="Int8")
    original["sign_reversal"] = ((original.exact_direction * original.parent_direction).lt(0)
                                   & original.v1_profile_id.notna()).fillna(False)
    assert int((original.sign_reversal & original.is_eligible).sum()) == 2704
    e = original[original.is_eligible]
    assert len(e) == 31470 and e.municipal_id.nunique() == 2392 and int(e.LN.sum()) == 97999677
    municipalities["municipal_id"] = municipalities.EDOCVE + "|" + municipalities.MPIOCVE
    assert municipalities.municipal_id.nunique() == 2477
    return original, parents, municipalities, refs


def count_summary(frame):
    d = int(frame.specified_count.sum())
    return {"segments": len(frame), "municipalities": frame.municipal_id.nunique(), "states": frame.EDOCVE.nunique(),
            **{k: int(frame[k].sum()) for k in COUNTS}, "specified_count": d,
            "participation_observed": float(frame.SV.sum() / d) if d else None,
            "undefined": int(frame.specified_count.eq(0).sum()), "high_ns": int(frame.high_ns.sum()),
            "few_sections": int(frame.few_sections.sum())}


def national_tables(original):
    core = original[original.age_band.isin(BANDS) & original.SEXO.isin(["0", "1"])]
    result = {}
    for name, keys in [("age_sex_section", ["age_band", "SEXO", "TIPOSEC"]), ("age_sex", ["age_band", "SEXO"]),
                       ("age_section", ["age_band", "TIPOSEC"]), ("sex_section", ["SEXO", "TIPOSEC"])]:
        rows = []
        for values, group in core.groupby(keys):
            row = dict(zip(keys, values))
            row.update(count_summary(group))
            e = group[group.is_eligible]
            row.update({"eligible_segments": len(e), "eligible_municipalities": e.municipal_id.nunique(),
                        "eligible_LN": int(e.LN.sum()), "eligible_nominal_fraction": float(e.LN.sum() / group.LN.sum())})
            rows.append(row)
        result[name] = pd.DataFrame(rows)
    # Estandarización descriptiva por edad: mismos pesos nacionales D de las tres bandas en todos los cruces sexo/tipo.
    weights = core.groupby("age_band").specified_count.sum()
    weights = weights / weights.sum()
    rows = []
    for (sex, section), group in result["age_sex_section"].groupby(["SEXO", "TIPOSEC"]):
        crude = result["sex_section"].query("SEXO == @sex and TIPOSEC == @section").iloc[0]
        rows.append({"SEXO": sex, "TIPOSEC": section, "crude_rate": crude.participation_observed,
            "age_standardized_rate": sum(r.participation_observed * weights[r.age_band] for r in group.itertuples()),
            "age_weights": json.dumps(weights.to_dict()), "source": "all_original_before_support"})
    result["age_standardized_sex_section"] = pd.DataFrame(rows)
    result["quality_by_state"] = pd.DataFrame([{"EDOCVE": code, **count_summary(g),
        "eligible_segments": int(g.is_eligible.sum()), "eligible_LN": int(g.loc[g.is_eligible, "LN"].sum())}
        for code, g in original.groupby("EDOCVE")])
    return result


def matched_block(frame, components, contrast_id, family, band, section):
    """Cada componente=(sexo,tipo,signo); unión interior conserva sólo municipios comparables."""
    keys = ["municipal_id", "EDOCVE", "MPIOCVE"]
    fields = ["row_id", "LN", "SV", "NV", "NS", "specified_count", "source_row_count", "section_count", "high_ns"]
    block = None
    for n, (sex, typ, coefficient) in enumerate(components):
        subset = frame[frame.age_band.eq(band) & frame.SEXO.eq(sex) & frame.TIPOSEC.eq(typ)][keys + fields]
        subset = subset.rename(columns={k: f"{k}_{n}" for k in fields})
        block = subset if block is None else block.merge(subset, on=keys, how="inner", validate="one_to_one")
    block = block.copy()
    block["contrast_id"] = contrast_id
    block["family"] = family
    block["age_band"] = band
    block["section_contrast"] = section
    block["components"] = json.dumps(components)
    block["interaction_pp"] = 0.0
    for n, (_, _, sign) in enumerate(components):
        block["interaction_pp"] += 100 * sign * block[f"SV_{n}"] / block[f"specified_count_{n}"]
    for field in ["LN", "SV", "NV", "NS", "specified_count", "source_row_count"]:
        block[field] = sum(block[f"{field}_{n}"] for n in range(len(components)))
    block["min_D"] = block[[f"specified_count_{n}" for n in range(len(components))]].min(axis=1)
    block["min_LN"] = block[[f"LN_{n}" for n in range(len(components))]].min(axis=1)
    block["min_sources"] = block[[f"source_row_count_{n}" for n in range(len(components))]].min(axis=1)
    block["min_sections"] = block[[f"section_count_{n}" for n in range(len(components))]].min(axis=1)
    block["max_ns"] = max_ns = np.zeros(len(block))
    for n in range(len(components)):
        max_ns = np.maximum(max_ns, block[f"NS_{n}"] / block[f"LN_{n}"])
    block["max_ns"] = max_ns
    return block


def build_contrasts(eligible_frame):
    blocks = []
    for band in BANDS:
        for typ in ["U", "R", "M"]:
            blocks.append(matched_block(eligible_frame, [("1", typ, 1), ("0", typ, -1)],
                f"sex_{band}_{typ}", "sex_gap", band, typ))
        for sex in ["0", "1"]:
            for typ in ["R", "M"]:
                blocks.append(matched_block(eligible_frame, [(sex, typ, 1), (sex, "U", -1)],
                    f"section_{band}_{sex}_{typ}_U", "section_gap", band, f"{typ}-U"))
        for typ in ["R", "M"]:
            blocks.append(matched_block(eligible_frame, [("1", typ, 1), ("0", typ, -1), ("1", "U", -1), ("0", "U", 1)],
                f"interaction_{band}_{typ}_U", "interaction", band, f"{typ}-U"))
    result = pd.concat(blocks, ignore_index=True)
    # Las comparaciones simples no tienen componentes 2/3: mantener booleanos NULL tipados al escribir Arrow.
    for column in result.columns:
        if column.startswith("high_ns_"):
            result[column] = result[column].astype("boolean")
    return result


def estimators(group, multiplicity=None):
    components = json.loads(group.components.iloc[0])
    m = np.ones(len(group)) if multiplicity is None else np.asarray(multiplicity, dtype=float)
    if m.sum() == 0:
        return np.full(3, np.nan)
    values = group.interaction_pp.to_numpy()
    equal = np.sum(m * values) / m.sum()
    nominal = np.sum(m * group.LN.to_numpy() * values) / np.sum(m * group.LN.to_numpy())
    pooled = 0.0
    for n, (_, _, sign) in enumerate(components):
        pooled += 100 * sign * np.sum(m * group[f"SV_{n}"].to_numpy()) / np.sum(m * group[f"specified_count_{n}"].to_numpy())
    return np.array([equal, nominal, pooled])


def contrast_summary(group):
    values = estimators(group)
    sign = np.sign(values[0])
    q = group.interaction_pp.quantile([.1, .25, .5, .75, .9]).tolist()
    state = group.groupby("EDOCVE").interaction_pp.agg(["size", "mean"])
    state = state[state["size"].ge(5)]
    result = {"contrast_id": group.contrast_id.iloc[0], "family": group.family.iloc[0], "age_band": group.age_band.iloc[0],
        "section_contrast": group.section_contrast.iloc[0], "municipalities": len(group), "states": group.EDOCVE.nunique(),
        "segments": len(group) * len(json.loads(group.components.iloc[0])),
        **{k: int(group[k].sum()) for k in COUNTS if k in group},
        "specified_count": int(group.specified_count.sum()), "annual_LN_fraction": float(group.LN.sum() / 98330348),
        "municipality_same_sign_fraction": float((group.interaction_pp * sign > 0).mean()),
        "state_same_sign_fraction": float((state["mean"] * sign > 0).mean()) if len(state) else np.nan,
        "states_with_five_pairs": len(state), "top_municipality_LN_fraction": float(group.LN.max() / group.LN.sum()),
        "top_ten_municipality_LN_fraction": float(group.LN.nlargest(10).sum() / group.LN.sum()),
        "min_D": int(group.min_D.min()), "median_min_D": float(group.min_D.median()),
        "high_ns_blocks": int(group.max_ns.ge(.1).sum()), "few_sections_blocks": int(group.min_sections.lt(5).sum()),
        "contrast_p10_pp": q[0], "contrast_q1_pp": q[1], "contrast_median_pp": q[2], "contrast_q3_pp": q[3], "contrast_p90_pp": q[4]}
    result.update({f"{key}_pp": v for key, v in zip(ESTIMANDS, values)})
    lower, upper = np.zeros(len(group)), np.zeros(len(group))
    for n, (_, _, coefficient) in enumerate(json.loads(group.components.iloc[0])):
        lo = group[f"SV_{n}"] / group[f"LN_{n}"]
        hi = (group[f"SV_{n}"] + group[f"NS_{n}"]) / group[f"LN_{n}"]
        lower += 100 * coefficient * (lo if coefficient > 0 else hi)
        upper += 100 * coefficient * (hi if coefficient > 0 else lo)
    result.update({"ns_extreme_municipal_low_pp": float(np.mean(lower)), "ns_extreme_municipal_high_pp": float(np.mean(upper)),
        "ns_extreme_nominal_low_pp": float(np.average(lower, weights=group.LN)),
        "ns_extreme_nominal_high_pp": float(np.average(upper, weights=group.LN))})
    return result


def age_changes(contrasts):
    """Contrastes de edad secundarios sobre exactamente los mismos municipios."""
    rows = []
    for family in ["interaction", "sex_gap"]:
        labels = ["R-U", "M-U"] if family == "interaction" else ["U", "R", "M"]
        for section in labels:
            for younger, older in [(BANDS[0], BANDS[1]), (BANDS[0], BANDS[2]), (BANDS[1], BANDS[2])]:
                a = contrasts[contrasts.family.eq(family) & contrasts.age_band.eq(younger) & contrasts.section_contrast.eq(section)]
                b = contrasts[contrasts.family.eq(family) & contrasts.age_band.eq(older) & contrasts.section_contrast.eq(section)]
                common = sorted(set(a.municipal_id) & set(b.municipal_id))
                a = a.set_index("municipal_id").loc[common].reset_index()
                b = b.set_index("municipal_id").loc[common].reset_index()
                delta = a.interaction_pp - b.interaction_pp
                values_a, values_b = estimators(a), estimators(b)
                weights = a.LN + b.LN
                rows.append({"family": family, "section_contrast": section, "younger": younger, "older": older,
                    "municipalities": len(common), "states": a.EDOCVE.nunique(), "LN": int(weights.sum()),
                    "equal_municipality_difference_pp": float(delta.mean()),
                    "nominal_difference_pp": float(np.average(delta, weights=weights)),
                    "pooled_count_difference_pp": values_a[2] - values_b[2],
                    "same_sign_fraction": float((delta * np.sign(delta.mean()) > 0).mean()),
                    "younger_equal_municipality_pp": values_a[0], "older_equal_municipality_pp": values_b[0]})
    return pd.DataFrame(rows)


def municipal_split(municipalities):
    rng = np.random.default_rng(SEED)
    pieces = []
    for _, group in municipalities.sort_values("municipal_id").groupby("EDOCVE"):
        group = group.copy()
        idx = rng.permutation(len(group))
        n = int(np.floor(.6 * len(group)))
        group["split"] = "confirmation"
        group.iloc[idx[:n], group.columns.get_loc("split")] = "discovery"
        pieces.append(group[["municipal_id", "EDOCVE", "MPIOCVE", "split"]])
    return pd.concat(pieces, ignore_index=True)


def joint_bootstrap(primary, municipalities, output):
    """Índices municipales comunes para las seis interacciones y sus tres estimandos."""
    ids = municipalities.municipal_id.sort_values().to_numpy()
    positions = {key: n for n, key in enumerate(ids)}
    groups = list(primary.groupby("contrast_id", sort=True))
    estimates = np.vstack([estimators(g) for _, g in groups])
    repeats = np.empty((BOOTSTRAPS, len(groups), 3))
    rng = np.random.default_rng(SEED + 1)
    membership = np.empty((BOOTSTRAPS, len(ids)), dtype=np.uint16)
    coverage = []
    for b in range(BOOTSTRAPS):
        counts = np.bincount(rng.integers(len(ids), size=len(ids)), minlength=len(ids))
        membership[b] = counts
        for n, (_, group) in enumerate(groups):
            m = counts[[positions[k] for k in group.municipal_id]]
            repeats[b, n] = estimators(group, m)
            coverage.append({"replicate": b, "contrast_id": groups[n][0], "drawn_municipalities": len(ids),
                "unique_active_municipalities": int((m > 0).sum()), "block_draws": int(m.sum()),
                "unique_LN": int(group.loc[m > 0, "LN"].sum()), "replicated_LN": int((m * group.LN).sum())})
    scale = repeats.std(axis=0, ddof=1)
    if not (scale > 0).all():
        raise ValueError("Distribución bootstrap degenerada")
    standardized = np.abs((repeats - estimates[None, :, :]) / scale[None, :, :])
    maxima = standardized.max(axis=(1, 2))
    critical = float(np.quantile(maxima, .95))
    rows = []
    for n, (contrast_id, _) in enumerate(groups):
        for j, name in enumerate(ESTIMANDS):
            rows.append({"contrast_id": contrast_id, "estimand": name, "estimate_pp": estimates[n, j],
                "bootstrap_scale_pp": scale[n, j], "simultaneous_low_pp": estimates[n, j] - critical * scale[n, j],
                "simultaneous_high_pp": estimates[n, j] + critical * scale[n, j],
                "bootstrap_same_sign_fraction": float((repeats[:, n, j] * estimates[n, j] > 0).mean()),
                "max_standardized_critical": critical, "family_size": len(groups) * 3, "replicates": BOOTSTRAPS})
    path = output / "resampling/municipal_bootstrap.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, municipal_ids=ids, multiplicities=membership, estimates=repeats,
                        contrast_ids=np.array([x[0] for x in groups]), max_standardized=maxima)
    save(output, "resampling/bootstrap_coverage.csv", pd.DataFrame(coverage))
    return pd.DataFrame(rows)


def sign_reversal_analysis(original, output):
    e = original[original.is_eligible]
    f = e[e.sign_reversal].copy()
    f["child_near_2pp"] = f.delta_age_sex.abs().le(.02)
    f["parent_near_2pp"] = f.v1_parent_delta.abs().le(.02)
    f["parent_D_fraction"] = f.specified_count / f.parent_D
    f["robust_fixed_reference"] = np.where(f.exact_direction.gt(0), f.SV / f.LN > f.national_rate,
                                                          (f.SV + f.NS) / f.LN < f.national_rate)
    f["robust_both_ns_bounds"] = np.where(f.exact_direction.gt(0), f.SV / f.LN > (f.national_SV + f.national_NS) / f.national_LN,
                                        (f.SV + f.NS) / f.LN < f.national_SV / f.national_LN)
    save(output, "sign_reversals/all_2704.parquet", f)
    for label, keys in [("joint", ["age_band", "SEXO", "TIPOSEC"]), ("age", ["age_band"]), ("sex", ["SEXO"]),
                        ("section", ["TIPOSEC"]), ("state", ["EDOCVE", "state_name_label"]),
                        ("municipality", ["municipal_id", "EDOCVE", "MPIOCVE"]), ("v1_profile", ["v1_profile_id"])]:
        rows = []
        for values, group in e.groupby(keys):
            flip = group[group.sign_reversal]
            row = {**dict(zip(keys, values)), "eligible_segments": len(group), "reversal_segments": len(flip),
                "reversal_segment_fraction": len(flip) / len(group), "eligible_municipalities": group.municipal_id.nunique(),
                "reversal_municipalities": flip.municipal_id.nunique(),
                "municipality_fraction_with_reversal": flip.municipal_id.nunique() / group.municipal_id.nunique(),
                "eligible_LN": int(group.LN.sum()), "reversal_LN": int(flip.LN.sum()),
                "reversal_nominal_fraction": float(flip.LN.sum() / group.LN.sum()),
                "eligible_D": int(group.specified_count.sum()), "reversal_D": int(flip.specified_count.sum()),
                "reversal_specified_fraction": float(flip.specified_count.sum() / group.specified_count.sum()),
                "child_abs_delta_median_pp": float(flip.delta_age_sex.abs().median() * 100) if len(flip) else None}
            rows.append(row)
        save(output, f"sign_reversals/by_{label}.csv", pd.DataFrame(rows))
    sensitivities = []
    cases = [(f"support_{threshold}_sources_5", eligible(original, threshold)) for threshold in [50, 100, 200, 500]]
    cases += [("support_100_sources_1", eligible(original, 100, 1)),
              ("low_ns", original.is_eligible & original.unspecified_rate.lt(.1)),
              ("five_sections", original.is_eligible & original.section_count.ge(5))]
    original_ids = set(f.row_id)
    for name, mask in cases:
        group = original[mask]
        flip = group[group.sign_reversal]
        old = flip[flip.row_id.isin(original_ids)]
        sensitivities.append({"scenario": name, "eligible_segments": len(group), "eligible_municipalities": group.municipal_id.nunique(),
            "eligible_LN": int(group.LN.sum()), "eligible_D": int(group.specified_count.sum()),
            "reversal_segments": len(flip), "reversal_segment_fraction": len(flip) / len(group),
            "reversal_municipalities": flip.municipal_id.nunique(), "reversal_LN": int(flip.LN.sum()), "reversal_D": int(flip.specified_count.sum()),
            "reversal_nominal_fraction": float(flip.LN.sum() / group.LN.sum()),
            "original_reversals_surviving": len(old), "surviving_fraction_of_2704": len(old) / 2704,
            "surviving_original_LN": int(old.LN.sum())})
    save(output, "sign_reversals/sensitivity.csv", pd.DataFrame(sensitivities))
    magnitudes = pd.DataFrame({"child_band": pd.cut(f.delta_age_sex.abs() * 100, [-np.inf, 2, 5, np.inf], labels=["<=2pp", "2to5pp", ">5pp"]),
        "parent_band": pd.cut(f.v1_parent_delta.abs() * 100, [-np.inf, 2, 5, np.inf], labels=["<=2pp", "2to5pp", ">5pp"]),
        "LN": f.LN, "specified_count": f.specified_count, "segments": 1})
    save(output, "sign_reversals/magnitude_cross.csv", magnitudes.groupby(["child_band", "parent_band"], observed=False)[["segments", "LN", "specified_count"]].sum().reset_index())
    # La identidad de promedios ponderados explica inversiones locales sin afirmar una paradoja global.
    pkeys = ["EDOCVE", "MPIOCVE", "age_band", "SEXO"]
    reconstructed = original.groupby(pkeys).agg(SV=("SV", "sum"), D=("specified_count", "sum"),
        weighted_delta=("delta_age_sex", lambda _: 0.0))
    numerators = (original.specified_count * original.delta_age_sex).groupby([original[k] for k in pkeys]).sum()
    parents_delta = original.groupby(pkeys).v1_parent_delta.first()
    defined = reconstructed.D.gt(0) & parents_delta.notna()
    residual = (numerators[defined] / reconstructed.loc[defined, "D"] - parents_delta[defined]).abs().max()
    # Fuera del hijo que invierte, el resto debe sostener el signo del padre (cuando padre V1 es definido).
    parents_sum = original.groupby(pkeys)[["SV", "specified_count"]].sum().reset_index().rename(columns={"SV": "parent_SV_sum", "specified_count": "parent_D_sum"})
    f = f.merge(parents_sum, on=pkeys, validate="many_to_one")
    f["other_types_D"] = f.parent_D_sum - f.specified_count
    f["other_types_delta"] = (f.parent_SV_sum - f.SV) / f.other_types_D - f.national_rate
    assert (f.other_types_D > 0).all() and (f.other_types_delta * f.parent_direction > 0).all()
    save(output, "sign_reversals/decomposition.parquet", f)
    summary = {"eligible": count_summary(e), "reversals": count_summary(f),
        "reversal_unique_municipalities_fraction_eligible": f.municipal_id.nunique() / e.municipal_id.nunique(),
        "reversal_unique_municipalities_fraction_original": f.municipal_id.nunique() / 2477,
        "child_abs_delta_median_pp": f.delta_age_sex.abs().median() * 100,
        "parent_abs_delta_median_pp": f.v1_parent_delta.abs().median() * 100,
        "child_near_2pp": int(f.child_near_2pp.sum()), "parent_near_2pp": int(f.parent_near_2pp.sum()),
        "both_beyond_2pp": int((~f.child_near_2pp & ~f.parent_near_2pp).sum()),
        "both_beyond_5pp": int((f.delta_age_sex.abs().gt(.05) & f.v1_parent_delta.abs().gt(.05)).sum()),
        "robust_fixed_reference": int(f.robust_fixed_reference.sum()), "robust_both_ns_bounds": int(f.robust_both_ns_bounds.sum()),
        "median_D_reversals": f.specified_count.median(), "median_D_other": e.loc[~e.sign_reversal, "specified_count"].median(),
        "median_parent_D_share": f.parent_D_fraction.median(), "weighted_delta_identity_max_residual": float(residual),
        "top_ten_municipality_LN_fraction": float(f.groupby("municipal_id").LN.sum().nlargest(10).sum() / f.LN.sum())}
    write_json(output / "sign_reversals/summary.json", summary)
    return summary


def screening(primary, summaries, split, bands, output):
    split_rows, sensitivity_rows, state_rows, components = [], [], [], []
    for contrast_id, group in primary.groupby("contrast_id"):
        with_split = group.merge(split[["municipal_id", "split"]], on="municipal_id", validate="one_to_one")
        for name, part in with_split.groupby("split"):
            split_rows.append({"split": name, **contrast_summary(part)})
        for name, mask in [("support_200", group.min_D.ge(200) & group.min_LN.ge(200)),
                           ("low_ns", group.max_ns.lt(.1)), ("five_sections", group.min_sections.ge(5))]:
            part = group[mask]
            if len(part):
                sensitivity_rows.append({"scenario": name, **contrast_summary(part)})
        for state, part in group.groupby("EDOCVE"):
            state_rows.append({"EDOCVE": state, **contrast_summary(part)})
        for n, (sex, typ, coefficient) in enumerate(json.loads(group.components.iloc[0])):
            D = group[f"specified_count_{n}"].sum()
            components.append({"contrast_id": contrast_id, "age_band": group.age_band.iloc[0], "SEXO": sex, "TIPOSEC": typ,
                "coefficient": coefficient, "municipalities": len(group), "LN": int(group[f"LN_{n}"].sum()),
                "SV": int(group[f"SV_{n}"].sum()), "NV": int(group[f"NV_{n}"].sum()), "NS": int(group[f"NS_{n}"].sum()),
                "specified_count": int(D), "participation_observed": float(group[f"SV_{n}"].sum() / D)})
    splits = pd.DataFrame(split_rows)
    sensitivity = pd.DataFrame(sensitivity_rows)
    save(output, "validation/split_results.csv", splits)
    save(output, "validation/quality_sensitivity.csv", sensitivity)
    save(output, "validation/state_consistency.csv", pd.DataFrame(state_rows))
    save(output, "interactions/primary_components.csv", pd.DataFrame(components))
    rows = []
    for row in summaries[summaries.family.eq("interaction")].to_dict("records"):
        contrast_id = row["contrast_id"]
        sign = np.sign(row["equal_municipality_pp"])
        criteria = {
            "coverage": row["municipalities"] >= 200 and row["states"] >= 10 and row["annual_LN_fraction"] >= .005,
            "not_one_territory": row["top_municipality_LN_fraction"] < .1,
            "practical_and_weights": abs(row["equal_municipality_pp"]) >= 2 and row["nominal_pp"] * sign >= 2 and row["pooled_counts_pp"] * sign > 0,
            "territorial_consistency": row["municipality_same_sign_fraction"] >= .6 and row["state_same_sign_fraction"] >= 2/3,
        }
        sp = splits[splits.contrast_id.eq(contrast_id)]
        criteria["confirmation"] = len(sp) == 2 and (sp.equal_municipality_pp * sign >= 2).all() and (sp.nominal_pp * sign >= 2).all()
        ba = bands[bands.contrast_id.eq(contrast_id) & bands.estimand.isin(ESTIMANDS[:2])]
        criteria["simultaneous_envelope"] = len(ba) == 2 and ((ba.simultaneous_low_pp > 0) if sign > 0 else (ba.simultaneous_high_pp < 0)).all()
        se = sensitivity[sensitivity.contrast_id.eq(contrast_id)]
        criteria["quality_sensitivity"] = len(se) == 3 and se.municipalities.ge(100).all() and (se.equal_municipality_pp * sign > 0).all() and (se.nominal_pp * sign > 0).all()
        rows.append({**row, **{f"pass_{k}": bool(v) for k, v in criteria.items()},
            "passes_screen": all(criteria.values()), "failed_criteria": ";".join(k for k, v in criteria.items() if not v)})
    screened = pd.DataFrame(rows)
    save(output, "candidates/screening.csv", screened)
    return screened


def pattern_membership(primary, screened, original, output):
    rows = []
    for contrast_id, group in primary.groupby("contrast_id"):
        accepted = bool(screened.set_index("contrast_id").loc[contrast_id, "passes_screen"])
        for n, (sex, typ, coefficient) in enumerate(json.loads(group.components.iloc[0])):
            for r in group[["municipal_id", f"row_id_{n}"]].itertuples(index=False, name=None):
                rows.append({"pattern_id": contrast_id, "municipal_id": r[0], "row_id": r[1], "SEXO": sex,
                             "TIPOSEC": typ, "coefficient": coefficient, "passes_screen": accepted})
    memberships = pd.DataFrame(rows)
    assert not memberships.duplicated(["pattern_id", "row_id"]).any()
    save(output, "candidates/all_six_memberships.parquet", memberships)
    accepted = memberships[memberships.passes_screen]
    frequency = accepted.groupby("row_id").size().rename("validated_pattern_count")
    trace = original.merge(frequency, on="row_id", how="left", validate="one_to_one")
    # Cero aquí significa ninguna membresía, nunca una imputación de tasas.
    trace["validated_pattern_count"] = trace.validated_pattern_count.fillna(0).astype("int16")
    save(output, "reference/all_observations.parquet", trace)
    union = trace[trace.validated_pattern_count.gt(0)]
    summary = {"definition": "overlapping_representative_patterns_not_partition", "patterns_passing": int(screened.passes_screen.sum()),
        "union": count_summary(union), "eligible_outside_union": count_summary(trace[trace.is_eligible & trace.validated_pattern_count.eq(0)]),
        "nominal_union_fraction_annual": float(union.LN.sum() / original.LN.sum()),
        "nominal_union_fraction_eligible": float(union.LN.sum() / original.loc[original.is_eligible, "LN"].sum()),
        "overlapping_segments": int(trace.validated_pattern_count.gt(1).sum()),
        "membership_rows": len(accepted), "union_rows": len(union)}
    write_json(output / "candidates/union_coverage.json", summary)
    return summary


def snapshot(output):
    roots = [ROOT / "src", ROOT / "public", ROOT / "docs", ROOT / "analysis/profile_v2", ROOT / "data/processed/participamx_multiyear"]
    files = {p for root in roots for p in root.rglob("*") if p.is_file() and HOME not in p.parents
             and "__pycache__" not in p.parts and ".cache" not in p.parts}
    files.update([ROOT / "package.json", ROOT / ".gitignore", ROOT / "README.md"])
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(files)}


def refresh_reports(output):
    """Actualiza sólo esta entrega, tras verificar cálculos y fuentes ya validados."""
    manifest = json.loads((output / "metadata/run_manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "validated":
        raise ValueError("No se refresca una ejecución sin manifiesto validado")
    for name, value in manifest["artifacts"].items():
        assert digest(output / name) == value, f"Artefacto alterado: {name}"
    for name, value in manifest["protected_hashes"].items():
        assert digest(ROOT / name) == value, f"Archivo protegido alterado: {name}"
    assert digest(HOME / "reports/protocol.md") == manifest["protocol_hash"]
    original, _, _, _ = load_inputs()
    tables = national_tables(original)
    contrasts = pd.read_parquet(output / "interactions/municipal_contrasts.parquet")
    summaries = pd.read_csv(output / "interactions/contrast_summary.csv")
    screened = pd.read_csv(output / "candidates/screening.csv").fillna({"failed_criteria": ""})
    bands = pd.read_csv(output / "validation/simultaneous_envelopes.csv")
    reversals = json.loads((output / "sign_reversals/summary.json").read_text(encoding="utf-8"))
    union = json.loads((output / "candidates/union_coverage.json").read_text(encoding="utf-8"))
    (output / "_SUCCESS").unlink(missing_ok=True)
    from write_pattern_reports import write_reports
    write_reports(output, tables, contrasts, summaries, screened, bands, reversals, union)
    for name, value in manifest["protected_hashes"].items():
        assert digest(ROOT / name) == value, f"Archivo previo modificado: {name}"
    manifest["report_refresh_count"] = manifest.get("report_refresh_count", 0) + 1
    manifest["code_hashes"] = {p.relative_to(ROOT).as_posix(): digest(p) for p in Path(__file__).parent.glob("*.py")}
    manifest["artifacts"] = {p.relative_to(output).as_posix(): digest(p) for p in sorted(output.rglob("*"))
                             if p.is_file() and p != output / "metadata/run_manifest.json"}
    write_json(output / "metadata/run_manifest.json", manifest)
    (output / "_SUCCESS").write_text("Informe revisado sin recalcular contrastes; integridad verificada.\n", encoding="utf-8")
    print("Informes actualizados; contrastes y remuestreo se mantienen", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--refresh-reports", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(HOME):
        raise ValueError("Use un destino nuevo dentro de patterns/")
    if args.refresh_reports:
        refresh_reports(output)
        return
    if output.exists():
        raise ValueError("Use un destino nuevo dentro de patterns/")
    protected = snapshot(output)
    verified = {}
    for folder in [PRIOR, ROOT / "analysis/profile_v2/editorial/results"]:
        assert (folder / "_SUCCESS").is_file()
        m = json.loads((folder / "metadata/run_manifest.json").read_text(encoding="utf-8"))
        assert m["status"] == "validated"
        for name, value in m["artifacts"].items():
            path = folder / name.replace("\\", "/")
            assert digest(path) == value, f"Artefacto previo alterado: {path}"
            verified[path.relative_to(ROOT).as_posix()] = value
    print(f"Integridad previa verificada: {len(protected)} archivos protegidos", flush=True)
    original, parents, municipalities, references = load_inputs()
    output.mkdir(parents=True)
    write_json(output / "metadata/git_initial.json", {"branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True)})
    tables = national_tables(original)
    for name, frame in tables.items():
        save(output, f"interactions/{name}.csv", frame)
    save(output, "reference/national_age_sex.csv", references)
    contrasts = build_contrasts(original[original.is_eligible])
    save(output, "interactions/municipal_contrasts.parquet", contrasts)
    summaries = pd.DataFrame([contrast_summary(g) for _, g in contrasts.groupby("contrast_id")])
    save(output, "interactions/contrast_summary.csv", summaries)
    save(output, "interactions/age_changes_common_municipalities.csv", age_changes(contrasts))
    primary = contrasts[contrasts.family.eq("interaction")].copy()
    split = municipal_split(municipalities)
    save(output, "validation/municipal_split.parquet", split)
    print("Calculados 27 contrastes emparejados; comienza remuestreo de seis interacciones", flush=True)
    bands = joint_bootstrap(primary, municipalities, output)
    save(output, "validation/simultaneous_envelopes.csv", bands)
    reversals = sign_reversal_analysis(original, output)
    screened = screening(primary, summaries, split, bands, output)
    union = pattern_membership(primary, screened, original, output)
    for name in ["model_metrics", "seed_stability", "municipal_stability", "sensitivity_metrics"]:
        save(output, f"comparisons/v2_{name}.csv", pd.read_csv(PRIOR / f"diagnostics/{name}.csv"))
    from write_pattern_reports import write_reports
    write_reports(output, tables, contrasts, summaries, screened, bands, reversals, union)
    for name, value in protected.items():
        assert digest(ROOT / name) == value, f"Archivo previo modificado: {name}"
    manifest = {"status": "validated", "experiment": "profile-v2.1-matched-interactions-2024", "new_clustering_fits": 0,
        "original_CSV_reads": 0, "bootstrap_replicates": BOOTSTRAPS, "seed": SEED, "primary_contrasts": 6,
        "primary_estimands_family": 18, "protected_files": len(protected), "protected_hashes": protected,
        "verified_prior_artifacts": verified, "candidate_patterns": int(screened.passes_screen.sum()),
        "environment": {key: importlib.metadata.version(key) for key in ["numpy", "pandas", "scipy", "pyarrow", "matplotlib"]},
        "protocol_hash": digest(HOME / "reports/protocol.md"), "critical_review_hash": digest(HOME / "reports/v2_critical_review.md"),
        "code_hashes": {p.relative_to(ROOT).as_posix(): digest(p) for p in Path(__file__).parent.glob("*.py")},
        "artifacts": {p.relative_to(output).as_posix(): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}}
    write_json(output / "metadata/run_manifest.json", manifest)
    (output / "_SUCCESS").write_text("Contrastes, fuentes, conservación y entregables validados.\n", encoding="utf-8")
    print(screened[["contrast_id", "equal_municipality_pp", "nominal_pp", "passes_screen", "failed_criteria"]].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
