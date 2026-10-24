"""正常單支箭及購買後弩箭的 DRAFT 詞形與來源；原版資料保持唯讀。"""
import ast
from pathlib import Path
import re
import shutil
import sys
import tempfile

from bar_ui_inputs import write
from literal_catalog import catalog,digest,read,sha,windows
from text_catalog import write_tsv

BASE='ammo-rows-20261024/inputs-r2'
STUDY='ammo-boundaries-20261024'
PATHS={'single':('single-observe-r2','single-control-r2',13),
       'bolts':('bolts-ui-observe-r1','bolts-ui-control-r1',20)}
FORMS={'Arrow':('Arrow',1),'Arrows':('Arrow',2),'Bolt':('Bolt',1),'Bolts':('Bolt',2)}
ROOTS={'inventory.'+digest(s)[:20]:n for s,(_,n) in FORMS.items()}


def row_model(text,en):
    for key,form in ROOTS.items():
        if key not in en:continue
        pattern=(r' ('+re.escape(en['answer.yes'])+'|'+re.escape(en['answer.no'])+
            r')\t( ?)([1-9][0-9]*) ('+re.escape(en[key])+r')( \+[1-9][0-9]*)? ')
        m=re.fullmatch(pattern,text)
        if not m or m[2]!=' '*(3-len(m[1])):continue
        quantity=int(m[3])
        if quantity>2**31-1 or (quantity==1)!=(form==1):continue
        if m[5] and int(m[5][2:])>2**31-1:continue
        ready='inventory.'+digest(m[1])[:20];assert en[ready]==m[1]
        return dict(Pane='inventory',SHA256=digest(text),Foregrounds=[7,11],
            Spans=[dict(Start=m.start(1),Length=len(m[1]),Key=ready),dict(Start=m.start(4),Length=len(m[4]),Key=key)])
    return None


def aliases(root):
    en,zh=[catalog(root/'workplace/translation'/n) for n in ('en.tsv','zh-TW.tsv')]
    parent=catalog(root/'workplace/probe'/BASE/'en.tsv');out=[]
    for source,(formal,_) in FORMS.items():
        key='inventory.'+digest(source)[:20]
        candidates=[k for k,v in en.items() if v==formal and k in zh]
        assert candidates and len({zh[k] for k in candidates})==1
        if key not in parent:out.append(dict(key=key,source=source,translation=zh[candidates[0]],formal_keys=candidates))
    assert len(out)==3
    return out


