"""由已驗原版標題、正式 TSV 及前作術語建立私有列表原型輸入。"""
import csv
import hashlib
import json
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
        term = [t for t in terms if t["en"] == "Shield" and t["category"] == category]
        assert len(term) == 1 and term[0]["project"] == "death_knight_of_krynn"
        key = pane + ".shield"
        aliases[key], translations[key] = term[0]["en"], term[0]["zh"]
        provenance.append({"pane": pane, "header_catalog_key": source_keys[0] if source_keys else None,
                           "header_source": "formal-en" if source_keys else "observed original RAM NUL format; not registered in main catalog",
                           "header_occurrences": len(matches), "term": term[0],
                           "receipt_sha256": sha((observed / folder / "receipt.json").read_bytes())})
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
    for name, rows in (("en.tsv", aliases), ("zh-TW.tsv", translations)):
        (output / name).write_text("key\ttext\n" + "".join(f"{key}\t{value}\n" for key, value in rows.items()))
    config = {"Headers": headers, "Background": backgrounds.pop(),
              "fine_windows": [[672000000, 673000000], [681000000, 682000000],
                               [699000000, 700000000], [705000000, 706000000],
                               [738000000, 739000000], [741000000, 742000000], [744000000, 745000000]]}
    (output / "inputs.json").write_text(json.dumps(config, indent=2) + "\n")
    (output / "provenance.json").write_text(json.dumps({"draft": True, "bindings": provenance,
        "formal_en_sha256": sha((texts / "en.tsv").read_bytes()),
        "formal_zh_sha256": sha((texts / "zh-TW.tsv").read_bytes()),
        "glossary_sha256": sha((texts / "glossary.tsv").read_bytes()),
        "tool_sha256": sha(Path(__file__).read_bytes())}, ensure_ascii=False, indent=2) + "\n")
    print("列表原型輸入：兩個標題來源、兩個繁中詞條；未改正式譯表")


if __name__ == "__main__":
    prepare(*map(Path, sys.argv[1:4]))
