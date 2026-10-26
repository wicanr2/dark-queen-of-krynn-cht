"""本機 HLIB/TILE 圖鑑。格式與解交錯方法參照 Gold Box Explorer，保留 MIT 聲明。

來源固定 eac30abaa6ee66aea6f5d65ebe6d676b10015a8f 的 Plugins/Tbl/FruaTlbFile.cs。
原版像素與圖鑑只寫 workplace，不提供為公開素材；來源 ID 尚不等同人物／怪物身分。
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

from PIL import Image,ImageDraw

SOURCE='https://github.com/bsimser/Gold-Box-Explorer/blob/eac30abaa6ee66aea6f5d65ebe6d676b10015a8f/src/Common/Plugins/Tbl/FruaTlbFile.cs'
EGA=((0,0,0),(0,0,170),(0,170,0),(0,170,170),(170,0,0),(170,0,170),(170,85,0),(170,170,170),
     (85,85,85),(85,85,255),(85,255,85),(85,255,255),(255,85,85),(255,85,255),(255,255,85),(255,255,255))


def sha(data):return hashlib.sha256(data).hexdigest()


def image_blocks(data):
    assert len(data)>=20 and data[:4]==b'HLIB'
    length,count=struct.unpack_from('<IH',data,4);assert length==len(data) and 1<=count<=4096
    first=struct.unpack_from('<I',data,16)[0]
    assert first in (16+count*4,16+(count+1)*4)
    pointers=(first-16)//4
    assert 16+pointers*4<=length
    offsets=list(struct.unpack_from('<'+'I'*pointers,data,16))
    assert offsets[0]==16+pointers*4
    if pointers==count+1:assert offsets[-1]==length
    else:offsets.append(length)
    assert all(a<b for a,b in zip(offsets,offsets[1:]))
    return list(zip(offsets,offsets[1:]))


def directory(data):
    count=struct.unpack_from('<H',data)[0]
    assert len(data)==2+4*count
    pairs=[struct.unpack_from('<HH',data,2+4*i) for i in range(count)]
    # CPIC 原版含重複 ID，指向不同圖格；逐筆保留，不能拿 ID 當唯一身分。
    return pairs


def deinterlace(data):
    assert len(data)%4==0
    result=bytearray(len(data));quarter=len(data)//4
    for plane in range(4):result[plane::4]=data[plane*quarter:(plane+1)*quarter]
    return result


def dac_color(color):return tuple((c>>2)*4+(c>>6) for c in color)


def external_palette(path,palette):
    data=path.read_bytes();base=0
    if data[12:16]==b'HLIB':
        start,end=image_blocks(data)[1];base=start;data=data[start:end]
    start,end=image_blocks(data)[1 if data[11] else 0]
    _,first,count,_,_=struct.unpack_from('<HHHBB',data,start)
    assert first+count<=256 and start+8+count*3<=end
    for i in range(count):palette[first+i]=tuple(data[start+8+i*3:start+11+i*3])
    return dict(path=str(path),sha256=sha(path.read_bytes()),offset=base+start,first=first,count=count)


def pixels(data,width,height,method):
    size=width*height
    if method in (16,21):
        assert len(data)>=size
        return deinterlace(data[:size]),size
    if method==17:
        assert len(data)>=size*2
        mask=deinterlace(data[:size]);result=deinterlace(data[size:size*2])
        for i,value in enumerate(mask):
            if value==255:result[i]=255
        return result,size*2
    if method==18:
        stream=bytearray();pos=0
        while len(stream)<size:
            assert pos<len(data);op=data[pos];pos+=1
            if op<128:
                count=op+1;assert pos+count<=len(data);stream.extend(data[pos:pos+count]);pos+=count
            else:
                count=257-op;assert pos<len(data);stream.extend(bytes([data[pos]])*count);pos+=1
            assert len(stream)<=size
        result=bytearray(size);quarter=width//4
        for y in range(height):
            for plane in range(4):result[y*width+plane:(y+1)*width:4]=stream[y*width+plane*quarter:y*width+(plane+1)*quarter]
        return result,pos
    if method==23:
        raw,used,_=packet_pixels(data,width,height)
        return raw,used
    raise ValueError('未支援的繪圖方法 '+str(method))


def packet_pixels(data,width,height):
    """sub_26D6A／sub_11B26 已證實的逐平面、逐列 signed RLE。"""
    assert width%4==0 and width>0 and height>0
    raw,alpha=bytearray([255])*(width*height),bytearray(width*height)
    pos=0;quarter=width//4
    for plane in range(4):
        for y in range(height):
            x=0
            while True:
                if pos>=len(data):raise ValueError('method23 缺少列終止')
                op=data[pos];pos+=1
                if op==0:break
                count=op if op<128 else 256-op
                if x+count>quarter:raise ValueError('method23 封包超出原列')
                if op<128:
                    if pos+count>len(data):raise ValueError('method23 常值不足')
                    for i in range(count):
                        at=y*width+(x+i)*4+plane
                        raw[at]=data[pos+i];alpha[at]=255
                    pos+=count
                x+=count
    return raw,pos,alpha


def extract_bank(data,base,context,palette,records,output,source_name):
    blocks=image_blocks(data);kind=data[12:16];has_table=data[11]
    assert has_table in (0,1)
    if kind==b'HLIB':
        assert has_table==1
        ids=directory(data[slice(*blocks[0])]);mapping={}
        for key,index in ids:
            assert 1<=index<len(blocks);mapping.setdefault(index,[]).append(key)
        for i,(start,end) in enumerate(blocks[1:],1):
            extract_bank(data[start:end],base+start,context+[(i,mapping.get(i,[]))],palette,records,output,source_name)
        return
    assert kind==b'TILE'
    ids=directory(data[slice(*blocks[0])]) if has_table else []
    palette_index=1 if has_table else 0;start,end=blocks[palette_index]
    assert end-start>=8
    cycling,first,count,ranges,magic=struct.unpack_from('<HHHBB',data,start)
    assert first+count<=256 and start+8+3*count<=end
    for i in range(count):palette[first+i]=tuple(data[start+8+3*i:start+11+3*i])
    mapping={}
    for key,index in ids:
        assert palette_index<index<len(blocks);mapping.setdefault(index,[]).append(key)
    bank_records=[]
    for i,(start,end) in enumerate(blocks[palette_index+1:],palette_index+1):
        assert end-start>=8
        height,dy,dx,quarter,method=struct.unpack_from('<HhhBB',data,start);width=quarter*4
        key=source_name+'.'+'.'.join(str(x[0]) for x in context)+'.'+str(i)
        record=dict(key=key,source=source_name,offset=base+start,bytes=end-start,sha256=sha(data[start:end]),
            context=context,block=i,ids=mapping.get(i,[]),width=width,height=height,x=dx,y=dy,method=method,
            palette_range=[first,count],palette_cycling=cycling,palette_cycles=ranges,header_magic=magic)
        records.append(record);bank_records.append(record)
        if width==0 and method==24:
            resource=struct.unpack_from('<HHHBB',data,start)
            assert resource[1]+resource[2]<=256 and 8+3*resource[2]<=end-start
            record.update(palette_only=True,palette_resource_header=list(resource),
                          classification='強推論：色盤資料形狀；切換時機未知')
            continue
        assert 0<width<=640 and 0<height<=400
        if method==25:
            parts=[];at=0;total=1
            while len(parts)<total:
                if start+8+at+6>end:raise ValueError('組圖子記錄不足')
                child,total,py,px=struct.unpack_from('<BBhh',data,start+8+at)
                parts.append(dict(block=child,dy=py,dx=px,total=total));at+=6
            record.update(composite_parts=parts,consumed_bytes=at)
            continue
        opacity=None
        try:
            if method==23:raw,used,opacity=packet_pixels(data[start+8:end],width,height)
            else:raw,used=pixels(data[start+8:end],width,height,method)
        except ValueError as error:record['unsupported']=str(error);continue
        assert len(raw)==width*height and used<=end-start-8
        rgba=bytearray()
        for index,value in enumerate(raw):
            if opacity is not None and opacity[index]==0:rgba.extend((0,0,0,0));continue
            if method in (17,21) and value==255:rgba.extend((0,0,0,0));continue
            color=palette[value];assert color is not None,('缺少色盤',key,value)
            rgba.extend((*dac_color(color),255))
        image=Image.frombytes('RGBA',(width,height),bytes(rgba));name=key+'.png';image.save(output/name)
        (output/(key+'.idx')).write_bytes(raw)
        record.update(image=name,image_sha256=sha((output/name).read_bytes()),indexed_sha256=sha(raw),consumed_bytes=used,
            palette=[list(dac_color(c)) if c is not None else None for c in palette])
    compose_bank_records(bank_records,output)


def compose_bank_records(records,output):
    """sub_2744C 的逐筆遞迴參照；只重建離線圖，不增加執行期繪製。"""
    by_block={r['block']:r for r in records}
    def resolve(record,active):
        if 'image' in record:return
        if 'composite_parts' not in record:raise ValueError('組圖參照非圖片或未知來源')
        if record['block'] in active:raise ValueError('組圖循環參照')
        active=active|{record['block']}
        w,h=record['width'],record['height']
        result=Image.new('RGBA',(w,h));raw=bytearray([255])*(w*h);children=[]
        for part in record['composite_parts']:
            child=by_block.get(part['block'])
            if child is None:raise ValueError('組圖子索引不存在')
            resolve(child,active)
            logical_x=part['dx']-child['x']
            # sub_2416C 的CA41=15分支以x>>2定址；離線原點採四像素對齊。
            x,y=logical_x//4*4,part['dy']-child['y']
            if x<0 or y<0 or x+child['width']>w or y+child['height']>h:
                raise ValueError('組圖子圖超出宣告邊界')
            image=Image.open(output/child['image']).convert('RGBA')
            indexes=(output/Path(child['image']).with_suffix('.idx')).read_bytes()
            assert len(indexes)==image.width*image.height
            for yy in range(image.height):
                for xx in range(image.width):
                    color=image.getpixel((xx,yy))
                    if color[3]:
                        raw[(y+yy)*w+x+xx]=indexes[yy*image.width+xx]
                        result.putpixel((x+xx,y+yy),color)
            children.append(dict(key=child['key'],sha256=child['sha256'],x=x,y=y,logical_x=logical_x))
        name=record['key']+'.png';result.save(output/name)
        (output/Path(name).with_suffix('.idx')).write_bytes(raw)
        record.update(image=name,image_sha256=sha((output/name).read_bytes()),indexed_sha256=sha(raw),
                      composite_children=children,mode_x_origin_phase=0,
                      render_policy='原版遞迴分派既有子圖；不再繪製整張組圖')
    for record in records:
        if 'composite_parts' in record:
            try:resolve(record,set())
            except ValueError as error:record['unsupported']=str(error)


def run(original,output):
    assert output.is_dir() and not (output/'tlb-index.json').exists()
    records=[];inputs=[];base_palette=[None]*256;base_palette[:16]=EGA
    palettes=[]
    for name in ('WILDCOM.TLB','CBODY.TLB'):
        paths=list(original.rglob(name));assert len(paths)==1
        palettes.append(external_palette(paths[0],base_palette))
    for name in ('CPIC.TLB','CBODY.TLB','PICA.TLB','PICB.TLB','PICC.TLB'):
        paths=list(original.rglob(name));assert len(paths)==1
        path=paths[0];data=path.read_bytes();inputs.append(dict(path=str(path.relative_to(original)),sha256=sha(data),bytes=len(data)))
        palette=list(base_palette)
        extract_bank(data,0,[],palette,records,output,name[:-4])
    summary={}
    for name in ('CPIC','CBODY','PICA','PICB','PICC'):
        chosen=[r for r in records if r['source']==name and 'image' in r]
        size=144 if name in ('CPIC','CBODY') else 192;cols=8 if size==144 else 6
        panel=Image.new('RGB',(cols*size,((len(chosen)+cols-1)//cols)*size),'#23232c');draw=ImageDraw.Draw(panel)
        for i,r in enumerate(chosen):
            image=Image.open(output/r['image']);scale=max(1,min((size-16)//image.width,(size-32)//image.height));image=image.resize((image.width*scale,image.height*scale),Image.Resampling.NEAREST)
            x=(i%cols)*size;y=(i//cols)*size;panel.paste(image,(x+(size-image.width)//2,y+16),image)
            draw.text((x+4,y+size-14),r['key']+' '+','.join(map(str,r['ids'])),fill='white')
        panel.save(output/(name+'-original.png'));summary[name]=dict(images=len(chosen),methods=dict(Counter(r['method'] for r in chosen)),atlas=name+'-original.png')
    result=dict(format_reference=SOURCE,rights='本機原版圖像；不加入 Git 或公開交付',identity_status='來源編號及靜態圖格，尚未全量核對人物／怪物身分；無 HD 資產',
        palette_status='WILDCOM／CBODY 共用色盤與各圖庫色盤，轉六位元 DAC；尚未全量對拍',external_palettes=palettes,
        id_policy='重複 ID 及多個 ID 指同一圖格均保留，不由 ID 單獨推斷身分',inputs=inputs,summary=summary,records=records)
    (output/'tlb-index.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
