"""原版勝利結算的 DRAFT 顯示輸入，經驗數字保持原樣。"""
import ast
import copy
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

from literal_catalog import catalog, digest, read, sha, windows
from text_catalog import write_tsv

BASE = 'haste-battle-20261025/inputs-r2'
STUDY = 'victory-text-20261025'
SOURCE = STUDY + '/observe-r2/receipt.json'
HARBOR = STUDY + '/harbor-observe-r2/receipt.json'
CONTINUOUS = STUDY + '/continuous-observe-r1/receipt.json'
FORMAL = ('en.tsv','zh-TW.tsv','catalog.json','glossary.tsv','glossary-additions.tsv')
PREFIX = 'ui.aa90baed1dda012893d9'
STATIC = ('ui.bc4ac4b84ba534bcc525','ui.7313f57bf6d1b1f1e3db','ui.4392706a5b968abedb61')


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def counter(source,prefix):
    if not source.startswith(prefix):return None
    raw=source[len(prefix):]
    if not re.fullmatch(r'(?:0|[1-9][0-9]{0,9})',raw) or int(raw)>0xffffffff:return None
    return int(raw)


def native(root,output):
    probe=root/'workplace/probe'
    a,b=[read(output/f'{mode}-r2/receipt.json') for mode in ('observe','control')]
    for name in ('source_commit','go_version','exe_sha256','probe_sha256','state_sha256','request_sha256','request','checkpoints'):
        assert a[name]==b[name],name
    assert a['observe'] and not b['observe'] and len(a['checkpoints'])==21
    assert a['source_commit']=='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8'
    assert a['exe_sha256']=='3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
    assert a['probe_sha256']==sha(probe/'combat-aim-route-20261024/programs-r3/ui-context-probe')
    assert a['state_sha256']==sha(probe/'haste-battle-20261025/control-buffed-quick-r1/final.state')
    assert a['request_sha256']==sha(output/'request-r2.json')
    assert not any(v for k,v in a.items() if k.startswith('pending'))
    previous=read(output/'observe-r1/receipt.json')
    for name in ('calls','wrappers','paragraphs','fill_events','display_changes','menus','list_events'):
        assert a[name]==previous[name],name
    checkpoints={c['step']:c for c in previous['checkpoints']}
    for cp in a['checkpoints']:
        assert not cp['file_writes'] and not cp['unimplemented']
        if cp['step'] in checkpoints:assert cp==checkpoints[cp['step']]
        for suffix in ('.idx','.png'):
            name=cp['label']+suffix
            assert sha(output/'observe-r2'/name)==sha(output/'control-r2'/name)
    final=sha(output/'control-r2/final.state')
    assert final==sha(output/'observe-r2/final.state')==sha(probe/'haste-battle-20261025/control-return-r1/final.state')
    h,k=[read(output/f'harbor-{mode}-r2/receipt.json') for mode in ('observe','control')]
    for name in ('source_commit','go_version','exe_sha256','probe_sha256','state_sha256','request_sha256','request','checkpoints'):
        assert h[name]==k[name],name
    assert h['observe'] and not k['observe'] and len(h['checkpoints'])==16
    assert h['state_sha256']==final and h['probe_sha256']==a['probe_sha256'] and h['exe_sha256']==a['exe_sha256']
    assert h['request_sha256']==sha(output/'harbor-request-r2.json')
    assert not any(v for key,v in h.items() if key.startswith('pending'))
    prior=read(output/'harbor-observe-r1/receipt.json')
    for name in ('calls','wrappers','paragraphs','fill_events','display_changes','menus','list_events'):assert h[name]==prior[name]
    previous={c['step']:c for c in prior['checkpoints']}
    for cp in h['checkpoints']:
        assert not cp['file_writes'] and not cp['unimplemented']
        if cp['step'] in previous:assert cp==previous[cp['step']]
        for suffix in ('.idx','.png'):
            name=cp['label']+suffix
            assert sha(output/'harbor-observe-r2'/name)==sha(output/'harbor-control-r2'/name)
    harbor_final=sha(output/'harbor-control-r2/final.state')
    assert harbor_final==sha(output/'harbor-observe-r2/final.state')==sha(output/'post-observe-r3/final.state')
    c,d=[read(output/f'continuous-{mode}-r1/receipt.json') for mode in ('observe','control')]
    for name in ('source_commit','go_version','exe_sha256','probe_sha256','state_sha256','request_sha256','request','checkpoints'):
        assert c[name]==d[name],name
    assert c['observe'] and not d['observe'] and len(c['checkpoints'])==37
    assert c['state_sha256']==a['state_sha256'] and c['probe_sha256']==a['probe_sha256']
    assert c['request_sha256']==sha(output/'continuous-request-r1.json')
    assert not any(v for key,v in c.items() if key.startswith('pending'))
    combined={cp['step']:cp for cp in a['checkpoints']+h['checkpoints']}
    for cp in c['checkpoints']:
        expected=copy.deepcopy(combined[cp['step']])
        if cp['step']>a['checkpoints'][-1]['step']:
            # 獨立 oracle 程序重設研究端計數；連續路徑已消耗前段的兩鍵。
            expected['keys_consumed']+=a['checkpoints'][-1]['keys_consumed']
        assert cp==expected and not cp['file_writes'] and not cp['unimplemented']
        for suffix in ('.idx','.png'):
            name=cp['label']+suffix
            assert sha(output/'continuous-observe-r1'/name)==sha(output/'continuous-control-r1'/name)
    assert c['calls'][:len(a['calls'])]==a['calls'] and c['paragraphs']==h['paragraphs']
    assert sha(output/'continuous-observe-r1/final.state')==sha(output/'continuous-control-r1/final.state')==harbor_final
    write(output/'native-check.json',dict(checkpoints=21,source_path=SOURCE,source_sha256=sha(output/'observe-r2/receipt.json'),final_state_sha256=final,
        harbor=dict(checkpoints=16,source_path=HARBOR,source_sha256=sha(output/'harbor-observe-r2/receipt.json'),final_state_sha256=harbor_final),
        continuous=dict(checkpoints=37,source_path=CONTINUOUS,source_sha256=sha(output/'continuous-observe-r1/receipt.json'),final_state_sha256=harbor_final)))


