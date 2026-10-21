"""從實際繪製前事件合成可丟棄原型，不能當作正式 GUI 已通過。"""

import csv
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


root, font_path = map(Path, sys.argv[1:3])
trace = json.loads((root / "trace.json").read_text())
control = json.loads((root.parent / "early-control/trace.json").read_text())
for field in ("steps", "regs", "ram_sha256", "indexed_sha256", "palette"):
    if trace[field] != control[field]:
        raise ValueError(f"觀測與控制組不一致：{field}")
with (root / "zh-TW.tsv").open() as f:
    rows = list(csv.DictReader(f, delimiter="\t"))
catalog = {row["key"]: row["text"] for row in rows}
if len(catalog) != len(rows):
    raise ValueError("重複 key")
events = trace["events"]
plain = [event for event in events if event["key"] in catalog]
if len(plain) != 12 or any(event["first_glyph"] <= event["step"] for event in plain):
    raise ValueError("預期 12 個已驗證的繪製前選單事件")
palette = [tuple(color) for color in trace["palette"]]
output = root / "preview"
output.mkdir(exist_ok=True)
report = {"prototype": True, "guest_unchanged": True,
          "source_events": len(plain), "frames": len(trace["frames"]),
          "minimum_instruction_lead": min(e["first_glyph"] - e["step"] for e in plain),
          "font_sha256": hashlib.sha256(font_path.read_bytes()).hexdigest(),
          "scope": "recorded initial character-menu transition only; offline composition, not live GUI",
          "variants": []}
for size in (16, 20):
    font = ImageFont.truetype(str(font_path), size)
    frames = []
    for frame in trace["frames"]:
        base = Image.open(root / frame["file"]).convert("RGB")
        image = base.resize((640, 400), Image.Resampling.NEAREST)
        draw = ImageDraw.Draw(image)
        active = {}
        for event in events[:frame["events"]]:
            point = (event["x"], event["y"])
            if event["key"] in catalog:
                active[point] = event
        for event in active.values():
            x, y = event["x"] * 2, event["y"] * 2
            width = len(event["source"]) * 16
            draw.rectangle((x, y, x + width - 1, y + 15),
                           fill=palette[(event["color"] >> 4) & 15])
            text = catalog[event["key"]]
            bbox = draw.textbbox((0, 0), text, font=font, anchor="lt")
            if bbox[2] > width or bbox[3] > 24:
                raise ValueError(f"譯文超出原型安全框：{event['key']}")
            draw.text((x, y - max(0, size - 16) // 2), text, font=font, anchor="lt",
                      fill=palette[event["color"] & 15])
        frames.append(image)
    # 一千步級的連續原型只保存事件區間與少量停留，不把機器步數冒稱實機播放時間。
    selected = [image for index, image in enumerate(frames)
                if 90 <= index <= 415 and index % 4 == 0]
    frames[-1].save(output / f"menu-{size}px.png")
    selected[0].save(output / f"transition-{size}px.gif", save_all=True,
                     append_images=selected[1:] + [frames[-1]] * 15,
                     duration=40, loop=0)
    report["variants"].append({"font_size": size, "composed_frames": len(frames)})
(output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report, ensure_ascii=False))
