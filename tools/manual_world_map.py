"""從原生地形建立閱讀用向量示意圖；掃描只列來源，不讀取其像素。"""
import argparse
import base64
import csv
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def geometry(source, output):
    import cv2
    import numpy as np
    assert source.is_dir() and output.parent.is_dir() and not output.exists()
    image = Image.new('RGB', (304, 240))
    sources = []
    for n in (1, 2):
        path = source/f'BIGPIC.{n}.1.png'
        with Image.open(path) as item:
            assert item.size == (304, 120)
            image.paste(item.convert('RGB'), (0, (n-1)*120))
        sources.append(dict(path=path.name, sha256=sha(path)))
    # 僅為閱讀圖縮減色階，不解釋遊戲地形、通行或事件欄位。
    reduced = image.quantize(colors=24, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    colors = reduced.getpalette()
    labels = np.array(reduced)
    layers = []
    for value in sorted(set(reduced.tobytes())):
        mask = np.repeat(np.repeat((labels == value).astype(np.uint8)*255, 2, axis=0), 2, axis=1)
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        rings = []
        for i, contour in enumerate(contours):
            parent, depth = hierarchy[0][i][3], 0
            while parent >= 0:
                depth += 1
                parent = hierarchy[0][parent][3]
            points = (contour.reshape(-1, 2)/2).tolist()
            if len(points) < 3:
                x, y, w, h = cv2.boundingRect(contour)
                points = [[x/2,y/2],[(x+w)/2,y/2],[(x+w)/2,(y+h)/2],[x/2,(y+h)/2]]
            rings.append(dict(depth=depth, points=points))
        rgb = colors[value*3:value*3+3]
        paint = [round(v*.72+p*.28) for v, p in zip(rgb, [238, 224, 191])]
        layers.append(dict(source_rgb=rgb, fill='#'+bytes(paint).hex(), rings=rings))
    data = dict(state='reading-illustration', size=[304,240], sources=sources,
                native_rgb_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
                geometry='24-color cartographic contours; illustrative, not cell traversal',
                cv2=cv2.__version__, numpy=np.__version__, layers=layers)
    output.write_text(json.dumps(data, separators=(',', ':'))+'\n')
    print(json.dumps(dict(layers=len(layers), contours=sum(len(v['rings']) for v in layers), geometry_sha256=sha(output))))


def render(geo, layout_path, catalog_path, font_path, license_path, output):
    assert not output.exists() and output.parent.is_dir()
    data, layout = [json.loads(p.read_text()) for p in (geo, layout_path)]
    with catalog_path.open() as f:
        rows = list(csv.DictReader(f, delimiter='\t'))
    catalog = {r['key']: r['text'] for r in rows}
    assert len(catalog) == len(rows) == 23
    assert data['size'] == [304,240] and layout['scale'] == 3
    width, height = layout['canvas']
    left, top = layout['origin']
    scale = layout['scale']
    output.mkdir()
    png = Image.new('RGB', (width,height), '#f2ead9')
    draw = ImageDraw.Draw(png)
    root = ET.Element('svg', {'xmlns':'http://www.w3.org/2000/svg', 'viewBox':f'0 0 {width} {height}', 'role':'img'})
    ET.SubElement(root,'title').text = catalog['map.title']
    style = ET.SubElement(root,'style')
    style.text = "@font-face{font-family:mapfont;src:url(data:font/ttf;base64,"+base64.b64encode(font_path.read_bytes()).decode()+")}text{font-family:mapfont}"
    ET.SubElement(root,'rect',width='100%',height='100%',fill='#f2ead9')
    draw.rectangle((left,top,left+912,top+720),fill='#a7c6c7')
    ET.SubElement(root,'rect',x=str(left),y=str(top),width='912',height='720',fill='#a7c6c7')
    for layer in data['layers']:
        mask = Image.new('L',png.size)
        pen = ImageDraw.Draw(mask)
        paths=[]
        for ring in sorted(layer['rings'], key=lambda r:r['depth']):
            pts = [(left+x*scale,top+y*scale) for x,y in ring['points']]
            pen.polygon(pts,fill=255 if ring['depth']%2 == 0 else 0)
            paths.append('M'+'L'.join(f'{x:g},{y:g}' for x,y in pts)+'Z')
        # OpenCV 輪廓採取樣點中心。擴至相鄰取樣點邊界，避免色階間留下紙色細縫。
        for ring in layer['rings']:
            pts = [(left+x*scale,top+y*scale) for x,y in ring['points']]
            pen.line(pts+[pts[0]],fill=255,width=2)
        png.paste(layer['fill'],mask=mask)
        ET.SubElement(root,'path',d=''.join(paths),fill=layer['fill'],stroke=layer['fill'],**{'fill-rule':'evenodd','stroke-width':'1.5','stroke-linejoin':'round'})
    boxes=[]
    used=set()
    def text(key, x, y, size, center=False, boxed=False):
        value=catalog[key];used.add(key)
        font=ImageFont.truetype(str(font_path),size)
        advance=round(draw.textlength(value,font=font))
        if center:x-=advance//2
        box=[x-5,y-4,x+advance+5,y+size+7]
        assert 0<=box[0]<box[2]<=width and 0<=box[1]<box[3]<=height,(key,box)
        assert not any(box[0]<b[2] and b[0]<box[2] and box[1]<b[3] and b[1]<box[3] for b in boxes),(key,'label collision')
        boxes.append(box)
        if boxed:
            draw.rectangle(box,fill='#f2ead9',outline='#665947',width=1)
            ET.SubElement(root,'rect',x=str(box[0]),y=str(box[1]),width=str(box[2]-box[0]),height=str(box[3]-box[1]),fill='#f2ead9',stroke='#665947')
        draw.text((x,y),value,font=font,fill='#243f40',anchor='lt',stroke_width=0 if boxed else 2,stroke_fill='#f2ead9')
        node=ET.SubElement(root,'text',x=str(x),y=str(y+size),fill='#243f40',**{'font-size':str(size),'paint-order':'stroke','stroke':'none' if boxed else '#f2ead9','stroke-width':'3'})
        node.text=value
    text('map.title',width//2,12,34,True)
    for city in layout['cities']:
        x,y=city['point'];x,y=left+x*scale,top+y*scale
        lx,ly=city['label'];key='map.city.'+city['id']
        font=ImageFont.truetype(str(font_path),22)
        middle=lx+round(draw.textlength(catalog[key],font=font))/2
        line=[(middle,ly+11),(x,y)]
        draw.line(line,fill='#69553f',width=2)
        ET.SubElement(root,'path',d=f'M{middle:g},{ly+11}L{x},{y}',fill='none',stroke='#69553f',**{'stroke-width':'2'})
        draw.ellipse((x-4,y-4,x+4,y+4),fill='#f6efdd',outline='#694b33',width=2)
        ET.SubElement(root,'circle',cx=str(x),cy=str(y),r='4',fill='#f6efdd',stroke='#694b33',**{'stroke-width':'2'})
    for region in layout['regions']:
        x,y=region['point']
        text('map.region.'+region['id'],left+x*scale,top+y*scale,24,True)
    for city in layout['cities']:
        text('map.city.'+city['id'],*city['label'],22,boxed=True)
    text('map.note',32,1010,16)
    assert used == catalog.keys(), '圖文有未使用鍵'
    svg=output/'manual-world-map.svg';ET.ElementTree(root).write(svg,encoding='utf-8',xml_declaration=True)
    assert not any(n.tag.split('}')[-1]=='image' for n in ET.parse(svg).iter())
    png.save(output/'manual-world-map.png')
    shutil.copyfile(catalog_path,output/'labels.zh-TW.tsv')
    shutil.copyfile(license_path,output/'FONT-LICENSE.txt')
    receipt=dict(state='reading-illustration', source_geometry_sha256=sha(geo),layout_sha256=sha(layout_path),
                 catalog_sha256=sha(catalog_path),font_sha256=sha(font_path),tool_sha256=sha(Path(__file__)),
                 source_page=layout['source'],printed_page=layout['printed_page'],cities=len(layout['cities']),regions=len(layout['regions']),
                 labels=len(boxes), embedded_images=0,canvas=layout['canvas'],
                 limits=layout['scope'],sources=data['sources'],new_gameplay_verification=False,
                 files={p.name:sha(p) for p in output.iterdir() if p.is_file()})
    (output/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['files','sources']},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='mode',required=True)
    q=sub.add_parser('geometry');q.add_argument('source',type=Path);q.add_argument('output',type=Path)
    q=sub.add_parser('render')
    for n in ('geo','layout','catalog','font','license','output'):q.add_argument(n,type=Path)
    args=p.parse_args()
    if args.mode=='geometry':geometry(args.source,args.output)
    else:render(args.geo,args.layout,args.catalog,args.font,args.license,args.output)
