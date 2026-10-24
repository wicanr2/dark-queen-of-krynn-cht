"""全冊手札引用的 DRAFT 資料；完整來源與顯示語境共同辨識。"""
import ast
import base64
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from literal_catalog import catalog, digest, read, sha, windows
from text_catalog import decode6

BASE = 'combat-rounds-20261024/inputs-r6'
STUDY = 'journal-references-20261024'
TEMPLATE = 'ui.aa93370ee0689e9a462e'
FORMAL = ('en.tsv', 'zh-TW.tsv', 'catalog.json', 'glossary.tsv', 'glossary-additions.tsv')
# 固定圓體、16×20、Pillow 11.3.0 的新增字模見證；不在 Git 保存字模像素。
EXTRA_GLYPHS = {'冊': '472a264ba98e1ed2411c0f4c66e86051f9771ee830283daf5e6ce8278657cf30'}
LITERAL_IDS = {
    'ecl.cebe248eb5a12c58345e': 39, 'ecl.343b2defdb962a661579': 7,
    'ecl.a009fe4812e8bb40e573': 56, 'ecl.9d85a84571b31de4f0ba': 23,
    'ecl.7889f96fe232e846977a': 2, 'ecl.c5081d302c08d5b49090': 17,
    'ecl.2d07e522eb8268f57a6c': 49, 'ecl.bb1f434e4ccb2c00fe38': 5,
    'ecl.644fefe0dbad36054e38': 9,
}
PATHS = {
    '54': ('pane-render-20261022/observe-palace-journal-r1',
           'pane-render-20261022/control-palace-journal-r1', 'save-load-city-20261022/inn.state'),
    '65': ('battle-text-20261024/observe-arrival-r2',
           'battle-text-20261024/control-arrival-r2', 'battle-text-20261024/control-journey-r2/final.state'),
}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def native(root, output):
    reports = {}
    for entry, (old_observed, _, state) in PATHS.items():
        a, b = [read(output / f'{mode}-{entry}-r1/receipt.json') for mode in ('observe', 'control')]
        old = read(root / 'workplace/probe' / old_observed / 'receipt.json')
        for key in ('source_commit', 'go_version', 'exe_sha256', 'probe_sha256', 'state_sha256',
                    'request_sha256', 'request', 'checkpoints'):
            assert a[key] == b[key], (entry, key)
        assert a['observe'] and not b['observe']
        assert a['source_commit'] == 'f79eab6db8c64a524a06535e53e5d32b0bbcf7c8'
        assert a['exe_sha256'] == '3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
        assert a['state_sha256'] == sha(root / 'workplace/probe' / state)
        assert not any(v for key, v in a.items() if key.startswith('pending'))
        assert [{k:v for k,v in c.items() if k!='indexed_file'} for c in a['checkpoints']] == [
            {k:v for k,v in c.items() if k!='indexed_file'} for c in old['checkpoints'][:len(a['checkpoints'])]]
        for cp in a['checkpoints']:
            assert not cp['file_writes'] and not cp['unimplemented']
            for suffix in ('.idx', '.png'):
                name = cp['label'] + suffix
                assert sha(output / f'observe-{entry}-r1' / name) == sha(output / f'control-{entry}-r1' / name)
                previous = root / 'workplace/probe' / old_observed / name
                if previous.exists():
                    assert sha(output / f'observe-{entry}-r1' / name) == sha(previous)
                else:
                    assert suffix=='.idx' and sha(output / f'observe-{entry}-r1' / name)==cp['indexed_sha256']
        assert sha(output / f'observe-{entry}-r1/final.state') == sha(output / f'control-{entry}-r1/final.state')
        reports[entry] = dict(source_path=f'{STUDY}/observe-{entry}-r1/receipt.json',
            source_sha256=sha(output / f'observe-{entry}-r1/receipt.json'),
            state=state, checkpoints=len(a['checkpoints']),
            page_validation=dict(source_path=f'{STUDY}/observe-{entry}-r1/receipt.json',
                sha256=sha(output / f'observe-{entry}-r1/receipt.json')))
    write(output / 'native-check.json', reports)
    return reports


