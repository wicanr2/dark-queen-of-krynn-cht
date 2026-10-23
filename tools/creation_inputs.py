"""建角 DRAFT 的來源綁定；由已完成的原版正常按鍵收據產生，限 Docker。"""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys


def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text())
def catalog(path):
    rows=[line.split("\t",1) for line in path.read_text().splitlines()]
    assert rows.pop(0)==["key","text"] and all(len(r)==2 and all(r) for r in rows)
    result=dict(rows);assert len(result)==len(rows)
    return result
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
def tsv(path,values):path.write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k,v in sorted(values.items())))


def native_check(output,revision="r2"):
    assert revision in ("r2","r4")
    folders=("observe-"+revision,"control-"+revision)
    a,b=[read(output/n/"receipt.json") for n in folders]
    for key in ("source_commit","go_version","exe_sha256","state_sha256","request_sha256","probe_sha256","request","checkpoints"):
        assert a[key]==b[key],key
    assert a["request"]["start_steps"]==260000000 and len(a["checkpoints"])==12
    name=next(v["key"] for v in a["request"]["actions"] if v["label"]=="name-entered")
    assert 1<=len(name)<=15 and name.isascii() and name.isalnum()
    expected="SAVE\\"+name[:8].upper()+".qch"
    writes=a["checkpoints"][-1]["file_writes"]
    assert writes==[dict(Name=expected,N=n) for n in [414,17,17,17,17,17]]
    for cp in a["checkpoints"]:
        assert not cp["unimplemented"]
        assert not cp["file_writes"] or cp["file_writes"]==writes
        label=cp["label"]
        assert (output/folders[0]/(label+".png")).read_bytes()==(output/folders[1]/(label+".png")).read_bytes()
    files=[]
    for folder in folders:
        qch=output/folder/"scratch/SAVE"/(name[:8].upper()+".qch")
        assert qch.is_file() and qch.stat().st_size==499
        files.append(dict(file=str(qch.relative_to(output)),sha256=sha(qch.read_bytes()),mtime_ns=qch.stat().st_mtime_ns))
    assert files[0]["sha256"]==files[1]["sha256"]
    target=output/("original-check-"+revision+".json");assert not target.exists()
    write(target,dict(checkpoints_equal=12,request_sha256=a["request_sha256"],state_sha256=a["state_sha256"],saved_files=files,
        receipt_sha256={n:sha((output/n/"receipt.json").read_bytes()) for n in folders},
        limits="正常 MZ 角色選單狀態後建角、保存並加入；只驗本 fixture 的一個 499-byte QCH，不宣稱完整格式解析或擲骰規則對拍"))
    print(json.dumps(dict(checkpoints_equal=12,qch_bytes=499,qch_sha256=files[0]["sha256"])))


