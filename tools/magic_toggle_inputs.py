"""原版自動施法切換的 DRAFT 呈現資料；來源、復原像素及譯文分別核對。"""
import copy
import ast
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile

from combat_rounds_inputs import hud_records
from literal_catalog import catalog, digest, read, sha, windows
from spell_route_inputs import write
from text_catalog import write_tsv

BASE = 'combat-spells-route-20261024/inputs-r3'
STUDY = 'combat-aim-route-20261024'
SOURCE = STUDY + '/observe-r13/receipt.json'
SIGNATURE = 'a32c634dc8b64a3bcbade4cd694c0cf00b0bd586c70e3091093db7c521eb266f'
STATUS_SIGNATURE = 'b891f7b3c26270165eaf8756b7b4d59704d7cf11b45fccb5cdae13dd2468ae6b'
FORMAL = ('en.tsv', 'zh-TW.tsv', 'catalog.json', 'glossary.tsv', 'glossary-additions.tsv')


def native(root, output):
    a, b = [read(output / f'{m}-r13/receipt.json') for m in ('observe', 'control')]
    assert a['observe'] and not b['observe']
    for key in ('source_commit', 'go_version', 'exe_sha256', 'state_sha256',
                'request_sha256', 'probe_sha256', 'request', 'checkpoints'):
        assert a[key] == b[key], key
    assert a['exe_sha256'] == '3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
    assert a['source_commit'] == 'f79eab6db8c64a524a06535e53e5d32b0bbcf7c8'
    assert a['probe_sha256'] == sha(output / 'programs-r3/ui-context-probe')
    assert a['request_sha256'] == sha(output / 'request-r12.json')
    assert len(a['checkpoints']) == 16
    assert not any(v for k,v in a.items() if k.startswith('pending'))
    for cp in a['checkpoints']:
        assert not cp['file_writes'] and not cp['unimplemented']
        for suffix in ('.png', '.idx'):
            name = cp['label'] + suffix
            assert sha(output / 'observe-r13' / name) == sha(output / 'control-r13' / name)
    assert sha(output / 'observe-r13/final.state') == sha(output / 'control-r13/final.state')
    assert a['checkpoints'] == read(output / 'observe-r12/receipt.json')['checkpoints']
    write(output / 'native-check-r2.json', dict(checkpoints=16, source_sha256=sha(output / 'observe-r13/receipt.json')))


