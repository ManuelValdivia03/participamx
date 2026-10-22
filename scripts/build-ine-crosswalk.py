"""Build nominal crosswalks from the local ZIP audit; no fuzzy or numeric fallback.

Usage: python scripts/build-ine-crosswalk.py path/to/auditoria.json
The audit stores names, original INE codes and name candidates for each year.
"""
import collections
import hashlib
import json
import pathlib
import sys

audit = pathlib.Path(sys.argv[1])
root = pathlib.Path(__file__).resolve().parent.parent
output = root / 'public/data/ine-crosswalk'
output.mkdir(exist_ok=True)
states = {f'{i:02}': {'stateCode': f'{i:02}', 'years': {}} for i in range(1, 33)}
summary = []
for row in json.loads(audit.read_text(encoding='utf-8')):
    if row['special']:
        continue
    year = row['years'][0]
    reverse = collections.defaultdict(list)
    unresolved = []
    for item in row['municipalities']:
        candidates = item['same_name_map_candidates']
        if len(candidates) == 1:
            reverse[candidates[0]].append(item)
        else:
            unresolved.append({'ineCode': item['code'], 'ineNames': item['names'], 'candidateInegiCodes': candidates,
                               'reason': 'ambiguous-name' if candidates else 'name-not-found'})
    count = 0
    for code, payload in states.items():
        mapped = {}
        for inegi, items in reverse.items():
            if inegi[:2] != code:
                continue
            if len(items) != 1:
                unresolved.extend({'ineCode': i['code'], 'ineNames': i['names'], 'candidateInegiCodes': [inegi],
                                   'reason': 'multiple-ine-records'} for i in items)
                continue
            item = items[0]
            mapped[inegi] = {'ineCode': item['code'], 'ineName': item['names'][0], 'method': 'unique-normalized-name'}
            count += 1
        payload['years'][year] = mapped
    summary.append({'year': year, 'archive': row['archive'], 'ineMunicipalities': row['municipality_count'],
                    'mapped': count, 'unresolved': unresolved})
for state, data in states.items():
    (output / f'{state}.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
(output / 'metadata.json').write_text(json.dumps({
    'source': 'ZIP DatosAbiertos DECEyEC Conteos Censales proporcionados por el usuario; diccionarios EDOCVE y MPIOCVE (claves INE).',
    'method': 'Nombre único normalizado dentro de la misma entidad; equivalencia nominal, no homologación histórica de límites. No se utiliza coincidencia numérica ni aproximación difusa.',
    'auditSha256': hashlib.sha256(audit.read_bytes()).hexdigest(), 'years': summary,
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print([(r['year'], r['mapped'], len(r['unresolved'])) for r in summary])
