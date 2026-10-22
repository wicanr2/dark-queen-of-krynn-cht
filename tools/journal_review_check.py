"""核對手札校讀稿的來源、編號、術語與字型；不宣稱自動驗出譯意正確。"""
import csv
import hashlib
import importlib.metadata
import json
import re
import sys
from pathlib import Path

def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def rows(path, fields):
    raw = path.read_bytes()
    assert b"\r" not in raw and "\ufffd" not in raw.decode("utf-8"), path
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t", quoting=csv.QUOTE_NONE)
        assert reader.fieldnames == fields, (path, reader.fieldnames)
        result = list(reader)
    assert result and all(set(r) == set(fields) and all(r.values()) for r in result), path
    return result


def catalog(path):
    data = rows(path, ["key", "text"])
    result = {row["key"]: row["text"] for row in data}
    assert len(result) == len(data), (path, "重複 key")
    return result


def wrapped(text):
    """只量測既有 38 字格原型的容量，不新增正式分頁規則。"""
    result = []
    for paragraph in text.split(r"\n"):
        if not paragraph:
            result.append("")
            continue
        while paragraph:
            ends = [i for i in range(1, min(38, len(paragraph)) + 1)
                    if i == len(paragraph) or
                    (paragraph[i] not in "，。！？、；：」』）》】" and paragraph[i-1] not in "「『（《【")]
            assert ends, "無安全斷行"
            end = max(ends)
            result.append(paragraph[:end])
            paragraph = paragraph[end:]
    return result


def printed_page(source):
    match = re.fullmatch(r"Image(\d+)-(left|right)\.png", source)
    assert match, source
    return 2 * (int(match[1]) - 47) + (1 if match[2] == "left" else 2)


def chinese_source(page):
    return f"Image{47+(page-1)//2:03d}-{'left' if page % 2 else 'right'}.png"


