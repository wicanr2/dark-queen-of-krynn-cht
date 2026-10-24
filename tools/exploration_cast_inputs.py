"""正常探索施法的 DRAFT 顯示資料；不寫入原版狀態。"""
import copy
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

from literal_catalog import catalog, digest, read, sha, windows
from text_catalog import write_tsv
from combat_rounds_inputs import hud_records

BASE = 'combat-fire-20261025/inputs-r2'
STUDY = 'haste-battle-20261025'
SOURCE = STUDY + '/observe-main-r2/receipt.json'
FORMAL = ('en.tsv', 'zh-TW.tsv', 'catalog.json', 'glossary.tsv', 'glossary-additions.tsv')


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def native(root, output):
    a, b = [read(output / f'{mode}-main-r2/receipt.json') for mode in ('observe', 'control')]
    assert a['observe'] and not b['observe']
    for key in ('source_commit', 'go_version', 'exe_sha256', 'probe_sha256', 'state_sha256',
                'request_sha256', 'request', 'checkpoints'):
        assert a[key] == b[key], key
    probe = root / 'workplace/probe'
    assert a['source_commit'] == 'f79eab6db8c64a524a06535e53e5d32b0bbcf7c8'
    assert a['exe_sha256'] == '3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
    assert a['probe_sha256'] == sha(probe / 'combat-aim-route-20261024/programs-r3/ui-context-probe')
    assert a['state_sha256'] == sha(probe / 'battle-text-20261024/observe-gate-r1/final.state')
    assert a['request_sha256'] == sha(output / 'request-main-r2.json')
    assert len(a['checkpoints']) == 55
    assert not any(v for k, v in a.items() if k.startswith('pending'))
    old = read(output / 'observe-main-r1/receipt.json')
    for key in ('calls', 'paragraphs', 'wrappers', 'list_events', 'fill_events', 'menus', 'display_changes'):
        assert a[key] == old[key], key
    previous = {c['label']: c for c in old['checkpoints']}
    for c in a['checkpoints']:
        assert not c['file_writes'] and not c['unimplemented']
        if c['label'] in previous:
            assert c == previous[c['label']]
        for suffix in ('.idx', '.png'):
            name = c['label'] + suffix
            assert sha(output / 'observe-main-r2' / name) == sha(output / 'control-main-r2' / name)
    state = sha(output / 'observe-main-r2/final.state')
    assert state == sha(output / 'control-main-r2/final.state') == sha(output / 'observe-main-r1/final.state')
    write(output / 'native-check.json', dict(checkpoints=55, previous_checkpoints=len(previous),
        source_path=SOURCE, source_sha256=sha(output / 'observe-main-r2/receipt.json'), final_state_sha256=state))


