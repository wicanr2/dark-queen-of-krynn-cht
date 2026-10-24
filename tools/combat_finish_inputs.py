"""首戰一般傷害及死亡回報的 DRAFT 輸入，沿正式 TSV，不重算遊戲數值。"""
import copy
import ast
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile

from bar_ui_inputs import write
from combat_effects_inputs import FORMAL, hud_records
from literal_catalog import catalog, digest, read, sha, windows
from text_catalog import write_tsv

BASE = 'combat-effects-20261024/inputs-r2'
SOURCE = 'combat-finish-20261024/observe-r4/receipt.json'


def derive(probe, texts):
    base = probe / BASE
    config = copy.deepcopy(read(base / 'inputs.json'))
    trace = read(probe / SOURCE)
    en, zh = [catalog(texts / (locale + '.tsv')) for locale in ('en', 'zh-TW')]
    aliases, bindings, fields = [], [], []
    prefix, damage, hit = ['ui.' + s for s in ('0047c0cbccc6f94c1ac8', 'f5e1d63728c2e2d27737', 'ffafa4fd7069a9fa0bda')]
    assert en[prefix] == 'takes %d%s' and en[damage] == ' points of damage '
    assert en[hit] == '%sHitting for %s'
    patterns = [
        (en[prefix].replace('%s', en[damage]), zh[prefix].replace('%s', zh[damage]), [prefix, damage], dict(Seg=0x88e, Off=0x15e1), [184, 88, 312, 176]),
        (en[hit].replace('%s', '', 1).replace('%s', '%d' + en[damage].rstrip()), zh[hit].replace('%s', '', 1).replace('%s', '%d' + zh[damage].rstrip()), [hit, damage], dict(Seg=0x22f4, Off=0x48f), [184, 104, 312, 136]),
    ]
    parent_en = catalog(base / 'en.tsv')
    parent_zh = catalog(base / 'zh-TW.tsv')
    for source, translated, keys, caller, box in patterns:
        key = 'hud-format.' + digest(source)[:20]
        assert key not in parent_en
        aliases.append(dict(key=key, source=source, translation=translated, formal_keys=keys))
        bindings.append(dict(SHA256=digest(source), Caller=caller, NativeBox=box,
            Foreground=7, Background=0, Clear=1, IntegerTemplateKey=key, OrdinaryDamage=True, HideFooter=(caller['Seg']==0x88e),
            Spans=[dict(Start=0, Length=len(source), Key=key, Rect=[box[0], box[1], box[2]-box[0], 16 if caller['Seg']==0x88e else box[3]-box[1]])]))
    for key, box in [('ui.3c1c36a1af881a7bd161', [184, 88, 312, 176]), ('ui.a95140d02db9873ba8a6', [184, 112, 312, 176])]:
        source = en[key]
        if key not in parent_en:
            aliases.append(dict(key=key, source=source, translation=zh[key], formal_keys=[key]))
        else:
            assert parent_en[key] == source and parent_zh[key] == zh[key]
        bindings.append(dict(SHA256=digest(source), Caller=dict(Seg=0x88e, Off=0x15e1), NativeBox=box,
            Foreground=7, Background=0, Clear=1,
            HideFooter=(box[1]==88),
            Spans=[dict(Start=0, Length=len(source), Key=key, Rect=[box[0], box[1], box[2]-box[0], box[3]-box[1]])]))
    config['HUDParagraphs'] += bindings
    # 同一怪物在行動者位置的顏色由原版提供，不能沿目標欄的顏色猜測。
    for c in trace['calls']:
        source = c['vararg_1_candidate']['text']
        if c['format']['text'] != '%s' or source not in ('BLUE DRAGON', 'GREEN DRAGON'):
            continue
        w = trace['wrappers'][c['wrapper_index']]
        assert c['wrapper_index'] >= 0 and w['caller'] == dict(Seg=0x88e, Off=0x16fb)
        y = (c['stack'][2]-8000)*2
        assert c['stack'][3] == 8092 and y in (8, 80, 96)
        assert [(w['stack'][n]&255)*8 for n in (2, 3)] == [184, y]
        choices = [k for k, v in parent_en.items() if v == source and k in parent_zh]
        if choices:
            assert len({parent_zh[k] for k in choices}) == 1
            key = min(choices)
        else:
            previous = [a for a in aliases if a['source'] == source]
            if previous:
                key = previous[0]['key']
            else:
                choices = [k for k,v in en.items() if v.upper() == source and k in zh]
                assert choices and len({zh[k] for k in choices}) == 1
                key = 'hud.' + digest(source)[:20]
                aliases.append(dict(key=key, source=source, translation=zh[min(choices)], formal_keys=choices))
        f = dict(Pane='callsite', Group='body', Key=key, Start=0, Length=len(source),
            SHA256=digest(source), FormatSHA256=digest('%s'), Caller=c['caller'], UpperCaller=w['caller'],
            UpperFormatSHA256=digest('%s'), UpperNative=[184, y], RawX=8092, RawY=c['stack'][2],
            Color=c['stack'][4], BackgroundOverride=23, MenuSignature='')
        if f not in config['Fields']:
            config['Fields'].append(f)
            fields.append(dict(call_step=c['step'], source=source, binding=f))
    all_en = dict(parent_en, **{a['key']: a['source'] for a in aliases})
    records = hud_records(trace, config['HUDParagraphs'], all_en)
    assert [r['number'] for r in records if r['number'] is not None] == [12, 40, 80]
    assert {r['binding']['SHA256'] for r in records} >= {b['SHA256'] for b in bindings}
    config['fine_windows'] = windows(trace)
    return config, dict(aliases=aliases, bindings=bindings, fields=fields, records=records)


