"""以原始圓體輪廓輸出固定字格 SVG，不裁字或縮放字墨；FontTools 容器限定。"""
import hashlib
import json
from pathlib import Path
import sys
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen

font_path,output=map(Path,sys.argv[1:3])
font_hash=hashlib.sha256(font_path.read_bytes()).hexdigest()
assert font_hash=="9d5bf4932d31fe94c18cd8cfddc98bc1b14ce10f4e354c682179db290a99c825"
font=TTFont(font_path);glyphs=font.getGlyphSet();unit=font["head"].unitsPerEm
rows=[]
for code in sys.argv[3:]:
    char=chr(int(code,16));name=font.getBestCmap()[ord(char)]
    pen=BoundsPen(glyphs);glyphs[name].draw(pen);bounds=pen.bounds
    assert 0<=bounds[0]<bounds[2]<=unit and (bounds[3]-bounds[1])*16/unit<=16
    path=SVGPathPen(glyphs);glyphs[name].draw(path)
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="20" viewBox="0 0 {unit} {unit*20/16}"><rect width="100%" height="100%" fill="black"/><path fill="white" transform="translate(0,{bounds[3]}) scale(1,-1)" d="{path.getCommands()}"/></svg>\n'
    target=output/(code+".svg");assert not target.exists();target.write_text(svg)
    rows.append(dict(char=char,svg=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),outline_bounds=bounds,
                     native_bounds=[v*16/unit for v in bounds],units_per_em=unit))
target=output/"outline-source.json";assert not target.exists()
target.write_text(json.dumps(dict(font_sha256=font_hash,size=16,height=20,glyphs=rows),ensure_ascii=False,indent=2)+"\n")
