"""由人工校讀的線段與地形重繪攻略樣張，不讀取或嵌入掃描圖。

研究輸入格式可變，尚非正式資料格式。輸出與輸入資料只留本機。
"""

import argparse
import base64
import hashlib
import html
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def render(data, font_path, font_license, output):
    output.mkdir(parents=True, exist_ok=True)
    width, height = 1280, 1020
    image = Image.new("RGB", (width, height), "#181d21")
    draw = ImageDraw.Draw(image)
    fonts = {n: ImageFont.truetype(str(font_path), n) for n in (16, 18, 20, 24, 32)}
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
           'role="img" aria-labelledby="title desc">',
           f'<title id="title">{html.escape(data["title"])}</title>',
           '<desc id="desc">依攻略來源人工重繪的校對樣張，尚未與遊戲逐格核對。</desc>',
           '<style>@font-face{font-family:dqk-map;src:url(data:font/ttf;base64,'
           + base64.b64encode(font_path.read_bytes()).decode("ascii")
           + ')}text{font-family:dqk-map,sans-serif} '
           '.point{cursor:pointer}.point:focus circle{stroke:#b54725;stroke-width:4}</style>']

    def rect(box, fill, stroke=None, line_width=1):
        x0, y0, x1, y1 = box
        draw.rectangle(box, fill=fill, outline=stroke, width=line_width)
        svg.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" '
                   f'fill="{fill}" stroke="{stroke or "none"}" stroke-width="{line_width}"/>')

    def poly(points, fill):
        draw.polygon(points, fill=fill)
        svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in points)}" fill="{fill}"/>')

    def line(points, fill, line_width=2):
        draw.line(points, fill=fill, width=line_width, joint="curve")
        svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" '
                   f'fill="none" stroke="{fill}" stroke-width="{line_width}" '
                   'stroke-linecap="round" stroke-linejoin="round"/>')

    def text(x, y, label, size=20, fill="#e9e4d8", max_width=None):
        if max_width is not None and draw.textlength(label, font=fonts[size]) > max_width:
            raise ValueError(f"文字超出安全框：{label}")
        draw.text((x, y), label, font=fonts[size], fill=fill, anchor="lt")
        svg.append(f'<text x="{x}" y="{y}" font-size="{size}" '
                   f'fill="{fill}" dominant-baseline="text-before-edge">{html.escape(label)}</text>')

    rect((0, 0, width, height), "#181d21")
    text(40, 28, data["title"], 32, max_width=1100)
    text(40, 76, "攻略地圖重繪・校對樣張", 20, "#d6bc83")
    text(40, 108, data["source_label"], 16, "#afb6b5")

    ox, oy, scale = 48, 160, 44
    columns, rows = data["size"]

    def point(p):
        return (ox + p[0] * scale, oy + p[1] * scale)

    rect((ox, oy, ox+columns*scale, oy+(rows-1)*scale), "#2b463e")
    # 林地符號是重新生成的向量，沒有來源像素。
    for y in range(rows-1):
        for x in range(columns):
            cx, cy = point((x+.5, y+.5))
            poly([(cx, cy-8), (cx-7, cy+5), (cx+7, cy+5)], "#49675b")
    for shape in data["floor"]:
        poly([point(p) for p in shape], "#f2ecd9")
    for shape in data["rubble"]:
        x0, y0, x1, y1 = shape
        x, y = point((x0, y0))
        w, h = (x1-x0)*scale, (y1-y0)*scale
        points = [(x+3, y), (x+w*.5, y+3), (x+w-2, y), (x+w, y+h*.5),
                  (x+w-3, y+h), (x+w*.5, y+h-3), (x, y+h), (x+3, y+h*.5)]
        poly(points, "#c8c0a8")
        for i in range(int(y1-y0)):
            line([(x+8, y+12+i*scale), (x+18, y+18+i*scale)], "#8a846f", 2)
    for box in data["blocked"]:
        x0, y0 = point(box[:2])
        x1, y1 = point(box[2:])
        rect((x0, y0, x1, y1), "#c7cfbf")
        for i in range(0, scale, 8):
            line([(x0+i, y0), (x1, y1-i)], "#637566", 2)
            if i:
                line([(x0, y0+i), (x1-i, y1)], "#637566", 2)
    for wall in data["walls"]:
        line([point(p) for p in wall], "#32453c", 3)
    for wall in data["tree_walls"]:
        a, b = map(point, wall)
        line([a, b], "#42644e", 7)
    for door in data["doors"]:
        cx, cy = point(door["at"])
        if door["axis"] == "h":
            rect((cx-9, cy-4, cx+9, cy+4), "#e6bb68", "#805f2d", 2)
        else:
            rect((cx-4, cy-9, cx+4, cy+9), "#e6bb68", "#805f2d", 2)
    for marker in data["markers"]:
        cx, cy = point(marker["at"])
        label = str(marker["id"])
        # 點位以向量座標保存；HTML 只改變檢視，不回寫遊戲。
        svg.append(f'<g class="point" data-point="{label}" tabindex="0" '
                   f'role="button" aria-label="標記 {label}">')
        draw.ellipse((cx-14, cy-14, cx+14, cy+14), fill="#f7f1df", outline="#805f2d", width=2)
        svg.append(f'<circle cx="{cx}" cy="{cy}" r="14" fill="#f7f1df" stroke="#805f2d" stroke-width="2"/>')
        text(cx-draw.textlength(label, font=fonts[18])/2, cy-10, label, 18, "#433b2c")
        svg.append("</g>")

    sx = 724
    rect((sx-20, 154, 1240, 938), "#242c30")
    text(sx, 176, "圖例", 24, "#d6bc83")
    for y, label, color in ((222, "可行走區域", "#f2ecd9"),
                            (258, "密林", "#2b463e"),
                            (294, "瓦礫", "#c8c0a8"),
                            (330, "不可通行", "#c7cfbf")):
        rect((sx, y, sx+22, y+22), color, "#89968d")
        text(sx+36, y, label, 20)
    line([(sx, 378), (sx+24, 378)], "#d0dfd0", 3)
    text(sx+36, 366, "牆", 20)
    rect((sx, 408, sx+24, 416), "#e6bb68", "#805f2d", 2)
    text(sx+36, 402, "門", 20)
    line([(sx, 450), (sx+24, 450)], "#63846c", 7)
    text(sx+36, 438, "樹牆", 20)
    text(sx, 496, "編號與正文對照", 24, "#d6bc83")
    summaries = data["legend_notes"]
    for i, (number, label) in enumerate(summaries):
        text(sx, 542+i*44, number, 20, "#d6bc83")
        text(sx+60, 542+i*44, label, 20, max_width=440)
    text(sx, 832, "原圖未標方向，暫不添加北箭頭。", 18, "#b9c2bf", 490)
    text(sx, 864, "幾何與標記依掃描校讀，尚未逐格驗遊戲。", 18, "#b9c2bf", 490)
    text(sx, 896, "線條、配色及閱讀版面皆為可調整樣張。", 18, "#b9c2bf", 490)
    text(40, 974, "原作者：Steeler　｜　重繪樣張　｜　來源頁碼與圖號保持可回查", 16, "#afb6b5")
    svg.append("</svg>")
    svg_text = "\n".join(svg)
    (output / "map.svg").write_text(svg_text, encoding="utf-8")
    (output / "FONT-LICENSE.txt").write_bytes(font_license.read_bytes())
    image.save(output / "map.png")
    marker_json = json.dumps(data["markers"], ensure_ascii=False).replace("<", "\\u003c")
    page = '''<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>攻略地圖重繪樣張</title>
<style>body{margin:0;background:#181d21;color:#eee5d5;font:18px sans-serif}
header{padding:12px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
body{font-family:dqk-map,sans-serif}
button{font:inherit;padding:6px 14px;background:#303c40;color:inherit;border:1px solid #6b796d}
#viewport{height:78vh;overflow:hidden;touch-action:none;background:#111719;cursor:grab}
#canvas{transform-origin:0 0;width:1280px;height:1020px}svg{display:block;width:1280px;height:1020px}
#detail{padding:16px;max-width:1100px;line-height:1.7}</style>
<header>攻略地圖重繪樣張 <button id="fit">符合視窗</button>
<button id="plus">放大</button><button id="minus">縮小</button>
<span>拖曳移動，點選編號查閱正文</span></header>
<div id="viewport"><div id="canvas">__SVG__</div></div>
<div id="detail" aria-live="polite">請點選圖上編號。樣張尚未接入遊戲。</div>
<script>
const markers=__MARKERS__, view=document.getElementById('viewport'),
canvas=document.getElementById('canvas'); let zoom=1,tx=0,ty=0,drag=null;
function apply(){canvas.style.transform=`translate(${tx}px,${ty}px) scale(${zoom})`;}
function fit(){zoom=Math.min(view.clientWidth/1280,view.clientHeight/1020);tx=0;ty=0;apply();}
function scale(factor){const old=zoom;zoom=Math.max(.25,Math.min(4,zoom*factor));
 const cx=view.clientWidth/2,cy=view.clientHeight/2;
 tx=cx-(cx-tx)*zoom/old;ty=cy-(cy-ty)*zoom/old;apply();}
document.getElementById('fit').onclick=fit;document.getElementById('plus').onclick=()=>scale(1.25);
document.getElementById('minus').onclick=()=>scale(.8);
function show(id){const m=markers.find(p=>String(p.id)===id);if(m)
document.getElementById('detail').textContent=`${m.id}｜${m.note}　來源：${m.evidence}`;}
document.querySelectorAll('.point').forEach(node=>{
node.onclick=()=>show(node.dataset.point);node.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){
e.preventDefault();show(node.dataset.point);}};});
view.onpointerdown=e=>{if(e.target.closest('.point'))return;
drag={x:e.clientX,y:e.clientY,tx,ty};view.setPointerCapture(e.pointerId);};
view.onpointermove=e=>{if(drag){tx=drag.tx+e.clientX-drag.x;ty=drag.ty+e.clientY-drag.y;apply();}};
view.onpointerup=view.onpointercancel=()=>drag=null;addEventListener('resize',fit);fit();
</script></html>'''.replace("__SVG__", svg_text).replace("__MARKERS__", marker_json)
    (output / "reader.html").write_text(page, encoding="utf-8")
    paths = [output/name for name in ("map.svg", "map.png", "reader.html", "FONT-LICENSE.txt")]
    return [{"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
             "bytes": p.stat().st_size} for p in paths]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--font-license", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.data.read_text())
    outputs = render(data, args.font, args.font_license, args.output)
    receipt = {"prototype": True, "input_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
               "font_sha256": hashlib.sha256(args.font.read_bytes()).hexdigest(),
               "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "files": outputs}
    (args.output/"receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(receipt, ensure_ascii=False))
