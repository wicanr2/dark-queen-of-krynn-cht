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
assert len(flags) == len(set(flags)) and set(flags) <= {'--hd-off', '--manual-map', '--demo'}
root, out = map(Path, sys.argv[1:3])
expected_hd = '--hd-off' not in flags
manual_map = '--manual-map' in flags
demo = '--demo' in flags
assert not (manual_map and demo)
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
assert not diagnostics['renderer']['pending'] and diagnostics['reader_stable']
assert len(diagnostics['words']) == 12
events = diagnostics['manual_events']
if manual_map:
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
else:
    assert [event['key'] for event in events] == ['F6', 'Esc']
assert [event['chinese'] for event in controls if event['action'] == 'language'] == [False, True]
assert controls[0]['action'] == 'scale3' and all(event['hd'] is expected_hd for event in controls)
assert controls[-1]['action'] == 'screenshot'
assert not counts.get('unexpected_owned_native_writes', 0) and counts['nonvideo_copy'] > 0
assert sha(out / '05-chinese.png') == sha(out / '07-return.png')
assert sha(out / '06-manual.png') != sha(out / '05-chinese.png')
assert 'panic' not in (out / 'player.log').read_text()
if demo:
    with Image.open(out/'02-return.png') as expected, Image.open(out/'09-demo-return.png') as actual:
        assert expected.size == actual.size == (640,400)
        for y in range(400):
            for x in range(640):
                if x < 32 and y < 32:continue
                assert expected.getpixel((x,y)) == actual.getpixel((x,y)), ('demo return',x,y)
    assert sha(out/'08-demo.png') != sha(out/'02-return.png'), '未進入示範'

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
(out / 'checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'passed': True, 'frames': len(differences), 'byte_differences': 0,
                  'open_render_transactions': 0, 'role_buttons': 12}))
