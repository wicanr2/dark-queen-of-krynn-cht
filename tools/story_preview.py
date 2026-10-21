"""由正常玩家首段及私有譯文繪製字級比較。僅為 DRAFT，不接正式路徑。"""

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont


root, font_path = map(Path, sys.argv[1:3])
trace = json.loads((root / "trace.json").read_text())
if len(sys.argv) == 5 and sys.argv[3] == "--runtime-inputs":
    catalogs = Path(sys.argv[4])
    def load(name):
        with (catalogs / name).open() as file:
            rows = list(csv.DictReader(file, delimiter="\t", quoting=csv.QUOTE_NONE))
        result = {r["key"]: r["text"] for r in rows}
        if len(result) != len(rows):
            raise ValueError("來源 TSV 重複 key")
        return result
    en, zh = load("en.tsv"), load("zh-TW.tsv")
    selected = {}
    unmatched = []
    for entry in trace["paragraphs"]:
        if not entry["source"]["nul_terminated"]:
            raise ValueError("觀測來源未結束")
        source = entry["source"]["text"]
        key = "ecl." + hashlib.sha256(source.encode()).hexdigest()[:20]
        if en.get(key) != source or key not in zh:
            unmatched.append({"step": entry["step"], "key": key})
            continue
        selected[key] = zh[key]
    if "ecl.6eddbe9ac1fb277bfaab" not in selected:
        raise ValueError("缺少正常首段的現行譯文")
    output = root / "runtime-zh-TW.tsv"
    if output.exists():
        raise ValueError("不覆寫既有原型輸入")
    with output.open("w") as file:
        writer = csv.writer(file, delimiter="\t", quoting=csv.QUOTE_NONE, quotechar=None, lineterminator="\n")
        writer.writerow(["key", "text"])
        writer.writerows(sorted(selected.items()))
    manifest = {"draft": True, "source_catalog_sha256": hashlib.sha256((catalogs / "en.tsv").read_bytes()).hexdigest(),
                "translation_catalog_sha256": hashlib.sha256((catalogs / "zh-TW.tsv").read_bytes()).hexdigest(),
                "trace_sha256": hashlib.sha256((root / "trace.json").read_bytes()).hexdigest(),
                "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "selected_keys": sorted(selected), "unmatched": unmatched,
                "scope": "Derived subset for glyph baking only; no promotion to formal runtime."}
    (root / "runtime-inputs.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(manifest, ensure_ascii=False))
    raise SystemExit(0)
paragraph = trace["paragraphs"][0]
source = paragraph["source"]["text"]
key = hashlib.sha256(source.encode()).hexdigest()
with (root / "zh-TW.tsv").open() as file:
    rows = list(csv.DictReader(file, delimiter="\t"))
catalog = {row["key"]: row["text"] for row in rows}
text = catalog[key]
if not paragraph["source"]["nul_terminated"] or paragraph["clear"] != 1:
    raise ValueError("原型只支援這個完整、清除後繪製的首段")
left, top, right, bottom = [paragraph[k] for k in
    ("left_column", "top_row", "right_column", "bottom_row")]
rectangle = (left * 8, top * 8, (right + 1) * 8, (bottom + 1) * 8)
base = Image.open(root / "final.png").convert("RGB")
colors = Counter(base.crop(rectangle).getdata())
if len(colors) != 2:
    raise ValueError("此原型預期原版首段文字框只有前景與背景兩色")
background, foreground = [color for color, _ in colors.most_common()]
report = {"prototype": True, "source_key": key, "source_step": paragraph["step"],
          "font_sha256": hashlib.sha256(font_path.read_bytes()).hexdigest(),
          "scope": "offline first-paragraph font comparison; no runtime pagination", "variants": []}
for size in (16, 20):
    image = base.resize((640, 400), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(image)
    x, y, end_x, end_y = [coordinate * 2 for coordinate in rectangle]
    draw.rectangle((x, y, end_x - 1, end_y - 1), fill=background)
    font = ImageFont.truetype(str(font_path), size)
    lines = [""]
    for char in text:
        if draw.textlength(lines[-1] + char, font=font) > end_x - x:
            lines.append("")
        lines[-1] += char
    line_height = size + 4
    if len(lines) * line_height > end_y - y:
        raise ValueError("原型文字超出安全框，需要另作分頁")
    for index, line in enumerate(lines):
        bounds = draw.textbbox((x, y + index * line_height), line, font=font, anchor="lt")
        if bounds[0] < x or bounds[1] < y or bounds[2] > end_x or bounds[3] > end_y:
            raise ValueError("原型字墨超出安全框")
        draw.text((x, y + index * line_height), line, font=font, fill=foreground, anchor="lt")
    image.save(root / f"preview-{size}px.png")
    report["variants"].append({"size": size, "lines": len(lines), "line_height": line_height,
                               "text_rectangle": [x, y, end_x, end_y]})
(root / "preview-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report, ensure_ascii=False))
