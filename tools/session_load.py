"""同程序讀檔的 DRAFT 請求、來源綁定與本機證據工具；只在 Docker 內執行。"""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path


def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text())
def write(path,data):
    assert not path.exists(),str(path)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
def catalog(path):
    lines=path.read_text().splitlines()
    assert lines[0]=="key\ttext"
    rows=[line.split("\t") for line in lines[1:]]
    assert all(len(row)==2 and all(row) for row in rows)
    result=dict(rows);assert len(result)==len(rows)
    return result


def prepare(probe,output):
    source=probe/"load-prompts-live-20261023"
    assert output.parent==probe and (probe.stat().st_uid,probe.stat().st_gid)==(os.getuid(),os.getgid())
    if not output.exists():output.mkdir()
    assert output.is_dir() and not (output/"boot.json").exists()
    copied=[]
    for name in ["boot.json","native-cold","ui-inputs"]:
        original=source/name;target=output/name
        if original.is_dir():shutil.copytree(original,target)
        else:shutil.copyfile(original,target)
        paths=original.rglob("*") if original.is_dir() else [original]
        for p in paths:
            if p.is_file():
                q=output/p.relative_to(source)
                assert sha(q.read_bytes())==sha(p.read_bytes())
                copied.append(dict(source=str(p.relative_to(probe)),target=str(q.relative_to(output)),sha256=sha(p.read_bytes())))
    from load_prompt_inputs import prompt_mask_width
    path=output/"ui-inputs/bindings.json";config=read(path);sources=catalog(output/"ui-inputs/en.tsv")
    base_binding_sha=sha(path.read_bytes())
    for binding in config["Bindings"]:binding["Width"]=prompt_mask_width(sources[binding["Key"]],binding["Button"])
    path.write_text(json.dumps(config,indent=2)+"\n")
    copied=[row for row in copied if row["target"]!="ui-inputs/bindings.json"]
    request=read(source/"gameplay-request.json")
    request["Actions"] += [dict(At=t,End=e,Kind=k,Key=v,Label=l) for t,e,k,v,l in [
        (501000000,520000000,"text","i","reload-inn"),
        (521000000,540000000,"named","Return","reload-camp"),
        (541000000,560000000,"text","l","unsaved-question"),
        (561000000,580000000,"text","n","decline-reload"),
        (581000000,600000000,"text","l","unsaved-again"),
        (601000000,620000000,"text","y","accept-reload"),
        (621000000,640000000,"text","t","reload-slots"),
        (641000000,660000000,"text","j","reloaded-role-menu"),
        (661000000,700000000,"text","b","reloaded-city"),
        (701000000,720000000,"text","i","reloaded-inn"),
        (721000000,740000000,"named","Return","reloaded-camp"),
        (741000000,760000000,"text","v","reloaded-status"),
        (761000000,780000000,"text","e","reloaded-return-camp"),
        (781000000,800000000,"text","e","reloaded-return-city")]]
    write(output/"gameplay-request.json",request)
    shutil.copyfile(output/"gameplay-request.json",output/"request-full-r1.json")
    write(output/"native-reuse.json",dict(files=copied,derived_bindings=dict(base_sha256=base_binding_sha,sha256=sha(path.read_bytes()),rule="保留末尾定位空白與四像素原版邊框"),limits="重用相同 boot 的原版前段；提示遮罩依原版邊框衍生，呈現程序另跑"))
    print(json.dumps(dict(actions=len(request["Actions"]),reused=len(copied))))


