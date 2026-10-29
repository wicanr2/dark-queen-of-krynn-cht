"""核對正常介面抽驗的實際畫格、控制紀錄與未結束交易，不啟動遊戲。"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from PIL import Image


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


assert len(sys.argv) in (3, 4, 5)
flags = sys.argv[3:]
assert len(flags) == len(set(flags)) and set(flags) <= {'--hd-off', '--manual-map', '--demo', '--guide', '--music'}
root, out = map(Path, sys.argv[1:3])
expected_hd = '--hd-off' not in flags
manual_map = '--manual-map' in flags
demo = '--demo' in flags
guide = '--guide' in flags
music = '--music' in flags
assert sum((manual_map,demo,guide,music)) <= 1
assert out.is_dir() and out.stat().st_uid == os.getuid()
reference = root / 'workplace/probe/player-sample-20261026-r5'
reference_proof = read(reference / 'checks.json')
assert reference_proof['passed'] and not reference_proof['state_injection']
for source in out.glob('*.ppm'):
    with Image.open(source) as picture:
        picture.save(source.with_suffix('.png'))

differences = {}
for name in ['03-scale', '04-original', '05-chinese', '06-manual', '07-return']:
    source = reference / (name + '.png')
    assert sha(source) == reference_proof['screenshots'][source.name]
    with Image.open(source) as expected, Image.open(out / source.name) as actual:
        assert expected.size == actual.size == (960, 600)
        differences[name] = sum(a != b for a, b in zip(expected.convert('RGB').tobytes(), actual.convert('RGB').tobytes()))
assert not any(differences.values()), differences
controls = read(out / 'session/controls.json')
counts = read(out / 'session/render-counts.json')['Counts']
diagnostics_path = out / 'session/ui-diagnostics.json'
diagnostics = read(diagnostics_path)
map_windows = [e for e in diagnostics.get('reader_events', []) if e.get('action') in ('map-window-open', 'map-window-close')]
windowed_maps = bool(map_windows)
assert not diagnostics['renderer']['pending'] and diagnostics['reader_stable']
assert len(diagnostics['words']) == 12
events = diagnostics['manual_events']
if manual_map and not windowed_maps:
    assert [event['key'] for event in events] == ['F6', 'Right', 'Down', 'Return', 'ZoomIn', 'ZoomIn', 'PanRight', 'PanDown', 'Home', 'Esc', 'Esc']
    assert len({e['step'] for e in events}) == 1, '手動查閱期間原版不應前進'
    views = [events[n]['page']['Image'] for n in [3,4,5,7,8]]
    assert views == [dict(zoom=0,x=0,y=0),dict(zoom=1,x=296,y=416),dict(zoom=2,x=448,y=468),dict(zoom=2,x=512,y=532),dict(zoom=0,x=0,y=0)]
    assert sha(out/'08-map-fit.png') == sha(out/'12-map-reset.png')
    player = read(out/'build-info-at-start.json')
    profiles = [p for p in sorted((root/'workplace/probe').glob('player-*/inputs/player-profile.json'))
                if sha(p) == player['profile_sha256']]
    assert profiles, '缺少與啟動時雜湊相同的閱讀資料'
    profile = read(profiles[0])
    map_file = profiles[0].parent/'manual-world-map.png'
    assert sha(map_file) == profile['Files']['manual-world-map.png']
    with Image.open(map_file) as source:
        source = source.convert('RGB')
        for name, view in zip(['08-map-fit','09-map-native','10-map-double','11-map-pan','12-map-reset'], views):
            with Image.open(out/(name+'.png')) as screenshot:
                # 960×600視窗，640×400邏輯框；獨立以來源座標核對圖區。
                for sy in range(48,360,3):
                    ly = sy*2//3-32
                    for sx in range(24,936,3):
                        lx = sx*2//3-16
                        if view['zoom'] == 0:
                            if not 184 <= lx < 424: continue
                            px,py=(lx-184)*5,ly*5
                        else:
                            div = view['zoom']
                            px,py=view['x']+lx//div,view['y']+ly//div
                        assert screenshot.getpixel((sx,sy))[:3] == source.getpixel((px,py)),(name,sx,sy,px,py)
    assert sha(map_file) == json.loads((map_file.parent/'manual-map-provenance.json').read_text())['map_sha256']
elif manual_map:
    assert [e['key'] for e in events] == ['F6','Right','Down','Return','Esc','Esc']
    assert len({e['step'] for e in events}) == 1
    build=read(out/'build-info-at-start.json')
    folder=next(p.parent for p in (root/'workplace/probe').glob('player-*/inputs/player-profile.json') if sha(p)==build['profile_sha256'])
    map_file=folder/'manual-world-map.png'
else:
    expected_manual=['F6','Esc']
    if guide and diagnostics['reader_mode']=='manual': expected_manual+=['F6']
    assert [event['key'] for event in events] == expected_manual
assert [event['chinese'] for event in controls if event['action'] == 'language'] == [False, True]
assert next(event for event in controls if event['action'] != 'music')['action'] == 'scale3' and all(event['hd'] is expected_hd for event in controls)
assert controls[-1]['action'] == 'screenshot'
assert not counts.get('unexpected_owned_native_writes', 0) and counts['nonvideo_copy'] > 0
assert sha(out / '05-chinese.png') == sha(out / '07-return.png')
assert sha(out / '06-manual.png') != sha(out / '05-chinese.png')
assert 'panic' not in (out / 'player.log').read_text()
if guide:
    events = diagnostics['guide_events']
    close_in_reader=windowed_maps and diagnostics['reader_mode']=='guide'
    expected=['F7','Return','Esc','Left','Left','Left','Return','PgDn','Esc','Down','Return']
    if not windowed_maps: expected+=['ZoomIn','ZoomIn','PanRight','PanDown','Home']
    expected+=['Esc','Esc','F7','F7']
    if close_in_reader: expected.pop()
    assert [e['key'] for e in events] == expected
    assert len({e['step'] for e in (events[:-1] if close_in_reader else events[:-2])}) == 1, '攻略查閱期間原版不應前進'
    if not close_in_reader: assert events[-2]['step'] == events[-1]['step']
    assert events[6]['page']['Number'] == 1 and events[7]['page']['Number'] == 2
    assert events[10]['book'] == 'chapter-17' and events[10]['page']['Mode'] == 'guide-map'
    assert events[10]['page']['SourceKey'] == 'guide.map.flame-0'
    assert events[10]['page']['Image'] == dict(zoom=0,x=0,y=0)
    if not windowed_maps:
        assert events[11]['page']['Image']['zoom'] == 1 and events[12]['page']['Image']['zoom'] == 2
        assert events[14]['page']['Image']['x'] > events[12]['page']['Image']['x']
        assert events[14]['page']['Image']['y'] > events[12]['page']['Image']['y']
        assert events[15]['page']['Image'] == dict(zoom=0,x=0,y=0)
    for name in (['23-guide-return'] if close_in_reader else ['23-guide-return','25-guide-toggle-return']):
        assert sha(out/(name+'.png')) == sha(out/'07a-guide-base.png')
    assert sha(out/'17-guide-map-fit.png') == sha(out/'21-guide-map-reset.png')
    assert sha(out/'22-guide-map-index.png') == sha(out/'24-guide-reopen.png')
    assert sha(out/'15a-guide-body.png') != sha(out/'16-guide-page.png')
    assert any(c['action'] == 'guide' for c in controls), '工具列攻略未實際點選'
    build = read(out/'build-info-at-start.json')
    profiles = [p for p in (root/'workplace/probe').glob('player-*/inputs/player-profile.json') if sha(p) == build['profile_sha256']]
    assert profiles
    folder = profiles[0].parent
    index = read(folder/'guide-index.json')
    assert index['complete'] and index['map_count'] == 52 and len(index['books']) == 20
    assert sum(len(b['documents']) for b in index['books']) == 72
    source_path = folder/'guide-map-flame-0.png'
    assert sha(source_path) == read(profiles[0])['Files'][source_path.name]
    if not windowed_maps:
      with Image.open(source_path) as original:
        original = original.convert('RGB');w,h = original.size
        for name, e in zip(['17-guide-map-fit','18-guide-map-native','19-guide-map-double','20-guide-map-pan','21-guide-map-reset'],[events[i] for i in (10,11,12,14,15)]):
            view=e['page']['Image'];n,d=(208,h) if view['zoom']==0 else (view['zoom'],1)
            left,top=max(0,(608-w*n//d)//2),max(0,(208-h*n//d)//2)
            with Image.open(out/(name+'.png')) as picture:
                for sy in range(48,360,6):
                    ly=sy*2//3-32
                    for sx in range(24,936,6):
                        lx=sx*2//3-16
                        if not (left<=lx<min(608,left+w*n//d) and top<=ly<min(208,top+h*n//d)):continue
                        px,py=view['x']+(lx-left)*d//n,view['y']+(ly-top)*d//n
                        assert picture.getpixel((sx,sy))[:3] == original.getpixel((px,py)),(name,sx,sy,px,py)
if windowed_maps:
    assert [e['action'] for e in map_windows] == ['map-window-open','map-window-close']
    assert map_windows[0]['fullscreen'] and map_windows[0]['pid'] > 0
    assert map_windows[0]['step'] == map_windows[1]['step'], '獨立視窗不能推進原版'
    names=(['17-guide-map-fit','18-guide-map-native','19-guide-map-double','20-guide-map-pan','21-guide-map-reset'] if guide else
           ['08-map-fit','09-map-native','10-map-double','11-map-pan','12-map-reset'])
    for name in names:
        with Image.open(out/(name+'.png')) as picture: assert picture.size==(1280,900), (name,picture.size)
    assert sha(out/(names[0]+'.png'))==sha(out/(names[-1]+'.png'))
    assert len({sha(out/(name+'.png')) for name in names[:-1]})==4
    source=source_path if guide else map_file
    index=read(source.parent/('guide-index.json' if guide else 'manual-index.json'))
    docs=[d for b in index['books'] for d in b['documents'] if d.get('image',{}).get('file')==source.name]
    assert len(docs)==1
    crop=docs[0]['image']['crop']
    with Image.open(source) as original, Image.open(out/(names[0]+'.png')) as screenshot:
        original=original.crop(crop).convert('RGB');w,h=original.size
        scale=min(1248/w,796/h);dw,dh=int(w*scale),int(h*scale)
        left,top=int((1280-w*scale)/2),int(48+(796-h*scale)/2)
        expected=original.resize((dw,dh),Image.Resampling.BILINEAR)
        actual=screenshot.crop((left,top,left+dw,top+dh)).convert('RGB')
        # GPU線性取樣與Pillow的中心對齊略有差異；整張來源獨立核對，不只驗尺寸。
        error=sum(abs(a-b) for a,b in zip(actual.tobytes(),expected.tobytes()))/(dw*dh*3)
        assert error<10, ('fullscreen map source comparison',error)
    assert not any(x.get('key') in ('ZoomIn','PanRight','PanDown') for x in diagnostics['manual_events']+(diagnostics.get('guide_events') or []))
if demo:
    if read(out/'build-info-at-start.json').get('transparent_resume_verified'):
        assert not counts.get('image_native_fallback',0), '森林示範仍丟失完整圖片身分'
    with Image.open(out/'02-return.png') as expected, Image.open(out/'09-demo-return.png') as actual:
        assert expected.size == actual.size == (640,400)
        for y in range(400):
            for x in range(640):
                if x < 32 and y < 32:continue
                assert expected.getpixel((x,y)) == actual.getpixel((x,y)), ('demo return',x,y)
    assert sha(out/'08-demo.png') != sha(out/'02-return.png'), '未進入示範'
if music:
    audio = read(out/'session/music-events.json')
    assert audio['available'] and audio['enabled'] and not audio['errors']
    assert [c['music'] for c in controls if c['action']=='music'] == [False,True,False,True]
    assert all(not c['music'] for c in controls if c['action'] in ['scale3','language'])
    assert len([c for c in audio['events'] if c['Kind']=='start']) == 1
    assert audio['events'][0]['Key']=='RODQ1-0'
    assert read(out/'session/preferences.json')['Music'] is True

# 保留實際執行時的工具；舊批補檢查時不能用新runner覆寫來源快照。
sources = out / 'source'
sources.mkdir(exist_ok=True)
for name in ['player-sample.sh', 'player_gui_probe.c', 'player_xtest_key.go', 'player_sample_check.py']:
    if not (sources / name).exists():
        shutil.copyfile(root / 'tools' / name, sources / name)
build = out / 'build-info-at-start.json'
assert build.is_file(), '缺少啟動時的建置來源紀錄'
result = dict(
    mode='normal-cold-start-role-menu-and-manual-XTEST', passed=True,
    build_sha256=read(build)['binary_sha256'], controls=controls, counts=counts,
    static_menu_comparison_byte_differences=differences,
    state_injection=False, new_assets=True, expected_hd=expected_hd,
    screenshots={p.name: sha(p) for p in out.glob('*.png')},
    source={p.name: sha(p) for p in sources.iterdir()},
    scope=['cold startup', 'native P to character management', 'scale 2x to 3x',
           'original/Chinese switch', 'manual open/close', 'reader native corner preserved',
           'screenshot', 'WM_DELETE_WINDOW exit', 'RAM copies excluded from display transactions'],
    not_verified=['creation completion', 'exploration', 'combat', 'save/reload', 'new HD sources in normal game'],
    native_input='XTEST server events; XGB v1.1.1 in fixed offline container',
    diagnostics_sha256=sha(diagnostics_path), reference_receipt_sha256=sha(reference / 'checks.json'),
    checker_sha256=sha(root / 'tools/player_sample_check.py'))
if manual_map:
    result['scope'] += ['manual world map fit/native/double', 'manual map pan/reset', 'reader CPU pause', 'manual index and game return']
    result['manual_map_source_sha256'] = sha(map_file)
if demo:
    result['scope'] += ['opening Demo selection', 'Esc interrupts native demo', 'opening menu restored', 'Play enters character management after demo cancellation']
    if read(build).get('transparent_resume_verified'):
        result['scope'] += ['transparent image source retained after event boundary in forest demo']
if guide:
    result['scope'] += ['guide toolbar click, Esc close and F7 reopen' if close_in_reader else 'guide toolbar click and F7 toggle', '20 guide sections and 52 maps loaded',
        'guide body paging', 'chapter navigation', 'map fit/native/double and pan/reset',
        'independent map source pixel sampling', 'guest CPU paused during guide', 'index and game return']
    result['guide_events'] = diagnostics['guide_events']
    result['guide_map_source_sha256'] = sha(source_path)
if music:
    device_path=out/'audio-device.json'
    device=read(device_path)['audio_device'] if device_path.exists() else 'null'
    assert device in ('null','pulse')
    result['scope'] += ['original title cue', 'F8 music off/on', 'music toolbar click', 'music preference independent of scale/language/HD', 'no cue restart on preference changes',
                        'desktop PulseAudio socket accepts playback' if device=='pulse' else 'ALSA null device accepts playback']
    result['audio_device']=device
    result['not_verified'] += ['human listening', 'physical audio device']
    result['music_events_sha256'] = sha(out/'session/music-events.json')
if windowed_maps:
    result['map_window'] = dict(events=map_windows,canvas=[1280,900],source_mean_error=error,
                              zoom_pan_reset=True,separate_process=True,guest_steps_unchanged=True)
(out / 'checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'passed': True, 'frames': len(differences), 'byte_differences': 0,
                  'open_render_transactions': 0, 'role_buttons': 12}))
