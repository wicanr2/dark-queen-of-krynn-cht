"""其他角色的正常記憶法術清單；沿既有 DRAFT 資料，不改原版判定。"""
import base64
import copy
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from bar_ui_inputs import audit, write
from literal_catalog import catalog, digest, read, sha, windows
from text_catalog import write_tsv

BASE="battle-cast-20261024/inputs-r3"
SOURCE="party-cast-20261024/observe-r3/receipt.json"
GLYPHS="party-cast-20261024/glyphs-added-16.json"
JORIS_START=2950000000


def derive(probe,texts):
    old=read(probe/BASE/"inputs.json");config=copy.deepcopy(old)
    trace=read(probe/SOURCE);en,zh=catalog(texts/"en.tsv"),catalog(texts/"zh-TW.tsv")
    aliases={};records={};contexts=[];fields=[]
    menu_keys={m["Signature"] for m in trace["menus"] if [bytes.fromhex(b["SourceHex"]).decode() for b in m["Buttons"]]==["Cast","Exit"]}
    assert len(menu_keys)==2 and all(old["Menus"].get(k)=="grimoire" for k in menu_keys)
    for listing in trace["list_events"]:
        if listing["step"]<JORIS_START:continue
        assert listing["menu_snapshot"]["Signature"] in menu_keys
        c=dict(Pane="grimoire",RowFillPage=True,DescriptorSHA256=hashlib.sha256(bytes.fromhex(listing["descriptor_before_hex"])).hexdigest(),
               MenuSignature=listing["menu_snapshot"]["Signature"],Caller=dict(Seg=listing["stack"][1],Off=listing["stack"][0]))
        if c not in config["PaneLists"]:config["PaneLists"].append(c);contexts.append(c)
    for w in trace["wrappers"]:
        if w["step"]<JORIS_START:continue
        if w["caller"] not in old["RowCallers"] or w["format"]["text"]!="%s":continue
        source=w["vararg_1_candidate"];assert source["nul_terminated"]
        text=source["text"]
        if text.startswith("\t"):
            m=re.fullmatch(r"\t(.+?)(?: \([1-9][0-9]*\))?",text);assert m and "\t" not in m[1]
            start,name=1,m[1]
        else:
            assert text=="Special" or re.fullmatch(r"[1-9](?:st|nd|rd|th) Level",text)
            start,name=0,text
        candidates=[k for k,v in en.items() if v.casefold()==name.casefold() and k in zh]
        assert candidates and len({zh[k] for k in candidates})==1,name
        formal=min(candidates,key=lambda k:(en[k]!=name,not k.startswith("ui."),k))
        key="grimoire."+digest(name)[:20]
        aliases[key]=dict(key=key,source=name,formal_key=formal)
        record=records.setdefault(digest(text),dict(source=text,spans=[dict(Start=start,Length=len(name),Key=key)],colors=set()))
        assert record["source"]==text
        color=w["stack"][4]&255;assert color in (7,11,12);record["colors"].add(color)
    rows=[];new_rows=[];updated=[]
    for h,record in records.items():
        row=dict(Pane="grimoire",SHA256=h,Spans=record["spans"],Foregrounds=sorted(record["colors"]))
        previous=next((r for r in config["Rows"] if r["Pane"]=="grimoire" and r["SHA256"]==h),None)
        if previous:
            assert previous["Spans"]==row["Spans"]
            combined=sorted(set(previous["Foregrounds"])|record["colors"])
            if previous["Foregrounds"]!=combined:previous["Foregrounds"]=combined;updated.append(h)
        else:config["Rows"].append(row);new_rows.append(h)
        rows.append(dict(source=record["source"],row=row))
    assert len(rows)==25
    title=next(h for h in old["Headers"] if h["Key"]=="header.41b8dd827bde29bd2677")
    title_field=next(f for f in old["Fields"] if f["Pane"]=="grimoire" and f["Group"]=="header" and f["SHA256"]==title["SHA256"])
    calls=[]
    for c in trace["calls"]:
        if c["step"]<JORIS_START:continue
        if c["format"]["text"]!="%s" or not c["vararg_1_candidate"]["nul_terminated"]:continue
        if digest(c["vararg_1_candidate"]["text"])!=title["SHA256"]:continue
        w=trace["wrappers"][c["wrapper_index"]]
        assert (w["format"]["segment"],w["format"]["offset"])==(title["Segment"],title["Offset"])
        assert digest(w["format"]["text"])==title["SHA256"] and c["caller"]==title_field["Caller"]
        assert c["stack"][2:4]==[8004,8072]
        f=copy.deepcopy(title_field);f["RawY"],f["RawX"]=c["stack"][2:4]
        if f not in config["Fields"]:config["Fields"].append(f);fields.append(f)
        calls.append(c["step"])
    assert len(fields)==1 and len(calls)==1
    config["fine_windows"]=windows(trace)
    return config,dict(aliases=list(aliases.values()),rows=rows,fields=fields,contexts=contexts,
        added_rows=new_rows,updated_rows=updated,title_calls=calls)


