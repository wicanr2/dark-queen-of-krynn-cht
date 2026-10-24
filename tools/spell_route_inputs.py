"""正常首戰其他法術清單的 DRAFT 資料；只擴充已觀測的呈現綁定。"""
import copy
import ast
import hashlib
from pathlib import Path
import re
import shutil
import sys
import tempfile

from literal_catalog import catalog, digest, read, sha, windows
from text_catalog import write_tsv
from combat_rounds_inputs import hud_records

BASE = 'journal-references-20261024/inputs-r1'
STUDY = 'combat-spells-route-20261024'
SOURCE = STUDY + '/observe-r6/receipt.json'
FORMAL = ('en.tsv', 'zh-TW.tsv', 'catalog.json', 'glossary.tsv', 'glossary-additions.tsv')


def write(path, value):
    import json
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def native(root, output):
    a, b = [read(output / f'{m}-r6/receipt.json') for m in ('observe', 'control')]
    assert a['observe'] and not b['observe']
    for key in ('source_commit', 'go_version', 'exe_sha256', 'state_sha256',
                'probe_sha256', 'request_sha256', 'request', 'checkpoints'):
        assert a[key] == b[key], key
    assert a['source_commit'] == 'f79eab6db8c64a524a06535e53e5d32b0bbcf7c8'
    assert a['exe_sha256'] == '3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
    assert a['state_sha256'] == sha(root / 'workplace/probe/combat-effects-20261024/observe-r1/final.state')
    assert a['probe_sha256'] == sha(root / 'workplace/probe/journal-references-20261024/source-programs-r1/ui-context-probe')
    assert a['request_sha256'] == sha(output / 'request-r6.json')
    assert len(a['checkpoints']) == 4 and a['request']['start_steps'] == 3570000000
    assert not any(v for k, v in a.items() if k.startswith('pending'))
    for cp in a['checkpoints']:
        assert not cp['file_writes'] and not cp['unimplemented']
        for suffix in ('.png', '.idx'):
            name = cp['label'] + suffix
            assert sha(output / 'observe-r6' / name) == sha(output / 'control-r6' / name)
    assert sha(output / 'observe-r6/final.state') == sha(output / 'control-r6/final.state')
    write(output / 'native-check-r2.json', dict(checkpoints=4, source_path=SOURCE,
        source_sha256=sha(output / 'observe-r6/receipt.json'), final_state_sha256=sha(output / 'observe-r6/final.state')))


