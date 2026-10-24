"""以原版施法續行收據衍生傷害模板及欄位，僅供 DRAFT。"""
import copy
import csv
import base64
from pathlib import Path
import re
import shutil
import sys
import tempfile

from bar_ui_inputs import audit, write
from literal_catalog import catalog, digest, read, sha, windows
from text_catalog import write_tsv

BASE="combat-hud-20261024/inputs-r4"
SOURCE="combat-effects-20261024/observe-r2/receipt.json"
TARGET="4d5975c1c597e7c7c0a0cbf4ae62812b319a94315944583c850c1437d3e89a71"
GLYPHS="combat-effects-20261024/glyphs-added-16.json"
FORMAL=("en.tsv","zh-TW.tsv","glossary.tsv","catalog.json","glossary-additions.tsv")


def integer(source,pattern):
    assert pattern.count("%d")==1 and pattern.count("%")==1
    prefix,suffix=pattern.split("%d")
    match=re.fullmatch(re.escape(prefix)+r"(-?(?:0|[1-9][0-9]*))"+re.escape(suffix),source)
    if not match:return None
    value=int(match[1])
    return value if -(2**31)<=value<2**31 and str(value)==match[1] else None


def hud_records(trace,bindings,en):
    result=[]
    for i,p in enumerate(trace["paragraphs"]):
        source=p["source"]["text"]
        matches=[]
        for binding in bindings:
            if binding["Caller"]!=p["caller"] or binding["NativeBox"]!=p["native_box"]:continue
            if [binding[k] for k in ("Foreground","Background","Clear")]!=[p[k] for k in ("foreground","background","clear")]:continue
            key=binding.get("IntegerTemplateKey")
            value=integer(source,en[key]) if key else None
            if (key and value is not None) or (not key and binding["SHA256"]==digest(source)):matches.append((binding,value))
        if not matches:continue
        assert len(matches)==1
        binding,value=matches[0]
        chars=[c for c in trace["calls"] if c["paragraph_index"]==i and c["format"]["text"]=="%c"]
        assert "".join(chr(c["stack"][7]&255) for c in chars)==source
        assert p["source"]["nul_terminated"] and bytes.fromhex(p["source"]["hex"]).decode()==source
        assert p["step"]<p["first_glyph"]==chars[0]["first_glyph"]<p["return_step"]
        pages={page for c in chars for page in c["video_pages"]};assert len(pages)==1
        result.append(dict(index=i,step=p["step"],first_glyph=p["first_glyph"],return_step=p["return_step"],source=source,binding=binding,number=value,paint_page=int(next(iter(pages)))))
    return result


