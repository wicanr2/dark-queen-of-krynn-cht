"""選項附加問句：既有完整段落的來源核對、接續及進港抽驗。入口見規格 001。"""
import base64
from pathlib import Path
import shutil
import sys
import tempfile

from PIL import Image
from empty_notice_inputs import catalog, read, sha, write

PARENT = "empty-notice-20261025/inputs-r1"
ORACLE = "shared-menu-20261025"
KEY = "ui.ab9e574dc207b6412ef1"
INTRO = ["ecl.536d514499664cd03a55", "ecl.bb39448ea0e98f6b6269", KEY]


def prepare(root, out):
    probe = root / "workplace/probe"
    native = read(probe / ORACLE / "port-entry-observe/receipt.json")
    question = native["paragraphs"][2]
    assert question["source"]["text"] == "what do you do?" and question["source"]["nul_terminated"]
    assert question["caller"] == dict(Seg=0x26b4, Off=0x2022)
    assert question["source"]["segment"] == 0x333e and question["source"]["offset"] == 0x7791
    assert question["native_box"] == [8, 136, 312, 184]
    assert [question[k] for k in ("foreground", "background", "clear")] == [7, 0, 0]
    source = question["source"]["text"]
    import hashlib
    field = dict(Key=KEY, SHA256=hashlib.sha256(source.encode()).hexdigest(), Caller=question["caller"],
                 NativeBox=question["native_box"], Foreground=7, Background=0, Clear=0)
    assert KEY == "ui." + field["SHA256"][:20]
    target = out / "inputs-r1"
    assert not target.exists()
    shutil.copytree(probe / PARENT, target)
    cfg = read(target / "inputs.json")
    assert not any(p["Key"] == KEY for p in cfg["Paragraphs"])
    cfg["Paragraphs"].append(field)
    sources = []
    for i, paragraph in enumerate(native["paragraphs"][:3]):
        calls = [c for c in native["calls"] if c["paragraph_index"] == i]
        assert calls and paragraph["step"] < calls[0]["first_glyph"] < paragraph["return_step"]
        if i < 2:
            assert any(p["Key"] == INTRO[i] and p["Caller"] == paragraph["caller"] and
                       p["Clear"] == paragraph["clear"] for p in cfg["Paragraphs"])
        sources.append(dict(paragraph=paragraph, first_glyph=calls[0]["first_glyph"]))
        for step in (paragraph["step"], calls[0]["first_glyph"], paragraph["return_step"]):
            cfg["fine_windows"].append([step - 2000, step + 4000])
    write(target / "inputs.json", cfg)
    glyphs = read(target / "glyphs-16.json")["glyphs"]
    for name in ("en.tsv", "zh-TW.tsv"):
        values = catalog(target / name)
        assert KEY not in values
        formal = catalog(root / "workplace/translation" / name)
        values[KEY] = formal[KEY]
        if name == "en.tsv":
            assert values[KEY] == source
        else:
            assert set(values[KEY]) <= glyphs.keys()
        (target / name).write_text("key\ttext\n" + "".join(k + "\t" + v + "\n" for k, v in sorted(values.items())))
    old = read(probe / ORACLE / "port-entry-zh-r2/receipt.json")
    failures = [e for e in old["list_events"] if e["Kind"] == "unknown-paragraph-original" and e["Step"] == question["step"]]
    assert len(failures) == 1 and failures[0]["detail"]["reason"] == "source or context mismatch"
    old_frames = [m for f, m in zip(old["frames"], old["list_frames"]) if not f["held"] and
                  question["return_step"] < f["step"] < 5187000000]
    assert old_frames and all(m["paragraph"] is None for m in old_frames)
    write(out / "binding.json", dict(field=field, sources=sources, old_fallback=failures[0], old_original_frames=len(old_frames)))
    provenance = read(target / "provenance.json")
    provenance["choice_prompt_extension"] = dict(parent=PARENT, binding_sha256=sha(out / "binding.json"),
         en_sha256=sha(target / "en.tsv"), zh_sha256=sha(target / "zh-TW.tsv"))
    write(target / "provenance.json", provenance)
    shutil.copyfile(probe / ORACLE / "port-entry-request.json", out / "request.json")
    print("existing full intro confirmed; one missing append prompt binding")


