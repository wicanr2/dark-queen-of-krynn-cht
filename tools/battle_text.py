"""正常離城至首次戰鬥的來源與繁中 DRAFT，限 Docker。"""
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def write(path,value):
    assert not path.exists(),path
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")


def catalog(path):
    with path.open() as f:
        rows=list(csv.DictReader(f,delimiter="\t",quoting=csv.QUOTE_NONE))
    result={r["key"]:r["text"] for r in rows}
    assert len(result)==len(rows)
    return result


def route(root,output):
    probe=root/"workplace/probe"
    state=probe/"pane-render-20261022/observe-palace-journal-r1/final.state"
    phases=[("leave-request.json","observe-leave-r1"),("journey-request-r1.json","observe-journey-r1"),
        ("forest-request-r1.json","observe-forest-r1"),("forest-request-r2.json","observe-forest-r2"),
        ("area-request-r1.json","observe-area-r1"),("forest-request-r3.json","observe-forest-r3"),
        ("forest-request-r4.json","observe-forest-r4"),("forest-request-r5.json","observe-forest-r5"),
        ("forest-request-r6.json","observe-forest-r6"),("forest-request-r7.json","observe-forest-r7"),
        ("gate-request-r1.json","observe-gate-r1"),("gate-request-r2.json","observe-gate-r2"),
        ("city-request-r1.json","observe-city-r1"),("encounter-request-r1.json","observe-encounter-r1"),
        ("city-request-r2.json","observe-city-r2"),("combat-request-r1.json","observe-combat-r1"),
        ("aim-request-r1.json","observe-aim-r1"),("quick-request-r1.json","observe-quick-r1")]
    request=dict(state_sha256=sha(state),start_steps=890000000,actions=[])
    previous=state;end=request["start_steps"];sources=[]
    binary=probe/"ui-context-probe"
    for i,(name,folder) in enumerate(phases,1):
        req=read(output/name);run=read(output/folder/"receipt.json")
        assert req["state_sha256"]==sha(previous) and req["start_steps"]==end
        assert run["probe_sha256"]==sha(binary) and not any(c["unimplemented"] for c in run["checkpoints"])
        for action in req["actions"]:
            request["actions"].append(dict(action,label=f"p{i:02}-"+action["label"]))
        end=req["actions"][-1]["end"];previous=output/folder/"final.state"
        sources.append(dict(request=name,request_sha256=sha(output/name),receipt=folder+"/receipt.json",
                            receipt_sha256=sha(output/folder/"receipt.json")))
    assert end==2690000000
    write(output/"route-request-r1.json",request)
    snapshots=output/"context-programs";snapshots.mkdir()
    files=[root/"tools"/name for name in ("ui_context_probe.go","ui_menu_source.go","oracle_video_observer.go","ui-context.sh")]+[binary]
    for p in files:shutil.copy2(p,snapshots/p.name)
    write(output/"route-source.json",dict(initial_state=str(state.relative_to(root)),state_sha256=sha(state),
        phases=sources,context_files={str(p.relative_to(root)):sha(p) for p in files},
        limits="逐段正常輸入完整合併，不刪撞牆或等待時的無效方向鍵；獨立 Inv 分支及未完成的長時間觀測不納入。合併重播另核對原版控制，未以快照串接冒充連續執行。"))
    print(json.dumps(dict(phases=len(phases),actions=len(request["actions"]),end=end)))


def native_check(output):
    a,b=[read(output/name/"receipt.json") for name in ("observe-route-r1","control-route-r1")]
    for key in ("source_commit","go_version","exe_sha256","state_sha256","request_sha256","probe_sha256","request","checkpoints"):
        assert a[key]==b[key],key
    assert not any(c["unimplemented"] or c["file_writes"] for c in a["checkpoints"])
    paragraphs=[p["source"]["text"] for p in a["paragraphs"] or []]
    assert any(s.endswith("AS JOURNAL ENTRY 65.") for s in paragraphs)
    assert "THEY ATTACK!" in paragraphs and "Hitting for 14 points of damage" in paragraphs
    battle=[m for m in a["menus"] if [bytes.fromhex(v["SourceHex"]).decode() for v in m["Buttons"]]==["Aim","Use","Cast","Guard","Quick","Delay","View","Speed","End"]]
    aiming=[m for m in a["menus"] if [bytes.fromhex(v["SourceHex"]).decode() for v in m["Buttons"]]==["Next","Prev","Manual","Center","Exit"]]
    assert {m["Count"] for m in battle}=={10,19} and aiming
    for cp in a["checkpoints"]:
        assert sha(output/"observe-route-r1"/(cp["label"]+".png"))==sha(output/"control-route-r1"/(cp["label"]+".png"))
    write(output/"native-check.json",dict(checkpoints_equal=len(a["checkpoints"]),battle_shapes=[m["Signature"] for m in battle],
        aiming_shapes=[m["Signature"] for m in aiming],source_sha256=sha(output/"observe-route-r1/receipt.json"),
        limits="正常宮殿告別快照後連續離城、探索、原版手札 65 引用、龍群遭遇、戰鬥、瞄準退出及首次攻擊；不是從 MZ 冷啟動或整場戰鬥結束驗收。"))
    print(json.dumps(dict(checkpoints_equal=len(a["checkpoints"]),battle_shapes=len(battle),aiming_shapes=len(aiming))))


