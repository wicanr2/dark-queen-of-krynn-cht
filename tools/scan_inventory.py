"""盤點唯讀掃描來源，雜湊與接觸表只寫入指定研究目錄。"""

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw


source, output = map(Path, sys.argv[1:3])
if not source.is_dir():
    raise SystemExit("來源目錄不存在")
output.mkdir(parents=True, exist_ok=True)
records = []
images = []
for path in sorted(source.rglob("*")):
    if not path.is_file():
        continue
    record = {"path": str(path.relative_to(source)), "bytes": path.stat().st_size,
              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    with Image.open(path) as image:
        record.update(width=image.width, height=image.height, format=image.format)
    records.append(record)
    images.append(path)
for start in range(0, len(images), 12):
    sheet = Image.new("RGB", (1200, 1680), "#eeeeee")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(images[start:start + 12]):
        x, y = index % 3 * 400, index // 3 * 420
        with Image.open(path) as original:
            image = original.convert("RGB")
            image.thumbnail((392, 388))
            sheet.paste(image, (x, y + 24))
        draw.text((x + 4, y + 4), f"{start + index + 1:02d} {path.parent.name[-3:]} / {path.name}", fill="black")
    sheet.save(output / f"sheet-{start // 12 + 1}.jpg", quality=90)
(output / "manifest.json").write_text(json.dumps({"schema": 1, "source": str(source),
    "files": records}, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"files": len(records), "bytes": sum(r["bytes"] for r in records),
                  "output": str(output)}, ensure_ascii=False))
