"""已觀測裝備名稱及正常裝卸的 DRAFT 輸入，限 Docker。"""
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


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def catalog(path):
    rows=[line.split("\t",1) for line in path.read_text().splitlines()]
    assert rows.pop(0)==["key","text"] and all(len(r)==2 and all(r) for r in rows)
    result=dict(rows)
    assert len(result)==len(rows)
    return result


def equipment_calls(trace, start, end):
    return [c for c in trace["calls"] if start<c["step"]<end and c["wrapper_index"]>=0
            and trace["wrappers"][c["wrapper_index"]]["caller"]==dict(Seg=0x88e,Off=0x71d)]


def row_match(text):
    match=re.fullmatch(r" (Yes|No)\t( ?(?:[0-9]+ )?)(.+?)( \+[0-9]+)? ",text)
    assert match,repr(text)
    return match


def native_check(output):
    a,b=[read(output/n/"receipt.json") for n in ("observe-r3","control-r3")]
    for key in ("source_commit","go_version","exe_sha256","state_sha256","request_sha256","probe_sha256","request","checkpoints"):
        assert a[key]==b[key],key
    assert len(a["checkpoints"])==20 and not any(c["file_writes"] or c["unimplemented"] for c in a["checkpoints"])
    actions={v["label"]:v for v in a["request"]["actions"]}
    phases=[]
    for label,wanted in [("unarmed-status",["Plate Mail +2 "]),
                         ("unarmored-status",["Long Sword +2 "]),
                         ("restored-status",["Long Sword +2 ","Plate Mail +2 "])]:
        action=actions[label]
        found=[c["vararg_1_candidate"]["text"] for c in equipment_calls(a,action["at"],action["end"])]
        assert found==wanted,(label,found)
        phases.append(dict(label=label,equipment=found))
    toggles=[]
    for label,item,state in [("sword-unreadied","Long Sword","No"),("sword-readied","Long Sword","Yes"),
                             ("armor-unreadied","Plate Mail","No"),("armor-readied","Plate Mail","Yes")]:
        action=actions[label]
        rows=[w["vararg_1_candidate"]["text"] for w in a["wrappers"]
              if action["at"]<w["step"]<action["end"] and w["format"]["text"]=="%s" and "\t" in w["vararg_1_candidate"]["text"]]
        matches=[text for text in rows if row_match(text)[3]==item and row_match(text)[1]==state]
        assert matches,(label,rows)
        toggles.append(dict(label=label,item=item,ready=state,rows=matches))
    for cp in a["checkpoints"]:
        assert sha(output/"observe-r3"/(cp["label"]+".png"))==sha(output/"control-r3"/(cp["label"]+".png"))
    write(output/"equipment-native-check.json",dict(checkpoints_equal=20,phases=phases,toggles=toggles,
        receipts={n:sha(output/n/"receipt.json") for n in ("observe-r3","control-r3")},
        limits="正常建角保存後狀態及按鍵；只證實原版裝卸與顯示隔離，不解析物品格式或推論未知裝備規則"))
    print(json.dumps(dict(checkpoints_equal=20,verified_toggles=4)))