def native(root,output):
    data={};all_names=set();probe=root/'workplace/probe'
    en=catalog(probe/BASE/'en.tsv');en.update({a['key']:a['source'] for a in aliases(root)})
    for name,(obs,control,count) in PATHS.items():
        a,b=[read(output/p/'receipt.json') for p in (obs,control)]
        for k in ('source_commit','go_version','exe_sha256','state_sha256','request_sha256','probe_sha256','request','checkpoints'):assert a[k]==b[k],(name,k)
        assert a['source_commit']=='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8' and a['exe_sha256']=='3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
        assert len(a['checkpoints'])==count and a['observe'] and not b['observe']
        assert not any(a[k] for k in ('pending_calls','pending_wrappers','pending_lists','pending_scrolls','pending_fills','pending_paragraphs'))
        assert not any(c['file_writes'] or c['unimplemented'] for c in a['checkpoints'])
        for cp in a['checkpoints']:
            for ext in ('.png','.idx'):assert sha(output/obs/(cp['label']+ext))==sha(output/control/(cp['label']+ext))
        assert sha(output/obs/'final.state')==sha(output/control/'final.state')
        records=[]
        for c in a['calls']:
            text=c['vararg_1_candidate']['text'];binding=row_model(text,en)
            if c['format']['text']!='%s' or binding is None:continue
            assert c['caller']==dict(Seg=0xb72,Off=0x27c) and c['wrapper_index']>=0
            assert c['vararg_1_candidate']['nul_terminated'] and bytes.fromhex(c['vararg_1_candidate']['hex']).decode()==text
            w=a['wrappers'][c['wrapper_index']]
            assert w['caller'] in tuple(dict(Seg=0xc15,Off=n) for n in (0x460,0x42c,0xc3a,0xc78))
            assert w['format']['text']=='%s' and w['vararg_1_candidate']['text']==text
            assert c['stack'][4] in (0x87,0x8b) and (w['stack'][4]&255)==(c['stack'][4]&15)
            assert w['step']<c['step']<c['first_glyph']<c['return_step']<=w['return_step']
            root_key=binding['Spans'][1]['Key'];all_names.add(en[root_key])
            records.append(dict(step=c['step'],wrapper_step=w['step'],first_glyph=c['first_glyph'],returned=w['return_step'],source=text,binding=binding))
        singular='Arrow' if name=='single' else 'Bolt'
        assert any(r['source']==' '+en['answer.no']+'\t 1 '+singular+(' +2 ' if name=='single' else ' ') for r in records)
        assert any(r['source']==' '+en['answer.yes']+'\t1 '+singular+(' +2 ' if name=='single' else ' ') for r in records)
        path=STUDY+'/'+obs+'/receipt.json'
        data[name]=dict(source_path=path,source_sha256=sha(output/obs/'receipt.json'),records=records,
            page_validation=dict(source_path=path,source_sha256=sha(output/obs/'receipt.json')))
    assert all_names==set(FORMS)
    a,b=[read(output/n/'receipt.json') for n in ('bolts-observe-r1','bolts-control-r1')]
    for k in ('source_commit','go_version','exe_sha256','state_sha256','request_sha256','probe_sha256','request','checkpoints'):assert a[k]==b[k],k
    assert len(a['checkpoints'])==31 and not any(c['file_writes'] or c['unimplemented'] for c in a['checkpoints'])
    assert sha(output/'bolts-observe-r1/final.state')==sha(output/'bolts-control-r1/final.state')
    for cp in a['checkpoints']:
        for ext in ('.png','.idx'):assert sha(output/'bolts-observe-r1'/(cp['label']+ext))==sha(output/'bolts-control-r1'/(cp['label']+ext))
    funds=list(dict.fromkeys(c['vararg_1_candidate']['text'] for c in a['calls'] if c['format']['text']=='%s' and c['vararg_1_candidate']['text'].startswith('Personal funds:')))
    assert [int(s.split(':')[1]) for s in funds]==[200,180,160],funds
    buys=[c for c in a['calls'] if c['format']['text']=='%s' and c['vararg_1_candidate']['text']=='SIR DRYDEN buys 20 Bolts  ']
    assert len(buys)==2
    assert read(output/'bolts-ui-observe-r1/receipt.json')['state_sha256']==sha(output/'bolts-control-r1/final.state')
    write(output/'purchase-check.json',dict(checkpoints=31,funds=[200,180,160],purchases=2,pack_quantity=20,
        final_state_sha256=sha(output/'bolts-control-r1/final.state'),scope='原版正常購買；不列為新增中文購買回報或連續 GUI。'))
    write(output/'native-check.json',data)


def derive(root):
    probe=root/'workplace/probe';base=probe/BASE;output=probe/STUDY
    config=read(base/'inputs.json');data=read(output/'native-check.json');added=aliases(root)
    en=catalog(base/'en.tsv');en.update({a['key']:a['source'] for a in added})
    bound={s['Key'] for r in config['Rows'] if r['Pane']=='inventory' for s in r['Spans']}
    rows=[];fine=[]
    for path in data.values():
        assert sha(probe/path['source_path'])==path['source_sha256']
        trace=read(probe/path['source_path']);fine.extend(windows(trace))
        for record in path['records']:
            binding=row_model(record['source'],en);assert binding==record['binding']
            key=binding['Spans'][1]['Key']
            if key not in bound:config['Rows'].append(binding);rows.append(binding);bound.add(key)
    assert len(rows)==3
    merged=[]
    for start,end in sorted(fine):
        if merged and start<=merged[-1][1]:merged[-1][1]=max(end,merged[-1][1])
        else:merged.append([start,end])
    config['fine_windows']=merged
    return config,dict(aliases=added,rows=rows,paths=data)


def generate(root,target):
    probe=root/'workplace/probe';base=probe/BASE;config,data=derive(root)
    shutil.copytree(base,target)
    for name,column in [('en.tsv','source'),('zh-TW.tsv','translation'),('font-zh-TW.tsv','translation')]:
        values=catalog(base/name);values.update({a['key']:a[column] for a in data['aliases']})
        write_tsv(target/name,['key','text'],values.items())
    glyphs=read(base/'glyphs-16.json');assert not set(''.join(a['translation'] for a in data['aliases']))-set(glyphs['glyphs'])
    proof=read(base/'provenance.json');proof['ammo_boundary_extension']=dict(base=BASE,base_files={f.name:sha(f) for f in base.iterdir()},data=data)
    write(target/'inputs.json',config);write(target/'provenance.json',proof)