def derive(probe, texts):
    old = read(probe / BASE / 'inputs.json')
    config = copy.deepcopy(old)
    en, zh = catalog(texts / 'en.tsv'), catalog(texts / 'zh-TW.tsv')
    trace = read(probe / SOURCE)
    assert old['Menus'][SIGNATURE] == 'combat'
    assert {m['Signature'] for m in trace['menus']} == {SIGNATURE}
    fields, aliases, witnesses = [], {}, []
    footer_baseline = None
    selected = [(i,w) for i,w in enumerate(trace['wrappers'])
                if w['caller'] == dict(Seg=0x88e, Off=0x1560)]
    assert len(selected) == 3
    for label, (index, wrapper) in zip(('magic-on', 'magic-off', 'magic-on-again'), selected):
        assert wrapper['menu_valid'] and wrapper['menu_snapshot']['Count'] == 19
        assert wrapper['menu_snapshot']['Signature'] == STATUS_SIGNATURE
        source = wrapper['vararg_1_candidate']['text']
        key = 'ui.' + digest(source)[:20]
        assert key in ('ui.3dd44f96ef1d6b028dfe', 'ui.25fd2397b3b79835861d')
        assert source == en[key] and key in zh
        assert wrapper['format']['text'] == '%s' and wrapper['vararg_1_candidate']['nul_terminated']
        calls = [c for c in trace['calls'] if c['wrapper_index'] == index
                 and c['format']['text'] == '%s' and c['vararg_1_candidate']['text'] == source]
        assert len(calls) == 1
        call = calls[0]
        assert call['caller'] == dict(Seg=0xb72, Off=0x27c)
        assert call['stack'][2:5] == [189, 8004, 0x8f]
        assert wrapper['step'] < call['step'] < call['first_glyph'] < call['return_step'] < wrapper['return_step']
        field = dict(Pane='callsite', Group='footer', Key=key, Start=0, Length=len(source),
            RawX=8004, RawY=189, Caller=call['caller'], UpperCaller=wrapper['caller'],
            UpperNative=[0,192], UpperFormatSHA256=digest('%s'), FormatSHA256=digest('%s'),
            Color=0x8f, SHA256=digest(source), MenuSignature=STATUS_SIGNATURE)
        if field not in config['Fields']:
            config['Fields'].append(field)
            fields.append(field)
        aliases[key] = dict(key=key, formal_key=key, source=source)
        rect = [8,189,len(source)*8,8]
        pixels, paths, steps = {}, {}, {}
        for kind in ('before', 'ready', 'restored'):
            cp, = [c for c in trace['checkpoints'] if c['label'] == label + '-' + kind]
            path = Path(SOURCE).parent / cp['indexed_file']
            raw = (probe / path).read_bytes()
            assert sha(probe / path) == cp['indexed_sha256']
            x,y,w,h = rect
            pixels[kind] = b''.join(raw[row*320+x:row*320+x+w] for row in range(y,y+h))
            paths[kind], steps[kind] = str(path), cp['step']
        assert pixels['before'] == pixels['restored'] and pixels['before'] != pixels['ready']
        def footer(path):
            raw = (probe / path).read_bytes()
            return b''.join(raw[row*320+8:row*320+312] for row in range(176,200))
        before_footer, ready_footer = footer(paths['before']), footer(paths['ready'])
        if footer_baseline is None:footer_baseline = before_footer
        assert before_footer == footer_baseline
        assert before_footer[:11*304] == ready_footer[:11*304], 'original top button row must remain erased'
        assert steps['before'] == wrapper['step'] and steps['ready'] == wrapper['return_step']
        assert len(call['video_pages']) == 1
        witnesses.append(dict(key=key, source=source, entry=wrapper['step'], field_entry=call['step'],
            returned=wrapper['return_step'], restored_by=steps['restored'], rect=rect,
            before_index=paths['before'], ready_index=paths['ready'], restored_index=paths['restored'],
            before_sha256=hashlib.sha256(pixels['before']).hexdigest(), ready_sha256=hashlib.sha256(pixels['ready']).hexdigest(),
            erased_footer_rect=[8,176,304,24], erased_footer_sha256=hashlib.sha256(before_footer).hexdigest()))
    assert len(fields) == len(aliases) == 2
    config['fine_windows'] = windows(trace)
    return config, dict(fields=fields, aliases=list(aliases.values()), notices=witnesses,
        records=hud_records(trace, config['HUDParagraphs'], catalog(probe / BASE / 'en.tsv')))


def generate(root, target):
    probe, texts = root / 'workplace/probe', root / 'workplace/translation'
    base = probe / BASE
    config, data = derive(probe, texts)
    en, zh, font = [catalog(base / n) for n in ('en.tsv', 'zh-TW.tsv', 'font-zh-TW.tsv')]
    formal = catalog(texts / 'zh-TW.tsv')
    for a in data['aliases']:
        assert a['key'] not in en
        en[a['key']], zh[a['key']], font[a['key']] = a['source'], formal[a['formal_key']], formal[a['formal_key']]
    glyphs = read(base / 'glyphs-16.json')
    assert not (set(''.join(font.values())) - set('\r\n\t') - set(glyphs['glyphs'])), 'new glyphs required'
    shutil.copytree(base, target)
    proof = read(base / 'provenance.json')
    proof['magic_toggle_extension'] = dict(base=BASE, base_files={p.name:sha(p) for p in base.iterdir()},
        source_path=SOURCE, source_sha256=sha(probe / SOURCE), data=data,
        page_validation=dict(source_path=SOURCE, source_sha256=sha(probe / SOURCE)),
        formal_files={n:sha(texts / n) for n in FORMAL})
    for name, values in (('en.tsv',en), ('zh-TW.tsv',zh), ('font-zh-TW.tsv',font)):
        write_tsv(target / name, ['key','text'], values.items())
    write(target / 'inputs.json',config)
    write(target / 'provenance.json',proof)


