#!/usr/bin/env python3
"""DRAFT 收據檢查：只讀原始收據，報告寫入既有原型目錄。Docker 內執行。"""
import hashlib
import json
import os
import sys
from pathlib import Path

from PIL import Image


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    root = Path(sys.argv[1])
    names = sys.argv[2:]
    assert len(names) == 5, "需觀測、控制、原文、繁中、細分五份目錄"
    receipts = [json.loads((root / n / "receipt.json").read_text()) for n in names]
    observed, control, english, chinese, fine = receipts
    fields = ("step", "regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes")
    expected = [{k: c[k] for k in fields} for c in control["checkpoints"]]
    assert len(expected) == 3
    for r in receipts:
        assert [{k: c[k] for k in fields} for c in r["checkpoints"]] == expected
        assert not r["unimplemented"]
    assert english["events"] == chinese["events"] == fine["events"]
    assert english["boundaries"] == chinese["boundaries"] == fine["boundaries"]
    summaries = []
    at_checkpoint = []
    for name, r in zip(names[2:], receipts[2:]):
        previous = None
        by_step = {}
        held_count = 0
        for frame in r["frames"]:
            file = Path(frame["File"])
            assert file.name == str(file), "收據檔名不得跨出目錄"
            with Image.open(root / name / file) as im:
                assert im.size == (640, 400)
                pixels = im.convert("RGBA").tobytes()
            assert sha(pixels) == frame["SHA256"]
            if frame["held"]:
                assert previous == frame["SHA256"], "過渡期間露出未完成畫格"
                held_count += 1
            previous = frame["SHA256"]
            by_step[frame["step"]] = frame
        for step, count in [(246000000, 12), (275000000, 0), (290000000, 12)]:
            assert by_step[step]["active"] == count
            assert not by_step[step]["held"]
        for start, end in [(241026258, 241805302), (260062329, 260241058), (275027020, 275815194)]:
            middle = [f for f in r["frames"] if start <= f["step"] < end]
            assert middle and all(f["held"] for f in middle)
        boundaries = r["boundaries"]
        entries = sum(b["kind"] == "button-paint-entry" for b in boundaries)
        returns = sum(b["kind"] == "button-paint-return" for b in boundaries)
        assert entries == returns == 30
        assert boundaries[-1]["paint_depth"] == boundaries[-1]["render_depth"] == 0
        events = dict(line.split() for line in (root / name / "memory-events.txt").read_text().splitlines())
        assert int(events["oom"]) == int(events["oom_kill"]) == 0
        assert 0 < r["texture_uploads"] < len(r["frames"])
        summaries.append({"directory": name, "frames": len(r["frames"]), "held_frames": held_count,
                          "paint_pairs": entries, "texture_uploads": r["texture_uploads"],
                          "receipt_sha256": sha((root / name / "receipt.json").read_bytes())})
        at_checkpoint.append(by_step)
    for step in [246000000, 290000000]:
        assert at_checkpoint[0][step]["SHA256"] != at_checkpoint[1][step]["SHA256"]
        assert at_checkpoint[1][step]["SHA256"] == at_checkpoint[2][step]["SHA256"]
    assert len({r[275000000]["SHA256"] for r in at_checkpoint}) == 1, "讀取來源頁有中文殘影"
    for start in [241000000, 260000000, 275000000]:
        steps = sorted({f["step"] for f in fine["frames"] if start <= f["step"] <= start + 1000000})
        assert steps[0] <= start + 2000 and steps[-1] == start + 1000000
        assert max(b - a for a, b in zip(steps, steps[1:])) <= 2000, "細分時漏掉提交間隔"
    report = {"draft": True, "scope": "normal p/l/e; twelve character-menu labels only",
              "guest_checkpoints_equal": True, "frames_verified": summaries,
              "no_stale_labels_at_load_source": True, "fine_max_interval": 2000,
              "limits": "No story, scrolling, save/load roundtrip, or complete-game claim."}
    output = root / names[-1] / "comparison.json"
    assert output.parent.stat().st_uid == os.getuid()
    assert not output.exists(), "不覆寫既有驗證收據"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