def derive(probe,texts):
    base=probe/BASE;config=copy.deepcopy(read(base/"inputs.json"));trace=read(probe/SOURCE)
    en,zh=catalog(texts/"en.tsv"),catalog(texts/"zh-TW.tsv")
    aliases=[];bindings=[];fields=[];menus=[]
    def alias(source,translation,origin,prefix="hud."):
        key=prefix+digest(source)[:20]
        assert key not in catalog(base/"en.tsv")
        aliases.append(dict(key=key,source=source,translation=translation,origin=origin));return key
    parts=["ui.0047c0cbccc6f94c1ac8","ui.f5e1d63728c2e2d27737","ui.d4d4cdcd08b7f8cdfb44"]
    assert [en[k] for k in parts]==["takes %d%s"," points of damage ","%sfrom Magic"]
    pattern=en[parts[0]].replace("%s",en[parts[2]].replace("%s",en[parts[1]]))
    translated=zh[parts[0]].replace("%s",zh[parts[2]].replace("%s",zh[parts[1]]))
    assert translated=="受到%d點傷害（魔法）"
    key=alias(pattern,translated,dict(formal_keys=parts),"hud-format.")
    binding=dict(SHA256=digest(pattern),Caller=dict(Seg=0x88e,Off=0x15e1),NativeBox=[184,88,312,176],Foreground=7,Background=0,Clear=1,
        IntegerTemplateKey=key,KeepFooterSignature=TARGET,Spans=[dict(Start=0,Length=len(pattern),Key=key,Rect=[184,88,128,88])])
    bindings.append(binding)
    for source,keys,width,height in [("Footman's Dragonlance",["ui.92ecb2f088b1f4df9e67","ui.a39e9ac3b4639bba41f4"],128,24),("Hoopak",["ui.bf6c2c94e57c329f88df"],48,8)]:
        assert " ".join(en[k] for k in keys)==source
        key=alias(source,"".join(zh[k] for k in keys),dict(formal_keys=keys))
        sources={p["source"]["text"] for p in trace["paragraphs"] if p["source"]["text"].startswith(source)}
        assert sources=={source+(" +2 " if source=="Hoopak" else " ")}
        bindings.append(dict(SHA256=digest(next(iter(sources))),Caller=dict(Seg=0x88e,Off=0x97e),NativeBox=[184,56,312,80],Foreground=7,Background=0,Clear=1,
            Spans=[dict(Start=0,Length=len(source),Key=key,Rect=[184,56,width,height])]))
    config["HUDParagraphs"]+=bindings
    parent_en,parent_zh=catalog(base/"en.tsv"),catalog(base/"zh-TW.tsv")
    for c in trace["calls"]:
        if c["format"]["text"]!="%s" or c["vararg_1_candidate"]["text"]!="BLUE DRAGON" or c["stack"][2] not in (8004,8040):continue
        w=trace["wrappers"][c["wrapper_index"]];y=(c["stack"][2]-8000)*2
        assert c["stack"][3:5]==[8092,0x82] and w["caller"]==dict(Seg=0x88e,Off=0x16fb) and w["format"]["text"]=="%s"
        assert [(w["stack"][n]&255)*8 for n in (2,3)]==[184,y]
        key=next(k for k,v in parent_en.items() if v=="BLUE DRAGON" and k in parent_zh)
        f=dict(Pane="callsite",Group="body",Key=key,Start=0,Length=11,SHA256=digest("BLUE DRAGON"),FormatSHA256=digest("%s"),Caller=c["caller"],UpperCaller=w["caller"],UpperFormatSHA256=digest("%s"),UpperNative=[184,y],RawX=8092,RawY=c["stack"][2],Color=0x82,BackgroundOverride=23,MenuSignature="")
        if f not in config["Fields"]:config["Fields"].append(f);fields.append(dict(call_step=c["step"],source="BLUE DRAGON",binding=f))
    assert len(fields)==2
    for menu in trace["menus"]:
        if menu["Signature"] in config["Menus"]:continue
        buttons=menu["Buttons"];sources=[bytes.fromhex(b["SourceHex"]).decode() for b in buttons]
        assert menu["Count"] in (10,19) and sources==["Aim","Use","Guard","Quick","Delay","Yell","View","Speed","End"]
        config["Menus"][menu["Signature"]]="combat";menus.append(menu)
        for button,source in zip(buttons,sources):
            choices=[k for k,v in parent_en.items() if v==source and k in parent_zh]
            if choices:
                assert len({parent_zh[k] for k in choices})==1,source
                key=min(choices)
            else:
                previous=[a for a in aliases if a["source"]==source]
                if previous:key=previous[0]["key"]
                else:
                    choices=[k for k,v in en.items() if v==source and k in zh]
                    if choices:
                        assert len({zh[k] for k in choices})==1,source
                        formal=min(choices);key=alias(source,zh[formal],dict(formal_keys=[formal]))
                    else:
                        rows=[r for r in csv.DictReader((texts/"glossary.tsv").open(),delimiter="\t") if r["en"]==source]
                        assert len(rows)==1 and rows[0]["project"]=="death_knight_of_krynn",source
                        key=alias(source,rows[0]["zh"],dict(glossary=rows[0]))
            native=lambda n:n if n<400 else (n-8000)*2
            f=dict(Pane="menu",Group="footer",Key=key,Start=0,Length=len(source),SHA256=button["SHA256"],FormatSHA256=button["SHA256"],Caller=dict(Seg=0xceb,Off=0x1be),RawX=native(button["RawX"]),RawY=native(button["RawY"])+1,MenuSignature=menu["Signature"])
            config["Fields"].append(f);fields.append(dict(button_index=button["Index"],source=source,binding=f))
    assert len(menus)==2 and len(fields)==20
    all_en=dict(parent_en,**{a["key"]:a["source"] for a in aliases})
    records=hud_records(trace,config["HUDParagraphs"],all_en)
    assert len([r for r in records if r["number"] is not None])==7
    config["fine_windows"]=windows(trace)
    return config,dict(aliases=aliases,bindings=bindings,fields=fields,menus=menus,records=records)


