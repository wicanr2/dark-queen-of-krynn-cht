"""武器欄共通詞表與八鈕戰鬥選單的 DRAFT 輸入。"""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile

from original_prefix_check import catalog, read
from passage_runtime_inputs import record, sha, write

PARENT = "passage-runtime-20261025/inputs-r2"
MENU = "6d639cad2401b3e3be9d37b7f563f3294bd99ed2313a6a3dd8825c0f743b063b"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def terms(path):
    with path.open() as f:
        return list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))


def derive(root, out):
    parent = root / "workplace/probe" / PARENT
    config = read(parent / "inputs.json")
    assert not config.get("HUDWeaponNames") and MENU not in config["Menus"]
    en, zh = catalog(parent / "en.tsv"), catalog(parent / "zh-TW.tsv")
    glyphs = read(parent / "glyphs-16.json")["glyphs"]
    previous = terms(Path("/previous-text/glossary.tsv"))
    vocabulary = []
    for row in terms(root / "workplace/translation/glossary.tsv"):
        if row["category"] != "item" or row["project"] != "death_knight_of_krynn":
            continue
        authority = [r for r in previous if r["en"] == row["en"] and r["zh"] == row["zh"]]
        if len(authority) != 1:
            continue
        keys = [k for k, v in en.items() if v == row["en"] and zh.get(k) == row["zh"] and
                1 <= len(v) <= 15 and v.isascii() and v.strip() == v and
                not any(c in v for c in "%\\\n\r\t+") and len(zh[k]) <= len(v) and set(zh[k]) <= glyphs.keys()]
        if keys:
            vocabulary.append(dict(key=min(keys), name=row["en"], text=row["zh"], glossary=row, previous=authority[0]))
    assert len(vocabulary) >= 20 and len({r["name"] for r in vocabulary}) == len(vocabulary)
    config["HUDWeaponNames"] = [r["key"] for r in vocabulary]
    trace = read(out / "observe-r2/receipt.json")
    menu = next(m for m in trace["menus"] if m["Signature"] == MENU)
    buttons = menu["Buttons"]
    assert menu["Count"] == 9 and len(buttons) == 8
    assert [bytes.fromhex(b["SourceHex"]).decode() for b in buttons] == ["Aim", "Use", "Cast", "Quick", "Delay", "View", "Speed", "End"]
    assert [b["Index"] for b in buttons] == list(range(1, 9))
    encoded = json.dumps([9, [[b["Index"], b["SHA256"], b["RawX"], b["RawY"]] for b in buttons]], separators=(",", ":")).encode()
    assert digest(encoded) == MENU
    raw = bytes.fromhex(menu["RawHex"])
    fields = []
    for b in buttons:
        source = bytes.fromhex(b["SourceHex"]).decode()
        assert digest(source.encode()) == b["SHA256"]
        at = b["Index"]*32
        assert struct.unpack_from("<HH", raw, at) == (0x008e, 0x0ceb)
        assert struct.unpack_from("<HH", raw, at+12) == (b["SourcePointer"]["Off"], b["SourcePointer"]["Seg"])
        assert struct.unpack_from("<HH", raw, at+16) == (b["RawY"], b["RawX"])
        keys = {f["Key"] for f in config["Fields"] if f["Pane"] == "menu" and en[f["Key"]] == source}
        assert len(keys) == 1, source
        f = dict(Pane="menu", Group="footer", Key=next(iter(keys)), Start=0, Length=len(source),
                 SHA256=b["SHA256"], FormatSHA256=b["SHA256"], Caller=dict(Seg=0x0ceb, Off=0x01be),
                 RawX=(b["RawX"]-8000)*2, RawY=(b["RawY"]-8000)*2+1, MenuSignature=MENU)
        assert f not in config["Fields"] and f["RawX"] >= 0 and f["RawY"] in (179, 191)
        fields.append(f)
    config["Fields"].extend(fields)
    config["Menus"][MENU] = "combat"
    weapons, clears = [], []
    for i, p in enumerate(trace["paragraphs"]):
        source = p["source"]["text"]
        assert p["source"]["nul_terminated"] and [p[k] for k in ("foreground", "background", "clear")] == [7, 0, 1]
        assert p["step"] < p["first_glyph"] < p["return_step"]
        if source == " ":
            assert p["caller"] == dict(Seg=0x088e, Off=0x15e1) and p["native_box"] == [184, 16, 312, 176]
            clears.append(p)
            continue
        assert source == "Staff Sling +2 " and p["caller"] == dict(Seg=0x088e, Off=0x097e)
        assert p["native_box"] == [184, 56, 312, 80]
        calls = [c for c in trace["calls"] if c["paragraph_index"] == i and c["format"]["text"] == "%c"]
        assert "".join(chr(c["stack"][7] & 255) for c in calls) == source
        assert all(p["step"] < c["step"] < c["first_glyph"] < c["return_step"] < p["return_step"] for c in calls)
        weapons.append(p)
    assert len(weapons) == len(clears) == 2
    return config, dict(vocabulary=vocabulary, menu=menu, fields=fields, weapons=weapons, clears=clears,
                        source_sha256=sha(out / "observe-r2/receipt.json"), previous_sha256=sha(Path("/previous-text/glossary.tsv")))


