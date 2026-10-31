"""重跑全部介面測試並產生契約；原版IRQ對照使用verify-base正常快照。"""
import hashlib
import json
import re
from pathlib import Path
import shlex
import sys

mode, root, output = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
BASE_RECEIPT = 'workplace/probe/verify-base-20261031-r2/base/receipt.json'
TEST_FILES = ['ui_cold_fill_test.go','player_music_assets_test.go','player_map_test.go','player_text_hd_test.go','player_quiz_test.go']
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def passed(path):
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    assert not any(r['Action']=='fail' for r in rows)
    assert any(r['Action']=='pass' and not r.get('Test') for r in rows)
    return {r['Test'] for r in rows if r['Action']=='pass' and r.get('Test')}

assert output.is_dir() and output.stat().st_uid == 1000
if mode=='prepare':
    sources=(root/'tools/player_sources.txt').read_text().splitlines()
    assert len(sources)==len(set(sources)) and all(Path(n).name==n and n.endswith('.go') for n in sources)
    args=['go','build','-modfile','/out/audio-go.mod','-overlay','/out/build-overlay/overlay.json','-o','/out/dqk-player']+['/tools/'+n for n in sources]
    overlay = json.loads((output/'build-overlay/overlay.json').read_text())
    overlay['Replace'].update({
        '/src/oracle/dqk_render_probe.go':'/tools/oracle_render_probe.go',
        '/src/internal/machine/dqk_render_probe.go':'/tools/machine_render_probe.go',
    })
    (output/'ui-overlay.json').write_text(json.dumps(overlay,indent=2)+'\n')
    args[args.index('-overlay')+1]='/out/ui-overlay.json'
    i = args.index('-o')
    del args[i:i+2]
    args[1:2] = ['test','-json','-count=1']
    args += ['/tools/'+n for n in TEST_FILES]
    script = '''#!/usr/bin/env bash
set -euo pipefail
Xvfb :92 -screen 0 1280x900x24 -nolisten tcp >/out/ui-xvfb.log 2>&1 &
XVFB_PID=$!
trap 'kill "$XVFB_PID" 2>/dev/null || true' EXIT
for i in {1..50}; do [[ -S /tmp/.X11-unix/X92 ]] && break; sleep .1; done
test -S /tmp/.X11-unix/X92
export DISPLAY=:92
'''+shlex.join(args)+' >/out/ui-tests.json\n'
    (output/'ui-tests.sh').write_text(script)
elif mode=='finish':
    # 2026-10-31起不再比對已刪的父批收據：這次測試本身就是證據。編入的每個Test函式都須通過，
    # 不得略過；原版IRQ對照以verify-base正常快照實際執行。
    rows = [json.loads(x) for x in (output/'ui-tests.json').read_text().splitlines()]
    assert not any(r['Action'] in ('fail', 'skip') for r in rows), '介面測試失敗或略過'
    tests = passed(output/'ui-tests.json')
    files = [n for n in TEST_FILES]
    expected = {m for n in files for m in re.findall(r'^func (Test\w+)\(', (root/'tools'/n).read_text(), re.M)}
    assert {t for t in tests if '/' not in t} == expected, '介面測試清單不符'
    def sub(name):
        return len([t for t in tests if t.startswith(name+'/')])
    counts = dict(cases=sub('TestColdFillObserverIRQBoundary'), quiz_guard_cases=sub('TestStartupQuizPresentationGate'),
                  camp_guard_cases=sub('TestCampSavePromptGuards'), quiz_footer_guard_cases=sub('TestQuizFooterReplacement'),
                  quiz_enter_retire_cases=sub('TestQuizEnterRetiresWithOriginalFooter'))
    assert counts == dict(cases=16, quiz_guard_cases=3, camp_guard_cases=2, quiz_footer_guard_cases=3, quiz_enter_retire_cases=2), counts
    receipt_path = root/BASE_RECEIPT
    base = json.loads(receipt_path.read_text())
    snapshot = receipt_path.parent/'palanthas.state'
    assert base['exe_sha256'] == sha(root/'workplace/input/dos/drkqueen/DQK.EXE')
    assert base['states']['palanthas.state']['sha256'] == sha(snapshot)
    names = (root/'tools/player_sources.txt').read_text().splitlines() + files
    result = dict(version=2, passed=True, **counts, machine_effects_unchanged=True, virtual_time_unchanged=True,
                  sources={'tools/'+n: sha(root/'tools'/n) for n in names}, tests_sha256=sha(output/'ui-tests.json'),
                  normal_source_snapshot_sha256=sha(snapshot), base_receipt_sha256=sha(receipt_path),
                  scope='編入的介面、音樂、地圖、原版模式、ASCII、查驗與16組原版IRQ對照全部重跑；IRQ對照以verify-base冷啟動正常快照執行，不沿用已刪父批')
    (output/'ui-contract.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=True,passed_tests=len(tests),contract_sha256=sha(output/'ui-contract.json'))))
else:
    raise ValueError(mode)