def font_values(probe, data):
    return dict(catalog(probe / BASE / 'font-zh-TW.tsv'), **{a['key']: a['translation'] for a in data['aliases']})


def glyph_inputs(root, output):
    probe = root / 'workplace/probe'
    _, data = derive(probe, root / 'workplace/translation')
    old = read(probe / BASE / 'glyphs-16.json')
    missing = set(''.join(font_values(probe, data).values())) - set('\r\n\t') - set(old['glyphs'])
    write_tsv(output / 'glyph-source.tsv', ['key', 'text'], (('glyph.'+format(ord(c), 'x'), c) for c in sorted(missing)))
    print('new glyphs', sorted(missing))


def merged(probe, data):
    old = read(probe / BASE / 'glyphs-16.json')
    new = read(probe / 'combat-finish-20261024/glyphs-added-16.json')
    assert all(old[k] == new[k] for k in ('size', 'height', 'font_sha256'))
    missing = set(''.join(font_values(probe, data).values())) - set('\r\n\t') - set(old['glyphs'])
    assert set(new['glyphs']) == missing
    result = copy.deepcopy(old)
    result['glyphs'].update(new['glyphs'])
    return result


def generate(root, target):
    probe = root / 'workplace/probe'
    texts = root / 'workplace/translation'
    base = probe / BASE
    config, data = derive(probe, texts)
    shutil.copytree(base, target)
    for name, column in [('en.tsv', 'source'), ('zh-TW.tsv', 'translation'), ('font-zh-TW.tsv', 'translation')]:
        values = catalog(base / name)
        values.update({a['key']: a[column] for a in data['aliases']})
        write_tsv(target / name, ['key', 'text'], values.items())
    proof = read(base / 'provenance.json')
    proof['finish_extension'] = dict(base=BASE, base_files={f.name:sha(f) for f in base.iterdir()},
        source_path=SOURCE, source_sha256=sha(probe / SOURCE), data=data,
        page_validation=dict(source_path=SOURCE, source_sha256=sha(probe / SOURCE)),
        formal_files={n:sha(texts / n) for n in FORMAL})
    write(target / 'inputs.json', config)
    write(target / 'provenance.json', proof)
    write(target / 'glyphs-16.json', merged(probe, data))


