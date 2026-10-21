"""以真實輸入及觀測衍生邊界案例，驗證執行期標籤不污染原始來源定位。"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from text_catalog import extract


def main():
    original, trace_path = map(Path, sys.argv[1:3])
    if not (original / "DQK.EXE").is_file() or not trace_path.is_file():
        print("略過：缺少原版或正常觀測，不以自製資料代替原版。")
        return
    trace = json.loads(trace_path.read_text())
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        baseline_dir = root / "baseline"
        extract(original, baseline_dir, [])
        baseline = {r["key"]: r for r in json.loads((baseline_dir / "catalog.json").read_text())["entries"]}
        candidates = [c for c in trace["calls"] if c["format"].get("nul_terminated")
                      and c["format"].get("text") and "%" not in c["format"]["text"]
                      and 0 <= c["stack"][2] < 200 and 0 <= c["stack"][3] < 320
                      and "ui." + hashlib.sha256(c["format"]["text"].encode()).hexdigest()[:20] not in baseline]
        assert candidates, "真實觀測中沒有新增標籤，不能驗證此路徑"
        event = candidates[0]
        key = "ui." + hashlib.sha256(event["format"]["text"].encode()).hexdigest()[:20]
        cases = [("literal", copy.deepcopy(event), "accept")]
        for name, change, outcome in [
            ("encoded-coordinate", lambda c: c["stack"].__setitem__(2, 8008), "skip"),
            ("format", lambda c: c["format"].__setitem__("text", "%s"), "skip"),
            ("unterminated", lambda c: c["format"].__setitem__("nul_terminated", False), "skip"),
            ("wrong-entry", lambda c: c["regs"].__setitem__("IP", 0), "skip"),
            ("pointer-mismatch", lambda c: c["format"].__setitem__("offset", c["stack"][5] + 1), "reject"),
            ("video-memory", lambda c: (c["stack"].__setitem__(6, 0xa000), c["format"].__setitem__("segment", 0xa000)), "skip"),
        ]:
            altered = copy.deepcopy(event)
            change(altered)
            cases.append((name, altered, outcome))
        for name, call, outcome in cases:
            input_path = root / (name + ".json")
            input_path.write_text(json.dumps({"input_sha256": trace["input_sha256"], "calls": [call]}))
            output = root / name
            try:
                extract(original, output, [input_path])
            except ValueError:
                assert outcome == "reject" and not (output / "en.tsv").exists()
                continue
            assert outcome != "reject"
            records = {r["key"]: r for r in json.loads((output / "catalog.json").read_text())["entries"]}
            assert set(records) - set(baseline) == ({key} if outcome == "accept" else set())
            for old_key in baseline:
                assert records[old_key] == baseline[old_key]
            if outcome == "accept":
                location = records[key]["sources"][0]
                assert "file_offset" not in location and location["file"] == "runtime RAM"
                assert location["segment"] == event["stack"][6] and location["offset"] == event["stack"][5]
        bad_trace = root / "wrong-exe.json"
        bad_trace.write_text(json.dumps({"input_sha256": "0" * 64, "calls": [event]}))
        try:
            extract(original, root / "wrong-exe", [bad_trace])
        except ValueError:
            assert not (root / "wrong-exe/en.tsv").exists()
        else:
            raise AssertionError("未拒絕 EXE 雜湊失配")
        print("執行期標籤 8 項檢查通過：真實 literal、座標、格式、結尾、入口、指標、顯存及 EXE 身分。")


if __name__ == "__main__":
    main()