def font_values(probe,data):
    return dict(catalog(probe/BASE/"font-zh-TW.tsv"),**{a["key"]:a["translation"] for a in data["aliases"]})


def glyph_inputs(root,output):
    probe=root/"workplace/probe";_,data=derive(probe,root/"workplace/translation")
    old=read(probe/BASE/"glyphs-16.json")
    missing=set("".join(font_values(probe,data).values()))-set("\r\n\t")-set(old["glyphs"])
    write_tsv(output/"glyph-source.tsv",["key","text"],(("glyph."+format(ord(c),"x"),c) for c in sorted(missing)))
    print("new glyphs",sorted(missing))


def merged(probe,data):
    old=read(probe/BASE/"glyphs-16.json");new=read(probe/GLYPHS)
    assert all(old[k]==new[k] for k in ("size","height","font_sha256"))
    missing=set("".join(font_values(probe,data).values()))-set("\r\n\t")-set(old["glyphs"])
    assert set(new["glyphs"])==missing
    for v in new["glyphs"].values():
        raw=base64.b64decode(v,validate=True);assert len(raw)==320 and not any(raw[256:])
    result=copy.deepcopy(old);result["glyphs"].update(new["glyphs"]);return result


def generate(root,target):
    probe=root/"workplace/probe";texts=root/"workplace/translation";base=probe/BASE
    config,data=derive(probe,texts);shutil.copytree(base,target)
    for name,column in [("en.tsv","source"),("zh-TW.tsv","translation"),("font-zh-TW.tsv","translation")]:
        values=catalog(base/name);values.update({a["key"]:a[column] for a in data["aliases"]})
        write_tsv(target/name,["key","text"],values.items())
    proof=read(base/"provenance.json")
    proof["effects_extension"]=dict(base=BASE,base_files={f.name:sha(f) for f in base.iterdir()},source_path=SOURCE,source_sha256=sha(probe/SOURCE),data=data,
        page_validation=dict(source_path=SOURCE,source_sha256=sha(probe/SOURCE)),formal_files={n:sha(texts/n) for n in FORMAL},glyph_source_sha256=sha(probe/GLYPHS))
    write(target/"inputs.json",config);write(target/"provenance.json",proof)
    write(target/"glyphs-16.json",merged(probe,data))


def check_sources(inputs,config,proof,en,zh,glyphs):
    probe=inputs.parent.parent;item=proof["effects_extension"];base=probe/BASE;texts=Path("/catalogs")
    expected,data=derive(probe,texts)
    assert item==dict(base=BASE,base_files={f.name:sha(f) for f in base.iterdir()},source_path=SOURCE,source_sha256=sha(probe/SOURCE),data=data,
        page_validation=dict(source_path=SOURCE,source_sha256=sha(probe/SOURCE)),formal_files={n:sha(texts/n) for n in FORMAL},glyph_source_sha256=sha(probe/GLYPHS)),"effects provenance"
    assert config==expected,"effects config"
    parent=read(base/"provenance.json");assert {k:v for k,v in proof.items() if k!="effects_extension"}==parent
    old_en,old_zh=catalog(base/"en.tsv"),catalog(base/"zh-TW.tsv")
    assert en==dict(old_en,**{a["key"]:a["source"] for a in data["aliases"]})
    assert zh==dict(old_zh,**{a["key"]:a["translation"] for a in data["aliases"]}),"effects translation"
    assert catalog(inputs/"font-zh-TW.tsv")==dict(catalog(base/"font-zh-TW.tsv"),**{a["key"]:a["translation"] for a in data["aliases"]})
    for name in item["base_files"]:
        if name not in ("inputs.json","provenance.json","en.tsv","zh-TW.tsv","font-zh-TW.tsv","glyphs-16.json"):assert (inputs/name).read_bytes()==(base/name).read_bytes(),name
    assert glyphs==merged(probe,data)
    return base,read(base/"inputs.json"),parent,old_en,old_zh,read(base/"glyphs-16.json")


