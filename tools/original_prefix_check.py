"""抽驗動態原文前綴、既有譯文接句、畫格與原版狀態。"""
import base64
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image
from original_prefix_inputs import sha, write
from text_catalog import decode6, hlib


def read(path):
    return json.loads(path.read_text())


def image(path):
    return Image.open(path).convert("RGB")


def catalog(path):
    return dict(line.split("\t", 1) for line in path.read_text().splitlines()[1:])


def check(root, out):
    inputs = out / "prefix-inputs-r3"
    parent = root / "workplace/probe/voyage-text-20261025/inputs-r2"
    for p in parent.iterdir():
        if p.is_file():
            assert p.name == "inputs.json" or sha(p) == sha(inputs / p.name), p.name
    cfg, old_cfg = read(inputs / "inputs.json"), read(parent / "inputs.json")
    assert {k: v for k, v in cfg.items() if k not in ("OriginalPrefixes", "fine_windows")} == {
        k: v for k, v in old_cfg.items() if k != "fine_windows"}
    batch = read(out / "prefix-batch.json")
    assert cfg["OriginalPrefixes"] == batch["bindings"] and len(batch["rows"]) == 88
    assert all(c["Binding"] in cfg["OriginalPrefixes"] for c in read(out / "prefix-source-fixture.json")["Cases"])
    library = (root / "workplace/input/dos/drkqueen/DISK3/ECL.GLB").read_bytes()
    assert hashlib.sha256(library).hexdigest() == "40542071e42d3cd125eabcead11456a99942bf55a7736fdb79f66a3c27c3664d"
    blocks = hlib(library)
    for row in batch["rows"]:
        a0, b0 = blocks[row["chunk"]]
        block, binding = library[a0:b0], row["binding"]
        first, end = binding["Offset"], binding["End"]
        assert a0+first == row["file_offset"] and binding["ChunkBytes"] == len(block)
        assert hashlib.sha256(block).hexdigest() == binding["ChunkSHA256"]
        assert block[first:end] == bytes.fromhex("12 81 01 04")
        assert hashlib.sha256(block[first:end]).hexdigest() == binding["PacketSHA256"]
        assert block[end:end+2] == bytes.fromhex("11 80")
        source = decode6(block[end+3:end+3+block[end+2]])
        assert row["following_key"] == "ecl."+hashlib.sha256(source.encode()).hexdigest()[:20]
    en, zh = catalog(inputs / "en.tsv"), catalog(inputs / "zh-TW.tsv")
    glyphs = read(inputs / "glyphs-16.json")
    masks = {k: Image.frombytes("L", (glyphs["size"], glyphs["height"]), base64.b64decode(v)) for k, v in glyphs["glyphs"].items()}
    native, control = [read(out / n / "receipt.json") for n in ("prefix-observe-r2", "prefix-control-r2")]
    a, b, old = [read(out / n / "receipt.json") for n in ("prefix-en-r3", "prefix-zh-r3", "prefix-old-zh-r1")]
    fields = ("regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes", "step", "label")
    assert native["checkpoints"] == control["checkpoints"]
    assert len(a["checkpoints"]) == len(b["checkpoints"]) == len(old["checkpoints"]) == len(control["checkpoints"]) == 51
    for x, y, z, c in zip(a["checkpoints"], b["checkpoints"], old["checkpoints"], control["checkpoints"]):
        assert all(x[k] == y[k] == z[k] == c[k] for k in fields), c["label"]
        assert not c["file_writes"] and not c["unimplemented"]
    assert sha(out / "prefix-observe-r2/final.state") == sha(out / "prefix-control-r2/final.state")
    for run in (a, b, old):
        assert run["initial_state_sha256"] == sha(out / "warning-start-control-r1/final.state")
        assert run["list_request_sha256"] == sha(out / "prefix-request-r2.json")
        expected_inputs = out / "prefix-inputs-r2/inputs.json" if run is old else inputs / "inputs.json"
        assert run["list_inputs_sha256"] == sha(expected_inputs)
        assert not run["unimplemented"] and not run["reader_seen"] and not run["reader_ui_events"]
        assert run["ram_sha256"] == control["checkpoints"][-1]["ram_sha256"]
    assert a["paragraphs"] == b["paragraphs"] and len(b["paragraphs"]) == 7
    assert len(old["paragraphs"]) == 1
    assert sum(e["Kind"] == "unknown-paragraph-original" for e in old["list_events"]) == 6
    assert not [e for e in b["list_events"] if e["Kind"] == "unknown-paragraph-original"]
    entries = [e for e in b["list_events"] if e["Kind"] == "paragraph-before-glyph"]
    returned = [e for e in b["list_events"] if e["Kind"] == "original-prefix-return"]
    assert len(entries) == 7 and len(returned) == 2
    cps = {c["step"]: c for c in control["checkpoints"]}
    prefix_images, expected_text, prefix, components, colors = {}, "", None, [], []
    for p, page, entry in zip(native["paragraphs"], b["paragraphs"], entries):
        assert entry["Step"] == page["step"] == p["step"] < entry["first_glyph"] == p["first_glyph"] < p["return_step"]
        assert page["Source"] == p["source"] and page["Clear"] == p["clear"]
        assert page["Box"] == [16, 272, 624, 368] and page["Background"] == 8
        if p["raw_b216"] == 0x81:
            assert p["clear"] == 1 and page["Prefix"]["Text"] == p["source"] and 1 <= len(p["source"]) <= 15
            expected_text = p["source"]
            prefix = page["Prefix"]
            cp = cps[p["return_step"]+1]
            original = image(out / "prefix-control-r2" / (cp["label"]+".png"))
            cropped = original.crop((8, 136, 8+len(p["source"])*8, 144))
            event = next(e for e in returned if e["Step"] == p["return_step"])
            assert hashlib.sha256(cropped.tobytes()).hexdigest() == event["detail"]["rgb_sha256"]
            prefix_images[p["step"]] = cropped.resize((cropped.width*2, 16), Image.Resampling.NEAREST)
            components, colors = [page["Key"]], [p["foreground"]]
        else:
            key = "ecl."+hashlib.sha256(p["source"].encode()).hexdigest()[:20]
            assert page["Key"] == key and en[key] == p["source"]
            bindings = [v for v in cfg["Paragraphs"] if v["Key"] == key and v["Caller"] == p["caller"] and
                        v["NativeBox"] == p["native_box"] and all(v[k] == p[k.lower()] for k in ("Clear", "Foreground", "Background"))]
            assert len(bindings) == 1
            if p["clear"]:
                expected_text, prefix, components, colors = "", None, [], []
            expected_text += zh[key]
            components.append(key)
            colors.append(p["foreground"])
        assert page["Text"] == expected_text and page.get("Prefix") == prefix
        assert page["Components"] == components
        assert page.get("ComponentColors", [page["Foreground"]]*len(components)) == colors
        assert "".join(page["Lines"]) == expected_text
        assert len(page["Lines"])*glyphs["height"] <= 96 and all(len(s)*16 <= 608 for s in page["Lines"])
    af, bf, of = [r["frames"] for r in (a, b, old)]
    assert [f["step"] for f in af] == [f["step"] for f in bf] == [f["step"] for f in of]
    metadata = {f["step"]: f for f in b["list_frames"]}
    images = {}
    def gpu(name, frame):
        key = name, frame["File"]
        if key not in images:
            images[key] = image(out / name / frame["File"])
            assert hashlib.sha256(images[key].convert("RGBA").tobytes()).hexdigest() == frame["SHA256"]
        return images[key]
    body_cache = {}
    held = visible_prefix = visible_cjk = 0
    previous = None
    prefix_ranges, active_prefix = [], False
    for p in native["paragraphs"]:
        if p["clear"]:
            active_prefix = p["raw_b216"] == 0x81
        if active_prefix:
            prefix_ranges.append((p["step"], p["return_step"]))
    for x, y, z in zip(af, bf, of):
        english, chinese, legacy = gpu("prefix-en-r3", x), gpu("prefix-zh-r3", y), gpu("prefix-old-zh-r1", z)
        if x["step"] in cps:
            cp = cps[x["step"]]
            expected = image(out / "prefix-control-r2" / (cp["label"]+".png")).resize((640, 400), Image.Resampling.NEAREST)
            assert english.tobytes() == expected.tobytes(), ("original", x["step"])
        # 原版呼叫剛進入時，截點可先保存新 metadata，GPU 還是前一次提交。
        # 以獨立原版入口／返回範圍要求保留完整前畫面，不把 pending page 當作已顯示。
        painting = any(first <= y["step"] <= last for first, last in prefix_ranges)
        if y["held"] or painting:
            assert previous is not None and y["SHA256"] == previous["SHA256"], ("held", y["step"])
            held += 1
        else:
            for box in ((0, 0, 640, 272), (0, 368, 640, 400), (0, 272, 16, 368), (624, 272, 640, 368)):
                assert chinese.crop(box).tobytes() == legacy.crop(box).tobytes(), ("outside narrative", y["step"], box)
            page = metadata[y["step"]]["paragraph"]
            if page:
                cache_key = page["step"]
                if cache_key not in body_cache:
                    palette = metadata[y["step"]]["palette"]
                    expected = Image.new("RGB", (608, 96), tuple(palette[page["Background"]]))
                    prefix = page.get("Prefix")
                    text_colors = []
                    for key, color in zip(page["Components"], page.get("ComponentColors", [page["Foreground"]]*len(page["Components"]))):
                        value = prefix["Text"] if prefix and key == prefix["Key"] else zh[key]
                        text_colors.extend([color]*len(value))
                    n = 0
                    for row, line in enumerate(page["Lines"]):
                        for col, ch in enumerate(line):
                            if not prefix or n >= len(prefix["Text"]):
                                fg = Image.new("RGB", (16, glyphs["height"]), tuple(palette[text_colors[n]]))
                                at = col*16, row*glyphs["height"]
                                expected.paste(fg, at, masks[ch])
                            n += 1
                    if prefix:
                        source_step = max(s for s in prefix_images if s <= page["step"])
                        expected.paste(prefix_images[source_step], (0, 0))
                    body_cache[cache_key] = expected.tobytes()
                assert chinese.crop((16, 272, 624, 368)).tobytes() == body_cache[cache_key], ("paragraph pixels", y["step"])
                visible_prefix += bool(page.get("Prefix"))
                visible_cjk += not page["Key"].startswith("original-prefix.")
        previous = y
    assert visible_prefix > 0 and visible_cjk > 0
    b_frames = {f["step"]: f for f in bf}
    o_frames = {f["step"]: f for f in of}
    for label in ["prefix-"+str(i) for i in range(1, 7)] + ["prefix-8"]:
        cp = next(c for c in control["checkpoints"] if c["label"] == label)
        assert b_frames[cp["step"]]["SHA256"] == o_frames[cp["step"]]["SHA256"], ("return", label)
    # 批次資料的實測子集須與已通過的兩來源原型完全相同，只允許輸入檔雜湊改變。
    for run, name in ((a, "prefix-en-r2"), (b, "prefix-zh-r2")):
        sampled = read(out / name / "receipt.json")
        assert {k: v for k, v in run.items() if k != "list_inputs_sha256"} == {
            k: v for k, v in sampled.items() if k != "list_inputs_sha256"}
    write(out / "prefix-check-r1.json", dict(gpu_pairs=len(bf), checkpoints=51, paragraphs=7,
          source_bindings=88, source_blocks=27, normal_source_samples=2,
          native_prefixes=2, old_fallbacks=6, new_fallbacks=0, held_samples=held,
          visible_prefix_samples=visible_prefix, visible_cjk_samples=visible_cjk,
          original_cpu_ram_pixels_equal=True, original_prefix_rgb_equal=True, unaffected_ui_equal_old=True,
          limits="兩種原版前綴與一般段落的代表性抽驗；其餘整句、任意 81h、實體鍵盤與正式入口未驗。"))
    print(read(out / "prefix-check-r1.json"))


if __name__ == "__main__":
    check(Path(sys.argv[1]), Path(sys.argv[2]))
