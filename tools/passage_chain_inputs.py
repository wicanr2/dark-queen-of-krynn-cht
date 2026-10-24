"""相鄰敘事的 DRAFT 來源核對與校讀子集；不修改遊戲或正式目錄。"""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

from text_catalog import decode6, hlib, write_tsv
from translation_check import load


GLB_SHA = "40542071e42d3cd125eabcead11456a99942bf55a7736fdb79f66a3c27c3664d"
EXE_SHA = "3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def packets(block, start, leading=0x12):
    """只讀直接 11h 接續。未知指令立即停止，不能跳過控制指令。"""
    if not 0 <= start < len(block):
        raise ValueError("起點越界")
    result, pos = [], start
    while True:
        opcode = leading if not result else 0x11
        if pos + 3 > len(block) or block[pos:pos+2] != bytes([opcode, 0x80]):
            if not result:
                raise ValueError("不是原位元串敘事")
            break
        length = block[pos+2]
        end = pos + 3 + length
        if not length or end > len(block):
            raise ValueError("原位元串越界")
        text = decode6(block[pos+3:end])
        if not text or not all(32 <= ord(c) <= 126 for c in text):
            raise ValueError("原文不符合 ASCII 契約")
        result.append(dict(offset=pos, end=end, packed_length=length,
                           key="ecl." + digest(text.encode())[:20]))
        pos = end
        if len(result) > 32:
            raise ValueError("超過片段上限")
    return result


def native(root, output):
    library = (root/"workplace/input/dos/drkqueen/DISK3/ECL.GLB").read_bytes()
    assert digest(library) == GLB_SHA
    blocks = hlib(library)
    records, checks = [], []
    requests = {
        "bar-r1": (root/"workplace/probe/pane-render-20261022/observe-palace-journal-r1/final.state", root/"workplace/probe/literal-catalog-20261024/bar-return-request-r2.json"),
        "battle-wait-r1": (root/"workplace/probe/battle-text-20261024/control-quick-r3/final.state", output/"battle-wait-r1.json"),
        "battle-wait-r2": (output/"control-battle-wait-r1/final.state", output/"battle-wait-r2.json"),
        "after-battle-r2": (output/"control-battle-wait-r2/final.state", output/"after-battle-r2.json"),
    }
    for phase in ("bar-r1", "battle-wait-r1", "battle-wait-r2", "after-battle-r2"):
        a, b = [read(output/(mode+"-"+phase)/"receipt.json") for mode in ("observe", "control")]
        for key in ("exe_sha256", "state_sha256", "request_sha256", "probe_sha256", "source_commit", "go_version", "request", "checkpoints"):
            assert a[key] == b[key], (phase, key)
        assert a["exe_sha256"] == EXE_SHA and a["pending_paragraphs"] == 0
        assert a["source_commit"] == "f79eab6db8c64a524a06535e53e5d32b0bbcf7c8" and a["go_version"] == "go1.24.13"
        assert a["probe_sha256"] == sha(output/"programs-r1/passage-chain-probe")
        state, request = requests[phase]
        assert a["state_sha256"] == sha(state) and a["request_sha256"] == sha(request)
        assert not b["paragraphs"] and b["pending_paragraphs"] == 0
        for cp in a["checkpoints"]:
            assert not cp["file_writes"] and not cp["unimplemented"]
            assert sha(output/("observe-"+phase)/(cp["label"]+".png")) == sha(output/("control-"+phase)/(cp["label"]+".png"))
        assert sha(output/("observe-"+phase)/"final.state") == sha(output/("control-"+phase)/"final.state")
        checks.append(dict(phase=phase, checkpoints=len(a["checkpoints"]), paragraphs=len(a["paragraphs"] or []),
                           final_sha256=sha(output/("control-"+phase)/"final.state")))
        for p in a["paragraphs"] or []:
            assert p["raw_b216"] == 0x80 and p["raw_b1c7"] in (0x11, 0x12)
            assert p["source_pointer"] == dict(Seg=0x333e, Off=0xb487)
            assert p["handler"]["step"] < p["step"] < p["first_glyph"] < p["return_step"]
            assert p["handler"]["raw_ae5c"] == p["raw_ae5c"]
            script = (output/("observe-"+phase)/a["script_files"][p["script_sha256"]]["file"]).read_bytes()
            assert digest(script) == p["script_sha256"] and len(script) == 0x8000
            matched = [(i, begin, end) for i, (begin, end) in enumerate(blocks)
                       if end-begin <= len(script) and script[:end-begin] == library[begin:end]]
            assert len(matched) == 1
            chunk, begin, end = matched[0]
            before, after = p["handler"]["raw_b7f9"], p["raw_b7f9"]
            offset = (p["raw_ae5c"]["Off"] + before) & 0xffff
            parsed = packets(script[:end-begin], offset, p["raw_b1c7"])
            first = parsed[0]
            assert (after-before) & 0xffff == first["end"]-offset
            assert decode6(script[offset+3:first["end"]]) == p["source"]
            assert first["key"] == "ecl."+digest(p["source"].encode())[:20]
            records.append(dict(phase=phase, step=p["step"], first_glyph=p["first_glyph"], chunk=chunk,
                chunk_sha256=digest(library[begin:end]), chunk_bytes=end-begin,
                runtime_script_segment=p["raw_ae5c"]["Seg"], raw_base_offset=p["raw_ae5c"]["Off"],
                raw_cursor_before=before, raw_cursor_after=after, chunk_offset=offset,
                file_offset=begin+offset, end_chunk_offset=first["end"], key=first["key"],
                direct_packets_available=len(parsed), following_bytes=script[first["end"]:first["end"]+8].hex(" ")))
    assert len(records) == 4 and all(r["chunk"] == 4 for r in records)
    assert all(r["direct_packets_available"] == 1 for r in records)
    write(output/"native-check.json", dict(checks=checks, records=records,
        address_spaces=dict(runtime="dosgolem segment:offset，偏移加法取低 16 bit", archive="HLIB 區塊及 ECL.GLB 檔案偏移，分欄保存"),
        formula="chunk_offset = (raw_base_offset + raw_cursor_before) & 0xffff; cursor_delta = 3 + packed_length",
        limits="四個正常酒館來源證實游標與區塊對應，沒有直接相鄰片段的正常路徑；首戰敗北返回角色管理，不作勝利或後續章節證據。"))
    print("native", len(records), "sources", sum(c["checkpoints"] for c in checks), "paired checkpoints")


