"""唯讀擷取本作XMI樂譜；不將原版音符或衍生音樂加入Git。"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def chunks(raw, start=0, end=None):
    end = len(raw) if end is None else end
    pos = start
    while pos < end:
        if pos+8 > end:
            raise ValueError('截斷IFF標頭')
        kind, size = raw[pos:pos+4], struct.unpack_from('>I', raw, pos+4)[0]
        lo, hi = pos+8, pos+8+size
        if hi > end:
            raise ValueError('IFF區塊越界')
        yield kind, lo, hi
        pos = hi+(size & 1)
    if pos != end:
        raise ValueError('IFF對齊越界')


def vlq(data, pos):
    value = 0
    for _ in range(4):
        if pos >= len(data):
            raise ValueError('截斷VLQ')
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 127)
        if byte < 128:
            return value, pos
    raise ValueError('VLQ過長')


def parse_events(data, base):
    pos, tick, ended = 0, 0, False
    events, notes, loops = [], [], []
    while pos < len(data):
        start = pos
        while pos < len(data) and data[pos] < 128:
            tick += data[pos]
            pos += 1
        if pos == len(data):
            raise ValueError('缺少XMI事件')
        status = data[pos]
        pos += 1
        event = dict(tick=tick, status=status, source_offset=base+start)
        command = status >> 4
        if 8 <= command <= 14:
            size = 1 if command in (12, 13) else 2
            args = list(data[pos:pos+size])
            if len(args) != size or any(x > 127 for x in args):
                raise ValueError('無效MIDI資料')
            pos += size
            event['data'] = args
            if command == 9:
                duration, pos = vlq(data, pos)
                event['duration'] = duration
                if args[1]:
                    notes.append([tick, duration, status & 15, args[0], args[1]])
            elif command == 11 and args[0] in (116, 117):
                loops.append([tick, status & 15, *args])
        elif status in (0xf0, 0xf7, 0xff):
            if status == 0xff:
                if pos == len(data):
                    raise ValueError('截斷Meta事件')
                event['meta'] = data[pos]
                pos += 1
            size, pos = vlq(data, pos)
            if pos+size > len(data):
                raise ValueError('Meta／SysEx越界')
            event['hex'] = data[pos:pos+size].hex()
            pos += size
            if event.get('meta') == 0x2f:
                if size or any(data[pos:]):
                    raise ValueError('無效結束事件')
                ended = True
        else:
            raise ValueError(f'未支援事件{status:02x}')
        events.append(event)
        if ended:
            break
    if not ended:
        raise ValueError('缺少結束事件')
    return dict(events=events, notes=notes, loop_controls=loops, end_tick=tick,
                note_end_tick=max([t+d for t,d,*_ in notes], default=0),
                note_sha256=sha(json.dumps(notes,separators=(',',':')).encode()))


def parse_xmi(raw):
    outer = list(chunks(raw))
    if len(outer) != 2 or outer[0][0] != b'FORM' or outer[1][0] != b'CAT ':
        raise ValueError('非本作XDIR／CAT格式')
    _, lo, hi = outer[0]
    if raw[lo:lo+4] != b'XDIR':
        raise ValueError('缺少XDIR')
    info = [(a,b) for k,a,b in chunks(raw,lo+4,hi) if k == b'INFO']
    if len(info) != 1 or info[0][1]-info[0][0] != 2:
        raise ValueError('無效序列數')
    count = struct.unpack_from('<H',raw,info[0][0])[0]
    _, lo, hi = outer[1]
    if raw[lo:lo+4] != b'XMID':
        raise ValueError('缺少CAT XMID')
    tracks = []
    for kind, start, end in chunks(raw,lo+4,hi):
        if kind != b'FORM' or raw[start:start+4] != b'XMID':
            raise ValueError('無效序列容器')
        timbres, event = None, None
        for k,a,b in chunks(raw,start+4,end):
            if k == b'TIMB':
                n = struct.unpack_from('<H',raw,a)[0]
                if b-a != 2+2*n:
                    raise ValueError('音色表尺寸不符')
                timbres = [list(raw[p:p+2]) for p in range(a+2,b,2)]
            elif k == b'EVNT':
                if event is not None:
                    raise ValueError('重複EVNT')
                event = (a,b)
            else:
                raise ValueError(f'未支援區塊{k!r}')
        if event is None or timbres is None:
            raise ValueError('缺少音色或事件區塊')
        a,b = event
        track = parse_events(raw[a:b], a)
        track.update(index=len(tracks), offset=a, bytes=b-a, timbres=timbres, evnt_sha256=sha(raw[a:b]))
        tracks.append(track)
    if len(tracks) != count:
        raise ValueError('宣告序列數與實際不符')
    return tracks


def inventory(original, output):
    assert original.is_dir() and output.is_dir() and not (output/'inventory.json').exists()
    rows = []
    for path in sorted(original.glob('*DQ?.XMI')):
        raw = path.read_bytes()
        tracks = parse_xmi(raw)
        for track in tracks:
            name = f'{path.stem}-{track["index"]}.json'
            (output/name).write_text(json.dumps(track,ensure_ascii=False,indent=2)+'\n')
            row = {k:v for k,v in track.items() if k not in ('events','notes')}
            row.update(file=path.name, file_sha256=sha(raw), file_bytes=len(raw), score=name,
                       notes=len(track['notes']), events=len(track['events']),
                       programs=sorted({tuple(e['data']) for e in track['events'] if e['status'] >> 4 == 12}),
                       banks=sorted({tuple(e['data']) for e in track['events'] if e['status'] >> 4 == 11 and e['data'][0] == 114}))
            rows.append(row)
    assert len(rows) == 32 and len({r['file'] for r in rows}) == 12
    result = dict(version=1, tracks=rows, source_files=12, sequences_per_hardware=8,
                  clock='XMI 120 ticks/second；依成熟XMIDI契約，不用SMF的原始tempo meta改寫此時基',
                  source_only=True)
    (output/'inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'files':12,'sequences':32,'per_hardware':8,
                      'roland':[{k:r[k] for k in ('file','index','notes','end_tick','note_end_tick','programs','banks','loop_controls')} for r in rows if r['file'].startswith('RO')]},ensure_ascii=False))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    inventory(args.original,args.output)