def check_sources(inputs, config, provenance, en, zh, glyphs):
    root, texts = inputs.parent.parent, Path('/catalogs')
    base = root / BASE
    proof = provenance['magic_toggle_extension']
    assert proof['base'] == BASE and proof['source_path'] == SOURCE
    assert proof['base_files'] == {p.name:sha(p) for p in base.iterdir()}
    assert proof['source_sha256'] == sha(root / SOURCE)
    assert proof['page_validation'] == dict(source_path=SOURCE, source_sha256=sha(root / SOURCE))
    assert proof['formal_files'] == {n:sha(texts / n) for n in FORMAL}
    expected, data = derive(root, texts)
    assert config == expected, 'magic toggle config'
    assert proof['data'] == data, 'magic toggle proof'
    parent = read(base / 'provenance.json')
    assert {k:v for k,v in provenance.items() if k != 'magic_toggle_extension'} == parent
    old_en, old_zh, old_font = [catalog(base / n) for n in ('en.tsv','zh-TW.tsv','font-zh-TW.tsv')]
    formal = catalog(texts / 'zh-TW.tsv')
    assert en == dict(old_en, **{a['key']:a['source'] for a in data['aliases']})
    extra = {a['key']:formal[a['formal_key']] for a in data['aliases']}
    assert zh == dict(old_zh, **extra), 'magic toggle translation'
    assert catalog(inputs / 'font-zh-TW.tsv') == dict(old_font, **extra)
    assert glyphs == read(base / 'glyphs-16.json'), 'magic toggle glyphs'
    for name in set(proof['base_files']) - {'inputs.json','provenance.json','en.tsv','zh-TW.tsv','font-zh-TW.tsv'}:
        assert (inputs / name).read_bytes() == (base / name).read_bytes(), name
    return base,read(base / 'inputs.json'),parent,old_en,old_zh,read(base / 'glyphs-16.json')


def guards(root, output):
    source = output / 'inputs-r3'
    def check(p):
        return check_sources(p, read(p / 'inputs.json'), read(p / 'provenance.json'),
            catalog(p / 'en.tsv'), catalog(p / 'zh-TW.tsv'), read(p / 'glyphs-16.json'))
    check(source)
    rejected = []
    for name in ('caller','position','menu','span','translation','glyph','witness'):
        with tempfile.TemporaryDirectory(dir=output,prefix='guard-') as temporary:
            p = Path(temporary)
            shutil.copytree(source,p,dirs_exist_ok=True)
            c, proof = read(p / 'inputs.json'),read(p / 'provenance.json')
            if name == 'translation':
                z = catalog(p / 'zh-TW.tsv')
                z[c['Fields'][-1]['Key']] += 'x'
                write_tsv(p / 'zh-TW.tsv',['key','text'],z.items())
            elif name == 'glyph':
                g = read(p / 'glyphs-16.json')
                g['glyphs'].pop(next(iter(g['glyphs'])))
                write(p / 'glyphs-16.json',g)
            elif name == 'witness':
                proof['magic_toggle_extension']['data']['notices'][0]['before_sha256'] = '0'*64
                write(p / 'provenance.json',proof)
            else:
                field = c['Fields'][-1]
                if name == 'caller':field['UpperCaller']['Off'] += 1
                elif name == 'position':field['RawY'] += 1
                elif name == 'menu':field['MenuSignature'] = '0'*64
                else:field['Length'] += 1
                proof['magic_toggle_extension']['data']['fields'][-1] = copy.deepcopy(field)
                write(p / 'inputs.json',c)
                write(p / 'provenance.json',proof)
            try:
                check(p)
            except AssertionError as error:
                assert str(error) in ('magic toggle config','magic toggle translation','magic toggle glyphs','magic toggle proof'),(name,error)
                rejected.append(name)
            else:raise AssertionError(name)
    with tempfile.TemporaryDirectory(dir=output,prefix='rebuild-') as temporary:
        p = Path(temporary) / 'inputs'
        generate(root,p)
        assert {f.name for f in p.iterdir()} == {f.name for f in source.iterdir()}
        for f in source.iterdir():assert f.read_bytes() == (p / f.name).read_bytes(),f.name
    write(output / 'guards-r3.json',dict(rejected=rejected,rebuilt_files=len(list(source.iterdir()))))


def review(root, output):
    from PIL import Image
    check = read(output / 'check-r4.json')
    assert check['all_submitted_pixels_equal_expected'] and len(check['magic_toggle']['intervals']) == 3
    runs = {lang:read(output / f'{lang}-r3/receipt.json') for lang in ('en','zh')}
    views = []
    for label in ('magic-on','magic-off','magic-on-again','magic-status-restored'):
        cp, = [c for c in runs['zh']['checkpoints'] if c['label'] == label]
        item = dict(label=label,step=cp['step'])
        for lang,run in runs.items():
            frame, = [f for f in run['frames'] if f['step'] == cp['step']]
            assert not frame['held']
            path = output / f'{lang}-r3' / frame['File']
            with Image.open(path) as image:
                assert image.size == (640,400)
                image.verify()
            item[lang] = dict(file=str(path.relative_to(output)),sha256=sha(path))
        views.append(item)
    counts = []
    run = runs['zh']
    for interval in check['magic_toggle']['intervals']:
        count = sum(not f['held'] and interval['ready_index'] < s['list_event_count'] <= interval['closed_index']
                    for f,s in zip(run['frames'],run['list_frames']))
        assert count > 0
        counts.append(count)
    write(output / 'visibility-review.json',dict(views=views,visible_frames=counts,
        intervals=3,footer_regression=read(output / 'footer-regression.json')))