def inputs(probe,texts,font,output):
    assert read(output/"native-check.json")["checkpoints_equal"]==82
    base=probe/"item-contexts-20261024/inputs-r1"
    target=output/"inputs-r1";assert not target.exists();shutil.copytree(base,target)
    config=read(target/"inputs.json");parent=read(target/"provenance.json")
    # 舊綁定以整份父輸入雜湊保留。新批只列自己的來源，不複製歷代 validator 分支。
    origin={k:v for k,v in parent.items() if not k.endswith("_extension")}
    en,zh=catalog(target/"en.tsv"),catalog(target/"zh-TW.tsv")
    formal_en,formal_zh=catalog(texts/"en.tsv"),catalog(texts/"zh-TW.tsv")
    glossary=list(csv.DictReader((texts/"glossary.tsv").open(),delimiter="\t"))
    review=list(csv.DictReader((texts/"battle-ui-review.tsv").open(),delimiter="\t"))
    trace_path=output/"observe-route-r1/receipt.json";trace=read(trace_path)
    added=[];paragraphs=[];menus=[];origins={}
    def key(source):
        reviewed=next((r for r in review if r["en"]==source),None)
        if reviewed:
            k=reviewed["key"];en[k],zh[k]=source,reviewed["text"];origins[k]=dict(review=reviewed);return k
        old=sorted(k for k,v in en.items() if v==source and k in zh)
        if old:
            assert len({zh[k] for k in old})==1,(source,old)
            return old[0]
        formal=sorted(k for k,v in formal_en.items() if v==source and k in formal_zh)
        if formal:
            assert len({formal_zh[k] for k in formal})==1
            k=formal[0];en[k],zh[k]=source,formal_zh[k];origins[k]=dict(formal_key=k);return k
        term=[r for r in glossary if r["category"]=="ui" and r["en"].casefold()==source.casefold()]
        assert len(term)==1,(source,term)
        k="battle.ui."+digest(source)[:20]
        en[k],zh[k]=source,term[0]["zh"];origins[k]=dict(glossary=term[0]);return k
    for menu in trace["menus"]:
        words=[bytes.fromhex(b["SourceHex"]).decode() for b in menu["Buttons"]]
        if words==["Aim","Use","Cast","Guard","Quick","Delay","View","Speed","End"]:kind="combat"
        elif words==["Next","Prev","Manual","Center","Exit"]:kind="aiming"
        else:continue
        if menu["Signature"] in config["Menus"]:continue
        config["Menus"][menu["Signature"]]=kind;menus.append(menu)
        native=lambda v:v if v<400 else (v-8000)*2
        for b in menu["Buttons"]:
            source=bytes.fromhex(b["SourceHex"]).decode();k=key(source)
            assert len(zh[k])<=len(source),(source,zh[k])
            binding=dict(Pane="menu",Group="footer",Key=k,Start=0,Length=len(source),Caller=dict(Seg=0xCEB,Off=0x1BE),
                RawX=native(b["RawX"]),RawY=native(b["RawY"])+1,MenuSignature=menu["Signature"],
                FormatSHA256=digest(source),SHA256=digest(source),UpperCaller=dict(Seg=0,Off=0),UpperFormatSHA256="")
            config["Fields"].append(binding)
            added.append(dict(binding=binding,kind="menu",menu_signature=menu["Signature"],button_index=b["Index"]))
    for c in trace["calls"]:
        if c["format"]["text"]!="%s" or c["wrapper_index"]<0:continue
        source=c["vararg_1_candidate"]["text"]
        if source not in ("Hitpoints","AC","A battle begins...") and not source.startswith("Aim: range = "):continue
        prefix="Aim: range = " if source.startswith("Aim: range = ") else source
        k=key(prefix);w=trace["wrappers"][c["wrapper_index"]]
        binding=dict(Pane="callsite",Group="body" if prefix in ("Hitpoints","AC") else "footer",Key=k,
            Start=0,Length=len(prefix),Caller=c["caller"],UpperCaller=w["caller"],RawX=c["stack"][3],RawY=c["stack"][2],
            FormatSHA256=digest("%s"),SHA256=digest(source))
        if binding in config["Fields"]:continue
        config["Fields"].append(binding)
        added.append(dict(binding=binding,kind="callsite",call_step=c["step"],first_glyph=c["first_glyph"],return_step=c["return_step"]))
    for p in trace["paragraphs"] or []:
        if p["native_box"]!=[8,136,312,184] or p["caller"]["Seg"]!=0x26B4:continue
        source=p["source"]["text"];k=key(source)
        assert k.startswith("ecl.") and k=="ecl."+digest(source)[:20]
        binding=dict(Key=k,SHA256=digest(source),Caller=p["caller"],NativeBox=p["native_box"],
            Foreground=p["foreground"],Background=p["background"],Clear=p["clear"])
        if source.endswith("AS JOURNAL ENTRY 65."):binding["JournalEntry"]=65
        if binding in config["Paragraphs"]:continue
        config["Paragraphs"].append(binding)
        paragraphs.append(dict(binding=binding,step=p["step"],first_glyph=p["first_glyph"],return_step=p["return_step"]))
    config["fine_windows"]=windows(trace,890000000,2690000000)
    relative=Path(output.name)/"observe-route-r1/receipt.json"
    assert sha(probe/relative)==sha(trace_path)
    origin["battle_extension"]=dict(base=str(base.relative_to(probe)),base_files={p.name:sha(p) for p in base.iterdir() if p.is_file()},
        source_path=str(relative),source_sha256=sha(trace_path),fields=added,paragraphs=paragraphs,menus=menus,origins=origins,
        review_sha256=sha(texts/"battle-ui-review.tsv"),formal_files={n:sha(texts/n) for n in ["en.tsv","zh-TW.tsv","glossary.tsv","catalog.json","glossary-additions.tsv"]},
        page_validation=dict(source_path=str(relative),sha256=sha(trace_path)))
    for name,value in [("inputs.json",config),("provenance.json",origin)]:
        (target/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
    def save(name,values):
        (target/name).write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k,v in sorted(values.items())))
    save("en.tsv",en);save("zh-TW.tsv",zh)
    font_text=catalog(base/"font-zh-TW.tsv")
    for k in origins:font_text[k]=zh[k]
    save("font-zh-TW.tsv",font_text)
    glyph_path=target/"glyphs-added.json"
    subprocess.run([sys.executable,str(Path(__file__).with_name("menu_glyphs.py")),str(font),str(target/"font-zh-TW.tsv"),str(glyph_path),"16"],check=True)
    old,new=read(base/"glyphs-16.json"),read(glyph_path)
    assert all(old[k]==new[k] for k in ["size","height","font_sha256"])
    for k,v in old["glyphs"].items():
        if k in new["glyphs"]:assert new["glyphs"][k]==v
    old["glyphs"].update(new["glyphs"])
    (target/"glyphs-16.json").write_text(json.dumps(old,ensure_ascii=False)+"\n")
    glyph_path.unlink()
    print(json.dumps(dict(fields=len(added),paragraphs=len(paragraphs),menus=len(menus),en=len(en),zh=len(zh),glyphs=len(old["glyphs"]))))


