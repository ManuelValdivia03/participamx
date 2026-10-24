"""Construye agregados descriptivos sin modificar los Parquet limpios.

Suma conteos antes de dividir; nunca promedia tasas de celdas.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import tempfile
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from clean_data import EXPECTED_ROWS, YEARS, ValidationError, file_hash, open_dataset, require, save_csv, save_json

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "participamx_matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

COUNTS = ["LN", "SV", "NV", "NS"]
METRICS = [*COUNTS, "source_row_count", "sex_2_source_rows", "sex_2_nominal_count"]
RATES = ["participation_observed", "nonparticipation_observed", "participation_nominal", "unspecified_rate"]
KEYS = {
    "year": ["election_year"],
    "state": ["election_year", "EDOCVE"],
    "municipality": ["election_year", "EDOCVE", "MPIOCVE"],
    "municipality_age_sex": ["election_year", "EDOCVE", "MPIOCVE", "age_value", "SEXO"],
    "municipality_section_type": ["election_year", "EDOCVE", "MPIOCVE", "TIPOSEC"],
    "age_sex_year": ["election_year", "age_value", "SEXO"],
    "sex_year": ["election_year", "SEXO"],
    "section_type_year": ["election_year", "TIPOSEC"],
}
SOURCE_COUNTS = {"registered_count": "LN", "voted_count": "SV", "not_voted_count": "NV", "unspecified_count": "NS"}
INPUT_COLUMNS = ["AELEC", "EDOCVE", "MPIOCVE", "age_value", "SEXO", "TIPOSEC",
                 "state_name_label", "municipality_name_label", "district_reference_year", *SOURCE_COUNTS]
SECTION_LABELS = {"U": "Urbana", "M": "Mixta", "R": "Rural"}
SEX_LABELS = {"0": "Hombres", "1": "Mujeres", "2": "No binario"}
ELECTION_TYPES = {year: "presidential" if year in (2012, 2018, 2024) else "midterm" for year in YEARS}
ELECTION_LABELS = {"presidential": "Presidencial", "midterm": "Intermedia"}
DEFAULT_THRESHOLDS = dict(min_registered_count=100, min_specified_count=100, min_source_rows=5, high_unspecified_rate=.10)


def sum_groups(frame, keys):
    """Agrega únicamente métricas aditivas, manteniendo claves como texto."""
    return frame.groupby(keys, as_index=False, sort=False, dropna=False, observed=True)[METRICS].sum()


def combine_parts(parts, keys):
    return sum_groups(pd.concat(parts, ignore_index=True), keys)


def safe_ratio(numerator, denominator):
    numerator, denominator = np.asarray(numerator, dtype=np.float64), np.asarray(denominator, dtype=np.float64)
    result = np.full(len(denominator), np.nan, dtype=np.float64)
    np.divide(numerator, denominator, out=result, where=denominator > 0)
    return result


def add_indicators(frame, thresholds):
    """Las tasas indefinidas permanecen nulas; no se asigna participación cero."""
    result = frame.copy()
    result["specified_count"] = result["SV"] + result["NV"]
    result["participation_observed"] = safe_ratio(result["SV"], result["specified_count"])
    result["nonparticipation_observed"] = safe_ratio(result["NV"], result["specified_count"])
    result["participation_nominal"] = safe_ratio(result["SV"], result["LN"])
    result["unspecified_rate"] = safe_ratio(result["NS"], result["LN"])
    result["is_observed_undefined"] = result["specified_count"].eq(0)
    result["is_nominal_undefined"] = result["LN"].eq(0)
    result["has_low_registered_count"] = result["LN"] < thresholds["min_registered_count"]
    result["has_low_specified_count"] = result["specified_count"] < thresholds["min_specified_count"]
    result["has_few_source_rows"] = result["source_row_count"] < thresholds["min_source_rows"]
    result["has_low_support"] = result[["has_low_registered_count", "has_low_specified_count", "has_few_source_rows"]].any(axis=1)
    result["has_high_unspecified_rate"] = result["unspecified_rate"].ge(thresholds["high_unspecified_rate"])
    result["election_type"] = result["election_year"].map(ELECTION_TYPES)
    if "SEXO" in result:
        result["sex_label"] = result["SEXO"].map(SEX_LABELS)
    if "TIPOSEC" in result:
        result["section_type_label"] = result["TIPOSEC"].map(SECTION_LABELS)
    return result


def validate_table(frame, keys):
    require(not frame[keys].isna().any().any(), f"Clave nula en {keys}")
    require(not frame.duplicated(keys).any(), f"Clave agregada repetida en {keys}")
    require((frame[COUNTS] >= 0).all().all(), f"Conteos negativos en {keys}")
    require(frame["LN"].eq(frame["SV"] + frame["NV"] + frame["NS"]).all(), f"Identidad aritmética fallida en {keys}")
    require(frame["specified_count"].eq(frame["SV"] + frame["NV"]).all(), "Denominador especificado incorrecto")
    undefined = frame["specified_count"].eq(0)
    for name in RATES[:2]:
        require(frame[name].isna().equals(undefined), f"Nulos observados incorrectos: {name}")
    for name in RATES[2:]:
        require(frame[name].isna().equals(frame["LN"].eq(0)), f"Nulos nominales incorrectos: {name}")
    for name in RATES:
        require(frame[name].dropna().between(0, 1).all(), f"Tasa fuera de [0,1]: {name}")
    require(np.allclose((frame["participation_observed"] + frame["nonparticipation_observed"])[~undefined], 1),
            "Las tasas observadas no suman uno.")
    for name in ("EDOCVE", "MPIOCVE", "SEXO", "TIPOSEC"):
        if name in frame:
            require(all(isinstance(value, str) for value in frame[name]), f"Se perdió el tipo texto de {name}")


def aggregate_batches(batches, year, state):
    """Memoria acotada a un bloque y a los grupos de una entidad/elección."""
    age_parts, section_parts, source = [], [], Counter()
    names = defaultdict(set)
    state_names, references = set(), set()
    for batch in batches:
        frame = batch.to_pandas().rename(columns=SOURCE_COUNTS)
        require(not frame[INPUT_COLUMNS[:6] + COUNTS].isna().any().any(), "Campos requeridos nulos en la fuente limpia.")
        require(frame["AELEC"].eq(str(year)).all() and frame["EDOCVE"].eq(state).all(), "Partición y claves de origen no coinciden.")
        require(set(frame["SEXO"]) <= ({"0", "1", "2"} if year == 2024 else {"0", "1"}), "Categoría SEXO no permitida en ese año.")
        require(set(frame["TIPOSEC"]) <= set(SECTION_LABELS), "Tipo de sección desconocido.")
        require((frame[COUNTS] >= 0).all().all(), "Conteos negativos en la fuente.")
        require(frame["LN"].eq(frame["SV"] + frame["NV"] + frame["NS"]).all(), "Identidad fallida en la fuente.")
        frame["source_row_count"] = np.ones(len(frame), dtype=np.int64)
        frame["sex_2_source_rows"] = frame["SEXO"].eq("2").astype("int64")
        frame["sex_2_nominal_count"] = np.where(frame["SEXO"].eq("2"), frame["LN"], 0).astype("int64")
        for metric in METRICS:
            source[metric] += int(frame[metric].sum())
        state_names.update(frame["state_name_label"].unique())
        references.update(map(int, frame["district_reference_year"].unique()))
        for municipality, label in frame[["MPIOCVE", "municipality_name_label"]].drop_duplicates().itertuples(index=False, name=None):
            names[municipality].add(label)
        age_parts.append(sum_groups(frame, ["MPIOCVE", "age_value", "SEXO"]))
        section_parts.append(sum_groups(frame, ["MPIOCVE", "TIPOSEC"]))
        # Reduce periódicamente para no acumular todos los parciales del estado.
        if len(age_parts) >= 8:
            age_parts = [combine_parts(age_parts, ["MPIOCVE", "age_value", "SEXO"])]
            section_parts = [combine_parts(section_parts, ["MPIOCVE", "TIPOSEC"])]
    require(source["source_row_count"] > 0, f"Partición vacía: {year}/{state}")
    require(len(state_names) == len(references) == 1, f"Etiquetas o marcos ambiguos: {year}/{state}")
    require(all(len(labels) == 1 for labels in names.values()), f"Nombres municipales ambiguos en {year}/{state}; no se elegirá uno arbitrariamente.")
    age = combine_parts(age_parts, ["MPIOCVE", "age_value", "SEXO"])
    section = combine_parts(section_parts, ["MPIOCVE", "TIPOSEC"])
    municipality = sum_groups(age, ["MPIOCVE"])
    section_municipality = sum_groups(section, ["MPIOCVE"])
    compare_sums(municipality, section_municipality, ["MPIOCVE"])
    for frame in (age, section, municipality):
        for metric in METRICS:
            require(int(frame[metric].sum()) == source[metric], f"Duplicación o pérdida en {year}/{state}/{metric}")
        frame.insert(0, "election_year", np.int16(year))
        frame.insert(1, "EDOCVE", state)
        frame["state_name_label"] = next(iter(state_names))
        frame["municipality_name_label"] = frame["MPIOCVE"].map({code: next(iter(labels)) for code, labels in names.items()})
        frame["district_reference_year"] = np.int16(next(iter(references)))
    return age, section, municipality, source


def compare_sums(left, right, keys):
    left = sum_groups(left, keys).sort_values(keys).reset_index(drop=True)
    right = sum_groups(right, keys).sort_values(keys).reset_index(drop=True)
    require(left[keys].equals(right[keys]), f"Conjuntos de claves diferentes al conciliar {keys}")
    require(np.array_equal(left[METRICS].to_numpy(), right[METRICS].to_numpy()), f"Conteos no conciliados en {keys}")


def write_frame(frame, path, keys):
    frame = frame.sort_values(keys).reset_index(drop=True)
    validate_table(frame, keys)
    table = pa.Table.from_pandas(frame, preserve_index=False)
    # Pandas puede producir large_string; fija un contrato de texto uniforme.
    schema = pa.schema([pa.field(field.name, pa.string() if pa.types.is_large_string(field.type) else field.type,
                                 nullable=field.nullable) for field in table.schema], metadata=table.schema.metadata)
    table = table.cast(schema)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), f"No se sobrescribirá {path}")
    pq.write_table(table, path, compression="zstd", compression_level=3, use_dictionary=True, row_group_size=100_000)
    with pq.ParquetFile(path) as parquet:
        stored = parquet.read()
    require(stored.equals(table), f"Parquet no coincide con la tabla: {path}")
    return dict(rows=len(frame), bytes=path.stat().st_size, sha256=file_hash(path))


def snapshot_inputs(root, source, manifest):
    """Comprueba todos los archivos limpios y los ZIP contra la limpieza validada."""
    success = json.loads((source / "_SUCCESS").read_text(encoding="utf-8"))
    require(success["manifest_sha256"] == file_hash(source / "metadata/run_manifest.json"), "Manifiesto limpio alterado.")
    require(manifest["status"] == "validated", "La limpieza no está validada.")
    require({p.relative_to(source).as_posix() for p in (source / "records").rglob("*.parquet")} == {p["path"] for p in manifest["parts"]}, "Inventario limpio diferente del manifiesto.")
    hashes = {}
    for part in manifest["parts"]:
        path = source / part["path"]
        digest = file_hash(path)
        require(digest == part["sha256"], f"Parquet limpio alterado: {path}")
        hashes[str(path)] = digest
    for path in (source / "metadata").iterdir():
        if path.is_file():
            hashes[str(path)] = file_hash(path)
    hashes[str(source / "_SUCCESS")] = file_hash(source / "_SUCCESS")
    for item in manifest["sources"]:
        path = root / "data/raw" / item["archive"]
        digest = file_hash(path)
        require(digest == item["sha256_after"], f"ZIP original alterado: {path}")
        hashes[str(path)] = digest
    return hashes


def pct(value):
    return "n/d" if pd.isna(value) else f"{100 * value:.2f} %"


def number(value):
    return f"{int(value):,}"


def points(value):
    return "n/d" if pd.isna(value) else f"{100 * value:.2f}"


def markdown_table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(str(v).replace("|", "\\|") for v in row) + " |" for row in rows)])


def ranking_rows(frame, municipality=False):
    rows = []
    for row in frame.to_dict("records"):
        label = f"{row['EDOCVE']} · {row['state_name_label']}"
        if municipality:
            label += f" / {row['MPIOCVE']} · {row['municipality_name_label']}"
        rows.append([label, number(row["LN"]), number(row["specified_count"]), pct(row["participation_observed"]),
                     pct(row["participation_nominal"]), pct(row["unspecified_rate"]),
                     "Sí" if row["has_low_support"] else "No"])
    return rows


def generate_charts(tables, charts):
    charts.mkdir(parents=True, exist_ok=True)
    states = tables["state"].query("election_year == 2024").sort_values(["participation_observed", "EDOCVE"])
    fig, axes = plt.subplots(1, 2, figsize=(18, 12), gridspec_kw={"width_ratios": [3, 1]}, sharey=True)
    y = np.arange(len(states))
    axes[0].scatter(states["participation_observed"], y, label="Observada: SV/(SV+NV)", s=28)
    axes[0].scatter(states["participation_nominal"], y, label="Nominal: SV/LN", s=22, marker="x", color="#d36b20")
    axes[0].set_yticks(y, [f"{r.state_name_label} · LN {r.LN:,}" for r in states.itertuples()], fontsize=8)
    axes[0].set_xlim(0, 1)
    axes[0].set_title("Participación por entidad, 2024")
    axes[0].legend(loc="lower right")
    axes[1].barh(y, states["unspecified_rate"], color="#ad494a")
    axes[1].set_title("NS / LN")
    for axis in axes:
        axis.xaxis.set_major_formatter(PercentFormatter(1))
        axis.grid(axis="x", alpha=.25)
    fig.tight_layout()
    fig.savefig(charts / "state_participation_2024.png", dpi=170)
    plt.close(fig)
    annual = tables["year"].sort_values("election_year")
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for name, label in (("participation_observed", "Observada"), ("participation_nominal", "Nominal")):
        axes[0].plot(annual["election_year"], annual[name], marker="o", label=label)
    for row in annual.itertuples():
        axes[0].annotate("P" if row.election_type == "presidential" else "I", (row.election_year, row.participation_observed), xytext=(0, 10), textcoords="offset points", ha="center")
    axes[0].set_ylim(0, .85)
    axes[0].set_title("Seis elecciones: P = presidencial, I = intermedia")
    axes[0].legend()
    axes[1].plot(annual["election_year"], annual["unspecified_rate"], marker="o", color="#ad494a")
    axes[1].set_title("Participación no especificada: NS / LN")
    for axis in axes:
        axis.xaxis.set_ticks(annual["election_year"])
        axis.yaxis.set_major_formatter(PercentFormatter(1))
        axis.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig(charts / "election_history.png", dpi=170)
    plt.close(fig)
    age = tables["age_sex_year"]
    fig, axes = plt.subplots(2, 3, figsize=(17, 9), sharex=True, sharey=True)
    colors = {"0": "#286b9d", "1": "#ab427b", "2": "#be7b14"}
    for axis, year in zip(axes.flat, YEARS):
        selected = age[age["election_year"].eq(year)]
        for sex in sorted(selected["SEXO"].unique()):
            values = selected[selected["SEXO"].eq(sex)].sort_values("age_value")
            if sex == "2":
                axis.scatter(values["age_value"], values["participation_observed"], color=colors[sex], marker="x", s=20, label=SEX_LABELS[sex])
            else:
                # Reindexar sólo para el trazado deja huecos; no crea filas analíticas.
                curve = values.set_index("age_value")["participation_observed"].reindex(range(int(age.age_value.min()), int(age.age_value.max()) + 1))
                axis.plot(curve.index, curve, label=SEX_LABELS[sex], color=colors[sex], linewidth=1.3)
            low = values[values["has_low_support"]]
            axis.scatter(low["age_value"], low["participation_observed"], s=10, facecolors="none", edgecolors=colors[sex], alpha=.5)
        axis.set_title(str(year))
        axis.set_xlabel("Edad exacta")
        axis.set_ylabel("SV / (SV + NV)")
        axis.set_ylim(0, 1.04)
        axis.yaxis.set_major_formatter(PercentFormatter(1))
        axis.grid(alpha=.2)
        axis.legend(fontsize=8)
    fig.suptitle("Perfiles por edad y sexo; círculos huecos = soporte pequeño\nEdades extremas conservadas; los puntos de SEXO=2 tienen base reducida", fontsize=11)
    fig.tight_layout()
    fig.savefig(charts / "age_sex_profiles.png", dpi=170)
    plt.close(fig)
    section = tables["section_type_year"]
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for code, label in SECTION_LABELS.items():
        values = section[section["TIPOSEC"].eq(code)].sort_values("election_year")
        axes[0].plot(values["election_year"], values["participation_observed"], marker="o", label=label)
        axes[1].plot(values["election_year"], values["unspecified_rate"], marker="o", label=label)
    axes[0].set_title("Participación observada según tipo de sección")
    axes[1].set_title("NS / LN según tipo de sección")
    for axis in axes:
        axis.set_xticks(YEARS)
        axis.yaxis.set_major_formatter(PercentFormatter(1))
        axis.legend()
        axis.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig(charts / "section_type_history.png", dpi=170)
    plt.close(fig)
    municipality = tables["municipality"].query("election_year == 2024")
    fig, axis = plt.subplots(figsize=(10, 6))
    points = axis.scatter(municipality["LN"], municipality["participation_observed"], c=municipality["unspecified_rate"], cmap="viridis", s=15, alpha=.65, vmin=0, vmax=1)
    axis.set_xscale("log")
    axis.set_xlabel("LN municipal (escala logarítmica de visualización)")
    axis.set_ylabel("Participación observada")
    axis.yaxis.set_major_formatter(PercentFormatter(1))
    axis.set_title("Municipios 2024: tamaño, participación y no especificación")
    axis.text(.02, .02, f"{int(municipality.is_observed_undefined.sum())} municipios con tasa no definida;\nconservados en la tabla, sin coordenada vertical", transform=axis.transAxes,
              fontsize=9, va='bottom', bbox=dict(facecolor='white', alpha=.85, edgecolor='none'))
    colorbar = fig.colorbar(points, ax=axis)
    colorbar.set_label("NS / LN")
    colorbar.ax.yaxis.set_major_formatter(PercentFormatter(1))
    axis.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(charts / "municipality_support_2024.png", dpi=170)
    plt.close(fig)


def write_report(root, output, tables, summaries, validation_rows, thresholds, manifest):
    annual = tables["year"].sort_values("election_year")
    states = tables["state"].query("election_year == 2024").sort_values(["participation_observed", "EDOCVE"], ascending=[False, True], na_position="last")
    municipalities = tables["municipality"].query("election_year == 2024")
    defined = municipalities[municipalities["participation_observed"].notna()]
    high = defined.sort_values(["participation_observed", "EDOCVE", "MPIOCVE"], ascending=[False, True, True]).head(5)
    low = defined.sort_values(["participation_observed", "EDOCVE", "MPIOCVE"], ascending=[True, True, True]).head(5)
    high_ns = municipalities.sort_values(["unspecified_rate", "EDOCVE", "MPIOCVE"], ascending=[False, True, True]).head(5)
    sex = tables["sex_year"].sort_values(["election_year", "SEXO"])
    sections = tables["section_type_year"].sort_values(["election_year", "TIPOSEC"])
    age = tables["age_sex_year"]
    ranked_headers = ["Entidad / municipio", "LN", "SV+NV", "Observada", "Nominal", "NS/LN", "Soporte pequeño"]
    highest, lowest = states.iloc[0], states.iloc[-1]
    nominal_highest = states.sort_values('participation_nominal', ascending=False).iloc[0]
    age24 = age.query("election_year == 2024")
    maxima = []
    for code in ("0", "1"):
        values = age24[age24.SEXO.eq(code) & age24.participation_observed.notna()]
        if values.empty:
            continue
        top = values.sort_values(["participation_observed", "age_value"], ascending=[False, True]).iloc[0]
        maxima.append([SEX_LABELS[code], int(top.age_value), number(top.LN), pct(top.participation_observed), pct(top.unspecified_rate), "Sí" if top.has_low_support else "No"])
    pairs = tables["municipality_section_type"].query("election_year == 2024").pivot(index=["EDOCVE", "MPIOCVE"], columns="TIPOSEC", values="participation_observed")
    paired = pairs[["U", "R"]].dropna() if {"U", "R"} <= set(pairs.columns) else pd.DataFrame(columns=["U", "R"])
    differences = paired["R"] - paired["U"]
    history_means = annual.groupby("election_type")[["participation_observed", "participation_nominal", "unspecified_rate"]].mean()
    age_comparisons = []
    for code in ['0','1']:
        values = age24[age24.SEXO.eq(code)].set_index('age_value')
        if 25 in values.index and 60 in values.index:
            younger, older = values.loc[25], values.loc[60]
            age_comparisons.append(f"{SEX_LABELS[code]}: {pct(younger.participation_observed)} a los 25 años frente a {pct(older.participation_observed)} a los 60; diferencia {points(older.participation_observed-younger.participation_observed)} pp.")
    section_findings = ''
    section24 = sections[sections.election_year.eq(2024)].set_index('TIPOSEC')
    if {'U','R'} <= set(section24.index):
        urban, rural = section24.loc['U'], section24.loc['R']
        section_findings = f"En 2024, R registra {pct(rural.participation_observed)} observada y U {pct(urban.participation_observed)} (R−U: {points(rural.participation_observed-urban.participation_observed)} pp). Sobre LN, las proporciones son {pct(rural.participation_nominal)} y {pct(urban.participation_nominal)}, respectivamente, con NS/LN de {pct(rural.unspecified_rate)} y {pct(urban.unspecified_rate)}. La comparación cambia al cambiar el denominador; no se interpreta como efecto del tipo de sección."
    sex_two_rows = int(sex.loc[sex.SEXO.eq('2'), 'source_row_count'].sum())
    sex_two_nominal = int(sex.loc[sex.SEXO.eq('2'), 'LN'].sum())
    sex_gaps = []
    for year in YEARS:
        values = sex[sex.election_year.eq(year)].set_index('SEXO').participation_observed
        sex_gaps.append([year, points(values.get('1', np.nan) - values.get('0', np.nan))])
    lines = ["# Análisis descriptivo territorial, demográfico e histórico de ParticipaMX", "",
        "## Alcance, unidad y denominadores", "",
        f"Se procesaron los **{manifest['source_rows']:,} registros** del conjunto técnico validado, sin modificar ZIP, Parquet limpios ni src/. Cada registro de entrada es una celda de sección, sexo y edad; `source_row_count` cuenta esas filas, no personas. LN/SV/NV/NS son conteos reportados. Los resultados describen los cuadernillos disponibles y no equivalen automáticamente al total de votos de actas; los diccionarios excluyen casillas especiales y residentes en el extranjero.", "",
        "En cada grupo se sumaron primero LN, SV, NV y NS. `specified_count=SV+NV`; `participation_observed=SV/(SV+NV)`; `nonparticipation_observed=NV/(SV+NV)`; `participation_nominal=SV/LN`; `unspecified_rate=NS/LN`. Las tasas se almacenan entre 0 y 1; para presentarlas como porcentajes se multiplican por 100, sin cambiar el dato almacenado. Las diferencias de tasas se expresan como puntos porcentuales (pp). No se promedian tasas de celdas.", "",
        "Cuando SV+NV=0, las dos tasas observadas son NULL y no cero. LN=0 también produce tasas nominales nulas; se registra su estado aunque no exista en esta fuente. NS se conserva separado: no se asigna a votantes ni a no votantes. Una proporción observada alta con NS alto describe sólo la parte especificada.", "",
        "## Elecciones y comparación histórica", "",
        markdown_table(["Año", "Tipo", "LN", "SV", "NV", "NS", "Observada", "Nominal", "NS/LN"],
            [[int(r.election_year), ELECTION_LABELS[r.election_type], *[number(getattr(r, c)) for c in COUNTS], pct(r.participation_observed), pct(r.participation_nominal), pct(r.unspecified_rate)] for r in annual.itertuples()]), "",
        "Contexto electoral: 2012, 2018 y 2024 son elecciones presidenciales; 2009, 2015 y 2021 son intermedias. Se clasifica por año, sin interpretar el texto ambiguo FELECCION. No se siguen personas individuales entre elecciones ni se supone estabilidad de municipios o distritos.", "",
        f"La media simple de las tres tasas nacionales observadas es {pct(history_means.loc['presidential', 'participation_observed'])} en presidenciales y {pct(history_means.loc['midterm', 'participation_observed'])} en intermedias. Cada elección tiene igual peso en esta comparación descriptiva; no es una tasa de personas únicas ni una estimación causal del tipo de elección. Cambian cobertura, NS, composición demográfica, oferta electoral, contexto y procedimientos; estos resultados no separan sus efectos.", "",
        "![Historia electoral](../charts/descriptive/election_history.png)", "",
        "## Las entidades en 2024", "",
        f"Se comparan las {len(states)} entidades por participación observada entre registros especificados. El primer valor del orden es {highest.state_name_label}: {pct(highest.participation_observed)}, LN={number(highest.LN)}, NS/LN={pct(highest.unspecified_rate)}. El último es {lowest.state_name_label}: {pct(lowest.participation_observed)}, LN={number(lowest.LN)}, NS/LN={pct(lowest.unspecified_rate)}. La diferencia es {100*(highest.participation_observed-lowest.participation_observed):.2f} pp. No se atribuye esa diferencia a una causa concreta.", "",
        markdown_table(ranked_headers, ranking_rows(states)), "",
        f"Al ordenar por la proporción nominal, el primer lugar es {nominal_highest.state_name_label}: {pct(nominal_highest.participation_nominal)}, LN={number(nominal_highest.LN)}, NS/LN={pct(nominal_highest.unspecified_rate)}. El orden depende del indicador y la cobertura; {int(states.has_high_unspecified_rate.sum())} entidades presentan NS/LN por encima o igual al umbral exploratorio de {pct(thresholds['high_unspecified_rate'])}.", "",
        "![Entidades 2024](../charts/descriptive/state_participation_2024.png)", "",
        "## Municipios con valores altos, bajos y alta no especificación", "",
        f"En 2024 se observan {len(municipalities):,} pares entidad–municipio. Las tablas completas conservan todos los grupos; aquí se muestran cinco extremos definidos por cada orden, sin filtrar por LN o NS. Los empates se ordenan por las claves textuales. Hay {int(municipalities.is_observed_undefined.sum())} municipios con tasa observada no definida, que no reciben una posición numérica. Las listas no demuestran diferencias significativas ni calidad equivalente de cobertura.", "",
        "Cinco mayores participaciones observadas:", "", markdown_table(ranked_headers, ranking_rows(high, True)), "",
        "Cinco menores participaciones observadas:", "", markdown_table(ranked_headers, ranking_rows(low, True)), "",
        "Cinco mayores proporciones NS/LN, incluyendo tasas observadas no definidas si las hubiera:", "", markdown_table(ranked_headers, ranking_rows(high_ns, True)), "",
        "![Tamaño y cobertura municipal](../charts/descriptive/municipality_support_2024.png)", "",
        "## Edad exacta y sexo", "",
        markdown_table(["Año", "SEXO", "Categoría", "Filas fuente", "LN", "SV+NV", "Observada", "Nominal", "NS/LN"],
            [[int(r.election_year), r.SEXO, r.sex_label, number(r.source_row_count), number(r.LN), number(r.specified_count), pct(r.participation_observed), pct(r.participation_nominal), pct(r.unspecified_rate)] for r in sex.itertuples()]), "",
        f"SEXO=0 corresponde a hombres y SEXO=1 a mujeres. SEXO=2 se define como no binario en 2024; su ausencia en los diccionarios previos no equivale a cero personas. Los {sex_two_rows} registros fuente de esa categoría, con LN={sex_two_nominal}, se conservan y se reconcilian incluso en tablas que no tienen SEXO como clave. Su base pequeña limita cualquier comparación y no representa una serie histórica comparable.", "",
        "Diferencia observada mujeres menos hombres por elección:", "",
        markdown_table(["Año", "Diferencia (pp)"], sex_gaps), "",
        "Ejemplos de edades exactas en 2024 (selección para presentación; la tabla completa conserva todas las edades):", "",
        markdown_table(["Edad", "Sexo", "LN", "SV+NV", "Observada", "NS/LN"],
            [[int(r.age_value), r.sex_label, number(r.LN), number(r.specified_count), pct(r.participation_observed), pct(r.unspecified_rate)]
             for r in age24[age24.age_value.isin([18,25,40,60,80,100]) & age24.SEXO.isin(['0','1'])].sort_values(['age_value','SEXO']).itertuples()]), "",
        ' '.join(age_comparisons) + " Son comparaciones entre grupos de edad del mismo año, no trayectorias de las mismas personas ni efectos causales de envejecer.", "",
        "Las curvas conservan todas las edades exactas, incluidas las extremas. Las máximas tasas por edad de 2024, sin filtrar soporte, son:", "",
        markdown_table(["Sexo", "Edad exacta", "LN", "Observada", "NS/LN", "Soporte pequeño"], maxima), "",
        "Un máximo con denominador pequeño no identifica una edad óptima de participación ni prueba una diferencia poblacional. Las edades extremas siguen pendientes de validación con la fuente. Las diferencias entre sexos son descriptivas y no están ajustadas por edad, territorio o cobertura.", "",
        "![Edad y sexo](../charts/descriptive/age_sex_profiles.png)", "",
        "## Tipos de sección", "",
        markdown_table(["Año", "Tipo", "LN", "SV+NV", "Observada", "Nominal", "NS/LN"],
            [[int(r.election_year), f"{r.TIPOSEC}: {r.section_type_label}", number(r.LN), number(r.specified_count), pct(r.participation_observed), pct(r.participation_nominal), pct(r.unspecified_rate)] for r in sections.itertuples()]), "",
        "TIPOSEC describe la sección de residencia consignada, no una categoría personal ni necesariamente la condición rural/urbana completa de un municipio. Las diferencias nacionales pueden reflejar composición de estados, municipios y edades, además de cobertura; no son efectos causales del tipo de sección.", "",
        section_findings, "",
        f"Dentro de 2024 hay {len(paired):,} municipios con tipos U y R presentes y tasas definidas para ambos. En ese subconjunto, la mediana de R menos U es {points(differences.median())} pp; R supera a U en {int((differences>0).sum()):,}, U supera a R en {int((differences<0).sum()):,} y hay {int((differences==0).sum()):,} empates. Es una comparación no ponderada de diferencias municipales del mismo año; no ajusta edad ni NS y no incluye en ese contraste los municipios sin ambos tipos, que permanecen en sus tablas.", "",
        "![Tipos de sección](../charts/descriptive/section_type_history.png)", "",
        "## Soporte pequeño, alta no especificación y resultados no definidos", "",
        f"Se usan banderas exploratorias configurables: LN<{thresholds['min_registered_count']}, SV+NV<{thresholds['min_specified_count']} o filas fuente<{thresholds['min_source_rows']} para soporte pequeño; NS/LN≥{pct(thresholds['high_unspecified_rate'])} para no especificación elevada. No son criterios oficiales ni pruebas de error, no excluyen datos y no equivalen a márgenes de error de una muestra. La precisión aparente de las tasas no resuelve errores de cobertura o captura.", "",
        markdown_table(["Nivel", "Año", "Grupos", "Soporte pequeño", "NS elevado", "SV+NV=0", "LN=0"],
            [[r['level'], r['election_year'], number(r['groups']), number(r['low_support_groups']), number(r['high_unspecified_groups']), number(r['observed_undefined_groups']), number(r['nominal_undefined_groups'])] for r in summaries if r['level'] in ['municipality', 'municipality_age_sex']]), "",
        "Los diagnósticos completos de los ocho niveles están en `metadata/group_quality.csv`. Los grupos sin especificación quedan conservados con sus conteos y tasas NULL. Las banderas se superponen: no se suman para estimar grupos únicos. Los grupos ausentes no se completaron con cero.", "",
        "## Validaciones y estructura de entrega", "",
        f"Se conciliaron {len(validation_rows):,} controles nivel–año–entidad contra las {manifest['baseline_state_groups']} combinaciones del reporte de limpieza. Las diferencias de LN/SV/NV/NS, filas fuente y conservación de SEXO=2 son cero. Cada una de las cinco tablas principales representa la población una sola vez a su propio nivel; nunca deben concatenarse y volver a sumarse entre sí. Las agregaciones demográfica y por tipo de sección se conciliaron también por municipio, sin unir sus filas ni multiplicar conteos.", "",
        "Se verificaron claves únicas en cada nivel, la identidad LN=SV+NV+NS en todos los grupos, tipos territoriales de texto, categorías por año, denominadores y nulos correctos, tasas entre 0 y 1 e igualdad tras escribir y releer Parquet. Los conteos y hashes de los archivos originales y limpios se comprobaron antes y después de la ejecución.", "",
        markdown_table(["Tabla", "Claves", "Grupos"], [[name, ', '.join(KEYS[name]), number(manifest['table_rows'][name])] for name in KEYS]), "",
        "Los cinco primeros niveles son los solicitados; `age_sex_year`, `sex_year` y `section_type_year` son resúmenes auxiliares calculados desde esos conteos para el informe y los gráficos. `sex_2_source_rows` y `sex_2_nominal_count` permiten verificar la categoría incluso donde SEXO no forma parte de la clave. `district_reference_year` conserva la referencia original cuando hay dimensión territorial; no se hizo una correspondencia de distritos.", "",
        f"Datos: `{output.relative_to(root).as_posix()}`; contrato y controles en `metadata/`; gráficos en `analysis/charts/descriptive/`. El marcador `_SUCCESS` indica ejecución validada. Para reproducir: `.venv/Scripts/python.exe analysis/scripts/build_descriptive.py --batch-size 100000`. El destino existente se protege: una repetición debe usar otro `--output` dentro de data/processed/. Las salidas están ignoradas por las reglas existentes de Git.", "",
        "El manifiesto de construcción conserva el hash del código utilizado al calcular las tablas. Si se regenera sólo el informe y los gráficos con `--report-only`, `metadata/presentation_manifest.json` registra por separado el hash de esa versión de presentación; no se alteran los agregados ni su validación.", "",
        "## Limitaciones y decisiones pendientes", "",
        "No se supone continuidad territorial de una clave entre elecciones. Municipio requiere entidad, clave municipal y año; los nombres son etiquetas, no claves. Los marcos distritales 2021/2023, posibles cambios municipales y seccionales, cobertura de cuadernillos y fechas ambiguas siguen pendientes de contraste oficial. No se modelaron efectos ni se interpretaron asociaciones como causalidad. No hubo exclusiones, imputación, normalización estadística ni clustering. La escala logarítmica del gráfico municipal sólo cambia el eje visual, no los datos.", "",
        "Estos son indicadores descriptivos, no una selección definitiva de variables para clustering. Cualquier decisión posterior sobre edades extremas, NS, comparación histórica, unidades de análisis o criterios de cobertura deberá ser explícita y conservar esta versión completa.", ""]
    path = root / "analysis/reports/descriptive_analysis.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    (output / "metadata/descriptive_analysis.md").write_text("\n".join(lines), encoding="utf-8")


def build_descriptive(root, source, output, batch_size=100_000, thresholds=None, expected_total=EXPECTED_ROWS):
    root, source, output = Path(root).resolve(), Path(source).resolve(), Path(output).resolve()
    thresholds = dict(DEFAULT_THRESHOLDS if thresholds is None else thresholds)
    require(batch_size > 0, "batch-size debe ser positivo.")
    require(0 <= thresholds['high_unspecified_rate'] <= 1 and all(thresholds[k] > 0 for k in ['min_registered_count','min_specified_count','min_source_rows']), "Umbrales inválidos.")
    require(output.is_relative_to(root / "data/processed") and not output.is_relative_to(source), "Destino fuera de data/processed/ o dentro de la fuente.")
    require(not output.exists(), f"El destino ya existe: {output}; elegir otro --output.")
    clean_manifest = json.loads((source / "metadata/run_manifest.json").read_text(encoding="utf-8"))
    require(clean_manifest['rows'] == expected_total, "Cantidad de registros limpia diferente de la esperada.")
    input_hashes = snapshot_inputs(root, source, clean_manifest)
    dataset = open_dataset(source)
    require(dataset.count_rows() == expected_total, "Filas Parquet diferentes del manifiesto.")
    baseline = pd.read_csv(source / "metadata/state_validation.csv", dtype={"EDOCVE": str})
    quality = pd.read_csv(source / "metadata/quality_summary.csv", dtype={"EDOCVE": str})
    require(not baseline.duplicated(['election_year','EDOCVE']).any(), "Claves repetidas en controles de limpieza.")
    output.mkdir(parents=True)
    (output / "metadata").mkdir()
    started = time.monotonic()
    manifest = dict(status="running", source=str(source), output=str(output), batch_size=batch_size,
                    thresholds=thresholds, started_at_utc=datetime.now(timezone.utc).isoformat(),
                    versions=dict(python=platform.python_version(), pandas=pd.__version__, numpy=np.__version__, pyarrow=pa.__version__, matplotlib=matplotlib.__version__),
                    input_files=len(input_hashes), baseline_state_groups=len(baseline), files=[], errors=[], table_rows={name: 0 for name in KEYS})
    save_json(output / "metadata/run_manifest.json", manifest)
    save_json(output / "metadata/input_hashes.json", input_hashes)
    parts = defaultdict(list)
    validation_rows, summaries = [], []
    baseline_metrics = {}
    try:
        for record in baseline.to_dict('records'):
            year, state = int(record['election_year']), record['EDOCVE']
            batches = dataset.scanner(columns=INPUT_COLUMNS,
                filter=(ds.field('election_year') == year) & (ds.field('state_code') == state),
                batch_size=batch_size, use_threads=False, batch_readahead=1, fragment_readahead=1).to_batches()
            age, section, municipality, actual = aggregate_batches(batches, year, state)
            expected_quality = quality.loc[(quality.election_year == year) & (quality.EDOCVE == state)]
            require(len(expected_quality) == 1, "Control de categoría ausente o repetido.")
            expected = {c: int(record[f'output_sum_{c}']) for c in COUNTS}
            expected.update(source_row_count=int(record['output_rows']),
                            sex_2_source_rows=int(expected_quality.iloc[0].sex_2_rows),
                            sex_2_nominal_count=int(expected_quality.iloc[0].sex_2_LN))
            baseline_metrics[(year, state)] = expected
            require(all(actual[c] == expected[c] for c in METRICS), f"Fuente no conciliada con limpieza: {year}/{state}")
            for name, frame in [('municipality_age_sex', age), ('municipality_section_type', section), ('municipality', municipality)]:
                frame = add_indicators(frame, thresholds)
                validate_table(frame, KEYS[name])
                validation_rows.append(dict(level=name, election_year=year, EDOCVE=state,
                    **{f'difference_{c}': int(frame[c].sum()) - expected[c] for c in METRICS}))
                collect_quality(name, frame, summaries)
                if name == 'municipality_age_sex':
                    destination = output / name / f'part-{year}-{state}.parquet'
                    info = write_frame(frame, destination, KEYS[name])
                    manifest['files'].append(dict(table=name, path=destination.relative_to(output).as_posix(), **info))
                    manifest['table_rows'][name] += len(frame)
                else:
                    parts[name].append(frame)
            parts['age_sex_year'].append(sum_groups(age, KEYS['age_sex_year']))
            parts['section_type_year'].append(sum_groups(section, KEYS['section_type_year']))
            state_frame = sum_groups(municipality, KEYS['state'])
            state_frame['state_name_label'] = municipality.state_name_label.iloc[0]
            state_frame['district_reference_year'] = municipality.district_reference_year.iloc[0]
            parts['state'].append(state_frame)
            print(f"{year}/{state}: {actual['source_row_count']:,} filas; {len(age):,} grupos edad/sexo conciliados", flush=True)
        tables = {}
        for name in ['municipality', 'municipality_section_type', 'state']:
            tables[name] = add_indicators(pd.concat(parts[name], ignore_index=True)[KEYS[name] + METRICS + [c for c in ['state_name_label','municipality_name_label','district_reference_year'] if c in parts[name][0]]], thresholds)
        tables['year'] = add_indicators(sum_groups(tables['state'], KEYS['year']), thresholds)
        tables['age_sex_year'] = add_indicators(combine_parts(parts['age_sex_year'], KEYS['age_sex_year']), thresholds)
        tables['sex_year'] = add_indicators(sum_groups(tables['age_sex_year'], KEYS['sex_year']), thresholds)
        tables['section_type_year'] = add_indicators(combine_parts(parts['section_type_year'], KEYS['section_type_year']), thresholds)
        for name, frame in tables.items():
            destination = output / name / 'table.parquet'
            info = write_frame(frame, destination, KEYS[name])
            manifest['files'].append(dict(table=name, path=destination.relative_to(output).as_posix(), **info))
            manifest['table_rows'][name] = len(frame)
            if name not in ['municipality', 'municipality_section_type']:
                collect_quality(name, frame, summaries)
            if name == 'state':
                for (year, state), group in frame.groupby(['election_year','EDOCVE'], dropna=False):
                    validation_rows.append(dict(level=name, election_year=int(year), EDOCVE=state,
                        **{f'difference_{c}': int(group[c].sum()) - baseline_metrics[(int(year),state)][c] for c in METRICS}))
            elif 'EDOCVE' not in KEYS[name]:
                compare_sums(frame, tables['state'], ['election_year'])
            require(int(frame.source_row_count.sum()) == expected_total, f"Conteos fuente duplicados en {name}")
            require(int(frame.sex_2_source_rows.sum()) == sum(v['sex_2_source_rows'] for v in baseline_metrics.values()), f"SEXO=2 perdido en {name}")
        require(all(row[f'difference_{c}'] == 0 for row in validation_rows for c in METRICS), "Diferencias entre niveles.")
        summaries = pd.DataFrame(summaries).groupby(['level','election_year'],as_index=False).sum().to_dict('records')
        manifest['source_rows'] = expected_total
        # Comprobación de todas las particiones demográficas persistidas, por metadatos.
        require(sum(f['rows'] for f in manifest['files'] if f['table']=='municipality_age_sex') == manifest['table_rows']['municipality_age_sex'], "Inventario demográfico incorrecto.")
        save_csv(output/'metadata/state_reconciliation.csv', list(validation_rows[0]), validation_rows)
        save_csv(output/'metadata/group_quality.csv', list(summaries[0]), summaries)
        save_json(output/'metadata/source_dictionaries.json', json.loads((source/'metadata/source_dictionaries.json').read_text(encoding='utf-8')))
        save_json(output/'metadata/table_contract.json', dict(keys=KEYS, metrics=METRICS, rates={
            'specified_count':'SV + NV','participation_observed':'SV / (SV + NV)',
            'nonparticipation_observed':'NV / (SV + NV)','participation_nominal':'SV / LN','unspecified_rate':'NS / LN'},
            null_policy='Tasas observadas NULL cuando SV+NV=0; nominales NULL cuando LN=0.',
            thresholds=thresholds, categories=dict(sex_by_year={y: {'0':SEX_LABELS['0'],'1':SEX_LABELS['1'], **({'2':SEX_LABELS['2']} if y==2024 else {})} for y in YEARS}, section_type=SECTION_LABELS),
            election_types=ELECTION_TYPES, warning='Los niveles son vistas alternativas; no sumar entre niveles. Claves de texto sin correspondencia territorial histórica asumida.'))
        charts = root/'analysis/charts/descriptive'
        generate_charts(tables, charts)
        for path_string, digest in input_hashes.items():
            require(file_hash(path_string) == digest, f"Fuente modificada durante el análisis: {path_string}")
        require({p.relative_to(output).as_posix() for p in output.rglob('*.parquet')} == {f['path'] for f in manifest['files']}, "Inventario de salida diferente.")
        for entry in manifest['files']:
            require(file_hash(output/entry['path']) == entry['sha256'], "Salida alterada tras escribir.")
        manifest.update(status='validated', seconds=round(time.monotonic()-started,2), finished_at_utc=datetime.now(timezone.utc).isoformat(),
            artifact_hashes={str(p):file_hash(p) for p in [Path(__file__),root/'analysis/scripts/clean_data.py',root/'analysis/cleaning_plan.md',root/'analysis/reports/technical_cleaning.md']})
        write_report(root, output, tables, summaries, validation_rows, thresholds, manifest)
        save_json(output/'metadata/run_manifest.json',manifest)
        (output/'_SUCCESS').write_text(json.dumps(dict(rows=expected_total, manifest_sha256=file_hash(output/'metadata/run_manifest.json'))),encoding='utf-8')
        print(f"VALIDADO: {expected_total:,} filas fuente; informe en analysis/reports/descriptive_analysis.md",flush=True)
        return manifest
    except Exception as error:
        manifest['status']='failed'
        manifest['errors'].append(dict(type=type(error).__name__,message=str(error)))
        save_json(output/'metadata/run_manifest.json',manifest)
        save_json(output/'metadata/incidents.json',manifest['errors'])
        raise


def collect_quality(name, frame, summaries):
    for year, group in frame.groupby('election_year'):
        summaries.append(dict(level=name,election_year=int(year),groups=len(group),
            low_support_groups=int(group.has_low_support.sum()), high_unspecified_groups=int(group.has_high_unspecified_rate.sum()),
            observed_undefined_groups=int(group.is_observed_undefined.sum()), nominal_undefined_groups=int(group.is_nominal_undefined.sum())))


def refresh_presentation(root, output):
    """Regenera informe y gráficos desde agregados validados, sin reagregar fuentes."""
    root, output = Path(root).resolve(), Path(output).resolve()
    manifest_path = output/'metadata/run_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    success = json.loads((output/'_SUCCESS').read_text(encoding='utf-8'))
    require(manifest['status']=='validated' and success['manifest_sha256']==file_hash(manifest_path), 'Agregados no validados.')
    for entry in manifest['files']:
        require(file_hash(output/entry['path'])==entry['sha256'], 'Un agregado cambió desde su validación.')
    tables = {name:pd.read_parquet(output/name/'table.parquet') for name in KEYS if name!='municipality_age_sex'}
    summaries = pd.read_csv(output/'metadata/group_quality.csv').to_dict('records')
    validation = pd.read_csv(output/'metadata/state_reconciliation.csv',dtype={'EDOCVE':str}).to_dict('records')
    generate_charts(tables,root/'analysis/charts/descriptive')
    write_report(root,output,tables,summaries,validation,manifest['thresholds'],manifest)
    save_json(output/'metadata/presentation_manifest.json',dict(
        generated_at_utc=datetime.now(timezone.utc).isoformat(), data_manifest_sha256=file_hash(manifest_path),
        presentation_script_sha256=file_hash(Path(__file__)),
        note='Regeneración de presentación desde agregados validados; no se modificaron Parquet ni el manifiesto de su construcción.'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--source',type=Path,default=Path('data/processed/technical_cleaned'))
    parser.add_argument('--output',type=Path,default=Path('data/processed/descriptive'))
    parser.add_argument('--batch-size',type=int,default=100_000)
    parser.add_argument('--min-registered-count',type=int,default=100)
    parser.add_argument('--min-specified-count',type=int,default=100)
    parser.add_argument('--min-source-rows',type=int,default=5)
    parser.add_argument('--high-unspecified-rate',type=float,default=.10)
    parser.add_argument('--report-only',action='store_true',help='Regenera sólo informe y gráficos desde agregados validados.')
    args=parser.parse_args()
    root=args.root.resolve()
    source=args.source if args.source.is_absolute() else root/args.source
    output=args.output if args.output.is_absolute() else root/args.output
    if args.report_only:
        refresh_presentation(root,output)
        return
    build_descriptive(root,source,output,args.batch_size,dict(min_registered_count=args.min_registered_count,
        min_specified_count=args.min_specified_count,min_source_rows=args.min_source_rows,high_unspecified_rate=args.high_unspecified_rate))


if __name__=='__main__':
    main()
