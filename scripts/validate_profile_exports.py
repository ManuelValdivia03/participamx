"""Comprueba los PDF/PNG realmente descargados; PyMuPDF sólo se usa para validar."""
import argparse
import json
import re
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', type=Path, default=Path('node_modules/.cache/profile-workflows-ui/downloads'))
parser.add_argument('--renderer-path', type=Path, default=Path('node_modules/.cache/pdf-render-minimal'))
args = parser.parse_args()
sys.path.insert(0, str(args.renderer_path.resolve()))
import pymupdf
from PIL import Image

profiles = json.loads(Path('public/data/profiles/enriched-2024.json').read_text(encoding='utf-8'))['profiles']
results = []
for profile in profiles:
    matches = [p for p in args.directory.glob('*.pdf') if '-previous-' not in p.name and profile['id'] in pymupdf.open(p).metadata.get('subject', '')]
    # La identidad se verifica en texto seleccionable, no por el número arbitrario del archivo.
    if not matches:
        matches = [p for p in args.directory.glob('*.pdf') if '-previous-' not in p.name and profile['id'] in pymupdf.open(p)[0].get_text()]
    assert len(matches) == 1, (profile['id'], matches)
    path = matches[0]
    with pymupdf.open(path) as document:
        assert len(document) == 2
        full_text = re.sub(r'\s+', ' ', ' '.join(page.get_text() for page in document))
        assert profile['name'] in full_text
        assert profile['id'] in document.metadata['subject'] and '2024' in full_text and 'INE' in full_text
        assert 'SEXO=2' not in full_text
        assert f"{profile['participation'] * 100:.2f} %" in full_text
        assert f"{profile['reference'] * 100:.2f} %" in full_text
        sign = '+' if profile['deltaPp'] > 0 else '-' if profile['deltaPp'] < 0 else ''
        assert f"{sign}{abs(profile['deltaPp']):.2f} pp" in full_text
        assert f"{profile['nominalShare'] * 100:.2f} %" in full_text
        for field in ['LN', 'SV', 'NV', 'NS', 'specified_count', 'source_row_count']:
            assert f"{profile['counts'][field]:,}" in full_text
        assert 'Descargar' not in full_text and 'Menú principal' not in full_text
        for index, page in enumerate(document):
            assert abs(page.rect.width - 595.28) < .05 and abs(page.rect.height - 841.89) < .05
            spans = [s for block in page.get_text('dict')['blocks'] if block['type'] == 0 for line in block['lines'] for s in line['spans']]
            assert len(spans) > 10 and any(span['size'] >= 17 for span in spans)
            for span in spans:
                x0, y0, x1, y1 = span['bbox']
                assert x0 >= 35 and y0 >= 18 and x1 <= page.rect.width - 26 and y1 <= page.rect.height - 15, (profile['id'], span)
            if profile['id'] == 'young_favorable':
                page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(args.directory / f'pdf_preview_page_{index + 1}.png')
        (args.directory / f'{profile["id"]}_extracted_text.txt').write_text(full_text, encoding='utf-8')
    png = path.with_suffix('.png')
    with Image.open(png) as image:
        assert image.size == (1600, 4526) and image.format == 'PNG'
        assert image.convert('RGBA').getextrema()[3] == (255, 255)
        assert len(image.convert('RGB').getcolors(maxcolors=1000000)) > 100
    results.append({'id': profile['id'], 'pdf': path.name, 'pages': 2, 'selectable_text': True, 'margins_checked': True, 'png': png.name, 'dimensions': [1600, 4526]})
(args.directory.parent / 'independent-export-validation.json').write_text(json.dumps({'status': 'passed', 'renderer': pymupdf.VersionBind, 'profiles': results}, indent=2), encoding='utf-8')
print(json.dumps({'status': 'passed', 'profiles': len(results), 'pdf_pages': 12, 'png_dimensions': [1600, 4526]}))
