"""主線 Quick 續行的名稱、回報及代表性畫格。入口見規格 001。"""
import base64
import copy
import csv
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile

from PIL import Image
from empty_notice_inputs import catalog, read, sha, write

PARENT = "choice-prompt-20261025/inputs-r1"
MENU = "326aacadb1a01c55f2e08f88cd3fc3ce209f7cfb0826f53439bd66558839a4dc"
NAMES = ("name.ec48f92529153b54d99a", "name.1ed983b04da092ad444e")
GUARD = "ui.0323473424f14da356d4"
DYING = "round.3639be1dab675907c6bf"
DAMAGE = "hud-format.66e294009f6a0a6b1d62"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def prepare(root, out):
    probe = root / "workplace/probe"
    native, control = [read(out / (name + "-r1/receipt.json")) for name in ("observe", "control")]
    assert native["checkpoints"] == control["checkpoints"]
    assert sha(out / "observe-r1/final.state") == sha(out / "control-r1/final.state")
    target = out / "inputs-r1"
    assert not target.exists()
    shutil.copytree(probe / PARENT, target)
    cfg = read(target / "inputs.json")
    en, zh = [catalog(target / name) for name in ("en.tsv", "zh-TW.tsv")]
    formal_en, formal_zh = [catalog(root / "workplace/translation" / name) for name in ("en.tsv", "zh-TW.tsv")]
    for key in (*NAMES, GUARD):
        assert key not in en and key not in zh
        en[key], zh[key] = formal_en[key], formal_zh[key]
    assert all(set(zh[key]) <= read(target / "glyphs-16.json")["glyphs"].keys() for key in (*NAMES, GUARD))
    terms = {}
    for directory, key, source in (("/previous", NAMES[0], "Sivak"), ("/champions", NAMES[1], "Bozak")):
        path = Path(directory) / "glossary.tsv"
        rows = list(csv.DictReader(path.open(), delimiter="\t"))
        matches = [r for r in rows if r["en"].casefold() == source.casefold()]
        assert len(matches) == 1 and matches[0]["zh"] == zh[key]
        terms[key] = dict(path=str(path), sha256=sha(path), row=matches[0])
    fields, sources = [], []
    wanted = {en[key]: key for key in (*NAMES, GUARD)}
    for call in native["calls"]:
        text = call["vararg_1_candidate"]["text"]
        if call["format"]["text"] != "%s" or text not in wanted:
            continue
        key = wanted[text]
        wrapper = native["wrappers"][call["wrapper_index"]]
        assert call["caller"] == dict(Seg=0xb72, Off=0x27c)
        assert wrapper["format"]["text"] == "%s" and wrapper["step"] < call["step"] < call["first_glyph"] < call["return_step"]
        x, y = [int(v & 255) * 8 for v in wrapper["stack"][2:4]]
        if key in NAMES:
            assert wrapper["caller"] == dict(Seg=0x88e, Off=0x16fb)
            assert call["stack"][3:5] == [8092, 130] and x == 184 and y in (8, 80)
            field = dict(Pane="callsite", Group="body", Key=key, Start=0, Length=len(text),
                 SHA256=digest(text), FormatSHA256=digest("%s"), Caller=call["caller"], UpperCaller=wrapper["caller"],
                 UpperFormatSHA256=digest("%s"), UpperNative=[x, y], RawX=8092, RawY=call["stack"][2], Color=130, BackgroundOverride=23)
        else:
            assert wrapper["caller"] == dict(Seg=0x88e, Off=0x1560) and [x, y] == [0, 192]
            assert wrapper["menu_valid"] and wrapper["menu_snapshot"]["Signature"] == MENU
            assert call["stack"][2:5] == [189, 8004, 143]
            field = dict(Pane="callsite", Group="footer", Key=key, Start=0, Length=len(text),
                 SHA256=digest(text), FormatSHA256=digest("%s"), Caller=call["caller"], UpperCaller=wrapper["caller"],
                 UpperFormatSHA256=digest("%s"), UpperNative=[x, y], RawX=8004, RawY=189, Color=143, MenuSignature=MENU)
        fields.append(field)
        sources.append(dict(field=field, call=call, wrapper=wrapper))
    assert len(fields) == 4 and {f["Key"] for f in fields} == set((*NAMES, GUARD))
    cfg["Fields"].extend(fields)
    dying = next(p for p in native["paragraphs"] if p["source"]["text"] == en[DYING])
    assert dying["native_box"] == [184, 120, 312, 176] and dying["menu_snapshot"]["Signature"] == MENU
    old = next(p for p in cfg["HUDParagraphs"] if p["Spans"][0]["Key"] == DYING)
    binding = copy.deepcopy(old)
    binding["NativeBox"] = dying["native_box"]
    binding["Spans"][0]["Rect"] = [184, 120, 128, 56]
    cfg["HUDParagraphs"].append(binding)
    cfg["fine_windows"] = []
    for source in sources:
        for step in (source["wrapper"]["step"], source["call"]["step"], source["call"]["first_glyph"], source["call"]["return_step"]):
            cfg["fine_windows"].append([step - 2000, step + 4000])
    for i, paragraph in enumerate(native["paragraphs"]):
        if paragraph["source"]["text"] == " ":
            continue
        calls = [c for c in native["calls"] if c["paragraph_index"] == i]
        assert calls and paragraph["menu_snapshot"]["Signature"] == MENU
        for step in (paragraph["step"], calls[0]["first_glyph"], paragraph["return_step"]):
            cfg["fine_windows"].append([step - 2000, step + 4000])
    write(target / "inputs.json", cfg)
    for name, values in (("en.tsv", en), ("zh-TW.tsv", zh)):
        (target / name).write_text("key\ttext\n" + "".join(k + "\t" + v + "\n" for k, v in sorted(values.items())))
    write(out / "bindings.json", dict(fields=sources, dying=dying, dying_binding=binding, terms=terms))
    provenance = read(target / "provenance.json")
    provenance["battle_continuation"] = dict(parent=PARENT, binding_sha256=sha(out / "bindings.json"),
             en_sha256=sha(target / "en.tsv"), zh_sha256=sha(target / "zh-TW.tsv"))
    write(target / "provenance.json", provenance)
    print("two monster names, Guarding, dying row120; existing numeric template retained")


