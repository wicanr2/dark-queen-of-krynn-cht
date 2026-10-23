"""開頭、姓名、查驗與旅店標籤的 DRAFT 輸入；只在 Docker 內執行。"""
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
    rows=[line.split("\t") for line in path.read_text().splitlines()]
    assert rows.pop(0)==["key","text"] and all(len(row)==2 and all(row) for row in rows)
    result=dict(rows);assert len(result)==len(rows)
    return result


def prepare(probe,output):
    parent=probe/"session-load-20261023-r4"
    assert output.parent==probe and not output.exists()
    assert (probe.stat().st_uid,probe.stat().st_gid)==(os.getuid(),os.getgid())
    output.mkdir()
    for name in ["boot.json","native-cold","ui-inputs","inputs-r1"]:
        source=parent/name;target=output/name
        if source.is_dir():shutil.copytree(source,target)
        else:shutil.copyfile(source,target)
    request=read(parent/"gameplay-request.json")
    request["Actions"]=[a for a in request["Actions"] if a["End"]<=700000000]
    assert len(request["Actions"])==21 and request["Actions"][-1]["Label"]=="reloaded-city"
    write(output/"gameplay-request.json",request)
    files=[]
    for name in ["boot.json","native-cold"]:
        source=parent/name
        for p in source.rglob("*") if source.is_dir() else [source]:
            if p.is_file():
                q=output/p.relative_to(parent);assert sha(q.read_bytes())==sha(p.read_bytes())
                files.append(dict(source=str(p.relative_to(probe)),target=str(q.relative_to(output)),sha256=sha(p.read_bytes())))
    write(output/"native-reuse.json",dict(files=files,limits="只重用相同十二動作 MZ 前段；後段二十一步由原版重新執行"))
    print(json.dumps(dict(actions=21,reused=len(files))))


