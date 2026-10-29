"""從正式遊戲新錄影剪輯故事與玩法篇；字幕及分鏡由自有TSV提供。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while data:=f.read(1024*1024):h.update(data)
    return h.hexdigest()


def read(path):return json.loads(path.read_text())


def stamp(seconds):
    ms=round(seconds*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def prepare(a):
    from PIL import ImageFont
    assert a.output.is_dir() and not (a.output/'story-plan.json').exists()
    assert re.fullmatch(r'v\.\d+\.\d+\.\d+-\d{8}',a.version)
    formal=a.player or a.root/'workplace/probe/player-current'
    acceptance=a.acceptance or a.root/'workplace/probe/completion-20261029/render-two-rounds-checks.json'
    accepted=read(acceptance)
    assert accepted['passed'] and sha(formal/'dqk-player')==accepted['binary_sha256']
    sources={k:getattr(a,k) for k in ['normal','exploration','combat']}
    inputs={k:read(p/'capture-inputs.json') for k,p in sources.items()}
    for k,metadata in inputs.items():
        if metadata.get('full_screen_capture'):
            geometry=read(sources[k]/'window-rect.json')
            x,y,w,h=geometry['rect']
            assert w==960 and h==600 and x>=0 and y>=0 and x+w<=1280 and y+h<=900
            metadata['window_rect']=geometry['rect']
            metadata['window_rect_evidence_sha256']=sha(sources[k]/'window-rect.json')
    filmed_names=[p.name for p in (sources['exploration']/'code').glob('*.go') if not p.name.startswith('zz_')]
    assert filmed_names
    frozen={n:read(formal/'build-info.json')['sources'][n] for n in filmed_names}
    for k,metadata in inputs.items():
        assert metadata['edition']=='story' and metadata['mode']==k
        assert metadata['binary_sha256']==accepted['binary_sha256']
        assert metadata['profile_sha256']==accepted['profile_sha256']
        assert metadata['hd_sha256']==accepted['hd_sha256']
        assert 'panic:' not in (sources[k]/'player.log').read_text()
        metadata['state_injection']=k!='normal'
        metadata['execution_binary_sha256']=sha(sources[k]/'scene-player') if k!='normal' else metadata['binary_sha256']
        if k!='normal':
            assert all(sha(sources[k]/'code'/n)==h for n,h in frozen.items())
            metadata['production_go_sources_verified']=True
    events={k:{name:float(at) for name,at in (line.split('\t') for line in (p/'events.tsv').read_text().splitlines())} for k,p in sources.items()}
    switches=read(sources['exploration']/'session/controls.json')
    assert [x['hd'] for x in switches if x['action']=='hd']==[False,True], 'HD對照需兩次實際切換成功'
    normal=read(sources['normal']/'session/ui-diagnostics.json')
    maps=[x for x in normal['reader_events'] if x.get('action') in ('map-window-open','map-window-close')]
    assert [x['action'] for x in maps]==['map-window-open','map-window-close']*2, '手冊與攻略地圖均需實際開啟及關閉'
    assert [x['source'] for x in maps if x['action']=='map-window-open']==['manual.adventurer.page2','guide.map.flame-0']
    assert all(maps[i]['step']==maps[i+1]['step'] for i in (0,2))
    guide=normal['guide_events'] or []
    assert any(x['page'] and x['page']['Mode']=='guide-body' and x['book']=='chapter-17' for x in guide)
    assert any(x['page'] and x['page']['SourceKey']=='guide.map.flame-0' for x in guide)
    text_dir=a.output/'text';text_dir.mkdir()
    metrics=[]
    def text(key,value,size,rect,where):
        assert '\n' not in value and value and not any(ord(c)<32 for c in value)
        font=ImageFont.truetype(str(a.font),size)
        box=font.getbbox(value)
        width,height=box[2]-box[0],box[3]-box[1]
        assert width<=rect[2] and height<=rect[3],(key,value,width,height,rect)
        x,y=rect[:2]
        assert x>=0 and y>=0 and x+rect[2]<=1920 and y+rect[3]<=1080
        path=text_dir/(key+'.txt');path.write_text(value)
        metrics.append(dict(key=key,text=value,font_pixels=size,bbox=box,safe_rect=rect,placement=where))
        return str(path)
    catalog=a.root/'text/promo-story.zh-TW.tsv'
    rows=list(csv.DictReader(catalog.open(),delimiter='\t',quoting=csv.QUOTE_NONE))
    assert len(rows)==len({r['key'] for r in rows})==12
    segments=[];cursor=0;srt=[]
    for i,row in enumerate(rows):
        key=row['key'];duration=int(row['duration']);family,event=row['source'].split(':')
        segment=dict(key=key,section=row['section'],title=row['title'],lines=[row['line1'],row['line2']],start=cursor,end=cursor+duration,duration=duration,source_id=row['source'])
        side=key in ('story-call','combat')
        segment['layout']='cover' if key=='opening' else 'map-and-story' if key=='story-call' else 'tactical-closeup' if key=='combat' else 'split-comparison' if key.startswith('art-') else 'ending-card' if key=='ending' else 'gameplay'
        segment['text']={
            'section':text(key+'-section',row['section'],27,[64,40,260,40],'left'),
            'title':text(key+'-title',row['title'],44,[1040,270,824,60] if side else [290,30,1330,60],'left' if side else 'center'),
            'line1':text(key+'-line1',row['line1'],32 if side else 38,[1040,430,824,50] if side else [120,928,1680,50],'left' if side else 'center'),
            'line2':text(key+'-line2',row['line2'],32 if side else 38,[1040,500,824,50] if side else [120,982,1680,50],'left' if side else 'center'),
        }
        if family=='cover':
            cover=formal/'hd/references/title-final-20261026/TITLE-cover-r1.png'
            assert cover.is_file()
            segment.update(source=str(cover),source_sha256=sha(cover),state_injection=False)
        elif family!='card':
            segment['source']=str(sources[family]/'raw.mp4')
            # spell是剪輯點，並非遊戲事件：取實際戰鬥錄影第14秒。
            segment['source_start']=events[family].get(event,14.0 if event=='spell' else -1)
            assert segment['source_start']>=0
            segment['state_injection']=family!='normal'
            segment['full_screen_capture']=inputs[family].get('full_screen_capture',False)
            segment['window_rect']=inputs[family].get('window_rect')
            segment['full_screen_map']=event in ('map','guide-map')
            badge='正常操作錄影' if family=='normal' else '場景快照續行'
            if key=='art-original':badge+='｜原版美術'
            if key=='art-hd':badge+='｜HD美術'
            if key=='combat':badge+='｜戰鬥局部'
            segment['text']['badge']=text(key+'-badge',badge,24,[1450,44,410,38],'right')
            if key.startswith('art-'):
                segment['comparison_starts']=[events['exploration']['cave-native'],events['exploration']['cave-hd']]
                for label,value in [('native','原版美術'),('hd','HD美術')]:
                    segment['text'][label]=text(key+'-'+label,value,32,[64 if label=='native' else 992,160,864,50],'center')
        else:
            segment['state_injection']=False
        if key in ['opening','ending']:
            segment['card_text']={
                'title':text(key+'-large',row['title'],72 if key=='opening' else 60,[100,770 if key=='opening' else 340,1720,100],'center'),
                'line1':text(key+'-middle',row['line1'],42,[100,875 if key=='opening' else 470,1720,70],'center'),
                'line2':text(key+'-bottom',row['line2'],38,[100,940 if key=='opening' else 555,1720,70],'center'),
                'version':text(key+'-version',a.version,28,[100,1010 if key=='opening' else 665,1720,50],'center'),
            }
        srt.append(f'{i+1}\n{stamp(cursor)} --> {stamp(cursor+duration)}\n{row["title"]}\n{row["line1"]}\n{row["line2"]}\n')
        segments.append(segment);cursor+=duration
    assert cursor==86
    (a.output/'故事與玩法字幕.srt').write_text('\n'.join(srt),encoding='utf-8-sig')
    (a.output/'subtitle-layout.json').write_text(json.dumps(dict(passed=True,font_sha256=sha(a.font),canvas=[1920,1080],game_rect=[320,104,1280,800],metrics=metrics),ensure_ascii=False,indent=2)+'\n')
    music=formal/'music'
    hashes={str(p/'raw.mp4'):sha(p/'raw.mp4') for p in sources.values()}
    hashes.update({s['source']:s['source_sha256'] for s in segments if s['source_id'].startswith('cover:')})
    plan=dict(schema=1,version=a.version,seconds=cursor,font='/font/'+a.font.name,segments=segments,source_inputs=inputs,source_hashes=hashes,music=[str(music/'RODQ1-0.ogg'),str(music/'RODQ3-0.ogg')],music_hashes={n:sha(music/n) for n in ['RODQ1-0.ogg','RODQ3-0.ogg']},render_acceptance_sha256=sha(acceptance),catalog_sha256=sha(catalog),story_source=dict(path='README.md',sha256=sha(a.root/'README.md'),sections=['故事背景','遊戲機制','中文介面與工具列','遊戲內地圖與攻略重繪']),rights='local-only-original-and-derived-assets',public_upload=False)
    (a.output/'story-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(prepared=True,segments=len(segments),seconds=cursor,text_fields=len(metrics)),ensure_ascii=False))


def run(args,log):
    if args[0]=='ffmpeg':args=args[:1]+['-filter_threads','1','-filter_complex_threads','1']+args[1:-1]+['-threads','2']+args[-1:]
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    log.write_text(result.stdout);result.check_returncode()


def overlay(font,path,size,x,y,color='white'):
    return f'drawtext=fontfile={font}:textfile={path}:fontcolor={color}:fontsize={size}:x={x}:y={y}:fix_bounds=0'


def render(a):
    plan=read(a.output/'story-plan.json');font=plan['font'];generated=[]
    name='黑暗之后-HD繁中推廣影片-故事與玩法篇.mp4'
    destination=a.output/name;assert not destination.exists()
    assert all(sha(Path(p))==h for p,h in plan['source_hashes'].items())
    for i,s in enumerate(plan['segments']):
        video=a.output/f'segment-{i:02}.mp4'
        complex_prefix=None
        if s['key']=='ending':
            inputs=['-f','lavfi','-i',f'color=c=0x211710:s=1920x1080:r=30:d={s["duration"]}']
            vf='null'
        elif s['key']=='opening':
            inputs=['-loop','1','-i',s['source']]
            vf='scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x211710,drawbox=x=0:y=752:w=1920:h=328:color=black@0.72:t=fill'
        else:
            inputs=['-ss',str(s['source_start']),'-i',s['source']]
            crop=''
            if s.get('full_screen_capture') and not s.get('full_screen_map'):
                x,y,w,h=s['window_rect']
                crop=f'crop={w}:{h}:{x}:{y},'
            if s.get('full_screen_map'):
                vf='crop=1280:796:0:48,scale=1280:796:flags=lanczos,pad=1920:1080:320:104:color=0x211710'
            else:
                vf=crop+'scale=1280:800:flags=lanczos,pad=1920:1080:320:104:color=0x211710'
            if s['layout']=='map-and-story':
                vf='crop=1280:796:0:48,scale=900:560:flags=lanczos,pad=1920:1080:64:230:color=0x211710'
            elif s['layout']=='tactical-closeup':
                x,y,_,_=s['window_rect']
                vf=f'crop=540:510:{x}:{y},scale=860:812:flags=lanczos,pad=1920:1080:64:104:color=0x211710'
            elif s['layout']=='split-comparison':
                starts=s['comparison_starts']
                inputs=['-ss',str(starts[0]),'-i',s['source'],'-ss',str(starts[1]),'-i',s['source']]
                complex_prefix=f'[0:v]{crop}scale=864:540,pad=1920:1080:64:220:color=0x211710[left];[1:v]{crop}scale=864:540[right];[left][right]overlay=992:220'
                vf='null'
        if s['key'] in ['opening','ending']:
            t=s['card_text']
            for key,size,y in [('title',72 if s['key']=='opening' else 60,340),('line1',42,470),('line2',38,555),('version',28,665)]:
                if s['key']=='opening':y={'title':770,'line1':875,'line2':940,'version':1010}[key]
                vf+=','+overlay(font,t[key],size,'(w-text_w)/2',y,'0xf3d89d' if key=='title' else 'white')
        else:
            t=s['text']
            side=s['layout'] in ('map-and-story','tactical-closeup')
            vf+=','+overlay(font,t['section'],27,64,40,'0xdac28c')
            vf+=','+overlay(font,t['title'],44,1040 if side else '(w-text_w)/2',270 if side else 30,'0xf3d89d')
            vf+=','+overlay(font,t['badge'],24,'w-text_w-60',44,'0xc3cbd1')
            vf+=','+overlay(font,t['line1'],32 if side else 38,1040 if side else '(w-text_w)/2',430 if side else 928)
            vf+=','+overlay(font,t['line2'],32 if side else 38,1040 if side else '(w-text_w)/2',500 if side else 982)
            if s['layout']=='split-comparison':
                vf+=','+overlay(font,t['native'],32,'64+(864-text_w)/2',160,'0xf3d89d')
                vf+=','+overlay(font,t['hd'],32,'992+(864-text_w)/2',160,'0xf3d89d')
        filters=['-vf',vf] if complex_prefix is None else ['-filter_complex',complex_prefix+','+vf+'[frame]','-map','[frame]']
        run(['ffmpeg','-nostdin','-v','warning','-y']+inputs+['-t',str(s['duration'])]+filters+['-an','-r','30','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p',str(video)],a.output/f'encode-{i:02}.log')
        generated.append(video)
    concat=a.output/'concat.txt';concat.write_text(''.join("file '"+str(p)+"'\n" for p in generated))
    music=plan['music'];duration=plan['seconds']
    filt=f'[1:a]atrim=duration=62.8,asetpts=PTS-STARTPTS[a0];[2:a]asetpts=PTS-STARTPTS[a1];[a0][a1]acrossfade=d=1.5:c1=tri:c2=tri,atrim=duration={duration},afade=t=in:d=0.2,afade=t=out:st={duration-1.5}:d=1.5[audio]'
    run(['ffmpeg','-nostdin','-v','warning','-y','-f','concat','-safe','0','-i',str(concat),'-i',music[0],'-i',music[1],'-filter_complex',filt,'-map','0:v:0','-map','[audio]','-t',str(duration),'-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-movflags','+faststart',str(destination)],a.output/'mux.log')
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(destination)]))
    (a.output/'story-ffprobe.json').write_text(json.dumps(probe,indent=2)+'\n')
    v=next(x for x in probe['streams'] if x['codec_type']=='video');audio=next(x for x in probe['streams'] if x['codec_type']=='audio')
    assert (v['codec_name'],v['width'],v['height'],v['r_frame_rate'])==('h264',1920,1080,'30/1')
    assert (audio['codec_name'],audio['sample_rate'],audio['channels'])==('aac','48000',2)
    assert abs(float(probe['format']['duration'])-duration)<.1
    assert abs(float(audio['duration'])-duration)<.1
    run(['ffmpeg','-nostdin','-v','info','-i',str(destination),'-af','volumedetect,silencedetect=n=-55dB:d=1.5,astats=metadata=1:reset=0','-vf','blackdetect=d=0.1:pix_th=0.02:pic_th=0.995,freezedetect=n=-60dB:d=2','-f','null','-'],a.output/'story-quality.log')
    quality=(a.output/'story-quality.log').read_text()
    assert 'max_volume: -inf' not in quality and 'max_volume: 0.0 dB' not in quality
    assert 'black_start:' not in quality
    # 片尾淡出可靜音，曲目銜接處不可出現長段靜音。
    silences=[float(t) for t in re.findall(r'silence_start: ([0-9.]+)',quality)]
    assert all(t>=duration-1.7 for t in silences),silences
    for i,s in enumerate(plan['segments']):
        run(['ffmpeg','-nostdin','-v','error','-y','-ss',str((s['start']+s['end'])/2),'-i',str(destination),'-frames:v','1',str(a.output/f'story-contact-{i:02}.png')],a.output/f'contact-{i:02}.log')
    manifest=dict(passed=True,version=plan['version'],edition='故事與玩法篇',video=name,sha256=sha(destination),bytes=destination.stat().st_size,seconds=duration,segments=plan['segments'],source_hashes=plan['source_hashes'],capture_inputs=plan['source_inputs'],subtitle_catalog_sha256=plan['catalog_sha256'],subtitle_srt_sha256=sha(a.output/'故事與玩法字幕.srt'),subtitle_layout_sha256=sha(a.output/'subtitle-layout.json'),story_source=plan['story_source'],music_hashes=plan['music_hashes'],music_provenance='使用者已授權的原譜RODQ1-0與RODQ3-0取樣HD版，剪輯交叉淡化，非原版晶片錄音',rights=plan['rights'],public_upload=False,visual_review_required=True,freeze_review='封面、故事地圖、隊伍目錄及閱讀停留是預期靜態；探索與戰鬥另看分幕動作',no_engine_or_package_change=False)
    (a.output/'promo-story-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=True,edition=manifest['edition'],seconds=duration,sha256=manifest['sha256']),ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['prepare','render']);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--root',type=Path);p.add_argument('--normal',type=Path);p.add_argument('--exploration',type=Path);p.add_argument('--combat',type=Path)
    p.add_argument('--font',type=Path);p.add_argument('--version');p.add_argument('--player',type=Path);p.add_argument('--acceptance',type=Path)
    a=p.parse_args();globals()[a.mode](a)
