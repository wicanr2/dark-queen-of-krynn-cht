"""由正式譯表與已觀測營地座標產生可丟棄原型輸入。"""

import csv
import hashlib
import json
import os
from pathlib import Path
import sys

from PIL import ImageFont


def sha(data):
    return hashlib.sha256(data).hexdigest()


def catalog(path):
    with path.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file, delimiter="\t", quoting=csv.QUOTE_NONE))
    result = {r["key"]: r["text"] for r in rows}
    assert len(result) == len(rows)
    return result


def main():
    texts, trace, output, font = map(Path, sys.argv[1:5])
    assert not output.exists() and (output.parent.stat().st_uid, output.parent.stat().st_gid) == (os.getuid(), os.getgid())
    r = json.loads(trace.read_text())
    assert r["input_sha256"] == "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
    assert r["source_commit"] == "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8"
    assert sha(font.read_bytes()) == "9d5bf4932d31fe94c18cd8cfddc98bc1b14ce10f4e354c682179db290a99c825"
    start = next(e["step"] for e in r["menu_events"] if e["kind"] == "render-entry" and e["count"] == 9)
    end = next(e["step"] for e in r["checkpoints"] if e["label"] == "saved-j")
    en, zh = catalog(texts / "en.tsv"), catalog(texts / "zh-TW.tsv")
    selected, bindings, seen = {}, [], set()
    for c in r["calls"]:
        s, text = c["stack"], c["format"]["text"]
        if not start <= c["step"] <= end or s[:2] != [0x01BE, 0x0CEB] or s[2] != 189 or len(text) < 2:
            continue
        assert c["format"]["nul_terminated"] and c["first_glyph"] - c["step"] == 345 and c["return_step"] > c["first_glyph"]
        digest = sha(text.encode("ascii"))
        key = "ui." + digest[:20]
        assert en[key] == text and key in zh
        pos = (s[3], s[2])
        if pos in seen:
            assert selected[digest] == zh[key]
            continue
        seen.add(pos)
        selected[digest] = zh[key]
        bindings.append({"source_sha256": digest, "catalog_key": key, "x": pos[0], "y": pos[1],
                         "source_field_width": len(text) * 16})
    assert len(selected) == len(bindings) == 10
    measurements = {}
    for size in [16, 20]:
        active_font = ImageFont.truetype(str(font), size)
        measurements[str(size)] = [{"catalog_key": v["catalog_key"], "field_width": v["source_field_width"],
            "advance": len(zh[v["catalog_key"]]) * size,
            "ink_bbox": active_font.getbbox(zh[v["catalog_key"]], anchor="lt"),
            "fits_original_word_width": len(zh[v["catalog_key"]]) * size <= v["source_field_width"]} for v in bindings]
    assert all(v["fits_original_word_width"] for v in measurements["16"])
    output.mkdir()
    for name in ["en.tsv", "zh-TW.tsv"]:
        (output / ("source-" + name)).write_bytes((texts / name).read_bytes())
    with (output / "zh-TW.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", quoting=csv.QUOTE_NONE, quotechar=None, lineterminator="\n")
        writer.writerow(["key", "text"])
        writer.writerows(sorted(selected.items()))
    report = {"draft": True, "bindings": bindings, "measurements": measurements,
              "trace_sha256": sha(trace.read_bytes()), "en_sha256": sha((texts / "en.tsv").read_bytes()),
              "zh_sha256": sha((texts / "zh-TW.tsv").read_bytes()), "alias_sha256": sha((output / "zh-TW.tsv").read_bytes()),
              "font_sha256": sha(font.read_bytes())}
    (output / "inputs.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已由正式 TSV 衍生十個短標籤，16 像素皆在原文字寬內；20 像素有超出項，未採用。")


if __name__ == "__main__":
    main()
