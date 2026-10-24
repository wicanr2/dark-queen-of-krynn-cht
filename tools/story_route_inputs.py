"""正常敘事重播的 DRAFT 證據；不擴張譯表或改變原版路徑。"""
import ast
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

from literal_catalog import catalog, digest, read, sha, windows

BASE = 'journal59-route-20261025/inputs-r3'
STUDY = 'voyage-text-20261025'
SOURCE = STUDY+'/observe-r2/receipt.json'
STATE = 'journal59-route-20261025/control-r2/final.state'
KEYS = ('ecl.10f008d4d82f4f1a1db9', 'ecl.5b5e9f757e06ceeef236', 'ecl.0fb510edbdacde81c506',
        'ecl.728ee4b90850be968570', 'ecl.f91bb9c12982ec47f8ea')


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def native(root, output):
    a, b = [read(output/f'{mode}-r2/receipt.json') for mode in ('observe', 'control')]
    for key in ('source_commit', 'go_version', 'exe_sha256', 'probe_sha256', 'state_sha256', 'request_sha256', 'request', 'checkpoints'):
        assert a[key] == b[key], key
    assert a['observe'] and not b['observe'] and len(a['checkpoints']) == 65
    assert a['source_commit'] == 'f79eab6db8c64a524a06535e53e5d32b0bbcf7c8'
    assert a['exe_sha256'] == '3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
    probe = root/'workplace/probe'
    assert a['probe_sha256'] == sha(probe/'combat-aim-route-20261024/programs-r3/ui-context-probe')
    assert a['state_sha256'] == sha(probe/STATE) and a['request_sha256'] == sha(output/'request-r2.json')
    assert not any(v for k, v in a.items() if k.startswith('pending'))
    old = read(output/'observe-r1/receipt.json')
    for key in ('calls', 'paragraphs', 'wrappers', 'fill_events', 'display_changes', 'menus', 'list_events'):
        assert a[key] == old[key], key
    checkpoints = {c['step']: c for c in a['checkpoints']}
    previous = read(probe/'journal59-route-20261025/depart-observe-r2/receipt.json')
    assert old['checkpoints'][:2] == previous['checkpoints']
    for cp in old['checkpoints']:
        current = checkpoints[cp['step']]
        assert cp['indexed_file'] == cp['label']+'.idx' and current['indexed_file'] == current['label']+'.idx'
        for suffix in ('.idx', '.png'):
            assert sha(output/'observe-r1'/(cp['label']+suffix)) == sha(output/'observe-r2'/(current['label']+suffix))
        assert {k: v for k, v in cp.items() if k not in ('label', 'indexed_file')} == {k: v for k, v in current.items() if k not in ('label', 'indexed_file')}
    for cp in a['checkpoints']:
        assert not cp['file_writes'] and not cp['unimplemented']
        for suffix in ('.idx', '.png'):
            name = cp['label']+suffix
            assert sha(output/'observe-r2'/name) == sha(output/'control-r2'/name)
    final = sha(output/'control-r2/final.state')
    assert final == sha(output/'observe-r2/final.state') == sha(output/'control-r1/final.state')
    write(output/'native-check.json', dict(checkpoints=65, source_path=SOURCE,
        source_sha256=sha(output/'observe-r2/receipt.json'), final_state_sha256=final))


