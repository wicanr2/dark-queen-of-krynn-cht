"""從已核對的原生圖片建立文字安全框，完整來源與輸出僅留本機。"""
import argparse
import base64
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from PIL import Image


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root, output, font):
    assert root.is_dir() and output.parent.is_dir() and not output.exists()
    assert output.parent.stat().st_uid == 1000 and font.is_file()
    inventory = root / 'workplace/probe/hd-assets-20261026-r3'
    raw = json.loads((inventory / 'inventory.json').read_text())
    records = {r['key']: r for r in raw['records']}
    captions = {}

    def caption(key, box, mode='background', scale=1, foreground=None, **extra):
        b = [n * 3 for n in box]
        return dict(Key=key, ClearBox=b, TextBox=b, Mode=mode, Scale=scale, GlyphSize=24 if scale == 1 else 16*scale,
                    **({'Foreground': foreground} if foreground is not None else {}), **extra)

    captions['TITLE.9.1'] = [
        caption('image.credits.creation', [40, 0, 136, 8]),
        caption('image.credits.system', [4, 17, 110, 25]),
        caption('image.credits.producer', [6, 40, 64, 48]),
        caption('image.credits.programmers', [160, 40, 246, 48]),
        caption('image.credits.associate', [5, 65, 125, 73]),
    ]
    captions['TITLE.9.2'] = [
        caption('image.credits.managers', [6, 19, 124, 27]),
        caption('image.credits.scenario', [159, 25, 271, 33]),
        caption('image.credits.artists', [63, 57, 113, 65]),
    ]
    captions['TITLE.10.1'] = [
        caption('image.credits.playtesters', [134, 0, 217, 8]),
        caption('image.credits.music', [6, 7, 59, 15]),
        caption('image.credits.encounters', [6, 45, 127, 53]),
    ]
    captions['TITLE.10.2'] = [caption('image.credits.consultants', [5, 35, 134, 43])]
    captions['TITLE.4.2'] = [
        caption('image.copyright.tsr', [0, 0, 248, 10]),
        caption('image.copyright.ssi', [0, 10, 248, 21]),
    ]
    for c in captions['TITLE.4.2']: c['GlyphSize'] = 16
    captions['TITLE.7.1'] = [caption('image.title.main', [0, 0, 320, 80], scale=6)]
    captions['TITLE.7.2'] = [caption('image.title.world', [0, 0, 176, 82], scale=6)]
    captions['TITLE.2.1'] = [caption('image.title.and', [116, 75, 142, 85])]
    captions['TITLE.3.1'] = [caption('image.title.present', [127, 85, 186, 95])]
    captions['TITLE.4.1'] = [caption('image.title.an', [132, 0, 151, 10]),
                             caption('image.title.computer', [81, 65, 212, 75])]
    captions['TITLE.6.1'] = [caption('image.title.a', [140, 0, 165, 18])]
    captions['TITLE.6.2'] = [caption('image.title.epic', [40, 33, 280, 65], scale=2),
                             caption('image.title.volume', [40, 33, 280, 65], scale=2)]
    captions['TITLE.6.2'][0]['TextBox'] = [120, 99, 840, 147]
    captions['TITLE.6.2'][1]['TextBox'] = [120, 147, 840, 195]
    captions['TITLE.6.2'][0]['ClearBox'] = [120, 99, 840, 147]
    captions['TITLE.6.2'][1]['ClearBox'] = [120, 147, 840, 195]
    # 羅盤上緣為正向，左右下緣是相鄰方位。只換字，指針與刻度保留。
    directions = [('north', 'west', 'east'), ('south', 'east', 'west'),
                  ('west', 'south', 'north'), ('east', 'north', 'south')]
    for n, names in enumerate(directions, 25):
        captions[f'FRAME..{n}'] = [caption('image.direction.' + name, box, 'color', MaskSource=True)
                                 for name, box in zip(names, [[24, 0, 42, 15], [5, 18, 28, 28], [44, 18, 63, 28]])]
    batch = root / 'workplace/probe/localization-hd-20261026'
    for n in range(7, 15):
        key = f'FINAL.2.{n}'
        receipt = json.loads((batch / (key + '-image-text-r3.json')).read_text())
        assert receipt['passed'] and receipt['result']['state'] == 'localized'
        captions[key] = [dict(Key='image.ending.our-heroes', ClearBox=[0, 0, 912, 165],
                              TextBox=receipt['result']['text_safe_box'], Mode='indexed', Scale=1)]
    output.mkdir()
    for locale in ['en', 'zh-TW']:
        (output / (locale + '.tsv')).write_bytes((root / 'text' / f'image-text.{locale}.tsv').read_bytes())
    subprocess.run([sys.executable, str(root / 'tools/menu_glyphs.py'), str(font),
                    str(output / 'zh-TW.tsv'), str(output / 'glyphs.json'), '16'], check=True)
    bindings = []
    provenance = []
    for key, specs in captions.items():
        r = records[key]
        im = Image.open(inventory / r['image']).convert('RGBA')
        indexed = (inventory / (key + '.idx')).read_bytes()
        alpha = im.getchannel('A').tobytes()
        assert len(indexed) == len(alpha) == r['width'] * r['height']
        source_files = list((root / 'workplace/input/dos/drkqueen').glob('*/' + r['source'] + '.TLB'))
        assert len(source_files) == 1
        source = source_files[0].read_bytes()[r['offset']:r['offset'] + r['bytes']]
        assert hashlib.sha256(source).hexdigest() == r['sha256']
        colors = {tuple(im.getpixel((n % im.width, n // im.width))[:3]): indexed[n]
                  for n, a in enumerate(alpha) if a}
        for c in specs:
            if key.startswith('TITLE.9.') or key.startswith('TITLE.10.'):
                c['Foreground'] = colors[(182, 81, 44)]
            elif key.startswith('FRAME.'):
                c.update(Foreground=colors[(255, 255, 255)], FillIndex=colors[(56, 52, 56)])
            elif key.startswith('FINAL.'):
                mask = bytearray(len(alpha));fill = bytearray(len(alpha));greens = []
                for x in range(84, 222):
                    top = next((y for y in range(min(im.height, 55)) if
                                (lambda c: c[3] == 255 and c[0] >= 120 and c[1] >= 90 and c[0]*10 >= c[1]*9 and c[1] > c[2]*1.2)(im.getpixel((x, y)))), None)
                    if top is None:
                        continue
                    y = top
                    while y < min(im.height, 55) and alpha[y*im.width+x]:
                        at = y*im.width+x; mask[at] = 255; fill[at] = indexed[top*im.width+x]
                        color = im.getpixel((x, y))
                        if color[1] >= color[0] and color[1] > color[2]*2 and color[0] < 150:
                            greens.append(indexed[at])
                        y += 1
                assert greens and any(mask)
                c.update(Foreground=greens[0], Mask=base64.b64encode(mask).decode(), Fill=base64.b64encode(fill).decode())
            else:
                if key.startswith('TITLE.7.'):
                    rgb = min(colors, key=lambda c: sum((a-b)**2 for a, b in zip(c, (230, 165, 30))))
                else:
                    rgb = max(colors, key=sum)
                c['Foreground'] = colors[rgb]
        bindings.append(dict(Key=key, Header=source[:8].hex(), SourceSHA256=r['sha256'],
                             SourceBytes=r['bytes'], W=im.width, H=im.height,
                             IndexSHA256=hashlib.sha256(indexed).hexdigest(),
                             AlphaSHA256=hashlib.sha256(alpha).hexdigest(),
                             HDAlreadyLocalized=key.startswith('FINAL.'), Captions=specs))
        provenance.append(dict(key=key, source=str(source_files[0].relative_to(root)), source_sha256=sha(source_files[0]),
                               offset=r['offset'], block_sha256=r['sha256'], native_image_sha256=sha(inventory / r['image'])))
    manifest = dict(Version=1, Files={n: sha(output / n) for n in ['en.tsv', 'zh-TW.tsv', 'glyphs.json']}, Bindings=bindings)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (output / 'provenance.json').write_text(json.dumps(dict(inventory_sha256=sha(inventory / 'inventory.json'),
        font_sha256=sha(font), sources=provenance, bindings=len(bindings), captions=sum(len(b['Captions']) for b in bindings),
        new_gameplay_verification=False), ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(bindings=len(bindings), captions=sum(len(b['Captions']) for b in bindings), manifest_sha256=sha(output / 'manifest.json'))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--font', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.root, args.output, args.font)