def derive(probe, formal):
    base = probe / BASE
    config = copy.deepcopy(read(base / 'inputs.json'))
    trace = read(probe / SOURCE)
    en, zh = catalog(formal / 'en.tsv'), catalog(formal / 'zh-TW.tsv')
    old_en, old_zh = catalog(base / 'en.tsv'), catalog(base / 'zh-TW.tsv')
    aliases, fields, contexts, rows, menus, bindings = {}, [], [], [], [], []

    def term(text):
        previous = [k for k, v in old_en.items() if v == text and k in old_zh]
        if previous:
            assert len({old_zh[k] for k in previous}) == 1, text
            return min(previous)
        choices = [k for k, v in en.items() if v.rstrip().casefold() == text.rstrip().casefold() and k in zh]
        assert choices and len({zh[k] for k in choices}) == 1, text
        formal_key = min(choices)
        key = 'exploration-cast.' + digest(text)[:20]
        aliases[key] = dict(key=key, source=text, formal_key=formal_key)
        return key

    # 探索底列尚有未證實的 Inv 操作語意，整個未知表形沿用原文。
    # 本批只處理正常 Cast 進入後的既有選單、清單與效果回報。
    for listing in trace['list_events']:
        menu = listing['menu_snapshot']
        assert config['Menus'][menu['Signature']] == 'grimoire'
        item = dict(Pane='grimoire', RowFillPage=True, DescriptorSHA256=hashlib.sha256(bytes.fromhex(listing['descriptor_before_hex'])).hexdigest(),
            MenuSignature=menu['Signature'], Caller=dict(Seg=listing['stack'][1], Off=listing['stack'][0]))
        if item not in config['PaneLists']:
            config['PaneLists'].append(item)
            contexts.append(item)
    observed_rows = {}
    for w in trace['wrappers']:
        if w['caller'] not in config['RowCallers'] or w['format']['text'] != '%s':
            continue
        source = w['vararg_1_candidate']['text']
        if source.startswith('\t'):
            match = re.fullmatch(r'\t(.+?)(?: \([1-9][0-9]*\))?', source)
            assert match
            name, start = match[1], 1
        else:
            assert re.fullmatch(r'[1-9](?:st|nd|rd|th) Level', source), source
            name, start = source, 0
        color = w['stack'][4] & 255
        assert color in (7, 11, 12)
        item = observed_rows.setdefault(digest(source), dict(source=source, colors=set(),
            spans=[dict(Start=start, Length=len(name), Key=term(name))]))
        item['colors'].add(color)
    for h, item in observed_rows.items():
        row = next((r for r in config['Rows'] if r['Pane'] == 'grimoire' and r['SHA256'] == h), None)
        if row is None:
            row = dict(Pane='grimoire', SHA256=h, Spans=item['spans'], Foregrounds=sorted(item['colors']))
            config['Rows'].append(row)
        else:
            # 舊列的 key 保持不變；相同原文的別名不能改動繪製來源。
            def lexical(spans):
                return [(s['Start'], s['Length'], old_en[s['Key']] if s['Key'] in old_en else aliases[s['Key']]['source']) for s in spans]
            assert lexical(row['Spans']) == lexical(item['spans']), 'row lexical spans'
            row['Foregrounds'] = sorted(set(row['Foregrounds']) | item['colors'])
        rows.append(dict(source=item['source'], row=copy.deepcopy(row)))
    cast_sources = {'casts', 'Haste', 'Lightning Bolt', "Can't be cast here...", 'Lose it? '}
    for c in trace['calls']:
        source = c['vararg_1_candidate']['text'] if c['format']['text'] == '%s' else c['format']['text']
        if source not in cast_sources or source=='Lightning Bolt' and c['step']<2427000000:
            continue
        w = trace['wrappers'][c['wrapper_index']]
        assert c['caller'] == dict(Seg=0xb72, Off=0x27c) and c['format']['text'] == '%s'
        key = term(source.rstrip())
        field = dict(Pane='callsite', Group='body', Key=key, Start=0, Length=len(source.rstrip()),
            MenuSignature='', RawX=c['stack'][3], RawY=c['stack'][2], Caller=c['caller'],
            FormatSHA256=digest(c['format']['text']), SHA256=digest(source), UpperCaller=w['caller'],
            UpperNative=[(w['stack'][n] & 255) * 8 for n in (2, 3)], Color=c['stack'][4] & 255)
        if source == 'Lose it? ':
            field.update(Group='footer', BackgroundOverride=7, UpperFormatSHA256=digest('%s'))
        else:
            field['BackgroundOverride'] = 23
        fields.append(field)
    assert len([f for f in fields if f['Pane'] == 'callsite']) == 5
    config['Fields'].extend(fields)
    for p in trace['paragraphs']:
        source = p['source']['text']
        assert source in ('is Hasted', 'ages') and p['caller'] == dict(Seg=0x88e, Off=0x164e)
        assert p['native_box'] == [8, 152, 312, 184]
        assert [p[n] for n in ('foreground', 'background', 'clear')] == [7, 0, 1]
        binding = dict(SHA256=digest(source), Caller=p['caller'], NativeBox=p['native_box'],
            Foreground=7, Background=0, Clear=1, Spans=[dict(Start=0, Length=len(source), Key=term(source),
                Rect=[8, 152, len(source)*8, 8])])
        if binding not in bindings:
            bindings.append(binding)
    assert len(trace['paragraphs']) == 12 and len(bindings) == 2
    config['HUDParagraphs'].extend(bindings)
    config['fine_windows'] = windows(trace)
    return config, dict(aliases=list(aliases.values()), fields=fields, contexts=contexts, rows=rows,
        menus=menus, bindings=bindings, records=hud_records(trace, config['HUDParagraphs'], dict(old_en, **{k:a['source'] for k,a in aliases.items()})))


