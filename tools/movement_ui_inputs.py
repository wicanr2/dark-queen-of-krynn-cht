"""正常方向鍵及復原／完成兩路的移動力底列，僅供 DRAFT。"""
import ast
import copy
import hashlib
from pathlib import Path
import re
import shutil
import sys
import tempfile

from bar_ui_inputs import write
from combat_effects_inputs import FORMAL, hud_records
from literal_catalog import catalog, digest, read, sha, windows
from text_catalog import write_tsv

BASE = 'combat-finish-20261024/inputs-r4'
STUDY = 'combat-movement-20261024'
QUICK = 'combat-finish-20261024/observe-r4/receipt.json'
SOURCES = {'done':STUDY+'/observe-r3/receipt.json', 'undo':STUDY+'/observe-undo-r1/receipt.json','quick':QUICK}
PREFIX = 'ui.5af65b05298fbefb97ac'


def counter(source, prefix):
    if not source.startswith(prefix): return None
    raw = source[len(prefix):]
    number = raw.strip()
    if not re.fullmatch(r'0|[1-9][0-9]*', number): return None
    value = int(number)
    if value > 2**31-1 or raw not in (str(value), str(value).rjust(2)+' '): return None
    return value


def quick_witness(probe,prefix):
    path=probe/STUDY/'caption-control-r1'
    control=read(path/'receipt.json');source=read(probe/QUICK)
    call=next(c for c in source['calls'] if c['format']['text']=='%s' and c['vararg_1_candidate']['text'].startswith(prefix))
    wrapper=source['wrappers'][call['wrapper_index']]
    assert control['state_sha256']==source['state_sha256'] and control['request']['start_steps']==source['request']['start_steps']
    assert control['request']['actions']==[dict(at=3571000000,end=wrapper['return_step'],kind='text',key='q',label='quick-caption-ready')]
    assert control['checkpoints'][0]['step']==wrapper['return_step'] and not control['checkpoints'][0]['file_writes'] and not control['checkpoints'][0]['unimplemented']
    raw=(path/'quick-caption-ready.idx').read_bytes()
    blank=(probe/'combat-finish-20261024/control-r4/breath-lightning.idx').read_bytes()
    def crop(data,rect):
        x,y,w,h=rect;return b''.join(data[row*320+x:row*320+x+w] for row in range(y,y+h))
    assert crop(raw,[160,179,40,8])==crop(blank,[160,179,40,8])
    rect=[8,189,len(prefix)*8,8]
    return dict(control_path=STUDY+'/caption-control-r1/receipt.json',control_sha256=sha(path/'receipt.json'),
        indexed_path=STUDY+'/caption-control-r1/quick-caption-ready.idx',indexed_sha256=sha(path/'quick-caption-ready.idx'),
        step=wrapper['return_step'],native_rect=rect,reference_sha256=hashlib.sha256(crop(raw,rect)).hexdigest(),
        removed_button_rect=[160,179,40,8],blank_path='combat-finish-20261024/control-r4/breath-lightning.idx',blank_sha256=sha(probe/'combat-finish-20261024/control-r4/breath-lightning.idx'))


