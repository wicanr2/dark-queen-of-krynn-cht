"""由人工校讀的幾何與圖號重繪攻略圖。研究格式，不接遊戲座標。

來源掃描只核雜湊與尺寸，不取像素。地形、線段、符號和文字皆由本工具繪製。
"""
import argparse
import base64
import hashlib
import html
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_doors(record):
    paths=record.get('walls',[])+[p+[p[0]] for p in record['floor']]
    for x0,y0,x1,y1 in record.get('pits',[])+record.get('blocked',[]):
        paths.append([[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]])
    segments=[(a,b) for path in paths for a,b in zip(path,path[1:])]
    for door in record.get('doors',[]):
        x,y=door['at'];axis=door.get('axis','h')
        matched=False
        for a,b in segments:
            if axis=='h' and abs(a[1]-y)<.01 and abs(b[1]-y)<.01:
                matched |= min(a[0],b[0])-.01<=x<=max(a[0],b[0])+.01
            elif axis=='v' and abs(a[0]-x)<.01 and abs(b[0]-x)<.01:
                matched |= min(a[1],b[1])-.01<=y<=max(a[1],b[1])+.01
        if not matched:
            raise ValueError(f'{record["id"]}: 門未接在線段上 {door}')


LABELS = {'wall': '牆', 'door': '門', 'arch': '拱門', 'secret': '密門',
          'one-way': '單向門', 'up': '上樓', 'down': '下樓',
          'blocked': '不可通行', 'pit': '坑洞', 'teleport': '傳送點',
          'magic': '魔法門', 'false': '假門', 'stairs': '樓梯',
          'forest': '密林', 'rubble': '瓦礫'}


class Painter:
    def __init__(self, font):
        self.image = Image.new('RGB', (1100, 1040), '#182329')
        self.draw = ImageDraw.Draw(self.image)
        self.fonts = {n: ImageFont.truetype(str(font), n) for n in (18, 20, 24, 32)}
        self.svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 1040">',
                    '<style>@font-face{font-family:map;src:url(data:font/ttf;base64,' +
                    base64.b64encode(font.read_bytes()).decode() +
                    ')}text{font-family:map,sans-serif}</style>']
        self.box((0, 0, 1100, 1040), '#182329')

    def box(self, box, fill, stroke=None, width=2):
        x0,y0,x1,y1 = box
        self.draw.rectangle(box, fill=fill, outline=stroke, width=width)
        self.svg.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" '
                        f'fill="{fill}" stroke="{stroke or "none"}" stroke-width="{width}"/>')

    def line(self, points, fill='#34494c', width=4):
        self.draw.line(points, fill=fill, width=width, joint='curve')
        ps = ' '.join(f'{x},{y}' for x,y in points)
        self.svg.append(f'<polyline points="{ps}" fill="none" stroke="{fill}" '
                        f'stroke-width="{width}" stroke-linejoin="round"/>')

    def polygon(self, points, fill, stroke=None):
        self.draw.polygon(points, fill=fill)
        ps = ' '.join(f'{x},{y}' for x,y in points)
        self.svg.append(f'<polygon points="{ps}" fill="{fill}"/>')
        if stroke:
            self.line(points + [points[0]], stroke)

    def text(self, at, label, size=20, color='#f1e5c9', center=False):
        x,y = at
        font = self.fonts[size]
        if center:
            box = self.draw.textbbox((0,0), label, font=font)
            x -= self.draw.textlength(label, font=font)/2
            y -= (box[3]+box[1])/2
        self.draw.text((x,y), label, font=font, fill=color)
        self.svg.append(f'<text x="{x}" y="{y}" dominant-baseline="text-before-edge" '
                        f'font-size="{size}" fill="{color}">{html.escape(label)}</text>')

    def symbol(self, kind, at, axis='h', radius=12):
        x,y = at
        if kind in ('door','secret','one-way','magic','false'):
            w,h = (radius, radius*.3) if axis=='h' else (radius*.3, radius)
            color = '#be9b52' if kind!='magic' else '#9775ba'
            self.box((x-w,y-h,x+w,y+h), '#e5cc89', color)
            if kind=='false':
                self.line([(x-w,y-h),(x+w,y+h)],'#714750',2)
                self.line([(x-w,y+h),(x+w,y-h)],'#714750',2)
            elif kind=='secret':
                self.text((x,y), '密', 18, '#34494c', True)
            elif kind=='one-way':
                self.line([(x-w*.6,y-h*.6),(x+w*.6,y),(x-w*.6,y+h*.6)], color, 2)
        elif kind=='arch':
            # 中央留白後重畫拱形，不保留掃描字形或線條像素。
            def pt(a,b):
                return (x+a,y+b) if axis=='h' else (x+b,y+a)
            self.line([pt(-radius,0),pt(radius,0)], '#eee3c9', 9)
            points=[pt(radius*math.cos(t), -radius*.65*math.sin(t))
                    for t in [i*math.pi/16 for i in range(17)]]
            self.line(points, '#9f753b', 3)
        elif kind in ('up','down'):
            direction = -1 if kind=='up' else 1
            self.polygon([(x-radius,y-direction*radius*.6),
                          (x+radius,y-direction*radius*.6),
                          (x,y+direction*radius)], '#6489a0')
        elif kind=='stairs':
            for i in range(4):
                self.line([(x-radius+i*radius/2,y+radius-i*radius/2),
                           (x+radius,y+radius-i*radius/2)],'#6489a0',3)
        elif kind=='teleport':
            pts=[]
            for i in range(16):
                r=radius if i%2==0 else radius*.4
                pts.append((x+r*math.cos(i*math.pi/8),y+r*math.sin(i*math.pi/8)))
            self.polygon(pts, '#aa79ba')