def prepare(root, out):
    assert not (out / "evidence.json").exists()
    config, data = derive(root, out)
    target = out / "inputs-r1"
    assert not target.exists()
    shutil.copytree(root / "workplace/probe" / PARENT, target)
    config["fine_windows"] = []
    write(target / "inputs.json", config)
    provenance = read(target / "provenance.json")
    provenance["weapon_hud_extension"] = dict(parent=PARENT, data=data)
    write(target / "provenance.json", provenance)
    write(out / "data-r1.json", data)
    print("existing item vocabulary", len(data["vocabulary"]), "new menu fields", len(data["fields"]), "no catalog or glyph changes")


def samples(root, out):
    native, control = [read(out / n / "receipt.json") for n in ("observe-r2", "control-r2")]
    for key in ("checkpoints", "state_sha256", "request_sha256", "probe_sha256", "exe_sha256", "source_commit", "go_version"):
        assert native[key] == control[key], key
    assert sha(out / "observe-r2/final.state") == sha(out / "control-r2/final.state")
    assert all(not v for k, v in native.items() if k.startswith("pending_"))
    assert all(not c["file_writes"] and not c["unimplemented"] for c in native["checkpoints"])
    for cp in native["checkpoints"]:
        for ext in (".png", ".idx"):
            assert sha(out / "observe-r2" / (cp["label"]+ext)) == sha(out / "control-r2" / (cp["label"]+ext))
    data = read(out / "data-r1.json")
    request = read(out / "request-r2.json")
    points = {a["end"]: a["label"] for a in request["actions"]}
    calls = [c for c in native["calls"] if c["caller"] == dict(Seg=0x0ceb, Off=0x01be) and
             native["menus"][c["menu_index"]]["Signature"] == MENU]
    assert len(calls) == 16
    windows = []
    for source in data["weapons"] + data["clears"] + calls:
        for step in (source["step"], source["first_glyph"], source["return_step"]):
            points.setdefault(step-1, "sample-"+str(step-1))
            points.setdefault(step+1, "sample-"+str(step+1))
            windows.append([step-2000, step+4000])
    previous, actions, used = request["start_steps"], [], set()
    for step, label in sorted(points.items()):
        keys = [(i, a) for i, a in enumerate(request["actions"]) if previous <= a["at"] < step]
        assert len(keys) <= 1
        if keys:
            i, key = keys[0]
            used.add(i)
            actions.append(dict(at=key["at"], end=step, kind=key["kind"], key=key["key"], label=label))
        else:
            actions.append(dict(at=previous, end=step, kind="text", key="", label=label))
        previous = step
    assert len(used) == 3
    request["actions"] = actions
    write(out / "request-r3.json", request)
    merged = []
    for first, last in sorted(windows):
        if merged and first <= merged[-1][1]:
            merged[-1][1] = max(last, merged[-1][1])
        else:
            merged.append([first, last])
    target = out / "inputs-r2"
    assert not target.exists()
    shutil.copytree(out / "inputs-r1", target)
    cfg = read(target / "inputs.json")
    cfg["fine_windows"] = merged
    write(target / "inputs.json", cfg)
    write(out / "sampling.json", dict(checkpoints=len(actions), weapons=2, menu_calls=16, windows=len(merged)))
    print(read(out / "sampling.json"))