def inputs(probe,text,output,name="inputs-r1"):
    base=probe/"startup-captions-20261023-r3/inputs-r1"
    trace=read(output/"observe-r2/receipt.json")
    assert read(output/"original-check-r2.json")["checkpoints_equal"]==12
    assert Path(name).name==name and name.startswith("inputs-r")
    destination=output/name
    if destination.exists():
        assert sorted(f.relative_to(destination) for f in destination.rglob("*") if f.is_file())==sorted(f.relative_to(base) for f in base.rglob("*") if f.is_file())
        assert all(f.read_bytes()==(base/f.relative_to(destination)).read_bytes() for f in destination.rglob("*") if f.is_file()),"不能覆寫已生成或固定的輸入"
    else:shutil.copytree(base,destination)
    config=read(destination/"inputs.json");provenance=read(destination/"provenance.json")
    en,zh=catalog(destination/"en.tsv"),catalog(destination/"zh-TW.tsv")
    base_en,base_zh=dict(en),dict(zh)
    formal_en,formal_zh=catalog(text/"en.tsv"),catalog(text/"zh-TW.tsv")
    review={r["en"]:r for r in csv.DictReader((text/"creation-ui-review.tsv").open(),delimiter="\t")}
    removed=[f for f in config["Fields"] if f["Pane"]=="callsite" and f["RawX"]==8032 and f["RawY"]==8012 and f["UpperCaller"]==dict(Seg=0x2c4a,Off=0xd3) and en[f["Key"]]=="years" and not f.get("SourcePattern")]
    config["Fields"]=[f for f in config["Fields"] if f not in removed]
    added=[];origins={};seen=set()
    def field_id(f):
        names=("Pane","Key","RawX","RawY","Caller","UpperCaller","MenuSignature","Start","Length","SourcePattern")
        return tuple(json.dumps(f.get(k,dict(Seg=0,Off=0) if k.endswith("Caller") else ""),sort_keys=True) for k in names)
    seen.update(field_id(f) for f in config["Fields"])
    def locale(source):
        if source in review:
            r=review[source];key=r["key"];origins[key]=dict(review=r)
            en[key],zh[key]=source,r["zh-TW"]
            return key
        roots=[k for k,v in base_en.items() if v==source and k in base_zh]
        if roots:
            assert len({base_zh[k] for k in roots})==1,(source,roots)
            key=sorted(roots)[0];origins[key]=dict(base_key=key,en=source,zh=base_zh[key])
            return key
        roots=[k for k,v in formal_en.items() if k.startswith("ui.") and v==source]
        assert len(roots)==1,("missing or ambiguous formal source",repr(source),roots)
        root=roots[0];key="field."+root[3:]
        if key in zh:assert (en[key],zh[key])==(source,formal_zh[root])
        en[key],zh[key]=source,formal_zh[root]
        origins[key]=dict(formal_key=root,en=source,zh=formal_zh[root])
        return key
    for c in trace["calls"]:
        fmt=c["format"]["text"];source=c["vararg_1_candidate"]["text"] if fmt=="%s" else fmt
        caller=c["caller"];x,y=c["stack"][3],c["stack"][2]
        direct=caller==dict(Seg=0x1bb6,Off=0x1be) or (caller["Seg"]==0x26b4 and caller["Off"] in (0x2918,0x2931,0x294a,0x2963,0x9dd)) or (caller==dict(Seg=0x266d,Off=0x11f) and source=="Character name:")
        button=caller==dict(Seg=0xceb,Off=0x1be)
        prompt=source in ("add from where? ","add a character:")
        save=source.startswith("Save ") and source.endswith("? ") and c["stack"][4]==0x70
        wrapper=trace["wrappers"][c["wrapper_index"]] if c["wrapper_index"]>=0 else None
        actor=wrapper and ((wrapper["caller"]==dict(Seg=0x2c4a,Off=0x2f0) and source=="Fighter") or
                         (wrapper["caller"]["Seg"]==0x26b4 and wrapper["caller"]["Off"] in (0x77c,0x7b6,0x8e8) and source in ("Male","Human","Fighter")))
        age=wrapper and wrapper["caller"]==dict(Seg=0x2c4a,Off=0xd3) and source.endswith(" years") and source[:-6].isdigit()
        if not (direct or button or prompt or save or actor or age):continue
        if save:source="Save"
        if age:source="years"
        key=locale(source)
        field=dict(Pane="menu-text" if direct else "menu" if button else "callsite",Group="body" if direct else "footer",Key=key,
                   SHA256=sha(source.encode()),FormatSHA256=sha(fmt.encode()),Start=0,Length=len(source),RawX=x,RawY=y,Caller=caller,
                   MenuSignature="",UpperCaller=dict(Seg=0,Off=0),UpperFormatSHA256="")
        if direct and caller["Seg"]==0x26b4:field["Group"]="header"
        if direct and source=="Character name:":field.update(Group="footer",Color=0x80,BackgroundOverride=23)
        if direct or button:
            assert c["menu_index"]>=0
            menu=trace["menus"][c["menu_index"]];signature=menu["Signature"]
            field["MenuSignature"]=signature
            config["Menus"].setdefault(signature,"creation")
            if signature=="191c0ba49dc03bfaceb8be1ab19c0d92efb10341e05b2c851e46682a74451ed1" and button:
                # 已確認的角色管理字級及鍵值由父批次完整沿用。
                assert any(f["Pane"]=="menu" and f["MenuSignature"]==signature and f["SHA256"]==field["SHA256"] and f["RawX"]==x and f["RawY"]==y and f["FontSize"]==20 for f in config["Fields"])
                continue
        else:
            if actor or age:
                assert wrapper["format"]["text"]==(c["vararg_1_candidate"]["text"])
                field.update(Group="body",UpperCaller=wrapper["caller"])
                if age:field["SourcePattern"]="age-unit"
            else:
                assert wrapper["format"]["text"]=="%s" and wrapper["caller"]==dict(Seg=0xceb,Off=0x995)
                field.update(UpperCaller=wrapper["caller"],UpperFormatSHA256=sha(b"%s"),UpperNative=[0,192],Color=0x70,BackgroundOverride=7)
                if save:field["SourcePattern"]="created-name"
                if prompt:field["Width"]=124
        assert len(zh[key])*8<=len(source)*8,(key,zh[key],source)
        identity=field_id(field)
        if identity in seen:continue
        seen.add(identity);config["Fields"].append(field);added.append(dict(binding=field,call_step=c["step"],first_glyph=c["first_glyph"],return_step=c["return_step"]))
    # 逐一沿用原版十五種合法姓名長度的實際 Yes／No 表，不推測中間座標。
    cases=read(output/"name-cases/results.json")
    for case in cases["cases"]:
        relative=Path("name-cases")/f"length-{case['length']:02}"/"observe/receipt.json"
        path=output/relative;part=read(path);assert sha(path.read_bytes())==case["receipt_sha256"]["observe"]
        for c in part["calls"]:
            if c["caller"]!=dict(Seg=0xceb,Off=0x1be) or c["menu_index"]<0:continue
            table=part["menus"][c["menu_index"]]
            if table["Signature"]!=case["menu"]["Signature"]:continue
            source=c["format"]["text"];key=locale(source)
            f=dict(Pane="menu",Group="footer",Key=key,SHA256=sha(source.encode()),FormatSHA256=sha(source.encode()),Start=0,Length=len(source),
                   RawX=c["stack"][3],RawY=c["stack"][2],Caller=c["caller"],MenuSignature=table["Signature"],UpperCaller=dict(Seg=0,Off=0),UpperFormatSHA256="")
            identity=field_id(f)
            if identity in seen:continue
            seen.add(identity);config["Fields"].append(f);config["Menus"].setdefault(table["Signature"],"creation")
            added.append(dict(binding=f,call_step=c["step"],first_glyph=c["first_glyph"],return_step=c["return_step"],source_path=str((output/relative).relative_to(probe)),source_sha256=sha(path.read_bytes())))
    # 正式清單須可獨立回查；字模來源另外保留舊閱讀聯集。
    used={f["Key"] for f in config["Fields"]}|set(catalog(base/"zh-TW.tsv"))
    zh={k:v for k,v in zh.items() if k in used}
    font=catalog(base/"font-zh-TW.tsv") if (base/"font-zh-TW.tsv").exists() else {}
    font.update(zh)
    intervals=[]
    for group,end in (("calls","return_step"),("wrappers","return_step"),("fill_events","return_instruction_step"),("paragraphs","return_step")):
        for e in trace[group] or []:intervals.append([max(260000000,e["step"]-2000),min(480000000,e[end]+2000)])
    merged=[]
    for lo,hi in sorted(intervals):
        if merged and lo<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],hi)
        else:merged.append([lo,hi])
    config["fine_windows"]=merged
    provenance["creation_extension"]=dict(base=str(base.relative_to(probe)),source_path=str((output/"observe-r2/receipt.json").relative_to(probe)),source_sha256=sha((output/"observe-r2/receipt.json").read_bytes()),
        review_sha256=sha((text/"creation-ui-review.tsv").read_bytes()),origins=origins,added=added,removed_age_fields=removed,limits="建角正常預設人類戰士路徑；新文字框沒有按鈕語意，姓名、數值與選項判定不變")
    write(destination/"inputs.json",config);write(destination/"provenance.json",provenance)
    tsv(destination/"en.tsv",en);tsv(destination/"zh-TW.tsv",zh);tsv(destination/"font-zh-TW.tsv",font)
    print(json.dumps(dict(added_fields=len(added),words=len(zh),source_keys=len(en),fine_windows=len(merged),replaced_age_fields=len(removed))))