def check_sources(inputs, config, proof, en, zh, glyphs):
    probe = inputs.parent.parent
    item = proof['finish_extension']
    base = probe / BASE
    expected, data = derive(probe, Path('/catalogs'))
    assert config == expected, 'finish config'
    assert item == dict(base=BASE, base_files={f.name:sha(f) for f in base.iterdir()},
        source_path=SOURCE, source_sha256=sha(probe / SOURCE), data=data,
        page_validation=dict(source_path=SOURCE, source_sha256=sha(probe / SOURCE)),
        formal_files={n:sha(Path('/catalogs') / n) for n in FORMAL}), 'finish provenance'
    parent = read(base / 'provenance.json')
    assert {k:v for k,v in proof.items() if k != 'finish_extension'} == parent
    old_en, old_zh = catalog(base / 'en.tsv'), catalog(base / 'zh-TW.tsv')
    assert en == dict(old_en, **{a['key']:a['source'] for a in data['aliases']})
    assert zh == dict(old_zh, **{a['key']:a['translation'] for a in data['aliases']}), 'finish translation'
    assert catalog(inputs / 'font-zh-TW.tsv') == font_values(probe, data)
    assert glyphs == merged(probe, data)
    for name in item['base_files']:
        if name not in ('inputs.json', 'provenance.json', 'en.tsv', 'zh-TW.tsv', 'font-zh-TW.tsv', 'glyphs-16.json'):
            assert (inputs / name).read_bytes() == (base / name).read_bytes()
    return base, read(base / 'inputs.json'), parent, old_en, old_zh, read(base / 'glyphs-16.json')


def guards(root, output):
    inputs = output / 'inputs-r4'
    def check(p):
        return check_sources(p, read(p/'inputs.json'), read(p/'provenance.json'), catalog(p/'en.tsv'), catalog(p/'zh-TW.tsv'), read(p/'glyphs-16.json'))
    check(inputs)
    cases = []
    for name in ('caller', 'box', 'footer', 'damage-kind', 'translation'):
        with tempfile.TemporaryDirectory(dir=output, prefix='guard-') as d:
            p = Path(d)
            shutil.copytree(inputs, p, dirs_exist_ok=True)
            c = read(p/'inputs.json')
            b = c['HUDParagraphs'][-4]
            if name == 'translation':
                z = catalog(p/'zh-TW.tsv')
                z[b['IntegerTemplateKey']] = z[b['IntegerTemplateKey']].replace('%d', '80')
                write_tsv(p/'zh-TW.tsv', ['key', 'text'], z.items())
            else:
                if name == 'caller': b['Caller']['Off'] += 1
                elif name == 'box': b['NativeBox'][1] += 8
                elif name == 'footer': b['KeepFooterSignature'] = '0'*64
                else: b['OrdinaryDamage'] = False
                write(p/'inputs.json', c)
            try:
                check(p)
            except AssertionError as e:
                assert str(e) == ('finish translation' if name == 'translation' else 'finish config')
            else:
                raise AssertionError(name)
            cases.append(name)
    with tempfile.TemporaryDirectory(dir=output, prefix='rebuild-') as d:
        p = Path(d)/'inputs'
        generate(root, p)
        assert {f.name for f in inputs.iterdir()} == {f.name for f in p.iterdir()}
        for f in inputs.iterdir(): assert f.read_bytes() == (p/f.name).read_bytes(), f.name
    write(output/'guards.json', dict(cases=cases, rebuilt_files=len(list(inputs.iterdir())), tool_sha256=sha(Path(__file__))))