def inputs(probe, output):
    assert read(output/"equipment-native-check.json")["checkpoints_equal"]==20
    base=probe/"creation-20261024/inputs-r4"
    target=output/"inputs-r4"
    if target.exists():
        assert sorted(p.relative_to(target) for p in target.rglob("*") if p.is_file())==sorted(p.relative_to(base) for p in base.rglob("*") if p.is_file())
        assert all(p.read_bytes()==(base/p.relative_to(target)).read_bytes() for p in target.rglob("*") if p.is_file()),"不能覆寫已生成的輸入"
    else:shutil.copytree(base,target)
    config=read(target/"inputs.json");origin=read(target/"provenance.json")
    en,zh=catalog(target/"en.tsv"),catalog(target/"zh-TW.tsv")
    trace_path=output/"observe-r3/receipt.json";trace=read(trace_path)
    added_fields=[];added_rows=[];added_menus=[]
    def key(source, button=False):
        # 物品與法術可能同名。只從已對齊前作的物品／列表詞條取文字。
        found=[k for k,v in en.items() if v==source and k in zh
               and (k.startswith(("inventory.","service.item.")) if not button else
                    any(f["Key"]==k and f["Pane"]=="menu" and config["Menus"].get(f["MenuSignature"])=="inventory" for f in config["Fields"]))]
        assert found and len({zh[k] for k in found})==1,(source,found)
        return sorted(found)[0]
    field_ids={json.dumps(f,sort_keys=True) for f in config["Fields"]}
    for c in trace["calls"]:
        if c["format"]["text"]!="%s" or c["vararg_1_candidate"]["text"]!="Items" or c["stack"][2]!=8004:continue
        templates=[f for f in config["Fields"] if f["Pane"]=="inventory" and en[f["Key"]]=="Items"]
        assert templates
        f=dict(templates[0],RawX=c["stack"][3],RawY=c["stack"][2],Caller=c["caller"])
        if json.dumps(f,sort_keys=True) in field_ids:continue
        config["Fields"].append(f);field_ids.add(json.dumps(f,sort_keys=True))
        added_fields.append(dict(binding=f,call_step=c["step"],first_glyph=c["first_glyph"],return_step=c["return_step"]))
    for c in trace["calls"]:
        if c["format"]["text"]!="%s" or c["vararg_1_candidate"]["text"]!="'s" or c["stack"][2]!=8004:continue
        templates=[f for f in config["Fields"] if f["Pane"]=="suffix" and en[f["Key"]]=="'s"]
        assert templates
        f=dict(templates[0],RawX=c["stack"][3],RawY=c["stack"][2],Caller=c["caller"])
        if json.dumps(f,sort_keys=True) in field_ids:continue
        config["Fields"].append(f);field_ids.add(json.dumps(f,sort_keys=True))
        added_fields.append(dict(binding=f,call_step=c["step"],first_glyph=c["first_glyph"],return_step=c["return_step"]))
    for c in equipment_calls(trace,480000000,880000000):
        text=c["vararg_1_candidate"]["text"]
        match=re.fullmatch(r"(.+?)(?: \+[0-9]+)? *",text)
        assert match and c["format"]["text"]=="%s"
        k=key(match[1]);wrapper=trace["wrappers"][c["wrapper_index"]]
        assert wrapper["format"]["text"]==text
        f=dict(Pane="callsite",Group="body",Key=k,Start=0,Length=len(match[1]),
               UpperCaller=wrapper["caller"],RawX=c["stack"][3],RawY=c["stack"][2],Caller=c["caller"],
               FormatSHA256=digest("%s"),SHA256=digest(text))
        # 已有同來源與遮罩的欄位保留原 key，避免同一個位置重複覆繪。
        if any(all(old.get(n)==f.get(n) for n in ("Pane","Start","Length","UpperCaller","RawX","RawY","Caller","FormatSHA256","SHA256")) for old in config["Fields"]):
            continue
        assert json.dumps(f,sort_keys=True) not in field_ids
        config["Fields"].append(f);field_ids.add(json.dumps(f,sort_keys=True))
        added_fields.append(dict(binding=f,call_step=c["step"],first_glyph=c["first_glyph"],return_step=c["return_step"]))
    for menu_index,menu in enumerate(trace["menus"]):
        if menu["Signature"] in config["Menus"]:continue
        buttons=menu["Buttons"]
        assert [bytes.fromhex(b["SourceHex"]).decode() for b in buttons]==["Rdy","Trade","Drop","Halve","Join","Exit"]
        assert menu["Count"] in (7,9)
        for button in buttons:
            source=bytes.fromhex(button["SourceHex"]).decode()
            native=lambda v:v if v<400 else (v-8000)*2
            f=dict(Pane="menu",Group="footer",Key=key(source,True),Start=0,Length=len(source),Caller=dict(Seg=0xceb,Off=0x1be),
                   RawX=native(button["RawX"]),RawY=native(button["RawY"])+1,MenuSignature=menu["Signature"],
                   FormatSHA256=digest(source),SHA256=digest(source),UpperCaller=dict(Seg=0,Off=0),UpperFormatSHA256="")
            config["Fields"].append(f)
            added_fields.append(dict(binding=f,menu_index=menu_index,button_index=button["Index"]))
        config["Menus"][menu["Signature"]]="inventory"
        added_menus.append(menu)
    rows_by_sha={r["SHA256"] for r in config["Rows"] if r["Pane"]=="inventory"}
    for w in trace["wrappers"]:
        text=w["vararg_1_candidate"]["text"]
        if w["format"]["text"]!="%s" or "\t" not in text or not any(p["step"]<=w["step"]<=p["return_instruction_step"] for p in trace["list_events"]):
            continue
        h=digest(text)
        if h in rows_by_sha:continue
        match=row_match(text)
        spans=[dict(Start=match.start(n),Length=len(match[n]),Key=key(match[n])) for n in (1,3)]
        row=dict(Pane="inventory",SHA256=h,Spans=spans,Foregrounds=[7,11])
        config["Rows"].append(row);rows_by_sha.add(h)
        added_rows.append(dict(binding=row,wrapper_step=w["step"],source=text))
    intervals=[]
    for group,end_key in (("calls","return_step"),("wrappers","return_step"),("fill_events","return_instruction_step"),("list_events","return_instruction_step")):
        for e in trace[group] or []:
            intervals.append([max(480000000,e["step"]-2000),min(880000000,e[end_key]+2000)])
    intervals += [[max(480000000,v["step"]-2000),min(880000000,v["step"]+2000)] for v in trace["display_changes"] if v["step"]>480000000]
    merged=[]
    for lo,hi in sorted(intervals):
        if merged and lo<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],hi)
        else:merged.append([lo,hi])
    config["fine_windows"]=merged
    trace_relative=Path(output.name)/"observe-r3/receipt.json"
    assert sha(probe/trace_relative)==sha(trace_path)
    origin["equipment_extension"]=dict(base=str(base.relative_to(probe)),base_files={p.name:sha(p) for p in base.iterdir() if p.is_file()},
        source_path=str(trace_relative),source_sha256=sha(trace_path),fields=added_fields,rows=added_rows,menus=added_menus,
        page_validation=dict(source_path=str(trace_relative),sha256=sha(trace_path)),
        limits="既有物品 TSV 與實際完整來源；只增加呈現綁定，不改原版 Rdy 判定、數量或加值")
    (target/"inputs.json").write_text(json.dumps(config,ensure_ascii=False,indent=2)+"\n")
    (target/"provenance.json").write_text(json.dumps(origin,ensure_ascii=False,indent=2)+"\n")
    for name in ("ui-inputs","observe-combined-boundaries-r2"):
        source=base.parent/name;destination=output/name
        assert source.is_dir()
        if not destination.exists():shutil.copytree(source,destination)
        assert sorted(p.relative_to(source) for p in source.rglob("*") if p.is_file())==sorted(p.relative_to(destination) for p in destination.rglob("*") if p.is_file())
        assert all(sha(p)==sha(destination/p.relative_to(source)) for p in source.rglob("*") if p.is_file())
    print(json.dumps(dict(added_fields=len(added_fields),added_rows=len(added_rows),added_menus=len(added_menus),fine_windows=len(merged),catalog_unchanged=True)))


