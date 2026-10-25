"""特殊物品空清單：完整來源綁定與一次連續往返抽驗。入口見規格 001。"""
import base64
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

from PIL import Image

PARENT = "shared-menu-20261025"
KEY = "ui.31f10d38edf50b7a3f39"
SIG = "72c4041e90650eaa2c0b46505cfc183082f23966891560a9b9dec4ad6e4fdfaa"
PROGRAM = "manual-reader-rows-20261025/programs-r1"


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def catalog(path):
    with path.open() as stream:
        rows = list(csv.DictReader(stream, delimiter="\t", quoting=csv.QUOTE_NONE))
    assert len({r["key"] for r in rows}) == len(rows)
    return {r["key"]: r["text"] for r in rows}


def prepare(root, out):
    probe = root / "workplace/probe"
    parent = probe / PARENT
    receipt = read(parent / "inv-observe/receipt.json")
    calls = [c for c in receipt["calls"] if c.get("vararg_1_candidate", {}).get("text") == "Empty!"]
    assert len(calls) == 1
    call = calls[0]
    wrapper = receipt["wrappers"][call["wrapper_index"]]
    assert call["caller"] == dict(Seg=0xb72, Off=0x27c)
    assert wrapper["caller"] == dict(Seg=0x88e, Off=0x1560)
    assert wrapper["menu_valid"] and wrapper["menu_snapshot"]["Signature"] == SIG
    assert wrapper["vararg_1_candidate"]["text"] == "Empty!"
    assert wrapper["step"] < call["step"] < call["first_glyph"] < call["return_step"] < wrapper["return_step"]
    assert call["format"]["text"] == wrapper["format"]["text"] == "%s"
    assert call["stack"][2:5] == [189, 8004, 143]
    assert [int(x & 255) * 8 for x in wrapper["stack"][2:4]] == [0, 192]
    field = dict(Pane="callsite", Group="footer", Key=KEY, Start=0, Length=6,
                 RawX=8004, RawY=189, Caller=call["caller"], UpperCaller=wrapper["caller"],
                 UpperNative=[0, 192], Color=143, MenuSignature=SIG,
                 SHA256=hashlib.sha256(b"Empty!").hexdigest(),
                 FormatSHA256=hashlib.sha256(b"%s").hexdigest(),
                 UpperFormatSHA256=hashlib.sha256(b"%s").hexdigest())
    target = out / "inputs-r1"
    assert not target.exists()
    shutil.copytree(parent / "inputs-r2", target)
    cfg = read(target / "inputs.json")
    assert cfg["Menus"][SIG] == "exploration" and not any(f["Key"] == KEY for f in cfg["Fields"])
    cfg["Fields"].append(field)
    # 同一段 20M 路徑，只在來源、首字形、返回和還原交界加密。
    windows = [[wrapper["step"] - 2000, wrapper["step"] + 4000]]
    windows.extend([call[k] - 2000, call[k] + 4000] for k in ("step", "first_glyph", "return_step"))
    cfg["fine_windows"].extend(windows)
    write(target / "inputs.json", cfg)
    glyphs = read(target / "glyphs-16.json")["glyphs"]
    for name, text in (("en.tsv", "Empty!"), ("zh-TW.tsv", "空的！")):
        values = catalog(target / name)
        assert KEY not in values
        formal = catalog(root / "workplace/translation" / name)
        assert formal[KEY] == text
        if name == "zh-TW.tsv":
            assert set(text) <= glyphs.keys()
        values[KEY] = text
        (target / name).write_text("key\ttext\n" + "".join(k + "\t" + v + "\n" for k, v in sorted(values.items())))
    write(out / "binding.json", dict(field=field, call=call, wrapper=wrapper))
    provenance = read(target / "provenance.json")
    provenance["empty_notice_extension"] = dict(parent=PARENT + "/inputs-r2", binding_sha256=sha(out / "binding.json"),
                                                en_sha256=sha(target / "en.tsv"), zh_sha256=sha(target / "zh-TW.tsv"))
    write(target / "provenance.json", provenance)
    shutil.copyfile(parent / "inv-request.json", out / "request.json")
    print("one existing translation, exact source and menu, unchanged glyphs")


