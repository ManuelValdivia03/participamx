"""Auditoría exploratoria reproducible; no modifica ni extrae los ZIP originales.

Ejecución desde cualquier directorio:
    .venv/Scripts/python.exe analysis/scripts/initial_audit.py --chunk-size 100000
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import csv
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import tempfile
import time
import zipfile
import warnings

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "participamx_matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

YEARS = (2009, 2012, 2015, 2018, 2021, 2024)
COLUMNS = "AELEC FELECCION EDOCVE EDONOM MPIOCVE MPIONOM SECCION TIPOSEC DEF DEL SEXO EDAD LN SV NV NS".split()
FOCUS = "DEF DEL SEXO EDAD LN SV NV NS".split()
COUNTS = "LN SV NV NS".split()
NUMERIC = "AELEC EDOCVE MPIOCVE SECCION DEF DEL SEXO EDAD LN SV NV NS".split()
KEY = "AELEC EDOCVE MPIOCVE SECCION SEXO EDAD".split()
MISSING_TOKENS = {"", "NA", "N/A", "NULL", "NONE", "NAN"}
PARTITIONS = 32


def write_csv(path, fields, rows):
    """Guarda evidencia en UTF-8, sin alterar valores de origen."""
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def missing(value):
    return value.strip().upper() in MISSING_TOKENS


def invalid_reason(column, value, year):
    """Aplica reglas estructurales; los límites sin catálogo se documentan."""
    if missing(value):
        return "missing"
    if column == "TIPOSEC":
        return "unknown_section_type" if value not in {"U", "M", "R"} else ""
    if column == "FELECCION":
        valid = []
        for pattern in ("%d/%m/%Y", "%m/%d/%Y"):
            try:
                valid.append(datetime.strptime(value, pattern))
            except ValueError:
                pass
        if not valid:
            return "unparseable_date"
        return "date_year_mismatch" if all(d.year != year for d in valid) else ""
    if column not in NUMERIC:
        return ""
    if not re.fullmatch(r"[+-]?\d+", value):
        return "not_integer_literal"
    number = int(value)
    if column == "AELEC" and number != year:
        return "election_year_mismatch"
    if column == "EDOCVE" and not 1 <= number <= 32:
        return "outside_state_range"
    if column in {"MPIOCVE", "SECCION", "DEF", "DEL"} and number <= 0:
        return "nonpositive_identifier"
    if column == "SEXO" and number not in ({0, 1, 2} if year == 2024 else {0, 1}):
        return "unknown_sex_category"
    if column == "EDAD" and number < 18:
        return "age_below_18_review"
    if column in COUNTS and number < 0:
        return "negative_count"
    return ""


def weighted_statistics(frequencies):
    """Calcula cuantiles lineales exactos desde frecuencias, sin muestreo."""
    histogram = Counter()
    for token, count in frequencies.items():
        if not missing(token) and re.fullmatch(r"[+-]?\d+", token):
            histogram[int(token)] += count
    if not histogram:
        return {}
    values = np.array(sorted(histogram), dtype=np.float64)
    weights = np.array([histogram[int(v)] for v in values], dtype=np.int64)
    cumulative = np.cumsum(weights)
    count = int(cumulative[-1])

    def quantile(probability):
        rank = (count - 1) * probability
        low, high = int(np.floor(rank)), int(np.ceil(rank))
        left = values[np.searchsorted(cumulative, low, side="right")]
        right = values[np.searchsorted(cumulative, high, side="right")]
        return float(left + (right - left) * (rank - low))

    mean = float(np.dot(values, weights) / count)
    deviation = float(np.sqrt(np.dot((values - mean) ** 2, weights) / (count - 1))) if count > 1 else 0.0
    q1, median, q3 = [quantile(p) for p in (.25, .5, .75)]
    lower, upper = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    inside = (values >= lower) & (values <= upper)
    return dict(count=count, total=sum(v * n for v, n in histogram.items()), mean=mean,
                std=deviation, min=float(values[0]), q1=q1, median=median, q3=q3,
                p95=quantile(.95), p99=quantile(.99), max=float(values[-1]),
                zero_count=int(histogram[0]), lower_fence=lower, upper_fence=upper,
                lower_outliers=int(weights[values < lower].sum()),
                upper_outliers=int(weights[values > upper].sum()),
                whislo=float(values[inside][0]), whishi=float(values[inside][-1]))


def csv_chunks(archive, name, chunk_size):
    """Lee todas las columnas como texto; no infiere nulos ni pierde ceros."""
    with archive.open(name) as stream, warnings.catch_warnings():
        warnings.simplefilter("error", pd.errors.ParserWarning)
        yield from pd.read_csv(stream, encoding="utf-8-sig", sep=",", dtype=str,
                               na_filter=False, keep_default_na=False, skip_blank_lines=False,
                               chunksize=chunk_size, on_bad_lines="error", index_col=False)


def save_hashes(directory, kind, hashes):
    buckets = hashes % PARTITIONS
    for bucket in range(PARTITIONS):
        selected = hashes[buckets == bucket]
        with (directory / f"{kind}_{bucket}.bin").open("ab") as stream:
            selected.tofile(stream)


def duplicate_candidates(directory, kind):
    candidates = []
    for bucket in range(PARTITIONS):
        path = directory / f"{kind}_{bucket}.bin"
        if path.exists():
            values = np.fromfile(path, dtype=np.uint64)
            unique, counts = np.unique(values, return_counts=True)
            candidates.extend(unique[counts > 1])
    return np.array(candidates, dtype=np.uint64)


def verify_duplicates(archive, names, chunk_size, candidates, year, output):
    """Confirma igualdad de tuplas; una colisión de hash nunca prueba duplicación."""
    totals = {}
    for kind, columns in (("full", COLUMNS), ("key", KEY)):
        suspected = candidates[kind]
        if not len(suspected):
            totals[kind] = dict(groups=0, excess_rows=0, involved_rows=0)
            continue
        # Sólo las coincidencias de hash se guardan en SQLite, con igualdad exacta.
        import sqlite3
        with tempfile.TemporaryDirectory(prefix="audit_duplicates_") as temporary:
            with closing(sqlite3.connect(str(Path(temporary) / "matches.sqlite"))) as database:
                database.execute("CREATE TABLE matches (value TEXT, member TEXT, record INTEGER)")
                for name in names:
                    offset = 0
                    for chunk in csv_chunks(archive, name, chunk_size):
                        hashes = pd.util.hash_pandas_object(chunk[columns], index=False).to_numpy()
                        positions = np.flatnonzero(np.isin(hashes, suspected))
                        database.executemany("INSERT INTO matches VALUES (?, ?, ?)", (
                            (json.dumps(chunk.iloc[int(i)][columns].tolist(), ensure_ascii=False), name, offset + int(i) + 1)
                            for i in positions))
                        offset += len(chunk)
                database.execute("CREATE INDEX matches_value ON matches(value)")
                counts = database.execute("SELECT COUNT(*), COALESCE(SUM(n-1),0), COALESCE(SUM(n),0) FROM (SELECT COUNT(*) n FROM matches GROUP BY value HAVING COUNT(*)>1)").fetchone()
                totals[kind] = dict(zip(("groups", "excess_rows", "involved_rows"), map(int, counts)))
                rows = database.execute("SELECT m.member, m.record, m.value FROM matches m JOIN (SELECT value FROM matches GROUP BY value HAVING COUNT(*)>1) d ON m.value=d.value ORDER BY m.value,m.member,m.record")
                write_csv(output / f"duplicates_{kind}_{year}.csv", ["year", "member", "record", *columns],
                          (dict(year=year, member=name, record=record, **dict(zip(columns, json.loads(value)))) for name, record, value in rows))
    return totals


def audit_year(path, year, chunk_size, output):
    started = time.monotonic()
    before = file_hash(path)
    frequencies = {c: Counter() for c in COLUMNS}
    geography, sections = set(), set()
    checks = Counter()
    files, inventory, dictionaries = [], [], []
    exception_fields = ["year", "member", "record", "issue", *COLUMNS, "difference"]
    with (output / f"row_exceptions_{year}.csv").open("w", newline="", encoding="utf-8-sig") as exception_stream:
        writer = csv.DictWriter(exception_stream, fieldnames=exception_fields)
        writer.writeheader()
        with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory(prefix=f"audit_{year}_") as temporary:
            temporary = Path(temporary)
            for member in archive.infolist():
                inventory.append(dict(year=year, archive=path.name, member=member.filename,
                                      kind="directory" if member.is_dir() else Path(member.filename).suffix.lower(),
                                      bytes=member.file_size, compressed_bytes=member.compress_size,
                                      crc32=f"{member.CRC:08x}"))
                if member.filename.lower().endswith(".txt"):
                    dictionaries.append(dict(member=member.filename, text=archive.read(member).decode("utf-8-sig")))
            names = [m.filename for m in archive.infolist() if m.filename.lower().endswith(".csv")]
            for file_index, name in enumerate(names, 1):
                with archive.open(name) as stream:
                    sample = stream.read(65536)
                # Sólo decodifica el encabezado: el corte de la muestra puede
                # coincidir con la mitad de un carácter UTF-8 de los datos.
                header = next(csv.reader(io.StringIO(sample.split(b"\n", 1)[0].decode("utf-8-sig"))))
                if header != COLUMNS:
                    raise ValueError(f"Esquema inesperado en {name}: {header}")
                offset = 0
                member_states = set()
                for chunk in csv_chunks(archive, name, chunk_size):
                    for column in COLUMNS:
                        frequencies[column].update(chunk[column].value_counts(dropna=False).to_dict())
                    geography.update(chunk[["EDOCVE", "MPIOCVE", "EDONOM", "MPIONOM"]].drop_duplicates().itertuples(index=False, name=None))
                    sections.update(chunk[["EDOCVE", "SECCION"]].drop_duplicates().itertuples(index=False, name=None))
                    member_states.update(chunk["EDOCVE"].unique())
                    numeric = chunk[COUNTS].apply(pd.to_numeric, errors="coerce")
                    valid = numeric.notna().all(axis=1) & np.isfinite(numeric).all(axis=1) & numeric.mod(1).eq(0).all(axis=1)
                    difference = numeric["LN"] - numeric[["SV", "NV", "NS"]].sum(axis=1)
                    mismatch = valid & difference.ne(0)
                    checks["equation_evaluable"] += int(valid.sum())
                    checks["equation_unevaluable"] += int((~valid).sum())
                    checks["equation_mismatch"] += int(mismatch.sum())
                    checks["zero_ln"] += int(numeric["LN"].eq(0).sum())
                    checks["component_above_ln"] += int(numeric[["SV", "NV", "NS"]].gt(numeric["LN"], axis=0).any(axis=1).sum())
                    for issue, mask in (("equation_mismatch", mismatch), ("equation_unevaluable", ~valid)):
                        for i in np.flatnonzero(mask.to_numpy()):
                            writer.writerow(dict(year=year, member=name, record=offset + int(i) + 1,
                                                 issue=issue, **chunk.iloc[int(i)].to_dict(),
                                                 difference=difference.iloc[int(i)] if valid.iloc[int(i)] else ""))
                    for kind, columns in (("full", COLUMNS), ("key", KEY)):
                        save_hashes(temporary, kind, pd.util.hash_pandas_object(chunk[columns], index=False).to_numpy())
                    offset += len(chunk)
                files.append(dict(year=year, member=name, rows=offset, encoding="utf-8-sig" if sample.startswith(b"\xef\xbb\xbf") else "utf-8", separator=",",
                                  newline="CRLF" if b"\r\n" in sample else "LF", columns="|".join(header), states="|".join(sorted(member_states))))
                print(f"{year}: CSV {file_index}/{len(names)}, {offset:,} registros", flush=True)
            candidates = {kind: duplicate_candidates(temporary, kind) for kind in ("full", "key")}
            duplicates = verify_duplicates(archive, names, chunk_size, candidates, year, output)
    after = file_hash(path)
    if before != after:
        raise RuntimeError(f"El ZIP cambió durante la auditoría: {path}")
    profiles, invalid, statistics = [], [], {}
    for column in COLUMNS:
        counts = frequencies[column]
        null_count = sum(n for value, n in counts.items() if missing(value))
        bad = Counter()
        for value, count in counts.items():
            reason = invalid_reason(column, value, year)
            if reason:
                invalid.append(dict(year=year, column=column, value=value, reason=reason, count=count))
                if reason != "missing":
                    bad[reason] += count
        profiles.append(dict(year=year, column=column, storage_type="text", rows=sum(counts.values()),
                             distinct=len(counts), missing=null_count, empty=counts[""],
                             whitespace=sum(n for v, n in counts.items() if v != v.strip()),
                             replacement_characters=sum(n for v, n in counts.items() if "\ufffd" in v),
                             invalid=sum(bad.values()),
                             observed_type="integer" if column in NUMERIC and all(missing(v) or re.fullmatch(r"[+-]?\d+", v) for v in counts) else "text"))
        if column in NUMERIC:
            statistics[column] = weighted_statistics(counts)
    rows = sum(f["rows"] for f in files)
    assert all(p["rows"] == rows for p in profiles)
    assert checks["equation_evaluable"] + checks["equation_unevaluable"] == rows
    result = dict(year=year, archive=path.name, archive_bytes=path.stat().st_size,
                  sha256_before=before, sha256_after=after, rows=rows, checks=dict(checks),
                  duplicates=duplicates, statistics=statistics, profiles=profiles, invalid=invalid,
                  files=files, inventory=inventory, dictionaries=dictionaries,
                  states=sorted(frequencies["EDOCVE"]), municipalities=len({g[:2] for g in geography}),
                  sections=len(sections), seconds=round(time.monotonic() - started, 2))
    write_csv(output / f"value_frequencies_{year}.csv", ["year", "column", "value", "count"],
              (dict(year=year, column=c, value=v, count=n) for c in COLUMNS for v, n in sorted(frequencies[c].items())))
    write_csv(output / f"geographic_identifiers_{year}.csv", ["year", "EDOCVE", "MPIOCVE", "EDONOM", "MPIONOM"],
              (dict(year=year, **dict(zip(["EDOCVE", "MPIOCVE", "EDONOM", "MPIONOM"], g))) for g in sorted(geography)))
    (output / f"audit_{year}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{year}: terminado en {result['seconds']} s; {rows:,} registros; {duplicates}", flush=True)
    return result


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
                       *("| " + " | ".join(str(v).replace("|", "\\|") for v in row) + " |" for row in rows)])


def load_frequencies(output, year, column):
    with (output / f"value_frequencies_{year}.csv").open(encoding="utf-8-sig", newline="") as stream:
        return {row["value"]: int(row["count"]) for row in csv.DictReader(stream) if row["column"] == column}


def build_findings(results, output):
    """Resume sólo mediciones comprobadas; separa alertas de decisiones."""
    total = sum(r["rows"] for r in results)
    mismatch = sum(r["checks"]["equation_mismatch"] for r in results)
    unevaluable = sum(r["checks"]["equation_unevaluable"] for r in results)
    duplicates = sum(r["duplicates"]["full"]["excess_rows"] for r in results)
    key_duplicates = sum(r["duplicates"]["key"]["excess_rows"] for r in results)
    numeric_invalid = sum(p["invalid"] for r in results for p in r["profiles"] if p["column"] in NUMERIC)
    rows = []
    for result in results:
        year = result["year"]
        age = load_frequencies(output, year, "EDAD")
        profiles = {p["column"]: p for p in result["profiles"]}
        rows.append([year, profiles["DEF"]["missing"], profiles["DEL"]["missing"],
                     result["statistics"]["DEL"]["zero_count"],
                     result["statistics"]["EDAD"]["max"],
                     sum(n for value, n in age.items() if value.isdigit() and int(value) > 100),
                     profiles["MPIONOM"]["whitespace"]])
    return ["## Hallazgos comprobados", "",
            f"Se leyeron {total:,} filas. Excepciones a LN = SV + NV + NS: {mismatch:,}; filas no evaluables: {unevaluable:,}. Repeticiones completas (exceso): {duplicates:,}; repeticiones de la clave candidata (exceso): {key_duplicates:,}. Valores numéricos que incumplen las reglas estructurales: {numeric_invalid:,} (los faltantes se presentan por separado).", "",
            table(["Año", "DEF faltante", "DEL faltante", "DEL=0", "Edad máxima", "Celdas edad >100", "MPIONOM con espacios periféricos"], rows), "",
            "Las edades extremas son alertas para revisión documental; no se les asigna un valor corregido ni se asume que sean códigos de agregación. El número de celdas con edad >100 no es el número de personas: no se sumó LN para ese subconjunto. Los faltantes distritales y los espacios de nombres se conservan exactamente como aparecen.", "",
            "Totales aritméticos observados por año, antes de cualquier decisión de comparabilidad o cobertura:", "",
            table(["Año", "LN", "SV", "NV", "NS", "NS / LN (%)"],
                  [[r['year'], *[f"{r['statistics'][c]['total']:,}" for c in COUNTS],
                    f"{100 * r['statistics']['NS']['total'] / r['statistics']['LN']['total']:.3f}"] for r in results]), ""]


def create_charts(results, charts):
    for filename, columns in (("count_boxplots.png", COUNTS), ("demographic_boxplots.png", ["EDAD"]), ("district_boxplots.png", ["DEF", "DEL"])):
        figure, axes = plt.subplots(1, len(columns), figsize=(5 * len(columns), 5), squeeze=False)
        for axis, column in zip(axes[0], columns):
            boxes = []
            for result in results:
                stats = result["statistics"][column]
                boxes.append(dict(label=str(result["year"]), med=stats["median"], q1=stats["q1"], q3=stats["q3"],
                                  whislo=stats["whislo"], whishi=stats["whishi"], fliers=[stats["min"], stats["max"]]))
            axis.bxp(boxes, showfliers=False)
            axis.set_title(column)
            axis.set_xlabel("Año electoral")
            axis.set_ylabel("Valor observado")
            axis.grid(axis="y", alpha=.25)
            if column == "NS" and all(box["q1"] == box["q3"] == 0 for box in boxes):
                axis.set_ylim(-.5, 1)
                axis.set_yticks([0])
                axis.text(.5, .75, "Q1 = mediana = Q3 = 0\nConsulte los extremos en el informe", ha="center", transform=axis.transAxes, fontsize=9)
        figure.suptitle("Cuartiles exactos y bigotes a 1.5 IQR\nExtremos y frecuencias en el informe", fontsize=10)
        figure.tight_layout()
        figure.savefig(charts / filename, dpi=160)
        plt.close(figure)
    figure, axes = plt.subplots(1, 2, figsize=(12, 4))
    for column in COUNTS:
        axes[0].plot([r["year"] for r in results], [r["statistics"][column]["max"] for r in results], marker="o", label=column)
        axes[1].plot([r["year"] for r in results], [100 * (r["statistics"][column]["lower_outliers"] + r["statistics"][column]["upper_outliers"]) / r["statistics"][column]["count"] for r in results], marker="o", label=column)
    axes[0].set_title("Máximos observados por celda")
    axes[1].set_title("Celdas fuera de 1.5 IQR (%)")
    for axis in axes:
        axis.set_xlabel("Año electoral")
        axis.set_xticks([r["year"] for r in results])
        axis.legend()
        axis.grid(alpha=.25)
    figure.tight_layout()
    figure.savefig(charts / "count_extremes.png", dpi=160)
    plt.close(figure)


def create_report(results, output, charts, chunk_size):
    profiles = [p for r in results for p in r["profiles"]]
    invalid = [v for r in results for v in r["invalid"]]
    write_csv(output / "column_profiles.csv", list(profiles[0]), profiles)
    write_csv(output / "invalid_values.csv", ["year", "column", "value", "reason", "count"], invalid)
    files = [f for r in results for f in r["files"]]
    write_csv(output / "csv_inventory.csv", list(files[0]), files)
    inventory = [m for r in results for m in r["inventory"]]
    write_csv(output / "zip_inventory.csv", list(inventory[0]), inventory)
    stats = [dict(year=r["year"], column=c, **s) for r in results for c, s in r["statistics"].items() if s]
    write_csv(output / "descriptive_statistics.csv", list(stats[0]), stats)
    outliers = []
    for result in results:
        for column in ["EDAD", *COUNTS]:
            distribution = result["statistics"][column]
            for value, count in load_frequencies(output, result["year"], column).items():
                if re.fullmatch(r"[+-]?\d+", value):
                    number = int(value)
                    if number < distribution["lower_fence"] or number > distribution["upper_fence"]:
                        outliers.append(dict(year=result["year"], column=column, value=value, count=count,
                                             lower_fence=distribution["lower_fence"], upper_fence=distribution["upper_fence"]))
    write_csv(output / "outlier_values.csv", ["year", "column", "value", "count", "lower_fence", "upper_fence"], outliers)
    create_charts(results, charts)
    metadata = dict(python=platform.python_version(), pandas=pd.__version__, numpy=np.__version__, matplotlib=matplotlib.__version__, chunk_size=chunk_size)
    (output / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    lines = ["# Auditoría exploratoria inicial de ParticipaMX", "",
             "Alcance: exclusivamente los seis ZIP de `data/raw/` (2009, 2012, 2015, 2018, 2021 y 2024). No se modificaron registros, no se imputó, no se normalizó ni se ejecutó clustering. No se intervino el desarrollo web ni se crearon commits.", "",
             "## Método y reproducción", "",
             f"Lectura completa de {sum(r['rows'] for r in results):,} registros en {len(files)} CSV, directamente dentro de los ZIP, por bloques de hasta {chunk_size:,} filas. Todas las columnas se conservan como texto (`na_filter=False`), incluidos `EDOCVE` y `MPIOCVE`; las conversiones numéricas sólo sirven para comprobaciones en memoria. `record` en las excepciones es el ordinal de registro, desde 1 después del encabezado, no una línea física.", "",
             "Las frecuencias por valor permiten calcular estadísticas y cuantiles lineales exactos sin acumular filas ni muestrear. Los hashes para duplicados se particionan en 32 archivos temporales por año; las coincidencias se vuelven a leer y se confirman mediante igualdad exacta de tuplas en SQLite. Se detectan repeticiones entre bloques y entre CSV del mismo año. Las tuplas completas incluyen AELEC, por lo que no se interpreta la repetición de una geografía en distintos años como duplicación. La memoria depende del bloque, las categorías distintas y una partición de hashes, no de cargar los CSV completos. Se requiere disco temporal para aproximadamente 16 bytes por fila del año, más SQLite si hubiera candidatos.", "",
             "Se comprueban SHA-256 antes y después de cada ZIP y CRC al consumir sus miembros completos. El proceso se detiene ante errores de decodificación o esquema inesperado. Las versiones quedan en `run_metadata.json`. Ejecutar desde la raíz:", "", "```powershell", ".venv/Scripts/python.exe analysis/scripts/initial_audit.py --chunk-size 100000", "```", "",
             "## Estructura y cobertura observada", "", table(["Año", "CSV", "Registros", "Entidades", "Municipios (clave compuesta)", "Secciones (entidad + sección)", "ZIP íntegro"],
                 [[r['year'], len(r['files']), f"{r['rows']:,}", len(r['states']), r['municipalities'], r['sections'], r['sha256_before'] == r['sha256_after']] for r in results]), "",
             "Cada ZIP contiene una carpeta, 32 CSV y un TXT de descripción. El detalle de todos los miembros, tamaños y CRC está en `zip_inventory.csv`; encabezados y formato por CSV en `csv_inventory.csv`. Las 16 columnas, en el mismo orden, son:", "", "`" + ", ".join(COLUMNS) + "`", "",
             "Los catálogos observados de entidad y municipio se guardan sin rellenar ni recodificar en `geographic_identifiers_YEAR.csv`. `MPIOCVE` sólo identifica municipio junto con `EDOCVE`. No se realizó validación contra un catálogo territorial externo.", "",
             "## Tipos, faltantes y valores inválidos", "",
             "Se distinguen texto vacío, tokens de faltantes (vacío/espacios, NA, N/A, NULL, NONE y NAN), espacios periféricos y caracteres de sustitución U+FFFD. Los faltantes se cuentan aparte de los inválidos. No se convierten automáticamente a cero. `column_profiles.csv` cubre las 16 columnas; `invalid_values.csv` conserva cada token señalado y su frecuencia.", "",
             "Reglas: enteros literales en campos numéricos; conteos no negativos; entidad entre 1 y 32; municipio, sección y distritos positivos; año coincidente con el ZIP; SEXO según el diccionario de cada año; TIPOSEC en U/M/R; fechas interpretables con día/mes o mes/día y año coincidente. EDAD menor de 18 se señala para revisión, sin excluirla; no se impone un máximo biológico ni límites distritales sin catálogos. Los ceros distritales se señalan como identificadores no positivos y requieren confirmar si son códigos especiales.", "",
             table(["Año", "Columna", "Tipo observado", "Faltantes", "Inválidos según reglas", "Valores distintos"],
                   [[p['year'], p['column'], p['observed_type'], p['missing'], p['invalid'], p['distinct']] for p in profiles if p['column'] in FOCUS]), "",
             "Otros campos con alertas:", "", table(["Año", "Columna", "Faltantes", "Inválidos", "Espacios periféricos", "U+FFFD"],
                [[p['year'], p['column'], p['missing'], p['invalid'], p['whitespace'], p['replacement_characters']] for p in profiles if p['column'] not in FOCUS and any(p[k] for k in ('missing','invalid','whitespace','replacement_characters'))]), "",
             "## Duplicados y consistencia aritmética", "",
             "Duplicado completo: igualdad textual de las 16 columnas después del parseo CSV. Clave candidata: `" + ", ".join(KEY) + "`. Es una hipótesis sobre el nivel de desagregación; repetirla no demuestra un error ni autoriza a eliminar filas. La clave no incluye DEF/DEL para poder detectar múltiples asignaciones distritales en una misma celda. Los conteos de exceso son ocurrencias posteriores a la primera, y los involucrados incluyen todas las ocurrencias.", "",
             table(["Año", "Duplicados completos: exceso", "Clave: grupos / exceso / involucrados", "Ecuación evaluable", "Excepciones LN=SV+NV+NS", "No evaluables", "LN=0", "Algún componente > LN"],
                [[r['year'], r['duplicates']['full']['excess_rows'], ' / '.join(str(r['duplicates']['key'][k]) for k in ('groups','excess_rows','involved_rows')), r['checks']['equation_evaluable'], r['checks']['equation_mismatch'], r['checks']['equation_unevaluable'], r['checks']['zero_ln'], r['checks']['component_above_ln']] for r in results]), "",
             "`row_exceptions_YEAR.csv` contiene todas las excepciones aritméticas y filas no evaluables, con valores originales y procedencia; un archivo sólo con encabezado significa cero excepciones. Los archivos `duplicates_full_YEAR.csv` y `duplicates_key_YEAR.csv` se producen únicamente cuando hay candidatos de hash y contienen sólo coincidencias confirmadas. `difference` es LN − (SV + NV + NS). No se sustituyen faltantes para evaluar la igualdad.", "",
             "## Estadísticas descriptivas y posibles atípicos", "",
             "Unidad: celda observada de sección, sexo y edad, según clave candidata. Estadísticas sin ponderar por personas; los conteos son personas por celda. Desviación estándar muestral (ddof=1). Se incluyen los ceros y todos los enteros observados. Un atípico se define por valores fuera de [Q1 − 1.5 IQR, Q3 + 1.5 IQR]; es una señal exploratoria, no un registro inválido. Para NS con Q1=Q3=0, cualquier valor positivo queda fuera: debe interpretarse como falta de especificación, no como justificación para borrar datos.", "",
             table(["Año", "Campo", "Media", "DE", "Mín", "Q1", "Mediana", "Q3", "P99", "Máx", "Fuera IQR"],
                [[r['year'], c, *[f"{s[k]:.3f}" for k in ('mean','std','min','q1','median','q3','p99','max')], s['lower_outliers'] + s['upper_outliers']] for r in results for c in FOCUS if (s := r['statistics'][c])]), "",
             "DEF, DEL y SEXO son códigos categóricos: sus estadísticas numéricas no tienen interpretación de magnitud. El boxplot de distritos sólo muestra cambios de codificación/cobertura, no distancias ni perfiles. No se hace boxplot de SEXO.", "",
             "Los valores concretos de EDAD/LN/SV/NV/NS fuera de los umbrales, sus frecuencias y límites se guardan en `outlier_values.csv`; no se recortaron ni eliminaron registros. Los boxplots usan cuantiles y bigotes calculados con todos los registros; se omiten los puntos individuales para evitar saturación. Los máximos y los conteos de atípicos se muestran por separado:", "",
             "![Conteos](../charts/count_boxplots.png)", "", "![Edad](../charts/demographic_boxplots.png)", "", "![Distritos](../charts/district_boxplots.png)", "", "![Extremos](../charts/count_extremes.png)", "",
             "## Diferencias entre años", "",
             table(["Año", "Codificación", "Fin de línea", "FELECCION (texto original)", "SEXO: frecuencias", "TIPOSEC: frecuencias", "Referencia distrital del TXT"],
                [[r['year'], ', '.join(sorted({f['encoding'] for f in r['files']})), ', '.join(sorted({f['newline'] for f in r['files']})), category_summary(output, r['year'], 'FELECCION'), category_summary(output, r['year'], 'SEXO'), category_summary(output, r['year'], 'TIPOSEC'), 'DERFE 2023' if r['year'] == 2024 else 'DERFE 2021'] for r in results]), "",
             "Los TXT de 2009–2021 definen SEXO 0=hombres y 1=mujeres; el de 2024 añade 2=no binario. Las asignaciones DEF/DEL de 2009–2021 están referidas a DERFE 2021 y las de 2024 a DERFE 2023: no deben compararse como territorios constantes sin correspondencias cartográficas. Los diccionarios originales están incluidos como texto en `audit_YEAR.json`.", "",
             "Los textos de fecha se conservan sin elegir una interpretación de día/mes o mes/día cuando ambas son posibles. Las claves territoriales no se rellenan con ceros; sus longitudes y valores originales se pueden revisar en las frecuencias y los catálogos. Las diferencias de cobertura municipal/seccional pueden reflejar cambios territoriales y disponibilidad; no se atribuyen automáticamente a errores.", "",
             "## Limitaciones y decisiones antes de limpiar", "",
             "1. Validar con el equipo la clave de observación y cómo tratar cualquier repetición; no deduplicar sólo por entidad/municipio/edad. La igualdad textual no equipara códigos con formatos distintos.",
             "2. Obtener catálogos INE versionados de municipios, secciones y distritos, y correspondencias entre los marcos 2021 y 2023. No se validaron nombres ni límites máximos distritales contra fuentes externas.",
             "3. Acordar el tratamiento de DEF/DEL faltantes, representados por un espacio en 2009 y 2012 y por texto vacío en DEL de 2024. No se observaron ceros en DEL. Conservar las claves originales como texto y decidir por separado la representación para integración.",
             "4. Confirmar el formato de FELECCION, especialmente 2024, con metadatos oficiales; no resolver fechas ambiguas por inferencia automática.",
             "5. Conservar SEXO=2 en 2024 y decidir cómo presentar la comparabilidad histórica sin recodificarlo ni excluirlo.",
             "6. Definir el denominador de participación y el tratamiento de NS. El diccionario describe SV como registros con marca, NV sin marca y NS no especificados; NS no equivale a abstención ni a dato imputable. Esta fuente excluye casillas especiales y residentes en el extranjero, según los TXT.",
             "7. Revisar edades extremas, ceros y colas de LN/SV/NV/NS con contexto territorial. Los umbrales globales IQR dependen de la distribución de las celdas y no prueban errores; no se ajustaron por municipio o edad.",
             "8. La cobertura observada no prueba exhaustividad del universo electoral. Los CSV se leen con el parser de pandas y los encabezados se validan; no se hizo una segunda validación independiente del número de campos por cada línea física. No se consultaron fuentes externas ni se hizo limpieza, normalización, imputación o modelado.", "",
             "## Integridad de originales", "", table(["Año", "SHA-256 antes = después"], [[r['year'], '`' + r['sha256_before'] + '`'] for r in results]), "",
             "Los reportes y gráficos permanecen ignorados por las reglas existentes de `.gitignore`; se conservan localmente. No se modificó ese archivo. Los CSV auxiliares son evidencia de auditoría, no una base limpia.", ""]
    position = lines.index("## Método y reproducción")
    lines[position:position] = build_findings(results, output)
    (output / "initial_audit.md").write_text("\n".join(lines), encoding="utf-8")


def category_summary(output, year, column):
    return "; ".join(f"{value!r}: {count:,}" for value, count in load_frequencies(output, year, column).items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--chunk-size", type=int, default=100_000)
    parser.add_argument("--report-only", action="store_true", help="Regenera el informe desde resultados ya calculados.")
    args = parser.parse_args()
    if args.chunk_size <= 0:
        parser.error("--chunk-size debe ser positivo")
    output, charts = args.root / "analysis/reports", args.root / "analysis/charts"
    output.mkdir(parents=True, exist_ok=True)
    charts.mkdir(parents=True, exist_ok=True)
    results = []
    for year in YEARS:
        if args.report_only:
            result = json.loads((output / f"audit_{year}.json").read_text(encoding="utf-8"))
        else:
            paths = list((args.root / "data/raw").glob(f"*{year}.zip"))
            if len(paths) != 1:
                raise ValueError(f"Se esperaba un ZIP para {year}; encontrados: {paths}")
            result = audit_year(paths[0], year, args.chunk_size, output)
        results.append(result)
    create_report(results, output, charts, args.chunk_size)
    print(f"Informe guardado en {output / 'initial_audit.md'}", flush=True)


if __name__ == "__main__":
    main()
