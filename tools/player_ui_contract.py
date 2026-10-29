"""重跑受影響的24個介面子案例；原版IRQ根收據沿用，兩者分列。"""
import hashlib
import json
from pathlib import Path
import shlex
import sys

mode, root, output = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
parent = root/'workplace/probe/player-hd-finish-20261029'
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
    args += ['/tools/ui_cold_fill_test.go','/tools/player_music_assets_test.go']
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
    assert passed(output/'ui-tests.json')==passed(parent/'ui-tests.json')|{'TestOriginalMusicAliases','TestDecodeOriginalScoreMusic'}
    old = json.loads((parent/'camp-save-contract.json').read_text())
    for name, digest in old['sources'].items():
        if name not in ('tools/early_text_live.go','tools/player_render_owner.go'):
            assert sha(root/name)==digest, name
    result = dict(old)
    result.update(sources={name:sha(root/name) for name in old['sources']},tests_sha256=sha(output/'ui-tests.json'),
                  parent_contract_sha256=sha(parent/'camp-save-contract.json'),
                  scope='原版IRQ根收據沿用；本次重跑24個介面子案例，新增音樂欄位及工具列不改既有UI觀察器')
    (output/'ui-contract.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=24,contract_sha256=sha(output/'ui-contract.json'))))
else:
    raise ValueError(mode)
