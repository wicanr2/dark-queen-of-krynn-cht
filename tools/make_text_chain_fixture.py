"""在獨立資料副本製作文字拼接實驗，原版來源保持唯讀。"""

import argparse
import json
from pathlib import Path
import shutil

from text_catalog import decode6, digest, hlib


def encode6(text):
    bits = "".join(f"{ord(c)-64 if 64 <= ord(c) < 96 else ord(c):06b}" for c in text)
    bits += "0" * (-len(bits) % 8)
    return bytes(int(bits[i:i+8], 2) for i in range(0, len(bits), 8))


def make(original, output):
    library = original/"DISK3/ECL.GLB"
    data = library.read_bytes()
    if digest(data) != "40542071e42d3cd125eabcead11456a99942bf55a7736fdb79f66a3c27c3664d":
        raise ValueError("ECL 來源不同")
    if digest((original/"DQK.EXE").read_bytes()) != "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58":
        raise ValueError("EXE 來源不同")
    pos = 12826
    length = data[pos+1]
    if data[pos-1:pos+2] != b"\x12\x80\x8b":
        raise ValueError("首段定位 bytes 不符")
    before = data[pos:pos+2+length]
    output.mkdir(parents=True, exist_ok=True)
    for name, join in [("direct-11", b"\x11"), ("prefix-18-11", b"\x18\x11")]:
        root = output/name
        game = root/"game"
        if root.exists():
            raise ValueError("實驗輸出已存在，不覆寫")
        shutil.copytree(original, game)
        (root/"trace").mkdir()
        packed_total = length - 2 - len(join)
        lengths = [packed_total//2, packed_total-packed_total//2]
        texts, packets = [], []
        for label, size in zip(["FIRST SEGMENT. ", "SECOND SEGMENT."], lengths):
            text = label.ljust(size*8//6)
            packed = encode6(text)
            assert len(packed) == size and decode6(packed) == text
            texts.append(text)
            packets.append(bytes([0x80, size])+packed)
        replacement = packets[0]+join+packets[1]
        assert len(replacement) == len(before)
        modified = data[:pos]+replacement+data[pos+len(before):]
        assert hlib(modified) == hlib(data)
        target = game/"DISK3/ECL.GLB"
        target.write_bytes(modified)
        files = []
        for source in sorted(original.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(original)
            old, new = digest(source.read_bytes()), digest((game/relative).read_bytes())
            assert (old != new) == (str(relative) == "DISK3/ECL.GLB")
            files.append({"path": str(relative), "original_sha256": old, "fixture_sha256": new})
        manifest = {"controlled_fixture": True, "normal_player_receipt": False,
            "tool_sha256": digest(Path(__file__).read_bytes()), "address_space": "ECL.GLB 檔案偏移",
            "file_offset": pos, "before_hex": before.hex(" "), "replacement_hex": replacement.hex(" "),
            "join_bytes": join.hex(" "), "expected_segments": texts,
            "expected_concatenation": "".join(texts), "files": files}
        (root/"fixture.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    return {"fixtures": ["direct-11", "prefix-18-11"], "controlled_fixture": True,
        "changed_file": "DISK3/ECL.GLB", "exe_changed": False}


def verify(original, output, snapshot, probe):
    results = []
    for name in ["direct-11", "prefix-18-11"]:
        root = output/name
        fixture = json.loads((root/"fixture.json").read_text())
        trace_path = root/"trace/trace.json"
        trace = json.loads(trace_path.read_text())
        for item in fixture["files"]:
            assert digest((original/item["path"]).read_bytes()) == item["original_sha256"]
            assert digest((root/"game"/item["path"]).read_bytes()) == item["fixture_sha256"]
        paragraphs = trace["paragraphs"]
        assert [p["source"]["text"] for p in paragraphs] == fixture["expected_segments"]
        assert [p["clear"] for p in paragraphs] == [1, 0]
        assert paragraphs[0]["step"] < paragraphs[0]["first_glyph"] < paragraphs[1]["step"]
        assert paragraphs[1]["step"] < paragraphs[1]["first_glyph"] < trace["steps"]
        results.append({"name": name, "trace_sha256": digest(trace_path.read_bytes()),
            "fixture_sha256": digest((root/"fixture.json").read_bytes()),
            "paragraph_steps": [p["step"] for p in paragraphs], "clear": [p["clear"] for p in paragraphs],
            "first_glyph_steps": [p["first_glyph"] for p in paragraphs]})
    receipt = {"controlled_fixture": True, "normal_player_receipt": False,
        "snapshot_sha256": digest(snapshot.read_bytes()), "probe_sha256": digest(probe.read_bytes()),
        "tool_sha256": digest(Path(__file__).read_bytes()),
        "source_commit": trace["source_commit"], "results": results,
        "limitation": "只證實兩種接續位元組在此受控首段產生兩次 clear=1、0 繪製；不外推其他 opcode、分頁或全部候選"}
    (output/"receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--probe", type=Path)
    args = parser.parse_args()
    if args.verify and (args.snapshot is None or args.probe is None):
        parser.error("核對收據需要 --snapshot 與 --probe")
    result = verify(args.original, args.output, args.snapshot, args.probe) if args.verify else make(args.original, args.output)
    print(json.dumps(result, ensure_ascii=False))
