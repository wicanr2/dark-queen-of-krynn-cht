#!/usr/bin/env python3
"""核對原始定位、MZ relocation 與建置來源，不執行遊戲。"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys

root, output = map(Path, sys.argv[1:])
assert output.is_dir() and output.stat().st_uid == 1000
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

exe = root / "workplace/input/dos/drkqueen/DQK.EXE"
bindings = root / "docs/spec/005-render-hooks.json"
j = json.loads(bindings.read_text())
assert sha(exe) == j["ExecutableSHA256"] == "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
assert j["Version"] == 2 and len(j["Hooks"]) == 36 and len(j["NativeSteps"]) == 65
b = exe.read_bytes()
header = struct.unpack_from("<H", b, 8)[0] * 16
reloc = []
for i in range(struct.unpack_from("<H", b, 6)[0]):
    off, seg = struct.unpack_from("<HH", b, struct.unpack_from("<H", b, 24)[0] + i * 4)
    reloc.append(header + seg * 16 + off)
points = j["Hooks"] + j["NativeSteps"] + [j[k] for k in ["ImageSource", "ImagePosition", "TextGlyph"]]
seen = set()
for point in points:
    off, ea = point["file_offset"], point["ida_linear"]
    assert off == ea - 0xdc00
    assert point["segment"] * 16 + point["offset"] + 0xef00 == ea
    assert ea not in seen
    seen.add(ea)
    raw = bytearray(b[off:off + 8])
    if "file_prefix" in point:
        assert raw.hex() == point["file_prefix"]
    for pos in reloc:
        if off <= pos < off + 7:
            struct.pack_into("<H", raw, pos - off, (struct.unpack_from("<H", raw, pos - off)[0] + 0x110) & 0xffff)
    assert raw.hex() == point["prefix"], point["name"]

profile = output / "inputs/player-profile.json"
manifest = json.loads(profile.read_text())
for name, want in manifest["Files"].items():
    assert sha(output / "inputs" / name) == want, name
assert sha(output / "inputs/render-hooks.json") == sha(bindings)
sources = [p for p in (root / "tools").glob("*.go") if p.name.startswith(("player_", "render_scene_", "ui_", "oracle_", "machine_"))]
sources += [root / "tools" / n for n in ["early_text_live.go", "picture_text.go", "picture_text_inputs.py", "manual_world_map.py", "manual_map_inputs.py", "guide_inputs.py", "player.sh", "player_inputs.py", "player_video_overlay.py", "player_render_check.py"]]
sources += [root / "tools" / n for n in ["music_cues.go", "player_music_inputs.py", "player_ui_contract.py"]]
sources += [root / "tools" / n for n in ["completion_audit.py", "player_sources.txt"]]
sources += [root / "tools/text_hd_inputs.py"]
# 2026-10-31原收據與戰鬥快照已刪，以verify-base冷啟動正常快照重跑1652組。
base_receipt_path = root / "workplace/probe/verify-base-20261031-r2/base/receipt.json"
base_snapshot = base_receipt_path.parent / "palanthas.state"
base_snapshot_sha = None
if base_receipt_path.is_file() and base_snapshot.is_file():
    base_receipt = json.loads(base_receipt_path.read_text())
    if base_receipt.get("exe_sha256") == sha(exe) and base_receipt["states"]["palanthas.state"]["sha256"] == sha(base_snapshot):
        base_snapshot_sha = sha(base_snapshot)
abi_root = root / "workplace/probe/render-abi-rebuild-20261031-r1"
abi_path = abi_root / "evidence.json"
verified = False
if abi_path.is_file():
    abi = json.loads(abi_path.read_text())
    verified = (abi.get("passed") is True and abi.get("machine_effects_verified") is True
                and abi.get("virtual_time_verified") is True and abi.get("cases") == 1652
                and abi.get("inputs", {}).get("original_exe") == sha(exe)
                and abi.get("inputs", {}).get("bindings") == sha(bindings)
                and base_snapshot_sha is not None and abi.get("inputs", {}).get("normal_source_snapshot") == base_snapshot_sha
                and abi.get("receipt_sha256") == sha(abi_root / "abi-initial.json")
                and all(sha(root / "tools" / name) == abi.get("sources", {}).get(name) for name in [
                    "player_owned_drivers.go", "render_scene_state.go", "player_video_overlay.py",
                    "machine_presentation_video.go", "oracle_presentation_video.go", "oracle_video_observer.go"]))
    cases=json.loads((abi_root / "abi-initial.json").read_text())
    verified = verified and len(cases)==1652 and all(
        row.get("Passed") is True and ("reject" in row["Name"] or row["DirectWrites"]==0)
        for row in cases)
# 介面契約只採本次check-ui在同一整合目錄重跑的結果，並要求建置後來源未再變動。
ui_path = output / "ui-contract.json"
ui_verified = False
if ui_path.is_file() and (output / "ui-tests.json").is_file():
    ui = json.loads(ui_path.read_text())
    ui_verified = (ui.get("version") == 2 and ui.get("passed") is True and ui.get("cases") == 16
                   and ui.get("quiz_guard_cases") == 3 and ui.get("camp_guard_cases") == 2
                   and ui.get("quiz_footer_guard_cases") == 3 and ui.get("quiz_enter_retire_cases") == 2
                   and ui.get("machine_effects_unchanged") is True and ui.get("virtual_time_unchanged") is True
                   and ui.get("tests_sha256") == sha(output / "ui-tests.json")
                   and base_snapshot_sha is not None and ui.get("normal_source_snapshot_sha256") == base_snapshot_sha
                   and ui.get("base_receipt_sha256") == sha(base_receipt_path)
                   and len(ui.get("sources", {})) > 0
                   and all((root / name).is_file() and sha(root / name) == digest for name, digest in ui["sources"].items())
                   and all(ui["sources"].get("tools/" + name) == sha(root / "tools" / name) for name in [
                       "ui_cold_prompts.go", "ui_list_live.go", "player_render_owner.go", "early_text_live.go", "ui_cold_fill_test.go"]))
player_sample = root / "workplace/probe/player-sample-canvas-complete-20261026-r1/checks.json"
for candidate in sorted((root / "workplace/probe").glob("player-sample-*/checks.json")):
    candidate_data=json.loads(candidate.read_text())
    if candidate_data.get("passed") is True and candidate_data.get("build_sha256")==sha(output / "dqk-player"):
        player_sample=candidate
sample = json.loads(player_sample.read_text()) if player_sample.is_file() else {}
sample_verified = sample.get("passed") is True and sample.get("build_sha256") == sha(output / "dqk-player")
info = {
    "state": "READY" if verified and ui_verified else "DRAFT",
    "ui_observer_irq_verified": ui_verified,
    "ui_observer_contract_sha256": sha(ui_path) if ui_verified else None,
    "native_effects_verified": verified,
    "virtual_time_accounting_verified": verified,
    "function_evidence_sha256": sha(abi_path) if abi_path.is_file() else None,
    "normal_player_sample_verified": sample_verified,
    "normal_player_sample_scope": sample.get("scope", []) if sample_verified else [],
    "normal_player_sample_sha256": sha(player_sample) if sample_verified else None,
    "render_backend": "GPU texture and rectangle batches; CPU pixel reference in pure tests",
    "date": datetime.now(timezone.utc).isoformat(),
    "binary_sha256": sha(output / "dqk-player"),
    "sdk_commit": "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8",
    "go": "1.24.13",
    "profile_files": len(manifest["Files"]),
    "profile_sha256": sha(profile),
    "sources": {**{p.name: sha(p) for p in sorted(sources)},
                **{"windowbridge/"+p.name:sha(p) for p in sorted((root/"tools/windowbridge").iterdir()) if p.is_file()}},
    "render_hooks_sha256": sha(bindings),
    "verified_resident_points": len(points),
    "native_steps": len(j["NativeSteps"]),
    "sdk_overlay": {p.name: sha(p) for p in sorted((output / "build-overlay").glob("*.go"))},
    "new_gameplay_verification": sample_verified,
    "new_gui_sampling": sample_verified,
    "whole_game_takeover_complete": False,
    "go_canvas_presenter": True,
    "legacy_screen_rgb_fallback": False,
    "known_valid_command_native_writes": 0 if verified else None,
    "transparent_resume_verified": verified,
}
sample_correction = player_sample.with_name("label-correction.json")
if sample_verified and sample_correction.is_file():
    correction = json.loads(sample_correction.read_text())
    if correction.get("source_sha256") == sha(player_sample) and isinstance(correction.get("scope"), list):
        info["normal_player_sample_scope"] = correction["scope"]
        info["normal_player_sample_correction_sha256"] = sha(sample_correction)
picture_manifest = output / "picture-text/manifest.json"
music_manifest = output / "music/manifest.json"
info['music_tracks'] = 0
info['music_listening_verified'] = False
if music_manifest.is_file():
    music = json.loads(music_manifest.read_text())
    music_valid = (music.get('schema') == 1 and music.get('sample_rate') == 48000
                   and music.get('channels') == 2 and len(music.get('tracks', [])) == 8)
    music_valid = music_valid and all(
        '/' not in t['key'] and '..' not in t['key']
        and (output/'music'/(t['key']+'.ogg')).is_file()
        and sha(output/'music'/(t['key']+'.ogg')) == t['ogg_sha256'] for t in music['tracks'])
    info['music_assets_verified'] = music_valid
    info['music_manifest_sha256'] = sha(music_manifest)
    info['music_tracks'] = 8 if music_valid else 0
if picture_manifest.is_file():
    pictures = json.loads(picture_manifest.read_text())
    assert pictures["Version"] == 1 and len(pictures["Bindings"]) == 24
    for name, want in pictures["Files"].items():
        assert name in {"en.tsv", "zh-TW.tsv", "glyphs.json"}
        assert sha(output / "picture-text" / name) == want
    for locale in ["en", "zh-TW"]:
        assert sha(output / "picture-text" / (locale + ".tsv")) == sha(root / "text" / ("image-text." + locale + ".tsv"))
    info["picture_text_manifest_sha256"] = sha(picture_manifest)
    info["picture_text_bindings"] = len(pictures["Bindings"])
    info["picture_text_captions"] = sum(len(b["Captions"]) for b in pictures["Bindings"])
guide_index = output / "inputs/guide-index.json"
if guide_index.is_file():
    guide = json.loads(guide_index.read_text())
    assert guide['version'] == 1 and guide['complete'] and guide['map_count'] == 52
    assert len(guide['books']) == 20 and sum(len(b['documents']) for b in guide['books']) == 72
    info['guide_maps'], info['guide_chapters'], info['guide_documents'] = 52, 18, 72
    info['guide_index_sha256'] = sha(guide_index)
    info['guide_catalog_sha256'] = sha(output / 'inputs/guide.zh-TW.tsv')
    info['guide_provenance_sha256'] = sha(output / 'inputs/guide-provenance.json')
(output / "build-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: info[k] for k in ["binary_sha256", "verified_resident_points", "native_steps", "profile_files", "new_gameplay_verification"]}))
