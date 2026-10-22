"""核對營地原型的實際提交畫面、原版狀態與存檔 J；不驗收正式中文化。"""

import base64
import hashlib
import json
import os
from pathlib import Path
import sys

from PIL import Image

from camp_live_inputs import catalog


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def pixels(run, frame):
    name = frame["File"]
    assert Path(name).name == name
    with Image.open(run / name) as image:
        assert image.size == (640, 400)
        data = image.convert("RGBA").tobytes()
    assert sha(data) == frame["SHA256"]
    return data


def compose(data, active, palette, glyphs):
    output = bytearray(data)
    for event in active.values():
        x, y = event["X"] * 2, event["Y"] * 2
        width = len(event["Source"]) * 16
        bg, fg = palette[(event["Color"] >> 4) & 15], palette[event["Color"] & 15]
        assert 0 <= x < x + width <= 640 and y == 378
        assert len(event["Text"]) * 16 <= width
        row = bytes([*bg, 255]) * width
        for yy in range(y, y + 16):
            start = (yy * 640 + x) * 4
            output[start:start + width * 4] = row
        for index, character in enumerate(event["Text"]):
            alpha = glyphs[character]
            assert len(alpha) == 320 and not any(alpha[256:])
            for offset, value in enumerate(alpha[:256]):
                if value:
                    yy, xx = divmod(offset, 16)
                    start = ((y + yy) * 640 + x + index * 16 + xx) * 4
                    for channel in range(3):
                        output[start + channel] = (fg[channel] * value + output[start + channel] * (255 - value) + 127) // 255
    return sha(output)


