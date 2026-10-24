"""首戰正常續行至敗北的 DRAFT 顯示資料；不修改原版規則。"""
import ast
import copy
import hashlib
from pathlib import Path
import re
import shutil
import sys
import tempfile

from bar_ui_inputs import write
from combat_effects_inputs import integer
from literal_catalog import catalog,digest,read,sha,windows
from text_catalog import write_tsv

BASE='ammo-boundaries-20261024/inputs-r1'
STUDY='combat-rounds-20261024'
RUNS={1:12,3:8,4:8,13:16,10:9,9:8}
DYING='round.3639be1dab675907c6bf'
AUTOMATIC_MENU='c5b214e0c009d9bf9bb1be3435f8b0c72be521577ac3912c57dfa55d39b0a5c2'


def hud_records(trace,bindings,en):
    result=[]
    for i,p in enumerate(trace['paragraphs'] or []):
        source=p['source']['text'];matches=[]
        for b in bindings:
            if b['Caller']!=p['caller'] or b['NativeBox']!=p['native_box']:continue
            if [b[k] for k in ('Foreground','Background','Clear')]!=[p[k] for k in ('foreground','background','clear')]:continue
            key=b.get('IntegerTemplateKey');number=integer(source,en[key]) if key else None
            if key and any(t.get('IntegerTemplateKey')==key and t.get('KeepFooterSignature') for t in bindings):
                if not p.get('menu_valid'):continue
                signature=p['menu_snapshot']['Signature']
                if b.get('OrdinaryDamage'):
                    if signature!=AUTOMATIC_MENU:continue
                elif signature!=b.get('KeepFooterSignature'):continue
            if (key and number is not None) or (not key and b['SHA256']==digest(source)):matches.append((b,number))
        if not matches:continue
        assert len(matches)==1;b,number=matches[0]
        chars=[c for c in trace['calls'] if c['paragraph_index']==i and c['format']['text']=='%c']
        rendered=''.join(chr(c['stack'][7]&255) for c in chars)
        if any(s['Key']==DYING for s in b['Spans']):
            assert source==en[DYING] and len(source)==22 and source[16]==' '
            assert rendered==source[:16]+source[17:]
            x,y,_,_=p['native_box']
            positions=[(x+8*j,y) for j in range(16)]+[(x+8*j,y+8) for j in range(5)]
            assert [((c['stack'][3]-8000)*2,(c['stack'][2]-8000)*2) for c in chars]==positions
        else:assert rendered==source
        assert p['source']['nul_terminated'] and bytes.fromhex(p['source']['hex']).decode()==source
        assert p['step']<p['first_glyph']==chars[0]['first_glyph']<p['return_step']
        assert all(p['step']<c['step']<c['first_glyph']<c['return_step']<p['return_step'] for c in chars)
        pages={page for c in chars for page in c['video_pages']};assert len(pages)==1
        result.append(dict(index=i,step=p['step'],first_glyph=p['first_glyph'],return_step=p['return_step'],source=source,binding=b,number=number,paint_page=int(next(iter(pages)))))
    return result


