"""從正常戰鬥來源衍生獨立右側欄位，不改原版規則。"""
import base64
import copy
import csv
from pathlib import Path
import re
import shutil
import sys
import tempfile

from bar_ui_inputs import audit,write
from literal_catalog import catalog,digest,read,sha,windows
from text_catalog import write_tsv

BASE="party-cast-20261024/inputs-r2"
SOURCE="combat-hud-20261024/observe-r3/receipt.json"
GLYPHS="combat-hud-20261024/glyphs-added-16.json"


def derive(probe,texts):
    config=copy.deepcopy(read(probe/BASE/"inputs.json"));trace=read(probe/SOURCE)
    en,zh=catalog(texts/"en.tsv"),catalog(texts/"zh-TW.tsv")
    terms=list(csv.DictReader((texts/"glossary.tsv").open(),delimiter="\t"))
    aliases={};bindings=[];records=[];fields=[]
    def term(text):
        exact=[k for k,v in en.items() if v.casefold()==text.casefold() and k in zh]
        templates=[k for k,v in en.items() if v.count("%s")==1 and v.replace("%s","")==text and k in zh]
        if exact:
            assert len({zh[k] for k in exact})==1
            key=min(exact,key=lambda k:(en[k]!=text,not k.startswith("ui."),k));value=zh[key];origin=dict(formal_key=key)
        elif templates:
            assert len(templates)==1;key=templates[0];assert zh[key].count("%s")==1
            value=zh[key].replace("%s","");origin=dict(template_key=key,argument="")
        else:
            rows=[r for r in terms if r["en"].casefold()==text.casefold()]
            assert rows and len({r["zh"] for r in rows})==1,text
            row=rows[0];assert row["project"]=="death_knight_of_krynn"
            value=row["zh"];origin=dict(glossary=row)
        key="hud."+digest(text)[:20];aliases[key]=dict(key=key,source=text,translation=value,origin=origin)
        return key
    for i,p in enumerate(trace["paragraphs"]):
        source=p["source"]["text"]
        if source==" ":continue
        weapon=p["caller"]==dict(Seg=0x088e,Off=0x097e)
        assert weapon or (p["caller"],p["native_box"]) in [(dict(Seg=0x088e,Off=0x15e1),[184,88,312,176]),(dict(Seg=0x22f4,Off=0x048f),[184,104,312,136])]
        assert p["source"]["nul_terminated"] and [p[k] for k in ("foreground","background","clear")]==[7,0,1]
        root=re.sub(r"(?: \+[1-9][0-9]*)? *$","",source) if weapon else source
        key=term(root);x,y,right,bottom=p["native_box"]
        assert x==184 and right==312
        rect=[x,y,len(root)*8,8]
        if rect[2]>right-x:
            assert weapon and source==root+" ";rect=[x,y,right-x,bottom-y]
        span=dict(Start=0,Length=len(root),Key=key,Rect=rect)
        binding=dict(SHA256=digest(source),Caller=p["caller"],NativeBox=p["native_box"],Foreground=7,Background=0,Clear=1,Spans=[span])
        if p["native_box"]==[184,88,312,176]:binding["HideFooter"]=True
        if binding not in bindings:bindings.append(binding)
        chars=[c for c in trace["calls"] if c["paragraph_index"]==i and c["format"]["text"]=="%c"]
        assert chars and all(c["caller"]==dict(Seg=0xb72,Off=0x2e3) for c in chars)
        assert "".join(chr(c["stack"][7]&255) for c in chars)==source
        assert p["step"]<p["first_glyph"]==chars[0]["first_glyph"]<p["return_step"]
        assert all(p["step"]<c["step"]<c["first_glyph"]<c["return_step"]<p["return_step"] for c in chars)
        pages={page for c in chars for page in c["video_pages"]};assert len(pages)==1
        records.append(dict(index=i,step=p["step"],first_glyph=p["first_glyph"],return_step=p["return_step"],source=source,binding=binding,paint_page=int(next(iter(pages)))))
    assert len(bindings)==6 and len(records)==12
    for c in trace["calls"]:
        if c["format"]["text"]!="%s" or c["vararg_1_candidate"]["text"]!="BLUE DRAGON":continue
        w=trace["wrappers"][c["wrapper_index"]];source=c["vararg_1_candidate"]["text"];key=term(source)
        assert w["caller"]==dict(Seg=0x088e,Off=0x16fb) and w["format"]["text"]=="%s"
        assert [(w["stack"][n]&255)*8 for n in (2,3)]==[184,96] and c["stack"][2:5]==[8048,8092,0x82]
        f=dict(Pane="callsite",Group="body",Key=key,Start=0,Length=len(source),SHA256=digest(source),FormatSHA256=digest("%s"),
            Caller=c["caller"],UpperCaller=w["caller"],UpperFormatSHA256=digest("%s"),UpperNative=[184,96],RawX=8092,RawY=8048,Color=0x82,BackgroundOverride=23,MenuSignature="")
        if f not in config["Fields"]:config["Fields"].append(f)
        fields.append(dict(call_step=c["step"],source=source,binding=f))
    assert len(fields)==1
    parent_en,parent_zh=catalog(probe/BASE/"en.tsv"),catalog(probe/BASE/"zh-TW.tsv")
    added_menus=[]
    for menu in trace["menus"]:
        if menu["Signature"] in config["Menus"]:continue
        buttons=menu["Buttons"]
        assert menu["Count"]==7 and len(buttons)==6
        assert [bytes.fromhex(b["SourceHex"]).decode() for b in buttons]==["Next","Prev","Manual","Target","Center","Exit"]
        config["Menus"][menu["Signature"]]="aim";added_menus.append(menu)
        for button in buttons:
            source=bytes.fromhex(button["SourceHex"]).decode()
            choices=[k for k,v in parent_en.items() if v==source and k in parent_zh]
            if choices:
                assert len({parent_zh[k] for k in choices})==1;key=min(choices)
            else:key=term(source)
            f=dict(Pane="menu",Group="footer",Key=key,Start=0,Length=len(source),SHA256=button["SHA256"],FormatSHA256=button["SHA256"],
                Caller=dict(Seg=0xceb,Off=0x1be),RawX=button["RawX"] if button["RawX"]<400 else (button["RawX"]-8000)*2,RawY=(button["RawY"] if button["RawY"]<400 else (button["RawY"]-8000)*2)+1,MenuSignature=menu["Signature"])
            assert f not in config["Fields"];config["Fields"].append(f);fields.append(dict(button_index=button["Index"],source=source,binding=f))
    assert len(added_menus)==1
    for c in trace["calls"]:
        if c["format"]["text"]!="%s" or not c["vararg_1_candidate"]["text"].startswith("Spell:"):continue
        source=c["vararg_1_candidate"]["text"];argument=source[len("Spell:"):]
        templates=[k for k,v in en.items() if v=="Spell:%s"];args=[k for k,v in en.items() if v==argument and k in zh]
        assert len(templates)==1 and args and len({zh[k] for k in args})==1
        template_key=templates[0];argument_key=min(args);key="hud."+digest(source)[:20]
        assert en[template_key].replace("%s",en[argument_key])==source and zh[template_key].count("%s")==1
        aliases[key]=dict(key=key,source=source,translation=zh[template_key].replace("%s",zh[argument_key]),origin=dict(template_key=template_key,argument_key=argument_key))
        w=trace["wrappers"][c["wrapper_index"]]
        assert w["caller"]==dict(Seg=0x2c4a,Off=0x4630) and w["format"]["text"]==source and c["stack"][2:5]==[8089,8004,0x8f]
        f=dict(Pane="callsite",Group="footer",Key=key,Start=0,Length=len(source),SHA256=digest(source),FormatSHA256=digest("%s"),
            Caller=c["caller"],UpperCaller=w["caller"],UpperNative=[0,184],Color=0x8f,RawX=8004,RawY=8089,MenuSignature="")
        assert f not in config["Fields"];config["Fields"].append(f);fields.append(dict(call_step=c["step"],source=source,binding=f))
    assert len(fields)==8 and len(aliases)==9
    config["HUDParagraphs"]=bindings;config["fine_windows"]=windows(trace)
    return config,dict(aliases=list(aliases.values()),bindings=bindings,records=records,fields=fields,menus=added_menus)


