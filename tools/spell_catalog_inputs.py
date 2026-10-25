"""法術名稱與施法提示的共用資料；保留原版次數，只抽正常清單及戰鬥。"""
import base64
import csv
import hashlib
from pathlib import Path
import re
import shutil
import sys
import tempfile

from PIL import Image
from empty_notice_inputs import catalog, read, sha, write

PARENT = "combat-names-20261025/inputs-r1"
BATTLE = "battle-continuation-20261025"
TEMPLATE = "ui.0eab976d6f20cabc5ca7"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def derive(root):
    parent = root / "workplace/probe" / PARENT
    cfg = read(parent / "inputs.json")
    en, zh = [catalog(parent / name) for name in ("en.tsv", "zh-TW.tsv")]
    old_keys = set(en)
    formal = root / "workplace/translation"
    formal_en, formal_zh = [catalog(formal / name) for name in ("en.tsv", "zh-TW.tsv")]
    with (formal / "glossary.tsv").open() as stream:
        terms = {}
        for row in csv.DictReader(stream, delimiter="\t"):
            if row["category"] == "spell":
                name = row["en"].casefold()
                if name in terms:
                    assert terms[name]["zh"] == row["zh"]
                else:
                    terms[name] = row
    metadata = read(formal / "catalog.json")
    executable = root / "workplace/input/dos/drkqueen/DQK.EXE"
    raw = executable.read_bytes()
    assert sha(executable) == next(r["sha256"] for r in metadata["inputs"] if r["path"] == "DQK.EXE")
    names = [r for r in metadata["entries"] if r["domain"] == "ui" and r["text"].casefold() in terms]
    assert len(names) == 113
    glyphs = read(parent / "glyphs-16.json")["glyphs"]
    assert formal_en[TEMPLATE].count("%s") == formal_zh[TEMPLATE].count("%s") == 1
    records, row_additions, color_updates, caption_additions = [], [], [], []
    for source in names:
        name, key = source["text"], "grimoire." + source["sha256"][:20]
        term = terms[name.casefold()]
        assert digest(name) == source["sha256"] and formal_en[source["key"]] == name
        assert len(term["zh"]) <= len(name) and set(term["zh"]) <= glyphs.keys()
        for origin in source["sources"]:
            assert origin["file"] == "DQK.EXE"
            offset = origin["file_offset"]
            assert raw[offset:offset + len(name) + 1] == name.encode("ascii") + b"\x00"
        if key in en:
            assert en[key] == name and zh[key] == term["zh"]
        else:
            en[key], zh[key] = name, term["zh"]
        row = dict(Pane="grimoire", SHA256=digest("\t" + name),
                   Spans=[dict(Start=1, Length=len(name), Key=key)], Foregrounds=[7, 11, 12])
        previous = next((r for r in cfg["Rows"] if r["Pane"] == "grimoire" and r["SHA256"] == row["SHA256"]), None)
        if previous:
            assert previous["Spans"] == row["Spans"] and set(previous["Foregrounds"]) <= {7, 11, 12}
            if previous["Foregrounds"] != row["Foregrounds"]:
                color_updates.append(dict(sha256=row["SHA256"], previous=list(previous["Foregrounds"])))
                previous["Foregrounds"] = row["Foregrounds"]
        else:
            cfg["Rows"].append(row)
            row_additions.append(row)
        caption = formal_en[TEMPLATE].replace("%s", name)
        translated = formal_zh[TEMPLATE].replace("%s", term["zh"])
        assert len(caption) <= 38 and len(translated) <= len(caption) and set(translated) <= glyphs.keys()
        field = dict(Pane="callsite", Group="footer", Start=0, Length=len(caption), SHA256=digest(caption),
              FormatSHA256=digest("%s"), Caller=dict(Seg=0xb72, Off=0x27c), UpperCaller=dict(Seg=0x2c4a, Off=0x4630),
              RawX=8004, RawY=8089, Color=143, UpperNative=[0, 184])
        matches = [f for f in cfg["Fields"] if all(f.get(k) == v for k, v in field.items())]
        assert len(matches) <= 1
        if matches:
            caption_key = matches[0]["Key"]
            assert en[caption_key] == caption and zh[caption_key] == translated
        else:
            caption_key = "fire-spell." + digest(caption)[:20]
            assert caption_key not in en
            en[caption_key], zh[caption_key] = caption, translated
            field["Key"] = caption_key
            cfg["Fields"].append(field)
            caption_additions.append(field)
        records.append(dict(source=source, term=term, row_key=key, caption_key=caption_key))
    assert len(row_additions) == 68 and len(caption_additions) == 107
    return cfg, en, zh, dict(records=records, row_additions=row_additions, color_updates=color_updates,
                    caption_additions=caption_additions, new_keys=sorted(set(en) - old_keys))


