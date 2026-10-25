"""戰鬥施法狀態的來源綁定、代表抽驗及跨目錄缺口盤點。入口見規格 001。"""
from collections import Counter
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile

from PIL import Image
from empty_notice_inputs import catalog, read, sha, write
from ui_word_frame_check import compose_words, masks16

PARENT = "effect-catalog-20261025/inputs-r1"
STATE = "battle-text-20261024/observe-combat-r1/final.state"
KEY = "ui.9e5d3472e05f5073d206"
STARTUP = "startup-captions-20261023-r3/ui-inputs"
PROGRAM = "spell-catalog-20261025/programs-r1/ui-list-live"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def derive(root):
    parent = root / "workplace/probe" / PARENT
    cfg = read(parent / "inputs.json")
    en, zh = [catalog(parent / n) for n in ("en.tsv", "zh-TW.tsv")]
    formal = root / "workplace/translation"
    a, b = [catalog(formal / n) for n in ("en.tsv", "zh-TW.tsv")]
    entry = next(e for e in read(formal / "catalog.json")["entries"] if e["key"] == KEY)
    raw = root / "workplace/input/dos/drkqueen/DQK.EXE"
    assert sha(raw) == "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
    assert entry["domain"] == "ui" and entry["text"] == a[KEY]
    assert entry["sources"] == [dict(file="DQK.EXE", file_offset=408694, encoding="ASCII NUL")]
    assert raw.read_bytes()[408694:408694 + len(a[KEY]) + 1] == a[KEY].encode() + b"\0"
    assert KEY not in en and KEY not in zh and len(a[KEY]) == 9 and 0 < len(b[KEY]) <= 9
    masks = masks16(read(parent / "glyphs-16.json"))
    for char in b[KEY]:
        assert masks[char].getbbox() is None or masks[char].getbbox()[3] <= 16
    en[KEY], zh[KEY] = a[KEY], b[KEY]
    field = dict(Pane="callsite", Group="body", Key=KEY, Start=0, Length=9,
                 Caller=dict(Seg=0xb72, Off=0x27c), UpperCaller=dict(Seg=0x88e, Off=0xa12),
                 RawX=8092, RawY=8036, FormatSHA256=digest("%s"), SHA256=digest(a[KEY]))
    assert not any(f.get("UpperCaller") == field["UpperCaller"] for f in cfg["Fields"])
    cfg["Fields"].append(field)
    return cfg, en, zh, dict(formal=entry, field=field)


def prepare(root, out):
    cfg, en, zh, binding = derive(root)
    native = read(out / "observe-r1/receipt.json")
    calls = [c for c in native["calls"] if c["vararg_1_candidate"]["text"] == en[KEY]
             and c["format"]["text"] == "%s"]
    assert calls
    for call in calls:
        w = native["wrappers"][call["wrapper_index"]]
        assert w["caller"] == binding["field"]["UpperCaller"] and w["format"]["text"] == en[KEY]
        assert call["caller"] == binding["field"]["Caller"] and call["stack"][2:5] == [8036, 8092, 139]
        cfg["fine_windows"].extend([step - 2000, step + 4000] for step in
                                  (w["step"], call["step"], call["first_glyph"], call["return_step"]))
    target = out / "inputs-r1"
    assert not target.exists()
    shutil.copytree(root / "workplace/probe" / PARENT, target)
    write(target / "inputs.json", cfg)
    for n, values in (("en.tsv", en), ("zh-TW.tsv", zh)):
        (target / n).write_text("key\ttext\n" + "".join(k + "\t" + v + "\n" for k, v in sorted(values.items())))
    write(out / "binding.json", binding)
    provenance = read(target / "provenance.json")
    provenance["combat_casting_extension"] = dict(parent=PARENT, binding_sha256=sha(out / "binding.json"),
        en_sha256=sha(target / "en.tsv"), zh_sha256=sha(target / "zh-TW.tsv"))
    write(target / "provenance.json", provenance)
    print("one formal source, one display field; program and glyphs unchanged")


