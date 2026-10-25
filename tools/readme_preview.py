"""由 README 與本機證據產生圖文首頁；不下載、不修改原始圖像。"""
import argparse
import hashlib
import html
import json
import os
import platform
import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw
import PIL


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def section(document, title):
    """完整讀取 README 二級章節，保留小節、表格與來源。"""
    return document.split('## ' + title + '\n\n', 1)[1].split('\n## ', 1)[0].strip()


def prose_html(markdown):
    """轉換本頁使用的標題、段落、圖片、表格與命令。"""
    def inline(text):
        escaped = html.escape(text.replace('\n', ' '), quote=True)
        escaped = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1" loading="lazy">', escaped)
        escaped = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', escaped)
        escaped = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)
        return re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', escaped)

    blocks = []
    for block in markdown.split('\n\n'):
        heading = re.fullmatch(r'(#{1,3}) (.+)', block)
        if heading:
            level, title = len(heading[1]), heading[2]
            anchor = re.sub(r'[^\w\-\u3400-\u9fff ]', '', title).replace(' ', '-')
            blocks.append(f'<h{level} id="{anchor}">' + inline(title) + f'</h{level}>')
        elif block.startswith('```'):
            lines = block.splitlines()
            assert lines[-1] == '```'
            blocks.append('<pre><code>' + html.escape('\n'.join(lines[1:-1])) + '</code></pre>')
        elif block.startswith('|'):
            rows = [line.strip().strip('|').split('|') for line in block.splitlines()]
            header = '<tr>' + ''.join('<th>' + inline(c.strip()) + '</th>' for c in rows[0]) + '</tr>'
            body = ''.join('<tr>' + ''.join('<td>' + inline(c.strip()) + '</td>' for c in row)
                           + '</tr>' for row in rows[2:])
            blocks.append('<div class="table-scroll"><table><thead>' + header
                          + '</thead><tbody>' + body + '</tbody></table></div>')
        else:
            blocks.append('<p>' + inline(block) + '</p>')
    return ''.join(blocks)


