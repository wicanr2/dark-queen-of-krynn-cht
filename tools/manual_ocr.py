"""本機掃描的 OCR 草稿，禁止當作已校訂正文；在專用容器內執行。"""

import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image


source, output = map(Path, sys.argv[1:3])
output.mkdir(parents=True, exist_ok=True)
if output.stat().st_uid != os.getuid():
    raise RuntimeError("輸出擁有權不符")
os.environ["OMP_THREAD_LIMIT"] = "1"
tasks = []
# 先完成旅行手札，再處理操作與規則。掃描都是跨頁，拆成左右頁再辨識。
order = list(range(87, 112)) + list(range(5, 44)) + list(range(45, 87))
for number in order:
    scan = source / f"Image{number:03d}.jpg"
    with Image.open(scan) as image:
        width, height = image.size
        for side, bounds in (
            ("left", (0, 0, width // 2, height)),
            ("right", (width // 2, 0, width, height)),
        ):
            key = f"{scan.stem}-{side}"
            crop = output / f"{key}.png"
            image.crop(bounds).convert("L").save(crop)
            tasks.append((key, crop, scan.name, bounds))


def recognize(task):
    key, crop, scan, bounds = task
    destination = output / key
    run = subprocess.run(
        ["tesseract", str(crop), str(destination), "-l", "chi_tra+eng", "--psm", "3"],
        capture_output=True, text=True, timeout=90,
    )
    (output / f"{key}.log").write_text(run.stderr)
    text = destination.with_suffix(".txt")
    if run.returncode or not text.is_file():
        raise RuntimeError(f"OCR 失敗：{key}，見該頁 log")
    content = text.read_bytes()
    return {"key": key, "source": scan, "crop": bounds,
            "text_sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content), "status": "OCR draft, not proofread"}


rows = []
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    for result in executor.map(recognize, tasks):
        rows.append(result)
        if len(rows) % 20 == 0:
            print("OCR", len(rows), "/", len(tasks), flush=True)
metadata = {"tool": subprocess.check_output(["tesseract", "--version"], text=True).splitlines()[0],
            "language": "chi_tra+eng", "psm": 3, "pages": rows,
            "status": "All output is unreviewed OCR; not a production TSV"}
(output / "manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
print("OCR draft complete", len(rows), flush=True)