def inputs(probe,text,output):
    base=probe/"services-trade-20261023/inputs-r2"
    target=output/"inputs-r1";assert not target.exists()
    shutil.copytree(base,target)
    boundaries(probe,output)
    en,zh=catalog(target/"en.tsv"),catalog(target/"zh-TW.tsv")
    formal_en,formal_zh=catalog(text/"en.tsv"),catalog(text/"zh-TW.tsv")
    short_en,short_zh=catalog(output/"ui-inputs/en.tsv"),catalog(output/"ui-inputs/zh-TW.tsv")
    roles=probe/"interactive-menu-inputs-20261022"
    role_zh=catalog(roles/"zh-TW.tsv")
    shutil.copyfile(roles/"zh-TW.tsv",target/"role.zh-TW.tsv")
    shutil.copyfile(roles/"glyphs-20.json",target/"glyphs-20.json")
    trace=read(output/"observe-r1/receipt.json")
    config=read(target/"inputs.json")
    chosen=[];seen=set();origins=[]
    prompts={"Game not saved. Load anyway? ","load from where? ","load which game:","Loading...Please Wait"}
    role_signature="191c0ba49dc03bfaceb8be1ab19c0d92efb10341e05b2c851e46682a74451ed1"
    source_signature="96d6d47227be681ef02494b29b4823d71a79622be36972815bf1888e89cc68e0"
    confirm_signature="dd8ab79b6b6e798b76e268c5cc46b3ef4370fb5f94cca8f543c1db2a6e877738"
    for call in trace["calls"]:
        if call["step"]<540000000:continue
        source=call["vararg_1_candidate"]["text"] if call["format"]["text"]=="%s" else call["format"]["text"]
        button=call["caller"]==dict(Seg=0xCEB,Off=0x1BE)
        signature=trace["menus"][call["menu_index"]]["Signature"] if button else ""
        role=signature==role_signature
        if not (source in prompts or signature in (role_signature,source_signature,confirm_signature)):continue
        identity=(source,signature)
        if identity in seen:continue
        seen.add(identity)
        assert call["step"]<call["first_glyph"]<call["return_step"]
        lexical=source.rstrip(" ") if not button else source
        if role:
            selected=sha(source.encode());translation=role_zh[selected]
            origin=dict(role_key=selected,source=source,translation=translation)
        elif source in short_en.values():
            selected=next(k for k,v in short_en.items() if v==source);translation=short_zh[selected]
            origin=dict(short_key=selected,source=source,translation=translation)
        else:
            matches=[k for k,v in formal_en.items() if k.startswith("ui.") and v.rstrip(" ")==lexical]
            assert len(matches)==1,(source,matches)
            selected=matches[0];translation=formal_zh[selected]
            origin=dict(formal_key=selected,source=source,translation=translation)
        key=("role." if role else "session-load.")+sha(source.encode())[:20]
        if key in en:assert (en[key],zh[key])==(lexical,translation)
        en[key],zh[key]=lexical,translation
        field=dict(Pane="menu" if button else "callsite",Group="footer",Key=key,SHA256=sha(source.encode()),
            FormatSHA256=sha(call["format"]["text"].encode()),Start=0,Length=len(lexical),RawX=call["stack"][3],RawY=call["stack"][2],Caller=call["caller"])
        if button:
            field["MenuSignature"]=signature
            config["Menus"][signature]="role" if role else "load-source" if signature==source_signature else "confirm"
            if role:field["FontSize"]=20
        else:
            wrapper=trace["wrappers"][call["wrapper_index"]]
            assert wrapper["step"]<call["step"]<call["return_step"]<wrapper["return_step"]
            field.update(UpperCaller=wrapper["caller"],UpperNative=[(wrapper["stack"][i]&255)*8 for i in (2,3)],Color=call["stack"][4])
            if wrapper["format"]["text"]!=source:field["UpperFormatSHA256"]=sha(wrapper["format"]["text"].encode())
            if call["stack"][4]==0x70:field["BackgroundOverride"]=7
            if source=="load which game:":field["Width"]=124
        assert len(translation)*(10 if role else 8)<=len(lexical)*8
        config["Fields"].append(field)
        chosen.append(field);origins.append(dict(binding=field,origin=origin,call_step=call["step"]))
    assert len(chosen)==21 and sum(f.get("FontSize")==20 for f in chosen)==12
    windows=[]
    for kind,endkey in [("calls","return_step"),("wrappers","return_step"),("fill_events","return_instruction_step"),("paragraphs","return_step")]:
        for event in trace[kind] or []:windows.append([max(355000000,event["step"]-2000),min(800000000,event[endkey]+2000)])
    windows += [[a["at"],min(a["at"]+1000000,a["end"])] for a in trace["request"]["actions"]]
    merged=[]
    for start,end in sorted(windows):
        if merged and start<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],end)
        else:merged.append([start,end])
    config["fine_windows"]=merged
    (target/"inputs.json").write_text(json.dumps(config,indent=2)+"\n")
    for name,rows in [("en.tsv",en),("zh-TW.tsv",zh)]:
        (target/name).write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k,v in sorted(rows.items())))
    provenance=read(target/"provenance.json")
    provenance["session_load_extension"]=dict(base="services-trade-20261023/inputs-r2",base_files={n:sha((base/n).read_bytes()) for n in ["en.tsv","zh-TW.tsv","inputs.json"]},
        observed_path=str((output/"observe-r1/receipt.json").relative_to(probe)),
        observed_sha256=sha((output/"observe-r1/receipt.json").read_bytes()),added=origins,
        formal_files={n:sha((text/n).read_bytes()) for n in ["en.tsv","zh-TW.tsv"]},
        role_files={n:sha((roles/n).read_bytes()) for n in ["zh-TW.tsv","glyphs-20.json"]})
    (target/"provenance.json").write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(dict(added=len(chosen),words=len(en),role_words=12,windows=len(merged))))