def check(root, out):
    native, control = [read(out / (name + "-r1/receipt.json")) for name in ("observe", "control")]
    assert native["checkpoints"] == control["checkpoints"]
    assert sha(out / "observe-r1/final.state") == sha(out / "control-r1/final.state")
    en, zh = [read(out / lang / "receipt.json") for lang in ("en-r2", "zh-r2")]
    for run in (en, zh):
        assert not run["unimplemented"] and run["initial_state_sha256"] == native["state_sha256"]
        assert run["list_inputs_sha256"] == sha(out / "inputs-r1/inputs.json")
        assert run["list_request_sha256"] == sha(out / "request-r1.json")
        assert len(run["checkpoints"]) == len(control["checkpoints"])
        for actual, expected in zip(run["checkpoints"], control["checkpoints"]):
            for key in ("regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes", "step", "label"):
                assert actual[key] == expected[key], key
            assert not actual["file_writes"]
    for proof in read(out / "bindings.json")["fields"]:
        call = proof["call"]
        event = next(e for e in zh["list_events"] if e["Kind"] == "field-before-glyph" and e["Step"] == call["step"])
        assert event["Step"] < event["first_glyph"] == call["first_glyph"] < call["return_step"]
        assert event["detail"]["word"]["Key"] == proof["field"]["Key"]
    unknown = [e for e in zh["list_events"] if e["Kind"] == "unknown-paragraph-original"]
    assert [e["Step"] for e in unknown] == [p["step"] for p in native["paragraphs"] if p["source"]["text"] == " "]
    hud_events = [e for e in zh["list_events"] if e["Kind"] == "hud-before-glyph"]
    paragraphs = [(i, p) for i, p in enumerate(native["paragraphs"]) if p["source"]["text"] != " "]
    assert len(hud_events) == len(paragraphs) == 4
    for event, (index, paragraph) in zip(hud_events, paragraphs):
        call = next(c for c in native["calls"] if c["paragraph_index"] == index)
        assert event["Step"] == paragraph["step"] < event["first_glyph"] == call["first_glyph"] < paragraph["return_step"]
    glyphs = read(out / "inputs-r1/glyphs-16.json")["glyphs"]
    masks = {k: Image.frombytes("L", (16, 20), base64.b64decode(v)) for k, v in glyphs.items()}
    translations = catalog(out / "inputs-r1/zh-TW.tsv")
    assert [f["step"] for f in en["frames"]] == [f["step"] for f in zh["frames"]]
    assert len(zh["frames"]) == len(zh["list_frames"])
    visible = {key: 0 for key in (*NAMES, GUARD, DYING, DAMAGE)}
    examples = {}
    held = after_guard = bonus = 0
    previous = None
    guard_call = next(p["call"] for p in read(out / "bindings.json")["fields"] if p["field"]["Key"] == GUARD)
    actor = next(c for c in native["calls"] if c["format"]["text"] == "%s" and c["vararg_1_candidate"]["text"] == "JORIS THE WISE" and c["stack"][2:4] == [8004, 8092])
    cps = {c["step"]: c for c in control["checkpoints"]}
    for a, b, meta in zip(en["frames"], zh["frames"], zh["list_frames"]):
        english, chinese = [Image.open(out / lang / frame["File"]).convert("RGB") for lang, frame in (("en-r2", a), ("zh-r2", b))]
        for frame, im in ((a, english), (b, chinese)):
            assert hashlib.sha256(im.convert("RGBA").tobytes()).hexdigest() == frame["SHA256"]
        if a["step"] in cps:
            original = Image.open(out / "control-r1" / (cps[a["step"]]["label"] + ".png")).convert("RGB")
            assert english.tobytes() == original.resize((640, 400), Image.Resampling.NEAREST).tobytes()
        assert not meta["paragraph"] and not meta["reader"]
        if b["held"]:
            assert previous is not None and b["SHA256"] == previous["SHA256"]
            held += 1
        else:
            expected = english.copy()
            for word in meta["words"] or []:
                x, y, width, height = [word.get(k, 8) * 2 for k in ("X", "Y", "Width", "Height")]
                bg, fg = [tuple(meta["palette"][word[k]]) for k in ("Background", "Foreground")]
                expected.paste(bg, (x, y, x + width, y + height))
                text = translations[word["Key"]]
                if "Number" in word:
                    text = text.replace("%d", str(word["Number"]))
                assert len(text) * 16 <= width
                for i, char in enumerate(text):
                    expected.paste(fg, (x + i * 16, y, x + (i + 1) * 16, y + 20), masks[char])
                if word["Key"] in visible:
                    visible[word["Key"]] += 1
                    examples[word["Key"]] = b["File"]
                if word["Key"] == DAMAGE:
                    assert word["Number"] == 9
            assert chinese.tobytes() == expected.tobytes(), (b["step"], "composition")
            if any(w["Y"] == 64 and w["Width"] == 24 for w in meta["words"] or []):
                assert chinese.crop((416, 128, 624, 144)).tobytes() == english.crop((416, 128, 624, 144)).tobytes()
                bonus += 1
            if b["step"] > actor["return_step"]:
                assert not [w for w in meta["words"] or [] if w["Key"] in NAMES and w["Y"] == 8], "old monster name on party member"
            if b["step"] > guard_call["return_step"] and visible[GUARD] and not any(w["Key"] == GUARD for w in meta["words"] or []):
                after_guard += 1
        previous = b
    assert all(visible.values()) and after_guard > 0 and bonus > 0, visible
    parent = root / "workplace/probe" / PARENT
    for p in parent.iterdir():
        if p.is_file() and p.name not in ("inputs.json", "en.tsv", "zh-TW.tsv", "provenance.json"):
            assert sha(p) == sha(out / "inputs-r1" / p.name), p.name
    for p in (out / "programs-r2").glob("*.go"):
        assert sha(p) == sha(root / "tools" / p.name), p.name
    write(out / "check.json", dict(original_state_equal=True, gpu_pairs=len(zh["frames"]), native_checkpoints=len(control["checkpoints"]),
          held=held, visible=visible, guard_removed_samples=after_guard, preserved_bonus_samples=bonus,
          source_before_glyph=True, new_field_sources=4, hud_sources=4, examples=examples,
          source=len(catalog(out / "inputs-r1/en.tsv")), translated=len(translations),
          next_state_sha256=sha(out / "control-r1/final.state"), next_steps=15786000000,
          scope="正常戰鬥100M續行，兩種龍人、守衛、魔法傷害9及垂死；不代表整場勝利或全遊戲完成。"))
    print(read(out / "check.json"))


def rebuild(root, out):
    with tempfile.TemporaryDirectory(prefix="rebuild-", dir=out) as directory:
        fresh = Path(directory)
        for name in ("observe-r1", "control-r1"):
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
    assert not (out / "evidence.json").exists()
    probe = root / "workplace/probe"
    sources = list((probe / PARENT).iterdir())
    sources.extend(root / name for name in ("workplace/translation/en.tsv", "workplace/translation/zh-TW.tsv", "workplace/input/dos/drkqueen/DQK.EXE", "workplace/probe/weapon-hud-20261025/control-r5/final.state", "workplace/probe/combat-aim-route-20261024/programs-r3/ui-context-probe"))
    snapshots = out / "tool-snapshots"
    snapshots.mkdir()
    for name in ("battle_continuation_inputs.py", "empty_notice_inputs.py"):
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
