"""由 README 與本機證據產生圖文首頁；不下載、不修改原始圖像。"""
import argparse
import hashlib
import html
import json
import platform
import shutil
from pathlib import Path

from PIL import Image
import PIL


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def build(root, output):
    assert output.is_dir() and output.stat().st_uid == 1000
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
    art_source = root / 'workplace/probe/readme-gallery-20261024'
    for name, original, generated in [
        ('hd-blue-dragon-r2.png', 'CPIC..6', 'exec-aa1e0904-d57a-4d47-a6c5-0807dd36cfc5.png'),
        ('hd-portrait-r1.png', 'PICA.7.1', 'exec-d35fea1a-c87c-4557-bc51-0d8df2956322.png')]:
        pictures[name] = copy(art_source / name, name, kind='imagegen 試繪，尚未接入遊戲，正式風格未定',
            source_key=original, original_png_sha256=records[original]['image_sha256'],
            generator='內建 imagegen；工具未提供模型版號',
            generated_source=generated)

    # 人物候選只選第一圖格，完整圖庫另列，保留未知身分。
    candidates = {'PICA': {6, 7, 11, 18, 19, 20, 21, 22},
                  'PICB': {4, 5, 6, 7, 10, 12, 13, 16, 19, 21},
                  'PICC': {3, 4, 5, 7, 9, 10, 11, 12, 20, 21, 22, 23, 24}}
    portraits = [r for r in records.values() if r['source'] in candidates
                 and r['block'] == 1 and r['context'][0][0] in candidates[r['source']]]
    assert len(portraits) == 31

    def esc(text):
        return html.escape(str(text), quote=True)

    def figure(file, caption, pixel=False):
        return ('<figure><a href="' + esc(file) + '"><img ' + ('class="pixel" ' if pixel else '')
                + 'src="' + esc(file) + '" alt="' + esc(caption) + '"></a><figcaption>'
                + esc(caption) + '</figcaption></figure>')

    readme = (root / 'README.md').read_text()
    story = readme.split('## 故事背景\n\n', 1)[1].split('\n\n', 1)[0].replace('\n', '')
    content = '<header><p class="eyebrow">克萊恩三部曲 · 第三部</p><h1>黑暗之后</h1>'
    content += '<p>The Dark Queen of Krynn · HD＋繁體中文化</p><p>' + esc(story) + '</p>'
    content += '<p class="note">繁中顯示仍為研究原型。兩張 HD 圖為試繪，尚未接入遊戲。原版圖像只在本機展示。</p></header>'
    content += '<nav><a href="#hd">原版＋HD</a><a href="#monsters">怪物圖庫</a><a href="#portraits">人物頭像</a><a href="#screens">遊戲畫面</a><a href="#maps">地圖</a></nav><main>'
    content += '<section id="hd"><h2>原版＋HD 試繪</h2><p>藍龍的原版圖格已與首戰畫面核對。頭像身分尚未確認，保留來源編號。全量 HD 排在中文化之後。</p><div class="pairs">'
    for key, name, title in [('CPIC..6', 'hd-blue-dragon-r2.png', '藍龍 · CPIC ID 82'),
                              ('PICA.7.1', 'hd-portrait-r1.png', '人物頭像 · PICA 7.1')]:
        content += '<article><h3>' + title + '</h3><div class="pair">'
        content += figure(records[key]['image'], '原版 · ' + key, True)
        content += figure(name, 'HD 試繪 · 未接入') + '</div></article>'
    content += '</div></section><section id="monsters"><h2>怪物與戰鬥角色原版總覽</h2><p>CPIC 共 190 格，包含動作與重複編號；圖格數不等於怪物種類數。尚未逐項對回怪物名稱。</p>'
    content += figure('CPIC-original.png', 'CPIC 原版全圖格總覽 · 點圖開啟原尺寸', True)
    content += '<details><summary>隊員戰鬥造型 · CBODY 98 格</summary>' + figure('CBODY-original.png', 'CBODY 原版戰鬥造型', True) + '</details></section>'
    content += '<section id="portraits"><h2>人物頭像原版總覽</h2><p>先列 31 張人物候選圖。名稱與身分待核對；三個 PIC 圖庫已解出的 72 格另含場景與怪物，還有 52 個其他繪圖方法的區塊尚未解碼。</p><div class="portraits">'
    for r in portraits:
        content += figure(r['image'], r['key'] + ' · 身分待核', True)
    content += '</div><details><summary>查看 PICA／PICB／PICC 已解出的圖格</summary>'
    for name in ('PICA', 'PICB', 'PICC'):
        content += figure(name + '-original.png', name + ' 原版圖庫 · 含人物、怪物及場景', True)
    content += '</details></section><section id="screens"><h2>遊戲實際畫面</h2><p>左為原版，右為繁中顯示原型。兩側使用相同原版狀態與輸入。這些畫面未套用 HD 圖像。</p>'
    for name, title in [('ammo', '單支箭矢與裝備清單'), ('battle', '首戰 · 毒氣與傷害回報'), ('defeat', '首戰敗北 · 三行結語')]:
        content += '<h3>' + title + '</h3><div class="pair">'
        content += figure(name + '-en.png', '原版', True) + figure(name + '-zh.png', '繁中顯示原型', True) + '</div>'
    content += '</section><section id="maps"><h2>探索與遊戲內地圖</h2><p>以下兩張直接取自原版正常探索流程，尚未套用繁中或 HD。</p><div class="pair">'
    content += figure('forest.png', '森林探索 · 原版', True) + figure('area-map.png', '遊戲內區域圖 · 原版', True)
    content += '</div><h3>凱爾高斯攻略地圖重繪</h3><p>這是另行繪製的攻略地圖原型，含繁中標註。與上方原版區域圖分開展示，尚未作為遊戲內地圖接入。</p>'
    content += figure('guide-caergoth.png', '凱爾高斯 · 攻略重繪原型') + '</section>'
    content += '<footer><p>故事依《冒險手冊》「故事開始」的將軍來信整理。圖像來源、雜湊與截圖狀態見 <a href="preview-index.json">展示索引</a>；全部原版圖格見 <a href="tlb-index.json">圖庫索引</a>。</p><p>玩家須自備合法原版。本頁與原版圖像只留本機，並非可公開的遊戲封包。</p></footer></main>'
    css = '''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#12151c;color:#ede9dc;font:17px/1.8 system-ui,sans-serif}header,main,nav{max-width:1200px;margin:auto;padding:32px}header{padding-top:64px}header p{max-width:850px}.eyebrow{color:#cbb47e;letter-spacing:.15em}h1{font-size:64px;line-height:1.1;letter-spacing:.12em;margin:20px 0}h2{font-size:30px;color:#dec58d}h3{font-size:21px}.note,figcaption,footer{color:#b9b6ae}nav{display:flex;gap:24px;flex-wrap:wrap;border-block:1px solid #44413a;padding-block:16px}a{color:#d9bf87}section{padding:24px 0 42px;border-bottom:1px solid #44413a;scroll-margin-top:20px}.pair,.pairs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.pair{align-items:start}figure{min-width:0;margin:12px 0}figure img{display:block;width:100%;height:auto;background:#23232c;border:1px solid #49483f}.pixel{image-rendering:pixelated}.pairs .pair{align-items:center}.pairs img{aspect-ratio:1;object-fit:contain}.pairs article{padding:20px;background:#1b202b;border:1px solid #49483f}.portraits{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:18px}.portraits figcaption{font-size:12px}figcaption{font-size:14px;padding-top:6px}summary{cursor:pointer;padding:16px 0;color:#d9bf87}footer{font-size:14px;padding-top:30px}@media(max-width:720px){header,main,nav{padding:20px}h1{font-size:44px}.pairs,.pair{grid-template-columns:1fr}.portraits{grid-template-columns:repeat(3,minmax(0,1fr))}}'''
    page = '<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>黑暗之后 · 圖文介紹</title><style>' + css + '</style>' + content + '</html>\n'
    (output / 'README.html').write_text(page)
    result = dict(draft=True, rights='本機限定；原版及衍生圖像不加入 Git',
        readme_sha256=digest(root / 'README.md'), tlb_index_sha256=digest(output / 'tlb-index.json'),
        original_frames=len(records), unsupported_blocks=len(unsupported), portrait_candidates=[r['key'] for r in portraits],
        hd_samples=2, hd_in_game=False, screenshots=files,
        versions=dict(python=platform.python_version(), pillow=PIL.__version__),
        tools={n: digest(root / 'tools' / n) for n in ('tlb_gallery.py', 'readme_preview.py', 'readme-gallery.sh')},
        sprite_witness=dict(key='CPIC..6', xy=[32, 104], opaque_pixels=matched,
            receipt_sha256=digest(native / 'receipt.json'), indexed_sha256=checkpoint['indexed_sha256']),
        html_sha256=digest(output / 'README.html'))
    (output / 'preview-index.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('original_frames', 'hd_samples', 'hd_in_game')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build(args.root, args.output)