def native(root,output):
    result={}
    for number,count in [*RUNS.items(),(5,10),(6,4),(7,8)]:
        run_number={1:12,13:14,10:15}.get(number,number)
        previous=(root/'workplace/probe/combat-finish-20261024/control-r4/final.state' if number==1 else
            output/('control-r'+str({3:1,4:3,5:4,6:5,7:6,10:6,9:7,13:4}[number]))/'final.state')
        a,b=[read(output/(mode+'-r'+str(run_number))/'receipt.json') for mode in ('observe','control')]
        for k in ('source_commit','go_version','exe_sha256','probe_sha256','state_sha256','request_sha256','request','checkpoints'):assert a[k]==b[k],(number,k)
        assert a['state_sha256']==sha(previous)
        assert a['source_commit']=='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8'
        assert a['exe_sha256']=='3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58'
        assert a['observe'] and not b['observe'] and len(a['checkpoints'])==count
        assert not any(v for k,v in a.items() if k.startswith('pending'))
        assert not any(cp['file_writes'] or cp['unimplemented'] for cp in a['checkpoints'])
        for cp in a['checkpoints']:
            for suffix in ('.png','.idx'):
                assert sha(output/('observe-r'+str(run_number))/(cp['label']+suffix))==sha(output/('control-r'+str(run_number))/(cp['label']+suffix))
        previous=output/('control-r'+str(run_number))/'final.state'
        assert sha(previous)==sha(output/('observe-r'+str(run_number))/'final.state')
        result[str(number)]=dict(source_path=STUDY+'/observe-r'+str(run_number)+'/receipt.json',
            source_sha256=sha(output/('observe-r'+str(run_number))/'receipt.json'),checkpoints=count)
        if number==1:
            old=read(output/'observe-r1/receipt.json')
            for key in ('checkpoints','calls','wrappers','paragraphs'):assert a[key]==old[key]
            assert sha(previous)==sha(output/'control-r1/final.state')
            assert [e['step'] for e in a['menu_refresh_sources']]==[3760446709]
        if number in (10,13):
            old=read(output/('observe-r'+str(number))/'receipt.json')
            assert a['checkpoints']==old['checkpoints'] and a['calls']==old['calls'] and a['wrappers']==old['wrappers']
            assert [{k:v for k,v in p.items() if k not in ('menu_valid','menu_snapshot')} for p in a['paragraphs']]==old['paragraphs']
            assert sha(previous)==sha(output/('control-r'+str(number))/'final.state')
    # OOM 前已落盤的原版前綴不得因分段重播改變。
    for mode in ('observe','control'):
        for cp in read(output/(mode+'-r3')/'receipt.json')['checkpoints']:
            for suffix in ('.png','.idx'):assert sha(output/(mode+'-r2')/(cp['label']+suffix))==sha(output/(mode+'-r3')/(cp['label']+suffix))
        for cp in read(output/(mode+'-r7')/'receipt.json')['checkpoints']:
            for suffix in ('.png','.idx'):assert sha(output/(mode+'-r7')/(cp['label']+suffix))==sha(output/(mode+'-r10')/(cp['label']+suffix))
        for suffix in ('.png','.idx'):assert sha(output/(mode+'-r10')/('next-damage-forty'+suffix))==sha(output/(mode+'-r9')/('defeat-1'+suffix))
        joined=read(output/(mode+'-r13')/'receipt.json')
        assert sha(output/(mode+'-r13')/'final.state')==sha(output/(mode+'-r6')/'final.state')
        for n in (5,6):
            for cp in read(output/(mode+'-r'+str(n))/'receipt.json')['checkpoints']:
                assert cp==next(c for c in joined['checkpoints'] if c['label']==cp['label'])
                for suffix in ('.png','.idx'):assert sha(output/(mode+'-r'+str(n))/(cp['label']+suffix))==sha(output/(mode+'-r13')/(cp['label']+suffix))
    write(output/'native-check.json',result)


def copy_witness(output):
    original=read(output/'observe-r14/receipt.json')
    a,b=[read(output/(mode+'-r17')/'receipt.json') for mode in ('observe','control')]
    for key in ('source_commit','go_version','exe_sha256','probe_sha256','state_sha256','request_sha256','request','checkpoints'):
        assert a[key]==b[key]
    for key in ('source_commit','go_version','exe_sha256','probe_sha256','state_sha256','calls','wrappers','paragraphs','fill_events','display_changes'):
        assert a[key]==original[key],key
    assert len(a['checkpoints'])==len(original['checkpoints'])+1==17
    assert [(v['at'],v['kind'],v['key']) for v in a['request']['actions'] if v['key']]==[(v['at'],v['kind'],v['key']) for v in original['request']['actions'] if v['key']]
    for cp in a['checkpoints']:
        assert not cp['file_writes'] and not cp['unimplemented']
        if cp['label']!='weapon-copy':assert cp==next(c for c in original['checkpoints'] if c['label']==cp['label'])
        for suffix in ('.png','.idx'):
            assert sha(output/'observe-r17'/(cp['label']+suffix))==sha(output/'control-r17'/(cp['label']+suffix))
            if cp['label']!='weapon-copy':assert sha(output/'observe-r17'/(cp['label']+suffix))==sha(output/'observe-r14'/(cp['label']+suffix))
    assert sha(output/'observe-r17/final.state')==sha(output/'control-r17/final.state')==sha(output/'observe-r14/final.state')
    cp=next(c for c in a['checkpoints'] if c['label']=='weapon-copy')
    assert cp['step']==4284677330
    return dict(step=cp['step'],path='observe-r17/weapon-copy.png',sha256=sha(output/'observe-r17/weapon-copy.png'),
        receipt_sha256=sha(output/'observe-r17/receipt.json'),original_checkpoints_equal=16,extra_checkpoints=1)


