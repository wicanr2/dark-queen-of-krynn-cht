"""核對正常森林紮營支線，明列未觸發整句；不作中文或 GUI 驗收。"""
from pathlib import Path
import shutil
import sys

from bar_ui_inputs import write
from literal_catalog import read, sha
from passage_chain_source import comparable

STUDY = 'passage-chain-camp-20261024'
BINARY = 'passage-chain-live-20261024/programs-r1/passage-chain-probe'
PAIRS = [
    ('', 'request-r1.json', 'battle-text-20261024/control-journey-r2/final.state', 14),
    ('rest-', 'rest-request-r1.json', STUDY+'/observe-r1/final.state', 1),
    ('area-', 'area-request-r1.json', STUDY+'/rest-observe-r1/final.state', 2),
    ('south-', 'south-request-r1.json', STUDY+'/area-observe-r1/final.state', 12),
]
TOOLS = ('passage_camp_source.py', 'passage_chain_source.py', 'passage_chain_probe.go',
         'ui_passage_source.go', 'bar_ui_inputs.py', 'literal_catalog.py', 'text_catalog.py',
         'ui_list_inputs.py', 'combat_finish_inputs.py')


def verify(root, output):
    probe = root/'workplace/probe'
    assert output == probe/STUDY
    assert sha(probe/BINARY) == 'd9250e5ea4124debd373f3a24b8835e5990dab81a76e8febfccdaa9c5c8a7656'
    total = 0
    for prefix, request, state, count in PAIRS:
        observed, control = [output/(prefix+n+'-r1') for n in ('observe', 'control')]
        a, b = [read(p/'receipt.json') for p in (observed, control)]
        comparable(a, b)
        assert a['probe_sha256'] == b['probe_sha256'] == sha(probe/BINARY)
        assert a['observe'] and not b['observe'] and len(a['checkpoints']) == count
        assert not a['paragraphs'] and not b['paragraphs'] and a['passage_candidate_parts'] == b['passage_candidate_parts'] == 0
        assert a['state_sha256'] == sha(probe/state) and a['request_sha256'] == sha(output/request)
        for cp in a['checkpoints']:
            assert sha(observed/(cp['label']+'.png')) == sha(control/(cp['label']+'.png'))
        assert sha(observed/'final.state') == sha(control/'final.state')
        total += count
    assert total == 29
    return total


def evidence(root, output):
    count = verify(root, output)
    snapshots = output/'tool-snapshots'
    snapshots.mkdir()
    for name in TOOLS:
        shutil.copyfile(root/'tools'/name, snapshots/name)
    probe = root/'workplace/probe'
    sources = [probe/BINARY, root/'workplace/input/dos/drkqueen/DQK.EXE',
               probe/'battle-text-20261024/control-journey-r2/final.state']
    sources += [probe/'passage-chain-20261024/chain-inputs-r1'/n for n in ('registry.json', 'en.tsv')]
    def info(p):
        s = p.stat()
        assert (s.st_uid, s.st_gid) == (1000, 1000), p
        return dict(bytes=s.st_size, sha256=sha(p), uid=s.st_uid, gid=s.st_gid)
    write(output/'evidence.json', dict(draft=True, runtime_integrated=False,
        normal_checkpoints=count, normal_chain_verified=False, translated_keys_added=0,
        engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        sources={str(p):info(p) for p in sources},
        tools={name:sha(root/'tools'/name) for name in TOOLS},
        artifacts={str(p.relative_to(output)):info(p) for p in sorted(output.rglob('*')) if p.is_file()},
        limits='正常森林移動、預設休息、區域圖與南行沒有敘事；不列整句、GUI、中文或完整路線覆蓋。'))


if __name__ == '__main__':
    command, root, output = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    if command == 'verify':
        print('normal checkpoints', verify(root, output), 'paragraphs 0; no chain observed')
    elif command == 'evidence':
        evidence(root, output)
    elif command == 'audit':
        from combat_finish_inputs import audit
        audit(root, output)
    else:
        raise SystemExit('verify | evidence | audit')