def copy_witness(probe):
    """補上同一原版路徑中，兩個 GUI 動作截點之間的原生畫面。"""
    from PIL import Image
    output=probe/"combat-effects-20261024"
    base=read(output/"observe-r3/receipt.json")
    a=read(output/"copy-observe-r2/receipt.json");b=read(output/"copy-control-r1/receipt.json")
    expected=copy.deepcopy(base["request"]);last=expected["actions"].pop()
    assert last==dict(at=3533000000,end=3570000000,kind="text",key="",label="spell-return-combat")
    for at,end,label in [(3533000000,3539500000,"post-magic-panel"),(3539500000,3539674897,"post-magic-visible-copy"),(3539674897,3570000000,"spell-return-combat")]:
        expected["actions"].append(dict(at=at,end=end,kind="text",key="",label=label))
    assert a["request"]==b["request"]==read(output/"copy-request-r1.json")==expected
    assert a["request_sha256"]==b["request_sha256"]==sha(output/"copy-request-r1.json")
    for k in ("source_commit","go_version","exe_sha256","state_sha256","probe_sha256"):
        assert a[k]==b[k]==base[k],k
    assert a["probe_sha256"]==sha(output/"programs-r5/ui-context-probe")
    for k in ("calls","paragraphs","fill_events","wrappers","menus","hud_panels","display_changes"):
        assert a[k]==base[k],("observation changed original",k)
    assert a["checkpoints"]==b["checkpoints"] and len(a["checkpoints"])==29
    assert a["checkpoints"][:26]==base["checkpoints"][:26] and a["checkpoints"][-1]==base["checkpoints"][-1]
    assert all(not a[k] and not b[k] for k in a if k.startswith("pending_"))
    assert sha(output/"copy-observe-r2/final.state")==sha(output/"copy-control-r1/final.state")==sha(output/"control-r3/final.state")
    images=[]
    for cp in a["checkpoints"]:
        assert not cp["file_writes"] and not cp["unimplemented"]
        for suffix in (".png",".idx"):
            assert sha(output/("copy-observe-r2/"+cp["label"]+suffix))==sha(output/("copy-control-r1/"+cp["label"]+suffix))
        if cp["label"] not in ("post-magic-panel","post-magic-visible-copy"):continue
        idx=output/"copy-observe-r2"/cp["indexed_file"];assert sha(idx)==cp["indexed_sha256"]
        path=output/"copy-observe-r2"/(cp["label"]+".png")
        im=Image.open(path).convert("RGB");assert im.size==(320,200)
        assert im.tobytes()==b"".join(bytes(cp["palette"][v]) for v in idx.read_bytes())
        page=next(v["layout"]["DisplayStart"] for v in reversed(a["display_changes"]) if v["step"]<=cp["step"])
        images.append(dict(step=cp["step"],label=cp["label"],path=str(path.relative_to(probe)),sha256=sha(path),page=page))
    assert [i["page"] for i in images]==[16384,0]
    crops=[Image.open(probe/i["path"]).convert("RGB").crop((184,56,312,80)).tobytes() for i in images]
    assert crops[0]==crops[1],"original weapon panel copy"
    return dict(source_sha256=sha(output/"copy-observe-r2/receipt.json"),control_sha256=sha(output/"copy-control-r1/receipt.json"),request_sha256=sha(output/"copy-request-r1.json"),checkpoints=29,images=images,weapon_panels_equal=True)