def prepare(root, out):
    cfg, en, zh, data = derive(root)
    a, b = [read(out / ("book-" + mode) / "receipt.json") for mode in ("observe", "control")]
    assert a["checkpoints"] == b["checkpoints"] and sha(out / "book-observe/final.state") == sha(out / "book-control/final.state")
    old = read(root / "workplace/probe/combat-spells-route-20261024/control-r6/receipt.json")
    assert a["checkpoints"][:2] == old["checkpoints"][:2]
    calls = [c for c in a["calls"] if c["format"]["text"] == "%s" and c["vararg_1_candidate"]["text"].startswith("\t")]
    assert calls
    for call in calls:
        for step in (call["step"], call["first_glyph"], call["return_step"]):
            cfg["fine_windows"].append([step - 2000, step + 4000])
    target = out / "inputs-r1"
    assert not target.exists()
    shutil.copytree(root / "workplace/probe" / PARENT, target)
    write(target / "inputs.json", cfg)
    for name, values in (("en.tsv", en), ("zh-TW.tsv", zh)):
        (target / name).write_text("key\ttext\n" + "".join(k + "\t" + v + "\n" for k, v in sorted(values.items())))
    write(out / "bindings.json", data)
    provenance = read(target / "provenance.json")
    provenance["spell_catalog_extension"] = dict(parent=PARENT, binding_sha256=sha(out / "bindings.json"),
              en_sha256=sha(target / "en.tsv"), zh_sha256=sha(target / "zh-TW.tsv"))
    write(target / "provenance.json", provenance)
    shutil.copyfile(root / "workplace/probe" / BATTLE / "request-r1.json", out / "battle-request.json")
    print("113 source spellings; new rows", len(data["row_additions"]), "captions", len(data["caption_additions"]),
          "color updates", len(data["color_updates"]), "catalog keys", len(data["new_keys"]))


