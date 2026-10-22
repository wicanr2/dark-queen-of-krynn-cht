"""由重繪來源獨立模擬圖文取景及像素，不讀取 Go 計算結果。"""
from fractions import Fraction
from functools import lru_cache
import hashlib
import json
from PIL import Image

IMAGE_KEYS = {"ZoomIn","ZoomOut","PanLeft","PanRight","PanUp","PanDown","Home"}


def illustrations(inputs):
    path=inputs/"illustrations.json"
    if not path.exists(): return {}
    data=json.loads(path.read_text())
    assert set(data)=={"draft","entries"} and data["draft"] is True
    result={}
    for item in data["entries"]:
        assert set(item)=={"entry","file","sha256","crop"} and item["entry"] not in result
        path=inputs/item["file"]
        assert path.parent==inputs and hashlib.sha256(path.read_bytes()).hexdigest()==item["sha256"]
        with Image.open(path) as source:
            x,y,right,bottom=item["crop"]
            assert 0<=x<right<=source.width and 0<=y<bottom<=source.height
            image=source.crop(item["crop"]).convert("RGBA")
        assert image.getextrema()[3]==(255,255)
        result[item["entry"]]={"width":image.width,"height":image.height,"pixels":image.tobytes()}
    assert set(result)=={12,25,64}
    return result


def geometry(item, view):
    assert set(view)=={"zoom","x","y"} and view["zoom"] in (0,1,2)
    width,height=item["width"],item["height"]
    scale=min(Fraction(608,width),Fraction(208,height)) if view["zoom"]==0 else Fraction(view["zoom"])
    dx,dy=max(0,(608-int(width*scale))//2),max(0,(208-int(height*scale))//2)
    visible_width=-(-Fraction(608)/scale//1)
    visible_height=-(-Fraction(208)/scale//1)
    return scale,dx,dy,int(visible_width),int(visible_height)


def move(item, previous, key):
    assert key in IMAGE_KEYS
    view=dict(previous)
    if key=="Home": return {"zoom":0,"x":0,"y":0}
    scale,_,_,vw,vh=geometry(item,view)
    if key in ("ZoomIn","ZoomOut"):
        cx=view["x"]+min(item["width"],vw)//2
        cy=view["y"]+min(item["height"],vh)//2
        view["zoom"]=min(2,view["zoom"]+1) if key=="ZoomIn" else max(0,view["zoom"]-1)
        _,_,_,vw,vh=geometry(item,view)
        view["x"],view["y"]=cx-vw//2,cy-vh//2
    elif view["zoom"]:
        axis,change={"PanLeft":("x",-64),"PanRight":("x",64),"PanUp":("y",-64),"PanDown":("y",64)}[key]
        view[axis]+=change
    view["x"]=min(max(view["x"],0),max(0,item["width"]-vw))
    view["y"]=min(max(view["y"],0),max(0,item["height"]-vh))
    return view


def paint(px,page,images):
    if not page.get("Image"): return
    item=images[page["Entry"]]; view=page["Image"]
    scale,dx,dy,vw,vh=geometry(item,view)
    assert 0<=view["x"]<=max(0,item["width"]-vw) and 0<=view["y"]<=max(0,item["height"]-vh)
    width,height=item["width"],item["height"]
    # 來源行與欄的離散索引分開計算，核對實際 GPU 畫格的每個像素。
    xs=[view["x"]+int(Fraction(x-dx)/scale) for x in range(dx,min(608,dx+int(width*scale)))]
    ys=[view["y"]+int(Fraction(y-dy)/scale) for y in range(dy,min(208,dy+int(height*scale)))]
    assert not xs or (min(xs)>=0 and max(xs)<width)
    assert not ys or (min(ys)>=0 and max(ys)<height)
    raw=item["pixels"]
    for row,sy in enumerate(ys):
        values=b"".join(raw[(sy*width+x)*4:(sy*width+x+1)*4] for x in xs)
        dest=((32+dy+row)*640+16+dx)*4
        px[dest:dest+len(values)]=values
