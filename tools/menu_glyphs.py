"""由私有原型 TSV 與已核對的圓體產生 16／20 像素研究字模；預設 20。"""

import csv
import base64
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


font_path, catalog_path, output = map(Path, sys.argv[1:4])
if len(sys.argv) not in (4,5,6):
    raise ValueError("需提供字型、TSV、輸出、可選字級及輪廓回退資料")
size = int(sys.argv[4]) if len(sys.argv) >= 5 else 20
if size not in (16, 20):
    raise ValueError("研究原型只提供 16／20 像素比較")
height = size + 4
font_hash = hashlib.sha256(font_path.read_bytes()).hexdigest()
if font_hash != "9d5bf4932d31fe94c18cd8cfddc98bc1b14ce10f4e354c682179db290a99c825":
    raise ValueError("未核對的原型字型")
with catalog_path.open() as file:
    rows = list(csv.DictReader(file, delimiter="\t", quoting=csv.QUOTE_NONE))
chars = sorted(set("".join(row["text"] for row in rows)) - set("\r\n\t"))
font = ImageFont.truetype(str(font_path), size)
glyphs = {}
fallback=json.loads(Path(sys.argv[5]).read_text()) if len(sys.argv)==6 else None
if fallback is not None:
    if (fallback["font_sha256"],fallback["size"],fallback["height"])!=(font_hash,size,height):
        raise ValueError("輪廓字模來源或尺寸不符")
for char in chars:
    # 先保留字格外的字墨，再以實際墨跡判斷容量。部分字只有 bearing 外伸，
    # 例如 16px 的「取」向左一格、「珊」向右一格；整數平移即可完整放入。
    padded = Image.new("L", (size * 3, height * 3), 0)
    draw = ImageDraw.Draw(padded)
    metrics = draw.textbbox((size, height), char, font=font, anchor="lt")
    if metrics[0] < 0 or metrics[1] < 0 or metrics[2] > padded.width or metrics[3] > padded.height:
        raise ValueError(f"字型量測範圍不足：{char}")
    draw.text((size, height), char, font=font, fill=255, anchor="lt")
    ink = padded.getbbox()
    dx = dy = 0
    if ink is not None:
        left, top, right, bottom = ink[0] - size, ink[1] - height, ink[2] - size, ink[3] - height
        if right - left > size or bottom - top > height:
            if fallback is None or char not in fallback["glyphs"]:
                raise ValueError(f"字墨超出原型安全框：{char}")
            raw=base64.b64decode(fallback["glyphs"][char],validate=True)
            if len(raw)!=size*height or any(raw[size*size:]):
                raise ValueError(f"輪廓字模超出安全框：{char}")
            glyphs[char]=fallback["glyphs"][char]
            continue
        dx = min(max(0, -left), size - right)
        dy = min(max(0, -top), height - bottom)
    image = padded.crop((size - dx, height - dy, size * 2 - dx, height * 2 - dy))
    glyphs[char] = base64.b64encode(image.tobytes()).decode("ascii")
output.write_text(json.dumps({"size": size, "height": height, "font_sha256": font_hash,
                              "glyphs": glyphs}, ensure_ascii=False) + "\n")
print(f"已產生 {len(glyphs)} 個研究字模")
