"""索引未校對的手札標題，保留來源編號，不用連續陣列重編號。"""

import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata


root, output = map(Path, sys.argv[1:3])
manifest_path = root / "manifest.json"
manifest = json.loads(manifest_path.read_text())
if not manifest["complete"] or manifest["errors"]:
    raise ValueError("來源批次尚未完整成功")
entries = {}
for page in manifest["pages"]:
    match = re.fullmatch(r"Image(\d+)-(left|right)\.png", page["source"])
    if not match or not 87 <= int(match[1]) <= 111:
        continue
    result = json.loads((root / page["output"]).read_text())["result"]
    for index, text in enumerate(result["rec_texts"]):
        heading = re.fullmatch(r"旅行手札\s*(\d+)", unicodedata.normalize("NFKC", text))
        if not heading:
            continue
        number = int(heading[1])
        if number in entries:
            raise ValueError(f"重複手札編號：{number}")
        entries[number] = {"id": number, "source": page["source"],
                           "source_sha256": page["source_sha256"], "region": index,
                           "polygon": result["rec_polys"][index], "heading_raw": text,
                           "confidence": result["rec_scores"][index],
                           "status": "OCR heading, not proofread"}
if not entries:
    raise ValueError("沒有找到手札標題")
missing = sorted(set(range(1, max(entries) + 1)) - entries.keys())
output.write_text(json.dumps({"schema": 1, "status": "research index, not runtime catalog",
    "source_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    "entries": [entries[number] for number in sorted(entries)], "missing_ids": missing},
    ensure_ascii=False, indent=2) + "\n")
print(f"手札標題 {len(entries)} 則，未見編號：{missing}")