def generate(root, target):
    texts = root/"workplace/translation"
    raw = (root/"workplace/input/dos/drkqueen/DISK3/ECL.GLB").read_bytes()
    groups = read(texts/"passage-candidates.json")
    assert digest(raw) == GLB_SHA == groups["source_sha256"]
    blocks = hlib(raw)
    reviews = {r["key"]: r for r in load(texts/"passage-review/zh-TW.review.tsv", ["key", "text", "note"])}
    selected, excluded, occurrences = [], [], []
    for group in groups["groups"]:
        key, source = group["key"], group["text"]
        assert key == "passage."+digest(source.encode())[:20]
        valid = []
        for origin in group["sources"]:
            begin, end = blocks[origin["chunk"]]
            first = origin["file_offset"]-begin-1
            if raw[begin+first] != 0x12 or any(j["bytes"] != "11" for j in origin["joins"]):
                continue
            chain = packets(raw[begin:end], first)
            assert len(chain) == len(origin["fragments"])
            assert chain[-1]["end"] == origin["end_file_offset"]-begin
            for item, fragment in zip(chain, origin["fragments"]):
                assert item["key"] == fragment["key"] and item["offset"]+1 == fragment["chunk_offset"]
                assert item["packed_length"] == fragment["packed_length"]
            assert "".join(decode6(raw[begin+x["offset"]+3:begin+x["end"]]) for x in chain) == source
            valid.append(dict(key=key, chunk=origin["chunk"], chunk_bytes=end-begin,
                chunk_sha256=digest(raw[begin:end]), file_offset=begin+first, chunk_offset=first,
                end_chunk_offset=chain[-1]["end"], packet_sha256=digest(raw[begin+first:begin+chain[-1]["end"]]), fragments=chain))
        reason = ("unreviewed" if key not in reviews else "control-or-continuation" if not valid
                  else "length" if len(source)>96 or len(reviews[key]["text"])>144 else "")
        if reason:
            excluded.append(dict(key=key, reason=reason))
            continue
        target_text = reviews[key]["text"]
        assert not any(c in source+target_text for c in ("%", "\\", "\n", "\t"))
        selected.append((key, source, target_text, reviews[key]["note"]))
        occurrences.extend(valid)
    write_tsv(target/"en.tsv", ["key", "text"], ((k, en) for k, en, _, _ in selected))
    write_tsv(target/"zh-TW.review.tsv", ["key", "text", "note"], ((k, zh, note) for k, _, zh, note in selected))
    keys = {r[0] for r in selected}
    term_rows = load(texts/"passage-review/term-reviews.tsv", ["key", "term", "source_sha256", "translation_sha256", "reason"], 2)
    write_tsv(target/"term-reviews.tsv", ["key", "term", "source_sha256", "translation_sha256", "reason"],
        (list(r.values()) for r in term_rows if r["key"] in keys))
    write(target/"registry.json", dict(draft=True, runtime_integrated=False, normal_chain_verified=False,
        source_sha256=GLB_SHA, occurrences=occurrences, excluded=excluded,
        limits="只作校讀與前瞻原型輸入；12h 開頭、直接 11h 接續，英文至多 96 字元及繁中至多 144 字元。未知控制指令停止，不推定其後資料會執行；未接正式或現行 DRAFT GUI。"))
    return dict(groups=len(selected), occurrences=len(occurrences),
                fragment_keys=len({f["key"] for r in occurrences for f in r["fragments"]}),
                excluded=len(excluded), runtime_integrated=False)