def boundaries(probe,output):
    base=probe/"services-trade-20261023/inputs-r2"
    reference=read(base/"provenance.json")["trade_extension"]["feedback_boundaries"]
    relative=Path(reference["receipt"])
    assert len(relative.parts)==2 and relative.name=="receipt.json" and ".." not in relative.parts
    source=base.parent/relative.parent;target=output/relative.parent
    assert sha((source/"receipt.json").read_bytes())==reference["sha256"] and not target.exists()
    shutil.copytree(source,target)
    files=[]
    for p in source.rglob("*"):
        if p.is_file():
            q=target/p.relative_to(source);assert sha(q.read_bytes())==sha(p.read_bytes())
            files.append(dict(source=str(p.relative_to(probe)),target=str(q.relative_to(output)),sha256=sha(p.read_bytes())))
    write(output/"boundary-reuse.json",dict(files=files,limits="只補齊原輸入的相對證據依賴，不更動已執行的 catalog、字模或綁定"))


def reuse_original(probe,output,previous):
    source=probe/previous
    assert (output/"boot.json").read_bytes()==(source/"boot.json").read_bytes()
    assert (output/"gameplay-request.json").read_bytes()==(source/"gameplay-request.json").read_bytes()
    copied=[]
    for original_name,new_name in [("observe-mz-r2","observe-r1"),("control-mz-r2","control-r1"),("original-check-mz-r2.json","original-check.json")]:
        original=source/original_name;target=output/new_name;assert not target.exists()
        if original.is_dir():
            receipt=read(original/"receipt.json")
            assert receipt["cold_boot"] and not receipt["snapshot_loaded"]
            assert receipt["request_sha256"]==sha((output/"gameplay-request.json").read_bytes())
            assert receipt["boot_request_sha256"]==sha((output/"boot.json").read_bytes())
            shutil.copytree(original,target)
        else:shutil.copyfile(original,target)
        paths=original.rglob("*") if original.is_dir() else [original]
        for p in paths:
            if p.is_file():
                q=target/p.relative_to(original) if original.is_dir() else target
                assert sha(p.read_bytes())==sha(q.read_bytes())
                copied.append(dict(source=str(p.relative_to(probe)),target=str(q.relative_to(output)),sha256=sha(q.read_bytes())))
    write(output/"original-mz-reuse.json",dict(files=copied,limits="同一 boot 與後段請求，逐檔保留全程 MZ 原版收據；沒有載入快照作最終原版對照"))


