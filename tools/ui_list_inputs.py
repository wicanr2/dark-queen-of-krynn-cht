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


def prepare(texts, observed, output):
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
            rows.append({"Pane": pane, "SHA256": sha(text.encode()), "Spans": spans})
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
    output.mkdir()
    for name, strings in (("en.tsv", aliases), ("zh-TW.tsv", translations)):
        (output / name).write_text("key\ttext\n" + "".join(f"{key}\t{value}\n" for key, value in strings.items()))
    config = {"Headers": headers, "Rows": rows, "Background": backgrounds.pop(),
              "fine_windows": [[672000000, 673000000], [681000000, 682000000],
                               [699000000, 700000000], [705000000, 706000000],
                               [738000000, 739000000], [741000000, 742000000], [744000000, 745000000]]}
    (output / "inputs.json").write_text(json.dumps(config, indent=2) + "\n")
    (output / "provenance.json").write_text(json.dumps({"draft": True, "headers": provenance, "bindings": bindings,
        "observed_rows": len(rows),
        "formal_en_sha256": sha((texts / "en.tsv").read_bytes()),
        "formal_zh_sha256": sha((texts / "zh-TW.tsv").read_bytes()),
        "glossary_sha256": sha((texts / "glossary.tsv").read_bytes()),
        "tool_sha256": sha(Path(__file__).read_bytes())}, ensure_ascii=False, indent=2) + "\n")
    print(f"列表原型輸入：{len(rows)} 種完整列、{len(translations)} 個顯示詞條；未改正式譯表")


if __name__ == "__main__":
    prepare(*map(Path, sys.argv[1:4]))