def check(root, out):
    cfg, en, zh, data = derive(root)
    actual = read(out / "inputs-r1/inputs.json")
    assert {k: v for k, v in cfg.items() if k != "fine_windows"} == {k: v for k, v in actual.items() if k != "fine_windows"}
    assert data == read(out / "bindings.json")
    for p in (root / "workplace/probe" / PARENT).iterdir():
        if p.is_file() and p.name not in ("inputs.json", "en.tsv", "zh-TW.tsv", "provenance.json"):
            assert sha(p) == sha(out / "inputs-r1" / p.name), p.name
    glyphs = read(out / "inputs-r1/glyphs-16.json")["glyphs"]
    masks = {k: Image.frombytes("L", (16, 20), base64.b64decode(v)) for k, v in glyphs.items()}
    spell_keys = {r["row_key"] for r in data["records"]}
    results = {}
    for case in ("book", "battle"):
        native_root = out if case == "book" else root / "workplace/probe" / BATTLE
        native = read(native_root / ("book-observe" if case == "book" else "observe-r1") / "receipt.json")
        control_dir = native_root / ("book-control" if case == "book" else "control-r1")
        control = read(control_dir / "receipt.json")
        assert native["checkpoints"] == control["checkpoints"]
        a, b = [read(out / (case + "-" + lang) / "receipt.json") for lang in ("en", "zh")]
        for run in (a, b):
            assert not run["unimplemented"] and run["initial_state_sha256"] == native["state_sha256"]
            assert run["list_inputs_sha256"] == sha(out / "inputs-r1/inputs.json")
            assert run["list_request_sha256"] == sha(out / (case + "-request.json"))
            assert len(run["checkpoints"]) == len(control["checkpoints"])
            for cp, expected in zip(run["checkpoints"], control["checkpoints"]):
                for key in ("regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes", "step", "label"):
                    assert cp[key] == expected[key], (case, key)
                assert not cp["file_writes"]
        suffix_records = []
        if case == "book":
            events = {e["Step"]: e for e in b["list_events"] if e["Kind"] == "row-before-glyph"}
            row_calls = []
            for call in native["calls"]:
                text = call["vararg_1_candidate"]["text"]
                if call["format"]["text"] == "%s" and text.startswith("\t") and call["wrapper_index"] >= 0:
                    wrapper = native["wrappers"][call["wrapper_index"]]
                    row_calls.append((call, wrapper, text))
            for call, wrapper, text in row_calls:
                match = re.fullmatch(r"\t(.+) \(([1-9][0-9]*)\)", text)
                if not match:
                    continue
                key = "grimoire." + digest(match[1])[:20]
                assert key in spell_keys and en[key] == match[1]
                event = events[wrapper["step"]]
                assert event["Step"] < call["step"] < event["first_glyph"] == call["first_glyph"] < call["return_step"]
                assert event["Pane"] == "grimoire" and event["detail"]["source_sha256"] == digest(text)
                assert event["detail"]["spans"] == [dict(Start=1, Length=len(match[1]), Key=key)]
                col, row = [v & 255 for v in wrapper["stack"][2:4]]
                later = [w["step"] for c, w, t in row_calls if w["step"] > wrapper["step"] and
                         [v & 255 for v in w["stack"][2:4]] == [col, row]]
                suffix_records.append(dict(key=key, source=text, entry=wrapper["step"], start=wrapper["return_step"],
                    end=min(later) if later else 2**64, x=(col + 1) * 8, y=row * 8, width=len(match[1]) * 8,
                    suffix_width=(len(match[2]) + 3) * 8, samples=0))
            assert suffix_records
        else:
            calls = [c for c in native["calls"] if c["format"]["text"] == "%s" and c["vararg_1_candidate"]["text"].startswith("Spell:")]
            assert calls
            for call in calls:
                event = next(e for e in b["list_events"] if e["Kind"] == "field-before-glyph" and e["Step"] == call["step"])
                assert event["Step"] < event["first_glyph"] == call["first_glyph"] < call["return_step"]
        assert [f["step"] for f in a["frames"]] == [f["step"] for f in b["frames"]]
        assert len(b["frames"]) == len(b["list_frames"])
        cps = {c["step"]: c for c in control["checkpoints"]}
        held = visible_rows = visible_caption = count_suffixes = 0
        examples = {}
        previous = None
        for x, y, meta in zip(a["frames"], b["frames"], b["list_frames"]):
            english, chinese = [Image.open(out / (case + "-" + lang) / f["File"]).convert("RGB") for lang, f in (("en", x), ("zh", y))]
            for frame, im in ((x, english), (y, chinese)):
                assert hashlib.sha256(im.convert("RGBA").tobytes()).hexdigest() == frame["SHA256"]
            if x["step"] in cps:
                expected = Image.open(control_dir / (cps[x["step"]]["label"] + ".png")).convert("RGB")
                assert english.tobytes() == expected.resize((640, 400), Image.Resampling.NEAREST).tobytes()
            assert not meta["paragraph"] and not meta["reader"]
            if y["held"]:
                assert previous is not None and y["SHA256"] == previous["SHA256"]
                held += 1
            else:
                expected = english.copy()
                for word in meta["words"] or []:
                    xx, yy, width, height = [word.get(k, 8) * 2 for k in ("X", "Y", "Width", "Height")]
                    bg, fg = [tuple(meta["palette"][word[k]]) for k in ("Background", "Foreground")]
                    expected.paste(bg, (xx, yy, xx + width, yy + height))
                    text = zh[word["Key"]]
                    if "Number" in word:
                        text = text.replace("%d", str(word["Number"]))
                    assert len(text) * 16 <= width
                    for i, char in enumerate(text):
                        expected.paste(fg, (xx + i * 16, yy, xx + (i + 1) * 16, yy + 20), masks[char])
                    if word["Key"] in spell_keys:
                        visible_rows += 1
                        examples["rows"] = y["File"]
                        for record in suffix_records:
                            if record["key"] == word["Key"] and record["start"] <= y["step"] < record["end"] and \
                               [word["X"], word["Y"], word["Width"]] == [record["x"], record["y"], record["width"]]:
                                left, top = (record["x"] + record["width"]) * 2, record["y"] * 2
                                rect = (left, top, left + record["suffix_width"] * 2, top + 16)
                                assert chinese.crop(rect).tobytes() == english.crop(rect).tobytes()
                                assert len(set(english.crop(rect).getdata())) > 1
                                record["samples"] += 1
                                count_suffixes += 1
                    if en[word["Key"]].startswith("Spell:"):
                        visible_caption += 1
                        examples["caption"] = y["File"]
                assert chinese.tobytes() == expected.tobytes(), (case, y["step"], "composition")
            previous = y
        if case == "book":
            assert visible_rows > 0
            assert {r["source"] for r in suffix_records if r["samples"]} == {r["source"] for r in suffix_records}
            assert not any(w["Key"].startswith("grimoire.") for w in b["final_words"])
            assert not [e for e in b["list_events"] if e["Kind"] == "unknown-row-original"]
            last_button = [c for c in native["calls"] if c["caller"] == dict(Seg=0xceb, Off=0x1be)][-1]
            signature = native["menus"][last_button["menu_index"]]["Signature"]
            expected_buttons = {f["Key"] for f in actual["Fields"] if f["Pane"] == "menu" and f.get("MenuSignature") == signature}
            assert expected_buttons and {w["Key"] for w in b["final_words"] if w.get("Button")} == expected_buttons
            write(out / "count-suffix-check.json", dict(records=suffix_records, preserved_samples=count_suffixes))
        else:
            assert visible_caption > 0
            parent = root / "workplace/probe" / BATTLE
            for language, run in (("en", a), ("zh", b)):
                old = read(parent / (language + "-r2/receipt.json"))
                assert run["frames"] == old["frames"] and run["list_frames"] == old["list_frames"]
        results[case] = dict(gpu_pairs=len(b["frames"]), native_checkpoints=len(control["checkpoints"]),
                 held=held, visible_rows=visible_rows, visible_caption=visible_caption,
                 original_count_suffix_samples=count_suffixes, examples=examples)
    for p in (out / "programs-r1").glob("*.go"):
        assert sha(p) == sha(root / "tools" / p.name), p.name
    write(out / "check.json", dict(original_state_equal=True, names=113, normalized_names=len({r["source"]["text"].casefold() for r in data["records"]}),
          new_rows=len(data["row_additions"]), new_captions=len(data["caption_additions"]),
          source=len(en), translated=len(zh), glyphs_unchanged=True, cases=results,
          scope="113筆名稱來源、清單與提示資料；正常抽法術清單次數及主線魔法飛彈，未逐一施放113筆來源。"))
    print(read(out / "check.json"))


