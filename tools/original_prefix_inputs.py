"""以正常洞穴來源建立動態原文前綴的 DRAFT 輸入，不改正式譯文。"""
import hashlib
import json
from pathlib import Path
import shutil
import sys

from text_catalog import decode6, hlib


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def prepare(root, out):
    assert not (out / "evidence.json").exists()
    raw = (root / "workplace/input/dos/drkqueen/DISK3/ECL.GLB").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "40542071e42d3cd125eabcead11456a99942bf55a7736fdb79f66a3c27c3664d"
    blocks = hlib(raw)
    cases = []
    for directory in ("tunnel-observe-r1", "bend-observe-r1"):
        base = out / directory
        native = json.loads((base / "receipt.json").read_text())
        item = next(p for p in native["paragraphs"] if p["raw_b216"] == 0x81)
        assert item["caller"] == {"Seg": 0x26b4, "Off": 0x1d81}
        assert item["source_pointer"] == {"Seg": 0x333e, "Off": 0xb487}
        assert item["clear"] == 1 and item["foreground"] == 7 and item["background"] == 0
        assert item["native_box"] == [8, 136, 312, 184]
        script_path = base / native["script_files"][item["script_sha256"]]["file"]
        script = script_path.read_bytes()
        hits = [(i, a, b) for i, (a, b) in enumerate(blocks) if script[:b-a] == raw[a:b]]
        assert len(hits) == 1
        chunk, a, b = hits[0]
        offset = (item["raw_ae5c"]["Off"] + item["handler"]["raw_b7f9"]) & 65535
        end = (item["raw_ae5c"]["Off"] + item["raw_b7f9"]) & 65535
        assert script[offset:offset+2] == b"\x12\x81" and end > offset+2
        binding = dict(ChunkSHA256=hashlib.sha256(raw[a:b]).hexdigest(),
                       PacketSHA256=hashlib.sha256(script[offset:end]).hexdigest(),
                       ChunkBytes=b-a, Offset=offset, End=end)
        observation = dict(DS=item["regs"]["DS"], PointerSeg=0x333e, PointerOff=0xb487,
                           CallerSeg=0x26b4, CallerOff=0x1d81, RawBaseOffset=item["raw_ae5c"]["Off"],
                           RawCursorAfter=item["raw_b7f9"], Kind=0x81, Opcode=0x12, Clear=1, Source=item["source"])
        cases.append(dict(Binding=binding, Observation=observation, ScriptFile=str(script_path),
                          chunk=chunk, file_offset=a+offset, first_glyph=item["first_glyph"],
                          entry_step=item["step"], return_step=item["return_step"]))
    target = out / "prefix-inputs-r1"
    assert not target.exists()
    parent = root / "workplace/probe/voyage-text-20261025/inputs-r2"
    target.mkdir()
    for p in parent.iterdir():
        if p.is_file():
            shutil.copyfile(p, target / p.name)
    config = json.loads((target / "inputs.json").read_text())
    assert not config.get("OriginalPrefixes")
    config["OriginalPrefixes"] = [case["Binding"] for case in cases]
    write(target / "inputs.json", config)
    write(out / "prefix-source-fixture.json", dict(Cases=cases))
    source = out / "warning-start-control-r1/final.state"
    start = 8166000000
    keys = ["Up", "Return", "Left", "Up", "Up", "Right", "Up", "Up", "Return"]
    actions = [dict(at=start+i*20000000+1000000, end=start+(i+1)*20000000,
                    kind="named", key=key, label="prefix-"+str(i)) for i, key in enumerate(keys)]
    write(out / "prefix-request-r1.json", dict(state_sha256=sha(source), start_steps=start, actions=actions))
    write(out / "prefix-input-check.json", dict(bindings=len(cases), unchanged={p.name: sha(p) for p in parent.iterdir()
          if p.is_file() and p.name not in ("inputs.json", "provenance.json")},
          parent_config_sha256=sha(parent / "inputs.json"), current_config_sha256=sha(target / "inputs.json"),
          limits="兩個正常來源的原版前綴；原版、正式譯表、閱讀、字模不改，不外推其他 81h 或全部整句。"))
    print("prefix bindings", len(cases), "no catalog or glyph changes")


