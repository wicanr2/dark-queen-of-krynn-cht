"""本作正常箭堆數量／反白的 DRAFT 輸入；不修改原版物品或數值。"""
import copy
import ast
import hashlib
from pathlib import Path
import re
import shutil
import sys
import tempfile

from bar_ui_inputs import write
from literal_catalog import catalog, digest, read, sha, windows

BASE = 'combat-movement-20261024/inputs-r3'
STUDY = 'ammo-rows-20261024'
SOURCE = STUDY+'/observe-r4/receipt.json'
ROOT_KEY = 'inventory.423c677c12e0b601c34c'


def row_model(text, en):
    root = en[ROOT_KEY]
    pattern = (r' ('+re.escape(en['answer.yes'])+'|'+re.escape(en['answer.no'])+
               r')\t( ?)([1-9][0-9]*) ('+re.escape(root)+r')( \+[1-9][0-9]*)? ')
    m = re.fullmatch(pattern, text)
    if not m or m[2] != ' '*(3-len(m[1])) or int(m[3]) > 2**31-1:
        return None
    if m[5] and int(m[5][2:]) > 2**31-1:
        return None
    key = 'inventory.'+digest(m[1])[:20]
    assert en[key] == m[1] and ROOT_KEY == 'inventory.'+digest(root)[:20]
    return dict(Pane='inventory',SHA256=digest(text),Foregrounds=[7,11],
        Spans=[dict(Start=m.start(1),Length=len(m[1]),Key=key),
               dict(Start=m.start(4),Length=len(root),Key=ROOT_KEY)])


def native(root, output):
    a,b=[read(output/n/'receipt.json') for n in ('observe-r4','control-r4')]
    for k in ('source_commit','go_version','exe_sha256','state_sha256','request_sha256','probe_sha256','request','checkpoints'):
        assert a[k]==b[k],k
    assert len(a['checkpoints'])==17
    assert a['source_commit']=='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8'
    assert a['exe_sha256']=='3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
    assert not any(c['file_writes'] or c['unimplemented'] for c in a['checkpoints'])
    assert a['observe'] and not b['observe'] and not b['calls']
    assert not any(a[k] for k in ('pending_calls','pending_wrappers','pending_lists','pending_scrolls','pending_fills','pending_paragraphs'))
    for cp in a['checkpoints']:
        for ext in ('.png','.idx'):
            assert sha(output/'observe-r4'/(cp['label']+ext))==sha(output/'control-r4'/(cp['label']+ext))
    assert sha(output/'observe-r4/final.state')==sha(output/'control-r4/final.state')
    base=root/'workplace/probe'/BASE
    en=catalog(base/'en.tsv');records=[]
    for c in a['calls']:
        if c['format']['text']!='%s':continue
        text=c['vararg_1_candidate']['text'];binding=row_model(text,en)
        if binding is None:continue
        assert c['caller']==dict(Seg=0xb72,Off=0x27c) and c['wrapper_index']>=0
        w=a['wrappers'][c['wrapper_index']]
        assert w['caller'] in tuple(dict(Seg=0xc15,Off=n) for n in (0x460,0x42c,0xc3a,0xc78)) and w['format']['text']=='%s'
        assert w['vararg_1_candidate']['text']==text and c['step']<c['first_glyph']<c['return_step']
        assert c['stack'][4] in (0x87,0x8b) and (w['stack'][4]&255)==(c['stack'][4]&15)
        records.append(dict(step=c['step'],wrapper_step=w['step'],first_glyph=c['first_glyph'],returned=w['return_step'],source=text,binding=binding))
    quantities={int(re.search(r'([0-9]+) '+re.escape(en[ROOT_KEY]),r['source'])[1]) for r in records}
    assert quantities=={2,3,5,10,20,40}
    assert any(r['source'].startswith(' '+en['answer.no']) for r in records)
    write(output/'native-check-r3.json',dict(checkpoints=17,records=records,quantities=sorted(quantities),
        source_sha256=sha(output/'observe-r4/receipt.json'),final_state_sha256=sha(output/'control-r4/final.state')))


def generate(root, target):
    probe=root/'workplace/probe';output=probe/STUDY;base=probe/BASE
    assert read(output/'native-check-r3.json')['source_sha256']==sha(probe/SOURCE)
    config=read(base/'inputs.json');config['fine_windows']=windows(read(probe/SOURCE))
    proof=read(base/'provenance.json')
    proof['ammo_extension']=dict(base=BASE,base_files={f.name:sha(f) for f in base.iterdir()},
        source_path=SOURCE,source_sha256=sha(probe/SOURCE),
        page_validation=dict(source_path=SOURCE,source_sha256=sha(probe/SOURCE)))
    shutil.copytree(base,target)
    write(target/'inputs.json',config);write(target/'provenance.json',proof)