def inputs(probe,text,output):
    import csv
    from load_prompt_inputs import prompt_mask_width
    parent=probe/"session-load-20261023-r4"
    cold_path=probe/"load-prompts-20261023/observe-cold-r3/receipt.json"
    cold=read(cold_path);post=read(output/"observe-r1/receipt.json")
    formal_en,formal_zh=catalog(text/"en.tsv"),catalog(text/"zh-TW.tsv")
    review={r["key"]:r for r in csv.DictReader((text/"startup-ui-review.tsv").open(),delimiter="\t")}
    ui=output/"ui-inputs";config=read(ui/"bindings.json");en,zh=catalog(ui/"en.tsv"),catalog(ui/"zh-TW.tsv")
    origin=read(ui/"provenance.json")
    origin["source_files"]["startup-ui-review.tsv"]=sha((text/"startup-ui-review.tsv").read_bytes())
    cases=[("play","Play",8,189,"opening"),("demo","Demo",48,189,"opening"),("quit","Quit",88,189,"opening"),
           ("role-name","Name",8004,8008,"role-name"),("party-name","Name",8068,8008,"party-name"),
           ("quiz-page"," journal, page ",8012,8008,"quiz"),("quiz-word"," what is word # ",8012,8016,"quiz"),
           ("quiz-heading"," after the heading ",8012,8024,"quiz"),("quiz-enter","Enter ",8004,189,"quiz")]
    added=[]
    for name,source,x,y,group in cases:
        call=next(c for c in cold["calls"] if c["stack"][2:4]==[y,x] and
                  (c["vararg_1_candidate"]["text"] if c["format"]["text"]=="%s" else c["format"]["text"])==source)
        key="startup."+name;assert key not in en
        matches=[k for k,v in formal_en.items() if k.startswith("ui.") and v==source]
        if matches:
            assert len(matches)==1;selected=matches[0];translation=formal_zh[selected]
            record=dict(formal_key=selected,en=source,zh=translation,rule="exact")
        else:
            row=review[key];assert row["en"]==source;translation=row["zh-TW"]
            record=dict(startup_review_key=key,review=row)
        en[key],zh[key]=source,translation;origin["origins"][key]=record
        button=group=="opening"
        binding=dict(Key=key,Group=group,SourceSHA256=sha(source.encode()),FormatSHA256=sha(call["format"]["text"].encode()),
                     UpperCaller=dict(Seg=0,Off=0),UpperFormatSHA256="",MenuSignature="",Caller=call["caller"],
                     RawX=x,RawY=y,X=x if x<400 else (x-8000)*2,Y=y if y<400 else (y-8000)*2,
                     Width=prompt_mask_width(source,button),Background=23,Button=button)
        if button:
            signature=cold["menus"][call["menu_index"]]["Signature"]
            binding["MenuSignature"]=signature;config["Menus"][signature]="opening"
        else:
            binding["Color"]=call["stack"][4]
            if call["wrapper_index"]>=0:
                wrapper=cold["wrappers"][call["wrapper_index"]]
                binding["UpperCaller"]=wrapper["caller"];binding["UpperFormatSHA256"]=sha(wrapper["format"]["text"].encode())
            else:assert name=="quiz-enter"
        assert len(translation)*8<=binding["Width"]
        assert call["step"]<call["first_glyph"]<call["return_step"]
        config["Bindings"].append(binding)
        origin["glyph_evidence"].append(dict(key=key,call_step=call["step"],first_glyph=call["first_glyph"],glyph_calls=call.get("glyph_calls")))
        added.append(dict(binding=binding,call_step=call["step"]))
    assert len(config["Bindings"])==len(en)==len(zh)==15
    # 原版的字串、上層組句與填色區間共同決定取樣；等待輸入不必逐指令抓圖。
    intervals=[]
    for kind,end_key in [("calls","return_step"),("wrappers","return_step"),("fill_events","return_instruction_step")]:
        for event in cold[kind] or []:
            if 220000000<=event["step"]<355000000:
                intervals.append([max(220000000,event["step"]-2000),min(355000000,event[end_key]+2000)])
    merged=[]
    for start,end in sorted(intervals):
        if merged and start<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],end)
        else:merged.append([start,end])
    config["FineWindows"]=merged
    origin["continuation_trace"]=dict(path=str((output/"observe-r1/receipt.json")),sha256=sha((output/"observe-r1/receipt.json").read_bytes()))
    origin["startup_extension"]=dict(parent=str(parent/"ui-inputs"),added=added,limits="保留英文查驗標題、頁碼、字序及答案；不自動回答")
    for name,rows in [("en.tsv",en),("zh-TW.tsv",zh)]:
        (ui/name).write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k,v in sorted(rows.items())))
    (ui/"bindings.json").write_text(json.dumps(config,indent=2)+"\n")
    (ui/"provenance.json").write_text(json.dumps(origin,ensure_ascii=False,indent=2)+"\n")
    main=output/"inputs-r1";base=parent/"inputs-r1"
    c=read(main/"inputs.json");a,b=catalog(main/"en.tsv"),catalog(main/"zh-TW.tsv")
    added=[]
    name_field=next(f for f in c["Fields"] if f["Key"]=="field.dcd1d5223f73b3a965c0" and f["RawX"]==8068).copy()
    name_field["RawX"]=8004
    name_field["Color"]=0x8c;name_field["BackgroundOverride"]=23
    name_call=next(call for call in post["calls"] if call["stack"][2:4]==[8008,8004] and call["vararg_1_candidate"]["text"]=="Name")
    added.append(dict(binding=name_field,call_step=name_call["step"],formal_key="ui.dcd1d5223f73b3a965c0"))
    call=next(call for call in post["calls"] if call["format"]["text"]=="Return" and call["caller"]==dict(Seg=0xCEB,Off=0x1BE))
    signature=post["menus"][call["menu_index"]]["Signature"]
    key="field.6b0143d03864993fdf69";assert key not in a
    a[key],b[key]=formal_en["ui.6b0143d03864993fdf69"],formal_zh["ui.6b0143d03864993fdf69"]
    binding=dict(Pane="menu",Group="footer",Key=key,Start=0,Length=6,MenuSignature=signature,RawX=112,RawY=189,
                 Caller=call["caller"],FormatSHA256=sha(b"Return"),SHA256=sha(b"Return"),BackgroundOverride=23)
    added.append(dict(binding=binding,call_step=call["step"],formal_key="ui.6b0143d03864993fdf69"))
    c["Fields"] += [row["binding"] for row in added];c["Menus"][signature]="inn"
    provenance=read(main/"provenance.json")
    provenance["startup_extension"]=dict(base=str(base.relative_to(probe)),base_files={n:sha((base/n).read_bytes()) for n in ["inputs.json","en.tsv","zh-TW.tsv"]},
        observed_path=str((output/"observe-r1/receipt.json").relative_to(probe)),observed_sha256=sha((output/"observe-r1/receipt.json").read_bytes()),added=added)
    # 保留原本細驗條件，僅移除本批結束點以後的區間。
    c["fine_windows"]=[[lo,min(hi,700000000)] for lo,hi in c["fine_windows"] if lo<700000000]
    for name,rows in [("en.tsv",a),("zh-TW.tsv",b)]:
        (main/name).write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k,v in sorted(rows.items())))
    (main/"inputs.json").write_text(json.dumps(c,indent=2)+"\n")
    (main/"provenance.json").write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+"\n")
    from session_load import boundaries
    boundaries(probe,output)
    print(json.dumps(dict(cold_bindings=15,cold_windows=len(merged),main_added_fields=2,main_words=len(a))))


