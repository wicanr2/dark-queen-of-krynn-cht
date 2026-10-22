"""檢查原版介面觀測及無觀測控制組，不生成譯文或修改原版狀態。"""

import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check(observed, control, output, role):
    if output.exists():
        raise ValueError("輸出必須全新")
    a = json.loads((observed / "receipt.json").read_text())
    b = json.loads((control / "receipt.json").read_text())
    assert a["draft"] and b["draft"] and a["observe"] and not b["observe"]
    for field in ("source_commit", "go_version", "exe_sha256", "state_sha256",
                  "request_sha256", "probe_sha256", "request", "checkpoints"):
        assert a[field] == b[field], field
    assert a["source_commit"] == "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8"
    assert a["exe_sha256"] == "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
    assert a["pending_calls"] == b["pending_calls"] == 0, "觀測呼叫尚未封閉"
    assert len(a["checkpoints"]) == len(a["request"]["actions"])
    images = []
    for checkpoint in a["checkpoints"]:
        assert not checkpoint["file_writes"] and not checkpoint["unimplemented"]
        label = checkpoint["label"]
        assert label and Path(label).name == label
        with Image.open(observed / (label + ".png")) as x, Image.open(control / (label + ".png")) as y:
            assert x.size == y.size == (320, 200)
            pixels = x.convert("RGB").tobytes()
            assert pixels == y.convert("RGB").tobytes(), label
            images.append({"label": label, "rgb_sha256": sha(pixels)})
    for folder in (observed, control):
        assert sha((folder / "ram.bin").read_bytes()) == a["checkpoints"][-1]["ram_sha256"]
    matches = []
    for index, call in enumerate(a["calls"]):
        source = call["vararg_1_candidate"]
        text = source["text"]
        matched = (role == "inventory" and re.fullmatch(r" (Yes|No)\tShield(?: \+\d+)? ", text))
        matched = matched or (role == "grimoire" and text == "\tShield")
        if not matched:
            continue
        assert call["format"]["text"] == "%s" and call["format"]["hex"] == "2573"
        assert call["format"]["nul_terminated"] and source["nul_terminated"]
        assert bytes.fromhex(source["hex"]).decode("ascii") == text
        assert call["step"] < call["first_glyph"] < call["return_step"]
        matches.append({"call_index": index, "step": call["step"],
                        "first_glyph": call["first_glyph"], "return_step": call["return_step"],
                        "lead_instructions": call["first_glyph"] - call["step"],
                        "caller": call["caller"], "format_pointer": [call["format"]["segment"], call["format"]["offset"]],
                        "buffer_pointer": [source["segment"], source["offset"]],
                        "source_hex": source["hex"]})
    if role != "none":
        assert matches, "沒有在指定玩家路徑觀測到 Shield"
    result = {"draft": True, "checkpoints_equal": len(images), "images_equal": images,
              "role": role, "shield_occurrences": matches,
              "observed_receipt_sha256": sha((observed / "receipt.json").read_bytes()),
              "control_receipt_sha256": sha((control / "receipt.json").read_bytes()),
              "checker_sha256": sha(Path(__file__).read_bytes()),
              "limits": "僅證明指定原版按鍵流程的觀測隔離與字串時間；未翻譯，未證實任意 vararg、全域角色判定、冷啟動 GUI 或中文覆繪。"}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return {"checkpoints_equal": len(images), "role": role,
            "shield_occurrences": len(matches),
            "lead_instructions": sorted({m["lead_instructions"] for m in matches})}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("observed", type=Path)
    parser.add_argument("control", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--role", choices=("inventory", "grimoire", "none"), default="none")
    args = parser.parse_args()
    print(json.dumps(check(args.observed, args.control, args.output, args.role), ensure_ascii=False))
