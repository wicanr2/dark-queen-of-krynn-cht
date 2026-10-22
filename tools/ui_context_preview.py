"""已驗原版檢查點的離線字形對照圖；不作 runtime 語境判斷或無閃爍證明。"""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import PIL
from PIL import Image, ImageChops, ImageDraw, ImageFont


def sha(data):
    return hashlib.sha256(data).hexdigest()


def preview(observed, comparison, glossary, font_path, output):
    assert not output.exists(), "輸出必須全新"
    check = json.loads(comparison.read_text())
    receipt_path = observed / "receipt.json"
    assert check["observed_receipt_sha256"] == sha(receipt_path.read_bytes())
    assert check["checker_sha256"] == sha(Path(__file__).with_name("ui_context_check.py").read_bytes())
    assert check["draft"] and check["native_list_transactions"] > 0
    role = check["role"]
    assert role in ("inventory", "grimoire")
    category = {"inventory": "ui", "grimoire": "spell"}[role]
    with glossary.open(newline="", encoding="utf-8") as source:
        terms = [r for r in csv.DictReader(source, delimiter="\t")
                 if r["en"] == "Shield" and r["category"] == category]
    assert len(terms) == 1 and terms[0]["project"] == "death_knight_of_krynn"
    term = terms[0]
    assert sha(font_path.read_bytes()) == "9d5bf4932d31fe94c18cd8cfddc98bc1b14ce10f4e354c682179db290a99c825"
    font = ImageFont.truetype(str(font_path), 16)
    receipt = json.loads(receipt_path.read_text())
    checked_images = {r["label"]: r["rgb_sha256"] for r in check["images_equal"]}
    renders = []
    output.mkdir()
    for match in check["shield_occurrences"]:
        point = next(p for p in receipt["checkpoints"] if p["step"] >= match["return_step"])
        # 只取字串後第一個檢查點，若同一批之後另有列表重繪就拒絕猜測。
        event = receipt["list_events"][match["list_index"]]
        assert not any(event["return_instruction_step"] < e["step"] <= point["step"]
                       for e in receipt["list_events"])
        image_path = observed / (point["label"] + ".png")
        original_native = Image.open(image_path).convert("RGB")
        assert original_native.size == (320, 200)
        assert sha(original_native.tobytes()) == checked_images[point["label"]]
        original = original_native.resize((640, 400), Image.Resampling.NEAREST)
        translated = original.copy()
        x, y, w, h = [v * 2 for v in match["word_after_list_native_rect"]]
        assert 0 <= x < x + w <= 640 and 0 <= y < y + h <= 400
        fg = tuple(point["palette"][match["foreground"]])
        # 原版第二個顏色參數不等於此圖的背景色盤索引。只接受已驗文字框內
        # 實際可見的一種背景色，不把參數 8 推測成 palette[8]。
        colors = set(original.crop((x, y, x + w, y + h)).getdata())
        assert fg in colors and len(colors) == 2
        bg = next(iter(colors - {fg}))
        ink = Image.new("L", (w, h))
        draw = ImageDraw.Draw(ink)
        bounds = draw.textbbox((0, 0), term["zh"], font=font, anchor="lt")
        assert bounds[0] == bounds[1] == 0 and bounds[2] <= w and bounds[3] <= h
        draw.text((0, (h - bounds[3]) // 2), term["zh"], font=font, anchor="lt", fill=255)
        assert ink.getbbox() is not None
        translated.paste(bg, (x, y, x + w, y + h))
        translated.paste(Image.new("RGB", (w, h), fg), (x, y), ink)
        diff = ImageChops.difference(original, translated)
        assert diff.getbbox() is not None
        outside = diff.copy()
        ImageDraw.Draw(outside).rectangle((x, y, x + w - 1, y + h - 1), fill=(0, 0, 0))
        assert outside.getbbox() is None, "中文不得改動其他欄、加值或背景"
        stem = f"{role}-{match['call_index']}"
        translated.save(output / (stem + ".png"))
        pair = Image.new("RGB", (1280, 400))
        pair.paste(original, (0, 0))
        pair.paste(translated, (640, 0))
        pair.save(output / (stem + "-comparison.png"))
        renders.append({"call_index": match["call_index"], "checkpoint": point["label"],
                        "original_png_sha256": sha(image_path.read_bytes()),
                        "translated_png_sha256": sha((output / (stem + ".png")).read_bytes()),
                        "comparison_png_sha256": sha((output / (stem + "-comparison.png")).read_bytes()),
                        "word_rect_640": [x, y, w, h], "ink_rect_local": ink.getbbox(),
                        "foreground_rgb": fg, "measured_background_rgb": bg,
                        "original_background_argument": match["background_argument"],
                        "outside_word_pixels_equal": True})
    result = {"draft": True, "offline_only": True, "role_from_verified_test_route": role,
              "term_source": term, "font_pixels": 16, "font_decision": "未定案的離線試排",
              "pillow_version": PIL.__version__, "renders": renders,
              "comparison_sha256": sha(comparison.read_bytes()),
              "glossary_sha256": sha(glossary.read_bytes()), "font_sha256": sha(font_path.read_bytes()),
              "tool_sha256": sha(Path(__file__).read_bytes()),
              "limits": "已知測試流程指定語境，只取六次已驗 Shield 的第一張後續檢查點。沒有自動分類、遊戲接入、連續畫格、無閃爍、離開殘字或完整列表中文的驗收聲明。"}
    (output / "receipt.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return {"role": role, "previews": len(renders), "outside_word_pixels_equal": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("observed", "comparison", "glossary", "font", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(preview(args.observed, args.comparison, args.glossary, args.font, args.output), ensure_ascii=False))
