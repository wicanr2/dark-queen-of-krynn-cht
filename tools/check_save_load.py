"""核對固定原版存檔 J、無觀測組與正常冷啟動讀回；不驗收中文或 GUI。"""

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root, observe, control, cold = Path(sys.argv[1]), *sys.argv[2:5]
    for name in [observe, control, cold]:
        assert Path(name).name == name and name not in (".", "..")
    a = json.loads((root / observe / "trace.json").read_text())
    b = json.loads((root / control / "trace.json").read_text())
    assert a["observe"] and not b["observe"] and a["save_sequence"] and b["save_sequence"]
    assert a["input_sha256"] == b["input_sha256"] == "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
    assert a["source_commit"] == b["source_commit"] == "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8"
    assert a["steps"] == b["steps"] == 716031795 and a["exit_code"] == b["exit_code"] == 0
    assert len(a["checkpoints"]) == len(b["checkpoints"]) == 16
    for x, y in zip(a["checkpoints"], b["checkpoints"]):
        for field in ["label", "step", "regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes", "unimplemented"]:
            assert x[field] == y[field], (x["label"], field)
        if x["label"] == "exit-dos":
            assert x["unimplemented"] == ["int 10h AH=01 AL=00 ×1"]
        else:
            assert not x["unimplemented"]
    assert a["unimplemented"] == b["unimplemented"] == ["int 10h AH=01 AL=00 ×1"]
    files = []
    expected = {
        "SavGamJ.qsv": (7965, "72a45079a189126c3a96d4681fac846086a6edaf26748d260d3a73fbc8905488"),
        "VaultJ.DAT": (866, "2acc13fa21f319fac65ad823d7ca52f1ed02d13ce8708431f7ce5c116d9db7ba"),
    }
    for name, (size, digest) in expected.items():
        for run in [observe, control, cold]:
            file = root / run / "scratch/SAVE" / name
            assert file.stat().st_size == size and sha(file) == digest, (run, name)
        files.append({"name": name, "bytes": size, "sha256": digest})
    for label in ["load-j", "begin-loaded-j", "resume-j"]:
        log = (root / cold / (label + ".log")).read_text()
        assert "沒實作的服務（0 種）" in log
        if label == "load-j":
            assert "SavGamJ.qsv" in log and "取走 11 個" in log
        elif label == "begin-loaded-j":
            assert "取走 1 個" in log
        else:
            assert "取走 7 個" in log
    assert sha(root / cold / "begin-loaded-j.bin") == "d7eec5b094e4265a627d2b61333d3bc7d339572431e281ac29b533e10c76ae67"
    with Image.open(root / observe / "return-08.png") as old, Image.open(root / cold / "resume-j.png") as new:
        assert old.size == new.size == (320, 200)
        assert old.convert("RGB").tobytes() == new.convert("RGB").tobytes()
    report = {
        "draft": True,
        "scope": "Original dosgolem save J and cold load only; no localized renderer, GUI, all slots, in-session Load or binary format parity claim.",
        "observe": observe, "control": control, "cold": cold,
        "matching_guest_checkpoints": 16, "gameplay_unimplemented": [],
        "post_exit_unimplemented": a["unimplemented"], "exit_code": 0,
        "save_files": files, "cold_city_rgb_equal": True,
        "initial_state_sha256": sha(root / "startup/adventure-start.state"),
        "observe_trace_sha256": sha(root / observe / "trace.json"),
        "control_trace_sha256": sha(root / control / "trace.json"),
        "cold_logs_sha256": {name: sha(root / cold / (name + ".log")) for name in ["load-j", "begin-loaded-j", "resume-j"]},
        "tool_sha256": sha(Path(__file__)),
    }
    target = root / observe / "save-load-comparison.json"
    if target.exists():
        assert json.loads(target.read_text()) == report, "重驗結果與原有收據不同"
    else:
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