def samples(root, out):
    a, b = [json.loads((out / n / "receipt.json").read_text()) for n in ("prefix-observe-r1", "prefix-control-r1")]
    for key in ("checkpoints", "state_sha256", "request_sha256", "exe_sha256", "probe_sha256", "source_commit", "go_version"):
        assert a[key] == b[key], key
    assert not a["pending_paragraphs"] and not b["pending_paragraphs"]
    assert len(a["paragraphs"]) == 7
    for c in a["checkpoints"]:
        assert not c["file_writes"] and not c["unimplemented"]
        assert sha(out / "prefix-observe-r1" / (c["label"]+".png")) == sha(out / "prefix-control-r1" / (c["label"]+".png"))
    assert sha(out / "prefix-observe-r1/final.state") == sha(out / "prefix-control-r1/final.state")
    request = json.loads((out / "prefix-request-r1.json").read_text())
    points = {c["end"]: c["label"] for c in request["actions"]}
    windows = []
    for p in a["paragraphs"]:
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
    write(out / "prefix-request-r2.json", request)
    merged = []
    for first, last in sorted(windows):
        if merged and first <= merged[-1][1]:
            merged[-1][1] = max(last, merged[-1][1])
        else:
            merged.append([first, last])
    target = out / "prefix-inputs-r2"
    assert not target.exists()
    shutil.copytree(out / "prefix-inputs-r1", target)
    config = json.loads((target / "inputs.json").read_text())
    config["fine_windows"] = merged
    write(target / "inputs.json", config)
    write(out / "prefix-sampling.json", dict(paragraphs=7, original_prefixes=2, macro_checkpoints=9,
          boundary_checkpoints=len(actions)-9, fine_windows=merged,
          limits="代表性來源／首字形／返回邊界及穩定畫面抽驗，不宣稱所有繪製期間逐指令無閃爍。"))
    print("sampled checkpoints", len(actions), "fine windows", len(merged))


def batch(root, out):
    proof = json.loads((out / "prefix-check-r1.json").read_text())
    assert proof["new_fallbacks"] == 0 and proof["native_prefixes"] == 2
    fixture = json.loads((out / "prefix-source-fixture.json").read_text())
    packet = bytes.fromhex("12 81 01 04")
    assert all(c["Binding"]["PacketSHA256"] == hashlib.sha256(packet).hexdigest() for c in fixture["Cases"])
    raw = (root / "workplace/input/dos/drkqueen/DISK3/ECL.GLB").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "40542071e42d3cd125eabcead11456a99942bf55a7736fdb79f66a3c27c3664d"
    config = json.loads((out / "prefix-inputs-r2/inputs.json").read_text())
    continuations = {p["Key"] for p in config["Paragraphs"] if p["Caller"] == dict(Seg=0x26b4, Off=0x1d53)
                     and p["Clear"] == 0 and p["Foreground"] == 7 and p["Background"] == 0}
    rows, excluded = [], []
    for chunk, (a, b) in enumerate(hlib(raw)):
        block = raw[a:b]
        if len(block) > 0x8000:
            continue
        offset = 0
        while True:
            at = block.find(packet, offset)
            if at < 0:
                break
            offset, end = at+1, at+len(packet)
            if block[end:end+2] != b"\x11\x80" or end+3 >= len(block):
                excluded.append(dict(chunk=chunk, offset=at, reason="not-direct-literal"))
                continue
            length = block[end+2]
            if not length or end+3+length > len(block):
                excluded.append(dict(chunk=chunk, offset=at, reason="literal-bounds"))
                continue
            source = decode6(block[end+3:end+3+length])
            key = "ecl."+hashlib.sha256(source.encode()).hexdigest()[:20]
            if key not in continuations:
                excluded.append(dict(chunk=chunk, offset=at, reason="no-existing-translation-binding"))
                continue
            binding = dict(ChunkSHA256=hashlib.sha256(block).hexdigest(), PacketSHA256=hashlib.sha256(packet).hexdigest(),
                           ChunkBytes=len(block), Offset=at, End=end)
            rows.append(dict(chunk=chunk, file_offset=a+at, following_key=key, binding=binding))
    assert len(rows) == 88 and len({r["chunk"] for r in rows}) == 27
    bindings = [r["binding"] for r in rows]
    assert all(c["Binding"] in bindings for c in fixture["Cases"])
    target = out / "prefix-inputs-r3"
    assert not target.exists()
    shutil.copytree(out / "prefix-inputs-r2", target)
    config["OriginalPrefixes"] = bindings
    write(target / "inputs.json", config)
    write(out / "prefix-batch.json", dict(rows=rows, excluded=excluded, bindings=bindings,
        source_occurrences=len(rows), source_chunks=27, normal_sources_sampled=2,
        limits="相同已見證封包及已有繁中接句的批次綁定；實際呼叫仍核對整個區塊、游標、來源型別及呈現語境。不宣稱其餘 86 處已走訪。"))
    old_script = (out / "gui-prefix-r1.sh").read_text()
    (out / "gui-prefix-r3.sh").write_text(old_script.replace("/prefix-inputs-r2/", "/prefix-inputs-r3/"))
    print("batch source occurrences", len(rows), "chunks", 27, "normal samples", 2)