def evidence(root, output):
    for name in ('native-check-r2.json','guards-r3.json','check-r4.json','input-guards.json',
                 'legacy-warning-check-r1.json','legacy-spells-check-r1.json','binary-rebuild.json',
                 'visibility-review.json','run-r1.json','hygiene-r1.json'):
        assert (output / name).is_file(),name
    names = {'magic_toggle_inputs.py','ui_list_live_check.py','oracle_input_modifier.go',
             'oracle_video_observer.go','ui_context_probe.go','ui-context.sh','ui-list-live.sh','early-live.sh',
             'ui_journal_reader_check.py','ui_journal_illustrations_check.py','research_storage.py'}
    names.update(p.name for p in (output / 'programs-r5').glob('*.go'))
    pending = list(names)
    while pending:
        name = pending.pop()
        if not name.endswith('.py'):continue
        for node in ast.walk(ast.parse((root / 'tools' / name).read_text())):
            modules = [node.module] if isinstance(node,ast.ImportFrom) else (
                [a.name for a in node.names] if isinstance(node,ast.Import) else [])
            for module in modules:
                candidate = (module or '').split('.')[0] + '.py'
                if candidate not in names and (root / 'tools' / candidate).is_file():
                    names.add(candidate)
                    pending.append(candidate)
    snapshots = output / 'tool-snapshots'
    assert not snapshots.exists()
    snapshots.mkdir()
    for name in sorted(names):shutil.copyfile(root / 'tools' / name,snapshots / name)
    probe = root / 'workplace/probe'
    sources = list((probe / BASE).iterdir())
    sources.extend(root / 'workplace/translation' / n for n in FORMAL)
    sources.extend(root / 'workplace/input/dos/drkqueen' / n for n in ('DQK.EXE','DISK3/ECL.GLB'))
    sources.extend(probe / n for n in ('battle-text-20261024/observe-combat-r1/final.state',
        'battle-text-20261024/control-quick-r3/final.state',
        'combat-spells-route-20261024/observe-r3/final.state',
        'combat-finish-20261024/control-r4/final.state',
        'combat-spells-route-20261024/evidence.json'))
    sources.extend(root / 'workplace/dosgolem' / n for n in
                   ('internal/dos/scancode.go','internal/dos/dos.go','oracle/input.go'))
    def record(path):
        info = path.stat()
        assert (info.st_uid,info.st_gid) == (1000,1000),path
        return dict(bytes=info.st_size,sha256=sha(path),uid=info.st_uid,gid=info.st_gid)
    assert not (output / 'evidence.json').exists()
    write(output / 'evidence.json',dict(draft=True,runtime_integrated=False,
        rights='原版、全文、字模及畫格只留本機',
        engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        effective=dict(inputs='inputs-r3',source='observe/control-r13',request='request-r12.json',
            gpu='en/zh-r3',program='programs-r5',native='programs-r3',check='check-r4.json',
            limits='正常首戰快照的 Alt-M 三次切換；Alt-Q 僅原版支線，未取得勝利。'),
        tools={n:sha(root / 'tools' / n) for n in sorted(names)},
        sources={str(p):record(p) for p in sources},
        artifacts={str(p.relative_to(output)):record(p) for p in sorted(output.rglob('*')) if p.is_file()}))


if __name__ == '__main__':
    command, project, directory = sys.argv[1:]
    root, output = Path(project),Path(directory)
    if command == 'native':native(root,output)
    elif command == 'prepare':
        assert read(output / 'native-check-r2.json')['checkpoints'] == 16
        generate(root,output / 'inputs-r3')
    elif command == 'guards':guards(root,output)
    elif command == 'review':review(root,output)
    elif command == 'evidence':evidence(root,output)
    elif command == 'audit':
        from combat_finish_inputs import audit
        audit(root,output)
    else:raise ValueError(command)