def regression(probe, output):
    target=output/"inputs-creation-r4"
    assert not target.exists()
    shutil.copytree(output/"inputs-r4",target)
    reference=probe/"creation-20261024/observe-r4/receipt.json"
    config=read(target/"inputs.json")
    config["fine_windows"]=read(probe/"creation-20261024/inputs-r4/inputs.json")["fine_windows"]
    origin=read(target/"provenance.json")
    origin["equipment_extension"]["page_validation"]=dict(source_path=str(reference.relative_to(probe)),sha256=sha(reference))
    (target/"inputs.json").write_text(json.dumps(config,ensure_ascii=False,indent=2)+"\n")
    (target/"provenance.json").write_text(json.dumps(origin,ensure_ascii=False,indent=2)+"\n")
    print("已建立原建角路徑的新裝備來源回歸輸入")


def review(probe, output):
    run=read(output/"zh-r4/receipt.json")
    frames={f["step"]:f for f in run["frames"]}
    layouts={f["step"]:f for f in run["list_frames"]}
    en=catalog(output/"inputs-r4/en.tsv")
    checks=[]
    for label,wanted in [("unarmed-status",["Plate Mail"]),("unarmored-status",["Long Sword"]),
                         ("restored-status",["Long Sword","Plate Mail"])]:
        cp=next(c for c in run["checkpoints"] if c["label"]==label)
        assert not frames[cp["step"]]["held"]
        words=[w for w in layouts[cp["step"]]["words"] if w["X"]==8 and w["Y"] in (168,176)]
        assert [en[w["Key"]] for w in words]==wanted,(label,words)
        checks.append(dict(label=label,words=words))
    wanted={"initial-inventory","select-sword","sword-unreadied","unarmed-status","sword-readied",
            "armor-unreadied","unarmored-status","armor-readied","restored-status"}
    images=[dict(label=c["label"],**frames[c["step"]]) for c in run["checkpoints"] if c["label"] in wanted]
    assert len(images)==9 and all(not v["held"] for v in images)
    write(output/"review-images-r4.json",images)
    original=probe/"creation-20261024/control-r4/scratch/SAVE/CHTVERIF.qch"
    files=[]
    for folder in ("creation-en-r2","creation-zh-r2"):
        p=output/folder/"scratch/SAVE/CHTVERIF.qch"
        assert p.stat().st_size==499 and p.read_bytes()==original.read_bytes()
        files.append(dict(path=str(p.relative_to(output)),sha256=sha(p)))
    write(output/"display-check-r4.json",dict(equipment=checks,creation_qch=files,original_qch_sha256=sha(original)))
    print(json.dumps(dict(review_images=9,equipment_phases=3,creation_qch_equal=2)))