def prompt_witnesses(probe, config, en, trace):
    """只用原版來源與原始色號，保存每次完整灰底提示的實際可見基準。"""
    result = []
    position = lambda v: v if v < 400 else (v-8000)*2
    def crop(cp, rect):
        path = probe/STUDY/'observe-r2'/(cp['label']+'.idx')
        raw = path.read_bytes()
        assert sha(path) == cp['indexed_sha256']
        x, y, width, height = rect
        return b''.join(raw[row*320+x:row*320+x+width] for row in range(y, y+height))
    for field in config['Fields']:
        if field.get('UpperCaller') != dict(Seg=0xceb, Off=0x4bd): continue
        calls = [c for c in trace['calls'] if c['caller'] == field['Caller']
            and c['format']['nul_terminated'] and digest(c['format']['text']) == field['FormatSHA256']
            and c['stack'][2:4] == [field['RawY'], field['RawX']] and c['wrapper_index'] >= 0
            and trace['wrappers'][c['wrapper_index']]['caller'] == field['UpperCaller']
            and c['vararg_1_candidate']['text'][field['Start']:field['Start']+field['Length']] == en[field['Key']]]
        for call in calls:
            rect = [position(field['RawX'])+field['Start']*8, position(field['RawY']), field['Length']*8, 8]
            until = min([p['step'] for p in trace['paragraphs'] if p['step'] > call['return_step']]+[trace['checkpoints'][-1]['step']+1])
            printed = next(cp for cp in trace['checkpoints'] if call['return_step'] <= cp['step'] < until and set(crop(cp, rect)) == {0, 7})
            pixels = crop(printed, rect)
            result.append(dict(key=field['Key'], field_entry=call['step'], native_rect=rect,
                printed=printed['label'], printed_sha256=hashlib.sha256(pixels).hexdigest()))
    assert len(result) == 6
    return result