def derive(probe, texts):
    old = read(probe / BASE / 'inputs.json')
    config = copy.deepcopy(old)
    trace = read(probe / SOURCE)
    en, zh = catalog(texts / 'en.tsv'), catalog(texts / 'zh-TW.tsv')
    aliases, rows, contexts, fields = {}, {}, [], []
    for listing in trace['list_events']:
        menu = listing['menu_snapshot']
        assert old['Menus'][menu['Signature']] == 'grimoire'
        assert [bytes.fromhex(b['SourceHex']).decode() for b in menu['Buttons']] == ['Cast', 'Exit']
        context = dict(Pane='grimoire', RowFillPage=True,
            DescriptorSHA256=hashlib.sha256(bytes.fromhex(listing['descriptor_before_hex'])).hexdigest(),
            MenuSignature=menu['Signature'], Caller=dict(Seg=listing['stack'][1], Off=listing['stack'][0]))
        if context not in config['PaneLists']:
            config['PaneLists'].append(context)
            contexts.append(context)
    for wrapper in trace['wrappers']:
        if wrapper['caller'] not in old['RowCallers'] or wrapper['format']['text'] != '%s':
            continue
        source = wrapper['vararg_1_candidate']
        assert source['nul_terminated']
        text = source['text']
        if text.startswith('\t'):
            match = re.fullmatch(r'\t(.+?)(?: \([1-9][0-9]*\))?', text)
            assert match and '\t' not in match[1]
            start, name = 1, match[1]
        else:
            assert text == 'Special' or re.fullmatch(r'[1-9](?:st|nd|rd|th) Level', text)
            start, name = 0, text
        choices = [k for k, v in en.items() if v.casefold() == name.casefold() and k in zh]
        assert choices and len({zh[k] for k in choices}) == 1, name
        formal = min(choices, key=lambda k: (en[k] != name, not k.startswith('ui.'), k))
        key = 'grimoire.' + digest(name)[:20]
        aliases[key] = dict(key=key, source=name, formal_key=formal)
        color = wrapper['stack'][4] & 255
        assert color in (7, 11, 12)
        item = rows.setdefault(digest(text), dict(source=text,
            spans=[dict(Start=start, Length=len(name), Key=key)], colors=set()))
        assert item['source'] == text
        item['colors'].add(color)
    records, added, updated = [], [], []
    for h, item in rows.items():
        row = dict(Pane='grimoire', SHA256=h, Spans=item['spans'], Foregrounds=sorted(item['colors']))
        previous = next((r for r in config['Rows'] if r['Pane'] == 'grimoire' and r['SHA256'] == h), None)
        if previous:
            assert previous['Spans'] == row['Spans']
            merged = sorted(set(previous['Foregrounds']) | item['colors'])
            if merged != previous['Foregrounds']:
                previous['Foregrounds'] = merged
                updated.append(h)
        else:
            config['Rows'].append(row)
            added.append(h)
        records.append(dict(source=item['source'], row=row))
    assert len(records) == 20 and len(added) == 10
    title = next(h for h in old['Headers'] if h['Key'] == 'header.41b8dd827bde29bd2677')
    template = next(f for f in old['Fields'] if f['Pane'] == 'grimoire'
                    and f['Group'] == 'header' and f['SHA256'] == title['SHA256'])
    calls = []
    for call in trace['calls']:
        if call['format']['text'] != '%s' or not call['vararg_1_candidate']['nul_terminated']:
            continue
        if digest(call['vararg_1_candidate']['text']) != title['SHA256']:
            continue
        wrapper = trace['wrappers'][call['wrapper_index']]
        assert (wrapper['format']['segment'], wrapper['format']['offset']) == (title['Segment'], title['Offset'])
        assert digest(wrapper['format']['text']) == title['SHA256'] and call['caller'] == template['Caller']
        assert call['stack'][2:4] == [8004, 8076]
        field = copy.deepcopy(template)
        field['RawY'], field['RawX'] = call['stack'][2:4]
        if field not in config['Fields']:
            config['Fields'].append(field)
            fields.append(field)
        calls.append(call['step'])
    assert len(fields) == len(calls) == 1
    config['fine_windows'] = windows(trace)
    return config, dict(aliases=list(aliases.values()), rows=records, added_rows=added,
        updated_rows=updated, contexts=contexts, fields=fields, title_calls=calls,
        records=hud_records(trace, config['HUDParagraphs'], catalog(probe / BASE / 'en.tsv')))


def generate(root, target):
    probe, texts = root / 'workplace/probe', root / 'workplace/translation'
    base = probe / BASE
    config, data = derive(probe, texts)
    en, zh, font = [catalog(base / n) for n in ('en.tsv', 'zh-TW.tsv', 'font-zh-TW.tsv')]
    formal = catalog(texts / 'zh-TW.tsv')
    for alias in data['aliases']:
        key, text, value = alias['key'], alias['source'], formal[alias['formal_key']]
        if key in en:
            assert (en[key], zh[key]) == (text, value)
        en[key], zh[key], font[key] = text, value, value
    glyphs = read(base / 'glyphs-16.json')
    assert not (set(''.join(font.values())) - set('\r\n\t') - set(glyphs['glyphs'])), 'new glyphs required'
    shutil.copytree(base, target)
    proof = read(base / 'provenance.json')
    proof['spell_route_extension'] = dict(base=BASE, base_files={p.name:sha(p) for p in base.iterdir()},
        source_path=SOURCE, source_sha256=sha(probe / SOURCE), data=data,
        page_validation=dict(source_path=SOURCE, source_sha256=sha(probe / SOURCE)),
        formal_files={n:sha(texts / n) for n in FORMAL})
    for name, values in (('en.tsv', en), ('zh-TW.tsv', zh), ('font-zh-TW.tsv', font)):
        write_tsv(target / name, ['key', 'text'], values.items())
    write(target / 'inputs.json', config)
    write(target / 'provenance.json', proof)