def guards(probe, output):
    assert read(output/"gpu-check-r4.json")["all_submitted_pixels_equal_expected"]
    results=[]
    for case,reason in [("menu","equipment route contains untranslated menu shape"),("mask","equipment lexical mask mismatch"),
                        ("title","equipment title remains untranslated")]:
        target=output/("negative-"+case)
        assert not target.exists()
        shutil.copytree(output/"inputs-r4",target)
        config=read(target/"inputs.json");origin=read(target/"provenance.json");e=origin["equipment_extension"]
        if case=="menu":
            signature=e["menus"][0]["Signature"]
            remove=[r for r in e["fields"] if r["binding"].get("MenuSignature")==signature]
            e["fields"]=[r for r in e["fields"] if r not in remove]
            config["Fields"]=[f for f in config["Fields"] if f not in [r["binding"] for r in remove]]
            del config["Menus"][signature]
            e["menus"]=[m for m in e["menus"] if m["Signature"]!=signature]
        elif case=="mask":
            f=next(r["binding"] for r in e["fields"] if r["binding"]["Pane"]=="callsite")
            original=dict(f)
            next(v for v in config["Fields"] if v==original)["Length"]+=3
            f["Length"]+=3
        else:
            remove=[r for r in e["fields"] if r["binding"]["Pane"]=="inventory"]
            assert len(remove)==1
            e["fields"]=[r for r in e["fields"] if r not in remove]
            config["Fields"]=[f for f in config["Fields"] if f!=remove[0]["binding"]]
        for name,value in (("inputs.json",config),("provenance.json",origin)):
            (target/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
        result=output/("unexpected-"+case+".json")
        command=[sys.executable,str(Path(__file__).with_name("ui_list_live_check.py")),str(output/"en-r4"),str(output/"zh-r4"),
                 str(target),str(output/"control-r3"),str(output/"observe-r3"),str(result)]
        p=subprocess.run(command,capture_output=True,text=True)
        assert p.returncode!=0 and not result.exists() and reason in p.stderr,p.stderr
        results.append(dict(case=case,returncode=p.returncode,reason=reason,stderr=p.stderr))
    write(output/"guards.json",dict(cases=results,checker_sha256=sha(Path(__file__).with_name("ui_list_live_check.py"))))
    print("三項獨立原版防護拒絕通過")


def evidence(root, output):
    assert output.resolve()==(root/"workplace/probe/equipment-20261024").resolve()
    parent=root/"workplace/probe/creation-20261024/evidence.json"
    previous=read(parent)
    main=read(output/"gpu-check-r4.json");creation=read(output/"creation-check-r2-r4.json")
    assert main["original_checkpoints_equal"]==20 and creation["original_checkpoints_equal"]==12
    assert main["checker_sha256"]==creation["checker_sha256"]==sha(root/"tools/ui_list_live_check.py")
    fixed=read(output/"run-r4.json")
    assert fixed["program_sha256"]==read(root/"workplace/probe/creation-20261024/run-r7.json")["program_sha256"]
    for name,h in fixed["source_files"].items():assert sha(root/name)==h
    for name,files in fixed["inputs"].items():
        for file,h in files.items():assert sha(output/name/file)==h
    names=list(previous["tools"])+["equipment_inputs.py"]
    snapshots=output/"tool-snapshots";assert not snapshots.exists();snapshots.mkdir()
    for name in names:shutil.copy2(root/"tools"/name,snapshots/name)
    def item(p):return dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p))
    sources=[item(parent)]
    for old in previous["sources"]:
        if old["path"].startswith("workplace/translation/") and Path(old["path"]).name in ("en.tsv","zh-TW.tsv","glossary.tsv","catalog.json","glossary-additions.tsv"):
            p=root/old["path"];assert sha(p)==old["sha256"];sources.append(item(p))
    sources.append(item(root/"workplace/input/dos/drkqueen/DQK.EXE"))
    target=output/"evidence.json"
    artifacts=[item(p) for p in sorted(output.rglob("*")) if p.is_file() and p!=target]
    write(target,dict(draft=True,sources=sources,artifacts=artifacts,tools={n:sha(root/"tools"/n) for n in names},
        docker_images=previous["docker_images"],accepted=["observe-r3","control-r3","en-r4","zh-r4","creation-en-r2","creation-zh-r2"],
        main=main,creation=creation,native=read(output/"equipment-native-check.json"),guards=read(output/"guards.json"),
        runtime_unchanged=True,limits="預設人類戰士的裝卸及原建角回歸；其他姓名長度的標題、任意裝備與拒絕回報未完成，正式入口與全遊戲中文化尚未驗收。原版、全文、字模及畫格留本機。"))
    print(json.dumps(dict(artifacts=len(artifacts),tools=len(names),sources=len(sources))))


if __name__=="__main__":
    if sys.argv[1]=="native-check":native_check(Path(sys.argv[2]))
    elif sys.argv[1]=="inputs":inputs(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="regression":regression(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="review":review(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="guards":guards(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="evidence":evidence(*map(Path,sys.argv[2:4]))
    else:raise SystemExit("未知子命令")
