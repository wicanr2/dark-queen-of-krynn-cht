"""DRAFT：從兩條正常服務重播衍生已觀測列表及文字切片；不改原版資料。"""
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

from ui_list_inputs import catalog


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(base, text, traces, output):
    assert not output.exists() and output.parent.is_dir()
    en, zh = catalog(base / "en.tsv"), catalog(base / "zh-TW.tsv")
    formal_en, formal_zh = catalog(text / "en.tsv"), catalog(text / "zh-TW.tsv")
    with (text / "glossary.tsv").open() as stream:
        terms = list(csv.DictReader(stream, delimiter="\t"))
    config = json.loads((base / "inputs.json").read_text())
    provenance = json.loads((base / "provenance.json").read_text())
    added = {"rows": [], "fields": [], "contexts": [], "menus": [], "words": []}
    row_ids = {(r["Pane"], r["SHA256"]) for r in config["Rows"]}
    field_ids = {json.dumps(f, sort_keys=True) for f in config["Fields"]}
    context_ids = {json.dumps(c, sort_keys=True) for c in config["PaneLists"]}

    def formal(source):
        found = [(key, formal_zh[key]) for key, value in formal_en.items() if value == source and key in formal_zh]
        assert found and len({v for _, v in found}) == 1, source
        return found[0]

    def word(source, category=None, origin=None, translated=None):
        key = "service." + (category or "ui") + "." + sha(source.encode())[:20]
        if category:
            spelling = {"Arrows": "Arrow", "Darts": "Dart", "Bolts": "Bolt", "Javelins": "Javelin"}.get(source, source)
            categories = {"ui"} if category == "item" and spelling == "Shield" else {category}
            found = [t for t in terms if t["en"].casefold() == spelling.casefold() and t["category"] in categories]
            if found:
                assert len(found) == 1, (source, category)
                translated, origin = found[0]["zh"], {"glossary": found[0], "observed_source": source}
            else:
                formal_key, translated = formal(spelling)
                origin = {"formal_key": formal_key, "observed_source": source, "root": spelling}
        elif translated is None:
            formal_key, translated = formal(source)
            origin = {"formal_key": formal_key}
        assert translated and len(translated) * 8 <= len(source) * 8, (source, translated)
        if key in en:
            assert en[key] == source and zh[key] == translated
        else:
            en[key], zh[key] = source, translated
            added["words"].append({"key": key, "source": source, "origin": origin})
        return key

    def row(pane, source, spans):
        identity = (pane, sha(source.encode()))
        if identity not in row_ids:
            value = {"Pane": pane, "SHA256": identity[1], "Spans": spans, "Foregrounds": [7, 11]}
            config["Rows"].append(value); added["rows"].append(value); row_ids.add(identity)

    def field(value):
        identity = json.dumps(value, sort_keys=True)
        if identity not in field_ids:
            config["Fields"].append(value); added["fields"].append(value); field_ids.add(identity)

    def menu_word(source):
        keys = {f["Key"] for f in config["Fields"] if f["Pane"] == "menu" and en[f["Key"]] == source}
        if not keys:
            return word(source, "ui")
        assert len({zh[key] for key in keys}) == 1, source
        return sorted(keys)[0]

    native = lambda value: value if value < 400 else (value - 8000) * 2
    contexts = {("Buy", "Exit"): "shop-stock", ("Heal", "Exit"): "temple-spells"}
    menu_kinds = {**contexts, ("Rdy", "Trade", "Drop", "Halve", "Join", "Sell", "Id", "Exit"): "inventory"}
    windows, receipts = [], []
    stock_sources, temple_sources = set(), set()
    for filename in ("observe-shop-full-r1/receipt.json", "observe-temple-full-r1/receipt.json"):
        path = traces / filename
        receipt = json.loads(path.read_text()); receipts.append(receipt)
        assert receipt["observe"] and receipt["exe_sha256"] == "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
        assert all(not receipt[k] for k in ("pending_calls", "pending_lists", "pending_fills", "pending_scrolls", "pending_paragraphs"))
        for menu in receipt["menus"]:
            names = tuple(bytes.fromhex(b["SourceHex"]).decode("ascii") for b in menu["Buttons"])
            if names not in menu_kinds:
                continue
            signature, pane = menu["Signature"], menu_kinds[names]
            assert signature not in config["Menus"] or config["Menus"][signature] == pane
            config["Menus"][signature] = pane
            added["menus"].append({"receipt": filename, "signature": signature, "pane": pane})
            for button in menu["Buttons"]:
                source = bytes.fromhex(button["SourceHex"]).decode("ascii")
                field({"Pane": "menu", "Group": "footer", "Key": menu_word(source), "Start": 0, "Length": len(source),
                       "MenuSignature": signature, "RawX": native(button["RawX"]), "RawY": native(button["RawY"]) + 1,
                       "Caller": {"Seg": 0xCEB, "Off": 0x1BE}, "FormatSHA256": button["SHA256"], "SHA256": button["SHA256"]})
        for listing in receipt["list_events"] or []:
            signature = listing["menu_snapshot"]["Signature"]
            pane = config["Menus"].get(signature)
            if pane not in contexts.values():
                continue
            value = {"Pane": pane, "RowFillPage": True, "DescriptorSHA256": sha(bytes.fromhex(listing["descriptor_before_hex"])),
                     "MenuSignature": signature, "Caller": {"Seg": listing["stack"][1], "Off": listing["stack"][0]}}
            identity = json.dumps(value, sort_keys=True)
            if identity not in context_ids:
                config["PaneLists"].append(value); added["contexts"].append(value); context_ids.add(identity)
            for wrapper in receipt["wrappers"]:
                if not listing["step"] <= wrapper["step"] <= listing["return_instruction_step"] or wrapper["caller"] not in config["RowCallers"]:
                    continue
                assert wrapper["format"]["text"] == "%s" and wrapper["vararg_1_candidate"]["nul_terminated"]
                source = wrapper["vararg_1_candidate"]["text"]
                if pane == "shop-stock":
                    match = re.fullmatch(r"(?:(\d+) )?(.+?) +([0-9]+)", source)
                    assert match, source
                    name, start = match[2], match.start(2); stock_sources.add(source)
                    spans = [{"Start": start, "Length": len(name), "Key": word(name, "item")}]
                else:
                    temple_sources.add(source)
                    spans = [{"Start": 0, "Length": len(source), "Key": word(source, "ui" if source == "Heal" else "spell")}]
                row(pane, source, spans)
        for wrapper in receipt["wrappers"]:
            source = wrapper["vararg_1_candidate"]["text"]
            if wrapper["format"]["text"] == "%s" and wrapper["caller"] in config["RowCallers"] and "\t" in source and ("inventory", sha(source.encode())) not in row_ids:
                # 本次唯一新增背包列是實際購入的普通盾牌；其他新變體仍拒絕。
                match = re.fullmatch(r" (No)\t (Shield) ", source)
                assert match, source
                row("inventory", source, [{"Start": match.start(i), "Length": len(match[i]), "Key": word(match[i], "ui" if i == 1 else "item")} for i in (1, 2)])
        for call in receipt["calls"]:
            if call["wrapper_index"] < 0 or call["format"]["text"] != "%s":
                continue
            wrapper = receipt["wrappers"][call["wrapper_index"]]
            source = call["vararg_1_candidate"]["text"]
            if not call["vararg_1_candidate"]["nul_terminated"]:
                continue
            parts = []
            if wrapper["caller"] in ({"Seg": 0x291A, "Off": 0x42D}, {"Seg": 0x291A, "Off": 0x489}):
                assert wrapper["format"]["text"] == source
                template = "Personal funds:%s" if source.startswith("Personal funds:") else "Pooled funds:  %s"
                key, translated = formal(template); prefix = template.split("%s")[0].rstrip()
                assert source.startswith(prefix) and re.fullmatch(r" +[0-9]+", source[len(prefix):])
                parts = [(0, prefix, word(prefix, origin={"formal_template": key, "prefix_only": True}, translated=translated.split("%s")[0]))]
            elif wrapper["caller"] == {"Seg": 0xCEB, "Off": 0x995} and source == "items :":
                key, translated = formal("items : ")
                assert translated.endswith("：")
                # 只覆蓋英文詞，原版空白、冒號與按鈕邊緣保留。
                parts = [(0, "items", word("items", origin={"formal_key": key, "lexical_slice": True}, translated=translated[:-1]))]
            elif wrapper["caller"] == {"Seg": 0x2A20, "Off": 0x7D6}:
                assert wrapper["format"]["text"] == "%s%s"
                prefix = wrapper["vararg_1_candidate"]["text"]; suffix = source[len(prefix):]
                assert source.startswith(prefix) and suffix == ", how can we help you?"
                parts = [(len(prefix), suffix, word(suffix))]
            elif wrapper["caller"] == {"Seg": 0x088E, "Off": 0x1560}:
                separator = " buys a "
                assert wrapper["format"]["text"] == "%s" and source.count(separator) == 1 and source.endswith("  ")
                prefix, name = source[:-2].split(separator)
                assert name == "Shield"
                parts = [(len(prefix), separator, word(separator)), (len(prefix) + len(separator), name, word(name, "item"))]
            for start, fragment, key in parts:
                value = {"Pane": "callsite", "Group": "footer" if call["stack"][2] == 189 else "body", "Key": key,
                         "Start": start, "Length": len(fragment), "RawX": call["stack"][3], "RawY": call["stack"][2],
                         "Caller": call["caller"], "UpperCaller": wrapper["caller"],
                         "FormatSHA256": sha(call["format"]["text"].encode()), "SHA256": sha(source.encode())}
                if wrapper["format"]["text"] != source:
                    value["UpperFormatSHA256"] = sha(wrapper["format"]["text"].encode())
                if wrapper["caller"] == {"Seg": 0x088E, "Off": 0x1560}:
                    value.update(UpperNative=[0, 192], Color=0x8F)
                if wrapper["caller"] == {"Seg": 0xCEB, "Off": 0x995}:
                    value.update(UpperNative=[0, 192], Color=0x70, BackgroundOverride=7)
                expected_upper = value.get("UpperNative", [native(call["stack"][3]), native(call["stack"][2])])
                assert [(wrapper["stack"][n] & 255) * 8 for n in (2, 3)] == expected_upper, (source, expected_upper)
                field(value)
        for action in receipt["request"]["actions"]:
            windows.append([action["at"], min(action["at"] + 80000, action["end"])])
        for call in receipt["calls"]:
            wrapper = receipt["wrappers"][call["wrapper_index"]] if call["wrapper_index"] >= 0 else call
            windows.append([max(receipt["request"]["start_steps"], wrapper["step"] - 2000), call["return_step"] + 2000])
        for event in (receipt["fill_events"] or []) + (receipt["scroll_events"] or []):
            end = event.get("return_instruction_step", event.get("return_step"))
            assert end is not None
            windows.append([event["step"] - 2000, end + 2000])
    assert len(stock_sources) == 45 and len(temple_sources) == 11
    merged = []
    for start, end in sorted(windows):
        if merged and start <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], end)
        else: merged.append([start, end])
    config["fine_windows"] = merged
    output.mkdir()
    for path in base.iterdir():
        if path.is_file() and path.name not in ("inputs.json", "en.tsv", "zh-TW.tsv", "glyphs-16.json", "font-zh-TW.tsv", "provenance.json", "reader-controls.json"):
            (output / path.name).write_bytes(path.read_bytes())
    for name, values in (("en.tsv", en), ("zh-TW.tsv", zh)):
        (output / name).write_text("key\ttext\n" + "".join(f"{key}\t{value}\n" for key, value in values.items()))
    font = catalog(base / "font-zh-TW.tsv"); font.update(zh)
    (output / "font-zh-TW.tsv").write_text("key\ttext\n" + "".join(f"{key}\t{value}\n" for key, value in font.items()))
    (output / "inputs.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    lifetime_path = traces / "observe-purchase-lifetime-r1/receipt.json"
    lifetime = json.loads(lifetime_path.read_text())
    assert lifetime["pending_wrappers"] == 0
    provenance["service_extension"] = {"draft": True, "base_files": {p.name: sha(p.read_bytes()) for p in base.iterdir() if p.is_file()},
        "current_sources": {name: sha((text / name).read_bytes()) for name in ("en.tsv", "zh-TW.tsv", "glossary.tsv")},
        "receipts": {name: sha((traces / name).read_bytes()) for name in ("observe-shop-full-r1/receipt.json", "observe-temple-full-r1/receipt.json")},
        "tool_sha256": sha(Path(__file__).read_bytes()), "added": added,
        "feedback_proof": {"receipt": "observe-purchase-lifetime-r1/receipt.json", "sha256": sha(lifetime_path.read_bytes())},
        "feedback_boundaries": {"receipt": "observe-purchase-boundaries-r1/receipt.json", "sha256": sha((traces / "observe-purchase-boundaries-r1/receipt.json").read_bytes())},
        "limits": "DRAFT observed service lists; original names, prices, counts, funds and HP unchanged; old scripted reader controls belong to a different request and are not copied"}
    (output / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"stock_rows": 45, "temple_rows": 11, "new_rows": len(added["rows"]), "new_fields": len(added["fields"]), "new_contexts": len(added["contexts"]), "aliases": len(en)}))


if __name__ == "__main__":
    prepare(*(Path(p) for p in sys.argv[1:]))