def native(output):
    a,b=[read(output/(mode+"-r2/receipt.json")) for mode in ("observe","control")]
    for k in ("source_commit","go_version","exe_sha256","state_sha256","request_sha256","probe_sha256","request","checkpoints"):assert a[k]==b[k],k
    assert len(a["checkpoints"])==27 and all(not a[k] for k in a if k.startswith("pending_"))
    for c in a["checkpoints"]:
        assert not c["file_writes"] and not c["unimplemented"]
        for suffix in (".png",".idx"):assert sha(output/("observe-r2/"+c["label"]+suffix))==sha(output/("control-r2/"+c["label"]+suffix))
    assert sha(output/"observe-r2/final.state")==sha(output/"control-r2/final.state")==sha(output/"control-tail-r2/final.state")
    parent=output.parent/"combat-hud-20261024"
    assert a["checkpoints"][:16]==read(parent/"observe-r3/receipt.json")["checkpoints"]
    for p in a["hud_panels"]:
        assert p["step"]<p["return_instruction_step"]<p["return_step"]
    newer,control=[read(output/(mode+"-r3/receipt.json")) for mode in ("observe","control")]
    for k in ("source_commit","go_version","exe_sha256","state_sha256","request_sha256","request","checkpoints"):
        assert newer[k]==control[k]==a[k],k
    for k in ("calls","paragraphs","fill_events","wrappers","menus","hud_panels"):assert newer[k]==a[k],k
    assert [{k:v for k,v in row.items() if k not in ("menu_valid","menu_snapshot")} for row in newer["display_changes"]]==a["display_changes"]
    assert newer["probe_sha256"]==control["probe_sha256"]==sha(output/"programs-r5/ui-context-probe")
    assert all(not newer[k] and not control[k] for k in newer if k.startswith("pending_"))
    assert sha(output/"observe-r3/final.state")==sha(output/"control-r3/final.state")==sha(output/"control-r2/final.state")
    for cp in a["checkpoints"]:
        for suffix in (".png",".idx"):
            assert sha(output/("observe-r3/"+cp["label"]+suffix))==sha(output/("control-r3/"+cp["label"]+suffix))==sha(output/("observe-r2/"+cp["label"]+suffix))
    flip=next(row for row in newer["display_changes"] if row["step"]==3539400801)
    assert flip["menu_valid"] and flip["menu_snapshot"]["Signature"]==TARGET
    write(output/"native-layout-check.json",dict(checkpoints=27,panels=len(a["hud_panels"]),source_sha256=sha(output/"observe-r2/receipt.json"),additional_source_sha256=sha(output/"observe-r3/receipt.json"),first_return_flip_still_target=True))
    write(output/"copy-witness-check.json",copy_witness(output.parent))


def guards(root,output):
    source=output/"inputs-r2"
    def check(p):return check_sources(p,read(p/"inputs.json"),read(p/"provenance.json"),catalog(p/"en.tsv"),catalog(p/"zh-TW.tsv"),read(p/"glyphs-16.json"))
    check(source);cases=[]
    for name in ("template","footer","height","caller","old-field","menu-coordinate","translation","provenance"):
        with tempfile.TemporaryDirectory(dir=output,prefix="guard-") as d:
            p=Path(d);shutil.copytree(source,p,dirs_exist_ok=True);c=read(p/"inputs.json");b=c["HUDParagraphs"][-3]
            if name=="translation":
                z=catalog(p/"zh-TW.tsv");z[b["IntegerTemplateKey"]]="受到16點傷害（魔法）";write_tsv(p/"zh-TW.tsv",["key","text"],z.items())
            elif name=="provenance":
                v=read(p/"provenance.json");next(r for r in v["effects_extension"]["data"]["records"] if r["number"] is not None)["number"]=17;write(p/"provenance.json",v)
            else:
                if name=="template":b["IntegerTemplateKey"]=b["Spans"][0]["Key"]+"x"
                elif name=="footer":b["HideFooter"]=True
                elif name=="height":b["Spans"][0]["Rect"][3]=8
                elif name=="caller":b["Caller"]["Off"]+=1
                elif name=="old-field":c["Fields"][0]["RawX"]+=1
                else:c["Fields"][-1]["RawX"]+=1
                write(p/"inputs.json",c)
            try:check(p)
            except AssertionError as e:assert str(e)=={"translation":"effects translation","provenance":"effects provenance"}.get(name,"effects config"),(name,e)
            else:raise AssertionError(name)
            cases.append(name)
    with tempfile.TemporaryDirectory(dir=output,prefix="rebuild-") as d:
        p=Path(d)/"inputs";generate(root,p)
        assert {f.name for f in p.iterdir()}=={f.name for f in source.iterdir()}
        for f in source.iterdir():assert f.read_bytes()==(p/f.name).read_bytes(),f.name
    write(output/"guards-final.json",dict(cases=cases,rebuilt_files=len(list(source.iterdir())),tool_sha256=sha(Path(__file__))))