def check_sources(inputs,config,proof,en,zh,glyphs):
    probe=inputs.parent.parent;base=probe/BASE;item=proof['ammo_extension']
    source=item['source_path']
    assert source in (STUDY+'/observe-r3/receipt.json',SOURCE)
    expected=read(base/'inputs.json');expected['fine_windows']=windows(read(probe/source))
    assert config==expected,'ammo config'
    assert item==dict(base=BASE,base_files={f.name:sha(f) for f in base.iterdir()},source_path=source,
        source_sha256=sha(probe/source),page_validation=dict(source_path=source,source_sha256=sha(probe/source))),'ammo provenance'
    parent=read(base/'provenance.json')
    assert {k:v for k,v in proof.items() if k!='ammo_extension'}==parent
    for f in base.iterdir():
        if f.name not in ('inputs.json','provenance.json'):assert f.read_bytes()==(inputs/f.name).read_bytes(),f.name
    return base,read(base/'inputs.json'),parent,catalog(base/'en.tsv'),catalog(base/'zh-TW.tsv'),read(base/'glyphs-16.json')


def guards(root, output):
    source=output/'inputs-r2'
    def check(p):return check_sources(p,read(p/'inputs.json'),read(p/'provenance.json'),catalog(p/'en.tsv'),catalog(p/'zh-TW.tsv'),read(p/'glyphs-16.json'))
    check(source);cases=[]
    for name in ('caller','name-span','color','translation','font'):
        with tempfile.TemporaryDirectory(dir=output,prefix='guard-') as d:
            p=Path(d);shutil.copytree(source,p,dirs_exist_ok=True);c=read(p/'inputs.json')
            row=next(r for r in c['Rows'] if r['Pane']=='inventory' and any(s['Key']==ROOT_KEY for s in r['Spans']))
            if name=='translation':(p/'zh-TW.tsv').write_text((p/'zh-TW.tsv').read_text().replace(ROOT_KEY+'\t',ROOT_KEY+'\t99',1))
            elif name=='font':(p/'glyphs-16.json').write_text('{}\n')
            else:
                if name=='caller':c['RowCallers'].pop()
                elif name=='name-span':row['Spans'][-1]['Start']+=1
                else:row['Foregrounds']=[15]
                write(p/'inputs.json',c)
            try:check(p)
            except AssertionError as e:assert str(e)==({'translation':'zh-TW.tsv','font':'glyphs-16.json'}.get(name,'ammo config')),(name,e)
            else:raise AssertionError(name)
            cases.append(name)
    with tempfile.TemporaryDirectory(dir=output,prefix='rebuild-') as d:
        p=Path(d)/'inputs';generate(root,p)
        assert {f.name for f in p.iterdir()}=={f.name for f in source.iterdir()}
        for f in source.iterdir():assert f.read_bytes()==(p/f.name).read_bytes(),f.name
    write(output/'guards.json',dict(cases=cases,rebuilt_files=len(list(source.iterdir())),tool_sha256=sha(Path(__file__))))