def scan(root, out):
    """只有候選差額，不是工作清單或完整中文化完成度。"""
    probe = root / "workplace/probe"
    profile = out / "inputs-r1"
    known = {v.strip().casefold() for v in catalog(profile / "en.tsv").values()}
    startup = probe / STARTUP
    known.update(v.strip().casefold() for v in catalog(startup / "en.tsv").values())
    cfg = read(profile / "inputs.json")
    native_hashes = {f["SHA256"] for f in cfg["Fields"]}
    formal_en, formal_zh = [catalog(root / "workplace/translation" / n) for n in ("en.tsv", "zh-TW.tsv")]
    formal = {v.strip(): k for k, v in formal_en.items() if k in formal_zh}
    hits, first, sources = Counter(), {}, {}
    for p in sorted(probe.glob("*/*observe*/receipt.json")):
        if p.stat().st_size > 8_000_000:
            continue
        trace = read(p)
        if not trace.get("observe") or trace.get("exe_sha256") != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58":
            continue
        sources[str(p.relative_to(root))] = sha(p)
        for wrapper in trace.get("wrappers") or []:
            fmt = wrapper["format"]["text"]
            raw = wrapper["vararg_1_candidate"]["text"] if fmt == "%s" else fmt
            text = raw.strip()
            if "%" in text or text not in formal or text.casefold() in known or digest(raw) in native_hashes:
                continue
            caller = wrapper["caller"]
            key = (formal[text], caller["Seg"], caller["Off"])
            hits[key] += 1
            first.setdefault(key, dict(source=str(p.relative_to(root)), step=wrapper["step"]))
    result = [dict(formal_key=k, caller=dict(Seg=s, Off=o), samples=count, first=first[(k, s, o)])
              for (k, s, o), count in hits.most_common()]
    excluded = ["startup.quiz-page", "startup.quiz-word", "startup.quiz-heading"]
    assert all(k in catalog(startup / "en.tsv") for k in excluded)
    write(out / "coverage.json", dict(scope="僅8MB以下既有原版觀測的完整UI文字候選；組句與子詞框仍可能已覆蓋，不作完成度或待辦權威。",
          primary_catalog_sha256=sha(profile / "en.tsv"), startup_catalog_sha256=sha(startup / "en.tsv"),
          startup_binding_sha256=sha(startup / "bindings.json"), startup_quiz_excluded=excluded,
          traces=sources, candidates=result))
    print("bounded traces", len(sources), "candidate pairs", len(result), "startup quiz recognized")


def panel_samples(root, out):
    target = out / "inputs-r2"
    assert not target.exists()
    shutil.copytree(out / "inputs-r1", target)
    cfg = read(target / "inputs.json")
    panels = [p for p in read(out / "observe-r1/receipt.json")["hud_panels"] if p["caller"] == dict(Seg=0x059f, Off=0x23bb)]
    assert len(panels) == 1
    for p in panels:
        cfg["fine_windows"].extend([p[k] - 2000, p[k] + 4000] for k in ("step", "return_step"))
    write(target / "inputs.json", cfg)


