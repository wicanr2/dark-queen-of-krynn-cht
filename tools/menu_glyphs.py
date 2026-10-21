"""由私有原型 TSV 與已核對的圓體產生 20 像素研究字模。"""

import csv
import base64
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


font_path, catalog_path, output = map(Path, sys.argv[1:4])
font_hash = hashlib.sha256(font_path.read_bytes()).hexdigest()
if font_hash != "9d5bf4932d31fe94c18cd8cfddc98bc1b14ce10f4e354c682179db290a99c825":
    raise ValueError("未核對的原型字型")
with catalog_path.open() as file:
    rows = list(csv.DictReader(file, delimiter="\t"))
chars = sorted(set("".join(row["text"] for row in rows)))
font = ImageFont.truetype(str(font_path), 20)
glyphs = {}
for char in chars:
    image = Image.new("L", (20, 24), 0)
    draw = ImageDraw.Draw(image)
    bounds = draw.textbbox((0, 0), char, font=font, anchor="lt")
    if bounds[2] > 20 or bounds[3] > 24:
        raise ValueError(f"字模超出原型安全框：{char}")
    draw.text((0, 0), char, font=font, fill=255, anchor="lt")
    glyphs[char] = base64.b64encode(image.tobytes()).decode("ascii")
output.write_text(json.dumps({"size": 20, "height": 24, "font_sha256": font_hash,
                              "glyphs": glyphs}, ensure_ascii=False) + "\n")
print(f"已產生 {len(glyphs)} 個研究字模")