def prepare(root, output):
    assert read(output/"native-check.json")["records"]
    target = output/"chain-inputs-r1"
    target.mkdir()
    write(output/"selection.json", generate(root, target))
    print(read(output/"selection.json"))


def guards(root, output):
    raw = (root/"workplace/input/dos/drkqueen/DISK3/ECL.GLB").read_bytes()
    begin, end = hlib(raw)[5]
    block, start = raw[begin:end], 3357
    good = packets(block, start)
    assert len(good) == 2
    cases = []
    for name, changed, offset, expected in [
        ("unknown-18", block[:good[0]["end"]]+b"\x18"+block[good[0]["end"]:], start, 1),
        ("unknown-33", block[:good[0]["end"]]+b"\x33"+block[good[0]["end"]:], start, 1),
        ("indirect-next", block[:good[1]["offset"]+1]+b"\x81"+block[good[1]["offset"]+2:], start, 1),
        ("truncated-next", block[:good[1]["end"]-1], start, None),
        ("wrong-leading", b"\x11"+block[start+1:good[-1]["end"]], 0, None),
        ("out-of-bounds", block, len(block), None),
        ("negative-offset", block, -1, None),
        ("zero-length", block[:start+2]+b"\x00"+block[start+3:], start, None),
    ]:
        try:
            result = packets(changed, offset)
        except ValueError:
            assert expected is None, name
        else:
            assert expected is not None and len(result) == expected, name
        cases.append(name)
    with tempfile.TemporaryDirectory() as directory:
        rebuilt = Path(directory)
        summary = generate(root, rebuilt)
        assert summary == read(output/"selection.json")
        for file in rebuilt.iterdir():
            assert file.read_bytes() == (output/"chain-inputs-r1"/file.name).read_bytes(), file.name
    write(output/"guards.json", dict(cases=cases, rebuilt_files=4, generator_sha256=sha(Path(__file__)),
        limits="在原版區塊副本變造指令及邊界，未改寫 guest；不是正常分支或 GUI 驗收。"))
    print("guards", len(cases), "rebuild", 4)


