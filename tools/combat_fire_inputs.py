"""正常自動施法支線的 DRAFT 火焰、防護與武器顯示資料。"""
import ast
import copy
import hashlib
from pathlib import Path
import re
import shutil
import sys
import tempfile

from bar_ui_inputs import write
from combat_rounds_inputs import hud_records
from literal_catalog import catalog, digest, read, sha, windows
from text_catalog import write_tsv

BASE = 'combat-aim-route-20261024/inputs-r3'
STUDY = 'combat-fire-20261025'
FORMAL = ('en.tsv', 'zh-TW.tsv', 'catalog.json', 'glossary.tsv', 'glossary-additions.tsv')
COUNTS = (25, 19, 28, 12)
RUNS = (2, 2, 2, 1)


def native(root, output):
    probe = root / 'workplace/probe'
    initial = read(output / 'initial-sources.json')
    result = {}
    for name, count, run in zip(map(str, range(1, 5)), COUNTS, RUNS):
        observed, control = [read(output / f'{mode}-p{name}-r{run}/receipt.json') for mode in ('observe', 'control')]
        for key in ('source_commit', 'go_version', 'exe_sha256', 'probe_sha256', 'state_sha256', 'request_sha256', 'request', 'checkpoints'):
            assert observed[key] == control[key], (name, key)
        assert observed['observe'] and not control['observe'] and len(observed['checkpoints']) == count
        assert observed['state_sha256'] == initial[name]['state_sha256'] == sha(probe / initial[name]['state'])
        assert observed['source_commit'] == 'f79eab6db8c64a524a06535e53e5d32b0bbcf7c8'
        assert observed['exe_sha256'] == '3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
        assert observed['probe_sha256'] == sha(probe / 'combat-aim-route-20261024/programs-r3/ui-context-probe')
        assert observed['request_sha256'] == sha(output / f'request-p{name}-r{run}.json')
        assert not any(value for key, value in observed.items() if key.startswith('pending'))
        previous = read(probe / initial[name]['previous_trace'])
        assert sha(probe / initial[name]['previous_trace']) == initial[name]['previous_trace_sha256']
        prefix = {c['step']: c for c in previous['checkpoints']}
        compared = 0
        for checkpoint in observed['checkpoints']:
            assert not checkpoint['file_writes'] and not checkpoint['unimplemented']
            for suffix in ('.png', '.idx'):
                f = checkpoint['label'] + suffix
                assert sha(output / f'observe-p{name}-r{run}' / f) == sha(output / f'control-p{name}-r{run}' / f)
            if checkpoint['step'] in prefix:
                assert checkpoint == prefix[checkpoint['step']]
                compared += 1
        assert compared >= (8 if name == '4' else 16)
        assert sha(output / f'observe-p{name}-r{run}/final.state') == sha(output / f'control-p{name}-r{run}/final.state')
        result[name] = dict(source_path=f'{STUDY}/observe-p{name}-r{run}/receipt.json',
            source_sha256=sha(output / f'observe-p{name}-r{run}/receipt.json'), checkpoints=count,
            previous_checkpoints_equal=compared,
            final_state_sha256=sha(output / f'control-p{name}-r{run}/final.state'))
    write(output / 'native-check-r2.json', result)