def glyphs(probe,output,name="inputs-r1"):
    base=read(probe/"startup-captions-20261023-r3/inputs-r1/glyphs-16.json")
    path=output/name/"glyphs-16.json";new=read(path)
    assert all(base[k]==new[k] for k in ("size","height","font_sha256"))
    for k,v in base["glyphs"].items():
        if k in new["glyphs"]:assert v==new["glyphs"][k]
    base["glyphs"].update(new["glyphs"]);write(path,base)
    print(json.dumps(dict(glyphs=len(base["glyphs"]))))


def name_cases(output):
    target=output/"name-cases";assert not target.exists();target.mkdir()
    state=output/"observe-done-values/final.state";digest=sha(state.read_bytes())
    for length in range(1,16):
        folder=target/f"length-{length:02}";folder.mkdir()
        actions=[dict(At=321000000,End=322000000,Kind="text",Key="A"*length,Label="name-entered"),
                 dict(At=323000000,End=340000000,Kind="named",Key="Return",Label="combat-icon"),
                 dict(At=341000000,End=360000000,Kind="text",Key="d",Label="save-question"),
                 dict(At=361000000,End=380000000,Kind="text",Key="n",Label="declined-save")]
        write(folder/"request.json",dict(state_sha256=digest,start_steps=320000000,Actions=actions))
    print("已建立十五種姓名長度的正常輸入及不儲存分支")


