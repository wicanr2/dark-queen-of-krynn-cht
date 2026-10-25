"""將正式戰鬥短名稱衍生為既有欄位，並以父批正常路徑抽驗。入口見規格 001。"""
import csv
import hashlib
from pathlib import Path
import re
import shutil
import sys
import tempfile

from empty_notice_inputs import catalog, read, sha, write
from text_catalog import hlib

PARENT = "battle-continuation-20261025"
POSITIONS = ((8004, 8), (8040, 80), (8048, 96))


def derive(root):
    parent = root / "workplace/probe" / PARENT / "inputs-r1"
    cfg = read(parent / "inputs.json")
    en, zh = [catalog(parent / name) for name in ("en.tsv", "zh-TW.tsv")]
    formal_en, formal_zh = [catalog(root / "workplace/translation" / name) for name in ("en.tsv", "zh-TW.tsv")]
    metadata = read(root / "workplace/translation/catalog.json")
    raw_path = root / "workplace/input/dos/drkqueen/DISK2/MONCHA.GLB"
    raw = raw_path.read_bytes()
    blocks = hlib(raw)
    identity = next(x for x in metadata["inputs"] if x["path"] == "DISK2/MONCHA.GLB")
    assert sha(raw_path) == identity["sha256"] and len(blocks) == identity["blocks"] == 99
    names = [r for r in metadata["entries"] if r["domain"] == "name"]
    assert len(names) == len({r["key"] for r in names}) == 98
    glyphs = read(parent / "glyphs-16.json")["glyphs"]
    rows, excluded, additions = [], [], []
    old_keys = set(en)
    fmt = hashlib.sha256(b"%s").hexdigest()
    for row in names:
        key, source, digest = [row[n] for n in ("key", "text", "sha256")]
        assert key == "name." + digest[:20] and digest == hashlib.sha256(source.encode("ascii")).hexdigest()
        for origin in row["sources"]:
            assert origin["file"] == "DISK2/MONCHA.GLB"
            start, end = blocks[origin["chunk"]]
            offset = origin["file_offset"]
            assert start <= offset < offset + len(source) <= end
            assert raw[offset:offset + len(source)] == source.encode("ascii")
        if key not in formal_zh:
            excluded.append(dict(key=key, source=source, reason="no formal translation"))
            continue
        assert formal_en[key] == source and formal_zh[key]
        assert re.fullmatch(r"[A-Z][A-Z0-9 '\-]*[A-Z]", source) and 0 < len(source) <= 16
        assert len(formal_zh[key]) <= len(source) and set(formal_zh[key]) <= glyphs.keys()
        slots = []
        for raw_y, y in POSITIONS:
            template = dict(Pane="callsite", Group="body", Start=0, Length=len(source), SHA256=digest,
                 FormatSHA256=fmt, Caller=dict(Seg=0xb72, Off=0x27c), UpperCaller=dict(Seg=0x88e, Off=0x16fb),
                 UpperFormatSHA256=fmt, UpperNative=[184, y], RawX=8092, RawY=raw_y, Color=130, BackgroundOverride=23)
            matches = [f for f in cfg["Fields"] if all(f.get(k) == v for k, v in template.items())]
            assert len(matches) <= 1, (source, raw_y)
            if matches:
                field = matches[0]
                assert en[field["Key"]] == source and zh[field["Key"]] == formal_zh[key]
            else:
                en[key], zh[key] = source, formal_zh[key]
                field = dict(template, Key=key)
                cfg["Fields"].append(field)
                additions.append(field)
            slots.append(dict(raw_y=raw_y, native_y=y, key=field["Key"]))
        rows.append(dict(key=key, sha256=digest, source_origins=row["sources"], slots=slots))
    assert len(rows) == 96 and len(excluded) == 2
    assert len(additions) == 279 and len(set(en) - old_keys) == 92
    return cfg, en, zh, dict(names=rows, excluded=excluded, fields=additions,
                source_sha256=identity["sha256"], blocks=len(blocks), new_keys=sorted(set(en) - old_keys))