def font_values(probe,data):
    values=catalog(probe/BASE/"font-zh-TW.tsv");values.update({a["key"]:a["translation"] for a in data["aliases"]});return values


def glyph_inputs(root,output):
    p=root/"workplace/probe";_,data=derive(p,root/"workplace/translation")
    old=read(p/BASE/"glyphs-16.json")
    missing=set("".join(font_values(p,data).values()))-set("\r\n\t")-set(old["glyphs"])
    target=output/"glyph-source.tsv";assert not target.exists()
    write_tsv(target,["key","text"],(("glyph."+format(ord(c),"x"),c) for c in sorted(missing)));print("new glyphs",sorted(missing))


def merged(probe,data):
    old=read(probe/BASE/"glyphs-16.json");new=read(probe/GLYPHS)
    assert all(old[k]==new[k] for k in ("size","height","font_sha256"))
    missing=set("".join(font_values(probe,data).values()))-set("\r\n\t")-set(old["glyphs"])
    assert set(new["glyphs"])==missing
    for value in new["glyphs"].values():
        raw=base64.b64decode(value,validate=True);assert len(raw)==320 and not any(raw[256:])
    result=copy.deepcopy(old);result["glyphs"].update(new["glyphs"]);return result


def native(output):
    a,b=[read(output/(mode+"-r3/receipt.json")) for mode in ("observe","control")]
    for k in ("source_commit","go_version","exe_sha256","state_sha256","request_sha256","probe_sha256","request","checkpoints"):assert a[k]==b[k],k
    assert len(a["checkpoints"])==16 and all(not a[k] for k in a if k.startswith("pending_"))
    assert a["probe_sha256"]==sha(output/"programs-r1/ui-context-probe") and a["request_sha256"]==sha(output/"request-r3.json")
    for c in a["checkpoints"]:
        assert not c["file_writes"] and not c["unimplemented"]
        for suffix in (".png",".idx"):assert sha(output/("observe-r3/"+c["label"]+suffix))==sha(output/("control-r3/"+c["label"]+suffix))
    assert sha(output/"observe-r3/final.state")==sha(output/"control-r3/final.state")
    write(output/"native-check-r2.json",dict(checkpoints=16,source_sha256=sha(output/"observe-r3/receipt.json")))


