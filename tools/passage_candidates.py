"""整理相鄰 ECL 字串的段落候選；未證實執行語意，不接入正式顯示。"""

import argparse
import hashlib
import json
from pathlib import Path

from text_catalog import decode6, hlib, write_tsv


def sha(data):
    return hashlib.sha256(data).hexdigest()


def extract(library_path, catalog_path, output):
    data = library_path.read_bytes()
    catalog = json.loads(catalog_path.read_text())
    expected = next(x["sha256"] for x in catalog["inputs"] if x["path"] == "DISK3/ECL.GLB")
    if sha(data) != expected:
        raise ValueError("ECL 與來源清單雜湊不同")
    blocks = hlib(data)
    literals = {}
    for entry in catalog["entries"]:
        if entry["domain"] != "ecl":
            continue
        for source in entry["sources"]:
            pos, length = source["file_offset"], source["packed_length"]
            begin, end = blocks[source["chunk"]]
            if not begin <= pos < pos + 2 + length <= end:
                raise ValueError("字串候選超出 HLIB 區塊")
            if data[pos:pos+2] != bytes([0x80, length]):
                raise ValueError("字串標記與來源清單不同")
            if decode6(data[pos+2:pos+2+length]) != entry["text"]:
                raise ValueError("解碼與來源清單不同")
            literals[pos] = (entry, source)
    groups, used = {}, set()
    for pos, (entry, source) in sorted(literals.items()):
        if pos in used or data[pos-1] not in (0x11, 0x12):
            continue
        parts = [(entry, source)]
        joins = []
        end = pos + 2 + source["packed_length"]
        while True:
            following = None
            if data[end:end+2] == b"\x11\x80":
                following = end + 1
            elif data[end:end+3] == b"\x18\x11\x80":
                following = end + 2
            if following not in literals:
                break
            next_entry, next_source = literals[following]
            if next_source["chunk"] != source["chunk"]:
                break
            joins.append({"file_offset": end, "bytes": data[end:following].hex(" ")})
            parts.append((next_entry, next_source))
            end = following + 2 + next_source["packed_length"]
        if len(parts) < 2:
            continue
        text = "".join(x["text"] for x, _ in parts)
        key = "passage." + sha(text.encode("ascii"))[:20]
        group = groups.setdefault(key, {"key": key, "text": text, "sources": [],
            "evidence_level": "強推論", "runtime_verified": False,
            "status": "相鄰文字的整句校讀候選；完整腳本控制與頁面狀態未驗，不進正式顯示"})
        if group["text"] != text:
            raise ValueError("段落候選 key 雜湊衝突")
        group["sources"].append({"file": "DISK3/ECL.GLB", "chunk": source["chunk"],
            "file_offset": pos, "end_file_offset": end,
            "leading_bytes": data[max(0, pos-4):pos].hex(" "),
            "following_bytes": data[end:end+8].hex(" "), "joins": joins,
            "fragments": [{"key": x["key"], "text": x["text"], **s} for x, s in parts]})
        used.update(s["file_offset"] for _, s in parts)
    entries = list(groups.values())
    report = {"candidate_only": True, "runtime_verified": False,
        "address_space": "ECL.GLB 檔案偏移，非 IDA 或執行期位址",
        "source_sha256": sha(data), "catalog_sha256": sha(catalog_path.read_bytes()),
        "tool_sha256": sha(Path(__file__).read_bytes()), "groups": entries}
    output.mkdir(parents=True, exist_ok=True)
    (output/"passage-candidates.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    write_tsv(output/"passage-candidates.en.tsv", ["key", "text"],
        ((x["key"], x["text"]) for x in entries))
    return {"passage_candidates": len(entries), "source_occurrences": sum(len(x["sources"]) for x in entries),
        "fragment_occurrences": sum(len(s["fragments"]) for x in entries for s in x["sources"]),
        "runtime_verified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(extract(args.library, args.catalog, args.output), ensure_ascii=False))
