"""三種共用回報及兩個名稱詞表位置。規格與 Docker 入口見規格 001。"""
from collections import Counter
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile

from PIL import Image
from empty_notice_inputs import catalog, read, sha, write
from ui_word_frame_check import check_word_pair, masks16

PARENT = "combat-casting-20261025/inputs-r2"
KEYS = dict(rest="ui.5c4efffc1a548cffaeab", dying="ui.4c07a5e271430d43cca9", question="ui.6a11455ae32b7edfde7a")
SEEDS = dict(rest="save-load-city-20261022/inn.state", dying="combat-aim-route-20261024/observe-r6/final.state", question="haste-battle-20261025/control-ambush-r1/final.state")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def equal_native(out, a, b):
    x, y = [read(out / name / "receipt.json") for name in (a, b)]
    assert x["checkpoints"] == y["checkpoints"]
    assert sha(out / a / "final.state") == sha(out / b / "final.state")
    return x


def requests(root, out):
    probe = root / "workplace/probe"
    for case, seed in SEEDS.items():
        trace = equal_native(out, case + "-prefix-observe", case + "-prefix-control")
        assert trace["request"]["state_sha256"] == sha(probe / seed)
        assert trace["request"]["actions"][-1]["end"] - trace["request"]["start_steps"] <= 100000000
    rest = read(probe / "pane-render-20261022/observe-clock-city-r1/receipt.json")["request"]
    rest["start_steps"], rest["state_sha256"] = 665000000, sha(out / "rest-prefix-control/final.state")
    rest["actions"] = rest["actions"][3:10]
    rest["actions"][-1] = dict(at=760000000, end=765000000, kind="text", key="e", label="return-camp")
    dying = read(probe / "combat-aim-route-20261024/request-r7.json")
    dying["start_steps"], dying["state_sha256"] = 3600000000, sha(out / "dying-prefix-control/final.state")
    dying["actions"] = dying["actions"][:5]
    dying["actions"][0]["at"] = 3600000000
    dying["actions"].append(dict(at=3690000000, end=3700000000, kind="text", key="", label="next-actor"))
    question = dict(state_sha256=sha(out / "question-prefix-control/final.state"), start_steps=3086000000,
       actions=[dict(at=3086000000, end=3140000000, kind="text", key="", label="continue-question"),
                dict(at=3141000000, end=3186000000, kind="text", key="y", label="continue-yes")])
    for case, request in (("rest", rest), ("dying", dying), ("question", question)):
        assert request["actions"][-1]["end"] - request["start_steps"] == 100000000
        target = out / (case + "-request.json")
        if target.exists():
            assert read(target) == request
        write(target, request)
    full_rest = read(probe / "pane-render-20261022/observe-clock-city-r1/receipt.json")["request"]
    full_rest["actions"] = full_rest["actions"][:8]
    full_rest["actions"][-1]["end"] = 740000000
    write(out / "rest-request-r3.json", full_rest)


def case_trace(out, case):
    stem = "rest-r3" if case == "rest" else case
    return equal_native(out, stem + "-observe", stem + "-control")