def generate(root, target):
    probe, formal = root / 'workplace/probe', root / 'workplace/translation'
    config, data = derive(probe, formal)
    base = probe / BASE
    values = {n:catalog(base / n) for n in ('en.tsv', 'zh-TW.tsv', 'font-zh-TW.tsv')}
    zh = catalog(formal / 'zh-TW.tsv')
    for a in data['aliases']:
        values['en.tsv'][a['key']] = a['source']
        for name in ('zh-TW.tsv', 'font-zh-TW.tsv'):
            values[name][a['key']] = zh[a['formal_key']]
    glyphs = read(base / 'glyphs-16.json')
    assert not (set(''.join(values['font-zh-TW.tsv'].values())) - set('\r\n\t') - set(glyphs['glyphs'])), 'new glyphs required'
    shutil.copytree(base, target)
    proof = read(base / 'provenance.json')
    proof['exploration_cast_extension'] = dict(base=BASE, base_files={p.name:sha(p) for p in base.iterdir()},
        source_path=SOURCE, source_sha256=sha(probe / SOURCE), data=data,
        page_validation=dict(source_path=SOURCE, source_sha256=sha(probe / SOURCE)),
        formal_files={n:sha(formal / n) for n in FORMAL})
    for name, catalog_values in values.items():
        write_tsv(target / name, ['key', 'text'], catalog_values.items())
    write(target / 'inputs.json', config)
    write(target / 'provenance.json', proof)


def check_sources(inputs, config, provenance, en, zh, glyphs):
    probe, formal = inputs.parent.parent, Path('/catalogs')
    proof = provenance['exploration_cast_extension']
    base = probe / BASE
    assert proof['base'] == BASE and proof['source_path'] == SOURCE
    assert proof['base_files'] == {p.name:sha(p) for p in base.iterdir()}
    assert proof['source_sha256'] == sha(probe / SOURCE)
    assert proof['formal_files'] == {n:sha(formal / n) for n in FORMAL}
    assert proof['page_validation'] == dict(source_path=SOURCE, source_sha256=sha(probe / SOURCE))
    expected, data = derive(probe, formal)
    assert config == expected, 'exploration cast config'
    assert proof['data'] == data, 'exploration cast provenance'
    parent = read(base / 'provenance.json')
    assert {k:v for k,v in provenance.items() if k != 'exploration_cast_extension'} == parent
    old_en, old_zh, old_font = [catalog(base / n) for n in ('en.tsv', 'zh-TW.tsv', 'font-zh-TW.tsv')]
    translations = catalog(formal / 'zh-TW.tsv')
    extra = {a['key']:translations[a['formal_key']] for a in data['aliases']}
    assert en == dict(old_en, **{a['key']:a['source'] for a in data['aliases']})
    assert zh == dict(old_zh, **extra), 'exploration cast translation'
    assert catalog(inputs / 'font-zh-TW.tsv') == dict(old_font, **extra)
    assert glyphs == read(base / 'glyphs-16.json'), 'exploration cast glyphs'
    for name in set(proof['base_files']) - {'inputs.json', 'provenance.json', 'en.tsv', 'zh-TW.tsv', 'font-zh-TW.tsv'}:
        assert (inputs / name).read_bytes() == (base / name).read_bytes()
    return base, read(base / 'inputs.json'), parent, old_en, old_zh, read(base / 'glyphs-16.json')


def guards(root, output):
    source = output / 'inputs-r2'
    def check(p):
        check_sources(p, read(p/'inputs.json'), read(p/'provenance.json'), catalog(p/'en.tsv'),
            catalog(p/'zh-TW.tsv'), read(p/'glyphs-16.json'))
    check(source)
    rejected = []
    for name in ('effect-box', 'field-position', 'list-context', 'quantity', 'translation'):
        with tempfile.TemporaryDirectory(dir=output, prefix='guard-') as tmp:
            p = Path(tmp)
            shutil.copytree(source, p, dirs_exist_ok=True)
            c = read(p/'inputs.json')
            if name == 'translation':
                values = catalog(p/'zh-TW.tsv')
                values[next(iter(read(p/'provenance.json')['exploration_cast_extension']['data']['aliases']))['key']] += 'x'
                write_tsv(p/'zh-TW.tsv', ['key','text'], values.items())
            else:
                if name == 'effect-box': c['HUDParagraphs'][-1]['NativeBox'][0] += 8
                elif name == 'field-position': c['Fields'][-1]['RawX'] += 1
                elif name == 'list-context': c['PaneLists'][-1]['DescriptorSHA256'] = '0'*64
                else: c['Rows'][-1]['Spans'][0]['Length'] += 4
                write(p/'inputs.json', c)
            try: check(p)
            except AssertionError: rejected.append(name)
            else: raise AssertionError(name)
    with tempfile.TemporaryDirectory(dir=output, prefix='rebuild-') as tmp:
        p = Path(tmp)/'inputs'
        generate(root,p)
        assert {f.name:sha(f) for f in p.iterdir()} == {f.name:sha(f) for f in source.iterdir()}
    write(output/'guards.json',dict(rejected=rejected,rebuilt_files=len(list(source.iterdir()))))


