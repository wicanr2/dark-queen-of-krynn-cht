"""DRAFT：把已校閱的印刷地圖幾何與 TSV 重繪為 SVG／PNG，不讀取掃描。"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

FONT_SHA = "9d5bf4932d31fe94c18cd8cfddc98bc1b14ce10f4e354c682179db290a99c825"


def read_catalog(path):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t", quoting=csv.QUOTE_NONE))
    assert rows and all(set(r) == {"key", "text"} and r["key"] and r["text"] for r in rows)
    assert len({r["key"] for r in rows}) == len(rows)
    return {r["key"]: r["text"] for r in rows}


def geometry(data, layout):
    assert data["draft"] is True and 1 <= data["entry"] <= 99
    cols, rows = data["grid"]
    assert all(type(n) is int and 0 < n <= 128 for n in (cols, rows))
    width, height = layout["canvas"]
    assert all(type(n) is int and 0 < n <= 4096 for n in (width, height))
    cell = layout["cell"]
    assert type(cell) is int and 16 <= cell <= 64
    seen, primitives = set(), []
    def boundary(axis, x, y, kind):
        assert axis in ("h", "v") and kind in ("wall", "door", "arch")
        x2, y2 = x + (cell if axis == "h" else 0), y + (cell if axis == "v" else 0)
        primitives.append(("line", [(x, y), (x2, y2)]))
        cx, cy = (x+x2)/2, (y+y2)/2
        if kind == "door":
            dx, dy = (cell*.28, cell*.12) if axis == "h" else (cell*.12, cell*.28)
            primitives.append(("rect", [(cx-dx, cy-dy), (cx+dx, cy+dy)]))
        elif kind == "arch":
            def point(u, v):
                return (cx+u, cy+v) if axis == "h" else (cx-v, cy+u)
            mask = [point(-cell*.32, -2), point(cell*.32, 2)]
            primitives.append(("erase", [(min(a[0] for a in mask), min(a[1] for a in mask)),
                                          (max(a[0] for a in mask), max(a[1] for a in mask))]))
            for radius in (cell*.28, cell*.13):
                points = [point(radius*math.cos(math.pi-i*math.pi/32), -radius*math.sin(math.pi-i*math.pi/32)) for i in range(33)]
                primitives.append(("line", points))
            for side in (-1, 1):
                primitives.append(("line", [point(side*cell*.28, 0), point(side*cell*.13, 0)]))
    for edge in data["edges"]:
        axis, x, y, kind = [edge[k] for k in ("axis", "x", "y", "kind")]
        assert type(x) is int and type(y) is int
        assert axis in ("h", "v") and 0 <= x < cols+(axis == "v") and 0 <= y < rows+(axis == "h")
        assert (axis, x, y) not in seen, "重複方格邊"
        seen.add((axis, x, y))
        boundary(axis, layout["origin"][0]+x*cell, layout["origin"][1]+y*cell, kind)
    counts = {k: sum(e["kind"] == k for e in data["edges"]) for k in ("wall", "door", "arch")}
    assert counts == data["counts"] and all(counts.values())
    lx, ly = layout["legend"]
    for i, kind in enumerate(("wall", "door", "arch")):
        boundary("v", lx+16, ly+48+i*64, kind)
    for _, points in primitives:
        assert all(math.isfinite(v) for p in points for v in p)
        assert all(1 <= x < width-1 and 1 <= y < height-1 for x, y in points), "幾何超出畫布"
    return primitives


def texts(data, layout, catalog):
    entry = data["entry"]
    prefix = f"journal.{entry}.label."
    heading = catalog["reader.heading"]
    assert heading.count("%s") == 2
    result = [{"key": "reader.heading", "text": heading % (entry, catalog[f"journal.{entry}.title"]), "x": 32, "y": 28, "size": 28}]
    lx, ly = layout["legend"]
    result.append({"key": prefix+"key", "text": catalog[prefix+"key"], "x": lx, "y": ly, "size": 24})
    for i, name in enumerate(("wall", "door", "archway")):
        result.append({"key": prefix+name, "text": catalog[prefix+name], "x": lx+48, "y": ly+52+i*64, "size": 24})
    for label in layout["labels"]:
        assert label["key"].startswith(prefix) and label["space"] == "grid"
        text = catalog[label["key"]]
        assert type(label["cells"]) is int and label["cells"] > 0
        assert label["size"] in (20, 24, 28, 32)
        parts = label.get("parts", [{"range": [0, len(text)], "x": label["x"], "y": label["y"]}])
        at = 0
        for part in parts:
            start, end = part["range"]
            assert start == at and start < end <= len(text), "分行遺失或重複文字"
            at = end
            for row, offset in enumerate(range(start, end, label["cells"])):
                line = text[offset:min(offset+label["cells"], end)]
                size = label["size"]
                x = layout["origin"][0]+part["x"]*layout["cell"]-len(line)*size/2
                y = layout["origin"][1]+part["y"]*layout["cell"]+row*(size+4)
                result.append({"key": label["key"], "text": line, "x": x, "y": y, "size": size})
        assert at == len(text)
    for line in result:
        assert line["text"] and not any(ord(c) < 32 or c == "\\" for c in line["text"])
        assert 0 <= line["x"] and line["x"]+len(line["text"])*line["size"] <= layout["canvas"][0]
        assert 0 <= line["y"] and line["y"]+line["size"]+4 <= layout["canvas"][1]
    assert {k for k in catalog if k.startswith(prefix)} == {line["key"] for line in result if line["key"].startswith(prefix)}, "地圖標籤未完整呈現"
    return result


def png(primitives, lines, layout, font_path, output):
    from PIL import Image, ImageChops, ImageDraw, ImageFont
    image = Image.new("RGB", tuple(layout["canvas"]), "white")
    draw = ImageDraw.Draw(image)
    for kind, points in primitives:
        points = [(round(x), round(y)) for x, y in points]
        if kind == "line": draw.line(points, fill="black", width=2)
        else: draw.rectangle(points, fill="white", outline="black" if kind == "rect" else None, width=2)
    walls = ImageChops.invert(image.convert("L"))
    glyphs, collisions = {}, []
    for line in lines:
        size = line["size"]
        font = ImageFont.truetype(str(font_path), size)
        mask = Image.new("L", image.size, 0)
        for index, char in enumerate(line["text"]):
            key = (size, char)
            if key not in glyphs:
                padded = Image.new("L", (size*3, (size+4)*3), 0)
                ImageDraw.Draw(padded).text((size, size+4), char, font=font, fill=255, anchor="lt")
                box = padded.getbbox()
                dx = 0
                if box:
                    left, top, right, bottom = box[0]-size, box[1]-size-4, box[2]-size, box[3]-size-4
                    assert right-left <= size and 0 <= top and bottom <= size+4, ("字墨超格", char, size)
                    dx = min(max(0, -left), size-right)
                glyphs[key] = padded.crop((size-dx, size+4, size*2-dx, (size+4)*2))
            mask.paste(glyphs[key], (round(line["x"]+index*size), round(line["y"])))
        collision = ImageChops.multiply(mask, walls).getbbox()
        if collision:
            collisions.append((line["key"], line["text"], line["x"], line["y"], collision))
        image.paste("black", mask=mask)
    assert not collisions, ("文字遮住地圖", collisions)
    image.save(output)


def svg(primitives, lines, layout, font_path, output):
    from fontTools.ttLib import TTFont
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    font = TTFont(font_path)
    cmap, glyph_set, units = font.getBestCmap(), font.getGlyphSet(), font["head"].unitsPerEm
    root = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": f'0 0 {layout["canvas"][0]} {layout["canvas"][1]}', "role": "img"})
    ET.SubElement(root, "rect", {"width": "100%", "height": "100%", "fill": "white"})
    defs = ET.SubElement(root, "defs")
    bounds = {}
    for char in sorted(set("".join(line["text"] for line in lines))):
        assert ord(char) in cmap, ("字型缺字", char)
        glyph = glyph_set[cmap[ord(char)]]
        pen, box = SVGPathPen(glyph_set), BoundsPen(glyph_set)
        glyph.draw(pen); glyph.draw(box)
        bounds[char] = box.bounds
        ET.SubElement(defs, "path", {"id": f"u{ord(char):x}", "d": pen.getCommands()})
    for kind, points in primitives:
        if kind == "line":
            ET.SubElement(root, "polyline", {"points": " ".join(f"{x:.4f},{y:.4f}" for x,y in points), "fill": "none", "stroke": "black", "stroke-width": "2"})
        else:
            (x,y),(right,bottom) = points
            ET.SubElement(root, "rect", {"x": str(x), "y": str(y), "width": str(right-x), "height": str(bottom-y), "fill": "white", "stroke": "black" if kind == "rect" else "none", "stroke-width": "2"})
    for line in lines:
        group = ET.SubElement(root, "g", {"data-key": line["key"], "aria-label": line["text"]})
        scale = line["size"]/units
        for index, char in enumerate(line["text"]):
            box = bounds[char]
            if box is None: continue
            left, _, right, top = box
            assert (right-left)*scale <= line["size"]+1e-6, ("向量字墨超格", char)
            dx = min(max(0, -left*scale), line["size"]-right*scale)
            x, y = line["x"]+index*line["size"]+dx, line["y"]+top*scale
            ET.SubElement(group, "use", {"href": f"#u{ord(char):x}", "transform": f"translate({x:.5f},{y:.5f}) scale({scale:.7f},-{scale:.7f})"})
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("geometry", "layout", "catalog", "font", "output"): parser.add_argument(name, type=Path)
    parser.add_argument("--format", choices=("svg", "png"), required=True)
    args = parser.parse_args()
    assert not args.output.exists() and args.output.parent.is_dir()
    assert hashlib.sha256(args.font.read_bytes()).hexdigest() == FONT_SHA
    data, layout = [json.loads(path.read_text()) for path in (args.geometry, args.layout)]
    primitives = geometry(data, layout)
    lines = texts(data, layout, read_catalog(args.catalog))
    if args.format == "svg": svg(primitives, lines, layout, args.font, args.output)
    else: png(primitives, lines, layout, args.font, args.output)
    print(json.dumps({"draft": True, "entry": data["entry"], "edges": len(data["edges"]), "counts": data["counts"], "text_lines": len(lines), "format": args.format}, ensure_ascii=False))


if __name__ == "__main__": main()