def review(output):
    from PIL import Image,ImageDraw
    revisions={"en":"r6","zh":"r6"}
    runs={lang:read(output/(lang+"-"+revision+"/receipt.json")) for lang,revision in revisions.items()};run=runs["zh"]
    data=read(output/"inputs-r2/provenance.json")["effects_extension"]["data"]
    config=read(output/"inputs-r2/inputs.json");points=[];prefix=[]
    for lang,r in runs.items():
        parent=read(output.parent/("combat-hud-20261024/"+lang+"-r4/receipt.json"))
        frames=[f for f in r["frames"] if f["step"]<=3290000000]
        assert frames==parent["frames"],("parent frames",lang)
        assert [f for f in r["list_frames"] if f["step"]<=3290000000]==parent["list_frames"]
        assert [e for e in r["list_events"] if e["Step"]<=3290000000]==parent["list_events"]
        assert r["checkpoints"][:16]==parent["checkpoints"]
        prefix.append(dict(language=lang,frames=len(frames),checkpoints=16))
    previous=read(output/"en-r4/receipt.json")
    assert runs["en"]["frames"]==previous["frames"] and runs["en"]["checkpoints"]==previous["checkpoints"],"original control changed"
    for cp in run["checkpoints"]:
        i=next(i for i,f in enumerate(run["frames"]) if f["step"]==cp["step"])
        frame,state=run["frames"][i],run["list_frames"][i]
        if cp["label"]=="spell-apply-target":
            assert frame["held"]
            last=next(e for e in reversed(run["list_events"]) if e["Step"]<=cp["step"])
            assert last["Kind"]=="footer-selection-return"
            assert next(e for e in run["list_events"] if e["Step"]>cp["step"] and e["Kind"]=="hud-update-return")["Step"]==3372322671
        else:assert not frame["held"],("stable checkpoint held",cp["label"])
        numbers=[w for w in state["words"] or [] if "Number" in w]
        if cp["label"] in ["magic-victim-"+n for n in ("one","two","three","four","five","six","seven")]:
            assert len(numbers)==1 and numbers[0]["Number"]==16
            assert len([w for w in state["words"] if w.get("Button")])==6
            assert any(w["Group"]=="footer" and w["Key"].startswith("hud.") for w in state["words"])
        points.append(dict(label=cp["label"],step=cp["step"],frame=frame["File"],sha256=frame["SHA256"],held=frame["held"],words=state["words"]))
    assert len(points)==27
    assert not any(w.get("Height")==88 for w in points[-1]["words"])
    assert len([w for w in points[-1]["words"] if w.get("Button")])==9
    visible={w["Key"] for f,s in zip(run["frames"],run["list_frames"]) if not f["held"] for w in s["words"] or []}
    assert {a["key"] for a in data["aliases"]}<=visible
    intervals=[]
    for record in data["records"]:
        frames=[f for f in run["frames"] if record["step"]<=f["step"]<record["return_step"]]
        assert frames and all(f["held"] for f in frames)
        intervals.append(dict(entry=record["step"],return_step=record["return_step"],held_samples=len(frames)))
    panel_entries=[e for e in run["list_events"] if e["Kind"]=="hud-update-entry"]
    panel_returns=[e for e in run["list_events"] if e["Kind"]=="hud-update-return"]
    assert len(panel_entries)==len(panel_returns)==9
    panels=[]
    for entry,returned in zip(panel_entries,panel_returns):
        frames=[f for f in run["frames"] if entry["Step"]<=f["step"]<returned["Step"]]
        assert frames and all(f["held"] for f in frames)
        panels.append(dict(entry=entry["Step"],return_step=returned["Step"],held_samples=len(frames)))
    images=[]
    for point in points:
        if not (point["label"].startswith("magic-victim-") or point["label"] in ("spell-next-target","spell-return-combat")):continue
        panel=Image.new("RGB",(1280,420),"#202020");draw=ImageDraw.Draw(panel)
        for i,lang in enumerate(("en","zh")):
            f=next(f for f in runs[lang]["frames"] if f["step"]==point["step"])
            assert not f["held"]
            panel.paste(Image.open(output/(lang+"-"+revisions[lang])/f["File"]).convert("RGB"),(i*640,20));draw.text((i*640+4,2),point["label"]+" / "+lang,fill="white")
        file=output/("review-final-"+point["label"]+".png");assert not file.exists();panel.save(file);images.append(dict(path=file.name,sha256=sha(file)))
    write(output/"visibility-review-final.json",dict(revisions=revisions,points=points,images=images,intervals=intervals,panels=panels,parent_prefix=prefix,visible_aliases=sorted(visible&{a["key"] for a in data["aliases"]})))


