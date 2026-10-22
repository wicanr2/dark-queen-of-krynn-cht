"""核對列表原型的自動選譯、原版狀態及實際 GPU 提交畫格。"""
import base64
import hashlib
import json
import struct
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
    en = catalog(inputs / "en.tsv")
    config = read(inputs / "inputs.json")
    # 從原版整表 bytes 獨立重建按鈕順序、文字指標、座標及指紋。
    native = lambda value: value if value < 400 else (value - 8000) * 2
    for menu in [*trace["menus"], *(e["menu_snapshot"] for e in trace["list_events"] if "menu_snapshot" in e)]:
        raw = bytes.fromhex(menu["RawHex"])
        assert len(raw) == menu["Count"] * 32
        indices = [i for i in range(menu["Count"]) if struct.unpack_from("<HH", raw, i*32) == (0x8E, 0xCEB)]
        assert indices == [b["Index"] for b in menu["Buttons"]]
        signature = []
        for button in menu["Buttons"]:
            record = raw[button["Index"]*32:][:32]
            off, seg, y, x = struct.unpack_from("<HHHH", record, 12)
            assert button["SourcePointer"] == {"Seg": seg, "Off": off}
            assert (button["RawX"], button["RawY"]) == (x, y)
            assert sha(bytes.fromhex(button["SourceHex"])) == button["SHA256"]
            signature.append([button["Index"], button["SHA256"], x, y])
        assert sha(json.dumps([menu["Count"], signature], separators=(",", ":")).encode()) == menu["Signature"]
        if menu["Signature"] in config["Menus"]:
            for button in menu["Buttons"]:
                text = bytes.fromhex(button["SourceHex"]).decode("ascii")
                matches = [f for f in config["Fields"] if f["Pane"] == "menu" and f["MenuSignature"] == menu["Signature"]
                           and f["RawX"] == native(button["RawX"]) and f["RawY"] == native(button["RawY"])+1
                           and f["SHA256"] == button["SHA256"] and f["FormatSHA256"] == button["SHA256"]
                           and f["Caller"] == {"Seg": 0xCEB, "Off": 0x1BE}]
                assert len(matches) == 1
                field = matches[0]
                assert field["Group"] == "footer" and field["Start"] == 0 and field["Length"] == len(text)
                assert en[field["Key"]] == text
    def menu_signature(call):
        index = call.get("menu_index", -1)
        return trace["menus"][index]["Signature"] if index >= 0 else ""
    for c in trace["calls"]:
        if c["caller"] != {"Seg": 0xCEB, "Off": 0x1BE}:
            continue
        assert c["menu_index"] >= 0
        menu = trace["menus"][c["menu_index"]]
        buttons = [b for b in menu["Buttons"] if b["SourceHex"] == c["format"]["hex"]
                   and native(b["RawX"]) == native(c["stack"][3]) and native(b["RawY"])+1 == native(c["stack"][2])]
        assert len(buttons) == 1
    for actual in (a, b):
        assert actual["initial_state_sha256"] == oracle["state_sha256"]
        assert actual["list_request_sha256"] == oracle["request_sha256"]
        assert actual["list_inputs_sha256"] == sha((inputs / "inputs.json").read_bytes())
        assert actual["catalog_sha256"] == sha((inputs / "zh-TW.tsv").read_bytes())
        assert actual["source_catalog_sha256"] == sha((inputs / "en.tsv").read_bytes())
        assert actual["glyphs_sha256"] == sha((inputs / "glyphs-16.json").read_bytes())
        assert not actual["unimplemented"]
        assert len(actual["checkpoints"]) == len(oracle["checkpoints"])
        for x, y in zip(actual["checkpoints"], oracle["checkpoints"]):
            for field in ("label", "step", "regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes"):
                assert x[field] == y[field], (field, x["step"])
        for field in ("regs", "ram_sha256", "indexed_sha256", "palette"):
            assert actual[field] == oracle["checkpoints"][-1][field]
    assert a["list_events"] == b["list_events"]
    accepted = [e for e in b["list_events"] if e["Kind"] == "row-before-glyph"]
    bindings = {(row["Pane"], row["SHA256"]): row for row in config["Rows"]}
    wrappers, pane = {}, ""
    timeline = []
    for fill in trace["fill_events"]:
        x, y, w, h = fill["native_rect"]
        if not fill["within_list"] and x <= 8 and y <= 8 and x+w >= 312 and y+h >= 184:
            timeline.append((fill["step"], ""))
    for wrapper in trace["wrappers"]:
        if wrapper["stack"][3] & 255 == 1:
            found = [h["Pane"] for h in config["Headers"] if wrapper["format"]["segment"] == h["Segment"]
                     and wrapper["format"]["offset"] == h["Offset"] and sha(wrapper["format"]["text"].encode()) == h["SHA256"]]
            timeline.append((wrapper["step"], found[0] if found else ""))
    contexts = []
    for original in trace["list_events"]:
        for source in config["PaneLists"]:
            if source["DescriptorSHA256"] == sha(bytes.fromhex(original["descriptor_before_hex"])) \
                    and source["Caller"] == {"Seg": original["stack"][1], "Off": original["stack"][0]} \
                    and source["MenuSignature"] == original.get("menu_snapshot", {}).get("Signature"):
                contexts.append((original["step"], source))
                timeline.append((original["step"], source["Pane"]))
    hits = [e for e in b["list_events"] if e["Kind"] == "list-context"]
    assert len(hits) == len(contexts)
    for event, (step, source) in zip(hits, contexts):
        assert event["Step"] == step and event["Pane"] == source["Pane"]
        assert event["detail"] == {"descriptor_sha256": source["DescriptorSHA256"], "menu_signature": source["MenuSignature"], "caller": source["Caller"]}
    baselines = [e for e in b["list_events"] if e["Kind"] == "list-page-baseline"]
    pages = [e for e in b["list_events"] if e["Kind"] == "list-render-page"]
    assert len(baselines) == len(pages) == sum(s["RowFillPage"] for _, s in contexts)
    for baseline, page in zip(baselines, pages):
        fill = next(f for f in trace["fill_events"] if f["step"] <= baseline["Step"] <= f["return_instruction_step"]
                    and f["native_rect"] == baseline["detail"] and f["within_list"])
        assert baseline["Step"] < page["Step"] <= fill["return_instruction_step"]
        x, y, width, height = fill["native_rect"]
        assert width > 0 and height > 0 and x % 4 == 0
        assert page["detail"]["origin"] == [x, y]
        assert page["detail"]["target_page"] == (page["detail"]["first_write_offset"] - y*80-x//4) & 65535
        assert page["detail"]["target_page"] in (0, 16384)
    timeline.sort()
    actor_headers = []
    for step, source in contexts:
        if source["Pane"] != "effects":
            continue
        listing = next(e for e in trace["list_events"] if e["step"] == step)
        end = next(f["step"] for f in trace["fill_events"] if f["step"] > listing["return_instruction_step"]
                   and f["native_rect"] == [8, 8, 304, 176])
        for wrapper in trace["wrappers"]:
            if listing["step"] <= wrapper["step"] <= listing["return_instruction_step"] and wrapper["stack"][4] & 255 == 12:
                text = wrapper["vararg_1_candidate"]["text"]
                actor_headers.append((step, end, ((wrapper["stack"][2]&255)*8, (wrapper["stack"][3]&255)*8, len(text)*8, 8)))
    cursor = 0
    for i, wrapper in enumerate(trace["wrappers"]):
        while cursor < len(timeline) and timeline[cursor][0] <= wrapper["step"]:
            pane = timeline[cursor][1]
            cursor += 1
        if wrapper["format"]["text"] != "%s":
            continue
        source = wrapper["vararg_1_candidate"]["text"]
        row = bindings.get((pane, sha(source.encode())))
        within_list = any(p["step"] <= wrapper["step"] <= p["return_instruction_step"] for p in trace["list_events"])
        if wrapper["format"]["text"] == "%s" and within_list and "\t" in source:
            assert row is not None, (pane, source)
        if row and wrapper["stack"][4] & 255 in row["Foregrounds"]:
            assert wrapper["caller"] in config["RowCallers"], ("unregistered known-row caller", wrapper["caller"], source)
            wrappers[i] = row
    expected = [c for c in trace["calls"] if c["wrapper_index"] in wrappers]
    assert len(accepted) == len(expected) > 0
    for event, original in zip(accepted, expected):
        wrapper = trace["wrappers"][original["wrapper_index"]]
        assert event["Step"] == wrapper["step"] < event["first_glyph"] == original["first_glyph"]
        assert event["detail"]["source_sha256"] == sha(original["vararg_1_candidate"]["text"].encode())
        binding = wrappers[original["wrapper_index"]]
        assert event["Pane"] == binding["Pane"]
        assert event["detail"]["spans"] == binding["Spans"]
        assert event["detail"]["caller"] == wrapper["caller"]
        assert event["detail"]["foreground"] == wrapper["stack"][4] & 255
        assert event["detail"]["within_list"] == any(p["step"] <= wrapper["step"] <= p["return_instruction_step"] for p in trace["list_events"])
        for span in binding["Spans"]:
            wanted = {"X": ((wrapper["stack"][2] & 255) + span["Start"]) * 8,
                      "Y": (wrapper["stack"][3] & 255) * 8, "Width": span["Length"] * 8,
                      "Key": span["Key"], "Group": "body", "Foreground": wrapper["stack"][4] & 255,
                      "Background": config["Background"]}
            assert wanted in event["Words"]
    assert {e["detail"]["source_sha256"] for e in accepted} == {row["SHA256"] for row in wrappers.values()}
    # 由原版下層印字事件核對欄位，不以原型自行宣稱的文字框作為來源。
    fields = [e for e in b["list_events"] if e["Kind"] == "field-before-glyph"]
    calls_by_step = {c["step"]: c for c in trace["calls"]}
    field_by_step = {}
    for e in fields:
        c = calls_by_step[e["Step"]]
        source = c["vararg_1_candidate"] if c["format"]["text"] == "%s" else c["format"]
        matches = [f for f in config["Fields"] if f["RawX"] == c["stack"][3] and f["RawY"] == c["stack"][2]
                   and f["Caller"] == c["caller"] and f["SHA256"] == sha(source["text"].encode())
                   and f["FormatSHA256"] == sha(c["format"]["text"].encode())
                   and (f["Pane"] == e["Pane"] or f["Pane"] in ("suffix", "callsite", "menu"))
                   and (f["Pane"] != "menu" or f["MenuSignature"] == menu_signature(c))
                   and (f["Pane"] != "callsite" or c["wrapper_index"] >= 0
                        and trace["wrappers"][c["wrapper_index"]]["caller"] == f["UpperCaller"])]
        assert len(matches) == 1
        f = matches[0]
        assert e["detail"]["menu_signature"] == f.get("MenuSignature", "")
        assert e["Step"] < e["first_glyph"] == c["first_glyph"]
        assert e["detail"]["source_sha256"] == f["SHA256"]
        assert e["detail"]["deferred"] == (f["Pane"] == "suffix")
        assert source["text"][f["Start"]:f["Start"]+f["Length"]] == en[f["Key"]]
        if f["Pane"] == "callsite":
            wrapper = trace["wrappers"][c["wrapper_index"]]
            assert wrapper["step"] < c["step"] and wrapper["format"]["text"] == source["text"]
            assert (wrapper["stack"][2]&255)*8 == native(c["stack"][3])
            assert (wrapper["stack"][3]&255)*8 == native(c["stack"][2])
        word = {"X": native(c["stack"][3])+f["Start"]*8, "Y": native(c["stack"][2]), "Width": f["Length"]*8,
                "Key": f["Key"], "Group": f["Group"], "Foreground": c["stack"][4] & 15,
                "Background": config["Background"]}
        assert e["detail"]["word"] == word
        field_by_step[e["Step"]] = e
    # 所有已辨識列表內的靜態標題、提示及按鈕均須接入。所有格候選另驗 attach。
    title_wrappers = [w for w in trace["wrappers"] if any(
        w["format"]["segment"] == h["Segment"] and w["format"]["offset"] == h["Offset"]
        and w["stack"][3] & 255 == 1 for h in config["Headers"])]
    full_fills = [f["step"] for f in trace["fill_events"] if not f["within_list"]
                  and f["native_rect"][0] <= 8 and f["native_rect"][1] <= 8
                  and f["native_rect"][0] + f["native_rect"][2] >= 312
                  and f["native_rect"][1] + f["native_rect"][3] >= 184]
    intervals = [(w["step"], next(s for s in full_fills if s > w["step"])) for w in title_wrappers]
    for c in trace["calls"]:
        source = c["vararg_1_candidate"] if c["format"]["text"] == "%s" else c["format"]
        in_list = any(start <= c["step"] < end for start, end in intervals)
        if any(f["Pane"] != "suffix" and f["RawX"] == c["stack"][3] and f["RawY"] == c["stack"][2]
               and f["Caller"] == c["caller"] and f["SHA256"] == sha(source["text"].encode())
               and f["FormatSHA256"] == sha(c["format"]["text"].encode())
               and ((f["Pane"] == "callsite" and c["wrapper_index"] >= 0
                     and trace["wrappers"][c["wrapper_index"]]["caller"] == f["UpperCaller"])
                    or (f["Pane"] == "menu" and f["MenuSignature"] == menu_signature(c))
                    or (f["Pane"] not in ("callsite", "menu") and in_list)) for f in config["Fields"]):
            assert c["step"] in field_by_step
    assert len([e for e in b["list_events"] if e["Kind"] == "title-suffix-attached"]) == len(title_wrappers)

    # 從有原版來源的事件重建每幀詞框位置，避免遺漏捲動頂列仍通過像素合成檢查。
    words, pending_suffix, model, row_positions = {}, None, [], set()
    clear_baselines = []
    wrappers_by_step = {w["step"]: w for w in trace["wrappers"]}
    def intersects(w, rect):
        x, y, width, height = rect
        return w["X"] < x + width and w["X"] + w["Width"] > x and w["Y"] < y + height and w["Y"] + 8 > y
    def erase(rect):
        for pos, w in list(words.items()):
            if intersects(w, rect):
                del words[pos]
                row_positions.discard(pos)
    for e in b["list_events"]:
        kind = e["Kind"]
        if kind in ("pane-invalidate", "clear-write-baseline"):
            targets = sorted((w for w in words.values() if w["Group"] != "footer"), key=lambda w:(w["Y"],w["X"]))
            if kind == "clear-write-baseline":
                assert targets and e["detail"]["targets"] == targets
                assert any(f["step"] <= e["Step"] <= f["return_instruction_step"] and not f["within_list"]
                           and f["native_rect"][0] <= 8 and f["native_rect"][1] <= 8
                           and f["native_rect"][0]+f["native_rect"][2] >= 312 and f["native_rect"][1]+f["native_rect"][3] >= 184 for f in trace["fill_events"])
                clear_baselines.append((e["Step"], targets))
            else:
                assert not targets, ("missing clear baseline", e["Step"])
            words = {pos: w for pos, w in words.items() if w["Group"] == "footer"}
            pending_suffix = None
        elif kind == "footer-render-entry":
            words = {pos: w for pos, w in words.items() if w["Group"] != "footer"}
        elif kind == "native-fill":
            assert any(f["step"] <= e["Step"] <= f["return_instruction_step"]
                       and f["native_rect"] == e["detail"] for f in trace["fill_events"])
            erase(e["detail"])
        elif kind in ("row-before-glyph", "unknown-row-original"):
            w = wrappers_by_step[e["Step"]]
            source = w["vararg_1_candidate"]["text"]
            x, y = (w["stack"][2] & 255)*8, (w["stack"][3] & 255)*8
            erase((x, y, len(source)*8, 8))
            if kind == "row-before-glyph":
                for span in bindings[(e["Pane"], sha(source.encode()))]["Spans"]:
                    word = {"X": x + span["Start"]*8, "Y": y, "Width": span["Length"]*8,
                            "Key": span["Key"], "Group": "body", "Foreground": w["stack"][4]&255,
                            "Background": config["Background"]}
                    words[(word["X"], word["Y"])] = word
                    row_positions.add((word["X"], word["Y"]))
        elif kind == "field-before-glyph":
            w = field_by_step[e["Step"]]["detail"]["word"]
            if e["detail"]["deferred"]:
                pending_suffix = w
            else:
                erase((w["X"], w["Y"], w["Width"], 8))
                words[(w["X"], w["Y"])] = w
        elif kind == "title-suffix-attached":
            assert pending_suffix and pending_suffix["Key"] == e["detail"]["key"]
            words[(pending_suffix["X"], pending_suffix["Y"])] = pending_suffix
            pending_suffix = None
        elif kind == "native-scroll":
            original = next(s for s in trace["scroll_events"] if s["step"] == e["Step"])
            s = [(v - 8000)*2 for v in original["stack"][2:8]]
            x, y, width, height = s[1], s[0], s[3]-s[1], s[2]-s[0]
            dx, dy = -s[5], -s[4]
            assert e["detail"] == {"delta": [dx, dy], "rect": [x, y, width, height]}
            # 原始參數給裁切區；實際來源是裁切區與反向平移區的交集。
            sx, sy = max(x, x-dx), max(y, y-dy)
            sw, sh = min(x+width, x+width-dx)-sx, min(y+height, y+height-dy)-sy
            source, destination = (sx,sy,sw,sh), (sx+dx,sy+dy,sw,sh)
            before = (observed / original["indexed_before"]).read_bytes()
            after = (observed / original["indexed_after"]).read_bytes()
            assert all(before[(sy+row)*320+sx:(sy+row)*320+sx+sw] ==
                       after[(sy+dy+row)*320+sx+dx:(sy+dy+row)*320+sx+dx+sw] for row in range(sh))
            moved, moved_rows = [], set()
            for w in words.values():
                if intersects(w, source):
                    assert sx <= w["X"] and w["X"]+w["Width"] <= sx+sw and sy <= w["Y"] and w["Y"]+8 <= sy+sh
                    moved.append({**w, "X": w["X"]+dx, "Y": w["Y"]+dy})
                    if (w["X"], w["Y"]) in row_positions:
                        moved_rows.add((w["X"]+dx, w["Y"]+dy))
            erase((x,y,width,height))
            for w in moved:
                words[(w["X"], w["Y"])] = w
            row_positions.update(moved_rows)
        row_positions.intersection_update(words)
        expected_words = sorted(words.values(), key=lambda w: (w["Y"], w["X"]))
        assert (e["Words"] or []) == expected_words, (kind, e["Step"])
        model.append((e["Step"], expected_words, sorted(row_positions)))
    # 法術書的退出會返回魔法選單。終點若仍有已辨識選單，應保留該選單的完整中文。
    final_button = next(c for c in reversed(trace["calls"]) if c["caller"] == {"Seg": 0xCEB, "Off": 0x1BE})
    final_signature = menu_signature(final_button)
    final_keys = {f["Key"] for f in config["Fields"] if f["Pane"] == "menu" and f["MenuSignature"] == final_signature}
    for actual in (a, b):
        assert (actual["final_words"] or []) == model[-1][1]
        assert all(w["Group"] == "footer" for w in actual["final_words"] or [])
        assert {w["Key"] for w in actual["final_words"] or []} == final_keys
    cleared = [e for e in b["list_events"] if e["Kind"] == "pane-cleared"]
    assert len(cleared) == len(clear_baselines) > 0
    for event, (start, targets) in zip(cleared, clear_baselines):
        assert start < event["Step"] and event["detail"]["targets"] == targets
    assert all(e["detail"]["pixels"] == sum(w["Width"] * 8 for w in e["detail"]["targets"]) for e in cleared)
    assert all(e["detail"]["target_page"] == e["detail"]["visible_page"] for e in cleared)
    originals = {}
    native_layouts = {s["step"]: s for s in a["list_frames"]}
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
        rectangles = []
        for w in words or []:
            x, y = w["X"] * 2, w["Y"] * 2
            width = w["Width"] * 2
            assert w["Width"] == len(en[w["Key"]]) * 8 and w["Background"] == config["Background"]
            assert 0 <= x < x + width <= 640 and 0 <= y < y + 16 <= 400
            assert len(zh[w["Key"]]) * 16 <= width
            assert all(x + width <= xx or xx + ww <= x or y + 16 <= yy or yy + 16 <= y for xx, yy, ww in rectangles)
            rectangles.append((x, y, width))
            fg, bg = palette[w["Foreground"]], palette[w["Background"]]
            row = bytes([*bg, 255]) * width
            for yy in range(y, y + 16):
                at = (yy * 640 + x) * 4
                px[at:at + width * 4] = row
            for col, ch in enumerate(zh[w["Key"]]):
                for off, value in enumerate(alpha[ch][:256]):
                    if value:
                        yy, xx = divmod(off, 16)
                        at = ((y + yy) * 640 + x + col * 16 + xx) * 4
                        for channel in range(3):
                            px[at + channel] = (fg[channel] * value + px[at + channel] * (255 - value) + 127) // 255
        return sha(px)

    previous, held, translated_frames, model_index = None, 0, 0, -1
    assert len(b["frames"]) == len(b["list_frames"])
    for frame, state in zip(b["frames"], b["list_frames"]):
        assert frame["step"] == state["step"] and frame["step"] in originals
        while model_index + 1 < len(model) and model[model_index + 1][0] <= frame["step"]:
            model_index += 1
        assert (state["words"] or []) == (model[model_index][1] if model_index >= 0 else []), frame["step"]
        original = originals[frame["step"]]
        native_state = native_layouts[frame["step"]]
        for field in ("display_start", "render_page", "palette"):
            assert state[field] == native_state[field]
        if frame["held"]:
            assert previous is not None
            expected_hash = previous
            held += 1
        else:
            # 此契約來自上層列表列；下層靜態標題／提示不共用列表的填色頁生命週期。
            if model_index >= 0 and model[model_index][2]:
                assert state["display_start"] == state["render_page"]
            for start, end, (x, y, width, height) in actor_headers:
                if start <= frame["step"] < end:
                    assert all(w["X"]+w["Width"] <= x or x+width <= w["X"] or w["Y"]+8 <= y or y+height <= w["Y"] for w in state["words"] or [])
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
    seen_steps = {f["step"] for f in b["frames"]}
    start = oracle["request"]["start_steps"]
    end = oracle["request"]["actions"][-1]["end"]
    for lo, hi in config["fine_windows"]:
        if start <= lo < hi <= end:
            assert all(step in seen_steps for step in range(lo + 2000, hi + 1, 2000)), (lo, hi)
    result = {"draft": True, "real_gpu_readback_frames": len(b["frames"]), "held_frames": held,
              "translated_frames": translated_frames, "original_checkpoints_equal": len(b["checkpoints"]),
              "observed_unique_rows": len({e["detail"]["source_sha256"] for e in accepted}),
              "row_events": len(accepted), "clear_transactions": len(cleared),
              "single_row_events": sum(not e["detail"]["within_list"] for e in accepted),
              "list_context_events": len(contexts),
              "list_page_rebases": len(pages),
              "preserved_actor_headers": len(actor_headers),
              "field_events": len(fields), "field_keys": sorted({e["detail"]["key"] for e in fields}),
              "callsite_field_events": sum(1 for e in fields if any(f["Pane"] == "callsite" and f["Key"] == e["detail"]["key"] for f in config["Fields"])),
              "menu_field_events": sum(bool(e["detail"]["menu_signature"]) for e in fields),
              "menu_kinds": sorted({config["Menus"][e["detail"]["menu_signature"]] for e in fields if e["detail"]["menu_signature"]}),
              "final_menu_kind": config["Menus"].get(final_signature, "original"),
              "final_footer_words": len(b["final_words"] or []),
              "native_button_calls": sum(c["caller"] == {"Seg": 0xCEB, "Off": 0x1BE} for c in trace["calls"]),
              "known_menu_shapes": sorted({menu["Signature"] for menu in trace["menus"] if menu["Signature"] in config["Menus"]}),
              "field_lifetime_model_equal": True,
              "fine_windows_verified": True,
              "all_submitted_pixels_equal_expected": True,
              "en_receipt_sha256": sha((en_run / "receipt.json").read_bytes()),
              "zh_receipt_sha256": sha((zh_run / "receipt.json").read_bytes()),
              "checker_sha256": sha(Path(__file__).read_bytes()),
              "limits": "固定正常旅店快照與一般按鍵；已觀測列表、角色欄位及已知整表選單。數字與加值維持原版。不是全部介面、冷啟動、X11、裝備操作、施法、存讀檔、正式字級或正式中文化驗收。"}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("real_gpu_readback_frames", "held_frames", "original_checkpoints_equal", "clear_transactions")}, ensure_ascii=False))


if __name__ == "__main__":
    check(*map(Path, sys.argv[1:7]))