def check_sources(inputs,config,proof,en,zh,glyphs):
    probe=inputs.parent.parent;root=probe.parent.parent;base=probe/BASE
    expected,data=derive(root);item=proof['ammo_boundary_extension']
    assert config==expected,'ammo boundary config'
    assert item==dict(base=BASE,base_files={f.name:sha(f) for f in base.iterdir()},data=data),'ammo boundary provenance'
    parent=read(base/'provenance.json');assert {k:v for k,v in proof.items() if k!='ammo_boundary_extension'}==parent
    old_en,old_zh=catalog(base/'en.tsv'),catalog(base/'zh-TW.tsv')
    assert en==dict(old_en,**{a['key']:a['source'] for a in data['aliases']})
    assert zh==dict(old_zh,**{a['key']:a['translation'] for a in data['aliases']}),'ammo boundary translation'
    for f in base.iterdir():
        if f.name not in ('en.tsv','zh-TW.tsv','font-zh-TW.tsv','inputs.json','provenance.json'):assert f.read_bytes()==(inputs/f.name).read_bytes(),f.name
    assert catalog(inputs/'font-zh-TW.tsv')==dict(catalog(base/'font-zh-TW.tsv'),**{a['key']:a['translation'] for a in data['aliases']})
    return base,read(base/'inputs.json'),parent,old_en,old_zh,read(base/'glyphs-16.json')


def guards(root,output):
    source=output/'inputs-r1'
    def check(p):return check_sources(p,read(p/'inputs.json'),read(p/'provenance.json'),catalog(p/'en.tsv'),catalog(p/'zh-TW.tsv'),read(p/'glyphs-16.json'))
    check(source);cases=[]
    for name in ('caller','form','quantity-span','translation','font'):
        with tempfile.TemporaryDirectory(dir=output,prefix='guard-') as d:
            p=Path(d);shutil.copytree(source,p,dirs_exist_ok=True);c=read(p/'inputs.json')
            if name=='translation':
                key=next(a['key'] for a in aliases(root) if a['source']=='Bolt')
                (p/'zh-TW.tsv').write_text((p/'zh-TW.tsv').read_text().replace(key+'\t',key+'\t99',1))
            elif name=='font':(p/'glyphs-16.json').write_text('{}\n')
            else:
                if name=='caller':c['RowCallers'].pop()
                elif name=='form':c['Rows'].pop()
                else:c['Rows'][-1]['Spans'][-1]['Start']-=2
                write(p/'inputs.json',c)
            try:check(p)
            except AssertionError as e:assert str(e)=={'translation':'ammo boundary translation','font':'glyphs-16.json'}.get(name,'ammo boundary config'),(name,e)
            else:raise AssertionError(name)
            cases.append(name)
    with tempfile.TemporaryDirectory(dir=output,prefix='rebuild-') as d:
        p=Path(d)/'inputs';generate(root,p)
        assert {f.name for f in p.iterdir()}=={f.name for f in source.iterdir()}
        for f in source.iterdir():assert f.read_bytes()==(p/f.name).read_bytes(),f.name
    write(output/'guards.json',dict(cases=cases,rebuilt_files=len(list(source.iterdir())),tool_sha256=sha(Path(__file__))))


