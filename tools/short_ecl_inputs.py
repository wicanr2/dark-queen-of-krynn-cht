"""以已證實的 80h 原位元串來源接入短敘事；固定 Docker 工具鏈限定。"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from literal_catalog import FORMAL, binding, catalog, digest, read, save, sha, write


def short_keys(texts):
    en,zh=catalog(texts/"en.tsv"),catalog(texts/"zh-TW.tsv")
    fragments={f["key"] for g in read(texts/"passage-candidates.json")["groups"] for s in g["sources"] for f in s["fragments"]}
    keys=[]
    for k,v in en.items():
        if not k.startswith("ecl.") or k not in zh or len(v)>15 or k in fragments:continue
        if not v.isascii() or any(ord(c)<32 for c in v+zh[k]) or "\\" in v+zh[k] or "%" in v or "JOURNAL ENTRY" in v:continue
        assert k=="ecl."+digest(v)[:20]
        keys.append(k)
    return en,zh,sorted(keys)


def native_check(probe,output):
    a,b=[read(output/(m+"-bar-r3/receipt.json")) for m in ("observe","control")]
    canonical=read(probe/"literal-catalog-20261024/observe-bar-return-r2/receipt.json")
    assert a["checkpoints"]==b["checkpoints"] and len(a["checkpoints"])==5
    for x,y in zip(a["checkpoints"],canonical["checkpoints"]):
        assert all(x[k]==y[k] for k in ("step","label","regs","ram_sha256","indexed_sha256","palette"))
        assert not x["writes"] and not x["unimplemented"]
    points=[(0x26b4,0x1cd3),(0x26b4,0x1cfc),(0x26b4,0x1d2d),(0xb72,0x311),(0x26b4,0x1d8c)]
    assert len(a["events"])==20
    for i,p in enumerate(canonical["paragraphs"]):
        events=a["events"][5*i:5*i+5]
        assert [(e["point"]["Seg"],e["point"]["Off"]) for e in events]==points
        assert events[3]["step"]==p["step"] and events[3]["buffer"]==p["source"]["text"]
        assert all(e["raw_b216"]==0x80 and e["buffer"]==p["source"]["text"] for e in events[1:])
        assert events[3]["caller"]==p["caller"] and events[3]["source_pointer"]=={"Seg":0x333e,"Off":0xb487}
        assert events[3]["raw_b1c7"]==(0x12 if p["clear"] else 0x11)
        assert events[0]["step"]<events[1]["step"]<events[3]["step"]<p["first_glyph"]<events[4]["step"]
    state=output/"observe-bar-r3/short-source.state"
    assert sha(state)==a["short_state_sha256"]
    write(output/"native-source-check.json",dict(checkpoints=5,handler_cycles=4,events=20,source_sha256=sha(output/"observe-bar-r3/receipt.json"),
        state_sha256=sha(state),canonical_sha256=sha(probe/"literal-catalog-20261024/observe-bar-return-r2/receipt.json")))


def prepare(probe,texts,font,output):
    base=probe/"literal-catalog-20261024/inputs-r3";target=output/"inputs-r1"
    assert not target.exists();shutil.copytree(base,target)
    en,zh=[catalog(base/n) for n in ("en.tsv","zh-TW.tsv")]
    source,translated,keys=short_keys(texts)
    config,origin=[read(base/n) for n in ("inputs.json","provenance.json")]
    styles=[p["style"] for p in origin["literal_catalog_extension"]["styles"]]
    old={json.dumps(p,sort_keys=True) for p in config["Paragraphs"]};added=[];new=[]
    for k in keys:
        if k in en:assert en[k]==source[k] and zh[k]==translated[k]
        else:en[k]=source[k];zh[k]=translated[k];new.append(k)
        for s in styles:
            p=binding(k,source[k],s)
            if json.dumps(p,sort_keys=True) not in old:added.append(p)
    config["Paragraphs"].extend(added)
    proof=read(output/"native-source-check.json")
    origin["short_ecl_extension"]=dict(base=str(base.relative_to(probe)),base_files={p.name:sha(p) for p in base.iterdir()},
        formal_files={n:sha(texts/n) for n in FORMAL},fragments_sha256=sha(texts/"passage-candidates.json"),
        keys=keys,new_keys=new,added_bindings=len(added),native_source=output.name+"/observe-bar-r3/receipt.json",native_sha256=proof["source_sha256"])
    save(target/"en.tsv",en);save(target/"zh-TW.tsv",zh)
    words=catalog(base/"font-zh-TW.tsv");words.update({k:translated[k] for k in keys});save(target/"font-zh-TW.tsv",words)
    for name,value in (("inputs.json",config),("provenance.json",origin)):
        (target/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
    temp=target/"generated-glyphs.json"
    subprocess.run([sys.executable,str(Path(__file__).with_name("menu_glyphs.py")),str(font),str(target/"font-zh-TW.tsv"),str(temp),"16",str(probe/"literal-catalog-20261024/outline-fallback.json")],check=True)
    glyphs,new_glyphs=read(base/"glyphs-16.json"),read(temp)
    for k,v in glyphs["glyphs"].items():assert k not in new_glyphs["glyphs"] or new_glyphs["glyphs"][k]==v
    glyphs["glyphs"].update(new_glyphs["glyphs"])
    (target/"glyphs-16.json").write_text(json.dumps(glyphs,ensure_ascii=False)+"\n");temp.unlink()
    write(output/"short-catalog-summary.json",dict(eligible=len(keys),new_keys=len(new),added_bindings=len(added),en=len(en),zh=len(zh),glyphs=len(glyphs["glyphs"]),
        max_short_chars=max(len(translated[k]) for k in keys),limits="資料接入數，不是已驗玩家路徑數。"))
    print(read(output/"short-catalog-summary.json"))


def rebuild(probe,texts,font,output):
    with tempfile.TemporaryDirectory() as temp:
        fresh=Path(temp)/output.name;fresh.mkdir();shutil.copy2(output/"native-source-check.json",fresh/"native-source-check.json")
        prepare(probe,texts,font,fresh)
        files=[]
        for p in sorted((fresh/"inputs-r1").iterdir()):
            assert p.read_bytes()==(output/"inputs-r1"/p.name).read_bytes(),p
            files.append(dict(name=p.name,sha256=sha(p)))
        write(output/"short-rebuild-check.json",dict(files=files,generator_sha256=sha(Path(__file__))))
        print("rebuilt",len(files))


def guards(output):
    from ui_list_live_check import check_short_ecl_sources
    records=[]
    for name in ("translation","binding","inherited"):
        target=output/("negative-"+name);shutil.copytree(output/"inputs-r1",target)
        config,origin=read(target/"inputs.json"),read(target/"provenance.json")
        en,zh=catalog(target/"en.tsv"),catalog(target/"zh-TW.tsv");p=origin["short_ecl_extension"]
        if name=="translation":zh[p["new_keys"][0]]+="。";save(target/"zh-TW.tsv",zh)
        elif name=="binding":config["Paragraphs"][-1]["Caller"]["Off"]+=1
        else:config["Fields"][0]["RawX"]+=1
        (target/"inputs.json").write_text(json.dumps(config,ensure_ascii=False,indent=2)+"\n")
        try:check_short_ecl_sources(target,config,origin,en,zh,read(target/"glyphs-16.json"))
        except AssertionError as e:
            assert str(e)=="short ECL "+name+" mismatch",(name,e)
            records.append(dict(case=name,rejected=True,reason=str(e)))
        else:raise AssertionError("變造未拒絕："+name)
    write(output/"short-data-guards.json",dict(cases=records,checker_sha256=sha(Path(__file__).with_name("ui_list_live_check.py"))))


if __name__=="__main__":
    action=sys.argv[1]
    if action=="native-check":native_check(*map(Path,sys.argv[2:4]))
    elif action=="prepare":prepare(*map(Path,sys.argv[2:6]))
    elif action=="rebuild":rebuild(*map(Path,sys.argv[2:6]))
    elif action=="guards":guards(Path(sys.argv[2]))
    else:raise SystemExit("未知命令")
