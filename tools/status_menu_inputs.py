"""人物資料頁三種已觀測表形的情境翻譯與代表性抽驗。"""
import base64
import csv
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

from PIL import Image
from original_prefix_check import catalog, image, read
from passage_runtime_inputs import record, sha, write

PARENT = "weapon-hud-20261025/inputs-r4"
SOURCES = {
    "c8e6a5099c5cec86a73756c7edc06264de1214283e1a33480d631e42ab259456": "ammo-boundaries-20261024/bolts-observe-r1/receipt.json",
    "7f64b83332ab0f1c6041c30a354332372fdbcec1ebacca5f8ace5c772c23af38": "creation-20261024/observe-r2/receipt.json",
    "02b12afcec7ad80572357eac11f9544fa509c197a8d87dd98524d89c284f145c": "weapon-hud-20261025/observe-r2/receipt.json",
}
KEYS = {"Items": "field.fb8e7a1a3cb7b25d2627", "Spells": "field.6a0a0288ac6b0b743b5b",
        "Trade": "status-menu.trade-money", "Drop": "status-menu.drop-money",
        "Exit": "field.d17d84a604994b722db3"}


def prepare(root, out):
    assert not (out / "evidence.json").exists()
    probe = root / "workplace/probe"
    parent = probe / PARENT
    cfg = read(parent / "inputs.json")
    en, zh = [catalog(parent / n) for n in ("en.tsv", "zh-TW.tsv")]
    with (out / "status-menu.zh-TW.tsv").open() as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    assert len(rows) == 2 and {r["key"] for r in rows} == {KEYS["Trade"], KEYS["Drop"]}
    glyphs = read(parent / "glyphs-16.json")["glyphs"]
    for row in rows:
        k = row["key"]
        assert k not in en and k not in zh and row["en"] in ("Trade", "Drop")
        assert 0 < len(row["zh-TW"]) <= len(row["en"]) and set(row["zh-TW"]) <= glyphs.keys()
        en[k], zh[k] = row["en"], row["zh-TW"]
    data = {}
    old_fields = cfg["Fields"]
    cfg["Fields"] = [f for f in old_fields if f.get("MenuSignature") not in SOURCES]
    for sig, source in SOURCES.items():
        trace = read(probe / source)
        m = next(m for m in trace["menus"] if m["Signature"] == sig)
        buttons = m["Buttons"]
        assert m["Count"] == len(buttons)+1 and [b["Index"] for b in buttons] == list(range(1, m["Count"]))
        encoding = [m["Count"], [[b[k] for k in ("Index", "SHA256", "RawX", "RawY")] for b in buttons]]
        assert hashlib.sha256(json.dumps(encoding, separators=(",", ":")).encode()).hexdigest() == sig
        raw, fields = bytes.fromhex(m["RawHex"]), []
        for b in buttons:
            text = bytes.fromhex(b["SourceHex"]).decode("ascii")
            assert text in KEYS and hashlib.sha256(text.encode()).hexdigest() == b["SHA256"]
            at = b["Index"]*32
            assert struct.unpack_from("<HH", raw, at) == (0x8e, 0xceb)
            assert struct.unpack_from("<HH", raw, at+12) == (b["SourcePointer"]["Off"], b["SourcePointer"]["Seg"])
            assert struct.unpack_from("<HH", raw, at+16) == (b["RawY"], b["RawX"])
            assert b["RawY"] == 8094
            fields.append(dict(Pane="menu", Group="footer", Key=KEYS[text], Start=0, Length=len(text),
                               SHA256=b["SHA256"], FormatSHA256=b["SHA256"], Caller=dict(Seg=0xceb, Off=0x1be),
                               RawX=(b["RawX"]-8000)*2, RawY=189, MenuSignature=sig))
        # 已知表形保留原分類；新戰鬥資料頁沿既有 status 分類。
        cfg["Menus"].setdefault(sig, "status")
        cfg["Fields"].extend(fields)
        data[sig] = dict(source=source, menu=m, fields=fields)
    target = out / "inputs-r1"
    assert not target.exists()
    shutil.copytree(parent, target)
    for name, values in (("en.tsv", en), ("zh-TW.tsv", zh)):
        (target / name).write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k, v in sorted(values.items())))
    trace = read(probe / SOURCES[list(SOURCES)[-1]])
    calls = [c for c in trace["calls"] if c["caller"] == dict(Seg=0xceb, Off=0x1be)
             and trace["menus"][c["menu_index"]]["Signature"] == list(SOURCES)[-1]]
    assert len(calls) == 5  # 四鈕初印及返回前 Exit 反白重印。
    cfg["fine_windows"].extend([c[k]-2000, c[k]+4000] for c in calls for k in ("step", "first_glyph", "return_step"))
    write(target / "inputs.json", cfg)
    write(out / "bindings.json", data)
    shutil.copyfile(probe / "weapon-hud-20261025/request-r4.json", out / "battle-request.json")
    state = probe / "ammo-boundaries-20261024/bolts-observe-r1/final.state"
    write(out / "city-request.json", dict(state_sha256=sha(state), start_steps=885000000,
          actions=[dict(at=886000000, end=905000000, kind="text", key="e", label="city-status"),
                   dict(at=906000000, end=925000000, kind="text", key="e", label="city-return")]))
    write(out / "provenance.json", dict(parent=PARENT, parent_record=record(parent / "inputs.json"),
          menus=data, translations=record(out / "status-menu.zh-TW.tsv"),
          manual=record(root / "workplace/manual-ocr/Image024-right.png")))
    print("three menu signatures; 13 bindings; two context-specific TSV rows; glyphs unchanged")