def derive(probe,formal):
    base=probe/BASE
    config=copy.deepcopy(read(base/'inputs.json'))
    trace=read(probe/SOURCE)
    en,zh=catalog(formal/'en.tsv'),catalog(formal/'zh-TW.tsv')
    aliases=[dict(key='victory.'+digest(en[k])[:20],source=en[k],formal_key=k) for k in (*STATIC,PREFIX)]
    assert all(a['formal_key'] in zh for a in aliases)
    fields,records=[],[]
    for alias in aliases:
        source=alias['source']
        matches=[c for c in trace['calls'] if c['format']['text']=='%s' and c['vararg_1_candidate']['nul_terminated']
            and (counter(c['vararg_1_candidate']['text'],source) is not None if alias['formal_key']==PREFIX else c['vararg_1_candidate']['text']==source)]
        assert len(matches)==1,(alias,matches)
        c=matches[0];w=trace['wrappers'][c['wrapper_index']]
        assert c['caller']==dict(Seg=0xb72,Off=0x27c) and c['stack'][4]==0x87
        field=dict(Pane='callsite',Group='body',Key=alias['key'],Start=0,Length=len(source),
            MenuSignature='',RawX=c['stack'][3],RawY=c['stack'][2],Caller=c['caller'],
            FormatSHA256=digest('%s'),SHA256=digest(source),UpperCaller=w['caller'],
            UpperNative=[(w['stack'][n]&255)*8 for n in (2,3)],Color=0x87,BackgroundOverride=23)
        if alias['formal_key']==PREFIX:field['SourcePattern']='victory-experience'
        fields.append(field)
        records.append(dict(binding=field,step=c['step'],first_glyph=c['first_glyph'],return_step=c['return_step'],source=c['vararg_1_candidate']['text']))
    config['Fields'].extend(fields)
    sources={'victory':SOURCE,'harbor':HARBOR,'continuous':CONTINUOUS}
    traces={k:read(probe/path) for k,path in sources.items()}
    merged=[]
    for start,end in sorted(w for t in traces.values() for w in windows(t)):
        if merged and start<=merged[-1][1]:merged[-1][1]=max(end,merged[-1][1])
        else:merged.append([start,end])
    config['fine_windows']=merged
    paths={k:dict(source_path=path,source_sha256=sha(probe/path),records=[],
        page_validation=dict(source_path=path,source_sha256=sha(probe/path))) for k,path in sources.items()}
    return config,dict(aliases=aliases,fields=fields,field_records=records,records=[],paths=paths)


