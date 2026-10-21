"""驗證冷啟動、X11 事件、真實視窗擷取及原版按鍵重播；結果限此研究原型。"""
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

from PIL import Image


def sha(data):
    return hashlib.sha256(data).hexdigest()


def catalog(path):
    with path.open() as file:
        rows = list(csv.DictReader(file, delimiter="\t", quoting=csv.QUOTE_NONE))
    result = {r["key"]: r["text"] for r in rows}
    assert len(result) == len(rows)
    return result


def main():
    root, inputs = map(Path, sys.argv[1:3])
    names = sys.argv[3:]
    assert len(names) == 2, "需取消返回與開始冒險兩條 GUI 路徑"
    manifest = json.loads((inputs / "inputs.json").read_text())
    assert manifest["en_sha256"] == sha((inputs / "source-en.tsv").read_bytes())
    assert manifest["zh_sha256"] == sha((inputs / "source-zh-TW.tsv").read_bytes())
    en, zh = catalog(inputs / "source-en.tsv"), catalog(inputs / "source-zh-TW.tsv")
    current_en, current_zh = catalog(Path("/catalogs/en.tsv")), catalog(Path("/catalogs/zh-TW.tsv"))
    subset = catalog(inputs / "zh-TW.tsv")
    assert len(subset) == len(manifest["bindings"]) == 12
    for binding in manifest["bindings"]:
        key, full = binding["catalog_key"], binding["source_sha256"]
        assert sha(en[key].encode()) == full and subset[full] == zh[key]
        assert current_en[key] == en[key] and current_zh[key] == zh[key], "已驗證選單的正式文字依賴改變"
    reports = []
    for index, name in enumerate(names):
        path = root / name
        raw = (path / "receipt.json").read_bytes()
        r = json.loads(raw)
        assert r["cold_boot"] and "initial_state_sha256" not in r
        assert r["source_commit"] == "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8"
        assert r["catalog_sha256"] == manifest["output_sha256"] == sha((inputs / "zh-TW.tsv").read_bytes())
        assert r["glyphs_sha256"] == sha((inputs / "glyphs-20.json").read_bytes())
        expected = [("text", " ")] * 7 + [("text", k) for k in ("ple" if index == 0 else "pltabx")]
        if index:
            expected.append(("named", "Backspace"))
        assert [(v["kind"], v["value"]) for v in r["inputs"]] == expected
        control = json.loads((root / (name + "-control") / "comparison.json").read_text())
        assert control["matched_gui_guest"] and control["input_receipt_sha256"] == sha(raw)
        assert control["input_count"] == len(expected)
        checkpoint = r["checkpoints"][-1]
        for field in ["steps", "regs", "ram_sha256", "indexed_sha256", "palette"]:
            assert control[field] == r[field]
        for field in ["keys_consumed", "file_writes"]:
            assert control[field] == checkpoint[field]
        assert control["keys_consumed"] == len(expected) and not control["file_writes"] and not control["unimplemented"]
        checked = {}
        previous = None
        for frame in r["frames"]:
            file = Path(frame["File"])
            assert file.name == str(file)
            if file not in checked:
                with Image.open(path / file) as im:
                    assert im.size == (640, 400) and sha(im.convert("RGBA").tobytes()) == frame["SHA256"]
                checked[file] = frame["SHA256"]
            assert checked[file] == frame["SHA256"]
            if frame["held"]:
                assert frame["SHA256"] == previous, "過渡期間沒有保留完整畫面"
            if 0 < frame["active"] < 12:
                assert frame["held"], "提交了尚未完整建立的角色選單中文"
            previous = frame["SHA256"]
        for event in r["events"]:
            assert sha(event["Source"].encode()) == event["Key"] and event["Text"] == subset[event["Key"]]
        capture = json.loads((path / "x11-capture.json").read_text())
        assert (capture["width"], capture["height"]) == (640, 400)
        with Image.open(path / "actual-window.ppm") as im:
            assert im.size == (640, 400)
            visible_sha = sha(im.convert("RGBA").tobytes())
        matches = [f["step"] for f in r["frames"] if capture["step"] - 2000000 <= f["step"] <= r["steps"] and f["SHA256"] == visible_sha]
        assert matches, "X11 視窗畫面與近期實際提交不同"
        events = dict(line.split() for line in (path / "memory-events.txt").read_text().splitlines())
        assert int(events["oom"]) == int(events["oom_kill"]) == 0
        if index:
            escape = [b for b in r["boundaries"] if b["kind"] == "begin-adventure-native-hud"]
            assert len(escape) == 1 and escape[0]["step"] > escape[0]["selection_step"]
            assert r["frames"][-1]["active"] == 0 and not r["frames"][-1]["held"]
        else:
            assert r["frames"][-1]["active"] == 12 and not r["frames"][-1]["held"]
        reports.append({"directory": name, "steps": r["steps"], "inputs": len(expected), "frames": len(r["frames"]),
                        "distinct_images": len(checked), "x11_matching_steps": matches, "receipt_sha256": sha(raw),
                        "ram_sha256": r["ram_sha256"]})
    output = root / names[-1] / "gui-verification.json"
    assert output.parent.stat().st_uid == os.getuid()
    result = {"draft": True, "cold_boot_without_snapshot": True, "real_x11_keyboard_and_window_capture": True,
              "original_guest_replay_equal": True, "runs": reports,
              "limits": "Keyboard prototype and twelve character labels only; no complete localization, production, mouse, IME, audio, long-text or save/load claim."}
    if output.exists():
        assert json.loads(output.read_text()) == result, "重驗結果與原有收據不同"
    else:
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