def parent_review(output):
    from PIL import Image
    parent = output.parent/'combat-effects-20261024'
    old = read(parent/'zh-r6/receipt.json')
    new = read(output/'parent-zh-r2/receipt.json')
    for name in ('frames', 'list_frames', 'list_events', 'checkpoints', 'paragraphs', 'final_words', 'final_paragraph'):
        assert old[name] == new[name], name
    files = {f['File']: f for f in new['frames']}
    for name, frame in files.items():
        with Image.open(output/'parent-zh-r2'/name) as im:
            assert im.size == (640, 400)
            assert hashlib.sha256(im.convert('RGBA').tobytes()).hexdigest() == frame['SHA256']
    write(output/'parent-regression-r2.json', dict(frames_equal=len(new['frames']),
        checkpoints_equal=len(new['checkpoints']), checked_pngs=len(files),
        parent_receipt_sha256=sha(parent/'zh-r6/receipt.json'),
        new_receipt_sha256=sha(output/'parent-zh-r2/receipt.json'),
        scope='同一新版重跑既有繁中施法，原版狀態、事件及實際 GPU 像素保持相同；未重跑父批英文。'))


def review(output):
    from PIL import Image, ImageDraw
    run = read(output/'zh-r5/receipt.json')
    data = read(output/'inputs-r4/provenance.json')['finish_extension']['data']
    assert (output/'gpu-check-r5.json').is_file()
    visible = {w['Key'] for frame, state in zip(run['frames'], run['list_frames'])
        if not frame['held'] for w in state['words'] or []}
    assert {a['key'] for a in data['aliases']} <= visible
    points = []
    for cp in run['checkpoints']:
        i = next(i for i,f in enumerate(run['frames']) if f['step'] == cp['step'])
        frame, state = run['frames'][i], run['list_frames'][i]
        numbers = [w['Number'] for w in state['words'] or [] if 'Number' in w]
        assert frame['held'] == (cp['label'] in ('quick-weapon', 'next-victim-weapon'))
        expected = {'hit-twelve':[12], 'damage-forty':[40], 'damage-eighty':[80], 'victim-killed':[80], 'quick-wait':[80]}.get(cp['label'], [])
        assert numbers == expected, cp['label']
        if cp['label'] in ('victim-killed', 'quick-wait'):
            assert any(w['Key']=='ui.a95140d02db9873ba8a6' for w in state['words'])
        points.append(dict(label=cp['label'], step=cp['step'], held=frame['held'], numbers=numbers))
    intervals = []
    for record in data['records']:
        frames = [f for f in run['frames'] if record['step'] <= f['step'] < record['return_step']]
        assert frames and all(f['held'] for f in frames)
        intervals.append(dict(entry=record['step'], first_glyph=record['first_glyph'], returned=record['return_step'], held_samples=len(frames)))
    runs = {lang:read(output/(lang+'-r5/receipt.json')) for lang in ('en', 'zh')}
    images = []
    for label in ('hit-twelve', 'breath-lightning', 'damage-forty', 'damage-eighty', 'victim-killed'):
        panel = Image.new('RGB', (1280, 420), '#202020')
        draw = ImageDraw.Draw(panel)
        for col, lang in enumerate(('en', 'zh')):
            r = runs[lang]
            cp = next(c for c in r['checkpoints'] if c['label']==label)
            frame = next(f for f in r['frames'] if f['step']==cp['step'])
            assert not frame['held']
            panel.paste(Image.open(output/(lang+'-r5')/frame['File']).convert('RGB'), (col*640, 20))
            draw.text((col*640+4, 2), label+' / '+lang, fill='white')
        path = output/('review-r5-'+label+'.png')
        panel.save(path)
        images.append(dict(file=path.name, sha256=sha(path)))
    write(output/'visibility-review-r5.json', dict(points=points, visible_aliases=len(data['aliases']), intervals=intervals, images=images))


