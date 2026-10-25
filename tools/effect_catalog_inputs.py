"""效果頁的完整標籤候選、正式譯文及正常往返抽驗。入口見規格 001。"""
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile

from PIL import Image
from empty_notice_inputs import catalog, read, sha, write
from ui_word_frame_check import compose_words, masks16

PARENT = "spell-catalog-20261025/inputs-r1"
OLD = "pane-render-20261022"
FIRST = "ui.67927b5fa959c7b4203b"
LAST = "ui.5d6374be40132730735f"
CASES = {
    "ordinary": ("save-load-city-20261022/inn-menu.state", OLD + "/observe-effects-r1", OLD + "/control-effects-r1"),
    "haste": ("haste-battle-20261025/control-main-r2/final.state", None, None),
}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def derive(root):
    parent = root / "workplace/probe" / PARENT
    cfg = read(parent / "inputs.json")
    en, zh = [catalog(parent / name) for name in ("en.tsv", "zh-TW.tsv")]
    formal = root / "workplace/translation"
    formal_en, formal_zh = [catalog(formal / name) for name in ("en.tsv", "zh-TW.tsv")]
    metadata = read(formal / "catalog.json")
    entries = {r["key"]: r for r in metadata["entries"]}
    raw_path = root / "workplace/input/dos/drkqueen/DQK.EXE"
    raw = raw_path.read_bytes()
    assert sha(raw_path) == next(r["sha256"] for r in metadata["inputs"] if r["path"] == "DQK.EXE")
    first, last = [entries[k] for k in (FIRST, LAST)]
    # Blessed 另有角色狀態用的同字串；這裡固定已盤點的完整效果字串區段。
    start = 435039
    assert any(s["file"] == "DQK.EXE" and s["file_offset"] == start for s in first["sources"])
    end = last["sources"][0]["file_offset"] + len(last["text"]) + 1
    cluster = raw[start:end].split(b"\x00")
    assert cluster[-1] == b"" and len(cluster) - 1 == 69
    masks = masks16(read(parent / "glyphs-16.json"))
    records, additions = [], []
    offset = start
    for literal in cluster[:-1]:
        text = literal.decode("ascii")
        key = "ui." + digest(text)[:20]
        entry = entries[key]
        assert entry["domain"] == "ui" and entry["text"] == formal_en[key] == text
        assert any(s["file"] == "DQK.EXE" and s["file_offset"] == offset for s in entry["sources"])
        assert formal_zh[key] and len(formal_zh[key]) <= len(text)
        for char in formal_zh[key]:
            bbox = masks[char].getbbox()
            assert bbox is None or bbox[3] <= 16
        row = dict(Pane="effects", SHA256=digest(" " + text), Foregrounds=[7, 11],
                   Spans=[dict(Start=1, Length=len(text), Key="effect." + digest(text)[:20])])
        old = [r for r in cfg["Rows"] if r["Pane"] == "effects" and r["SHA256"] == row["SHA256"]]
        assert len(old) <= 1
        if old:
            span = old[0]["Spans"][0]
            assert len(old[0]["Spans"]) == 1 and span["Start"] == 1 and span["Length"] == len(text)
            assert old[0]["Foregrounds"] == [7, 11]
            assert en[span["Key"]] == text and zh[span["Key"]] == formal_zh[key]
            row = old[0]
        else:
            name_key = row["Spans"][0]["Key"]
            assert name_key not in en
            en[name_key], zh[name_key] = text, formal_zh[key]
            cfg["Rows"].append(row)
            additions.append(row)
        records.append(dict(literal_key=key, file_offset=offset, text_sha256=digest(text), row=row))
        offset += len(literal) + 1
    assert offset == end and len(additions) == 67
    assert len([r for r in cfg["Rows"] if r["Pane"] == "effects"]) == 70
    return cfg, en, zh, dict(start=start, end=end, records=records, additions=additions,
             confidence="原檔完整字串已證實；其餘標籤用途為候選，只有實際 effects 語境全字串匹配時套用。")