def check(root, texts, font, merged, output):
    from fontTools.ttLib import TTFont

    assert not output.exists() and not merged.exists(), "輸出必須全新"
    index_path = root / "workplace/paddle-manual/journal-index.json"
    index = json.loads(index_path.read_text())
    ids = set(range(1, 69)) - {13}
    assert {e["id"] for e in index["entries"]} == ids and index["missing_ids"] == [13]
    files = {name: texts / name for name in (
        "journal-book-prose-additions.zh-TW.tsv", "palace-journal54-review.tsv",
        "journal-book-map-labels.zh-TW.tsv", "journal-book-term-bindings.tsv",
        "journal-book-name-candidates.tsv", "journal-book-fragments.zh-TW.tsv")}
    draft = catalog(files["journal-book-prose-additions.zh-TW.tsv"])
    legacy = catalog(files["palace-journal54-review.tsv"])
    assert set(legacy) == {"journal.54.title", "journal.54.body"}
    assert not draft.keys() & legacy.keys()
    combined = {**draft, **legacy}
    visual = {12: "fragment illustration", 25: "map", 64: "map"}
    expected = {f"journal.{i}.title" for i in ids} | {f"journal.{i}.body" for i in ids - visual.keys()}
    assert set(combined) == expected, ("正文與圖文範圍", sorted(expected-combined.keys()), sorted(combined.keys()-expected))
    labels = catalog(files["journal-book-map-labels.zh-TW.tsv"])
    label_ids = {
        25: "lair_baldranous lair_tremor clematra key wall door archway".split(),
        64: "palace great_hall princes_chamber armory temple safe_hall garden forge to_ocean to_celanost key wall door archway".split(),
    }
    assert set(labels) == {f"journal.{i}.label.{key}" for i, keys in label_ids.items() for key in keys}
    fragments = catalog(files["journal-book-fragments.zh-TW.tsv"])
    assert set(fragments) == {f"journal.12.fragment.line{i}" for i in range(1,8)}
    assert all("……" in fragments[f"journal.12.fragment.line{i}"] for i in range(1,7))
    all_text = list(combined.values()) + list(labels.values()) + list(fragments.values())
    for text in all_text:
        plain = text.replace(r"\n", "")
        assert plain and "\\" not in plain and "%" not in plain
        assert all(ord(ch) >= 32 and ord(ch) != 127 for ch in plain)
        for left, right in (("「", "」"), ("『", "』"), ("（", "）")):
            depth = 0
            for ch in plain:
                depth += int(ch == left) - int(ch == right)
                assert depth >= 0, (left, right, plain)
            assert depth == 0, (left, right, plain)
    assert all(len(combined[f"journal.{i}.title"]) <= 37 for i in ids)
    # 必須保留可輸入的五個原文詞，以及原圖已勾選的一項與八項未勾選項目。
    ritual = combined["journal.29.body"].split(r"\n")
    assert [line.split("：", 1)[0] for line in ritual] == ["Limene", "Bilbara", "Shuwara", "Holbani", "Gebene"]
    assert all(len(line.split("：")) == 2 and line.split("：")[1] for line in ritual)
    checklist = combined["journal.52.body"].split(r"\n")
    assert len(checklist) == 9 and checklist[0].startswith("[x] ")
    assert all(line.startswith("[ ] ") for line in checklist[1:])
    assert all(number in combined["journal.50.body"] for number in ("2,976,341", "3,123,882", "8,647", "73", "323", "77"))
    glossary_path = root / "workplace/translation/glossary.tsv"
    with glossary_path.open(encoding="utf-8", newline="") as stream:
        glossary = list(csv.DictReader(stream, delimiter="\t"))
    bindings = rows(files["journal-book-term-bindings.tsv"], ["entries", "en", "zh", "origin", "note"])
    term_matches = []
    for binding in bindings:
        assert binding["origin"] == "glossary"
        matches = [r for r in glossary if r["en"] == binding["en"] and r["zh"] == binding["zh"]]
        assert matches, ("術語來源不符", binding)
        entries = [int(value) for value in binding["entries"].split(",")]
        assert len(entries) == len(set(entries)) and set(entries) <= ids
        for i in entries:
            parts = [value for key, value in {**combined, **labels, **fragments}.items() if key.startswith(f"journal.{i}.")]
            assert binding["zh"] in "".join(parts), ("術語未對齊", i, binding)
        term_matches.append({**binding, "entries": entries, "source": matches})
    candidates = rows(files["journal-book-name-candidates.tsv"], ["en", "zh", "entries", "source", "note"])
    assert len({r["en"] for r in candidates}) == len(candidates)
    for candidate in candidates:
        for value in candidate["entries"].split(","):
            i = int(value)
            assert i in ids and candidate["zh"] in combined.get(f"journal.{i}.body", "") + combined[f"journal.{i}.title"]
    assert sha(font) == "9d5bf4932d31fe94c18cd8cfddc98bc1b14ce10f4e354c682179db290a99c825"
    cmap = TTFont(font).getBestCmap()
    characters = set("".join(all_text).replace(r"\n", ""))
    missing = sorted(ch for ch in characters if ord(ch) not in cmap)
    assert not missing, ("字型缺字", missing)
    # 原版頁碼來自逐頁目視，不能以有錯字、漏標題的英文文字層自動切篇。
    english = {}
    for lo, hi, page in ((1,4,31),(5,8,32),(10,12,33),(14,17,34),(18,21,35),(22,24,36),
                         (25,25,37),(26,30,38),(31,35,39),(36,38,40),(40,43,41),
                         (44,46,42),(48,48,43),(51,53,44),(55,58,45),(59,63,46),(64,64,47),(65,68,48)):
        for i in range(lo, hi+1):
            english[i] = [page]
    english.update({9:[32,33],39:[40,41],47:[42,43],49:[43,44],50:[43,44],54:[44,45]})
    assert set(english) == ids
    entries, scan_hashes = [], {}
    for n, entry in enumerate(index["entries"]):
        i = entry["id"]
        first = printed_page(entry["source"])
        last = 130
        if n+1 < len(index["entries"]):
            following = index["entries"][n+1]
            last = max(first, printed_page(following["source"]) - int(following["region"] <= 1))
        sources = [chinese_source(page) for page in range(first, last+1)]
        for name in sources:
            if name not in scan_hashes:
                scan_hashes[name] = sha(root / "workplace/manual-ocr" / name)
        assert scan_hashes[entry["source"]] == entry["source_sha256"]
        body = combined.get(f"journal.{i}.body")
        lines = wrapped(body) if body is not None else None
        entries.append({"id":i, "kind":visual.get(i, "prose"), "title_key":f"journal.{i}.title",
                        "body_key":f"journal.{i}.body" if body is not None else None,
                        "status":"bilingual draft; editorial review remains" if body is not None else "illustration reconstruction pending",
                        "english_printed_pages":english[i], "english_pdf_indices":sorted({(page+3)//2 for page in english[i]}),
                        "chinese_start_page":first, "chinese_source_pages":sources,
                        "chinese_range_method":"heading index plus next heading region; OCR-based navigation, not a page-content proof",
                        "body_characters":len(body.replace(r"\n", "")) if body is not None else 0,
                        "draft_lines_38_cells":len(lines) if lines is not None else None,
                        "exceeds_single_page_prototype":bool(lines and len(lines)>13)})
    pdf = root / "workplace/input/dqk-english-journal.pdf"
    assert sha(pdf) == "fb31889c508e81d3c32ef44b4d1245ee5aa418335e6f94a11a3361c7a30185aa"
    render_root = root / "workplace/probe/pane-render-20261022"
    sources = {str(path.relative_to(root)):sha(path) for path in (pdf,index_path,glossary_path,
        root/"workplace/translation/en.tsv",root/"workplace/translation/zh-TW.tsv",
        root/"workplace/translation/catalog.json",render_root/"journal-reader-evidence.json",
        render_root/"journal-book-english-raw.json")}
    sources.update({f"workplace/manual-ocr/{name}":value for name,value in scan_hashes.items()})
    sources.update({f"workplace/probe/pane-render-20261022/journal-book-en-{i}.png":sha(render_root/f"journal-book-en-{i}.png") for i in range(17,26)})
    ordered = sorted(combined, key=lambda key:(int(key.split(".")[1]), key.split(".")[2] != "title"))
    merged.write_text("key\ttext\n"+"".join(f"{key}\t{combined[key]}\n" for key in ordered))
    result = {"draft":True,"runtime_integrated":False,"whole_journal_complete":False,
              "titles":len(ids),"prose_drafts":len(ids)-len(visual),"new_prose_drafts":len(ids)-len(visual)-1,
              "visual_entries_pending":visual,"map_labels":len(labels),"fragment_lines":len(fragments),"merged_rows":len(combined),
              "characters":sum(len(t.replace(r"\n", "")) for t in all_text),"unique_characters":len(characters),
              "missing_glyphs":missing,"font_sha256":sha(font),"fonttools_version":importlib.metadata.version("fonttools"),
              "term_bindings":term_matches,"term_binding_occurrences":sum(len(t["entries"]) for t in term_matches),
              "name_candidates":candidates,"input_sha256":{name:sha(path) for name,path in files.items()},
              "source_sha256":sources,"entries":entries,"merged_sha256":sha(merged),"checker_sha256":sha(Path(__file__)),
              "fragment_review":{"entry":12,"scope":"seven visible line groups only; not a completed letter",
                                 "level":"visible wording reviewed; damaged word completions are strong inference; missing text unknown",
                                 "ellipses":"mark gaps; not a reconstruction of exact missing-letter counts or paper geometry",
                                 "source":"Image091-left.png and English printed page 33; no handwritten annotations included"},
              "rights":"User-provided manual derivative and local verification sources; local only, not for Git or distribution",
              "limits":"Checks prove inventory, source identity, selected terms, retained input tokens, checklist state, numeric anchors and glyph coverage. They do not prove every translation choice, whole-journal completion, illustration geometry, game routes or manual-reader integration. Lines only measure the existing disposable 16px prototype; long-page behavior is not defined here."}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({key:result[key] for key in ("titles","prose_drafts","new_prose_drafts","map_labels","fragment_lines","merged_rows","characters","unique_characters","missing_glyphs","term_binding_occurrences")},ensure_ascii=False))
    return result


if __name__ == "__main__":
    check(*map(Path, sys.argv[1:6]))