def generate(root,target):
    p=root/"workplace/probe";texts=root/"workplace/translation";base=p/BASE
    config,data=derive(p,texts);en,zh=catalog(base/"en.tsv"),catalog(base/"zh-TW.tsv")
    for a in data["aliases"]:
        assert a["key"] not in en;en[a["key"]],zh[a["key"]]=a["source"],a["translation"]
    shutil.copytree(base,target);proof=read(base/"provenance.json")
    proof["hud_extension"]=dict(base=BASE,base_files={f.name:sha(f) for f in base.iterdir()},data=data,source_path=SOURCE,source_sha256=sha(p/SOURCE),
        page_validation=dict(source_path=SOURCE,source_sha256=sha(p/SOURCE)),glyph_source_path=GLYPHS,glyph_source_sha256=sha(p/GLYPHS),
        formal_files={n:sha(texts/n) for n in ("en.tsv","zh-TW.tsv","glossary.tsv","catalog.json","glossary-additions.tsv")})
    for n,v in (("en.tsv",en),("zh-TW.tsv",zh),("font-zh-TW.tsv",font_values(p,data))):write_tsv(target/n,["key","text"],v.items())
    write(target/"inputs.json",config);write(target/"provenance.json",proof);write(target/"glyphs-16.json",merged(p,data))