def guards(root, out):
    assert not (out / "evidence.json").exists()
    cfg, data = derive(root, out)
    assert data == read(out / "data-r1.json")
    cfg["fine_windows"] = []
    assert cfg == read(out / "inputs-r1/inputs.json")
    parent = root / "workplace/probe" / PARENT
    for p in parent.iterdir():
        if p.is_file() and p.name not in ("inputs.json", "provenance.json"):
            assert sha(p) == sha(out / "inputs-r1" / p.name) == sha(out / "inputs-r2" / p.name), p.name
    before = read(parent / "inputs.json")
    assert {k: v for k, v in cfg.items() if k not in ("HUDWeaponNames", "fine_windows", "Fields", "Menus")} == {
        k: v for k, v in before.items() if k not in ("fine_windows", "Fields", "Menus")}
    assert cfg["Fields"] == before["Fields"] + data["fields"]
    assert cfg["Menus"] == dict(before["Menus"], **{MENU: "combat"})
    assert {k: v for k, v in read(out / "inputs-r3/inputs.json").items() if k != "fine_windows"} == {
        k: v for k, v in cfg.items() if k != "fine_windows"}
    for p in parent.iterdir():
        if p.is_file() and p.name not in ("inputs.json", "provenance.json"):
            assert sha(p) == sha(out / "inputs-r3" / p.name), p.name
    equipment_data = read(out / "equipment-field.json")
    call = next(c for c in read(out / "observe-r2/receipt.json")["calls"] if c["step"] == 15647517150)
    assert equipment_data["call"] == call
    equipment_field = equipment_data["field"]
    assert equipment_field["SHA256"] == digest(call["vararg_1_candidate"]["text"].encode())
    assert equipment_field["RawX"] == 8004 and equipment_field["RawY"] == 8084 and equipment_field["Length"] == 11
    final = read(out / "inputs-r4/inputs.json")
    assert {k: v for k, v in final.items() if k not in ("Fields", "fine_windows")} == {
        k: v for k, v in cfg.items() if k not in ("Fields", "fine_windows")}
    assert final["Fields"] == cfg["Fields"] + [equipment_field]
    for p in parent.iterdir():
        if p.is_file() and p.name not in ("inputs.json", "provenance.json"):
            assert sha(p) == sha(out / "inputs-r4" / p.name), p.name
    with tempfile.TemporaryDirectory(prefix="rebuild-", dir=out) as name:
        fresh = Path(name)
        (fresh / "observe-r2").mkdir()
        shutil.copyfile(out / "observe-r2/receipt.json", fresh / "observe-r2/receipt.json")
        prepare(root, fresh)
        rebuilt = [p.name for p in (fresh / "inputs-r1").iterdir() if p.is_file()]
        for name in rebuilt:
            assert sha(fresh / "inputs-r1" / name) == sha(out / "inputs-r1" / name), name
    write(out / "inputs-check.json", dict(vocabulary=len(data["vocabulary"]), menu_fields=8, equipment_fields=1,
          unchanged_files=14, rebuilt_base_files=len(rebuilt),
          catalogs_unchanged=True, glyphs_unchanged=True, previous_terms_equal=True))
    print(read(out / "inputs-check.json"))


