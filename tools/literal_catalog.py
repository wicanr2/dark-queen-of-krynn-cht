"""正式 ECL 譯文沿既有段落契約批次接入；只在固定 Docker 工具鏈執行。"""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


FORMAL=("en.tsv","zh-TW.tsv","glossary.tsv","catalog.json","glossary-additions.tsv")
STYLE_TRIPLES={(0x1D81,7,1),(0x1D81,3,1),(0x1D53,7,0),(0x1D53,3,0)}


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(text):return hashlib.sha256(text.encode()).hexdigest()


def write(path,value):
    assert not path.exists(),path
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")


def catalog(path):
    rows=list(csv.DictReader(path.open(),delimiter="\t",quoting=csv.QUOTE_NONE))
    result={r["key"]:r["text"] for r in rows}
    assert len(result)==len(rows)
    return result


def save(path,values):
    path.write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k,v in sorted(values.items())))


def selection(texts):
    en,zh=[catalog(texts/n) for n in ("en.tsv","zh-TW.tsv")]
    groups=read(texts/"passage-candidates.json")["groups"]
    fragments={f["key"] for g in groups for s in g["sources"] for f in s["fragments"]}
    eligible=[];excluded=[]
    for key,source in en.items():
        if not key.startswith("ecl.") or key not in zh:continue
        assert key=="ecl."+digest(source)[:20]
        reason=""
        if len(source)<=15:reason="name-length"
        elif key in fragments:reason="passage-fragment"
        elif not source.isascii() or any(ord(c)<32 for c in source+zh[key]) or "\\" in source+zh[key] or "%" in source:reason="control-or-format"
        elif "JOURNAL ENTRY" in source:reason="journal"
        elif len(zh[key])>144:reason="length"
        (excluded if reason else eligible).append(dict(key=key,reason=reason))
    return en,zh,sorted(r["key"] for r in eligible),excluded


def shape(p):
    return {"Caller":p["caller"],"NativeBox":p["native_box"],"Foreground":p["foreground"],
            "Background":p["background"],"Clear":p["clear"]}


def binding(key,source,style):
    return dict(Key=key,SHA256=digest(source),**style)


def windows(trace):
    lo=trace["request"]["start_steps"];hi=trace["request"]["actions"][-1]["end"]
    values=[]
    for group,end in (("calls","return_step"),("wrappers","return_step"),("paragraphs","return_step"),
                      ("fill_events","return_instruction_step"),("list_events","return_instruction_step")):
        values.extend([max(lo,p["step"]-2000),min(hi,p[end]+2000)] for p in trace[group] or [])
    values.extend([max(lo,p["step"]-2000),min(hi,p["step"]+2000)] for p in trace["display_changes"] if p["step"]>lo)
    result=[]
    for a,b in sorted(values):
        if result and a<=result[-1][1]:result[-1][1]=max(b,result[-1][1])
        else:result.append([a,b])
    return result


def native_check(output,phase="bar-route-r1",report="native-check.json"):
    a,b=[read(output/(mode+"-"+phase+"/receipt.json")) for mode in ("observe","control")]
    for key in ("source_commit","go_version","exe_sha256","state_sha256","request_sha256","probe_sha256","request","checkpoints"):
        assert a[key]==b[key],key
    assert not any(c["unimplemented"] or c["file_writes"] for c in a["checkpoints"])
    for c in a["checkpoints"]:
        name=c["label"]+".png"
        assert sha(output/("observe-"+phase)/name)==sha(output/("control-"+phase)/name)
    write(output/report,dict(checkpoints_equal=len(a["checkpoints"]),source_sha256=sha(output/("observe-"+phase+"/receipt.json")),
          limits="正常宮殿告別狀態後進酒館與交談，無座標、遭遇、物品或亂數改寫，不是從 MZ 冷啟動。"))
    print("native checkpoints",len(a["checkpoints"]))