def derive(root):
    probe = root / "workplace/probe"
    parent = probe / PARENT
    cfg = read(parent / "inputs.json")
    en, zh = [catalog(parent / n) for n in ("en.tsv", "zh-TW.tsv")]
    formal = root / "workplace/translation"
    a, b = [catalog(formal / n) for n in ("en.tsv", "zh-TW.tsv")]
    entries = {e["key"]: e for e in read(formal / "catalog.json")["entries"]}
    raw_path = root / "workplace/input/dos/drkqueen/DQK.EXE"
    assert sha(raw_path) == "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
    raw = raw_path.read_bytes()
    additions = []

    def field(key, caller, x, y):
        return dict(Pane="callsite", Group="body", Key=key, Start=0, Length=len(en[key]),
                    Caller=dict(Seg=0xb72, Off=0x27c), UpperCaller=caller,
                    RawX=x, RawY=y, SHA256=digest(en[key]), FormatSHA256=digest("%s"))

    positions = dict(rest=(dict(Seg=0x2c4a, Off=0x4687), 8052, 8076),
                     dying=(dict(Seg=0x22f4, Off=0x555), 8092, 8072),
                     question=(dict(Seg=0xceb, Off=0x995), 8004, 189))
    for case, key in KEYS.items():
        assert key not in en and key not in zh
        entry = entries[key]
        assert entry["domain"] == "ui" and entry["text"] == a[key] and digest(a[key]) == entry["sha256"]
        assert any(s["file"] == "DQK.EXE" and raw[s["file_offset"]:s["file_offset"] + len(a[key]) + 1] == a[key].encode() + b"\0" for s in entry["sources"])
        en[key], zh[key] = a[key], b[key]
        f = field(key, *positions[case])
        if case == "question":
            f.update(Group="footer", UpperFormatSHA256=digest("%s"), UpperNative=[0, 192], Color=0x70, BackgroundOverride=7)
        additions.append(f)
    spell_path = probe / "spell-catalog-20261025/bindings.json"
    assert sha(spell_path) == read(spell_path.parent / "evidence.json")["artifacts"]["bindings.json"]
    spells = read(spell_path)["records"]
    assert len(spells) == 113
    for record in spells:
        source = record["source"]["text"]
        row = next(r for r in cfg["Rows"] if r["Pane"] == "grimoire" and r["SHA256"] == digest("\t" + source))
        key = row["Spans"][0]["Key"]
        assert en[key] == source and zh[key] == record["term"]["zh"]
        additions.append(field(key, dict(Seg=0x2c4a, Off=0x46ad), 8004, 8080))
    names_path = probe / "combat-names-20261025/bindings.json"
    assert sha(names_path) == read(names_path.parent / "evidence.json")["artifacts"]["bindings.json"]
    names = read(names_path)
    moncha = root / "workplace/input/dos/drkqueen/DISK2/MONCHA.GLB"
    assert sha(moncha) == names["source_sha256"] == "43de18b224dde3786e223ae5d0af53afad2a8109981fd73c1e3e81bd87d6ac68"
    raw_names = moncha.read_bytes()
    assert names["blocks"] == 99 and len(names["names"]) == 96
    for record in names["names"]:
        key = record["slots"][0]["key"]
        text = en[key]
        assert a[record["key"]] == text and b[record["key"]] == zh[key]
        assert digest(text) == record["sha256"] and len(text) <= 16
        assert all(s["file"] == "DISK2/MONCHA.GLB" and raw_names[s["file_offset"]:s["file_offset"] + len(text)] == text.encode() for s in record["source_origins"])
        f = field(key, dict(Seg=0x88e, Off=0x16fb), 8092, 8064)
        f["UpperFormatSHA256"] = digest("%s")
        additions.append(f)
    masks = masks16(read(parent / "glyphs-16.json"))
    retained = 0
    for i, f in enumerate(additions):
        text = zh[f["Key"]]
        assert 0 < len(text) <= f["Length"] and 0 < f["Length"] <= 39
        for char in text:
            assert masks[char].getbbox() is None or masks[char].getbbox()[3] <= 16
        existing = [old for old in cfg["Fields"] if old.get("UpperCaller") == f["UpperCaller"] and old["RawX"] == f["RawX"] and old["RawY"] == f["RawY"] and old["SHA256"] == f["SHA256"]]
        assert len(existing) <= 1
        if existing:
            old = existing[0]
            assert en[old["Key"]] == en[f["Key"]] and zh[old["Key"]] == text
            assert old["Start"] == 0 and old["Length"] == f["Length"] and old["Caller"] == f["Caller"]
            additions[i] = old
            retained += 1
        else:
            cfg["Fields"].append(f)
    assert len(additions) == 212
    assert retained == 1
    down = next(p for p in cfg["HUDParagraphs"] if p["SHA256"] == "bcf47e35fc5fe9b78d1ce32a9b98b05adeb3e2aae129207ef29f5fdaeb290f93")
    assert down["NativeBox"] == [184, 136, 312, 176] and len(down["Spans"]) == 1
    span = down["Spans"][0]
    assert span["Start"] == 0 and span["Length"] == 9 and span["Rect"] == [184, 136, 128, 40]
    before = list(span["Rect"])
    span["Rect"] = [184, 136, 72, 8]
    return cfg, en, zh, dict(fields=additions, new_fields=211, retained_fields=retained, spells=113, names=96,
         hud_mask_updates=[dict(key=span["Key"], source_sha256=down["SHA256"], before=before, after=span["Rect"])],
         ui={case: entries[key] for case, key in KEYS.items()})