def check(root, out):
    parent = root / "workplace/probe" / PARENT
    for source in (parent / "inputs-r2").iterdir():
        if source.is_file() and source.name not in ("inputs.json", "en.tsv", "zh-TW.tsv", "provenance.json"):
            assert sha(source) == sha(out / "inputs-r1" / source.name), source.name
    for source in (out / "programs-r1").glob("*.go"):
        assert sha(source) == sha(root / "tools" / source.name), source.name
    native, control = [read(parent / ("inv-" + mode) / "receipt.json") for mode in ("observe", "control")]
    en, zh = [read(out / language / "receipt.json") for language in ("en", "zh")]
    assert native["checkpoints"] == control["checkpoints"]
    for run in (en, zh):
        assert not run["unimplemented"]
        assert run["initial_state_sha256"] == native["state_sha256"]
        assert run["list_inputs_sha256"] == sha(out / "inputs-r1/inputs.json")
        assert run["list_request_sha256"] == sha(out / "request.json")
        assert len(run["checkpoints"]) == len(control["checkpoints"])
        for actual, expected in zip(run["checkpoints"], control["checkpoints"]):
            for key in ("regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes", "step", "label"):
                assert actual[key] == expected[key], key
            assert not actual["file_writes"]
    binding = read(out / "binding.json")
    events = [e for e in zh["list_events"] if e["Kind"] == "field-before-glyph" and e["detail"]["word"]["Key"] == KEY]
    assert len(events) == 1
    event, call = events[0], binding["call"]
    assert event["Step"] == call["step"] < event["first_glyph"] == call["first_glyph"] < call["return_step"]
    transitions = [e["Kind"] for e in zh["list_events"] if e["Kind"].startswith("footer-feedback-")]
    assert transitions == ["footer-feedback-capture", "footer-feedback-entry", "footer-feedback-ready", "footer-feedback-restore-begin", "footer-feedback-closed"], transitions
    glyphs = read(out / "inputs-r1/glyphs-16.json")["glyphs"]
    masks = {k: Image.frombytes("L", (16, 20), base64.b64decode(v)) for k, v in glyphs.items()}
    translations = catalog(out / "inputs-r1/zh-TW.tsv")
    assert [f["step"] for f in en["frames"]] == [f["step"] for f in zh["frames"]]
    assert len(zh["frames"]) == len(zh["list_frames"])
    visible = held = restored = 0
    previous = None
    example = None
    checkpoints = {c["step"]: c for c in control["checkpoints"]}
    for a, b, meta in zip(en["frames"], zh["frames"], zh["list_frames"]):
        english = Image.open(out / "en" / a["File"]).convert("RGB")
        chinese = Image.open(out / "zh" / b["File"]).convert("RGB")
        assert not meta["paragraph"] and not meta["reader"]
        for frame, im in ((a, english), (b, chinese)):
            assert hashlib.sha256(im.convert("RGBA").tobytes()).hexdigest() == frame["SHA256"]
        if a["step"] in checkpoints:
            cp = checkpoints[a["step"]]
            original = Image.open(parent / "inv-control" / (cp["label"] + ".png")).convert("RGB")
            assert english.tobytes() == original.resize((640, 400), Image.Resampling.NEAREST).tobytes()
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
                assert len(text) * 16 <= width
                for i, char in enumerate(text):
                    expected.paste(fg, (x + i * 16, y, x + (i + 1) * 16, y + 20), masks[char])
                if word["Key"] == KEY:
                    visible += 1
                    example = b["File"]
            assert chinese.tobytes() == expected.tobytes(), (b["step"], "composition")
            if b["step"] > call["return_step"] and visible and all(w["Key"] != KEY for w in meta["words"] or []):
                restored += 1
        previous = b
    assert visible > 0 and restored > 0
    assert all(w["Key"] != KEY for w in zh["final_words"])
    write(out / "check.json", dict(original_state_equal=True, gpu_pairs=len(zh["frames"]),
          native_checkpoints=len(control["checkpoints"]), held=held, visible=visible, restored=restored,
          source_before_glyph=True, example=example, source=len(catalog(out / "inputs-r1/en.tsv")),
          translated=len(translations), scope="特殊物品空清單及返回的一條正常按鍵路徑；其餘遊戲未重驗。"))
    print(read(out / "check.json"))


def rebuild(root, out):
    assert not (out / "evidence.json").exists()
    with tempfile.TemporaryDirectory(prefix="rebuild-", dir=out) as directory:
        fresh = Path(directory)
        prepare(root, fresh)
        for source in (out / "inputs-r1").iterdir():
            if source.is_file():
                assert sha(source) == sha(fresh / "inputs-r1" / source.name), source.name
        for name in ("binding.json", "request.json"):
            assert sha(out / name) == sha(fresh / name), name
    write(out / "rebuild.json", dict(input_files=18, all_inputs_equal=True))


def seal(root, out):
    assert read(out / "check.json")["original_state_equal"] and not (out / "evidence.json").exists()
    assert read(out / "rebuild.json")["all_inputs_equal"]
    parent = root / "workplace/probe" / PARENT
    sources = list((parent / "inputs-r2").iterdir())
    sources.extend(parent / name for name in ("inv-observe/receipt.json", "inv-control/receipt.json", "inv-request.json"))
    sources.extend(root / name for name in ("workplace/translation/en.tsv", "workplace/translation/zh-TW.tsv",
         "workplace/probe/battle-text-20261024/observe-gate-r1/final.state", "workplace/input/dos/drkqueen/DQK.EXE"))
    snapshots = out / "tool-snapshots"
    snapshots.mkdir()
    shutil.copyfile(root / "tools/empty_notice_inputs.py", snapshots / "empty_notice_inputs.py")
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
