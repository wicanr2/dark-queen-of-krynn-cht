"""裝備回報與一至十五字元姓名的原版來源，限 Docker。"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")


def prepare(probe, output):
    assert not output.exists()
    output.mkdir()
    state=probe/"creation-20261024/observe-r4/final.state"
    request=dict(state_sha256=sha(state),start_steps=480000000,Actions=[
        dict(At=481000000,End=500000000,Kind="text",Key="i",Label="inventory"),
        dict(At=501000000,End=520000000,Kind="named",Key="Down",Label="select-bow"),
        dict(At=521000000,End=530000000,Kind="text",Key="r",Label="refusal-visible"),
        dict(At=530000000,End=540000000,Kind="text",Key="",Label="refusal-closed")])
    write(output/"refusal-request.json",request)
    names=output/"names"
    names.mkdir()
    for length in range(1,16):
        folder=names/f"length-{length:02}"
        folder.mkdir()
        boundary=length in (1,15)
        state=probe/("creation-20261024/observe-cold-role/final.state" if boundary else "creation-20261024/observe-done-values/final.state")
        actions=[]
        if boundary:
            actions=[dict(At=261000000,End=280000000,Kind="text",Key="c",Label="creation-sheet"),
                     dict(At=281000000,End=300000000,Kind="text",Key="d",Label="generated-values"),
                     dict(At=301000000,End=320000000,Kind="text",Key="d",Label="name-prompt")]
        actions += [dict(At=321000000,End=322000000,Kind="text",Key="A"*length,Label="name-entered"),
                    dict(At=323000000,End=340000000,Kind="named",Key="Return",Label="combat-icon")]
        for at,key,label in [(341,"d","save-question"),(361,"y","character-saved"),(381,"a","add-source"),
                             (401,"t","saved-characters"),(421,"a","added-character"),(441,"e","party"),
                             (461,"v","status"),(481,"i","inventory")]:
            actions.append(dict(At=at*1000000,End=(at+19)*1000000,Kind="text",Key=key,Label=label))
        write(folder/"request.json",dict(state_sha256=sha(state),start_steps=260000000 if boundary else 320000000,Actions=actions))
    print("已建立裝備拒絕及十五種姓名的正常輸入")


def boundaries(output):
    trace=read(output/"observe-refusal/receipt.json")
    wrapper=next(w for w in trace["wrappers"] if w["caller"]==dict(Seg=0x88e,Off=0x1560))
    assert wrapper["vararg_1_candidate"]["text"]=="already using Long Sword +2 "
    request=read(output/"refusal-request.json")
    actions=request["Actions"][:2]
    actions += [dict(At=521000000,End=wrapper["step"],Kind="text",Key="r",Label="before-refusal"),
                dict(At=wrapper["step"],End=wrapper["return_step"],Kind="text",Key="",Label="after-refusal"),
                dict(At=wrapper["return_step"],End=540000000,Kind="text",Key="",Label="restored-menu")]
    request["Actions"]=actions
    write(output/"refusal-boundaries-request.json",request)
    print(json.dumps(dict(entry=wrapper["step"],returned=wrapper["return_step"])))


def names_check(output):
    results=[]
    for length in range(1,16):
        folder=output/"names"/f"length-{length:02}"
        a,b=[read(folder/n/"receipt.json") for n in ("observe","control")]
        for key in ("source_commit","go_version","exe_sha256","state_sha256","request_sha256","probe_sha256","request","checkpoints"):
            assert a[key]==b[key],(length,key)
        assert all(not c["unimplemented"] for c in a["checkpoints"])
        filename="A"*min(length,8)+".qch"
        first=folder/"observe/scratch/SAVE"/filename
        second=folder/"control/scratch/SAVE"/filename
        assert first.stat().st_size==499 and first.read_bytes()==second.read_bytes()
        suffix=[c for c in a["calls"] if c["format"]["text"]=="%s" and c["vararg_1_candidate"]["text"]=="'s" and c["stack"][2]==8004]
        items=[c for c in a["calls"] if c["format"]["text"]=="%s" and c["vararg_1_candidate"]["text"]=="Items" and c["stack"][2]==8004]
        assert len(suffix)==len(items)==1
        assert [suffix[0]["stack"][3],items[0]["stack"][3]]==[8004+length*4,8016+length*4]
        assert a["checkpoints"][-1]["file_writes"]==[dict(Name="SAVE\\"+filename,N=n) for n in [414,17,17,17,17,17]]
        results.append(dict(length=length,suffix_call=suffix[0]["step"],items_call=items[0]["step"],
                            coordinates=[suffix[0]["stack"][3],items[0]["stack"][3]],checkpoints_equal=len(a["checkpoints"]),
                            receipt_sha256=sha(folder/"observe/receipt.json"),qch_sha256=sha(first)))
    write(output/"names-check.json",dict(cases=results,checkpoints_equal=sum(v["checkpoints_equal"] for v in results),
        limits="逐一正常輸入一至十五個 ASCII A；原版觀測／控制及角色檔相同，GUI 另列抽樣，不聲稱所有姓名字元均驗證"))
    print(json.dumps(dict(names=15,checkpoints_equal=sum(v["checkpoints_equal"] for v in results))))


def refusal_check(output):
    main=read(output/"observe-refusal/receipt.json")
    boundary=read(output/"observe-boundaries/receipt.json")
    for key in ("step","regs","ram_sha256","indexed_sha256","palette","keys_consumed","file_writes","unimplemented"):
        assert main["checkpoints"][-1][key]==boundary["checkpoints"][-1][key],key
    rows=[]
    for label in ("before-refusal","after-refusal"):
        cp=next(c for c in boundary["checkpoints"] if c["label"]==label)
        raw=(output/"observe-boundaries"/cp["indexed_file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==cp["indexed_sha256"]
        rect=b"".join(raw[y*320+8:y*320+312] for y in range(189,197))
        colors=sorted(set(rect))
        text_width=len(next(w["vararg_1_candidate"]["text"] for w in main["wrappers"] if w["caller"]==dict(Seg=0x88e,Off=0x1560)))*8
        painted=b"".join(raw[y*320+8:y*320+8+text_width] for y in range(189,197))
        painted_colors=sorted(set(painted))
        if label=="after-refusal":assert 15 in painted_colors and 23 in painted_colors and set(painted_colors)<={0,15,23},painted_colors
        rows.append(dict(label=label,step=cp["step"],colors=colors,rect_sha256=hashlib.sha256(rect).hexdigest(),
                         painted_rect=[8,189,text_width,8],painted_colors=painted_colors,painted_sha256=hashlib.sha256(painted).hexdigest()))
    assert not main["checkpoints"][-1]["file_writes"] and main["checkpoints"][-1]["keys_consumed"]==3
    write(output/"refusal-source-check.json",dict(boundary_state_equal=True,keys_consumed=3,rectangles=rows,
        limits="空字串動作只分割原版等待區間，最後完整狀態與未分割請求相同；不新增按鍵或更改拒絕規則"))
    print("回報前後色號與等待區間分割驗證通過")


def catalog(path):
    rows=[v.split("\t",1) for v in path.read_text().splitlines()]
    assert rows.pop(0)==["key","text"] and all(len(v)==2 and all(v) for v in rows)
    result=dict(rows)
    assert len(result)==len(rows)
    return result


def inputs(probe, texts, output):
    assert len(read(output/"names-check.json")["cases"])==15
    base=probe/"equipment-20261024/inputs-r4"
    target=output/"inputs-r1"
    assert not target.exists()
    shutil.copytree(base,target)
    config=read(target/"inputs.json");origin=read(target/"provenance.json")
    en,zh=catalog(target/"en.tsv"),catalog(target/"zh-TW.tsv")
    formal_en,formal_zh=catalog(texts/"en.tsv"),catalog(texts/"zh-TW.tsv")
    template="ui.eac62452d4fe9941a79c"
    assert formal_en[template].count("%s")==formal_zh[template].count("%s")==1
    prefix,tail=formal_en[template].split("%s")
    translation,translated_tail=formal_zh[template].split("%s")
    assert not tail and not translated_tail
    key="item-context.already-using"
    assert key not in en and key not in zh
    en[key],zh[key]=prefix,translation
    glyphs=read(target/"glyphs-16.json")["glyphs"]
    assert all(c in glyphs for c in translation)
    added=[]
    def reference(path):
        relative=Path(output.name)/path.relative_to(output)
        assert sha(probe/relative)==sha(path)
        return str(relative)
    def append(binding, path, call):
        if binding in config["Fields"]:return
        config["Fields"].append(binding)
        added.append(dict(binding=binding,source_path=reference(path),source_sha256=sha(path),call_step=call["step"],
                          first_glyph=call["first_glyph"],return_step=call["return_step"]))
    for length in range(1,16):
        path=output/"names"/f"length-{length:02}"/"observe/receipt.json"
        trace=read(path)
        for c in trace["calls"]:
            source=c["vararg_1_candidate"]["text"]
            if c["format"]["text"]!="%s" or source not in ("'s","Items") or c["stack"][2]!=8004:continue
            pane="suffix" if source=="'s" else "inventory"
            model=next(f for f in config["Fields"] if f["Pane"]==pane and en[f["Key"]]==source)
            binding=dict(model,RawX=c["stack"][3],RawY=c["stack"][2],Caller=c["caller"])
            append(binding,path,c)
    path=output/"observe-refusal/receipt.json"
    trace=read(path)
    c=next(c for c in trace["calls"] if c["vararg_1_candidate"]["text"]=="already using Long Sword +2 ")
    wrapper=trace["wrappers"][c["wrapper_index"]]
    assert wrapper["caller"]==dict(Seg=0x88e,Off=0x1560) and wrapper["format"]["text"]=="%s"
    item_key=next(k for k,v in en.items() if v=="Long Sword" and k.startswith("inventory."))
    for start,k in [(0,key),(len(prefix),item_key)]:
        source=c["vararg_1_candidate"]["text"]
        assert source[start:start+len(en[k])]==en[k]
        f=dict(Pane="callsite",Group="footer",Key=k,Start=start,Length=len(en[k]),RawX=c["stack"][3],RawY=c["stack"][2],
               Caller=c["caller"],UpperCaller=wrapper["caller"],UpperNative=[0,192],Color=0x8f,
               FormatSHA256=hashlib.sha256(b"%s").hexdigest(),UpperFormatSHA256=hashlib.sha256(b"%s").hexdigest(),
               SHA256=hashlib.sha256(source.encode()).hexdigest())
        append(f,path,c)
    context=dict(base=str(base.relative_to(probe)),base_files={p.name:sha(p) for p in base.iterdir() if p.is_file()},fields=added,
        prefix_key=key,formal_key=template,feedback_proof=dict(receipt="observe-refusal/receipt.json",sha256=sha(path)),
        feedback_boundaries=dict(receipt="observe-boundaries/receipt.json",sha256=sha(output/"observe-boundaries/receipt.json")),
        page_validation=dict(source_path=reference(path),sha256=sha(path)))
    origin["item_context_extension"]=context
    intervals=[]
    for group,end in (("calls","return_step"),("wrappers","return_step"),("fill_events","return_instruction_step"),("list_events","return_instruction_step")):
        intervals += [[max(480000000,v["step"]-2000),min(540000000,v[end]+2000)] for v in trace[group] or []]
    merged=[]
    for lo,hi in sorted(intervals):
        if merged and lo<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],hi)
        else:merged.append([lo,hi])
    config["fine_windows"]=merged
    (target/"inputs.json").write_text(json.dumps(config,ensure_ascii=False,indent=2)+"\n")
    (target/"provenance.json").write_text(json.dumps(origin,ensure_ascii=False,indent=2)+"\n")
    for name,values in [("en.tsv",en),("zh-TW.tsv",zh)]:
        (target/name).write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k,v in sorted(values.items())))
    font=catalog(target/"font-zh-TW.tsv");font[key]=translation
    (target/"font-zh-TW.tsv").write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k,v in sorted(font.items())))
    for name in ("ui-inputs","observe-combined-boundaries-r2"):
        source=base.parent/name;destination=output/name
        assert not destination.exists();shutil.copytree(source,destination)
    for length in (1,15):
        trace_path=output/"names"/f"length-{length:02}"/"observe/receipt.json"
        trace=read(trace_path)
        variant=output/f"inputs-name-{length:02}"
        shutil.copytree(target,variant)
        cfg=read(variant/"inputs.json");meta=read(variant/"provenance.json")
        intervals=[]
        for group,end in (("calls","return_step"),("wrappers","return_step"),("fill_events","return_instruction_step"),("list_events","return_instruction_step")):
            intervals += [[max(260000000,v["step"]-2000),min(500000000,v[end]+2000)] for v in trace[group] or []]
        intervals += [[max(260000000,v["step"]-2000),min(500000000,v["step"]+2000)] for v in trace["display_changes"] if v["step"]>260000000]
        merged=[]
        for lo,hi in sorted(intervals):
            if merged and lo<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],hi)
            else:merged.append([lo,hi])
        cfg["fine_windows"]=merged
        meta["item_context_extension"]["page_validation"]=dict(source_path=reference(trace_path),sha256=sha(trace_path))
        (variant/"inputs.json").write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+"\n")
        (variant/"provenance.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(dict(added_fields=len(added),prefix_key=key,catalog_keys=len(zh))))


def review(output):
    images=[];files=[]
    for length in (1,15):
        folder=output/f"name-{length:02}-zh-r1"
        run=read(folder/"receipt.json")
        frames={v["step"]:v for v in run["frames"]}
        layouts={v["step"]:v for v in run["list_frames"]}
        en=catalog(output/f"inputs-name-{length:02}/en.tsv")
        for label in ("name-entered","save-question","status","inventory"):
            cp=next(v for v in run["checkpoints"] if v["label"]==label)
            frame=frames[cp["step"]]
            assert not frame["held"]
            if label=="inventory":
                headers=[v for v in layouts[cp["step"]]["words"] if v["Group"]=="header"]
                assert [(en[v["Key"]],v["X"],v["Y"]) for v in headers]==[("'s",8+length*8,8),("Items",32+length*8,8)]
            images.append(dict(run=folder.name,label=label,**frame))
        before=next(v for v in run["checkpoints"] if v["label"]=="name-prompt")
        entered=next(v for v in run["checkpoints"] if v["label"]=="name-entered")
        assert frames[before["step"]]["SHA256"]!=frames[entered["step"]]["SHA256"],"姓名輸入必須在 Return 前可見"
        original=output/"names"/f"length-{length:02}"/"control/scratch/SAVE"/("A"*min(length,8)+".qch")
        for language in ("en","zh"):
            p=output/f"name-{length:02}-{language}-r1"/"scratch/SAVE"/original.name
            assert p.stat().st_size==499 and p.read_bytes()==original.read_bytes()
            files.append(dict(path=str(p.relative_to(output)),sha256=sha(p)))
    folder=output/"refusal-zh-r1";run=read(folder/"receipt.json")
    frames={v["step"]:v for v in run["frames"]}
    layouts={v["step"]:v for v in run["list_frames"]}
    en=catalog(output/"inputs-r1/en.tsv")
    for label in ("refusal-visible","refusal-closed"):
        cp=next(v for v in run["checkpoints"] if v["label"]==label)
        frame=frames[cp["step"]];assert not frame["held"]
        footer=[v for v in layouts[cp["step"]]["words"] if v["Group"]=="footer"]
        if label=="refusal-visible":
            assert [(en[v["Key"]],v["X"],v["Width"]) for v in footer]==[("already using ",8,112),("Long Sword",120,80)]
        else:assert len(footer)==6 and all(v.get("Button") for v in footer)
        images.append(dict(run=folder.name,label=label,**frame))
    write(output/"review-images.json",images)
    write(output/"display-check.json",dict(review_images=len(images),gui_qch=files,
        limits="一及十五字元的正常建角至物品頁；十五個姓名長度的原版來源另見 names-check.json"))
    print(json.dumps(dict(review_images=len(images),gui_qch_equal=len(files))))


def guards(output):
    results=[]
    for case,reason in [("upper",'f["UpperCaller"]==wrapper["caller"]'),
                        ("mask",'source[f["Start"]:f["Start"]+f["Length"]]'),
                        ("title","item context name title remains untranslated")]:
        target=output/("negative-"+case+"-r3")
        shutil.copytree(output/"inputs-name-15",target)
        config=read(target/"inputs.json");origin=read(target/"provenance.json")
        context=origin["item_context_extension"]
        if case=="title":
            remove=[next(v for v in context["fields"] if v["binding"]["Pane"]=="inventory")]
            assert len(remove)==1
            context["fields"]=[v for v in context["fields"] if v not in remove]
            config["Fields"]=[v for v in config["Fields"] if v!=remove[0]["binding"]]
        else:
            f=next(v["binding"] for v in context["fields"] if v["binding"]["Pane"]=="callsite" and v["binding"]["Start"]>0)
            runtime=next(v for v in config["Fields"] if v==f)
            if case=="upper":
                f["UpperCaller"]["Off"]+=1
                runtime["UpperCaller"]["Off"]+=1
            else:
                f["Length"]+=3;runtime["Length"]+=3
        for name,value in (("inputs.json",config),("provenance.json",origin)):
            (target/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
        result=output/("unexpected-"+case+".json")
        command=[sys.executable,str(Path(__file__).with_name("ui_list_live_check.py")),
            str(output/"name-15-en-r1"),str(output/"name-15-zh-r1"),str(target),
            str(output/"names/length-15/control"),str(output/"names/length-15/observe"),str(result)]
        p=subprocess.run(command,capture_output=True,text=True)
        assert p.returncode!=0 and not result.exists() and reason in p.stderr,p.stderr
        results.append(dict(case=case,reason=reason,stderr=p.stderr,returncode=p.returncode))
    write(output/"guards.json",dict(cases=results,checker_sha256=sha(Path(__file__).with_name("ui_list_live_check.py"))))
    print("三項來源、加值及標題防護通過")


def rebuild(probe, texts, output):
    import tempfile
    with tempfile.TemporaryDirectory() as temporary:
        fresh=Path(temporary)/output.name;fresh.mkdir()
        sources=["names-check.json","observe-refusal/receipt.json","observe-boundaries/receipt.json"]
        sources += [f"names/length-{length:02}/observe/receipt.json" for length in range(1,16)]
        for name in sources:
            p=fresh/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(output/name,p)
        inputs(probe,texts,fresh)
        checked=[]
        for name in ("inputs-r1","inputs-name-01","inputs-name-15"):
            assert sorted(p.name for p in (fresh/name).iterdir())==sorted(p.name for p in (output/name).iterdir())
            for p in sorted((fresh/name).iterdir()):
                assert p.read_bytes()==(output/name/p.name).read_bytes(),p
                checked.append(dict(path=f"{name}/{p.name}",sha256=sha(p)))
        write(output/"rebuild-check.json",dict(files=checked,generator_sha256=sha(Path(__file__))))
        print(json.dumps(dict(rebuilt_files_equal=len(checked))))


def evidence(root, output):
    parent=root/"workplace/probe/equipment-20261024/evidence.json"
    previous=read(parent);fixed=read(output/"run-r1.json")
    reports=[read(output/name) for name in ("refusal-gpu-check-final.json","name-01-gpu-check-final-r2.json","name-15-gpu-check-final.json")]
    assert sum(v["real_gpu_readback_frames"] for v in reports)==5975
    assert sum(v["original_checkpoints_equal"] for v in reports)==30
    assert all(v["checker_sha256"]==sha(root/"tools/ui_list_live_check.py") and v["all_submitted_pixels_equal_expected"] for v in reports)
    assert fixed["program_sha256"]==read(parent.parent/"run-r4.json")["program_sha256"]==sha(output/"programs/ui-list-live")
    for name,h in fixed["source_files"].items():assert sha(root/name)==sha(output/"programs"/Path(name).name)==h
    for name,files in fixed["inputs"].items():
        for file,h in files.items():assert sha(output/name/file)==h
    assert read(output/"rebuild-check.json")["generator_sha256"]==sha(Path(__file__))
    assert len(read(output/"guards.json")["cases"])==3
    assert read(output/"names-check.json")["checkpoints_equal"]==156
    names=list(previous["tools"])+["item_contexts.py"]
    snapshots=output/"tool-snapshots";snapshots.mkdir()
    for name in names:shutil.copy2(root/"tools"/name,snapshots/name)
    def item(p):return dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p))
    sources=[item(parent)]
    for old in previous["sources"]:
        if old["path"].startswith("workplace/translation/"):
            p=root/old["path"];assert sha(p)==old["sha256"];sources.append(item(p))
    sources.append(item(root/"workplace/input/dos/drkqueen/DQK.EXE"))
    target=output/"evidence.json"
    artifacts=[item(p) for p in sorted(output.rglob("*")) if p.is_file() and p!=target]
    write(target,dict(draft=True,sources=sources,artifacts=artifacts,tools={n:sha(root/"tools"/n) for n in names},
        docker_images=previous["docker_images"],reports=reports,names=read(output/"names-check.json"),
        guards=read(output/"guards.json"),runtime_unchanged=True,
        limits="一至十五個 ASCII A 的原版標題來源；GUI 僅一、十五字元及長劍裝備中的長弓拒絕回報。未涵蓋任意姓名字元、裝備變體、正式入口或全遊戲中文化。"))
    print(json.dumps(dict(artifacts=len(artifacts),tools=len(names),sources=len(sources))))


if __name__=="__main__":
    if sys.argv[1]=="prepare":prepare(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="boundaries":boundaries(Path(sys.argv[2]))
    elif sys.argv[1]=="names-check":names_check(Path(sys.argv[2]))
    elif sys.argv[1]=="refusal-check":refusal_check(Path(sys.argv[2]))
    elif sys.argv[1]=="inputs":inputs(*map(Path,sys.argv[2:5]))
    elif sys.argv[1]=="review":review(Path(sys.argv[2]))
    elif sys.argv[1]=="guards":guards(Path(sys.argv[2]))
    elif sys.argv[1]=="rebuild":rebuild(*map(Path,sys.argv[2:5]))
    elif sys.argv[1]=="evidence":evidence(*map(Path,sys.argv[2:4]))
    else:raise SystemExit("未知子命令")
