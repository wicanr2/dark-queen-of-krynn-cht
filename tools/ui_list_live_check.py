"""核對列表原型的自動選譯、原版狀態及實際 GPU 提交畫格。"""
import base64
import hashlib
import json
import re
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
    # 未進列表的正常路徑，Go 的空 slice 會輸出 null。
    for field in ("list_events", "scroll_events"):
        if trace[field] is None:
            trace[field] = []
        assert isinstance(trace[field], list)
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
    typed_buttons = bool(b.get("button_ownership"))
    assert bool(a.get("button_ownership")) == typed_buttons
    if config.get("Paragraphs"):
        assert typed_buttons
    native_paragraphs = trace.get("paragraphs") or []
    paragraph_by_step = {p["step"]:p for p in native_paragraphs}
    def paragraph_bindings(p):
        source = p["source"]["text"]
        return [f for f in config.get("Paragraphs",[]) if f["SHA256"] == sha(source.encode()) and en[f["Key"]] == source
                and f["Caller"] == p["caller"] and f["NativeBox"] == p["native_box"]
                and [f[k] for k in ("Foreground","Background","Clear")] == [p[k] for k in ("foreground","background","clear")]]
    paragraph_entries = [e for e in b["list_events"] if e["Kind"] == "paragraph-before-glyph"]
    paragraph_fallbacks = [e for e in b["list_events"] if e["Kind"] == "unknown-paragraph-original"]
    if config.get("Paragraphs"):
        assert {e["Step"] for e in paragraph_entries+paragraph_fallbacks} == set(paragraph_by_step)
        assert len(paragraph_entries)+len(paragraph_fallbacks) == len(native_paragraphs)
    else:
        assert not paragraph_entries and not paragraph_fallbacks
    for e in paragraph_entries:
        p = paragraph_by_step[e["Step"]]
        assert len(paragraph_bindings(p)) == 1
        assert p["source"]["nul_terminated"] and bytes.fromhex(p["source"]["hex"]).decode("ascii") == p["source"]["text"]
        assert (p["source"]["segment"],p["source"]["offset"]) == (p["stack"][10],p["stack"][9])
        assert e["Step"] < e["first_glyph"] == p["first_glyph"] < p["return_step"]
        assert e["detail"]["caller"] == p["caller"]
        assert e["detail"]["source_pointer"] == {"Seg":p["source"]["segment"],"Off":p["source"]["offset"]}
    paragraph_returns = [e for e in b["list_events"] if e["Kind"] == "paragraph-return"]
    assert len(paragraph_returns) == len(paragraph_entries)
    for entry, returned in zip(paragraph_entries,paragraph_returns):
        p = paragraph_by_step[entry["Step"]]
        assert returned["Step"] == p["return_step"]
        assert returned["detail"] == {"caller":p["caller"],"ss":p["regs"]["SS"],"sp":(p["regs"]["SP"]+4)&65535}
    def field_start(field, text):
        if not field.get("SourcePattern"):
            return field["Start"] if sha(text.encode()) == field["SHA256"] else None
        assert field["SourcePattern"] == "clock-period"
        assert field["Pane"] == "callsite" and field["Group"] == "body"
        assert field["UpperCaller"] == {"Seg": 0x205E, "Off": 0x53C}
        assert (field["RawX"], field["RawY"], field["Start"], field["Length"]) == (8104, 8060, 0, 2)
        if re.fullmatch(r"[0-9]{1,2}:[0-9]{2} (AM|PM)", text) and text[-2:] == en[field["Key"]] and sha(text[-2:].encode()) == field["SHA256"]:
            return len(text)-2
        return None
    # 從原版整表 bytes 獨立重建按鈕順序、文字指標、座標及指紋。
    native = lambda value: value if value < 400 else (value - 8000) * 2
    refresh_sources = {e["step"]: e for e in trace.get("menu_refresh_sources") or []}
    for menu in [*trace["menus"], *(e["menu_snapshot"] for e in trace["list_events"] if "menu_snapshot" in e),
                 *(e["menu_snapshot"] for e in refresh_sources.values() if e["valid"])]:
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
    assert len(accepted) == len(expected)
    assert accepted or paragraph_entries, "沒有列表列或完整段落接入"
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
    field_by_id = {}
    verified_field_widths = set()
    verified_field_backgrounds = set()
    for e in fields:
        c = calls_by_step[e["Step"]]
        source = c["vararg_1_candidate"] if c["format"]["text"] == "%s" else c["format"]
        matches = [f for f in config["Fields"] if f["Key"] == e["detail"]["key"] and f["RawX"] == c["stack"][3] and f["RawY"] == c["stack"][2]
                   and f["Caller"] == c["caller"] and field_start(f, source["text"]) is not None
                   and ("Color" not in f or f["Color"] == (c["stack"][4]&255))
                   and f["FormatSHA256"] == sha(c["format"]["text"].encode())
                   and (f["Pane"] == e["Pane"] or f["Pane"] in ("suffix", "callsite", "menu"))
                   and (f["Pane"] != "menu" or f["MenuSignature"] == menu_signature(c))
                   and (f["Pane"] != "callsite" or c["wrapper_index"] >= 0
                        and trace["wrappers"][c["wrapper_index"]]["caller"] == f["UpperCaller"])]
        assert len(matches) == 1
        f = matches[0]
        assert e["detail"]["menu_signature"] == f.get("MenuSignature", "")
        assert e["Step"] < e["first_glyph"] == c["first_glyph"]
        start = field_start(f, source["text"])
        assert e["detail"]["source_sha256"] == sha(source["text"].encode())
        assert e["detail"].get("source_start", None if f.get("SourcePattern") else f["Start"]) == start
        assert e["detail"]["deferred"] == (f["Pane"] == "suffix")
        assert source["text"][start:start+f["Length"]] == en[f["Key"]]
        if f["Pane"] == "callsite":
            wrapper = trace["wrappers"][c["wrapper_index"]]
            assert wrapper["step"] < c["step"] and wrapper["format"]["text"] == source["text"]
            expected_upper = f.get("UpperNative",[native(c["stack"][3]),native(c["stack"][2])])
            assert [(wrapper["stack"][n]&255)*8 for n in (2,3)] == expected_upper
        background = f.get("BackgroundOverride",config["Background"])
        if "BackgroundOverride" in f:
            assert f["UpperCaller"] == {"Seg":0xCEB,"Off":0x4BD} and f["UpperNative"] == [56,192]
            assert c["stack"][2:5] == [189,8032,0x70] and f["Color"] == 0x70 and background == 7
            assert source["text"] == "Press        to continue." and (start,f["Length"]) in ((0,5),(13,12))
            checkpoint=next(cp for cp in trace["checkpoints"] if cp["step"]>=c["return_step"])
            original=Image.open(observed/(checkpoint["label"]+".png")).convert("RGB")
            foreground=tuple(checkpoint["palette"][0]);bg=tuple(checkpoint["palette"][7])
            left=64+start*8
            assert set(original.crop((left,189,left+f["Length"]*8,197)).getdata())=={foreground,bg}
            verified_field_backgrounds.add((f["Key"],background))
        width = f.get("Width", f["Length"]*8)
        if "Width" in f:
            # 唯一已量測擴框是 AC／HP 的欄間及面板留白，不准任意擴框。
            assert f["UpperCaller"] == {"Seg": 0x205E, "Off": 0x2B9}
            assert source["text"] == "AC\tHP" and (f["Start"], f["Length"], width) in ((0, 2, 24), (3, 2, 24))
            assert (native(c["stack"][3]), native(c["stack"][2])) == (264, 16)
            checkpoint = next(cp for cp in trace["checkpoints"] if cp["step"] >= c["return_step"])
            original = Image.open(observed / (checkpoint["label"] + ".png")).convert("RGB")
            foreground = tuple(checkpoint["palette"][c["stack"][4] & 15])
            assert original.size == (320, 200)
            background_rgb = tuple(checkpoint["palette"][config["Background"]])
            assert set(original.crop((264, 16, 312, 24)).getdata()) == {foreground, background_rgb}
            ink = {x for x in range(264, 312) if any(original.getpixel((x, y)) == foreground for y in range(16, 24))}
            assert ink and ink <= set(range(264, 280)) | set(range(288, 304))
            assert ink & set(range(264, 280)) and ink & set(range(288, 304))
        word = {"X": native(c["stack"][3])+start*8, "Y": native(c["stack"][2]), "Width": width,
                "Key": f["Key"], "Group": f["Group"], "Foreground": c["stack"][4] & 15,
                "Background": background}
        if typed_buttons and f["Pane"] == "menu":
            word["Button"] = True
        assert e["detail"]["word"] == word
        verified_field_widths.add((f["Key"], width))
        identity = e["Step"], f["Key"]
        assert identity not in field_by_id
        field_by_id[identity] = e
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
        expected_keys = {f["Key"] for f in config["Fields"] if f["Pane"] != "suffix" and f["RawX"] == c["stack"][3] and f["RawY"] == c["stack"][2]
               and f["Caller"] == c["caller"] and field_start(f, source["text"]) is not None
               and ("Color" not in f or f["Color"] == (c["stack"][4]&255))
               and f["FormatSHA256"] == sha(c["format"]["text"].encode())
               and ((f["Pane"] == "callsite" and c["wrapper_index"] >= 0
                     and trace["wrappers"][c["wrapper_index"]]["caller"] == f["UpperCaller"])
                    or (f["Pane"] == "menu" and f["MenuSignature"] == menu_signature(c))
                    or (f["Pane"] not in ("callsite", "menu") and in_list))}
        actual_keys = {key for (step, key), event in field_by_id.items() if step == c["step"] and not event["detail"]["deferred"]}
        assert actual_keys == expected_keys, (c["step"], expected_keys, actual_keys)
    assert len([e for e in b["list_events"] if e["Kind"] == "title-suffix-attached"]) == len(title_wrappers)
    clock_keys = {f["Key"] for f in config["Fields"] if f.get("SourcePattern") == "clock-period"}
    clock_wrappers = [w for w in trace["wrappers"] if clock_keys and w["caller"] == {"Seg": 0x205E, "Off": 0x53C}
                      and ((w["stack"][2]&255)*8, (w["stack"][3]&255)*8) == (208, 120)]
    resets = [e for e in b["list_events"] if e["Kind"] == "clock-source-reset"]
    returns = [e for e in b["list_events"] if e["Kind"] == "clock-render-return"]
    assert len(resets) == len(returns) == len(clock_wrappers)
    clock_intervals = []
    for wrapper, reset, returned in zip(clock_wrappers, resets, returns):
        assert reset["Step"] == wrapper["step"]
        assert reset["detail"] == {"caller": wrapper["caller"], "native_xy": [208, 120]}
        assert returned["detail"] == {"caller": wrapper["caller"], "ss": wrapper["regs"]["SS"], "sp": (wrapper["regs"]["SP"]+4)&65535}
        lower = [c for c in trace["calls"] if c["wrapper_index"] >= 0 and trace["wrappers"][c["wrapper_index"]]["step"] == wrapper["step"]]
        assert len(lower) == 1 and lower[0]["return_step"] < returned["Step"]
        assert returned["Step"] < next((w["step"] for w in clock_wrappers if w["step"] > wrapper["step"]), oracle["request"]["actions"][-1]["end"])
        clock_intervals.append((reset["Step"], returned["Step"]))

    # 從有原版來源的事件重建每幀詞框位置，避免遺漏捲動頂列仍通過像素合成檢查。
    words, pending_suffix, model, row_positions = {}, None, [], set()
    page, page_history = None, []
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
        if kind == "paragraph-before-glyph":
            p = paragraph_by_step[e["Step"]]
            binding = paragraph_bindings(p)[0]
            components = [binding["Key"]]
            box = [v*2 for v in p["native_box"]]
            bg = p["background"] or 8
            if not p["clear"]:
                assert page is not None and page["Box"] == box and page["Foreground"] == p["foreground"] and page["Background"] == bg
                components = page["Components"]+components
            text = "".join(zh[key] for key in components)
            # 由正式全文、框與禁則獨立驗每個分界，不呼叫 runtime 的斷行實作。
            lines = e["detail"]["page"]["Lines"]
            cells = (box[2]-box[0])//glyphs["size"]
            assert lines and all(lines) and "".join(lines) == text
            assert len(lines)*glyphs["height"] <= box[3]-box[1]
            assert all(len(line) <= cells for line in lines)
            offset = 0
            for line in lines[:-1]:
                offset += len(line)
                legal = lambda end: text[end] not in "，。！？、；：」』）》】" and text[end-1] not in "「『（《【"
                assert legal(offset)
                assert not any(legal(end) for end in range(offset+1,min(offset-len(line)+cells,len(text)-1)+1))
            expected_page = {"step":p["step"],"Key":binding["Key"],"Source":p["source"]["text"],"Text":text,"Box":box,
                             "Foreground":p["foreground"],"Background":bg,"Lines":lines,"Clear":p["clear"],"Components":components}
            assert e["detail"]["page"] == expected_page
            page = expected_page
            page_history.append(page)
            x,y,right,bottom = p["native_box"]
            erase((x,y,right-x,bottom-y))
        elif kind == "unknown-paragraph-original":
            p = paragraph_by_step[e["Step"]]
            assert e["detail"]["caller"] == p["caller"]
            bindings_here = paragraph_bindings(p)
            if bindings_here:
                assert not p["clear"] and page is None
                assert e["detail"]["reason"] == "missing compatible predecessor"
            else:
                assert e["detail"]["reason"] == "source or context mismatch"
            page = None
        elif kind == "paragraph-invalidated":
            assert page is not None
            rect = e["detail"]["native_rect"]
            x,y,width,height = rect
            left,top,right,bottom = [v//2 for v in page["Box"]]
            assert x<right and x+width>left and y<bottom and y+height>top
            assert not any(p["step"]<=e["Step"]<=p["return_step"] for p in native_paragraphs)
            if e["detail"]["reason"] == "native fill":
                assert any(f["step"]<=e["Step"]<=f["return_instruction_step"] and f["native_rect"]==rect for f in trace["fill_events"])
            else:
                assert e["detail"]["reason"] == "field overwrite"
                assert any(step==e["Step"] and [event["detail"]["word"][k] for k in ("X","Y","Width")]+[8]==rect for (step,key),event in field_by_id.items())
            page = None
        elif kind in ("pane-invalidate", "clear-write-baseline"):
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
        elif kind == "clock-source-reset":
            words = {pos: w for pos, w in words.items() if w["Key"] not in clock_keys}
        elif kind == "footer-render-entry":
            preserved = False
            if e.get("detail") is not None:
                native_refresh = refresh_sources[e["Step"]]
                signature = native_refresh["menu_snapshot"]["Signature"] if native_refresh["valid"] else ""
                expected = {(f["RawX"]+f["Start"]*8, f["RawY"], f.get("Width", f["Length"]*8), f["Key"])
                            for f in config["Fields"] if f["Pane"] == "menu" and f["MenuSignature"] == signature}
                before = {(w["X"], w["Y"], w["Width"], w["Key"]) for w in words.values() if w["Group"] == "footer" and (not typed_buttons or w.get("Button"))}
                preserved = bool(expected) and signature in config["Menus"] and before == expected
                assert e["detail"] == {"menu_signature": signature, "preserved": preserved}
            if not preserved:
                words = {pos: w for pos, w in words.items() if w["Group"] != "footer" or (typed_buttons and not w.get("Button"))}
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
            w = field_by_id[e["Step"], e["detail"]["key"]]["detail"]["word"]
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
        model.append((e["Step"], expected_words, sorted(row_positions), page))
    for actual in (a,b):
        assert (actual.get("paragraphs") or []) == page_history
        assert actual.get("final_paragraph") == (model[-1][3] if model else None)
    # 法術書的退出會返回魔法選單。終點若仍有已辨識選單，應保留該選單的完整中文。
    final_button = next(c for c in reversed(trace["calls"]) if c["caller"] == {"Seg": 0xCEB, "Off": 0x1BE})
    final_signature = menu_signature(final_button)
    final_keys = {f["Key"] for f in config["Fields"] if f["Pane"] == "menu" and f["MenuSignature"] == final_signature}
    for actual in (a, b):
        assert (actual["final_words"] or []) == model[-1][1]
        assert {w["Key"] for w in actual["final_words"] or [] if w["Group"] == "footer" and (not typed_buttons or w.get("Button"))} == final_keys
        # 每個動作終點都應保留完整已知按鈕；同區提示另外由生命週期模型驗證。
        layouts = {frame["step"]: frame for frame in actual["list_frames"]}
        menu_field_keys = {f["Key"] for f in config["Fields"] if f["Pane"] == "menu"}
        for checkpoint in actual["checkpoints"]:
            button = next(c for c in reversed(trace["calls"]) if c["step"] < checkpoint["step"] and c["caller"] == {"Seg": 0xCEB, "Off": 0x1BE})
            signature = menu_signature(button)
            if signature not in config["Menus"]:
                continue
            expected_keys = {f["Key"] for f in config["Fields"] if f["Pane"] == "menu" and f["MenuSignature"] == signature}
            actual_keys = {w["Key"] for w in layouts[checkpoint["step"]]["words"] or [] if w["Group"] == "footer" and (w.get("Button") if typed_buttons else w["Key"] in menu_field_keys)}
            assert actual_keys == expected_keys, ("checkpoint footer incomplete", checkpoint["label"], expected_keys-actual_keys, actual_keys-expected_keys)
        # 原版仍保留的提示必須留在穩定畫面，不能因模型也把它清掉而通過。
        for checkpoint in actual["checkpoints"]:
            for f in config["Fields"]:
                if "UpperNative" not in f:
                    continue
                candidates=[event for (step,key),event in field_by_id.items() if step<checkpoint["step"] and key==f["Key"]]
                if not candidates:
                    continue
                event=candidates[-1]; word=event["detail"]["word"]
                x,y,width,height=word["X"],word["Y"],word["Width"],8
                start=calls_by_step[event["Step"]]["return_step"]
                changed=any(start<fill["step"]<checkpoint["step"] and intersects(word,fill["native_rect"]) for fill in trace["fill_events"])
                for call in trace["calls"]:
                    if not start<call["step"]<checkpoint["step"]:
                        continue
                    text=call["vararg_1_candidate"]["text"] if call["format"]["text"]=="%s" else call["format"]["text"]
                    changed=changed or intersects(word,(native(call["stack"][3]),native(call["stack"][2]),max(1,len(text))*8,8))
                if not changed:
                    assert word in (layouts[checkpoint["step"]]["words"] or []), ("missing retained prompt",checkpoint["label"],f["Key"])
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

    def compose(source, words, palette, page):
        px = bytearray(source)
        rectangles = []
        if page is not None:
            x,y,right,bottom = page["Box"]
            assert [x,y,right,bottom] == [16,272,624,368]
            width,height = right-x,bottom-y
            rectangles.append((x,y,width,height))
            fg,bg = palette[page["Foreground"]],palette[page["Background"]]
            row = bytes([*bg,255])*width
            for yy in range(y,bottom):
                at=(yy*640+x)*4;px[at:at+width*4]=row
            assert len(page["Lines"])*glyphs["height"] <= height
            for line,text in enumerate(page["Lines"]):
                assert len(text)*glyphs["size"] <= width
                for col,ch in enumerate(text):
                    for off,value in enumerate(alpha[ch]):
                        if value:
                            yy,xx=divmod(off,glyphs["size"])
                            at=((y+line*glyphs["height"]+yy)*640+x+col*glyphs["size"]+xx)*4
                            for channel in range(3):px[at+channel]=(fg[channel]*value+px[at+channel]*(255-value)+127)//255
        for w in words or []:
            x, y = w["X"] * 2, w["Y"] * 2
            width = w["Width"] * 2
            assert (w["Width"] == len(en[w["Key"]])*8 or (w["Key"], w["Width"]) in verified_field_widths)
            assert w["Background"] == config["Background"] or (w["Key"],w["Background"]) in verified_field_backgrounds
            assert 0 <= x < x + width <= 640 and 0 <= y < y + 16 <= 400
            assert len(zh[w["Key"]]) * 16 <= width
            assert all(x + width <= xx or xx + ww <= x or y + 16 <= yy or yy + hh <= y for xx, yy, ww, hh in rectangles)
            rectangles.append((x, y, width, 16))
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
        expected_page = model[model_index][3] if model_index >= 0 else None
        assert state.get("paragraph") == expected_page, ("paragraph frame lifetime",frame["step"])
        original = originals[frame["step"]]
        if any(start <= frame["step"] < end for start, end in clock_intervals):
            assert frame["held"], ("clock transaction exposed", frame["step"])
        native_state = native_layouts[frame["step"]]
        assert native_state.get("paragraph") == state.get("paragraph")
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
            key = (original["SHA256"], json.dumps(state["words"], sort_keys=True), json.dumps(state["palette"]),json.dumps(state.get("paragraph"),sort_keys=True))
            if key not in cache:
                cache[key] = compose(pixels(en_run, original), state["words"], state["palette"],state.get("paragraph"))
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
              "clock_transactions": len(clock_intervals),
              "typed_button_ownership":typed_buttons,
              "paragraph_events":len(paragraph_entries),"paragraph_original_fallbacks":len(paragraph_fallbacks),
              "paragraph_joins":sum(not p["Clear"] for p in page_history),
              "paragraph_invalidations":sum(e["Kind"]=="paragraph-invalidated" for e in b["list_events"]),
              "compatible_footer_refreshes": sum(e["Kind"] == "footer-render-entry" and bool((e.get("detail") or {}).get("preserved")) for e in b["list_events"]),
              "fine_window_count": len(config["fine_windows"]),
              "callsite_field_events": sum(1 for e in fields if any(f["Pane"] == "callsite" and f["Key"] == e["detail"]["key"] for f in config["Fields"])),
              "menu_field_events": sum(bool(e["detail"]["menu_signature"]) for e in fields),
              "menu_kinds": sorted({config["Menus"][e["detail"]["menu_signature"]] for e in fields if e["detail"]["menu_signature"]}),
              "final_menu_kind": config["Menus"].get(final_signature, "original"),
              "final_footer_words": sum(w["Group"] == "footer" for w in b["final_words"] or []),
              "final_body_words": sum(w["Group"] != "footer" for w in b["final_words"] or []),
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