def check(root, out):
    cfg, en, zh, binding = derive(root)
    profile = out / "inputs-r2"
    actual = read(profile / "inputs.json")
    assert {k: v for k, v in cfg.items() if k != "fine_windows"} == {k: v for k, v in actual.items() if k != "fine_windows"}
    assert binding == read(out / "binding.json")
    assert catalog(profile / "en.tsv") == en and catalog(profile / "zh-TW.tsv") == zh
    native, control = [read(out / (n + "-r1/receipt.json")) for n in ("observe", "control")]
    assert native["checkpoints"] == control["checkpoints"]
    assert sha(out / "observe-r1/final.state") == sha(out / "control-r1/final.state")
    assert native["request"] == read(out / "request-r1.json")
    assert native["request"]["state_sha256"] == sha(root / "workplace/probe" / STATE)
    old = root / "workplace/probe/combat-aim-route-20261024"
    assert control["checkpoints"][:2] == read(old / "control-r3/receipt.json")["checkpoints"]
    base = control["checkpoints"][1]["keys_consumed"]
    for cp, previous in zip(control["checkpoints"][2:], read(old / "observe-r4/receipt.json")["checkpoints"]):
        assert cp == {**previous, "keys_consumed": previous["keys_consumed"] + base}
    a, b = [read(out / (n + "-r3/receipt.json")) for n in ("en", "zh")]
    for run in (a, b):
        assert not run["unimplemented"] and run["initial_state_sha256"] == native["request"]["state_sha256"]
        assert run["list_inputs_sha256"] == sha(profile / "inputs.json")
        assert run["list_request_sha256"] == sha(out / "request-r1.json")
        assert len(run["checkpoints"]) == 5
        for cp, expected in zip(run["checkpoints"], control["checkpoints"]):
            for key in ("step", "label", "regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes"):
                assert cp[key] == expected[key], key
            assert not cp["file_writes"]
    events = [e for e in b["list_events"] if e["Kind"] == "field-before-glyph" and e["detail"]["key"] == KEY]
    calls = [c for c in native["calls"] if c["format"]["text"] == "%s" and c["vararg_1_candidate"]["text"] == en[KEY]]
    assert len(events) == len(calls) == 1
    c, e = calls[0], events[0]
    w = native["wrappers"][c["wrapper_index"]]
    assert w["step"] < e["Step"] == c["step"] < e["first_glyph"] == c["first_glyph"] < c["return_step"]
    assert e["detail"]["raw_xy"] == [8092, 8036] and e["detail"]["source_sha256"] == binding["field"]["SHA256"]
    next_actor = next(c for c in native["calls"] if c["step"] > w["step"] and c["wrapper_index"] >= 0 and
        native["wrappers"][c["wrapper_index"]]["caller"] == dict(Seg=0x88e, Off=0x16fb) and c["vararg_1_candidate"]["text"] != "LENDUIRA")
    assert [f["step"] for f in a["frames"]] == [f["step"] for f in b["frames"]]
    assert len(b["frames"]) == len(b["list_frames"])
    masks = masks16(read(profile / "glyphs-16.json"))
    cps = {cp["step"]: cp for cp in control["checkpoints"]}
    visible = held = removed = protected = 0
    previous = example = None
    for x, y, meta in zip(a["frames"], b["frames"], b["list_frames"]):
        english, chinese = [Image.open(out / (n + "-r3") / f["File"]).convert("RGB") for n, f in (("en", x), ("zh", y))]
        for frame, image in ((x, english), (y, chinese)):
            assert hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest() == frame["SHA256"]
        if x["step"] in cps:
            original = Image.open(out / "control-r1" / (cps[x["step"]]["label"] + ".png")).convert("RGB")
            assert english.tobytes() == original.resize((640, 400), Image.Resampling.NEAREST).tobytes()
        assert not meta["paragraph"] and not meta["reader"]
        if y["held"]:
            assert previous and previous["SHA256"] == y["SHA256"]
            held += 1
        else:
            assert chinese.tobytes() == compose_words(english, meta["words"], meta["palette"], zh, masks).tobytes()
            active = any(word["Key"] == KEY for word in meta["words"] or [])
            if active:
                visible += 1
                example = y["File"]
                for xx, yy, width, height in ((184, 8, 128, 8), (264, 24, 48, 8), (208, 40, 40, 8), (264, 56, 32, 8)):
                    rect = tuple(v * 2 for v in (xx, yy, xx + width, yy + height))
                    assert chinese.crop(rect).tobytes() == english.crop(rect).tobytes()
                    protected += 1
            if y["step"] > next_actor["return_step"]:
                assert not active
                assert chinese.crop((368, 144, 512, 160)).tobytes() == english.crop((368, 144, 512, 160)).tobytes()
                removed += 1
        previous = y
    assert visible > 0 and removed > 0 and not any(w["Key"] == KEY for w in b["final_words"])
    parent = root / "workplace/probe" / PARENT
    for p in parent.iterdir():
        if p.is_file() and p.name not in ("inputs.json", "en.tsv", "zh-TW.tsv", "provenance.json"):
            assert sha(p) == sha(profile / p.name)
    panel = next(p for p in native["hud_panels"] if p["caller"] == dict(Seg=0x059f, Off=0x23bb))
    restored = [e for e in b["list_events"] if e["Kind"] == "spell-footer-panel-return"]
    assert len(restored) == 1 and restored[0]["detail"]["kept"]
    assert restored[0]["Step"] == panel["return_step"] and restored[0]["detail"]["entry_step"] == panel["step"]
    first_fill = next(f for f in native["fill_events"] if panel["step"] < f["step"] < panel["return_step"] and f["native_rect"] == [184, 8, 128, 168])
    during = [f for f in b["frames"] if first_fill["converted_step"] <= f["step"] < panel["return_step"]]
    assert during and all(f["held"] for f in during)
    footer_after = [meta for f, meta in zip(b["frames"], b["list_frames"]) if not f["held"] and f["step"] >= panel["return_step"]]
    assert footer_after and all(any(w["Key"] == "hud.ec5608fbca6974ee4604" for w in m["words"] or []) for m in footer_after)
    for p in (out / "programs-r3").glob("*.go"):
        assert sha(p) == sha(root / "tools" / p.name), p.name
    assert len(list((out / "programs-r3").glob("*.go"))) == 14
    write(out / "check.json", dict(original_state_equal=True, source_before_glyph=True,
          source=len(en), translated=len(zh), gpu_pairs=len(b["frames"]), native_checkpoints=5,
          held=held, visible=visible, removed=removed, protected_samples=protected, example=example,
          glyphs_unchanged=True, frontend_sha256=sha(out / "programs-r3/ui-list-live"),
          panel_held_samples=len(during), caption_after_panel=len(footer_after),
          target_panel_return=panel["return_step"], scope="只抽一次正常自動施法及下一角色，原版與完整詞框以外的像素保持。"))
    print(read(out / "check.json"))


