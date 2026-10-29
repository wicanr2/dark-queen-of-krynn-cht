"""將本作原譜轉為取樣樂器音樂；所有輸出只存本機。"""
import argparse
from array import array
from collections import defaultdict, deque
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import wave

from xmi_score import vlq


# 零起算。依原樂器角色配對，並非 MT-32 波形重現。
INSTRUMENTS = {
    12: (19, '管風琴'), 23: (8, '鋼片琴'),
    24: (62, '合成銅管一'), 25: (63, '合成銅管二'),
    36: (97, '合成音景'), 38: (14, '鐘聲，以管鐘近似'),
    48: (48, '弦樂合奏'), 51: (45, '撥奏弦樂'),
    57: (46, '豎琴一'), 58: (46, '豎琴二'),
    76: (74, '直笛'), 83: (71, '單簧管'), 93: (60, '法國號'),
    107: (77, '尺八'), 112: (47, '定音鼓'),
    114: (118, '低音小鼓，以合成鼓近似'), 117: (116, '太鼓'),
}
SOUNDFONT_SHA = '74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def variable(value):
    assert 0 <= value < 1 << 28
    out = [value & 127]
    while value >> 7:
        value >>= 7
        out.insert(0, (value & 127) | 128)
    return bytes(out)


def export(score):
    assert not score['loop_controls'], '未實作的原譜內部循環'
    events = []
    for i, event in enumerate(score['events']):
        status, tick = event['status'], event['tick']
        command, channel = status >> 4, status & 15
        if status >= 0xf0:
            assert status == 0xff, '未審查的 SysEx'
            continue
        args = list(event['data'])
        if command == 12 and channel != 9:
            args[0] = INSTRUMENTS[args[0]][0]
        if command == 11 and args[0] == 114:
            assert args[1] == 0, '未審查的 MT-32 音色庫'
            continue
        events.append((tick, i*2+1, bytes([status, *args])))
        if command == 9 and args[1]:
            assert event['duration'] > 0, '零長度音符需另外審查'
            events.append((tick+event['duration'], i*2+2, bytes([0x80 | channel, args[0], 0])))
    # XMIDI 的固定 120 Hz 時基：PPQN 60、每四分音符 500000 微秒。
    raw = bytearray(b'\x00\xff\x51\x03\x07\xa1\x20')
    last = 0
    for tick, _, data in sorted(events):
        raw += variable(tick-last)+data
        last = tick
    end = max(score['end_tick'], score['note_end_tick'])+360
    raw += variable(end-last)+b'\xff\x2f\x00'
    return b'MThd'+struct.pack('>IHHH', 6, 0, 1, 60)+b'MTrk'+struct.pack('>I',len(raw))+raw


def read_midi_notes(raw):
    """獨立讀回標準 MIDI，核對實際輸出音符與起訖。"""
    assert raw[:14] == b'MThd'+struct.pack('>IHHH',6,0,1,60)
    assert raw[14:18] == b'MTrk' and struct.unpack_from('>I',raw,18)[0] == len(raw)-22
    pos, tick, tempo, notes = 22, 0, [], []
    active = defaultdict(deque)
    while pos < len(raw):
        delta,pos = vlq(raw,pos)
        tick += delta
        status = raw[pos]
        pos += 1
        if status == 0xff:
            meta = raw[pos]
            count,pos = vlq(raw,pos+1)
            data = raw[pos:pos+count]
            pos += count
            if meta == 0x51:
                tempo.append(data.hex())
            if meta == 0x2f:
                break
            continue
        command, channel = status >> 4, status & 15
        count = 1 if command in (12,13) else 2
        data = raw[pos:pos+count]
        pos += count
        if command == 9 and data[1]:
            active[channel,data[0]].append((tick,data[1]))
        elif command == 8 or command == 9:
            start, velocity = active[channel,data[0]].popleft()
            notes.append([start,tick-start,channel,data[0],velocity])
    assert tempo == ['07a120'] and not any(active.values()) and pos == len(raw)
    return sorted(notes)


def run(*args):
    return subprocess.run(args,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True).stdout


def pcm_check(path):
    with wave.open(str(path),'rb') as audio:
        assert audio.getframerate() == 48000 and audio.getnchannels() == 2 and audio.getsampwidth() == 2
        samples = array('h',audio.readframes(audio.getnframes()))
        frames = audio.getnframes()
    if sys.byteorder != 'little':
        samples.byteswap()
    peak = max(map(abs,samples))
    rms = math.sqrt(sum(x*x for x in samples)/len(samples))
    assert 0 < peak < 32760 and rms > 1, (peak,rms)
    return dict(frames=frames,seconds=frames/48000,peak=peak,clipped_samples=sum(abs(x)>=32767 for x in samples),rms_dbfs=20*math.log10(rms/32768))


