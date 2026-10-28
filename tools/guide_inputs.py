"""編譯已校讀攻略及52張重繪圖；不接觸原版狀態或掃描像素。"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from PIL import Image
from player_inputs import catalog, save_catalog, sha

CHAPTER_MAPS = [[], [], ['caergoth'], ['draconian-caves'],
    ['naulidis','naulidis-passageway','celanost-underwater','celanost-air'], ['taladas'], ['hizden'],
    ['luminari-b2','luminari-b1']+[f'luminari-{i:02}' for i in range(1,12)], ['kristophan'],
    [f'tombs-{i}' for i in range(1,5)], ['hulderfolk'], ['new-aurim'],
    ['thenol-dungeon','thenol-first','thenol-second','thenol-inner'],
    ['hawk-01','hawk-02','hawk-03','hawk-04','hawk-top','hawk-dungeon','hawk-catacombs'],
    ['baior'], ['blackwater'], ['ald-ground','ald-guest','ald-workshop','ald-palace'],
    [f'flame-{i}' for i in range(5)], ['abyss-cage','abyss-return'], []]


def install(root, output, font):
    batch = root/'workplace/probe/guide-20261028'
    delivery = batch/'guide-map-delivery.json'
    data = json.loads(delivery.read_text())
    assert data['version'] == 1 and data['complete'] is True and data['map_count'] == 52
    assert output.is_dir() and output.stat().st_uid == 1000 and font.is_file()
    def local(name):
        rel = Path(name)
        assert not rel.is_absolute() and '..' not in rel.parts and rel.parts[:2] == ('workplace','probe')
        p = root/rel
        assert p.is_file() and p.resolve().is_relative_to((root/'workplace/probe').resolve())
        return p
    words = catalog(batch/'guide.zh-TW.tsv')
    assert len(words) == 40 and sha(batch/'guide.zh-TW.tsv') == data['text_sha256']
    proof = json.loads((batch/'guide-text-review.json').read_text())
    assert sha(batch/'guide-text-review.json') == data['text_review_sha256']
    source_words = dict(words)
    ui = catalog(root/'text/guide-ui.zh-TW.tsv')
    assert not set(words) & set(ui)
    words.update(ui)
    records = {r['id']:r for r in data['maps']}
    assert len(records) == len(data['maps']) == 52
    assert set(records) == {key for keys in CHAPTER_MAPS for key in keys}
    old_files = {p.name:sha(p) for p in output.iterdir() if p.is_file()}
    books, copied = [], {}
    pages = [60,60,62,62,63,65,66,66,58,59,61,62,63,65,67,67,69,71,72,72]
    for chapter in range(20):
        suffix = 'preface' if chapter == 0 else 'spells' if chapter == 19 else f'chapter.{chapter}'
        bid = suffix.replace('.','-')
        title_key, body_key = f'guide.{suffix}.title', f'guide.{suffix}.body'
        book_key = f'guide.book.{bid}'
        words[book_key] = words[title_key] if chapter in (0,19) else f'第{chapter}章 '+words[title_key]
        docs = [dict(id=f'guide.{suffix}.body',source_page=pages[chapter],title_key=title_key,body_key=body_key,kind='body')]
        for key in CHAPTER_MAPS[chapter]:
            r = records[key]
            review_path = local(r['review'])
            assert sha(review_path) == r['review_sha256']
            review = json.loads(review_path.read_text())
            assert review.get('status') == 'accepted-paper-redraw' or review.get('state') == 'accepted-as-paper-reading-reference'
            png, svg = local(r['png']), local(r['svg'])
            reviewed_rows = review.get('maps')
            if reviewed_rows is None:
                receipt = png.parent.parent/'receipt.json'
                assert sha(receipt) == review['receipt_sha256']
                reviewed_rows = json.loads(receipt.read_text())['maps']
            reviewed = next(v for v in reviewed_rows if v['id'] == key)
            hashes = reviewed.get('files',{'map.png':reviewed.get('png_sha256'),'map.svg':reviewed.get('svg_sha256')})
            assert sha(png) == hashes['map.png'] == r['png_sha256']
            assert sha(svg) == hashes['map.svg'] == r['svg_sha256']
            assert not any(n.tag.rsplit('}',1)[-1] == 'image' for n in ET.parse(svg).iter())
            with Image.open(png) as im:
                assert im.mode == 'RGB' and im.size in ((1100,1040),(1200,1040))
                width, height = im.size
                im.verify()
            name = f'guide-map-{key}.png'
            assert not (output/name).exists()
            shutil.copyfile(png,output/name)
            copied[name] = sha(output/name)
            key_title = f'guide.map.{key}.title'
            words[key_title] = r['title'].split('：')[-1]
            docs.append(dict(id=f'guide.map.{key}',source_page=r['source_page'],title_key=key_title,
                body_key='manual.image_pending',kind='illustration',
                image=dict(entry=0,file=name,sha256=copied[name],crop=[0,0,width,height])))
        books.append(dict(id=bid,title_key=book_key,documents=docs))
    assert len(books) == 20 and sum(len(b['documents']) for b in books) == 72
    index = dict(version=1,complete=True,map_count=52,books=books)
    # 先檢查模板展開的原框寬度；完整正文斷行與字型仍由Go載入器檢查。
    for b in books:
        assert len(words['manual.index_heading'] % words[b['title_key']]) <= 37
        for d in b['documents']:
            assert len(words['manual.document_heading'] % (words[b['title_key']],str(d['source_page']),words[d['title_key']])) <= 37
            assert len(words['manual.index_item'] % (words['manual.selected'],str(d['source_page']),words[d['title_key']])) <= 38
    assert all(len(words[k]) <= 38 for k in ('manual.index_hint','manual.map_hint'))
    assert len(words['manual.document_hint'] % ('99','99')) <= 38
    save_catalog(output/'guide.zh-TW.tsv',words)
    (output/'guide-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
    glyph_path = output/'glyphs-16.json'
    glyphs = json.loads(glyph_path.read_text()); old_glyphs = dict(glyphs['glyphs'])
    missing = ''.join(sorted(set(''.join(words.values()))-set(old_glyphs)-set('\\n')))
    if missing:
        temporary_text, temporary_font = output/'guide-additions.tmp.tsv', output/'guide-glyphs.tmp.json'
        assert not temporary_text.exists() and not temporary_font.exists()
        try:
            save_catalog(temporary_text,{'font.guide':missing})
            subprocess.run([sys.executable,str(root/'tools/menu_glyphs.py'),str(font),str(temporary_text),str(temporary_font),'16'],check=True)
            glyphs['glyphs'].update(json.loads(temporary_font.read_text())['glyphs'])
            glyph_path.write_text(json.dumps(glyphs,ensure_ascii=False,separators=(',',':'))+'\n')
        finally:
            temporary_text.unlink(missing_ok=True);temporary_font.unlink(missing_ok=True)
    assert all(glyphs['glyphs'][k] == v for k,v in old_glyphs.items())
    for ch in set(''.join(words.values()))-set('\\n'):
        raw = glyphs['glyphs'][ch]; alpha = base64.b64decode(raw) if isinstance(raw,str) else bytes(raw)
        assert len(alpha) == 320 and not any(alpha[256:])
    assert all(words[k] == v for k,v in source_words.items())
    assert all(sha(output/n) == h for n,h in old_files.items() if n != 'glyphs-16.json')
    result = dict(complete=True,chapters=18,books=20,documents=72,map_count=52,source_text_keys=40,
        text_sha256=data['text_sha256'],delivery_sha256=sha(delivery),font_sha256=sha(font),
        guide_catalog_sha256=sha(output/'guide.zh-TW.tsv'),guide_index_sha256=sha(output/'guide-index.json'),
        added_glyphs=missing,original_glyphs_unchanged=True,scan_pixels_embedded=False,
        game_geometry_confirmed=False,files=copied,new_gameplay_verification=False)
    (output/'guide-provenance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','added_glyphs')},ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root','output','font'): parser.add_argument(name,type=Path)
    args = parser.parse_args(); install(args.root,args.output,args.font)