def evidence(root,output):
    gpu=read(output/"gpu-check-final.json");parent_check=read(output/"parent-old-check-final-r3.json")
    for report in (gpu,parent_check):assert report["all_submitted_pixels_equal_expected"] and report["checker_sha256"]==sha(root/"tools/ui_list_live_check.py")
    assert gpu["original_checkpoints_equal"]==27 and parent_check["original_checkpoints_equal"]==16
    assert gpu["effects"]["numeric_reports"]==7 and gpu["effects"]["panel_updates"]==9
    assert gpu["effects"]["copy_witness"]==copy_witness(output.parent)==read(output/"copy-witness-check.json")
    review_report=read(output/"visibility-review-final.json");assert len(review_report["visible_aliases"])==4 and len(review_report["intervals"])==26
    assert read(output/"guards-final.json")["tool_sha256"]==sha(Path(__file__)) and len(read(output/"guards-final.json")["cases"])==8
    fixed=read(output/"run-r6.json")
    assert fixed["binary_sha256"]==sha(output/"programs-r6/ui-list-live")==read(output/"binary-rebuild-r6.json")["binary_sha256"]
    for n,h in fixed["source_files"].items():assert sha(output/"programs-r6"/n)==sha(root/"tools"/n)==h
    for n,h in fixed["input_files"].items():assert sha(output/"inputs-r2"/n)==h
    for n in ("ui_context_probe.go","ui_menu_source.go","oracle_video_observer.go"):
        assert sha(output/"programs-r5"/n)==sha(root/"tools"/n)
    assert read(output/"native-layout-check.json")["checkpoints"]==27
    parent_path=root/"workplace/probe/combat-hud-20261024/evidence.json";parent=read(parent_path)
    sources=[parent_path,root/"workplace/input/dos/drkqueen/DQK.EXE",root/"workplace/ida/dqk.i64",root/"workplace/probe/battle-cast-20261024/control-cast-r2/final.state"]
    for n in FORMAL:
        p=root/"workplace/translation"/n
        prior=next(r for r in parent["sources"] if r["path"]==str(p.relative_to(root)));assert sha(p)==prior["sha256"];sources.append(p)
    ida=read(output/"ida-panel-r1/result.json")
    assert ida["ida_version"]=="9.4" and ida["sha256"]==sha(root/"workplace/input/dos/drkqueen/DQK.EXE")
    f=ida["functions"][0];assert (f["name"],f["start"],f["end"])==("sub_1803F",0x1803f,0x181f9)
    names=list(dict.fromkeys(list(parent["tools"])+["combat_effects_inputs.py","ui_hud_integer.go","ui_inventory_ammo.go","ui_hud_integer_test.go","early-live.sh"]))
    snapshots=output/"tool-snapshots";snapshots.mkdir()
    for n in names:shutil.copy2(root/"tools"/n,snapshots/n)
    def item(p):return dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p))
    write(output/"evidence.json",dict(draft=True,sources=[item(p) for p in sources],artifacts=[item(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name!="evidence.json"],tools={n:sha(root/"tools"/n) for n in names},gpu=gpu,parent_gpu=parent_check,original_control=dict(revision="en-r6",binary_sha256=fixed["binary_sha256"]),translated_program=dict(revision="zh-r6",binary_sha256=fixed["binary_sha256"]),docker_images=parent["docker_images"],limits="正常施法續行與七次魔法傷害文字；原文與繁中皆由同一新程式重跑，兩側原版狀態及逐格來源另驗。未推導法術規則，未驗完整戰鬥、其他格式或正式入口。"))


if __name__=="__main__":
    command=sys.argv[1]
    if command=="native":native(Path(sys.argv[2]))
    elif command=="prepare":generate(Path(sys.argv[2]),Path(sys.argv[3])/"inputs-r2")
    elif command=="review":review(Path(sys.argv[2]))
    elif command in ("glyph_inputs","guards","evidence","audit"):globals()[command](*map(Path,sys.argv[2:4]))
    else:raise SystemExit("未知命令")
