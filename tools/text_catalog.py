"""擷取本作 HLIB 劇本與 EXE 文字候選；不改動原版，不把候選當已確認輸出。"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import struct


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hlib(data):
    if len(data) < 20 or data[:4] != b"HLIB":
        raise ValueError("不是 HLIB")
    end, count = struct.unpack_from("<IH", data, 4)
    if end != len(data) or not 1 <= count <= 4096:
        raise ValueError("HLIB 長度或區塊數不符")
    header_end = 16 + 4 * (count+1)
    if header_end > len(data):
        raise ValueError("HLIB 索引越界")
    offsets = struct.unpack_from("<" + "I"*(count+1), data, 16)
    if offsets[0] != header_end or offsets[-1] != len(data):
        raise ValueError("HLIB 邊界不符")
    if any(a > b for a, b in zip(offsets, offsets[1:])):
        raise ValueError("HLIB 索引逆序")
    return [(a, b) for a, b in zip(offsets, offsets[1:])]


def decode6(payload):
    bits, count, output = 0, 0, []
    for byte in payload:
        bits = (bits << 8) | byte
        count += 8
        while count >= 6:
            count -= 6
            value = (bits >> count) & 63
            if value:
                output.append(chr(value+64 if value < 32 else value))
        bits &= (1 << count)-1
    return "".join(output)


def plausible(text):
    # 啟發式。保留原始字串，明列候選狀態，未知或雜訊不能進正式顯示。
    return (len(text.strip()) >= 2 and re.search(r"[A-Za-z]{2}", text)
            and re.fullmatch(r"[A-Za-z0-9 .,'!?\-:;\"()/&%$#*+<>=\[\]{}|\\]+", text))


def ecl_plausible(text):
    if not plausible(text) or not re.fullmatch(r"[A-Z0-9 .,'!?\-:;\"()/&%$#*+<>=]+", text):
        return False
    tokens = [t for t in re.split(r" |\.\.\.+|--+", text.strip()) if t]
    def word(token):
        value = re.sub(r"^[\"'(<\-.,!?;:)>=*]+|[\"'(<\-.,!?;:)>=*]+$", "", token)
        return not value or bool(re.fullmatch(
            r"(?:[A-Z]+(?:[.'\-/][A-Z]+)*(?:\(S\))?|[0-9]+(?:[.,:][0-9]+)*(?:ST|ND|RD|TH|S|%|CR)?)", value))
    return bool(tokens and word(tokens[0]) and word(tokens[-1])
                and sum(word(t) for t in tokens)/len(tokens) >= .9)


def write_tsv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", quoting=csv.QUOTE_NONE, quotechar=None, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def extract(original, output, traces):
    output.mkdir(parents=True, exist_ok=True)
    records, inputs = {}, []

    def add(domain, text, location, anchor=None):
        raw = text.encode("ascii")
        key = domain + "." + digest(raw)[:20]
        entry = records.setdefault(key, {"key": key, "domain": domain, "text": text,
            "sha256": digest(raw), "sources": [], "observations": [], "status": "candidate"})
        if entry["text"] != text:
            raise ValueError("文字 key 雜湊衝突")
        if location not in entry["sources"]:
            entry["sources"].append(location)
        if anchor:
            entry["observations"].append(anchor)
            entry["status"] = "observed"

    library_path = original/"DISK3/ECL.GLB"
    library = library_path.read_bytes()
    blocks = hlib(library)
    inputs.append({"path":"DISK3/ECL.GLB", "sha256":digest(library), "blocks":len(blocks)})
    directory = library[slice(*blocks[0])]
    directory_count = struct.unpack_from("<H", directory)[0]
    if len(directory) != 2 + directory_count*4 or directory_count != len(blocks)-1:
        raise ValueError("ECL 對照區塊形狀與目前來源不同")
    for chunk, (begin, end) in enumerate(blocks[1:], start=1):
        for pos in range(begin, end-2):
            if library[pos] != 0x80:
                continue
            length = library[pos+1]
            if not length or pos+2+length > end:
                continue
            text = decode6(library[pos+2:pos+2+length])
            if ecl_plausible(text):
                add("ecl", text, {"file":"DISK3/ECL.GLB", "chunk":chunk,
                    "file_offset":pos, "chunk_offset":pos-begin, "packed_length":length})
    exe = (original/"DQK.EXE").read_bytes()
    inputs.append({"path":"DQK.EXE", "sha256":digest(exe)})
    for match in re.finditer(rb"[\x20-\x7e]{2,1024}\x00", exe):
        text = match[0][:-1].decode("ascii")
        if plausible(text):
            add("ui", text, {"file":"DQK.EXE", "file_offset":match.start(), "encoding":"ASCII NUL"})
    monster_path=original/"DISK2/MONCHA.GLB"
    monsters=monster_path.read_bytes()
    monster_blocks=hlib(monsters)
    inputs.append({"path":"DISK2/MONCHA.GLB","sha256":digest(monsters),"blocks":len(monster_blocks)})
    for chunk,(begin,end) in enumerate(monster_blocks[1:],start=1):
        for match in re.finditer(rb"[\x20-\x7e]{3,32}",monsters[begin:end]):
            text=match[0].decode("ascii")
            if re.fullmatch(r"[A-Z][A-Z0-9 '\-]*[A-Z]",text):
                add("name",text,{"file":"DISK2/MONCHA.GLB","chunk":chunk,
                    "file_offset":begin+match.start(),"encoding":"raw ASCII candidate; record layout unverified"})
    missing, excluded_formats = [], 0
    for path in traces:
        data = json.loads(path.read_text())
        trace_digest = digest(path.read_bytes())
        values = []
        for event in data.get("events", []):
            if "source" in event:
                values.append(("ui", event["source"], event["step"]))
        for event in data.get("paragraphs", []):
            source = event.get("source", {})
            if source.get("nul_terminated"):
                values.append(("ecl", source["text"], event["step"]))
        for domain, text, step in values:
            if domain == "ui" and re.fullmatch(r"%[rsc]",text):
                excluded_formats += 1
                continue
            key = domain+"."+digest(text.encode("ascii"))[:20]
            if key not in records and domain == "ui":
                # 正常選單會從整串拆出單一標籤；檔案匹配只證明有相同 bytes，來源由觀測保留。
                position = exe.find(text.encode("ascii"))
                if position >= 0:
                    add(domain,text,{"file":"DQK.EXE","file_offset":position,
                        "encoding":"runtime component; matching file bytes"})
            if key not in records:
                missing.append({"domain":domain, "text":text, "trace":str(path), "step":step})
                continue
            records[key]["status"] = "observed"
            anchor = {"trace_sha256":trace_digest, "step":step}
            if anchor not in records[key]["observations"]:
                records[key]["observations"].append(anchor)
    ordered = sorted(records.values(), key=lambda e:(e["domain"],e["sources"][0]["file_offset"]))
    write_tsv(output/"en.tsv", ["key","text"], ((e["key"],e["text"]) for e in ordered))
    write_tsv(output/"events.tsv", ["key","domain","sha256","length","status","sources"],
        ((e["key"],e["domain"],e["sha256"],len(e["text"]),e["status"],
          ";".join(f'{p["file"]}@0x{p["file_offset"]:X}' for p in e["sources"])) for e in ordered))
    (output/"catalog.json").write_text(json.dumps({"candidate_catalog":True,
        "inputs":inputs, "entries":ordered, "missing_observations":missing},ensure_ascii=False,indent=2)+"\n")
    summary = {"candidate_catalog":True,"entries":len(ordered),
        "domains":{d:sum(e["domain"]==d for e in ordered) for d in ("ecl","ui","name")},
        "characters":sum(len(e["text"]) for e in ordered),
        "observed":sum(e["status"]=="observed" for e in ordered),
        "excluded_format_events":excluded_formats,
        "missing_observations":len(missing), "inputs":inputs,
        "tool_sha256":digest(Path(__file__).read_bytes()),
        "outputs":{name:digest((output/name).read_bytes()) for name in ("en.tsv","events.tsv","catalog.json")}}
    (output/"receipt.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--trace", type=Path, action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(extract(args.original,args.output,args.trace),ensure_ascii=False))
