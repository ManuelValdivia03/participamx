"""Limpieza técnica reversible de los seis ZIP auditados de ParticipaMX.

Conserva las 16 columnas originales como texto y añade campos derivados.
No elimina, imputa, agrupa edades, normaliza estadísticamente ni entrena modelos.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import time
import warnings
import zipfile

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq

YEARS = (2009, 2012, 2015, 2018, 2021, 2024)
EXPECTED_ROWS = 54_872_712
SCHEMA_VERSION = "1.0.0"
RULE_VERSION = "1.0.0"
ORIGINAL_COLUMNS = "AELEC FELECCION EDOCVE EDONOM MPIOCVE MPIONOM SECCION TIPOSEC DEF DEL SEXO EDAD LN SV NV NS".split()
COUNT_COLUMNS = ["LN", "SV", "NV", "NS"]
TYPED_COLUMNS = {"EDAD": "age_value", "LN": "registered_count", "SV": "voted_count",
                 "NV": "not_voted_count", "NS": "unspecified_count"}
FLAG_COLUMNS = ["is_federal_district_missing", "is_local_district_missing",
                "age_over_100", "age_over_120", "age_iqr_outlier",
                "ln_iqr_outlier", "sv_iqr_outlier", "nv_iqr_outlier", "ns_iqr_outlier",
                "count_iqr_outlier", "state_name_trimmed", "municipality_name_trimmed"]
PARTITION_SCHEMA = pa.schema([pa.field("election_year", pa.int16()), pa.field("state_code", pa.string())])


class ValidationError(RuntimeError):
    """Una discrepancia impide declarar válido el conjunto generado."""


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def save_csv(path, fields, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def output_schema():
    fields = [pa.field(name, pa.string(), nullable=False) for name in ORIGINAL_COLUMNS]
    fields += [pa.field(name, pa.int64(), nullable=False) for name in TYPED_COLUMNS.values()]
    fields += [pa.field(name, pa.string()) for name in (
        "federal_district_code", "local_district_code",
        "federal_district_missing_reason", "local_district_missing_reason")]
    fields += [pa.field(name, pa.string(), nullable=False) for name in ("state_name_label", "municipality_name_label")]
    fields += [pa.field("district_reference_year", pa.int16(), nullable=False)]
    fields += [pa.field(name, pa.bool_(), nullable=False) for name in FLAG_COLUMNS]
    fields += [pa.field(name, pa.string(), nullable=False) for name in ("source_archive", "source_member")]
    fields += [pa.field("source_record", pa.int64(), nullable=False)]
    fields += [pa.field(name, pa.string(), nullable=False) for name in ("source_sha256", "schema_version", "cleaning_rule_version")]
    return pa.schema(fields, metadata={
        b"original_columns": json.dumps(ORIGINAL_COLUMNS).encode(),
        b"schema_version": SCHEMA_VERSION.encode(), b"cleaning_rule_version": RULE_VERSION.encode(),
        b"description": "Originales textuales y derivados técnicos; sin imputación ni normalización estadística".encode("utf-8"),
    })


def open_dataset(output):
    """Abre Parquet conservando el tipo texto de la partición territorial."""
    output = Path(output)
    require((output / "_SUCCESS").is_file(), "El conjunto no tiene una validación completa (_SUCCESS ausente).")
    return ds.dataset(output / "records", format="parquet",
                      partitioning=ds.partitioning(PARTITION_SCHEMA, flavor="hive"))


def load_baselines(root, expected_total):
    baselines = {}
    for year in YEARS:
        path = root / f"analysis/reports/audit_{year}.json"
        audit = json.loads(path.read_text(encoding="utf-8"))
        require(audit["year"] == year, f"Año incorrecto en {path}")
        require(audit["sha256_before"] == audit["sha256_after"], f"Integridad de auditoría fallida: {year}")
        require(audit["checks"]["equation_mismatch"] == 0 and audit["checks"]["equation_unevaluable"] == 0,
                f"La auditoría tiene excepciones aritméticas: {year}")
        baselines[year] = audit
    require(sum(a["rows"] for a in baselines.values()) == expected_total,
            f"La auditoría no coincide con los {expected_total:,} registros esperados.")
    return baselines


def read_chunks(archive, member, chunk_size):
    with archive.open(member) as stream, warnings.catch_warnings():
        warnings.simplefilter("error", pd.errors.ParserWarning)
        yield from pd.read_csv(stream, encoding="utf-8-sig", dtype=str, na_filter=False,
                               keep_default_na=False, skip_blank_lines=False, index_col=False,
                               on_bad_lines="error", chunksize=chunk_size)


def parse_integers(values, name):
    """Rechaza formatos no enteros y desbordamientos, sin sustituir valores."""
    require(all(isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value) for value in values.unique()),
            f"{name}: se encontró un token que no es un entero literal.")
    try:
        return values.to_numpy(dtype=np.int64)
    except (ValueError, OverflowError) as error:
        raise ValidationError(f"{name}: conversión exacta a int64 imposible.") from error


def transform_chunk(chunk, year, archive_name, member, source_sha256, offset, statistics):
    """Añade derivados; todas las columnas originales mantienen su texto exacto."""
    require(chunk.columns.tolist() == ORIGINAL_COLUMNS, f"Esquema inesperado en {member}")
    require(not chunk.isna().any().any(), f"El parser introdujo nulos en originales: {member}")
    require(chunk["AELEC"].eq(str(year)).all(), f"Año diferente del ZIP en {member}")
    allowed_sex = {"0", "1", "2"} if year == 2024 else {"0", "1"}
    require(set(chunk["SEXO"].unique()) <= allowed_sex, f"Categoría SEXO no auditada en {member}")
    require(set(chunk["TIPOSEC"].unique()) <= {"U", "M", "R"}, f"Categoría TIPOSEC no auditada en {member}")
    for name in ("EDOCVE", "MPIOCVE", "SECCION"):
        require(all(value.isascii() and value.isdigit() and int(value) > 0 for value in chunk[name].unique()),
                f"Identificador inválido: {name} en {member}")
    require(all(1 <= int(value) <= 32 for value in chunk["EDOCVE"].unique()), f"Entidad fuera de rango en {member}")
    values = {name: parse_integers(chunk[name], name) for name in TYPED_COLUMNS}
    require((values["EDAD"] >= 18).all(), f"Edad menor de 18 no presente en la auditoría: {member}")
    for name in COUNT_COLUMNS:
        require((values[name] >= 0).all(), f"Conteo negativo en {name}: {member}")
        # Evita también desbordamientos en las sumas de comprobación.
        require((values[name] <= np.iinfo(np.int64).max // max(4, len(chunk))).all(),
                f"Conteo fuera del límite de cálculo exacto en {name}")
    require(np.array_equal(values["LN"], values["SV"] + values["NV"] + values["NS"]),
            f"LN != SV + NV + NS en {member}, bloque iniciado en {offset + 1}")
    arrays = {name: pa.array(chunk[name], type=pa.string(), from_pandas=False) for name in ORIGINAL_COLUMNS}
    for original, derived in TYPED_COLUMNS.items():
        arrays[derived] = pa.array(values[original], type=pa.int64())
    flags = {}
    for original, prefix in (("DEF", "federal"), ("DEL", "local")):
        tokens = chunk[original]
        blank = tokens.str.strip().eq("").to_numpy(dtype=bool)
        require(all(not token.strip() or (token.isascii() and token.isdigit() and int(token) > 0)
                    for token in tokens.unique()), f"Código distrital no auditado en {original}")
        arrays[f"{prefix}_district_code"] = pc.if_else(pa.array(blank), pa.scalar(None, type=pa.string()), arrays[original])
        reasons = np.full(len(chunk), None, dtype=object)
        reasons[blank] = "blank_space"
        reasons[tokens.eq("").to_numpy(dtype=bool)] = "empty_string"
        arrays[f"{prefix}_district_missing_reason"] = pa.array(reasons, type=pa.string())
        flags[f"is_{prefix}_district_missing"] = blank
    for original, prefix in (("EDONOM", "state"), ("MPIONOM", "municipality")):
        trimmed = chunk[original].str.strip()
        arrays[f"{prefix}_name_label"] = pa.array(trimmed, type=pa.string(), from_pandas=False)
        flags[f"{prefix}_name_trimmed"] = chunk[original].ne(trimmed).to_numpy(dtype=bool)
    arrays["district_reference_year"] = pa.array(np.full(len(chunk), 2023 if year == 2024 else 2021, dtype=np.int16))
    flags["age_over_100"] = values["EDAD"] > 100
    flags["age_over_120"] = values["EDAD"] > 120
    for name in ("EDAD", *COUNT_COLUMNS):
        stats = statistics[name]
        flag_name = "age_iqr_outlier" if name == "EDAD" else f"{name.lower()}_iqr_outlier"
        flags[flag_name] = (values[name] < stats["lower_fence"]) | (values[name] > stats["upper_fence"])
    flags["count_iqr_outlier"] = np.logical_or.reduce([flags[f"{c.lower()}_iqr_outlier"] for c in COUNT_COLUMNS])
    arrays.update({name: pa.array(flags[name], type=pa.bool_()) for name in FLAG_COLUMNS})
    constants = dict(source_archive=archive_name, source_member=member, source_sha256=source_sha256,
                     schema_version=SCHEMA_VERSION, cleaning_rule_version=RULE_VERSION)
    arrays.update({name: pa.repeat(value, len(chunk)) for name, value in constants.items()})
    arrays["source_record"] = pa.array(np.arange(offset + 1, offset + len(chunk) + 1, dtype=np.int64))
    schema = output_schema()
    return pa.Table.from_arrays([arrays[name] for name in schema.names], schema=schema), values


def table_profile(table):
    """Resume la copia leída de disco, independientemente del DataFrame de origen."""
    result = Counter(rows=table.num_rows)
    for original, derived in TYPED_COLUMNS.items():
        if original in COUNT_COLUMNS:
            result[f"sum_{original}"] = int(pc.sum(table[derived]).as_py())
            result[f"zero_{original}"] = int(pc.sum(pc.cast(pc.equal(table[derived], 0), pa.int64())).as_py())
    for name in FLAG_COLUMNS:
        result[name] = int(pc.sum(pc.cast(table[name], pa.int64())).as_py())
    sex_two = pc.equal(table["SEXO"], "2")
    result["sex_2_rows"] = int(pc.sum(pc.cast(sex_two, pa.int64())).as_py())
    result["sex_2_LN"] = int(pc.sum(pc.if_else(sex_two, table["registered_count"], 0)).as_py())
    return result


def source_profile(chunk, values):
    result = Counter(rows=len(chunk))
    for name in COUNT_COLUMNS:
        result[f"sum_{name}"] = int(values[name].sum())
        result[f"zero_{name}"] = int(np.count_nonzero(values[name] == 0))
    for original, prefix in (("DEF", "federal"), ("DEL", "local")):
        result[f"is_{prefix}_district_missing"] = int(chunk[original].str.strip().eq("").sum())
    for original, prefix in (("EDONOM", "state"), ("MPIONOM", "municipality")):
        result[f"{prefix}_name_trimmed"] = int(chunk[original].ne(chunk[original].str.strip()).sum())
    result["age_over_100"] = int(np.count_nonzero(values["EDAD"] > 100))
    result["age_over_120"] = int(np.count_nonzero(values["EDAD"] > 120))
    mask = chunk["SEXO"].eq("2").to_numpy(dtype=bool)
    result["sex_2_rows"] = int(np.count_nonzero(mask))
    result["sex_2_LN"] = int(values["LN"][mask].sum())
    return result


def verify_part(path, expected):
    """Comprueba todo el bloque serializado, incluidas las 16 columnas y procedencia."""
    with pq.ParquetFile(path) as parquet:
        stored = parquet.read()
    require(stored.schema.equals(expected.schema, check_metadata=True), f"Esquema alterado en {path}")
    require(stored.equals(expected), f"Valores, orden o procedencia alterados en {path}")
    counts = [stored[TYPED_COLUMNS[c]].to_numpy() for c in COUNT_COLUMNS]
    require(np.array_equal(counts[0], counts[1] + counts[2] + counts[3]), f"Ecuación alterada en {path}")
    return table_profile(stored)


def baseline_checks(year, source, stored, audit):
    require(source["rows"] == stored["rows"] == audit["rows"], f"Número de filas incorrecto en {year}")
    profiles = {p["column"]: p for p in audit["profiles"]}
    for name in COUNT_COLUMNS:
        require(source[f"sum_{name}"] == stored[f"sum_{name}"] == audit["statistics"][name]["total"],
                f"Suma de {name} diferente de la auditoría en {year}")
        require(source[f"zero_{name}"] == stored[f"zero_{name}"] == audit["statistics"][name]["zero_count"],
                f"Ceros de {name} diferentes de la auditoría en {year}")
    for original, flag in (("DEF", "is_federal_district_missing"), ("DEL", "is_local_district_missing")):
        require(source[flag] == stored[flag] == profiles[original]["missing"], f"Faltantes de {original} diferentes en {year}")
    for name in ("EDAD", *COUNT_COLUMNS):
        stats = audit["statistics"][name]
        flag = "age_iqr_outlier" if name == "EDAD" else f"{name.lower()}_iqr_outlier"
        require(stored[flag] == stats["lower_outliers"] + stats["upper_outliers"], f"Atípicos diferentes en {year}/{name}")
    for name in source:
        require(source[name] == stored[name], f"Resumen de origen y salida diferente en {year}/{name}")


def aggregate_profiles(profiles):
    result = Counter()
    for profile in profiles:
        result.update(profile)
    return result


def write_report(output, manifest, state_rows, yearly):
    """Documenta resultados calculados y decisiones que siguen pendientes."""
    root = Path(manifest["root"])
    report_path = root / "analysis/reports/technical_cleaning.md"
    total = sum(profile["rows"] for profile in yearly.values())
    all_counts = aggregate_profiles(yearly.values())
    def markdown_table(headers, rows):
        return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
                          *("| " + " | ".join(map(str, row)) + " |" for row in rows)])
    sections = ["# Resultado de la limpieza técnica de ParticipaMX", "",
        f"Estado: **validado**. Se conservaron **{total:,} registros**, las 16 columnas originales y todos los conteos y ceros. Se generaron {len(manifest['parts'])} archivos Parquet en {manifest['state_partitions']} particiones año–entidad. Esta ejecución no excluye, imputa, agrupa edades, selecciona variables definitivas, normaliza estadísticamente ni ejecuta modelos.", "",
        "## Ubicación y reproducción", "", f"Conjunto: `{output.relative_to(root).as_posix()}`. Datos: `records/`; contrato, manifiestos y evidencia: `metadata/`. El marcador `_SUCCESS` se escribe exclusivamente después de validar todos los archivos. Los originales y `src/` no se modifican; el script no crea commits.", "",
        "```powershell", ".venv/Scripts/python.exe -m pip install -r analysis/scripts/requirements.txt",
        ".venv/Scripts/python.exe analysis/scripts/clean_data.py --chunk-size 100000", "```", "",
        "Una segunda ejecución debe elegir un destino nuevo con `--output data/processed/technical_cleaned_v2`: el programa rechaza sobrescribir cualquier directorio existente. Los Parquet se comprimen con Zstandard, con diccionarios y una partición por elección y entidad. No hay agregación de registros. La memoria depende del bloque y sus copias de validación, no del conjunto completo.", "",
        "## Transformaciones ejecutadas", "",
        "Las 16 columnas originales mantienen exactamente su texto parseado del CSV, incluidos espacios, ceros iniciales y el texto de FELECCION. Los derivados `age_value`, `registered_count`, `voted_count`, `not_voted_count` y `unspecified_count` son int64. `DEF`, `DEL` y `SEXO` se conservan como códigos, sin asignarles distancias numéricas.", "",
        "`federal_district_code` y `local_district_code` son texto nullable; los espacios/vacíos originales siguen en DEF/DEL. Las razones son `blank_space` o `empty_string`; los casos presentes tienen razón nula. Las etiquetas `state_name_label` y `municipality_name_label` sólo eliminan espacios periféricos y conservan las etiquetas originales.", "",
        "Se añadieron banderas de distritos faltantes, EDAD>100, EDAD>120, IQR de edad, IQR de LN/SV/NV/NS por separado, su unión `count_iqr_outlier` y etiquetas con espacios retirados. Los umbrales exactos por año provienen de la auditoría y están congelados en `metadata/iqr_thresholds.json`; no se recalculan por bloque. NS con IQR=0 marca todo valor positivo; esa bandera no representa error ni exclusión.", "",
        "La referencia se conserva como `district_reference_year`: 2021 para elecciones 2009–2021 y 2023 para 2024. Los diccionarios originales se guardan en `metadata/source_dictionaries.json`. La procedencia incluye `source_archive`, `source_member`, `source_record` (desde 1 tras el encabezado), `source_sha256`, `schema_version` y `cleaning_rule_version`.", "",
        "## Validaciones obligatorias", "",
        markdown_table(["Año", "Filas origen = salida = auditoría", "DEF nulo derivado", "DEL nulo derivado", "SEXO=2 conservado", "SHA-256 antes = después"],
            [[year, f"{p['rows']:,}", p['is_federal_district_missing'], p['is_local_district_missing'], p['sex_2_rows'], "Sí"] for year, p in yearly.items()]), "",
        "Cada bloque escrito se volvió a leer desde Parquet y se comparó por igualdad exacta de todas las columnas, tipos, orden y procedencia. Se comprobó LN = SV + NV + NS tanto en el origen como en la copia persistida: cero excepciones; una discrepancia habría detenido la ejecución sin escribir `_SUCCESS`. No se detectó pérdida de filas, modificación de conteos o introducción de nulos en las columnas originales.", "",
        f"Se conciliaron **{len(state_rows)} pares año–entidad**. `metadata/state_validation.csv` contiene filas, sumas de los cuatro conteos y cantidades de ceros de origen y salida, además de sus diferencias (todas cero). Cada CSV conserva su número de registros auditado; cada archivo de salida tiene un intervalo de procedencia no superpuesto. No se convirtieron claves originales ni se hicieron uniones; no se realiza una nueva búsqueda de duplicados de negocio, cuya auditoría permanece aplicable a originales idénticos.", "",
        markdown_table(["Año", "LN origen = salida", "SV origen = salida", "NV origen = salida", "NS origen = salida"],
            [[year, *[f"{p[f'sum_{c}']:,}" for c in COUNT_COLUMNS]] for year, p in yearly.items()]), "",
        f"Se conservaron {all_counts['sex_2_rows']} registros SEXO=2, con LN={all_counts['sex_2_LN']}; se conservaron todos los ceros de los cuatro conteos (ver conciliación). Los SHA-256 inicial y final de los seis ZIP coinciden también con la auditoría. Se verificaron además el inventario final de Parquet, sus filas, esquema y hashes. `metadata/run_manifest.json` registra las versiones de Python y dependencias, hashes de scripts/documentos/auditorías, parámetros e intervalos de cada archivo.", "",
        "## Indicadores de revisión conservados", "",
        markdown_table(["Año", "EDAD>100", "EDAD>120", "IQR edad", "IQR LN", "IQR SV", "IQR NV", "IQR NS", "Al menos un conteo IQR", "Etiquetas municipales ajustadas"],
            [[year, *[p[name] for name in ['age_over_100', 'age_over_120', 'age_iqr_outlier', 'ln_iqr_outlier', 'sv_iqr_outlier', 'nv_iqr_outlier', 'ns_iqr_outlier', 'count_iqr_outlier', 'municipality_name_trimmed']]] for year, p in yearly.items()]), "",
        "Estos conteos corresponden a filas/celdas; las banderas se pueden superponer y no deben sumarse como registros únicos. Las edades exactas, incluidas las extremas, siguen presentes. Ninguna bandera desencadena corrección, exclusión o agrupación de edad.", "",
        "## Incidencias y limitaciones", "",
        f"Errores de ejecución o validación: **{len(manifest['errors'])}**. Las incidencias de completitud, formato y revisión se documentan por año y entidad en `metadata/quality_summary.csv`; `metadata/incidents.json` separa estos hallazgos conservados de los errores fatales. Los faltantes de 2009/2012 siguen representados como un espacio en los originales y los de DEL 2024 como texto vacío. La ejecución no determina sus distritos correctos.", "",
        "Las claves territoriales permanecen como texto. Para abrir las particiones usando PyArrow, usar `open_dataset()` de `clean_data.py`, que declara `state_code` como texto; evitar inferir el tipo de esa partición a partir del nombre numérico. EDOCVE y MPIOCVE siguen siendo texto también dentro de cada archivo. El contrato detallado está en `metadata/schema.json` y `metadata/schema.md`.", "",
        "No se validaron catálogos externos ni correspondencias INE/INEGI. No se interpretó FELECCION, no se investigó la causa de edades extremas y no se impuso un máximo biológico. El conjunto y los reportes son locales según las reglas existentes de .gitignore. Las validaciones exactas se hicieron sobre los archivos escritos en esta ejecución; futuras modificaciones necesitan una nueva verificación.", "",
        "## Decisiones metodológicas pendientes", "",
        "1. Confirmar edades extremas y posibles códigos especiales con la fuente antes de corregir, agrupar o excluir.",
        "2. Obtener catálogos versionados y correspondencias de secciones/distritos para recuperar faltantes y comparar marcos 2021/2023; resolver relaciones múltiples sin imputar por moda o arrastre.",
        "3. Confirmar la continuidad territorial municipal y su relación con las geometrías; usar EDOCVE + MPIOCVE y el año, no nombres como claves.",
        "4. Confirmar la interpretación de las fechas, especialmente 06/02/2024, preservada como texto.",
        "5. Acordar la presentación histórica de SEXO=2 sin recodificarlo o interpretar su ausencia previa como cero personas.",
        "6. Definir población objetivo, denominadores y tratamiento analítico de NS, así como cobertura y sensibilidad. No se generaron tasas ni variables definitivas para clustering.", ""]
    report_path.write_text("\n".join(sections), encoding="utf-8")
    (output / "metadata/technical_cleaning.md").write_text("\n".join(sections), encoding="utf-8")
    return report_path


def write_schema_docs(output):
    descriptions = {name: f"Columna original {name}, texto exacto después del parseo CSV; sin modificación." for name in ORIGINAL_COLUMNS}
    descriptions.update({derived: f"Conversión exacta a int64 de {original}; sin imputación ni recorte." for original, derived in TYPED_COLUMNS.items()})
    descriptions.update({
        "federal_district_code": "DEF como texto; nulo sólo cuando el original está vacío o tiene únicamente espacios.",
        "local_district_code": "DEL como texto; nulo sólo cuando el original está vacío o tiene únicamente espacios.",
        "federal_district_missing_reason": "blank_space o empty_string si falta DEF; nulo si está presente.",
        "local_district_missing_reason": "blank_space o empty_string si falta DEL; nulo si está presente.",
        "state_name_label": "EDONOM sin espacios periféricos; el original permanece intacto.",
        "municipality_name_label": "MPIONOM sin espacios periféricos; el original permanece intacto.",
        "district_reference_year": "Marco DERFE indicado por el diccionario: 2021 o 2023, distinto del año electoral.",
        "source_archive": "Nombre del ZIP original.", "source_member": "Ruta completa del CSV dentro del ZIP.",
        "source_record": "Ordinal de registro desde 1 sin incluir el encabezado; no es una línea física.",
        "source_sha256": "SHA-256 del ZIP de origen, comprobado antes y después de procesarlo.",
        "schema_version": "Versión del contrato de datos.", "cleaning_rule_version": "Versión de las reglas técnicas aplicadas.",
    })
    for name in FLAG_COLUMNS:
        descriptions[name] = {
            "is_federal_district_missing": "DEF vacío o compuesto sólo de espacios.",
            "is_local_district_missing": "DEL vacío o compuesto sólo de espacios.",
            "age_over_100": "EDAD estrictamente mayor de 100; sólo revisión.",
            "age_over_120": "EDAD estrictamente mayor de 120; sólo revisión.",
            "age_iqr_outlier": "EDAD fuera de los límites IQR de su año, sin alterar la edad.",
            "count_iqr_outlier": "Unión lógica de ln/sv/nv/ns_iqr_outlier; no identifica errores comprobados.",
            "state_name_trimmed": "La etiqueta estatal derivada difiere por espacios periféricos.",
            "municipality_name_trimmed": "La etiqueta municipal derivada difiere por espacios periféricos.",
        }.get(name, "Conteo original fuera de los límites IQR de su año; consultar iqr_thresholds.json.")
    fields = [dict(name=field.name, type=str(field.type), nullable=field.nullable, description=descriptions[field.name]) for field in output_schema()]
    partitions = [dict(name="election_year", type="int16", description="Año electoral validado contra AELEC."),
                  dict(name="state_code", type="string", description="Alias textual exacto de EDOCVE; no rellenado con ceros.")]
    save_json(output / "metadata/schema.json", dict(schema_version=SCHEMA_VERSION, original_columns=ORIGINAL_COLUMNS, fields=fields, partitions=partitions))
    rows = ["# Contrato del conjunto técnico", "", "Las primeras 16 columnas conservan el texto original. Los derivados no reemplazan el origen. Las particiones no agrupan ni eliminan filas.", "",
            "| Campo | Tipo Arrow | Nullable | Significado |", "| --- | --- | --- | --- |"]
    rows += [f"| `{field['name']}` | {field['type']} | {'Sí' if field['nullable'] else 'No'} | {field['description']} |" for field in fields]
    rows += ["", "Particiones Hive: `election_year` (int16) y `state_code` (texto). No están duplicadas dentro de los archivos; se recuperan con particionado explícito en `open_dataset()`.", "",
             "Las filas no representan personas individuales. La identidad de procedencia es source_archive + source_member + source_record; EDOCVE + MPIOCVE identifica un municipio en el marco y año correspondientes. La clave de negocio continúa pendiente de validación metodológica.", ""]
    (output / "metadata/schema.md").write_text("\n".join(rows), encoding="utf-8")


def run_cleaning(root, output, chunk_size=100_000, expected_total=EXPECTED_ROWS):
    root, output = Path(root).resolve(), Path(output).resolve()
    require(chunk_size > 0, "El tamaño de bloque debe ser positivo.")
    require(output.is_relative_to(root / "data/processed"), "El destino debe estar dentro de data/processed/.")
    require(not output.exists(), f"El destino ya existe; elegir otro con --output: {output}")
    baselines = load_baselines(root, expected_total)
    output.mkdir(parents=True)
    (output / "metadata").mkdir()
    started = time.monotonic()
    manifest = dict(status="running", root=str(root), output=str(output), expected_rows=expected_total,
                    chunk_size=chunk_size, schema_version=SCHEMA_VERSION, cleaning_rule_version=RULE_VERSION,
                    started_at_utc=datetime.now(timezone.utc).isoformat(),
                    versions=dict(python=platform.python_version(), pandas=pd.__version__, numpy=np.__version__, pyarrow=pa.__version__),
                    input_hashes={}, sources=[], parts=[], errors=[])
    manifest_path = output / "metadata/run_manifest.json"
    save_json(manifest_path, manifest)
    source_by_state, stored_by_state = defaultdict(Counter), defaultdict(Counter)
    try:
        for relative in ["analysis/cleaning_plan.md", "analysis/reports/initial_audit.md", "analysis/scripts/clean_data.py", *[f"analysis/reports/audit_{year}.json" for year in YEARS]]:
            manifest["input_hashes"][relative] = file_hash(root / relative)
        write_schema_docs(output)
        save_json(output / "metadata/iqr_thresholds.json", {year: {c: {key: baseline["statistics"][c][key] for key in ("q1", "q3", "lower_fence", "upper_fence")} for c in ["EDAD", *COUNT_COLUMNS]} for year, baseline in baselines.items()})
        save_json(output / "metadata/source_dictionaries.json", {year: baseline["dictionaries"] for year, baseline in baselines.items()})
        for year, audit in baselines.items():
            path = root / "data/raw" / audit["archive"]
            before = file_hash(path)
            require(before == audit["sha256_after"], f"El ZIP {year} difiere del auditado; no se procesará.")
            source_info = dict(year=year, archive=path.name, sha256_before=before, sha256_after=None, rows=0)
            manifest["sources"].append(source_info)
            with zipfile.ZipFile(path) as archive:
                members = [m.filename for m in archive.infolist() if m.filename.lower().endswith(".csv")]
                expected_files = {entry["member"]: entry for entry in audit["files"]}
                require(len(members) == len(expected_files) and set(members) == set(expected_files), f"Inventario CSV distinto en {year}")
                for member_index, member in enumerate(members):
                    with archive.open(member) as stream:
                        header = next(csv.reader([stream.readline().decode("utf-8-sig").strip("\r\n")]))
                    require(header == ORIGINAL_COLUMNS, f"Encabezado inesperado en {member}")
                    offset = 0
                    for chunk_index, chunk in enumerate(read_chunks(archive, member, chunk_size)):
                        states = chunk["EDOCVE"].unique()
                        require(len(states) == 1, f"El CSV auditado ya no tiene una única entidad: {member}")
                        state = str(states[0])
                        require(state == expected_files[member]["states"], f"Entidad diferente de la auditada en {member}")
                        key = (year, state)
                        table, values = transform_chunk(chunk, year, path.name, member, before, offset, audit["statistics"])
                        source_by_state[key].update(source_profile(chunk, values))
                        destination = output / f"records/election_year={year}/state_code={state}/part-{member_index:02d}-{chunk_index:05d}.parquet"
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        require(not destination.exists(), f"No se sobrescribirá {destination}")
                        pq.write_table(table, destination, compression="zstd", compression_level=3, use_dictionary=True,
                                       row_group_size=chunk_size, write_statistics=True)
                        stored_profile = verify_part(destination, table)
                        stored_by_state[key].update(stored_profile)
                        manifest["parts"].append(dict(path=destination.relative_to(output).as_posix(), year=year,
                            state_code=state, source_member=member, first_record=offset + 1,
                            last_record=offset + len(chunk), rows=len(chunk), bytes=destination.stat().st_size,
                            sha256=file_hash(destination)))
                        offset += len(chunk)
                    require(offset == expected_files[member]["rows"], f"Filas diferentes del CSV auditado: {member}")
                    source_info["rows"] += offset
                    print(f"{year}: CSV {member_index + 1}/{len(members)}, {offset:,} filas persistidas y verificadas", flush=True)
            source_info["sha256_after"] = file_hash(path)
            require(source_info["sha256_after"] == before, f"El ZIP cambió durante la ejecución: {year}")
            source = aggregate_profiles(p for (y, _), p in source_by_state.items() if y == year)
            stored = aggregate_profiles(p for (y, _), p in stored_by_state.items() if y == year)
            baseline_checks(year, source, stored, audit)
            save_json(manifest_path, manifest)
        require(sum(p["rows"] for p in stored_by_state.values()) == expected_total, "Total persistido diferente del esperado.")
        state_rows, quality_rows = [], []
        for key, source in sorted(source_by_state.items()):
            year, state = key
            stored = stored_by_state[key]
            row = dict(election_year=year, EDOCVE=state)
            for metric in ("rows", *[f"sum_{c}" for c in COUNT_COLUMNS], *[f"zero_{c}" for c in COUNT_COLUMNS]):
                row[f"source_{metric}"] = source[metric]
                row[f"output_{metric}"] = stored[metric]
                row[f"difference_{metric}"] = stored[metric] - source[metric]
                require(row[f"difference_{metric}"] == 0, f"Diferencia por año/entidad: {year}/{state}/{metric}")
            state_rows.append(row)
            quality_rows.append(dict(election_year=year, EDOCVE=state, rows=stored["rows"],
                                     **{name: stored[name] for name in [*FLAG_COLUMNS, "sex_2_rows", "sex_2_LN"]}))
        save_csv(output / "metadata/state_validation.csv", list(state_rows[0]), state_rows)
        save_csv(output / "metadata/quality_summary.csv", list(quality_rows[0]), quality_rows)
        expected_paths = {part["path"] for part in manifest["parts"]}
        actual_paths = {p.relative_to(output).as_posix() for p in (output / "records").rglob("*.parquet")}
        require(expected_paths == actual_paths, "El inventario final de Parquet difiere del manifiesto.")
        for part in manifest["parts"]:
            path = output / part["path"]
            with pq.ParquetFile(path) as parquet:
                require(parquet.metadata.num_rows == part["rows"], f"Filas modificadas tras verificar: {path}")
                require(parquet.schema_arrow.equals(output_schema(), check_metadata=True), f"Esquema final distinto: {path}")
            require(file_hash(path) == part["sha256"], f"Archivo modificado tras verificar: {path}")
        yearly = {year: aggregate_profiles(p for (y, _), p in stored_by_state.items() if y == year) for year in YEARS}
        manifest.update(status="validated", finished_at_utc=datetime.now(timezone.utc).isoformat(),
                        seconds=round(time.monotonic() - started, 2), rows=expected_total,
                        output_bytes=sum(p["bytes"] for p in manifest["parts"]), state_partitions=len(stored_by_state),
                        yearly_summary={year: dict(profile) for year, profile in yearly.items()})
        save_json(output / "metadata/incidents.json", dict(errors=[], observed_quality_findings=quality_rows,
            interpretation="Los hallazgos se conservan con banderas; no son exclusiones ni errores demostrados por un IQR."))
        report_path = write_report(output, manifest, state_rows, yearly)
        save_json(manifest_path, manifest)
        (output / "_SUCCESS").write_text(json.dumps(dict(rows=expected_total, manifest_sha256=file_hash(manifest_path))), encoding="utf-8")
        print(f"VALIDADO: {expected_total:,} filas; {len(manifest['parts'])} Parquet; informe: {report_path}", flush=True)
        return manifest
    except Exception as error:
        manifest["status"] = "failed"
        manifest["errors"].append(dict(type=type(error).__name__, message=str(error)))
        save_json(manifest_path, manifest)
        save_json(output / "metadata/incidents.json", dict(errors=manifest["errors"], note="Ejecución incompleta: no utilizar records/; no se excluyeron filas para continuar."))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, help="Destino nuevo dentro de data/processed/.")
    parser.add_argument("--chunk-size", type=int, default=100_000)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output or root / "data/processed/technical_cleaned"
    if not output.is_absolute():
        output = root / output
    run_cleaning(root, output, args.chunk_size)


if __name__ == "__main__":
    main()