def matched(trace, fields):
    found = []
    for c in trace["calls"]:
        if c["wrapper_index"] < 0 or c["format"]["text"] != "%s":
            continue
        w = trace["wrappers"][c["wrapper_index"]]
        source = c["vararg_1_candidate"]["text"]
        for f in fields:
            if w["caller"] == f["UpperCaller"] and c["caller"] == f["Caller"] and c["stack"][2:4] == [f["RawY"], f["RawX"]] and digest(source) == f["SHA256"]:
                assert (w["vararg_1_candidate"]["text"] if w["format"]["text"] == "%s" else w["format"]["text"]) == source
                found.append((f, c, w))
    return found


def prepare(root, out):
    cfg, en, zh, data = derive(root)
    for case in KEYS:
        trace = case_trace(out, case)
        found = matched(trace, data["fields"])
        assert found, case
        for _, c, w in found:
            cfg["fine_windows"].extend([step - 2000, step + 4000] for step in (w["step"], c["step"], c["first_glyph"], c["return_step"]))
        last = max(c["return_step"] for _, c, _ in found)
        f = next(f for f, _, _ in found if f["Key"] == KEYS[case])
        x = (f["RawX"] - 8000) * 2
        y = f["RawY"] if f["RawY"] < 400 else (f["RawY"] - 8000) * 2
        clear = next((e for e in trace["fill_events"] if e["step"] > last and e["native_rect"][0] <= x and e["native_rect"][1] <= y and e["native_rect"][0] + e["native_rect"][2] >= x + f["Length"] * 8 and e["native_rect"][1] + e["native_rect"][3] >= y + 8), None)
        if clear:
            cfg["fine_windows"].extend([clear[k] - 2000, clear[k] + 4000] for k in ("step", "converted_step", "return_instruction_step"))
        if case == "question":
            for c in trace["calls"]:
                if c["caller"] == dict(Seg=0xceb, Off=0x1be) and c["menu_index"] >= 0:
                    cfg["fine_windows"].extend([c[k] - 2000, c[k] + 4000] for k in ("step", "first_glyph", "return_step"))
    target = out / "inputs-r3"
    assert not target.exists()
    shutil.copytree(root / "workplace/probe" / PARENT, target)
    write(target / "inputs.json", cfg)
    for name, values in (("en.tsv", en), ("zh-TW.tsv", zh)):
        (target / name).write_text("key\ttext\n" + "".join(k + "\t" + v + "\n" for k, v in sorted(values.items())))
    write(out / "bindings-r3.json", data)
    provenance = read(target / "provenance.json")
    provenance["shared_feedback_extension"] = dict(parent=PARENT, bindings_sha256=sha(out / "bindings-r3.json"),
        en_sha256=sha(target / "en.tsv"), zh_sha256=sha(target / "zh-TW.tsv"))
    write(target / "provenance.json", provenance)
    print("211 new bindings, existing Haste field kept, three new locale keys; 113 spells and96 names reused")


