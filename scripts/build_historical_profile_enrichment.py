"""Caracteriza perfiles V1 multianuales desde Parquet validados; no lee CSV ni ajusta modelos."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/processed/participamx_multiyear'
OUTPUT = ROOT / 'data/processed/profile_enrichment_history'
PUBLIC = ROOT / 'public/data/profiles'
YEARS = [2009, 2012, 2015, 2018, 2021, 2024]
KEYS = ['election_year', 'EDOCVE', 'MPIOCVE', 'age_band', 'SEXO']
COUNTS = ['LN', 'SV', 'NV', 'NS', 'source_row_count', 'sex_2_source_rows', 'sex_2_nominal_count']
NAMES = {
    'young_favorable': 'Jóvenes con mayor participación', 'young_unfavorable': 'Jóvenes con menor participación',
    'adult_favorable': 'Adultos con mayor participación', 'adult_unfavorable': 'Adultos con menor participación',
    'older_favorable': 'Personas mayores con mayor participación', 'older_unfavorable': 'Personas mayores con menor participación',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value, check=False):
    content = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n'
    if path.exists():
        require(path.read_text(encoding='utf-8') == content, f'El destino existente difiere: {path}')
    else:
        require(not check, f'Falta el destino: {path}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')


def direction(sv, denominator, ref_sv, ref_denominator):
    if denominator == 0 or ref_denominator == 0:
        return None
    product = int(sv) * int(ref_denominator) - int(ref_sv) * int(denominator)
    return (product > 0) - (product < 0)


def supported(frame):
    return frame.LN.ge(100) & frame.specified_count.ge(100) & frame.source_row_count.ge(5)


def assert_counts(left, right, keys):
    a = left.groupby(keys, observed=True)[COUNTS].sum().sort_index()
    b = right.groupby(keys, observed=True)[COUNTS].sum().sort_index()
    pd.testing.assert_frame_equal(a, b, check_dtype=False, check_index_type=False)
    return len(a) * len(COUNTS)


def aggregate_cell(group, code, total_ln):
    if group.empty:
        return dict(code=code, status='missing', **{k: None for k in ['LN', 'SV', 'NV', 'NS', 'specifiedCount', 'sourceRows', 'nominalShare', 'participation', 'reference', 'deltaPp']}, availableCells=0, eligibleCells=0, undefinedCells=0)
    counts = {key: int(group[key].sum()) for key in COUNTS}
    den = counts['SV'] + counts['NV']
    rate = counts['SV'] / den if den else None
    reference = float((group.specified_count * group.national_rate).sum() / den) if den else None
    status = 'undefined' if not den else 'low_support' if counts['LN'] < 100 or den < 100 or counts['source_row_count'] < 5 else 'defined'
    return dict(code=code, status=status, **{k: counts[k] for k in ['LN', 'SV', 'NV', 'NS']},
                specifiedCount=den, sourceRows=counts['source_row_count'], nominalShare=counts['LN'] / total_ln,
                participation=rate, reference=reference, deltaPp=100 * (rate-reference) if den else None,
                availableCells=len(group), eligibleCells=int(supported(group).sum()), undefinedCells=int(group.specified_count.eq(0).sum()))


def audit_year(year):
    checkpoint_path = SOURCE / f'metadata/checkpoint_year_{year}.json'
    checkpoint = load(checkpoint_path)
    require(checkpoint['status'] == 'complete', 'Checkpoint multianual incompleto')
    inputs = {}
    for relative in [f'elections/{year}/tables/{name}.parquet' for name in ['segments', 'section_segments', 'national_references']] + [f'elections/{year}/profiles.json']:
        path = SOURCE / relative
        digest = sha(path)
        key = str(path.relative_to(ROOT))
        require(checkpoint['artifacts'].get(key) == digest, f'Fuente no conciliada con checkpoint: {key}')
        inputs[key] = digest
    parents = pd.read_parquet(SOURCE / f'elections/{year}/tables/segments.parquet')
    children = pd.read_parquet(SOURCE / f'elections/{year}/tables/section_segments.parquet')
    refs = pd.read_parquet(SOURCE / f'elections/{year}/tables/national_references.parquet')
    original = load(SOURCE / f'elections/{year}/profiles.json')['data']
    public_path = ROOT / f'public/data/participamx_multiyear/elections/{year}/profiles.json'
    require(load(public_path)['data'] == original, 'V1 público distinto del resultado validado')
    inputs[str(public_path.relative_to(ROOT))] = sha(public_path)
    require(not parents.duplicated(KEYS).any() and not children.duplicated(KEYS+['TIPOSEC']).any(), 'Claves duplicadas')
    require(set(children.TIPOSEC) <= {'U', 'R', 'M'}, 'Tipo de sección desconocido')
    for frame in [parents, children]:
        require(frame.election_year.eq(year).all(), 'Elección incorrecta')
        require(frame[COUNTS].ge(0).all().all(), 'Conteo negativo')
        require((frame.SV+frame.NV+frame.NS).eq(frame.LN).all(), 'Partición LN incorrecta')
        require((frame.SV+frame.NV).eq(frame.specified_count).all(), 'Denominador incorrecto')
    checks = assert_counts(parents, children, KEYS)
    # Las referencias se validan contra todos los conteos anteriores al soporte.
    reference_counts = parents.groupby(['age_band', 'SEXO'], observed=True)[COUNTS].sum().reset_index()
    checks += assert_counts(reference_counts, refs, ['age_band', 'SEXO'])
    require(np.allclose(refs.national_rate, refs.SV/(refs.SV+refs.NV), rtol=0, atol=1e-12, equal_nan=True), 'Referencia nacional incorrecta')
    matched = parents.merge(refs[['age_band','SEXO','SV','national_specified_count','national_rate']], on=['age_band','SEXO'], how='left', validate='many_to_one', suffixes=('','_checked'))
    require(matched.national_SV.eq(matched.SV_checked).all() and matched.national_specified_count.eq(matched.national_specified_count_checked).all(), 'Conteos de referencia del padre incorrectos')
    require(np.allclose(matched.national_rate,matched.national_rate_checked,rtol=0,atol=1e-12,equal_nan=True), 'Referencia del padre distinta de su elección')
    signed = parents.apply(lambda r: direction(r.SV, r.specified_count, r.national_SV, r.national_specified_count), axis=1)
    scope = parents.age_band.isin(['18-34', '35-59', '60-100']) & parents.SEXO.isin(['0', '1'])
    eligible = scope & supported(parents) & signed.notna() & signed.ne(0)
    require(parents.candidate_id.notna().equals(eligible), 'Soporte/asignación V1 diferentes')
    family = parents.age_band.map({'18-34': 'young', '35-59': 'adult', '60-100': 'older'})
    expected = family + signed.map(lambda d: '_favorable' if d == 1 else '_unfavorable')
    require(parents.loc[eligible, 'candidate_id'].eq(expected.loc[eligible]).all(), 'Regla de signo V1 diferente')
    joined = children.merge(parents[KEYS+['candidate_id', 'national_rate', 'national_SV', 'national_specified_count', 'direction', 'participation_delta']], on=KEYS, how='left', validate='many_to_one', indicator=True)
    require(joined._merge.eq('both').all(), 'Hijo sin padre')
    joined = joined.drop(columns='_merge')
    joined['child_direction'] = joined.apply(lambda r: direction(r.SV, r.specified_count, r.national_SV, r.national_specified_count), axis=1)
    joined['opposes_parent'] = joined.child_direction.notna() & joined.child_direction.ne(0) & joined.child_direction.ne(joined.direction)
    joined['child_delta'] = joined.SV.div(joined.specified_count.replace(0, np.nan)) - joined.national_rate
    return parents, joined, original, inputs, checks


def build_year(year):
    parents, children, original, inputs, checks = audit_year(year)
    profiles, reconciliations = [], []
    for profile_id, name in NAMES.items():
        base = next(p for p in original if p['profile_id'] == profile_id)
        parent = parents[parents.candidate_id.eq(profile_id)]
        group = children[children.candidate_id.eq(profile_id)]
        require(len(parent) == base['segments'] > 0, 'Cantidad V1 incorrecta')
        for field in COUNTS:
            require(int(group[field].sum()) == int(parent[field].sum()) == base[field], f'Conciliación {year}/{profile_id}/{field}')
            reconciliations.append(dict(year=year, profile_id=profile_id, field=field, difference=0))
        total = base['LN']
        cells = {
            'sexCells': [aggregate_cell(group[group.SEXO.eq(sex)], sex, total) for sex in ['0', '1']],
            'sectionCells': [aggregate_cell(group[group.TIPOSEC.eq(kind)], kind, total) for kind in ['U', 'R', 'M']],
            'jointCells': [{**aggregate_cell(group[group.SEXO.eq(sex) & group.TIPOSEC.eq(kind)], kind, total), 'sexCode': sex} for sex in ['0', '1'] for kind in ['U', 'R', 'M']],
        }
        eligible = group[supported(group)]
        flips = eligible[eligible.opposes_parent]
        sex_text = ' · '.join(f"{'Hombres' if c['code']=='0' else 'Mujeres'}: {c['participation']*100:.2f} %" if c['participation'] is not None else f"Sexo {c['code']}: sin denominador" for c in cells['sexCells'])
        section_text = ' · '.join(f"{dict(U='Urbana',R='Rural',M='Mixta')[c['code']]}: {c['participation']*100:.2f} %" if c['participation'] is not None else f"{c['code']}: sin denominador" for c in cells['sectionCells'])
        direction_text = 'por debajo' if profile_id.endswith('_unfavorable') else 'por encima'
        intro = f"En {year}, reúne segmentos de {base['age_band']} años con participación {direction_text} de la referencia nacional de su misma edad y sexo. Son agregados municipales, no personas individuales."
        quality = dict(nearReferenceShare=base['near_reference_fraction'], highNsShare=base['high_ns_fraction'], availableCells=len(group), eligibleCells=len(eligible), undefinedCells=int(group.specified_count.eq(0).sum()), signReversals=len(flips), reversalShare=len(flips)/len(eligible) if len(eligible) else None, reversalLN=int(flips.LN.sum()), reversalNominalShare=float(flips.LN.sum()/eligible.LN.sum()) if len(eligible) else None)
        profiles.append(dict(id=profile_id, name=name, ageBand=base['age_band'], subtitle=f"{base['age_band']} años · participación {direction_text} de su referencia en {year}.", description=intro,
            distinctive=f"En {year}: {base['participation_observed']*100:.2f} % de participación; diferencia {base['participation_delta']*100:+.2f} pp.", nameStatus='agreed',
            participation=base['participation_observed'], reference=base['matched_peer_reference'], deltaPp=base['participation_delta']*100, nominalShare=base['nominal_coverage'],
            counts={k: base[k] for k in ['LN','SV','NV','NS','specified_count','source_row_count']}, segments=base['segments'], municipalities=base['municipalities'], states=base['states'],
            findings=[f"En {year}, participación por sexo: {sex_text}.", f"En {year}, participación por tipo de sección electoral: {section_text}.", f"{base['near_reference_fraction']*100:.2f} % de los segmentos está a no más de 2 pp de su referencia; {len(flips):,} de {len(eligible):,} cruces con soporte cambian de signo frente al agregado. Son diferencias descriptivas, no causas."],
            sexAnalysis=f"Resultados de {year}. {sex_text}. Cada sexo tiene su referencia nacional propia.", sectionAnalysis=f"Resultados de {year}. {section_text}. U/R/M describe secciones electorales, no residencia individual. La referencia conserva edad y sexo; no es una referencia ajustada por U/R/M.",
            territoryAnalysis=f"Presente en {base['municipalities']:,} municipios y {base['states']} entidades de {year}. Los municipios se superponen entre fichas. No se supone continuidad de límites con otras elecciones.",
            **cells, quality=quality, additionalCategory=dict(code='2', status='unavailable_category' if year<2024 else 'low_support', value=None, explanation='SEXO=2 no está registrado en esta elección; su ausencia no significa cero personas.' if year<2024 else 'SEXO=2 permanece complementario en 2024, con LN=105; no se reparte entre H/M.'), sourceRefs=['v1','segments','sections','references']))
        aggregate = aggregate_cell(group, 'all', total)
        require(np.isclose(aggregate['reference'], base['matched_peer_reference'], rtol=0, atol=1e-12), 'Referencia agregada distinta de V1')
        for dimension in cells.values():
            for field, source_field in [('LN','LN'),('SV','SV'),('NV','NV'),('NS','NS'),('specifiedCount','specified_count'),('sourceRows','source_row_count')]:
                require(sum(c[field] for c in dimension if c[field] is not None) == base[source_field], 'Desglose no exhaustivo')
            require(np.isclose(sum(c['nominalShare'] for c in dimension if c['nominalShare'] is not None), 1, rtol=0, atol=1e-12), 'Composición no suma uno')
    sources = {key: dict(path=str(SOURCE.relative_to(ROOT)/f'elections/{year}'/relative), sha256=sha(SOURCE/f'elections/{year}'/relative)) for key,relative in dict(v1='profiles.json',segments='tables/segments.parquet',sections='tables/section_segments.parquet',references='tables/national_references.parquet').items()}
    heterogeneity = dict(eligibleCells=sum(p['quality']['eligibleCells'] for p in profiles), signReversals=sum(p['quality']['signReversals'] for p in profiles), bothBeyond2Pp=int((children.candidate_id.notna() & supported(children) & children.opposes_parent & children.child_delta.abs().gt(.02) & children.participation_delta.abs().gt(.02)).sum()), unit='municipality_age_band_sex_section_type')
    payload = dict(schemaVersion='profiles-enriched-1',year=year,rateUnit='proportion',namesStatus='agreed',profiles=profiles,transversalFinding=None,heterogeneity=heterogeneity,sources=sources)
    if year == 2024:
        previous = load(PUBLIC/'enriched-2024.json')
        for p in profiles:
            old = next(v for v in previous['profiles'] if v['id'] == p['id'])
            for field in ['counts','quality','sexCells','sectionCells','jointCells']:
                if field == 'counts': require(p[field] == old[field], 'Regresión de conteos 2024')
                else:
                    a, b = p[field], old[field]
                    rows = [(x,next(y for y in b if y['code']==x['code'] and y.get('sexCode')==x.get('sexCode'))) for x in a] if isinstance(a,list) else [(a,b)]
                    for x,y in rows:
                        for key in x:
                            require(x[key] == y[key] if not isinstance(x[key],float) else np.isclose(x[key],y[key],rtol=0,atol=1e-10), f'Regresión 2024 {field}/{key}')
        payload = previous  # Se conserva también la edición revisada y V2.1, sin sobrescribirlos.
        inputs[str((PUBLIC/'enriched-2024.json').relative_to(ROOT))] = sha(PUBLIC/'enriched-2024.json')
    audit = dict(year=year,election_type='presidential' if year in [2012,2018,2024] else 'midterm',v1_profiles=6,age=True,sex=sorted(parents.SEXO.unique()),section_types=sorted(children.TIPOSEC.unique()),nominal_composition=True,participation=True,counts=True,joint_sex_section=True,territorial_context=True,export_before=year==2024,export_after=True,original_segments=len(parents),supported_segments=int(parents.candidate_id.notna().sum()),municipalities=parents.loc[parents.candidate_id.notna(),['EDOCVE','MPIOCVE']].drop_duplicates().shape[0],LN=int(parents.loc[parents.candidate_id.notna(),'LN'].sum()),nominal_fraction=float(parents.loc[parents.candidate_id.notna(),'LN'].sum()/parents.LN.sum()),child_cells=int(children.candidate_id.notna().sum()),low_support_child_cells=int((children.candidate_id.notna() & ~supported(children)).sum()),undefined_child_cells=int((children.candidate_id.notna() & children.specified_count.eq(0)).sum()),source_checks=checks,inputs=inputs)
    return payload, audit, reconciliations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-only', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    require((SOURCE/'_SUCCESS').exists() and load(SOURCE/'metadata/run_manifest.json')['status']=='validated', 'Fuente multianual no validada')
    coverage, rows, inputs, artifacts = [], [], {}, {}
    for year in YEARS:
        payload, audit, checks = build_year(year)
        coverage.append(audit); rows.extend(checks); inputs.update(audit['inputs'])
        if not args.audit_only:
            for path in [OUTPUT/f'elections/{year}/enriched.json'] + ([] if year==2024 else [PUBLIC/f'enriched-{year}.json']):
                save(path,payload,args.check); artifacts[str(path.relative_to(ROOT))]=sha(path)
        print(f"{year}: {audit['supported_segments']} segmentos, {audit['municipalities']} municipios; conciliación sin diferencias")
    save(OUTPUT/'coverage.json',coverage,args.check)
    save(OUTPUT/'reconciliation.json',rows,args.check)
    if not args.audit_only:
        save(OUTPUT/'manifest.json',dict(status='validated',inputs=inputs,artifacts=artifacts,years=YEARS,original_csv_reads=0,model_fits=0,parent_assignment='V1 unchanged; exact integer cross products; LN>=100,D>=100,source_rows>=5'),args.check)
        save(OUTPUT/'_SUCCESS',dict(status='validated',years=YEARS),args.check)


if __name__ == '__main__':
    main()