def derive(probe):
    base = probe/BASE
    trace = read(probe/SOURCE)
    config = copy.deepcopy(read(base/'inputs.json'))
    en = catalog(base/'en.tsv')
    paragraphs = []
    for p, key in zip(trace['paragraphs'], KEYS, strict=True):
        assert p['source']['nul_terminated'] and key == 'ecl.'+digest(p['source']['text'])[:20]
        binding, = [b for b in config['Paragraphs'] if b['Key'] == key and en[key] == p['source']['text']
            and b['Caller'] == p['caller'] and b['NativeBox'] == p['native_box']
            and all(b[k] == p[v] for k, v in (('Foreground', 'foreground'), ('Background', 'background'), ('Clear', 'clear')))]
        assert not binding.get('JournalEntry')
        paragraphs.append(binding)
    assert [p['Clear'] for p in paragraphs] == [1, 1, 1, 0, 1]
    assert all(m['Signature'] in config['Menus'] for m in trace['menus'])
    initial_call, = [c for c in trace['calls'] if c['caller'] == dict(Seg=0xceb, Off=0x1be) and c['step'] < trace['paragraphs'][0]['step']]
    menu = trace['menus'][initial_call['menu_index']]
    assert initial_call['format']['nul_terminated'] and initial_call['format']['hex'] == '596573'
    initial_field, = [f for f in config['Fields'] if f['Pane'] == 'menu' and f['MenuSignature'] == menu['Signature']
        and en[f['Key']] == initial_call['format']['text']]
    x, y, width, height = initial_call['stack'][3], initial_call['stack'][2], initial_field['Length']*8, 8
    printed, = [cp for cp in trace['checkpoints'] if cp['step'] == initial_call['return_step']]
    raw = (probe/STUDY/'observe-r2'/printed['indexed_file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == printed['indexed_sha256']
    initial_pixels = b''.join(raw[row*320+x:row*320+x+width] for row in range(y, y+height))
    initial = dict(field_entry=initial_call['step'], key=initial_field['Key'], menu_signature=menu['Signature'],
        native_rect=[x, y, width, height], printed=printed['label'], printed_sha256=hashlib.sha256(initial_pixels).hexdigest())
    config['fine_windows'] = windows(trace)
    controls = dict(native_request_sha256=sha(probe/STUDY/'request-r2.json'), controls=[])
    data = dict(records=[], fields=[], paragraphs=paragraphs, controls=controls,
        initial_button=initial,
        prompt_witnesses=prompt_witnesses(probe, config, en, trace),
        page_validation=dict(source_path=SOURCE, source_sha256=sha(probe/SOURCE)))
    return config, data


def generate(root, output):
    probe = root/'workplace/probe'; base = probe/BASE
    config, data = derive(probe)
    target = output/'inputs-r2'
    shutil.copytree(base, target)
    proof = read(base/'provenance.json')
    proof['story_route_extension'] = dict(base=BASE, base_files={p.name: sha(p) for p in base.iterdir()},
        source_path=SOURCE, source_sha256=sha(probe/SOURCE), data=data)
    write(target/'inputs.json', config)
    write(target/'reader-controls.json', data['controls'])
    write(target/'provenance.json', proof)


def check_sources(inputs, config, proof, en, zh, glyphs):
    probe = inputs.parent.parent; base = probe/BASE
    extension = proof['story_route_extension']
    assert extension['base'] == BASE and extension['source_path'] == SOURCE
    assert extension['source_sha256'] == sha(probe/SOURCE)
    assert extension['base_files'] == {p.name: sha(p) for p in base.iterdir()}
    expected, data = derive(probe)
    assert config == expected and extension['data'] == data, 'story route source'
    assert read(inputs/'reader-controls.json') == data['controls']
    parent = read(base/'provenance.json')
    assert {k: v for k, v in proof.items() if k != 'story_route_extension'} == parent
    for name in set(extension['base_files'])-{'inputs.json', 'provenance.json', 'reader-controls.json'}:
        assert (inputs/name).read_bytes() == (base/name).read_bytes(), name
    assert en == catalog(base/'en.tsv') and zh == catalog(base/'zh-TW.tsv') and glyphs == read(base/'glyphs-16.json')
    return base, read(base/'inputs.json'), parent, en, zh, glyphs


def guards(root, output):
    source = output/'inputs-r2'
    def check(p):
        check_sources(p, read(p/'inputs.json'), read(p/'provenance.json'), catalog(p/'en.tsv'), catalog(p/'zh-TW.tsv'), read(p/'glyphs-16.json'))
    check(source); rejected = []
    for name in ('paragraph', 'control', 'translation', 'glyph', 'prompt-witness', 'initial-button'):
        with tempfile.TemporaryDirectory(dir=output, prefix='guard-') as directory:
            p = Path(directory); shutil.copytree(source, p, dirs_exist_ok=True)
            config, proof = read(p/'inputs.json'), read(p/'provenance.json')
            if name == 'paragraph': config['Paragraphs'][-1]['SHA256'] = '0'*64
            elif name == 'control':
                control = read(p/'reader-controls.json'); control['controls'].append(dict(at=5506000000, key='F5'))
                write(p/'reader-controls.json', control)
            elif name == 'translation':
                f = p/'zh-TW.tsv'; f.write_text(f.read_text()+'bad\tx\n')
            elif name == 'glyph':
                g = read(p/'glyphs-16.json'); g['glyphs'].pop(next(iter(g['glyphs']))); write(p/'glyphs-16.json', g)
            elif name == 'prompt-witness': proof['story_route_extension']['data']['prompt_witnesses'][0]['printed_sha256'] = '0'*64
            else: proof['story_route_extension']['data']['initial_button']['key'] = 'answer.no'
            write(p/'inputs.json', config); write(p/'provenance.json', proof)
            try: check(p)
            except AssertionError: rejected.append(name)
            else: raise AssertionError(name)
    with tempfile.TemporaryDirectory(dir=output, prefix='rebuild-') as directory:
        p = Path(directory); generate(root, p)
        assert {f.name: sha(f) for f in (p/'inputs-r2').iterdir()} == {f.name: sha(f) for f in source.iterdir()}
    write(output/'guards.json', dict(rejected=rejected, rebuilt_files=len(list(source.iterdir()))))


def review(root, output):
    from PIL import Image
    from ui_list_live_check import read as receipt
    assert read(output/'main-check-r6.json')['all_submitted_pixels_equal_expected']
    a, b = [receipt(output/f'main-{lang}-r1/receipt.json') for lang in ('en', 'zh')]
    entries = [e['detail']['page'] for e in b['list_events'] if e['Kind'] == 'paragraph-before-glyph']
    assert [e['Key'] for e in entries] == list(KEYS)
    assert not any(e['Kind'] == 'unknown-paragraph-original' for e in b['list_events'])
    assert entries[3]['Components'] == list(KEYS[2:4]) and entries[3]['ComponentColors'] == [7, 3]
    assert entries[-1]['Components'] == [KEYS[-1]]
    assert b['reader_seen'] == [] and not b['reader_events'] and not b['reader_ui_events']
    samples = []
    for key in KEYS:
        frames = [f for f, state in zip(b['frames'], b['list_frames']) if not f['held']
            and state.get('paragraph') and key in state['paragraph']['Components']]
        assert frames, ('paragraph invisible', key)
        samples.append(dict(key=key, samples=len(frames), first_file=frames[0]['File'], last_file=frames[-1]['File']))
    proof = read(output/'inputs-r2/provenance.json')['story_route_extension']
    references = {}
    for w in proof['data']['prompt_witnesses']:
        x, y, width, height = w['native_rect']
        rect = (x*2, y*2, (x+width)*2, (y+height)*2)
        with Image.open(output/'observe-r2'/(w['printed']+'.png')) as image:
            assert image.size == (320, 200)
            pixels = image.convert('RGB').resize((640, 400), Image.Resampling.NEAREST).crop(rect).tobytes()
        identity = w['key'], rect
        if identity in references: assert references[identity]['pixels'] == pixels
        else: references[identity] = dict(pixels=pixels, first=w['field_entry'], matches=0)
    cached = {}
    def crop(lang, file, rect):
        token = lang, file, rect
        if token not in cached:
            with Image.open(output/f'main-{lang}-r1'/file) as image:
                cached[token] = image.convert('RGB').crop(rect).tobytes()
        return cached[token]
    for original, translated, state in zip(a['frames'], b['frames'], b['list_frames'], strict=True):
        if original['held'] or translated['held']: continue
        for (key, rect), ref in references.items():
            if original['step'] <= ref['first'] or crop('en', original['File'], rect) != ref['pixels']: continue
            # 原文 GPU 仍有完整提示時，已辨識提示必須保留中文，不只讓覆層模型自洽。
            assert any(w['Key'] == key for w in state.get('words') or []), ('English prompt exposed', key, original['step'])
            assert crop('zh', translated['File'], rect) != ref['pixels']
            ref['matches'] += 1
    assert all(ref['matches'] for ref in references.values())
    write(output/'visibility-review.json', dict(paragraphs=samples, mixed_colors=[7, 3],
        prompt_native_pixel_checks=[dict(key=key, rect=rect, samples=ref['matches']) for (key, rect), ref in references.items()],
        final_components=b['list_frames'][-1]['paragraph']['Components'], reader_seen=[],
        limits='四頁正常出航與殘骸提問；原快照已畫好而未重印的文字不作本段全畫面中文證據。'))


def ashore(root, output):
    a, b = [read(output/f'ashore-{mode}-r2/receipt.json') for mode in ('observe', 'control')]
    main = read(output/'observe-r2/receipt.json')
    for key in ('source_commit', 'go_version', 'exe_sha256', 'probe_sha256', 'state_sha256', 'request_sha256', 'request', 'checkpoints'):
        assert a[key] == b[key], key
    for key in ('source_commit', 'go_version', 'exe_sha256', 'probe_sha256'): assert a[key] == main[key]
    assert a['observe'] and not b['observe'] and len(a['checkpoints']) == 2
    assert a['state_sha256'] == sha(output/'control-r2/final.state')
    assert a['request_sha256'] == sha(output/'ashore-request-r2.json')
    assert not any(v for k, v in a.items() if k.startswith('pending'))
    for cp in a['checkpoints']:
        assert not cp['file_writes'] and not cp['unimplemented']
        for suffix in ('.idx', '.png'):
            name = cp['label']+suffix
            assert sha(output/'ashore-observe-r2'/name) == sha(output/'ashore-control-r2'/name)
    assert sha(output/'ashore-observe-r2/final.state') == sha(output/'ashore-control-r2/final.state')
    assert a['checkpoints'][:1] == read(output/'ashore-observe-r1/receipt.json')['checkpoints']
    write(output/'ashore-check.json', dict(checkpoints=2, source_sha256=sha(output/'ashore-observe-r2/receipt.json'),
        final_state_sha256=sha(output/'ashore-control-r2/final.state'), normal_gui_conformance=False))
    c, d = [read(output/f'ashore-{mode}-r3/receipt.json') for mode in ('observe', 'control')]
    for key in ('source_commit', 'go_version', 'exe_sha256', 'probe_sha256', 'state_sha256', 'request_sha256', 'request', 'checkpoints'):
        assert c[key] == d[key], key
    assert c['observe'] and not d['observe'] and len(c['checkpoints']) == 3
    assert c['state_sha256'] == a['state_sha256'] and c['probe_sha256'] == a['probe_sha256']
    assert c['request_sha256'] == sha(output/'ashore-request-r3.json')
    assert c['checkpoints'][:2] == a['checkpoints'] and c['paragraphs'] == a['paragraphs']
    assert not any(v for k, v in c.items() if k.startswith('pending'))
    for cp in c['checkpoints']:
        assert not cp['file_writes'] and not cp['unimplemented']
        for suffix in ('.idx', '.png'):
            name = cp['label']+suffix
            assert sha(output/'ashore-observe-r3'/name) == sha(output/'ashore-control-r3'/name)
    assert sha(output/'ashore-observe-r3/final.state') == sha(output/'ashore-control-r3/final.state')
    write(output/'cave-check.json', dict(checkpoints=3, source_sha256=sha(output/'ashore-observe-r3/receipt.json'),
        final_state_sha256=sha(output/'ashore-control-r3/final.state'), normal_gui_conformance=False,
        limits='Return 後取得探索選單，不由動作標籤推定已載入 chunk 5。'))


def coverage(root, output):
    texts = root/'workplace/translation'
    formal = catalog(texts/'zh-TW.tsv')
    current = catalog(output/'inputs-r2/zh-TW.tsv')
    wanted = {k for k in formal if k.startswith('ecl.')}
    gap = wanted-current.keys()
    groups = read(texts/'passage-candidates.json')['groups']
    fragments = {f['key'] for g in groups for s in g['sources'] for f in s['fragments']}
    registry_path = root/'workplace/probe/passage-chain-20261024/chain-inputs-r1/registry.json'
    registry = read(registry_path)
    registered = {f['key'] for occurrence in registry['occurrences'] for f in occurrence['fragments']}
    assert len(wanted) == 6562 and len(gap) == 810 and gap <= fragments
    assert not registry['runtime_integrated'] and not registry['normal_chain_verified']
    write(output/'catalog-gap-audit.json', dict(formal_ecl_keys=len(wanted), direct_runtime_ecl_keys=len(wanted)-len(gap),
        direct_gap=len(gap), all_gap_is_passage_fragment=True, groups=len(groups),
        registry_occurrences=len(registry['occurrences']), registry_keys=len({o['key'] for o in registry['occurrences']}),
        gap_keys_in_registry=len(gap & registered), registry_chunks=sorted({o['chunk'] for o in registry['occurrences']}),
        excluded_reasons=dict(Counter(o.get('reason', 'unspecified') for o in registry['excluded'])),
        registry_integrated=False, normal_chain_verified=False, gap_keys=sorted(gap),
        source_sha256=dict(formal_zh=sha(texts/'zh-TW.tsv'), runtime_zh=sha(output/'inputs-r2/zh-TW.tsv'),
            candidates=sha(texts/'passage-candidates.json'), registry=sha(registry_path)),
        limits='810 為尚未直接接入的片段鍵，不能以整句 registry 或來源候選筆數宣稱玩家流程已完成。'))


def evidence(root, output):
    for name in ('native-check.json', 'main-check-r6.json', 'guards.json', 'visibility-review.json', 'ashore-check.json', 'cave-check.json', 'payload-equality.json', 'initial-transaction.json', 'footer-phase-audit.json', 'catalog-gap-audit.json'):
        assert (output/name).is_file(), name
    names = {'story_route_inputs.py', 'ui_list_live_check.py', 'research_storage.py'}
    pending = list(names)
    while pending:
        name = pending.pop()
        for node in ast.walk(ast.parse((root/'tools'/name).read_text())):
            modules = [node.module] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names] if isinstance(node, ast.Import) else []
            for module in modules:
                candidate = (module or '').split('.')[0]+'.py'
                if candidate not in names and (root/'tools'/candidate).is_file():
                    names.add(candidate); pending.append(candidate)
    program = root/'workplace/probe/captain-dialogue-20261025/programs-r1'
    names.update(p.name for p in program.glob('*.go'))
    names.update(('oracle_video_observer.go', 'oracle_input_modifier.go'))
    snapshots = output/'tool-snapshots'
    assert not snapshots.exists(); snapshots.mkdir()
    for name in sorted(names): shutil.copyfile(root/'tools'/name, snapshots/name)
    probe = root/'workplace/probe'
    sources = list((probe/BASE).iterdir())
    sources.extend(probe/'journal59-route-20261025'/n for n in ('evidence.json', 'control-r2/final.state', 'depart-observe-r2/receipt.json'))
    sources.extend(probe/'captain-dialogue-20261025'/n for n in ('programs-r1/ui-list-live', 'evidence.json'))
    sources.append(probe/'combat-aim-route-20261024/programs-r3/ui-context-probe')
    sources.extend(root/'workplace/input/dos/drkqueen'/n for n in ('DQK.EXE', 'DISK3/ECL.GLB'))
    sources.extend(root/'workplace/translation'/n for n in ('en.tsv', 'zh-TW.tsv', 'catalog.json', 'glossary.tsv', 'glossary-additions.tsv'))
    sources.extend((root/'workplace/translation/passage-candidates.json', probe/'passage-chain-20261024/chain-inputs-r1/registry.json'))
    def info(p):
        stat = p.stat(); assert (stat.st_uid, stat.st_gid) == (1000, 1000)
        return dict(bytes=stat.st_size, sha256=sha(p), uid=stat.st_uid, gid=stat.st_gid)
    assert not (output/'evidence.json').exists()
    write(output/'evidence.json', dict(draft=True, runtime_integrated=False,
        rights='原版、全文、字模與畫格只留本機', engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        effective=dict(inputs='inputs-r2', source='observe/control-r2', gpu='main-en/zh-r1',
            program='captain-dialogue-20261025/programs-r1', checks='main-check-r6.json', next_state='control-r2/final.state',
            limits='出航至邀請上岸的四頁；上岸後僅原版來源，完整中文及正式入口未完成。'),
        tools={name: sha(root/'tools'/name) for name in sorted(names)}, sources={str(p): info(p) for p in sources},
        artifacts={str(p.relative_to(output)): info(p) for p in sorted(output.rglob('*')) if p.is_file()}))


if __name__ == '__main__':
    mode, project, directory = sys.argv[1:]
    root, output = Path(project), Path(directory)
    if mode == 'native': native(root, output)
    elif mode == 'prepare':
        native(root, output); generate(root, output)
    elif mode == 'guards': guards(root, output)
    elif mode == 'review': review(root, output)
    elif mode == 'ashore': ashore(root, output)
    elif mode == 'coverage': coverage(root, output)
    elif mode == 'evidence': evidence(root, output)
    elif mode == 'audit':
        from combat_finish_inputs import audit
        audit(root, output)
    else: raise ValueError(mode)