def check(root, out):
    cfg, en, zh, data = derive(root)
    profile = out / "inputs-r3"
    actual = read(profile / "inputs.json")
    assert {k: v for k, v in cfg.items() if k != "fine_windows"} == {k: v for k, v in actual.items() if k != "fine_windows"}
    assert read(out / "bindings-r3.json") == data
    assert catalog(profile / "en.tsv") == en and catalog(profile / "zh-TW.tsv") == zh
    results = {}
    masks = masks16(read(profile / "glyphs-16.json"))
    for case in KEYS:
        trace = case_trace(out, case)
        equal_native(out, case + "-prefix-observe", case + "-prefix-control")
        native_dir = out / ("rest-r3-control" if case == "rest" else case + "-control")
        state = root / "workplace/probe" / SEEDS["rest"] if case == "rest" else out / (case + "-prefix-control/final.state")
        request = out / ("rest-request-r3.json" if case == "rest" else case + "-request.json")
        result = check_word_pair(out / (case + "-en-r4"), out / (case + "-zh-r4"), native_dir, state, request, profile, zh, masks)
        a, b = [read(out / (case + "-" + n + "-r4") / "receipt.json") for n in ("en", "zh")]
        assert trace["request"] == read(request) and trace["request"]["state_sha256"] == sha(state)
        events = {e["Step"]: e for e in b["list_events"] if e["Kind"] == "field-before-glyph"}
        found = matched(trace, data["fields"])
        targets = {(f["Key"], (f["RawX"] - 8000) * 2, f["RawY"] if f["RawY"] < 400 else (f["RawY"] - 8000) * 2) for f, _, _ in found}
        visible = Counter({t: 0 for t in targets})
        for f, c, w in found:
            e = events[c["step"]]
            assert e["detail"]["key"] == f["Key"] and e["detail"]["source_sha256"] == f["SHA256"] and e["detail"]["raw_xy"] == [f["RawX"], f["RawY"]]
            assert w["step"] < e["Step"] == c["step"] < e["first_glyph"] == c["first_glyph"] < c["return_step"]
        protected = removed = combined = down_together = 0
        yes_at = 3141000000
        buttons = {f["Key"] for f in cfg["Fields"] if f.get("MenuSignature") == "7272d96e89c7974d280914813f2f4a2b4350bced877036575b8641c701a78f4e"}
        for x, y, meta in zip(a["frames"], b["frames"], b["list_frames"]):
            if y["held"]:
                continue
            words = meta["words"] or []
            for word in words:
                t = (word["Key"], word["X"], word["Y"])
                if t in visible:
                    visible[t] += 1
            active = any(w["Key"] == KEYS[case] for w in words)
            if case == "question":
                if active and {w["Key"] for w in words} >= buttons:
                    combined += 1
                if y["step"] > yes_at and not active:
                    removed += 1
            else:
                if active:
                    english, chinese = [Image.open(out / (case + "-" + n + "-r4") / f["File"]).convert("RGB") for n, f in (("en", x), ("zh", y))]
                    rects = [(8, 152, 96, 8), (96, 136, 64, 8)] if case == "rest" else [(264, 24, 48, 8), (208, 40, 40, 8)]
                    for xx, yy, width, height in rects:
                        rect = tuple(v * 2 for v in (xx, yy, xx + width, yy + height))
                        assert english.crop(rect).tobytes() == chinese.crop(rect).tobytes()
                        protected += 1
                    if case == "dying":
                        down_key = data["hud_mask_updates"][0]["key"]
                        assert any(w["Key"] == down_key and w["X"] == 184 and w["Y"] == 136 and w["Width"] == 72 and w.get("Height", 8) in (0, 8) for w in words)
                        down_together += 1
                if y["step"] > max(c["return_step"] for _, c, _ in found) and not any((w["Key"], w["X"], w["Y"]) in targets for w in words):
                    removed += 1
        assert visible and all(visible.values()) and removed > 0
        assert not any((w["Key"], w["X"], w["Y"]) in targets for w in b["final_words"])
        if case == "question":
            assert len(buttons) == 2 and combined > 0
        else:
            assert protected > 0
        if case == "rest":
            ready = [e for e in b["list_events"] if e["Kind"] == "rest-memo-ready"]
            assert len(ready) == 3
            native_returns = {w["return_step"]: digest(w["format"]["text"]) for w in trace["wrappers"] if w["caller"] == dict(Seg=0x2c4a, Off=0x46ad)}
            assert all(native_returns[e["Step"]] == e["detail"]["source_sha256"] for e in ready)
            rest_buttons = {f["Key"] for f in cfg["Fields"] if f.get("MenuSignature") == "744578f86fd82e27ec8c0b3ed07c8404cbb7061d6e459626ed7c33ae19e38999"}
            assert len(rest_buttons) == 7
            for frame, meta in zip(b["frames"], b["list_frames"]):
                if not frame["held"] and any(w["Key"] == KEYS[case] for w in meta["words"] or []):
                    assert {w["Key"] for w in meta["words"] if w.get("Button")} >= rest_buttons
            result["complete_report_returns"] = len(ready)
            legacy = read(out / "rest-zh-legacy-full/receipt.json")
            assert [f["step"] for f in legacy["frames"]] == [f["step"] for f in b["frames"]]
            previous = read(out / "rest-zh-r3/receipt.json")
            assert legacy["initial_state_sha256"] == b["initial_state_sha256"] and legacy["list_inputs_sha256"] == previous["list_inputs_sha256"]
            assert legacy["list_request_sha256"] == b["list_request_sha256"]
            assert legacy["checkpoints"] == b["checkpoints"]
            assert not any(not f["held"] and any(w["Key"] == KEYS[case] for w in m["words"] or []) for f, m in zip(legacy["frames"], legacy["list_frames"]))
            assert any({w["Key"] for w in m["words"] if w.get("Button")} >= rest_buttons and any(w["Key"] == KEYS[case] for w in m["words"]) for m in legacy["list_frames"] if m["words"])
            result["legacy_hidden_reports_confirmed"] = True
            result["legacy_held"] = sum(f["held"] for f in legacy["frames"])
        else:
            for language in ("en", "zh"):
                previous = read(out / (case + "-" + language + "-r2/receipt.json"))
                prior_fix = read(out / (case + "-" + language + "-r3/receipt.json"))
                assert prior_fix["frames"] == previous["frames"] and prior_fix["list_frames"] == previous["list_frames"]
                assert prior_fix["list_events"] == previous["list_events"]
            assert a["frames"] == read(out / (case + "-en-r3/receipt.json"))["frames"]
            result["rest_fix_other_paths_unchanged"] = True
        result["down_and_dying_together"] = down_together
        result.update(source_calls=len(found), target_samples=[dict(key=k, x=x, y=y, samples=count) for (k, x, y), count in visible.items()],
                      removed=removed, protected_samples=protected, question_with_both_buttons=combined)
        results[case] = result
    parent = root / "workplace/probe" / PARENT
    for p in parent.iterdir():
        if p.is_file() and p.name not in ("inputs.json", "en.tsv", "zh-TW.tsv", "provenance.json"):
            assert sha(p) == sha(profile / p.name), p.name
    for p in (out / "programs-r2").glob("*.go"):
        assert sha(p) == sha(root / "tools" / p.name), p.name
    assert len(list((out / "programs-r2").glob("*.go"))) == 14
    write(out / "check.json", dict(original_state_equal=True, source_before_glyph=True, source=len(en), translated=len(zh),
          new_fields=211, retained_fields=1, spells=113, names=96, glyphs_unchanged=True, frontend_sha256=sha(out / "programs-r2/ui-list-live"), cases=results))
    print({k: {x: y for x, y in v.items() if x not in ("visible", "examples", "target_samples")} for k, v in results.items()})


