"""DRAFT：依校閱的紙片輪廓、文字位置與 TSV 重繪破損信件。"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import xml.etree.ElementTree as ET

from journal_diagrams import FONT_SHA, png, read_catalog, svg


def inside(point, polygon):
    x, y = point
    result = False
    for (ax, ay), (bx, by) in zip(polygon, polygon[1:]+polygon[:1]):
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            result = not result
    return result


def build(data, layout, catalog):
    assert data["draft"] is True and data["entry"] == 12
    assert layout["draft"] is True
    width, height = layout["canvas"]
    assert all(type(n) is int and 0 < n <= 4096 for n in (width, height))
    scale = layout["scale"]
    assert type(scale) is int and 1 <= scale <= 4
    sx, sy = data["roi"][:2]
    ox, oy = layout["origin"]
    polygons, primitives = {}, []
    for piece in data["pieces"]:
        key, points = piece["id"], piece["points"]
        assert key and key not in polygons and len(points) >= 3
        if points[-1] == points[0]: points = points[:-1]
        assert all(len(p) == 2 and all(type(v) is int for v in p) for p in points)
        assert all(data["roi"][0] <= x < data["roi"][2] and data["roi"][1] <= y < data["roi"][3] for x, y in points)
        mapped = [(ox+(x-sx)*scale, oy+(y-sy)*scale) for x, y in points]
        assert all(1 <= x < width-1 and 1 <= y < height-1 for x, y in mapped)
        polygons[key] = mapped
        primitives.append(("line", mapped+[mapped[0]]))
    assert len(polygons) == data["piece_count"] == 9
    heading = catalog["reader.heading"]
    assert heading.count("%s") == 2
    lines = [{"key": "reader.heading", "text": heading % (12, catalog["journal.12.title"]), "x": 32, "y": 28, "size": 28}]
    seen = set()
    for field in layout["fields"]:
        key, piece, size = [field[k] for k in ("key", "piece", "size")]
        assert key.startswith("journal.12.shard.") and key not in seen
        seen.add(key)
        assert piece in polygons and size in (20, 24, 28, 32)
        text = catalog[key]
        assert not any(ord(c) < 32 or c == "\\" for c in text)
        parts = field.get("parts", [{"range": [0, len(text)], "box": field.get("box")}])
        at = 0
        for part in parts:
            start, end = part["range"]
            assert start == at and start < end <= len(text), "分段遺失或重複文字"
            at = end
            segment = text[start:end]
            left, top, right, bottom = part["box"]
            assert all(math.isfinite(v) for v in part["box"])
            assert 0 <= left < right <= width and 0 <= top < bottom <= height
            assert len(segment)*size <= right-left and size+4 <= bottom-top, ("文字超出欄位", key)
            # 每個像素都須位於所屬紙片，不能只檢查四角而跨過凹口。
            assert all(inside((x+.5, y+.5), polygons[piece]) for y in range(math.floor(top), math.ceil(bottom)) for x in range(math.floor(left), math.ceil(right))), ("欄位跨出紙片", key)
            lines.append({"key": key, "text": segment, "x": left+(right-left-len(segment)*size)/2,
                          "y": top+(bottom-top-size-4)/2, "size": size})
        assert at == len(text)
    assert seen == {key for key in catalog if key.startswith("journal.12.shard.")}
    assert len(seen) == 22 and set(polygons)-{f["piece"] for f in layout["fields"]} == set("efgi")
    assert catalog["journal.12.shard.h.3"] == "a", "孤立殘字不能猜補"
    footer = catalog["journal.12.notice"]
    lines.append({"key": "journal.12.notice", "text": footer, "x": 32, "y": height-52, "size": 24})
    assert set(catalog) == seen | {"reader.heading", "journal.12.title", "journal.12.notice"}
    for line in lines:
        assert 0 <= line["x"] and line["x"]+len(line["text"])*line["size"] <= width
        assert 0 <= line["y"] and line["y"]+line["size"]+4 <= height
    return primitives, lines


def render(primitives, lines, layout, font_path, output, format):
    # 地圖工具按字墨上緣對齊；破損信件含大量標點，須改為共用基線。
    if format == "png":
        from PIL import ImageFont
        fonts, positioned = {}, []
        for line in lines:
            size = line["size"]
            if size not in fonts: fonts[size] = ImageFont.truetype(str(font_path), size)
            for i, char in enumerate(line["text"]):
                _, top, _, bottom = fonts[size].getbbox(char, anchor="ls")
                assert 0 <= size+top and size+bottom <= size+4, ("基線字墨超格", char)
                positioned.append({**line, "text": char, "x": line["x"]+i*size, "y": line["y"]+size+top})
        png(primitives, positioned, layout, font_path, output)
    else:
        from fontTools.ttLib import TTFont
        from fontTools.pens.boundsPen import BoundsPen
        font = TTFont(font_path)
        glyphs, cmap, units = font.getGlyphSet(), font.getBestCmap(), font["head"].unitsPerEm
        for line in lines:
            for char in line["text"]:
                assert ord(char) in cmap, ("字型缺字", char)
                pen = BoundsPen(glyphs)
                glyphs[cmap[ord(char)]].draw(pen)
                if pen.bounds:
                    _, bottom, _, top = pen.bounds
                    assert top <= units and -bottom*line["size"]/units <= 4, ("基線字墨超格", char)
        svg(primitives, lines, layout, font_path, output)
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        tree = ET.parse(output)
        groups = tree.getroot().findall("{*}g")
        assert len(groups) == len(lines)
        for group, line in zip(groups, lines):
            for use in group:
                match = re.fullmatch(r"translate\(([^,]+),[^)]+\)(.*)", use.attrib["transform"])
                assert match
                use.set("transform", f'translate({match[1]},{line["y"]+line["size"]:.5f}){match[2]}')
        tree.write(output, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("geometry", "layout", "catalog", "font", "output"): parser.add_argument(name, type=Path)
    parser.add_argument("--format", choices=("svg", "png"), required=True)
    args = parser.parse_args()
    assert not args.output.exists() and args.output.parent.is_dir()
    assert hashlib.sha256(args.font.read_bytes()).hexdigest() == FONT_SHA
    data, layout = [json.loads(p.read_text()) for p in (args.geometry, args.layout)]
    primitives, lines = build(data, layout, read_catalog(args.catalog))
    render(primitives, lines, layout, args.font, args.output, args.format)
    print(json.dumps({"draft": True, "entry": 12, "pieces": len(primitives), "text_lines": len(lines), "format": args.format}))


if __name__ == "__main__": main()