def evidence(root, out):
    assert not (out / "evidence.json").exists()
    report = json.loads((out / "prefix-check-r1.json").read_text())
    assert report["gpu_pairs"] == 441 and report["new_fallbacks"] == 0
    test = (out / "prefix-tests-r4.log").read_text()
    assert "FAIL" not in test and "SKIP" not in test and "PASS" in test
    names = {"original_prefix_inputs.py", "original_prefix_check.py", "text_catalog.py",
             "ui-list-live.sh", "early-live.sh", "battle_text.py", "cold_load.py",
             "load_prompt_inputs.py", "research_storage.py", "ui_list_live_check.py",
             "story_route_inputs.py", "oracle_video_observer.go", "oracle_input_modifier.go"}
    names.update(p.name for p in (out / "programs-r2").glob("*.go"))
    snapshots = out / "tool-snapshots"
    assert not snapshots.exists()
    snapshots.mkdir()
    for name in sorted(names):
        shutil.copyfile(root / "tools" / name, snapshots / name)
    sources = [root / "workplace/input/dos/drkqueen" / n for n in ("DQK.EXE", "DISK3/ECL.GLB")]
    sources.extend(root / "workplace/translation" / n for n in ("en.tsv", "zh-TW.tsv", "catalog.json", "glossary.tsv", "glossary-additions.tsv"))
    parent = root / "workplace/probe/voyage-text-20261025"
    sources.extend((parent / "evidence.json", parent / "ashore-control-r3/final.state"))
    sources.extend(p for p in (parent / "inputs-r2").iterdir() if p.is_file())
    probe = root / "workplace/probe"
    sources.extend(probe / n for n in ("captain-dialogue-20261025/programs-r1/ui-list-live",
        "passage-chain-live-20261024/programs-r1/passage-chain-probe", "combat-aim-route-20261024/programs-r3/ui-context-probe",
        "passage-chain-live-20261024/evidence.json", "passage-chain-live-20261024/source-run.json",
        "passage-chain-20261024/chain-inputs-r1/registry.json", "passage-chain-20261024/chain-inputs-r1/en.tsv"))
    def info(p):
        s = p.stat()
        assert s.st_uid == s.st_gid == 1000
        return dict(bytes=s.st_size, sha256=sha(p), uid=s.st_uid, gid=s.st_gid)
    write(out / "evidence.json", dict(draft=True, runtime_integrated=False, draft_runtime_integrated=True,
        effective=dict(inputs="prefix-inputs-r3", source="prefix-observe/control-r2", program="programs-r2/ui-list-live",
            gpu="prefix-en/zh-r3", baseline="prefix-old-zh-r1", checks="prefix-check-r1.json",
            next_state="prefix-control-r2/final.state"),
        verification=report, engine_commit="f79eab6db8c64a524a06535e53e5d32b0bbcf7c8",
        docker_images=dict(go="sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581",
            pillow="sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48"),
        tools={name: sha(root / "tools" / name) for name in sorted(names)},
        sources={str(p.relative_to(root)): info(p) for p in sources},
        artifacts={str(p.relative_to(out)): info(p) for p in sorted(out.rglob("*")) if p.is_file()},
        rights="原版、全文、字模與畫格只留本機；新前綴只保留原版識別字，不改遊戲規則、原文或存檔。"))


def audit(root, out):
    manifest = json.loads((out / "evidence.json").read_text())
    paths = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file() and p.name != "evidence.json"}
    assert paths == set(manifest["artifacts"])
    for base, records in ((root, manifest["sources"]), (out, manifest["artifacts"])):
        for name, row in records.items():
            p = base / name
            s = p.stat()
            assert s.st_size == row["bytes"] and s.st_uid == row["uid"] and s.st_gid == row["gid"] and sha(p) == row["sha256"], name
    for name, expected in manifest["tools"].items():
        assert sha(root / "tools" / name) == sha(out / "tool-snapshots" / name) == expected, name
    print("verified", len(manifest["artifacts"]), "artifacts", len(manifest["sources"]), "sources", len(manifest["tools"]), "tools")


if __name__ == "__main__":
    mode, project, output = sys.argv[1:]
    if mode not in ("prepare", "samples", "batch", "evidence", "audit"):
        raise ValueError(mode)
    globals()[mode](Path(project), Path(output))