def font_values(probe,texts,data):
    values=catalog(probe/BASE/"font-zh-TW.tsv");zh=catalog(texts/"zh-TW.tsv")
    values.update({a["key"]:zh[a["formal_key"]] for a in data["aliases"]})
    return values


def glyph_inputs(root,output):
    p=root/"workplace/probe";texts=root/"workplace/translation";_,data=derive(p,texts)
    old=read(p/BASE/"glyphs-16.json")
    missing=set("".join(font_values(p,texts,data).values()))-set("\r\n\t")-set(old["glyphs"])
    target=output/"glyph-source.tsv";assert not target.exists()
    write_tsv(target,["key","text"],(("glyph."+format(ord(c),"x"),c) for c in sorted(missing)))
    print("new glyphs",sorted(missing))


def merged(probe,texts,data):
    old=read(probe/BASE/"glyphs-16.json");new=read(probe/GLYPHS)
    assert all(old[k]==new[k] for k in ("size","height","font_sha256"))
    missing=set("".join(font_values(probe,texts,data).values()))-set("\r\n\t")-set(old["glyphs"])
    assert set(new["glyphs"])==missing
    for v in new["glyphs"].values():
        raw=base64.b64decode(v,validate=True);assert len(raw)==320 and not any(raw[256:])
    result=copy.deepcopy(old);result["glyphs"].update(new["glyphs"])
    return result


def native(output):
    a,b=[read(output/(m+"-r3/receipt.json")) for m in ("observe","control")]
    for k in ("source_commit","go_version","exe_sha256","state_sha256","request_sha256","probe_sha256","request","checkpoints"):
        assert a[k]==b[k],k
    assert len(a["checkpoints"])==11 and all(not a[k] for k in a if k.startswith("pending_"))
    assert a["probe_sha256"]==sha(output/"programs-r1/ui-context-probe") and a["request_sha256"]==sha(output/"request-r3.json")
    for c in a["checkpoints"]:
        assert not c["file_writes"] and not c["unimplemented"]
        for suffix in (".png",".idx"):assert sha(output/("observe-r3/"+c["label"]+suffix))==sha(output/("control-r3/"+c["label"]+suffix))
    assert sha(output/"observe-r3/final.state")==sha(output/"control-r3/final.state")
    write(output/"native-check-r2.json",dict(checkpoints=11,source_sha256=sha(output/"observe-r3/receipt.json")))


def generate(root,target):
    p=root/"workplace/probe";texts=root/"workplace/translation";base=p/BASE
    config,data=derive(p,texts)
    en,zh=catalog(base/"en.tsv"),catalog(base/"zh-TW.tsv");formal=catalog(texts/"zh-TW.tsv")
    for a in data["aliases"]:
        k=a["key"];value=formal[a["formal_key"]]
        if k in en:assert (en[k],zh[k])==(a["source"],value)
        en[k],zh[k]=a["source"],value
    shutil.copytree(base,target)
    proof=read(base/"provenance.json")
    proof["party_cast_extension"]=dict(base=BASE,base_files={f.name:sha(f) for f in base.iterdir()},data=data,
        source_path=SOURCE,source_sha256=sha(p/SOURCE),page_validation=dict(source_path=SOURCE,source_sha256=sha(p/SOURCE)),
        formal_files={n:sha(texts/n) for n in ("en.tsv","zh-TW.tsv","glossary.tsv","catalog.json","glossary-additions.tsv")},
        glyph_source_path=GLYPHS,glyph_source_sha256=sha(p/GLYPHS))
    for n,values in (("en.tsv",en),("zh-TW.tsv",zh),("font-zh-TW.tsv",font_values(p,texts,data))):write_tsv(target/n,["key","text"],values.items())
    write(target/"inputs.json",config);write(target/"provenance.json",proof);write(target/"glyphs-16.json",merged(p,texts,data))