def prepare(root, out):
    cfg, en, zh, data = derive(root)
    target = out / "inputs-r1"
    assert not target.exists()
    shutil.copytree(root / "workplace/probe" / PARENT / "inputs-r1", target)
    write(target / "inputs.json", cfg)
    for name, values in (("en.tsv", en), ("zh-TW.tsv", zh)):
        (target / name).write_text("key\ttext\n" + "".join(k + "\t" + v + "\n" for k, v in sorted(values.items())))
    write(out / "bindings.json", data)
    provenance = read(target / "provenance.json")
    provenance["combat_names_extension"] = dict(parent=PARENT + "/inputs-r1", binding_sha256=sha(out / "bindings.json"),
            en_sha256=sha(target / "en.tsv"), zh_sha256=sha(target / "zh-TW.tsv"))
    write(target / "provenance.json", provenance)
    shutil.copyfile(root / "workplace/probe" / PARENT / "request-r1.json", out / "request.json")
    print("96 names, three slots each, 279 new fields, 92 catalog keys; no new glyphs")


def review_terms(root, out):
    def rows(path):
        with Path(path).open() as stream:
            return list(csv.DictReader(stream, delimiter="\t"))
    paths = ["/previous/" + n for n in ("glossary.tsv", "name.zh-TW.tsv", "name-lexicon-five.tsv", "name-events.tsv")]
    paths.append("/champions/glossary.tsv")
    prior = {}
    for path in (paths[0], paths[2]):
        for row in rows(path):
            if row.get("en") and row.get("zh"):
                prior.setdefault(row["en"].casefold(), []).append(dict(path=path, row=row, translation=row["zh"]))
    name_zh = {r["key"]: r for r in rows(paths[1])}
    events = {r["original_sha256"]: r for r in rows(paths[3])}
    champions = rows(paths[4])
    aliases = read(root / "workplace/probe" / PARENT / "bindings.json")["terms"]
    metadata = read(root / "workplace/translation/catalog.json")
    translated = catalog(root / "workplace/translation/zh-TW.tsv")
    records = []
    counts = dict(ghost=0, champions=0, formal=0)
    for name in metadata["entries"]:
        key = name["key"]
        if name["domain"] != "name" or key not in translated:
            continue
        matches = list(prior.get(name["text"].casefold(), []))
        if name["sha256"] in events:
            event = events[name["sha256"]]
            assert int(event["original_length"]) == len(name["text"]) and event["event_key"] == "name." + name["sha256"][:12]
            row = name_zh[event["event_key"]]
            matches.append(dict(path=paths[1], row=row, event=event, translation=row["translation"]))
        origin = "ghost" if matches else "formal"
        if not matches:
            matches = [dict(path=paths[4], row=r, translation=r["zh"]) for r in champions if r["en"].casefold() == name["text"].casefold()]
            if not matches and key in aliases:
                alias = aliases[key]
                assert alias["path"] in (paths[0], paths[4]) and sha(Path(alias["path"])) == alias["sha256"]
                assert alias["row"] in rows(alias["path"])
                matches = [dict(path=alias["path"], row=alias["row"], translation=alias["row"]["zh"], explicit_alias=True)]
            if matches:
                origin = "ghost" if all(m["path"].startswith("/previous/") for m in matches) else "champions"
        assert not matches or translated[key] in {m["translation"] for m in matches}, name["text"]
        counts[origin] += 1
        records.append(dict(key=key, origin=origin, matches=matches))
    assert len(records) == 96
    write(out / "term-review.json", dict(counts=counts, records=records, conflicts=0,
          sources={p: sha(Path(p)) for p in paths}, formal_zh_sha256=sha(root / "workplace/translation/zh-TW.tsv")))
    print("common terms", counts, "zero conflicts; remaining names retain reviewed formal translations")