def derive(probe, texts):
    base = probe/BASE
    config = copy.deepcopy(read(base/'inputs.json'))
    en, zh = catalog(texts/'en.tsv'), catalog(texts/'zh-TW.tsv')
    parent_en, parent_zh = catalog(base/'en.tsv'), catalog(base/'zh-TW.tsv')
    output = probe/STUDY
    controls_en, controls_zh = catalog(output/'controls.en.tsv'), catalog(output/'controls.zh-TW.review.tsv')
    assert set(controls_en) == set(controls_zh) == {'movement.undo'}
    assert controls_en['movement.undo'] == 'Undo' and controls_zh['movement.undo']
    prefix = en[PREFIX]
    assert prefix and 'ui.'+digest(prefix)[:20] == PREFIX
    aliases, fields, menus = [], [], []
    def select(source):
        choices = [k for k,v in parent_en.items() if v==source and k in parent_zh]
        if choices:
            assert len({parent_zh[k] for k in choices}) == 1
            return min(choices)
        previous = [a for a in aliases if a['source']==source]
        if previous: return previous[0]['key']
        choices = [k for k,v in en.items() if v==source and k in zh]
        if choices:
            assert len({zh[k] for k in choices}) == 1
            key = min(choices)
            aliases.append(dict(key=key, source=source, translation=zh[key], formal_keys=choices))
        else:
            choices = [k for k,v in controls_en.items() if v==source]
            assert len(choices)==1
            key = choices[0]
            aliases.append(dict(key=key, source=source, translation=controls_zh[key], controls_key=key))
        return key
    assert select(prefix) == PREFIX
    binding = dict(Pane='callsite', Group='footer', Key=PREFIX, SourcePattern='movement-left',
        Start=0, Length=len(prefix), SHA256=digest(prefix), FormatSHA256=digest('%s'),
        Caller=dict(Seg=0xb72,Off=0x27c), UpperCaller=dict(Seg=0xceb,Off=0x995),
        UpperFormatSHA256=digest('%s'),UpperNative=[0,192],RawX=8004,RawY=189,Color=0x70,BackgroundOverride=7,MenuSignature='')
    assert binding not in config['Fields']
    config['Fields'].append(binding)
    fields.append(dict(source=prefix,binding=binding))
    quick_binding=copy.deepcopy(binding)
    quick_binding.update(UpperCaller=dict(Seg=0x29e0,Off=0x74f),UpperFormatSHA256='',Color=0x8f)
    del quick_binding['BackgroundOverride']
    config['Fields'].append(quick_binding)
    fields.append(dict(source=prefix,binding=quick_binding))
    traces = {name:read(probe/path) for name,path in SOURCES.items()}
    for trace in traces.values():
        for menu in trace['menus'] or []:
            if menu['Signature'] in config['Menus']: continue
            labels = [bytes.fromhex(b['SourceHex']).decode() for b in menu['Buttons']]
            assert (menu['Count'] in (3,12) and labels==['Undo','Done']) or (
                menu['Count']==10 and labels==['Aim','Use','Cast','Guard','Quick','Delay','View','Speed','End'])
            config['Menus'][menu['Signature']] = 'combat'
            menus.append(menu)
            native = lambda value:value if value<400 else (value-8000)*2
            for button,source in zip(menu['Buttons'],labels):
                f = dict(Pane='menu',Group='footer',Key=select(source),Start=0,Length=len(source),
                    SHA256=button['SHA256'],FormatSHA256=button['SHA256'],Caller=dict(Seg=0xceb,Off=0x1be),
                    RawX=native(button['RawX']),RawY=native(button['RawY'])+1,MenuSignature=menu['Signature'])
                config['Fields'].append(f)
                fields.append(dict(source=source,binding=f))
    all_en = dict(parent_en,**{a['key']:a['source'] for a in aliases})
    paths = {}
    for name,trace in traces.items():
        active=quick_binding if name=='quick' else binding
        records = []
        for c in trace['calls']:
            source = c['vararg_1_candidate']['text']
            if c['format']['text']!='%s' or not source.startswith(prefix): continue
            value = counter(source,prefix)
            assert value is not None and c['caller']==active['Caller']
            assert c['stack'][2:5]==[189,8004,active['Color']] and c['wrapper_index']>=0
            wrapper = trace['wrappers'][c['wrapper_index']]
            assert wrapper['caller']==active['UpperCaller']
            if name=='quick':assert wrapper['format']['text']==source
            else:assert wrapper['format']['text']=='%s' and wrapper['vararg_1_candidate']['text']==source
            assert [(wrapper['stack'][n]&255)*8 for n in (2,3)]==active['UpperNative']
            assert c['step']<c['first_glyph']<c['return_step']<=wrapper['return_step']
            assert c['vararg_1_candidate']['nul_terminated'] and bytes.fromhex(c['vararg_1_candidate']['hex']).decode()==source
            assert len(c['video_pages'])==1
            records.append(dict(step=c['step'],first_glyph=c['first_glyph'],returned=c['return_step'],source=source,value=value,
                native_digits=[8+len(prefix)*8,189,(len(source)-len(prefix))*8,8]))
        assert [r['value'] for r in records]==([12] if name=='quick' else [11,10,9])
        path = SOURCES[name]
        paths[name] = dict(source_path=path,source_sha256=sha(probe/path),counters=records,
            records=hud_records(trace,config['HUDParagraphs'],all_en),page_validation=dict(source_path=path,source_sha256=sha(probe/path)))
    quick = read(probe/QUICK)
    candidates = [c for c in quick['calls'] if c['format']['text']=='%s' and c['vararg_1_candidate']['text'].startswith(prefix)]
    assert len(candidates)==1
    q=candidates[0];qw=quick['wrappers'][q['wrapper_index']]
    assert counter(q['vararg_1_candidate']['text'],prefix)==12 and q['stack'][2:5]==[189,8004,0x8f]
    assert q['caller']==quick_binding['Caller'] and qw['caller']==quick_binding['UpperCaller']
    assert qw['format']['text']==q['vararg_1_candidate']['text']
    assert [(qw['stack'][n]&255)*8 for n in (2,3)]==[0,192]
    assert q['step']<q['first_glyph']<q['return_step']<=qw['return_step']
    intervals = [v for trace in traces.values() for v in windows(trace)]
    merged = []
    for start,end in sorted(intervals):
        if merged and start<=merged[-1][1]: merged[-1][1]=max(end,merged[-1][1])
        else: merged.append([start,end])
    config['fine_windows'] = merged
    return config,dict(aliases=aliases,fields=fields,menus=menus,paths=paths,quick_source=QUICK,quick_sha256=sha(probe/QUICK),quick_witness=quick_witness(probe,prefix))