def rebuild(root, out):
    with tempfile.TemporaryDirectory(prefix="rebuild-", dir=out) as directory:
        fresh = Path(directory)
        (fresh / "observe-r1").mkdir()
        shutil.copyfile(out / "observe-r1/receipt.json", fresh / "observe-r1/receipt.json")
        prepare(root, fresh)
        panel_samples(root, fresh)
        for name in ("inputs-r1", "inputs-r2"):
            for p in (out / name).iterdir():
                if p.is_file():
                    assert sha(p) == sha(fresh / name / p.name), (name, p.name)
        assert sha(out / "binding.json") == sha(fresh / "binding.json")
    write(out / "rebuild.json", dict(input_files=18, profiles=2, all_inputs_equal=True))


def regression(root, out):
    probe = root / "workplace/probe"
    native = read(probe / "battle-continuation-20261025/control-r1/receipt.json")
    observed = read(probe / "battle-continuation-20261025/observe-r1/receipt.json")
    cfg = out / "inputs-r2"
    zh, masks = catalog(cfg / "zh-TW.tsv"), masks16(read(cfg / "glyphs-16.json"))
    english = read(out / "regression-en/receipt.json")
    released = carried = 0
    for language in ("en", "zh"):
        new = read(out / ("regression-" + language) / "receipt.json")
        old_root = probe / "spell-catalog-20261025" / ("battle-" + language)
        old = read(old_root / "receipt.json")
        assert new["list_inputs_sha256"] == sha(out / "inputs-r2/inputs.json")
        assert new["list_request_sha256"] == sha(probe / "spell-catalog-20261025/battle-request.json")
        assert [f["step"] for f in new["frames"]] == [f["step"] for f in old["frames"]]
        assert [{k: v for k, v in m.items() if k != "list_event_count"} for m in new["list_frames"]] == [{k: v for k, v in m.items() if k != "list_event_count"} for m in old["list_frames"]]
        additions = [e for e in new["list_events"] if e["Kind"] in ("hud-update-entry", "spell-footer-panel-return")]
        assert len(additions) == 2 and additions[-1]["detail"]["kept"]
        panel = next(p for p in observed["hud_panels"] if p["step"] == additions[0]["Step"])
        assert panel["caller"] == dict(Seg=0x059f, Off=0x23bb) and panel["return_step"] == additions[-1]["Step"]
        assert [e for e in new["list_events"] if e not in additions] == old["list_events"]
        assert new["final_words"] == old["final_words"]
        assert not new["unimplemented"]
        for cp, expected in zip(new["checkpoints"], native["checkpoints"]):
            for key in ("step", "label", "regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes"):
                assert cp[key] == expected[key]
        previous = None
        for i, (f, before, meta) in enumerate(zip(new["frames"], old["frames"], new["list_frames"])):
            path = out / ("regression-" + language) / f["File"]
            image = Image.open(path).convert("RGB")
            assert hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest() == f["SHA256"]
            if language == "en":
                assert f == before and sha(path) == sha(old_root / before["File"])
            else:
                if f != before:
                    assert before["held"] and f["step"] > panel["return_step"]
                    if f["held"]:
                        carried += 1
                    else:
                        released += 1
                if f["held"]:
                    assert previous is not None and f["SHA256"] == previous["SHA256"]
                else:
                    source = Image.open(out / "regression-en" / english["frames"][i]["File"]).convert("RGB")
                    assert not meta["paragraph"] and not meta["reader"]
                    assert image.tobytes() == compose_words(source, meta["words"], meta["palette"], zh, masks).tobytes()
            previous = f
    assert released > 0
    write(out / "caption-regression.json", dict(gpu_pairs=len(new["frames"]), native_checkpoints=len(new["checkpoints"]),
         original_state_equal=True, english_parent_frames_equal=True, extra_released_frames=released,
         held_after_release=carried, other_parent_frames_equal=True, parent_source_events_equal=True))
    print(read(out / "caption-regression.json"))