def main():
    root, inputs, current = map(Path, sys.argv[1:4])
    names = sys.argv[4:]
    assert len(names) == 2
    for name in names:
        assert Path(name).name == name and name not in (".", "..")
    manifest = read_json(inputs / "inputs.json")
    assert manifest["en_sha256"] == sha((inputs / "source-en.tsv").read_bytes())
    assert manifest["zh_sha256"] == sha((inputs / "source-zh-TW.tsv").read_bytes())
    en, zh = catalog(inputs / "source-en.tsv"), catalog(inputs / "source-zh-TW.tsv")
    current_en, current_zh = catalog(current / "en.tsv"), catalog(current / "zh-TW.tsv")
    subset = catalog(inputs / "zh-TW.tsv")
    bindings = {b["source_sha256"]: b for b in manifest["bindings"]}
    assert len(bindings) == len(subset) == 10
    for full, binding in bindings.items():
        key = binding["catalog_key"]
        assert sha(en[key].encode()) == full and zh[key] == subset[full]
        assert current_en[key] == en[key] and current_zh[key] == zh[key]
    glyph_data = read_json(inputs / "glyphs-16.json")
    assert glyph_data["size"] == 16 and glyph_data["height"] == 20
    assert glyph_data["font_sha256"] == manifest["font_sha256"]
    glyphs = {k: base64.b64decode(v) for k, v in glyph_data["glyphs"].items()}
    control_path = root / "save-load-control-r2-20261022/trace.json"
    control = read_json(control_path)
    assert sha(control_path.read_bytes()) == "5fe9f28d7f3ef208bf97b600b4840f294909aa526eef02cef0b3db6372df82f6"
    runs = [root / name for name in names]
    receipts = [read_json(run / "receipt.json") for run in runs]
    for translated, (run, receipt) in enumerate(zip(runs, receipts)):
        assert receipt["translate"] == bool(translated) and receipt["prototype"]
        assert receipt["steps"] == 715000000 and not receipt["unimplemented"]
        assert receipt["source_commit"] == "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8"
        assert receipt["initial_state_sha256"] == "7c5ce572b8cd979f03ffd423e80c2c3048ed404b44f49a9f42d834b6f6fbacc5"
        assert receipt["font_size"] == 16
        assert receipt["camp_inputs_sha256"] == sha((inputs / "inputs.json").read_bytes())
        assert receipt["catalog_sha256"] == manifest["alias_sha256"] == sha((inputs / "zh-TW.tsv").read_bytes())
        assert receipt["glyphs_sha256"] == sha((inputs / "glyphs-16.json").read_bytes())
        assert len(receipt["checkpoints"]) == 15
        for actual, original in zip(receipt["checkpoints"], control["checkpoints"][:15]):
            for field in ["step", "regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes"]:
                assert actual[field] == original[field], (name, actual["step"], field)
            assert not original["unimplemented"]
        for field in ["regs", "ram_sha256", "indexed_sha256", "palette"]:
            assert receipt[field] == control["checkpoints"][14][field]
        for event in receipt["events"]:
            binding = bindings[event["Key"]]
            assert sha(event["Source"].encode()) == event["Key"] and event["Text"] == subset[event["Key"]]
            assert (event["X"], event["Y"]) == (binding["x"], binding["y"])
        assert len(receipt["events"]) == 11 and len({v["Key"] for v in receipt["events"]}) == 10
        events = dict(line.split() for line in (run / "memory-events.txt").read_text().splitlines())
        assert int(events["oom"]) == int(events["oom_kill"]) == 0
    assert receipts[0]["events"] == receipts[1]["events"]
    assert receipts[0]["boundaries"] == receipts[1]["boundaries"]
    frames = [r["frames"] for r in receipts]
    assert [f["step"] for f in frames[0]] == [f["step"] for f in frames[1]]
    windows = []
    for start in [641000000, 666000000, 691000000]:
        steps = sorted({f["step"] for f in frames[0] if start <= f["step"] <= start + 1000000})
        assert steps[0] == start and steps[-1] == start + 1000000
        assert max(b - a for a, b in zip(steps, steps[1:])) <= 2000
        windows.append({"start": start, "end": steps[-1], "distinct_steps": len(steps)})
    timeline = [(v["step"], "clear", None) for v in receipts[1]["boundaries"] if v["kind"] == "transition-render-entry"]
    timeline += [(v["step"], "text", v) for v in receipts[1]["events"]]
    timeline.sort(key=lambda v: v[0])
    cursor, active = 0, {}
    seen = [{}, {}]
    expected_cache = {}
    held_counts = [0, 0]
    previous = [None, None]
    complete_counts = set()
    for left, right in zip(*frames):
        while cursor < len(timeline) and timeline[cursor][0] <= right["step"]:
            _, kind, event = timeline[cursor]
            if kind == "clear":
                active.clear()
            else:
                active[event["X"], event["Y"]] = event
            cursor += 1
        assert left["held"] == right["held"] and left["active"] == right["active"] == len(active)
        for index, frame in enumerate([left, right]):
            if frame["File"] not in seen[index]:
                pixels(runs[index], frame)
                seen[index][frame["File"]] = frame["SHA256"]
            assert seen[index][frame["File"]] == frame["SHA256"]
            if frame["held"]:
                assert frame["SHA256"] == previous[index], "過渡幀未保留完整畫面"
                held_counts[index] += 1
            previous[index] = frame["SHA256"]
        if not right["held"]:
            assert len(active) in (0, 8, 2), "提交尚未完整建立的營地或確認選單"
            complete_counts.add(len(active))
            state = tuple((v["Key"], v["Color"], v["X"], v["Y"]) for v in active.values())
            signature = (left["SHA256"], state, tuple(map(tuple, right["camp_palette"])))
            if signature not in expected_cache:
                expected_cache[signature] = compose(pixels(runs[0], left), active, right["camp_palette"], glyphs)
            assert right["SHA256"] == expected_cache[signature], (right["step"], "中文合成或原文字框外像素不同")
    assert complete_counts == {0, 8, 2} and min(held_counts) > 0
    for step, count in [(665000000, 8), (690000000, 0), (715000000, 2)]:
        assert any(f["step"] == step and f["active"] == count and not f["held"] for f in frames[1])
    save_files = []
    for name, size, digest in [
        ("SavGamJ.qsv", 7965, "72a45079a189126c3a96d4681fac846086a6edaf26748d260d3a73fbc8905488"),
        ("VaultJ.DAT", 866, "2acc13fa21f319fac65ad823d7ca52f1ed02d13ce8708431f7ce5c116d9db7ba"),
    ]:
        for run in [*runs, control_path.parent]:
            file = run / "scratch/SAVE" / name
            assert file.stat().st_size == size and sha(file.read_bytes()) == digest
        save_files.append({"name": name, "bytes": size, "sha256": digest})
    report = {"draft": True, "runs": names, "frames_per_run": len(frames[0]),
              "held_frames": held_counts, "distinct_images": list(map(len, seen)),
              "fine_windows": windows, "matching_guest_checkpoints_per_run": 15,
              "all_submitted_pixels_verified": True, "save_files": save_files,
              "receipt_sha256": [sha((r / "receipt.json").read_bytes()) for r in runs],
              "tool_sha256": sha(Path(__file__).read_bytes()),
              "limits": "Ten footer labels, normal Inn/Save/J only; disposable 16px prototype. No production, GUI cold load, all slots, full localization or HD claim."}
    target = runs[1] / "camp-comparison.json"
    assert (target.parent.stat().st_uid, target.parent.stat().st_gid) == (os.getuid(), os.getgid())
    if target.exists():
        assert read_json(target) == report
    else:
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
