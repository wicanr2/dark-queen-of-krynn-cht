"""測試用 16px 詞框合成模型；呼叫端另核原版來源及哪些詞框應存在。"""
import base64

from PIL import Image


def masks16(data):
    assert data["size"] == 16 if "size" in data else data["Size"] == 16
    return {key: Image.frombytes("L", (16, 20), base64.b64decode(value)) for key, value in data["glyphs"].items()}


def compose_words(english, words, palette, translations, masks):
    expected = english.copy()
    for word in words or []:
        assert word.get("FontSize", 16) in (0, 16)
        x, y, width, height = [word.get(k, 8) * 2 for k in ("X", "Y", "Width", "Height")]
        assert 0 <= x < x + width <= 640 and 0 <= y < y + height <= 400
        bg, fg = [tuple(palette[word[key]]) for key in ("Background", "Foreground")]
        expected.paste(bg, (x, y, x + width, y + height))
        text = translations[word["Key"]]
        if "Number" in word:
            text = text.replace("%d", str(word["Number"]))
        assert len(text) * 16 <= width
        for i, char in enumerate(text):
            mask = masks[char]
            bbox = mask.getbbox()
            assert bbox is None or bbox[3] <= 16
            expected.paste(fg, (x + i * 16, y, x + (i + 1) * 16, y + 20), mask)
    return expected


def check_word_pair(english_root, chinese_root, control_root, state, request, profile, translations, masks):
    """核原版狀態及每張畫格；呼叫端另核應有來源、詞框與撤除時機。"""
    import hashlib
    import json
    from collections import Counter

    def read(path):
        return json.loads(path.read_text())

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    native = read(control_root / "receipt.json")
    a, b = [read(p / "receipt.json") for p in (english_root, chinese_root)]
    for run in (a, b):
        assert not run["unimplemented"]
        assert run["initial_state_sha256"] == sha(state)
        assert run["list_request_sha256"] == sha(request)
        assert run["list_inputs_sha256"] == sha(profile / "inputs.json")
        assert run["source_catalog_sha256"] == sha(profile / "en.tsv")
        assert run["catalog_sha256"] == sha(profile / "zh-TW.tsv")
        assert run["glyphs_sha256"] == sha(profile / "glyphs-16.json")
        assert len(run["checkpoints"]) == len(native["checkpoints"])
        for cp, expected in zip(run["checkpoints"], native["checkpoints"]):
            for key in ("step", "label", "regs", "ram_sha256", "indexed_sha256", "palette", "keys_consumed", "file_writes"):
                assert cp[key] == expected[key], (cp["label"], key)
            assert not cp["file_writes"]
    assert [f["step"] for f in a["frames"]] == [f["step"] for f in b["frames"]]
    assert len(b["frames"]) == len(b["list_frames"])
    checkpoints = {c["step"]: c for c in native["checkpoints"]}
    visible, examples = Counter(), {}
    held, previous = 0, None
    for x, y, meta in zip(a["frames"], b["frames"], b["list_frames"]):
        english, chinese = [Image.open(root / f["File"]).convert("RGB") for root, f in ((english_root, x), (chinese_root, y))]
        for f, image in ((x, english), (y, chinese)):
            assert hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest() == f["SHA256"]
        if x["step"] in checkpoints:
            original = Image.open(control_root / (checkpoints[x["step"]]["label"] + ".png")).convert("RGB")
            assert english.tobytes() == original.resize((640, 400), Image.Resampling.NEAREST).tobytes()
        assert not meta["paragraph"] and not meta["reader"]
        if y["held"]:
            assert previous is not None and previous["SHA256"] == y["SHA256"]
            held += 1
        else:
            assert chinese.tobytes() == compose_words(english, meta["words"], meta["palette"], translations, masks).tobytes()
            for word in meta["words"] or []:
                visible[word["Key"]] += 1
                examples[word["Key"]] = y["File"]
        previous = y
    return dict(gpu_pairs=len(b["frames"]), native_checkpoints=len(native["checkpoints"]), held=held,
                visible=dict(visible), examples=examples)