def seal(root, out):
    assert read(out / "check.json")["original_state_equal"] and read(out / "rebuild.json")["all_inputs_equal"]
    assert read(out / "caption-regression.json")["original_state_equal"] and read(out / "binary-rebuild.json")["equal"]
    assert not (out / "evidence.json").exists()
    probe = root / "workplace/probe"
    sources = list((probe / PARENT).iterdir()) + list((probe / STARTUP).iterdir())
    sources.extend(root / n for n in ("workplace/translation/en.tsv", "workplace/translation/zh-TW.tsv", "workplace/translation/catalog.json", "workplace/input/dos/drkqueen/DQK.EXE"))
    sources.extend(probe / n for n in (STATE, PROGRAM, "combat-aim-route-20261024/control-r3/receipt.json", "combat-aim-route-20261024/observe-r4/receipt.json", "save-load-cold-wrapper-r2-20261022/load-j.state"))
    sources.extend(probe / n for n in ("battle-continuation-20261025/control-r1/receipt.json", "battle-continuation-20261025/observe-r1/receipt.json", "weapon-hud-20261025/control-r5/final.state", "spell-catalog-20261025/battle-request.json", "spell-catalog-20261025/battle-en/receipt.json", "spell-catalog-20261025/battle-zh/receipt.json"))
    snapshots = out / "tool-snapshots"
    snapshots.mkdir()
    for n in ("combat_casting_inputs.py", "empty_notice_inputs.py", "ui_word_frame_check.py"):
        shutil.copyfile(root / "tools" / n, snapshots / n)
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
    assert mode in ("prepare", "scan", "panel_samples", "check", "rebuild", "regression", "seal", "audit")
    globals()[mode](Path(project), Path(directory))