def copy_witnesses(root, output):
    from PIL import Image
    probe=root/'workplace/probe'
    result={}
    for n,run in enumerate(RUNS,1):
        main=read(output/f'observe-p{n}-r{run}/receipt.json')
        a,b=[read(output/f'copy-{mode}-p{n}-r1/receipt.json') for mode in ('observe','control')]
        for key in ('source_commit','go_version','exe_sha256','probe_sha256','state_sha256','request_sha256','request','checkpoints'):
            assert a[key]==b[key],(n,key)
        for key in ('source_commit','go_version','exe_sha256','probe_sha256','state_sha256','calls','paragraphs','wrappers','fill_events','display_changes','menus','hud_panels'):
            assert a[key]==main[key],(n,key)
        assert a['request_sha256']==sha(output/f'copy-request-p{n}-r1.json')
        assert not any(value for key,value in a.items() if key.startswith('pending'))
        assert sha(output/f'copy-observe-p{n}-r1/final.state')==sha(output/f'copy-control-p{n}-r1/final.state')==sha(output/f'control-p{n}-r{run}/final.state')
        previous={c['label']:c for c in main['checkpoints']}
        images=[]
        for checkpoint in a['checkpoints']:
            assert not checkpoint['file_writes'] and not checkpoint['unimplemented']
            for suffix in ('.png','.idx'):
                name=checkpoint['label']+suffix
                assert sha(output/f'copy-observe-p{n}-r1'/name)==sha(output/f'copy-control-p{n}-r1'/name)
                if checkpoint['label'] in previous:
                    assert checkpoint==previous[checkpoint['label']]
                    assert sha(output/f'copy-observe-p{n}-r1'/name)==sha(output/f'observe-p{n}-r{run}'/name)
            if not checkpoint['label'].startswith('copy-display-'):continue
            path=output/f'copy-observe-p{n}-r1'/(checkpoint['label']+'.png')
            idx=path.with_suffix('.idx').read_bytes()
            assert hashlib.sha256(idx).hexdigest()==checkpoint['indexed_sha256']
            with Image.open(path) as image:
                assert image.size==(320,200)
                assert image.convert('RGB').tobytes()==b''.join(bytes(checkpoint['palette'][v]) for v in idx)
            images.append(dict(step=checkpoint['step'],path=str(path.relative_to(probe)),sha256=sha(path)))
        assert len(images)==len(a['checkpoints'])-len(main['checkpoints'])
        result[str(n)]=dict(source_path=f'{STUDY}/copy-observe-p{n}-r1/receipt.json',source_sha256=sha(output/f'copy-observe-p{n}-r1/receipt.json'),
            original_checkpoints=len(previous),extra_checkpoints=len(images),images=images)
    return result