def derive(root):
    probe = root / 'workplace/probe'; texts = root / 'workplace/translation'
    base = probe / BASE; output = probe / STUDY
    config = copy.deepcopy(read(base / 'inputs.json'))
    en, zh = [catalog(base / name) for name in ('en.tsv', 'zh-TW.tsv')]
    formal_en, formal_zh = [catalog(texts / name) for name in ('en.tsv', 'zh-TW.tsv')]
    entries = {r['key']: r for r in read(texts / 'catalog.json')['entries']}
    raw = (root / 'workplace/input/dos/drkqueen/DISK3/ECL.GLB').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '40542071e42d3cd125eabcead11456a99942bf55a7736fdb79f66a3c27c3664d'
    reader = catalog(base / 'reader.zh-TW.tsv')
    ids = sorted(int(k.split('.')[1]) for k in reader if re.fullmatch(r'journal\.[0-9]+\.title', k))
    assert ids == [n for n in range(1, 69) if n != 13]
    added = []; aliases = {}; sources = []; paths = {}; fine = []
    existing = {json.dumps(p, sort_keys=True) for p in config['Paragraphs']}

    def append(binding):
        signature = json.dumps(binding, sort_keys=True)
        if signature not in existing:
            existing.add(signature); added.append(binding)

    # 可用編號只由已載入標題決定，不補造缺號；文字由正式模板衍生。
    template = next(p for p in config['Paragraphs'] if p.get('JournalEntry') == 54)
    assert en[TEMPLATE] == formal_en[TEMPLATE] and zh[TEMPLATE] == formal_zh[TEMPLATE]
    for number in ids:
        source = en[TEMPLATE].replace('%s', str(number))
        target = zh[TEMPLATE].replace('%s', str(number))
        key = 'message.' + digest(source)[:20]
        if key not in en:
            aliases[key] = dict(source=source, translation=target, template_key=TEMPLATE, entry=number)
        else:
            assert en[key] == source and zh[key] == target
        binding = dict(template, Key=key, SHA256=digest(source), JournalEntry=number)
        append(binding)

    for key, number in LITERAL_IDS.items():
        source, target = formal_en[key], formal_zh[key]
        assert key not in en and key == 'ecl.' + digest(source)[:20]
        assert len(target) <= 144 and '\\' not in source + target and '%' not in source + target
        assert re.search(r' AS JOURNAL ENTRY (?:# )?' + str(number) + r'\.$', source)
        assert source.count('JOURNAL ENTRY') == 1
        row = entries[key]; assert row['text'] == source
        opcodes = set()
        for occurrence in row['sources']:
            at = occurrence['file_offset']; size = occurrence['packed_length']
            packet = raw[at - 1:at + 2 + size]
            assert packet[0] in (0x11, 0x12) and packet[1:3] == bytes((0x80, size))
            assert decode6(packet[3:]) == source
            opcodes.add(packet[0])
            sources.append(dict(key=key, entry=number, **occurrence, opcode=packet[0],
                packet_sha256=hashlib.sha256(packet).hexdigest()))
        aliases[key] = dict(source=source, translation=target, formal_key=key, entry=number)
        for opcode in sorted(opcodes):
            for color in (3, 7):
                append(dict(Key=key, SHA256=digest(source), Caller=dict(Seg=0x26b4, Off=0x1d81 if opcode==0x12 else 0x1d53),
                    NativeBox=[8,136,312,184], Foreground=color, Background=0, Clear=int(opcode==0x12), JournalEntry=number))
    assert len(aliases) == 75 and len(added) == 84 and len(sources) == 9
    config['Paragraphs'].extend(added)
    for entry, (_, _, state) in PATHS.items():
        observed = output / f'observe-{entry}-r1/receipt.json'; trace = read(observed)
        paths[entry] = dict(source_path=f'{STUDY}/observe-{entry}-r1/receipt.json', source_sha256=sha(observed), state=state,
            page_validation=dict(source_path=f'{STUDY}/observe-{entry}-r1/receipt.json', sha256=sha(observed)))
        fine.extend(windows(trace))
    config['fine_windows'] = sorted(fine)
    proof = dict(base=BASE, base_files={f.name:sha(f) for f in base.iterdir()},
        formal_files={n:sha(texts/n) for n in FORMAL}, aliases=aliases, added=added, sources=sources,
        ids=ids, paths=paths, runtime_coverage_unknown=True, raw_sha256=hashlib.sha256(raw).hexdigest())
    return config, proof