def rebuild(root, out):
    with tempfile.TemporaryDirectory(prefix="rebuild-", dir=out) as directory:
        fresh = Path(directory)
        for name in ("book-observe", "book-control"):
            (fresh / name).mkdir()
            for file in ("receipt.json", "final.state"):
                shutil.copyfile(out / name / file, fresh / name / file)
        prepare(root, fresh)
        for p in (out / "inputs-r1").iterdir():
            if p.is_file():
                assert sha(p) == sha(fresh / "inputs-r1" / p.name), p.name
        assert sha(out / "bindings.json") == sha(fresh / "bindings.json")
    write(out / "rebuild.json", dict(input_files=18, all_inputs_equal=True))


def seal(root, out):
    assert read(out / "check.json")["original_state_equal"] and read(out / "rebuild.json")["all_inputs_equal"]
    assert "PASS" in (out / "spell-row-tests.log").read_text() and not (out / "evidence.json").exists()
    probe = root / "workplace/probe"
    sources = list((probe / PARENT).iterdir())
    sources.extend(probe / BATTLE / name for name in ("observe-r1/receipt.json", "control-r1/receipt.json", "request-r1.json"))
    sources.extend(root / name for name in ("workplace/translation/en.tsv", "workplace/translation/zh-TW.tsv", "workplace/translation/catalog.json", "workplace/translation/glossary.tsv", "workplace/input/dos/drkqueen/DQK.EXE", "workplace/probe/weapon-hud-20261025/control-r5/final.state", "workplace/probe/combat-effects-20261024/observe-r1/final.state", "workplace/probe/combat-spells-route-20261024/control-r6/receipt.json", "workplace/probe/combat-aim-route-20261024/programs-r3/ui-context-probe"))
    snapshots = out / "tool-snapshots"
    snapshots.mkdir()
    for name in ("spell_catalog_inputs.py", "empty_notice_inputs.py", "ui_spell_row_test.go"):
        shutil.copyfile(root / "tools" / name, snapshots / name)
    write(out / "evidence.json", dict(state="SEALED", draft=True, summary=read(out / "check.json"),
          artifacts={str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()},
          sources={str(p.relative_to(root)): sha(p) for p in sources if p.is_file()}))
    audit(root, out)


def audit(root, out):
    index = read(out / "evidence.json")
    assert index["state"] == "SEALED"
    for name, expected in index["artifacts"].items():
        assert sha(out / name) == expected, name
    for name, expected in index["sources"].items():
        assert sha(root / name) == expected, name
    print("sealed", len(index["artifacts"]), "artifacts", len(index["sources"]), "sources")


if __name__ == "__main__":
    mode, project, directory = sys.argv[1:]
    assert mode in ("prepare", "check", "rebuild", "seal", "audit")
    globals()[mode](Path(project), Path(directory))