def derive(root):
    probe=root/'workplace/probe';base=probe/BASE;output=probe/STUDY
    config=copy.deepcopy(read(base/'inputs.json'));en,zh=[catalog(root/'workplace/translation'/n) for n in ('en.tsv','zh-TW.tsv')]
    parent_en,parent_zh=[catalog(base/n) for n in ('en.tsv','zh-TW.tsv')]
    aliases={};bindings=[];paragraphs=[];fields=[];paths={};fine=[]
    aimed=next(b for b in config['HUDParagraphs'] if b.get('IntegerTemplateKey')=='hud-format.66e294009f6a0a6b1d62')
    automatic=copy.deepcopy(aimed);automatic.pop('KeepFooterSignature');automatic['OrdinaryDamage']=True
    config['HUDParagraphs'].append(automatic);bindings.append(automatic)
    def term(source):
        known=[k for k,v in parent_en.items() if v==source and k in parent_zh]
        if known:
            assert len({parent_zh[k] for k in known})==1
            return min(known)
        key='round.'+digest(source)[:20]
        if key in aliases:return key
        choices=[k for k,v in en.items() if v.casefold()==source.casefold() and k in zh]
        if choices:
            assert len({zh[k] for k in choices})==1
            formal=min(choices,key=lambda k:(en[k]!=source,not k.startswith('ui.'),k));value=zh[formal];keys=[formal]
        elif source==en['ui.478a25da3621662e9064'].replace('%s',en['ui.fd5da56f78edbf8bcec0']):
            keys=['ui.478a25da3621662e9064','ui.fd5da56f78edbf8bcec0']
            value=zh[keys[0]].replace('%s',zh[keys[1]])
        elif source.startswith('Spell:'):
            templates=[k for k,v in en.items() if v=='Spell:%s'];arguments=[k for k,v in en.items() if v==source[6:] and k in zh]
            assert len(templates)==1 and arguments and len({zh[k] for k in arguments})==1
            keys=[templates[0],min(arguments)];value=zh[keys[0]].replace('%s',zh[keys[1]])
        else:raise AssertionError(('沒有正式詞條',source))
        aliases[key]=dict(key=key,source=source,translation=value,formal_keys=keys)
        return key
    sources=read(output/'native-check.json')
    for name in map(str,RUNS):
        proof=sources[name]
        path=probe/proof['source_path'];assert sha(path)==proof['source_sha256'];trace=read(path);fine.extend(windows(trace))
        for p in trace['paragraphs'] or []:
            source=p['source']['text']
            if source==' ':continue
            all_en=dict(parent_en,**{k:a['source'] for k,a in aliases.items()})
            if hud_records(dict(paragraphs=[p],calls=[dict(c,paragraph_index=0) for c in trace['calls'] if c['paragraph_index']==trace['paragraphs'].index(p)]),config['HUDParagraphs'],all_en):continue
            weapon=p['caller']==dict(Seg=0x88e,Off=0x97e)
            root=re.sub(r'(?: \+[1-9][0-9]*)? *$','',source) if weapon else source
            key=term(root);x,y,right,bottom=p['native_box']
            assert p['source']['nul_terminated'] and [p[k] for k in ('foreground','background','clear')][:2]==[7,0]
            if x==184:
                assert p['caller'] in (dict(Seg=0x88e,Off=0x97e),dict(Seg=0x88e,Off=0x15e1)) and p['clear']==1
                rect=[x,y,min(len(root)*8,right-x),8 if weapon and len(root)*8<=right-x else bottom-y]
                binding=dict(SHA256=digest(source),Caller=p['caller'],NativeBox=p['native_box'],Foreground=7,Background=0,Clear=1,
                    Spans=[dict(Start=0,Length=len(root),Key=key,Rect=rect)])
                if y==88:binding['HideFooter']=True
                assert binding not in config['HUDParagraphs'];config['HUDParagraphs'].append(binding);bindings.append(binding)
            else:
                assert p['caller'] in tuple(dict(Seg=0x27c7,Off=o) for o in (0x148e,0x14b0,0x14d2))
                expected_y=40+8*((p['caller']['Off']-0x148e)//0x22)
                assert p['native_box']==[16,expected_y,304,184] and p['clear']==1
                # 三段分別清除各自列以下的區域，保留前一列；沿既有多詞框型別。
                binding=dict(SHA256=digest(source),Caller=p['caller'],NativeBox=p['native_box'],Foreground=7,Background=0,Clear=1,
                    Spans=[dict(Start=0,Length=len(source),Key=key,Rect=[16,expected_y,288,8])])
                if binding not in config['HUDParagraphs']:config['HUDParagraphs'].append(binding);bindings.append(binding)
        for c in trace['calls']:
            source=c['vararg_1_candidate']['text']
            if c['format']['text']!='%s' or c['wrapper_index']<0:continue
            w=trace['wrappers'][c['wrapper_index']]
            actor=w['caller']==dict(Seg=0x88e,Off=0x16fb) and source in ('BLUE DRAGON','GREEN DRAGON')
            warning=w['caller']==dict(Seg=0x88e,Off=0x1560) and source==en['ui.50e28de96686ceec7dc0']
            spell=w['caller']==dict(Seg=0x2c4a,Off=0x4630) and source.startswith('Spell:')
            if not(actor or warning or spell):continue
            key=term(source);f=dict(Pane='callsite',Group='body' if actor else 'footer',Key=key,Start=0,Length=len(source),
                SHA256=digest(source),FormatSHA256=digest('%s'),Caller=c['caller'],UpperCaller=w['caller'],
                RawX=c['stack'][3],RawY=c['stack'][2],Color=c['stack'][4],MenuSignature='')
            if actor:
                y=(c['stack'][2]-8000)*2;assert y in (8,80,96) and c['stack'][3]==8092 and c['stack'][4]==0x82
                f.update(UpperFormatSHA256=digest('%s'),UpperNative=[184,y],BackgroundOverride=23)
            elif warning:f.update(UpperFormatSHA256=digest('%s'),UpperNative=[0,192])
            else:assert w['format']['text']==source;f['UpperNative']=[0,184]
            if f not in config['Fields']:config['Fields'].append(f);fields.append(dict(step=c['step'],source=source,binding=f))
        paths[name]=dict(proof,page_validation=dict(source_path=proof['source_path'],source_sha256=proof['source_sha256']))
    all_en=dict(parent_en,**{k:a['source'] for k,a in aliases.items()})
    for name,p in paths.items():p['records']=hud_records(read(probe/p['source_path']),config['HUDParagraphs'],all_en)
    merged=[]
    for start,end in sorted(fine):
        if merged and start<=merged[-1][1]:merged[-1][1]=max(end,merged[-1][1])
        else:merged.append([start,end])
    config['fine_windows']=merged
    warning=read(output/'observe-r14/receipt.json')
    w=next(w for w in warning['wrappers'] if w['vararg_1_candidate']['text']==en['ui.50e28de96686ceec7dc0'])
    c=next(c for c in warning['calls'] if c['wrapper_index']==warning['wrappers'].index(w) and c['format']['text']=='%s')
    assert w['caller']==dict(Seg=0x88e,Off=0x1560) and c['caller']==dict(Seg=0xb72,Off=0x27c)
    rect=[8,189,176,8]
    def region(label):
        path=output/'observe-r14'/(label+'.idx')
        checkpoint=next(c for c in warning['checkpoints'] if c['label']==label)
        assert sha(path)==checkpoint['indexed_sha256']
        raw=path.read_bytes()
        return b''.join(raw[y*320+8:y*320+184] for y in range(189,197))
    before,ready,after=[region(label) for label in ('warning-before','warning-fully-painted','dying-prompt-1')]
    assert before==after and before!=ready
    witness=dict(source_path=STUDY+'/observe-r14/receipt.json',before_index=STUDY+'/observe-r14/warning-before.idx',
        ready_index=STUDY+'/observe-r14/warning-fully-painted.idx',after_index=STUDY+'/observe-r14/dying-prompt-1.idx',
        entry=w['step'],returned=w['return_step'],field_entry=c['step'],rect=rect,before_sha256=hashlib.sha256(before).hexdigest(),ready_sha256=hashlib.sha256(ready).hexdigest(),
        return_key_at=4271000000,restored_by=4290000000)
    return config,dict(aliases=list(aliases.values()),bindings=bindings,paragraphs=paragraphs,fields=fields,menus=[],paths=paths,notice_witness=witness)


def generate(root,target):
    base=root/'workplace/probe'/BASE;config,data=derive(root);shutil.copytree(base,target)
    for name,column in [('en.tsv','source'),('zh-TW.tsv','translation'),('font-zh-TW.tsv','translation')]:
        values=catalog(base/name);values.update({a['key']:a[column] for a in data['aliases']});write_tsv(target/name,['key','text'],values.items())
    missing=set(''.join(a['translation'] for a in data['aliases']))-set(read(base/'glyphs-16.json')['glyphs'])-set('\n\r\t')
    assert not missing,('缺字',missing)
    proof=read(base/'provenance.json');proof['round_extension']=dict(base=BASE,base_files={f.name:sha(f) for f in base.iterdir()},data=data)
    write(target/'inputs.json',config);write(target/'provenance.json',proof)


def check_sources(inputs,config,proof,en,zh,glyphs):
    root=inputs.parent.parent.parent.parent;base=root/'workplace/probe'/BASE;expected,data=derive(root)
    assert config==expected,'round config'
    assert proof['round_extension']==dict(base=BASE,base_files={f.name:sha(f) for f in base.iterdir()},data=data),'round provenance'
    parent=read(base/'provenance.json');assert {k:v for k,v in proof.items() if k!='round_extension'}==parent
    old_en,old_zh=catalog(base/'en.tsv'),catalog(base/'zh-TW.tsv')
    assert en==dict(old_en,**{a['key']:a['source'] for a in data['aliases']})
    assert zh==dict(old_zh,**{a['key']:a['translation'] for a in data['aliases']}),'round translation'
    for f in base.iterdir():
        if f.name not in ('en.tsv','zh-TW.tsv','font-zh-TW.tsv','inputs.json','provenance.json'):assert f.read_bytes()==(inputs/f.name).read_bytes(),f.name
    assert catalog(inputs/'font-zh-TW.tsv')==dict(catalog(base/'font-zh-TW.tsv'),**{a['key']:a['translation'] for a in data['aliases']})
    return base,read(base/'inputs.json'),parent,old_en,old_zh,read(base/'glyphs-16.json')


def guards(root,output):
    source=output/'inputs-r6';cases=[]
    def check(p):return check_sources(p,read(p/'inputs.json'),read(p/'provenance.json'),catalog(p/'en.tsv'),catalog(p/'zh-TW.tsv'),read(p/'glyphs-16.json'))
    check(source)
    for name in ('caller','box','number','reference','translation','font'):
        with tempfile.TemporaryDirectory(dir=output,prefix='guard-') as directory:
            p=Path(directory);shutil.copytree(source,p,dirs_exist_ok=True);c=read(p/'inputs.json')
            if name=='caller':c['HUDParagraphs'][-1]['Caller']['Off']+=1;write(p/'inputs.json',c)
            elif name=='box':c['HUDParagraphs'][-1]['Spans'][0]['Rect'][2]+=8;write(p/'inputs.json',c)
            elif name=='number':
                proof=read(p/'provenance.json');next(r for r in proof['round_extension']['data']['paths']['3']['records'] if r['number'] is not None)['number']+=1
                write(p/'provenance.json',proof)
            elif name=='reference':
                proof=read(p/'provenance.json');proof['round_extension']['data']['notice_witness']['before_sha256']='0'*64;write(p/'provenance.json',proof)
            elif name=='translation':
                key=read(source/'provenance.json')['round_extension']['data']['aliases'][0]['key']
                (p/'zh-TW.tsv').write_text((p/'zh-TW.tsv').read_text().replace(key+'\t',key+'\t99',1))
            else:(p/'glyphs-16.json').write_text('{}\n')
            try:check(p)
            except AssertionError as e:assert str(e)=={'number':'round provenance','reference':'round provenance','translation':'round translation','font':'glyphs-16.json'}.get(name,'round config'),(name,e)
            else:raise AssertionError(name)
            cases.append(name)
    trace=read(output/'observe-r1/receipt.json');bad=copy.deepcopy(trace)
    p=next(i for i,p in enumerate(bad['paragraphs']) if p['source']['text']==catalog(source/'en.tsv')[DYING])
    chars=[c for c in bad['calls'] if c['paragraph_index']==p and c['format']['text']=='%c'];chars[16]['stack'][3]+=4
    try:hud_records(bad,read(source/'inputs.json')['HUDParagraphs'],catalog(source/'en.tsv'))
    except AssertionError:cases.append('wrapped-glyph-coordinate')
    else:raise AssertionError('換行座標變造未拒絕')
    with tempfile.TemporaryDirectory(dir=output,prefix='rebuild-') as directory:
        p=Path(directory)/'inputs';generate(root,p)
        assert {f.name for f in source.iterdir()}=={f.name for f in p.iterdir()}
        for f in source.iterdir():assert f.read_bytes()==(p/f.name).read_bytes(),f.name
    write(output/'guards.json',dict(cases=cases,rebuilt_files=len(list(source.iterdir())),tool_sha256=sha(Path(__file__))))


def caption_review(root,output):
    from PIL import Image
    paths={};key='round.1a0e55074a01fc9262bb'
    for number,native_number,label in ((13,14,'dying-prompt-3'),(10,15,'magic-round-1')):
        observed=output/('observe-r'+str(native_number));trace=read(observed/'receipt.json')
        checkpoint=next(c for c in trace['checkpoints'] if c['label']==label)
        raw=(observed/(label+'.idx')).read_bytes();assert hashlib.sha256(raw).hexdigest()==checkpoint['indexed_sha256']
        reference=Image.frombytes('P',(320,200),raw)
        reference.putpalette([v for color in checkpoint['palette'] for v in color])
        reference=reference.convert('RGB').crop((8,178,160,186)).resize((304,16),Image.Resampling.NEAREST)
        reference_hash=hashlib.sha256(reference.tobytes()).hexdigest()
        en,zh=[read(output/f'p{number}-{lang}-r9/receipt.json') for lang in ('en','zh')]
        first=next(c['return_step'] for c in trace['calls'] if c['vararg_1_candidate']['text']=='Spell:Magic Missile' and c['format']['text']=='%s')
        cache={};retained=absent=printing=0
        captions=[c for c in trace['calls'] if c['vararg_1_candidate']['text']=='Spell:Magic Missile' and c['format']['text']=='%s']
        wrappers=[trace['wrappers'][c['wrapper_index']] for c in captions]
        for ef,zf,state in zip(en['frames'],zh['frames'],zh['list_frames']):
            assert ef['step']==zf['step']==state['step']
            if zf['held'] or zf['step']<=first:continue
            if any(c['step']<=zf['step']<w['return_step'] for c,w in zip(captions,wrappers)):
                # 同字串重印時原版可只畫完部分；完整字串早已辨識，覆層必須仍覆蓋整句。
                assert any(w['Key']==key for w in state['words'] or []),('caption reprint',number,zf['step'])
                printing+=1
                continue
            if ef['File'] not in cache:
                image=Image.open(output/f'p{number}-en-r9'/ef['File']).convert('RGB')
                cache[ef['File']]=hashlib.sha256(image.crop((16,356,320,372)).tobytes()).hexdigest()
            original=cache[ef['File']]==reference_hash
            translated=any(w['Key']==key for w in state['words'] or [])
            assert original==translated,('spell-caption-lifetime',number,zf['step'],original,translated)
            if original:retained+=1
            else:absent+=1
        assert retained>0
        paths[str(number)]=dict(retained_frames=retained,absent_frames=absent,known_reprint_frames=printing,reference_sha256=reference_hash,
            native_indexed_sha256=checkpoint['indexed_sha256'],label=label,native_source='observe-r'+str(native_number),
            source_return=first,native_rect=[8,178,152,8])
    write(output/'caption-review-r2.json',dict(paths=paths,original_gpu_compared=True,held_frames_excluded=True,
        known_reprints_require_complete_overlay=True))


def review(root,output):
    from PIL import Image,ImageDraw
    data=read(output/'inputs-r6/provenance.json')['round_extension']['data'];keys={a['key'] for a in data['aliases']}
    paths={};visible=set();visible_numbers=set();panels=[];total_frames=total_held=0
    for number in RUNS:
        name=str(number);report_revision='r9' if number in (10,13) else 'r2'
        report=read(output/('check-p'+name+'-'+report_revision+'.json'))
        assert report['checker_sha256'] in (sha(root/'tools/ui_list_live_check.py'),sha(output/'checker-r2.py'),sha(output/'checker-r8.py'))
        revision='r9' if number in (10,13) else 'r2'
        enrun,zhrun=[read(output/('p'+name+'-'+lang+'-'+revision)/'receipt.json') for lang in ('en','zh')]
        intervals=[]
        for record in data['paths'][name]['records']:
            event_index=next(i for i,e in enumerate(zhrun['list_events']) if e['Kind']=='hud-before-glyph' and e['Step']==record['step'])
            frames=[];before=0
            for f,state in zip(zhrun['frames'],zhrun['list_frames']):
                if not record['step']<=f['step']<record['return_step']:continue
                if state['list_event_count']<=event_index:
                    assert f['step']==record['step'] and state['list_event_count']==event_index;before+=1
                else:frames.append(f)
            assert frames and all(f['held'] for f in frames),record['step']
            intervals.append(dict(step=record['step'],returned=record['return_step'],held_samples=len(frames),before_entry_samples=before))
        points=[]
        for f,state in zip(zhrun['frames'],zhrun['list_frames']):
            if f['held']:continue
            visible.update(w['Key'] for w in state['words'] or [] if w['Key'] in keys)
            visible_numbers.update(w['Number'] for w in state['words'] or [] if w.get('Number') is not None)
        for cp in zhrun['checkpoints']:
            index=next(i for i,f in enumerate(zhrun['frames']) if f['step']==cp['step'])
            points.append(dict(label=cp['label'],step=cp['step'],held=zhrun['frames'][index]['held']))
        paths[name]=dict(intervals=intervals,points=points)
        total_frames+=len(zhrun['frames']);total_held+=sum(f['held'] for f in zhrun['frames'])
        # 只收穩定且含新詞條的實際截點，不把保留畫面充作新輸出。
        for cp in zhrun['checkpoints']:
            index=next(i for i,f in enumerate(zhrun['frames']) if f['step']==cp['step']);zf=zhrun['frames'][index]
            present={w['Key'] for w in zhrun['list_frames'][index]['words'] or []}&keys
            if zf['held'] or not present or (number!=9 and any(p[0]==name for p in panels)):continue
            if number==9 and cp!=zhrun['checkpoints'][-1]:continue
            ef=next(f for f in enrun['frames'] if f['step']==zf['step'])
            panels.append((name,cp['label'],[Image.open(output/('p'+name+'-'+lang+'-'+revision)/f['File']).convert('RGB') for lang,f in (('en',ef),('zh',zf))]))
    assert visible==keys,('未實際可見',keys-visible)
    numbers={r['number'] for p in data['paths'].values() for r in p['records'] if r['number'] is not None}
    assert numbers<=visible_numbers,('數值未實際可見',numbers-visible_numbers)
    final=read(output/'p9-zh-r2/receipt.json')
    defeat_keys={b['Spans'][0]['Key'] for b in data['bindings'] if b['Caller']['Seg']==0x27c7}
    assert len(defeat_keys)==3 and defeat_keys<={w['Key'] for w in final['final_words']}
    assert not final['frames'][-1]['held']
    panel=Image.new('RGB',(1280,420*len(panels)),'#202020');draw=ImageDraw.Draw(panel)
    for row,(name,label,images) in enumerate(panels):
        for col,img in enumerate(images):
            panel.paste(img,(640*col,420*row+20));draw.text((640*col+4,420*row+2),'p'+name+' / '+label+' / '+('en' if col==0 else 'zh'),fill='white')
    panel.save(output/'review-r1.png')
    write(output/'visibility-review-r1.json',dict(paths=paths,visible_keys=sorted(visible),visible_numbers=sorted(visible_numbers),
        numeric_source_values=sorted(numbers),defeat_keys=sorted(defeat_keys),real_gpu_pairs=total_frames,held_pairs=total_held,review_panels=len(panels),
        scope='首戰正常續行至敗北；三段結尾同時保留，不宣稱勝利或全遊戲完成。'))


def evidence(root,output):
    assert read(output/'guards.json')['tool_sha256']==sha(Path(__file__))
    for number in RUNS:
        revision='r9' if number in (10,13) else 'r2'
        assert read(output/('check-p'+str(number)+'-'+revision+'.json'))['all_submitted_pixels_equal_expected']
    for name in ('visibility-review-r1.json','binary-rebuild-r6.json','native-binary-rebuild-r3.json','parent-check-r2.json','run-r9.json','caption-review-r2.json','regression-r5.json','copy-witness-r1.json'):assert (output/name).is_file(),name
    tools=root/'tools';names={'combat_rounds_inputs.py','ui_list_live_check.py','oracle_video_observer.go','ui-context.sh','ui_context_probe.go','ui-list-live.sh','early-live.sh'}
    names.update(f.name for f in (output/'programs-r6').glob('*.go'));pending=list(names)
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
    sources += [root/'workplace/input/dos/drkqueen/DQK.EXE',probe/'ui-context-probe',probe/'combat-finish-20261024/control-r4/final.state']
    sources += [root/'workplace/translation'/n for n in ('en.tsv','zh-TW.tsv','glossary.tsv','catalog.json','glossary-additions.tsv')]
    sources += [Path('/dkk/text')/n for n in ('glossary.tsv','name.zh-TW.tsv','name-lexicon-five.tsv')]
    def info(p):
        s=p.stat();assert(s.st_uid,s.st_gid)==(1000,1000),p
        return dict(bytes=s.st_size,sha256=sha(p),uid=s.st_uid,gid=s.st_gid)
    write(output/'evidence.json',dict(draft=True,runtime_integrated=False,rights='原版、全文、字模及畫格只留本機',
        engine_commit='f79eab6db8c64a524a06535e53e5d32b0bbcf7c8',
        go_image='sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581',
        pillow_image='sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48',
        tools={n:sha(tools/n) for n in names},sources={str(p):info(p) for p in sources},
        artifacts={str(p.relative_to(output)):info(p) for p in sorted(output.rglob('*')) if p.is_file()},
        effective=dict(program='programs-r6；四條既有路徑另保留 programs-r2 回歸收據',inputs='inputs-r6',gpu='pN-en/zh-r2（r5 逐位元組回歸）；p10/p13-en/zh-r9',native=list(RUNS))))


if __name__=='__main__':
    command,root,output=sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3])
    if command=='native':native(root,output)
    elif command=='prepare':generate(root,output/'inputs-r6')
    elif command=='guards':guards(root,output)
    elif command=='review':review(root,output)
    elif command=='caption':caption_review(root,output)
    elif command=='copy':write(output/'copy-witness-r1.json',copy_witness(output))
    elif command=='evidence':evidence(root,output)
    elif command=='audit':
        from combat_finish_inputs import audit
        audit(root,output)
    else:raise SystemExit('native | prepare | guards | caption | copy | review | evidence | audit')
