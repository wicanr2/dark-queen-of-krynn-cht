"""檢查原版介面觀測及無觀測控制組，不生成譯文或修改原版狀態。"""

import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check(observed, control, output, role):
    if output.exists():
        raise ValueError("輸出必須全新")
    a = json.loads((observed / "receipt.json").read_text())
    b = json.loads((control / "receipt.json").read_text())
    assert a["draft"] and b["draft"] and a["observe"] and not b["observe"]
    for field in ("source_commit", "go_version", "exe_sha256", "state_sha256",
                  "request_sha256", "probe_sha256", "request", "checkpoints"):
        assert a[field] == b[field], field
    assert a["source_commit"] == "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8"
    assert a["exe_sha256"] == "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
    assert a["pending_calls"] == b["pending_calls"] == 0, "觀測呼叫尚未封閉"
    if "paragraphs" in a:
        assert a["pending_paragraphs"] == b["pending_paragraphs"] == 0
        assert not b["paragraphs"]
        for i, paragraph in enumerate(a["paragraphs"] or []):
            s, source, regs = paragraph["stack"], paragraph["source"], paragraph["regs"]
            assert (regs["CS"], regs["IP"]) == (0xB72, 0x311)
            assert source["nul_terminated"] and bytes.fromhex(source["hex"]).decode("ascii") == source["text"]
            assert (source["segment"], source["offset"]) == (s[10], s[9])
            assert source["offset"]+len(source["text"])+1 <= 65536
            assert source["segment"]*16+source["offset"]+len(source["text"])+1 <= 0xA0000
            assert paragraph["caller"] == {"Seg":s[1], "Off":s[0]}
            assert paragraph["native_box"] == [(s[2]&255)*8,(s[3]&255)*8,((s[4]&255)+1)*8,((s[5]&255)+1)*8]
            assert [paragraph[k] for k in ("foreground","background","clear")] == [s[n]&255 for n in (6,7,8)]
            calls = [c for c in a["calls"] if c.get("paragraph_index",-1)==i]
            assert calls and all(paragraph["step"] < c["step"] < c["return_step"] < paragraph["return_step"] for c in calls)
            assert all(c["format"]["text"] == "%c" and c["caller"] == {"Seg":0xB72,"Off":0x2E3} for c in calls)
            assert bytes(c["stack"][7]&255 for c in calls).decode("ascii") == source["text"]
            assert paragraph["first_glyph"] == calls[0]["first_glyph"] > paragraph["step"]
    if "fill_events" in a:
        assert a["pending_fills"] == b["pending_fills"] == 0, "填色要求尚未封閉"
        assert not b["fill_events"]
        for event in a["fill_events"]:
            assert event["step"] < event["return_instruction_step"]
            assert len(event["native_rect"]) == 4
    lists = a.get("list_events") or []
    scrolls = a.get("scroll_events") or []
    scroll_pixels = {}
    scroll_geometry = {}
    scroll_checks = []
    if "scroll_events" in a:
        assert a["pending_scrolls"] == b["pending_scrolls"] == 0, "捲動尚未封閉"
        assert not b["scroll_events"]
        for i, event in enumerate(scrolls):
            assert event["step"] < event["return_step"]
            pixels = []
            for field in ("indexed_before", "indexed_after"):
                name = event[field]
                assert Path(name).name == name
                raw = (observed / name).read_bytes()
                assert len(raw) == 64000
                pixels.append(Image.frombytes("L", (320, 200), raw))
            scroll_pixels[i] = pixels
            y0, x0, y1, x1, source_dy, source_dx = [(v - 8000) * 2 for v in event["stack"][2:8]]
            dx, dy = -source_dx, -source_dy
            assert 0 <= x0 < x1 <= 320 and 0 <= y0 < y1 <= 200
            sx0, sy0 = max(x0, x0 - dx), max(y0, y0 - dy)
            sx1, sy1 = min(x1, x1 - dx), min(y1, y1 - dy)
            assert sx0 < sx1 and sy0 < sy1
            moved_pixels = pixels[0].crop((sx0, sy0, sx1, sy1)).tobytes()
            assert moved_pixels == pixels[1].crop((sx0 + dx, sy0 + dy, sx1 + dx, sy1 + dy)).tobytes()
            scroll_geometry[i] = (x0, y0, x1, y1, dx, dy)
            scroll_checks.append({"scroll_index": i, "source_native_rect": [sx0, sy0, sx1 - sx0, sy1 - sy0],
                                  "delta_native": [dx, dy], "copied_region_pixels_equal": True,
                                  "source_pixels_sha256": sha(moved_pixels),
                                  "before_indexed_sha256": sha(pixels[0].tobytes()),
                                  "after_indexed_sha256": sha(pixels[1].tobytes())})
    if "list_events" in a:
        assert a["pending_lists"] == b["pending_lists"] == 0, "列表繪製尚未封閉"
        assert not b["list_events"], "控制組不應裝觀測掛勾"
        for event in lists:
            assert event["step"] < event["return_instruction_step"]
            assert len(bytes.fromhex(event["descriptor_before_hex"])) == 24
            assert len(bytes.fromhex(event["descriptor_after_hex"])) == 24
            assert len(bytes.fromhex(event["callback_bytes_hex"])) == 64
    assert len(a["checkpoints"]) == len(a["request"]["actions"])
    images = []
    for checkpoint in a["checkpoints"]:
        assert not checkpoint["file_writes"] and not checkpoint["unimplemented"]
        label = checkpoint["label"]
        assert label and Path(label).name == label
        with Image.open(observed / (label + ".png")) as x, Image.open(control / (label + ".png")) as y:
            assert x.size == y.size == (320, 200)
            pixels = x.convert("RGB").tobytes()
            assert pixels == y.convert("RGB").tobytes(), label
            images.append({"label": label, "rgb_sha256": sha(pixels)})
    for folder in (observed, control):
        assert sha((folder / "ram.bin").read_bytes()) == a["checkpoints"][-1]["ram_sha256"]
    matches = []
    for index, call in enumerate(a["calls"]):
        source = call["vararg_1_candidate"]
        text = source["text"]
        matched = (role == "inventory" and re.fullmatch(r" (Yes|No)\tShield(?: \+\d+)? ", text))
        matched = matched or (role == "grimoire" and text == "\tShield")
        if not matched:
            continue
        assert call["format"]["text"] == "%s" and call["format"]["hex"] == "2573"
        assert call["format"]["nul_terminated"] and source["nul_terminated"]
        assert bytes.fromhex(source["hex"]).decode("ascii") == text
        assert call["step"] < call["first_glyph"] < call["return_step"]
        match = {"call_index": index, "step": call["step"],
                        "first_glyph": call["first_glyph"], "return_step": call["return_step"],
                        "lead_instructions": call["first_glyph"] - call["step"],
                        "caller": call["caller"], "format_pointer": [call["format"]["segment"], call["format"]["offset"]],
                        "buffer_pointer": [source["segment"], source["offset"]],
                        "source_hex": source["hex"]}
        if lists:
            assert call["wrapper_index"] >= 0
            wrapper = a["wrappers"][call["wrapper_index"]]
            enclosing = [(j, e) for j, e in enumerate(lists)
                         if e["step"] < wrapper["step"] < call["step"]
                         < call["return_step"] < e["return_instruction_step"]]
            assert len(enclosing) == 1, "須有唯一包住完整字串的列表繪製"
            event_index, event = enclosing[0]
            assert wrapper["format"]["text"] == "%s"
            assert wrapper["format"]["nul_terminated"]
            assert wrapper["vararg_1_candidate"]["hex"] == source["hex"]
            assert wrapper["vararg_1_candidate"]["nul_terminated"]
            glyphs = call["glyph_calls"]
            assert bytes(g["stack"][4] for g in glyphs).decode("ascii") == text
            col, row = wrapper["stack"][2:4]
            fg, bg = wrapper["stack"][4] & 255, wrapper["stack"][5] & 255
            for n, glyph in enumerate(glyphs):
                y, x, char, color = glyph["stack"][2:6]
                assert (x, y) == (8 * (col + n), 8 * row)
                assert (glyph["ds_ca12"], glyph["ds_ca14"]) == (x, y)
                assert color == bg * 16 + fg
                assert call["step"] < glyph["step"] < call["return_step"]
            word_start = text.index("Shield")
            rect = [8 * (col + word_start), 8 * row, 48, 8]
            moved = []
            for j, scroll in enumerate(scrolls):
                if not call["return_step"] < scroll["step"] < event["return_instruction_step"]:
                    continue
                assert scroll["return_step"] < event["return_instruction_step"]
                # 此 helper 的參數指定讀取來源位移；可見像素朝反方向搬移。
                # 下方以原版前後色號逐位元組核對，不能只靠數值命名推定。
                x0, y0, x1, y1, dx, dy = scroll_geometry[j]
                x, y, w, h = rect
                intersects = x < x1 and x + w > x0 and y < y1 and y + h > y0
                if not intersects:
                    continue
                assert x0 <= x < x + w <= x1 and y0 <= y < y + h <= y1
                assert 0 <= x + dx < x + dx + w <= 320
                assert 0 <= y + dy < y + dy + h <= 200
                before, after = scroll_pixels[j]
                source_pixels = before.crop((x, y, x + w, y + h)).tobytes()
                assert source_pixels == after.crop((x + dx, y + dy, x + dx + w, y + dy + h)).tobytes()
                rect = [x + dx, y + dy, w, h]
                moved.append({"scroll_index": j, "delta_native": [dx, dy],
                              "source_pixels_sha256": sha(source_pixels), "word_pixels_moved_equal": True})
            match.update({"wrapper_index": call["wrapper_index"],
                          "wrapper_step": wrapper["step"],
                          "wrapper_lead_instructions": call["first_glyph"] - wrapper["step"],
                          "wrapper_caller": wrapper["caller"], "list_index": event_index,
                          "list_callback": event["callback"],
                          "list_callback_sha256": sha(bytes.fromhex(event["callback_bytes_hex"])),
                          "descriptor_before_hex": event["descriptor_before_hex"],
                          "descriptor_after_hex": event["descriptor_after_hex"],
                          "word_native_rect": [8 * (col + word_start), 8 * row, 48, 8],
                          "word_after_list_native_rect": rect, "word_scrolls": moved,
                          "foreground": fg, "background_argument": bg})
        matches.append(match)
    if role != "none":
        assert matches, "沒有在指定玩家路徑觀測到 Shield"
    result = {"draft": True, "checkpoints_equal": len(images), "images_equal": images,
              "role": role, "native_list_transactions": len(lists),
              "native_scroll_transactions": len(scrolls), "shield_occurrences": matches,
              "scroll_copy_checks": scroll_checks,
              "observed_receipt_sha256": sha((observed / "receipt.json").read_bytes()),
              "control_receipt_sha256": sha((control / "receipt.json").read_bytes()),
              "checker_sha256": sha(Path(__file__).read_bytes()),
              "limits": "role 由已知按鍵流程標記，並非 runtime 語境分類器。僅證明此流程的觀測隔離、字串時間與已捕獲列表邊界；未翻譯，未證實任意 vararg、全域語境判定、冷啟動 GUI 或中文覆繪。"}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return {"checkpoints_equal": len(images), "role": role,
            "shield_occurrences": len(matches),
            "lead_instructions": sorted({m["lead_instructions"] for m in matches})}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("observed", type=Path)
    parser.add_argument("control", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--role", choices=("inventory", "grimoire", "none"), default="none")
    args = parser.parse_args()
    print(json.dumps(check(args.observed, args.control, args.output, args.role), ensure_ascii=False))