def visibility(output, run):
    original = read(output/'observe-main-r2/receipt.json')
    proof = read(output/'inputs-r2/provenance.json')['exploration_cast_extension']
    data = proof['data']
    zh = read(output/run/'receipt.json')
    frames = list(zip(zh['frames'],zh['list_frames']))
    effects = []
    for record in data['records']:
        key = record['binding']['Spans'][0]['Key']
        clear = next(f for f in original['fill_events'] if f['step']>record['return_step']
            and f['native_rect'][0]<=8 and f['native_rect'][1]<=152
            and f['native_rect'][0]+f['native_rect'][2]>=80 and f['native_rect'][1]+f['native_rect'][3]>=160)
        samples = [f for f,s in frames if record['return_step']<f['step']<clear['step']
            and not f['held'] and any(w['Key']==key for w in s.get('words') or [])]
        assert samples, ('effect never visible',record['step'],key)
        during = [f for f,s in frames if record['step']<=f['step']<record['return_step']]
        assert during and all(f['held'] for f in during)
        effects.append(dict(entry=record['step'],key=key,visible_samples=len(samples),
            held_during_paint=len(during),clear_step=clear['step'],file=samples[0]['File']))
    assert len(effects)==12
    fields = {f['Key'] for f in data['fields']}
    visible = {w['Key'] for f,s in frames if not f['held'] for w in s.get('words') or []}
    assert fields <= visible, ('fields never visible',fields-visible)
    # 返回探索後，清單與本批五個新詞條都必須撤除。
    assert not any(w['Key'] in fields|{a['key'] for a in data['aliases']}
        for w in zh['list_frames'][-1].get('words') or [])
    views = []
    for label in ('open-spells','spell-down-7','cast-prohibited','decline-discard','return-exploration'):
        cp = next(c for c in zh['checkpoints'] if c['label']==label)
        frame = next(f for f in zh['frames'] if f['step']==cp['step'])
        assert not frame['held']
        views.append(dict(label=label,step=cp['step'],file=frame['File']))
    return dict(effects=effects,fields=sorted(fields),views=views,returned=True)


def review(root,output):
    from PIL import Image
    check = read(output/'check-r5.json')
    assert check['all_submitted_pixels_equal_expected']
    result = visibility(output,'zh-r4')
    try: visibility(output,'zh-r1')
    except AssertionError as error:
        assert 'effect never visible' in str(error)
        result['old_hidden_effects_rejected'] = str(error)
    else: raise AssertionError('old GUI unexpectedly visible')
    original = read(output/'observe-main-r2/receipt.json')
    runs = {lang:read(output/f'{lang}-r4/receipt.json') for lang in ('en','zh')}
    rows = read(output/'inputs-r2/provenance.json')['exploration_cast_extension']['data']['rows']
    numbers = []
    for label in ('open-spells','decline-discard'):
        cp = next(c for c in runs['zh']['checkpoints'] if c['label']==label)
        frames = {lang:next(f for f in r['frames'] if f['step']==cp['step']) for lang,r in runs.items()}
        state = next(s for s in runs['zh']['list_frames'] if s['step']==cp['step'])
        images = {lang:Image.open(output/f'{lang}-r4'/f['File']).convert('RGB') for lang,f in frames.items()}
        for row in rows:
            source = row['source']
            match = re.search(r'\([1-9][0-9]*\)$',source)
            if not match: continue
            wrappers = [w for w in original['wrappers'] if w['step']<cp['step'] and w['format']['text']=='%s'
                and w['vararg_1_candidate']['text']==source and w['caller'] in read(output/'inputs-r2/inputs.json')['RowCallers']]
            if not wrappers: continue
            w = wrappers[-1]
            x,y = [(w['stack'][n]&255)*8 for n in (2,3)]
            span = row['row']['Spans'][0]
            if not any(word['Key']==span['Key'] and (word['X'],word['Y'])==(x+span['Start']*8,y) for word in state.get('words') or []): continue
            left=x+match.start()*8
            rect=(left*2,y*2,(left+len(match[0])*8)*2,(y+8)*2)
            crops={lang:image.crop(rect).tobytes() for lang,image in images.items()}
            assert crops['en']==crops['zh'] and len(set(images['en'].crop(rect).getdata()))>1
            numbers.append(dict(label=label,source=source,quantity=match[0],rect=rect,sha256=hashlib.sha256(crops['en']).hexdigest()))
    assert len(numbers)>=4 and {n['quantity'] for n in numbers}=={'(2)','(5)'}
    result['quantity_checks'] = numbers
    write(output/'visibility-review.json',result)