def return_samples(root, out):
    """補原版資料頁退出的填色及切頁邊界，保留先前全部截點。"""
    trace = read(out / "observe-r2/receipt.json")
    original = read(out / "request-r2.json")
    back = original["actions"][-1]["at"]
    fill = next(f for f in trace["fill_events"] if f["step"] > back)
    assert fill["native_rect"] == [184, 8, 128, 168]
    flips = [v for v in trace["display_changes"] if v["step"] > back]
    assert [v["layout"]["DisplayStart"] for v in flips] == [16384, 0, 16384]
    steps = [fill["step"], fill["converted_step"], fill["return_instruction_step"]] + [v["step"] for v in flips]
    points = {a["end"]: a["label"] for a in read(out / "request-r3.json")["actions"]}
    for step in steps:
        points.setdefault(step-1, "return-"+str(step-1))
        points.setdefault(step+1, "return-"+str(step+1))
    actions, previous, used = [], original["start_steps"], set()
    for step, label in sorted(points.items()):
        keys = [(i, a) for i, a in enumerate(original["actions"]) if previous <= a["at"] < step]
        assert len(keys) <= 1
        if keys:
            i, key = keys[0]
            used.add(i)
            actions.append(dict(at=key["at"], end=step, kind=key["kind"], key=key["key"], label=label))
        else:
            actions.append(dict(at=previous, end=step, kind="text", key="", label=label))
        previous = step
    assert len(used) == 3
    original["actions"] = actions
    write(out / "request-r4.json", original)
    config = read(out / "inputs-r2/inputs.json")
    windows = config["fine_windows"] + [[s-2000, s+4000] for s in steps]
    merged = []
    for first, last in sorted(windows):
        if merged and first <= merged[-1][1]:
            merged[-1][1] = max(last, merged[-1][1])
        else:
            merged.append([first, last])
    target = out / "inputs-r3"
    assert not target.exists()
    shutil.copytree(out / "inputs-r2", target)
    config["fine_windows"] = merged
    write(target / "inputs.json", config)
    write(out / "return-sampling.json", dict(checkpoints=len(actions), native_fill=fill, display_changes=flips,
          windows=len(merged), prior_checkpoints=123, scope="只補已發現返回殘字的獨立原版邊界。"))
    print("return checkpoints", len(actions), "windows", len(merged))


def equipment(root, out):
    """完整資料頁沿既有裝備欄契約補上已觀測的同一名稱。"""
    assert not (out / "evidence.json").exists()
    trace = read(out / "observe-r2/receipt.json")
    call = next(c for c in trace["calls"] if c["step"] == 15647517150)
    wrapper = trace["wrappers"][call["wrapper_index"]]
    assert call["caller"] == dict(Seg=0x0b72, Off=0x027c) and wrapper["caller"] == dict(Seg=0x088e, Off=0x071d)
    assert call["format"]["text"] == "%s" and call["vararg_1_candidate"]["text"] == "Staff Sling +2 "
    assert call["stack"][2:5] == [8084, 8004, 0x87]
    en = catalog(out / "inputs-r3/en.tsv")
    key = next(v["key"] for v in read(out / "data-r1.json")["vocabulary"] if v["name"] == "Staff Sling")
    field = dict(Pane="callsite", Group="body", Key=key, Start=0, Length=len(en[key]),
                 UpperCaller=wrapper["caller"], RawX=8004, RawY=8084, Caller=call["caller"],
                 FormatSHA256=digest(b"%s"), SHA256=digest(call["vararg_1_candidate"]["text"].encode()))
    target = out / "inputs-r4"
    assert not target.exists()
    shutil.copytree(out / "inputs-r3", target)
    cfg = read(target / "inputs.json")
    assert field not in cfg["Fields"]
    cfg["Fields"].append(field)
    write(target / "inputs.json", cfg)
    provenance = read(target / "provenance.json")
    provenance["weapon_hud_extension"]["equipment"] = dict(field=field, call=call, wrapper=wrapper)
    write(target / "provenance.json", provenance)
    write(out / "equipment-field.json", dict(field=field, call=call, wrapper=wrapper))
    print("known equipment field", field["SHA256"], "no new text or glyphs")


