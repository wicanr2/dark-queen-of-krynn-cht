"""攻略閱讀頁的可丟棄原型。內容與原掃描只從本機研究輸入讀取。"""

import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont


data_path, font_path, output = map(Path, sys.argv[1:4])
data = json.loads(data_path.read_text())
image = Image.new("RGB", (960, 600), "#18191d")
draw = ImageDraw.Draw(image)
fonts = {size: ImageFont.truetype(str(font_path), size) for size in (16, 20, 24)}
text_color, muted, accent = "#eee5d5", "#aaa59a", "#dfbd70"


def text(x, y, label, size=20, color=text_color):
    draw.text((x, y), label, font=fonts[size], fill=color, anchor="lt")


draw.rectangle((12, 12, 947, 587), outline="#777064", width=2)
text(32, 28, "黑暗之后　遊戲資料", 24)
text(765, 32, "閱讀面板原型", 16, muted)
for x, label in ((32, "旅行手札"), (172, "說明書"), (292, "攻略")):
    text(x, 78, label, 20, accent if label == "攻略" else muted)
draw.line((28, 108, 932, 108), fill="#777064", width=1)
draw.rectangle((28, 124, 226, 546), fill="#222329")
text(44, 140, "目錄", 20, accent)
text(44, 184, "導讀", 20, accent)
for chapter in range(1, 8):
    text(44, 184 + chapter * 40, f"第 {chapter} 章", 20, muted)
text(44, 514, "共 18 章", 16, muted)
text(254, 132, data["title"], 24, accent)
text(254, 168, data["source"], 16, muted)
text(254, 206, "文字閱讀", 20, accent)
draw.rectangle((390, 198, 510, 232), outline="#777064")
text(410, 206, "查看原頁", 20, muted)

x, y, width, bottom = 254, 252, 650, 514
line_height = 28
for paragraph in data["paragraphs"]:
    line = ""
    for char in paragraph:
        if draw.textlength(line + char, font=fonts[20]) > width:
            if y + line_height > bottom:
                raise ValueError("閱讀原型超出安全框")
            text(x, y, line)
            y += line_height
            line = ""
        line += char
    if y + line_height > bottom:
        raise ValueError("閱讀原型超出安全框")
    text(x, y, line)
    y += line_height + 16
text(254, 526, "試排節錄，全文尚待校對", 16, muted)
draw.line((28, 556, 932, 556), fill="#777064")
text(32, 568, "原作者：Steeler", 16, muted)
text(774, 568, "上一頁　下一頁", 16, muted)
image.save(output)
print(output)
