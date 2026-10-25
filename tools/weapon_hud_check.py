"""以原版來源、原版畫面與實際 GPU 抽驗武器及資料頁返回。"""
import base64
import hashlib
from pathlib import Path
import sys

from PIL import Image
from original_prefix_check import catalog, image, read
from passage_runtime_inputs import sha, write
from weapon_hud_inputs import MENU, PARENT, derive


def check(root, out):
    inputs = out / "inputs-r4"
    cfg, data = derive(root, out)
    current = read(inputs / "inputs.json")
    equipment = read(out / "equipment-field.json")
    cfg["Fields"].append(equipment["field"])
    assert {k: v for k, v in cfg.items() if k != "fine_windows"} == {k: v for k, v in current.items() if k != "fine_windows"}
    parent = root / "workplace/probe" / PARENT
    for p in parent.iterdir():
        if p.is_file() and p.name not in ("inputs.json", "provenance.json"):
            assert sha(p) == sha(inputs / p.name), p.name
    assert len(data["vocabulary"]) == 44 and len(data["fields"]) == 8
    en, zh = catalog(inputs / "en.tsv"), catalog(inputs / "zh-TW.tsv")
    native, control = [read(out / n / "receipt.json") for n in ("observe-r5", "control-r5")]
    assert native["checkpoints"] == control["checkpoints"]
    assert sha(out / "observe-r5/final.state") == sha(out / "control-r5/final.state")
    assert all(not v for k, v in native.items() if k.startswith("pending_"))
    assert len(native["checkpoints"]) == 135
    # 新增截點保留先前取得的完整原版來源及粗粒度狀態。
    coarse = read(out / "observe-r2/receipt.json")
    for key in ("calls", "paragraphs", "menus", "fill_events", "display_changes", "hud_panels"):
        assert native[key] == coarse[key], key
    equipment_call = next(c for c in native["calls"] if c["step"] == equipment["call"]["step"])
    assert equipment_call == equipment["call"]
    by_label = {c["label"]: c for c in native["checkpoints"]}
    assert all(by_label[c["label"]] == c for c in coarse["checkpoints"])
    a, b, old = [read(out / n / "receipt.json") for n in ("en-r5", "zh-r5", "old-zh-r5")]
    fields = ("regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes", "step", "label")
    start = root / "workplace/probe/passage-runtime-20261025/girl-observe-r3/final.state"
    for run in (a, b, old):
        assert run["initial_state_sha256"] == sha(start)
        assert run["list_request_sha256"] == sha(out / "request-r4.json")
        assert run["list_inputs_sha256"] == sha(inputs / "inputs.json")
        assert len(run["checkpoints"]) == 135 and not run["unimplemented"]
        assert not run["reader_seen"] and not run["reader_ui_events"]
        for cp, orig in zip(run["checkpoints"], control["checkpoints"]):
            assert all(cp[k] == orig[k] for k in fields), orig["label"]
            assert not orig["file_writes"] and not orig["unimplemented"]
        assert run["ram_sha256"] == control["checkpoints"][-1]["ram_sha256"]
    key = next(v["key"] for v in data["vocabulary"] if v["name"] == "Staff Sling")
    weapons = data["weapons"]
    entries = [e for e in b["list_events"] if e["Kind"] == "hud-before-glyph"]
    assert len(entries) == 2
    for original, entry in zip(weapons, entries):
        assert entry["Step"] == original["step"] < entry["first_glyph"] == original["first_glyph"] < original["return_step"]
        assert entry["detail"]["source_sha256"] == hashlib.sha256(original["source"]["text"].encode()).hexdigest()
        assert entry["detail"]["spans"] == [dict(Start=0, Length=11, Key=key, Rect=[184, 56, 88, 8])]
    equipment_event = next(e for e in b["list_events"] if e["Kind"] == "field-before-glyph" and e["Step"] == equipment_call["step"])
    assert equipment_event["detail"]["word"]["Key"] == key
    assert equipment_event["first_glyph"] == equipment_call["first_glyph"] > equipment_call["step"]
    unknown = [e for e in b["list_events"] if e["Kind"] == "unknown-paragraph-original"]
    assert [e["Step"] for e in unknown] == [p["step"] for p in data["clears"]]
    assert all(p["source"]["text"] == " " for p in data["clears"])
    assert len([e for e in old["list_events"] if e["Kind"] == "unknown-paragraph-original"]) == 4
    sampling = read(out / "return-sampling.json")
    fill = sampling["native_fill"]
    closed = [e for e in b["list_events"] if e["Kind"] == "status-view-closed"]
    assert len(closed) == 1 and closed[0]["Step"] == fill["converted_step"]
    assert closed[0]["detail"]["native_rect"] == fill["native_rect"] == [184, 8, 128, 168]
    assert closed[0]["Step"] < next(v["step"] for v in sampling["display_changes"] if v["layout"]["DisplayStart"] == 0)
    marker = [e for e in b["list_events"] if e["Kind"] == "status-view-header"]
    assert len(marker) == 1
    native_marker = [c for c in native["calls"] if c["step"] == marker[0]["Step"]]
    assert len(native_marker) == 1 and native_marker[0]["vararg_1_candidate"]["text"] == en["field.755c8b2a9fb114460e09"]
    buttons = {f["Key"]: f for f in data["fields"]}
    expected_keys = set(buttons) | {key, "ui.c35ed1964164e1c292c9", "battle.ac"}
    frames = [run["frames"] for run in (a, b, old)]
    assert [f["step"] for f in frames[0]] == [f["step"] for f in frames[1]] == [f["step"] for f in frames[2]]
    metadata = {f["step"]: f for f in b["list_frames"]}
    previous_meta = {f["step"]: f for f in old["list_frames"]}
    cps = {c["step"]: c for c in control["checkpoints"]}
    glyphs = read(inputs / "glyphs-16.json")
    masks = {k: Image.frombytes("L", (16, 20), base64.b64decode(v)) for k, v in glyphs["glyphs"].items()}
    images, composed = {}, {}
    def gpu(name, frame):
        identity = name, frame["File"]
        if identity not in images:
            im = image(out / name / frame["File"])
            assert hashlib.sha256(im.convert("RGBA").tobytes()).hexdigest() == frame["SHA256"]
            images[identity] = im
        return images[identity]
    seen_buttons = {k: 0 for k in buttons}
    held = visible_weapon = view = cleared = retained_suffix = old_stale = status_weapon = 0
    last = None
    menu_calls = [c for c in native["calls"] if c["caller"] == dict(Seg=0x0ceb, Off=0x01be) and
                  native["menus"][c["menu_index"]]["Signature"] == MENU]
    return_done = max(c["return_step"] for c in menu_calls)
    for x, y, z in zip(*frames):
        english, chinese, legacy = gpu("en-r5", x), gpu("zh-r5", y), gpu("old-zh-r5", z)
        step = y["step"]
        if step in cps:
            cp = cps[step]
            expected = image(out / "control-r5" / (cp["label"]+".png")).resize((640, 400), Image.Resampling.NEAREST)
            assert english.tobytes() == expected.tobytes(), ("original GPU", step)
        painting = any(p["step"] <= step <= p["return_step"] for p in weapons)
        restoring = fill["converted_step"] <= step <= return_done
        if y["held"] or painting or restoring:
            assert last is not None and y["SHA256"] == last["SHA256"], ("hold", step)
            held += 1
        else:
            meta = metadata[step]
            assert meta["paragraph"] is None
            words = meta["words"] or []
            identity = x["File"], tuple((w["X"], w["Y"], w["Width"], w["Key"], w["Foreground"], w["Background"], w.get("Height", 8), w.get("Number")) for w in words)
            if identity not in composed:
                expected = english.copy()
                for w in words:
                    assert w.get("FontSize", 16) in (0, 16)
                    xx, yy, width, height = w["X"]*2, w["Y"]*2, w["Width"]*2, w.get("Height", 8)*2
                    assert 0 <= xx < xx+width <= 640 and 0 <= yy < yy+height <= 400
                    bg, fg = [tuple(meta["palette"][w[n]]) for n in ("Background", "Foreground")]
                    expected.paste(bg, (xx, yy, xx+width, yy+height))
                    text = zh[w["Key"]]
                    if "Number" in w:
                        text = text.replace("%d", str(w["Number"]))
                    assert len(text)*16 <= width
                    for i, ch in enumerate(text):
                        expected.paste(fg, (xx+i*16, yy, xx+(i+1)*16, yy+20), masks[ch])
                composed[identity] = expected.tobytes()
            assert chinese.tobytes() == composed[identity], ("glyphs or unexpected overlay", step)
            active = next((w for w in words if w["Key"] == key and (w["X"], w["Y"]) == (184, 56)), None)
            if active:
                assert active == dict(X=184, Y=56, Width=88, Key=key, Group="body", Foreground=7, Background=23)
                assert chinese.crop((544, 112, 624, 128)).tobytes() == english.crop((544, 112, 624, 128)).tobytes()
                assert len(set(english.crop((544, 112, 624, 128)).getdata())) > 1
                retained_suffix += 1
                visible_weapon += 1
                # 戰場是原版圖形；既有資料頁文字不能在返回後覆蓋人物。
                assert chinese.crop((0, 0, 368, 354)).tobytes() == english.crop((0, 0, 368, 354)).tobytes(), ("battlefield residue", step)
                for k, f in buttons.items():
                    found = next((w for w in words if w["Key"] == k and w.get("Button")), None)
                    assert found and (found["X"], found["Y"]) == (f["RawX"], f["RawY"])
                    seen_buttons[k] += 1
                if step > return_done:
                    cleared += 1
                    old_stale += legacy.crop((0, 0, 368, 354)).tobytes() != english.crop((0, 0, 368, 354)).tobytes()
            elif 15666000000 <= step < fill["converted_step"]:
                assert words == previous_meta[step]["words"] and y["SHA256"] == z["SHA256"]
                assert any(w["Key"] == key and (w["X"], w["Y"]) == (8, 168) and w["Width"] == 88 for w in words)
                assert chinese.crop((192, 336, 260, 352)).tobytes() == english.crop((192, 336, 260, 352)).tobytes()
                assert len(set(english.crop((192, 336, 260, 352)).getdata())) > 1
                status_weapon += 1
                view += 1
        last = y
    for step in (15646000000, 15686000000):
        assert {w["Key"] for w in metadata[step]["words"]} == expected_keys
    assert not any(w["Key"] == key and w["X"] == 184 for w in metadata[15666000000]["words"])
    assert held and visible_weapon and view and cleared and old_stale and status_weapon
    assert all(n > 0 for n in seen_buttons.values())
    write(out / "check-r3.json", dict(gpu_pairs=len(frames[1]), checkpoints=135, vocabulary=44,
          actual_weapon_sources=2, held_samples=held, visible_weapon_samples=visible_weapon,
          preserved_bonus_samples=retained_suffix, visible_buttons=seen_buttons,
          view_samples=view, status_weapon_samples=status_weapon, restored_battle_samples=cleared, old_residue_samples=old_stale,
          blank_clear_paragraphs=2, old_weapon_fallbacks=2, new_weapon_fallbacks=0,
          original_cpu_ram_pixels_equal=True, battlefield_restored=True, catalogs_and_glyphs_unchanged=True,
          limits="單行武器共通契約、八鈕、資料頁返回的正常抽驗；詞表其餘名稱未逐一走訪，完整中文化未完成。"))
    print(read(out / "check-r3.json"))


if __name__ == "__main__":
    check(Path(sys.argv[1]), Path(sys.argv[2]))