def derive(root):
    probe = root / 'workplace/probe'
    base, output = probe / BASE, probe / STUDY
    formal = root / 'workplace/translation'
    en, zh = catalog(formal / 'en.tsv'), catalog(formal / 'zh-TW.tsv')
    parent_en, parent_zh = catalog(base / 'en.tsv'), catalog(base / 'zh-TW.tsv')
    config = copy.deepcopy(read(base / 'inputs.json'))
    aliases, bindings, fields, paths, fine = {}, [], [], {}, []

    def alias(source, translation, keys, prefix='fire.'):
        key = prefix + digest(source)[:20]
        item = dict(key=key, source=source, translation=translation, formal_keys=keys)
        assert key not in parent_en
        if key in aliases:
            assert aliases[key] == item
        aliases[key] = item
        return key

    def term(source):
        found = [key for key, text in parent_en.items() if text == source and key in parent_zh]
        if found:
            assert len({parent_zh[key] for key in found}) == 1
            return min(found)
        if source.startswith('Spell:'):
            argument = source.removeprefix('Spell:')
            choices = [key for key, text in en.items() if text == argument and key in zh]
            assert choices, source
            key = min(choices)
            template = 'ui.0eab976d6f20cabc5ca7'
            assert en[template].replace('%s', en[key]) == source
            return alias(source, zh[template].replace('%s', zh[key]), [template, key], 'fire-spell.')
        choices = [key for key, text in en.items() if text == source and key in zh]
        if source == 'Javelins':
            choices = ['ui.3331d5456d2d5b84ac4b']
            assert en[choices[0]] == 'Javelin'
        assert choices, source
        assert len({zh[key] for key in choices}) == 1
        key = min(choices)
        return alias(source, zh[key], [key])

    fire_parts = ['ui.0047c0cbccc6f94c1ac8', 'ui.f5e1d63728c2e2d27737', 'ui.47604718a30bfd03e5f6']
    pattern = en[fire_parts[0]].replace('%s', en[fire_parts[2]].replace('%s', en[fire_parts[1]]))
    translated = zh[fire_parts[0]].replace('%s', zh[fire_parts[2]].replace('%s', zh[fire_parts[1]]))
    fire_key = alias(pattern, translated, fire_parts, 'fire-format.')
    binding = dict(SHA256=digest(pattern), Caller=dict(Seg=0x88e, Off=0x15e1), NativeBox=[184,88,312,176],
        Foreground=7, Background=0, Clear=1, IntegerTemplateKey=fire_key, OrdinaryDamage=True, HideFooter=True,
        Spans=[dict(Start=0, Length=len(pattern), Key=fire_key, Rect=[184,88,128,88])])
    config['HUDParagraphs'].append(binding)
    bindings.append(binding)
    for name, proof in read(output / 'native-check-r2.json').items():
        source = probe / proof['source_path']
        assert sha(source) == proof['source_sha256']
        trace = read(source)
        fine.extend(windows(trace))
        for i, paragraph in enumerate(trace['paragraphs']):
            text = paragraph['source']['text']
            if not text.strip():
                continue
            all_en = dict(parent_en, **{a['key']:a['source'] for a in aliases.values()})
            known = hud_records(trace, config['HUDParagraphs'], all_en)
            if i in {r['index'] for r in known}:
                continue
            weapon = paragraph['caller'] == dict(Seg=0x88e, Off=0x97e)
            x,y,right,bottom = paragraph['native_box']
            assert [paragraph[k] for k in ('foreground','background','clear')] == [7,0,1]
            assert paragraph['caller'] == dict(Seg=0x88e, Off=0x97e if weapon else 0x15e1)
            spans = []
            quantity = re.fullmatch(r'([12]) (Javelins?) \+2 ', text) if weapon else None
            if quantity:
                assert quantity[2] == ('Javelins' if quantity[1] == '2' else 'Javelin')
                key = term(quantity[2])
                spans = [dict(Start=2, Length=len(quantity[2]), Key=key, Rect=[200,56,len(quantity[2])*8,8])]
            elif weapon and text == 'Composite Long Bow +2 ':
                full_key = 'ui.842c3f9a91518c4bb5f9'
                assert en[full_key] == text[:18] and len(zh[full_key]) == 4
                for start,length,translation,rect in [(0,14,zh[full_key][:3],[184,56,112,8]), (15,3,zh[full_key][3:],[184,64,24,8])]:
                    key = alias(text[start:start+length], translation, [full_key], 'fire-bow.')
                    spans.append(dict(Start=start, Length=length, Key=key, Rect=rect))
            else:
                assert not weapon, ('unknown weapon', text)
                key = term(text)
                spans = [dict(Start=0, Length=len(text), Key=key, Rect=[x,y,right-x,bottom-y])]
            binding = dict(SHA256=digest(text), Caller=paragraph['caller'], NativeBox=paragraph['native_box'],
                Foreground=7, Background=0, Clear=1, Spans=spans)
            if not weapon and y == 88:
                binding['HideFooter'] = True
            assert binding not in config['HUDParagraphs']
            config['HUDParagraphs'].append(binding)
            bindings.append(binding)
        captions = []
        for index, wrapper in enumerate(trace['wrappers']):
            text = wrapper['format']['text']
            if wrapper['caller'] != dict(Seg=0x2c4a, Off=0x4630) or not text.startswith('Spell:'):
                continue
            key = term(text)
            call, = [c for c in trace['calls'] if c['wrapper_index'] == index and c['format']['text'] == '%s']
            assert call['vararg_1_candidate']['text'] == text and call['caller'] == dict(Seg=0xb72, Off=0x27c)
            assert call['stack'][2:5] == [8089,8004,0x8f]
            f = dict(Pane='callsite', Group='footer', Key=key, Start=0, Length=len(text), SHA256=digest(text),
                FormatSHA256=digest('%s'), Caller=call['caller'], UpperCaller=wrapper['caller'], UpperNative=[0,184],
                RawX=8004, RawY=8089, Color=0x8f, MenuSignature='')
            if f not in config['Fields']:
                config['Fields'].append(f)
                fields.append(dict(step=call['step'], source=text, binding=f))
            checkpoint, = [c for c in trace['checkpoints'] if c['step'] == wrapper['return_step']]
            native_index = source.parent / checkpoint['indexed_file']
            assert sha(native_index) == checkpoint['indexed_sha256']
            raw = native_index.read_bytes()
            rect = [8,178,len(text)*8,8]
            pixels = b''.join(raw[y*320+8:y*320+8+rect[2]] for y in range(178,186))
            captions.append(dict(key=key, entry=call['step'], ready=wrapper['return_step'], rect=rect,
                ready_index=str(native_index.relative_to(probe)), reference_sha256=hashlib.sha256(pixels).hexdigest(),
                palette=checkpoint['palette'], label=checkpoint['label']))
        paths[name] = dict(proof, captions=captions,
            page_validation=dict(source_path=proof['source_path'], source_sha256=proof['source_sha256']))
    all_en = dict(parent_en, **{a['key']:a['source'] for a in aliases.values()})
    for path in paths.values():
        path['records'] = hud_records(read(probe / path['source_path']), config['HUDParagraphs'], all_en)
    merged = []
    for start,end in sorted(fine):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start,end])
    config['fine_windows'] = merged
    return config, dict(aliases=list(aliases.values()), bindings=bindings, fields=fields, paths=paths)