def prepare(root, out):
    cfg, en, zh, data = derive(root)
    probe = root / "workplace/probe"
    for case, (_, observed, control) in CASES.items():
        a = read((probe / observed if observed else out / "haste-observe") / "receipt.json")
        b = read((probe / control if control else out / "haste-control") / "receipt.json")
        assert a["checkpoints"] == b["checkpoints"]
        labels = {" " + en[r["row"]["Spans"][0]["Key"]] for r in data["records"]}
        for call in a["calls"]:
            if call["format"]["text"] == "%s" and call["vararg_1_candidate"]["text"] in labels:
                wrapper = a["wrappers"][call["wrapper_index"]]
                for step in (wrapper["step"], call["first_glyph"], call["return_step"]):
                    cfg["fine_windows"].append([step - 2000, step + 4000])
    target = out / "inputs-r1"
    assert not target.exists()
    shutil.copytree(probe / PARENT, target)
    write(target / "inputs.json", cfg)
    for name, values in (("en.tsv", en), ("zh-TW.tsv", zh)):
        (target / name).write_text("key\ttext\n" + "".join(k + "\t" + v + "\n" for k, v in sorted(values.items())))
    write(out / "bindings.json", data)
    provenance = read(target / "provenance.json")
    provenance["effect_catalog_extension"] = dict(parent=PARENT, binding_sha256=sha(out / "bindings.json"),
                en_sha256=sha(target / "en.tsv"), zh_sha256=sha(target / "zh-TW.tsv"))
    write(target / "provenance.json", provenance)
    shutil.copyfile(probe / OLD / "effects-roundtrip-request.json", out / "ordinary-request.json")
    print("69 candidate literals, 67 new effect rows/keys, existing three rows kept")


def check(root, out):
    cfg, en, zh, data = derive(root)
    actual = read(out / "inputs-r1/inputs.json")
    assert {k: v for k, v in cfg.items() if k != "fine_windows"} == {k: v for k, v in actual.items() if k != "fine_windows"}
    assert data == read(out / "bindings.json")
    profile = out / "inputs-r1"
    assert catalog(profile / "en.tsv") == en and catalog(profile / "zh-TW.tsv") == zh
    masks = masks16(read(profile / "glyphs-16.json"))
    effect_keys = {r["Spans"][0]["Key"] for r in cfg["Rows"] if r["Pane"] == "effects"}
    source_rows = {r["SHA256"]: r for r in cfg["Rows"] if r["Pane"] == "effects"}
    results = {}
    for case, (state, observed, control) in CASES.items():
        probe = root / "workplace/probe"
        native_root = probe / observed if observed else out / "haste-observe"
        control_root = probe / control if control else out / "haste-control"
        native, oracle = [read(p / "receipt.json") for p in (native_root, control_root)]
        assert native["checkpoints"] == oracle["checkpoints"]
        assert sha(native_root / "final.state") == sha(control_root / "final.state")
        request = read(out / (case + "-request.json"))
        assert request["state_sha256"] == sha(probe / state)
        end = next(a["at"] for a in request["actions"] if a["label"] in ("return-magic", "exit-effects-to-magic"))
        entry = next(l for l in native["list_events"] if l["menu_snapshot"]["Signature"] == "26528c2fbf961821f685b4c9a5941ec653ffb4238854686697e1b9eb23375cd3")
        a, b = [read(out / (case + "-" + lang) / "receipt.json") for lang in ("en", "zh")]
        for run in (a, b):
            assert not run["unimplemented"] and run["initial_state_sha256"] == sha(probe / state)
            assert run["list_inputs_sha256"] == sha(profile / "inputs.json")
            assert run["list_request_sha256"] == sha(out / (case + "-request.json"))
            assert len(run["checkpoints"]) == len(oracle["checkpoints"])
            for cp, expected in zip(run["checkpoints"], oracle["checkpoints"]):
                for key in ("regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes", "step", "label"):
                    assert cp[key] == expected[key], (case, key)
                assert not cp["file_writes"]
        events = {e["Step"]: e for e in b["list_events"] if e["Kind"] == "row-before-glyph"}
        labels, headers = [], []
        for call in native["calls"]:
            if call["wrapper_index"] < 0 or call["format"]["text"] != "%s":
                continue
            wrapper = native["wrappers"][call["wrapper_index"]]
            if not entry["step"] <= wrapper["step"] < end or wrapper["caller"] not in cfg["RowCallers"]:
                continue
            text = call["vararg_1_candidate"]["text"]
            color = wrapper["stack"][4] & 255
            if color == 12:
                col, row = [v & 255 for v in wrapper["stack"][2:4]]
                headers.append(dict(start=call["return_step"], rect=[col * 8, row * 8, len(text) * 8, 8], source_sha256=digest(text)))
                continue
            if color not in (7, 11) or not text.strip():
                continue
            row = source_rows[digest(text)]
            event = events[wrapper["step"]]
            assert event["Pane"] == "effects" and event["Step"] < call["step"] < event["first_glyph"] == call["first_glyph"] < call["return_step"]
            assert event["detail"]["spans"] == row["Spans"] and event["detail"]["foreground"] == color
            labels.append(dict(step=wrapper["step"], key=row["Spans"][0]["Key"], color=color))
        assert headers and labels
        assert [f["step"] for f in a["frames"]] == [f["step"] for f in b["frames"]]
        assert len(b["frames"]) == len(b["list_frames"])
        cps = {c["step"]: c for c in oracle["checkpoints"]}
        visible = {key: 0 for key in {r["key"] for r in labels}}
        held = header_samples = 0
        previous = example = None
        for x, y, meta in zip(a["frames"], b["frames"], b["list_frames"]):
            english, chinese = [Image.open(out / (case + "-" + lang) / f["File"]).convert("RGB") for lang, f in (("en", x), ("zh", y))]
            for frame, image in ((x, english), (y, chinese)):
                assert hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest() == frame["SHA256"]
            if x["step"] in cps:
                expected = Image.open(control_root / (cps[x["step"]]["label"] + ".png")).convert("RGB")
                assert english.tobytes() == expected.resize((640, 400), Image.Resampling.NEAREST).tobytes()
            assert not meta["paragraph"] and not meta["reader"]
            if y["held"]:
                assert previous is not None and y["SHA256"] == previous["SHA256"]
                held += 1
            else:
                assert chinese.tobytes() == compose_words(english, meta["words"], meta["palette"], zh, masks).tobytes()
                active = [w for w in meta["words"] or [] if w["Key"] in visible]
                for word in active:
                    visible[word["Key"]] += 1
                    example = y["File"]
                if active:
                    for header in headers:
                        if header["start"] <= y["step"] < end:
                            xx, yy, w, h = [v * 2 for v in header["rect"]]
                            assert chinese.crop((xx, yy, xx + w, yy + h)).tobytes() == english.crop((xx, yy, xx + w, yy + h)).tobytes()
                            header_samples += 1
            previous = y
        assert all(visible.values()) and header_samples > 0
        assert not any(w["Key"] in effect_keys for w in b["final_words"])
        if case == "haste":
            haste = "effect." + digest("Hastened")[:20]
            assert haste in visible and visible[haste] > 0
        results[case] = dict(gpu_pairs=len(b["frames"]), native_checkpoints=len(oracle["checkpoints"]),
             held=held, visible=visible, native_row_sources=len(labels), protected_name_samples=header_samples,
             example=example, colors=sorted({r["color"] for r in labels}))
    parent = root / "workplace/probe" / PARENT
    for p in parent.iterdir():
        if p.is_file() and p.name not in ("inputs.json", "en.tsv", "zh-TW.tsv", "provenance.json"):
            assert sha(p) == sha(profile / p.name), p.name
    assert sha(root / "workplace/probe/spell-catalog-20261025/programs-r1/ui-list-live") == "dfbdfbb341419fbd69a3b096daee9b300834175ad7ea9701e747b0daf9376953"
    write(out / "check.json", dict(original_state_equal=True, source_before_glyph=True, candidates=69,
          new_rows=67, source=len(en), translated=len(zh), glyphs_unchanged=True, program_unchanged=True,
          cases=results, scope="資料69候選；正常抽既有三列及加倍術後 Hastened、姓名與返回，未逐項觸發其餘標籤。"))
    print(read(out / "check.json"))