def generate(root, target):
    base = root/'workplace/probe'/BASE; config, extension = derive(root)
    assert not target.exists(); shutil.copytree(base, target)
    proof = read(base/'provenance.json'); proof['journal_reference_extension'] = extension
    write(target/'inputs.json', config); write(target/'provenance.json', proof)
    for name in ('en.tsv', 'zh-TW.tsv', 'font-zh-TW.tsv'):
        values = catalog(base/name)
        values.update({k:v['source' if name=='en.tsv' else 'translation'] for k,v in extension['aliases'].items()})
        (target/name).write_text('key\ttext\n'+''.join(k+'\t'+v+'\n' for k,v in sorted(values.items())))
    glyphs = read(base/'glyphs-16.json')
    missing = set(''.join(catalog(target/'font-zh-TW.tsv').values())) - glyphs['glyphs'].keys()
    if missing:
        with tempfile.TemporaryDirectory(dir=target.parent, prefix='glyph-') as directory:
            temp = Path(directory); font = Path('/dkk/font/jf-openhuninn-2.1.ttf')
            (temp/'added.tsv').write_text('key\ttext\nreference-added\t'+''.join(sorted(missing))+'\n')
            subprocess.run([sys.executable, str(root/'tools/menu_glyphs.py'), str(font), str(temp/'added.tsv'), str(temp/'glyphs.json'), '16'], check=True)
            extra = read(temp/'glyphs.json')
            assert all(extra[n]==glyphs[n] for n in ('size','height','font_sha256'))
            for ch in missing:
                value = extra['glyphs'][ch]; raw = base64.b64decode(value)
                assert len(raw)==320 and not any(raw[256:])
                glyphs['glyphs'][ch] = value
    write(target/'glyphs-16.json', glyphs)
    print(json.dumps(dict(aliases=len(extension['aliases']), bindings=len(extension['added']), glyphs=len(glyphs['glyphs']), missing_added=sorted(missing)),ensure_ascii=False))


def check_sources(inputs, config, proof, en, zh, glyphs):
    root = inputs.parents[3]; base = root/'workplace/probe'/BASE
    expected, extension = derive(root)
    assert config == expected, 'journal reference config'
    assert proof['journal_reference_extension'] == extension, 'journal reference provenance'
    parent = read(base/'provenance.json')
    assert {k:v for k,v in proof.items() if k!='journal_reference_extension'} == parent
    old_en, old_zh = catalog(base/'en.tsv'), catalog(base/'zh-TW.tsv')
    assert en == dict(old_en, **{k:v['source'] for k,v in extension['aliases'].items()})
    assert zh == dict(old_zh, **{k:v['translation'] for k,v in extension['aliases'].items()})
    for name in set(extension['base_files'])-{'inputs.json','provenance.json','en.tsv','zh-TW.tsv','font-zh-TW.tsv','glyphs-16.json'}:
        assert (inputs/name).read_bytes() == (base/name).read_bytes(), name
    old_glyphs = read(base/'glyphs-16.json')
    for key,value in old_glyphs['glyphs'].items(): assert glyphs['glyphs'][key] == value
    assert all(glyphs[n]==old_glyphs[n] for n in ('size','height','font_sha256'))
    text = catalog(inputs/'font-zh-TW.tsv')
    assert text == dict(catalog(base/'font-zh-TW.tsv'), **{k:v['translation'] for k,v in extension['aliases'].items()})
    assert set(glyphs['glyphs']) == set(old_glyphs['glyphs']) | set(''.join(text.values()))
    assert all(len(base64.b64decode(v))==320 and not any(base64.b64decode(v)[256:]) for v in glyphs['glyphs'].values())
    assert set(glyphs['glyphs'])-old_glyphs['glyphs'].keys() == EXTRA_GLYPHS.keys()
    assert all(hashlib.sha256(base64.b64decode(glyphs['glyphs'][ch])).hexdigest()==h for ch,h in EXTRA_GLYPHS.items()), 'journal reference glyph'
    return base, read(base/'inputs.json'), parent, old_en, old_zh, old_glyphs