def windows(trace,start,end):
    intervals=[]
    for group,returned in (("calls","return_step"),("wrappers","return_step"),("paragraphs","return_step"),
                           ("fill_events","return_instruction_step"),("list_events","return_instruction_step")):
        intervals += [[max(start,v["step"]-2000),min(end,v[returned]+2000)] for v in trace[group] or []]
    intervals += [[max(start,v["step"]-2000),min(end,v["step"]+2000)] for v in trace.get("display_changes",[]) if v["step"]>start]
    merged=[]
    for lo,hi in sorted(intervals):
        if merged and lo<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],hi)
        else:merged.append([lo,hi])
    return merged


def freeze(root,output,revision="r1",input_revision=None):
    assert re.fullmatch(r"r[1-9][0-9]*",revision)
    input_revision=input_revision or revision
    assert re.fullmatch(r"r[1-9][0-9]*",input_revision)
    probe=root/"workplace/probe"
    programs=output/("programs-"+revision);programs.mkdir()
    names=["early_text_live.go","ui_cold_prompts.go","ui_list_live.go","ui_list_paragraphs.go",
        "ui_journal_reader.go","ui_journal_illustrations.go","ui_menu_source.go","oracle_video_observer.go","ui_hud_integer.go","ui_inventory_ammo.go","ui-list-live.sh"]
    for name in names:shutil.copy2(root/"tools"/name,programs/name)
    shutil.copy2(probe/"ui-list-live",programs/"ui-list-live")
    profiles={"inputs-"+input_revision}|{p.name for p in output.glob("inputs-*-"+input_revision) if p.is_dir()}
    if (output/"inputs-journey-r3").exists():profiles.update(("inputs-journey-r3","inputs-arrival-r3"))
    write(output/("run-"+revision+".json"),dict(program_sha256=sha(programs/"ui-list-live"),
        source_files={"tools/"+n:sha(root/"tools"/n) for n in names},
        inputs={name:{p.name:sha(p) for p in (output/name).iterdir() if p.is_file()} for name in sorted(profiles)},
        request_sha256=sha(output/"route-request-r1.json")))
    print(json.dumps(dict(revision=revision,profiles=sorted(profiles),program_sha256=sha(programs/"ui-list-live"))))


