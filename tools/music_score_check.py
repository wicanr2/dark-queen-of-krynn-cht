"""核對實際SMF控制事件、音符與本機音訊雜湊，不重新合成。"""
import hashlib
import json
from pathlib import Path
import struct
import sys

from music_score_render import INSTRUMENTS, read_midi_notes
from xmi_score import vlq

batch, output = map(Path,sys.argv[1:])
manifest=json.loads((output/'manifest.json').read_text())
rows=[]
for track in manifest['tracks']:
    score=json.loads((batch/(track['key']+'.json')).read_text())
    raw=(output/(track['key']+'.mid')).read_bytes()
    assert sorted(score['notes'])==read_midi_notes(raw)
    assert raw[:4]==b'MThd' and struct.unpack_from('>I',raw,18)[0]==len(raw)-22
    pos,tick,controls=22,0,[]
    while pos<len(raw):
        delta,pos=vlq(raw,pos);tick+=delta
        status=raw[pos];pos+=1
        if status==0xff:
            meta=raw[pos];count,pos=vlq(raw,pos+1);pos+=count
            if meta==0x2f:break
            continue
        command=status>>4
        size=1 if command in (12,13) else 2
        data=list(raw[pos:pos+size]);pos+=size
        if command not in (8,9):controls.append([tick,status,data])
    expected=[]
    for event in score['events']:
        status=event['status'];command=status>>4
        if status>=0xf0 or command in (8,9):continue
        data=list(event['data'])
        if command==11 and data[0]==114:
            assert data[1]==0
            continue
        if command==12 and status&15!=9:data[0]=INSTRUMENTS[data[0]][0]
        expected.append([event['tick'],status,data])
    assert controls==expected
    assert tick==max(score['end_tick'],score['note_end_tick'])+360
    for extension,key in [('mid','midi_sha256'),('wav','wav_sha256'),('ogg','ogg_sha256')]:
        assert hashlib.sha256((output/(track['key']+'.'+extension)).read_bytes()).hexdigest()==track[key]
    assert track['decoded']['frames']==(score['note_end_tick']+360)*400
    assert track['decoded']['clipped_samples']==0 and 0<track['decoded']['peak']<32760
    rows.append(dict(key=track['key'],notes=len(score['notes']),control_events=len(controls),passed=True))
assert len(rows)==8 and sum(t['notes'] for t in rows)==4191
result=dict(passed=True,tracks=rows,total_notes=4191,source_hashes_verified=True,controls_roundtrip=True,note_timing_roundtrip=True,listening_verified=False,manifest_sha256=hashlib.sha256((output/'manifest.json').read_bytes()).hexdigest())
(output/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