def generate(root,target):
    probe,formal=root/'workplace/probe',root/'workplace/translation'
    base=probe/BASE;config,data=derive(probe,formal)
    values={n:catalog(base/n) for n in ('en.tsv','zh-TW.tsv','font-zh-TW.tsv')}
    translated=catalog(formal/'zh-TW.tsv')
    for a in data['aliases']:
        assert a['key'] not in values['en.tsv']
        values['en.tsv'][a['key']]=a['source']
        for name in ('zh-TW.tsv','font-zh-TW.tsv'):values[name][a['key']]=translated[a['formal_key']]
    glyphs=read(base/'glyphs-16.json')
    assert not (set(''.join(values['font-zh-TW.tsv'].values()))-set('\r\n\t')-set(glyphs['glyphs'])),'new glyphs required'
    shutil.copytree(base,target)
    proof=read(base/'provenance.json')
    proof['victory_extension']=dict(base=BASE,base_files={p.name:sha(p) for p in base.iterdir()},source_path=SOURCE,
        source_sha256=sha(probe/SOURCE),data=data,page_validation=dict(source_path=SOURCE,source_sha256=sha(probe/SOURCE)),
        formal_files={n:sha(formal/n) for n in FORMAL})
    for name,v in values.items():write_tsv(target/name,['key','text'],v.items())
    write(target/'inputs.json',config);write(target/'provenance.json',proof)


def check_sources(inputs,config,provenance,en,zh,glyphs):
    probe,formal=inputs.parent.parent,Path('/catalogs')
    proof=provenance['victory_extension'];base=probe/BASE
    assert proof['base']==BASE and proof['source_path']==SOURCE
    assert proof['base_files']=={p.name:sha(p) for p in base.iterdir()}
    assert proof['source_sha256']==sha(probe/SOURCE)
    assert proof['formal_files']=={n:sha(formal/n) for n in FORMAL}
    assert proof['page_validation']==dict(source_path=SOURCE,source_sha256=sha(probe/SOURCE))
    expected,data=derive(probe,formal)
    assert config==expected,'victory config'
    assert proof['data']==data,'victory provenance'
    parent=read(base/'provenance.json')
    assert {k:v for k,v in provenance.items() if k!='victory_extension'}==parent
    old_en,old_zh,old_font=[catalog(base/n) for n in ('en.tsv','zh-TW.tsv','font-zh-TW.tsv')]
    translated=catalog(formal/'zh-TW.tsv');extra={a['key']:translated[a['formal_key']] for a in data['aliases']}
    assert en==dict(old_en,**{a['key']:a['source'] for a in data['aliases']})
    assert zh==dict(old_zh,**extra),'victory translation'
    assert catalog(inputs/'font-zh-TW.tsv')==dict(old_font,**extra)
    assert glyphs==read(base/'glyphs-16.json'),'victory glyphs'
    for n in set(proof['base_files'])-{'inputs.json','provenance.json','en.tsv','zh-TW.tsv','font-zh-TW.tsv'}:
        assert (inputs/n).read_bytes()==(base/n).read_bytes(),n
    return base,read(base/'inputs.json'),parent,old_en,old_zh,read(base/'glyphs-16.json')