def check_sources(inputs,config,proof,en,zh,glyphs):
    root=inputs.parent.parent;item=proof["hud_extension"];base=root/BASE;texts=Path("/catalogs")
    assert item["base"]==BASE and item["source_path"]==SOURCE and sha(root/SOURCE)==item["source_sha256"]
    assert item["page_validation"]==dict(source_path=SOURCE,source_sha256=sha(root/SOURCE))
    assert set(item["base_files"])=={f.name for f in base.iterdir()}
    for n,h in item["base_files"].items():assert Path(n).name==n and sha(base/n)==h
    for n,h in item["formal_files"].items():assert sha(texts/n)==h
    expected,data=derive(root,texts);assert config==expected,"hud config";assert item["data"]==data
    parent=read(base/"provenance.json");assert {k:v for k,v in proof.items() if k!="hud_extension"}==parent
    old_en,old_zh=catalog(base/"en.tsv"),catalog(base/"zh-TW.tsv")
    assert en==dict(old_en,**{a["key"]:a["source"] for a in data["aliases"]})
    assert zh==dict(old_zh,**{a["key"]:a["translation"] for a in data["aliases"]}),"hud translation"
    assert catalog(inputs/"font-zh-TW.tsv")==font_values(root,data)
    assert item["glyph_source_path"]==GLYPHS and sha(root/GLYPHS)==item["glyph_source_sha256"]
    assert glyphs==merged(root,data),"hud glyph union"
    for n in set(item["base_files"])-{"inputs.json","provenance.json","en.tsv","zh-TW.tsv","font-zh-TW.tsv","glyphs-16.json"}:assert (inputs/n).read_bytes()==(base/n).read_bytes()
    return base,read(base/"inputs.json"),parent,old_en,old_zh,read(base/"glyphs-16.json")


def prepare(root,output):
    assert read(output/"native-check-r2.json")["checkpoints"]==16;generate(root,output/"inputs-r4")


def guards(root,output):
    source=output/"inputs-r4"
    def check(p):return check_sources(p,read(p/"inputs.json"),read(p/"provenance.json"),catalog(p/"en.tsv"),catalog(p/"zh-TW.tsv"),read(p/"glyphs-16.json"))
    check(source);cases=[]
    for name in ("caller","box","height","prefix","footer","menu-coordinate","old-field","translation","glyph"):
        with tempfile.TemporaryDirectory(dir=output,prefix="guard-") as temporary:
            p=Path(temporary);shutil.copytree(source,p,dirs_exist_ok=True);c=read(p/"inputs.json");b=c["HUDParagraphs"][0]
            if name=="translation":
                z=catalog(p/"zh-TW.tsv");z[b["Spans"][0]["Key"]]+="x";write_tsv(p/"zh-TW.tsv",["key","text"],z.items())
            elif name=="glyph":
                g=read(p/"glyphs-16.json");g["glyphs"].pop(next(iter(g["glyphs"])));write(p/"glyphs-16.json",g)
            else:
                if name=="caller":b["Caller"]["Off"]+=1
                elif name=="box":b["NativeBox"][0]+=1
                elif name=="height":next(b for b in c["HUDParagraphs"] if b["Spans"][0]["Rect"][3]>8)["Spans"][0]["Rect"][3]=8
                elif name=="prefix":b["Spans"][0]["Length"]+=1
                elif name=="footer":c["HUDParagraphs"][1]["HideFooter"]=False
                elif name=="menu-coordinate":c["Fields"][-2]["RawX"]+=1
                else:c["Fields"][0]["RawX"]+=1
                write(p/"inputs.json",c)
            try:check(p)
            except AssertionError as error:assert str(error)=={"translation":"hud translation","glyph":"hud glyph union"}.get(name,"hud config"),(name,error)
            else:raise AssertionError(name)
            cases.append(name)
    with tempfile.TemporaryDirectory(dir=output,prefix="rebuild-") as temporary:
        p=Path(temporary)/"inputs";generate(root,p)
        assert {f.name for f in p.iterdir()}=={f.name for f in source.iterdir()}
        for f in source.iterdir():assert f.read_bytes()==(p/f.name).read_bytes(),f.name
    write(output/"guards.json",dict(cases=cases,rebuilt_files=len(list(source.iterdir())),tool_sha256=sha(Path(__file__))))