def render(record, font, output):
    p = Painter(font)
    p.text((40,24), record['title'], 32)
    p.text((40,72), record['source_label'], 18, '#b9c8c8')
    w,h = record['size']
    scale = min(980/w, 710/h)
    ox,oy = 550-w*scale/2, 140+(710-h*scale)/2

    def point(v):
        assert len(v)==2 and all(isinstance(n,(int,float)) and math.isfinite(n) for n in v)
        assert -.5 <= v[0] <= w+.5 and -.5 <= v[1] <= h+.5, (record['id'],v)
        return (round(ox+v[0]*scale,3), round(oy+v[1]*scale,3))

    used={'wall'}
    for poly in record['floor']:
        assert len(poly)>=3
        p.polygon([point(v) for v in poly], '#eee3c9', '#34494c')
    for wall in record.get('walls',[]):
        assert len(wall)>=2
        p.line([point(v) for v in wall])
    for box in record.get('rubble',[]):
        used.add('rubble')
        x0,y0=box[:2];x1,y1=box[2:]
        p.polygon([point((x0+.05,y0)),point((x1-.05,y0+.04)),
                   point((x1,y1-.05)),point((x0+.04,y1))], '#b3a68b', '#827b67')
        for row in range(3):
            for col in range(3):
                x=x0+(col+.25)*(x1-x0)/3;y=y0+(row+.3)*(y1-y0)/3
                p.line([point((x,y)),point((x+.13*(x1-x0),y+.08*(y1-y0)))], '#827b67',2)
    for box in record.get('blocked',[]):
        used.add('blocked')
        a,b=point(box[:2]),point(box[2:])
        p.box((*a,*b), '#7c8e86', '#34494c')
        # 對角線只畫在矩形內，保留完整相鄰開口。
        x0,y0=a; x1,y1=b
        for k in range(-int(y1-y0), int(x1-x0)+1, 14):
            lo=max(0,-k);hi=min(y1-y0,x1-x0-k)
            if lo<hi:
                p.line([(x0+k+lo,y0+lo),(x0+k+hi,y0+hi)], '#c0cbc0', 2)
    for box in record.get('pits',[]):
        used.add('pit')
        x0,y0=box[:2];x1,y1=box[2:]
        points=[]
        corners=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
        for i,a in enumerate(corners):
            b=corners[(i+1)%4]
            for j in range(6):
                t=j/6;dx,dy=b[0]-a[0],b[1]-a[1]
                n=.035 if j%2 else 0
                points.append(point((a[0]+t*dx+n*dy,a[1]+t*dy-n*dx)))
        p.polygon(points, '#aebcc2', '#526c7b')
    for door in record.get('doors',[]):
        kind=door.get('kind','door');assert kind in ('door','arch','secret','one-way','magic','false')
        axis=door.get('axis','h');assert axis in ('h','v')
        used.add(kind)
        p.symbol(kind,point(door['at']),axis,min(14,scale*.23))
    for symbol in record.get('symbols',[]):
        kind=symbol['kind'];assert kind in ('up','down','stairs','teleport')
        used.add(kind)
        p.symbol(kind,point(symbol['at']),radius=min(16,scale*.22))
    for marker in record.get('markers',[]):
        assert isinstance(marker['id'],str) and marker['id']
        at=point(marker['at'])
        background=p.image.getpixel((round(at[0]),round(at[1])))
        ink='#e5cc89' if background==(24,35,41) else '#273d44'
        p.text(at,marker['id'],20,ink,True)
    for label in record.get('labels',[]):
        p.text(point(label['at']),label['text'],18,'#d4c091',True)
    p.line([(40,890),(1060,890)],'#4e6369',2)
    for n,kind in enumerate(k for k in LABELS if k in used):
        x,y = 60+(n%6)*174, 922+(n//6)*40
        if kind=='wall':p.line([(x-12,y),(x+12,y)],'#bdc9c4',4)
        elif kind=='blocked':p.box((x-12,y-10,x+12,y+10),'#7c8e86')
        elif kind=='pit':p.box((x-12,y-10,x+12,y+10),'#aebcc2')
        elif kind=='rubble':p.box((x-12,y-10,x+12,y+10),'#b3a68b')
        else:p.symbol(kind,(x,y))
        p.text((x+22,y-13),LABELS[kind],18)
    p.text((40,1000),'依紙本重繪的閱讀示意圖。圖號對照攻略正文，非遊戲座標。',18,'#b9c8c8')
    output.mkdir()
    p.image.save(output/'map.png')
    p.svg.append('</svg>')
    (output/'map.svg').write_text('\n'.join(p.svg)+'\n')
    return dict(id=record['id'],title=record['title'],marker_count=len(record.get('markers',[])),
                symbols=sorted(used),files={n:sha(output/n) for n in ['map.png','map.svg']})


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('annotations',type=Path)
    a.add_argument('source_root',type=Path)
    a.add_argument('font',type=Path)
    a.add_argument('font_license',type=Path)
    a.add_argument('output',type=Path)
    args=a.parse_args()
    data=json.loads(args.annotations.read_text())
    assert data['status']=='paper-geometry-draft' and data['version']==1
    assert not args.output.exists()
    assert sha(args.font)=='9d5bf4932d31fe94c18cd8cfddc98bc1b14ce10f4e354c682179db290a99c825'
    ids=[r['id'] for r in data['maps']]
    assert len(ids)==len(set(ids)) and all(x.replace('-','').isalnum() and x.isascii() for x in ids)
    for record in data['maps']:
        validate_doors(record)
        rel=Path(record['source']);assert not rel.is_absolute() and '..' not in rel.parts
        source=args.source_root/rel
        assert sha(source)==record['source_sha256']
        # 來源只讀取檔頭尺寸。render() 不接受來源圖像。
        with Image.open(source) as image:
            x0,y0,x1,y1=record['source_bbox']
            assert 0<=x0<x1<=image.width and 0<=y0<y1<=image.height
    args.output.mkdir()
    results=[render(r,args.font,args.output/r['id']) for r in data['maps']]
    (args.output/'FONT-LICENSE.txt').write_bytes(args.font_license.read_bytes())
    receipt=dict(status='paper-redraw-awaiting-review',map_count=len(results),maps=results,
                 annotations_sha256=sha(args.annotations),tool_sha256=sha(Path(__file__)),
                 font_sha256=sha(args.font),scan_pixels_used=False,embedded_raster=False,
                 game_geometry_confirmed=False,runtime_ready=False)
    (args.output/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(maps=len(results),markers=sum(x['marker_count'] for x in results))))


if __name__=='__main__':main()
