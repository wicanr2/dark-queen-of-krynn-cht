"""戰鬥施法清單的 DRAFT 衍生資料；不改原版法術與選取。"""
import copy
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import subprocess
import tempfile

from literal_catalog import catalog, digest, read, sha, windows
from text_catalog import write_tsv
from translation_check import load


BASE = "bar-ui-20261024/inputs-r2"
SOURCE = "battle-cast-20261024/observe-cast-r2/receipt.json"
GLYPHS = "battle-cast-20261024/glyphs-cast-16.json"
LABEL_EN = "battle-cast-20261024/title.en.tsv"
LABEL_ZH = "battle-cast-20261024/title.zh-TW.review.tsv"


def write(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")


def labels(probe,texts):
    en,zh=catalog(texts/"en.tsv"),catalog(texts/"zh-TW.tsv")
    extra=catalog(probe/LABEL_EN)
    translated={r["key"]:r["text"] for r in load(probe/LABEL_ZH,["key","text","note"])}
    assert len(extra)==1 and set(extra)==set(translated) and not (set(extra)&set(en))
    en.update(extra);zh.update(translated)
    return en,zh,set(extra)


def derive(probe, texts):
    trace = read(probe/SOURCE)
    old = read(probe/BASE/"inputs.json")
    config = copy.deepcopy(old)
    en,zh,reviewed = labels(probe,texts)
    aliases, row_sources, fields, contexts, menus = {}, [], [], [], {}
    def alias(source, domain):
        choices = [k for k,v in en.items() if v.casefold()==source.casefold() and k in zh]
        assert choices and len({zh[k] for k in choices})==1, source
        formal = min(choices,key=lambda k:(en[k]!=source,not k.startswith("ui."),k))
        key = domain+"."+digest(source)[:20]
        row = dict(key=key,source_key=formal,source_catalog="reviewed" if formal in reviewed else "formal",source=source)
        if key in aliases:assert aliases[key]==row
        aliases[key]=row
        return key
    for menu in trace["menus"]:
        if [bytes.fromhex(b["SourceHex"]).decode() for b in menu["Buttons"]] != ["Cast","Exit"]:continue
        assert menu["Count"] in (3,6) and len(bytes.fromhex(menu["RawHex"]))==menu["Count"]*32
        menus[menu["Signature"]]="grimoire"
        for button in menu["Buttons"]:
            source=bytes.fromhex(button["SourceHex"]).decode()
            key=alias(source,"field")
            native=lambda n:n if n<400 else (n-8000)*2
            field=dict(Pane="menu",Group="footer",Key=key,Start=0,Length=len(source),Caller=dict(Seg=0xCEB,Off=0x1BE),
                RawX=native(button["RawX"]),RawY=native(button["RawY"])+1,MenuSignature=menu["Signature"],
                SHA256=button["SHA256"],FormatSHA256=button["SHA256"])
            assert field["RawY"]==189
            assert field not in config["Fields"]
            fields.append(field);config["Fields"].append(field)
    assert len(menus)==2 and not (set(menus)&set(old["Menus"]))
    config["Menus"].update(menus)
    headers=[]
    for index,wrapper in enumerate(trace["wrappers"]):
        source=wrapper["format"]
        source_key="ui."+digest(source["text"])[:20]
        if source_key not in reviewed:continue
        assert wrapper["stack"][3]&255==1 and source["nul_terminated"]
        key=alias(source["text"],"header")
        header=dict(Pane="grimoire",Key=key,Segment=source["segment"],Offset=source["offset"],SHA256=digest(source["text"]))
        assert header not in old["Headers"]
        config["Headers"].append(header);headers.append(header)
        calls=[c for c in trace["calls"] if c["wrapper_index"]==index and c["format"]["text"]=="%s" and c["vararg_1_candidate"]["text"]==source["text"]]
        assert len(calls)==1
        call=calls[0]
        field=dict(Pane="grimoire",Group="header",Key=alias(source["text"],"field"),Start=0,Length=len(source["text"]),
            MenuSignature="",RawX=call["stack"][3],RawY=call["stack"][2],Caller=call["caller"],
            FormatSHA256=digest(call["format"]["text"]),SHA256=digest(source["text"]))
        fields.append(field);config["Fields"].append(field)
    assert len(headers)==1
    for listing in trace["list_events"]:
        menu=listing.get("menu_snapshot",{})
        if menu.get("Signature") not in menus:continue
        context=dict(Pane="grimoire",RowFillPage=True,DescriptorSHA256=hashlib.sha256(bytes.fromhex(listing["descriptor_before_hex"])).hexdigest(),
                     MenuSignature=menu["Signature"],Caller=dict(Seg=listing["stack"][1],Off=listing["stack"][0]))
        assert context not in old["PaneLists"]
        if context not in contexts:contexts.append(context)
    assert len(contexts)==2
    config["PaneLists"].extend(contexts)
    original_rows={}
    for wrapper in trace["wrappers"]:
        if wrapper["caller"] not in old["RowCallers"] or wrapper["format"]["text"]!="%s":continue
        source=wrapper["vararg_1_candidate"]
        assert source["nul_terminated"]
        text=source["text"]
        if text.startswith("\t"):
            match=re.fullmatch(r"\t(.+?)(?: \([1-9][0-9]*\))?",text)
            assert match and "\t" not in match[1]
            start,name=1,match[1]
        else:
            assert text=="Special" or re.fullmatch(r"[1-9](?:st|nd|rd|th) Level",text),repr(text)
            start,name=0,text
        key=alias(name,"grimoire")
        h=digest(text)
        record=original_rows.setdefault(h,dict(source=text,spans=[dict(Start=start,Length=len(name),Key=key)],colors=set()))
        assert record["source"]==text
        color=wrapper["stack"][4]&255
        assert color in (7,11,12)
        record["colors"].add(color)
    for h,record in original_rows.items():
        row=dict(Pane="grimoire",SHA256=h,Spans=record["spans"],Foregrounds=sorted(record["colors"]))
        previous=next((r for r in config["Rows"] if (r["Pane"],r["SHA256"])==("grimoire",h)),None)
        if previous:
            assert previous["Spans"]==row["Spans"]
            previous["Foregrounds"]=sorted(set(previous["Foregrounds"])|record["colors"])
        else:config["Rows"].append(row)
        row_sources.append(dict(source=record["source"],row=row))
    assert len(row_sources)==33
    config["fine_windows"]=windows(trace)
    return config,dict(aliases=list(aliases.values()),rows=row_sources,fields=fields,contexts=contexts,menus=menus,headers=headers)


def native(output):
    a,b=[read(output/(m+"-cast-r2/receipt.json")) for m in ("observe","control")]
    for k in ("source_commit","go_version","exe_sha256","state_sha256","request_sha256","probe_sha256","request","checkpoints"):
        assert a[k]==b[k],k
    assert a["probe_sha256"]==sha(output/"programs-r1/ui-context-probe")
    assert a["request_sha256"]==sha(output/"cast-request-r2.json")
    assert all(not a[k] for k in a if k.startswith("pending_")) and len(a["checkpoints"])==5
    for cp in a["checkpoints"]:
        assert not cp["file_writes"] and not cp["unimplemented"]
        for suffix in (".png",".idx"):
            assert sha(output/("observe-cast-r2/"+cp["label"]+suffix))==sha(output/("control-cast-r2/"+cp["label"]+suffix))
    assert sha(output/"observe-cast-r2/final.state")==sha(output/"control-cast-r2/final.state")
    write(output/"native-check.json",dict(checkpoints=5,source_sha256=sha(output/"observe-cast-r2/receipt.json"),
        limits="正常首戰狀態、Cast、兩次 PageDown 及 Exit；沒有施法成功、戰鬥勝利或中文畫面聲明。"))


def font_values(probe,texts,data):
    font=catalog(probe/BASE/"font-zh-TW.tsv");_,targets,_=labels(probe,texts)
    font.update({a["key"]:targets[a["source_key"]] for a in data["aliases"]})
    return font


def glyph_inputs(root,output):
    probe=root/"workplace/probe";texts=root/"workplace/translation"
    _,data=derive(probe,texts)
    old=read(probe/BASE/"glyphs-16.json")
    missing=set("".join(font_values(probe,texts,data).values()))-set("\r\n\t")-set(old["glyphs"])
    target=output/"glyph-source.tsv";assert not target.exists()
    write_tsv(target,["key","text"],(("glyph."+format(ord(c),"x"),c) for c in sorted(missing)))


def merged_glyphs(probe,texts,data):
    old=read(probe/BASE/"glyphs-16.json");fresh=read(probe/GLYPHS)
    assert all(fresh[k]==old[k] for k in ("size","height","font_sha256"))
    missing=set("".join(font_values(probe,texts,data).values()))-set("\r\n\t")-set(old["glyphs"])
    assert set(fresh["glyphs"])==missing,"cast glyph set"
    for value in fresh["glyphs"].values():
        raw=base64.b64decode(value,validate=True);assert len(raw)==320 and not any(raw[256:]),"cast glyph bounds"
    result=copy.deepcopy(old);result["glyphs"].update(fresh["glyphs"])
    return result


def generate(root, target):
    probe=root/"workplace/probe";texts=root/"workplace/translation";base=probe/BASE
    config,proof=derive(probe,texts)
    shutil.copytree(base,target)
    en,zh,font=[catalog(target/n) for n in ("en.tsv","zh-TW.tsv","font-zh-TW.tsv")]
    _,targets,_=labels(probe,texts)
    for a in proof["aliases"]:
        k=a["key"];value=targets[a["source_key"]]
        if k in en:assert (en[k],zh[k])==(a["source"],value)
        en[k],zh[k],font[k]=a["source"],value,value
    glyphs=merged_glyphs(probe,texts,proof)
    provenance=read(target/"provenance.json")
    provenance["cast_extension"]=dict(base=BASE,base_files={p.name:sha(p) for p in base.iterdir()},
        source_path=SOURCE,source_sha256=sha(probe/SOURCE),data=proof,
        glyph_source_path=GLYPHS,glyph_source_sha256=sha(probe/GLYPHS),
        reviewed_files={n:sha(probe/n) for n in (LABEL_EN,LABEL_ZH)},
        page_validation=dict(source_path=SOURCE,source_sha256=sha(probe/SOURCE)),
        formal_files={n:sha(texts/n) for n in ("en.tsv","zh-TW.tsv","glossary.tsv","catalog.json","glossary-additions.tsv")})
    for n,values in (("en.tsv",en),("zh-TW.tsv",zh),("font-zh-TW.tsv",font)):
        write_tsv(target/n,["key","text"],values.items())
    write(target/"inputs.json",config);write(target/"provenance.json",provenance)
    write(target/"glyphs-16.json",glyphs)


def check_sources(inputs, config, provenance, en, zh, glyphs):
    root=inputs.parent.parent;proof=provenance["cast_extension"];base=root/BASE
    assert proof["base"]==BASE and proof["source_path"]==SOURCE
    assert set(proof["base_files"])=={p.name for p in base.iterdir()}
    for n,h in proof["base_files"].items():assert Path(n).name==n and sha(base/n)==h
    assert sha(root/SOURCE)==proof["source_sha256"]
    assert proof["page_validation"]==dict(source_path=SOURCE,source_sha256=sha(root/SOURCE))
    for n,h in proof["formal_files"].items():assert sha(Path("/catalogs")/n)==h
    assert set(proof["reviewed_files"])=={LABEL_EN,LABEL_ZH}
    for n,h in proof["reviewed_files"].items():assert sha(root/n)==h
    expected,data=derive(root,Path("/catalogs"))
    assert config==expected,"cast config"
    assert proof["data"]==data,"cast source records"
    parent=read(base/"provenance.json")
    assert {k:v for k,v in provenance.items() if k!="cast_extension"}==parent
    old_en,old_zh=catalog(base/"en.tsv"),catalog(base/"zh-TW.tsv")
    _,targets,_=labels(root,Path("/catalogs"))
    assert en==dict(old_en,**{a["key"]:a["source"] for a in data["aliases"]})
    assert zh==dict(old_zh,**{a["key"]:targets[a["source_key"]] for a in data["aliases"]}),"cast translation"
    font=catalog(base/"font-zh-TW.tsv");font.update({a["key"]:targets[a["source_key"]] for a in data["aliases"]})
    assert catalog(inputs/"font-zh-TW.tsv")==font
    assert proof["glyph_source_path"]==GLYPHS and sha(root/GLYPHS)==proof["glyph_source_sha256"]
    for n in set(proof["base_files"])-{"inputs.json","provenance.json","en.tsv","zh-TW.tsv","font-zh-TW.tsv","glyphs-16.json"}:
        assert (inputs/n).read_bytes()==(base/n).read_bytes(),n
    assert glyphs==merged_glyphs(root,Path("/catalogs"),data),"cast glyph union"
    return base,read(base/"inputs.json"),parent,old_en,old_zh,read(base/"glyphs-16.json")


def prepare(root,output):
    assert read(output/"native-check.json")["checkpoints"]==5
    generate(root,output/"inputs-r3")


def guards(root,output):
    source=output/"inputs-r3"
    def check(path):return check_sources(path,read(path/"inputs.json"),read(path/"provenance.json"),catalog(path/"en.tsv"),catalog(path/"zh-TW.tsv"),read(path/"glyphs-16.json"))
    check(source);cases=[]
    for name in ("row","color","menu","descriptor","inherited","translation","header","glyph"):
        with tempfile.TemporaryDirectory(dir=output,prefix="guard-") as temporary:
            target=Path(temporary);shutil.copytree(source,target,dirs_exist_ok=True)
            config=read(target/"inputs.json")
            if name=="glyph":
                glyphs=read(target/"glyphs-16.json");glyphs["glyphs"].pop(next(iter(read(output/"glyphs-cast-16.json")["glyphs"])))
                write(target/"glyphs-16.json",glyphs)
            elif name=="translation":
                zh=catalog(target/"zh-TW.tsv");zh[config["Rows"][-1]["Spans"][0]["Key"]]+="x"
                write_tsv(target/"zh-TW.tsv",["key","text"],zh.items())
            else:
                if name=="row":config["Rows"][-1]["Spans"][0]["Start"]+=1
                elif name=="color":config["Rows"][-1]["Foregrounds"].append(3)
                elif name=="menu":config["Menus"].pop(next(iter(read(source/"provenance.json")["cast_extension"]["data"]["menus"])))
                elif name=="descriptor":config["PaneLists"][-1]["DescriptorSHA256"]="0"*64
                elif name=="header":config["Headers"][-1]["SHA256"]="0"*64
                else:config["Fields"][0]["RawX"]+=1
                write(target/"inputs.json",config)
            try:check(target)
            except AssertionError as error:assert str(error)==({"translation":"cast translation","glyph":"cast glyph union"}.get(name,"cast config")),(name,error)
            else:raise AssertionError(name)
            cases.append(name)
    with tempfile.TemporaryDirectory(dir=output,prefix="rebuild-") as temporary:
        target=Path(temporary)/"inputs";generate(root,target)
        assert {p.name for p in target.iterdir()}=={p.name for p in source.iterdir()}
        for file in source.iterdir():assert file.read_bytes()==(target/file.name).read_bytes(),file.name
        rebuilt=Path(temporary)/"glyphs.json"
        subprocess.run([sys.executable,str(Path(__file__).with_name("menu_glyphs.py")),"/font/jf-openhuninn-2.1.ttf",str(output/"glyph-source.tsv"),str(rebuilt),"16"],check=True,capture_output=True,text=True,timeout=15)
        assert rebuilt.read_bytes()==(output/"glyphs-cast-16.json").read_bytes()
    write(output/"guards.json",dict(cases=cases,rebuilt_files=len(list(source.iterdir())),glyph_rebuilt=True,tool_sha256=sha(Path(__file__))))


def review(output):
    from PIL import Image,ImageDraw
    en,zh=catalog(output/"inputs-r3/en.tsv"),catalog(output/"inputs-r3/zh-TW.tsv")
    data=read(output/"inputs-r3/provenance.json")["cast_extension"]["data"]
    runs={lang:read(output/(lang+"-r4/receipt.json")) for lang in ("en","zh")}
    run=runs["zh"]
    accepted={e["detail"]["source_sha256"] for e in run["list_events"] if e["Kind"]=="row-before-glyph"}
    assert {r["row"]["SHA256"] for r in data["rows"]}<=accepted
    points=[]
    for cp in run["checkpoints"]:
        i=next(i for i,f in enumerate(run["frames"]) if f["step"]==cp["step"])
        frame,state=run["frames"][i],run["list_frames"][i]
        assert not frame["held"],("stable checkpoint held",cp["label"])
        points.append(dict(label=cp["label"],step=cp["step"],frame=frame["File"],sha256=frame["SHA256"],words=state["words"]))
    assert len(points)==5 and points[0]["words"]==points[-1]["words"]
    assert points[0]["sha256"]==points[-1]["sha256"],"cancel must restore battle"
    visible={w["Key"] for p in points[1:4] for w in p["words"]}
    for a in data["aliases"]:
        if a["key"].startswith("header."):continue
        # 一級標題已有相同正文與譯文的舊欄位，兩者共用畫面位置。
        equivalent={k for k,v in en.items() if v==en[a["key"]] and zh.get(k)==zh[a["key"]]}
        assert visible&equivalent,("unseen cast label",a["key"])
    assert {7,11,12}<={w["Foreground"] for p in points[1:4] for w in p["words"]}
    closed=[e for e in run["list_events"] if e["Kind"]=="memory-list-closed"]
    assert len(closed)==1
    close=closed[0]["Step"]
    ready=next(e["Step"] for e in run["list_events"] if e["Kind"]=="footer-render-return" and e["Step"]>close)
    waiting=[f for f in run["frames"] if close<=f["step"]<ready]
    assert waiting and all(f["held"] for f in waiting)
    images=[]
    for point in points[1:]:
        panel=Image.new("RGB",(1280,420),"#202020");draw=ImageDraw.Draw(panel)
        for i,lang in enumerate(("en","zh")):
            f=next(f for f in runs[lang]["frames"] if f["step"]==point["step"])
            assert not f["held"]
            panel.paste(Image.open(output/(lang+"-r4")/f["File"]).convert("RGB"),(i*640,20))
            draw.text((i*640+4,2),point["label"]+" / "+lang,fill="white")
        file=output/("review-"+point["label"]+".png");assert not file.exists();panel.save(file)
        images.append(dict(path=file.name,sha256=sha(file)))
    write(output/"visibility-review.json",dict(points=points,images=images,source_rows=len(data["rows"]),
        close_step=close,footer_ready=ready,held_return_frames=len(waiting),visible_keys=sorted(visible),
        limits="五個穩定截點皆須顯示，取消後與原戰鬥畫面相同；不以曾觸發、永久保留前畫面或單張圖證明完整施法。"))


def evidence(root,output):
    gpu,regression=[read(output/n) for n in ("gpu-check-final.json","bar-gpu-check-final.json")]
    for r in (gpu,regression):
        assert r["all_submitted_pixels_equal_expected"] and r["checker_sha256"]==sha(root/"tools/ui_list_live_check.py")
    assert gpu["original_checkpoints_equal"]==5 and regression["original_checkpoints_equal"]==9
    assert read(output/"visibility-review.json")["source_rows"]==33
    assert len(read(output/"guards.json")["cases"])==8 and read(output/"guards.json")["tool_sha256"]==sha(Path(__file__))
    title=read(output/"cast-title-check.json")
    assert title["review_only"] and not title["errors"] and not title["term_warnings"]
    assert title["input_sha256"]==sha(output/"title.zh-TW.review.tsv")
    parent_path=root/"workplace/probe/bar-ui-20261024/evidence.json";parent=read(parent_path)
    sources=[parent_path,root/"workplace/input/dos/drkqueen/DQK.EXE",root/"workplace/probe/battle-text-20261024/control-arrival-r2/final.state"]
    for row in parent["sources"]:
        if row["path"].startswith("workplace/translation/"):
            p=root/row["path"];assert sha(p)==row["sha256"];sources.append(p)
    fixed=read(output/"run-r4.json")
    assert fixed["binary_sha256"]==sha(output/"programs-r3/ui-list-live")
    for name,h in fixed["source_files"].items():assert sha(output/"programs-r3"/name)==sha(root/"tools"/name)==h
    for name,h in fixed["input_files"].items():assert sha(output/"inputs-r3"/name)==h
    for phase in ("target-r1","joris-r1"):
        native_a,native_b=[read(output/(m+"-"+phase+"/receipt.json")) for m in ("observe","control")]
        assert native_a["checkpoints"]==native_b["checkpoints"]
        assert all(not c["file_writes"] and not c["unimplemented"] for c in native_a["checkpoints"])
        assert sha(output/("observe-"+phase+"/final.state"))==sha(output/("control-"+phase+"/final.state"))
    names=list(parent["tools"])+["cast_ui_inputs.py"]
    snapshots=output/"tool-snapshots";snapshots.mkdir()
    for name in names:shutil.copy2(root/"tools"/name,snapshots/name)
    def item(p):return dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p))
    write(output/"evidence.json",dict(draft=True,sources=[item(p) for p in sources],
        artifacts=[item(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name!="evidence.json"],
        tools={n:sha(root/"tools"/n) for n in names},gpu=gpu,regression=regression,
        docker_images={**parent["docker_images"],"fonttools":"sha256:6d849051db2e108262fa689160011dc64045cc402f61985548a525559d3a1cf3"},
        limits="正常施法清單、兩頁及取消返回；另有原版施法起始及下一角色的九個狀態，不作傷害、完整戰鬥、其他角色中文、正式入口或全遊戲中文化聲明。"))


def audit(root,output):
    r=read(output/"evidence.json")
    for row in r["sources"]+r["artifacts"]:
        p=root/row["path"];assert p.is_file() and p.stat().st_size==row["bytes"] and sha(p)==row["sha256"],p
        assert (p.stat().st_uid,p.stat().st_gid)==(1000,1000),p
    for n,h in r["tools"].items():assert sha(root/"tools"/n)==sha(output/"tool-snapshots"/n)==h
    assert {str(p.relative_to(root)) for p in output.rglob("*") if p.is_file() and p.name!="evidence.json"}=={x["path"] for x in r["artifacts"]}
    print("audited",len(r["artifacts"]),"artifacts",len(r["sources"]),"sources",len(r["tools"]),"tools")


if __name__=="__main__":
    command=sys.argv[1]
    if command=="native":native(Path(sys.argv[2]))
    elif command=="review":review(Path(sys.argv[2]))
    elif command in ("prepare","guards","glyph_inputs","evidence","audit"):globals()[command](*map(Path,sys.argv[2:4]))
    else:raise SystemExit("未知命令")