def font_values(probe,data):
    return dict(catalog(probe/BASE/'font-zh-TW.tsv'),**{a['key']:a['translation'] for a in data['aliases']})


def glyph_inputs(root, output):
    probe=root/'workplace/probe';_,data=derive(probe,root/'workplace/translation')
    old=read(probe/BASE/'glyphs-16.json')
    missing=set(''.join(font_values(probe,data).values()))-set('\r\n\t')-set(old['glyphs'])
    write_tsv(output/'glyph-source.tsv',['key','text'],(('glyph.'+format(ord(c),'x'),c) for c in sorted(missing)))
    print('new glyphs',sorted(missing))


def merged_glyphs(probe,data):
    old=read(probe/BASE/'glyphs-16.json');new=read(probe/STUDY/'glyphs-added-16.json')
    assert all(old[k]==new[k] for k in ('size','height','font_sha256'))
    missing=set(''.join(font_values(probe,data).values()))-set('\r\n\t')-set(old['glyphs'])
    assert set(new['glyphs'])==missing
    result=copy.deepcopy(old);result['glyphs'].update(new['glyphs']);return result


def generate(root,target):
    probe=root/'workplace/probe';texts=root/'workplace/translation';base=probe/BASE
    config,data=derive(probe,texts)
    shutil.copytree(base,target)
    for name,column in [('en.tsv','source'),('zh-TW.tsv','translation'),('font-zh-TW.tsv','translation')]:
        values=catalog(base/name);values.update({a['key']:a[column] for a in data['aliases']})
        write_tsv(target/name,['key','text'],values.items())
    proof=read(base/'provenance.json')
    proof['movement_extension']=dict(base=BASE,base_files={f.name:sha(f) for f in base.iterdir()},data=data,
        formal_files={n:sha(texts/n) for n in FORMAL},controls={n:sha(probe/STUDY/n) for n in ('controls.en.tsv','controls.zh-TW.review.tsv')})
    write(target/'inputs.json',config);write(target/'provenance.json',proof);write(target/'glyphs-16.json',merged_glyphs(probe,data))