def review(output):
    from PIL import Image,ImageDraw
    runs={lang:read(output/(lang+"-r4/receipt.json")) for lang in ("en","zh")};run=runs["zh"]
    proof=read(output/"inputs-r4/provenance.json")["hud_extension"]
    points=[]
    for cp in run["checkpoints"]:
        i=next(i for i,f in enumerate(run["frames"]) if f["step"]==cp["step"])
        frame,state=run["frames"][i],run["list_frames"][i]
        assert not frame["held"],("stable checkpoint held",cp["label"])
        points.append(dict(label=cp["label"],step=cp["step"],frame=frame["File"],sha256=frame["SHA256"],words=state["words"]))
    assert len(points)==16
    mace=next(a["key"] for a in proof["data"]["aliases"] if a["source"]=="Mace of Disruption")
    assert any(w["Key"]==mace and w.get("Height")==24 for p in points if p["label"]=="combat-quick-wait" for w in p["words"])
    assert not any(w["Key"]==mace for w in points[-1]["words"])
    target_buttons=[f for f in read(output/"inputs-r4/inputs.json")["Fields"] if f["Pane"]=="menu" and f["MenuSignature"]==proof["data"]["menus"][0]["Signature"]]
    assert len(target_buttons)==6 and {w["Key"] for w in points[-1]["words"] if w.get("Button")}=={f["Key"] for f in target_buttons}
    before=next(p for p in points if p["label"]=="joris-before-cast");after=next(p for p in points if p["label"]=="joris-cancel")
    assert before["words"]==after["words"] and before["sha256"]==after["sha256"]
    for label in ("begins-casting","attacks-and-misses"):
        point=next(p for p in points if p["label"]==label)
        assert not any(w["Group"]=="footer" for w in point["words"])
    visible={w["Key"] for f,s in zip(run["frames"],run["list_frames"]) if not f["held"] for w in s["words"] or []}
    assert {a["key"] for a in proof["data"]["aliases"]}<=visible
    entries={e["Step"]:e for e in run["list_events"] if e["Kind"]=="hud-before-glyph"}
    intervals=[]
    for record in proof["data"]["records"]:
        event=entries[record["step"]];assert event["first_glyph"]==record["first_glyph"]
        frames=[f for f in run["frames"] if record["step"]<=f["step"]<record["return_step"]]
        assert frames and all(f["held"] for f in frames)
        intervals.append(dict(entry=record["step"],first_glyph=record["first_glyph"],return_step=record["return_step"],held_samples=len(frames)))
    numbers=[]
    for point in (next(p for p in points if p["label"]=="begins-casting"),before,after):
        crop=[]
        for lang in ("en","zh"):
            f=next(f for f in runs[lang]["frames"] if f["step"]==point["step"])
            crop.append(Image.open(output/(lang+"-r4")/f["File"]).convert("RGB").crop((544,112,592,128)).tobytes())
        assert crop[0]==crop[1];numbers.append(point["label"])
    images=[]
    for label in ("begins-casting","joris-cancel","attacks-and-misses","combat-quick-wait","mace-guard-next-actor"):
        point=next(p for p in points if p["label"]==label)
        panel=Image.new("RGB",(1280,420),"#202020");draw=ImageDraw.Draw(panel)
        for i,lang in enumerate(("en","zh")):
            f=next(f for f in runs[lang]["frames"] if f["step"]==point["step"])
            assert not f["held"]
            panel.paste(Image.open(output/(lang+"-r4")/f["File"]).convert("RGB"),(i*640,20));draw.text((i*640+4,2),label+" / "+lang,fill="white")
        file=output/("review-r4-"+label+".png");assert not file.exists();panel.save(file);images.append(dict(path=file.name,sha256=sha(file)))
    write(output/"visibility-review-r2.json",dict(points=points,images=images,intervals=intervals,visible_aliases=sorted(visible&{a["key"] for a in proof["data"]["aliases"]}),
        original_bonus_crops_equal=numbers,limits="正常兩種武器、施法起始、一次攻擊及未命中；沒有傷害、完整施法或戰鬥勝利聲明。"))