def glyphs(probe,output):
    target=output/"inputs-r1/glyphs-16.json"
    original=read(probe/"services-trade-20261023/inputs-r2/glyphs-16.json")
    extra=read(target)
    assert all(original[k]==extra[k] for k in ("size","height","font_sha256"))
    for key,value in extra["glyphs"].items():
        if key in original["glyphs"]:assert original["glyphs"][key]==value,key
    write(output/"inputs-r1/glyphs-added-16.json",extra)
    original["glyphs"].update(extra["glyphs"])
    target.write_text(json.dumps(original,ensure_ascii=False)+"\n")
    print(json.dumps(dict(glyphs=len(original["glyphs"]))))


def legacy(probe,output):
    source=probe/"load-prompts-live-20261023"
    copied=[]
    for name in ["legacy-observe-r1","legacy-control-r1","legacy-original-check.json"]:
        original=source/name;target=output/name;assert not target.exists()
        if original.is_dir():shutil.copytree(original,target)
        else:shutil.copyfile(original,target)
        paths=original.rglob("*") if original.is_dir() else [original]
        for p in paths:
            if p.is_file():
                q=output/p.relative_to(source)
                assert sha(q.read_bytes())==sha(p.read_bytes())
                copied.append(dict(source=str(p.relative_to(probe)),target=str(q.relative_to(output)),sha256=sha(p.read_bytes())))
    write(output/"legacy-reuse.json",dict(files=copied))


def guards(output):
    target=output/"session-guards";assert not target.exists();target.mkdir()
    for name in ["font16","role-text","toolbar-font","prompt-background"]:
        folder=target/name;shutil.copytree(output/"inputs-r1",folder)
        config=read(folder/"inputs.json")
        if name=="font16":
            shutil.copyfile(folder/"glyphs-16.json",folder/"glyphs-20.json")
        elif name=="role-text":
            key=next(f["Key"] for f in config["Fields"] if f.get("FontSize")==20)
            words=catalog(folder/"zh-TW.tsv")
            words[key]=words[next(k for k in words if k!=key)]
            (folder/"zh-TW.tsv").write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k,v in words.items()))
        elif name=="toolbar-font":
            next(f for f in config["Fields"] if f["Pane"]=="menu" and not f.get("FontSize"))["FontSize"]=20
        else:
            next(f for f in config["Fields"] if f["SHA256"]=="27f835efb80b2af751f472f06171037b89065c6143ee753de6944a644900b081")["BackgroundOverride"]=6
        (folder/"inputs.json").write_text(json.dumps(config,indent=2)+"\n")


def check_guards(output):
    expected={"font16":"角色管理需沿用已確認的 20px 輸入","role-text":"角色管理需沿用已確認的 20px 輸入",
              "toolbar-font":"未驗證的角色字級綁定","prompt-background":"未驗證的提示欄位幾何或顏色"}
    results=[]
    for name,message in expected.items():
        log=output/"session-guards"/(name+".log")
        assert "panic: "+message in log.read_text(),name
        assert not (output/"session-guards"/(name+"-run")/"receipt.json").exists()
        results.append(dict(name=name,rejected=True,reason=message,log_sha256=sha(log.read_bytes())))
    write(output/"session-guards/results.json",dict(cases=results))
    print(json.dumps(results,ensure_ascii=False))