def check_sources(inputs,config,proof,en,zh,glyphs):
    probe=inputs.parent.parent;base=probe/BASE;texts=Path('/catalogs')
    expected,data=derive(probe,texts);item=proof['movement_extension']
    assert config==expected,'movement config'
    assert item==dict(base=BASE,base_files={f.name:sha(f) for f in base.iterdir()},data=data,
        formal_files={n:sha(texts/n) for n in FORMAL},controls={n:sha(probe/STUDY/n) for n in ('controls.en.tsv','controls.zh-TW.review.tsv')}),'movement provenance'
    parent=read(base/'provenance.json');assert {k:v for k,v in proof.items() if k!='movement_extension'}==parent
    old_en,old_zh=catalog(base/'en.tsv'),catalog(base/'zh-TW.tsv')
    assert en==dict(old_en,**{a['key']:a['source'] for a in data['aliases']})
    assert zh==dict(old_zh,**{a['key']:a['translation'] for a in data['aliases']}),'movement translation'
    assert catalog(inputs/'font-zh-TW.tsv')==font_values(probe,data) and glyphs==merged_glyphs(probe,data)
    for name in item['base_files']:
        if name not in ('inputs.json','provenance.json','en.tsv','zh-TW.tsv','font-zh-TW.tsv','glyphs-16.json'):
            assert (inputs/name).read_bytes()==(base/name).read_bytes(),name
    return base,read(base/'inputs.json'),parent,old_en,old_zh,read(base/'glyphs-16.json')


def guards(root,output):
    source=output/'inputs-r3'
    def check(p):return check_sources(p,read(p/'inputs.json'),read(p/'provenance.json'),catalog(p/'en.tsv'),catalog(p/'zh-TW.tsv'),read(p/'glyphs-16.json'))
    check(source);cases=[]
    for name in ('caller','pattern','color','numeric-mask','menu-button','translation'):
        with tempfile.TemporaryDirectory(dir=output,prefix='guard-') as d:
            p=Path(d);shutil.copytree(source,p,dirs_exist_ok=True);c=read(p/'inputs.json')
            b=next(f for f in c['Fields'] if f.get('SourcePattern')=='movement-left')
            if name=='translation':
                z=catalog(p/'zh-TW.tsv');z[PREFIX]+='99';write_tsv(p/'zh-TW.tsv',['key','text'],z.items())
            else:
                if name=='caller':b['UpperCaller']['Off']+=1
                elif name=='pattern':b['SourcePattern']='created-name'
                elif name=='color':b['Color']=0x8f
                elif name=='numeric-mask':b['Width']=216
                else:c['Fields'].pop()
                write(p/'inputs.json',c)
            try:check(p)
            except AssertionError as e:assert str(e)==('movement translation' if name=='translation' else 'movement config'),(name,e)
            else:raise AssertionError(name)
            cases.append(name)
    with tempfile.TemporaryDirectory(dir=output,prefix='rebuild-') as d:
        p=Path(d)/'inputs';generate(root,p)
        assert {f.name for f in p.iterdir()}=={f.name for f in source.iterdir()}
        for f in source.iterdir():assert f.read_bytes()==(p/f.name).read_bytes(),f.name
    write(output/'guards.json',dict(cases=cases,rebuilt_files=len(list(source.iterdir())),tool_sha256=sha(Path(__file__))))


