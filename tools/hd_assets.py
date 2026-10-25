"""將 imagegen 原圖編譯成三倍資產，保留原版前景遮罩與來源索引。"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_image(original, generated):
    original, generated = original.convert('RGBA'), generated.convert('RGBA')
    size = original.width*3, original.height*3
    mask = original.getchannel('A').resize(size, Image.Resampling.NEAREST)
    if original.getchannel('A').getextrema() == (255, 255):
        result = generated.resize(size, Image.Resampling.LANCZOS)
        if result.getchannel('A').getextrema() != (255, 255):
            raise ValueError('不透明插畫需要完整背景，不能用透明缺口猜補背景')
    else:
        source_box, target_box = generated.getchannel('A').getbbox(), mask.getbbox()
        if source_box is None or target_box is None:
            raise ValueError('空白前景不能編譯')
        x0, y0, x1, y1 = target_box
        picture = generated.crop(source_box).resize((x1-x0, y1-y0), Image.Resampling.LANCZOS)
        result = Image.new('RGBA', size)
        result.paste(picture, (x0, y0))
        # 延展生成圖本身的邊緣RGB，再套原版遮罩。完全不從原版取色補成假HD。
        # 這是貼圖遮罩編譯，不清除或重建未知遊戲背景。
        pixels = bytearray(result.tobytes())
        queue, visited = deque(), bytearray(size[0]*size[1])
        for i in range(size[0]*size[1]):
            if pixels[i*4+3] >= 32:
                queue.append(i)
                visited[i] = 1
        if not queue:
            raise ValueError('生成圖沒有可用前景')
        width, height = size
        while queue:
            i = queue.popleft()
            x, y = i % width, i // width
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nx, ny = x+dx, y+dy
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                n = ny*width+nx
                if not visited[n]:
                    visited[n] = 1
                    pixels[n*4:n*4+3] = pixels[i*4:i*4+3]
                    queue.append(n)
        result = Image.frombytes('RGBA', size, bytes(pixels))
    result.putalpha(mask)
    return result


def read_manifest(output):
    path = output / 'hd.json'
    if path.exists():
        return json.loads(path.read_text())
    return {'Version': 1, 'Scale': 3, 'Ready': False, 'Assets': [],
            'rights': '本機原版與衍生資產，不加入Git', 'new_gameplay_replay': False, 'new_gui_sampling': False}


def save_manifest(output, data):
    temporary = output / 'hd.json.tmp'
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    temporary.replace(output / 'hd.json')


def add(root, output, key, generated, round_number):
    assert round_number in [1, 2], '同批最多兩輪，不建立第三輪美化'
    inventory = root / 'workplace/probe/hd-assets-20261025'
    index = json.loads((inventory / 'inventory.json').read_text())
    record, = [r for r in index['records'] if r['key'] == key and 'image' in r]
    source_file, = [r for r in index['input_files'] if Path(r['path']).stem == record['source']]
    original = inventory / record['image']
    assert original.is_file() and generated.is_file()
    assert sha(original) == record['image_sha256']
    assert output.parent.is_dir() and output.parent.stat().st_uid == 1000
    output.mkdir(exist_ok=True)
    for folder in ['originals', 'masters', 'painted']:
        (output / folder).mkdir(exist_ok=True)
    manifest = read_manifest(output)
    existing = next((r for r in manifest['Assets'] if r['Key'] == key), None)
    if existing:
        assert existing['review_round'] < round_number <= 2, '已接受的相同輪次不覆寫'
    raw_name = f'masters/{key}-r{round_number}.png'
    target_name = f'painted/{key}-r{round_number}.png'
    assert not (output / raw_name).exists() and not (output / target_name).exists()
    original_name = f'originals/{key}.png'
    if (output / original_name).exists():
        assert sha(output / original_name) == sha(original)
    else:
        shutil.copyfile(original, output / original_name)
    indexed_name = f'originals/{key}.idx'
    indexed_source = inventory / Path(record['image']).with_suffix('.idx')
    assert sha(indexed_source) == record['indexed_sha256']
    assert indexed_source.stat().st_size == record['width']*record['height']
    shutil.copyfile(indexed_source, output / indexed_name)
    shutil.copyfile(generated, output / raw_name)
    with Image.open(original) as source, Image.open(generated) as master:
        target = compile_image(source, master)
        assert target.size == (record['width']*3, record['height']*3)
        assert target.getchannel('A').tobytes() == source.getchannel('A').resize(target.size, Image.Resampling.NEAREST).tobytes()
        target.save(output / target_name)
    item = dict(Key=key, Original=original_name, Image=target_name,
                Indexed=indexed_name, IndexedSHA256=sha(output / indexed_name),
                OriginalSHA256=sha(output / original_name), SHA256=sha(output / target_name),
                master=raw_name, master_sha256=sha(output / raw_name),
                generator='內建imagegen；工具未提供模型版本', review_round=round_number,
                source_file=source_file['path'], source_file_sha256=source_file['sha256'], source_offset=record['offset'],
                source_block_sha256=record['sha256'], source_block_bytes=record['bytes'], native_size=[record['width'], record['height']],
                source_method=record['method'], source_header_xy=[record['x'], record['y']],
                palette_sha256=hashlib.sha256(json.dumps(record['palette'], separators=(',', ':')).encode()).hexdigest(),
                native_foreground_preserved=True, new_gameplay_verification=False)
    manifest['Assets'] = [r for r in manifest['Assets'] if r['Key'] != key] + [item]
    manifest['Assets'].sort(key=lambda r: r['Key'])
    manifest['Ready'] = False
    manifest['inventory_sha256'] = sha(inventory / 'inventory.json')
    save_manifest(output, manifest)
    print(json.dumps({'asset': key, 'size': list(target.size), 'round': round_number, 'theme_ready': False}))


def accept(root, output):
    # 正式風格決定必須已保存；不以逾時、沉默或有兩張試繪代答。
    style = root / 'docs/spec/004-hd-style-approved.json'
    assert style.is_file(), 'HD風格與倍率仍待使用者確認'
    decision = json.loads(style.read_text())
    assert decision['asset_scale'] == 3 and decision['window_size_independent'] and decision['approved'] is True
    manifest = read_manifest(output)
    assert manifest['Assets']
    inventory = json.loads((root / 'workplace/probe/hd-assets-20261025/inventory.json').read_text())
    for item in manifest['Assets']:
        for field, expected in [('Original', 'OriginalSHA256'), ('Image', 'SHA256'), ('master', 'master_sha256')]:
            assert sha(output / item[field]) == item[expected], item['Key']
        assert item['review_round'] in [1, 2]
        record, = [r for r in inventory['records'] if r['key'] == item['Key'] and 'image' in r]
        indexed_source = root / 'workplace/probe/hd-assets-20261025' / Path(record['image']).with_suffix('.idx')
        assert sha(indexed_source) == record['indexed_sha256']
        assert indexed_source.stat().st_size == record['width']*record['height']
        indexed_name = f"originals/{item['Key']}.idx"
        if (output / indexed_name).exists():
            assert sha(output / indexed_name) == record['indexed_sha256']
        else:
            shutil.copyfile(indexed_source, output / indexed_name)
        item.update(Indexed=indexed_name, IndexedSHA256=record['indexed_sha256'])
        source_file, = [r for r in inventory['input_files'] if Path(r['path']).stem == record['source']]
        assert item['OriginalSHA256'] == record['image_sha256']
        native_file = root / 'workplace/input/dos/drkqueen' / source_file['path']
        assert sha(native_file) == source_file['sha256']
        block = native_file.read_bytes()[record['offset']:record['offset']+record['bytes']]
        assert len(block) == record['bytes'] and hashlib.sha256(block).hexdigest() == record['sha256']
        item.update(source_file=source_file['path'], source_file_sha256=source_file['sha256'],
                    source_method=record['method'], source_header_xy=[record['x'], record['y']],
                    source_block_sha256=record['sha256'], source_block_bytes=record['bytes'], source_header_hex=block[:8].hex(),
                    palette_sha256=hashlib.sha256(json.dumps(record['palette'], separators=(',', ':')).encode()).hexdigest())
    manifest['Ready'] = True
    manifest['approved_style_sha256'] = sha(style)
    save_manifest(output, manifest)
    print(json.dumps({'theme_ready': True, 'assets': len(manifest['Assets']), 'new_gameplay_verification': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    a = sub.add_parser('add')
    a.add_argument('root', type=Path)
    a.add_argument('output', type=Path)
    a.add_argument('key')
    a.add_argument('generated', type=Path)
    a.add_argument('--round', type=int, choices=[1, 2], default=1)
    a = sub.add_parser('accept')
    a.add_argument('root', type=Path)
    a.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.mode == 'add':
        add(args.root, args.output, args.key, args.generated, args.round)
    else:
        accept(args.root, args.output)
