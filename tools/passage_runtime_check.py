"""抽驗整句交易、原版狀態、實際中文字形與回退邊界。"""
import base64
import hashlib
from pathlib import Path
import sys

from PIL import Image
from original_prefix_check import catalog, image, read
from passage_runtime_inputs import sha, write


def check(root, out):
    inputs = out / "inputs-r2"
    parent = root / "workplace/probe/passage-island-20261025/prefix-inputs-r3"
    cfg, before = read(inputs / "inputs.json"), read(parent / "inputs.json")
    assert {k: v for k, v in cfg.items() if k not in ("PassageGroups", "fine_windows")} == {
        k: v for k, v in before.items() if k != "fine_windows"}
    assert cfg["PassageGroups"] == read(out / "groups-r1/registry.json")["occurrences"]
    assert len(cfg["PassageGroups"]) == 219
    for p in parent.iterdir():
        if p.is_file() and p.name not in ("inputs.json", "glyphs-16.json", "en.tsv", "zh-TW.tsv"):
            assert sha(p) == sha(inputs / p.name), p.name
    for name in ("en.tsv", "zh-TW.tsv"):
        assert (inputs / name).read_bytes() == (parent / name).read_bytes() + (out / "groups-r1" / name).read_bytes().split(b"\n", 1)[1]
    zh = catalog(inputs / "zh-TW.tsv")
    glyphs = read(inputs / "glyphs-16.json")
    old_glyphs = read(parent / "glyphs-16.json")
    assert len(glyphs["glyphs"]) == 2752
    assert all(glyphs["glyphs"][k] == v for k, v in old_glyphs["glyphs"].items())
    masks = {k: Image.frombytes("L", (16, glyphs["height"]), base64.b64decode(v)) for k, v in glyphs["glyphs"].items()}
    native, control = [read(out / n / "receipt.json") for n in ("observe-r2", "control-r2")]
    a, b, old = [read(out / n / "receipt.json") for n in ("en-r1", "zh-r1", "old-zh-r1")]
    assert native["checkpoints"] == control["checkpoints"]
    assert sha(out / "observe-r2/final.state") == sha(out / "control-r2/final.state")
    assert len(control["checkpoints"]) == 53 and len(native["paragraphs"]) == 8
    fields = ("regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes", "step", "label")
    for run in (a, b, old):
        assert run["initial_state_sha256"] == sha(out / "girl-observe-r1/final.state")
        assert run["list_request_sha256"] == sha(out / "request-r2.json")
        assert run["list_inputs_sha256"] == sha(inputs / "inputs.json")
        assert len(run["checkpoints"]) == 53 and not run["unimplemented"]
        assert not run["reader_seen"] and not run["reader_ui_events"]
        for cp, original in zip(run["checkpoints"], control["checkpoints"]):
            assert all(cp[k] == original[k] for k in fields), original["label"]
            assert not original["unimplemented"] and not original["file_writes"]
        assert run["ram_sha256"] == control["checkpoints"][-1]["ram_sha256"]
    assert a["paragraphs"] == b["paragraphs"]
    key = "passage.36dcf45b3fb5546a23b5"
    binding = next(p for p in cfg["PassageGroups"] if p["key"] == key)
    assert binding["leading_continuation"]
    original = native["paragraphs"][-2:]
    assert "".join(p["source"] for p in original) == catalog(inputs / "en.tsv")[key]
    raw = (out / "observe-r2" / native["script_files"][original[0]["script_sha256"]]["file"]).read_bytes()
    assert hashlib.sha256(raw[:binding["chunk_bytes"]]).hexdigest() == binding["chunk_sha256"]
    assert hashlib.sha256(raw[binding["chunk_offset"]:binding["end_chunk_offset"]]).hexdigest() == binding["packet_sha256"]
    for p, fragment in zip(original, binding["fragments"]):
        assert (p["raw_ae5c"]["Off"] + p["raw_b7f9"]) & 65535 == fragment["end"]
        assert p["raw_b216"] == 128 and p["raw_b1c7"] == 17 and p["clear"] == 0
        assert p["native_box"] == [8, 136, 312, 184] and p["foreground"] == 7 and p["background"] == 0
        assert p["caller"] == dict(Seg=0x26b4, Off=0x1d53)
        assert p["step"] < p["first_glyph"] < p["return_step"]
    assert original[0]["return_step"] < original[1]["step"]
    parts = [e for e in b["list_events"] if e["Kind"] == "passage-part-before-glyph"]
    returned = [e for e in b["list_events"] if e["Kind"] == "passage-part-return"]
    assert len(parts) == len(returned) == 2
    for i, (p, entry, done) in enumerate(zip(original, parts, returned)):
        assert entry["Step"] == p["step"] and entry["first_glyph"] == p["first_glyph"]
        assert done["Step"] == p["return_step"]
        assert entry["detail"]["part"] == done["detail"]["part"] == i
    completed = [e for e in b["list_events"] if e["Kind"] == "passage-complete"]
    assert len(completed) == 1 and completed[0]["Step"] == original[-1]["return_step"]
    assert not [e for e in b["list_events"] if e["Kind"] == "passage-original"]
    unknown = [e for e in b["list_events"] if e["Kind"] == "unknown-paragraph-original"]
    old_unknown = [e for e in old["list_events"] if e["Kind"] == "unknown-paragraph-original"]
    boundary = original[-1]["return_step"]
    assert not [e for e in unknown if e["Step"] <= boundary]
    assert len([e for e in old_unknown if e["Step"] <= boundary]) == 2
    # 返回後新戰鬥的未知武器／狀態仍保留原版，必須與舊版同位置、同原因。
    retained = [e for e in old_unknown if e["Step"] > boundary]
    assert len(retained) == len(unknown) == 2
    assert [(e["Step"], e["detail"]) for e in unknown] == [(e["Step"], e["detail"]) for e in retained]
    assert len(b["paragraphs"]) == 7 and len(old["paragraphs"]) == 6
    page = next(p for p in b["paragraphs"] if p["Key"] == key)
    previous = b["paragraphs"][b["paragraphs"].index(page)-1]
    assert page["Text"] == previous["Text"] + zh[key]
    assert page["Components"] == previous["Components"] + [key]
    assert page["Source"] == "".join(p["source"] for p in original)
    frames = [r["frames"] for r in (a, b, old)]
    assert [f["step"] for f in frames[0]] == [f["step"] for f in frames[1]] == [f["step"] for f in frames[2]]
    metadata = {f["step"]: f for f in b["list_frames"]}
    cps = {c["step"]: c for c in control["checkpoints"]}
    cache, bodies = {}, {}
    def gpu(name, frame):
        k = name, frame["File"]
        if k not in cache:
            im = image(out / name / frame["File"])
            assert hashlib.sha256(im.convert("RGBA").tobytes()).hexdigest() == frame["SHA256"]
            cache[k] = im
        return cache[k]
    held = visible = ordinary = released = 0
    last = None
    for x, y, z in zip(*frames):
        english, chinese, legacy = gpu("en-r1", x), gpu("zh-r1", y), gpu("old-zh-r1", z)
        if x["step"] in cps:
            cp = cps[x["step"]]
            expected = image(out / "control-r2" / (cp["label"]+".png")).resize((640, 400), Image.Resampling.NEAREST)
            assert english.tobytes() == expected.tobytes(), ("original", x["step"])
        # pending page 可先記錄，只有已提交 GPU 畫格才算實際顯示。
        painting = original[0]["step"] <= y["step"] <= original[-1]["return_step"]
        if y["held"] or painting:
            assert last is not None and y["SHA256"] == last["SHA256"], ("hold", y["step"])
            held += 1
        else:
            for box in ((0, 0, 640, 272), (0, 368, 640, 400), (0, 272, 16, 368), (624, 272, 640, 368)):
                assert chinese.crop(box).tobytes() == legacy.crop(box).tobytes(), ("outside", y["step"], box)
            p = metadata[y["step"]]["paragraph"]
            if p:
                assert not p.get("Prefix")
                assert p["Box"] == [16, 272, 624, 368] and p["Background"] == 8
                assert "".join(p["Lines"]) == p["Text"] and len(p["Lines"])*glyphs["height"] <= 96
                assert all(len(s)*16 <= 608 for s in p["Lines"])
                if p["step"] not in bodies:
                    pal = metadata[y["step"]]["palette"]
                    expected = Image.new("RGB", (608, 96), tuple(pal[p["Background"]]))
                    colors = []
                    for k, color in zip(p["Components"], p.get("ComponentColors", [p["Foreground"]]*len(p["Components"]))):
                        colors.extend([color]*len(zh[k]))
                    assert len(colors) == len(p["Text"])
                    pos = 0
                    for row, line in enumerate(p["Lines"]):
                        for col, ch in enumerate(line):
                            fg = Image.new("RGB", (16, glyphs["height"]), tuple(pal[colors[pos]]))
                            expected.paste(fg, (col*16, row*glyphs["height"]), masks[ch])
                            pos += 1
                    bodies[p["step"]] = expected.tobytes()
                assert chinese.crop((16, 272, 624, 368)).tobytes() == bodies[p["step"]], ("glyphs", y["step"])
                if p["Key"] == key:
                    assert y["step"] > original[-1]["return_step"]
                    visible += 1
                else:
                    assert y["SHA256"] == z["SHA256"], ("ordinary", y["step"])
                    ordinary += 1
            elif y["step"] > original[-1]["return_step"]:
                assert y["SHA256"] == z["SHA256"]
                released += 1
        last = y
    assert visible > 0 and ordinary > 0 and released > 0
    write(out / "check-r1.json", dict(groups=205, source_occurrences=219, normal_groups=1, native_parts=2,
          gpu_pairs=len(frames[1]), checkpoints=53, held_samples=held, visible_whole_samples=visible,
          ordinary_samples=ordinary, released_samples=released, old_fallbacks=2, new_fallbacks=0,
          retained_original_battle_paragraphs=2,
          original_cpu_ram_pixels_equal=True, whole_source_before_first_glyph=True, commit_after_last_return=True,
          limits="一個正常兩片段接續型與前文／返回的代表性抽驗；其餘來源未逐一走訪，正式入口仍未完成。"))
    print(read(out / "check-r1.json"))


if __name__ == "__main__":
    check(Path(sys.argv[1]), Path(sys.argv[2]))
