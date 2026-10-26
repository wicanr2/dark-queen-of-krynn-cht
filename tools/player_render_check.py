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
assert j["Version"] == 2 and len(j["Hooks"]) == 35 and len(j["NativeSteps"]) == 64
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
sources += [root / "tools" / n for n in ["early_text_live.go", "player.sh", "player_inputs.py", "player_video_overlay.py", "player_render_check.py"]]
abi_root = root / "workplace/probe/render-abi-canvas-complete-20261026-r1"
abi_path = abi_root / "evidence.json"
verified = False
if abi_path.is_file():
    abi = json.loads(abi_path.read_text())
    verified = (abi.get("passed") is True and abi.get("machine_effects_verified") is True
                and abi.get("virtual_time_verified") is True and abi.get("cases") == 1452
                and abi.get("inputs", {}).get("original_exe") == sha(exe)
                and abi.get("inputs", {}).get("bindings") == sha(bindings)
                and abi.get("receipt_sha256") == sha(abi_root / "abi-initial.json")
                and all(sha(root / "tools" / name) == abi.get("sources", {}).get(name) for name in [
                    "player_owned_drivers.go", "render_scene_state.go", "player_video_overlay.py",
                    "machine_presentation_video.go", "oracle_presentation_video.go", "oracle_video_observer.go"]))
    cases=json.loads((abi_root / "abi-initial.json").read_text())
    verified = verified and len(cases)==1452 and all(
        row.get("Passed") is True and ("reject" in row["Name"] or row["DirectWrites"]==0)
        for row in cases)
player_sample = root / "workplace/probe/player-sample-canvas-complete-20261026-r1/checks.json"
sample = json.loads(player_sample.read_text()) if player_sample.is_file() else {}
sample_verified = sample.get("passed") is True and sample.get("build_sha256") == sha(output / "dqk-player")
info = {
    "state": "READY" if verified else "DRAFT",
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
    "sources": {p.name: sha(p) for p in sorted(sources)},
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
}
(output / "build-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: info[k] for k in ["binary_sha256", "verified_resident_points", "native_steps", "profile_files", "new_gameplay_verification"]}))