def glyphs(probe,output):
    for folder,parent in [("inputs-r1",probe/"session-load-20261023-r4/inputs-r1"),("ui-inputs",probe/"session-load-20261023-r4/ui-inputs")]:
        path=output/folder/"glyphs-16.json";old=read(parent/"glyphs-16.json");new=read(path)
        assert all(old[k]==new[k] for k in ["size","height","font_sha256"])
        for key,value in old["glyphs"].items():
            if key in new["glyphs"]:assert new["glyphs"][key]==value
        original=len(old["glyphs"]);old["glyphs"].update(new["glyphs"])
        path.write_text(json.dumps(old,ensure_ascii=False)+"\n")
        print(json.dumps(dict(folder=folder,preserved=original,glyphs=len(old["glyphs"]))))


def guards(output):
    target=output/"caption-guards";assert not target.exists();target.mkdir()
    for name in ["position","width","caller","group"]:
        folder=target/name;shutil.copytree(output/"ui-inputs",folder)
        config=read(folder/"bindings.json")
        binding=next(b for b in config["Bindings"] if b["Key"]=="startup.quiz-page")
        if name=="position":binding["X"]+=1
        elif name=="width":binding["Width"]+=8
        elif name=="caller":binding["UpperCaller"]["Off"]+=1
        else:binding["Group"]="source"
        (folder/"bindings.json").write_text(json.dumps(config,indent=2)+"\n")


def check_guards(output):
    results=[]
    for name in ["position","width","caller","group"]:
        log=output/"caption-guards"/(name+".log")
        assert "panic: 冷讀提示綁定不符" in log.read_text(),name
        assert not (output/"caption-guards"/(name+"-run")/"receipt.json").exists()
        results.append(dict(name=name,rejected=True,log_sha256=sha(log.read_bytes())))
    write(output/"caption-guards/results.json",dict(cases=results))
    print(json.dumps(results))


def correct_backgrounds(probe,source,output):
    assert source.parent==output.parent==probe and not output.exists()
    assert read(source/"failure.json")["accepted"] is False
    output.mkdir()
    names=["boot.json","native-cold","observe-r1","control-r1","original-check.json","gameplay-request.json",
           "native-fine-windows.json","ui-inputs","inputs-r1","observe-combined-boundaries-r2","boundary-reuse.json",
           "legacy-control-r1","legacy-observe-r1","legacy-original-check.json","legacy-reuse.json","native-reuse.json"]
    reused=[]
    for name in names:
        old=source/name;new=output/name
        if old.is_dir():shutil.copytree(old,new)
        else:shutil.copyfile(old,new)
        for p in old.rglob("*") if old.is_dir() else [old]:
            if p.is_file():
                q=output/p.relative_to(source);assert sha(p.read_bytes())==sha(q.read_bytes())
                reused.append(dict(source=str(p.relative_to(probe)),target=str(q.relative_to(output)),sha256=sha(p.read_bytes())))
    native_backgrounds(output)
    reused=[r for r in reused if r["target"] not in ("ui-inputs/bindings.json","inputs-r1/inputs.json","inputs-r1/provenance.json")]
    write(output/"r1-reuse.json",dict(files=reused,corrected=["ui-inputs/bindings.json","inputs-r1/inputs.json","inputs-r1/provenance.json"],
        original_failure=dict(path=str((source/"failure.json").relative_to(probe)),sha256=sha((source/"failure.json").read_bytes())),
        limits="只重用已核對原版及未改輸入；呈現以原版索引 23 重建，不重用 r1 GPU 驗收"))
    print(json.dumps(dict(reused=len(reused),native_background=23)))