def review(root, output):
    from PIL import Image, ImageDraw
    data=read(output/'inputs-r3/provenance.json')['movement_extension']['data']
    points={};visible=set();intervals=[];totals=dict(frames=0,held=0,checkpoints=0)
    for name in ('done','undo','quick'):
        check=read(output/(name+'-check-r2.json'))
        assert check['checker_sha256']==sha(root/'tools/ui_list_live_check.py')
        runs={lang:read(output/(name+'-'+lang+'-r2/receipt.json')) for lang in ('en','zh')}
        run=runs['zh'];path=data['paths'][name]
        totals['frames']+=check['real_gpu_readback_frames'];totals['held']+=check['held_frames']
        totals['checkpoints']+=check['original_checkpoints_equal']
        visible.update(w['Key'] for f,s in zip(run['frames'],run['list_frames']) if not f['held'] for w in s['words'] or [])
        trace=read(root/'workplace/probe'/path['source_path'])
        for record in path['counters']:
            call=next(c for c in trace['calls'] if c['step']==record['step'])
            end=trace['wrappers'][call['wrapper_index']]['return_step']
            frames=[f for f in run['frames'] if record['step']<=f['step']<end]
            assert frames and all(f['held'] for f in frames),(name,record['value'])
            intervals.append(dict(path=name,value=record['value'],entry=record['step'],first_glyph=record['first_glyph'],ready=end,held_samples=len(frames)))
        points[name]=[]
        labels=['quick-weapon','hit-twelve'] if name=='quick' else ['move-left-eleven','move-back-ten','move-left-nine']
        for label in labels:
            cp=next(c for c in run['checkpoints'] if c['label']==label)
            frame=next(f for f in run['frames'] if f['step']==cp['step'])
            assert not frame['held']
            images=[]
            for lang in ('en','zh'):
                f=next(f for f in runs[lang]['frames'] if f['step']==cp['step'])
                images.append(Image.open(output/(name+'-'+lang+'-r2')/f['File']).convert('RGBA'))
            # 前綴止於原生 x=208，原版數字與填補空白逐像素保留。
            rect=(416,378,464,394)
            assert images[0].crop(rect).tobytes()==images[1].crop(rect).tobytes(),(name,label,'digits')
            points[name].append(dict(label=label,step=cp['step'],digit_sha256=hashlib.sha256(images[0].crop(rect).tobytes()).hexdigest()))
        if name!='quick':
            # 新版只改 Quick 提示生命週期；一般方向鍵兩路仍等於上次實測畫格。
            previous=read(output/(name+'-zh-r1/receipt.json'))
            for field in ('frames','list_frames','list_events','checkpoints','final_words'):
                assert run[field]==previous[field],(name,field)
        labels=[labels[0],labels[-1],('victim-killed' if name=='quick' else 'move-'+name)]
        panel=Image.new('RGB',(1280,420*len(labels)),'#202020');draw=ImageDraw.Draw(panel)
        for row,label in enumerate(labels):
            for col,lang in enumerate(('en','zh')):
                cp=next(c for c in runs[lang]['checkpoints'] if c['label']==label)
                f=next(f for f in runs[lang]['frames'] if f['step']==cp['step'])
                panel.paste(Image.open(output/(name+'-'+lang+'-r2')/f['File']).convert('RGB'),(col*640,row*420+20))
                draw.text((col*640+4,row*420+2),name+' / '+label+' / '+lang,fill='white')
        panel.save(output/(name+'-review-r2.png'))
    assert {a['key'] for a in data['aliases']}<=visible
    quick=read(output/'quick-zh-r2/receipt.json')
    ready=[e for e in quick['list_events'] if e['Kind']=='movement-caption-ready']
    retired=[e for e in quick['list_events'] if e['Kind']=='movement-caption-retired']
    assert len(ready)==len(retired)==1 and ready[0]['Step']<retired[0]['Step']
    assert not any(w['Key']==PREFIX for w in quick['final_words'])
    parent=read(output.parent/'combat-finish-20261024/zh-r5/receipt.json')
    replay=read(output/'parent-zh-r2/receipt.json')
    for field in ('frames','list_frames','list_events','checkpoints','paragraphs','final_words','final_paragraph'):
        assert parent[field]==replay[field],field
    for frame in replay['frames']:
        with Image.open(output/'parent-zh-r2'/frame['File']) as im:
            assert im.size==(640,400) and hashlib.sha256(im.convert('RGBA').tobytes()).hexdigest()==frame['SHA256']
    write(output/'visibility-review-r2.json',dict(points=points,totals=totals,intervals=intervals,
        visible_added_keys=sorted({a['key'] for a in data['aliases']}),quick_ready=ready[0]['Step'],quick_retired=retired[0]['Step'],
        parent_frames_equal=len(replay['frames']),parent_checkpoints_equal=len(replay['checkpoints']),
        scope='三條正常輸入分支；父批僅重跑繁中，不重複加總覆蓋。中途快照既有英文姓名未重印，不外推全畫面或正式入口。'))