def generate(root, target):
    base = root / 'workplace/probe' / BASE
    config, data = derive(root)
    shutil.copytree(base, target)
    for name,column in [('en.tsv','source'), ('zh-TW.tsv','translation'), ('font-zh-TW.tsv','translation')]:
        values = catalog(base / name)
        values.update({a['key']:a[column] for a in data['aliases']})
        write_tsv(target / name, ['key','text'], values.items())
    missing = set(''.join(a['translation'] for a in data['aliases'])) - set(read(base / 'glyphs-16.json')['glyphs']) - set('\n\r\t')
    assert not missing, ('缺字',missing)
    proof = read(base / 'provenance.json')
    formal = root / 'workplace/translation'
    proof['fire_extension'] = dict(base=BASE, base_files={f.name:sha(f) for f in base.iterdir()},
        formal_files={n:sha(formal / n) for n in FORMAL}, data=data)
    write(target / 'inputs.json', config)
    write(target / 'provenance.json', proof)


def check_sources(inputs, config, proof, en, zh, glyphs):
    root = inputs.parent.parent.parent.parent
    base = root / 'workplace/probe' / BASE
    expected,data = derive(root)
    assert config == expected, 'fire config'
    formal = root / 'workplace/translation'
    assert proof['fire_extension'] == dict(base=BASE, base_files={f.name:sha(f) for f in base.iterdir()},
        formal_files={n:sha(formal / n) for n in FORMAL}, data=data), 'fire provenance'
    parent = read(base / 'provenance.json')
    assert {k:v for k,v in proof.items() if k != 'fire_extension'} == parent
    old_en,old_zh = catalog(base / 'en.tsv'),catalog(base / 'zh-TW.tsv')
    assert en == dict(old_en, **{a['key']:a['source'] for a in data['aliases']})
    assert zh == dict(old_zh, **{a['key']:a['translation'] for a in data['aliases']}), 'fire translation'
    assert catalog(inputs / 'font-zh-TW.tsv') == dict(catalog(base / 'font-zh-TW.tsv'), **{a['key']:a['translation'] for a in data['aliases']})
    assert glyphs == read(base / 'glyphs-16.json'), 'fire glyphs'
    for path in base.iterdir():
        if path.name not in ('inputs.json','provenance.json','en.tsv','zh-TW.tsv','font-zh-TW.tsv'):
            assert (inputs / path.name).read_bytes() == path.read_bytes(), path.name
    return base,read(base / 'inputs.json'),parent,old_en,old_zh,read(base / 'glyphs-16.json')