def evidence(root, output):
    assert read(output/"native-check.json")["records"] and read(output/"guards.json")["cases"]
    review = read(output/"chain-inputs-r1/chain-review-check.json")
    assert not review["errors"] and not review["term_warnings"] and review["review_only"]
    assert review["glossary_sha256"] == sha(root/"workplace/translation/glossary.tsv")
    assert review["input_sha256"] == sha(output/"chain-inputs-r1/zh-TW.review.tsv")
    assert review["source_sha256"] == sha(output/"chain-inputs-r1/en.tsv")
    assert review["font_sha256"] == "9d5bf4932d31fe94c18cd8cfddc98bc1b14ce10f4e354c682179db290a99c825"
    previous = read(root/"workplace/probe/ecl-source-20261024/evidence.json")
    formal_names = {"en.tsv", "zh-TW.tsv", "glossary.tsv", "catalog.json", "glossary-additions.tsv"}
    unchanged = [r for r in previous["sources"] if r["path"].startswith("workplace/translation/") and Path(r["path"]).name in formal_names]
    assert len(unchanged) == 5
    for row in unchanged:
        assert sha(root/row["path"]) == row["sha256"]
    sources = ["workplace/probe/ecl-source-20261024/evidence.json", "workplace/input/dos/drkqueen/DQK.EXE",
        "workplace/input/dos/drkqueen/DISK3/ECL.GLB", "workplace/translation/en.tsv", "workplace/translation/zh-TW.tsv",
        "workplace/translation/catalog.json", "workplace/translation/glossary-additions.tsv",
        "workplace/translation/glossary.tsv", "workplace/translation/passage-candidates.json",
        "workplace/translation/passage-review/zh-TW.review.tsv", "workplace/translation/passage-review/term-reviews.tsv",
        "workplace/probe/pane-render-20261022/observe-palace-journal-r1/final.state",
        "workplace/probe/battle-text-20261024/control-quick-r3/final.state",
        "workplace/probe/literal-catalog-20261024/bar-return-request-r2.json",
        "workplace/probe/ecl-source-20261024/inputs-r1/en.tsv"]
    names = ["passage_chain_probe.go", "passage_chain_inputs.py", "text_catalog.py", "translation_check.py"]
    snapshot = output/"tool-snapshots"
    snapshot.mkdir()
    for name in names:
        shutil.copy2(root/"tools"/name, snapshot/name)
    assert sha(root/"tools/passage_chain_probe.go") == sha(output/"programs-r1/passage_chain_probe.go")
    fragment_keys = {f["key"] for r in read(output/"chain-inputs-r1/registry.json")["occurrences"] for f in r["fragments"]}
    current = {r["key"] for r in load(root/"workplace/probe/ecl-source-20261024/inputs-r1/en.tsv", ["key", "text"])}
    def item(path):
        return dict(path=str(path.relative_to(root)), bytes=path.stat().st_size, sha256=sha(path))
    write(output/"evidence.json", dict(draft=True, selection=read(output/"selection.json"),
        fragments_in_current_catalog=len(fragment_keys & current), fragments_outside_current_catalog=len(fragment_keys-current),
        unchanged_formal_sources=unchanged, docker_images={k:v for k,v in previous["docker_images"].items() if k in ("go", "python", "fonttools")},
        font=dict(path="/home/anr2/cht/golden_box/death_knight_of_krynn/font/jf-openhuninn-2.1.ttf", sha256=review["font_sha256"]),
        sources=[item(root/p) for p in sources], tools={n:sha(root/"tools"/n) for n in names},
        artifacts=[item(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name!="evidence.json"],
        limits="整句子集尚未接入 GUI，原版首戰此路徑敗北；正式主表、字模與現行呈現程式不變。"))


def audit(root, output):
    report = read(output/"evidence.json")
    for row in report["sources"]+report["artifacts"]:
        p = root/row["path"]
        assert p.is_file() and p.stat().st_size == row["bytes"] and sha(p) == row["sha256"], p
        assert (p.stat().st_uid, p.stat().st_gid) == (1000,1000), p
    for name, expected in report["tools"].items():
        assert sha(root/"tools"/name) == sha(output/"tool-snapshots"/name) == expected
    assert {str(p.relative_to(root)) for p in output.rglob("*") if p.is_file() and p.name!="evidence.json"} == {r["path"] for r in report["artifacts"]}
    print("audited", len(report["artifacts"]), "artifacts", len(report["sources"]), "sources")


if __name__ == "__main__":
    command = sys.argv[1]
    operations = dict(native=native, prepare=prepare, guards=guards, evidence=evidence, audit=audit)
    if command not in operations:
        raise SystemExit("未知命令")
    operations[command](*map(Path, sys.argv[2:4]))
