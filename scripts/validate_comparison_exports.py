"""Valida las comparaciones descargadas y renderiza muestras con un lector independiente."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0,str(Path('node_modules/.cache/pdf-render-minimal').resolve()))
import pymupdf
from PIL import Image

CACHE=Path('node_modules/.cache/comparison-exports-ui')
run=json.loads((CACHE/'results.json').read_text(encoding='utf-8'))
assert run['status']=='passed'
results=[]
preview=CACHE/'previews'
preview.mkdir(exist_ok=True)
for item in run['exports']:
    if item['format']!='pdf':
        continue
    year=item['year']
    payload=json.loads(Path(f'public/data/profiles/enriched-{year}.json').read_text(encoding='utf-8'))
    profiles=[p for p in payload['profiles'] if p['id'] in item['ids']]
    assert len(profiles)==len(item['ids'])
    path=Path(item['path'])
    with pymupdf.open(path) as document:
        assert len(document)==3
        text=re.sub(r'\s+',' ',' '.join(page.get_text() for page in document))
        assert 'Comparación de perfiles ciudadanos' in text and f'Elección {year}' in text
        assert 'SEXO=' not in text and 'Descargar' not in text
        if year!=2024:
            assert '2024' not in text
        for title in ['Sexo','Tipo de sección electoral','Distancia frente a sus propias referencias','Diferencias internas entre mujeres y hombres','Contraste rural-urbano y composición','Fuentes, calidad y límites']:
            assert title in text,(year,title)
        for profile in profiles:
            assert profile['name'] in text
            assert profile['id'] in document.metadata['subject']
            for field in ['participation','reference','nominalShare']:
                assert f"{profile[field]*100:.2f} %" in text,(year,profile['id'],field)
            sign='+' if profile['deltaPp']>0 else '-' if profile['deltaPp']<0 else ''
            assert f"{sign}{abs(profile['deltaPp']):.2f} pp" in text
            for value in profile['counts'].values():
                assert f'{value:,}' in text
            for cell in profile['sexCells']+profile['sectionCells']:
                for field in ['participation','nominalShare']:
                    if cell[field] is not None:
                        assert f"{cell[field]*100:.2f} %" in text
        example=(year==2009 and item['ids']==['young_favorable','young_unfavorable']) or (year==2018 and item['ids']==['young_favorable','adult_unfavorable']) or (year==2024 and len(item['ids'])==3)
        for index,page in enumerate(document):
            assert abs(page.rect.width-595.28)<.05 and abs(page.rect.height-841.89)<.05
            spans=[s for b in page.get_text('dict')['blocks'] if b['type']==0 for line in b['lines'] for s in line['spans']]
            assert len(spans)>12
            for span in spans:
                x0,y0,x1,y1=span['bbox']
                assert x0>=30 and y0>=18 and x1<=page.rect.width-29 and y1<=page.rect.height-13,(year,index,span)
            # Detecta solapamientos de texto, además de cortes; tolera <1 pt de caja tipográfica.
            for a,span in enumerate(spans):
                ax0,ay0,ax1,ay1=span['bbox']
                for other in spans[a+1:]:
                    bx0,by0,bx1,by1=other['bbox']
                    assert min(ax1,bx1)-max(ax0,bx0)<=1 or min(ay1,by1)-max(ay0,by0)<=1,(year,index,span['text'],other['text'])
            if example:
                page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(preview/f'{year}_page_{index+1}.png')
    with Image.open(path.with_suffix('.png')) as image:
        assert image.size==(1600,2357) and image.format=='PNG'
        assert image.convert('RGBA').getextrema()[3]==(255,255)
        colors={color:amount for amount,color in image.convert('RGB').getcolors(maxcolors=1000000)}
        for color in [(105,56,143),(169,85,54),(38,117,101),(191,96,147),(94,146,187)]:
            assert colors.get(color,0)>50,(year,color)
    results.append(dict(year=year,ids=item['ids'],pdf=path.name,pages=3,text_selectable=True,values_checked=True,no_text_overlap=True,png=path.with_suffix('.png').name,dimensions=[1600,2357]))
assert len(results)==18
(CACHE/'independent-validation.json').write_text(json.dumps(dict(status='passed',reader=pymupdf.VersionBind,comparisons=18,pdf_pages=54,downloads=36,results=results),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='passed',comparisons=18,pdf_pages=54,png=18)))
