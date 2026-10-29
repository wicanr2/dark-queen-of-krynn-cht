"""剪輯實際視窗錄影，使用已授權原譜HD音樂；不製造遊戲畫面。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,log):
    if args[0]=='ffmpeg':
        args=args[:1]+['-filter_threads','1','-filter_complex_threads','1']+args[1:-1]+['-threads','2']+args[-1:]
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    log.write_text(result.stdout)
    result.check_returncode()
def events(p):return {n:float(t) for n,t in (line.split('\t') for line in (p/'events.tsv').read_text().splitlines())}

def main(a):
    assert a.output.is_dir() and not (a.output/'黑暗之后-HD繁中推廣影片.mp4').exists()
    font='/font/jf-openhuninn-2.1.ttf'
    n=events(a.normal)
    clips=[(a.normal,0.2,3,'克萊恩三部曲終章'),(a.normal,n['role'],4,'20像素圓體・繁中角色管理'),
           (a.normal,n['toolbar'],3,'獨立工具列・HD與視窗大小分開'),
           (a.exploration,events(a.exploration)['cave'],8,'HD洞穴探索・場景快照展示'),(a.combat,events(a.combat)['battle'],8,'HD戰鬥畫面・場景快照展示'),
           (a.normal,n['manual'],4,'內建繁中手札與說明'),(a.normal,n['map'],4,'重新繪製的繁中閱讀地圖'),
           (a.normal,n['guide-body'],4,'18章手動攻略・52張重繪圖')]
    generated=[];segments=[];cursor=0
    for i,(source,start,duration,caption) in enumerate(clips):
        text=a.output/f'caption-{i}.txt';text.write_text(caption)
        video=a.output/f'segment-{i}.mp4'
        vf=f'scale=1440:900:flags=lanczos,pad=1920:1080:240:90:color=0x18202c,drawtext=fontfile={font}:textfile={text}:fontcolor=white:fontsize=38:x=(w-text_w)/2:y=1015'
        run(['ffmpeg','-nostdin','-v','warning','-y','-ss',str(start),'-i',str(source/'raw.mp4'),'-t',str(duration),'-vf',vf,'-an','-r','30','-c:v','libx264','-preset','veryfast','-crf','19','-pix_fmt','yuv420p',str(video)],a.output/f'encode-{i}.log')
        generated.append(video);segments.append(dict(start=cursor,end=cursor+duration,caption=caption,source=str(source/'raw.mp4'),source_start=start,state_injection=source!=a.normal));cursor+=duration
    endtext=a.output/'end.txt';endtext.write_text('黑暗之后 HD＋繁體中文\n原版規則・HD美術・原譜音樂\n'+a.version)
    end=a.output/'end.mp4'
    run(['ffmpeg','-nostdin','-v','warning','-y','-f','lavfi','-i','color=c=0x18202c:s=1920x1080:r=30:d=4','-vf',f'drawtext=fontfile={font}:textfile={endtext}:fontcolor=white:fontsize=48:line_spacing=30:x=(w-text_w)/2:y=(h-text_h)/2','-an','-c:v','libx264','-preset','veryfast','-crf','19','-pix_fmt','yuv420p',str(end)],a.output/'encode-end.log')
    generated.append(end);segments.append(dict(start=cursor,end=cursor+4,caption='片尾自有文字',state_injection=False));cursor+=4
    concat=a.output/'concat.txt';concat.write_text(''.join("file '"+str(p)+"'\n" for p in generated))
    destination=a.output/'黑暗之后-HD繁中推廣影片.mp4'
    run(['ffmpeg','-nostdin','-v','warning','-y','-f','concat','-safe','0','-i',str(concat),'-i',str(a.music),'-t',str(cursor),'-af',f'atrim=duration={cursor},afade=t=out:st={cursor-1}:d=1','-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-movflags','+faststart',str(destination)],a.output/'mux.log')
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(destination)]))
    (a.output/'ffprobe.json').write_text(json.dumps(probe,indent=2)+'\n')
    video=next(x for x in probe['streams'] if x['codec_type']=='video');audio=next(x for x in probe['streams'] if x['codec_type']=='audio')
    assert video['codec_name']=='h264' and (video['width'],video['height'])==(1920,1080) and video['r_frame_rate']=='30/1'
    assert audio['codec_name']=='aac' and audio['sample_rate']=='48000' and audio['channels']==2
    assert abs(float(probe['format']['duration'])-cursor)<.2
    run(['ffmpeg','-nostdin','-v','info','-i',str(destination),'-af','volumedetect,astats=metadata=1:reset=0','-vf','blackdetect=d=0.1:pix_th=0.02:pic_th=0.995,freezedetect=n=-60dB:d=2','-f','null','-'],a.output/'quality.log')
    quality=(a.output/'quality.log').read_text()
    assert 'max_volume: -inf' not in quality and 'max_volume: 0.0 dB' not in quality
    assert 'black_start:' not in quality
    for i,segment in enumerate(segments):
        run(['ffmpeg','-nostdin','-v','error','-y','-ss',str((segment['start']+segment['end'])/2),'-i',str(destination),'-frames:v','1',str(a.output/f'contact-{i:02d}.png')],a.output/f'contact-{i:02d}.log')
    result=dict(passed=True,version=a.version,video=destination.name,sha256=sha(destination),bytes=destination.stat().st_size,seconds=cursor,
                segments=segments,source_hashes={str(p/'raw.mp4'):sha(p/'raw.mp4') for p in [a.normal,a.exploration,a.combat]},
                music_sha256=sha(a.music),music_provenance='使用者已授權的原版RODQ1-0樂譜取樣HD；非原版晶片錄音',
                rights='local-only-original-and-derived-assets',public_upload=False,
                freeze_review='原生閱讀停留及片尾字卡可靜止；運動畫面按分幕抽幀目視，不把靜態閱讀誤判程式凍結')
    (a.output/'promo-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['segments','source_hashes']},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['normal','exploration','combat','music','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--version',required=True);main(p.parse_args())