def scan(root, out):
    from combat_casting_inputs import scan as scan_catalog

    with tempfile.TemporaryDirectory(prefix="scan-", dir=out) as directory:
        fresh = Path(directory)
        shutil.copytree(out / "inputs-r3", fresh / "inputs-r1")
        scan_catalog(root, fresh)
        shutil.copyfile(fresh / "coverage.json", out / "coverage.json")


def rebuild(root, out):
    with tempfile.TemporaryDirectory(prefix="rebuild-", dir=out) as directory:
        fresh = Path(directory)
        for case in KEYS:
            for suffix in ("prefix-observe", "prefix-control", "observe", "control"):
                name = case + "-" + suffix
                (fresh / name).mkdir()
                for file in ("receipt.json", "final.state"):
                    shutil.copyfile(out / name / file, fresh / name / file)
        for name in ("rest-r3-observe", "rest-r3-control"):
            (fresh / name).mkdir()
            for file in ("receipt.json", "final.state"):
                shutil.copyfile(out / name / file, fresh / name / file)
        requests(root, fresh)
        prepare(root, fresh)
        for p in (out / "inputs-r3").iterdir():
            if p.is_file():
                assert sha(p) == sha(fresh / "inputs-r3" / p.name), p.name
        for name in ["bindings-r3.json", "rest-request-r3.json"] + [c + "-request.json" for c in KEYS]:
            assert sha(out / name) == sha(fresh / name), name
    write(out / "rebuild.json", dict(input_files=18, requests=3, all_inputs_equal=True))