def rebuild(root, out):
    with tempfile.TemporaryDirectory(prefix="rebuild-", dir=out) as directory:
        fresh = Path(directory)
        for name in ("haste-observe", "haste-control"):
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
    sources.extend(probe / OLD / name for name in ("observe-effects-r1/receipt.json", "control-effects-r1/receipt.json", "effects-roundtrip-request.json"))
    sources.extend(probe / OLD / name / "final.state" for name in ("observe-effects-r1", "control-effects-r1"))
    old_control = probe / OLD / "control-effects-r1"
    sources.extend(old_control / (cp["label"] + ".png") for cp in read(old_control / "receipt.json")["checkpoints"])
    sources.extend(root / name for name in ("workplace/translation/en.tsv", "workplace/translation/zh-TW.tsv", "workplace/translation/catalog.json", "workplace/input/dos/drkqueen/DQK.EXE", "workplace/probe/save-load-city-20261022/inn-menu.state", "workplace/probe/haste-battle-20261025/control-main-r2/final.state", "workplace/probe/spell-catalog-20261025/programs-r1/ui-list-live", "workplace/ida/list-pane-20261022/row-provider/result.json"))
    snapshots = out / "tool-snapshots"
    snapshots.mkdir()
    for name in ("effect_catalog_inputs.py", "empty_notice_inputs.py", "ui_word_frame_check.py"):
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