def guards(root, output):
    source=output/'inputs-r1'; cases=[]
    def check(path):
        return check_sources(path, read(path/'inputs.json'), read(path/'provenance.json'),
            catalog(path/'en.tsv'), catalog(path/'zh-TW.tsv'), read(path/'glyphs-16.json'))
    check(source)
    for name in ('ordinal', 'opcode-context', 'omit-reference', 'missing-13', 'packet-offset',
                 'translation', 'glyph', 'reader', 'source'):
        with tempfile.TemporaryDirectory(dir=output, prefix='guard-') as directory:
            path=Path(directory);shutil.copytree(source,path,dirs_exist_ok=True)
            config=read(path/'inputs.json');proof=read(path/'provenance.json');extension=proof['journal_reference_extension']
            if name in ('ordinal','opcode-context','omit-reference'):
                key='ecl.bb1f434e4ccb2c00fe38' if name=='ordinal' else 'ecl.cebe248eb5a12c58345e'
                for item in (config['Paragraphs'],extension['added']):
                    if name=='omit-reference':item[:]=[p for p in item if p['Key']!=key]
                    else:
                        for p in item:
                            if p['Key']==key:
                                if name=='ordinal':p['JournalEntry']=6
                                else:p['Caller']['Off']=0x1d81;p['Clear']=1
                if name=='ordinal':extension['aliases'][key]['entry']=6
                if name=='omit-reference':del extension['aliases'][key]
            elif name=='missing-13':extension['ids'].append(13)
            elif name=='packet-offset':extension['sources'][0]['file_offset']+=1
            elif name=='translation':
                key=next(k for k in extension['aliases'] if k.startswith('ecl.'))
                old=extension['aliases'][key]['translation'];extension['aliases'][key]['translation']='錯誤'
                (path/'zh-TW.tsv').write_text((path/'zh-TW.tsv').read_text().replace(key+'\t'+old,key+'\t錯誤'))
            elif name=='glyph':
                g=read(path/'glyphs-16.json');g['glyphs']['冊']=base64.b64encode(bytes(320)).decode();write(path/'glyphs-16.json',g)
            elif name=='reader':(path/'reader.zh-TW.tsv').write_text((path/'reader.zh-TW.tsv').read_text().replace('journal.54.body','journal.13.body'))
            else:(path/'en.tsv').write_text((path/'en.tsv').read_text().replace('JOURNAL ENTRY # 5.','JOURNAL ENTRY # 6.'))
            write(path/'inputs.json',config);write(path/'provenance.json',proof)
            try:check(path)
            except AssertionError:cases.append(name)
            else:raise AssertionError('變造未拒絕：'+name)
    with tempfile.TemporaryDirectory(dir=output,prefix='rebuild-') as directory:
        target=Path(directory)/'inputs';generate(root,target)
        assert {f.name for f in target.iterdir()}=={f.name for f in source.iterdir()}
        for f in source.iterdir():assert f.read_bytes()==(target/f.name).read_bytes(),f.name
    write(output/'guards-r1.json',dict(cases=cases,rebuilt_files=len(list(source.iterdir())),tool_sha256=sha(Path(__file__))))


def review(root, output):
    from PIL import Image, ImageDraw
    from ui_list_live_check import read as read_compact
    cases={};panels=[]
    for entry in PATHS:
        report=read(output/f'check-{entry}-r2.json')
        assert report['checker_sha256']==sha(root/'tools/ui_list_live_check.py')
        assert report['all_submitted_pixels_equal_expected']
        en,zh=[read_compact(output/f'j{entry}-{lang}-r1/receipt.json') for lang in ('en','zh')]
        assert report['en_receipt_sha256']==sha(output/f'j{entry}-en-r1/receipt.json')
        assert report['zh_receipt_sha256']==sha(output/f'j{entry}-zh-r1/receipt.json')
        opened=[e for e in zh['reader_events'] or [] if e['action']=='open']
        closed=[e for e in zh['reader_events'] or [] if e['action']=='close']
        assert len(opened)==len(closed)==1 and opened[0]['page']['Entry']==closed[0]['entry']==int(entry)
        assert opened[0]['step']<closed[0]['step']
        assert {int(k) for k in zh['reader_seen']}=={int(entry)}
        indices=[i for i,(f,s) in enumerate(zip(zh['frames'],zh['list_frames'])) if not f['held'] and s['reader'] and s['reader']['Entry']==int(entry)]
        assert indices and all(opened[0]['step']<=zh['frames'][i]['step']<=closed[0]['step'] for i in indices)
        closing_index=next(i for i,e in enumerate(zh['list_events']) if e['Step']==closed[0]['step'])
        for i in indices:
            if zh['frames'][i]['step']==closed[0]['step']:
                # 原指令尚未執行，與關閉回呼同一步數的畫格仍可保有舊書頁。
                assert zh['list_frames'][i]['list_event_count']<=closing_index
        restore=next(i for i,(f,s) in enumerate(zip(zh['frames'],zh['list_frames'])) if f['step']>closed[0]['step'] and not f['held'] and s['reader'] is None)
        for label,index in (('open',indices[0]),('restored',restore)):
            frame=zh['frames'][index];original=next(f for f in en['frames'] if f['step']==frame['step'])
            panels.append((entry,label,frame['step'],[Image.open(output/f'j{entry}-{lang}-r1'/f['File']).convert('RGB') for lang,f in (('en',original),('zh',frame))]))
        cases[entry]=dict(real_gpu_pairs=report['real_gpu_readback_frames'],held_pairs=report['held_frames'],
            checkpoints=report['original_checkpoints_equal'],visible_reader_frames=len(indices),open=opened[0]['step'],close=closed[0]['step'],
            seen=[int(entry)],final_reader=zh['final_reader'])
        assert zh['final_reader'] is None
    panel=Image.new('RGB',(1280,len(panels)*420),'#202020');draw=ImageDraw.Draw(panel)
    for row,(entry,label,step,images) in enumerate(panels):
        for col,image in enumerate(images):
            panel.paste(image,(col*640,row*420+20));draw.text((col*640+4,row*420+2),f'journal {entry} / {label} / {step} / '+('en' if col==0 else 'zh'),fill='white')
    panel.save(output/'review-r1.png')
    write(output/'visibility-review-r1.json',dict(cases=cases,normal_entries=[54,65],new_normal_entries=[],
        normal_new_literals_observed=0,real_gpu_pairs=sum(v['real_gpu_pairs'] for v in cases.values()),
        held_pairs=sum(v['held_pairs'] for v in cases.values()),scope='新引用資料的正常第 54／65 則回歸；其他 75 別名不列為已走過原版引用。'))