def review(output,run_name):
    assert Path(run_name).name==run_name
    run=output/run_name;receipt=read(run/"receipt.json")
    config=read(output/"inputs-r1/inputs.json")
    frames={f["step"]:f for f in receipt["frames"]}
    layouts={f["step"]:f for f in receipt["list_frames"]}
    role_keys={f["Key"] for f in config["Fields"] if f.get("FontSize")==20}
    added=read(output/"inputs-r1/provenance.json")["session_load_extension"]["added"]
    visible={row["binding"]["Key"]:0 for row in added}
    for step,state in layouts.items():
        if not frames[step]["held"]:
            for word in state["words"] or []:
                if word["Key"] in visible:visible[word["Key"]]+=1
    assert all(visible.values()),("new caption hidden",visible)
    images=[]
    for step in [560000000,580000000,620000000,640000000,660000000,700000000,740000000,760000000,800000000]:
        frame=frames[step];assert not frame["held"]
        words=layouts[step]["words"] or []
        if step==660000000:
            assert {w["Key"] for w in words if w.get("FontSize")==20}==role_keys
        images.append(dict(step=step,file=run_name+"/"+frame["File"],rgba_sha256=frame["SHA256"],words=words))
    loading=next((step,state) for step,state in layouts.items() if not frames[step]["held"] and any(w["Key"]=="session-load.e920b38b45dd6a828b46" for w in state["words"] or []))
    step,state=loading;frame=frames[step]
    images.append(dict(step=step,file=run_name+"/"+frame["File"],rgba_sha256=frame["SHA256"],words=state["words"]))
    write(output/"review-images.json",dict(images=images,visible_frames=visible))
    print(json.dumps([dict(step=i["step"],file=i["file"]) for i in images]))