def check(root, out):
    probe = root / "workplace/probe"
    native, control = [read(probe / ORACLE / ("port-entry-" + name) / "receipt.json") for name in ("observe", "control")]
    assert native["checkpoints"] == control["checkpoints"]
    en, zh = [read(out / language / "receipt.json") for language in ("en", "zh")]
    for run in (en, zh):
        assert not run["unimplemented"] and run["initial_state_sha256"] == native["state_sha256"]
        assert run["list_inputs_sha256"] == sha(out / "inputs-r1/inputs.json")
        assert run["list_request_sha256"] == sha(out / "request.json")
        assert len(run["checkpoints"]) == len(control["checkpoints"])
        for actual, expected in zip(run["checkpoints"], control["checkpoints"]):
            for key in ("regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes", "step", "label"):
                assert actual[key] == expected[key], key
            assert not actual["file_writes"]
    events = [e for e in zh["list_events"] if e["Kind"] == "paragraph-before-glyph"]
    assert len(events) == len(native["paragraphs"])
    for i, (event, paragraph) in enumerate(zip(events, native["paragraphs"])):
        first = next(c["first_glyph"] for c in native["calls"] if c["paragraph_index"] == i)
        assert event["Step"] == paragraph["step"] < event["first_glyph"] == first < paragraph["return_step"]
    assert not [e for e in zh["list_events"] if e["Kind"] == "unknown-paragraph-original"]
    parent = probe / PARENT
    for p in parent.iterdir():
        if p.is_file() and p.name not in ("inputs.json", "en.tsv", "zh-TW.tsv", "provenance.json"):
            assert sha(p) == sha(out / "inputs-r1" / p.name), p.name
    for p in (out / "programs-r1").glob("*.go"):
        assert sha(p) == sha(root / "tools" / p.name), p.name
    glyphs = read(out / "inputs-r1/glyphs-16.json")["glyphs"]
    masks = {k: Image.frombytes("L", (16, 20), base64.b64decode(v)) for k, v in glyphs.items()}
    translations = catalog(out / "inputs-r1/zh-TW.tsv")
    assert [f["step"] for f in en["frames"]] == [f["step"] for f in zh["frames"]]
    assert len(zh["frames"]) == len(zh["list_frames"])
    cps = {c["step"]: c for c in control["checkpoints"]}
    held = visible = buttons = after = 0
    previous = example = None
    import hashlib
    for a, b, meta in zip(en["frames"], zh["frames"], zh["list_frames"]):
        english, chinese = [Image.open(out / name / frame["File"]).convert("RGB") for name, frame in (("en", a), ("zh", b))]
        for frame, im in ((a, english), (b, chinese)):
            assert hashlib.sha256(im.convert("RGBA").tobytes()).hexdigest() == frame["SHA256"]
        if a["step"] in cps:
            original = Image.open(probe / ORACLE / "port-entry-control" / (cps[a["step"]]["label"] + ".png")).convert("RGB")
            assert english.tobytes() == original.resize((640, 400), Image.Resampling.NEAREST).tobytes()
        assert not meta["reader"]
        if b["held"]:
            assert previous is not None and b["SHA256"] == previous["SHA256"]
            held += 1
        else:
            expected = english.copy()
            for w in meta["words"] or []:
                x, y, width, height = [w.get(k, 8) * 2 for k in ("X", "Y", "Width", "Height")]
                bg, fg = [tuple(meta["palette"][w[k]]) for k in ("Background", "Foreground")]
                expected.paste(bg, (x, y, x + width, y + height))
                text = translations[w["Key"]]
                assert len(text) * 16 <= width
                for i, char in enumerate(text):
                    expected.paste(fg, (x + i * 16, y, x + (i + 1) * 16, y + 20), masks[char])
            page = meta["paragraph"]
            if page:
                assert not page.get("Prefix") and page["Box"] == [16, 272, 624, 368]
                components = page.get("Components") or [page["Key"]]
                colors = [color for key, color in zip(components, page.get("ComponentColors") or [page["Foreground"]] * len(components)) for _ in translations[key]]
                assert "".join(page["Lines"]) == "".join(translations[key] for key in components)
                expected.paste(tuple(meta["palette"][page["Background"]]), tuple(page["Box"]))
                at = 0
                for row, line in enumerate(page["Lines"]):
                    for col, char in enumerate(line):
                        x, y = 16 + col * 16, 272 + row * 20
                        expected.paste(tuple(meta["palette"][colors[at]]), (x, y, x + 16, y + 20), masks[char])
                        at += 1
                if KEY in components:
                    assert components == INTRO and page["ComponentColors"] == [7, 3, 7]
                    visible += 1
                    if {"menu.shared.attack", "menu.shared.explain"} <= {w["Key"] for w in meta["words"] or []}:
                        buttons += 1
                        example = b["File"]
                elif visible:
                    after += 1
            assert chinese.tobytes() == expected.tobytes(), (b["step"], "composition")
        previous = b
    assert visible > 0 and buttons > 0 and after > 0 and KEY not in zh["final_paragraph"]["Components"]
    write(out / "check.json", dict(original_state_equal=True, gpu_pairs=len(zh["frames"]), native_checkpoints=len(control["checkpoints"]),
          held=held, visible_intro_and_prompt=visible, visible_with_both_buttons=buttons,
          following_dialogue=after, paragraph_sources=len(events),
          source_before_glyph=True, example=example, source=len(catalog(out / "inputs-r1/en.tsv")), translated=len(translations),
          scope="正常進港、三片段同頁及解釋後對話的一條路徑；其他選項問句未逐場走訪。"))
    print(read(out / "check.json"))


def rebuild(root, out):
    assert not (out / "evidence.json").exists()
    with tempfile.TemporaryDirectory(prefix="rebuild-", dir=out) as directory:
        fresh = Path(directory)
        prepare(root, fresh)
        for p in (out / "inputs-r1").iterdir():
            if p.is_file():
                assert sha(p) == sha(fresh / "inputs-r1" / p.name), p.name
        for name in ("binding.json", "request.json"):
            assert sha(out / name) == sha(fresh / name), name
    write(out / "rebuild.json", dict(input_files=18, all_inputs_equal=True))


def seal(root, out):
    assert read(out / "check.json")["original_state_equal"] and read(out / "rebuild.json")["all_inputs_equal"]
    assert not (out / "evidence.json").exists()
    probe = root / "workplace/probe"
    sources = list((probe / PARENT).iterdir())
    sources.extend(probe / ORACLE / name for name in ("port-entry-observe/receipt.json", "port-entry-control/receipt.json", "port-entry-request.json", "port-entry-zh-r2/receipt.json", "port-prefix-3/final.state"))
    sources.extend(root / name for name in ("workplace/translation/en.tsv", "workplace/translation/zh-TW.tsv", "workplace/input/dos/drkqueen/DQK.EXE"))
    snapshots = out / "tool-snapshots"
    snapshots.mkdir()
    for name in ("choice_prompt_inputs.py", "empty_notice_inputs.py"):
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