def evidence(root, output):
    assert read(output/'guards.json')['tool_sha256'] == sha(Path(__file__))
    for name in ('gpu-check-r5.json', 'visibility-review-r5.json', 'parent-regression-r2.json', 'parent-check-final.json', 'binary-rebuild-r3.json'):
        assert (output/name).is_file(), name
    tools = root/'tools'
    names = {'combat_finish_inputs.py', 'ui_list_live_check.py', 'ui-context.sh', 'ui_context_probe.go',
        'oracle_video_observer.go', 'ui_hud_integer_test.go'}
    names.update(f.name for f in (output/'programs-r3').glob('*.go'))
    pending = list(names)
    while pending:
        name = pending.pop()
        if not name.endswith('.py'): continue
        tree = ast.parse((tools/name).read_text())
        for node in ast.walk(tree):
            modules = [node.module] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names] if isinstance(node, ast.Import) else []
            for module in modules:
                candidate = (module or '').split('.')[0] + '.py'
                if candidate not in names and (tools/candidate).is_file():
                    names.add(candidate)
                    pending.append(candidate)
    snapshots = output/'tool-snapshots'
    snapshots.mkdir()
    tool_index = {}
    for name in sorted(names):
        assert (tools/name).stat().st_uid == 1000
        shutil.copyfile(tools/name, snapshots/name)
        tool_index[name] = sha(tools/name)
    sources = [root/'workplace/translation'/n for n in FORMAL]
    sources += list((root/'workplace/probe'/BASE).iterdir())
    sources += [root/'workplace/input/dos/drkqueen/DQK.EXE', Path('/font/jf-openhuninn-2.1.ttf'),
        root/'workplace/probe/ui-context-probe']
    def info(path):
        s = path.stat()
        assert (s.st_uid, s.st_gid) == (1000, 1000), path
        return dict(bytes=s.st_size, sha256=sha(path), uid=s.st_uid, gid=s.st_gid)
    artifacts = {str(f.relative_to(output)):info(f) for f in sorted(output.rglob('*')) if f.is_file()}
    result = dict(draft=True, runtime_integrated=False, rights='僅本機；不提交原版、全文、字模或畫格',
        engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        sources={str(f):info(f) for f in sources}, tools=tool_index, artifacts=artifacts,
        effective=dict(inputs='inputs-r4', program='programs-r3', native='observe-r4/control-r4', gpu='en-r5/zh-r5', parent_gpu='parent-zh-r2'))
    write(output/'evidence.json', result)


def audit(root, output):
    manifest = read(output/'evidence.json')
    assert set(manifest['artifacts']) == {str(f.relative_to(output)) for f in output.rglob('*') if f.is_file() and f.name!='evidence.json'}
    for name, expected in manifest['artifacts'].items():
        path = output/name
        assert path.resolve().is_relative_to(output.resolve())
        assert (path.stat().st_size, sha(path), path.stat().st_uid, path.stat().st_gid) == (expected['bytes'], expected['sha256'], expected['uid'], expected['gid']), name
    for name, expected in manifest['sources'].items():
        path = Path(name)
        assert path.stat().st_size == expected['bytes'] and sha(path) == expected['sha256'], name
    for name, expected in manifest['tools'].items():
        assert sha(root/'tools'/name) == sha(output/'tool-snapshots'/name) == expected, name
    print('verified', len(manifest['artifacts']), 'artifacts', len(manifest['sources']), 'sources', len(manifest['tools']), 'tools')


if __name__ == '__main__':
    command, root, output = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    if command == 'prepare': generate(root, output/'inputs-r4')
    elif command == 'glyph_inputs': glyph_inputs(root, output)
    elif command == 'guards': guards(root, output)
    elif command == 'review': review(output)
    elif command == 'parent_review': parent_review(output)
    elif command == 'evidence': evidence(root, output)
    elif command == 'audit': audit(root, output)
    else: raise SystemExit('glyph_inputs | prepare | guards | review | parent_review | evidence | audit')