def guards(root,output):
    source=output/'inputs-r3'
    def check(p):check_sources(p,read(p/'inputs.json'),read(p/'provenance.json'),catalog(p/'en.tsv'),catalog(p/'zh-TW.tsv'),read(p/'glyphs-16.json'))
    check(source);rejected=[]
    for name in ('number-mask','caller','prefix','translation','glyph'):
        with tempfile.TemporaryDirectory(dir=output,prefix='guard-') as tmp:
            p=Path(tmp);shutil.copytree(source,p,dirs_exist_ok=True);c=read(p/'inputs.json')
            if name=='number-mask':c['Fields'][-1]['Length']+=4;write(p/'inputs.json',c)
            elif name=='caller':c['Fields'][-1]['UpperCaller']['Off']+=1;write(p/'inputs.json',c)
            elif name=='glyph':
                g=read(p/'glyphs-16.json');g['glyphs'].pop(next(iter(g['glyphs'])));write(p/'glyphs-16.json',g)
            else:
                locale='en.tsv' if name=='prefix' else 'zh-TW.tsv';v=catalog(p/locale)
                v['victory.aa90baed1dda012893d9']+='x';write_tsv(p/locale,['key','text'],v.items())
            try:check(p)
            except AssertionError:rejected.append(name)
            else:raise AssertionError(name)
    with tempfile.TemporaryDirectory(dir=output,prefix='rebuild-') as tmp:
        p=Path(tmp)/'inputs';generate(root,p)
        assert {f.name:sha(f) for f in p.iterdir()}=={f.name:sha(f) for f in source.iterdir()}
    write(output/'guards.json',dict(rejected=rejected,rebuilt_files=len(list(source.iterdir()))))


def review(root,output):
    from PIL import Image
    assert read(output/'continuous-check-r2.json')['all_submitted_pixels_equal_expected']
    en,zh=[read(output/f'continuous-{lang}-r1/receipt.json') for lang in ('en','zh')]
    data=read(output/'inputs-r3/provenance.json')['victory_extension']['data']
    samples=[]
    for record in data['field_records']:
        key=record['binding']['Key']
        visible=[f for f,s in zip(zh['frames'],zh['list_frames']) if not f['held'] and any(w['Key']==key for w in s.get('words') or [])]
        assert visible,('victory field invisible',key)
        samples.append(dict(key=key,visible_samples=len(visible),first_file=visible[0]['File']))
    assert not any(w['Key'] in {a['key'] for a in data['aliases']} for w in zh['list_frames'][-1].get('words') or [])
    prefix=next(a['source'] for a in data['aliases'] if a['formal_key']==PREFIX)
    numbers=[];cache={}
    for a,b,s in zip(en['frames'],zh['frames'],zh['list_frames']):
        if b['held'] or not any(w['Key']=='victory.aa90baed1dda012893d9' for w in s.get('words') or []):continue
        c=next(r for r in data['field_records'] if r['binding']['Key']=='victory.aa90baed1dda012893d9')
        number=counter(c['source'],prefix);assert number is not None
        rect=((8+len(prefix)*8)*2,80,(8+len(prefix)*8+len(str(number))*8)*2,96)
        values=[]
        for lang,f in [('en',a),('zh',b)]:
            token=lang,f['File']
            if token not in cache:cache[token]=Image.open(output/f'continuous-{lang}-r1'/f['File']).convert('RGB')
            values.append(cache[token].crop(rect).tobytes())
        assert values[0]==values[1] and len(set(cache[('en',a['File'])].crop(rect).getdata()))>1
        numbers.append(dict(step=a['step'],value=number,rect=rect))
    assert numbers
    key='ecl.982f1eb13cedddcf0d19'
    story=[f for f,s in zip(zh['frames'],zh['list_frames']) if not f['held'] and s.get('paragraph') and key in s['paragraph']['Components']]
    assert story and zh['list_frames'][-1].get('paragraph') is None
    write(output/'visibility-review.json',dict(fields=samples,number_checks=numbers,returned=True,
        harbor=dict(key=key,visible_samples=len(story),first_file=story[0]['File'],cleared=True)))