def native_backgrounds(output):
    assert not list(output.glob("run-*.json")),"不能修改已固定的執行輸入"
    config=read(output/"ui-inputs/bindings.json")
    for binding in config["Bindings"]:
        if binding["Key"].startswith("startup."):binding["Background"]=23
    (output/"ui-inputs/bindings.json").write_text(json.dumps(config,indent=2)+"\n")
    c=read(output/"inputs-r1/inputs.json");origin=read(output/"inputs-r1/provenance.json")
    for binding in c["Fields"]+[row["binding"] for row in origin["startup_extension"]["added"]]:
        if binding["Key"]=="field.dcd1d5223f73b3a965c0" and binding["RawX"]==8004:
            binding["Color"]=0x8c;binding["BackgroundOverride"]=23
        if binding["Key"]=="field.6b0143d03864993fdf69":binding["BackgroundOverride"]=23
    (output/"inputs-r1/inputs.json").write_text(json.dumps(c,indent=2)+"\n")
    (output/"inputs-r1/provenance.json").write_text(json.dumps(origin,ensure_ascii=False,indent=2)+"\n")


def page_sync_inputs(probe,source,output):
    assert source.parent==output.parent==probe and not output.exists()
    assert read(source/"failure.json")["accepted"] is False
    output.mkdir()
    names=["boot.json","native-cold","observe-r1","control-r1","original-check.json","gameplay-request.json",
           "native-fine-windows.json","ui-inputs","inputs-r1","observe-combined-boundaries-r2","boundary-reuse.json",
           "legacy-control-r1","legacy-observe-r1","legacy-original-check.json","legacy-reuse.json","native-reuse.json","video-observe-r2"]
    reused=[]
    for name in names:
        old=source/name;new=output/name
        if old.is_dir():shutil.copytree(old,new)
        else:shutil.copyfile(old,new)
        for p in old.rglob("*") if old.is_dir() else [old]:
            if p.is_file():
                q=output/p.relative_to(source);assert sha(p.read_bytes())==sha(q.read_bytes())
                reused.append(dict(source=str(p.relative_to(probe)),target=str(q.relative_to(output)),sha256=sha(p.read_bytes())))
    video=read(output/"video-observe-r2/receipt.json")
    baseline=read(output/"native-cold/receipt.json")["checkpoints"]+read(output/"control-r1/receipt.json")["checkpoints"][:7]
    fields=("label","step","regs","ram_sha256","indexed_sha256","palette","keys_consumed","file_writes")
    assert len(baseline)==len(video["checkpoints"])==19
    assert all(all(a[k]==b[k] for k in fields) for a,b in zip(baseline,video["checkpoints"]))
    origin=read(output/"ui-inputs/provenance.json")
    origin["page_sync"]=dict(path=str(Path("/probe")/output.relative_to(probe)/"video-observe-r2/receipt.json"),sha256=sha((output/"video-observe-r2/receipt.json").read_bytes()),native_checkpoints_equal=19)
    (output/"ui-inputs/provenance.json").write_text(json.dumps(origin,ensure_ascii=False,indent=2)+"\n")
    config=read(output/"ui-inputs/bindings.json")
    intervals=config["FineWindows"]+[[e["step"]-2000,e["step"]+2000] for e in video["display_changes"] if 220000000<e["step"]<355000000]
    merged=[]
    for start,end in sorted(intervals):
        if merged and start<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],end)
        else:merged.append([start,end])
    config["FineWindows"]=merged
    (output/"ui-inputs/bindings.json").write_text(json.dumps(config,indent=2)+"\n")
    reused=[r for r in reused if r["target"] not in ("ui-inputs/provenance.json","ui-inputs/bindings.json")]
    write(output/"r2-reuse.json",dict(files=reused,changed=["ui-inputs/provenance.json","ui-inputs/bindings.json"],native_checkpoints_equal=19,
        original_failure=dict(path=str((source/"failure.json").relative_to(probe)),sha256=sha((source/"failure.json").read_bytes())),limits="不重用失敗的 GPU 驗收；本輪從 MZ 重跑頁面同步"))
    print(json.dumps(dict(reused=len(reused),cold_fine_windows=len(merged),native_checkpoints_equal=19)))