def guards(root, output):
    source = output / 'inputs-r2'
    def check(p):
        return check_sources(p,read(p/'inputs.json'),read(p/'provenance.json'),catalog(p/'en.tsv'),catalog(p/'zh-TW.tsv'),read(p/'glyphs-16.json'))
    check(source)
    rejected = []
    for name in ('caller','number','weapon-span','field-position','translation','glyph'):
        with tempfile.TemporaryDirectory(dir=output,prefix='guard-') as temporary:
            p = Path(temporary)
            shutil.copytree(source,p,dirs_exist_ok=True)
            c,v = read(p/'inputs.json'),read(p/'provenance.json')
            if name == 'number':
                next(r for r in v['fire_extension']['data']['paths']['1']['records'] if r['number'] is not None)['number'] += 1
            elif name == 'translation':
                z = catalog(p/'zh-TW.tsv')
                z[v['fire_extension']['data']['aliases'][0]['key']] += 'x'
                write_tsv(p/'zh-TW.tsv',['key','text'],z.items())
            elif name == 'glyph':
                g = read(p/'glyphs-16.json');g['glyphs'].pop(next(iter(g['glyphs'])));write(p/'glyphs-16.json',g)
            elif name == 'field-position':
                c['Fields'][-1]['RawY'] += 1
                v['fire_extension']['data']['fields'][-1]['binding'] = copy.deepcopy(c['Fields'][-1])
            else:
                b = next(b for b in c['HUDParagraphs'] if any(s['Start']==2 for s in b['Spans']))
                if name == 'caller':b['Caller']['Off'] += 1
                else:b['Spans'][0]['Start'] += 1
                v['fire_extension']['data']['bindings'] = copy.deepcopy(c['HUDParagraphs'][-len(v['fire_extension']['data']['bindings']):])
            write(p/'inputs.json',c);write(p/'provenance.json',v)
            try:
                check(p)
            except AssertionError as error:
                assert str(error) in ('fire config','fire provenance','fire translation','fire glyphs'), (name,error)
                rejected.append(name)
            else:
                raise AssertionError(name)
    with tempfile.TemporaryDirectory(dir=output,prefix='rebuild-') as temporary:
        target = Path(temporary)/'inputs'
        generate(root,target)
        assert {p.name for p in target.iterdir()} == {p.name for p in source.iterdir()}
        for p in source.iterdir():
            assert p.read_bytes() == (target/p.name).read_bytes(),p.name
    write(output/'guards-r2.json',dict(rejected=rejected,rebuilt_files=len(list(source.iterdir()))))


