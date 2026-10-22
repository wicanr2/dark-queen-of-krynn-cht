"""由已驗原版標題、正式 TSV 及前作術語建立私有列表原型輸入。"""
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from PIL import Image


def sha(data):
    return hashlib.sha256(data).hexdigest()


def catalog(path):
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))
    result = {r["key"]: r["text"] for r in rows}
    assert len(result) == len(rows)
    return result


def prepare(texts, observed, output, paragraph_trace=None):
    assert not output.exists()
    en = catalog(texts / "en.tsv")
    with (texts / "glossary.tsv").open(encoding="utf-8", newline="") as f:
        terms = list(csv.DictReader(f, delimiter="\t"))
    aliases, translations, headers, provenance = {}, {}, [], []
    zh = catalog(texts / "zh-TW.tsv")
    def glossary(source, categories):
        found = [t for t in terms if t["en"].casefold() == source.casefold()
                 and t["category"] in categories]
        assert len(found) == 1, source
        return found[0]

    def formal(source):
        found = [(k, zh[k]) for k, value in en.items() if value == source and k in zh]
        assert found and len({v for _, v in found}) == 1, source
        return found[0]

    bindings = []
    rows = []
    # 明列已觀測變體的詞根與順序；不作任意字串替換或推導未知物品。
    variants = {"Javelins": ("Javelin",), "Arrows": ("Arrow",),
                "Cleric Scroll": ("Clerical Scroll",),
                "Fine Long Bow": ("Fine", "Long Bow"),
                "Cloak Of Prot": ("Of Prot", "Cloak"),
                "Ring Of Prot": ("Ring of Protection",),
                "Footman's Dragonlance": ("Footman's", "Dragonlance"),
                "Potion of Giant Strength": ("Giant Strength", "Potion")}
    def bind(pane, source, categories):
        key = pane + "." + sha(source.encode())[:20]
        if key in translations:
            return key
        roots = variants.get(source, (source,)) if pane == "inventory" else (source,)
        origins, values = [], []
        for root in roots:
            found = [t for t in terms if t["en"].casefold() == root.casefold()
                     and t["category"] in categories]
            if found:
                term = glossary(root, categories)
                values.append(term["zh"])
                origins.append({"glossary": term})
            else:
                k, value = formal(root)
                values.append(value)
                origins.append({"formal_key": k})
        aliases[key], translations[key] = source, "".join(values)
        assert len(translations[key]) * 16 <= len(source) * 16, source
        bindings.append({"key": key, "source": source, "roots": origins,
                         "method": "existing term" if roots == (source,) else "observed variant with explicit existing roots"})
        return key
    for pane, folder, offset, category in (("inventory", "observe-items-r2", 0x4689, "ui"),
                                           ("grimoire", "observe-grimoire-r2", 0xA7C4, "spell")):
        receipt = json.loads((observed / folder / "receipt.json").read_text())
        assert not receipt["pending_fills"] and not receipt["pending_lists"]
        matches = [w for w in receipt["wrappers"] if w["format"]["offset"] == offset
                   and (w["stack"][3] & 255) == 1 and w["format"]["nul_terminated"]]
        assert matches
        f = matches[0]["format"]
        assert all(w["format"] == f for w in matches)
        source_keys = [key for key, value in en.items() if value == f["text"]]
        assert len(source_keys) <= 1
        key = "header." + pane
        aliases[key] = en[source_keys[0]] if source_keys else f["text"]
        headers.append({"Pane": pane, "Key": key, "Segment": f["segment"],
                        "Offset": offset, "SHA256": sha(aliases[key].encode())})
        provenance.append({"pane": pane, "header_catalog_key": source_keys[0] if source_keys else None,
                           "header_source": "formal-en" if source_keys else "observed original RAM NUL format; not registered in main catalog",
                           "header_occurrences": len(matches),
                           "receipt_sha256": sha((observed / folder / "receipt.json").read_bytes())})
        # 只採原版列表交易內、完整 NUL 結尾的實際 %s 列。標題和角色名稱不參與。
        observed_rows = sorted({w["vararg_1_candidate"]["text"] for w in receipt["wrappers"]
                                if w["format"]["text"] == "%s" and w["vararg_1_candidate"]["nul_terminated"]
                                and "\t" in w["vararg_1_candidate"]["text"]
                                and any(p["step"] <= w["step"] <= p["return_instruction_step"]
                                        for p in receipt["list_events"])})
        for text in observed_rows:
            spans = []
            def span(start, source, categories):
                assert text[start:start + len(source)] == source
                spans.append({"Start": start, "Length": len(source), "Key": bind(pane, source, categories)})
            if pane == "grimoire":
                assert text.startswith("\t") and text.count("\t") == 1, repr(text)
                span(1, text[1:], {"spell"})
            else:
                match = re.fullmatch(r" (Yes|No)\t( ?(?:[0-9]+ )?)(.+?)( \+[0-9]+)? ", text)
                assert match, repr(text)
                span(1, match[1], {"ui"})
                start, name = match.start(3), match[3]
                if name.startswith("Bracers AC "):
                    assert re.fullmatch(r"Bracers AC [0-9]+", name)
                    span(start, name.split(" AC ")[0], {"item"})
                elif name.endswith(" Spells"):
                    scroll = re.fullmatch(r"(.+ Scroll) ([0-9]+) (Spells)", name)
                    assert scroll
                    span(start, scroll[1], {"item"})
                    span(start + scroll.start(3), scroll[3], {"ui"})
                else:
                    span(start, name, {"item", "ui"} if name == "Shield" else {"item"})
            rows.append({"Pane": pane, "SHA256": sha(text.encode()), "Spans": spans,
                         "Foregrounds": [7, 11]})
    # 這些是 source key 的辨識值。runtime 只讀 TSV，不內嵌顯示字串。
    for key, value in (("answer.yes", "Yes"), ("answer.no", "No")):
        assert value in en.values()
        aliases[key] = value
    # 格式語法不是玩家文案，由真實列印字的原始格式取得，不能當成漏譯項目。
    row_formats = {w["format"]["text"] for w in receipt["wrappers"]
                   if w["format"]["hex"] == "2573" and w["format"]["nul_terminated"]}
    assert len(row_formats) == 1
    aliases["format.string"] = row_formats.pop()
    backgrounds = None
    native_backgrounds = set()
    for pane, comparison, folder in (("inventory", "items-comparison.json", "observe-items-r2"),
                                      ("grimoire", "grimoire-comparison.json", "observe-grimoire-r2")):
        checked = json.loads((observed / comparison).read_text())
        receipt = json.loads((observed / folder / "receipt.json").read_text())
        assert checked["observed_receipt_sha256"] == sha((observed / folder / "receipt.json").read_bytes())
        for m in checked["shield_occurrences"]:
            p = next(p for p in receipt["checkpoints"] if p["step"] >= m["return_step"])
            im = Image.open(observed / folder / (p["label"] + ".png")).convert("RGB")
            x, y, w, h = m["word_after_list_native_rect"]
            colors = set(im.crop((x, y, x + w, y + h)).getdata())
            fg = tuple(p["palette"][m["foreground"]])
            assert fg in colors and len(colors) == 2
            bg = next(iter(colors - {fg}))
            indices = [i for i, rgb in enumerate(p["palette"]) if tuple(rgb) == bg]
            assert indices
            backgrounds = set(indices) if backgrounds is None else backgrounds.intersection(indices)
            for moved in m["word_scrolls"]:
                scroll = receipt["scroll_events"][moved["scroll_index"]]
                raw = (observed / folder / scroll["indexed_before"]).read_bytes()
                xx, yy, ww, hh = m["word_native_rect"]
                native = set(b for y0 in range(yy, yy + hh) for b in raw[y0 * 320 + xx:y0 * 320 + xx + ww])
                assert m["foreground"] in native and len(native) == 2
                native_backgrounds.update(native - {m["foreground"]})
    # DAC 可有多個索引對應同 RGB；用原版捲動前色號證據選索引，不能從 RGB 隨便反查。
    backgrounds.intersection_update(native_backgrounds)
    assert len(backgrounds) == 1
    # 標題、底列及提示仍由原版印字取得；不翻譯玩家姓名或解析任意格式。
    with (texts / "ui-list-chrome-reviewed.tsv").open(encoding="utf-8", newline="") as stream:
        reviewed = list(csv.DictReader(stream, delimiter="\t", quoting=csv.QUOTE_NONE))
    assert len(reviewed) == 2 and len({r["en"] for r in reviewed}) == 2
    reviewed_by_en = {r["en"]: r for r in reviewed}
    menu_terms = {}
    for source in ("Rdy Use Trade Deposit Drop Halve Join Sell Id Exit",
                   "Cast Memorize Scribe Display Rest Exit",
                   "Items Spells Trade Deposit Drop Lay Cure Exit",
                   "Rest Days Hours Mins Add Subtract Exit"):
        k, target = formal(source)
        source_parts, target_parts = source.split(), target.replace("\\u3000", " ").split()
        assert len(source_parts) == len(target_parts)
        for english, translated in zip(source_parts, target_parts):
            if english in menu_terms:
                assert menu_terms[english][0] == translated
            menu_terms[english] = (translated, k)
    # 營地短標籤已有正式來源與先前字框量測，直接沿用既有詞條。
    for source in ("View", "Magic", "Alt", "Fix", "Load", "Save", "Palace", "Temple", "Hall", "Shop", "Inn", "Bar", "Leave"):
        k, value = formal(source)
        menu_terms[source] = (value, k)
    fields, field_ids, field_provenance = [], set(), []
    prompt_terms = {}
    if paragraph_trace is not None:
        key, target = formal("Press        to continue.")
        left, right = target.split("        ")
        assert left and right
        prompt_terms = {"Press":(left,key), "to continue.":(right,key)}
    def field_key(source, categories=None, width=None):
        if categories == {"item"}:
            return bind("inventory", source, categories)
        key = "field." + sha(source.encode())[:20]
        if key in translations:
            return key
        if source in reviewed_by_en:
            origin = {"reviewed": reviewed_by_en[source]}
            translated = reviewed_by_en[source]["text"]
        elif source in menu_terms:
            translated, k = menu_terms[source]
            origin = {"formal_menu_key": k, "component": source}
        elif source in prompt_terms:
            translated, k = prompt_terms[source]
            origin = {"formal_component_key":k,"component":source}
        elif categories and any(t["en"].casefold() == source.casefold() and t["category"] in categories for t in terms):
            term = glossary(source, categories)
            translated, origin = term["zh"], {"glossary": term}
        elif categories == {"class"} and "/" in source:
            parts, origins = [], []
            for part in source.split("/"):
                if part.endswith(" Cleric"):
                    deity, cleric = glossary(part[:-7], {"deity"}), glossary("Cleric", {"class"})
                    parts.append(deity["zh"] + cleric["zh"])
                    origins.extend([{"glossary": deity}, {"glossary": cleric}])
                else:
                    matches = [t for t in terms if t["en"].casefold() == part.casefold() and t["category"] == "class"]
                    if matches:
                        term = glossary(part, {"class"})
                        parts.append(term["zh"])
                        origins.append({"glossary": term})
                    else:
                        k, value = formal(part)
                        parts.append(value)
                        origins.append({"formal_key": k})
            translated, origin = "/".join(parts), {"observed_class_components": origins}
        elif source == "years":
            k, value = formal("%d years")
            assert value.startswith("%d ")
            translated, origin = value[3:], {"formal_key": k, "suffix_only": True}
        else:
            found = [(k, zh[k]) for k, value in en.items() if value.strip() == source and k in zh]
            assert found and len({v for _, v in found}) == 1, source
            k, translated = found[0]
            origin = {"formal_key": k}
        assert translated and len(translated)*8 <= (len(source)*8 if width is None else width), source
        aliases[key], translations[key] = source, translated
        field_provenance.append({"key": key, "source": source, "origin": origin})
        return key
    menu_kinds = {
        ("Items", "Spells", "Trade", "Drop", "Exit"): "status",
        ("Rdy", "Use", "Trade", "Drop", "Halve", "Join", "Exit"): "inventory",
        ("Cast", "Memorize", "Scribe", "Display", "Rest", "Exit"): "magic",
        ("Memorize", "Exit"): "grimoire", ("Exit",): "effects",
        ("View", "Magic", "Rest", "Alt", "Fix", "Load", "Save", "Exit"): "camp",
        ("Rest", "Days", "Hours", "Mins", "Add", "Subtract", "Exit"): "rest",
        ("Palace", "Temple", "Hall", "Shop", "Inn", "Bar", "Leave"): "city"}
    menus, menu_provenance = {}, []
    for pane, folder in (("inventory", "observe-menus-items-r1"), ("grimoire", "observe-menus-grimoire-r1"),
                         ("effects", "observe-effects-r1"), ("camp", "observe-camp-roundtrip-r1"),
                         ("camp", "observe-clock-city-r1")):
        receipt = json.loads((observed / folder / "receipt.json").read_text())
        known_menus = {}
        for index, menu in enumerate(receipt["menus"]):
            sources = tuple(bytes.fromhex(b["SourceHex"]).decode("ascii") for b in menu["Buttons"])
            if sources in menu_kinds:
                known_menus[index] = menu["Signature"]
                menus[menu["Signature"]] = menu_kinds[sources]
                menu_provenance.append({"folder": folder, "menu_index": index, "signature": menu["Signature"],
                                        "kind": menu_kinds[sources], "receipt_sha256": sha((observed / folder / "receipt.json").read_bytes())})
        full_fills = [f["step"] for f in receipt["fill_events"] if not f["within_list"]
                      and f["native_rect"][0] <= 8 and f["native_rect"][1] <= 8
                      and f["native_rect"][0] + f["native_rect"][2] >= 312
                      and f["native_rect"][1] + f["native_rect"][3] >= 184]
        h = next((h for h in headers if h["Pane"] == pane), None)
        title_indices = {i for i, w in enumerate(receipt["wrappers"])
                         if h and (w["format"]["segment"], w["format"]["offset"], sha(w["format"]["text"].encode()))
                         == (h["Segment"], h["Offset"], h["SHA256"]) and w["stack"][3] & 255 == 1}
        assert title_indices or pane in ("effects", "camp")
        intervals = [(receipt["wrappers"][i]["step"], next(f for f in full_fills if f > receipt["wrappers"][i]["step"])) for i in title_indices]
        suffix_indices = {i - 1 for i in title_indices}
        for i in suffix_indices:
            assert receipt["wrappers"][i]["format"]["text"] == "'s"
        for c in receipt["calls"]:
            fmt, stack = c["format"], c["stack"]
            source = c["vararg_1_candidate"] if fmt["text"] == "%s" else fmt
            if not source["nul_terminated"]:
                continue
            text, group, scope, menu_signature = source["text"], None, pane, ""
            active = any(start <= c["step"] < end for start, end in intervals)
            if c["wrapper_index"] in title_indices:
                group = "header"
            elif c["wrapper_index"] in suffix_indices:
                group, scope = "header", "suffix"
            elif c["caller"] == {"Seg": 0xCEB, "Off": 0x1BE} and stack[2] == 189 and c["menu_index"] in known_menus:
                group, scope, menu_signature = "footer", "menu", known_menus[c["menu_index"]]
                assert text in menu_terms
            elif active and text in ("Ready Item", "1st Level", "Choose Spell:"):
                group = "footer" if text == "Choose Spell:" else "body"
            if group is None:
                continue
            key = field_key(text)
            native = lambda value: value if 0 <= value < 400 else (value - 8000) * 2
            x, y = native(stack[3]), native(stack[2])
            assert 0 <= x < x + len(text) * 8 <= 320 and 0 <= y <= 192
            field = {"Pane": scope, "Group": group, "Key": key,
                     "Start": 0, "Length": len(text),
                     "MenuSignature": menu_signature,
                     "RawX": stack[3], "RawY": stack[2], "Caller": c["caller"],
                     "FormatSHA256": sha(fmt["text"].encode()), "SHA256": sha(text.encode())}
            identity = json.dumps(field, sort_keys=True)
            if identity not in field_ids:
                fields.append(field)
                field_ids.add(identity)
        # 整表已給出所有按鈕。反白階段可能只印其中一個，不以舊追蹤是否
        # 恰好印過該按鈕，限制同一已知完整選單的其餘按鈕。
        native = lambda value: value if value < 400 else (value - 8000) * 2
        for index, signature in known_menus.items():
            for button in receipt["menus"][index]["Buttons"]:
                text = bytes.fromhex(button["SourceHex"]).decode("ascii")
                x, y = native(button["RawX"]), native(button["RawY"]) + 1
                assert 0 <= x < x + len(text)*8 <= 320 and y == 189
                field = {"Pane": "menu", "Group": "footer", "Key": field_key(text),
                         "Start": 0, "Length": len(text), "MenuSignature": signature,
                         "RawX": x, "RawY": y, "Caller": {"Seg": 0xCEB, "Off": 0x1BE},
                         "FormatSHA256": button["SHA256"], "SHA256": button["SHA256"]}
                identity = json.dumps(field, sort_keys=True)
                if identity not in field_ids:
                    fields.append(field)
                    field_ids.add(identity)
    effects = json.loads((observed / "observe-effects-r1/receipt.json").read_text())
    first = effects["list_events"][0]
    assert menus[first["menu_snapshot"]["Signature"]] == "effects"
    contexts = [{"Pane": "effects", "RowFillPage": True, "DescriptorSHA256": sha(bytes.fromhex(first["descriptor_before_hex"])),
                 "MenuSignature": first["menu_snapshot"]["Signature"],
                 "Caller": {"Seg": first["stack"][1], "Off": first["stack"][0]}}]
    effect_sources = {en[key].strip(): key for key in ("ui.07259b8cfb9f6862dd7d", "ui.1325da320d8d79b3c1ca", "ui.fbcb3b194ad0afcbb789")}
    # 姓名同樣經過列表函式，但原版標成紅色；只取已觀測的一般／反白效果列。
    actual = {w["vararg_1_candidate"]["text"] for w in effects["wrappers"]
              if w["format"]["text"] == "%s" and w["vararg_1_candidate"]["nul_terminated"]
              and w["vararg_1_candidate"]["text"].strip() in effect_sources and w["stack"][4] & 255 in (7, 11)}
    assert len(actual) == len(effect_sources)
    for text in sorted(actual):
        assert text.startswith(" ") and not text.endswith(" ")
        key = field_key(text[1:])
        rows.append({"Pane": "effects", "SHA256": sha(text.encode()), "Foregrounds": [7, 11],
                     "Spans": [{"Start": 1, "Length": len(text)-1, "Key": key}]})
    # 狀態及計數在列表標題之前印出。只接已觀測的上層專屬呼叫者，
    # 再由同一個尚未返回的 wrapper 核對完整來源、座標及下層印字。
    status_callers = {0x46, 0x6E, 0xA8, 0xD3, 0x10D, 0x147, 0x2F0, 0x309,
                      0x3FA, 0x508, 0x5FD, 0x68F, 0x6D6, 0x760, 0x7BE, 0x81D, 0x93C}
    callsite_sources = []
    for folder in ("observe-items-r2", "observe-grimoire-r2"):
        receipt = json.loads((observed / folder / "receipt.json").read_text())
        for c in receipt["calls"]:
            if c["wrapper_index"] < 0:
                continue
            wrapper = receipt["wrappers"][c["wrapper_index"]]
            caller = wrapper["caller"]
            status = caller["Seg"] == 0x2C4A and caller["Off"] in status_callers
            equipped = caller == {"Seg": 0x88E, "Off": 0x71D}
            counter = caller == {"Seg": 0x26B4, "Off": 0x9ED}
            if not (status or equipped or counter):
                continue
            source, stack = c["vararg_1_candidate"], c["stack"]
            assert c["format"]["text"] == "%s" and source["nul_terminated"]
            text = source["text"]
            assert wrapper["format"]["text"] == text
            start, end = len(text) - len(text.lstrip()), len(text.rstrip())
            categories = None
            if status and caller["Off"] == 0xD3:
                match = re.fullmatch(r"[0-9]+ (years)", text)
                assert match
                start, end = match.span(1)
            elif status and caller["Off"] == 0x7BE:
                assert text == "THAC0\t "
                start, end, categories = 0, 5, {"attribute"}
            elif status and caller["Off"] == 0x2F0:
                categories = {"class"}
            elif status and caller["Off"] == 0x147:
                categories = {"race"}
            elif equipped:
                categories = {"item"}
                item = re.fullmatch(r"(.+?)(?: \+[0-9]+)? *", text)
                assert item
                start, end = item.span(1)
            key = field_key(text[start:end], categories)
            field = {"Pane": "callsite", "Group": "body", "Key": key,
                     "Start": start, "Length": end - start, "UpperCaller": caller,
                     "RawX": stack[3], "RawY": stack[2], "Caller": c["caller"],
                     "FormatSHA256": sha(c["format"]["text"].encode()), "SHA256": sha(text.encode())}
            identity = json.dumps(field, sort_keys=True)
            if identity not in field_ids:
                fields.append(field)
                field_ids.add(identity)
            callsite_sources.append({"folder": folder, "step": c["step"], "wrapper_step": wrapper["step"],
                                     "first_glyph": c["first_glyph"], "field": field})
    # 同一筆 AC\tHP 印字分為兩框；安全寬度由原版欄間與面板留白量測。
    hud_sources = {
        (0x205E, 0x2A0): ("Name", [(0, 4, 0)]),
        (0x205E, 0x2B9): ("AC\tHP", [(0, 2, 24), (3, 2, 24)]),
        (0x205E, 0x64F): ("camping", [(0, 7, 0)]),
        (0x26B4, 0x2DB2): ("the party makes camp...", [(0, 23, 0)])}
    hud = json.loads((observed / "observe-camp-roundtrip-r1/receipt.json").read_text())
    seen_hud = set()
    for c in hud["calls"]:
        if c["wrapper_index"] < 0:
            continue
        wrapper = hud["wrappers"][c["wrapper_index"]]
        caller = wrapper["caller"]
        identity = caller["Seg"], caller["Off"]
        if identity not in hud_sources:
            continue
        source, spans = hud_sources[identity]
        assert c["format"]["text"] == "%s" and c["vararg_1_candidate"]["text"] == wrapper["format"]["text"] == source
        seen_hud.add(identity)
        for start, length, width in spans:
            key = field_key(source[start:start+length], width=width or None)
            field = {"Pane": "callsite", "Group": "body", "Key": key, "Start": start, "Length": length,
                     "RawX": c["stack"][3], "RawY": c["stack"][2], "Caller": c["caller"], "UpperCaller": caller,
                     "FormatSHA256": sha(c["format"]["text"].encode()), "SHA256": sha(source.encode())}
            if width:
                field["Width"] = width
            encoded = json.dumps(field, sort_keys=True)
            if encoded not in field_ids:
                fields.append(field)
                field_ids.add(encoded)
            callsite_sources.append({"folder": "observe-camp-roundtrip-r1", "step": c["step"],
                "wrapper_step": wrapper["step"], "caller": caller, "source": source, "binding": field})
    assert seen_hud == set(hud_sources)
    clock = json.loads((observed / "observe-clock-city-r1/receipt.json").read_text())
    for c in clock["calls"]:
        if c["wrapper_index"] < 0:
            continue
        wrapper = clock["wrappers"][c["wrapper_index"]]
        caller = wrapper["caller"]
        text = c["vararg_1_candidate"]["text"]
        period = caller == {"Seg": 0x205E, "Off": 0x53C}
        rest = caller == {"Seg": 0x4A6, "Off": 0x631} and text == "Rest Time:"
        if not (period or rest):
            continue
        assert c["format"]["text"] == "%s" and c["vararg_1_candidate"]["nul_terminated"]
        assert wrapper["format"]["text"] == text
        if period:
            assert re.fullmatch(r"[0-9]{1,2}:[0-9]{2} (AM|PM)", text)
            source = text[-2:]
        else:
            source = text
        field = {"Pane":"callsite", "Group":"body", "Key":field_key(source), "Start":0, "Length":len(source),
                 "RawX":c["stack"][3], "RawY":c["stack"][2], "Caller":c["caller"], "UpperCaller":caller,
                 "FormatSHA256":sha(c["format"]["text"].encode()), "SHA256":sha(source.encode())}
        if period:
            field["SourcePattern"] = "clock-period"
        encoded = json.dumps(field, sort_keys=True)
        if encoded not in field_ids:
            fields.append(field)
            field_ids.add(encoded)
        callsite_sources.append({"folder":"observe-clock-city-r1", "step":c["step"], "wrapper_step":wrapper["step"],
                                 "caller":caller,"source":text,"binding":field})
    paragraph_bindings, paragraph_provenance = [], []
    paragraph_receipt = None
    if paragraph_trace is not None:
        paragraph_receipt = json.loads(paragraph_trace.read_text())
        assert paragraph_receipt["observe"] and paragraph_receipt["exe_sha256"] == "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
        assert paragraph_receipt["paragraphs"] and not paragraph_receipt["pending_paragraphs"]
        identities = set()
        for p in paragraph_receipt["paragraphs"]:
            source, stack = p["source"], p["stack"]
            assert source["nul_terminated"] and bytes.fromhex(source["hex"]).decode("ascii") == source["text"]
            assert (source["segment"], source["offset"]) == (stack[10], stack[9])
            assert p["step"] < p["first_glyph"] < p["return_step"]
            key = "ecl." + sha(source["text"].encode())[:20]
            assert en.get(key) == source["text"] and key in zh
            assert p["native_box"] == [8,136,312,184] and p["foreground"] in (3,7) and p["background"] == 0 and p["clear"] in (0,1)
            aliases[key], translations[key] = en[key], zh[key]
            binding = {"Key":key,"SHA256":sha(source["text"].encode()),"Caller":p["caller"],"NativeBox":p["native_box"],
                       "Foreground":p["foreground"],"Background":p["background"],"Clear":p["clear"]}
            identity = json.dumps(binding,sort_keys=True)
            if identity not in identities:
                identities.add(identity); paragraph_bindings.append(binding)
            paragraph_provenance.append({"step":p["step"],"first_glyph":p["first_glyph"],"return_step":p["return_step"],"binding":binding})
        for call in paragraph_receipt["calls"]:
            if call["wrapper_index"]<0:
                continue
            wrapper = paragraph_receipt["wrappers"][call["wrapper_index"]]
            if wrapper["caller"] != {"Seg":0xCEB,"Off":0x4BD}:
                continue
            text = call["vararg_1_candidate"]["text"]
            assert wrapper["format"]["text"] == text == "Press        to continue."
            assert call["format"]["text"] == "%s" and call["vararg_1_candidate"]["nul_terminated"]
            assert call["stack"][2:5] == [189,8032,0x70]
            assert [(wrapper["stack"][n]&255)*8 for n in (2,3)] == [56,192]
            for start,length in ((0,5),(13,12)):
                field = {"Pane":"callsite","Group":"footer","Key":field_key(text[start:start+length]),"Start":start,"Length":length,
                         "RawX":8032,"RawY":189,"Caller":call["caller"],"UpperCaller":wrapper["caller"],"UpperNative":[56,192],
                         "BackgroundOverride":7,"Color":0x70,"FormatSHA256":sha(b"%s"),"SHA256":sha(text.encode())}
                identity = json.dumps(field,sort_keys=True)
                if identity not in field_ids:
                    fields.append(field); field_ids.add(identity)
                callsite_sources.append({"folder":str(paragraph_trace),"step":call["step"],"wrapper_step":wrapper["step"],"binding":field})
    output.mkdir()
    for name, strings in (("en.tsv", aliases), ("zh-TW.tsv", translations)):
        (output / name).write_text("key\ttext\n" + "".join(f"{key}\t{value}\n" for key, value in strings.items()))
    row_hashes = {row["SHA256"] for row in rows}
    row_callers = set()
    for folder in ("observe-menus-items-r1", "observe-menus-grimoire-r1", "observe-effects-r1"):
        original = json.loads((observed / folder / "receipt.json").read_text())
        row_callers.update((w["caller"]["Seg"], w["caller"]["Off"]) for w in original["wrappers"]
                           if w["format"]["text"] == "%s" and w["vararg_1_candidate"]["nul_terminated"]
                           and sha(w["vararg_1_candidate"]["text"].encode()) in row_hashes
                           and w["stack"][4] & 255 in (7, 11))
    assert row_callers and all(seg == 0xC15 for seg, _ in row_callers)
    windows = [[666000000, 667000000], [672000000, 673000000], [681000000, 682000000],
               [690000000, 691000000], [699000000, 700000000], [705000000, 706000000],
               [717000000, 718000000], [720000000, 721000000], [727000000, 728000000],
               [738000000, 739000000], [741000000, 742000000], [744000000, 745000000]]
    camp_request = observed / "camp-roundtrip-request.json"
    for action in json.loads(camp_request.read_text())["actions"]:
        windows.append([action["at"], min(action["at"]+1000000, action["end"])])
    clock_request = observed / "clock-city-request.json"
    for action in json.loads(clock_request.read_text())["actions"]:
        windows.append([action["at"],min(action["at"]+1000000,action["end"])])
    for wrapper in clock["wrappers"]:
        if wrapper["caller"] == {"Seg":0x205E,"Off":0x53C}:
            start = wrapper["step"] // 1000000 * 1000000
            windows.append([start,start+1000000])
    if paragraph_receipt is not None:
        # 以這條玩家路徑的完整段落繪製及操作入口取樣，不沿用其他路徑的閒置區間。
        windows = [[a["at"], min(a["at"]+1000000,a["end"])] for a in paragraph_receipt["request"]["actions"]]
        windows += [[p["step"]//2000*2000,(p["return_step"]+1999)//2000*2000] for p in paragraph_receipt["paragraphs"]]
        # 提示在段落返回後才繪製，需另含同列 RETURN 按鈕的後續重畫。
        windows += [[w["step"]//1000000*1000000, (w["step"]//1000000+1)*1000000]
                    for w in paragraph_receipt["wrappers"] if w["caller"] == {"Seg":0xCEB,"Off":0x4BD}]
    merged = []
    for start, end in sorted(windows):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    config = {"Headers": headers, "Rows": rows, "Fields": fields, "Menus": menus, "PaneLists": contexts,
              "RowCallers": [{"Seg": seg, "Off": off} for seg, off in sorted(row_callers)],
              "Background": backgrounds.pop(),
              "fine_windows": merged}
    if paragraph_receipt is not None:
        config["Paragraphs"] = paragraph_bindings
    (output / "inputs.json").write_text(json.dumps(config, indent=2) + "\n")
    result_provenance = {"draft": True, "headers": provenance, "bindings": bindings,
        "fields": field_provenance,
        "callsite_sources": callsite_sources,
        "menus": menu_provenance,
        "effects_receipt_sha256": sha((observed / "observe-effects-r1/receipt.json").read_bytes()),
        "camp_request_sha256": sha(camp_request.read_bytes()),
        "clock_request_sha256": sha(clock_request.read_bytes()),
        "reviewed_fields_sha256": sha((texts / "ui-list-chrome-reviewed.tsv").read_bytes()),
        "observed_rows": len(rows),
        "formal_en_sha256": sha((texts / "en.tsv").read_bytes()),
        "formal_zh_sha256": sha((texts / "zh-TW.tsv").read_bytes()),
        "glossary_sha256": sha((texts / "glossary.tsv").read_bytes()),
        "tool_sha256": sha(Path(__file__).read_bytes())}
    if paragraph_trace is not None:
        result_provenance["paragraph_trace_sha256"] = sha(paragraph_trace.read_bytes())
        result_provenance["paragraph_bindings"] = paragraph_provenance
    (output / "provenance.json").write_text(json.dumps(result_provenance, ensure_ascii=False, indent=2) + "\n")
    print(f"列表原型輸入：{len(rows)} 種完整列、{len(field_provenance)} 種標題提示與按鈕；未改正式譯表")


if __name__ == "__main__":
    prepare(*map(Path, sys.argv[1:]))
