"""正常手札引用的 DRAFT 路線輸入，沿用譯文、字模與閱讀元件。"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

from literal_catalog import catalog, digest, read, sha, windows

BASE = 'captain-dialogue-20261025/inputs-r1'
STUDY = 'journal59-route-20261025'
SOURCE = STUDY+'/observe-r2/receipt.json'
STATE = 'captain-dialogue-20261025/control-r2/final.state'
KEY = 'message.2afd4692509810066bcb'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def native(root, output):
    a, b = [read(output/f'{mode}-r2/receipt.json') for mode in ('observe', 'control')]
    for key in ('source_commit', 'go_version', 'exe_sha256', 'probe_sha256', 'state_sha256', 'request_sha256', 'request', 'checkpoints'):
        assert a[key] == b[key], key
    assert a['observe'] and not b['observe'] and len(a['checkpoints']) == 14
    assert a['source_commit'] == 'f79eab6db8c64a524a06535e53e5d32b0bbcf7c8'
    assert a['exe_sha256'] == '3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
    probe = root/'workplace/probe'
    assert a['probe_sha256'] == sha(probe/'combat-aim-route-20261024/programs-r3/ui-context-probe')
    assert a['state_sha256'] == sha(probe/STATE)
    assert a['request_sha256'] == sha(output/'request-r2.json')
    assert not any(v for key, v in a.items() if key.startswith('pending'))
    old = read(output/'observe-r1/receipt.json')
    for key in ('calls', 'paragraphs', 'wrappers', 'fill_events', 'display_changes', 'menus', 'list_events'):
        assert a[key] == old[key], key
    for cp in a['checkpoints']:
        assert not cp['file_writes'] and not cp['unimplemented']
        for suffix in ('.idx', '.png'):
            name = cp['label']+suffix
            assert sha(output/'observe-r2'/name) == sha(output/'control-r2'/name)
    final = sha(output/'control-r2/final.state')
    assert final == sha(output/'observe-r2/final.state') == sha(output/'control-r1/final.state')
    write(output/'native-check.json', dict(checkpoints=14, source_path=SOURCE,
        source_sha256=sha(output/'observe-r2/receipt.json'), final_state_sha256=final))


def derive(probe):
    base = probe/BASE
    config = copy.deepcopy(read(base/'inputs.json'))
    trace = read(probe/SOURCE)
    en = catalog(base/'en.tsv')
    first, following = trace['paragraphs']
    assert first['caller'] == dict(Seg=0x26b4, Off=0x3320)
    binding, = [p for p in config['Paragraphs'] if p['Key'] == KEY]
    for p, b in ((first, binding),):
        assert p['source']['nul_terminated'] and p['source']['text'] == en[b['Key']]
        assert p['caller'] == b['Caller'] and p['native_box'] == b['NativeBox']
        assert all(p[k] == b[v] for k, v in (('foreground', 'Foreground'), ('background', 'Background'), ('clear', 'Clear')))
    assert binding['JournalEntry'] == 59 and first['return_step'] < following['step']
    assert following['caller'] == dict(Seg=0x26b4, Off=0x1d81) and following['clear'] == 1
    next_bindings = [p for p in config['Paragraphs'] if en[p['Key']] == following['source']['text']
        and p['Caller'] == following['caller'] and p['Foreground'] == following['foreground'] and p['Clear'] == following['clear']]
    assert len(next_bindings) == 1 and not next_bindings[0].get('JournalEntry')
    reader = catalog(base/'reader.zh-TW.tsv')
    assert reader['journal.59.title'] and reader['journal.59.body']
    request = read(probe/STUDY/'request-r2.json')
    assert request == trace['request'] and [(a['at'], a['kind'], a['key']) for a in request['actions'] if a['key']] == [
        (5347000000, 'named', 'Return'), (5427000000, 'named', 'Return')]
    controls = dict(native_request_sha256=sha(probe/STUDY/'request-r2.json'), controls=[
        dict(at=at, key=key) for at in (5426000000, 5466000000)
        for key in ('F5', 'Right', 'Left', 'PgDn', 'PgUp', 'Esc')])
    menu, = [m for m in trace['menus'] if m['Signature'] == '9e69584e14170e3cf1b339ed08ba397a86557930ab3965cb83af74ed87490ea3']
    assert menu['Count'] == 3 and [b['SourceHex'] for b in menu['Buttons']] == ['596573', '4e6f']
    assert menu['Signature'] not in config['Menus']
    choice_fields = []
    for button in menu['Buttons']:
        key = 'trade.ui.'+button['SHA256'][:20]
        assert en[key].encode().hex() == button['SourceHex']
        call, = [c for c in trace['calls'] if c['caller'] == dict(Seg=0xceb, Off=0x1be)
            and c['format']['nul_terminated'] and c['format']['text'] == en[key] and c['menu_index'] >= 0
            and trace['menus'][c['menu_index']]['Signature'] == menu['Signature']]
        raw_y, raw_x, color = call['stack'][2:5]
        # 本表原生按鈕頂端 y=188，原版列印入口的字形列為 y=189。
        assert raw_x == (button['RawX']-8000)*2 and (button['RawY']-8000)*2 == 188 and raw_y == 189
        assert color == 0x87 and call['step'] < call['first_glyph'] < call['return_step']
        choice_fields.append(dict(Pane='menu', Group='footer', Key=key, Start=0, Length=len(en[key]),
            MenuSignature=menu['Signature'], RawX=raw_x, RawY=raw_y, Caller=call['caller'],
            FormatSHA256=button['SHA256'], SHA256=button['SHA256']))
    config['Fields'].extend(choice_fields)
    config['Menus'][menu['Signature']] = 'confirm'
    config['fine_windows'] = windows(trace)
    prompt_witnesses = []
    native_position = lambda v: v if v < 400 else (v-8000)*2
    def crop(checkpoint, rect):
        path = probe/STUDY/'observe-r2'/(checkpoint['label']+'.idx')
        raw = path.read_bytes()
        assert sha(path) == checkpoint['indexed_sha256']
        x, y, width, height = rect
        return b''.join(raw[row*320+x:row*320+x+width] for row in range(y, y+height))
    for field in config['Fields']:
        if field.get('UpperCaller') != dict(Seg=0xceb, Off=0x4bd): continue
        calls = [c for c in trace['calls'] if c['caller'] == field['Caller']
            and c['format']['nul_terminated'] and digest(c['format']['text']) == field['FormatSHA256']
            and c['stack'][2:4] == [field['RawY'], field['RawX']] and c['wrapper_index'] >= 0
            and trace['wrappers'][c['wrapper_index']]['caller'] == field['UpperCaller']
            and c['vararg_1_candidate']['text'][field['Start']:field['Start']+field['Length']] == en[field['Key']]]
        assert len(calls) == 1
        call, = calls
        rect = [native_position(field['RawX'])+field['Start']*8, native_position(field['RawY']), field['Length']*8, 8]
        before = max((cp for cp in trace['checkpoints'] if cp['step'] < call['step']), key=lambda cp: cp['step'])
        printed = min((cp for cp in trace['checkpoints'] if call['return_step'] < cp['step'] < following['step']), key=lambda cp: cp['step'])
        old_pixels, printed_pixels = crop(before, rect), crop(printed, rect)
        assert old_pixels != printed_pixels and set(printed_pixels) == {0, 7}
        restored = next(cp for cp in trace['checkpoints'] if cp['step'] > following['return_step'] and crop(cp, rect) == old_pixels)
        prompt_witnesses.append(dict(key=field['Key'], field_entry=call['step'], native_rect=rect,
            before=before['label'], printed=printed['label'], restored=restored['label'], restored_step=restored['step'],
            printed_sha256=hashlib.sha256(printed_pixels).hexdigest(),
            background_sha256=hashlib.sha256(old_pixels).hexdigest()))
    assert len(prompt_witnesses) == 2
    data = dict(records=[], fields=choice_fields, menu=menu, binding=binding, next_binding=next_bindings[0], controls=controls,
        prompt_witnesses=prompt_witnesses,
        page_validation=dict(source_path=SOURCE, source_sha256=sha(probe/SOURCE)))
    return config, data


def generate(root, output):
    probe = root/'workplace/probe'
    config, data = derive(probe)
    base = probe/BASE
    target = output/'inputs-r3'
    shutil.copytree(base, target)
    assert not (target/'reader-controls.json').exists()
    proof = read(base/'provenance.json')
    proof['reader_route_extension'] = dict(base=BASE, base_files={p.name: sha(p) for p in base.iterdir()},
        source_path=SOURCE, source_sha256=sha(probe/SOURCE), data=data)
    write(target/'inputs.json', config)
    write(target/'provenance.json', proof)
    write(target/'reader-controls.json', data['controls'])


def check_sources(inputs, config, proof, en, zh, glyphs):
    probe = inputs.parent.parent
    base = probe/BASE
    extension = proof['reader_route_extension']
    assert extension['base'] == BASE and extension['source_path'] == SOURCE
    assert extension['base_files'] == {p.name: sha(p) for p in base.iterdir()}
    assert extension['source_sha256'] == sha(probe/SOURCE)
    expected, data = derive(probe)
    assert config == expected and extension['data'] == data, 'reader route source'
    assert read(inputs/'reader-controls.json') == data['controls'], 'reader route controls'
    parent = read(base/'provenance.json')
    assert {k: v for k, v in proof.items() if k != 'reader_route_extension'} == parent
    for name in set(extension['base_files'])-{'inputs.json', 'provenance.json'}:
        assert (inputs/name).read_bytes() == (base/name).read_bytes(), name
    assert en == catalog(base/'en.tsv') and zh == catalog(base/'zh-TW.tsv')
    assert glyphs == read(base/'glyphs-16.json')
    return base, read(base/'inputs.json'), parent, en, zh, glyphs


def guards(root, output):
    source = output/'inputs-r3'
    def check(p):
        check_sources(p, read(p/'inputs.json'), read(p/'provenance.json'), catalog(p/'en.tsv'), catalog(p/'zh-TW.tsv'), read(p/'glyphs-16.json'))
    check(source)
    rejected = []
    for name in ('ordinal', 'caller', 'controls', 'reader', 'translation', 'glyph', 'prompt-witness', 'choice-position', 'choice-menu'):
        with tempfile.TemporaryDirectory(dir=output, prefix='guard-') as directory:
            p = Path(directory)
            shutil.copytree(source, p, dirs_exist_ok=True)
            config = read(p/'inputs.json')
            binding, = [b for b in config['Paragraphs'] if b['Key'] == KEY]
            if name == 'ordinal': binding['JournalEntry'] = 58
            elif name == 'caller': binding['Caller']['Off'] += 1
            elif name == 'controls':
                controls = read(p/'reader-controls.json'); controls['controls'][0]['at'] += 1
                write(p/'reader-controls.json', controls)
            elif name == 'choice-position': config['Fields'][-1]['RawX'] += 8
            elif name == 'choice-menu': config['Menus'].pop(config['Fields'][-1]['MenuSignature'])
            elif name in ('reader', 'translation'):
                target = p/('reader.zh-TW.tsv' if name == 'reader' else 'zh-TW.tsv')
                target.write_text(target.read_text()+'bad\tx\n')
            elif name == 'glyph':
                g = read(p/'glyphs-16.json'); g['glyphs'].pop(next(iter(g['glyphs'])))
                write(p/'glyphs-16.json', g)
            write(p/'inputs.json', config)
            proof = read(p/'provenance.json'); proof['reader_route_extension']['data']['binding'] = binding
            if name == 'prompt-witness':
                proof['reader_route_extension']['data']['prompt_witnesses'][0]['printed_sha256'] = '0'*64
            write(p/'provenance.json', proof)
            try: check(p)
            except AssertionError: rejected.append(name)
            else: raise AssertionError(name)
    with tempfile.TemporaryDirectory(dir=output, prefix='rebuild-') as directory:
        p = Path(directory)
        generate(root, p)
        assert {f.name: sha(f) for f in (p/'inputs-r3').iterdir()} == {f.name: sha(f) for f in source.iterdir()}
    write(output/'guards.json', dict(rejected=rejected, rebuilt_files=len(list(source.iterdir()))))


def review(root, output):
    from ui_list_live_check import read as receipt
    assert read(output/'main-check-r3.json')['all_submitted_pixels_equal_expected']
    en, zh = [receipt(output/f'main-{lang}-r3/receipt.json') for lang in ('en', 'zh')]
    assert len(en['frames']) == len(zh['frames'])
    assert zh['reader_seen'] == [59] and zh['final_reader'] is None and zh['final_auto_reader'] is None
    assert [(e['action'], e.get('entry', e.get('page', {}).get('Entry'))) for e in zh['reader_events']] == [('open', 59), ('close', 59)]
    assert len(zh['reader_ui_events']) == 12 and not zh['reader_probe']
    visible = []
    for mode in ('', 'browse'):
        frames = [f for f, state in zip(zh['frames'], zh['list_frames']) if not f['held']
            and state.get('reader') and state['reader']['Entry'] == 59 and state['reader'].get('Mode', '') == mode]
        assert frames, ('reader invisible', mode)
        visible.append(dict(mode=mode, samples=len(frames), first_file=frames[0]['File'], last_file=frames[-1]['File']))
    for event in zh['reader_ui_events']:
        assert event['source'] == 'script' and not event.get('ignored')
        page = event.get('page')
        if page:
            assert page['Entry'] == 59 and page.get('Number', 1) == page.get('Count', 1) == 1
    after = [f for f, state in zip(zh['frames'], zh['list_frames']) if not f['held']
        and state.get('paragraph') and state['paragraph']['Key'] == 'ecl.0e74ee34950715510a57']
    assert after and zh['list_frames'][-1]['reader'] is None
    data = read(output/'inputs-r3/provenance.json')['reader_route_extension']['data']
    choices = []
    for field in data['fields']:
        frames = [f for f, state in zip(zh['frames'], zh['list_frames']) if not f['held']
            and any(w['Key'] == field['Key'] for w in state.get('words') or [])]
        assert frames, ('choice invisible', field['Key'])
        choices.append(dict(key=field['Key'], samples=len(frames), first_file=frames[0]['File']))
    write(output/'visibility-review.json', dict(reader=visible, controls=12, seen=[59], closed=True,
        choices=choices,
        next_paragraph_visible=len(after), next_paragraph_file=after[-1]['File'],
        limits='正常引用及腳本化前端查閱；不宣稱實體鍵盤或其餘手札正常引用完成。'))


def departure(root, output):
    a, b = [read(output/f'depart-{mode}-r2/receipt.json') for mode in ('observe', 'control')]
    main = read(output/'observe-r2/receipt.json')
    for key in ('source_commit', 'go_version', 'exe_sha256', 'probe_sha256', 'state_sha256', 'request_sha256', 'request', 'checkpoints'):
        assert a[key] == b[key], key
    for key in ('source_commit', 'go_version', 'exe_sha256', 'probe_sha256'):
        assert a[key] == main[key]
    assert a['observe'] and not b['observe'] and len(a['checkpoints']) == 2
    assert a['state_sha256'] == sha(output/'control-r2/final.state')
    assert a['request_sha256'] == sha(output/'depart-request-r2.json')
    assert not any(v for k, v in a.items() if k.startswith('pending'))
    for cp in a['checkpoints']:
        assert not cp['file_writes'] and not cp['unimplemented']
        for suffix in ('.idx', '.png'):
            name = cp['label']+suffix
            assert sha(output/'depart-observe-r2'/name) == sha(output/'depart-control-r2'/name)
    assert sha(output/'depart-observe-r2/final.state') == sha(output/'depart-control-r2/final.state')
    old = read(output/'depart-observe-r1/receipt.json')
    assert a['checkpoints'][:1] == old['checkpoints']
    write(output/'departure-check.json', dict(checkpoints=2, source_sha256=sha(output/'depart-observe-r2/receipt.json'),
        final_state_sha256=sha(output/'depart-control-r2/final.state'), normal_gui_conformance=False))


def evidence(root, output):
    for name in ('native-check.json', 'main-check-r3.json', 'guards.json', 'visibility-review.json', 'departure-check.json', 'payload-equality.json', 'choice-change.json'):
        assert (output/name).is_file(), name
    names = {'journal_route_inputs.py', 'ui_list_live_check.py', 'research_storage.py'}
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
    assert not snapshots.exists()
    snapshots.mkdir()
    for name in sorted(names):
        shutil.copyfile(root/'tools'/name, snapshots/name)
    probe = root/'workplace/probe'
    sources = list((probe/BASE).iterdir())
    sources.extend(probe/'captain-dialogue-20261025'/n for n in ('evidence.json', 'programs-r1/ui-list-live', 'control-r2/final.state'))
    sources.extend(probe/'combat-aim-route-20261024'/n for n in ('programs-r3/ui-context-probe',))
    sources.extend(root/'workplace/input/dos/drkqueen'/n for n in ('DQK.EXE', 'DISK3/ECL.GLB'))
    def info(p):
        stat = p.stat()
        assert (stat.st_uid, stat.st_gid) == (1000, 1000)
        return dict(bytes=stat.st_size, sha256=sha(p), uid=stat.st_uid, gid=stat.st_gid)
    assert not (output/'evidence.json').exists()
    write(output/'evidence.json', dict(draft=True, runtime_integrated=False,
        rights='原版、全文、字模與畫格只留本機', engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        effective=dict(inputs='inputs-r3', source='observe/control-r2', gpu='main-en/zh-r3',
            program='captain-dialogue-20261025/programs-r1', checks='main-check-r3.json', next_state='control-r2/final.state',
            limits='正常引用 59 與登船提問；接受登船之後只有原版來源。'),
        tools={name: sha(root/'tools'/name) for name in sorted(names)},
        sources={str(p): info(p) for p in sources},
        artifacts={str(p.relative_to(output)): info(p) for p in sorted(output.rglob('*')) if p.is_file()}))


if __name__ == '__main__':
    mode, project, directory = sys.argv[1:]
    root, output = Path(project), Path(directory)
    if mode == 'native': native(root, output)
    elif mode == 'prepare':
        native(root, output)
        generate(root, output)
    elif mode == 'guards': guards(root, output)
    elif mode == 'review': review(root, output)
    elif mode == 'departure': departure(root, output)
    elif mode == 'evidence': evidence(root, output)
    elif mode == 'audit':
        from combat_finish_inputs import audit
        audit(root, output)
    else: raise ValueError(mode)