def evidence(root,output):
    for name in ('native-check.json','guards.json','check-r5.json','visibility-review.json',
                 'continuation-chain.json','legacy-equality.json','legacy-current.json',
                 'rebuild-check.json','terminology-check.json'):
        assert (output/name).is_file(),name
    names={'exploration_cast_inputs.py','ui_list_live_check.py','research_storage.py'}
    pending=list(names)
    while pending:
        name=pending.pop()
        for node in ast.walk(ast.parse((root/'tools'/name).read_text())):
            modules=[node.module] if isinstance(node,ast.ImportFrom) else [a.name for a in node.names] if isinstance(node,ast.Import) else []
            for module in modules:
                candidate=(module or '').split('.')[0]+'.py'
                if candidate not in names and (root/'tools'/candidate).is_file():
                    names.add(candidate);pending.append(candidate)
    names.update(f.name for f in (output/'programs-r4').glob('*.go'))
    names.update(('oracle_video_observer.go','oracle_input_modifier.go'))
    snapshots=output/'tool-snapshots';assert not snapshots.exists();snapshots.mkdir()
    for name in sorted(names): shutil.copyfile(root/'tools'/name,snapshots/name)
    probe=root/'workplace/probe'
    sources=list((probe/BASE).iterdir())
    sources.extend(root/'workplace/translation'/n for n in FORMAL)
    sources.extend(root/'workplace/input/dos/drkqueen'/n for n in ('DQK.EXE','DISK3/ECL.GLB'))
    sources.extend(Path('/dkk/text')/n for n in ('glossary.tsv','name.zh-TW.tsv','name-lexicon-five.tsv'))
    sources.extend(probe/n for n in ('battle-text-20261024/observe-gate-r1/final.state',
        'combat-aim-route-20261024/programs-r3/ui-context-probe','combat-fire-20261025/evidence.json',
        'combat-finish-20261024/control-r4/final.state'))
    for case in ('warning','spells','magic'):
        sources.extend(probe/'combat-fire-20261025'/f'legacy-{case}-{lang}-r2/receipt.json' for lang in ('en','zh'))
    def record(p):
        s=p.stat();assert (s.st_uid,s.st_gid)==(1000,1000),p
        return dict(bytes=s.st_size,sha256=sha(p),uid=s.st_uid,gid=s.st_gid)
    assert not (output/'evidence.json').exists()
    write(output/'evidence.json',dict(draft=True,runtime_integrated=False,rights='原版、全文、字模與畫格只留本機',
        engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        effective=dict(inputs='inputs-r2',source='observe/control-main-r2',gpu='en/zh-r4',
            program='programs-r4',checks='check-r5.json',next_state='control-return-r1/final.state',
            limits='繁中只驗探索施法；首戰勝利另有原版正常按鍵分段收據，結算中文與連續戰鬥 GUI 未驗。'),
        tools={n:sha(root/'tools'/n) for n in sorted(names)},sources={str(p):record(p) for p in sources},
        artifacts={str(p.relative_to(output)):record(p) for p in sorted(output.rglob('*')) if p.is_file()}))


if __name__ == '__main__':
    command, project, directory = sys.argv[1:]
    root, output = Path(project), Path(directory)
    if command == 'native': native(root,output)
    elif command == 'prepare':
        assert read(output/'native-check.json')['checkpoints'] == 55
        generate(root,output/'inputs-r2')
    elif command == 'guards': guards(root,output)
    elif command == 'review': review(root,output)
    elif command == 'evidence': evidence(root,output)
    elif command == 'audit':
        from combat_finish_inputs import audit
        audit(root,output)
    else: raise ValueError(command)
