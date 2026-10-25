"""直接相鄰敘事的批次 DRAFT 資料，保留原版封包與來源界線。"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import subprocess

from passage_chain_inputs import packets
from text_catalog import decode6, hlib, write_tsv
from translation_check import load


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")


def prepare(root, out):
    target = out / "groups-r1"
    assert not target.exists() and not (out / "evidence.json").exists()
    source = root / "workplace/translation"
    raw = (root / "workplace/input/dos/drkqueen/DISK3/ECL.GLB").read_bytes()
    assert digest(raw) == "40542071e42d3cd125eabcead11456a99942bf55a7736fdb79f66a3c27c3664d"
    blocks = hlib(raw)
    groups = read(source / "passage-candidates.json")
    assert groups["source_sha256"] == digest(raw)
    reviews = {r["key"]: r for r in load(source / "passage-review/zh-TW.review.tsv", ["key", "text", "note"])}
    selected, occurrences, excluded = [], [], []
    for group in groups["groups"]:
        key, text = group["key"], group["text"]
        assert key == "passage."+digest(text.encode())[:20]
        if key not in reviews:
            excluded.append(dict(key=key, reason="unreviewed"))
            continue
        valid = []
        for origin in group["sources"]:
            a, b = blocks[origin["chunk"]]
            block = raw[a:b]
            at = origin["file_offset"]-a-1
            opcode = block[at]
            if opcode not in (0x11, 0x12) or any(j["bytes"] != "11" for j in origin["joins"]):
                continue
            limit_en, limit_zh = (128, 128) if opcode == 0x11 else (96, 144)
            if len(text) > limit_en or len(reviews[key]["text"]) > limit_zh:
                continue
            parsed = packets(block, at, opcode)
            assert len(parsed) == len(origin["fragments"]) >= 2
            assert parsed[-1]["end"] == origin["end_file_offset"]-a
            assert "".join(decode6(block[x["offset"]+3:x["end"]]) for x in parsed) == text
            for part, item in zip(parsed, origin["fragments"]):
                assert part["key"] == item["key"] and part["offset"]+1 == item["chunk_offset"]
            if len(block) > 0x8000:
                continue
            binding = dict(key=key, chunk=origin["chunk"], chunk_bytes=len(block), chunk_sha256=digest(block),
                file_offset=a+at, chunk_offset=at, end_chunk_offset=parsed[-1]["end"],
                packet_sha256=digest(block[at:parsed[-1]["end"]]), fragments=parsed)
            if opcode == 0x11:
                binding["leading_continuation"] = True
            valid.append(binding)
        if not valid:
            excluded.append(dict(key=key, reason="control-or-length"))
            continue
        target_text = reviews[key]["text"]
        assert not any(c in text+target_text for c in ("%", "\\", "\n", "\r", "\t"))
        selected.append((key, text, target_text))
        occurrences.extend(valid)
    old = read(root / "workplace/probe/passage-chain-20261024/chain-inputs-r1/registry.json")["occurrences"]
    assert all(b in occurrences for b in old)
    target.mkdir()
    write_tsv(target / "en.tsv", ["key", "text"], ((k, en) for k, en, _ in selected))
    write_tsv(target / "zh-TW.tsv", ["key", "text"], ((k, zh) for k, _, zh in selected))
    write(target / "registry.json", dict(source_sha256=digest(raw), draft=True, occurrences=occurrences,
        excluded=excluded, limits="相同來源契約的靜態子集；正常輸出順序與 GUI 另外抽驗，不跨控制指令。"))
    fragments = {f["key"] for b in occurrences for f in b["fragments"]}
    write(out / "group-selection.json", dict(groups=len(selected), occurrences=len(occurrences), fragment_keys=len(fragments),
        continuation_occurrences=sum(bool(b.get("leading_continuation")) for b in occurrences),
        parent_occurrences=len(old), excluded_groups=len(excluded), normal_verified=False, runtime_integrated=False))
    print(read(out / "group-selection.json"))


def inputs(root, out):
    assert not (out / "evidence.json").exists()
    parent = root / "workplace/probe/passage-island-20261025/prefix-inputs-r3"
    target = out / "inputs-r1"
    assert not target.exists()
    shutil.copytree(parent, target)
    counts = {}
    for name, expected in (("en.tsv", 6213), ("zh-TW.tsv", 6208)):
        before = (parent / name).read_bytes()
        rows = load(parent / name, ["key", "text"])
        extra = load(out / "groups-r1" / name, ["key", "text"])
        assert len(rows) == expected and len(extra) == 205
        assert not ({r["key"] for r in rows} & {r["key"] for r in extra})
        assert before.endswith(b"\n")
        additions = (out / "groups-r1" / name).read_bytes().split(b"\n", 1)[1]
        (target / name).write_bytes(before + additions)
        counts[name] = len(load(target / name, ["key", "text"]))
    glyphs = read(parent / "glyphs-16.json")
    added = read(out / "glyphs-added-16.json")
    assert glyphs.keys() == added.keys()
    # 唯一可改的字模欄位由實際格式決定；其餘字型參數逐一保留。
    for field in glyphs:
        if isinstance(glyphs[field], dict):
            for char, bitmap in added[field].items():
                assert char not in glyphs[field] or glyphs[field][char] == bitmap
                glyphs[field][char] = bitmap
        else:
            assert glyphs[field] == added[field], field
    write(target / "glyphs-16.json", glyphs)
    config = read(parent / "inputs.json")
    assert not config.get("PassageGroups") and len(config["OriginalPrefixes"]) == 88
    config["PassageGroups"] = read(out / "groups-r1/registry.json")["occurrences"]
    config["fine_windows"] = []
    write(target / "inputs.json", config)
    write(out / "inputs-check.json", dict(counts=counts, groups=205, source_occurrences=219,
          parent=str(parent), parent_config_sha256=sha(parent / "inputs.json"),
          parent_catalog_sha256={n: sha(parent / n) for n in counts},
          unchanged={p.name: sha(p) for p in parent.iterdir() if p.is_file() and
                     p.name not in (*counts, "inputs.json", "glyphs-16.json")}))
    print(counts)


def glyphs(root, out):
    parent = root / "workplace/probe/passage-island-20261025/prefix-inputs-r3/glyphs-16.json"
    rows = load(out / "groups-r1/zh-TW.tsv", ["key", "text"])
    needed = sorted(set("".join(r["text"] for r in rows)) - read(parent)["glyphs"].keys())
    assert len(needed) == 9
    target = out / "glyph-needed.tsv"
    raw = ("key\ttext\nfont.passage-needed\t"+"".join(needed)+"\n").encode()
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    print("缺字", "".join(needed))


def guards(root, out):
    assert not (out / "evidence.json").exists()
    with tempfile.TemporaryDirectory(prefix="rebuild-", dir=out) as name:
        fresh = Path(name)
        prepare(root, fresh)
        glyphs(root, fresh)
        assert (fresh / "glyph-needed.tsv").read_bytes() == (out / "glyph-needed.tsv").read_bytes()
        font = Path("/font/jf-openhuninn-2.1.ttf")
        assert font.is_file() and sha(font) == "9d5bf4932d31fe94c18cd8cfddc98bc1b14ce10f4e354c682179db290a99c825"
        subprocess.run([sys.executable, str(root / "tools/menu_glyphs.py"), str(font),
                        str(fresh / "glyph-needed.tsv"), str(fresh / "glyphs-added-16.json"), "16"], check=True)
        assert sha(fresh / "glyphs-added-16.json") == sha(out / "glyphs-added-16.json")
        inputs(root, fresh)
        names = [p.name for p in (fresh / "inputs-r1").iterdir() if p.is_file()]
        for n in names:
            assert sha(fresh / "inputs-r1" / n) == sha(out / "inputs-r1" / n), n
        for n in ("en.tsv", "zh-TW.tsv", "registry.json"):
            assert sha(fresh / "groups-r1" / n) == sha(out / "groups-r1" / n), n
    active = out / "inputs-r1"
    all_chars = set("".join(r["text"] for r in load(active / "zh-TW.tsv", ["key", "text"])))
    missing = all_chars - read(active / "glyphs-16.json")["glyphs"].keys()
    # 玩家姓名另保留原始像素；角色介面的 20px 子集沿父批，不在此字集內。
    group_chars = set("".join(r["text"] for r in load(out / "groups-r1/zh-TW.tsv", ["key", "text"])))
    assert not group_chars & missing
    write(out / "rebuild-check.json", dict(input_files=len(names), group_files=3, groups_font_complete=True,
          scope="完整批次來源重建、既有資料保留與新增整句缺字檢查；正常執行另抽驗。"))
    print(read(out / "rebuild-check.json"))


def samples(root, out):
    native, control = [read(out / n / "receipt.json") for n in ("observe-r1", "control-r1")]
    for field in ("checkpoints", "exe_sha256", "state_sha256", "request_sha256", "probe_sha256"):
        assert native[field] == control[field], field
    assert sha(out / "observe-r1/final.state") == sha(out / "control-r1/final.state")
    for cp in native["checkpoints"]:
        assert not cp["unimplemented"] and not cp["file_writes"]
        assert sha(out / "observe-r1" / (cp["label"]+".png")) == sha(out / "control-r1" / (cp["label"]+".png"))
    assert not native["pending_paragraphs"]
    request = read(out / "request-r1.json")
    points = {a["end"]: a["label"] for a in request["actions"]}
    windows = []
    for p in native["paragraphs"]:
        assert p["step"] < p["first_glyph"] < p["return_step"]
        for step in (p["step"], p["first_glyph"], p["return_step"]):
            points.setdefault(step-1, "sample-"+str(step-1))
            points.setdefault(step+1, "sample-"+str(step+1))
            windows.append([step-2000, step+4000])
    actions, previous, used = [], request["start_steps"], set()
    for step, label in sorted(points.items()):
        keys = [(i, c) for i, c in enumerate(request["actions"]) if previous <= c["at"] < step]
        assert len(keys) <= 1
        if keys:
            i, key = keys[0]
            used.add(i)
            actions.append(dict(at=key["at"], end=step, kind=key["kind"], key=key["key"], label=label))
        else:
            actions.append(dict(at=previous, end=step, kind="text", key="", label=label))
        previous = step
    assert len(used) == len(request["actions"])
    request["actions"] = actions
    write(out / "request-r2.json", request)
    merged = []
    for first, last in sorted(windows):
        if merged and first <= merged[-1][1]:
            merged[-1][1] = max(last, merged[-1][1])
        else:
            merged.append([first, last])
    config = read(out / "inputs-r1/inputs.json")
    config["fine_windows"] = merged
    target = out / "inputs-r2"
    assert not target.exists()
    shutil.copytree(out / "inputs-r1", target)
    write(target / "inputs.json", config)
    write(out / "sampling.json", dict(paragraphs=len(native["paragraphs"]), checkpoints=len(actions), fine_windows=merged,
          limits="來源／首字形／返回邊界與穩定畫面抽驗，未逐一走訪全部來源。"))
    print(read(out / "sampling.json"))


def record(path):
    s = path.stat()
    return dict(sha256=sha(path), bytes=s.st_size, uid=s.st_uid, gid=s.st_gid)


def evidence(root, out):
    assert not (out / "evidence.json").exists()
    proof = read(out / "check-r1.json")
    assert proof["gpu_pairs"] == 369 and proof["new_fallbacks"] == 0
    tests = (out / "source-tests-r1.log").read_text()
    assert "PASS" in tests and "FAIL" not in tests and "SKIP" not in tests
    names = {"passage_runtime_inputs.py", "passage_runtime_check.py", "passage_chain_inputs.py",
             "ui_passage_source_test.go", "ui_passage_runtime_test.go", "text_catalog.py", "translation_check.py",
             "original_prefix_check.py", "original_prefix_inputs.py", "menu_glyphs.py", "research_storage.py",
             "ui-list-live.sh", "early-live.sh", "battle_text.py", "cold_load.py", "load_prompt_inputs.py",
             "oracle_video_observer.go", "oracle_input_modifier.go"}
    names.update(p.name for p in (out / "programs-r2").glob("*.go"))
    target = out / "tool-snapshots"
    assert not target.exists()
    target.mkdir()
    for n in sorted(names):
        shutil.copyfile(root / "tools" / n, target / n)
    sources = [root / "workplace/input/dos/drkqueen" / n for n in ("DQK.EXE", "DISK3/ECL.GLB")]
    sources.extend(root / "workplace/translation" / n for n in ("en.tsv", "zh-TW.tsv", "catalog.json", "glossary.tsv",
                  "glossary-additions.tsv", "passage-candidates.json", "passage-review/zh-TW.review.tsv"))
    parent = root / "workplace/probe/passage-island-20261025"
    sources.extend(parent / n for n in ("evidence.json", "warning-start-control-r1/final.state",
                  "prefix-control-r2/final.state", "programs-r2/ui-list-live"))
    sources.extend(p for p in (parent / "prefix-inputs-r3").iterdir() if p.is_file())
    sources.append(root / "workplace/probe/passage-chain-live-20261024/programs-r1/passage-chain-probe")
    write(out / "evidence.json", dict(draft=True, state="SEALED", summary=proof,
          artifacts={str(p.relative_to(out)): record(p) for p in sorted(out.rglob("*")) if p.is_file()},
          sources={str(p.relative_to(root)): record(p) for p in sources},
          tools={n: record(target / n) for n in sorted(names)},
          limits="一組正常接續型抽驗，資料批次不等於逐處走訪；所有原版、譯文、字模及畫格只留本機。"))
    audit(root, out)


def audit(root, out):
    index = read(out / "evidence.json")
    assert index["state"] == "SEALED"
    for relative, expected in index["artifacts"].items():
        assert record(out / relative) == expected, relative
    for relative, expected in index["sources"].items():
        assert record(root / relative) == expected, relative
    for name, expected in index["tools"].items():
        assert record(out / "tool-snapshots" / name) == expected, name
    print("sealed audit", {n: len(index[n]) for n in ("artifacts", "sources", "tools")})


if __name__ == "__main__":
    mode, project, directory = sys.argv[1:]
    if mode not in ("prepare", "inputs", "samples", "glyphs", "guards", "evidence", "audit"):
        raise ValueError(mode)
    globals()[mode](Path(project), Path(directory))