def guards(output,revision="r1"):
    assert re.fullmatch(r"r[1-9][0-9]*",revision)
    reports=[]
    for case,reason in [("menu","battle menu shape untranslated"),("range","battle lexical mask mismatch"),
                        ("journal","battle journal source number mismatch"),
                        ("button","battle menu buttons incomplete"),
                        ("upper-coordinate","battle upper coordinate contract mismatch")]:
        target=output/("negative-"+case+"-"+revision);shutil.copytree(output/"inputs-battle-r2",target)
        config=read(target/"inputs.json");origin=read(target/"provenance.json");b=origin["battle_extension"]
        if case=="menu":
            m=next(m for m in b["menus"] if m["Count"]==19)
            removed=[f for f in b["fields"] if f["binding"].get("MenuSignature")==m["Signature"]]
            assert len(removed)==9
            b["fields"]=[f for f in b["fields"] if f not in removed]
            config["Fields"]=[f for f in config["Fields"] if f not in [r["binding"] for r in removed]]
            b["menus"]=[v for v in b["menus"] if v!=m];del config["Menus"][m["Signature"]]
        elif case=="button":
            row=next(r for r in b["fields"] if r["kind"]=="menu")
            config["Fields"].remove(row["binding"]);b["fields"].remove(row)
        elif case=="range":
            en=catalog(target/"en.tsv")
            f=next(r["binding"] for r in b["fields"] if en[r["binding"]["Key"]]=="Aim: range = ")
            actual=next(v for v in config["Fields"] if v==f)
            f["Length"]+=1;actual["Length"]+=1
        elif case=="journal":
            f=next(r["binding"] for r in b["paragraphs"] if r["binding"].get("JournalEntry")==65)
            actual=next(v for v in config["Paragraphs"] if v==f)
            f["JournalEntry"]=actual["JournalEntry"]=64
        else:
            en=catalog(target/"en.tsv")
            f=next(r["binding"] for r in b["fields"] if en[r["binding"]["Key"]]=="Aim: range = ")
            actual=next(v for v in config["Fields"] if v==f)
            f["UpperNative"][1]+=8;actual["UpperNative"][1]+=8
        for name,value in [("inputs.json",config),("provenance.json",origin)]:
            (target/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
        result=output/("unexpected-"+case+"-"+revision+".json")
        cmd=[sys.executable,str(Path(__file__).with_name("ui_list_live_check.py")),str(output/"battle-en-r4"),str(output/"battle-zh-r4"),
            str(target),str(output/"control-battle-r2"),str(output/"observe-battle-r2"),str(result)]
        p=subprocess.run(cmd,capture_output=True,text=True)
        assert p.returncode!=0 and not result.exists() and reason in p.stderr,p.stderr
        reports.append(dict(case=case,reason=reason,returncode=p.returncode,stderr=p.stderr))
    write(output/("guards-"+revision+".json"),dict(cases=reports,checker_sha256=sha(Path(__file__).with_name("ui_list_live_check.py"))))
    print("漏完整表、漏單一按鈕、覆蓋射程、錯手札編號及上層座標五項防護通過")


def rebuild(probe,texts,font,output,revision="r1"):
    assert re.fullmatch(r"r[1-9][0-9]*",revision)
    import tempfile
    with tempfile.TemporaryDirectory() as temporary:
        fresh=Path(temporary)/output.name;fresh.mkdir()
        for name in ["native-check.json","observe-route-r1/receipt.json"]:
            p=fresh/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(output/name,p)
        inputs(probe,texts,font,fresh)
        geometry_inputs(fresh)
        legacy_inputs(fresh)
        for name in ("journey","arrival","battle"):
            for item in (name+"-native-check-r2.json","observe-"+name+"-r2/receipt.json"):
                p=fresh/item;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(output/item,p)
            segment_inputs(probe,fresh,name)
        files=[]
        for folder in ("inputs-r1","inputs-r2","inputs-journey-r2","inputs-arrival-r2","inputs-battle-r2","inputs-legacy54-r2"):
            accepted=folder.replace("-r2","-r3") if folder in ("inputs-journey-r2","inputs-arrival-r2") else folder
            assert {p.name for p in (fresh/folder).iterdir()}=={p.name for p in (output/accepted).iterdir()}
            for p in sorted((fresh/folder).iterdir()):
                assert p.read_bytes()==(output/accepted/p.name).read_bytes(),p
                files.append(dict(path=accepted+"/"+p.name,sha256=sha(p)))
        write(output/("rebuild-check-"+revision+".json"),dict(files=files,generator_sha256=sha(Path(__file__))))
        print(json.dumps(dict(rebuilt_files_equal=len(files))))


def corpus(texts,output):
    en,zh=catalog(texts/"en.tsv"),catalog(texts/"zh-TW.tsv")
    eligible=[];excluded=[]
    for key,source in en.items():
        if not key.startswith("ecl.") or key not in zh:continue
        text=zh[key]
        reason=""
        if any(ord(c)<32 for c in source+text) or "\\" in source+text:reason="controls"
        elif re.search(r"%[-+ 0-9.]*[diuoxXfFeEgGcs]",source):reason="format"
        elif len(text)>144:reason="length"
        (excluded if reason else eligible).append(dict(key=key,zh_length=len(text),reason=reason))
    write(output/"literal-corpus-audit.json",dict(formal_files={n:sha(texts/n) for n in ["en.tsv","zh-TW.tsv","catalog.json"]},
        conservative_single_text_chars=144,eligible=eligible,excluded=excluded,
        required_glyphs=len(set("".join(zh[r["key"]] for r in eligible))),
        limits="正式 ECL 譯文的候選盤點；144 字是 38 格、20px 行距與禁則的保守單段界限，未核對原版顯示路徑、接續合併、全量字模或全遊戲。未寫入任何呈現輸入，不算已接入。"))
    print(json.dumps(dict(eligible=len(eligible),excluded=len(excluded),required_glyphs=len(set("".join(zh[r["key"]] for r in eligible))))))


def geometry_inputs(output):
    target=output/"inputs-r2";shutil.copytree(output/"inputs-r1",target)
    config=read(target/"inputs.json");origin=read(target/"provenance.json")
    trace=read(output/"observe-route-r1/receipt.json")
    en=catalog(target/"en.tsv");calls={c["step"]:c for c in trace["calls"]}
    count=0
    for row in origin["battle_extension"]["fields"]:
        f=row["binding"]
        if row["kind"]!="callsite" or en[f["Key"]] not in ("A battle begins...","Aim: range = "):continue
        actual=next(v for v in config["Fields"] if v==f)
        c=calls[row["call_step"]];w=trace["wrappers"][c["wrapper_index"]]
        xy=[(w["stack"][i]&255)*8 for i in (2,3)]
        for binding in (actual,f):binding.update(UpperNative=list(xy),Color=c["stack"][4])
        count+=1
    assert count==2
    for name,value in [("inputs.json",config),("provenance.json",origin)]:
        (target/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
    print("兩組上下層座標來源已補入 inputs-r2")


def segments(probe,output):
    full=read(output/"route-request-r1.json")
    for name,start,end,state in [("journey",890000000,1850000000,"pane-render-20261022/observe-palace-journal-r1/final.state"),
        ("arrival",1850000000,2550000000,"battle-text-20261024/observe-forest-r6/final.state"),
        ("battle",2550000000,2690000000,"battle-text-20261024/observe-city-r2/final.state")]:
        actions=[a for a in full["actions"] if start<a["at"]<a["end"]<=end]
        assert actions and actions[-1]["end"]==end
        write(output/(name+"-slice-request-r2.json"),dict(state_sha256=sha(probe/state),start_steps=start,actions=actions))
    print("已分成旅途、入城及首戰三段正常來源")


def segment_check(output,name):
    a,b=[read(output/(m+"-"+name+"-r2")/"receipt.json") for m in ("observe","control")]
    for key in ("source_commit","go_version","exe_sha256","state_sha256","request_sha256","probe_sha256","request","checkpoints"):
        assert a[key]==b[key],key
    full=read(output/"observe-route-r1/receipt.json");by_label={c["label"]:c for c in full["checkpoints"]}
    start=a["request"]["start_steps"]
    offset=next((c["keys_consumed"] for c in full["checkpoints"] if c["step"]==start),0)
    for cp in a["checkpoints"]:
        original=by_label[cp["label"]]
        for key in ("step","regs","ram_sha256","indexed_sha256","palette","file_writes","unimplemented"):
            assert cp[key]==original[key],(name,cp["label"],key)
        assert cp["keys_consumed"]+offset==original["keys_consumed"]
    write(output/(name+"-native-check-r2.json"),dict(checkpoints_equal=len(a["checkpoints"]),continuous_checkpoints_equal=len(a["checkpoints"]),
        key_counter_offset=offset,source_sha256=sha(output/("observe-"+name+"-r2")/"receipt.json"),
        limits="分段從既有正常狀態接續，與各自控制及連續原版相同；按鍵計數器依快照載入後重新計數，不變更 guest 或比較遮罩。"))
    print(json.dumps(dict(segment=name,checkpoints_equal=len(a["checkpoints"]))))


def segment_inputs(probe,output,name):
    assert read(output/(name+"-native-check-r2.json"))["checkpoints_equal"]>0
    target=output/("inputs-"+name+"-r2");shutil.copytree(output/"inputs-r2",target)
    path=output/("observe-"+name+"-r2")/"receipt.json";trace=read(path)
    config=read(target/"inputs.json");origin=read(target/"provenance.json")
    config["fine_windows"]=windows(trace,trace["request"]["start_steps"],trace["request"]["actions"][-1]["end"])
    origin["battle_extension"]["page_validation"]=dict(source_path=str(Path(output.name)/path.relative_to(output)),sha256=sha(path))
    for filename,value in [("inputs.json",config),("provenance.json",origin)]:
        (target/filename).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
    print("已建立 "+name+" 的來源與細驗區間")


def repair_segment_provenance(output):
    """保留實測輸入，另存掛載別名造成的來源路徑勘誤。"""
    seal=read(output/"segment-input-seal-r2.json");reports=[]
    for name in ("journey","arrival"):
        source=output/("inputs-"+name+"-r2");target=output/("inputs-"+name+"-r3")
        assert {p.name:sha(p) for p in source.iterdir()}==seal[source.name]
        shutil.copytree(source,target)
        origin=read(target/"provenance.json");page=origin["battle_extension"]["page_validation"]
        assert page["source_path"]=="out/observe-"+name+"-r2/receipt.json"
        page["source_path"]=output.name+"/observe-"+name+"-r2/receipt.json"
        assert page["sha256"]==sha(output/("observe-"+name+"-r2/receipt.json"))
        (target/"provenance.json").write_text(json.dumps(origin,ensure_ascii=False,indent=2)+"\n")
        same=[p.name for p in source.iterdir() if p.name!="provenance.json"]
        assert all((target/n).read_bytes()==(source/n).read_bytes() for n in same)
        reports.append(dict(executed=source.name,validated=target.name,unchanged_files=same,
                            executed_provenance_sha256=sha(source/"provenance.json"),
                            corrected_provenance_sha256=sha(target/"provenance.json"),page_validation=page))
    write(output/"segment-provenance-correction.json",dict(profiles=reports,
        limits="/out 掛載別名誤寫為相對來源根。保留實測 r2，r3 只修 provenance 的原版收據路徑，十四份執行輸入逐位元組相同，未改原版或呈現程序。"))
    print("兩份分段來源路徑勘誤完成，執行輸入未變")


def legacy_inputs(output):
    target=output/"inputs-legacy54-r2";shutil.copytree(output/"inputs-r2",target)
    config=read(target/"inputs.json");origin=read(target/"provenance.json")
    config["fine_windows"]=[]
    origin["battle_extension"].pop("page_validation",None)
    for name,value in [("inputs.json",config),("provenance.json",origin)]:
        (target/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
    print("舊格式手札 54 的稀疏回歸輸入已建立，不作細驗無閃爍結論")


def review(output):
    from PIL import Image,ImageDraw
    from io import BytesIO
    run_cache={}
    def cached(segment,lang):
        key=(segment,lang)
        if key not in run_cache:run_cache[key]=read(output/(segment+"-"+lang+"-r4")/"receipt.json")
        return run_cache[key]
    points=[("journey","p01-leave-pal-national"),("journey","p02-journey-continued"),
        ("arrival","p10-toward-gate-3"),("arrival","p11-city-gate"),("arrival","p12-inside-city"),
        ("arrival","p15-south-ruins-3"),("arrival","p15-east-ruins-turn"),
        ("battle","p16-combat-first-turn"),("battle","p17-aim-mode"),("battle","p18-quick-first-character")]
    reports=[]
    for number,(segment,label) in enumerate(points,1):
        images=[];frames=[]
        for lang in ("en","zh"):
            folder=output/(segment+"-"+lang+"-r4");run=cached(segment,lang)
            cp=next(c for c in run["checkpoints"] if c["label"]==label)
            index=next(i for i,f in enumerate(run["frames"]) if f["step"]==cp["step"])
            frame=run["frames"][index];assert not frame["held"]
            path=folder/frame["File"];images.append(Image.open(path).convert("RGB"))
            frames.append(dict(language=lang,path=str(path.relative_to(output)),sha256=sha(path),step=frame["step"],
                               words=run["list_frames"][index]["words"],reader=run["list_frames"][index]["reader"]))
        panel=Image.new("RGB",(1280,420),"#202020");draw=ImageDraw.Draw(panel)
        draw.text((8,4),label+" / original",fill="white");draw.text((648,4),label+" / zh-TW",fill="white")
        panel.paste(images[0],(0,20));panel.paste(images[1],(640,20))
        path=output/(f"review-{number:02}.png");buffer=BytesIO();panel.save(buffer,format="PNG")
        if path.exists():assert path.read_bytes()==buffer.getvalue()
        else:path.write_bytes(buffer.getvalue())
        reports.append(dict(label=label,frames=frames,panel=path.name,panel_sha256=sha(path)))
    proof=read(output/"inputs-r2/provenance.json")["battle_extension"];visibility=[]
    runs=[cached(n,"zh") for n in ("journey","arrival","battle")]
    for row in proof["fields"]:
        binding=row["binding"];events=[];visible=[]
        for run in runs:
            matches=[e for e in run["list_events"] if e["Kind"]=="field-before-glyph" and
                e["detail"]["key"]==binding["Key"] and e["detail"]["caller"]==binding["Caller"] and
                e["detail"]["raw_xy"]==[binding["RawX"],binding["RawY"]] and
                (row["kind"]!="menu" or e["detail"]["menu_signature"]==binding["MenuSignature"])]
            events.extend(e["Step"] for e in matches)
            for event in matches:
                later=[e["Step"] for e in run["list_events"] if e["Kind"]=="field-before-glyph" and e["Step"]>event["Step"] and e["detail"]["key"]==binding["Key"]]
                end=min(later,default=run["steps"]+1)
                visible.extend(f["step"] for f,d in zip(run["frames"],run["list_frames"]) if
                    event["Step"]<=f["step"]<end and not f["held"] and event["detail"]["word"] in (d["words"] or []))
        visibility.append(dict(binding=binding,events=events,visible_frame_count=len(set(visible))))
    source_only=[r for r in visibility if not r["events"]]
    menu_sizes={m["Signature"]:m["Count"] for m in proof["menus"]}
    assert len(visibility)==27 and len(source_only)==7
    for row in source_only:
        f=row["binding"];assert f["Pane"]=="menu" and menu_sizes[f["MenuSignature"]]==19
        peers=[r for r in visibility if r["events"] and all(r["binding"][k]==f[k] for k in ("Key","RawX","RawY","Length","Caller"))]
        assert peers
        row["shared_geometry_with"]=[r["binding"]["MenuSignature"] for r in peers]
    hidden=[r for r in visibility if r["events"] and not r["visible_frame_count"]]
    en=catalog(output/"inputs-r2/en.tsv")
    assert len(hidden)==3 and {en[r["binding"]["Key"]] for r in hidden}=={"A battle begins...","Aim","Quick"}
    assert all(r["binding"]["Pane"]=="callsite" or menu_sizes[r["binding"]["MenuSignature"]]==19 for r in hidden)
    paragraphs=[]
    for row in proof["paragraphs"]:
        key=row["binding"]["Key"]
        visible=sum(1 for run in runs for f,d in zip(run["frames"],run["list_frames"]) if
                    not f["held"] and d["paragraph"] and key in d["paragraph"]["Components"])
        assert visible,key
        paragraphs.append(dict(key=key,visible_frames=visible))
    assert any(e["action"]=="open" and e["page"]["Entry"]==65 for run in runs for e in run["reader_events"] or [])
    write(output/"review-images.json",dict(points=reports,field_visibility=visibility,paragraph_visibility=paragraphs,
        limits="二十七個綁定中，二十個實際觸發，十七個有可見畫格。戰鬥開始提示及 19 筆表的 Aim／Quick 反白只觸發而未顯示；該表其餘七鈕只有完整表來源，位置與實際印字的 10 筆記錄表相同，不當作七次新印字。正常戰鬥九鈕及瞄準五鈕均有可見文字。右側武器、攻擊及傷害保留原文。"))
    print(json.dumps(dict(review_points=len(reports),visible_bindings=sum(bool(r["visible_frame_count"]) for r in visibility),triggered_bindings=len(visibility)-len(source_only),source_bindings=len(visibility))))


def evidence(root,output):
    parent=root/"workplace/probe/item-contexts-20261024/evidence.json";previous=read(parent)
    fixed=read(output/"run-r4.json")
    for name,h in fixed["source_files"].items():assert sha(root/name)==sha(output/"programs-r4"/Path(name).name)==h
    assert fixed["program_sha256"]==sha(output/"programs-r4/ui-list-live")==sha(root/"workplace/probe/ui-list-live")
    profiles=dict(fixed["inputs"]);profiles.update(read(output/"segment-input-seal-r2.json"))
    for name,files in profiles.items():
        assert {p.name:sha(p) for p in (output/name).iterdir() if p.is_file()}==files
    for row in read(output/"segment-provenance-correction.json")["profiles"]:
        a,b=[output/row[k] for k in ("executed","validated")]
        assert sha(a/"provenance.json")==row["executed_provenance_sha256"]
        assert sha(b/"provenance.json")==row["corrected_provenance_sha256"]
        assert all((a/n).read_bytes()==(b/n).read_bytes() for n in row["unchanged_files"])
    reports=[read(output/(n+"-gpu-check-accepted"+("-r2" if n=="arrival" else "")+".json")) for n in ("journey","arrival","battle","legacy54")]
    assert all(r["checker_sha256"]==sha(root/"tools/ui_list_live_check.py") and r["all_submitted_pixels_equal_expected"] for r in reports)
    assert all(r["reader_model_sha256"]==sha(root/"tools/ui_journal_reader_check.py") for r in reports)
    assert sum(r["original_checkpoints_equal"] for r in reports)==90
    assert read(output/"native-check.json")["checkpoints_equal"]==82
    assert sum(read(output/(n+"-native-check-r2.json"))["continuous_checkpoints_equal"] for n in ("journey","arrival","battle"))==82
    rebuilt=read(output/"rebuild-check-r8.json")
    assert rebuilt["generator_sha256"]==sha(Path(__file__)) and len(rebuilt["files"])==90
    for row in rebuilt["files"]:assert sha(output/row["path"])==row["sha256"]
    guards=read(output/"guards-r6.json")
    assert len(guards["cases"])==5 and guards["checker_sha256"]==sha(root/"tools/ui_list_live_check.py")
    runtime_guards=[]
    for name,reason in [("journal","手札編號與完整原文不符"),("upper-coordinate","未驗證的提示欄位幾何或顏色")]:
        prefix="runtime-negative-"+name+"-r5"
        log=output/(prefix+".log");code=output/(prefix+".exit")
        assert code.read_text().strip()=="2" and "panic: "+reason in log.read_text()
        assert not (output/prefix/"receipt.json").exists()
        runtime_guards.append(dict(case=name,exit_code=2,log_sha256=sha(log),reason=reason))
    reviewed=read(output/"review-images.json");assert len(reviewed["points"])==10
    names=list(previous["tools"])+["battle_text.py"]
    snapshots=output/"tool-snapshots";snapshots.mkdir()
    for name in names:shutil.copy2(root/"tools"/name,snapshots/name)
    def item(p):return dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p))
    sources=[item(parent)]
    for old in previous["sources"]:
        if old["path"].startswith("workplace/translation/"):
            p=root/old["path"];assert sha(p)==old["sha256"];sources.append(item(p))
    sources.extend(item(root/n) for n in ("workplace/input/dos/drkqueen/DQK.EXE","workplace/translation/battle-ui-review.tsv"))
    target=output/"evidence.json"
    artifacts=[item(p) for p in sorted(output.rglob("*")) if p.is_file() and p!=target]
    write(target,dict(draft=True,sources=sources,artifacts=artifacts,tools={n:sha(root/"tools"/n) for n in names},
        docker_images=previous["docker_images"],reports=reports,guards=guards,runtime_guards=runtime_guards,
        accepted_program="programs-r4/ui-list-live",accepted_inputs=["inputs-journey-r3","inputs-arrival-r3","inputs-battle-r2","inputs-legacy54-r2"],
        failed_runs=["en-r1","zh-r1","journey-en-r2","journey-zh-r2","observe-quick-r2","control-quick-r2"],
        interrupted_runs=dict(reason="r3 的舊手札回歸證實 Return 選單提示被過度撤除，停止四份長測後修正，未將它們列為成功。",runs=[n+"-"+lang+"-r3" for n in ("journey","arrival") for lang in ("en","zh")]),
        limits="三段普通狀態起點的繁中 GUI 與連續原版八十二個狀態相同，另稀疏回歸手札 54；未把分段 GUI 當作從 MZ 連續執行。戰鬥開始提示未成為可見中文畫格，右側武器、攻擊及傷害仍原文。不是整場戰鬥、正式入口或全遊戲中文化完成。"))
    print(json.dumps(dict(artifacts=len(artifacts),tools=len(names),sources=len(sources),gpu_frames=sum(r["real_gpu_readback_frames"] for r in reports))))


def audit(root,output):
    record=read(output/"evidence.json")
    for row in record["sources"]+record["artifacts"]:
        p=root/row["path"];assert p.is_file() and p.stat().st_size==row["bytes"] and sha(p)==row["sha256"],p
        assert p.stat().st_uid==1000 and p.stat().st_gid==1000,p
    for name,h in record["tools"].items():assert sha(root/"tools"/name)==sha(output/"tool-snapshots"/name)==h
    assert {str(p.relative_to(root)) for p in output.rglob("*") if p.is_file() and p.name!="evidence.json"}=={r["path"] for r in record["artifacts"]}
    print(json.dumps(dict(verified_artifacts=len(record["artifacts"]),verified_sources=len(record["sources"]),verified_tools=len(record["tools"]))))


if __name__=="__main__":
    if sys.argv[1]=="route":route(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="native-check":native_check(Path(sys.argv[2]))
    elif sys.argv[1]=="inputs":inputs(*map(Path,sys.argv[2:6]))
    elif sys.argv[1]=="freeze":freeze(Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4] if len(sys.argv)>4 else "r1",sys.argv[5] if len(sys.argv)>5 else None)
    elif sys.argv[1]=="guards":guards(Path(sys.argv[2]),sys.argv[3] if len(sys.argv)>3 else "r1")
    elif sys.argv[1]=="rebuild":rebuild(*map(Path,sys.argv[2:6]),sys.argv[6] if len(sys.argv)>6 else "r1")
    elif sys.argv[1]=="corpus":corpus(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="geometry-inputs":geometry_inputs(Path(sys.argv[2]))
    elif sys.argv[1]=="segments":segments(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="segment-check":segment_check(Path(sys.argv[2]),sys.argv[3])
    elif sys.argv[1]=="segment-inputs":segment_inputs(Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4])
    elif sys.argv[1]=="repair-segment-provenance":repair_segment_provenance(Path(sys.argv[2]))
    elif sys.argv[1]=="legacy-inputs":legacy_inputs(Path(sys.argv[2]))
    elif sys.argv[1]=="review":review(Path(sys.argv[2]))
    elif sys.argv[1]=="evidence":evidence(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="audit":audit(*map(Path,sys.argv[2:4]))
    else:raise SystemExit("未知子命令")