def seal(root, out):
    assert read(out / "check.json")["original_state_equal"] and read(out / "rebuild.json")["all_inputs_equal"]
    assert read(out / "binary-rebuild.json")["equal"]
    assert not (out / "evidence.json").exists()
    probe = root / "workplace/probe"
    sources = list((probe / PARENT).iterdir())
    sources.extend(root / n for n in ("workplace/translation/en.tsv", "workplace/translation/zh-TW.tsv", "workplace/translation/catalog.json", "workplace/input/dos/drkqueen/DQK.EXE", "workplace/input/dos/drkqueen/DISK2/MONCHA.GLB"))
    sources.extend(probe / n for n in list(SEEDS.values()) + ["spell-catalog-20261025/bindings.json", "spell-catalog-20261025/evidence.json", "combat-names-20261025/bindings.json", "combat-names-20261025/evidence.json", "combat-names-20261025/term-review.json", "pane-render-20261022/observe-clock-city-r1/receipt.json", "combat-aim-route-20261024/request-r7.json"])
    snapshots = out / "tool-snapshots"
    snapshots.mkdir()
    sources.extend(probe / "startup-captions-20261023-r3/ui-inputs" / n for n in ("en.tsv", "bindings.json"))
    for name in ("shared_feedback_inputs.py", "empty_notice_inputs.py", "ui_word_frame_check.py", "combat_casting_inputs.py"):
        shutil.copyfile(root / "tools" / name, snapshots / name)
    write(out / "evidence.json", dict(state="SEALED", draft=True, summary=read(out / "check.json"),
          artifacts={str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()},
          sources={str(p.relative_to(root)): sha(p) for p in sources if p.is_file()}))
    audit(root, out)


def audit(root, out):
    d = read(out / "evidence.json")
    assert d["state"] == "SEALED"
    for n, expected in d["artifacts"].items():
        assert sha(out / n) == expected, n
    for n, expected in d["sources"].items():
        assert sha(root / n) == expected, n
    print("sealed", len(d["artifacts"]), "artifacts", len(d["sources"]), "sources")


if __name__ == "__main__":
    mode, project, directory = sys.argv[1:]
    assert mode in ("requests", "prepare", "check", "scan", "rebuild", "seal", "audit")
    globals()[mode](Path(project), Path(directory))