def review(output,run_name):
    assert Path(run_name).name==run_name
    folder=output/run_name;r=read(folder/"receipt.json")
    frames={f["step"]:f for f in r["cold_frames"]+r["frames"]}
    layouts={f["step"]:f for f in r["list_frames"]}
    images=[]
    for step in [240000000,326000000,355000000,356500000,400000000,420000000,640000000,660000000,700000000]:
        frame=frames[step];assert not frame["held"],step
        if step in (355000000,356500000):
            assert {w["Key"] for w in frame["cold_ui_words"]}=={"startup.quiz-page","startup.quiz-word","startup.quiz-heading","startup.quiz-enter"}
        if step==420000000:assert any(w["Key"]=="field.6b0143d03864993fdf69" for w in layouts[step]["words"])
        if step==660000000:
            words=layouts[step]["words"]
            assert sum(w.get("FontSize")==20 for w in words)==12
            assert any(w["Key"]=="field.dcd1d5223f73b3a965c0" and w["X"]==8 for w in words)
        images.append(dict(step=step,file=run_name+"/"+frame["File"],rgba_sha256=frame["SHA256"],cold_words=frame.get("cold_ui_words"),words=layouts.get(step,{}).get("words")))
    write(output/"review-images.json",dict(images=images))
    print(json.dumps([dict(step=i["step"],file=i["file"]) for i in images]))


