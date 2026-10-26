"""將已重繪的泰勒達斯地圖接入說明索引；不修改原版或其他書頁。"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import subprocess
import sys

from player_inputs import catalog, save_catalog, sha


def install(root, output, font):
    batch = root/'workplace/probe/guide-20261027'
    maps = batch/'world-map-r2'
    proof = json.loads((maps/'receipt.json').read_text())
    assert proof['cities'] == 13 and proof['regions'] == 8 and proof['embedded_images'] == 0
    for name, digest in proof['files'].items():
        assert Path(name).name == name and sha(maps/name) == digest
    for name, key in [('world-terrain.json','source_geometry_sha256'),('world-map-layout.json','layout_sha256'),
                      ('world-map.zh-TW.tsv','catalog_sha256')]:
        assert sha(batch/name) == proof[key], name
    assert sha(font) == proof['font_sha256']
    assert output.is_dir() and output.stat().st_uid == 1000
    index_path, text_path = output/'manual-index.json', output/'manual.zh-TW.tsv'
    index, words = json.loads(index_path.read_text()), catalog(text_path)
    old_index = json.loads(index_path.read_text())
    old_words = dict(words)
    docs = [d for b in index['books'] for d in b['documents']]
    assert len(docs) == 190
    target = next(d for d in docs if d['id'] == 'manual.adventurer.page2')
    assert target['kind'] == 'illustration-pending' and target['body_key'] == 'manual.image_pending'
    target.update(kind='illustration', body_key='manual.adventurer.page2.body', image=dict(
        entry=0, file='manual-world-map.png', sha256=proof['files']['manual-world-map.png'], crop=[0,0,1200,1040]))
    words[target['body_key']] = '泰勒達斯地形示意。地名來源：冒險手冊第2頁。'
    words['manual.map_hint'] = '＋－縮放 WASD平移 Home全圖 Esc目錄 F6離開'
    assert len(words['manual.map_hint']) <= 38
    png = output/'manual-world-map.png'
    assert not png.exists()
    shutil.copyfile(maps/'manual-world-map.png', png)
    save_catalog(text_path, words)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2)+'\n')
    glyph_path = output/'glyphs-16.json'
    glyphs = json.loads(glyph_path.read_text())
    old_glyphs = dict(glyphs['glyphs'])
    missing = ''.join(sorted(set(words[target['body_key']]+words['manual.map_hint'])-set(old_glyphs)))
    if missing:
        extra_text, extra_font = output/'map-font-additions.tmp.tsv', output/'map-glyphs.tmp.json'
        assert not extra_text.exists() and not extra_font.exists()
        try:
            save_catalog(extra_text, {'font.manual_map':missing})
            subprocess.run([sys.executable,str(root/'tools/menu_glyphs.py'),str(font),str(extra_text),str(extra_font),'16'],check=True)
            glyphs['glyphs'].update(json.loads(extra_font.read_text())['glyphs'])
            glyph_path.write_text(json.dumps(glyphs,ensure_ascii=False,separators=(',',':'))+'\n')
        finally:
            extra_text.unlink(missing_ok=True);extra_font.unlink(missing_ok=True)
    assert all(glyphs['glyphs'][k] == v for k,v in old_glyphs.items())
    for s in (words[target['body_key']], words['manual.map_hint']):
        for ch in s:
            raw=glyphs['glyphs'][ch]
            alpha=base64.b64decode(raw) if isinstance(raw,str) else bytes(raw)
            assert len(alpha)==320 and not any(alpha[256:])
    old_docs = {d['id']:d for b in old_index['books'] for d in b['documents']}
    assert all(d == old_docs[d['id']] for d in docs if d != target)
    assert all(words[k] == v for k,v in old_words.items())
    evidence=dict(map_receipt_sha256=sha(maps/'receipt.json'),
        source_scan_sha256=sha(root/'workplace/manual-ocr/Image047-right.png'),
        source_layout_sha256=sha(batch/'world-map-layout.json'),
        map_sha256=sha(png), unchanged_documents=189, added_glyphs=missing,
        manual_index_sha256=sha(index_path),manual_catalog_sha256=sha(text_path),glyphs_sha256=sha(glyph_path),
        new_gameplay_verification=False)
    (output/'manual-map-provenance.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(evidence,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('root','output','font'):p.add_argument(n,type=Path)
    a=p.parse_args();install(a.root,a.output,a.font)