def check_sources(inputs,config,provenance,en,zh,glyphs):
    root=inputs.parent.parent;proof=provenance["party_cast_extension"];base=root/BASE;texts=Path("/catalogs")
    assert proof["base"]==BASE and proof["source_path"]==SOURCE
    assert set(proof["base_files"])=={f.name for f in base.iterdir()}
    for n,h in proof["base_files"].items():assert Path(n).name==n and sha(base/n)==h
    assert sha(root/SOURCE)==proof["source_sha256"]
    assert proof["page_validation"]==dict(source_path=SOURCE,source_sha256=sha(root/SOURCE))
    for n,h in proof["formal_files"].items():assert sha(texts/n)==h
    expected,data=derive(root,texts)
    assert config==expected,"party cast config"
    assert proof["data"]==data
    old,parent=read(base/"inputs.json"),read(base/"provenance.json")
    assert {k:v for k,v in provenance.items() if k!="party_cast_extension"}==parent
    old_en,old_zh=catalog(base/"en.tsv"),catalog(base/"zh-TW.tsv");formal=catalog(texts/"zh-TW.tsv")
    assert en==dict(old_en,**{a["key"]:a["source"] for a in data["aliases"]})
    assert zh==dict(old_zh,**{a["key"]:formal[a["formal_key"]] for a in data["aliases"]}),"party cast translation"
    assert catalog(inputs/"font-zh-TW.tsv")==font_values(root,texts,data)
    assert proof["glyph_source_path"]==GLYPHS and sha(root/GLYPHS)==proof["glyph_source_sha256"]
    assert glyphs==merged(root,texts,data),"party cast glyph union"
    for n in set(proof["base_files"])-{"inputs.json","provenance.json","en.tsv","zh-TW.tsv","font-zh-TW.tsv","glyphs-16.json"}:
        assert (inputs/n).read_bytes()==(base/n).read_bytes(),n
    return base,old,parent,old_en,old_zh,read(base/"glyphs-16.json")


def prepare(root,output):
    assert read(output/"native-check-r2.json")["checkpoints"]==11
    generate(root,output/"inputs-r2")


def guards(root,output):
    source=output/"inputs-r2"
    def check(p):return check_sources(p,read(p/"inputs.json"),read(p/"provenance.json"),catalog(p/"en.tsv"),catalog(p/"zh-TW.tsv"),read(p/"glyphs-16.json"))
    check(source);cases=[]
    for name in ("position","row","context","old-field","translation","glyph"):
        with tempfile.TemporaryDirectory(dir=output,prefix="guard-") as temporary:
            p=Path(temporary);shutil.copytree(source,p,dirs_exist_ok=True);c=read(p/"inputs.json")
            if name=="translation":
                z=catalog(p/"zh-TW.tsv");z[c["Rows"][-1]["Spans"][0]["Key"]]+="x";write_tsv(p/"zh-TW.tsv",["key","text"],z.items())
            elif name=="glyph":
                g=read(p/"glyphs-16.json");g["glyphs"].pop(next(iter(g["glyphs"])));write(p/"glyphs-16.json",g)
            else:
                if name=="position":c["Fields"][-1]["RawX"]+=1
                elif name=="row":c["Rows"][-1]["Spans"][0]["Start"]+=1
                elif name=="context":c["PaneLists"][-1]["DescriptorSHA256"]="0"*64
                else:c["Fields"][0]["RawX"]+=1
                write(p/"inputs.json",c)
            try:check(p)
            except AssertionError as error:assert str(error)==({"translation":"party cast translation","glyph":"party cast glyph union"}.get(name,"party cast config")),(name,error)
            else:raise AssertionError(name)
            cases.append(name)
    with tempfile.TemporaryDirectory(dir=output,prefix="rebuild-") as temporary:
        p=Path(temporary)/"inputs";generate(root,p)
        assert {f.name for f in p.iterdir()}=={f.name for f in source.iterdir()}
        for f in source.iterdir():assert f.read_bytes()==(p/f.name).read_bytes(),f.name
        glyph=Path(temporary)/"glyphs.json"
        subprocess.run([sys.executable,str(Path(__file__).with_name("menu_glyphs.py")),"/font/jf-openhuninn-2.1.ttf",str(output/"glyph-source.tsv"),str(glyph),"16"],check=True,capture_output=True,text=True,timeout=15)
        assert glyph.read_bytes()==(output/"glyphs-added-16.json").read_bytes()
    write(output/"guards.json",dict(cases=cases,rebuilt_files=len(list(source.iterdir())),tool_sha256=sha(Path(__file__))))