def evidence(root, output):
    assert read(output/'guards.json')['tool_sha256']==sha(Path(__file__))
    for name in ('done-check-r2.json','undo-check-r2.json','quick-check-r2.json','visibility-review-r2.json','binary-rebuild-r2.json'):
        assert (output/name).is_file(),name
    tools=root/'tools'
    names={'movement_ui_inputs.py','ui_list_live_check.py','ui-context.sh','ui_context_probe.go',
           'oracle_video_observer.go','ui_hud_integer_test.go','ui_movement_counter_test.go'}
    names.update(f.name for f in (output/'programs-r2').glob('*.go'))
    pending=list(names)
    while pending:
        name=pending.pop()
        if not name.endswith('.py'):continue
        for node in ast.walk(ast.parse((tools/name).read_text())):
            modules=[node.module] if isinstance(node,ast.ImportFrom) else [a.name for a in node.names] if isinstance(node,ast.Import) else []
            for module in modules:
                candidate=(module or '').split('.')[0]+'.py'
                if candidate not in names and (tools/candidate).is_file():names.add(candidate);pending.append(candidate)
    snapshots=output/'tool-snapshots';snapshots.mkdir()
    for name in sorted(names):shutil.copyfile(tools/name,snapshots/name)
    sources=[root/'workplace/translation'/n for n in FORMAL]
    sources+=list((root/'workplace/probe'/BASE).iterdir())
    sources += [root/'workplace/input/dos/drkqueen/DQK.EXE',Path('/font/jf-openhuninn-2.1.ttf'),
        root/'workplace/probe/ui-context-probe',root/'workplace/probe/combat-effects-20261024/control-r3/final.state',
        root/'workplace/probe'/QUICK,root/'workplace/probe/combat-finish-20261024/control-r4/receipt.json',
        root/'workplace/probe/combat-finish-20261024/control-r4/breath-lightning.idx',
        root/'workplace/probe/combat-finish-20261024/zh-r5/receipt.json']
    def info(p):
        s=p.stat();assert (s.st_uid,s.st_gid)==(1000,1000),p
        return dict(bytes=s.st_size,sha256=sha(p),uid=s.st_uid,gid=s.st_gid)
    write(output/'evidence.json',dict(draft=True,runtime_integrated=False,rights='僅本機；不提交原版、全文、字模或畫格',
        engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        sources={str(f):info(f) for f in sources},tools={n:sha(tools/n) for n in sorted(names)},
        artifacts={str(f.relative_to(output)):info(f) for f in sorted(output.rglob('*')) if f.is_file()},
        effective=dict(inputs='inputs-r3',program='programs-r2',gpu='done/undo/quick-en-r2/zh-r2',
            native='observe-r3/control-r3; observe-undo-r1/control-undo-r1; combat-finish observe-r4/control-r4',
            parent_gpu='parent-zh-r2')))


if __name__=='__main__':
    command,root,output=sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3])
    if command=='glyph_inputs':glyph_inputs(root,output)
    elif command=='prepare':generate(root,output/'inputs-r3')
    elif command=='guards':guards(root,output)
    elif command=='review':review(root,output)
    elif command=='evidence':evidence(root,output)
    elif command=='audit':
        from combat_finish_inputs import audit
        audit(root,output)
    else:raise SystemExit('glyph_inputs | prepare | guards | review | evidence | audit')