def render(batch, output, soundfont):
    assert batch.is_dir() and not output.exists() and sha(soundfont) == SOUNDFONT_SHA
    inventory = json.loads((batch/'inventory.json').read_text())
    tracks = [t for t in inventory['tracks'] if t['file'].startswith('RO')]
    assert len(tracks) == 8
    output.mkdir()
    rows = []
    for track in tracks:
        key = Path(track['score']).stem
        score = json.loads((batch/track['score']).read_text())
        midi = export(score)
        assert read_midi_notes(midi) == sorted(score['notes']), key
        mid, wav, ogg = [output/(key+ext) for ext in ('.mid','.wav','.ogg')]
        mid.write_bytes(midi)
        raw_wav = output/(key+'-raw.wav')
        log = run('fluidsynth','-ni','-F',str(raw_wav),'-T','wav','-r','48000','-g','0.2','-R','1','-C','0',str(soundfont),str(mid))
        (output/(key+'.log')).write_text(log)
        # 合成器另加的靜音尾端不算曲式；只保留原譜結束後三秒釋音。
        frames = (max(score['end_tick'],score['note_end_tick'])+360)*400
        with wave.open(str(raw_wav),'rb') as source:
            assert source.getnframes() >= frames
            params, pcm = source.getparams(), source.readframes(frames)
        with wave.open(str(wav),'wb') as target:
            target.setparams(params)
            target.writeframes(pcm)
        raw_wav.unlink()
        quality = pcm_check(wav)
        run('ffmpeg','-v','error','-nostdin','-i',str(wav),'-c:a','libvorbis','-q:a','6','-ar','48000','-ac','2',str(ogg))
        decoded = output/(key+'-decoded.wav')
        run('ffmpeg','-v','error','-nostdin','-i',str(ogg),'-c:a','pcm_s16le',str(decoded))
        decoded_quality = pcm_check(decoded)
        assert decoded_quality['frames'] == quality['frames']
        decoded.unlink()
        rows.append(dict(key=key,source=track['file'],source_sha256=track['file_sha256'],sequence=track['index'],notes=track['notes'],note_sha256=score['note_sha256'],note_roundtrip=True,score_seconds=score['note_end_tick']/120,midi_sha256=sha(mid),wav_sha256=sha(wav),ogg_sha256=sha(ogg),pcm=quality,decoded=decoded_quality,aliases=[track['file'].replace('RO',prefix)+':'+str(track['index']) for prefix in ('AD','RO','TY','PC')]))
        print(json.dumps(rows[-1]),flush=True)
    result = dict(schema=1,tracks=rows,instruments={str(k):dict(gm=v,role=role) for k,(v,role) in INSTRUMENTS.items()},soundfont_sha256=SOUNDFONT_SHA,codec='Ogg Vorbis',sample_rate=48000,channels=2,clock_hz=120,release_tail_ticks=360,gain=0.2,chorus=False,reverb=True,listening='尚未聽驗',rights='原版樂譜的衍生音樂，僅限本機，不提交或公開',container=os.environ.get('DQK_MEDIA_IMAGE','未提供'),sources={p.name:sha(p) for p in [Path(__file__),Path(__file__).with_name('xmi_score.py')]},tools={name:run(*cmd).splitlines()[0] for name,cmd in {'fluidsynth':['fluidsynth','--version'],'ffmpeg':['ffmpeg','-version']}.items()})
    (output/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    html = '<!doctype html><meta charset="utf-8"><title>黑暗之后原譜音樂試聽</title><h1>原譜取樣樂器試聽</h1><p>保留原版音符、節奏與曲式。音色為角色近似，尚未聽驗。僅限本機。</p>'
    for row in rows:
        html += f'<h2>{row["key"]}</h2><p>{row["notes"]} 個音符，原譜 {row["score_seconds"]:.3f} 秒，另留三秒尾音。</p><audio controls preload="none" src="{row["key"]}.ogg"></audio>'
    (output/'index.html').write_text(html+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--soundfont',type=Path,default=Path('/usr/share/sounds/sf2/FluidR3_GM.sf2'))
    args = parser.parse_args()
    render(args.batch,args.output,args.soundfont)
