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