def review(root,output):
    from PIL import Image,ImageDraw
    report=read(output/'gpu-check-r3.json')
    assert report['checker_sha256']==sha(root/'tools/ui_list_live_check.py')
    enrun,zhrun=[read(output/n/'receipt.json') for n in ('en-r3','zh-r3')]
    data=read(output/'native-check-r3.json');trace=read(root/'workplace/probe'/SOURCE)
    assert len(data['records'])==28
    counts=[];intervals=[];points=[]
    actions={a['label']:a for a in read(output/'request-r3.json')['actions']}
    for record in data['records']:
        event_index=next(i for i,e in enumerate(zhrun['list_events']) if e['Kind']=='row-before-glyph' and e['Step']==record['wrapper_step'])
        frames=[];before=0
        for f,state in zip(zhrun['frames'],zhrun['list_frames']):
            if not record['wrapper_step']<=f['step']<record['returned']:continue
            if state['list_event_count']<=event_index:
                assert f['step']==record['wrapper_step'] and state['list_event_count']==event_index
                before+=1
            else:frames.append(f)
        assert frames and all(f['held'] for f in frames),record['step']
        intervals.append(dict(entry=record['wrapper_step'],first_glyph=record['first_glyph'],returned=record['returned'],held_samples=len(frames),before_entry_samples=before))
    for cp in zhrun['checkpoints']:
        index=next(i for i,f in enumerate(zhrun['frames']) if f['step']==cp['step']);zf=zhrun['frames'][index]
        held=zf['held']
        if held:
            assert cp['label']=='arrows-five'
            prior=max(i for i,f in enumerate(zhrun['frames'][:index]) if not f['held'])
            assert zhrun['frames'][prior]['step']>actions[cp['label']]['at']
            assert zf['SHA256']==zhrun['frames'][prior]['SHA256']
            index=prior;zf=zhrun['frames'][index]
        points.append(dict(label=cp['label'],step=cp['step'],held=held,sample_step=zf['step']))
        ef=next(f for f in enrun['frames'] if f['step']==zf['step'])
        images=[Image.open(output/n/f['File']).convert('RGBA') for n,f in (('en-r3',ef),('zh-r3',zf))]
        for word in zhrun['list_frames'][index]['words'] or []:
            if word['Key']!=ROOT_KEY:continue
            choices=[]
            for record in data['records']:
                call=next(c for c in trace['calls'] if c['step']==record['step']);w=trace['wrappers'][call['wrapper_index']]
                x,y=(w['stack'][2]&255)*8,(w['stack'][3]&255)*8
                span=record['binding']['Spans'][1]
                if record['returned']<zf['step'] and (x+span['Start']*8,y)==(word['X'],word['Y']):choices.append((record,x,y))
            record,x,y=choices[-1];text=record['source']
            for m in re.finditer(r'[0-9]+',text):
                rect=((x+m.start()*8)*2,y*2,(x+m.end()*8)*2,(y+8)*2)
                assert images[0].crop(rect).tobytes()==images[1].crop(rect).tobytes(),(cp['label'],text,rect)
                counts.append(dict(label=cp['label'],source_sha256=digest(text),digits=m[0],rect=rect))
    assert counts
    labels=('arrows-unready','arrows-halved','arrows-odd-halved','all-arrows-ready')
    panel=Image.new('RGB',(1280,420*len(labels)),'#202020');draw=ImageDraw.Draw(panel)
    for row,label in enumerate(labels):
        for col,(name,run) in enumerate((('en-r3',enrun),('zh-r3',zhrun))):
            cp=next(c for c in run['checkpoints'] if c['label']==label);f=next(f for f in run['frames'] if f['step']==cp['step'])
            panel.paste(Image.open(output/name/f['File']).convert('RGB'),(col*640,row*420+20));draw.text((col*640+4,row*420+2),label+' / '+name,fill='white')
    panel.save(output/'review-r3.png')
    write(output/'visibility-review-r3.json',dict(stable_checkpoints=sum(not p['held'] for p in points),points=points,numeric_regions=counts,intervals=intervals,
        final_words=zhrun['final_words'],scope='原版 +2 箭的正常卸下、分半、集合與反白；+1 只有格式回歸測例。'))


def evidence(root,output):
    assert read(output/'guards.json')['tool_sha256']==sha(Path(__file__))
    for n in ('gpu-check-r3.json','visibility-review-r3.json','baseline-proof-r1.json','binary-rebuild-r2.json','terminology-check.json'):assert (output/n).is_file(),n
    assert 'FAIL' not in (output/'ammo-tests-r1.log').read_text() and (output/'ammo-tests-r1.log').read_text().count('--- PASS:')==3
    tools=root/'tools';names={'ammo_ui_inputs.py','ui_list_live_check.py','oracle_video_observer.go','ui-context.sh','ui_context_probe.go','ui-list-live.sh','early-live.sh'}
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
    probe=root/'workplace/probe';sources=list((probe/BASE).iterdir())
    sources += [root/'workplace/input/dos/drkqueen/DQK.EXE',probe/'save-load-city-20261022/inn-menu.state',
        probe/'ui-context-probe',probe/'combat-movement-20261024/programs-r2/ui-list-live']
    sources += [root/'workplace/translation'/n for n in ('en.tsv','zh-TW.tsv','glossary.tsv')]
    sources += [Path('/dkk/text')/n for n in ('glossary.tsv','name.zh-TW.tsv','name-lexicon-five.tsv')]
    def info(p):
        s=p.stat();assert(s.st_uid,s.st_gid)==(1000,1000),p
        return dict(bytes=s.st_size,sha256=sha(p),uid=s.st_uid,gid=s.st_gid)
    write(output/'evidence.json',dict(draft=True,runtime_integrated=False,rights='原版、譯表全文、字模與畫格只留本機',
        engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        tools={n:sha(tools/n) for n in names},sources={str(p):info(p) for p in sources},
        artifacts={str(p.relative_to(output)):info(p) for p in sorted(output.rglob('*')) if p.is_file()},
        effective=dict(program='programs-r2',inputs='inputs-r2',native='observe-r4/control-r4',gpu='en-r3/zh-r3',baseline='baseline-zh-r3')))


if __name__=='__main__':
    command,root,output=sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3])
    if command=='native':native(root,output)
    elif command=='prepare':generate(root,output/'inputs-r2')
    elif command=='guards':guards(root,output)
    elif command=='review':review(root,output)
    elif command=='evidence':evidence(root,output)
    elif command=='audit':
        from combat_finish_inputs import audit
        audit(root,output)
    else:raise SystemExit('native | prepare | guards | review | evidence | audit')