def check_sources(inputs, config, provenance, en, zh, glyphs):
    root = inputs.parent.parent
    proof = provenance['spell_route_extension']
    base, texts = root / BASE, Path('/catalogs')
    assert proof['base'] == BASE and proof['source_path'] == SOURCE
    assert set(proof['base_files']) == {p.name for p in base.iterdir()}
    for name, h in proof['base_files'].items():
        assert Path(name).name == name and sha(base / name) == h
    assert sha(root / SOURCE) == proof['source_sha256']
    assert proof['page_validation'] == dict(source_path=SOURCE, source_sha256=sha(root / SOURCE))
    assert proof['formal_files'] == {n:sha(texts / n) for n in FORMAL}
    expected, data = derive(root, texts)
    assert config == expected, 'spell route config'
    assert proof['data'] == data, 'spell route provenance'
    parent = read(base / 'provenance.json')
    assert {k:v for k,v in provenance.items() if k != 'spell_route_extension'} == parent
    old_en, old_zh, old_font = [catalog(base / n) for n in ('en.tsv', 'zh-TW.tsv', 'font-zh-TW.tsv')]
    formal = catalog(texts / 'zh-TW.tsv')
    assert en == dict(old_en, **{a['key']:a['source'] for a in data['aliases']})
    extra = {a['key']:formal[a['formal_key']] for a in data['aliases']}
    assert zh == dict(old_zh, **extra), 'spell route translation'
    assert catalog(inputs / 'font-zh-TW.tsv') == dict(old_font, **extra)
    assert glyphs == read(base / 'glyphs-16.json'), 'spell route glyphs'
    changed = {'inputs.json', 'provenance.json', 'en.tsv', 'zh-TW.tsv', 'font-zh-TW.tsv'}
    for name in set(proof['base_files']) - changed:
        assert (inputs / name).read_bytes() == (base / name).read_bytes(), name
    return base, read(base / 'inputs.json'), parent, old_en, old_zh, read(base / 'glyphs-16.json')


def guards(root, output):
    source = output / 'inputs-r3'
    def check(p):
        return check_sources(p, read(p / 'inputs.json'), read(p / 'provenance.json'),
            catalog(p / 'en.tsv'), catalog(p / 'zh-TW.tsv'), read(p / 'glyphs-16.json'))
    check(source)
    rejected = []
    for name in ('title-position', 'row-span', 'list-context', 'quantity', 'translation', 'glyph'):
        with tempfile.TemporaryDirectory(dir=output, prefix='guard-') as tmp:
            p = Path(tmp)
            shutil.copytree(source, p, dirs_exist_ok=True)
            c, proof = read(p / 'inputs.json'), read(p / 'provenance.json')
            if name == 'translation':
                values = catalog(p / 'zh-TW.tsv')
                values[proof['spell_route_extension']['data']['aliases'][-1]['key']] += 'x'
                write_tsv(p / 'zh-TW.tsv', ['key', 'text'], values.items())
            elif name == 'glyph':
                g = read(p / 'glyphs-16.json')
                g['glyphs'].pop(next(iter(g['glyphs'])))
                write(p / 'glyphs-16.json', g)
            else:
                if name == 'title-position':
                    c['Fields'][-1]['RawX'] += 1
                    proof['spell_route_extension']['data']['fields'][-1]['RawX'] += 1
                elif name == 'row-span':
                    c['Rows'][-1]['Spans'][0]['Start'] += 1
                elif name == 'list-context':
                    c['PaneLists'][-1]['DescriptorSHA256'] = '0' * 64
                else:
                    row = next(r for r in c['Rows'] if r['SHA256'] == digest('\tCone of Cold (2)'))
                    row['Spans'][0]['Length'] += 4
                write(p / 'inputs.json', c)
                write(p / 'provenance.json', proof)
            try:
                check(p)
            except AssertionError as error:
                assert str(error) in ('spell route config', 'spell route translation', 'spell route glyphs'), (name, error)
                rejected.append(name)
            else:
                raise AssertionError(name)
    with tempfile.TemporaryDirectory(dir=output, prefix='rebuild-') as tmp:
        p = Path(tmp) / 'inputs'
        generate(root, p)
        assert {f.name for f in p.iterdir()} == {f.name for f in source.iterdir()}
        for f in source.iterdir():
            assert f.read_bytes() == (p / f.name).read_bytes(), f.name
    write(output / 'guards-r3.json', dict(rejected=rejected, rebuilt_files=len(list(source.iterdir()))))


