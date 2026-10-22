"""核對列表原型的自動選譯、原版狀態及實際 GPU 提交畫格。"""
import base64
import hashlib
import json
import sys
from pathlib import Path
from PIL import Image


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def check(en_run, zh_run, inputs, control, observed, output):
    assert not output.exists()
    a, b, oracle, trace = [read(p / "receipt.json") for p in (en_run, zh_run, control, observed)]
    assert not a["translate"] and b["translate"]
    assert a["prototype"] and b["prototype"]
    glyphs = read(inputs / "glyphs-16.json")
    assert glyphs["size"] == 16 and glyphs["height"] == 20
    alpha = {key: base64.b64decode(value) for key, value in glyphs["glyphs"].items()}
    assert all(len(v) == 320 and not any(v[256:]) for v in alpha.values())
    from ui_list_inputs import catalog
    zh = catalog(inputs / "zh-TW.tsv")
    for actual in (a, b):
        assert actual["initial_state_sha256"] == oracle["state_sha256"]
        assert actual["list_request_sha256"] == oracle["request_sha256"]
        assert actual["list_inputs_sha256"] == sha((inputs / "inputs.json").read_bytes())
        assert actual["catalog_sha256"] == sha((inputs / "zh-TW.tsv").read_bytes())
        assert actual["source_catalog_sha256"] == sha((inputs / "en.tsv").read_bytes())
        assert actual["glyphs_sha256"] == sha((inputs / "glyphs-16.json").read_bytes())
        assert not actual["unimplemented"] and not actual["final_words"]
        assert len(actual["checkpoints"]) == len(oracle["checkpoints"])
        for x, y in zip(actual["checkpoints"], oracle["checkpoints"]):
            for field in ("label", "step", "regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes"):
                assert x[field] == y[field], (field, x["step"])
        for field in ("regs", "ram_sha256", "indexed_sha256", "palette"):
            assert actual[field] == oracle["checkpoints"][-1][field]
    assert a["list_events"] == b["list_events"]
    accepted = [e for e in b["list_events"] if e["Kind"] == "word-before-glyph"]
    expected = [trace["calls"][i] for i in trace["shield_candidate_indices"]]
    assert len(accepted) == len(expected) > 0
    for event, original in zip(accepted, expected):
        wrapper = trace["wrappers"][original["wrapper_index"]]
        assert event["Step"] == wrapper["step"] < event["first_glyph"] == original["first_glyph"]
        assert event["detail"]["source_sha256"] == sha(original["vararg_1_candidate"]["text"].encode())
        wanted = "inventory.shield" if original["vararg_1_candidate"]["text"].startswith(" ") else "grimoire.shield"
        assert event["detail"]["key"] == wanted
    cleared = [e for e in b["list_events"] if e["Kind"] == "pane-cleared"]
    assert len(cleared) == (4 if len(accepted) == 4 else 1)
    assert all(e["detail"]["pixels"] == 384 * len(e["detail"]["targets"]) for e in cleared)
    assert all(e["detail"]["target_page"] == e["detail"]["visible_page"] for e in cleared)
    originals = {}
    for frame in a["frames"]:
        assert not frame["held"]
        originals[frame["step"]] = frame
    verified_pngs, cache = set(), {}

    def pixels(folder, frame):
        name = frame["File"]
        assert Path(name).name == name
        with Image.open(folder / name) as im:
            assert im.size == (640, 400)
            data = im.convert("RGBA").tobytes()
        assert sha(data) == frame["SHA256"]
        verified_pngs.add((str(folder), name))
        return data

    def compose(source, words, palette):
        px = bytearray(source)
        for w in words or []:
            x, y = w["X"] * 2, w["Y"] * 2
            assert 0 <= x < x + 96 <= 640 and 0 <= y < y + 16 <= 400
            fg, bg = palette[w["Foreground"]], palette[w["Background"]]
            row = bytes([*bg, 255]) * 96
            for yy in range(y, y + 16):
                at = (yy * 640 + x) * 4
                px[at:at + 384] = row
            for col, ch in enumerate(zh[w["Key"]]):
                for off, value in enumerate(alpha[ch][:256]):
                    if value:
                        yy, xx = divmod(off, 16)
                        at = ((y + yy) * 640 + x + col * 16 + xx) * 4
                        for channel in range(3):
                            px[at + channel] = (fg[channel] * value + px[at + channel] * (255 - value) + 127) // 255
        return sha(px)

    previous, held, translated_frames = None, 0, 0
    assert len(b["frames"]) == len(b["list_frames"])
    for frame, state in zip(b["frames"], b["list_frames"]):
        assert frame["step"] == state["step"] and frame["step"] in originals
        original = originals[frame["step"]]
        if frame["held"]:
            assert previous is not None
            expected_hash = previous
            held += 1
        else:
            if state["words"]:
                assert state["display_start"] == state["render_page"]
            key = (original["SHA256"], json.dumps(state["words"], sort_keys=True), json.dumps(state["palette"]))
            if key not in cache:
                cache[key] = compose(pixels(en_run, original), state["words"], state["palette"])
            expected_hash = cache[key]
            if state["words"]:
                translated_frames += 1
        assert frame["SHA256"] == expected_hash, (frame["step"], frame["held"])
        if (str(zh_run), frame["File"]) not in verified_pngs:
            pixels(zh_run, frame)
        previous = expected_hash
    assert translated_frames > 0
    config = read(inputs / "inputs.json")
    seen_steps = {f["step"] for f in b["frames"]}
    start = oracle["request"]["start_steps"]
    end = oracle["request"]["actions"][-1]["end"]
    for lo, hi in config["fine_windows"]:
        if start <= lo < hi <= end:
            assert all(step in seen_steps for step in range(lo + 2000, hi + 1, 2000)), (lo, hi)
    result = {"draft": True, "real_gpu_readback_frames": len(b["frames"]), "held_frames": held,
              "translated_frames": translated_frames, "original_checkpoints_equal": len(b["checkpoints"]),
              "automatic_terms": [e["detail"]["key"] for e in accepted], "clear_transactions": len(cleared),
              "all_submitted_pixels_equal_expected": True,
              "en_receipt_sha256": sha((en_run / "receipt.json").read_bytes()),
              "zh_receipt_sha256": sha((zh_run / "receipt.json").read_bytes()),
              "checker_sha256": sha(Path(__file__).read_bytes()),
              "limits": "固定正常旅店快照、一般按鍵及兩個詞條。不是完整列表、冷啟動、X11 按鍵、正式字級或正式中文化驗收。"}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("real_gpu_readback_frames", "held_frames", "original_checkpoints_equal", "clear_transactions")}, ensure_ascii=False))


if __name__ == "__main__":
    check(*map(Path, sys.argv[1:7]))