def review(root,output):
    from PIL import Image,ImageDraw
    native_data=read(output/'native-check.json');paths={};panels=[]
    for name,(observe,_,_) in PATHS.items():
        report=read(output/(name+'-check-r2.json'))
        assert report['checker_sha256']==sha(root/'tools/ui_list_live_check.py')
        enrun,zhrun=[read(output/(name+'-'+lang+'-r1')/'receipt.json') for lang in ('en','zh')]
        trace=read(output/observe/'receipt.json');records=native_data[name]['records']
        intervals=[];points=[];numbers=[];visible=set()
        for record in records:
            event_index=next(i for i,e in enumerate(zhrun['list_events']) if e['Kind']=='row-before-glyph' and e['Step']==record['wrapper_step'])
            frames=[];before=0
            for f,state in zip(zhrun['frames'],zhrun['list_frames']):
                if not record['wrapper_step']<=f['step']<record['returned']:continue
                if state['list_event_count']<=event_index:
                    assert f['step']==record['wrapper_step'] and state['list_event_count']==event_index
                    before+=1
                else:frames.append(f)
            assert frames and all(f['held'] for f in frames),record['step']
            intervals.append(dict(entry=record['wrapper_step'],returned=record['returned'],held_samples=len(frames),before_entry_samples=before))
        request=read(output/('single-request-r2.json' if name=='single' else 'bolts-ui-request-r1.json'))
        actions={a['label']:a for a in request['actions']}
        for cp in zhrun['checkpoints']:
            index=next(i for i,f in enumerate(zhrun['frames']) if f['step']==cp['step']);zf=zhrun['frames'][index];held=zf['held']
            if held:
                prior=max(i for i,f in enumerate(zhrun['frames'][:index]) if not f['held'])
                assert zhrun['frames'][prior]['step']>actions[cp['label']]['at']
                assert zf['SHA256']==zhrun['frames'][prior]['SHA256']
                index=prior;zf=zhrun['frames'][index]
            points.append(dict(label=cp['label'],step=cp['step'],held=held,sample_step=zf['step']))
            ef=next(f for f in enrun['frames'] if f['step']==zf['step'])
            images=[Image.open(output/(name+'-'+lang+'-r1')/f['File']).convert('RGBA') for lang,f in (('en',ef),('zh',zf))]
            for word in zhrun['list_frames'][index]['words'] or []:
                if word['Key'] not in ROOTS:continue
                visible.add(word['Key']);choices=[]
                for record in records:
                    call=next(c for c in trace['calls'] if c['step']==record['step']);w=trace['wrappers'][call['wrapper_index']]
                    x,y=(w['stack'][2]&255)*8,(w['stack'][3]&255)*8
                    span=record['binding']['Spans'][1]
                    if span['Key']==word['Key'] and record['returned']<zf['step'] and (x+span['Start']*8,y)==(word['X'],word['Y']):choices.append((record,x,y))
                record,x,y=choices[-1]
                for m in re.finditer(r'[0-9]+',record['source']):
                    rect=((x+m.start()*8)*2,y*2,(x+m.end()*8)*2,(y+8)*2)
                    assert images[0].crop(rect).tobytes()==images[1].crop(rect).tobytes(),(cp['label'],record['source'],rect)
                    numbers.append(dict(label=cp['label'],source_sha256=digest(record['source']),digits=m[0],rect=rect))
            if any(s in cp['label'] for s in ('one','join')):
                panels.append((name,cp['label'],images))
        paths[name]=dict(intervals=intervals,points=points,numeric_regions=numbers,visible_keys=sorted(visible))
    assert set().union(*(set(p['visible_keys']) for p in paths.values()))==set(ROOTS)
    panel=Image.new('RGB',(1280,420*len(panels)),'#202020');draw=ImageDraw.Draw(panel)
    for row,(name,label,images) in enumerate(panels):
        for col,img in enumerate(images):
            panel.paste(img.convert('RGB'),(col*640,row*420+20));draw.text((col*640+4,row*420+2),name+' / '+label+' / '+('en' if col==0 else 'zh'),fill='white')
    assert panels
    panel.save(output/'review-r1.png')
    write(output/'visibility-review-r1.json',dict(paths=paths,scope='單支／複數箭與弩箭的正常背包顯示；購買僅另有原版無頭收據，未列為連續 GUI。'))


def evidence(root,output):
    assert read(output/'guards.json')['tool_sha256']==sha(Path(__file__))
    for name in ('single-check-r2.json','bolts-check-r2.json','visibility-review-r1.json','binary-rebuild-r1.json'):
        assert (output/name).is_file(),name
    log=(output/'tests-r1.log').read_text();assert 'FAIL' not in log and 'SKIP' not in log and log.count('--- PASS:')==5
    tools=root/'tools';names={'ammo_boundary_inputs.py','ui_list_live_check.py','oracle_video_observer.go','ui-context.sh','ui_context_probe.go','ui-list-live.sh','early-live.sh'}
    names.update(f.name for f in (output/'programs-r1').glob('*.go'))
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
    sources += [root/'workplace/input/dos/drkqueen/DQK.EXE',probe/'ui-context-probe',probe/'ammo-rows-20261024/control-r4/final.state',probe/'pane-render-20261022/observe-city-shop-r1/final.state']
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
        effective=dict(program='programs-r1',inputs='inputs-r1',native=list(PATHS.values()),gpu='single-en/zh-r1、bolts-en/zh-r1')))


if __name__=='__main__':
    command,root,output=sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3])
    if command=='native':native(root,output)
    elif command=='prepare':generate(root,output/'inputs-r1')
    elif command=='guards':guards(root,output)
    elif command=='review':review(root,output)
    elif command=='evidence':evidence(root,output)
    elif command=='audit':
        from combat_finish_inputs import audit
        audit(root,output)
    else:raise SystemExit('native | prepare | guards | review | evidence | audit')