def return_inputs(output):
    native_check(output,"bar-return-r2","return-native-check.json")
    old,new=[read(output/n/"receipt.json") for n in ("observe-bar-route-r1","observe-bar-return-r2")]
    assert new["checkpoints"][:4]==old["checkpoints"]
    source=output/"inputs-r2";target=output/"inputs-r3";shutil.copytree(source,target)
    config=read(target/"inputs.json");origin=read(target/"provenance.json")
    config["fine_windows"]=windows(new)
    origin["literal_catalog_extension"]["page_validation"]=dict(source_path=output.name+"/observe-bar-return-r2/receipt.json",sha256=sha(output/"observe-bar-return-r2/receipt.json"))
    for name,value in (("inputs.json",config),("provenance.json",origin)):
        (target/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
    same=[p.name for p in source.iterdir() if p.name not in ("inputs.json","provenance.json")]
    assert all((source/n).read_bytes()==(target/n).read_bytes() for n in same)
    a,b=read(source/"inputs.json"),read(target/"inputs.json");assert {k:v for k,v in a.items() if k!="fine_windows"}=={k:v for k,v in b.items() if k!="fine_windows"}
    write(output/"return-input-check.json",dict(unchanged_files=same,source="inputs-r2",executed="inputs-r3",only_config_change="fine_windows"))
    fixed=read(output/"run-r1.json");fixed["inputs"]={p.name:sha(p) for p in target.iterdir()}
    fixed["request_sha256"]=sha(output/"bar-return-request-r2.json")
    write(output/"run-r2.json",fixed)


def prepare(probe,texts,font,output):
    assert (output/"native-check.json").is_file()
    base=probe/"battle-text-20261024/inputs-r2"
    target=output/"inputs-r2";assert not target.exists();shutil.copytree(base,target)
    config=read(target/"inputs.json");origin=read(target/"provenance.json")
    en,zh=catalog(target/"en.tsv"),catalog(target/"zh-TW.tsv")
    formal_en,formal_zh,keys,excluded=selection(texts)
    styles={}
    for name in ("battle-text-20261024/observe-route-r1/receipt.json","pane-render-20261022/observe-palace-journal-r1/receipt.json"):
        trace=read(probe/name)
        for p in trace["paragraphs"] or []:
            triple=(p["caller"]["Off"],p["foreground"],p["clear"])
            if p["caller"]["Seg"]!=0x26B4 or triple not in STYLE_TRIPLES or triple in styles:continue
            style=shape(p);assert style["NativeBox"]==[8,136,312,184] and style["Background"]==0
            k="ecl."+digest(p["source"]["text"])[:20]
            assert binding(k,p["source"]["text"],style) in config["Paragraphs"]
            styles[triple]=dict(style=style,source_path=name,source_sha256=sha(probe/name),step=p["step"])
    assert set(styles)==STYLE_TRIPLES
    ordered=[styles[k] for k in sorted(styles)]
    old_signatures={json.dumps(p,sort_keys=True) for p in config["Paragraphs"]}
    added=[];new_keys=[]
    font_text=catalog(base/"font-zh-TW.tsv")
    for key in keys:
        if key in en:assert en[key]==formal_en[key] and zh[key]==formal_zh[key]
        else:en[key]=formal_en[key];zh[key]=formal_zh[key];new_keys.append(key)
        font_text[key]=formal_zh[key]
        for item in ordered:
            p=binding(key,formal_en[key],item["style"])
            if json.dumps(p,sort_keys=True) not in old_signatures:added.append(p)
    config["Paragraphs"].extend(added)
    actual=output/"observe-bar-route-r1/receipt.json";trace=read(actual)
    config["fine_windows"]=windows(trace)
    origin["literal_catalog_extension"]=dict(base=str(base.relative_to(probe)),base_files={p.name:sha(p) for p in base.iterdir()},
        formal_files={n:sha(texts/n) for n in FORMAL},fragments_sha256=sha(texts/"passage-candidates.json"),
        keys=keys,new_keys=new_keys,styles=ordered,added_bindings=len(added),excluded=excluded,
        outline_fallback=dict(path=str(Path(output.name)/"outline-fallback.json"),sha256=sha(output/"outline-fallback.json")),
        page_validation=dict(source_path=str(Path(output.name)/"observe-bar-route-r1/receipt.json"),sha256=sha(actual)))
    for name,value in (("inputs.json",config),("provenance.json",origin)):
        (target/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
    for name,values in (("en.tsv",en),("zh-TW.tsv",zh),("font-zh-TW.tsv",font_text)):save(target/name,values)
    temp=target/"glyphs-added.json"
    subprocess.run([sys.executable,str(Path(__file__).with_name("menu_glyphs.py")),str(font),str(target/"font-zh-TW.tsv"),str(temp),"16",str(output/"outline-fallback.json")],check=True)
    old,new=read(base/"glyphs-16.json"),read(temp)
    assert all(old[n]==new[n] for n in ("font_sha256","size","height"))
    for k,v in old["glyphs"].items():
        if k in new["glyphs"]:assert new["glyphs"][k]==v
    old["glyphs"].update(new["glyphs"]);(target/"glyphs-16.json").write_text(json.dumps(old,ensure_ascii=False)+"\n");temp.unlink()
    write(output/"catalog-summary.json",dict(eligible=len(keys),new_keys=len(new_keys),added_bindings=len(added),en=len(en),zh=len(zh),glyphs=len(old["glyphs"]),
        runtime_coverage_unknown=True,limits="正式譯文的資料接入數，不是玩家流程或全遊戲中文化覆蓋率。"))
    print(read(output/"catalog-summary.json"))


def baseline(probe,output):
    old=read(probe/"battle-text-20261024/inputs-r2/inputs.json")
    new=read(output/"inputs-r2/inputs.json")
    en=catalog(output/"inputs-r2/en.tsv")
    records=[]
    for name in ("battle-text-20261024/observe-route-r1/receipt.json","pane-render-20261022/observe-palace-journal-r1/receipt.json"):
        trace=read(probe/name)
        for p in trace["paragraphs"] or []:
            actual=shape(p);h=digest(p["source"]["text"])
            matches=lambda c:[b for b in c["Paragraphs"] if b["SHA256"]==h and en[b["Key"]]==p["source"]["text"] and all(b[k]==v for k,v in actual.items())]
            assert matches(old)==matches(new),(name,p["step"],p["source"]["text"])
        records.append(dict(source=name,source_sha256=sha(probe/name),paragraphs=len(trace["paragraphs"] or [])))
    write(output/"baseline-selection-check-r2.json",dict(records=records,selection_unchanged=True,
        limits="只證明固定原版收據的選譯資料與舊字模不變；沒有重新執行那批 GPU，也不外推新路徑。"))
    print(records)


def outline_pack(output):
    import base64
    from PIL import Image
    folder=output/"outline-r2";source=read(folder/"outline-source.json")
    glyphs={};rows=[]
    for row in source["glyphs"]:
        svg=folder/row["svg"];assert sha(svg)==row["sha256"]
        path=svg.with_suffix(".png");im=Image.open(path).convert("RGB")
        red,green,blue=im.split();raw=red.tobytes()
        assert im.size==(16,20) and raw==green.tobytes()==blue.tobytes() and not any(raw[256:])
        glyphs[row["char"]]=base64.b64encode(raw).decode()
        rows.append(dict(char=row["char"],png_sha256=sha(path),svg_sha256=sha(svg),ink_box=red.getbbox(),outline=row))
    write(output/"outline-fallback.json",dict(font_sha256=source["font_sha256"],size=16,height=20,glyphs=glyphs))
    write(output/"outline-proof.json",dict(source_sha256=sha(folder/"outline-source.json"),browser=read(folder/"outline-browser.json"),glyphs=rows,
        limits="僅對超框的新字直接光柵化原始 16px 字型輪廓，沒有裁切、縮放字墨或修改舊點陣。"))


def layout(output):
    import base64
    p=output/"inputs-r2";origin=read(p/"provenance.json")["literal_catalog_extension"]
    zh=catalog(p/"zh-TW.tsv");glyphs=read(p/"glyphs-16.json")
    counts={}
    for key in origin["keys"]:
        text=zh[key];lines=[]
        while text:
            n=min(38,len(text))
            if n<len(text) and text[n] in "，。！？、；：」』）》】":n-=1
            if n<len(text) and text[n-1] in "「『（《【":n-=1
            assert n>0;lines.append(text[:n]);text=text[n:]
        assert len(lines)<=4,key
        counts[key]=len(lines)
    for raw in glyphs["glyphs"].values():
        value=base64.b64decode(raw,validate=True);assert len(value)==320 and not any(value[256:])
    write(output/"layout-check.json",dict(texts=len(counts),max_lines=max(counts.values()),glyphs=len(glyphs["glyphs"]),
        counts=counts,limits="單段容量與點陣安全框；未把任意接續合併、所有玩家路徑或正式字級視為完成。"))
    print("layout",len(counts),"max lines",max(counts.values()))


def guards(output,revision="r2"):
    assert revision.startswith("r") and revision[1:].isdigit() and int(revision[1:])>0
    from ui_list_live_check import check_literal_catalog_sources
    base=output/"inputs-r2";proof=read(base/"provenance.json")["literal_catalog_extension"]
    old_count=len(read(output.parent/proof["base"]/"inputs.json")["Paragraphs"])
    reports=[]
    cases=[("short","key selection"),("context","binding matrix"),("translation","translation"),
           ("missing-glyph","glyph set"),("outline","outline"),("inherited","inherited config")]
    for name,part in cases:
        target=output/("negative-"+name+"-"+revision);shutil.copytree(base,target)
        config=read(target/"inputs.json");origin=read(target/"provenance.json")
        en,zh=catalog(target/"en.tsv"),catalog(target/"zh-TW.tsv");glyphs=read(target/"glyphs-16.json")
        if name=="short":
            key="ecl."+digest("A QUIET BAR.")[:20]
            origin["literal_catalog_extension"]["keys"].append(key);origin["literal_catalog_extension"]["keys"].sort()
            origin["literal_catalog_extension"]["new_keys"].append(key);origin["literal_catalog_extension"]["new_keys"].sort()
            en[key]=catalog(Path("/catalogs/en.tsv"))[key];zh[key]=catalog(Path("/catalogs/zh-TW.tsv"))[key]
            for item in proof["styles"]:config["Paragraphs"].append(binding(key,en[key],item["style"]))
            origin["literal_catalog_extension"]["added_bindings"]+=4
            font=catalog(target/"font-zh-TW.tsv");font[key]=zh[key];save(target/"font-zh-TW.tsv",font)
        elif name=="context":config["Paragraphs"][old_count]["Caller"]["Off"]+=1
        elif name=="translation":zh[proof["new_keys"][0]]+="。"
        elif name=="missing-glyph":del glyphs["glyphs"]["描"]
        elif name=="outline":
            import base64
            raw=bytearray(base64.b64decode(glyphs["glyphs"]["描"]));raw[0]^=1;glyphs["glyphs"]["描"]=base64.b64encode(raw).decode()
        else:config["Fields"][0]["RawX"]+=1
        for path,value in (("inputs.json",config),("provenance.json",origin),("glyphs-16.json",glyphs)):
            (target/path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
        save(target/"zh-TW.tsv",zh)
        save(target/"en.tsv",en)
        try:check_literal_catalog_sources(target,config,origin,en,zh,glyphs)
        except AssertionError as error:
            assert "literal catalog "+part+" mismatch" in str(error),(name,error)
            reports.append(dict(case=name,rejected=True,reason=str(error)))
        else:raise AssertionError("變造未拒絕："+name)
    write(output/("guards-"+revision+".json"),dict(cases=reports,checker_sha256=sha(Path(__file__).with_name("ui_list_live_check.py"))))
    print("guard cases",len(reports))


def rebuild(probe,texts,font,output,revision="r4"):
    assert revision.startswith("r") and revision[1:].isdigit() and int(revision[1:])>0
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        fresh=Path(temp)/output.name;fresh.mkdir()
        for name in ("native-check.json","observe-bar-route-r1/receipt.json","outline-fallback.json"):
            p=fresh/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(output/name,p)
        prepare(probe,texts,font,fresh)
        shutil.copytree(fresh/"inputs-r2",fresh/"inputs-r3")
        config=read(fresh/"inputs-r3/inputs.json");origin=read(fresh/"inputs-r3/provenance.json")
        trace_path=output/"observe-bar-return-r2/receipt.json";trace=read(trace_path)
        config["fine_windows"]=windows(trace)
        origin["literal_catalog_extension"]["page_validation"]=dict(source_path=output.name+"/observe-bar-return-r2/receipt.json",sha256=sha(trace_path))
        for name,value in (("inputs.json",config),("provenance.json",origin)):
            (fresh/"inputs-r3"/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
        files=[]
        for folder in ("inputs-r2","inputs-r3"):
            for path in sorted((fresh/folder).iterdir()):
                assert path.read_bytes()==(output/folder/path.name).read_bytes(),path
                files.append(dict(name=folder+"/"+path.name,sha256=sha(path)))
        write(output/("rebuild-check-"+revision+".json"),dict(files=files,generator_sha256=sha(Path(__file__))))
        print("rebuilt files",len(files))


def guard_recheck(output,revision="r2"):
    assert revision.startswith("r") and revision[1:].isdigit() and int(revision[1:])>0
    from ui_list_live_check import check_literal_catalog_sources
    records=[]
    for row in read(output/"guards-r2.json")["cases"]:
        folder=output/("negative-"+row["case"]+"-r2")
        try:check_literal_catalog_sources(folder,read(folder/"inputs.json"),read(folder/"provenance.json"),
                                         catalog(folder/"en.tsv"),catalog(folder/"zh-TW.tsv"),read(folder/"glyphs-16.json"))
        except AssertionError as error:assert str(error)==row["reason"];records.append(row)
        else:raise AssertionError(row["case"])
    write(output/("guards-final-"+revision+".json"),dict(cases=records,checker_sha256=sha(Path(__file__).with_name("ui_list_live_check.py"))))
    print("rechecked guards",len(records))


def reader_regression(probe,output):
    from ui_journal_reader_check import reader_model
    inputs=output/"inputs-r2";config=read(inputs/"inputs.json");records=[]
    cases=[("54","pane-render-20261022/observe-palace-journal-r1/receipt.json","battle-text-20261024/legacy54-"),
           ("65","battle-text-20261024/observe-arrival-r2/receipt.json","battle-text-20261024/arrival-")]
    for number,native,prefix in cases:
        trace=read(probe/native)
        a,b=[read(probe/(prefix+lang+"-r4/receipt.json")) for lang in ("en","zh")]
        accepted=[e for e in b["list_events"] if e["Kind"]=="paragraph-before-glyph"]
        result=reader_model(inputs,config,trace["paragraphs"],accepted,(a,b))
        assert any(e["action"]=="open" and e["page"]["Entry"]==int(number) for e in b["reader_events"])
        records.append(dict(entry=int(number),source=native,source_sha256=sha(probe/native),frames=len(b["frames"]),model=result))
    write(output/"reader-regression.json",dict(records=records,model_sha256=sha(Path(__file__).with_name("ui_journal_reader_check.py")),
        limits="新完整目錄對舊實際畫格的閱讀生命週期檢查；未重新執行舊 GPU，亦不外推新增引用。"))
    print("reader regressions",[r["entry"] for r in records])


def review(output):
    from PIL import Image,ImageDraw,ImageFont
    records=[];a,b=[read(output/(lang+"-r2/receipt.json")) for lang in ("en","zh")]
    for cp in b["checkpoints"]:
        pair=Image.new("RGB",(1280,420),"#202020");draw=ImageDraw.Draw(pair);sources=[]
        for index,(lang,run) in enumerate((("en",a),("zh",b))):
            f=next(f for f in run["frames"] if f["step"]==cp["step"]);assert not f["held"]
            path=output/(lang+"-r2")/f["File"];pair.paste(Image.open(path).convert("RGB"),(index*640,20))
            draw.text((index*640+4,2),cp["label"]+" / "+lang,fill="white")
            sources.append(dict(path=str(path.relative_to(output)),sha256=sha(path),step=f["step"]))
        path=output/("review-r2-"+cp["label"]+".png");assert not path.exists();pair.save(path)
        records.append(dict(label=cp["label"],sources=sources,panel=path.name,sha256=sha(path)))
    font=ImageFont.truetype("/font/jf-openhuninn-2.1.ttf",16)
    sheet=Image.new("RGB",(640,200),"#303030");draw=ImageDraw.Draw(sheet)
    for i,(code,char) in enumerate((("63cf","描"),("6cc9","泉"))):
        original=Image.new("L",(32,20));ImageDraw.Draw(original).text((4,0),char,font=font,fill=255,anchor="lt")
        actual=Image.open(output/"outline-r2"/(code+".png")).convert("RGB")
        draw.text((i*320+4,4),code+" original / outline",fill="white")
        sheet.paste(original.resize((192,120),Image.Resampling.NEAREST).convert("RGB"),(i*320,30))
        sheet.paste(actual.resize((96,120),Image.Resampling.NEAREST),(i*320+192,30))
    sheet.save(output/"review-r2-glyphs.png")
    write(output/"review-images-r2.json",dict(points=records,glyph_panel_sha256=sha(output/"review-r2-glyphs.png"),
        limits="酒館短標題與未綁定選單維持原文；只宣稱新長台詞與既有提示的實際呈現，輪廓字模另為離線抽查。"))
    print("review points",len(records))


def evidence(root,output):
    parent=root/"workplace/probe/battle-text-20261024/evidence.json";previous=read(parent)
    fixed=read(output/"run-r2.json");report=read(output/"gpu-check-return-r2.json")
    assert report["checker_sha256"]==sha(root/"tools/ui_list_live_check.py") and report["all_submitted_pixels_equal_expected"]
    assert report["reader_model_sha256"]==sha(root/"tools/ui_journal_reader_check.py")
    assert report["original_checkpoints_equal"]==5 and report["literal_catalog"]["visible_new_keys"]
    for name,h in fixed["source_files"].items():assert sha(root/name)==sha(output/"programs-r1"/Path(name).name)==h
    assert sha(output/"programs-r1/ui-list-live")==fixed["program_sha256"]
    for name,h in fixed["inputs"].items():assert sha(output/"inputs-r3"/name)==h
    assert read(output/"rebuild-check-r4.json")["generator_sha256"]==sha(Path(__file__))
    assert len(read(output/"guards-final-r3.json")["cases"])==6
    assert read(output/"guards-final-r3.json")["checker_sha256"]==sha(root/"tools/ui_list_live_check.py")
    assert len(read(output/"review-images-r2.json")["points"])==5
    assert read(output/"baseline-selection-check-r2.json")["selection_unchanged"]
    names=list(previous["tools"])+["literal_catalog.py","glyph_outline.py","glyph_outline_capture.mjs"]
    assert len(names)==len(set(names))
    folder=output/"tool-snapshots";folder.mkdir()
    for name in names:shutil.copy2(root/"tools"/name,folder/name)
    def item(path):return dict(path=str(path.relative_to(root)),bytes=path.stat().st_size,sha256=sha(path))
    sources=[item(parent)]
    for old in previous["sources"]:
        if old["path"].startswith("workplace/translation/") and Path(old["path"]).name in FORMAL:
            p=root/old["path"];assert sha(p)==old["sha256"];sources.append(item(p))
    sources.extend(item(root/n) for n in ("workplace/input/dos/drkqueen/DQK.EXE","workplace/translation/passage-candidates.json"))
    target=output/"evidence.json"
    write(target,dict(draft=True,sources=sources,artifacts=[item(p) for p in sorted(output.rglob("*")) if p.is_file() and p!=target],
          tools={n:sha(root/"tools"/n) for n in names},runtime_unchanged=True,report=report,summary=read(output/"catalog-summary.json"),
          docker_images={**previous["docker_images"],"fonttools":"sha256:6d849051db2e108262fa689160011dc64045cc402f61985548a525559d3a1cf3",
                         "chromium":"sha256:f1e7e01021efd65dd1a2c56064be399f3e4de00fd021ac561325f2bfbb2b837a"},
          limits="新增 5,045 鍵與 20,231 個情境綁定是資料接入；本輪正常 GUI 只驗酒館一段新台詞，不把五千筆稱為五千條已驗玩家路徑。短句、相鄰片段、新引用、其他介面及正式入口仍未完成。"))
    saved=read(target);print(dict(artifacts=len(saved["artifacts"]),sources=len(sources),tools=len(names)))


def audit(root,output):
    data=read(output/"evidence.json")
    for row in data["sources"]+data["artifacts"]:
        p=root/row["path"];assert p.is_file() and p.stat().st_size==row["bytes"] and sha(p)==row["sha256"],p
        assert p.stat().st_uid==1000 and p.stat().st_gid==1000,p
    for name,h in data["tools"].items():assert sha(root/"tools"/name)==sha(output/"tool-snapshots"/name)==h
    assert {str(p.relative_to(root)) for p in output.rglob("*") if p.is_file() and p.name!="evidence.json"}=={r["path"] for r in data["artifacts"]}
    print("audited",len(data["artifacts"]),"artifacts",len(data["sources"]),"sources",len(data["tools"]),"tools")


if __name__=="__main__":
    action=sys.argv[1]
    if action=="native-check":native_check(Path(sys.argv[2]))
    elif action=="return-inputs":return_inputs(Path(sys.argv[2]))
    elif action=="prepare":prepare(*map(Path,sys.argv[2:6]))
    elif action=="baseline":baseline(*map(Path,sys.argv[2:4]))
    elif action=="outline-pack":outline_pack(Path(sys.argv[2]))
    elif action=="layout":layout(Path(sys.argv[2]))
    elif action=="guards":guards(Path(sys.argv[2]),sys.argv[3] if len(sys.argv)>3 else "r2")
    elif action=="rebuild":rebuild(*map(Path,sys.argv[2:6]),sys.argv[6] if len(sys.argv)>6 else "r4")
    elif action=="guard-recheck":guard_recheck(Path(sys.argv[2]),sys.argv[3] if len(sys.argv)>3 else "r2")
    elif action=="reader-regression":reader_regression(*map(Path,sys.argv[2:4]))
    elif action=="review":review(Path(sys.argv[2]))
    elif action=="evidence":evidence(*map(Path,sys.argv[2:4]))
    elif action=="audit":audit(*map(Path,sys.argv[2:4]))
    else:raise SystemExit("未知命令")
