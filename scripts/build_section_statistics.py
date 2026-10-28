"""Exporta U/R/M desde agregados descriptivos; no lee CSV ni registros limpios."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
YEARS = (2009, 2012, 2015, 2018, 2021, 2024)
FIELDS = ['LN', 'SV', 'NV', 'NS', 'source_row_count']
CHECK_FIELDS = FIELDS + ['sex_2_source_rows', 'sex_2_nominal_count']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def build(output, check=False, audit_only=False):
    sources = {}

    def read(relative, parquet=False):
        path = ROOT / relative
        sources[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        return pd.read_parquet(path) if parquet else json.loads(path.read_text(encoding='utf-8'))

    rows = read('data/processed/descriptive/municipality_section_type/table.parquet', True)
    municipalities = read('data/processed/descriptive/municipality/table.parquet', True)
    national = read('data/processed/descriptive/section_type_year/table.parquet', True)
    keys = ['election_year', 'EDOCVE', 'MPIOCVE']
    require(set(rows.election_year) == set(YEARS), 'Elecciones inesperadas')
    require(set(rows.TIPOSEC) == {'U', 'R', 'M'} and not rows[['TIPOSEC', *CHECK_FIELDS]].isna().any().any(), 'Categorías o conteos ausentes')
    require(not rows.duplicated(keys + ['TIPOSEC']).any(), 'Claves duplicadas')
    require((rows[CHECK_FIELDS] >= 0).all().all(), 'Conteos negativos')
    require((rows.LN == rows.SV + rows.NV + rows.NS).all(), 'LN no concilia')
    pd.testing.assert_frame_equal(rows.groupby(keys)[CHECK_FIELDS].sum().sort_index(), municipalities.set_index(keys)[CHECK_FIELDS].sort_index())
    pd.testing.assert_frame_equal(rows.groupby(['election_year', 'TIPOSEC'])[CHECK_FIELDS].sum().sort_index(), national.set_index(['election_year', 'TIPOSEC'])[CHECK_FIELDS].sort_index())

    def counts(frame):
        return {field: int(frame[field].sum()) for field in FIELDS}

    def profile(frame, code, name):
        return dict(code=code, name=name, complete=True, totals=counts(frame),
                    sections=[dict(section_type=kind, **counts(part)) for kind, part in sorted(frame.groupby('TIPOSEC'))])

    files, coverage = {}, []
    for year in YEARS:
        current = rows[rows.election_year.eq(year)]
        original = read(f'data/processed/participamx_multiyear/elections/{year}/section_statistics.json')
        require(original['election_year'] == year, 'Año nacional incorrecto')
        for row in original['data']:
            require(counts(current[current.TIPOSEC.eq(row['section_type'])]) == {field: row[field] for field in FIELDS}, 'Marginal nacional distinta')
        states = []
        for number in range(1, 33):
            code = str(number).zfill(2)
            part = current[current.EDOCVE.eq(str(number))]
            require(len(part) > 0, 'Entidad sin datos')
            summary = read(f'public/data/territorial/summaries/{year}/{code}.json')
            require(counts(part) == summary['totals'], 'Universo estatal diferente al Atlas')
            states.append(profile(part, code, summary['territory_name']))
            municipal = read(f'public/data/territorial/{year}/{code}.json')
            expected = {record['ine_code']: record for record in municipal['data']}
            records = []
            for municipality, cells in sorted(part.groupby('MPIOCVE'), key=lambda item: int(item[0])):
                ine_code = code + str(municipality).zfill(3)
                require(ine_code in expected, 'Clave municipal no disponible en Atlas')
                require(counts(cells) == expected[ine_code]['totals'], 'Universo municipal diferente al Atlas')
                records.append(profile(cells, ine_code, expected[ine_code]['municipality_name']))
            require(len(records) == len(expected), 'Cobertura municipal distinta al Atlas')
            files[f'{year}/{code}.json'] = dict(schema_version='section-statistics-1', election_year=year, state_code=code, data=records)
        summary = read(f'public/data/territorial/summaries/{year}/national.json')
        require(counts(current) == summary['totals'], 'Universo nacional diferente al Atlas')
        files[f'{year}/index.json'] = dict(schema_version='section-statistics-1', election_year=year, state_code=None,
                                         national=profile(current, 'national', 'México'), states=states)
        coverage.append(dict(election_year=year, states=len(states), municipalities=len(current[keys].drop_duplicates()),
                             observed_type_cells=len(current), absent_type_cells=3 * len(current[keys].drop_duplicates()) - len(current),
                             **counts(current)))
    print(json.dumps(coverage, ensure_ascii=False, indent=2))
    if audit_only:
        return
    encoded = {name: encode(value) for name, value in files.items()}
    encoded['manifest.json'] = encode(dict(schema_version='section-statistics-1', sources=sources, coverage=coverage,
        formulas=dict(composition='LN_type/LN_total', participation='SV_type/(SV_type+NV_type)'),
        files={name: hashlib.sha256(value).hexdigest() for name, value in encoded.items()}))
    # Se verifica todo antes de escribir; un destino diferente exige una ruta nueva.
    for name, content in encoded.items():
        path = output / name
        if check or path.exists():
            require(path.is_file() and path.read_bytes() == content, f'Destino ausente o distinto: {path}')
    if not check:
        for name, content in encoded.items():
            path = output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                with path.open('xb') as stream:
                    stream.write(content)
            require(path.read_bytes() == content, 'Error de lectura posterior')
    for name, digest in sources.items():
        require(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, f'Fuente modificada: {name}')
    print(f'{len(encoded)} archivos verificados; fuentes conservadas.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'public/data/territorial/sections')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args()
    build(args.output, args.check, args.audit_only)