def name_cases_check(output):
    results=[]
    for length in range(1,16):
        folder=output/"name-cases"/f"length-{length:02}"
        a,b=[read(folder/n/"receipt.json") for n in ("observe","control")]
        for key in ("source_commit","go_version","exe_sha256","state_sha256","request_sha256","probe_sha256","request","checkpoints"):assert a[key]==b[key],(length,key)
        assert len(a["checkpoints"])==4 and all(not c["file_writes"] and not c["unimplemented"] for c in a["checkpoints"])
        question=next(c for c in a["calls"] if c["format"]["text"]=="%s" and c["vararg_1_candidate"]["text"]=="Save "+"A"*length+"? ")
        choices=next(m for m in a["menus"] if len(m["Buttons"])==2 and [bytes.fromhex(v["SourceHex"]).decode() for v in m["Buttons"]]==["Yes","No"])
        assert choices["Count"]==3 and [v["Index"] for v in choices["Buttons"]]==[1,2]
        coords=[(v["RawX"]-8000)*2 for v in choices["Buttons"]]
        assert coords==[8+len(question["vararg_1_candidate"]["text"])*8,40+len(question["vararg_1_candidate"]["text"])*8]
        assert all(v["RawY"]==8094 for v in choices["Buttons"])
        results.append(dict(length=length,checkpoints_equal=4,question_step=question["step"],menu=choices,receipt_sha256={n:sha((folder/n/"receipt.json").read_bytes()) for n in ("observe","control")}))
    target=output/"name-cases/results.json";assert not target.exists();write(target,dict(cases=results,limits="十五種合法 ASCII 姓名長度；正常原版輸入及 No 分支，不代表繁中 GUI 或所有字元組合"))
    print(json.dumps(dict(cases=len(results),original_checkpoints_equal=60)))


def legacy_inputs(probe,output):
    target=output/"inputs-legacy-r3";assert not target.exists();shutil.copytree(output/"inputs-r3",target)
    reference=probe/"startup-captions-20261023-r3/legacy-observe-r1/receipt.json"
    trace=read(reference);config=read(target/"inputs.json")
    intervals=read(probe/"services-trade-20261023/inputs-r2/inputs.json")["fine_windows"]
    for c in trace["calls"]:
        if c["wrapper_index"]<0:continue
        w=trace["wrappers"][c["wrapper_index"]]
        if w["caller"]==dict(Seg=0x2c4a,Off=0xd3) and c["vararg_1_candidate"]["text"].endswith(" years"):
            intervals.append([w["step"]-2000,w["return_step"]+2000])
    merged=[]
    for lo,hi in sorted(intervals):
        if merged and lo<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],hi)
        else:merged.append([lo,hi])
    config["fine_windows"]=merged;write(target/"inputs.json",config)
    origin=read(target/"provenance.json");origin["creation_extension"]["legacy_validation"]=dict(source_path=str(reference.relative_to(probe)),sha256=sha(reference.read_bytes()),limits="沿既有六類選單細驗，另補新年齡單位的原版印字區間；其餘輸入與主流程相同")
    write(target/"provenance.json",origin)
    print(json.dumps(dict(legacy_fine_windows=len(merged))))


def page_inputs(output):
    target=output/"inputs-r4";assert not target.exists();shutil.copytree(output/"inputs-r3",target)
    path=output/"observe-r4/receipt.json";trace=read(path)
    assert read(output/"original-check-r4.json")["checkpoints_equal"]==12
    config=read(target/"inputs.json")
    intervals=config["fine_windows"]+[[max(260000000,v["step"]-2000),min(480000000,v["step"]+2000)] for v in trace["display_changes"] if v["step"]>260000000]
    merged=[]
    for lo,hi in sorted(intervals):
        if merged and lo<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],hi)
        else:merged.append([lo,hi])
    config["fine_windows"]=merged;write(target/"inputs.json",config)
    origin=read(target/"provenance.json");origin["creation_extension"]["page_validation"]=dict(source_path="creation-20261024/observe-r4/receipt.json",sha256=sha(path.read_bytes()))
    write(target/"provenance.json",origin)
    print(json.dumps(dict(fine_windows=len(merged))))


