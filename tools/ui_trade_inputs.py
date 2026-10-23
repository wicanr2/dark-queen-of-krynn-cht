"""DRAFT：由正常買賣原版收據與正式 TSV 衍生服務組句，不改遊戲資料。"""
import hashlib
import json
from pathlib import Path
import re
import sys

from ui_list_inputs import catalog


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(base, text, traces, output):
    assert base.is_dir() and traces.is_dir() and not output.exists()
    en, zh = catalog(base / "en.tsv"), catalog(base / "zh-TW.tsv")
    formal_en, formal_zh = catalog(text / "en.tsv"), catalog(text / "zh-TW.tsv")
    config = json.loads((base / "inputs.json").read_text())
    provenance = json.loads((base / "provenance.json").read_text())
    receipt_path = traces / "observe-combined-r1/receipt.json"
    boundary_path = traces / "observe-combined-boundaries-r2/receipt.json"
    receipt, boundary = [json.loads(p.read_text()) for p in (receipt_path, boundary_path)]
    assert receipt["observe"] and all(not v for k, v in receipt.items() if k.startswith("pending_"))
    assert receipt["exe_sha256"] == "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
    templates, added, messages, windows = {}, {"fields": [], "menus": [], "words": []}, [], []
    field_ids = {json.dumps(f, sort_keys=True) for f in config["Fields"]}

    def formal(source):
        found = [k for k, v in formal_en.items() if v == source and k in formal_zh]
        assert found and len({formal_zh[k] for k in found}) == 1, source
        key = found[0]
        templates[key] = {"en": formal_en[key], "zh": formal_zh[key]}
        return key

    def alias(source, translation, origin):
        key = "trade.ui." + sha(source.encode())[:20]
        assert source and translation and len(translation) <= len(source)
        if key in en:
            assert en[key] == source and zh[key] == translation
        else:
            en[key], zh[key] = source, translation
            added["words"].append({"key": key, "origin": origin})
        return key

    def term_key(source):
        found = {span["Key"] for row in config["Rows"] if row["Pane"] in ("inventory", "shop-stock")
                 for span in row["Spans"] if en[span["Key"]] == source}
        assert found and len({zh[k] for k in found}) == 1, source
        return sorted(found)[0]

    def field(value):
        identity = json.dumps(value, sort_keys=True)
        if identity not in field_ids:
            config["Fields"].append(value); added["fields"].append(value); field_ids.add(identity)

    native = lambda value: value if value < 400 else (value - 8000) * 2
    for menu in receipt["menus"]:
        names = tuple(bytes.fromhex(b["SourceHex"]).decode("ascii") for b in menu["Buttons"])
        if names != ("Yes", "No"):
            continue
        signature = menu["Signature"]
        assert signature not in config["Menus"] or config["Menus"][signature] == "confirm"
        config["Menus"][signature] = "confirm"
        added["menus"].append(signature)
        for button in menu["Buttons"]:
            source = bytes.fromhex(button["SourceHex"]).decode("ascii")
            key = formal(source)
            binding_key = alias(source, formal_zh[key], {"formal_key": key})
            field({"Pane": "menu", "Group": "footer", "Key": binding_key, "Start": 0, "Length": len(source),
                   "MenuSignature": signature, "RawX": native(button["RawX"]), "RawY": native(button["RawY"]) + 1,
                   "Caller": {"Seg": 0xCEB, "Off": 0x1BE}, "FormatSHA256": button["SHA256"], "SHA256": button["SHA256"]})

    for call in receipt["calls"]:
        if call["wrapper_index"] < 0 or call["format"]["text"] != "%s":
            continue
        wrapper = receipt["wrappers"][call["wrapper_index"]]
        source = call["vararg_1_candidate"]["text"]
        owner = wrapper["caller"]
        if owner == {"Seg": 0x88E, "Off": 0x1560} and source in ("Must be unreadied", "Sold!"):
            template = formal(source)
            key = alias(source, formal_zh[template], {"formal_key": template})
            extra = {"Color": 0x8F}
        elif owner == {"Seg": 0xCEB, "Off": 0x995} and source in ("Is It a Deal? ", "Will you sell it? "):
            if source.startswith("Is"):
                template = formal(source)
                key = alias(source.rstrip(), formal_zh[template], {"formal_key": template, "lexical_slice": True})
            else:
                prefix, suffix = formal("Will you sell "), formal("%sit? ")
                assert formal_en[suffix] % formal_en[prefix] == source
                key = alias(source.rstrip(), formal_zh[suffix] % formal_zh[prefix], {"prefix_key": prefix, "suffix_key": suffix, "lexical_slice": True})
            extra = {"Color": 0x70, "BackgroundOverride": 7}
        else:
            continue
        assert wrapper["format"]["text"] == "%s" and call["stack"][2:4] == [189, 8004]
        assert [(wrapper["stack"][n] & 255)*8 for n in (2, 3)] == [0, 192]
        field({"Pane": "callsite", "Group": "footer", "Key": key, "Start": 0, "Length": len(en[key]),
               "RawX": 8004, "RawY": 189, "Caller": call["caller"], "UpperCaller": owner,
               "UpperNative": [0, 192], "UpperFormatSHA256": sha(b"%s"), "FormatSHA256": sha(b"%s"), "SHA256": sha(source.encode()), **extra})

    template_callers = {0xEEE: "For 20 steel pieces I'll identify your %s",
                        0xFD0: "I can't tell anything new about your %s",
                        0xC7F: "I'll give you %u steel pieces for your %s"}
    for p in receipt["paragraphs"] or []:
        if p["native_box"] != [8, 168, 312, 184]:
            continue
        assert p["caller"]["Seg"] == 0x291A and p["caller"]["Off"] in template_callers
        assert [p[k] for k in ("foreground", "background", "clear")] == [11, 0, 1]
        template_key = formal(template_callers[p["caller"]["Off"]])
        template = formal_en[template_key]
        pattern = re.escape(template).replace("%u", r"([0-9]+)").replace("%s", r"(.+?)") + " "
        source = p["source"]["text"]
        match = re.fullmatch(pattern, source); assert match, source
        name_key = term_key(match.groups()[-1])
        args = [{"kind": "term", "key": name_key}]
        values = [zh[name_key]]
        if "%u" in template:
            args.insert(0, {"kind": "integer", "value": int(match[1])}); values.insert(0, int(match[1]))
        translation = formal_zh[template_key] % tuple(values)
        assert len(translation) <= 38 and "\n" not in translation
        key = "service-message." + sha(source.encode())[:20]
        en[key], zh[key] = source, translation
        binding = {"Key": key, "SHA256": sha(source.encode()), "Caller": p["caller"], "NativeBox": p["native_box"],
                   "Foreground": 11, "Background": 0, "Clear": 1}
        if binding not in config["Paragraphs"]: config["Paragraphs"].append(binding)
        cp = next(c for c in boundary["checkpoints"] if c["step"] == p["return_step"])
        raw = (boundary_path.parent / cp["indexed_file"]).read_bytes()
        assert sha(raw) == cp["indexed_sha256"]
        crop = b"".join(raw[y*320+8:y*320+312] for y in range(168, 184))
        assert set(crop) == {11, 23}
        messages.append({"step": p["step"], "binding": binding, "template_key": template_key, "args": args,
                         "native_painted_step": p["return_step"], "native_pixels_sha256": sha(crop)})
        windows.append([p["step"]-2000, p["return_step"]+2000])
    assert len(messages) == 5 and len({m["binding"]["Key"] for m in messages}) == 3
    for a in receipt["request"]["actions"]: windows.append([a["at"], min(a["at"]+80000, a["end"])])
    for c in receipt["calls"]:
        w = receipt["wrappers"][c["wrapper_index"]] if c["wrapper_index"] >= 0 else c
        windows.append([w["step"]-2000, c["return_step"]+2000])
    for e in (receipt["fill_events"] or []) + (receipt["scroll_events"] or []):
        windows.append([e["step"]-2000, e.get("return_instruction_step", e.get("return_step"))+2000])
    merged = []
    for start, end in sorted(windows):
        if merged and start <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], end)
        else: merged.append([start, end])
    config["fine_windows"] = merged
    provenance["trade_extension"] = {"draft": True, "base": "services-20261023/inputs-r3",
        "base_files": {p.name: sha(p.read_bytes()) for p in base.iterdir() if p.is_file()},
        "current_sources": {name: sha((text/name).read_bytes()) for name in ("en.tsv", "zh-TW.tsv", "glossary.tsv")},
        "feedback_proof": {"receipt": str(receipt_path.relative_to(traces)), "sha256": sha(receipt_path.read_bytes())},
        "feedback_boundaries": {"receipt": str(boundary_path.relative_to(traces)), "sha256": sha(boundary_path.read_bytes())},
        "formal_templates": templates, "messages": messages, "added": added, "tool_sha256": sha(Path(__file__).read_bytes())}
    output.mkdir()
    for p in base.iterdir():
        if p.is_file() and p.name not in ("inputs.json", "en.tsv", "zh-TW.tsv", "provenance.json", "glyphs-16.json", "font-zh-TW.tsv", "reader-controls.json"):
            (output/p.name).write_bytes(p.read_bytes())
    for name, values in (("en.tsv", en), ("zh-TW.tsv", zh)):
        (output/name).write_text("key\ttext\n"+"".join(f"{k}\t{v}\n" for k,v in values.items()))
    font = catalog(base/"font-zh-TW.tsv"); font.update(zh)
    (output/"font-zh-TW.tsv").write_text("key\ttext\n"+"".join(f"{k}\t{v}\n" for k,v in font.items()))
    (output/"inputs.json").write_text(json.dumps(config,ensure_ascii=False,indent=2)+"\n")
    (output/"provenance.json").write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"new_fields":len(added["fields"]), "message_calls":len(messages), "unique_messages":3, "aliases":len(en)}))


if __name__ == "__main__":
    prepare(*(Path(p) for p in sys.argv[1:]))
