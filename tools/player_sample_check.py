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


root, out = map(Path, sys.argv[1:])
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
assert [event['key'] for event in diagnostics['manual_events']] == ['F6', 'Esc']
assert [event['chinese'] for event in controls if event['action'] == 'language'] == [False, True]
assert controls[0]['action'] == 'scale3' and all(event['hd'] for event in controls)
assert controls[-1]['action'] == 'screenshot'
assert not counts.get('unexpected_owned_native_writes', 0) and counts['nonvideo_copy'] > 0
assert sha(out / '05-chinese.png') == sha(out / '07-return.png')
assert sha(out / '06-manual.png') != sha(out / '05-chinese.png')
assert 'panic' not in (out / 'player.log').read_text()

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
    state_injection=False, new_assets=True,
    screenshots={p.name: sha(p) for p in out.glob('*.png')},
    source={p.name: sha(p) for p in sources.iterdir()},
    scope=['cold startup', 'native P to character management', 'scale 2x to 3x',
           'original/Chinese switch', 'manual open/close', 'reader native corner preserved',
           'screenshot', 'WM_DELETE_WINDOW exit', 'RAM copies excluded from display transactions'],
    not_verified=['creation completion', 'exploration', 'combat', 'save/reload', 'new HD sources in normal game'],
    native_input='XTEST server events; XGB v1.1.1 in fixed offline container',
    diagnostics_sha256=sha(diagnostics_path), reference_receipt_sha256=sha(reference / 'checks.json'),
    checker_sha256=sha(root / 'tools/player_sample_check.py'))
(out / 'checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'passed': True, 'frames': len(differences), 'byte_differences': 0,
                  'open_render_transactions': 0, 'role_buttons': 12}))