def build(root, output):
    assert output.is_dir() and output.stat().st_uid == os.getuid()
    assert not (output / 'preview-index.json').exists(), '請使用新的輸出目錄，保留舊版證據'
    index = read(output / 'tlb-index.json')
    records = {r['key']: r for r in index['records'] if 'image' in r}
    unsupported = [r for r in index['records'] if 'unsupported' in r]
    assert len(records) == 360 and len(unsupported) == 52
    for r in records.values():
        assert digest(output / r['image']) == r['image_sha256']
        with Image.open(output / r['image']) as image:
            assert image.size == (r['width'], r['height'])
    # 藍龍名稱的最小充分見證：同一圖格在正常首戰的可見位置。
    native = root / 'workplace/probe/combat-rounds-20261024/control-r1'
    native_receipt = read(native / 'receipt.json')
    checkpoint, = [c for c in native_receipt['checkpoints'] if c['label'] == 'wait-4']
    indexed = (native / 'wait-4.idx').read_bytes()
    assert hashlib.sha256(indexed).hexdigest() == checkpoint['indexed_sha256']
    dragon = Image.open(output / records['CPIC..6']['image']).convert('RGBA')
    matched = 0
    for y in range(dragon.height):
        for x in range(dragon.width):
            red, green, blue, alpha = dragon.getpixel((x, y))
            if alpha:
                assert (red, green, blue) == tuple(checkpoint['palette'][indexed[(y+104)*320+x+32]])
                matched += 1
    assert matched == 1653
    files = []

    def copy(source, name, **metadata):
        assert source.is_file() and source.stat().st_uid == 1000, source
        target = output / name
        if target.exists():
            assert digest(source) == digest(target), name
        else:
            shutil.copyfile(source, target)
        with Image.open(target) as image:
            size = list(image.size)
        files.append(dict(file=name, source=str(source.relative_to(root)),
                          sha256=digest(target), size=size, **metadata))
        return name

    def screenshot(study, profile, label, name, check=None):
        directory = root / 'workplace/probe' / study / profile
        receipt_path = directory / 'receipt.json'
        receipt = read(receipt_path)
        checkpoint, = [c for c in receipt['checkpoints'] if c['label'] == label]
        if 'frames' in receipt:
            frame, = [f for f in receipt['frames'] if f['step'] == checkpoint['step']]
            assert not frame['held'], '展示穩定畫格'
            source = directory / frame['File']
        else:
            source = directory / (label + '.png')
        if check:
            check_path = root / 'workplace/probe' / study / check
            proof = read(check_path)
            key = 'zh_receipt_sha256' if receipt['translate'] else 'en_receipt_sha256'
            assert proof[key] == digest(receipt_path)
            assert proof['all_submitted_pixels_equal_expected']
        return copy(source, name, label=label, step=checkpoint['step'],
                    receipt=str(receipt_path.relative_to(root)), receipt_sha256=digest(receipt_path),
                    ram_sha256=checkpoint['ram_sha256'], indexed_sha256=checkpoint['indexed_sha256'],
                    validation=check or '原版探索收據；非繁中驗收')

    pictures = {}
    for lang in ('en', 'zh'):
        pictures['ammo-' + lang] = screenshot('ammo-boundaries-20261024', 'single-' + lang + '-r1',
            'single-ready-one', 'ammo-' + lang + '.png', 'single-check-r1.json')
        pictures['battle-' + lang] = screenshot('combat-rounds-20261024', 'p3-' + lang + '-r2',
            'dryden-quick-1', 'battle-' + lang + '.png', 'check-p3-r2.json')
        pictures['defeat-' + lang] = screenshot('combat-rounds-20261024', 'p9-' + lang + '-r2',
            'defeat-8', 'defeat-' + lang + '.png', 'check-p9-r2.json')
    for label, name in [('forest-rest-exit', 'forest.png'), ('forest-area', 'area-map.png')]:
        pictures[name] = screenshot('passage-chain-camp-20261024', 'area-observe-r1', label, name)
    pictures['guide'] = copy(root / 'workplace/caergoth-redraw/map.png', 'guide-caergoth.png',
        kind='攻略地圖重繪原型，非遊戲內地圖',
        receipt_sha256=digest(root / 'workplace/caergoth-redraw/receipt.json'))
    theme_root = root / 'workplace/probe/player-current/hd'
    theme = read(theme_root / 'hd.json')
    assert theme['Ready'] and theme['Scale'] == 3
    assets = sorted(theme['Assets'], key=lambda r: (r['Key'].split('.')[0],
                     [int(v) for v in r['Key'].split('.')[1:] if v]))
    for item in assets:
        for source_field, hash_field in [('Original', 'OriginalSHA256'), ('Image', 'SHA256')]:
            assert digest(theme_root / item[source_field]) == item[hash_field]
        copy(theme_root / item['Image'], 'hd-' + item['Key'] + '.png',
             kind='現行已編譯HD素材；不是遊戲截圖', source_key=item['Key'],
             review_round=item['review_round'])
    portrait, = [r for r in assets if r['Key'] == 'PICA.7.1']
    copy(theme_root / portrait['Image'], 'hd-portrait-current.png', kind='現行已編譯HD頭像素材')
    combat = [r for r in assets if r['Key'].startswith('CPIC.')]
    width, height, columns = 320, 180, 4
    comparison = Image.new('RGB', (width * columns, height * ((len(combat)+columns-1)//columns)), '#23232c')
    painter = ImageDraw.Draw(comparison)
    for i, item in enumerate(combat):
        x, y = i % columns * width, i // columns * height
        painter.text((x+8, y+5), item['Key'] + ' / Original | HD', fill='white')
        for column, field in enumerate(['Original', 'Image']):
            with Image.open(theme_root / item[field]) as source:
                picture = source.convert('RGBA')
                # 比較格只排版，原版使用整數倍最近鄰，不把放大當成HD。
                factor = max(1, min(144//picture.width, 144//picture.height))
                if field == 'Original':
                    picture = picture.resize((picture.width*factor, picture.height*factor), Image.Resampling.NEAREST)
                else:
                    picture.thumbnail((144, 144), Image.Resampling.LANCZOS)
                comparison.paste(picture, (x+column*160+(160-picture.width)//2, y+26+(144-picture.height)//2), picture)
    comparison.save(output / 'combat-hd-comparison.png')
    files.append(dict(file='combat-hd-comparison.png', sha256=digest(output/'combat-hd-comparison.png'),
                      kind='現行素材對照排版，左原版右HD；不是遊戲截圖', keys=[r['Key'] for r in combat]))
    sample_root = root / 'workplace/probe/player-sample-20261026-r5'
    sample = read(sample_root / 'checks.json')
    assert sample['passed'] and sample['state_injection'] is False
    for source, target in [('05-chinese.png', 'player-chinese.png'), ('06-manual.png', 'player-manual.png')]:
        assert digest(sample_root/source) == sample['screenshots'][source]
        copy(sample_root/source, target, kind='現行程式正常冷啟動介面抽驗；非同狀態成對截圖',
             build_sha256=sample['build_sha256'], receipt_sha256=digest(sample_root/'checks.json'))

    # 人物候選只選第一圖格，完整圖庫另列，保留未知身分。
    candidates = {'PICA': {6, 7, 11, 18, 19, 20, 21, 22},
                  'PICB': {4, 5, 6, 7, 10, 12, 13, 16, 19, 21},
                  'PICC': {3, 4, 5, 7, 9, 10, 11, 12, 20, 21, 22, 23, 24}}
    portraits = [r for r in records.values() if r['source'] in candidates
                 and r['block'] == 1 and r['context'][0][0] in candidates[r['source']]]
    assert len(portraits) == 31
    # 總覽只排版已解圖格，不補人物身分，也不改原圖。
    cell, columns = 192, 6
    atlas = Image.new('RGB', (cell * columns, cell * ((len(portraits) + columns - 1) // columns)), '#23232c')
    draw = ImageDraw.Draw(atlas)
    for i, record in enumerate(portraits):
        with Image.open(output / record['image']) as image:
            image = image.convert('RGBA')
            scale = max(1, min((cell - 16) // image.width, (cell - 32) // image.height))
            image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
            x, y = (i % columns) * cell, (i // columns) * cell
            atlas.paste(image, (x + (cell - image.width) // 2, y + 8), image)
        draw.text((x + 8, y + cell - 20), record['key'], fill='white')
    atlas.save(output / 'portraits-original.png')

    readme = (root / 'README.md').read_text()
    story, mechanics = [section(readme, title) for title in ('故事背景', '遊戲機制')]
    # 兩種閱讀格式都從根README建立，避免另維護一份過時的功能與風格說明。
    def local_link(match):
        label, destination = match.groups()
        prefix = 'workplace/probe/readme-gallery-current/'
        if destination.startswith(prefix):
            destination = destination[len(prefix):]
        elif not re.match(r'^(?:https?://|#)', destination):
            destination = '../../../' + destination
        return label + '(' + destination + ')'
    markdown = re.sub(r'(!?\[[^\]]*\])\(([^)]+)\)', local_link, readme)
    markdown += '\n## 已編譯 HD 素材逐項查閱\n\n下列為素材圖，不是遊戲執行截圖。\n\n'
    markdown += '| 來源鍵 | HD 素材 | 接受輪次 |\n|---|---|---|\n'
    for item in assets:
        markdown += f"| {item['Key']} | ![{item['Key']}](hd-{item['Key']}.png) | {item['review_round']} |\n"
    markdown += '\n來源及雜湊見 [展示索引](preview-index.json) 與 [圖庫索引](tlb-index.json)。\n'
    css = """*{box-sizing:border-box}body{margin:0;background:#12151c;color:#ede9dc;font:17px/1.8 system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:32px}h1{font-size:42px;color:#dec58d}h2{margin-top:48px;color:#dec58d}h3{color:#d9c69f}a{color:#d9bf87}p{max-width:1000px}img{display:block;max-width:100%;height:auto;margin:12px auto;background:#23232c}table{border-collapse:collapse;width:100%;margin:16px 0}th,td{border:1px solid #49483f;padding:10px;vertical-align:top;text-align:left}th{background:#1b202b}td img{max-height:600px;object-fit:contain}pre{overflow-x:auto;background:#1b202b;padding:16px}.table-scroll{overflow-x:auto}code{overflow-wrap:anywhere}@media(max-width:720px){main{padding:16px}h1{font-size:30px}table{font-size:14px}th,td{padding:6px}}"""
    page = '<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>黑暗之后 · 圖文介紹</title><style>' + css + '</style><main>' + prose_html(markdown) + '</main></html>\n'
    (output / 'README.html').write_text(page)
    (output / 'README.md').write_text(markdown)
    result = dict(draft=False, rights='本機限定；原版及衍生圖像不加入 Git',
        readme_sha256=digest(root / 'README.md'), tlb_index_sha256=digest(output / 'tlb-index.json'),
        original_frames=len(records), unsupported_blocks=len(unsupported), portrait_candidates=[r['key'] for r in portraits],
        hd_samples=len(assets), hd_in_game="僅已匹配來源可接入；本頁HD為素材展示", screenshots=files,
        hd_manifest_sha256=digest(theme_root / "hd.json"),
        player_sample_sha256=digest(sample_root / "checks.json"),
        versions=dict(python=platform.python_version(), pillow=PIL.__version__),
        tools={n: digest(root / 'tools' / n) for n in ('tlb_gallery.py', 'readme_preview.py', 'readme-gallery.sh')},
        sprite_witness=dict(key='CPIC..6', xy=[32, 104], opaque_pixels=matched,
            receipt_sha256=digest(native / 'receipt.json'), indexed_sha256=checkpoint['indexed_sha256']),
        html_sha256=digest(output / 'README.html'), markdown_sha256=digest(output / 'README.md'),
        sections={title: hashlib.sha256(text.encode()).hexdigest()
                  for title, text in [('故事背景', story), ('遊戲機制', mechanics)]},
        portrait_atlas=dict(file='portraits-original.png', sha256=digest(output / 'portraits-original.png'),
                            size=list(atlas.size), keys=[r['key'] for r in portraits]))
    (output / 'preview-index.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('original_frames', 'hd_samples', 'hd_in_game')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build(args.root, args.output)