def review(root, output):
    from PIL import Image
    from ui_list_live_check import read as read_frames
    base = output/'inputs-r2'
    config,data = derive(root)
    source,translated = catalog(base/'en.tsv'),catalog(base/'zh-TW.tsv')
    added = {digest(str(b)):b for b in data['bindings']}
    visible_bindings, caption_intervals, numeric_regions, views = set(), [], 0, {}
    for name,path in data['paths'].items():
        check = read(output/f'check-p{name}-r1.json')
        assert check['all_submitted_pixels_equal_expected'] and check['fire']['source_path']==path['source_path']
        runs = {lang:read_frames(output/f'p{name}-{lang}-r4/receipt.json') for lang in ('en','zh')}
        a,b = runs['en'],runs['zh']
        crop_cache = {}
        def crop(lang,frame,rect):
            token = (lang,frame['File'],tuple(rect))
            if token not in crop_cache:
                x,y,w,h=rect
                with Image.open(output/f'p{name}-{lang}-r4'/frame['File']) as image:
                    crop_cache[token]=image.convert('RGB').crop((x*2,y*2,(x+w)*2,(y+h)*2)).tobytes()
            return crop_cache[token]
        for original,frame,state in zip(a['frames'],b['frames'],b['list_frames']):
            assert original['step']==frame['step']==state['step']
            if frame['held']:
                continue
            words=state.get('words') or []
            for record in path['records']:
                binding=record['binding'];token=digest(str(binding))
                if token not in added or frame['step']<record['return_step']:
                    continue
                keys={s['Key'] for s in binding['Spans']}
                if keys <= {w['Key'] for w in words}:
                    visible_bindings.add(token)
                    views.setdefault(record['source'],dict(case=name,step=frame['step'],
                        en=f'p{name}-en-r4/'+original['File'],zh=f'p{name}-zh-r4/'+frame['File']))
                else:
                    continue
                quantity=re.fullmatch(r'([12]) (Javelins?) \+2 ',record['source'])
                rectangles=[]
                if quantity:
                    rectangles=[[184,56,16,8],[184+(3+len(quantity[2]))*8,56,16,8]]
                elif record['source']=='Composite Long Bow +2 ':
                    rectangles=[[216,64,16,8]]
                for rect in rectangles:
                    pixels=crop('en',original,rect)
                    assert pixels==crop('zh',frame,rect),('weapon number',name,frame['step'],rect)
                    assert len(set(zip(pixels[::3],pixels[1::3],pixels[2::3])))>1,('blank weapon number',name,frame['step'],rect)
                    numeric_regions+=1
        for i,witness in enumerate(path['captions']):
            rect=witness['rect'];x,y,w,h=rect
            idx=(root/'workplace/probe'/witness['ready_index']).read_bytes()
            native_rgb=Image.frombytes('RGB',(320,200),b''.join(bytes(witness['palette'][v]) for v in idx))
            expected=native_rgb.crop((x,y,x+w,y+h)).resize((w*2,h*2),Image.Resampling.NEAREST).tobytes()
            end=path['captions'][i+1]['entry'] if i+1<len(path['captions']) else b['checkpoints'][-1]['step']+1
            retained=retired=0
            for original,frame,state in zip(a['frames'],b['frames'],b['list_frames']):
                if frame['held'] or not witness['ready']<frame['step']<end:
                    continue
                present=any(word['Key']==witness['key'] for word in state.get('words') or [])
                unchanged=crop('en',original,rect)==expected
                assert present==unchanged,('spell caption lifecycle',name,witness['key'],frame['step'],present,unchanged)
                if unchanged:
                    retained+=1
                    views.setdefault(source[witness['key']],dict(case=name,step=frame['step'],
                        en=f'p{name}-en-r4/'+original['File'],zh=f'p{name}-zh-r4/'+frame['File']))
                else:retired+=1
            assert retained,(name,witness['key'],retained,retired)
            continued=False
            if not retired:
                assert i==len(path['captions'])-1,(name,witness['key'],'missing original clear')
                last_frame,last_state=b['frames'][-1],b['list_frames'][-1]
                assert not last_frame['held'] and crop('en',a['frames'][-1],rect)==expected
                assert any(word['Key']==witness['key'] for word in last_state.get('words') or [])
                continued=True
            caption_intervals.append(dict(case=name,key=witness['key'],retained=retained,retired=retired,continued_at_end=continued))
        if name=='3':
            checkpoint=next(c for c in b['checkpoints'] if c['label']=='report-22')
            frame=next(f for f in b['frames'] if f['step']==checkpoint['step'])
            state=next(s for s in b['list_frames'] if s['step']==checkpoint['step'])
            original=next(f for f in a['frames'] if f['step']==checkpoint['step'])
            word,=[w for w in state['words'] if w['Key']=='hud-format.66e294009f6a0a6b1d62']
            assert word['Number']==11 and word.get('Height',8)==8 and not frame['held']
            old={lang:read_frames(output/f'p3-{lang}-r3/receipt.json') for lang in ('en','zh')}
            old_frames={lang:next(f for f in run['frames'] if f['step']==checkpoint['step']) for lang,run in old.items()}
            assert (output/'p3-en-r3'/old_frames['en']['File']).read_bytes()==(output/'p3-en-r4'/original['File']).read_bytes()
            with Image.open(output/'p3-zh-r3'/old_frames['zh']['File']) as image:
                old_row=image.convert('RGB').crop((368,176,624,192)).tobytes()
            assert old_row==crop('en',original,[184,88,128,8]),'old English leak not reproduced'
            assert old_row!=crop('zh',frame,[184,88,128,8]),'new damage translation missing'
            views['spell-interruption-fixed']=dict(case=name,step=frame['step'],en=f'p3-en-r4/'+original['File'],zh=f'p3-zh-r4/'+frame['File'])
    assert visible_bindings==set(added),('unseen added bindings',set(added)-visible_bindings)
    assert numeric_regions>0
    write(output/'visibility-review-r2.json',dict(added_bindings_visible=len(visible_bindings),
        captions=caption_intervals,numeric_regions_equal=numeric_regions,partial_clear_regression=True,views=views))