def check(root, out):
    cfg, en_catalog, zh_catalog, data = derive(root)
    assert cfg == read(out / "inputs-r1/inputs.json") and data == read(out / "bindings.json")
    assert catalog(out / "inputs-r1/en.tsv") == en_catalog and catalog(out / "inputs-r1/zh-TW.tsv") == zh_catalog
    parent = root / "workplace/probe" / PARENT
    for p in (parent / "inputs-r1").iterdir():
        if p.is_file() and p.name not in ("inputs.json", "en.tsv", "zh-TW.tsv", "provenance.json"):
            assert sha(p) == sha(out / "inputs-r1" / p.name), p.name
    for p in (out / "programs-r1").glob("*.go"):
        assert sha(p) == sha(root / "tools" / p.name), p.name
    native, control = [read(parent / (name + "-r1/receipt.json")) for name in ("observe", "control")]
    assert native["checkpoints"] == control["checkpoints"]
    assert sha(parent / "observe-r1/final.state") == sha(parent / "control-r1/final.state")
    runs = []
    for language in ("en", "zh"):
        run = read(out / language / "receipt.json")
        old = read(parent / (language + "-r2/receipt.json"))
        assert not run["unimplemented"] and run["initial_state_sha256"] == native["state_sha256"]
        assert run["list_inputs_sha256"] == sha(out / "inputs-r1/inputs.json")
        assert run["list_request_sha256"] == sha(out / "request.json")
        for key in ("frames", "list_frames", "list_events", "checkpoints", "ram_sha256", "regs", "indexed_sha256", "palette"):
            assert run[key] == old[key], (language, key)
        assert len(run["checkpoints"]) == len(control["checkpoints"])
        for actual, expected in zip(run["checkpoints"], control["checkpoints"]):
            for key in ("regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes", "step", "label"):
                assert actual[key] == expected[key], key
        for frame in run["frames"]:
            assert sha(out / language / frame["File"]) == sha(parent / (language + "-r2") / frame["File"])
        runs.append(run)
    proof = read(parent / "check.json")
    assert proof["original_state_equal"] and proof["source_before_glyph"]
    write(out / "check.json", dict(original_state_equal=True, parent_render_equal=True, names=96,
          slots=288, new_fields=len(data["fields"]), new_keys=len(data["new_keys"]), excluded=data["excluded"],
          gpu_pairs=len(runs[1]["frames"]), native_checkpoints=len(control["checkpoints"]),
          source=len(en_catalog), translated=len(zh_catalog), glyphs_unchanged=True,
          representative_visible=proof["visible"], source_before_glyph=True,
          limits="96筆來源與三位置資料檢查；正常GUI仍只抽父批兩種龍人、守衛、傷害、垂死及撤除。未逐一走訪96名稱。"))
    print(read(out / "check.json"))


def rebuild(root, out):
    with tempfile.TemporaryDirectory(prefix="rebuild-", dir=out) as directory:
        fresh = Path(directory)
        prepare(root, fresh)
        for p in (out / "inputs-r1").iterdir():
            if p.is_file():
                assert sha(p) == sha(fresh / "inputs-r1" / p.name), p.name
        for name in ("bindings.json", "request.json"):
            assert sha(out / name) == sha(fresh / name), name
    write(out / "rebuild.json", dict(input_files=18, all_inputs_equal=True))


def seal(root, out):
    assert read(out / "check.json")["original_state_equal"] and read(out / "rebuild.json")["all_inputs_equal"]
    assert read(out / "term-review.json")["conflicts"] == 0
    assert not (out / "evidence.json").exists()
    probe = root / "workplace/probe"
    sources = list((probe / PARENT / "inputs-r1").iterdir())
    sources.extend(probe / PARENT / name for name in ("check.json", "observe-r1/receipt.json", "control-r1/receipt.json", "request-r1.json", "en-r2/receipt.json", "zh-r2/receipt.json", "control-r1/final.state"))
    sources.extend(root / name for name in ("workplace/translation/en.tsv", "workplace/translation/zh-TW.tsv", "workplace/translation/catalog.json", "workplace/input/dos/drkqueen/DQK.EXE", "workplace/input/dos/drkqueen/DISK2/MONCHA.GLB", "workplace/probe/weapon-hud-20261025/control-r5/final.state"))
    snapshots = out / "tool-snapshots"
    snapshots.mkdir()
    for name in ("combat_name_inputs.py", "empty_notice_inputs.py", "text_catalog.py"):
        shutil.copyfile(root / "tools" / name, snapshots / name)
    write(out / "evidence.json", dict(state="SEALED", draft=True, summary=read(out / "check.json"),
          artifacts={str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()},
          sources={str(p.relative_to(root)): sha(p) for p in sources if p.is_file()}))
    audit(root, out)


def audit(root, out):
    index = read(out / "evidence.json")
    assert index["state"] == "SEALED"
    for name, expected in index["artifacts"].items():
        assert sha(out / name) == expected, name
    for name, expected in index["sources"].items():
        assert sha(root / name) == expected, name
    print("sealed", len(index["artifacts"]), "artifacts", len(index["sources"]), "sources")


if __name__ == "__main__":
    mode, project, directory = sys.argv[1:]
    assert mode in ("prepare", "review_terms", "check", "rebuild", "seal", "audit")
    globals()[mode](Path(project), Path(directory))
