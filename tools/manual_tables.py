"""DRAFT：檢查手冊表格的逐格轉錄、術語及離線重排，不接入規則。"""
import argparse
import base64
import csv
import hashlib
import json
from pathlib import Path
import re

from journal_diagrams import FONT_SHA, read_catalog
from manual_review_check import wrap


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(project, source, prior, font, output):
    from fontTools.ttLib import TTFont
    assert not output.exists()
    manifest=json.loads((source/'tables.json').read_text())
    assert manifest['draft'] is True and manifest['runtime_verified'] is False
    for item in manifest['sources']:
        path=(project/item['path']).resolve()
        assert path.is_relative_to(project.resolve()) and sha(path)==item['sha256'],item['path']
    assert sha(source/'table-cells.tsv')==manifest['cells_sha256']
    assert sha(source/'tables.zh-TW.tsv')==manifest['translation_sha256']
    text=read_catalog(source/'tables.zh-TW.tsv')
    with (source/'table-cells.tsv').open() as stream:
        reader=csv.DictReader(stream,delimiter='\t')
        assert reader.fieldnames==['table','row','field','value']
        raw=list(reader)
    cells={}
    for item in raw:
        assert None not in item and all(item.values())
        key=(item['table'],item['row'],item['field'])
        assert key not in cells,'重複表格格位'
        cells[key]=item['value']
    used=set();keys=set();pages=[];numeric=0
    for table in manifest['tables']:
        tid=table['id'];title=f'table.{tid}.title';note=f'table.{tid}.note'
        assert table['source_page'] in manifest['source_pages']
        keys.update((title,note))
        assert len(table['rows'])==len(set(table['rows']))
        fields=[field['id'] for field in table['fields']]
        assert len(fields)==len(set(fields))
        for field in fields:keys.add(f'table.{tid}.column.{field}')
        # 每筆資料逐欄重排，先量測，超過容量時分頁；正式 UI 尚未定案。
        for row in table['rows']:
            lines=[]
            for field in table['fields']:
                fid=field['id'];cell=(tid,row,fid);used.add(cell)
                value=cells[cell];key=f'table.{tid}.row.{row}.{fid}';keys.add(key)
                translated=text[key]
                if field['kind']=='literal':
                    assert re.fullmatch(r'[0-9+*/()%., -]+|—',value),'數值格式錯誤'
                    assert translated==value,('數值變動',cell)
                    numeric+=1
                elif field['kind']=='mapped':
                    assert translated==field['values'][value],('代碼對照錯誤',cell)
                else:
                    assert field['kind']=='label'
                lines.extend(wrap(text[f'table.{tid}.column.{fid}']+'：'+translated))
            heading=wrap(text[title]);notes=wrap(text[note])
            assert len(heading)<=2
            for part,start in enumerate(range(0,len(lines),13)):
                pages.append({'table':tid,'row':row,'part':part+1,'lines':heading+lines[start:start+13]})
        notes=wrap(text[note])
        for part,start in enumerate(range(0,len(notes),13)):
            pages.append({'table':tid,'row':'notes','part':part+1,'lines':wrap(text[title])+notes[start:start+13]})
    assert used==set(cells),'漏格或孤兒資料'
    assert keys==set(text),'漏譯或孤兒文字'
    for value in text.values():
        assert value and not any(ord(c)<32 or c=='�' for c in value)
        assert not re.search(r'\\(?!n)',value)
    term_path=project/manifest['glossary']['path']
    assert sha(term_path)==manifest['glossary']['sha256']
    glossary=read_terms(term_path)
    assert sha(prior)==manifest['prior_glossary_sha256'] and sha(font)==FONT_SHA
    previous=read_terms(prior);prior_bindings=0
    for binding in manifest['bindings']:
        matches=[r for r in glossary if r['en']==binding['en'] and r['category']==binding['category']]
        assert len(matches)==1 and matches[0]['zh'] in text[binding['key']],('術語不符',binding)
        old=[r for r in previous if r['en']==binding['en'] and r['category']==binding['category']]
        if old:
            assert len(old)==1 and old[0]['zh']==matches[0]['zh'],('前作術語衝突',binding)
            prior_bindings+=1
    source_text={f'layout.{i}.{j}':line for i,page in enumerate(pages) for j,line in enumerate(page['lines'])}
    cmap=TTFont(font).getBestCmap()
    assert all(ord(c) in cmap for line in source_text.values() for c in line),'表格字型缺字'
    output.mkdir()
    (output/'font-source.tsv').write_text('key\ttext\n'+''.join(f'{key}\t{value}\n' for key,value in source_text.items()))
    report={'draft':True,'tables':len(manifest['tables']),'records':sum(len(t['rows']) for t in manifest['tables']),
            'cells':len(cells),'numeric_cells':numeric,'translation_rows':len(text),'bindings':len(manifest['bindings']),
            'prior_bindings':prior_bindings,'font_sha256':sha(font),
            'pages':pages,'translation_sha256':sha(source/'tables.zh-TW.tsv'),
            'limits':'offline source transcription and layout; no original engine rule verification or production panel'}
    (output/'table-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('pages',)},ensure_ascii=False))


def read_terms(path):
    with path.open() as stream:return list(csv.DictReader(stream,delimiter='\t'))


def render(source, output):
    from PIL import Image
    report=json.loads((output/'table-check.json').read_text())
    assert sha(source/'tables.zh-TW.tsv')==report['translation_sha256']
    font=json.loads((output/'glyphs-16.json').read_text())
    assert font['size']==16 and font['height']==20
    alpha={c:base64.b64decode(value) for c,value in font['glyphs'].items()}
    assert all(len(value)==320 and not any(value[256:]) for value in alpha.values())
    dest=output/'pages';assert not dest.exists();dest.mkdir()
    images=[]
    for i,page in enumerate(report['pages']):
        image=Image.new('RGB',(640,400),'black')
        assert len(page['lines'])<=15
        for y,line in enumerate(page['lines']):
            assert len(line)<=38
            for x,char in enumerate(line):
                mask=Image.frombytes('L',(16,20),alpha[char]).crop((0,0,16,16))
                image.paste((255,255,85) if y==0 else (255,255,255),(16+x*16,16+y*20,32+x*16,32+y*20),mask)
        path=dest/f'{i:03d}-{page["table"]}-{page["row"]}-{page["part"]}.png';image.save(path)
        images.append({'path':str(path.relative_to(output)),'sha256':sha(path)})
    (output/'render-check.json').write_text(json.dumps({'draft':True,'not_game_capture':True,'images':images},indent=2)+'\n')
    print('表格離線重排圖：',len(images))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','render']);parser.add_argument('paths',type=Path,nargs='+')
    args=parser.parse_args()
    if args.mode=='prepare':prepare(*args.paths)
    else:render(*args.paths)