def evidence(root,output):
    for name in ('continuous-check-r2.json','native-check.json','guards.json','visibility-review.json',
                 'counter-test.log','parent-equality.json','rebuild-check.json','dock-source-check.json','quote-diagnostic.json'):
        assert (output/name).is_file(),name
    names={'victory_ui_inputs.py','ui_list_live_check.py','research_storage.py'}
    pending=list(names)
    while pending:
        name=pending.pop()
        for node in ast.walk(ast.parse((root/'tools'/name).read_text())):
            modules=[node.module] if isinstance(node,ast.ImportFrom) else [a.name for a in node.names] if isinstance(node,ast.Import) else []
            for module in modules:
                candidate=(module or '').split('.')[0]+'.py'
                if candidate not in names and (root/'tools'/candidate).is_file():
                    names.add(candidate);pending.append(candidate)
    names.update(f.name for f in (output/'programs-r1').glob('*.go'))
    names.update(('oracle_video_observer.go','oracle_input_modifier.go','ui_victory_counter_test.go'))
    snapshots=output/'tool-snapshots';assert not snapshots.exists();snapshots.mkdir()
    for name in sorted(names):shutil.copyfile(root/'tools'/name,snapshots/name)
    probe=root/'workplace/probe'
    sources=list((probe/BASE).iterdir())
    sources.extend(root/'workplace/translation'/n for n in FORMAL)
    sources.extend(root/'workplace/input/dos/drkqueen'/n for n in ('DQK.EXE','DISK3/ECL.GLB'))
    sources.extend(Path('/dkk/text')/n for n in ('glossary.tsv','name.zh-TW.tsv','name-lexicon-five.tsv'))
    sources.extend(probe/n for n in ('haste-battle-20261025/control-buffed-quick-r1/final.state',
        'haste-battle-20261025/control-return-r1/final.state','haste-battle-20261025/programs-r4/ui-list-live',
        'haste-battle-20261025/evidence.json','combat-aim-route-20261024/programs-r3/ui-context-probe',
        'combat-finish-20261024/control-r4/final.state'))
    sources.extend(probe/'haste-battle-20261025'/f'{lang}-r4/receipt.json' for lang in ('en','zh'))
    def record(p):
        s=p.stat();assert (s.st_uid,s.st_gid)==(1000,1000),p
        return dict(bytes=s.st_size,sha256=sha(p),uid=s.st_uid,gid=s.st_gid)
    assert not (output/'evidence.json').exists()
    write(output/'evidence.json',dict(draft=True,runtime_integrated=False,rights='原版、全文、字模及畫格只留本機',
        engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        effective=dict(inputs='inputs-r3',source='continuous-observe/control-r1',gpu='continuous-en/zh-r1',
            program='programs-r1',checks='continuous-check-r2.json',next_state='dock-control-r1/final.state',
            limits='繁中連續驗到港口敘事；船長對話只有原版控制組及粗粒度漏譯診斷，不列中文通過。'),
        tools={n:sha(root/'tools'/n) for n in sorted(names)},sources={str(p):record(p) for p in sources},
        artifacts={str(p.relative_to(output)):record(p) for p in sorted(output.rglob('*')) if p.is_file()}))


if __name__=='__main__':
    command,project,directory=sys.argv[1:];root,output=Path(project),Path(directory)
    if command=='native':native(root,output)
    elif command=='prepare':
        assert read(output/'native-check.json')['continuous']['checkpoints']==37
        generate(root,output/'inputs-r3')
    elif command=='guards':guards(root,output)
    elif command=='review':review(root,output)
    elif command=='evidence':evidence(root,output)
    elif command=='audit':
        from combat_finish_inputs import audit
        audit(root,output)
    else:raise ValueError(command)