def evidence(root, output):
    for name in ('native-check-r2.json','guards-r2.json','visibility-review-r2.json','term-alignment.json','copy-witnesses.json',
                 'binary-rebuild.json','legacy-equality.json','run-r1.json','commands-r1.json','hygiene-r1.json',
                 *(f'check-p{n}-r1.json' for n in range(1,5))):
        assert (output/name).is_file(),name
    names={'combat_fire_inputs.py','ui_list_live_check.py','ui_context_probe.go','oracle_video_observer.go',
           'oracle_input_modifier.go','ui-context.sh','ui-list-live.sh','early-live.sh','research_storage.py'}
    names.update(p.name for p in (output/'programs-r4').glob('*.go'))
    pending=list(names)
    while pending:
        name=pending.pop()
        if not name.endswith('.py'):continue
        for node in ast.walk(ast.parse((root/'tools'/name).read_text())):
            modules=[node.module] if isinstance(node,ast.ImportFrom) else [a.name for a in node.names] if isinstance(node,ast.Import) else []
            for module in modules:
                candidate=(module or '').split('.')[0]+'.py'
                if candidate not in names and (root/'tools'/candidate).is_file():
                    names.add(candidate);pending.append(candidate)
    snapshots=output/'tool-snapshots'
    assert not snapshots.exists()
    snapshots.mkdir()
    for name in sorted(names):shutil.copyfile(root/'tools'/name,snapshots/name)
    probe=root/'workplace/probe'
    sources=list((probe/BASE).iterdir())
    sources.extend(root/'workplace/translation'/name for name in FORMAL)
    sources.extend(root/'workplace/input/dos/drkqueen'/name for name in ('DQK.EXE','DISK3/ECL.GLB'))
    for item in read(output/'initial-sources.json').values():
        sources.extend(probe/item[name] for name in ('state','previous_trace'))
    sources.extend(probe/name for name in ('combat-aim-route-20261024/evidence.json',
        'combat-aim-route-20261024/programs-r3/ui-context-probe','combat-aim-route-20261024/programs-r5/ui-list-live',
        'combat-finish-20261024/control-r4/final.state'))
    sources.extend(Path('/dkk/text')/name for name in ('glossary.tsv','name.zh-TW.tsv','name-lexicon-five.tsv'))
    def record(path):
        info=path.stat()
        assert (info.st_uid,info.st_gid)==(1000,1000),path
        return dict(bytes=info.st_size,sha256=sha(path),uid=info.st_uid,gid=info.st_gid)
    assert not (output/'evidence.json').exists()
    write(output/'evidence.json',dict(draft=True,runtime_integrated=False,rights='原版、全文、字模及畫格只留本機',
        engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        effective=dict(inputs='inputs-r2',frontend='programs-r4',gpu='p1..4-en/zh-r4',
            native_runs=list(RUNS),checks='check-p1..4-r1.json',limits='四段正常首戰快照；包含敗北，不宣稱勝利、整場或正式入口'),
        tools={name:sha(root/'tools'/name) for name in sorted(names)},
        sources={str(path):record(path) for path in sources},
        artifacts={str(path.relative_to(output)):record(path) for path in sorted(output.rglob('*')) if path.is_file()}))


if __name__ == '__main__':
    command,root,output = sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3])
    if command == 'native':native(root,output)
    elif command == 'prepare':generate(root,output/'inputs-r2')
    elif command == 'guards':guards(root,output)
    elif command == 'copies':write(output/'copy-witnesses.json',copy_witnesses(root,output))
    elif command == 'review':review(root,output)
    elif command == 'evidence':evidence(root,output)
    elif command == 'audit':
        from combat_finish_inputs import audit
        audit(root,output)
    else:raise SystemExit(command)