def evidence(project,output):
    probe=project/"workplace/probe";parent=probe/"session-load-20261023-r4"
    runs=list(output.glob("run-r*.json"));assert len(runs)==1
    run=read(runs[0])
    assert run["program_sha256"]==sha((probe/"ui-list-live").read_bytes())
    for name,digest in run["source_files"].items():assert sha((project/name).read_bytes())==digest,name
    for group,path in [("inputs","inputs-r1"),("cold_inputs","ui-inputs")]:
        for name,digest in run[group].items():assert sha((output/path/name).read_bytes())==digest,name
    cold,game,legacy=[read(output/n) for n in ["cold-check.json","gameplay-check.json","legacy-check.json"]]
    assert cold["original_checkpoints_equal"]==12 and game["original_checkpoints_equal"]==21 and legacy["original_checkpoints_equal"]==16
    assert read(output/"original-check.json")["checkpoints_equal"]==21
    assert cold["checker_sha256"]==sha((project/"tools/cold_load.py").read_bytes())
    for report in [game,legacy]:
        assert report["checker_sha256"]==sha((project/"tools/ui_list_live_check.py").read_bytes())
        assert report["field_lifetime_model_equal"] and report["all_submitted_pixels_equal_expected"]
    assert len(cold["cold_prompt_visible_frames"])==15 and all(cold["cold_prompt_visible_frames"].values())
    assert cold["cold_page_sync_verified"]
    assert game["cold_caption_carry_frames"]>0
    model_sha=sha((project/"tools/load_prompt_check.py").read_bytes())
    assert cold["cold_prompt_model_sha256"]==game["cold_caption_model_sha256"]==model_sha
    guards=read(output/"caption-guards/results.json")
    assert len(guards["cases"])==4 and all(c["rejected"] for c in guards["cases"])
    assert len((output/"runtime-guards/results.tsv").read_text().splitlines())==5
    assert len(read(output/"review-images.json")["images"])==9
    for name in cold["runs"]:
        events=dict(line.split() for line in (output/(name+"-memory-events.txt")).read_text().splitlines())
        assert events["oom"]==events["oom_kill"]=="0"
    for name in ["glyphs-20.json","role.zh-TW.tsv","reader.zh-TW.tsv","illustrations.json"]:
        assert (parent/"inputs-r1"/name).read_bytes()==(output/"inputs-r1"/name).read_bytes()
    old,new=read(parent/"inputs-r1/glyphs-16.json"),read(output/"inputs-r1/glyphs-16.json")
    assert len(old["glyphs"])==1637 and len(new["glyphs"])==1640
    assert all(new["glyphs"][k]==v for k,v in old["glyphs"].items())
    snapshot=output/"tool-snapshots";assert not snapshot.exists();snapshot.mkdir()
    names=list(read(parent/"evidence.json")["tools"])+["startup_captions.py"]
    tools={}
    for name in names:
        source=project/"tools"/name;shutil.copyfile(source,snapshot/name);tools[name]=sha(source.read_bytes())
    for name in ["ui-list-live","ui-context-probe"]:shutil.copyfile(probe/name,snapshot/name)
    def fingerprint(path):
        h=hashlib.sha256()
        with path.open("rb") as stream:
            while block:=stream.read(1<<20):h.update(block)
        return dict(path=str(path.relative_to(project)),bytes=path.stat().st_size,sha256=h.hexdigest())
    sources=[parent/"evidence.json",probe/"load-prompts-20261023/observe-cold-r3/receipt.json",project/"workplace/input/dos/drkqueen/DQK.EXE"]
    sources += [project/"workplace/translation"/n for n in ["en.tsv","zh-TW.tsv","glossary.tsv","catalog.json","glossary-additions.tsv","startup-ui-review.tsv"]]
    if (output/"r1-reuse.json").exists():
        old=probe/"startup-captions-20261023"
        sources += [old/n for n in ["failure.json","run-r1.json","cold-check.json","gameplay-check.json","review-images.json"]]
    if (output/"r2-reuse.json").exists():
        old=probe/"startup-captions-20261023-r2"
        sources += [old/n for n in ["failure.json","run-r2.json","background-transition-diagnostic.json"]]
        sources += [p for p in sorted((old/"r2-programs").rglob("*")) if p.is_file()]
        first=probe/"startup-captions-20261023"
        sources += [first/n for n in ["failure.json","run-r1.json","cold-check.json","gameplay-check.json","review-images.json"]]
        sources += [p for p in sorted((first/"r1-programs").rglob("*")) if p.is_file()]
        comparison=read(output/"video-observe-r2/state-comparison.json")
        assert comparison["equal"]==19 and comparison["sha256"]==sha((output/"video-observe-r2/receipt.json").read_bytes())
    result=dict(draft=True,scope="開頭三鈕、兩處姓名、查驗四段與交接保留、旅店 Enter 及重讀角色欄名",
        docker_images=read(parent/"evidence.json")["docker_images"],
        accepted_runs=dict(cold_and_gameplay=["en-r3","zh-r3"],legacy=["legacy-en-fine-r3","legacy-zh-fine-r3"]),
        diagnostic_runs=dict(accepted=False,runs=["legacy-en-r3","legacy-zh-r3"],reason="誤用稀疏參數，沒有通過細驗間距檢查"),
        execution=run,tools=tools,sources=[fingerprint(p) for p in sources],
        artifacts=[fingerprint(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name!="evidence.json"],
        cold=cold,gameplay=game,legacy=legacy,guards=guards,source_commit="f79eab6db8c64a524a06535e53e5d32b0bbcf7c8",
        rights="原版、全文、存檔、字模及畫格只留本機 workplace，不加入 Git",
        limits="DRAFT；英文查驗標題、數字與答案判定不變；未驗全部查驗題、建角、戰鬥、說明面板、正式入口或全遊戲中文化")
    write(output/"evidence.json",result)
    print(json.dumps(dict(artifacts=len(result["artifacts"]),tools=len(tools),cold_frames=cold["gpu_frames_verified"],gameplay_frames=game["real_gpu_readback_frames"])))


if __name__=="__main__":
    if sys.argv[1]=="prepare":prepare(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="inputs":inputs(*map(Path,sys.argv[2:5]))
    elif sys.argv[1]=="glyphs":glyphs(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="guards":guards(Path(sys.argv[2]))
    elif sys.argv[1]=="check-guards":check_guards(Path(sys.argv[2]))
    elif sys.argv[1]=="correct-backgrounds":correct_backgrounds(*map(Path,sys.argv[2:5]))
    elif sys.argv[1]=="native-backgrounds":native_backgrounds(Path(sys.argv[2]))
    elif sys.argv[1]=="page-sync-inputs":page_sync_inputs(*map(Path,sys.argv[2:5]))
    elif sys.argv[1]=="review":review(Path(sys.argv[2]),sys.argv[3])
    elif sys.argv[1]=="evidence":evidence(*map(Path,sys.argv[2:4]))
    else:raise SystemExit("未知命令")
