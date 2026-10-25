"""盤點所有 TLB 圖庫並解出既有已知格式；不啟動遊戲，不猜補未知繪圖方法。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw
from tlb_gallery import EGA, external_palette, extract_bank


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root, output):
    original = root / 'workplace/input/dos/drkqueen'
    assert original.is_dir() and output.parent.is_dir() and not output.exists()
    assert output.parent.stat().st_uid == 1000
    output.mkdir()
    base = [None] * 256
    base[:16] = EGA
    palettes = []
    for name in ['WILDCOM.TLB', 'CBODY.TLB']:
        path, = original.rglob(name)
        palettes.append(external_palette(path, base))
    records, inputs, failures = [], [], []
    for path in sorted(original.rglob('*.TLB')):
        relative = str(path.relative_to(original))
        inputs.append(dict(path=relative, sha256=sha(path), bytes=path.stat().st_size))
        # 每一檔單獨解析，不用其他圖庫剛好讀到的局部色盤。
        name = path.stem
        try:
            extract_bank(path.read_bytes(), 0, [], list(base), records, output, name)
        except (AssertionError, ValueError, IndexError, KeyError) as error:
            failures.append(dict(path=relative, error=repr(error), status='需要格式或色盤補充；不補黑色'))
    summary = {}
    for source in sorted({r['source'] for r in records}):
        group = [r for r in records if r['source'] == source]
        decoded = [r for r in group if 'image' in r]
        summary[source] = dict(records=len(group), decoded=len(decoded),
                               methods=dict(Counter(r['method'] for r in group)),
                               unknown=sum('unsupported' in r for r in group))
        if decoded:
            size, columns = 160, 8
            panel = Image.new('RGB', (size*columns, size*((len(decoded)+columns-1)//columns)), '#23232c')
            draw = ImageDraw.Draw(panel)
            for i, record in enumerate(decoded):
                with Image.open(output / record['image']) as image:
                    image = image.convert('RGBA')
                    factor = min((size-12)/image.width, (size-32)/image.height)
                    image = image.resize((max(1, int(image.width*factor)), max(1, int(image.height*factor))), Image.Resampling.NEAREST)
                    x, y = i % columns * size, i // columns * size
                    panel.paste(image, (x+(size-image.width)//2, y+8), image)
                draw.text((x+4, y+size-18), record['key'], fill='white')
            panel.save(output / (source+'-atlas.png'))
    images = [r for r in records if 'image' in r]
    exact = {}
    for record in images:
        # 同像素及尺寸才可共用一份重繪。原編號及動畫幀不刪除。
        with Image.open(output / record['image']) as image:
            key = (image.size, hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest())
        exact.setdefault(str(key), []).append(record['key'])
    result = dict(version=1, input_files=inputs, external_palettes=palettes, summary=summary,
                  decoded_images=len(images), unique_images=len(exact), identical_groups=list(exact.values()),
                  records=records, failures=failures, new_gameplay_replay=False, new_gui_sampling=False,
                  limits='只證明來源解析與圖像可產生；未全量辨識身分、色盤、動畫或遊戲可見位置。未知方法保留。',
                  rights='本機原版／衍生素材，不加入Git',
                  tools={name: sha(root/'tools'/name) for name in ['hd_inventory.py', 'tlb_gallery.py']})
    (output / 'inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['decoded_images', 'unique_images', 'summary', 'failures']}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    inventory(args.root, args.output)