def evidence(root,output):
    gpu,regression=[read(output/n) for n in ("gpu-check-final-r2.json","parent-gpu-check-final-r2.json")]
    for report in (gpu,regression):
        assert report["all_submitted_pixels_equal_expected"] and report["checker_sha256"]==sha(root/"tools/ui_list_live_check.py")
    assert gpu["original_checkpoints_equal"]==16 and regression["original_checkpoints_equal"]==11
    review_report=read(output/"visibility-review-r2.json")
    assert len(review_report["visible_aliases"])==9 and len(review_report["intervals"])==12
    assert read(output/"guards.json")["tool_sha256"]==sha(Path(__file__))
    assert len(read(output/"guards.json")["cases"])==9
    parent_path=root/"workplace/probe/party-cast-20261024/evidence.json";parent=read(parent_path)
    sources=[parent_path,root/"workplace/input/dos/drkqueen/DQK.EXE",root/"workplace/probe/battle-cast-20261024/control-cast-r2/final.state",root/"workplace/ida/dqk.i64"]
    for row in parent["sources"]:
        if row["path"].startswith("workplace/translation/"):
            p=root/row["path"];assert sha(p)==row["sha256"];sources.append(p)
    fixed=read(output/"run-r4.json");assert fixed["binary_sha256"]==sha(output/"programs-r4/ui-list-live")
    for name,h in fixed["source_files"].items():assert sha(output/"programs-r4"/name)==sha(root/"tools"/name)==h
    for name,h in fixed["input_files"].items():assert sha(output/"inputs-r4"/name)==h
    assert read(output/"binary-rebuild-r2.json")["binary_sha256"]==fixed["binary_sha256"]
    ida=read(output/"ida-query-r1/result.json");assert ida["ida_version"]=="9.4" and ida["sha256"]==sha(root/"workplace/input/dos/drkqueen/DQK.EXE")
    assert ida["functions"][0]["name"]=="sub_1A8A3" and ida["functions"][0]["start"]==0x1a8a3
    names=list(dict.fromkeys(list(parent["tools"])+["combat_hud_inputs.py","ida_inspect.py"]))
    snapshots=output/"tool-snapshots";snapshots.mkdir()
    for name in names:shutil.copy2(root/"tools"/name,snapshots/name)
    def item(p):return dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p))
    write(output/"evidence.json",dict(draft=True,sources=[item(p) for p in sources],
        artifacts=[item(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name!="evidence.json"],tools={n:sha(root/"tools"/n) for n in names},gpu=gpu,regression=regression,
        docker_images={**parent["docker_images"],"ida":"sha256:4ac62de83339c215bab10e455cee3a22d9c6efed9fd0d8ed0f068327b83a06ab"},
        limits="正常兩種武器、開始施法、一次攻擊與未命中；舊清單用同一新二進位重跑，未驗傷害、完整施法、勝利或正式入口。"))


if __name__=="__main__":
    command=sys.argv[1]
    if command=="native":native(Path(sys.argv[2]))
    elif command=="review":review(Path(sys.argv[2]))
    elif command in ("glyph_inputs","prepare","guards","evidence","audit"):globals()[command](*map(Path,sys.argv[2:4]))
    else:raise SystemExit("未知命令")