def evidence(project,output):
    probe=project/"workplace/probe"
    run=read(output/"run-r4.json")
    assert run["program_sha256"]==sha((probe/"ui-list-live").read_bytes())
    for name,digest in run["source_files"].items():assert sha((project/name).read_bytes())==digest,name
    for name,digest in run["inputs"].items():assert sha((output/"inputs-r1"/name).read_bytes())==digest,name
    assert run["boot_sha256"]==sha((output/"boot.json").read_bytes())
    assert run["gameplay_request_sha256"]==sha((output/"gameplay-request.json").read_bytes())
    cold,game,legacy=[read(output/n) for n in ["cold-check.json","gameplay-check.json","legacy-check.json"]]
    assert cold["original_checkpoints_equal"]==12 and game["original_checkpoints_equal"]==26 and legacy["original_checkpoints_equal"]==16
    assert cold["checker_sha256"]==sha((project/"tools/cold_load.py").read_bytes())
    for report in [game,legacy]:
        assert report["checker_sha256"]==sha((project/"tools/ui_list_live_check.py").read_bytes())
        assert report["all_submitted_pixels_equal_expected"] and report["field_lifetime_model_equal"]
    assert read(output/"original-check.json")["checkpoints_equal"]==26
    request_sha=sha((output/"gameplay-request.json").read_bytes())
    for name in ["observe-r1","control-r1"]:
        original=read(output/name/"receipt.json")
        assert original["request_sha256"]==request_sha and original["cold_boot"] and not original["snapshot_loaded"]
        assert original["boot_request_sha256"]==run["boot_sha256"] and len(original["cold_checkpoints"])==12
    visible=read(output/"review-images.json")["visible_frames"]
    assert len(visible)==21 and all(visible.values())
    guards=read(output/"session-guards/results.json")
    assert len(guards["cases"])==4 and all(c["rejected"] for c in guards["cases"])
    assert len((output/"runtime-guards/results.tsv").read_text().splitlines())==5
    for name in cold["runs"]:
        events=dict(line.split() for line in (output/(name+"-memory-events.txt")).read_text().splitlines())
        assert events["oom"]==events["oom_kill"]=="0"
    base=probe/"services-trade-20261023/inputs-r2";inputs=output/"inputs-r1"
    for name in ["reader.zh-TW.tsv","illustrations.json"]:assert (base/name).read_bytes()==(inputs/name).read_bytes()
    old,new=read(base/"glyphs-16.json"),read(inputs/"glyphs-16.json")
    assert len(old["glyphs"])==1633 and len(new["glyphs"])==1637
    assert all(new["glyphs"][k]==v for k,v in old["glyphs"].items())
    parent=read(probe/"load-prompts-live-20261023/evidence.json")
    names=list(parent["tools"])+["session_load.py"]
    snapshots=output/"tool-snapshots";assert not snapshots.exists();snapshots.mkdir()
    tools={}
    for name in names:
        source=project/"tools"/name;shutil.copyfile(source,snapshots/name);tools[name]=sha(source.read_bytes())
    for name in ["ui-list-live","ui-context-probe"]:shutil.copyfile(probe/name,snapshots/name)
    def fingerprint(path):
        h=hashlib.sha256()
        with path.open("rb") as stream:
            while block:=stream.read(1<<20):h.update(block)
        return dict(path=str(path.relative_to(project)),bytes=path.stat().st_size,sha256=h.hexdigest())
    artifacts=[fingerprint(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name!="evidence.json"]
    sources=[project/"workplace/translation"/n for n in ["en.tsv","zh-TW.tsv","glossary.tsv","catalog.json","glossary-additions.tsv"]]
    sources += [probe/"load-prompts-live-20261023/evidence.json",project/"workplace/input/dos/drkqueen/DQK.EXE"]
    previous=probe/"session-load-20261023"
    diagnostics=[previous/name for name in ["ram-diagnostic.json","clear-lifecycle-r3.json","run-r3.json","diagnostic-known-border-only.json"]]
    diagnostics += [p for folder in ["failed-r1-tools","failed-r2-tools","r3-programs"] for p in sorted((previous/folder).rglob("*")) if p.is_file()]
    diagnostics += [previous/name/"receipt.json" for name in ["zh-r1","en-r3","zh-r3","control-r3","control-mz-r2"]]
    assert all(p.is_file() for p in diagnostics)
    result=dict(draft=True,scope="連續 MZ 冷讀 J、營地未儲存拒絕／接受、再次讀 J、20px 角色選單及返回城市／角色頁",
        source_commit="f79eab6db8c64a524a06535e53e5d32b0bbcf7c8",docker_images=parent["docker_images"],
        tools=tools,artifacts=artifacts,sources=[fingerprint(p) for p in sources],cold=cold,gameplay=game,legacy=legacy,guards=guards,execution=run,
        visible_frames=visible,prior_diagnostics=dict(accepted=False,files=[fingerprint(p) for p in diagnostics],reason="r1 載入中不可見；r2 條件雜湊錯誤；r3 邊框及連續清畫面未通過；快照 RAM 不作最終原版基準"),
        preserved_gameplay_glyphs=1633,gameplay_glyphs=1637,role_glyphs_sha256=sha((inputs/"glyphs-20.json").read_bytes()),
        rights="原版、存檔、全文、字模及畫格只留本機 workplace，不加入 Git",
        limits="DRAFT；未驗全部槽位、跨作角色匯入、實體鍵盤、戰鬥、說明面板、正式入口或完整中文化")
    write(output/"evidence.json",result)
    print(json.dumps(dict(artifacts=len(artifacts),tools=len(tools),cold_frames=cold["gpu_frames_verified"],gameplay_frames=game["real_gpu_readback_frames"])))


if __name__=="__main__":
    if sys.argv[1]=="prepare":prepare(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="inputs":inputs(*map(Path,sys.argv[2:5]))
    elif sys.argv[1]=="boundaries":boundaries(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="reuse-original":reuse_original(*map(Path,sys.argv[2:4]),sys.argv[4])
    elif sys.argv[1]=="glyphs":glyphs(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="legacy":legacy(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="guards":guards(Path(sys.argv[2]))
    elif sys.argv[1]=="check-guards":check_guards(Path(sys.argv[2]))
    elif sys.argv[1]=="review":review(Path(sys.argv[2]),sys.argv[3])
    elif sys.argv[1]=="evidence":evidence(*map(Path,sys.argv[2:4]))
    else:raise SystemExit("未知命令")
