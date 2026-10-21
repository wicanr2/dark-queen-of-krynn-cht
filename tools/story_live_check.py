#!/usr/bin/env python3
"""DRAFT：原始流程、現行 TSV、實際畫格及段落清除接續的交叉檢查。"""
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

from PIL import Image


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_catalog(path):
    with path.open() as file:
        rows = list(csv.DictReader(file, delimiter="\t", quoting=csv.QUOTE_NONE))
    result = {r["key"]: r["text"] for r in rows}
    assert len(rows) == len(result)
    return result


def main():
    root = Path(sys.argv[1])
    names = sys.argv[2:]
    assert len(names) == 7, "需原始觀測、控制、連續原文／16／20、首段細分原文／20 共七份目錄"
    observed, control = [json.loads((root / n / "trace.json").read_text()) for n in names[:2]]
    live = [json.loads((root / n / "receipt.json").read_text()) for n in names[2:]]
    en, zh = load_catalog(Path("/catalogs/en.tsv")), load_catalog(Path("/catalogs/zh-TW.tsv"))
    manifest = json.loads((root / names[0] / "runtime-inputs.json").read_text())
    assert manifest["source_catalog_sha256"] == sha(Path("/catalogs/en.tsv").read_bytes())
    assert manifest["translation_catalog_sha256"] == sha(Path("/catalogs/zh-TW.tsv").read_bytes())
    assert manifest["trace_sha256"] == sha((root / names[0] / "trace.json").read_bytes())
    assert not manifest["unmatched"]
    fields = ("step", "regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes")
    expected = [{k: c[k] for k in fields} for c in control["checkpoints"]]
    assert len(expected) == 9 and len(observed["paragraphs"]) == 7
    assert [{k: c[k] for k in fields} for c in observed["checkpoints"]] == expected
    assert not control["unimplemented"] and not observed["unimplemented"]
    original = observed["paragraphs"]
    assert [p["clear"] for p in original] == [1, 1, 1, 0, 0, 1, 0]
    source_keys = []
    for p in original:
        assert p["source"]["nul_terminated"]
        key = "ecl." + sha(p["source"]["text"].encode())[:20]
        assert en[key] == p["source"]["text"] and key in zh
        assert p["step"] < p["first_glyph"] < p["return_step"]
        source_keys.append(key)
    summaries, indexed_frames = [], []
    for name, receipt in zip(names[2:], live):
        checkpoints = receipt["checkpoints"]
        assert [{k: c[k] for k in fields} for c in checkpoints] == expected[:len(checkpoints)]
        assert len(checkpoints) in (1, 9) and not receipt["unimplemented"]
        pages = receipt["paragraphs"]
        assert len(pages) == (7 if len(checkpoints) == 9 else 1)
        parts = []
        for index, page in enumerate(pages):
            assert page["step"] == original[index]["step"] and page["Key"] == source_keys[index]
            assert page["Source"] == original[index]["source"]["text"]
            # 舊首段收據沒有 Components；文字仍須直接等於正式 catalog。
            clear = original[index]["clear"]
            if clear:
                parts = []
            parts.append(page["Key"])
            assert page["Text"] == "".join(zh[k] for k in parts)
            assert "".join(page["Lines"]) == page["Text"]
            assert page["Box"] == [16, 272, 624, 368]
            assert len(page["Lines"]) * (receipt["font_size"] + 4) <= 96
            assert all(len(line) * receipt["font_size"] <= 608 for line in page["Lines"])
        frames = {}
        regions = {}
        for frame in receipt["frames"]:
            file = Path(frame["File"])
            assert file.name == str(file)
            with Image.open(root / name / file) as im:
                assert im.size == (640, 400)
                pixels = im.convert("RGBA")
                assert sha(pixels.tobytes()) == frame["SHA256"]
                crop = sha(pixels.crop((16, 272, 624, 368)).tobytes())
                # 只存可交叉比對的摘要，避免把整段截圖留在記憶體。
                outside = pixels.copy()
                outside.paste((0, 0, 0, 0), (16, 272, 624, 368))
                outside_hash = sha(outside.tobytes())
            active = [i for i, p in enumerate(pages) if p["step"] <= frame["step"]]
            if receipt["translate"] and active:
                index = active[-1]
                assert regions.setdefault(index, crop) == crop, "同一中文段落露出逐字原文或殘字"
            frames[frame["step"]] = {"full": frame["SHA256"], "region": crop, "outside": outside_hash}
        events = dict(line.split() for line in (root / name / "memory-events.txt").read_text().splitlines())
        assert int(events["oom"]) == int(events["oom_kill"]) == 0
        summaries.append({"directory": name, "frames": len(receipt["frames"]), "paragraphs": len(pages),
                          "texture_uploads": receipt["texture_uploads"],
                          "receipt_sha256": sha((root / name / "receipt.json").read_bytes())})
        indexed_frames.append(frames)
    comparisons = []
    for a, b in [(0, 1), (0, 2), (3, 4)]:
        common = set(indexed_frames[a]) & set(indexed_frames[b])
        assert len(common) > 100
        for step in common:
            left, right = indexed_frames[a][step], indexed_frames[b][step]
            assert left["outside"] == right["outside"], "翻譯改變文字框外的畫面"
            if step < original[0]["step"]:
                assert left["full"] == right["full"]
        comparisons.append({"english": names[a + 2], "chinese": names[b + 2], "shared_steps": len(common)})
    fine = indexed_frames[-1]
    steps = sorted(s for s in fine if 334000000 <= s <= 335000000)
    assert steps[0] == 334000000 and steps[-1] == 335000000
    assert max(b - a for a, b in zip(steps, steps[1:])) <= 2000
    early = [s for s in fine if original[0]["step"] <= s < original[0]["first_glyph"]]
    assert early, "沒有取得原版首字元前的中文提交畫格"
    assert any(indexed_frames[-2][s]["region"] != fine[s]["region"] for s in early)
    report = {"draft": True, "scope": "seven normal story fragments; body only; font decision pending",
              "nine_guest_checkpoints_equal": True, "current_catalogs_match": True,
              "clear_flags": [p["clear"] for p in original], "frames": summaries,
              "outside_region_comparisons": comparisons, "first_chinese_steps_before_original_glyph": early,
              "limits": "No complete-game, scrolling, long-text pagination, prompt/menu localization or save/load claim."}
    output = root / names[4] / "comparison.json"
    assert output.parent.stat().st_uid == os.getuid() and not output.exists()
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