def review(output):
    from PIL import Image,ImageDraw
    en,zh=catalog(output/"inputs-r2/en.tsv"),catalog(output/"inputs-r2/zh-TW.tsv")
    data=read(output/"inputs-r2/provenance.json")["party_cast_extension"]["data"]
    runs={lang:read(output/(lang+"-r2/receipt.json")) for lang in ("en","zh")}
    run=runs["zh"]
    accepted={e["detail"]["source_sha256"] for e in run["list_events"] if e["Kind"]=="row-before-glyph"}
    assert {r["row"]["SHA256"] for r in data["rows"]}<=accepted
    points=[]
    for cp in run["checkpoints"]:
        if not cp["label"].startswith("joris-"):continue
        i=next(i for i,f in enumerate(run["frames"]) if f["step"]==cp["step"])
        frame,state=run["frames"][i],run["list_frames"][i]
        assert not frame["held"],("stable checkpoint held",cp["label"])
        points.append(dict(label=cp["label"],step=cp["step"],frame=frame["File"],sha256=frame["SHA256"],words=state["words"]))
    assert len(points)==5 and points[0]["words"]==points[-1]["words"]
    assert points[0]["sha256"]==points[-1]["sha256"],"cancel must restore battle"
    visible={w["Key"] for p in points[1:4] for w in p["words"]}
    for a in data["aliases"]:
        equivalent={k for k,v in en.items() if v==en[a["key"]] and zh.get(k)==zh[a["key"]]}
        assert visible&equivalent,("unseen party cast label",a["key"])
    field=data["fields"][0]
    assert all(any((w["Key"],w["X"],w["Y"])==(field["Key"],144,8) for w in p["words"]) for p in points[1:4])
    assert {7,11,12}<={w["Foreground"] for p in points[1:4] for w in p["words"]}
    closed=[e for e in run["list_events"] if e["Kind"]=="memory-list-closed" and e["Step"]>=JORIS_START]
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
            panel.paste(Image.open(output/(lang+"-r2")/f["File"]).convert("RGB"),(i*640,20))
            draw.text((i*640+4,2),point["label"]+" / "+lang,fill="white")
        file=output/("review-"+point["label"]+".png");assert not file.exists();panel.save(file)
        images.append(dict(path=file.name,sha256=sha(file)))
    write(output/"visibility-review.json",dict(points=points,images=images,source_rows=len(data["rows"]),all_checkpoints=len(run["checkpoints"]),
        close_step=close,footer_ready=ready,held_return_frames=len(waiting),visible_keys=sorted(visible),
        limits="Joris 的五個穩定截點、清單翻頁與取消返回；不證明完整施法、傷害或戰鬥結束。"))


def evidence(root,output):
    gpu,regression=[read(output/n) for n in ("gpu-check-final.json","parent-gpu-check-final.json")]
    for report in (gpu,regression):
        assert report["all_submitted_pixels_equal_expected"] and report["checker_sha256"]==sha(root/"tools/ui_list_live_check.py")
    assert gpu["original_checkpoints_equal"]==11 and regression["original_checkpoints_equal"]==5
    assert read(output/"visibility-review.json")["source_rows"]==25
    guards=read(output/"guards.json")
    assert len(guards["cases"])==6 and guards["rebuilt_files"]==15 and guards["tool_sha256"]==sha(Path(__file__))
    parent_path=root/"workplace/probe/battle-cast-20261024/evidence.json";parent=read(parent_path)
    sources=[parent_path,root/"workplace/input/dos/drkqueen/DQK.EXE",
        root/"workplace/probe/battle-cast-20261024/control-cast-r2/final.state"]
    for row in parent["sources"]:
        if row["path"].startswith("workplace/translation/"):
            p=root/row["path"];assert sha(p)==row["sha256"];sources.append(p)
    fixed=read(output/"run-r2.json")
    assert fixed["binary_sha256"]==sha(output/"programs-r1/ui-list-live")=="1294f9cbab3d68137210c4f0d691416795c8d2857e68fdbde8db3e1d34be1c7c"
    for name,h in fixed["source_files"].items():assert sha(output/"programs-r1"/name)==sha(root/"tools"/name)==h
    for name,h in fixed["input_files"].items():assert sha(output/"inputs-r2"/name)==h
    names=list(parent["tools"])+["party_cast_inputs.py"]
    snapshots=output/"tool-snapshots";snapshots.mkdir()
    for name in names:shutil.copy2(root/"tools"/name,snapshots/name)
    def item(p):return dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p))
    write(output/"evidence.json",dict(draft=True,sources=[item(p) for p in sources],
        artifacts=[item(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name!="evidence.json"],
        tools={n:sha(root/"tools"/n) for n in names},gpu=gpu,regression=regression,docker_images=parent["docker_images"],
        regression_method="同一未改動 GUI binary；以前輪 Lendura 實際 GPU 收據及原輸入重驗。子批次另驗舊欄位、列、譯文與 glyph 不變；不冒稱重新執行 Lendura GUI。",
        limits="Joris 正常記憶法術清單的 DRAFT 呈現；未驗完整施法、傷害、戰鬥結束、正式入口或全遊戲中文化。"))


if __name__=="__main__":
    command=sys.argv[1]
    if command=="native":native(Path(sys.argv[2]))
    elif command=="review":review(Path(sys.argv[2]))
    elif command in ("glyph_inputs","prepare","guards","evidence","audit"):globals()[command](*map(Path,sys.argv[2:4]))
    else:raise SystemExit("未知命令")
