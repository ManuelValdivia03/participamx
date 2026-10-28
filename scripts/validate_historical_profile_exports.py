"""Validación independiente de las 72 descargas reales: texto, cifras, márgenes y raster."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0,str(Path('node_modules/.cache/pdf-render-minimal').resolve()))
import pymupdf
from PIL import Image

CACHE = Path('node_modules/.cache/historical-profiles-ui')
downloads = CACHE/'downloads'
results = []
for year in [2009,2012,2015,2018,2021,2024]:
    payload = json.loads(Path(f'public/data/profiles/enriched-{year}.json').read_text(encoding='utf-8'))
    for index, profile in enumerate(payload['profiles']):
        paths = [p for p in downloads.glob(f'participamx_perfil_{index+1:02d}_*_{year}.pdf') if '-previous-' not in p.name]
        assert len(paths)==1, (year,profile['id'],paths)
        path=paths[0]
        with pymupdf.open(path) as document:
            assert len(document)==2
            text = re.sub(r'\s+', ' ', ' '.join(page.get_text() for page in document))
            assert profile['name'] in text and profile['id'] in document.metadata['subject'] and f'elección {year}' in text and 'INE' in text
            assert 'SEXO=2' not in text
            if year!=2024:
                assert '2024' not in text
            for field in ['participation','reference','nominalShare']:
                assert f"{profile[field]*100:.2f} %" in text, (year,profile['id'],field)
            sign = '+' if profile['deltaPp']>0 else '-' if profile['deltaPp']<0 else ''
            assert f"{sign}{abs(profile['deltaPp']):.2f} pp" in text
            for value in profile['counts'].values():
                assert f'{value:,}' in text
            for cell in profile['sexCells']+profile['sectionCells']:
                for field in ['participation','nominalShare']:
                    if cell[field] is not None:
                        assert f"{cell[field]*100:.2f} %" in text
            assert 'Descargar' not in text
            for page_index,page in enumerate(document):
                assert abs(page.rect.width-595.28)<.05 and abs(page.rect.height-841.89)<.05
                spans=[s for block in page.get_text('dict')['blocks'] if block['type']==0 for line in block['lines'] for s in line['spans']]
                assert len(spans)>10
                for span in spans:
                    x0,y0,x1,y1=span['bbox']
                    assert x0>=35 and y0>=18 and x1<=page.rect.width-26 and y1<=page.rect.height-15,(year,profile['id'],span)
                if index==0 and year in [2009,2018,2024]:
                    page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(CACHE/f'pdf_{year}_page_{page_index+1}.png')
        png=path.with_suffix('.png')
        with Image.open(png) as image:
            assert image.size==(1600,4526) and image.format=='PNG'
            assert image.convert('RGBA').getextrema()[3]==(255,255)
            assert len(image.convert('RGB').getcolors(maxcolors=1000000))>100
        results.append(dict(year=year,id=profile['id'],pdf=path.name,pages=2,selectable_text=True,values_checked=True,margins_checked=True,png=png.name,dimensions=[1600,4526]))
(CACHE/'independent-export-validation.json').write_text(json.dumps(dict(status='passed',renderer=pymupdf.VersionBind,combinations=36,downloads=72,pages=72,results=results),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='passed',combinations=36,downloads=72,pdf_pages=72)))