def samples(root, out):
    """沿兩次正常 Exit 取得的原版時序追加細驗範圍，不擴大重播。"""
    a, b = [read(out / n / "receipt.json") for n in ("city-observe", "city-control")]
    assert a["checkpoints"] == b["checkpoints"]
    assert sha(out / "city-observe/final.state") == sha(out / "city-control/final.state")
    calls = [c for c in a["calls"] if c["caller"] == dict(Seg=0xceb, Off=0x1be)
             and a["menus"][c["menu_index"]]["Signature"] in SOURCES]
    assert len(calls) >= 5 and {a["menus"][c["menu_index"]]["Signature"] for c in calls} == {next(iter(SOURCES))}
    cfg = read(out / "inputs-r1/inputs.json")
    cfg["fine_windows"].extend([c[k]-2000, c[k]+4000] for c in calls for k in ("step", "first_glyph", "return_step"))
    write(out / "inputs-r1/inputs.json", cfg)
    write(out / "city-sources.json", calls)
    print("normal city status menu calls", len(calls))


def check(root, out):
    cfg = read(out / "inputs-r1/inputs.json")
    parent = root / "workplace/probe" / PARENT
    before = read(parent / "inputs.json")
    assert {k:v for k,v in cfg.items() if k not in ("Menus", "Fields", "fine_windows")} == {
        k:v for k,v in before.items() if k not in ("Menus", "Fields", "fine_windows")}
    assert [f for f in cfg["Fields"] if f.get("MenuSignature") not in SOURCES] == [
        f for f in before["Fields"] if f.get("MenuSignature") not in SOURCES]
    for sig, kind in before["Menus"].items():
        assert cfg["Menus"][sig] == kind
    bindings = read(out / "bindings.json")
    assert [f for f in cfg["Fields"] if f.get("MenuSignature") in SOURCES] == [
        f for data in bindings.values() for f in data["fields"]]
    for p in parent.iterdir():
        if p.is_file() and p.name not in ("inputs.json", "provenance.json", "en.tsv", "zh-TW.tsv"):
            assert sha(p) == sha(out / "inputs-r1" / p.name), p.name
    en, zh = [catalog(out / "inputs-r1" / n) for n in ("en.tsv", "zh-TW.tsv")]
    for name, values in (("en.tsv", en), ("zh-TW.tsv", zh)):
        previous = catalog(parent / name)
        assert all(values[k] == v for k,v in previous.items())
        assert set(values)-set(previous) == {KEYS["Trade"], KEYS["Drop"]}
    glyphs = read(out / "inputs-r1/glyphs-16.json")
    masks = {k: Image.frombytes("L", (16,20), base64.b64decode(v)) for k,v in glyphs["glyphs"].items()}
    summaries = {}
    for route in ("city", "battle"):
        native_dir = out / "city-control" if route == "city" else root / "workplace/probe/weapon-hud-20261025/control-r5"
        native = read(native_dir / "receipt.json")
        a, b = [read(out / (route+"-"+lang) / "receipt.json") for lang in ("en", "zh")]
        assert a["list_request_sha256"] == b["list_request_sha256"] == sha(out / (route+"-request.json"))
        assert a["list_inputs_sha256"] == b["list_inputs_sha256"] == sha(out / "inputs-r1/inputs.json")
        assert not a["unimplemented"] and not b["unimplemented"]
        assert len(a["checkpoints"]) == len(b["checkpoints"]) == len(native["checkpoints"])
        fields = ("regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes", "step", "label")
        for run in (a,b):
            for cp, orig in zip(run["checkpoints"], native["checkpoints"]):
                assert all(cp[k] == orig[k] for k in fields), orig["label"]
                assert not cp["file_writes"]
        events = [e for e in b["list_events"] if e["Kind"] == "field-before-glyph"
                  and e["detail"]["word"].get("Button") and e["detail"]["word"]["Key"] in KEYS.values()
                  and e["detail"].get("menu_signature") in SOURCES]
        assert len(events) >= (5 if route == "city" else 4)
        assert all(e["Step"] < e["first_glyph"] for e in events)
        af, bf = a["frames"], b["frames"]
        assert [f["step"] for f in af] == [f["step"] for f in bf]
        metadata = {f["step"]:f for f in b["list_frames"]}
        cps = {c["step"]:c for c in native["checkpoints"]}
        sig = next(iter(SOURCES)) if route == "city" else list(SOURCES)[-1]
        target_fields = bindings[sig]["fields"]
        seen, held, last, restored = {k:0 for k in KEYS.values()}, 0, None, 0
        for x,y in zip(af,bf):
            english = image(out / (route+"-en") / x["File"])
            chinese = image(out / (route+"-zh") / y["File"])
            for f,im in ((x,english),(y,chinese)):
                assert hashlib.sha256(im.convert("RGBA").tobytes()).hexdigest() == f["SHA256"]
            step = y["step"]
            if step in cps:
                orig = image(native_dir / (cps[step]["label"]+".png")).resize((640,400), Image.Resampling.NEAREST)
                assert english.tobytes() == orig.tobytes()
            if y["held"]:
                assert last is not None and y["SHA256"] == last["SHA256"], step
                held += 1
            else:
                meta = metadata[step]
                assert not meta["paragraph"]
                expected = english.copy()
                for w in meta["words"] or []:
                    xx,yy,width,height = w["X"]*2,w["Y"]*2,w["Width"]*2,w.get("Height",8)*2
                    bg,fg = [tuple(meta["palette"][w[n]]) for n in ("Background","Foreground")]
                    expected.paste(bg,(xx,yy,xx+width,yy+height))
                    text = zh[w["Key"]]
                    if "Number" in w:
                        text = text.replace("%d",str(w["Number"]))
                    assert len(text)*16 <= width
                    for i,ch in enumerate(text):
                        expected.paste(fg,(xx+i*16,yy,xx+(i+1)*16,yy+20),masks[ch])
                    if w.get("Button") and any((w["Key"],w["X"],w["Y"]) == (f["Key"],f["RawX"],f["RawY"])
                                               for f in target_fields):
                        seen[w["Key"]] += 1
                assert chinese.tobytes() == expected.tobytes(), (route,step)
                if route == "battle" and step >= 15667605024:
                    assert chinese.crop((0,0,368,354)).tobytes() == english.crop((0,0,368,354)).tobytes()
                    assert chinese.crop((544,112,624,128)).tobytes() == english.crop((544,112,624,128)).tobytes()
                    restored += 1
            last = y
        required = set(KEYS.values()) if route == "city" else set(KEYS.values())-{KEYS["Trade"]}
        assert all(seen[k] for k in required)
        final_words = metadata[bf[-1]["step"]]["words"] or []
        assert not any((w["Key"],w["X"],w["Y"]) == (f["Key"],f["RawX"],f["RawY"])
                       for w in final_words for f in target_fields)
        assert route != "battle" or restored > 0
        summaries[route] = dict(gpu_pairs=len(bf), checkpoints=len(native["checkpoints"]), held=held,
                                visible_buttons=seen, early_button_events=len(events), returned=True,
                                restored_battle_and_bonus_samples=restored)
    write(out / "check.json", dict(routes=summaries, menu_signatures=3, bindings=13, new_context_keys=2,
          original_state_equal=True, original_catalog_rows_preserved=True, glyphs_unchanged=True,
          limits="兩條正常代表路徑；無法術的建角表形只核來源，未新增完整重播。"))
    print(read(out / "check.json"))