def review(root, output):
    from PIL import Image
    check = read(output / 'check-r6.json')
    assert check['spell_route']['rows'] == 20 and check['all_submitted_pixels_equal_expected']
    views = []
    runs = {lang:read(output / f'{lang}-r3/receipt.json') for lang in ('en', 'zh')}
    assert sum(e['Kind'] == 'memory-list-closed' for e in runs['zh']['list_events']) == 1
    keys = {a['key'] for a in read(output / 'inputs-r3/provenance.json')['spell_route_extension']['data']['aliases']}
    en, zh = catalog(output / 'inputs-r3/en.tsv'), catalog(output / 'inputs-r3/zh-TW.tsv')
    values = {(en[k], zh[k]) for k in keys}
    assert not any((en[w['Key']], zh[w['Key']]) in values for w in runs['zh']['list_frames'][-1]['words'])
    for cp in runs['zh']['checkpoints']:
        item = dict(label=cp['label'], step=cp['step'])
        for lang, run in runs.items():
            frame, = [f for f in run['frames'] if f['step'] == cp['step']]
            assert not frame['held']
            path = output / f'{lang}-r3' / frame['File']
            with Image.open(path) as image:
                assert image.size == (640, 400)
                image.verify()
            item[lang] = dict(file=str(path.relative_to(output)), sha256=sha(path))
        views.append(item)
    assert len(views) == 4
    write(output / 'visibility-review.json', dict(views=views, rows=20, added_rows=10,
        returned=True, rendering_only=True, no_victory_claim=True))


def evidence(root, output):
    for name in ('native-check-r2.json', 'guards-r3.json', 'check-r6.json',
                 'parent65-check-r1.json', 'visibility-review.json', 'run-r3.json'):
        assert (output / name).is_file(), name
    names = {'spell_route_inputs.py', 'ui_list_live_check.py', 'ui_journal_reader_check.py',
             'ui_journal_illustrations_check.py', 'research_storage.py'}
    pending = list(names)
    while pending:
        name = pending.pop()
        for node in ast.walk(ast.parse((root / 'tools' / name).read_text())):
            modules = [node.module] if isinstance(node, ast.ImportFrom) else (
                [a.name for a in node.names] if isinstance(node, ast.Import) else [])
            for module in modules:
                candidate = (module or '').split('.')[0] + '.py'
                if candidate not in names and (root / 'tools' / candidate).is_file():
                    names.add(candidate)
                    pending.append(candidate)
    snapshots = output / 'tool-snapshots'
    assert not snapshots.exists()
    snapshots.mkdir()
    for name in sorted(names):
        shutil.copyfile(root / 'tools' / name, snapshots / name)
    probe = root / 'workplace/probe'
    sources = list((probe / BASE).iterdir())
    sources.extend(root / 'workplace/translation' / n for n in FORMAL)
    sources.extend(root / 'workplace/input/dos/drkqueen' / n for n in ('DQK.EXE', 'DISK3/ECL.GLB'))
    sources.extend(Path('/dkk/text') / n for n in ('glossary.tsv', 'name.zh-TW.tsv', 'name-lexicon-five.tsv'))
    sources.extend(probe / n for n in (
        'journal-references-20261024/programs-r1/ui-list-live',
        'journal-references-20261024/source-programs-r1/ui-context-probe',
        'combat-effects-20261024/observe-r1/final.state',
        'combat-rounds-20261024/control-r1/final.state',
        'combat-finish-20261024/control-r4/final.state',
        'journal-references-20261024/evidence.json'))
    def record(path):
        info = path.stat()
        assert (info.st_uid, info.st_gid) == (1000, 1000), path
        return dict(bytes=info.st_size, sha256=sha(path), uid=info.st_uid, gid=info.st_gid)
    assert not (output / 'evidence.json').exists()
    write(output / 'evidence.json', dict(draft=True, runtime_integrated=False,
        rights='原版、全文、字模及畫格僅留本機',
        engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        effective=dict(inputs='inputs-r3', source='observe/control-r6', gpu='en/zh-r3',
            checks='check-r6.json', program='journal-references-20261024/programs-r1/ui-list-live',
            limits='原二進位未改；原版正常三頁清單與返回，不是首戰勝利。r1/r2 只為早期驗證資料。'),
        tools={name:sha(root / 'tools' / name) for name in sorted(names)},
        sources={str(p):record(p) for p in sources},
        artifacts={str(p.relative_to(output)):record(p) for p in sorted(output.rglob('*')) if p.is_file()}))


if __name__ == '__main__':
    command, project, directory = sys.argv[1:]
    root, output = Path(project), Path(directory)
    if command == 'native':
        native(root, output)
    elif command == 'prepare':
        assert read(output / 'native-check-r2.json')['checkpoints'] == 4
        generate(root, output / 'inputs-r3')
    elif command == 'guards':
        guards(root, output)
    elif command == 'review':
        review(root, output)
    elif command == 'evidence':
        evidence(root, output)
    elif command == 'audit':
        from combat_finish_inputs import audit
        audit(root, output)
    else:
        raise ValueError(command)