def review_output(output):
    run=read(output/"zh-r7/receipt.json");frames={f["step"]:f for f in run["frames"]}
    images=[dict(label=c["label"],**frames[c["step"]]) for c in run["checkpoints"]]
    assert len(images)==12 and all(not v["held"] for v in images)
    target=output/"review-images-r7.json";assert not target.exists();write(target,images)
    files=[]
    for folder in ("observe-r4","control-r4","en-r7","zh-r7"):
        p=output/folder/"scratch/SAVE/CHTVERIF.qch";assert p.stat().st_size==499
        files.append(dict(path=str(p.relative_to(output)),sha256=sha(p.read_bytes())))
    assert len({v["sha256"] for v in files})==1
    target=output/"gpu-qch-check-r7.json";assert not target.exists();write(target,dict(bytes=499,files=files))
    print(json.dumps(dict(images=12,qch_equal=4)))


def evidence(root,output):
    assert output.resolve()==(root/"workplace/probe/creation-20261024").resolve()
    target=output/"evidence.json";assert not target.exists()
    parent=root/"workplace/probe/startup-captions-20261023-r3/evidence.json";previous=read(parent)
    main,legacy=[read(output/n) for n in ("gpu-check-r7.json","legacy-check-r7-final.json")]
    assert main["original_checkpoints_equal"]==12 and legacy["original_checkpoints_equal"]==16
    fixed=read(output/"run-r7.json")
    for p,digest in fixed["source_files"].items():assert sha((root/p).read_bytes())==digest
    for p,digest in fixed["inputs"].items():assert sha((output/"inputs-r4"/p).read_bytes())==digest
    assert sha((root/"workplace/probe/ui-list-live").read_bytes())==fixed["program_sha256"]
    names=list(previous["tools"])+["creation_inputs.py","creation_patterns_test.go"]
    folder=output/"tool-snapshots";assert not folder.exists();folder.mkdir()
    tool_hashes={}
    for name in names:
        p=root/"tools"/name;shutil.copy2(p,folder/name);tool_hashes[name]=sha(p.read_bytes())
    def item(p):return dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
    sources=[item(parent)]
    for old in previous["sources"]:
        if old["path"].startswith("workplace/translation/") and Path(old["path"]).name in ("en.tsv","zh-TW.tsv","glossary.tsv","catalog.json","glossary-additions.tsv"):
            p=root/old["path"];assert sha(p.read_bytes())==old["sha256"];sources.append(item(p))
    sources += [item(root/"workplace/translation/creation-ui-review.tsv"),item(root/"workplace/input/dos/drkqueen/DQK.EXE")]
    artifacts=[item(p) for p in sorted(output.rglob("*")) if p.is_file() and p!=target]
    write(target,dict(draft=True,docker_images=previous["docker_images"],source_commit="f79eab6db8c64a524a06535e53e5d32b0bbcf7c8",sources=sources,tools=tool_hashes,artifacts=artifacts,
        accepted_runs=["observe-r4","control-r4","en-r7","zh-r7","legacy-en-r7","legacy-zh-r7"],
        diagnostic_runs=["en-r1","zh-r1","en-r2","zh-r2","en-r3","zh-r3","en-r4","zh-r4","en-r5","zh-r5","en-r6","zh-r6"],
        main=main,legacy=legacy,name_cases=read(output/"name-cases/results.json"),saved_character=read(output/"gpu-qch-check-r7.json"),
        rights="原版、角色檔、全文、字模、畫格及衍生輸入只留本機；程式與最小研究文件入 Git",
        limits="本預設人類戰士正常快照及按鍵的 DRAFT；十五種姓名長度只有原版及來源測試，沒有各長度 GPU 驗收。未驗其他職業、重擲、修改、全部介面或正式入口。r1 的一份舊 Go 來源無法完整復原，僅保留診斷二進位與 reconstruction-proof，不作成功來源。"))
    print(json.dumps(dict(artifacts=len(artifacts),tools=len(tool_hashes),sources=len(sources))))


if __name__=="__main__":
    if sys.argv[1]=="native-check":native_check(Path(sys.argv[2]),*sys.argv[3:4])
    elif sys.argv[1]=="page-inputs":page_inputs(Path(sys.argv[2]))
    elif sys.argv[1]=="review":review_output(Path(sys.argv[2]))
    elif sys.argv[1]=="evidence":evidence(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="name-cases":name_cases(Path(sys.argv[2]))
    elif sys.argv[1]=="name-cases-check":name_cases_check(Path(sys.argv[2]))
    elif sys.argv[1]=="legacy-inputs":legacy_inputs(*map(Path,sys.argv[2:4]))
    elif sys.argv[1]=="inputs":inputs(*map(Path,sys.argv[2:5]),*(sys.argv[5:6]))
    elif sys.argv[1]=="glyphs":glyphs(*map(Path,sys.argv[2:4]),*(sys.argv[4:5]))
    else:raise SystemExit("未知子命令")