def seal(root, out):
    assert not (out / "evidence.json").exists()
    assert read(out / "check.json")["original_state_equal"]
    sources = [root / "workplace/probe" / p for p in SOURCES.values()]
    sources += [root / "workplace/manual-ocr/Image024-right.png",
                root / "workplace/probe/weapon-hud-20261025/programs-r3/ui-list-live",
                root / "workplace/probe/weapon-hud-20261025/control-r5/receipt.json",
                root / "workplace/probe/passage-runtime-20261025/girl-observe-r3/final.state",
                root / "workplace/probe/ammo-boundaries-20261024/bolts-observe-r1/final.state",
                root / "workplace/probe/combat-aim-route-20261024/programs-r3/ui-context-probe",
                root / "workplace/input/dos/drkqueen/DQK.EXE",
                root / "workplace/input/dos/drkqueen/DISK3/ECL.GLB"]
    sources.extend(p for p in (root / "workplace/probe" / PARENT).iterdir() if p.is_file())
    names=("status_menu_inputs.py", "original_prefix_check.py", "passage_runtime_inputs.py",
           "passage_chain_inputs.py", "original_prefix_inputs.py", "text_catalog.py")
    snapshots=out / "tool-snapshots"
    snapshots.mkdir()
    for name in names:
        shutil.copyfile(root / "tools" / name,snapshots / name)
    write(out / "evidence.json", dict(state="SEALED", draft=True, summary=read(out / "check.json"),
          artifacts={str(p.relative_to(out)):record(p) for p in sorted(out.rglob("*")) if p.is_file()},
          sources={str(p.relative_to(root)):record(p) for p in sources},
          tools={n:record(snapshots / n) for n in names}))
    print("sealed",len(read(out / "evidence.json")["artifacts"]),"artifacts")
    audit(root,out)


def audit(root,out):
    index=read(out / "evidence.json")
    assert index["state"] == "SEALED"
    for path,expected in index["artifacts"].items():
        assert record(out / path) == expected,path
    for path,expected in index["sources"].items():
        assert record(root / path) == expected,path
    for name,expected in index["tools"].items():
        assert record(out / "tool-snapshots" / name) == expected,name
    print("audit passed",len(index["artifacts"]),"artifacts")


if __name__ == "__main__":
    mode, project, directory = sys.argv[1:]
    assert mode in ("prepare", "samples", "check", "seal", "audit")
    globals()[mode](Path(project), Path(directory))
