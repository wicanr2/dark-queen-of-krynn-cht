"""匯出 DQK 原生地圖欄位與向量研究圖；不推定通行、門或樓層語意。"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

from text_catalog import hlib


DIRECTIONS = ("north", "east", "south", "west")
EDGES = ((0, 0, 1, 0), (1, 0, 1, 1), (0, 1, 1, 1), (0, 0, 0, 1))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    blocks = hlib(raw)
    toc = raw[slice(*blocks[0])]
    if len(toc) < 2:
        raise ValueError("GEO 目錄不足")
    count = struct.unpack_from("<H", toc)[0]
    if count != len(blocks)-1 or len(toc) != 2+4*count:
        raise ValueError("GEO 目錄長度或筆數不符")
    pairs = list(struct.iter_unpack("<HH", toc[2:]))
    if len({tag for tag, _ in pairs}) != count or {i for _, i in pairs} != set(range(1, count+1)):
        raise ValueError("GEO 原始標籤重複或區塊索引不全")
    maps = []
    for tag, index in pairs:
        lo, hi = blocks[index]
        data = raw[lo:hi]
        if len(data) < 8:
            raise ValueError("GEO 標頭不足")
        height, width = data[:2]
        cells = width*height
        if not width or not height or len(data) != 8+4*cells:
            raise ValueError("GEO 平面範圍與可變尺寸不符")
        planes = [data[8+p*cells:8+(p+1)*cells] for p in range(4)]
        tiles, edges = [], {}
        inverse = [bytearray() for _ in range(4)]
        for i, (ne, sw, event, barrier) in enumerate(zip(*planes)):
            x, y = i % width, i // width
            materials = (ne >> 4, ne & 15, sw >> 4, sw & 15)
            codes = [(barrier >> shift) & 3 for shift in (0, 2, 4, 6)]
            tile = dict(x=x, y=y, materials=dict(zip(DIRECTIONS, materials)), event_raw=event,
                        barrier_raw=barrier, barrier_codes=dict(zip(DIRECTIONS, codes)))
            tiles.append(tile)
            inverse[0].append((materials[0] << 4) | materials[1])
            inverse[1].append((materials[2] << 4) | materials[3])
            inverse[2].append(event)
            inverse[3].append(sum(code << (2*d) for d, code in enumerate(codes)))
            for direction, delta, material, code in zip(DIRECTIONS, EDGES, materials, codes):
                a, b, c, d = delta
                key = (x+a, y+b, x+c, y+d)
                edges.setdefault(key, []).append(dict(cell=[x, y], direction=direction,
                                                       material_raw=material, barrier_code=code))
        if data[:8]+b"".join(inverse) != data:
            raise ValueError("GEO 原始欄位往返不一致")
        if sum(len(v) for v in edges.values()) != 4*cells or any(len(v) not in (1, 2) for v in edges.values()):
            raise ValueError("GEO 方向或共用邊遺失")
        maps.append(dict(raw_tag=tag, chunk=index, file_offset=lo, bytes=hi-lo, sha256=sha(data),
                         width=width, height=height, header_hex=data[:8].hex(),
                         planes=[dict(name=name, file_offset=lo+8+p*cells, bytes=cells,
                                      sha256=sha(planes[p]))
                                 for p, name in enumerate(("NE", "SW", "event", "barrier"))],
                         tiles=tiles, edges=[dict(points=list(k), faces=v) for k, v in sorted(edges.items())],
                         byte_roundtrip_equal=True))
    return maps


def svg(record, output):
    """線段只代表非零美術欄位；兩側原值同時保存，不把旗標畫成門。"""
    step, margin = 32, 32
    width, height = record['width']*step+2*margin, record['height']*step+2*margin+48
    root = ET.Element('svg', {'xmlns': 'http://www.w3.org/2000/svg',
                             'viewBox': f'0 0 {width} {height}', 'role': 'img'})
    ET.SubElement(root, 'title').text = f"GEO raw tag {record['raw_tag']}：美術欄位研究圖，非攻略成品"
    ET.SubElement(root, 'rect', width='100%', height='100%', fill='#fff')
    grid = ET.SubElement(root, 'g', stroke='#ddd', **{'stroke-width': '0.5'})
    for x in range(record['width']+1):
        ET.SubElement(grid, 'path', d=f'M{margin+x*step} {margin}v{record["height"]*step}')
    for y in range(record['height']+1):
        ET.SubElement(grid, 'path', d=f'M{margin} {margin+y*step}h{record["width"]*step}')
    for edge in record['edges']:
        materials = [f['material_raw'] for f in edge['faces']]
        if not any(materials):
            continue
        x, y, a, b = edge['points']
        node = ET.SubElement(root, 'path', d=f'M{margin+x*step} {margin+y*step}L{margin+a*step} {margin+b*step}',
                             stroke='#354854', **{'stroke-width': '2',
                             'data-faces': json.dumps(edge['faces'], separators=(',', ':'))})
        ET.SubElement(node, 'title').text = json.dumps(edge, ensure_ascii=False)
    label = ET.SubElement(root, 'text', x=str(margin), y=str(height-28), **{'font-size': '13'})
    label.text = f"RAW {record['raw_tag']} / {record['width']} x {record['height']} / FIELD VIEW ONLY"
    label = ET.SubElement(root, 'text', x=str(margin), y=str(height-9), **{'font-size': '11'})
    label.text = 'Lines = nonzero art fields; not walls, doors or pathfinding claims.'
    ET.ElementTree(root).write(output, encoding='utf-8', xml_declaration=True)


def export(source, output):
    if not source.is_file() or not output.parent.is_dir() or output.exists():
        raise ValueError("需要既有唯讀來源、既有父目錄及全新輸出目錄")
    raw = source.read_bytes()
    maps = decode(raw)
    output.mkdir()
    files = []
    for record in maps:
        path = output/f'geo-raw-{record["raw_tag"]:03d}.svg'
        svg(record, path)
        files.append(dict(path=path.name, sha256=sha(path.read_bytes())))
    data = dict(state='DRAFT', source_name=source.name, source_sha256=sha(raw), maps=maps,
                field_evidence='DQK shape + primary format references; game consumer not traced',
                limits='原始標籤不右移。標頭其餘六bytes、通行、鎖、門、事件、樓層及玩家地圖名稱未推定。')
    path = output/'geo-fields.json'
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'))+'\n')
    files.append(dict(path=path.name, sha256=sha(path.read_bytes())))
    receipt = dict(state='DRAFT', tool_sha256=sha(Path(__file__).read_bytes()),
                   hlib_tool_sha256=sha(Path(__file__).with_name('text_catalog.py').read_bytes()),
                   source_sha256=sha(raw), maps=len(maps),
                   raw_tags=[m['raw_tag'] for m in maps], byte_roundtrip_equal=True,
                   directional_faces=sum(m['width']*m['height']*4 for m in maps),
                   embedded_images=0, files=files, runtime_verified=False)
    (output/'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    export(args.source, args.output)