def evidence(root, output):
    assert read(output/'guards-r1.json')['tool_sha256']==sha(Path(__file__))
    for name in ('native-check.json','guards-r1.json','test-r3.log','binary-rebuild-r2.json','parent-check-r1.json',
                 'json-reader-check-r1.json','catalog-coverage-r1.json','visibility-review-r1.json','run-r1.json'):
        assert (output/name).is_file(),name
    assert '--- PASS: TestJournalLiteralOriginalSources' in (output/'test-r3.log').read_text()
    assert '--- PASS: TestJournalLiteralCanonicalNumbers' in (output/'test-r3.log').read_text()
    names={'journal_reference_inputs.py','ui_list_live_check.py','ui_journal_reference_test.go',
           'ui_journal_reader_check.py','ui_journal_illustrations_check.py','ui-context.sh','ui-list-live.sh','early-live.sh','menu_glyphs.py'}
    names.update(p.name for p in (output/'programs-r1').glob('*.go'))
    names.update(p.name for p in (output/'source-programs-r3').glob('*.go'))
    pending=list(names)
    while pending:
        name=pending.pop()
        if not name.endswith('.py'):continue
        for node in ast.walk(ast.parse((root/'tools'/name).read_text())):
            imports=[node.module] if isinstance(node,ast.ImportFrom) else [a.name for a in node.names] if isinstance(node,ast.Import) else []
            for item in imports:
                candidate=(item or '').split('.')[0]+'.py'
                if candidate not in names and (root/'tools'/candidate).is_file():names.add(candidate);pending.append(candidate)
    snapshots=output/'tool-snapshots';assert not snapshots.exists();snapshots.mkdir()
    for name in sorted(names):shutil.copyfile(root/'tools'/name,snapshots/name)
    sources=list((root/'workplace/probe'/BASE).iterdir())
    sources.extend(root/'workplace/translation'/n for n in FORMAL)
    sources.extend(root/'workplace/input/dos/drkqueen'/n for n in ('DQK.EXE','DISK3/ECL.GLB'))
    sources.extend(root/'workplace/probe'/v[2] for v in PATHS.values())
    sources.append(Path('/dkk/font/jf-openhuninn-2.1.ttf'))
    def record(path):
        s=path.stat();assert (s.st_uid,s.st_gid)==(1000,1000),path
        return dict(bytes=s.st_size,sha256=sha(path),uid=s.st_uid,gid=s.st_gid)
    write(output/'evidence.json',dict(draft=True,runtime_integrated=False,rights='原版、全文、字模及畫格僅留本機',
        engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        effective=dict(inputs='inputs-r1',program='programs-r1',source_program='source-programs-r1（與原來源路徑 r3 二進位相同）',
            gpu='j54/j65-en/zh-r1',checks='check-54/check-65-r2',unused='inputs-r2 僅未執行的細驗視窗草稿'),
        tools={n:sha(root/'tools'/n) for n in names},sources={str(p):record(p) for p in sources},
        artifacts={str(p.relative_to(output)):record(p) for p in sorted(output.rglob('*')) if p.is_file()}))


if __name__ == '__main__':
    command, root, output = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    if command == 'native': native(root, output)
    elif command == 'prepare': generate(root, output/'inputs-r1')
    elif command == 'guards': guards(root, output)
    elif command == 'review': review(root, output)
    elif command == 'evidence': evidence(root, output)
    elif command == 'audit':
        from combat_finish_inputs import audit
        audit(root, output)
    else: raise SystemExit('native | prepare | guards | review | evidence | audit')