def evidence(root, out):
    assert not (out / "evidence.json").exists()
    proof = read(out / "check-r3.json")
    assert proof["gpu_pairs"] == 355 and proof["battlefield_restored"] and proof["new_weapon_fallbacks"] == 0
    tests = (out / "weapon-tests-r1.log").read_text()
    assert "PASS" in tests and "FAIL" not in tests and "SKIP" not in tests
    assert all(read(out / "scope-equality.json").values())
    names = {"weapon_hud_inputs.py", "weapon_hud_check.py", "ui_hud_weapon_test.go", "research_storage.py",
             "ui-list-live.sh", "early-live.sh", "battle_text.py", "cold_load.py", "load_prompt_inputs.py",
             "original_prefix_check.py", "original_prefix_inputs.py", "passage_runtime_inputs.py",
             "passage_chain_inputs.py", "text_catalog.py", "translation_check.py",
             "oracle_video_observer.go", "oracle_input_modifier.go"}
    names.update(p.name for p in (out / "programs-r3").glob("*.go"))
    target = out / "tool-snapshots"
    assert not target.exists()
    target.mkdir()
    for name in sorted(names):
        shutil.copyfile(root / "tools" / name, target / name)
    sources = [root / "workplace/input/dos/drkqueen" / n for n in ("DQK.EXE", "DISK3/ECL.GLB")]
    sources.extend(root / "workplace/translation" / n for n in ("en.tsv", "zh-TW.tsv", "catalog.json", "glossary.tsv", "glossary-additions.tsv"))
    parent = root / "workplace/probe/passage-runtime-20261025"
    sources.extend(parent / n for n in ("evidence.json", "programs-r2/ui-list-live", "girl-observe-r3/final.state"))
    sources.extend(p for p in (parent / "inputs-r2").iterdir() if p.is_file())
    sources.extend(root / "workplace/probe" / n for n in ("combat-aim-route-20261024/programs-r3/ui-context-probe",
                   "combat-hud-20261024/observe-r3/receipt.json"))
    write(out / "evidence.json", dict(draft=True, state="SEALED", summary=proof,
          artifacts={str(p.relative_to(out)): record(p) for p in sorted(out.rglob("*")) if p.is_file()},
          sources={str(p.relative_to(root)): record(p) for p in sources},
          tools={n: record(target / n) for n in sorted(names)},
          previous_glossary=dict(origin="/home/anr2/cht/golden_box/death_knight_of_krynn/text/glossary.tsv",
                                 record=record(Path("/previous-text/glossary.tsv"))),
          limits="44 個既有物品詞作受限武器欄詞表；正常抽兩次杖投石索及 View／Exit，不代表全部名稱已走訪或完整中文化。"))
    audit(root, out)


def audit(root, out):
    index = read(out / "evidence.json")
    assert index["state"] == "SEALED"
    for name, expected in index["artifacts"].items():
        assert record(out / name) == expected, name
    for name, expected in index["sources"].items():
        assert record(root / name) == expected, name
    for name, expected in index["tools"].items():
        assert record(out / "tool-snapshots" / name) == expected, name
    assert record(Path("/previous-text/glossary.tsv")) == index["previous_glossary"]["record"]
    print("sealed audit", {k: len(index[k]) for k in ("artifacts", "sources", "tools")})


if __name__ == "__main__":
    mode, project, directory = sys.argv[1:]
    if mode not in ("prepare", "samples", "guards", "return_samples", "equipment", "evidence", "audit"):
        raise ValueError(mode)
    globals()[mode](Path(project), Path(directory))
